import yfinance as yf
import pandas as pd
from datetime import datetime
import pytz


class MarketData:
    def __init__(self):
        self.utc = pytz.UTC

    def get_ohlcv(self, symbol: str, interval: str = "1h", period: str = "5d") -> pd.DataFrame:
        """yfinance üzerinden OHLCV verisi çek."""
        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(period=period, interval=interval)
            if df.empty:
                return pd.DataFrame()
            df.index = pd.to_datetime(df.index, utc=True)
            df = df[["Open", "High", "Low", "Close", "Volume"]]
            return df
        except Exception as e:
            print(f"[DATA] {symbol} verisi alınamadı: {e}")
            return pd.DataFrame()

    def get_current_kill_zone(self) -> str:
        """Şu an hangi ICT Kill Zone'undayız?"""
        from config import KILL_ZONES
        now_utc = datetime.utcnow()
        current_time = now_utc.strftime("%H:%M")

        for zone_name, zone in KILL_ZONES.items():
            if zone["start"] <= current_time <= zone["end"]:
                return zone_name

        return ""

    def get_session_highs_lows(self, symbol: str) -> dict:
        """Önceki session'ların high/low değerlerini döndür."""
        df_1h = self.get_ohlcv(symbol, interval="1h", period="5d")
        if df_1h.empty:
            return {}

        df_1h = df_1h.copy()
        df_1h["date"] = df_1h.index.date
        df_1h["hour"] = df_1h.index.hour

        # Asia session (00-08 UTC)
        asia = df_1h[df_1h["hour"].between(0, 7)]
        # London session (07-13 UTC)
        london = df_1h[df_1h["hour"].between(7, 12)]
        # New York session (12-21 UTC)
        ny = df_1h[df_1h["hour"].between(12, 20)]

        result = {}
        for session_name, session_df in [("asia", asia), ("london", london), ("ny", ny)]:
            if not session_df.empty:
                result[f"{session_name}_high"] = session_df["High"].iloc[-1:].max()
                result[f"{session_name}_low"]  = session_df["Low"].iloc[-1:].min()

        return result
