"""AUDIT 7 : la « force » des pistes à taille variable (bande_bruit, bitcoin_journee) est calculée sur le rendement BRUT
non pondéré par la taille ; le compte, lui, est taillé à cible / agitation. Force recalculée pondérée par la taille.
Depuis Test_IA : venv_gpu\\Scripts\\python.exe -u -m collapsar.audit.t7_force_ponderee
"""
import json
import math

import numpy as np
import pandas as pd

from collapsar.donnees import marches as dm

OUT = dm.RACINE / "collapsar" / "vie" / "audit"
VIE = dm.RACINE / "collapsar" / "vie"
res = {}


def f(x):
    return float(x.mean() / x.std(ddof=1) * math.sqrt(len(x)))


t = pd.read_csv(VIE / "bande_bruit" / "trades_apprentissage.csv", parse_dates=["jour"])
for per, (a, z) in {"2015-2021": ("2015-01-01", "2022-01-01"), "2022-2023": ("2022-01-01", "2024-01-01")}.items():
    for mk in ("US500", "NAS100", "XAUUSD"):
        g = t[(t["marche"] == mk) & (t["jour"] >= a) & (t["jour"] < z)]
        lev = np.minimum(4.0, 0.01 * g["levier_par_cible"])
        res[f"bande_bruit {mk} {per}"] = {"trades": len(g), "force_projet": f(g["brut"]), "force_ponderee": f(lev * g["brut"])}
bj = pd.read_csv(VIE / "pistes" / "bitcoin_journee" / "trades_apprentissage.csv", parse_dates=["jour"])
for per, (a, z) in {"2017-05 -> 2021": ("2017-05-01", "2022-01-01"), "2022-2023": ("2022-01-01", "2024-01-01")}.items():
    for v in ("A3", "B1", "B2", "C1", "C2", "D1"):
        g = bj[(bj["variante"] == v) & (bj["jour"] >= a) & (bj["jour"] < z)]
        brut = g["sens"] * g["r_prix"]
        expo = np.minimum(1.0, 0.01 / g["agitation"])
        res[f"bitcoin {v} {per}"] = {"trades": len(g), "force_projet": f(brut), "force_ponderee": f(expo * brut)}
df = pd.DataFrame(res).T
print(df.round(2).to_string())
(OUT / "t7_force_ponderee.json").write_text(json.dumps(res, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
