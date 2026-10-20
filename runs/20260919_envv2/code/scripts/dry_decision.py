"""
Décision LIVE à blanc d'un style (06/10/2026) : même chaîne que la démo (bougies MT5, vision du trader, état réel,
modèle champion), AUCUN ordre envoyé, aucun fichier d'état écrit. Sert à vérifier un style avant son premier
trade réel.

    python scripts/dry_decision.py AUREX        (cwd = code/)
"""
import os, sys, time
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
os.chdir(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import yaml


def main(style: str):
    cfg = yaml.safe_load(open("../run_config_A.yaml", encoding="utf-8"))
    from src.risk_profile import apply_risk_profile
    apply_risk_profile(cfg)
    cfg.setdefault("live", {})["dry_run"] = True
    e, ag = cfg["environment"], cfg["agent"]
    env_kwargs = dict(window_size=e["window_size"], initial_balance=e["initial_balance"],
                      transaction_cost=e["transaction_cost"], reward_type=e["reward_type"],
                      drawdown_penalty=e["drawdown_penalty"], max_position=e["max_position"],
                      continuous_action=False, spread_volatility_multiplier=e.get("spread_volatility_multiplier", 1.0),
                      learn_stop_loss=ag.get("learn_stop_loss", False), stop_loss_buckets=ag.get("stop_loss_buckets"),
                      stop_loss_range=tuple(ag.get("stop_loss_range", (0.003, 0.06))),
                      atr_stop_loss=ag.get("atr_stop_loss", True),
                      session_spread_enabled=e.get("session_spread_enabled", True),
                      session_spread_multipliers=e.get("session_spread_multipliers"),
                      inactivity_penalty_coef=e.get("inactivity_penalty_coef", 0.0))
    from src.mt5_connector import MT5Connector
    from src.episodic_memory import EpisodicMemory
    from src import demo_trader as dt
    conn = MT5Connector(cfg)
    conn.connect()
    entry = dt._load_style_entry(style)
    assert entry is not None, f"champion {style} introuvable"
    mem_cfg = cfg.get("memory", {})
    memory = EpisodicMemory(mem_cfg["db_path"], mem_cfg.get("max_episodes", 20000),
                            private_styles=mem_cfg.get("private_styles"))     # même mémoire que le live
    rt = dt._StyleRuntime()
    kw = dt._style_env_kwargs(cfg, style, env_kwargs)
    n_needed = env_kwargs["window_size"] + 150
    n_ctx = cfg.get("data", {}).get("n_bars_context", 3000)
    t0 = time.time()
    rt.maybe_reload(entry, conn, None, n_needed, n_ctx, memory, mem_cfg.get("similarity_top_k", 5), kw)
    pos = conn.get_open_positions_by_style([style]).get(style)
    extra = dt._live_extra(conn, style, pos) if kw.get("trader_state") else None
    target, stop_pct, atr_mult, atr_units, df = rt.decide(conn, None, n_needed, memory,
                                                         mem_cfg.get("similarity_top_k", 5), kw,
                                                         live_position=pos, live_extra=extra)
    print(f"{style} gén {entry['meta'].get('generation')} -- décision à blanc en {time.time() - t0:.0f} s")
    print(f"  dernière bougie : {df['time'].iloc[-1] if 'time' in df.columns else '?'} ; {len(df)} bougies, "
          f"{len(rt.feature_columns)} variables, NaN dans la dernière ligne : "
          f"{int(df[rt.feature_columns].iloc[-1].isna().sum())}")
    print(f"  cible {target:+.2f}, stop {stop_pct}, ATR x{atr_mult} ({atr_units}), objectif R/R "
          f"{getattr(rt, 'last_take_profit_rr', None)}, probas {getattr(rt, 'last_proba', None)}")
    for k in ("last_limit_offset", "last_manage", "last_note"):
        if hasattr(rt, k):
            print(f"  {k} : {getattr(rt, k)}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "AUREX")
