"""Arbre 3 (14/10/2026) : la vision du trader (« pas de menu »).

Archive l'arbre 2 (racines « sens / ampleur / agitation », plafonnées à ~50,8 %) dans vie/arbre2_14oct/ et plante une
graine à vision de trader GREFFÉE : elle reprend les yeux et le tronc de la cime de l'arbre 2 (la lecture des
graphiques n'est pas perdue), seule la tête qui juge les coups est neuve.
À lancer CŒUR ARRÊTÉ (vie/ARRET), puis mettre « vision: trader » dans reglages.yaml et relancer le cœur.
Depuis Test_IA : venv_gpu\\Scripts\\python.exe -m collapsar.arbre.nouvel_arbre_trader
"""
from __future__ import annotations

import shutil
import sys
from datetime import datetime

import psutil
import torch
import yaml

from collapsar.arbre import coeur
from collapsar.arbre.jardinier import TEMPERAMENT_GRAINE, Arbre, Reglages
from collapsar.arbre.journal import Journal
from collapsar.cerveau.trader import CerveauTrader, greffer

ARCHIVE = coeur.VIE / "arbre2_14oct"


def main():
    if coeur.VERROU.exists():
        try:
            pid = int(coeur.VERROU.read_text())
            if psutil.pid_exists(pid) and "python" in psutil.Process(pid).name().lower():
                sys.exit(f"le cœur tourne encore (processus {pid}) : l'arrêter d'abord")
        except (ValueError, psutil.Error):
            pass
    if ARCHIVE.exists():
        # « recommencer » : l'arbre 3 en cours (essai) est archivé à part ; la greffe vient toujours de l'arbre 2
        if "recommencer" not in sys.argv[1:]:
            sys.exit(f"{ARCHIVE} existe déjà : rien n'est touché (argument « recommencer » pour replanter l'arbre 3)")
        essai = coeur.VIE / f"arbre3_essai_{datetime.now():%Y%m%d_%H%M}"
        essai.mkdir(parents=True)
        for nom in ("arbre.json", "journal_croissance.jsonl", "branches", "archives"):
            if (coeur.VIE / nom).exists():
                shutil.move(str(coeur.VIE / nom), str(essai / nom))
        cime = Arbre.charger(ARCHIVE / "arbre.json").cime
        racines = torch.load(ARCHIVE / "branches" / f"{cime}.pt", map_location="cpu", weights_only=True)["cerveau"]
        print(f"essai précédent de l'arbre 3 archivé dans {essai}")
    else:
        ancien = Arbre.charger(coeur.ETAT)
        cime = ancien.cime
        racines = torch.load(coeur.BRANCHES / f"{cime}.pt", map_location="cpu", weights_only=True)["cerveau"]
        ARCHIVE.mkdir(parents=True)
        for nom in ("arbre.json", "journal_croissance.jsonl", "branches", "archives"):
            if (coeur.VIE / nom).exists():
                shutil.move(str(coeur.VIE / nom), str(ARCHIVE / nom))
        print(f"arbre 2 archivé dans {ARCHIVE} (cime {cime}, {ancien.battements} battements)")

    reglages = yaml.safe_load(coeur.REGLAGES.read_text(encoding="utf-8")) or {}
    arbre = Arbre(Reglages(**reglages.get("arbre", {})))
    # yeux neufs : plus d'oubli forcé et graphiques retournés dès la graine (contre le par cœur, 14/10 07h40)
    graine = arbre.naitre([], dict(TEMPERAMENT_GRAINE, oubli=0.3, miroir=0.5, bruit=0.15, masque=0.25)
                          if "neuf" in sys.argv[1:] else TEMPERAMENT_GRAINE)
    torch.manual_seed(0)
    cerveau = CerveauTrader(oubli=graine.temperament["oubli"], largeur=float(reglages.get("largeur_trader", 1.0)))
    # « neuf » (14/10 07h40) : SANS greffe — les yeux de l'arbre 2 connaissaient par cœur la suite de leurs années
    # (la tête récitait leur mémoire : +48 % du risque par coup sur les années apprises après 2 M de coups)
    n = 0 if "neuf" in sys.argv[1:] else greffer(cerveau, racines)
    coeur.VISION = "trader"
    coeur.sauver_branche(graine.nom, cerveau, coeur.optimiseur(cerveau, graine.temperament))
    arbre.noter_seve()
    arbre.sauver(coeur.ETAT)
    Journal(coeur.VIE / "journal_croissance.jsonl").ecrire(
        "naissance", branche=graine.nom, parents=[], temperament=graine.temperament,
        greffe=f"yeux et tronc de la cime {cime} de l'arbre 2 ({n} morceaux repris)" if n else "yeux neufs")
    print(f"graine {graine.nom} plantée : vision du trader, " + (f"{n} morceaux des yeux et du tronc repris de {cime}"
                                                                 if n else "yeux neufs (sans greffe)"))


if __name__ == "__main__":
    main()
