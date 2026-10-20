"""La démonstration : « suivre son propre avis de fond, entrer sur conviction, tenir jusqu'au retournement ».

Ce n'est PAS une règle de trading imposée à l'IA : c'est son POINT DE DÉPART à l'école (d'abord imiter, ensuite
s'améliorer par la récompense, comme AlphaGo ou ChatGPT). Le modèle imité, c'est elle-même : son avis vient de ses
propres yeux (les racines), et le test de vérité du 13/10 a montré que le TENIR est rentable sur 2023-2025 jamais
vus (+0,24 %/mois par marché à 1 x le compte, 68 % des marchés gagnants, frais compris). Ensuite, la récompense la
laisse s'en écarter là où elle trouve mieux.
"""
from __future__ import annotations

import numpy as np
import torch

from collapsar.donnees import marches as dm
from collapsar.ecole.classe import Classe
from collapsar.mains.simulateur import Comptes
from collapsar.regarder.exercices import HORIZONS
from collapsar.yeux.avis import LISSAGES, N_PRED

NOMS_H = list(HORIZONS)


def colonne(horizon: str, lissage: int) -> int:
    """Colonne de l'avis : son sens à `horizon`, lissé sur `lissage` bougies (1 = pas lissé)."""
    h = NOMS_H.index(horizon)
    n = len(NOMS_H)
    return h if lissage == 1 else 3 * n + n * LISSAGES.index(lissage) + h


class TenirSonAvis:
    def __init__(self, avis, marches: list[str], horizon="1 semaine", lissage=16, conviction=0.5, exposition=1.0,
                 lignes: dict | None = None, risque_jour: float | None = None):
        """`conviction` : entrer seulement quand l'avis dépasse ses 50 % de cas les plus nets, mesuré sur les bougies
        `lignes[m]` (par défaut : toutes celles d'avant 2023).
        Taille : `risque_jour` (ex. 0,005) = position telle qu'une journée habituelle de ce marché fasse bouger le
        compte d'environ 0,5 % (beaucoup d'euro-dollar, peu de Bitcoin) ; sinon `exposition` x la valeur du compte."""
        self.avis, self.k, self.expo, self.risque = avis, colonne(horizon, lissage), exposition, risque_jour
        self.seuil = {}
        for m in marches:
            d = int(avis.debut[m])
            rangs = lignes[m] if lignes is not None else np.arange(len(dm.charger(m)))
            col = avis.table[d + torch.as_tensor(rangs, device=avis.table.device), self.k].float().abs().cpu().numpy()
            self.seuil[m] = float(np.quantile(col, conviction)) if len(col) else 0.0
        taille = f"risque {risque_jour:.1%}/jour" if risque_jour else f"{exposition:g} x"
        self.description = f"tenir son avis {horizon} lissé {lissage}, conviction {conviction:.0%}, {taille}"

    def actions(self, c: Classe, cpt: Comptes, idx, vm, vc):
        b, m = vm.shape[0], vm.shape[1]
        vu = self.avis.voir(idx).reshape(b, m, -1)
        a = vu[..., self.k]
        if self.risque:
            # taille moyenne des bougies JOURNALIÈRES (colonne « jour » des yeux : (log(taille) + 6) / 3)
            jour = torch.exp(vu[..., N_PRED + 3] * 3 - 6).clamp(min=1e-4)
            expo = (self.risque / jour).clamp(max=20.0)
        else:
            expo = torch.full_like(a, self.expo)
        seuil = torch.tensor([self.seuil[x] for x in c.h.marches], device=a.device)[None, :]
        pos = torch.sign(cpt.u).float()
        fort = a.abs() >= seuil
        voulu = torch.where(pos == 0, torch.where(fort, torch.sign(a), 0.0),
                            torch.where(a * pos < 0, torch.where(fort, torch.sign(a), 0.0), pos))
        agir = (voulu != pos).float()
        cible = voulu * (expo / 100.0) ** (1 / 3)
        z = torch.atanh(cible.clamp(-0.999, 0.999))
        return agir, z
