"""Tests du STOP SUIVEUR de l'arbre de l'or (18/10/2026, collapsar/ecole/precision/suiveur.py + simulateur.py) :
- HYPERNOVA (réglages par défaut, suiveur éteint) : EXACTEMENT le même comportement qu'avant (empreinte du code d'avant :
  simulateur, décisions, leçon, apprentissage, examen) ;
- un trade calculé à la main (achat : stop remonté derrière chaque nouveau creux, jamais reculé, sortie au stop remonté ;
  suiveur après l'objectif 1) et la vente symétrique ;
- ÉGALITÉ avec regarder/pistes/mouvements.trade_suiveur sur des centaines de trades au hasard (frais, nuits, fermetures
  avant une pause, destination) ;
- GREFFE SANS PERTE : les anciennes sorties des têtes et la destination ne changent pas, à graine égale les anciens
  tirages sont les mêmes ; avec « aucun suiveur » forcé, une partie entière est identique à l'ancien cerveau ;
- greffe d'un arbre (sauvegarde, branche la plus faible archivée, branche « laisse_courir » et ses penchants), refus d'un
  arbre non greffé, examen qui rapporte l'usage du suiveur.
Depuis Test_IA : $env:CUDA_VISIBLE_DEVICES='-1'; venv_gpu\\Scripts\\python.exe -m pytest collapsar/tests/test_suiveur.py -q
"""
from __future__ import annotations

import json
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest
import torch

from collapsar.ecole.precision import simulateur as SIM
from collapsar.ecole.precision import structure as S
from collapsar.ecole.precision import suiveur as SV
from collapsar.ecole.precision.reglages import R
from collapsar.mains.simulateur import CAPITAL

from test_ecole_precision import monde_invente, univers_minimal  # noqa: F401  (fixture partagée)

NAN = np.nan


@pytest.fixture
def allume(monkeypatch):
    """Le stop suiveur allumé (comme reglages_or.yaml), remis comme avant à la fin du test."""
    monkeypatch.setattr(R().mains, "suiveur", True, raising=False)
    monkeypatch.setattr(R().mains, "suiveur_unites", ["D1", "H4", "H1", "M15"], raising=False)
    monkeypatch.setattr(R().mains, "suiveur_depart_pct", 10.0, raising=False)


# ================================================================================================ HYPERNOVA intact
def test_hypernova_exactement_comme_avant():
    import empreinte_hypernova as E
    from collapsar.ecole.precision import cerveau as C
    assert not SV.active() and SV.n_sorties() == 0
    assert C.Cerveau().tetes.out_features == 6 + 5 + 3 + 5 + 3            # mêmes têtes qu'avant
    ref = np.load(E.FICHIER)
    out = E.calculer()
    for k in ref.files:
        assert np.array_equal(ref[k], out[k], equal_nan=ref[k].dtype.kind == "f"), k


def test_reglages_or_allument_le_suiveur():
    from collapsar.ecole.precision import reglages as RG
    o = RG.lire(RG.DEFAUT.with_name("reglages_or.yaml"))
    assert o.mains.suiveur is True and list(o.mains.suiveur_unites) == ["D1", "H4", "H1", "M15"]
    assert getattr(R().mains, "suiveur", False) is False                    # HYPERNOVA : éteint


# ================================================================================================ à la main
def _monde(o, h, l, c, sw_v, sw_id, demi=1e-4):
    T = len(o)
    U = univers_minimal(o, h, l, c, jour=np.zeros(T, np.int64), nuits=np.zeros(T), demi=demi, nuit_achat=0.0)
    U.sw_v, U.sw_id = sw_v, sw_id
    return U


def _chemin_main():
    o = np.array([100.0, 100.0, 100.5, 101.0, 101.5, 102.0, 101.8, 101.0, 100.6])
    return o, o + 0.3, o - 0.3, o.copy()


def _swings(T, creux, n_creux, sommets=None, n_sommets=None):
    """Tableaux [T, 1, 1, 2] connus à la CLÔTURE de chaque bougie (= à l'ouverture de la suivante)."""
    sw_v = np.full((T, 1, 1, 2), NAN)
    sw_id = np.zeros((T, 1, 1, 2), np.int64)
    sw_v[:, 0, 0, 0], sw_id[:, 0, 0, 0] = creux, n_creux
    if sommets is not None:
        sw_v[:, 0, 0, 1], sw_id[:, 0, 0, 1] = sommets, n_sommets
    return sw_v, sw_id


def _jouer(U, sens, stop, tp1=NAN, part=0.0, dest=NAN, suiveur=0, apres_tp1=False, marge=0.1, unites=1000.0):
    cp = SIM.Comptes(U, 1, 1)
    cp.recommencer(np.array([True]), np.array([[0]]), np.array([0]))
    cp.ord_act[0, 0], cp.ord_u[0, 0], cp.ord_stop[0, 0] = SIM.MARCHE, sens * unites, stop
    cp.ord_tp1[0, 0], cp.ord_part[0, 0], cp.ord_dest[0, 0] = tp1, part, dest
    cp.ord_sv_u[0, 0], cp.ord_sv_tp1[0, 0], cp.ord_sv_m[0, 0] = suiveur, apres_tp1, marge
    stops, evts = [], []
    for _ in range(len(U.o) - 1):
        cp.pas(1.0)
        stops.append(cp.stop[0, 0])
        evts.append(cp.evt[0, 0])
        if cp.u[0, 0] == 0:
            break
    return cp, stops, evts


def test_stop_suiveur_a_la_main():
    """Achat au marché à 100 (+ demi-frais), stop 99. Creux confirmés : 99,8 (connu à l'ouverture de la bougie 4) puis
    101,2 (bougie 6) -> stop 99,7 puis 101,1 ; la bougie 7 ouvre à 101,0 sous le stop : sortie à l'ouverture."""
    s = 1e-4
    o, h, l, c = _chemin_main()
    T = len(o)
    # connus à la clôture de la bougie k (ouverture de k + 1) : creux 99,8 à la clôture de 3, 101,2 à la clôture de 5
    sw_v, sw_id = _swings(T, [NAN, NAN, NAN, 99.8, 99.8, 101.2, 101.2, 101.2, 101.2], [0, 0, 0, 1, 1, 2, 2, 2, 2])
    U = _monde(o, h, l, c, sw_v, sw_id, s)
    cp, stops, evts = _jouer(U, 1.0, 99.0)
    e = 100.0 * (1 + s)
    assert cp.entree[0, 0] == pytest.approx(e)
    # bougies 1..7 : 99, 99, 99, 99,7 (remonté), 99,7, 101,1 (remonté), sortie
    assert stops[:6] == pytest.approx([99.0, 99.0, 99.0, 99.7, 99.7, 101.1])
    assert [bool(x & SIM.SUIVI) for x in evts] == [False, False, False, True, False, True, False]
    px = min(101.1, 101.0 * (1 - s)) * (1 - s)                     # glissement : un demi-frais en plus
    assert evts[-1] & SIM.STOP and len(evts) == 7 and cp.sv_n[0, 0] == 2
    assert cp.r_ferme[0, 0] == pytest.approx((px - e) / (e - 99.0), abs=1e-12)
    assert cp.solde[0] == pytest.approx(CAPITAL + 1000 * (px - e), abs=1e-6)
    # sans suiveur (place -1) : le stop reste à 99 jusqu'au bout
    cp, stops, _ = _jouer(U, 1.0, 99.0, suiveur=-1)
    assert cp.u[0, 0] == 1000 and set(stops) == {99.0}
    # un nouveau creux plus BAS que le stop ne le fait jamais reculer ; au-dessus du prix d'ouverture : ignoré
    sw_v2, _ = _swings(T, [NAN, NAN, NAN, 99.8, 99.8, 99.5, 99.5, 99.5, 99.5], [0] * T)
    cp, stops, _ = _jouer(_monde(o, h, l, c, sw_v2, sw_id, s), 1.0, 99.0)
    assert stops[-1] == pytest.approx(99.7) and cp.u[0, 0] == 1000
    sw_v3, _ = _swings(T, [NAN, NAN, NAN, 99.8, 99.8, 103.0, 103.0, 103.0, 103.0], [0] * T)
    cp, stops, _ = _jouer(_monde(o, h, l, c, sw_v3, sw_id, s), 1.0, 99.0)
    assert stops[-1] == pytest.approx(99.7) and cp.u[0, 0] == 1000


def test_stop_suiveur_apres_l_objectif_1():
    """Suiveur « après l'objectif 1 » : le creux 99,8 (avant TP1) ne compte pas ; TP1 à 101,2 (bougie 3, la moitié
    fermée), stop à l'entrée ; le creux 99,8 vu ensuite ne le fait pas reculer ; 101,2 -> stop 101,1 ; sortie bougie 7."""
    s = 1e-4
    o, h, l, c = _chemin_main()
    T = len(o)
    sw_v, sw_id = _swings(T, [NAN, NAN, NAN, 99.8, 99.8, 101.2, 101.2, 101.2, 101.2], [0, 0, 0, 1, 1, 2, 2, 2, 2])
    U = _monde(o, h, l, c, sw_v, sw_id, s)
    cp, stops, evts = _jouer(U, 1.0, 99.0, tp1=101.2, part=0.5, suiveur=0, apres_tp1=True)
    e = 100.0 * (1 + s)
    assert evts[2] & SIM.TP1 and stops[2] == pytest.approx(e)       # bougie 3 : TP1, stop à l'entrée
    assert stops[3] == pytest.approx(e) and stops[5] == pytest.approx(101.1)
    px = min(101.1, 101.0 * (1 - s)) * (1 - s)
    attendu = 500 * (101.2 - e) + 500 * (px - e)
    assert evts[-1] & SIM.STOP and cp.r_ferme[0, 0] == pytest.approx(attendu / (1000 * (e - 99.0)), abs=1e-12)
    # suiveur dès l'entrée + TP1 : le stop déjà remonté au-dessus de l'entrée n'est PAS ramené à l'entrée par TP1
    sw_v4, sw_id4 = _swings(T, [NAN] + [100.15] * (T - 1), [0] + [1] * (T - 1))
    cp, stops, evts = _jouer(_monde(o, h, l, c, sw_v4, sw_id4, s), 1.0, 99.0, tp1=101.2, part=0.5, suiveur=0)
    assert stops[1] == pytest.approx(100.05) and evts[2] & SIM.TP1 and stops[2] == pytest.approx(100.05)
    assert stops[2] > e


def test_stop_suiveur_vente_symetrique():
    """Sans frais, la vente sur le chemin retourné (200 - prix) avec les sommets retournés : même R que l'achat."""
    o, h, l, c = _chemin_main()
    T = len(o)
    cr = np.array([NAN, NAN, NAN, 99.8, 99.8, 101.2, 101.2, 101.2, 101.2])
    nc = np.array([0, 0, 0, 1, 1, 2, 2, 2, 2])
    a, _, _ = _jouer(_monde(o, h, l, c, *_swings(T, cr, nc), demi=0.0), 1.0, 99.0)
    sv, si = _swings(T, np.full(T, NAN), np.zeros(T, np.int64), 200 - cr, nc)
    b, _, _ = _jouer(_monde(200 - o, 200 - l, 200 - h, 200 - c, sv, si, demi=0.0), -1.0, 101.0)
    assert a.r_ferme[0, 0] == pytest.approx(b.r_ferme[0, 0], abs=1e-12) and a.sv_n[0, 0] == b.sv_n[0, 0] == 2


# ================================================================================================ égalité avec la piste
def test_egal_a_trade_suiveur_des_mouvements():
    """Des centaines de trades au hasard (achat / vente, destination ou non, marge, frais, nuits achat ≠ vente, fermetures
    avant une pause) : le simulateur de l'arbre avec suiveur dès l'entrée donne EXACTEMENT mouvements.trade_suiveur
    (creux / sommets fractal 2 du chemin lui-même, numérotés par suiveur.numeros)."""
    from collapsar.regarder.pistes import mouvements as MV
    rng = np.random.default_rng(5)
    T = 1800
    c = 100 * np.exp(np.cumsum(rng.normal(0, 0.0015, T)))
    o = np.r_[100.0, c[:-1]]
    h = np.maximum(o, c) * (1 + np.abs(rng.normal(0, 0.001, T)))
    l = np.minimum(o, c) * (1 - np.abs(rng.normal(0, 0.001, T)))
    derniere = rng.random(T) < 0.004
    nuits = (rng.random(T) < 0.03).astype(float)
    fx, demi, na, nv = 1.3, 2e-4, 0.03, -0.01
    px_, cf, ty = S.sommets(h, l)
    sw = S.derniers_sommets(T, px_, cf, ty)                      # connu à la clôture de chaque bougie
    nc, ns = SV.numeros(sw)
    # trade_suiveur : connu à l'OUVERTURE de n = clôture de n - 1
    tv_l, tid_l = np.r_[NAN, sw[:-1, 2]], np.r_[0, nc[:-1]]
    tv_s, tid_s = np.r_[NAN, sw[:-1, 0]], np.r_[0, ns[:-1]]
    sw_v = np.stack([sw[:, 2], sw[:, 0]], -1)[:, None, None, :].copy()
    sw_id = np.stack([nc, ns], -1)[:, None, None, :].copy()
    col = lambda x: np.asarray(x, float)[:, None]
    U = SimpleNamespace(o=col(o), h=col(h), l=col(l), c=col(c), fx=np.full((T, 1), fx), ouvert=np.ones((T, 1), bool),
                        derniere=derniere[:, None].copy(), demi=np.full((T, 1), demi), nuit_a=np.full((T, 1), na),
                        nuit_v=np.full((T, 1), nv), nuits=col(nuits), jour=np.arange(T, dtype=np.int64) // 96,
                        levier=np.array([30.0]), pas_u=np.array([1.0]), pas_d=np.array([100.0]), min_u=np.array([0.0]),
                        fin_challenge=lambda t0: np.full_like(t0, T - 1), sw_v=sw_v, sw_id=sw_id)
    ch = (o, h, l, c, np.full(T, fx), np.ones(T, bool), derniere, np.full(T, demi), np.full(T, na), np.full(T, nv), nuits)
    n_exe, n_suivi, n_stop = 0, 0, 0
    for _ in range(400):
        t = int(rng.integers(0, T - 60))
        sens = 1.0 if rng.random() < 0.5 else -1.0
        stop = c[t] * (1 - sens * rng.uniform(0.002, 0.015))
        dest = c[t] * (1 + sens * rng.uniform(0.01, 0.05)) if rng.random() < 0.4 else NAN
        marge = float(rng.choice([0.0, 0.05, 0.2])) * 0.5
        a = MV.trade_suiveur(*ch, t, sens, stop, dest, 0.0, 10 ** 9, 1.0, tv_l, tid_l, tv_s, tid_s, marge, True)
        cp = SIM.Comptes(U, 1, 1)
        cp.recommencer(np.array([True]), np.array([[0]]), np.array([t]))
        cp.ord_act[0, 0], cp.ord_u[0, 0], cp.ord_stop[0, 0], cp.ord_dest[0, 0] = SIM.MARCHE, sens * 100.0, stop, dest
        cp.ord_sv_u[0, 0], cp.ord_sv_m[0, 0] = 0, marge
        cp.pas(1.0)
        assert bool(cp.evt[0, 0] & SIM.OUVERTE) == a[0]
        if not a[0]:
            continue
        n_exe += 1
        while cp.u[0, 0] != 0 and cp.t[0] < T - 1:
            cp.pas(1.0)
        if a[4] == MV.JT.FIN:                                   # pas fermé avant la fin des données : ouvert ici aussi
            assert cp.u[0, 0] != 0
            continue
        assert cp.u[0, 0] == 0 and cp.t[0] == a[2], (t, a)
        assert cp.r_ferme[0, 0] == pytest.approx(a[3], abs=1e-9)
        n_suivi += int(cp.sv_n[0, 0] > 0)
        n_stop += int(a[4] == MV.JT.STOP)
    assert n_exe > 300 and n_suivi > 100 and n_stop > 100


# ================================================================================================ greffe sans perte
def _vieux_cerveau():
    from collapsar.ecole.precision import cerveau as C
    torch.manual_seed(4)
    net = C.Cerveau()
    with torch.no_grad():                                    # des têtes « apprises » (pas les zéros du départ)
        net.tetes.weight.normal_(0, 0.05)
        net.tetes.bias.normal_(0, 0.5)
        net.delai.weight.normal_(0, 0.05)
    return net


def _sortie(U, net, graine):
    """Un regard de 40 comptes : choix tirés, niveaux, probabilités relues (log-prob, hasard) et sorties des têtes."""
    from collapsar.ecole.precision import cerveau as C
    from collapsar.ecole.precision import jeu as JEU
    B = 40
    tb = JEU.Table(U, B, 1)
    dep = np.random.default_rng(1).integers(U.premier[0], U.T - 400, B)
    tb.demarrer(np.ones(B, bool), np.zeros((B, 1), np.int64), dep)
    torch.manual_seed(graine)
    with torch.no_grad():
        (choix, lp, lp_exec, hasard, valeur, lv), (t, cols, fc, pos) = tb.regarder(net, np.arange(B))
        s = tb.vue.structure(t, cols)
        fm = torch.cat([tb.vue.caracteristiques(s), pos], -1)
        h, g = net.corps(fm, fc, s["slot"])
        tetes = net.tetes(h)
        # relecture des choix avec le suiveur « aucun » : la probabilité des anciens gestes seule
        ch0 = {k: v for k, v in choix.items()}
        if "suiveur" in ch0:
            ch0["suiveur"] = torch.zeros_like(ch0["suiveur"])
        _, lp2, lpe2, _, val2, _ = C.politique(net, s, fm, fc, pos, ch0, True)
    return choix, lv, tetes, lp2, lpe2, val2


def test_greffe_sans_perte_des_anciens_gestes(monde_invente, monkeypatch):
    from collapsar.ecole.precision import cerveau as C
    from collapsar.ecole.precision.univers import Univers
    de, a = pd.Timestamp("2019-03-01"), pd.Timestamp("2019-07-01")
    U0 = Univers([("EURUSD", False)], de, a, "cpu")
    vieux = _vieux_cerveau()
    opt = torch.optim.AdamW(vieux.parameters(), lr=1e-3)
    vieux.zero_grad()
    sum(p.sum() for p in vieux.parameters()).backward()
    opt.step()                                                               # un optimiseur qui a une mémoire
    etat = {"cerveau": vieux.state_dict(), "opt": opt.state_dict()}
    c0, lv0, t0, lp0, lpe0, v0_ = _sortie(U0, vieux, 7)
    # greffe, puis le même cerveau dans le monde où le suiveur est allumé
    monkeypatch.setattr(R().mains, "suiveur", True, raising=False)
    monkeypatch.setattr(R().mains, "suiveur_unites", ["D1", "H4", "H1", "M15"], raising=False)
    e2, change = SV.greffer_etat(etat)
    assert change and SV.greffer_etat(e2)[1] is False                       # une seule fois
    for k, v in etat["cerveau"].items():                                    # aucune ancienne valeur ne change
        assert torch.equal(e2["cerveau"][k], v), k
    assert set(e2["cerveau"]) - set(etat["cerveau"]) == {"suiv.weight", "suiv.bias"}
    neuf = C.Cerveau()
    neuf.load_state_dict(e2["cerveau"])
    U1 = Univers([("EURUSD", False)], de, a, "cpu")
    c1, lv1, t1, lp1, lpe1, v1_ = _sortie(U1, neuf, 7)
    assert torch.equal(t1, t0)                                               # anciennes têtes : identiques
    for k in c0:                                                             # mêmes tirages à graine égale
        assert torch.equal(c0[k], c1[k]), k
    for k in lv0:
        assert torch.equal(torch.nan_to_num(lv0[k].float(), nan=-7.0), torch.nan_to_num(lv1[k].float(), nan=-7.0)), k
    assert "suiveur" in c1 and not ("suiveur" in c0)
    assert torch.equal(v1_, v0_)                                             # même valeur attendue
    # probabilités des anciens gestes : identiques (relues avec « aucun suiveur » certain : log p = 0)
    import copy
    sur = copy.deepcopy(neuf)
    with torch.no_grad():
        sur.suiv.bias[1:SV.n_options()] = -1e4
    c2, lv2, t2, lp2, lpe2, _ = _sortie(U1, sur, 7)
    assert torch.equal(lp2, lp0) and torch.equal(lpe2, lpe0)
    for k in c0:
        assert torch.equal(c0[k], c2[k]), k
    # part de départ du suiveur : 10 % en tout (poids à zéro)
    p = torch.softmax(neuf.suiv.bias[:SV.n_options()], -1)
    assert float(1 - p[0]) == pytest.approx(0.10, abs=1e-6) and float(neuf.suiv.bias[-1]) == 0.0
    # l'optimiseur se recharge (nouvelle tête à la fin, sa mémoire naîtra au premier pas) et apprend
    opt2 = torch.optim.AdamW(neuf.parameters(), lr=1e-3)
    opt2.load_state_dict(e2["opt"])
    neuf.zero_grad()
    (neuf.suiv.bias.sum() + sum(p.sum() for p in neuf.tetes.parameters())).backward()
    opt2.step()
    # NB : sur une partie entière, le tirage du suiveur (fait en dernier) décale le hasard des regards suivants, comme
    # une autre graine : la LOI des décisions est la même (prouvé ci-dessus), pas la suite exacte des tirages.


def test_aucun_suiveur_meme_partie_que_l_ancien_cerveau(monde_invente, monkeypatch):
    """Une partie entière (table, ordres, simulateur, réveils) avec le tirage du suiveur neutralisé (« aucun » rendu
    sans consommer de hasard) : EXACTEMENT la partie de l'ancien cerveau non greffé."""
    from collapsar.ecole.precision import cerveau as C
    from collapsar.ecole.precision.univers import Univers
    from test_ecole_precision import _jouer_table
    de, a = pd.Timestamp("2019-03-01"), pd.Timestamp("2019-07-01")
    U0 = Univers([("EURUSD", False)], de, a, "cpu")
    vieux = _vieux_cerveau()
    v0, f0, nu0 = _jouer_table(U0, vieux, 60, 600, graine=3)
    monkeypatch.setattr(R().mains, "suiveur", True, raising=False)
    monkeypatch.setattr(R().mains, "suiveur_unites", ["D1", "H4", "H1", "M15"], raising=False)
    neuf = C.Cerveau()
    neuf.load_state_dict(SV.greffer_etat({"cerveau": vieux.state_dict()})[0]["cerveau"])
    tirer = C.Loi.tirer
    monkeypatch.setattr(C.Loi, "tirer", lambda self: torch.zeros(self.logits.shape[:-1], dtype=torch.long)
                        if self.logits.shape[-1] == SV.n_options() else tirer(self))
    U1 = Univers([("EURUSD", False)], de, a, "cpu")
    v1, f1, nu1 = _jouer_table(U1, neuf, 60, 600, graine=3)
    assert np.array_equal(v0, v1) and np.array_equal(f0, f1) and np.array_equal(nu0, nu1)
    assert (v0 != CAPITAL).any()


def test_le_suiveur_choisi_change_les_trades(monde_invente, allume):
    """Allumé : des trades au stop suiveur existent, le stop est remonté, l'examen rapporte l'usage et les R ; une
    leçon et un pas d'apprentissage passent."""
    from collapsar.ecole.precision import cerveau as C
    from collapsar.ecole.precision import jeu as JEU
    from collapsar.ecole.precision.univers import Univers
    U = Univers([("EURUSD", False)], pd.Timestamp("2019-03-01"), pd.Timestamp("2019-09-01"), "cpu")
    assert U.sw_v.shape == (U.T, 1, 4, 2) and bool(U.tSV_DISPO.all())
    torch.manual_seed(0)
    net = C.Cerveau()
    SV.pencher(net, {"suiveur_pct": 90.0})
    old = R().monde.challenge_jours
    R().monde.challenge_jours = 10
    try:
        ex = JEU.Examen(U, [["EURUSD"]], pd.Timestamp("2019-06-01"), pd.Timestamp("2019-08-15"), 5)
        x = ex.jouer_un(net, 1)
    finally:
        R().monde.challenge_jours = old
    for k in ("suiveur_pct", "r_moyen_suiveur", "r_moyen_sans_suiveur", "suiveur_remonte_pct", "suiveur_unite_pct"):
        assert k in x and k in x["jumeau"], k
    assert x["suiveur_pct"] > 60 and x["suiveur_trades"] > 20 and x["suiveur_remonte_pct"] > 0
    assert sum(x["suiveur_unite_pct"].values()) == pytest.approx(100.0)
    opt = torch.optim.AdamW(net.parameters(), lr=3e-4)
    lecon = JEU.Lecon(U, 16, np.random.default_rng(0))
    m, b = lecon.jouer(net, 64)
    assert "suiveur" in m["choix"]
    a = JEU.apprendre(net, opt, lecon.table, m, 1, 256, 0.2, 0.003)
    assert np.isfinite(a["perte_decision"])


def test_examen_sans_suiveur_ne_change_pas(monde_invente):
    from collapsar.ecole.precision import cerveau as C
    from collapsar.ecole.precision import jeu as JEU
    from collapsar.ecole.precision.univers import Univers
    U = Univers([("EURUSD", False)], pd.Timestamp("2019-06-01"), pd.Timestamp("2019-08-15"), "cpu")
    assert not hasattr(U, "sw_v")
    old = R().monde.challenge_jours
    R().monde.challenge_jours = 10
    try:
        x = JEU.Examen(U, [["EURUSD"]], pd.Timestamp("2019-06-01"), pd.Timestamp("2019-08-15"), 10).jouer_un(C.Cerveau(), 1)
    finally:
        R().monde.challenge_jours = old
    assert "suiveur_pct" not in x


# ================================================================================================ greffe d'un arbre
def _arbre(d):
    from collapsar.arbre.jardinier import Arbre, Reglages
    from collapsar.ecole.precision import cerveau as C
    (d / "branches").mkdir(parents=True)
    a = Arbre(Reglages(places=4))
    for i, (nom_t, notes, her) in enumerate((("heritiere", [0.1, 0.0, -0.1], "HYPERNOVA x"),
                                             ("curieuse", [0.2, 0.2, 0.2], "HYPERNOVA x"),
                                             ("seconde", [0.5, 0.5, 0.5], "HYPERNOVA y"),
                                             ("temoin", [-0.9, -0.9, -0.9], "aucun (branche neuve, témoin)"))):
        b = a.naitre([], {"nom": nom_t, "vitesse": 3e-4, "curiosite": 0.003, "heritage": her})
        for s in notes:
            a.noter(b.nom, s)
        torch.manual_seed(i)
        net = C.Cerveau()
        opt = torch.optim.AdamW(net.parameters(), lr=3e-4)
        e = {"cerveau": net.state_dict(), "opt": opt.state_dict(), "temperament": b.temperament}
        torch.save(e, d / "branches" / f"{b.nom}.pt")
        torch.save({"cerveau": net.state_dict()}, d / "branches" / f"{b.nom}_meilleur.pt")
    a._elire_cime()
    a.fin_de_battement()
    a.sauver(d / "arbre.json")
    torch.save({"cerveau": torch.load(d / "branches" / "C.pt", weights_only=False)["cerveau"], "branche": "C",
                "generation": 1}, d / "cime.pt")
    (d / "journal_croissance.jsonl").write_text("", encoding="utf-8")
    (d / "derniers_examens.json").write_text(json.dumps({"A": {}, "B": {}, "C": {}, "D": {}}), encoding="utf-8")


def test_greffe_d_un_arbre_et_laisse_courir(tmp_path, monkeypatch):
    from collapsar.arbre.jardinier import Arbre
    from collapsar.ecole.precision import cerveau as C
    from collapsar.ecole.precision import coeur as L
    d = tmp_path / "or"
    _arbre(d)
    monkeypatch.setattr(R().mains, "suiveur", False, raising=False)
    monkeypatch.setattr(R().mains, "suiveur_unites", ["D1", "H4", "H1", "M15"], raising=False)
    cime_avant = torch.load(d / "branches" / "C.pt", weights_only=False)["cerveau"]
    # allumé mais pas greffé : le cœur refuse de démarrer
    monkeypatch.setattr(R().mains, "suiveur", True)
    with pytest.raises(SystemExit):
        L.main(["--dossier", str(d), "--appareil", "cpu", "--muet", "--generations", "1"])
    monkeypatch.setattr(R().mains, "suiveur", False)
    info = SV.greffer(d, dire=lambda *_: None)
    assert SV.active() and SV.greffee(d)
    assert (info["cime"], info["remplacee"], info["nouvelle"]) == ("C", "A", "E")     # A : la plus faible hors témoin
    assert (d / "archives" / "A.pt").exists() and (d / "archives" / "A_meilleur.pt").exists()
    assert (tmp_path / "or" / "sauvegardes").exists() and len(info["fichiers"]) == 9
    a = Arbre.charger(d / "arbre.json")
    assert [b.nom for b in a.vivantes()] == ["B", "C", "D", "E"] and a.branches["A"].cause == "coupée"
    assert a.cime == "C" and a.branches["E"].parents == ["C"]
    assert "A" not in json.loads((d / "derniers_examens.json").read_text(encoding="utf-8"))
    # toutes les branches se chargent dans le cerveau agrandi ; la cime garde ses anciennes sorties
    for f in sorted((d / "branches").glob("*.pt")) + [d / "cime.pt"]:
        C.Cerveau().load_state_dict(torch.load(f, weights_only=False)["cerveau"])
    c2 = torch.load(d / "branches" / "C.pt", weights_only=False)["cerveau"]
    for k, v in cime_avant.items():
        assert torch.equal(c2[k], v), k                                             # rien d'ancien ne bouge
    assert torch.all(c2["suiv.weight"] == 0)
    # la branche laisse_courir : la cime + ses penchants (rien encaisser à l'objectif 1, suiveur 90 %, laisser courir)
    pen = SV.LAISSE_COURIR["penchants"]
    e = torch.load(d / "branches" / "E.pt", weights_only=False)
    assert e["temperament"]["nom"] == "laisse_courir" and "C" in e["temperament"]["heritage"]
    assert e["temperament"]["penchants"] == pen
    b, bc = e["cerveau"]["tetes.bias"], c2["tetes.bias"]
    o2 = 6 + 5
    assert float(b[o2] - bc[o2]) == pytest.approx(pen["part0"])
    assert torch.equal(b[:o2], bc[:o2]) and torch.equal(b[o2 + 1:], bc[o2 + 1:])
    sb = e["cerveau"]["suiv.bias"]
    p = torch.softmax(sb[:SV.n_options()], -1)
    assert float(1 - p[0]) == pytest.approx(pen["suiveur_pct"] / 100, abs=1e-6)
    assert float(sb[SV.n_options()]) == pytest.approx(pen["courir"])
    for k in e["cerveau"]:
        if k not in ("tetes.bias", "suiv.bias"):
            assert torch.equal(e["cerveau"][k], c2[k]), k
    with pytest.raises(SystemExit):                                                 # une seule greffe
        SV.greffer(d, dire=lambda *_: None)
    # retour arrière : tout revient comme avant
    SV.defaire(d, dire=lambda *_: None)
    assert not SV.greffee(d) and (d / "branches" / "A.pt").exists() and not (d / "branches" / "E.pt").exists()
    assert torch.equal(torch.load(d / "branches" / "C.pt", weights_only=False)["cerveau"]["tetes.bias"],
                       cime_avant["tetes.bias"])


def test_penchant_d_une_seule_branche(tmp_path, monkeypatch):
    """« Fermer moins à la main » pour UNE branche (arbre arrêté) : sauvegarde, seul le biais « fermer » de cette branche
    (et de sa meilleure version) bouge, de la valeur demandée ; aucune autre branche ne change."""
    from collapsar.arbre.jardinier import Arbre
    from collapsar.ecole.precision.cerveau import FERMER
    d = tmp_path / "or"
    _arbre(d)
    monkeypatch.setattr(R().mains, "suiveur", False, raising=False)
    monkeypatch.setattr(R().mains, "suiveur_unites", ["D1", "H4", "H1", "M15"], raising=False)
    SV.greffer(d, dire=lambda *_: None)
    avant = {f.name: torch.load(f, weights_only=False)["cerveau"] for f in (d / "branches").glob("*.pt")}
    info = SV.pencher_branche(d, "E", {"fermer": -8.0}, dire=lambda *_: None)
    assert (tmp_path / "or" / "sauvegardes").exists() and info["fichiers"] == ["E.pt"]
    for f in (d / "branches").glob("*.pt"):
        apres = torch.load(f, weights_only=False)
        for k, v in avant[f.name].items():
            if f.name == "E.pt" and k == "tetes.bias":
                diff = apres["cerveau"][k] - v
                assert float(diff[FERMER]) == pytest.approx(-8.0) and float(diff.abs().sum()) == pytest.approx(8.0)
            else:
                assert torch.equal(apres["cerveau"][k], v), (f.name, k)
    e = torch.load(d / "branches" / "E.pt", weights_only=False)
    assert e["temperament"]["penchants"]["fermer"] == -8.0 and e["temperament"]["penchants"]["courir"] == 5.0
    assert Arbre.charger(d / "arbre.json").branches["E"].temperament["penchants"]["fermer"] == -8.0
