"""
market_hours.py
================
Détection des heures de marché XAUUSD -- suit les sessions Forex (fermé du
vendredi soir à dimanche soir, heure UTC). Utilisé pour adapter
automatiquement le volume de données d'entraînement : pendant la fermeture
du marché (week-end), rien ne presse et aucune décision de trading en
direct ne sollicite le CPU -- le système peut alors se permettre d'apprendre
sur BEAUCOUP plus d'historique d'un coup (voir data.max_bars_market_closed
dans config/autonomous.yaml).

DEUX SOURCES, la première prioritaire :
  1. Un statut RÉEL mis en cache par src/live_data_feed.py, basé sur la
     fraîcheur des cotations MT5 (voir MT5Connector.is_symbol_active) --
     s'adapte automatiquement au calendrier RÉEL de VOTRE broker, sans
     rien configurer. Seulement disponible quand la démo (ou --no-demo
     avec MT5 détecté) a pu se connecter au moins une fois.
  2. À défaut (pas de MT5, ou cache trop ancien) : l'estimation `market_hours`
     ci-dessous (calendrier Forex générique, ajustable dans la config si le
     vôtre diffère).
"""
from __future__ import annotations
from datetime import datetime, time as dt_time, timezone


def is_market_open(cfg: dict, now: datetime | None = None) -> bool:
    """True si le marché XAUUSD est considéré comme ouvert à l'instant `now`
    (UTC par défaut). Si `market_hours.enabled` est à `false` dans la
    config, retourne toujours True (comportement classique, sans distinction
    ouvert/fermé). Préfère un statut RÉEL mis en cache par MT5 (voir
    docstring du module) quand il est disponible et récent.
    """
    mh = cfg.get("market_hours", {})
    if not mh.get("enabled", True):
        return True

    if mh.get("use_mt5_detection", True):
        try:
            from src.live_data_feed import read_cached_market_status
            cached = read_cached_market_status(max_age_hours=mh.get("mt5_status_max_age_hours", 1.0))
            if cached is not None:
                return cached
        except Exception:
            pass  # retombe sur l'estimation ci-dessous, jamais d'exception remontée à l'appelant

    now = now or datetime.now(timezone.utc)
    weekday = now.weekday()  # lundi=0 ... dimanche=6

    close_weekday = mh.get("close_weekday", 4)  # vendredi par défaut
    close_hour = mh.get("close_hour", 21)        # 21h UTC (~17h New York)
    open_weekday = mh.get("open_weekday", 6)      # dimanche
    open_hour = mh.get("open_hour", 21)           # 21h UTC

    # Comparaison à la MINUTE (datetime.time) plutôt qu'à l'heure seule --
    # une comparaison sur l'heure seule traite toute la fenêtre 21:00-21:59
    # comme équivalente à 21:00 pile, ce qui décale la fermeture/réouverture
    # réelle de jusqu'à 59 minutes selon la minute où `now` tombe.
    current = (weekday, now.time())
    closed_start = (close_weekday, dt_time(hour=close_hour))
    closed_end = (open_weekday, dt_time(hour=open_hour))

    if closed_start <= current < closed_end:
        return False
    return True
