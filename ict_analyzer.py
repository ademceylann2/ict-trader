"""
ICT Analyzer v5 — Inner Circle Trader TAM metodoloji (YouTube 2024 Mentorship).

Kavramlar:
  Temel: BOS/CHOCH/MSS, FVG (BISI/SIBI), IFVG, Order Blocks, Breaker Blocks
  Modeller: Unicorn, OTE (62-79%), Silver Bullet, MMXM, AMD/Power of 3
  Zaman: Kill Zones, ICT Macros (8 pencere), NDOG, NWOG
  Gelişmiş: SMT Divergence, IPDA, Judas Swing, Quarterly Theory,
             Displacement, Session Sweep, Turtle Soup, CRT,
             Weekly Profiles, Inducement (IDM), Consequent Encroachment
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
    # BISI / SIBI — FVG yön sınıflandırması (ICT 2024)
    # BISI = Up-closed FVG (bullish), SIBI = Down-closed FVG (bearish)
    # ══════════════════════════════════════════════════════════════════════
    def find_fvg_classified(self, df: pd.DataFrame, min_size_pct: float = 0.0005) -> list:
        """find_fvg'yi BISI/SIBI etiketiyle zenginleştirir."""
        fvgs = self.find_fvg(df, min_size_pct)
        for f in fvgs:
            f["label"] = "BISI" if f["type"] == "BULLISH_FVG" else "SIBI"
            f["consequent_encroachment"] = f["midpoint"]
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
    # SILVER BULLET — 3AM / 10AM / 2PM NY pencereleri (1 saatlik)
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

        # MTF analiz setleri — BISI/SIBI etiketli FVG (BUG FIX)
        fvgs      = self.find_fvg_classified(df_mtf)
        ifvgs     = self.find_ifvg(df_mtf)
        obs       = self.find_order_blocks(df_mtf)
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
                    confs.append(f"OTE: {round(ote['bottom'],4)}-{round(ote['top'],4)}")

            # 5. IFVG ★★★
            if not entry_zone:
                for ifvg in reversed(ifvgs):
                    if ifvg["type"] == "BULLISH_IFVG" and ifvg["bottom"] <= current <= ifvg["top"]:
                        entry_zone, setup_name, model_name, stars = \
                            ifvg, "Bullish IFVG", "OB_FVG", 3
                        confs.append("Bullish IFVG (Ters FVG destek)")
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

            # 9. FVG (BISI) ★★
            if not entry_zone:
                for fvg in reversed(fvgs):
                    if fvg["type"] == "BULLISH_FVG" and fvg["bottom"] <= current <= fvg["top"]:
                        entry_zone, setup_name, model_name = fvg, f"Bullish BISI", "OB_FVG"
                        confs.append(f"BISI CE: {round(fvg['midpoint'],4)}")
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
                    confs.append(f"OTE: {round(ote['bottom'],4)}-{round(ote['top'],4)}")

            # 5. IFVG ★★★
            if not entry_zone:
                for ifvg in reversed(ifvgs):
                    if ifvg["type"] == "BEARISH_IFVG" and ifvg["bottom"] <= current <= ifvg["top"]:
                        entry_zone, setup_name, model_name, stars = \
                            ifvg, "Bearish IFVG", "OB_FVG", 3
                        confs.append("Bearish IFVG (Ters FVG direnç)")
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

            # 9. FVG (SIBI) ★★
            if not entry_zone:
                for fvg in reversed(fvgs):
                    if fvg["type"] == "BEARISH_FVG" and fvg["bottom"] <= current <= fvg["top"]:
                        entry_zone, setup_name, model_name = fvg, "Bearish SIBI", "OB_FVG"
                        confs.append(f"SIBI CE: {round(fvg['midpoint'],4)}")
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
