"""
Pilote ISOLE : entraine le style M15 UNIQUEMENT avec reward_type=
"risk_adjusted_v2" (giveback ratio + friction de frequence, calibres le
18/09 -- voir trading_env.py::_compute_reward), dans son PROPRE arbre de
repertoires, completement separe de la production.

GARDE-FOUS D'ISOLEMENT (demande explicite de l'utilisateur) :
  - Ne touche JAMAIS models/ (repertoire de production) -- tout est ecrit
    dans models_pilot_m15_v2/, via un monkeypatch des constantes de chemin
    de src.continuous_trainer AVANT toute instanciation.
  - N'entraine QUE M15 (data.timeframe_pool=["M15"]) -- D1/H4/H1/M30
    continuent de tourner normalement dans le processus de production,
    totalement independant de celui-ci (processus Python separe).
  - Memoire episodique et fichier de progression separes -- aucune
    ecriture partagee avec le processus de production.
  - Ce pilote n'est JAMAIS lu par demo_trader.py (qui ne lit que
    models/demo_champion/, jamais models_pilot_m15_v2/) -- ne peut donc
    jamais trader en reel, meme accidentellement.

Lancement : python scripts/pilot_m15_v2.py
"""
import sys
import os
import copy
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.chdir(Path(__file__).resolve().parent.parent)

import yaml
import src.continuous_trainer as ct

# --- Isolation totale : patch AVANT toute instanciation de ContinuousEvolutionTrainer ---
PILOT_ROOT = "models_pilot_m15_v2"
ct.MODELS_ROOT = PILOT_ROOT
ct.DEMO_DIR = os.path.join(PILOT_ROOT, "demo_champion")
ct.DEMO_MODEL = os.path.join(ct.DEMO_DIR, "agent")
ct.DEMO_META = os.path.join(ct.DEMO_DIR, "meta.json")
ct.DEMO_STATS = os.path.join(ct.DEMO_DIR, "norm_stats.json")
ct.CANDIDATES_TMP_DIR = os.path.join(PILOT_ROOT, "_tmp_candidates")
ct.PROGRESS_FILE = os.path.join(PILOT_ROOT, "_progress.json")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [PILOTE-M15-v2] [%(name)s] %(message)s")
log = logging.getLogger("pilot_m15_v2")

from autonomous_agent import make_data_provider
from src.continuous_trainer import ContinuousEvolutionTrainer

with open("config/autonomous.yaml", encoding="utf-8") as f:
    cfg = yaml.safe_load(f)

# Copie isolee : la config de production sur disque n'est jamais modifiee.
cfg = copy.deepcopy(cfg)
cfg["data"]["timeframe_pool"] = ["M15"]
cfg["environment"]["reward_type"] = "risk_adjusted_v2"
# Memoire episodique SEPAREE -- aucune ecriture partagee avec le process de prod.
cfg["memory"]["db_path"] = "data/episodic_memory_pilot_m15.sqlite"
# CPU MODESTE (demande implicite : ne jamais gener la production, qui tourne
# deja avec 6 workers sur cette machine 6 coeurs/12 threads) -- ce pilote
# reste volontairement petit (1 candidat, 1 processus) plutot que de faire
# concurrence aux 4 autres styles + la boucle de demo pour le CPU.
cfg["continuous"]["parallel_workers"] = 1
cfg["continuous"]["candidates_per_cycle"] = 1
cfg["continuous"]["cpu_target_threads"] = 2
# Notifications COUPÉES pour ce pilote -- sinon ses alertes de cycle se
# mélangent avec celles de la production sur le même topic ntfy, sans
# distinction claire pour l'utilisateur. Le suivi de ce pilote se fait via
# cette conversation, pas par notification push.
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
    # Coefficients CALIBRES le 18/09 sur le champion M15 existant (voir
    # trading_env.py) -- explicites ici pour que le pilote reste traçable
    # meme si les defauts de TradingEnv changent plus tard.
    giveback_ratio_threshold=0.4,
    giveback_penalty_coef=0.03,
    friction_window=12,
    friction_penalty_coef=0.01,
)

log.info(f"=== Pilote M15 / risk_adjusted_v2 -- isole dans '{PILOT_ROOT}/', "
         f"memoire episodique separee, JAMAIS lu par la demo en production. ===")

get_data_fn, _ = make_data_provider(cfg)
trainer = ContinuousEvolutionTrainer(cfg, get_data_fn, ["M15"], env_kwargs)
trainer.run_forever(cycle_interval_seconds=cfg["continuous"].get("cycle_interval_seconds", 60))
