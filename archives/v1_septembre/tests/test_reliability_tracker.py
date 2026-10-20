"""
test_reliability_tracker.py
============================
Vérifie que reliability_tracker.py compare bien chaque style live à SON
PROPRE meta.json walk-forward, plutôt qu'à un agrégat global commun à tous
les styles (voir demo_trader.py, retrait du blending par style) : deux
styles avec des trades très différents ne doivent jamais se mélanger dans
les métriques réalisées de l'un ou l'autre, et le rapport doit contenir une
entrée par style avec ses propres Sharpe/win_rate/n_trades.
"""
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import numpy as np

from src.episodic_memory import EpisodicMemory
from src.reliability_tracker import compute_reliability_report


def _store_trades(memory, style, pnls):
    for pnl in pnls:
        memory.store(context=np.array([1.0, 2.0, 3.0]), action=1, pnl_pct=pnl,
                     drawdown=abs(min(0.0, pnl)), generation=-1, source="live", style=style)


def test_report_has_one_entry_per_style_with_isolated_metrics(tmp_path):
    memory = EpisodicMemory(str(tmp_path / "mem.sqlite"), max_episodes=1000)

    # M15 : que des gains. H1 : que des pertes. Si la comparaison était
    # encore faite en agrégat, les deux styles se contamineraient l'un
    # l'autre dans les métriques réalisées.
    _store_trades(memory, "M15", [0.02, 0.01, 0.03])
    _store_trades(memory, "H1", [-0.02, -0.01, -0.03])

    styles_predicted = {
        "M15": {"sharpe": 1.0, "max_drawdown": 0.05},
        "H1": {"sharpe": 1.0, "max_drawdown": 0.05},
    }
    report = compute_reliability_report(memory, styles_predicted, min_trades_for_confidence=3)

    assert set(report["styles"].keys()) == {"M15", "H1"}

    m15 = report["styles"]["M15"]["realized"]
    h1 = report["styles"]["H1"]["realized"]
    assert m15["n_trades"] == 3
    assert h1["n_trades"] == 3
    assert m15["win_rate"] == 1.0
    assert h1["win_rate"] == 0.0
    assert m15["sharpe"] > 0
    assert h1["sharpe"] < 0

    # M15 a un vrai excédent de gains vs prédit -> cohérent. H1 s'effondre
    # par rapport à son propre backtest -> écart significatif détecté PAR
    # STYLE, pas noyé dans une moyenne globale.
    assert "ÉCART" in report["styles"]["H1"]["verdict"]
    assert "ÉCART" not in report["styles"]["M15"]["verdict"]


def test_style_without_promoted_champion_reports_none_predicted(tmp_path):
    memory = EpisodicMemory(str(tmp_path / "mem2.sqlite"), max_episodes=1000)
    _store_trades(memory, "D1", [0.01])

    report = compute_reliability_report(memory, {"D1": None}, min_trades_for_confidence=100)

    assert report["styles"]["D1"]["predicted"] is None
    assert "Aucun champion" in report["styles"]["D1"]["verdict"]


def test_trades_from_other_styles_never_leak_into_this_style(tmp_path):
    memory = EpisodicMemory(str(tmp_path / "mem3.sqlite"), max_episodes=1000)
    _store_trades(memory, "M15", [0.02] * 5)
    _store_trades(memory, "H1", [0.02] * 50)

    report = compute_reliability_report(
        memory, {"M15": {"sharpe": 0.0, "max_drawdown": 1.0}}, min_trades_for_confidence=100)

    # Le style H1 (50 trades) n'a même pas été demandé -- ne doit pas être
    # présent, et surtout ne doit pas gonfler le compte de M15 (5 trades).
    assert "H1" not in report["styles"]
    assert report["styles"]["M15"]["n_live_trades"] == 5
