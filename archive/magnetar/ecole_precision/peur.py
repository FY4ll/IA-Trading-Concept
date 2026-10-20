"""LA PEUR DU MUR CORRIGÉE, SUR UNE SEULE BRANCHE (19/10/2026, accord du chef de projet pour MAGNETAR).

Avant (toutes les branches, et HYPERNOVA) : à chaque bougie, une BAISSE du compte compte x (1 + 4 d²), d = part de la
perte permise déjà consommée (jeu.ressenti) : x1,16 dès -1 % sur la journée, x2 à mi-chemin, x5 au mur. Chaque
oscillation contre elle fait plus mal qu'un mouvement égal en sa faveur : garder un trade coûte, le couper tout de suite
« soulage » (constat de l'essai : 60 % des trades fermés à la main, gagnants rendus).

Réglage `peur` du TEMPÉRAMENT d'une branche (absent = la peur d'avant : rien ne change pour les autres branches) :
- {"mode": "pres_des_murs", "seuil": 0.5, "max": 5.0}  (CHOISI) : l'argent compte tel quel, gain ou perte ; la douleur
  EN PLUS n'existe que près des murs (x1 tant que moins de la moitié de la perte permise est consommée, puis monte en
  ligne droite jusqu'à x5 au mur) ET seulement pour la baisse SOUS le plus haut solde RÉALISÉ de la journée (un trade
  gagnant qui oscille au-dessus ne fait jamais mal ; une perte réalisée, ou une baisse qui entame l'argent déjà
  encaissé, si) : jeu.douleur_pres_des_murs ;
- {"mode": "fermeture_r"} (l'autre option, gardée en réglage) : rien pendant le trade ; à sa fermeture, son résultat en
  R. Pas choisie : la taille (0,1 à 2 % de risque) n'y compte plus (un trade à 2 % = un trade à 0,1 %), seuls le mur
  (-20) et la réussite (+5) la voient, et le signal est plus rare (apprentissage plus lent).
La branche hérite de ce réglage à chaque division (une fille d'elle le garde ; une fille de la cime ne l'a pas).

GREFFE (arbre ARRÊTÉ ; sauvegarde automatique sauvegardes/avant_peur_<date>/) :
  venv_gpu\\Scripts\\python.exe -m collapsar.ecole.precision.peur greffer --dossier collapsar\\vie\\arbre_or
  (réglages de l'or : variable COLLAPSAR_PRECISION_REGLAGES, comme greffer_journal_magnetar.ps1)
La branche la plus faible (hors cime et hors branche au journal) est archivée et remplacée par une branche « sans_peur »
née de la cime : copie EXACTE de ses poids, seul le réglage `peur` change. Retour arrière : `peur defaire`.
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

CHOIX = {"mode": "pres_des_murs", "seuil": 0.5, "max": 5.0}
AUTRE = {"mode": "fermeture_r"}
FICHIER = "peur.json"


def greffer(dossier: Path | None = None, peur: dict | None = None, dire=print) -> dict:
    from collapsar.arbre.jardinier import Arbre
    from collapsar.arbre.journal import Journal
    from collapsar.ecole.precision import cerveau as C
    from collapsar.ecole.precision import jeu as JEU
    from collapsar.ecole.precision import journal_trading as JN
    from collapsar.ecole.precision import suiveur as SV
    peur = dict(peur or CHOIX)
    assert peur["mode"] in JEU.PEURS, peur
    dossier = (Path(dossier) if dossier else VIE).resolve()
    if (dossier / FICHIER).exists():
        raise SystemExit(f"{dossier} : déjà greffé de la peur corrigée ({FICHIER} existe)")
    pid = SV._pid_vivant(dossier / "coeur.verrou")
    if pid:
        raise SystemExit(f"le cœur bat encore (processus {pid}) : créer {dossier / 'ARRET'} et attendre sa fin")
    if not (dossier / "arbre.json").exists():
        raise SystemExit(f"{dossier} : aucun arbre")
    JN._allumer_comme_l_arbre(dossier)
    arbre = Arbre.charger(dossier / "arbre.json")
    cime = arbre.cime
    au_journal = {b.nom for b in arbre.vivantes() if b.temperament.get("journal")}
    faible = SV.la_plus_faible(arbre, {cime} | au_journal)
    if faible is None:
        raise SystemExit("aucune branche à remplacer (hors cime et branche au journal)")
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    sauve = dossier / "sauvegardes" / f"avant_peur_{stamp}"
    sauve.mkdir(parents=True)
    for nom in ("arbre.json", "cime.pt", "derniers_examens.json", "journal_croissance.jsonl"):
        if (dossier / nom).exists():
            shutil.copy2(dossier / nom, sauve / nom)
    shutil.copytree(dossier / "branches", sauve / "branches")
    dire(f"sauvegarde de l'arbre : {sauve}")
    e = torch.load(dossier / "branches" / f"{cime}.pt", map_location="cpu", weights_only=False)
    net = C.cerveau_pour(e["cerveau"])                  # copie exacte des poids de la cime
    if net.n_journal:
        raise SystemExit(f"la cime {cime} voit le journal : greffer la peur sur une copie d'une cime sans journal")
    tc = dict(e.get("temperament") or arbre.branches[cime].temperament)
    tc.pop("alertes", None)
    tc.pop("journal", None)
    t = {**tc, "nom": "sans_peur", "peur": peur, "heritage": f"cime {cime}, peur du mur corrigée ({stamp})"}
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
    journal.ecrire("coupe", branche=faible, raison="remplacée par une branche « sans_peur » (peur du mur corrigée)")
    journal.ecrire("naissance", branche=b.nom, parents=[cime], temperament=t, heritage=t["heritage"])
    info = {"date": datetime.now().isoformat(timespec="seconds"), "peur": peur, "branche": b.nom, "cime": cime,
            "remplacee": faible, "sauvegarde": str(sauve)}
    journal.ecrire("greffe_peur", **{k: v for k, v in info.items() if k != "date"})
    (dossier / FICHIER).write_text(json.dumps(info, ensure_ascii=False, indent=1), encoding="utf-8")
    dire(f"branche {faible} archivée ; branche {b.nom} « sans_peur » ({peur}) née de la cime {cime}")
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
    dire(f"greffe de la peur défaite : état remis depuis {sauve}")


def main(argv=None):
    ap = argparse.ArgumentParser(description="peur du mur corrigée sur une branche (école de la précision)")
    ap.add_argument("quoi", choices=["greffer", "defaire"])
    ap.add_argument("--dossier", default=None)
    ap.add_argument("--mode", default=CHOIX["mode"], choices=["pres_des_murs", "fermeture_r"])
    a = ap.parse_args(argv)
    d = Path(a.dossier) if a.dossier else None
    if a.quoi == "greffer":
        greffer(d, CHOIX if a.mode == "pres_des_murs" else AUTRE)
    else:
        defaire(d)


if __name__ == "__main__":
    main()
