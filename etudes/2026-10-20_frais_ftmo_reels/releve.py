"""Relevé des VRAIS frais FTMO (écart achat - vente, taux de nuit affichés) dans un 2e MetaTrader, toutes les 5 minutes,
jour et nuit (20/10/2026, accord du chef de projet). LECTURE SEULE : aucun ordre. Ne touche JAMAIS au MetaTrader de la
démo Tradeco (refus si le chemin du terminal est le même).

Accès : fichier `Test_IA/.env` (hors git, rempli par le chef de projet ; jamais affiché) :
    FTMO_LOGIN=...            FTMO_MOT_DE_PASSE=...        FTMO_SERVEUR=...  (ex. FTMO-Demo)
    FTMO_TERMINAL=C:\\Users\\utilisateur\\MT5_FTMO\\terminal64.exe   (2e MetaTrader, mode portable ; préparé le 20/10)
Sorties : data/frais_ftmo/brut_AAAAMMJJ.csv (relevés bruts, hors git) ; etudes/2026-10-20_frais_ftmo_reels/resultats/
resume.json (médiane de l'écart par marché et par heure du serveur, taux de nuit affichés ; réécrit chaque heure).

    venv_gpu\\Scripts\\python.exe -u etudes\\2026-10-20_frais_ftmo_reels\\releve.py [--jours 7] [--pas 5]
    venv_gpu\\Scripts\\python.exe etudes\\2026-10-20_frais_ftmo_reels\\releve.py --verifier   (accès + compte, sans relevé)
"""
from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np

ICI = Path(__file__).resolve().parent
RACINE = ICI.parents[1]
ENV = RACINE / ".env"
TERMINAL_TRADECO = Path(r"C:\Program Files\MetaTrader 5\terminal64.exe")
BRUT = RACINE / "data" / "frais_ftmo"
RESUME = ICI / "resultats" / "resume.json"
# noms FTMO (vérifiés le 15/10 sur le compte d'essai : core/ftmo/conditions_ftmo.json -> "symboles")
MARCHES = ["XAUUSD", "XAGUSD", "EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCHF", "USDCAD", "NZDUSD",
           "US500.cash", "US100.cash", "US30.cash", "GER40.cash", "USOIL.cash", "BTCUSD", "ETHUSD"]


def lire_env() -> dict:
    if not ENV.exists():
        raise SystemExit(f"accès absents : créer {ENV} (FTMO_LOGIN, FTMO_MOT_DE_PASSE, FTMO_SERVEUR, FTMO_TERMINAL)")
    out = {}
    for ligne in ENV.read_text(encoding="utf-8").splitlines():
        if "=" in ligne and not ligne.strip().startswith("#"):
            k, v = ligne.split("=", 1)
            out[k.strip()] = v.strip().strip('"')
    manque = [k for k in ("FTMO_LOGIN", "FTMO_MOT_DE_PASSE", "FTMO_SERVEUR", "FTMO_TERMINAL") if not out.get(k)]
    if manque:
        raise SystemExit(f"accès incomplets dans .env : {manque}")
    return out


def connecter(acces: dict):
    import MetaTrader5 as mt5
    terminal = Path(acces["FTMO_TERMINAL"])
    if terminal.resolve() == TERMINAL_TRADECO.resolve():
        raise SystemExit("refus : FTMO_TERMINAL est le MetaTrader de la démo Tradeco ; il faut le 2e MetaTrader")
    if not mt5.initialize(path=str(terminal), login=int(acces["FTMO_LOGIN"]), password=acces["FTMO_MOT_DE_PASSE"],
                          server=acces["FTMO_SERVEUR"], portable=True, timeout=90_000):
        raise SystemExit(f"connexion FTMO impossible : {mt5.last_error()}")
    a = mt5.account_info()
    if a is None or a.trade_mode != mt5.ACCOUNT_TRADE_MODE_DEMO or "FTMO" not in (a.server or "").upper():
        mt5.shutdown()
        raise SystemExit("refus : le compte connecté n'est pas un compte DÉMO FTMO")
    for s in MARCHES:
        mt5.symbol_select(s, True)
    return mt5, a


def releve(mt5) -> list[tuple]:
    lignes = []
    for s in MARCHES:
        t, i = mt5.symbol_info_tick(s), mt5.symbol_info(s)
        if not t or not i or t.bid <= 0 or t.ask <= 0:
            continue
        milieu = (t.bid + t.ask) / 2
        heure = datetime.utcfromtimestamp(t.time)                      # heure du serveur du dernier prix
        lignes.append((heure.strftime("%Y-%m-%d %H:%M:%S"), s, milieu, (t.ask - t.bid) / milieu, i.swap_long,
                       i.swap_short, i.swap_mode, i.swap_rollover3days))
    return lignes


def resumer():
    import pandas as pd
    fichiers = sorted(BRUT.glob("brut_*.csv"))
    if not fichiers:
        return
    df = pd.concat(pd.read_csv(f) for f in fichiers)
    df["heure_serveur"] = pd.to_datetime(df["heure_serveur"])
    df = df.drop_duplicates(["heure_serveur", "marche"])               # prix inchangé (marché fermé) : une fois
    df["h"] = df["heure_serveur"].dt.hour
    out = {"releves": int(len(df)), "du": str(df["heure_serveur"].min()), "au": str(df["heure_serveur"].max()),
           "marches": {}}
    for m, g in df.groupby("marche"):
        out["marches"][m] = {"ecart_median_pct": round(100 * float(g["ecart"].median()), 5),
                             "ecart_p90_pct": round(100 * float(g["ecart"].quantile(0.9)), 5),
                             "par_heure_serveur_median_pct": {int(h): round(100 * float(x.median()), 5)
                                                              for h, x in g.groupby("h")["ecart"]},
                             "nuit_achat_affichee": float(g["swap_long"].iloc[-1]),
                             "nuit_vente_affichee": float(g["swap_short"].iloc[-1]),
                             "mode_nuit": int(g["swap_mode"].iloc[-1]), "jour_triple": int(g["swap_triple"].iloc[-1])}
    RESUME.parent.mkdir(parents=True, exist_ok=True)
    RESUME.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--jours", type=float, default=7)
    ap.add_argument("--pas", type=float, default=5, help="minutes entre deux relevés")
    ap.add_argument("--verifier", action="store_true")
    a = ap.parse_args()
    acces = lire_env()
    mt5, compte = connecter(acces)
    print(f"connecté : compte démo FTMO, serveur {compte.server} (numéro masqué)", flush=True)
    if a.verifier:
        print(f"{len(releve(mt5))} marchés lus", flush=True)
        mt5.shutdown()
        return
    BRUT.mkdir(parents=True, exist_ok=True)
    fin = datetime.now() + timedelta(days=a.jours)
    dernier_resume = 0.0
    try:
        while datetime.now() < fin:
            f = BRUT / f"brut_{datetime.now():%Y%m%d}.csv"
            neuf = not f.exists()
            with open(f, "a", encoding="utf-8") as h:
                if neuf:
                    h.write("heure_serveur,marche,prix,ecart,swap_long,swap_short,swap_mode,swap_triple\n")
                for l in releve(mt5):
                    h.write(",".join(str(x) for x in l) + "\n")
            if time.time() - dernier_resume > 3600:
                resumer()
                dernier_resume = time.time()
            time.sleep(a.pas * 60)
    finally:
        resumer()
        mt5.shutdown()


if __name__ == "__main__":
    main()
