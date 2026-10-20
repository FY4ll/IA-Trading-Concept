"""Tests des TROIS CHANGEMENTS de MAGNETAR (19/10/2026) :
1. YEUX DE LA TENDANCE DE FOND (ecole/precision/tendance.py) : sans futur (calcul coupé = calcul complet, jour en cours
   jamais regardé), exactement inversée sur le marché retourné, définitions simples ; greffe à zéro sur une branche :
   MÊME partie que l'ancien cerveau, elle voit bien des valeurs, l'apprentissage passe ;
2. STOP SUIVEUR APRÈS +1R (suiveur.py, simulateur.py) : trades calculés à la main (creux confirmés et agitation, achat
   et vente, ordre limite dont la bougie d'exécution ne compte pas), rien ne bouge avant +1R ; greffe de la tête : anciens
   gestes identiques (un regard à graine égale ; partie entière avec le tirage du suiveur neutralisé), penchant calibré,
   examen qui rapporte l'usage ;
3. EXAMEN TOURNANT (tournant.py) : réservoir fixé et vérifié, blocs + marges jamais appris (départs permis), mêmes
   fenêtres pour toutes les branches, incertitude par bloc, passage d'un arbre (notes mises de côté), deux générations
   d'un petit arbre ; HYPERNOVA et MAGNETAR (règles d'avant) : empreintes identiques.
Depuis Test_IA : $env:CUDA_VISIBLE_DEVICES='-1'; venv_gpu\\Scripts\\python.exe -m pytest collapsar/tests/test_trois_changements.py -q
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest
import torch

from collapsar.donnees.marches import RACINE
from collapsar.ecole.precision import simulateur as SIM
from collapsar.ecole.precision import suiveur as SV
from collapsar.ecole.precision import tendance as TD
from collapsar.ecole.precision.reglages import R
from collapsar.mains.simulateur import CAPITAL

from test_ecole_precision import monde_invente, petite_ecole, univers_minimal  # noqa: F401  (fixtures partagées)

NAN = np.nan
MIN = 60 * 10 ** 9


# ================================================================================================ 1. tendance de fond
def _quinze(jours=420, graine=3, derive=0.0):
    rng = np.random.default_rng(graine)
    t15 = pd.Timestamp("2019-01-01").value + np.arange(jours * 96) * 15 * MIN
    c = 100 * np.exp(np.cumsum(rng.normal(derive, 0.002, len(t15))))
    o = np.r_[100.0, c[:-1]]
    h = np.maximum(o, c) * (1 + np.abs(rng.normal(0, 5e-4, len(t15))))
    l = np.minimum(o, c) * (1 - np.abs(rng.normal(0, 5e-4, len(t15))))
    return t15, o, h, l, c


def test_tendance_noms_et_sans_futur():
    assert TD.NTD == 12 == len(TD.NOMS)
    t15, o, h, l, c = _quinze()
    J = TD.jours_ohlc(t15, h, l, c)
    t = pd.Timestamp("2019-09-10 13:45").value + np.arange(40) * 11 * 3600 * 10 ** 9
    x = TD.calcul(*J, t)
    assert np.abs(x).max() <= 4 and (x != 0).mean() > 0.5
    for i, ti in enumerate(t):
        coupe = t15 + 15 * MIN <= ti                                   # bougies closes à t
        xc = TD.calcul(*TD.jours_ohlc(t15[coupe], h[coupe], l[coupe], c[coupe]), t[i:i + 1])
        np.testing.assert_allclose(xc[0], x[i], atol=1e-6)
        jour = ti - ti % TD.JOUR_NS                                     # le jour en cours ne compte jamais
        c2, h2, l2 = c.copy(), h.copy(), l.copy()
        k = t15 >= jour
        c2[k] *= 1.3
        h2[k] *= 1.3
        l2[k] *= 0.7
        np.testing.assert_allclose(TD.calcul(*TD.jours_ohlc(t15, h2, l2, c2), t[i:i + 1])[0], x[i], atol=1e-6)


def test_tendance_inversee_sur_le_miroir():
    """Calcul direct sur le marché retourné (k / prix, comme donnees.retourner) = l'opposé exact du marché réel."""
    t15, o, h, l, c = _quinze(graine=8)
    k = c[0] ** 2
    t = pd.Timestamp("2019-07-01").value + np.arange(300) * 7 * 3600 * 10 ** 9
    x = TD.calcul(*TD.jours_ohlc(t15, h, l, c), t)
    xm = TD.calcul(*TD.jours_ohlc(t15, k / l, k / h, k / c), t)
    np.testing.assert_allclose(xm, TD.retourner(x), atol=1e-5)
    np.testing.assert_allclose(xm[:, :11], -x[:, :11], atol=1e-5)
    assert (np.abs(x[:, 11]) > 0.1).mean() > 0.5


def test_tendance_definitions_simples():
    jours = pd.Timestamp("2021-01-01").value + np.arange(200) * TD.JOUR_NS
    C = np.r_[np.linspace(100, 200, 150), np.linspace(200, 170, 50)]
    H, L = C * 1.01, C * 0.99
    x = TD.calcul(jours, H, L, C, np.array([jours[149] + TD.JOUR_NS + 5 * 3600 * 10 ** 9]))[0]
    assert list(x[:3]) == [1, 1, 1] and x[9] == 1 and x[10] == 1 and x[11] > 0.85     # haut de la fourchette
    # (clôture 1 % sous le plus haut du jour : position = 2 x log(C / L60) / log(H / L60) - 1)
    ln = np.log
    assert x[11] == pytest.approx(2 * (ln(C[149]) - ln(L[90:150].min())) / (ln(H[90:150].max()) - ln(L[90:150].min())) - 1,
                                  abs=1e-5)
    assert (x[3:6] > 0).all() and (x[6:9] > 0).all()
    x = TD.calcul(jours, H, L, C, np.array([jours[199] + 3600 * 10 ** 9]))[0]          # baisse depuis le jour 150
    assert list(x[:3]) == [-1, -1, 1] and x[9] == pytest.approx(-1 / 3) and x[10] == 0
    assert not TD.calcul(jours, H, L, C, np.array([jours[5]])).any()                    # pas assez d'histoire


@pytest.fixture
def tendance_allumee(monde_invente, monkeypatch):
    """La tendance allumée, calculée sur les jours du marché inventé (les vraies données ne sont pas lues)."""
    from collapsar.ecole.precision import donnees as D
    x = monde_invente
    monkeypatch.setattr(R().yeux, "tendance", True, raising=False)
    J = TD.jours_ohlc(x["t15"], x["h"], x["l"], x["c"])
    monkeypatch.setattr(TD, "_jours", lambda nom: J)
    return D


def _vieux(graine=4, **forme):
    from collapsar.ecole.precision import cerveau as C
    torch.manual_seed(graine)
    net = C.Cerveau(**forme)
    with torch.no_grad():                                    # des têtes « apprises » qui tradent souvent
        net.tetes.weight.normal_(0, 0.05)
        net.tetes.bias.normal_(0, 0.5)
        net.delai.weight.normal_(0, 0.05)
        net.tetes.bias[0] = -1.0
        if net.n_suiv:
            net.suiv.weight.normal_(0, 0.05)
            net.suiv.bias.normal_(0, 0.5)
    return net


def _partie(U, net, B=24, bougies=500, graine=1):
    from collapsar.ecole.precision import jeu as JEU
    tb = JEU.Table(U, B, 1)
    rng = np.random.default_rng(0)
    tb.demarrer(np.ones(B, bool), np.zeros((B, 1), np.int64), rng.integers(U.premier[0], U.T - bougies - 200, B))
    dec = JEU.Decideur(tb, net, evaluer=True, graphe=False)
    torch.manual_seed(graine)
    c = tb.cpt
    gestes, lps = [], []
    for _ in range(bougies):
        qui = np.flatnonzero(c.actif & ((c.t >= tb.prochain) | tb.reveil))
        if len(qui):
            (choix, lp, *_), _, paquet = dec(qui)
            gestes.append(choix["geste"][:len(qui)].clone())
            lps.append(lp[:len(qui)].clone())
            tb.appliquer(qui, JEU.niveaux_np(paquet[:, :len(qui)]))
        tb.avancer()
        c.actif &= ~(c.mort | c.reussi)
    return c.valeurs().copy(), torch.cat(gestes), torch.cat(lps), tb


def test_greffe_tendance_ne_change_aucune_decision(tendance_allumee):
    from collapsar.ecole.precision import cerveau as C
    from collapsar.ecole.precision import jeu as JEU
    from collapsar.ecole.precision.univers import Univers
    U = Univers([("EURUSD", False)], pd.Timestamp("2019-03-01"), pd.Timestamp("2019-09-01"), "cpu")
    assert U.tTEND.shape == (U.T, 1, TD.NTD) and float((U.tTEND != 0).float().mean()) > 0.5
    vieux = _vieux()
    neuf = C.cerveau_pour(TD.etat_avec_tendance(vieux.state_dict()))
    assert neuf.n_tendance == TD.NTD and neuf.F == vieux.F + TD.NTD
    assert C.forme(neuf.state_dict()) == {"journal": False, "tendance": True, "suiveur_1r": False}
    v0, g0, lp0, _ = _partie(U, vieux)
    v1, g1, lp1, _ = _partie(U, neuf)
    assert len(g0) > 1000 and (g0 > 0).sum() > 200
    assert torch.equal(g0, g1) and torch.equal(lp0, lp1) and np.array_equal(v0, v1)
    # elle VOIT la tendance (dernières colonnes de sa position) et apprend à s'en servir
    opt = torch.optim.AdamW(neuf.parameters(), lr=3e-4)
    lecon = JEU.Lecon(U, 16, np.random.default_rng(0))
    m, b = lecon.jouer(neuf, 64)
    assert m["pos"].shape[-1] == C.N_POS + TD.NTD and float((m["pos"][..., -TD.NTD:] != 0).float().mean()) > 0.05
    vu = U.tTEND[m["t"][:, None], m["cols"].clamp(min=0)] * (m["cols"] >= 0)[..., None]      # (places vides : 0)
    assert torch.equal(m["pos"][..., -TD.NTD:], vu)
    JEU.apprendre(neuf, opt, lecon.table, m, 1, 256, 0.2, 0.003)
    assert float(neuf.marche[0].weight[:, -TD.NTD:].abs().sum()) > 0
    # retour à un cerveau sans tendance (garde-fou) et l'inverse : bloc par bloc
    vieux.load_state_dict(C.adapter(neuf.state_dict(), vieux))
    neuf.load_state_dict(C.adapter(vieux.state_dict(), neuf))
    assert float(neuf.marche[0].weight[:, -TD.NTD:].abs().sum()) == 0
    # sans le réglage, un cerveau à la tendance refuse de jouer (pas de monde sans tendance)
    R().yeux.tendance = False
    U2 = Univers([("EURUSD", False)], pd.Timestamp("2019-03-01"), pd.Timestamp("2019-05-01"), "cpu")
    with pytest.raises(ValueError):
        _partie(U2, neuf, bougies=5)


def test_tendance_avec_journal_dans_l_ordre():
    """Journal ET tendance : yeux + position + journal (NJ) + tendance (NTD), dans cet ordre (adapter bloc par bloc)."""
    from collapsar.ecole.precision import cerveau as C
    from collapsar.ecole.precision import journal_trading as JN
    a = C.Cerveau(journal=True)
    b = C.Cerveau(journal=True, tendance=True)
    assert b.F == a.F + TD.NTD
    with torch.no_grad():
        a.marche[0].weight.normal_()
    e = C.adapter(a.state_dict(), b)["marche.0.weight"]
    assert torch.equal(e[:, :a.F], a.marche[0].weight) and not e[:, a.F:].any()
    c = C.Cerveau(tendance=True)
    e2 = C.adapter(b.state_dict() | {"marche.0.weight": e}, c)["marche.0.weight"]
    assert e2.shape[1] == c.F and torch.equal(e2[:, :a.F - JN.NJ], a.marche[0].weight[:, :a.F - JN.NJ])


# ================================================================================================ 2. suiveur après +1R
def _monde(o, h, l, c, sw_v, sw_id, demi=1e-4):
    T = len(o)
    U = univers_minimal(o, h, l, c, jour=np.zeros(T, np.int64), nuits=np.zeros(T), demi=demi, nuit_achat=0.0)
    U.sw_v, U.sw_id = sw_v, sw_id
    return U


def _swings(T, creux, n_creux, sommets=None, n_sommets=None):
    sw_v = np.full((T, 1, 1, 2), NAN)
    sw_id = np.zeros((T, 1, 1, 2), np.int64)
    sw_v[:, 0, 0, 0], sw_id[:, 0, 0, 0] = creux, n_creux
    if sommets is not None:
        sw_v[:, 0, 0, 1], sw_id[:, 0, 0, 1] = sommets, n_sommets
    return sw_v, sw_id


def _jouer(U, sens, stop, un_r=True, ag=0.0, marge=0.1, unites=1000.0, limite=None):
    cp = SIM.Comptes(U, 1, 1)
    cp.recommencer(np.array([True]), np.array([[0]]), np.array([0]))
    cp.ord_act[0, 0], cp.ord_u[0, 0], cp.ord_stop[0, 0] = SIM.MARCHE, sens * unites, stop
    if limite is not None:
        cp.ord_act[0, 0], cp.ord_prix[0, 0], cp.ord_duree[0, 0] = SIM.LIMITE, limite, 10
    cp.ord_tp1[0, 0], cp.ord_part[0, 0], cp.ord_dest[0, 0] = NAN, 0.0, NAN
    cp.ord_sv_u[0, 0], cp.ord_sv_tp1[0, 0], cp.ord_sv_m[0, 0] = 0, False, marge
    cp.ord_sv_1r[0, 0], cp.ord_sv_ag[0, 0] = un_r, ag
    stops, evts = [], []
    for _ in range(len(U.o) - 1):
        cp.pas(1.0)
        stops.append(cp.stop[0, 0])
        evts.append(cp.evt[0, 0])
        if cp.u[0, 0] == 0 and cp.att[0, 0] == 0:
            break
    return cp, stops, evts


def _chemin():
    o = np.array([100.0, 100.0, 100.5, 101.0, 101.5, 102.0, 101.8, 101.0, 100.6])
    return o, o + 0.3, o - 0.3, o.copy()


# creux 99,8 connu dès la clôture de la bougie 1 (le suiveur d'avant remonte le stop dès la bougie 2), 101,2 à la clôture
# de la bougie 5
CREUX = [NAN, 99.8, 99.8, 99.8, 99.8, 101.2, 101.2, 101.2, 101.2]
N_CREUX = [0, 1, 1, 1, 1, 2, 2, 2, 2]


def test_suiveur_apres_1r_a_la_main_creux_confirmes():
    """Achat au marché à 100 x (1 + s) = 100,01, stop 99 : 1R = 1,01. Meilleur prix de sortie (plus haut x (1 - s)) :
    100,29 (bougie 1), 100,79 (2), 101,29 (3) -> +1R atteint à l'ouverture de la bougie 4 (101,29 - 100,01 = 1,28).
    Le creux 99,8 (connu depuis la bougie 1) ne compte qu'à partir de là : stop 99 -> 99,7 à la bougie 4 (le suiveur
    d'avant l'aurait mis dès la bougie 2), 101,1 à la bougie 6 ; la bougie 7 ouvre à 101,0 sous le stop : sortie."""
    s = 1e-4
    o, h, l, c = _chemin()
    T = len(o)
    U = _monde(o, h, l, c, *_swings(T, CREUX, N_CREUX), s)
    e = 100.0 * (1 + s)
    cp, stops, evts = _jouer(U, 1.0, 99.0)
    assert cp.entree[0, 0] == pytest.approx(e) and cp.sv_r0[0, 0] == pytest.approx(e - 99.0)
    assert stops[:6] == pytest.approx([99.0, 99.0, 99.0, 99.7, 99.7, 101.1])
    assert [bool(x & SIM.SUIVI) for x in evts] == [False, False, False, True, False, True, False]
    px = min(101.1, 101.0 * (1 - s)) * (1 - s)
    assert evts[-1] & SIM.STOP and len(evts) == 7 and cp.sv_n[0, 0] == 2 and cp.sv_on[0, 0]
    assert cp.r_ferme[0, 0] == pytest.approx((px - e) / (e - 99.0), abs=1e-12)
    # le suiveur d'avant (sans +1R) : remonté dès la bougie 2
    cp0, stops0, _ = _jouer(U, 1.0, 99.0, un_r=False)
    assert stops0[:6] == pytest.approx([99.0, 99.7, 99.7, 99.7, 99.7, 101.1])
    # +1R jamais atteint (stop d'origine plus loin : 1R = 3,01) : le stop ne bouge JAMAIS, même avec des creux nouveaux
    cp2, stops2, _ = _jouer(U, 1.0, 97.0)
    assert set(stops2) == {97.0} and cp2.sv_n[0, 0] == 0 and not cp2.sv_on[0, 0]


def test_suiveur_apres_1r_a_la_main_agitation():
    """Variante par agitation (1,0 en prix) : après +1R (bougie 4), stop = meilleur prix de sortie - 1 : 100,2899
    (bougie 4), 100,7898 (5), 101,2898 (6) ; bougie 7 : ouverture 101,0 sous le stop -> sortie à l'ouverture."""
    s = 1e-4
    o, h, l, c = _chemin()
    T = len(o)
    U = _monde(o, h, l, c, *_swings(T, CREUX, N_CREUX), s)
    e = 100.0 * (1 + s)
    cp, stops, evts = _jouer(U, 1.0, 99.0, ag=1.0)
    haut = lambda k: max(h[1:k + 1]) * (1 - s)                       # meilleur prix de sortie jusqu'à la clôture de k
    assert stops[:6] == pytest.approx([99.0, 99.0, 99.0, haut(3) - 1, haut(4) - 1, haut(5) - 1])
    assert haut(3) - 1 == pytest.approx(100.28987, abs=1e-5)
    px = min(haut(5) - 1, 101.0 * (1 - s)) * (1 - s)
    assert evts[-1] & SIM.STOP and len(evts) == 7 and cp.sv_n[0, 0] == 3
    assert cp.r_ferme[0, 0] == pytest.approx((px - e) / (e - 99.0), abs=1e-12)
    assert cp.sv_dern[0, 0] == pytest.approx(haut(5) - 1)
    # vente symétrique sans frais (chemin retourné 200 - prix) : même R
    a, _, _ = _jouer(_monde(o, h, l, c, *_swings(T, CREUX, N_CREUX), 0.0), 1.0, 99.0, ag=1.0)
    sv, si = _swings(T, np.full(T, NAN), np.zeros(T, np.int64), 200 - np.asarray(CREUX), N_CREUX)
    b, _, _ = _jouer(_monde(200 - o, 200 - l, 200 - h, 200 - c, sv, si, 0.0), -1.0, 101.0, ag=1.0)
    assert a.r_ferme[0, 0] == pytest.approx(b.r_ferme[0, 0], abs=1e-12) and a.sv_n[0, 0] == b.sv_n[0, 0] == 3
    a, _, _ = _jouer(_monde(o, h, l, c, *_swings(T, CREUX, N_CREUX), 0.0), 1.0, 99.0)
    b, _, _ = _jouer(_monde(200 - o, 200 - l, 200 - h, 200 - c, sv, si, 0.0), -1.0, 101.0)
    assert a.r_ferme[0, 0] == pytest.approx(b.r_ferme[0, 0], abs=1e-12) and a.sv_n[0, 0] == b.sv_n[0, 0] == 2


def test_suiveur_apres_1r_ordre_limite():
    """Ordre limite d'achat à 99,95 exécuté à la bougie 1 (plus haut 101,2 : +1,24 au-dessus de l'entrée, mais la bougie
    d'exécution ne compte pas, on ne sait pas si le plus haut était avant) ; 1R = 0,95 ; +1R atteint par la bougie 3
    seulement (101,29) -> stop 99,7 à la bougie 4."""
    s = 1e-4
    o, h, l, c = _chemin()
    h = h.copy()
    h[1] = 101.2
    T = len(o)
    U = _monde(o, h, l, c, *_swings(T, CREUX, N_CREUX), s)
    cp, stops, evts = _jouer(U, 1.0, 99.0, limite=99.95)
    assert evts[0] & SIM.EXECUTE and cp.entree[0, 0] == pytest.approx(99.95) and cp.sv_r0[0, 0] == pytest.approx(0.95)
    assert stops[:4] == pytest.approx([99.0, 99.0, 99.0, 99.7])


def test_sans_option_1r_le_simulateur_ne_change_pas():
    """Positions sans option +1R : mêmes stops et même R que le suiveur d'avant, et sans suiveur rien ne bouge."""
    o, h, l, c = _chemin()
    T = len(o)
    U = _monde(o, h, l, c, *_swings(T, CREUX, N_CREUX))
    a, sa, _ = _jouer(U, 1.0, 99.0, un_r=False, ag=1.0)              # (agitation ignorée sans +1R)
    assert sa[:6] == pytest.approx([99.0, 99.7, 99.7, 99.7, 99.7, 101.1]) and not a.sv_1r[0, 0]


@pytest.fixture
def un_r_allume(monkeypatch):
    monkeypatch.setattr(R().mains, "suiveur", True, raising=False)
    monkeypatch.setattr(R().mains, "suiveur_unites", ["D1", "H4", "H1", "M15"], raising=False)
    monkeypatch.setattr(R().mains, "suiveur_depart_pct", 10.0, raising=False)
    monkeypatch.setattr(R().mains, "suiveur_1r", True, raising=False)
    monkeypatch.setattr(R().mains, "suiveur_1r_unites", ["H1", "H4"], raising=False)
    monkeypatch.setattr(R().mains, "suiveur_1r_agitations", [1.0], raising=False)


def test_options_1r(un_r_allume):
    assert SV.active_1r() and SV.n_options_1r() == 3
    assert [x[:2] for x in SV.options_1r()] == [(2, 0.0), (1, 0.0), (0, 1.0)]


def test_greffe_1r_anciens_gestes_identiques(monde_invente, un_r_allume, monkeypatch):
    from collapsar.ecole.precision import cerveau as C
    from collapsar.ecole.precision import jeu as JEU
    from collapsar.ecole.precision.univers import Univers
    U = Univers([("EURUSD", False)], pd.Timestamp("2019-03-01"), pd.Timestamp("2019-09-01"), "cpu")
    vieux = _vieux()
    neuf = C.Cerveau(suiveur_1r=True)
    neuf.load_state_dict(C.adapter(vieux.state_dict(), neuf))
    assert neuf.n_suiv1r == 3 and not neuf.suiv1r.weight.any()
    assert C.forme(neuf.state_dict())["suiveur_1r"] and not C.forme(vieux.state_dict())["suiveur_1r"]
    for k, v in vieux.state_dict().items():                                   # rien d'ancien ne bouge
        assert torch.equal(neuf.state_dict()[k], v), k
    # (1) un regard à graine égale, penchant fort : tous les autres choix et niveaux identiques
    with torch.no_grad():
        neuf.suiv1r.bias[:] = 3.0
    res = []
    for net in (vieux, neuf):
        tb = JEU.Table(U, 64, 1)
        tb.demarrer(np.ones(64, bool), np.zeros((64, 1), np.int64),
                    np.random.default_rng(1).integers(U.premier[0], U.T - 400, 64))
        torch.manual_seed(7)
        with torch.no_grad():
            res.append(tb.regarder(net, np.arange(64))[0])
    (c0, lp0, _, _, v0, l0), (c1, lp1, _, _, v1, l1) = res
    for k in c0:
        if k != "suiveur":
            assert torch.equal(c0[k], c1[k]), k
    for k in l0:
        if not k.startswith("suiveur"):
            assert torch.equal(torch.nan_to_num(l0[k].float(), nan=-7.0), torch.nan_to_num(l1[k].float(), nan=-7.0)), k
    assert torch.equal(v0, v1)
    ouvre = (c1["geste"] >= 1) & (c1["geste"] <= 4)
    assert float((c1["suiveur"][ouvre] >= neuf.n_suiv).float().mean()) > 0.5
    assert bool((l1["suiveur_1r"][ouvre & (c1["suiveur"] >= neuf.n_suiv)] == 1).all())
    ag = c1["suiveur"] == neuf.n_suiv + 2
    assert torch.allclose(l1["suiveur_ag"][ag & ouvre], tb.vue.structure(*[torch.as_tensor(x) for x in (
        tb.cpt.t[np.arange(64)], tb.cpt.col[np.arange(64)])])["A"][ag & ouvre].float())
    # (2) une partie entière, tirage du suiveur rendu sans hasard (meilleure ANCIENNE option) : identique
    tirer = C.Loi.tirer
    monkeypatch.setattr(C.Loi, "tirer", lambda self: self.logits[..., :vieux.n_suiv].argmax(-1)
                        if self.logits.shape[-1] in (vieux.n_suiv, vieux.n_suiv + 3) else tirer(self))
    v0, g0, lp0, _ = _partie(U, vieux)
    v1, g1, lp1, _ = _partie(U, neuf)
    assert torch.equal(g0, g1) and np.array_equal(v0, v1) and (g0 > 0).sum() > 200
    monkeypatch.setattr(C.Loi, "tirer", tirer)
    # (3) le penchant calibré : la part demandée des ouvertures
    b, p = SV.calibrer_1r(neuf, U, 70.0, n=256)
    assert abs(p - 70.0) < 8 and np.isfinite(b)


def test_examen_et_apprentissage_avec_1r(monde_invente, un_r_allume):
    from collapsar.ecole.precision import cerveau as C
    from collapsar.ecole.precision import jeu as JEU
    from collapsar.ecole.precision.univers import Univers
    U = Univers([("EURUSD", False)], pd.Timestamp("2019-03-01"), pd.Timestamp("2019-09-01"), "cpu")
    torch.manual_seed(0)
    net = C.Cerveau(suiveur_1r=True)
    with torch.no_grad():
        net.suiv1r.bias[:] = 4.0
    old = R().monde.challenge_jours
    R().monde.challenge_jours = 10
    R().selection.mesurer_tenue = True
    try:
        ex = JEU.Examen(U, [["EURUSD"]], pd.Timestamp("2019-06-01"), pd.Timestamp("2019-08-15"), 5)
        x = ex.jouer_un(net, 1)
    finally:
        R().monde.challenge_jours = old
        R().selection.mesurer_tenue = False
    for k in ("trades_3r_pct", "stop_remonte_tous_pct", "suiveur_1r_pct", "suiveur_1r_atteint_pct", "cotes"):
        assert k in x and k in x["jumeau"], k
    assert x["suiveur_1r_pct"] > 50 and x["suiveur_1r_atteint_pct"] >= 0
    assert x["cotes"]["achats"]["trades"] + x["cotes"]["ventes"]["trades"] == x["trades_r"]
    assert "après +1R" in x["suiveur_unite_pct"]
    opt = torch.optim.AdamW(net.parameters(), lr=3e-4)
    lecon = JEU.Lecon(U, 16, np.random.default_rng(0))
    m, _ = lecon.jouer(net, 64)
    JEU.apprendre(net, opt, lecon.table, m, 1, 256, 0.2, 0.003)
    assert net.suiv1r.weight.abs().sum() > 0


# ================================================================================================ 3. examen tournant
@pytest.fixture
def tournant(monde_invente, monkeypatch):
    """Examen tournant sur le marché inventé (2019) : tranches de 2 mois, blocs de 20 jours, marges de 3 jours."""
    from collapsar.ecole.precision import tournant as TN
    monkeypatch.setattr(R(), "examen_tournant", SimpleNamespace(
        graine=5, de="2019-03-01", jusqua="2019-08-01", tranche_mois=2, bloc_jours=20, marge_avant_jours=3,
        marge_apres_jours=3, blocs_par_generation=1, marches=["EURUSD"], appris_jusqua="2019-04-15"), raising=False)
    monkeypatch.setattr(R().monde, "challenge_jours", 20)
    return TN


def test_reservoir_fixe_et_blocs_jamais_appris(tournant):
    from collapsar.ecole.precision import jeu as JEU
    from collapsar.ecole.precision.univers import Univers
    TN = tournant
    b = TN.blocs()
    assert b == TN.fabriquer_blocs() and [x["debut"] for x in b] == ["2019-03-01", "2019-05-01"]
    assert all(pd.Timestamp(x["fin"]) - pd.Timestamp(x["debut"]) == pd.Timedelta(days=20) for x in b)
    U = Univers([("EURUSD", False)], pd.Timestamp("2019-02-15"), pd.Timestamp("2019-08-10"), "cpu")
    ok = TN.permis_depart(U)
    z = TN.zones_interdites()
    assert z[0, 0] == (pd.Timestamp("2019-03-01") - pd.Timedelta(days=3)).value
    fin = U.fin_challenge(np.arange(U.T))
    for t in np.flatnonzero(ok)[::50]:                     # tout le challenge d'un départ permis est hors des zones
        a, e = U.t_ns[t], U.t_ns[fin[t]]
        assert not ((a < z[:, 1]) & (e >= z[:, 0])).any()
    assert ok.sum() > 96 * 10 and (~ok).sum() > 96 * 40
    U.permis_depart = ok
    lecon = JEU.Lecon(U, 64, np.random.default_rng(0))
    for _ in range(3):
        cols, dep = lecon._tirer(200)
        assert ok[dep].all()


def test_examen_tournant_memes_fenetres_et_incertitude_par_bloc(tournant):
    from collapsar.ecole.precision import cerveau as C
    from collapsar.ecole.precision import jeu as JEU
    TN = tournant
    R().examen_tournant.blocs_par_generation = 2
    U, ex = TN.monde_examen_tournant("cpu")
    assert ex.n == 4 and list(ex.panier) == [0, 1, 0, 1] and list(ex.ids) == [0, 0, 1, 1]
    assert ex.tirage(7) == ex.tirage(7)
    x1 = ex.jouer_un(_vieux(1), 1)
    x2 = ex.jouer_un(_vieux(2), 1)
    assert x1["challenges"] == x2["challenges"] == 4 and x1["blocs"] == [0, 1]
    assert np.isfinite(x1["note_blocs_appris"]) and np.isfinite(x1["note_blocs_neufs"]) and x1["challenges_neufs"] == 2
    cp = JEU.comparer(x1, x2, ex.pas_jours, ex.groupes)
    d = np.asarray(x1["notes"]) - np.asarray(x2["notes"])
    m = np.array([d[:2].mean(), d[2:].mean()])
    assert cp["incertitude"] == pytest.approx(m.std(ddof=1) / np.sqrt(2))
    assert C.Cerveau().n_suiv == 0                                            # (HYPERNOVA : rien d'autre ne change)


def test_examen_tournant_parties_par_bloc_et_graine_par_generation(tournant, monkeypatch):
    """(19/10 soir) Plusieurs parties par bloc : mêmes fenêtres répétées sur d'autres comptes, incertitude toujours par
    bloc ; graine de l'examen changée à chaque génération (la même pour toutes les branches). Absent = comme avant."""
    from collapsar.ecole.precision import jeu as JEU
    TN = tournant
    R().examen_tournant.blocs_par_generation = 2
    U, ex1 = TN.monde_examen_tournant("cpu")
    ex3 = TN.ExamenTournant(U, TN.blocs(), 2, parties=3)
    assert ex1.parties == 1 and ex3.parties == 3 and ex3.n == 3 * ex1.n == 12
    assert list(ex3.ids) == [0] * 6 + [1] * 6 and list(ex3.panier) == [0, 1] * 6
    assert (ex3.dep[:6] == ex1.dep[0]).all() and (ex3.dep[6:] == ex1.dep[2]).all()
    a, b = _vieux(1), _vieux(2)
    x1 = ex1.jouer_un(a, 1)
    xa, xb = ex3.jouer_un(a, 1), ex3.jouer_un(b, 1)
    assert x1["graine_examen"] == xa["graine_examen"] == 1                    # réglage absent : graine inchangée
    assert xa["challenges"] == 12 and xa["blocs"] == [0, 1] and xa["parties_par_bloc"] == 3
    assert xa["challenges_neufs"] == x1["challenges_neufs"] == 2
    cp = JEU.comparer(xa, xb, ex3.pas_jours, ex3.groupes)
    d = np.asarray(xa["notes"]) - np.asarray(xb["notes"])
    m = np.array([d[:6].mean(), d[6:].mean()])
    assert cp["incertitude"] == pytest.approx(m.std(ddof=1) / np.sqrt(2))
    monkeypatch.setattr(R().examen_tournant, "graine_par_generation", True, raising=False)
    ex3.tirer(5)
    assert ex3.jouer_un(a, 1)["graine_examen"] == 1 + 7919 * 5 and ex3.jouer_un(b, 1)["graine_examen"] == 1 + 7919 * 5


def test_apprentissage_apparie_reel_et_retourne(monde_invente, monkeypatch):
    """(19/10 soir) Apprentissage apparié : moitié des comptes sur le réel, moitié sur le même marché retourné, aux
    MÊMES départs ; un (re)départ d'un côté est rejoué de l'autre par le prochain compte de ce côté."""
    from collapsar.ecole.precision import jeu as JEU
    from collapsar.ecole.precision.univers import Univers
    U = Univers([("EURUSD", False), ("EURUSD", True)], pd.Timestamp("2019-03-01"), pd.Timestamp("2019-09-01"), "cpu")
    monkeypatch.setattr(R().ecole, "marches_par_compte", [1, 1])
    monkeypatch.setattr(R().ecole, "apprentissage_apparie", True, raising=False)
    lecon = JEU.Lecon(U, 20, np.random.default_rng(3))
    c = lecon.table.cpt
    assert (c.col[:10, 0] == 0).all() and (c.col[10:, 0] == 1).all()          # réel / retourné, 10 et 10
    assert (lecon.table.dernier[:10] == lecon.table.dernier[10:]).all()        # mêmes départs
    assert lecon.apparie["attente"] == ([], [])
    cols, dep = lecon._tirer_comptes(np.array([0, 3]))                         # deux comptes réels redémarrent
    assert (cols[:, 0] == 0).all() and len(lecon.apparie["attente"][1]) == 2
    cols2, dep2 = lecon._tirer_comptes(np.array([12, 17]))                     # deux retournés : les mêmes départs
    assert (cols2[:, 0] == 1).all() and list(dep2) == list(dep) and lecon.apparie["attente"] == ([], [])
    m, b = lecon.jouer(_vieux(1), 48)                                          # une leçon se joue
    assert b["regards_par_jour"] > 0
    monkeypatch.setattr(R().ecole, "apprentissage_apparie", False)
    assert JEU.Lecon(U, 20, np.random.default_rng(3)).apparie is None           # réglage éteint : comme avant


def test_note_du_cote_le_moins_bon(tournant, monkeypatch):
    """(19/10 soir) note_cotes: moins_bon : note = la moins bonne des moyennes or réel / or retourné ; écarts entre
    branches mesurés bloc par bloc sur ce côté ; résultats séparés par côté ; murs du pire côté."""
    from collapsar.ecole.precision import jeu as JEU
    TN = tournant
    R().examen_tournant.blocs_par_generation = 2
    monkeypatch.setattr(R().selection, "mesurer_tenue", True, raising=False)
    U, ex = TN.monde_examen_tournant("cpu")
    a, b = _vieux(1), _vieux(2)
    x0 = ex.jouer_un(a, 1)
    assert "note_moyenne" not in x0 and set(x0["par_cote"]) == {"réel", "retourné"}       # réglage absent : moyenne
    monkeypatch.setattr(R().examen_tournant, "note_cotes", "moins_bon", raising=False)
    xa, xb = ex.jouer_un(a, 1), ex.jouer_un(b, 1)
    n = np.asarray(xa["notes"])
    assert xa["note_moyenne"] == pytest.approx(n.mean()) == pytest.approx(x0["note"])
    assert xa["note_reel"] == pytest.approx(n[ex.panier == 0].mean())
    assert xa["note"] == pytest.approx(min(xa["note_reel"], xa["note_retourne"]))
    assert xa["note"] == pytest.approx(np.mean(xa["notes_selection_blocs"]))
    cp = JEU.comparer(xa, xb, ex.pas_jours, ex.groupes)
    assert cp["ecart"] == pytest.approx(xa["note"] - xb["note"])
    assert xa["murs_pct_pire_cote"] >= xa["murs_pct"] - 1e-9
    assert "réel" in TN.texte_cotes(xa) and "retourné" in TN.texte_cotes(xa)


def test_passage_note_cotes(tmp_path, tournant, monkeypatch):
    from collapsar.arbre.jardinier import Arbre, Reglages
    TN = tournant
    d = tmp_path / "or"
    d.mkdir()
    a = Arbre(Reglages(places=2))
    for nom_t in ("x", "y"):
        b = a.naitre([], {"nom": nom_t})
        for s in (0.1, 0.2, 0.3):
            a.noter(b.nom, s)
    a.sauver(d / "arbre.json")
    (d / "journal_croissance.jsonl").write_text("", encoding="utf-8")
    assert TN.passer_note_cotes(d, lambda *_: None) is False                   # réglage absent : rien
    monkeypatch.setattr(R().examen_tournant, "note_cotes", "moins_bon", raising=False)
    assert TN.passer_note_cotes(d, lambda *_: None) is True
    a2 = Arbre.charger(d / "arbre.json")
    assert all(b.scores == [] and b.record is None for b in a2.vivantes())
    info = json.loads((d / TN.FICHIER_NOTE_COTES).read_text(encoding="utf-8"))
    assert len(info["notes_moyenne_avant"]["A"]) == 3
    assert TN.passer_note_cotes(d, lambda *_: None) is False                   # une seule fois


def test_passage_puis_deux_generations_d_un_petit_arbre(petite_ecole, tournant, monkeypatch, capsys):
    """Un petit arbre à l'examen fixe (1 génération), puis l'examen tournant (2 générations) : passage, mêmes blocs pour
    toutes les branches, niveaux mesurés sur l'examen tournant seulement, ligne de génération avec la tenue."""
    L, d = petite_ecole
    TN = tournant
    base = ["--dossier", str(d), "--appareil", "cpu", "--muet"]
    et = R().examen_tournant
    monkeypatch.setattr(R(), "examen_tournant", None)
    L.main(["--generations", "1"] + base)
    a0 = json.loads((d / "arbre.json").read_text(encoding="utf-8"))
    vivantes = [n for n, b in a0["branches"].items() if b["morte"] is None]
    assert all(len(a0["branches"][n]["scores"]) == 1 for n in vivantes)
    monkeypatch.setattr(R(), "examen_tournant", et)
    monkeypatch.setattr(R().selection, "mesurer_tenue", True, raising=False)
    L.main(["--generations", "3"] + base)
    lignes = [json.loads(x) for x in (d / "journal_croissance.jsonl").read_text(encoding="utf-8").splitlines()]
    gens = [x for x in lignes if x.get("quoi") == "generation"]
    assert [x["generation"] for x in gens] == [1, 2, 3] and "blocs_examen" not in gens[0]
    assert all(len(x["blocs_examen"]) == 1 for x in gens[1:])
    assert any(x.get("quoi") == "examen_tournant" for x in lignes) and (d / TN.FICHIER_BLOCS).exists()
    a = json.loads((d / "arbre.json").read_text(encoding="utf-8"))
    for n in vivantes:
        if a["branches"][n]["morte"] is None:
            assert len(a["branches"][n]["scores"]) == 2                     # notes de l'examen fixe mises de côté
    ex = json.loads((d / "derniers_examens.json").read_text(encoding="utf-8"))
    assert len({tuple(x["blocs"]) for x in ex.values()}) == 1              # mêmes blocs pour toutes les branches
    assert "stop remonté" in capsys.readouterr().out


def test_passage_d_un_arbre(tmp_path, tournant):
    from collapsar.arbre.jardinier import Arbre, Reglages
    TN = tournant
    d = tmp_path / "or"
    d.mkdir()
    a = Arbre(Reglages(places=2))
    for nom_t in ("x", "y"):
        b = a.naitre([], {"nom": nom_t})
        for s in (0.1, 0.2, 0.3):
            a.noter(b.nom, s)
        b.record = 0.3
    a.sauver(d / "arbre.json")
    (d / "journal_croissance.jsonl").write_text("", encoding="utf-8")
    assert TN.passer(d, lambda *_: None) is True
    a2 = Arbre.charger(d / "arbre.json")
    assert all(b.scores == [] and b.record is None for b in a2.vivantes()) and a2.cime is None
    info = json.loads((d / TN.FICHIER_PASSAGE).read_text(encoding="utf-8"))
    assert len(info["notes_examen_fixe"]["A"]) == 3 and (d / TN.FICHIER_BLOCS).exists()
    assert TN.passer(d, lambda *_: None) is False                              # une seule fois
    R().examen_tournant.graine = 6                                            # réservoir changé : refus
    if TN.fabriquer_blocs() != json.loads((d / TN.FICHIER_BLOCS).read_text(encoding="utf-8"))["blocs"]:
        with pytest.raises(SystemExit):
            TN.passer(d, lambda *_: None)


# ================================================================================================ rien d'autre ne change
def test_magnetar_decisions_identiques_avec_les_nouveautes():
    """Empreinte de MAGNETAR (vraie cime figée) : règles d'avant (« comparer »), compte Swing (« swing »), et vrais
    réglages AVEC tendance, suiveur après +1R et mesure de la tenue (« nouveautes ») : décisions et résultats identiques."""
    env = {**os.environ, "CUDA_VISIBLE_DEVICES": "-1"}
    env.pop("COLLAPSAR_PRECISION_REGLAGES", None)
    for mode in ("swing", "nouveautes"):
        p = subprocess.run([sys.executable, "-m", "collapsar.tests.empreinte_magnetar", mode], cwd=RACINE, env=env,
                           capture_output=True, text=True, timeout=900)
        assert p.returncode == 0 and "RESULTAT IDENTIQUE" in p.stdout, (mode, p.stdout[-2000:] + p.stderr[-2000:])
