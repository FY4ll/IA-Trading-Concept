"""
poll_frequency_sensitivity.py
==============================
Diagnostic LEGER (inference seule, aucun entrainement) qui mesure l'impact
reel de la frequence de decision (`live.poll_seconds`) sur le nombre de
retournements de position et le cout de spread cumule, style par style, sur
historique reel deja telecharge -- jamais de connexion MT5, ne touche
jamais models/ ni la config en cours (lecture seule d'un champion deja
promu). Meme esprit que scripts/friction_sensitivity.py.

LIMITE ASSUMEE : ce framework de backtest decide au plus une fois par
bougie (une "etape" = une bougie de la timeframe primaire du style). On ne
peut donc pas simuler un sondage PLUS FREQUENT que la bougie elle-meme (ca
n'ajouterait aucune information nouvelle -- exactement pourquoi un sondage
a poll_seconds=300 sur un style H4/D1, dont la bougie dure 4h/24h, ne peut
QUE requeter la meme bougie deja vue, sans nouvelle info, ce qui est deja
une explication qualitative de l'incident de sur-trading documente dans
config/autonomous.yaml pres de `min_reentry_cooldown_minutes`). Ce script
teste donc le sens complementaire et mesurable : decider MOINS souvent que
chaque bougie (throttle) reduit-il le cout sans degrader le rendement ?

Usage :
    python scripts/poll_frequency_sensitivity.py [--style M30] [--config ...]
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
from src.backtester import compute_metrics
from src.multi_timeframe import discover_files, build_mtf_dataset
from src.features import add_technical_features, normalize_features
from src.data_loader import chronological_split

logging.basicConfig(level=logging.INFO, format="%(asctime)s [POLL-FREQ] [%(name)s] %(message)s")
log = logging.getLogger("poll_frequency_sensitivity")

# Duree d'une bougie par style (minutes) -- sert a convertir un nombre de
# bougies sautees en une frequence de sondage "equivalente" lisible.
BAR_MINUTES = {"M15": 15, "M30": 30, "H1": 60, "H4": 240, "D1": 1440}

# Nombre de bougies sautees entre deux decisions (1 = decide a chaque
# bougie, la frequence la plus fine possible dans ce framework -- voir
# limite assumee ci-dessus).
THROTTLE_STEPS = [1, 2, 4, 8]


def run_episode_throttled(agent, env: TradingEnv, throttle_steps: int) -> TradingEnv:
    """Comme src.backtester.run_episode, mais ne rappelle agent.predict()
    qu'une bougie sur `throttle_steps` -- entre deux decisions, l'action
    PRECEDENTE est reappliquee telle quelle (le marche continue d'avancer
    bougie par bougie, seule la DECISION est ralentie, jamais l'avancee du
    temps)."""
    obs, _ = env.reset()
    done = False
    step_i = 0
    action = 0
    while not done:
        if step_i % throttle_steps == 0:
            action = agent.predict(obs, deterministic=True)
        obs, reward, terminated, truncated, info = env.step(action)
        done = terminated or truncated
        step_i += 1
    return env


def _n_reversals(env: TradingEnv) -> int:
    """Nombre de clotures CONSECUTIVES dont la direction s'inverse
    (long->short ou short->long) dans `env.trade_log` -- proxy du
    retournement rapide qui paie le spread deux fois (ferme + rouvre),
    distinct de n_trades qui compte toute cloture sans distinguer un
    retournement d'une simple sortie vers plat."""
    trades = getattr(env, "trade_log", None)
    if not trades or len(trades) < 2:
        return 0
    reversals = 0
    for i in range(1, len(trades)):
        prev_sign = 1 if trades[i - 1]["position"] > 0 else (-1 if trades[i - 1]["position"] < 0 else 0)
        cur_sign = 1 if trades[i]["position"] > 0 else (-1 if trades[i]["position"] < 0 else 0)
        if prev_sign != 0 and cur_sign != 0 and prev_sign != cur_sign:
            reversals += 1
    return reversals


def evaluate_style(style: str, cfg: dict) -> list[dict]:
    meta_path = _champion_meta(style)
    if not Path(meta_path).exists():
        log.warning(f"Aucun champion pour le style '{style}' -- ignore.")
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
    # ATR en unites de prix pour TradingEnv._atr_price_units (voir
    # ATR_RAW_COLUMN dans trading_env.py) -- meme copie que celle faite par
    # autonomous_agent.py::make_data_provider. Sans elle, _atr_price_units()
    # renvoie toujours None et AUCUNE ouverture n'est jamais permise (le
    # garde-fou anti-incoherence de trading_env.py annule tout changement de
    # position) : bug trouve en executant ce script pour la premiere fois
    # (0 trade partout, tous styles, tous throttle) -- meme piege probable
    # dans scripts/friction_sensitivity.py, qui a le meme gap.
    df[TradingEnv.ATR_RAW_COLUMN] = df["atr_14"]
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
    agent = None
    rows = []
    bar_min = BAR_MINUTES.get(style, 60)
    for n in THROTTLE_STEPS:
        env = TradingEnv(val_df_norm, feature_columns=feature_columns, style=style, **env_kwargs)
        if agent is None:
            agent = TradingAgent.load(_champion_model(style), env, {"algo": meta.get("algo", "PPO")})
        env = run_episode_throttled(agent, env, n)
        metrics = compute_metrics(env, timeframe=style)
        rows.append({
            "style": style, "throttle_steps": n, "equiv_poll_minutes": n * bar_min,
            "sharpe": metrics["sharpe"], "max_drawdown": metrics["max_drawdown"],
            "total_return": metrics["total_return"], "n_trades": metrics["n_trades"],
            "n_reversals": _n_reversals(env),
        })
        log.info(f"[{style}] throttle={n} bougie(s) (~{n * bar_min}min) : "
                  f"sharpe={metrics['sharpe']:.3f} n_trades={metrics['n_trades']} "
                  f"n_reversals={rows[-1]['n_reversals']} return={metrics['total_return']:.3%}")
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--style", default=None, help="Style unique a evaluer (defaut : tous ceux avec un champion)")
    parser.add_argument("--config", default="config/autonomous.yaml")
    args = parser.parse_args()

    with open(args.config, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    styles = [args.style] if args.style else cfg["data"].get("timeframe_pool", [])
    all_rows = []
    for style in styles:
        all_rows.extend(evaluate_style(style, cfg))

    if not all_rows:
        log.warning("Aucun champion evalue (aucun style n'en a encore).")
        return

    print(f"\n{'style':<6} {'~min':<7} {'sharpe':<8} {'drawdown':<10} {'return':<10} {'n_trades':<9} {'n_revers':<9}")
    for r in all_rows:
        print(f"{r['style']:<6} {r['equiv_poll_minutes']:<7} {r['sharpe']:<8.2f} "
              f"{r['max_drawdown']:<10.2%} {r['total_return']:<10.2%} {r['n_trades']:<9} {r['n_reversals']:<9}")


if __name__ == "__main__":
    main()
