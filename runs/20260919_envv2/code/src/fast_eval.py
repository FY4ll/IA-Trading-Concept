"""
fast_eval.py
=============
Évaluation ACCÉLÉRÉE d'un épisode (06/10/2026) -- mêmes décisions que backtester.run_episode, en
beaucoup moins de temps.

Constat (mesuré sur AUREX) : ~85 % d'un cycle d'évolution passe dans l'ÉVALUATION des candidats, pas
dans l'apprentissage. À chaque bougie, le LSTM (src/policy_networks.py) relit toute la fenêtre de
50 bougies, une bougie à la fois, alors que cette partie du réseau ne dépend QUE du marché : la
position, le gain latent, la mémoire et la journée du trader ("extra") ne sont ajoutés qu'APRÈS le
LSTM, dans la petite tête de décision.

Donc : 1) l'état LSTM de TOUTES les bougies est calculé d'avance, par gros paquets (calcul vectorisé) ;
2) la boucle bougie par bougie (qui dépend de la position) n'exécute plus que la tête + le MLP de la
politique. Décisions identiques à la version pas à pas (vérifié par tests/test_fast_eval.py), repli
automatique sur la version d'origine pour tout réseau qui ne correspond pas à ce schéma.
"""
from __future__ import annotations
import logging

import numpy as np
import torch

log = logging.getLogger("fast_eval")
CHUNK = 2048


def supported(agent, env) -> bool:
    try:
        from src.policy_networks import LSTMFeaturesExtractor
        from stable_baselines3 import PPO
        pol = agent.model.policy
        return (isinstance(agent.model, PPO) and isinstance(pol.features_extractor, LSTMFeaturesExtractor)
                and not getattr(env, "continuous_action", False)
                and pol.features_extractor.window_size == env.window_size
                and pol.features_extractor.n_features == env.n_features)
    except Exception:
        return False


@torch.no_grad()
def _precompute_on(lstm, feature_values: np.ndarray, window: int, chunk: int) -> torch.Tensor:
    n, f = feature_values.shape
    dev = next(lstm.parameters()).device
    fv = torch.as_tensor(np.ascontiguousarray(feature_values, dtype=np.float32), device=dev)
    out = torch.zeros((n, lstm.hidden_size), dtype=torch.float32)
    steps = np.arange(window, n)
    for a in range(0, len(steps), chunk):
        s = steps[a:a + chunk]
        idx = torch.as_tensor(s[:, None] - window + np.arange(window)[None, :], device=dev)
        _, (h_n, _) = lstm(fv[idx])                     # fv[idx] : (b, window, f)
        out[torch.as_tensor(s)] = h_n[-1].float().cpu()
    return out


@torch.no_grad()
def precompute_lstm(extractor, feature_values: np.ndarray, window: int) -> torch.Tensor:
    """État final du LSTM pour chaque pas s (fenêtre feature_values[s-window:s]), index s -> ligne s.
    07/10/2026 : calculé sur le matériel du réseau -- carte graphique si disponible (~30x plus rapide), par paquets
    de 256 (plusieurs processus se partagent 6 Go) ; si la carte est pleine, repli sur le processeur."""
    lstm = extractor.lstm
    dev = next(lstm.parameters()).device
    if dev.type != "cuda":
        # 10/10/2026 : le réseau vit sur le processeur (agent.device: cpu) -> la relecture des fenêtres n'utilisait
        # JAMAIS la carte graphique, alors qu'avec 512 neurones et 205 variables elle prend ~64 % de l'examen (11,7 s
        # sur 18,3 s par marché-période, mesuré). Copie du LSTM sur la carte le temps du calcul (~12x plus rapide,
        # écart < 1e-5), résultat rendu au processeur. Repli sur le processeur si carte absente, pleine ou en erreur.
        import os
        if torch.cuda.is_available() and os.environ.get("FAST_EVAL_GPU", "1") != "0":
            import copy
            try:
                g = copy.deepcopy(lstm).cuda()
                return _precompute_on(g, feature_values, window, 256).cpu()
            except Exception as e:                          # carte pleine (plusieurs processus) ou indisponible
                torch.cuda.empty_cache()
                log.warning(f"Relecture sur carte graphique impossible ({type(e).__name__}) -> processeur.")
        return _precompute_on(lstm, feature_values, window, CHUNK)
    try:
        return _precompute_on(lstm, feature_values, window, 256)
    except torch.cuda.OutOfMemoryError:
        import copy
        torch.cuda.empty_cache()
        log.warning("Carte graphique pleine pendant la relecture des bougies -> calcul sur le processeur.")
        return _precompute_on(copy.deepcopy(lstm).cpu(), feature_values, window, CHUNK)


class _NumpyHead:
    """Tête de décision (head + MLP acteur + action_net) recopiée en NumPy : à cette taille (quelques
    milliers de poids), NumPy évite le coût fixe de PyTorch à chaque bougie. None si une couche n'est
    pas reconnue (repli sur la version PyTorch)."""

    _ACT = {"ReLU": lambda x: np.maximum(x, 0.0), "Tanh": np.tanh, "Identity": lambda x: x}

    def __init__(self, policy):
        import torch.nn as nn
        self.layers = []
        mods = list(policy.features_extractor.head) + list(policy.mlp_extractor.policy_net) + [policy.action_net]
        for m in mods:
            if isinstance(m, nn.Linear):
                self.layers.append(("lin", m.weight.detach().cpu().numpy().astype(np.float64).T.copy(),
                                    m.bias.detach().cpu().numpy().astype(np.float64).copy()))
            elif type(m).__name__ in self._ACT:
                self.layers.append(("act", self._ACT[type(m).__name__], None))
            else:
                raise TypeError(type(m).__name__)
        nvec = getattr(policy.action_space, "nvec", None)
        self.splits = np.cumsum([int(x) for x in nvec])[:-1] if nvec is not None else None

        self.bounds = list(zip(np.r_[0, self.splits], np.r_[self.splits, 10 ** 9])) if self.splits is not None else None

    def act(self, hidden: np.ndarray, extra: np.ndarray):
        x = np.concatenate([hidden, extra]).astype(np.float64)
        for kind, a, b in self.layers:
            x = x @ a + b if kind == "lin" else a(x)
        return self._argmax(x)

    def _argmax(self, x):
        if self.bounds is None:
            return int(np.argmax(x))
        return np.array([int(np.argmax(x[a:b])) for a, b in self.bounds])

    # 12/10/2026 : la PREMIÈRE couche de la tête reçoit [état LSTM (512), situation (10)]. La partie « état LSTM »
    # ne dépend que des bougies : calculée d'avance pour TOUTES les bougies d'un coup (carte graphique si disponible,
    # double précision comme le reste de la tête) ; à chaque bougie il ne reste que la petite partie « situation ».
    def precompute_first(self, hidden: torch.Tensor) -> np.ndarray | None:
        if not self.layers or self.layers[0][0] != "lin":
            return None
        w, b = self.layers[0][1], self.layers[0][2]             # w : (512 + extra, sortie)
        n_h = hidden.shape[1]
        self.w_extra = w[n_h:]
        import os
        if torch.cuda.is_available() and os.environ.get("FAST_EVAL_GPU", "1") != "0":
            try:
                with torch.no_grad():
                    out = (hidden.to("cuda", torch.float64) @ torch.as_tensor(w[:n_h], device="cuda")
                           + torch.as_tensor(b, device="cuda"))
                return out.cpu().numpy()
            except Exception as e:
                torch.cuda.empty_cache()
                log.warning(f"Tête pré-calculée sur carte graphique impossible ({type(e).__name__}) -> processeur.")
        return hidden.numpy().astype(np.float64) @ w[:n_h] + b

    def act_pre(self, pre_row: np.ndarray, extra: np.ndarray):
        x = pre_row + np.asarray(extra, dtype=np.float64) @ self.w_extra
        for kind, a, b in self.layers[1:]:
            x = x @ a + b if kind == "lin" else a(x)
        return self._argmax(x)


@torch.no_grad()
def _act(policy, hidden: torch.Tensor, extra: np.ndarray):
    ex = policy.features_extractor
    dev = next(ex.head.parameters()).device
    feats = ex.head(torch.cat([hidden.unsqueeze(0).to(dev),
                               torch.as_tensor(extra, dtype=torch.float32, device=dev).unsqueeze(0)], dim=1))
    latent_pi = policy.mlp_extractor.forward_actor(feats)
    logits = policy.action_net(latent_pi)
    nvec = getattr(policy.action_space, "nvec", None)
    if nvec is None:                                    # Discrete
        return int(torch.argmax(logits, dim=1).item())
    parts = torch.split(logits, [int(x) for x in nvec], dim=1)
    return np.array([int(torch.argmax(p, dim=1).item()) for p in parts])


def run_episode_fast(agent, env):
    """Équivalent de backtester.run_episode (actions déterministes), LSTM pré-calculé."""
    policy = agent.model.policy
    policy.set_training_mode(False)
    hidden = precompute_lstm(policy.features_extractor, env._feature_values, env.window_size)
    pre = None
    try:
        head = _NumpyHead(policy)
        pre = head.precompute_first(hidden)
        hidden_np = None if pre is not None else hidden.numpy().astype(np.float64)
    except Exception:
        head = None
    seq_len = env.window_size * env.n_features
    lean = hasattr(env, "_extra_obs")                   # 12/10/2026 : seulement la situation, pas la fenêtre entière
    if hasattr(env, "precompute_memory"):
        env.precompute_memory()                         # 07/10/2026 : recherche en mémoire groupée (~50x)
    env.reset()
    env._lean_obs = lean
    try:
        done = False
        while not done:
            obs_extra = env._extra_obs() if lean else env._get_obs()[seq_len:]
            if pre is not None:
                action = head.act_pre(pre[env.current_step], obs_extra)
            elif head is not None:
                action = head.act(hidden_np[env.current_step], obs_extra)
            else:
                action = _act(policy, hidden[env.current_step], obs_extra)
            _, _, terminated, truncated, _ = env.step(action)
            done = terminated or truncated
    finally:
        env._lean_obs = False
    return env
