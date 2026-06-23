"""
ICT Trader — OANDA Executor
Altın (XAU/USD), Nasdaq (US100), Forex çiftlerinde otomatik trade.

Demo URL : https://api-fxpractice.oanda.com
Live URL : https://api-fxtrade.oanda.com
"""

import os
import oandapyV20
import oandapyV20.endpoints.orders as orders
import oandapyV20.endpoints.trades as trades
import oandapyV20.endpoints.accounts as accounts
import oandapyV20.endpoints.pricing as pricing
from ict_analyzer import Signal
from notifier import send_telegram

OANDA_TOKEN      = os.environ.get("OANDA_TOKEN", "")
OANDA_ACCOUNT_ID = os.environ.get("OANDA_ACCOUNT_ID", "")
OANDA_DEMO       = os.environ.get("OANDA_DEMO", "true").lower() == "true"

OANDA_ENV = "practice" if OANDA_DEMO else "live"

# ICT sembolü → OANDA enstrümanı
SYMBOL_MAP = {
    "GC=F":     "XAU_USD",    # Altın
    "NQ=F":     "NAS100_USD", # Nasdaq 100
    "ES=F":     "SPX500_USD", # S&P 500
    "EURUSD=X": "EUR_USD",
    "GBPUSD=X": "GBP_USD",
    "USDJPY=X": "USD_JPY",
    "BTC-USD":  "BTC_USD",
    "ETH-USD":  "ETH_USD",
}

# Sembol başına pip değerleri (yaklaşık, risk hesabı için)
PIP_VALUES = {
    "XAU_USD":    0.01,   # 1 pip = $0.01 per unit
    "NAS100_USD": 1.0,    # 1 pip = $1 per unit
    "SPX500_USD": 1.0,
    "EUR_USD":    0.0001,
    "GBP_USD":    0.0001,
    "USD_JPY":    0.01,
    "BTC_USD":    1.0,
    "ETH_USD":    0.1,
}

# Trade başına risk (USD)
RISK_PER_TRADE_USD = float(os.environ.get("RISK_PER_TRADE_USD", "5.0"))


def get_client():
    return oandapyV20.API(access_token=OANDA_TOKEN, environment=OANDA_ENV)


def get_account_info() -> dict:
    client = get_client()
    r = accounts.AccountSummary(OANDA_ACCOUNT_ID)
    client.request(r)
    acc = r.response["account"]
    return {
        "balance":       float(acc["balance"]),
        "nav":           float(acc["NAV"]),
        "unrealized_pl": float(acc["unrealizedPL"]),
        "open_trades":   int(acc["openTradeCount"]),
    }


def get_current_price(instrument: str) -> float:
    client = get_client()
    params = {"instruments": instrument}
    r = pricing.PricingInfo(OANDA_ACCOUNT_ID, params=params)
    client.request(r)
    price = r.response["prices"][0]
    bid = float(price["bids"][0]["price"])
    ask = float(price["asks"][0]["price"])
    return (bid + ask) / 2


def calculate_units(signal: Signal, instrument: str, balance: float) -> int:
    """
    Pozisyon boyutu = risk_usd / (entry - sl)
    OANDA units cinsinden döndürür (negatif = short).
    """
    price_risk = abs(signal.entry - signal.sl)
    if price_risk <= 0:
        return 0

    units = RISK_PER_TRADE_USD / price_risk

    # Max: bakiyenin %10'u kadar pozisyon
    max_units = (balance * 0.10) / signal.entry
    units = min(units, max_units)
    units = max(int(units), 1)

    return units if signal.direction == "LONG" else -units


def execute_signal(signal: Signal) -> bool:
    """
    ICT sinyalini OANDA'da bracket order olarak açar.
    """
    instrument = SYMBOL_MAP.get(signal.symbol)
    if not instrument:
        print(f"[OANDA] {signal.symbol} desteklenmiyor.")
        return False

    if not OANDA_TOKEN or not OANDA_ACCOUNT_ID:
        print("[OANDA] Token/Account ID eksik.")
        return False

    try:
        client  = get_client()
        acc     = get_account_info()
        balance = acc["balance"]
        units   = calculate_units(signal, instrument, balance)

        if units == 0:
            print("[OANDA] Pozisyon boyutu sıfır.")
            return False

        # OANDA bracket order: Market entry + TP + SL
        order_body = {
            "order": {
                "type":        "MARKET",
                "instrument":  instrument,
                "units":       str(units),
                "timeInForce": "FOK",
                "takeProfitOnFill": {
                    "price": str(round(signal.tp1, 5)),
                    "timeInForce": "GTC",
                },
                "stopLossOnFill": {
                    "price": str(round(signal.sl, 5)),
                    "timeInForce": "GTC",
                },
            }
        }

        r = orders.OrderCreate(OANDA_ACCOUNT_ID, data=order_body)
        client.request(r)
        result = r.response

        trade_id = result.get("orderFillTransaction", {}).get("tradeOpened", {}).get("tradeID", "?")
        fill_px  = result.get("orderFillTransaction", {}).get("price", signal.entry)

        mode = "📄 DEMO" if OANDA_DEMO else "💰 GERÇEK"
        msg = f"""
{mode} — OANDA EMİR AÇILDI ✅

🎯 {instrument}
{'🟢 LONG' if signal.direction=='LONG' else '🔴 SHORT'} | {signal.model} ★{signal.confidence}

💰 Entry:   {fill_px}
🛑 SL:      {round(signal.sl, 5)}
🎯 TP1:     {round(signal.tp1, 5)}
📊 R:R      1:{signal.rr}
📦 Units:   {abs(units)}
💼 Bakiye:  ${balance:.2f}
🆔 Trade:   #{trade_id}
"""
        send_telegram(msg)
        print(f"[OANDA] ✅ Trade açıldı: #{trade_id} | {instrument} | {units} units")
        return True

    except Exception as e:
        err = str(e)
        print(f"[OANDA] ❌ Hata: {err}")
        send_telegram(f"⚠️ OANDA emir hatası ({signal.symbol}): {err[:200]}")
        return False


def close_all_trades():
    """Tüm açık trade'leri kapat (acil durum)."""
    try:
        client    = get_client()
        r_list    = trades.OpenTrades(OANDA_ACCOUNT_ID)
        client.request(r_list)
        open_trades = r_list.response.get("trades", [])

        for t in open_trades:
            tid = t["id"]
            r_close = trades.TradeClose(OANDA_ACCOUNT_ID, tradeID=tid)
            client.request(r_close)
            print(f"[OANDA] Trade #{tid} kapatıldı.")

        send_telegram(f"🚨 {len(open_trades)} trade kapatıldı.")
    except Exception as e:
        print(f"[OANDA] Kapatma hatası: {e}")


def get_open_trades() -> list:
    try:
        client  = get_client()
        r       = trades.OpenTrades(OANDA_ACCOUNT_ID)
        client.request(r)
        result  = []
        for t in r.response.get("trades", []):
            result.append({
                "id":            t["id"],
                "instrument":    t["instrument"],
                "units":         t["currentUnits"],
                "unrealized_pl": t["unrealizedPL"],
                "price":         t["price"],
            })
        return result
    except Exception as e:
        print(f"[OANDA] Pozisyon sorgu hatası: {e}")
        return []
