"""
Agrandit le cerveau (neurones de mémoire du LSTM) d'un champion SANS rien lui faire oublier (07/10/2026).
Technique « Net2Net » (src/network_growth.grow_agent) : les nouveaux neurones sont ajoutés éteints -- décisions
strictement identiques juste après l'opération (vérifié sur 300 bougies de validation avant toute écriture),
puis l'entraînement les met en service progressivement.

    python scripts/grow_brain.py AUREXIS 512            (cwd = code/, Run A ARRÊTÉ)

Sauvegarde l'ancien champion dans models/champion_<style>/pre_grow_<horodatage>/.
"""
import json, os, shutil, sys, time
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
os.chdir(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import numpy as np
import yaml


def main(style: str, new_hidden: int):
    from autonomous_agent import make_data_provider
    from src.trading_env import TradingEnv
    from src.agent import TradingAgent
    from src.lockbox_gate import eval_env_kwargs
    from src.network_growth import grow_agent
    cfg = yaml.safe_load(open("../run_config_A.yaml", encoding="utf-8"))
    cdir = os.path.join("models", f"champion_{style}")
    meta = json.load(open(os.path.join(cdir, "meta.json"), encoding="utf-8"))
    cols = meta["feature_columns"]
    get_data, _ = make_data_provider(cfg)
    alias = (cfg.get("data", {}).get("dataset_alias") or {}).get(style, style)
    _, val_df, _, data_cols, _ = get_data(alias)
    if data_cols != cols:
        raise SystemExit("ABANDON : variables du champion différentes de celles des données")
    kw = eval_env_kwargs(style, cfg, meta)
    env = TradingEnv(val_df.iloc[:2000].reset_index(drop=True), feature_columns=cols, style=style, **kw)
    agent = TradingAgent.load(os.path.join(cdir, "agent"), env, {"algo": meta.get("algo", "PPO")})
    ex = agent.model.policy.features_extractor
    old_hidden = ex.lstm.hidden_size
    if new_hidden <= old_hidden:
        print(f"Rien à faire : déjà {old_hidden} neurones."); return
    agent.hyperparams = {**cfg["agent"], **(cfg["agent"].get("style_overrides", {}).get(style) or {}),
                         "lstm_hidden_size": old_hidden,
                         "net_arch": agent.model.policy_kwargs.get("net_arch", cfg["agent"].get("net_arch"))}
    agent.hyperparams.pop("style_overrides", None)
    n_old = sum(p.numel() for p in agent.model.policy.parameters())
    steps = list(range(env.window_size + 5, env.window_size + 305))
    env.reset()
    ref = []
    for s in steps:
        env.current_step = s
        ref.append(np.asarray(agent.predict(env._get_obs(), deterministic=True)).tolist())
    grow_agent(agent, new_hidden, env)
    n_new = sum(p.numel() for p in agent.model.policy.parameters())
    same = 0
    for s, r in zip(steps, ref):
        env.current_step = s
        same += int(np.asarray(agent.predict(env._get_obs(), deterministic=True)).tolist() == r)
    print(f"cerveau : {old_hidden} -> {new_hidden} neurones de mémoire, {n_old:,} -> {n_new:,} connexions ; "
          f"décisions identiques : {same}/{len(steps)}".replace(",", " "))
    if same != len(steps):
        raise SystemExit("ABANDON : la croissance change des décisions -- champion NON modifié")
    backup = os.path.join(cdir, f"pre_grow_{time.strftime('%Y%m%d_%H%M')}")
    os.makedirs(backup, exist_ok=True)
    for f in ("agent.zip", "meta.json", "norm_stats.json"):
        shutil.copy(os.path.join(cdir, f), backup)
    agent.save(os.path.join(cdir, "agent"))
    meta.update({"lstm_hidden_size": new_hidden, "grown_from_hidden": old_hidden, "updated_at": time.time()})
    json.dump(meta, open(os.path.join(cdir, "meta.json"), "w", encoding="utf-8"), indent=2, default=str)
    print(f"OK : cerveau de {style} agrandi à {new_hidden} neurones (sauvegarde : {backup})")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "AUREXIS", int(sys.argv[2]) if len(sys.argv) > 2 else 512)
