"""
PRÉFORMATION DU NOUVEL AUREXIS (08/10/2026) -- un cerveau NEUF, sans rien hériter d'AUREX (biais acheteur sur l'or).

1. La mémoire à court terme (LSTM 200 -> 512, fenêtre de 50 bougies, EXACTEMENT celle de la politique d'AUREXIS)
   apprend à prédire le résultat d'un achat et d'une vente (stop 2 x ATR, objectif 2 x stop, 24 h) sur les
   situations corrigées des 10 marchés (or, euro/dollar, dollar/yen, S&P 500, livre/dollar et leurs versions
   INVERSÉES : autant de baisses que de hausses -> aucun biais acheteur). Données de scripts/moteur_prediction.py.
2. On prend la structure du champion actuel (mêmes entrées/sorties), on REMET À ZÉRO tous ses poids (tête de
   décision, valeur, LSTM), puis on y place la LSTM préformée. Optimiseur neuf.
Ne touche à rien de ce qui tourne : écrit models/aurexis_neuf/ (agent.zip, lstm_preforme.pt, rapport.json).

    python scripts/preformation_aurexis.py            (cwd = code/)
"""
import json, os, sys, time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
os.chdir(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import numpy as np
import pandas as pd
import torch
import torch.nn as nn

import moteur_prediction as mp

OUT = os.path.join("models", "aurexis_neuf")
log = mp.log


class Pre(nn.Module):
    def __init__(self, n_features, hidden):
        super().__init__()
        self.lstm = nn.LSTM(input_size=n_features, hidden_size=hidden, batch_first=True)
        self.head = nn.Sequential(nn.Dropout(0.2), nn.Linear(hidden, 128), nn.ReLU(), nn.Linear(128, 2))

    def forward(self, x):
        _, (h, _) = self.lstm(x)
        return self.head(h[-1])


def reinit_policy(policy):
    """Poids neufs partout (même règles d'initialisation que stable-baselines3), optimiseur neuf."""
    for m in policy.modules():
        if isinstance(m, nn.Linear):
            nn.init.orthogonal_(m.weight, gain=np.sqrt(2))
            nn.init.zeros_(m.bias)
        elif isinstance(m, nn.LSTM):
            m.reset_parameters()
    nn.init.orthogonal_(policy.action_net.weight, gain=0.01)
    nn.init.zeros_(policy.action_net.bias)
    nn.init.orthogonal_(policy.value_net.weight, gain=1.0)
    nn.init.zeros_(policy.value_net.bias)
    policy.optimizer = policy.optimizer_class(policy.parameters(), lr=policy.optimizer.param_groups[0]["lr"],
                                              **(policy.optimizer_kwargs or {}))


def main():
    t_start = time.time()
    mp.W, mp.H = 50, 96
    os.makedirs(OUT, exist_ok=True)
    dm = json.load(open(os.path.join(mp.OUT, "meta.json"), encoding="utf-8"))
    F = dm["n_features"]
    X = np.memmap(os.path.join(mp.OUT, "X.f16"), dtype=np.float16, mode="r", shape=(dm["total"], F))
    TRAIN_END = mp.TRAIN_END
    VAL_A_END = TRAIN_END + pd.Timedelta(days=300)
    Y = np.full((dm["total"], 2), np.nan, np.float32)
    tr_idx, va_idx = [], []
    for mi, mk in enumerate(dm["markets"]):
        r = np.load(os.path.join(mp.OUT, f"raw_{mi}.npz"))
        cost = 0.0002 if mk["name"].startswith("XAUUSD") else 0.0001
        Rl, Rs, _, _ = mp.labels(r["open"], r["high"], r["low"], r["close"], r["atr"], 2.0, cost)
        times = pd.to_datetime(r["time"])
        ok = np.isfinite(Rl) & np.isfinite(Rs)
        ok[:mp.W] = False
        g = mk["start"] + np.arange(mk["n"])
        Y[g, 0], Y[g, 1] = Rl, Rs
        tr_idx.append(g[ok & (times < TRAIN_END - pd.Timedelta(hours=48))][::2])
        va_idx.append(g[ok & (times >= TRAIN_END) & (times < VAL_A_END)])
    tr_idx, va_all = np.concatenate(tr_idx), np.concatenate(va_idx)
    rng = np.random.default_rng(1)
    va_s = rng.choice(va_all, min(100_000, len(va_all)), replace=False)
    meta = json.load(open(os.path.join("models", "champion_AUREXIS", "meta.json"), encoding="utf-8"))
    hidden = int(meta.get("lstm_hidden_size", 512))
    dev = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    net = Pre(F, hidden).to(dev)
    opt = torch.optim.AdamW(net.parameters(), lr=5e-4, weight_decay=1e-3)
    loss_fn = nn.HuberLoss(delta=1.0)
    bs = 512
    log(f"préformation LSTM {F} -> {hidden} sur {len(tr_idx)} situations ({dev}), contrôle {len(va_s)}")
    best, best_state, patience, hist = 1e9, None, 0, []
    for ep in range(6):
        net.train()
        perm = rng.permutation(tr_idx)
        t0, tot, k = time.time(), 0.0, 0
        for k, (b, xb) in enumerate(mp.batches(X, perm, bs)):
            xt = torch.as_tensor(xb, device=dev)
            xt = xt + 0.2 * torch.randn_like(xt)
            loss = loss_fn(net(xt), torch.as_tensor(Y[b], device=dev))
            opt.zero_grad(); loss.backward()
            nn.utils.clip_grad_norm_(net.parameters(), 1.0)
            opt.step()
            tot += float(loss)
        net.eval()
        pv = np.zeros((len(va_s), 2), np.float32)
        with torch.no_grad():
            for j, (b, xb) in enumerate(mp.batches(X, va_s, 2048)):
                pv[j * 2048:j * 2048 + len(b)] = net(torch.as_tensor(xb, device=dev)).cpu().numpy()
        d = np.abs(pv - Y[va_s])
        vloss = float(np.mean(np.where(d < 1, 0.5 * d ** 2, d - 0.5)))
        cl, cs = float(np.corrcoef(pv[:, 0], Y[va_s, 0])[0, 1]), float(np.corrcoef(pv[:, 1], Y[va_s, 1])[0, 1])
        hist.append({"passe": ep + 1, "erreur": tot / (k + 1), "validation": vloss, "lien_achat": cl, "lien_vente": cs})
        log(f"  passe {ep + 1} : erreur {tot / (k + 1):.4f} | validation {vloss:.4f} | lien prédiction/réalité "
            f"achat {cl:+.3f} vente {cs:+.3f} ({time.time() - t0:.0f} s)")
        if vloss < best - 1e-4:
            best, patience = vloss, 0
            best_state = {k_: v.detach().cpu().clone() for k_, v in net.state_dict().items()}
        else:
            patience += 1
            if patience >= 2:
                break
    net.load_state_dict(best_state)
    lstm_state = {k_[len("lstm."):]: v for k_, v in best_state.items() if k_.startswith("lstm.")}
    torch.save(lstm_state, os.path.join(OUT, "lstm_preforme.pt"))

    # cerveau neuf : structure du champion, poids remis à zéro, LSTM préformée
    from stable_baselines3 import PPO
    model = PPO.load(os.path.join("models", "champion_AUREXIS", "agent"), device="cpu")
    pol = model.policy
    reinit_policy(pol)
    extractors = [m for m in (getattr(pol, "features_extractor", None), getattr(pol, "pi_features_extractor", None),
                              getattr(pol, "vf_features_extractor", None)) if m is not None]
    for ex in {id(e): e for e in extractors}.values():
        ex.lstm.load_state_dict(lstm_state)
    model.num_timesteps = 0
    model.save(os.path.join(OUT, "agent"))
    # contrôle : sur 2 000 situations de l'or (validation), répartition des décisions du cerveau neuf
    gold = dm["markets"][0]
    idx = gold["start"] + np.arange(mp.W, gold["n"], max(1, gold["n"] // 2000))[:2000]
    with torch.no_grad():
        seq = torch.as_tensor(np.asarray(X[idx[:, None] + np.arange(-mp.W + 1, 1)[None, :]], dtype=np.float32))
        p_pre = net.cpu()(seq).numpy()
    report = {"passes": hist, "lstm": f"{F}->{hidden}", "fenetre": mp.W,
              "part_achat_prefere": float((p_pre[:, 0] > p_pre[:, 1]).mean()),
              "duree_min": round((time.time() - t_start) / 60, 1)}
    json.dump(report, open(os.path.join(OUT, "rapport.json"), "w", encoding="utf-8"), indent=1)
    log(f"cerveau neuf écrit dans {OUT}/agent.zip ; la mémoire préformée préfère l'achat dans "
        f"{report['part_achat_prefere']:.0%} des situations de l'or (AUREX : ~100 %)")
    log("TERMINÉ")


if __name__ == "__main__":
    main()
