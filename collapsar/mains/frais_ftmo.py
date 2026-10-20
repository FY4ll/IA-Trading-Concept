"""Frais d'un trade complet FIDÈLES AU COMPTE FTMO, à chaque époque (16/10/2026).

Mesure : écarts relevés sur le compte d'essai FTMO (mains/conditions_ftmo.json, 15/10/2026 03h34 serveur = heures
d'Asie, donc plutôt LARGES pour les indices américains). Les fiches (mains/fiches.py) comptaient 0,012 % sur les indices
US : ~2 x le relevé (US500 0,0078 %, US100 0,0066 %, US30 0,0052 %).
Modèle : un écart de courtier est à peu près constant en POINTS -> écart en part du prix à la date t =
écart relevé (part) x prix au relevé / prix(t). Les vieilles années (prix bas) coûtent donc plus cher, les récentes
moins. Commission : devises = fiche (déjà calée sur FTMO), indices / énergies / cryptos = 0 (FTMO), métaux = 0,0014 %
aller-retour (prudence) ; cryptos : commission FTMO 0,0325 % par côté.
Prudence (audit du 16/10, défaut 5) : l'ancien « x 1,25 de glissement » sur TOUT le frais est retiré : le glissement
réel mesuré au marché est nul (AUREX chez Tradeco, 11 ordres). Le réglage MARGE_PRUDENCE (multiplie l'ÉCART seulement,
jamais la commission, qui est un tarif fixe) permet de remettre une marge si on le veut ; 1,0 = frais mesurés.
Le glissement des STOPS (mesuré, ~+0,5 fiche) est compté par les moteurs qui simulent les stops, pas ici.
Ne remplace PAS fiches.py (utilisée par l'école et la démo).
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

import numpy as np

from collapsar.mains.fiches import fiche

MESURE = Path(__file__).with_name("conditions_ftmo.json")
MARGE_PRUDENCE = 1.0          # x sur les écarts mesurés (1,25 jusqu'au 16/10 : prudence non mesurée, retirée)
GLISSEMENT = MARGE_PRUDENCE   # ancien nom, gardé pour les programmes qui l'importent
# crypto : commission FTMO 0,0325 % PAR CÔTÉ depuis le 28/07/2025 (ftmo.com, « FTMO enhances crypto trading ») = 0,065 %
# aller-retour, EN PLUS de l'écart (oubliée jusqu'au 16/10 03h : les tests crypto d'avant sous-estimaient les frais)
COMMISSION = {"metal": 0.000014, "indice": 0.0, "energie": 0.0, "crypto": 0.00065, "obligation": 0.0}


@lru_cache(maxsize=1)
def _mesures() -> dict:
    return json.loads(MESURE.read_text(encoding="utf-8"))["marches"]


@lru_cache(maxsize=64)
def _prix_au_releve(sym: str) -> float:
    from collapsar.donnees import marches as dm
    import pandas as pd
    df = dm.charger(sym, pd.Timestamp("2026-10-16"))
    return float(df["close"].iloc[-1])


def frais(sym: str, prix) -> np.ndarray | float:
    """Coût d'un trade complet (aller-retour) en part du prix, au(x) prix donné(s)."""
    f = fiche(sym)
    m = _mesures().get(f.nom)
    if f.famille == "devise" or m is None:
        return f.frais * MARGE_PRUDENCE * np.ones_like(np.asarray(prix, float))
    ecart = m["ecart_pct"] / 100 * _prix_au_releve(sym) / np.asarray(prix, float)
    return ecart * MARGE_PRUDENCE + COMMISSION.get(f.famille, 0.0)
