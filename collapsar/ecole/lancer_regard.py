"""Lance la nouvelle école « elle choisit quand revenir regarder » (14/10/2026).

Classes (plan validé) :
  1 : l'euro-dollar seul (et son miroir, contre le par cœur d'une tendance passée) ;
  2 : quelques marchés différents (devises, or, un indice) ;
  3 : tous les marchés FTMO sur un seul compte (à brancher après la classe 2).
Toutes les CONTROLE_MINUTES : contrôle sur 2020-2022 (jamais appris) et témoin du par cœur sur 2016-2019 (appris),
argent ET comportement ; l'élève est sauvé (eleve.pt), le meilleur au contrôle aussi (meilleur.pt), avec un carnet
de bord d'exemple (le premier compte de contrôle). Reprend où il en était si eleve.pt existe.
Depuis Test_IA : venv_gpu\\Scripts\\python.exe -u -m collapsar.ecole.lancer_regard --classe 1 --minutes 120
Arrêt propre : créer collapsar/vie/ecole_regard/STOP (il finit sa leçon, se contrôle, se sauve et s'arrête).
"""
from __future__ import annotations

import argparse
import json
import os
import time
from datetime import datetime

import pandas as pd
import psutil
import torch

from collapsar.cerveau.humain import TraderHumain
from collapsar.donnees import marches as dm
from collapsar.ecole.verite import marche_cache
from collapsar.ecole.regard import (DUREE_PARTIE, ClasseRegard, ProfesseurRegard, TEMOIN_DE, TEMOIN_JUSQUA, controler,
                                    donnees_regard, jouer_comptes)
from collapsar.mains.fiches import MIROIR
from collapsar.surveillance import carnet, telephone

VIE = dm.RACINE / "collapsar" / "vie"
RACINE_ECOLE = VIE / "ecole_regard"
CLASSES = {1: ["EURUSD"], 2: ["EURUSD", "USDJPY", "XAUUSD", "USA500IDXUSD"]}
CONTROLE_MINUTES = 15
DERNIER = {}                       # le dernier contrôle, pour le message de fin sur le téléphone


def dire(texte):
    print(f"[{datetime.now():%d/%m %H:%M:%S}] {texte}", flush=True)


def verrou(dossier):
    f = dossier / "ecole.verrou"
    if f.exists():
        try:
            pid = int(f.read_text())
            if pid != os.getpid() and psutil.pid_exists(pid) and "python" in psutil.Process(pid).name().lower():
                raise SystemExit(f"l'école tourne déjà (processus {pid})")
        except ValueError:
            pass
    dossier.mkdir(parents=True, exist_ok=True)
    f.write_text(str(os.getpid()))
    return f


def resume(r: dict) -> str:
    return (f"{r['gain_moyen_pct']:+.2f} %/mois, réussis {r['challenges_reussis_pct']:.0f} %, murs "
            f"{r['murs_touches_pct']:.0f} %, inactivité {r['inactifs_pct']:.0f} %, {r['jours_trading_moyen']:.0f} jours "
            f"de trading, baisse max {r['baisse_max_moyenne_pct']:.1f} % | regarde "
            f"{r['regards_par_jour']:.1f} fois/jour, {r['trades_par_mois']:.1f} trades/mois, tient "
            f"{r['tenue_mediane_h']:.0f} h (médiane), stop {r['avec_stop_pct']:.0f} %, en position "
            f"{r['temps_en_position_pct']:.0f} % du temps")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--classe", type=int, default=1)
    ap.add_argument("--minutes", type=float, default=120)
    ap.add_argument("--parties", type=int, default=512)
    ap.add_argument("--pas", type=int, default=512)
    ap.add_argument("--appareil", default="cuda" if torch.cuda.is_available() else "cpu")
    ap.add_argument("--essai", action="store_true", help="dossier d'essai à part (l'élève de la classe n'est pas touché)")
    ap.add_argument("--verite", action="store_true", help="test de vérité de l'école : faux euro-dollar à tendance cachée")
    args = ap.parse_args()
    dossier = RACINE_ECOLE / ("verite" if args.verite else f"classe{args.classe}" + ("_essai" if args.essai else ""))
    f_verrou = verrou(dossier)
    if args.verite:
        args.essai = True                      # pas de message téléphone pour le test de vérité
    stop = RACINE_ECOLE / "STOP"
    marches = CLASSES[args.classe]
    dev = args.appareil
    dire(f"classe {args.classe} : {', '.join(marches)} (+ miroirs), {args.parties} comptes, appareil {dev}")
    annonces = None
    if args.verite:
        marches = ["EURUSD"]
        faux = marche_cache(graine=1)
        donnees = {"EURUSD": faux, "EURUSD" + MIROIR: dm.miroir(faux)}
        annonces = pd.DataFrame({"temps": pd.to_datetime([]), "devise": []})
        dire("TEST DE VÉRITÉ : faux euro-dollar avec une tendance cachée (elle ne le sait pas)")
    else:
        donnees = donnees_regard(marches + [m + MIROIR for m in marches])
    reel = ClasseRegard(marches, dev, donnees, annonces)
    miroir = ClasseRegard([m + MIROIR for m in marches], dev, donnees, annonces)
    agent = TraderHumain().to(dev)
    fichier = dossier / "eleve.pt"
    lecons, meilleur = 0, None
    if fichier.exists():
        etat = torch.load(fichier, map_location=dev, weights_only=False)
        agent.charger(etat["cerveau"])
        lecons, meilleur = etat.get("lecons", 0), etat.get("meilleur")
        dire(f"reprise : {lecons} leçons déjà faites")
    prof = ProfesseurRegard([reel, miroir], agent, parties=args.parties, pas=args.pas, graine=lecons)
    n_param = sum(p.numel() for p in agent.parameters())
    dire(f"cerveau neuf et petit : {n_param:,} connexions".replace(",", " "))
    if not args.essai:
        telephone.envoyer_texte(f"COLLAPSAR — école classe {args.classe} lancée",
                                f"{', '.join(marches)}, {args.minutes:.0f} min. Contrôle toutes les {CONTROLE_MINUTES} min "
                                "sur 2020-2022 (années jamais vues).")
    journal = dossier / "journal.jsonl"
    fin = time.time() + args.minutes * 60
    prochain_controle = time.time() + CONTROLE_MINUTES * 60
    try:
        while time.time() < fin and not stop.exists():
            t0 = time.time()
            jeu = prof.jouer()
            appris = prof.apprendre()
            lecons += 1
            dire(f"leçon {lecons} ({jeu['monde']}) : regarde {jeu['regards_par_jour']:.1f} fois/jour (revient dans "
                 f"{jeu['delai_moyen_h']:.1f} h), garde {jeu['garder_pct']:.0f} % / protège {jeu['proteger_pct']:.0f} % "
                 f"/ change {jeu['changer_pct']:.0f} % (risque {jeu['risque_moyen_pct']:.2f} %/bougie du jour), en position {jeu['en_position_pct']:.0f} %, murs {jeu['morts']} (dont inactivité {jeu['inactifs']}), "
                 f"réussis {jeu['reussis']}, récompense/jour {jeu['recompense_par_jour']:+.3f} ({time.time() - t0:.0f} s)")
            with journal.open("a", encoding="utf-8") as j:
                j.write(json.dumps({"temps": datetime.now().isoformat(timespec="seconds"), "lecon": lecons,
                                    **jeu, **appris}, ensure_ascii=False) + "\n")
            if time.time() >= prochain_controle or time.time() >= fin or stop.exists():
                prochain_controle = time.time() + CONTROLE_MINUTES * 60
                meilleur = controle_et_sauvegarde(reel, agent, dossier, lecons, meilleur, journal)
    finally:
        torch.save({"cerveau": agent.state_dict(), "lecons": lecons, "meilleur": meilleur}, fichier)
        f_verrou.unlink(missing_ok=True)
        dire(f"école arrêtée après {lecons} leçons ; élève sauvé dans {fichier}")
        if not args.essai:
            telephone.envoyer_texte(f"COLLAPSAR — école classe {args.classe} arrêtée ({lecons} leçons)",
                                    "Dernier contrôle 2020-2022 : " + DERNIER.get("texte", "aucun"))


def controle_et_sauvegarde(reel: ClasseRegard, agent, dossier, lecons, meilleur, journal):
    notes = []
    ctrl = controler(reel, agent)
    lo, hi = reel.instant(TEMOIN_DE), reel.instant(TEMOIN_JUSQUA) - DUREE_PARTIE - 1
    temoin = jouer_comptes(reel, agent, torch.linspace(lo, hi, 24, device=reel.dev).long(), graine=777)
    jouer_comptes(reel, agent, torch.tensor([reel.instant("2021-03-01")], device=reel.dev), graine=1, carnet=notes)
    carnet.ecrire(notes, dossier / "carnet_exemple.txt")
    dire(f"CONTRÔLE 2020-2022 (jamais appris) : {resume(ctrl)}")
    dire(f"témoin 2016-2019 (appris)         : {resume(temoin)}")
    DERNIER["texte"] = resume(ctrl)
    with journal.open("a", encoding="utf-8") as j:
        j.write(json.dumps({"temps": datetime.now().isoformat(timespec="seconds"), "lecon": lecons,
                            "controle": ctrl, "temoin": temoin}, ensure_ascii=False) + "\n")
    torch.save({"cerveau": agent.state_dict(), "lecons": lecons, "meilleur": meilleur}, dossier / "eleve.pt")
    note = ctrl["gain_moyen_pct"] - 0.05 * (ctrl["murs_touches_pct"] + ctrl["inactifs_pct"])
    if meilleur is None or note > meilleur:
        meilleur = note
        torch.save({"cerveau": agent.state_dict(), "lecons": lecons, "controle": ctrl}, dossier / "meilleur.pt")
        dire(f"nouveau meilleur élève au contrôle (note {note:+.3f})")
    return meilleur


if __name__ == "__main__":
    main()
