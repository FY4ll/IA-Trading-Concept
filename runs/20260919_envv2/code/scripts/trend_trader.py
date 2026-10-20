"""
TRADER DE TENDANCE (07/10/2026) -- recherche, lecture seule. Le trader humain discipliné : sens donné par la
tendance de fond (journalier), achat ET vente, risque connu avant d'entrer (stop sur la structure / l'ATR),
gains qu'on laisse courir (stop suiveur), une position par marché, frais inclus. Décision à la clôture du jour,
exécution à l'ouverture suivante ; un stop touché pendant la journée sort au stop (ou à l'ouverture si gap).

  breakout   cassure 55 jours (plus haut/bas des 55 derniers jours), stop 2 ATR20, sortie sur le plus bas/haut
             des 20 derniers jours (le stop ne fait que suivre)
  pullback   tendance (SMA50 vs SMA200 et prix du bon côté de la SMA50), repli SOUS l'EMA20 dans les 5 derniers
             jours puis clôture de retour au-dessus -> entrée ; stop sous le creux des 10 jours (1 à 4 ATR) ;
             stop suiveur 3 ATR sous le plus haut de clôture ; sortie si la tendance s'inverse

Développement 2010-2018, vérification 2019 -> 2023-04. La lockbox (2023-05 ->) n'est PAS regardée ici.
    python scripts/trend_trader.py        (cwd = code/)  -> reports/trend_trader.md
"""
import os, sys, time
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
os.chdir(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import numpy as np, pandas as pd

D = "C:/Users/utilisateur/Documents/Test_IA/data"
DEV = (pd.Timestamp("2010-01-01"), pd.Timestamp("2019-01-01"))
VAL = (pd.Timestamp("2019-01-01"), pd.Timestamp("2023-05-01"))
END = pd.Timestamp("2023-05-01")          # rien au-delà n'est chargé : lockbox intacte
# frais aller-retour en fraction du prix (spread + glissement, prudents)
COST = {"OR": 2e-4, "EURUSD": 1.2e-4, "GBPUSD": 1.5e-4, "USDJPY": 1.2e-4, "US500": 1.5e-4, "ARGENT": 6e-4}


def daily_from_csv(path, sep=None):
    from src.data_loader import load_kaggle_ohlcv_csv
    df = load_kaggle_ohlcv_csv(path)
    df["time"] = pd.to_datetime(df["time"])
    return df.set_index("time").sort_index()[["open", "high", "low", "close"]]


def daily_from_m15(path):
    df = pd.read_csv(path, parse_dates=["time"]).set_index("time").sort_index()
    o = df.resample("1D").agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
    return o


def markets():
    m = {"OR": [daily_from_csv(f"{D}/kaggle_gold/XAU_1d_data.csv")]}
    for sym, kag, duk in (("EURUSD", "kaggle_eurusd/EURUSD_d1_data.csv", "fx_intraday/EURUSD_M15.csv"),
                          ("GBPUSD", "kaggle_gbpusd/GBPUSD_d1_data.csv", None),
                          ("USDJPY", "kaggle_usdjpy/USDJPY_d1_data.csv", "fx_intraday/USDJPY_M15.csv")):
        segs = [daily_from_csv(f"{D}/{kag}")]
        if duk:                                  # Dukascopy prend le relais après la fin de l'historique Kaggle
            dk = daily_from_m15(f"{D}/{duk}")
            segs.append(dk[dk.index > segs[0].index.max()])
        m[sym] = segs
    m["US500"] = [daily_from_m15(f"{D}/fx_intraday/USA500IDXUSD_M15.csv")]
    return {k: [s[s.index < END] for s in v if len(s[s.index < END]) > 260] for k, v in m.items()}


def atr(df, n=20):
    c = df["close"]
    tr = pd.concat([df["high"] - df["low"], (df["high"] - c.shift()).abs(), (df["low"] - c.shift()).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / n, adjust=False).mean()


def simulate(df, system, cost_frac):
    o, h, l, c = (df[k].to_numpy(float) for k in ("open", "high", "low", "close"))
    a = atr(df).to_numpy()
    n = len(df)
    hi55 = df["high"].rolling(55).max().shift(1).to_numpy(); lo55 = df["low"].rolling(55).min().shift(1).to_numpy()
    hi20 = df["high"].rolling(20).max().shift(1).to_numpy(); lo20 = df["low"].rolling(20).min().shift(1).to_numpy()
    sma50 = df["close"].rolling(50).mean().to_numpy(); sma200 = df["close"].rolling(200).mean().to_numpy()
    ema20 = df["close"].ewm(span=20, adjust=False).mean().to_numpy()
    lo10 = df["low"].rolling(10).min().to_numpy(); hi10 = df["high"].rolling(10).max().to_numpy()
    below5 = pd.Series(c < ema20).rolling(5).max().fillna(0).to_numpy().astype(bool)
    above5 = pd.Series(c > ema20).rolling(5).max().fillna(0).to_numpy().astype(bool)
    trades, pos = [], None
    for t in range(201, n - 1):
        if pos is not None:                       # --- gestion (stop intrajournalier, puis règles de sortie à la clôture)
            d = pos["d"]
            if (l[t] <= pos["sl"]) if d > 0 else (h[t] >= pos["sl"]):
                px = min(o[t], pos["sl"]) if d > 0 else max(o[t], pos["sl"])
                pos["exit"], pos["why"] = px, "stop"
            else:
                pos["best"] = max(pos["best"], c[t]) if d > 0 else min(pos["best"], c[t])
                if system == "breakout":
                    trail = lo20[t] if d > 0 else hi20[t]
                    exit_now = (c[t] < trail) if d > 0 else (c[t] > trail)
                else:
                    trail = pos["best"] - d * 3 * a[t]
                    pos["sl"] = max(pos["sl"], trail) if d > 0 else min(pos["sl"], trail)
                    exit_now = (sma50[t] < sma200[t]) if d > 0 else (sma50[t] > sma200[t])
                if exit_now:
                    pos["exit"], pos["why"] = o[t + 1], "règle de sortie"
            if "exit" in pos:
                R = (pos["exit"] - pos["entry"]) * pos["d"] / pos["risk"] - cost_frac * pos["entry"] / pos["risk"]
                trades.append({"entry_time": df.index[pos["t"]], "exit_time": df.index[t], "dir": pos["d"], "R": R,
                               "why": pos["why"], "risk_atr": pos["risk"] / a[pos["t"]]})
                pos = None
            continue
        if not np.isfinite(sma200[t]) or not np.isfinite(a[t]) or a[t] <= 0:
            continue
        d = 0
        if system == "breakout":
            d = 1 if c[t] > hi55[t] else (-1 if c[t] < lo55[t] else 0)
            stop_dist = 2 * a[t]
        else:
            up = sma50[t] > sma200[t] and c[t] > sma50[t]
            dn = sma50[t] < sma200[t] and c[t] < sma50[t]
            if up and below5[t - 1] and c[t] > ema20[t] and c[t - 1] <= ema20[t - 1]:
                d = 1
            elif dn and above5[t - 1] and c[t] < ema20[t] and c[t - 1] >= ema20[t - 1]:
                d = -1
            stop_dist = (c[t] - lo10[t] + 0.5 * a[t]) if d > 0 else (hi10[t] - c[t] + 0.5 * a[t])
            stop_dist = float(np.clip(stop_dist, 1 * a[t], 4 * a[t]))
        if d:
            entry = o[t + 1]
            sl = entry - d * stop_dist
            pos = {"t": t + 1, "d": d, "entry": entry, "sl": sl, "risk": stop_dist, "best": entry}
    return pd.DataFrame(trades)


def stats(R):
    R = np.asarray(R, float)
    if len(R) == 0:
        return {"n": 0}
    w, lo = R[R > 0], R[R <= 0]
    sd = R.std(ddof=1) if len(R) > 1 else 0
    cum = np.cumsum(R)
    return {"n": len(R), "win": float((R > 0).mean()), "avg": float(R.mean()),
            "pf": float(w.sum() / -lo.sum()) if lo.sum() < 0 else None,
            "t": float(R.mean() / (sd / np.sqrt(len(R)))) if sd > 0 else 0.0,
            "dd": float((cum - np.maximum.accumulate(np.r_[0, cum])[1:]).min()), "total": float(R.sum()),
            "avg_win": float(w.mean()) if len(w) else 0.0}


def fmt(s):
    if not s.get("n"):
        return "0 trade"
    pf = f"{s['pf']:.2f}" if s.get("pf") else "n/a"
    return (f"{s['n']:4d} trades, gain {s['win']:.0%}, gain moyen gagnant {s['avg_win']:+.2f}R, {s['avg']:+.3f}R/trade, "
            f"PF {pf}, total {s['total']:+.1f}R, pire série {s['dd']:.1f}R, t={s['t']:+.1f}")


def main():
    t0 = time.time()
    mk = markets()
    L = [f"# Trader de tendance ({time.strftime('%Y-%m-%d %H:%M')})", "",
         "Journalier, achat et vente, frais inclus, entrée à l'ouverture suivante. Lockbox non regardée.", ""]
    for system in ("breakout", "pullback"):
        L.append(f"## Système : {system}")
        allt = []
        for sym, segs in mk.items():
            ts = [simulate(s, system, COST[sym]) for s in segs]
            t = pd.concat([x for x in ts if len(x)], ignore_index=True) if any(len(x) for x in ts) else pd.DataFrame()
            if not len(t):
                continue
            t["market"] = sym
            allt.append(t)
            for pname, (a, b) in (("2010-2018", DEV), ("2019-2023/04", VAL)):
                m = (t["entry_time"] >= a) & (t["entry_time"] < b)
                if m.sum():
                    L.append(f"- {sym:7s} {pname} : {fmt(stats(t.loc[m, 'R']))}")
        T = pd.concat(allt, ignore_index=True)
        for pname, (a, b) in (("2010-2018", DEV), ("2019-2023/04", VAL)):
            m = (T["entry_time"] >= a) & (T["entry_time"] < b)
            L.append(f"- **TOUS MARCHÉS {pname}** : {fmt(stats(T.loc[m, 'R']))}")
        for side, dd in (("achats", 1), ("ventes", -1)):
            L.append(f"- {side} (2010-2023/04) : {fmt(stats(T.loc[T['dir'] == dd, 'R']))}")
        L.append("")
        print("\n".join(L[-20:]), flush=True)
    os.makedirs("reports", exist_ok=True)
    open("reports/trend_trader.md", "w", encoding="utf-8").write("\n".join(L) + "\n")
    print(f"terminé en {time.time() - t0:.0f}s -> reports/trend_trader.md")


if __name__ == "__main__":
    main()
