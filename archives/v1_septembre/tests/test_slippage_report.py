"""Tests pour scripts/slippage_report.py -- l'analyse agrégée du journal
d'exécution (audit institutionnel, section 6 "Test du Compte Cent" /
"Analyse du Gap"). Teste `build_report` directement (pas de dépendance au
système de fichiers réel) plutôt que d'exécuter le script en sous-processus."""
from __future__ import annotations
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from slippage_report import build_report, _read_records


def test_empty_log_reports_no_data():
    report = build_report([])
    assert "Aucun enregistrement" in report


def test_aggregate_stats_computed_from_measurable_records():
    records = [
        {"style": "M15", "requested_price": 2000.0, "filled_price": 2000.5,
         "slippage": 0.5, "slippage_pct": 0.00025, "retcode": 10009},
        {"style": "M15", "requested_price": 2000.0, "filled_price": 1999.0,
         "slippage": -1.0, "slippage_pct": -0.0005, "retcode": 10009},
        {"style": "H1", "requested_price": 2000.0, "filled_price": 2004.0,
         "slippage": 4.0, "slippage_pct": 0.002, "retcode": 10009},
    ]
    report = build_report(records)
    assert "3 ordre(s) réel(s)" in report
    assert "3 avec slippage mesurable" in report
    assert "moyenne" in report
    assert "M15" in report and "H1" in report  # détail par style


def test_rejected_orders_excluded_from_slippage_stats_but_reported():
    records = [
        {"style": "M15", "requested_price": 2000.0, "filled_price": 2000.5,
         "slippage": 0.5, "slippage_pct": 0.00025, "retcode": 10009},
        {"style": "M15", "requested_price": 2000.0, "filled_price": None,
         "slippage": None, "slippage_pct": None, "retcode": 10030},  # rejeté (filling mode)
    ]
    report = build_report(records)
    assert "1 avec slippage mesurable" in report
    assert "rejeté" in report.lower()
    assert "10030" in report


def test_read_records_skips_corrupted_lines(tmp_path):
    log_path = tmp_path / "execution_log.jsonl"
    log_path.write_text(
        '{"style": "M15", "slippage_pct": 0.001, "retcode": 10009}\n'
        'not valid json at all\n'
        '{"style": "H1", "slippage_pct": -0.0005, "retcode": 10009}\n',
        encoding="utf-8",
    )
    records = _read_records(log_path)
    assert len(records) == 2  # la ligne corrompue est ignorée, pas une exception


def test_read_records_missing_file_returns_empty_list(tmp_path):
    assert _read_records(tmp_path / "does_not_exist.jsonl") == []
