"""
lockbox_analysis.py
====================
Analyse hors ligne d'un champion (05/10/2026, vision "Autonomous Trader V1",
§40, §42, §43, §76) : rejoue le modèle bougie par bougie sur une période
(lockbox, ou la période d'AVANT la lockbox, jamais vue par la porte), en
enregistrant sa position à chaque pas, pour :
  - reconstruire les trades (entrée, sortie, direction, rendement net) ;
  - les ventiler par régime / classe de volatilité AU MOMENT DE L'ENTRÉE ;
  - tester un FILTRE D'OUVERTURE exactement comme il s'appliquerait en live
    (src/market_gate.py : une ouverture bloquée devient "rester à plat", un
    retournement bloqué devient une simple clôture), en rejouant le modèle
    avec le filtre -- pas un simple retrait de trades après coup.
Ne sert QU'À la recherche : aucune décision live ne lit ce module.
"""
from __future__ import annotations
import json
import os

import numpy as np
import pandas as pd

from src.style_utils import base_timeframe


def load_champion(style: str, model_dir: str | None = None):
    mdir = model_dir or os.path.join("models", f"champion_{style}")
    with open(os.path.join(mdir, "meta.json"), encoding="utf-8") as f:
        meta = json.load(f)
    with open(os.path.join(mdir, "norm_stats.json"), encoding="utf-8") as f:
        stats = json.load(f)
    return meta, stats, os.path.join(mdir, "agent")


def _flat_action(action, env):
    """Même action mais direction 'plat' (index 1 en discret, 0.0 en continu)."""
    a = np.array(action, copy=True)
    flat = a.reshape(-1)
    if getattr(env, "continuous_action", False):
        flat[0] = 0.0
    else:
        flat[0] = 1
    return a if a.ndim else flat[0]


def _direction_of_action(action, env) -> int:
    a = np.asarray(action).reshape(-1)
    if getattr(env, "continuous_action", False):
        v = float(a[0])
        return 0 if abs(v) < 1e-9 else (1 if v > 0 else -1)
    return {0: -1, 1: 0, 2: 1}[int(a[0])]


def replay(style: str, cfg: dict, period: str = "lockbox", block_mask: np.ndarray | None = None,
           model_dir: str | None = None, max_bars: int | None = None, cost_multiplier: float = 1.0) -> dict:
    """Rejoue le champion de `style` sur `period` ("lockbox" ou "pre_lockbox" = les dernières
    bougies AVANT la lockbox, même longueur que la lockbox par défaut). `block_mask[i]` = True
    interdit d'OUVRIR à la bougie i (filtre live simulé)."""
    from src.lockbox_gate import build_eval_frames, eval_env_kwargs
    from src.features import normalize_features
    from src.trading_env import TradingEnv
    from src.agent import TradingAgent

    meta, stats, model_path = load_champion(style, model_dir)
    visible, lock, _ = build_eval_frames(style, cfg, meta)
    if period == "lockbox":
        raw = lock
    else:
        n = max_bars or len(lock)
        raw = visible.iloc[-n:]
    raw = raw.reset_index(drop=True)
    cols = meta["feature_columns"]
    dfn, _ = normalize_features(raw, stats={k: tuple(v) for k, v in stats.items()}, columns=cols)
    kw = eval_env_kwargs(style, cfg, meta)
    if cost_multiplier != 1.0:
        kw["transaction_cost"] = kw["transaction_cost"] * cost_multiplier
    env = TradingEnv(dfn, feature_columns=cols, style=style, **kw)
    agent = TradingAgent.load(model_path, env, {"algo": meta.get("algo", "PPO")})

    obs, _ = env.reset()
    steps, pos_after, eq_before, eq_after = [], [], [], []
    n_blocked = 0
    while True:
        i = env.current_step
        action = agent.predict(obs, deterministic=True)
        if block_mask is not None and i < len(block_mask) and block_mask[i]:
            cur = 0 if abs(env.position) < 1e-9 else (1 if env.position > 0 else -1)
            d = _direction_of_action(action, env)
            if d != 0 and d != cur:
                action = _flat_action(action, env)
                n_blocked += 1
        e0 = env.equity_curve[-1]
        obs, _, term, trunc, _ = env.step(action)
        steps.append(i)
        pos_after.append(float(env.position))
        eq_before.append(e0)
        eq_after.append(env.equity_curve[-1])
        if term or trunc:
            break
    return {"style": style, "period": period, "raw": raw, "steps": np.array(steps),
            "positions": np.array(pos_after), "eq_before": np.array(eq_before),
            "eq_after": np.array(eq_after), "equity_curve": np.array(env.equity_curve),
            "n_blocked": n_blocked, "meta": meta}


def extract_trades(rep: dict) -> list[dict]:
    """Segments de position non nulle -> trades (indice de la bougie de DÉCISION d'entrée)."""
    trades, cur, entry = [], 0, None
    for k, (i, p) in enumerate(zip(rep["steps"], rep["positions"])):
        d = 0 if abs(p) < 1e-9 else (1 if p > 0 else -1)
        if d != cur:
            if cur != 0 and entry is not None:
                trades.append({"entry_bar": entry[0], "exit_bar": int(i), "direction": cur,
                               "ret": float(rep["eq_after"][k] / entry[1] - 1)})
            entry = (int(i), rep["eq_before"][k]) if d != 0 else None
            cur = d
    if cur != 0 and entry is not None:
        trades.append({"entry_bar": entry[0], "exit_bar": int(rep["steps"][-1]), "direction": cur,
                       "ret": float(rep["eq_after"][-1] / entry[1] - 1), "open_at_end": True})
    return trades


def summary(rep: dict) -> dict:
    from src.ftmo_metrics import daily_returns, prop_firm_summary
    eq = rep["equity_curve"]
    r = np.diff(eq) / eq[:-1]
    sharpe = float(r.mean() / r.std() * np.sqrt(252 * 24)) if r.std() > 1e-12 else 0.0
    dd = float((eq / np.maximum.accumulate(eq) - 1).min())
    trades = extract_trades(rep)
    rets = np.array([t["ret"] for t in trades]) if trades else np.array([])
    out = {"total_return": float(eq[-1] / eq[0] - 1), "sharpe": sharpe, "max_drawdown": -dd,
           "n_trades": len(trades), "win_rate": float((rets > 0).mean()) if len(rets) else None,
           "avg_trade": float(rets.mean()) if len(rets) else None, "n_blocked": rep.get("n_blocked", 0)}
    if "time" in rep["raw"].columns:
        out["prop_firm"] = prop_firm_summary(daily_returns(eq, rep["raw"]["time"]).to_numpy(), n_sims=2000)
    return out


def by_regime(rep: dict, regimes: pd.DataFrame) -> dict:
    """Résultats des trades ventilés par régime et par classe de volatilité à l'entrée."""
    trades = extract_trades(rep)
    out = {"regime": {}, "vol_class": {}}
    for key in ("regime", "vol_class"):
        groups: dict[str, list] = {}
        for t in trades:
            groups.setdefault(str(regimes[key].iloc[t["entry_bar"]]), []).append(t["ret"])
        for g, rs in groups.items():
            a = np.array(rs)
            out[key][g] = {"n": int(len(a)), "win_rate": float((a > 0).mean()), "avg_ret": float(a.mean()),
                           "sum_ret": float(a.sum())}
    share = regimes["vol_class"].value_counts(normalize=True).to_dict()
    out["time_share_vol_class"] = {str(k): float(v) for k, v in share.items()}
    out["time_share_regime"] = {str(k): float(v) for k, v in regimes["regime"].value_counts(normalize=True).to_dict().items()}
    return out
