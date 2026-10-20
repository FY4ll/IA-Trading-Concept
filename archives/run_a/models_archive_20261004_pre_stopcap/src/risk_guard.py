"""
risk_guard.py
==============
Filet de sécurité INDÉPENDANT du réseau appris : détecte des conditions de
marché anormales sur les dernières bougies connues (mouvement de prix ou
volatilité extrêmes par rapport à l'historique récent) et force une
RÉDUCTION de l'exposition en démo, quelle que soit la décision de l'agent
(ou de l'ensemble multi-styles).

Volontairement une règle STATISTIQUE simple, pas un modèle appris : le but
est justement de ne pas dépendre du même type de réseau qui pourrait, lui,
être pris au dépourvu par une situation inédite -- une seconde ligne de
défense qui ne partage aucune faiblesse avec la première.
"""
from __future__ import annotations
import logging
import numpy as np
import pandas as pd

log = logging.getLogger("risk_guard")


def anomaly_scale(df: pd.DataFrame, lookback: int = 200, z_threshold: float = 4.0) -> tuple[float, dict]:
    """Retourne (scale, info) où scale ∈ [0, 1] multiplie l'exposition
    désirée : 1.0 = rien d'anormal détecté, décroît vers 0.0 si le dernier
    rendement ou la volatilité récente s'écarte fortement (z-score) de son
    historique récent. `info` détaille les z-scores calculés, pour le
    logging et le diagnostic.

    Un DataFrame sans colonne 'close' (appelant malformé, ou DataFrame de
    contexte inattendu) retombe sur le même comportement qu'un historique
    insuffisant -- scale=1.0, aucune réduction -- plutôt que de lever une
    KeyError qui interromprait toute la boucle de décision live. Ce filet
    de sécurité ne doit jamais lui-même devenir une source de panne.
    """
    if "close" not in df.columns:
        log.warning("anomaly_scale : colonne 'close' absente du DataFrame -- scale neutre (1.0) utilisé.")
        return 1.0, {"reason": "colonne 'close' absente du DataFrame"}

    closes = df["close"].values
    if len(closes) < lookback + 2:
        return 1.0, {"reason": "historique insuffisant pour évaluer l'anomalie"}

    returns = np.diff(closes) / closes[:-1]
    recent = returns[-lookback:]
    mean, std = recent.mean(), recent.std() + 1e-9
    last_return_z = abs((returns[-1] - mean) / std)

    abs_returns = np.abs(returns[-lookback:])
    vol_recent = abs_returns[:-1]
    vol_mean, vol_std = vol_recent.mean(), vol_recent.std() + 1e-9
    last_vol_z = abs((abs_returns[-1] - vol_mean) / vol_std)

    worst_z = max(last_return_z, last_vol_z)
    if worst_z <= z_threshold:
        scale = 1.0
    else:
        # décroît linéairement de 1.0 (au seuil) à 0.0 (deux fois le seuil),
        # puis reste à 0 au-delà -- jamais de coupure brutale à pile le seuil.
        scale = max(0.0, 1.0 - (worst_z - z_threshold) / z_threshold)

    return float(scale), {
        "last_return_z": float(last_return_z), "last_vol_z": float(last_vol_z),
        "z_threshold": z_threshold, "scale": float(scale),
    }
