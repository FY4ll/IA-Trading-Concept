"""La note du juge : avantage sur le jumeau au hasard, seuil corrigé du nombre d'essais."""
import math

import numpy as np
import pandas as pd
import pytest
import torch

from collapsar.cerveau.humain import ACHETER, CHANGER, TraderHumain
from collapsar.ecole.regard import ClasseRegard, jouer_comptes
from collapsar.juge.note import avantage_sur_hasard, seuil_essais

AUCUNE_ANNONCE = pd.DataFrame({"temps": pd.to_datetime([]), "devise": []})


@pytest.fixture(autouse=True)
def sans_releve(monkeypatch):
    from collapsar.mains import fiches
    monkeypatch.setattr(fiches, "_reelles", lambda: {})


def _res(gains, reussis=None, morts=None):
    n = len(gains)
    return {"gains_comptes_pct_mois": list(gains), "reussis_comptes": reussis or [False] * n,
            "morts_comptes": morts or [False] * n}


def test_seuil_au_moins_3_et_croit_avec_les_essais():
    assert seuil_essais(1) == 3.0
    assert seuil_essais(10_000) == pytest.approx(math.sqrt(2 * math.log(10_000)))
    assert seuil_essais(10_000) > 4


def test_avantage_compte_par_compte():
    rng = np.random.default_rng(0)
    base = rng.normal(0, 1, 200)
    elle = _res(base + 0.5)
    jum = _res(base)
    a = avantage_sur_hasard(elle, [jum], essais=1)
    assert a["avantage_pct_mois"] == pytest.approx(0.5)
    assert a["prouve"], "un avantage net et constant sur 200 comptes est prouvé"
    b = avantage_sur_hasard(_res(base + rng.normal(0, 1, 200) * 0.0 + 0.01 * rng.normal(0, 1, 200)), [jum], 1)
    assert not b["prouve"]


def test_les_comptes_qui_se_chevauchent_comptent_moins():
    rng = np.random.default_rng(1)
    elle, jum = _res(rng.normal(0.2, 1, 40)), _res(rng.normal(0, 1, 40))
    libre = avantage_sur_hasard(elle, [jum], 1)
    chevauche = avantage_sur_hasard(elle, [jum], 1, duree=4200, ecart_departs=1050)
    assert chevauche["comptes_independants"] == pytest.approx(10)
    assert chevauche["incertitude_pct_mois"] == pytest.approx(libre["incertitude_pct_mois"] * 2)


def test_le_jumeau_tire_le_sens_au_hasard():
    t = pd.date_range("2022-01-03", periods=60 * 96, freq="15min")
    t = t[t.dayofweek < 5]
    c = 1.1 * np.exp(np.cumsum(np.random.default_rng(0).normal(0, 0.0007, len(t))))
    df = pd.DataFrame({"time": t, "open": np.r_[c[0], c[:-1]], "high": c * 1.0003, "low": c * 0.9997, "close": c,
                       "volume": 1.0})
    df["high"] = df[["open", "high", "close"]].max(axis=1)
    df["low"] = df[["open", "low", "close"]].min(axis=1)
    classe = ClasseRegard(["EURUSD"], "cpu", {"EURUSD": df}, annonces=AUCUNE_ANNONCE)
    agent = TraderHumain()
    with torch.no_grad():
        agent.decisions.geste.bias.copy_(torch.tensor([-10.0, -10.0, 10.0, -10.0]))       # change à chaque regard
        agent.decisions.position.bias[:3] = torch.tensor([-10.0, -10.0, 10.0])     # et achète toujours
        agent.decisions.regard.bias.fill_(math.log(8))
    signes = {}
    for jumeau in (False, True):
        notes = []
        jouer_comptes(classe, agent, torch.tensor([3000]), duree=600, carnet=notes, jumeau=jumeau)
        signes[jumeau] = {np.sign(g["position_dollars"]) for n in notes if n["type"] == "regard" for g in n["gestes"]
                          if g["geste"] == CHANGER}
    assert signes[False] == {1.0}, "elle achète toujours"
    assert signes[True] == {1.0, -1.0}, "son jumeau achète ou vend au hasard"
