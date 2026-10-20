"""Vérifie que les mondes inventés ressemblent aux vrais marchés AVANT qu'elle y entre (14/10/2026).

1. Empreintes (mondes/empreintes.py) : la médiane des vrais marchés doit tomber dans la plage des mondes.
2. Difficulté : qualité annuelle d'un simple suivi de tendance (instrument de MESURE seulement, elle ne le voit
   jamais) sur 5, 20 et 60 jours, vrais marchés contre mondes, à plusieurs intensités de lois.
Seulement les années d'apprentissage (2010-2019) des vrais marchés.
Depuis Test_IA : venv_gpu\\Scripts\\python.exe -m collapsar.mondes.verifier
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from collapsar.donnees import marches as dm
from collapsar.mondes.empreintes import NOMS, empreintes
from collapsar.mondes.generateur import fabriquer, tirer_lois

REELS = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "EURJPY", "XAGUSD", "USA500IDXUSD", "DEUIDXEUR", "LIGHTCMDUSD",
         "BTCUSD"]
SORTIE = dm.RACINE / "collapsar" / "vie" / "mondes_verification.json"


def qualite_tendance(df: pd.DataFrame, n: int, frais: float = 0.0001) -> float:
    c = np.log(df.set_index("time")["close"])
    j = c.groupby(c.index.normalize()).last()
    j = j[j.index.dayofweek < 5]
    r = j.diff()
    s = np.sign(j.diff(n)).shift(1)
    g = (s * r - (s.diff().abs() > 0) * frais).dropna()
    return float(g.mean() / g.std() * np.sqrt(252))


def mesurer(df) -> dict:
    return {**empreintes(df), **{f"tendance_{n}j": qualite_tendance(df, n) for n in (5, 20, 60)}}


def main(intensites=(1.0, 0.3), mondes: int = 100):
    reels = {}
    for m in REELS:
        df = dm.charger(m, jusqua=pd.Timestamp("2020-01-01"))
        reels[m] = mesurer(df[df["time"] >= "2010-01-01"])
    reels = pd.DataFrame(reels).T
    rapport = {"reels": reels.to_dict()}
    pd.set_option("display.width", 250)
    for k in intensites:
        rng = np.random.default_rng(0)
        lignes = []
        for _ in range(mondes):
            d, _ = fabriquer(tirer_lois(rng, 2, intensite=k), jours=520)
            lignes += [mesurer(df) for df in d.values()]
        mo = pd.DataFrame(lignes)
        tab = pd.DataFrame({"vrais_min": reels.min(), "vrais_median": reels.median(), "vrais_max": reels.max(),
                            "mondes_10%": mo.quantile(0.1), "mondes_median": mo.median(),
                            "mondes_90%": mo.quantile(0.9)}).round(3)
        tab["couvert"] = [bool(mo[c].quantile(0.05) <= reels[c].median() <= mo[c].quantile(0.95)) for c in tab.index]
        tab.index = [NOMS.get(c, "suivi de tendance " + c.split("_")[1]) for c in tab.index]
        print(f"\n=== intensité des lois {k} ===")
        print(tab.to_string())
        rapport[str(k)] = tab.to_dict()
    SORTIE.write_text(json.dumps(rapport, ensure_ascii=False, indent=1, default=float), encoding="utf-8")


if __name__ == "__main__":
    main()
