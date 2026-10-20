"""Mémoire privée par style (07/10/2026) : AUREXIS a sa propre mémoire, séparée de celle d'AUREX."""
from __future__ import annotations
import numpy as np

from src.episodic_memory import EpisodicMemory


def _mem(tmp_path, max_episodes=1000):
    return EpisodicMemory(db_path=str(tmp_path / "mem.sqlite"), max_episodes=max_episodes,
                          private_styles=["AUREXIS"])


def _rec(pnl, style=None, symbol=None, source="backtest"):
    return {"context": np.full(4, pnl, dtype=np.float32), "action": 1, "pnl_pct": pnl, "drawdown": 0.0,
            "source": source, "style": style, "symbol": symbol}


def test_private_style_reads_only_its_own_trades_on_every_market(tmp_path):
    mem = _mem(tmp_path)
    mem.store_many([_rec(0.01), _rec(0.02, style="AUREX", source="live"),
                    _rec(0.03, style="AUREXIS", symbol="EURUSD miroir"), _rec(0.04, style="AUREXIS")])
    own = mem.snapshot(dim=4, symbols=["XAUUSD"], style="AUREXIS")
    assert np.allclose(sorted(own[1]), [0.03, 0.04]), "ses trades, tous marchés confondus"
    shared = mem.snapshot(dim=4, symbols=["XAUUSD"], style="AUREX")
    assert np.allclose(sorted(shared[1]), [0.01, 0.02]), "AUREX ne voit jamais les souvenirs d'AUREXIS"
    assert np.allclose(sorted(mem.snapshot(dim=4)[1]), [0.01, 0.02]), "sans style : mémoire commune"
    mem.close()


def test_private_memory_starts_empty(tmp_path):
    mem = _mem(tmp_path)
    mem.store_many([_rec(0.01), _rec(0.02)])
    assert mem.snapshot(dim=4, sources=["backtest"], style="AUREXIS") is None
    mem.close()


def test_private_trades_never_erase_the_shared_memory(tmp_path):
    mem = _mem(tmp_path, max_episodes=5)
    mem.store_many([_rec(0.001 * i) for i in range(5)])
    mem.store_many([_rec(0.1 + 0.001 * i, style="AUREXIS") for i in range(8)])
    assert len(mem.snapshot(dim=4, style="AUREX")[1]) == 5, "mémoire commune intacte"
    own = mem.snapshot(dim=4, style="AUREXIS")[1]
    assert len(own) == 5 and min(own) > 0.1025, "mémoire privée limitée à part, les plus anciens effacés"
    mem.close()


def test_without_private_styles_behaviour_is_unchanged(tmp_path):
    mem = EpisodicMemory(db_path=str(tmp_path / "m.sqlite"), max_episodes=3)
    mem.store_many([_rec(0.01 * i, style="AUREXIS" if i % 2 else None) for i in range(6)])
    snap = mem.snapshot(dim=4, style="AUREXIS")
    assert len(snap[1]) == 3, "limite globale et lecture commune comme avant"
    mem.close()


def test_trainer_records_private_style_trades_with_other_markets(tmp_path):
    from src.continuous_trainer import ContinuousEvolutionTrainer

    class Fake:
        memory = _mem(tmp_path)
    ctx = [0.0] * 4
    gold = [{"position": 1, "pnl_pct": 0.01, "context": ctx}]
    extra = [{"position": -1, "pnl_pct": 0.02, "context": ctx, "market": "XAUUSD miroir"}]
    ContinuousEvolutionTrainer._record_trades_from_result(
        Fake, {"style": "AUREXIS", "trades": gold, "extra_trades": extra, "max_drawdown": 0.1, "generation": 7})
    ContinuousEvolutionTrainer._record_trades_from_result(
        Fake, {"style": "AUREX", "trades": gold, "extra_trades": extra, "max_drawdown": 0.1, "generation": 7})
    rows = Fake.memory.conn.execute("SELECT style, symbol, action FROM episodes ORDER BY id").fetchall()
    assert rows == [("AUREXIS", None, 1), ("AUREXIS", "XAUUSD miroir", -1), (None, None, 1)]
    Fake.memory.close()
