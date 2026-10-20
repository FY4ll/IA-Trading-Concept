"""Collecte des MAÎTRES sur Hyperliquid (15/10/2026, idée validée par le chef de projet : « des milliers d'exemples »).

Hyperliquid est une bourse sur la blockchain : chaque trade de chaque trader est public, et l'interface de
programmation officielle (api.hyperliquid.xyz/info) est faite pour être lue. On la lit LENTEMENT (une requête toutes
les ~1,3 s, sous la limite publiée de 1 200 « poids » par minute ; un historique pèse 20).

Étapes (reprenables : rien n'est retéléchargé deux fois) :
1. classement public -> traders DURABLES : gagnants depuis le début, compte d'au moins 20 000 $, gain total
   raisonnable (pas un ticket de loterie : rendement depuis le début entre +10 % et +2 000 %) ;
2. derniers 2 000 trades de chacun -> part HORS CRYPTO (or, argent, devises, indices, pétrole : marchés « HIP-3 ») ;
3. historique complet (depuis 2023) des retenus, les traders hors crypto d'abord (le chef de projet : « il faut
   varier, on n'a pas que des cryptos »).
Fichiers : data/maitres/hyperliquid/ (classement.json, apercu.jsonl, historiques/<adresse>.csv).
Depuis Test_IA : venv_gpu\\Scripts\\python.exe -u -m collapsar.maitres.hyperliquid [etape] [max]
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import pandas as pd
import requests

from collapsar.donnees.marches import RACINE

API = "https://api.hyperliquid.xyz/info"
CLASSEMENT = "https://stats-data.hyperliquid.xyz/Mainnet/leaderboard"
DOSSIER = RACINE / "data" / "maitres" / "hyperliquid"
PAUSE = 1.3
MOTS_HORS_CRYPTO = ("GOLD", "SILVER", "EUR", "JPY", "GBP", "DXY", "SP500", "US500", "OIL", "WTI", "NDX", "NAS",
                    "XAU", "XAG", "COPPER", "NATGAS", "CHF", "AUD", "CAD")


def hors_crypto(coin: str) -> bool:
    return ":" in coin and any(k in coin.upper() for k in MOTS_HORS_CRYPTO)


def _post(corps: dict, essais: int = 5):
    for k in range(essais):
        try:
            r = requests.post(API, json=corps, timeout=60)
            if r.status_code == 429:
                time.sleep(30 * (k + 1))
                continue
            r.raise_for_status()
            return r.json()
        except requests.RequestException:
            time.sleep(10 * (k + 1))
    return None


def classement() -> list[dict]:
    f = DOSSIER / "classement.json"
    if not f.exists():
        DOSSIER.mkdir(parents=True, exist_ok=True)
        f.write_bytes(requests.get(CLASSEMENT, timeout=120).content)
    return json.loads(f.read_text(encoding="utf-8"))["leaderboardRows"]


def durables(lignes: list[dict]) -> list[dict]:
    choisis = []
    for l in lignes:
        perf = {w: p for w, p in l["windowPerformances"]}
        tout = perf.get("allTime", {})
        try:
            valeur, pnl, roi = float(l["accountValue"]), float(tout["pnl"]), float(tout["roi"])
            vol = float(tout.get("vlm", 0))
        except (KeyError, TypeError, ValueError):
            continue
        if valeur >= 20_000 and pnl > 0 and 0.10 <= roi <= 20.0 and vol >= 1_000_000:
            choisis.append({"adresse": l["ethAddress"], "valeur": valeur, "gain": pnl, "rendement": roi,
                            "volume": vol, "nom": l.get("displayName")})
    return sorted(choisis, key=lambda c: -c["gain"])


def apercu(maximum: int):
    """Étape 2 : les 2 000 derniers trades de chaque trader durable -> part hors crypto (reprend où il en était)."""
    f = DOSSIER / "apercu.jsonl"
    vus = {json.loads(l)["adresse"] for l in f.open(encoding="utf-8")} if f.exists() else set()
    candidats = [c for c in durables(classement()) if c["adresse"] not in vus][:maximum]
    print(f"{len(vus)} traders déjà vus ; {len(candidats)} à regarder", flush=True)
    for i, c in enumerate(candidats):
        fills = _post({"type": "userFills", "user": c["adresse"]}) or []
        coins = pd.Series([x["coin"] for x in fills]).value_counts() if fills else pd.Series(dtype=int)
        hc = int(sum(n for coin, n in coins.items() if hors_crypto(coin)))
        ligne = {**c, "trades_recents": len(fills), "hors_crypto": hc,
                 "part_hors_crypto": hc / max(len(fills), 1), "marches": coins.head(8).to_dict()}
        with f.open("a", encoding="utf-8") as g:
            g.write(json.dumps(ligne, ensure_ascii=False) + "\n")
        if (i + 1) % 50 == 0:
            print(f"  {i + 1}/{len(candidats)} regardés", flush=True)
        time.sleep(PAUSE)


def historique(adresse: str, depuis_ms: int = 1672531200000) -> pd.DataFrame:
    """Tout l'historique d'un trader depuis le 01/01/2023, par tranches de 2 000 exécutions."""
    lignes, debut = [], depuis_ms
    while True:
        lot = _post({"type": "userFillsByTime", "user": adresse, "startTime": debut, "aggregateByTime": False})
        time.sleep(PAUSE)
        if not lot:
            break
        lignes += lot
        dernier = max(x["time"] for x in lot)
        if len(lot) < 2000 or dernier <= debut:
            break
        debut = dernier + 1
    df = pd.DataFrame(lignes)
    if len(df):
        df = df.drop_duplicates("tid").sort_values("time")
    return df


def historiques(maximum: int, part_min: float = 0.3):
    """Étape 3 : historiques complets, traders hors crypto d'abord, puis les meilleurs crypto."""
    sortie = DOSSIER / "historiques"
    sortie.mkdir(parents=True, exist_ok=True)
    ap = [json.loads(l) for l in (DOSSIER / "apercu.jsonl").open(encoding="utf-8")]
    hors = sorted([a for a in ap if a["part_hors_crypto"] >= part_min], key=lambda a: -a["hors_crypto"])
    crypto = sorted([a for a in ap if a["part_hors_crypto"] < part_min], key=lambda a: -a["gain"])
    ordre = hors + crypto
    faits = 0
    for a in ordre:
        f = sortie / f"{a['adresse']}.csv"
        if f.exists():
            continue
        df = historique(a["adresse"])
        df.to_csv(f, index=False)
        courbe = _post({"type": "portfolio", "user": a["adresse"]})      # courbes officielles valeur / gains
        time.sleep(PAUSE)
        if courbe:
            f.with_suffix(".courbe.json").write_text(json.dumps(dict(courbe)), encoding="utf-8")
        faits += 1
        print(f"  {a['adresse'][:10]}… : {len(df)} exécutions ({a['part_hors_crypto']*100:.0f} % hors crypto)", flush=True)
        if faits >= maximum:
            break


if __name__ == "__main__":
    etape = sys.argv[1] if len(sys.argv) > 1 else "apercu"
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 3000
    if etape == "apercu":
        apercu(n)
    elif etape == "historiques":
        historiques(n)
