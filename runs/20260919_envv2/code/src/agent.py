"""
agent.py
========
Encapsule l'algorithme d'apprentissage par renforcement. C'est la partie
"Deep Learning" qui apprend, à partir de l'expérience accumulée dans
l'environnement, quelle action prendre dans chaque état.

Deux familles supportées (`agent.algo` dans la config) :
  - "PPO" (par défaut) : action DISCRÈTE (short/flat/long) -- comportement
    historique du projet, inchangé.
  - "SAC" / "TD3" : action CONTINUE -- l'agent apprend directement
    l'INTENSITÉ de la position (pas juste sa direction), voir
    `TradingEnv(continuous_action=True)`. Change l'algorithme entier (hors-
    politique, mémoire de replay), pas juste un réglage : à activer en
    connaissance de cause, voir README.

Supporte explicitement le choix du device (CPU/GPU) et la taille du réseau
(voir `agent.device` et `agent.net_arch` dans la config), ainsi qu'un
affichage périodique de la progression pendant l'entraînement (utile en
mode multi-processus, où chaque candidat tourne en parallèle sans autre
retour visuel qu'un log).
"""
from __future__ import annotations
import os
import json
import logging
from stable_baselines3 import PPO, SAC, TD3
from stable_baselines3.common.vec_env import DummyVecEnv
from stable_baselines3.common.callbacks import BaseCallback

from src.policy_networks import LSTMFeaturesExtractor
from src.trading_env import ENV_VERSION, env_version_matches, EnvVersionMismatch

log = logging.getLogger("agent")

ALGO_CLASSES = {"PPO": PPO, "SAC": SAC, "TD3": TD3}


class _ProgressLogCallback(BaseCallback):
    """Affiche périodiquement l'avancement (%) d'un entraînement, avec un
    label identifiant le candidat/style/génération concerné -- remplace les
    barres de progression tqdm (illisibles avec plusieurs processus en
    parallèle) par de simples lignes de log lisibles dans n'importe quel
    terminal."""
    def __init__(self, total_timesteps: int, label: str, every_pct: int = 20):
        super().__init__(verbose=0)
        self.total_timesteps = max(1, total_timesteps)
        self.label = label
        self.every_pct = max(1, every_pct)
        self._next_pct = self.every_pct

    def _on_step(self) -> bool:
        pct = 100 * self.num_timesteps / self.total_timesteps
        if pct >= self._next_pct:
            log.info(f"{self.label} : {self.num_timesteps}/{self.total_timesteps} pas ({pct:.0f}%)")
            self._next_pct += self.every_pct
        return True


def _algo_class(hyperparams: dict):
    name = str(hyperparams.get("algo", "PPO")).upper()
    return ALGO_CLASSES.get(name, PPO)


class TradingAgent:
    def __init__(self, env, hyperparams: dict, warm_start_model_path: str | None = None):
        self.hyperparams = hyperparams
        self._algo_class = _algo_class(hyperparams)
        # PARTIES EN PARALLÈLE (07/10/2026, `n_envs`) : plusieurs copies de l'environnement jouent chacune leur
        # propre partie (départ au hasard) ; le réseau décide pour toutes d'un coup -> la carte graphique calcule
        # n décisions par appel au lieu d'une. Copies légères : les données du marché sont partagées, chaque
        # copie a son propre état (remis à neuf par reset) et son propre tirage au hasard.
        n_envs = int(hyperparams.get("n_envs", 1) or 1)
        envs = [env]
        if n_envs > 1 and self._algo_class is PPO:
            import copy
            for _ in range(n_envs - 1):
                e = copy.copy(env)
                e._np_random = None                       # tirage au hasard propre à cette copie
                envs.append(e)
            # 11/10/2026 : COMPTE PARTAGÉ (src/shared_account.py) -- les parties en parallèle tradent un seul compte
            if hasattr(env, "link_account"):
                env.link_account(envs)
        vec_env = DummyVecEnv([(lambda e=e: e) for e in envs])
        self.n_envs = len(envs)
        net_arch = hyperparams.get("net_arch")

        if hyperparams.get("use_lstm", True):
            # Remplace l'aplatissement par défaut (MlpPolicy) par un LSTM qui
            # parcourt réellement la séquence temporelle avant la tête de
            # décision -- voir src/policy_networks.py. `env` est l'environnement
            # BRUT (pas encore vectorisé) : window_size/n_features/EXTRA_DIM y
            # sont directement accessibles. Fonctionne pour PPO ET SAC/TD3
            # (tous acceptent features_extractor_class/kwargs via policy_kwargs).
            lstm_hidden = hyperparams.get("lstm_hidden_size", 128)
            policy_kwargs = {
                "net_arch": net_arch or [64],
                "features_extractor_class": LSTMFeaturesExtractor,
                "features_extractor_kwargs": {
                    "window_size": env.window_size,
                    "n_features": env.n_features,
                    "extra_dim": env.EXTRA_DIM,
                    "lstm_hidden_size": lstm_hidden,
                    "features_dim": lstm_hidden,
                },
            }
        else:
            policy_kwargs = {"net_arch": net_arch} if net_arch else None

        common_kwargs = dict(
            device=hyperparams.get("device", "auto"),
            policy_kwargs=policy_kwargs,
            verbose=0,
        )
        if self._algo_class is PPO:
            self.model = PPO(
                hyperparams.get("policy", "MlpPolicy"), vec_env,
                learning_rate=hyperparams.get("learning_rate", 3e-4),
                # n_steps est PAR partie : même taille de lot qu'avant (n_steps x parties ~ n_steps d'origine)
                n_steps=max(64, int(hyperparams.get("n_steps", 2048)) // self.n_envs),
                batch_size=hyperparams.get("batch_size", 256),
                gamma=hyperparams.get("gamma", 0.99),
                gae_lambda=hyperparams.get("gae_lambda", 0.95),
                ent_coef=hyperparams.get("ent_coef", 0.01),
                n_epochs=hyperparams.get("n_epochs", 10),
                # 06/10/2026 : perfectionnement stable d'un modèle déjà formé -- clip_range borne le changement de
                # politique par mise à jour, target_kl arrête une mise à jour qui s'éloigne trop (anti-régression).
                clip_range=hyperparams.get("clip_range", 0.2),
                target_kl=hyperparams.get("target_kl"),
                **common_kwargs,
            )
        else:
            # SAC / TD3 : hors-politique (replay buffer), hyperparamètres
            # différents de PPO -- n_steps/gae_lambda/n_epochs n'existent
            # pas ici, ne sont jamais passés (mutés par evolution.py mais
            # simplement ignorés pour ces algos, sans erreur).
            algo_kwargs = dict(
                learning_rate=hyperparams.get("learning_rate", 3e-4),
                buffer_size=hyperparams.get("buffer_size", 100_000),
                batch_size=hyperparams.get("batch_size", 256),
                gamma=hyperparams.get("gamma", 0.99),
                tau=hyperparams.get("tau", 0.005),
                learning_starts=hyperparams.get("learning_starts", 100),
                train_freq=hyperparams.get("train_freq", 1),
                **common_kwargs,
            )
            if self._algo_class is SAC:
                algo_kwargs["ent_coef"] = hyperparams.get("ent_coef", "auto")
            self.model = self._algo_class(hyperparams.get("policy", "MlpPolicy"), vec_env, **algo_kwargs)

        # ÉVOLUTION CONTINUE : au lieu de repartir d'un réseau vierge à chaque
        # cycle, on peut réinjecter les poids d'un agent déjà entraîné (le
        # "champion" actuel) avant de continuer l'apprentissage. C'est ce qui
        # permet à l'agent de progresser cycle après cycle plutôt que de
        # réapprendre depuis zéro à chaque fois. Si les poids ne sont pas
        # compatibles (ex: nombre de features différent -> style/timeframe
        # différent, ou changement d'algorithme -> architecture de réseau
        # différente), l'échec est silencieux et l'agent repart à neuf.
        self.warm_started = False          # 10/10 : vrai seulement si des poids ont réellement été rechargés
        if warm_start_model_path and os.path.exists(warm_start_model_path + ".zip"):
            self._warm_start(warm_start_model_path)

    def _warm_start(self, path: str):
        # GATE ENV_VERSION (LOT 2, phase 1) : AVANT tout essai de chargement
        # des poids, refuse le warm start si le meta.json du modèle source
        # indique une version d'environnement différente -- sans ce garde-fou,
        # un warm start pourrait "réussir" (même forme de réseau par
        # coïncidence) tout en réinjectant des poids appris sous une
        # sémantique d'observation/action différente, silencieusement.
        # meta.json illisible/absent : comportement d'ORIGINE, on tente quand
        # même le warm start ci-dessous (jamais plus strict qu'avant pour un
        # modèle sans meta -- seul un env_version EXPLICITEMENT différent
        # bloque).
        meta_path = os.path.join(os.path.dirname(path), "meta.json")
        if os.path.exists(meta_path):
            try:
                with open(meta_path, encoding="utf-8") as f:
                    meta = json.load(f)
                if not env_version_matches(meta):
                    log.info(f"Warm start refusé depuis {path} (env_version="
                              f"{meta.get('env_version', 1)} != {ENV_VERSION}) -> agent réinitialisé "
                              f"à neuf (changement d'environnement volontaire, warm-start "
                              f"intentionnellement rompu une fois -- voir LOT 2 phase 1).")
                    return
            except Exception:
                pass  # meta illisible -> tente quand même le warm start ci-dessous
        try:
            old_model = self._algo_class.load(path, device="cpu")
            self.model.policy.load_state_dict(old_model.policy.state_dict())
            self.warm_started = True
            log.info(f"Warm start réussi depuis {path} (poids réutilisés).")
        except Exception as e:
            log.info(f"Warm start impossible depuis {path} ({type(e).__name__}) -> agent réinitialisé à neuf "
                      f"(normal si le style/timeframe ou l'algorithme a changé depuis le dernier champion "
                      f"de cette lignée).")

    def learn(self, total_timesteps: int, label: str | None = None):
        callback = _ProgressLogCallback(total_timesteps, label) if label else None
        self.model.learn(total_timesteps=total_timesteps, callback=callback, progress_bar=False)

    def predict(self, obs, deterministic=True):
        action, _ = self.model.predict(obs, deterministic=deterministic)
        return action

    def predict_proba(self, obs):
        """Distribution de probabilité (court/plat/long) de la dimension
        DIRECTION de l'action pour `obs` (29/09, demande explicite --
        traçabilité des décisions démo, voir demo_trader.py) -- jamais
        utilisé pour décider (predict() reste la seule source de vérité
        pour la décision réelle envoyée au broker), uniquement pour le
        logging. `None` en best-effort (algo/action continue sans
        distribution catégorielle, ex: SAC/TD3) -- ne doit jamais faire
        échouer une décision réelle si l'extraction échoue.
        """
        try:
            obs_tensor, _ = self.model.policy.obs_to_tensor(obs)
            dist = self.model.policy.get_distribution(obs_tensor).distribution
            sub_dist = dist[0] if isinstance(dist, (list, tuple)) else dist
            probs = sub_dist.probs.detach().cpu().numpy()[0]
            return {"short": float(probs[0]), "flat": float(probs[1]), "long": float(probs[2])}
        except Exception:
            return None

    def save(self, path: str):
        self.model.save(path)

    @classmethod
    def load(cls, path: str, env, hyperparams: dict):
        # GATE ENV_VERSION (LOT 2, phase 1) : refus EXPLICITE (exception, pas
        # un simple log) de charger un modèle pour l'INFÉRENCE (démo live,
        # scripts d'évaluation) si son meta.json indique une version
        # d'environnement différente -- contrairement au warm start
        # (_warm_start ci-dessus, qui dégrade silencieusement vers un agent
        # neuf, un comportement normal et fréquent), charger un modèle
        # INCOMPATIBLE pour DÉCIDER de vrais ordres serait une erreur
        # silencieuse bien plus grave : mieux vaut un crash explicite qu'une
        # décision prise sur une sémantique d'observation/action erronée.
        # meta.json absent : comportement d'ORIGINE (pas de blocage) -- seul
        # un env_version EXPLICITEMENT différent lève cette exception.
        meta_path = os.path.join(os.path.dirname(path), "meta.json")
        if os.path.exists(meta_path):
            with open(meta_path, encoding="utf-8") as f:
                meta = json.load(f)
            if not env_version_matches(meta):
                raise EnvVersionMismatch(
                    f"Chargement refusé pour '{path}' : env_version="
                    f"{meta.get('env_version', 1)} != ENV_VERSION actuel ({ENV_VERSION}) -- "
                    f"espace d'observation/action potentiellement différent, ce modèle ne peut "
                    f"pas être utilisé pour l'inférence tant qu'il n'a pas été réentraîné sous "
                    f"la version actuelle (voir LOT 2 phase 1).")
        instance = cls(env, hyperparams)
        # 10/10/2026 : les candidats peuvent apprendre sur la carte graphique ; un programme qui la cache (examen du
        # jour, AUREXIS à blanc, verdict) doit pouvoir recharger le cerveau sur le processeur, sans dépendre de la
        # détection « auto ».
        import torch
        dev = hyperparams.get("device") or ("auto" if torch.cuda.is_available() else "cpu")
        if dev != "cpu" and not torch.cuda.is_available():
            dev = "cpu"
        instance.model = instance._algo_class.load(path, env=DummyVecEnv([lambda: env]), device=dev)
        return instance
