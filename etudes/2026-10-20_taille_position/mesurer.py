"""Taille de position : passe unique (PLAN.md). venv_gpu\\Scripts\\python.exe etudes\\2026-10-20_taille_position\\mesurer.py"""
from __future__ import annotations

import json
import sys
import time
from multiprocessing import Pool
from pathlib import Path

ICI = Path(__file__).resolve().parent
RACINE = ICI.parents[1]
sys.path.insert(0, str(RACINE))

import numpy as np
import pandas as pd

from cerveau.mesure import compte as C
from cerveau.perception.tendance import TENDANCES
from core import donnees as D

FIN = pd.Timestamp("2026-10-14")
TEST = (pd.Timestamp("2018-01-01"), FIN)
DEBUT_COMPTE = pd.Timestamp("2017-01-01")
SIGNAUX = ("acheteur", 1, 3, 6, 12)
VERROU = ICI / "resultats" / "VERROU.json"


def un(args):
    signal, taille = args
    b15 = D.charger("XAUUSD", FIN)
    h1 = C.heures(b15)
    m = h1["t"] >= DEBUT_COMPTE
    h1 = {k: v[m] for k, v in h1.items()}
    j = TENDANCES[1 if signal == "acheteur" else signal].jours(b15)
    j = j[j["fin"] >= DEBUT_COMPTE].reset_index(drop=True)
    s = np.ones(len(j), int) if signal == "acheteur" else j["sens"].to_numpy()
    r = C.simuler("XAUUSD", h1, j, s, taille=taille)
    return str(signal), taille, C.mesures_relatives(r, *TEST)


def main():
    (ICI / "resultats").mkdir(exist_ok=True)
    if VERROU.exists():
        raise SystemExit("passe unique déjà lancée")
    VERROU.write_text(json.dumps({"lance": time.strftime("%d/%m/%Y %H:%M:%S")}), encoding="utf-8")
    with Pool(6) as p:
        res = p.map(un, [(s, t) for s in SIGNAUX for t in C.TAILLES])
    out = {}
    for s, t, m in res:
        out.setdefault(s, {})[t] = m
        print(f"{s:>9} {t:>11} : {m['rendement_an_pct']:+6.2f} %/an, vol {m['volatilite_an_pct']:5.1f} %, gain/vol "
              f"{m['gain_sur_vol']:5.2f}, pire baisse {m['pire_baisse_pct']:5.1f} %, pire jour {m['pire_jour_pct']:6.2f} %, "
              f"jours<=-5% {m['jours_sous_5pct']}, frais {m['frais_pct_an']:.2f} + nuits {m['nuits_pct_an']:.2f} %/an, "
              f"rotation {m['rotation_x_an']:.1f}x, challenge {m['challenge']}", flush=True)
    (ICI / "resultats" / "taille.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
