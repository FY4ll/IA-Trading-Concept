# Repris de Run A (src/policy_networks.py, version du 08/10/2026) pour l'architecture v3 -- calculs IDENTIQUES
# (prouvé par tests/test_cerveau_equivalence.py). Toute modification doit garder ce test vert.
"""
policy_networks.py
===================
Extracteur de features personnalisé pour la politique PPO (stable-baselines3).

Par défaut, un MlpPolicy traite l'observation comme un simple vecteur plat :
la fenêtre glissante de bougies (`window_size` x features) est déjà aplatie
par `TradingEnv._get_obs`, donc le réseau ne "voit" aucune structure
temporelle -- il doit la redécouvrir indirectement à partir d'indicateurs
déjà pré-calculés (RSI, MACD...), sans jamais percevoir l'ORDRE des pas de
temps entre eux.

`LSTMFeaturesExtractor` reconstruit la séquence (window_size, n_features) à
partir du vecteur aplati et la fait parcourir par un LSTM, qui produit un
état récapitulant l'évolution récente du marché. Cet état est ensuite
combiné avec les variables hors-séquence (position courante, pnl flottant,
signal de mémoire épisodique -- voir trading_env.py) avant la tête de
décision de PPO. C'est la partie du réseau qui manquait pour que l'agent
apprenne des motifs temporels (accélération, retournement, essoufflement
d'une tendance...) plutôt que de les déduire indirectement.
"""
from __future__ import annotations
import torch
import torch.nn as nn
from gymnasium import spaces
from stable_baselines3.common.torch_layers import BaseFeaturesExtractor


class LSTMFeaturesExtractor(BaseFeaturesExtractor):
    def __init__(self, observation_space: spaces.Box, window_size: int, n_features: int,
                 extra_dim: int = 4, lstm_hidden_size: int = 128, features_dim: int = 128):
        super().__init__(observation_space, features_dim=features_dim)
        self.window_size = window_size
        self.n_features = n_features
        self.extra_dim = extra_dim
        self.lstm = nn.LSTM(input_size=n_features, hidden_size=lstm_hidden_size, batch_first=True)
        self.head = nn.Sequential(
            nn.Linear(lstm_hidden_size + extra_dim, features_dim),
            nn.ReLU(),
        )

    def forward(self, observations: torch.Tensor) -> torch.Tensor:
        seq_len = self.window_size * self.n_features
        seq = observations[:, :seq_len].reshape(-1, self.window_size, self.n_features)
        extra = observations[:, seq_len:seq_len + self.extra_dim]
        _, (h_n, _) = self.lstm(seq)
        last_hidden = h_n[-1]  # état final de la dernière couche LSTM
        return self.head(torch.cat([last_hidden, extra], dim=1))
