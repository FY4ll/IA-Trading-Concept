"""Le cerveau qui AGIT (étage 2) : les yeux et le tronc des racines + la vue de son compte + ses mains + ses horloges.

- Les yeux et le tronc viennent de la cime des racines : elle sait déjà lire un graphique.
- Pour chaque marché : ce qu'elle comprend du graphique + ce qu'elle a sur ce marché (position, gain latent, stop,
  objectif, ordre en attente, heures avant la fermeture forcée...).
- Le compte entier (valeur, baisse du jour, distance aux murs, argent engagé) est vu en même temps pour tous les
  marchés : elle sait toujours ce qu'elle a déjà ouvert ailleurs.
- Ses mains (classe 1) : pour chaque marché, « changer ma position ou garder » et, si elle change, la position voulue
  (achat ou vente, et combien : taille libre, seuls le levier du compte et les murs FTMO la limitent).
- Ses horloges : une estimation de l'avenir pour plusieurs horizons (environ 1 jour, 1 semaine, 1 mois).
"""
from __future__ import annotations

import torch
from torch import nn
from torch.distributions import Bernoulli, Normal

from collapsar.cerveau.reseau import Cerveau
from collapsar.mains.simulateur import N_VUE_COMPTE, N_VUE_MARCHE
from collapsar.yeux.avis import N_AVIS

HORLOGES = (0.99, 0.998, 0.9995)          # ~100 bougies (1 jour), ~500 (1 semaine), ~2 000 (1 mois)
LEVIER_MAX = 100.0                        # position voulue = a^3 x 100 x valeur du compte (a entre -1 et 1)


class Agent(nn.Module):
    def __init__(self, cerveau: Cerveau, horloges=HORLOGES, yeux_figes: bool = True):
        super().__init__()
        self.cerveau = cerveau
        self.yeux_figes = yeux_figes                         # l'école apprend les mains ; les racines, les yeux
        if yeux_figes:
            for p in cerveau.parameters():
                p.requires_grad_(False)
        self._mains_et_horloges(horloges)

    def _mains_et_horloges(self, horloges, d: int = 256):
        self.marche = nn.Sequential(nn.Linear(d + N_VUE_MARCHE, d), nn.LayerNorm(d), nn.GELU())
        self.compte = nn.Sequential(nn.Linear(N_VUE_COMPTE, 64), nn.GELU())
        self.ensemble = nn.Sequential(nn.Linear(d + 64, d), nn.LayerNorm(d), nn.GELU(), nn.Linear(d, d), nn.GELU())
        self.mains = nn.Linear(d, 2)                         # garder/changer, position voulue
        self.log_ecart = nn.Parameter(torch.tensor(-1.0))    # largeur de ses essais (exploration) : ~4x au départ
        self.horloges = nn.Linear(d + 64, len(horloges))
        self.gammas = horloges
        nn.init.zeros_(self.mains.weight)
        nn.init.zeros_(self.mains.bias)                      # au départ : 50 % de chances d'agir, positions variées

    def lire(self, fenetres, extra, b, m):
        """Ce que ses yeux comprennent des graphiques [B, M, 256]. Yeux figés à l'école : calculé une seule fois."""
        if self.yeux_figes:
            with torch.no_grad():
                return self.cerveau.comprendre(fenetres, extra).reshape(b, m, -1)
        return self.cerveau.comprendre(fenetres, extra).reshape(b, m, -1)

    def forward(self, fenetres, extra, vue_marche, vue_compte):
        """fenetres [B*M, échelles, 64, traits], extra [B*M, ...], vue_marche [B, M, 13], vue_compte [B, 7]."""
        b, m, _ = vue_marche.shape
        return self.decider(self.lire(fenetres, extra, b, m), vue_marche, vue_compte)

    def decider(self, lu, vue_marche, vue_compte):
        b, m, _ = vue_marche.shape
        par_marche = self.marche(torch.cat([lu, vue_marche], -1))
        c = self.compte(vue_compte)
        x = self.ensemble(torch.cat([par_marche, c[:, None, :].expand(b, m, -1)], -1))
        mains = self.mains(x)
        valeurs = self.horloges(torch.cat([x.mean(1), c], -1))
        return mains[..., 0], mains[..., 1], valeurs

    def lois(self, logit_agir, moyenne, plancher: float = 0.0):
        """`plancher` (à l'école) : elle garde au moins cette chance d'agir à chaque bougie, pour ne jamais arrêter
        d'essayer (contre la paresse ; constaté le 13/10 : sans lui, elle finissait par ne plus trader du tout)."""
        p = torch.sigmoid(logit_agir)
        p = plancher + (1 - 2 * plancher) * p
        ecart = self.log_ecart.clamp(-3.0, 0.0).exp()
        return Bernoulli(probs=p), Normal(moyenne, ecart.expand_as(moyenne))

    @staticmethod
    def log_prob(loi_agir, loi_pos, agir, z):
        a = torch.tanh(z)
        lp_pos = loi_pos.log_prob(z) - torch.log(1 - a * a + 1e-6)
        return (loi_agir.log_prob(agir) + agir * lp_pos).sum(-1)

    @staticmethod
    def position_voulue(z, valeur_compte):
        """Position voulue en dollars : a^3 x 100 x valeur du compte (fine près de zéro, large au bout)."""
        a = torch.tanh(z)
        return (a ** 3) * LEVIER_MAX * valeur_compte[:, None]


class AgentAvis(Agent):
    """L'élève qui décide à partir de SON AVIS (yeux/avis.py : ce que pensent ses yeux, et son évolution dans le
    temps) au lieu des 256 signaux internes des racines : il n'a plus à redécouvrir ce que ses propres yeux pensent.
    Mêmes mains, même vue du compte, mêmes horloges."""
    par_avis = True

    def __init__(self, n_avis: int = N_AVIS, horloges=HORLOGES):
        nn.Module.__init__(self)
        self.cerveau = None
        self.yeux_figes = True                    # l'avis est calculé d'avance ; seul l'encodeur ci-dessous apprend
        # PAS de normalisation par ligne à l'entrée (13/10 : elle effaçait la FORCE de sa conviction, justement ce qui
        # décide d'entrer) ; l'avis est déjà mis à l'échelle marché par marché (Avis.normaliser)
        self.encodeur = nn.Sequential(nn.Linear(n_avis, 128), nn.GELU(), nn.Linear(128, 256), nn.GELU())
        self._mains_et_horloges(horloges)

    def decider(self, avis, vue_marche, vue_compte):
        return super().decider(self.encodeur(avis), vue_marche, vue_compte)
