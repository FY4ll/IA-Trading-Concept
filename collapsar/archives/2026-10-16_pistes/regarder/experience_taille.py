"""Expérience « cerveau plus grand » (13/10/2026 soir) : avec 20 ans d'historique, un cerveau plus grand voit-il mieux ?
Cerveaux NEUFS, même temps d'entraînement, même contrôle 2020-2022 (3 ans jamais vus), 2 tirages par taille.
Depuis Test_IA : venv_gpu\\Scripts\\python.exe -u -m collapsar.regarder.experience_taille [minutes]
"""
from __future__ import annotations

import json
import sys
from datetime import datetime

import numpy as np
import torch

from collapsar.cerveau.reseau import Cerveau
from collapsar.donnees import marches as dm
from collapsar.regarder import exercices as exo
from collapsar.yeux.graphique import Graphique

VIE = dm.RACINE / "collapsar" / "vie"


def main():
    minutes = float(sys.argv[1]) if len(sys.argv) > 1 else 10
    dev = torch.device("cuda")
    donnees = {m: d for m in dm.liste_marches() if len(d := dm.charger(m)) >= dm.MIN_BOUGIES}
    horaires = {m: dm.charger_horaire(m, avant=df["time"].iloc[0]) for m, df in donnees.items()}
    g = Graphique(donnees, dev, horaires)
    ex = exo.Exercices(g)
    print(f"{len(ex.idx_apprend):,} exercices (1999-2019), {len(ex.idx_controle):,} de contrôle (2020-2022)".replace(",", " "),
          flush=True)
    res = {}
    for largeur in (1.0, 2.5):
        res[largeur] = []
        for graine in (0, 1):
            torch.manual_seed(graine)
            c = Cerveau(largeur=largeur).to(dev)
            n = sum(p.numel() for p in c.parameters())
            opt = torch.optim.AdamW(c.parameters(), lr=3e-4, weight_decay=1e-4)
            notes = []
            for k in range(int(minutes // 5)):
                ex.entrainer(c, opt, 5, 512, torch.Generator().manual_seed(graine * 100 + k))
                notes.append(round(ex.controler(c)["score"], 2))
            res[largeur].append(notes)
            print(f"[{datetime.now():%H:%M}] taille {largeur} ({n:,} connexions) tirage {graine} : "
                  f"{' -> '.join(f'{x:.2f}' for x in notes)} %".replace(",", " "), flush=True)
            del c, opt
            torch.cuda.empty_cache()
        print(f"   taille {largeur} : moyenne finale {np.mean([n[-1] for n in res[largeur]]):.2f} %", flush=True)
    (VIE / "experience_taille.json").write_text(json.dumps({str(k): v for k, v in res.items()}, indent=1),
                                                encoding="utf-8")


if __name__ == "__main__":
    main()
