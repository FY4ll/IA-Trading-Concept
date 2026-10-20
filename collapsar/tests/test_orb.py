"""La piste « ouverture de New York » (regarder/orb.py) sur des journées fabriquées (15/10/2026)."""
import numpy as np
import pandas as pd
import pytest

from collapsar.regarder import orb


def _jour(chemin):
    """Une séance de 390 minutes à partir d'une liste de prix de clôture (open = clôture précédente)."""
    c = np.asarray(chemin, float)
    o = np.r_[c[0], c[:-1]]
    h, l = np.maximum(o, c) + 0.01, np.minimum(o, c) - 0.01
    m = np.arange(len(c))
    return np.c_[m, o, h, l, c, np.full(len(c), np.nan)]


def test_cassure_haussiere_tenue_jusqu_a_15h55():
    # range 100-101 pendant 5 minutes, puis montée régulière jusqu'à 110
    chemin = [100, 101, 100.5, 100, 100.8] + list(np.linspace(101.2, 110, 385))
    r = orb.jour_orb(_jour(chemin), 5, frais=0.0, facteur={})
    assert r["sens"] == 1 and r["R"] > 5, "achat à la cassure, gros gain jusqu'à la sortie de 15h55"
    assert r["R_inverse"] == pytest.approx(-1.0, abs=0.05), "le jumeau inverse est stoppé à -1 R"


def test_stop_touche_et_frais_comptes():
    chemin = [100, 101, 100.5, 100, 100.8, 101.3] + list(np.linspace(101, 95, 384))
    r0 = orb.jour_orb(_jour(chemin), 5, frais=0.0, facteur={})
    r1 = orb.jour_orb(_jour(chemin), 5, frais=0.001, facteur={})
    assert r0["R"] == pytest.approx(-1.0, abs=0.1) and r1["R"] < r0["R"], "stoppée à -1 R, les frais l'aggravent"


def test_pas_de_cassure_pas_de_trade():
    chemin = [100, 101, 100.5, 100, 100.8] + [100.5] * 385
    assert orb.jour_orb(_jour(chemin), 5, frais=0.0, facteur={}) is None


def test_note_contre_le_jumeau():
    rng = np.random.default_rng(0)
    bon = pd.DataFrame({"jour": pd.date_range("2016-01-01", periods=400), "R": rng.normal(0.3, 1, 400)})
    bon["R_inverse"] = -bon["R"] - 0.1
    assert orb.note(bon)["force"] > 3
    hasard = bon.assign(R_inverse=bon["R"] + rng.normal(0, 0.01, 400))
    assert abs(orb.note(hasard)["force"]) < 3


def test_seuil_corrige_du_nombre_de_variantes():
    assert orb.seuil(18) == 3.0 and orb.seuil(10_000) > 4
