"""The validation protocol on SYNTHETIC prices: runs on a fresh clone, no market data needed.

Three sanity checks every engine in this project must pass (see docs/VALIDATION_PROTOCOL.md):
1. a strategy that knows the future must crush its random-direction twin;
2. a strategy with no information must NOT beat its twin;
3. on a rising market, "always buy" makes money but shows no skill against buy-and-hold.
"""
import numpy as np

from core.jumeau import comparer, intentions_jumeau, sens_au_hasard

COST = 0.0002          # round-trip cost, fraction of price
N = 5_000              # trades
K = 10                 # random twins


def _returns(drift: float, seed: int = 0) -> np.ndarray:
    """Per-trade forward returns of a synthetic market (fraction of price)."""
    return np.random.default_rng(seed).normal(drift, 0.01, N)


def _pnl(direction: np.ndarray, r: np.ndarray) -> np.ndarray:
    return direction * r - COST


def _twins(direction: np.ndarray, r: np.ndarray) -> np.ndarray:
    return np.stack([_pnl(direction * sens_au_hasard(N, 100 + i), r) for i in range(K)])


def test_cheater_beats_its_twin():
    r = _returns(0.0)
    cheat = np.sign(r)                                   # knows the next move
    res = comparer(_pnl(cheat, r), _twins(cheat, r))
    assert res["net"] and res["force"] > 10


def test_no_information_does_not_beat_its_twin():
    r = _returns(0.0)
    blind = sens_au_hasard(N, 7)                         # direction unrelated to the future
    res = comparer(_pnl(blind, r), _twins(blind, r))
    assert not res["net"]
    assert abs(res["force"]) < 4


def test_always_buy_on_rising_market_has_no_skill_vs_buy_and_hold():
    r = _returns(0.001)                                  # market drifts upward
    buy = np.ones(N)
    vs_twin = comparer(_pnl(buy, r), _twins(buy, r))
    assert vs_twin["gain_ia"] > 0 and vs_twin["avantage"] > 0   # looks like an edge against the coin-flip twin...
    vs_hold = comparer(_pnl(buy, r), _pnl(np.ones(N), r))
    assert vs_hold["avantage"] == 0 and not vs_hold["net"]      # ...but it is just the market drift


def test_twin_mirrors_levels_around_entry():
    it = [{"sens": 1, "entree": 100.0, "stop": 98.0, "objectifs": [104.0]}] * 200
    twins = intentions_jumeau(it, graine=3)
    flipped = [j for j in twins if j["sens"] == -1]
    assert 60 < len(flipped) < 140
    assert all(j["stop"] == 102.0 and j["objectifs"] == [96.0] for j in flipped)
