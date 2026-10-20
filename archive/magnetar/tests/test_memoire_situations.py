"""Tests de LA MÉMOIRE DES SITUATIONS (collapsar/regarder/pistes/memoire_situations.py) :
- SANS FUTUR : les vecteurs (zones, tendances, structure, compression, peur GVZ, heure, mouvement) calculés sur des
  données coupées à t = calcul complet ;
- la suite de chaque moment (avances 24 / 72 h, gros mouvement, premier côté atteint) à la main ;
- LA BARRIÈRE : seuls les souvenirs dont la suite était connue 5 jours avant la question sont lus ; voisins = recherche
  exacte ; prévisions inchangées si l'on remplace la suite des souvenirs non permis par n'importe quoi ;
- TEST PIÈGE (marché inventé sans avantage) : la mémoire honnête n'y voit rien, la mémoire qui triche y voit « tout » ;
- liste figée et seuil de preuve.
Depuis Test_IA : $env:CUDA_VISIBLE_DEVICES='-1'; venv_gpu\\Scripts\\python.exe -m pytest collapsar/tests/test_memoire_situations.py -q
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from collapsar.ecole.precision import donnees as D
from collapsar.regarder.pistes import memoire_situations as MS
from test_ecole_precision import chemin_minutes
from test_mouvements import _calc

JOUR = MS.JOUR_NS


@pytest.fixture(scope="module")
def invente():
    m = chemin_minutes(160, 41, depart="2019-01-07", pas=0.0002)
    q = D.reechantillonner(m, "15min")
    return q, _calc(q)


# ================================================================================================ sans futur
def test_vecteurs_sans_futur(invente):
    q, x = invente
    rows = MS.moments(x)
    assert len(rows) > 1500
    V = MS.vecteurs(x, rows)
    assert V.shape == (len(rows), MS.NV) and np.isfinite(V).all()
    t15 = np.asarray(x["t15"], np.int64)
    T = len(q)
    vus = 0
    for r in (int(T * 0.6), int(T * 0.85)):
        xc = _calc(q.iloc[:r + 1].reset_index(drop=True))
        rr = rows[rows <= r]
        Vc = MS.vecteurs(xc, rr, coupe_ns=int(t15[r]) + MS.QUINZE_NS + 1)
        assert np.allclose(V[:len(rr)], Vc, atol=1e-12, equal_nan=True), r
        vus += len(rr)
    assert vus > 2000
    # la peur GVZ du marché inventé (2019) est bien lue, et seulement ce qui était publié
    assert (V[:, MS.NOMS_V.index("peur or GVZ (1 an)")] != 0).mean() > 0.5


# ================================================================================================ à la main
def test_suites_a_la_main():
    h = np.array([10.0, 10.5, 11.2, 13.4, 12.0, 12.0, 12.0])
    l = np.array([9.5, 9.6, 10.1, 11.0, 11.5, 6.0, 11.0])
    c = np.array([10.0, 10.2, 11.0, 13.0, 11.8, 11.7, 11.9])
    rows = np.array([0, 1, 3])
    out, s, ok = MS._suites(h, l, c, rows, c[rows], np.ones(3), 2, 4, 3.0)
    assert list(ok) == [True, True, False]
    # moment 0 (prix 10) : 24 h = bougies 1-2 ; 72 h = bougies 1-4 ; +3 atteint à la bougie 3 (13,4) en premier
    assert out[0, 0] == pytest.approx(1.2) and out[0, 1] == pytest.approx(0.4) and out[0, 4] == pytest.approx(1.0)
    assert out[0, 2] == pytest.approx(3.4) and out[0, 3] == pytest.approx(0.4) and out[0, 5] == pytest.approx(1.8)
    assert s[0] == 1
    # moment 1 (prix 10,2) : +3 = 13,2 atteint à la bougie 3 ; -3 = 7,2 atteint à la bougie 5 (plus tard) -> hausse
    assert s[1] == 1 and out[1, 3] == pytest.approx(10.2 - 6.0)
    # les deux côtés dans la même bougie : sens inconnu
    out2, s2, _ = MS._suites(np.array([10.0, 14.0, 10.0]), np.array([10.0, 6.0, 10.0]), np.full(3, 10.0),
                             np.array([0]), np.array([10.0]), np.ones(1), 1, 2, 3.0)
    assert s2[0] == 2


# ================================================================================================ la barrière
def test_barriere_et_voisins_exacts():
    rng = np.random.default_rng(5)
    n, d = 3000, 6
    Xm = rng.normal(size=(n, d))
    fin = np.cumsum(rng.integers(1, 3, n)) * MS.HEURE_NS * 3
    dec_q = np.sort(rng.integers(int(fin[0]) + MS.MARGE_NS, int(fin[-1]) + MS.MARGE_NS + JOUR, 400))
    lim = MS.limite_memoire(fin, dec_q)
    Xq = rng.normal(size=(400, d))
    nb = MS.voisins(Xq, lim, Xm, 20, bloc=64)
    for i in range(400):
        L = lim[i]
        assert (fin[:L] + MS.MARGE_NS <= dec_q[i]).all() and (L == n or fin[L] + MS.MARGE_NS > dec_q[i])
        v = nb[i][nb[i] >= 0]
        assert (v < L).all()
        if L:
            dist = ((Xm[:L] - Xq[i]) ** 2).sum(1)
            vrai = np.argsort(dist, kind="stable")[:min(20, L)]
            assert np.allclose(np.sort(dist[v]), np.sort(dist[vrai]), rtol=1e-4, atol=1e-4)
    # la suite des souvenirs NON permis ne change rien aux prévisions
    gros = rng.random(n) < 0.1
    sens = np.where(gros, np.where(rng.random(n) < 0.5, 1, -1), 0)
    p1 = MS.predire(nb, 20, gros, sens)
    i0 = 200
    g2, s2 = gros.copy(), sens.copy()
    g2[lim[i0]:] = ~g2[lim[i0]:]
    s2[lim[i0]:] = -s2[lim[i0]:] + 1
    p2 = MS.predire(nb[:i0 + 1], 20, g2, s2)
    for k in ("p", "up", "dn", "n_gros"):
        assert np.array_equal(p1[k][:i0 + 1], p2[k], equal_nan=True)
    # taux de base = part des gros mouvements dans la mémoire permise
    pb = MS.taux_base(lim, gros)
    j = int(np.flatnonzero(lim > 0)[0])
    assert pb[j] == pytest.approx(gros[:lim[j]].mean())
    # version qui triche : le moment lui-même est exclu, tout le reste (futur compris) est permis
    soi = np.arange(0, 400) * 5
    nt = MS.voisins(Xm[soi], np.full(400, n), Xm, 5, soi=soi)
    assert not (nt == soi[:, None]).any() and (nt >= 0).all()


def test_piege_marche_invente():
    """Marché sans avantage : la mémoire honnête n'annonce rien (aire ~ 0,5) ; celle qui triche, en lisant les suites qui
    chevauchent celle du moment présent, annonce les gros mouvements presque parfaitement."""
    rng = np.random.default_rng(11)
    n = 20000
    P = 100 + np.cumsum(rng.normal(0, 0.25, n + 400))
    rows = np.arange(n)
    out, s, ok = MS._suites(P, P, P, rows, P[rows], np.ones(n), 24, 72, 3.0)
    gros = ok & (np.maximum(out[:, 2], out[:, 3]) >= 3.0)
    assert 0.05 < gros.mean() < 0.95
    # ce que « voit » la mémoire : trois valeurs qui changent lentement (comme des tendances), sans lien avec l'avenir
    X = np.cumsum(rng.normal(0, 0.05, (n, 3)), 0)
    fin = (rows + 72) * MS.HEURE_NS
    dec = rows * MS.HEURE_NS
    q = np.arange(3000, n, 3)
    lim = MS.limite_memoire(fin, dec[q])
    hon = MS.voisins(X[q], lim, X, 20)
    tri = MS.voisins(X[q], np.full(len(q), n), X, 20, soi=q)
    pb = MS.taux_base(lim, gros)
    y = gros[q]
    a_h = MS.aire(MS.predire(hon, 20, gros, s)["p"], y)
    a_t = MS.aire(MS.predire(tri, 20, gros, s)["p"], y)
    assert abs(a_h - 0.5) < 0.06, a_h
    assert a_t > 0.8 and a_t > a_h + 0.25, (a_h, a_t)
    sem = dec[q] // MS.SEMAINE_NS
    g_h = MS.mesure_gros(MS.predire(hon, 20, gros, s)["p"], pb, pb, pb, y, sem)
    g_t = MS.mesure_gros(MS.predire(tri, 20, gros, s)["p"], pb, pb, pb, y, sem)
    assert g_t["brier"]["m"] > 0 > g_h["brier"]["m"] - 1e-3


def test_signaux_a_la_main():
    pr = {"p": np.array([0.4, 0.4, 0.4, 0.1, 0.4]), "n_gros": np.array([8, 8, 4, 2, 8]),
          "up": np.array([6, 2, 4, 2, 4]), "dn": np.array([2, 6, 0, 0, 4])}
    pb = np.full(5, 0.15)
    assert list(MS.signaux(pr, pb)) == [1, -1, 0, 0, 0]


def test_stops_structure(invente):
    q, x = invente
    rows = MS.moments(x)[200:1200]
    for sg in (1, -1):
        st = MS.stops_structure(x, rows, np.full(len(rows), sg))
        ok = np.isfinite(st)
        assert ok.mean() > 0.3
        p, A = np.asarray(x["c"])[rows][ok], np.asarray(x["A"])[rows][ok]
        rd = sg * (p - st[ok])
        assert (rd >= MS.RISQUE_MIN_A * A - 1e-12).all() and (rd <= MS.RISQUE_MAX_A * A + 1e-12).all()


def test_liste_figee_et_seuil():
    assert MS.NV == 20 and MS.NOMS_V[MS.I_T60] == "tendance 60 j"
    assert MS.N_TOTAL == 1257 + 12 + 9 + 7
    assert MS.SEUIL == max(3.0, math.sqrt(2 * math.log(MS.N_TOTAL))) and 3.7 < MS.SEUIL < 3.9
    assert MS.PERIODES["choix"][1] == MS.PERIODES["verification"][0] == "2022-01-01"
    assert MS.PERIODES["verification"][1] == MS.PERIODES["controle"][0] and MS.PERIODES["controle"][1] <= "2025-10-01"
    assert MS.MARGE_NS == 5 * JOUR and MS.H72 == 288 and MS.GROS_A == 3.0
