"""Le CONTRÔLEUR de l'école des mille mondes, dans son propre processus (15/10/2026) : l'école apprend sans
s'interrompre (lancer_mondes --sans-controle) et dépose une copie de l'élève toutes les 10 minutes ; le contrôleur la
juge dès qu'elle change :
- mondes de contrôle FIXES à l'intensité de l'élève (part du gagnable capturée) et à l'intensité réaliste (0,3), avec
  la NOTE du juge (avantage sur le jumeau au hasard, corrigé du nombre d'essais) ;
- le vrai euro-dollar 2020-2022 (jamais appris), avec la note ;
- garde le MEILLEUR élève (avantage sur le hasard dans les mondes réalistes, moins son incertitude) dans meilleur.pt ;
- quand l'élève capture au moins 25 % du gagnable, écrit consigne.json : l'école affaiblit les lois (x 0,8).
Depuis Test_IA : venv_gpu\\Scripts\\python.exe -u -m collapsar.ecole.controleur_mondes
"""
from __future__ import annotations

import json
import math
import time
from datetime import datetime

import torch

from collapsar.cerveau.humain import TraderHumain
from collapsar.ecole.lancer_mondes import (CAPTURE_POUR_AVANCER, DOSSIER, INTENSITE_REELLE, controle_reel, dire,
                                           resume)
from collapsar.ecole.regard import ClasseRegard, donnees_regard
from collapsar.juge.note import phrase
from collapsar.mondes.ecole import ControleMondes

ECART_DEGRADE = 0.3                  # garde-fou : note prudente plus basse que celle du meilleur de 0,3 %/mois
MURS_DEGRADE = 2.0                   # ... ou au moins 2 % des comptes de contrôle au mur


def note_prudente(c: dict) -> float:
    """Avantage sur le hasard MOINS son incertitude, moins une pénalité par mur ou compte inactif (15/10 : garder le
    plus haut de notes bruitées à ± 0,15 couronnait surtout la chance ; un élève ne détrône le meilleur que si sa
    note prudente est plus haute)."""
    n = c["note"]
    return n["avantage_pct_mois"] - n["incertitude_pct_mois"] - 0.05 * (c["murs_touches_pct"] + c["inactifs_pct"])


def main(appareil: str = "cuda" if torch.cuda.is_available() else "cpu", mondes: int = 4, essai: bool = False,
         une_fois: bool = False):
    global DOSSIER
    if essai:
        DOSSIER = DOSSIER.with_name(DOSSIER.name + "_essai")
    ETAT = DOSSIER / "controleur.json"
    copie = DOSSIER / "eleve_a_controler.pt"
    etat = json.loads(ETAT.read_text(encoding="utf-8")) if ETAT.exists() else {"essais": 0, "meilleur": None, "vu": 0}
    reel = ClasseRegard(["EURUSD"], appareil, donnees_regard(["EURUSD"]))
    controles: dict[float, ControleMondes] = {}
    def ctrl(i: float) -> ControleMondes:
        cle = round(i, 4)
        if cle not in controles:
            dire(f"mondes de contrôle à l'intensité {cle} : construction et mesure du gagnable")
            controles[cle] = ControleMondes(cle, appareil, mondes)
        return controles[cle]
    agent = TraderHumain().to(appareil)
    dire("contrôleur prêt : il juge chaque nouvelle copie de l'élève")
    while True:
        if not copie.exists() or copie.stat().st_mtime <= etat["vu"]:
            time.sleep(60)
            continue
        vu = copie.stat().st_mtime
        try:
            e = torch.load(copie, map_location=appareil, weights_only=False)
        except Exception:
            time.sleep(30)                          # copie en cours d'écriture
            continue
        agent.charger(e["cerveau"])
        if etat["meilleur"] is None:
            etat["meilleur"] = e.get("meilleur")             # le meilleur connu de l'école avant le contrôleur
        intensite, lecons = float(e["intensite"]), int(e["lecons"])
        etat["essais"] += 1
        realiste = ctrl(INTENSITE_REELLE).noter(agent, jumeaux=1, essais=etat["essais"])
        courant = realiste if intensite <= INTENSITE_REELLE + 1e-9 else ctrl(intensite).noter(agent)
        vrai = controle_reel(reel, agent, etat["essais"])
        dire(f"leçon {lecons} — mondes jamais vus, intensité {intensite:.2f} : {resume(courant)}")
        dire(f"leçon {lecons} — mondes réalistes (0,3) : {resume(realiste)}")
        dire(f"leçon {lecons} — vrai euro-dollar 2020-2022 : {resume(vrai)}")
        dire(f"NOTE mondes réalistes : {phrase(realiste['note'])}")
        dire(f"NOTE vrai euro-dollar : {phrase(vrai['note'])}")
        with (DOSSIER / "controles.jsonl").open("a", encoding="utf-8") as j:
            j.write(json.dumps({"temps": datetime.now().isoformat(timespec="seconds"), "lecon": lecons,
                                "intensite": intensite, "controle": courant, "controle_realiste": realiste,
                                "vrai_eurusd": vrai}, ensure_ascii=False, default=float) + "\n")
        note = note_prudente(realiste)
        if etat.get("meilleur_prudent") is None and (DOSSIER / "meilleur.pt").exists():
            ancien = torch.load(DOSSIER / "meilleur.pt", map_location="cpu", weights_only=False).get("controle")
            etat["meilleur_prudent"] = note_prudente(ancien) if ancien else None
        if etat.get("meilleur_prudent") is None or note > etat["meilleur_prudent"]:
            etat["meilleur"] = etat["meilleur_prudent"] = note
            torch.save({"cerveau": agent.state_dict(), "lecons": lecons, "intensite": intensite,
                        "controle": realiste, "vrai": vrai}, DOSSIER / "meilleur.pt")
            dire(f"nouveau meilleur élève (avantage sur le hasard dans les mondes réalistes, note prudente {note:+.3f})")
        capture = courant.get("capture_pct", float("nan"))
        # seulement si le gagnable est significatif (15/10 : avec +0,11 %/mois de gagnable, « 491 % capturés »)
        if (not math.isnan(capture) and capture >= CAPTURE_POUR_AVANCER and courant.get("gagnable_pct", 0) >= 0.2
                and intensite > INTENSITE_REELLE + 1e-9):
            nouvelle = max(INTENSITE_REELLE, intensite * 0.8)
            (DOSSIER / "consigne.json").write_text(json.dumps({"intensite": nouvelle}), encoding="utf-8")
            dire(f"elle capture {capture:.0f} % du gagnable : consigne à l'école, intensité {nouvelle:.2f}")
        # 15/10 GARDE-FOU (accord du chef de projet) : deux contrôles d'affilée nettement moins bons que le meilleur
        # élève, ou avec des murs, -> l'école repart du meilleur élève (fichier retour.json, lu par l'école)
        murs = max(realiste["murs_touches_pct"], courant["murs_touches_pct"])
        degrade = (etat.get("meilleur_prudent") is not None and note < etat["meilleur_prudent"] - ECART_DEGRADE) \
            or murs >= MURS_DEGRADE
        etat["degrades"] = etat.get("degrades", 0) + 1 if degrade else 0
        if etat["degrades"] >= 2:
            raison = f"note prudente {note:+.2f} (meilleur {etat['meilleur_prudent']:+.2f}), murs {murs:.0f} %"
            (DOSSIER / "retour.json").write_text(json.dumps({"raison": raison, "temps": datetime.now().isoformat(
                timespec="seconds")}, ensure_ascii=False), encoding="utf-8")
            dire(f"GARDE-FOU : deux contrôles dégradés d'affilée ({raison}) -> l'école repart du meilleur élève")
            etat["degrades"] = 0
        etat["vu"] = vu
        ETAT.write_text(json.dumps(etat), encoding="utf-8")
        if une_fois:
            break


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--essai", action="store_true")
    ap.add_argument("--une-fois", action="store_true")
    ap.add_argument("--mondes", type=int, default=4)
    ap.add_argument("--appareil", default="cuda" if torch.cuda.is_available() else "cpu")
    a = ap.parse_args()
    main(a.appareil, a.mondes, a.essai, a.une_fois)
