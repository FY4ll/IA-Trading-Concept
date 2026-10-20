"""
Pilote v4 -- ISOLE (comme v2/v3) : corrige la solution DEGENERE trouvee par
le pilote v3 atr_fix (reward_type="risk_adjusted_v2") -- 72.5% de sorties
au stop-loss (4.4% en production), une fenetre walk-forward a 1 seul trade
sur 5563 pas. Cause identifiee : la penalite de friction punissait TOUT
changement de position, y compris celui qui prend un profit et revient a
plat -- l'agent avait appris a ne quasiment plus jamais agir.

Deux correctifs, tous deux dans reward_type="risk_adjusted_v3" (voir
src/trading_env.py -- "risk_adjusted" et "risk_adjusted_v2" restent
INCHANGES, v3 est un bloc separe, point de comparaison stable garanti) :
  1. FRICTION ASYMETRIQUE : un retour a FLAT ne compte plus comme un
     evenement de friction (gratuit). Seules restent "friction" :
     l'ouverture depuis plat, et le retournement direct (long<->short).
  2. GIVEBACK RENFORCE : giveback_ratio_threshold 0.4->0.25,
     giveback_penalty_coef 0.03->0.15 -- sortir etant devenu gratuit,
     c'est desormais le SEUL levier qui rend couteux le fait de laisser
     filer un profit jusqu'au stop plutot que de sortir dessus.

Repart du champion atr_fix (gen 114, warm-start) plutot que de zero --
isole l'effet du SEUL changement de formule de recompense, sans melanger
avec l'effet de l'espace de mutation elargi (pilote "expanded", experience
separee). Meme choix qu'atr_fix : mutate_hyperparams INCHANGE (les 5 memes
hyperparametres, jamais l'architecture) -- garde la comparaison a une seule
variable (la formule de recompense), pas deux.

ISOLATION TOTALE (comme v2/v3) : aucun fichier src/*.py modifie sur disque
au sens "different du disque" -- trading_env.py a bien un nouveau bloc
risk_adjusted_v3, mais c'est un AJOUT permanent au projet (demande
explicite), pas un monkeypatch ephemere comme le correctif atr_14
ci-dessous (qui, lui, reste local a ce processus). Ecrit dans son PROPRE
repertoire, jamais models/.

Lancement : python scripts/pilot_m15_v4.py
"""
import sys
import os
import copy
import logging
import json
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.chdir(Path(__file__).resolve().parent.parent)

import yaml
import src.continuous_trainer as ct
import src.features as feat
from src.trading_env import TradingEnv
from src.agent import TradingAgent
from src.backtester import evaluate_agent_walkforward, run_episode

PILOT_ROOT = "models_pilot_m15_v4"
ct.MODELS_ROOT = PILOT_ROOT
ct.DEMO_DIR = os.path.join(PILOT_ROOT, "demo_champion")
ct.DEMO_MODEL = os.path.join(ct.DEMO_DIR, "agent")
ct.DEMO_META = os.path.join(ct.DEMO_DIR, "meta.json")
ct.DEMO_STATS = os.path.join(ct.DEMO_DIR, "norm_stats.json")
ct.CANDIDATES_TMP_DIR = os.path.join(PILOT_ROOT, "_tmp_candidates")
ct.PROGRESS_FILE = os.path.join(PILOT_ROOT, "_progress.json")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [PILOTE-M15-v4] [%(name)s] %(message)s")
log = logging.getLogger("pilot_m15_v4")

ENTROPY_LOG_PATH = os.path.join(ct._champion_dir("M15"), "entropy_log.jsonl")


# ============================================================
# CORRECTIF ATR_14 -- IDENTIQUE au pilote v3 (rolling z-score, fenetre=300)
# -- indispensable pour rester compatible avec le warm-start depuis le
# champion atr_fix (memes features, meme espace d'observation).
# ============================================================
_ORIGINAL_add_technical_features = feat.add_technical_features


def _patched_add_technical_features(df, fundamental_feed=None, refresh_fundamental=True):
    df = _ORIGINAL_add_technical_features(df, fundamental_feed, refresh_fundamental)
    window = 300
    roll_mean = df["atr_14"].rolling(window, min_periods=window // 3).mean()
    roll_std = df["atr_14"].rolling(window, min_periods=window // 3).std()
    df["atr_14"] = (df["atr_14"] - roll_mean) / (roll_std + 1e-8)
    df = df.dropna().reset_index(drop=True)
    return df


feat.add_technical_features = _patched_add_technical_features
import autonomous_agent
autonomous_agent.add_technical_features = _patched_add_technical_features
log.info("Correctif atr_14 (rolling z-score, fenetre=300) actif -- identique au pilote atr_fix (compat warm-start).")


# ============================================================
# JOURNALISATION ENTROPIE -- identique aux pilotes v2/v3, mesure seule.
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
# _train_candidate_worker PATCHE -- IDENTIQUE au pilote v3 (gere
# window_size par candidat, mort ici puisque mutate_hyperparams reste
# INCHANGE -- jamais de window_size different du defaut -- mais gardee
# pour rester au plus pres du code deja verifie).
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
# Config isolee + lancement.
# ============================================================
from autonomous_agent import make_data_provider
from src.continuous_trainer import ContinuousEvolutionTrainer

with open("config/autonomous.yaml", encoding="utf-8") as f:
    cfg = yaml.safe_load(f)
cfg = copy.deepcopy(cfg)
cfg["data"]["timeframe_pool"] = ["M15"]
cfg["environment"]["reward_type"] = "risk_adjusted_v3"
cfg["memory"]["db_path"] = "data/episodic_memory_pilot_m15_v4.sqlite"
cfg["continuous"]["parallel_workers"] = 1
# INCHANGE par rapport a atr_fix (1) -- volontaire : ce pilote isole le
# SEUL changement de formule de recompense, mutate_hyperparams() n'est de
# toute facon jamais atteint a candidates_per_cycle=1 (voir le correctif
# du meme bug applique au pilote "expanded", candidates_per_cycle=3 la-bas
# car CE pilote-la doit justement exercer la mutation -- pas celui-ci).
cfg["continuous"]["candidates_per_cycle"] = 1
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
    # GIVEBACK RENFORCE (17/09) : 0.25/0.15 au lieu de 0.4/0.03 sous v2 --
    # voir src/trading_env.py pour le raisonnement complet.
    giveback_ratio_threshold=0.25, giveback_penalty_coef=0.15,
    friction_window=12, friction_penalty_coef=0.01,
)

log.info("=== Pilote M15 v4 -- correctif friction asymetrique + giveback renforce "
         f"(reward_type='risk_adjusted_v3'), isole dans '{PILOT_ROOT}/', jamais lu par la demo en production. ===")

get_data_fn, _ = make_data_provider(cfg)
trainer = ContinuousEvolutionTrainer(cfg, get_data_fn, ["M15"], env_kwargs)
trainer.run_forever(cycle_interval_seconds=cfg["continuous"].get("cycle_interval_seconds", 60))
