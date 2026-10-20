"""Tests de la piste « scalping de l'or » (collapsar/regarder/pistes/scalping_or.py)."""
from types import SimpleNamespace

import numpy as np
import pandas as pd

from collapsar.regarder.pistes import scalping_or as so


def tranche(o, h, l, c, e=0.0, g=0.0, t0=0):
    n = len(o)
    return SimpleNamespace(T=list(range(t0, t0 + n)), O=list(o), H=list(h), L=list(l), C=list(c), E=[e] * n,
                           G=[g] * n)


def test_seuil():
    assert abs(so.SEUIL - 3.79) < 0.01


def test_stop_et_objectif_meme_minute_compte_le_stop():
    s = tranche([100, 100], [100.5, 105], [99.5, 95], [100, 100])
    sortie, i, motif, _, _ = so.suivre(s, 1, 1, 100.0, 100.0, 2.0, 103.0, None, None, 10 ** 9, False, False)
    assert motif == "stop" and i == 1 and sortie == 98.0


def test_glissement_dur_pire_de_la_minute():
    s = tranche([100, 99], [100.5, 99.5], [99.5, 96], [100, 97], g=0.1)
    sortie, _, motif, _, ideal = so.suivre(s, 1, 1, 100.0, 100.0, 2.0, None, None, None, 10 ** 9, True, False)
    assert motif == "stop" and abs(sortie - 95.9) < 1e-9 and ideal == 98.0


def test_stop_a_l_entree_puis_suiveur():
    # monte de +1 R (stop -> entrée), puis +3, puis retombe : sortie au suiveur (meilleur 106 - 1,5 = 104,5)
    o = [100, 101, 103, 106, 105]
    h = [100, 102.1, 104, 106, 105]
    l = [100, 100.5, 102.5, 105, 104]
    s = tranche(o, h, l, o)
    sortie, i, motif, _, ideal = so.suivre(s, 0, 1, 100.0, 100.0, 2.0, None, 1.0, 1.5, 10 ** 9, False, False)
    assert motif == "stop" and i == 4 and ideal == 104.5


def test_jumeau_sans_frais_somme_nulle():
    rng = np.random.default_rng(0)
    c = 100 + np.cumsum(rng.normal(0, 0.1, 300))
    s = tranche(c, c + 0.05, c - 0.05, c, t0=0)
    x = so.couple(s, 5, 1, c[5], c[5], 50.0, None, None, None, 200, False, True, 0, "T")
    assert abs(x["R"] + x["R_inv"]) < 1e-3          # seule la commission (minuscule) les sépare


def test_heure_serveur_vers_new_york():
    serveur = pd.Timestamp("2020-01-10 15:30")      # emploi américain : 8h30 New York
    ny = serveur - pd.Timedelta(minutes=so.SERVEUR_MOINS_NY)
    assert (ny.hour, ny.minute) == (8, 30)


def test_annonces_proximite():
    t = np.arange(0, 60)
    f, p15, p2 = so.proximite_annonces(t, np.array([30]))
    assert f[28] == 5 and f[35] == 5 and f[40] == 2 and f[50] == 1 and p15[15] and not p15[14] and p2[32] and not p2[33]


def test_etiquettes():
    assert so.etiquette({"force": 4.0, "R_moyen": 0.1}, {"R_moyen": 0.05}) == "🟢"
    assert so.etiquette({"force": 4.0, "R_moyen": 0.1}, {"R_moyen": -0.05}) == "🟡"
    assert so.etiquette({"force": 2.5, "R_moyen": 0.1}, {"R_moyen": 0.1}) == "🟡"
    assert so.etiquette({"force": 1.0, "R_moyen": 0.1}, {"R_moyen": 0.1}) == "⚪"
