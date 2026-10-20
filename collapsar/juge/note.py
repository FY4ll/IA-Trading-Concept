"""La NOTE du juge (15/10/2026, rapports reports/*.md) : son avantage SUR LE HASARD, pas son gain brut.

Pourquoi : au hasard, sans aucun avantage, on réussit déjà la phase 1 d'un challenge FTMO environ une fois sur deux
(deux barrières +10 % / -10 %), et la taille des positions ne crée aucun avantage : elle déforme seulement le chemin.
Un gain ou une réussite ne prouvent donc rien seuls. On compare chaque compte à son JUMEAU : mêmes gestes, même
taille, mêmes stops, mêmes frais, mais le sens d'ouverture tiré à pile ou face (ecole/regard.jouer_comptes).

- avantage = moyenne, compte par compte, de (son gain - gain moyen de ses jumeaux), en %/mois ;
- force de la preuve = avantage / son incertitude ; l'incertitude tient compte des comptes qui se CHEVAUCHENT dans
  le temps (deux comptes qui vivent les mêmes jours ne sont pas deux preuves indépendantes) ;
- seuil corrigé du nombre d'ESSAIS (Harvey, Liu, Zhu 2016 ; Bailey et López de Prado 2014) : en essayant N élèves
  ou réglages, le meilleur dépasse le hasard de ~racine(2 ln N) incertitudes par pure chance. Le seuil est le plus
  grand de 3 (recommandé par Harvey et al.) et de ce nombre.
"""
from __future__ import annotations

import math

import numpy as np


def seuil_essais(essais: int) -> float:
    return max(3.0, math.sqrt(2 * math.log(max(essais, 1))))


def avantage_sur_hasard(elle: dict, jumeaux: list[dict], essais: int = 1, duree: int | None = None,
                        ecart_departs: float | None = None) -> dict:
    """`elle`, `jumeaux` : résultats de jouer_comptes (mêmes départs, même durée). `duree` et `ecart_departs` (en
    bougies) : pour compter les comptes vraiment indépendants (chevauchement)."""
    g = np.asarray(elle["gains_comptes_pct_mois"], dtype=float)
    gj = np.mean([np.asarray(j["gains_comptes_pct_mois"], dtype=float) for j in jumeaux], axis=0)
    d = g - gj
    n = len(d)
    independants = n
    if duree and ecart_departs:
        independants = max(1.0, n * min(1.0, ecart_departs / duree))
    ecart = d.std(ddof=1) if n > 1 else float("nan")
    incertitude = ecart / math.sqrt(independants) if n > 1 else float("nan")
    force = d.mean() / incertitude if incertitude and incertitude > 0 else float("nan")
    r_elle = float(np.mean(elle["reussis_comptes"]) * 100)
    r_jum = float(np.mean([np.mean(j["reussis_comptes"]) for j in jumeaux]) * 100)
    m_elle = float(np.mean(elle["morts_comptes"]) * 100)
    m_jum = float(np.mean([np.mean(j["morts_comptes"]) for j in jumeaux]) * 100)
    seuil = seuil_essais(essais)
    return {"avantage_pct_mois": float(d.mean()), "incertitude_pct_mois": float(incertitude),
            "force_preuve": float(force), "seuil": seuil, "comptes_independants": float(independants),
            "prouve": bool(np.isfinite(force) and force > seuil),
            "reussis_elle_pct": r_elle, "reussis_jumeau_pct": r_jum, "reussis_en_plus_pct": r_elle - r_jum,
            "murs_elle_pct": m_elle, "murs_jumeau_pct": m_jum, "essais": essais}


def phrase(a: dict) -> str:
    verdict = "PROUVÉ" if a["prouve"] else "pas prouvé"
    return (f"avantage sur le hasard {a['avantage_pct_mois']:+.2f} %/mois (± {a['incertitude_pct_mois']:.2f}, force "
            f"{a['force_preuve']:+.1f} pour un seuil de {a['seuil']:.1f} après {a['essais']} essais : {verdict}) ; "
            f"challenges réussis {a['reussis_elle_pct']:.0f} % contre {a['reussis_jumeau_pct']:.0f} % au hasard, "
            f"murs {a['murs_elle_pct']:.0f} % contre {a['murs_jumeau_pct']:.0f} %")
