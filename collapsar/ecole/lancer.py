"""Lance une classe de l'école (essai de la classe 1 : l'euro-dollar).

Elle entre à l'école avec les yeux et le tronc de la CIME DES RACINES (elle sait déjà lire un graphique).
Toutes les 20 leçons : contrôle sur juillet-décembre 2022 (jamais appris), journal, cerveau enregistré.
Depuis Test_IA : venv_gpu\\Scripts\\python.exe -u -m collapsar.ecole.lancer [minutes] [marchés séparés par des virgules]
"""
from __future__ import annotations

import json
import sys
import time
from datetime import datetime

import torch

from collapsar.arbre.jardinier import Arbre
from collapsar.cerveau.agent import Agent
from collapsar.cerveau.reseau import Cerveau
from collapsar.donnees import marches as dm
from collapsar.ecole.classe import Classe, Professeur, controler
from collapsar.donnees.marches import miroir
from collapsar.juge.examen import Juge
from collapsar.mains.fiches import MIROIR

VIE = dm.RACINE / "collapsar" / "vie"


def dire(texte):
    print(f"[{datetime.now():%d/%m %H:%M:%S}] {texte}", flush=True)


def main():
    minutes = float(sys.argv[1]) if len(sys.argv) > 1 else 120
    marches = sys.argv[2].split(",") if len(sys.argv) > 2 else ["EURUSD"]
    dossier = VIE / "ecole" / ("classe1" if marches == ["EURUSD"] else "classe_" + "_".join(marches))
    dossier.mkdir(parents=True, exist_ok=True)
    dev = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    arbre = Arbre.charger(VIE / "arbre.json")
    cerveau = Cerveau()
    contenu = torch.load(VIE / "branches" / f"{arbre.cime}.pt", map_location="cpu", weights_only=True)
    cerveau.load_state_dict(contenu["cerveau"])
    for m in cerveau.modules():
        if isinstance(m, torch.nn.Dropout):
            m.p = 0.0
    agent = Agent(cerveau).to(dev)
    eleve = dossier / "eleve.pt"
    if eleve.exists():
        agent.load_state_dict(torch.load(eleve, map_location=dev, weights_only=True))
        dire("l'élève reprend où il en était")
    else:
        dire(f"entrée à l'école avec les yeux de la cime des racines ({arbre.cime}, {arbre.branches[arbre.cime].score:.2f} %)")
    # la moitié des parties sur le vrai marché, l'autre moitié sur son MIROIR (marché retourné) : une tendance passée
    # ne peut plus être apprise par cœur (« vendre gros a toujours payé ») ; contrôle et examens : vrai marché seul
    classe = Classe(marches, parties=256, appareil=dev)
    donnees_miroir = {m + MIROIR: miroir(dm.charger(m)) for m in marches}
    retournee = Classe([m + MIROIR for m in marches], parties=256, appareil=dev, donnees=donnees_miroir, graine=1)
    prof = Professeur([classe, retournee], agent)
    juge = Juge(marches, appareil=dev)
    meilleure_note = None
    journal = dossier / "journal.jsonl"
    fin = time.time() + minutes * 60
    # la séance en cours, pour le gardien : s'il ne voit plus l'école avant l'heure de fin, il la relance
    seance = VIE / "ecole" / "seance.json"
    seance.write_text(json.dumps({"fin": datetime.fromtimestamp(fin).isoformat(timespec="seconds"),
                                  "marches": ",".join(marches)}), encoding="utf-8")
    lecon = 0
    meilleur = None
    while time.time() < fin:
        t0 = time.time()
        s = prof.jouer()
        b = prof.apprendre()
        lecon += 1
        if lecon % 5 == 0:
            dire(f"  leçon {lecon} ({time.time() - t0:.0f} s) : récompense {s['recompense']:+.2f}, agit {s['agit'] * 100:.0f} %, "
                 f"en position {s['en_position'] * 100:.0f} %, exposition {s['expo']:.1f}x, morts {s['morts']}, "
                 f"réussis {s['reussis']}, danger moyen {s['danger'] * 100:.0f} %, "
                 f"largeur des essais {agent.log_ecart.exp().item():.2f}")
        if lecon % 100 == 0:
            ex = juge.examiner(agent, numero=lecon // 100)
            with open(journal, "a", encoding="utf-8") as f:
                f.write(json.dumps({"heure": datetime.now().isoformat(timespec="seconds"), "lecon": lecon,
                                    "examen": ex}, ensure_ascii=False) + "\n")
            if meilleure_note is None or ex["note"] > meilleure_note:
                meilleure_note = ex["note"]
                torch.save(agent.state_dict(), dossier / "meilleur_examen.pt")
            dire(f"EXAMEN {ex['numero']} ({ex['periode']}) : {ex['gain_moyen_mois_pct']:+.2f} %/mois, "
                 f"réussis {ex['challenges_reussis_pct']:.0f} %, murs {ex['murs_touches_pct']:.0f} %, "
                 f"note {ex['note']:+.0f}, {ex['trades_par_compte']:.0f} trades/compte")
        if lecon % 20 == 1:
            ctrl = controler(classe, agent)
            ligne = {"heure": datetime.now().isoformat(timespec="seconds"), "lecon": lecon, "jeu": s, "apprentissage": b,
                     "controle": ctrl, "secondes_par_lecon": round(time.time() - t0, 1)}
            with open(journal, "a", encoding="utf-8") as f:
                f.write(json.dumps(ligne, ensure_ascii=False) + "\n")
            torch.save(agent.state_dict(), eleve)
            if meilleur is None or ctrl["gain_moyen_mois_pct"] > meilleur:
                meilleur = ctrl["gain_moyen_mois_pct"]
                torch.save(agent.state_dict(), dossier / "meilleur_controle.pt")
            dire(f"leçon {lecon} : contrôle {ctrl['gain_moyen_mois_pct']:+.2f} %/mois, "
                 f"{ctrl['comptes_positifs_pct']:.0f} % de comptes positifs, murs {ctrl['murs_touches_pct']:.0f} %, "
                 f"réussis {ctrl['challenges_reussis_pct']:.0f} %, {ctrl['trades_par_compte']:.0f} trades/compte, "
                 f"en position {ctrl['temps_en_position_pct']:.0f} % | jeu : agit {s['agit'] * 100:.0f} %, "
                 f"exposition {s['expo']:.1f}x, morts {s['morts']}, réussis {s['reussis']}")
    torch.save(agent.state_dict(), eleve)
    seance.unlink(missing_ok=True)
    dire("fin de la séance")


if __name__ == "__main__":
    main()
