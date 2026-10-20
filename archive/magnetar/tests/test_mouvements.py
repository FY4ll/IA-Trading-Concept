"""Tests des MOUVEMENTS DU JOUR (collapsar/regarder/pistes/mouvements.py) :
- le STOP SUIVEUR calculé à la main (achat, vente retournée, nouveau creux seulement, jamais en arrière, jamais au-delà
  du prix, sortie au stop avec glissement) ;
- sans stop suiveur, le moteur donne EXACTEMENT juge_trade.un_trade (même simulateur) ;
- SANS FUTUR : creux / sommets du suiveur, tendance des unités, compression, rebonds / cassures et leurs stops (petite zone
  comprise) calculés sur des données coupées à r = calcul complet ;
- rebond / cassure / zone morte, courses de continuation, trader parfait, petite zone : à la main ;
- liste figée et seuil de preuve.
Depuis Test_IA : $env:CUDA_VISIBLE_DEVICES='-1'; venv_gpu\\Scripts\\python.exe -m pytest collapsar/tests/test_mouvements.py -q
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from collapsar.ecole.precision import donnees as D
from collapsar.ecole.precision import juge_trade as JT
from collapsar.ecole.precision import structure as S
from collapsar.ecole.precision.reglages import UNITES_15, R
from collapsar.regarder.pistes import mouvements as MV
from test_ecole_precision import chemin_minutes

NAN = np.nan


def _chemin(o, h, l, c, demi=1e-4):
    T = len(o)
    a = lambda x: np.asarray(x, float)
    return (a(o), a(h), a(l), a(c), np.ones(T), np.ones(T, bool), np.zeros(T, bool), np.full(T, demi),
            np.zeros(T), np.zeros(T), np.zeros(T))


def _un(ch, t, sens, stop, dest, dest_r, suiv, marge=0.1, suivre=True, horizon=MV.HORIZON):
    tv_l, tid_l, tv_s, tid_s = suiv
    return MV.trade_suiveur(*ch, t, sens, stop, dest, dest_r, horizon, 1.0, np.asarray(tv_l, float),
                            np.asarray(tid_l, np.int64), np.asarray(tv_s, float), np.asarray(tid_s, np.int64), marge, suivre)


# ================================================================================================ le stop suiveur
def test_stop_suiveur_a_la_main():
    s = 1e-4
    o = np.array([100.0, 100.0, 100.5, 101.0, 101.5, 102.0, 101.8, 101.0, 100.6])
    h, l = o + 0.3, o - 0.3
    ch = _chemin(o, h, l, o, s)
    T = len(o)
    # connus à l'ouverture de chaque bougie : un 1er creux à 99,8 (bougie 4), puis un creux à 101,2 (bougie 6)
    tv_l = [NAN, NAN, NAN, NAN, 99.8, 99.8, 101.2, 101.2, 101.2]
    tid_l = [0, 0, 0, 0, 1, 1, 2, 2, 2]
    suiv = (tv_l, tid_l, np.full(T, NAN), np.zeros(T, np.int64))
    exe, ne, ns, r, code, mfe = _un(ch, 0, 1.0, 99.0, NAN, 0.0, suiv)
    e = 100.0 * (1 + s)
    # bougie 4 : stop 99 -> 99,7 ; bougie 6 : -> 101,1 ; bougie 7 ouvre à 101,0 sous le stop : sortie à l'ouverture
    px = min(101.1, 101.0 * (1 - s)) * (1 - s)
    assert exe and ne == 1 and ns == 7 and code == JT.STOP
    assert r == pytest.approx((px - e) / (e - 99.0), abs=1e-12)
    assert mfe == pytest.approx((102.3 * (1 - s) - e) / (e - 99.0), abs=1e-12)
    # sans suiveur : le stop reste à 99, le trade va jusqu'à la fin des données
    exe, ne, ns, r, code, _ = _un(ch, 0, 1.0, 99.0, NAN, 0.0, suiv, suivre=False)
    assert exe and code == JT.FIN and ns == T - 1
    # un creux DÉJÀ connu à l'entrée ne compte pas : tid déjà à 1 à l'entrée -> seul le creux n° 2 fait monter le stop
    tid2 = [1, 1, 1, 1, 1, 1, 2, 2, 2]
    exe, ne, ns, r, code, _ = _un(ch, 0, 1.0, 99.0, NAN, 0.0, (tv_l, tid2, suiv[2], suiv[3]))
    assert ns == 7 and r == pytest.approx((px - e) / (e - 99.0), abs=1e-12)
    # un nouveau creux AU-DESSUS du prix d'ouverture ne déplace pas le stop (jamais au-delà du prix)
    tv3 = [NAN, NAN, NAN, NAN, 99.8, 99.8, 103.0, 103.0, 103.0]
    exe, ne, ns, r, code, _ = _un(ch, 0, 1.0, 99.0, NAN, 0.0, (tv3, tid_l, suiv[2], suiv[3]))
    assert code == JT.FIN                                         # stop resté à 99,7 : jamais touché
    # un nouveau creux plus BAS que le stop ne le fait pas reculer
    tv4 = [NAN, NAN, NAN, NAN, 99.8, 99.8, 99.5, 99.5, 99.5]
    exe, ne, ns, r, code, _ = _un(ch, 0, 1.0, 99.0, NAN, 0.0, (tv4, tid_l, suiv[2], suiv[3]))
    assert code == JT.FIN
    # destination absolue à 101,6 : touchée à la bougie 4 (101,8 x (1 - s) >= 101,6)
    exe, ne, ns, r, code, _ = _un(ch, 0, 1.0, 99.0, 101.6, 0.0, suiv)
    assert code == JT.DEST and ns == 4 and r == pytest.approx((101.6 - e) / (e - 99.0), abs=1e-12)


def test_stop_suiveur_vente_symetrique():
    """Sans frais, la vente sur le chemin retourné (200 - prix) donne exactement le même R que l'achat."""
    o = np.array([100.0, 100.0, 100.5, 101.0, 101.5, 102.0, 101.8, 101.0, 100.6])
    h, l = o + 0.3, o - 0.3
    T = len(o)
    tv = np.array([NAN, NAN, NAN, NAN, 99.8, 99.8, 101.2, 101.2, 101.2])
    tid = np.array([0, 0, 0, 0, 1, 1, 2, 2, 2])
    a = _un(_chemin(o, h, l, o, 0.0), 0, 1.0, 99.0, NAN, 0.0, (tv, tid, np.full(T, NAN), np.zeros(T, np.int64)))
    b = _un(_chemin(200 - o, 200 - l, 200 - h, 200 - o, 0.0), 0, -1.0, 101.0, NAN, 0.0,
            (np.full(T, NAN), np.zeros(T, np.int64), 200 - tv, tid))
    assert a[2] == b[2] and a[4] == b[4] == JT.STOP and a[3] == pytest.approx(b[3], abs=1e-12)


def test_sans_suiveur_identique_au_simulateur():
    rng = np.random.default_rng(3)
    T = 3000
    c = 100 * np.exp(np.cumsum(rng.normal(0, 0.002, T)))
    o = np.r_[100.0, c[:-1]]
    h = np.maximum(o, c) * (1 + np.abs(rng.normal(0, 0.001, T)))
    l = np.minimum(o, c) * (1 - np.abs(rng.normal(0, 0.001, T)))
    derniere = rng.random(T) < 0.01
    ch = (o, h, l, c, np.full(T, 1.3), np.ones(T, bool), derniere, np.full(T, 2e-4), np.full(T, 0.03),
          np.full(T, -0.01), (rng.random(T) < 0.05).astype(float))
    vides = (np.full(T, NAN), np.zeros(T, np.int64), np.full(T, NAN), np.zeros(T, np.int64))
    n_exe = 0
    for _ in range(300):
        t = int(rng.integers(0, T - 50))
        sens = 1.0 if rng.random() < 0.5 else -1.0
        stop = c[t] * (1 - sens * rng.uniform(0.002, 0.02))
        for dest, dr in ((NAN, 2.0), (c[t] * (1 + sens * 0.01), 0.0)):
            a = JT.un_trade(*ch, t, sens, False, NAN, stop, dest, dr, 0.0, 0.0, 1, 200, 1.0)
            b = _un(ch, t, sens, stop, dest, dr, vides, suivre=False, horizon=200)
            assert a[0] == b[0] and a[1] == b[1] and a[2] == b[2] and a[4] == b[4]
            if a[0]:
                n_exe += 1
                assert a[3] == pytest.approx(b[3], abs=1e-12)
    assert n_exe > 300


# ================================================================================================ sans futur
def _x(t15, q, s):
    x = {"t15": t15, "o": q["open"].to_numpy(float), "h": q["high"].to_numpy(float), "l": q["low"].to_numpy(float),
         "c": q["close"].to_numpy(float), "A": s["A"], "demi": np.full(len(t15), 3e-5)}
    for u in UNITES_15:
        x[u] = {k: v for k, v in s[u].items() if k not in ("ne", "fin", "debut_u")}
    return x


def _calc(q):
    t15 = q["time"].values.astype("datetime64[ns]").astype(np.int64)
    s = S.calculer(t15, *(q[k].to_numpy(float) for k in ("open", "high", "low", "close")), None, UNITES_15,
                   R().yeux.zones_par_cote, q)
    return _x(t15, q, s)


@pytest.fixture(scope="module")
def invente():
    m = chemin_minutes(300, 33, depart="2019-01-07", pas=0.0002)
    q = D.reechantillonner(m, "15min")
    return q, _calc(q)


def test_suiveur_tendance_compression_sans_futur(invente):
    q, x = invente
    T = len(q)
    rng = np.random.default_rng(1)
    for r in np.sort(rng.choice(np.arange(T // 2, T - 10), 4, replace=False)):
        xc = _calc(q.iloc[:r + 1].reset_index(drop=True))
        rr = np.array([r])
        for u in MV.SUIVEURS:
            a, b = MV.suiveur_lignes(x, u, rr), MV.suiveur_lignes(xc, u, rr)
            for va, vb in zip(a, b):
                assert np.array_equal(va, vb, equal_nan=True), (r, u)
        assert np.array_equal(MV.tendance_unites(x, rr), MV.tendance_unites(xc, rr))
        assert np.allclose(MV.compression(x, rr), MV.compression(xc, rr), equal_nan=True)


def test_rebonds_cassures_et_stops_sans_futur(invente):
    q, x = invente
    T = len(q)
    ev = MV.evenements_marche(x)
    assert (ev["genre"] == 1).sum() > 30 and (ev["genre"] == 2).sum() > 15
    assert (ev["j"] >= ev["k"]).all()
    geo = MV.geometries(x, ev)
    vus = 0
    for r in (int(T * 0.55), int(T * 0.8)):
        xc = _calc(q.iloc[:r + 1].reset_index(drop=True))
        evc = MV.evenements_marche(xc)
        gc = MV.geometries(xc, evc)
        cle = lambda e, i: (int(e["k"][i]), int(e["j"][i]), int(e["unite"][i]), int(e["genre"][i]), float(e["top"][i]))
        complet = {cle(ev, i) for i in range(len(ev["j"])) if ev["j"][i] <= r}
        coupe = {cle(evc, i) for i in range(len(evc["j"])) if evc["j"][i] <= r}
        assert complet == coupe
        for fam in geo:
            A_ = {cle(ev, i): (s_, st, d) for i, s_, st, d in zip(geo[fam]["idx"], geo[fam]["sens"], geo[fam]["stop"],
                                                                 geo[fam]["dest"]) if ev["j"][i] <= r}
            B_ = {cle(evc, i): (s_, st, d) for i, s_, st, d in zip(gc[fam]["idx"], gc[fam]["sens"], gc[fam]["stop"],
                                                                  gc[fam]["dest"]) if evc["j"][i] <= r}
            assert A_.keys() == B_.keys()
            for k in A_:
                assert A_[k][0] == B_[k][0] and A_[k][1] == pytest.approx(B_[k][1])
                assert (np.isnan(A_[k][2]) and np.isnan(B_[k][2])) or A_[k][2] == pytest.approx(B_[k][2])
            vus += len(A_)
    assert vus > 40
    # règles : stop du bon côté, risque entre 0,2 et 3 agitations ; rebond = sens de la zone, cassure = l'inverse
    A = np.asarray(x["A"])
    for fam, g in geo.items():
        j = ev["j"][g["idx"]].astype(int)
        rd = g["sens"] * (g["p"] - g["stop"])
        assert (rd >= MV.RISQUE_MIN_A * A[j] - 1e-12).all() and (rd <= MV.RISQUE_MAX_A * A[j] + 1e-12).all()
        side = ev["side"][g["idx"]]
        assert (g["sens"] == (side if fam.startswith("REB") else -side)).all()
        ok = np.isfinite(g["dest"])
        assert (g["sens"][ok] * (g["dest"][ok] - g["p"][ok]) >= MV.DEST_MIN_R * rd[ok] - 1e-12).all()
    # la petite zone resserre (ou garde) le stop d'un rebond
    a, b = geo["REB-Z"], geo["REB-G"]
    commun = np.intersect1d(a["idx"], b["idx"])
    sa = dict(zip(a["idx"], a["stop"] * a["sens"]))
    sb = dict(zip(b["idx"], b["stop"] * b["sens"]))
    assert all(sb[i] >= sa[i] - 1e-12 for i in commun) and any(sb[i] > sa[i] + 1e-12 for i in commun)


# ================================================================================================ à la main
def test_rebond_cassure_zone_morte_a_la_main():
    lig = np.arange(8)
    un = lambda c, fin, side=1: MV.evenements(np.asarray(c, float), lig, np.array([fin]), np.array([10.0]),
                                              np.array([9.0]), np.array([side]), np.array([2]), 96)
    g, d = un([10.5, 10.2, 9.8, 9.5, 10.3, 10.6, 10.6, 10.6], 100)
    assert g[0] == 1 and d[0] == 4                               # rebond : 1re clôture au-dessus du haut
    g, d = un([10.5, 10.2, 9.8, 8.9, 10.3, 10.6, 10.6, 10.6], 100)
    assert g[0] == 2 and d[0] == 3                               # cassure : clôture sous le bas
    g, d = un([10.5, 10.2, 9.8, 9.5, 10.3, 10.6, 10.6, 10.6], 3)
    assert g[0] == 0                                             # morte à la clôture de la ligne 3 : rien
    g, d = un([8.5, 8.8, 9.2, 9.5, 8.7, 8.6, 8.6, 8.6], 100, side=-1)
    assert g[0] == 1 and d[0] == 4                               # offre : rebond = clôture sous le bas
    g, d = un([8.5, 8.8, 10.4, 9.5, 8.7, 8.6, 8.6, 8.6], 100, side=-1)
    assert g[0] == 2 and d[0] == 2


def test_courses_a_la_main():
    f = lambda h, l, fin=10, hor=480: MV.courses(np.asarray(h, float), np.asarray(l, float), np.array([0]),
                                                 np.array([100.0]), np.array([fin]), np.array([1.0]), 0.5, 2.0, 3.0, hor)
    h = [100.2, 100.6, 101.5, 102.1, 101.5, 101.0]
    l = [99.9, 100.1, 100.3, 101.0, 99.9, 99.0]
    s, t, r = f(h, l)
    assert s[0] == 1 and t[0] == 1 and list(r[0]) == [1, 0]      # 2 A atteint (bougie 3), retour avant 3 A
    s, t, r = f([100.2, 100.6], [99.9, 99.4])                    # la bougie 1 touche +0,5 et -0,5 : ignorée
    assert t[0] == -1
    s, t, r = f([100.2, 100.6, 102.5], [99.9, 100.1, 99.8])      # objectif et retour dans la même bougie = retour
    assert list(r[0]) == [0, 0]
    s, t, r = f([100.2, 100.6, 101.0, 101.0], [99.9, 100.1, 100.5, 100.5], hor=2)
    assert list(r[0]) == [-1, -1]                                # rien dans l'horizon : non résolu
    s, t, r = f([100.2, 100.3, 100.6], [99.9, 99.8, 99.6], fin=2)
    assert t[0] == -1                                            # le seuil doit venir avant la fin de la journée
    s, t, r = f([100.2, 100.3, 99.9], [99.9, 99.4, 97.0])
    assert s[0] == -1 and t[0] == 1 and list(r[0]) == [1, 1]     # baisse : -3 A atteint dans la bougie suivante


def test_trader_parfait_a_la_main():
    s = 1e-4
    o = np.array([100.0, 100.2, 100.8, 101.5, 101.2, 101.6])
    h = np.array([100.3, 100.9, 101.2, 102.0, 101.6, 101.8])
    l = np.array([99.8, 100.1, 100.6, 101.2, 100.9, 101.3])
    c = np.array([100.2, 100.8, 101.5, 101.2, 101.6, 101.7])
    A, demi = np.ones(6), np.full(6, s)
    z = np.zeros(6, np.int64)
    nan6 = np.full(6, NAN)
    f = lambda tv, tid, ll: MV.parfait(o, h, ll, c, np.array([0]), np.array([6]), A, demi, 0.25, tv, tid, nan6, z, 1.0)
    # hausse, M = 2, entrée à 100,5 (bougie 1), stop 99,9 jamais touché : sortie à la dernière clôture
    cap = f(nan6, z, l)
    assert cap[0] == pytest.approx(101.7 * (1 - s) - 100.5 * (1 + s), abs=1e-12)
    # un nouveau creux à 100,7 connu à l'ouverture de la bougie 3 : stop 100,6 ; la bougie 4 descend à 100,5
    l2 = l.copy()
    l2[4] = 100.5
    cap = f(np.array([NAN, NAN, NAN, 100.7, 100.7, 100.7]), np.array([0, 0, 0, 1, 1, 1]), l2)
    assert cap[0] == pytest.approx(100.6 * (1 - s) - 100.5 * (1 + s), abs=1e-12)


def test_petite_zone_a_la_main():
    T = 6
    knn = np.full((T, 2, 2), -1, np.int64)
    knn[:, 0, 0] = 0                                              # une petite zone de demande [9,4 ; 9,7]
    tl = S.table_min(np.array([10.2, 9.8, 9.5, 9.6, 10.1, 10.3]))
    th = S.table_min(-np.full(T, 11.0))
    f = lambda tou, tl_=tl: MV.petites(np.array([4]), np.array([1]), np.array([1]), np.array([10.0]), np.array([9.0]),
                                       np.arange(T), knn, np.array([9.7]), np.array([9.4]), np.array([0]),
                                       np.array([tou]), tl_, th, np.array([NAN]))
    assert f(2)[0] == pytest.approx(9.4)                          # touchée et respectée (plus bas 9,5 > 9,4)
    assert np.isnan(f(5)[0])                                      # touchée après la décision : non
    tl2 = S.table_min(np.array([10.2, 9.8, 9.3, 9.6, 10.1, 10.3]))
    assert np.isnan(f(2, tl2)[0])                                 # le prix est passé sous son bas : non respectée


def test_liste_figee_et_seuil():
    assert len(MV.VARIANTES) == 12 and len({MV.vid(v) for v in MV.VARIANTES}) == 12
    assert MV.N_CONT == 2 * 4 * (4 * 4 + 1) + 4 and MV.N_TRADES == 48
    assert MV.N_TOTAL == 65 + 140 + 48 + 2
    assert MV.SEUIL == max(3.0, math.sqrt(2 * math.log(MV.N_TOTAL))) and MV.SEUIL > 3.3
    assert MV.PERIODES["choix"][1] == MV.PERIODES["verification"][0] == "2022-01-01"
    assert MV.PERIODES["verification"][1] == MV.PERIODES["controle"][0] and MV.PERIODES["controle"][1] <= "2025-10-01"
