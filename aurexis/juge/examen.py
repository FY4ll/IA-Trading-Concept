"""Couche 4 -- L'EXAMEN, le seul juge de la v3 (même examen pour choisir le champion, ouvrir un marché, décider d'un
challenge). Trois épreuves :
  1. examen complet sur l'or : validation jamais vue à l'entraînement, en plusieurs fenêtres + scénarios de crise ;
  2. tous les autres marchés (et leurs versions inversées), même période ;
  3. activité minimale (une IA qui ne trade pas ne peut pas gagner l'examen).
Note de chaque épreuve = régularité des gains (sortino) - 2 x pire baisse ; note finale = poids x or + (1 - poids) x
moyenne des autres marchés. Et un PETIT EXAMEN rapide (marché + période tirés au hasard) pour trier les candidats.
Mêmes calculs que Run A (continuous_trainer._train_candidate_worker / _multi_market_score / _quick_exam_result /
_active_enough), prouvés identiques par tests/test_juge_equivalence.py."""
from __future__ import annotations
import zlib

import numpy as np

from aurexis.cerveau.simulateur import TradingEnv
from aurexis.juge.fenetres import compute_metrics, evaluate_agent_walkforward, run_episode


def graine_crise(nom: str) -> int:
    """Même scénario de crise à chaque cycle pour une même IA (comparaison équitable avec le champion)."""
    return zlib.crc32(nom.encode()) & 0x7FFFFFFF


def note(m: dict, regularite: str = "sortino", poids_exces: float = 0.0, borne: float | None = None) -> float:
    s = m.get(regularite, m["sharpe"]) - 2.0 * m["max_drawdown"] + poids_exces * m.get("excess_return", 0.0)
    return float(np.clip(s, -borne, borne)) if borne is not None else float(s)


def examen_or(agent, val_or, env_kwargs: dict, nom: str = "AUREXIS", fenetres: int = 4, crises: bool = True,
              evenements_macro=None, frottements: str = "pessimistic", regularite: str = "sortino",
              poids_exces: float = 0.0) -> tuple[float, dict]:
    m = evaluate_agent_walkforward(agent, val_or, env_kwargs, n_windows=fenetres, stress_test=crises,
                                   stress_seed=graine_crise(nom), timeframe="M15", garch_stress=False,
                                   macro_event_timestamps=evenements_macro, friction_profile=frottements)
    return note(m, regularite, poids_exces), m


def examen_marches(agent, marches: list, env_kwargs: dict, regularite: str = "sortino", borne: float = 5.0,
                   souvenirs: list | None = None) -> list[dict]:
    detail = []
    for nom, df in marches:
        try:
            env = run_episode(agent, TradingEnv(df, **env_kwargs))
            m = compute_metrics(env, timeframe="M15")
            detail.append({"market": nom, "score": note(m, regularite, borne=borne), "sharpe": float(m["sharpe"]),
                           "total_return": float(m["total_return"]), "max_drawdown": float(m["max_drawdown"]),
                           "n_trades": int(m.get("n_trades", 0) or 0)})
            if souvenirs is not None:
                souvenirs.extend({"entry": t["entry"], "exit": t["exit"], "position": t["position"],
                                  "pnl_pct": t["pnl_pct"], "context": t["context"], "market": nom}
                                 for t in env.trade_log)
        except Exception as e:                       # un marché en erreur = pire note, jamais un plantage
            detail.append({"market": nom, "score": -borne, "error": f"{type(e).__name__}: {e}"})
    return detail


def examen_complet(agent, val_or, marches: list, env_kwargs: dict, poids_or: float = 0.5, **kw) -> dict:
    s_or, m = examen_or(agent, val_or, env_kwargs, **{k: v for k, v in kw.items() if k != "borne"})
    detail = examen_marches(agent, marches, env_kwargs, kw.get("regularite", "sortino"), kw.get("borne", 5.0))
    if not detail:
        return {"score": s_or, "metrics": m}
    autres = float(np.mean([p["score"] for p in detail]))
    m.update(gold_score=float(s_or), markets_score=autres, markets=detail)
    return {"score": poids_or * float(s_or) + (1.0 - poids_or) * autres, "metrics": m}


def petit_examen(agent, epreuves: list, env_kwargs: dict, regularite: str = "sortino", borne: float = 5.0) -> dict:
    detail = []
    for nom, df in epreuves:
        env = run_episode(agent, TradingEnv(df, **env_kwargs))
        m = compute_metrics(env, timeframe="M15")
        detail.append({"epreuve": nom, "score": note(m, regularite, borne=borne),
                       "total_return": float(m["total_return"]), "max_drawdown": float(m["max_drawdown"]),
                       "n_trades": int(m.get("n_trades", 0) or 0)})
    return {"score": float(np.mean([d["score"] for d in detail])) if detail else -borne, "detail": detail}


def assez_actif(m: dict, min_trades_or: int, min_trades_marches: int) -> bool:
    if int(m.get("n_trades", 0) or 0) < min_trades_or:
        return False
    mk = m.get("markets")
    return not (mk and sum(int(p.get("n_trades", 0) or 0) for p in mk) < min_trades_marches)
