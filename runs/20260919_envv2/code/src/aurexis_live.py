"""
aurexis_live.py
===============
AUREXIS EN DIRECT SUR TOUS LES MARCHÉS (09/10/2026, accord de l'utilisateur : « mets les 3 points en place »).

Étape 1 -- « À BLANC » : toutes les 15 minutes, AUREXIS reçoit les VRAIES cotations du courtier (MT5) sur chacun de ses
marchés, décide exactement comme à l'entraînement (même vision, mêmes statistiques, même mémoire), et un COMPTE FICTIF
de 100 000 $ exécute ses décisions : stops et objectifs vérifiés bougie par bougie (stop d'abord si les deux sont
touchés : hypothèse prudente), frais propres à chaque marché, taille au risque choisie par l'IA, gestion du stop
(break-even / suiveur), et les MÊMES MURS que le compte réel (-4,5 % sur la journée, -9 % au total : tout est fermé).
Aucun ordre n'est envoyé. Simplification assumée : un ordre limite choisi par l'IA est exécuté comme un ordre au marché.

Étape 3 -- « DÉMO » (mode `demo`, activé seulement par la règle automatique de scripts/regle_demo_aurexis.py) : les
mêmes décisions deviennent de vrais ordres sur le compte démo, via src/mt5_connector.MT5Connector (un par symbole, même
dimensionnement au risque et mêmes garde-fous que pour AUREX). L'or reste à AUREX (jamais deux IA sur le même symbole).

État : data/aurexis_live/etat.json ; journal : data/aurexis_live/journal.csv.
"""
from __future__ import annotations

import csv
import json
import logging
import os
import time
from dataclasses import dataclass

import numpy as np
import pandas as pd

log = logging.getLogger("aurexis_live")

STYLE = "AUREXIS"
DIR = os.path.join("data", "aurexis_live")
START_EQUITY = 100_000.0
DAILY_WALL, TOTAL_WALL = 0.045, 0.09
RISK_BUDGET = 0.04          # risque cumulé maximum des positions ouvertes (profil FTMO ftmo_ai.yaml, comme le compte réel)
# FREIN DE BAISSE (10/10/2026, accord de l'utilisateur) : protection du compte comme les murs FTMO, pas une règle de
# trading -- compte à plus de BRAKE_DD sous son plus haut -> risque de chaque NOUVEAU trade et budget x BRAKE_FACTOR,
# jusqu'à ce qu'il remonte au-dessus de ce seuil.
BRAKE_DD, BRAKE_FACTOR = 0.05, 0.5


def brake_factor(equity: float, peak: float, dd: float = BRAKE_DD, factor: float = BRAKE_FACTOR) -> float:
    return factor if peak > 0 and equity < peak * (1.0 - dd) else 1.0


def replay_account(trades: list, start: float = START_EQUITY, budget: float = RISK_BUDGET, brake: bool = True,
                   daily_wall: float = DAILY_WALL, total_wall: float = TOTAL_WALL) -> dict:
    """VERDICT FIDÈLE (10/10/2026) : les trades de TOUS les marchés rejoués sur UN compte, dans l'ordre du temps, avec
    les règles du vrai compte -- budget de risque cumulé (refus au-delà), frein de baisse, mur du jour (plus d'ouverture
    jusqu'au lendemain) et mur total (plus rien). `trades` : dicts {marche, ouvert, ferme (horodatages), risque,
    resultat (part du compte au risque choisi, frais déduits)}. Résultat sur les trades CLÔTURÉS (pas de prix entre
    l'ouverture et la clôture : la baisse réelle en cours de trade peut être un peu plus forte)."""
    events = []
    for i, t in enumerate(trades):
        o, c = pd.Timestamp(t["ouvert"]), pd.Timestamp(t["ferme"])
        events.append((o, 1, i))
        events.append((max(c, o + pd.Timedelta(1)), 0, i))   # à heure égale, les clôtures passent d'abord
    events.sort()
    eq, peak, day, day_start, halted = start, start, None, start, None
    open_ = {}                                               # i -> (risque engagé, facteur)
    taken = refused = day_walls = 0
    curve = {}
    for ts, kind, i in events:
        d = ts.normalize()
        if d != day:
            day, day_start = d, eq
            if halted == "jour":
                halted = None
        if kind == 0:
            if i in open_:
                _, f = open_.pop(i)
                eq *= 1.0 + float(trades[i]["resultat"]) * f
                peak = max(peak, eq)
                curve[d] = eq
                if eq <= start * (1 - total_wall):
                    halted = "total"
                elif eq / day_start - 1 <= -daily_wall and halted not in ("total", "jour"):
                    halted = "jour"
                    day_walls += 1
            continue
        if halted:
            refused += 1
            continue
        f = brake_factor(eq, peak) if brake else 1.0
        r = float(trades[i]["risque"]) * f
        if sum(x[0] for x in open_.values()) + r > budget * f + 1e-12:
            refused += 1
            continue
        open_[i] = (r, f)
        taken += 1
    s = pd.Series(curve).sort_index()
    if s.empty:
        return {"compte": 0.0, "baisse_max": 0.0, "trades_pris": 0, "trades_refuses": refused, "arret": halted,
                "murs_jour": day_walls, "jours": {}}
    full = pd.concat([pd.Series({s.index[0] - pd.Timedelta(days=1): start}), s])
    dd = float((1 - full / full.cummax()).max())
    daily = full.pct_change().dropna()
    return {"compte": float(s.iloc[-1] / start - 1), "baisse_max": dd, "trades_pris": taken, "trades_refuses": refused,
            "arret": halted, "murs_jour": day_walls, "jours": {f"{k:%Y-%m-%d}": round(float(v), 6) for k, v in daily.items()}}


# ------------------------------------------------------------------ compte fictif
@dataclass
class Position:
    direction: int            # +1 achat, -1 vente
    entry: float
    stop: float
    tp: float | None
    size: float               # multiplicateur de taille (risque / distance du stop)
    risk: float               # part du compte risquée jusqu'au stop
    opened: str               # date de la bougie d'entrée
    initial_risk: float       # distance prix entrée-stop à l'ouverture
    bars: int = 0


class PaperBook:
    """Compte fictif multi-marchés. Équité en $, rendements de chaque trade en part du compte."""

    def __init__(self, state: dict | None = None):
        s = state or {}
        self.equity = float(s.get("equity", START_EQUITY))
        self.start_equity = float(s.get("start_equity", START_EQUITY))
        self.peak_equity = float(s.get("peak_equity", max(self.equity, self.start_equity)))
        self.day = s.get("day")
        self.day_start_equity = float(s.get("day_start_equity", self.equity))
        self.halted = s.get("halted")                       # None | "jour" | "total"
        self.positions = {k: Position(**v) for k, v in (s.get("positions") or {}).items()}
        self.stops_today = dict(s.get("stops_today") or {})
        self.last_bar = dict(s.get("last_bar") or {})       # dernière bougie traitée par marché
        self.trades = []                                    # trades clôturés pendant ce passage

    def to_state(self) -> dict:
        return {"equity": self.equity, "start_equity": self.start_equity, "peak_equity": self.peak_equity, "day": self.day,
                "day_start_equity": self.day_start_equity, "halted": self.halted,
                "positions": {k: vars(p) for k, p in self.positions.items()},
                "stops_today": self.stops_today, "last_bar": self.last_bar}

    # -- journée et murs
    def new_day(self, day: str) -> None:
        if day != self.day:
            self.day, self.day_start_equity, self.stops_today = day, self.equity, {}
            if self.halted == "jour":
                self.halted = None

    def day_pnl(self) -> float:
        return self.equity / self.day_start_equity - 1.0 if self.day_start_equity else 0.0

    def check_walls(self) -> str | None:
        if self.halted == "total" or self.equity <= self.start_equity * (1 - TOTAL_WALL):
            return "total"
        if self.day_pnl() <= -DAILY_WALL:
            return "jour"
        return None

    # -- exécution
    def close(self, market: str, price: float, cost: float, reason: str, when: str) -> float:
        p = self.positions.pop(market)
        pnl = (price - p.entry) / p.entry * p.direction * p.size - cost * p.size
        self.equity *= (1.0 + pnl)
        self.peak_equity = max(self.peak_equity, self.equity)
        self.trades.append({"marche": market, "sens": "achat" if p.direction > 0 else "vente", "entree": p.entry,
                            "sortie": price, "risque": p.risk, "resultat_compte": pnl, "raison": reason,
                            "ouvert": p.opened, "ferme": when})
        if reason == "stop":
            self.stops_today[market] = self.stops_today.get(market, 0) + 1
        return pnl

    def open(self, market: str, direction: int, price: float, stop_pct: float, tp_mult: float | None, risk: float,
             when: str, max_leverage: float = 10.0) -> Position:
        size = min(risk / stop_pct, max_leverage)
        stop = price * (1 - stop_pct) if direction > 0 else price * (1 + stop_pct)
        tp = None if not tp_mult else (price * (1 + stop_pct * tp_mult) if direction > 0 else price * (1 - stop_pct * tp_mult))
        p = Position(direction, price, stop, tp, size, risk, when, abs(price - stop))
        self.positions[market] = p
        return p

    def follow_bars(self, market: str, bars: pd.DataFrame, cost: float) -> None:
        """Stops et objectifs vérifiés sur chaque bougie CLÔTURÉE depuis la dernière vue (stop d'abord)."""
        p = self.positions.get(market)
        if p is None:
            return
        for _, b in bars.iterrows():
            p.bars += 1
            hit_stop = (b["low"] <= p.stop) if p.direction > 0 else (b["high"] >= p.stop)
            if hit_stop:
                self.close(market, p.stop, cost, "stop", str(b["time"])); return
            if p.tp is not None:
                hit_tp = (b["high"] >= p.tp) if p.direction > 0 else (b["low"] <= p.tp)
                if hit_tp:
                    self.close(market, p.tp, cost, "objectif", str(b["time"])); return

    def manage(self, market: str, choice: int, price: float, be_trigger_r: float = 0.5, trail_r: float = 1.0) -> None:
        """Gestion choisie par l'IA (même règle que l'entraînement) : 1 = break-even si gain >= 0,5 R, 2 = suiveur à
        1 R du prix ; le stop ne peut que se resserrer."""
        p = self.positions.get(market)
        if p is None or not choice:
            return
        d, r = float(p.direction), p.initial_risk
        new = None
        if choice == 1 and (price - p.entry) * d >= be_trigger_r * r:
            new = p.entry + d * 0.05 * r
        elif choice == 2:
            new = price - d * trail_r * r
        if new is not None and (new - p.stop) * d > 0 and (price - new) * d > 0:
            p.stop = new

    def open_risk(self) -> float:
        """Risque cumulé des positions ouvertes (part du compte perdue si tous les stops étaient touchés)."""
        return float(sum(p.risk for p in self.positions.values()))

    def brake(self) -> float:
        """Facteur du frein de baisse (1 normalement, 0,5 si le compte est à plus de 5 % sous son plus haut)."""
        return brake_factor(self.equity, self.peak_equity)

    def can_open(self, risk: float, budget: float = RISK_BUDGET) -> bool:
        """Même règle que le compte réel (exposition cumulée, mt5_connector) : refus au-delà du budget (réduit par le
        frein de baisse). `risk` = risque DÉJÀ réduit par le frein."""
        return self.open_risk() + risk <= budget * self.brake() + 1e-12

    def unrealized(self, market: str, price: float) -> float:
        p = self.positions.get(market)
        return 0.0 if p is None else (price - p.entry) / p.entry * p.direction * p.size


# ------------------------------------------------------------------ décision
def decode(env, action) -> dict:
    """Décode l'action d'AUREXIS avec l'environnement lui-même (mêmes positions d'action, mêmes stops ATR)."""
    a = np.asarray(action).reshape(-1)
    price = float(env._close[env.current_step])
    buckets = env._compute_atr_stop_loss_buckets(price) if env._atr_stop_loss_active else env.stop_loss_buckets
    out = {"direction": {0: -1, 1: 0, 2: 1}[int(a[0])], "stop_pct": float(buckets[int(a[1])]),
           "tp_mult": float(env.take_profit_rr_buckets[int(a[2])]) if env.learn_take_profit else None,
           "manage": int(a[env._idx_manage]) if env._idx_manage is not None else 0,
           "risk": float(env.size_risk_buckets[int(a[env._idx_size])]) if env._idx_size is not None
           else float(env.risk_sizing_pct or 0.0025)}
    return out


# ------------------------------------------------------------------ démo (vrais ordres)
def demo_execute(connector, target: int, d: dict, generation=None) -> str:
    """Mode DÉMO : envoie la décision au courtier pour CE symbole (connecteur dédié, src/mt5_connector.MT5Connector) --
    même chemin que les ordres d'AUREX : taille au risque choisi par l'IA (risk_pct_override), stop et objectif posés
    chez le courtier, refus si l'exposition cumulée dépasse le profil FTMO, jamais d'ordre sur un compte réel non
    autorisé. `target` 0 = fermer la position d'AUREXIS sur ce symbole."""
    if target == 0:
        connector.send_order(0.0, style=STYLE, generation=generation)
        return "fermé"
    kw = {"take_profit_rr": d["tp_mult"]} if d.get("tp_mult") else {}
    connector.send_order(float(target), stop_pct=d["stop_pct"], style=STYLE, generation=generation,
                         risk_pct_override=d["risk"], **kw)
    return "ordre envoyé"


def demo_breaker(connectors: dict) -> int:
    """Coupe-circuit du compte DÉCLENCHÉ (src/account_guard) : AUREXIS ferme TOUT, sur chacun de ses symboles (celui
    d'AUREX ne ferme que l'or). Retourne le nombre de positions fermées."""
    n = 0
    for conn in connectors.values():
        try:
            n += len(conn.close_all_positions(reason="coupe_circuit").get("closed", []))
        except Exception as e:
            log.error(f"coupe-circuit AUREXIS : fermeture impossible sur {getattr(conn, 'symbol', '?')} ({e})")
    return n


def append_journal(rows: list) -> None:
    if not rows:
        return
    os.makedirs(DIR, exist_ok=True)
    path = os.path.join(DIR, "journal.csv")
    new = not os.path.exists(path)
    keys = ["heure", "marche", "evenement", "sens", "prix", "stop", "objectif", "risque", "resultat_compte", "equite"]
    with open(path, "a", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore")
        if new:
            w.writeheader()
        w.writerows(rows)


def load_state() -> PaperBook:
    try:
        with open(os.path.join(DIR, "etat.json"), encoding="utf-8") as f:
            return PaperBook(json.load(f))
    except (OSError, ValueError):
        return PaperBook()


def save_state(book: PaperBook) -> None:
    os.makedirs(DIR, exist_ok=True)
    tmp = os.path.join(DIR, "etat.json.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(book.to_state(), f, indent=1, default=str)
    os.replace(tmp, os.path.join(DIR, "etat.json"))
