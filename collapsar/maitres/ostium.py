"""Maîtres d'OSTIUM (échange sur la chaîne publique Arbitrum, spécialisé devises, or, argent, indices, pétrole ;
15/10/2026). Chaque ordre exécuté est inscrit sur la chaîne : personne ne peut le truquer ni cacher les perdants.

Source : le sous-graphe public officiel (adresse lue dans le paquet officiel ostium-python-sdk, config.py), en
lecture seule, sans clé, à cadence lente. Données depuis 08/2024. On ne garde que nos marchés (pas de crypto ni
d'actions). Unités de la chaîne : prix x 1e18, montants en USDC x 1e6, levier x 100, pourcentages x 1e6 (closePercent
x 100).

Fichier : data/maitres/ostium/ordres.csv (tous les ordres ouverture/fermeture, ajoutés au fil de l'eau).
Depuis Test_IA : venv_gpu\\Scripts\\python.exe -u -m collapsar.maitres.ostium [boucle]
"""
from __future__ import annotations

import sys
import time

import pandas as pd
import requests

from collapsar.donnees.marches import RACINE

URL = ("https://api.subgraph.ormilabs.com/api/public/67a599d5-c8d2-4cc4-9c4d-2975a97bc5d8/subgraphs/ost-prod/"
       "live/gn")
DOSSIER = RACINE / "data" / "maitres" / "ostium"
FICHIER = DOSSIER / "ordres.csv"
# paire Ostium -> nos données (seulement ce que nous savons simuler)
MARCHES = {"EURUSD": "EURUSD", "GBPUSD": "GBPUSD", "USDJPY": "USDJPY", "USDCAD": "USDCAD", "USDCHF": "USDCHF",
           "AUDUSD": "AUDUSD", "NZDUSD": "NZDUSD", "XAUUSD": "XAUUSD", "XAGUSD": "XAGUSD", "CLUSD": "LIGHTCMDUSD",
           "BRENTUSD": "BRENTCMDUSD", "SPXUSD": "USA500IDXUSD", "NDXUSD": "USATECHIDXUSD", "DJIUSD": "USA30IDXUSD",
           "DAXEUR": "DEUIDXEUR", "FTSEGBP": "GBRIDXGBP", "NIKJPY": "JPNIDXJPY"}
CHAMPS = ("id tradeID trader isBuy orderType orderAction price executedAt collateral leverage notional closePercent "
          "profitPercent totalProfitPercent amountSentToTrader pair{from to}")
# ouverture (au marché ou ordre à l'avance) et toutes les sorties : à la main, stop, objectif, liquidation,
# fermeture de fin de journée
FERMETURES = ("Close", "StopLoss", "TakeProfit", "Liquidation", "CloseDayTrade")
ACTIONS = '["Open","' + '","'.join(FERMETURES) + '"]'
PAUSE = 1.5


def _requete(corps: str, essais: int = 6) -> dict:
    for k in range(essais):
        try:
            r = requests.post(URL, json={"query": corps}, timeout=90)
            d = r.json()
            if "errors" not in d:
                return d["data"]
            print("erreur du sous-graphe :", str(d["errors"])[:200], flush=True)
        except Exception as e:
            print(f"réseau : {type(e).__name__}", flush=True)
        time.sleep(10 * (k + 1))
    raise RuntimeError("sous-graphe Ostium injoignable")


def paires() -> dict[str, str]:
    """identifiant Ostium -> notre marché."""
    d = _requete("{pairs(first:500){id from to}}")
    return {p["id"]: MARCHES[p["from"] + p["to"]] for p in d["pairs"] if p["from"] + p["to"] in MARCHES}


def collecter() -> int:
    """Ajoute au fichier tous les ordres ouverture/fermeture exécutés depuis le dernier connu. Rend le nombre ajouté."""
    DOSSIER.mkdir(parents=True, exist_ok=True)
    ids = paires()
    liste = "[" + ",".join(f'"{i}"' for i in ids) + "]"
    deja = pd.read_csv(FICHIER, usecols=["id", "executedAt"]) if FICHIER.exists() else None
    curseur = int(deja["executedAt"].max()) if deja is not None and len(deja) else 0
    vus = set(deja.loc[deja["executedAt"] == curseur, "id"].astype(str)) if deja is not None else set()
    ajoutes = 0
    while True:
        d = _requete('{orders(first:1000,orderBy:executedAt,orderDirection:asc,where:{isPending:false,'
                     'isCancelled:false,orderAction_in:%s,pair_in:%s,executedAt_gte:"%d"}){%s}}'
                     % (ACTIONS, liste, curseur, CHAMPS))
        lot = [o for o in d["orders"] if o["id"] not in vus]
        if not lot:
            break
        df = pd.DataFrame([{**{k: v for k, v in o.items() if k != "pair"},
                            "paire": o["pair"]["from"] + o["pair"]["to"]} for o in lot])
        df.to_csv(FICHIER, mode="a", header=not FICHIER.exists(), index=False)
        ajoutes += len(df)
        nouveau = int(df["executedAt"].astype(int).max())
        vus = (vus if nouveau == curseur else set()) | set(df.loc[df["executedAt"].astype(int) == nouveau, "id"])
        curseur = nouveau
        if ajoutes % 20000 < 1000:
            print(f"{ajoutes} ordres ajoutés, jusqu'au {pd.Timestamp(curseur, unit='s'):%d/%m/%Y}", flush=True)
        time.sleep(PAUSE)
    return ajoutes


def main():
    boucle = len(sys.argv) > 1 and sys.argv[1] == "boucle"
    while True:
        n = collecter()
        print(f"{pd.Timestamp.now():%d/%m %H:%M} : {n} ordres ajoutés (fichier {FICHIER})", flush=True)
        if not boucle:
            return
        time.sleep(3 * 3600)


if __name__ == "__main__":
    main()
