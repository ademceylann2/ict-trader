"""
ICT Trader — Alpaca Paper Trading Executor
ICT sinyallerini otomatik olarak Alpaca'ya iletir.

Desteklenen semboller: BTC/USD, ETH/USD (crypto 24/7)
"""

import os
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest, LimitOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce, OrderType
from alpaca.trading.requests import TakeProfitRequest, StopLossRequest
from ict_analyzer import Signal
from notifier import send_telegram

ALPACA_API_KEY    = os.environ.get("ALPACA_API_KEY", "")
ALPACA_API_SECRET = os.environ.get("ALPACA_API_SECRET", "")
PAPER_TRADING     = os.environ.get("ALPACA_PAPER", "true").lower() == "true"

# ICT sembolü → Alpaca sembolü
SYMBOL_MAP = {
    "BTC-USD":  "BTC/USD",
    "ETH-USD":  "ETH/USD",
}

# Kaç $ risk per trade (sabit dolar tutarı)
RISK_PER_TRADE_USD = float(os.environ.get("RISK_PER_TRADE_USD", "5.0"))


def get_client() -> TradingClient:
    return TradingClient(
        api_key=ALPACA_API_KEY,
        secret_key=ALPACA_API_SECRET,
        paper=PAPER_TRADING,
    )


def get_account_info() -> dict:
    client = get_client()
    account = client.get_account()
    return {
        "equity":       float(account.equity),
        "cash":         float(account.cash),
        "buying_power": float(account.buying_power),
        "status":       account.status,
    }


def calculate_qty(signal: Signal, account_equity: float) -> float:
    """
    Risk-based pozisyon boyutu:
    qty = risk_usd / (entry - sl)
    """
    risk_usd = RISK_PER_TRADE_USD
    price_risk = abs(signal.entry - signal.sl)
    if price_risk <= 0:
        return 0.0

    qty = risk_usd / price_risk

    # Maks pozisyon: toplam sermayenin %20'si
    max_position_usd = account_equity * 0.20
    max_qty = max_position_usd / signal.entry
    qty = min(qty, max_qty)

    # Crypto için 6 ondalık hassasiyet
    return round(qty, 6)


def execute_signal(signal: Signal) -> bool:
    """
    ICT sinyalini Alpaca'da işleme çevirir.
    Sadece desteklenen semboller için çalışır.
    """
    alpaca_sym = SYMBOL_MAP.get(signal.symbol)
    if not alpaca_sym:
        print(f"[EXECUTOR] {signal.symbol} Alpaca'da desteklenmiyor, atlanıyor.")
        return False

    if not ALPACA_API_KEY or not ALPACA_API_SECRET:
        print("[EXECUTOR] API key eksik — .env dosyasını kontrol et.")
        return False

    try:
        client  = get_client()
        account = get_account_info()
        equity  = account["equity"]
        qty     = calculate_qty(signal, equity)

        if qty <= 0:
            print(f"[EXECUTOR] Pozisyon boyutu sıfır, işlem atlandı.")
            return False

        side = OrderSide.BUY if signal.direction == "LONG" else OrderSide.SELL

        # Bracket order: entry + SL + TP1
        order_req = MarketOrderRequest(
            symbol=alpaca_sym,
            qty=qty,
            side=side,
            time_in_force=TimeInForce.GTC,
            order_class="bracket",
            take_profit=TakeProfitRequest(limit_price=round(signal.tp1, 2)),
            stop_loss=StopLossRequest(stop_price=round(signal.sl, 2)),
        )

        order = client.submit_order(order_req)

        mode = "📄 PAPER" if PAPER_TRADING else "💰 GERÇEK"
        msg = f"""
{mode} — EMİR GÖNDERİLDİ ✅

🎯 {signal.symbol} → {alpaca_sym}
{'🟢 LONG' if signal.direction=='LONG' else '🔴 SHORT'} | {signal.model} ★{signal.confidence}

💰 Entry:  {signal.entry}
🛑 SL:     {round(signal.sl, 2)}
🎯 TP1:    {round(signal.tp1, 2)}
📊 R:R     1:{signal.rr}
📦 Miktar: {qty}
💼 Sermaye: ${equity:.2f}
🆔 Order:  {order.id}
"""
        send_telegram(msg)
        print(f"[EXECUTOR] ✅ Emir gönderildi: {order.id}")
        return True

    except Exception as e:
        error_msg = f"[EXECUTOR] ❌ Emir hatası ({signal.symbol}): {e}"
        print(error_msg)
        send_telegram(f"⚠️ Emir hatası: {e}")
        return False


def close_all_positions():
    """Tüm açık pozisyonları kapat (acil durum)."""
    try:
        client = get_client()
        client.close_all_positions(cancel_orders=True)
        send_telegram("🚨 TÜM POZİSYONLAR KAPATILDI")
        print("[EXECUTOR] Tüm pozisyonlar kapatıldı.")
    except Exception as e:
        print(f"[EXECUTOR] Kapatma hatası: {e}")


def get_positions() -> list:
    """Açık pozisyonları döndür."""
    try:
        client    = get_client()
        positions = client.get_all_positions()
        return [{"symbol": p.symbol, "qty": p.qty,
                 "side": p.side, "unrealized_pl": p.unrealized_pl,
                 "current_price": p.current_price} for p in positions]
    except Exception as e:
        print(f"[EXECUTOR] Pozisyon sorgu hatası: {e}")
        return []
