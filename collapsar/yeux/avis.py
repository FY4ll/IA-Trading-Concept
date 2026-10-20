"""Son AVIS : ce que pensent ses yeux (la cime des racines) à chaque bougie de chaque marché, et comment cet avis
évolue dans le temps — comme un trader qui sait ce qu'il pense, et depuis combien de temps il le pense.

Par bougie (décision à sa clôture), 44 nombres :
- pour 1 h, 4 h, 1 jour, 1 semaine, 1 mois : sens (sa conviction de hausse/baisse), ampleur, agitation attendues (15) ;
- sa conviction de sens LISSÉE sur 4 h, 1 jour et 1 semaine, pour les 5 horizons (15) ;
- la taille des bougies de chaque échelle (6) et l'heure / le jour (4) ;
- son regard de fond : le chemin parcouru par le prix sur 1, 3, 6 et 12 mois (4), en journées habituelles.
Calculé une seule fois (à l'école, ses yeux sont figés) : l'école devient très rapide.

ATTENTION (13/10/2026) : sur les années où les racines ont appris (2018 -> mi-2022), leur avis est faux-parfait
(97-99 % à 1 jour / 1 semaine, appris par cœur). L'école ne doit s'entraîner que sur des années jamais vues des
racines (2010-2017) ; le contrôle (2e moitié 2022) et l'examen (2023-2025) le sont aussi.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import torch

from collapsar.yeux.graphique import Graphique

LISSAGES = (16, 96, 480)
N_HORIZONS = 5                         # = len(regarder.exercices.HORIZONS) (pas importé ici : éviter une boucle)
N_PRED = 3 * N_HORIZONS + len(LISSAGES) * N_HORIZONS          # prédictions + convictions lissées (mises à l'échelle)
TENDANCES_JOURS = (30, 91, 182, 365)   # son regard de fond (13/10, accord du chef de projet) : 1, 3, 6, 12 mois
N_AVIS = N_PRED + 10 + len(TENDANCES_JOURS)


def _tendances(g: Graphique, m0: int, a: int, b: int, ext: np.ndarray) -> np.ndarray:
    """Le chemin parcouru par le prix sur 1, 3, 6 et 12 mois, en « journées habituelles » de ce marché (une
    INFORMATION comme un trader qui regarde son graphique mensuel, pas une règle). 0 si l'historique manque."""
    t = g.temps[m0:b]
    lc = g.lc15[m0:b].cpu().numpy().astype(np.float64)
    decision = (g.temps[a:b] + g.pas[a:b].astype("timedelta64[m]")).astype("datetime64[ns]")
    jour = np.exp(ext[:, 3].astype(np.float64) * 3 - 6)                 # taille habituelle d'une bougie journalière
    sorties = []
    for j in TENDANCES_JOURS:
        k = np.searchsorted(t, decision - np.timedelta64(j, "D"), side="right") - 1
        ok = k >= 0
        r = np.where(ok, lc[(np.arange(a, b) - m0)] - lc[np.maximum(k, 0)], 0.0)
        sorties.append(np.clip(r / (jour * np.sqrt(j * 5 / 7)), -5, 5) * ok)
    return np.stack(sorties, 1)


@torch.no_grad()
def _avis_marche(cerveau, g: Graphique, a: int, b: int, lot: int, m0: int | None = None) -> np.ndarray:
    sens, amp, agi, ext = [], [], [], []
    for d in range(a, b, lot):
        idx = torch.arange(d, min(d + lot, b), device=g.appareil)
        f, x = g.voir(idx)
        s, p, q = cerveau(f, x)
        sens.append(s.float().cpu().numpy())
        amp.append(p.float().cpu().numpy())
        agi.append(q.float().cpu().numpy())
        ext.append(x.float().cpu().numpy())
    sens, amp, agi, ext = (np.concatenate(v) for v in (sens, amp, agi, ext))
    lisses = [pd.DataFrame(sens).ewm(span=n).mean().to_numpy() for n in LISSAGES]
    fond = _tendances(g, a if m0 is None else m0, a, b, ext)
    return np.concatenate([sens, amp, agi, *lisses, ext[:, :10], fond], 1).astype(np.float16)


class Avis:
    def __init__(self, tables: dict[str, np.ndarray], source: dict, appareil="cpu"):
        self.noms = list(tables)
        self.source = source
        longueurs = [len(t) for t in tables.values()]
        self.debut = dict(zip(self.noms, np.r_[0, np.cumsum(longueurs)[:-1]].astype(np.int64)))
        self.table = torch.from_numpy(np.concatenate(list(tables.values()))).to(appareil)

    @classmethod
    def calculer(cls, cerveau, donnees: dict[str, pd.DataFrame], appareil="cpu", source=None, lot=4096,
                 horaires: dict[str, pd.DataFrame] | None = None) -> "Avis":
        """Avis pour chaque bougie de 15 minutes. `horaires` : les années en bougies d'1 heure d'avant, pour qu'elle
        voie tout le contexte de fond (échelles semaine / mois) ; aucun avis n'est rendu pour ces années-là."""
        cerveau.eval()
        g = Graphique(donnees, appareil, horaires)
        tables = {}
        for j, m in enumerate(g.noms):
            m0 = int(g.debut_marche[j])
            a = m0 + int(g.n_h1.get(m, 0))
            tables[m] = _avis_marche(cerveau, g, a, int(g.debut_marche[j + 1]), lot, m0)
        return cls(tables, source or {}, appareil)

    def normaliser(self, lignes_vierges: dict[str, np.ndarray]):
        """Met son avis à la même échelle sur chaque marché (sa conviction en « fort / faible » plutôt qu'en chiffres
        bruts, qui varient d'un marché à l'autre). L'échelle est mesurée UNIQUEMENT sur des bougies que les racines
        n'ont jamais apprises et qui ne sont pas l'examen (avant 2018, ou 2e moitié 2022) : sur leurs années apprises,
        leur avis est trop tranché (appris par cœur) et fausserait l'échelle. Le zéro n'est pas déplacé (0 = sans avis).
        Les 10 dernières colonnes (taille des bougies, heure) sont déjà à l'échelle."""
        t = self.table.float()
        for m, lignes in lignes_vierges.items():
            d = int(self.debut[m])
            if len(lignes) > 500:
                bloc = t[d + torch.as_tensor(lignes, device=t.device), :N_PRED]
                ecart = bloc.pow(2).mean(0).sqrt().clamp(min=1e-3)
                t[d:d + self._longueur(m), :N_PRED] /= ecart
        self.table = t.clamp(-10, 10).to(self.table.dtype)
        self.source["normalise"] = True
        return self

    def _longueur(self, m: str) -> int:
        i = self.noms.index(m)
        return int((self.debut[self.noms[i + 1]] if i + 1 < len(self.noms) else len(self.table)) - self.debut[m])

    def voir(self, idx: torch.Tensor) -> torch.Tensor:
        return self.table[idx.to(self.table.device)].float()

    def sauver(self, fichier: Path):
        fichier.parent.mkdir(parents=True, exist_ok=True)
        t = self.table.cpu().numpy()
        tables = {m: t[self.debut[m]:self.debut[m] + n]
                  for m, n in zip(self.noms, np.diff(np.r_[list(self.debut.values()), len(t)]))}
        np.savez(fichier, **tables)
        fichier.with_suffix(".json").write_text(json.dumps(self.source, ensure_ascii=False, indent=1),
                                                encoding="utf-8")

    @classmethod
    def charger(cls, fichier: Path, appareil="cpu") -> "Avis":
        z = np.load(fichier)
        source = json.loads(fichier.with_suffix(".json").read_text(encoding="utf-8"))
        return cls({m: z[m] for m in z.files}, source, appareil)
