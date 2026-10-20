"""LOT 2, phase 4, point 9 : colonne `symbol` dans EpisodicMemory -- le live
n'interroge que l'or (voir demo_trader.py::_StyleRuntime.maybe_reload/decide,
symbols=[GOLD_SYMBOL]), jamais un épisode d'un autre symbole. Fichier DÉDIÉ
(pas tests/test_autonomous.py), comme demandé."""
from __future__ import annotations
import numpy as np
import pytest

from src.episodic_memory import EpisodicMemory


def _mem(tmp_path):
    return EpisodicMemory(db_path=str(tmp_path / "mem.sqlite"), max_episodes=1000)


def test_symbol_stored_and_filterable(tmp_path):
    mem = _mem(tmp_path)
    mem.store(context=np.zeros(5, dtype=np.float32), action=1, pnl_pct=0.01, drawdown=0.0, symbol="XAUUSD")
    mem.store(context=np.ones(5, dtype=np.float32), action=-1, pnl_pct=-0.01, drawdown=0.01, symbol="EURUSD")

    gold_only = mem.snapshot(dim=5, symbols=["XAUUSD"])
    contexts, pnls, drawdowns = gold_only
    assert len(pnls) == 1
    assert pnls[0] == pytest.approx(0.01, abs=1e-6)
    mem.close()


def test_symbol_none_legacy_rows_included_when_filtering_gold(tmp_path):
    """Compatibilité : les épisodes d'avant ce mécanisme (symbol=NULL,
    implicitement de l'or) ne doivent JAMAIS être exclus silencieusement
    d'un filtre symbols=["XAUUSD"]."""
    mem = _mem(tmp_path)
    mem.store(context=np.zeros(5, dtype=np.float32), action=1, pnl_pct=0.02, drawdown=0.0)  # symbol non fourni
    mem.store(context=np.ones(5, dtype=np.float32), action=-1, pnl_pct=-0.05, drawdown=0.02, symbol="EURUSD")

    gold_only = mem.snapshot(dim=5, symbols=["XAUUSD"])
    contexts, pnls, drawdowns = gold_only
    assert len(pnls) == 1, "la ligne symbol=NULL doit être incluse (implicitement de l'or)"
    assert pnls[0] == pytest.approx(0.02, abs=1e-6)
    mem.close()


def test_no_symbol_filter_returns_everything_unchanged(tmp_path):
    """Comportement d'ORIGINE préservé : sans `symbols`, aucun filtrage
    (utilisé par l'entraînement, qui doit voir tous les épisodes)."""
    mem = _mem(tmp_path)
    mem.store(context=np.zeros(5, dtype=np.float32), action=1, pnl_pct=0.02, drawdown=0.0, symbol="XAUUSD")
    mem.store(context=np.ones(5, dtype=np.float32), action=-1, pnl_pct=-0.05, drawdown=0.02, symbol="EURUSD")
    all_episodes = mem.snapshot(dim=5)
    contexts, pnls, drawdowns = all_episodes
    assert len(pnls) == 2
    mem.close()


def test_symbol_and_source_filters_combine(tmp_path):
    mem = _mem(tmp_path)
    mem.store(context=np.zeros(5, dtype=np.float32), action=1, pnl_pct=0.03, drawdown=0.0,
              symbol="XAUUSD", source="backtest")
    mem.store(context=np.zeros(5, dtype=np.float32), action=1, pnl_pct=0.04, drawdown=0.0,
              symbol="XAUUSD", source="live")
    mem.store(context=np.zeros(5, dtype=np.float32), action=1, pnl_pct=0.05, drawdown=0.0,
              symbol="EURUSD", source="backtest")

    result = mem.snapshot(dim=5, sources=["backtest"], symbols=["XAUUSD"])
    _, pnls, _ = result
    assert len(pnls) == 1
    assert pnls[0] == pytest.approx(0.03, abs=1e-6)
    mem.close()


def test_migration_adds_symbol_column_to_existing_db(tmp_path):
    """Une base créée AVANT ce mécanisme (sans colonne symbol) doit être
    migrée automatiquement (ALTER TABLE), jamais une erreur au démarrage."""
    import sqlite3
    db_path = str(tmp_path / "old.sqlite")
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE episodes (
            id INTEGER PRIMARY KEY AUTOINCREMENT, created_at REAL, generation INTEGER,
            context TEXT, action INTEGER, pnl_pct REAL, drawdown REAL,
            source TEXT DEFAULT 'backtest', style TEXT
        )
    """)
    conn.commit()
    conn.close()

    mem = EpisodicMemory(db_path=db_path)  # ne doit pas lever d'exception
    mem.store(context=np.zeros(3, dtype=np.float32), action=1, pnl_pct=0.01, drawdown=0.0, symbol="XAUUSD")
    result = mem.snapshot(dim=3, symbols=["XAUUSD"])
    assert result is not None
    mem.close()
