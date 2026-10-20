"""Tests du portefeuille journalier multi-marchés (compétition 2, 20/10/2026)."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from cerveau.mesure import portefeuille as PF


@pytest.fixture(scope="module")
def u():
    return PF.Univers(["EURUSD", "USDJPY", "USA500IDXUSD"], pd.Timestamp("2016-07-01"), pd.Timestamp("2015-01-01"))


def test_gain_achat_et_frais(u):
    c = pd.DataFrame(np.nan, index=u.jours, columns=u.marches)
    c.iloc[100, 0] = 50_000.0                                     # achat de 50 000 $ d'EURUSD
    r = u.simuler(c)
    g = r["gain"]["EURUSD"]
    p = u.P["EURUSD"]
    attendu = 50_000 * (p.iloc[101] / p.iloc[100] - 1)
    assert g.iloc[101] == pytest.approx(attendu - 50_000 * u.achat["EURUSD"].iloc[101] / 360 * u.nuits["EURUSD"].iloc[101], rel=1e-6)
    assert g.iloc[100] == pytest.approx(-50_000 * u.demi_frais["EURUSD"].iloc[100])
    assert (r["pos"]["EURUSD"].iloc[100:] == 50_000).all()


def test_dollar_base_et_sens(u):
    """USDJPY : acheter 10 000 $ quand le dollar monte de 1 % contre le yen rapporte ~ +99 $ ; le rendement log est
    compté dans le sens « devise (yen) contre dollar »."""
    j = u.marches.index("USDJPY")
    assert u.base_dollar[j] and not u.base_dollar[0]
    p = u.P["USDJPY"]
    d = 150
    assert u.r["USDJPY"].iloc[d] == pytest.approx(1 - p.iloc[d - 1] / p.iloc[d])
    assert u.lr["USDJPY"].iloc[d] == pytest.approx(-np.log(p.iloc[d] / p.iloc[d - 1]))


def test_vendredi_seulement_reduire(u):
    vendredis = np.flatnonzero(u.vendredi)
    v = vendredis[vendredis > 120][0]
    c = pd.DataFrame(np.nan, index=u.jours, columns=u.marches)
    c.iloc[v - 1, 0] = 10_000.0
    c.iloc[v, 0] = 30_000.0                                       # agrandir un vendredi : refusé
    c.iloc[v, 1] = 5_000.0                                        # ouvrir un vendredi : refusé
    r = u.simuler(c)
    assert r["pos"]["EURUSD"].iloc[v] == 10_000.0 and r["pos"]["USDJPY"].iloc[v] == 0.0
    c.iloc[v, 0] = -10_000.0                                      # se retourner un vendredi : fermer seulement
    assert u.simuler(c)["pos"]["EURUSD"].iloc[v] == 0.0


def test_inverse_paie_les_frais(u):
    c = pd.DataFrame(np.nan, index=u.jours, columns=u.marches)
    c.iloc[50:300:10, :] = 20_000.0
    c.iloc[55:300:10, :] = -20_000.0
    a, b = u.simuler(c), u.simuler(-c)
    assert (a["gain"].sum().sum() + b["gain"].sum().sum()) < 0
