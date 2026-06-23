import pandas as pd
import numpy as np
from dataclasses import dataclass
from typing import Optional
from datetime import datetime


@dataclass
class Signal:
    symbol: str
    direction: str        # "LONG" | "SHORT"
    entry: float
    sl: float
    tp1: float
    tp2: float
    rr: float
    setup: str            # Hangi ICT kurulumu
    timeframe: str
    kill_zone: str
    bias: str             # "BULLISH" | "BEARISH"
    confluences: list
    timestamp: datetime


class ICTAnalyzer:
    def __init__(self, symbol: str):
        self.symbol = symbol

    # ─── Market Structure ───────────────────────────────────────────────────
    def detect_market_structure(self, df: pd.DataFrame) -> str:
        """BOS ve CHOCH tespiti ile genel bias belirle."""
        highs = df["High"].values
        lows = df["Low"].values
        n = len(df)

        swing_highs, swing_lows = [], []
        for i in range(2, n - 2):
            if highs[i] > highs[i-1] and highs[i] > highs[i-2] and highs[i] > highs[i+1] and highs[i] > highs[i+2]:
                swing_highs.append((i, highs[i]))
            if lows[i] < lows[i-1] and lows[i] < lows[i-2] and lows[i] < lows[i+1] and lows[i] < lows[i+2]:
                swing_lows.append((i, lows[i]))

        if len(swing_highs) < 2 or len(swing_lows) < 2:
            return "NEUTRAL"

        last_hh = swing_highs[-1][1] > swing_highs[-2][1]
        last_hl = swing_lows[-1][1] > swing_lows[-2][1]
        last_lh = swing_highs[-1][1] < swing_highs[-2][1]
        last_ll = swing_lows[-1][1] < swing_lows[-2][1]

        if last_hh and last_hl:
            return "BULLISH"
        elif last_lh and last_ll:
            return "BEARISH"
        elif last_lh and last_hl:
            return "CHOCH_BULLISH"   # Change of Character - potansiyel dönüş
        elif last_hh and last_ll:
            return "CHOCH_BEARISH"
        return "NEUTRAL"

    # ─── Fair Value Gap ─────────────────────────────────────────────────────
    def find_fvg(self, df: pd.DataFrame) -> list:
        """Bullish ve Bearish FVG bul (3 mumlu imbalance)."""
        fvgs = []
        for i in range(1, len(df) - 1):
            c1_high = df["High"].iloc[i-1]
            c1_low  = df["Low"].iloc[i-1]
            c3_high = df["High"].iloc[i+1]
            c3_low  = df["Low"].iloc[i+1]

            # Bullish FVG: C1 high < C3 low
            if c1_high < c3_low:
                fvgs.append({
                    "type": "BULLISH_FVG",
                    "top": c3_low,
                    "bottom": c1_high,
                    "midpoint": (c3_low + c1_high) / 2,
                    "index": i,
                    "time": df.index[i],
                })

            # Bearish FVG: C1 low > C3 high
            if c1_low > c3_high:
                fvgs.append({
                    "type": "BEARISH_FVG",
                    "top": c1_low,
                    "bottom": c3_high,
                    "midpoint": (c1_low + c3_high) / 2,
                    "index": i,
                    "time": df.index[i],
                })

        return fvgs

    # ─── Order Blocks ────────────────────────────────────────────────────────
    def find_order_blocks(self, df: pd.DataFrame) -> list:
        """Bullish ve Bearish OB tespit et (hareketten önceki zıt mum)."""
        obs = []
        for i in range(1, len(df) - 3):
            # Güçlü yukarı hareket var mı? (sonraki 3 mumda yüksek momentum)
            up_move = all(df["Close"].iloc[i+j] > df["Close"].iloc[i+j-1] for j in range(1, 4))
            down_move = all(df["Close"].iloc[i+j] < df["Close"].iloc[i+j-1] for j in range(1, 4))

            # Bullish OB: güçlü yukarı hareketten önceki bearish mum
            if up_move and df["Close"].iloc[i] < df["Open"].iloc[i]:
                obs.append({
                    "type": "BULLISH_OB",
                    "top": df["High"].iloc[i],
                    "bottom": df["Low"].iloc[i],
                    "50pct": (df["High"].iloc[i] + df["Low"].iloc[i]) / 2,
                    "index": i,
                    "time": df.index[i],
                })

            # Bearish OB: güçlü aşağı hareketten önceki bullish mum
            if down_move and df["Close"].iloc[i] > df["Open"].iloc[i]:
                obs.append({
                    "type": "BEARISH_OB",
                    "top": df["High"].iloc[i],
                    "bottom": df["Low"].iloc[i],
                    "50pct": (df["High"].iloc[i] + df["Low"].iloc[i]) / 2,
                    "index": i,
                    "time": df.index[i],
                })

        return obs

    # ─── Liquidity Levels ───────────────────────────────────────────────────
    def find_liquidity(self, df: pd.DataFrame, lookback: int = 20) -> dict:
        """Önceki session high/low ve equal high/low liquidity bul."""
        recent = df.tail(lookback)
        liquidity = {
            "buy_side":  [],   # Equal highs / prev session highs (hedef: yukarı)
            "sell_side": [],   # Equal lows / prev session lows (hedef: aşağı)
        }

        # Swing high/low liquidity
        for i in range(2, len(recent) - 2):
            h = recent["High"].iloc[i]
            l = recent["Low"].iloc[i]
            # Swing high = buy-side liquidity
            if h > recent["High"].iloc[i-1] and h > recent["High"].iloc[i-2] and \
               h > recent["High"].iloc[i+1] and h > recent["High"].iloc[i+2]:
                liquidity["buy_side"].append({"price": h, "time": recent.index[i]})
            # Swing low = sell-side liquidity
            if l < recent["Low"].iloc[i-1] and l < recent["Low"].iloc[i-2] and \
               l < recent["Low"].iloc[i+1] and l < recent["Low"].iloc[i+2]:
                liquidity["sell_side"].append({"price": l, "time": recent.index[i]})

        return liquidity

    # ─── Premium / Discount ─────────────────────────────────────────────────
    def get_premium_discount(self, df: pd.DataFrame, lookback: int = 50) -> dict:
        """Son swing'in %50 seviyesi: üstü premium, altı discount."""
        recent = df.tail(lookback)
        swing_high = recent["High"].max()
        swing_low  = recent["Low"].min()
        eq = (swing_high + swing_low) / 2
        current = df["Close"].iloc[-1]

        return {
            "swing_high": swing_high,
            "swing_low": swing_low,
            "equilibrium": eq,
            "zone": "PREMIUM" if current > eq else "DISCOUNT",
            "current": current,
        }

    # ─── Ana Sinyal Üretici ──────────────────────────────────────────────────
    def generate_signal(self, df_htf: pd.DataFrame, df_mtf: pd.DataFrame,
                        kill_zone: str, news_clear: bool) -> Optional[Signal]:
        """
        ICT Power of 3 mantığıyla sinyal üret:
        1. HTF bias al
        2. MTF'de OB veya FVG bul
        3. Kill zone + haber onayı
        """
        bias = self.detect_market_structure(df_htf)
        pd_zone = self.get_premium_discount(df_htf)
        fvgs = self.find_fvg(df_mtf)
        obs  = self.find_order_blocks(df_mtf)
        liq  = self.find_liquidity(df_htf)
        current_price = df_mtf["Close"].iloc[-1]

        confluences = []

        # Kill zone aktif mi?
        if not kill_zone:
            return None
        confluences.append(f"Kill Zone: {kill_zone}")

        # Haber riski var mı?
        if not news_clear:
            return None
        confluences.append("Haber riski yok")

        # ─── LONG kurulumu ───
        if bias in ("BULLISH", "CHOCH_BULLISH") and pd_zone["zone"] == "DISCOUNT":
            confluences.append(f"HTF Bias: {bias} + Discount bölge")

            # MTF'de yakın bullish OB veya FVG ara
            entry_zone = None
            setup_name = ""

            for fvg in reversed(fvgs):
                if fvg["type"] == "BULLISH_FVG" and fvg["bottom"] <= current_price <= fvg["top"]:
                    entry_zone = fvg
                    setup_name = "FVG Entry (Bullish)"
                    confluences.append("Bullish FVG üzerinde fiyat")
                    break

            if not entry_zone:
                for ob in reversed(obs):
                    if ob["type"] == "BULLISH_OB" and ob["bottom"] <= current_price <= ob["top"]:
                        entry_zone = ob
                        setup_name = "Order Block Entry (Bullish)"
                        confluences.append("Bullish OB içinde fiyat")
                        break

            if entry_zone:
                # Sell-side liquidity var mı (SL için)?
                sl_candidates = [l["price"] for l in liq["sell_side"] if l["price"] < current_price]
                sl = min(sl_candidates) if sl_candidates else entry_zone["bottom"] * 0.999

                # Buy-side liquidity hedef
                tp_candidates = [l["price"] for l in liq["buy_side"] if l["price"] > current_price]
                tp1 = tp_candidates[0] if tp_candidates else current_price * 1.005
                tp2 = tp_candidates[1] if len(tp_candidates) > 1 else current_price * 1.010

                risk = current_price - sl
                reward = tp1 - current_price
                rr = round(reward / risk, 2) if risk > 0 else 0

                if rr >= 2.0:
                    return Signal(
                        symbol=self.symbol, direction="LONG",
                        entry=round(current_price, 5), sl=round(sl, 5),
                        tp1=round(tp1, 5), tp2=round(tp2, 5),
                        rr=rr, setup=setup_name, timeframe="MTF",
                        kill_zone=kill_zone, bias=bias,
                        confluences=confluences, timestamp=datetime.utcnow(),
                    )

        # ─── SHORT kurulumu ───
        if bias in ("BEARISH", "CHOCH_BEARISH") and pd_zone["zone"] == "PREMIUM":
            confluences.append(f"HTF Bias: {bias} + Premium bölge")

            entry_zone = None
            setup_name = ""

            for fvg in reversed(fvgs):
                if fvg["type"] == "BEARISH_FVG" and fvg["bottom"] <= current_price <= fvg["top"]:
                    entry_zone = fvg
                    setup_name = "FVG Entry (Bearish)"
                    confluences.append("Bearish FVG içinde fiyat")
                    break

            if not entry_zone:
                for ob in reversed(obs):
                    if ob["type"] == "BEARISH_OB" and ob["bottom"] <= current_price <= ob["top"]:
                        entry_zone = ob
                        setup_name = "Order Block Entry (Bearish)"
                        confluences.append("Bearish OB içinde fiyat")
                        break

            if entry_zone:
                sl_candidates = [l["price"] for l in liq["buy_side"] if l["price"] > current_price]
                sl = max(sl_candidates) if sl_candidates else entry_zone["top"] * 1.001

                tp_candidates = [l["price"] for l in liq["sell_side"] if l["price"] < current_price]
                tp1 = tp_candidates[-1] if tp_candidates else current_price * 0.995
                tp2 = tp_candidates[-2] if len(tp_candidates) > 1 else current_price * 0.990

                risk = sl - current_price
                reward = current_price - tp1
                rr = round(reward / risk, 2) if risk > 0 else 0

                if rr >= 2.0:
                    return Signal(
                        symbol=self.symbol, direction="SHORT",
                        entry=round(current_price, 5), sl=round(sl, 5),
                        tp1=round(tp1, 5), tp2=round(tp2, 5),
                        rr=rr, setup=setup_name, timeframe="MTF",
                        kill_zone=kill_zone, bias=bias,
                        confluences=confluences, timestamp=datetime.utcnow(),
                    )

        return None
