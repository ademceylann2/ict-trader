#!/usr/bin/env python3
"""
ICT Trader - Inner Circle Trader metodolojisiyle otomatik sinyal botu.
Çalıştırmak için: python3 main.py
"""

import time
import sys
from datetime import datetime

from config import SYMBOLS, TIMEFRAMES
from market_data import MarketData
from ict_analyzer import ICTAnalyzer
from news_monitor import NewsMonitor
from notifier import send_signal, send_news_alert, send_startup_message

SCAN_INTERVAL = 300   # Her 5 dakikada bir tara
sent_signals  = set() # Aynı sinyali tekrar gönderme


def scan_symbol(symbol: str, data: MarketData, analyzer: ICTAnalyzer,
                kill_zone: str) -> None:
    """Tek bir sembolü ICT mantığıyla analiz et."""
    df_htf = data.get_ohlcv(symbol, interval=TIMEFRAMES["htf"], period="10d")
    df_mtf = data.get_ohlcv(symbol, interval=TIMEFRAMES["mtf"], period="3d")

    if df_htf.empty or df_mtf.empty:
        print(f"  [{symbol}] Veri alınamadı, atlanıyor.")
        return

    signal = analyzer.generate_signal(df_htf, df_mtf, kill_zone, news_clear=True)

    if signal:
        sig_key = f"{signal.symbol}_{signal.direction}_{signal.entry}"
        if sig_key not in sent_signals:
            print(f"  [{symbol}] ✅ Sinyal bulundu: {signal.direction} @ {signal.entry}")
            send_signal(signal)
            sent_signals.add(sig_key)
    else:
        print(f"  [{symbol}] Kurulum yok.")


def main():
    print("=" * 50)
    print("  ICT TRADER BAŞLADI")
    print("=" * 50)

    data     = MarketData()
    news     = NewsMonitor(high_impact_only=True)

    all_symbols = (
        SYMBOLS["forex"] +
        SYMBOLS["crypto"] +
        SYMBOLS["indices"]
    )

    send_startup_message(all_symbols)

    while True:
        now = datetime.utcnow()
        print(f"\n[{now.strftime('%H:%M:%S UTC')}] Tarama başlıyor...")

        # Kill Zone kontrolü
        kill_zone = data.get_current_kill_zone()
        if kill_zone:
            print(f"  Kill Zone: {kill_zone.upper()} aktif")
        else:
            print("  Kill Zone dışı - bekleniyor...")

        # Haber kontrolü
        in_news, news_event = news.is_news_window(minutes_before=30, minutes_after=30)
        if in_news:
            print(f"  ⚠️  HABER PENCERESİ: {news_event} - sinyal atlanıyor")
            send_news_alert({"currency": news_event.split("-")[0].strip(),
                             "event": news_event, "time": "ŞIMDI"})
            time.sleep(SCAN_INTERVAL)
            continue

        # Yaklaşan haberleri bildir
        upcoming = news.get_upcoming_events(hours=2)
        for ev in upcoming:
            if ev.get("minutes_away", 999) <= 30:
                print(f"  ⚠️  Haber {ev['minutes_away']}dk sonra: {ev['currency']} {ev['event']}")
                send_news_alert(ev)

        # Kill Zone aktifse tara
        if kill_zone:
            for symbol in all_symbols:
                analyzer = ICTAnalyzer(symbol)
                print(f"  Taranıyor: {symbol}")
                scan_symbol(symbol, data, analyzer, kill_zone)
        else:
            print("  (Kill Zone dışı - sadece haber takibi)")

        print(f"  Sonraki tarama: {SCAN_INTERVAL//60} dakika sonra")
        time.sleep(SCAN_INTERVAL)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nBot durduruldu.")
        sys.exit(0)
