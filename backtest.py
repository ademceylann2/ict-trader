"""
ICT Trader — Backtest Motoru
Geçmiş veri üzerinde tüm ICT kurulumlarını test eder.
"""

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from ict_analyzer import ICTAnalyzer


# ── Backtest parametreleri ────────────────────────────────────────────────────
SYMBOLS = {
    "EURUSD=X": "GBPUSD=X",
    "GBPUSD=X": "EURUSD=X",
    "GC=F":     None,
    "BTC-USD":  "ETH-USD",
    "ES=F":     "NQ=F",
    "NQ=F":     "ES=F",
}
LOOKBACK_DAYS  = 60    # Kaç günlük geçmiş taransın
SCAN_INTERVAL  = 15    # Dakika cinsinden tarama aralığı (MTF)
MIN_RR         = 2.0   # Minimum R:R


def load_data(symbol, corr_sym=None):
    tf_map = {"1h": "10d", "15m": "59d", "1d": "60d"}
    dfs = {}
    for tf, period in tf_map.items():
        df = yf.Ticker(symbol).history(period=period, interval=tf)
        df.index = pd.to_datetime(df.index, utc=True)
        dfs[tf] = df[["Open","High","Low","Close","Volume"]]

    df_corr = None
    if corr_sym:
        df_corr = yf.Ticker(corr_sym).history(period="59d", interval="15m")
        df_corr.index = pd.to_datetime(df_corr.index, utc=True)
        df_corr = df_corr[["Open","High","Low","Close","Volume"]]

    return dfs, df_corr


def simulate_trade(df_future: pd.DataFrame, direction: str,
                   entry: float, sl: float, tp1: float) -> dict:
    """
    Sinyalden sonraki mumları kontrol et: SL mi TP mi önce geldi?
    """
    for i, row in df_future.iterrows():
        if direction == "LONG":
            if row["Low"] <= sl:
                return {"result": "LOSS", "exit": sl, "candles": len(df_future.loc[:i])}
            if row["High"] >= tp1:
                return {"result": "WIN",  "exit": tp1, "candles": len(df_future.loc[:i])}
        else:
            if row["High"] >= sl:
                return {"result": "LOSS", "exit": sl, "candles": len(df_future.loc[:i])}
            if row["Low"] <= tp1:
                return {"result": "WIN",  "exit": tp1, "candles": len(df_future.loc[:i])}
    return {"result": "OPEN", "exit": None, "candles": len(df_future)}


def is_kill_zone(dt) -> str:
    h = dt.hour
    if 0 <= h < 3:   return "asia"
    if 7 <= h < 10:  return "london"
    if 12 <= h < 15: return "new_york"
    if 19 <= h < 20: return "ny_close"
    return ""


def backtest_symbol(symbol: str, corr_sym=None) -> pd.DataFrame:
    print(f"\n{'─'*50}")
    print(f"  Backtest: {symbol}")
    print(f"{'─'*50}")

    dfs, df_corr = load_data(symbol, corr_sym)
    df_15m = dfs["15m"]
    df_1h  = dfs["1h"]
    df_1d  = dfs["1d"]

    analyzer = ICTAnalyzer(symbol)
    results  = []

    # MTF mumlarında ileri kaydıran pencere
    step = SCAN_INTERVAL  # dakika
    indices = df_15m.index

    for idx_pos in range(100, len(indices) - 20):
        ts  = indices[idx_pos]
        kz  = is_kill_zone(ts)
        if not kz:
            continue

        # O ana kadar olan veri dilimleri
        df_htf_slice = df_1h[df_1h.index <= ts].tail(200)
        df_mtf_slice = df_15m[df_15m.index <= ts].tail(200)
        df_d_slice   = df_1d[df_1d.index <= ts].tail(90)
        df_corr_sl   = None
        if df_corr is not None:
            df_corr_sl = df_corr[df_corr.index <= ts].tail(200)

        if len(df_htf_slice) < 30 or len(df_mtf_slice) < 30:
            continue

        try:
            sig = analyzer.generate_signal(
                df_htf_slice, df_mtf_slice, kz, news_clear=True,
                df_daily=df_d_slice if not df_d_slice.empty else None,
                df_corr=df_corr_sl,
            )
        except Exception as e:
            continue

        if sig is None:
            continue

        # Çift sinyal önleme (aynı yön + benzer entry)
        if results:
            last = results[-1]
            if last["direction"] == sig.direction and \
               abs(last["entry"] - sig.entry) / sig.entry < 0.002:
                continue

        # Sinyalden sonraki mumlar üzerinde simüle et
        df_future = df_15m[df_15m.index > ts].head(96)  # 96 x 15min = 24 saat
        outcome   = simulate_trade(df_future, sig.direction,
                                   sig.entry, sig.sl, sig.tp1)

        results.append({
            "time":       ts,
            "symbol":     symbol,
            "direction":  sig.direction,
            "model":      sig.model,
            "setup":      sig.setup,
            "kill_zone":  kz,
            "confidence": sig.confidence,
            "entry":      sig.entry,
            "sl":         sig.sl,
            "tp1":        sig.tp1,
            "rr":         sig.rr,
            "result":     outcome["result"],
            "exit":       outcome["exit"],
            "candles":    outcome["candles"],
        })

        r = outcome["result"]
        emoji = "✅" if r=="WIN" else ("❌" if r=="LOSS" else "⏳")
        print(f"  {emoji} {ts.strftime('%m/%d %H:%M')} | {sig.direction:5s} | "
              f"{sig.model:12s} | {kz:9s} | ★{sig.confidence} | R:R {sig.rr} | {r}")

    return pd.DataFrame(results)


def print_report(df: pd.DataFrame, symbol: str):
    if df.empty:
        print(f"  [{symbol}] Sinyal üretilemedi.")
        return

    closed = df[df["result"].isin(["WIN","LOSS"])]
    if closed.empty:
        print(f"  [{symbol}] Kapanmış işlem yok.")
        return

    total  = len(closed)
    wins   = (closed["result"] == "WIN").sum()
    losses = (closed["result"] == "LOSS").sum()
    wr     = wins / total * 100

    print(f"\n  ── {symbol} SONUÇLAR ──")
    print(f"  Toplam işlem : {total}")
    print(f"  Kazanan      : {wins}  ({wr:.1f}%)")
    print(f"  Kaybeden     : {losses}")

    # Model bazında kırılım
    print(f"\n  Model bazında:")
    for model in closed["model"].unique():
        sub = closed[closed["model"] == model]
        w   = (sub["result"]=="WIN").sum()
        t   = len(sub)
        print(f"    {model:15s}: {w}/{t} = {w/t*100:.0f}% win rate")

    # Kill Zone bazında
    print(f"\n  Kill Zone bazında:")
    for kz in closed["kill_zone"].unique():
        sub = closed[closed["kill_zone"] == kz]
        w   = (sub["result"]=="WIN").sum()
        t   = len(sub)
        print(f"    {kz:12s}: {w}/{t} = {w/t*100:.0f}% win rate")

    # Güven puanı bazında
    print(f"\n  Güven puanı bazında:")
    for stars in sorted(closed["confidence"].unique()):
        sub = closed[closed["confidence"] == stars]
        w   = (sub["result"]=="WIN").sum()
        t   = len(sub)
        print(f"    ★{stars}: {w}/{t} = {w/t*100:.0f}% win rate")


def main():
    print("=" * 55)
    print("  ICT TRADER — BACKTEST MOTORU")
    print(f"  Dönem: Son {LOOKBACK_DAYS} gün | Aralik: {SCAN_INTERVAL}dk")
    print("=" * 55)

    all_results = []

    for symbol, corr_sym in SYMBOLS.items():
        try:
            df = backtest_symbol(symbol, corr_sym)
            if not df.empty:
                all_results.append(df)
                print_report(df, symbol)
        except Exception as e:
            print(f"  [{symbol}] Hata: {e}")

    if not all_results:
        print("\nSonuç yok.")
        return

    combined = pd.concat(all_results, ignore_index=True)
    closed   = combined[combined["result"].isin(["WIN","LOSS"])]

    print("\n" + "="*55)
    print("  GENEL ÖZET")
    print("="*55)

    if not closed.empty:
        total  = len(closed)
        wins   = (closed["result"]=="WIN").sum()
        wr     = wins / total * 100
        print(f"  Toplam işlem : {total}")
        print(f"  Kazanan      : {wins} ({wr:.1f}%)")
        print(f"  Kaybeden     : {total-wins}")
        avg_rr = closed[closed["result"]=="WIN"]["rr"].mean()
        print(f"  Ortalama R:R : {avg_rr:.2f}")

        print(f"\n  Model win rate özeti:")
        for model in closed["model"].unique():
            sub = closed[closed["model"]==model]
            w   = (sub["result"]=="WIN").sum()
            t   = len(sub)
            print(f"    {model:15s}: {w/t*100:.0f}% ({w}/{t})")

        print(f"\n  ★ Güven puanı win rate:")
        for stars in sorted(closed["confidence"].unique()):
            sub = closed[closed["confidence"]==stars]
            w   = (sub["result"]=="WIN").sum()
            t   = len(sub)
            print(f"    ★{stars}: {w/t*100:.0f}% ({w}/{t})")

    # CSV kaydet
    combined.to_csv("backtest_results.csv", index=False)
    print(f"\n  Detaylı sonuçlar: backtest_results.csv")
    print("="*55)


if __name__ == "__main__":
    main()
