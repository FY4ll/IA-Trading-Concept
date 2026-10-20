"""Tests de core (20/10/2026) : les copies donnent EXACTEMENT les résultats des originaux de COLLAPSAR (tant qu'ils
existent), les bornes d'honnêteté tiennent, le jumeau au hasard fait ce qu'il dit.
Depuis Test_IA : $env:CUDA_VISIBLE_DEVICES='-1'; venv_gpu\\Scripts\\python.exe -m pytest core/tests -q
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest
import torch

from core import donnees as D
from core import jumeau as J
from core.ftmo import frais as F
from core.ftmo import nuit as N
from core.ftmo.fiches import fiche
from core.ftmo.horloge import Horloge
from core.ftmo.simulateur import CAPITAL, Comptes, Ordres


@pytest.fixture(scope="module")
def or_2019():
    df = D.charger("XAUUSD", pd.Timestamp("2019-04-01"))
    return df[df["time"] >= pd.Timestamp("2019-01-01")].reset_index(drop=True)


# ------------------------------------------------------------------------------------------------ données
def test_honnetete_par_defaut():
    df = D.charger("XAUUSD")
    assert df["time"].max() < D.FIN_APPRENTISSAGE
    assert df["time"].is_monotonic_increasing and not df["time"].duplicated().any()
    assert (df["high"] >= df[["open", "close"]].max(axis=1)).all()
    assert (df["low"] <= df[["open", "close"]].min(axis=1)).all()


def test_donnees_identiques_a_collapsar():
    dm = pytest.importorskip("collapsar.donnees.marches")
    a = D.charger("XAUUSD", pd.Timestamp("2020-01-01"), cache=False)
    b = dm.charger("XAUUSD", pd.Timestamp("2020-01-01"), cache=False)
    pd.testing.assert_frame_equal(a, b)


def test_echelles_sans_futur(or_2019):
    h4 = D.echelle(or_2019, "4 h")
    k = D.dernieres_terminees(or_2019["time"].values, h4)
    decision = or_2019["time"].values.astype("datetime64[ns]") + D.QUINZE
    ok = k >= 0
    assert (h4["fin"][k[ok]] <= decision[ok]).all()            # jamais une bougie de 4 h pas encore fermée


def test_minutes_or_et_cinq_minutes():
    m = D.charger_minutes_or(pd.Timestamp("2019-01-08"), depuis=pd.Timestamp("2019-01-02"))
    assert len(m) > 1000 and m["time"].max() < pd.Timestamp("2019-01-08")
    m5 = D.reechantillonner(m, "5min")
    assert (m5["time"].dt.minute % 5 == 0).all()
    assert m5["high"].max() == m["high"].max() and m5["low"].min() == m["low"].min()


# ------------------------------------------------------------------------------------------------ FTMO
def test_frais_et_nuits_identiques_a_collapsar():
    ff = pytest.importorskip("collapsar.mains.frais_ftmo")
    nu = pytest.importorskip("collapsar.mains.nuit")
    fi = pytest.importorskip("collapsar.mains.fiches")
    prix = np.array([1200.0, 1800.0, 2400.0, 4000.0])
    assert np.array_equal(F.frais("XAUUSD", prix), ff.frais("XAUUSD", prix))
    t = pd.date_range("2012-01-01", "2025-09-01", freq="7D")
    a1, v1 = N.taux_nuit(fiche("XAUUSD"), t)
    a2, v2 = nu.taux_nuit(fi.fiche("XAUUSD"), t)
    assert np.array_equal(a1, a2) and np.array_equal(v1, v2)


def _jouer(Horl, Cpt, Ord, df, pas=600, B=48, graine=3):
    """Ordres au hasard (positions, stops, objectifs, ordres à l'avance) : trajectoire de la valeur des comptes."""
    h = Horl({"XAUUSD": df}, ["XAUUSD"], nuit_historique=True)
    c = Cpt(h, B)
    c.recommencer(torch.ones(B, dtype=torch.bool), torch.zeros(B, dtype=torch.int64))
    g = torch.Generator().manual_seed(graine)
    vals = []
    for _ in range(pas):
        prix = h.c[c.t]                                         # [B, 1] : un seul marché
        tirage = torch.rand(B, 1, generator=g, dtype=torch.float64)
        cible = torch.where(tirage < 0.05, 30_000.0, torch.where(tirage < 0.10, -30_000.0,
                            torch.where(tirage < 0.13, 0.0, float("nan"))))
        cible = cible.to(torch.float64)
        sens = torch.sign(torch.nan_to_num(cible))
        stop = torch.where(sens != 0, prix * (1 - 0.004 * sens), torch.full_like(prix, float("nan")))
        obj = torch.where(sens != 0, prix * (1 + 0.008 * sens), torch.full_like(prix, float("nan")))
        att = torch.where(tirage > 0.97, 1, 0).to(torch.int64)
        o = Ord(cible=cible, stop=stop, objectif=obj, attente_type=att, attente_prix=prix * 0.998,
                attente_montant=torch.full_like(prix, 20_000.0), attente_duree=torch.full_like(prix, 8.0))
        r = c.pas(o)
        vals.append(r["valeur"].clone())
    return torch.stack(vals)


def test_simulateur_identique_a_collapsar(or_2019):
    hz = pytest.importorskip("collapsar.mains.horloge")
    sm = pytest.importorskip("collapsar.mains.simulateur")
    a = _jouer(Horloge, Comptes, Ordres, or_2019)
    b = _jouer(hz.Horloge, sm.Comptes, sm.Ordres, or_2019)
    assert torch.equal(a, b)
    assert not torch.allclose(a[-1], torch.full_like(a[-1], CAPITAL))      # il s'est bien passé quelque chose


def test_mur_du_jour(or_2019):
    """Une position énorme contre le marché : le mur des -5 % du jour termine la partie."""
    h = Horloge({"XAUUSD": or_2019}, ["XAUUSD"])
    c = Comptes(h, 1)
    c.recommencer(torch.ones(1, dtype=torch.bool), torch.zeros(1, dtype=torch.int64))
    mort = False
    for _ in range(2000):
        r = c.pas(Ordres(cible=torch.tensor([[1_400_000.0]], dtype=torch.float64)))
        if r["mort"].item():
            mort = True
            break
    assert mort


# ------------------------------------------------------------------------------------------------ jumeau
def test_jumeau_meme_gestes_sens_au_hasard():
    its = [{"t": i, "sens": 1, "entree": 2000.0, "stop": 1990.0, "objectifs": [2020.0, 2050.0], "risque": 0.005}
           for i in range(4000)]
    jum = J.intentions_jumeau(its, graine=1)
    inv = np.array([j["sens"] == -1 for j in jum])
    assert 0.47 < inv.mean() < 0.53
    for it, j in zip(its, jum):
        assert j["t"] == it["t"] and j["risque"] == it["risque"]
        if j["sens"] == -1:
            assert j["stop"] == 2010.0 and j["objectifs"] == [1980.0, 1950.0]
        else:
            assert j["stop"] == 1990.0
    assert J.intentions_jumeau(its, 1) == jum                     # même graine = même jumeau


def test_comparer():
    g = np.array([1.0, 2.0, 0.5, 1.5])
    r = J.comparer(g, g)
    assert r["avantage"] == 0.0 and not r["net"]
    rng = np.random.default_rng(0)
    ia = rng.normal(1.0, 0.5, 200)
    ju = rng.normal(0.0, 0.5, (5, 200))
    r = J.comparer(ia, ju)
    assert r["net"] and r["force"] > 2
    r2 = J.comparer(ia, ju, groupes=np.repeat(np.arange(100), 2))
    assert math.isfinite(r2["incertitude"])
    perd = J.comparer(ia - 3.0, ju - 4.0)                         # bat le hasard mais perd de l'argent : pas « net »
    assert perd["avantage"] > 0 and not perd["net"]
