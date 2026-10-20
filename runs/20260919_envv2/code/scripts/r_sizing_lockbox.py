# Usage : python scripts/r_sizing_lockbox.py AUREX   (cwd = code/)
"""AUREX sur la lockbox, rejoué avec le dimensionnement LIVE (risque fixe par trade) au lieu de l'exposition 1x."""
import json, os, sys, time
CODE = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, CODE); os.chdir(CODE)
import numpy as np, pandas as pd, yaml
from src.lockbox_gate import build_eval_frames, eval_env_kwargs
from src.features import normalize_features
from src.trading_env import TradingEnv
from src.agent import TradingAgent
from src.ftmo_metrics import daily_returns, prop_firm_summary

style = sys.argv[1] if len(sys.argv) > 1 else "AUREX"
OUT = os.path.join("reports", f"r_sizing_{style}.json")
cfg = yaml.safe_load(open("../run_config_A.yaml", encoding="utf-8"))
d = f"models/champion_{style}"
meta = json.load(open(f"{d}/meta.json", encoding="utf-8"))
stats = json.load(open(f"{d}/norm_stats.json", encoding="utf-8"))
t0 = time.time()
_, lock, start = build_eval_frames(style, cfg, meta)
cols = meta["feature_columns"]
dfn, _ = normalize_features(lock, stats={k: tuple(v) for k, v in stats.items()}, columns=cols)
kw = eval_env_kwargs(style, cfg, meta)
kw["risk_sizing_pct"] = 0.0   # simulation 1x ici : la conversion au risque est faite plus bas (sinon appliquée deux fois)
env = TradingEnv(dfn, feature_columns=cols, style=style, **kw)
agent = TradingAgent.load(f"{d}/agent", env, {"algo": meta.get("algo", "PPO")})
print("data ready", len(dfn), f"{time.time()-t0:.0f}s", flush=True)

obs, _ = env.reset()
lstm_state, start_flag = None, np.ones((1,), dtype=bool)
stop_frac = []          # distance du stop (fraction du prix) de la position détenue APRÈS chaque pas
eq = [env.equity_curve[-1]]
trade_r = []
orig_log = env._log_trade
def _log(position, entry, exit_, pnl, stopped_out):
    sf = (env._initial_risk / entry) if (env._initial_risk and entry) else None
    trade_r.append((pnl / sf) if sf else None)
    return orig_log(position, entry, exit_, pnl, stopped_out)
env._log_trade = _log
done = False
while not done:
    action = agent.predict(obs, deterministic=True)
    obs, reward, term, trunc, info = env.step(action)
    done = term or trunc
    sf = (env._initial_risk / env.entry_price) if (env.position != 0 and env._initial_risk and env.entry_price) else 0.0
    stop_frac.append(sf)
    eq.append(env.equity_curve[-1])
print("episode done", f"{time.time()-t0:.0f}s", flush=True)

eq = np.asarray(env.equity_curve, dtype=float)
r = np.diff(eq) / eq[:-1]
sf = np.asarray(stop_frac[:len(r)], dtype=float)
held_sf = np.concatenate([[0.0], sf[:-1]])        # position détenue pendant la bougie t = décidée à t-1
times = env.df["time"].iloc[len(env.df) - len(eq):].reset_index(drop=True) if "time" in env.df.columns else None
res = {"style": style, "generation": meta.get("generation"), "lockbox_start": str(start.date()),
       "sim_1x": {"return": float(eq[-1] / eq[0] - 1), "max_dd": float(-(eq / np.maximum.accumulate(eq) - 1).min())}}
valid_r = np.array([x for x in trade_r if x is not None and np.isfinite(x)])
res["trades"] = {"n": len(trade_r), "n_with_stop": int(len(valid_r)),
                 "win_rate": float((valid_r > 0).mean()) if len(valid_r) else None,
                 "avg_R": float(valid_r.mean()) if len(valid_r) else None,
                 "median_R": float(np.median(valid_r)) if len(valid_r) else None,
                 "stop_pct_median": float(np.median(sf[sf > 0])) if (sf > 0).any() else None}
for risk in (0.0025, 0.005, 0.01):
    lev = np.where(held_sf > 0, risk / np.maximum(held_sf, 1e-6), 1.0)
    lev = np.minimum(lev, 30.0)                  # levier max d'un compte FTMO sur l'or ~ 1:30
    eq_r = np.cumprod(np.concatenate([[1.0], 1 + lev * r]))
    item = {"return": float(eq_r[-1] - 1), "max_dd": float(-(eq_r / np.maximum.accumulate(eq_r) - 1).min()),
            "lev_median": float(np.median(lev[held_sf > 0])) if (held_sf > 0).any() else None}
    if times is not None and len(times) == len(eq_r):
        dr = daily_returns(eq_r, times).to_numpy()
        item["worst_day"] = float(dr.min())
        item["months"] = float(len(dr) / 21)
        item["prop_firm"] = prop_firm_summary(dr)
    res[f"risk_{risk}"] = item
    print(risk, {k: v for k, v in item.items() if k != "prop_firm"}, (item.get("prop_firm") or {}).get("challenge_pass"), flush=True)
print(json.dumps(res["trades"]), flush=True)
json.dump(res, open(OUT, "w"), indent=1, default=str)
print("total", f"{time.time()-t0:.0f}s")
