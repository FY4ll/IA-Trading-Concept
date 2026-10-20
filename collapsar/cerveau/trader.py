"""Le cerveau à vision de trader (14/10/2026) : les mêmes yeux et le même tronc que les racines (on les greffe : la
lecture des graphiques n'est pas perdue), et une tête qui évalue N'IMPORTE QUEL coup qu'on lui décrit (sens, distance
du stop, objectif — ou pas de stop, ou pas d'objectif) : chance d'atteindre l'objectif avant le stop, et ce que le coup
rapporte. Aucun menu : la description du coup est une entrée continue.
"""
from __future__ import annotations

import torch
from torch import nn

from collapsar.cerveau.reseau import LecteurDeGraphique
from collapsar.donnees.marches import ECHELLES
from collapsar.yeux.graphique import N_EXTRA

N_REQUETE = 5          # sens, distance du stop, objectif, « pas d'objectif », « pas de stop »


class _JugeDeCoups:
    """La tête qui juge n'importe quel coup décrit (partagée par toutes les façons de regarder)."""

    def _construire_tete(self):
        # la description du coup module ce que le tronc a compris du graphique
        self.coup = nn.Sequential(nn.Linear(N_REQUETE, 64), nn.GELU(), nn.Linear(64, 256))
        # 3 réponses : chance d'atteindre l'objectif, gain moyen, et son INCERTITUDE (14/10 05h15 : sans elle, parmi
        # 108 coups estimés, elle choisissait toujours le « billet de loterie » surestimé par hasard)
        self.juger = nn.Sequential(nn.Linear(256 + 256, 256), nn.GELU(), nn.Linear(256, 128), nn.GELU(),
                                   nn.Linear(128, 3))

    def forward(self, fenetres, extra, requetes):
        return self.juger_coups(self.comprendre(fenetres, extra), requetes)

    def juger_coups(self, compris: torch.Tensor, requetes: torch.Tensor):
        """`compris` [B, 256], `requetes` [B, Q, 5] -> (chance d'atteindre l'objectif (logit) [B, Q],
        résultat moyen en multiples de min(stop, 20 tailles) [B, Q], log de sa variance (même unité) [B, Q])."""
        q = self.coup(requetes)
        c = compris[:, None, :].expand(-1, q.shape[1], -1)
        r = self.juger(torch.cat([c * (1 + q), q], -1))
        return r[..., 0], r[..., 1], r[..., 2].clamp(-8, 8)


class CerveauTrader(_JugeDeCoups, nn.Module):
    """Regarde le graphique BRUT : 64 bougies sur 6 échelles."""

    def __init__(self, oubli: float = 0.1, largeur: float = 1.0):
        nn.Module.__init__(self)
        self.largeur = largeur
        self.lecteur = LecteurDeGraphique(largeur=largeur)
        entree = len(ECHELLES) * 96 + N_EXTRA
        milieu = int(round(512 * largeur))
        self.tronc = nn.Sequential(
            nn.Linear(entree, milieu), nn.LayerNorm(milieu), nn.GELU(), nn.Dropout(oubli),
            nn.Linear(milieu, 256), nn.LayerNorm(256), nn.GELU())
        self._construire_tete()

    def comprendre(self, fenetres: torch.Tensor, extra: torch.Tensor) -> torch.Tensor:
        lu = self.lecteur(fenetres).flatten(1)
        return self.tronc(torch.cat([lu, extra], 1))


class CerveauVueDEnsemble(_JugeDeCoups, nn.Module):
    """Regarde la VUE D'ENSEMBLE (yeux/vue_ensemble.py) : quelques dizaines de nombres au lieu de 384 bougies — elle
    ne peut plus reconnaître un moment précis pour réciter sa suite (14/10 après-midi)."""

    def __init__(self, n_entrees: int, oubli: float = 0.1, largeur: float = 1.0):
        nn.Module.__init__(self)
        milieu = int(round(256 * largeur))
        self.tronc = nn.Sequential(
            nn.Linear(n_entrees, milieu), nn.LayerNorm(milieu), nn.GELU(), nn.Dropout(oubli),
            nn.Linear(milieu, 256), nn.LayerNorm(256), nn.GELU())
        self._construire_tete()

    def comprendre(self, vue: torch.Tensor, _extra=None) -> torch.Tensor:
        return self.tronc(vue)


def greffer(cerveau: CerveauTrader, etat_racines: dict) -> int:
    """Reprend les yeux et le tronc d'une branche des racines (même forme). Rend le nombre de morceaux repris."""
    propre = cerveau.state_dict()
    repris = {k: v for k, v in etat_racines.items()
              if (k.startswith("lecteur.") or k.startswith("tronc.")) and k in propre and propre[k].shape == v.shape}
    propre.update(repris)
    cerveau.load_state_dict(propre)
    return len(repris)
