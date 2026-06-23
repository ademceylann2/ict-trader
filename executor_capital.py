"""
ICT Trader — Capital.com Executor
Altın (GOLD), Nasdaq (US100), Forex otomatik trade.

Capital.com REST API v1 kullanır.
Demo: https://demo-api-capital.backend.gbcmanager.com
Live: https://api-capital.backend.gbcmanager.com
"""

import os
import requests
from ict_analyzer import Signal
from notifier import send_telegram

CAPITAL_API_KEY  = os.environ.get("CAPITAL_API_KEY", "")
CAPITAL_EMAIL    = os.environ.get("CAPITAL_EMAIL", "")
CAPITAL_PASSWORD = os.environ.get("CAPITAL_PASSWORD", "")
CAPITAL_DEMO     = os.environ.get("CAPITAL_DEMO", "true").lower() == "true"

BASE_URL = (
    "https://demo-api-capital.backend-capital.com"
    if CAPITAL_DEMO else
    "https://api-capital.backend-capital.com"
)

# ICT sembolü → Capital.com EPIC
SYMBOL_MAP = {
    "GC=F":     "GOLD",     # Altın
    "NQ=F":     "US100",    # Nasdaq 100
    "ES=F":     "US500",    # S&P 500
    "EURUSD=X": "EURUSD",
    "GBPUSD=X": "GBPUSD",
    "USDJPY=X": "USDJPY",
    "BTC-USD":  "BITCOIN",
    "ETH-USD":  "ETHEREUM",
}

RISK_PER_TRADE_USD = float(os.environ.get("RISK_PER_TRADE_USD", "5.0"))


def _session_headers() -> dict:
    """Capital.com oturumu aç, CST ve X-SECURITY-TOKEN döndür."""
    url = f"{BASE_URL}/api/v1/session"
    payload = {
        "identifier": CAPITAL_EMAIL,
        "password":   CAPITAL_PASSWORD,
        "encryptedPassword": False,
    }
    headers = {
        "X-CAP-API-KEY": CAPITAL_API_KEY,
        "Content-Type":  "application/json",
    }
    resp = requests.post(url, json=payload, headers=headers, timeout=10)
    resp.raise_for_status()
    return {
        "X-CAP-API-KEY":    CAPITAL_API_KEY,
        "CST":              resp.headers.get("CST", ""),
        "X-SECURITY-TOKEN": resp.headers.get("X-SECURITY-TOKEN", ""),
        "Content-Type":     "application/json",
    }


def get_account_info() -> dict:
    headers = _session_headers()
    resp = requests.get(f"{BASE_URL}/api/v1/accounts", headers=headers, timeout=10)
    resp.raise_for_status()
    accounts = resp.json().get("accounts", [])
    acc = accounts[0] if accounts else {}
    return {
        "balance":    acc.get("balance", {}).get("balance", 0),
        "available":  acc.get("balance", {}).get("available", 0),
        "currency":   acc.get("preferred", True),
        "account_id": acc.get("accountId", ""),
    }


def get_market_info(epic: str, headers: dict) -> dict:
    resp = requests.get(
        f"{BASE_URL}/api/v1/markets/{epic}",
        headers=headers, timeout=10
    )
    resp.raise_for_status()
    return resp.json()


def calculate_size(signal: Signal, balance: float, min_size: float = 0.1) -> float:
    """
    Pozisyon boyutu = risk_usd / (entry - sl)
    Capital.com 'size' cinsinden (lot/contract).
    """
    price_risk = abs(signal.entry - signal.sl)
    if price_risk <= 0:
        return min_size

    size = RISK_PER_TRADE_USD / price_risk

    # Max: bakiyenin %10'u
    max_size = (balance * 0.10) / signal.entry
    size = min(size, max_size)
    size = max(round(size, 2), min_size)
    return size


def execute_signal(signal: Signal) -> bool:
    epic = SYMBOL_MAP.get(signal.symbol)
    if not epic:
        print(f"[CAPITAL] {signal.symbol} desteklenmiyor.")
        return False

    if not CAPITAL_API_KEY or not CAPITAL_EMAIL or not CAPITAL_PASSWORD:
        print("[CAPITAL] API bilgileri eksik.")
        return False

    try:
        headers = _session_headers()
        acc     = get_account_info()
        balance = float(acc["balance"])
        size    = calculate_size(signal, balance)

        direction = "BUY" if signal.direction == "LONG" else "SELL"

        order_body = {
            "epic":      epic,
            "direction": direction,
            "size":      size,
            "guaranteedStop": False,
            "stopLevel":   round(signal.sl, 5),
            "profitLevel": round(signal.tp1, 5),
        }

        resp = requests.post(
            f"{BASE_URL}/api/v1/positions",
            json=order_body, headers=headers, timeout=15
        )
        resp.raise_for_status()
        result  = resp.json()
        deal_id = result.get("dealReference", "?")

        mode = "📄 DEMO" if CAPITAL_DEMO else "💰 GERÇEK"
        msg = f"""
{mode} — CAPITAL.COM EMİR AÇILDI ✅

🎯 {epic} ({signal.symbol})
{'🟢 LONG' if signal.direction=='LONG' else '🔴 SHORT'} | {signal.model} ★{signal.confidence}

💰 Entry:  {signal.entry}
🛑 SL:     {round(signal.sl, 5)}
🎯 TP1:    {round(signal.tp1, 5)}
📊 R:R     1:{signal.rr}
📦 Size:   {size}
💼 Bakiye: ${balance:.2f}
🆔 Deal:   {deal_id}
"""
        send_telegram(msg)
        print(f"[CAPITAL] ✅ Pozisyon açıldı: {deal_id} | {epic} | {direction} {size}")
        return True

    except requests.HTTPError as e:
        err = e.response.text[:300] if e.response else str(e)
        print(f"[CAPITAL] ❌ HTTP Hatası: {err}")
        send_telegram(f"⚠️ Capital.com hata ({signal.symbol}): {err[:200]}")
        return False
    except Exception as e:
        print(f"[CAPITAL] ❌ Hata: {e}")
        send_telegram(f"⚠️ Capital.com hata: {str(e)[:200]}")
        return False


def close_all_positions():
    """Tüm açık pozisyonları kapat."""
    try:
        headers   = _session_headers()
        resp      = requests.get(f"{BASE_URL}/api/v1/positions", headers=headers, timeout=10)
        positions = resp.json().get("positions", [])

        for p in positions:
            deal_id = p["position"]["dealId"]
            requests.delete(
                f"{BASE_URL}/api/v1/positions/{deal_id}",
                headers=headers, timeout=10
            )
            print(f"[CAPITAL] Pozisyon kapatıldı: {deal_id}")

        send_telegram(f"🚨 {len(positions)} pozisyon kapatıldı.")
    except Exception as e:
        print(f"[CAPITAL] Kapatma hatası: {e}")


def get_open_positions() -> list:
    try:
        headers = _session_headers()
        resp    = requests.get(f"{BASE_URL}/api/v1/positions", headers=headers, timeout=10)
        result  = []
        for p in resp.json().get("positions", []):
            pos = p["position"]
            mkt = p["market"]
            result.append({
                "deal_id":    pos["dealId"],
                "epic":       mkt["epic"],
                "direction":  pos["direction"],
                "size":       pos["size"],
                "open_price": pos["openLevel"],
                "pl":         pos.get("upl", 0),
            })
        return result
    except Exception as e:
        print(f"[CAPITAL] Pozisyon sorgu hatası: {e}")
        return []
