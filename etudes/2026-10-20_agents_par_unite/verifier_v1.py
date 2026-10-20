"""Vérification honnête des PREMIERS agents par unité de temps (projet v1, champions du 17/09/2026, commit git b9621f7) :
D1, H4, H1, M30, M15 sur l'or. Lecture seule. Même principe que verifier.py (rejeu exact + jumeaux au hasard).

Le code de l'époque (src/ de b9621f7) est extrait de git dans un dossier à part (`--code`), avec ses modèles et sa
mémoire d'épisodes ; les données sont celles d'aujourd'hui (data/kaggle_gold, prolongées depuis par le flux direct).
Seule différence connue avec l'époque : la note « fondamentale » (actualités en direct) vaut 0 (aucun historique).

Fenêtre vue à l'entraînement (config v1 : max_bars_by_style M15 75 000, H1 50 000, M30 60 000 ; H4 et D1 : tout
l'historique) : les N dernières bougies avant le 17/09/2026. Jamais vu : avant cette fenêtre, et après le 17/09/2026.

    venv_gpu\\Scripts\\python.exe etudes\\2026-10-20_agents_par_unite\\verifier_v1.py H1 --code <dossier v1> [--jumeaux 4]
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

ICI = Path(__file__).resolve().parent
RACINE = ICI.parents[1]
style = sys.argv[1]
CODE = Path(sys.argv[sys.argv.index("--code") + 1])
K = int(sys.argv[sys.argv.index("--jumeaux") + 1]) if "--jumeaux" in sys.argv else 4
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(CODE))
os.chdir(CODE)

import numpy as np
import pandas as pd
import yaml

from core.jumeau import comparer

FIN_V1 = pd.Timestamp("2026-09-17")
FENETRE = {"M15": 75_000, "H1": 50_000, "M30": 60_000}           # H4, D1 : tout l'historique
# temps de calcul (le rejeu v1 lit pandas bougie par bougie) : ~2 ans jamais vus avant chaque fenêtre suffisent
DEBUT_PAR_STYLE = {"M15": pd.Timestamp("2021-06-01"), "M30": pd.Timestamp("2019-07-01"), "H1": pd.Timestamp("2016-01-01")}
# `--seul g` : un seul rejeu (g = 0 : l'agent ; g >= 1 : le jumeau g), courbe écrite dans resultats/v1_courbes/ ;
# `--assembler` : relit les courbes et fait la comparaison (un processus par rejeu = toute la machine).
SEUL = int(sys.argv[sys.argv.index("--seul") + 1]) if "--seul" in sys.argv else None
COURBES = ICI / "resultats" / "v1_courbes"


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def jouer(env, agent, graine):
    rng = np.random.default_rng(graine) if graine is not None else None
    obs, _ = env.reset()
    temps = pd.to_datetime(env.df["time"]).to_numpy()
    t_out, v_out, ouv = [], [], []
    done = False
    while not done:
        t = env.current_step
        action = np.array(agent.predict(obs, deterministic=True)).reshape(-1).copy()
        pos = env.position
        d = {0: -1, 1: 0, 2: 1}[int(action[0])]
        if rng is not None and d != 0 and (pos == 0 or np.sign(pos) != d) and rng.random() < 0.5:
            action[0] = {-1: 2, 1: 0}[d]                         # sens retourné
        obs, _, term, trunc, _ = env.step(action)
        done = term or trunc
        if env.position != 0 and (pos == 0 or np.sign(pos) != np.sign(env.position)):
            ouv.append((temps[t], int(np.sign(env.position))))
        t_out.append(temps[t])
        v_out.append(float(env.equity_curve[-1]))
    return np.asarray(t_out), np.asarray(v_out), ouv


def gains_mensuels(t, v, a, b) -> pd.Series:
    s = pd.Series(v, index=pd.to_datetime(t))
    s = s[(s.index >= a) & (s.index < b)]
    if s.empty:
        return pd.Series(dtype=float)
    return ((s.resample("ME").last() / s.resample("ME").first() - 1) * 100).dropna()


def main():
    from src.multi_timeframe import discover_files, build_mtf_dataset, TF_ORDER
    from src.features import add_technical_features, normalize_features, FEATURE_COLUMNS
    from src.trading_env import TradingEnv
    from src.agent import TradingAgent
    from src.episodic_memory import EpisodicMemory

    cfg = yaml.safe_load(open("config/autonomous.yaml", encoding="utf-8"))
    d = f"models/champion_{style}"
    meta = json.load(open(f"{d}/meta.json", encoding="utf-8"))
    stats = json.load(open(f"{d}/norm_stats.json", encoding="utf-8"))
    cols = meta["feature_columns"]
    files = discover_files(str(RACINE / "data" / "kaggle_gold"))
    ctx = meta.get("context_timeframes") or [tf for tf in TF_ORDER[TF_ORDER.index(style) + 1:] if tf in files]
    t0 = time.time()
    df, _ = build_mtf_dataset(files, primary_tf=style, context_tfs=ctx, max_bars=None)
    df = add_technical_features(df, fundamental_feed=None, refresh_fundamental=False)
    df["time"] = pd.to_datetime(df["time"])
    avant = df[df["time"] < FIN_V1]
    n = FENETRE.get(style)
    debut_fen = avant["time"].iloc[-n] if n and n < len(avant) else avant["time"].iloc[0]
    debut = max(DEBUT_PAR_STYLE.get(style, pd.Timestamp("2010-01-01")), df["time"].iloc[0])
    df = df[df["time"] >= debut - pd.Timedelta(days=30)].reset_index(drop=True)
    dfn, _ = normalize_features(df, {k: tuple(v) for k, v in stats.items()}, columns=cols)
    snap = EpisodicMemory(cfg["memory"]["db_path"], cfg["memory"]["max_episodes"]).snapshot(dim=len(cols), sources=["backtest"])
    kw = dict(window_size=cfg["environment"]["window_size"], initial_balance=cfg["environment"]["initial_balance"],
              transaction_cost=cfg["environment"]["transaction_cost"], reward_type=cfg["environment"]["reward_type"],
              drawdown_penalty=cfg["environment"]["drawdown_penalty"], max_position=cfg["environment"]["max_position"],
              continuous_action=False,
              spread_volatility_multiplier=cfg["environment"].get("spread_volatility_multiplier", 1.0),
              learn_stop_loss=cfg["agent"].get("learn_stop_loss", False),
              stop_loss_buckets=cfg["agent"].get("stop_loss_buckets"),
              stop_loss_range=tuple(cfg["agent"].get("stop_loss_range", (0.003, 0.06))),
              feature_columns=cols, memory_snapshot=snap, memory_top_k=cfg["memory"].get("similarity_top_k", 5))
    log(f"v1 {style} gén {meta.get('generation')} : {len(dfn)} bougies depuis {df['time'].iloc[0].date()}, "
        f"fenêtre vue {debut_fen.date()} -> {FIN_V1.date()} ({time.time() - t0:.0f} s)")
    COURBES.mkdir(parents=True, exist_ok=True)
    if SEUL is not None:
        env = TradingEnv(dfn, **kw)
        agent = TradingAgent.load(f"{d}/agent", env, {"algo": "PPO"})
        t, v, ouv = jouer(env, agent, None if SEUL == 0 else SEUL)
        np.savez(COURBES / f"{style}_{SEUL}.npz", t=t.astype("datetime64[ns]"), v=v,
                 ouv_t=np.asarray([o[0] for o in ouv], "datetime64[ns]"), ouv_s=np.asarray([o[1] for o in ouv], int))
        log(f"  {'agent' if SEUL == 0 else f'jumeau {SEUL}'} : {len(ouv)} ouvertures, valeur finale {v[-1]:,.0f} "
            f"({time.time() - t0:.0f} s)")
        return
    runs = {}
    for g in range(0, K + 1):
        z = np.load(COURBES / f"{style}_{g}.npz")
        runs[None if g == 0 else g] = (z["t"], z["v"], list(zip(z["ouv_t"], z["ouv_s"])))
    fin = df["time"].iloc[-1] + pd.Timedelta(minutes=1)
    periodes = []
    if debut < debut_fen:
        periodes.append(("jamais vue : avant sa fenêtre", debut, debut_fen))
    periodes.append(("déjà vue : sa fenêtre (apprentissage 70 % + validation 30 %)", max(debut, debut_fen), FIN_V1))
    periodes.append(("jamais vue : après le 17/09/2026", FIN_V1, fin))
    out = {"style": style, "generation": meta.get("generation"), "jumeaux": K, "fenetre_debut": str(debut_fen.date()),
           "metrics_meta": {k: v for k, v in meta.get("metrics", {}).items() if k != "per_window"}, "periodes": []}
    for titre, a, b in periodes:
        ga = gains_mensuels(*runs[None][:2], a, b)
        gj = [gains_mensuels(*runs[i][:2], a, b).reindex(ga.index).fillna(0.0) for i in range(1, K + 1)]
        ouv = [o for o in runs[None][2] if a <= pd.Timestamp(o[0]) < b]
        p = df[(df["time"] >= a) & (df["time"] < b)]["close"].to_numpy()
        c = comparer(ga.to_numpy(), np.stack([x.to_numpy() for x in gj])) if len(ga) > 1 else {}
        res = {"periode": titre, "debut": str(a.date()), "fin": str(b.date()), "mois": int(len(ga)),
               "agent_pct_mois": float(ga.mean()) if len(ga) else None,
               "jumeaux_pct_mois": [float(x.mean()) for x in gj], "trades": len(ouv),
               "part_achats_pct": float(100 * np.mean([o[1] > 0 for o in ouv])) if ouv else None,
               "or_variation_pct": float(100 * (p[-1] / p[0] - 1)) if len(p) > 1 else None, "comparaison": c}
        out["periodes"].append(res)
        log(f"v1 {style} | {titre} | {a.date()} -> {b.date()} : agent {res['agent_pct_mois'] if res['agent_pct_mois'] is not None else float('nan'):+.2f} %/mois, "
            f"jumeaux {np.mean(res['jumeaux_pct_mois']) if gj else float('nan'):+.2f}, avantage "
            f"{c.get('avantage', float('nan')):+.2f} ± {c.get('incertitude', float('nan')):.2f} ; {len(ouv)} trades, "
            f"achats {res['part_achats_pct']} %")
    (ICI / "resultats").mkdir(exist_ok=True)
    (ICI / "resultats" / f"v1_{style}.json").write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str),
                                                        encoding="utf-8")
    log(f"terminé en {(time.time() - t0) / 60:.1f} min")


if __name__ == "__main__":
    main()
