"""
Évaluation des entraînements longs (06/10/2026) -- lecture seule, ne promeut rien.
Chaque point de sauvegarde de models/long_<style>/<run>/ est noté sur la validation OR avec la même mesure que les
cycles (walk-forward + scénarios de stress, score = fitness - 2 x drawdown + excès), comme le champion AUREX
actuel (même règle). Les 2 meilleurs passent ensuite la lockbox (40 mois jamais vus) et la porte.
Résultat : reports/long_<style>.json

    python scripts/eval_long.py AUREXIS        (cwd = code/)
"""
import glob, json, os, sys, time
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
os.chdir(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import yaml


def main(style: str, quick: bool = False, only: str | None = None):
    cfg = yaml.safe_load(open("../run_config_A.yaml", encoding="utf-8"))
    from src.risk_profile import apply_risk_profile
    apply_risk_profile(cfg)
    import autonomous_agent as aa
    from src.continuous_trainer import DEFAULT_VALIDATION, _resolve_stress_test, _stress_seed_for_style
    from src.backtester import evaluate_agent_walkforward, passes_validation
    from src.episodic_memory import EpisodicMemory
    from src.trading_env import TradingEnv
    from src.agent import TradingAgent
    sys.path.insert(0, "scripts")
    from train_long import env_kwargs_for
    cfg["validation"] = {**DEFAULT_VALIDATION, **cfg.get("validation", {})}
    c = cfg["continuous"]
    t0 = time.time()
    get_data, _ = aa.make_data_provider(cfg)
    # validation OR uniquement : le dataset or de l'alias (AUREX) suffit, sans reconstruire les autres marchés
    _, val_df, stats, cols, ctx = get_data((cfg.get("data", {}).get("dataset_alias") or {}).get(style, style))
    mem_cfg = cfg.get("memory", {})
    memory = EpisodicMemory(mem_cfg["db_path"], mem_cfg.get("max_episodes", 20000))
    snap = memory.snapshot(dim=len(cols), sources=["backtest"])
    memory.close()
    kw = env_kwargs_for(cfg, style, cols, snap)
    macro = None
    if (cfg.get("stress_test") or {}).get("macro_events_csv"):
        try:
            from src.stress_test import load_macro_events_csv
            macro = load_macro_events_csv(cfg["stress_test"]["macro_events_csv"])
        except Exception:
            macro = None
    stress = _resolve_stress_test(style, c.get("stress_test", False), c.get("stress_test_styles"))

    def score_model(path):
        env = TradingEnv(val_df, **kw)
        agent = TradingAgent.load(path, env, {"algo": "PPO"})
        m = evaluate_agent_walkforward(agent, val_df, kw, n_windows=c.get("eval_windows", 3), stress_test=stress,
                                       stress_seed=_stress_seed_for_style(style), timeframe="M15",
                                       macro_event_timestamps=macro,
                                       friction_profile=(cfg.get("frictions") or {}).get("profile", "pessimistic"))
        fit = m.get(c.get("fitness_metric", "sortino"), m["sharpe"])
        s = fit - 2.0 * m["max_drawdown"] + float(c.get("excess_return_weight", 0.0) or 0.0) * m.get("excess_return", 0.0)
        return s, m

    os.makedirs("reports", exist_ok=True)
    part_path = lambda name: f"reports/long_{style}_part_{name}.json"
    rows = []
    if only in (None, "ref"):
        ref = os.path.join("models", "champion_AUREX", "agent")
        s, m = score_model(ref)
        rows.append({"name": "AUREX champion (référence)", "path": ref, "score": s, "metrics": m, "reference": True})
        print(f"référence AUREX : score {s:.3f} sharpe {m['sharpe']:.2f} ret {m['total_return']:+.2%} dd {m['max_drawdown']:.1%}", flush=True)
    for run_dir in sorted(glob.glob(os.path.join("models", os.environ.get("LONG_BASE", f"long_{style}"), "r*"))):
        if only is not None and os.path.basename(run_dir) != only:
            continue
        cks = sorted(glob.glob(os.path.join(run_dir, "ckpt_*.zip")), key=lambda p: int(p.split("_")[-1][:-4]))
        if quick:
            cks = cks[:1]
        for ck in cks:
            path = ck[:-4]
            try:
                s, m = score_model(path)
            except Exception as e:
                print(f"{path} : évaluation impossible ({e})", flush=True)
                continue
            rows.append({"name": f"{os.path.basename(run_dir)}/{os.path.basename(path)}", "path": path, "score": s,
                         "metrics": m, "passes_validation": bool(passes_validation(m, cfg, style=style))})
            print(f"{rows[-1]['name']} : score {s:.3f} sharpe {m['sharpe']:.2f} ret {m['total_return']:+.2%} "
                  f"dd {m['max_drawdown']:.1%} trades {m.get('n_trades')} validation {'OK' if rows[-1]['passes_validation'] else 'non'} "
                  f"({(time.time() - t0) / 60:.0f} min)", flush=True)
    if only is not None:      # évaluation partielle (un processus par entraînement) : fusion par --merge
        json.dump({"rows": rows}, open(part_path(only), "w", encoding="utf-8"), indent=1, default=str)
        print(f"partie {only} terminée en {(time.time() - t0) / 60:.0f} min", flush=True)
        return
    _lockbox_and_report(style, cfg, rows, cols, ctx, stats, quick, t0)


def _lockbox_and_report(style, cfg, rows, cols, ctx, stats, quick, t0):
    from src.lockbox_gate import evaluate_on_lockbox, gate_decision
    cands = sorted([r for r in rows if not r.get("reference")], key=lambda r: r["score"], reverse=True)[:1 if quick else 2]
    meta_like = {"feature_columns": cols, "context_timeframes": ctx, "algo": "PPO"}
    gate_cfg = cfg["validation"].get("lockbox_gate") or {}
    for r in cands:
        try:
            lb = evaluate_on_lockbox(style, cfg, r["path"], meta_like, stats)
            ok, why = gate_decision(lb, gate_cfg, None)
            r["lockbox"], r["gate_ok"], r["gate_reason"] = lb, ok, why
            print(f"LOCKBOX {r['name']} : sharpe {lb['sharpe']:.2f} ret {lb['total_return']:+.1%} dd {lb['max_drawdown']:.1%} "
                  f"trades {lb['n_trades']} tiers {[round(x, 3) for x in lb.get('thirds_returns', [])]} -> "
                  f"{'OK' if ok else 'REFUSÉE : ' + why}", flush=True)
        except Exception as e:
            print(f"LOCKBOX {r['name']} impossible : {e}", flush=True)
    json.dump({"style": style, "reference_aurex_lockbox": json.load(open("reports/lockbox_AUREX.json", encoding="utf-8"))
               if os.path.exists("reports/lockbox_AUREX.json") else None, "rows": rows},
              open(f"reports/long_{style}{'_essai' if quick else ''}.json", "w", encoding="utf-8"), indent=1, default=str)
    print(f"terminé en {(time.time() - t0) / 60:.0f} min -> reports/long_{style}.json", flush=True)


def merge(style: str):
    """Fusionne les évaluations partielles puis passe les 2 meilleurs sur la lockbox."""
    t0 = time.time()
    cfg = yaml.safe_load(open("../run_config_A.yaml", encoding="utf-8"))
    from src.risk_profile import apply_risk_profile
    apply_risk_profile(cfg)
    from src.continuous_trainer import DEFAULT_VALIDATION
    cfg["validation"] = {**DEFAULT_VALIDATION, **cfg.get("validation", {})}
    rows = []
    for p in sorted(glob.glob(f"reports/long_{style}_part_*.json")):
        rows += json.load(open(p, encoding="utf-8"))["rows"]
    d = sorted(glob.glob(os.path.join("models", os.environ.get("LONG_BASE", f"long_{style}"), "r*")))[0]
    meta = json.load(open(os.path.join(d, "meta.json"), encoding="utf-8"))
    stats = {k: tuple(v) for k, v in json.load(open(os.path.join(d, "norm_stats.json"), encoding="utf-8")).items()}
    print(f"fusion : {len(rows)} évaluations", flush=True)
    _lockbox_and_report(style, cfg, rows, meta["feature_columns"], meta["context_timeframes"], stats, False, t0)


if __name__ == "__main__":
    st = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("--") else "AUREXIS"
    if "--merge" in sys.argv:
        merge(st)
    else:
        only = sys.argv[sys.argv.index("--only") + 1] if "--only" in sys.argv else None
        main(st, quick="--quick" in sys.argv, only=only)