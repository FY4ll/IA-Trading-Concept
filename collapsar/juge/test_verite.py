"""Test de vérité : ce que voient les racines rapporte-t-il de l'argent, frais compris ?

On prend directement la prédiction de sens de la cime des racines (« ça monte » / « ça baisse ») sur une période
JAMAIS APPRISE et on mesure ce qu'aurait rapporté une position de 1 x le compte dans ce sens, frais réels compris.
Ce n'est pas une stratégie à garder : c'est la mesure du plafond. Si même ça perd, aucune école ne peut gagner avec
ces yeux ; si ça gagne, l'avantage existe et l'école doit apprendre à s'en servir.

Depuis Test_IA : venv_gpu\\Scripts\\python.exe -m collapsar.juge.test_verite [début] [fin]
(par défaut 2023-01-01 -> 2025-09-30 ; jamais les mois cachés)
"""
from __future__ import annotations

import json
import sys
from datetime import datetime

import numpy as np
import pandas as pd
import torch

from collapsar.arbre.jardinier import Arbre
from collapsar.cerveau.reseau import Cerveau
from collapsar.donnees import marches as dm
from collapsar.mains.fiches import fiche
from collapsar.regarder.exercices import HORIZONS
from collapsar.yeux.graphique import Graphique

VIE = dm.RACINE / "collapsar" / "vie"
SEUILS = (0.0, 0.5, 0.8, 0.9)          # 0 = toujours en position ; 0,9 = seulement ses 10 % de cas les plus sûrs


@torch.no_grad()
def predictions(cerveau, g: Graphique, idx: np.ndarray, lot=4096) -> np.ndarray:
    sorties = []
    for d in range(0, len(idx), lot):
        f, x = g.voir(torch.from_numpy(idx[d:d + lot]))
        sorties.append(cerveau(f, x)[0].float().cpu().numpy())
    return np.concatenate(sorties) if sorties else np.zeros((0, len(HORIZONS)))


def main():
    debut = pd.Timestamp(sys.argv[1]) if len(sys.argv) > 1 else pd.Timestamp("2023-01-01")
    fin = min(pd.Timestamp(sys.argv[2]) if len(sys.argv) > 2 else dm.FIN_EXAMEN, dm.FIN_EXAMEN)
    dev = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    arbre = Arbre.charger(VIE / "arbre.json")
    cerveau = Cerveau().to(dev)
    cerveau.load_state_dict(torch.load(VIE / "branches" / f"{arbre.cime}.pt", map_location=dev,
                                       weights_only=True)["cerveau"])
    cerveau.eval()
    donnees = {}
    for m in dm.liste_marches():
        df = dm.charger(m, jusqua=fin)
        if len(df) >= dm.MIN_BOUGIES and (df["time"] >= debut).sum() > 2000:
            donnees[m] = df
    g = Graphique(donnees, dev)
    res, lignes = {}, []
    for j, (m, df) in enumerate(donnees.items()):
        a = g.debut_marche[j]
        t = df["time"].values
        loc = np.flatnonzero((t >= debut.to_datetime64()) & (t < fin.to_datetime64()))[:-1]
        if len(loc) < 1000:
            continue
        logits = predictions(cerveau, g, a + loc)
        c = df["close"].to_numpy()
        r = np.log(c[loc + 1] / c[loc])                     # décision à la clôture, tenue pendant la bougie suivante
        frais = fiche(m).frais / 2                          # chaque changement de sens paie un demi-trade par unité
        mois = (t[loc[-1]] - t[loc[0]]) / np.timedelta64(30, "D")
        for h, nom_h in enumerate(HORIZONS):
            lg = logits[:, h]
            for s in SEUILS:
                seuil = np.quantile(np.abs(lg), s) if s > 0 else 0.0
                pos = np.where(np.abs(lg) >= seuil, np.sign(lg), 0.0)
                tourne = np.abs(np.diff(np.r_[0.0, pos]))
                brut = (pos * r).sum()
                net = brut - (tourne * frais).sum()
                cle = (nom_h, s)
                res.setdefault(cle, []).append({"marche": m, "brut_mois": brut / mois * 100, "net_mois": net / mois * 100,
                                                "en_position": float((pos != 0).mean() * 100),
                                                "changements_par_jour": float(tourne.sum() / mois / 21)})
    tableau = []
    for (h, s), lst in res.items():
        net = np.array([x["net_mois"] for x in lst])
        brut = np.array([x["brut_mois"] for x in lst])
        tableau.append({"horizon": h, "seulement_les_plus_surs": f"{int((1 - s) * 100)} %",
                        "brut_pct_mois_moyen": float(brut.mean()), "net_pct_mois_moyen": float(net.mean()),
                        "marches_gagnants_net_pct": float((net > 0).mean() * 100),
                        "en_position_pct": float(np.mean([x["en_position"] for x in lst])),
                        "changements_par_jour": float(np.mean([x["changements_par_jour"] for x in lst])),
                        "marches": len(lst)})
    rapport = {"quand": datetime.now().isoformat(timespec="seconds"), "cime": arbre.cime,
               "periode": f"{debut:%Y-%m-%d} -> {fin:%Y-%m-%d}", "resultats": tableau,
               "par_marche": {f"{h}|{s}": lst for (h, s), lst in res.items()}}
    sortie = VIE / f"test_verite_{debut:%Y%m%d}_{fin:%Y%m%d}.json"
    sortie.write_text(json.dumps(rapport, ensure_ascii=False, indent=1), encoding="utf-8")
    for l in sorted(tableau, key=lambda x: -x["net_pct_mois_moyen"]):
        print(f"{l['horizon']:>10} | {l['seulement_les_plus_surs']:>5} | brut {l['brut_pct_mois_moyen']:+6.2f} %/mois | "
              f"net {l['net_pct_mois_moyen']:+6.2f} %/mois | gagnants {l['marches_gagnants_net_pct']:5.1f} % | "
              f"en position {l['en_position_pct']:5.1f} % | {l['changements_par_jour']:5.1f} changements/jour")


if __name__ == "__main__":
    main()
