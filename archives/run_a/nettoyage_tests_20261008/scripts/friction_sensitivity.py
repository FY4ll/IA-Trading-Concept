"""
friction_sensitivity.py
========================
LOT 2, phase 5 : évalue un champion déjà promu à des niveaux de friction
x0.5, x1 (référence, le profil actuellement configuré -- voir
src/stress_test.py::resolve_friction_params) et x2, pour mesurer la
SENSIBILITÉ de ses métriques à l'ampleur du choc de coût d'exécution
(spread élargi + slippage, voir inject_macro_shocks) -- jamais une
recalibration automatique (décision humaine, voir aussi
scripts/slippage_report.py).

Usage : python scripts/friction_sensitivity.py [--style M15] [--config config/autonomous.yaml]
(sans --style : évalue TOUS les styles ayant un champion existant)
"""
from __future__ import annotations
import argparse
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import yaml

from src.continuous_trainer import _champion_meta, _champion_model, _champion_stats
from src.trading_env import TradingEnv
from src.agent import TradingAgent
from src.backtester import evaluate_agent
from src.stress_test import inject_macro_shocks, resolve_friction_params
from src.multi_timeframe import discover_files, build_mtf_dataset
from src.features import add_technical_features, normalize_features
from src.data_loader import chronological_split

logging.basicConfig(level=logging.INFO, format="%(asctime)s [FRICTION] [%(name)s] %(message)s")
log = logging.getLogger("friction_sensitivity")

FRICTION_MULTIPLIERS = [0.5, 1.0, 2.0]


def evaluate_at_friction_multiplier(agent, val_df, env_kwargs, timeframe: str,
                                      multiplier: float, base_params: dict, seed: int) -> dict:
    """Cœur testable (voir tests/test_friction_sensitivity.py) : ré-échelonne
    `spread_multiplier_range`/`slippage_price_range` par `multiplier` (jamais
    `spread_multiplier_range` sous 1.0 -- un spread ne peut pas être plus
    étroit que le spread normal, seulement plus large), applique le choc, et
    évalue l'agent (poids figés) sur le résultat."""
    low_s, high_s = base_params["spread_multiplier_range"]
    low_p, high_p = base_params["slippage_price_range"]
    scaled = {
        "spread_multiplier_range": (max(1.0, low_s * multiplier), max(1.0, high_s * multiplier)),
        "slippage_price_range": (max(0.0, low_p * multiplier), max(0.0, high_p * multiplier)),
    }
    shocked_df = inject_macro_shocks(val_df, seed=seed, **scaled)
    return evaluate_agent(agent, shocked_df, env_kwargs, timeframe=timeframe)


def evaluate_style(style: str, cfg: dict) -> list[dict]:
    meta_path = _champion_meta(style)
    if not Path(meta_path).exists():
        log.warning(f"Aucun champion pour le style '{style}' -- ignoré.")
        return []
    with open(meta_path, encoding="utf-8") as f:
        meta = json.load(f)
    with open(_champion_stats(style), encoding="utf-8") as f:
        stats = {k: tuple(v) for k, v in json.load(f).items()}

    data_cfg = cfg["data"]
    files = discover_files(data_cfg["folder"])
    context_tfs = meta.get("context_timeframes") or []
    df, _ = build_mtf_dataset(files, primary_tf=style, context_tfs=context_tfs,
                                max_bars=data_cfg.get("max_bars", 60000))
    df = add_technical_features(df)
    _, val_df, _ = chronological_split(df, data_cfg.get("train_ratio", 0.7), data_cfg.get("val_ratio", 0.3),
                                         purge_bars=data_cfg.get("purge_bars", 50))
    feature_columns = meta["feature_columns"]
    val_df_norm, _ = normalize_features(val_df, stats=stats, columns=feature_columns)

    continuous_action = str(meta.get("algo", "PPO")).upper() in ("SAC", "TD3")
    env_kwargs = dict(
        window_size=cfg["environment"]["window_size"], initial_balance=cfg["environment"]["initial_balance"],
        transaction_cost=cfg["environment"]["transaction_cost"], reward_type=cfg["environment"]["reward_type"],
        drawdown_penalty=cfg["environment"]["drawdown_penalty"], max_position=cfg["environment"]["max_position"],
        continuous_action=continuous_action,
        learn_stop_loss=cfg["agent"].get("learn_stop_loss", False),
        atr_stop_loss=cfg["agent"].get("atr_stop_loss", True),
    )
    env = TradingEnv(val_df_norm, feature_columns=feature_columns, style=style, **env_kwargs)
    agent = TradingAgent.load(_champion_model(style), env, {"algo": meta.get("algo", "PPO")})

    profile = (cfg.get("frictions") or {}).get("profile", "pessimistic")
    base_params = resolve_friction_params(profile)
    from src.continuous_trainer import _stress_seed_for_style
    seed = _stress_seed_for_style(style)

    rows = []
    for mult in FRICTION_MULTIPLIERS:
        metrics = evaluate_at_friction_multiplier(agent, val_df_norm, env_kwargs, style, mult, base_params, seed)
        rows.append({"style": style, "friction_multiplier": mult, "sharpe": metrics["sharpe"],
                      "max_drawdown": metrics["max_drawdown"], "total_return": metrics["total_return"],
                      "n_trades": metrics["n_trades"]})
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--style", default=None, help="Style unique à évaluer (défaut : tous ceux avec un champion)")
    parser.add_argument("--config", default="config/autonomous.yaml")
    args = parser.parse_args()

    with open(args.config, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    styles = [args.style] if args.style else cfg["data"].get("timeframe_pool", [])
    all_rows = []
    for style in styles:
        all_rows.extend(evaluate_style(style, cfg))

    if not all_rows:
        log.warning("Aucun champion évalué (aucun style n'en a encore).")
        return

    print(f"\n{'style':<6} {'friction':<10} {'sharpe':<8} {'drawdown':<10} {'return':<10} {'n_trades':<8}")
    for r in all_rows:
        print(f"{r['style']:<6} x{r['friction_multiplier']:<9} {r['sharpe']:<8.2f} "
              f"{r['max_drawdown']:<10.2%} {r['total_return']:<10.2%} {r['n_trades']:<8}")


if __name__ == "__main__":
    main()
