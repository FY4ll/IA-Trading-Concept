"""Tests de l'école « juger un trade » (collapsar/ecole/precision/juge_trade.py) :
- un trade calculé à la main (ordre limite, stop de structure, 80 % à 2R, stop à l'entrée, nuit, glissement) ;
- le chemin du prix d'un candidat donne EXACTEMENT le résultat du simulateur de l'arbre (simulateur.pas_comptes) ;
- SANS FUTUR : ce que voit le juge (yeux + candidats + description) à t ne dépend pas des données après t ;
- recalibration des poids : un apprentissage où les trades à 2R pèsent 3 fois plus, corrigé, redonne la vraie chance ;
- candidat témoin : géométrie d'un vrai candidat, posée ailleurs, du bon côté du prix ;
- greffe : notes du juge ajoutées à l'arbre avec des poids à zéro = décisions identiques.
Depuis Test_IA : $env:CUDA_VISIBLE_DEVICES='-1'; venv_gpu\\Scripts\\python.exe -m pytest collapsar/tests/test_juge_trade.py -q
"""
from __future__ import annotations

import math
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest
import torch

from collapsar.ecole.precision import juge_trade as JT
from collapsar.ecole.precision import simulateur as SIM
from collapsar.ecole.precision import structure as S
from collapsar.ecole.precision.reglages import R
from collapsar.mains.simulateur import CAPITAL
from test_ecole_precision import monde_invente  # noqa: F401  (fixture : euro-dollar inventé, yeux calculés)


def _chemin(o, h, l, c, demi=1e-4, nuits=None, nuit_a=0.05, nuit_v=-0.02, derniere=None):
    T = len(o)
    a = lambda x: np.asarray(x, float)
    return (a(o), a(h), a(l), a(c), np.ones(T), np.ones(T, bool),
            np.zeros(T, bool) if derniere is None else np.asarray(derniere, bool), np.full(T, demi),
            np.full(T, nuit_a), np.full(T, nuit_v), np.zeros(T) if nuits is None else a(nuits))


def test_un_trade_calcule_a_la_main():
    """Le même trade que tests/test_ecole_precision.test_un_trade_calcule_a_la_main : ordre limite d'achat à 99, stop 98,
    objectif 1 à 2R = 101 (80 %), destination 104 ; exécution, TP1, stop à l'entrée, une nuit, le reste sort à l'entrée
    moins le glissement."""
    s = 1e-4
    ch = _chemin([100.0, 99.8, 99.6, 99.3, 101.0, 100.0], [100.1, 100.2, 99.7, 101.3, 101.5, 100.1],
                 [99.9, 99.5, 98.7, 99.2, 100.5, 98.8], [100.0, 99.9, 99.2, 101.0, 101.2, 99.0], demi=s,
                 nuits=[0, 0, 0, 0, 1, 0])
    exe, ne, ns, r, code = JT.un_trade(*ch, 0, 1.0, True, 99.0, 98.0, 104.0, 0.0, 2.0, 0.8, 10, 960, 1.0)
    nuit = 0.2 * 101.0 * 0.05 / 360
    attendu = 0.8 * (101 - 99) - nuit + 0.2 * (99.0 * (1 - s) - 99.0)
    assert exe and ne == 2 and ns == 5 and code == JT.STOP
    assert r == pytest.approx(attendu / 1.0, abs=1e-9)                # 1 R = 99 - 98
    # même trade, tout à 2R : sort à 101 à la bougie 3
    exe, ne, ns, r, code = JT.un_trade(*ch, 0, 1.0, True, 99.0, 98.0, np.nan, 2.0, 0.0, 0.0, 10, 960, 1.0)
    assert exe and ns == 3 and code == JT.DEST and r == pytest.approx(2.0)
    # ordre jamais exécuté (validité 1 bougie) ; bougie d'exécution jugée au pire (stop dans la même bougie)
    exe, *_ = JT.un_trade(*ch, 0, 1.0, True, 99.0, 98.0, np.nan, 2.0, 0.0, 0.0, 1, 960, 1.0)
    assert not exe
    exe, ne, ns, r, code = JT.un_trade(*ch, 0, 1.0, True, 99.0, 98.8, np.nan, 2.0, 0.0, 0.0, 10, 960, 1.0)
    assert exe and ne == ns == 2 and code == JT.STOP
    assert r == pytest.approx((98.8 * (1 - s) - 99.0) / 0.2)


def _monde_simulateur(T, rng):
    x = 100 + np.cumsum(rng.normal(0, 0.03, (T * 4))).reshape(T, 4)
    o = np.r_[100.0, x[:-1, -1]]
    gap = rng.random(T) < 0.01                                       # quelques trous d'ouverture
    o = np.where(gap, o + rng.normal(0, 0.2, T), o)
    h, l = np.maximum(x.max(1), o), np.minimum(x.min(1), o)
    c = x[:, -1]
    derniere = (np.arange(T) % 200) == 199                           # une pause > 2 h toutes les 200 bougies
    nuits = np.where(np.arange(T) % 96 == 0, np.where(np.arange(T) % 480 == 288, 3.0, 1.0), 0.0)
    demi = 1e-4 * (1 + 0.5 * rng.random(T))
    return o, h, l, c, derniere, nuits, demi


def test_identique_au_simulateur_de_l_arbre():
    """Des centaines de candidats au hasard (achat / vente, marché / ordre limite, destination fixe ou en R, avec ou
    sans 80 % à 2R) : exécution, sortie et R identiques à simulateur.pas_comptes."""
    rng = np.random.default_rng(3)
    T = 1900
    o, h, l, c, derniere, nuits, demi = _monde_simulateur(T, rng)
    ch = (o, h, l, c, np.ones(T), np.ones(T, bool), derniere, demi, np.full(T, 0.04), np.full(T, -0.03), nuits)
    B = 600
    t = rng.integers(10, T - 700, B)
    sens = np.where(rng.random(B) < 0.5, 1.0, -1.0)
    limite = rng.random(B) < 0.6
    A = 0.6
    P = np.where(limite, c[t] - sens * rng.uniform(0.05, 1.5, B) * A, np.nan)
    # entrée attendue : niveau de l'ordre limite, ou ouverture suivante + écart (au marché)
    e_att = np.where(limite, P, o[t + 1] * (1 + sens * demi[t + 1]))
    risque = rng.uniform(0.2, 1.5, B) * A
    stop = e_att - sens * risque
    avec_tp1 = rng.random(B) < 0.5
    k_dest = np.where(avec_tp1, rng.uniform(2.5, 5, B), rng.uniform(0.5, 5, B))
    dest = e_att + sens * k_dest * risque
    val = rng.choice([16, 96, 288], B)
    exe, ne, ns, r, code = JT.trades(*ch, t, sens, limite, np.nan_to_num(P), stop, dest, np.zeros(B),
                                     np.where(avec_tp1, 2.0, 0.0), np.where(avec_tp1, 0.8, 0.0), val, 10 ** 6, 1.0)
    # le simulateur de l'arbre, un compte par candidat
    U = SimpleNamespace(o=o[:, None], h=h[:, None], l=l[:, None], c=c[:, None], fx=np.ones((T, 1)),
                        ouvert=np.ones((T, 1), bool), derniere=derniere[:, None], demi=demi[:, None],
                        nuit_a=np.full((T, 1), 0.04), nuit_v=np.full((T, 1), -0.03), nuits=nuits[:, None],
                        jour=np.arange(T) // 96, levier=np.array([1e6]), pas_u=np.array([1e-9]),
                        pas_d=np.array([1.0]), min_u=np.array([0.0]), fin_challenge=lambda t0: np.full_like(t0, T - 1))
    cp = SIM.Comptes(U, B, 1)
    cp.recommencer(np.ones(B, bool), np.zeros((B, 1), np.int64), t.astype(np.int64))
    cp.ord_act[:, 0] = np.where(limite, SIM.LIMITE, SIM.MARCHE)
    cp.ord_u[:, 0] = sens * 10.0
    cp.ord_prix[:, 0] = P
    cp.ord_stop[:, 0] = stop
    cp.ord_tp1[:, 0] = np.where(avec_tp1, e_att + sens * 2 * risque, np.nan)
    cp.ord_part[:, 0] = np.where(avec_tp1, 0.8, 0.0)
    cp.ord_dest[:, 0] = dest
    cp.ord_duree[:, 0] = val
    r_sim = np.full(B, np.nan)
    exe_sim = np.zeros(B, bool)
    entree_sim = np.full(B, np.nan)
    sortie_sim = np.full(B, -1)
    for _ in range(T):
        if not cp.actif.any():
            break
        cp.pas(1.0)
        ev = cp.evt[:, 0]
        neuf = ((ev & (SIM.EXECUTE | SIM.OUVERTE)) != 0) & ~exe_sim
        entree_sim = np.where(neuf, cp.entree[:, 0], entree_sim)
        exe_sim |= neuf
        fini = np.isfinite(cp.r_ferme[:, 0]) & np.isnan(r_sim)
        r_sim = np.where(fini, cp.r_ferme[:, 0], r_sim)
        sortie_sim = np.where(fini, cp.t, sortie_sim)
        rate = ((ev & (SIM.EXPIRE | SIM.REFUS)) != 0) | ((cp.att[:, 0] == 0) & (cp.u[:, 0] == 0) & ~exe_sim)
        cp.actif &= ~(fini | rate | (cp.t >= T - 2))
    pareil = (code != JT.FIN) & (np.isnan(entree_sim) | np.isclose(entree_sim, e_att, rtol=0, atol=1e-12))
    assert pareil.sum() > 0.8 * B
    np.testing.assert_array_equal(exe[pareil], exe_sim[pareil])
    assert exe[pareil].mean() > 0.3 and (code[pareil] == JT.DEST).sum() > 20 and (code[pareil] == JT.FORCEE).sum() > 5
    m = pareil & exe
    np.testing.assert_array_equal(ns[m], sortie_sim[m])
    np.testing.assert_allclose(r[m], r_sim[m], rtol=0, atol=1e-9)


def _univers_euro():
    if not (S.dossier("EURUSD", False) / "fait.json").exists():
        pytest.skip("yeux de EURUSD pas encore calculés")
    from collapsar.ecole.precision.univers import Univers
    de = pd.Timestamp("2019-01-01")
    return (Univers([("EURUSD", False)], de, pd.Timestamp("2019-04-01"), "cpu"),
            Univers([("EURUSD", False)], de, pd.Timestamp("2019-09-01"), "cpu"))


def _vu_par_le_juge(U, t, graine):
    from collapsar.ecole.precision.vue import Vue
    v = Vue(U)
    s = v.structure(t, torch.zeros(len(t), 1, dtype=torch.long))
    X = JT.foule_neutre_si_besoin(v.caracteristiques(s)[:, 0])
    o = JT.options(s)
    gen = torch.Generator().manual_seed(graine)
    c = JT.tirer(o, 3, gen)
    tm = JT.temoins(c, o, 1, gen)
    return X, c, JT.decrire(c), JT.decrire(tm), JT.pres_d_une_zone(s)


def test_sans_futur():
    """Le juge à l'instant t (yeux, candidats tirés, description, présence d'une zone) : identique que les données
    s'arrêtent 3 jours après t ou 5 mois après."""
    U1, U2 = _univers_euro()
    t = torch.arange(U1.premier[0], U1.T - 3 * 96, 29)
    X1, c1, d1, w1, p1 = _vu_par_le_juge(U1, t, 5)
    X2, c2, d2, w2, p2 = _vu_par_le_juge(U2, t, 5)
    torch.testing.assert_close(X1, X2)
    for k in ("inst", "sig", "limite", "e", "stop", "dest", "validite"):
        torch.testing.assert_close(c1[k], c2[k])
    torch.testing.assert_close(d1, d2)
    torch.testing.assert_close(w1, w2)
    assert torch.equal(p1, p2)
    assert len(c1["sig"]) > 100 and d1.shape[1] == JT.ND


def test_candidats_comme_les_mains():
    """Les candidats respectent les règles des mains : ordre limite du bon côté du prix (plus d'un aller-retour de
    frais), à 6 agitations au plus ; stop derrière l'entrée (plus d'un aller-retour) ; destination devant."""
    U1, _ = _univers_euro()
    t = torch.arange(U1.premier[0], U1.T - 3 * 96, 13)
    _, c, d, _, _ = _vu_par_le_juge(U1, t, 9)
    sig, e, p, fr, A = c["sig"], c["e"], c["p"], c["fr"], c["A"]
    lim = c["limite"]
    assert (sig[lim] * (p[lim] - e[lim]) > fr[lim]).all()
    assert ((p[lim] - e[lim]).abs() <= R().mains.entree_max_agitation * A[lim] + 1e-6).all()
    assert (sig * (e - c["stop"]) > fr).all()
    assert (sig * (c["dest"] - e) > 0).all()
    assert 0.3 < lim.float().mean() < 0.95
    # destinations : zones opposées, sommets / creux, 2R et 3R
    assert set(c["d_type"].unique().tolist()) == {0, 1, 2}


def test_candidat_temoin():
    """Un témoin reprend la géométrie d'un vrai candidat (au marché ou limite, distance d'entrée et risque en
    agitations, destination en R) et la pose à SON instant, du bon côté du prix."""
    gen = torch.Generator().manual_seed(1)
    n = 50
    o = {"p": torch.linspace(1.0, 2.0, n), "A": torch.full((n,), 0.01), "fr": torch.full((n,), 1e-5)}
    c = {"inst": torch.arange(n), "sig": torch.ones(n), "limite": torch.ones(n, dtype=torch.bool),
         "p": torch.full((n,), 1.5), "A": torch.full((n,), 0.02), "e": torch.full((n,), 1.5 - 0.03),
         "rd": torch.full((n,), 0.01), "stop": torch.full((n,), 1.5 - 0.04), "dest": torch.full((n,), 1.5 - 0.03 + 0.025),
         "marge": torch.full((n,), 0.002), "dest_r": torch.zeros(n, dtype=torch.long), "validite": torch.full((n,), 96),
         "fr": torch.full((n,), 1e-5), "temoin": torch.zeros(n, dtype=torch.bool)}
    un = lambda v: torch.full((n,), v, dtype=torch.long)
    c.update({"e_type": un(1), "e_unite": un(2), "e_att": torch.rand(n, 5), "st_type": un(0), "st_unite": un(2),
              "st_att": torch.rand(n, 5), "d_type": un(0), "d_unite": un(1), "d_att": torch.rand(n, 5)})
    tm = JT.temoins(c, o, 1, gen)
    assert tm["temoin"].all() and (tm["inst"] == torch.arange(n)).all()
    sig = tm["sig"]
    assert set(sig.tolist()) == {1.0, -1.0}
    torch.testing.assert_close(sig * (o["p"] - tm["e"]) / o["A"], torch.full((n,), 1.5))      # 0,03 / 0,02 agitation
    torch.testing.assert_close(tm["rd"] / o["A"], torch.full((n,), 0.5))                       # risque 0,5 agitation
    torch.testing.assert_close(sig * (tm["dest"] - tm["e"]) / tm["rd"], torch.full((n,), 2.5), rtol=1e-4, atol=1e-4)  # destination 2,5 R
    torch.testing.assert_close(sig * (tm["e"] - tm["stop"]), tm["rd"])
    assert JT.decrire(tm)[:, JT.NOMS_DESC.index("temoin")].eq(1).all()


def test_recalibration_des_poids():
    """Les trades à 2R pèsent POIDS_2R fois plus à l'apprentissage : la chance apprise est gonflée ; la correction de
    la cote redonne la vraie chance (et la recalibration a z + b ne la déforme pas)."""
    rng = np.random.default_rng(0)
    vraie = 0.25
    y = torch.as_tensor(rng.random(200_000) < vraie)
    w = JT.poids_exemples(torch.ones_like(y), y, 3.0)
    z = torch.zeros(1, requires_grad=True)
    opt = torch.optim.LBFGS([z], max_iter=100)

    def f():
        opt.zero_grad()
        l = (torch.nn.functional.binary_cross_entropy_with_logits(z.expand(len(y)), y.float(), reduction="none")
             * w).sum() / w.sum()
        l.backward()
        return l
    opt.step(f)
    apprise = float(torch.sigmoid(z))
    p = float(y.float().mean())
    assert apprise == pytest.approx(3 * p / (3 * p + 1 - p), abs=2e-3)            # gonflée (~0,5)
    assert float(torch.sigmoid(JT.corriger_cote(z, 3.0))) == pytest.approx(p, abs=2e-3)
    a, b = JT._platt(np.full(len(y), float(JT.corriger_cote(z, 3.0))), y.numpy().astype(float))
    assert 1 / (1 + math.exp(-(a * float(JT.corriger_cote(z, 3.0)) + b))) == pytest.approx(p, abs=2e-3)


def test_greffe_decisions_identiques(monde_invente, tmp_path, monkeypatch):
    """Notes du juge ajoutées aux yeux de l'arbre avec des poids à ZÉRO : mêmes yeux transformés, mêmes choix."""
    from collapsar.ecole.precision import cerveau as C
    from collapsar.ecole.precision import vue as V
    from collapsar.ecole.precision.univers import Univers
    assert V.N_JUGE == JT.NJ
    torch.manual_seed(0)
    juge = JT.Juge(V.taille_caracteristiques() + (19 if not V.foule_active() else 0))
    with torch.no_grad():
        for p_ in juge.parameters():
            p_.add_(torch.randn_like(p_) * 0.05)
    f = tmp_path / "juge.pt"
    JT.sauver_juge(juge, f, {})
    monkeypatch.setenv("COLLAPSAR_JUGE", str(f))
    monkeypatch.setattr(JT, "_JUGE", {})
    de, a = pd.Timestamp("2019-03-01"), pd.Timestamp("2019-05-01")
    U0 = Univers([("EURUSD", False)], de, a, "cpu")
    torch.manual_seed(1)
    net0 = C.Cerveau()
    monkeypatch.setattr(R().yeux, "juge", True)
    U1 = Univers([("EURUSD", False)], de, a, "cpu")
    assert U1.tJUGE.shape == (U1.T, 1, JT.NJ) and U1.tJUGE.abs().sum() > 0
    net1 = C.Cerveau()
    etat, change = JT.greffer_etat({"cerveau": net0.state_dict()})
    assert change
    net1.load_state_dict(etat["cerveau"])
    t = torch.arange(U0.premier[0], U0.T - 10, 7)
    cols = torch.zeros(len(t), 1, dtype=torch.long)
    pos = torch.zeros(len(t), 1, C.N_POS)
    fc = torch.zeros(len(t), C.N_COMPTE)
    monkeypatch.setattr(R().yeux, "juge", False)
    v0 = V.Vue(U0)
    s0 = v0.structure(t, cols)
    fm0 = torch.cat([v0.caracteristiques(s0), pos], -1)
    monkeypatch.setattr(R().yeux, "juge", True)
    v1 = V.Vue(U1)
    s1 = v1.structure(t, cols)
    fm1 = torch.cat([v1.caracteristiques(s1), pos], -1)
    assert fm1.shape[-1] == fm0.shape[-1] + JT.NJ
    with torch.no_grad():
        torch.testing.assert_close(net1.marche(fm1), net0.marche(fm0))
        torch.manual_seed(7)
        ch0, *_ = C.politique(net0, s0, fm0, fc, pos, None, False)
        torch.manual_seed(7)
        ch1, *_ = C.politique(net1, s1, fm1, fc, pos, None, False)
    for k in ch0:
        assert torch.equal(ch0[k], ch1[k]), k
