"""Tests du module tendance de fond et du compte heure par heure (20/10/2026)."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from cerveau import socle
from cerveau.mesure import compte as C
from cerveau.perception.tendance import TENDANCES
from core import donnees as D


@pytest.fixture(scope="module")
def or15():
    df = D.charger("XAUUSD", pd.Timestamp("2016-01-01"))
    return df[df["time"] >= pd.Timestamp("2012-01-01")].reset_index(drop=True)


def test_modules_enregistres():
    assert {"tendance_1m", "tendance_3m", "tendance_6m", "tendance_12m"} <= {m.nom for m in socle.modules("perception")}


def test_sens_sans_futur(or15):
    """Le sens d'un jour ne change pas si on coupe l'historique après ce jour."""
    j_long = TENDANCES[3].jours(or15)
    court = or15[or15["time"] < pd.Timestamp("2014-06-01")].reset_index(drop=True)
    j_court = TENDANCES[3].jours(court)
    a = j_long[j_long["fin"] < pd.Timestamp("2014-05-30")][["fin", "sens", "vol_jour", "atr"]].reset_index(drop=True)
    b = j_court[j_court["fin"] < pd.Timestamp("2014-05-30")][["fin", "sens", "vol_jour", "atr"]].reset_index(drop=True)
    pd.testing.assert_frame_equal(a, b)


def test_sens_est_le_signe_du_rendement(or15):
    j = TENDANCES[6].jours(or15)
    ligne = j.iloc[400]
    ref = j[j["debut"] <= ligne["debut"] - pd.DateOffset(months=6)].iloc[-1]
    assert ligne["sens"] == np.sign(ligne["close"] / ref["close"] - 1)


def test_compte_achat_inverse_et_frais(or15):
    """Le système et son inverse paient chacun les frais : leur somme est négative (frais + nuits), pas nulle."""
    h1 = C.heures(or15)
    j = TENDANCES[3].jours(or15)
    s = j["sens"].to_numpy()
    a = C.simuler("XAUUSD", h1, j, s)
    b = C.simuler("XAUUSD", h1, j, -s)
    assert len(a["ouvertures"]) > 5
    assert (a["eq"][-1] - C.CAPITAL) + (b["eq"][-1] - C.CAPITAL) < 0
    assert (a["pire"] <= a["eq"] + 1e-6).all()


def _serie_montante():
    """Un prix qui double en 100 jours (bougies d'1 h), volatilité constante : une position d'achat jamais stoppée."""
    t = pd.date_range("2020-01-06", periods=2400, freq="1h")
    prix = 1000.0 * np.exp(np.linspace(0, np.log(2), 2400))
    h1 = {"t": pd.DatetimeIndex(t), "open": prix, "high": prix * 1.0005, "low": prix * 0.9995, "close": prix}
    fins = t[23::24]
    j = pd.DataFrame({"fin": fins, "close": prix[23::24], "vol_jour": 0.01, "atr": prix[23::24] * 0.01})
    return h1, j


def test_taille_fixe_grossit_avec_le_prix_vol_reste_a_la_cible():
    """Taille figée : le montant engagé double avec le prix ; taille « vol » : ramenée chaque jour à la cible."""
    h1, j = _serie_montante()
    s = np.ones(len(j), int)
    fixe = C.simuler("XAUUSD", h1, j, s, taille="fixe")
    vol = C.simuler("XAUUSD", h1, j, s, taille="vol")
    assert len(fixe["ouvertures"]) == len(vol["ouvertures"]) == 1
    # gain de la taille figée ~ montant initial × 100 % ; « vol » ~ montant × ln(2) (exposition constante)
    montant = C.CAPITAL * C.VOL_CIBLE / (0.01 * np.sqrt(252))
    assert fixe["eq"][-1] - C.CAPITAL == pytest.approx(montant, rel=0.05)
    assert vol["eq"][-1] - C.CAPITAL == pytest.approx(montant * np.log(2), rel=0.10)
    assert vol["volume_total"] > fixe["volume_total"]              # les ajustements se paient


def test_taille_capital_suit_la_valeur_du_compte():
    h1, j = _serie_montante()
    s = np.ones(len(j), int)
    cv = C.simuler("XAUUSD", h1, j, s, taille="capital_vol")
    v = C.simuler("XAUUSD", h1, j, s, taille="vol")
    assert cv["eq"][-1] > v["eq"][-1]                               # le gain réinvesti grossit la taille
    with pytest.raises(ValueError):
        C.simuler("XAUUSD", h1, j, s, taille="nimporte")


def test_stop_large_touche():
    """Un achat dont le prix s'effondre de 10 % sort au stop (3 ATR) et ne perd pas plus que prévu (+ frais)."""
    t = pd.date_range("2020-01-06", periods=200, freq="1h")
    prix = np.r_[np.full(100, 1000.0), np.full(100, 900.0)]
    h1 = {"t": pd.DatetimeIndex(t), "open": prix, "high": prix + 1, "low": prix - 1, "close": prix}
    j = pd.DataFrame({"fin": [t[10]], "close": [1000.0], "vol_jour": [0.01], "atr": [10.0]})
    r = C.simuler("XAUUSD", h1, j, np.array([1]))
    montant = C.CAPITAL * C.VOL_CIBLE / (0.01 * np.sqrt(252))
    perte_max = montant / 1000 * 100                          # sortie à l'ouverture 900 (trou sous le stop 970)
    assert C.CAPITAL - r["eq"][-1] == pytest.approx(perte_max, rel=0.02)
    assert len(r["ouvertures"]) == 1
