"""
ICT Analyzer v8 — Inner Circle Trader TAM metodoloji (2017/2022/2024 Mentorship).

Kavramlar:
  Temel: BOS/CHOCH/MSS, FVG (BISI/SIBI), IFVG, Order Blocks, Breaker Blocks
  Modeller: Unicorn, OTE (62-79%), Silver Bullet, MMXM, AMD/Power of 3
  Zaman: Kill Zones, ICT Macros (8 pencere), NDOG, NWOG, Asian Range (19-00 NY)
  Gelişmiş: SMT Divergence, IPDA, Judas Swing, Quarterly Theory,
             Displacement, Session Sweep, Turtle Soup, CRT,
             Weekly Profiles, Inducement (IDM), Consequent Encroachment,
             BPR, Volume Imbalance, Rejection Block, Propulsion Block,
             Mitigation Block, Vacuum Block, Psychological Levels
  v8 Yeni: CISD (Change in State of Delivery), HRLR/LRLR (Liquidity Run),
            MMBM/MMSM (Market Maker Buy/Sell Model — 4 faz),
            STH/ITH/LTH + STL/ITL/LTL (Swing Hierarchy)
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
    # POWER OF 3 / AMD — Accumulation, Manipulation, Distribution (ICT 2024)
    # Exact ET time windows per ICT 2024 material:
    # Accumulation: 19:00-01:00 ET (Asia builds positions in tight range)
    # Manipulation: 01:00-07:00 ET (London false breakout, Judas Swing)
    # Distribution: 07:00-13:00 ET (NY delivers real direction)
    # ══════════════════════════════════════════════════════════════════════
    def detect_amd_phase(self, df_1h: pd.DataFrame) -> str:
        """
        ICT Power of 3 (AMD) — exact ET session windows:
        Asia   19:00-01:00 ET = Accumulation (tight range, build positions)
        London 01:00-07:00 ET = Manipulation (Judas Swing, retail traps)
        NY     07:00-13:00 ET = Distribution (real institutional direction)
        """
        h = datetime.now(self._et).hour
        if h >= 19 or h < 1:   return "ACCUMULATION"   # Asia
        elif 1 <= h < 7:       return "MANIPULATION"   # London
        elif 7 <= h < 13:      return "DISTRIBUTION"   # New York AM
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
    # IMPLIED FVG — Hidden gap between wick midpoints (ICT 2024)
    # Large displacement candle whose body is overlapped by neighbor wicks.
    # Bullish: (c1_wick_50% of upper, c3_wick_50% of lower) = hidden support
    # Bearish: (c1_wick_50% of lower, c3_wick_50% of upper) = hidden resistance
    # Different from Inversion FVG — this was NEVER visible as a gap.
    # ══════════════════════════════════════════════════════════════════════
    def find_implied_fvg(self, df: pd.DataFrame, min_size_pct: float = 0.0003) -> list:
        """
        Implied FVG: hidden support/resistance between wick 50% levels.
        Requires a large-bodied middle candle whose body is partially or
        fully overlapped by the wicks of both surrounding candles.
        """
        if len(df) < 3:
            return []

        implied = []
        current  = df["Close"].iloc[-1]
        atr_body = (df["Close"] - df["Open"]).abs().rolling(14).mean()

        for i in range(1, len(df) - 1):
            c1 = df.iloc[i-1]
            c2 = df.iloc[i]
            c3 = df.iloc[i+1]

            c2_body = abs(c2["Close"] - c2["Open"])
            if atr_body.iloc[i] <= 0 or c2_body < atr_body.iloc[i] * 1.2:
                continue   # c2 must be a displacement (larger than avg body)

            # Bullish Implied FVG: c2 is a big up candle
            if c2["Close"] > c2["Open"]:
                # c1 and c3 wicks overlap c2's body
                c1_upper_wick_50 = (c1["High"] + max(c1["Open"], c1["Close"])) / 2
                c3_lower_wick_50 = (c3["Low"]  + min(c3["Open"], c3["Close"])) / 2
                if c3_lower_wick_50 > c1_upper_wick_50:
                    size = c3_lower_wick_50 - c1_upper_wick_50
                    if size / current >= min_size_pct and current < c3_lower_wick_50:
                        implied.append({
                            "type":     "BULLISH_IMPLIED_FVG",
                            "top":      c3_lower_wick_50,
                            "bottom":   c1_upper_wick_50,
                            "midpoint": (c3_lower_wick_50 + c1_upper_wick_50) / 2,
                            "index":    i,
                            "time":     df.index[i],
                        })
            # Bearish Implied FVG: c2 is a big down candle
            elif c2["Close"] < c2["Open"]:
                c1_lower_wick_50 = (c1["Low"]  + min(c1["Open"], c1["Close"])) / 2
                c3_upper_wick_50 = (c3["High"] + max(c3["Open"], c3["Close"])) / 2
                if c1_lower_wick_50 > c3_upper_wick_50:
                    size = c1_lower_wick_50 - c3_upper_wick_50
                    if size / current >= min_size_pct and current > c3_upper_wick_50:
                        implied.append({
                            "type":     "BEARISH_IMPLIED_FVG",
                            "top":      c1_lower_wick_50,
                            "bottom":   c3_upper_wick_50,
                            "midpoint": (c1_lower_wick_50 + c3_upper_wick_50) / 2,
                            "index":    i,
                            "time":     df.index[i],
                        })
        return implied

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
    # OTE — Optimal Trade Entry (ICT Fibonacci: 62-79%, sweet spot 70.5%)
    # Extensions: -0.27 = TP1, -0.62 = TP2 (beyond swing)
    # Rule: price MUST first cross 50% equilibrium before OTE is valid
    # ══════════════════════════════════════════════════════════════════════
    def find_ote(self, df: pd.DataFrame, bias: str) -> Optional[dict]:
        sh, sl = self._swing_points(df)
        if not sh or not sl:
            return None
        if bias in ("BULLISH", "CHOCH_BULLISH"):
            lo, hi = sl[-1][1], sh[-1][1]
            if hi <= lo: return None
            rng = hi - lo
            eq  = lo + 0.50 * rng
            # Must have crossed below equilibrium (50%) to be valid OTE
            if df["Close"].iloc[-1] > eq:
                return None   # Not in discount — OTE not valid yet
            return {
                "direction":   "BULLISH",
                "top":         lo + 0.79 * rng,
                "bottom":      lo + 0.62 * rng,
                "sweet_spot":  lo + 0.705 * rng,   # ICT 70.5% precision level
                "fib_50":      eq,
                "tp1_ext":     hi + 0.27 * rng,    # -0.27 extension target
                "tp2_ext":     hi + 0.62 * rng,    # -0.62 extension target
                "swing_low":   lo,
                "swing_high":  hi,
            }
        elif bias in ("BEARISH", "CHOCH_BEARISH"):
            hi, lo = sh[-1][1], sl[-1][1]
            if lo >= hi: return None
            rng = hi - lo
            eq  = hi - 0.50 * rng
            if df["Close"].iloc[-1] < eq:
                return None   # Not in premium — OTE not valid yet
            return {
                "direction":   "BEARISH",
                "bottom":      hi - 0.79 * rng,
                "top":         hi - 0.62 * rng,
                "sweet_spot":  hi - 0.705 * rng,
                "fib_50":      eq,
                "tp1_ext":     lo - 0.27 * rng,    # -0.27 extension target
                "tp2_ext":     lo - 0.62 * rng,    # -0.62 extension target
                "swing_high":  hi,
                "swing_low":   lo,
            }
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
    # BISI / SIBI — FVG yön sınıflandırması (ICT 2024)
    # BISI = Up-closed FVG (bullish), SIBI = Down-closed FVG (bearish)
    # IOFED = Candle 3's boundary — earliest/tightest entry (best R:R)
    # CE    = 50% midpoint — second pyramid add
    # Far Edge = Candle 1's boundary — full fill (last resort)
    # ══════════════════════════════════════════════════════════════════════
    def find_fvg_classified(self, df: pd.DataFrame, min_size_pct: float = 0.0005) -> list:
        """find_fvg'yi BISI/SIBI + IOFED etiketiyle zenginleştirir."""
        fvgs = self.find_fvg(df, min_size_pct)
        for f in fvgs:
            f["label"] = "BISI" if f["type"] == "BULLISH_FVG" else "SIBI"
            f["consequent_encroachment"] = f["midpoint"]   # CE = 50%
            # IOFED: entry at candle-3 boundary (tightest entry, best R:R)
            if f["type"] == "BULLISH_FVG":
                f["iofed"] = f["top"]      # top = c3l, enter from above into FVG
            else:
                f["iofed"] = f["bottom"]   # bottom = c3h, enter from below into FVG
        return fvgs

    # ══════════════════════════════════════════════════════════════════════
    # BALANCED PRICE RANGE (BPR) — İki çakışan FVG → ultra güçlü bölge
    # ICT: BISI + SIBI çakışması = kurumsal dengeleme bölgesi
    # ══════════════════════════════════════════════════════════════════════
    def find_bpr(self, df: pd.DataFrame) -> list:
        """
        BPR: Bullish FVG ile Bearish FVG çakışıyorsa oluşur.
        Çakışan bölge hem destek hem direnç olabilir — bias yönünde kullan.
        """
        fvgs = self.find_fvg_classified(df)
        bull_fvgs = [f for f in fvgs if f["type"] == "BULLISH_FVG"]
        bear_fvgs = [f for f in fvgs if f["type"] == "BEARISH_FVG"]
        bprs = []
        for bf in bull_fvgs:
            for sf in bear_fvgs:
                overlap_top    = min(bf["top"], sf["top"])
                overlap_bottom = max(bf["bottom"], sf["bottom"])
                if overlap_top > overlap_bottom:
                    bprs.append({
                        "top":      overlap_top,
                        "bottom":   overlap_bottom,
                        "midpoint": (overlap_top + overlap_bottom) / 2,
                        "type":     "BPR",
                        "bull_fvg": bf,
                        "bear_fvg": sf,
                    })
        return bprs

    # ══════════════════════════════════════════════════════════════════════
    # VOLUME IMBALANCE — Gövde-gövde boşluk (wick çakışması olabilir)
    # FVG'den farkı: sadece candle body'leri arasındaki boşluk
    # ══════════════════════════════════════════════════════════════════════
    def find_volume_imbalance(self, df: pd.DataFrame, min_size_pct: float = 0.0003) -> list:
        """
        Volume Imbalance: Consecutive candle body'leri arasında boşluk.
        FVG'den daha sık oluşur, daha zayıf ama yine de geçerli PD Array.
        """
        vis  = []
        current = df["Close"].iloc[-1]
        for i in range(1, len(df) - 1):
            body1_top    = max(df["Open"].iloc[i-1], df["Close"].iloc[i-1])
            body1_bottom = min(df["Open"].iloc[i-1], df["Close"].iloc[i-1])
            body2_top    = max(df["Open"].iloc[i],   df["Close"].iloc[i])
            body2_bottom = min(df["Open"].iloc[i],   df["Close"].iloc[i])

            # Bullish VI: body2 tamamen body1'in üstünde
            if body2_bottom > body1_top:
                size = body2_bottom - body1_top
                if size / current >= min_size_pct:
                    vis.append({"type": "BULLISH_VI", "top": body2_bottom,
                                "bottom": body1_top, "midpoint": (body2_bottom+body1_top)/2,
                                "index": i})
            # Bearish VI: body2 tamamen body1'in altında
            elif body2_top < body1_bottom:
                size = body1_bottom - body2_top
                if size / current >= min_size_pct:
                    vis.append({"type": "BEARISH_VI", "top": body1_bottom,
                                "bottom": body2_top, "midpoint": (body1_bottom+body2_top)/2,
                                "index": i})
        return vis

    # ══════════════════════════════════════════════════════════════════════
    # REJECTION BLOCK — Uzun fitilli mum = kurumsal ret bölgesi
    # ══════════════════════════════════════════════════════════════════════
    def find_rejection_blocks(self, df: pd.DataFrame, wick_ratio: float = 2.5) -> list:
        """
        Rejection Block: Fitilin gövdeye oranı wick_ratio'dan büyükse
        güçlü kurumsal red — destek/direnç bölgesi.
        """
        rbs = []
        for i in range(1, len(df) - 1):
            o, h, l, c = df["Open"].iloc[i], df["High"].iloc[i], df["Low"].iloc[i], df["Close"].iloc[i]
            body    = abs(c - o)
            up_wick = h - max(o, c)
            dn_wick = min(o, c) - l
            if body == 0:
                continue
            # Bullish Rejection (uzun alt fitil) → destek
            if dn_wick / body >= wick_ratio and dn_wick > up_wick:
                rbs.append({"type": "BULLISH_REJECTION", "top": max(o, c),
                            "bottom": l, "midpoint": (max(o,c)+l)/2,
                            "wick_ratio": round(dn_wick/body, 1), "index": i})
            # Bearish Rejection (uzun üst fitil) → direnç
            elif up_wick / body >= wick_ratio and up_wick > dn_wick:
                rbs.append({"type": "BEARISH_REJECTION", "top": h,
                            "bottom": min(o, c), "midpoint": (h+min(o,c))/2,
                            "wick_ratio": round(up_wick/body, 1), "index": i})
        return rbs

    # ══════════════════════════════════════════════════════════════════════
    # 1ST PRESENTED FVG — Displacement sonrası ilk FVG (en güçlü)
    # ICT: Displacement'tan sonraki ILGINCI FVG entry için en iyi
    # ══════════════════════════════════════════════════════════════════════
    def find_first_presented_fvg(self, df: pd.DataFrame) -> Optional[dict]:
        """
        Displacement sonrası oluşan ilk FVG → en hassas entry bölgesi.
        """
        disp = self.detect_displacement(df)
        if not disp.get("found"):
            return None

        disp_time = disp.get("candle_time")
        if disp_time is None:
            return None

        fvgs = self.find_fvg_classified(df)
        direction = disp["direction"]

        for fvg in fvgs:
            fvg_time = fvg.get("time")
            if fvg_time is None:
                continue
            after_disp = fvg_time >= disp_time
            right_dir  = (direction == "BULLISH" and fvg["type"] == "BULLISH_FVG") or \
                         (direction == "BEARISH" and fvg["type"] == "BEARISH_FVG")
            if after_disp and right_dir:
                fvg["model"] = "1ST_FVG"
                return fvg

        return None

    # ══════════════════════════════════════════════════════════════════════
    # ICT VENOM MODEL — 90 dakikalık öncesi-açılış aralığı (Endeksler)
    # 08:00-09:30 NY arası range → 09:30 açılışta sweep + reversal
    # ══════════════════════════════════════════════════════════════════════
    def detect_venom_setup(self, df: pd.DataFrame) -> dict:
        """
        Venom: NQ/ES için 08:00-09:30 NY aralığını işaretle.
        09:30 sonrası bu aralığın high veya low'u sweep + MSS → giriş.
        """
        if len(df) < 20:
            return {"found": False}

        df_et = df.copy()
        df_et.index = pd.to_datetime(df_et.index, utc=True).tz_convert(self._et)

        today = df_et.index[-1].date()
        pre_mkt = df_et[
            (df_et.index.date == today) &
            (df_et.index.hour >= 8) &
            (df_et.index.hour < 9) |
            ((df_et.index.date == today) & (df_et.index.hour == 9) & (df_et.index.minute < 30))
        ]

        if len(pre_mkt) < 3:
            return {"found": False}

        venom_high = pre_mkt["High"].max()
        venom_low  = pre_mkt["Low"].min()
        current    = df["Close"].iloc[-1]
        last3_high = df["High"].iloc[-3:].max()
        last3_low  = df["Low"].iloc[-3:].min()

        now_et = datetime.now(self._et)
        if now_et.hour < 9 or (now_et.hour == 9 and now_et.minute < 30):
            return {"found": False}   # Henüz 09:30 açılmadı

        if last3_low < venom_low and current > venom_low:
            return {"found": True, "direction": "BULLISH",
                    "range_high": venom_high, "range_low": venom_low,
                    "target": venom_high,
                    "desc": f"Venom Bullish: Low sweep ({round(venom_low,2)}) → {round(venom_high,2)}"}
        if last3_high > venom_high and current < venom_high:
            return {"found": True, "direction": "BEARISH",
                    "range_high": venom_high, "range_low": venom_low,
                    "target": venom_low,
                    "desc": f"Venom Bearish: High sweep ({round(venom_high,2)}) → {round(venom_low,2)}"}

        return {"found": False}

    # ══════════════════════════════════════════════════════════════════════
    # ICT MACROS — 8 kesin zaman penceresi (NY local → UTC dönüşüm)
    # Algoritmanın en yoğun çalıştığı 20-dakikalık pencereler
    # ══════════════════════════════════════════════════════════════════════
    # Macro zamanları NY (Eastern) saatiyle:
    # London M1: 02:33-03:00, London M2: 04:03-04:30
    # NY AM M1: 08:50-09:10, NY AM M2: 09:50-10:10, NY AM M3: 10:50-11:10
    # NY Lunch: 11:50-12:10, NY PM: 13:10-13:40, NY Last: 15:15-15:45
    MACRO_WINDOWS_ET = [
        ("02:33", "03:00", "London Macro 1"),
        ("04:03", "04:30", "London Macro 2"),
        ("08:50", "09:10", "NY AM Macro 1"),
        ("09:50", "10:10", "NY AM Macro 2 ⭐"),   # En güçlü pencere
        ("10:50", "11:10", "NY AM Macro 3"),
        ("11:50", "12:10", "NY Lunch Macro"),
        ("13:10", "13:40", "NY PM Macro"),
        ("15:15", "15:45", "NY Last Hour Macro"),
    ]

    def is_ict_macro_window(self) -> str:
        """Şu an ICT Macro penceresi içindeyiz mi? Pencere adını döndür."""
        now_et = datetime.now(self._et).strftime("%H:%M")
        for start, end, name in self.MACRO_WINDOWS_ET:
            if start <= now_et <= end:
                return name
        return ""

    # ══════════════════════════════════════════════════════════════════════
    # NDOG / NWOG — Günlük & Haftalık Açılış Boşlukları
    # NDOG: 17:00-18:00 NY arası boşluk (her gün)
    # NWOG: Cuma 17:00 - Pazartesi 18:00 NY arası boşluk
    # ══════════════════════════════════════════════════════════════════════
    def find_opening_gaps(self, df_1h: pd.DataFrame) -> dict:
        """
        NDOG: Her gün 17:00 NY kapanış ile 18:00 NY açılış arası fiyat boşluğu.
        NWOG: Haftanın en büyük boşluğu — Cuma kapanış / Pazartesi açılış.
        Consequent Encroachment = boşluğun tam ortası (50%).
        """
        if df_1h.empty or len(df_1h) < 48:
            return {}

        df = df_1h.copy()
        df.index = pd.to_datetime(df.index, utc=True)
        df_et = df.copy()
        df_et.index = df_et.index.tz_convert(self._et)

        gaps = {"ndog": [], "nwog": None}

        # Son 5 NDOG bul
        for i in range(1, min(len(df_et), 120)):
            row = df_et.iloc[-i]
            h   = df_et.index[-i].hour
            dow = df_et.index[-i].weekday()  # 0=Mon, 4=Fri

            # 17:00 NY kapanış mumu → boşluk varsa
            if h == 17:
                prev_close = row["Close"]
                # 18:00 açılış
                next_idx = -i + 1 if i > 1 else None
                if next_idx and abs(next_idx) < len(df_et):
                    next_open = df_et.iloc[next_idx]["Open"]
                    if abs(next_open - prev_close) / prev_close > 0.0001:
                        top    = max(prev_close, next_open)
                        bottom = min(prev_close, next_open)
                        gaps["ndog"].append({
                            "top":    top,
                            "bottom": bottom,
                            "midpoint": (top + bottom) / 2,
                            "direction": "BULLISH" if next_open > prev_close else "BEARISH",
                            "date": df_et.index[-i].date(),
                        })
                        if len(gaps["ndog"]) >= 5:
                            break

        # NWOG: Cuma 17:00 vs Pazartesi 18:00
        fridays = df_et[df_et.index.weekday == 4]
        mondays = df_et[df_et.index.weekday == 0]
        if not fridays.empty and not mondays.empty:
            fri_close = fridays[fridays.index.hour == 17]
            mon_open  = mondays[mondays.index.hour == 18]
            if not fri_close.empty and not mon_open.empty:
                fc = fri_close.iloc[-1]["Close"]
                mo = mon_open.iloc[-1]["Open"]
                if abs(mo - fc) / fc > 0.0001:
                    top    = max(fc, mo)
                    bottom = min(fc, mo)
                    gaps["nwog"] = {
                        "top":      top,
                        "bottom":   bottom,
                        "midpoint": (top + bottom) / 2,
                        "direction": "BULLISH" if mo > fc else "BEARISH",
                    }
        return gaps

    # ══════════════════════════════════════════════════════════════════════
    # CRT — Candle Range Theory (ICT 2024)
    # Üst TF mumun high/low'u taranıp geri dönüşse → karşı yön
    # ══════════════════════════════════════════════════════════════════════
    def detect_crt(self, df_htf: pd.DataFrame, df_mtf: pd.DataFrame) -> dict:
        """
        CRT: Bir önceki HTF mumun high veya low'u kırılıp kapanış
        mum aralığı içine geri dönüyorsa → sweep + reversal sinyali.
        Entry: MSS sonrası FVG/OB'ye geri çekilmede.
        """
        if len(df_htf) < 3 or len(df_mtf) < 5:
            return {"found": False}

        prev_candle  = df_htf.iloc[-2]
        crt_high     = prev_candle["High"]
        crt_low      = prev_candle["Low"]
        current      = df_mtf["Close"].iloc[-1]

        last3_mtf_high = df_mtf["High"].iloc[-3:].max()
        last3_mtf_low  = df_mtf["Low"].iloc[-3:].min()
        last_close     = df_mtf["Close"].iloc[-1]

        # Bearish CRT: CRT-High aşıldı ama kapanış içine döndü
        if last3_mtf_high > crt_high and last_close < crt_high:
            return {"found": True, "direction": "BEARISH",
                    "crt_high": crt_high, "crt_low": crt_low,
                    "target": crt_low,
                    "desc": f"CRT Bearish: High ({round(crt_high,4)}) sweep → {round(crt_low,4)} hedef"}

        # Bullish CRT: CRT-Low aşıldı ama kapanış içine döndü
        if last3_mtf_low < crt_low and last_close > crt_low:
            return {"found": True, "direction": "BULLISH",
                    "crt_high": crt_high, "crt_low": crt_low,
                    "target": crt_high,
                    "desc": f"CRT Bullish: Low ({round(crt_low,4)}) sweep → {round(crt_high,4)} hedef"}

        return {"found": False}

    # ══════════════════════════════════════════════════════════════════════
    # WEEKLY PROFILE — Haftanın hangi gününde high/low oluşur?
    # ICT: Salı/Çarşamba genellikle haftalık high/low oluşturur
    # ══════════════════════════════════════════════════════════════════════
    def weekly_profile_bias(self) -> dict:
        """
        ICT Weekly Profiles:
        Pazartesi: Sahte hareket (manipulation), Salı/Çarşamba: Gerçek yön
        Perşembe: Devam veya geri çekilme, Cuma: Düşük olasılık (avoid)
        """
        dow = datetime.now(self._et).weekday()  # 0=Mon
        profiles = {
            0: {"day": "Pazartesi", "bias": "MANIPULATION",
                "note": "Sahte hareket — Salı yönünü bekle", "trade": False},
            1: {"day": "Salı",      "bias": "EXPANSION",
                "note": "Haftalık high/low en sık Salı oluşur", "trade": True},
            2: {"day": "Çarşamba",  "bias": "EXPANSION",
                "note": "Salı'da oluşmadıysa Çarşamba high/low", "trade": True},
            3: {"day": "Perşembe",  "bias": "CONTINUATION",
                "note": "Trend devamı veya düzeltme", "trade": True},
            4: {"day": "Cuma",      "bias": "AVOID",
                "note": "Friday Seek & Destroy — düşük güven", "trade": False},
        }
        return profiles.get(dow, {"day": "?", "bias": "NEUTRAL", "trade": True})

    # ══════════════════════════════════════════════════════════════════════
    # INDUCEMENT (IDM) — Sahte giriş noktası tespiti
    # Gerçek hareketten önce küçük ters swing = retail tuzağı
    # ══════════════════════════════════════════════════════════════════════
    def detect_inducement(self, df: pd.DataFrame, bias: str) -> dict:
        """
        IDM: Büyük hareketten önce küçük bir ters swing.
        Bullish bias → küçük düşüş (retail'i short'a çekiyor) → sonra yukarı
        Bearish bias → küçük yükseliş (retail'i long'a çekiyor) → sonra aşağı
        """
        if len(df) < 10:
            return {"found": False}

        recent = df.tail(10)
        closes = recent["Close"].values
        highs  = recent["High"].values
        lows   = recent["Low"].values

        # Son 3 mumda beklenen yönün tersi bir hareket var mı?
        if bias in ("BULLISH", "CHOCH_BULLISH"):
            # Son 3-5 mumda düşüş var, sonra toparlanıyor
            mini_drop  = closes[-4] > closes[-3] > closes[-2]
            recovering = closes[-1] > closes[-2] * 1.0003
            if mini_drop and recovering:
                idm_low = min(lows[-4:-1])
                return {"found": True, "direction": "BULLISH",
                        "idm_level": idm_low,
                        "desc": f"IDM Bullish: Retail short tuzağı @ {round(idm_low,4)}"}

        elif bias in ("BEARISH", "CHOCH_BEARISH"):
            mini_rise  = closes[-4] < closes[-3] < closes[-2]
            recovering = closes[-1] < closes[-2] * 0.9997
            if mini_rise and recovering:
                idm_high = max(highs[-4:-1])
                return {"found": True, "direction": "BEARISH",
                        "idm_level": idm_high,
                        "desc": f"IDM Bearish: Retail long tuzağı @ {round(idm_high,4)}"}

        return {"found": False}

    # ══════════════════════════════════════════════════════════════════════
    # SILVER BULLET — 3AM / 8:30AM / 10AM / 2PM NY (ICT 2022/2024)
    # 08:30 = US economic release window, ICT 2024 Lecture 1 key model
    # ══════════════════════════════════════════════════════════════════════
    def is_silver_bullet_window(self) -> str:
        now_et = datetime.now(self._et)
        h, m   = now_et.hour, now_et.minute
        if h == 3:  return "silver_bullet_3am"
        if h == 8 and m >= 30: return "silver_bullet_8:30am"   # 2024 model
        if h == 9 and m < 30:  return "silver_bullet_8:30am"   # 08:30-09:30 window
        if h == 10: return "silver_bullet_10am"
        if h == 14: return "silver_bullet_2pm"
        return ""

    # ══════════════════════════════════════════════════════════════════════
    # ICT INTRADAY PROFILES — 4 types (ICT 2017 Month 8 + 2022)
    # CBDR < 40 pips filter, Asian range 20-30 pips.
    # Normal: protraction 12:00-02:00 AM ET
    # Delayed: protraction 02:00+ AM ET (IPDA protraction stage)
    # ══════════════════════════════════════════════════════════════════════
    def detect_intraday_profile(self, df_1h: pd.DataFrame) -> dict:
        """
        Classify today's intraday profile:
        London Normal Buy/Sell: CBDR < 40p, Asian 20-30p, early move before 02:00
        London Delayed Buy/Sell: same filters but move after 02:00 ET
        """
        if len(df_1h) < 24:
            return {"profile": "UNKNOWN"}

        df_et = df_1h.copy()
        try:
            df_et.index = pd.to_datetime(df_et.index, utc=True).tz_convert(self._et)
        except Exception:
            return {"profile": "UNKNOWN"}

        today = df_et.index[-1].date()
        current = df_1h["Close"].iloc[-1]

        # CBDR range (14:00-20:00 ET yesterday)
        cbdr = self.calculate_cbdr(df_1h)
        cbdr_range_pct = cbdr.get("range", 0) / current if cbdr else 0
        cbdr_ok = cbdr_range_pct < 0.004   # ~40 pips equivalent for most instruments

        # Asian range (19:00-01:00 ET = midnight session)
        asian_df = df_et[
            (df_et.index.date == today) & (df_et.index.hour < 1)
        ]
        if asian_df.empty:
            asian_range_pct = 0
        else:
            arange = asian_df["High"].max() - asian_df["Low"].min()
            asian_range_pct = arange / current
        asian_ok = 0.001 < asian_range_pct < 0.005   # 20-30p equivalent

        # London open period (00:00-02:00 ET) — did price move?
        london_early = df_et[
            (df_et.index.date == today) &
            (df_et.index.hour >= 0) & (df_et.index.hour < 2)
        ]
        london_late = df_et[
            (df_et.index.date == today) &
            (df_et.index.hour >= 2) & (df_et.index.hour < 7)
        ]

        bias = self.detect_market_structure(df_1h)
        is_bullish = bias in ("BULLISH", "CHOCH_BULLISH")

        if not cbdr_ok or not asian_ok:
            return {
                "profile": "UNCLASSIFIED",
                "cbdr_ok": cbdr_ok, "asian_ok": asian_ok,
                "desc": "CBDR veya Asian range profil filtrelerine uymuyor",
            }

        # Check if significant move happened in early London (00-02 ET)
        if not london_early.empty:
            early_move = london_early["High"].max() - london_early["Low"].min()
            if early_move / current > 0.002:   # meaningful protraction
                profile_type = "NORMAL"
                profile = f"London Normal {'Buy' if is_bullish else 'Sell'}"
            elif not london_late.empty:
                profile_type = "DELAYED"
                profile = f"London Delayed {'Buy' if is_bullish else 'Sell'}"
            else:
                return {"profile": "FORMING"}
        else:
            return {"profile": "FORMING"}

        return {
            "profile":      profile,
            "type":         profile_type,
            "direction":    "BULLISH" if is_bullish else "BEARISH",
            "cbdr_ok":      cbdr_ok,
            "asian_ok":     asian_ok,
            "desc": (
                f"{profile}: CBDR✓ Asian✓ "
                f"{'Erken protraksiyon' if profile_type=='NORMAL' else 'IPDA gecikmeli protraksiyon'}"
            ),
        }

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
    # DISPLACEMENT — Büyük impulsif mum (ATR'nin 1.5x üstü)
    # ICT: FVG içeren güçlü mum = giriş onayı
    # ══════════════════════════════════════════════════════════════════════
    def detect_displacement(self, df: pd.DataFrame, lookback: int = 20) -> dict:
        """
        Displacement: Gövdesi ATR ortalamasının 1.5x üstünde olan mum.
        FVG bırakıyorsa güçlü giriş sinyali.
        """
        if len(df) < lookback + 3:
            return {"found": False}

        bodies   = (df["Close"] - df["Open"]).abs()
        atr      = bodies.rolling(lookback).mean()
        recent   = df.tail(6)
        atr_val  = atr.iloc[-1]

        for i in range(1, len(recent) - 1):
            body = abs(recent["Close"].iloc[i] - recent["Open"].iloc[i])
            if body < atr_val * 1.5:
                continue
            bull_disp = recent["Close"].iloc[i] > recent["Open"].iloc[i]
            bear_disp = recent["Close"].iloc[i] < recent["Open"].iloc[i]

            # Displacement + FVG kontrolü (3 mumlu boşluk)
            if i > 0 and i < len(recent) - 1:
                prev_h = recent["High"].iloc[i-1]
                next_l = recent["Low"].iloc[i+1]
                prev_l = recent["Low"].iloc[i-1]
                next_h = recent["High"].iloc[i+1]

                if bull_disp and prev_h < next_l:
                    return {"found": True, "direction": "BULLISH",
                            "body": body, "atr": atr_val,
                            "fvg_top": next_l, "fvg_bottom": prev_h,
                            "candle_time": recent.index[i]}
                if bear_disp and prev_l > next_h:
                    return {"found": True, "direction": "BEARISH",
                            "body": body, "atr": atr_val,
                            "fvg_top": prev_l, "fvg_bottom": next_h,
                            "candle_time": recent.index[i]}
        return {"found": False}

    # ══════════════════════════════════════════════════════════════════════
    # SESSION HIGH/LOW SWEEP — Asia/London high-low likidite avı
    # ICT: Önceki session'ın high veya low'unu tararsa → ters yön hazır
    # ══════════════════════════════════════════════════════════════════════
    def detect_session_sweep(self, df: pd.DataFrame) -> dict:
        """
        Son 3 saatteki fiyat Asia/London session H/L'yi aşıp dönüyorsa
        bu bir stop hunt — karşı yönde giriş fırsatı.
        """
        if len(df) < 24:
            return {"sweep": False}

        df_utc = df.copy()
        if not hasattr(df_utc.index, 'hour'):
            df_utc.index = pd.to_datetime(df_utc.index, utc=True)

        today = df_utc.index[-1].date()

        asia   = df_utc[(df_utc.index.date == today) & (df_utc.index.hour < 7)]
        london = df_utc[(df_utc.index.date == today) &
                        (df_utc.index.hour >= 7) & (df_utc.index.hour < 12)]

        current = df_utc["Close"].iloc[-1]
        last2   = df_utc.tail(3)

        results = {}

        if not asia.empty:
            ah = asia["High"].max()
            al = asia["Low"].min()
            # Asia high sweep + geri dönüş
            if last2["High"].max() > ah and current < ah:
                results = {"sweep": True, "type": "ASIA_HIGH_SWEEP",
                           "level": ah, "direction": "BEARISH",
                           "desc": f"Asia High ({round(ah,4)}) sweep → short"}
            elif last2["Low"].min() < al and current > al:
                results = {"sweep": True, "type": "ASIA_LOW_SWEEP",
                           "level": al, "direction": "BULLISH",
                           "desc": f"Asia Low ({round(al,4)}) sweep → long"}

        if not results.get("sweep") and not london.empty:
            lh = london["High"].max()
            ll = london["Low"].min()
            if last2["High"].max() > lh and current < lh:
                results = {"sweep": True, "type": "LONDON_HIGH_SWEEP",
                           "level": lh, "direction": "BEARISH",
                           "desc": f"London High ({round(lh,4)}) sweep → short"}
            elif last2["Low"].min() < ll and current > ll:
                results = {"sweep": True, "type": "LONDON_LOW_SWEEP",
                           "level": ll, "direction": "BULLISH",
                           "desc": f"London Low ({round(ll,4)}) sweep → long"}

        return results if results else {"sweep": False}

    # ══════════════════════════════════════════════════════════════════════
    # TURTLE SOUP — Eşit high/low tuzağı (equal highs/lows sweep)
    # ICT: EQH/EQL likidite havuzları kırılınca karşı yön
    # ══════════════════════════════════════════════════════════════════════
    def detect_turtle_soup(self, df: pd.DataFrame, tolerance: float = 0.0003,
                            lookback: int = 30) -> dict:
        """
        Son `lookback` mum içinde birden fazla high/low aynı seviyedeyse
        (tolerance içinde) → EQH veya EQL var.
        Fiyat bu seviyeyi aşıp geri dönüyorsa Turtle Soup sinyali.
        """
        if len(df) < lookback + 3:
            return {"found": False}

        recent  = df.tail(lookback)
        current = df["Close"].iloc[-1]
        last3   = df.tail(3)

        highs = recent["High"].values
        lows  = recent["Low"].values

        def find_eq(arr, tol):
            clusters = []
            for i in range(len(arr) - 1):
                for j in range(i+1, len(arr)):
                    if abs(arr[i] - arr[j]) / arr[i] < tol:
                        clusters.append((arr[i] + arr[j]) / 2)
            return clusters

        eq_highs = find_eq(highs[:-3], tolerance)
        eq_lows  = find_eq(lows[:-3],  tolerance)

        for eqh in eq_highs:
            if last3["High"].max() > eqh * (1 + tolerance) and current < eqh:
                return {"found": True, "type": "EQH_SWEEP", "level": eqh,
                        "direction": "BEARISH",
                        "desc": f"EQH ({round(eqh,4)}) Turtle Soup → short"}

        for eql in eq_lows:
            if last3["Low"].min() < eql * (1 - tolerance) and current > eql:
                return {"found": True, "type": "EQL_SWEEP", "level": eql,
                        "direction": "BULLISH",
                        "desc": f"EQL ({round(eql,4)}) Turtle Soup → long"}

        return {"found": False}

    # ══════════════════════════════════════════════════════════════════════
    # CBDR — Central Bank Dealers Range (ICT 2017 Month 8)
    # 14:00–20:00 NY arası range → ertesi günün H/L projeksiyon hedefi
    # ══════════════════════════════════════════════════════════════════════
    def calculate_cbdr(self, df_1h: pd.DataFrame) -> dict:
        """
        CBDR: 14:00-20:00 NY arası mumların body high/low'u.
        Standart deviasyon = CBDR yüksekliği.
        Bullish: -1/-2 std = büyük ihtimal gün dibi (hedef: +2/+3 std)
        Bearish: +1/+2 std = büyük ihtimal gün tepesi (hedef: -2/-3 std)
        """
        if df_1h.empty or len(df_1h) < 24:
            return {}

        df = df_1h.copy()
        df.index = pd.to_datetime(df.index, utc=True).tz_convert(self._et)
        today = df.index[-1].date()

        cbdr_df = df[
            (df.index.date == today) &
            (df.index.hour >= 14) &
            (df.index.hour < 20)
        ]

        if len(cbdr_df) < 2:
            return {}

        # ICT: body high/low kullan (wick değil)
        body_high = cbdr_df.apply(lambda r: max(r["Open"], r["Close"]), axis=1).max()
        body_low  = cbdr_df.apply(lambda r: min(r["Open"], r["Close"]), axis=1).min()
        cbdr_range = body_high - body_low

        if cbdr_range <= 0:
            return {}

        return {
            "high":    body_high,
            "low":     body_low,
            "range":   cbdr_range,
            "std1_up": body_high + cbdr_range,
            "std2_up": body_high + 2 * cbdr_range,
            "std3_up": body_high + 3 * cbdr_range,
            "std1_dn": body_low  - cbdr_range,
            "std2_dn": body_low  - 2 * cbdr_range,
            "std3_dn": body_low  - 3 * cbdr_range,
            "valid":   cbdr_range < 0.005 * body_high,  # <0.5% = ideal
        }

    # ══════════════════════════════════════════════════════════════════════
    # ADR — Average Daily Range (ICT 2017)
    # Son N günün ortalama yüksek-alçak farkı = günün öngörülen genişliği
    # ══════════════════════════════════════════════════════════════════════
    def calculate_adr(self, df_daily: pd.DataFrame, periods: int = 14) -> dict:
        """
        ADR: Son 14 günün High-Low ortalaması.
        1/3 ADR = Judas Swing sınırı (bu seviyeyi aşarsa sahte hareket teyit)
        Günün açılışı ± ADR = hedef H/L projeksiyonu.
        """
        if df_daily is None or len(df_daily) < periods:
            return {}

        daily_ranges = (df_daily["High"] - df_daily["Low"]).tail(periods)
        adr          = daily_ranges.mean()
        today_open   = df_daily["Open"].iloc[-1]

        return {
            "adr":         round(adr, 4),
            "adr_third":   round(adr / 3, 4),      # Judas Swing eşiği
            "proj_high":   round(today_open + adr, 4),
            "proj_low":    round(today_open - adr, 4),
            "proj_high50": round(today_open + adr * 0.5, 4),
            "proj_low50":  round(today_open - adr * 0.5, 4),
        }

    # ══════════════════════════════════════════════════════════════════════
    # PROPULSION BLOCK (ICT 2017 Month 4)
    # OB içine giren ve fiyatı oradan fırlatan tek mum
    # ══════════════════════════════════════════════════════════════════════
    def find_propulsion_blocks(self, df: pd.DataFrame) -> list:
        """
        Propulsion Block: OB'ye giren sonra hızla ters dönen mum.
        Geri test → midpoint (50%) ihlal edilmeden tepki = geçerli giriş.
        """
        obs   = self.find_order_blocks(df)
        props = []
        for ob in obs:
            idx = ob["index"]
            if idx + 3 >= len(df):
                continue

            # OB sonrası fiyat OB içine girip geri döndü mü?
            for j in range(idx + 1, min(idx + 6, len(df) - 1)):
                c = df["Close"].iloc[j]
                h = df["High"].iloc[j]
                l = df["Low"].iloc[j]
                mid = ob["50pct"]

                if ob["type"] == "BULLISH_OB":
                    # Fiyat OB içine indi ama midpoint'i kapatmadı → propulsion
                    if l <= ob["top"] and c > mid:
                        props.append({
                            "type":    "BULLISH_PROPULSION",
                            "top":     ob["top"],
                            "bottom":  ob["bottom"],
                            "midpoint": mid,
                            "index":   j,
                            "time":    df.index[j],
                            "desc":    f"Propulsion Long @ {round(mid,4)} (OB mid)"
                        })
                        break
                elif ob["type"] == "BEARISH_OB":
                    if h >= ob["bottom"] and c < mid:
                        props.append({
                            "type":    "BEARISH_PROPULSION",
                            "top":     ob["top"],
                            "bottom":  ob["bottom"],
                            "midpoint": mid,
                            "index":   j,
                            "time":    df.index[j],
                            "desc":    f"Propulsion Short @ {round(mid,4)} (OB mid)"
                        })
                        break
        return props

    # ══════════════════════════════════════════════════════════════════════
    # MITIGATION BLOCK (ICT 2017 Month 4)
    # Kurumların zararlı pozisyonlarını kapattığı eski OB bölgesi
    # ══════════════════════════════════════════════════════════════════════
    def find_mitigation_blocks(self, df: pd.DataFrame) -> list:
        """
        Mitigation Block: Fiyat OB'ye geri dönerek onu 'mitigate' etti
        (kurumlar zararı kapattı). Fiyat tekrar o bölgeye gelirse daha
        zayıf tepki — ama hâlâ destek/direnç olarak işlev görür.
        """
        obs  = self.find_order_blocks(df)
        mits = []
        for ob in obs:
            touched = False
            for j in range(ob["index"] + 1, len(df)):
                c = df["Close"].iloc[j]
                if ob["type"] == "BULLISH_OB" and c < ob["50pct"]:
                    touched = True
                    mits.append({
                        "type":     "BULLISH_MITIGATION",
                        "top":      ob["top"],
                        "bottom":   ob["bottom"],
                        "midpoint": ob["50pct"],
                        "mitigated_at": j,
                        "desc":     f"Mitigated Bull OB: {round(ob['bottom'],4)}-{round(ob['top'],4)}"
                    })
                    break
                if ob["type"] == "BEARISH_OB" and c > ob["50pct"]:
                    touched = True
                    mits.append({
                        "type":     "BEARISH_MITIGATION",
                        "top":      ob["top"],
                        "bottom":   ob["bottom"],
                        "midpoint": ob["50pct"],
                        "mitigated_at": j,
                        "desc":     f"Mitigated Bear OB: {round(ob['bottom'],4)}-{round(ob['top'],4)}"
                    })
                    break
        return mits

    # ══════════════════════════════════════════════════════════════════════
    # VACUUM BLOCK / LIQUIDITY VOID (ICT 2017 Month 4)
    # Fiyatın çok hızlı geçtiği bölge — geri dönüş beklenir
    # ══════════════════════════════════════════════════════════════════════
    def find_vacuum_blocks(self, df: pd.DataFrame, speed_mult: float = 3.0) -> list:
        """
        Vacuum Block: Bir mumun range'i ATR'nin speed_mult katından büyükse
        ve içinde neredeyse hiç geri çekilme yoksa → fiyat bu bölgeye döner.
        """
        if len(df) < 20:
            return []

        atr     = (df["High"] - df["Low"]).rolling(14).mean()
        vacuums = []

        for i in range(14, len(df) - 1):
            candle_range = df["High"].iloc[i] - df["Low"].iloc[i]
            if atr.iloc[i] <= 0:
                continue
            if candle_range < atr.iloc[i] * speed_mult:
                continue

            bull_vac = df["Close"].iloc[i] > df["Open"].iloc[i]
            bear_vac = df["Close"].iloc[i] < df["Open"].iloc[i]

            if bull_vac:
                vacuums.append({
                    "type":    "BULLISH_VACUUM",
                    "top":     df["High"].iloc[i],
                    "bottom":  df["Low"].iloc[i],
                    "midpoint": (df["High"].iloc[i] + df["Low"].iloc[i]) / 2,
                    "index":   i,
                    "speed":   round(candle_range / atr.iloc[i], 1),
                })
            elif bear_vac:
                vacuums.append({
                    "type":    "BEARISH_VACUUM",
                    "top":     df["High"].iloc[i],
                    "bottom":  df["Low"].iloc[i],
                    "midpoint": (df["High"].iloc[i] + df["Low"].iloc[i]) / 2,
                    "index":   i,
                    "speed":   round(candle_range / atr.iloc[i], 1),
                })
        return vacuums

    # ══════════════════════════════════════════════════════════════════════
    # DOL — Draw on Liquidity (ICT 2022/2024 core concept)
    # The specific price level the market is targeting next.
    # Selection: compare today's close vs yesterday's → DOL = prev day H or L
    # PDH/PDL are the most common intraday DOL targets.
    # ══════════════════════════════════════════════════════════════════════
    def find_draw_on_liquidity(self, df_daily: pd.DataFrame, df_htf: pd.DataFrame) -> dict:
        """
        DOL rules (ICT 2022):
        - Daily close > prev day close → DOL = prev day HIGH (BSL target)
        - Daily close < prev day close → DOL = prev day LOW  (SSL target)
        - Daily closes inside prev daily range → anticipate opposite DOL
        Also marks PDH, PDL, PWH, PWL (Previous Week High/Low) as levels.
        """
        if df_daily is None or len(df_daily) < 3:
            return {}

        today_close = df_daily["Close"].iloc[-1]
        prev_close  = df_daily["Close"].iloc[-2]
        pdh         = df_daily["High"].iloc[-2]   # Previous Day High
        pdl         = df_daily["Low"].iloc[-2]    # Previous Day Low
        current     = df_htf["Close"].iloc[-1] if not df_htf.empty else today_close

        # Inside bar check
        prev_high = df_daily["High"].iloc[-2]
        prev_low  = df_daily["Low"].iloc[-2]
        today_high = df_daily["High"].iloc[-1]
        today_low  = df_daily["Low"].iloc[-1]
        inside_bar = today_high <= prev_high and today_low >= prev_low

        if today_close > prev_close:
            dol_level   = pdh
            dol_dir     = "BULLISH"
            dol_type    = "PDH"
            dol_desc    = f"DOL → PDH {round(pdh,4)} (günlük kapanış yukarı)"
        elif today_close < prev_close:
            dol_level   = pdl
            dol_dir     = "BEARISH"
            dol_type    = "PDL"
            dol_desc    = f"DOL → PDL {round(pdl,4)} (günlük kapanış aşağı)"
        else:
            dol_level   = pdh if current > (pdh + pdl) / 2 else pdl
            dol_dir     = "BULLISH" if current > (pdh + pdl) / 2 else "BEARISH"
            dol_type    = "PDH" if dol_dir == "BULLISH" else "PDL"
            dol_desc    = f"DOL → {dol_type} {round(dol_level,4)} (inside bar)"

        # Weekly high/low (last 5 days)
        pwh = df_daily["High"].tail(5).max()
        pwl = df_daily["Low"].tail(5).min()

        return {
            "dol_level":  dol_level,
            "dol_dir":    dol_dir,
            "dol_type":   dol_type,
            "dol_desc":   dol_desc,
            "pdh":        pdh,
            "pdl":        pdl,
            "pwh":        pwh,
            "pwl":        pwl,
            "inside_bar": inside_bar,
        }

    # ══════════════════════════════════════════════════════════════════════
    # RDRB — Redelivered Rebalanced Price Range (ICT hidden PD Array)
    # Two consecutive candles: deliver → wick pullback → redeliver same dir
    # Wick = rebalancing zone. If price returns → strong reaction.
    # ══════════════════════════════════════════════════════════════════════
    def find_rdrb(self, df: pd.DataFrame, min_size_pct: float = 0.0003) -> list:
        """
        RDRB: Candle N delivers up, candle N+1 wicks down then closes up
        (or mirror for bearish). The wick = rebalanced zone.
        Similar to Rejection Block but requires consecutive delivery direction.
        """
        if len(df) < 3:
            return []

        rdrbs   = []
        current = df["Close"].iloc[-1]

        for i in range(1, len(df) - 1):
            c1 = df.iloc[i-1]
            c2 = df.iloc[i]

            c1_bull = c1["Close"] > c1["Open"]
            c2_bull = c2["Close"] > c2["Open"]
            c1_bear = not c1_bull
            c2_bear = not c2_bull

            # Bullish RDRB: both candles up, c2 has significant lower wick
            if c1_bull and c2_bull:
                c2_body   = c2["Close"] - c2["Open"]
                c2_wick   = c2["Open"] - c2["Low"]
                if c2_body > 0 and c2_wick / c2_body >= 0.5:
                    # Wick = rebalancing zone (c2 Low to c2 Open)
                    top    = c2["Open"]
                    bottom = c2["Low"]
                    size   = top - bottom
                    if size / current >= min_size_pct and current < top:
                        rdrbs.append({
                            "type":     "BULLISH_RDRB",
                            "top":      top,
                            "bottom":   bottom,
                            "midpoint": (top + bottom) / 2,
                            "index":    i,
                            "time":     df.index[i],
                        })

            # Bearish RDRB: both candles down, c2 has significant upper wick
            elif c1_bear and c2_bear:
                c2_body = c2["Open"] - c2["Close"]
                c2_wick = c2["High"] - c2["Open"]
                if c2_body > 0 and c2_wick / c2_body >= 0.5:
                    top    = c2["High"]
                    bottom = c2["Open"]
                    size   = top - bottom
                    if size / current >= min_size_pct and current > bottom:
                        rdrbs.append({
                            "type":     "BEARISH_RDRB",
                            "top":      top,
                            "bottom":   bottom,
                            "midpoint": (top + bottom) / 2,
                            "index":    i,
                            "time":     df.index[i],
                        })
        return rdrbs

    # ══════════════════════════════════════════════════════════════════════
    # PSYCHOLOGICAL LEVELS — Yuvarlak sayılar (ICT 2017 + Filling Numbers)
    # Altın için: $3300, $3350, $3400 gibi seviyeleri yakala
    # ══════════════════════════════════════════════════════════════════════
    def find_psychological_levels(self, current: float, step: float = None) -> list:
        """
        Yakın yuvarlak sayıları bul.
        Altın için step=50 (3300, 3350...), Forex için step=0.01
        """
        if step is None:
            if current > 1000:     step = 50     # Gold
            elif current > 100:    step = 10
            elif current > 10:     step = 1
            elif current > 1:      step = 0.05
            else:                  step = 0.001

        levels = []
        base = round(current / step) * step
        for mult in [-3, -2, -1, 0, 1, 2, 3]:
            lvl = base + mult * step
            pct_away = abs(lvl - current) / current
            if pct_away < 0.02:   # %2 yakınındaki seviyeleri ekle
                levels.append({
                    "price":   round(lvl, 5),
                    "pct_away": round(pct_away * 100, 3),
                    "type":    "above" if lvl > current else "below"
                })
        return levels

    # ══════════════════════════════════════════════════════════════════════
    # NY MIDNIGHT OPEN — 00:00 NY (ICT True Daily Bias Reference)
    # Price above MO = bullish day bias; below = bearish day bias.
    # MO also acts as intraday S/R — price often returns to it during NY.
    # ══════════════════════════════════════════════════════════════════════
    def find_midnight_open(self, df: pd.DataFrame) -> dict:
        """
        NY Midnight Open: open price at 00:00 ET.
        Above MO = bullish day bias. Below = bearish.
        NY Midnight Range = 00:00-03:00 ET (2022 model Judas reference).
        """
        if len(df) < 4:
            return {}

        df_et = df.copy()
        try:
            df_et.index = pd.to_datetime(df_et.index, utc=True).tz_convert(self._et)
        except Exception:
            return {}

        today = df_et.index[-1].date()

        # Midnight open (00:00 NY candle)
        midnight_candles = df_et[
            (df_et.index.date == today) & (df_et.index.hour == 0) & (df_et.index.minute == 0)
        ]
        if midnight_candles.empty:
            # Fallback: first candle of today
            today_candles = df_et[df_et.index.date == today]
            if today_candles.empty:
                return {}
            midnight_open = today_candles.iloc[0]["Open"]
        else:
            midnight_open = midnight_candles.iloc[0]["Open"]

        # NY Midnight Range (00:00-03:00 ET) — 2022 model Judas reference
        midnight_range = df_et[
            (df_et.index.date == today) &
            (df_et.index.hour >= 0) & (df_et.index.hour < 3)
        ]

        current = df["Close"].iloc[-1]
        result  = {
            "midnight_open": midnight_open,
            "bias": "BULLISH" if current > midnight_open else "BEARISH",
            "desc": (f"Price {'above' if current > midnight_open else 'below'} "
                     f"Midnight Open {round(midnight_open,4)}"),
        }

        if not midnight_range.empty:
            mr_high = midnight_range["High"].max()
            mr_low  = midnight_range["Low"].min()
            # Judas sweep detection (2022 model)
            last3_high = df["High"].iloc[-3:].max()
            last3_low  = df["Low"].iloc[-3:].min()
            swept_high = last3_high > mr_high and current < mr_high
            swept_low  = last3_low  < mr_low  and current > mr_low
            result.update({
                "mr_high":      mr_high,
                "mr_low":       mr_low,
                "mr_midpoint":  (mr_high + mr_low) / 2,
                "swept_high":   swept_high,
                "swept_low":    swept_low,
                "judas_dir":    ("BEARISH" if swept_high else "BULLISH" if swept_low else "NONE"),
            })

        return result

    # ══════════════════════════════════════════════════════════════════════
    # WEEKLY OPEN — Sunday 18:00 ET (ICT Weekly Bias Reference)
    # Price above WO all week = bullish; below = bearish.
    # Monday typically forms weekly high (bearish week) or low (bullish week).
    # ══════════════════════════════════════════════════════════════════════
    def find_weekly_open(self, df: pd.DataFrame) -> dict:
        """
        Weekly Open: First candle Sunday 18:00 ET (or Monday 00:00 if gap).
        WO above current price = discount (buy zone).
        WO below current price = premium (sell zone).
        """
        if len(df) < 5:
            return {}

        df_et = df.copy()
        try:
            df_et.index = pd.to_datetime(df_et.index, utc=True).tz_convert(self._et)
        except Exception:
            return {}

        current = df["Close"].iloc[-1]

        # Find most recent Sunday 18:00 or Monday first candle
        sundays = df_et[df_et.index.weekday == 6]  # 6 = Sunday
        mondays = df_et[df_et.index.weekday == 0]  # 0 = Monday

        weekly_open = None
        if not sundays.empty:
            sun_eve = sundays[sundays.index.hour >= 18]
            if not sun_eve.empty:
                weekly_open = sun_eve.iloc[-1]["Open"]
        if weekly_open is None and not mondays.empty:
            weekly_open = mondays.iloc[-1]["Open"]

        if weekly_open is None:
            return {}

        above_wo = current > weekly_open
        return {
            "weekly_open":  weekly_open,
            "bias":         "BULLISH" if above_wo else "BEARISH",
            "zone":         "PREMIUM" if above_wo else "DISCOUNT",
            "desc":         (f"Price {'above' if above_wo else 'below'} "
                             f"Weekly Open {round(weekly_open,4)}"),
        }

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
    # CISD — Change in State of Delivery (ICT 2022 Mentorship)
    # Body close above open of opposing leg = earliest reversal signal
    # Fires BEFORE MSS/CHoCH — use on 5m/15m after HTF PD Array tap
    # ══════════════════════════════════════════════════════════════════════
    def detect_cisd(self, df: pd.DataFrame, bias: str) -> dict:
        """
        Bullish CISD: body closes above the open of the last bearish (down) leg.
        Bearish CISD: body closes below the open of the last bullish (up) leg.
        Body-only rule — wicks are ignored.
        """
        if len(df) < 6:
            return {"found": False}

        closes = df["Close"].values
        opens  = df["Open"].values

        # Find last opposing leg then check if body closed past its open
        if bias in ("BULLISH", "CHOCH_BULLISH"):
            # Look for last bearish leg (series of down closes)
            for i in range(len(df) - 3, 1, -1):
                if opens[i] > closes[i]:   # bearish candle — opposing leg
                    opposing_open = opens[i]
                    # Check if any subsequent candle body closed above opposing open
                    for j in range(i + 1, len(df)):
                        body_close = closes[j]
                        body_open  = opens[j]
                        # Body close must be above opposing_open (body only)
                        if body_close > opposing_open and body_open < body_close:
                            return {
                                "found": True, "direction": "BULLISH",
                                "cisd_level": opposing_open,
                                "confirmed_at": j,
                                "desc": f"Bullish CISD: body close {round(body_close,4)} > bear open {round(opposing_open,4)}"
                            }
                    break

        elif bias in ("BEARISH", "CHOCH_BEARISH"):
            for i in range(len(df) - 3, 1, -1):
                if opens[i] < closes[i]:   # bullish candle — opposing leg
                    opposing_open = opens[i]
                    for j in range(i + 1, len(df)):
                        body_close = closes[j]
                        body_open  = opens[j]
                        if body_close < opposing_open and body_open > body_close:
                            return {
                                "found": True, "direction": "BEARISH",
                                "cisd_level": opposing_open,
                                "confirmed_at": j,
                                "desc": f"Bearish CISD: body close {round(body_close,4)} < bull open {round(opposing_open,4)}"
                            }
                    break

        return {"found": False}

    # ══════════════════════════════════════════════════════════════════════
    # HRLR / LRLR — High/Low Resistance Liquidity Run (ICT 2017)
    # Classify if the path to target is clear or blocked by swing obstacles
    # LRLR = clean acceleration (FVGs left behind, no opposing swings in path)
    # HRLR = multiple swing obstacles block path (needs news catalyst)
    # ══════════════════════════════════════════════════════════════════════
    def classify_liquidity_run(self, df: pd.DataFrame, target_level: float,
                               direction: str) -> dict:
        """
        Count swing highs/lows between current price and target.
        LRLR (0-1 obstacles) → high probability TP, enter aggressively.
        HRLR (2+ obstacles)  → stretch target, wait for news catalyst.
        """
        if len(df) < 10:
            return {"type": "UNKNOWN", "obstacles": 0}

        current = df["Close"].iloc[-1]
        sh, sl  = self._swing_points(df, strength=1)   # smaller strength = more swings

        obstacles = 0
        if direction == "BULLISH":
            # Count swing highs between current and target
            obstacles = sum(1 for _, h in sh if current < h < target_level)
        else:
            # Count swing lows between target and current
            obstacles = sum(1 for _, l in sl if target_level < l < current)

        run_type = "LRLR" if obstacles <= 1 else "HRLR"
        return {
            "type": run_type,
            "obstacles": obstacles,
            "desc": (f"LRLR: chıkan yol açık ({obstacles} engel)"
                     if run_type == "LRLR"
                     else f"HRLR: {obstacles} swing engeli — haber gününü bekle"),
        }

    # ══════════════════════════════════════════════════════════════════════
    # MMBM / MMSM — Market Maker Buy/Sell Model (ICT 2022)
    # 4 phases: Original Consolidation → Engineering Liquidity →
    #           Smart Money Reversal → Liquidity Hunt
    # ══════════════════════════════════════════════════════════════════════
    def detect_mm_model_phase(self, df_htf: pd.DataFrame, df_mtf: pd.DataFrame,
                              bias: str) -> dict:
        """
        Detects which phase of the Market Maker model price is in.
        Phase 3 (Smart Money Reversal after MSS + SMT) = entry phase.
        """
        if len(df_htf) < 20 or len(df_mtf) < 10:
            return {"phase": "UNKNOWN", "model": "NONE"}

        current    = df_mtf["Close"].iloc[-1]
        atr_series = (df_htf["High"] - df_htf["Low"]).rolling(14).mean()
        if atr_series.empty or pd.isna(atr_series.iloc[-1]):
            return {"phase": "UNKNOWN", "model": "NONE"}
        atr = atr_series.iloc[-1]

        # Phase 1 — Consolidation: tight range, recent range < 1.5x ATR
        recent_range = df_htf["High"].tail(10).max() - df_htf["Low"].tail(10).min()
        in_consol    = recent_range < atr * 1.5

        # Phase 2 — Engineering Liquidity: EQH or EQL present (Turtle Soup setup)
        turtle = self.detect_turtle_soup(df_mtf)
        in_engineering = turtle.get("found", False)

        # Phase 3 — Smart Money Reversal: MSS after sweep
        sess_sweep = self.detect_session_sweep(df_mtf)
        disp       = self.detect_displacement(df_mtf)
        ms         = self.detect_market_structure(df_mtf)
        in_reversal = (
            sess_sweep.get("sweep") and
            disp.get("found") and
            "CHOCH" in ms
        )

        # Phase 4 — Liquidity Hunt: strong trending with FVGs
        fvgs = self.find_fvg_classified(df_mtf)
        in_hunt = len(fvgs) >= 2 and not in_consol

        if in_reversal:
            model = "MMBM" if bias in ("BULLISH","CHOCH_BULLISH") else "MMSM"
            return {
                "phase": "SMART_MONEY_REVERSAL",
                "model": model,
                "desc":  f"{model} Faz 3: MSS+Sweep+Displacement onayı → entry!",
                "entry_ready": True,
            }
        if in_engineering:
            return {
                "phase": "ENGINEERING_LIQUIDITY",
                "model": "MMBM" if bias in ("BULLISH","CHOCH_BULLISH") else "MMSM",
                "desc":  "Faz 2: Retail tuzağı kurulyor (EQH/EQL) — bekle",
                "entry_ready": False,
            }
        if in_consol:
            return {"phase": "ORIGINAL_CONSOLIDATION", "model": "NONE",
                    "desc": "Faz 1: Konsolidasyon — hareket bekleniyor", "entry_ready": False}
        if in_hunt:
            return {"phase": "LIQUIDITY_HUNT", "model": "NONE",
                    "desc": "Faz 4: Likidite avı devam ediyor", "entry_ready": False}

        return {"phase": "UNKNOWN", "model": "NONE", "entry_ready": False}

    # ══════════════════════════════════════════════════════════════════════
    # ASIAN RANGE — 19:00-00:00 NY (ICT 2022)
    # High/low of this session = tomorrow's liquidity sweep targets
    # London & NY sessions typically raid Asian high or low first
    # ══════════════════════════════════════════════════════════════════════
    def find_asian_range(self, df: pd.DataFrame) -> dict:
        """
        Asian session 19:00-00:00 NY. High = BSL target, Low = SSL target.
        When price sweeps Asian High → bearish, Asian Low → bullish.
        """
        if len(df) < 12:
            return {}

        df_et = df.copy()
        try:
            df_et.index = pd.to_datetime(df_et.index, utc=True).tz_convert(self._et)
        except Exception:
            return {}

        today = df_et.index[-1].date()
        # Asian range is prior session: 19:00 yesterday to 00:00 today
        asian = df_et[
            (
                (df_et.index.hour >= 19) &
                (df_et.index.date < today)   # yesterday's evening
            ) | (
                (df_et.index.hour == 0) &
                (df_et.index.date == today)  # midnight candle
            )
        ]

        if len(asian) < 3:
            return {}

        asian_high = asian["High"].max()
        asian_low  = asian["Low"].min()
        current    = df["Close"].iloc[-1]
        last3_high = df["High"].iloc[-3:].max()
        last3_low  = df["Low"].iloc[-3:].min()

        swept_high = last3_high > asian_high and current < asian_high
        swept_low  = last3_low  < asian_low  and current > asian_low

        return {
            "high":        asian_high,
            "low":         asian_low,
            "midpoint":    (asian_high + asian_low) / 2,
            "swept_high":  swept_high,
            "swept_low":   swept_low,
            "direction":   ("BEARISH" if swept_high else "BULLISH" if swept_low else "NONE"),
            "desc": (
                f"Asian High Sweep → bear ({round(asian_high,4)})" if swept_high else
                f"Asian Low Sweep → bull ({round(asian_low,4)})"   if swept_low  else
                f"Asian Range: {round(asian_low,4)}-{round(asian_high,4)}"
            ),
        }

    # ══════════════════════════════════════════════════════════════════════
    # STH / ITH / LTH — Swing Hierarchy (ICT Advanced Market Structure)
    # STH = 3-candle swing high (higher than both neighbors)
    # ITH = STH with lower STHs on each side
    # LTH = ITH with lower ITHs on each side
    # ══════════════════════════════════════════════════════════════════════
    def classify_swing_hierarchy(self, df: pd.DataFrame) -> dict:
        """
        Returns labeled swing highs and lows sorted by significance.
        Use LTH/LTL as trend anchors, ITH/ITL as active structure,
        STH/STL as intraday entry zones.
        """
        if len(df) < 15:
            return {"sth": [], "ith": [], "lth": [], "stl": [], "itl": [], "ltl": []}

        highs = df["High"].values
        lows  = df["Low"].values
        n     = len(df)

        # Detect raw STH/STL (3-candle swing)
        sth_idx, stl_idx = [], []
        for i in range(1, n - 1):
            if highs[i] > highs[i-1] and highs[i] > highs[i+1]:
                sth_idx.append(i)
            if lows[i] < lows[i-1] and lows[i] < lows[i+1]:
                stl_idx.append(i)

        # ITH: STH with lower STHs on each side
        ith_idx = []
        for k, i in enumerate(sth_idx):
            left  = [j for j in sth_idx[:k]  if highs[j] < highs[i]]
            right = [j for j in sth_idx[k+1:] if highs[j] < highs[i]]
            if left and right:
                ith_idx.append(i)

        # LTH: ITH with lower ITHs on each side
        lth_idx = []
        for k, i in enumerate(ith_idx):
            left  = [j for j in ith_idx[:k]  if highs[j] < highs[i]]
            right = [j for j in ith_idx[k+1:] if highs[j] < highs[i]]
            if left and right:
                lth_idx.append(i)

        # ITL / LTL (mirror for lows)
        itl_idx = []
        for k, i in enumerate(stl_idx):
            left  = [j for j in stl_idx[:k]  if lows[j] > lows[i]]
            right = [j for j in stl_idx[k+1:] if lows[j] > lows[i]]
            if left and right:
                itl_idx.append(i)

        ltl_idx = []
        for k, i in enumerate(itl_idx):
            left  = [j for j in itl_idx[:k]  if lows[j] > lows[i]]
            right = [j for j in itl_idx[k+1:] if lows[j] > lows[i]]
            if left and right:
                ltl_idx.append(i)

        def to_list(idx_list, arr):
            return [{"index": i, "price": arr[i], "time": df.index[i]} for i in idx_list]

        return {
            "sth": to_list(sth_idx, highs),
            "ith": to_list(ith_idx, highs),
            "lth": to_list(lth_idx, highs),
            "stl": to_list(stl_idx, lows),
            "itl": to_list(itl_idx, lows),
            "ltl": to_list(ltl_idx, lows),
        }

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

        # MTF analiz setleri — BISI/SIBI etiketli FVG (BUG FIX)
        fvgs       = self.find_fvg_classified(df_mtf)
        ifvgs      = self.find_ifvg(df_mtf)
        impl_fvgs  = self.find_implied_fvg(df_mtf)
        rdrbs      = self.find_rdrb(df_mtf)
        obs        = self.find_order_blocks(df_mtf)
        breakers  = self.find_breaker_blocks(df_mtf)
        unicorns  = self.find_unicorn(df_mtf)
        ote       = self.find_ote(df_htf, bias)
        bprs      = self.find_bpr(df_mtf)
        rej_blks  = self.find_rejection_blocks(df_mtf)
        first_fvg = self.find_first_presented_fvg(df_mtf)
        props     = self.find_propulsion_blocks(df_mtf)
        mits      = self.find_mitigation_blocks(df_mtf)
        vacuums   = self.find_vacuum_blocks(df_mtf)
        psych_lvl = self.find_psychological_levels(current)

        # Ek bağlam
        sb_window    = self.is_silver_bullet_window()
        macro_win    = self.is_ict_macro_window()
        judas        = self.detect_judas_swing(df_mtf, bias)
        amd_phase    = self.detect_amd_phase(df_htf)
        q_theory     = self.quarterly_bias()
        mmxm         = self.detect_mmxm_phase(df_htf, bias)
        displacement = self.detect_displacement(df_mtf)
        sess_sweep   = self.detect_session_sweep(df_mtf)
        turtle       = self.detect_turtle_soup(df_mtf)
        crt          = self.detect_crt(df_htf, df_mtf)
        weekly_prof  = self.weekly_profile_bias()
        inducement   = self.detect_inducement(df_mtf, bias)
        venom        = self.detect_venom_setup(df_mtf) if self.symbol in ("NQ=F","ES=F") else {"found": False}

        # Yeni ICT kavramları (v8)
        cisd         = self.detect_cisd(df_mtf, bias)
        mm_phase     = self.detect_mm_model_phase(df_htf, df_mtf, bias)
        asian_range  = self.find_asian_range(df_mtf)
        swing_hier   = self.classify_swing_hierarchy(df_htf)
        midnight_ref  = self.find_midnight_open(df_htf)
        weekly_ref    = self.find_weekly_open(df_htf)
        intraday_prof = self.detect_intraday_profile(df_htf)
        dol           = self.find_draw_on_liquidity(df_daily, df_htf) if df_daily is not None and not df_daily.empty else {}

        # NDOG/NWOG seviyeleri
        opening_gaps = self.find_opening_gaps(df_htf) if len(df_htf) >= 48 else {}

        # CBDR & ADR (2017 mentorship)
        cbdr = self.calculate_cbdr(df_htf)
        adr  = self.calculate_adr(df_daily) if df_daily is not None and not df_daily.empty else {}

        # IPDA
        ipda = {}
        if df_daily is not None and not df_daily.empty:
            ipda = self.ipda_levels(df_daily)

        # SMT divergence (korelasyonlu çift)
        smt = "NONE"
        if df_corr is not None:
            smt = self.detect_smt_divergence(df_mtf, df_corr)

        # ── Cuma / Pazartesi düşük olasılık (Weekly Profile) ─────────────
        low_prob_day = not weekly_prof.get("trade", True)  # Cuma & Pazartesi

        # ── Temel confluence listesi ──────────────────────────────────────
        base = [f"Kill Zone: {kill_zone.upper()}"]
        if macro_win:
            base.append(f"⭐ ICT Macro: {macro_win}")
        if sb_window:
            base.append(f"Silver Bullet: {sb_window}")
        if intraday_prof.get("profile") not in ("UNKNOWN", "UNCLASSIFIED", "FORMING", None):
            base.append(f"Intraday Profil: {intraday_prof['desc']}")
        if judas:
            base.append("Judas Swing onayı")
        if amd_phase in ("MANIPULATION", "DISTRIBUTION"):
            base.append(f"AMD Fazı: {amd_phase}")
        if "ERL_SWEEP" in mmxm:
            base.append(f"MMXM: {mmxm}")
        if smt != "NONE":
            base.append(f"SMT Divergence: {smt}")
        if displacement.get("found"):
            base.append(f"Displacement: {displacement['direction']} "
                        f"(gövde {round(displacement['body']/displacement['atr'],1)}x ATR)")
        if sess_sweep.get("sweep"):
            base.append(f"Session Sweep: {sess_sweep['desc']}")
        if turtle.get("found"):
            base.append(f"Turtle Soup: {turtle['desc']}")
        if crt.get("found"):
            base.append(f"CRT: {crt['desc']}")
        if inducement.get("found"):
            base.append(f"IDM: {inducement['desc']}")
        if venom.get("found"):
            base.append(f"Venom: {venom['desc']}")
        if first_fvg:
            base.append(f"1st FVG ({first_fvg['label']}): {round(first_fvg['bottom'],4)}-{round(first_fvg['top'],4)}")
        # Midnight Open & Weekly Open bağlamı
        if midnight_ref.get("midnight_open"):
            base.append(f"Midnight Open: {round(midnight_ref['midnight_open'],4)} ({midnight_ref['bias']})")
        if midnight_ref.get("judas_dir") and midnight_ref["judas_dir"] != "NONE":
            base.append(f"★ 2022 Judas Sweep: {midnight_ref['judas_dir']} (MR sweep)")
        if weekly_ref.get("weekly_open"):
            base.append(f"Weekly Open: {round(weekly_ref['weekly_open'],4)} ({weekly_ref['bias']})")

        # CISD — erken dönüş sinyali
        if cisd.get("found"):
            base.append(f"CISD: {cisd['desc']}")
        # MMBM/MMSM faz
        if mm_phase.get("phase") == "SMART_MONEY_REVERSAL":
            base.append(f"★ {mm_phase['desc']}")
        elif mm_phase.get("phase") not in ("UNKNOWN", "NONE"):
            base.append(f"MM Model Faz: {mm_phase['desc']}")
        # Asian Range sweep
        if asian_range.get("direction") not in (None, "NONE", ""):
            base.append(f"Asian Range: {asian_range['desc']}")
        # STH/ITH/LTH yakın seviyeler
        lths = swing_hier.get("lth", [])
        ltls = swing_hier.get("ltl", [])
        iths = swing_hier.get("ith", [])
        itls = swing_hier.get("itl", [])
        if lths:
            nearest_lth = min(lths, key=lambda x: abs(x["price"] - current))
            if abs(nearest_lth["price"] - current) / current < 0.005:
                base.append(f"LTH Yakın: {round(nearest_lth['price'],4)}")
        if ltls:
            nearest_ltl = min(ltls, key=lambda x: abs(x["price"] - current))
            if abs(nearest_ltl["price"] - current) / current < 0.005:
                base.append(f"LTL Yakın: {round(nearest_ltl['price'],4)}")
        base.append(f"Hafta: {weekly_prof['day']} ({weekly_prof['bias']})")

        # NDOG seviyeleri yakınsa ekle
        for nd in opening_gaps.get("ndog", [])[:3]:
            if abs(current - nd["midpoint"]) / current < 0.005:
                base.append(f"NDOG CE: {round(nd['midpoint'],4)} ({nd['direction']})")

        # CBDR seviyeleri
        if cbdr:
            for k in ["std1_up","std2_up","std1_dn","std2_dn"]:
                if abs(current - cbdr[k]) / current < 0.004:
                    base.append(f"CBDR {k}: {round(cbdr[k],4)}")

        # ADR hedef projeksiyon
        if adr:
            base.append(f"ADR: {adr['adr']} | Hedef H:{adr['proj_high']} L:{adr['proj_low']}")

        # Psikolojik seviyeler
        for pl in psych_lvl:
            if pl["pct_away"] < 0.3:
                base.append(f"Psik. Seviye: {pl['price']} ({pl['type']}, %{pl['pct_away']} uzakta)")

        q3_warning = q_theory["quarter"] == "Q3"  # Q3 düşük güven

        # IPDA yakın seviyeleri
        for k, v in ipda.items():
            if abs(current - v) / current < 0.003:
                base.append(f"IPDA {k}: {round(v,4)}")

        # DOL — Likidite hedefi
        if dol.get("dol_desc"):
            base.append(f"DOL: {dol['dol_desc']}")
        if dol.get("inside_bar"):
            base.append("Inside Bar: düşük volatilite — kırılış bekle")

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

            # 1b. Venom Bullish (Endeksler) ★★★★★
            if not entry_zone and venom.get("found") and venom.get("direction") == "BULLISH":
                entry_zone = {"bottom": current * 0.999, "top": current * 1.001}
                setup_name, model_name, stars = "Venom Bullish", "UNICORN", 5
                confs.append(f"★ VENOM: {venom['desc']}")

            # 2. Silver Bullet + FVG ★★★★★
            if not entry_zone and sb_window:
                for fvg in reversed(fvgs):
                    if fvg["type"] == "BULLISH_FVG" and fvg["bottom"] <= current <= fvg["top"]:
                        entry_zone, setup_name, model_name, stars = \
                            fvg, f"Silver Bullet ({sb_window})", "SILVER_BULLET", 5
                        confs.append(f"Silver Bullet BISI @ {sb_window}")
                        break

            # 2b. 1st Presented FVG (displacement sonrası) ★★★★★
            if not entry_zone and first_fvg and first_fvg.get("type") == "BULLISH_FVG":
                if first_fvg["bottom"] <= current <= first_fvg["top"]:
                    entry_zone, setup_name, model_name, stars = \
                        first_fvg, "1st Presented BISI", "SILVER_BULLET", 5
                    confs.append(f"1st BISI: displacement sonrası ilk FVG")

            # 3. BPR (Balanced Price Range) ★★★★
            if not entry_zone:
                for bpr in reversed(bprs):
                    if bpr["bottom"] <= current <= bpr["top"]:
                        entry_zone, setup_name, model_name, stars = \
                            bpr, "BPR Bullish", "OTE", 4
                        confs.append(f"BPR: BISI+SIBI çakışma bölgesi")
                        break

            # 4. OTE ★★★★
            if not entry_zone and ote and ote.get("direction") == "BULLISH":
                if ote["bottom"] <= current <= ote["top"]:
                    entry_zone, setup_name, model_name, stars = \
                        ote, "OTE 62-79% Fib", "OTE", 4
                    confs.append(f"OTE: {round(ote['bottom'],4)}-{round(ote['top'],4)} | 70.5%={round(ote['sweet_spot'],4)}")
                    # Use Fibonacci extension as TP
                    if ote.get("tp1_ext"):
                        tp1 = ote["tp1_ext"]
                        confs.append(f"OTE -0.27 ext TP1: {round(tp1,4)}")
                    if ote.get("tp2_ext"):
                        tp2 = ote["tp2_ext"]
                        confs.append(f"OTE -0.62 ext TP2: {round(tp2,4)}")

            # 5. IFVG (Inversion FVG) ★★★
            if not entry_zone:
                for ifvg in reversed(ifvgs):
                    if ifvg["type"] == "BULLISH_IFVG" and ifvg["bottom"] <= current <= ifvg["top"]:
                        entry_zone, setup_name, model_name, stars = \
                            ifvg, "Bullish IFVG", "OB_FVG", 3
                        confs.append("Bullish IFVG (Ters FVG destek)")
                        break

            # 5b. Implied FVG ★★★ (hidden wick-midpoint gap)
            if not entry_zone:
                for imp in reversed(impl_fvgs):
                    if imp["type"] == "BULLISH_IMPLIED_FVG" and imp["bottom"] <= current <= imp["top"]:
                        entry_zone, setup_name, model_name, stars = \
                            imp, "Bullish Implied FVG", "OB_FVG", 3
                        confs.append(f"Bullish Implied FVG (gizli gap): {round(imp['bottom'],4)}-{round(imp['top'],4)}")
                        break

            # 6. Bullish Breaker ★★★
            if not entry_zone:
                for b in reversed(breakers):
                    if b["type"] == "BULLISH_BREAKER" and b["bottom"] <= current <= b["top"]:
                        entry_zone, setup_name, model_name, stars = \
                            b, "Bullish Breaker Block", "OB_FVG", 3
                        confs.append("Bullish Breaker Block")
                        break

            # 7. Rejection Block ★★★
            if not entry_zone:
                for rb in reversed(rej_blks):
                    if rb["type"] == "BULLISH_REJECTION" and rb["bottom"] <= current <= rb["top"]:
                        entry_zone, setup_name, model_name, stars = \
                            rb, f"Bullish Rejection Block (wick {rb['wick_ratio']}x)", "OB_FVG", 3
                        confs.append(f"Rejection Block: {rb['wick_ratio']}x fitil")
                        break

            # 8. Propulsion Block ★★★
            if not entry_zone:
                for p in reversed(props):
                    if p["type"] == "BULLISH_PROPULSION" and p["bottom"] <= current <= p["top"]:
                        entry_zone, setup_name, model_name, stars = \
                            p, p["desc"], "OB_FVG", 3
                        confs.append(f"Propulsion Block: midpoint {round(p['midpoint'],4)}")
                        break

            # 8b. RDRB ★★★ (Redelivered Rebalanced Price Range)
            if not entry_zone:
                for r in reversed(rdrbs):
                    if r["type"] == "BULLISH_RDRB" and r["bottom"] <= current <= r["top"]:
                        entry_zone, setup_name, model_name, stars = \
                            r, "Bullish RDRB", "OB_FVG", 3
                        confs.append(f"RDRB Bullish: rebalans bölgesi {round(r['bottom'],4)}-{round(r['top'],4)}")
                        break

            # 9. FVG (BISI) ★★
            if not entry_zone:
                for fvg in reversed(fvgs):
                    if fvg["type"] == "BULLISH_FVG" and fvg["bottom"] <= current <= fvg["top"]:
                        entry_zone, setup_name, model_name = fvg, f"Bullish BISI", "OB_FVG"
                        confs.append(f"BISI IOFED: {round(fvg.get('iofed',fvg['top']),4)} | CE: {round(fvg['midpoint'],4)}")
                        break

            # 10. Order Block ★★
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

                # NDOG hedef (BUG FIX — artık kullanılıyor)
                ndog_up = sorted([nd["midpoint"] for nd in opening_gaps.get("ndog",[])
                                  if nd["midpoint"] > current and nd["direction"] == "BULLISH"])
                if ndog_up:
                    tp1 = ndog_up[0]
                    confs.append(f"NDOG CE hedef: {round(tp1,4)}")

                # NWOG hedef
                nwog = opening_gaps.get("nwog")
                if nwog and nwog["midpoint"] > current:
                    tp2 = nwog["midpoint"]
                    confs.append(f"NWOG CE hedef: {round(tp2,4)}")

                # CBDR std dev hedefi (Bullish: +2/+3 std)
                if cbdr and cbdr.get("std2_up", 0) > current:
                    tp2 = cbdr["std2_up"]
                    confs.append(f"CBDR +2σ hedef: {round(tp2,4)}")

                # ADR Yüksek projeksiyonu
                if adr and adr.get("proj_high", 0) > current:
                    confs.append(f"ADR Yüksek: {adr['proj_high']}")

                # 2022 model: MR High hedef (Judas sweep sonrası)
                if midnight_ref.get("judas_dir") == "BULLISH" and midnight_ref.get("mr_high", 0) > current:
                    tp1 = midnight_ref["mr_high"]
                    confs.append(f"2022 MR High hedef: {round(tp1,4)}")

                # DOL (Draw on Liquidity) bullish — PDH hedef
                if dol.get("dol_dir") == "BULLISH" and dol.get("pdh", 0) > current:
                    tp1 = dol["pdh"]
                    confs.append(f"DOL Bullish: PDH {round(dol['pdh'],4)} hedef ✓")
                    stars = min(stars + 1, 5)
                elif dol.get("pwh", 0) > current:
                    confs.append(f"PWH hedef: {round(dol['pwh'],4)}")

                # ICT Macro penceresi bonus
                if macro_win:
                    stars = min(stars + 1, 5)
                    confs.append(f"ICT Macro penceresi: {macro_win} ✓")

                # SMT ekstra onay
                if smt == "BULLISH_SMT":
                    stars = min(stars + 1, 5)
                    confs.append("SMT Divergence: Bullish onay ✓")

                # Displacement onayı
                if displacement.get("found") and displacement.get("direction") == "BULLISH":
                    stars = min(stars + 1, 5)
                    confs.append("Displacement Bullish ✓")

                # Session sweep / Turtle Soup bullish onay
                if sess_sweep.get("sweep") and sess_sweep.get("direction") == "BULLISH":
                    stars = min(stars + 1, 5)
                    confs.append(f"Stop Hunt Bullish: {sess_sweep['type']} ✓")
                if turtle.get("found") and turtle.get("direction") == "BULLISH":
                    stars = min(stars + 1, 5)
                    confs.append(f"Turtle Soup Bullish ✓")

                # CRT bullish onay
                if crt.get("found") and crt.get("direction") == "BULLISH":
                    stars = min(stars + 1, 5)
                    tp1 = crt["target"]
                    confs.append(f"CRT Bullish hedef: {round(tp1,4)} ✓")

                # IDM onayı (tuzak sonrası giriş)
                if inducement.get("found") and inducement.get("direction") == "BULLISH":
                    stars = min(stars + 1, 5)
                    confs.append(f"IDM tuzağı sonrası long ✓")

                # Intraday Profile alignment (+1 yıldız)
                if intraday_prof.get("direction") == "BULLISH" and \
                   intraday_prof.get("profile") not in ("UNKNOWN", "UNCLASSIFIED", "FORMING", None):
                    stars = min(stars + 1, 5)
                    confs.append(f"Intraday Profil Bullish: {intraday_prof['profile']} ✓")

                # Midnight Open bullish alignment (+1 yıldız)
                if midnight_ref.get("bias") == "BULLISH":
                    stars = min(stars + 1, 5)
                    confs.append(f"Midnight Open Bullish: fiyat MO üzerinde ✓")
                # 2022 Judas Sweep MR Low → Bullish (+1 yıldız)
                if midnight_ref.get("judas_dir") == "BULLISH":
                    stars = min(stars + 1, 5)
                    confs.append(f"2022 Judas: MR Low sweep → bullish ✓")
                # Weekly Open bias alignment (+1 yıldız)
                if weekly_ref.get("bias") == "BULLISH":
                    stars = min(stars + 1, 5)
                    confs.append(f"Weekly Open Bullish: fiyat WO üzerinde ✓")

                # CISD bullish onay (+1 yıldız — erken dönüş teyidi)
                if cisd.get("found") and cisd.get("direction") == "BULLISH":
                    stars = min(stars + 1, 5)
                    confs.append(f"CISD Bullish ✓ {cisd['desc']}")

                # MMBM Faz 3 onayı (+1 yıldız)
                if mm_phase.get("phase") == "SMART_MONEY_REVERSAL" and \
                   mm_phase.get("model") == "MMBM":
                    stars = min(stars + 1, 5)
                    confs.append(f"MMBM Faz 3: Smart Money Reversal ✓")

                # Asian Low sweep → bullish (+1 yıldız + TP güncelle)
                if asian_range.get("swept_low"):
                    stars = min(stars + 1, 5)
                    confs.append(f"Asian Low Sweep bullish ✓ ({round(asian_range['low'],4)})")
                    if asian_range.get("high", 0) > current:
                        tp2 = asian_range["high"]
                        confs.append(f"Asian Range hedef: {round(tp2,4)}")

                # LRLR — temiz yol bonus (+1 yıldız)
                if tp_list:
                    lrlr = self.classify_liquidity_run(df_htf, tp1, "BULLISH")
                    if lrlr["type"] == "LRLR":
                        stars = min(stars + 1, 5)
                        confs.append(f"LRLR: Temiz yol → TP ({lrlr['obstacles']} engel)")
                    elif lrlr["type"] == "HRLR":
                        confs.append(f"HRLR: {lrlr['obstacles']} engel — haber gününü tercih et")

                # ITH/LTH yakın → güçlü direnç (TP hedefi)
                if iths:
                    ith_targets = [x["price"] for x in iths if x["price"] > current]
                    if ith_targets:
                        nearest_ith_tp = min(ith_targets)
                        if nearest_ith_tp < tp2:
                            tp1 = min(tp1, nearest_ith_tp)
                            confs.append(f"ITH hedef: {round(nearest_ith_tp,4)}")

                # Q3 uyarısı
                if q3_warning:
                    confs.append("⚠️ Q3 — düşük güven sezonu, pozisyon küçük tut")
                    stars = max(stars - 1, 1)

                # Cuma/Pazartesi -1 yıldız (tamamen bloklamak yerine)
                if low_prob_day:
                    confs.append(f"⚠️ {weekly_prof['day']}: {weekly_prof['note']}")
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

            # 1b. Venom Bearish (Endeksler) ★★★★★
            if not entry_zone and venom.get("found") and venom.get("direction") == "BEARISH":
                entry_zone = {"bottom": current * 0.999, "top": current * 1.001}
                setup_name, model_name, stars = "Venom Bearish", "UNICORN", 5
                confs.append(f"★ VENOM: {venom['desc']}")

            # 2. Silver Bullet + FVG ★★★★★
            if not entry_zone and sb_window:
                for fvg in reversed(fvgs):
                    if fvg["type"] == "BEARISH_FVG" and fvg["bottom"] <= current <= fvg["top"]:
                        entry_zone, setup_name, model_name, stars = \
                            fvg, f"Silver Bullet ({sb_window})", "SILVER_BULLET", 5
                        confs.append(f"Silver Bullet SIBI @ {sb_window}")
                        break

            # 2b. 1st Presented FVG ★★★★★
            if not entry_zone and first_fvg and first_fvg.get("type") == "BEARISH_FVG":
                if first_fvg["bottom"] <= current <= first_fvg["top"]:
                    entry_zone, setup_name, model_name, stars = \
                        first_fvg, "1st Presented SIBI", "SILVER_BULLET", 5
                    confs.append(f"1st SIBI: displacement sonrası ilk FVG")

            # 3. BPR ★★★★
            if not entry_zone:
                for bpr in reversed(bprs):
                    if bpr["bottom"] <= current <= bpr["top"]:
                        entry_zone, setup_name, model_name, stars = \
                            bpr, "BPR Bearish", "OTE", 4
                        confs.append(f"BPR: BISI+SIBI çakışma bölgesi")
                        break

            # 4. OTE ★★★★
            if not entry_zone and ote and ote.get("direction") == "BEARISH":
                if ote["bottom"] <= current <= ote["top"]:
                    entry_zone, setup_name, model_name, stars = \
                        ote, "OTE 62-79% Fib", "OTE", 4
                    confs.append(f"OTE: {round(ote['bottom'],4)}-{round(ote['top'],4)} | 70.5%={round(ote['sweet_spot'],4)}")
                    if ote.get("tp1_ext"):
                        tp1 = ote["tp1_ext"]
                        confs.append(f"OTE -0.27 ext TP1: {round(tp1,4)}")
                    if ote.get("tp2_ext"):
                        tp2 = ote["tp2_ext"]
                        confs.append(f"OTE -0.62 ext TP2: {round(tp2,4)}")

            # 5. IFVG (Inversion FVG) ★★★
            if not entry_zone:
                for ifvg in reversed(ifvgs):
                    if ifvg["type"] == "BEARISH_IFVG" and ifvg["bottom"] <= current <= ifvg["top"]:
                        entry_zone, setup_name, model_name, stars = \
                            ifvg, "Bearish IFVG", "OB_FVG", 3
                        confs.append("Bearish IFVG (Ters FVG direnç)")
                        break

            # 5b. Implied FVG ★★★
            if not entry_zone:
                for imp in reversed(impl_fvgs):
                    if imp["type"] == "BEARISH_IMPLIED_FVG" and imp["bottom"] <= current <= imp["top"]:
                        entry_zone, setup_name, model_name, stars = \
                            imp, "Bearish Implied FVG", "OB_FVG", 3
                        confs.append(f"Bearish Implied FVG (gizli gap): {round(imp['bottom'],4)}-{round(imp['top'],4)}")
                        break

            # 6. Bearish Breaker ★★★
            if not entry_zone:
                for b in reversed(breakers):
                    if b["type"] == "BEARISH_BREAKER" and b["bottom"] <= current <= b["top"]:
                        entry_zone, setup_name, model_name, stars = \
                            b, "Bearish Breaker Block", "OB_FVG", 3
                        confs.append("Bearish Breaker Block")
                        break

            # 7. Rejection Block ★★★
            if not entry_zone:
                for rb in reversed(rej_blks):
                    if rb["type"] == "BEARISH_REJECTION" and rb["bottom"] <= current <= rb["top"]:
                        entry_zone, setup_name, model_name, stars = \
                            rb, f"Bearish Rejection Block (wick {rb['wick_ratio']}x)", "OB_FVG", 3
                        confs.append(f"Rejection Block: {rb['wick_ratio']}x fitil")
                        break

            # 8. Propulsion Block ★★★
            if not entry_zone:
                for p in reversed(props):
                    if p["type"] == "BEARISH_PROPULSION" and p["bottom"] <= current <= p["top"]:
                        entry_zone, setup_name, model_name, stars = \
                            p, p["desc"], "OB_FVG", 3
                        confs.append(f"Propulsion Block: midpoint {round(p['midpoint'],4)}")
                        break

            # 8b. RDRB ★★★
            if not entry_zone:
                for r in reversed(rdrbs):
                    if r["type"] == "BEARISH_RDRB" and r["bottom"] <= current <= r["top"]:
                        entry_zone, setup_name, model_name, stars = \
                            r, "Bearish RDRB", "OB_FVG", 3
                        confs.append(f"RDRB Bearish: rebalans bölgesi {round(r['bottom'],4)}-{round(r['top'],4)}")
                        break

            # 9. FVG (SIBI) ★★
            if not entry_zone:
                for fvg in reversed(fvgs):
                    if fvg["type"] == "BEARISH_FVG" and fvg["bottom"] <= current <= fvg["top"]:
                        entry_zone, setup_name, model_name = fvg, "Bearish SIBI", "OB_FVG"
                        confs.append(f"SIBI IOFED: {round(fvg.get('iofed',fvg['bottom']),4)} | CE: {round(fvg['midpoint'],4)}")
                        break

            # 10. Order Block ★★
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

                # NDOG hedef (BUG FIX)
                ndog_dn = sorted([nd["midpoint"] for nd in opening_gaps.get("ndog",[])
                                  if nd["midpoint"] < current and nd["direction"] == "BEARISH"], reverse=True)
                if ndog_dn:
                    tp1 = ndog_dn[0]
                    confs.append(f"NDOG CE hedef: {round(tp1,4)}")

                nwog = opening_gaps.get("nwog")
                if nwog and nwog["midpoint"] < current:
                    tp2 = nwog["midpoint"]
                    confs.append(f"NWOG CE hedef: {round(tp2,4)}")

                # CBDR std dev hedefi (Bearish: -2/-3 std)
                if cbdr and cbdr.get("std2_dn", float("inf")) < current:
                    tp2 = cbdr["std2_dn"]
                    confs.append(f"CBDR -2σ hedef: {round(tp2,4)}")

                # ADR Düşük projeksiyonu
                if adr and adr.get("proj_low", float("inf")) < current:
                    confs.append(f"ADR Düşük: {adr['proj_low']}")

                # 2022 model: MR Low hedef (Judas sweep sonrası)
                if midnight_ref.get("judas_dir") == "BEARISH" and midnight_ref.get("mr_low", float("inf")) < current:
                    tp1 = midnight_ref["mr_low"]
                    confs.append(f"2022 MR Low hedef: {round(tp1,4)}")

                # DOL (Draw on Liquidity) bearish — PDL hedef
                if dol.get("dol_dir") == "BEARISH" and dol.get("pdl", float("inf")) < current:
                    tp1 = dol["pdl"]
                    confs.append(f"DOL Bearish: PDL {round(dol['pdl'],4)} hedef ✓")
                    stars = min(stars + 1, 5)
                elif dol.get("pwl", float("inf")) < current:
                    confs.append(f"PWL hedef: {round(dol['pwl'],4)}")

                # ICT Macro penceresi bonus
                if macro_win:
                    stars = min(stars + 1, 5)
                    confs.append(f"ICT Macro penceresi: {macro_win} ✓")

                if smt == "BEARISH_SMT":
                    stars = min(stars + 1, 5)
                    confs.append("SMT Divergence: Bearish onay ✓")

                if displacement.get("found") and displacement.get("direction") == "BEARISH":
                    stars = min(stars + 1, 5)
                    confs.append("Displacement Bearish ✓")

                if sess_sweep.get("sweep") and sess_sweep.get("direction") == "BEARISH":
                    stars = min(stars + 1, 5)
                    confs.append(f"Stop Hunt Bearish: {sess_sweep['type']} ✓")
                if turtle.get("found") and turtle.get("direction") == "BEARISH":
                    stars = min(stars + 1, 5)
                    confs.append(f"Turtle Soup Bearish ✓")

                if crt.get("found") and crt.get("direction") == "BEARISH":
                    stars = min(stars + 1, 5)
                    tp1 = crt["target"]
                    confs.append(f"CRT Bearish hedef: {round(tp1,4)} ✓")

                if inducement.get("found") and inducement.get("direction") == "BEARISH":
                    stars = min(stars + 1, 5)
                    confs.append(f"IDM tuzağı sonrası short ✓")

                # Intraday Profile alignment (+1 yıldız)
                if intraday_prof.get("direction") == "BEARISH" and \
                   intraday_prof.get("profile") not in ("UNKNOWN", "UNCLASSIFIED", "FORMING", None):
                    stars = min(stars + 1, 5)
                    confs.append(f"Intraday Profil Bearish: {intraday_prof['profile']} ✓")

                # Midnight Open bearish alignment (+1 yıldız)
                if midnight_ref.get("bias") == "BEARISH":
                    stars = min(stars + 1, 5)
                    confs.append(f"Midnight Open Bearish: fiyat MO altında ✓")
                # 2022 Judas Sweep MR High → Bearish (+1 yıldız)
                if midnight_ref.get("judas_dir") == "BEARISH":
                    stars = min(stars + 1, 5)
                    confs.append(f"2022 Judas: MR High sweep → bearish ✓")
                # Weekly Open bias alignment (+1 yıldız)
                if weekly_ref.get("bias") == "BEARISH":
                    stars = min(stars + 1, 5)
                    confs.append(f"Weekly Open Bearish: fiyat WO altında ✓")

                # CISD bearish onay (+1 yıldız)
                if cisd.get("found") and cisd.get("direction") == "BEARISH":
                    stars = min(stars + 1, 5)
                    confs.append(f"CISD Bearish ✓ {cisd['desc']}")

                # MMSM Faz 3 onayı (+1 yıldız)
                if mm_phase.get("phase") == "SMART_MONEY_REVERSAL" and \
                   mm_phase.get("model") == "MMSM":
                    stars = min(stars + 1, 5)
                    confs.append(f"MMSM Faz 3: Smart Money Reversal ✓")

                # Asian High sweep → bearish (+1 yıldız + TP güncelle)
                if asian_range.get("swept_high"):
                    stars = min(stars + 1, 5)
                    confs.append(f"Asian High Sweep bearish ✓ ({round(asian_range['high'],4)})")
                    if asian_range.get("low", float("inf")) < current:
                        tp2 = asian_range["low"]
                        confs.append(f"Asian Range hedef: {round(tp2,4)}")

                # LRLR — temiz yol bonus (+1 yıldız)
                if tp_list:
                    lrlr = self.classify_liquidity_run(df_htf, tp1, "BEARISH")
                    if lrlr["type"] == "LRLR":
                        stars = min(stars + 1, 5)
                        confs.append(f"LRLR: Temiz yol → TP ({lrlr['obstacles']} engel)")
                    elif lrlr["type"] == "HRLR":
                        confs.append(f"HRLR: {lrlr['obstacles']} engel — haber gününü tercih et")

                # ITL/LTL yakın → güçlü destek (TP hedefi)
                if itls:
                    itl_targets = [x["price"] for x in itls if x["price"] < current]
                    if itl_targets:
                        nearest_itl_tp = max(itl_targets)
                        if nearest_itl_tp > tp2:
                            tp1 = max(tp1, nearest_itl_tp)
                            confs.append(f"ITL hedef: {round(nearest_itl_tp,4)}")

                if q3_warning:
                    confs.append("⚠️ Q3 — düşük güven sezonu, pozisyon küçük tut")
                    stars = max(stars - 1, 1)

                if low_prob_day:
                    confs.append(f"⚠️ {weekly_prof['day']}: {weekly_prof['note']}")
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
