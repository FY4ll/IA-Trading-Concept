"""
LE PROFESSEUR D'AUREXIS (09/10/2026, accord de l'utilisateur : « démerde-toi pour que mon IA fasse le maximum »).

Constat : sur les 12 mois cachés (10/2025 -> 10/2026), une règle simple de TENDANCE DE FOND jouée dans les conditions
exactes d'AUREXIS (scratchpad professeur_test.py) fait +6,4 % sur un compte tous marchés, quand le champion AUREXIS
perd presque tout. AUREXIS n'a jamais appris cet avantage de base.

Ici AUREXIS APPREND EN IMITANT (apprentissage supervisé) : on part de son cerveau actuel, on lui montre des situations
de son ENTRAÎNEMENT (tous les marchés, coupés avant 2023 : aucune fuite vers l'examen ni vers les 12 mois cachés) et
la décision du professeur dans chacune ; il apprend à reproduire la DIRECTION (acheter / vendre / rester à plat), avec
des stops larges, un objectif à 3x le risque et un stop suiveur. Ensuite son apprentissage habituel (récompense en
argent, mort FTMO, examen tournant) le pousse à faire MIEUX que le professeur. Ce n'est pas une règle imposée : c'est
un point de départ que l'IA peut abandonner si elle trouve mieux.

Ne touche à rien de ce qui tourne : écrit models/professeur_AUREXIS/ (agent.zip, meta.json, norm_stats.json, rapport).

    python scripts/professeur_aurexis.py            (cwd = code/)
"""
import json, os, shutil, sys, time
os.environ.setdefault("CUDA_VISIBLE_DEVICES", "-1")
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
os.chdir(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import numpy as np
import pandas as pd
import torch
import yaml

STYLE = "AUREXIS"
OUT = os.environ.get("PROF_SORTIE") or os.path.join("models", f"professeur_{STYLE}")
HORIZONS = (21, 63, 126, 252)                    # jours de bourse : 1, 3, 6 et 12 mois
STEPS = int(os.environ.get("PROF_ETAPES", 3000))
BATCH = int(os.environ.get("PROF_LOT", 128))


def daily_signal(path: str) -> pd.Series:
    """Signal du professeur par jour, calculé sur l'HISTORIQUE COMPLET du marché : moyenne des signes des rendements à
    1/3/6/12 mois (clôtures quotidiennes jusqu'à la veille), entre -1 et +1."""
    from src.aurexis_data import load_m15
    m15 = load_m15(path)
    d = m15.set_index("time")["close"].resample("1D").last().dropna()
    return (sum(np.sign(d / d.shift(h) - 1) for h in HORIZONS) / len(HORIZONS)).shift(1)


def teacher_direction(frame: pd.DataFrame, sig: pd.Series, mirror: bool) -> np.ndarray:
    """Décision du professeur à chaque bougie : signal >= 0,5 -> acheter (2), <= -0,5 -> vendre (0), sinon à plat (1).
    Marché miroir (prix inversés) : le signal s'inverse."""
    s = sig.reindex(pd.to_datetime(frame["time"]).dt.normalize().to_numpy()).to_numpy()
    if mirror:
        s = -s
    return np.where(s >= 0.5, 2, np.where(s <= -0.5, 0, 1)).astype(np.int64)


def main():
    from src.lockbox_gate import eval_env_kwargs
    from src.trading_env import TradingEnv
    from src.agent import TradingAgent
    from src.episodic_memory import EpisodicMemory
    from src.aurexis_data import other_markets_train, load_market_stats
    t0 = time.time()
    torch.set_num_threads(3)
    cfg = yaml.safe_load(open("../run_config_A.yaml", encoding="utf-8"))
    # point de départ : le champion (défaut) ou un autre modèle (PROF_DEPART_MODELE, ex. le professeur déjà formé)
    cdir = os.environ.get("PROF_DEPART_MODELE") or os.path.join("models", f"champion_{STYLE}")
    meta = json.load(open(os.path.join(cdir, "meta.json"), encoding="utf-8"))
    cols, ctx = meta["feature_columns"], meta.get("context_timeframes") or []
    mm = cfg["multi_market"]
    cut = pd.Timestamp(load_market_stats("EURUSD")["cut"]) + pd.Timedelta(hours=float(mm.get("embargo_hours", 48)))
    print(f"données d'entraînement coupées avant {cut.date()} (aucune fuite vers les examens)", flush=True)
    import src.aurexis_data as ad
    ad.save_market_stats = lambda *a, **k: None          # ne JAMAIS réécrire les statistiques de l'entraînement
    fred = None
    try:
        from src.fundamental_feed import AutoFundamentalFeed
        fred = getattr(AutoFundamentalFeed(cfg), "_fred", None)
    except Exception:
        pass
    frames = other_markets_train(cfg, cols, ctx, cut, max_bars_per_market=int(os.environ.get("PROF_BOUGIES", 15000)),
                                 fred=fred)
    infos = list(ad._train_info.items())                 # même ordre que `frames` (marchés construits avec succès)
    assert len(infos) == len(frames), "correspondance marchés / tranches perdue"
    kw = eval_env_kwargs(STYLE, cfg, meta)
    kw.update(trader_state=kw.get("trader_state", False))
    mem = EpisodicMemory(cfg["memory"]["db_path"], cfg["memory"]["max_episodes"],
                         private_styles=cfg["memory"].get("private_styles"))
    kw.update(memory_snapshot=mem.snapshot(dim=len(cols), sources=["backtest"], style=STYLE),
              memory_top_k=cfg.get("memory", {}).get("similarity_top_k", 5))
    envs, labels, names, signals = [], [], [], {}
    for f, (key, info) in zip(frames, infos):
        path, mirror = key[1], key[6]
        if path not in signals:
            signals[path] = daily_signal(path)
        lab = teacher_direction(f, signals[path], mirror)
        env = TradingEnv(f, feature_columns=cols, style=STYLE, **kw)
        env.reset()
        env.precompute_memory()
        envs.append(env); labels.append(lab); names.append(info["name"])
    print(f"{len(envs)} marchés prêts ({time.time() - t0:.0f} s) ; répartition professeur : "
          + ", ".join(f"{n} {np.mean(l == 2):.0%}/{np.mean(l == 0):.0%}" for n, l in list(zip(names, labels))[:6]) + "...",
          flush=True)

    agent = TradingAgent.load(os.path.join(cdir, "agent"), envs[0], {"algo": meta.get("algo", "PPO")})
    pol = agent.model.policy
    pol.set_training_mode(True)
    opt = torch.optim.Adam(pol.parameters(), lr=float(os.environ.get("PROF_LR", 1e-4)))
    rng = np.random.default_rng(0)
    nvec = envs[0].action_space.nvec
    # cibles des autres outils : stop le plus large, objectif 3x le risque, ordre au marché, stop suiveur, 0,25 %
    other_targets = [int(nvec[1]) - 1, int(nvec[2]) - 1, 0, 2, 1][:len(nvec) - 1]

    def sample(n, held_out=False):
        obs, y = [], []
        while len(obs) < n:
            k = int(rng.integers(len(envs)))
            env, lab = envs[k], labels[k]
            lo, hi = env.window_size + 1, len(env.df) - 3
            span = hi - lo
            cut_i = lo + int(span * 0.9)                    # 10 % les plus récents de chaque marché gardés pour juger
            s = int(rng.integers(cut_i, hi)) if held_out else int(rng.integers(lo, cut_i))
            env.current_step = s
            env.position, env.entry_price, env.stop_price = 0, None, None
            obs.append(env._get_obs()); y.append(lab[s])
        return np.stack(obs).astype(np.float32), np.asarray(y)

    def agreement(n=2000):
        o, y = sample(n, held_out=True)
        with torch.no_grad():
            d = pol.get_distribution(torch.as_tensor(o, device=pol.device)).distribution[0].logits.argmax(-1).cpu().numpy()
        return float(np.mean(d == y)), float(np.mean(y != 1))

    before, active = agreement()
    print(f"avant : AUREXIS d'accord avec le professeur {before:.0%} du temps (professeur en position {active:.0%})", flush=True)
    ce = torch.nn.CrossEntropyLoss()
    for step in range(1, STEPS + 1):
        o, y = sample(BATCH)
        dist = pol.get_distribution(torch.as_tensor(o, device=pol.device)).distribution
        loss = ce(dist[0].logits, torch.as_tensor(y, device=pol.device))
        for j, tgt in enumerate(other_targets, start=1):
            loss = loss + 0.2 * ce(dist[j].logits, torch.full((len(y),), tgt, device=pol.device, dtype=torch.long))
        opt.zero_grad(); loss.backward()
        torch.nn.utils.clip_grad_norm_(pol.parameters(), 0.5)
        opt.step()
        if step % 250 == 0:
            print(f"étape {step}/{STEPS} : erreur {loss.item():.3f} ({time.time() - t0:.0f} s)", flush=True)
    pol.set_training_mode(False)
    after, _ = agreement()
    print(f"après : d'accord avec le professeur {after:.0%} du temps (avant {before:.0%})", flush=True)

    os.makedirs(OUT, exist_ok=True)
    agent.save(os.path.join(OUT, "agent"))
    shutil.copy(os.path.join(cdir, "norm_stats.json"), OUT)
    m2 = {**meta, "origin": f"professeur (tendance de fond) imité depuis le champion gen {meta.get('generation')} "
                            f"le {time.strftime('%d/%m/%Y %H:%M')}", "updated_at": time.time(),
          "professeur": {"accord_avant": before, "accord_apres": after, "etapes": STEPS, "horizons": HORIZONS}}
    json.dump(m2, open(os.path.join(OUT, "meta.json"), "w", encoding="utf-8"), indent=1, default=str)
    print(f"OK : {OUT} ({(time.time() - t0) / 60:.0f} min)", flush=True)


if __name__ == "__main__":
    main()
