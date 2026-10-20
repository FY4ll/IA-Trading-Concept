"""
EXAMEN PAR MARCHÉ d'AUREXIS (07/10/2026) -- lecture seule, ne modifie aucun modèle.

Le champion AUREXIS apprend sur l'or + d'autres marchés (src/aurexis_data.py), mais n'est examiné que sur l'or.
Ce script le juge sur CHAQUE marché, sur des périodes qu'il n'a jamais vues (son entraînement s'arrête début
novembre 2021), avec EXACTEMENT les mêmes seuils que l'examen final de l'or (validation.lockbox_gate) :
  - période « récente » : du début du jeu sous clé de l'or (juin 2023) à aujourd'hui -- même période que l'or ;
  - période « intermédiaire » : de la fin de son entraînement (nov. 2021) à juin 2023 -- deuxième avis ;
  - marchés MIROIRS (à l'envers) sur la période récente : sait-il gagner quand le marché baisse ?
Chaque marché est normalisé avec les statistiques de SA tranche d'entraînement (comme pendant l'entraînement).

Mémoire : calcul sur le processeur (pas de carte graphique), un marché à la fois ; attend si la mémoire libre de
Windows passe sous 1,5 Go (l'entraînement en cours reste prioritaire).

    set CUDA_VISIBLE_DEVICES= & python scripts/aurexis_market_exam.py          (cwd = code/)
Écrit reports/aurexis_marches.json.
"""
import ctypes, gc, json, os, sys, time

os.environ.setdefault("CUDA_VISIBLE_DEVICES", "")
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
os.chdir(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import numpy as np
import pandas as pd
import yaml

STYLE = "AUREXIS"
TRAIN_END = pd.Timestamp("2021-11-03")      # dernière bougie d'entraînement des autres marchés : 2021-11-02
WARMUP = 3000                               # chauffe des indicateurs longs, comme other_markets_train


def free_commit_gb() -> float:
    class MS(ctypes.Structure):
        _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
    m = MS(); m.dwLength = ctypes.sizeof(MS)
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
    return m.ullAvailPageFile / 1e9


def wait_memory(min_gb: float = 1.5, max_wait_s: int = 900):
    t0 = time.time()
    while free_commit_gb() < min_gb and time.time() - t0 < max_wait_s:
        time.sleep(20)


def frame(symbol, m15, mirror, cfg, cols, ctx, cross_folder, fred):
    from src.aurexis_data import build_market_frame, mirror_m15
    if mirror:
        m15 = mirror_m15(m15)
    df = build_market_frame(symbol, m15.reset_index(drop=True), ctx, cross_folder, fred=fred,
                            toolbox=any(str(c).startswith("tb_") for c in cols))
    df = df.iloc[WARMUP:].reset_index(drop=True)
    df[cols] = df[cols].replace([np.inf, -np.inf], np.nan).ffill().fillna(0.0)
    return df


def normalized(df, stats, cols, mirror):
    from src.features import normalize_features
    dfn, stats = normalize_features(df, stats=stats, columns=cols)
    if mirror:
        neutral = [c for c in cols if c.startswith("x_") or c.startswith(("tv_eur_", "tv_jpy_", "tv_spx_"))]
        dfn[neutral] = 0.0
    dfn[cols] = dfn[cols].astype("float32")
    return dfn, stats


def exam(agent_path, meta, cfg, dfn, raw):
    from src.trading_env import TradingEnv
    from src.backtester import run_episode, compute_metrics
    from src.lockbox_gate import eval_env_kwargs, _thirds_returns, baseline_metrics
    from src.ftmo_metrics import daily_returns, prop_firm_summary
    cols = meta["feature_columns"]
    kw = eval_env_kwargs(STYLE, cfg, meta)
    env = TradingEnv(dfn, feature_columns=cols, style=STYLE, **kw)
    # modèle enregistré depuis la carte graphique : rechargé directement sur le processeur
    from stable_baselines3 import PPO
    from stable_baselines3.common.vec_env import DummyVecEnv
    from src.agent import env_version_matches
    assert env_version_matches(meta), "version d'environnement différente : examen impossible"

    class _Agent:
        model = PPO.load(agent_path, env=DummyVecEnv([lambda: env]), device="cpu")
    agent = _Agent()
    env = run_episode(agent, env)
    m = compute_metrics(env, timeframe="M15")
    out = {"sharpe": float(m["sharpe"]), "max_drawdown": float(m["max_drawdown"]),
           "total_return": float(m["total_return"]), "n_trades": int(m["n_trades"]),
           "profit_factor": float(m["profit_factor"]), "n_bars": int(len(dfn)),
           "start": str(dfn["time"].iloc[0].date()), "end": str(dfn["time"].iloc[-1].date()),
           "thirds_returns": _thirds_returns(env.equity_curve)}
    try:
        out["prop_firm"] = prop_firm_summary(daily_returns(env.equity_curve, env.df["time"]).to_numpy())
        out["baselines"] = baseline_metrics(raw, kw["transaction_cost"])
    except Exception as e:
        print(f"   (mesures FTMO indisponibles : {e})", flush=True)
    mult = float(cfg["validation"]["lockbox_gate"].get("stress_cost_multiplier", 0) or 0)
    if mult > 1:
        env2 = TradingEnv(dfn, feature_columns=cols, style=STYLE, **{**kw, "transaction_cost": kw["transaction_cost"] * mult})
        env2 = run_episode(agent, env2)
        m2 = compute_metrics(env2, timeframe="M15")
        out["stress_return"], out["stress_sharpe"], out["stress_cost_multiplier"] = float(m2["total_return"]), float(m2["sharpe"]), mult
    del agent, env
    return out


def main():
    import torch
    torch.set_num_threads(3)
    from src.aurexis_data import load_m15, DEFAULT_MARKETS
    from src.lockbox_gate import resolve_lockbox_start, gate_decision
    from src.multi_timeframe import discover_files
    cfg = yaml.safe_load(open("../run_config_A.yaml", encoding="utf-8"))
    d = os.environ.get("EXAM_MODEL_DIR") or os.path.join("models", f"champion_{STYLE}")   # copie figée possible
    meta = json.load(open(os.path.join(d, "meta.json"), encoding="utf-8"))
    cols, ctx = meta["feature_columns"], meta.get("context_timeframes") or []
    gate_cfg = cfg["validation"]["lockbox_gate"]
    lock_start = resolve_lockbox_start(cfg)
    data_cfg = cfg["data"]
    cross_folder = data_cfg.get("cross_asset_folder") or os.path.join(
        os.path.dirname(os.path.abspath(data_cfg.get("folder", "."))), "cross_asset")
    fred = None
    try:
        from src.fundamental_feed import AutoFundamentalFeed
        fred = getattr(AutoFundamentalFeed(cfg), "_fred", None)
    except Exception as e:
        print(f"(macro FRED indisponible : {type(e).__name__})", flush=True)
    mm = cfg.get("multi_market") or {}
    markets = dict(mm.get("markets") or DEFAULT_MARKETS)
    gold_path = discover_files(data_cfg["folder"]).get("M15")
    n_train, n_mirror = int(mm.get("max_bars_per_market", 80000)), int(mm.get("mirror_max_bars", 30000))
    jobs = []
    for sym in markets:
        jobs.append((sym, markets[sym], False, "récente", lock_start, None))
        jobs.append((sym, markets[sym], False, "intermédiaire", TRAIN_END + pd.Timedelta(hours=48), lock_start))
    for sym, path in [("XAUUSD", gold_path)] + list(markets.items()):
        jobs.append((sym, path, True, "récente", lock_start, None))

    report = {"generation": meta.get("generation"), "lockbox_start": str(lock_start.date()),
              "or_reel_recente": meta.get("lockbox"), "examens": []}
    out_path = os.path.join("reports", "aurexis_marches.json")
    stats_cache = {}
    for sym, path, mirror, period, start, end in jobs:
        name = f"{sym} miroir" if mirror else sym
        t0 = time.time()
        wait_memory()
        try:
            m15 = load_m15(path)
            key = (sym, mirror)
            if key not in stats_cache:               # statistiques de la tranche d'entraînement de ce marché
                tr = m15[m15["time"] < TRAIN_END].tail((n_mirror if mirror else n_train) + WARMUP)
                df_tr = frame(name, tr, mirror, cfg, cols, ctx, cross_folder, fred)
                _, stats_cache[key] = normalized(df_tr, None, cols, mirror)
                del df_tr, tr; gc.collect()
            i0 = int(np.searchsorted(m15["time"].to_numpy(), np.datetime64(start)))
            sl = m15.iloc[max(0, i0 - WARMUP):]
            if end is not None:
                sl = sl[sl["time"] < end]
            if len(sl) - WARMUP < 5000:
                print(f"{name:14s} {period:13s} : pas assez de données ({max(0, len(sl) - WARMUP)} bougies) -- ignoré", flush=True)
                continue
            raw = frame(name, sl, mirror, cfg, cols, ctx, cross_folder, fred)
            raw = raw[raw["time"] >= start].reset_index(drop=True)
            dfn, _ = normalized(raw, stats_cache[key], cols, mirror)
            del m15, sl; gc.collect()
            r = exam(os.path.join(d, "agent"), meta, cfg, dfn, raw)
            ok, why = gate_decision(r, gate_cfg, None)
            r.update(marche=name, periode=period, examen_ok=ok, raisons=why, minutes=round((time.time() - t0) / 60, 1))
            report["examens"].append(r)
            json.dump(report, open(out_path, "w", encoding="utf-8"), indent=1, default=str)
            pf = r.get("prop_firm") or {}
            bh = ((r.get("baselines") or {}).get("buy_hold") or {}).get("total_return", float("nan"))
            print(f"{name:14s} {period:13s} {r['start']}->{r['end']} : rendement {r['total_return']:+.1%} "
                  f"(marché {bh:+.1%}), Sharpe {r['sharpe']:.2f}, baisse max {r['max_drawdown']:.1%}, "
                  f"{r['n_trades']} trades, coûts x2 {r.get('stress_return', float('nan')):+.1%}, "
                  f"tiers {[round(x, 3) for x in r['thirds_returns']]}, FTMO {pf.get('challenge_pass', 0):.0%} "
                  f"-> {'RÉUSSI' if ok else 'ÉCHOUÉ : ' + why} ({r['minutes']} min)", flush=True)
            del dfn, raw; gc.collect()
        except Exception as e:
            import traceback; traceback.print_exc()
            print(f"{name:14s} {period:13s} : ERREUR {type(e).__name__}: {e}", flush=True)
    print("TERMINÉ", flush=True)


if __name__ == "__main__":
    main()
