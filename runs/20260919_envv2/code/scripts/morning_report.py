"""
Bilan en français de l'état du système (06/10/2026) -- compte, positions, apprentissage d'AUREX, gardien,
dernières décisions avec leur note de trader.

    python scripts/morning_report.py [--since "2026-10-06 00:00"]        (cwd = code/)

Écrit reports/bilan.md et l'affiche.
"""
import argparse, glob, json, os, sqlite3, sys, time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
os.chdir(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pandas as pd


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", default=time.strftime("%Y-%m-%d 00:00"))
    args = ap.parse_args()
    L = [f"# Bilan du système ({time.strftime('%d/%m/%Y %H:%M')})", ""]

    # compte et positions (lecture seule)
    try:
        import MetaTrader5 as mt5
        mt5.initialize(path="C:/Program Files/MetaTrader 5/terminal64.exe")
        a = mt5.account_info()
        L += ["## Compte démo", f"- Équité **{a.equity:,.2f} $**, solde {a.balance:,.2f} $".replace(",", " ")]
        for p in mt5.positions_get(symbol="XAUUSD") or []:
            L.append(f"- {p.comment} : {'ACHAT' if p.type == 0 else 'VENTE'} {p.volume} lot à {p.price_open}, "
                     f"stop {p.sl}, objectif {p.tp or '-'}, P&L {p.profit:+.2f} $")
        L.append(f"- Or : {mt5.symbol_info_tick('XAUUSD').bid}")
    except Exception as e:
        L.append(f"- compte illisible ({e})")

    # trades clôturés depuis --since
    try:
        c = sqlite3.connect("data/decision_journal.sqlite")
        t = pd.read_sql("select style, close_time, net_profit, r_multiple, close_reason from trades", c)
        t = t[pd.to_datetime(t["close_time"]) >= pd.Timestamp(args.since)]
        L += ["", f"## Trades clôturés depuis {args.since} : {len(t)}"]
        for _, r in t.iterrows():
            L.append(f"- {r['close_time']} {r['style']} : {r['net_profit']:+.2f} $ ({r['r_multiple'] or 0:+.2f}R, {r['close_reason']})")
        d = pd.read_sql("select * from decisions where ts_utc >= ? order by ts_utc desc limit 8", c, params=(args.since,))
        if len(d):
            L += ["", "## Dernières décisions (heure UTC) et notes de trader"]
            L += [f"- {r['ts_utc']} {r['style']} : {r.get('note') or r['action']}" for _, r in d.iterrows()]
    except Exception as e:
        L.append(f"- journal illisible ({e})")

    # apprentissage AUREX
    rows = [json.loads(l) for l in open("reports/experiment_journal.jsonl", encoding="utf-8")]
    au = pd.DataFrame([r for r in rows if r.get("style") == "AUREX" and r.get("time", "") >= args.since])
    L += ["", "## Apprentissage d'AUREX"]
    try:
        m = json.load(open("models/champion_AUREX/meta.json", encoding="utf-8"))
        mm = m.get("metrics", {})
        L.append(f"- Champion : génération {m.get('generation')}, score {m.get('score', 0):.3f}, Sharpe {mm.get('sharpe', 0):.2f}, "
                 f"rendement validation {mm.get('total_return', 0):+.1%}, drawdown {mm.get('max_drawdown', 0):.1%}, "
                 f"{mm.get('n_trades')} trades, éligible démo : {'OUI' if m.get('passes_validation') else 'non'}"
                 + (f", lockbox Sharpe {m['lockbox']['sharpe']:.2f}" if m.get("lockbox") else ""))
    except Exception as e:
        L.append(f"- champion illisible ({e})")
    if len(au):
        if "kind" not in au.columns:
            au["kind"] = "control"
        for g, grp in au.groupby("generation"):
            inc = grp[grp["kind"] == "incumbent"]
            grp = grp[grp["kind"] != "incumbent"]
            if not len(grp):
                continue
            b = grp.sort_values("score", ascending=False).iloc[0]
            L.append(f"- cycle {g} : {len(grp)} candidats, {int((grp['score'] > 0).sum())} positifs, meilleur score "
                     f"{b['score']:.3f} (Sharpe {b['sharpe']:.2f}, {b['total_return']:+.1%}, DD {b['max_drawdown']:.1%}"
                     + (f", {int(b['n_trades'])} trades" if "n_trades" in b and pd.notna(b.get("n_trades")) else "") + ")"
                     + (f" -- champion rejoué : {inc.iloc[0]['score']:.3f}" if len(inc) else ""))

    # lockbox et taille au risque (scripts/lockbox_check_style.py, scripts/r_sizing_lockbox.py)
    for f, title in (("reports/lockbox_AUREX.json", "lockbox"), ("reports/r_sizing_AUREX.json", "taille au risque")):
        if not os.path.exists(f):
            continue
        j = json.load(open(f, encoding="utf-8"))
        if title == "lockbox":
            L.append(f"- Lockbox (gén {j.get('generation')}, depuis {j.get('lockbox_start')}) : Sharpe {j['sharpe']:.2f}, "
                     f"{j['total_return']:+.1%}, DD {j['max_drawdown']:.1%}, {j['n_trades']} trades -> "
                     f"{'porte OK' if j.get('gate_ok') else 'porte refusée : ' + str(j.get('gate_reason'))}")
        else:
            tr = j.get("trades", {})
            L.append(f"- Lockbox en R : {tr.get('n')} trades, réussite {tr.get('win_rate', 0):.0%}, "
                     f"{tr.get('avg_R', 0):+.2f} R/trade en moyenne")
            for k in ("risk_0.0025", "risk_0.005", "risk_0.01"):
                if k in j:
                    x = j[k]
                    L.append(f"  - risque {float(k.split('_')[1]):.2%}/trade : {x['return']:+.0%} sur "
                             f"{x.get('months', 0):.0f} mois, DD {x['max_dd']:.1%}, pire jour {x.get('worst_day', 0):+.1%}, "
                             f"Challenge FTMO {(x.get('prop_firm') or {}).get('challenge_pass', 0):.0%}")

    # gardien et redémarrages
    for f, title in (("logs/watchdog.txt", "Gardien"), ("logs/boundary_apply_status.txt", "Modifications appliquées")):
        if os.path.exists(f):
            lines = [l.strip() for l in open(f, encoding="utf-8", errors="replace") if l.strip()]
            L += ["", f"## {title}"] + [f"- {l}" for l in lines[-8:]]
    out = "\n".join(L) + "\n"
    os.makedirs("reports", exist_ok=True)
    open("reports/bilan.md", "w", encoding="utf-8").write(out)
    print(out)


if __name__ == "__main__":
    main()
