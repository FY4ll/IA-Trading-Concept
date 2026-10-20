"""La VUE D'ENSEMBLE (14/10/2026 après-midi) : une autre façon de regarder, qui prend du recul.

Pourquoi : les yeux « graphique brut » (384 bougies) reconnaissent chaque moment de leurs années apprises et récitent
la suite (+30 à +97 % du risque par coup sur ces années, rien sur 2020-2022 : lien sur le sens -0,5 %). Le seul outil
du projet qui ait eu un lien réel sur le sens (3-4 %, moteur de prédiction de Run A) regardait une vue résumée.

Ce qu'elle voit, à la clôture de chaque bougie de 15 minutes (que des prix bruts, aucun indicateur de trader) :
- de combien le prix a bougé sur 15 min, 1 h, 4 h, 16 h, 1 jour, 1 semaine, 1 mois, 3 mois, 6 mois, rapporté à
  son agitation habituelle ;
- où est le prix dans sa fourchette du jour, de la semaine, du mois ;
- si le marché est plus agité ou plus calme que d'habitude ;
- l'heure, le jour, la famille du marché, ce que coûte un trade ;
- ce que font AU MÊME MOMENT les grands marchés : euro-dollar, dollar-yen, or, actions américaines, pétrole, bitcoin.
Les années en bougies d'1 heure (avant ~2010) ne sont pas vues par cette vue (marquées non valides).
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import torch

from collapsar.mains.fiches import fiche
from collapsar.yeux.graphique import Graphique

PAS = (1, 4, 16, 64, 96, 480, 2100, 6300, 12600)          # 15 min -> 6 mois, en bougies de 15 minutes
FOURCHETTES = (96, 480, 2100)                             # jour, semaine, mois
GRANDS = ("EURUSD", "USDJPY", "XAUUSD", "USA500IDXUSD", "LIGHTCMDUSD", "BTCUSD")
PAS_GRANDS = (16, 96, 480, 2100)
FAMILLES = ("devise", "metal", "indice", "energie", "crypto", "obligation")
N_PROPRES = len(PAS) + len(FOURCHETTES) + 2 + 4 + len(FAMILLES) + 1
N_ENTREES = N_PROPRES + len(GRANDS) * len(PAS_GRANDS)


def _mouvements(c: np.ndarray, h: np.ndarray, l: np.ndarray, pas=PAS) -> tuple[np.ndarray, np.ndarray]:
    """Mouvements sur chaque durée, rapportés à l'agitation habituelle ; et l'agitation (taille moyenne de bougie)."""
    u = pd.Series(h - l).rolling(64, min_periods=16).mean().to_numpy()
    sc = pd.Series(c)
    out = []
    for k in pas:
        with np.errstate(divide="ignore", invalid="ignore"):
            r = (c - sc.shift(k).to_numpy()) / (u * np.sqrt(k))
        out.append(np.clip(np.nan_to_num(r, nan=0.0, posinf=0.0, neginf=0.0), -5, 5))
    return np.stack(out, 1), u


class VueDEnsemble:
    def __init__(self, g: Graphique, appareil=None):
        self.g = g
        dev = torch.device(appareil) if appareil is not None else g.appareil
        lc = g.lc15.cpu().numpy().astype(np.float64)
        lh = g.lh15.cpu().numpy().astype(np.float64)
        ll = g.ll15.cpu().numpy().astype(np.float64)
        n = g.n
        vue = np.zeros((n, N_ENTREES), np.float32)
        valide = np.zeros(n, bool)
        cal = g.calendrier.cpu().numpy()
        temps = g.temps.astype("datetime64[ns]")
        grands = {}
        for m, nom in enumerate(g.noms):
            a, b = int(g.debut_marche[m]), int(g.debut_marche[m + 1])
            a += int(getattr(g, "n_h1", {}).get(nom, 0))            # seulement les bougies de 15 minutes
            if b - a < 100:
                continue
            c, h, l = lc[a:b], lh[a:b], ll[a:b]
            mv, u = _mouvements(c, h, l)
            col = 0
            vue[a:b, col:col + len(PAS)] = mv
            col += len(PAS)
            for k in FOURCHETTES:
                haut = pd.Series(h).rolling(k, min_periods=4).max().to_numpy()
                bas = pd.Series(l).rolling(k, min_periods=4).min().to_numpy()
                with np.errstate(divide="ignore", invalid="ignore"):
                    pos = (c - bas) / (haut - bas) - 0.5
                vue[a:b, col] = np.nan_to_num(np.clip(pos, -0.5, 0.5))
                col += 1
            with np.errstate(divide="ignore", invalid="ignore"):
                for k in (96, 2100):
                    reg = np.log(u / pd.Series(u).rolling(k, min_periods=16).mean().to_numpy())
                    vue[a:b, col] = np.nan_to_num(np.clip(reg, -3, 3))
                    col += 1
            vue[a:b, col:col + 4] = cal[a:b]
            col += 4
            try:
                f = fiche(nom)
                fam, frais = f.famille, f.frais
            except ValueError:
                fam, frais = "", 0.0006
            if fam in FAMILLES:
                vue[a:b, col + FAMILLES.index(fam)] = 1.0
            col += len(FAMILLES)
            with np.errstate(divide="ignore", invalid="ignore"):
                vue[a:b, col] = np.nan_to_num(np.clip(np.log(frais / u), -8, 4))
            valide[a:b] = np.isfinite(u) & (u > 0)
            if nom in GRANDS:
                grands[nom] = (temps[a:b], _mouvements(c, h, l, PAS_GRANDS)[0])
        # ce que font les grands marchés AU MÊME MOMENT (dernière bougie de 15 min déjà commencée, jamais après)
        for j, nom in enumerate(GRANDS):
            if nom not in grands:
                continue
            tg, mg = grands[nom]
            pos = np.searchsorted(tg, temps, side="right") - 1
            present = pos >= 0
            col = N_PROPRES + j * len(PAS_GRANDS)
            vue[present, col:col + len(PAS_GRANDS)] = mg[pos[present]]
        self.vue = torch.from_numpy(vue).to(dev)
        self.valide = valide

    def voir(self, idx: torch.Tensor):
        return self.vue[idx.to(self.vue.device).long()], None
