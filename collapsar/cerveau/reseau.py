"""Le cerveau de COLLAPSAR.

- Les mêmes yeux pour toutes les échelles (un seul « lecteur de graphique », qui sait sur quelle échelle il lit),
  comme un humain qui lit de la même façon un graphique 15 minutes ou un graphique mensuel.
- Un tronc qui rassemble les échelles, l'heure et le jour.
- Des têtes de réponse : pour l'étage « regarder », les exercices (sens, ampleur et agitation à plusieurs horizons).
  L'étage « agir » ajoutera ses mains sur le même tronc.
Toutes les branches de l'arbre ont la même forme : c'est ce qui permet de les fusionner.
"""
from __future__ import annotations

import torch
from torch import nn

from collapsar.yeux.graphique import N_EXTRA, N_TRAITS
from collapsar.donnees.marches import ECHELLES
from collapsar.regarder.exercices import HORIZONS


class LecteurDeGraphique(nn.Module):
    def __init__(self, sortie: int = 96, largeur: float = 1.0):
        super().__init__()
        c1, c2, c3 = (int(round(x * largeur)) for x in (48, 64, 96))
        self.conv = nn.Sequential(
            nn.Conv1d(N_TRAITS, c1, 5, padding=2), nn.GELU(),
            nn.Conv1d(c1, c2, 5, padding=2, stride=2), nn.GELU(),
            nn.Conv1d(c2, c3, 5, padding=2, stride=2), nn.GELU(),
            nn.Conv1d(c3, c3, 3, padding=1), nn.GELU())
        self.quelle_echelle = nn.Embedding(len(ECHELLES), 16)
        self.fin = nn.Linear(c3 * 3 + 16, sortie)

    def forward(self, f: torch.Tensor) -> torch.Tensor:          # f : [B, E, 64, traits]
        b, e, n, k = f.shape
        x = self.conv(f.reshape(b * e, n, k).transpose(1, 2))   # [B*E, 96, 16]
        dernier = x[:, :, -1]                                    # ce qui se passe juste maintenant
        resume = torch.cat([x.mean(2), x.amax(2), dernier], 1)
        quelle = self.quelle_echelle.weight.repeat(b, 1)
        return self.fin(torch.cat([resume, quelle], 1)).reshape(b, e, -1)


class Cerveau(nn.Module):
    def __init__(self, n_horizons: int = len(HORIZONS), oubli: float = 0.1, largeur: float = 1.0):
        """`largeur` : taille du cerveau (1 = ~1 200 neurones, 0,54 million de connexions ; 2,5 = ~3 000 neurones,
        ~1,6 million). La sortie du tronc reste à 256 : les mains de l'école s'y branchent pareil."""
        super().__init__()
        self.largeur = largeur
        self.lecteur = LecteurDeGraphique(largeur=largeur)
        entree = len(ECHELLES) * 96 + N_EXTRA
        milieu = int(round(512 * largeur))
        self.tronc = nn.Sequential(
            nn.Linear(entree, milieu), nn.LayerNorm(milieu), nn.GELU(), nn.Dropout(oubli),
            nn.Linear(milieu, 256), nn.LayerNorm(256), nn.GELU())
        self.n_horizons = n_horizons
        self.regarder = nn.Linear(256, 3 * n_horizons)          # sens, ampleur, agitation par horizon

    def comprendre(self, fenetres: torch.Tensor, extra: torch.Tensor) -> torch.Tensor:
        lu = self.lecteur(fenetres).flatten(1)
        return self.tronc(torch.cat([lu, extra], 1))

    def forward(self, fenetres, extra):
        r = self.regarder(self.comprendre(fenetres, extra))
        h = self.n_horizons
        return r[:, :h], r[:, h:2 * h], r[:, 2 * h:]            # sens (logit), ampleur, agitation
