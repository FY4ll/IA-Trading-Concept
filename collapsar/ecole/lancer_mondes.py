"""Lance l'ÉCOLE DES MILLE MONDES (validée par le chef de projet le 14/10/2026 au soir).

À chaque leçon, elle joue des centaines de comptes FTMO dans un monde inventé (lois cachées tirées au hasard) ; après
la leçon, ce monde est remplacé par un monde NEUF : elle ne revoit jamais deux fois le même, impossible de réciter.
Progression : les lois commencent fortes (intensité 1, exercices faciles) ; quand elle capture au moins 25 % du
gagnable aux mondes de contrôle, l'intensité baisse (x 0,8) jusqu'au niveau des vrais marchés (0,3).
Toutes les CONTROLE_MINUTES :
- mondes de contrôle FIXES (jamais vus) à l'intensité en cours et à l'intensité réaliste : son gain, le gagnable
  (connaisseur), la part capturée, murs, comportement ;
- le VRAI euro-dollar 2020-2022 (jamais appris) : ce qu'elle a appris dans les mondes sert-il dans la réalité ?
Depuis Test_IA : venv_gpu\\Scripts\\python.exe -u -m collapsar.ecole.lancer_mondes --minutes 600
Arrêt propre : créer collapsar/vie/ecole_mondes/STOP. Reprend où il en était (eleve.pt).
"""
from __future__ import annotations

import argparse
import json
import math
import os
import time
from datetime import datetime

import numpy as np
import psutil
import torch

from collapsar.cerveau.humain import TraderHumain
from collapsar.donnees import marches as dm
from collapsar.ecole.regard import (CONTROLE_DE, CONTROLE_JUSQUA, DUREE_PARTIE, ClasseRegard, ProfesseurRegard,
                                    donnees_regard, jouer_comptes)
from collapsar.juge.note import avantage_sur_hasard, phrase
from collapsar.mondes.ecole import ControleMondes, nouveau_monde
from collapsar.surveillance import telephone

VIE = dm.RACINE / "collapsar" / "vie"
DOSSIER = VIE / "ecole_mondes"
DEPOT_MINUTES = 10                   # --sans-controle : une copie de l'élève pour le contrôleur à part
CONTROLE_MINUTES = 40                # un contrôle dure ~10-15 min : l'école apprend l'essentiel du temps
SEANCE = VIE / "ecole" / "seance.json"   # lue par le gardien : il relance l'école arrêtée avant l'heure
INTENSITE_DEPART, INTENSITE_REELLE = 1.0, 0.3
CAPTURE_POUR_AVANCER = 25.0
MURS_FENETRE, MURS_MAX = 25, 5.0     # garde-fou : plus de 5 murs par leçon (sur 2 048 comptes) en moyenne sur 25 leçons


def dire(texte):
    print(f"[{datetime.now():%d/%m %H:%M:%S}] {texte}", flush=True)


def verrou(dossier):
    f = dossier / "ecole.verrou"
    if f.exists():
        try:
            pid = int(f.read_text())
            if pid != os.getpid() and psutil.pid_exists(pid) and "python" in psutil.Process(pid).name().lower():
                raise SystemExit(f"l'école des mondes tourne déjà (processus {pid})")
        except ValueError:
            pass
    dossier.mkdir(parents=True, exist_ok=True)
    f.write_text(str(os.getpid()))
    return f


def resume(r: dict) -> str:
    capture = r.get("capture_pct", float("nan"))
    texte = f"{r['gain_moyen_pct']:+.2f} %/mois"
    if "gagnable_pct" in r:
        texte += f" (gagnable {r['gagnable_pct']:+.2f}, capturé {capture:.0f} %)" if not math.isnan(capture) \
            else f" (gagnable {r['gagnable_pct']:+.2f})"
    return (texte + f", réussis {r['challenges_reussis_pct']:.0f} %, murs {r['murs_touches_pct']:.0f} %, inactivité "
            f"{r['inactifs_pct']:.0f} %, baisse max {r['baisse_max_moyenne_pct']:.1f} % | regarde "
            f"{r['regards_par_jour']:.1f} fois/jour, {r['trades_par_mois']:.1f} trades/mois, tient "
            f"{r['tenue_mediane_h']:.0f} h, stop {r['avec_stop_pct']:.0f} %, en position {r['temps_en_position_pct']:.0f} %"
            + (f" | en R ({r['trades_en_r']} trades avec stop) : moyenne {r['r_moyen']:+.2f} R, gagnants {r['gagnants_pct']:.0f} %, "
               f"gain moyen {r['gain_moyen_r']:+.2f} R, perte moyenne {r['perte_moyenne_r']:+.2f} R, objectif prévu "
               f"{r['objectif_prevu_r']:.1f} R" if r.get("trades_en_r") else ""))


def controle_reel(reel: ClasseRegard, agent, essais: int, comptes: int = 36) -> dict:
    """Le vrai euro-dollar 2020-2022 (jamais appris) : elle, puis son jumeau au hasard sur les mêmes comptes."""
    lo, hi = reel.instant(CONTROLE_DE), reel.instant(CONTROLE_JUSQUA) - DUREE_PARTIE - 1
    departs = torch.linspace(lo, max(hi, lo + 1), comptes, device=reel.dev).long()
    elle = jouer_comptes(reel, agent, departs, DUREE_PARTIE, graine=12345)
    jumeau = jouer_comptes(reel, agent, departs, DUREE_PARTIE, graine=54321, jumeau=True)
    ecart = float((hi - lo) / max(comptes - 1, 1))
    elle["note"] = avantage_sur_hasard(elle, [jumeau], essais, DUREE_PARTIE, ecart)
    return elle


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--minutes", type=float, default=600)
    ap.add_argument("--parties", type=int, default=512)
    ap.add_argument("--pas", type=int, default=512)
    ap.add_argument("--reserve", type=int, default=6, help="mondes en jeu à la fois (un est remplacé à chaque leçon)")
    ap.add_argument("--appareil", default="cuda" if torch.cuda.is_available() else "cpu")
    ap.add_argument("--essai", action="store_true")
    ap.add_argument("--controle-mondes", type=int, default=4)
    ap.add_argument("--sans-controle", action="store_true",
                    help="15/10 : l'école ne s'arrête plus pour se contrôler ; elle dépose une copie de l'élève toutes les "
                         "10 min pour le contrôleur à part (ecole/controleur_mondes.py), qui lui renvoie l'intensité")
    ap.add_argument("--depart", default=None,
                    help="15/10 : repartir d'un élève sauvé (ex. meilleur.pt) au lieu du dernier élève (eleve.pt)")
    args = ap.parse_args()
    dossier = DOSSIER.with_name(DOSSIER.name + "_essai") if args.essai else DOSSIER
    f_verrou = verrou(dossier)
    stop = dossier / "STOP"
    dev = args.appareil
    agent = TraderHumain().to(dev)
    fichier = dossier / "eleve.pt"
    lecons, intensite, meilleur, mondes_vus, essais = 0, INTENSITE_DEPART, None, 0, 0
    if fichier.exists():
        etat = torch.load(fichier, map_location=dev, weights_only=False)
        agent.charger(etat["cerveau"])
        lecons, intensite = etat["lecons"], etat["intensite"]
        meilleur, mondes_vus, essais = etat.get("meilleur"), etat.get("mondes_vus", 0), etat.get("essais", 0)
        dire(f"reprise : {lecons} leçons, {mondes_vus} mondes vécus, intensité {intensite:.2f}")
    if args.depart:
        # 15/10 : repartir d'un élève sain (l'élève de la matinée était devenu joueur) ; l'ancien est gardé à côté
        if fichier.exists():
            torch.save(torch.load(fichier, map_location="cpu", weights_only=False),
                       dossier / f"eleve_avant_depart_{datetime.now():%Y%m%d_%H%M}.pt")
        depart = torch.load(args.depart, map_location=dev, weights_only=False)
        agent.charger(depart["cerveau"])
        lecons, intensite = depart.get("lecons", lecons), depart.get("intensite", intensite)
        (dossier / "consigne.json").write_text(json.dumps({"intensite": intensite}), encoding="utf-8")
        dire(f"départ depuis {args.depart} : leçon {lecons}, intensité {intensite:.2f}")
    rng = np.random.default_rng(1000 + lecons)
    reserve = [nouveau_monde(rng, intensite, dev) for _ in range(args.reserve)]
    mondes_vus += len(reserve)
    debut, fin_monde = reserve[0].h.temps[0], reserve[0].h.temps[-1]
    prof = ProfesseurRegard(reserve, agent, parties=args.parties, pas=args.pas, graine=lecons, de=debut,
                            jusqua=fin_monde)
    if not args.sans_controle:
        reel = ClasseRegard(["EURUSD"], dev, donnees_regard(["EURUSD"]))
        dire("mondes de contrôle : construction et mesure du gagnable (une seule fois)")
        ctrl_realiste = ControleMondes(INTENSITE_REELLE, dev, args.controle_mondes)
        ctrl_courant = (ctrl_realiste if intensite <= INTENSITE_REELLE + 1e-9
                        else ControleMondes(intensite, dev, args.controle_mondes))
    prochain_depot = time.time() + DEPOT_MINUTES * 60
    murs_recents: list[int] = []
    n_param = sum(p.numel() for p in agent.parameters())
    dire(f"école des mille mondes : {args.reserve} mondes en jeu, {args.parties} comptes, cerveau "
         f"{n_param:,} connexions, intensité {intensite:.2f}".replace(",", " "))
    if not args.essai and 8 <= datetime.now().hour < 23:   # heures calmes : pas de message la nuit
        telephone.envoyer_texte("COLLAPSAR — école des mille mondes lancée",
                                f"{args.minutes:.0f} min. Un monde neuf à chaque leçon ; contrôle toutes les "
                                f"{CONTROLE_MINUTES} min (mondes jamais vus + vrai euro-dollar 2020-2022).")
    journal = dossier / "journal.jsonl"
    fin = time.time() + args.minutes * 60
    if not args.essai:
        SEANCE.parent.mkdir(parents=True, exist_ok=True)
        SEANCE.write_text(json.dumps({"fin": datetime.fromtimestamp(fin).isoformat(timespec="seconds"),
                                      "lanceur": "collapsar.ecole.lancer_mondes",
                                      "arguments": ["--parties", str(args.parties), "--pas", str(args.pas),
                                                    "--reserve", str(args.reserve),
                                                    "--controle-mondes", str(args.controle_mondes)]
                                                   + (["--sans-controle"] if args.sans_controle else [])}),
                          encoding="utf-8")
    fini = False
    prochain_controle = time.time() + CONTROLE_MINUTES * 60
    dernier = "aucun contrôle"
    try:
        while time.time() < fin and not stop.exists():
            t0 = time.time()
            jeu = prof.jouer()
            appris = prof.apprendre()
            lecons += 1
            k = prof.k
            m = prof.mondes[k]
            jeu["regimes"] = {n: round(float((m.regime == i).float().mean()), 2)
                              for i, n in enumerate(("rien", "tendance", "retour"))}
            dire(f"leçon {lecons} (monde à {m.h.M} marché(s), intensité {intensite:.2f}) : regarde "
                 f"{jeu['regards_par_jour']:.1f} fois/jour, garde {jeu['garder_pct']:.0f} % / protège "
                 f"{jeu['proteger_pct']:.0f} % / change {jeu['changer_pct']:.0f} % / ordre à l'avance {jeu.get('attendre_pct', 0):.0f} % (risque "
                 f"{jeu['risque_moyen_pct']:.2f} %), en position {jeu['en_position_pct']:.0f} %, murs {jeu['morts']} "
                 f"(inactivité {jeu['inactifs']}), réussis {jeu['reussis']}, récompense/jour "
                 f"{jeu['recompense_par_jour']:+.3f} ({time.time() - t0:.0f} s)")
            # le monde qu'elle vient de jouer est remplacé par un monde neuf
            prof.installer(k, nouveau_monde(rng, intensite, dev), debut, fin_monde)
            mondes_vus += 1
            murs_recents = (murs_recents + [jeu["morts"]])[-MURS_FENETRE:]
            with journal.open("a", encoding="utf-8") as j:
                j.write(json.dumps({"temps": datetime.now().isoformat(timespec="seconds"), "lecon": lecons,
                                    "intensite": intensite, **jeu, **appris}, ensure_ascii=False) + "\n")
            if args.sans_controle and (time.time() >= prochain_depot or time.time() >= fin or stop.exists()):
                prochain_depot = time.time() + DEPOT_MINUTES * 60
                copie = {"cerveau": agent.state_dict(), "lecons": lecons, "intensite": intensite,
                         "meilleur": meilleur, "mondes_vus": mondes_vus, "essais": essais}
                torch.save(copie, fichier)
                torch.save(copie, dossier / "eleve_a_controler.pt")
                # 15/10 GARDE-FOU (accord du chef de projet) : le contrôleur a vu deux contrôles dégradés, ou trop de
                # murs dans ses dernières leçons -> elle repart du meilleur élève (sa mémoire d'apprentissage est vidée)
                retour = dossier / "retour.json"
                trop_de_murs = len(murs_recents) >= MURS_FENETRE and np.mean(murs_recents) > MURS_MAX
                if (retour.exists() or trop_de_murs) and (dossier / "meilleur.pt").exists():
                    raison = (json.loads(retour.read_text(encoding="utf-8-sig")).get("raison", "") if retour.exists()
                              else f"{np.mean(murs_recents):.1f} murs par leçon en moyenne sur {MURS_FENETRE} leçons")
                    m = torch.load(dossier / "meilleur.pt", map_location=dev, weights_only=False)
                    agent.charger(m["cerveau"])
                    prof.opt.state.clear()
                    intensite = float(m.get("intensite", intensite))
                    (dossier / "consigne.json").write_text(json.dumps({"intensite": intensite}), encoding="utf-8")
                    retour.unlink(missing_ok=True)
                    murs_recents = []
                    dire(f"GARDE-FOU : retour au meilleur élève (leçon {m.get('lecons')}, intensité {intensite:.2f}) : {raison}")
                    if not args.essai and 8 <= datetime.now().hour < 23:
                        telephone.envoyer_texte("COLLAPSAR — garde-fou de l'école",
                                                f"L'élève dérivait ({raison}) : l'école repart du meilleur élève.")
                consigne = dossier / "consigne.json"
                if consigne.exists():
                    nouvelle = float(json.loads(consigne.read_text(encoding="utf-8")).get("intensite", intensite))
                    if nouvelle < intensite - 1e-9:
                        intensite = nouvelle
                        dire(f"le contrôleur affaiblit les lois des mondes : intensité {intensite:.2f}")
            if not args.sans_controle and (time.time() >= prochain_controle or time.time() >= fin or stop.exists()):
                prochain_controle = time.time() + CONTROLE_MINUTES * 60
                essais += 1                         # chaque contrôle sert à choisir le meilleur : un essai
                if ctrl_courant is ctrl_realiste:
                    ctrl = ctrl_reel_monde = ctrl_realiste.noter(agent, jumeaux=1, essais=essais)
                else:
                    ctrl = ctrl_courant.noter(agent)
                    ctrl_reel_monde = ctrl_realiste.noter(agent, jumeaux=1, essais=essais)
                vrai = controle_reel(reel, agent, essais)
                dire(f"CONTRÔLE mondes jamais vus, intensité {intensite:.2f} : {resume(ctrl)}")
                dire(f"CONTRÔLE mondes réalistes (0,3)          : {resume(ctrl_reel_monde)}")
                dire(f"CONTRÔLE vrai euro-dollar 2020-2022      : {resume(vrai)}")
                dire(f"NOTE mondes réalistes : {phrase(ctrl_reel_monde['note'])}")
                dire(f"NOTE vrai euro-dollar : {phrase(vrai['note'])}")
                dernier = (f"mondes réalistes : avantage sur le hasard {ctrl_reel_monde['note']['avantage_pct_mois']:+.2f} "
                           f"%/mois ; vrai euro-dollar 2020-2022 : {vrai['gain_moyen_pct']:+.2f} %/mois (avantage "
                           f"{vrai['note']['avantage_pct_mois']:+.2f}), murs {vrai['murs_touches_pct']:.0f} %")
                with journal.open("a", encoding="utf-8") as j:
                    j.write(json.dumps({"temps": datetime.now().isoformat(timespec="seconds"), "lecon": lecons,
                                        "controle": ctrl, "controle_realiste": ctrl_reel_monde, "vrai_eurusd": vrai},
                                       ensure_ascii=False) + "\n")
                # le meilleur élève : son avantage SUR LE HASARD dans les mondes réalistes (pas son gain brut)
                note = ctrl_reel_monde["note"]["avantage_pct_mois"] - 0.05 * (ctrl_reel_monde["murs_touches_pct"]
                                                                               + ctrl_reel_monde["inactifs_pct"])
                if meilleur is None or note > meilleur:
                    meilleur = note
                    torch.save({"cerveau": agent.state_dict(), "lecons": lecons, "intensite": intensite,
                                "controle": ctrl_reel_monde, "vrai": vrai}, dossier / "meilleur.pt")
                    dire(f"nouveau meilleur élève (mondes réalistes, note {note:+.3f})")
                capture = ctrl.get("capture_pct", float("nan"))
                if (not math.isnan(capture) and capture >= CAPTURE_POUR_AVANCER
                        and intensite > INTENSITE_REELLE + 1e-9):
                    intensite = max(INTENSITE_REELLE, intensite * 0.8)
                    ctrl_courant = (ctrl_realiste if intensite <= INTENSITE_REELLE + 1e-9
                                    else ControleMondes(intensite, dev, args.controle_mondes))
                    dire(f"elle capture {capture:.0f} % du gagnable : les lois s'affaiblissent (intensité "
                         f"{intensite:.2f})")
                torch.save({"cerveau": agent.state_dict(), "lecons": lecons, "intensite": intensite,
                            "meilleur": meilleur, "mondes_vus": mondes_vus, "essais": essais}, fichier)
        fini = True
    finally:
        if fini and not args.essai:
            SEANCE.unlink(missing_ok=True)              # fin normale (heure ou STOP) : le gardien ne relance pas
        torch.save({"cerveau": agent.state_dict(), "lecons": lecons, "intensite": intensite, "meilleur": meilleur,
                    "mondes_vus": mondes_vus, "essais": essais}, fichier)
        f_verrou.unlink(missing_ok=True)
        dire(f"école arrêtée après {lecons} leçons ({mondes_vus} mondes vécus) ; élève sauvé dans {fichier}")
        if not args.essai and 8 <= datetime.now().hour < 23:   # heures calmes : pas de message la nuit
            telephone.envoyer_texte(f"COLLAPSAR — école des mille mondes arrêtée ({lecons} leçons, "
                                    f"{mondes_vus} mondes)", f"Intensité {intensite:.2f}. Dernier contrôle : {dernier}")


if __name__ == "__main__":
    main()
