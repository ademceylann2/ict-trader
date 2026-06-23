#!/usr/bin/env python3
"""
ICT Trader v3 — Inner Circle Trader tam metodoloji botu.
"""

import time
import sys
from datetime import datetime

from config import SYMBOLS, TIMEFRAMES
from market_data import MarketData
from ict_analyzer import ICTAnalyzer
from news_monitor import NewsMonitor
from notifier import send_signal, send_news_alert, send_startup_message
from executor import execute_signal, get_account_info, ALPACA_API_KEY

SCAN_INTERVAL = 300
sent_signals  = set()

# ── Backtest filtreleri ──────────────────────────────────────────────────────
# NY Close tüm sembollerde %0 win rate → tamamen kapat
SKIP_KZ_GLOBAL    = {"ny_close"}

# Endeksler (ES/NQ) için sadece London çalışıyor
INDEX_SYMBOLS     = {"ES=F", "NQ=F"}
SKIP_KZ_FOR_INDEX = {"asia", "ny_close", "new_york"}  # sadece london aktif

# Crypto için minimum ★5 (BTC ★5=%100, ★4=%0)
CRYPTO_SYMBOLS    = {"BTC-USD", "ETH-USD"}
CRYPTO_MIN_STARS  = 5

# SMT Divergence korelasyon çiftleri
SMT_PAIRS = {
    "EURUSD=X": "GBPUSD=X",
    "GBPUSD=X": "EURUSD=X",
    "ES=F":     "NQ=F",
    "NQ=F":     "ES=F",
    "BTC-USD":  "ETH-USD",
    "ETH-USD":  "BTC-USD",
}


def scan_symbol(symbol: str, data: MarketData, analyzer: ICTAnalyzer,
                kill_zone: str) -> None:
    df_htf   = data.get_ohlcv(symbol, interval=TIMEFRAMES["htf"], period="10d")
    df_mtf   = data.get_ohlcv(symbol, interval=TIMEFRAMES["mtf"], period="3d")
    df_daily = data.get_ohlcv(symbol, interval="1d", period="90d")

    if df_htf.empty or df_mtf.empty:
        print(f"  [{symbol}] Veri alınamadı, atlanıyor.")
        return

    # NY Close tüm sembollerde kötü → global filtre
    if kill_zone in SKIP_KZ_GLOBAL:
        print(f"  [{symbol}] ny_close atlanıyor (backtest: %0 win rate)")
        return

    # Endeksler sadece London'da iyi
    if symbol in INDEX_SYMBOLS and kill_zone in SKIP_KZ_FOR_INDEX:
        print(f"  [{symbol}] {kill_zone} endeks için atlanıyor (backtest filtresi)")
        return

    # SMT için korelasyonlu çift
    df_corr = None
    corr_sym = SMT_PAIRS.get(symbol)
    if corr_sym:
        df_corr = data.get_ohlcv(corr_sym, interval=TIMEFRAMES["mtf"], period="3d")
        if df_corr.empty:
            df_corr = None

    signal = analyzer.generate_signal(
        df_htf, df_mtf, kill_zone, news_clear=True,
        df_daily=df_daily if not df_daily.empty else None,
        df_corr=df_corr,
    )

    if signal:
        # Crypto için minimum ★5 filtresi (backtest: ★4=%0, ★5=%100)
        if symbol in CRYPTO_SYMBOLS and signal.confidence < CRYPTO_MIN_STARS:
            print(f"  [{symbol}] {signal.model} ★{signal.confidence} crypto min altında, atlanıyor")
            return

        # OB_FVG tek başına asla gönderme — UNICORN veya Silver Bullet olmalı
        if signal.model == "OB_FVG" and signal.confidence < 5:
            print(f"  [{symbol}] OB_FVG ★{signal.confidence} yeterli değil, atlanıyor")
            return

        sig_key = f"{signal.symbol}_{signal.direction}_{signal.entry}"
        if sig_key not in sent_signals:
            stars = "★" * signal.confidence + "☆" * (5 - signal.confidence)
            print(f"  [{symbol}] ✅ {signal.model} {signal.direction} @ {signal.entry} [{stars}]")
            send_signal(signal)
            # Alpaca entegrasyonu aktifse otomatik emir gönder
            if ALPACA_API_KEY:
                execute_signal(signal)
            sent_signals.add(sig_key)
    else:
        print(f"  [{symbol}] Kurulum yok.")


def main():
    print("=" * 50)
    print("  ICT TRADER v3 BAŞLADI")
    print("=" * 50)

    data = MarketData()
    news = NewsMonitor(high_impact_only=True)

    all_symbols = (
        SYMBOLS["forex"] + SYMBOLS["crypto"] + SYMBOLS["indices"]
    )

    # Alpaca hesap bilgisi
    if ALPACA_API_KEY:
        try:
            acc = get_account_info()
            print(f"  Alpaca {('PAPER' if True else 'LIVE')} | Sermaye: ${acc['equity']:.2f}")
        except Exception as e:
            print(f"  Alpaca bağlantı hatası: {e}")

    send_startup_message(all_symbols)

    while True:
        now = datetime.utcnow()
        print(f"\n[{now.strftime('%H:%M:%S UTC')}] Tarama başlıyor...")

        kill_zone = data.get_current_kill_zone()
        if kill_zone:
            print(f"  Kill Zone: {kill_zone.upper()} aktif")
        else:
            print("  Kill Zone dışı — haber takibi devam ediyor")

        in_news, news_event = news.is_news_window(minutes_before=30, minutes_after=30)
        if in_news:
            print(f"  ⚠️  HABER PENCERESİ: {news_event} — sinyal atlanıyor")
            send_news_alert({"currency": news_event.split("-")[0].strip(),
                             "event": news_event, "time": "ŞIMDI",
                             "minutes_away": 0})
            time.sleep(SCAN_INTERVAL)
            continue

        upcoming = news.get_upcoming_events(hours=2)
        for ev in upcoming:
            if ev.get("minutes_away", 999) <= 30:
                print(f"  ⚠️  Haber {ev['minutes_away']}dk sonra: {ev['currency']} {ev['event']}")
                send_news_alert(ev)

        if kill_zone:
            for symbol in all_symbols:
                analyzer = ICTAnalyzer(symbol)
                print(f"  Taranıyor: {symbol}")
                scan_symbol(symbol, data, analyzer, kill_zone)
        else:
            print("  (Kill Zone dışı — sadece haber takibi)")

        print(f"  Sonraki tarama: {SCAN_INTERVAL//60} dakika sonra")
        time.sleep(SCAN_INTERVAL)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nBot durduruldu.")
        sys.exit(0)
