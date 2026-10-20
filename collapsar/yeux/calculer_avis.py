"""Calcule et enregistre son avis avec la cime du moment (tous les marchés, 20 ans d'historique horaire en contexte,
regard de fond compris). Depuis Test_IA : venv_gpu\\Scripts\\python.exe -u -m collapsar.yeux.calculer_avis"""
from __future__ import annotations

import os

import torch

from collapsar.ecole import lancer_avis


def main():
    os.environ["COLLAPSAR_NOUVEL_AVIS"] = "1"
    dev = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    avis = lancer_avis.avis_de_la_cime(dev)
    print("colonnes de l'avis :", avis.table.shape[1], flush=True)


if __name__ == "__main__":
    main()
