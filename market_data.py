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
        """Şu an hangi ICT Kill Zone'undayız? (ET bazlı, DST farkındalıklı)"""
        et = pytz.timezone("America/New_York")
        now_et = datetime.now(et)
        current_time = now_et.strftime("%H:%M")

        # ICT Kill Zone times in ET (Eastern Time, DST-aware):
        # Asian:    19:00-22:00 ET (7PM-10PM)
        # London:   02:00-05:00 ET (2AM-5AM)
        # New York: 07:00-10:00 ET (7AM-10AM) — NY AM session
        # NY Close: 14:00-16:00 ET (2PM-4PM)
        KILL_ZONES_ET = {
            "asia":      {"start": "19:00", "end": "22:00"},
            "london":    {"start": "02:00", "end": "05:00"},
            "new_york":  {"start": "07:00", "end": "10:00"},
            "ny_close":  {"start": "14:00", "end": "16:00"},
        }

        for zone_name, zone in KILL_ZONES_ET.items():
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
