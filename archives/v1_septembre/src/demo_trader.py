"""
demo_trader.py
===============
Boucle de trading en démonstration continue.

ENSEMBLE MULTI-STYLES (voir `live.ensemble`, activé par défaut) : plusieurs
styles (scalping, swing...) peuvent désormais être ÉLIGIBLES SIMULTANÉMENT
(chacun ayant individuellement passé les seuils de qualité -- voir le champ
`passes_validation` écrit par src/continuous_trainer.py dans le meta.json de
chaque champion technique). La décision finale est une MOYENNE PONDÉRÉE
(par score) des positions cibles de chaque style éligible, ce qui produit
une exposition CONTINUE plutôt qu'un simple -1/0/1 :
  - si tous les styles éligibles sont d'accord sur la direction, l'exposition
    finale est pleine (proche de ±1) ;
  - s'ils sont en désaccord, l'exposition se rapproche de 0 -- la taille de
    la position reflète donc la CONFIANCE (l'accord) de l'ensemble, au lieu
    de trader plein pot sur un signal incertain.
Avec `live.ensemble: false`, ou tant qu'aucun style ne passe encore
individuellement la validation, on retombe sur l'ancien comportement
"gagnant unique" (models/demo_champion/, voir continuous_trainer.py).

Dans les deux cas, la timeframe primaire, les timeframes de contexte et les
colonnes de features utilisées ne sont JAMAIS fixées au démarrage : elles
sont relues depuis le meta.json de chaque style à chaque rechargement.

SÉCURITÉ (voir aussi src/mt5_connector.py) : n'envoie jamais d'ordre réel
sur un compte qui n'est pas détecté comme compte de démonstration, sauf
activation explicite de `live.allow_real_account` dans la config.
"""
from __future__ import annotations
import os
import json
import time
import logging
import traceback
import numpy as np

from src.trading_env import TradingEnv, ENV_VERSION, env_version_matches, EnvVersionMismatch
from src.multi_asset import GOLD_SYMBOL
from src.agent import TradingAgent
from src.features import add_technical_features, normalize_features
from src.multi_timeframe import fuse_mtf_frames
from src.continuous_trainer import (
    DEMO_MODEL, DEMO_META, DEMO_STATS, _champion_meta, _champion_model, _champion_stats, _champion_dir,
)
from src.risk_guard import anomaly_scale
from src.reliability_tracker import compute_reliability_report, save_report
from src.dashboard import write_live_status
from src.market_hours import is_market_open
from src.account_guard import check as account_guard_check
from src.state_reconciliation import reconcile_state
from src.io_utils import read_json_safe

log = logging.getLogger("demo_trader")


def _read_json_safe(path: str) -> dict:
    # Factorisé dans src/io_utils.py (tâche de nettoyage, audit
    # institutionnel) -- auparavant dupliquée à l'identique ici, dans
    # src/continuous_trainer.py et src/dashboard.py.
    return read_json_safe(path)


# HIÉRARCHIE TEMPORELLE (mode "temporal_hierarchy", voir risk_profile.py) :
# alternative à "priority_by_score" qui n'arbitre JAMAIS sur le score
# walk-forward -- seulement sur le RANG du timeframe primaire de chaque
# style. Un timeframe plus large (D1) réagit à un horizon de marché plus
# lointain qu'un timeframe court (M15) -- le style supérieur a TOUJOURS
# priorité, quel que soit l'écart de niveau, et le style inférieur qui
# s'opposerait à lui est TOUJOURS bloqué (jamais autorisé, même partiellement).
# ZÉRO HEDGING TOLÉRÉ (18/09, durci sur demande explicite -- un ancien palier
# "écart=1 niveau -> autorisé à budget réduit" a été retiré) : un BUY et un
# SELL ouverts simultanément sur le MÊME symbole par deux styles différents
# est le genre de pattern qu'un broker ou une prop firm anti-hedging détecte
# et peut flaguer -- risque réel au moment d'un retrait, observé concrètement
# en démo entre H1 et H4 le 18/09. Le score walk-forward reste réservé à la
# promotion de champion (continuous_trainer.py) -- jamais à cet arbitrage.
TIMEFRAME_HIERARCHY = {"D1": 5, "H4": 4, "H1": 3, "M30": 2, "M15": 1}


def _style_score(style: str) -> float:
    """Score de validation walk-forward ACTUEL du champion de ce style --
    le MÊME champ que celui utilisé par le sélecteur de champion (voir
    _scan_eligible_styles) et par la coordination inter-styles ci-dessous.
    Lu directement depuis meta.json plutôt que depuis `eligible` : reste
    valide même si `style` n'est plus éligible CE cycle (sa position
    resterait alors gérée par personne, mais reste comparable ici pour
    l'arbitrage de priorité)."""
    return _read_json_safe(_champion_meta(style)).get("score", -1e9)


def _build_live_dataframe(mtf_config, connector, n_bars_primary,
                           fundamental_feed, refresh_fundamental):
    """Construit le DataFrame de décision en fusionnant EN DIRECT plusieurs
    timeframes récupérées depuis MT5 (primaire + contexte)."""
    primary_tf = mtf_config["primary_timeframe"]
    context_tfs = mtf_config["context_timeframes"]
    n_bars_context = mtf_config.get("n_bars_context", 3000)

    dfs = {primary_tf: connector.get_latest_bars(primary_tf, n_bars_primary)}
    for tf in context_tfs:
        if tf == primary_tf:
            continue
        try:
            dfs[tf] = connector.get_latest_bars(tf, n_bars_context)
        except Exception as e:
            log.warning(f"Timeframe de contexte '{tf}' indisponible en direct ({e}) "
                        f"-> ignorée pour ce cycle (dernière valeur connue conservée par ffill).")

    df, _ = fuse_mtf_frames(dfs, primary_tf, context_tfs)
    df = add_technical_features(df, fundamental_feed=fundamental_feed,
                                 refresh_fundamental=refresh_fundamental)
    # ATR BRUT (audit institutionnel, item "Stop Loss basé sur l'ATR") : même
    # colonne que celle ajoutée côté entraînement (voir
    # autonomous_agent.py::_rebuild) -- SANS elle ici, la démo retomberait
    # silencieusement sur les buckets de stop STATIQUES (voir
    # TradingEnv._atr_stop_loss_active) alors que l'entraînement, lui,
    # utiliserait le stop dynamique ATR -- un écart entraînement/démo qu'il
    # faut éviter. Voir TradingEnv.ATR_RAW_COLUMN.
    if "atr_14" in df.columns:
        df[TradingEnv.ATR_RAW_COLUMN] = df["atr_14"]
    return df


def _load_style_entry(tf: str) -> dict | None:
    """Charge le meta/model_path/stats_path d'UN style, SANS filtrer sur
    `passes_validation` (voir `_scan_eligible_styles`, qui ajoute ce filtre
    par-dessus pour l'éligibilité à une NOUVELLE ouverture) -- factorisé le
    21/09 pour être réutilisable par `_position_only_entries` (un style qui
    n'est plus éligible mais a encore une position réelle ouverte doit
    quand même pouvoir charger son meta pour continuer à la gérer). Renvoie
    None si le meta est absent/illisible, d'une version d'environnement
    différente, ou si les stats sont introuvables."""
    meta_path = _champion_meta(tf)
    if not os.path.exists(meta_path):
        return None
    try:
        with open(meta_path, encoding="utf-8") as f:
            meta = json.load(f)
    except Exception:
        return None
    if "feature_columns" not in meta:
        return None
    if not env_version_matches(meta):
        log.warning(f"Style '{tf}' ignoré pour la démo : env_version="
                     f"{meta.get('env_version', 1)} != {ENV_VERSION}.")
        return None
    stats_path = _champion_stats(tf)
    if not os.path.exists(stats_path):
        return None
    return {"style": tf, "meta": meta, "model_path": _champion_model(tf), "stats_path": stats_path}


def _scan_eligible_styles(cfg: dict) -> list[dict]:
    """Renvoie les styles ACTUELLEMENT éligibles à la démo, triés par score
    décroissant. Plusieurs styles peuvent être éligibles en même temps
    (contrairement à l'ancien champion démo unique) -- c'est ce qui permet
    l'ensemble pondéré.

    Repli sur l'ancien champion démo unique (models/demo_champion/) si
    aucun pool multi-style n'est configuré, ou si aucun style ne passe
    encore individuellement la validation (bootstrap, ou `live.ensemble:
    false`) : garantit un comportement identique à l'ancien système dans
    ces deux cas.
    """
    pool = cfg.get("data", {}).get("timeframe_pool") or []
    eligible = []
    if cfg.get("live", {}).get("ensemble", True):
        for tf in pool:
            entry = _load_style_entry(tf)
            if entry is None or not entry["meta"].get("passes_validation"):
                continue
            eligible.append(entry)
        eligible.sort(key=lambda e: e["meta"].get("score", -1e9), reverse=True)
        if eligible:
            return eligible

    if os.path.exists(DEMO_META):
        try:
            with open(DEMO_META, encoding="utf-8") as f:
                meta = json.load(f)
        except Exception:
            return []
        if "feature_columns" in meta and env_version_matches(meta):
            return [{"style": meta.get("primary_timeframe", "demo"), "meta": meta,
                      "model_path": DEMO_MODEL, "stats_path": DEMO_STATS}]
    return []


def _position_only_entries(cfg: dict, eligible_styles: set, open_by_style: dict) -> list[dict]:
    """Bug réel trouvé le 21/09 en démo (H4) : un style qui a une position
    RÉELLE ouverte, puis qui repasse sous les seuils de validation avant
    que cette position ne se solde, se retrouvait totalement abandonné --
    ni `close_orphan_positions` (son tag reste reconnu) ni la boucle de
    décision (filtrée sur `_scan_eligible_styles`, qui exclut désormais ce
    style) ne le touchaient plus. Renvoie les entrées pour les styles
    HORS de `eligible_styles` mais présents dans `open_by_style` -- ajoutés
    à la boucle de décision UNIQUEMENT pour continuer à gérer (et pouvoir
    fermer) leur position existante. `_StyleRuntime.maybe_reload` continue
    de reporter le rechargement tant que cette position reste ouverte (déjà
    en place, voir plus bas) -- c'est donc TOUJOURS la même génération qui
    a ouvert la position qui continue à la gérer, jamais une génération
    plus récente non validée : pas de risque de "double avis" sur un même
    trade. `run_demo_trading_loop` doit en plus empêcher CES styles
    d'ouvrir une NOUVELLE position tant qu'ils ne sont pas repassés
    éligibles (voir le garde-fou `position_only` dans la boucle)."""
    extra = []
    for style, pos in open_by_style.items():
        if style in eligible_styles:
            continue
        entry = _load_style_entry(style)
        if entry is None:
            continue
        entry["position_only"] = True
        extra.append(entry)
    return extra


def _resolve_entry_for_open_position(entry: dict, open_position: dict | None) -> dict:
    """Bug réel trouvé le 21/09 (H4, au redémarrage du processus) : le tout
    PREMIER chargement d'un style dans un processus fraîchement démarré
    n'est jamais reporté par `_StyleRuntime.maybe_reload` (rien à préserver
    au premier chargement, voir sa docstring) -- donc si ce style a une
    position réelle ouverte par une génération N, mais que le champion
    actuel est déjà une génération N+k différente, cette position se
    retrouve gérée par un modèle qui n'est PAS celui qui l'a ouverte, dès
    le premier cycle après un redémarrage (observé : position H4 gen:134
    reprise puis fermée par gen:204). Hors redémarrage, cette situation ne
    peut pas se produire (le garde-fou de `maybe_reload` s'applique déjà à
    partir du 2e chargement).

    Corrige en rechargeant le snapshot ARCHIVÉ exact de la génération qui a
    ouvert la position (voir `_archive_snapshot`/`history/gen_<N>/` dans
    src/continuous_trainer.py) au lieu du champion courant, si `entry` et
    `open_position` désignent des générations différentes et qu'un tel
    snapshot existe. Repli silencieux sur `entry` tel quel (champion
    courant) si : aucune position, générations identiques, génération
    d'ouverture inconnue (comment "?" -- position ouverte avant l'ajout de
    ce tag), ou snapshot introuvable/incomplet/d'une autre version
    d'environnement -- ne doit JAMAIS bloquer le chargement, seulement
    l'améliorer quand c'est possible."""
    if not open_position:
        return entry
    opened_gen = open_position.get("opened_by_generation")
    current_gen = entry["meta"].get("generation")
    if opened_gen is None or opened_gen == current_gen:
        return entry

    style = entry["style"]
    snap_dir = os.path.join(_champion_dir(style), "history", f"gen_{opened_gen}")
    snap_meta_path = os.path.join(snap_dir, "meta.json")
    snap_model_path = os.path.join(snap_dir, "agent")
    snap_stats_path = os.path.join(snap_dir, "norm_stats.json")
    if not (os.path.exists(snap_meta_path) and os.path.exists(snap_model_path + ".zip")
            and os.path.exists(snap_stats_path)):
        log.warning(f"[{style}] Position ouverte par la génération {opened_gen}, mais le champion actuel "
                     f"est déjà la génération {current_gen} et aucun snapshot archivé de la génération "
                     f"{opened_gen} n'est disponible -- repli sur le champion actuel : cette position sera "
                     f"gérée par un modèle différent de celui qui l'a ouverte.")
        return entry
    try:
        with open(snap_meta_path, encoding="utf-8") as f:
            snap_meta = json.load(f)
    except Exception:
        return entry
    if "feature_columns" not in snap_meta or not env_version_matches(snap_meta):
        return entry

    log.info(f"[{style}] Position ouverte par la génération {opened_gen} (le champion actuel est la "
              f"génération {current_gen}) -- chargement du snapshot archivé EXACT de la génération "
              f"{opened_gen} pour cette position, jamais le champion courant : la même génération qui a "
              f"ouvert un trade doit toujours être celle qui le gère, y compris après un redémarrage.")
    resolved = {"style": style, "meta": snap_meta, "model_path": snap_model_path,
                "stats_path": snap_stats_path}
    if "position_only" in entry:
        resolved["position_only"] = entry["position_only"]
    return resolved


class _LiveMemoryTracker:
    """Transforme les DÉCISIONS RÉELLEMENT prises en démo en expérience pour
    la mémoire épisodique -- sans ça, la mémoire ne contient QUE des trades
    SIMULÉS issus de la validation d'entraînement (voir
    continuous_trainer.py), jamais ce qui s'est réellement passé une fois
    connecté à MT5. Approximation volontairement simple (mouvement de prix
    pondéré par l'exposition, pas de comptage de frais/spread exact -- déjà
    tenu par MT5 lui-même) : le but est de donner un signal directionnel
    réel à la mémoire, pas un livre de comptes.
    """

    def __init__(self):
        self.entry_exposure = 0.0
        self.entry_price = None
        self.entry_context = None

    def update(self, memory, new_exposure: float, price: float, context: np.ndarray,
               style: str | None = None, generation: int = -1):
        if memory is not None and self.entry_price is not None and abs(self.entry_exposure) > 1e-9 \
                and abs(new_exposure - self.entry_exposure) > 0.05:
            direction = 1 if self.entry_exposure > 0 else -1
            realized = (price - self.entry_price) / self.entry_price * direction * abs(self.entry_exposure)
            drawdown = abs(min(0.0, realized))
            memory.store(
                context=self.entry_context if self.entry_context is not None else context,
                action=int(round(self.entry_exposure)), pnl_pct=float(realized),
                drawdown=float(drawdown), generation=generation,
                source="live", style=style,
            )
            log.info(f"[mémoire live] position réelle clôturée (exposition {self.entry_exposure:+.2f} -> "
                      f"{new_exposure:+.2f}) : pnl≈{realized:+.2%} enregistré dans la mémoire épisodique.")
        if abs(new_exposure - self.entry_exposure) > 0.05 or self.entry_price is None:
            self.entry_exposure = new_exposure
            self.entry_price = price
            self.entry_context = context


class _StyleRuntime:
    """Cache d'un style chargé (modèle + stats + config multi-timeframe),
    rechargé uniquement quand une nouvelle version a été promue
    (`meta["updated_at"]` change) -- qu'il s'agisse d'un membre de
    l'ensemble ou de l'ancien champion démo unique."""

    def __init__(self):
        self.agent = None
        self.stats = None
        self.feature_columns = None
        self.mtf_config = None
        self.last_loaded_at = None
        self.tracker = _LiveMemoryTracker()
        # GARDE-FOU DE FRÉQUENCE (cooldown de réouverture, voir
        # apply_reentry_cooldown ci-dessous) : état PAR STYLE, cohérent avec
        # le reste de cette classe (une instance par style).
        self.cooldown_prev_target = 0.0
        self.cooldown_last_close_at = None
        # ÉTAT DU FILET DE SÉCURITÉ (risk_guard, voir plus bas) : mémorisé
        # PAR STYLE pour ne notifier qu'aux TRANSITIONS (début/fin d'anomalie)
        # -- pas à chaque cycle tant que l'anomalie persiste, sinon un marché
        # agité pendant plusieurs heures spammerait une alerte par cycle.
        self.guard_active = False

    def maybe_reload(self, entry, connector, fundamental_feed, n_bars_needed,
                      n_bars_context, memory, memory_top_k, env_kwargs):
        meta = entry["meta"]
        if not env_version_matches(meta):
            log.error(f"Rechargement du style '{entry['style']}' bloqué : env_version="
                       f"{meta.get('env_version', 1)} != {ENV_VERSION} (filet de sécurité, "
                       f"déjà filtré normalement par _scan_eligible_styles).")
            return
        if meta.get("updated_at") == self.last_loaded_at:
            return
        # GARDE-FOU (demande explicite de l'utilisateur, 15/09) : ne JAMAIS
        # remplacer les poids d'un style déjà chargé (self.agent existe déjà
        # -- le tout premier chargement d'un style qui vient de devenir
        # éligible n'est PAS concerné, rien à préserver) tant qu'une position
        # réelle est ouverte sur MT5. Sans ça, l'entrée d'un trade pouvait
        # être décidée par la génération N et sa gestion/sortie par la
        # génération N+1 fraîchement promue -- deux "avis" différents sur la
        # même position, un risque concret par exemple juste avant une
        # fermeture de marché (week-end). Le rechargement est simplement
        # REPORTÉ : retenté à chaque cycle suivant jusqu'à ce que le compte
        # repasse à plat, journalisé avec le contexte COMPLET de la position
        # en cours (ticket, direction, prix d'entrée, stop, P&L flottant) --
        # pas un simple booléen -- pour que le report reste traçable et lié
        # aux objectifs d'origine de cette position précise.
        if self.agent is not None:
            # PAR STYLE, pas par symbole (corrigé 21/09 -- bug réel trouvé en
            # observant M30 rester bloqué sur sa toute première version
            # pendant des heures) : `get_open_position_info()` renvoyait LA
            # position sur le symbole entier, donc une position ouverte par
            # H4 reportait aussi le rechargement de M30, qui n'avait
            # pourtant lui-même AUCUNE position à préserver. Avec le
            # multi-position indépendant par style (LOT 2), seule une
            # position ouverte par CE style précis doit reporter SON propre
            # rechargement -- voir MT5Connector.get_open_positions_by_style.
            open_position = connector.get_open_positions_by_style([entry["style"]]).get(entry["style"])
            if open_position is not None:
                sens = "ACHAT" if open_position["direction"] == 1 else "VENTE"
                log.info(
                    f"Nouvelle version du style '{entry['style']}' disponible (génération "
                    f"{meta.get('generation')}, score={meta.get('score', 0):.3f}) mais REPORTÉE : "
                    f"position réelle ouverte (ticket {open_position['ticket']}, {sens}, "
                    f"entrée à {open_position['price_open']}, stop à {open_position['sl']}, "
                    f"P&L actuel {open_position['profit']:+.2f}$) -- l'ancienne version continue de "
                    f"gérer cette position jusqu'à sa clôture, pour ne jamais faire trancher l'entrée "
                    f"et la sortie d'un même trade par deux modèles différents."
                )
                return
        log.info(f"Rechargement du style '{entry['style']}' : génération {meta.get('generation')}, "
                  f"score={meta.get('score', 0):.3f}...")
        self.feature_columns = meta["feature_columns"]
        self.mtf_config = {
            "primary_timeframe": meta["primary_timeframe"],
            "context_timeframes": meta["context_timeframes"],
            "n_bars_context": n_bars_context,
        }
        warmup_df = _build_live_dataframe(self.mtf_config, connector, n_bars_needed,
                                           fundamental_feed, refresh_fundamental=False)
        # SYMBOLE OR UNIQUEMENT (LOT 2, phase 4, point 9) : le live ne trade
        # que l'or -- un souvenir d'un trade EURUSD/SPX synthétique
        # n'a aucune pertinence pour une décision réelle ici (voir
        # EpisodicMemory.snapshot, symbol=None des lignes historiques inclus).
        memory_snapshot = memory.snapshot(dim=len(self.feature_columns),
                                            symbols=[GOLD_SYMBOL]) if memory else None
        dummy_env = TradingEnv(warmup_df, feature_columns=self.feature_columns,
                                memory_snapshot=memory_snapshot, memory_top_k=memory_top_k,
                                style=entry["style"], **env_kwargs)
        try:
            self.agent = TradingAgent.load(entry["model_path"], dummy_env, {"algo": meta.get("algo", "PPO")})
        except EnvVersionMismatch as e:
            log.error(f"Rechargement du style '{entry['style']}' annulé : {e}")
            return
        with open(entry["stats_path"], encoding="utf-8") as f:
            self.stats = {k: tuple(v) for k, v in json.load(f).items()}
        self.last_loaded_at = meta.get("updated_at")

    def decide(self, connector, fundamental_feed, n_bars_needed, memory, memory_top_k, env_kwargs):
        """Retourne (position cible discrète de CE style {-1, 0, 1}, distance
        de stop-loss CHOISIE PAR L'AGENT en fraction du prix d'entrée -- ou
        None si `agent.learn_stop_loss` est désactivé, si le style est flat,
        ou si le stop ATR dynamique est actif (voir ci-dessous) --, multiple
        ATR choisi par l'agent -- ou None si le stop ATR n'est pas actif --,
        ATR live en unités de prix -- ou None --, DataFrame brut utilisé).

        STOP ATR (LOT 2, phase 3 -- corrige un écart entraînement/live réel :
        cette méthode décodait auparavant TOUJOURS le bucket choisi via la
        table STATIQUE en %, même quand l'entraînement utilisait des buckets
        ATR dynamiques -- voir TradingEnv._atr_stop_loss_active) : quand le
        stop ATR est actif (même condition EXACTE que TradingEnv, lue
        directement sur l'instance `env` construite ci-dessous -- source
        unique, jamais une réimplémentation séparée qui pourrait diverger),
        `stop_pct` reste None et c'est le MULTIPLE choisi (pas une distance
        déjà résolue) qui est retourné, avec l'ATR live -- la résolution
        finale (multiple x ATR, bornée) se fait dans MT5Connector.send_order
        via risk_engine, la même formule que l'entraînement.

        La position, le stop (statique OU ATR) sont combinés avec ceux des
        autres styles éligibles par l'appelant ; le DataFrame sert au filet
        de sécurité indépendant (voir src/risk_guard.py)."""
        raw_df = _build_live_dataframe(self.mtf_config, connector, n_bars_needed,
                                        fundamental_feed, refresh_fundamental=True)
        df, _ = normalize_features(raw_df, self.stats, columns=self.feature_columns)

        memory_snapshot = memory.snapshot(dim=len(self.feature_columns),
                                            symbols=[GOLD_SYMBOL]) if memory else None
        style = self.mtf_config["primary_timeframe"]
        env = TradingEnv(df, feature_columns=self.feature_columns,
                          memory_snapshot=memory_snapshot, memory_top_k=memory_top_k,
                          style=style, **env_kwargs)
        obs, _ = env.reset()
        while env.current_step < len(df) - 2:
            obs, _, term, trunc, _ = env.step(1)
            if term or trunc:
                break
        # La boucle ci-dessus s'arrete a `len(df) - 2` : c'est la marge que
        # TradingEnv.step() reserve TOUJOURS pour le prix de remplissage de
        # la bougie `current_step + 1` (necessaire en entrainement/backtest,
        # voir TradingEnv.step()). En LIVE cette bougie future n'existe pas
        # a reserver -- la derniere bougie recuperee (`len(df) - 1`) est deja
        # reelle et cloturee/en cours, et doit servir de contexte a la
        # decision. Sans ce rattrapage, l'agent decide TOUJOURS avec une
        # bougie de retard sur la donnee la plus fraiche (jusqu'a un cycle
        # complet de sa propre timeframe primaire de retard en permanence).
        env.current_step = len(df) - 1
        obs = env._get_obs()
        action = self.agent.predict(obs, deterministic=True)

        # Interprétation de l'action IDENTIQUE à celle de TradingEnv.step()
        # (voir src/trading_env.py) : même mapping discret/continu, mêmes
        # buckets/bornes de stop -- sinon la démo décoderait l'action du
        # modèle différemment de la façon dont il a appris à la produire.
        learn_stop_loss = env_kwargs.get("learn_stop_loss", False)
        stop_pct = None
        atr_multiplier = None
        atr_price_units = None
        if env_kwargs.get("continuous_action"):
            arr = np.asarray(action, dtype=np.float32).reshape(-1)
            target = float(np.clip(arr[0], -1.0, 1.0))
            if learn_stop_loss and arr.shape[0] > 1 and target != 0:
                lo, hi = env_kwargs.get("stop_loss_range", (0.003, 0.06))
                stop_pct = lo + (float(np.clip(arr[1], -1.0, 1.0)) + 1) / 2 * (hi - lo)
        elif learn_stop_loss:
            direction_idx, stop_idx = int(action[0]), int(action[1])
            target = float({0: -1, 1: 0, 2: 1}[direction_idx])
            if target != 0:
                if env._atr_stop_loss_active:
                    atr_multiplier = float(env.atr_stop_multipliers[stop_idx])
                    atr_price_units = env._atr_price_units()
                else:
                    buckets = (env_kwargs.get("stop_loss_buckets")
                               or TradingEnv.STOP_LOSS_BUCKETS_BY_STYLE.get(style)
                               or [0.005, 0.01, 0.02, 0.03, 0.05])
                    stop_pct = float(buckets[stop_idx])
        else:
            target = float({0: -1, 1: 0, 2: 1}[int(action)])

        # MÉMOIRE VIVANTE : la décision RÉELLEMENT prise, avec le contexte de
        # marché RÉEL au moment de la décision -- pas un remplacement du
        # replay simulé de l'entraînement, un complément qui reflète ce qui
        # se passe VRAIMENT une fois connecté à MT5.
        last_price = float(df.iloc[-1]["close"])
        last_context = df.iloc[-1][self.feature_columns].values.astype(np.float32)
        self.tracker.update(memory, target, last_price, last_context, style=style)

        return target, stop_pct, atr_multiplier, atr_price_units, raw_df

    def apply_reentry_cooldown(self, style: str, raw_target: float,
                                cooldown_minutes: float, now: float | None = None) -> float:
        """GARDE-FOU DE FRÉQUENCE (18/09, suite à l'analyse de l'historique de
        trades -- 0% de sorties par stop-loss touché sur 18 trades, plusieurs
        retournements en 5 min, le cycle minimum, ~400$ de coût de spread
        estimé sur 19h) : correctif côté EXÉCUTION, pas un changement du
        modèle -- le coût de transaction dans la récompense d'entraînement
        est correct pour un trade isolé mais ne pénalise pas la fréquence
        CUMULATIVE des retournements, donc ce garde-fou comble ce trou côté
        exécution plutôt que d'attendre un réentraînement.

        RÈGLE ABSOLUE : ne bloque JAMAIS une fermeture, seulement une
        NOUVELLE ouverture. Concrètement, une décision de CE style qui
        s'éloigne de sa direction actuelle (retour à plat, ou retournement
        vers le sens opposé) passe TOUJOURS -- on ne bloque que la partie
        "réouverture" d'un retournement (le nouveau sens opposé est ramené à
        plat pour ce cycle, retenté aux cycles suivants), et toute tentative
        d'ouverture depuis plat pendant les `cooldown_minutes` qui suivent la
        dernière fermeture DE CE STYLE. État tenu PAR STYLE (une instance de
        _StyleRuntime par style, voir runtimes dans run_demo_trading_loop) --
        un retournement sur D1 ne doit jamais affecter le cooldown de M15."""
        now = now if now is not None else time.time()
        prev = self.cooldown_prev_target
        is_closing_or_reversing = prev != 0.0 and (raw_target == 0.0 or (raw_target * prev) < 0.0)

        if is_closing_or_reversing:
            # La fermeture passe TOUJOURS -- démarre/rafraîchit le cooldown
            # maintenant. Si c'était un retournement (raw_target de signe
            # opposé, pas juste un retour à plat), la réouverture dans le
            # nouveau sens est reportée : on ne l'ouvre pas CE cycle, elle
            # sera retentée (et soumise au cooldown) au cycle suivant comme
            # n'importe quelle nouvelle ouverture.
            self.cooldown_last_close_at = now
            self.cooldown_prev_target = 0.0
            return 0.0

        if prev == 0.0 and raw_target != 0.0:
            # Tentative de NOUVELLE ouverture (départ de plat) -- seule
            # situation soumise au cooldown.
            if self.cooldown_last_close_at is not None:
                elapsed = now - self.cooldown_last_close_at
                cooldown_seconds = cooldown_minutes * 60.0
                if elapsed < cooldown_seconds:
                    remaining_min = (cooldown_seconds - elapsed) / 60.0
                    log.info(
                        f"[cooldown] Style '{style}' : ouverture demandée "
                        f"(target={raw_target:+.2f}) BLOQUÉE -- {remaining_min:.1f} min "
                        f"restantes avant réautorisation (min_reentry_cooldown_minutes="
                        f"{cooldown_minutes})."
                    )
                    return 0.0
            self.cooldown_prev_target = raw_target
            return raw_target

        # Maintien de la même direction (ou déjà plat) : jamais concerné par
        # le cooldown, passe tel quel.
        self.cooldown_prev_target = raw_target
        return raw_target


def run_demo_trading_loop(cfg: dict, env_kwargs: dict,
                           connector=None, max_iterations: int | None = None):
    """Boucle principale. `connector` peut être injecté (utilisé par les
    tests avec un faux connecteur) ; sinon un MT5Connector réel est créé.
    `max_iterations` permet de limiter la boucle (tests) ; None = infini.
    """
    if connector is None:
        from src.mt5_connector import MT5Connector
        connector = MT5Connector(cfg)
    connector.connect()

    # MIGRATION (18/09, passage au multi-position indépendant par style) :
    # ferme toute position sans tag de style reconnu (héritée de l'ancien
    # système à blending d'ensemble) AVANT que la boucle ci-dessous ne
    # commence à gérer des positions par style -- voir
    # MT5Connector.close_orphan_positions pour la décision et son
    # justification. Idempotent (sans effet si rien à fermer), donc appelé
    # à chaque démarrage, pas seulement une fois.
    orphans_closed = connector.close_orphan_positions(
        recognized_styles=cfg.get("data", {}).get("timeframe_pool") or [])
    if orphans_closed:
        from src.notifier import send_alert
        detail = "; ".join(f"ticket={o['ticket']} ({o['original_comment']!r}, "
                             f"{o['profit']:+.2f}$)" for o in orphans_closed)
        send_alert(cfg, subject="Migration multi-position -- position(s) orpheline(s) fermée(s)",
                   message=f"{len(orphans_closed)} position(s) sans style reconnu fermée(s) au "
                            f"démarrage du nouveau système multi-position : {detail}")

    fundamental_feed = None
    if cfg.get("fundamental", {}).get("enabled"):
        from src.fundamental_feed import AutoFundamentalFeed
        fundamental_feed = AutoFundamentalFeed(cfg)

    # MÉMOIRE ÉPISODIQUE : la démo doit voir le même signal "situations
    # passées similaires" que celui utilisé pendant l'entraînement (voir
    # src/continuous_trainer.py et src/memory_features.py), sinon l'agent
    # déciderait en démo avec une observation différente de celle sur
    # laquelle il a appris. Rafraîchi à chaque décision (nouveaux trades
    # enregistrés en continu par la boucle d'évolution en arrière-plan).
    memory = None
    memory_cfg = cfg.get("memory") or {}
    if memory_cfg.get("db_path"):
        from src.episodic_memory import EpisodicMemory
        memory = EpisodicMemory(memory_cfg["db_path"], memory_cfg.get("max_episodes", 20000))
    memory_top_k = memory_cfg.get("similarity_top_k", 5)

    n_bars_needed = env_kwargs["window_size"] + 60
    n_bars_context = cfg.get("data", {}).get("n_bars_context", 3000)
    from src.reliability_tracker import DEFAULT_MIN_TRADES_FOR_CONFIDENCE
    min_trades_for_confidence = cfg.get("reliability", {}).get(
        "min_trades_for_confidence", DEFAULT_MIN_TRADES_FOR_CONFIDENCE)

    runtimes: dict[str, _StyleRuntime] = {}
    iterations = 0
    # HEARTBEAT (audit institutionnel, section 5) : état de coupure PERSISTANT
    # ENTRE LES ITÉRATIONS de la boucle (pas de halt sur disque comme
    # account_guard -- juste une variable de PROCESSUS, réinitialisée à
    # False si le script redémarre, ce qui est le comportement voulu : un
    # redémarrage n'a pas besoin de "se souvenir" d'une coupure passée).
    # Sert à n'ALERTER qu'une fois par ÉPISODE de coupure (pas à chaque
    # cycle tant qu'elle dure) et à détecter la TRANSITION de rétablissement.
    heartbeat_outage_active = False

    while True:
        # RELUS À CHAQUE ITÉRATION (pas mis en cache avant la boucle) : ces
        # trois réglages font partie du sous-ensemble éditable en direct
        # depuis le tableau de bord (voir src/settings_server.py) -- un
        # changement doit prendre effet au cycle de démo SUIVANT, pas
        # seulement après un redémarrage complet du script.
        poll = cfg["live"].get("poll_seconds", 60)
        risk_guard_enabled = cfg.get("live", {}).get("risk_guard", True)
        risk_guard_z_threshold = cfg.get("live", {}).get("risk_guard_z_threshold", 4.0)
        # SEUIL D'ALERTE, DISTINCT du seuil de RÉDUCTION D'EXPOSITION ci-dessus
        # (22/09, "plus jamais" -- voir bloc de notification plus bas) :
        # volontairement plus bas que risk_guard_z_threshold, pour PRÉVENIR
        # l'utilisateur d'un mouvement de marché notable même quand il n'est
        # pas (encore) assez extrême statistiquement pour justifier une
        # réduction de position -- informer et agir sont deux seuils
        # différents, ne pas les confondre.
        risk_guard_notify_z_threshold = cfg.get("live", {}).get("risk_guard_notify_z_threshold", 2.5)
        min_reentry_cooldown_minutes = cfg.get("live", {}).get("min_reentry_cooldown_minutes", 15)

        # MARCHÉ FERMÉ : ne tente ni décision ni envoi d'ordre -- basé sur
        # la fraîcheur RÉELLE des cotations MT5 quand disponible (voir
        # src/market_hours.py et src/live_data_feed.py), pas seulement une
        # estimation d'horaire dans la config. Le rechargement de modèle et
        # le scan d'éligibilité restent inoffensifs, mais interroger MT5
        # pour une décision alors que rien ne bouge n'aurait aucun sens.
        if not is_market_open(cfg):
            log.info(f"Marché {cfg.get('live', {}).get('symbol', 'XAUUSD')} détecté FERMÉ -> "
                      f"pas de décision cette fois, nouvelle vérification dans {poll}s...")
            time.sleep(poll)
            iterations += 1
            if max_iterations is not None and iterations >= max_iterations:
                return
            continue

        # COUPE-CIRCUIT DE COMPTE (voir src/account_guard.py) : dernier
        # filet de sécurité, indépendant de l'agent ET du garde-fou
        # statistique de marché -- si l'équité RÉELLE a chuté de plus de
        # `live.max_account_drawdown_pct` depuis son pic, tout nouvel ordre
        # est bloqué et une alerte est envoyée, jusqu'à revue humaine
        # explicite. Ne touche JAMAIS à l'entraînement (continuous_trainer.py
        # continue de tourner normalement même si ce contrôle bloque la démo).
        if not account_guard_check(connector, cfg):
            log.critical("Coupe-circuit de compte ACTIF -- aucune décision ni ordre tant qu'il n'est "
                         "pas réinitialisé manuellement (voir src/account_guard.py::reset()).")
            time.sleep(poll)
            iterations += 1
            if max_iterations is not None and iterations >= max_iterations:
                return
            continue

        # HEARTBEAT / PERTE DE CONNEXION (audit institutionnel, section 5) :
        # si aucun appel MT5 n'a réussi depuis plus de `heartbeat_timeout_s`
        # secondes (voir MT5Connector.seconds_since_last_success/
        # _mark_success) ET qu'au moins une position réelle est ouverte, la
        # communication avec le broker est potentiellement rompue PENDANT
        # qu'un risque réel est en cours -- cycle sauté par précaution à
        # CHAQUE cycle tant que la coupure dure (même traitement que le
        # coupe-circuit de compte : aucun nouvel ordre tant que la connexion
        # n'a pas prouvé qu'elle fonctionne à nouveau, PAS de halt persistant
        # nécessitant un reset() -- le cycle suivant réévalue normalement dès
        # que le heartbeat redevient frais). L'ALERTE, elle, n'est envoyée
        # QU'UNE FOIS par ÉPISODE de coupure (`heartbeat_outage_active`,
        # pas de spam à chaque cycle d'une coupure prolongée) ; une alerte de
        # RÉTABLISSEMENT distincte est envoyée à la transition inverse.
        # `getattr` avec repli à None : reste inoffensif si `connector` est
        # un faux connecteur de test qui n'implémente pas encore cette
        # méthode (comportement d'origine inchangé dans ce cas -- jamais de
        # transition de rétablissement non plus, puisqu'aucune coupure ne
        # peut alors être détectée).
        heartbeat_timeout_s = cfg.get("live", {}).get("heartbeat_timeout_s", 5.0)
        heartbeat_fn = getattr(connector, "seconds_since_last_success", None)
        if heartbeat_fn is not None:
            stale_for = heartbeat_fn()
            is_stale = stale_for > heartbeat_timeout_s
            if is_stale and not heartbeat_outage_active:
                try:
                    open_positions_now = connector.get_open_positions_by_style(
                        recognized_styles=cfg.get("data", {}).get("timeframe_pool") or [])
                except Exception:
                    open_positions_now = {}
                if open_positions_now:
                    heartbeat_outage_active = True
                    log.critical(
                        f"ALERTE CONNEXION MT5 : aucun appel réussi depuis {stale_for:.1f}s (seuil "
                        f"{heartbeat_timeout_s:.1f}s) alors que {len(open_positions_now)} position(s) "
                        f"réelle(s) sont ouvertes ({list(open_positions_now.keys())}) -- cycle sauté par précaution."
                    )
                    try:
                        from src.notifier import send_alert
                        send_alert(cfg, subject="Test_IA - ALERTE perte de connexion MT5",
                                   message=(f"Aucun appel MT5 réussi depuis {stale_for:.1f}s alors que des "
                                            f"positions réelles sont ouvertes ({list(open_positions_now.keys())}) "
                                            f"-- vérifiez immédiatement le terminal MT5 et la connexion réseau."))
                    except Exception:
                        pass
                    time.sleep(poll)
                    iterations += 1
                    if max_iterations is not None and iterations >= max_iterations:
                        return
                    continue
            elif is_stale and heartbeat_outage_active:
                # Coupure toujours en cours -- cycle sauté SANS ré-alerter
                # (voir docstring ci-dessus), mais uniquement si des positions
                # sont ENCORE ouvertes (si elles ont entre-temps toutes été
                # fermées côté broker, ex: stop-loss touché, il n'y a plus de
                # risque réel à protéger -- laisser le cycle continuer
                # normalement plutôt que de bloquer indéfiniment sur un
                # heartbeat qui ne se rétablira peut-être jamais).
                try:
                    open_positions_now = connector.get_open_positions_by_style(
                        recognized_styles=cfg.get("data", {}).get("timeframe_pool") or [])
                except Exception:
                    open_positions_now = {}
                if open_positions_now:
                    log.warning(f"Coupure de connexion MT5 toujours en cours ({stale_for:.1f}s) -- "
                                f"cycle sauté (alerte déjà envoyée pour cet épisode).")
                    time.sleep(poll)
                    iterations += 1
                    if max_iterations is not None and iterations >= max_iterations:
                        return
                    continue
            elif not is_stale and heartbeat_outage_active:
                # RÉTABLISSEMENT : transition coupure -> connexion fraîche.
                heartbeat_outage_active = False
                log.info(f"Connexion MT5 rétablie (dernier succès il y a {stale_for:.1f}s, "
                         f"sous le seuil de {heartbeat_timeout_s:.1f}s).")
                try:
                    from src.notifier import send_alert
                    send_alert(cfg, subject="Test_IA - connexion MT5 rétablie",
                               message="La connexion MT5, précédemment signalée comme rompue, est de "
                                       "nouveau active -- le trading reprend normalement.")
                except Exception:
                    pass

        # LATENCE RÉSEAU (audit institutionnel, section 5, "Optimisation de
        # l'Infrastructure Réseau" -- voir MT5Connector.measure_round_trip_ms) :
        # mesure best-effort, une fois par cycle, journalisée dans le
        # tableau de bord (write_live_status ci-dessous) -- purement
        # informatif, ne bloque jamais le cycle. `getattr` : même repli
        # inoffensif qu'au-dessus pour un faux connecteur de test.
        round_trip_ms = None
        rtt_fn = getattr(connector, "measure_round_trip_ms", None)
        if rtt_fn is not None:
            try:
                round_trip_ms = rtt_fn()
            except Exception:
                round_trip_ms = None

        eligible = _scan_eligible_styles(cfg)

        # POSITION SANS STYLE ÉLIGIBLE (21/09, voir _position_only_entries) :
        # récupéré ICI, AVANT le repli "aucun style éligible" ci-dessous --
        # sinon un style qui aurait une position réelle ouverte mais serait
        # le SEUL du pool (ou le dernier) à retomber sous les seuils de
        # validation ferait sortir de la boucle AVANT même de vérifier s'il
        # a quelque chose à gérer, abandonnant sa position pour de bon.
        open_by_style = connector.get_open_positions_by_style(
            recognized_styles=cfg.get("data", {}).get("timeframe_pool") or [])
        position_only = _position_only_entries(cfg, {e["style"] for e in eligible}, open_by_style)
        if position_only:
            log.info(f"Style(s) avec position réelle ouverte mais non éligible(s) à une NOUVELLE "
                      f"ouverture (validation repassée sous les seuils) : "
                      f"{', '.join(e['style'] for e in position_only)} -- conservé(s) dans la boucle "
                      f"pour continuer à gérer/fermer leur position existante, jamais pour en ouvrir une nouvelle.")
        to_process = eligible + position_only

        # SNAPSHOT EXACT DE LA GÉNÉRATION QUI A OUVERT LA POSITION (21/09,
        # voir _resolve_entry_for_open_position) : n'a d'effet que juste
        # après un redémarrage du processus (1er chargement de ce style) --
        # sans effet sinon, puisque `entry["meta"]["generation"]` égale déjà
        # `opened_by_generation` une fois ce style chargé au moins une fois
        # dans ce processus (maybe_reload gère la suite normalement).
        to_process = [_resolve_entry_for_open_position(e, open_by_style.get(e["style"]))
                      for e in to_process]

        if not to_process:
            log.info("Aucun style éligible à la démo pour l'instant (aucun agent n'a encore "
                      f"passé les seuils de validation), nouvelle vérification dans {poll}s...")
            time.sleep(poll)
            iterations += 1
            if max_iterations is not None and iterations >= max_iterations:
                return
            continue

        # MULTI-POSITION INDÉPENDANT (18/09) : plus de blending -- chaque
        # style éligible prend SA PROPRE décision et gère SA PROPRE position
        # via mt5_connector.send_order(style=...), sans agrégation de poids
        # entre styles. _StyleRuntime (rechargement, hot-swap guard,
        # cooldown de réouverture) est déjà structuré par style depuis sa
        # conception -- rien à y changer, ce retrait du blending ne fait que
        # cesser de COMBINER leurs sorties après coup.
        #
        # COORDINATION INTER-STYLES (19/09) : voir risk_profile.py
        # `conflict_resolution` -- "priority_by_score" (évite les positions
        # BUY/SELL simultanées et contradictoires entre styles, observé en
        # démo à 1-4s d'intervalle) ou "disabled" (comportement D'ORIGINE --
        # chaque style agit indépendamment, hedging possible). Un RÉGLAGE,
        # pas un blocage en dur : le hedging n'est pas interdit par toutes
        # les prop firms, voir config/risk_profiles/*.yaml.
        conflict_resolution = cfg.get("live", {}).get("conflict_resolution", "disabled")

        # BUDGET DE RISQUE PAR STYLE -- OPTION B (19/09, remplace la
        # répartition fixe /n_styles_du_pool) : live.max_risk_pct_per_trade
        # divisé par le nombre de styles RÉELLEMENT en position à l'instant
        # de CHAQUE ouverture (positions_get() réel, pas la taille du pool
        # configuré) -- un style seul actif utilise alors 100% du budget
        # max, pas seulement 1/n_pool même quand les autres sont flat.
        # Recalculé À CHAQUE style de la boucle ci-dessous (pas une seule
        # fois avant) : l'ensemble des styles en position évolue au fil de
        # la boucle (fermetures de coordination ci-dessus, nouvelles
        # ouvertures), donc ORDONNÉ -- le premier style à ouvrir dans un
        # cycle profite du budget plein, les suivants se partagent ce qui
        # reste. COMPROMIS ASSUMÉ (déjà identifié) : une position déjà
        # ouverte n'est JAMAIS redimensionnée a posteriori quand un nouveau
        # style rejoint -- le risque CUMULÉ peut donc dépasser
        # max_risk_pct_per_trade si plusieurs styles ouvrent l'un après
        # l'autre dans le même sens (pire cas avec 5 styles : facteur
        # ~2.28x, somme harmonique 1+1/2+1/3+1/4+1/5). Le plafond
        # d'exposition cumulée (`cumulative_exposure`, prévu dans une
        # conversation précédente mais PAS ENCORE implémenté dans
        # risk_profile.py à ce jour) reste la VRAIE protection contre ce
        # pire cas, d'autant plus nécessaire qu'avec l'ancienne répartition
        # fixe (option A) le risque cumulé ne pouvait structurellement
        # jamais dépasser max_risk_pct_per_trade.
        base_max_risk_pct = cfg.get("live", {}).get("max_risk_pct_per_trade")

        # `open_by_style` déjà récupéré plus haut (voir position_only) --
        # tenu à jour LOCALEMENT à partir d'ici (sans re-requêter MT5 à
        # chaque style) au fil de la boucle ci-dessous, pour refléter les
        # fermetures/ouvertures décidées PENDANT ce même cycle (coordination
        # inter-styles, budget dynamique).

        results = []
        for entry in to_process:
            style = entry["style"]
            try:
                # Snapshot AVANT toute décision/ordre de ce cycle pour ce style --
                # seul moment où volume/profit reflètent une position RÉELLEMENT
                # ouverte côté MT5 (le placeholder écrit plus bas après
                # send_order n'a ni volume ni profit connus).
                existing_position = open_by_style.get(style)
                rt = runtimes.setdefault(style, _StyleRuntime())
                rt.maybe_reload(entry, connector, fundamental_feed, n_bars_needed,
                                 n_bars_context, memory, memory_top_k, env_kwargs)

                # RÉCONCILIATION D'ÉTAT (audit institutionnel, section 5) :
                # compare CE QUE la mémoire interne de ce style croit être sa
                # position (rt.tracker) à la réalité MT5 (open_by_style, déjà
                # récupéré ci-dessus pour la coordination -- aucun appel MT5
                # supplémentaire), et réaligne automatiquement en cas de
                # divergence -- voir src/state_reconciliation.py pour le détail
                # (stop-loss déclenché côté broker entre deux cycles, ou
                # redémarrage du script pendant qu'une position réelle était
                # ouverte). Placé ICI, AVANT rt.decide() : couvre à la fois "au
                # démarrage" (premier cycle où CE style est chargé -- son
                # tracker fraîchement créé est toujours à plat par défaut,
                # voir _LiveMemoryTracker.__init__) et "après chaque cycle"
                # (styles déjà actifs les cycles suivants) en un seul appel,
                # jamais avec un état interne périmé au moment de décider.
                reconcile_state(connector, cfg, {style: rt}, broker_positions=open_by_style)

                target, stop_pct, atr_multiplier, atr_price_units, style_df = rt.decide(
                    connector, fundamental_feed, n_bars_needed, memory, memory_top_k, env_kwargs)
                target = rt.apply_reentry_cooldown(style, target, min_reentry_cooldown_minutes)

                # FILET DE SÉCURITÉ INDÉPENDANT (voir src/risk_guard.py),
                # appliqué PAR STYLE désormais -- une anomalie détectée sur les
                # bougies vues par CE style réduit SA SEULE exposition, sans
                # affecter les autres styles.
                final_target = target
                if risk_guard_enabled and style_df is not None:
                    scale, guard_info = anomaly_scale(style_df, z_threshold=risk_guard_z_threshold)
                    if scale < 1.0:
                        final_target = target * scale
                        log.warning(f"[{style}] Filet de sécurité : conditions de marché anormales détectées "
                                    f"({guard_info}) -> exposition réduite de {target:+.2f} à "
                                    f"{final_target:+.2f} (facteur {scale:.2f}).")

                    # NOTIFICATION PROACTIVE (22/09, demande explicite de
                    # l'utilisateur suite à un mouvement H4 réel -0.93% passé
                    # inaperçu -- "plus jamais") : seuil VOLONTAIREMENT séparé
                    # et plus bas (`risk_guard_notify_z_threshold`, défaut 2.5)
                    # que celui de la réduction d'exposition (`risk_guard_
                    # z_threshold`, défaut 4.0) -- un mouvement peut mériter
                    # d'être signalé à l'utilisateur SANS être assez extrême
                    # statistiquement pour justifier une réduction de risque
                    # (le mouvement réel du 22/09 n'aurait PAS déclenché de
                    # réduction à z=4.0 -- z_return=0.37 après coup une fois
                    # le marché stabilisé -- mais mérite quand même d'être vu).
                    # Notifie seulement à la TRANSITION (début/fin), pas à
                    # chaque cycle tant que l'anomalie persiste. Ce filet est
                    # indépendant du réseau appris (voir src/risk_guard.py) :
                    # il lit directement la dernière bougie récupérée, jamais
                    # sujet au décalage de fenêtre de l'agent.
                    worst_z = max(guard_info.get("last_return_z", 0.0), guard_info.get("last_vol_z", 0.0))
                    notable = worst_z > risk_guard_notify_z_threshold
                    if notable and not rt.guard_active:
                        from src.notifier import send_alert
                        send_alert(cfg, subject=f"Test_IA - Mouvement de marché notable ({style})",
                                   message=f"[{style}] z-scores {guard_info} -- exposition "
                                           f"{'réduite de ' + format(target, '+.2f') + ' à ' + format(final_target, '+.2f') if scale < 1.0 else f'inchangée ({final_target:+.2f})'} "
                                           f"(facteur {scale:.2f}).")
                        rt.guard_active = True
                    elif not notable and rt.guard_active:
                        log.info(f"[{style}] Filet de sécurité : conditions de marché redevenues normales.")
                        from src.notifier import send_alert
                        send_alert(cfg, subject=f"Test_IA - Marché redevenu normal ({style})",
                                   message=f"[{style}] Conditions de marché redevenues normales "
                                           f"(z-scores {guard_info}).")
                        rt.guard_active = False

                # ARBITRAGE DE PRIORITÉ (voir bloc de commentaire ci-dessus) :
                # ne s'applique qu'à une NOUVELLE direction non nulle qui
                # s'oppose à la position d'un AUTRE style déjà ouverte -- ne
                # touche jamais à une décision de fermeture/maintien de la même
                # direction (déjà gérées par le cooldown de réouverture).
                conflict_blocked_by = None
                if conflict_resolution == "temporal_hierarchy" and abs(final_target) > 1e-9:
                    direction = 1 if final_target > 0 else -1
                    my_level = TIMEFRAME_HIERARCHY.get(style)
                    if my_level is not None:
                        opposing = [(other, info) for other, info in open_by_style.items()
                                    if other != style and info["direction"] == -direction]
                        blocked_by = None
                        for other, info in opposing:
                            other_level = TIMEFRAME_HIERARCHY.get(other)
                            # Un style de niveau ÉGAL ou INFÉRIEUR à nous n'est
                            # jamais restrictif -- seul un style de niveau
                            # SUPÉRIEUR (timeframe plus large) peut nous
                            # bloquer, jamais l'inverse (voir docstring de
                            # TIMEFRAME_HIERARCHY ci-dessus).
                            #
                            # ZÉRO HEDGING TOLÉRÉ (18/09, durci sur demande
                            # explicite -- un palier "écart=1 niveau -> permis
                            # à budget réduit" existait ici, retiré) : un BUY
                            # et un SELL ouverts simultanément sur le MÊME
                            # symbole par deux styles différents, même à un
                            # seul niveau d'écart (ex: H1 vs H4, observé en
                            # démo le 18/09), est le genre de pattern qu'un
                            # broker ou une prop firm anti-hedging détecte et
                            # peut flaguer -- risque réel au moment d'un
                            # retrait, pas juste une question de firme de
                            # challenge. N'IMPORTE QUEL écart >= 1 bloque
                            # désormais le style inférieur, jamais de milieu
                            # de terrain : le senior gagne toujours, point.
                            if other_level is None or other_level <= my_level:
                                continue
                            blocked_by = other
                            break
                        if blocked_by is not None:
                            conflict_blocked_by = blocked_by
                            log.warning(
                                f"[coordination] Ouverture de '{style}' (niveau hiérarchique={my_level}, "
                                f"cible={final_target:+.2f}) BLOQUÉE -- '{blocked_by}' (niveau supérieur) "
                                f"détient une position opposée -- zéro hedging toléré entre styles."
                            )
                            final_target = 0.0

                if conflict_resolution == "priority_by_score" and abs(final_target) > 1e-9:
                    direction = 1 if final_target > 0 else -1
                    opposing = [(other, info, _style_score(other))
                                for other, info in open_by_style.items()
                                if other != style and info["direction"] == -direction]
                    if opposing:
                        my_score = entry["meta"].get("score", -1e9)
                        best_other, best_info, best_other_score = max(opposing, key=lambda t: t[2])
                        if my_score > best_other_score:
                            # Le NOUVEAU style gagne (meilleur score) : ferme
                            # TOUTES les positions opposées de moindre score
                            # avant de laisser celui-ci s'ouvrir normalement.
                            for other, info, other_score in opposing:
                                other_meta = _read_json_safe(_champion_meta(other))
                                log.warning(
                                    f"[coordination] '{style}' (score={my_score:.3f}) prend la priorité sur "
                                    f"'{other}' (score={other_score:.3f}) -- fermeture de sa position "
                                    f"opposée (ticket={info['ticket']}, direction={info['direction']:+d})."
                                )
                                connector.send_order(0.0, style=other, generation=other_meta.get("generation"))
                                other_rt = runtimes.get(other)
                                if other_rt is not None:
                                    # Synchronise le cooldown de réouverture de
                                    # l'AUTRE style avec cette fermeture externe
                                    # -- sinon son état interne resterait
                                    # incohérent avec MT5 (position fermée sans
                                    # qu'il le sache), et il pourrait rouvrir la
                                    # même direction au cycle suivant sans être
                                    # soumis au cooldown normal.
                                    other_rt.cooldown_prev_target = 0.0
                                    other_rt.cooldown_last_close_at = time.time()
                                open_by_style.pop(other, None)
                        else:
                            # Le style DÉJÀ en position garde la priorité :
                            # bloque cette nouvelle ouverture pour ce cycle
                            # (retentée aux cycles suivants comme toute
                            # ouverture bloquée par un autre garde-fou).
                            conflict_blocked_by = best_other
                            log.warning(
                                f"[coordination] Ouverture de '{style}' (score={my_score:.3f}, cible="
                                f"{final_target:+.2f}) BLOQUÉE -- '{best_other}' (score="
                                f"{best_other_score:.3f}) détient déjà une position opposée "
                                f"(ticket={best_info['ticket']}) et garde la priorité."
                            )
                            final_target = 0.0

                # GARDE-FOU POSITION-SEULE (21/09, voir _position_only_entries) :
                # un style ajouté à la boucle UNIQUEMENT pour gérer une
                # position déjà ouverte ne doit JAMAIS en ouvrir une
                # NOUVELLE depuis plat -- il n'est plus validé, sa présence
                # ici sert à liquider proprement l'existant, pas à prendre
                # de nouveaux risques. Ne bloque jamais une fermeture ni un
                # maintien (seulement un départ de plat).
                if entry.get("position_only") and existing_position is None and abs(final_target) > 1e-9:
                    log.warning(f"[{style}] Ouverture BLOQUÉE (cible={final_target:+.2f}) -- ce style n'est plus "
                                 f"éligible à la démo (validation repassée sous les seuils) : conservé dans la "
                                 f"boucle uniquement pour gérer une position déjà ouverte, jamais pour en ouvrir "
                                 f"une nouvelle.")
                    final_target = 0.0

                prospective_active = set(open_by_style.keys())
                if abs(final_target) > 1e-9:
                    prospective_active.add(style)
                else:
                    prospective_active.discard(style)
                n_active = max(1, len(prospective_active))
                per_style_risk_pct = (base_max_risk_pct / n_active) if base_max_risk_pct is not None else None

                if abs(final_target) <= 1e-9:
                    stop_pct = None
                    atr_multiplier = None
                    atr_price_units = None

                generation = entry["meta"].get("generation")
                if atr_multiplier is not None:
                    stop_detail = f", stop=ATR x{atr_multiplier:.2f}" + \
                        (f" ({atr_price_units:.4f}$ ATR)" if atr_price_units is not None else " (ATR indisponible)")
                else:
                    stop_detail = f", stop={stop_pct:.2%}" if stop_pct is not None else ""
                budget_detail = f", budget={per_style_risk_pct:.3%}/{n_active} style(s) actif(s)" \
                    if per_style_risk_pct is not None else ""
                log.info(f"[{style}] Décision (gen {generation}, score={entry['meta'].get('score', 0.0):.2f}) : "
                          f"exposition={final_target:+.2f}{stop_detail}{budget_detail}")
                connector.send_order(final_target, stop_pct=stop_pct, atr_multiplier=atr_multiplier,
                                      atr_price_units=atr_price_units, style=style, generation=generation,
                                      risk_pct_override=per_style_risk_pct)

                if abs(final_target) > 1e-9:
                    open_by_style[style] = {"ticket": None, "direction": 1 if final_target > 0 else -1,
                                              "volume": None, "price_open": None}
                else:
                    open_by_style.pop(style, None)

                results.append({"style": style, "score": entry["meta"].get("score", 0.0),
                                 "generation": generation, "target": target, "final_target": final_target,
                                 "stop_pct": stop_pct, "risk_guard_triggered": final_target != target,
                                 "conflict_blocked_by": conflict_blocked_by,
                                 "risk_pct_used": per_style_risk_pct,
                                 "position_only": bool(entry.get("position_only")),
                                 "direction": existing_position["direction"] if existing_position else
                                     (1 if final_target > 0 else -1 if final_target < 0 else 0),
                                 "volume": existing_position.get("volume") if existing_position else None,
                                 "profit": existing_position.get("profit") if existing_position else None})
            except Exception:
                # Une exception sur CE style (bug de modèle, erreur MT5
                # ponctuelle, donnée manquante) ne doit jamais interrompre le
                # traitement des autres styles éligibles de ce même cycle.
                log.error(f"[{style}] Exception non gérée pendant le cycle de décision -- ce style est "
                          f"IGNORÉ pour ce cycle, les autres styles continuent normalement :\n"
                          f"{traceback.format_exc()}")
                continue

        # FIABILITÉ BACKTEST VS RÉEL, PAR STYLE : chaque style compare SES
        # PROPRES trades live (voir _LiveMemoryTracker, colonne `style` de la
        # mémoire épisodique) à SON PROPRE backtest walk-forward (le
        # "metrics" de son propre meta.json, `entry["meta"]` ci-dessus) --
        # plus de comparaison à un seul agrégat global (DEMO_META), qui
        # n'aurait plus de sens depuis le retrait du blending (chaque style
        # trade indépendamment, avec son propre walk-forward). Écrit dans
        # reports/reliability.json (lu par le tableau de bord), une entrée
        # par style sous la clé "styles".
        if memory is not None:
            styles_predicted = {entry["style"]: entry["meta"].get("metrics") for entry in eligible}
            report = compute_reliability_report(memory, styles_predicted, min_trades_for_confidence)
            save_report(report)
            for style, style_report in report["styles"].items():
                if style_report["confident"]:
                    log.info(f"[fiabilité][{style}] {style_report['verdict']}")

        try:
            write_live_status({
                "mode": "multi_position", "n_eligible_styles": len(results),
                "per_style_risk_pct": per_style_risk_pct,
                "positions": results,
                # LATENCE RÉSEAU (voir mesure ci-dessus) : None si non
                # mesurable (faux connecteur de test, échec ponctuel) --
                # jamais une clé absente, pour que le tableau de bord puisse
                # toujours s'attendre à sa présence.
                "round_trip_ms": round_trip_ms,
            }, cfg=cfg)
        except Exception:
            pass

        iterations += 1
        if max_iterations is not None and iterations >= max_iterations:
            return
        time.sleep(poll)
