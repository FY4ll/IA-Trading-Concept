"""src/risk_engine.py (LOT 2, phase 2) : fonctions de risque pures,
extraites de MT5Connector -- ce fichier verrouille les formules EXACTES
avant que MT5Connector et TradingEnv ne délèguent tous deux à ce module.
Fichier DÉDIÉ (pas tests/test_autonomous.py), comme demandé."""
from __future__ import annotations
import pytest

from src.risk_engine import (
    SymbolSpec, atr_stop_distance_pct, cap_stop_pct, lots_from_risk,
    notional_lots, round_volume, tighten_stop_or_cancel,
)


def test_atr_stop_distance_pct_basic_formula():
    # multiple=2, atr=5$, price=2000$ -> 2*5/2000 = 0.005
    assert atr_stop_distance_pct(5.0, 2.0, 2000.0, 0.002, 0.15) == pytest.approx(0.005)


def test_atr_stop_distance_pct_floors_and_ceils():
    assert atr_stop_distance_pct(0.0001, 0.5, 2000.0, 0.002, 0.15) == pytest.approx(0.002)
    assert atr_stop_distance_pct(10000.0, 4.0, 2000.0, 0.002, 0.15) == pytest.approx(0.15)


def test_atr_stop_distance_pct_none_atr_returns_floor():
    assert atr_stop_distance_pct(None, 2.0, 2000.0, 0.002, 0.15) == 0.002


def test_atr_stop_distance_pct_zero_price_returns_floor():
    assert atr_stop_distance_pct(5.0, 2.0, 0.0, 0.002, 0.15) == 0.002


def test_cap_stop_pct_caps_when_above():
    assert cap_stop_pct(0.05, 0.02) == 0.02


def test_cap_stop_pct_unchanged_when_below_or_none_cap():
    assert cap_stop_pct(0.01, 0.02) == 0.01
    assert cap_stop_pct(0.01, None) == 0.01
    assert cap_stop_pct(None, 0.02) is None


def test_lots_from_risk_matches_original_formula():
    # equity=10000, risk=0.02 -> 200$ risqués ; price=2000, stop_pct=0.01 ->
    # stop_distance_price=20$ ; contract_size=100 -> 200/(20*100) = 0.1 lot
    assert lots_from_risk(10000.0, 0.02, 2000.0, 0.01, 100.0) == pytest.approx(0.1)


@pytest.mark.parametrize("equity,risk_pct,price,stop_pct,contract_size", [
    (0.0, 0.02, 2000.0, 0.01, 100.0), (10000.0, 0.02, 0.0, 0.01, 100.0),
    (10000.0, 0.02, 2000.0, 0.0, 100.0), (10000.0, 0.02, 2000.0, None, 100.0),
    (10000.0, 0.02, 2000.0, 0.01, 0.0), (-500.0, 0.02, 2000.0, 0.01, 100.0),
])
def test_lots_from_risk_returns_zero_never_raises_on_invalid_input(equity, risk_pct, price, stop_pct, contract_size):
    assert lots_from_risk(equity, risk_pct, price, stop_pct, contract_size) == 0.0


def test_notional_lots_matches_original_formula():
    assert notional_lots(10000.0, 2000.0, 100.0) == pytest.approx(0.05)


@pytest.mark.parametrize("equity,price,contract_size", [
    (0.0, 2000.0, 100.0), (10000.0, 0.0, 100.0), (10000.0, 2000.0, 0.0),
])
def test_notional_lots_returns_zero_never_raises_on_invalid_input(equity, price, contract_size):
    assert notional_lots(equity, price, contract_size) == 0.0


def test_round_volume_below_min_returns_zero_by_default():
    spec = SymbolSpec(volume_min=0.01, volume_step=0.01, volume_max=100.0)
    assert round_volume(0.001, spec) == 0.0


def test_round_volume_below_min_floors_when_floor_if_positive():
    spec = SymbolSpec(volume_min=0.01, volume_step=0.01, volume_max=100.0)
    assert round_volume(0.001, spec, floor_if_positive=True) == 0.01


def test_round_volume_zero_never_floors_even_with_flag():
    spec = SymbolSpec(volume_min=0.01, volume_step=0.01, volume_max=100.0)
    assert round_volume(0.0, spec, floor_if_positive=True) == 0.0


def test_round_volume_steps_and_clamps_to_max():
    spec = SymbolSpec(volume_min=0.01, volume_step=0.01, volume_max=1.0)
    assert round_volume(0.567, spec) == pytest.approx(0.57)
    assert round_volume(5.0, spec) == 1.0


def test_round_volume_default_spec_matches_connector_defaults():
    # spec par défaut = mêmes valeurs que MT5Connector._round_volume quand
    # symbol_info est indisponible (step=0.01, vol_min=step, vol_max=raw).
    spec = SymbolSpec()
    assert round_volume(0.234, spec) == pytest.approx(0.23)


def test_tighten_stop_or_cancel_no_tightening_when_not_floored():
    spec = SymbolSpec(contract_size=100.0)
    stop, cancel = tighten_stop_or_cancel(0.05, 0.05, 0.01, 10000.0, 2000.0, 0.02, spec)
    assert stop == 0.01 and cancel is False


def test_tighten_stop_or_cancel_tightens_when_floored_above_ideal():
    # raw=0.001 (idéal), floored=0.01 (minimum broker) -> le risque $ grandit
    # avec le lot, donc le stop doit se resserrer proportionnellement.
    spec = SymbolSpec(contract_size=100.0)
    stop, cancel = tighten_stop_or_cancel(0.001, 0.01, 0.05, 10000.0, 2000.0, 0.02, spec)
    # max_loss=200$ ; tightened = 200/(0.01*100*2000) = 0.1 ... mais 0.1 > 0.05
    # (stop d'origine) -> ne resserre PAS (ne resserre que si ça réduit).
    assert stop == 0.05 and cancel is False


def test_tighten_stop_or_cancel_actually_tightens_downward():
    spec = SymbolSpec(contract_size=100.0)
    # max_loss=200$ ; tightened = 200/(0.01*100*2000) = 0.1 ; stop d'origine=0.5
    # -> 0.1 < 0.5, donc resserré à 0.1.
    stop, cancel = tighten_stop_or_cancel(0.001, 0.01, 0.5, 10000.0, 2000.0, 0.02, spec)
    assert stop == pytest.approx(0.1) and cancel is False


def test_tighten_stop_or_cancel_cancels_below_broker_stops_level():
    spec = SymbolSpec(contract_size=100.0, stops_level_points=50, point=0.01)
    # min_stop_pct = (50*0.01)/2000 = 0.00025 ; stop resserré (0.1) > ça donc
    # pas d'annulation dans ce cas -- on force un stop_pct déjà minuscule.
    stop, cancel = tighten_stop_or_cancel(1.0, 1.0, 0.0001, 10000.0, 2000.0, 0.02, spec)
    assert cancel is True


def test_tighten_stop_or_cancel_never_widens_stop():
    spec = SymbolSpec(contract_size=100.0)
    # tightened serait plus GRAND que le stop d'origine -> reste inchangé.
    stop, cancel = tighten_stop_or_cancel(0.001, 0.002, 0.001, 10000.0, 2000.0, 0.02, spec)
    assert stop == 0.001 and cancel is False


def test_tighten_stop_or_cancel_none_stop_pct_passthrough():
    spec = SymbolSpec(contract_size=100.0)
    stop, cancel = tighten_stop_or_cancel(0.05, 0.05, None, 10000.0, 2000.0, 0.02, spec)
    assert stop is None and cancel is False
