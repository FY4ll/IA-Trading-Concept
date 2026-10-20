"""Couche 1 -- historiques macro FRED (taux réels, dollar large, VIX, inflation anticipée), cache disque 6 h.
Repris de Run A (src/fred_feed.py::_fetch_history). La clé ne s'affiche jamais."""
from __future__ import annotations
import json
import logging
import os
import time

import pandas as pd

log = logging.getLogger("aurexis.fred")
HIST_START = "2009-01-01"
TTL_SECONDES = 6 * 3600
ENDPOINT = "https://api.stlouisfed.org/fred/series/observations"
CACHE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "cache")


class Fred:
    """Accès FRED (clé + dossier de cache)."""

    def __init__(self, cle: str, dossier_cache: str = CACHE):
        self.cle = cle or ""
        self.dossier_cache = dossier_cache
        self._prevenu = set()


def historique(fred: Fred, serie: str) -> pd.Series:
    """Historique complet d'une série FRED (pd.Series datée), relu du cache s'il a moins de 6 h."""
    chemin = os.path.join(fred.dossier_cache, f"fred_hist_{serie}.json")
    cache = None
    if os.path.exists(chemin):
        try:
            with open(chemin, encoding="utf-8") as f:
                cache = json.load(f)
        except (OSError, ValueError):
            cache = None
    if cache is not None and time.time() - cache.get("_fetched_at", 0) < TTL_SECONDES:
        obs = cache.get("observations", [])
    else:
        obs = cache.get("observations", []) if cache else []
        if fred.cle:
            try:
                import requests
                r = requests.get(ENDPOINT, params={"series_id": serie, "api_key": fred.cle,
                                                   "observation_start": HIST_START, "file_type": "json"}, timeout=30)
                r.raise_for_status()
                obs = [{"date": o["date"], "value": o["value"]} for o in r.json().get("observations", [])]
                os.makedirs(fred.dossier_cache, exist_ok=True)
                with open(chemin, "w", encoding="utf-8") as f:
                    json.dump({"_fetched_at": time.time(), "observations": obs}, f)
            except Exception as e:
                if serie not in fred._prevenu:
                    log.warning(f"Historique FRED {serie} indisponible ({type(e).__name__}) -> cache existant.")
                    fred._prevenu.add(serie)
    valeurs = {}
    for o in obs:
        try:
            valeurs[pd.Timestamp(o["date"])] = float(o["value"])
        except (TypeError, ValueError):
            continue
    return pd.Series(valeurs, dtype=float).sort_index()
