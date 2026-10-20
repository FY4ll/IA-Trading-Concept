"""
Donne à AUREXIS la VISION DU COMPTE (11/10/2026, point 3 validé par l'utilisateur) : 2 nouvelles entrées -- baisse du
compte depuis son plus haut, part du budget de risque déjà prise par les autres positions -- et les règles du vrai
compte à l'ouverture (frein de baisse, refus au-delà du budget de 4 %), voir src/trading_env.py (account_state).

Greffe sans perte (src/network_growth.add_extra_inputs) : les connexions des nouvelles entrées partent à ZÉRO -> juste
après, l'IA décide EXACTEMENT comme avant (vérifié sur 300 situations, avec un compte en baisse et un budget en partie
pris) ; l'apprentissage les met ensuite en service. Même greffe pour les veines (vivantes et archivées) et pour le
prétendant à l'essai s'il y en a un. Le réglage `account_state: true` n'est écrit QUE si toutes les greffes ont réussi.

    python scripts/vision_compte_aurexis.py            (cwd = code/, Run A ARRÊTÉ)
    python scripts/vision_compte_aurexis.py --essai    (rien n'est modifié)
"""
import json, os, shutil, sys, time
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
os.chdir(os.environ.get("GREFFE_CODE") or os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
os.environ.setdefault("CUDA_VISIBLE_DEVICES", "-1")
import numpy as np
import yaml

STYLE = "AUREXIS"
CONFIG = os.path.abspath(os.path.join("..", "run_config_A.yaml"))
ANCHOR = "      trader_state: true\n      # 09/10 : plus de règle imposée à -2,5 %"


def graft(model_path, cfg, meta):
    from src.trading_env import TradingEnv
    from src.agent import TradingAgent
    from src.lockbox_gate import eval_env_kwargs
    from src.network_growth import add_extra_inputs
    from graft_aurexis_taille import _situations
    cols = meta["feature_columns"]
    kw = {k: v for k, v in eval_env_kwargs(STYLE, cfg, meta).items() if k != "account_state"}
    df = _situations(cols)
    old_env = TradingEnv(df, feature_columns=cols, style=STYLE, **kw)
    new_env = TradingEnv(df, feature_columns=cols, style=STYLE, **{**kw, "account_state": True})
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
    add_extra_inputs(agent, new_env, hp)
    rng = np.random.default_rng(1)
    same = 0
    for s, r in zip(steps, ref):
        new_env.current_step = s
        new_env.live_state = {"account_dd": float(rng.uniform(0, 0.08)), "other_risk_share": float(rng.uniform(0, 1))}
        same += int(np.asarray(agent.predict(new_env._get_obs(), deterministic=True)).tolist() == r)
    if same != len(steps):
        raise SystemExit(f"ABANDON : {model_path} -- {len(steps) - same} décision(s) changée(s), rien modifié")
    return agent


def edit_config(text: str) -> str:
    assert text.count(ANCHOR) == 1, "ancre AUREXIS (trader_state) introuvable"
    text = text.replace(ANCHOR,
        "      trader_state: true\n"
        "      # 11/10 : VISION DU COMPTE -- baisse du compte + part du budget prise par les autres positions, et règles du\n"
        "      # vrai compte à l'ouverture (frein sous -5 %, refus au-delà du budget de 4 %). scripts/vision_compte_aurexis.py\n"
        "      account_state: true\n"
        "      # 09/10 : plus de règle imposée à -2,5 %")
    cfg = yaml.safe_load(text)
    assert cfg["environment"]["style_overrides"][STYLE]["account_state"] is True
    assert "account_state" not in cfg["environment"]["style_overrides"]["AUREX"], "AUREX inchangé"
    return text


def targets() -> list:
    cdir = os.path.join("models", f"champion_{STYLE}")
    out = [(os.path.join(cdir, "agent"), os.path.join(cdir, "meta.json"))]
    pdir = os.path.join("models", f"pretendant_{STYLE}")
    if os.path.exists(os.path.join(pdir, "agent.zip")):
        out.append((os.path.join(pdir, "agent"), None))
    vroot = os.path.join(cdir, "veines")
    for j in (os.path.join(vroot, "veines.json"), os.path.join(vroot, "archives", "archives.json")):
        if os.path.exists(j):
            out += [(v["path"], None) for v in json.load(open(j, encoding="utf-8")) if os.path.exists(v["path"] + ".zip")]
    return out


def main(essai: bool):
    cfg_text = open(CONFIG, encoding="utf-8").read()
    cfg = yaml.safe_load(cfg_text)
    if (cfg["environment"]["style_overrides"].get(STYLE) or {}).get("account_state"):
        print("Rien à faire : vision du compte déjà active."); return
    new_text = edit_config(cfg_text)                       # vérifie l'ancre AVANT de toucher au cerveau
    cdir = os.path.join("models", f"champion_{STYLE}")
    meta = json.load(open(os.path.join(cdir, "meta.json"), encoding="utf-8"))
    grafted = [(t, graft(t[0], cfg, meta)) for t in targets()]
    print(f"greffes réussies : {len(grafted)} (champion, prétendant, veines) -- décisions identiques 300/300 chacune")
    if essai:
        print("ESSAI : rien n'a été modifié"); return
    stamp = time.strftime("%Y%m%d_%H%M")
    backup = os.path.join(cdir, "history", f"avant_vision_compte_{stamp}")
    os.makedirs(backup, exist_ok=True)
    for (mp, mt), agent in grafted:
        shutil.copy(mp + ".zip", os.path.join(backup, os.path.basename(os.path.dirname(mp)) + "_" + os.path.basename(mp) + ".zip"))
        agent.save(mp)
        if mt:
            shutil.copy(mt, os.path.join(backup, "meta.json"))
            m = json.load(open(mt, encoding="utf-8"))
            m.update(updated_at=time.time(), vision_compte=True)
            json.dump(m, open(mt, "w", encoding="utf-8"), indent=1, default=str)
    shutil.copy(CONFIG, CONFIG + f".bak_vision_compte_{stamp}")
    open(CONFIG, "w", encoding="utf-8").write(new_text)
    print(f"OK : vision du compte active pour AUREXIS, sauvegardes dans {backup}")


if __name__ == "__main__":
    main("--essai" in sys.argv)
