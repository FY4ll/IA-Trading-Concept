"""
JUGE DES TRADES D'AUREX (07/10/2026) -- recherche, lecture seule (aucun modèle modifié).

AUREX garde ses décisions ; un second modèle (gradient boosting, apprentissage supervisé) estime pour chaque
trade qu'AUREX veut ouvrir la probabilité qu'il finisse gagnant, à partir du contexte de marché (les 114 variables
d'AUREX) et de la confiance d'AUREX lui-même. Trade sous le seuil -> non pris.

Protocole honnête :
  1. AUREX rejoué sur l'or 2010 -> aujourd'hui (même environnement que la lockbox : taille au risque 0,5 %),
     chaque trade enregistré (contexte à la décision, confiance, choix, résultat en R) ;
  2. le juge apprend UNIQUEMENT sur les trades d'avant le 01/10/2018 (période jamais vue par l'entraînement
     d'AUREX : ses résultats y sont réels) ;
  3. seuil choisi sur la validation (01/11/2021 -> 31/05/2023) ;
  4. examen sur la lockbox (01/06/2023 ->) : AUREX seul contre AUREX + juge, même risque, mêmes critères FTMO.

    python scripts/aurex_judge.py            (cwd = code/)  -> reports/aurex_judge.json
"""
import json, os, sys, time
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
os.chdir(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import numpy as np, pandas as pd, yaml

TRAIN_END = pd.Timestamp("2018-10-01")
VAL_START, VAL_END = pd.Timestamp("2021-11-01"), pd.Timestamp("2023-05-31")
HIST_START = pd.Timestamp("2010-01-01")
RISK_UNIT = 0.005          # risque par trade de l'environnement (risk_sizing_pct d'AUREX)


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def head_logits(head, hidden, extra):
    x = np.concatenate([hidden, extra]).astype(np.float64)
    for kind, a, b in head.layers:
        x = x @ a + b if kind == "lin" else a(x)
    return x


def replay(agent, env):
    """Rejoue AUREX (décisions identiques à run_episode_fast) en enregistrant chaque trade."""
    from src.fast_eval import precompute_lstm, _NumpyHead
    pol = agent.model.policy
    pol.set_training_mode(False)
    hidden = precompute_lstm(pol.features_extractor, env._feature_values, env.window_size).numpy().astype(np.float64)
    head = _NumpyHead(pol)
    seq_len = env.window_size * env.n_features
    env.reset()
    trades, open_rec, n_logged = [], None, 0
    times = pd.to_datetime(env.df["time"]).to_numpy()
    done = False
    while not done:
        t = env.current_step
        extra = env._get_obs()[seq_len:]
        x = head_logits(head, hidden[t], extra)
        parts = np.split(x, head.splits)
        action = np.array([int(np.argmax(p)) for p in parts])
        d = np.exp(parts[0] - parts[0].max()); d /= d.sum()          # short / flat / long
        pos_before = env.position
        _, _, term, trunc, _ = env.step(action)
        done = term or trunc
        closed_now = len(env.trade_log) > n_logged
        if closed_now:                            # clôture(s) pendant ce pas
            for tr in env.trade_log[n_logged:]:
                if open_rec is not None:
                    open_rec["R"] = float(tr["pnl_pct"]) / RISK_UNIT
                    open_rec["stopped"] = bool(tr["stopped_out"])
                    trades.append(open_rec)
                    open_rec = None
            n_logged = len(env.trade_log)
        # nouvelle position : depuis plat, retournement, OU réouverture dans le même pas qu'une clôture (stop/objectif)
        if env.position != 0 and (pos_before == 0 or np.sign(pos_before) != np.sign(env.position) or closed_now):
            sp = (env._initial_risk / env.entry_price) if env._initial_risk and env.entry_price else np.nan
            open_rec = {"t": int(t), "time": times[t], "dir": int(np.sign(env.position)),
                        "p_short": float(d[0]), "p_flat": float(d[1]), "p_long": float(d[2]),
                        "stop_idx": int(action[1]), "tp_idx": int(action[2]) if len(action) > 2 else -1,
                        "order_idx": int(action[3]) if len(action) > 3 else -1, "stop_pct": float(sp),
                        "feat": env._feature_values[t].astype(np.float32)}
    return trades


def _add_trend(trs, raw):
    for tr in trs:
        for col, key in (("D1_trend_signal", "d1"), ("H4_trend_signal", "h4")):
            tr[key] = float(raw[col].iloc[tr["t"]]) if col in raw.columns else np.nan


def trend_report(groups):
    """Discipline de tendance : R moyen des trades d'AUREX dans le sens de la tendance D1 / H4 / des deux, par période."""
    out = {}
    for gname, trs in groups.items():
        if not trs:
            continue
        R = np.array([t["R"] for t in trs]); dr = np.array([t["dir"] for t in trs])
        d1 = np.array([t["d1"] for t in trs]); h4 = np.array([t["h4"] for t in trs])
        tm = pd.to_datetime([t["time"] for t in trs])
        rules = {"tous": np.ones(len(R), bool), "achats": dr > 0, "ventes": dr < 0,
                 "sens D1": dr * d1 > 0, "sens H4": dr * h4 > 0, "sens D1 et H4": (dr * d1 > 0) & (dr * h4 > 0),
                 "contre D1": dr * d1 < 0}
        out[gname] = {}
        for rn, m in rules.items():
            order = np.argsort(tm[m])
            out[gname][rn] = r_stats(R[m][order], tm[m][order]) if m.sum() else {"n": 0}
            s = out[gname][rn]
            if s.get("n"):
                log(f"[{gname}] {rn:14s}: {s['n']:5d} trades, réussite {s['win_rate']:.0%}, R moyen {s['avg_R']:+.3f}, "
                    f"tiers {[round(x, 3) for x in s['thirds_avg_R']]}, DD {s['max_dd']:.1%}")
    return out


def r_stats(R, times, risk=0.0025):
    from src.ftmo_metrics import prop_firm_summary
    R = np.asarray(R, float)
    if len(R) == 0:
        return {"n": 0}
    eq = np.cumprod(1 + risk * R)
    days = pd.to_datetime(times).normalize()
    daily = pd.Series(risk * R, index=days).groupby(level=0).sum()
    daily = daily.reindex(pd.bdate_range(days.min(), days.max()), fill_value=0.0)
    months = max(1.0, (days.max() - days.min()).days / 30.4)
    thirds = [float(x.mean()) for x in np.array_split(R, 3)]
    return {"n": int(len(R)), "win_rate": float((R > 0).mean()), "avg_R": float(R.mean()), "thirds_avg_R": thirds,
            "return": float(eq[-1] - 1), "monthly": float(eq[-1] ** (1 / months) - 1),
            "max_dd": float(-(eq / np.maximum.accumulate(eq) - 1).min()), "worst_day": float(daily.min()),
            "ftmo_challenge": prop_firm_summary(daily.to_numpy()).get("challenge_pass")}


def main():
    from src.risk_profile import apply_risk_profile
    from src.lockbox_gate import build_eval_frames, eval_env_kwargs
    from src.features import normalize_features
    from src.trading_env import TradingEnv
    from src.agent import TradingAgent
    from sklearn.ensemble import HistGradientBoostingClassifier
    cfg = yaml.safe_load(open("../run_config_A.yaml", encoding="utf-8"))
    apply_risk_profile(cfg)
    style = next((x for x in sys.argv[1:] if not x.startswith("--")), "AUREX")
    d = f"models/champion_{style}"
    meta = json.load(open(f"{d}/meta.json", encoding="utf-8"))
    stats = {k: tuple(v) for k, v in json.load(open(f"{d}/norm_stats.json", encoding="utf-8")).items()}
    cols = meta["feature_columns"]
    t0 = time.time()
    vis, lock, start = build_eval_frames(style, cfg, meta)
    vis = vis[pd.to_datetime(vis["time"]) >= HIST_START].reset_index(drop=True)
    log(f"données : historique {len(vis)} bougies (2010 -> lockbox), lockbox {len(lock)} ({time.time() - t0:.0f}s)")
    kw = eval_env_kwargs(style, cfg, meta)
    all_trades = {}
    for name, raw in (("hist", vis), ("lock", lock)):
        raw = raw.reset_index(drop=True)
        dfn, _ = normalize_features(raw, stats=stats, columns=cols)
        env = TradingEnv(dfn, feature_columns=cols, style=style, **kw)
        agent = TradingAgent.load(f"{d}/agent", env, {"algo": "PPO"})
        all_trades[name] = replay(agent, env)
        _add_trend(all_trades[name], raw)
        log(f"{name} : {len(all_trades[name])} trades d'AUREX enregistrés ({time.time() - t0:.0f}s)")
        del dfn, env

    # MULTI-MARCHÉS (AUREXIS) : le même agent rejoué sur les autres marchés, AVANT le début de la validation de
    # l'or (aucune fuite vers la validation ni la lockbox) -> beaucoup plus d'exemples pour le juge.
    other = []
    if "--multi" in sys.argv:
        from src.aurexis_data import load_m15, build_market_frame
        from src.fundamental_feed import AutoFundamentalFeed
        fred = getattr(AutoFundamentalFeed(cfg), "_fred", None)
        data_cfg = cfg.get("data", {})
        cross_folder = data_cfg.get("cross_asset_folder") or os.path.join(
            os.path.dirname(os.path.abspath(data_cfg.get("folder", "."))), "cross_asset")
        cut = VAL_START - pd.Timedelta(hours=48)
        for sym, path in ((cfg.get("multi_market") or {}).get("markets") or {}).items():
            try:
                m15 = load_m15(path)
                m15 = m15[m15["time"] < cut].reset_index(drop=True)
                fr = build_market_frame(sym, m15, meta.get("context_timeframes") or [], cross_folder, fred=fred)
                fr = fr.iloc[3000:].reset_index(drop=True)
                fr[cols] = fr[cols].replace([np.inf, -np.inf], np.nan).ffill().fillna(0.0)
                frn, _ = normalize_features(fr, columns=cols)       # statistiques propres au marché (comme à l'entraînement)
                env = TradingEnv(frn, feature_columns=cols, style=style, **kw)
                agent = TradingAgent.load(f"{d}/agent", env, {"algo": "PPO"})
                trs = replay(agent, env)
                _add_trend(trs, fr)
                for tr in trs:
                    tr["market"] = sym
                other += trs
                log(f"{sym} : {len(trs)} trades enregistrés ({time.time() - t0:.0f}s)")
            except Exception as e:
                log(f"{sym} : impossible ({type(e).__name__}: {e})")

    def frame(trs):
        X = np.stack([np.concatenate([tr["feat"], [tr["p_short"], tr["p_flat"], tr["p_long"], tr["dir"],
                                                   tr["stop_idx"], tr["tp_idx"], tr["order_idx"], tr["stop_pct"]]])
                      for tr in trs]) if trs else np.zeros((0, len(cols) + 8))
        y = np.array([tr["R"] for tr in trs]); tm = pd.to_datetime([tr["time"] for tr in trs])
        return X, y, tm

    hist = all_trades["hist"]
    groups = {"or 2010-2018": [t for t in hist if pd.Timestamp(t["time"]) < TRAIN_END],
              "or validation 2021-2023": [t for t in hist if VAL_START <= pd.Timestamp(t["time"]) <= VAL_END],
              "or lockbox 2023-2026": all_trades["lock"]}
    for sym in sorted({t.get("market") for t in other}):
        groups[f"{sym} (jamais vu)"] = [t for t in other if t.get("market") == sym]
    trend = trend_report(groups)
    Xh, yh, th = frame(all_trades["hist"])
    Xl, yl, tl = frame(all_trades["lock"])
    tr_m = th < TRAIN_END
    va_m = (th >= VAL_START) & (th <= VAL_END)
    log(f"trades : apprentissage {tr_m.sum()} (avant {TRAIN_END.date()}), validation {va_m.sum()}, lockbox {len(yl)}")
    clf = HistGradientBoostingClassifier(max_iter=300, learning_rate=0.03, max_leaf_nodes=15, min_samples_leaf=60,
                                         l2_regularization=1.0, random_state=0)
    Xtr, ytr = Xh[tr_m], yh[tr_m]
    if other:
        Xo, yo, _ = frame(other)
        Xtr, ytr = np.vstack([Xtr, Xo]), np.concatenate([ytr, yo])
        log(f"exemples d'apprentissage du juge : {tr_m.sum()} or + {len(yo)} autres marchés ; R moyen autres marchés {yo.mean():+.3f}")
        res_other = r_stats(yo, pd.to_datetime([tr["time"] for tr in other]).sort_values())
    else:
        res_other = None
    clf.fit(Xtr, (ytr > 0).astype(int))
    pv = clf.predict_proba(Xh[va_m])[:, 1]
    pl = clf.predict_proba(Xl)[:, 1]
    res = {"aurex_alone": {"validation": r_stats(yh[va_m], th[va_m]), "lockbox": r_stats(yl, tl)},
           "gold_train_period": r_stats(yh[tr_m], th[tr_m]), "other_markets": res_other, "trend_discipline": trend}
    grid = {}
    for q in (0.0, 0.1, 0.2, 0.3, 0.4, 0.5):           # part des trades les moins sûrs écartée
        thr = float(np.quantile(pv, q)) if q > 0 else -1.0
        keep = pv > thr
        grid[q] = {"threshold": thr, "validation": r_stats(yh[va_m][keep], th[va_m][keep])}
        v = grid[q]["validation"]
        log(f"validation : écarte {q:.0%} -> {v['n']} trades, R moyen {v['avg_R']:+.3f}, réussite {v['win_rate']:.0%}")
    base_val = grid[0.0]["validation"]["avg_R"]
    best_q = max(grid, key=lambda q: grid[q]["validation"]["avg_R"] * np.sqrt(grid[q]["validation"]["n"]))
    thr = grid[best_q]["threshold"]
    keep_l = pl > thr
    res.update({"grid": {str(k): v for k, v in grid.items()}, "chosen_drop_share": best_q, "threshold": thr,
                "judge_lockbox": r_stats(yl[keep_l], tl[keep_l]),
                "lockbox_rejected_trades": r_stats(yl[~keep_l], tl[~keep_l])})
    a, j = res["aurex_alone"]["lockbox"], res["judge_lockbox"]
    log(f"seuil retenu sur la validation : écarter {best_q:.0%} des trades (R moyen validation de base {base_val:+.3f})")
    for name, s in (("LOCKBOX AUREX seul", a), ("LOCKBOX AUREX + juge", j), ("trades écartés par le juge", res["lockbox_rejected_trades"])):
        if s.get("n"):
            log(f"{name} : {s['n']} trades, réussite {s['win_rate']:.0%}, R moyen {s['avg_R']:+.3f}, "
                f"tiers {[round(x, 3) for x in s['thirds_avg_R']]}, à 0,25 % : {s['return']:+.1%} "
                f"({s['monthly']:+.2%}/mois), DD {s['max_dd']:.1%}, pire jour {s['worst_day']:+.2%}, FTMO {s['ftmo_challenge']:.0%}")
    os.makedirs("reports", exist_ok=True)
    json.dump(res, open(f"reports/judge_{style}{'_multi' if '--multi' in sys.argv else ''}.json", "w", encoding="utf-8"), indent=1, default=str)
    log(f"terminé en {(time.time() - t0) / 60:.1f} min -> reports/aurex_judge.json")


if __name__ == "__main__":
    main()
