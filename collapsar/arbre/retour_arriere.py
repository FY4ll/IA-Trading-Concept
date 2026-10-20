"""Retour arrière de l'arbre (13/10/2026 midi) : l'essai de l'horizon « 1 mois » a fait reculer les racines
(52,3 % -> 51,5 %) sans aucun avantage sur 2023-2025. On remet les cerveaux sauvegardés juste avant (.avant_1mois)
et leurs notes d'alors ; les branches nées après sont archivées. À lancer cœur arrêté :
venv_gpu\\Scripts\\python.exe -m collapsar.arbre.retour_arriere
"""
from __future__ import annotations

import shutil

import torch

from collapsar.arbre.jardinier import Arbre
from collapsar.arbre.journal import Journal
from collapsar.arbre.migration_horizons import etendre
from collapsar.donnees import marches as dm
from collapsar.regarder.exercices import HORIZONS

VIE = dm.RACINE / "collapsar" / "vie"
AVANT = "2026-10-13T08:56:30"
SAUVEGARDES = ["G", "I", "J", "K"]


def main():
    arbre = Arbre.charger(VIE / "arbre.json")
    for b in arbre.vivantes():                                   # les branches d'après : archivées
        if b.nom not in SAUVEGARDES:
            arbre.mourir(b.nom, "retour arrière")
            f = VIE / "branches" / f"{b.nom}.pt"
            if f.exists():
                shutil.move(str(f), str(VIE / "archives" / f"{b.nom}.pt"))
    for nom in SAUVEGARDES:
        contenu = torch.load(VIE / "branches" / f"{nom}.avant_1mois", map_location="cpu", weights_only=True)
        etendre(contenu["cerveau"], len(HORIZONS))
        contenu["optimiseur"] = None
        torch.save(contenu, VIE / "branches" / f"{nom}.pt")
        b = arbre.branches[nom]
        b.morte, b.cause = None, None
        b.scores = [s for s in b.scores if s[0] <= AVANT]
        b.seve = [s for s in b.seve if s[0] <= AVANT]
        b.battements = len(b.scores)
        b.meilleur, b.sans_progres = b.score, 0
    arbre._elire_cime()
    arbre.noter_seve()
    arbre.sauver(VIE / "arbre.json")
    Journal(VIE / "journal_croissance.jsonl").ecrire(
        "retour_arriere", branches=SAUVEGARDES, cime=arbre.cime,
        raison="l'horizon 1 mois a fait reculer les racines de 52,3 à 51,5 % sans avantage sur 2023-2025")
    print("cime", arbre.cime, {n: round(arbre.branches[n].score, 2) for n in SAUVEGARDES})


if __name__ == "__main__":
    main()
