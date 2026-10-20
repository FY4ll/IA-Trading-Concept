"""Contrôle rapide d'activité (06/10/2026) : nombre de trades et répartition des décisions de chaque point de
sauvegarde des entraînements longs, sur les 12 000 dernières bougies de la validation or (sans stress).
    python scripts/activity_check.py AUREXIS        (cwd = code/)"""
import glob, json, os, sys, time
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
os.chdir(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import numpy as np, yaml


def main(style):
    cfg = yaml.safe_load(open("../run_config_A.yaml", encoding="utf-8"))
    from src.risk_profile import apply_risk_profile
    apply_risk_profile(cfg)
    import autonomous_agent as aa
    from src.episodic_memory import EpisodicMemory
    from src.trading_env import TradingEnv
    from src.agent import TradingAgent
    from src.backtester import run_episode
    sys.path.insert(0, "scripts")
    from train_long import env_kwargs_for
    get_data, _ = aa.make_data_provider(cfg)
    _, val, _, cols, _ = get_data((cfg["data"].get("dataset_alias") or {}).get(style, style))
    val = val.iloc[-12000:].reset_index(drop=True)
    mem = EpisodicMemory(cfg["memory"]["db_path"])
    kw = env_kwargs_for(cfg, style, cols, mem.snapshot(dim=len(cols), sources=["backtest"]))
    paths = [("AUREX (référence)", "models/champion_AUREX/agent")]
    only = sys.argv[2].split(",") if len(sys.argv) > 2 else None
    for d in sorted(glob.glob(f"models/long_{style}/r*")):
        if only and os.path.basename(d) not in only:
            continue
        cks = sorted(glob.glob(os.path.join(d, "ckpt_*.zip")), key=lambda p: int(p.split("_")[-1][:-4]))
        paths += [(f"{os.path.basename(d)}/{os.path.basename(c)[:-4]}", c[:-4]) for c in cks]
    for name, p in paths:
        env = TradingEnv(val, **kw)
        agent = TradingAgent.load(p, env, {"algo": "PPO"})
        env = run_episode(agent, env)
        eq = np.asarray(env.equity_curve)
        print(f"{name:28s} trades {len(env.trade_log):4d}  rendement {eq[-1] / eq[0] - 1:+.2%}", flush=True)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "AUREXIS")
