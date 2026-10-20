"""
Télécharge l'historique MINUTE gratuit de Dukascopy (banque suisse) pour combler les trous de données
intraday (05/10/2026) : les CSV locaux EURUSD/USDJPY M15 s'arrêtent en 2022-03 et MT5 ne remonte qu'à
2024. Agrège en M15, convertit en heure SERVEUR du broker (New York + 7 h, comme les bougies de l'or)
et écrit C:/Users/utilisateur/Documents/Test_IA/data/fx_intraday/<SYMBOLE>_M15.csv.

    python scripts/fetch_dukascopy.py [--start 2012-01-01] [--symbols EURUSD USDJPY USA500IDXUSD USTBONDTRUSD]

Reprise automatique : chaque mois terminé est gardé dans fx_intraday/raw/<SYMBOLE>/<AAAA-MM>.csv et n'est
pas retéléchargé (sauf le mois en cours). Serveur lent : 5 essais par jour, délai 60 s, 6 en parallèle.
"""
import argparse, lzma, os, struct, sys, time
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta

import pandas as pd
import requests

OUT = "C:/Users/utilisateur/Documents/Test_IA/data/fx_intraday"
POINT = {"EURUSD": 1e-5, "USDJPY": 1e-3, "XAUUSD": 1e-3, "AUDUSD": 1e-5, "USDCHF": 1e-5, "XAGUSD": 1e-3,
         "BTCUSD": 1e-1, "USA30IDXUSD": 1e-3, "DEUIDXEUR": 1e-3}   # 08/10 : vérifiés sur des prix connus (2024-03-05)
# 08/10 soir : marchés FTMO (sonde du 05/03/2024) -- devises hors yen 5 décimales, paires en yen 3, indices/pétrole 3,
# gaz 4, éther/litecoin 1, ripple 3.
for _s in ("USDCAD", "NZDUSD", "EURGBP", "EURCHF", "EURAUD", "EURCAD", "EURNZD", "GBPCHF", "GBPAUD", "GBPCAD", "GBPNZD",
           "AUDCHF", "AUDCAD", "AUDNZD", "NZDCHF", "NZDCAD", "CADCHF", "GBPUSD"):
    POINT[_s] = 1e-5
for _s in ("EURJPY", "GBPJPY", "AUDJPY", "NZDJPY", "CADJPY", "CHFJPY", "USATECHIDXUSD", "GBRIDXGBP", "FRAIDXEUR",
           "EUSIDXEUR", "JPNIDXJPY", "AUSIDXAUD", "LIGHTCMDUSD", "BRENTCMDUSD", "XRPUSD"):
    POINT[_s] = 1e-3
POINT.update({"GASCMDUSD": 1e-4, "ETHUSD": 1e-1, "LTCUSD": 1e-1})
_session = requests.Session()
_session.headers["User-Agent"] = "Mozilla/5.0"


FAILED = "FAILED"


def fetch_day(sym: str, d: date, tries: int = 6, base_wait: float = 10.0):
    """DataFrame M1 du jour, None si pas de cotation ce jour-là, FAILED si le serveur a refusé."""
    url = f"https://datafeed.dukascopy.com/datafeed/{sym}/{d.year:04d}/{d.month - 1:02d}/{d.day:02d}/BID_candles_min_1.bi5"
    last = None
    for k in range(tries):
        try:
            r = _session.get(url, timeout=60)
            if r.status_code == 404:
                return None
            if r.status_code != 200:
                raise IOError(f"HTTP {r.status_code}")
            if not r.content:
                return None
            raw = lzma.decompress(r.content)
            n = len(raw) // 24
            recs = [struct.unpack(">5if", raw[i * 24:(i + 1) * 24]) for i in range(n)]
            p = POINT.get(sym, 1e-3)
            df = pd.DataFrame(recs, columns=["sec", "open", "close", "low", "high", "volume"])
            df = df[df["volume"] > 0]                      # minutes sans transaction = remplissage plat
            if df.empty:
                return None
            df["time"] = pd.Timestamp(d) + pd.to_timedelta(df["sec"], unit="s")
            for c in ("open", "close", "low", "high"):
                df[c] = df[c] * p
            return df[["time", "open", "high", "low", "close", "volume"]]
        except Exception as e:
            time.sleep(base_wait * (k + 1))     # serveur saturé (503) : on attend de plus en plus
            last = e
    print(f"  ! {sym} {d} refusé après {tries} essais ({last}) -- sera retenté", flush=True)
    return FAILED


def to_m15(m1: pd.DataFrame) -> pd.DataFrame:
    g = m1.set_index("time").resample("15min", label="left", closed="left")
    return g.agg({"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}).dropna().reset_index()


def utc_to_server(t: pd.Series) -> pd.Series:
    return (pd.to_datetime(t).dt.tz_localize("UTC").dt.tz_convert("America/New_York").dt.tz_localize(None)
            + pd.Timedelta(hours=7))


def fetch_month(sym: str, y: int, m: int, today: date) -> pd.DataFrame:
    raw_dir = os.path.join(OUT, "raw", sym)
    os.makedirs(raw_dir, exist_ok=True)
    path = os.path.join(raw_dir, f"{y:04d}-{m:02d}.csv")
    current = (y, m) == (today.year, today.month)
    if os.path.exists(path) and not current:
        return pd.read_csv(path, parse_dates=["time"])
    d0 = date(y, m, 1)
    days = [d0 + timedelta(days=i) for i in range(31) if (d0 + timedelta(days=i)).month == m
            and d0 + timedelta(days=i) <= today and (d0 + timedelta(days=i)).weekday() != 5]
    with ThreadPoolExecutor(max_workers=4) as ex:
        results = list(ex.map(lambda d: fetch_day(sym, d), days))
    # passe de rattrapage : jours refusés retentés un par un, avec des attentes longues
    for rnd in range(3):
        failed = [i for i, r in enumerate(results) if isinstance(r, str)]
        if not failed:
            break
        time.sleep(30)
        for i in failed:
            results[i] = fetch_day(sym, days[i], tries=4, base_wait=20.0)
    missing = [str(days[i]) for i, r in enumerate(results) if isinstance(r, str)]
    parts = [p for p in results if isinstance(p, pd.DataFrame)]
    m15 = to_m15(pd.concat(parts)) if parts else pd.DataFrame(columns=["time", "open", "high", "low", "close", "volume"])
    if missing:
        print(f"  !! {sym} {y}-{m:02d} : jours toujours manquants {missing} -- mois NON figé, retenté au prochain lancement", flush=True)
        return m15                                      # pas de fichier mensuel : le mois sera repris
    m15.to_csv(path, index=False)                      # heure UTC dans les fichiers bruts mensuels
    return m15


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="2012-01-01")
    ap.add_argument("--symbols", nargs="+", default=["EURUSD", "USDJPY", "USA500IDXUSD", "USTBONDTRUSD"])
    ap.add_argument("--end", default=None, help="dernier jour (défaut : aujourd'hui)")
    args = ap.parse_args()
    today = pd.Timestamp(args.end).date() if args.end else date.today()
    start = pd.Timestamp(args.start).date()
    for sym in args.symbols:
        t0 = time.time()
        months, y, m = [], start.year, start.month
        while (y, m) <= (today.year, today.month):
            months.append((y, m))
            y, m = (y + 1, 1) if m == 12 else (y, m + 1)
        frames = []
        for (y, m) in months:
            f = fetch_month(sym, y, m, today)
            frames.append(f)
            print(f"{sym} {y}-{m:02d} : {len(f)} bougies M15 ({(time.time() - t0) / 60:.1f} min)", flush=True)
        allm = pd.concat([f for f in frames if len(f)]).drop_duplicates("time").sort_values("time")
        allm["time"] = utc_to_server(allm["time"])
        os.makedirs(OUT, exist_ok=True)
        allm.to_csv(os.path.join(OUT, f"{sym}_M15.csv"), index=False)
        print(f"== {sym} : {len(allm)} bougies M15 de {allm['time'].min()} à {allm['time'].max()} (heure serveur)", flush=True)


if __name__ == "__main__":
    sys.exit(main())
