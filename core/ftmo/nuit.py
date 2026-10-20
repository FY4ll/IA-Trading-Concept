"""Frais de nuit FIDÈLES À CHAQUE ÉPOQUE (15/10/2026), calés sur la TABLE FTMO relevée (16/10/2026, audit, défaut 11).

Un CFD gardé après minuit paie (ou reçoit) chaque nuit un taux annuel / 360 :
- devises : l'écart de taux d'intérêt entre les deux devises (acheter l'euro-dollar = recevoir le taux de l'euro,
  payer celui du dollar), plus la marge du courtier ;
- indices, métaux, obligations : le taux de la devise de cotation (l'achat le paie, la vente le reçoit), moins un
  décalage propre au marché (dividendes d'un indice, taux de prêt de l'or...), plus la marge ;
- crypto : le taux fixe relevé (30 %/an, achat comme vente) ; énergies et marchés inventés : le taux fixe de leur
  fiche (voir plus bas).
Table FTMO (compte d'essai Swing, 15/10/2026 03h34, mains/conditions_ftmo.json), ACHAT ET VENTE SÉPARÉS : pour chaque
marché relevé, on en tire
  marge    m = (achat relevé + vente relevée) / 2          (ce que le courtier prend, quelle que soit l'époque)
  décalage d = base du modèle au relevé - (achat relevé - vente relevée) / 2
puis à l'instant t : achat = base(t) - d + m ; vente = -(base(t) - d) + m. Au jour du relevé, on retrouve EXACTEMENT la
table (achat et vente) ; les autres années suivent les taux de l'époque (collapsar/donnees/taux.py, le mois précédent,
publié). Avant le 16/10 : une marge par famille, la même pour l'achat et la vente (US500 achat 7,6 %/an contre 5,7 %
relevé, vente -0,1 % contre +2,1 % ; or achat 7,8 % contre 5,3 %).
Garde-fou : un décalage de plus de DECALAGE_MAX (UK100 : 13 %/an le jour du relevé, sans doute un dividende ponctuel)
n'est PAS prolongé dans le passé (il offrirait ~9 %/an aux acheteurs de 2015) : décalage 0, marge mesurée gardée.
Énergies : FTMO suit la courbe des contrats à terme (pétrole : vente ~90 %/an, achat REÇU ~20 %/an le 15/10), qui
change de signe selon les années -> taux fixes de la fiche (relevé, sans jamais offrir de frais reçus).
Marchés sans relevé (obligations...) : marge de la famille (MARGE), même valeur à l'achat et à la vente.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

from core.ftmo.fiches import DEVISES, MIROIR, Fiche

# Marges médianes par famille (essai Swing, 15/10/2026 03h40) : seulement pour un marché absent de la table FTMO.
MARGE = {"devise": 0.0146, "indice": 0.0375, "metal": 0.0395, "obligation": 0.02}
MESURE = Path(__file__).with_name("conditions_ftmo.json")
DECALAGE_MAX = 0.05                  # %/an : au-delà, le décalage relevé n'est pas prolongé dans le passé
TABLE_FIXE = ("crypto",)             # familles dont le taux relevé est fixe (pas lié aux taux d'intérêt)


@lru_cache(maxsize=1)
def _taux() -> pd.DataFrame | None:
    from core import taux
    try:
        return taux.charger()
    except FileNotFoundError:
        return None


@lru_cache(maxsize=1)
def _table() -> tuple[dict, pd.Timestamp | None]:
    """(marchés relevés, date du relevé) ; vide si le fichier manque."""
    try:
        d = json.loads(MESURE.read_text(encoding="utf-8"))
        return d.get("marches", {}), pd.Timestamp(d["quand"]).normalize()
    except (FileNotFoundError, KeyError, ValueError):
        return {}, None


def _base(f: Fiche, nom: str, jours: pd.DataFrame) -> np.ndarray:
    """Taux de base du modèle (acheter paie la base) pour chaque ligne de `jours` (taux par devise)."""
    if f.famille == "devise" and nom[:3] in DEVISES and nom[3:] in DEVISES:
        return (jours[nom[3:]] - jours[nom[:3]]).to_numpy()          # acheter la paire : payer la cotation
    if f.cotation in jours:
        return jours[f.cotation].to_numpy()
    return np.full(len(jours), np.nan)


def marge_et_decalage(f: Fiche, nom_ftmo: str, nom: str) -> tuple[float, float]:
    """(marge m, décalage d) du marché, tirés de la table FTMO ; sinon (marge de la famille, 0)."""
    table, quand = _table()
    r = _taux()
    m = table.get(nom_ftmo)
    if m is None or m.get("nuit_achat") is None or m.get("nuit_vente") is None or r is None or quand is None:
        return MARGE.get(f.famille, 0.0), 0.0
    na, nv = float(m["nuit_achat"]), float(m["nuit_vente"])
    jour = r.reindex(pd.DatetimeIndex([quand]), method="ffill")
    base = float(_base(f, nom, jour)[0])
    if not np.isfinite(base):
        return MARGE.get(f.famille, 0.0), 0.0
    decalage = base - (na - nv) / 2
    if abs(decalage) > DECALAGE_MAX:
        decalage = 0.0
    return (na + nv) / 2, decalage


def taux_nuit(f: Fiche, temps: pd.DatetimeIndex) -> tuple[np.ndarray, np.ndarray]:
    """(achat, vente) : taux annuels payés par une position acheteuse / vendeuse à chaque instant (négatif = reçu).
    Sans taux connus pour un instant : les taux fixes de la fiche."""
    T = len(temps)
    fixe = np.full(T, f.nuit_achat), np.full(T, f.nuit_vente)
    miroir = f.fichier.endswith(MIROIR)
    nom = f.fichier[:-len(MIROIR)] if miroir else f.fichier
    nom_ftmo = f.nom[:-len(MIROIR)] if f.nom.endswith(MIROIR) else f.nom
    if f.famille in TABLE_FIXE:
        m = _table()[0].get(nom_ftmo)
        if m is None or m.get("nuit_achat") is None or m.get("nuit_vente") is None:
            return fixe
        achat, vente = np.full(T, float(m["nuit_achat"])), np.full(T, float(m["nuit_vente"]))
        return (vente, achat) if miroir else (achat, vente)
    r = _taux()
    if r is None or f.famille not in MARGE:
        return fixe
    jours = r.reindex(pd.DatetimeIndex(temps).normalize(), method="ffill")
    base = _base(f, nom, jours)
    m, d = marge_et_decalage(f, nom_ftmo, nom)
    achat, vente = base - d + m, -(base - d) + m
    if miroir:                                  # le marché retourné : acheter le miroir = vendre l'original
        achat, vente = vente, achat
    achat = np.where(np.isfinite(achat), achat, fixe[0])
    vente = np.where(np.isfinite(vente), vente, fixe[1])
    return achat, vente
