"""Lecteur EN DIRECT (lecture seule, sans clé) de la position de la foule sur les contrats perpétuels Binance.

Source : API publique Binance « futures/data » (aucun compte, aucune clé), vérifiée le 16/10/2026 :
- comptes   : https://fapi.binance.com/futures/data/globalLongShortAccountRatio  (part des COMPTES acheteurs / vendeurs,
              = colonne count_long_short_ratio des fichiers « metrics » ; c'est l'information de la variante C1)
- top       : .../futures/data/topLongShortPositionRatio  (positions des gros traders)
- positions : .../futures/data/openInterestHist             (positions ouvertes)
Intervalles : 5m, 15m, 30m, 1h, 2h, 4h, 6h, 12h, 1d ; au plus 500 lignes par appel ; SEULEMENT LES 30 DERNIERS JOURS
(au-delà : fichiers journaliers data.binance.vision, voir data/binance_futures/LISEZMOI.md).

Heures (mesuré le 16/10/2026 sur BTC, ETH, SOL) :
- la ligne d'horodatage T (UTC) est publiée de 20 s à environ 5 min après T (sondages : 18 s, 23 s, 77 s, 140 s,
  et une valeur encore absente 5 min 33 s après) -> la colonne `connu_a` = T + 5 min (prudent) ;
- la même valeur figure dans les fichiers journaliers à l'heure T - 5 min (create_time) : fichier(T - 5 min) = API(T)
  à 0,0001 près (l'API arrondit à 4 décimales). La piste crypto_flux utilise le fichier avec 15 min de retard, soit
  l'équivalent de API(T) utilisée à T + 10 min : le direct (T + 5 min au plus tard) reste plus rapide.
- la valeur « 1h » d'horodatage T est exactement la valeur « 5m » de même horodatage.

Usage : from collapsar.donnees import binance_foule as bf ; bf.lire("BTCUSDT", "1h", 200)
        python -m collapsar.donnees.binance_foule BTCUSDT  (affiche les dernières valeurs)
"""
from __future__ import annotations

import sys

import numpy as np
import pandas as pd
import requests

BASE = "https://fapi.binance.com/futures/data/"
ROUTES = {"comptes": "globalLongShortAccountRatio", "top": "topLongShortPositionRatio",
          "positions": "openInterestHist"}
PERIODES = ("5m", "15m", "30m", "1h", "2h", "4h", "6h", "12h", "1d")
RETARD_PUBLICATION = pd.Timedelta(minutes=5)


def serveur(utc: pd.Series) -> pd.Series:
    """UTC -> heure du serveur MetaTrader (New York + 7 h), comme le reste du projet."""
    return (pd.DatetimeIndex(utc).tz_localize("UTC").tz_convert("America/New_York").tz_localize(None)
            + pd.Timedelta(hours=7)).to_series(index=utc.index)


def lire(symbole: str = "BTCUSDT", periode: str = "1h", limite: int = 500, quoi: str = "comptes",
         debut: pd.Timestamp | None = None, fin: pd.Timestamp | None = None, delai: float = 20.0) -> pd.DataFrame:
    """Dernières valeurs (au plus 500, 30 derniers jours). Colonnes : utc (horodatage Binance), time (serveur),
    connu_a (utc + 5 min), et selon `quoi` : part_acheteurs, part_vendeurs, ratio (comptes, top) ou positions,
    positions_usdt (positions)."""
    if periode not in PERIODES:
        raise ValueError(f"période {periode} : choisir parmi {PERIODES}")
    p = {"symbol": symbole, "period": periode, "limit": int(min(max(limite, 1), 500))}
    if debut is not None:
        p["startTime"] = int(pd.Timestamp(debut).value // 10 ** 6)
    if fin is not None:
        p["endTime"] = int(pd.Timestamp(fin).value // 10 ** 6)
    r = requests.get(BASE + ROUTES[quoi], params=p, timeout=delai)
    r.raise_for_status()
    j = r.json()
    if isinstance(j, dict):                                  # message d'erreur de Binance
        raise RuntimeError(f"Binance : {j}")
    d = pd.DataFrame(j)
    if d.empty:
        return d
    out = pd.DataFrame({"utc": pd.to_datetime(d["timestamp"].astype("int64"), unit="ms")})
    if quoi == "positions":
        out["positions"] = d["sumOpenInterest"].astype(float)
        out["positions_usdt"] = d["sumOpenInterestValue"].astype(float)
    else:
        out["part_acheteurs"] = d["longAccount"].astype(float)
        out["part_vendeurs"] = d["shortAccount"].astype(float)
        out["ratio"] = d["longShortRatio"].astype(float)
    out = out.sort_values("utc").reset_index(drop=True)
    out.insert(1, "time", serveur(out["utc"]).to_numpy())
    out.insert(2, "connu_a", out["utc"] + RETARD_PUBLICATION)
    return out


def derniere(symbole: str = "BTCUSDT", quoi: str = "comptes") -> dict:
    """Dernière valeur publiée (intervalle 5 min) et son âge en secondes."""
    d = lire(symbole, "5m", 1, quoi)
    x = d.iloc[-1].to_dict()
    x["age_s"] = float((pd.Timestamp.now("UTC").tz_localize(None) - x["utc"]).total_seconds())
    return x


if __name__ == "__main__":
    s = sys.argv[1] if len(sys.argv) > 1 else "BTCUSDT"
    print(lire(s, "1h", 5).to_string())
    print(derniere(s))
