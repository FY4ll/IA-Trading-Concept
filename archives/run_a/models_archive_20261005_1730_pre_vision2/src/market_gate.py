"""
market_gate.py
===============
Filtre de marché INDÉPENDANT de l'IA (05/10/2026, vision "Autonomous Trader V1",
§10, §17, §21) : il peut seulement empêcher une NOUVELLE ouverture, jamais une
fermeture ni le maintien d'une position existante. Quatre contrôles :

  1. news   : pas d'ouverture de `minutes_before` avant à `minutes_after` après
              une annonce à fort impact (calendrier Forex Factory, devises
              configurées -- USD par défaut, ce qui couvre NFP/CPI/FOMC).
              Calendrier indisponible -> état explicite NEWS_DATA_UNAVAILABLE
              (jamais "pas de news"), politique `on_unavailable` allow|block.
  2. spread : spread actuel / ATR au-dessus de `max_spread_atr_ratio`.
  3. data   : symbole sans cotation fraîche depuis `stale_minutes`.
  4. regime : classe de volatilité ou régime listé dans la config.

Config (run_config.live.market_gate), tout est désactivé si la section manque :
  market_gate:
    enabled: true
    news: {enabled: true, currencies: [USD], impacts: [High], minutes_before: 30,
           minutes_after: 15, on_unavailable: allow, refresh_minutes: 240}
    max_spread_atr_ratio: 0.10
    stale_minutes: 10
    block_vol_classes: []
    block_regimes: []
"""
from __future__ import annotations
import json
import logging
import os
import threading
import time
from datetime import datetime, timedelta, timezone

log = logging.getLogger("market_gate")

NEWS_OK, NEWS_STALE, NEWS_UNAVAILABLE = "OK", "STALE_CACHE", "NEWS_DATA_UNAVAILABLE"
CALENDAR_CACHE = os.path.join("data", "cache", "ff_calendar.json")
DEFAULT_CALENDAR_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"


def _parse_event_time(s: str) -> datetime | None:
    try:
        dt = datetime.fromisoformat(s)
    except Exception:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


class NewsCalendar:
    """Calendrier économique de la semaine, mis en cache sur disque. Ne fait jamais planter l'appelant."""

    def __init__(self, url: str = DEFAULT_CALENDAR_URL, refresh_minutes: float = 240,
                 cache_path: str = CALENDAR_CACHE, fetcher=None):
        self.url = url
        self.refresh_s = refresh_minutes * 60
        self.cache_path = cache_path
        self._fetcher = fetcher
        self._lock = threading.Lock()
        self._events: list[dict] = []
        self._fetched_at = 0.0
        self._last_attempt = 0.0
        self._load_cache()

    def _load_cache(self):
        try:
            with open(self.cache_path, encoding="utf-8") as f:
                data = json.load(f)
            self._events = data.get("events", [])
            self._fetched_at = float(data.get("fetched_at", 0))
        except Exception:
            pass

    def _fetch(self) -> list[dict]:
        if self._fetcher is not None:
            return self._fetcher()
        import requests
        r = requests.get(self.url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
        r.raise_for_status()
        return r.json()

    def refresh_if_needed(self, now: float | None = None):
        now = now if now is not None else time.time()
        with self._lock:
            if now - self._fetched_at < self.refresh_s or now - self._last_attempt < 1800:
                return
            self._last_attempt = now
            try:
                raw = self._fetch()
                events = []
                for e in raw:
                    t = _parse_event_time(str(e.get("date", "")))
                    if t is None:
                        continue
                    events.append({"time_utc": t.isoformat(), "title": e.get("title", ""),
                                   "country": e.get("country", ""), "impact": e.get("impact", "")})
                self._events, self._fetched_at = events, now
                os.makedirs(os.path.dirname(self.cache_path), exist_ok=True)
                with open(self.cache_path, "w", encoding="utf-8") as f:
                    json.dump({"fetched_at": now, "events": events}, f)
            except Exception as e:
                log.warning(f"Calendrier économique indisponible ({type(e).__name__}: {e}).")

    def status(self, now: float | None = None) -> str:
        now = now if now is not None else time.time()
        if not self._events:
            return NEWS_UNAVAILABLE
        if now - self._fetched_at > 7 * 86400:
            return NEWS_UNAVAILABLE
        if now - self._fetched_at > max(self.refresh_s * 2, 86400):
            return NEWS_STALE
        return NEWS_OK

    def events(self) -> list[dict]:
        return list(self._events)


def find_blackout(events: list[dict], now_utc: datetime, currencies, impacts,
                  minutes_before: float, minutes_after: float) -> dict | None:
    """Annonce qui place `now_utc` dans sa fenêtre interdite, sinon None."""
    cur = {c.upper() for c in currencies}
    imp = {i.lower() for i in impacts}
    for e in events:
        if e.get("country", "").upper() not in cur or e.get("impact", "").lower() not in imp:
            continue
        t = _parse_event_time(e["time_utc"])
        if t is None:
            continue
        if t - timedelta(minutes=minutes_before) <= now_utc <= t + timedelta(minutes=minutes_after):
            return e
    return None


def next_event(events: list[dict], now_utc: datetime, currencies, impacts) -> dict | None:
    cur = {c.upper() for c in currencies}
    imp = {i.lower() for i in impacts}
    future = [e for e in events if e.get("country", "").upper() in cur and e.get("impact", "").lower() in imp
              and (_parse_event_time(e["time_utc"]) or now_utc) > now_utc]
    return min(future, key=lambda e: e["time_utc"]) if future else None


class MarketGate:
    def __init__(self, cfg: dict, calendar: NewsCalendar | None = None):
        self.cfg = (cfg.get("live") or {}).get("market_gate") or {}
        news = self.cfg.get("news") or {}
        self.news_cfg = news
        self.calendar = calendar
        if self.calendar is None and self.enabled and news.get("enabled"):
            url = (cfg.get("fundamental") or {}).get("calendar_url") or DEFAULT_CALENDAR_URL
            self.calendar = NewsCalendar(url=url, refresh_minutes=news.get("refresh_minutes", 240))

    @property
    def enabled(self) -> bool:
        return bool(self.cfg.get("enabled"))

    def news_context(self, now_utc: datetime | None = None) -> dict:
        """État des news pour le journal (même si le filtre ne bloque rien)."""
        if not (self.enabled and self.news_cfg.get("enabled") and self.calendar):
            return {"news_status": "DISABLED"}
        now_utc = now_utc or datetime.now(timezone.utc)
        self.calendar.refresh_if_needed()
        status = self.calendar.status()
        cur = self.news_cfg.get("currencies", ["USD"])
        imp = self.news_cfg.get("impacts", ["High"])
        nxt = next_event(self.calendar.events(), now_utc, cur, imp) if status != NEWS_UNAVAILABLE else None
        return {"news_status": status,
                "next_event": f"{nxt['time_utc']} {nxt['country']} {nxt['title']}" if nxt else None}

    def check_opening(self, df, connector, regime: dict | None,
                      now_utc: datetime | None = None, style: str | None = None) -> list[str]:
        """Raisons de bloquer une nouvelle ouverture ([] = autorisée). Les filtres de régime de
        la config s'ajoutent à ceux ADOPTÉS par la recherche pour ce style (research_engine)."""
        if not self.enabled:
            return []
        reasons = []
        now_utc = now_utc or datetime.now(timezone.utc)

        if self.news_cfg.get("enabled") and self.calendar is not None:
            self.calendar.refresh_if_needed()
            status = self.calendar.status()
            if status == NEWS_UNAVAILABLE:
                if self.news_cfg.get("on_unavailable", "allow") == "block":
                    reasons.append("news_data_unavailable")
            else:
                ev = find_blackout(self.calendar.events(), now_utc,
                                   self.news_cfg.get("currencies", ["USD"]),
                                   self.news_cfg.get("impacts", ["High"]),
                                   self.news_cfg.get("minutes_before", 30),
                                   self.news_cfg.get("minutes_after", 15))
                if ev is not None:
                    reasons.append(f"news_blackout:{ev['country']} {ev['title']} @ {ev['time_utc']}")

        max_ratio = self.cfg.get("max_spread_atr_ratio")
        spread_fn = getattr(connector, "get_current_spread_pct", None)
        if max_ratio and spread_fn is not None and df is not None and "atr_14" in df.columns:
            try:
                price = float(df["close"].iloc[-1])
                atr = float(df["atr_14"].iloc[-1])
                ratio = spread_fn() * price / atr if atr > 0 else None
                if ratio is not None and ratio > max_ratio:
                    reasons.append(f"spread_high:{ratio:.3f}xATR")
            except Exception as e:
                reasons.append(f"spread_unknown:{type(e).__name__}")

        stale = self.cfg.get("stale_minutes")
        active_fn = getattr(connector, "is_symbol_active", None)
        if stale and active_fn is not None:
            try:
                if not active_fn(staleness_minutes=stale):
                    reasons.append(f"data_stale:>{stale}min")
            except Exception:
                reasons.append("data_stale:unknown")

        if regime:
            block_vol = list(self.cfg.get("block_vol_classes") or [])
            block_reg = list(self.cfg.get("block_regimes") or [])
            if style and self.cfg.get("use_research_filters", True):
                from src.research_engine import adopted_filters
                adopted = adopted_filters().get(style) or {}
                block_vol += adopted.get("block_vol_classes") or []
                block_reg += adopted.get("block_regimes") or []
            if regime.get("vol_class") in block_vol:
                reasons.append(f"regime_filter:vol={regime['vol_class']}")
            if regime.get("regime") in block_reg:
                reasons.append(f"regime_filter:{regime['regime']}")
        return reasons
