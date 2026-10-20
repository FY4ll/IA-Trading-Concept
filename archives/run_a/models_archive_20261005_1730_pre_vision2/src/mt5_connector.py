"""
mt5_connector.py
================
Pont entre l'agent entraîné et un terminal MetaTrader 5 DÉJÀ INSTALLÉ et
DÉJÀ CONNECTÉ à un compte (comme demandé dans la vision du projet).

IMPORTANT :
  - Le package Python `MetaTrader5` ne fonctionne QUE sous Windows, et
    UNIQUEMENT si le terminal MT5 est ouvert sur la même machine.
  - Ce module est volontairement protégé par plusieurs garde-fous :
      1. seul un agent qui a passé la validation (`models/demo_champion/`,
         voir src/continuous_trainer.py) est utilisé par la boucle de
         démo -- ce connecteur n'est jamais appelé avant cela
         (autonomous_agent.py attend `has_demo_champion()`).
      2. `is_demo_account()` vérifie auprès de MT5 que le compte connecté
         est bien un compte de DÉMONSTRATION ; si ce n'est pas le cas,
         `send_order()` force le dry-run quoi qu'il arrive, sauf
         activation explicite de `live.allow_real_account`.
      3. `live.dry_run = true` par défaut : les décisions sont calculées et
         journalisées mais AUCUN ordre réel n'est envoyé, tant que vous ne
         passez pas explicitement `dry_run: false`.
"""
from __future__ import annotations
import time
import threading
import logging
import traceback
import json
import os
import concurrent.futures

from src.constants import MAGIC_NUMBER, LOT_TOLERANCE, LOT_REL_TOLERANCE, PRICE_TOLERANCE
from src.risk_engine import (
    SymbolSpec, cap_stop_pct, lots_from_risk, notional_lots, round_volume, tighten_stop_or_cancel,
    atr_stop_distance_pct, ATR_STOP_PCT_FLOOR, ATR_STOP_PCT_CEILING,
)

# JOURNAL D'EXÉCUTION (audit institutionnel, section 6 -- gap slippage
# réel/simulé) : un enregistrement JSON par ligne (append-only) pour chaque
# ordre RÉELLEMENT envoyé à MT5 (ouverture ET clôture), comparant le prix
# DEMANDÉ (`request["price"]`, lu juste avant l'envoi) au prix RÉELLEMENT
# rempli (`result.price`, renvoyé par MT5) -- voir send_order. Jamais écrit
# en dry-run (aucun ordre réel envoyé, rien à mesurer). Voir
# scripts/slippage_report.py pour l'analyse agrégée.
EXECUTION_LOG_PATH = os.path.join("data", "execution_log.jsonl")

# LATENCE RÉSEAU (audit institutionnel, section 5 -- optimisation
# infrastructure) : cache simple pour measure_round_trip_ms, même
# emplacement/format que data/cache/live_spread.json (src/live_data_feed.py).
LATENCY_CACHE_PATH = os.path.join("data", "cache", "live_latency.json")

log = logging.getLogger("mt5_connector")

# Partagée entre get_latest_bars() et get_bars_range() -- construite avec
# les constantes du module `MetaTrader5` réel (self._mt5), résolue à
# l'appel plutôt qu'à l'import (le module n'est importable que sur Windows
# avec un terminal MT5 installé, voir connect()).
_TF_ATTR = {
    "M1": "TIMEFRAME_M1", "M5": "TIMEFRAME_M5", "M15": "TIMEFRAME_M15",
    "M30": "TIMEFRAME_M30", "H1": "TIMEFRAME_H1", "H4": "TIMEFRAME_H4",
    "D1": "TIMEFRAME_D1", "W1": "TIMEFRAME_W1", "MN1": "TIMEFRAME_MN1",
}

# TAG DE POSITION PAR STYLE (18/09, fondation du multi-position -- voir
# send_order) : format "{style} gen:{génération}" (ex: "D1 gen:296"),
# volontairement lisible directement dans l'historique MT5, pas seulement
# par du code. Le magic number (voir send_order, constants.MAGIC_NUMBER) identifie déjà
# "c'est notre bot" -- ce tag ne sert QU'à dire à quel style/génération
# appartient une position précise, rien de plus (pas d'indicateur
# ouverture/fermeture ici : MT5 le donne déjà nativement et fiablement via
# deal.entry, inutile de le dupliquer). Fonctions libres (pas de `self`) :
# testables isolément, utilisées aussi bien pour construire que pour
# relire un comment.
_STYLE_TAG_SEP = " gen:"


def _position_comment(style: str | None, generation: int | None) -> str | None:
    """None si `style` n'est pas fourni (appel non taggé -- l'appelant
    retombe alors sur les anciens comments génériques, comportement
    d'origine inchangé pour qui n'utilise pas encore le tag par style)."""
    if style is None:
        return None
    gen_str = str(generation) if generation is not None else "?"
    return f"{style}{_STYLE_TAG_SEP}{gen_str}"


def _parse_style_from_comment(comment: str | None) -> str | None:
    """Style extrait d'un comment taggé, ou None si le comment n'a pas ce
    format (comment générique legacy, position manuelle, etc. -- jamais
    confondue avec un style précis par un filtre trop permissif)."""
    if not comment or _STYLE_TAG_SEP not in comment:
        return None
    return comment.split(_STYLE_TAG_SEP)[0]


def _parse_generation_from_comment(comment: str | None) -> int | None:
    """Génération extraite d'un comment taggé (ex: "H4 gen:134" -> 134),
    ou None si absente/illisible ("?" -- voir _position_comment quand
    `generation` n'était pas connu à l'ouverture -- ou tout autre format
    inattendu). Ajouté le 21/09 pour reprendre EXACTEMENT le snapshot
    historique qui a ouvert une position au redémarrage du processus (voir
    demo_trader.py::_resolve_entry_for_open_position) -- sans ça, un
    redémarrage fait toujours gérer une position par la version COURANTE
    du champion, potentiellement différente de celle qui l'a ouverte."""
    if not comment or _STYLE_TAG_SEP not in comment:
        return None
    gen_str = comment.split(_STYLE_TAG_SEP, 1)[1]
    try:
        return int(gen_str)
    except ValueError:
        return None


def _positions_for_style(positions, style: str | None):
    """Filtre une liste de positions MT5 par tag de style. `style=None` =
    comportement D'ORIGINE inchangé : retourne TOUTES les positions telles
    quelles (l'appelant ne fait alors aucune distinction par style, exactement
    comme avant l'existence de ce tag)."""
    if positions is None:
        return []
    if style is None:
        return list(positions)
    return [p for p in positions if _parse_style_from_comment(getattr(p, "comment", None)) == style]


def _worst_case_loss(price_open: float, sl: float, volume: float, contract_size: float) -> float | None:
    """Perte en DOLLARS si le stop de cette position est touché --
    (distance prix d'entrée -> stop) x volume x taille de contrat.

    Mesurée depuis le PRIX D'ENTRÉE, pas le prix courant : c'est exactement
    la quantité que le dimensionnement par risque a budgétée à l'ouverture
    (voir `_risk_based_lots`), donc la seule qui permette de vérifier
    l'invariant "somme des risques budgétés <= plafond". La mesurer depuis
    le prix courant donnerait un chiffre qui dérive à chaque tick et qui
    AUGMENTE quand la position est en profit (un long à 4400 entré à 4300
    avec stop à 4250 "risquerait" alors 150 points au lieu des 50
    budgétés), ce qui bloquerait des ouvertures d'autant plus que le compte
    va bien -- l'inverse du comportement voulu.

    `None` quand la position n'a PAS de stop (`sl` absent ou 0) : sa perte
    maximale n'est alors pas bornée, et l'appelant doit traiter ce cas
    explicitement plutôt que de le compter comme un risque nul.
    """
    if not sl or float(sl) <= 0:
        return None
    return abs(float(price_open) - float(sl)) * float(volume) * float(contract_size)


class MT5Connector:
    def __init__(self, cfg: dict):
        self.cfg = cfg["live"]
        # Référence à la config COMPLÈTE (pas seulement `live`) -- nécessaire
        # pour envoyer une alerte via src/notifier.py (section `notifications`,
        # au niveau racine) depuis send_order().
        self._full_cfg = cfg
        self.symbol = self.cfg["symbol"]
        self.lot_size = self.cfg["lot_size"]
        self._mt5 = None
        self._verified_demo = None  # tri-état : None = pas encore vérifié
        # Ce connecteur est PARTAGÉ entre le thread principal (boucle de
        # démo) et le thread LIVE_FEED (voir src/live_data_feed.py), qui
        # interrogent tous les deux MT5 en parallèle. Le package Python
        # MetaTrader5 n'est pas documenté comme thread-safe (un seul canal
        # IPC vers le terminal) -- sans ce verrou, deux appels concurrents
        # peuvent se marcher dessus et renvoyer des résultats corrompus ou
        # incohérents. Toutes les méthodes qui touchent self._mt5 doivent
        # l'acquérir. RLock (pas Lock) : send_order() appelle
        # get_open_position() et is_demo_account() en interne, qui
        # ré-acquièrent le même verrou depuis le même thread -- un Lock
        # simple ferait un deadlock dans ce cas.
        self._lock = threading.RLock()
        # HEARTBEAT (audit institutionnel, section 5) : horodatage du DERNIER
        # appel MT5 réussi, tous types confondus -- voir _mark_success (appelé
        # par les méthodes les plus sollicitées à chaque cycle de démo) et
        # seconds_since_last_success. Initialisé à la construction (pas à
        # connect()) pour ne jamais être None -- avant toute connexion
        # réussie, "temps écoulé depuis le dernier succès" grandit simplement
        # depuis l'instant de création du connecteur, ce qui est le
        # comportement voulu (pas encore connecté = pas encore de succès).
        self._last_success_at = time.time()
        # ROUTAGE ASYNCHRONE DES ORDRES (audit institutionnel, section 5) :
        # un seul worker dédié -- send_order() reste englobé par self._lock
        # (l'API MetaTrader5 n'est pas documentée thread-safe, un seul canal
        # IPC vers le terminal), donc plusieurs workers ne paralléliseraient
        # RIEN de plus (ils finiraient par se mettre en file sur le même
        # verrou) ; l'intérêt réel de cet exécuteur est de sortir l'envoi
        # d'ordre du thread APPELANT (la boucle de décision de demo_trader.py)
        # pour qu'un aller-retour réseau lent sur UN ordre ne bloque jamais,
        # par exemple, le thread LIVE_FEED qui a besoin du même verrou pour de
        # simples lectures de cotations. Voir send_order_async.
        self._order_executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=1, thread_name_prefix="MT5_ORDER_ROUTER")

    def _mark_success(self):
        """Appelé après CHAQUE appel MT5 réussi par les méthodes les plus
        sollicitées à chaque cycle de démo (équité, bougies, positions,
        envoi d'ordre) -- voir seconds_since_last_success. Volontairement
        PAS instrumenté sur la totalité des méthodes de ce fichier (~15+
        appels MT5 différents) : celles listées ci-dessus couvrent déjà tout
        le chemin critique d'un cycle de démo normal, un heartbeat n'a pas
        besoin d'une précision à la méthode près."""
        self._last_success_at = time.time()

    def seconds_since_last_success(self) -> float:
        """Temps écoulé (secondes) depuis le dernier appel MT5 réussi -- voir
        _mark_success. Utilisé par demo_trader.py pour détecter une perte de
        connexion prolongée (seuil de 5s avec position(s) ouverte(s), voir
        cahier des charges institutionnel section 5) indépendamment de toute
        autre logique (account_guard, market_hours...)."""
        return time.time() - self._last_success_at

    def measure_round_trip_ms(self) -> float | None:
        """Mesure le temps d'aller-retour (ms) d'un appel MT5 léger
        (`symbol_info_tick`) -- pas une vraie latence réseau jusqu'au serveur
        du broker (l'API Python MT5 ne l'expose pas), mais le temps du
        cycle Python -> terminal MT5 (IPC local) -> réponse, qui inclut la
        composante réseau terminal<->serveur broker en interne. Sert de
        signal de dégradation relatif (une hausse soudaine indique un
        problème, même sans valeur absolue parfaitement comparable au ping
        réseau pur) -- voir cahier des charges institutionnel section 5
        ("optimisation infrastructure réseau"). None en cas d'échec, ne lève
        jamais d'exception. Écrit un cache JSON (même emplacement/format que
        data/cache/live_spread.json, voir src/live_data_feed.py) à chaque
        appel -- pas de planificateur périodique intégré ici, c'est à
        l'appelant de rappeler cette méthode aussi souvent que voulu."""
        try:
            start = time.perf_counter()
            with self._lock:
                tick = self._mt5.symbol_info_tick(self.symbol)
            elapsed_ms = (time.perf_counter() - start) * 1000.0
            if tick is None:
                return None
            self._mark_success()
        except Exception:
            return None
        try:
            os.makedirs(os.path.dirname(LATENCY_CACHE_PATH), exist_ok=True)
            with open(LATENCY_CACHE_PATH, "w", encoding="utf-8") as f:
                json.dump({"round_trip_ms": elapsed_ms, "measured_at": time.time(),
                           "symbol": self.symbol}, f)
        except Exception:
            pass  # le cache est un confort de diagnostic, jamais bloquant
        return elapsed_ms

    def send_order_async(self, *args, **kwargs) -> concurrent.futures.Future:
        """Enveloppe purement additive autour de `send_order` (signature et
        comportement de `send_order` lui-même INCHANGÉS -- voir ce cahier des
        charges institutionnel, section 5 "routage asynchrone") : soumet
        l'appel au worker dédié (`self._order_executor`) et retourne
        immédiatement un `Future` plutôt que de bloquer le thread appelant
        pendant tout l'aller-retour réseau. L'appelant (voir
        demo_trader.py) qui a besoin du résultat AVANT de poursuivre (ex:
        coordination inter-styles dans le même cycle) appelle
        `.result(timeout=...)` explicitement -- ce n'est donc pas "envoyer et
        oublier", seulement "ne pas monopoliser le verrou MT5 partagé
        pendant l'attente réseau depuis LE THREAD APPELANT", ce qui suffit à
        libérer par exemple le thread LIVE_FEED en parallèle."""
        return self._order_executor.submit(self.send_order, *args, **kwargs)

    @property
    def dry_run(self) -> bool:
        """Relu depuis `self.cfg` à CHAQUE accès (pas mis en cache à la
        connexion) : fait partie du sous-ensemble éditable en direct depuis
        le tableau de bord (voir src/settings_server.py) -- un changement
        doit couper/reprendre l'envoi d'ordres réels sans redémarrer le
        script."""
        return self.cfg.get("dry_run", True)

    @property
    def allow_real_account(self) -> bool:
        return self.cfg.get("allow_real_account", False)

    @property
    def order_type(self) -> str:
        """LOT 2, phase 8 : "market" (défaut, comportement D'ORIGINE inchangé
        -- exécution immédiate au marché) ou "limit" (ouverture UNIQUEMENT --
        une clôture reste TOUJOURS au marché, voir send_order -- placée en
        ordre à cours limité protégé, voir limit_order_max_slippage_pct).
        Relu à chaque accès, comme `dry_run` ci-dessus (éditable en direct)."""
        return self.cfg.get("order_type", "market")

    @property
    def limit_order_max_slippage_pct(self) -> float:
        """Distance MAXIMALE (fraction du prix) au-delà du prix courant à
        laquelle un ordre à cours limité d'OUVERTURE accepte encore de se
        remplir -- jamais pire que ça, contrairement à un ordre au marché
        qui accepte n'importe quel prix d'exécution disponible."""
        return self.cfg.get("limit_order_max_slippage_pct", 0.0005)

    def is_demo_account(self) -> bool:
        """Vérifie auprès de MT5 si le compte connecté est un compte de
        DÉMONSTRATION. Résultat mis en cache après connexion.
        """
        if self._verified_demo is not None:
            return self._verified_demo
        if self._mt5 is None:
            return False
        with self._lock:
            account = self._mt5.account_info()
            if account is None:
                self._verified_demo = False
            else:
                self._verified_demo = (
                    getattr(account, "trade_mode", None) == self._mt5.ACCOUNT_TRADE_MODE_DEMO
                )
        return self._verified_demo

    def connect(self):
        try:
            import MetaTrader5 as mt5
        except ImportError as e:
            raise RuntimeError(
                "Le package `MetaTrader5` n'est pas installé ou n'est pas "
                "disponible sur cet OS (Windows uniquement). "
                "Faites `pip install MetaTrader5` sur votre machine Windows."
            ) from e

        with self._lock:
            self._mt5 = mt5
            # Comme un compte est déjà connecté dans le terminal ouvert, un simple
            # initialize() suffit (pas besoin de renvoyer login/mot de passe).
            # IMPORTANT : ne JAMAIS passer path=None explicitement -> l'API MT5
            # rejette ça avec "Invalid 'path' argument". Il faut soit omettre
            # totalement le paramètre, soit fournir une vraie chaîne de chemin.
            terminal_path = self.cfg.get("mt5_terminal_path") or ""
            ok = mt5.initialize(path=terminal_path) if terminal_path else mt5.initialize()
            if not ok:
                raise RuntimeError(f"Échec de connexion à MT5 : {mt5.last_error()}")

            account = mt5.account_info()
            if account is None:
                raise RuntimeError("Aucun compte connecté détecté dans le terminal MT5.")
            log.info(f"Connecté au compte {account.login} ({account.server}), "
                      f"solde={account.balance} {account.currency}")

        if self.is_demo_account():
            log.info("Compte détecté comme DÉMONSTRATION.")
        else:
            log.warning(
                "Compte détecté comme RÉEL (pas une démo). Par sécurité, tous les "
                "ordres seront forcés en mode DRY RUN (aucun envoi réel), sauf si "
                "vous avez explicitement mis `live.allow_real_account: true` dans "
                "votre config -- ce que ce projet déconseille fortement pour un "
                "système entièrement automatisé."
            )
        return account

    def get_latest_bars(self, timeframe: str, n_bars: int):
        """Récupère l'historique récent EN RÉUTILISANT la connexion MT5 déjà
        établie (self._mt5), sans jamais la réinitialiser ni la fermer.

        Important : contrairement à `src.data_loader.load_mt5` (qui fait son
        propre cycle initialize()/shutdown() à chaque appel -- adapté pour un
        usage ponctuel, mais qui COUPERAIT la connexion partagée utilisée
        ensuite pour envoyer des ordres), cette méthode réutilise la connexion
        déjà ouverte par `connect()`.
        """
        import pandas as pd

        if timeframe not in _TF_ATTR:
            raise ValueError(f"Timeframe '{timeframe}' non supportée par MT5Connector. "
                              f"Disponibles : {list(_TF_ATTR.keys())}")

        with self._lock:
            rates = self._mt5.copy_rates_from_pos(self.symbol, getattr(self._mt5, _TF_ATTR[timeframe]), 0, n_bars)
        if rates is None or len(rates) == 0:
            raise RuntimeError(f"Aucune donnée MT5 reçue pour {self.symbol} en {timeframe}. "
                                f"Vérifiez que ce symbole/cette timeframe est bien disponible "
                                f"dans votre terminal (Market Watch).")
        self._mark_success()  # HEARTBEAT (voir _mark_success) -- appel critique du cycle de démo

        df = pd.DataFrame(rates)
        df["time"] = pd.to_datetime(df["time"], unit="s")
        df = df.rename(columns={"tick_volume": "volume"})
        return df[["time", "open", "high", "low", "close", "volume"]]

    def get_symbol_bars(self, symbol: str, timeframe: str, n_bars: int):
        """Comme get_latest_bars mais pour un AUTRE symbole (variables croisées, lecture seule)."""
        import pandas as pd

        if timeframe not in _TF_ATTR:
            raise ValueError(f"Timeframe '{timeframe}' non supportée par MT5Connector.")
        with self._lock:
            self._mt5.symbol_select(symbol, True)
            rates = self._mt5.copy_rates_from_pos(symbol, getattr(self._mt5, _TF_ATTR[timeframe]), 0, n_bars)
        if rates is None or len(rates) == 0:
            raise RuntimeError(f"Aucune donnée MT5 reçue pour {symbol} en {timeframe}.")
        df = pd.DataFrame(rates)
        df["time"] = pd.to_datetime(df["time"], unit="s")
        return df[["time", "close"]]

    def get_bars_range(self, timeframe: str, date_from, date_to):
        """Récupère les bougies entre deux DATES précises (pas un simple
        nombre de bougies) -- utilisé pour COMBLER un trou dans l'historique
        (voir src/live_data_feed.py) sans dépendre de savoir combien de
        bougies ça représente à l'avance (un trou de 7 mois en M1 ne fait
        pas le même nombre de bougies qu'en D1). Retourne un DataFrame vide
        (pas d'exception) si MT5 n'a rien à offrir sur cette plage -- un
        trou qui ne peut pas encore être comblé n'est pas une erreur fatale,
        juste retenté au prochain rafraîchissement.
        """
        import pandas as pd

        if timeframe not in _TF_ATTR:
            raise ValueError(f"Timeframe '{timeframe}' non supportée par MT5Connector. "
                              f"Disponibles : {list(_TF_ATTR.keys())}")

        with self._lock:
            rates = self._mt5.copy_rates_range(self.symbol, getattr(self._mt5, _TF_ATTR[timeframe]), date_from, date_to)
        if rates is None or len(rates) == 0:
            return pd.DataFrame(columns=["time", "open", "high", "low", "close", "volume"])

        df = pd.DataFrame(rates)
        df["time"] = pd.to_datetime(df["time"], unit="s")
        df = df.rename(columns={"tick_volume": "volume"})
        return df[["time", "open", "high", "low", "close", "volume"]]

    def get_current_spread_pct(self) -> float:
        """Retourne le spread bid/ask ACTUEL de `self.symbol`, en fraction
        du prix (ex: 0.00015 = 0.015%) -- pas une estimation, une MESURE
        RÉELLE lue directement sur le terminal MT5 déjà connecté. Sert à
        calibrer le coût de transaction de l'entraînement (voir
        src/live_data_feed.py) sur ce que ça coûte VRAIMENT de trader
        aujourd'hui chez votre broker, au lieu d'une valeur devinée dans
        la config.
        """
        with self._lock:
            tick = self._mt5.symbol_info_tick(self.symbol)
        if tick is None or not tick.bid or not tick.ask:
            raise RuntimeError(f"Impossible de lire le spread actuel pour {self.symbol} "
                                f"(tick MT5 indisponible).")
        mid = (tick.bid + tick.ask) / 2.0
        if mid <= 0:
            raise RuntimeError(f"Prix mid invalide pour {self.symbol} (bid={tick.bid}, ask={tick.ask}).")
        return (tick.ask - tick.bid) / mid

    def is_symbol_active(self, staleness_minutes: float = 10.0) -> bool:
        """Détecte si le marché est ACTUELLEMENT actif pour `self.symbol`,
        en vérifiant la FRAÎCHEUR du dernier tick reçu -- PAS une heure de
        session déclarée : l'API Python de MetaTrader5 n'expose pas
        `symbol_info_session_trade` (contrairement à MQL5, côté terminal),
        donc aucune heure de session exacte n'est disponible depuis ce
        connecteur. La fraîcheur du tick reste un signal réel et fiable,
        indépendant du broker : si aucune nouvelle cotation n'est arrivée
        depuis `staleness_minutes`, le marché est fermé (ou la connexion
        est cassée) -- quoi que dise `market_hours` dans la config.
        """
        with self._lock:
            tick = self._mt5.symbol_info_tick(self.symbol)
        if tick is None or not tick.time:
            return False
        age_minutes = (time.time() - tick.time) / 60.0
        return age_minutes <= staleness_minutes

    def get_account_equity(self) -> float | None:
        """Équité RÉELLE actuelle du compte (solde + PnL flottant), lue
        directement sur MT5 -- utilisée par src/account_guard.py pour le
        coupe-circuit au niveau du compte (indépendant du dimensionnement
        des ordres, voir _risk_based_lots/_notional_lots, qui la lisent
        aussi mais sans l'exposer publiquement). None si indisponible."""
        with self._lock:
            try:
                account = self._mt5.account_info()
            except AttributeError:
                return None
        if account is None:
            return None
        self._mark_success()  # HEARTBEAT (voir _mark_success) -- appel critique du cycle de démo
        return float(account.equity)

    def _price_and_contract_size(self) -> tuple[float, float] | None:
        """Prix moyen (bid+ask)/2 et taille de contrat du symbole -- factorisé
        car recalculé à la fois par `_risk_based_lots` et par `send_order`
        lors du resserrement du stop après arrondi du lot au minimum broker
        (voir send_order). None si prix/infos du symbole indisponibles."""
        try:
            info = self._mt5.symbol_info(self.symbol)
            tick = self._mt5.symbol_info_tick(self.symbol)
            if info is None or tick is None or not tick.bid or not tick.ask:
                return None
            price = (tick.bid + tick.ask) / 2.0
            contract_size = float(getattr(info, "trade_contract_size", 0.0) or 0.0)
            if price <= 0 or contract_size <= 0:
                return None
            return price, contract_size
        except AttributeError:
            return None

    def _symbol_spec(self) -> SymbolSpec:
        """Construit un risk_engine.SymbolSpec depuis mt5.symbol_info() pour
        CE symbole -- mêmes valeurs par défaut que les anciennes lectures
        individuelles (_round_volume, send_order) si `info` est
        indisponible/dégradé (LOT 2, phase 2 : source unique pour
        MT5Connector ET TradingEnv)."""
        try:
            info = self._mt5.symbol_info(self.symbol)
        except AttributeError:
            info = None
        # volume_min N'A PAS de valeur par défaut forcée ici (contrairement à
        # volume_step) : round_volume() applique lui-même `spec.volume_min or
        # step` -- si on forçait un défaut ici, ce fallback ne verrait jamais
        # le vrai `step` lu au-dessus en cas de volume_min absent/0 côté MT5
        # (réplique EXACTEMENT l'ancien MT5Connector._round_volume).
        return SymbolSpec(
            volume_min=float(getattr(info, "volume_min", 0.0) or 0.0) if info else 0.0,
            volume_step=float(getattr(info, "volume_step", 0.01) or 0.01) if info else 0.01,
            volume_max=float(getattr(info, "volume_max", 0.0) or 0.0) if info else 0.0,
            contract_size=float(getattr(info, "trade_contract_size", 0.0) or 0.0) if info else 0.0,
            digits=int(getattr(info, "digits", 2) or 2) if info else 2,
            stops_level_points=float(getattr(info, "trade_stops_level", 0) or 0) if info else 0.0,
            point=float(getattr(info, "point", 0) or 0) if info else 0.0,
        )

    def _risk_based_lots(self, stop_pct: float | None, risk_pct_override: float | None = None) -> float:
        """Taille de position (en lots, pour une exposition PLEINE de 1.0 --
        voir send_order, qui la met à l'échelle par `abs(target_exposure)`)
        basée sur le RISQUE RÉEL EN DOLLARS, pas sur l'équité brute -- la
        façon dont un trader qui comprend les enjeux dimensionne vraiment
        une position : il décide d'abord combien il est prêt à PERDRE si
        son stop est touché (`live.max_risk_pct_per_trade` x équité
        actuelle), puis calcule la taille à partir de CETTE perte tolérée
        et de la distance de SON PROPRE stop (voir agent.learn_stop_loss,
        src/trading_env.py) -- jamais l'inverse.

        Avantage concret par rapport à une taille fixe ou à une simple
        fraction d'équité : un stop plus large réduit automatiquement la
        taille (même perte en $ si le stop est touché), un stop plus serré
        permet une position plus grosse -- le compromis taille/risque
        qu'un vrai trader fait à chaque position, impossible à exprimer
        avec un lot fixe. Grandit aussi avec l'équité (un compte qui
        double sa taille double son risque en $ à conviction égale, pas en
        %) -- fidèle à la façon dont l'agent raisonne pendant
        l'entraînement (fraction du capital, jamais un lot absolu),
        corrigeant l'écart backtest/réel que créait un lot toujours fixe
        (voir aussi src/reliability_tracker.py).

        Retourne 0.0 si `stop_pct` est indisponible (agent.learn_stop_loss
        désactivé, ou aucun stop dominant côté ensemble -- l'appelant
        retombe alors sur `_notional_lots`) ou si équité/prix/infos du
        symbole manquent (retombe alors sur `live.lot_size`).
        """
        # LOT 2, phase 2 : délègue à risk_engine.lots_from_risk (formule
        # identique) -- l'I/O MT5 (equity/prix/contrat) reste ici, la formule
        # pure est partagée avec TradingEnv.
        if not stop_pct or stop_pct <= 0:
            return 0.0
        try:
            account = self._mt5.account_info()
            ctx = self._price_and_contract_size()
            if account is None or ctx is None:
                return 0.0
            equity = float(account.equity)
            price, contract_size = ctx
            risk_pct = float(risk_pct_override) if risk_pct_override is not None \
                else float(self.cfg.get("max_risk_pct_per_trade", 0.02))
            return lots_from_risk(equity, risk_pct, price, stop_pct, contract_size)
        except AttributeError:
            return 0.0

    def _notional_lots(self) -> float:
        """Repli utilisé quand aucun stop n'est disponible pour
        `_risk_based_lots` (ex: agent.learn_stop_loss désactivé) : nombre
        de lots dont la valeur notionnelle équivaut à 100% de l'ÉQUITÉ
        RÉELLE actuelle du compte, SANS effet de levier ajouté --
        équivalent au calcul de PnL non-levier utilisé pendant
        l'entraînement (`realized = variation_prix% x position`) quand il
        n'y a pas de notion de stop pour raisonner en risque plutôt qu'en
        exposition brute. Retourne 0.0 si l'équité, le prix ou les infos du
        symbole sont indisponibles -- l'appelant retombe alors sur
        `live.lot_size` (voir send_order), le comportement d'origine.
        """
        # LOT 2, phase 2 : délègue à risk_engine.notional_lots.
        try:
            account = self._mt5.account_info()
            info = self._mt5.symbol_info(self.symbol)
            tick = self._mt5.symbol_info_tick(self.symbol)
            if account is None or info is None or tick is None or not tick.bid or not tick.ask:
                return 0.0
            equity = float(account.equity)
            price = (tick.bid + tick.ask) / 2.0
            contract_size = float(getattr(info, "trade_contract_size", 0.0) or 0.0)
            return notional_lots(equity, price, contract_size)
        except AttributeError:
            return 0.0

    def _type_filling(self):
        """Mode de remplissage (`type_filling`) accepté par CE broker pour CE
        symbole -- chaque broker/instrument n'accepte souvent qu'UN SEUL des
        modes possibles (FOK, IOC, RETURN), et une requête avec le mauvais
        mode est rejetée par MT5 (retcode 10030 'Unsupported filling mode'),
        même si le volume/prix/stop sont par ailleurs corrects. Trouvé en
        conditions réelles le 14/09 : le code n'envoyait jamais ce champ,
        MT5 retombait sur FOK (valeur 0 par défaut du côté MT5) qui n'était
        pas supporté par ce broker précis -- premier ordre réel de la nuit
        rejeté silencieusement (aucune exception levée, juste un retcode
        d'échec dans le résultat, jamais vérifié). Lit le bitmask
        `symbol_info(symbol).filling_mode` et choisit FOK s'il est
        supporté, sinon IOC, sinon RETURN (repli universel, accepté par
        pratiquement tous les brokers)."""
        try:
            info = self._mt5.symbol_info(self.symbol)
            mode = int(getattr(info, "filling_mode", 0) or 0)
        except AttributeError:
            mode = 0
        if mode & 1:  # SYMBOL_FILLING_FOK
            return self._mt5.ORDER_FILLING_FOK
        if mode & 2:  # SYMBOL_FILLING_IOC
            return self._mt5.ORDER_FILLING_IOC
        return self._mt5.ORDER_FILLING_RETURN

    def _round_volume(self, raw_volume: float, floor_if_positive: bool = False) -> float:
        """Arrondit/borne un volume brut aux contraintes RÉELLES du broker
        pour ce symbole (`volume_step`/`volume_min`/`volume_max`) -- pas une
        limite de risque de notre fait, juste ce qu'il faut pour que
        `order_send` accepte la requête (un volume hors de ces bornes est
        rejeté par MT5). 0.0 si en-dessous du minimum (aucun ordre), SAUF si
        `floor_if_positive` (voir send_order) : un signal directionnel réel
        (l'agent veut une position, pas juste un calcul à zéro) est alors
        remonté au lot minimum plutôt que silencieusement abandonné -- un
        petit compte peut sinon voir CHAQUE conviction, même forte, arrondie
        à zéro indéfiniment sur un instrument à forte valeur de contrat
        (ex: XAUUSD), sans jamais qu'aucun trade ne parte. Le risque RÉEL
        pris dépasse alors légèrement `max_risk_pct_per_trade` pour cette
        position précise -- un compromis délibéré (toujours borné par le lot
        minimum du broker, jamais arbitrairement gros) plutôt que de ne
        jamais trader du tout."""
        # LOT 2, phase 2 : délègue à risk_engine.round_volume (via
        # _symbol_spec(), qui réplique les mêmes défauts que ci-dessus).
        return round_volume(raw_volume, self._symbol_spec(), floor_if_positive=floor_if_positive)

    def _cancel_stale_pending_orders(self, style: str | None):
        """LOT 2, phase 8 : annule tout ordre à cours limité EN ATTENTE (pas
        encore rempli) taggé pour CE style, avant d'en soumettre un nouveau --
        le marché ou la décision de l'agent a pu changer depuis le cycle où
        cet ordre a été placé ; le laisser traîner accumulerait des ordres
        périmés dans le carnet plutôt que de refléter la décision actuelle.
        Best-effort : une erreur d'annulation est journalisée, jamais levée
        (ne doit jamais empêcher la NOUVELLE soumission ci-après)."""
        try:
            pending = self._mt5.orders_get(symbol=self.symbol) or ()
        except AttributeError:
            return
        for order in pending:
            if _parse_style_from_comment(getattr(order, "comment", None)) != style:
                continue
            try:
                cancel_request = {"action": self._mt5.TRADE_ACTION_REMOVE, "order": order.ticket}
                result = self._mt5.order_send(cancel_request)
                log.info(f"Ordre en attente périmé annulé (ticket={order.ticket}, style={style}) : {result}")
            except Exception:
                log.warning(f"Échec d'annulation de l'ordre en attente périmé (ticket={order.ticket}, "
                            f"style={style}) -- best-effort, non bloquant.")

    def get_open_position_info(self) -> dict | None:
        """Retourne le contexte complet de la position RÉELLEMENT ouverte sur
        ce symbole (ticket, direction, prix d'entrée, stop-loss, volume,
        profit flottant) -- ou None si le compte est à plat. Sert au garde-fou
        de `demo_trader.py` (`_StyleRuntime.maybe_reload`) : avant de
        remplacer les poids d'un style par une version nouvellement promue,
        on doit savoir SI une position est ouverte ET quels étaient ses
        objectifs d'origine (prix d'entrée, stop choisi par l'agent à
        l'ouverture) -- pour ne jamais faire gérer une même position par deux
        versions différentes du modèle, et pour que le report du changement
        soit journalisé avec le contexte réel plutôt qu'un simple booléen."""
        with self._lock:
            positions = self._mt5.positions_get(symbol=self.symbol)
        if not positions:
            return None
        pos = positions[0]
        direction = 1 if pos.type == self._mt5.ORDER_TYPE_BUY else -1
        return {
            "ticket": pos.ticket, "direction": direction, "volume": pos.volume,
            "price_open": pos.price_open, "sl": pos.sl, "profit": pos.profit,
        }

    def get_open_positions_by_style(self, recognized_styles: list[str]) -> dict[str, dict]:
        """COORDINATION INTER-STYLES (19/09, arbitrage priorité par score --
        voir demo_trader.py) : renvoie {style: {ticket, direction, volume,
        price_open, sl, profit, opened_by_generation}} pour CHAQUE position actuellement ouverte et taguée
        avec un style de `recognized_styles` -- une position dont le tag ne
        matche aucun style reconnu est simplement absente du résultat (déjà
        traitée par `close_orphan_positions` à la migration, pas le rôle de
        cette méthode). Lecture seule, aucun ordre envoyé -- contrairement à
        `get_open_position_info` (non taguée par style, un seul résultat
        `positions[0]`), celle-ci distingue explicitement chaque style pour
        détecter les positions BUY/SELL simultanées et contradictoires
        entre styles différents."""
        with self._lock:
            positions = self._mt5.positions_get(symbol=self.symbol) or ()
        self._mark_success()  # HEARTBEAT (voir _mark_success) -- appel critique du cycle de démo
        out = {}
        for p in positions:
            comment = getattr(p, "comment", None)
            style = _parse_style_from_comment(comment)
            if style in recognized_styles:
                direction = 1 if p.type == self._mt5.ORDER_TYPE_BUY else -1
                out[style] = {"ticket": p.ticket, "direction": direction,
                               "volume": p.volume, "price_open": p.price_open,
                               "sl": p.sl, "profit": p.profit,
                               "opened_by_generation": _parse_generation_from_comment(comment)}
        return out

    def count_stop_outs_today(self, style: str) -> int | None:
        """Nombre de positions de `style` clôturées par stop-loss CÔTÉ BROKER depuis
        le début de la journée serveur (plafond de stop-outs par jour, prop firm).
        None si l'historique est indisponible (l'appelant ne bloque alors rien)."""
        import datetime as _dt
        try:
            with self._lock:
                tick = self._mt5.symbol_info_tick(self.symbol)
                now = _dt.datetime.utcnow()
                deals = self._mt5.history_deals_get(now - _dt.timedelta(days=30), now + _dt.timedelta(days=1))
            if tick is None or deals is None:
                return None
            day_start = int(tick.time) - int(tick.time) % 86400
            style_of_position = {}
            for d in deals:
                if d.symbol == self.symbol and d.entry == self._mt5.DEAL_ENTRY_IN:
                    style_of_position[d.position_id] = _parse_style_from_comment(getattr(d, "comment", None))
            return sum(
                1 for d in deals
                if d.symbol == self.symbol and d.entry == self._mt5.DEAL_ENTRY_OUT
                and d.reason == self._mt5.DEAL_REASON_SL and d.time >= day_start
                and style_of_position.get(d.position_id) == style
            )
        except Exception as exc:
            log.warning(f"count_stop_outs_today({style}) indisponible : {exc}")
            return None

    def _stop_loss_field(self, entry_price: float, direction: int, stop_pct: float | None = None) -> dict:
        """Construit le champ `sl` (stop-loss) de la requête d'ouverture --
        un FILET DE SÉCURITÉ appliqué CÔTÉ BROKER, indépendant de l'agent :
        sans lui, un mouvement violent entre deux sondages
        (`live.poll_seconds`, 5 min par défaut) n'était rattrapé qu'au
        prochain cycle de décision -- aucune protection immédiate en cas de
        move brutal (news, gap de week-end). Volontairement PAS de
        take-profit : la sortie sur gain reste la décision de l'agent, ce
        stop ne sert qu'à plafonner la perte, jamais à couper un gain à sa
        place.

        `stop_pct`, quand fourni, est la distance CHOISIE PAR L'AGENT
        lui-même pour cette position précise (voir demo_trader.py, qui
        l'extrait de l'action du modèle quand `agent.learn_stop_loss:
        true`) -- prioritaire sur `live.stop_loss_pct`, qui ne sert alors
        que de filet de repli si l'agent n'en a fourni aucune. Retourne {}
        (aucun champ `sl`) si ni l'un ni l'autre n'est disponible --
        comportement d'origine inchangé.
        """
        sl_pct = stop_pct if stop_pct is not None else self.cfg.get("stop_loss_pct")
        if not sl_pct:
            return {}
        info = self._mt5.symbol_info(self.symbol)
        digits = info.digits if info is not None else 2
        sl_price = entry_price * (1 - sl_pct) if direction == 1 else entry_price * (1 + sl_pct)
        return {"sl": round(sl_price, digits)}

    def _take_profit_field(self, entry_price: float, direction: int, stop_pct: float | None,
                           rr: float | None) -> dict:
        """Champ `tp` de la requête : même formule que TradingEnv (entrée x (1 +/- stop x rr))."""
        if not rr or not stop_pct:
            return {}
        info = self._mt5.symbol_info(self.symbol)
        digits = info.digits if info is not None else 2
        tp_price = entry_price * (1 + stop_pct * rr) if direction == 1 else entry_price * (1 - stop_pct * rr)
        return {"tp": round(tp_price, digits)}

    def close_orphan_positions(self, recognized_styles: list[str]) -> list[dict]:
        """MIGRATION (18/09, passage à l'ensemble blended vers le
        multi-position indépendant par style) : ferme, UNE FOIS, proprement,
        toute position dont le tag de style (voir `_parse_style_from_comment`)
        n'est PAS reconnu parmi `recognized_styles` -- typiquement une
        position héritée de l'ancien système (comment générique
        "opened_by_agent", jamais attribuable à un style précis).

        Décision explicite de l'utilisateur (18/09), après avoir écarté le
        "retag" (MT5 ne permet pas de modifier le comment d'une position déjà
        ouverte) et le "laisser intacte indéfiniment" (une position sans
        propriétaire, plus jamais gérée activement par aucun style, ne
        dépendrait plus que de son stop déjà posé -- un risque structurel
        jugé pire qu'un aller-retour de spread pour repartir sur une base
        saine). Appelée au DÉMARRAGE de la boucle multi-position -- idempotente
        et sans effet si aucune position orpheline n'existe (donc sûre à
        rappeler à chaque redémarrage, pas seulement la toute première fois).
        """
        with self._lock:
            mt5 = self._mt5
            positions = mt5.positions_get(symbol=self.symbol) or ()
            orphans = [p for p in positions
                        if _parse_style_from_comment(getattr(p, "comment", None)) not in recognized_styles]
            if not orphans:
                return []

            # MÊME GARDE-FOU que send_order (jamais d'ordre réel sans compte
            # démo confirmé, jamais si dry_run) -- une fermeture de migration
            # reste un ordre réel envoyé à MT5, elle ne doit PAS le contourner.
            effective_dry_run = self.dry_run
            if not self.is_demo_account() and not self.allow_real_account:
                effective_dry_run = True
            if effective_dry_run:
                for p in orphans:
                    log.warning(
                        f"[DRY RUN][MIGRATION multi-position] Aurait fermé la position sans style "
                        f"reconnu : ticket={p.ticket} comment_origine={getattr(p, 'comment', None)!r} "
                        f"volume={p.volume} profit={getattr(p, 'profit', 0.0):.2f}$."
                    )
                return []

            closed = []
            for p in orphans:
                order_type = mt5.ORDER_TYPE_SELL if p.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY
                price = mt5.symbol_info_tick(self.symbol).bid if p.type == mt5.ORDER_TYPE_BUY \
                    else mt5.symbol_info_tick(self.symbol).ask
                request = {
                    "action": mt5.TRADE_ACTION_DEAL, "symbol": self.symbol, "volume": p.volume,
                    "type": order_type, "type_filling": self._type_filling(), "position": p.ticket,
                    "price": price, "deviation": 20, "magic": MAGIC_NUMBER,
                    "comment": "migration_close_untagged",
                }
                result = mt5.order_send(request)
                # `order_send` ne lève JAMAIS d'exception sur un ordre refusé
                # (même constat que dans send_order, ex: retcode 10018 'Market
                # closed' constaté le 18/09) -- sans cette vérification, la
                # position restait ouverte sur le compte réel tout en étant
                # déclarée "fermée" dans le log ET dans l'alerte ntfy envoyée
                # à l'utilisateur, ce qui aurait caché un échec réel.
                if getattr(result, "retcode", None) == mt5.TRADE_RETCODE_DONE:
                    log.warning(
                        f"[MIGRATION multi-position] Position sans style reconnu fermée : ticket={p.ticket} "
                        f"comment_origine={getattr(p, 'comment', None)!r} volume={p.volume} "
                        f"profit={getattr(p, 'profit', 0.0):.2f}$ -> {result}"
                    )
                    closed.append({"ticket": p.ticket, "original_comment": getattr(p, "comment", None),
                                    "volume": p.volume, "profit": getattr(p, "profit", 0.0)})
                else:
                    log.error(
                        f"[MIGRATION multi-position] Échec de fermeture de la position sans style reconnu "
                        f"(retcode={getattr(result, 'retcode', '?')}) : ticket={p.ticket} "
                        f"comment_origine={getattr(p, 'comment', None)!r} volume={p.volume} -- reste ouverte, "
                        f"sera retraitée à la prochaine tentative."
                    )
                    try:
                        from src.notifier import send_alert
                        send_alert(
                            self._full_cfg,
                            subject="Migration multi-position -- échec de fermeture d'une position orpheline",
                            message=(
                                f"Position ticket={p.ticket} (comment_origine="
                                f"{getattr(p, 'comment', None)!r}, volume={p.volume}) non reconnue par un "
                                f"style mais PAS fermée -- ordre refusé par MT5 (retcode="
                                f"{getattr(result, 'retcode', '?')}). Reste ouverte, sera retraitée à la "
                                f"prochaine tentative de migration."
                            ),
                        )
                    except Exception:
                        pass
            return closed

    def _cumulative_exposure_refusal(self, entry_price: float, sl_price: float | None,
                                      volume: float) -> str | None:
        """PLAFOND D'EXPOSITION CUMULÉE (19/09) -- renvoie la RAISON du refus
        d'ouvrir (chaîne prête à journaliser), ou None si l'ouverture est
        autorisée. Ne ferme jamais rien, ne modifie jamais une position
        existante : c'est un veto sur une NOUVELLE ouverture, rien d'autre.

        POURQUOI : depuis le passage au budget de risque DYNAMIQUE (option B,
        voir demo_trader.py), le budget d'un trade est divisé par le nombre de
        styles en position AU MOMENT de son ouverture -- mais une position
        déjà ouverte n'est jamais redimensionnée quand un nouveau style la
        rejoint. Cinq styles d'accord sur la même direction, ouvrant l'un
        après l'autre, cumulent donc 2% + 1% + 0.67% + 0.5% + 0.4% = 4.57%
        de risque simultané, soit 2.28x le plafond nominal par trade (2%).
        Sous l'ancienne répartition FIXE (option A) ce cumul était borné par
        construction à exactement max_risk_pct_per_trade. Ce plafond
        RÉTABLIT cet invariant, mais au niveau du COMPTE et avec un seuil
        propre (`cumulative_exposure_max_pct`), ce qui laisse la
        diversification multi-styles exister au lieu de la neutraliser.

        Somme calculée sur les positions RÉELLEMENT ouvertes chez le broker
        (`positions_get()` relu à l'instant), jamais sur une comptabilité
        interne qui pourrait avoir dérivé (ordre rejeté, stop touché entre
        deux cycles, fermeture manuelle dans le terminal...).
        """
        if not self.cfg.get("cumulative_exposure_enabled"):
            return None
        max_pct = self.cfg.get("cumulative_exposure_max_pct")
        if not max_pct:
            return None

        mt5 = self._mt5
        account = mt5.account_info()
        ctx = self._price_and_contract_size()
        if account is None or ctx is None:
            # Un plafond qu'on ne PEUT PAS mesurer ne garantit rien : refuser
            # est le seul comportement cohérent avec le fait de l'avoir
            # activé explicitement. C'est aussi le moment le plus dangereux
            # pour ouvrir à l'aveugle -- sans équité/infos symbole, le
            # dimensionnement lui-même est déjà retombé sur `live.lot_size`
            # (taille fixe, sans aucun rapport avec le risque voulu).
            return ("équité ou infos symbole indisponibles -- impossible de mesurer l'exposition "
                    "cumulée, ouverture refusée (plafond actif)")
        _, contract_size = ctx
        equity = float(account.equity)
        budget = equity * float(max_pct)

        existing_total = 0.0
        for p in (mt5.positions_get(symbol=self.symbol) or ()):
            loss = _worst_case_loss(getattr(p, "price_open", 0.0), getattr(p, "sl", 0.0),
                                     getattr(p, "volume", 0.0), contract_size)
            if loss is None:
                return (f"la position ouverte ticket={getattr(p, 'ticket', '?')} n'a AUCUN stop -- "
                        f"sa perte maximale n'est pas bornée, donc l'exposition cumulée n'est pas "
                        f"mesurable, ouverture refusée (plafond actif)")
            existing_total += loss

        new_loss = _worst_case_loss(entry_price, sl_price, volume, contract_size)
        if new_loss is None:
            return ("la nouvelle position n'aurait aucun stop -- sa perte maximale ne serait pas "
                    "bornée, ouverture refusée (plafond actif)")

        total = existing_total + new_loss
        if total <= budget:
            return None
        return (f"exposition cumulée {total:.2f}$ ({total / equity:.2%} de l'équité) dépasserait le "
                f"plafond de {budget:.2f}$ ({float(max_pct):.2%}) -- déjà {existing_total:.2f}$ "
                f"engagés sur les positions ouvertes, + {new_loss:.2f}$ pour celle-ci")

    def send_order(self, target_exposure: float, stop_pct: float | None = None,
                    atr_multiplier: float | None = None, atr_price_units: float | None = None,
                    style: str | None = None, generation: int | None = None,
                    risk_pct_override: float | None = None, take_profit_rr: float | None = None,
                    limit_offset_price: float | None = None):
        """`limit_offset_price` (05/10/2026, style TRADER) : l'IA a choisi un ordre LIMITE -> au lieu
        d'un ordre au marché, ordre en attente BUY_LIMIT `limit_offset_price` sous le prix (SELL_LIMIT au-dessus),
        stop et take-profit calculés depuis ce prix limite, expiration 15 min (une bougie M15, comme à
        l'entraînement). None = ordre au marché (comportement d'origine).

        `take_profit_rr` : multiple R/R du take-profit appris par l'agent (styles entraînés avec
        `learn_take_profit`) -> champ `tp` = entrée +/- distance de stop x rr ; None = pas de TP.

        `atr_multiplier`/`atr_price_units` (LOT 2, phase 3 -- corrige un
        écart entraînement/live réel : demo_trader.py décodait auparavant le
        bucket choisi par l'agent via la table STATIQUE en % même quand
        l'entraînement utilisait des buckets ATR dynamiques) : quand
        `atr_multiplier` est fourni, la distance de stop est calculée ICI, à
        l'exécution, via risk_engine.atr_stop_distance_pct (même formule que
        TradingEnv._compute_atr_stop_loss_buckets) à partir du MULTIPLE choisi
        par l'agent et de l'ATR live (`atr_price_units`, en unités de prix,
        fourni par l'appelant) -- `stop_pct` explicite est alors IGNORÉ (source
        unique : soit un `stop_pct` déjà résolu -- style statique -- soit un
        multiple ATR à résoudre ici, jamais les deux). Si l'ATR est REQUIS
        (`atr_multiplier` fourni) mais INDISPONIBLE (`atr_price_units=None`,
        ou prix courant indisponible) : AUCUNE OUVERTURE n'est envoyée (une
        fermeture, elle, n'est jamais bloquée) -- mieux vaut ne pas ouvrir
        que d'ouvrir avec un stop dont on ne peut plus garantir la
        cohérence avec ce que l'agent a appris.

        `style`/`generation` (18/09, fondation du multi-position) :
        quand fournis, cet appel n'agit QUE sur la position taguée pour ce
        style précis (voir `_positions_for_style` -- lecture/fermeture/
        ouverture), et tague toute nouvelle position avec
        "{style} gen:{generation}" (voir `_position_comment`). `None`
        (par défaut, comportement D'ORIGINE inchangé tant que demo_trader.py
        n'a pas été adapté) : agit sur TOUTES les positions du symbole sans
        distinction, exactement comme avant.

        `risk_pct_override` (18/09, budget de risque par style -- option A
        validée, répartition FIXE) : remplace `live.max_risk_pct_per_trade`
        pour CET appel uniquement (dimensionnement ET resserrement après
        floor du lot minimum) -- jamais une mutation de `self.cfg`, qui
        resterait partagée entre tous les styles. `None` = comportement
        d'origine (lit `live.max_risk_pct_per_trade` tel quel).

        `target_exposure` ∈ [-1, 1] : direction ET conviction de la
        position désirée (1 = pleine conviction acheteuse, -1 = idem côté
        vendeur, 0 = flat, valeurs intermédiaires = conviction partielle).

        TAILLE BASÉE SUR LE RISQUE RÉEL EN DOLLARS, PAS UN LOT FIXE (voir
        _risk_based_lots) : à pleine conviction, l'agent risque au plus
        `live.max_risk_pct_per_trade` de l'ÉQUITÉ RÉELLE actuelle du
        compte SI son propre stop est touché -- pas une fraction fixe de
        lots, pas une exposition notionnelle brute. La taille en lots qui
        en découle dépend donc de la distance du stop CHOISI PAR L'AGENT
        (voir `stop_pct` ci-dessous) : un stop plus large -> position plus
        petite pour le même risque en $ ; un stop plus serré -> position
        plus grosse. Exactement le compromis taille/risque qu'un trader
        fait à chaque position, impossible à exprimer avec un lot fixe.
        Sans stop disponible (agent.learn_stop_loss désactivé), repli sur
        une fraction notionnelle de l'équité (_notional_lots) ; sans
        équité/infos symbole disponibles (ex: MT5 déconnecté un instant),
        dernier repli sur `live.lot_size` (comportement d'origine, taille
        fixe).

        Les valeurs intermédiaires de `target_exposure` viennent aussi de
        l'ensemble pondéré multi-styles (voir demo_trader.py,
        `live.ensemble`) : quand les styles actifs sont en désaccord sur la
        direction, l'exposition moyenne se rapproche naturellement de 0 --
        un mécanisme supplémentaire de réduction de taille en cas
        d'incertitude, en plus du risque déjà borné ci-dessus.

        `stop_pct`, quand fourni, est la distance de stop CHOISIE PAR
        L'AGENT pour cette position (voir demo_trader.py) -- transmise à la
        fois au dimensionnement (ci-dessus) et à `_stop_loss_field`
        (prioritaire sur `live.stop_loss_pct`, repli statique).

        SÉCURITÉ : si le compte connecté n'est pas un compte de démonstration
        et que `allow_real_account` n'est pas explicitement activé, l'ordre
        est automatiquement traité en dry-run, quel que soit `self.dry_run`.

        TOLÉRANCE ANTI-SCALPING : compare la DIRECTION et le VOLUME
        RÉELLEMENT ouverts au volume qui serait envoyé pour `target_exposure`
        maintenant, jamais une fraction d'exposition reconstruite. Un premier
        bug de ce type (14/09 : position dimensionnée par risque comparée à
        une référence NOTIONNELLE différente) a déjà été corrigé une fois, en
        introduisant un `get_open_position()` qui recalculait une exposition
        `direction x volume_ouvert / taille_de_référence`. Un second bug DE LA
        MÊME FAMILLE est réapparu le 15/09 dès qu'un 2ᵉ style (M15) a rejoint
        l'ensemble multi-styles : sur ce compte modeste tradant XAUUSD (grosse
        valeur de contrat), le lot calculé par risque tombe sous le minimum
        broker MÊME à pleine conviction (target_exposure=1.0) -- le floor
        s'applique donc IDENTIQUEMENT pour une conviction de 0.13 ou de 1.0
        (0.01 lot dans les deux cas). Reconstruire une fraction d'exposition à
        partir de ce lot déjà floored redonnait alors TOUJOURS ~1.0 (pleine
        conviction), quelle que soit la conviction réelle d'origine -- faisant
        dépasser la tolérance de 0.05 à CHAQUE cycle dès que la cible n'était
        pas déjà proche de {-1, 0, 1}, ce qui est le cas normal d'un ensemble
        à plusieurs styles en désaccord. Comparer directement le volume/la
        direction réels élimine cette perte d'information par construction :
        deux cycles qui aboutissent au même lot (même après floor) sont
        maintenant reconnus comme identiques, quelle que soit la conviction
        fractionnaire d'origine.
        """
        # Tout le cycle lecture-décision-exécution est verrouillé (RLock) :
        # sans ça, le thread LIVE_FEED pourrait interroger MT5 entre notre
        # lecture de la position ouverte et l'envoi de l'ordre, avec un
        # risque d'appels concurrents sur le même canal IPC MT5.
        with self._lock:
            mt5 = self._mt5
            # COMPTE RENDU D'EXÉCUTION (05/10, journal de décision) : ce que cet appel a réellement
            # fait (action finale + jambes envoyées, vérifiées sur MT5) -- lu par demo_trader.py.
            self.last_order_report = {"action": "none", "legs": []}
            # RÉSOLUTION ATR (LOT 2, phase 3) : AVANT toute autre utilisation
            # de stop_pct -- un multiple fourni prend la main entièrement (la
            # distance résolue ici REMPLACE tout stop_pct déjà passé), pour
            # que le plafond max_stop_pct_executed ci-dessous s'applique aussi
            # au résultat.
            atr_unavailable_blocks_opening = False
            if atr_multiplier is not None:
                ctx_for_atr = self._price_and_contract_size()
                if atr_price_units is None or ctx_for_atr is None:
                    atr_unavailable_blocks_opening = True
                    stop_pct = None
                else:
                    price_for_atr, _ = ctx_for_atr
                    stop_pct = atr_stop_distance_pct(
                        atr_price_units, atr_multiplier, price_for_atr,
                        ATR_STOP_PCT_FLOOR, ATR_STOP_PCT_CEILING)
            # PLAFOND D'EXÉCUTION sur la distance de stop (voir
            # config.live.max_stop_pct_executed) : appliqué UNE FOIS ici,
            # avant toute utilisation de stop_pct (dimensionnement ET champ
            # `sl` envoyé au broker) -- ne touche jamais aux buckets/à
            # l'espace d'action appris par l'agent, seulement à la distance
            # RÉELLEMENT utilisée à l'exécution. Demande explicite de
            # l'utilisateur (15/09) après avoir constaté un stop réel à 4.4%
            # du prix d'entrée, une distance si large qu'elle ne protège plus
            # rien en pratique.
            tp_base_stop_pct = stop_pct  # distance apprise, avant plafond d'exécution (même base que l'entraînement)
            max_stop_pct = self.cfg.get("max_stop_pct_executed")
            if stop_pct is not None and max_stop_pct is not None and stop_pct > max_stop_pct:
                log.info(f"Distance de stop demandée par l'agent ({stop_pct:.2%}) plafonnée à "
                          f"{max_stop_pct:.2%} (config live.max_stop_pct_executed).")
                stop_pct = max_stop_pct
            positions = mt5.positions_get(symbol=self.symbol)
            style_positions = _positions_for_style(positions, style)
            pos = style_positions[0] if style_positions else None
            current_direction = (1 if pos.type == mt5.ORDER_TYPE_BUY else -1) if pos is not None else 0
            current_volume = float(pos.volume) if pos is not None else 0.0

            effective_dry_run = self.dry_run
            if not self.is_demo_account() and not self.allow_real_account:
                effective_dry_run = True

            target_direction = 0 if abs(target_exposure) < PRICE_TOLERANCE else (1 if target_exposure > 0 else -1)
            # Hiérarchie de dimensionnement : (1) risque réel en $ rapporté à
            # la distance du stop CHOISI PAR L'AGENT (le plus fidèle -- voir
            # _risk_based_lots) ; (2) à défaut de stop disponible, fraction
            # notionnelle de l'équité (_notional_lots) ; (3) en tout dernier
            # recours (équité/infos symbole indisponibles), le lot fixe de
            # config -- comportement d'origine, jamais l'agent qui décide.
            max_lots = self._risk_based_lots(stop_pct, risk_pct_override=risk_pct_override)
            sizing = "risque/stop"
            if max_lots <= 0:
                max_lots = self._notional_lots()
                sizing = "notionnel/équité"
            if max_lots <= 0:
                log.warning("Équité/prix/infos symbole indisponibles pour dimensionner l'ordre -> "
                            "repli sur live.lot_size (comportement d'origine, taille fixe).")
                volume = round(abs(target_exposure) * self.lot_size, 2)
            else:
                raw_volume = abs(target_exposure) * max_lots
                volume = self._round_volume(raw_volume, floor_if_positive=(target_direction != 0))
                floor_note = " (remonté au lot minimum du broker -- calcul par risque sous ce seuil)" \
                    if volume > 0 and raw_volume > 0 and self._round_volume(raw_volume) == 0.0 else ""
                log.info(f"Taille dimensionnée par {sizing} : {volume} lot(s) pour une exposition de "
                          f"{abs(target_exposure):.2f}{floor_note}.")

            # GARDE-FOU RISQUE APRÈS ARRONDI AU LOT MINIMUM (voir
            # _round_volume, floor_if_positive) : `stop_pct` a servi à
            # calculer `raw_volume` (le lot IDÉAL pour rester dans le budget
            # de risque) -- si le broker impose un lot final PLUS GROS que cet
            # idéal, garder le MÊME stop_pct pour `_stop_loss_field` sous-
            # entendrait un risque $ toujours borné, alors qu'il grandit avec
            # le lot (mesuré jusqu'à x4 le budget ciblé sur un petit compte en
            # XAUUSD). Resserre la distance RÉELLEMENT envoyée à MT5 pour que
            # (lot final x distance x valeur du point) reste sous le budget
            # d'origine -- jamais l'espace d'action appris par l'agent
            # (agent.stop_loss_buckets inchangé), seulement la distance
            # exécutée, exactement comme `max_stop_pct_executed` ci-dessus.
            # LOT 2, phase 2 : délègue à risk_engine.tighten_stop_or_cancel
            # (formule identique) -- l'I/O MT5 et les logs restent ici.
            effective_stop_pct = stop_pct
            if sizing == "risque/stop" and effective_stop_pct is not None and volume > raw_volume > 0:
                account = mt5.account_info()
                ctx = self._price_and_contract_size()
                if account is not None and ctx is not None:
                    price_ctx, contract_size = ctx
                    risk_pct = float(risk_pct_override) if risk_pct_override is not None \
                        else float(self.cfg.get("max_risk_pct_per_trade", 0.02))
                    spec = self._symbol_spec()
                    new_stop_pct, cancel = tighten_stop_or_cancel(
                        raw_volume, volume, effective_stop_pct, float(account.equity),
                        price_ctx, risk_pct, spec)
                    if new_stop_pct != effective_stop_pct:
                        log.info(
                            f"Lot arrondi au minimum broker ({volume} > {raw_volume:.4f} idéal) -- "
                            f"stop resserré de {effective_stop_pct:.2%} à {new_stop_pct:.2%} "
                            f"pour ne pas dépasser le risque cible ({float(account.equity) * risk_pct:.2f}$)."
                        )
                    effective_stop_pct = new_stop_pct
                    if cancel:
                        min_stop_pct = (spec.stops_level_points * spec.point) / price_ctx
                        log.error(
                            f"Ordre ANNULÉ : compte trop petit pour ce risque sur {self.symbol} à "
                            f"ce prix ({price_ctx}), à ce stop_level broker "
                            f"({spec.stops_level_points} points = {min_stop_pct:.2%}) -- le stop "
                            f"resserré nécessaire ({effective_stop_pct:.2%}) serait rejeté par "
                            f"MT5, et l'élargir dépasserait le risque cible."
                        )
                        self.last_order_report["action"] = "cancelled_min_stop"
                        return

            # tolérance : évite de renvoyer un ordre pour un micro-ajustement
            # de volume qui ne changerait rien de notable côté broker.
            if target_direction == current_direction and abs(current_volume - volume) < max(
                    LOT_TOLERANCE, LOT_REL_TOLERANCE * max(current_volume, volume)):
                log.info(f"Position déjà alignée (direction={current_direction}, "
                          f"volume={current_volume:.2f} ~= {volume:.2f}), rien à faire.")
                self.last_order_report["action"] = "aligned"
                if target_direction == 0 and style is not None and not self.dry_run:
                    self._cancel_stale_pending_orders(style)   # l'IA ne veut plus entrer : limite en attente annulée
                return

            # DISJONCTEUR DE COMPTE DANS LE CONNECTEUR (19/09, audit
            # institutionnel section 5) : demo_trader.py vérifie déjà
            # account_guard.check() une fois PAR CYCLE avant d'appeler
            # decide()/send_order() pour chaque style (voir
            # run_demo_trading_loop) -- ceci est un SECOND filet INDÉPENDANT,
            # directement dans le connecteur, pour tout appelant futur de
            # send_order() qui ne passerait pas par cette boucle (défense en
            # profondeur, pas une duplication inutile : la boucle appelante
            # pourrait un jour changer sans que ce filet-ci ne bouge).
            # MÊME RÈGLE que `_cumulative_exposure_refusal` plus bas (voir ce
            # garde-fou) : ne bloque QU'une OUVERTURE (`target_direction != 0
            # and volume > 0`, la seule condition sous laquelle ce code
            # atteint jamais l'envoi réel d'un ordre d'OUVERTURE -- une
            # fermeture pure, elle, ne repasse jamais par cette branche) --
            # une fermeture n'augmente jamais le risque et ne doit JAMAIS
            # pouvoir être bloquée, quel que soit l'état du coupe-circuit.
            # Lecture seule (`is_halted()`, pas `check()`) : ne relit pas
            # l'équité, ne modifie aucun état -- réutilise simplement le halt
            # déjà décidé par le cycle appelant (ou par tout autre appelant
            # de account_guard.check()), sans jamais dupliquer sa logique de
            # décision ici (voir "Pas de réécriture de MT5Connector").
            # ATR REQUIS MAIS INDISPONIBLE (LOT 2, phase 3) : même règle
            # qu'account_guard ci-dessous -- ne bloque QU'une ouverture,
            # jamais une fermeture.
            if target_direction != 0 and volume > 0 and atr_unavailable_blocks_opening:
                log.error(
                    f"Ouverture REFUSÉE : distance de stop ATR requise (multiple={atr_multiplier}) "
                    f"mais ATR indisponible{f' [{style}]' if style else ''} -- aucun ordre envoyé plutôt "
                    f"qu'un stop incohérent avec ce que l'agent a appris."
                )
                self._log_execution(
                    {"type": mt5.ORDER_TYPE_BUY if target_direction == 1 else mt5.ORDER_TYPE_SELL,
                     "volume": volume, "price": None},
                    None, style, leg="refused_atr_unavailable",
                )
                self.last_order_report["action"] = "refused_atr_unavailable"
                return

            if target_direction != 0 and volume > 0:
                from src.account_guard import is_halted
                if is_halted():
                    log.error(
                        f"Ouverture REFUSÉE par le coupe-circuit de compte (account_guard.is_halted())"
                        f"{f' [{style}]' if style else ''} : direction={target_direction:+d}, "
                        f"volume={volume:.2f}. Les positions déjà ouvertes ne sont PAS touchées ; "
                        f"réinitialisez explicitement le coupe-circuit (voir "
                        f"src/account_guard.py::reset()) pour débloquer de nouvelles ouvertures."
                    )
                    self._log_execution(
                        {"type": mt5.ORDER_TYPE_BUY if target_direction == 1 else mt5.ORDER_TYPE_SELL,
                         "volume": volume, "price": None},
                        None, style, leg="refused_halted",
                    )
                    self.last_order_report["action"] = "refused_halted"
                    return

            if effective_dry_run:
                log.info(f"[DRY RUN] Aurait envoyé un ordre pour passer de "
                          f"(direction={current_direction}, volume={current_volume:.2f}) à "
                          f"(direction={target_direction}, volume={volume:.2f}) sur {self.symbol}.")
                if target_direction != 0 and volume > 0:
                    self._notify_trade_opened(target_direction, volume, stop_pct, simulated=True)
                self.last_order_report["action"] = "dry_run"
                return

            # Clôture de la/les position(s) existante(s) si nécessaire --
            # UNIQUEMENT celles de CE style si `style` est fourni (voir
            # style_positions ci-dessus), sinon TOUTES (comportement
            # d'origine inchangé). CORRECTIF (18/09) : la direction/le prix
            # de clôture de CHAQUE position viennent désormais de SA PROPRE
            # `p.type`, plus d'une `current_direction` partagée calculée une
            # fois pour toutes -- l'ancien code fermait TOUJOURS dans le
            # sens déduit de la première position trouvée, donc dans le
            # MAUVAIS sens pour toute autre position en direction opposée
            # (silencieux tant qu'une seule position existait à la fois,
            # devient un vrai risque dès que plusieurs styles tiennent des
            # positions simultanées et désaccordées).
            targets_to_close = style_positions if style is not None else positions
            if targets_to_close:
                for p in targets_to_close:
                    tick = mt5.symbol_info_tick(self.symbol)
                    if tick is None or tick.ask <= 0 or tick.bid <= 0:
                        log.error(f"Clôture ANNULÉE pour la position {p.ticket} : tick invalide "
                                  f"(marché fermé, déconnexion) pour {self.symbol} -- "
                                  f"ask={getattr(tick, 'ask', None)}, bid={getattr(tick, 'bid', None)}.")
                        continue
                    order_type = mt5.ORDER_TYPE_SELL if p.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY
                    price = tick.bid if p.type == mt5.ORDER_TYPE_BUY else tick.ask
                    request = {
                        "action": mt5.TRADE_ACTION_DEAL,
                        "symbol": self.symbol,
                        "volume": p.volume,
                        "type": order_type,
                        "type_filling": self._type_filling(),
                        "position": p.ticket,
                        "price": price,
                        "deviation": 20,
                        "magic": MAGIC_NUMBER,
                        "comment": _position_comment(style, generation) or "close_by_agent",
                    }
                    try:
                        t0 = time.perf_counter()
                        result = mt5.order_send(request)
                        self._last_send_ms = (time.perf_counter() - t0) * 1000.0
                    except Exception:
                        log.error(f"Exception lors de l'envoi de la clôture pour {self.symbol} "
                                  f"(position {p.ticket}) :\n{traceback.format_exc()}")
                        continue
                    log.info(f"Clôture position : {result}")
                    self._log_execution(request, result, style, leg="close", position_ticket=p.ticket)
                    self.last_order_report["action"] = "sent"
                    if getattr(result, "retcode", None) == mt5.TRADE_RETCODE_DONE:
                        self._mark_success()  # HEARTBEAT -- appel critique du cycle de démo

            # Ouverture de la nouvelle position si l'exposition cible n'est pas nulle
            if target_direction != 0 and volume > 0:
                tick = mt5.symbol_info_tick(self.symbol)
                if tick is None or tick.ask <= 0 or tick.bid <= 0:
                    log.error(f"Ouverture ANNULÉE : tick invalide (marché fermé, déconnexion) pour "
                              f"{self.symbol} -- ask={getattr(tick, 'ask', None)}, "
                              f"bid={getattr(tick, 'bid', None)}.")
                    self.last_order_report["action"] = "cancelled_bad_tick"
                    return
                deal_direction_type = mt5.ORDER_TYPE_BUY if target_direction == 1 else mt5.ORDER_TYPE_SELL
                price = tick.ask if target_direction == 1 else tick.bid
                # Calculé UNE fois : sert au garde-fou d'exposition cumulée
                # ci-dessous ET à la requête envoyée -- le plafond doit
                # raisonner sur le stop RÉELLEMENT transmis au broker, pas
                # sur une reconstruction qui pourrait diverger.
                sl_field = self._stop_loss_field(price, target_direction, effective_stop_pct)
                tp_field = self._take_profit_field(price, target_direction, tp_base_stop_pct, take_profit_rr)

                # PLAFOND D'EXPOSITION CUMULÉE : dernier filtre avant l'envoi,
                # APRÈS les éventuelles clôtures ci-dessus (donc sur l'état
                # réel du compte à cet instant). Ne s'applique qu'à une
                # OUVERTURE : une fermeture n'augmente jamais le risque et ne
                # doit jamais pouvoir être bloquée.
                refusal = self._cumulative_exposure_refusal(price, sl_field.get("sl"), volume)
                if refusal is not None:
                    log.error(
                        f"Ouverture REFUSÉE par le plafond d'exposition cumulée"
                        f"{f' [{style}]' if style else ''} : {refusal}. Les positions déjà ouvertes "
                        f"ne sont PAS touchées ; cette ouverture sera retentée aux cycles suivants, "
                        f"quand de l'exposition se sera libérée."
                    )
                    self.last_order_report["action"] = "refused_exposure"
                    return

                if limit_offset_price is not None and limit_offset_price > 0:
                    # ORDRE LIMITE CHOISI PAR L'IA (style TRADER) : prix limite sous/sur le marché,
                    # stop/TP recalculés depuis ce prix, expiration une bougie M15.
                    self._cancel_stale_pending_orders(style)
                    info = mt5.symbol_info(self.symbol)
                    digits = getattr(info, "digits", 2) if info else 2
                    lp = round(price - target_direction * float(limit_offset_price), digits)
                    sl_l = self._stop_loss_field(lp, target_direction, effective_stop_pct)
                    tp_l = self._take_profit_field(lp, target_direction, tp_base_stop_pct, take_profit_rr)
                    request = {
                        "action": mt5.TRADE_ACTION_PENDING, "symbol": self.symbol, "volume": volume,
                        "type": mt5.ORDER_TYPE_BUY_LIMIT if target_direction == 1 else mt5.ORDER_TYPE_SELL_LIMIT,
                        "type_time": getattr(mt5, "ORDER_TIME_SPECIFIED", mt5.ORDER_TIME_GTC),
                        "expiration": int(getattr(tick, "time", time.time())) + 900,
                        "type_filling": self._type_filling(), "price": lp, "magic": MAGIC_NUMBER,
                        "comment": _position_comment(style, generation) or "opened_by_agent", **sl_l, **tp_l,
                    }
                    t0 = time.perf_counter()
                    result = mt5.order_send(request)
                    if getattr(result, "retcode", None) != getattr(mt5, "TRADE_RETCODE_PLACED", 10008):
                        request.pop("expiration", None)
                        request["type_time"] = mt5.ORDER_TIME_GTC     # broker sans expiration : annulée au cycle suivant
                        result = mt5.order_send(request)
                    self._last_send_ms = (time.perf_counter() - t0) * 1000.0
                    log.info(f"Ordre LIMITE {'ACHAT' if target_direction == 1 else 'VENTE'} {volume} lot(s) à {lp} "
                             f"(marché {price}, écart {limit_offset_price:.2f}) [{style}] : {result}")
                    self._log_execution(request, result, style, leg="limit")
                    self.last_order_report["action"] = "limit_placed" if getattr(
                        result, "retcode", None) == getattr(mt5, "TRADE_RETCODE_PLACED", 10008) else "limit_refused"
                    return
                if self.order_type == "limit":
                    # ORDRE À COURS LIMITÉ (LOT 2, phase 8) : contrairement à
                    # l'ordre au marché ci-dessous (accepte n'importe quel
                    # prix disponible), celui-ci ne se remplira JAMAIS à un
                    # prix pire que `price` -- protection dure contre le
                    # slippage, au prix d'un risque de non-remplissage si le
                    # marché s'éloigne avant exécution. Annule d'abord tout
                    # ordre en attente PRÉCÉDENT de ce même style (jamais
                    # d'accumulation d'ordres périmés d'un cycle à l'autre --
                    # le marché/la décision de l'agent a pu changer entre-temps).
                    self._cancel_stale_pending_orders(style)
                    limit_price = (price * (1 + self.limit_order_max_slippage_pct) if target_direction == 1
                                   else price * (1 - self.limit_order_max_slippage_pct))
                    info = mt5.symbol_info(self.symbol)
                    digits = getattr(info, "digits", 2) if info else 2
                    request = {
                        "action": mt5.TRADE_ACTION_PENDING,
                        "symbol": self.symbol,
                        "volume": volume,
                        "type": (mt5.ORDER_TYPE_BUY_LIMIT if target_direction == 1
                                 else mt5.ORDER_TYPE_SELL_LIMIT),
                        "type_time": mt5.ORDER_TIME_GTC,
                        "type_filling": self._type_filling(),
                        "price": round(limit_price, digits),
                        "magic": MAGIC_NUMBER,
                        "comment": _position_comment(style, generation) or "opened_by_agent",
                        **sl_field,
                        **tp_field,
                    }
                else:
                    request = {
                        "action": mt5.TRADE_ACTION_DEAL,
                        "symbol": self.symbol,
                        "volume": volume,
                        "type": deal_direction_type,
                        "type_filling": self._type_filling(),
                        "price": price,
                        "deviation": 20,
                        "magic": MAGIC_NUMBER,
                        "comment": _position_comment(style, generation) or "opened_by_agent",
                        **sl_field,
                        **tp_field,
                    }
                try:
                    t0 = time.perf_counter()
                    result = mt5.order_send(request)
                    self._last_send_ms = (time.perf_counter() - t0) * 1000.0
                except Exception:
                    log.error(f"Exception lors de l'envoi de l'ouverture pour {self.symbol} :\n"
                              f"{traceback.format_exc()}")
                    self.last_order_report["action"] = "send_exception"
                    return
                log.info(f"Ouverture position : {result}")
                self._log_execution(request, result, style, leg="open")
                self.last_order_report["action"] = "sent"
                # VÉRIFICATION (vision V1 §23) : ne jamais supposer qu'un ordre est exécuté parce que
                # order_send a répondu -- relire la position réelle sur MT5 et comparer au voulu.
                if self.order_type != "limit":
                    self._verify_open(result, style, volume, sl_field.get("sl"), tp_field.get("tp"))
                # `order_send` ne lève JAMAIS d'exception sur un ordre
                # refusé (ex: retcode 10030 'Unsupported filling mode',
                # trouvé en conditions réelles le 14/09) -- sans cette
                # vérification, une notification "trade ouvert" partait
                # même quand MT5 avait rejeté l'ordre, ce qui aurait induit
                # l'utilisateur en erreur sur ce qui s'est réellement passé.
                # SUCCÈS ATTENDU DIFFÉRENT SELON LE TYPE D'ORDRE (LOT 2, phase 8) :
                # un ordre au marché "réussi" = TRADE_RETCODE_DONE (exécuté
                # immédiatement) ; un ordre à cours limité "réussi" =
                # TRADE_RETCODE_PLACED (accepté et EN ATTENTE dans le
                # carnet -- pas encore forcément rempli, voir
                # _cancel_stale_pending_orders pour le nettoyage au cycle
                # suivant s'il ne s'est toujours pas rempli).
                expected_retcode = (mt5.TRADE_RETCODE_PLACED if self.order_type == "limit"
                                     else mt5.TRADE_RETCODE_DONE)
                if getattr(result, "retcode", None) == expected_retcode:
                    self._mark_success()  # HEARTBEAT -- appel critique du cycle de démo
                    self._notify_trade_opened(target_direction, volume, stop_pct, simulated=False)
                else:
                    log.error(f"Ordre REFUSÉ par MT5 (retcode={getattr(result, 'retcode', '?')}) -- "
                              f"aucune position ouverte malgré la décision de l'agent.")

    def _verify_open(self, result, style: str | None, volume_req: float, sl_req, tp_req) -> None:
        """Relit sur MT5 la position réellement ouverte et complète la dernière jambe du compte
        rendu : prix/volume/SL/TP réels, remplissage partiel, risque réel en $ au stop."""
        try:
            legs = getattr(self, "last_order_report", {}).get("legs") or []
            leg = legs[-1] if legs else None
            if leg is None or getattr(result, "retcode", None) != self._mt5.TRADE_RETCODE_DONE:
                return
            positions = self._mt5.positions_get(symbol=self.symbol) or []
            mine = _positions_for_style(positions, style) if style is not None else list(positions)
            order_ticket = getattr(result, "order", None)
            pos = next((p for p in mine if p.ticket == order_ticket), None)
            if pos is None and mine:
                pos = max(mine, key=lambda p: getattr(p, "time_msc", getattr(p, "time", 0)))
            if pos is None:
                leg.update({"verified": 0, "note": "position introuvable sur MT5 après un ordre DONE"})
                log.error(f"[vérification] ordre DONE mais aucune position {style or ''} trouvée sur MT5.")
                return
            ctx = self._price_and_contract_size()
            contract = ctx[1] if ctx else None
            risk_usd = (abs(float(pos.price_open) - float(pos.sl)) * float(pos.volume) * contract
                        if contract and pos.sl else None)
            leg.update({"verified": 1, "position_ticket": int(pos.ticket), "volume_filled": float(pos.volume),
                        "price_filled": float(pos.price_open), "sl_req": sl_req, "tp_req": tp_req,
                        "sl_actual": float(pos.sl) or None, "tp_actual": float(pos.tp) or None,
                        "risk_usd": risk_usd})
            notes = []
            if abs(float(pos.volume) - float(volume_req)) > 1e-9:
                notes.append(f"remplissage partiel {pos.volume}/{volume_req}")
            if sl_req and abs(float(pos.sl) - float(sl_req)) > 1e-6 * float(sl_req):
                notes.append(f"SL réel {pos.sl} != voulu {sl_req}")
            if tp_req and abs(float(pos.tp) - float(tp_req)) > 1e-6 * float(tp_req):
                notes.append(f"TP réel {pos.tp} != voulu {tp_req}")
            if notes:
                leg["note"] = "; ".join(notes)
                log.warning(f"[vérification] {style or ''} : " + "; ".join(notes))
        except Exception:
            log.warning(f"[vérification] impossible de relire la position :\n{traceback.format_exc()}")

    def get_closed_positions(self, since_epoch: float, until_epoch: float | None = None) -> list[dict]:
        """Positions de CE système (magic) sur `self.symbol` entièrement clôturées entre les deux
        dates, reconstruites depuis l'historique des deals MT5 (source de vérité)."""
        from datetime import datetime as _dt
        mt5 = self._mt5
        until_epoch = until_epoch or (time.time() + 2 * 86400)
        with self._lock:
            deals = mt5.history_deals_get(_dt.fromtimestamp(since_epoch), _dt.fromtimestamp(until_epoch))
        if deals is None:
            return []
        by_pos: dict[int, list] = {}
        for d in deals:
            if getattr(d, "magic", None) != MAGIC_NUMBER or getattr(d, "symbol", None) != self.symbol:
                continue
            by_pos.setdefault(int(d.position_id), []).append(d)
        entry_in = getattr(mt5, "DEAL_ENTRY_IN", 0)
        reasons = {getattr(mt5, "DEAL_REASON_SL", 4): "SL", getattr(mt5, "DEAL_REASON_TP", 5): "TP",
                   getattr(mt5, "DEAL_REASON_SO", 6): "STOP_OUT", getattr(mt5, "DEAL_REASON_EXPERT", 3): "IA",
                   getattr(mt5, "DEAL_REASON_CLIENT", 0): "MANUEL", getattr(mt5, "DEAL_REASON_MOBILE", 1): "MANUEL",
                   getattr(mt5, "DEAL_REASON_WEB", 2): "MANUEL"}
        out = []
        for pid, ds in by_pos.items():
            ds.sort(key=lambda d: d.time_msc)
            ins = [d for d in ds if d.entry == entry_in]
            outs = [d for d in ds if d.entry != entry_in]
            if not ins or not outs:
                continue
            vin, vout = sum(d.volume for d in ins), sum(d.volume for d in outs)
            if vout + 1e-9 < vin:
                continue  # encore partiellement ouverte
            first = ins[0]
            sl = tp = None
            try:
                with self._lock:
                    orders = mt5.history_orders_get(position=pid) or []
                for o in orders:
                    if getattr(o, "sl", 0):
                        sl = float(o.sl); tp = float(o.tp) or None
                        break
            except Exception:
                pass
            out.append({
                "position_id": pid, "comment": first.comment,
                "style": _parse_style_from_comment(first.comment),
                "generation": _parse_generation_from_comment(first.comment),
                "direction": 1 if first.type == mt5.ORDER_TYPE_BUY else -1, "volume": float(vin),
                "open_epoch": int(first.time), "open_price": float(first.price),
                "close_epoch": int(outs[-1].time),
                "close_price": float(sum(d.price * d.volume for d in outs) / vout),
                "profit": float(sum(d.profit for d in ds)), "commission": float(sum(d.commission for d in ds)),
                "swap": float(sum(d.swap for d in ds)), "sl": sl, "tp": tp,
                "close_reason": reasons.get(getattr(outs[-1], "reason", None), str(getattr(outs[-1], "reason", "?"))),
            })
        return out

    def get_price_path(self, open_epoch: int, close_epoch: int, timeframe: str = "M5"):
        """(plus haut, plus bas) atteints entre l'ouverture et la clôture (bougies `timeframe`).
        Les heures des bougies et des deals sont toutes deux en heure serveur : on filtre sur les
        epochs bruts plutôt que de convertir des fuseaux."""
        from datetime import datetime as _dt
        with self._lock:
            rates = self._mt5.copy_rates_range(self.symbol, getattr(self._mt5, _TF_ATTR[timeframe]),
                                               _dt.fromtimestamp(open_epoch - 2 * 86400),
                                               _dt.fromtimestamp(close_epoch + 2 * 86400))
        if rates is None or len(rates) == 0:
            return None
        step = {"M1": 60, "M5": 300, "M15": 900, "H1": 3600}.get(timeframe, 300)
        sel = [r for r in rates if r["time"] + step > open_epoch and r["time"] <= close_epoch]
        if not sel:
            return None
        return float(max(r["high"] for r in sel)), float(min(r["low"] for r in sel))

    def _log_execution(self, request: dict, result, style: str | None, leg: str,
                       position_ticket: int | None = None):
        """Journal d'exécution (audit institutionnel, section 6 -- gap
        slippage réel/simulé) : compare, pour CHAQUE ordre réel envoyé
        (ouverture ET clôture), le prix DEMANDÉ (`request["price"]`, lu
        juste avant l'envoi) au prix RÉELLEMENT rempli par MT5
        (`result.price`) -- append-only dans EXECUTION_LOG_PATH (un JSON
        par ligne). CONVENTION DE SIGNE : `slippage` = filled - requested,
        SIGNÉ tel quel (pas ajusté selon le sens BUY/SELL) ; `direction`
        (1=achat, -1=vente) est journalisé à côté pour que l'analyse en aval
        (voir scripts/slippage_report.py) puisse interpréter correctement
        "pire que demandé" selon le sens (pour un achat, filled > requested
        est défavorable ; pour une vente, c'est l'inverse). Best-effort
        total : toute exception ici est avalée -- ne doit JAMAIS interrompre
        le flux d'ordre réel, qui a déjà eu lieu au moment où cette méthode
        est appelée."""
        try:
            requested_price = request.get("price")
            filled_price = getattr(result, "price", None)
            retcode = getattr(result, "retcode", None)
            slippage = (float(filled_price) - float(requested_price)
                        if filled_price and requested_price else None)
            slippage_pct = (slippage / requested_price
                             if slippage is not None and requested_price else None)
            record = {
                "timestamp": time.time(), "symbol": self.symbol, "style": style, "leg": leg,
                "direction": 1 if request.get("type") == self._mt5.ORDER_TYPE_BUY else -1,
                "volume": request.get("volume"), "requested_price": requested_price,
                "filled_price": filled_price, "slippage": slippage, "slippage_pct": slippage_pct,
                "retcode": retcode,
            }
            os.makedirs(os.path.dirname(EXECUTION_LOG_PATH), exist_ok=True)
            with open(EXECUTION_LOG_PATH, "a", encoding="utf-8") as f:
                f.write(json.dumps(record) + "\n")
            report = getattr(self, "last_order_report", None)
            if report is not None:
                adverse = (slippage * record["direction"]) if slippage is not None else None
                report["legs"].append({
                    "leg": leg, "direction": record["direction"], "volume_req": request.get("volume"),
                    "price_req": requested_price, "price_filled": filled_price, "slippage": slippage,
                    "adverse_slippage": adverse, "sl_req": request.get("sl"), "tp_req": request.get("tp"),
                    "retcode": retcode, "position_ticket": position_ticket,
                    "latency_ms": getattr(self, "_last_send_ms", None) if result is not None else None,
                    "volume_filled": getattr(result, "volume", None) if result is not None else None,
                })
        except Exception:
            pass  # journal de diagnostic best-effort -- ne bloque jamais le flux d'ordre réel

    def _notify_trade_opened(self, direction: int, volume: float, stop_pct: float | None, simulated: bool):
        """Alerte best-effort à l'ouverture d'une position -- réelle OU
        simulée (dry-run) : en dry-run (le mode par défaut pendant toute la
        phase de validation), ne pas alerter du tout laisserait l'utilisateur
        sans aucune visibilité sur l'activité de trading pendant des
        semaines. Le message précise TOUJOURS s'il s'agit d'un ordre réel ou
        d'une simulation, jamais ambigu."""
        try:
            from src.notifier import send_alert
            sens = "ACHAT" if direction == 1 else "VENTE"
            tag = "[SIMULATION dry-run]" if simulated else "[ORDRE RÉEL]"
            stop_note = f", stop={stop_pct:.2%}" if stop_pct is not None else ""
            send_alert(self._full_cfg, subject=f"Test_IA - {tag} {sens} {self.symbol}",
                       message=f"{tag} {sens} {volume} lot(s) sur {self.symbol}{stop_note}.")
        except Exception:
            pass

    def disconnect(self):
        if self._mt5:
            self._mt5.shutdown()
