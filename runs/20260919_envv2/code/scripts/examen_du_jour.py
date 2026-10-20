"""
EXAMEN DU JOUR d'AUREXIS (09/10/2026, accord de l'utilisateur) -- lecture seule, ne modifie aucun modèle.

La preuve qui manquait : l'examen de la sélection rejoue toujours la même période (2023), donc un champion stable ne
prouve pas qu'il tiendra sur des jours qu'il n'a jamais vus. Chaque soir :
  1. on récupère les VRAIES cotations des derniers jours (Dukascopy) pour l'or et tous les marchés d'AUREXIS
     (dossier séparé data/examen_du_jour/ : les fichiers d'entraînement ne sont jamais touchés) ;
  2. le champion AUREXIS du moment rejoue TOUS les marchés depuis le 09/10/2026 (jours qu'aucune IA n'a vus), avec
     exactement sa vision d'entraînement (statistiques enregistrées par l'entraînement, src/aurexis_data.py) ;
  3. un SEUL compte trade tout en même temps, jour par jour (vraies dates, cette fois) : gain cumulé, pire jour,
     plus forte baisse, verdict FTMO (mur -5 % sur un jour, -10 % au total, objectif +10 %) ;
  4. résultat dans reports/examen_du_jour.json + une notification courte sur le téléphone.

Aucun ordre n'est passé. Calcul sur le processeur, un marché à la fois, attend si la mémoire libre est basse.

    python scripts/examen_du_jour.py [--sans-telechargement]        (cwd = code/)
Tâche Windows « TestIA_ExamenDuJour » : tous les soirs à 22h30.
"""
import gc, json, os, sys, time

os.environ.setdefault("CUDA_VISIBLE_DEVICES", "-1")
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import numpy as np
import pandas as pd
import yaml

STYLE = "AUREXIS"
START = pd.Timestamp(os.environ.get("EXAMEN_DEPART", "2026-10-09"))   # premier jour jamais vu
WARMUP = 3000                                                          # chauffe des indicateurs, comme l'entraînement
DATA_DIR = "C:/Users/utilisateur/Documents/Test_IA/data/examen_du_jour"
REPORT = os.environ.get("EXAMEN_RAPPORT") or os.path.join("reports", "examen_du_jour.json")
ESSAI = bool(os.environ.get("EXAMEN_ESSAI"))      # essai : pas de notification, marchés limités (EXAMEN_MARCHES)
DAILY_LIMIT, TOTAL_LIMIT, TARGET = 0.05, 0.10, 0.10


def portefeuille(par_marche: dict) -> dict:
    """Un compte qui trade tous les marchés en même temps : rendement du jour = somme des rendements du jour de chaque
    marché (vraies dates). Retourne courbe, pire jour, plus forte baisse et verdict FTMO."""
    series = [s for s in par_marche.values() if s is not None and len(s)]
    if not series:
        return {"jours": {}, "compte": 0.0, "pire_jour": 0.0, "baisse_max": 0.0, "verdict": "pas encore de jour complet"}
    daily = pd.concat(series, axis=1).fillna(0.0).sum(axis=1).sort_index()
    eq = np.cumprod(1.0 + daily.to_numpy())
    peak = np.maximum.accumulate(np.r_[1.0, eq])[1:]
    dd = float(np.max(1.0 - eq / peak)) if len(eq) else 0.0
    verdict = "en cours"
    for d, r, e in zip(daily.index, daily.to_numpy(), eq):
        if r <= -DAILY_LIMIT:
            verdict = f"RATÉ le {pd.Timestamp(d):%d/%m} (journée à {r:+.1%})"; break
        if e <= 1 - TOTAL_LIMIT:
            verdict = f"RATÉ le {pd.Timestamp(d):%d/%m} (perte totale {e - 1:+.1%})"; break
        if e >= 1 + TARGET:
            verdict = f"RÉUSSI le {pd.Timestamp(d):%d/%m} (+{e - 1:.1%})"; break
    return {"jours": {f"{pd.Timestamp(d):%Y-%m-%d}": round(float(r), 6) for d, r in daily.items()},
            "compte": float(eq[-1] - 1.0), "pire_jour": float(daily.min()), "baisse_max": dd, "verdict": verdict}


def message(rep: dict) -> str:
    pf, pm = rep["compte"], rep["par_marche"]
    jours = pf["jours"]
    last = list(jours.items())[-1] if jours else None
    ranked = sorted(((k, v["rendement"]) for k, v in pm.items() if "rendement" in v), key=lambda x: x[1])
    best = ", ".join(f"{k} {v:+.1%}" for k, v in ranked[::-1][:3] if v > 0) or "aucun"
    worst = ", ".join(f"{k} {v:+.1%}" for k, v in ranked[:3] if v < 0) or "aucun"
    n_tr = sum(v.get("trades", 0) for v in pm.values())
    txt = (f"Examen du jour AUREXIS (jours jamais vus depuis le {START:%d/%m}) : compte tous marchés "
           f"{pf['compte']:+.2%}")
    if last:
        txt += f" (dernier jour {last[0][8:10]}/{last[0][5:7]} : {last[1]:+.2%})"
    txt += (f", pire jour {pf['pire_jour']:+.2%}, plus forte baisse {pf['baisse_max']:.2%}, {n_tr} trades. "
            f"Challenge FTMO : {pf['verdict']}. Meilleurs : {best}. Moins bons : {worst}.")
    return txt


def _free_gb() -> float:
    import ctypes

    class MS(ctypes.Structure):
        _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
    m = MS(); m.dwLength = ctypes.sizeof(MS)
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
    return m.ullAvailPageFile / 1e9


def _wait_memory(min_gb=1.5, max_wait_s=900):
    t0 = time.time()
    while _free_gb() < min_gb and time.time() - t0 < max_wait_s:
        time.sleep(20)


def telecharger(symbols: dict) -> None:
    """Cotations récentes (depuis ~2 mois avant le départ, pour la chauffe) -> data/examen_du_jour/<SYM>_M15.csv."""
    import importlib.util
    from datetime import date
    spec = importlib.util.spec_from_file_location("fetch_dukascopy", os.path.join("scripts", "fetch_dukascopy.py"))
    fd = importlib.util.module_from_spec(spec); spec.loader.exec_module(fd)
    os.makedirs(DATA_DIR, exist_ok=True)
    today = date.today()
    first = (START - pd.Timedelta(days=75)).date()
    months, y, m = [], first.year, first.month
    while (y, m) <= (today.year, today.month):
        months.append((y, m)); y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    for name, sym in symbols.items():
        if name == "XAUUSD":                 # or : fichier d'entraînement déjà à jour (voir rejouer)
            continue
        try:
            parts = [fd.fetch_month(sym, y, m, today) for (y, m) in months]
            allm = pd.concat([p for p in parts if len(p)]).drop_duplicates("time").sort_values("time")
            allm["time"] = fd.utc_to_server(allm["time"])
            allm.to_csv(os.path.join(DATA_DIR, f"{sym}_M15.csv"), index=False)
            print(f"{name:8s} : cotations jusqu'au {allm['time'].max()}", flush=True)
        except Exception as e:
            print(f"{name:8s} : téléchargement impossible ({type(e).__name__}: {e})", flush=True)


def rejouer(name, sym, stats, meta, cfg, kw, agent_path, cross_folder, fred) -> dict:
    from src.aurexis_data import load_m15, build_market_frame
    from src.features import normalize_features
    from src.trading_env import TradingEnv
    from src.backtester import run_episode
    from stable_baselines3 import PPO
    from stable_baselines3.common.vec_env import DummyVecEnv
    cols, ctx = meta["feature_columns"], meta.get("context_timeframes") or []
    path = os.path.join(DATA_DIR, f"{sym}_M15.csv")
    if name == "XAUUSD":                     # or : le fichier d'entraînement, mis à jour en continu (même source)
        from src.multi_timeframe import discover_files
        path = discover_files(cfg["data"]["folder"]).get("M15") or path
    if not os.path.exists(path):
        return {"erreur": "pas de cotations"}
    m15 = load_m15(path)
    i0 = int(np.searchsorted(m15["time"].to_numpy(), np.datetime64(START)))
    if i0 < WARMUP // 2:
        return {"erreur": f"historique trop court avant le départ ({i0} bougies)"}
    src = m15.iloc[max(0, i0 - WARMUP):].reset_index(drop=True)
    from src.trend_vision import daily_closes
    longue = m15                                   # tendances de fond : historique complet + cotations récentes
    hist = ((cfg.get("multi_market") or {}).get("markets") or {}).get(name)
    if name != "XAUUSD" and hist and os.path.exists(hist):
        longue = pd.concat([load_m15(hist), m15]).drop_duplicates("time").sort_values("time")
    df = build_market_frame(name, src, ctx, cross_folder, fred=fred,
                            toolbox=any(str(c).startswith("tb_") for c in cols), daily=daily_closes(longue))
    df = df[df["time"] >= START].reset_index(drop=True)
    if len(df) < int(kw.get("window_size", 50)) + 8:
        return {"erreur": f"pas encore assez de bougies ({len(df)})"}
    df[cols] = df[cols].replace([np.inf, -np.inf], np.nan).ffill().fillna(0.0)
    dfn, _ = normalize_features(df, stats=stats, columns=cols)
    dfn[cols] = dfn[cols].astype("float32")
    from src.aurexis_data import add_cost_column
    add_cost_column(dfn, name, float(kw.get("transaction_cost", 0.0002)), cfg)   # frais propres au marché
    env = TradingEnv(dfn, feature_columns=cols, style=STYLE, **kw)

    class _Agent:
        model = PPO.load(agent_path, env=DummyVecEnv([lambda: env]), device="cpu")
    env = run_episode(_Agent(), env)
    eq = np.asarray(env.equity_curve, dtype=float)
    return {"rendement": float(eq[-1] / eq[0] - 1.0), "trades": len(env.trade_log),
            "baisse_max": float(env.max_drawdown), "bougies": len(dfn),
            "jusqu_au": str(dfn["time"].iloc[-1]), "_jours": jours_du_compte(eq, dfn["time"], int(env.window_size))}


def jours_du_compte(equity, times, window_size: int) -> pd.Series:
    """Rendement de CHAQUE jour (premier jour compris, mesuré depuis le capital de départ), indexé par date."""
    eq = np.asarray(equity, dtype=float)
    t = pd.to_datetime(pd.Series(times)).iloc[max(0, window_size - 1):].reset_index(drop=True)
    n = min(len(eq), len(t))
    if n < 2:
        return pd.Series(dtype=float)
    s = pd.Series(eq[:n], index=t.iloc[:n].to_numpy())
    last = s.groupby(s.index.normalize()).last()
    prev = last.shift(1).fillna(eq[0])
    return last / prev - 1.0


def main(download: bool = True):
    import torch
    torch.set_num_threads(2)
    from src.lockbox_gate import eval_env_kwargs
    from src.agent import env_version_matches
    from src.episodic_memory import EpisodicMemory
    from src.aurexis_data import load_market_stats
    cfg = yaml.safe_load(open("../run_config_A.yaml", encoding="utf-8"))
    d = os.path.join("models", f"champion_{STYLE}")
    meta = json.load(open(os.path.join(d, "meta.json"), encoding="utf-8"))
    assert env_version_matches(meta), "version d'environnement différente : examen impossible"
    cols = meta["feature_columns"]
    markets = (cfg.get("multi_market") or {}).get("markets") or {}
    symbols = {"XAUUSD": "XAUUSD"}
    symbols.update({n: os.path.basename(p).split("_M15")[0] for n, p in markets.items()
                    if "fx_intraday" in p.replace("\\", "/")})
    if "GBPUSD" in markets and "GBPUSD" not in symbols:
        symbols["GBPUSD"] = "GBPUSD"
    if os.environ.get("EXAMEN_MARCHES"):
        keep = os.environ["EXAMEN_MARCHES"].split(",")
        symbols = {k: v for k, v in symbols.items() if k in keep}
    if download:
        telecharger(symbols)
    data_cfg = cfg["data"]
    cross_folder = data_cfg.get("cross_asset_folder") or os.path.join(
        os.path.dirname(os.path.abspath(data_cfg.get("folder", "."))), "cross_asset")
    fred = None
    try:
        from src.fundamental_feed import AutoFundamentalFeed
        fred = getattr(AutoFundamentalFeed(cfg), "_fred", None)
    except Exception:
        pass
    kw = eval_env_kwargs(STYLE, cfg, meta)
    mem = EpisodicMemory(cfg["memory"]["db_path"], cfg["memory"]["max_episodes"],
                         private_styles=cfg["memory"].get("private_styles"))
    kw.update(memory_snapshot=mem.snapshot(dim=len(cols), sources=["backtest"], style=STYLE),
              memory_top_k=cfg.get("memory", {}).get("similarity_top_k", 5))
    gold_stats = {c: tuple(v) for c, v in json.load(open(os.path.join(d, "norm_stats.json"), encoding="utf-8")).items()}
    par_marche, jours = {}, {}
    for name, sym in symbols.items():
        _wait_memory()
        st = gold_stats if name == "XAUUSD" else (load_market_stats(name) or {}).get("stats")
        if not st:
            par_marche[name] = {"erreur": "statistiques d'entraînement absentes (marché pas encore entraîné)"}
            continue
        try:
            r = rejouer(name, sym, st, meta, cfg, kw, os.path.join(d, "agent"), cross_folder, fred)
        except Exception as e:
            r = {"erreur": f"{type(e).__name__}: {e}"}
        s = r.pop("_jours", None)
        if s is not None:
            jours[name] = s
        par_marche[name] = r
        print(f"{name:8s} : {r}", flush=True)
        gc.collect()
    rep = {"execute_le": time.strftime("%Y-%m-%d %H:%M"), "depart": str(START.date()),
           "champion": {"generation": meta.get("generation"), "score": meta.get("score"),
                        "mis_a_jour": meta.get("updated_at")},
           "compte": portefeuille(jours), "par_marche": par_marche}
    hist = []
    if os.path.exists(REPORT):
        try:
            hist = json.load(open(REPORT, encoding="utf-8")).get("historique", [])
        except (OSError, ValueError):
            hist = []
    hist = (hist + [rep])[-90:]
    os.makedirs("reports", exist_ok=True)
    json.dump({"dernier": rep, "historique": hist}, open(REPORT, "w", encoding="utf-8"), indent=1, default=str)
    try:                                           # carnet de résultats par marché, reconstruit chaque soir
        import importlib.util as _iu
        _s = _iu.spec_from_file_location("carnet_marches", os.path.join("scripts", "carnet_marches.py"))
        _c = _iu.module_from_spec(_s); _s.loader.exec_module(_c); _c.main()
    except Exception as e:
        print(f"(carnet des marchés non mis à jour : {e})", flush=True)
    txt = message(rep)
    print(txt, flush=True)
    if ESSAI:
        return
    try:
        from src.notifier import send_alert
        send_alert(cfg, subject="AUREXIS - examen du jour", message=txt)
    except Exception as e:
        print(f"(notification impossible : {e})", flush=True)


if __name__ == "__main__":
    os.chdir(os.environ.get("EXAMEN_CODE") or os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    main(download="--sans-telechargement" not in sys.argv)
