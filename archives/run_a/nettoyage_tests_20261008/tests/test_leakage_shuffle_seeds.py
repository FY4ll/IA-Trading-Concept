"""LOT 2, phase 6, point 2 : scripts/leakage_shuffle_test.py --seeds N
(agrégation moyenne/écart-type/min/max/graines>0 sur plusieurs graines de
mélange indépendantes) -- src/backtester.py::compute_walk_forward_efficiency
enrichi (trades IS/OOS, raison, drapeau suspect). Fichier DÉDIÉ (pas
tests/test_autonomous.py ni tests/test_leakage_shuffle.py, qui teste la
fonction de mélange elle-même), comme demandé."""
from __future__ import annotations
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import pytest


def _import_stats_fn():
    # Import différé + ciblé (pas `import leakage_shuffle_test` en entier,
    # qui exécuterait tout le script au niveau module -- argparse compris).
    import ast
    import types
    source = (Path(__file__).resolve().parent.parent / "scripts" / "leakage_shuffle_test.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    func_node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "_shuffle_score_stats")
    module = types.ModuleType("_extracted")
    exec(compile(ast.Module(body=[func_node], type_ignores=[]), "<extracted>", "exec"), module.__dict__)
    return module._shuffle_score_stats


_shuffle_score_stats = _import_stats_fn()


def test_stats_basic_mean_min_max():
    result = _shuffle_score_stats([1.0, 2.0, 3.0])
    assert result["mean"] == pytest.approx(2.0)
    assert result["min"] == 1.0
    assert result["max"] == 3.0
    assert result["n_seeds"] == 3


def test_stats_std_zero_for_single_seed():
    result = _shuffle_score_stats([1.5])
    assert result["std"] == 0.0
    assert result["n_seeds"] == 1


def test_stats_n_positive_counts_correctly():
    result = _shuffle_score_stats([-1.0, 0.0, 0.5, 2.0, -0.3])
    assert result["n_positive"] == 2


def test_stats_std_nonzero_for_varying_values():
    result = _shuffle_score_stats([1.0, 5.0, 9.0])
    assert result["std"] > 0.0
