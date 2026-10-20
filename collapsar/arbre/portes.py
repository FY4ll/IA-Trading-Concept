"""Les portes de l'arbre, ouvertes AUTOMATIQUEMENT (décision du chef de projet, 13/10/2026).

Porte « observer -> école » : elle s'ouvre quand
1. la cime a un niveau d'au moins 52 % sur 2020-2022 (moyenne de ses 3 dernières notes, au moins 3 notes) ;
2. ET le test de vérité dit qu'il y a de l'argent à apprendre : la démonstration « tenir son avis » jouée sur le
   simulateur fidèle (frais FTMO, frais de nuit, fermetures forcées, murs) gagne sur 2020-2022 — les années de
   l'école, JAMAIS l'examen 2023-2025.
La vérification (calcul de son avis + test) tourne dans un programme à part, sans arrêter le cœur ; elle n'est
relancée que si la cime a changé ou progressé d'au moins 0,2 point depuis la dernière.
"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timedelta

from collapsar.arbre.jardinier import Arbre, maintenant
from collapsar.donnees import marches as dm

VIE = dm.RACINE / "collapsar" / "vie"
ETAT_PORTES = VIE / "portes.json"
NIVEAU_ECOLE = 52.0
PROGRES_POUR_REVERIFIER = 0.2


def lire() -> dict:
    if ETAT_PORTES.exists():
        return json.loads(ETAT_PORTES.read_text(encoding="utf-8"))
    return {"ecole": {"ouverte": False, "verifications": []}}


def ecrire(etat: dict):
    tmp = ETAT_PORTES.with_suffix(".tmp")
    tmp.write_text(json.dumps(etat, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(ETAT_PORTES)


def niveau_cime(arbre: Arbre) -> float | None:
    b = arbre.branches.get(arbre.cime) if arbre.cime else None
    if b is None or len(b.scores) < 3:
        return None
    return b.score


def faut_il_verifier(arbre: Arbre, etat: dict) -> bool:
    """Condition 1 remplie, porte encore fermée, aucune vérification en cours, et du nouveau depuis la dernière."""
    e = etat["ecole"]
    niveau = niveau_cime(arbre)
    en_cours = e.get("en_cours")
    if en_cours and datetime.fromisoformat(en_cours["depuis"]) < datetime.now() - timedelta(hours=2):
        en_cours = None                                   # une vérification bloquée depuis 2 h est considérée perdue
    if e.get("ouverte") or en_cours or niveau is None or niveau < NIVEAU_ECOLE:
        return False
    if not e["verifications"]:
        return True
    der = e["verifications"][-1]
    return der["cime"] != arbre.cime or niveau >= der["niveau"] + PROGRES_POUR_REVERIFIER


def lancer_verification(arbre: Arbre, etat: dict, python: str = sys.executable):
    etat["ecole"]["en_cours"] = {"depuis": maintenant(), "cime": arbre.cime, "niveau": niveau_cime(arbre)}
    ecrire(etat)
    journal = VIE / "logs" / f"porte_ecole_{maintenant().replace(':', '')}.txt"
    with open(journal, "w", encoding="utf-8") as f:
        subprocess.Popen([python, "-u", "-m", "collapsar.arbre.verifier_porte_ecole", arbre.cime],
                         cwd=str(dm.RACINE), stdout=f, stderr=subprocess.STDOUT,
                         creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))


def resume(arbre: Arbre, etat: dict) -> str:
    """Une ligne pour le téléphone : où en est la porte de l'école."""
    e = etat["ecole"]
    if e.get("ouverte"):
        return "Porte de l'école : OUVERTE."
    niveau = niveau_cime(arbre)
    txt = f"Porte de l'école : cime {niveau:.2f} % / {NIVEAU_ECOLE:.0f} % requis".replace(".", ",") if niveau else \
        "Porte de l'école : la cime n'a pas encore 3 notes"
    if e.get("en_cours"):
        txt += " ; vérification en cours"
    elif e["verifications"]:
        d = e["verifications"][-1]
        txt += f" ; dernier test de vérité : {d['gain_pct_mois']:+.2f} %/mois".replace(".", ",")
    return txt + "."
