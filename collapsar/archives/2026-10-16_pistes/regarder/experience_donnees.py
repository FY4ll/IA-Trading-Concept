"""Expérience « piste A » (13/10/2026) : PLUS D'ANNÉES rendent-elles les racines plus justes sur des années jamais vues ?

Deux cerveaux NEUFS, même forme, même temps d'entraînement, même contrôle — seule la quantité d'années change :
- élève 1 : apprend 2018 -> 2019 (2 ans) ;
- élève 2 : apprend 2010 -> 2019 (10 ans, là où l'historique existe) ;
- contrôle : 2020 -> 2022 (3 ans jamais vus, au lieu de 5 mois : beaucoup moins de hasard de mesure).
Depuis Test_IA : venv_gpu\\Scripts\\python.exe -u -m collapsar.regarder.experience_donnees [minutes par élève]
"""
from __future__ import annotations

import json
import sys
import time
from datetime import datetime

import pandas as pd
import torch

from collapsar.cerveau.reseau import Cerveau
from collapsar.donnees import marches as dm
from collapsar.regarder import exercices as exo
from collapsar.yeux.graphique import Graphique

VIE = dm.RACINE / "collapsar" / "vie"
DEBUT_CONTROLE = pd.Timestamp("2020-02-05")          # 35 jours après la fin d'apprentissage (31/12/2019)


def dire(t):
    print(f"[{datetime.now():%H:%M:%S}] {t}", flush=True)


def main():
    minutes = float(sys.argv[1]) if len(sys.argv) > 1 else 25
    dev = torch.device("cuda")
    exo.N_CONTROLE = 300_000
    donnees = {m: d for m in dm.liste_marches() if len(d := dm.charger(m)) >= dm.MIN_BOUGIES}
    g = Graphique(donnees, dev)
    res = {}
    for nom, debut in (("2 ans (2018-2019)", "2018-01-01"), ("10 ans (2010-2019)", "2010-01-01")):
        ex = exo.Exercices(g, debut_controle=DEBUT_CONTROLE, debut_apprentissage=pd.Timestamp(debut))
        dire(f"{nom} : {len(ex.idx_apprend):,} exercices d'apprentissage, {len(ex.idx_controle):,} de contrôle".replace(",", " "))
        torch.manual_seed(0)
        cerveau = Cerveau().to(dev)
        opt = torch.optim.AdamW(cerveau.parameters(), lr=3e-4, weight_decay=1e-4)
        gen = torch.Generator().manual_seed(0)
        courbe = []
        for etape in range(int(minutes // 5)):
            t = ex.entrainer(cerveau, opt, 5, 512, gen)
            n = ex.controler(cerveau)
            courbe.append({"minutes": (etape + 1) * 5, "score": n["score"], "bonnes": n["bonnes"],
                           "horizons": {h: round(n[h]["ponderees"], 2) for h in exo.HORIZONS},
                           "meme_reponse": {h: round(n[h]["meme_reponse"], 2) for h in exo.HORIZONS}})
            detail = ", ".join(f"{h} {n[h]['ponderees']:.2f}" for h in exo.HORIZONS)
            dire(f"  {nom} après {(etape + 1) * 5} min : {n['score']:.2f} % des mouvements bien devinés ({detail})")
        res[nom] = courbe
        del cerveau, opt
        torch.cuda.empty_cache()
    (VIE / "experience_donnees.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
