"""
live_rollback.py
=================
Réaction automatique à une DÉGRADATION LIVE d'un champion (05/10/2026, vision
V1 §52, §72-73), à partir des trades réels du journal (src/decision_journal.py),
par style ET par génération :

  REDUCE   : t-stat du R moyen < t_reduce après >= min_trades_reduce trades
             -> budget de risque de ce style multiplié par reduce_scale ;
  SUSPEND  : t-stat < t_suspend après >= min_trades_suspend trades, ou
             drawdown cumulé <= max_dd_r_suspend R -> plus de nouvelle
             ouverture pour cette génération ;
  ROLLBACK : comme SUSPEND, mais une génération PRÉCÉDENTE de ce style,
             validée (passes_validation + lockbox) et non dégradée en live,
             existe dans models/champion_<style>/history/ -> elle reprend les
             nouvelles ouvertures.

Politique MONOTONE pour une génération donnée : jamais de retour automatique
vers plus de risque (vision V1 §56). L'état est effacé quand un NOUVEAU
champion est promu (il repart de zéro). Les positions ouvertes ne sont jamais
fermées par ce module : il agit uniquement sur les nouvelles ouvertures.
"""
from __future__ import annotations
import json
import logging
import os

from src.decision_journal import summarize_r

log = logging.getLogger("live_rollback")

STATE_PATH = os.path.join("data", "live_rollback.json")
DEFAULTS = {"enabled": False, "min_trades_reduce": 15, "t_reduce": -1.5, "reduce_scale": 0.5,
            "min_trades_suspend": 25, "t_suspend": -2.0, "max_dd_r_suspend": -10.0}
_ORDER = {None: 0, "REDUCE": 1, "ROLLBACK": 2, "SUSPEND": 3}


def load_state(path: str = STATE_PATH) -> dict:
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_state(state: dict, path: str = STATE_PATH):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)
    os.replace(tmp, path)


def assess(trades: list[dict], cfg: dict) -> tuple[str | None, dict]:
    c = {**DEFAULTS, **(cfg or {})}
    s = summarize_r(trades)
    n, t, dd = s.get("n_r", 0), s.get("t_stat"), s.get("max_dd_r", 0.0)
    if n >= c["min_trades_suspend"] and ((t is not None and t < c["t_suspend"]) or (dd or 0) <= c["max_dd_r_suspend"]):
        return "SUSPEND", s
    if n >= c["min_trades_reduce"] and t is not None and t < c["t_reduce"]:
        return "REDUCE", s
    return None, s


def find_rollback_generation(style: str, current_gen: int, journal, cfg: dict,
                             models_dir: str = "models") -> int | None:
    hist = os.path.join(models_dir, f"champion_{style}", "history")
    if not os.path.isdir(hist):
        return None
    cands = []
    for name in os.listdir(hist):
        if not name.startswith("gen_"):
            continue
        try:
            g = int(name[4:])
        except ValueError:
            continue
        if g >= int(current_gen):
            continue
        d = os.path.join(hist, name)
        try:
            with open(os.path.join(d, "meta.json"), encoding="utf-8") as f:
                meta = json.load(f)
        except Exception:
            continue
        if not (meta.get("passes_validation") and meta.get("lockbox")
                and os.path.exists(os.path.join(d, "agent.zip")) and os.path.exists(os.path.join(d, "norm_stats.json"))):
            continue
        stage, _ = assess(journal.trades(style=style, generation=g), cfg)
        if stage is None:
            cands.append(g)
    return max(cands) if cands else None


def update(journal, style: str, generation, cfg: dict, path: str = STATE_PATH, notify=None) -> dict | None:
    """Réévalue un style ; renvoie son état courant (None = aucune restriction)."""
    c = {**DEFAULTS, **(cfg or {})}
    if not c.get("enabled") or journal is None or generation is None:
        return None
    state = load_state(path)
    cur = state.get(style)
    if cur and cur.get("generation") != generation:
        log.info(f"[rollback] {style} : nouveau champion (gén. {generation}) -> état de dégradation de la "
                 f"gén. {cur.get('generation')} effacé.")
        journal.log_event("rollback_cleared", {"old": cur, "new_generation": generation}, style)
        state.pop(style)
        cur = None
    stage, s = assess(journal.trades(style=style, generation=generation), c)
    new = dict(cur) if cur else None
    if stage == "SUSPEND" and (cur is None or cur.get("stage") in ("REDUCE",)):
        rb = find_rollback_generation(style, generation, journal, c)
        new = {"generation": generation, "stage": "ROLLBACK" if rb is not None else "SUSPEND",
               "rollback_to": rb, "risk_scale": c["reduce_scale"], "stats": s}
    elif stage == "REDUCE" and cur is None:
        new = {"generation": generation, "stage": "REDUCE", "risk_scale": c["reduce_scale"], "stats": s}
    if new and new.get("stage") == "ROLLBACK":
        rb_stage, rb_stats = assess(journal.trades(style=style, generation=new["rollback_to"]), c)
        if rb_stage == "SUSPEND":
            new = {**new, "stage": "SUSPEND", "rollback_stats": rb_stats}
    if new != cur and new is not None and _ORDER[new.get("stage")] >= _ORDER[(cur or {}).get("stage")]:
        state[style] = new
        save_state(state, path)
        msg = (f"[rollback] {style} gén. {generation} : {new['stage']}"
               + (f" -> retour à la gén. {new['rollback_to']}" if new.get("stage") == "ROLLBACK" else "")
               + f" ({s.get('n_r')} trades, R moyen {s.get('avg_r', 0):+.2f}, t={s.get('t_stat')}).")
        log.warning(msg)
        journal.log_event("rollback", new, style)
        if notify:
            try:
                notify(msg)
            except Exception:
                pass
    return state.get(style)
