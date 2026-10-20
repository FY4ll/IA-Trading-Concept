"""L'école par AVIS (13/10/2026) : la version qui corrige la cause du casino et de la paralysie.

1. Son avis (yeux/avis.py) est calculé une fois avec la cime des racines, sur tous les marchés.
2. Elle s'entraîne UNIQUEMENT sur des années que les racines n'ont jamais vues (2010 -> 2017), sur chaque marché qui
   a cet historique (l'or en est exclu : ses racines l'ont appris depuis 2004). Sur ces années, son avis a sa vraie
   justesse (~52 %), comme en réel — avant, ses yeux « connaissaient l'avenir » à l'entraînement (97-99 %).
3. Un compte par partie, un marché par partie ; parties d'un mois ; peur du mur ; curiosité minimum.
4. Contrôle : 2e moitié 2022. Examen toutes les 100 leçons : 12 marchés variés, 2023 -> 09/2025, jamais appris.
Depuis Test_IA : venv_gpu\\Scripts\\python.exe -u -m collapsar.ecole.lancer_avis [minutes]
"""
from __future__ import annotations

import copy
import json
import os
import sys
import time
from datetime import datetime

import numpy as np
import pandas as pd
import torch

from collapsar.arbre import portes
from collapsar.arbre.jardinier import Arbre
from collapsar.cerveau.agent import AgentAvis
from collapsar.cerveau.reseau import Cerveau
from collapsar.donnees import marches as dm
from collapsar.ecole.classe import Classe, Professeur, donnees_classe
from collapsar.ecole import classe as classe_ecole
from collapsar.ecole.demonstration import TenirSonAvis
from collapsar.ecole.imitation import Imitateur
from collapsar.juge.examen import JugeMarches
from collapsar.yeux.avis import Avis

VIE = dm.RACINE / "collapsar" / "vie"
DOSSIER = VIE / "ecole" / "par_avis"
APPRENDRE_DE = pd.Timestamp("2020-02-05")            # 13/10 après-midi : les racines apprennent 2010-2019
APPRENDRE_JUSQUA = pd.Timestamp("2023-01-01")          # -> l'école apprend sur 2020-2022, jamais appris des racines
HISTORIQUE_MIN = pd.Timestamp("2014-01-01")            # un marché d'école doit avoir des données avant cette date
DEMONSTRATION = ("1 h", 1, 0.9)                      # horizon, lissage, conviction (test d'argent 2020-2022 du 13/10 : la meilleure)
RISQUE_JOUR = 0.0025                                  # taille de la démonstration : ~0,25 % du compte par jour et par marché (compte unique multi-marchés : 0,5 % donnait 25-42 % de murs)
LECONS_IMITATION = 150
ECHAUFFEMENT = 20                                    # leçons où seules ses horloges apprennent
LAISSE = 1.0                                          # 0,3 : il repartait vers le casino (murs 25 -> 62 %)
EXAMEN = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "EURJPY", "GBPCHF", "USA500IDXUSD", "DEUIDXEUR", "XAUUSD",
          "XAGUSD", "LIGHTCMDUSD", "BTCUSD"]


def dire(texte):
    print(f"[{datetime.now():%d/%m %H:%M:%S}] {texte}", flush=True)


def avis_de_la_cime(dev) -> Avis:
    porte = (portes.lire().get("ecole") or {})
    if porte.get("avis") and (VIE / "avis" / porte["avis"]).exists():
        dire(f"avis de la porte de l'école : {porte['avis']}")       # celui qui a fait ouvrir la porte
        return Avis.charger(VIE / "avis" / porte["avis"], dev)
    arbre = Arbre.charger(VIE / "arbre.json")
    b = arbre.branches[arbre.cime]
    existants = sorted((VIE / "avis").glob("avis_*.npz"), key=lambda f: f.stat().st_mtime)
    if existants and not os.environ.get("COLLAPSAR_NOUVEL_AVIS"):
        # l'école garde un avis FIXE (le plus récent) : les cimes se valent à 0,1 point près, et le recalculer prend
        # 8 minutes ; pour en refaire un avec la cime du moment : COLLAPSAR_NOUVEL_AVIS=1
        dire(f"avis gardé : {existants[-1].name}")
        return Avis.charger(existants[-1], dev)
    fichier = VIE / "avis" / f"avis_{arbre.cime}.npz"
    cerveau = Cerveau().to(dev)
    cerveau.load_state_dict(torch.load(VIE / "branches" / f"{arbre.cime}.pt", map_location=dev,
                                       weights_only=True)["cerveau"])
    donnees = {m: d for m in dm.liste_marches() if len(d := dm.charger(m, jusqua=dm.FIN_EXAMEN)) >= dm.MIN_BOUGIES}
    dire(f"calcul de son avis avec la cime {arbre.cime} ({b.score:.2f} %) sur {len(donnees)} marchés...")
    horaires = {m: dm.charger_horaire(m, avant=df["time"].iloc[0], jusqua=dm.FIN_EXAMEN) for m, df in donnees.items()}
    avis = Avis.calculer(cerveau, donnees, dev, source={"cime": arbre.cime, "niveau": b.score, "notes": len(b.scores),
                                                       "quand": datetime.now().isoformat(timespec="seconds")},
                         horaires=horaires)
    avis.sauver(fichier)
    dire(f"avis calculé et enregistré ({avis.table.shape[0]:,} bougies)".replace(",", " "))
    return avis


def lignes_vierges(m: str) -> np.ndarray:
    """Les bougies du marché jamais apprises par les racines et hors examen : 2020 -> 2022."""
    t = dm.charger(m)["time"]
    return np.flatnonzero(((t >= APPRENDRE_DE) & (t < APPRENDRE_JUSQUA)).to_numpy())


def avis_normalise(dev) -> Avis:
    avis = avis_de_la_cime(dev)
    return avis.normaliser({m: lignes_vierges(m) for m in avis.noms})


ECOLE = EXAMEN + ["USDCAD", "NZDUSD", "EURGBP", "USA30IDXUSD"]       # 16 marchés variés (devises, indices, métaux...)


def marches_d_ecole() -> list[str]:
    """Les marchés de l'école : 16 marchés variés, sur 2020-2022 (années jamais apprises des racines)."""
    return [m for m in ECOLE if (dm.charger(m)["time"] >= APPRENDRE_DE).sum() > 20_000]


def main():
    minutes = float(sys.argv[1]) if len(sys.argv) > 1 else 600
    # mode « seul » (élève B, 13/10) : AUCUNE imitation, il découvre par la récompense seule (vision d'origine) ;
    # mode « imite » (élève A, par défaut) : imitation de la démonstration, puis récompense en laisse
    seul = len(sys.argv) > 2 and sys.argv[2] == "seul"
    global DOSSIER
    DOSSIER = VIE / "ecole" / ("seul" if seul else "par_avis")
    DOSSIER.mkdir(parents=True, exist_ok=True)
    dire(f"élève {'B : découverte seule, sans imitation' if seul else 'A : imitation puis récompense en laisse'}")
    dev = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    avis = avis_normalise(dev)
    ecole = marches_d_ecole()
    dire(f"marchés d'école (2020-2022, jamais appris des racines) : {', '.join(ecole)}")
    # UN SEUL COMPTE pour tous les marchés de l'école (13/10 soir, accord du chef de projet) : les petits avantages
    # de chaque marché s'additionnent dans le même compte, les risques beaucoup moins ; elle voit tout son compte
    mondes = [Classe(ecole, parties=256, appareil=dev, donnees=donnees_classe(ecole), avis=avis, graine=0,
                     apprendre_de=APPRENDRE_DE, apprendre_jusqua=APPRENDRE_JUSQUA)]
    agent = AgentAvis(n_avis=avis.table.shape[1]).to(dev)
    juge = JugeMarches([m for m in EXAMEN if m in avis.debut], avis, dev)
    journal = DOSSIER / "journal.jsonl"
    seance = VIE / "ecole" / "seance.json"
    fin = time.time() + minutes * 60
    if not seul:                                       # le gardien relance l'élève A s'il s'arrête avant l'heure
        seance.write_text(json.dumps({"fin": datetime.fromtimestamp(fin).isoformat(timespec="seconds"),
                                      "lanceur": "collapsar.ecole.lancer_avis"}), encoding="utf-8")

    def noter(etape, lecon, a):
        """Examen d'un VRAI compte FTMO : un compte de 100 000 $ qui trade les 12 marchés de l'examen en même temps,
        24 challenges de 3 mois à des dates tirées au hasard sur 2023 -> 09/2025 (jamais vu)."""
        ex = juge.examiner_compte_unique(a, numero=lecon // 100 + (0 if etape == "imitation" else 1000))
        with open(journal, "a", encoding="utf-8") as f:
            f.write(json.dumps({"heure": datetime.now().isoformat(timespec="seconds"), "etape": etape, "lecon": lecon,
                                "examen": ex}, ensure_ascii=False) + "\n")
        dire(f"EXAMEN {etape} leçon {lecon} (compte unique, {ex['marches']} marchés, 2023-2025) : "
             f"{ex['gain_moyen_mois_pct']:+.2f} %/mois (médiane {ex['gain_median_mois_pct']:+.2f}), comptes positifs "
             f"{ex['comptes_positifs_pct']:.0f} %, challenges réussis {ex['challenges_reussis_pct']:.0f} %, murs "
             f"{ex['murs_touches_pct']:.0f} %, baisse max moyenne {ex['baisse_max_moyenne_pct']:.1f} % (pire "
             f"{ex['pire_baisse_pct']:.1f} %), {ex['trades_par_mois']:.0f} trades/mois")
        return ex["gain_moyen_mois_pct"] - 0.05 * ex["murs_touches_pct"]

    # 1. IMITER la démonstration (« tenir son avis ») sur les années vierges
    imite = DOSSIER / "imite.pt"
    note_imitation = None
    if seul:
        dire("pas d'imitation : il part de zéro")
    elif imite.exists():
        agent.load_state_dict(torch.load(imite, map_location=dev, weights_only=True))
        dire("imitation déjà faite : reprise")
    else:
        demo = tuple((portes.lire().get("ecole") or {}).get("demonstration") or DEMONSTRATION)
        dire(f"démonstration à imiter : {demo}")
        maitre = TenirSonAvis(avis, sorted(set(ecole) | {m for m in EXAMEN if m in avis.debut}), *demo,
                              lignes={m: lignes_vierges(m) for m in avis.noms}, risque_jour=RISQUE_JOUR)
        noter("démonstration seule", 0, maitre)
        imit = Imitateur(mondes, agent, maitre)
        for lecon in range(1, LECONS_IMITATION + 1):
            s = imit.regarder_le_maitre()
            b = imit.apprendre()
            if lecon % 10 == 0:
                dire(f"  imitation {lecon} : le maître agit {s['agit_maitre'] * 100:.2f} % des bougies ; l'élève agit "
                     f"{b['rappel'] * 100:.0f} % du temps quand il faut, {b['fausses'] * 100:.2f} % quand il ne faut pas, "
                     f"écart de taille {b['combien']:.4f}")
        torch.save(agent.state_dict(), imite)
        note_imitation = noter("imitation", LECONS_IMITATION, agent)
        torch.save(agent.state_dict(), DOSSIER / "meilleur_examen.pt")    # la référence à battre par la récompense

    # 2. S'AMÉLIORER par la récompense, en laisse (elle ne peut pas trop s'éloigner de ce qu'elle a imité)
    if not seul:
        # 14/10 : sur un compte de 16 marchés, le hasard d'essai réglé pour UN marché créait sans cesse des positions
        # énormes (~200 murs par leçon à l'entraînement). Après l'imitation, il essaie par PETITES touches autour de
        # ce qu'il sait faire : largeur des essais ~0,08 (au lieu de 0,37) et curiosité minimum 0,2 % par marché.
        with torch.no_grad():
            agent.log_ecart.fill_(-2.5)
        classe_ecole.CURIOSITE_MIN = 0.002
        if note_imitation is None and imite.exists():
            note_imitation = noter("imitation (reprise)", LECONS_IMITATION, agent)
    reference = None if seul else copy.deepcopy(agent)
    eleve = DOSSIER / "eleve.pt"
    if eleve.exists():
        agent.load_state_dict(torch.load(eleve, map_location=dev, weights_only=True))
        dire("l'élève reprend où il en était")
    prof = Professeur(mondes, agent, reference=reference, laisse=0.0 if seul else LAISSE,
                      curiosite=0.01 if seul else 0.003)
    meilleure = note_imitation                         # la récompense doit faire MIEUX que l'imitation pour compter
    lecon = 0
    while time.time() < fin:
        t0 = time.time()
        s = prof.jouer()
        b = prof.echauffer() if lecon < ECHAUFFEMENT else prof.apprendre()
        lecon += 1
        if lecon % 10 == 0:
            dire(f"  leçon {lecon}{' (échauffement)' if lecon <= ECHAUFFEMENT else ''} ({time.time() - t0:.0f} s) : "
                 f"récompense {s['recompense']:+.2f}, agit {s['agit'] * 100:.1f} %, en position "
                 f"{s['en_position'] * 100:.0f} %, exposition {s['expo']:.2f}x, morts {s['morts']}, réussis {s['reussis']}, "
                 f"danger {s['danger'] * 100:.0f} %")
        if lecon % 20 == 0:
            torch.save(agent.state_dict(), eleve)
        if lecon % 100 == 0:
            cle = noter("récompense", lecon, agent)
            if meilleure is None or cle > meilleure:
                meilleure = cle
                torch.save(agent.state_dict(), DOSSIER / "meilleur_examen.pt")
                dire("  -> meilleur élève à l'examen, enregistré")
    torch.save(agent.state_dict(), eleve)
    seance.unlink(missing_ok=True)
    dire("fin de la séance")


if __name__ == "__main__":
    main()
