"""Tests des PROPOSITIONS DE DIRECTION de l'arbre HYPERNOVA (collapsar/ecole/precision/direction.py) :
- sans futur : calcul coupé à t = calcul complet (tendance de fond, cassure 24 h C2, contre la foule C1), sur données
  inventées ; le jour en cours n'est jamais regardé par la tendance ;
- fidélité : C2 et C1 retrouvent exactement les signaux des pistes d'origine (bitcoin_journee via chef_crypto, et
  crypto_flux) sur les vraies données 2024-2025 ;
- la mesure (regarder/pistes/direction_hypernova.py) : liste figée et seuil de preuve.
Depuis Test_IA : $env:CUDA_VISIBLE_DEVICES='-1'; venv_gpu\\Scripts\\python.exe -m pytest collapsar/tests/test_direction.py -q
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from collapsar.ecole.precision import direction as DI

MIN = 60 * 10 ** 9


# ================================================================================================ tendance de fond
def test_tendance_sans_futur_et_jour_en_cours_ignore():
    rng = np.random.default_rng(1)
    t15 = pd.Timestamp("2020-01-01").value + np.arange(400 * 96) * 15 * MIN
    clo = 100 * np.exp(np.cumsum(rng.normal(0, 0.002, len(t15))))
    jours, cj = DI.clotures_jour(t15, clo)
    assert len(jours) == 400 and cj[0] == clo[95]
    t = pd.Timestamp("2020-09-15 13:45").value + np.arange(50) * 7 * 3600 * 10 ** 9
    s, f = DI.tendance_aux(jours, cj, t)
    for i, ti in enumerate(t):
        coupe = t15 + 15 * MIN <= ti                                  # bougies closes à t
        jc, cc = DI.clotures_jour(t15[coupe], clo[coupe])
        sc, fc = DI.tendance_aux(jc, cc, t[i:i + 1])
        assert np.array_equal(sc[0], s[i]) and np.allclose(fc[0], f[i])
        # changer la fin du jour en cours ne change rien
        clo2 = clo.copy()
        jour = ti - ti % DI.JOUR_NS
        clo2[(t15 >= jour)] *= 1.5
        j2, c2_ = DI.clotures_jour(t15, clo2)
        s2, _ = DI.tendance_aux(j2, c2_, t[i:i + 1])
        assert np.array_equal(s2[0], s[i])
    assert set(np.unique(s)) <= {-1, 0, 1} and np.abs(f).max() <= 3


def test_tendance_definition_simple():
    jours = pd.Timestamp("2021-01-01").value + np.arange(200) * DI.JOUR_NS
    clo = np.r_[np.linspace(100, 200, 150), np.linspace(200, 170, 50)]
    t = np.array([jours[149] + DI.JOUR_NS + 5 * 3600 * 10 ** 9])        # le jour 150 en cours : dernier fermé = 149
    s, _ = DI.tendance_aux(jours, clo, t)
    assert list(s[0]) == [1, 1, 1]
    t = np.array([jours[199] + 3600 * 10 ** 9])                          # dernier fermé = 198 (baisse depuis 150)
    s, _ = DI.tendance_aux(jours, clo, t)
    assert list(s[0]) == [-1, -1, 1]
    s, _ = DI.tendance_aux(jours, clo, np.array([jours[10]]))
    assert list(s[0]) == [0, 0, 0]                                      # pas assez d'historique


# ================================================================================================ cassure 24 h (C2)
def _quinze_invente(jours=60, graine=2):
    rng = np.random.default_rng(graine)
    t15 = pd.Timestamp("2022-03-07").value + np.arange(jours * 96) * 15 * MIN   # un lundi
    keep = rng.random(len(t15)) > 0.01
    t15 = t15[keep]
    c = 100 * np.exp(np.cumsum(rng.normal(0, 0.004, len(t15))))
    h = c * np.exp(np.abs(rng.normal(0, 0.002, len(t15))))
    l = c * np.exp(-np.abs(rng.normal(0, 0.002, len(t15))))
    return t15, h, l, c


def test_c2_sans_futur():
    t15, h, l, c = _quinze_invente()
    deb, fin, sens = DI.c2_intervalles(t15, h, l, c)
    assert len(deb) > 20 and set(np.unique(sens)) == {-1, 1}
    assert np.all(fin > deb) and np.all(deb[1:] >= fin[:-1])
    rng = np.random.default_rng(3)
    ts = rng.choice(t15[96 * 3:], 120, replace=False) + 15 * MIN
    plein = DI.en_cours(deb, fin, sens, ts)
    assert (plein != 0).any()
    for ti, v in zip(ts, plein):
        k = t15 + 15 * MIN <= ti
        d2, f2, s2 = DI.c2_intervalles(t15[k], h[k], l[k], c[k])
        assert DI.en_cours(d2, f2, s2, np.array([ti]))[0] == v


def test_c2_heures_et_week_end():
    t15, h, l, c = _quinze_invente()
    deb, fin, _ = DI.c2_intervalles(t15, h, l, c)
    hd = (deb % DI.JOUR_NS) // DI.HEURE_NS
    assert hd.min() >= 1 and hd.max() <= 22 and (deb % DI.HEURE_NS == 0).all()
    assert ((fin % DI.JOUR_NS) <= DI.C2_FIN_MIN * MIN).all()
    dow = ((deb // DI.JOUR_NS) + 3) % 7
    assert (dow < 5).all()


# ================================================================================================ contre la foule (C1)
def test_c1_sans_futur():
    rng = np.random.default_rng(4)
    m5 = pd.Timestamp("2021-01-01").value + np.arange(200 * 288) * 5 * MIN
    m5 = m5[rng.random(len(m5)) > 0.02]
    ratio = np.exp(np.cumsum(rng.normal(0, 0.004, len(m5))))
    connu = m5 + DI.C1_RETARD
    deb, fin, sens = DI.c1_intervalles(connu, ratio)
    assert len(deb) > 10 and np.all(fin - deb == DI.C1_TENUE * DI.HEURE_NS)
    ts = rng.choice(connu[288 * 40:], 80, replace=False) + 7 * MIN
    plein = DI.en_cours(deb, fin, sens, ts)
    assert (plein != 0).any()
    for ti, v in zip(ts, plein):
        k = connu <= ti
        d2, f2, s2 = DI.c1_intervalles(connu[k], ratio[k])
        assert DI.en_cours(d2, f2, s2, np.array([ti]))[0] == v


def test_hors_marches_neutre():
    t = np.array([pd.Timestamp("2024-05-01").value])
    assert DI.c2("XAUUSD", t)[0] == 0 and DI.c2("SOLUSDT", t)[0] == 0
    assert DI.c1("EURUSD", t)[0] == 0


# ================================================================================================ fidélité aux pistes
def _ensemble(deb, sens, de, a):
    lo, hi = pd.Timestamp(de).value, pd.Timestamp(a).value
    return {(int(d), int(s)) for d, s in zip(deb, sens) if lo <= d < hi}


def test_c2_identique_a_la_piste():
    from collapsar.regarder.pistes import chef_crypto as cc
    if not (cc.BINANCE / "BTCUSDT_M15.csv").exists():
        pytest.skip("données Binance absentes")
    df = cc.charger_autre("BTCUSDT")
    df = df[df["time"] < pd.Timestamp("2025-10-01")].reset_index(drop=True)
    t = cc.trades_cassure(df, 0.0)
    ref = _ensemble(pd.to_datetime(t["serveur_entree"]).astype("datetime64[ns]").astype(np.int64), t["sens"],
                    "2024-01-01", "2025-10-01")
    deb, _, s = DI._c2("BTCUSDT")
    moi = _ensemble(deb, s, "2024-01-01", "2025-10-01")
    assert len(ref) > 300 and ref == moi


def test_c1_identique_a_la_piste():
    from collapsar.regarder.pistes import crypto_flux as cf
    if not (cf.FUT / "metrics" / "BTCUSDT.csv").exists():
        pytest.skip("données Binance futures absentes")
    F = cf.caracteristiques("BTCUSDT")
    tm = cf.trades_marche("BTCUSDT", F, cf.signaux(F), ("C1",))
    ref = _ensemble(pd.to_datetime(tm["entree"]).astype("datetime64[ns]").astype(np.int64), tm["sens"],
                    "2024-01-01", "2025-09-25")
    deb, _, s = DI._c1("BTCUSDT")
    moi = _ensemble(deb, s, "2024-01-01", "2025-09-25")
    assert len(ref) > 100 and ref == moi


# ================================================================================================ la mesure
def test_liste_figee_et_seuil():
    from collapsar.regarder.pistes import direction_hypernova as DH
    assert len(DH.COMBINAISONS) == 9
    assert DH.N_CASES == 2 * (4 * 4 + 5) + 1
    assert DH.SEUIL == max(3.0, math.sqrt(2 * math.log(DH.N_CASES)))
    for _, srcs, _ in DH.COMBINAISONS:
        assert set(srcs) <= set(DI.NOMS)
