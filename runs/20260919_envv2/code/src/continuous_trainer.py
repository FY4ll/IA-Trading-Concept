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
import glob
import logging
import numpy as np
import pandas as pd
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
from src.note_argent import run_daily_returns, note_run, note_portefeuille, note_compte_fidele, account_trades

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


def _account_entry(env, df, name: str) -> dict:
    """Trades d'un marché + bornes de sa période, pour le compte fidèle de l'examen."""
    t = pd.to_datetime(df["time"])
    return {"trades": account_trades(env, name), "debut": t.iloc[0], "fin": t.iloc[-1]}


def _multi_market_score(agent, spec: dict, gold_score: float, metrics: dict, fitness_metric: str,
                        trades_out: list | None = None, rets_out: dict | None = None,
                        account_out: dict | None = None) -> float:
    """SÉLECTION MULTI-MARCHÉS (07/10/2026). Constat : le champion AUREXIS (copie d'AUREX) perdait sur TOUS les
    autres marchés et achetait pendant les baisses, mais la sélection ne regardait que l'or -- elle récompensait
    donc exactement ce défaut. Ici le candidat joue aussi chaque autre marché (et chaque marché inversé) sur la
    période de validation ; note par marché = même formule que l'or sans l'excès de rendement (fitness -
    2 x baisse max), bornée à ±clip pour qu'un marché ne pèse pas tout. Score final = poids_or x note de l'or +
    (1 - poids_or) x moyenne des autres. Les métriques de l'OR restent `metrics` (seuils de validation, démo)."""
    from src.backtester import run_episode as _run, compute_metrics as _metrics
    clip = float(spec.get("extra_val_score_clip", 5.0))
    w = float(spec.get("extra_val_gold_weight", 0.5))
    tf = base_timeframe(spec.get("style", "H1"))
    per_market = []
    for name, df in spec["extra_val"]:
        try:
            env = _run(agent, TradingEnv(df, **spec["env_kwargs"]))
            m = _metrics(env, timeframe=tf)
            s = float(np.clip(m.get(fitness_metric, m["sharpe"]) - 2.0 * m["max_drawdown"], -clip, clip))
            per_market.append({"market": name, "score": s, "sharpe": float(m["sharpe"]),
                               "total_return": float(m["total_return"]),
                               "max_drawdown": float(m["max_drawdown"]), "n_trades": int(m.get("n_trades", 0) or 0)})
            if rets_out is not None:            # rendements journaliers -> compte « portefeuille » (note argent FTMO)
                rets_out[name] = run_daily_returns(env, df)
            if account_out is not None:         # trades horodatés -> compte fidèle (note_compte_fidele)
                account_out[name] = _account_entry(env, df, name)
            if trades_out is not None:          # souvenirs de ce marché (mémoire privée, voir _record_trades_from_result)
                trades_out.extend({"entry": t["entry"], "exit": t["exit"], "position": t["position"],
                                   "pnl_pct": t["pnl_pct"], "context": t["context"], "market": name}
                                  for t in env.trade_log)
        except Exception as exc:  # un marché en échec ne doit jamais faire tomber le candidat
            per_market.append({"market": name, "score": -clip, "error": f"{type(exc).__name__}: {exc}"})
    if not per_market:
        return gold_score
    others = float(np.mean([p["score"] for p in per_market]))
    metrics["gold_score"] = float(gold_score)
    metrics["markets_score"] = others
    metrics["markets"] = per_market
    return w * float(gold_score) + (1.0 - w) * others


# ------------------------------------------------------------------------ #
# VEINES (08/10/2026, continuous.veins) -- principe du blob (Physarum) proposé par l'utilisateur : plusieurs
# chemins d'apprentissage vivent en même temps. Le champion est la veine PRINCIPALE ; un candidat qui montre un
# NOUVEAU TALENT face au champion du même cycle (il vend mieux sur les marchés inversés, ou il le bat sur la
# majorité des marchés) ouvre une veine SECONDAIRE au lieu d'être effacé. À chaque cycle, un candidat repart d'une
# veine secondaire tirée au prorata de son FLUX : une veine qui progresse grossit (flux x1.5, son nouveau cerveau
# remplace l'ancien : "on garde, on relance, on garde"), une veine qui stagne s'amincit (flux x0.7) puis
# disparaît. La promotion du champion ne change pas : une veine devient le chemin principal en battant le
# champion au score global (mêmes garde-fous), elle fusionne alors avec lui.
# Optimisé pour la machine : AUCUN processus en plus (le candidat de veine remplace un candidat muté du
# champion -- même mémoire, même durée de cycle), au plus `max_veins` veines (~9 Mo chacune sur le disque).
# ------------------------------------------------------------------------ #
def _veins_dir(tf: str) -> str:
    return os.path.join(_champion_dir(tf), "veines")


def _veins_load(tf: str) -> list:
    try:
        with open(os.path.join(_veins_dir(tf), "veines.json"), encoding="utf-8") as f:
            veins = json.load(f)
        return [v for v in veins if os.path.exists(v["path"] + ".zip")]
    except (OSError, ValueError, KeyError, TypeError):
        return []


def _veins_save(tf: str, veins: list) -> None:
    os.makedirs(_veins_dir(tf), exist_ok=True)
    tmp = os.path.join(_veins_dir(tf), "veines.json.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(veins, f, indent=1, default=str)
    os.replace(tmp, os.path.join(_veins_dir(tf), "veines.json"))


def _new_talent(m: dict, inc_m: dict | None, vcfg: dict) -> tuple[bool, str]:
    """(nouveau talent ?, raison) : candidat comparé au champion réévalué du MÊME cycle (mêmes données, mêmes
    marchés). Il doit trader assez et ne pas s'effondrer sur l'or, puis faire mieux que le champion soit sur les
    marchés inversés (vendre), soit sur au moins 2/3 des marchés."""
    if not m.get("markets") or not inc_m or not inc_m.get("markets"):
        return False, ""
    if m.get("max_drawdown", 1.0) > float(vcfg.get("max_drawdown", 0.30)):
        return False, ""
    if int(m.get("n_trades", 0) or 0) < int(vcfg.get("min_trades", 100)):
        return False, ""
    inc = {p["market"]: p["score"] for p in inc_m["markets"]}
    cand = {p["market"]: p["score"] for p in m["markets"]}
    common = [k for k in cand if k in inc]
    if not common:
        return False, ""
    mirrors = [k for k in common if k.endswith("miroir")]
    if mirrors:
        gain = float(np.mean([cand[k] for k in mirrors]) - np.mean([inc[k] for k in mirrors]))
        if gain >= float(vcfg.get("min_mirror_gain", 0.25)):
            return True, f"vend mieux que le champion (marchés inversés {gain:+.2f})"
    wins = sum(1 for k in common if cand[k] > inc[k] + 0.05)
    if wins * 3 >= 2 * len(common):
        return True, f"bat le champion sur {wins}/{len(common)} marchés"
    return False, ""


def _pick_vein(veins: list, generation: int):
    """Veine secondaire à nourrir ce cycle : tirage au prorata du flux (reproductible par génération)."""
    if not veins:
        return None
    w = np.array([max(1e-6, float(v.get("flux", 1.0))) for v in veins])
    return veins[int(np.random.default_rng(generation).choice(len(veins), p=w / w.sum()))]


def _remove_vein_file(v: dict) -> None:
    try:
        os.remove(v["path"] + ".zip")
    except OSError:
        pass


def _gap(v: dict) -> float:
    """Écart au champion mesuré DANS LE MÊME CYCLE (anciennes veines sans écart : très défavorable)."""
    return float(v.get("gap", -9.0))


def _archive_vein(tf: str, v: dict, keep: int) -> None:
    """Garde une copie des `keep` meilleures veines disparues (meilleur écart au champion) pour pouvoir les relancer."""
    adir = os.path.join(_veins_dir(tf), "archives")
    os.makedirs(adir, exist_ok=True)
    try:
        shutil.move(v["path"] + ".zip", os.path.join(adir, v["id"] + ".zip"))
    except OSError:
        return
    path = os.path.join(adir, "archives.json")
    try:
        with open(path, encoding="utf-8") as f:
            arch = json.load(f)
    except (OSError, ValueError):
        arch = []
    arch.append({**v, "path": os.path.join(adir, v["id"])})
    arch.sort(key=lambda x: float(x.get("best_gap", _gap(x))), reverse=True)
    for old in arch[keep:]:
        try:
            os.remove(old["path"] + ".zip")
        except OSError:
            pass
    with open(path, "w", encoding="utf-8") as f:
        json.dump(arch[:keep], f, indent=1, default=str)


def _veins_update(tf: str, veins: list, results: list, inc_metrics: dict | None, generation: int,
                  vcfg: dict, inc_score: float | None = None) -> tuple[list, list]:
    """Fait vivre les veines après un cycle. Retourne (veines, lignes de journal).

    08/10/2026 (nuit du 07 au 08 : la meilleure veine, à 0,004 du champion, a été tuée) : le champion lui-même,
    poids figés, varie de 0,11 à 0,35 d'un cycle à l'autre (mémoire qui se remplit, coûts recalibrés). Une veine
    est donc jugée sur son ÉCART AU CHAMPION DU MÊME CYCLE (`gap` = score - score du champion réévalué), qui
    retire ce bruit commun ; une veine proche du champion (écart >= -protect_gap) n'est jamais supprimée (elle
    peut stagner 2 x plus longtemps et garde un flux minimal) ; les meilleures veines disparues sont archivées."""
    max_veins = int(vcfg.get("max_veins", 3))
    grow, shrink = float(vcfg.get("grow", 1.5)), float(vcfg.get("shrink", 0.7))
    flux_cap, flux_min = float(vcfg.get("flux_max", 4.0)), float(vcfg.get("flux_min", 0.2))
    max_stall, min_gain = int(vcfg.get("max_stall", 4)), float(vcfg.get("min_gain", 0.02))
    protect_gap = float(vcfg.get("protect_gap", 0.10))
    keep_archives = int(vcfg.get("archives", 3))
    ref = float(inc_score) if inc_score is not None else 0.0
    os.makedirs(_veins_dir(tf), exist_ok=True)
    veins = [dict(v) for v in veins]
    lines = []
    for r in results:
        if r.get("style") != tf or r.get("eval_only"):
            continue
        gap = float(r["score"]) - ref
        v = next((x for x in veins if x["id"] == r.get("vein_id")), None)
        if r.get("promoted"):
            if v is not None:                      # la veine a battu le champion : elle devient le chemin principal
                veins.remove(v)
                _remove_vein_file(v)
                lines.append(f"veine {v['id']} a battu le champion -> devient le chemin principal")
            continue
        if v is not None:
            v["tries"] = int(v.get("tries", 0)) + 1
            v["last_gen"] = generation
            if gap > _gap(v) + min_gain:
                shutil.copy(r["model_path"] + ".zip", v["path"] + ".zip")
                lines.append(f"veine {v['id']} PROGRESSE : écart au champion {_gap(v):+.3f} -> {gap:+.3f} "
                             f"(flux {float(v['flux']):.2f} -> {min(flux_cap, float(v['flux']) * grow):.2f})")
                v.update(score=float(r["score"]), gap=gap, best_gap=max(float(v.get("best_gap", gap)), gap),
                         hyperparams=r.get("hyperparams"), stall=0, flux=min(flux_cap, float(v["flux"]) * grow))
                v.setdefault("history", []).append(round(gap, 3))
            else:
                v["stall"] = int(v.get("stall", 0)) + 1
                v["flux"] = float(v["flux"]) * shrink
                if _gap(v) >= -protect_gap:
                    v["flux"] = max(v["flux"], 0.3)
                lines.append(f"veine {v['id']} stagne (écart {gap:+.3f} <= {_gap(v):+.3f}, "
                             f"{v['stall']} essai(s), flux {v['flux']:.2f})")
            continue
        ok, why = _new_talent(r.get("metrics") or {}, inc_metrics, vcfg)
        if not ok:
            continue
        new = {"id": f"V{generation}_{os.path.basename(r['model_path'])}", "score": float(r["score"]),
               "gap": gap, "best_gap": gap, "flux": 1.0, "stall": 0, "tries": 0, "born": generation,
               "last_gen": generation, "reason": why, "hyperparams": r.get("hyperparams"),
               "history": [round(gap, 3)]}
        new["path"] = os.path.join(_veins_dir(tf), new["id"])
        if len(veins) >= max_veins:
            weakest = min(veins, key=_gap)
            if gap <= _gap(weakest):
                continue
            veins.remove(weakest)
            _archive_vein(tf, weakest, keep_archives)
            lines.append(f"veine {weakest['id']} remplacée (la plus loin du champion, archivée)")
        shutil.copy(r["model_path"] + ".zip", new["path"] + ".zip")
        veins.append(new)
        lines.append(f"NOUVELLE veine {new['id']} : {why} (écart au champion {gap:+.3f})")
    for v in list(veins):
        protected = _gap(v) >= -protect_gap
        limit = max_stall * (2 if protected else 1)
        if int(v.get("stall", 0)) >= limit or (not protected and float(v.get("flux", 1.0)) < flux_min):
            veins.remove(v)
            _archive_vein(tf, v, keep_archives)
            lines.append(f"veine {v['id']} disparaît (stagne depuis {v.get('stall', 0)} essais, archivée)")
    _veins_save(tf, veins)
    return veins, lines


def _activity_rule(cfg: dict, style: str) -> dict | None:
    """Activité minimale exigée pour être champion (continuous.min_activity_by_style), None si aucune."""
    rule = ((cfg.get("continuous") or {}).get("min_activity_by_style") or {}).get(style)
    if not rule:
        return None
    return {"min_trades": int(rule.get("min_trades", 0)), "min_market_trades": int(rule.get("min_market_trades", 0)),
            "min_avg_market_trades": float(rule.get("min_avg_market_trades", 0) or 0)}


def _keep_excluded(tf: str, generation: int, r: dict, keep: int = 10) -> None:
    """Copie le cerveau d'un candidat écarté (trop peu actif) qui avait une meilleure note que le champion, avec ses
    chiffres, dans models/ecartes_<style>/ (les `keep` plus récents). Best effort."""
    try:
        d = os.path.join(MODELS_ROOT, f"ecartes_{tf}")
        os.makedirs(d, exist_ok=True)
        name = f"gen{generation}_{os.path.basename(r['model_path'])}"
        shutil.copy(r["model_path"] + ".zip", os.path.join(d, name + ".zip"))
        m = r.get("metrics") or {}
        info = {"generation": generation, "score": float(r["score"]), "n_trades_or": int(m.get("n_trades", 0) or 0),
                "n_trades_total": _trade_count(m), "portefeuille": m.get("portefeuille"),
                "hyperparams": r.get("hyperparams"), "feature_columns": r.get("feature_columns")}
        with open(os.path.join(d, name + ".json"), "w", encoding="utf-8") as f:
            json.dump(info, f, indent=1, default=str)
        for old in sorted(glob.glob(os.path.join(d, "gen*.zip")), key=os.path.getmtime)[:-keep]:
            for p in (old, old[:-4] + ".json"):
                try:
                    os.remove(p)
                except OSError:
                    pass
        log.info(f"  [{tf}] candidat écarté mais meilleur que le champion : mis à l'abri ({name})")
    except Exception as e:
        log.warning(f"  [{tf}] mise à l'abri du candidat écarté impossible ({type(e).__name__}: {e})")


def _mean_period_note(m: dict) -> float | None:
    """Note moyenne des périodes de l'examen tournant (None si une seule période ou pas de note « argent »)."""
    p = (m.get("portefeuille") or {}).get("periodes") or []
    return float(np.mean([x["note"] for x in p])) if len(p) > 1 else None


# PÉRIODE D'ESSAI AVANT PROMOTION (10/10/2026, accord de l'utilisateur) : la génération 424 a remplacé la 408 (positive
# 6 réévaluations de suite) sur UN seul bon tirage de deux périodes, puis a perdu sur les tirages suivants. Le gagnant
# d'un cycle devient « prétendant » : il repasse, poids figés, l'examen des cycles suivants à côté du champion, et n'est
# promu que s'il fait mieux en CUMULÉ (moyenne des notes de toutes les périodes ET moyenne des moins bonnes périodes).
def _validation_veto(cfg: dict, style: str) -> bool:
    """VETO DE L'ANCIENNE VALIDATION (seuils sur l'or seul, époque AUREX) : un champion « validé » ne peut être remplacé
    que par un candidat validé lui aussi. 12/10/2026 : désactivé pour AUREXIS (continuous.validation_veto_by_style)
    -- depuis que le champion 500 est « validé » (03h08), 12 candidats ont été bloqués sans jamais pouvoir devenir
    prétendants, dont un à +2,4 % / +2,5 %/mois sur le compte fidèle tous marchés. Pour AUREXIS, le juge est l'examen
    sur le compte fidèle + la période d'essai ; le passage en démo a sa propre règle (scripts/regle_demo_aurexis.py)."""
    v = ((cfg.get("continuous") or {}).get("validation_veto_by_style") or {}).get(style)
    return True if v is None else bool(v)


def _trial_need(cfg: dict, style: str) -> int:
    """Nombre d'examens de la période d'essai (continuous.promotion_trial_by_style ; 0/1 = promotion immédiate)."""
    return int(((cfg.get("continuous") or {}).get("promotion_trial_by_style") or {}).get(style, 0) or 0)


def _trial_dir(tf: str) -> str:
    return os.path.join(MODELS_ROOT, f"pretendant_{tf}")


def _trial_load(tf: str) -> dict | None:
    p = os.path.join(_trial_dir(tf), "meta.json")
    if not (os.path.exists(p) and os.path.exists(os.path.join(_trial_dir(tf), "agent.zip"))):
        return None
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def _trial_save(tf: str, trial: dict, model_path: str | None = None) -> None:
    d = _trial_dir(tf)
    os.makedirs(d, exist_ok=True)
    trial["env_version"] = ENV_VERSION     # sans elle, le cerveau est refusé au rechargement (incident du cycle 435)
    if model_path:
        shutil.copy(model_path + ".zip", os.path.join(d, "agent.zip"))
    with open(os.path.join(d, "meta.json"), "w", encoding="utf-8") as f:
        json.dump(trial, f, indent=1, default=float)


def _trial_drop(tf: str) -> None:
    shutil.rmtree(_trial_dir(tf), ignore_errors=True)


def _period_notes(m: dict, score: float) -> list:
    """Notes de chaque période d'un examen (la note du cycle si une seule période)."""
    p = (m.get("portefeuille") or {}).get("periodes") or []
    return [float(x["note"]) for x in p] if p else [float(score)]


def _trial_verdict(exams: list, need: int):
    """None = essai en cours ; True = le prétendant fait mieux que le champion en cumulé ; False = rejeté.
    Deux conditions, comme la promotion immédiate : moyenne des moins bonnes périodes (la note de chaque cycle) ET
    moyenne de toutes les périodes."""
    if len(exams) < need:
        return None
    return _trial_leading(exams)


def _trial_leading(exams: list) -> bool:
    """Le prétendant mène-t-il son essai sur les examens déjà passés (mêmes deux conditions que le verdict) ?"""
    if not exams:
        return False
    worst_c = np.mean([min(e["pretendant"]) for e in exams])
    worst_k = np.mean([min(e["champion"]) for e in exams])
    mean_c = np.mean([x for e in exams for x in e["pretendant"]])
    mean_k = np.mean([x for e in exams for x in e["champion"]])
    return bool(worst_c > worst_k and mean_c >= mean_k)


def _trial_summary(exams: list) -> str:
    c = np.mean([x for e in exams for x in e["pretendant"]])
    k = np.mean([x for e in exams for x in e["champion"]])
    return f"note moyenne {c:+.2f} contre {k:+.2f} pour le champion sur {sum(len(e['champion']) for e in exams)} périodes"


def _trade_count(m: dict) -> int:
    """Trades qui fondent la CONFIANCE dans une note : l'or + tous les marchés de l'examen pour une IA multi-marchés
    (09/10/2026 : avant, l'or seul -- une IA très active sur 50 marchés mais prudente sur l'or voyait sa note réduite)."""
    n = int(m.get("n_trades", 0) or 0)
    if m.get("markets"):
        n += sum(int(p.get("n_trades", 0) or 0) for p in m["markets"])
    return n


def _active_enough(m: dict, act: dict) -> bool:
    """Assez de trades sur l'or (validation) ET, si mesurés, sur l'ensemble des autres marchés.
    09/10/2026 : `min_avg_market_trades` = moyenne de trades par marché (et par période) de l'examen -- la règle des IA
    multi-marchés : l'or n'est plus qu'un marché parmi ~50 (le meilleur candidat du cycle 400, +4,35 %/mois et 100 %
    de réussite FTMO, avait été écarté pour 65 trades sur l'or)."""
    if int(m.get("n_trades", 0) or 0) < act["min_trades"]:
        return False
    markets = m.get("markets")
    if markets and sum(int(p.get("n_trades", 0) or 0) for p in markets) < act["min_market_trades"]:
        return False
    if markets and act.get("min_avg_market_trades", 0) > 0:
        if float(np.mean([int(p.get("n_trades", 0) or 0) for p in markets])) < act["min_avg_market_trades"]:
            return False
    return True


def _cycle_message(style: str, generation: int, inc_m: dict | None, candidates: list, promoted: bool) -> str:
    """Notification de fin de cycle en français simple (10/10/2026, demande de l'utilisateur : une par cycle)."""
    def per(m):
        p = (m or {}).get("portefeuille") or {}
        ps = p.get("periodes") or ([{"mensuel": p["mensuel"], "reussite": p["reussite"]}] if "mensuel" in p else [])
        if not ps:
            return "?", "?"
        return (" / ".join(f"{x['mensuel'] * 100:+.1f} %" for x in ps),
                " / ".join(f"{x['reussite'] * 100:.0f} %" for x in ps))
    gain, ok = per(inc_m)
    parts = [f"Champion : {gain} par mois (challenge réussi {ok})"]
    mine = [c for c in candidates if c.get("style") == style]
    active = [c for c in mine if not c.get("inactif")]
    if active:
        best = max(active, key=lambda c: float(c.get("score", -1e9)))
        g2, r2 = per(best.get("metrics"))
        parts.append(f"Meilleur candidat : {g2} (réussi {r2})")
    lazy = len(mine) - len(active)
    if lazy:
        parts.append(f"{lazy} écarté(s) pour manque d'activité")
    parts.append("NOUVEAU CHAMPION" if promoted else "champion conservé")
    trial = None if promoted else _trial_load(style)
    if trial:
        parts.append(f"prétendant gen {trial.get('generation')} à l'essai ({len(trial.get('exams') or [])} examen(s))")
    return f"Cycle {generation} : " + " | ".join(parts)


def _log_markets(style: str, m: dict) -> None:
    pf = m.get("portefeuille")
    if pf:
        for p in pf.get("periodes") or []:
            log.info(f"      [{style}] période {p['periode']} : compte tous marchés {p['mensuel']:+.2%}/mois, challenge "
                     f"réussi {p['reussite']:.0%} / raté {p['echec']:.0%} -> note {p['note']:+.2f}"
                     + (f" (compte fidèle : {p['trades_pris']} trades pris, {p['trades_refuses']} refusés)"
                        if p.get("trades_pris") is not None else ""))
        log.info(f"      [{style}] compte tous marchés : {pf['mensuel']:+.2%}/mois, challenge FTMO réussi "
                 f"{pf['reussite']:.0%} / raté {pf['echec']:.0%} -> note {pf['note']:+.2f} (gain {pf['gain']:+.2f}, "
                 f"FTMO {pf['ftmo']:+.2f}, mur -{pf['mur']:.2f})"
                 + (" [moins bonne des périodes]" if pf.get("periodes") else ""))
    if not m.get("markets"):
        return
    detail = ", ".join(f"{p['market']} {p.get('total_return', float('nan')):+.1%}" for p in m["markets"])
    log.info(f"      [{style}] note or {m.get('gold_score', float('nan')):.2f} | autres marchés "
             f"{m.get('markets_score', float('nan')):.2f} ({detail})")


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
    # Règles FTMO (mort/bonus, récompense en argent) : environnement d'ENTRAÎNEMENT seulement (train_env_kwargs).
    train_kwargs = {**spec["env_kwargs"], **(spec.get("train_env_kwargs") or {})}
    train = spec["train_df"]
    if hasattr(train, "load"):            # données partagées (src/shared_data.py) : lues en place, sans copie
        small, arr = train.load()
        env = TradingEnv(small, randomize_start=True, feature_array=arr, **train_kwargs)
    else:
        env = TradingEnv(train, randomize_start=True, **train_kwargs)
    # 07/10/2026 : recherche en mémoire calculée d'avance pour toutes les bougies (carte graphique si disponible)
    # au lieu de ~3 ms à chaque bougie jouée -- partagée par toutes les parties en parallèle (n_envs)
    if not spec.get("eval_only") and not spec.get("skip_learn"):
        env.precompute_memory()
    agent = TradingAgent(env, spec["hyperparams"], warm_start_model_path=spec["warm_start_path"])
    # RÉÉVALUATION DU CHAMPION (06/10/2026) : `eval_only` = poids du champion tels quels, aucun apprentissage.
    # EXAMEN EN DEUX TEMPS (08/10/2026) : `skip_learn` = candidat déjà entraîné au temps 1, rechargé pour l'examen complet.
    if not spec.get("eval_only") and not spec.get("skip_learn"):
        agent.learn(spec["timesteps"], label=label)
        acct = getattr(env, "_shared", None)
        if acct is not None:                         # 11/10 : compte partagé de l'entraînement (src/shared_account.py)
            games = agent.model.get_env().envs
            log.info(f"{label} compte partagé ({len(games)} parties) : {acct.restarts['mur']} mur(s) -9 %, "
                     f"{acct.restarts['objectif']} objectif(s) +10 %, "
                     f"{sum(g.n_budget_refused for g in games)} ouverture(s) refusée(s) (budget plein) en fin d'entraînement")
    if spec.get("phase") == 1:
        return _quick_exam_result(agent, spec)

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
    extra_trades = [] if (spec.get("extra_val") and spec.get("keep_extra_trades")) else None
    note_cfg = spec.get("note_argent")
    market_rets = {} if note_cfg else None
    # 11/10 : compte fidèle (note_argent.note_compte_fidele) -- trades horodatés de chaque marché
    account = {} if (note_cfg and note_cfg.get("compte_fidele")) else None
    if spec.get("extra_val"):
        score = _multi_market_score(agent, spec, score, metrics, fitness_metric, trades_out=extra_trades,
                                    rets_out=market_rets, account_out=account)

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
    if spec.get("compute_wfe", False) and not hasattr(spec["train_df"], "load"):
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
    if note_cfg:
        # NOTE « ARGENT FTMO » (09/10/2026, src/note_argent.py) : un compte qui trade l'or ET tous les marchés réels en
        # même temps ; la pire baisse de l'or (fenêtres + scénarios de crise) sert de mur. L'ancienne note est gardée
        # pour information (metrics["note_classique"]).
        # examen tournant : l'or de la période tirée est déjà dans les marchés ; sinon, la validation fixe de l'or
        market_rets.setdefault("XAUUSD", run_daily_returns(eval_env, spec["val_df"]))
        # 09/10 : plusieurs périodes tirées (marchés suffixés « pk ») -> un compte par période, la MOINS BONNE compte
        import re as _re
        groups = {}
        for name, r in market_rets.items():
            mk = _re.match(r"^(.*) p(\d+)$", name)
            k, base = (int(mk.group(2)), mk.group(1)) if mk else (1, name)
            groups.setdefault(k, {})[base] = r
        if account is not None:
            # compte fidèle : l'or de la validation fixe n'entre que s'il n'y a pas d'or dans les périodes tirées
            # (dates différentes : il étirerait la période du compte)
            if not any(_re.sub(r" p\d+$", "", n) == "XAUUSD" for n in account):
                account["XAUUSD"] = _account_entry(eval_env, spec["val_df"], "XAUUSD")
            acc_groups = {}
            for name, e in account.items():
                mk = _re.match(r"^(.*) p(\d+)$", name)
                k, base = (int(mk.group(2)), mk.group(1)) if mk else (1, name)
                acc_groups.setdefault(k, {})[base] = e
            pfs = [(k, note_compte_fidele(g, crisis_drawdown=float(metrics["max_drawdown"]), cfg=note_cfg))
                   for k, g in sorted(acc_groups.items())]
        else:
            pfs = [(k, note_portefeuille(g, crisis_drawdown=float(metrics["max_drawdown"]), cfg=note_cfg))
                   for k, g in sorted(groups.items())]
        pf = dict(min(pfs, key=lambda kp: kp[1]["note"])[1])
        if len(pfs) > 1:
            pf["periodes"] = [{"periode": k, "note": p["note"], "mensuel": p["mensuel"], "reussite": p["reussite"],
                               "echec": p["echec"], "trades_pris": p.get("trades_pris"),
                               "trades_refuses": p.get("trades_refuses")} for k, p in pfs]
        metrics["note_classique"] = float(score)
        metrics["portefeuille"] = pf
        score = pf["note"]
    elif spec.get("ftmo_weight"):
        ftmo = ftmo_chance(eval_env, spec["val_df"])
        metrics["ftmo"] = ftmo
        score += float(spec["ftmo_weight"]) * ftmo["term"]
    trades = [{"entry": t["entry"], "exit": t["exit"], "position": t["position"],
               "pnl_pct": t["pnl_pct"], "context": t["context"]} for t in eval_env.trade_log]

    agent.save(spec["out_path"])
    return {
        "score": score, "metrics": metrics, "model_path": spec["out_path"],
        "trades": trades, "extra_trades": extra_trades or [], "max_drawdown": eval_env.max_drawdown,
        "generation": spec["generation"], "style": spec["style"], "slot": spec["slot"],
        "feature_columns": spec["env_kwargs"]["feature_columns"],
        "context_timeframes": spec["context_timeframes"],
        "hyperparams": spec["hyperparams"], "env_search": spec.get("env_search"),
        "eval_only": bool(spec.get("eval_only")), "trial": bool(spec.get("trial")),
        "warm_started": bool(getattr(agent, "warm_started", True)),
        "vein_id": spec.get("vein_id"),
        "quick_score": spec.get("quick_score"), "quick": spec.get("quick"),
    }


def ftmo_chance(env, df, n_sims: int = 1000) -> dict:
    """CHANCE FTMO d'une partie rejouée (09/10/2026) : ses rendements journaliers rééchantillonnés (src/ftmo_metrics)
    -> chance de réussir le challenge (+10 % avant -5 % sur un jour ou -10 % au total). Terme de note = réussite -
    échecs : une IA qui joue minuscule ne réussit jamais (terme 0), une IA casino échoue souvent (terme négatif) ;
    seule une IA qui gagne avec une taille raisonnable obtient un terme positif."""
    from src.ftmo_metrics import daily_returns, simulate, TARGETS
    eq = np.asarray(env.equity_curve, dtype=float)
    start = max(0, int(env.window_size) - 1)
    times = pd.to_datetime(df["time"]).iloc[start:start + len(eq)]
    rets = daily_returns(eq[:len(times)], times).to_numpy()
    if len(rets) < 20:
        return {"pass": 0.0, "breach": 0.0, "term": 0.0, "n_days": int(len(rets))}
    s = simulate(rets, TARGETS["challenge"], n_sims, rng=np.random.default_rng(7))
    breach = float(s["daily_breach"] + s["total_breach"])
    return {"pass": float(s["pass"]), "breach": breach, "term": float(s["pass"]) - breach, "n_days": int(len(rets))}


def _quick_exam_result(agent, spec: dict) -> dict:
    """TEMPS 1 de l'examen (08/10/2026) : le candidat (ou le champion) joue le PETIT EXAMEN du cycle -- un marché et
    une période tirés au hasard + la même période passée au mélangeur. Note par épreuve = même formule que les
    marchés (fitness - 2 x baisse max, bornée) ; petit score = moyenne. Le modèle entraîné est sauvegardé pour le
    temps 2 (examen complet), réservé aux candidats qui tiennent la comparaison avec le champion."""
    from src.backtester import compute_metrics as _metrics
    clip = float(spec.get("extra_val_score_clip", 5.0))
    fitness_metric = spec.get("fitness_metric", "sortino")
    tf = base_timeframe(spec.get("style", "H1"))
    details, trades, worst_dd = [], [], 0.0
    for name, df in spec["quick_exam"]:
        env = run_episode(agent, TradingEnv(df, **spec["env_kwargs"]))
        m = _metrics(env, timeframe=tf)
        if spec.get("note_argent"):                    # même note « argent FTMO » que l'examen complet, sur ce marché
            s = note_run(run_daily_returns(env, df), float(m["max_drawdown"]), spec["note_argent"])
        else:
            s = float(np.clip(m.get(fitness_metric, m["sharpe"]) - 2.0 * m["max_drawdown"], -clip, clip))
        details.append({"epreuve": name, "score": s, "total_return": float(m["total_return"]),
                        "max_drawdown": float(m["max_drawdown"]), "sharpe": float(m["sharpe"]),
                        "n_trades": int(m.get("n_trades", 0) or 0)})
        worst_dd = max(worst_dd, float(m["max_drawdown"]))
        if name.startswith("tirage"):                  # souvenirs : la vraie période seulement
            trades += [{"entry": t["entry"], "exit": t["exit"], "position": t["position"], "pnl_pct": t["pnl_pct"],
                        "context": t["context"], "market": name} for t in env.trade_log]
    q = float(np.mean([d["score"] for d in details])) if details else -clip
    agent.save(spec["out_path"])
    first = details[0] if details else {"sharpe": 0.0, "total_return": 0.0, "n_trades": 0}
    return {
        "phase": 1, "quick_score": q, "quick": details, "score": q, "model_path": spec["out_path"],
        "metrics": {"sharpe": first["sharpe"], "max_drawdown": worst_dd, "total_return": first["total_return"],
                    "n_trades": sum(d["n_trades"] for d in details), "quick": details},
        "trades": [], "extra_trades": trades, "max_drawdown": worst_dd,
        "generation": spec["generation"], "style": spec["style"], "slot": spec["slot"],
        "feature_columns": spec["env_kwargs"]["feature_columns"], "context_timeframes": spec["context_timeframes"],
        "hyperparams": spec["hyperparams"], "env_search": spec.get("env_search"),
        "eval_only": bool(spec.get("eval_only")), "trial": bool(spec.get("trial")), "vein_id": spec.get("vein_id"),
        "warm_started": bool(getattr(agent, "warm_started", True)),
    }


class ContinuousEvolutionTrainer:
    @staticmethod
    def _run_pool(specs: list, max_workers: int) -> list:
        if max_workers > 1 and len(specs) > 1:
            with ProcessPoolExecutor(max_workers=min(max_workers, len(specs))) as pool:
                return list(pool.map(_train_candidate_worker, specs))
        return [_train_candidate_worker(s) for s in specs]

    def _two_stage_exam(self, specs: list, max_workers: int, total_threads: int) -> list:
        """EXAMEN EN DEUX TEMPS (08/10/2026). Temps 1 : chaque candidat apprend puis passe le PETIT EXAMEN du cycle
        (marché + période tirés au hasard, + mélangeur), le champion aussi. Temps 2 : examen complet (or,
        scénarios de crise, autres marchés) seulement pour les candidats qui font au moins presque aussi bien que
        le champion (écart <= `margin`), plus les `keep_best` meilleurs pour ne jamais tout jeter ; les autres sont
        éliminés (score = petit score - 10, leurs trades restent en mémoire). Le champion repasse l'examen complet."""
        qcfg = (self.cfg.get("multi_market") or {}).get("quick_exam") or {}
        margin, keep_best = float(qcfg.get("margin", 0.25)), int(qcfg.get("keep_best", 1))
        # le prétendant à l'essai ne repasse pas le petit examen : directement l'examen complet, comme le champion
        trial_specs = [{k: v for k, v in s.items() if k != "phase"} for s in specs if s.get("trial")]
        specs = [s for s in specs if not s.get("trial")]
        p1 = self._run_pool(specs, max_workers)
        by_out = {s["out_path"]: s for s in specs}
        inc_q = {(r["style"], r["slot"]): r["quick_score"] for r in p1 if r.get("eval_only") and not r.get("trial")}
        cands = [r for r in p1 if not r.get("eval_only")]
        passed = set()
        for key in sorted({(r["style"], r["slot"]) for r in cands}):
            group = sorted([r for r in cands if (r["style"], r["slot"]) == key],
                           key=lambda r: r["quick_score"], reverse=True)
            ref = inc_q.get(key)
            for i, r in enumerate(group):
                if i < keep_best or ref is None or r["quick_score"] >= ref - margin:
                    passed.add(r["model_path"])
            names = " + ".join(d["epreuve"] for d in (group[0].get("quick") or []))
            log.info(f"  [{key[0]}] petit examen ({names}) : champion "
                     f"{(ref if ref is not None else float('nan')):+.2f} | candidats "
                     + ", ".join(f"{r['quick_score']:+.2f}{'*' if r['model_path'] in passed else ''}" for r in group)
                     + f" -> examen complet pour {sum(1 for r in group if r['model_path'] in passed)}/{len(group)}")
        p2_specs = []
        for r in p1:
            if not (r.get("eval_only") or r["model_path"] in passed):
                continue
            s = {k: v for k, v in by_out[r["model_path"]].items() if k != "phase"}
            s.update(quick_score=r["quick_score"], quick=r.get("quick"))
            if not r.get("eval_only"):
                s.update(skip_learn=True, warm_start_path=r["model_path"])
            p2_specs.append(s)
        p2_specs += trial_specs
        n2 = max(1, min(max_workers, len(p2_specs)))
        for s in p2_specs:                              # moins de copies au temps 2 -> plus de cœurs chacune
            s["torch_threads"] = max(1, total_threads // n2) if max_workers > 1 else s.get("torch_threads")
        p2 = self._run_pool(p2_specs, max_workers)
        eliminated = []
        for r in p1:
            if r.get("eval_only") or r["model_path"] in passed:
                continue
            r.update(score=float(r["quick_score"]) - 10.0, eliminated=True)
            eliminated.append(r)
        return p2 + eliminated

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

        self.memory = EpisodicMemory(cfg["memory"]["db_path"], cfg["memory"]["max_episodes"],
                                     private_styles=cfg["memory"].get("private_styles"))

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

    def _update_incumbent_eligibility(self, tf: str, fresh_metrics: dict):
        """ÉLIGIBILITÉ SUR MESURE FRAÎCHE (06/10/2026) : `passes_validation` n'était calculé qu'à la promotion --
        un champion mesuré juste sous un seuil ce jour-là restait bloqué même en le passant ensuite cycle après
        cycle (AUREX gén 253 : Sharpe 0.67 à la promotion, 0.79 / 0.75 / 0.80 rejoué). Avec la réévaluation du
        champion, on applique EXACTEMENT les mêmes seuils (passes_validation + porte lockbox) à sa mesure
        fraîche : éligible après `incumbent_eligibility_streak` cycles consécutifs réussis, retiré après autant
        de cycles consécutifs ratés. Aucun seuil n'est abaissé."""
        need = int(self.cfg["continuous"].get("incumbent_eligibility_streak", 3) or 0)
        if need <= 0:
            return
        path = _champion_meta(tf)
        meta = self._read_json(path)
        if not meta:
            return
        min_gen = self.cfg["validation"].get("min_generations_before_demo", 0)
        fresh_ok = bool(passes_validation(fresh_metrics, self.cfg, style=tf) and self.generation + 1 >= min_gen)
        hist = (list(meta.get("fresh_validation") or []) + [fresh_ok])[-need:]
        meta["fresh_validation"] = hist
        was = bool(meta.get("passes_validation"))
        streak_ok = len(hist) >= need and all(hist)
        streak_ko = len(hist) >= need and not any(hist)
        log.info(f"  [{tf}] seuils de validation sur la mesure fraîche du champion : "
                 f"{'OK' if fresh_ok else 'non'} (historique {hist}, éligible démo={was})")
        if not was and streak_ok:
            lb, gate_ok = self._lockbox_check(tf, _champion_model(tf), meta,
                                              self._read_json(_champion_stats(tf)), False)
            self.__dict__.get("_lockbox_cache", {}).clear()   # le cache vise les candidats de ce cycle
            if gate_ok:
                meta["passes_validation"] = True
                meta["fresh_metrics"] = fresh_metrics
                meta["eligible_since"] = time.time()
                if lb is not None:
                    meta["lockbox"] = lb
                log.info(f"  -> '{tf}' gén {meta.get('generation')} ÉLIGIBLE DÉMO : seuils passés {need} cycles de "
                         f"suite sur mesure fraîche + porte lockbox OK.")
                try:
                    from src.notifier import send_alert
                    send_alert(self.cfg, subject=f"Test_IA - style '{tf}' promu en demo",
                               message=(f"Le champion '{tf}' (génération {meta.get('generation')}) passe les seuils "
                                        f"{need} cycles de suite (sharpe={fresh_metrics['sharpe']:.2f}) et la porte "
                                        f"lockbox : il est maintenant éligible à la démo."))
                except Exception:
                    pass
        elif was and streak_ko:
            meta["passes_validation"] = False
            log.warning(f"  -> '{tf}' gén {meta.get('generation')} RETIRÉ de la démo : seuils ratés {need} cycles "
                        f"de suite sur mesure fraîche.")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2, default=str)

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
            if not meta or meta.get("passes_validation") or not meta.get("metrics"):
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
        self._cycle_promoted = set()                       # styles dont le champion a changé ce cycle (notification)

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
            # 10/10 : `notify_cycle_start: false` = une seule notification par cycle (celle de fin, avec les résultats)
            if notif_cfg.get("notify_every_cycle") and notif_cfg.get("notify_cycle_start", True):
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

        reevaluate_incumbent = bool(self.cfg["continuous"].get("reevaluate_incumbent", False))
        total_candidates = ((n_per_style + (1 if reevaluate_incumbent else 0))
                            * population_size * len(self.timeframe_pool))
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
        vcfg = self.cfg["continuous"].get("veins") or {}
        veins_styles = set(vcfg.get("styles") or []) if vcfg.get("enabled") else set()
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
            # DONNÉES PARTAGÉES (08/10/2026, continuous.shared_train_data) : une seule version sur le disque pour
            # toutes les copies d'entraînement au lieu d'une copie par processus (voir src/shared_data.py).
            if (self.cfg["continuous"].get("shared_train_data")
                    and len(train_df) >= int(self.cfg["continuous"].get("shared_min_rows", 50_000))):
                from src.shared_data import share_frame
                train_df = share_frame(train_df, feature_columns, tag=f"train_{tf}")
            # SÉLECTION MULTI-MARCHÉS (07/10/2026, multi_market.selection) : examens des autres marchés de ce style,
            # préparés par get_data ; le champion réévalué et les candidats passent EXACTEMENT les mêmes.
            extra_val = (getattr(self.get_data_fn, "extra_val", None) or {}).get(tf) or None
            mm_sel = (self.cfg.get("multi_market") or {}).get("selection") or {}
            extra_spec = ({"extra_val": extra_val, "extra_val_gold_weight": float(mm_sel.get("gold_weight", 0.5)),
                           "extra_val_score_clip": float(mm_sel.get("score_clip", 5.0)),
                           "keep_extra_trades": tf in self.memory.private_styles} if extra_val else {})
            quick = (getattr(self.get_data_fn, "quick_exam", None) or {}).get(tf)
            if quick:                                    # examen en deux temps (voir _two_stage_exam)
                extra_spec = {**extra_spec, "quick_exam": quick, "phase": 1}
            # RÈGLES FTMO À L'ENTRAÎNEMENT + CHANCE FTMO DANS LA NOTE (09/10/2026) : `environment.training_only.<style>`
            # = réglages du simulateur d'ENTRAÎNEMENT seulement (mort à -5 %/-10 %, bonus à +10 %) -- l'examen joue
            # toujours les périodes en entier ; `continuous.ftmo_weight_by_style.<style>` = poids de la chance de
            # réussir le challenge dans la note (même calcul pour le champion réévalué et les candidats).
            train_only = ((self.cfg.get("environment") or {}).get("training_only") or {}).get(tf) or {}
            ftmo_w = float(((self.cfg["continuous"].get("ftmo_weight_by_style") or {}).get(tf)) or 0.0)
            if train_only or ftmo_w:
                extra_spec = {**extra_spec, "train_env_kwargs": dict(train_only), "ftmo_weight": ftmo_w}
            note_argent = (self.cfg["continuous"].get("note_argent_by_style") or {}).get(tf)
            if note_argent:                              # note « argent FTMO » (src/note_argent.py)
                extra_spec = {**extra_spec, "note_argent": dict(note_argent)}
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
            # 07/10/2026 : `style` -> un style à mémoire privée (memory.private_styles) ne lit que ses propres trades
            memory_snapshot = self.memory.snapshot(dim=len(feature_columns), sources=["backtest"], style=tf)
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
                # RÉÉVALUATION DU CHAMPION (06/10/2026) : son score mémorisé est le MAXIMUM d'une mesure
                # passée (autres données, autre mémoire épisodique) -- une barre périmée que plus aucun
                # candidat ne franchit. On le rejoue ici, poids figés, sur EXACTEMENT les mêmes données
                # et la même évaluation que les candidats de ce cycle : la comparaison devient équitable.
                if reevaluate_incumbent and warm_start_path:
                    specs.append({
                        "train_df": train_df, "val_df": val_df, "env_kwargs": style_env_kwargs,
                        "env_search": None, "eval_only": True,
                        "hyperparams": slot_center, "warm_start_path": warm_start_path, "timesteps": 0,
                        "out_path": os.path.join(CANDIDATES_TMP_DIR, f"{tf}_{slot}_incumbent"),
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
                        "label": f"[gen {self.generation} | {tf} pop{slot} champion réévalué]",
                        **extra_spec,
                    })
                    candidate_index += 1
                    # PÉRIODE D'ESSAI (10/10/2026) : le prétendant repasse l'examen de CE cycle, poids figés
                    trial = _trial_load(tf) if (population_size == 1 and _trial_need(self.cfg, tf) > 1) else None
                    if trial is not None:
                        specs.append({**specs[-1], "trial": True,
                                      "hyperparams": {**(trial.get("hyperparams") or slot_center), **(style_overrides or {})},
                                      "warm_start_path": os.path.join(_trial_dir(tf), "agent"),
                                      "out_path": os.path.join(CANDIDATES_TMP_DIR, f"{tf}_{slot}_pretendant"),
                                      "torch_threads": (thread_counts[candidate_index % max_workers]
                                                        if max_workers > 1 else None),
                                      "label": f"[gen {self.generation} | {tf} prétendant gen {trial.get('generation')}]"})
                        candidate_index += 1
                # VEINES (08/10/2026) : le DERNIER candidat (jamais le témoin #0) repart d'une veine secondaire
                # tirée au prorata de son flux, au lieu d'une mutation du champion (voir _veins_update).
                fed_vein = (_pick_vein(_veins_load(tf), self.generation)
                            if tf in veins_styles and population_size == 1 and n_per_style >= 2 else None)
                if fed_vein is not None:
                    log.info(f"  [{tf}] veine nourrie ce cycle : {fed_vein['id']} (écart au champion {_gap(fed_vein):+.3f}, "
                             f"flux {float(fed_vein['flux']):.2f}, {fed_vein.get('reason', '')})")
                for i in range(n_per_style):
                    vein = fed_vein if (fed_vein is not None and i == n_per_style - 1) else None
                    base_center = ({**(vein.get("hyperparams") or slot_center), **(style_overrides or {})}
                                   if vein is not None else slot_center)
                    hp = slot_center if i == 0 else mutate_hyperparams(
                        base_center, slot_sigma,
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
                        "hyperparams": hp, "timesteps": timesteps,
                        "warm_start_path": vein["path"] if vein is not None else warm_start_path,
                        "vein_id": vein["id"] if vein is not None else None,
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
                        "label": f"[gen {self.generation} | {tf} pop{slot} #{i}"
                                 f"{' veine ' + vein['id'] if vein is not None else ''}]",
                        **extra_spec,
                    })
                    candidate_index += 1

        log.info(f"Entraînement de {total_candidates} candidats ({n_per_style} par style x "
                  f"{len(self.timeframe_pool)} styles {self.timeframe_pool}) sur {max_workers} "
                  f"processus en parallèle ({sum(thread_counts)} threads CPU au total, "
                  f"répartition {thread_counts})...")

        if any(s.get("phase") == 1 for s in specs):
            results = self._two_stage_exam(specs, max_workers, sum(thread_counts))
        elif max_workers > 1:
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
                "n_trades": int(r["metrics"].get("n_trades", 0) or 0),
                "win_rate": float(r["metrics"].get("win_rate", 0) or 0),
                "stop_exit_rate": float(r["metrics"].get("stop_exit_rate", 0) or 0),
                "kind": ("incumbent" if r.get("eval_only")
                         else "reward_search" if r.get("env_search") else "control"),
                "env_search": r.get("env_search"),
            } for r in results])
        except Exception as exc:  # le journal ne doit jamais interrompre l'entraînement
            log.warning(f"Journal d'expériences : écriture impossible ({exc}).")

        # Champion réévalué (voir reevaluate_incumbent) : son score FRAIS devient la barre à battre de ce
        # cycle, dans un sens comme dans l'autre -- il n'entre jamais en concurrence comme candidat.
        inc_metrics_by_style = {}          # champion réévalué de ce cycle, référence des veines
        inc_score_by_style = {}
        trial_results = {r["style"]: r for r in results if r.get("trial")}
        for r in [r for r in results if r.get("eval_only") and not r.get("trial")]:
            key = (r["style"], r["slot"])
            m = r["metrics"]
            if r["slot"] == 0:
                inc_metrics_by_style[r["style"]] = m
                inc_score_by_style[r["style"]] = r["score"]
            log.info(f"  [{r['style']}] champion réévalué sur les données de ce cycle : score={r['score']:.3f} "
                     f"(mémorisé {self.slot_score.get(key, float('nan')):.3f}) sharpe={m['sharpe']:.2f} "
                     f"drawdown={m['max_drawdown']:.2%} return={m['total_return']:.2%} "
                     f"trades={int(m.get('n_trades', 0) or 0)}")
            _log_markets(r["style"], m)
            self.slot_score[key] = r["score"]
            self.slot_n_trades[key] = _trade_count(m)            # 09/10 : tous les marchés de l'examen
            act = _activity_rule(self.cfg, r["style"])
            if act and not _active_enough(m, act):         # champion trop peu actif : tout candidat actif le remplace
                log.warning(f"  [{r['style']}] champion actuel trop peu actif ({self.slot_n_trades[key]} trades sur l'or) "
                            f"-> remplaçable par n'importe quel candidat actif.")
                self.slot_score[key] = -1e8                 # 09/10 : -99 -> -1e8 (la note n'a plus de plancher ; -1e9 = « pas de champion »)
            if _slot_model(r["style"], r["slot"], population_size) == _champion_model(r["style"]):
                self.champion_score[r["style"]] = self.slot_score[key]    # -1e8 si trop peu actif (voir ci-dessus)
                self.champion_n_trades[r["style"]] = self.slot_n_trades[key]
                self._update_incumbent_eligibility(r["style"], m)
        trial_won = set()                  # styles dont le prétendant a réussi sa période d'essai CE cycle
        for tf, r in trial_results.items():
            trial = _trial_load(tf)
            if trial is None or tf not in inc_metrics_by_style:
                continue
            if not r.get("warm_started", True):
                # incident du cycle 435 : cerveau refusé au chargement -> examiné « à neuf » (-175 %/mois) ; jamais compté
                log.warning(f"  [{tf}] prétendant gen {trial.get('generation')} : cerveau non rechargé, examen de ce "
                            f"cycle NON compté")
                continue
            trial.setdefault("exams", []).append({
                "cycle": self.generation, "pretendant": _period_notes(r["metrics"], r["score"]),
                "champion": _period_notes(inc_metrics_by_style[tf], inc_score_by_style[tf])})
            need = _trial_need(self.cfg, tf)
            verdict = _trial_verdict(trial["exams"], need)
            log.info(f"  [{tf}] prétendant gen {trial.get('generation')} à l'essai, examen {len(trial['exams'])}/{need} "
                     f"(note de ce cycle {r['score']:+.2f}) : {_trial_summary(trial['exams'])}")
            _log_markets(tf, r["metrics"])
            if verdict is None:
                _trial_save(tf, trial)
            elif verdict:
                r.update(eval_only=False, trial_winner=True, vein_id=trial.get("vein_id"),
                         env_search=trial.get("env_search"))
                log.info(f"  [{tf}] période d'essai RÉUSSIE : le prétendant gen {trial.get('generation')} "
                         f"devient champion")
            else:
                _trial_drop(tf)
                log.info(f"  [{tf}] période d'essai ratée : le prétendant gen {trial.get('generation')} est écarté, "
                         f"le champion reste")
        results = [r for r in results if not r.get("eval_only")]

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
            _log_markets(r["style"], m)
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
                # ACTIVITÉ MINIMALE (08/10/2026, demande explicite : « évite de promouvoir une IA qui fait 0 trade ») :
                # un candidat qui trade trop peu (or ET autres marchés) ne peut JAMAIS devenir champion -- ne rien faire
                # ne perd rien et finissait par gagner les comparaisons (gén. 358 : 28 trades, note +0,07).
                act = _activity_rule(self.cfg, tf)
                if act:
                    lazy = [r for r in candidates if not _active_enough(r["metrics"], act)]
                    for r in lazy:
                        # 09/10 : un candidat écarté qui BATTAIT le champion est mis à l'abri (models/ecartes_<style>/)
                        # au lieu d'être effacé avec les fichiers temporaires -- incident du cycle 400 (+4,35 %/mois perdu).
                        if float(r["score"]) > float(self.slot_score.get(key, -1e9)):
                            _keep_excluded(tf, self.generation, r)
                        r["score"] = min(float(r["score"]), -1e6)   # 09/10 : -50 -> -1e6 (note sans plancher)
                        r["inactif"] = True
                    if lazy:
                        log.info(f"  [{tf}] {len(lazy)} candidat(s) écarté(s) de la promotion : trop peu actif(s) "
                                 f"(trades or {[int(r['metrics'].get('n_trades', 0) or 0) for r in lazy]}, "
                                 f"trades tous marchés {[_trade_count(r['metrics']) for r in lazy]} ; minimum "
                                 f"{act['min_trades']} sur l'or, {act['min_avg_market_trades']:g} par marché en moyenne)")
                # 06/10/2026 : classement sur le score FIABLE (celui qui décide la promotion), pas le score brut --
                # sinon un candidat chanceux sur peu de trades prend la 1re place et masque un candidat solide.
                candidates.sort(key=lambda r: _confident_score(r["score"], _trade_count(r["metrics"]), _mtc(tf)),
                                reverse=True)
                # un prétendant qui vient de RÉUSSIR sa période d'essai est promu (le cumul a déjà tranché)
                winner = next((r for r in candidates if r.get("trial_winner") and not r.get("inactif")), None)
                best = winner if winner is not None else candidates[0]
                best_n_trades = _trade_count(best["metrics"])
                # MARGE DE PROMOTION (06/10/2026) : battre le champion d'une marge nette, pas d'un écart de bruit.
                margin = float(self.cfg["continuous"].get("promotion_min_margin", 0.0) or 0.0)
                promoted = (
                    winner is not None
                    or _confident_score(best["score"], best_n_trades, _mtc(tf))
                    > _confident_score(self.slot_score[key], self.slot_n_trades.get(key, 0), _mtc(tf)) + margin
                    or not os.path.exists(_slot_model(tf, slot, population_size) + ".zip")
                )
                # PLUSIEURS PÉRIODES (09/10/2026, incident du cycle 402) : la note = la MOINS BONNE période ; quand une
                # période est catastrophique pour tout le monde, un candidat la gagnait de 0,13 point en étant 3x pire
                # sur l'autre (-10,9 %/mois contre -3,5 %) et remplaçait un bon champion. Il faut AUSSI ne pas être moins
                # bon que le champion en MOYENNE sur les périodes.
                if promoted and winner is None and os.path.exists(_slot_model(tf, slot, population_size) + ".zip"):
                    cand_mean = _mean_period_note(best["metrics"])
                    inc_mean = _mean_period_note(inc_metrics_by_style.get(tf) or {}) if slot == 0 else None
                    if cand_mean is not None and inc_mean is not None and cand_mean < inc_mean:
                        log.info(f"  [{tf}] promotion refusée : meilleur sur la plus mauvaise période mais moins bon en "
                                 f"moyenne sur les périodes ({cand_mean:+.2f} contre {inc_mean:+.2f} pour le champion)")
                        promoted = False
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
                if (promoted and _validation_veto(self.cfg, tf) and _slot_model(tf, slot, population_size) == _champion_model(tf)
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
                if (promoted and _validation_veto(self.cfg, tf) and _slot_model(tf, slot, population_size) == _champion_model(tf)
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
                # PÉRIODE D'ESSAI (10/10/2026) : un nouveau gagnant n'est pas promu tout de suite -- il devient
                # prétendant (ou remplace le prétendant en cours s'il fait mieux que lui sur CET examen).
                if (promoted and winner is None and population_size == 1 and _trial_need(self.cfg, tf) > 1
                        and tf in inc_metrics_by_style
                        and os.path.exists(_slot_model(tf, slot, population_size) + ".zip")):
                    promoted = False
                    current, cur_r = _trial_load(tf), trial_results.get(tf)
                    # 10/10 22h20 : un prétendant qui MÈNE son essai en cumulé va jusqu'au bout -- sinon un seul bon
                    # tirage d'un nouveau candidat le remplaçait (446, en tête, remplacé par 447 au cycle 447)
                    leading = current is not None and _trial_leading(current.get("exams") or [])
                    if leading:
                        log.info(f"  [{tf}] candidat gen {self.generation} meilleur que le champion, mais le prétendant "
                                 f"gen {current.get('generation')} mène son essai : il le termine "
                                 f"({_trial_summary(current['exams'])})")
                    elif current is None or cur_r is None or float(best["score"]) > float(cur_r["score"]):
                        exam = {"cycle": self.generation, "pretendant": _period_notes(best["metrics"], best["score"]),
                                "champion": _period_notes(inc_metrics_by_style[tf], inc_score_by_style[tf])}
                        _trial_save(tf, {"generation": self.generation, "debut": time.strftime("%Y-%m-%d %H:%M"),
                                         "hyperparams": best["hyperparams"], "env_search": best.get("env_search"),
                                         "vein_id": best.get("vein_id"), "feature_columns": best["feature_columns"],
                                         "context_timeframes": best["context_timeframes"], "exams": [exam]},
                                    model_path=best["model_path"])
                        best["trial_started"] = True
                        log.info(f"  [{tf}] candidat gen {self.generation} meilleur que le champion sur cet examen -> "
                                 f"PRÉTENDANT à l'essai ({_trial_need(self.cfg, tf)} examens au total"
                                 + (f", remplace le prétendant gen {current.get('generation')}" if current else "")
                                 + ")")
                    else:
                        log.info(f"  [{tf}] candidat gen {self.generation} meilleur que le champion mais pas que le "
                                 f"prétendant à l'essai ({float(best['score']):+.2f} contre {float(cur_r['score']):+.2f})")
                if promoted:
                    if winner is not None:
                        trial_won.add(tf)
                        _trial_drop(tf)
                    best["promoted"] = True        # voir _veins_update (une veine qui gagne devient le chemin principal)
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
                        json.dump({k: [float(x) for x in v] for k, v in style_stats[tf].items()}, f, indent=2)

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
                or tf in trial_won                 # période d'essai réussie : le cumul a tranché (voir plus haut)
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
                deploy = style_passes or not was_eligible_before or not _validation_veto(self.cfg, tf)
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
                    self._cycle_promoted.add(tf)
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
        # 09/10/2026 : une IA qui n'a PAS le droit de trader (live.trading_styles) n'est jamais copiée en champion démo
        # -- sinon, l'entraînement ne voyant que ses propres styles, elle était « promue » (et annoncée par
        # notification) à CHAQUE cycle dès qu'elle passait les seuils (AUREXIS, 02h24 -> 10h13, sans effet sur les ordres).
        allowed_live = (self.cfg.get("live") or {}).get("trading_styles")
        not_allowed = bool(overall_best is not None and allowed_live and overall_best["style"] not in allowed_live)
        if not_allowed:
            passes = False
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
                json.dump({k: [float(x) for x in v] for k, v in style_stats[overall_best["style"]].items()}, f, indent=2)
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
        elif not_allowed:
            log.info(f"  -> '{overall_best['style']}' n'est pas autorisé à trader (live.trading_styles) : "
                     f"pas de champion démo.")
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

        # ÉTAT D'ENTRAÎNEMENT (voir src/status_files.py) : reports/training_status.json.
        # Ne doit jamais interrompre le cycle si ça échoue.
        try:
            from src.status_files import write_training_status
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
                    # 10/10 : AUREXIS -> une notification courte en français simple (résultats du compte par période,
                    # meilleur candidat, champion changé ou non), numérotée comme le journal.
                    sent_aurexis = False
                    if "AUREXIS" in self.timeframe_pool:
                        send_alert(self.cfg, subject=f"AUREXIS - cycle {self.generation}",
                                   message=_cycle_message("AUREXIS", self.generation,
                                                          inc_metrics_by_style.get("AUREXIS"), results,
                                                          "AUREXIS" in getattr(self, "_cycle_promoted", set())))
                        sent_aurexis = True
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
                    if not sent_aurexis: send_alert(
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

        # VEINES : croissance / amincissement / naissance / disparition, AVANT l'effacement des candidats
        for tf in veins_styles:
            try:
                # 08/10 : si un candidat vient d'être promu, les veines se mesurent au NOUVEAU champion
                ref = [s for s in [inc_score_by_style.get(tf)] if s is not None]
                ref += [r["score"] for r in results if r.get("promoted") and r.get("style") == tf]
                veins, vlines = _veins_update(tf, _veins_load(tf), results, inc_metrics_by_style.get(tf),
                                              self.generation, vcfg, inc_score=max(ref) if ref else None)
                for line in vlines:
                    log.info(f"  [{tf}] {line}")
                summary = ", ".join(f"{v['id']} flux {float(v['flux']):.2f} écart {_gap(v):+.2f}" for v in veins)
                log.info(f"  [{tf}] veines vivantes : {len(veins)}{' (' + summary + ')' if veins else ''}")
            except Exception as exc:        # les veines ne doivent jamais interrompre l'entraînement
                log.warning(f"  [{tf}] veines : mise à jour impossible ({type(exc).__name__}: {exc})")

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
        # MÉMOIRE PRIVÉE (07/10/2026) : un style à mémoire propre (AUREXIS) garde aussi ses trades sur les autres
        # marchés et les marchés inversés -- ses souvenirs contiennent alors des ventes, pas seulement l'or.
        private = result.get("style") in self.memory.private_styles
        if private:
            trades = trades + list(result.get("extra_trades") or [])
        max_trades = 2000
        if len(trades) > max_trades:
            step = len(trades) / max_trades
            trades = [trades[int(i * step)] for i in range(max_trades)]
        # 06/10/2026 : écriture groupée (une transaction par candidat au lieu d'une par trade).
        self.memory.store_many([{"context": np.array(t["context"], dtype=np.float32), "action": t["position"],
                                 "pnl_pct": t["pnl_pct"], "drawdown": result["max_drawdown"],
                                 "generation": result["generation"], "source": "backtest",
                                 "style": result.get("style") if private else None,
                                 "symbol": t.get("market")} for t in trades])

    def close(self):
        self.memory.close()
