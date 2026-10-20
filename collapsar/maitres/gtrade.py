"""Collecte des MAÎTRES sur gTrade (Gains Network) — 15/10/2026, source n°2 de la recherche « sources de maîtres ».

Bourse sur la blockchain (Arbitrum, Base, Polygon) : chaque trade est public et impossible à truquer ; l'interface
officielle documentée (docs.gains.trade) est en lecture libre (« aucune authentification requise pour les points de
lecture publics »). On la lit lentement. Atout : marchés HORS CRYPTO (devises, or, argent, platine, pétrole, S&P 500
via SPY, Nasdaq via QQQ), et chaque trade donne le levier, le stop et l'objectif.

1. découverte : les trades des dernières 72 h de chaque chaîne -> adresses qui tradent HORS CRYPTO (cumulées d'une
   fois sur l'autre dans data/maitres/gtrade/adresses.json) ;
2. historique complet de chaque adresse retenue (pagination officielle) -> data/maitres/gtrade/historiques/.
Depuis Test_IA : venv_gpu\\Scripts\\python.exe -u -m collapsar.maitres.gtrade [boucle]
"""
from __future__ import annotations

import json
import sys
import time
from datetime import datetime

import pandas as pd
import requests

from collapsar.donnees.marches import RACINE

BASE = "https://backend-global.gains.trade/api"
CHAINES = {42161: "arbitrum", 8453: "base", 137: "polygon"}
DOSSIER = RACINE / "data" / "maitres" / "gtrade"
PAUSE = 2.0
DEVISES = {"EUR", "USD", "JPY", "GBP", "CHF", "AUD", "CAD", "NZD", "SEK", "NOK", "MXN", "TRY", "ZAR", "SGD", "HKD", "CNH"}
MOTS = ("XAU", "XAG", "XPT", "XPD", "WTI", "BRENT", "OIL", "SPX", "SPY", "QQQ", "NDX", "NAS", "DJI", "DAX", "FTSE", "NIK",
        "CAC", "COPPER", "NATGAS")


def hors_crypto(paire: str) -> bool:
    a, b = paire.split("/")[0], paire.split("/")[-1]
    return (a in DEVISES and b in DEVISES) or any(k in a for k in MOTS)


def _get(url: str, params: dict | None = None, essais: int = 5):
    for k in range(essais):
        try:
            r = requests.get(url, params=params, timeout=120)
            if r.status_code == 429:
                time.sleep(60 * (k + 1))
                continue
            r.raise_for_status()
            return r.json()
        except requests.RequestException:
            time.sleep(15 * (k + 1))
    return None


def decouvrir() -> dict:
    f = DOSSIER / "adresses.json"
    DOSSIER.mkdir(parents=True, exist_ok=True)
    adr = json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}
    for chaine in CHAINES:
        d = _get(f"{BASE}/trading-history/72h", {"chainId": chaine}) or []
        for t in d:
            if hors_crypto(str(t.get("pair", ""))):
                cle = f"{chaine}:{t['address']}"
                a = adr.setdefault(cle, {"chaine": chaine, "adresse": t["address"], "paires": {}, "vu": None})
                a["paires"][t["pair"]] = a["paires"].get(t["pair"], 0) + 1
                a["vu"] = datetime.now().isoformat(timespec="seconds")
        time.sleep(PAUSE)
    f.write_text(json.dumps(adr, ensure_ascii=False, indent=1), encoding="utf-8")
    return adr


def historique(chaine: int, adresse: str) -> pd.DataFrame:
    lignes, curseur = [], None
    while True:
        p = {"chainId": chaine, "limit": 500}
        if curseur is not None:
            p["cursor"] = curseur
        d = _get(f"{BASE}/personal-trading-history/{adresse}", p)
        time.sleep(PAUSE)
        if not d:
            break
        lignes += d.get("data", [])
        pag = d.get("pagination") or {}
        if not pag.get("hasMore") or pag.get("nextCursor") is None:
            break
        curseur = pag["nextCursor"]
    return pd.DataFrame(lignes)


def historiques(maximum: int = 10_000):
    sortie = DOSSIER / "historiques"
    sortie.mkdir(parents=True, exist_ok=True)
    adr = json.loads((DOSSIER / "adresses.json").read_text(encoding="utf-8"))
    faits = 0
    for cle, a in sorted(adr.items(), key=lambda kv: -sum(kv[1]["paires"].values())):
        f = sortie / f"{a['chaine']}_{a['adresse']}.csv"
        if f.exists():
            continue
        df = historique(a["chaine"], a["adresse"])
        df.to_csv(f, index=False)
        faits += 1
        n_hc = int(df["pair"].map(hors_crypto).sum()) if "pair" in df else 0
        print(f"  {a['adresse'][:10]}… ({CHAINES[a['chaine']]}) : {len(df)} actions, dont {n_hc} hors crypto", flush=True)
        if faits >= maximum:
            break


if __name__ == "__main__":
    boucle = len(sys.argv) > 1 and sys.argv[1] == "boucle"
    while True:
        adr = decouvrir()
        print(f"[{datetime.now():%d/%m %H:%M}] {len(adr)} adresses hors crypto connues", flush=True)
        historiques()
        if not boucle:
            break
        time.sleep(3 * 3600)                     # les 72 dernières heures : un passage toutes les 3 heures suffit
