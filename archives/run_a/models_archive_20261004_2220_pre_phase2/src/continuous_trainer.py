"""
continuous_trainer.py
======================
C'est ici que se joue "l'IA en constante évolution" : ce module tourne en
boucle INDÉFINIMENT et ne repart jamais de zéro.

STYLES DE TRADING MULTIPLES (scalping -> swing) :
  Le "vrai trader" demandé n'est pas un agent figé sur une seule timeframe :
  à chaque cycle, PLUSIEURS lignées progressent EN PARALLÈLE, une par
  timeframe primaire du pool configuré (`data.timeframe_pool`, ex: M15 pour
  du scalping, D1 pour du swing). Chaque lignée a son propre contexte
  multi-timeframe (toutes les timeframes plus larges disponibles) et sa
  propre mémoire de warm start (`models/champion_<TF>/`) -- un style
  scalping et un style swing n'ont pas la même quantité de features et ne
  peuvent donc pas partager les mêmes poids.

  À la fin de chaque cycle, le MEILLEUR candidat TOUS STYLES CONFONDUS
  (comparé sur un score commun sharpe/drawdown) est celui éligible à la
  promotion en démo : le style qui l'emporte peut changer d'un cycle à
  l'autre si le marché change de régime (tendanciel -> plus favorable au
  swing, ou heurté -> plus favorable au scalping).

DEUX niveaux de "meilleur agent", par lignée :
  - Le CHAMPION technique (models/champion_<TF>/) : sert uniquement de
    point de départ (warm start) pour continuer l'apprentissage de CETTE
    lignée cycle après cycle. Peut être promu même avec des métriques
    encore mauvaises (normal, surtout au tout début).
  - Le CHAMPION DÉMO (models/demo_champion/, UNIQUE, toutes lignées
    confondues) : c'est le SEUL modèle que `demo_trader.py` utilise. Il
    n'est mis à jour que si le meilleur candidat, toutes lignées
    confondues, passe les seuils de qualité (`validation.min_sharpe_to_go_live`,
    `validation.max_drawdown_allowed`) ET que le nombre minimal de cycles
    (`validation.min_generations_before_demo`) a été atteint.

VOLUME DE DONNÉES ADAPTÉ AUX HEURES DE MARCHÉ :
  Avant chaque cycle, le marché XAUUSD est-il ouvert ? Si non (week-end),
  `data.max_bars_market_closed` est utilisé à la place de `data.max_bars`
  pour reconstruire le dataset de chaque style -- typiquement BEAUCOUP plus
  d'historique, puisque rien ne presse et qu'aucune décision de trading en
  direct ne sollicite le CPU pendant la fermeture.

POPULATION ÉVOLUTIVE PAR STYLE (`continuous.population_size`) :
  Chaque style peut faire évoluer PLUSIEURS lignées indépendantes en
  parallèle (slots 0..N-1), chacune avec son propre agent, score, et
  recherche adaptative d'hyperparamètres (centre + amplitude, règle du
  1/5 -- voir ci-dessous). Le champion PUBLIC du style reste TOUJOURS le
  meilleur slot du moment, recopié à chaque cycle : demo_trader.py et
  l'ensemble multi-styles n'ont besoin de rien savoir de la population.
  Avec population_size=1 (par défaut), comportement identique à une seule
  lignée par style, comme avant.

RECHERCHE D'HYPERPARAMÈTRES ADAPTATIVE (remplace la mutation aléatoire à
amplitude fixe) :
  Chaque lignée (slot) mute autour de son propre "centre de recherche" (les
  hyperparamètres de son dernier succès) avec sa propre amplitude, qui
  grandit après un succès et rétrécit après un échec (règle du 1/5 des
  stratégies évolutives), avec un coup de pouce jusqu'à l'amplitude
  maximale en cas de plateau prolongé (`continuous.overfitting_patience_cycles`).

SUIVI ANTI-SURAPPRENTISSAGE :
  L'évolution continue tourne à l'infini par conception -- le garde-fou
  "un candidat n'est promu que s'il fait STRICTEMENT mieux" empêche déjà
  toute régression. En complément, le nombre de cycles consécutifs sans
  la moindre amélioration est suivi et journalisé (`continuous.
  overfitting_patience_cycles`) : au-delà du seuil, un avertissement
  explicite est affiché pour vous signaler un plateau (signe possible de
  sur-apprentissage des données disponibles), sans jamais arrêter le
  système ni annuler le dernier bon champion.
"""
from __future__ import annotations
import os
import json
import time
import shutil
import logging
import numpy as np
from concurrent.futures import ProcessPoolExecutor

from src.trading_env import TradingEnv, ENV_VERSION
from src.multi_asset import discover_configured_symbols, load_symbol_ohlcv, stability_veto
from src.style_utils import base_timeframe
from src.agent import TradingAgent
from src.backtester import evaluate_agent_walkforward, passes_validation, run_episode, compute_walk_forward_efficiency
from src.evolution import mutate_hyperparams
from src import experiment_journal as journal
from src.episodic_memory import EpisodicMemory
from src.market_hours import is_market_open
from src.io_utils import read_json_safe

log = logging.getLogger("continuous_trainer")

MODELS_ROOT = "models"
DEMO_DIR = os.path.join(MODELS_ROOT, "demo_champion")
DEMO_MODEL = os.path.join(DEMO_DIR, "agent")
DEMO_META = os.path.join(DEMO_DIR, "meta.json")
DEMO_STATS = os.path.join(DEMO_DIR, "norm_stats.json")

CANDIDATES_TMP_DIR = os.path.join(MODELS_ROOT, "_tmp_candidates")
PROGRESS_FILE = os.path.join(MODELS_ROOT, "_progress.json")

DEFAULT_VALIDATION = {
    "min_sharpe_to_go_live": 1.0,
    "max_drawdown_allowed": 0.20,
    "min_generations_before_demo": 20,
    "min_trades_to_go_live": 30,
}


def _resolve_stress_test(tf: str, stress_test_default: bool, stress_test_styles) -> bool:
    """Détermine si le stress-test (voir src/stress_test.py) s'applique à CE
    style : la liste `continuous.stress_test_styles`, si configurée,
    l'emporte sur le réglage global `continuous.stress_test` -- permet de
    ne l'appliquer qu'aux styles à petit historique (les plus exposés à la
    mémorisation par warm-start) si le coût sur les gros historiques devient
    trop élevé. `stress_test_styles=None` (pas configuré) = comportement
    d'origine, le réglage global s'applique à tous les styles."""
    if stress_test_styles is not None:
        return tf in stress_test_styles
    return stress_test_default


def _stress_seed_for_style(style: str) -> int:
    """Graine STABLE PAR STYLE (jamais par génération/cycle) pour le
    réordonnancement de blocs du stress-test (voir src/stress_test.py) :
    le même style doit toujours affronter le MÊME scénario adversarial
    d'un cycle à l'autre, sinon chaque candidat est comparé au champion
    incumbent sur un réarrangement DIFFÉRENT à chaque cycle -- un bruit de
    comparaison qui s'ajoute à la difficulté voulue, pas seulement elle.
    zlib.crc32 (jamais hash() -- randomisé par processus en Python 3, donc
    instable entre les workers spawnés) donne la même graine partout, pour
    toujours, pour un même nom de style."""
    import zlib
    return zlib.crc32(style.encode()) & 0x7FFFFFFF


def _confidence_marker(n_trades: int, min_trades_conf: int) -> str:
    """✓ si le score d'un style repose sur assez de trades pour qu'on lui
    fasse confiance (voir _confident_score), △ sinon -- ajouté à côté de
    CHAQUE score dans l'alerte de cycle pour qu'un score qui BAISSE parce
    que son champion vient de franchir ce seuil de fiabilité (donc un
    VRAI progrès, pas une régression) ne soit plus lisible comme une
    mauvaise nouvelle sur le simple aperçu d'une notification -- cas réel
    rencontré cette nuit avec D1 (4.69 -> 4.10 en franchissant 100 trades).
    `min_trades_conf` à 0 désactive le mécanisme (voir
    `continuous.min_trades_for_confident_score`) : tout est alors marqué ✓."""
    if min_trades_conf <= 0:
        return "✓"
    return "✓" if n_trades >= min_trades_conf else "△"


def _format_score_delta(current: float, previous: float | None) -> str:
    """Marge de progression affichée à côté d'un score dans l'alerte de
    cycle (ex: "0.90 (score +0.5%)") -- en pourcentage du score PRÉCÉDENT,
    pour donner un ordre de grandeur immédiat même sur un changement de
    signe (sur demande explicite -- le pourcentage a été jugé plus utile
    que le point absolu, même dans ce cas). Le mot "score" est TOUJOURS
    présent pour ne jamais laisser croire à un rendement financier (cas
    réel rencontré : un style passant de -1.01 à +2.15 affichait "+311%",
    qui avait pu être lu à tort comme un gain de trading avant qu'on
    clarifie que c'est le score interne, pas un pourcentage financier).

    Seule exception, purement mathématique (pas un choix de lisibilité) :
    le score précédent quasi nul rendrait le pourcentage infini/absurde
    (ex: +50000%) -- variation absolue utilisée UNIQUEMENT dans ce cas.
    Chaîne vide si aucun score précédent connu (premier cycle depuis le
    démarrage, ou premier passage de ce style)."""
    if previous is None:
        return ""
    if abs(previous) < 1e-6:
        return f" (score {current - previous:+.2f} pt)"
    pct = (current - previous) / abs(previous) * 100
    return f" (score {pct:+.1f}%)"


def _confident_score(score: float, n_trades: int, min_trades: int) -> float:
    """Score utilisé pour les comparaisons de PROMOTION (jamais pour
    l'affichage -- voir run_one_cycle) : réduit un score PROBABLEMENT
    optimiste par manque de données (peu de trades, forte variance) sans
    jamais aider un mauvais score. Répond à un cas réel observé (style D1) :
    un candidat évalué sur seulement 5 à 11 trades par fenêtre peut afficher
    un Sharpe très élevé par pur coup de chance statistique (petit
    échantillon), devenir champion, puis bloquer durablement toute
    amélioration GLOBALE détectée (voir cycles_since_improvement) -- aucun
    autre style ne peut plus jamais "améliorer" tant qu'il ne dépasse pas
    cette barre artificiellement haute, même en progressant réellement.

    ÉLARGI le 30/09 (bug réel trouvé -- "l'IA se sent performante en foutant
    rien") : la version d'origine n'ajustait QUE les scores positifs
    ("n'aide jamais un mauvais résultat"), en supposant qu'un score négatif
    est déjà pénalisé et n'a pas besoin d'aide. Mais un style qui reste plat
    presque tout le temps (peu de trades, quasi aucun risque pris) peut
    afficher un score LÉGÈREMENT négatif -- moins mauvais que des candidats
    plus actifs mais imparfaits -- et gagner les comparaisons de promotion
    par ce simple effet de "moins pire", sans que le garde-fou ci-dessus ne
    s'applique jamais (cas réel observé : H1 gén.712, score=-0.105 sur
    seulement 22 trades contre un seuil de 100, jamais inquiété par cette
    fonction, bloquant toute vraie progression). Un score négatif issu d'un
    petit échantillon est TOUT AUSSI incertain qu'un score positif -- il ne
    doit pas non plus gagner une comparaison juste parce qu'il "a l'air"
    moins mauvais par chance statistique. Pour un score positif, on RÉDUIT
    vers zéro (`score * ratio`, comportement d'origine inchangé). Pour un
    score négatif, on ACCENTUE symétriquement à l'opposé de zéro
    (`score / ratio`) -- même formule, même logique, mais dans le sens qui
    le rend plus difficile à battre injustement au lieu de plus facile.
    `min_trades <= 0` ou `n_trades <= 0` désactive l'ajustement (score
    inchangé) -- comportement d'origine.
    """
    if min_trades <= 0 or n_trades <= 0:
        return score
    ratio = min(1.0, n_trades / min_trades)
    if ratio >= 1.0 or score == 0:
        return score
    return score * ratio if score > 0 else score / ratio


def _champion_dir(tf: str) -> str:
    return os.path.join(MODELS_ROOT, f"champion_{tf}")


def _champion_model(tf: str) -> str:
    return os.path.join(_champion_dir(tf), "agent")


def _champion_meta(tf: str) -> str:
    return os.path.join(_champion_dir(tf), "meta.json")


def _champion_stats(tf: str) -> str:
    return os.path.join(_champion_dir(tf), "norm_stats.json")


HISTORY_MAX_SNAPSHOTS = 20   # borne le disque -- garde les N dernières promotions, pas un historique infini


def _archive_snapshot(model_path: str, stats_path: str, meta_path: str, history_root: str, generation: int):
    """Archive une promotion (modèle .zip + stats de normalisation + meta)
    dans `<history_root>/gen_<generation>/`, HORODATÉE et NE TOUCHANT JAMAIS
    aux fichiers "courants" -- répond au besoin de pouvoir revenir
    EXACTEMENT à un champion antérieur si une promotion future s'avère
    mauvaise après coup (ex: un bug de mesure découvert plus tard, comme
    celui du stress-test corrigé cette nuit). Best effort : ne lève jamais
    d'exception (un échec d'archivage ne doit jamais bloquer une
    promotion). Ne capture QUE les promotions à partir de maintenant --
    les champions déjà écrasés avant l'ajout de cette fonction ne sont pas
    récupérables rétroactivement.
    """
    try:
        snap_dir = os.path.join(history_root, f"gen_{generation}")
        os.makedirs(snap_dir, exist_ok=True)
        if os.path.exists(model_path + ".zip"):
            shutil.copy(model_path + ".zip", os.path.join(snap_dir, "agent.zip"))
        if os.path.exists(stats_path):
            shutil.copy(stats_path, os.path.join(snap_dir, "norm_stats.json"))
        if os.path.exists(meta_path):
            shutil.copy(meta_path, os.path.join(snap_dir, "meta.json"))
        _prune_history(history_root)
    except Exception:
        pass


def _prune_history(history_root: str):
    """Garde seulement les `HISTORY_MAX_SNAPSHOTS` promotions les plus
    RÉCENTES (par numéro de génération, pas date de fichier) -- évite une
    croissance illimitée du disque sur un système qui tourne H24 pendant
    des mois. Best effort, appelée par _archive_snapshot uniquement."""
    if not os.path.isdir(history_root):
        return
    entries = [d for d in os.listdir(history_root) if d.startswith("gen_")]

    def _gen_num(d):
        try:
            return int(d.split("_", 1)[1])
        except (IndexError, ValueError):
            return -1

    entries.sort(key=_gen_num)
    for stale in entries[:-HISTORY_MAX_SNAPSHOTS]:
        shutil.rmtree(os.path.join(history_root, stale), ignore_errors=True)


# ------------------------------------------------------------------------ #
# POPULATION ÉVOLUTIVE : chaque style peut faire évoluer PLUSIEURS lignées
# indépendantes en parallèle (`continuous.population_size`, slots 0..N-1),
# chacune avec son propre agent/score/recherche adaptative -- une vraie
# diversité génétique plutôt qu'une seule lignée + mutation aléatoire. Le
# CHAMPION PUBLIC du style (`_champion_*`, lu par demo_trader.py et
# l'ensemble multi-styles) reste TOUJOURS le meilleur slot du moment,
# recopié à chaque cycle -- rien ne change côté démo/ensemble.
#
# Avec `population_size <= 1` (par défaut), les chemins d'un slot
# s'identifient EXACTEMENT aux chemins classiques `_champion_*` ci-dessus :
# comportement rigoureusement identique à avant, aucune migration, aucun
# risque pour qui n'active pas cette fonctionnalité.
# ------------------------------------------------------------------------ #
def _slot_dir(tf: str, slot: int, population_size: int) -> str:
    if population_size <= 1:
        return _champion_dir(tf)
    return os.path.join(_champion_dir(tf), f"pop_{slot}")


def _slot_model(tf: str, slot: int, population_size: int) -> str:
    return os.path.join(_slot_dir(tf, slot, population_size), "agent")


def _slot_meta(tf: str, slot: int, population_size: int) -> str:
    return os.path.join(_slot_dir(tf, slot, population_size), "meta.json")


def _slot_stats(tf: str, slot: int, population_size: int) -> str:
    return os.path.join(_slot_dir(tf, slot, population_size), "norm_stats.json")


def _slot_search_state(tf: str, slot: int, population_size: int) -> str:
    return os.path.join(_slot_dir(tf, slot, population_size), "search_state.json")


# ------------------------------------------------------------------------ #
# Fonction exécutée dans un PROCESSUS SÉPARÉ (voir ProcessPoolExecutor plus
# bas) : DOIT rester une fonction de haut niveau du module (picklable), et ne
# recevoir/retourner QUE des objets sérialisables (dict/DataFrame/liste/str),
# jamais d'objet SB3/Torch/env "vivant".
# ------------------------------------------------------------------------ #
def _train_candidate_worker(spec: dict) -> dict:
    torch_threads = spec.get("torch_threads")
    if torch_threads:
        import torch
        torch.set_num_threads(max(1, torch_threads))
        try:
            torch.set_num_interop_threads(max(1, torch_threads))
        except RuntimeError:
            pass  # déjà fixé (ne peut être changé qu'une fois par processus) -> sans conséquence

    label = spec.get("label")

    # `randomize_start=True` (29/09, voir trading_env.py::TradingEnv.__init__
    # pour le diagnostic complet) -- UNIQUEMENT sur cet env d'ENTRAÎNEMENT,
    # jamais passé via `env_kwargs` (partagé avec eval_env ci-dessous et
    # `evaluate_agent_walkforward`, qui doivent rester déterministes).
    env = TradingEnv(spec["train_df"], randomize_start=True, **spec["env_kwargs"])
    agent = TradingAgent(env, spec["hyperparams"], warm_start_model_path=spec["warm_start_path"])
    agent.learn(spec["timesteps"], label=label)

    stress_seed = _stress_seed_for_style(spec.get("style", ""))
    metrics = evaluate_agent_walkforward(agent, spec["val_df"], spec["env_kwargs"],
                                          n_windows=spec.get("eval_windows", 3),
                                          stress_test=spec.get("stress_test", False),
                                          stress_seed=stress_seed,
                                          timeframe=base_timeframe(spec.get("style", "H1")),
                                          garch_stress=spec.get("garch_stress", False),
                                          garch_context_tfs=spec.get("garch_context_tfs"),
                                          garch_stats=spec.get("garch_stats"),
                                          garch_params=spec.get("garch_params"),
                                          macro_event_timestamps=spec.get("macro_event_timestamps"),
                                          friction_profile=spec.get("friction_profile", "pessimistic"))
    # MÉTRIQUE DE FITNESS (audit institutionnel, section 2, "Audit des
    # Métriques de Fitness" -- remplacer le profit brut/win rate par Sortino
    # OU Sharpe) : "sortino" par défaut -- ne pénalise QUE la variance des
    # rendements NÉGATIFS (voir src/backtester.py::compute_metrics), plus
    # fidèle à "le risque" qu'un Sharpe qui pénalise à égalité une hausse
    # erratique et une baisse erratique. `continuous.fitness_metric: "sharpe"`
    # restaure l'ancien comportement. Repli sur "sharpe" si la métrique
    # demandée est absente du dict retourné (jamais un KeyError ici).
    fitness_metric = spec.get("fitness_metric", "sortino")
    fitness_value = metrics.get(fitness_metric, metrics["sharpe"])
    # EXCÈS DE RENDEMENT VS MARCHÉ (25/09, demande explicite -- voir
    # src/backtester.py::compute_metrics) : `continuous.excess_return_weight`
    # (défaut 0.0 = comportement d'origine) récompense un candidat qui fait
    # au moins aussi bien que le buy-and-hold de l'instrument sur les
    # fenêtres walk-forward, et pénalise celui qui reste plat pendant une
    # hausse. C'est CE terme qui oriente la sélection (le garde-fou
    # `validation.max_lag_vs_market_pts` ne fait que filtrer). Avec 5.0, 10
    # points d'excès ~= +0.5 de score, du même ordre qu'un écart de Sortino
    # significatif. Change l'échelle des scores : les champions évalués sans
    # ce terme ne sont plus directement comparables (cf. note similaire sur
    # spread_volatility_multiplier en config).
    excess_weight = float(spec.get("excess_return_weight", 0.0) or 0.0)
    score = (fitness_value - 2.0 * metrics["max_drawdown"]
             + excess_weight * metrics.get("excess_return", 0.0))

    # WALK-FORWARD EFFICIENCY (audit institutionnel, section 2, item 6) --
    # OPT-IN (`continuous.compute_wfe`, défaut False) : voir
    # src/backtester.py::compute_walk_forward_efficiency. Coût réel (une
    # évaluation complète supplémentaire sur `train_df`, potentiellement
    # lente avec le LSTM récurrent -- voir sa docstring) -- désactivé par
    # défaut pour ne jamais ralentir silencieusement le cycle déjà calibré en
    # production ; activez-le explicitement pour commencer à mesurer/gater
    # dessus (voir `validation.min_wfe`, ignoré tant qu'aucun candidat n'a de
    # clé "wfe"). Best-effort total : un échec de calcul WFE ne doit JAMAIS
    # invalider l'évaluation principale déjà obtenue ci-dessus.
    if spec.get("compute_wfe", False):
        try:
            wfe_result = compute_walk_forward_efficiency(
                agent, spec["train_df"], metrics, spec["env_kwargs"],
                timeframe=base_timeframe(spec.get("style", "H1")),
                is_eval_bars=spec.get("wfe_is_eval_bars", 5000),
                oos_n_bars=len(spec["val_df"]),
            )
            metrics["wfe"] = wfe_result["wfe"]
            metrics["wfe_detail"] = wfe_result
        except Exception:
            pass

    # Rejoue un épisode sur la validation pour alimenter la mémoire épisodique.
    eval_env = TradingEnv(spec["val_df"], **spec["env_kwargs"])
    eval_env = run_episode(agent, eval_env)
    trades = [{"entry": t["entry"], "exit": t["exit"], "position": t["position"],
               "pnl_pct": t["pnl_pct"], "context": t["context"]} for t in eval_env.trade_log]

    agent.save(spec["out_path"])
    return {
        "score": score, "metrics": metrics, "model_path": spec["out_path"],
        "trades": trades, "max_drawdown": eval_env.max_drawdown,
        "generation": spec["generation"], "style": spec["style"], "slot": spec["slot"],
        "feature_columns": spec["env_kwargs"]["feature_columns"],
        "context_timeframes": spec["context_timeframes"],
        "hyperparams": spec["hyperparams"], "env_search": spec.get("env_search"),
    }


class ContinuousEvolutionTrainer:
    def __init__(self, cfg: dict, get_data_fn, timeframe_pool: list[str], env_kwargs: dict):
        """
        get_data_fn(primary_tf) : rappelée à CHAQUE cycle pour CHAQUE style du
        pool, retourne (train_df, val_df, stats, feature_columns,
        context_timeframes) déjà normalisés et à jour pour ce style.
        """
        self.cfg = cfg
        self.cfg["validation"] = {**DEFAULT_VALIDATION, **self.cfg.get("validation", {})}
        self.get_data_fn = get_data_fn
        self.timeframe_pool = timeframe_pool
        self.base_env_kwargs = env_kwargs

        self.population_size = max(1, cfg["continuous"].get("population_size", 1))

        os.makedirs(DEMO_DIR, exist_ok=True)
        os.makedirs(CANDIDATES_TMP_DIR, exist_ok=True)
        for tf in timeframe_pool:
            os.makedirs(_champion_dir(tf), exist_ok=True)
            for slot in range(self.population_size):
                os.makedirs(_slot_dir(tf, slot, self.population_size), exist_ok=True)

        self.memory = EpisodicMemory(cfg["memory"]["db_path"], cfg["memory"]["max_episodes"])

        progress = self._read_json(PROGRESS_FILE)
        self.generation = progress.get("generation", 0)
        self.best_ever_score = progress.get("best_ever_score", -1e9)
        self.cycles_since_improvement = progress.get("cycles_since_improvement", 0)
        # Suivi SÉPARÉ, ajusté par la confiance (voir _confident_score) :
        # `best_ever_score` ci-dessus reste le record BRUT affiché (dashboard,
        # transparence) -- mais décider si on a "vraiment" progressé (et donc
        # remettre `cycles_since_improvement` à zéro) sur CE chiffre brut
        # laisserait un score gonflé par un petit échantillon (ex: un style
        # qui trade rarement) bloquer indéfiniment la détection de progrès
        # réels chez les AUTRES styles, même quand ils s'améliorent
        # sincèrement. Ce second compteur ignore ce piège sans jamais changer
        # le nombre affiché.
        self.best_ever_confident_score = progress.get("best_ever_confident_score", -1e9)
        # Score de CHAQUE style au moment de la DERNIÈRE alerte envoyée (pas
        # forcément le cycle précédent, si notify_cycle_every_n > 1) --
        # permet d'afficher une marge de progression (ex: "+0.5%") dans
        # l'alerte de cycle, pas seulement le score brut. Volontairement en
        # mémoire seulement (pas persisté) : au redémarrage, la première
        # alerte n'affiche simplement aucune marge, rien de grave.
        self._last_notified_scores: dict[str, float] = {}

        # `champion_score`/`champion_meta` (chemins _champion_*) restent le
        # CHAMPION PUBLIC du style, tous slots confondus -- lu par
        # demo_trader.py, has_champion(), status_summary(). Inchangé pour
        # qui n'utilise pas la population (population_size=1 -> slot 0 =
        # ces mêmes fichiers, donc déjà à jour).
        self.champion_score = {tf: self._read_json(_champion_meta(tf)).get("score", -1e9)
                                for tf in timeframe_pool}
        # Nombre de trades derrière CE score -- nécessaire pour
        # _confident_score (voir plus haut) : sans lui, impossible de savoir
        # si le champion actuel mérite sa confiance ou est un coup de chance
        # sur petit échantillon lors de la comparaison avec un nouveau
        # candidat.
        self.champion_n_trades = {tf: self._read_json(_champion_meta(tf)).get("metrics", {}).get("n_trades", 0)
                                   for tf in timeframe_pool}
        self.demo_champion_score = self._read_json(DEMO_META).get("score", -1e9)
        self.demo_champion_n_trades = self._read_json(DEMO_META).get("metrics", {}).get("n_trades", 0)

        # RECHERCHE D'HYPERPARAMÈTRES ADAPTATIVE, PAR SLOT (chaque lignée de
        # la population évolue indépendamment) : un "centre de recherche"
        # (les hyperparamètres autour desquels on mute) et une amplitude
        # (`sigma`) propres à CE slot, persistés d'un lancement à l'autre.
        # Voir la règle du 1/5 appliquée dans run_one_cycle.
        self.slot_score = {}
        self.slot_n_trades = {}
        self.slot_search_state = {}
        for tf in timeframe_pool:
            for slot in range(self.population_size):
                key = (tf, slot)
                slot_meta = self._read_json(_slot_meta(tf, slot, self.population_size))
                self.slot_score[key] = slot_meta.get("score", -1e9)
                self.slot_n_trades[key] = slot_meta.get("metrics", {}).get("n_trades", 0)
                self.slot_search_state[key] = self._read_json(
                    _slot_search_state(tf, slot, self.population_size))
        self._stop = False

    # ------------------------------------------------------------------ #
    def _read_json(self, path: str) -> dict:
        # Factorisé dans src/io_utils.py (tâche de nettoyage, audit
        # institutionnel) -- auparavant dupliquée à l'identique ici, dans
        # src/dashboard.py et src/demo_trader.py. Gardé comme méthode fine
        # (plutôt que de réécrire chaque site d'appel `self._read_json(...)`
        # dans cette classe) pour ne changer aucun comportement.
        return read_json_safe(path)

    def _lockbox_check(self, tf: str, model_path: str, meta_like: dict, stats: dict,
                       was_eligible_before: bool):
        """Porte lockbox (src/lockbox_gate.py). Retourne (metrics|None, ok). Mise en cache par
        cycle et par style (le même candidat est testé au niveau slot ET champion)."""
        gate_cfg = self.cfg["validation"].get("lockbox_gate") or {}
        if not gate_cfg.get("enabled", False) or tf not in (gate_cfg.get("styles") or [tf]):
            return None, True
        cache = self.__dict__.setdefault("_lockbox_cache", {})
        key = (tf, self.generation)
        if key in cache:
            return cache[key]
        try:
            from src.lockbox_gate import evaluate_on_lockbox, gate_decision
            metrics = evaluate_on_lockbox(tf, self.cfg, model_path, meta_like, stats)
            incumbent = self._read_json(_champion_meta(tf)).get("lockbox") if was_eligible_before else None
            ok, why = gate_decision(metrics, gate_cfg, incumbent)
            log.info(f"  [{tf}] porte lockbox : sharpe={metrics['sharpe']:.2f} dd={metrics['max_drawdown']:.1%} "
                     f"ret={metrics['total_return']:.1%} trades={metrics['n_trades']} "
                     f"stress_ret={metrics.get('stress_return', float('nan')):.1%} "
                     f"tiers={[round(x, 3) for x in metrics.get('thirds_returns', [])]} -> "
                     f"{'OK' if ok else 'REFUSÉ (' + why + ')'}")
            result = (metrics, ok)
        except Exception as exc:
            log.warning(f"  [{tf}] porte lockbox indisponible ({type(exc).__name__}: {exc}) -- "
                        f"candidat NON éligible par précaution.")
            result = (None, False)
        cache.clear()
        cache[key] = result
        return result

    def has_champion(self, tf: str | None = None) -> bool:
        if tf is not None:
            return os.path.exists(_champion_model(tf) + ".zip")
        return any(os.path.exists(_champion_model(t) + ".zip") for t in self.timeframe_pool)

    def has_demo_champion(self) -> bool:
        """True seulement si un agent a DÉJÀ passé les seuils de qualité,
        toutes lignées confondues. C'est cette méthode (pas has_champion())
        qu'il faut utiliser pour décider si le système est prêt pour la démo.
        LIT le flag `passes_validation` du meta de CHAQUE style (écrit dans
        run_one_cycle() dès qu'un style individuel passe, voir plus bas) --
        PAS l'existence de DEMO_MODEL, qui ne reflète que le mécanisme
        "gagnant unique tous styles confondus" (repli pour `live.ensemble:
        false`) : ce fichier peut rester absent alors qu'un style est déjà
        individuellement éligible, si un AUTRE style a un score brut plus
        élevé sans passer lui-même la validation -- l'ancien code lisait
        DEMO_MODEL ici et restait bloqué à False dans ce cas, malgré le
        docstring déjà correct."""
        return any(
            self._read_json(_champion_meta(tf)).get("passes_validation")
            for tf in self.timeframe_pool
        )

    def _recheck_gate_eligibility(self):
        """`passes_validation` n'est normalement écrit dans le meta.json d'un
        style QU'AU MOMENT d'une promotion (voir plus bas) -- si un champion
        passait déjà les seuils de qualité mais a été promu AVANT que
        `validation.min_generations_before_demo` soit atteint, son flag reste
        bloqué à `false` jusqu'à sa PROCHAINE promotion, même une fois la
        porte de générations ouverte, alors que rien de nouveau ne justifie
        d'attendre (le modèle et ses métriques n'ont pas changé). Cette
        vérification, faite à chaque cycle, corrige ce flag dès que la porte
        s'ouvre pour un champion déjà qualifié, sans attendre une nouvelle
        promotion ni ré-évaluer le modèle."""
        min_gen = self.cfg["validation"].get("min_generations_before_demo", 0)
        if self.generation + 1 < min_gen:
            return
        for tf in self.timeframe_pool:
            meta_path = _champion_meta(tf)
            meta = self._read_json(meta_path)
            if not meta or meta.get("passes_validation") or "metrics" not in meta:
                continue
            if not passes_validation(meta["metrics"], self.cfg, style=tf):
                continue
            lockbox_metrics, lockbox_ok = self._lockbox_check(
                tf, _champion_model(tf), meta, self._read_json(_champion_stats(tf)), False)
            if not lockbox_ok:
                continue
            if lockbox_metrics is not None:
                meta["lockbox"] = lockbox_metrics
            meta["passes_validation"] = True
            meta["updated_at"] = time.time()
            with open(meta_path, "w", encoding="utf-8") as f:
                json.dump(meta, f, indent=2)
            log.info(f"  -> '{tf}' passait déjà les seuils de qualité (score={meta['score']:.3f}) -- la porte de "
                      f"générations vient de s'ouvrir (génération {self.generation + 1}/{min_gen}) -> "
                      f"passes_validation corrigé à true sans attendre une nouvelle promotion.")
            try:
                from src.notifier import send_alert
                send_alert(self.cfg, subject=f"Test_IA - '{tf}' eligible a la demo",
                           message=(f"'{tf}' passait deja les seuils de qualite (score={meta['score']:.3f}, "
                                     f"sharpe={meta['metrics']['sharpe']:.2f}, "
                                     f"drawdown={meta['metrics']['max_drawdown']:.1%}, "
                                     f"trades={meta['metrics']['n_trades']}) ; la porte de generations vient de "
                                     f"s'ouvrir (generation {self.generation + 1}/{min_gen}) -- desormais eligible "
                                     f"a l'ensemble de demo (toujours en dry-run)."))
            except Exception:
                pass

    def status_summary(self, min_gen: int) -> str:
        parts = [f"{tf}: score={self.champion_score[tf]:.2f}"
                 for tf in self.timeframe_pool if self.champion_score[tf] > -1e9]
        styles_str = "; ".join(parts) if parts else "aucun agent entraîné pour l'instant"
        return f"génération {self.generation} ({styles_str}) -- minimum requis avant démo : {min_gen} générations"

    def stop(self):
        self._stop = True

    # ------------------------------------------------------------------ #
    def run_forever(self, cycle_interval_seconds: int = 300, max_cycles: int | None = None):
        """`cycle_interval_seconds` ne sert que de VALEUR DE REPLI si
        `continuous.cycle_interval_seconds` est absent de la config -- le
        délai réellement appliqué est relu depuis `self.cfg` à CHAQUE cycle
        (pas figé à l'appel), pour que ce réglage fasse partie du
        sous-ensemble éditable en direct depuis le tableau de bord (voir
        src/settings_server.py) sans nécessiter de redémarrage."""
        cycles = 0
        while not self._stop:
            try:
                self.run_one_cycle()
            except Exception as e:
                # L'évolution continue ne doit JAMAIS s'arrêter suite à une
                # erreur ponctuelle (données manquantes, échec réseau...).
                log.error(f"Erreur pendant le cycle d'évolution : {e}", exc_info=True)

            cycles += 1
            if max_cycles is not None and cycles >= max_cycles:
                break
            interval = self.cfg.get("continuous", {}).get("cycle_interval_seconds", cycle_interval_seconds)
            for _ in range(interval):
                if self._stop:
                    break
                time.sleep(1)

    def run_one_cycle(self):
        log.info(f"=== Cycle d'évolution continue #{self.generation} ===")

        self._recheck_gate_eligibility()

        # VETO DE STABILITÉ MULTI-ACTIFS (LOT 2, phase 4, point 8) : chargé
        # UNE FOIS par cycle (pas par candidat/style) -- {} si
        # `multi_asset.enabled` est faux ou si aucun dossier configuré n'est
        # trouvé (voir discover_configured_symbols, no-op gracieux), auquel
        # cas la promotion se comporte EXACTEMENT comme avant ce mécanisme.
        other_symbol_dfs = {}
        try:
            resolved_symbols = discover_configured_symbols(self.cfg)
            for symbol, path in resolved_symbols.items():
                other_symbol_dfs[symbol] = load_symbol_ohlcv(path)
        except Exception as e:
            log.warning(f"[multi-actifs] chargement des symboles additionnels impossible "
                        f"({type(e).__name__}: {e}) -- veto de stabilité désactivé pour ce cycle.")
            other_symbol_dfs = {}

        # ALERTE AU LANCEMENT DU CYCLE (en plus de celle de fin de cycle déjà
        # envoyée plus bas) : même garde-fou (`notifications.notify_every_cycle`
        # / `notify_cycle_every_n`) pour rester cohérent avec le rythme déjà
        # choisi -- best effort, ne doit jamais bloquer le cycle.
        try:
            notif_cfg = self.cfg.get("notifications", {})
            if notif_cfg.get("notify_every_cycle"):
                every_n = max(1, int(notif_cfg.get("notify_cycle_every_n", 1)))
                if (self.generation + 1) % every_n == 0:
                    from src.notifier import send_alert
                    send_alert(self.cfg, subject=f"Test_IA - cycle {self.generation + 1} démarré",
                               message=f"Cycle {self.generation + 1} lancé -- styles : "
                                       f"{', '.join(self.timeframe_pool)}.")
        except Exception:
            pass

        market_open = is_market_open(self.cfg)
        log.info(f"Marché XAUUSD : {'OUVERT' if market_open else 'FERMÉ (week-end) -> volume de données étendu pour ce cycle'}.")

        n_per_style = self.cfg["continuous"].get("candidates_per_cycle", 3)
        # Pendant la FERMETURE du marché, aucune décision de trading en
        # direct ne presse (voir data.max_bars_market_closed, même logique) :
        # si configuré, on pousse plus de pas d'apprentissage par cycle,
        # puisque le seul coût est un cycle plus long, pas un risque en démo.
        timesteps = self.cfg["continuous"].get("timesteps_per_cycle", 5000)
        if not market_open:
            timesteps = self.cfg["continuous"].get("timesteps_per_cycle_market_closed", timesteps)
        base_mutation_scale = self.cfg["continuous"].get("mutation_scale", 0.2)
        mutation_scale_max = self.cfg["continuous"].get("mutation_scale_max", 1.0)
        adaptive = self.cfg["continuous"].get("adaptive_mutation", True)
        patience = self.cfg["continuous"].get("overfitting_patience_cycles", 15)
        eval_windows = self.cfg["continuous"].get("eval_windows", 3)
        # MÉTRIQUE DE FITNESS (audit institutionnel, section 2) : voir
        # _train_candidate_worker -- "sortino" par défaut, "sharpe" restaure
        # l'ancien comportement.
        fitness_metric = self.cfg["continuous"].get("fitness_metric", "sortino")
        excess_return_weight = self.cfg["continuous"].get("excess_return_weight", 0.0)
        # WALK-FORWARD EFFICIENCY (voir _train_candidate_worker) : opt-in,
        # désactivé par défaut (coût CPU réel, voir commentaire là-bas).
        compute_wfe = self.cfg["continuous"].get("compute_wfe", False)
        wfe_is_eval_bars = self.cfg["continuous"].get("wfe_is_eval_bars", 5000)
        stress_test = self.cfg["continuous"].get("stress_test", False)
        # SURCHARGE PAR STYLE (voir `continuous.stress_test_styles`) : le
        # stress-test (voir src/stress_test.py -- blocs réels réordonnés +
        # fenêtre haute volatilité) coûte 2 évaluations supplémentaires par
        # candidat, notable avec le LSTM sur un GROS dataset (M15/H1) --
        # mais quasi gratuit sur un PETIT (H4/D1). Ce sont justement les
        # styles à petit dataset qui risquent le plus de mémoriser l'ordre
        # chronologique exact plutôt que d'apprendre un schéma généralisable
        # (warm-start répété sur les MÊMES quelques milliers de bougies,
        # génération après génération) -- le stress-test les force à
        # performer sur un RÉARRANGEMENT des mêmes blocs réels, jamais vu
        # sous cette forme exacte, ce qui pénalise directement une politique
        # qui n'aurait fait que mémoriser la séquence d'origine. None (pas
        # de liste configurée) = comportement d'origine, `stress_test`
        # s'applique à tous les styles uniformément.
        stress_test_styles = self.cfg["continuous"].get("stress_test_styles")
        # GARCH (audit institutionnel, section 1, "Modélisation non linéaire
        # de la Volatilité") : interrupteur INDÉPENDANT du `stress_test`
        # booléen ci-dessus (config racine `stress_test.garch.*`, PAS
        # `continuous.stress_test` -- deux sections différentes malgré le nom
        # proche, voir config/autonomous.yaml) -- voir
        # src/stress_test.py::garch_stress_dataset. Réutilise `_resolve_stress_test`
        # avec la MÊME liste `stress_test_styles` ci-dessus plutôt que
        # d'introduire une troisième liste de styles séparée à maintenir.
        garch_cfg = (self.cfg.get("stress_test") or {}).get("garch") or {}
        garch_enabled = bool(garch_cfg.get("enabled", False))
        garch_params = {k: garch_cfg[k] for k in ("dof", "alpha", "beta") if k in garch_cfg}
        # FRICTIONS CALIBRABLES (LOT 2, phase 5) : "pessimistic" (défaut, non
        # configuré) reproduit EXACTEMENT le comportement d'origine (mêmes
        # valeurs qu'inject_macro_shocks utilisait déjà) -- voir
        # src/stress_test.py::resolve_friction_params.
        friction_profile = (self.cfg.get("frictions") or {}).get("profile", "pessimistic")
        # CALENDRIER MACRO RÉEL (audit institutionnel, section 3) : chargé
        # UNE SEULE FOIS ici (pas par candidat/par style) -- voir
        # src/stress_test.py::load_macro_events_csv. `stress_test.macro_events_csv`
        # absent/null (défaut) = comportement d'origine inchangé (None
        # transmis à evaluate_agent_walkforward -> proxy statistique). Un
        # chemin configuré qui échoue à charger (fichier absent/mal formé)
        # ne doit PAS interrompre le cycle -- log d'erreur + repli sur None
        # (proxy), jamais une exception qui remonterait jusqu'à run_one_cycle.
        macro_events_csv = (self.cfg.get("stress_test") or {}).get("macro_events_csv")
        macro_event_timestamps = None
        if macro_events_csv:
            try:
                from src.stress_test import load_macro_events_csv
                macro_event_timestamps = load_macro_events_csv(macro_events_csv)
                log.info(f"  Calendrier macro chargé depuis '{macro_events_csv}' : "
                          f"{len(macro_event_timestamps)} événement(s).")
            except Exception as e:
                log.error(f"  Échec du chargement du calendrier macro '{macro_events_csv}' "
                          f"({type(e).__name__}: {e}) -- repli sur le proxy statistique par défaut.")
                macro_event_timestamps = None
        base_hp = self.cfg["agent"]
        population_size = self.population_size

        # COÛT D'EXÉCUTION RÉEL : puisqu'on est déjà connecté à MT5 (voir
        # src/live_data_feed.py), on calibre le coût de transaction de
        # l'entraînement sur le spread RÉELLEMENT mesuré chez le broker
        # plutôt que sur la valeur devinée dans `environment.transaction_cost`
        # -- dès qu'une mesure récente est disponible (voir
        # `live_feed_spread_max_age_hours`). Retombe silencieusement sur la
        # config si aucune mesure récente n'existe (--no-demo sans MT5,
        # ou alimentation live désactivée).
        from src.live_data_feed import read_cached_spread
        max_age = self.cfg.get("data", {}).get("live_feed_spread_max_age_hours", 6.0)
        measured_spread = read_cached_spread(max_age_hours=max_age)
        env_kwargs_override = {}
        if measured_spread is not None:
            env_kwargs_override["transaction_cost"] = measured_spread
            log.info(f"  Coût de transaction calibré sur le spread réel mesuré : {measured_spread:.4%} "
                      f"(au lieu de {self.base_env_kwargs.get('transaction_cost'):.4%} configuré).")

        total_candidates = n_per_style * population_size * len(self.timeframe_pool)
        max_workers = self.cfg["continuous"].get("parallel_workers", total_candidates)
        max_workers = max(1, min(max_workers, total_candidates, os.cpu_count() or 1))
        # `cpu_target_threads` : budget TOTAL de threads logiques à utiliser
        # PENDANT la COURTE phase d'entraînement (celle qui sature réellement
        # les cœurs -- la phase d'évaluation walk-forward qui suit, elle, ne
        # charge le CPU qu'à 15-35% : la limiter via `parallel_workers`
        # coûterait des minutes de file d'attente pour rien, voir README).
        # Réparti sur tous les candidats simultanément (contrairement à
        # réduire `parallel_workers`, aucun candidat n'attend) : certains
        # reçoivent un thread de plus que d'autres pour approcher le budget
        # au plus près (ex: 12 threads sur 8 candidats -> 4 candidats à 2
        # threads + 4 à 1 thread). None (par défaut) = pas de limite, un
        # thread par cœur logique comme avant.
        target_threads = self.cfg["continuous"].get("cpu_target_threads")
        if target_threads is None:
            target_threads = os.cpu_count() or 1
        target_threads = max(max_workers, min(target_threads, os.cpu_count() or 1))
        base_threads, extra = divmod(target_threads, max_workers)
        thread_counts = [base_threads + 1 if i < extra else base_threads for i in range(max_workers)]

        memory_top_k = self.cfg.get("memory", {}).get("similarity_top_k", 5)

        specs = []
        style_stats = {}
        candidate_index = 0
        rs_cfg = self.cfg["continuous"].get("reward_search") or {}
        reward_bounds = ({k: tuple(v) for k, v in (rs_cfg.get("bounds") or {}).items()}
                          if rs_cfg.get("enabled") else {})
        reward_sigma = float(rs_cfg.get("sigma", 0.35))
        reward_defaults = {"drawdown_penalty": 2.0, "giveback_penalty_coef": 0.03,
                           "friction_penalty_coef": 0.01}
        for tf in self.timeframe_pool:
            train_df, val_df, stats, feature_columns, context_tfs = self.get_data_fn(tf)
            style_stats[tf] = stats
            style_stress_test = _resolve_stress_test(tf, stress_test, stress_test_styles)
            # GARCH (voir plus haut) : même résolution par style que
            # style_stress_test ci-dessus, avec `garch_enabled` comme
            # interrupteur global -- `garch_stress_dataset` retombe de toute
            # façon gracieusement sur None pour M15/M30 (voir
            # GARCH_STRESS_SUPPORTED_PRIMARY_TFS), donc l'activer pour un
            # style non supporté ne coûte qu'un essai silencieusement ignoré.
            style_garch = _resolve_stress_test(tf, garch_enabled, stress_test_styles)
            # instantané de mémoire épisodique PROPRE À CE STYLE (filtré par
            # nombre de features -- voir EpisodicMemory.snapshot) : calculé
            # UNE FOIS ici, transmis (picklable) à chaque processus candidat
            # de ce style plutôt que de repartager une connexion sqlite.
            # sources=["backtest"] EXCLUT les épisodes live (trading réel) de
            # ce signal : sans ça, un trade réel d'il y a quelques heures
            # (contexte de marché très récent) pouvait être retrouvé par
            # similarité pendant l'évaluation d'un candidat sur une fenêtre
            # historique bien antérieure -- une fuite d'information du futur
            # vers le passé qui gonflait artificiellement la vraisemblance
            # des scores (trouvé et corrigé le 15/09, voir episodic_memory.py
            # ::store pour l'explication complète).
            memory_snapshot = self.memory.snapshot(dim=len(feature_columns), sources=["backtest"])
            # SURCHARGE D'ENVIRONNEMENT PAR STYLE (30/09, voir
            # environment.style_overrides dans run_config_A.yaml -- même
            # principe que agent.style_overrides ci-dessus, mais pour des
            # paramètres de TradingEnv plutôt que d'hyperparamètres PPO, ex:
            # `learn_take_profit`) : contrairement à `env_kwargs_override`
            # (calculé dynamiquement, ex: spread mesuré, partagé par TOUS les
            # styles), ceci cible explicitement UN SEUL style choisi.
            env_style_overrides = self.cfg.get("environment", {}).get("style_overrides", {}).get(tf, {})
            style_env_kwargs = {
                **self.base_env_kwargs, **env_kwargs_override, **env_style_overrides,
                "feature_columns": feature_columns,
                "memory_snapshot": memory_snapshot, "memory_top_k": memory_top_k, "style": tf,
            }
            # SURCHARGE D'ARCHITECTURE PAR STYLE (29/09, voir agent.style_overrides
            # dans run_config_A.yaml pour le contexte complet) : fusionnée ICI
            # (pas une seule fois pour tous les styles) car chaque style a son
            # propre `base_hp` effectif -- un style sans surcharge garde EXACTEMENT
            # `base_hp` (même objet, aucune copie inutile à chaque cycle).
            style_overrides = base_hp.get("style_overrides", {}).get(tf)
            style_base_hp = {**base_hp, **style_overrides} if style_overrides else base_hp
            # POPULATION : chaque slot est une lignée INDÉPENDANTE (son
            # propre warm start, son propre centre/amplitude de recherche
            # adaptative -- règle du 1/5, coup de pouce sur plateau
            # prolongé). Avec population_size=1, slot 0 = l'ancien
            # comportement à l'identique (chemins _slot_* == _champion_*).
            for slot in range(population_size):
                warm_start_path = (_slot_model(tf, slot, population_size)
                                    if os.path.exists(_slot_model(tf, slot, population_size) + ".zip") else None)
                slot_state = self.slot_search_state.get((tf, slot)) or {}
                slot_center = slot_state.get("center") or style_base_hp
                if style_overrides:
                    # La surcharge d'architecture est une CONTRAINTE, pas
                    # juste une valeur de départ (29/09) : un `center` déjà
                    # persisté sur disque AVANT l'ajout de cette surcharge
                    # (search_state.json d'un cycle précédent) contient
                    # encore l'ancienne taille -- sans cette ré-application,
                    # il la ferait gagner silencieusement, et le warm start
                    # échouerait (forme différente de celle reconstruite par
                    # style_base_hp/agent.py) à chaque cycle suivant.
                    slot_center = {**slot_center, **style_overrides}
                slot_sigma = slot_state.get("sigma", base_mutation_scale) if adaptive else base_mutation_scale
                for i in range(n_per_style):
                    hp = slot_center if i == 0 else mutate_hyperparams(
                        slot_center, slot_sigma,
                        mutation_bounds=self.cfg["continuous"].get("mutation_bounds"))
                    # RECHERCHE AUTONOME SUR LA RÉCOMPENSE (04/10) : le candidat 0 reste le
                    # témoin (récompense du style) ; les autres tirent leurs pénalités autour
                    # du meilleur essai du journal. Seule la récompense d'ENTRAÎNEMENT change :
                    # le score/la validation (eval_env) sont évalués avec les mêmes env_kwargs
                    # mais le score, lui, ne dépend pas de ces pénalités.
                    cand_env_kwargs, env_search = style_env_kwargs, None
                    if reward_bounds and i > 0:
                        center = {n: style_env_kwargs.get(n, reward_defaults[n]) for n in reward_bounds}
                        center.update(journal.best_known_params(tf, reward_bounds))
                        env_search = journal.sample_params(center, reward_bounds, reward_sigma)
                        cand_env_kwargs = {**style_env_kwargs, **env_search}
                    specs.append({
                        "train_df": train_df, "val_df": val_df, "env_kwargs": cand_env_kwargs,
                        "env_search": env_search,
                        "hyperparams": hp, "warm_start_path": warm_start_path, "timesteps": timesteps,
                        "out_path": os.path.join(CANDIDATES_TMP_DIR, f"{tf}_{slot}_{i}"),
                        "generation": self.generation, "eval_windows": eval_windows,
                        "stress_test": style_stress_test, "fitness_metric": fitness_metric,
                        "excess_return_weight": excess_return_weight,
                        "compute_wfe": compute_wfe, "wfe_is_eval_bars": wfe_is_eval_bars,
                        "garch_stress": style_garch, "garch_context_tfs": context_tfs,
                        "garch_stats": stats, "garch_params": garch_params,
                        "macro_event_timestamps": macro_event_timestamps,
                        "friction_profile": friction_profile,
                        "torch_threads": thread_counts[candidate_index % max_workers] if max_workers > 1 else None,
                        "style": tf, "slot": slot, "context_timeframes": context_tfs,
                        "label": f"[gen {self.generation} | {tf} pop{slot} #{i}]",
                    })
                    candidate_index += 1

        log.info(f"Entraînement de {total_candidates} candidats ({n_per_style} par style x "
                  f"{len(self.timeframe_pool)} styles {self.timeframe_pool}) sur {max_workers} "
                  f"processus en parallèle ({sum(thread_counts)} threads CPU au total, "
                  f"répartition {thread_counts})...")

        if max_workers > 1:
            with ProcessPoolExecutor(max_workers=max_workers) as pool:
                results = list(pool.map(_train_candidate_worker, specs))
        else:
            results = [_train_candidate_worker(s) for s in specs]

        try:
            journal.append([{
                "time": time.strftime("%Y-%m-%d %H:%M:%S"), "generation": r["generation"],
                "style": r["style"], "slot": r["slot"], "score": float(r["score"]),
                "sharpe": float(r["metrics"]["sharpe"]), "max_drawdown": float(r["metrics"]["max_drawdown"]),
                "total_return": float(r["metrics"]["total_return"]),
                "kind": "reward_search" if r.get("env_search") else "control",
                "env_search": r.get("env_search"),
            } for r in results])
        except Exception as exc:  # le journal ne doit jamais interrompre l'entraînement
            log.warning(f"Journal d'expériences : écriture impossible ({exc}).")

        by_slot = {(tf, slot): [] for tf in self.timeframe_pool for slot in range(population_size)}
        for r in results:
            by_slot[(r["style"], r["slot"])].append(r)
            m = r["metrics"]
            slot_label = f" pop{r['slot']}" if population_size > 1 else ""
            log.info(f"  [{r['style']}{slot_label}] score={r['score']:.3f} sharpe={m['sharpe']:.2f} "
                      f"drawdown={m['max_drawdown']:.2%} return={m['total_return']:.2%}")
            if "per_window" in m and len(m["per_window"]) > 1:
                detail = ", ".join(f"return={w['total_return']:.1%}/sharpe={w['sharpe']:.1f}"
                                    for w in m["per_window"])
                log.info(f"      (détail par fenêtre : {detail})")
            if m.get("stress_windows"):
                detail = ", ".join(f"{w['stress']}: drawdown={w['max_drawdown']:.1%}/return={w['total_return']:.1%}"
                                    for w in m["stress_windows"])
                log.info(f"      (scénarios adversariaux : {detail})")
            self._record_trades_from_result(r)

        min_gen = self.cfg["validation"].get("min_generations_before_demo", 0)
        enough_generations = self.generation + 1 >= min_gen
        # Voir _confident_score : évite qu'un score gonflé par un petit
        # échantillon de trades (variance statistique, pas une vraie
        # compétence) ne devienne champion et bloque durablement toute
        # comparaison ultérieure -- sans changer les scores AFFICHÉS
        # (dashboard, logs), seulement la décision de promotion.
        min_trades_conf = self.cfg["continuous"].get("min_trades_for_confident_score", 100)
        # Seuil d'activité PAR STYLE (continuous.min_trades_for_confident_score_by_style) :
        # un style qui trade peu voit son score de sélection réduit proportionnellement.
        _mtc_by_style = self.cfg["continuous"].get("min_trades_for_confident_score_by_style") or {}

        def _mtc(tf_):
            return _mtc_by_style.get(tf_, min_trades_conf)

        # ---- 1) champion technique PAR SLOT, puis mirroring du MEILLEUR
        #         slot vers le champion PUBLIC du style (base de warm start
        #         externe/démo/ensemble -- inchangé pour qui n'utilise pas
        #         la population) ----
        style_bests = {}
        for tf in self.timeframe_pool:
            for slot in range(population_size):
                key = (tf, slot)
                candidates = by_slot[key]
                candidates.sort(key=lambda r: r["score"], reverse=True)
                best = candidates[0]
                best_n_trades = best["metrics"].get("n_trades", 0)
                promoted = (
                    _confident_score(best["score"], best_n_trades, _mtc(tf))
                    > _confident_score(self.slot_score[key], self.slot_n_trades.get(key, 0), _mtc(tf))
                    or not os.path.exists(_slot_model(tf, slot, population_size) + ".zip")
                )
                # VETO DE STABILITÉ MULTI-ACTIFS (LOT 2, phase 4, point 8) :
                # avec population_size=1, CE slot EST le champion public
                # (chemins identiques, voir _slot_dir) -- sans ce garde-fou
                # ICI, un candidat instable écraserait silencieusement le
                # fichier de poids du champion (même si sa promotion au
                # niveau "champion" ci-dessous est elle aussi bloquée),
                # polluant la lignée pour les warm starts futurs.
                if (promoted and other_symbol_dfs
                        and _slot_model(tf, slot, population_size) == _champion_model(tf)):
                    stable, veto_details = stability_veto(
                        tf, best["model_path"],
                        {"feature_columns": best["feature_columns"], "algo": best["hyperparams"].get("algo", "PPO")},
                        style_stats[tf], other_symbol_dfs)
                    if not stable:
                        log.warning(f"  [{tf}] promotion de slot BLOQUÉE par le veto de stabilité multi-actifs "
                                    f"({sum(1 for d in veto_details if not d.get('stable'))}/{len(veto_details)} "
                                    f"symboles instables) -- le fichier de poids du champion n'est PAS écrasé.")
                        promoted = False
                # GARDE-FOU ANTI-RÉGRESSION (21/09, bug réel observé sur H4 --
                # voir aussi le garde-fou équivalent au niveau "champion"
                # plus bas) : avec population_size=1 (défaut), CE slot EST
                # déjà le fichier de poids du champion public (chemins
                # identiques, voir commentaire "mirroring" plus bas) -- sans
                # ce garde-fou ICI, un candidat au score brut meilleur mais
                # NE PASSANT PAS la validation écrase directement le fichier
                # réellement utilisé par la démo, AVANT même que le garde-fou
                # "champion" plus bas ait la moindre chance d'agir. Un
                # candidat non-validant ne peut écraser ce fichier QUE si le
                # champion actuellement déployé n'était lui-même pas encore
                # validé (bootstrap, rien à protéger).
                if (promoted and _slot_model(tf, slot, population_size) == _champion_model(tf)
                        and not passes_validation(best["metrics"], self.cfg, style=tf)):
                    was_validated = self._read_json(_champion_meta(tf)).get("passes_validation", False)
                    if was_validated:
                        log.info(f"  [{tf}] candidat gen {self.generation + 1} meilleur score brut mais NE PASSE "
                                  f"PAS la validation -- le champion démo ACTUELLEMENT VALIDÉ reste déployé, "
                                  f"jamais remplacé par un candidat non validé (\"l'évolution ne doit jamais "
                                  f"faire sortir un style déjà validé de la démo\").")
                        promoted = False
                # PORTE LOCKBOX au niveau slot : même raison que ci-dessus -- avec population_size=1
                # le slot EST le fichier de poids du champion, il ne faut pas l'écraser avant d'avoir
                # vérifié le candidat sur le jeu sous clé (voir _lockbox_check).
                if (promoted and _slot_model(tf, slot, population_size) == _champion_model(tf)
                        and enough_generations and passes_validation(best["metrics"], self.cfg, style=tf)
                        and self._read_json(_champion_meta(tf)).get("passes_validation", False)):
                    _, gate_ok = self._lockbox_check(
                        tf, best["model_path"],
                        {"feature_columns": best["feature_columns"],
                         "context_timeframes": best["context_timeframes"],
                         "algo": best["hyperparams"].get("algo", "PPO")},
                        style_stats[tf], True)
                    if not gate_ok:
                        log.info(f"  [{tf}] candidat gen {self.generation + 1} refusé par la porte lockbox -- "
                                 f"le champion éligible actuel reste déployé.")
                        promoted = False
                if promoted:
                    shutil.copy(best["model_path"] + ".zip", _slot_model(tf, slot, population_size) + ".zip")
                    self.slot_score[key] = best["score"]
                    self.slot_n_trades[key] = best_n_trades
                    with open(_slot_meta(tf, slot, population_size), "w", encoding="utf-8") as f:
                        json.dump({
                            "generation": self.generation, "score": best["score"],
                            "metrics": best["metrics"], "updated_at": time.time(),
                            "env_version": ENV_VERSION,
                            "primary_timeframe": tf, "context_timeframes": best["context_timeframes"],
                            "feature_columns": best["feature_columns"],
                            # `algo` : quel algorithme RL a produit ce modèle
                            # (PPO discret, ou SAC/TD3 à action continue --
                            # voir agent.py) -- nécessaire pour que
                            # demo_trader.py sache comment recharger le
                            # modèle ET interpréter son action en démo.
                            "algo": best["hyperparams"].get("algo", "PPO"),
                        }, f, indent=2)
                    with open(_slot_stats(tf, slot, population_size), "w", encoding="utf-8") as f:
                        json.dump({k: list(v) for k, v in style_stats[tf].items()}, f, indent=2)

                # ---- mise à jour de la recherche adaptative de CE slot ----
                state = self.slot_search_state.get(key) or {}
                sigma = state.get("sigma", base_mutation_scale)
                stagnation = state.get("stagnation", 0)
                if promoted:
                    # succès : le centre de recherche se déplace vers ce qui
                    # a marché, l'amplitude grandit un peu (règle du 1/5 --
                    # on explore plus loin après un succès, pas moins).
                    new_center = best["hyperparams"]
                    new_sigma = min(mutation_scale_max, sigma * 1.2) if adaptive else base_mutation_scale
                    new_stagnation = 0
                else:
                    new_center = state.get("center") or best["hyperparams"]
                    new_stagnation = stagnation + 1
                    if adaptive and patience > 0 and new_stagnation >= patience:
                        # plateau prolongé : coup de pouce jusqu'à l'amplitude
                        # maximale pour tenter de s'échapper de l'optimum local.
                        new_sigma = mutation_scale_max
                        new_stagnation = 0
                        slot_label = f" pop{slot}" if population_size > 1 else ""
                        log.info(f"  [{tf}{slot_label}] plateau depuis {patience}+ cycles -> amplitude de "
                                  f"recherche élargie à {new_sigma:.2f} pour explorer plus loin.")
                    else:
                        # échec : on rétrécit un peu (exploite plus
                        # localement), jamais sous 10% de l'amplitude de base.
                        new_sigma = max(base_mutation_scale * 0.1, sigma * 0.9) if adaptive else base_mutation_scale
                self.slot_search_state[key] = {"center": new_center, "sigma": new_sigma, "stagnation": new_stagnation}
                with open(_slot_search_state(tf, slot, population_size), "w", encoding="utf-8") as f:
                    json.dump(self.slot_search_state[key], f, indent=2)

            # ---- mirroring : le CHAMPION PUBLIC du style = son meilleur slot ----
            # (avec population_size=1, le slot 0 EST déjà le champion public
            # -- mêmes chemins, voir _slot_dir -- donc rien à copier : la
            # promotion de slot ci-dessus a déjà tout écrit au bon endroit.)
            best_slot = max(
                range(population_size),
                key=lambda s: _confident_score(
                    self.slot_score[(tf, s)], self.slot_n_trades.get((tf, s), 0), _mtc(tf)
                ),
            )
            best_slot_meta = self._read_json(_slot_meta(tf, best_slot, population_size))
            # Capturé AVANT toute promotion ci-dessous, pour détecter la
            # TRANSITION vers "éligible démo" (voir l'alerte plus bas) --
            # jamais réévalué après coup, sinon on comparerait le nouvel
            # état à lui-même.
            was_eligible_before = self._read_json(_champion_meta(tf)).get("passes_validation", False)
            champion_promoted = (
                _confident_score(self.slot_score[(tf, best_slot)], self.slot_n_trades.get((tf, best_slot), 0),
                                  _mtc(tf))
                > _confident_score(self.champion_score[tf], self.champion_n_trades.get(tf, 0), _mtc(tf))
                or not self.has_champion(tf)
            )
            # VETO DE STABILITÉ MULTI-ACTIFS (LOT 2, phase 4, point 8) :
            # n'intervient QUE si `champion_promoted` est déjà vrai pour
            # d'AUTRES raisons (jamais de coût -- run_survival_test -- pour
            # un candidat qui de toute façon ne serait pas promu), et QUE si
            # au moins un symbole additionnel est chargé (voir
            # `other_symbol_dfs` en tête de run_one_cycle). Le SCORE de
            # promotion reste calculé uniquement sur la validation OR
            # ci-dessus -- ce veto peut seulement BLOQUER, jamais ajouter de
            # points. Poids FIGÉS du candidat (voir _slot_model), jamais
            # réentraînés pour ce test.
            if champion_promoted and other_symbol_dfs:
                candidate_model_path = _slot_model(tf, best_slot, population_size)
                candidate_stats = self._read_json(_slot_stats(tf, best_slot, population_size))
                stable, veto_details = stability_veto(
                    tf, candidate_model_path, best_slot_meta,
                    {k: tuple(v) for k, v in candidate_stats.items()}, other_symbol_dfs)
                if not stable:
                    log.warning(f"  [{tf}] promotion BLOQUÉE par le veto de stabilité multi-actifs "
                                f"({sum(1 for d in veto_details if not d.get('stable'))}/{len(veto_details)} "
                                f"symboles instables) -- score walk-forward pourtant meilleur, mais la courbe "
                                f"de capital s'effondre sur au moins un autre symbole.")
                    champion_promoted = False
            if champion_promoted:
                # Score/n_trades de recherche TOUJOURS mis à jour (même
                # logique qu'avant) -- sert de barre à battre pour les
                # PROCHAINS candidats et au suivi de plateau/mutation
                # adaptative, indépendamment de ce qui est réellement
                # DÉPLOYÉ en démo ci-dessous (voir garde-fou anti-régression).
                self.champion_score[tf] = self.slot_score[(tf, best_slot)]
                self.champion_n_trades[tf] = self.slot_n_trades.get((tf, best_slot), 0)
                # `passes_validation` : CE style, individuellement, passe-t-il
                # les seuils de qualité ? Contrairement à l'ancien mécanisme
                # (un seul "champion démo" gagnant tous styles confondus),
                # PLUSIEURS styles peuvent être éligibles SIMULTANÉMENT -- ce
                # qui permet à demo_trader.py de les combiner en un ENSEMBLE
                # pondéré (voir `live.ensemble`) plutôt qu'un unique gagnant.
                style_passes = passes_validation(best_slot_meta["metrics"], self.cfg, style=tf) and enough_generations
                # PORTE LOCKBOX (04/10) : un candidat qui passe la validation interne n'est
                # éligible démo que s'il tient aussi sur le jeu sous clé (et bat le champion
                # éligible actuel s'il a des métriques lockbox). Ne peut que refuser.
                lockbox_metrics = None
                if style_passes:
                    lockbox_metrics, gate_ok = self._lockbox_check(
                        tf, _slot_model(tf, best_slot, population_size), best_slot_meta,
                        self._read_json(_slot_stats(tf, best_slot, population_size)), was_eligible_before)
                    if not gate_ok:
                        style_passes = False

                # GARDE-FOU ANTI-RÉGRESSION (21/09, bug réel observé sur H4 :
                # un candidat gen:204 au score walk-forward meilleur, mais
                # UNE SEULE fenêtre sur quatre à 1 trade -- sous le plancher
                # anti-dégénérescence -- a quand même ÉCRASÉ les poids du
                # champion gen:134 précédent, VALIDÉ et servant la démo
                # depuis des heures. Résultat : la démo perd un agent qui
                # fonctionnait, remplacé par un qui ne passe pas les seuils.
                # "L'évolution doit pouvoir ALLER en démo, jamais en faire
                # SORTIR un style déjà validé" (demande explicite) : un
                # candidat qui ne valide pas ne peut déployer ses poids QUE
                # si rien n'était encore validé pour ce style -- jamais
                # remplacer un champion démo actuellement validé.
                deploy = style_passes or not was_eligible_before
                if not deploy:
                    log.info(f"  [{tf}] candidat gen {self.generation + 1} meilleur score walk-forward "
                              f"({best_slot_meta['score']:.3f}) mais NE PASSE PAS la validation -- le "
                              f"champion démo ACTUELLEMENT VALIDÉ (score={self.champion_score.get(tf, 0):.3f}) "
                              f"reste déployé tel quel, jamais remplacé par un candidat non validé. La "
                              f"recherche continue normalement en arrière-plan (score de référence mis à "
                              f"jour pour les prochains candidats).")
                else:
                    if _slot_model(tf, best_slot, population_size) != _champion_model(tf):
                        shutil.copy(_slot_model(tf, best_slot, population_size) + ".zip", _champion_model(tf) + ".zip")
                        shutil.copy(_slot_stats(tf, best_slot, population_size), _champion_stats(tf))
                    champion_meta = {**best_slot_meta, "passes_validation": style_passes, "updated_at": time.time()}
                    if lockbox_metrics is not None:
                        champion_meta["lockbox"] = lockbox_metrics
                    with open(_champion_meta(tf), "w", encoding="utf-8") as f:
                        json.dump(champion_meta, f, indent=2)
                    _archive_snapshot(_champion_model(tf), _champion_stats(tf), _champion_meta(tf),
                                      os.path.join(_champion_dir(tf), "history"), self.generation + 1)
                    pop_note = f" (meilleur parmi {population_size} lignées)" if population_size > 1 else ""
                    log.info(f"  -> nouveau champion technique '{tf}'{pop_note} (score={champion_meta['score']:.3f}, "
                              f"éligible démo={style_passes}).")
                    # ALERTE : le style vient de devenir éligible à la démo
                    # (voir `live.ensemble`) -- transition uniquement (jamais
                    # renvoyée tant qu'il reste éligible d'un cycle à
                    # l'autre), best effort.
                    if style_passes and not was_eligible_before:
                        try:
                            from src.notifier import send_alert
                            send_alert(self.cfg, subject=f"Test_IA - style '{tf}' promu en demo",
                                       message=(f"Le style '{tf}' vient de passer les seuils de qualité "
                                                f"(score={champion_meta['score']:.3f}, sharpe="
                                                f"{champion_meta['metrics']['sharpe']:.2f}, "
                                                f"drawdown={champion_meta['metrics']['max_drawdown']:.1%}) et "
                                                f"est maintenant éligible à la démo (génération {self.generation + 1})."))
                        except Exception:
                            pass

            style_bests[tf] = {**self._read_json(_champion_meta(tf)), "style": tf,
                                "model_path": _champion_model(tf)}

        # ---- 2) meilleur candidat TOUS STYLES CONFONDUS -> repli "gagnant unique" ----
        # (utilisé par demo_trader.py quand `live.ensemble: false`, ou tant
        # qu'aucun style ne passe encore individuellement la validation --
        # voir _scan_eligible_styles dans demo_trader.py)
        # STYLES SANS AUCUN CHAMPION ENCORE (LOT 2, phase 4 : possible
        # désormais dès le premier cycle si le veto de stabilité multi-actifs
        # bloque la toute première promotion d'un style -- auparavant
        # `not self.has_champion(tf)` garantissait TOUJOURS une promotion au
        # premier cycle) : `style_bests[tf]` n'a alors pas de clé "score"
        # (_champion_meta(tf) inexistant, _read_json renvoie {}) -- exclu ici
        # plutôt qu'un KeyError, ce cycle ne promeut simplement aucun champion
        # démo tant qu'AUCUN style n'a de champion utilisable.
        scored_styles = {tf: b for tf, b in style_bests.items() if "score" in b}
        if not scored_styles:
            log.info("  Aucun style n'a encore de champion utilisable ce cycle (score manquant) -- "
                      "pas de promotion de champion démo.")
            overall_best = None
        else:
            overall_best = max(scored_styles.values(), key=lambda r: r["score"])
        passes = passes_validation(overall_best["metrics"], self.cfg) if overall_best else False
        demo_promoted = (
            overall_best is not None and passes and enough_generations
            and (_confident_score(overall_best["score"], overall_best["metrics"].get("n_trades", 0),
                                  _mtc(overall_best["style"]))
                 > _confident_score(self.demo_champion_score, self.demo_champion_n_trades,
                                    _mtc(overall_best["style"]))
                 or not self.has_demo_champion())
        )
        if demo_promoted:
            shutil.copy(overall_best["model_path"] + ".zip", DEMO_MODEL + ".zip")
            self.demo_champion_score = overall_best["score"]
            self.demo_champion_n_trades = overall_best["metrics"].get("n_trades", 0)
            with open(DEMO_META, "w", encoding="utf-8") as f:
                json.dump({
                    "generation": self.generation, "score": overall_best["score"],
                    "metrics": overall_best["metrics"], "updated_at": time.time(),
                    "env_version": ENV_VERSION,
                    "validation_thresholds": self.cfg["validation"],
                    "primary_timeframe": overall_best["style"],
                    "context_timeframes": overall_best["context_timeframes"],
                    "feature_columns": overall_best["feature_columns"],
                    "algo": overall_best.get("algo", "PPO"),
                }, f, indent=2)
            with open(DEMO_STATS, "w", encoding="utf-8") as f:
                json.dump({k: list(v) for k, v in style_stats[overall_best["style"]].items()}, f, indent=2)
            _archive_snapshot(DEMO_MODEL, DEMO_STATS, DEMO_META,
                              os.path.join(DEMO_DIR, "history"), self.generation + 1)
            log.info(f"  -> NOUVEAU CHAMPION DÉMO promu : style '{overall_best['style']}' "
                      f"(score={overall_best['score']:.3f}, génération {self.generation + 1}/{min_gen} minimum) : "
                      f"sera utilisé par le trading en démo.")
            try:
                from src.notifier import send_alert
                send_alert(self.cfg, subject=f"Test_IA - nouveau champion demo ('{overall_best['style']}')",
                           message=(f"Style '{overall_best['style']}' promu champion démo "
                                    f"(score={overall_best['score']:.3f}, génération {self.generation + 1})."))
            except Exception:
                pass
        elif overall_best is None:
            pass  # déjà journalisé ci-dessus (aucun style n'a de champion utilisable)
        elif not passes:
            v = self.cfg["validation"]
            log.info(f"  -> le meilleur candidat tous styles confondus ('{overall_best['style']}') NE PASSE PAS "
                      f"les seuils de validation (sharpe={overall_best['metrics']['sharpe']:.2f} < "
                      f"{v.get('min_sharpe_to_go_live')} ou drawdown={overall_best['metrics']['max_drawdown']:.2%} "
                      f"> {v.get('max_drawdown_allowed'):.0%}) -> PAS envoyé en démo.")
        elif not enough_generations:
            log.info(f"  -> le meilleur candidat ('{overall_best['style']}') passe les seuils de qualité mais le "
                      f"nombre minimal de générations n'est pas encore atteint ({self.generation + 1}/{min_gen}).")
        else:
            log.info(f"  -> le meilleur candidat ('{overall_best['style']}') passe la validation mais ne bat pas "
                      f"le champion démo actuel (score={self.demo_champion_score:.3f}) : conservé.")

        # ---- suivi de plateau / risque de sur-apprentissage ----
        current_best_overall = max(self.champion_score.values())
        if current_best_overall > self.best_ever_score:
            self.best_ever_score = current_best_overall
        # La décision "a-t-on VRAIMENT progressé ?" (reset du compteur de
        # plateau) se fait sur le score ajusté par la confiance, PAS sur le
        # record brut ci-dessus (voir _confident_score / le commentaire sur
        # best_ever_confident_score dans __init__) -- un style qui progresse
        # sincèrement doit pouvoir remettre ce compteur à zéro même s'il ne
        # bat pas le record brut d'un autre style gonflé par la chance.
        current_best_confident = max(
            _confident_score(self.champion_score[tf], self.champion_n_trades.get(tf, 0), _mtc(tf))
            for tf in self.timeframe_pool
        )
        if current_best_confident > self.best_ever_confident_score:
            self.best_ever_confident_score = current_best_confident
            self.cycles_since_improvement = 0
        else:
            self.cycles_since_improvement += 1
        patience = self.cfg["continuous"].get("overfitting_patience_cycles", 15)
        if self.cycles_since_improvement >= patience:
            log.warning(f"  [!] Aucune amélioration depuis {self.cycles_since_improvement} cycles (meilleur "
                        f"score jamais atteint : {self.best_ever_score:.3f}). L'entraînement continue "
                        f"indéfiniment (c'est voulu -- un candidat n'est jamais promu s'il ne fait pas mieux), "
                        f"mais ce plateau peut signaler un sur-apprentissage des données disponibles : "
                        f"envisagez d'augmenter mutation_scale, ou de réduire vos attentes de progression "
                        f"supplémentaire sur cet historique.")
        else:
            log.info(f"  Progression : meilleur score jamais atteint = {self.best_ever_score:.3f} "
                      f"({self.cycles_since_improvement} cycle(s) sans amélioration, patience={patience}).")

        with open(PROGRESS_FILE, "w", encoding="utf-8") as f:
            json.dump({"generation": self.generation + 1, "best_ever_score": self.best_ever_score,
                       "best_ever_confident_score": self.best_ever_confident_score,
                       "cycles_since_improvement": self.cycles_since_improvement}, f, indent=2)

        # TABLEAU DE BORD (voir src/dashboard.py) : snapshot de l'état
        # d'entraînement, régénère reports/dashboard.html. Ne doit jamais
        # interrompre le cycle si ça échoue (write_training_status avale
        # ses propres exceptions).
        try:
            from src.dashboard import write_training_status
            write_training_status({
                "generation": self.generation + 1,
                "best_ever_score": self.best_ever_score,
                "cycles_since_improvement": self.cycles_since_improvement,
                "plateau": self.cycles_since_improvement >= patience,
                "styles": {
                    tf: {"score": self.champion_score[tf],
                         "generation": self._read_json(_champion_meta(tf)).get("generation"),
                         "passes_validation": self._read_json(_champion_meta(tf)).get("passes_validation", False)}
                    for tf in self.timeframe_pool
                },
            }, cfg=self.cfg)
        except Exception:
            pass

        # ALERTE À CHAQUE CYCLE (voir src/notifier.py, config `notifications.
        # notify_every_cycle`) : purement un résumé envoyé APRÈS que tout le
        # reste (score, promotion, persistance) a déjà été décidé
        # ci-dessus -- ne modifie RIEN à la logique d'entraînement, best
        # effort (jamais d'exception qui remonte, jamais de blocage du cycle).
        try:
            notif_cfg = self.cfg.get("notifications", {})
            if notif_cfg.get("notify_every_cycle"):
                every_n = max(1, int(notif_cfg.get("notify_cycle_every_n", 1)))
                if (self.generation + 1) % every_n == 0:
                    from src.notifier import send_alert
                    # Marqueur de FIABILITÉ (✓/△) collé à chaque score : répond
                    # au cas réel de cette nuit (D1 passé de 4.69 à 4.10 --
                    # une VRAIE amélioration, son champion venant de franchir
                    # min_trades_for_confident_score, mais illisible comme tel
                    # dans une notif -- ça ressemblait à une régression). Sans
                    # ce marqueur, seule la conversation permettait de savoir
                    # si un score brut méritait confiance ; maintenant c'est
                    # visible directement sur le téléphone.
                    styles_summary = " | ".join(
                        f"{tf}={self.champion_score[tf]:.2f}"
                        f"{_format_score_delta(self.champion_score[tf], self._last_notified_scores.get(tf))}"
                        f"{_confidence_marker(self.champion_n_trades.get(tf, 0), min_trades_conf)}"
                        for tf in self.timeframe_pool)
                    for tf in self.timeframe_pool:
                        self._last_notified_scores[tf] = self.champion_score[tf]
                    plateau_note = " [PLATEAU]" if self.cycles_since_improvement >= patience else ""
                    # "record brut" (best_ever_score) ne bouge QUE si un style
                    # bat ce chiffre EXACT en score brut -- un style peut très
                    # bien progresser réellement (voir _confident_score) sans
                    # jamais s'en approcher si le record actuel vient d'un
                    # score gonflé par un petit échantillon. Le VRAI signal de
                    # progrès est cycles_since_improvement (mis en avant
                    # ci-dessous) : à 0, quelque chose a réellement progressé
                    # CE cycle, même si le record brut affiché n'a pas bougé.
                    progress_note = " [PROGRÈS]" if self.cycles_since_improvement == 0 else ""
                    # Le message mène avec le progrès PAR STYLE (styles_summary
                    # contient déjà le delta de chaque style via
                    # _format_score_delta) -- le compteur global
                    # cycles_since_improvement est relégué en fin de message
                    # comme repère secondaire, car il ne bouge que si un
                    # style bat le record ABSOLU exact ; il peut rester figé
                    # (ex: "1 cycle sans amélioration") alors que d'autres
                    # styles progressent réellement ce même cycle.
                    send_alert(
                        self.cfg,
                        subject=f"Test_IA - cycle {self.generation + 1}",
                        message=(f"Cycle {self.generation + 1} terminé{progress_note} -- "
                                 f"Styles : {styles_summary}{plateau_note} | "
                                 f"(repère global : record absolu={self.best_ever_score:.3f}, "
                                 f"{self.cycles_since_improvement} cycle(s) sans nouveau record -- "
                                 f"ne bouge que si un style bat ce chiffre exact, peut rester figé "
                                 f"même si d'autres styles progressent) | "
                                 f"✓=fiable (≥{min_trades_conf} trades) △=encore peu de trades, "
                                 f"score à prendre avec précaution"),
                    )
        except Exception:
            pass

        # nettoyage des modèles temporaires de candidats (déjà copiés si retenus)
        for r in results:
            try:
                os.remove(r["model_path"] + ".zip")
            except OSError:
                pass

        self.generation += 1
        return demo_promoted

    def _record_trades_from_result(self, result: dict):
        # Le contexte enregistré est le vecteur de features de marché au
        # moment de la clôture (voir TradingEnv.step), PAS [entry, exit,
        # position] comme auparavant : c'est ce qui rend la recherche par
        # similarité (MemoryQuery) réellement comparable à la situation de
        # marché courante lors d'une future décision, plutôt qu'à trois
        # nombres qui ne décrivent rien du marché lui-même.
        # 30/09 : un candidat en surtrading (score -15, DD 99.7%) a bloqué le
        # cycle ~28 min en enregistrant des dizaines de milliers de trades
        # sans valeur -> on ignore les candidats dégénérés et on plafonne.
        if result["max_drawdown"] > 0.5:
            return
        trades = result["trades"]
        max_trades = 2000
        if len(trades) > max_trades:
            step = len(trades) / max_trades
            trades = [trades[int(i * step)] for i in range(max_trades)]
        for t in trades:
            self.memory.store(
                context=np.array(t["context"], dtype=np.float32),
                action=t["position"], pnl_pct=t["pnl_pct"],
                drawdown=result["max_drawdown"], generation=result["generation"],
                source="backtest",
            )

    def close(self):
        self.memory.close()
