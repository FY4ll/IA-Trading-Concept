"""Test de vérité n° 2 : l'avantage des racines devient-il rentable si on TIENT les positions ?

Même principe que test_verite.py (prédiction de sens de la cime, période jamais apprise, frais réels, 1 x le compte),
mais la position ne suit plus chaque hésitation de la prédiction :
- lissage : moyenne glissante de la prédiction sur N bougies (comme regarder la tendance de son propre avis) ;
- entrée sur conviction forte (au-delà de ses x % de cas les plus sûrs), sortie seulement quand l'avis lissé change
  de sens (pas à la première hésitation).
Mesure du plafond seulement : rien de tout ça n'est une règle donnée à l'IA.
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
from collapsar.juge.test_verite import predictions
from collapsar.mains.fiches import fiche
from collapsar.regarder.exercices import HORIZONS
from collapsar.yeux.graphique import Graphique

VIE = dm.RACINE / "collapsar" / "vie"
LISSAGES = (1, 16, 96, 480)            # bougies : aucun, 4 h, 1 jour, 1 semaine
ENTREES = (0.5, 0.8, 0.95)             # entrer seulement au-delà de ses 50 %, 20 %, 5 % de cas les plus sûrs


def tenir(avis: np.ndarray, seuil: float) -> np.ndarray:
    """Entre quand |avis| dépasse le seuil ; garde la position jusqu'à ce que l'avis change de sens."""
    pos = np.zeros(len(avis))
    p = 0.0
    for i, a in enumerate(avis):
        if p == 0.0:
            if a >= seuil:
                p = 1.0
            elif a <= -seuil:
                p = -1.0
        elif p * a < 0:                                # l'avis s'est retourné : on sort (et on retourne si fort)
            p = np.sign(a) if abs(a) >= seuil else 0.0
        pos[i] = p
    return pos


def logits_caches(debut, fin, dev):
    arbre = Arbre.charger(VIE / "arbre.json")
    cache = VIE / "cache" / f"verite_{arbre.cime}_{len(arbre.branches[arbre.cime].scores)}_{debut:%Y%m%d}_{fin:%Y%m%d}.npz"
    donnees = {}
    for m in dm.liste_marches():
        df = dm.charger(m, jusqua=fin)
        if len(df) >= dm.MIN_BOUGIES and (df["time"] >= debut).sum() > 2000:
            donnees[m] = df
    if cache.exists():
        z = np.load(cache, allow_pickle=True)
        return arbre.cime, donnees, z["sortie"].item()
    cerveau = Cerveau().to(dev)
    cerveau.load_state_dict(torch.load(VIE / "branches" / f"{arbre.cime}.pt", map_location=dev,
                                       weights_only=True)["cerveau"])
    cerveau.eval()
    g = Graphique(donnees, dev)
    sortie = {}
    for j, (m, df) in enumerate(donnees.items()):
        t = df["time"].values
        loc = np.flatnonzero((t >= debut.to_datetime64()) & (t < fin.to_datetime64()))[:-1]
        if len(loc) >= 1000:
            sortie[m] = (loc, predictions(cerveau, g, g.debut_marche[j] + loc))
    cache.parent.mkdir(parents=True, exist_ok=True)
    np.savez(cache, sortie=np.array(sortie, dtype=object))
    return arbre.cime, donnees, sortie


def main():
    debut = pd.Timestamp(sys.argv[1]) if len(sys.argv) > 1 else pd.Timestamp("2023-01-01")
    fin = min(pd.Timestamp(sys.argv[2]) if len(sys.argv) > 2 else dm.FIN_EXAMEN, dm.FIN_EXAMEN)
    dev = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    cime, donnees, sortie = logits_caches(debut, fin, dev)
    res = {}
    for m, (loc, logits) in sortie.items():
        df = donnees[m]
        c = df["close"].to_numpy()
        t = df["time"].values
        r = np.log(c[loc + 1] / c[loc])
        frais = fiche(m).frais / 2
        mois = (t[loc[-1]] - t[loc[0]]) / np.timedelta64(30, "D")
        for h, nom_h in enumerate(HORIZONS):
            for n in LISSAGES:
                avis = pd.Series(logits[:, h]).ewm(span=n).mean().to_numpy() if n > 1 else logits[:, h]
                for e in ENTREES:
                    pos = tenir(avis, np.quantile(np.abs(avis), e))
                    tourne = np.abs(np.diff(np.r_[0.0, pos]))
                    net = (pos * r).sum() - (tourne * frais).sum()
                    res.setdefault((nom_h, n, e), []).append(
                        {"marche": m, "net_mois": net / mois * 100, "brut_mois": (pos * r).sum() / mois * 100,
                         "en_position": float((pos != 0).mean() * 100),
                         "trades_par_semaine": float(tourne.sum() / mois / 4.3)})
    tableau = []
    for (h, n, e), lst in res.items():
        net = np.array([x["net_mois"] for x in lst])
        tableau.append({"horizon": h, "lissage_bougies": n, "entree_plus_surs": f"{int(round((1 - e) * 100))} %",
                        "net_pct_mois_moyen": float(net.mean()), "net_median": float(np.median(net)),
                        "brut_pct_mois_moyen": float(np.mean([x["brut_mois"] for x in lst])),
                        "marches_gagnants_pct": float((net > 0).mean() * 100),
                        "en_position_pct": float(np.mean([x["en_position"] for x in lst])),
                        "trades_par_semaine": float(np.mean([x["trades_par_semaine"] for x in lst]))})
    tableau.sort(key=lambda x: -x["net_pct_mois_moyen"])
    sortie_json = VIE / f"test_tenir_{debut:%Y%m%d}_{fin:%Y%m%d}.json"
    sortie_json.write_text(json.dumps({"quand": datetime.now().isoformat(timespec="seconds"), "cime": cime,
                                       "resultats": tableau,
                                       "par_marche": {f"{h}|{n}|{e}": l for (h, n, e), l in res.items()}},
                                      ensure_ascii=False, indent=1), encoding="utf-8")
    for l in tableau[:15]:
        print(f"{l['horizon']:>10} | lissage {l['lissage_bougies']:>3} | entrée {l['entree_plus_surs']:>4} | "
              f"net {l['net_pct_mois_moyen']:+6.2f} %/mois (médiane {l['net_median']:+5.2f}) | brut "
              f"{l['brut_pct_mois_moyen']:+5.2f} | gagnants {l['marches_gagnants_pct']:5.1f} % | "
              f"en position {l['en_position_pct']:5.1f} % | {l['trades_par_semaine']:5.1f} trades/sem")


if __name__ == "__main__":
    main()
