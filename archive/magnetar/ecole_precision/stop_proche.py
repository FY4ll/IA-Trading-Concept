"""LES STOPS PROCHES, SUR UNE SEULE BRANCHE (19/10/2026, accord du chef de projet pour MAGNETAR : « c'est facile de ne
rien perdre quand on a un SL 100 $ plus loin »).

Constat (vie/arbre_or/contrefactuel/rapport.md, examen 2023) : la moitié de ses stops sont à plus de 1,5 % du prix, un
quart à plus de 6,5 % ; tout son avantage d'entrée est dans les trades à stop serré. Un trader pose son stop JUSTE
DERRIÈRE la structure ; à 100 pips (10 $) de l'entrée sur l'or, 1R se fait facilement.

Réglage `precision` du TEMPÉRAMENT d'une branche (absent = rien ne change : HYPERNOVA, toutes les autres branches) :
  {"stop_max_agitation": X}
=> à chaque ouverture, les niveaux de stop (bord lointain d'une zone, creux / sommet confirmé) à plus de X agitations
de l'entrée, MARGE COMPRISE, sont simplement retirés de ses choix (cerveau.politique : masques) ; si aucun niveau n'est
assez proche, aucune ouverture n'est possible à ce moment-là (ni au marché, ni par ordre limite). Ce n'est PAS une règle
sur QUAND trader : seulement sur OÙ un trader peut poser un stop. Son jumeau au hasard a le même plafond (examen juste).
Agitation = moyenne (plus haut - plus bas) des 14 derniers jours (structure.py) : le plafond suit l'époque et vaut la
même chose sur l'or réel et sur l'or retourné (prix plus bas).
La branche hérite du réglage à chaque division (une fille d'elle le garde ; une fille d'une autre branche ne l'a pas).

GREFFE (arbre ARRÊTÉ ; sauvegarde complète automatique sauvegardes/avant_precision_<date>/) :
  venv_gpu\\Scripts\\python.exe -m collapsar.ecole.precision.stop_proche greffer --plafond 0.4 --dossier collapsar\\vie\\arbre_or
  (réglages de l'or : variable COLLAPSAR_PRECISION_REGLAGES)
La branche la plus faible (hors cime) est archivée et remplacée par une branche « precision » née de la cime : copie
EXACTE de ses poids (journal de trading compris si la cime l'a : il est hérité et actif, logs MT5 écrits), seul le
réglage `precision` s'ajoute. Retour arrière : `stop_proche defaire`.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
from datetime import datetime
from pathlib import Path

import torch

from collapsar.ecole.precision.reglages import R, VIE

FICHIER = "precision.json"


def greffer(dossier: Path | None = None, plafond: float = 0.4, dire=print, stamp: str | None = None) -> dict:
    from collapsar.arbre.jardinier import Arbre
    from collapsar.arbre.journal import Journal
    from collapsar.ecole.precision import cerveau as C
    from collapsar.ecole.precision import journal_trading as JN
    from collapsar.ecole.precision import suiveur as SV
    plafond = float(plafond)
    assert 0 < plafond < 50, plafond
    dossier = (Path(dossier) if dossier else VIE).resolve()
    if (dossier / FICHIER).exists():
        raise SystemExit(f"{dossier} : déjà greffé des stops proches ({FICHIER} existe)")
    pid = SV._pid_vivant(dossier / "coeur.verrou")
    if pid:
        raise SystemExit(f"le cœur bat encore (processus {pid}) : créer {dossier / 'ARRET'} et attendre sa fin")
    if not (dossier / "arbre.json").exists():
        raise SystemExit(f"{dossier} : aucun arbre")
    JN._allumer_comme_l_arbre(dossier)
    arbre = Arbre.charger(dossier / "arbre.json")
    cime = arbre.cime
    faible = SV.la_plus_faible(arbre, {cime})
    if faible is None:
        raise SystemExit("aucune branche à remplacer (hors cime)")
    stamp = stamp or datetime.now().strftime("%Y%m%d_%H%M%S")
    sauve = dossier / "sauvegardes" / f"avant_precision_{stamp}"
    sauve.mkdir(parents=True, exist_ok=True)
    for nom in ("arbre.json", "cime.pt", "derniers_examens.json", "journal_croissance.jsonl", "journal.json",
                "peur.json", "suiveur.json", "foule.json"):
        if (dossier / nom).exists():
            shutil.copy2(dossier / nom, sauve / nom)
    if (sauve / "branches").exists():
        shutil.rmtree(sauve / "branches")
    shutil.copytree(dossier / "branches", sauve / "branches")
    dire(f"sauvegarde de l'arbre : {sauve}")
    e = torch.load(dossier / "branches" / f"{cime}.pt", map_location="cpu", weights_only=False)
    net = C.cerveau_pour(e["cerveau"])                  # copie exacte des poids de la cime (journal compris)
    tc = dict(e.get("temperament") or arbre.branches[cime].temperament)
    tc.pop("alertes", None)
    t = {**tc, "nom": "precision", "precision": {"stop_max_agitation": plafond},
         "heritage": f"cime {cime}, stops proches <= {plafond:g} agitation ({stamp})"}
    arbre.mourir(faible, "coupée")
    (dossier / "archives").mkdir(exist_ok=True)
    for f in (f"{faible}.pt", f"{faible}_meilleur.pt"):
        if (dossier / "branches" / f).exists():
            shutil.move(str(dossier / "branches" / f), str(dossier / "archives" / f))
    b = arbre.naitre([cime], t)
    opt = torch.optim.AdamW(net.parameters(), lr=float(t.get("vitesse", R().ecole.vitesse)), weight_decay=1e-4)
    tmp = dossier / "branches" / f"{b.nom}.pt.tmp"
    torch.save({"cerveau": net.state_dict(), "opt": opt.state_dict(), "temperament": t}, tmp)
    os.replace(tmp, dossier / "branches" / f"{b.nom}.pt")
    arbre._elire_cime()
    arbre.sauver(dossier / "arbre.json")
    fx = dossier / "derniers_examens.json"
    if fx.exists():
        x = json.loads(fx.read_text(encoding="utf-8"))
        x.pop(faible, None)
        fx.write_text(json.dumps(x, ensure_ascii=False, default=float), encoding="utf-8")
    journal = Journal(dossier / "journal_croissance.jsonl")
    journal.ecrire("coupe", branche=faible, raison=f"remplacée par une branche « precision » (stops proches <= {plafond:g} agitation)")
    journal.ecrire("naissance", branche=b.nom, parents=[cime], temperament=t, heritage=t["heritage"])
    info = {"date": datetime.now().isoformat(timespec="seconds"), "plafond_agitation": plafond, "branche": b.nom,
            "cime": cime, "remplacee": faible, "journal": bool(net.n_journal), "sauvegarde": str(sauve)}
    journal.ecrire("greffe_precision", **{k: v for k, v in info.items() if k != "date"})
    (dossier / FICHIER).write_text(json.dumps(info, ensure_ascii=False, indent=1), encoding="utf-8")
    dire(f"branche {faible} archivée ; branche {b.nom} « precision » (stops <= {plafond:g} agitation, journal "
         f"{'hérité' if net.n_journal else 'absent'}) née de la cime {cime}")
    return info


def defaire(dossier: Path | None = None, dire=print):
    """Retour arrière : remet la sauvegarde d'avant la greffe (arbre arrêté)."""
    from collapsar.ecole.precision import suiveur as SV
    dossier = (Path(dossier) if dossier else VIE).resolve()
    if SV._pid_vivant(dossier / "coeur.verrou"):
        raise SystemExit("le cœur bat encore : l'arrêter d'abord (fichier ARRET)")
    info = json.loads((dossier / FICHIER).read_text(encoding="utf-8"))
    sauve = Path(info["sauvegarde"])
    shutil.rmtree(dossier / "branches")
    shutil.copytree(sauve / "branches", dossier / "branches")
    for nom in ("arbre.json", "cime.pt", "derniers_examens.json", "journal_croissance.jsonl"):
        if (sauve / nom).exists():
            shutil.copy2(sauve / nom, dossier / nom)
    for f in (f"{info['remplacee']}.pt", f"{info['remplacee']}_meilleur.pt"):
        (dossier / "archives" / f).unlink(missing_ok=True)
    (dossier / FICHIER).unlink()
    dire(f"greffe des stops proches défaite : état remis depuis {sauve}")


def main(argv=None):
    ap = argparse.ArgumentParser(description="stops proches sur une branche (école de la précision)")
    ap.add_argument("quoi", choices=["greffer", "defaire"])
    ap.add_argument("--dossier", default=None)
    ap.add_argument("--plafond", type=float, default=0.4, help="distance maximale entrée -> stop, en agitations")
    a = ap.parse_args(argv)
    d = Path(a.dossier) if a.dossier else None
    if a.quoi == "greffer":
        greffer(d, a.plafond)
    else:
        defaire(d)


if __name__ == "__main__":
    main()
