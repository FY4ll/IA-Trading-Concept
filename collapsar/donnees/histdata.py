"""Bougies d'UNE MINUTE du S&P 500 (SPXUSD) et du Nasdaq 100 (NSXUSD) depuis HistData.com (15/10/2026, piste
« ouverture de New York »). Dukascopy bridait trop (une demande acceptée toutes les ~2 minutes) ; HistData donne une
archive par année (une par mois pour l'année en cours) : ~25 demandes par marché.
Données : prix vendeur, à l'heure de NEW YORK heure d'été comprise (vérifié : voir charger).
Fichiers : data/minutes_histdata/<PAIRE>/<AAAA>[-MM].csv (brut). Lecture : charger(paire) -> colonnes ny, open, high,
low, close. Depuis Test_IA : venv_gpu\\Scripts\\python.exe -u -m collapsar.donnees.histdata [SPXUSD NSXUSD]
"""
from __future__ import annotations

import io
import re
import sys
import time
import zipfile
from datetime import date

import pandas as pd
import requests

from collapsar.donnees.marches import RACINE

DOSSIER = RACINE / "data" / "minutes_histdata"
PAGE = "https://www.histdata.com/download-free-forex-historical-data/?/ascii/1-minute-bar-quotes/{p}/{a}{m}"
GET = "https://www.histdata.com/get.php"
DEBUT = 2015


def _champ(html: str, nom: str) -> str | None:
    for motif in (rf'id="{nom}"[^>]*value="([^"]*)"', rf'name="{nom}"[^>]*value="([^"]*)"',
                  rf'value="([^"]*)"[^>]*id="{nom}"'):
        m = re.search(motif, html)
        if m:
            return m.group(1)
    return None


def telecharger(paire: str, annee: int, mois: int | None = None) -> pd.DataFrame | None:
    s = requests.Session()
    s.headers["User-Agent"] = "Mozilla/5.0"
    page = PAGE.format(p=paire.lower(), a=annee, m=f"/{mois}" if mois else "")
    html = s.get(page, timeout=60).text
    champs = {k: _champ(html, k) for k in ("tk", "date", "datemonth", "platform", "timeframe", "fxpair")}
    if not champs["tk"]:
        return None
    r = s.post(GET, data=champs, headers={"Referer": page}, timeout=300)
    if r.status_code != 200 or not r.content.startswith(b"PK"):
        return None
    z = zipfile.ZipFile(io.BytesIO(r.content))
    nom = next(n for n in z.namelist() if n.lower().endswith(".csv"))
    df = pd.read_csv(z.open(nom), sep=";", header=None, names=["t", "open", "high", "low", "close", "volume"])
    return df


def main():
    paires = sys.argv[1:] or ["SPXUSD", "NSXUSD"]
    aujourd_hui = date.today()
    for paire in paires:
        (DOSSIER / paire).mkdir(parents=True, exist_ok=True)
        lots = [(a, None) for a in range(DEBUT, aujourd_hui.year)] + \
               [(aujourd_hui.year, m) for m in range(1, aujourd_hui.month + 1)]
        for a, m in lots:
            f = DOSSIER / paire / (f"{a}.csv" if m is None else f"{a}-{m:02d}.csv")
            if f.exists() and not (a == aujourd_hui.year and m == aujourd_hui.month):
                continue
            df = None
            for essai in range(3):
                try:
                    df = telecharger(paire, a, m)
                    break
                except Exception as e:
                    print(f"  {paire} {a} {m or ''} : {type(e).__name__}, nouvel essai", flush=True)
                    time.sleep(20)
            if df is None:
                print(f"{paire} {a} {m or ''} : indisponible", flush=True)
                continue
            df.to_csv(f, index=False)
            print(f"{paire} {a} {m or ''} : {len(df)} minutes", flush=True)
            time.sleep(3)


def charger(paire: str) -> pd.DataFrame:
    fichiers = sorted((DOSSIER / paire).glob("*.csv"))
    df = pd.concat([pd.read_csv(f) for f in fichiers], ignore_index=True)
    # 15/10, VÉRIFIÉ sur nos données Dukascopy et sur le saut d'agitation de 9h30 : pour ces indices, les heures de
    # HistData sont DÉJÀ l'heure de New York, heure d'été comprise (et non « EST sans heure d'été » comme le dit leur
    # FAQ) ; convertie comme EST fixe, l'ouverture tombait à 10h30 en été. Accord avec Dukascopy : 98 % hiver comme été.
    df["ny"] = pd.to_datetime(df["t"].astype(str), format="%Y%m%d %H%M%S").astype("datetime64[ns]")  # 16/10 : µs -> ns
    return df.drop_duplicates("ny").sort_values("ny").reset_index(drop=True)[["ny", "open", "high", "low", "close"]]


if __name__ == "__main__":
    main()
