"""
TEST D'INFORMATION (07/10/2026) -- quelles sources contiennent VRAIMENT de l'information sur les mouvements futurs
de l'or ? Lecture seule. Pour chaque signal connu à la clôture du jour t : corrélation de rang (Spearman) avec le
rendement de l'or de t à t+h (h = 1, 5, 20 jours), sur des dates non chevauchantes (une tous les h jours, pour
des statistiques honnêtes). Développement 2010-2018, vérification 2019 -> 2023-04 ; la lockbox n'est pas regardée.

Sources : momentum de l'or (référence), argent, ratio or/argent, dollar australien, franc suisse, Dow Jones, DAX,
bitcoin (MT5) ; taux réels, dollar large, VIX, inflation anticipée, volatilité implicite de l'or (FRED) ;
positionnement des gros spéculateurs sur l'or (rapport CFTC, publié le vendredi pour le mardi).

    python scripts/info_test.py        (cwd = code/)  -> reports/info_test.md
"""
import io, os, sys, time, zipfile
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
os.chdir(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import numpy as np, pandas as pd, yaml
from scipy.stats import spearmanr

D = "C:/Users/utilisateur/Documents/Test_IA/data"
COT_DIR = os.path.join(D, "cot")
DEV = (pd.Timestamp("2010-01-01"), pd.Timestamp("2019-01-01"))
VAL = (pd.Timestamp("2019-01-01"), pd.Timestamp("2023-05-01"))
END = pd.Timestamp("2023-05-01")
HS = (1, 5, 20)


def gold_daily():
    from src.data_loader import load_kaggle_ohlcv_csv
    g = load_kaggle_ohlcv_csv(f"{D}/kaggle_gold/XAU_1d_data.csv")
    g["time"] = pd.to_datetime(g["time"]).dt.normalize()
    return g.set_index("time")["close"].sort_index()


def mt5_daily(symbols):
    import MetaTrader5 as mt5
    mt5.initialize(path="C:/Program Files/MetaTrader 5/terminal64.exe")
    out = {}
    for s in symbols:
        r = mt5.copy_rates_from_pos(s, mt5.TIMEFRAME_D1, 0, 6000)
        if r is not None and len(r):
            df = pd.DataFrame(r)
            out[s] = pd.Series(df["close"].to_numpy(float), index=pd.to_datetime(df["time"], unit="s").dt.normalize())
    return out


def cot_gold():
    """Positionnement 'managed money' (gros spéculateurs) sur l'or COMEX, rapports désagrégés 2010 -> 2023."""
    os.makedirs(COT_DIR, exist_ok=True)
    import requests
    frames = []
    files = [(f"fut_disagg_{y}.zip", f"fut_disagg_txt_{y}.zip") for y in range(2010, 2024)]
    hdr = {"User-Agent": "Mozilla/5.0"}
    for local, remote in files:
        p = os.path.join(COT_DIR, local)
        if not os.path.exists(p):
            r = requests.get(f"https://www.cftc.gov/files/dea/history/{remote}", timeout=120, headers=hdr)
            r.raise_for_status()
            open(p, "wb").write(r.content)
        with zipfile.ZipFile(p) as z:
            df = pd.read_csv(io.BytesIO(z.read(z.namelist()[0])), low_memory=False)
        g = df[df["Market_and_Exchange_Names"].str.upper().str.startswith("GOLD - COMMODITY EXCHANGE")]
        frames.append(g)
    c = pd.concat(frames)
    date_col = [x for x in c.columns if x.startswith("Report_Date_as_YYYY")][0]
    c["date"] = pd.to_datetime(c[date_col])
    c = c.drop_duplicates("date").set_index("date").sort_index()
    oi = c["Open_Interest_All"].astype(float)
    mm_net = (c["M_Money_Positions_Long_All"].astype(float) - c["M_Money_Positions_Short_All"].astype(float)) / oi
    pm_net = (c["Prod_Merc_Positions_Long_All"].astype(float) - c["Prod_Merc_Positions_Short_All"].astype(float)) / oi
    # rapport du mardi publié le vendredi -> utilisable à partir du lundi suivant (décalage 6 jours)
    out = pd.DataFrame({"cot_mm_net": mm_net, "cot_prod_net": pm_net, "cot_oi_chg4": oi.pct_change(4)})
    out.index = out.index + pd.Timedelta(days=6)
    return out


def zscore(s, n=252):
    return (s - s.rolling(n, min_periods=n // 2).mean()) / (s.rolling(n, min_periods=n // 2).std() + 1e-12)


def main():
    t0 = time.time()
    cfg = yaml.safe_load(open("../run_config_A.yaml", encoding="utf-8"))
    gold = gold_daily()
    gold = gold[gold.index < END + pd.Timedelta(days=40)]
    days = gold.index
    sig = {}
    # référence : momentum de l'or lui-même
    for n in (5, 20, 60, 120):
        sig[f"or : rendement {n} j"] = gold.pct_change(n)
    sig["or : écart à la moyenne 200 j"] = gold / gold.rolling(200).mean() - 1
    # marchés MT5
    m = mt5_daily(["XAGUSD", "AUDUSD", "USDCHF", "US30_Z6", "GER40_Z6", "BTCUSD", "USDJPY", "EURUSD"])
    names = {"XAGUSD": "argent", "AUDUSD": "dollar australien", "USDCHF": "dollar/franc suisse", "US30_Z6": "Dow Jones",
             "GER40_Z6": "DAX", "BTCUSD": "bitcoin", "USDJPY": "dollar/yen", "EURUSD": "euro/dollar"}
    for s, ser in m.items():
        ser = ser[~ser.index.duplicated()].reindex(days).ffill()
        for n in (5, 20):
            sig[f"{names[s]} : rendement {n} j"] = ser.pct_change(n)
    if "XAGUSD" in m:
        ratio = gold / m["XAGUSD"][~m["XAGUSD"].index.duplicated()].reindex(days).ffill()
        sig["ratio or/argent (z 1 an)"] = zscore(ratio)
    # FRED
    try:
        from src.fundamental_feed import AutoFundamentalFeed
        from src.fred_feed import _fetch_history
        fred = getattr(AutoFundamentalFeed(cfg), "_fred", None)
        for sid, label in (("DFII10", "taux réel 10 ans"), ("DTWEXBGS", "dollar large"), ("VIXCLS", "VIX"),
                           ("T10YIE", "inflation anticipée 10 ans"), ("GVZCLS", "volatilité implicite de l'or")):
            s = _fetch_history(fred, sid)
            if len(s) < 100:
                continue
            s = s[~s.index.duplicated()].reindex(days).ffill().shift(1)      # publié le lendemain
            sig[f"{label} : niveau (z 1 an)"] = zscore(s)
            sig[f"{label} : variation 5 j"] = s.diff(5)
            sig[f"{label} : variation 20 j"] = s.diff(20)
    except Exception as e:
        print("FRED indisponible :", e, flush=True)
    # CFTC
    try:
        cot = cot_gold()
        cot = cot[~cot.index.duplicated()].sort_index()
        cot = cot.reindex(cot.index.union(days.unique())).ffill().reindex(days)
        sig["gros spéculateurs : position nette (z 3 ans)"] = zscore(cot["cot_mm_net"], 156 * 5 // 5 * 5)
        sig["gros spéculateurs : position nette"] = cot["cot_mm_net"]
        sig["gros spéculateurs : variation 4 sem."] = cot["cot_mm_net"].diff(20)
        sig["producteurs/négociants : position nette"] = cot["cot_prod_net"]
        sig["intérêt ouvert : variation 4 sem."] = cot["cot_oi_chg4"]
    except Exception as e:
        print("CFTC indisponible :", e, flush=True)
    print(f"{len(sig)} signaux préparés ({time.time() - t0:.0f}s)", flush=True)

    fut = {h: gold.shift(-h) / gold - 1 for h in HS}
    rows = []
    for name, s in sig.items():
        r = {"signal": name}
        for h in HS:
            for pname, (a, b) in (("dev", DEV), ("val", VAL)):
                idx = days[(days >= a) & (days < b)][::h]
                x, y = s.reindex(idx), fut[h].reindex(idx)
                ok = x.notna() & y.notna()
                if ok.sum() < 30:
                    r[f"{pname}{h}"], r[f"t_{pname}{h}"] = np.nan, np.nan
                    continue
                ic = spearmanr(x[ok], y[ok]).correlation
                r[f"{pname}{h}"], r[f"t_{pname}{h}"] = ic, ic * np.sqrt(ok.sum())
        rows.append(r)
    T = pd.DataFrame(rows)
    # tient sur les deux périodes : même signe, |t| >= 2 en développement, |t| >= 1,5 en vérification
    for h in HS:
        T[f"robuste{h}"] = ((np.sign(T[f"dev{h}"]) == np.sign(T[f"val{h}"])) & (T[f"t_dev{h}"].abs() >= 2)
                            & (T[f"t_val{h}"].abs() >= 1.5))
    L = [f"# Test d'information sur l'or ({time.strftime('%Y-%m-%d %H:%M')})", "",
         "Corrélation de rang signal(t) -> rendement de l'or (t -> t+h), dates non chevauchantes. "
         "dev = 2010-2018, val = 2019 -> 2023-04. ROBUSTE = même sens, |t| >= 2 (dev) et >= 1,5 (val).", ""]
    for h in HS:
        L.append(f"## Horizon {h} jour(s)")
        sub = T.sort_values(f"t_dev{h}", key=lambda s: -s.abs())
        for _, r in sub.iterrows():
            if pd.isna(r[f"dev{h}"]):
                continue
            flag = " **ROBUSTE**" if r[f"robuste{h}"] else ""
            L.append(f"- {r['signal']} : dev {r[f'dev{h}']:+.3f} (t {r[f't_dev{h}']:+.1f}) | "
                     f"val {r[f'val{h}']:+.3f} (t {r[f't_val{h}']:+.1f}){flag}")
        L.append("")
    os.makedirs("reports", exist_ok=True)
    open("reports/info_test.md", "w", encoding="utf-8").write("\n".join(L) + "\n")
    T.to_csv("reports/info_test.csv", index=False)
    print("\n".join(L), flush=True)
    print(f"terminé en {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
