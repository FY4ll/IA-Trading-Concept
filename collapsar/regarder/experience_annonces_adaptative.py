"""Expérience du 14/10 : l'IA des annonces qui s'ADAPTE plus vite (comme un trader qui sent que le marché change).

Au lieu de réapprendre chaque 1er janvier avec toutes les années à poids égal, elle réapprend CHAQUE MOIS sur tout le
passé, en donnant plus de poids aux mois récents (mémoire : un mois ancien compte deux fois moins tous les X ans).
Si les surprises se mettent à moins payer, elle réduit d'elle-même. Mesure : argent simple (comme
experience_annonces_ia) par période, et lien prévu/réel.
Depuis Test_IA : venv_gpu\\Scripts\\python.exe -u -m collapsar.regarder.experience_annonces_adaptative
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd

from collapsar.regarder.experience_annonces_ia import RISQUE, entrees, situations

MEMOIRES = {"courte (1 an)": 1.0, "moyenne (2 ans)": 2.0, "longue (tout pareil)": None}
PERIODES = {"2013-2019": ("2013", "2020"), "2020-2022": ("2020", "2023"), "2023-04/2025": ("2023", "2025-04-08")}


def predictions_adaptatives(x: pd.DataFrame, X: np.ndarray, y: np.ndarray, demi_vie: float | None,
                            debut: str = "2013-01-01", apprendre_de: str | None = None) -> np.ndarray:
    """Conviction (bornée, nulle si les frais mangent le gain) de chaque situation, apprise sur le passé seul."""
    conv = np.full(len(x), np.nan)
    temps = x["temps"].to_numpy()
    for mois in pd.date_range(debut, x["temps"].max() + pd.offsets.MonthBegin(1), freq="MS"):
        te = (temps >= np.datetime64(mois)) & (temps < np.datetime64(mois + pd.offsets.MonthBegin(1)))
        if not te.any():
            continue
        ap = temps < np.datetime64(mois)
        if apprendre_de is not None:                       # n'apprend que depuis cette date (époque choisie)
            ap &= temps >= np.datetime64(pd.Timestamp(apprendre_de))
        if ap.sum() < 200:
            continue
        age = (np.datetime64(mois) - temps[ap]) / np.timedelta64(365, "D")
        poids = np.ones(ap.sum()) if demi_vie is None else 0.5 ** (age / demi_vie)
        moy = np.average(X[ap], axis=0, weights=poids)
        et = np.sqrt(np.average((X[ap] - moy) ** 2, axis=0, weights=poids)) + 1e-9
        A = np.c_[(X[ap] - moy) / et, np.ones(ap.sum())]
        Aw = A * poids[:, None]
        w = np.linalg.solve(A.T @ Aw + 1e3 * np.eye(A.shape[1]) * poids.mean(), Aw.T @ y[ap])
        pa = A @ w
        echelle = np.sqrt(np.average(pa ** 2, weights=poids)) + 1e-12
        p = np.c_[(X[te] - moy) / et, np.ones(te.sum())] @ w
        conv[te] = np.clip(p / echelle, -2, 2) * (np.abs(p) > 2 * x.loc[te, "frais"].to_numpy())
    return conv


def main():
    global PERIODES
    x = situations()
    X, y = entrees(x), np.clip(x["cible"].to_numpy(), -5, 5)
    debut = "2013-01-01"
    if os.environ.get("COLLAPSAR_CALENDRIER", "ff") == "mt5":       # valeurs attendues seulement depuis 2017
        debut = "2019-01-01"
        PERIODES = {"2019-2022": ("2019", "2023"), "2023-09/2025": ("2023", "2025-10")}
    for nom, demi_vie in MEMOIRES.items():
        conv = predictions_adaptatives(x, X, y, demi_vie, debut=debut)
        ok = np.isfinite(conv)
        d = x[ok].assign(gain=conv[ok] * y[ok] - np.abs(conv[ok]) * x.loc[ok, "frais"])
        par = d.groupby("id").agg(temps=("temps", "first"), gain=("gain", "mean"))
        print(f"\nmémoire {nom} :")
        for periode, (de, a) in PERIODES.items():
            p = par[(par["temps"] >= de) & (par["temps"] < a)]
            mois = (p.set_index("temps")["gain"] * RISQUE * 100).groupby(pd.Grouper(freq="ME")).sum()
            cumul = mois.cumsum()
            dd = d[(d["temps"] >= de) & (d["temps"] < a)]
            lien = np.corrcoef(conv[ok][(x.loc[ok, "temps"] >= de) & (x.loc[ok, "temps"] < a)],
                               y[ok][(x.loc[ok, "temps"] >= de) & (x.loc[ok, "temps"] < a)])[0, 1] * 100
            print(f"   {periode:13s} : lien {lien:+.2f} % | {mois.mean():+.2f} %/mois, mois positifs {(mois > 0).mean():.0%}, "
                  f"pire mois {mois.min():+.2f} %, baisse max {(cumul.cummax() - cumul).max():.1f} % "
                  f"({(dd['gain'] != 0).mean():.0%} des situations tradées)", flush=True)


if __name__ == "__main__":
    main()
