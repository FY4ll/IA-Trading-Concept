"""
lockbox_gate.py
================
Porte d'éligibilité démo basée sur le JEU SOUS CLÉ (lockbox) : avant qu'un
candidat ne devienne le champion démo d'un style, il est évalué sur les
données les plus récentes jamais vues à l'entraînement/validation/promotion.
La porte ne peut que REFUSER l'éligibilité (jamais ajouter de score) ; le
lockbox n'est évalué que pour un candidat qui passe déjà `passes_validation`.

Si un champion déjà éligible porte ses métriques lockbox (`meta["lockbox"]`),
le candidat doit aussi le battre (Sharpe) sans être moins actif (trades).
"""
from __future__ import annotations
import logging

import numpy as np

from src.style_utils import base_timeframe

log = logging.getLogger("lockbox_gate")

_MINUTES_PER_BAR = {"M15": 15, "M30": 30, "H1": 60, "H4": 240, "D1": 1440}


def evaluate_on_lockbox(tf: str, cfg: dict, model_path: str, meta: dict, stats: dict) -> dict:
    from src.multi_timeframe import discover_files, build_mtf_dataset
    from src.features import add_technical_features, normalize_features
    from src.data_loader import default_lockbox_start, split_lockbox, load_kaggle_ohlcv_csv
    from src.trading_env import TradingEnv
    from src.agent import TradingAgent
    from src.backtester import run_episode, compute_metrics
    import pandas as pd

    data_cfg = cfg["data"]
    files = discover_files(data_cfg["folder"])
    if data_cfg.get("lockbox_start"):
        lockbox_start = pd.Timestamp(data_cfg["lockbox_start"])
    else:
        src_tf = "D1" if "D1" in files else next(iter(files))
        lockbox_start = default_lockbox_start(load_kaggle_ohlcv_csv(files[src_tf]))

    feed = None
    if cfg.get("fundamental", {}).get("enabled"):
        from src.fundamental_feed import AutoFundamentalFeed
        feed = AutoFundamentalFeed(cfg)
    df, _ = build_mtf_dataset(files, primary_tf=base_timeframe(tf), context_tfs=meta.get("context_timeframes") or [], max_bars=None)
    df = add_technical_features(df, fundamental_feed=feed, refresh_fundamental=True)
    if "atr_14" in df.columns:
        df[TradingEnv.ATR_RAW_COLUMN] = df["atr_14"]

    purge = data_cfg.get("purge_bars", 50)
    embargo_h = data_cfg.get("embargo_hours", 24)
    embargo = max(1, round(embargo_h * 60 / _MINUTES_PER_BAR.get(base_timeframe(tf), 60))) if embargo_h else 0
    _, lock = split_lockbox(df, lockbox_start, purge_bars=purge, embargo_bars=embargo)
    if len(lock) == 0:
        raise ValueError(f"jeu sous clé vide pour '{tf}'")

    cols = meta["feature_columns"]
    dfn, _ = normalize_features(lock, stats={k: tuple(v) for k, v in stats.items()}, columns=cols)
    e, ag = cfg["environment"], cfg["agent"]
    kw = dict(window_size=e["window_size"], initial_balance=e["initial_balance"],
              transaction_cost=e["transaction_cost"], reward_type=e["reward_type"],
              drawdown_penalty=e["drawdown_penalty"], max_position=e["max_position"],
              continuous_action=str(meta.get("algo", "PPO")).upper() in ("SAC", "TD3"),
              learn_stop_loss=ag.get("learn_stop_loss", False),
              stop_loss_buckets=ag.get("stop_loss_buckets"),
              stop_loss_range=tuple(ag.get("stop_loss_range", (0.003, 0.06))),
              atr_stop_loss=ag.get("atr_stop_loss", True),
              session_spread_enabled=e.get("session_spread_enabled", True),
              session_spread_multipliers=e.get("session_spread_multipliers"))
    kw.update(e.get("style_overrides", {}).get(tf, {}))
    env = TradingEnv(dfn, feature_columns=cols, style=tf, **kw)
    agent = TradingAgent.load(model_path, env, {"algo": meta.get("algo", "PPO")})
    env = run_episode(agent, env)
    m = compute_metrics(env, timeframe=base_timeframe(tf))
    return {
        "sharpe": float(m["sharpe"]), "max_drawdown": float(m["max_drawdown"]),
        "total_return": float(m["total_return"]), "n_trades": int(m["n_trades"]),
        "profit_factor": float(m["profit_factor"]), "n_bars": int(len(dfn)),
        "lockbox_start": str(lockbox_start.date()),
    }


def gate_decision(metrics: dict, gate_cfg: dict, incumbent: dict | None) -> tuple[bool, str]:
    """(ok, raison). Seuils absolus + comparaison à l'incumbent s'il a des
    métriques lockbox : Sharpe >= le sien et activité >= `min_trades_ratio_vs_incumbent`
    fois la sienne."""
    problems = []
    if metrics["sharpe"] < gate_cfg.get("min_sharpe", 0.3):
        problems.append(f"sharpe {metrics['sharpe']:.2f} < {gate_cfg.get('min_sharpe', 0.3)}")
    if metrics["max_drawdown"] > gate_cfg.get("max_drawdown", 0.40):
        problems.append(f"drawdown {metrics['max_drawdown']:.1%} > {gate_cfg.get('max_drawdown', 0.40):.0%}")
    if metrics["total_return"] <= gate_cfg.get("min_return", 0.0):
        problems.append(f"rendement {metrics['total_return']:.1%} <= {gate_cfg.get('min_return', 0.0):.0%}")
    if metrics["n_trades"] < gate_cfg.get("min_trades", 100):
        problems.append(f"{metrics['n_trades']} trades < {gate_cfg.get('min_trades', 100)}")
    if incumbent and gate_cfg.get("beat_incumbent", True):
        if metrics["sharpe"] < incumbent.get("sharpe", -np.inf):
            problems.append(f"sharpe {metrics['sharpe']:.2f} < champion actuel {incumbent['sharpe']:.2f}")
        floor = gate_cfg.get("min_trades_ratio_vs_incumbent", 0.8) * incumbent.get("n_trades", 0)
        if metrics["n_trades"] < floor:
            problems.append(f"{metrics['n_trades']} trades < {floor:.0f} (80 % du champion actuel)")
    return (not problems, "; ".join(problems))
