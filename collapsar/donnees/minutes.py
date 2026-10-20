"""Bougies d'UNE MINUTE (prix vendeur ET acheteur) de Dukascopy, pour la piste « ouverture de New York » (15/10/2026).

Prix acheteur le mercredi seulement. Seule la plage 12h -> 22h UTC est gardée (la séance de New York 9h30-16h y tient toute l'année, été comme hiver).
Fichiers : data/minutes/<SYMBOLE>/<AAAA-MM>.csv (heure UTC ; colonnes open/high/low/close du prix vendeur, et
ask_open/ask_close du prix acheteur -> l'écart réel minute par minute). Reprise : un mois fini n'est pas
retéléchargé. Depuis Test_IA : venv_gpu\\Scripts\\python.exe -u -m collapsar.donnees.minutes [symboles...]
"""
from __future__ import annotations

import lzma
import struct
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta

import numpy as np
import pandas as pd
import requests

from collapsar.donnees.marches import RACINE

DOSSIER = RACINE / "data" / "minutes"
POINT = {"USATECHIDXUSD": 1e-3, "USA500IDXUSD": 1e-3, "XAUUSD": 1e-3}
DEBUT = date(2015, 1, 1)
PLAGE_UTC = (12, 22)
PAUSE = 1.0                          # secondes entre deux demandes, au mieux (le serveur refuse si on va trop vite)
_pause = PAUSE
_s = requests.Session()
_s.headers["User-Agent"] = "Mozilla/5.0"


def _jour(sym: str, d: date, cote: str):
    url = (f"https://datafeed.dukascopy.com/datafeed/{sym}/{d.year:04d}/{d.month - 1:02d}/{d.day:02d}/"
           f"{cote}_candles_min_1.bi5")
    global _pause
    for k in range(40):
        try:
            time.sleep(_pause)
            r = _s.get(url, timeout=60)
            if r.status_code == 503:                     # « trop de demandes » : on ralentit et on retente
                STATS["refusees"] += 1
                _pause = min(_pause * 2, 120.0)
                continue
            STATS["acceptees"] += 1
            _pause = max(PAUSE, _pause * 0.7)            # il accepte : on réaccélère doucement
            if r.status_code == 404 or (r.status_code == 200 and not r.content):
                return None
            if r.status_code != 200:
                raise IOError(f"HTTP {r.status_code}")
            raw = lzma.decompress(r.content)
            a = np.frombuffer(raw, dtype=">i4").reshape(-1, 6)
            vol = np.frombuffer(raw, dtype=">f4").reshape(-1, 6)[:, 5]
            df = pd.DataFrame({"sec": a[:, 0], "open": a[:, 1], "close": a[:, 2], "low": a[:, 3], "high": a[:, 4],
                               "volume": vol})
            df = df[df["volume"] > 0]
            if df.empty:
                return None
            df["time"] = pd.Timestamp(d) + pd.to_timedelta(df["sec"], unit="s")
            df = df[(df["time"].dt.hour >= PLAGE_UTC[0]) & (df["time"].dt.hour < PLAGE_UTC[1])]
            p = POINT[sym]
            for c in ("open", "close", "low", "high"):
                df[c] = df[c] * p
            return df[["time", "open", "high", "low", "close", "volume"]]
        except Exception:
            time.sleep(5 * (k + 1))
    return "RATE"


def jour(sym: str, d: date):
    """Prix vendeur chaque jour ; prix acheteur le MERCREDI seulement (de quoi mesurer l'écart à l'ouverture sans
    doubler les demandes au serveur, qui refuse quand on va trop vite)."""
    bid = _jour(sym, d, "BID")
    if not isinstance(bid, pd.DataFrame):
        return bid
    ask = _jour(sym, d, "ASK") if d.weekday() == 2 else None
    if isinstance(ask, pd.DataFrame):
        a = ask.rename(columns={"open": "ask_open", "close": "ask_close"})[["time", "ask_open", "ask_close"]]
        bid = bid.merge(a, on="time", how="left")
    else:
        bid["ask_open"], bid["ask_close"] = np.nan, np.nan
    return bid


STATS = {"acceptees": 0, "refusees": 0}


def mois(sym: str, y: int, m: int, aujourd_hui: date) -> int:
    """Un fichier par MOIS (reprise sans perte) ; le mois en cours est refait à chaque lancement."""
    f = DOSSIER / sym / f"{y}-{m:02d}.csv"
    courant = (y, m) == (aujourd_hui.year, aujourd_hui.month)
    if f.exists() and not courant:
        return -1
    jours = [date(y, m, 1) + timedelta(days=i) for i in range(31)]
    jours = [d for d in jours if d.month == m and d.weekday() < 5 and DEBUT <= d < aujourd_hui]
    res = [jour(sym, d) for d in jours]           # une demande à la fois (le serveur bride)
    if any(isinstance(r, str) for r in res):
        return -2                                  # jours refusés : le mois sera repris au prochain lancement
    parts = [r for r in res if isinstance(r, pd.DataFrame)]
    df = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame(columns=["time", "open", "high", "low", "close"])
    f.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(f, index=False)
    return len(df)


def main():
    syms = sys.argv[1:] or list(POINT)
    aujourd_hui = date.today()
    for tour in range(5):                          # les mois refusés sont repris aux tours suivants
        reste = 0
        for sym in syms:
            for y in range(DEBUT.year, aujourd_hui.year + 1):
                for m in range(1, 13):
                    if date(y, m, 1) > aujourd_hui:
                        break
                    t0 = time.time()
                    n = mois(sym, y, m, aujourd_hui)
                    if n == -1:
                        continue
                    reste += n == -2
                    print(f"{sym} {y}-{m:02d} : {'REFUSÉ, repris plus tard' if n == -2 else f'{n} minutes'} "
                          f"({time.time() - t0:.0f} s ; demandes acceptées {STATS['acceptees']}, refusées "
                          f"{STATS['refusees']}, pause {_pause:.1f} s)", flush=True)
        if not reste:
            break

def charger(sym: str) -> pd.DataFrame:
    """Toutes les minutes d'un symbole, avec l'heure de NEW YORK (colonne « ny », sans fuseau)."""
    fichiers = sorted((DOSSIER / sym).glob("*.csv"))
    df = pd.concat([pd.read_csv(f, parse_dates=["time"]) for f in fichiers], ignore_index=True)
    df = df.drop_duplicates("time").sort_values("time").reset_index(drop=True)
    df["time"] = df["time"].astype("datetime64[ns]")   # 16/10 (audit, défaut 1) : pandas 3 lit en µs ; projet en ns
    df["ny"] = df["time"].dt.tz_localize("UTC").dt.tz_convert("America/New_York").dt.tz_localize(None)
    df["ny"] = df["ny"].astype("datetime64[ns]")
    return df


if __name__ == "__main__":
    main()
