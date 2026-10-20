"""
Greffe de nouvelles variables d'observation sur le champion AUREX SANS perdre ce qu'il a appris
(05/10/2026, vision v3 : 9 variables intraday ajoutées À LA FIN de la liste). Les nouvelles entrées du
LSTM sont initialisées à zéro (src/network_growth.add_input_features) : AUREX prend exactement les mêmes
décisions qu'avant, puis l'apprentissage apprend à s'en servir.

    python scripts/graft_inputs.py <STYLE>            (cwd = code/, Run A ARRÊTÉ)

Sauvegarde l'ancien champion dans models/champion_AUREX/pre_graft_<horodatage>/ ; vérifie que les
actions sont identiques sur 300 bougies de validation avant d'écrire quoi que ce soit.
"""
import json, os, shutil, sys, time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
os.chdir(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import numpy as np
import yaml

STYLE = sys.argv[1] if len(sys.argv) > 1 else "AUREX"


def main():
    from autonomous_agent import make_data_provider
    from src.trading_env import TradingEnv
    from src.agent import TradingAgent
    from src.lockbox_gate import eval_env_kwargs
    from src.network_growth import add_input_features

    cfg = yaml.safe_load(open("../run_config_A.yaml", encoding="utf-8"))
    cdir = os.path.join("models", f"champion_{STYLE}")
    meta = json.load(open(os.path.join(cdir, "meta.json"), encoding="utf-8"))
    old_cols = meta["feature_columns"]
    get_data, _ = make_data_provider(cfg)
    train_df, val_df, stats, cols, ctx = get_data(STYLE)
    if cols[:len(old_cols)] != old_cols:
        raise SystemExit("ABANDON : les anciennes variables ne sont pas un préfixe des nouvelles -- greffe impossible")
    if len(cols) == len(old_cols):
        print("Rien à greffer : même nombre de variables."); return
    print(f"greffe : {len(old_cols)} -> {len(cols)} variables (+{len(cols) - len(old_cols)} : {cols[len(old_cols):]})")

    kw = eval_env_kwargs(STYLE, cfg, meta)
    df = val_df.iloc[:2000].reset_index(drop=True)
    old_env = TradingEnv(df, feature_columns=old_cols, style=STYLE, **kw)
    new_env = TradingEnv(df, feature_columns=cols, style=STYLE, **kw)
    old_agent = TradingAgent.load(os.path.join(cdir, "agent"), old_env, {"algo": meta.get("algo", "PPO")})
    ex = old_agent.model.policy.features_extractor
    hp = {**cfg["agent"], "lstm_hidden_size": ex.lstm.hidden_size,
          "net_arch": old_agent.model.policy_kwargs.get("net_arch", cfg["agent"].get("net_arch"))}
    ref_actions = []
    old_env.reset(); new_env.reset()
    steps = list(range(old_env.window_size + 5, old_env.window_size + 305))
    for s in steps:
        old_env.current_step = s
        ref_actions.append(np.asarray(old_agent.predict(old_env._get_obs(), deterministic=True)).tolist())
    new_agent = add_input_features(old_agent, new_env, hp) or old_agent
    same = 0
    for s, ref in zip(steps, ref_actions):
        new_env.current_step = s
        same += int(np.asarray(new_agent.predict(new_env._get_obs(), deterministic=True)).tolist() == ref)
    print(f"décisions identiques : {same}/{len(steps)}")
    if same != len(steps):
        raise SystemExit("ABANDON : la greffe change des décisions -- champion NON modifié")

    backup = os.path.join(cdir, f"pre_graft_{time.strftime('%Y%m%d_%H%M')}")
    os.makedirs(backup, exist_ok=True)
    for f in ("agent.zip", "meta.json", "norm_stats.json"):
        shutil.copy(os.path.join(cdir, f), backup)
    new_agent.save(os.path.join(cdir, "agent"))
    old_stats = json.load(open(os.path.join(cdir, "norm_stats.json"), encoding="utf-8"))
    for c in cols[len(old_cols):]:
        old_stats[c] = list(stats[c])
    json.dump(old_stats, open(os.path.join(cdir, "norm_stats.json"), "w", encoding="utf-8"), indent=1)
    meta["feature_columns"] = cols
    meta["updated_at"] = time.time()
    meta["grafted_from_n_features"] = len(old_cols)
    json.dump(meta, open(os.path.join(cdir, "meta.json"), "w", encoding="utf-8"), indent=2)
    print(f"OK : champion {STYLE} greffé ({len(cols)} variables), sauvegarde de l'ancien dans {backup}")


if __name__ == "__main__":
    main()
