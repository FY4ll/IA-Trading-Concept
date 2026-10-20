"""Couche 1 : la TENDANCE DE FOND contre ses juges, sur l'or et 5 marchés de robustesse (PLAN_FIGE.md).

    venv_gpu\\Scripts\\python.exe etudes\\2026-10-20_couche1_tendance\\mesurer.py mise_au_point   (comptes seulement)
    venv_gpu\\Scripts\\python.exe etudes\\2026-10-20_couche1_tendance\\mesurer.py test            (UNE fois, verrou)
"""
from __future__ import annotations

import json
import math
import subprocess
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

FIN_DONNEES = pd.Timestamp("2026-10-14")
TEST = (pd.Timestamp("2018-01-01"), FIN_DONNEES)
DEBUT_COMPTE = pd.Timestamp("2017-01-01")              # le compte vit depuis 2017 (positions en place au 01/01/2018)
OR = "XAUUSD"
ROBUSTESSE = ["XAGUSD", "USA500IDXUSD", "USATECHIDXUSD", "EURUSD", "USDJPY"]
NOMS = {"XAUUSD": "or", "XAGUSD": "argent", "USA500IDXUSD": "S&P 500", "USATECHIDXUSD": "Nasdaq 100",
        "EURUSD": "euro-dollar", "USDJPY": "dollar-yen"}
MOIS = (1, 3, 6, 12)
RES = ICI / "resultats"
VERROU = RES / "VERROU_TEST.json"
GIT = r"C:\Users\utilisateur\AppData\Local\GitHubDesktop\app-3.6.6\resources\app\git\cmd\git.exe"


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def un_marche(sym: str) -> dict:
    b15 = D.charger(sym, FIN_DONNEES)
    h1_tout = C.heures(b15)
    m = h1_tout["t"] >= DEBUT_COMPTE
    h1 = {k: (v[m] if k != "t" else v[m]) for k, v in h1_tout.items()}
    out = {"series": {}, "mesures": {}, "infos": {}}
    j0 = TENDANCES[1].jours(b15)
    j0 = j0[j0["fin"] >= DEBUT_COMPTE].reset_index(drop=True)
    ach = C.simuler(sym, h1, j0, np.ones(len(j0), int))
    out["mesures"]["acheteur"] = C.mesures(ach, *TEST)
    out["series"]["acheteur"] = C.mensuel(ach, *TEST)
    out["infos"]["acheteur"] = {"en_position_pct": ach["en_position_pct"]}
    for n in MOIS:
        j = TENDANCES[n].jours(b15)
        j = j[j["fin"] >= DEBUT_COMPTE].reset_index(drop=True)
        s = j["sens"].to_numpy()
        sy = C.simuler(sym, h1, j, s)
        iv = C.simuler(sym, h1, j, -s)
        out["mesures"][f"{n}m"] = C.mesures(sy, *TEST)
        out["series"][f"{n}m"] = C.mensuel(sy, *TEST)
        out["series"][f"{n}m_inverse"] = C.mensuel(iv, *TEST)
        out["infos"][f"{n}m"] = {"en_position_pct": sy["en_position_pct"], "achat_pct": sy["achat_pct"]}
    return {"sym": sym, **out}


def comparer_tout(r: dict) -> dict:
    out = {}
    ach = r["series"]["acheteur"]
    for n in MOIS:
        k = f"{n}m"
        sy, iv = r["series"][k], r["series"][f"{k}_inverse"]
        pile = (sy + iv) / 2
        out[k] = {"pile_ou_face_pct_mois": float(pile.mean()),
                  "contre_pile": C.comparer(sy, pile), "contre_acheteur": C.comparer(sy, ach),
                  "contre_acheteur_risque_egal": C.comparer(sy, ach, risque_egal=True)}
    return out


def robustesse(res: dict) -> dict:
    out = {}
    for n in MOIS:
        k = f"{n}m"
        diffs, signes = [], []
        for sym in ROBUSTESSE:
            sy, ach = res[sym]["series"][k].align(res[sym]["series"]["acheteur"], join="inner")
            b = ach * sy.std(ddof=1) / ach.std(ddof=1) if ach.std(ddof=1) > 0 else ach
            d = sy - b
            diffs.append(d)
            signes.append(float(d.mean()) > 0)
        moy = pd.concat(diffs, axis=1).mean(axis=1)
        q = moy.groupby(moy.index.to_period("Q")).sum()
        inc = float(q.std(ddof=1) / math.sqrt(len(q)) / 3)
        av = float(moy.mean())
        out[k] = {"positifs_sur_5": int(sum(signes)), "avantage_moyen": av, "incertitude": inc,
                  "robuste": bool(sum(signes) >= 3 and av > 2 * inc)}
    return out


def main():
    mode = sys.argv[1]
    RES.mkdir(exist_ok=True)
    if mode == "mise_au_point":
        b15 = D.charger(OR, pd.Timestamp("2018-01-01"))
        h1 = C.heures(b15)
        m = h1["t"] >= pd.Timestamp("2012-01-01")
        h1 = {k: v[m] for k, v in h1.items()}
        for n in MOIS:
            j = TENDANCES[n].jours(b15)
            j = j[j["fin"] >= pd.Timestamp("2012-01-01")].reset_index(drop=True)
            r = C.simuler(OR, h1, j, j["sens"].to_numpy())
            ans = (h1["t"][-1] - h1["t"][0]).days / 365.25
            log(f"or 2012-2017, {n} mois : {len(r['ouvertures']) / ans:.1f} trades/an, en position "
                f"{r['en_position_pct']:.0f} % du temps, dont à l'achat {r['achat_pct']:.0f} %")
        return
    if VERROU.exists():
        raise SystemExit(f"le test a déjà été lancé : {VERROU.read_text(encoding='utf-8')}")
    commit = subprocess.run([GIT, "rev-parse", "HEAD"], capture_output=True, text=True, cwd=RACINE).stdout.strip()
    sale = subprocess.run([GIT, "status", "--porcelain", "--", "cerveau", "core", str(ICI.relative_to(RACINE))],
                          capture_output=True, text=True, cwd=RACINE).stdout.strip()
    VERROU.write_text(json.dumps({"lance": time.strftime("%d/%m/%Y %H:%M:%S"), "commit": commit,
                                  "modifs_non_commitees": sale}, ensure_ascii=False, indent=1), encoding="utf-8")
    with Pool(6) as p:
        liste = p.map(un_marche, [OR] + ROBUSTESSE)
    res = {r["sym"]: r for r in liste}
    sortie = {"marches": {}, "robustesse": robustesse(res)}
    for sym, r in res.items():
        sortie["marches"][sym] = {"nom": NOMS[sym], "mesures": r["mesures"], "infos": r["infos"],
                                  "comparaisons": comparer_tout(r)}
        log(f"== {NOMS[sym]} : acheteur permanent {r['mesures']['acheteur']['gain_pct_mois']:+.2f} %/mois, "
            f"pire baisse {r['mesures']['acheteur']['pire_baisse_pct']:.1f} %, gain/vol "
            f"{r['mesures']['acheteur']['gain_sur_vol']:.2f}, challenge {r['mesures']['acheteur']['challenge']}")
        for n in MOIS:
            k = f"{n}m"
            me, co = r["mesures"][k], sortie["marches"][sym]["comparaisons"][k]
            log(f"   {k:>3} : {me['gain_pct_mois']:+.2f} %/mois, gain/vol {me['gain_sur_vol']:.2f}, pire baisse "
                f"{me['pire_baisse_pct']:.1f} %, pire jour {me['pire_jour_pct']:.2f} %, {me['trades_an']:.1f} trades/an | "
                f"pile {co['contre_pile']['avantage']:+.2f} ± {co['contre_pile']['incertitude']:.2f} | acheteur "
                f"{co['contre_acheteur']['avantage']:+.2f} ± {co['contre_acheteur']['incertitude']:.2f} | risque égal "
                f"{co['contre_acheteur_risque_egal']['avantage']:+.2f} ± {co['contre_acheteur_risque_egal']['incertitude']:.2f}"
                f" | challenge {me['challenge']}")
    for k, v in sortie["robustesse"].items():
        log(f"robustesse {k} : {v}")
    (RES / "test.json").write_text(json.dumps(sortie, ensure_ascii=False, indent=1, default=str), encoding="utf-8")


if __name__ == "__main__":
    main()
