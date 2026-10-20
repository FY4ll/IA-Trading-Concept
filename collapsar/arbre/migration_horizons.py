"""Ajoute un horizon aux cerveaux des branches SANS perdre ce qu'elles savent (13/10/2026 : + « 1 mois »).

La couche de réponse des racines passe de 3 x 4 à 3 x 5 sorties (sens, ampleur, agitation) : les anciennes sorties
sont recopiées telles quelles ; la nouvelle (1 mois) démarre comme une copie de la plus longue existante (1 semaine),
puis apprend. La mémoire de l'optimiseur est remise à zéro (sa forme change). Une sauvegarde de chaque fichier est
gardée (.avant_1mois). À lancer cœur arrêté : venv_gpu\\Scripts\\python.exe -m collapsar.arbre.migration_horizons
"""
from __future__ import annotations

import shutil

import torch

from collapsar.donnees import marches as dm
from collapsar.regarder.exercices import HORIZONS

VIE = dm.RACINE / "collapsar" / "vie"


def etendre(etat: dict, nouveau: int) -> bool:
    w, b = etat["regarder.weight"], etat["regarder.bias"]
    ancien = w.shape[0] // 3
    if ancien >= nouveau:
        return False
    lignes = []
    for bloc in range(3):                                   # sens, ampleur, agitation
        rangs = list(range(bloc * ancien, (bloc + 1) * ancien))
        rangs += [bloc * ancien + ancien - 1] * (nouveau - ancien)       # copie du plus long horizon existant
        lignes += rangs
    etat["regarder.weight"] = w[lignes].clone()
    etat["regarder.bias"] = b[lignes].clone()
    return True


def main():
    n = len(HORIZONS)
    faits = 0
    for dossier in (VIE / "branches", VIE / "archives"):
        for f in dossier.glob("*.pt"):
            contenu = torch.load(f, map_location="cpu", weights_only=True)
            if etendre(contenu["cerveau"], n):
                shutil.copy2(f, f.with_suffix(".avant_1mois"))
                contenu["optimiseur"] = None
                torch.save(contenu, f)
                faits += 1
                print(f"{f.parent.name}/{f.name} : {n} horizons")
    print(f"{faits} cerveau(x) migré(s)")


if __name__ == "__main__":
    main()
