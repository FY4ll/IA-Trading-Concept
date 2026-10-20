"""Couche 1 (perception) : mesure des 4 détecteurs codés à la main contre les deux juges (PLAN_FIGE.md).

    venv_gpu\\Scripts\\python.exe etudes\\2026-10-20_couche1_perception\\mesurer.py mise_au_point
        -> 2010-2017 : SEULEMENT les comptes et la plausibilité (aucun gain affiché : rien à régler dessus)
    venv_gpu\\Scripts\\python.exe etudes\\2026-10-20_couche1_perception\\mesurer.py test
        -> 2018-01-01 -> 2026-10-13, UNE fois (verrou resultats/VERROU_TEST.json, écrit AVANT le calcul) ;
           puis, à titre de contrôle, les mêmes tableaux sur 2010-2017.
    ... mesurer.py test2
        -> CORRECTIF DE MESURE (20/10 03h25, PLAN_FIGE « Avenant 1 ») : exécution sur les bougies d'une minute, la
           bougie d'entrée ne compte pour personne. Règles du détecteur inchangées. Verrou resultats/VERROU_TEST_2.json.
           Le 1er lancement (biaisé) est gardé : resultats/test_v1_biaise.json.
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

ICI = Path(__file__).resolve().parent
RACINE = ICI.parents[1]
sys.path.insert(0, str(RACINE))

import numpy as np
import pandas as pd

from cerveau.mesure import juges as J
from cerveau.mesure import trades as T
from cerveau.perception.detecteur import DETECTEURS
from core import donnees as D

FIN_DONNEES = pd.Timestamp("2026-10-14")
MISE_AU_POINT = (pd.Timestamp("2010-01-01"), pd.Timestamp("2018-01-01"))
TEST = (pd.Timestamp("2018-01-01"), FIN_DONNEES)
RES = ICI / "resultats"
VERROU = RES / "VERROU_TEST.json"
VERROU_2 = RES / "VERROU_TEST_2.json"
GIT = r"C:\Users\utilisateur\AppData\Local\GitHubDesktop\app-3.6.6\resources\app\git\cmd\git.exe"


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def tous_les_trades(b15: pd.DataFrame, execution: pd.DataFrame) -> tuple[dict, dict]:
    out, comptes = {}, {}
    for u, det in DETECTEURS.items():
        j = det.journal(RES / "journaux")
        t0 = time.time()
        c = {}
        av = det.avis(b15, compter=c)
        fins = det.bougies(b15)["fin"]
        tr = T.trades(av, execution, fins)
        c["executes"] = int(len(tr))
        comptes[u], out[u] = c, tr
        j.info(f"{det.nom} : {c} ({time.time() - t0:.0f} s)")
        log(f"{det.nom} : {c} ({time.time() - t0:.0f} s)")
    return out, comptes


def periode(tr: pd.DataFrame, p) -> pd.DataFrame:
    return tr[(tr["heure_entree"] >= p[0]) & (tr["heure_entree"] < p[1])]


def plausibilite(tr: pd.DataFrame) -> dict:
    return {"trades": int(len(tr)), "achats_pct": float(100 * (tr["sens"] > 0).mean()) if len(tr) else None,
            "risque_median_pct_prix": float(100 * (tr["risque_prix"] / tr["entree_reelle"]).median()) if len(tr) else None,
            "objectif_median_R": float(((tr["objectif"] - tr["entree_reelle"]) * tr["sens"] / tr["risque_prix"]).median()) if len(tr) else None,
            "cout_median_R": float(tr["cout_R"].median()) if len(tr) else None,
            "attente_mediane_h": float(((tr["heure_entree"] - tr["temps"]).dt.total_seconds() / 3600).median()) if len(tr) else None}


def tableau(trs: dict, p) -> dict:
    return {u: {"a": J.juger(periode(t, p), "a"), "b": J.juger(periode(t, p), "b")} for u, t in trs.items()}


def main():
    mode = sys.argv[1]
    RES.mkdir(exist_ok=True)
    if mode in ("test", "test2"):
        verrou = VERROU if mode == "test" else VERROU_2
        if verrou.exists():
            raise SystemExit(f"ce test a déjà été lancé : {verrou.read_text(encoding='utf-8')}")
        if mode == "test2" and not VERROU.exists():
            raise SystemExit("test2 n'existe que comme correctif du 1er lancement")
        commit = subprocess.run([GIT, "rev-parse", "HEAD"], capture_output=True, text=True, cwd=RACINE).stdout.strip()
        sale = subprocess.run([GIT, "status", "--porcelain", "--", "cerveau", "core", str(ICI.relative_to(RACINE))],
                              capture_output=True, text=True, cwd=RACINE).stdout.strip()
        verrou.write_text(json.dumps({"lance": time.strftime("%d/%m/%Y %H:%M:%S"), "commit": commit,
                                      "modifs_non_commitees": sale, "periode": [str(TEST[0].date()), str(TEST[1].date())]},
                                     ensure_ascii=False, indent=1), encoding="utf-8")
    b15 = D.charger("XAUUSD", FIN_DONNEES)
    log(f"or 15 min : {len(b15)} bougies, {b15['time'].min()} -> {b15['time'].max()}")
    if mode == "test":
        execution = b15
    else:                                              # correctif : exécution à la minute
        execution = D.charger_minutes_or(FIN_DONNEES, depuis=pd.Timestamp("2009-06-01"))
        log(f"or 1 min : {len(execution)} bougies, {execution['time'].min()} -> {execution['time'].max()}")
    trs, comptes = tous_les_trades(b15, execution)
    if mode == "mise_au_point":
        out = {"comptes_toute_histoire": comptes,
               "plausibilite_2010_2017": {u: plausibilite(periode(t, MISE_AU_POINT)) for u, t in trs.items()}}
        (RES / "mise_au_point.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
        for u, p in out["plausibilite_2010_2017"].items():
            log(f"{u} 2010-2017 : {p}")
        return
    out = {"comptes_toute_histoire": comptes, "test_2018_2026": tableau(trs, TEST),
           "controle_2010_2017": tableau(trs, MISE_AU_POINT)}
    suffixe = "" if mode == "test2" else "_v1_biaise"
    (RES / f"test{suffixe}.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    pd.concat([t.assign(unite=u) for u, t in trs.items()]).to_csv(RES / f"trades{suffixe}.csv", index=False)
    for per in ("test_2018_2026", "controle_2010_2017"):
        for u, m in out[per].items():
            for k in ("a", "b"):
                r = m[k]
                log(f"{per} {u} ({k}) : {r['trades']} trades, achats {r['achats_pct']:.0f} %, gain {r['gain_moyen']:+.3f}, "
                    f"pile {r['pile_ou_face']:+.3f}, achat {r['toujours_achat']:+.3f} | avantage pile {r['avantage_pile']:+.3f} "
                    f"± {r['incertitude_pile']:.3f}, achat {r['avantage_achat']:+.3f} ± {r['incertitude_achat']:.3f} "
                    f"| net {r['net']}")


if __name__ == "__main__":
    main()
