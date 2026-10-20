"""
Donne à AUREXIS la VISION DES TENDANCES DE FOND (09/10/2026, src/trend_vision.py) : 5 nouvelles entrées (tendance à
1, 3, 6 et 12 mois rapportée à la volatilité, et accord des quatre horizons), ajoutées À LA FIN de ses variables.

Greffe sans perte (src/network_growth.add_input_features) : les connexions des nouvelles entrées partent à ZÉRO ->
juste après, l'IA décide EXACTEMENT comme avant (vérifié sur 300 situations, avec des valeurs de tendance non nulles) ;
l'apprentissage les met ensuite en service. Même greffe pour chaque veine (vivante et archivée) et pour le modèle du
professeur. Statistiques de normalisation des nouvelles entrées : calculées sur l'historique de l'or avant la coupe.
Le réglage `data.trend_vision_styles: [AUREXIS]` n'est écrit QUE si toutes les greffes ont réussi.

    python scripts/vision_tendances_aurexis.py            (cwd = code/, Run A ARRÊTÉ)
    python scripts/vision_tendances_aurexis.py --essai    (copies, rien n'est modifié)
"""
import json, os, shutil, sys, tempfile, time
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
os.chdir(os.environ.get("GREFFE_CODE") or os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
os.environ.setdefault("CUDA_VISIBLE_DEVICES", "-1")
import numpy as np
import pandas as pd
import yaml

STYLE = "AUREXIS"
CONFIG = os.path.abspath(os.path.join("..", "run_config_A.yaml"))


def graft(model_path, cfg, meta, new_cols):
    import torch
    from src.trading_env import TradingEnv
    from src.agent import TradingAgent
    from src.lockbox_gate import eval_env_kwargs
    from src.network_growth import add_input_features
    from graft_aurexis_taille import _situations
    old_cols = meta["feature_columns"]
    kw = eval_env_kwargs(STYLE, cfg, meta)
    df = _situations(new_cols)                                    # tendances NON nulles (tirage aléatoire)
    old_env = TradingEnv(df, feature_columns=old_cols, style=STYLE, **kw)
    new_env = TradingEnv(df, feature_columns=new_cols, style=STYLE, **kw)
    agent = TradingAgent.load(model_path, old_env, {"algo": meta.get("algo", "PPO")})
    ex = agent.model.policy.features_extractor
    hp = {**cfg["agent"], **(cfg["agent"].get("style_overrides", {}).get(STYLE) or {}),
          "lstm_hidden_size": ex.lstm.hidden_size,
          "net_arch": agent.model.policy_kwargs.get("net_arch", cfg["agent"].get("net_arch"))}
    hp.pop("style_overrides", None)
    steps = list(range(old_env.window_size + 5, old_env.window_size + 305))
    old_env.reset(); new_env.reset()
    ref = []
    for s in steps:
        old_env.current_step = s
        ref.append(np.asarray(agent.predict(old_env._get_obs(), deterministic=True)).tolist())
    add_input_features(agent, new_env, hp)
    same = 0
    for s, r in zip(steps, ref):
        new_env.current_step = s
        same += int(np.asarray(agent.predict(new_env._get_obs(), deterministic=True)).tolist() == r)
    if same != len(steps):
        raise SystemExit(f"ABANDON : {model_path} -- {len(steps) - same} décision(s) changée(s), rien modifié")
    return agent


def gold_trend_stats(cfg) -> dict:
    """Moyenne / écart-type des nouvelles entrées sur l'or, AVANT la coupe d'entraînement des autres marchés."""
    from src.multi_timeframe import discover_files
    from src.aurexis_data import load_m15, load_market_stats
    from src.trend_vision import daily_closes, trend_table, TREND_COLUMNS
    m15 = load_m15(discover_files(cfg["data"]["folder"])["M15"])
    tab = trend_table(daily_closes(m15))
    cut = pd.Timestamp(load_market_stats("EURUSD")["cut"])
    tab = tab[tab.index < cut].dropna()
    return {c: [float(tab[c].mean()), float(tab[c].std() + 1e-8)] for c in TREND_COLUMNS}


def edit_config(text: str) -> str:
    old = '  toolbox_styles: ["AUREX", "AUREXIS"]'
    i = text.find(old)
    assert i >= 0 and text.count(old) == 1, "ancre toolbox_styles introuvable"
    j = text.index("\n", i)
    text = text[:j + 1] + ("  # 09/10 : vision des tendances de fond (src/trend_vision.py) -- 5 variables, AUREXIS seulement.\n"
                           '  trend_vision_styles: ["AUREXIS"]\n') + text[j + 1:]
    assert yaml.safe_load(text)["data"]["trend_vision_styles"] == [STYLE]
    return text


def main(essai: bool):
    from src.trend_vision import TREND_COLUMNS
    cfg_text = open(CONFIG, encoding="utf-8").read()
    cfg = yaml.safe_load(cfg_text)
    if STYLE in ((cfg.get("data") or {}).get("trend_vision_styles") or []):
        print("Rien à faire : vision des tendances déjà active."); return
    new_text = edit_config(cfg_text)
    cdir = os.path.join("models", f"champion_{STYLE}")
    meta = json.load(open(os.path.join(cdir, "meta.json"), encoding="utf-8"))
    new_cols = list(meta["feature_columns"]) + [c for c in TREND_COLUMNS if c not in meta["feature_columns"]]
    stats_new = gold_trend_stats(cfg)
    targets = [(os.path.join(cdir, "agent"), os.path.join(cdir, "meta.json"), os.path.join(cdir, "norm_stats.json"))]
    pdir = os.path.join("models", f"professeur_{STYLE}")
    if os.path.exists(os.path.join(pdir, "agent.zip")):
        targets.append((os.path.join(pdir, "agent"), os.path.join(pdir, "meta.json"), os.path.join(pdir, "norm_stats.json")))
    vroot = os.path.join(cdir, "veines")
    for j in (os.path.join(vroot, "veines.json"), os.path.join(vroot, "archives", "archives.json")):
        if os.path.exists(j):
            targets += [(v["path"], None, None) for v in json.load(open(j, encoding="utf-8")) if os.path.exists(v["path"] + ".zip")]
    grafted = [(t, graft(t[0], cfg, meta, new_cols)) for t in targets]
    print(f"greffes réussies : {len(grafted)} (champion, professeur, veines) -- décisions identiques 300/300 chacune")
    if essai:
        print("ESSAI : rien n'a été modifié"); return
    stamp = time.strftime("%Y%m%d_%H%M")
    backup = os.path.join(cdir, "history", f"avant_tendances_{stamp}")
    os.makedirs(backup, exist_ok=True)
    for (mp, mt, ns), agent in grafted:
        shutil.copy(mp + ".zip", os.path.join(backup, os.path.basename(os.path.dirname(mp)) + "_" + os.path.basename(mp) + ".zip"))
        agent.save(mp)
        if mt:
            m = json.load(open(mt, encoding="utf-8"))
            m.update(feature_columns=new_cols, updated_at=time.time(), vision_tendances=True)
            json.dump(m, open(mt, "w", encoding="utf-8"), indent=1, default=str)
        if ns and os.path.exists(ns):
            st = json.load(open(ns, encoding="utf-8"))
            st.update({c: v for c, v in stats_new.items() if c not in st})
            json.dump(st, open(ns, "w", encoding="utf-8"), indent=2)
    shutil.copy(CONFIG, CONFIG + f".bak_tendances_{stamp}")
    open(CONFIG, "w", encoding="utf-8").write(new_text)
    print(f"OK : vision des tendances active pour AUREXIS ({len(new_cols)} variables), sauvegardes dans {backup}")


if __name__ == "__main__":
    main("--essai" in sys.argv)
