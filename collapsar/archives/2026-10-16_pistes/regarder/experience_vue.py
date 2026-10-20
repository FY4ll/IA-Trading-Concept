"""Expérience du 14/10 après-midi : la VUE D'ENSEMBLE voit-elle mieux que le graphique brut ?
Même question de trader (n'importe quel coup), mêmes années (apprend 2010-2019, notée 2020-2022), mesures honnêtes :
lien prévu/réel SANS les frais, et lien sur le SENS. Repère : yeux « graphique brut » de l'arbre 3 (lien 1,1 %,
sens -0,5 %). Sur le processeur (la carte graphique reste à l'arbre).
Depuis Test_IA : venv_gpu\\Scripts\\python.exe -u -m collapsar.regarder.experience_vue [minutes]
"""
from __future__ import annotations

import json
import sys
from datetime import datetime

import numpy as np
import torch

from collapsar.cerveau.trader import CerveauVueDEnsemble
from collapsar.donnees import marches as dm
from collapsar.regarder.vision_trader import VisionTrader
from collapsar.yeux.graphique import Graphique
from collapsar.yeux.vue_ensemble import N_ENTREES, VueDEnsemble


def dire(t):
    print(f"[{datetime.now():%H:%M:%S}] {t}", flush=True)


def main():
    torch.set_num_threads(8)
    minutes = float(sys.argv[1]) if len(sys.argv) > 1 else 30
    donnees = {m: df for m in dm.liste_marches() if len(df := dm.charger(m)) >= dm.MIN_BOUGIES}
    g = Graphique(donnees, "cpu")
    del donnees
    vue = VueDEnsemble(g)
    vt = VisionTrader(g, n_controle=150_000)
    vt.voir = vue.voir
    garde = lambda idx: idx[torch.from_numpy(vue.valide[idx.numpy()])]
    vt.idx_apprend, vt.idx_controle, vt.idx_temoin = (garde(vt.idx_apprend), garde(vt.idx_controle),
                                                      garde(vt.idx_temoin))
    dire(f"{len(g.noms)} marchés, {N_ENTREES} nombres par situation, {len(vt.idx_apprend):,} situations "
         f"d'apprentissage, {len(vt.idx_controle):,} de contrôle".replace(",", " "))
    torch.manual_seed(0)
    c = CerveauVueDEnsemble(N_ENTREES, oubli=0.1)
    opt = torch.optim.AdamW(c.parameters(), lr=1e-3, weight_decay=1e-4)
    gen = torch.Generator().manual_seed(0)
    courbe, total = [], 0
    for t in range(int(minutes // 5)):
        w = vt.entrainer(c, opt, 5.0, 512, gen)
        total += w["exercices"]
        n = vt.controler(c)
        courbe.append({"minutes": 5 * (t + 1), "coups": total, **{k: n[k] for k in
                       ("lien", "lien_sens", "lien_frais_compris", "score", "bonnes", "par_coeur", "lien_appris")}})
        dire(f"{5 * (t + 1):3d} min, {total / 1e6:.0f} M coups : lien sans frais {n['lien']:+.2f} % | lien sur le "
             f"SENS {n['lien_sens']:+.2f} % | coups sûrs {n['score']:+.2f} % du risque | années apprises : lien "
             f"{n.get('lien_appris', np.nan):+.2f} %, coups sûrs {n.get('par_coeur', np.nan):+.2f}")
        torch.save({"cerveau": c.state_dict()}, dm.RACINE / "collapsar" / "vie" / "vue_ensemble_essai.pt")
    (dm.RACINE / "collapsar" / "vie" / f"experience_vue_{datetime.now():%Y%m%d_%H%M}.json").write_text(
        json.dumps(courbe, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
