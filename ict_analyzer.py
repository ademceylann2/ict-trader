import pandas as pd
import numpy as np
from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime
import pytz


@dataclass
class Signal:
    symbol: str
    direction: str        # "LONG" | "SHORT"
    entry: float
    sl: float
    tp1: float
    tp2: float
    rr: float
    setup: str
    timeframe: str
    kill_zone: str
    bias: str
    confluences: list
    timestamp: datetime
    model: str = ""       # "UNICORN" | "SILVER_BULLET" | "OTE" | "OB_FVG"


class ICTAnalyzer:
    def __init__(self, symbol: str):
        self.symbol = symbol
        self._et = pytz.timezone("America/New_York")

    # ─── Market Structure ────────────────────────────────────────────────────
    def detect_market_structure(self, df: pd.DataFrame) -> str:
        """BOS ve CHOCH tespiti — HH/HL veya LL/LH dizisi."""
        highs = df["High"].values
        lows  = df["Low"].values
        n     = len(df)

        swing_highs, swing_lows = [], []
        for i in range(2, n - 2):
            if highs[i] > highs[i-1] and highs[i] > highs[i-2] and \
               highs[i] > highs[i+1] and highs[i] > highs[i+2]:
                swing_highs.append((i, highs[i]))
            if lows[i] < lows[i-1] and lows[i] < lows[i-2] and \
               lows[i] < lows[i+1] and lows[i] < lows[i+2]:
                swing_lows.append((i, lows[i]))

        if len(swing_highs) < 2 or len(swing_lows) < 2:
            return "NEUTRAL"

        last_hh = swing_highs[-1][1] > swing_highs[-2][1]
        last_hl = swing_lows[-1][1]  > swing_lows[-2][1]
        last_lh = swing_highs[-1][1] < swing_highs[-2][1]
        last_ll = swing_lows[-1][1]  < swing_lows[-2][1]

        if last_hh and last_hl:
            return "BULLISH"
        elif last_lh and last_ll:
            return "BEARISH"
        elif last_lh and last_hl:
            return "CHOCH_BULLISH"
        elif last_hh and last_ll:
            return "CHOCH_BEARISH"
        return "NEUTRAL"

    def _get_swing_points(self, df: pd.DataFrame):
        """Swing high/low listesi döndür."""
        highs = df["High"].values
        lows  = df["Low"].values
        n     = len(df)
        sh, sl = [], []
        for i in range(2, n - 2):
            if highs[i] > highs[i-1] and highs[i] > highs[i-2] and \
               highs[i] > highs[i+1] and highs[i] > highs[i+2]:
                sh.append((i, highs[i]))
            if lows[i] < lows[i-1] and lows[i] < lows[i-2] and \
               lows[i] < lows[i+1] and lows[i] < lows[i+2]:
                sl.append((i, lows[i]))
        return sh, sl

    # ─── Fair Value Gap ──────────────────────────────────────────────────────
    def find_fvg(self, df: pd.DataFrame) -> list:
        """Bullish/Bearish FVG (3-mum imbalance). Sadece henüz dolmamışlar."""
        fvgs = []
        current_price = df["Close"].iloc[-1]

        for i in range(1, len(df) - 1):
            c1_high = df["High"].iloc[i - 1]
            c1_low  = df["Low"].iloc[i - 1]
            c3_high = df["High"].iloc[i + 1]
            c3_low  = df["Low"].iloc[i + 1]

            if c1_high < c3_low:
                top    = c3_low
                bottom = c1_high
                # Doldurulmamış FVG: fiyat hâlâ bölgenin altında
                if current_price < top:
                    fvgs.append({
                        "type": "BULLISH_FVG",
                        "top": top, "bottom": bottom,
                        "midpoint": (top + bottom) / 2,
                        "size": top - bottom,
                        "index": i, "time": df.index[i],
                    })

            if c1_low > c3_high:
                top    = c1_low
                bottom = c3_high
                if current_price > bottom:
                    fvgs.append({
                        "type": "BEARISH_FVG",
                        "top": top, "bottom": bottom,
                        "midpoint": (top + bottom) / 2,
                        "size": top - bottom,
                        "index": i, "time": df.index[i],
                    })

        return fvgs

    # ─── Order Blocks ────────────────────────────────────────────────────────
    def find_order_blocks(self, df: pd.DataFrame) -> list:
        """Güçlü hareketten önceki zıt mum = Order Block."""
        obs = []
        for i in range(1, len(df) - 3):
            up_move   = all(df["Close"].iloc[i+j] > df["Close"].iloc[i+j-1] for j in range(1, 4))
            down_move = all(df["Close"].iloc[i+j] < df["Close"].iloc[i+j-1] for j in range(1, 4))

            if up_move and df["Close"].iloc[i] < df["Open"].iloc[i]:
                obs.append({
                    "type": "BULLISH_OB",
                    "top": df["High"].iloc[i],
                    "bottom": df["Low"].iloc[i],
                    "50pct": (df["High"].iloc[i] + df["Low"].iloc[i]) / 2,
                    "broken": False,
                    "index": i, "time": df.index[i],
                })

            if down_move and df["Close"].iloc[i] > df["Open"].iloc[i]:
                obs.append({
                    "type": "BEARISH_OB",
                    "top": df["High"].iloc[i],
                    "bottom": df["Low"].iloc[i],
                    "50pct": (df["High"].iloc[i] + df["Low"].iloc[i]) / 2,
                    "broken": False,
                    "index": i, "time": df.index[i],
                })

        return obs

    # ─── Breaker Blocks ──────────────────────────────────────────────────────
    def find_breaker_blocks(self, df: pd.DataFrame) -> list:
        """
        Kırılan OB → Breaker Block (tersine döner).
        Bullish OB kırılırsa → Bearish Breaker.
        Bearish OB kırılırsa → Bullish Breaker.
        """
        obs      = self.find_order_blocks(df)
        breakers = []
        closes   = df["Close"].values

        for ob in obs:
            ob_idx = ob["index"]
            for j in range(ob_idx + 1, len(df)):
                if ob["type"] == "BULLISH_OB" and closes[j] < ob["bottom"]:
                    # Bullish OB kırıldı → Bearish Breaker
                    breakers.append({
                        "type": "BEARISH_BREAKER",
                        "top": ob["top"],
                        "bottom": ob["bottom"],
                        "midpoint": ob["50pct"],
                        "broken_at": j,
                        "index": ob_idx,
                        "time": ob["time"],
                    })
                    break
                if ob["type"] == "BEARISH_OB" and closes[j] > ob["top"]:
                    # Bearish OB kırıldı → Bullish Breaker
                    breakers.append({
                        "type": "BULLISH_BREAKER",
                        "top": ob["top"],
                        "bottom": ob["bottom"],
                        "midpoint": ob["50pct"],
                        "broken_at": j,
                        "index": ob_idx,
                        "time": ob["time"],
                    })
                    break

        return breakers

    # ─── Unicorn Model ───────────────────────────────────────────────────────
    def find_unicorn(self, df: pd.DataFrame) -> list:
        """
        ICT Unicorn: FVG + Breaker Block çakışması = en yüksek confluece kurulumu.
        """
        breakers = self.find_breaker_blocks(df)
        fvgs     = self.find_fvg(df)
        unicorns = []

        for b in breakers:
            for f in fvgs:
                # Aynı yön mü?
                if b["type"] == "BULLISH_BREAKER" and f["type"] == "BULLISH_FVG":
                    # Çakışıyor mu?
                    overlap_top    = min(b["top"], f["top"])
                    overlap_bottom = max(b["bottom"], f["bottom"])
                    if overlap_top > overlap_bottom:
                        unicorns.append({
                            "direction": "BULLISH",
                            "top": overlap_top,
                            "bottom": overlap_bottom,
                            "breaker": b, "fvg": f,
                        })
                elif b["type"] == "BEARISH_BREAKER" and f["type"] == "BEARISH_FVG":
                    overlap_top    = min(b["top"], f["top"])
                    overlap_bottom = max(b["bottom"], f["bottom"])
                    if overlap_top > overlap_bottom:
                        unicorns.append({
                            "direction": "BEARISH",
                            "top": overlap_top,
                            "bottom": overlap_bottom,
                            "breaker": b, "fvg": f,
                        })

        return unicorns

    # ─── OTE — Optimal Trade Entry ───────────────────────────────────────────
    def find_ote(self, df: pd.DataFrame, bias: str) -> Optional[dict]:
        """
        BOS/CHOCH sonrası impulse hareketin %62-%79 Fibonacci geri çekilmesi = OTE bölgesi.
        """
        sh, sl = self._get_swing_points(df)
        if not sh or not sl:
            return None

        if bias in ("BULLISH", "CHOCH_BULLISH"):
            # Son LL'den son HH'ye impulse → geri çekilme = OTE
            if not sl or not sh:
                return None
            swing_low  = sl[-1][1]
            swing_high = sh[-1][1]
            if swing_high <= swing_low:
                return None
            ote_top    = swing_low + 0.79 * (swing_high - swing_low)
            ote_bottom = swing_low + 0.62 * (swing_high - swing_low)
            return {
                "direction": "BULLISH", "top": ote_top, "bottom": ote_bottom,
                "swing_low": swing_low, "swing_high": swing_high,
                "fib_62": ote_bottom, "fib_79": ote_top,
            }

        elif bias in ("BEARISH", "CHOCH_BEARISH"):
            swing_high = sh[-1][1]
            swing_low  = sl[-1][1]
            if swing_low >= swing_high:
                return None
            ote_bottom = swing_high - 0.79 * (swing_high - swing_low)
            ote_top    = swing_high - 0.62 * (swing_high - swing_low)
            return {
                "direction": "BEARISH", "top": ote_top, "bottom": ote_bottom,
                "swing_high": swing_high, "swing_low": swing_low,
                "fib_62": ote_top, "fib_79": ote_bottom,
            }

        return None

    # ─── IPDA Seviyeleri (20/40/60 gün) ─────────────────────────────────────
    def ipda_levels(self, df_daily: pd.DataFrame) -> dict:
        """
        IPDA: 20/40/60 günlük high/low kurumsal referans noktaları.
        df_daily günlük veri olmalı (period="90d", interval="1d").
        """
        levels = {}
        for days in [20, 40, 60]:
            if len(df_daily) >= days:
                recent = df_daily.tail(days)
                levels[f"high_{days}d"] = recent["High"].max()
                levels[f"low_{days}d"]  = recent["Low"].min()
        return levels

    # ─── Silver Bullet Penceresi ─────────────────────────────────────────────
    def is_silver_bullet_window(self) -> str:
        """
        ICT Silver Bullet zaman pencereleri (New York saati):
        03:00-04:00 | 10:00-11:00 | 14:00-15:00
        """
        now_et = datetime.now(self._et)
        h = now_et.hour
        if 3 <= h < 4:
            return "silver_bullet_3am"
        if 10 <= h < 11:
            return "silver_bullet_10am"
        if 14 <= h < 15:
            return "silver_bullet_2pm"
        return ""

    # ─── Judas Swing ─────────────────────────────────────────────────────────
    def detect_judas_swing(self, df: pd.DataFrame, bias: str) -> bool:
        """
        Judas Swing: session açılışında bias'ın tersine sahte hareket, sonra gerçek yön.
        Son 3 mumda: bias BULLISH ise önce aşağı, sonra sert yukarı.
        """
        if len(df) < 4:
            return False
        last = df.tail(4)
        if bias in ("BULLISH", "CHOCH_BULLISH"):
            # İlk iki mum aşağı, son mum sert yukarı
            down = last["Close"].iloc[1] < last["Close"].iloc[0] and \
                   last["Close"].iloc[2] < last["Close"].iloc[1]
            up   = last["Close"].iloc[3] > last["Close"].iloc[2] * 1.001
            return down and up
        elif bias in ("BEARISH", "CHOCH_BEARISH"):
            up   = last["Close"].iloc[1] > last["Close"].iloc[0] and \
                   last["Close"].iloc[2] > last["Close"].iloc[1]
            down = last["Close"].iloc[3] < last["Close"].iloc[2] * 0.999
            return up and down
        return False

    # ─── Liquidity ───────────────────────────────────────────────────────────
    def find_liquidity(self, df: pd.DataFrame, lookback: int = 20) -> dict:
        """Swing high/low liquidity pool'larını tespit et."""
        recent = df.tail(lookback)
        liquidity = {"buy_side": [], "sell_side": []}

        for i in range(2, len(recent) - 2):
            h = recent["High"].iloc[i]
            l = recent["Low"].iloc[i]
            if h > recent["High"].iloc[i-1] and h > recent["High"].iloc[i-2] and \
               h > recent["High"].iloc[i+1] and h > recent["High"].iloc[i+2]:
                liquidity["buy_side"].append({"price": h, "time": recent.index[i]})
            if l < recent["Low"].iloc[i-1] and l < recent["Low"].iloc[i-2] and \
               l < recent["Low"].iloc[i+1] and l < recent["Low"].iloc[i+2]:
                liquidity["sell_side"].append({"price": l, "time": recent.index[i]})

        return liquidity

    # ─── Premium / Discount ──────────────────────────────────────────────────
    def get_premium_discount(self, df: pd.DataFrame, lookback: int = 50) -> dict:
        """Son swing'in %50 seviyesi: üstü premium, altı discount."""
        recent     = df.tail(lookback)
        swing_high = recent["High"].max()
        swing_low  = recent["Low"].min()
        eq         = (swing_high + swing_low) / 2
        current    = df["Close"].iloc[-1]
        return {
            "swing_high": swing_high, "swing_low": swing_low,
            "equilibrium": eq, "current": current,
            "zone": "PREMIUM" if current > eq else "DISCOUNT",
        }

    # ─── Ana Sinyal Üretici ──────────────────────────────────────────────────
    def generate_signal(self, df_htf: pd.DataFrame, df_mtf: pd.DataFrame,
                        kill_zone: str, news_clear: bool,
                        df_daily: pd.DataFrame = None) -> Optional[Signal]:
        """
        Geliştirilmiş ICT sinyal motoru:
        Priority: Unicorn > Silver Bullet > OTE > OB/FVG
        """
        if not kill_zone:
            return None
        if not news_clear:
            return None

        bias          = self.detect_market_structure(df_htf)
        pd_zone       = self.get_premium_discount(df_htf)
        fvgs          = self.find_fvg(df_mtf)
        obs           = self.find_order_blocks(df_mtf)
        breakers      = self.find_breaker_blocks(df_mtf)
        unicorns      = self.find_unicorn(df_mtf)
        ote           = self.find_ote(df_htf, bias)
        liq           = self.find_liquidity(df_htf)
        current_price = df_mtf["Close"].iloc[-1]
        sb_window     = self.is_silver_bullet_window()
        judas         = self.detect_judas_swing(df_mtf, bias)

        # IPDA seviyeleri (varsa)
        ipda = {}
        if df_daily is not None and not df_daily.empty:
            ipda = self.ipda_levels(df_daily)

        base_confluences = [f"Kill Zone: {kill_zone}", "Haber riski yok"]
        if sb_window:
            base_confluences.append(f"Silver Bullet penceresi: {sb_window}")
        if judas:
            base_confluences.append("Judas Swing tespit edildi")

        # IPDA confluence
        if ipda:
            for label, val in ipda.items():
                diff = abs(current_price - val) / current_price
                if diff < 0.002:  # %0.2 yakınlık
                    base_confluences.append(f"IPDA seviyesi yakın: {label} @ {round(val, 4)}")

        # ── LONG kurulumu ──────────────────────────────────────────────────
        if bias in ("BULLISH", "CHOCH_BULLISH") and pd_zone["zone"] == "DISCOUNT":
            confluences = base_confluences.copy()
            confluences.append(f"HTF Bias: {bias} | Discount bölge")

            entry_zone, setup_name, model_name = None, "", "OB_FVG"

            # 1. Unicorn (en yüksek öncelik)
            for u in reversed(unicorns):
                if u["direction"] == "BULLISH" and u["bottom"] <= current_price <= u["top"]:
                    entry_zone = u
                    setup_name = "Unicorn Model (Breaker+FVG)"
                    model_name = "UNICORN"
                    confluences.append("UNICORN: Breaker Block + FVG çakışması")
                    break

            # 2. Silver Bullet
            if not entry_zone and sb_window:
                for fvg in reversed(fvgs):
                    if fvg["type"] == "BULLISH_FVG" and fvg["bottom"] <= current_price <= fvg["top"]:
                        entry_zone = fvg
                        setup_name = f"Silver Bullet FVG ({sb_window})"
                        model_name = "SILVER_BULLET"
                        confluences.append(f"Silver Bullet: FVG @ {sb_window}")
                        break

            # 3. OTE (Optimal Trade Entry)
            if not entry_zone and ote and ote["direction"] == "BULLISH":
                if ote["bottom"] <= current_price <= ote["top"]:
                    entry_zone = ote
                    setup_name = "OTE (62-79% Fib Retracement)"
                    model_name = "OTE"
                    confluences.append(f"OTE bölgesi: {round(ote['bottom'],4)}-{round(ote['top'],4)}")

            # 4. Bullish Breaker Block
            if not entry_zone:
                for b in reversed(breakers):
                    if b["type"] == "BULLISH_BREAKER" and b["bottom"] <= current_price <= b["top"]:
                        entry_zone = b
                        setup_name = "Bullish Breaker Block"
                        model_name = "OB_FVG"
                        confluences.append("Bullish Breaker Block içinde fiyat")
                        break

            # 5. FVG Entry
            if not entry_zone:
                for fvg in reversed(fvgs):
                    if fvg["type"] == "BULLISH_FVG" and fvg["bottom"] <= current_price <= fvg["top"]:
                        entry_zone = fvg
                        setup_name = "FVG Entry (Bullish)"
                        confluences.append("Bullish FVG içinde fiyat")
                        break

            # 6. Order Block Entry
            if not entry_zone:
                for ob in reversed(obs):
                    if ob["type"] == "BULLISH_OB" and ob["bottom"] <= current_price <= ob["top"]:
                        entry_zone = ob
                        setup_name = "Order Block Entry (Bullish)"
                        confluences.append("Bullish OB içinde fiyat")
                        break

            if entry_zone:
                sl_candidates = [l["price"] for l in liq["sell_side"] if l["price"] < current_price]
                sl  = min(sl_candidates) if sl_candidates else entry_zone.get("bottom", current_price) * 0.999
                tp_candidates = [l["price"] for l in liq["buy_side"] if l["price"] > current_price]
                tp1 = tp_candidates[0]  if tp_candidates            else current_price * 1.005
                tp2 = tp_candidates[1]  if len(tp_candidates) > 1   else current_price * 1.010

                # IPDA hedef ekle
                ipda_targets = [v for k, v in ipda.items() if "high" in k and v > current_price]
                if ipda_targets:
                    tp2 = min(ipda_targets)
                    confluences.append(f"IPDA hedef: {round(tp2, 4)}")

                risk   = current_price - sl
                reward = tp1 - current_price
                rr     = round(reward / risk, 2) if risk > 0 else 0

                if rr >= 2.0:
                    return Signal(
                        symbol=self.symbol, direction="LONG",
                        entry=round(current_price, 5), sl=round(sl, 5),
                        tp1=round(tp1, 5), tp2=round(tp2, 5),
                        rr=rr, setup=setup_name, timeframe="MTF",
                        kill_zone=kill_zone, bias=bias,
                        confluences=confluences, timestamp=datetime.utcnow(),
                        model=model_name,
                    )

        # ── SHORT kurulumu ─────────────────────────────────────────────────
        if bias in ("BEARISH", "CHOCH_BEARISH") and pd_zone["zone"] == "PREMIUM":
            confluences = base_confluences.copy()
            confluences.append(f"HTF Bias: {bias} | Premium bölge")

            entry_zone, setup_name, model_name = None, "", "OB_FVG"

            # 1. Unicorn
            for u in reversed(unicorns):
                if u["direction"] == "BEARISH" and u["bottom"] <= current_price <= u["top"]:
                    entry_zone = u
                    setup_name = "Unicorn Model (Breaker+FVG)"
                    model_name = "UNICORN"
                    confluences.append("UNICORN: Breaker Block + FVG çakışması")
                    break

            # 2. Silver Bullet
            if not entry_zone and sb_window:
                for fvg in reversed(fvgs):
                    if fvg["type"] == "BEARISH_FVG" and fvg["bottom"] <= current_price <= fvg["top"]:
                        entry_zone = fvg
                        setup_name = f"Silver Bullet FVG ({sb_window})"
                        model_name = "SILVER_BULLET"
                        confluences.append(f"Silver Bullet: FVG @ {sb_window}")
                        break

            # 3. OTE
            if not entry_zone and ote and ote["direction"] == "BEARISH":
                if ote["bottom"] <= current_price <= ote["top"]:
                    entry_zone = ote
                    setup_name = "OTE (62-79% Fib Retracement)"
                    model_name = "OTE"
                    confluences.append(f"OTE bölgesi: {round(ote['bottom'],4)}-{round(ote['top'],4)}")

            # 4. Bearish Breaker Block
            if not entry_zone:
                for b in reversed(breakers):
                    if b["type"] == "BEARISH_BREAKER" and b["bottom"] <= current_price <= b["top"]:
                        entry_zone = b
                        setup_name = "Bearish Breaker Block"
                        confluences.append("Bearish Breaker Block içinde fiyat")
                        break

            # 5. FVG Entry
            if not entry_zone:
                for fvg in reversed(fvgs):
                    if fvg["type"] == "BEARISH_FVG" and fvg["bottom"] <= current_price <= fvg["top"]:
                        entry_zone = fvg
                        setup_name = "FVG Entry (Bearish)"
                        confluences.append("Bearish FVG içinde fiyat")
                        break

            # 6. Order Block Entry
            if not entry_zone:
                for ob in reversed(obs):
                    if ob["type"] == "BEARISH_OB" and ob["bottom"] <= current_price <= ob["top"]:
                        entry_zone = ob
                        setup_name = "Order Block Entry (Bearish)"
                        confluences.append("Bearish OB içinde fiyat")
                        break

            if entry_zone:
                sl_candidates = [l["price"] for l in liq["buy_side"] if l["price"] > current_price]
                sl  = max(sl_candidates) if sl_candidates else entry_zone.get("top", current_price) * 1.001
                tp_candidates = [l["price"] for l in liq["sell_side"] if l["price"] < current_price]
                tp1 = tp_candidates[-1] if tp_candidates            else current_price * 0.995
                tp2 = tp_candidates[-2] if len(tp_candidates) > 1   else current_price * 0.990

                ipda_targets = [v for k, v in ipda.items() if "low" in k and v < current_price]
                if ipda_targets:
                    tp2 = max(ipda_targets)
                    confluences.append(f"IPDA hedef: {round(tp2, 4)}")

                risk   = sl - current_price
                reward = current_price - tp1
                rr     = round(reward / risk, 2) if risk > 0 else 0

                if rr >= 2.0:
                    return Signal(
                        symbol=self.symbol, direction="SHORT",
                        entry=round(current_price, 5), sl=round(sl, 5),
                        tp1=round(tp1, 5), tp2=round(tp2, 5),
                        rr=rr, setup=setup_name, timeframe="MTF",
                        kill_zone=kill_zone, bias=bias,
                        confluences=confluences, timestamp=datetime.utcnow(),
                        model=model_name,
                    )

        return None
