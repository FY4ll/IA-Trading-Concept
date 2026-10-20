"""L'école des mille mondes branchée sur l'école « elle choisit quand revenir regarder » (14/10/2026).

- `ClasseMonde` : un monde inventé (mondes/generateur.py) habillé comme un vrai marché pour l'école : frais, levier
  et frais de nuit tirés parmi ceux des vrais marchés FTMO, calendrier des annonces du monde (connu d'avance, comme
  celui de MetaTrader), et sa VÉRITÉ cachée (la dérive réelle à chaque instant).
- `jouer_connaisseur` : le « connaisseur », qui connaît la dérive cachée et se place dans son sens chaque jour, avec
  la même prise de risque qu'elle au départ (0,5 % du compte par bougie du jour). Il n'existe que pour MESURER ce
  qui était gagnable : elle ne le voit jamais, il ne lui apprend rien.
- `controle_mondes` : des mondes de contrôle FIXES (jamais vus à l'école) : son gain, celui du connaisseur, la part
  du gagnable qu'elle capture, ses murs, son comportement.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import torch

from collapsar.cerveau.humain import TraderHumain
from collapsar.ecole.regard import DUREE_PARTIE, UN_MOIS, ClasseRegard, Etat, jouer_comptes
from collapsar.juge.note import avantage_sur_hasard
from collapsar.mains.fiches import Fiche
from collapsar.mains.simulateur import CAPITAL, Ordres
from collapsar.mondes.generateur import Lois, fabriquer, tirer_lois

JOURS_MONDE = 520                    # deux ans de marché par monde
GRAINE_CONTROLE = 900_000            # les mondes de contrôle ne sont jamais tirés à l'école (graines à part)


def fiche_monde(nom: str, rng: np.random.Generator, agitation_jour: float) -> Fiche:
    """Frais, frais de nuit et levier LIÉS à l'agitation, comme les vrais marchés FTMO (14/10 : tirés au hasard, un
    monde calme recevait les frais d'une crypto et même le connaisseur perdait) :
    - frais d'un trade complet = 1 à 3 % de l'agitation d'un jour (euro-dollar 0,006 % pour 0,55 %, or 0,012 % pour
      ~1 %, pétrole 0,06 % pour 2 %, bitcoin 0,08 % pour 5 %) ;
    - frais de nuit annuels = 2 à 6 x l'agitation d'un jour (euro-dollar 2 % pour 0,55 %, bitcoin 20 % pour 5 %) ;
    - levier : 1:100 sous 0,8 % d'agitation (devises), 1:30 sous 1,5 % (or, indices), 1:10 sous 3 %, sinon 1:2."""
    levier = 100.0 if agitation_jour < 0.008 else 30.0 if agitation_jour < 0.015 else 10.0 if agitation_jour < 0.03 else 2.0
    nuit = float(agitation_jour * rng.uniform(2.0, 6.0))
    frais = float(agitation_jour * rng.uniform(0.01, 0.03))
    return Fiche(nom, nom, "monde", "USD", frais, levier, nuit, nuit, 0.0, 0.0)


class ClasseMonde(ClasseRegard):
    def __init__(self, lois: Lois, appareil="cpu", jours: int = JOURS_MONDE):
        donnees, verite = fabriquer(lois, jours=jours)
        rng = np.random.default_rng(lois.graine + 1)
        marches = list(donnees)
        fiches = {m: fiche_monde(m, rng, float(lois.agitation_jour[j])) for j, m in enumerate(marches)}
        temps = donnees[marches[0]]["time"]
        annonces = pd.DataFrame({"temps": temps[verite["annonce"]].to_numpy(), "devise": "MONDE"})
        super().__init__(marches, appareil, donnees, annonces, fiches)
        self.lois = lois
        assert len(self.h.temps) == len(temps), "un monde : tous ses marchés cotent aux mêmes instants"
        self.derive = torch.from_numpy(verite["derive"]).to(self.dev)              # [T, M] par bougie (log)
        self.tendance = torch.from_numpy(verite["tendance"]).to(self.dev)          # sans le hasard
        self.rappel = torch.from_numpy(verite["rappel"]).to(self.dev)              # connu une bougie avant
        self.regime = torch.from_numpy(verite["regime"]).to(self.dev)


def nouveau_monde(rng: np.random.Generator, intensite: float, appareil="cpu", marches: int | None = None,
                  jours: int = JOURS_MONDE) -> ClasseMonde:
    m = int(marches or rng.integers(1, 5))
    return ClasseMonde(tirer_lois(rng, m, intensite=intensite), appareil, jours)


@torch.no_grad()
def jouer_connaisseur(c: ClasseMonde, departs: torch.Tensor, duree: int = DUREE_PARTIE,
                      risque: float = 0.005) -> dict:
    """Le connaisseur : chaque jour (et au départ), position dans le sens de ce qu'il SAIT du jour qui vient : la
    tendance cachée (qui ne dépend pas du hasard) + le retour au calme tel qu'il est au moment de décider (14/10 :
    utiliser le rappel FUTUR, qui dépend du hasard à venir, le faisait parier à contresens). 0,5 % du compte par
    bougie du jour. Mêmes comptes, mêmes frais, mêmes murs qu'elle."""
    n = len(departs)
    e = Etat(c.h, n)
    e.recommencer(torch.ones(n, dtype=torch.bool, device=c.dev), departs.to(c.dev))
    cpt = e.comptes
    vivant = torch.ones(n, dtype=torch.bool, device=c.dev)
    mort = torch.zeros_like(vivant)
    inactif = torch.zeros_like(vivant)
    reussi = torch.zeros_like(vivant)
    finale = torch.full((n,), CAPITAL, dtype=torch.float64, device=c.dev)
    T = c.h.T
    cumul = torch.cat([torch.zeros(1, c.h.M, device=c.dev, dtype=c.tendance.dtype), c.tendance.cumsum(0)])
    for k in range(duree):
        ordres = Ordres()
        if k % 96 == 0:
            t = cpt.t
            fin_jour = (t + 96).clamp(max=T)
            rappel = c.rappel[(t + 1).clamp(max=T - 1)]                                # connu à l'instant t
            sens = torch.sign(cumul[fin_jour] - cumul[t + 1] + 96 * rappel)
            idx = c.offset[None, :] + c.h.local[t].clamp(min=0)
            _, x = c.g.voir(idx.reshape(-1))
            taille = torch.exp(x[:, c.i_jour] * 3 - 6).reshape(n, -1).double()
            valeur = cpt.valeur(c.h.c[t], c.h.fx[t])
            cible = sens.double() * risque * valeur[:, None] / taille.clamp(min=1e-4)
            cible = torch.where(vivant[:, None], cible, torch.full_like(cible, float("nan")))
            ordres = Ordres(cible=cible)
        r = cpt.pas(ordres)
        finale = torch.where(vivant, r["valeur"], finale)
        mort |= vivant & r["mort"]
        inactif |= vivant & r["inactif"]
        reussi |= vivant & r["reussi"]
        vivant &= ~(r["mort"] | r["reussi"] | r["fin_histoire"])
        if not vivant.any():
            break
    gains = (finale / CAPITAL - 1) * 100
    return {"gain_moyen_pct": float(gains.mean()) / (duree / UN_MOIS),
            "murs_touches_pct": float((mort & ~inactif).float().mean() * 100),
            "inactifs_pct": float(inactif.float().mean() * 100),
            "challenges_reussis_pct": float(reussi.float().mean() * 100)}


def departs_monde(c: ClasseMonde, comptes: int, duree: int = DUREE_PARTIE) -> torch.Tensor:
    lo, hi = 96 * 30, c.h.T - duree - 1
    return torch.linspace(lo, hi, comptes, device=c.dev).long()


class ControleMondes:
    """Mondes de contrôle FIXES (graines à part, jamais vus à l'école), construits une fois ; le connaisseur y joue
    une seule fois (son résultat ne change pas). `noter(agent)` : son résultat, le gagnable, la part capturée
    (somme de ses gains / somme de ceux du connaisseur), ses murs et son comportement."""

    def __init__(self, intensite: float, appareil="cpu", mondes: int = 4, comptes: int = 6,
                 graine: int = GRAINE_CONTROLE, jours: int = JOURS_MONDE, duree: int = DUREE_PARTIE):
        rng = np.random.default_rng(graine)
        self.intensite, self.graine, self.duree = intensite, graine, duree
        self.mondes = [nouveau_monde(rng, intensite, appareil, jours=jours) for _ in range(mondes)]
        self.departs = [departs_monde(c, comptes, duree) for c in self.mondes]
        self.connaisseur = [jouer_connaisseur(c, d, duree) for c, d in zip(self.mondes, self.departs)]

    def noter(self, agent: TraderHumain, jumeaux: int = 0, essais: int = 1) -> dict:
        """`jumeaux` > 0 : ajoute la note du juge, son avantage sur son jumeau au hasard (juge/note.py)."""
        elle = [jouer_comptes(c, agent, d, self.duree, graine=self.graine + i)
                for i, (c, d) in enumerate(zip(self.mondes, self.departs))]
        moy = lambda liste, cle: float(np.mean([x[cle] for x in liste]))
        gain, gagnable = moy(elle, "gain_moyen_pct"), moy(self.connaisseur, "gain_moyen_pct")
        sortie = {k: moy(elle, k) for k, v in elle[0].items() if not isinstance(v, list)}
        if jumeaux > 0:
            colle = lambda liste: {k: sum((x[k] for x in liste), []) for k in
                                   ("gains_comptes_pct_mois", "reussis_comptes", "morts_comptes")}
            jum = [colle([jouer_comptes(c, agent, d, self.duree, graine=self.graine + 7919 * (k + 1) + i, jumeau=True)
                          for i, (c, d) in enumerate(zip(self.mondes, self.departs))]) for k in range(jumeaux)]
            sortie["note"] = avantage_sur_hasard(colle(elle), jum, essais)
        sortie.update({"gagnable_pct": gagnable,
                       "capture_pct": gain / gagnable * 100 if gagnable > 0.02 else float("nan"),
                       "murs_connaisseur_pct": moy(self.connaisseur, "murs_touches_pct"),
                       "intensite": self.intensite})
        return sortie