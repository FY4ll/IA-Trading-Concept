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

05/10/2026 (vision "Autonomous Trader V1", §42, §45, §71) : l'évaluation
calcule aussi les BASELINES sur la même période (buy & hold de l'or, tendance
simple SMA 20/50) et les mesures PROP FIRM (src/ftmo_metrics.py : probabilité
de Challenge/Vérification FTMO, pire jour, rendement mensuel). Deux critères
optionnels (absents = sans effet) : `min_ftmo_challenge_pass` et
`ftmo_max_drop_vs_incumbent`, plus `require_beat_trend_baseline`.
"""
from __future__ import annotations
import logging
import os

import numpy as np
import pandas as pd

from src.style_utils import base_timeframe

log = logging.getLogger("lockbox_gate")

_MINUTES_PER_BAR = {"M15": 15, "M30": 30, "H1": 60, "H4": 240, "D1": 1440}


def resolve_lockbox_start(cfg: dict):
    import pandas as pd
    from src.multi_timeframe import discover_files
    from src.data_loader import default_lockbox_start, load_kaggle_ohlcv_csv
    data_cfg = cfg["data"]
    if data_cfg.get("lockbox_start"):
        return pd.Timestamp(data_cfg["lockbox_start"])
    files = discover_files(data_cfg["folder"])
    src_tf = "D1" if "D1" in files else next(iter(files))
    return default_lockbox_start(load_kaggle_ohlcv_csv(files[src_tf]))


def build_eval_frames(tf: str, cfg: dict, meta: dict):
    """(visible, lockbox, lockbox_start) : DataFrames BRUTS (non normalisés) du style, avec les
    mêmes features qu'à l'entraînement, coupés à la date de lockbox (purge + embargo)."""
    from src.multi_timeframe import discover_files, build_mtf_dataset
    from src.features import add_technical_features
    from src.data_loader import split_lockbox
    from src.trading_env import TradingEnv

    data_cfg = cfg["data"]
    files = discover_files(data_cfg["folder"])
    lockbox_start = resolve_lockbox_start(cfg)
    feed = None
    if cfg.get("fundamental", {}).get("enabled"):
        from src.fundamental_feed import AutoFundamentalFeed
        feed = AutoFundamentalFeed(cfg)
    df, _ = build_mtf_dataset(files, primary_tf=base_timeframe(tf), context_tfs=meta.get("context_timeframes") or [], max_bars=None)
    df = add_technical_features(df, fundamental_feed=feed, refresh_fundamental=True)
    from src import cross_asset
    if cross_asset.has_cross_columns(meta.get("feature_columns")):
        df = cross_asset.add_cross_asset_features(
            df, fred=getattr(feed, "_fred", None),
            daily_provider=cross_asset.csv_daily_provider(
                data_cfg.get("cross_asset_folder") or os.path.join(os.path.dirname(os.path.abspath(data_cfg["folder"])), "cross_asset")))
    from src.trader.vision import has_trader_columns, add_trader_vision
    if has_trader_columns(meta.get("feature_columns")):
        from src.data_loader import load_kaggle_ohlcv_csv
        m5 = None
        if "M5" in files:
            m5 = load_kaggle_ohlcv_csv(files["M5"])
            m5["time"] = pd.to_datetime(m5["time"])
            m5 = m5[m5["time"] >= pd.to_datetime(df["time"]).min() - pd.Timedelta(days=3)]
        df = add_trader_vision(df, m5=m5)
    from src.trader.toolbox import has_toolbox_columns, add_toolbox
    if has_toolbox_columns(meta.get("feature_columns")):
        df = add_toolbox(df)
    from src.trend_vision import TREND_COLUMNS, add_trend_vision        # 09/10 : vision des tendances de fond
    if any(c in (meta.get("feature_columns") or []) for c in TREND_COLUMNS):
        df = add_trend_vision(df)
    if "atr_14" in df.columns:
        df[TradingEnv.ATR_RAW_COLUMN] = df["atr_14"]
    purge = data_cfg.get("purge_bars", 50)
    embargo_h = data_cfg.get("embargo_hours", 24)
    embargo = max(1, round(embargo_h * 60 / _MINUTES_PER_BAR.get(base_timeframe(tf), 60))) if embargo_h else 0
    visible, lock = split_lockbox(df, lockbox_start, purge_bars=purge, embargo_bars=embargo)
    return visible, lock, lockbox_start


def eval_env_kwargs(tf: str, cfg: dict, meta: dict) -> dict:
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
    return kw


def baseline_metrics(lock_raw, transaction_cost: float) -> dict:
    """Baselines sur la même période : buy & hold de l'or et tendance simple SMA20/50
    (long/short, exécutée à la bougie suivante, coût `transaction_cost` par changement)."""
    from src.ftmo_metrics import daily_returns, prop_firm_summary
    close = lock_raw["close"].to_numpy(float)
    times = lock_raw["time"] if "time" in lock_raw.columns else None
    out = {}
    bh_eq = close / close[0]
    sma20 = lock_raw["close"].rolling(20).mean().to_numpy()
    sma50 = lock_raw["close"].rolling(50).mean().to_numpy()
    sig = np.where(np.isnan(sma50), 0.0, np.sign(sma20 - sma50))
    pos = np.concatenate([[0.0], sig[:-1]])            # décision à t, exécution sur t+1
    bar_ret = np.concatenate([[0.0], close[1:] / close[:-1] - 1])
    cost = np.abs(np.diff(np.concatenate([[0.0], pos]))) * transaction_cost
    tr_eq = np.cumprod(1 + pos * bar_ret - cost)
    for name, eq in (("buy_hold", bh_eq), ("trend_sma20_50", tr_eq)):
        r = np.diff(eq) / eq[:-1]
        sharpe = float(r.mean() / r.std() * np.sqrt(252 * 24)) if r.std() > 1e-12 else 0.0
        dd = float((eq / np.maximum.accumulate(eq) - 1).min())
        item = {"total_return": float(eq[-1] - 1), "sharpe": sharpe, "max_drawdown": -dd}
        if times is not None:
            item["prop_firm"] = prop_firm_summary(daily_returns(eq, times).to_numpy(), n_sims=1000)
        out[name] = item
    return out


def evaluate_on_lockbox(tf: str, cfg: dict, model_path: str, meta: dict, stats: dict) -> dict:
    from src.features import normalize_features
    from src.trading_env import TradingEnv
    from src.agent import TradingAgent
    from src.backtester import run_episode, compute_metrics

    _, lock, lockbox_start = build_eval_frames(tf, cfg, meta)
    if len(lock) == 0:
        raise ValueError(f"jeu sous clé vide pour '{tf}'")

    cols = meta["feature_columns"]
    dfn, _ = normalize_features(lock, stats={k: tuple(v) for k, v in stats.items()}, columns=cols)
    kw = eval_env_kwargs(tf, cfg, meta)
    env = TradingEnv(dfn, feature_columns=cols, style=tf, **kw)
    agent = TradingAgent.load(model_path, env, {"algo": meta.get("algo", "PPO")})
    env = run_episode(agent, env)
    m = compute_metrics(env, timeframe=base_timeframe(tf))
    out = {
        "sharpe": float(m["sharpe"]), "max_drawdown": float(m["max_drawdown"]),
        "total_return": float(m["total_return"]), "n_trades": int(m["n_trades"]),
        "profit_factor": float(m["profit_factor"]), "n_bars": int(len(dfn)),
        "lockbox_start": str(lockbox_start.date()),
        "thirds_returns": _thirds_returns(env.equity_curve),
    }
    gate_cfg = cfg.get("validation", {}).get("lockbox_gate", {})
    if gate_cfg.get("prop_firm_metrics", True) and "time" in env.df.columns:
        try:
            from src.ftmo_metrics import daily_returns, prop_firm_summary
            out["prop_firm"] = prop_firm_summary(daily_returns(env.equity_curve, env.df["time"]).to_numpy())
            out["baselines"] = baseline_metrics(lock, kw["transaction_cost"])
        except Exception as e:
            log.warning(f"[lockbox] mesures prop firm/baselines indisponibles pour {tf} : {e}")
    mult = float(gate_cfg.get("stress_cost_multiplier", 0) or 0)
    if mult > 1.0:
        kw_stress = {**kw, "transaction_cost": kw["transaction_cost"] * mult}
        env2 = TradingEnv(dfn, feature_columns=cols, style=tf, **kw_stress)
        env2 = run_episode(agent, env2)
        m2 = compute_metrics(env2, timeframe=base_timeframe(tf))
        out["stress_sharpe"] = float(m2["sharpe"])
        out["stress_return"] = float(m2["total_return"])
        out["stress_cost_multiplier"] = mult
    return out


def _thirds_returns(equity_curve) -> list[float]:
    eq = np.asarray(equity_curve, dtype=float)
    if len(eq) < 6:
        return []
    cuts = np.linspace(0, len(eq) - 1, 4).astype(int)
    return [float(eq[b] / eq[a] - 1.0) for a, b in zip(cuts[:-1], cuts[1:])]


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
    # Durcissement (04/10) : actif seulement si la clé est configurée ET la mesure disponible.
    if "stress_min_return" in gate_cfg and "stress_return" in metrics:
        if metrics["stress_return"] <= gate_cfg["stress_min_return"]:
            problems.append(f"rendement sous coûts x{metrics.get('stress_cost_multiplier', 2):g} "
                            f"{metrics['stress_return']:.1%} <= {gate_cfg['stress_min_return']:.0%}")
    # PÉRIODE LA PLUS RÉCENTE (06/10/2026) : le dernier tiers de la lockbox (le marché le plus proche
    # d'aujourd'hui) ne doit pas être perdant -- un candidat bon seulement sur le passé lointain est refusé.
    last_min = gate_cfg.get("min_last_third_return")
    thirds_ = metrics.get("thirds_returns")
    if last_min is not None and thirds_ and thirds_[-1] < last_min:
        problems.append(f"dernier tiers de la lockbox {thirds_[-1]:.1%} < {last_min:.0%} (marché récent)")
    max_neg = gate_cfg.get("max_negative_thirds")
    thirds = metrics.get("thirds_returns")
    if max_neg is not None and thirds:
        n_neg = sum(1 for r in thirds if r <= 0)
        if n_neg > max_neg:
            problems.append(f"{n_neg}/{len(thirds)} sous-périodes de la lockbox négatives "
                            f"({', '.join(f'{r:.1%}' for r in thirds)})")
    # PROP FIRM (05/10) : probabilité de réussir le Challenge FTMO simulée sur la lockbox.
    pf = metrics.get("prop_firm") or {}
    if "min_ftmo_challenge_pass" in gate_cfg and "challenge_pass" in pf:
        if pf["challenge_pass"] < gate_cfg["min_ftmo_challenge_pass"]:
            problems.append(f"Challenge FTMO simulé {pf['challenge_pass']:.0%} < {gate_cfg['min_ftmo_challenge_pass']:.0%}")
    inc_pf = (incumbent or {}).get("prop_firm") or {}
    if "ftmo_max_drop_vs_incumbent" in gate_cfg and "challenge_pass" in pf and "challenge_pass" in inc_pf:
        floor = inc_pf["challenge_pass"] - gate_cfg["ftmo_max_drop_vs_incumbent"]
        if pf["challenge_pass"] < floor:
            problems.append(f"Challenge FTMO simulé {pf['challenge_pass']:.0%} < champion actuel "
                            f"{inc_pf['challenge_pass']:.0%} - {gate_cfg['ftmo_max_drop_vs_incumbent']:.0%}")
    # BASELINE (05/10) : battre une simple tendance SMA20/50 en Sharpe sur la même période.
    trend = ((metrics.get("baselines") or {}).get("trend_sma20_50") or {})
    if gate_cfg.get("require_beat_trend_baseline") and "sharpe" in trend:
        if metrics["sharpe"] <= trend["sharpe"]:
            problems.append(f"sharpe {metrics['sharpe']:.2f} <= baseline tendance SMA20/50 {trend['sharpe']:.2f}")
    if incumbent and gate_cfg.get("beat_incumbent", True):
        if metrics["sharpe"] < incumbent.get("sharpe", -np.inf):
            problems.append(f"sharpe {metrics['sharpe']:.2f} < champion actuel {incumbent['sharpe']:.2f}")
        floor = gate_cfg.get("min_trades_ratio_vs_incumbent", 0.8) * incumbent.get("n_trades", 0)
        if metrics["n_trades"] < floor:
            problems.append(f"{metrics['n_trades']} trades < {floor:.0f} (80 % du champion actuel)")
    return (not problems, "; ".join(problems))
