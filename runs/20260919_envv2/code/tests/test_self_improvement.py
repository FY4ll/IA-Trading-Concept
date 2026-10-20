"""
Auto-amélioration : journal d'expériences + recherche sur la récompense + durcissement de la porte lockbox.
"""
import sys, os, random
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src import experiment_journal as j
from src.lockbox_gate import gate_decision, _thirds_returns

BOUNDS = {"drawdown_penalty": (0.5, 6.0), "friction_penalty_coef": (0.002, 0.05)}


def test_sample_params_stays_within_bounds():
    rng = random.Random(0)
    for _ in range(200):
        p = j.sample_params({"drawdown_penalty": 2.0, "friction_penalty_coef": 0.01}, BOUNDS, 1.5, rng)
        assert all(BOUNDS[k][0] <= v <= BOUNDS[k][1] for k, v in p.items())


def test_journal_best_known_params(tmp_path):
    path = str(tmp_path / "j.jsonl")
    j.append([
        {"style": "H1", "score": 0.5, "env_search": {"drawdown_penalty": 1.0, "friction_penalty_coef": 0.01}},
        {"style": "H1", "score": 0.9, "env_search": {"drawdown_penalty": 3.0, "friction_penalty_coef": 0.02}},
        {"style": "H4", "score": 5.0, "env_search": {"drawdown_penalty": 9.0, "friction_penalty_coef": 0.04}},
        {"style": "H1", "score": 2.0, "env_search": None},
    ], path)
    assert j.best_known_params("H1", BOUNDS, path) == {"drawdown_penalty": 3.0, "friction_penalty_coef": 0.02}
    assert j.best_known_params("M30", BOUNDS, path) == {}


def test_thirds_returns():
    assert _thirds_returns([100, 110, 121, 121, 121, 133.1, 133.1]) != []
    assert _thirds_returns([100, 101]) == []


GATE = {"min_sharpe": 0.3, "max_drawdown": 0.4, "min_return": 0.0, "min_trades": 100,
        "stress_min_return": 0.0, "max_negative_thirds": 1}
GOOD = {"sharpe": 0.8, "max_drawdown": 0.2, "total_return": 0.3, "n_trades": 300,
        "stress_return": 0.05, "thirds_returns": [0.1, 0.2, -0.01]}


def test_gate_hardening_refuses_stress_loss_and_unstable_thirds():
    assert gate_decision(GOOD, GATE, None)[0]
    assert not gate_decision({**GOOD, "stress_return": -0.02}, GATE, None)[0]
    assert not gate_decision({**GOOD, "thirds_returns": [-0.1, 0.5, -0.01]}, GATE, None)[0]


def test_gate_hardening_inactive_without_config_or_measures():
    base = {k: v for k, v in GATE.items() if not k.startswith(("stress", "max_neg"))}
    assert gate_decision({**GOOD, "stress_return": -1.0, "thirds_returns": [-1, -1, -1]}, base, None)[0]
    legacy = {k: v for k, v in GOOD.items() if k not in ("stress_return", "thirds_returns")}
    assert gate_decision(legacy, GATE, None)[0]
