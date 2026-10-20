"""
shared_data.py
===============
DONNÉES D'ENTRAÎNEMENT PARTAGÉES (08/10/2026). Avant : le programme principal envoyait à CHAQUE copie
d'entraînement sa propre copie du jeu d'entraînement (555 000 bougies x 200 variables, ~0,5 Go), sérialisée
puis recopiée en mémoire par l'environnement (~1,2 Go par copie, plus le paquet à envoyer côté principal).
Maintenant les variables sont écrites UNE FOIS sur le disque (float32) ; chaque copie les lit en place
(np.memmap en lecture seule) : Windows garde une seule version en mémoire pour toutes les copies.
Seules les petites colonnes (temps, prix, ATR brut, numéro de marché) voyagent avec la copie.
"""
from __future__ import annotations
import glob
import hashlib
import os
import time

import numpy as np
import pandas as pd

SHARED_DIR = os.path.join("data", "partage")


class SharedFrame:
    """Jeu d'entraînement partagé : petites colonnes (DataFrame) + variables sur disque (memmap)."""

    def __init__(self, small: pd.DataFrame, path: str, shape: tuple, columns: list):
        self.small = small
        self.path = path
        self.shape = tuple(shape)
        self.columns = list(columns)

    def __len__(self):
        return self.shape[0]

    def load(self):
        arr = np.memmap(self.path, dtype=np.float32, mode="r", shape=self.shape)
        return self.small, arr


def share_frame(df: pd.DataFrame, cols: list, tag: str = "train", keep: int = 4) -> SharedFrame:
    """Écrit df[cols] en float32 sur le disque (une fois par contenu) et retourne un SharedFrame."""
    os.makedirs(SHARED_DIR, exist_ok=True)
    cols = list(cols)
    arr = np.ascontiguousarray(df[cols].to_numpy(dtype=np.float32))
    h = hashlib.sha1()
    h.update(str((arr.shape, cols)).encode())
    h.update(arr[:: max(1, len(arr) // 2000)].tobytes())          # échantillon régulier : rapide et fiable
    path = os.path.join(SHARED_DIR, f"{tag}_{h.hexdigest()[:16]}.f32")
    if not os.path.exists(path) or os.path.getsize(path) != arr.nbytes:
        tmp = path + ".tmp"
        arr.tofile(tmp)
        os.replace(tmp, path)
    os.utime(path, None)
    # ménage : garde les `keep` fichiers les plus récents de ce type (les copies en cours lisent le leur)
    old = sorted(glob.glob(os.path.join(SHARED_DIR, f"{tag}_*.f32")), key=os.path.getmtime, reverse=True)[keep:]
    for p in old:
        try:
            if time.time() - os.path.getmtime(p) > 3600:
                os.remove(p)
        except OSError:
            pass
    small = df[[c for c in df.columns if c not in set(cols)]].copy()
    return SharedFrame(small, path, arr.shape, cols)
