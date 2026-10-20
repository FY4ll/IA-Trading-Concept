"""Le JUMEAU AU HASARD : la référence de toute validation (core, 20/10/2026).

Idée reprise de MAGNETAR (ecole/precision/cerveau.politique, jeu.Examen.jouer_un), rendue indépendante de tout cerveau :
le jumeau fait EXACTEMENT les mêmes gestes que l'IA (même moment, même taille de risque, même distance de stop et
d'objectif, même gestion), mais le SENS de chaque trade est tiré à pile ou face. Il paie donc les mêmes frais et
subit les mêmes murs FTMO. Ce que l'IA gagne de plus que lui vient de son choix du sens (et seulement de lui).

Usage :
    jum = intentions_jumeau(intentions, graine)      # mêmes intentions, sens à pile ou face
    ... rejouer `intentions` et `jum` dans le même simulateur ...
    comparer(gains_ia, gains_jumeau, groupes)        # avantage moyen, incertitude, force (avantage / incertitude)

Une intention est un dict avec au moins « sens » (+1 achat, -1 vente) et, si on veut des niveaux, « entree »,
« stop », « objectifs » (liste) en PRIX : ils sont retournés autour du prix d'entrée (même distance, autre côté).
Plusieurs jumeaux (graines différentes) réduisent le bruit du tirage : `jumeaux(intentions, k)`.
"""
from __future__ import annotations

import math

import numpy as np


def _retourner_niveau(niveau, entree):
    if niveau is None or entree is None:
        return niveau
    if isinstance(niveau, float) and math.isnan(niveau):
        return niveau
    return 2 * entree - niveau


def intentions_jumeau(intentions: list[dict], graine: int) -> list[dict]:
    """Les mêmes intentions, sens tiré à pile ou face (probabilité 1/2, indépendante de tout). Quand le sens change,
    stop et objectifs sont placés à la même distance de l'entrée, de l'autre côté."""
    rng = np.random.default_rng(graine)
    out = []
    for it in intentions:
        j = dict(it)
        if rng.random() < 0.5:
            j["sens"] = -int(it["sens"])
            e = it.get("entree")
            if "stop" in it:
                j["stop"] = _retourner_niveau(it["stop"], e)
            if "objectifs" in it and it["objectifs"] is not None:
                j["objectifs"] = [_retourner_niveau(o, e) for o in it["objectifs"]]
        j["jumeau"] = True
        out.append(j)
    return out


def jumeaux(intentions: list[dict], k: int, graine: int = 0) -> list[list[dict]]:
    """k jumeaux indépendants (graines graine .. graine + k - 1)."""
    return [intentions_jumeau(intentions, graine + i) for i in range(k)]


def sens_au_hasard(n: int, graine: int) -> np.ndarray:
    """n sens à pile ou face (+1 / -1), pour un jumeau vectorisé."""
    return np.where(np.random.default_rng(graine).random(n) < 0.5, 1, -1)


def incertitude_groupes(d: np.ndarray, groupes) -> float:
    """Incertitude d'une moyenne quand les mesures vont par groupes dépendants (ex. or réel et or retourné d'une
    même période) : écart type des moyennes de groupe / racine du nombre de groupes (comme MAGNETAR)."""
    d, gr = np.asarray(d, float), np.asarray(groupes)
    m = np.asarray([d[gr == k].mean() for k in np.unique(gr)])
    return float(m.std(ddof=1) / math.sqrt(len(m))) if len(m) > 1 else float("nan")


def comparer(gains_ia, gains_jumeau, groupes=None) -> dict:
    """Avantage de l'IA sur son jumeau, mesure par mesure (mêmes périodes, appariées).
    `gains_jumeau` : [n] ou [k, n] (plusieurs jumeaux : leur moyenne). Rend l'avantage moyen, son incertitude
    (écart type / racine de n, ou par groupes dépendants), la force (avantage / incertitude ; > 2 = net) et le gain
    ABSOLU de l'IA (un avantage sur le hasard avec un gain négatif ne fait pas vivre)."""
    g = np.asarray(gains_ia, float)
    j = np.asarray(gains_jumeau, float)
    if j.ndim == 2:
        j = j.mean(0)
    if g.shape != j.shape:
        raise ValueError(f"mesures non appariées : {g.shape} contre {j.shape}")
    d = g - j
    n = len(d)
    if groupes is not None:
        inc = incertitude_groupes(d, groupes)
    else:
        inc = float(d.std(ddof=1) / math.sqrt(n)) if n > 1 else float("nan")
    av = float(d.mean()) if n else float("nan")
    return {"avantage": av, "incertitude": inc,
            "force": float(av / inc) if inc and inc > 0 and math.isfinite(inc) else 0.0,
            "gain_ia": float(g.mean()) if n else float("nan"), "gain_jumeau": float(j.mean()) if n else float("nan"),
            "mesures": int(n), "net": bool(inc and math.isfinite(inc) and av > 2 * inc and g.mean() > 0)}
