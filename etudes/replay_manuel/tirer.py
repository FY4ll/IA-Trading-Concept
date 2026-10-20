"""Tirage des séances de REPLAY MANUEL (20/10/2026) : 40 dates de départ tirées au hasard dans la zone d'exploration
2012-01-02 -> 2019-11-29 (jours de semaine), graine publique 20261020 : le tirage est refait à l'identique par n'importe
qui. Écrit sessions.csv (ordre imposé). Ne relancer que pour vérifier (même graine = même liste).

    venv_gpu\\Scripts\\python.exe etudes\\replay_manuel\\tirer.py
"""
from pathlib import Path

import numpy as np
import pandas as pd

GRAINE = 20261020
N = 40
ICI = Path(__file__).resolve().parent

jours = pd.bdate_range("2012-01-02", "2019-11-29")
rng = np.random.default_rng(GRAINE)
choix = jours[np.sort(rng.choice(len(jours), size=N, replace=False))]
ordre = rng.permutation(N)                                  # ordre de passage tiré au hasard aussi
df = pd.DataFrame({"seance": np.arange(1, N + 1), "date_depart": choix[ordre].strftime("%Y-%m-%d"),
                   "faite_le": "", "trades_pris": "", "remarque": ""})
df.to_csv(ICI / "sessions.csv", index=False, sep=";")
print(df.to_string(index=False))
