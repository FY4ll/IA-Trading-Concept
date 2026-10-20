"""Grand examen (14/10/2026) : 192 challenges de 3 mois au lieu de 24 (le petit examen bougeait de ±0,3 %/mois tout
seul : même cerveau, mêmes dates, +0,29 puis -0,09 %/mois). Compte unique sur les 12 marchés, 2023 -> 09/2025.
Depuis Test_IA : venv_gpu\\Scripts\\python.exe -u -m collapsar.juge.grand_examen
"""
from __future__ import annotations

import json
from datetime import datetime

import torch

from collapsar.cerveau.agent import AgentAvis
from collapsar.donnees import marches as dm
from collapsar.ecole.demonstration import TenirSonAvis
from collapsar.ecole.lancer_avis import EXAMEN, avis_normalise, lignes_vierges
from collapsar.juge.examen import JugeMarches

VIE = dm.RACINE / "collapsar" / "vie"
ECOLE = VIE / "ecole"


def main():
    dev = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    avis = avis_normalise(dev)
    marches = [m for m in EXAMEN if m in avis.debut]
    juge = JugeMarches(marches, avis, dev)
    lignes = {m: lignes_vierges(m) for m in marches}
    candidats = {
        "démonstration (risque 0,25 %)": TenirSonAvis(avis, marches, "1 h", 1, 0.9, lignes=lignes, risque_jour=0.0025),
    }
    # 14/10 matin : fin de la séance A3 (300 min) -> son meilleur au petit examen (leçon 900) et sa version finale
    for nom, f in (("A3 meilleur au petit examen", ECOLE / "par_avis" / "meilleur_examen.pt"),
                   ("A3 fin de séance", ECOLE / "par_avis" / "eleve.pt")):
        if f.exists():
            a = AgentAvis(n_avis=avis.table.shape[1]).to(dev)
            a.load_state_dict(torch.load(f, map_location=dev, weights_only=True))
            candidats[nom] = a
    res = {}
    for nom, c in candidats.items():
        r = juge.examiner_compte_unique(c, numero=4242, comptes=192, jours=90)
        res[nom] = r
        print(f"[{datetime.now():%H:%M}] {nom:32s} | {r['gain_moyen_mois_pct']:+.2f} %/mois (médiane "
              f"{r['gain_median_mois_pct']:+.2f}) | positifs {r['comptes_positifs_pct']:.0f} % | réussis "
              f"{r['challenges_reussis_pct']:.0f} % | murs {r['murs_touches_pct']:.0f} % | baisse max "
              f"{r['baisse_max_moyenne_pct']:.1f} % (pire {r['pire_baisse_pct']:.1f} %) | {r['trades_par_mois']:.0f} trades/mois",
              flush=True)
    (VIE / f"grand_examen_{datetime.now():%Y%m%d_%H%M}.json").write_text(json.dumps(res, ensure_ascii=False, indent=1),
                                                                         encoding="utf-8")


if __name__ == "__main__":
    main()
