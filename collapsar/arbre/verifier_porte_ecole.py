"""Vérification de la porte « observer -> école » (lancée par le cœur, programme à part).

1. calcule son avis avec la cime donnée (tous les marchés) ;
2. joue plusieurs façons de « tenir son avis » sur le simulateur fidèle, sur 2020 -> 2022 (années de l'école,
   jamais l'examen) : 12 marchés variés, challenges de 3 mois, frais FTMO, frais de nuit, fermetures forcées, murs ;
3. si la meilleure gagne (gain > 0 et au moins la moitié des marchés gagnants) : la porte s'ouvre, l'école est
   lancée avec cet avis et cette démonstration, le téléphone est prévenu. Sinon : résultat noté, porte fermée.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime

import torch

from collapsar.arbre import portes
from collapsar.arbre.journal import Journal
from collapsar.cerveau.reseau import Cerveau
from collapsar.donnees import marches as dm
from collapsar.ecole.demonstration import TenirSonAvis
from collapsar.ecole.lancer_avis import APPRENDRE_DE, APPRENDRE_JUSQUA, EXAMEN, lignes_vierges
from collapsar.juge.examen import JugeMarches
from collapsar.surveillance import telephone
from collapsar.yeux.avis import Avis

VIE = portes.VIE
VARIANTES = [("1 h", 1, 0.8), ("1 h", 1, 0.9), ("1 h", 1, 0.95), ("1 h", 1, 0.98), ("4 h", 1, 0.9),
             ("1 jour", 96, 0.8), ("1 semaine", 96, 0.5)]
MESURE_SEULE = "mesure" in sys.argv[2:]


def dire(t):
    print(f"[{datetime.now():%d/%m %H:%M:%S}] {t}", flush=True)


def main():
    cime = sys.argv[1]
    dev = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    etat = portes.lire()
    try:
        cerveau = Cerveau().to(dev)
        cerveau.load_state_dict(torch.load(VIE / "branches" / f"{cime}.pt", map_location=dev,
                                           weights_only=True)["cerveau"])
        donnees = {m: d for m in dm.liste_marches() if len(d := dm.charger(m, jusqua=dm.FIN_EXAMEN)) >= dm.MIN_BOUGIES}
        dire(f"calcul de son avis avec la cime {cime}...")
        fichier = VIE / "avis" / f"avis_{cime}_{datetime.now():%Y%m%d_%H%M}.npz"
        horaires = {m: dm.charger_horaire(m, avant=df["time"].iloc[0], jusqua=dm.FIN_EXAMEN) for m, df in donnees.items()}
        avis = Avis.calculer(cerveau, donnees, dev, source={"cime": cime, "quand": datetime.now().isoformat()},
                             horaires=horaires)
        avis.sauver(fichier)
        del cerveau, donnees
        avis.normaliser({m: lignes_vierges(m) for m in avis.noms})
        marches = [m for m in EXAMEN if m in avis.debut]
        juge = JugeMarches(marches, avis, dev, debut=APPRENDRE_DE, fin=APPRENDRE_JUSQUA)
        lignes = {m: lignes_vierges(m) for m in marches}
        resultats = []
        for h, l, conv in VARIANTES:
            p = TenirSonAvis(avis, marches, h, l, conv, lignes=lignes, risque_jour=0.005)
            r = juge.examiner(p, numero=77, comptes_par_marche=4, jours=90)
            resultats.append({"variante": [h, l, conv], "description": p.description,
                              **{k: v for k, v in r.items() if k != "par_marche"}})
            dire(f"{p.description} : {r['gain_moyen_mois_pct']:+.3f} %/mois, gagnants {r['marches_gagnants_pct']:.0f} %, "
                 f"murs {r['murs_touches_pct']:.0f} %, écart {r['ecart_paye_pct_mois']:.3f} %, nuits "
                 f"{r['nuits_payees_pct_mois']:.3f} %")
        meilleur = max(resultats, key=lambda x: x["gain_moyen_mois_pct"])
        ouverte = meilleur["gain_moyen_mois_pct"] > 0 and meilleur["marches_gagnants_pct"] >= 50
        if MESURE_SEULE:                                   # mesure demandée à la main : on n'ouvre rien
            dire(f"MESURE SEULE : meilleure façon {meilleur['description']} = {meilleur['gain_moyen_mois_pct']:+.3f} "
                 f"%/mois, gagnants {meilleur['marches_gagnants_pct']:.0f} % (la porte n'est pas touchée)")
            (VIE / f"mesure_porte_{cime}.json").write_text(json.dumps(resultats, ensure_ascii=False, indent=1),
                                                           encoding="utf-8")
            return
        etat = portes.lire()
        etat["ecole"]["verifications"].append({"quand": datetime.now().isoformat(timespec="seconds"), "cime": cime,
                                               "niveau": etat["ecole"].get("en_cours", {}).get("niveau"),
                                               "gain_pct_mois": meilleur["gain_moyen_mois_pct"],
                                               "marches_gagnants_pct": meilleur["marches_gagnants_pct"],
                                               "meilleure": meilleur["description"], "ouverte": ouverte,
                                               "avis": fichier.name, "resultats": resultats})
        etat["ecole"].pop("en_cours", None)
        journal = Journal(VIE / "journal_croissance.jsonl")
        if ouverte:
            etat["ecole"]["ouverte"] = True
            etat["ecole"]["demonstration"] = meilleur["variante"]
            etat["ecole"]["avis"] = fichier.name
            portes.ecrire(etat)
            journal.ecrire("porte", porte="école", cime=cime, gain_pct_mois=meilleur["gain_moyen_mois_pct"])
            telephone.envoyer_texte("COLLAPSAR : PORTE DE L'ÉCOLE OUVERTE",
                                    f"La cime {cime} voit assez juste : « {meilleur['description']} » gagne "
                                    f"{meilleur['gain_moyen_mois_pct']:+.2f} %/mois sur 2020-2022 (frais réels). "
                                    "L'école commence.")
            env = dict(os.environ)
            env.pop("CUDA_VISIBLE_DEVICES", None)
            log = VIE / "logs" / f"ecole_{datetime.now():%Y%m%d_%H%M}.txt"
            with open(log, "w", encoding="utf-8") as f:
                subprocess.Popen([sys.executable, "-u", "-m", "collapsar.ecole.lancer_avis", "1440"], cwd=str(dm.RACINE),
                                 stdout=f, stderr=subprocess.STDOUT, env=env,
                                 creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            dire("PORTE OUVERTE : école lancée")
        else:
            portes.ecrire(etat)
            journal.ecrire("porte_fermee", porte="école", cime=cime, gain_pct_mois=meilleur["gain_moyen_mois_pct"],
                           marches_gagnants_pct=meilleur["marches_gagnants_pct"])
            dire(f"porte fermée : meilleure façon {meilleur['description']} = {meilleur['gain_moyen_mois_pct']:+.3f} %/mois")
    except Exception as e:
        etat = portes.lire()
        etat["ecole"].pop("en_cours", None)
        portes.ecrire(etat)
        dire(f"ERREUR pendant la vérification : {type(e).__name__}: {e}")
        raise


if __name__ == "__main__":
    main()
