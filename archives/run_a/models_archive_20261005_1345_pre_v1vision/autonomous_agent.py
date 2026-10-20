"""
autonomous_agent.py
=====================
Point d'entrée UNIQUE de ce projet. Une seule commande lance une IA de
trading qui s'auto-alimente en données (fusion multi-timeframe), s'entraîne,
se valide, se déploie en démo, ET continue de se perfectionner indéfiniment
pendant qu'elle tourne. Il n'y a pas d'autre script d'entraînement : tout
passe par ici, pour éviter tout conflit entre plusieurs pipelines ou
plusieurs configurations.

    python autonomous_agent.py
    Ctrl+C pour arrêter proprement.

Deux boucles tournent en parallèle :
  1. ÉVOLUTION CONTINUE (src/continuous_trainer.py, thread "EVOLUTION") :
     rafraîchit les données, fait progresser plusieurs LIGNÉES de champions
     EN PARALLÈLE -- un "style" de trading par timeframe primaire du pool
     configuré (`data.timeframe_pool`, ex: scalping sur M15, swing sur D1) --
     chacune avec son propre contexte multi-timeframe automatiquement dérivé
     de toutes les timeframes plus larges disponibles. Ne s'arrête jamais.
  2. TRADING EN DÉMO (src/demo_trader.py, thread principal) : utilise en
     permanence la MEILLEURE lignée actuelle (celle qui a passé les seuils
     de qualité, quel que soit son style) pour décider, sur le compte MT5
     de démonstration déjà connecté dans votre terminal.

SÉLECTIVITÉ DES MODÈLES ENVOYÉS EN DÉMO :
  Un agent n'est utilisé en démo QUE s'il passe les seuils de qualité
  définis dans `validation` (Sharpe minimum, drawdown maximum) ET que le
  nombre minimal de cycles d'entraînement configuré a été atteint
  (`validation.min_generations_before_demo`). Voir src/continuous_trainer.py.

VOLUME DE DONNÉES ADAPTÉ AUX HEURES DE MARCHÉ :
  Pendant la fermeture du marché XAUUSD (week-end), le système entraîne sur
  BEAUCOUP plus d'historique d'un coup (voir `data.max_bars_market_closed`
  et `market_hours` dans la config) puisque rien ne presse et que le CPU
  n'est pas sollicité par des décisions de trading en direct.

SÉCURITÉ :
  - Aucun ordre réel n'est jamais envoyé automatiquement sur un compte qui
    n'est pas détecté comme compte de DÉMONSTRATION (vérifié auprès de
    MT5 à la connexion). Voir src/mt5_connector.py.
  - `live.dry_run` reste à `true` par défaut même sur un compte démo : vous
    observez d'abord les décisions avant de les laisser s'exécuter.
"""
from __future__ import annotations
import argparse
import os
import threading
import logging
import time
import webbrowser
import yaml
import pandas as pd

from src.continuous_trainer import ContinuousEvolutionTrainer
from src.demo_trader import run_demo_trading_loop, _scan_eligible_styles
from src.data_loader import chronological_split, split_lockbox, default_lockbox_start, load_kaggle_ohlcv_csv
from src.features import add_technical_features, normalize_features, FEATURE_COLUMNS
from src.fundamental_feed import AutoFundamentalFeed
from src.multi_timeframe import discover_files, verify_timeframe_assignment, build_mtf_dataset, TF_ORDER
from src.market_hours import is_market_open
from src.trading_env import TradingEnv
from src.style_utils import base_timeframe

# MINUTES PAR BOUGIE, par timeframe -- sert UNIQUEMENT à convertir
# `data.embargo_hours` (audit institutionnel, section 1 -- "Embargo : 24 à
# 48 heures") en un nombre de BOUGIES pour ce style précis (voir
# make_data_provider::get_data) : 24h représente 96 bougies en M15 mais
# seulement 1 en D1 -- une valeur unique en bougies n'aurait aucun sens
# appliquée uniformément à tous les styles du pool.
_MINUTES_PER_BAR = {
    "M1": 1, "M5": 5, "M15": 15, "M30": 30, "H1": 60, "H4": 240,
    "D1": 1440, "W1": 10080, "MN1": 43200,
}

# FICHIER DE LOG ÉCRIT DIRECTEMENT PAR PYTHON (18/09, remplace la redirection
# shell `*>> logs\autonomous_agent.log` faite par scripts/run_forever.ps1) :
# PowerShell (aussi bien `*>>` que `Out-File -Encoding utf8` en Append)
# réencode/reformate ce qu'il redirige -- avec les propres lignes de statut
# du watchdog ÉCRITES DANS LE MÊME FICHIER via un mécanisme différent
# (Out-File), les deux sources finissaient mélangées avec des encodages
# incompatibles entre elles, rendant des blocs entiers du fichier illisibles
# (mojibake, parfois un bloc entier en UTF-16 mal interprété comme UTF-8).
# Écrire le fichier nous-mêmes, avec un encodage explicite et cohérent,
# élimine le problème à la racine -- plus aucune réinterprétation par un
# shell intermédiaire. Le flux stderr (StreamHandler par défaut) reste actif
# pour qui lance le script à la main dans un terminal.
os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(threadName)s] [%(name)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("logs/autonomous_agent.log", encoding="utf-8"),
    ],
)
log = logging.getLogger("autonomous_agent")


def _resolve_max_bars(primary_tf: str, base_max_bars, max_bars_by_style: dict):
    """Détermine le plafond de bougies à utiliser pour CE style : la
    surcharge par style (`data.max_bars_by_style`, voir make_data_provider)
    l'emporte sur le plafond global, SAUF si le plafond de base est déjà
    "illimité" (None, cas typique de `max_bars_market_closed`) -- ne jamais
    RÉDUIRE ce qui est déjà prévu pour la fermeture du marché avec une
    surcharge pensée pour le cas normal (marché ouvert)."""
    override = max_bars_by_style.get(primary_tf)
    if override and base_max_bars is not None:
        return override
    return base_max_bars


def make_data_provider(cfg: dict):
    """Fournisseur de données UNIQUE pour la boucle d'évolution continue,
    avec support de PLUSIEURS "styles" de trading (un par timeframe primaire
    du pool configuré -- `data.timeframe_pool`). Pour un style donné, le
    contexte multi-timeframe est dérivé AUTOMATIQUEMENT : toutes les
    timeframes disponibles strictement plus larges que la primaire choisie
    (ex: style "M15" -> contexte M30/H1/H4/D1/W1/MN1 si tous sont présents ;
    style "D1" -> contexte W1/MN1 seulement). C'est ce qui permet une
    analyse multi-couche cohérente aussi bien pour un style scalping que
    pour un style swing, sans dupliquer la configuration.

    Le volume de données utilisé (`max_bars`) s'adapte automatiquement aux
    heures de marché : normal pendant les heures d'ouverture, étendu (voire
    illimité) pendant la fermeture du marché (voir market_hours.py).

    Retourne (get_data_fn, timeframe_pool) où get_data_fn(primary_tf)
    retourne (train_df, val_df, stats, feature_columns, context_timeframes)
    pour le style demandé.
    """
    data_cfg = cfg["data"]
    folder = data_cfg["folder"]
    timeframe_pool = data_cfg.get("timeframe_pool") or [data_cfg.get("primary_timeframe", "H1")]
    max_bars_open = data_cfg.get("max_bars", 40000)
    max_bars_closed = data_cfg.get("max_bars_market_closed", 0) or None  # None = illimité
    # SURCHARGE PAR STYLE (voir `data.max_bars_by_style`) : les timeframes
    # COURTES (M15, H1...) ont des CENTAINES DE MILLIERS de bougies
    # disponibles mais utilisaient jusqu'ici le MÊME plafond que D1/H4, qui,
    # eux, ont si peu de bougies au total que ce plafond ne les limite déjà
    # PAS (ils voient 100% de leur historique). Résultat : M15 n'apprenait
    # que sur une petite tranche récente (quelques années sur les 14+
    # disponibles) -- beaucoup moins de diversité de régimes de marché que
    # D1, ce qui explique une bonne partie de l'écart de score observé.
    # Cette surcharge permet de donner PLUS d'historique spécifiquement aux
    # styles qui en profitent, sans ralentir ceux qui sont déjà saturés
    # (H4/D1 : augmenter leur plafond ne changerait rien, ils sont déjà
    # bornés par leurs données, pas par ce réglage).
    max_bars_by_style = data_cfg.get("max_bars_by_style") or {}

    files = discover_files(folder)
    missing = [tf for tf in timeframe_pool if base_timeframe(tf) not in files]
    if missing:
        raise SystemExit(
            f"Timeframes du pool introuvables dans '{folder}' : {missing}. "
            f"Timeframes détectées : {sorted(files.keys())}. "
            f"Vérifiez data.timeframe_pool dans config/autonomous.yaml."
        )

    log.info(f"Fichiers multi-timeframe détectés dans '{folder}' :")
    report = verify_timeframe_assignment(files)
    any_suspect = False
    for tf, r in report.items():
        if "error" in r:
            log.warning(f"  [!] {tf}: erreur de lecture -> {r['error']}")
            any_suspect = True
            continue
        status = "OK" if r["ok"] else "SUSPECT"
        if not r["ok"]:
            any_suspect = True
        log.info(f"  [{status}] {tf} ({r['file']}) : attendu ~{r['expected_minutes']} min/bougie, "
                  f"observé ~{r['observed_minutes']} min/bougie")
    if any_suspect:
        log.warning("Au moins une timeframe semble mal associée (voir ci-dessus). "
                    "Le système continue, mais vérifiez vos fichiers si les résultats sont mauvais.")

    log.info(f"Pool de styles de trading : {timeframe_pool} "
              f"(le contexte de chaque style = toutes les timeframes plus larges disponibles).")

    fundamental_feed = AutoFundamentalFeed(cfg) if cfg.get("fundamental", {}).get("enabled") else None
    # un cache par STYLE (primary_tf), invalidé si les fichiers changent sur
    # disque OU si le volume de données à utiliser change (ouverture/fermeture)
    caches: dict[str, dict] = {}

    def _folder_mtime():
        return max((os.path.getmtime(p) for p in files.values()), default=0)

    def _context_for(primary_tf: str) -> list[str]:
        idx = TF_ORDER.index(primary_tf)
        return [tf for tf in TF_ORDER[idx + 1:] if tf in files]

    cross_styles = set(data_cfg.get("cross_asset_styles") or [])
    cross_folder = data_cfg.get("cross_asset_folder") or os.path.join(os.path.dirname(os.path.abspath(folder)), "cross_asset")

    def _cache_key(style: str) -> str:
        return style if style in cross_styles else base_timeframe(style)

    def _rebuild(style: str, max_bars):
        primary_tf = base_timeframe(style)
        context_tfs = _context_for(primary_tf)
        log.info(f"(Re)construction du dataset du style '{style}' (contexte {context_tfs}, "
                  f"max_bars={max_bars or 'illimité'})...")
        df, mtf_columns = build_mtf_dataset(files, primary_tf=primary_tf,
                                             context_tfs=context_tfs, max_bars=max_bars)
        df = add_technical_features(df, fundamental_feed=fundamental_feed, refresh_fundamental=True)
        x_columns = []
        if style in cross_styles:
            from src import cross_asset
            cross_asset.refresh_daily_csv(cross_folder)
            fred = getattr(fundamental_feed, "_fred", None)
            df = cross_asset.add_cross_asset_features(
                df, fred=fred, daily_provider=cross_asset.csv_daily_provider(cross_folder))
            x_columns = list(cross_asset.X_COLUMNS)
            n_live = sum(1 for c in x_columns if float(df[c].abs().sum()) > 0)
            log.info(f"Variables hors XAUUSD du style '{style}' : {n_live}/{len(x_columns)} actives.")
        # ATR BRUT (audit institutionnel, item "Stop Loss basé sur l'ATR") :
        # copie de `atr_14` HORS de `FEATURE_COLUMNS`/`cache["cols"]` (donc
        # jamais normalisée par normalize_features ci-dessous, jamais vue
        # par l'agent comme feature d'observation) -- voir
        # TradingEnv.ATR_RAW_COLUMN/_atr_price_units. Ajoutée UNE FOIS ici
        # (pas à chaque appel de get_data) : survit ensuite intacte à
        # chronological_split, à tout sous-découpage walk-forward
        # (backtester.py) et aux scénarios de stress (src/stress_test.py),
        # puisqu'elle voyage comme une colonne ordinaire de `df`.
        if "atr_14" in df.columns:
            df[TradingEnv.ATR_RAW_COLUMN] = df["atr_14"]
        caches[_cache_key(style)] = {
            "mtime": _folder_mtime(), "max_bars": max_bars, "df": df,
            "cols": FEATURE_COLUMNS + mtf_columns + x_columns, "context_tfs": context_tfs,
        }
        log.info(f"Dataset '{style}' prêt : {len(df)} bougies, "
                  f"{len(caches[_cache_key(style)]['cols'])} features.")

    # VERROUILLAGE ANTI-DATA-LEAKAGE (audit institutionnel, section 1,
    # standard Marcos López de Prado) : voir src/data_loader.py::
    # chronological_split pour l'implémentation. `purge_bars` (défaut 50,
    # même valeur que la plus longue fenêtre glissante utilisée dans
    # src/features.py -- sma_50/volatility_regime) supprime les bougies aux
    # frontières exactes train/val et val/test dont les indicateurs
    # techniques glissants pourraient chevaucher la période suivante.
    # `embargo_hours` (défaut 24, "24 à 48 heures" du cahier des charges)
    # est converti en BOUGIES séparément pour chaque style (voir
    # _MINUTES_PER_BAR) -- 24h ne représente pas le même nombre de bougies
    # en M15 qu'en D1. 0/null désactive chacun des deux indépendamment
    # (comportement d'origine, aucun espace entre les découpes).
    purge_bars = data_cfg.get("purge_bars", 50)
    embargo_hours = data_cfg.get("embargo_hours", 24)

    def _embargo_bars_for(primary_tf: str) -> int:
        if not embargo_hours:
            return 0
        minutes_per_bar = _MINUTES_PER_BAR.get(primary_tf, 60)
        return max(1, round(embargo_hours * 60 / minutes_per_bar))

    # JEU SOUS CLÉ (LOT 2, phase 1) : date calendaire UNIQUE pour tous les
    # symboles/timeframes -- jamais servie à l'entraînement, la validation,
    # le walk-forward ni la promotion (voir src/data_loader.py::split_lockbox,
    # scripts/lockbox_eval.py pour l'évaluer explicitement). Résolue UNE FOIS
    # ici (pas par style) : `data.lockbox_start` explicite dans la config, ou
    # par défaut les 15% les plus récents de l'historique or, arrondis au
    # début du mois.
    lockbox_start_cfg = data_cfg.get("lockbox_start")
    if lockbox_start_cfg:
        lockbox_start = pd.Timestamp(lockbox_start_cfg)
    else:
        default_source_tf = "D1" if "D1" in files else next(iter(files))
        ref_df = load_kaggle_ohlcv_csv(files[default_source_tf])
        lockbox_start = default_lockbox_start(ref_df)
    log.info(f"Jeu sous clé (lockbox) : données à partir du {lockbox_start.date()} exclues de "
              f"l'entraînement/validation/walk-forward/promotion (voir data.lockbox_start, "
              f"scripts/lockbox_eval.py).")

    def get_data(style: str):
        primary_tf = base_timeframe(style)
        base_max_bars = max_bars_open if is_market_open(cfg) else max_bars_closed
        max_bars = _resolve_max_bars(style if style in max_bars_by_style else primary_tf, base_max_bars, max_bars_by_style)
        key = _cache_key(style)
        cache = caches.get(key)
        if cache is None or cache["mtime"] != _folder_mtime() or cache["max_bars"] != max_bars:
            _rebuild(style, max_bars)
            cache = caches[key]
        df = cache["df"]
        embargo_bars = _embargo_bars_for(primary_tf)
        visible_df, _ = split_lockbox(df, lockbox_start, purge_bars=purge_bars, embargo_bars=embargo_bars)
        # GARDE-FOU (trouvé lors de l'essai à blanc LOT 2, phase 7) : la date
        # de lockbox est UNIQUE pour tous les styles, mais leur FENÊTRE de
        # données réellement utilisée ne l'est pas (`max_bars`/
        # `max_bars_by_style` -- un style scalp comme M15 ne voit souvent
        # qu'une fraction récente de l'historique complet dont la date de
        # lockbox a été calculée). Si ça laisse ce style SANS AUCUNE donnée
        # visible (son historique utilisé est déjà entièrement postérieur à
        # la date de lockbox), appliquer quand même le lockbox planterait
        # l'entraînement -- désactivé pour CE style/cycle uniquement, avec un
        # avertissement clair, plutôt qu'une exception qui interromprait tout
        # le cycle.
        min_usable_bars = 100
        if len(visible_df) < min_usable_bars:
            log.warning(f"[lockbox] style '{primary_tf}' : seulement {len(visible_df)} bougie(s) visible(s) "
                        f"avant le {lockbox_start.date()} (fenêtre de données de ce style trop récente par "
                        f"rapport à la date de lockbox commune) -- lockbox DÉSACTIVÉ pour ce style/ce cycle "
                        f"uniquement (retombe sur l'historique complet disponible pour ce style).")
            visible_df = df
        train_df, val_df, _ = chronological_split(
            visible_df, data_cfg["train_ratio"], data_cfg["val_ratio"],
            purge_bars=purge_bars, embargo_bars=embargo_bars)
        train_df, stats = normalize_features(train_df, columns=cache["cols"])
        val_df, _ = normalize_features(val_df, stats, columns=cache["cols"])
        return train_df, val_df, stats, cache["cols"], cache["context_tfs"]

    return get_data, timeframe_pool


def _start_live_feed(cfg: dict, no_demo: bool):
    """Démarre l'alimentation live des données historiques (voir
    src/live_data_feed.py) -- que la démo tourne ou non. Sans ça, les CSV
    de `data.folder` restent GELÉS à la date où ils ont été téléchargés, et
    l'évolution continue réapprendrait indéfiniment sur le MÊME passé,
    même en mode --no-demo, jusqu'à stagner. Tente une connexion MT5
    UNIQUEMENT pour récupérer des bougies fraîches (jamais pour envoyer un
    ordre) : en --no-demo, aucun ordre n'est de toute façon jamais envoyé,
    donc cette connexion est sans risque même sans compte démo confirmé.

    Retourne (live_feed, connector) -- connector est réutilisable par
    run_demo_trading_loop pour éviter une deuxième connexion ; les deux
    valent (None, None) si MT5 n'est pas disponible ou la fonctionnalité
    désactivée (`data.live_feed_enabled: false`) -- dégradation silencieuse,
    en particulier attendue en --no-demo sans MT5 installé.
    """
    if not cfg.get("data", {}).get("live_feed_enabled", True):
        return None, None
    try:
        from src.mt5_connector import MT5Connector
        from src.live_data_feed import LiveDataFeed
        connector = MT5Connector(cfg)
        connector.connect()
        files = discover_files(cfg["data"]["folder"])
        live_feed = LiveDataFeed(cfg, connector, files)
        threading.Thread(target=live_feed.run_forever, name="LIVE_FEED", daemon=True).start()
        log.info(f"Alimentation live des données historiques lancée en arrière-plan "
                  f"(rafraîchissement toutes les {live_feed.refresh_minutes} min) -- "
                  f"les CSV de '{cfg['data']['folder']}' resteront à jour avec le marché réel"
                  f"{' (malgré --no-demo, uniquement pour garder les données à jour)' if no_demo else ''}.")
        return live_feed, connector
    except Exception as e:
        suffix = " (normal si MT5 n'est pas installé ici)" if no_demo else ""
        log.info(f"Alimentation live indisponible ({type(e).__name__}: {e}) -> entraînement sur les "
                  f"CSV existants uniquement, sans données fraîches{suffix}.")
        return None, None


def _open_dashboard(cfg: dict):
    """Ouvre reports/dashboard.html dans le navigateur par défaut au
    démarrage, pour ne pas avoir à se souvenir du chemin ni à le rouvrir
    manuellement à chaque lancement -- voir src/dashboard.py.
    Mettez `dashboard.auto_open: false` dans la config pour désactiver.
    Ne lève jamais d'exception visible : un navigateur qui ne s'ouvre pas
    ne doit jamais empêcher le système de démarrer.
    """
    if not cfg.get("dashboard", {}).get("auto_open", True):
        return
    try:
        from src.dashboard import render, DASHBOARD_PATH
        render()  # génère un premier dashboard (même vide) s'il n'existe pas encore
        path = os.path.abspath(DASHBOARD_PATH)
        webbrowser.open(f"file:///{path.replace(os.sep, '/')}")
        log.info(f"Tableau de bord ouvert dans le navigateur ({path}).")
    except Exception as e:
        log.info(f"Impossible d'ouvrir automatiquement le tableau de bord "
                  f"({type(e).__name__}: {e}) -- ouvrez reports/dashboard.html manuellement.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config/autonomous.yaml")
    parser.add_argument("--no-demo", action="store_true",
                         help="N'exécute que la boucle d'évolution continue, sans trading en démo "
                              "(utile pour laisser le système apprendre avant de le connecter à MT5).")
    parser.add_argument("--no-train", action="store_true",
                         help="N'exécute QUE la boucle de démo (aucune évolution continue en arrière-plan) "
                              "-- donne toute la machine à la décision de démo. Utile en diagnostic ponctuel "
                              "pour vérifier si l'entraînement affame la démo en CPU ; les champions déjà "
                              "promus restent inchangés et utilisables, seule la PROGRESSION future est "
                              "gelée tant que ce mode est actif.")
    args = parser.parse_args()
    if args.no_demo and args.no_train:
        parser.error("--no-demo et --no-train ne peuvent pas être combinés (il ne resterait plus rien à faire).")

    with open(args.config, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    # PROFIL DE RISQUE (voir src/risk_profile.py, config/risk_profiles/) :
    # si `live.risk_profile` est réglé (ex: "ftmo_2step"), écrase les seuils
    # de risque ci-dessous avant tout le reste -- si absent, ne change RIEN
    # (comportement d'origine). Choix du profil volontairement PAS éditable
    # en direct (voir settings_server.py) : à changer ici et redémarrer.
    from src.risk_profile import apply_risk_profile
    apply_risk_profile(cfg)

    # SAC/TD3 (voir agent.algo) apprennent une action CONTINUE (intensité de
    # position, pas juste sa direction) -- PPO reste discret. Dérivé
    # automatiquement de l'algorithme choisi, pas un réglage séparé qui
    # pourrait finir en incohérence avec lui.
    continuous_action = str(cfg["agent"].get("algo", "PPO")).upper() in ("SAC", "TD3")

    env_kwargs = dict(
        window_size=cfg["environment"]["window_size"],
        initial_balance=cfg["environment"]["initial_balance"],
        transaction_cost=cfg["environment"]["transaction_cost"],
        reward_type=cfg["environment"]["reward_type"],
        drawdown_penalty=cfg["environment"]["drawdown_penalty"],
        max_position=cfg["environment"]["max_position"],
        continuous_action=continuous_action,
        spread_volatility_multiplier=cfg["environment"].get("spread_volatility_multiplier", 1.0),
        # Stop-loss décidé par l'agent lui-même (voir config/autonomous.yaml,
        # section agent, et src/trading_env.py) -- étend l'espace d'action
        # pour que l'agent choisisse sa propre distance de stop par position,
        # au lieu d'un pourcentage fixe imposé de l'extérieur.
        learn_stop_loss=cfg["agent"].get("learn_stop_loss", False),
        stop_loss_buckets=cfg["agent"].get("stop_loss_buckets"),
        stop_loss_range=tuple(cfg["agent"].get("stop_loss_range", (0.003, 0.06))),
        # STOP-LOSS ATR (audit institutionnel, section 2, item "Calcul de
        # Stop Loss Cohérent") : voir src/trading_env.py -- les buckets de
        # stop deviennent des multiples de l'ATR courant plutôt que des
        # fractions fixes du prix. Actif par défaut (True, comme le défaut
        # de TradingEnv lui-même) -- n'a d'effet que si `raw_atr`/la colonne
        # `atr_14_raw` est disponible (voir make_data_provider ci-dessus) ET
        # `agent.learn_stop_loss: true` ; sinon repli silencieux sur les
        # buckets statiques (comportement d'origine).
        atr_stop_loss=cfg["agent"].get("atr_stop_loss", True),
        # SPREAD SESSION/HEURE (audit institutionnel, section 3, item
        # "Modélisation du Spread Dynamique") : voir src/trading_env.py --
        # élargit le coût de transaction selon l'heure UTC (rollover, session
        # asiatique peu liquide...). Actif par défaut, neutre si le
        # dataframe n'a pas de colonne "time".
        session_spread_enabled=cfg["environment"].get("session_spread_enabled", True),
        session_spread_multipliers=cfg["environment"].get("session_spread_multipliers"),
        # PÉNALITÉ D'INACTIVITÉ (23/09, voir src/trading_env.py::__init__
        # pour le rationale complet) : 0.0 par défaut (comportement
        # d'origine inchangé) tant que non explicitement réglé.
        inactivity_penalty_coef=cfg["environment"].get("inactivity_penalty_coef", 0.0),
    )

    log.info("=== Démarrage du système autonome ===")

    # RÉGLAGES ÉDITABLES EN DIRECT (voir src/settings_server.py) : réapplique
    # d'abord ce qui a été changé depuis le tableau de bord lors d'un
    # lancement précédent (data/settings_overrides.json), PUIS démarre le
    # petit serveur local qui permet de continuer à les modifier sans
    # redémarrer. Uniquement un sous-ensemble volontairement restreint et
    # sûr (risque, fréquences, dry-run, notifications) -- jamais
    # l'architecture du modèle. `cfg` est le MÊME dictionnaire partagé par
    # l'entraînement continu et la boucle de démo : un changement via ce
    # serveur y est donc visible immédiatement, partout.
    from src.settings_server import start_server
    settings_port = cfg.get("dashboard", {}).get("settings_port", 8765)
    start_server(cfg, port=settings_port)

    _open_dashboard(cfg)

    live_feed, live_feed_connector = _start_live_feed(cfg, no_demo=args.no_demo)

    get_data_fn, timeframe_pool = make_data_provider(cfg)
    trainer = ContinuousEvolutionTrainer(cfg, get_data_fn, timeframe_pool, env_kwargs)

    if args.no_train:
        log.warning("Mode --no-train : évolution continue GELÉE (diagnostic ponctuel). Les champions déjà "
                     "promus restent utilisés tels quels par la démo -- aucune progression tant que ce mode "
                     "est actif. Relancez sans ce drapeau pour reprendre l'entraînement normalement.")
    else:
        log.info("Boucle d'évolution continue lancée en arrière-plan (ne s'arrête jamais).")
        train_thread = threading.Thread(
            target=trainer.run_forever,
            kwargs={"cycle_interval_seconds": cfg["continuous"].get("cycle_interval_seconds", 60)},
            name="EVOLUTION", daemon=True,
        )
        train_thread.start()

    if args.no_demo:
        log.info("Mode --no-demo : entraînement en arrière-plan uniquement, pas de démo. "
                  "Ctrl+C pour arrêter.")
        try:
            while True:
                time.sleep(3600)
        except KeyboardInterrupt:
            pass
        finally:
            if live_feed:
                live_feed.stop()
    else:
        # Réutilise le connecteur MT5 de l'alimentation live s'il a pu se
        # connecter ci-dessus (une seule connexion partagée) ; sinon
        # run_demo_trading_loop en crée un pour son propre usage.
        connector = live_feed_connector

        log.info("En attente d'un premier agent qui PASSE LA VALIDATION avant de démarrer la démo "
                  "(un agent qui ne passe pas les seuils, ou qui n'a pas encore atteint le nombre "
                  "minimal de générations requis, continue de s'entraîner en arrière-plan mais n'est "
                  "jamais envoyé en démo)...")
        waited = 0
        min_gen = cfg.get("validation", {}).get("min_generations_before_demo", 20)
        # `has_demo_champion()` ne teste QUE l'ancien mécanisme à champion
        # unique (models/demo_champion/) -- avec l'ensemble multi-styles
        # (live.ensemble, activé par défaut), un style peut être
        # individuellement éligible (voir _scan_eligible_styles) SANS que ce
        # champion unique existe jamais (ex: le meilleur score BRUT du pool
        # échoue sur le drawdown alors qu'un autre style, moins bon en score
        # mais dans les clous, passe déjà). Sans ce second test, cette
        # boucle attendrait indéfiniment un événement qui peut ne jamais
        # arriver, alors même que la démo aurait de quoi démarrer -- bug
        # réel trouvé le 14/09 après 1h30 sans aucune décision malgré H1
        # déjà marqué éligible.
        while not trainer.has_demo_champion() and not _scan_eligible_styles(cfg):
            time.sleep(5)
            waited += 5
            if waited % 60 == 0:
                status = trainer.status_summary(min_gen)
                log.info(f"... toujours en attente ({waited}s écoulées, {status}).")
        log.info("Premier champion DÉMO disponible (a passé la validation).")
        log.info("Démarrage du trading en démo (utilise toujours la meilleure lignée validée, "
                  "quel que soit son style -- primaire/contexte lus dynamiquement à chaque rechargement).")
        try:
            run_demo_trading_loop(cfg, env_kwargs, connector=connector)
        except KeyboardInterrupt:
            log.info("Arrêt demandé par l'utilisateur.")
        finally:
            if live_feed:
                live_feed.stop()

    trainer.stop()
    trainer.close()
    log.info("Système arrêté proprement.")


if __name__ == "__main__":
    main()
