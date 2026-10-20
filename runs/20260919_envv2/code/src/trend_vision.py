"""
trend_vision.py
===============
VISION DES TENDANCES DE FOND (09/10/2026) -- de nouvelles INFORMATIONS pour AUREXIS, pas des règles.

Constat : la seule source d'avantage jamais mesurée dans ce projet est la tendance de fond (règle « professeur » :
+6,4 % sur les 12 mois cachés, 37 marchés, dans les conditions exactes d'AUREXIS, quand AUREXIS perdait). Or AUREXIS
ne voyait que ses 50 dernières bougies de 15 minutes et des résumés par unité de temps : il ne pouvait pas savoir
clairement si un marché monte depuis 1, 3, 6 ou 12 mois. Imiter le professeur sans cette information plafonnait à
70 % d'accord.

Variables (une valeur par jour, calculée sur les clôtures QUOTIDIENNES jusqu'à la VEILLE -- jamais le jour même) :
  tdf_1m / tdf_3m / tdf_6m / tdf_12m : rendement sur 21 / 63 / 126 / 252 jours de bourse divisé par la volatilité
      attendue sur cette durée (volatilité quotidienne sur 60 jours x racine de la durée) -> comparable d'un marché à
      l'autre, bornée à +-5 ;
  tdf_signe : moyenne des signes des quatre rendements (-1 = baisse sur tous les horizons, +1 = hausse partout).
L'IA décide seule quoi en faire.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

HORIZONS = {"tdf_1m": 21, "tdf_3m": 63, "tdf_6m": 126, "tdf_12m": 252}
TREND_COLUMNS = list(HORIZONS) + ["tdf_signe"]


def daily_closes(m15: pd.DataFrame) -> pd.Series:
    """Clôture de chaque jour de cotation (index = date à minuit)."""
    s = pd.Series(m15["close"].to_numpy(dtype=float), index=pd.to_datetime(m15["time"]))
    return s.resample("1D").last().dropna()


def trend_table(daily: pd.Series) -> pd.DataFrame:
    """Variables de tendance par date, connues AU DÉBUT de cette date (calculées sur la veille et avant)."""
    d = daily.astype(float)
    vol = d.pct_change().rolling(60, min_periods=20).std()
    out = {}
    signs = []
    for name, h in HORIZONS.items():
        r = d / d.shift(h) - 1.0
        out[name] = (r / (vol * np.sqrt(h))).clip(-5, 5)
        signs.append(np.sign(r))
    sg = pd.concat(signs, axis=1)
    out["tdf_signe"] = sg.mean(axis=1, skipna=True)
    t = pd.DataFrame(out).shift(1)                      # jamais l'information du jour même
    return t.replace([np.inf, -np.inf], np.nan)


def add_trend_vision(df: pd.DataFrame, daily: pd.Series | None = None) -> pd.DataFrame:
    """Ajoute TREND_COLUMNS à `df` (bougies M15, colonne `time`). `daily` = clôtures quotidiennes de l'HISTORIQUE
    COMPLET du marché (sinon tirées de `df` lui-même, moins d'historique). Inconnu -> 0 (neutre)."""
    if daily is None:
        daily = daily_closes(df)
    tab = trend_table(daily)
    days = pd.to_datetime(df["time"]).dt.normalize()
    vals = tab.reindex(days.to_numpy())
    for c in TREND_COLUMNS:
        df[c] = vals[c].fillna(0.0).to_numpy(dtype=np.float64)   # float64 : statistiques enregistrables (incident 09/10 18h20)
    return df
