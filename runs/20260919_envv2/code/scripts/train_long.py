"""
ENTRAÎNEMENT LONG (06/10/2026) : un seul agent, des centaines de milliers de pas d'affilée, au lieu des
ajustements de 18 000 pas des cycles d'évolution -- nécessaire pour qu'AUREXIS apprenne vraiment de ses
5 marchés. Même données, même environnement, même mémoire épisodique, mêmes réglages qu'un candidat du cycle.
Point de sauvegarde tous les --ckpt pas (models/long_<style>/<run>/ckpt_<pas>.zip).

    python scripts/train_long.py --style AUREXIS --steps 600000 --run r1 --lr 0.00005 --seed 1 --threads 3
"""
import argparse, json, os, sys, time
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
os.chdir(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import yaml


def env_kwargs_for(cfg: dict, style: str, cols: list, memory_snapshot) -> dict:
    """Mêmes kwargs qu'un candidat du cycle (autonomous_agent.main + continuous_trainer.run_one_cycle)."""
    e, ag = cfg["environment"], cfg["agent"]
    kw = dict(window_size=e["window_size"], initial_balance=e["initial_balance"], transaction_cost=e["transaction_cost"],
              reward_type=e["reward_type"], drawdown_penalty=e["drawdown_penalty"], max_position=e["max_position"],
              continuous_action=False, spread_volatility_multiplier=e.get("spread_volatility_multiplier", 1.0),
              learn_stop_loss=ag.get("learn_stop_loss", False), stop_loss_buckets=ag.get("stop_loss_buckets"),
              stop_loss_range=tuple(ag.get("stop_loss_range", (0.003, 0.06))), atr_stop_loss=ag.get("atr_stop_loss", True),
              session_spread_enabled=e.get("session_spread_enabled", True),
              session_spread_multipliers=e.get("session_spread_multipliers"),
              inactivity_penalty_coef=e.get("inactivity_penalty_coef", 0.0))
    from src.live_data_feed import read_cached_spread
    spread = read_cached_spread(max_age_hours=cfg.get("data", {}).get("live_feed_spread_max_age_hours", 6.0))
    if spread is not None:
        kw["transaction_cost"] = spread
    kw.update(e.get("style_overrides", {}).get(style, {}))
    kw.update(feature_columns=cols, memory_snapshot=memory_snapshot,
              memory_top_k=cfg.get("memory", {}).get("similarity_top_k", 5), style=style)
    return kw


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--style", default="AUREXIS")
    ap.add_argument("--steps", type=int, default=600000)
    ap.add_argument("--ckpt", type=int, default=100000)
    ap.add_argument("--run", default="r1")
    ap.add_argument("--lr", type=float, default=None)
    ap.add_argument("--ent", type=float, default=None)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--threads", type=int, default=3)
    ap.add_argument("--warm", default=None, help="modèle de départ (défaut : champion du style)")
    ap.add_argument("--out-style", default=None, help="dossier models/long_<...> (défaut : le style)")
    ap.add_argument("--dd", type=float, default=None, help="pénalité de drawdown de la RÉCOMPENSE d'entraînement")
    ap.add_argument("--reward", default=None, help="type de récompense d'entraînement (ex: pnl)")
    ap.add_argument("--inact", type=float, default=None, help="pénalité d'inactivité par bougie à plat")
    a = ap.parse_args()

    import torch, numpy as np
    torch.set_num_threads(a.threads)
    torch.manual_seed(a.seed); np.random.seed(a.seed)
    cfg = yaml.safe_load(open("../run_config_A.yaml", encoding="utf-8"))
    from src.risk_profile import apply_risk_profile
    apply_risk_profile(cfg)
    import autonomous_agent as aa
    from src.episodic_memory import EpisodicMemory
    from src.trading_env import TradingEnv, ENV_VERSION
    from src.agent import TradingAgent

    out = os.path.join("models", f"long_{a.out_style or a.style}", a.run)
    os.makedirs(out, exist_ok=True)
    status = os.path.join(out, "status.txt")

    def note(msg):
        line = f"{time.strftime('%Y-%m-%d %H:%M:%S')} {msg}"
        print(line, flush=True)
        open(status, "a", encoding="utf-8").write(line + "\n")

    t0 = time.time()
    get_data, _ = aa.make_data_provider(cfg)
    train_df, val_df, stats, cols, ctx = get_data(a.style)
    mem_cfg = cfg.get("memory", {})
    memory = EpisodicMemory(mem_cfg["db_path"], mem_cfg.get("max_episodes", 20000))
    snap = memory.snapshot(dim=len(cols), sources=["backtest"])
    memory.close()
    kw = env_kwargs_for(cfg, a.style, cols, snap)
    # 06/10/2026 : récompense d'ENTRAÎNEMENT seulement (le jugement -- validation, lockbox -- ne change pas)
    if a.dd is not None:
        kw["drawdown_penalty"] = a.dd
    if a.inact is not None:
        kw["inactivity_penalty_coef"] = a.inact
    if a.reward is not None:
        kw["reward_type"] = a.reward
    env = TradingEnv(train_df, randomize_start=True, **kw)
    env.reset(seed=a.seed)
    hp = {**cfg["agent"], **(cfg["agent"].get("style_overrides", {}).get(a.style) or {})}
    hp.pop("style_overrides", None)
    if a.lr is not None:
        hp["learning_rate"] = a.lr
    if a.ent is not None:
        hp["ent_coef"] = a.ent
    warm = a.warm or os.path.join("models", f"champion_{a.style}", "agent")
    agent = TradingAgent(env, hp, warm_start_model_path=warm)
    json.dump({"style": a.style, "feature_columns": cols, "context_timeframes": ctx, "algo": hp.get("algo", "PPO"),
               "hyperparams": {k: v for k, v in hp.items() if isinstance(v, (int, float, str, bool))},
               "warm_start": warm, "env_version": ENV_VERSION, "reward_type": kw.get("reward_type"), "drawdown_penalty": kw.get("drawdown_penalty"), "inactivity_penalty_coef": kw.get("inactivity_penalty_coef"), "train_bars": len(train_df), "val_bars": len(val_df), "seed": a.seed},
              open(os.path.join(out, "meta.json"), "w", encoding="utf-8"), indent=1, default=str)
    json.dump({k: list(v) for k, v in stats.items()}, open(os.path.join(out, "norm_stats.json"), "w", encoding="utf-8"))
    note(f"départ : {len(train_df)} bougies d'entraînement, lr={hp.get('learning_rate')}, ent={hp.get('ent_coef')}, "
         f"départ={warm} ({time.time() - t0:.0f}s de préparation)")
    done = 0
    while done < a.steps:
        n = min(a.ckpt, a.steps - done)
        agent.model.learn(total_timesteps=n, reset_num_timesteps=False, progress_bar=False)
        done += n
        agent.save(os.path.join(out, f"ckpt_{done}"))
        note(f"{done}/{a.steps} pas -- point de sauvegarde ckpt_{done} ({(time.time() - t0) / 3600:.2f} h)")
    note("FIN")


if __name__ == "__main__":
    main()
