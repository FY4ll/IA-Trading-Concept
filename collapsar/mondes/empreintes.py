"""Les EMPREINTES d'un marché : les propriétés statistiques que la recherche retrouve sur tous les marchés réels
(Rama Cont, « Empirical properties of asset returns: stylized facts », 2001). Un monde inventé n'a le droit de servir
à l'école que s'il les reproduit : sinon elle apprendrait un monde qui n'existe pas.

Pour un marché (bougies de 15 minutes) :
- agitation d'un jour (écart type des variations journalières) ;
- queues épaisses : excès d'aplatissement des variations de 15 minutes et d'un jour (0 = courbe en cloche) ;
- pas de mémoire du sens : corrélation d'une variation avec la suivante (15 min, jour), proche de 0 ;
- agitation en vagues (Engle) : corrélation des variations ABSOLUES d'un jour avec celles 1, 5, 20 et 60 jours plus
  tard, qui décroît lentement ;
- tendances ou retours au calme : rapport de variance sur 1 semaine et 1 mois (1 = hasard, > 1 = les mouvements se
  prolongent, < 1 = ils reviennent) ;
- rythme de la journée : agitation de l'heure la plus agitée / de la plus calme.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def _ac(x: np.ndarray, k: int) -> float:
    x = x[np.isfinite(x)]
    if len(x) <= k + 10:
        return float("nan")
    a, b = x[:-k] - x[:-k].mean(), x[k:] - x[k:].mean()
    return float((a * b).mean() / (a.std() * b.std() + 1e-18))


def _aplatissement(x: np.ndarray) -> float:
    x = x[np.isfinite(x)]
    x = x - x.mean()
    return float((x ** 4).mean() / (x ** 2).mean() ** 2 - 3)


def empreintes(df: pd.DataFrame) -> dict:
    t = pd.DatetimeIndex(df["time"])
    c = pd.Series(np.log(df["close"].to_numpy(np.float64)), index=t)
    r15 = c.diff().to_numpy()[1:]
    r15 = r15[np.abs(r15) < 0.2]                                   # trous de données aberrants
    jour = c.groupby(t.normalize()).last()
    jour = jour[jour.index.dayofweek < 5]
    rj = jour.diff().dropna().to_numpy()
    ra = np.abs(rj)
    var_j = rj.var()

    def rapport(n):
        s = jour.to_numpy()
        rn = s[n:] - s[:-n]
        return float(rn.var() / (n * var_j))

    h = t.hour[1:]
    h = h[: len(r15)] if len(h) >= len(r15) else h
    prof = pd.Series(np.abs(c.diff().to_numpy()[1:]), index=t.hour[1:]).groupby(level=0).mean()
    prof = prof[prof > 0]
    return {"agitation_jour_pct": float(np.sqrt(var_j) * 100),
            "queues_15min": _aplatissement(r15), "queues_jour": _aplatissement(rj),
            "suite_15min": _ac(r15, 1), "suite_jour": _ac(rj, 1),
            "vagues_1j": _ac(ra, 1), "vagues_5j": _ac(ra, 5), "vagues_20j": _ac(ra, 20), "vagues_60j": _ac(ra, 60),
            "rapport_semaine": rapport(5), "rapport_mois": rapport(21),
            "rythme_journee": float(prof.max() / prof.min()) if len(prof) > 1 else float("nan")}


NOMS = {"agitation_jour_pct": "agitation d'un jour (%)", "queues_15min": "queues épaisses (15 min)",
        "queues_jour": "queues épaisses (jour)", "suite_15min": "mémoire du sens (15 min)",
        "suite_jour": "mémoire du sens (jour)", "vagues_1j": "agitation en vagues (1 jour)",
        "vagues_5j": "agitation en vagues (5 jours)", "vagues_20j": "agitation en vagues (20 jours)",
        "vagues_60j": "agitation en vagues (60 jours)", "rapport_semaine": "tendance/retour (1 semaine)",
        "rapport_mois": "tendance/retour (1 mois)", "rythme_journee": "rythme de la journée (max/min)"}
