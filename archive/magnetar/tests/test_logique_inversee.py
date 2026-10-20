"""Tests de la LOGIQUE INVERSÉE (collapsar/regarder/pistes/logique_inversee.py) :
- un trade calculé à la main : au marché, ordre limite, objectif 2R, sortie au temps, sortie trop proche ;
- SANS FUTUR : le placement (entrée, stop) à la ligne r est le même que les données s'arrêtent à r ou bien après ;
- règles du placement : stop derrière une vraie structure, à 0,25 - 2 agitations ; ordre limite sur le bord d'une zone ;
- déclencheurs : décision à / après le signal (jamais avant), retard d'1 h au plus, heure de sortie ;
- un seul trade à la fois ; compte FTMO (réussi / mort) calculé à la main ; liste figée et seuil.
Depuis Test_IA : $env:CUDA_VISIBLE_DEVICES='-1'; venv_gpu\\Scripts\\python.exe -m pytest collapsar/tests/test_logique_inversee.py -q
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from collapsar.ecole.precision import direction as DI
from collapsar.ecole.precision import juge_trade as JT
from collapsar.ecole.precision import structure as S
from collapsar.ecole.precision.reglages import UNITES_15, R
from collapsar.regarder.pistes import logique_inversee as LI
from test_ecole_precision import chemin_minutes
from collapsar.ecole.precision import donnees as D

MIN = 60 * 10 ** 9


def _chemin(o, h, l, c, demi=1e-4):
    T = len(o)
    a = lambda x: np.asarray(x, float)
    return (a(o), a(h), a(l), a(c), np.ones(T), np.ones(T, bool), np.zeros(T, bool), np.full(T, demi),
            np.zeros(T), np.zeros(T), np.zeros(T))


def _un(ch, t, sens, limite, P, stop, dest_r, t_sortie):
    a = lambda v, dt=float: np.asarray([v], dt)
    exe, ne, ns, r, code = LI.jouer(*ch, a(t, np.int64), a(sens), a(limite, bool), a(P), a(stop), a(dest_r),
                                    a(t_sortie, np.int64), LI.VALIDITE, 1.0)
    return exe[0], ne[0], ns[0], r[0], code[0]


# ================================================================================================ un trade à la main
def test_un_trade_calcule_a_la_main():
    s = 1e-4
    o = np.array([100.0, 100.0, 100.5, 101.0, 101.2, 101.0])
    h, l = o + 0.3, o - 0.3
    ch = _chemin(o, h, l, o, s)
    # achat au marché décidé à la clôture de la bougie 0 : entrée 100 x (1 + s), stop 99, objectif 2R jamais touché,
    # sortie au temps à l'ouverture de la bougie 4 (101,2 x (1 - s))
    exe, ne, ns, r, code = _un(ch, 0, 1.0, False, np.nan, 99.0, 2.0, 4)
    e = 100 * (1 + s)
    assert exe and ne == 1 and ns == 4 and code == JT.HORIZON_C
    assert r == pytest.approx((101.2 * (1 - s) - e) / (e - 99.0), abs=1e-12)
    # même trade, la bougie 3 monte à 102,5 : objectif 2R (100,01 + 2 x 1,01 = 102,03) touché, R = 2 exactement
    h2 = h.copy()
    h2[3] = 102.5
    exe, ne, ns, r, code = _un(_chemin(o, h2, l, o, s), 0, 1.0, False, np.nan, 99.0, 2.0, 4)
    assert exe and ns == 3 and code == JT.DEST and r == pytest.approx(2.0, abs=1e-12)
    # 3R : 100,01 + 3 x 1,01 = 103,04 pas touché -> sortie au temps
    exe, ne, ns, r, code = _un(_chemin(o, h2, l, o, s), 0, 1.0, False, np.nan, 99.0, 3.0, 4)
    assert ns == 4 and code == JT.HORIZON_C
    # ordre limite d'achat à 99,9 rempli à la bougie 1 (99,7 x (1 + s) < 99,9), stop 99, sortie au temps bougie 4
    exe, ne, ns, r, code = _un(ch, 0, 1.0, True, 99.9, 99.0, 2.0, 4)
    assert exe and ne == 1 and ns == 4 and code == JT.HORIZON_C
    assert r == pytest.approx((101.2 * (1 - s) - 99.9) / 0.9, abs=1e-12)
    # vente au marché : entrée 100 x (1 - s), stop 101,5 ; sortie au temps à l'ouverture de 4 (101,2 x (1 + s))
    exe, ne, ns, r, code = _un(ch, 0, -1.0, False, np.nan, 101.5, 2.0, 4)
    ev = 100 * (1 - s)
    assert exe and code == JT.HORIZON_C and r == pytest.approx((ev - 101.2 * (1 + s)) / (101.5 - ev), abs=1e-12)
    # stop touché dès la bougie d'entrée (bas 99,7 x (1 - s) <= 99,75) : sortie au stop moins un glissement d'un demi-frais
    exe, ne, ns, r, code = _un(ch, 0, 1.0, False, np.nan, 99.75, 2.0, 5)
    px = min(99.75, 100.0 * (1 - s)) * (1 - s)
    assert exe and ns == 1 and code == JT.STOP and r == pytest.approx((px - e) / (e - 99.75), abs=1e-12)
    # sortie au temps trop proche : pas de trade
    exe, *_ = _un(ch, 0, 1.0, False, np.nan, 99.0, 2.0, 1)
    assert not exe


def test_ordre_limite_vit_jusqu_a_la_sortie_au_temps():
    s = 1e-4
    o = np.array([100.0, 100.0, 100.0, 100.0, 99.0, 99.0, 99.0])
    h, l = o + 0.2, o - 0.2
    ch = _chemin(o, h, l, o, s)
    # l'ordre à 99,5 ne pourrait passer qu'à la bougie 4 : la sortie au temps est à 4 -> il expire à la bougie 3
    exe, ne, ns, r, code = _un(ch, 0, 1.0, True, 99.5, 98.0, 2.0, 4)
    assert not exe and code == JT.EXPIRE and ns == 3
    exe, ne, ns, r, code = _un(ch, 0, 1.0, True, 99.5, 98.0, 2.0, 6)
    assert exe and ne == 4 and ns == 6 and code == JT.HORIZON_C


# ================================================================================================ la structure
def _x(t15, s, demi=3e-5):
    x = {"t15": t15, "c": s["c"], "A": s["A"], "demi": np.full(len(t15), demi)}
    for u in UNITES_15:
        x[u] = {k: v for k, v in s[u].items() if k not in ("ne", "fin", "debut_u")}
    return x


@pytest.fixture(scope="module")
def invente():
    m = chemin_minutes(150, 21, depart="2019-01-07", pas=0.0002)
    q = D.reechantillonner(m, "15min")
    t15 = q["time"].values.astype("datetime64[ns]").astype(np.int64)
    arr = lambda qq: (qq[k].to_numpy(float) for k in ("open", "high", "low", "close"))
    s = S.calculer(t15, *arr(q), None, UNITES_15, R().yeux.zones_par_cote, q)
    return q, t15, arr, _x(t15, s)


def test_placement_sans_futur(invente):
    q, t15, arr, x = invente
    rng = np.random.default_rng(5)
    lignes = np.sort(rng.choice(np.arange(len(t15) // 2, len(t15) - 400), 5, replace=False))
    trouves = 0
    for r in lignes:
        qq = q.iloc[:r + 1].reset_index(drop=True)
        sc = S.calculer(t15[:r + 1], *arr(qq), None, UNITES_15, R().yeux.zones_par_cote, qq)
        xc = _x(t15[:r + 1], sc)
        for sens in (1, -1):
            for pl in LI.PLACEMENTS:
                a, b = LI.placer(x, int(r), sens, pl), LI.placer(xc, int(r), sens, pl)
                assert a == b, (r, sens, pl, a, b)
                trouves += a is not None
    assert trouves >= 10


def test_regles_du_placement(invente):
    q, t15, arr, x = invente
    vus = {p: 0 for p in LI.PLACEMENTS}
    for r in range(len(t15) // 3, len(t15) - 10, 23):
        p, A = float(x["c"][r]), float(x["A"][r])
        for sens in (1, -1):
            for pl in LI.PLACEMENTS:
                g = LI.placer(x, r, sens, pl)
                if g is None:
                    continue
                vus[pl] += 1
                lim, P, st = g
                e = P if lim else p
                lvl = st + sens * LI.MARGE_A * A                          # la structure elle-même
                rd = sens * (e - st)
                assert LI.STOP_MIN_A * A - 1e-9 <= sens * (e - lvl) and rd <= LI.STOP_MAX_A * A + 1e-9
                z = LI.zones_cote(x, r, 0 if sens > 0 else 1)
                if pl == "MS":
                    assert not lim and any(abs(v - lvl) < 1e-9 for v in LI.sommets_cote(x, r, sens))
                elif pl == "MZ":
                    assert not lim and any(abs((b if sens > 0 else t) - lvl) < 1e-6 for t, b in z)
                else:
                    assert lim and 0 < sens * (p - P) <= LI.N_LIMITE_A * A + 1e-9
                    assert any(abs((t if sens > 0 else b) - P) < 1e-6 and abs((b if sens > 0 else t) - lvl) < 1e-6
                               for t, b in z)
    assert min(vus.values()) > 20, vus


# ================================================================================================ déclencheurs
def _t15(jours=10):
    t = pd.Timestamp("2023-03-05 20:00").value + np.arange(jours * 96) * 15 * MIN  # un dimanche soir (serveur)
    return t[(t < pd.Timestamp("2023-03-08 10:00").value) | (t >= pd.Timestamp("2023-03-08 13:00").value)]   # trou de 3 h


def test_declencheur_c2(monkeypatch):
    t15 = _t15()
    deb = np.array([pd.Timestamp(s).value for s in ("2023-03-06 05:00", "2023-03-07 22:00", "2023-03-08 11:00",
                                                     "2023-03-08 12:00", "2023-03-09 03:00")])
    monkeypatch.setattr(DI, "_c2", lambda nom: (deb, deb + HEURE, np.array([1, -1, 1, 1, -1], np.int8)))
    r, s, sortie = LI.declencheurs("C2", "BTCUSDT", t15, pd.Timestamp("2023-01-01").value, pd.Timestamp("2024-01-01").value)
    dec = t15[r] + 15 * MIN
    # 11h dans le trou (décision à 13h15 : plus d'1 h de retard) -> ignoré ; 12h -> décision 13h15 (1 h 15) -> ignoré
    assert list(dec) == [deb[0], deb[1], deb[4]] and list(s) == [1, -1, -1]
    assert list(sortie) == [pd.Timestamp(d).value for d in ("2023-03-06 23:45", "2023-03-07 23:45", "2023-03-09 23:45")]


HEURE = 3600 * 10 ** 9


def test_declencheur_c1_jamais_avant_le_signal(monkeypatch):
    from collapsar.ecole.precision import foule as FO
    t15 = pd.Timestamp("2023-03-01").value + np.arange(60 * 96) * 15 * MIN     # passe le changement d'heure de mars
    deb = pd.Timestamp("2023-03-02 07:00").value + np.arange(40) * 26 * HEURE + 7 * MIN
    monkeypatch.setattr(DI, "_c1", lambda nom: (deb, deb + 24 * HEURE, np.where(np.arange(40) % 2, 1, -1).astype(np.int8)))
    r, s, sortie = LI.declencheurs("C1", "BTCUSDT", t15, pd.Timestamp("2023-01-01").value, pd.Timestamp("2024-01-01").value)
    dec = t15[r] + 15 * MIN
    utc = FO.serveur_vers_utc_ns(pd.DatetimeIndex(dec.astype("datetime64[ns]")))
    utc_avant = FO.serveur_vers_utc_ns(pd.DatetimeIndex((dec - 15 * MIN).astype("datetime64[ns]")))
    assert len(r) == 40 and (utc >= deb).all() and (utc_avant < deb).all() and (utc - deb <= 15 * MIN).all()
    assert (sortie == dec + 24 * HEURE).all()


def test_declencheur_tendance(monkeypatch):
    t15 = _t15()
    vu = []

    def tend(nom, t):
        vu.append(np.asarray(t))
        s = np.tile(np.array([1, 1, 1], np.int8), (len(t), 1))
        s[1] = [1, -1, 1]                                                  # pas d'accord le 2e jour
        s[2] = [-1, -1, -1]
        return s, np.zeros(s.shape, np.float32)
    monkeypatch.setattr(DI, "tendance", tend)
    r, s, sortie = LI.declencheurs("T", "BTCUSDT", t15, pd.Timestamp("2023-03-06").value, pd.Timestamp("2023-03-10").value)
    dec = t15[r] + 15 * MIN
    assert list(dec) == [pd.Timestamp(d).value for d in ("2023-03-06", "2023-03-08", "2023-03-09")]
    assert list(s) == [1, -1, 1] and (sortie == dec + 24 * HEURE).all()
    assert all((v % LI.JOUR_NS == 0).all() for v in vu)                     # la tendance est lue à 00h00 pile


# ================================================================================================ un à la fois, compte
def test_un_seul_trade_a_la_fois():
    t = np.array([10, 20, 30, 45, 60, 70])
    exe = np.array([True, True, False, True, True, True])
    ns = np.array([25, 40, 40, 50, 70, 80])
    code = np.array([JT.STOP, JT.HORIZON_C, JT.REFUS, JT.DEST, JT.HORIZON_C, JT.STOP])
    g = LI.garder_un_a_la_fois(t, exe, ns, code)
    # 20 : pendant le 1er (sorti au stop à 25) -> ignoré ; 30 : libre ; refusé -> ne bloque pas ; 45 : libre ;
    # 60 : sorti au temps à l'ouverture de 70 -> 70 peut entrer à l'ouverture de 71 >= 70
    assert list(g) == [True, False, True, True, True, True]


def test_compte_ftmo_a_la_main():
    j = LI.JOUR_NS
    d0 = pd.Timestamp("2024-01-01").value
    # 8 trades gagnants de 2R à 0,5 % (+1 % chacun), un par jour : le départ du 1er jour réussit au 10e... ici 8 % seulement
    e = d0 + np.arange(12) * j + 2 * HEURE
    s = e + 5 * HEURE
    rr = np.array([2.0] * 8 + [-1.0] * 4)
    c = LI.compte(e, s, rr, 0.5, d0, d0 + 20 * j)
    assert c["gain_total_pct"] == pytest.approx(8 * 1.0 - 4 * 0.5)
    assert c["baisse_max_pct"] == pytest.approx(2.0)
    assert c["reussis"] == 0 and c["morts"] == 0 and c["positions_simultanees_max"] == 1
    # risque 1,25 % : 4 trades à +2,5 % = +10 % -> réussi le 4e jour ; les départs suivants ne le sont pas
    c = LI.compte(e, s, rr, 1.25, d0, d0 + 20 * j)
    assert c["reussis"] == 1 and c["jours_median_termine"] == pytest.approx(3 + 7 / 24)
    # une journée à -6 % : mort par le mur du jour
    e2 = d0 + np.array([0, 1, 2]) * HEURE + 3 * HEURE
    c = LI.compte(e2, e2 + HEURE, np.array([-1.0, -1.0, -1.0]), 2.0, d0, d0 + 2 * j)
    assert c["morts"] == 1


def test_liste_figee_et_seuil():
    assert len(LI.VARIANTES) == 12 and len(LI.TEMOINS) == 6
    assert LI.N_TOTAL == 43 + 12 + 6 + 4
    assert LI.SEUIL == max(3.0, math.sqrt(2 * math.log(LI.N_TOTAL))) == 3.0
    assert all(v[0] in ("C1", "C2") for v in LI.VARIANTES) and all(v[0] == "T" for v in LI.TEMOINS)
    assert LI.PERIODES["controle"][1] <= "2025-10-01" and LI.PERIODES["selection"][1] == LI.PERIODES["controle"][0]
