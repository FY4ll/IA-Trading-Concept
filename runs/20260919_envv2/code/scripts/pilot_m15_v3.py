"""
Pilote v3 ISOLE, en DEUX PHASES SEPAREES (mesure isolee de chaque effet,
demande explicite) :
  --phase atr_fix   : UNIQUEMENT le correctif atr_14 (rolling z-score au
                       lieu d'un z-score global sur 22 ans) -- espace de
                       mutation INCHANGE (les 5 memes hyperparametres
                       qu'avant), pour isoler cet effet seul.
  --phase expanded  : correctif atr_14 EN PLUS de l'espace de mutation
                       elargi (net_arch / window_size / lstm_hidden_size
                       desormais mutables) -- pour isoler l'effet
                       INCREMENTAL de l'elargissement, par-dessus le
                       correctif deja actif.

ISOLATION TOTALE (comme le pilote v2) : aucun fichier src/*.py n'est
modifie sur disque -- tout est fait par monkeypatch DANS CE PROCESSUS
(parallel_workers=1 => _train_candidate_worker tourne dans CE processus,
pas dans un sous-processus spawn qui perdrait les patches sous Windows).
Chaque phase ecrit dans son PROPRE repertoire, jamais models/.

Lancement : python scripts/pilot_m15_v3.py --phase atr_fix
            python scripts/pilot_m15_v3.py --phase expanded
"""
import sys
import os
import copy
import random
import logging
import argparse
import json
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.chdir(Path(__file__).resolve().parent.parent)

parser = argparse.ArgumentParser()
parser.add_argument("--phase", choices=["atr_fix", "expanded"], required=True)
args = parser.parse_args()

import yaml
import numpy as np
import pandas as pd
import src.continuous_trainer as ct
import src.features as feat
import src.evolution as evo
from src.trading_env import TradingEnv
from src.agent import TradingAgent
from src.backtester import evaluate_agent_walkforward, run_episode

PILOT_ROOT = f"models_pilot_m15_v3_{args.phase}"
ct.MODELS_ROOT = PILOT_ROOT
ct.DEMO_DIR = os.path.join(PILOT_ROOT, "demo_champion")
ct.DEMO_MODEL = os.path.join(ct.DEMO_DIR, "agent")
ct.DEMO_META = os.path.join(ct.DEMO_DIR, "meta.json")
ct.DEMO_STATS = os.path.join(ct.DEMO_DIR, "norm_stats.json")
ct.CANDIDATES_TMP_DIR = os.path.join(PILOT_ROOT, "_tmp_candidates")
ct.PROGRESS_FILE = os.path.join(PILOT_ROOT, "_progress.json")

logging.basicConfig(level=logging.INFO, format=f"%(asctime)s [PILOTE-M15-v3-{args.phase}] [%(name)s] %(message)s")
log = logging.getLogger("pilot_m15_v3")

ENTROPY_LOG_PATH = os.path.join(ct._champion_dir("M15"), "entropy_log.jsonl")


# ============================================================
# 1) CORRECTIF ATR_14 -- rolling z-score au lieu d'un z-score global fixe.
#    Actif dans LES DEUX phases (atr_fix ET expanded, qui part de atr_fix).
# ============================================================
_ORIGINAL_add_technical_features = feat.add_technical_features


def _patched_add_technical_features(df, fundamental_feed=None, refresh_fundamental=True):
    df = _ORIGINAL_add_technical_features(df, fundamental_feed, refresh_fundamental)
    # atr_14 est en unites de PRIX BRUTES (dollars) -- sur un dataset qui
    # couvre l'or de quelques centaines de dollars (2004) a plus de 4300$
    # (2026), un z-score UNIQUE calcule sur tout le train ne corrige pas la
    # derive du niveau de prix. Remplace par un z-score GLISSANT (fenetre
    # 300 bougies, dans la fourchette 250-500 demandee) -- atr_14 reflete
    # alors la volatilite RELATIVE A L'EPOQUE RECENTE, pas a toute
    # l'histoire du dataset. Le nom de colonne reste "atr_14" (rien d'autre
    # a changer en aval -- FEATURE_COLUMNS, normalize_features...).
    window = 300
    roll_mean = df["atr_14"].rolling(window, min_periods=window // 3).mean()
    roll_std = df["atr_14"].rolling(window, min_periods=window // 3).std()
    df["atr_14"] = (df["atr_14"] - roll_mean) / (roll_std + 1e-8)
    df = df.dropna().reset_index(drop=True)
    return df


feat.add_technical_features = _patched_add_technical_features
# autonomous_agent.py fait `from src.features import add_technical_features` a
# l'IMPORT -- patcher l'attribut du module src.features seul ne suffit pas,
# il faut aussi patcher la reference deja importee dans autonomous_agent.
import autonomous_agent
autonomous_agent.add_technical_features = _patched_add_technical_features
log.info("Correctif atr_14 (rolling z-score, fenetre=300) actif pour ce pilote.")


# ============================================================
# 2) JOURNALISATION ENTROPIE/APPROX_KL/CLIP_FRACTION -- mesure seule,
#    aucun changement de comportement. Actif dans LES DEUX phases.
# ============================================================
from stable_baselines3.common.logger import Logger, KVWriter


class _CapturingWriter(KVWriter):
    def __init__(self):
        self.captured = []

    def write(self, key_values, key_excluded, step=0):
        self.captured.append(dict(key_values))

    def close(self):
        pass


def _train_with_entropy_capture(agent, total_timesteps, label, generation):
    writer = _CapturingWriter()
    agent.model.set_logger(Logger(folder=None, output_formats=[writer]))
    agent.learn(total_timesteps, label=label)
    if writer.captured:
        last = writer.captured[-1]
        def _to_float(v):
            return float(v) if v is not None else None
        record = {
            "generation": generation,
            "entropy_loss": _to_float(last.get("train/entropy_loss")),
            "approx_kl": _to_float(last.get("train/approx_kl")),
            "clip_fraction": _to_float(last.get("train/clip_fraction")),
            "n_dumps_this_candidate": len(writer.captured),
        }
        try:
            os.makedirs(os.path.dirname(ENTROPY_LOG_PATH), exist_ok=True)
            with open(ENTROPY_LOG_PATH, "a", encoding="utf-8") as f:
                f.write(json.dumps(record) + "\n")
        except Exception as e:
            log.warning(f"Echec ecriture entropy_log.jsonl ({type(e).__name__}: {e}) -- non bloquant.")
    else:
        log.warning("Aucune metrique SB3 capturee pour ce candidat (writer.captured vide).")


# ============================================================
# 3) ESPACE DE MUTATION ELARGI -- net_arch / lstm_hidden_size / window_size
#    -- actif UNIQUEMENT en phase "expanded".
# ============================================================
NET_ARCH_CHOICES = [[128, 128], [256, 256], [256, 256, 128]]
LSTM_HIDDEN_CHOICES = [64, 128, 256]
WINDOW_SIZE_CHOICES = [30, 50, 75, 100]

_ORIGINAL_mutate_hyperparams = evo.mutate_hyperparams


def _expanded_mutate_hyperparams(hp, scale):
    new_hp = _ORIGINAL_mutate_hyperparams(hp, scale)
    # Choix CATEGORIELS parmi un ensemble raisonnable (pas de valeurs
    # libres) -- probabilite de mutation proportionnelle a `scale` (a
    # amplitude minimale, on reste le plus souvent sur le centre actuel).
    p_mutate_structural = min(1.0, 0.3 * scale)
    if random.random() < p_mutate_structural:
        new_hp["net_arch"] = list(random.choice(NET_ARCH_CHOICES))
    if random.random() < p_mutate_structural:
        new_hp["lstm_hidden_size"] = random.choice(LSTM_HIDDEN_CHOICES)
    if random.random() < p_mutate_structural:
        new_hp["window_size"] = random.choice(WINDOW_SIZE_CHOICES)
    return new_hp


if args.phase == "expanded":
    evo.mutate_hyperparams = _expanded_mutate_hyperparams
    log.info(f"Espace de mutation ELARGI actif : net_arch parmi {NET_ARCH_CHOICES}, "
             f"lstm_hidden_size parmi {LSTM_HIDDEN_CHOICES}, window_size parmi {WINDOW_SIZE_CHOICES}.")
else:
    log.info("Phase 'atr_fix' : espace de mutation INCHANGE (5 memes hyperparametres qu'en production).")


# ============================================================
# _train_candidate_worker PATCHE : gere un window_size PAR CANDIDAT (lu
# dans hyperparams si present, sinon celui de env_kwargs comme avant) --
# necessaire seulement parce que window_size est un parametre d'ENV, pas
# d'agent, contrairement a net_arch/lstm_hidden_size qui passent deja par
# hyperparams sans rien à changer côté worker. Le warm-start reste protégé
# par le try/except deja present dans TradingAgent._warm_start (voir
# src/agent.py) -- un changement de dimension y echoue proprement et
# repart a neuf pour CETTE variante seulement, comportement EXISTANT,
# verifie, pas ajoute ici.
# ============================================================
def _patched_train_candidate_worker(spec: dict) -> dict:
    torch_threads = spec.get("torch_threads")
    if torch_threads:
        import torch
        torch.set_num_threads(max(1, torch_threads))
        try:
            torch.set_num_interop_threads(max(1, torch_threads))
        except RuntimeError:
            pass

    label = spec.get("label")
    hp = spec["hyperparams"]

    env_kwargs = dict(spec["env_kwargs"])
    if "window_size" in hp and hp["window_size"] != env_kwargs.get("window_size"):
        log.info(f"{label} : window_size candidat = {hp['window_size']} "
                 f"(different du defaut {env_kwargs.get('window_size')}) -- env reconstruit en consequence.")
        env_kwargs["window_size"] = hp["window_size"]

    env = TradingEnv(spec["train_df"], **env_kwargs)
    agent = TradingAgent(env, hp, warm_start_model_path=spec["warm_start_path"])
    _train_with_entropy_capture(agent, spec["timesteps"], label, spec["generation"])

    stress_seed = zlib.crc32(spec.get("style", "").encode()) & 0x7FFFFFFF
    metrics = evaluate_agent_walkforward(agent, spec["val_df"], env_kwargs,
                                          n_windows=spec.get("eval_windows", 3),
                                          stress_test=spec.get("stress_test", False),
                                          stress_seed=stress_seed)
    score = metrics["sharpe"] - 2.0 * metrics["max_drawdown"]

    eval_env = TradingEnv(spec["val_df"], **env_kwargs)
    eval_env = run_episode(agent, eval_env)
    trades = [{"entry": t["entry"], "exit": t["exit"], "position": t["position"],
               "pnl_pct": t["pnl_pct"], "context": t["context"]} for t in eval_env.trade_log]

    agent.save(spec["out_path"])
    return {
        "score": score, "metrics": metrics, "model_path": spec["out_path"],
        "trades": trades, "max_drawdown": eval_env.max_drawdown,
        "generation": spec["generation"], "style": spec["style"], "slot": spec["slot"],
        "feature_columns": env_kwargs["feature_columns"],
        "context_timeframes": spec["context_timeframes"],
        "hyperparams": hp,
    }


ct._train_candidate_worker = _patched_train_candidate_worker


# ============================================================
# Config isolee + lancement (memes garde-fous que le pilote v2 : pool M15
# seul, CPU modeste, memoire episodique separee, notifications coupees).
# ============================================================
from autonomous_agent import make_data_provider
from src.continuous_trainer import ContinuousEvolutionTrainer

with open("config/autonomous.yaml", encoding="utf-8") as f:
    cfg = yaml.safe_load(f)
cfg = copy.deepcopy(cfg)
cfg["data"]["timeframe_pool"] = ["M15"]
cfg["environment"]["reward_type"] = "risk_adjusted_v2"
cfg["memory"]["db_path"] = f"data/episodic_memory_pilot_m15_v3_{args.phase}.sqlite"
cfg["continuous"]["parallel_workers"] = 1
# BUG CORRIGE (17/09) : avec candidates_per_cycle=1, la boucle de
# continuous_trainer.py ("for i in range(n_per_style): hp = slot_center if
# i == 0 else mutate_hyperparams(...)") n'atteint JAMAIS i>=1 -- donc
# JAMAIS mutate_hyperparams, donc JAMAIS _expanded_mutate_hyperparams. La
# phase "expanded" tournerait sans jamais muter net_arch/lstm_hidden_size/
# window_size, silencieusement identique a atr_fix. Ce constat s'applique
# aussi a atr_fix (qui n'a donc jamais mute ses 5 hyperparametres non plus
# -- son evolution jusqu'ici vient uniquement de l'entrainement continu par
# warm-start, pas d'une recherche evolutive). Valeur alignee sur la config
# de production (continuous.candidates_per_cycle par defaut) pour "expanded"
# uniquement -- atr_fix garde 1 (comportement etabli inchange s'il redemarre).
cfg["continuous"]["candidates_per_cycle"] = 3 if args.phase == "expanded" else 1
cfg["continuous"]["cpu_target_threads"] = 2
cfg["notifications"]["enabled"] = False

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
    learn_stop_loss=cfg["agent"].get("learn_stop_loss", False),
    stop_loss_buckets=cfg["agent"].get("stop_loss_buckets"),
    stop_loss_range=tuple(cfg["agent"].get("stop_loss_range", (0.003, 0.06))),
    giveback_ratio_threshold=0.4, giveback_penalty_coef=0.03,
    friction_window=12, friction_penalty_coef=0.01,
)

log.info(f"=== Pilote M15 v3 / phase '{args.phase}' -- isole dans '{PILOT_ROOT}/', "
         f"jamais lu par la demo en production. ===")

get_data_fn, _ = make_data_provider(cfg)
trainer = ContinuousEvolutionTrainer(cfg, get_data_fn, ["M15"], env_kwargs)
trainer.run_forever(cycle_interval_seconds=cfg["continuous"].get("cycle_interval_seconds", 60))
