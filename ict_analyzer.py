"""
ICT Analyzer v3 — Inner Circle Trader tam metodoloji implementasyonu.

Öğrenilen kavramlar (ICT'nin ücretsiz YouTube/mentorship materyallerinden):
  Power of 3 / AMD, Market Structure (BOS/CHOCH), FVG, IFVG,
  Order Blocks, Breaker Blocks, Unicorn Model, OTE (62-79% Fib),
  Silver Bullet, IPDA (20/40/60d), SMT Divergence, MMXM Model,
  Judas Swing, Quarterly Theory, Draw on Liquidity (DOL)
"""

import pandas as pd
import numpy as np
from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime, date
import pytz


@dataclass
class Signal:
    symbol: str
    direction: str
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
    model: str = ""
    confidence: int = 0    # 1-5 yıldız puan


class ICTAnalyzer:
    def __init__(self, symbol: str):
        self.symbol = symbol
        self._et = pytz.timezone("America/New_York")

    # ══════════════════════════════════════════════════════════════════════
    # MARKET STRUCTURE — BOS / CHOCH
    # ══════════════════════════════════════════════════════════════════════
    def detect_market_structure(self, df: pd.DataFrame) -> str:
        sh, sl = self._swing_points(df)
        if len(sh) < 2 or len(sl) < 2:
            return "NEUTRAL"
        hh = sh[-1][1] > sh[-2][1]
        hl = sl[-1][1] > sl[-2][1]
        lh = sh[-1][1] < sh[-2][1]
        ll = sl[-1][1] < sl[-2][1]
        if hh and hl:  return "BULLISH"
        if lh and ll:  return "BEARISH"
        if lh and hl:  return "CHOCH_BULLISH"
        if hh and ll:  return "CHOCH_BEARISH"
        return "NEUTRAL"

    def _swing_points(self, df: pd.DataFrame, strength: int = 2):
        highs = df["High"].values
        lows  = df["Low"].values
        n     = len(df)
        sh, sl = [], []
        for i in range(strength, n - strength):
            if all(highs[i] > highs[i-j] for j in range(1, strength+1)) and \
               all(highs[i] > highs[i+j] for j in range(1, strength+1)):
                sh.append((i, highs[i]))
            if all(lows[i] < lows[i-j] for j in range(1, strength+1)) and \
               all(lows[i] < lows[i+j] for j in range(1, strength+1)):
                sl.append((i, lows[i]))
        return sh, sl

    # ══════════════════════════════════════════════════════════════════════
    # POWER OF 3 / AMD — Accumulation, Manipulation, Distribution
    # ══════════════════════════════════════════════════════════════════════
    def detect_amd_phase(self, df_1h: pd.DataFrame) -> str:
        """
        Asia (00-07 UTC) = Accumulation
        London (07-12 UTC) = Manipulation (Judas Swing)
        New York (12-21 UTC) = Distribution (gerçek hareket)
        """
        now_utc = datetime.utcnow()
        h = now_utc.hour
        if 0 <= h < 7:    return "ACCUMULATION"   # Asia
        elif 7 <= h < 12: return "MANIPULATION"   # London açılış
        elif 12 <= h < 21: return "DISTRIBUTION"  # New York
        return "CONSOLIDATION"

    # ══════════════════════════════════════════════════════════════════════
    # QUARTERLY THEORY — mevsimsel bias
    # ══════════════════════════════════════════════════════════════════════
    def quarterly_bias(self) -> dict:
        """
        Q1 (Jan-Mar): Accumulation/Manipulation → genellikle yukarı
        Q2 (Apr-Jun): Expansion → trend devamı
        Q3 (Jul-Sep): Distribution → zayıf/düzeltme
        Q4 (Oct-Dec): Reversal → büyük hareketler
        """
        month = datetime.utcnow().month
        if month in (1, 2, 3):
            return {"quarter": "Q1", "tendency": "BULLISH_ACCUMULATION", "confidence": "MEDIUM"}
        elif month in (4, 5, 6):
            return {"quarter": "Q2", "tendency": "EXPANSION", "confidence": "HIGH"}
        elif month in (7, 8, 9):
            return {"quarter": "Q3", "tendency": "DISTRIBUTION_BEARISH", "confidence": "LOW"}
        else:
            return {"quarter": "Q4", "tendency": "REVERSAL_VOLATILE", "confidence": "MEDIUM"}

    # ══════════════════════════════════════════════════════════════════════
    # FAIR VALUE GAP (FVG) — 3 mumlu imbalance
    # ══════════════════════════════════════════════════════════════════════
    def find_fvg(self, df: pd.DataFrame, min_size_pct: float = 0.0005) -> list:
        fvgs = []
        current = df["Close"].iloc[-1]
        for i in range(1, len(df) - 1):
            c1h = df["High"].iloc[i-1]
            c1l = df["Low"].iloc[i-1]
            c3h = df["High"].iloc[i+1]
            c3l = df["Low"].iloc[i+1]
            # Bullish FVG
            if c1h < c3l:
                size = c3l - c1h
                if size / current >= min_size_pct and current < c3l:
                    fvgs.append({"type": "BULLISH_FVG", "top": c3l, "bottom": c1h,
                                 "midpoint": (c3l+c1h)/2, "size": size,
                                 "index": i, "time": df.index[i]})
            # Bearish FVG
            if c1l > c3h:
                size = c1l - c3h
                if size / current >= min_size_pct and current > c3h:
                    fvgs.append({"type": "BEARISH_FVG", "top": c1l, "bottom": c3h,
                                 "midpoint": (c1l+c3h)/2, "size": size,
                                 "index": i, "time": df.index[i]})
        return fvgs

    # ══════════════════════════════════════════════════════════════════════
    # IFVG — Inverse Fair Value Gap (kırılan FVG tersine döner)
    # ══════════════════════════════════════════════════════════════════════
    def find_ifvg(self, df: pd.DataFrame) -> list:
        """
        Kırılan FVG → IFVG (tam tersi rol).
        Bullish FVG kırılırsa → Bearish IFVG (direnç).
        Bearish FVG kırılırsa → Bullish IFVG (destek).
        """
        fvgs   = self.find_fvg(df)
        ifvgs  = []
        closes = df["Close"].values

        for fvg in fvgs:
            idx = fvg["index"]
            for j in range(idx + 1, len(df)):
                if fvg["type"] == "BULLISH_FVG" and closes[j] < fvg["bottom"]:
                    ifvgs.append({"type": "BEARISH_IFVG",
                                  "top": fvg["top"], "bottom": fvg["bottom"],
                                  "midpoint": fvg["midpoint"],
                                  "original_fvg": fvg, "broken_at": j})
                    break
                if fvg["type"] == "BEARISH_FVG" and closes[j] > fvg["top"]:
                    ifvgs.append({"type": "BULLISH_IFVG",
                                  "top": fvg["top"], "bottom": fvg["bottom"],
                                  "midpoint": fvg["midpoint"],
                                  "original_fvg": fvg, "broken_at": j})
                    break
        return ifvgs

    # ══════════════════════════════════════════════════════════════════════
    # ORDER BLOCKS
    # ══════════════════════════════════════════════════════════════════════
    def find_order_blocks(self, df: pd.DataFrame) -> list:
        obs = []
        for i in range(1, len(df) - 3):
            up   = all(df["Close"].iloc[i+j] > df["Close"].iloc[i+j-1] for j in range(1,4))
            down = all(df["Close"].iloc[i+j] < df["Close"].iloc[i+j-1] for j in range(1,4))
            if up and df["Close"].iloc[i] < df["Open"].iloc[i]:
                obs.append({"type": "BULLISH_OB",
                            "top": df["High"].iloc[i], "bottom": df["Low"].iloc[i],
                            "50pct": (df["High"].iloc[i]+df["Low"].iloc[i])/2,
                            "index": i, "time": df.index[i]})
            if down and df["Close"].iloc[i] > df["Open"].iloc[i]:
                obs.append({"type": "BEARISH_OB",
                            "top": df["High"].iloc[i], "bottom": df["Low"].iloc[i],
                            "50pct": (df["High"].iloc[i]+df["Low"].iloc[i])/2,
                            "index": i, "time": df.index[i]})
        return obs

    # ══════════════════════════════════════════════════════════════════════
    # BREAKER BLOCKS — kırılan OB ters yöne döner
    # ══════════════════════════════════════════════════════════════════════
    def find_breaker_blocks(self, df: pd.DataFrame) -> list:
        obs      = self.find_order_blocks(df)
        breakers = []
        closes   = df["Close"].values
        for ob in obs:
            for j in range(ob["index"] + 1, len(df)):
                if ob["type"] == "BULLISH_OB" and closes[j] < ob["bottom"]:
                    breakers.append({"type": "BEARISH_BREAKER",
                                     "top": ob["top"], "bottom": ob["bottom"],
                                     "midpoint": ob["50pct"],
                                     "index": ob["index"], "time": ob["time"]})
                    break
                if ob["type"] == "BEARISH_OB" and closes[j] > ob["top"]:
                    breakers.append({"type": "BULLISH_BREAKER",
                                     "top": ob["top"], "bottom": ob["bottom"],
                                     "midpoint": ob["50pct"],
                                     "index": ob["index"], "time": ob["time"]})
                    break
        return breakers

    # ══════════════════════════════════════════════════════════════════════
    # UNICORN MODEL — Breaker + FVG çakışması
    # ══════════════════════════════════════════════════════════════════════
    def find_unicorn(self, df: pd.DataFrame) -> list:
        breakers = self.find_breaker_blocks(df)
        fvgs     = self.find_fvg(df)
        unicorns = []
        for b in breakers:
            for f in fvgs:
                b_bull = b["type"] == "BULLISH_BREAKER" and f["type"] == "BULLISH_FVG"
                b_bear = b["type"] == "BEARISH_BREAKER" and f["type"] == "BEARISH_FVG"
                if b_bull or b_bear:
                    ot = min(b["top"], f["top"])
                    ob_ = max(b["bottom"], f["bottom"])
                    if ot > ob_:
                        unicorns.append({
                            "direction": "BULLISH" if b_bull else "BEARISH",
                            "top": ot, "bottom": ob_,
                            "breaker": b, "fvg": f,
                        })
        return unicorns

    # ══════════════════════════════════════════════════════════════════════
    # OTE — Optimal Trade Entry (%62-%79 Fibonacci)
    # ══════════════════════════════════════════════════════════════════════
    def find_ote(self, df: pd.DataFrame, bias: str) -> Optional[dict]:
        sh, sl = self._swing_points(df)
        if not sh or not sl:
            return None
        if bias in ("BULLISH", "CHOCH_BULLISH"):
            lo, hi = sl[-1][1], sh[-1][1]
            if hi <= lo: return None
            return {"direction": "BULLISH",
                    "top":    lo + 0.79*(hi-lo),
                    "bottom": lo + 0.62*(hi-lo),
                    "fib_50": lo + 0.50*(hi-lo),
                    "swing_low": lo, "swing_high": hi}
        elif bias in ("BEARISH", "CHOCH_BEARISH"):
            hi, lo = sh[-1][1], sl[-1][1]
            if lo >= hi: return None
            return {"direction": "BEARISH",
                    "bottom": hi - 0.79*(hi-lo),
                    "top":    hi - 0.62*(hi-lo),
                    "fib_50": hi - 0.50*(hi-lo),
                    "swing_high": hi, "swing_low": lo}
        return None

    # ══════════════════════════════════════════════════════════════════════
    # IPDA — Interbank Price Delivery Algorithm (20/40/60 gün)
    # ══════════════════════════════════════════════════════════════════════
    def ipda_levels(self, df_daily: pd.DataFrame) -> dict:
        levels = {}
        for d in [20, 40, 60]:
            if len(df_daily) >= d:
                r = df_daily.tail(d)
                levels[f"high_{d}d"] = r["High"].max()
                levels[f"low_{d}d"]  = r["Low"].min()
        return levels

    # ══════════════════════════════════════════════════════════════════════
    # SMT DIVERGENCE — Korelasyonlu enstrüman uyumsuzluğu
    # ══════════════════════════════════════════════════════════════════════
    def detect_smt_divergence(self, df_a: pd.DataFrame,
                               df_b: pd.DataFrame, lookback: int = 10) -> str:
        """
        İki korelasyonlu enstrüman karşılaştırması.
        A yeni düşük yapıyor, B yapmıyorsa → Bullish SMT (B'yi long al).
        A yeni yüksek yapıyor, B yapmıyorsa → Bearish SMT (A'yı short al).
        """
        if df_a is None or df_b is None or df_a.empty or df_b.empty:
            return "NONE"

        # Ortak tarih aralığı
        common = df_a.index.intersection(df_b.index)
        if len(common) < lookback:
            return "NONE"

        a = df_a.loc[common].tail(lookback)
        b = df_b.loc[common].tail(lookback)

        a_new_low  = a["Low"].iloc[-1]  < a["Low"].iloc[:-1].min()
        b_new_low  = b["Low"].iloc[-1]  < b["Low"].iloc[:-1].min()
        a_new_high = a["High"].iloc[-1] > a["High"].iloc[:-1].max()
        b_new_high = b["High"].iloc[-1] > b["High"].iloc[:-1].max()

        if a_new_low and not b_new_low:
            return "BULLISH_SMT"    # A düşük yapıyor B yapmıyor → long
        if b_new_low and not a_new_low:
            return "BULLISH_SMT"
        if a_new_high and not b_new_high:
            return "BEARISH_SMT"   # A yüksek yapıyor B yapmıyor → short
        if b_new_high and not a_new_high:
            return "BEARISH_SMT"
        return "NONE"

    # ══════════════════════════════════════════════════════════════════════
    # MMXM — Market Maker Buy/Sell Model
    # ERL (External Range Liquidity) → IRL (Internal Range Liquidity) akışı
    # ══════════════════════════════════════════════════════════════════════
    def detect_mmxm_phase(self, df: pd.DataFrame, bias: str) -> str:
        """
        MMXM: Fiyat önce ERL (dış likidite = swing high/low) tarar,
        sonra IRL (iç likidite = FVG/OB) hedefler.
        """
        sh, sl    = self._swing_points(df)
        current   = df["Close"].iloc[-1]

        if not sh or not sl:
            return "UNKNOWN"

        last_high = sh[-1][1]
        last_low  = sl[-1][1]

        if bias in ("BULLISH", "CHOCH_BULLISH"):
            if current < last_low:
                return "ERL_SWEEP_BULLISH"  # Likidite tarandı, long hazır
            elif current > (last_high + last_low) / 2:
                return "IRL_DELIVERY_BULLISH"  # İç likiditeye doğru
        elif bias in ("BEARISH", "CHOCH_BEARISH"):
            if current > last_high:
                return "ERL_SWEEP_BEARISH"  # Likidite tarandı, short hazır
            elif current < (last_high + last_low) / 2:
                return "IRL_DELIVERY_BEARISH"
        return "RANGING"

    # ══════════════════════════════════════════════════════════════════════
    # SILVER BULLET — 3AM / 10AM / 2PM NY pencereleri
    # ══════════════════════════════════════════════════════════════════════
    def is_silver_bullet_window(self) -> str:
        h = datetime.now(self._et).hour
        if h == 3:  return "silver_bullet_3am"
        if h == 10: return "silver_bullet_10am"
        if h == 14: return "silver_bullet_2pm"
        return ""

    # ══════════════════════════════════════════════════════════════════════
    # JUDAS SWING — Sahte hareket tespiti
    # ══════════════════════════════════════════════════════════════════════
    def detect_judas_swing(self, df: pd.DataFrame, bias: str) -> bool:
        if len(df) < 4: return False
        last = df.tail(4)
        if bias in ("BULLISH", "CHOCH_BULLISH"):
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

    # ══════════════════════════════════════════════════════════════════════
    # LIQUIDITY — BSL / SSL
    # ══════════════════════════════════════════════════════════════════════
    def find_liquidity(self, df: pd.DataFrame, lookback: int = 20) -> dict:
        recent = df.tail(lookback)
        liq = {"buy_side": [], "sell_side": []}
        for i in range(2, len(recent) - 2):
            h = recent["High"].iloc[i]
            l = recent["Low"].iloc[i]
            if h > recent["High"].iloc[i-1] and h > recent["High"].iloc[i-2] and \
               h > recent["High"].iloc[i+1] and h > recent["High"].iloc[i+2]:
                liq["buy_side"].append({"price": h, "time": recent.index[i]})
            if l < recent["Low"].iloc[i-1] and l < recent["Low"].iloc[i-2] and \
               l < recent["Low"].iloc[i+1] and l < recent["Low"].iloc[i+2]:
                liq["sell_side"].append({"price": l, "time": recent.index[i]})
        return liq

    # ══════════════════════════════════════════════════════════════════════
    # PREMIUM / DISCOUNT
    # ══════════════════════════════════════════════════════════════════════
    def get_premium_discount(self, df: pd.DataFrame, lookback: int = 50) -> dict:
        r  = df.tail(lookback)
        sh = r["High"].max()
        sl = r["Low"].min()
        eq = (sh + sl) / 2
        current = df["Close"].iloc[-1]
        return {"swing_high": sh, "swing_low": sl, "equilibrium": eq,
                "zone": "PREMIUM" if current > eq else "DISCOUNT",
                "current": current, "pct_from_eq": round((current-eq)/eq*100, 2)}

    # ══════════════════════════════════════════════════════════════════════
    # ANA SİNYAL ÜRETİCİ — ICT v3 tam metodoloji
    # ══════════════════════════════════════════════════════════════════════
    def generate_signal(self, df_htf: pd.DataFrame, df_mtf: pd.DataFrame,
                        kill_zone: str, news_clear: bool,
                        df_daily: pd.DataFrame = None,
                        df_corr: pd.DataFrame = None) -> Optional[Signal]:
        """
        Sinyal önceliği (yüksekten düşüğe):
        1. UNICORN (Breaker + FVG)         — 5 yıldız
        2. MMXM + Silver Bullet + SMT       — 4-5 yıldız
        3. OTE (62-79% Fib)                — 3-4 yıldız
        4. IFVG (Inverse FVG)              — 3 yıldız
        5. Breaker Block                   — 3 yıldız
        6. FVG / Order Block               — 2 yıldız
        """
        if not kill_zone or not news_clear:
            return None

        bias      = self.detect_market_structure(df_htf)
        pd_zone   = self.get_premium_discount(df_htf)
        liq       = self.find_liquidity(df_htf)
        current   = df_mtf["Close"].iloc[-1]

        # MTF analiz setleri
        fvgs     = self.find_fvg(df_mtf)
        ifvgs    = self.find_ifvg(df_mtf)
        obs      = self.find_order_blocks(df_mtf)
        breakers = self.find_breaker_blocks(df_mtf)
        unicorns = self.find_unicorn(df_mtf)
        ote      = self.find_ote(df_htf, bias)

        # Ek bağlam
        sb_window = self.is_silver_bullet_window()
        judas     = self.detect_judas_swing(df_mtf, bias)
        amd_phase = self.detect_amd_phase(df_htf)
        q_theory  = self.quarterly_bias()
        mmxm      = self.detect_mmxm_phase(df_htf, bias)

        # IPDA
        ipda = {}
        if df_daily is not None and not df_daily.empty:
            ipda = self.ipda_levels(df_daily)

        # SMT divergence (korelasyonlu çift)
        smt = "NONE"
        if df_corr is not None:
            smt = self.detect_smt_divergence(df_mtf, df_corr)

        # ── Temel confluence listesi ──────────────────────────────────────
        base = [f"Kill Zone: {kill_zone.upper()}"]
        if sb_window:
            base.append(f"Silver Bullet: {sb_window}")
        if judas:
            base.append("Judas Swing onayı")
        if amd_phase in ("MANIPULATION", "DISTRIBUTION"):
            base.append(f"AMD Fazı: {amd_phase}")
        if "ERL_SWEEP" in mmxm:
            base.append(f"MMXM: {mmxm}")
        if smt != "NONE":
            base.append(f"SMT Divergence: {smt}")

        q3_warning = q_theory["quarter"] == "Q3"  # Q3 düşük güven

        # IPDA yakın seviyeleri
        for k, v in ipda.items():
            if abs(current - v) / current < 0.003:
                base.append(f"IPDA {k}: {round(v,4)}")

        # ══════════════ LONG KURULUMU ════════════════════════════════════
        if bias in ("BULLISH", "CHOCH_BULLISH") and pd_zone["zone"] == "DISCOUNT":
            confs = base.copy()
            confs.append(f"HTF: {bias} | Discount ({round(pd_zone['pct_from_eq'],1)}%)")

            entry_zone, setup_name, model_name, stars = None, "", "OB_FVG", 2

            # 1. Unicorn ★★★★★
            for u in reversed(unicorns):
                if u["direction"] == "BULLISH" and u["bottom"] <= current <= u["top"]:
                    entry_zone, setup_name, model_name, stars = \
                        u, "Unicorn Model", "UNICORN", 5
                    confs.append("★ UNICORN: Breaker Block + FVG çakışması")
                    break

            # 2. Silver Bullet + FVG ★★★★★
            if not entry_zone and sb_window:
                for fvg in reversed(fvgs):
                    if fvg["type"] == "BULLISH_FVG" and fvg["bottom"] <= current <= fvg["top"]:
                        entry_zone, setup_name, model_name, stars = \
                            fvg, f"Silver Bullet ({sb_window})", "SILVER_BULLET", 5
                        confs.append(f"Silver Bullet FVG @ {sb_window}")
                        break

            # 3. OTE ★★★★
            if not entry_zone and ote and ote.get("direction") == "BULLISH":
                if ote["bottom"] <= current <= ote["top"]:
                    entry_zone, setup_name, model_name, stars = \
                        ote, "OTE 62-79% Fib", "OTE", 4
                    confs.append(f"OTE: {round(ote['bottom'],4)}-{round(ote['top'],4)}")

            # 4. IFVG ★★★
            if not entry_zone:
                for ifvg in reversed(ifvgs):
                    if ifvg["type"] == "BULLISH_IFVG" and ifvg["bottom"] <= current <= ifvg["top"]:
                        entry_zone, setup_name, model_name, stars = \
                            ifvg, "Bullish IFVG", "OB_FVG", 3
                        confs.append("Bullish IFVG (Ters FVG destek)")
                        break

            # 5. Bullish Breaker ★★★
            if not entry_zone:
                for b in reversed(breakers):
                    if b["type"] == "BULLISH_BREAKER" and b["bottom"] <= current <= b["top"]:
                        entry_zone, setup_name, model_name, stars = \
                            b, "Bullish Breaker Block", "OB_FVG", 3
                        confs.append("Bullish Breaker Block")
                        break

            # 6. FVG ★★
            if not entry_zone:
                for fvg in reversed(fvgs):
                    if fvg["type"] == "BULLISH_FVG" and fvg["bottom"] <= current <= fvg["top"]:
                        entry_zone, setup_name, model_name = fvg, "Bullish FVG", "OB_FVG"
                        confs.append("Bullish FVG")
                        break

            # 7. Order Block ★★
            if not entry_zone:
                for ob in reversed(obs):
                    if ob["type"] == "BULLISH_OB" and ob["bottom"] <= current <= ob["top"]:
                        entry_zone, setup_name, model_name = ob, "Bullish OB", "OB_FVG"
                        confs.append("Bullish Order Block")
                        break

            if entry_zone:
                sl_list = [l["price"] for l in liq["sell_side"] if l["price"] < current]
                sl  = min(sl_list) if sl_list else entry_zone.get("bottom", current) * 0.999
                tp_list = [l["price"] for l in liq["buy_side"] if l["price"] > current]
                tp1 = tp_list[0]  if tp_list            else current * 1.005
                tp2 = tp_list[1]  if len(tp_list) > 1   else current * 1.010

                # IPDA hedef
                ipda_up = sorted([v for k,v in ipda.items() if "high" in k and v > current])
                if ipda_up:
                    tp2 = ipda_up[0]
                    confs.append(f"IPDA hedef: {round(tp2,4)}")

                # SMT ekstra onay
                if smt == "BULLISH_SMT":
                    stars = min(stars + 1, 5)
                    confs.append("SMT Divergence: Bullish onay ✓")

                # Q3 uyarısı
                if q3_warning:
                    confs.append("⚠️ Q3 — düşük güven sezonu, pozisyon küçük tut")
                    stars = max(stars - 1, 1)

                risk   = current - sl
                reward = tp1 - current
                rr     = round(reward / risk, 2) if risk > 0 else 0

                if rr >= 2.0 and rr <= 15.0 and stars >= 4:
                    return Signal(
                        symbol=self.symbol, direction="LONG",
                        entry=round(current,5), sl=round(sl,5),
                        tp1=round(tp1,5), tp2=round(tp2,5),
                        rr=rr, setup=setup_name, timeframe="MTF",
                        kill_zone=kill_zone, bias=bias,
                        confluences=confs, timestamp=datetime.utcnow(),
                        model=model_name, confidence=stars,
                    )

        # ══════════════ SHORT KURULUMU ═══════════════════════════════════
        if bias in ("BEARISH", "CHOCH_BEARISH") and pd_zone["zone"] == "PREMIUM":
            confs = base.copy()
            confs.append(f"HTF: {bias} | Premium ({round(pd_zone['pct_from_eq'],1)}%)")

            entry_zone, setup_name, model_name, stars = None, "", "OB_FVG", 2

            # 1. Unicorn ★★★★★
            for u in reversed(unicorns):
                if u["direction"] == "BEARISH" and u["bottom"] <= current <= u["top"]:
                    entry_zone, setup_name, model_name, stars = \
                        u, "Unicorn Model", "UNICORN", 5
                    confs.append("★ UNICORN: Breaker Block + FVG çakışması")
                    break

            # 2. Silver Bullet + FVG ★★★★★
            if not entry_zone and sb_window:
                for fvg in reversed(fvgs):
                    if fvg["type"] == "BEARISH_FVG" and fvg["bottom"] <= current <= fvg["top"]:
                        entry_zone, setup_name, model_name, stars = \
                            fvg, f"Silver Bullet ({sb_window})", "SILVER_BULLET", 5
                        confs.append(f"Silver Bullet FVG @ {sb_window}")
                        break

            # 3. OTE ★★★★
            if not entry_zone and ote and ote.get("direction") == "BEARISH":
                if ote["bottom"] <= current <= ote["top"]:
                    entry_zone, setup_name, model_name, stars = \
                        ote, "OTE 62-79% Fib", "OTE", 4
                    confs.append(f"OTE: {round(ote['bottom'],4)}-{round(ote['top'],4)}")

            # 4. IFVG ★★★
            if not entry_zone:
                for ifvg in reversed(ifvgs):
                    if ifvg["type"] == "BEARISH_IFVG" and ifvg["bottom"] <= current <= ifvg["top"]:
                        entry_zone, setup_name, model_name, stars = \
                            ifvg, "Bearish IFVG", "OB_FVG", 3
                        confs.append("Bearish IFVG (Ters FVG direnç)")
                        break

            # 5. Bearish Breaker ★★★
            if not entry_zone:
                for b in reversed(breakers):
                    if b["type"] == "BEARISH_BREAKER" and b["bottom"] <= current <= b["top"]:
                        entry_zone, setup_name, model_name, stars = \
                            b, "Bearish Breaker Block", "OB_FVG", 3
                        confs.append("Bearish Breaker Block")
                        break

            # 6. FVG ★★
            if not entry_zone:
                for fvg in reversed(fvgs):
                    if fvg["type"] == "BEARISH_FVG" and fvg["bottom"] <= current <= fvg["top"]:
                        entry_zone, setup_name, model_name = fvg, "Bearish FVG", "OB_FVG"
                        confs.append("Bearish FVG")
                        break

            # 7. Order Block ★★
            if not entry_zone:
                for ob in reversed(obs):
                    if ob["type"] == "BEARISH_OB" and ob["bottom"] <= current <= ob["top"]:
                        entry_zone, setup_name, model_name = ob, "Bearish OB", "OB_FVG"
                        confs.append("Bearish Order Block")
                        break

            if entry_zone:
                sl_list = [l["price"] for l in liq["buy_side"] if l["price"] > current]
                sl  = max(sl_list) if sl_list else entry_zone.get("top", current) * 1.001
                tp_list = [l["price"] for l in liq["sell_side"] if l["price"] < current]
                tp1 = tp_list[-1] if tp_list            else current * 0.995
                tp2 = tp_list[-2] if len(tp_list) > 1   else current * 0.990

                ipda_dn = sorted([v for k,v in ipda.items() if "low" in k and v < current], reverse=True)
                if ipda_dn:
                    tp2 = ipda_dn[0]
                    confs.append(f"IPDA hedef: {round(tp2,4)}")

                if smt == "BEARISH_SMT":
                    stars = min(stars + 1, 5)
                    confs.append("SMT Divergence: Bearish onay ✓")

                if q3_warning:
                    confs.append("⚠️ Q3 — düşük güven sezonu, pozisyon küçük tut")
                    stars = max(stars - 1, 1)

                risk   = sl - current
                reward = current - tp1
                rr     = round(reward / risk, 2) if risk > 0 else 0

                if rr >= 2.0 and rr <= 15.0 and stars >= 4:
                    return Signal(
                        symbol=self.symbol, direction="SHORT",
                        entry=round(current,5), sl=round(sl,5),
                        tp1=round(tp1,5), tp2=round(tp2,5),
                        rr=rr, setup=setup_name, timeframe="MTF",
                        kill_zone=kill_zone, bias=bias,
                        confluences=confs, timestamp=datetime.utcnow(),
                        model=model_name, confidence=stars,
                    )

        return None
