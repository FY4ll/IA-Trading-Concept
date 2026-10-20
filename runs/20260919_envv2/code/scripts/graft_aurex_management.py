"""
Greffe de la dimension d'action "gestion du trade" (0 rien / 1 break-even / 2 stop suiveur) sur le
champion AUREX SANS perdre ce qu'il a appris (06/10/2026). Les logits de la nouvelle dimension partent
d'un biais qui favorise "rien" : ses décisions actuelles restent identiques (vérifié), puis l'apprentissage
découvre quand gérer son stop comme un trader.

    python scripts/graft_aurex_management.py            (cwd = code/, Run A ARRÊTÉ)
"""
import json, os, shutil, sys, time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
os.chdir(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import numpy as np
import torch
import yaml

STYLE = "AUREX"
NOTHING_BIAS = 3.0


def main():
    from autonomous_agent import make_data_provider
    from src.trading_env import TradingEnv
    from src.agent import TradingAgent
    from src.lockbox_gate import eval_env_kwargs
    from src.network_growth import add_action_dim

    cfg = yaml.safe_load(open("../run_config_A.yaml", encoding="utf-8"))
    cdir = os.path.join("models", f"champion_{STYLE}")
    meta = json.load(open(os.path.join(cdir, "meta.json"), encoding="utf-8"))
    kw_new = eval_env_kwargs(STYLE, cfg, meta)
    if not kw_new.get("learn_trade_management"):
        raise SystemExit("ABANDON : learn_trade_management n'est pas activé pour AUREX dans la config")
    kw_old = {**kw_new, "learn_trade_management": False}
    get_data, _ = make_data_provider(cfg)
    _, val_df, _, cols, _ = get_data(STYLE)
    if cols != meta["feature_columns"]:
        raise SystemExit("ABANDON : variables différentes du champion")
    df = val_df.iloc[:3000].reset_index(drop=True)
    old_env = TradingEnv(df, feature_columns=cols, style=STYLE, **kw_old)
    new_env = TradingEnv(df, feature_columns=cols, style=STYLE, **kw_new)
    if len(new_env.action_space.nvec) != len(old_env.action_space.nvec) + 1:
        print("Rien à greffer : le champion a déjà la dimension de gestion ?"); return
    old_agent = TradingAgent.load(os.path.join(cdir, "agent"), old_env, {"algo": meta.get("algo", "PPO")})
    ex = old_agent.model.policy.features_extractor
    hp = {**cfg["agent"], "lstm_hidden_size": ex.lstm.hidden_size,
          "net_arch": old_agent.model.policy_kwargs.get("net_arch", cfg["agent"].get("net_arch"))}
    steps = list(range(old_env.window_size + 5, old_env.window_size + 405))
    old_env.reset()
    ref = []
    for s in steps:
        old_env.current_step = s
        ref.append(np.asarray(old_agent.predict(old_env._get_obs(), deterministic=True)).tolist())
    n_old_logits = old_agent.model.policy.action_net.weight.shape[0]
    agent = add_action_dim(old_agent, new_env, hp)
    with torch.no_grad():                                  # nouvelle dimension : "rien" par défaut
        an = agent.model.policy.action_net
        an.weight[n_old_logits:, :] = 0.0
        an.bias[n_old_logits:] = torch.tensor([NOTHING_BIAS, 0.0, 0.0])
    new_env.reset()
    same = 0
    for s, r in zip(steps, ref):
        new_env.current_step = s
        a = np.asarray(agent.predict(new_env._get_obs(), deterministic=True)).tolist()
        same += int(a[:-1] == r and a[-1] == 0)
    print(f"décisions identiques (anciennes dimensions + 'rien' en gestion) : {same}/{len(steps)}")
    if same != len(steps):
        raise SystemExit("ABANDON : la greffe change des décisions -- champion NON modifié")
    backup = os.path.join(cdir, f"pre_mgmt_{time.strftime('%Y%m%d_%H%M')}")
    os.makedirs(backup, exist_ok=True)
    for f in ("agent.zip", "meta.json", "norm_stats.json"):
        shutil.copy(os.path.join(cdir, f), backup)
    agent.save(os.path.join(cdir, "agent"))
    meta["updated_at"] = time.time()
    meta["grafted_trade_management"] = True
    json.dump(meta, open(os.path.join(cdir, "meta.json"), "w", encoding="utf-8"), indent=2)
    print(f"OK : gestion du trade greffée sur AUREX (sauvegarde : {backup})")


if __name__ == "__main__":
    main()
