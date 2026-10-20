"""Test de vérité de l'ÉCOLE (14/10/2026, « faut vraiment qu'on réussisse à la créer ») : sait-elle trouver un
avantage quand il EXISTE ?

Un faux euro-dollar (même agitation que le vrai : ~0,7 % par jour, mêmes frais, mêmes heures, week-ends) où une
TENDANCE est cachée : le prix dérive dans un sens pendant en moyenne 10 jours de marché, puis change de sens au hasard.
La dérive vaut 0,3 fois l'agitation d'un jour : invisible sur une bougie de 15 minutes, nette sur plusieurs jours,
exactement le genre d'avantage que gagnent les robots qui suivent les tendances.
- Si l'école trouve cet avantage (gain net sur les années de contrôle, jamais apprises) : elle sait apprendre, il
  faut lui montrer les marchés et les durées où l'avantage existe vraiment.
- Si elle ne le trouve pas : c'est l'ÉCOLE qui est en cause, à réparer avant tout.
Aucune règle n'est donnée à l'élève : elle ne sait pas qu'une tendance est cachée.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

AGITATION_BOUGIE = 0.0007            # ~0,7 % par jour de marché (96 bougies)
DERIVE_JOUR = 0.3                    # dérive par jour, en part de l'agitation d'un jour
DUREE_TENDANCE_JOURS = 10.0          # durée moyenne d'une tendance, en jours de marché


def marche_cache(graine: int = 0, debut="2010-01-04", fin="2023-01-01", derive_jour: float = DERIVE_JOUR,
                 duree_jours: float = DUREE_TENDANCE_JOURS) -> pd.DataFrame:
    """Bougies de 15 minutes du lundi 00:00 au vendredi 23:45 (heure serveur), avec une tendance cachée."""
    t = pd.date_range(debut, fin, freq="15min", inclusive="left")
    t = t[t.dayofweek < 5]
    n = len(t)
    rng = np.random.default_rng(graine)
    change = rng.random(n) < 1.0 / (duree_jours * 96)
    sens = np.where(np.cumsum(change) % 2 == 0, 1.0, -1.0) * (1 if rng.random() < 0.5 else -1)
    derive = sens * derive_jour * AGITATION_BOUGIE * np.sqrt(96) / 96
    r = derive + rng.normal(0.0, AGITATION_BOUGIE, n)
    c = 1.2 * np.exp(np.cumsum(r))
    o = np.r_[1.2, c[:-1]]
    meche = np.abs(rng.normal(0.0, AGITATION_BOUGIE * 0.4, (2, n)))
    h = np.maximum(o, c) * (1 + meche[0])
    l = np.minimum(o, c) * (1 - meche[1])
    return pd.DataFrame({"time": t, "open": o, "high": h, "low": l, "close": c, "volume": 1.0})
