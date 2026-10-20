"""
experiment_journal.py
=====================
Journal des expériences de l'IA et recherche autonome sur la FONCTION DE RÉCOMPENSE.

L'IA fait varier d'elle-même certains paramètres de sa récompense (pénalité de drawdown,
friction, giveback) d'un candidat à l'autre ; chaque essai est journalisé avec son score.
Le centre de la recherche suit le meilleur essai connu du style. Le juge (score walk-forward,
validation, porte lockbox) reste hors de portée : seule la récompense d'ENTRAÎNEMENT varie.
"""
from __future__ import annotations
import json
import math
import os
import random

JOURNAL_PATH = os.path.join("reports", "experiment_journal.jsonl")
_TAIL = 400


def append(entries: list[dict], path: str = JOURNAL_PATH) -> None:
    if not entries:
        return
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        for e in entries:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")


def _read_tail(path: str, n: int = _TAIL) -> list[dict]:
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        lines = f.readlines()[-n:]
    out = []
    for line in lines:
        try:
            out.append(json.loads(line))
        except ValueError:
            continue
    return out


def best_known_params(style: str, param_names, path: str = JOURNAL_PATH) -> dict:
    """Paramètres de récompense du meilleur essai récent du style ({} si aucun)."""
    best = None
    for e in _read_tail(path):
        env = e.get("env_search")
        if e.get("style") != style or not env or not all(p in env for p in param_names):
            continue
        if best is None or e["score"] > best["score"]:
            best = e
    return {p: best["env_search"][p] for p in param_names} if best else {}


def sample_params(center: dict, bounds: dict, sigma: float, rng: random.Random | None = None) -> dict:
    """Perturbation log-normale de chaque paramètre autour de `center`, bornée par `bounds`."""
    rng = rng or random
    out = {}
    for name, (lo, hi) in bounds.items():
        base = float(center[name])
        value = base * math.exp(rng.gauss(0.0, sigma)) if base > 0 else rng.uniform(lo, hi)
        out[name] = min(hi, max(lo, value))
    return out
