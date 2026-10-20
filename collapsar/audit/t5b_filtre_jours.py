"""AUDIT 5b : pourquoi la bande de bruit du projet (US500 2015-2021) gagne moins par trade que la réplication ?
Hypothèse : les séances incomplètes (300 à 369 minutes sur 390) que le projet garde, bouchées « plates ».
Depuis Test_IA : venv_gpu\\Scripts\\python.exe -u -m collapsar.audit.t5b_filtre_jours
"""
import json

import numpy as np
import pandas as pd

from collapsar.donnees import marches as dm
from collapsar.regarder import bande_bruit as BB

OUT = dm.RACINE / "collapsar" / "vie" / "audit"
from collapsar.regarder import orb

s = {j: a for j, a in orb.seances(orb.minutes("US500")).items() if j < pd.Timestamp("2022-01-01")}
n_min = pd.Series({j: len(a) for j, a in s.items()})
res = {"seances_gardees_par_le_projet": int(len(n_min)), "dont_300_a_369_minutes": int(((n_min >= 300) & (n_min < 370)).sum()),
       "dont_370_et_plus": int((n_min >= 370).sum())}
t = pd.read_csv(OUT.parent / "bande_bruit" / "trades_apprentissage.csv", parse_dates=["jour"])
t = t[(t["marche"] == "US500") & (t["jour"] < "2022-01-01")].copy()
t["minutes_seance"] = t["jour"].map(n_min)
for nom, g in (("séances complètes (>= 370 min)", t[t["minutes_seance"] >= 370]),
               ("séances trouées (300-369 min)", t[t["minutes_seance"] < 370])):
    res[nom] = {"trades": len(g), "brut_moyen_pct": float(g["brut"].mean() * 100),
                "jours": int(g["jour"].nunique())}
# même moteur du projet, séances complètes seulement
s2 = {j: a for j, a in s.items() if len(a) >= 370}
jours, O, H, L, C = BB.matrice(s2)
res["par_annee_minutes_par_seance_mediane"] = n_min.groupby(n_min.index.year).median().to_dict()
res["par_annee_part_seances_trouees_pct"] = ((n_min < 370).groupby(n_min.index.year).mean() * 100).round(1).to_dict()
print(json.dumps(res, ensure_ascii=False, indent=1, default=float))
(OUT / "t5b_filtre_jours.json").write_text(json.dumps(res, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
