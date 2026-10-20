"""
Donne à AUREXIS l'outil « taille » (09/10/2026, accord de l'utilisateur : « on lui donne les 3 outils ») puis active
les règles FTMO de son entraînement.

1. GREFFE : nouvelle sortie du cerveau = risque du trade parmi 0,1 / 0,25 / 0,5 / 1 % (src/network_growth.add_action_dim).
   Réglée au départ sur 0,5 % (= le risque fixe actuel, risk_sizing_pct) : juste après la greffe l'IA décide
   EXACTEMENT comme avant (vérifié sur 300 situations), puis l'entraînement lui apprend à moduler sa taille.
   Même greffe pour chaque veine (lignée secondaire) encore vivante.
2. CONFIG (seulement si la greffe a réussi) : récompense en argent, taille apprise, règles FTMO à l'entraînement
   (mort à -5 %/jour ou -10 %, bonus à +10 %), chance FTMO dans la note, mur du jour à -4,5 % (= le coupe-circuit
   réel) au lieu de la règle imposée à -2,5 %.

    python scripts/graft_aurexis_taille.py            (cwd = code/, Run A ARRÊTÉ)
    python scripts/graft_aurexis_taille.py --essai    (copie du champion dans un dossier temporaire, rien n'est modifié)
"""
import json, os, shutil, sys, tempfile, time
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
# GREFFE_CODE = dossier code/ de production (essai lancé depuis la copie de travail) ; sinon le dossier du script
os.chdir(os.environ.get("GREFFE_CODE") or os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
os.environ.setdefault("CUDA_VISIBLE_DEVICES", "-1")
import numpy as np
import pandas as pd
import yaml

STYLE = "AUREXIS"
CONFIG = os.path.abspath(os.path.join("..", "run_config_A.yaml"))
BUCKETS = [0.001, 0.0025, 0.005, 0.01]


def _situations(cols, n=600, seed=0):
    """Situations de marché inventées (même entrée pour l'ancien et le nouveau cerveau : seule compte l'égalité)."""
    rng = np.random.default_rng(seed)
    close = 2000 * np.cumprod(1 + rng.normal(0, 0.002, n))
    df = pd.DataFrame({"time": pd.date_range("2025-01-06", periods=n, freq="15min"), "open": close,
                       "high": close * 1.001, "low": close * 0.999, "close": close, "volume": 1.0})
    for c in cols:
        if c not in df.columns:
            df[c] = rng.normal(0, 1, n).astype(np.float32)
    return df


def graft(model_path, cfg, meta, bias_idx):
    """`model_path` = chemin du modèle SANS « .zip » (comme le chargement SB3)."""
    from src.trading_env import TradingEnv
    from src.agent import TradingAgent
    from src.lockbox_gate import eval_env_kwargs
    from src.network_growth import add_action_dim
    import torch
    cols = meta["feature_columns"]
    kw = eval_env_kwargs(STYLE, cfg, meta)
    kw.pop("learn_position_size", None)
    df = _situations(cols)
    old_env = TradingEnv(df, feature_columns=cols, style=STYLE, **{**kw, "learn_position_size": False})
    new_env = TradingEnv(df, feature_columns=cols, style=STYLE,
                         **{**kw, "learn_position_size": True, "size_risk_buckets": BUCKETS})
    if new_env._idx_size is None:
        raise SystemExit("ABANDON : l'environnement n'a pas de dimension taille (risk_sizing_pct nul ?)")
    agent = TradingAgent.load(model_path, old_env, {"algo": meta.get("algo", "PPO")})
    ex = agent.model.policy.features_extractor
    hp = {**cfg["agent"], **(cfg["agent"].get("style_overrides", {}).get(STYLE) or {}),
          "lstm_hidden_size": ex.lstm.hidden_size,
          "net_arch": agent.model.policy_kwargs.get("net_arch", cfg["agent"].get("net_arch"))}
    hp.pop("style_overrides", None)
    old_params = {k: v.detach().clone() for k, v in agent.model.policy.state_dict().items()}
    steps = list(range(old_env.window_size + 5, old_env.window_size + 305))
    old_env.reset(); new_env.reset()
    ref = []
    for s in steps:
        old_env.current_step = s
        ref.append(np.asarray(agent.predict(old_env._get_obs(), deterministic=True)).tolist())
    n_old = agent.model.policy.action_net.weight.shape[0]
    add_action_dim(agent, new_env, hp)
    with torch.no_grad():
        net = agent.model.policy.action_net
        net.weight[n_old:, :] = 0.0
        b = torch.zeros(len(BUCKETS))
        b[bias_idx] = 2.0                      # départ : ~70 % de chances de garder le risque actuel, 30 % d'essais
        net.bias[n_old:] = b
    # tout le reste du cerveau doit être recopié à l'identique (sinon la greffe a perdu quelque chose)
    new_params = agent.model.policy.state_dict()
    for k, v in old_params.items():
        if k.startswith("action_net."):
            assert torch.equal(new_params[k][:v.shape[0]], v), k
        elif not torch.equal(new_params[k], v):
            raise SystemExit(f"ABANDON : {k} n'a pas été recopié à l'identique")
    same = 0
    for s, r in zip(steps, ref):
        new_env.current_step = s
        a = np.asarray(agent.predict(new_env._get_obs(), deterministic=True)).tolist()
        same += int(a[:-1] == r and a[-1] == bias_idx)
    if same != len(steps):
        raise SystemExit(f"ABANDON : décisions différentes après greffe ({same}/{len(steps)}) -- rien modifié")
    return agent, len(steps)


def edit_config(text: str) -> str:
    anchor = "    AUREXIS:\n      # 08/10 : récompense trade par trade (test : prudence x3, la sélection empêche l'inactivité)\n" \
             "      reward_type: trade_r\n"
    assert text.count(anchor) == 1, "ancre AUREXIS introuvable"
    text = text.replace(anchor,
        "    AUREXIS:\n"
        "      # 09/10 : LES TROIS OUTILS -- récompense en ARGENT (part du compte / 0,5 % fixe, moins un coût fixe par\n"
        "      # trade : les micro-positions ne rapportent rien), TAILLE choisie par l'IA (risque 0,1 à 1 %), règles\n"
        "      # FTMO à l'entraînement (environment.training_only). Avant : trade_r (08/10).\n"
        "      reward_type: trade_argent\n"
        "      learn_position_size: true\n"
        f"      size_risk_buckets: {BUCKETS}\n")
    old = ("      max_stops_per_day: 2\n      trader_state: true\n      daily_loss_halt_pct: 0.025\n"
           "      prop_penalty_coef: 0.5\n      prop_soft_loss_pct: 0.015\n      learn_trade_management: true\n"
           "      be_trigger_r: 0.5\n      trail_r: 1.0\n      risk_sizing_pct: 0.005\n      max_leverage: 10.0\n    H4:\n")
    assert text.count(old) == 1, "bloc AUREXIS (règles du jour) introuvable"
    text = text.replace(old,
        "      max_stops_per_day: 2\n      trader_state: true\n"
        "      # 09/10 : plus de règle imposée à -2,5 % ni de pénalité à -1,5 % -- l'IA apprend que -5 % = la mort.\n"
        "      # Reste le mur du coupe-circuit RÉEL (-4,5 % sur la journée : plus de nouvelle position), simulé à l'identique.\n"
        "      daily_loss_halt_pct: 0.045\n      prop_penalty_coef: 0.0\n      learn_trade_management: true\n"
        "      be_trigger_r: 0.5\n      trail_r: 1.0\n      risk_sizing_pct: 0.005\n      max_leverage: 10.0\n    H4:\n")
    cfg = yaml.safe_load(text)
    assert "training_only" not in cfg["environment"] and "ftmo_weight_by_style" not in cfg["continuous"]
    lines = text.split("\n")
    # environment.training_only : inséré juste avant environment.style_overrides
    i_env = lines.index("environment:")
    j = next(k for k in range(i_env + 1, len(lines)) if lines[k].startswith("  style_overrides:"))
    lines[j:j] = ["  # 09/10 : réglages du simulateur d'ENTRAÎNEMENT seulement (l'examen joue toujours les périodes en entier) :",
                  "  # règles FTMO -- -5 % sur la journée ou -10 % au total = partie perdue (grosse punition), +10 % encaissés",
                  "  # = challenge réussi (bonus 4x plus petit que la punition : jouer au casino est perdant).",
                  "  training_only:",
                  "    AUREXIS: {ftmo_rules: true, ftmo_daily_loss: 0.05, ftmo_total_loss: 0.10, ftmo_target: 0.10,",
                  "              ftmo_death_penalty: 20.0, ftmo_success_bonus: 5.0}"]
    i_c = lines.index("continuous:")
    lines[i_c + 1:i_c + 1] = ["  # 09/10 : chance de réussir le challenge FTMO (rejouée sur la période d'examen) ajoutée à la note :",
                              "  # réussite - échecs. Une IA minuscule ne réussit jamais (0), une IA casino échoue (négatif).",
                              "  ftmo_weight_by_style: {AUREXIS: 1.0}"]
    text = "\n".join(lines)
    cfg = yaml.safe_load(text)
    o = cfg["environment"]["style_overrides"][STYLE]
    assert o["reward_type"] == "trade_argent" and o["learn_position_size"] is True and o["daily_loss_halt_pct"] == 0.045
    assert cfg["environment"]["training_only"][STYLE]["ftmo_rules"] is True
    assert cfg["continuous"]["ftmo_weight_by_style"][STYLE] == 1.0
    assert cfg["environment"]["style_overrides"]["AUREX"]["daily_loss_halt_pct"] == 0.025, "AUREX inchangé"
    return text


def main(essai: bool):
    cfg_text = open(CONFIG, encoding="utf-8").read()
    cfg = yaml.safe_load(cfg_text)
    if (cfg["environment"]["style_overrides"].get(STYLE) or {}).get("learn_position_size"):
        print("Rien à faire : AUREXIS a déjà l'outil taille."); return
    new_text = edit_config(cfg_text)                       # vérifie les ancres AVANT de toucher au cerveau
    risk = float(cfg["environment"]["style_overrides"][STYLE]["risk_sizing_pct"])
    bias_idx = BUCKETS.index(risk)
    cdir = os.path.join("models", f"champion_{STYLE}")
    if essai:
        tmp = tempfile.mkdtemp(prefix="greffe_taille_")
        for f in ("agent.zip", "meta.json"):
            shutil.copy(os.path.join(cdir, f), tmp)
        cdir = tmp
    meta = json.load(open(os.path.join(cdir, "meta.json"), encoding="utf-8"))
    agent, n = graft(os.path.join(cdir, "agent"), cfg, meta, bias_idx)
    print(f"champion : greffe OK, décisions identiques {n}/{n}, taille de départ {BUCKETS[bias_idx]:.2%}")
    # veines vivantes ET archivées (relançables) : modèles « <veines>/<id>.zip », mêmes variables que le champion
    vroot = os.path.join("models", f"champion_{STYLE}", "veines")
    veins = []
    for j in (os.path.join(vroot, "veines.json"), os.path.join(vroot, "archives", "archives.json")):
        if os.path.exists(j):
            veins += [v for v in json.load(open(j, encoding="utf-8")) if os.path.exists(v["path"] + ".zip")]
    grafted_veins = [(v["path"], graft(v["path"], cfg, meta, bias_idx)[0]) for v in veins]
    print(f"veines greffées : {len(grafted_veins)}")
    if essai:
        print(f"ESSAI : rien n'a été modifié (copie dans {cdir})")
        return
    stamp = time.strftime("%Y%m%d_%H%M")
    backup = os.path.join(cdir, "history", f"avant_taille_{stamp}")
    os.makedirs(backup, exist_ok=True)
    for f in ("agent.zip", "meta.json", "norm_stats.json"):
        if os.path.exists(os.path.join(cdir, f)):
            shutil.copy(os.path.join(cdir, f), backup)
    agent.save(os.path.join(cdir, "agent"))
    meta.update(updated_at=time.time(), outils=["taille"], size_risk_buckets=BUCKETS,
                origin=str(meta.get("origin", "")) + f" | outil taille greffé le {time.strftime('%d/%m/%Y %H:%M')}")
    json.dump(meta, open(os.path.join(cdir, "meta.json"), "w", encoding="utf-8"), indent=1, default=str)
    for vpath, va in grafted_veins:
        shutil.copy(vpath + ".zip", os.path.join(backup, os.path.basename(vpath) + ".zip"))
        va.save(vpath)
    shutil.copy(CONFIG, CONFIG + f".bak_avant_taille_{stamp}")
    open(CONFIG, "w", encoding="utf-8").write(new_text)
    print(f"OK : outil taille greffé (sauvegarde {backup}), config AUREXIS : argent + taille + règles FTMO")


if __name__ == "__main__":
    main("--essai" in sys.argv)
