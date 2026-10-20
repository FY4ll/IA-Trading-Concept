"""SECOND AVIS sur les signaux de la bande de bruit (16/10/2026, rapport « Recherche daytrading rentable », piste 3 :
l'apprentissage automatique trie les signaux d'une méthode, il ne devine pas la direction tout seul).

Pour chaque signal (regarder/bande_bruit.py), des faits connus AU MOMENT de l'entrée : marché, sens, heure, rang du
trade dans la journée, agitation des 14 jours, trou d'ouverture, chemin depuis l'ouverture, tendances 5/20/60 jours,
résultat de la veille, jour de la semaine (tout signé par le sens et rapporté à l'agitation).
Cible : gain APRÈS frais / agitation. Petit modèle (arbres boostés peu profonds) appris sur 2015-2021 ; seuil = 0
(fixé d'avance) ; vérification 2022-2023 ; 2024-2026 = DEUXIÈME regard (déjà vue pour la méthode brute, signalé).
Depuis Test_IA : venv_gpu\\Scripts\\python.exe -u -m collapsar.regarder.second_avis
"""
from __future__ import annotations

import json
import math
from datetime import datetime

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor

from collapsar.regarder import bande_bruit as bb
from collapsar.regarder import orb

VIE = bb.VIE
FIN_APPR = pd.Timestamp("2022-01-01")


def faits() -> pd.DataFrame:
    parts = []
    for m in bb.MARCHES:
        t = bb.simuler(m, "2027-01-01")
        s = orb.seances(orb.minutes(m))
        jours, O, H, L, C = bb.matrice(s)
        cl = pd.Series(C[:, -1], index=jours)
        ouv = pd.Series(O[:, 0], index=jours)
        veille = cl.shift(1)
        f = pd.DataFrame(index=jours)
        f["trou"] = ouv / veille - 1
        for n in (5, 20, 60):
            f[f"tend{n}"] = veille / cl.shift(1 + n) - 1
        f["hier"] = veille / cl.shift(2) - 1
        f["ouv"] = ouv
        t = t.join(f, on="jour")
        sg, ag = t["sens"], t["agitation"]
        x = pd.DataFrame({"marche": bb.MARCHES.index(m), "sens": sg, "minute": t["m_entree"],
                          "rang": t.groupby("jour").cumcount(), "agitation": ag,
                          "trou": sg * t["trou"] / ag, "chemin": sg * (t["prix"] / t["ouv"] - 1) / ag,
                          "tend5": sg * t["tend5"] / ag, "tend20": sg * t["tend20"] / ag, "tend60": sg * t["tend60"] / ag,
                          "hier": sg * t["hier"] / ag, "semaine": t["jour"].dt.dayofweek})
        x["y"] = (t["brut"] - t["frais"]) / ag
        brut_t = t.drop(columns=["marche", "trou", "tend5", "tend20", "tend60", "hier"]).assign(nom_marche=m)
        parts.append(pd.concat([brut_t, x.drop(columns=["sens", "agitation"])], axis=1))
    return pd.concat(parts, ignore_index=True).dropna(subset=["tend60"]).sort_values("jour", kind="stable")


COLS = ["marche", "sens", "minute", "rang", "agitation", "trou", "chemin", "tend5", "tend20", "tend60", "hier",
        "semaine"]


def main():
    d = faits()
    appr = d[d["jour"] < FIN_APPR]
    mod = HistGradientBoostingRegressor(max_depth=3, max_iter=200, learning_rate=0.05, min_samples_leaf=150,
                                        l2_regularization=1.0, categorical_features=[0], random_state=0)
    mod.fit(appr[COLS], appr["y"])
    d["avis"] = mod.predict(d[COLS])
    sortie = {"quand": datetime.now().isoformat(timespec="seconds"), "periodes": {}}
    for p, (de, a) in bb.PERIODES.items():
        g = d[(d["jour"] >= de) & (d["jour"] < a)]
        jours = pd.bdate_range(de, g["jour"].max() + pd.Timedelta(days=1))
        res = {}
        for nom, sel in (("tous les signaux", g), ("pris par le second avis", g[g["avis"] > 0])):
            x = bb.bilan(sel.assign(levier_par_cible=sel["levier_par_cible"] / math.sqrt(3)), jours)
            ch = {}
            for cible in bb.CIBLES:
                gj = bb.journalier(sel, cible / math.sqrt(3)).reindex(jours, fill_value=0.0)
                ch[f"{cible * 100:.1f} %"] = bb.challenge(gj)
            x["challenges"] = ch
            x["net_moyen_pct_prix"] = float((sel["brut"] - sel["frais"]).mean() * 100) if len(sel) else None
            res[nom] = x
        sortie["periodes"][p] = res
        print(f"\n=== {p} ===")
        for nom, x in res.items():
            print(f"{nom:25s} {x.get('trades')} trades | gagnants {x.get('gagnants_pct', 0):.0f} % | net "
                  f"{x.get('net_moyen_pct_prix') or 0:+.4f} % du prix | {x.get('gain_pct_mois_cible1', 0):+.2f} %/mois "
                  f"(cible 1 %) | rapport {x.get('rapport_gain_risque', 0):+.2f} | baisse max {x.get('pire_baisse_pct', 0):.1f} %")
            print("   challenges (réussis / morts) : " + ", ".join(
                f"{c} {v['reussis_pct']:.0f}/{v['morts_pct']:.0f}" for c, v in x["challenges"].items()))
    (VIE / "second_avis.json").write_text(json.dumps(sortie, ensure_ascii=False, indent=1, default=str),
                                          encoding="utf-8")
    d.to_csv(VIE / "second_avis_trades.csv", index=False)


if __name__ == "__main__":
    main()
