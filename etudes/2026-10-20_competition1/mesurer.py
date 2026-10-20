"""Compétition 1 : 3 hypothèses neuves contre leurs juges (PLAN_FIGE.md). Le COFFRE (2024 ->) n'est jamais chargé :
les données s'arrêtent au 01/01/2024 (FIN_LUE).

    venv_gpu\\Scripts\\python.exe etudes\\2026-10-20_competition1\\mesurer.py          (UNE fois, verrou)
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from multiprocessing import Pool
from pathlib import Path

ICI = Path(__file__).resolve().parent
RACINE = ICI.parents[1]
sys.path.insert(0, str(RACINE))

import numpy as np
import pandas as pd

FIN_LUE = pd.Timestamp("2024-01-01")
PERIODES = {"recherche": (pd.Timestamp("2012-01-01"), pd.Timestamp("2020-01-01")),
            "validation": (pd.Timestamp("2020-01-01"), FIN_LUE),
            "total": (pd.Timestamp("2012-01-01"), FIN_LUE)}
INDICES = {"elan_journee": ("USA500IDXUSD", ["USATECHIDXUSD", "USA30IDXUSD"]),
           "trou_ouverture": ("USA500IDXUSD", ["USATECHIDXUSD", "USA30IDXUSD"])}
RES = ICI / "resultats"
VERROU = RES / "VERROU.json"
GIT = r"C:\Users\utilisateur\AppData\Local\GitHubDesktop\app-3.6.6\resources\app\git\cmd\git.exe"


def _base(g, t, g15, n_trades, achats):
    from cerveau.mesure import fenetres as FE
    mens = FE.mensuel(g, t)
    jour = pd.Series(g, index=t).groupby(t.normalize()).sum()
    cumul = np.cumsum(g)
    return {"trades": int(n_trades), "achats_pct": achats, "gain_moyen_dollars": float(np.mean(g)) if len(g) else None,
            "gain_pct_mois": float(mens.mean() / FE.CAPITAL * 100), "gagnants_pct": float(100 * (g > 0).mean()),
            "gain_pct_mois_frais_x1_5": float(FE.mensuel(g15, t).mean() / FE.CAPITAL * 100),
            "pire_jour_pct": float(jour.min() / FE.CAPITAL * 100),
            "pire_baisse_pct": float(np.max(np.maximum.accumulate(np.r_[0, cumul])[1:] - cumul) / FE.CAPITAL * 100)}


def indice(args) -> dict:
    hyp, sym = args
    from cerveau.mesure import fenetres as FE
    from cerveau.perception.calendrier import HYPOTHESES
    from core import donnees as D
    b15 = D.charger(sym, FIN_LUE)                      # rien après le 31/12/2023
    m = FE.Marche(sym, b15)
    av = HYPOTHESES[hyp].avis(b15)
    out = {}
    for nom, (a, b) in PERIODES.items():
        ke, ks, s, t, pe, ps, ts = m.fenetres(av, a, b)
        kw = {"pe": pe, "ps": ps, "te": t.asi8, "ts": ts.asi8}
        g = m.pnl(ke, ks, s, **kw)
        pile = (g + m.pnl(ke, ks, -s, **kw)) / 2
        mens = FE.mensuel(g, t)
        res = _base(g, t, m.pnl(ke, ks, s, 1.5, **kw), len(g), float(100 * (s > 0).mean()))
        res["contre_pile_ou_face"] = FE.avantage(mens, FE.mensuel(pile, t))
        res["contre_acheteur_risque_egal"] = FE.avantage(mens, m.acheteur_mensuel(a, b), risque_egal=True)
        out[nom] = res
    return {"hyp": hyp, "sym": sym, "periodes": out}


def devises() -> dict:
    from cerveau.mesure import fenetres as FE
    from cerveau.perception.devises import PAIRES, RETOURNEMENT, devise_contre_dollar
    from core import donnees as D
    b = {p: D.charger(p, FIN_LUE) for p in PAIRES}
    marches = {p: FE.Marche(p, b[p]) for p in PAIRES}
    av = RETOURNEMENT.avis_multi(b)
    semaines = av[["temps", "expire"]].drop_duplicates().reset_index(drop=True)
    out = {}
    for nom, (a, bb) in PERIODES.items():
        lignes = []                                    # une ligne par (semaine, paire) : gains achat / vente de la devise
        for p in PAIRES:
            m = marches[p]
            tout = semaines.assign(sens=devise_contre_dollar(p))
            ke, ks, s, t, pe, ps, ts = m.fenetres(tout, a, bb)
            kw = {"pe": pe, "ps": ps, "te": t.asi8, "ts": ts.asi8}
            achat = 0.5 * m.pnl(ke, ks, s, **kw)
            vente = 0.5 * m.pnl(ke, ks, -s, **kw)
            achat15 = 0.5 * m.pnl(ke, ks, s, 1.5, **kw)
            vente15 = 0.5 * m.pnl(ke, ks, -s, 1.5, **kw)
            for i in range(len(ke)):
                lignes.append((t[i], p, achat[i], vente[i], achat15[i], vente15[i]))
        df = pd.DataFrame(lignes, columns=["temps", "paire", "achat", "vente", "achat15", "vente15"])
        choix = av[(av["temps"] >= a) & (av["temps"] < bb)][["temps", "marche", "sens"]].rename(columns={"marche": "paire"})
        choix["dir_devise"] = choix["sens"] * choix["paire"].map(devise_contre_dollar)       # +1 = devise achetée
        df = df.merge(choix[["temps", "paire", "dir_devise"]], on=["temps", "paire"], how="left").fillna({"dir_devise": 0})
        # semaines complètes seulement (les 7 paires mesurées)
        complet = df.groupby("temps")["paire"].transform("count") == len(PAIRES)
        df = df[complet]
        df["signal"] = np.where(df["dir_devise"] > 0, df["achat"], np.where(df["dir_devise"] < 0, df["vente"], 0.0))
        df["signal15"] = np.where(df["dir_devise"] > 0, df["achat15"], np.where(df["dir_devise"] < 0, df["vente15"], 0.0))
        df["hasard"] = 2 / 7 * (df["achat"] + df["vente"])                                 # espérance exacte du tirage
        df["pile"] = np.where(df["dir_devise"] != 0, (df["achat"] + df["vente"]) / 2, 0.0)
        sem = df.groupby("temps")[["signal", "signal15", "hasard", "pile"]].sum()
        t = pd.DatetimeIndex(sem.index)
        mens = FE.mensuel(sem["signal"].to_numpy(), t)
        res = _base(sem["signal"].to_numpy(), t, sem["signal15"].to_numpy(), 4 * len(sem), 50.0)
        res["semaines"] = int(len(sem))
        res["contre_tirage_des_devises"] = FE.avantage(mens, FE.mensuel(sem["hasard"].to_numpy(), t))
        res["contre_pile_ou_face"] = FE.avantage(mens, FE.mensuel(sem["pile"].to_numpy(), t))
        part = df.assign(ecart=df["signal"] - df["hasard"]).groupby("paire")["ecart"].sum()
        res["part_par_devise_dollars"] = {k: round(float(v), 1) for k, v in part.items()}
        out[nom] = res
    return out


def criteres(res_ind: dict, res_dev: dict) -> dict:
    c = {}
    for hyp, (sym, robs) in INDICES.items():
        p = res_ind[(hyp, sym)]
        tot = p["total"]["contre_pile_ou_face"]
        x = {"1_gain_positif_recherche_et_validation": p["recherche"]["gain_pct_mois"] > 0 and p["validation"]["gain_pct_mois"] > 0,
             "2_bat_le_juge_cle": tot["avantage_pct_mois"] > 2 * tot["incertitude"]
                                  and p["recherche"]["contre_pile_ou_face"]["avantage_pct_mois"] > 0
                                  and p["validation"]["contre_pile_ou_face"]["avantage_pct_mois"] > 0,
             "3_bat_acheteur_risque_egal": p["total"]["contre_acheteur_risque_egal"]["avantage_pct_mois"] > 0,
             "4_robuste": sum(res_ind[(hyp, r)]["total"]["contre_pile_ou_face"]["avantage_pct_mois"] > 0 for r in robs) >= 1,
             "5_frais_x1_5": p["total"]["gain_pct_mois_frais_x1_5"] > 0,
             "6_au_moins_100_trades": p["total"]["trades"] >= 100}
        x["CANDIDATE"] = all(x.values())
        c[hyp] = x
    p = res_dev
    tot = p["total"]["contre_tirage_des_devises"]
    x = {"1_gain_positif_recherche_et_validation": p["recherche"]["gain_pct_mois"] > 0 and p["validation"]["gain_pct_mois"] > 0,
         "2_bat_le_juge_cle": tot["avantage_pct_mois"] > 2 * tot["incertitude"]
                              and p["recherche"]["contre_tirage_des_devises"]["avantage_pct_mois"] > 0
                              and p["validation"]["contre_tirage_des_devises"]["avantage_pct_mois"] > 0,
         "3_bat_pile_ou_face": p["total"]["contre_pile_ou_face"]["avantage_pct_mois"] > 0,
         "4_robuste_5_devises_sur_7": sum(v > 0 for v in p["total"]["part_par_devise_dollars"].values()) >= 5,
         "5_frais_x1_5": p["total"]["gain_pct_mois_frais_x1_5"] > 0,
         "6_au_moins_100_trades": p["total"]["trades"] >= 100}
    x["CANDIDATE"] = all(x.values())
    c["retournement_devises"] = x
    return c


def main():
    RES.mkdir(exist_ok=True)
    if VERROU.exists():
        raise SystemExit(f"déjà lancé : {VERROU.read_text(encoding='utf-8')}")
    commit = subprocess.run([GIT, "rev-parse", "HEAD"], capture_output=True, text=True, cwd=RACINE).stdout.strip()
    sale = subprocess.run([GIT, "status", "--porcelain", "--", "cerveau", "core", str(ICI.relative_to(RACINE))],
                          capture_output=True, text=True, cwd=RACINE).stdout.strip()
    VERROU.write_text(json.dumps({"lance": time.strftime("%d/%m/%Y %H:%M:%S"), "commit": commit,
                                  "modifs_non_commitees": sale}, ensure_ascii=False, indent=1), encoding="utf-8")
    taches = [(h, s) for h, (p, robs) in INDICES.items() for s in [p] + robs]
    with Pool(6) as pool:
        r_dev = pool.apply_async(devises)
        liste = pool.map(indice, taches)
        res_dev = r_dev.get()
    res_ind = {(r["hyp"], r["sym"]): r["periodes"] for r in liste}
    sortie = {"indices": {f"{h}|{s}": v for (h, s), v in res_ind.items()}, "devises": res_dev,
              "criteres": criteres(res_ind, res_dev)}
    (RES / "competition1.json").write_text(json.dumps(sortie, ensure_ascii=False, indent=1), encoding="utf-8")
    for (h, s), v in res_ind.items():
        for per in ("recherche", "validation", "total"):
            x = v[per]
            print(f"{h:>15} {s:>13} {per:>10} : {x['trades']:5d} trades, {x['gain_pct_mois']:+.3f} %/mois (x1,5 "
                  f"{x['gain_pct_mois_frais_x1_5']:+.3f}) | pile {x['contre_pile_ou_face']['avantage_pct_mois']:+.3f} ± "
                  f"{x['contre_pile_ou_face']['incertitude']:.3f} | acheteur risque égal "
                  f"{x['contre_acheteur_risque_egal']['avantage_pct_mois']:+.3f} | pire jour {x['pire_jour_pct']:.2f} %",
                  flush=True)
    for per in ("recherche", "validation", "total"):
        x = res_dev[per]
        print(f"   devises {per:>10} : {x['semaines']} semaines, {x['gain_pct_mois']:+.3f} %/mois (x1,5 "
              f"{x['gain_pct_mois_frais_x1_5']:+.3f}) | tirage {x['contre_tirage_des_devises']['avantage_pct_mois']:+.3f} ± "
              f"{x['contre_tirage_des_devises']['incertitude']:.3f} | pile {x['contre_pile_ou_face']['avantage_pct_mois']:+.3f} "
              f"| part par devise {x['part_par_devise_dollars']}", flush=True)
    for h, c in sortie["criteres"].items():
        print(h, c, flush=True)


if __name__ == "__main__":
    main()
