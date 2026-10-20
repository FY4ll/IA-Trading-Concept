"""
live_data_feed.py
===================
Empêche l'IA de STAGNER une fois connectée à MT5 : sans ce module, le
dataset d'entraînement (les CSV de `data.folder`) reste GELÉ à la date où
il a été téléchargé, et la boucle d'évolution continue (voir
continuous_trainer.py) réapprend indéfiniment sur le MÊME passé -- de plus
en plus loin du marché réel au fil du temps. Ce n'est pas hypothétique :
sur le dataset XAUUSD fourni, l'écart avec la date du jour est déjà de
plusieurs mois avant même le premier lancement.

Ce module récupère PÉRIODIQUEMENT les bougies récentes depuis MT5 (via le
connecteur DÉJÀ connecté et partagé avec demo_trader.py -- jamais une
deuxième connexion) et les AJOUTE aux CSV existants -- ne réécrit et ne
supprime JAMAIS une ligne déjà présente, uniquement des lignes strictement
plus récentes que la dernière connue.

COMBLEMENT DE TROU : si l'écart entre la dernière bougie connue et
maintenant dépasse quelques bougies (cas normal au premier lancement,
voire des mois -- voir la docstring du module), un simple "dernières N
bougies" laisserait un TROU dans l'historique (les bougies entre l'ancien
dataset et le nouveau seraient silencieusement absentes, faussant tout
indicateur à fenêtre glissante calculé autour de cette coupure). Ce module
détecte le trou et bascule sur `MT5Connector.get_bars_range()` -- une
requête par PLAGE DE DATES, pas par nombre de bougies -- pour le combler
exactement, un rafraîchissement à la fois si nécessaire (MT5 peut limiter
la taille d'une seule requête sur les timeframes fines).
"""
from __future__ import annotations
import os
import json
import logging
import time
import pandas as pd

from src.data_loader import load_kaggle_ohlcv_csv
from src.multi_timeframe import TIMEFRAME_MINUTES

log = logging.getLogger("live_data_feed")

SPREAD_CACHE_PATH = os.path.join("data", "cache", "live_spread.json")
MARKET_STATUS_CACHE_PATH = os.path.join("data", "cache", "market_status.json")


def read_cached_market_status(max_age_hours: float = 1.0) -> bool | None:
    """Relit le statut de marché (ouvert/fermé) mis en cache par
    `LiveDataFeed` (voir `_refresh_market_status` ci-dessous), basé sur la
    fraîcheur RÉELLE des cotations MT5 -- pas une heure de session
    déclarée dans la config. Retourne None si absent ou trop ancien (l'appelant
    retombe alors sur `market_hours` dans la config)."""
    if not os.path.exists(MARKET_STATUS_CACHE_PATH):
        return None
    try:
        with open(MARKET_STATUS_CACHE_PATH, encoding="utf-8") as f:
            data = json.load(f)
        age_hours = (time.time() - data.get("checked_at", 0)) / 3600.0
        if age_hours > max_age_hours:
            return None
        return bool(data["is_open"])
    except Exception:
        return None


def read_cached_spread(max_age_hours: float = 6.0) -> float | None:
    """Relit le spread réel mis en cache par `LiveDataFeed` (voir
    `_refresh_spread` ci-dessous), utilisé par continuous_trainer.py pour
    calibrer le coût de transaction de l'entraînement sur une MESURE
    récente plutôt qu'une valeur devinée dans la config. Retourne None si
    absent ou trop ancien -- l'appelant retombe alors sur la config."""
    if not os.path.exists(SPREAD_CACHE_PATH):
        return None
    try:
        with open(SPREAD_CACHE_PATH, encoding="utf-8") as f:
            data = json.load(f)
        age_hours = (time.time() - data.get("updated_at", 0)) / 3600.0
        if age_hours > max_age_hours:
            return None
        return float(data["spread_pct"])
    except Exception:
        return None


def _detect_format(path: str) -> dict:
    """Devine le séparateur et les noms de colonnes à partir de l'EN-TÊTE
    seulement (pas besoin de charger tout le fichier, potentiellement
    plusieurs centaines de Mo pour les timeframes fines)."""
    with open(path, encoding="utf-8", errors="ignore") as f:
        header = f.readline().strip()
    for sep in [";", ",", "\t"]:
        if sep in header:
            return {"sep": sep, "columns": [c.strip() for c in header.split(sep)]}
    return {"sep": ",", "columns": [c.strip() for c in header.split(",")]}


def read_last_bar_time(path: str, fmt: dict | None = None) -> pd.Timestamp | None:
    """Lit UNIQUEMENT la fin du fichier (pas tout le fichier -- certains CSV
    Kaggle font plusieurs centaines de Mo) pour connaître le dernier
    horodatage déjà présent, sans le coût d'un chargement complet à chaque
    rafraîchissement."""
    fmt = fmt or _detect_format(path)
    with open(path, "rb") as f:
        f.seek(0, os.SEEK_END)
        size = f.tell()
        chunk = min(8192, size)
        f.seek(max(0, size - chunk))
        tail = f.read(chunk)
    lines = [ln for ln in tail.decode("utf-8", errors="ignore").splitlines() if ln.strip()]
    if not lines:
        return None
    parts = lines[-1].split(fmt["sep"])
    cols = [c.lower() for c in fmt["columns"]]
    if len(parts) != len(cols):
        return None  # ligne tronquée (lecture en plein milieu) -> on retente au prochain passage
    row = dict(zip(cols, parts))
    try:
        if "date" in row and "time" in row and row.get("time"):
            return pd.to_datetime(row["date"].replace(".", "-") + " " + row["time"], errors="coerce")
        if "date" in row:
            return pd.to_datetime(row["date"].replace(".", "-"), errors="coerce")
        if "datetime" in row:
            return pd.to_datetime(row["datetime"], errors="coerce")
    except Exception:
        pass
    return None


def append_new_bars(path: str, new_bars: pd.DataFrame, last_time: pd.Timestamp | None = None) -> int:
    """Ajoute à `path` les lignes de `new_bars` (colonnes time/open/high/
    low/close/volume) dont l'horodatage est STRICTEMENT postérieur à
    `last_time` (déjà connu par l'appelant -- évite de relire le fichier).
    Ne modifie/ne supprime JAMAIS une ligne existante. Retourne le nombre
    de lignes effectivement ajoutées.
    """
    if new_bars is None or new_bars.empty:
        return 0

    to_add = new_bars if last_time is None else new_bars[new_bars["time"] > last_time]
    to_add = to_add.sort_values("time")
    if to_add.empty:
        return 0

    valid_mask = (
        (to_add["open"] > 0) & (to_add["high"] > 0) & (to_add["low"] > 0) & (to_add["close"] > 0)
        & (to_add["high"] >= to_add["low"]) & (to_add["volume"] >= 0)
    )
    n_invalid = int((~valid_mask).sum())
    if n_invalid:
        log.warning(f"[live_data_feed] {n_invalid} bougie(s) invalide(s) reçue(s) de MT5 pour '{path}' "
                    f"(OHLCV <= 0, high < low, ou volume < 0) -> ignorée(s).")
    to_add = to_add[valid_mask]
    if to_add.empty:
        return 0

    fmt = _detect_format(path)
    sep, cols = fmt["sep"], fmt["columns"]

    rows = []
    for _, r in to_add.iterrows():
        row = {}
        for col in cols:
            lower = col.lower()
            if lower == "date":
                row[col] = r["time"].strftime("%Y.%m.%d %H:%M")
            elif lower == "time":
                row[col] = r["time"].strftime("%H:%M:%S")
            elif lower == "open":
                row[col] = r["open"]
            elif lower == "high":
                row[col] = r["high"]
            elif lower == "low":
                row[col] = r["low"]
            elif lower == "close":
                row[col] = r["close"]
            elif lower in ("volume", "vol", "tick_volume", "tickvol"):
                row[col] = r["volume"]
            else:
                row[col] = ""
        rows.append(row)

    pd.DataFrame(rows, columns=cols).to_csv(path, sep=sep, mode="a", header=False, index=False)
    return len(rows)


class LiveDataFeed:
    """Boucle en arrière-plan : récupère périodiquement les bougies
    manquantes de chaque timeframe du pool via un connecteur MT5 DÉJÀ
    connecté (partagé avec demo_trader.py) et les ajoute aux CSV de
    `data.folder`, en comblant proprement tout trou détecté. Ne fait RIEN
    d'autre -- la détection de fichier modifié, déjà présente dans
    autonomous_agent.py, se charge de faire réapprendre le système sur ces
    données fraîches au cycle suivant."""

    def __init__(self, cfg: dict, connector, files: dict):
        self.connector = connector
        self.files = files
        data_cfg = cfg.get("data", {})
        self.refresh_minutes = data_cfg.get("live_feed_refresh_minutes", 30)
        self.n_bars_fetch = data_cfg.get("live_feed_n_bars", 500)
        # Plafond de bougies demandées en UNE requête par plage de dates
        # lors d'un comblement de trou -- un trou de plusieurs mois en M1
        # représente des centaines de milliers de bougies ; mieux vaut le
        # combler en plusieurs rafraîchissements successifs (chacun plafonné
        # ici) que de risquer une requête énorme ou lente d'un coup.
        self.max_backfill_bars = data_cfg.get("live_feed_max_backfill_bars", 50000)
        self._stop = False

    def stop(self):
        self._stop = True

    def run_forever(self):
        while not self._stop:
            self.refresh_once()
            for _ in range(max(1, self.refresh_minutes) * 60):
                if self._stop:
                    break
                time.sleep(1)

    def refresh_once(self):
        now = pd.Timestamp.now()
        for tf, path in self.files.items():
            try:
                fmt = _detect_format(path)
                last_time = read_last_bar_time(path, fmt)
                tf_minutes = TIMEFRAME_MINUTES.get(tf, 60)
                gap_bars = ((now - last_time).total_seconds() / 60.0 / tf_minutes) if last_time is not None else 0

                if last_time is not None and gap_bars > self.n_bars_fetch:
                    # TROU détecté : "dernières N bougies" laisserait un vide
                    # entre l'ancien historique et les données récupérées ici
                    # -- on demande la PLAGE DE DATES manquante à la place.
                    date_to = min(now, last_time + pd.Timedelta(minutes=tf_minutes * self.max_backfill_bars))
                    bars = self.connector.get_bars_range(tf, last_time, date_to)
                    added = append_new_bars(path, bars, last_time=last_time)
                    remaining = int(gap_bars - added)
                    if added:
                        log.info(f"[live_data_feed] Comblement de trou '{tf}' : {added} bougie(s) ajoutée(s) "
                                 f"({remaining} restantes si trou plus large, comblées aux prochains "
                                 f"rafraîchissements) -> {path}.")
                    else:
                        log.warning(f"[live_data_feed] Trou détecté sur '{tf}' (~{int(gap_bars)} bougies "
                                    f"manquantes depuis {last_time}) mais MT5 n'a rien retourné sur cette "
                                    f"plage -- retenté au prochain rafraîchissement.")
                else:
                    bars = self.connector.get_latest_bars(tf, self.n_bars_fetch)
                    added = append_new_bars(path, bars, last_time=last_time)
                    if added:
                        log.info(f"[live_data_feed] {added} nouvelle(s) bougie(s) '{tf}' ajoutée(s) à {path} "
                                 f"-> pris en compte par l'évolution continue au prochain cycle.")
            except Exception as e:
                log.warning(f"[live_data_feed] Échec de mise à jour '{tf}' depuis MT5 "
                            f"({type(e).__name__}: {e}) -> ignoré, retenté au prochain rafraîchissement.")

        self._refresh_spread()
        self._refresh_market_status()

    def _refresh_market_status(self):
        """Détecte si le marché est actuellement actif via la fraîcheur
        RÉELLE des cotations MT5 (voir MT5Connector.is_symbol_active) et le
        met en cache -- utilisé par market_hours.py (entraînement) ET
        demo_trader.py (pause propre en démo) à la place d'une simple
        estimation d'horaire dans la config. Échec silencieux (log
        seulement) : ne doit jamais interrompre l'alimentation des
        données."""
        try:
            is_open = self.connector.is_symbol_active()
            os.makedirs(os.path.dirname(MARKET_STATUS_CACHE_PATH), exist_ok=True)
            with open(MARKET_STATUS_CACHE_PATH, "w", encoding="utf-8") as f:
                json.dump({"is_open": is_open, "checked_at": time.time()}, f, indent=2)
            log.info(f"[live_data_feed] Marché détecté {'OUVERT' if is_open else 'FERMÉ'} "
                     f"(fraîcheur des cotations MT5 réelles).")
        except Exception as e:
            log.warning(f"[live_data_feed] Impossible de vérifier l'activité du marché "
                        f"({type(e).__name__}: {e}) -> retombe sur market_hours configuré.")

    def _refresh_spread(self):
        """Mesure le spread RÉEL actuel (voir MT5Connector.get_current_spread_pct)
        et le met en cache pour continuous_trainer.py -- calibre le coût de
        transaction de l'entraînement sur ce que ça coûte VRAIMENT de
        trader aujourd'hui chez votre broker, au lieu d'une valeur devinée
        dans la config. Échec silencieux (log seulement) : un spread
        introuvable ne doit jamais interrompre l'alimentation des données."""
        try:
            spread_pct = self.connector.get_current_spread_pct()
            os.makedirs(os.path.dirname(SPREAD_CACHE_PATH), exist_ok=True)
            with open(SPREAD_CACHE_PATH, "w", encoding="utf-8") as f:
                json.dump({"spread_pct": spread_pct, "updated_at": time.time()}, f, indent=2)
            log.info(f"[live_data_feed] Spread réel mesuré : {spread_pct:.4%} -- "
                     f"utilisé comme coût de transaction de référence par l'évolution continue.")
        except Exception as e:
            log.warning(f"[live_data_feed] Impossible de mesurer le spread réel "
                        f"({type(e).__name__}: {e}) -> l'entraînement retombe sur "
                        f"environment.transaction_cost configuré.")
