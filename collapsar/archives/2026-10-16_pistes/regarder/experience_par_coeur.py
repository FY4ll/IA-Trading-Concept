"""Expérience du 14/10 matin : quel remède empêche le PAR CŒUR de la vision du trader ? (carte graphique, 47 marchés)

Constat : même avec des yeux neufs, du flou et des échelles cachées, après ~115 millions de coups (chaque moment vu
~14 fois) elle récite ses années apprises (+72 % du risque par coup) et perd sur 2020-2022. Nos 8 millions de
situations se chevauchent (deux bougies voisines ont presque le même avenir) : il n'y a qu'environ 100 000 situations
vraiment différentes, qu'un cerveau de 540 000 connexions peut retenir.
Variantes (même graine, mêmes données, même durée) : notes sur les années apprises ET jamais vues, toutes les 5 min.
Depuis Test_IA (cœur arrêté) : venv_gpu\\Scripts\\python.exe -u -m collapsar.regarder.experience_par_coeur
"""
from __future__ import annotations

import json
import sys
from datetime import datetime

import torch

from collapsar.cerveau.trader import CerveauTrader
from collapsar.donnees import marches as dm
from collapsar.regarder.vision_trader import VisionTrader
from collapsar.yeux.graphique import Graphique

VARIANTES = {
    "actuel": dict(largeur=1.0, bruit=0.15, masque=0.25, usure=1e-4, oubli=0.3),
    "petit": dict(largeur=0.35, bruit=0.15, masque=0.25, usure=1e-4, oubli=0.3),
    "fort": dict(largeur=1.0, bruit=0.5, masque=0.5, usure=1e-4, oubli=0.3),
    "frein": dict(largeur=1.0, bruit=0.15, masque=0.25, usure=5e-2, oubli=0.3),
}
MINUTES, TRANCHE = 15, 5


def main():
    dev = torch.device("cuda")
    donnees = {m: df for m in dm.liste_marches() if len(df := dm.charger(m)) >= dm.MIN_BOUGIES}
    horaires = {m: dm.charger_horaire(m, avant=df["time"].iloc[0]) for m, df in donnees.items()}
    g = Graphique(donnees, dev, horaires)
    del donnees, horaires
    vt = VisionTrader(g, n_controle=150_000)
    choix = sys.argv[1:] or list(VARIANTES)
    resultats = {}
    for nom in choix:
        v = VARIANTES[nom]
        torch.manual_seed(0)
        c = CerveauTrader(oubli=v["oubli"], largeur=v["largeur"]).to(dev)
        n_param = sum(p.numel() for p in c.parameters())
        opt = torch.optim.AdamW(c.parameters(), lr=3e-4, weight_decay=v["usure"])
        gen = torch.Generator().manual_seed(0)
        total, courbe = 0, []
        for t in range(MINUTES // TRANCHE):
            w = vt.entrainer(c, opt, TRANCHE, 512, gen, miroir=0.5, bruit=v["bruit"], masque=v["masque"])
            total += w["exercices"]
            n = vt.controler(c)
            courbe.append({"minutes": (t + 1) * TRANCHE, "coups": total, "jamais_vu": n["score"],
                           "appris": n.get("par_coeur"), "gagnants": n["bonnes"], "prevu": n["prevu"]})
            print(f"[{datetime.now():%H:%M}] {nom:7s} ({n_param / 1e3:.0f} k connexions) {(t + 1) * TRANCHE:2d} min, "
                  f"{total / 1e6:.0f} M coups : jamais vu {n['score']:+6.2f} | appris {n.get('par_coeur', 0):+6.2f} | "
                  f"gagnants {n['bonnes']:.0f} % | prévu {n['prevu']:+.0f}", flush=True)
        resultats[nom] = {"reglages": v, "connexions": n_param, "courbe": courbe}
        del c, opt
        torch.cuda.empty_cache()
    (dm.RACINE / "collapsar" / "vie" / f"experience_par_coeur_{datetime.now():%Y%m%d_%H%M}.json").write_text(
        json.dumps(resultats, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
