"""
io_utils.py
============
Petits utilitaires d'E/S partagés -- factorise `_read_json`/`_read_json_safe`,
auparavant dupliquée à l'identique dans src/continuous_trainer.py,
src/dashboard.py et src/demo_trader.py (tâche de nettoyage, audit
institutionnel).
"""
from __future__ import annotations
import json
import os


def read_json_safe(path: str) -> dict:
    """Lit un fichier JSON, ou {} si le fichier n'existe pas OU si sa lecture/
    son parsing échoue pour n'importe quelle raison (JSON corrompu, permission
    refusée...) -- ne lève JAMAIS d'exception. Comportement VÉRIFIÉ identique
    entre les trois implémentations d'origine avant fusion (fichier absent ->
    {}, exception à la lecture/au parsing -> {} également) : aucune n'avait de
    sémantique divergente à préserver séparément."""
    if not os.path.exists(path):
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


class JsonCacheMixin:
    """Mixin partagé (cache JSON sur disque + avertissement journalisé une
    seule fois par clé) -- factorise `_load_cache`/`_save_cache`/`_warn_once`,
    auparavant dupliqués entre src/fred_feed.py::FredFeed et
    src/fundamental_feed.py::AutoFundamentalFeed. Les DEUX implémentations
    d'origine avaient des DIVERGENCES réelles (`_load_cache` : {} par défaut
    chez AutoFundamentalFeed, None chez FredFeed -- qui teste explicitement
    `cached is not None` dans fetch_series() pour savoir si un cache existe,
    voir ce site d'appel ; `_warn_once` : suffixe de message légèrement
    différent) -- PRÉSERVÉES ici via des paramètres explicites (jamais de
    valeur par défaut implicite côté mixin) plutôt qu'aplanies en silence.

    La classe hôte doit définir dans son `__init__` :
      - `self._warned: set()`  (déjà le cas dans les deux classes d'origine,
        inchangé)
      - `self._log`            (le logger DU MODULE hôte -- pour que les
        messages restent attribués à "fred_feed"/"fundamental_feed", pas à
        "io_utils")
    """

    def _load_cache(self, path: str, default):
        if not os.path.exists(path):
            return default
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return default

    def _save_cache(self, path: str, data):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f)

    def _warn_once(self, key: str, msg: str, suffix: str):
        if key not in self._warned:
            self._log.warning(msg + suffix)
            self._warned.add(key)
