import requests
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
from ict_analyzer import Signal


def format_signal(signal: Signal) -> str:
    direction_emoji = "🟢 LONG" if signal.direction == "LONG" else "🔴 SHORT"
    bias_emoji = "📈" if signal.bias in ("BULLISH", "CHOCH_BULLISH") else "📉"

    confluences_text = "\n".join(f"  ✅ {c}" for c in signal.confluences)

    return f"""
╔══════════════════════════════╗
║    🎯 ICT SİNYAL - {signal.symbol}
╚══════════════════════════════╝

{direction_emoji} | {bias_emoji} Bias: {signal.bias}
⏰ Kill Zone: {signal.kill_zone.upper()}
📐 Setup: {signal.setup}

💰 Entry:  {signal.entry}
🛑 SL:     {signal.sl}
🎯 TP1:    {signal.tp1}
🎯 TP2:    {signal.tp2}
📊 R:R     1:{signal.rr}

📋 Confluence'lar:
{confluences_text}

🕐 {signal.timestamp.strftime('%Y-%m-%d %H:%M UTC')}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️  Bu bir eğitim amaçlı analizdir.
    Kendi risk yönetiminizi uygulayın.
"""


def send_telegram(message: str):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("[TELEGRAM] Token/Chat ID ayarlanmamış - konsola yazdırılıyor")
        print(message)
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
    }
    try:
        resp = requests.post(url, json=payload, timeout=10)
        if resp.status_code == 200:
            print("[TELEGRAM] Sinyal gönderildi ✓")
        else:
            print(f"[TELEGRAM] Hata: {resp.text}")
    except Exception as e:
        print(f"[TELEGRAM] Bağlantı hatası: {e}")


def send_signal(signal: Signal):
    msg = format_signal(signal)
    send_telegram(msg)


def send_news_alert(event: dict):
    msg = f"""
⚠️ YÜKSEK ETKİLİ HABER YAKLAŞIYOR ⚠️

💱 Para birimi: {event['currency']}
📰 Olay: {event['event']}
⏰ Saat: {event['time']} ET
🕐 {event.get('minutes_away', '?')} dakika kaldı

❌ Yeni pozisyon açmayın!
    Açık pozisyonları yönetin.
"""
    send_telegram(msg)


def send_startup_message(symbols: list):
    msg = f"""
🤖 ICT TRADER BAŞLADI

Takip edilen semboller:
{chr(10).join(f'  • {s}' for s in symbols)}

Kill Zone'lar (UTC):
  • Asia: 00:00 - 03:00
  • London: 07:00 - 10:00
  • New York: 12:00 - 15:00

✅ Sistem aktif - sinyal bekleniyor...
"""
    send_telegram(msg)
