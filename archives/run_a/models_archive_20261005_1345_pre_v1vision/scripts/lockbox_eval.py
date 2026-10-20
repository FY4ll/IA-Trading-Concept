"""
lockbox_eval.py
================
Évalue le champion d'un style sur le JEU SOUS CLÉ (LOT 2, phase 1) : les
données les plus récentes, jamais vues par l'entraînement/validation/
walk-forward/promotion (voir src/data_loader.py::split_lockbox,
autonomous_agent.py::make_data_provider). JAMAIS appelé automatiquement par
le trainer -- exécution manuelle uniquement, pour mesurer la performance sur
un futur qui n'a influencé aucune décision d'entraînement.

Chaque exécution ajoute une ligne à logs/lockbox_journal.jsonl (append-only) :
date, style, génération, env_version, métriques.

Usage : python scripts/lockbox_eval.py <style> [--config config/autonomous.yaml]
"""
from __future__ import annotations
import argparse
import json
import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import yaml

from src.continuous_trainer import _champion_meta, _champion_model, _champion_stats
from src.multi_timeframe import discover_files, build_mtf_dataset
from src.features import add_technical_features, normalize_features
from src.data_loader import default_lockbox_start, split_lockbox, load_kaggle_ohlcv_csv
from src.trading_env import TradingEnv, ENV_VERSION
from src.agent import TradingAgent
from src.backtester import run_episode, compute_metrics

logging.basicConfig(level=logging.INFO, format="%(asctime)s [LOCKBOX] [%(name)s] %(message)s")
log = logging.getLogger("lockbox_eval")

JOURNAL_PATH = "logs/lockbox_journal.jsonl"


def _resolve_lockbox_start(data_cfg: dict, files: dict):
    lockbox_start_cfg = data_cfg.get("lockbox_start")
    if lockbox_start_cfg:
        import pandas as pd
        return pd.Timestamp(lockbox_start_cfg)
    default_source_tf = "D1" if "D1" in files else next(iter(files))
    ref_df = load_kaggle_ohlcv_csv(files[default_source_tf])
    return default_lockbox_start(ref_df)


def evaluate_on_lockbox(style: str, cfg: dict) -> dict:
    """Cœur testable (voir tests/test_lockbox.py) : construit le jeu sous clé
    pour `style`, y évalue son champion, retourne les métriques."""
    meta_path = _champion_meta(style)
    if not Path(meta_path).exists():
        raise FileNotFoundError(f"Aucun champion pour le style '{style}' ({meta_path} introuvable).")
    with open(meta_path, encoding="utf-8") as f:
        meta = json.load(f)
    with open(_champion_stats(style), encoding="utf-8") as f:
        stats = {k: tuple(v) for k, v in json.load(f).items()}

    data_cfg = cfg["data"]
    files = discover_files(data_cfg["folder"])
    context_tfs = meta.get("context_timeframes") or []
    df, _ = build_mtf_dataset(files, primary_tf=style, context_tfs=context_tfs, max_bars=None)
    df = add_technical_features(df)
    if "atr_14" in df.columns:
        df[TradingEnv.ATR_RAW_COLUMN] = df["atr_14"]

    lockbox_start = _resolve_lockbox_start(data_cfg, files)
    purge_bars = data_cfg.get("purge_bars", 50)
    embargo_hours = data_cfg.get("embargo_hours", 24)
    from autonomous_agent import _MINUTES_PER_BAR
    embargo_bars = (max(1, round(embargo_hours * 60 / _MINUTES_PER_BAR.get(style, 60)))
                     if embargo_hours else 0)
    _, lockbox_df = split_lockbox(df, lockbox_start, purge_bars=purge_bars, embargo_bars=embargo_bars)
    if len(lockbox_df) == 0:
        raise ValueError(f"Jeu sous clé vide pour le style '{style}' (lockbox_start="
                          f"{lockbox_start.date()}) -- pas assez de données récentes.")

    feature_columns = meta["feature_columns"]
    missing = [c for c in feature_columns if c not in lockbox_df.columns]
    if missing:
        raise ValueError(f"Colonnes manquantes dans le jeu sous clé pour '{style}' : {missing}")
    df_norm, _ = normalize_features(lockbox_df, stats=stats, columns=feature_columns)

    continuous_action = str(meta.get("algo", "PPO")).upper() in ("SAC", "TD3")
    env_kwargs = dict(
        window_size=cfg["environment"]["window_size"],
        initial_balance=cfg["environment"]["initial_balance"],
        transaction_cost=cfg["environment"]["transaction_cost"],
        reward_type=cfg["environment"]["reward_type"],
        drawdown_penalty=cfg["environment"]["drawdown_penalty"],
        max_position=cfg["environment"]["max_position"],
        continuous_action=continuous_action,
        learn_stop_loss=cfg["agent"].get("learn_stop_loss", False),
        stop_loss_buckets=cfg["agent"].get("stop_loss_buckets"),
        stop_loss_range=tuple(cfg["agent"].get("stop_loss_range", (0.003, 0.06))),
        atr_stop_loss=cfg["agent"].get("atr_stop_loss", True),
        session_spread_enabled=cfg["environment"].get("session_spread_enabled", True),
        session_spread_multipliers=cfg["environment"].get("session_spread_multipliers"),
    )
    env_kwargs.update(cfg["environment"].get("style_overrides", {}).get(style, {}))
    env = TradingEnv(df_norm, feature_columns=feature_columns, style=style, **env_kwargs)
    # TradingAgent.load refuse un env_version incompatible (LOT 2, phase 1) --
    # laisse l'exception remonter : un champion pas encore réentraîné sous la
    # version actuelle ne doit pas produire un résultat trompeur ici non plus.
    agent = TradingAgent.load(_champion_model(style), env, {"algo": meta.get("algo", "PPO")})
    env = run_episode(agent, env)
    metrics = compute_metrics(env, timeframe=style)
    metrics["lockbox_start"] = str(lockbox_start.date())
    metrics["n_bars_tested"] = len(df_norm)
    return meta, metrics


def _append_journal(style: str, meta: dict, metrics: dict):
    Path(JOURNAL_PATH).parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "timestamp": time.time(), "date": time.strftime("%Y-%m-%d %H:%M:%S"),
        "style": style, "generation": meta.get("generation"),
        "env_version": meta.get("env_version"), "metrics": metrics,
    }
    with open(JOURNAL_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return entry


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("style", help="Style à évaluer (ex: M15, H1, D1)")
    parser.add_argument("--config", default="config/autonomous.yaml")
    args = parser.parse_args()

    with open(args.config, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    meta, metrics = evaluate_on_lockbox(args.style, cfg)
    entry = _append_journal(args.style, meta, metrics)

    log.info(f"Style '{args.style}' (génération {meta.get('generation')}, env_version="
              f"{meta.get('env_version')}) sur jeu sous clé (depuis {metrics['lockbox_start']}, "
              f"{metrics['n_bars_tested']} bougies) : sharpe={metrics['sharpe']:.2f}, "
              f"drawdown={metrics['max_drawdown']:.2%}, return={metrics['total_return']:.2%}, "
              f"n_trades={metrics['n_trades']}. Journalisé dans {JOURNAL_PATH}.")
    print(json.dumps(entry, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
