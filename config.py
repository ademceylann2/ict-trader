# ICT Trader Configuration
import os

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "8719621427:AAEDOSIvqxGGsr4zYgLXnEgLKSC0J-BYl10")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "7634663263")

# Takip edilecek semboller
SYMBOLS = {
    "forex": ["EURUSD=X", "GBPUSD=X", "USDJPY=X", "GC=F"],  # GC=F = Altın futures
    "crypto": ["ETH-USD"],
    "indices": ["ES=F", "NQ=F"],  # S&P500 ve Nasdaq futures
}

# ICT Kill Zones — DO NOT USE: market_data.py handles these in ET (DST-aware)
# Asia:     19:00-22:00 ET | London:  02:00-05:00 ET
# New York: 07:00-10:00 ET | NY Close: 14:00-16:00 ET

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
