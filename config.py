# ICT Trader Configuration
import os

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "8719621427:AAEDOSIvqxGGsr4zYgLXnEgLKSC0J-BYl10")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "7634663263")

# Takip edilecek semboller
SYMBOLS = {
    "forex": ["EURUSD=X", "GBPUSD=X", "USDJPY=X", "GC=F"],  # GC=F = Altın futures
    "crypto": ["BTC-USD", "ETH-USD"],
    "indices": ["ES=F", "NQ=F"],  # S&P500 ve Nasdaq futures
}

# ICT Kill Zones (UTC saat)
KILL_ZONES = {
    "asia":       {"start": "00:00", "end": "03:00"},
    "london":     {"start": "07:00", "end": "10:00"},
    "new_york":   {"start": "12:00", "end": "15:00"},
    "ny_close":   {"start": "19:00", "end": "20:00"},
}

# Timeframe'ler (yfinance formatı)
TIMEFRAMES = {
    "htf": "1h",   # Higher time frame - yapı analizi
    "mtf": "15m",  # Mid time frame - entry bölgeleri
    "ltf": "5m",   # Low time frame - kesin giriş
}

# Sinyal eşikleri
MIN_FVG_SIZE_PIPS = 5     # Minimum FVG büyüklüğü
MIN_OB_CANDLES = 3        # OB onayı için minimum ilerleyen mum sayısı
HIGH_IMPACT_NEWS_ONLY = True  # Sadece yüksek etkili haberlere bak
