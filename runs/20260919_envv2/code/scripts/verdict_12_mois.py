"""VERDICT DES 12 MOIS CACHÉS (09/10/2026) -- lecture seule. Le champion AUREXIS rejoue les mois cachés (après la plage
de l'examen tournant, jamais utilisés pour sélectionner) sur tous ses marchés, un seul compte aux vraies dates : gains
mensuels, pire jour, plus forte baisse, challenge FTMO démarré à chaque jour (réussi / raté / en cours après 120 jours).
Lancé chaque nuit (tâche « TestIA_Verdict12Mois ») ; écrit reports/verdict_12_mois.json (+ historique par génération),
lu par la règle de passage en démo (scripts/regle_demo_aurexis.py).

    python scripts/verdict_12_mois.py        (cwd = code/)
"""
import gc, json, os, sys, time
os.environ["CUDA_VISIBLE_DEVICES"] = "-1"
CODE = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, CODE)
os.chdir(CODE)
import importlib.util
import numpy as np
import pandas as pd
import yaml

spec = importlib.util.spec_from_file_location("ex", os.path.join(CODE, "scripts", "examen_du_jour.py"))
ex = importlib.util.module_from_spec(spec); spec.loader.exec_module(ex)
START = pd.Timestamp(os.environ.get("PRED_DEPART", "2025-10-01"))
OUT = os.environ.get("PRED_SORTIE", "reports/verdict_12_mois.json")


def rejouer(name, path, stats, meta, kw, agent_path, cross_folder, fred):
    from src.aurexis_data import load_m15, build_market_frame
    from src.features import normalize_features
    from src.trading_env import TradingEnv
    from src.backtester import run_episode
    from stable_baselines3 import PPO
    from stable_baselines3.common.vec_env import DummyVecEnv
    cols, ctx = meta["feature_columns"], meta.get("context_timeframes") or []
    m15 = load_m15(path)
    i0 = int(np.searchsorted(m15["time"].to_numpy(), np.datetime64(START)))
    if i0 < 1500:
        return None, [], {"erreur": "historique insuffisant"}
    src = m15.iloc[max(0, i0 - ex.WARMUP):].reset_index(drop=True)
    from src.trend_vision import daily_closes
    df = build_market_frame(name, src, ctx, cross_folder, fred=fred, toolbox=any(str(c).startswith("tb_") for c in cols),
                            daily=daily_closes(m15))          # tendances de fond : historique complet du marché
    df = df[df["time"] >= START].reset_index(drop=True)
    df[cols] = df[cols].replace([np.inf, -np.inf], np.nan).ffill().fillna(0.0)
    dfn, _ = normalize_features(df, stats=stats, columns=cols)
    dfn[cols] = dfn[cols].astype("float32")
    from src.aurexis_data import add_cost_column
    add_cost_column(dfn, name, float(kw.get("transaction_cost", 0.0002)))      # frais propres au marché
    env = TradingEnv(dfn, feature_columns=cols, style=ex.STYLE, **kw)

    class _A:
        model = PPO.load(agent_path, env=DummyVecEnv([lambda: env]), device="cpu")
    env = run_episode(_A(), env)
    eq = np.asarray(env.equity_curve, dtype=float)
    risks = [t.get("risk") for t in env.trade_log if t.get("risk")]
    times, last = dfn["time"].to_numpy(), len(dfn) - 1
    trades = [{"marche": name, "ouvert": times[int(t["open_step"])], "ferme": times[min(int(t["step"]) + 1, last)],
               "risque": float(t["risk"]), "resultat": float(t["pnl_pct"]) - float(t.get("cost_pct", 0.0))}
              for t in env.trade_log if t.get("open_step") is not None and t.get("risk")]
    return ex.jours_du_compte(eq, dfn["time"], int(env.window_size)), trades, {
        "rendement": float(eq[-1] / eq[0] - 1), "trades": len(env.trade_log), "baisse_max": float(env.max_drawdown),
        "risque_moyen": float(np.mean(risks)) if risks else None,
        "tailles": {f"{r:.2%}": int(sum(1 for x in risks if abs(x - r) < 1e-9)) for r in sorted(set(risks))}}


def challenges(daily: pd.Series, horizon=120):
    r = daily.to_numpy(); out = {"reussi": 0, "rate": 0, "en_cours": 0}; jours = []
    for s in range(len(r)):
        bal, res = 1.0, "en_cours"
        for k in range(s, min(len(r), s + horizon)):
            if r[k] <= -0.05: res = "rate"; break
            bal *= 1 + r[k]
            if bal <= 0.90: res = "rate"; break
            if bal >= 1.10: res = "reussi"; jours.append(k - s + 1); break
        if res == "en_cours" and s + horizon > len(r):
            continue                                   # pas assez de jours pour conclure : départ ignoré
        out[res] += 1
    n = sum(out.values())
    return {k: (v / n if n else 0.0) for k, v in out.items()} | {"departs": n,
            "jours_median": float(np.median(jours)) if jours else None}


def compte_fidele(trades: list, frein: bool, jours_index) -> dict:
    """Trades de tous les marchés rejoués sur un seul compte (src/aurexis_live.replay_account) ; jours sans clôture = 0."""
    from src.aurexis_live import replay_account
    r = replay_account(trades, brake=frein)
    j = pd.Series({pd.Timestamp(k): v for k, v in r.pop("jours").items()}, dtype=float)
    idx = pd.DatetimeIndex(jours_index).normalize().union(j.index).unique().sort_values()
    daily = j.reindex(idx).fillna(0.0)
    monthly = (1 + daily).groupby(daily.index.to_period("M")).prod() - 1
    return r | {"pire_jour": float(daily.min()) if len(daily) else 0.0, "challenge": challenges(daily),
                "mois": {str(k): float(v) for k, v in monthly.items()}}


def main():
    import torch; torch.set_num_threads(2)
    from src.lockbox_gate import eval_env_kwargs
    from src.episodic_memory import EpisodicMemory
    from src.aurexis_data import load_market_stats
    from src.multi_timeframe import discover_files
    cfg = yaml.safe_load(open("../run_config_A.yaml", encoding="utf-8"))
    d = os.environ.get("PRED_MODELE") or os.path.join("models", "champion_AUREXIS")
    meta = json.load(open(os.path.join(d, "meta.json"), encoding="utf-8"))
    cols = meta["feature_columns"]
    kw = eval_env_kwargs("AUREXIS", cfg, meta)
    mem = EpisodicMemory(cfg["memory"]["db_path"], cfg["memory"]["max_episodes"], private_styles=cfg["memory"].get("private_styles"))
    kw.update(memory_snapshot=mem.snapshot(dim=len(cols), sources=["backtest"], style="AUREXIS"),
              memory_top_k=cfg.get("memory", {}).get("similarity_top_k", 5))
    cross_folder = os.path.join(os.path.dirname(os.path.abspath(cfg["data"]["folder"])), "cross_asset")
    fred = None
    try:
        from src.fundamental_feed import AutoFundamentalFeed
        fred = getattr(AutoFundamentalFeed(cfg), "_fred", None)
    except Exception:
        pass
    gold_stats = {c: tuple(v) for c, v in json.load(open(os.path.join(d, "norm_stats.json"), encoding="utf-8")).items()}
    jobs = [("XAUUSD", discover_files(cfg["data"]["folder"])["M15"], gold_stats)]
    for n, p in cfg["multi_market"]["markets"].items():
        st = (load_market_stats(n) or {}).get("stats")
        if os.path.exists(p) and st:
            jobs.append((n, p, st))
    print(f"{len(jobs)} marchés", flush=True)
    jours, res, tous = {}, {}, []
    for n, p, st in jobs:
        ex._wait_memory()
        t0 = time.time()
        try:
            s, tr, r = rejouer(n, p, st, meta, kw, os.path.join(d, "agent"), cross_folder, fred)
        except Exception as e:
            s, tr, r = None, [], {"erreur": f"{type(e).__name__}: {e}"}
        if s is not None:
            jours[n] = s
            tous.extend(tr)
        res[n] = r
        print(f"{n:8s} {time.time() - t0:5.0f}s {r}", flush=True)
        gc.collect()
        json.dump({"marches": res}, open(OUT, "w", encoding="utf-8"), indent=1, default=str)
    daily = pd.concat(list(jours.values()), axis=1).fillna(0.0).sum(axis=1).sort_index()
    eq = np.cumprod(1 + daily.to_numpy())
    monthly = (1 + daily).groupby(daily.index.to_period("M")).prod() - 1
    peak = np.maximum.accumulate(np.r_[1.0, eq])[1:]
    rep = {"depart": str(START.date()), "champion": {"generation": meta.get("generation"), "score": meta.get("score")},
           "compte_total": float(eq[-1] - 1), "mois": {str(k): float(v) for k, v in monthly.items()},
           "pire_jour": float(daily.min()), "baisse_max": float(np.max(1 - eq / peak)),
           "jours_sous_moins_2pct": int((daily < -0.02).sum()), "challenge": challenges(daily), "marches": res}
    # 10/10 : VERDICT FIDÈLE -- les mêmes trades rejoués sur UN compte comme le vrai (budget de risque 4 %, murs du jour
    # et total), sans puis avec le frein de baisse. L'addition simple ci-dessus ignore le budget : elle exagère la baisse.
    for cle, frein in (("compte_fidele", False), ("compte_fidele_frein", True)):
        rep[cle] = compte_fidele(tous, frein, daily.index)
    rep["execute_le"] = time.strftime("%Y-%m-%d %H:%M")
    json.dump(rep, open(OUT, "w", encoding="utf-8"), indent=1, default=str)
    hist_path = OUT.replace(".json", "_historique.json")
    try:
        hist = json.load(open(hist_path, encoding="utf-8"))
    except (OSError, ValueError):
        hist = []
    hist.append({k: rep[k] for k in ("execute_le", "champion", "compte_total", "baisse_max", "pire_jour", "challenge",
                                     "compte_fidele", "compte_fidele_frein")})
    json.dump(hist[-120:], open(hist_path, "w", encoding="utf-8"), indent=1, default=str)
    print(json.dumps({k: v for k, v in rep.items() if k != "marches"}, indent=1, default=str), flush=True)


if __name__ == "__main__":
    main()
