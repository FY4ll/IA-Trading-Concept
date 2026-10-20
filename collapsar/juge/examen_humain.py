"""L'EXAMEN du trader humain numérique sur les VRAIS marchés, période du juge (09/2023 -> 09/2025, jamais apprise),
un seul compte FTMO de 100 000 $ pour tous les marchés de l'examen (15/10/2026).

Trois joueurs sur exactement les mêmes challenges (un départ tous les 10 jours de marché, 6 mois au plus, arrêt à
+10 % ou à un mur ; FTMO n'a plus de limite de temps, la fenêtre de 6 mois est celle de nos données) :
- ELLE (un élève sauvé) ;
- son JUMEAU au hasard (mêmes gestes, sens tiré à pile ou face) : la note du juge est son avantage sur lui
  (juge/note.py), corrigée du nombre d'essais ;
- le CONNAISSEUR DU RISQUE, repère discipliné tiré des rapports (reports/Risque agitation et tendance courte.md) :
  chaque jour, sens de la tendance des 20 derniers jours, risque total = 10 % de la distance au mur le plus proche
  (Grossman et Zhou 1993 : risquer une part de ce qui reste au-dessus du plancher), partagé entre les marchés,
  stop à une bougie du jour (agitation prévue), rien dans le quart d'heure d'une annonce. Elle ne le voit JAMAIS :
  il dit seulement si elle fait mieux qu'un trader simple et parfaitement discipliné.
Les 12 mois cachés (après 09/2025) ne sont jamais chargés.
Depuis Test_IA : venv_gpu\\Scripts\\python.exe -m collapsar.juge.examen_humain <eleve.pt> [essais]
"""
from __future__ import annotations

import json
import sys
from datetime import datetime

import numpy as np
import pandas as pd
import torch

from collapsar.cerveau.humain import TraderHumain
from collapsar.donnees import marches as dm
from collapsar.ecole.regard import UN_MOIS, ClasseRegard, Etat, donnees_regard, jouer_comptes
from collapsar.juge.note import avantage_sur_hasard, phrase
from collapsar.mains.simulateur import CAPITAL, MUR_JOUR, MUR_TOTAL, Ordres

MARCHES_EXAMEN = ["EURUSD", "USDJPY", "XAUUSD", "USA500IDXUSD"]
DEBUT_EXAMEN = pd.Timestamp("2023-09-01")
DUREE_CHALLENGE = 6 * UN_MOIS
ECART_DEPARTS = 10 * 96
JUMEAUX = 2


@torch.no_grad()
def jouer_connaisseur_risque(c: ClasseRegard, departs: torch.Tensor, duree: int, part_distance: float = 0.10,
                             signal_jours: int = 20, stop_jours: float = 1.0) -> dict:
    n, M = len(departs), c.h.M
    e = Etat(c.h, n)
    e.recommencer(torch.ones(n, dtype=torch.bool, device=c.dev), departs.to(c.dev))
    cpt, h = e.comptes, c.h
    vivant = torch.ones(n, dtype=torch.bool, device=c.dev)
    mort, inactif, reussi = (torch.zeros_like(vivant) for _ in range(3))
    finale = torch.full((n,), CAPITAL, dtype=torch.float64, device=c.dev)
    tailles = []
    for k in range(duree):
        ordres = Ordres()
        if k % 96 == 0:
            t = cpt.t
            prix, fx = h.c[t], h.fx[t]
            passe = h.c[(t - signal_jours * 96).clamp(min=0)]
            signe = torch.sign(torch.log(prix / passe))
            idx = c.offset[None, :] + h.local[t].clamp(min=0)
            _, x = c.g.voir(idx.reshape(-1))
            stop_frac = (torch.exp(x[:, c.i_jour] * 3 - 6).reshape(n, M).double() * stop_jours).clamp(min=1e-4)
            valeur = cpt.valeur(prix, fx)
            distance = torch.minimum(valeur - (cpt.solde_minuit - MUR_JOUR * CAPITAL),
                                     valeur - (1 - MUR_TOTAL) * CAPITAL).clamp(min=0)
            actifs = (signe != 0).sum(1).clamp(min=1)
            risque = part_distance * distance / actifs                       # en dollars, par marché
            cible = signe * risque[:, None] / stop_frac
            annonce = c.cal[t][..., 0] * 48 < 0.25                            # annonce dans le quart d'heure
            garder = annonce | ~vivant[:, None]
            nan = torch.full_like(cible, float("nan"))
            stop = torch.where(signe != 0, prix * (1 - signe * stop_frac), torch.zeros_like(prix))
            ordres = Ordres(cible=torch.where(garder, nan, cible), stop=torch.where(garder, nan, stop))
            tailles += (cible.abs() / valeur[:, None])[~garder & (signe != 0)].tolist()
        r = cpt.pas(ordres)
        finale = torch.where(vivant, r["valeur"], finale)
        mort |= vivant & r["mort"]
        inactif |= vivant & r["inactif"]
        reussi |= vivant & r["reussi"]
        vivant &= ~(r["mort"] | r["reussi"] | r["fin_histoire"])
        if not vivant.any():
            break
    gains = (finale / CAPITAL - 1) * 100 / (duree / UN_MOIS)
    t = np.array(tailles) if tailles else np.zeros(1)
    return {"gain_moyen_pct": float(gains.mean()), "gains_comptes_pct_mois": gains.tolist(),
            "reussis_comptes": reussi.tolist(), "morts_comptes": (mort & ~inactif).tolist(),
            "challenges_reussis_pct": float(reussi.float().mean() * 100),
            "murs_touches_pct": float((mort & ~inactif).float().mean() * 100),
            "inactifs_pct": float(inactif.float().mean() * 100),
            "taille_max_sur_mediane": float(t.max() / max(np.median(t), 1e-9))}


def preparer(marches=MARCHES_EXAMEN, appareil="cpu") -> tuple[ClasseRegard, torch.Tensor]:
    c = ClasseRegard(marches, appareil, donnees_regard(marches, jusqua=dm.FIN_EXAMEN))
    lo, hi = c.instant(DEBUT_EXAMEN), c.h.T - DUREE_CHALLENGE - 1
    if hi <= lo:
        raise ValueError("période d'examen trop courte")
    return c, torch.arange(lo, hi, ECART_DEPARTS, device=c.dev)


def examiner(agent: TraderHumain, essais: int = 1, marches=MARCHES_EXAMEN, appareil="cpu",
             duree: int = DUREE_CHALLENGE) -> dict:
    c, departs = preparer(marches, appareil)
    elle = jouer_comptes(c, agent, departs, duree, graine=2023)
    jumeaux = [jouer_comptes(c, agent, departs, duree, graine=3000 + k, jumeau=True) for k in range(JUMEAUX)]
    connaisseur = jouer_connaisseur_risque(c, departs, duree)
    note = avantage_sur_hasard(elle, jumeaux, essais, duree, ECART_DEPARTS)
    garde = lambda r: {k: v for k, v in r.items() if not isinstance(v, list)}
    return {"marches": list(marches), "challenges": len(departs), "elle": garde(elle),
            "jumeau": garde(jumeaux[0]), "connaisseur_du_risque": garde(connaisseur), "note": note}


def main():
    fichier = sys.argv[1]
    essais = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    agent = TraderHumain().to(dev)
    agent.charger(torch.load(fichier, map_location=dev, weights_only=False)["cerveau"])
    r = examiner(agent, essais, appareil=dev)
    sortie = dm.RACINE / "collapsar" / "vie" / f"examen_humain_{datetime.now():%Y%m%d_%H%M}.json"
    sortie.write_text(json.dumps(r, ensure_ascii=False, indent=1), encoding="utf-8")
    e, cr = r["elle"], r["connaisseur_du_risque"]
    print(f"EXAMEN 09/2023 -> 09/2025, {r['challenges']} challenges, marchés {', '.join(r['marches'])}")
    print(f"elle : {e['gain_moyen_pct']:+.2f} %/mois, réussis {e['challenges_reussis_pct']:.0f} %, murs "
          f"{e['murs_touches_pct']:.0f} %, taille max/médiane {e['taille_max_sur_mediane']:.1f}")
    print(f"connaisseur du risque : {cr['gain_moyen_pct']:+.2f} %/mois, réussis {cr['challenges_reussis_pct']:.0f} %, "
          f"murs {cr['murs_touches_pct']:.0f} %")
    print("NOTE : " + phrase(r["note"]))
    print(f"(enregistré : {sortie})")


if __name__ == "__main__":
    main()
