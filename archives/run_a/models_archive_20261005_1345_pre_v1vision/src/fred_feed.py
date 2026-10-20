"""
fred_feed.py
=============
Intègre l'API FRED (Federal Reserve Economic Data,
https://fred.stlouisfed.org/docs/api/fred) pour remplacer le calendrier
économique (`fundamental_feed.py::refresh_economic_calendar`) qui ne
retournait jamais que du zéro en production, comme signal fondamental.

Récupère 7 séries journalières pertinentes pour l'or (XAUUSD) :
  - DFII10   : taux réel 10 ans (TIPS) -- le plus corrélé à l'or
  - DGS10    : Treasury nominal 10 ans
  - FEDFUNDS : taux directeur de la Fed
  - DTWEXBGS : indice Dollar (large, pondéré échanges)
  - CPIAUCSL : indice des prix à la consommation (CPI)
  - VIXCLS   : indice de volatilité (VIX)
  - T10YIE   : point mort d'inflation 10 ans (breakeven)

Chaque série est mise en cache localement (data/cache/fred_{series_id}.json)
avec un TTL de 1h -- les séries FRED sont publiées au plus quotidiennement,
inutile de re-télécharger plus souvent.

Clé API lue depuis config/autonomous.yaml -> fred.api_key. Si absente ou si
la requête échoue, retombe sur un score neutre (0.0), même pattern que les
autres sources de fundamental_feed.py : le pipeline ne doit JAMAIS
s'interrompre pour une source indisponible.
"""
from __future__ import annotations
import os
import json
import time
import logging

import numpy as np

from src.io_utils import JsonCacheMixin

log = logging.getLogger("fred_feed")

CACHE_DIR = "data/cache"
CACHE_TTL_SECONDS = 3600  # 1h -- séries FRED journalières, pas besoin de plus fréquent

FRED_SERIES = ["DFII10", "DGS10", "FEDFUNDS", "DTWEXBGS", "CPIAUCSL", "VIXCLS", "T10YIE"]

FRED_ENDPOINT = "https://api.stlouisfed.org/fred/series/observations"

# Poids de chaque série dans la moyenne pondérée du score final. Seules les
# séries avec un signal directionnel clair pour l'or sont pondérées ;
# DGS10/CPIAUCSL sont récupérées (contexte utile / réutilisation future) mais
# n'entrent pas dans le score pour l'instant, faute de règle directionnelle
# simple et fiable demandée.
_SIGNAL_WEIGHTS = {
    "DFII10": 0.35,     # taux réel bas/négatif -> bullish or
    "DTWEXBGS": 0.25,   # dollar faible -> bullish or
    "VIXCLS": 0.20,     # VIX en hausse (risk-off) -> bullish or
    "T10YIE": 0.15,     # inflation anticipée en hausse -> bullish or
    "FEDFUNDS": 0.05,   # taux Fed en baisse -> bullish or
}


def _cache_path(series_id: str) -> str:
    return os.path.join(CACHE_DIR, f"fred_{series_id}.json")


class FredFeed(JsonCacheMixin):
    def __init__(self, cfg: dict):
        self.cfg = cfg.get("fred", {})
        os.makedirs(CACHE_DIR, exist_ok=True)
        self._warned = set()
        self._log = log  # voir src/io_utils.py::JsonCacheMixin

    def _api_key(self) -> str:
        return self.cfg.get("api_key", "") or ""

    # ---------------- Fetch + cache d'une série ---------------- #
    def fetch_series(self, series_id: str) -> list[dict]:
        """Retourne les observations `[{"date": ..., "value": ...}, ...]` de
        `series_id`, en repartant du cache local si sa dernière écriture a
        moins de `CACHE_TTL_SECONDS`, sinon en re-téléchargeant depuis FRED."""
        cache_path = _cache_path(series_id)
        # default=None (comportement d'origine, PAS {} comme
        # AutoFundamentalFeed -- voir JsonCacheMixin) : distingue "aucun
        # cache" (None) de "cache présent mais vide", testé juste en dessous.
        cached = self._load_cache(cache_path, default=None)
        if cached is not None and time.time() - cached.get("_fetched_at", 0) < CACHE_TTL_SECONDS:
            return cached.get("observations", [])

        api_key = self._api_key()
        if not api_key:
            self._warn_once("no_api_key", "Aucune clé FRED configurée (fred.api_key dans config/autonomous.yaml)",
                             suffix=" -> score neutre utilisé en remplacement.")
            return cached.get("observations", []) if cached else []

        try:
            import requests
        except ImportError:
            self._warn_once("requests_missing", "`requests` non installé.",
                             suffix=" -> score neutre utilisé en remplacement.")
            return cached.get("observations", []) if cached else []

        import datetime
        observation_start = (datetime.date.today() - datetime.timedelta(days=30)).isoformat()
        params = {
            "series_id": series_id,
            "api_key": api_key,
            "observation_start": observation_start,
            "file_type": "json",
        }
        try:
            resp = requests.get(FRED_ENDPOINT, params=params, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            observations = [
                {"date": o["date"], "value": o["value"]}
                for o in data.get("observations", [])
            ]
        except Exception as e:
            self._warn_once(f"fetch_{series_id}", f"Série FRED {series_id} indisponible : {e}",
                             suffix=" -> score neutre utilisé en remplacement.")
            return cached.get("observations", []) if cached else []

        self._save_cache(cache_path, {"_fetched_at": time.time(), "observations": observations})
        return observations

    # _load_cache/_save_cache/_warn_once : voir src/io_utils.py::JsonCacheMixin
    # (factorisés, auparavant dupliqués ici et dans src/fundamental_feed.py).

    # ---------------- Score fondamental ---------------- #
    def compute_fred_score(self) -> float:
        """Calcule un score entre -1.0 (bearish or) et +1.0 (bullish or) à
        partir des 7 séries FRED. Pas de clé API configurée (ou toutes les
        séries indisponibles) -> score neutre 0.0, comme les autres sources
        de fundamental_feed.py.

        Chaque signal est normalisé via un z-score sur les observations
        disponibles en cache (jusqu'aux 20 dernières), puis les signaux sont
        combinés en moyenne pondérée (`_SIGNAL_WEIGHTS`). Un z-score positif
        signifie "dernière valeur au-dessus de sa moyenne récente" -- le
        signe de sa contribution au score dépend du sens bullish/bearish de
        la série (voir `_signal_direction`).
        """
        if not self._api_key():
            return 0.0

        weighted_sum = 0.0
        total_weight = 0.0
        for series_id, weight in _SIGNAL_WEIGHTS.items():
            observations = self.fetch_series(series_id)
            z = _zscore_last(observations)
            if z is None:
                continue
            weighted_sum += weight * _signal_direction(series_id) * z
            total_weight += weight

        if total_weight == 0.0:
            return 0.0

        score = weighted_sum / total_weight
        return float(np.clip(score, -1.0, 1.0))


HIST_START = "2009-01-01"
HIST_TTL_SECONDS = 6 * 3600


def _fetch_history(feed: "FredFeed", series_id: str):
    """Historique complet d'une série FRED (pd.Series datée), cache disque 6 h."""
    import pandas as pd
    path = os.path.join(CACHE_DIR, f"fred_hist_{series_id}.json")
    cached = feed._load_cache(path, default=None)
    if cached is not None and time.time() - cached.get("_fetched_at", 0) < HIST_TTL_SECONDS:
        obs = cached.get("observations", [])
    else:
        obs = cached.get("observations", []) if cached else []
        key = feed._api_key()
        if key:
            try:
                import requests
                resp = requests.get(FRED_ENDPOINT, params={
                    "series_id": series_id, "api_key": key,
                    "observation_start": HIST_START, "file_type": "json"}, timeout=30)
                resp.raise_for_status()
                obs = [{"date": o["date"], "value": o["value"]}
                       for o in resp.json().get("observations", [])]
                feed._save_cache(path, {"_fetched_at": time.time(), "observations": obs})
            except Exception as e:
                feed._warn_once(f"hist_{series_id}", f"Historique FRED {series_id} indisponible : {e}",
                                suffix=" -> cache existant ou score neutre.")
    vals = {}
    for o in obs:
        try:
            vals[pd.Timestamp(o["date"])] = float(o["value"])
        except (TypeError, ValueError):
            continue
    return pd.Series(vals, dtype=float).sort_index()


def macro_score_series(feed: "FredFeed", window: int = 20):
    """Score macro quotidien POINT-IN-TIME (-1 bearish or .. +1 bullish or) sur
    tout l'historique : même formule que `compute_fred_score` (z-score des
    `window` dernières observations, pondéré par `_SIGNAL_WEIGHTS`), mais
    calculé à chaque date avec la valeur publiée la veille (décalage d'1 jour,
    pas de fuite du futur). Utilisé à l'identique en entraînement et en démo."""
    import pandas as pd
    days = pd.date_range(HIST_START, pd.Timestamp.today().normalize() + pd.Timedelta(days=1), freq="D")
    total = pd.Series(0.0, index=days)
    wsum = pd.Series(0.0, index=days)
    for series_id, weight in _SIGNAL_WEIGHTS.items():
        s = _fetch_history(feed, series_id)
        if len(s) < 3:
            continue
        roll = s.rolling(window, min_periods=2)
        z = ((s - roll.mean()) / roll.std(ddof=0)).replace([np.inf, -np.inf], np.nan)
        zd = z.reindex(days).ffill().shift(1)
        ok = zd.notna()
        total[ok] += weight * _signal_direction(series_id) * zd[ok]
        wsum[ok] += weight
    return (total / wsum.replace(0, np.nan)).clip(-1.0, 1.0)


def _signal_direction(series_id: str) -> float:
    """+1 si une valeur AU-DESSUS de sa moyenne récente est bullish pour
    l'or, -1 si c'est une valeur EN DESSOUS qui est bullish."""
    # DFII10 bas/négatif -> bullish : une valeur au-dessus de la moyenne est donc bearish (-1)
    # DTWEXBGS en baisse -> bullish : au-dessus de la moyenne = bearish (-1)
    # VIXCLS en hausse -> bullish : au-dessus de la moyenne = bullish (+1)
    # T10YIE en hausse -> bullish : au-dessus de la moyenne = bullish (+1)
    # FEDFUNDS en baisse -> bullish : au-dessus de la moyenne = bearish (-1)
    return {
        "DFII10": -1.0,
        "DTWEXBGS": -1.0,
        "VIXCLS": 1.0,
        "T10YIE": 1.0,
        "FEDFUNDS": -1.0,
    }.get(series_id, 0.0)


def _zscore_last(observations: list[dict], window: int = 20) -> float | None:
    """z-score de la dernière valeur numérique par rapport aux `window`
    précédentes observations disponibles (elles-mêmes incluses). None si
    moins de 2 valeurs numériques exploitables (FRED encode les valeurs
    manquantes avec ".") ou si l'échantillon est constant (écart-type nul)."""
    values = []
    for o in observations[-window:]:
        v = o.get("value")
        try:
            values.append(float(v))
        except (TypeError, ValueError):
            continue
    if len(values) < 2:
        return None
    arr = np.array(values)
    std = arr.std()
    if std == 0:
        return None
    return float((arr[-1] - arr.mean()) / std)
