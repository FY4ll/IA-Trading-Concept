"""Vérification honnête des anciens agents PAR UNITÉ DE TEMPS de Run A (20/10/2026, étape 1 du « cerveau modulaire »).

Lecture seule : aucun modèle n'est modifié, rien n'est écrit dans runs/. Pour un style (H1, H1T, H1X, H4, M30, AUREX) :
- le champion est rejoué exactement comme le rejeu de référence de Run A (scripts/aurex_judge.py : même environnement,
  mêmes frais, décisions au maximum de probabilité) sur l'or de 2010 à aujourd'hui ;
- K JUMEAUX AU HASARD : la même politique, les mêmes moments, les mêmes stops / objectifs / tailles / gestion, mais le
  SENS de chaque nouvelle ouverture (depuis plat ou retournement) est tiré à pile ou face ; ensuite la position est
  gérée par la politique comme elle la voit (même principe que le jumeau de MAGNETAR, core/jumeau.py) ;
- gains mensuels par période : DÉJÀ VUE à l'entraînement, et JAMAIS VUE (avant sa fenêtre d'historique et/ou après
  le début de la lockbox) ; comparaison appariée mois par mois contre la moyenne des jumeaux (core.jumeau.comparer).

    cd Test_IA ; venv_gpu\\Scripts\\python.exe etudes\\2026-10-20_agents_par_unite\\verifier.py H1 [--jumeaux 6]
    -> etudes/2026-10-20_agents_par_unite/resultats/<style>.json
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

ICI = Path(__file__).resolve().parent
RACINE = ICI.parents[1]
CODE = RACINE / "runs" / "20260919_envv2" / "code"
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(CODE))
os.chdir(CODE)                                    # le code de Run A lit ses chemins relatifs depuis code/

import numpy as np
import pandas as pd
import yaml

from core.jumeau import comparer

DEBUT = pd.Timestamp("2010-01-01")
# Ce que chaque champion a VU à l'entraînement (historique de Run A : data.max_bars_by_style, inventaire du 20/10) :
# H1 / H1T / H1X / H4 : tout l'or jusqu'à la lockbox ; M30 : ~100 000 bougies (~2014 ->) ; AUREX (base 15 min) :
# ~2018-06 -> 2023-05 (apprentissage jusqu'à 11/2021). Les périodes « jamais vues » ci-dessous en découlent.
AVANT_FENETRE = {"AUREX": pd.Timestamp("2018-01-01"), "M30": pd.Timestamp("2014-01-01")}


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def head_logits(head, hidden, extra):
    x = np.concatenate([hidden, extra]).astype(np.float64)
    for kind, a, b in head.layers:
        x = x @ a + b if kind == "lin" else a(x)
    return x


def jouer(env, hidden, head, seq_len, graine: int | None):
    """Rejoue la politique (graine None = l'agent lui-même ; sinon un jumeau). Rend (temps, valeur du compte à
    chaque pas, trades [(temps d'ouverture, sens)], ouvertures retournées)."""
    rng = np.random.default_rng(graine) if graine is not None else None
    env.reset()
    temps = pd.to_datetime(env.df["time"]).to_numpy()
    t_out, v_out, ouv = [], [], []
    done = False
    retournees = 0
    while not done:
        t = env.current_step
        extra = env._get_obs()[seq_len:]
        parts = np.split(head_logits(head, hidden[t], extra), head.splits)
        action = np.array([int(np.argmax(p)) for p in parts])
        pos = env.position
        d = {0: -1, 1: 0, 2: 1}[int(action[0])]
        ouverture = d != 0 and (pos == 0 or np.sign(pos) != d)
        if rng is not None and ouverture and rng.random() < 0.5:
            d = -d
            action[0] = {-1: 0, 1: 2}[d]
            retournees += 1
        _, _, term, trunc, info = env.step(action)
        done = term or trunc
        if env.position != 0 and (pos == 0 or np.sign(pos) != np.sign(env.position)):
            ouv.append((temps[t], int(np.sign(env.position))))
        t_out.append(temps[t])
        v_out.append(float(info.get("equity", env.balance)))
    return np.asarray(t_out), np.asarray(v_out), ouv, retournees


def gains_mensuels(t, v, debut, fin) -> pd.Series:
    """Gain de chaque mois civil complet de [debut, fin), en % du compte au début du mois."""
    s = pd.Series(v, index=pd.to_datetime(t))
    s = s[(s.index >= debut) & (s.index < fin)]
    if s.empty:
        return pd.Series(dtype=float)
    fins = s.resample("ME").last()
    debuts = s.resample("ME").first()
    g = (fins / debuts - 1) * 100
    return g.dropna()


def main():
    style = sys.argv[1]
    k = int(sys.argv[sys.argv.index("--jumeaux") + 1]) if "--jumeaux" in sys.argv else 6
    from src.risk_profile import apply_risk_profile
    from src.lockbox_gate import build_eval_frames, eval_env_kwargs
    from src.features import normalize_features
    from src.trading_env import TradingEnv
    from src.agent import TradingAgent
    from src.fast_eval import precompute_lstm, _NumpyHead

    cfg = yaml.safe_load(open("../run_config_A.yaml", encoding="utf-8"))
    apply_risk_profile(cfg)
    d = f"models/champion_{style}"
    meta = json.load(open(f"{d}/meta.json", encoding="utf-8"))
    stats = {kk: tuple(vv) for kk, vv in json.load(open(f"{d}/norm_stats.json", encoding="utf-8")).items()}
    cols = meta["feature_columns"]
    t0 = time.time()
    vis, lock, debut_lock = build_eval_frames(style, cfg, meta)
    vis = vis[pd.to_datetime(vis["time"]) >= DEBUT].reset_index(drop=True)
    log(f"{style} gén {meta.get('generation')} : historique {len(vis)} bougies, lockbox {len(lock)} "
        f"(depuis {debut_lock.date()}) ({time.time() - t0:.0f} s)")
    kw = eval_env_kwargs(style, cfg, meta)
    courbes = {}
    for nom, brut in (("historique", vis), ("lockbox", lock)):
        brut = brut.reset_index(drop=True)
        dfn, _ = normalize_features(brut, stats=stats, columns=cols)
        env = TradingEnv(dfn, feature_columns=cols, style=style, **kw)
        agent = TradingAgent.load(f"{d}/agent", env, {"algo": "PPO"})
        pol = agent.model.policy
        pol.set_training_mode(False)
        hidden = precompute_lstm(pol.features_extractor, env._feature_values, env.window_size).numpy().astype(np.float64)
        head = _NumpyHead(pol)
        seq_len = env.window_size * env.n_features
        prix = brut[["time", "close"]].copy()
        runs = {}
        for i, g in enumerate([None] + list(range(1, k + 1))):
            t, v, ouv, ret = jouer(env, hidden, head, seq_len, g)
            runs["agent" if g is None else f"jumeau_{g}"] = (t, v, ouv, ret)
            log(f"  {nom} {'agent' if g is None else f'jumeau {g}'} : {len(ouv)} ouvertures, "
                f"valeur finale {v[-1]:,.0f} ({time.time() - t0:.0f} s)")
        courbes[nom] = (runs, prix)
        del env, agent, dfn, hidden

    fin_vis = pd.to_datetime(vis["time"]).max() + pd.Timedelta(minutes=1)
    debut_l = pd.to_datetime(lock["time"]).min()
    fin_l = pd.to_datetime(lock["time"]).max() + pd.Timedelta(minutes=1)
    periodes = []
    if style in AVANT_FENETRE:
        periodes.append(("jamais vue : avant sa fenêtre d'historique", "historique", DEBUT, AVANT_FENETRE[style]))
        periodes.append(("déjà vue : sa fenêtre d'historique (apprentissage + validation)", "historique",
                         AVANT_FENETRE[style], fin_vis))
    else:
        periodes.append(("déjà vue : apprentissage + validation", "historique", DEBUT, fin_vis))
    periodes.append(("lockbox (après la date de coupure ; contaminée si la porte lockbox a servi)", "lockbox",
                     debut_l, fin_l))
    out = {"style": style, "generation": meta.get("generation"), "jumeaux": k, "lockbox_debut": str(debut_l.date()),
           "lockbox_meta": meta.get("lockbox"), "periodes": []}
    for titre, source, a, b in periodes:
        runs, prix = courbes[source]
        ga = gains_mensuels(*runs["agent"][:2], a, b)
        gj = [gains_mensuels(*runs[f"jumeau_{i}"][:2], a, b).reindex(ga.index).fillna(0.0) for i in range(1, k + 1)]
        ouv = [o for o in runs["agent"][2] if a <= pd.Timestamp(o[0]) < b]
        p = prix[(pd.to_datetime(prix["time"]) >= a) & (pd.to_datetime(prix["time"]) < b)]["close"].to_numpy()
        c = comparer(ga.to_numpy(), np.stack([x.to_numpy() for x in gj])) if len(ga) > 1 else {}
        ouv_j = [len([o for o in runs[f"jumeau_{i}"][2] if a <= pd.Timestamp(o[0]) < b]) for i in range(1, k + 1)]
        res = {"periode": titre, "debut": str(a.date()), "fin": str(b.date()), "mois": int(len(ga)),
               "agent_pct_mois": float(ga.mean()) if len(ga) else None,
               "jumeaux_pct_mois": [float(x.mean()) for x in gj],
               "agent_pire_mois": float(ga.min()) if len(ga) else None,
               "trades": len(ouv), "trades_jumeaux_moyen": float(np.mean(ouv_j)),
               "part_achats_pct": float(100 * np.mean([o[1] > 0 for o in ouv])) if ouv else None,
               "or_variation_pct": float(100 * (p[-1] / p[0] - 1)) if len(p) > 1 else None,
               "comparaison": c}
        out["periodes"].append(res)
        log(f"{style} | {titre} | {a.date()} -> {b.date()} : agent {res['agent_pct_mois']:+.2f} %/mois, jumeaux "
            f"{np.mean(res['jumeaux_pct_mois']):+.2f}, avantage {c.get('avantage', float('nan')):+.2f} "
            f"± {c.get('incertitude', float('nan')):.2f} ; {len(ouv)} trades, achats {res['part_achats_pct']} %")
    (ICI / "resultats").mkdir(exist_ok=True)
    (ICI / "resultats" / f"{style}.json").write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str),
                                                     encoding="utf-8")
    log(f"terminé en {(time.time() - t0) / 60:.1f} min")


if __name__ == "__main__":
    main()
