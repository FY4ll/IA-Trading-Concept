"""LES YEUX DE LA TENDANCE DE FOND de MAGNETAR (19/10/2026, accord du chef de projet) : sur UNE branche (née de la
cime), des INFORMATIONS de plus, jamais une règle : elle apprend seule si et quand s'en servir.

Ce qu'elle voit en plus, pour chaque marché de son panier, à chaque regard (12 valeurs, NOMS), calculé SANS FUTUR :
seuls les jours de cotation TERMINÉS avant le jour de la décision comptent (heure du serveur ; le jour en cours n'est
jamais regardé, même définition que direction.py, déjà testée « sans futur ») :
- pour 20, 60 et 120 jours : le SIGNE de la tendance (clôture du dernier jour fermé contre celle d'il y a N jours), sa
  FORCE rapportée à l'agitation (rendement / (écart type des rendements journaliers des 60 derniers jours x racine(N)),
  bornée à +-3, divisée par 3 : direction.tendance_aux) et sa PENTE en agitations (rendement en log / agitation moyenne
  des 14 derniers jours, log(plus haut / plus bas), bornée à +-20, divisée par 5) ;
- l'ACCORD des trois (moyenne des signes) et « les trois d'accord » (+1 / -1, sinon 0) ;
- la POSITION DU PRIX DANS SA FOURCHETTE des 60 derniers jours fermés (en log : -1 au plus bas, +1 au plus haut).
Tout est en LOG : sur l'or RETOURNÉ (prix = k / prix réel, donnees.retourner) chaque valeur est exactement l'opposée
(signes, forces, pentes, accord) ou le reflet (position) de celle de l'or réel : la tendance s'inverse avec le miroir.
Source : les bougies de 15 min du marché de base (l'or à la minute utilise l'or en 15 min, son histoire commence en 2004 :
120 jours d'histoire existent dès 2005). Rien n'est lu à partir de reglages.periodes.fin_donnees.

ALLUMAGE : le réglage `yeux.tendance: true` (reglages_or.yaml) fabrique le tableau du monde (univers.tTEND [T, M, 12]) ;
seul un cerveau construit avec `tendance=True` (sa branche : tempérament « tendance ») le voit : 12 colonnes ajoutées EN
DERNIER à l'entrée de sa première couche (après la position et le journal), poids à ZÉRO à la greffe : décisions
identiques à celles de la cime (prouvé, tests/test_trois_changements.py). HYPERNOVA (reglages.yaml) : rien ne change.
"""
from __future__ import annotations

from functools import lru_cache

import numpy as np
import pandas as pd

from collapsar.ecole.precision import direction as DI
from collapsar.ecole.precision.reglages import R

VERSION = 1
DUREES = (20, 60, 120)
JOURS_AGIT = 14
JOURS_FOURCHETTE = 60
NOMS = (tuple(f"signe_{n}j" for n in DUREES) + tuple(f"force_{n}j" for n in DUREES) + tuple(f"pente_{n}j" for n in DUREES)
        + ("accord", "trois_d_accord", "position_fourchette_60j"))
NTD = len(NOMS)                       # 12 entrées ajoutées au cerveau d'une branche « tendance »
JOUR_NS = DI.JOUR_NS


def active() -> bool:
    """Le tableau de la tendance est-il fabriqué dans les mondes ? (réglage yeux.tendance, éteint par défaut)"""
    return bool(getattr(R().yeux, "tendance", False))


def activer(oui: bool = True):
    R().yeux.tendance = bool(oui)


# ============================================================================================== le calcul
def jours_ohlc(t15_ns: np.ndarray, h: np.ndarray, l: np.ndarray, c: np.ndarray):
    """(début de chaque jour serveur, plus haut, plus bas, dernière clôture du jour) à partir de bougies de 15 min."""
    t15_ns = np.asarray(t15_ns, np.int64)
    jour = t15_ns - t15_ns % JOUR_NS
    debut = np.r_[True, jour[1:] != jour[:-1]]
    ids = np.cumsum(debut) - 1
    J = int(ids[-1]) + 1 if len(ids) else 0
    H = np.full(J, -np.inf)
    L = np.full(J, np.inf)
    np.maximum.at(H, ids, np.asarray(h, np.float64))
    np.minimum.at(L, ids, np.asarray(l, np.float64))
    fin = np.r_[jour[1:] != jour[:-1], True]
    return jour[debut], H, L, np.asarray(c, np.float64)[fin]


def calcul(jours: np.ndarray, H: np.ndarray, L: np.ndarray, C: np.ndarray, t_ns: np.ndarray) -> np.ndarray:
    """[n, 12] à chaque instant t (serveur, ns ; ouverture de la bougie de décision) : seuls les jours TERMINÉS avant le
    jour de t comptent. Valeurs neutres (0) sans assez d'histoire."""
    t_ns = np.asarray(t_ns, np.int64)
    n = len(t_ns)
    out = np.zeros((n, NTD), np.float32)
    if not len(jours):
        return out
    signes, forces = DI.tendance_aux(jours, C, t_ns, DUREES)
    k = np.searchsorted(jours, t_ns - t_ns % JOUR_NS) - 1               # dernier jour fermé avant le jour de t
    kk = np.clip(k, 0, None)
    lc, lh, ll = np.log(C), np.log(H), np.log(L)
    ag = pd.Series(lh - ll).rolling(JOURS_AGIT, min_periods=JOURS_AGIT).mean().to_numpy()
    for i, N in enumerate(DUREES):
        ok = (k - N >= 0) & np.isfinite(ag[kk]) & (ag[kk] > 0)
        d = lc[kk] - lc[np.clip(k - N, 0, None)]
        out[:, i] = signes[:, i]
        out[:, 3 + i] = forces[:, i] / 3.0
        out[:, 6 + i] = np.where(ok, np.clip(d / np.where(ok, ag[kk], 1.0), -20, 20) / 5.0, 0.0)
    out[:, 9] = signes.astype(np.float32).mean(1)
    tous = (signes == signes[:, :1]).all(1) & (signes[:, 0] != 0)
    out[:, 10] = np.where(tous, signes[:, 0], 0)
    hh = pd.Series(lh).rolling(JOURS_FOURCHETTE, min_periods=JOURS_FOURCHETTE).max().to_numpy()
    bb = pd.Series(ll).rolling(JOURS_FOURCHETTE, min_periods=JOURS_FOURCHETTE).min().to_numpy()
    larg = hh[kk] - bb[kk]
    okp = (k >= 0) & np.isfinite(larg) & (larg > 0)
    out[:, 11] = np.where(okp, 2 * (lc[kk] - bb[kk]) / np.where(okp, larg, 1.0) - 1, 0.0)
    out[k < 0] = 0.0
    return np.nan_to_num(out, nan=0.0, posinf=0.0, neginf=0.0)


def source(nom: str) -> str:
    """Le marché dont on lit les jours : le marché de base (l'or à la minute -> l'or en 15 min, plus d'histoire)."""
    from collapsar.ecole.precision import donnees as D
    return D.base(nom)


@lru_cache(maxsize=16)
def _jours(nom: str):
    from collapsar.ecole.precision import donnees as D
    df = D.quinze(source(nom))
    return jours_ohlc(df["time"].values.astype("datetime64[ns]").astype(np.int64), df["high"].to_numpy(float),
                      df["low"].to_numpy(float), df["close"].to_numpy(float))


def retourner(x: np.ndarray) -> np.ndarray:
    """Les valeurs du marché RETOURNÉ (k / prix) à partir de celles du marché réel : tout s'inverse (en log), la
    position dans la fourchette aussi (testé contre le calcul direct sur le marché retourné)."""
    # en log, prix retourné = ln k - ln prix : rendements opposés ; plus haut retourné = k / plus bas, d'où
    # position retournée = 2 (ln H - ln c) / (ln H - ln L) - 1 = - position
    return (-np.asarray(x, np.float32)) + 0.0


def valeurs(nom: str, miroir: bool, t_ns: np.ndarray) -> np.ndarray:
    x = calcul(*_jours(nom), t_ns)
    return retourner(x) if miroir else x


def tableau(variantes: list[tuple[str, bool]], t_ns: np.ndarray) -> np.ndarray:
    """[T, M, 12] pour un monde (univers.py)."""
    return np.stack([valeurs(n, m, t_ns) for n, m in variantes], 1).astype(np.float32)


# ============================================================================================== la greffe
def grandir(w, n: int = NTD):
    """Poids de la 1re couche : n colonnes à ZÉRO ajoutées EN DERNIER."""
    import torch
    return torch.cat([w, torch.zeros(*w.shape[:-1], n, dtype=w.dtype, device=w.device)], -1)


def etat_avec_tendance(cerveau: dict) -> dict:
    """Les poids d'un cerveau sans la tendance -> avec (12 colonnes à zéro en dernier) ; tout le reste identique."""
    cle = "marche.0.weight"
    return {**cerveau, cle: grandir(cerveau[cle])}
