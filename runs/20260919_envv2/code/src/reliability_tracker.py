"""
reliability_tracker.py
========================
Répond à une question qu'aucune métrique de backtest ne peut répondre
elle-même : "est-ce que je peux faire confiance aux Sharpe qu'on voit ?"

Le backtest walk-forward (voir src/backtester.py) et les scénarios
adversariaux (voir src/stress_test.py) mesurent une performance PRÉDITE sur
de l'historique. Ce module compare cette prédiction à ce qui s'est
RÉELLEMENT passé en démo -- les trades réels sont déjà enregistrés dans la
mémoire épisodique avec `generation=-1` (voir demo_trader.py::_LiveMemoryTracker).

DÉCOMPOSITION PAR STYLE (chaque style trade indépendamment depuis le retrait
du blending, voir demo_trader.py) : comparer un agrégat de tous les styles à
un seul backtest n'a pas de sens dès que plusieurs styles tournent en
parallèle avec des walk-forward et des profils de risque différents. Chaque
style live est donc comparé à SON PROPRE meta.json walk-forward (le champ
"metrics" écrit par continuous_trainer.py pour ce style précis), et le
rapport contient une entrée par style plutôt qu'un seul verdict global.

Volontairement honnête sur ses propres limites : avec peu de trades réels,
le rapport le dit explicitement plutôt que d'afficher un chiffre qui
donnerait une fausse impression de certitude.
"""
from __future__ import annotations
import json
import logging
import os
import numpy as np

log = logging.getLogger("reliability_tracker")

# 20 trades, c'est une taille d'échantillon où le hasard décide encore
# largement du résultat (un candidat peut "passer" par pure chance sur si
# peu d'observations) -- relevé significativement par défaut. Reste
# configurable (`reliability.min_trades_for_confidence`) si vous voulez
# ajuster selon votre propre tolérance au risque de faux positif.
DEFAULT_MIN_TRADES_FOR_CONFIDENCE = 100
REPORT_PATH = os.path.join("reports", "reliability.json")


def _live_trades(memory, style: str | None) -> list[dict]:
    """Trades RÉELLEMENT vécus en démo (generation=-1) pour CE style
    uniquement, triés du plus ancien au plus récent. `style=None` conserve
    l'ancien comportement (tous les styles confondus) -- utile pour les
    trades enregistrés avant l'ajout de la colonne `style`."""
    try:
        with memory._lock:
            if style is None:
                rows = memory.conn.execute(
                    "SELECT created_at, pnl_pct, drawdown FROM episodes WHERE generation = -1 "
                    "ORDER BY created_at ASC"
                ).fetchall()
            else:
                rows = memory.conn.execute(
                    "SELECT created_at, pnl_pct, drawdown FROM episodes WHERE generation = -1 "
                    "AND style = ? ORDER BY created_at ASC",
                    (style,),
                ).fetchall()
    except Exception as e:
        log.warning(f"[reliability_tracker] Échec de lecture SQLite des trades live "
                    f"({type(e).__name__}: {e}) -> rapport vide retourné pour ce style.")
        return []
    return [{"created_at": r[0], "pnl_pct": r[1], "drawdown": r[2]} for r in rows]


def _realized_metrics(trades: list[dict]) -> dict:
    """Métriques calculées sur les trades RÉELS uniquement -- même logique
    que backtester.compute_metrics, mais sur du vécu, pas du simulé."""
    if not trades:
        return {"n_trades": 0, "total_return": 0.0, "sharpe": 0.0,
                "max_drawdown": 0.0, "win_rate": 0.0}

    pnls = np.array([t["pnl_pct"] for t in trades])
    equity = np.cumprod(1 + pnls)
    total_return = float(equity[-1] - 1)
    sharpe = float(pnls.mean() / (pnls.std() + 1e-9)) if len(pnls) > 1 else 0.0
    peak = np.maximum.accumulate(equity)
    max_drawdown = float(np.max((peak - equity) / peak)) if len(equity) else 0.0
    win_rate = float((pnls > 0).mean())
    return {
        "n_trades": len(trades), "total_return": total_return, "sharpe": sharpe,
        "max_drawdown": max_drawdown, "win_rate": win_rate,
    }


def _style_report(memory, style: str | None, predicted_metrics: dict | None,
                   min_trades_for_confidence: int) -> dict:
    """Rapport de fiabilité pour UN SEUL style (ou pour l'ancien mode agrégat
    si `style=None`) : compare ses trades live à SON PROPRE `predicted_metrics`
    (le "metrics" de son propre meta.json walk-forward)."""
    trades = _live_trades(memory, style)
    realized = _realized_metrics(trades)

    report = {
        "n_live_trades": realized["n_trades"],
        "min_trades_for_confidence": min_trades_for_confidence,
        "confident": realized["n_trades"] >= min_trades_for_confidence,
        "realized": realized,
        "predicted": predicted_metrics,
    }

    if predicted_metrics is None:
        report["verdict"] = "Aucun champion démo encore promu -- rien à comparer pour l'instant."
    elif not report["confident"]:
        report["verdict"] = (
            f"Seulement {realized['n_trades']} trade(s) réel(s) enregistré(s) -- "
            f"trop peu pour juger si le backtest est fiable (seuil : {min_trades_for_confidence}, "
            f"volontairement élevé : sur un petit échantillon, un candidat peut sembler bon par pur hasard)."
        )
    else:
        sharpe_gap = realized["sharpe"] - predicted_metrics.get("sharpe", 0.0)
        dd_gap = realized["max_drawdown"] - predicted_metrics.get("max_drawdown", 0.0)
        if sharpe_gap < -0.5 or dd_gap > 0.05:
            report["verdict"] = (
                f"ÉCART SIGNIFICATIF : le réel fait moins bien que prédit "
                f"(sharpe réel {realized['sharpe']:.2f} vs prédit {predicted_metrics.get('sharpe', 0):.2f}, "
                f"drawdown réel {realized['max_drawdown']:.1%} vs prédit "
                f"{predicted_metrics.get('max_drawdown', 0):.1%}) -- le backtest semble optimiste, "
                f"à prendre avec méfiance."
            )
        else:
            report["verdict"] = (
                f"Cohérent : le réel (sharpe {realized['sharpe']:.2f}, drawdown "
                f"{realized['max_drawdown']:.1%}) ne s'écarte pas significativement de ce que "
                f"le backtest prédisait (sharpe {predicted_metrics.get('sharpe', 0):.2f}, drawdown "
                f"{predicted_metrics.get('max_drawdown', 0):.1%})."
            )

    return report


def compute_reliability_report(memory, styles_predicted: dict[str, dict | None],
                                 min_trades_for_confidence: int = DEFAULT_MIN_TRADES_FOR_CONFIDENCE) -> dict:
    """Compare les métriques RÉELLES (trades live, generation=-1) de CHAQUE
    style à son PROPRE backtest walk-forward -- plus de comparaison en
    agrégat. `styles_predicted` associe chaque nom de style au "metrics" de
    son propre meta.json (voir continuous_trainer.py::_champion_meta), ou
    None si ce style n'a pas encore de champion promu.

    Le rapport renvoyé contient une entrée par style dans `styles`, chacune
    avec ses propres Sharpe, win_rate et n_trades (voir `_style_report`).
    """
    styles = {
        style: _style_report(memory, style, predicted_metrics, min_trades_for_confidence)
        for style, predicted_metrics in styles_predicted.items()
    }

    return {
        "min_trades_for_confidence": min_trades_for_confidence,
        "styles": styles,
    }


def save_report(report: dict):
    os.makedirs(os.path.dirname(REPORT_PATH), exist_ok=True)
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
