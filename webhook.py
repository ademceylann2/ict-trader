"""
TradingView Webhook Alıcısı
TradingView Alert → POST /webhook → Capital.com emir

Güvenlik: ?token=WEBHOOK_TOKEN query parametresi zorunlu.
"""

import os
import threading
from datetime import datetime
from flask import Flask, request, jsonify

from ict_analyzer import Signal
from executor_capital import execute_signal as capital_execute, CAPITAL_API_KEY
from notifier import send_telegram

app = Flask(__name__)

WEBHOOK_TOKEN = os.environ.get("WEBHOOK_TOKEN", "ict-secret-2026")

# Son gelen sinyallerin kaydı (aynı sinyalin çift işleme alınmaması için)
_recent: dict = {}
_recent_lock = threading.Lock()


def _already_processed(key: str, ttl_sec: int = 3600) -> bool:
    import time
    now = time.time()
    with _recent_lock:
        if key in _recent and (now - _recent[key]) < ttl_sec:
            return True
        _recent[key] = now
        # Eski kayıtları temizle
        expired = [k for k, t in _recent.items() if now - t > ttl_sec]
        for k in expired:
            del _recent[k]
    return False


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "time": datetime.utcnow().isoformat()})


@app.route("/status", methods=["GET"])
def status():
    """Capital.com bakiye ve açık pozisyon özeti."""
    if not CAPITAL_API_KEY:
        return jsonify({"error": "Capital.com API bağlı değil"}), 503
    try:
        from executor_capital import get_account_info, get_open_positions
        acc = get_account_info()
        pos = get_open_positions()
        return jsonify({
            "balance":    acc.get("balance"),
            "available":  acc.get("available"),
            "positions":  len(pos),
            "pos_detail": pos,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/webhook", methods=["POST"])
def webhook():
    """
    TradingView alert JSON alır, Capital.com'da emir açar.

    Beklenen JSON formatı (TradingView alert message):
    {
        "token":    "ict-secret-2026",
        "symbol":   "GOLD",          ← Capital.com epic
        "action":   "buy",           ← buy / sell
        "price":    4099.0,          ← giriş fiyatı
        "sl":       4069.0,          ← stop loss fiyatı
        "tp":       4189.0,          ← take profit fiyatı
        "strategy": "IB_BREAKOUT",   ← strateji adı (log için)
        "stars":    4                ← güven seviyesi (opsiyonel)
    }
    """
    # Token kontrolü — URL veya body'den al
    token = request.args.get("token") or (request.json or {}).get("token", "")
    if token != WEBHOOK_TOKEN:
        return jsonify({"error": "Geçersiz token"}), 403

    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "JSON gövdesi gerekli"}), 400

    symbol   = data.get("symbol", "GOLD").upper()
    action   = data.get("action", "").lower()
    price    = float(data.get("price", 0))
    sl       = float(data.get("sl", 0))
    tp       = float(data.get("tp", 0))
    strategy = data.get("strategy", "TV_ALERT")
    stars    = int(data.get("stars", 4))

    if action not in ("buy", "sell"):
        return jsonify({"error": f"Geçersiz action: {action}"}), 400
    if price <= 0 or sl <= 0 or tp <= 0:
        return jsonify({"error": "price/sl/tp sıfır olamaz"}), 400

    # Duplicate kontrolü
    direction = "LONG" if action == "buy" else "SHORT"
    sig_key   = f"{symbol}_{direction}_{strategy}"
    if _already_processed(sig_key, ttl_sec=3600):
        return jsonify({"status": "duplicate", "message": "Aynı sinyal 1 saat içinde tekrar gönderildi, atlandı"}), 200

    # Signal nesnesi oluştur
    risk   = abs(price - sl)
    reward = abs(tp - price)
    rr     = round(reward / risk, 2) if risk > 0 else 0

    # yfinance sembol → Capital epic mapping
    EPIC_MAP = {
        "GOLD": "GOLD", "XAUUSD": "GOLD",
        "US100": "US100", "NAS100": "US100", "NQ": "US100",
        "US500": "US500", "SPX": "US500",
        "EURUSD": "EURUSD", "GBPUSD": "GBPUSD", "USDJPY": "USDJPY",
        "BITCOIN": "BITCOIN", "BTC": "BITCOIN",
    }
    epic = EPIC_MAP.get(symbol, symbol)

    signal = Signal(
        symbol    = epic,
        direction = direction,
        entry     = price,
        sl        = sl,
        tp1       = tp,
        tp2       = tp,
        rr        = rr,
        setup     = strategy,
        timeframe = "TV",
        kill_zone = "webhook",
        bias      = "BULLISH" if direction == "LONG" else "BEARISH",
        confluences = [f"TradingView: {strategy}", f"TV Alert @ {price}"],
        timestamp = datetime.utcnow(),
        model     = strategy,
        confidence= stars,
    )

    print(f"[WEBHOOK] {symbol} {direction} @ {price} | SL={sl} TP={tp} | {strategy} ★{stars}")
    send_telegram(
        f"📡 TradingView Sinyali\n"
        f"{'🟢 LONG' if direction=='LONG' else '🔴 SHORT'} {epic} @ {price}\n"
        f"SL: {sl} | TP: {tp} | R:R 1:{rr}\n"
        f"Strateji: {strategy} ★{stars}"
    )

    if CAPITAL_API_KEY:
        ok = capital_execute(signal)
        return jsonify({"status": "executed" if ok else "failed", "symbol": epic, "direction": direction})

    return jsonify({"status": "no_broker", "message": "Capital.com API key eksik"})


def run_webhook(port: int = 5000):
    """Flask'ı ayrı thread'de başlat."""
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)
