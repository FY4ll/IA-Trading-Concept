"""
evolution.py
============
Mutation des hyperparamètres d'un agent pour créer des variantes candidates
à chaque cycle d'évolution continue (voir src/continuous_trainer.py) --
c'est le mécanisme qui implémente le principe "Évolution / sélection" de
la vision du projet : chaque cycle fait légèrement varier quelques
hyperparamètres, entraîne les variantes en parallèle, et ne garde que ce
qui fait mieux que le champion actuel.
"""
from __future__ import annotations
import copy
import random
import numpy as np


# Bornes par défaut (comportement d'origine) -- surchargées par
# config/autonomous.yaml, section evolution.mutation_bounds, voir
# mutate_hyperparams ci-dessous.
DEFAULT_MUTATION_BOUNDS = {
    "learning_rate": (1e-5, 1e-2),
    "ent_coef": (1e-4, 0.5),
    "gamma": (0.90, 0.999),
    "gae_lambda": (0.80, 0.999),
    "n_epochs": (3, 30),
}


def mutate_hyperparams(hp: dict, scale: float, mutation_bounds: dict | None = None) -> dict:
    bounds = {**DEFAULT_MUTATION_BOUNDS, **(mutation_bounds or {})}
    new_hp = copy.deepcopy(hp)
    lr_lo, lr_hi = bounds["learning_rate"]
    new_hp["learning_rate"] = float(np.clip(
        hp["learning_rate"] * (1 + random.uniform(-scale, scale)), lr_lo, lr_hi))
    ent_lo, ent_hi = bounds["ent_coef"]
    new_hp["ent_coef"] = float(np.clip(
        hp["ent_coef"] * (1 + random.uniform(-scale, scale)), ent_lo, ent_hi))
    gamma_lo, gamma_hi = bounds["gamma"]
    new_hp["gamma"] = float(np.clip(
        hp["gamma"] + random.uniform(-0.02, 0.02) * scale, gamma_lo, gamma_hi))
    # gae_lambda et n_epochs (compromis biais/variance de l'estimation
    # d'avantage, et nombre de passes d'optimisation par batch de PPO) :
    # mutables sans risque puisqu'ils ne changent jamais la forme du réseau
    # (contrairement à net_arch), donc le warm start reste toujours possible
    # même quand ils varient d'un candidat à l'autre.
    gae_lo, gae_hi = bounds["gae_lambda"]
    new_hp["gae_lambda"] = float(np.clip(
        hp.get("gae_lambda", 0.95) + random.uniform(-0.05, 0.05) * scale, gae_lo, gae_hi))
    epochs_lo, epochs_hi = bounds["n_epochs"]
    new_hp["n_epochs"] = int(np.clip(
        round(hp.get("n_epochs", 10) * (1 + random.uniform(-scale, scale))), epochs_lo, epochs_hi))
    return new_hp
