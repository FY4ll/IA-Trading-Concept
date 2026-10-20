"""Positionnement des fonds sur l'or (collapsar/donnees/cot.py) : dates de publication prudentes et signaux sans futur."""
import numpy as np
import pandas as pd
import pytest

from collapsar.donnees import cot


def test_publication_normale_vendredi():
    p = cot.publication(pd.Series(pd.to_datetime(["2019-06-11"])))
    assert p.iloc[0] == pd.Timestamp("2019-06-14 15:30")


def test_publication_semaine_feriee_lundi_suivant():
    # Thanksgiving jeudi 28/11/2019 -> lundi 02/12 ; 4 juillet 2024 (jeudi) -> lundi 08/07
    p = cot.publication(pd.Series(pd.to_datetime(["2019-11-26", "2024-07-02"])))
    assert list(p) == [pd.Timestamp("2019-12-02 15:30"), pd.Timestamp("2024-07-08 15:30")]


def test_positions_du_lundi_meme_semaine():
    p = cot.publication(pd.Series(pd.to_datetime(["2018-12-24"])))     # mardi 25 férié -> publication lundi 31
    assert p.iloc[0] >= pd.Timestamp("2018-12-31 15:30")


def test_paralysies_exclues():
    m = cot.exclu(pd.Series(pd.to_datetime(["2013-10-08", "2013-09-24", "2019-01-15", "2019-03-12"])))
    assert list(m) == [True, False, True, False]


@pytest.mark.skipif(not cot.FICHIER.exists(), reason="fichier COT absent")
def test_signaux_sans_futur():
    c = cot.charger("2015-12-31")
    prix = pd.Series(np.linspace(1000, 1300, len(c)))
    complet = cot.signaux(c, prix)
    for k in (200, 300, len(c) - 1):
        coupe = cot.signaux(c.iloc[:k + 1].reset_index(drop=True), prix.iloc[:k + 1].reset_index(drop=True))
        a, b = complet.iloc[k][list(cot.SIGNAUX)].astype(float), coupe.iloc[-1][list(cot.SIGNAUX)].astype(float)
        assert np.allclose(a.to_numpy(), b.to_numpy(), equal_nan=True)
