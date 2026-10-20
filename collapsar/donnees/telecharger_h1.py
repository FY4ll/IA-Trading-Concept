"""Télécharge les bougies HORAIRES de Dukascopy depuis aussi loin qu'elles existent (un fichier par mois), pour donner
à COLLAPSAR des décennies d'historique sur les échelles 1 h -> mois (avant 2010, le 15 minutes n'existe pas).

Heure du serveur (New York + 7 h) comme les autres données. Un mois sans aucune transaction (remplissage plat de
Dukascopy) est ignoré : l'historique commence au premier vrai mois.
Fichiers : data/fx_h1/<SYMBOLE>_H1.csv ; mois bruts gardés dans data/fx_h1/brut/<SYMBOLE>/<AAAA-MM>.csv.
Depuis Test_IA : venv_gpu\\Scripts\\python.exe -u -m collapsar.donnees.telecharger_h1 [AAAA début] [symboles...]
"""
from __future__ import annotations

import lzma
import struct
import sys
import time
from datetime import date

import pandas as pd
import requests

from collapsar.donnees import marches as dm

sys.path.insert(0, str(dm.RACINE / "runs" / "20260919_envv2" / "code" / "scripts"))
from fetch_dukascopy import POINT, utc_to_server  # noqa: E402  (échelles de prix vérifiées)

SORTIE = dm.RACINE / "data" / "fx_h1"
_session = requests.Session()
_session.headers["User-Agent"] = "Mozilla/5.0"


def mois_h1(sym: str, a: int, m: int) -> pd.DataFrame | None:
    url = f"https://datafeed.dukascopy.com/datafeed/{sym}/{a:04d}/{m - 1:02d}/BID_candles_hour_1.bi5"
    for essai in range(6):
        try:
            r = _session.get(url, timeout=60)
            if r.status_code == 404 or (r.status_code == 200 and not r.content):
                return None
            if r.status_code != 200:
                raise IOError(r.status_code)
            raw = lzma.decompress(r.content)
            rec = [struct.unpack(">5if", raw[i * 24:(i + 1) * 24]) for i in range(len(raw) // 24)]
            df = pd.DataFrame(rec, columns=["sec", "open", "close", "low", "high", "volume"])
            df = df[df["volume"] > 0]
            if df.empty:
                return None
            p = POINT.get(sym, 1e-3)
            for c in ("open", "close", "low", "high"):
                df[c] = df[c] * p
            df["time"] = pd.Timestamp(a, m, 1) + pd.to_timedelta(df["sec"], unit="s")
            return df[["time", "open", "high", "low", "close", "volume"]]
        except Exception:
            time.sleep(10 * (essai + 1))
    return "REFUS"


def premiere_annee(sym: str, debut: int) -> int | None:
    """Sondage rapide (le mois de décembre de chaque année, en horaire) : la première année où le marché a de vraies
    bougies d'une heure (les journalières remontent plus loin mais pas les horaires)."""
    for a in range(debut, date.today().year + 1):
        d = mois_h1(sym, a, 12 if a < date.today().year else 1)
        if isinstance(d, pd.DataFrame) and len(d) > 50:
            return a
    return None


def telecharger(sym: str, debut: int):
    vraie = premiere_annee(sym, debut)
    if vraie is None:
        print(f"== {sym} : aucune donnée horaire chez Dukascopy", flush=True)
        return
    # inutile d'aller plus loin que le début de ses bougies de 15 minutes : l'horaire ne sert qu'AVANT
    nom15 = "XAUUSD" if sym == "XAUUSD" else sym
    try:
        debut15 = dm.charger(nom15, jusqua=dm.FIN_EXAMEN)["time"].iloc[0]
        fin_utile = date(debut15.year, debut15.month, 1)
    except Exception:
        fin_utile = date.today()
    print(f"{sym} : données horaires depuis {vraie}, utiles jusqu'à {fin_utile:%Y-%m}", flush=True)
    debut = vraie
    brut = SORTIE / "brut" / sym
    brut.mkdir(parents=True, exist_ok=True)
    aujourd_hui = fin_utile
    morceaux, vide_depuis_debut = [], True
    for a in range(debut, aujourd_hui.year + 1):
        for m in range(1, 13):
            if (a, m) > (aujourd_hui.year, aujourd_hui.month):
                break
            f = brut / f"{a:04d}-{m:02d}.csv"
            courant = (a, m) == (aujourd_hui.year, aujourd_hui.month)
            if f.exists() and not courant:
                d = pd.read_csv(f, parse_dates=["time"])
            else:
                d = mois_h1(sym, a, m)
                if isinstance(d, str):
                    print(f"  ! {sym} {a}-{m:02d} refusé, sera repris", flush=True)
                    continue
                if d is None:
                    d = pd.DataFrame(columns=["time", "open", "high", "low", "close", "volume"])
                if not courant:
                    d.to_csv(f, index=False)
            if len(d):
                vide_depuis_debut = False
                morceaux.append(d)
        if not vide_depuis_debut:
            print(f"{sym} {a} : {sum(len(x) for x in morceaux)} bougies horaires", flush=True)
    if not morceaux:
        print(f"== {sym} : rien", flush=True)
        return
    tout = pd.concat(morceaux).drop_duplicates("time").sort_values("time")
    tout["time"] = utc_to_server(tout["time"])
    tout.to_csv(SORTIE / f"{sym}_H1.csv", index=False)
    print(f"== {sym} : {len(tout)} bougies horaires de {tout['time'].min()} à {tout['time'].max()}", flush=True)


def main():
    debut = int(sys.argv[1]) if len(sys.argv) > 1 else 1995
    symboles = sys.argv[2:] or [m for m in dm.liste_marches() if m in POINT or m == "XAUUSD"]
    for s in symboles:
        telecharger(s, debut)


if __name__ == "__main__":
    main()
