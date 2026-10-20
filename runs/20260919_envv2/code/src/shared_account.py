"""
shared_account.py
=================
COMPTE PARTAGÉ À L'ENTRAÎNEMENT (11/10/2026, demande de l'utilisateur).

Constat : à l'entraînement, AUREXIS jouait un marché à la fois ; les « autres positions » du compte (vision du compte)
étaient simulées au hasard. Elle ne vivait jamais l'effet de SES PROPRES positions ouvertes en même temps sur plusieurs
marchés -- et à l'examen (compte fidèle) comme en réel, c'est elle qui remplissait le budget de risque (jusqu'à 3 800
trades refusés sur une période).

Ici, les parties jouées en parallèle (`n_envs`, src/agent.py) partagent UN compte : chaque partie joue un marché
différent, aux mêmes dates (départs alignés sur l'horloge des autres) ; le risque ouvert par l'une prend du budget aux
autres (refus au-delà de 4 %), et la baisse du compte est celle du compte entier (frein sous -5 %). Comme un challenge
FTMO, le compte repart de zéro quand il touche -9 % ou atteint +10 %. Le cerveau ne change pas (mêmes entrées que la
vision du compte) ; seul l'entraînement change. Les examens et le direct n'utilisent pas ce module.
"""
from __future__ import annotations

import numpy as np


class SharedAccount:
    def __init__(self, n: int, budget: float = 0.04, total_wall: float = 0.09, target: float = 0.10):
        self.n = int(n)
        self.budget = float(budget)
        self.total_wall, self.target = float(total_wall), float(target)
        self.risk = [0.0] * self.n           # risque ouvert de chaque partie (part du compte)
        self.ret = [0.0] * self.n            # rendement de chaque partie depuis qu'elle a rejoint le compte
        self.base = [1.0] * self.n           # équité de la partie quand elle a rejoint le compte
        self.times = [None] * self.n         # heure (int64 ns) de la bougie courante de chaque partie
        self.markets = [None] * self.n       # marché (segment) joué par chaque partie
        self.banked = 0.0                    # gains/pertes des parties terminées depuis le dernier redémarrage
        self.peak = 1.0
        self.restarts = {"mur": 0, "objectif": 0}

    def equity(self) -> float:
        return 1.0 + self.banked + float(sum(self.ret))

    def join(self, k: int, equity: float, market=None, time=None) -> None:
        """Une partie (re)commence : son résultat précédent reste acquis au compte, elle repart de `equity`."""
        self.banked += self.ret[k]
        self.ret[k], self.base[k], self.risk[k] = 0.0, float(equity), 0.0
        self.markets[k], self.times[k] = market, time

    def update(self, k: int, equity: float, risk: float, time=None) -> None:
        self.ret[k] = float(equity) / self.base[k] - 1.0 if self.base[k] else 0.0
        self.risk[k] = float(risk)
        if time is not None:
            self.times[k] = time
        e = self.equity()
        self.peak = max(self.peak, e)
        if e <= 1.0 - self.total_wall or e >= 1.0 + self.target:
            self.restarts["mur" if e < 1.0 else "objectif"] += 1
            self._restart()

    def _restart(self) -> None:
        """Nouveau challenge : compte remis à 100 %, chaque partie continue depuis son équité actuelle."""
        for j in range(self.n):
            self.base[j] *= 1.0 + self.ret[j]
            self.ret[j] = 0.0
        self.banked, self.peak = 0.0, 1.0

    def view(self, k: int) -> tuple:
        """(baisse du compte depuis son plus haut, part du budget prise par les AUTRES parties)."""
        e = self.equity()
        dd = max(0.0, 1.0 - e / self.peak) if self.peak else 0.0
        other = (float(sum(self.risk)) - self.risk[k]) / self.budget if self.budget else 0.0
        return dd, max(0.0, other)

    def clock(self, k: int):
        """Horloge commune : médiane des heures des AUTRES parties (None si aucune ne joue encore)."""
        t = [x for j, x in enumerate(self.times) if j != k and x is not None]
        return int(np.median(t)) if t else None

    def used_markets(self, k: int) -> set:
        return {m for j, m in enumerate(self.markets) if j != k and m is not None}
