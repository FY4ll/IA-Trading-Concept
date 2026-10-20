"""
fundamental_feed.py
====================
Auto-alimente l'agent en contexte FONDAMENTAL, automatiquement :

  1. Sentiment des news financières : lecture de flux RSS publics (aucune
     clé API requise). Score de sentiment calculé par FinBERT (voir
     src/finbert_sentiment.py -- modèle spécifiquement financier, LOCAL,
     sans API payante, poids téléchargés une seule fois) par défaut, avec
     repli automatique sur VADER (lexique générique embarqué) si FinBERT
     est indisponible. `fundamental.sentiment_model: "vader"` pour utiliser
     VADER directement.
  2. Contexte macro FRED (src/fred_feed.py) : remplace l'ancien calendrier
     économique (signal mort -- retournait toujours zéro en production,
     voir historique git). 7 séries FRED (taux réel 10 ans, Treasury 10
     ans, taux Fed, indice Dollar, CPI, VIX, breakeven inflation 10 ans)
     combinées en un score bullish/bearish pour l'or, pondéré à 40% dans
     `fundamental_score` (voir `AutoFundamentalFeed.align_to_bars`). Le
     sentiment RSS garde ses 60%. Nécessite une clé API FRED
     (config/autonomous.yaml -> fred.api_key) ; sans clé, retombe sur un
     score neutre (0.0), même pattern que les autres fallbacks du projet.

Les flux sont mis en cache localement (data/cache/) pour éviter de
re-télécharger à chaque appel, et alignés heure par heure sur les bougies
de prix.

Conçu pour ne JAMAIS interrompre le pipeline : si une source est
indisponible (pas de connexion internet, flux hors service...), un score
neutre (0.0) est utilisé à la place, avec un simple avertissement journalisé.
"""
from __future__ import annotations
import os
import json
import time
import threading
import logging
from functools import lru_cache
import numpy as np
import pandas as pd

from src.io_utils import JsonCacheMixin

log = logging.getLogger("fundamental_feed")

# Deux instances d'AutoFundamentalFeed existent en pratique -- une pour
# l'entraînement (créée dans autonomous_agent.py, utilisée par le thread
# EVOLUTION) et une pour la démo (créée dans demo_trader.py, thread
# principal) -- qui lisent-modifient-écrivent les MÊMES fichiers de cache
# (NEWS_CACHE, CALENDAR_CACHE, ARTICLE_SCORE_CACHE, chemins constants au
# niveau module, pas par instance). Sans ce verrou, un cycle lecture-
# modification-écriture concurrent depuis les deux threads peut perdre les
# ajouts de l'un des deux (le dernier à écrire gagne). Module-level (pas par
# instance) puisque le risque porte sur les FICHIERS partagés, pas sur un
# état d'instance.
_cache_lock = threading.Lock()

CACHE_DIR = "data/cache"
NEWS_CACHE = os.path.join(CACHE_DIR, "news_sentiment_cache.json")
# Cache PAR ARTICLE (id -> score), distinct de NEWS_CACHE (agrégat PAR
# HEURE) : sans lui, le même article -- qui reste dans les 50 dernières
# entrées d'un flux RSS pendant potentiellement des heures -- était rescoré
# par FinBERT à CHAQUE rafraîchissement (un par style à chaque reconstruction
# de dataset, potentiellement plusieurs fois par heure), pour un résultat
# identique à chaque fois. Chaque article n'est maintenant scoré qu'UNE
# SEULE fois, jamais recalculé ensuite.
ARTICLE_SCORE_CACHE = os.path.join(CACHE_DIR, "article_scores_cache.json")
_MAX_ARTICLE_CACHE_ENTRIES = 5000

# Flux RSS publics et gratuits, sans clé API. Vous pouvez en ajouter/retirer
# librement dans config/autonomous.yaml -> fundamental.rss_feeds
DEFAULT_RSS_FEEDS = [
    "https://feeds.a.dj.com/rss/RSSMarketsMain.xml",
    "https://investinglive.com/feed/",          # ex-forexlive.com, qui a été rebaptisé (l'ancienne URL ne répond plus)
    "https://www.federalreserve.gov/feeds/press_all.xml",
    "https://www.ecb.europa.eu/rss/press.xml",  # attention : ".xml", pas ".html" (qui n'est qu'une page web)
]

# Beaucoup de sites (WSJ notamment) bloquent silencieusement les requêtes
# dont l'en-tête User-Agent ressemble à un script automatisé plutôt qu'à un
# navigateur. Sans ceci, plusieurs flux échouent systématiquement même avec
# une connexion internet parfaitement fonctionnelle.
_BROWSER_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


class AutoFundamentalFeed(JsonCacheMixin):
    def __init__(self, cfg: dict):
        self.cfg = cfg.get("fundamental", {})
        os.makedirs(CACHE_DIR, exist_ok=True)
        self._analyzer = None
        self._warned = set()
        self._log = log  # voir src/io_utils.py::JsonCacheMixin
        from src.fred_feed import FredFeed
        self._fred = FredFeed(cfg)

    # ---------------- Sentiment (VADER, lexique embarqué) ---------------- #
    def _get_analyzer(self):
        if self._analyzer is None:
            from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
            self._analyzer = SentimentIntensityAnalyzer()
        return self._analyzer

    def refresh_news_sentiment(self) -> dict:
        """Télécharge les flux RSS configurés et calcule un score de sentiment
        moyen par heure (-1 = très négatif, +1 = très positif). Verrouillé
        (voir `_cache_lock`) : deux instances (entraînement + démo) peuvent
        sinon lire-modifier-écrire les mêmes fichiers de cache en même temps
        et perdre les ajouts de l'une des deux."""
        with _cache_lock:
            return self._refresh_news_sentiment_locked()

    def _refresh_news_sentiment_locked(self) -> dict:
        try:
            import feedparser
        except ImportError:
            self._warn_once("feedparser_missing", "`feedparser` non installé (pip install feedparser).",
                             suffix=" -> score neutre utilisé en remplacement pour cette source.")
            return self._load_cache(NEWS_CACHE, default={})

        feeds = self.cfg.get("rss_feeds", DEFAULT_RSS_FEEDS)
        analyzer = self._get_analyzer()
        scored: dict[str, list[float]] = {}
        any_success = False

        # Cache PAR ARTICLE : un même article reste dans les 50 dernières
        # entrées d'un flux RSS pendant potentiellement des heures -- sans
        # ce cache, il serait rescoré par FinBERT à chaque rafraîchissement
        # (un par style à chaque reconstruction de dataset) pour un résultat
        # identique. `article_cache` persiste entre les appels via le
        # fichier JSON, `article_cache_dirty` évite une écriture disque
        # inutile si rien de nouveau n'a été vu.
        article_cache = self._load_cache(ARTICLE_SCORE_CACHE, default={})
        article_cache_dirty = False

        import socket
        previous_timeout = socket.getdefaulttimeout()
        socket.setdefaulttimeout(10)  # évite un blocage indéfini si un flux ne répond jamais
        try:
            for url in feeds:
                try:
                    # `agent` = User-Agent envoyé au serveur. Sans ceci, plusieurs
                    # sites (notamment le WSJ) bloquent silencieusement les
                    # requêtes qui ressemblent à un script plutôt qu'à un
                    # navigateur, ce qui peut faire échouer TOUS les flux même
                    # avec une connexion internet parfaitement fonctionnelle.
                    parsed = feedparser.parse(url, agent=_BROWSER_USER_AGENT)
                    if getattr(parsed, "bozo", 0) and not parsed.entries:
                        raise RuntimeError(parsed.get("bozo_exception", "flux invalide"))
                    for entry in parsed.entries[:50]:
                        title = entry.get("title", "")
                        if not title:
                            continue
                        article_id = entry.get("id") or entry.get("link") or title
                        if article_id in article_cache:
                            title_score = article_cache[article_id]
                        else:
                            # FinBERT (modèle financier LOCAL, sans API -- voir
                            # src/finbert_sentiment.py) en priorité si activé et
                            # disponible ; VADER (lexique générique) en repli,
                            # jamais de plantage pour un titre qui échoue.
                            title_score = None
                            if self.cfg.get("sentiment_model", "finbert") == "finbert":
                                from src.finbert_sentiment import score as finbert_score
                                title_score = finbert_score(title)
                            if title_score is None:
                                title_score = analyzer.polarity_scores(title)["compound"]
                            article_cache[article_id] = title_score
                            article_cache_dirty = True
                        published = entry.get("published_parsed") or entry.get("updated_parsed")
                        if published:
                            ts = pd.Timestamp(time.strftime("%Y-%m-%d %H:00:00", published))
                        else:
                            ts = pd.Timestamp.utcnow().floor("h")
                        key = ts.strftime("%Y-%m-%d %H:00:00")
                        scored.setdefault(key, []).append(title_score)
                    any_success = True
                except Exception as e:
                    self._warn_once(f"rss_{url}", f"Flux RSS indisponible ({url}) : {e}",
                                     suffix=" -> score neutre utilisé en remplacement pour cette source.")
                    continue
        finally:
            socket.setdefaulttimeout(previous_timeout)

        if article_cache_dirty:
            # Purge simple (garde les plus récents) si le cache grossit trop
            # -- borne la taille sans dépendre d'une expiration par date.
            if len(article_cache) > _MAX_ARTICLE_CACHE_ENTRIES:
                article_cache = dict(list(article_cache.items())[-_MAX_ARTICLE_CACHE_ENTRIES:])
            self._save_cache(ARTICLE_SCORE_CACHE, article_cache)

        if not any_success:
            return self._load_cache(NEWS_CACHE, default={})

        hourly_avg = {k: sum(v) / len(v) for k, v in scored.items()}
        # fusion avec le cache existant plutôt qu'un écrasement complet
        merged = {**self._load_cache(NEWS_CACHE, default={}), **hourly_avg}
        self._save_cache(NEWS_CACHE, merged)
        return merged

    # _load_cache/_save_cache/_warn_once : voir src/io_utils.py::JsonCacheMixin
    # (factorisés, auparavant dupliqués ici et dans src/fred_feed.py).

    def align_to_bars(self, df: pd.DataFrame, refresh: bool = True) -> pd.Series:
        """Retourne une Series alignée sur la colonne 'time' de `df`,
        combinant sentiment RSS (FinBERT, 60%) et contexte macro FRED (40%),
        normalisée approximativement entre -1 et 1.

        Le score combinait auparavant sentiment des news (60%) et surprise
        macro du calendrier économique (40%). Le flux calendrier
        (`refresh_economic_calendar`/`CALENDAR_CACHE`) retournait zéro en
        continu en production (source jamais alimentée) : son poids (40%) a
        été redistribué au sentiment RSS (100%) en attendant une source de
        remplacement. `src/fred_feed.py` (API FRED) reprend maintenant ce
        rôle -- le score FRED est constant sur l'échelle horaire (les
        séries FRED sont journalières) et n'a donc pas besoin du mécanisme
        de decay ci-dessous, qui reste réservé au sentiment RSS.

        PERSISTANCE (decay) : un vrai pic de sentiment (ex: une news qui
        surprend) influence le marché pendant des HEURES, pas seulement la
        bougie de l'annonce -- sans ça, le score retombait à 0.0 dès l'heure
        suivante, ce qui revenait à ignorer l'essentiel de l'impact réel
        d'une annonce. Chaque score persiste maintenant en décroissant
        exponentiellement (`fundamental.decay_factor`, défaut 0.85 -> demi-
        vie d'environ 4h) au lieu de disparaître d'un coup.
        """
        if df.empty:
            return pd.Series([], dtype=float)

        # Score MACRO FRED historique point-in-time uniquement (reset 01/10) :
        # l'ancien mélange (60% news RSS + 40% scalaire FRED du jour) était
        # CONSTANT sur tout l'historique d'entraînement (std appris ~1e-8) donc
        # jamais appris, et explosait en live. Il n'existe pas d'historique de
        # news fiable -> news exclues du score, mêmes valeurs train et live.
        if self.cfg.get("macro_only", True):
            from src.fred_feed import macro_score_series
            daily = macro_score_series(self._fred)
            tbl = pd.DataFrame({"time": daily.index, "score": daily.values})
            order = df["time"].argsort()
            aligned = pd.merge_asof(
                df[["time"]].iloc[order].reset_index(drop=True).assign(time=lambda x: pd.to_datetime(x["time"])),
                tbl.dropna(), on="time", direction="backward",
            )
            result = pd.Series(0.0, index=df.index)
            result.iloc[order.values] = aligned["score"].fillna(0.0).values
            return result

        news = self.refresh_news_sentiment() if refresh else self._load_cache(NEWS_CACHE, default={})
        fred_score = self._fred.compute_fred_score()

        decay = self.cfg.get("decay_factor", 0.85)
        start, end = df["time"].min(), df["time"].max()
        news_decayed = _decayed_hourly_series(news, start, end, decay)

        hourly = pd.DataFrame({
            "time": news_decayed.index,
            "n": news_decayed.values,
        })
        hourly["score"] = 0.6 * hourly["n"] + 0.4 * fred_score

        order = df["time"].argsort()
        aligned = pd.merge_asof(
            df[["time"]].iloc[order].reset_index(drop=True),
            hourly[["time", "score"]], on="time", direction="backward",
        )
        result = pd.Series(0.0, index=df.index)
        result.iloc[order.values] = aligned["score"].fillna(0.0).values
        return result


def _decayed_hourly_series(scores: dict, start: pd.Timestamp, end: pd.Timestamp,
                            decay_factor: float) -> pd.Series:
    """Construit une série horaire où chaque score PERSISTE en décroissant
    exponentiellement (`decayed[t] = raw[t] + decay_factor * decayed[t-1]`)
    au lieu de disparaître dès l'heure suivante. Calculée UNE FOIS sur la
    grille horaire complète (pas bougie par bougie -- potentiellement des
    centaines de milliers de lignes pour une timeframe fine), puis alignée
    aux bougies par l'appelant via merge_asof (rapide).

    Mémoïsée (`_decayed_hourly_series_cached`) : `scores` ne change qu'au
    rythme du rafraîchissement des news (minutes), alors que cette fonction
    peut être appelée à chaque cycle de décision -- `scores` (dict, non
    hashable) est converti en tuple trié pour servir de clé de cache.
    """
    scores_key = tuple(sorted(scores.items()))
    return _decayed_hourly_series_cached(scores_key, pd.Timestamp(start), pd.Timestamp(end), decay_factor)


@lru_cache(maxsize=32)
def _decayed_hourly_series_cached(scores_items: tuple, start: pd.Timestamp, end: pd.Timestamp,
                                   decay_factor: float) -> pd.Series:
    scores = dict(scores_items)
    idx = pd.date_range(start=start.floor("h"), end=end.ceil("h"), freq="h")
    if len(idx) == 0:
        return pd.Series([0.0], index=[start])
    raw = np.array([scores.get(ts.strftime("%Y-%m-%d %H:00:00"), 0.0) for ts in idx])
    decayed = np.empty_like(raw)
    running = 0.0
    for i, v in enumerate(raw):
        running = v + decay_factor * running
        decayed[i] = running
    return pd.Series(decayed, index=idx)
