"""
test_lockbox_gate.py
=====================
Décision de la porte lockbox (src/lockbox_gate.py::gate_decision) : seuils absolus et
comparaison au champion éligible actuel.
"""
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.lockbox_gate import gate_decision

GATE = {"min_sharpe": 0.3, "max_drawdown": 0.40, "min_return": 0.0, "min_trades": 100,
        "beat_incumbent": True, "min_trades_ratio_vs_incumbent": 0.8}
GOOD = {"sharpe": 0.67, "max_drawdown": 0.37, "total_return": 0.45, "n_trades": 661}


def test_good_candidate_passes_without_incumbent():
    ok, why = gate_decision(GOOD, GATE, None)
    assert ok and why == ""


def test_each_absolute_threshold_rejects():
    for field, bad in (("sharpe", 0.1), ("max_drawdown", 0.55), ("total_return", -0.05), ("n_trades", 20)):
        ok, why = gate_decision({**GOOD, field: bad}, GATE, None)
        assert not ok and why


def test_must_beat_incumbent_sharpe_and_stay_active():
    incumbent = {"sharpe": 0.67, "n_trades": 661}
    assert not gate_decision({**GOOD, "sharpe": 0.60}, GATE, incumbent)[0]
    assert not gate_decision({**GOOD, "sharpe": 0.9, "n_trades": 400}, GATE, incumbent)[0]
    assert gate_decision({**GOOD, "sharpe": 0.9, "n_trades": 600}, GATE, incumbent)[0]


def test_incumbent_comparison_can_be_disabled():
    incumbent = {"sharpe": 2.0, "n_trades": 5000}
    assert gate_decision(GOOD, {**GATE, "beat_incumbent": False}, incumbent)[0]
