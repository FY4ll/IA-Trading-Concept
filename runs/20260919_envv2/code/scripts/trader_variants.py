"""
TRADER HUMAIN -- variantes (07/10/2026). Même graphique et mêmes setups que src/trader (chasse aux stops,
cassure-retest, repli en tendance, rejet en range ; achat ET vente), mais gestion « trader swing » possible :
stop élargi derrière une structure plus large (plancher en ATR H1 au lieu de refuser le trade), position gardée
plusieurs jours, discipline de tendance D1. Mesures en R, coûts réels (spread 0,30 $ + slippage 0,05 $ par jambe).

Développement 2010-2018, vérification 2019 -> 2023-04. La lockbox (2023-05 ->) N'EST PAS regardée ici.
    python scripts/trader_variants.py        (cwd = code/)  -> reports/trader_variants.md
"""
import os, sys, time
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
os.chdir(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import numpy as np, pandas as pd, yaml
from src.trader import chart, playbook, engine

DEV = (pd.Timestamp("2010-01-01"), pd.Timestamp("2019-01-01"))
VAL = (pd.Timestamp("2019-01-01"), pd.Timestamp("2023-05-01"))


def run_variant(ch, sig, rules, d1_trend=None, stop_floor_atr=None):
    """engine.run avec deux options humaines : stop élargi au plancher (au lieu de refuser) et tendance D1."""
    sig = sig.copy()
    if stop_floor_atr:
        # stop placé au moins à `stop_floor_atr` x ATR H1 du prix (derrière la structure M15/H1 ET à distance de bruit)
        c = ch["close"].to_numpy(); atr = ch["h1_atr"].to_numpy()
        d = sig["dir"].to_numpy(); sl = sig["sl"].to_numpy()
        floor_sl = c - d * stop_floor_atr * atr
        wider = np.where(d > 0, np.minimum(sl, floor_sl), np.maximum(sl, floor_sl))
        sig["sl"] = np.where(sig["setup"].to_numpy() != "", wider, sl)
    if d1_trend is not None:
        bad = (sig["setup"].to_numpy() != "") & (sig["dir"].to_numpy() * d1_trend <= 0)
        sig.loc[bad, "setup"] = ""
    return engine.run(ch, sig, rules)


def stats_period(t, a, b):
    if len(t) == 0:
        return {"n": 0}
    et = pd.to_datetime(t["entry_time"])
    return engine.stats(t[(et >= a) & (et < b)])


def fmt(s):
    if not s.get("n"):
        return "0 trade"
    pf = f"{s['profit_factor']:.2f}" if s.get("profit_factor") else "n/a"
    return f"{s['n']:5d} trades, gain {s['win_rate']:.0%}, {s['avg_R']:+.3f}R/trade, PF {pf}, t={s['t_stat'] or 0:+.1f}"


def main():
    t0 = time.time()
    cfg = yaml.safe_load(open("../run_config_A.yaml", encoding="utf-8"))
    m15 = chart.load_m15(cfg, "2008-01-01")
    m15 = m15[m15.index < pd.Timestamp("2023-05-01")]          # lockbox jamais chargée ici
    ch = chart.build_chart(m15)
    sig = playbook.detect(ch)
    d1 = chart.resample(m15, "1D")
    tr = ((d1["close"].rolling(20).mean() - d1["close"].rolling(50).mean()) / d1["close"]).shift(1)
    d1_trend = np.sign(tr.reindex(ch.index.normalize()).to_numpy())
    print(f"graphique : {len(ch)} bougies, {int((sig['setup'] != '').sum())} signaux ({time.time() - t0:.0f}s)", flush=True)
    zero = {"spread": 0.0, "slippage": 0.0}
    swing = {"intraday": False, "max_sl_atr": 6.0, "tp2_max_r": 4.0, "max_trades_day": 1}
    variants = [
        ("1. d'origine (intraday, stops serrés)", {}, None, None),
        ("2. d'origine SANS frais (avantage brut)", zero, None, None),
        ("3. stop >= 1 ATR H1", {"max_sl_atr": 3.0}, None, 1.0),
        ("4. stop >= 2 ATR H1, swing (plusieurs jours)", swing, None, 2.0),
        ("5. = 4 + tendance D1", swing, d1_trend, 2.0),
        ("6. stop >= 3 ATR H1, swing + tendance D1", {**swing, "max_sl_atr": 8.0}, d1_trend, 3.0),
        ("7. = 6 SANS frais", {**swing, "max_sl_atr": 8.0, **zero}, d1_trend, 3.0),
    ]
    L = [f"# Trader humain -- variantes ({time.strftime('%Y-%m-%d %H:%M')})", ""]
    for name, rules, trend, floor in variants:
        t, _ = run_variant(ch, sig, rules, trend, floor)
        L.append(f"## {name}")
        for pname, (a, b) in (("2010-2018", DEV), ("2019-2023/04", VAL)):
            L.append(f"- {pname} tous setups : {fmt(stats_period(t, a, b))}")
            for s in playbook.SETUPS:
                st = stats_period(t[t['setup'] == s] if len(t) else t, a, b)
                if st.get("n"):
                    L.append(f"    - {playbook.NAMES_FR[s]} : {fmt(st)}")
        if len(t):
            for side, dd in (("achats", 1), ("ventes", -1)):
                L.append(f"- {side} 2010-2023/04 : {fmt(engine.stats(t[t['dir'] == dd]))}")
        L.append("")
        print("\n".join(L[-14:]), flush=True)
    os.makedirs("reports", exist_ok=True)
    open("reports/trader_variants.md", "w", encoding="utf-8").write("\n".join(L) + "\n")
    print(f"terminé en {(time.time() - t0) / 60:.1f} min -> reports/trader_variants.md")


if __name__ == "__main__":
    main()
