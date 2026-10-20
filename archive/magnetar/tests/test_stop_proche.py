"""Tests des STOPS PROCHES (19/10/2026, collapsar/ecole/precision/stop_proche.py + cerveau.politique) :
- sans réglage (toutes les branches, HYPERNOVA) : rien ne change ; un plafond immense donne EXACTEMENT les mêmes choix,
  probabilités et niveaux que sans plafond (mêmes tirages à graine égale) ;
- avec un plafond : chaque stop posé est à au plus X agitations de l'entrée, marge comprise ; un plafond minuscule
  interdit toute ouverture ; les probabilités relues sont celles des choix tirés (apprentissage cohérent) ;
- greffe d'un arbre : sauvegarde, la plus faible archivée, branche « precision » = copie exacte de la cime (journal
  compris), plafond dans son tempérament et dans son cerveau au réveil du cœur ; retour arrière.
Depuis Test_IA : $env:CUDA_VISIBLE_DEVICES='-1'; venv_gpu\\Scripts\\python.exe -m pytest collapsar/tests/test_stop_proche.py -q
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest
import torch

from test_ecole_precision import monde_invente  # noqa: F401  (fixture partagée)


def _cerveau(graine=4):
    from collapsar.ecole.precision import cerveau as C
    torch.manual_seed(graine)
    net = C.Cerveau()
    with torch.no_grad():                                    # des têtes « apprises » qui ouvrent souvent
        net.tetes.weight.normal_(0, 0.05)
        net.tetes.bias.normal_(0, 0.5)
        net.tetes.bias[C.GARDER] = -3.0
        net.stop.c.weight.normal_(0, 0.5)
    return net


def _regard(U, net, graine, B=64):
    """Un regard de B comptes : choix tirés, niveaux, probabilités ; puis relecture des mêmes choix."""
    from collapsar.ecole.precision import cerveau as C
    from collapsar.ecole.precision import jeu as JEU
    tb = JEU.Table(U, B, 1)
    dep = np.random.default_rng(1).integers(U.premier[0], U.T - 400, B)
    tb.demarrer(np.ones(B, bool), np.zeros((B, 1), np.int64), dep)
    torch.manual_seed(graine)
    with torch.no_grad():
        (choix, lp, lp_exec, hasard, valeur, lv), (t, cols, fc, pos) = tb.regarder(net, np.arange(B))
        s = tb.vue.structure(t, cols)
        fm = torch.cat([tb.vue.caracteristiques(s), pos], -1)
        _, lp2, lpe2, _, _, _ = C.politique(net, s, fm, fc, pos, choix, True)
    return choix, lp, lp_exec, lv, s["A"], lp2, lpe2


def _univers():
    from collapsar.ecole.precision.univers import Univers
    return Univers([("EURUSD", False)], pd.Timestamp("2019-03-01"), pd.Timestamp("2019-07-01"), "cpu")


def test_reglage_absent_rien_ne_change():
    from collapsar.ecole.precision import cerveau as C
    net = C.Cerveau()
    assert net.stop_max_agitation is None
    assert "stop_max_agitation" not in str(list(net.state_dict()))         # pas un poids
    for t in (None, {}, {"nom": "x"}, {"precision": None}, {"precision": {}}):
        assert C.regler_precision(net, t).stop_max_agitation is None
    assert C.regler_precision(net, {"precision": {"stop_max_agitation": 0.4}}).stop_max_agitation == 0.4


def test_plafond_immense_memes_choix_que_sans(monde_invente):
    net = _cerveau()
    U = _univers()
    c0, lp0, lpe0, lv0, *_ = _regard(U, net, 7)
    net.stop_max_agitation = 1e9
    c1, lp1, lpe1, lv1, *_ = _regard(_univers(), net, 7)
    for k in c0:
        assert torch.equal(c0[k], c1[k]), k
    for k in lv0:
        assert torch.equal(torch.nan_to_num(lv0[k].float(), nan=-7.0), torch.nan_to_num(lv1[k].float(), nan=-7.0)), k
    assert torch.equal(lp0, lp1) and torch.equal(lpe0, lpe1)
    assert bool(lv0["ouvre"].any())


@pytest.mark.parametrize("cap", [0.3, 0.6, 1.5])
def test_stops_sous_le_plafond(monde_invente, cap):
    net = _cerveau()
    _, _, _, lv_libre, A0, _, _ = _regard(_univers(), net, 11, B=128)
    net.stop_max_agitation = cap
    choix, lp, lpe, lv, A, lp2, lpe2 = _regard(_univers(), net, 11, B=128)
    o = lv["ouvre"]
    assert bool(o.any())
    d = (lv["sig"] * (lv["entree"] - lv["stop"]) / A)[o]
    assert float(d.max()) <= cap + 1e-5 and float(d.min()) > 0
    d_libre = (lv_libre["sig"] * (lv_libre["entree"] - lv_libre["stop"]) / A0)[lv_libre["ouvre"]]
    assert float(d_libre.max()) > cap                                     # sans plafond, des stops plus lointains
    assert torch.allclose(lp, lp2) and torch.allclose(lpe, lpe2)          # relecture = tirage


def test_plafond_minuscule_aucune_ouverture(monde_invente):
    net = _cerveau()
    net.stop_max_agitation = 1e-9
    choix, lp, lpe, lv, A, lp2, lpe2 = _regard(_univers(), net, 3, B=128)
    assert not bool(lv["ouvre"].any())
    assert torch.allclose(lp, lp2)


def test_greffe_d_un_arbre_et_retour(tmp_path, monkeypatch):
    from collapsar.arbre.jardinier import Arbre
    from collapsar.ecole.precision import cerveau as C
    from collapsar.ecole.precision import coeur as CO
    from collapsar.ecole.precision import stop_proche as SP
    from test_suiveur import _arbre
    d = tmp_path / "vie"
    _arbre(d)                                       # A, B, C (cime), D (la plus faible : témoin)
    avant = {f.name: f.read_bytes() for f in (d / "branches").glob("*.pt")}
    info = SP.greffer(d, 0.4, dire=lambda *_: None)
    assert info["remplacee"] == "D" and info["cime"] == "C" and info["plafond_agitation"] == 0.4
    a = Arbre.charger(d / "arbre.json")
    nb = info["branche"]
    assert a.branches["D"].morte is not None and (d / "archives" / "D.pt").exists()
    assert a.branches[nb].temperament["precision"] == {"stop_max_agitation": 0.4}
    assert a.branches[nb].temperament["nom"] == "precision"
    e = torch.load(d / "branches" / f"{nb}.pt", weights_only=False)
    ec = torch.load(d / "branches" / "C.pt", weights_only=False)
    for k, v in ec["cerveau"].items():              # copie EXACTE des poids de la cime
        assert torch.equal(e["cerveau"][k], v), k
    br = CO.Branche(nb, e["temperament"], "cpu", e)
    assert br.net.stop_max_agitation == 0.4
    autre = CO.Branche("C", ec.get("temperament") or a.branches["C"].temperament, "cpu", ec)
    assert autre.net.stop_max_agitation is None
    for f in ("A.pt", "B.pt", "C.pt"):              # les autres branches ne bougent pas
        assert (d / "branches" / f).read_bytes() == avant[f]
    with pytest.raises(SystemExit):
        SP.greffer(d, 0.4, dire=lambda *_: None)    # une seule fois
    SP.defaire(d, dire=lambda *_: None)
    assert not (d / SP.FICHIER).exists() and not (d / "archives" / "D.pt").exists()
    assert {f.name: f.read_bytes() for f in (d / "branches").glob("*.pt")} == avant
