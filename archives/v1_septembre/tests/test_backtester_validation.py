"""
tests/test_backtester_validation.py
====================================
Couvre src/backtester.py::passes_validation, en particulier les deux
critères anti-dégénérescence :
  1. taux de sorties par stop-loss (`max_stop_exit_rate`) -- refuse un
     candidat qui a appris à quasiment ne plus jamais trader, quel que
     soit son score par ailleurs (cas réel : pilote M15 v3, 72.5% de
     sorties au stop contre 4.4% en production).
  2. plancher de trades PAR FENÊTRE walk-forward (`min_trades_per_window`)
     -- une fenêtre à 1 trade rend sa mesure non significative, même si le
     total agrégé est confortable.
"""
from src.backtester import passes_validation


def make_cfg(**overrides):
    validation = {
        "min_sharpe_to_go_live": 1.0,
        "max_drawdown_allowed": 0.20,
        "min_trades_to_go_live": 30,
        "max_stop_exit_rate": 0.40,
        "min_trades_per_window": 5,
    }
    validation.update(overrides)
    return {"validation": validation}


def make_metrics(**overrides):
    metrics = {
        "sharpe": 1.5,
        "max_drawdown": 0.10,
        "n_trades": 50,
        "stop_exit_rate": 0.10,
    }
    metrics.update(overrides)
    return metrics


# ------------------------------------------------------------------ #
# Comportement de base (inchangé)
# ------------------------------------------------------------------ #

def test_passes_when_all_criteria_met():
    assert passes_validation(make_metrics(), make_cfg()) is True


def test_fails_on_low_sharpe():
    assert passes_validation(make_metrics(sharpe=0.5), make_cfg()) is False


def test_fails_on_high_drawdown():
    assert passes_validation(make_metrics(max_drawdown=0.30), make_cfg()) is False


def test_fails_on_too_few_trades_total():
    assert passes_validation(make_metrics(n_trades=10), make_cfg()) is False


# ------------------------------------------------------------------ #
# Critère anti-dégénérescence : taux de sorties par stop-loss
# ------------------------------------------------------------------ #

def test_fails_on_stop_exit_rate_above_threshold_even_with_great_score():
    # Score par ailleurs excellent -- doit quand même être refusé.
    metrics = make_metrics(sharpe=5.0, max_drawdown=0.02, stop_exit_rate=0.725)
    assert passes_validation(metrics, make_cfg()) is False


def test_passes_on_stop_exit_rate_exactly_at_threshold():
    metrics = make_metrics(stop_exit_rate=0.40)
    assert passes_validation(metrics, make_cfg()) is True


def test_fails_just_above_threshold():
    metrics = make_metrics(stop_exit_rate=0.41)
    assert passes_validation(metrics, make_cfg()) is False


def test_stop_exit_rate_missing_defaults_to_zero_and_passes():
    metrics = make_metrics()
    del metrics["stop_exit_rate"]
    assert passes_validation(metrics, make_cfg()) is True


def test_max_stop_exit_rate_disabled_via_high_value():
    metrics = make_metrics(stop_exit_rate=0.99)
    assert passes_validation(metrics, make_cfg(max_stop_exit_rate=1.0)) is True


# ------------------------------------------------------------------ #
# Critère anti-dégénérescence : plancher de trades PAR FENÊTRE
# ------------------------------------------------------------------ #

def test_fails_when_one_window_below_min_trades_per_window():
    metrics = make_metrics(per_window=[
        {"n_trades": 20}, {"n_trades": 25}, {"n_trades": 1}, {"n_trades": 18},
    ])
    # total agrégé confortable (64 >= 30) mais une fenêtre à 1 trade seul.
    assert passes_validation(metrics, make_cfg()) is False


def test_passes_when_all_windows_meet_min_trades_per_window():
    metrics = make_metrics(per_window=[
        {"n_trades": 5}, {"n_trades": 25}, {"n_trades": 10}, {"n_trades": 18},
    ])
    assert passes_validation(metrics, make_cfg()) is True


def test_per_window_check_ignored_when_absent_single_window_eval():
    # evaluate_agent() (fenêtre unique) ne fournit pas "per_window".
    metrics = make_metrics()
    assert "per_window" not in metrics
    assert passes_validation(metrics, make_cfg()) is True


def test_per_window_check_disabled_via_zero_threshold():
    metrics = make_metrics(per_window=[{"n_trades": 1}, {"n_trades": 0}])
    assert passes_validation(metrics, make_cfg(min_trades_per_window=0)) is True


def test_per_window_check_ignores_empty_list():
    metrics = make_metrics(per_window=[])
    assert passes_validation(metrics, make_cfg()) is True
