"""
« Ouvre » l'outil taille d'AUREXIS (09/10/2026, accord de l'utilisateur) -- puis active la note d'examen « argent FTMO ».

Constat : à la greffe (01h13) la taille a été réglée à ~70 % de chances de rester à 0,5 % pour ne rien changer à ses
décisions ; avec des entraînements courts, l'IA n'essaie presque jamais les autres tailles. Ici on ADOUCIT ses
préférences de taille (on divise les sorties « taille » du cerveau par une température T) : son choix PRÉFÉRÉ dans
chaque situation reste exactement le même (décisions identiques, vérifié sur 300 situations), mais pendant
l'entraînement elle essaie plus souvent les autres tailles (cible : ~40 % de chances pour sa taille préférée au lieu
de ~70 %). Même chose pour chaque veine vivante.

    python scripts/ouvrir_taille_aurexis.py            (cwd = code/, Run A ARRÊTÉ)
    python scripts/ouvrir_taille_aurexis.py --essai    (copie du champion, rien n'est modifié)
"""
import json, os, shutil, sys, tempfile, time
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
os.chdir(os.environ.get("GREFFE_CODE") or os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
os.environ.setdefault("CUDA_VISIBLE_DEVICES", "-1")
import numpy as np
import yaml

STYLE = "AUREXIS"
CONFIG = os.path.abspath(os.path.join("..", "run_config_A.yaml"))
TARGET_MAX_PROB = 0.40


def _size_probs(agent, env, steps):
    import torch
    out = []
    pol = agent.model.policy
    for s in steps:
        env.current_step = s
        obs, _ = pol.obs_to_tensor(env._get_obs())
        with torch.no_grad():
            out.append(pol.get_distribution(obs).distribution[-1].probs.cpu().numpy()[0])
    return np.array(out)


def open_size(model_path, cfg, meta):
    """Retourne (agent modifié, prob. max moyenne avant, après, T) ; lève SystemExit si une décision change."""
    import torch
    from src.trading_env import TradingEnv
    from src.agent import TradingAgent
    from src.lockbox_gate import eval_env_kwargs
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from graft_aurexis_taille import _situations
    cols = meta["feature_columns"]
    kw = eval_env_kwargs(STYLE, cfg, meta)
    env = TradingEnv(_situations(cols), feature_columns=cols, style=STYLE, **kw)
    if env._idx_size is None:
        raise SystemExit("ABANDON : AUREXIS n'a pas l'outil taille dans la config")
    agent = TradingAgent.load(model_path, env, {"algo": meta.get("algo", "PPO")})
    n_size = int(env.action_space.nvec[env._idx_size])
    steps = list(range(env.window_size + 5, env.window_size + 305))
    env.reset()
    ref = []
    for s in steps:
        env.current_step = s
        ref.append(np.asarray(agent.predict(env._get_obs(), deterministic=True)).tolist())
    before = float(_size_probs(agent, env, steps).max(axis=1).mean())
    net = agent.model.policy.action_net
    w0, b0 = net.weight[-n_size:].detach().clone(), net.bias[-n_size:].detach().clone()
    T = 1.0
    if before > TARGET_MAX_PROB + 0.02:
        lo, hi = 1.0, 64.0
        for _ in range(30):                               # recherche de la température qui donne ~40 %
            T = (lo + hi) / 2
            with torch.no_grad():
                net.weight[-n_size:] = w0 / T
                net.bias[-n_size:] = b0 / T
            p = float(_size_probs(agent, env, steps).max(axis=1).mean())
            lo, hi = (T, hi) if p > TARGET_MAX_PROB else (lo, T)
    after = float(_size_probs(agent, env, steps).max(axis=1).mean())
    same = 0
    for s, r in zip(steps, ref):
        env.current_step = s
        same += int(np.asarray(agent.predict(env._get_obs(), deterministic=True)).tolist() == r)
    if same != len(steps):
        raise SystemExit(f"ABANDON : {len(steps) - same} décision(s) changée(s) -- rien modifié")
    return agent, before, after, T


def edit_config(text: str) -> str:
    """Note d'examen « argent FTMO » pour AUREXIS (remplace le seul terme FTMO ajouté le 09/10 01h13)."""
    old = "  ftmo_weight_by_style: {AUREXIS: 1.0}"
    assert text.count(old) == 1, "ligne ftmo_weight_by_style introuvable"
    text = text.replace(old,
        "  # 09/10 10h : remplacé par la note « argent FTMO » (src/note_argent.py) pour AUREXIS -- 0 = pas de double compte.\n"
        "  ftmo_weight_by_style: {AUREXIS: 0.0}\n"
        "  # 09/10 10h : NOTE D'EXAMEN « ARGENT FTMO » -- un compte de 100 000 $ qui trade TOUS les marchés réels en même\n"
        "  # temps : 5 x (chance de réussir le challenge - chance d'échouer) + gain mensuel (1 point par +1 %/mois, plafonné\n"
        "  # à 1,5) - mur (baisse au-delà de 6 %, crises comprises). L'ancienne note punissait la taille (baisse x2 quand\n"
        "  # la taille double, qualité inchangée) : l'IA la plus timide était promue.\n"
        "  note_argent_by_style:\n"
        "    AUREXIS: {month_unit: 0.01, ftmo_weight: 5.0, gain_cap: 1.5, dd_wall: 0.06, dd_slope: 25.0}")
    cfg = yaml.safe_load(text)
    assert cfg["continuous"]["note_argent_by_style"][STYLE]["ftmo_weight"] == 5.0
    assert cfg["continuous"]["ftmo_weight_by_style"][STYLE] == 0.0
    return text


def main(essai: bool):
    cfg_text = open(CONFIG, encoding="utf-8").read()
    cfg = yaml.safe_load(cfg_text)
    new_text = edit_config(cfg_text) if "note_argent_by_style" not in cfg["continuous"] else None
    cdir = os.path.join("models", f"champion_{STYLE}")
    src_dir = cdir
    if essai:
        src_dir = tempfile.mkdtemp(prefix="ouvrir_taille_")
        for f in ("agent.zip", "meta.json"):
            shutil.copy(os.path.join(cdir, f), src_dir)
    meta = json.load(open(os.path.join(src_dir, "meta.json"), encoding="utf-8"))
    agent, before, after, T = open_size(os.path.join(src_dir, "agent"), cfg, meta)
    print(f"champion : taille préférée {before:.0%} -> {after:.0%} (température {T:.2f}), décisions identiques 300/300")
    veins = []
    vj = os.path.join(cdir, "veines", "veines.json")
    if os.path.exists(vj):
        veins = [v for v in json.load(open(vj, encoding="utf-8")) if os.path.exists(v["path"] + ".zip")]
    opened = [(v["path"],) + open_size(v["path"], cfg, meta)[:1] for v in veins]
    print(f"veines ouvertes : {len(opened)}")
    if essai:
        print(f"ESSAI : rien n'a été modifié (copie dans {src_dir})")
        return
    stamp = time.strftime("%Y%m%d_%H%M")
    backup = os.path.join(cdir, "history", f"avant_ouverture_taille_{stamp}")
    os.makedirs(backup, exist_ok=True)
    for f in ("agent.zip", "meta.json", "norm_stats.json"):
        if os.path.exists(os.path.join(cdir, f)):
            shutil.copy(os.path.join(cdir, f), backup)
    for vpath, va in opened:
        shutil.copy(vpath + ".zip", os.path.join(backup, os.path.basename(vpath) + ".zip"))
        va.save(vpath)
    if T > 1.0:
        agent.save(os.path.join(cdir, "agent"))
        meta.update(updated_at=time.time(), taille_ouverte={"avant": before, "apres": after, "temperature": T})
        json.dump(meta, open(os.path.join(cdir, "meta.json"), "w", encoding="utf-8"), indent=1, default=str)
    if new_text is not None:
        shutil.copy(CONFIG, CONFIG + f".bak_note_argent_{stamp}")
        open(CONFIG, "w", encoding="utf-8").write(new_text)
    print(f"OK : taille ouverte ({before:.0%} -> {after:.0%}), note argent FTMO active (sauvegarde {backup})")


if __name__ == "__main__":
    main("--essai" in sys.argv)
