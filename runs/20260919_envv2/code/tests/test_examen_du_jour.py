"""Examen du jour (09/10/2026) : un compte qui trade tous les marchés sur des jours jamais vus, vraies dates ; et
les marchés ajoutés (miroirs limités, statistiques d'entraînement enregistrées pour l'examen)."""
from __future__ import annotations
import importlib.util
import os

import numpy as np
import pandas as pd
import pytest

_spec = importlib.util.spec_from_file_location(
    "examen_du_jour", os.path.join(os.path.dirname(__file__), "..", "scripts", "examen_du_jour.py"))
ex = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ex)


def _s(vals, start="2026-10-09"):
    return pd.Series(vals, index=pd.date_range(start, periods=len(vals), freq="D"))


def test_account_sums_markets_on_the_same_real_dates():
    pf = ex.portefeuille({"EURUSD": _s([0.01, -0.005]), "US30": _s([0.002, 0.003, 0.004])})
    assert pf["jours"] == {"2026-10-09": pytest.approx(0.012), "2026-10-10": pytest.approx(-0.002),
                           "2026-10-11": pytest.approx(0.004)}
    assert pf["compte"] == pytest.approx(1.012 * 0.998 * 1.004 - 1)
    assert pf["verdict"] == "en cours"


def test_ftmo_verdicts():
    assert ex.portefeuille({"A": _s([0.01, -0.03]), "B": _s([0.0, -0.025])})["verdict"].startswith("RATÉ le 10/10")
    assert "perte totale" in ex.portefeuille({"A": _s([-0.04, -0.04, -0.04])})["verdict"]
    assert ex.portefeuille({"A": _s([0.04, 0.04, 0.04])})["verdict"].startswith("RÉUSSI le 11/10")
    assert ex.portefeuille({})["compte"] == 0.0


def test_daily_returns_include_the_first_day_from_the_starting_capital():
    times = pd.date_range("2026-10-09", periods=200, freq="15min")
    eq = np.r_[np.full(100, 10000.0), np.full(100, 10100.0)]
    eq[95:100] = 10050.0                                       # fin du premier jour : +0,5 %
    r = ex.jours_du_compte(eq, times, window_size=1)
    assert list(r.index.strftime("%d/%m")) == ["09/10", "10/10", "11/10"]
    assert r.iloc[0] == pytest.approx(0.005) and r.iloc[1] == pytest.approx(10100 / 10050 - 1)


def test_message_is_plain_and_complete():
    rep = {"compte": ex.portefeuille({"US30": _s([0.01]), "EURUSD": _s([-0.002])}),
           "par_marche": {"US30": {"rendement": 0.01, "trades": 3}, "EURUSD": {"rendement": -0.002, "trades": 2},
                          "ETHUSD": {"erreur": "statistiques d'entraînement absentes"}}}
    txt = ex.message(rep)
    assert "compte tous marchés +0.80%" in txt and "5 trades" in txt and "US30 +1.0%" in txt and "EURUSD -0.2%" in txt


def test_mirrors_only_for_listed_markets():
    from src.aurexis_data import _market_jobs
    cfg = {"multi_market": {"markets": {"EURUSD": "a.csv", "AUDCAD": "b.csv"}, "mirror": True,
                            "mirror_markets": ["EURUSD"]}, "data": {"folder": ""}}
    names = [(s, m) for s, _, m, _ in _market_jobs(cfg, 1000)]
    assert names == [("EURUSD", False), ("AUDCAD", False), ("EURUSD", True)]
    cfg["multi_market"].pop("mirror_markets")
    assert ("AUDCAD", True) in [(s, m) for s, _, m, _ in _market_jobs(cfg, 1000)], "défaut : tous les miroirs"


def test_training_stats_round_trip(tmp_path, monkeypatch):
    import src.aurexis_data as ad
    monkeypatch.setattr(ad, "STATS_DIR", str(tmp_path))
    ad.save_market_stats("EURUSD miroir", {"stats": {"rsi_14": (np.float64(50.5), 11.2)}, "k": 1.21},
                         pd.Timestamp("2022-12-30"))
    d = ad.load_market_stats("EURUSD miroir")
    assert d["stats"] == {"rsi_14": (50.5, 11.2)} and d["k"] == 1.21
    assert ad.load_market_stats("INCONNU") is None
