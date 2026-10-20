"""Verdict des zones du chef de projet avec le juge corrigé (16/10/2026 au soir) : nuits FTMO du moteur des zones
(triple au bon jour), frais crypto avec commission, cohérence du compte FTMO. Attendus calculés à la main."""
import numpy as np
import pandas as pd
import pytest

from collapsar.regarder.pistes import zones_retouchees as ZR
from collapsar.regarder.pistes import verdict_zones_corrige as VZ

H7 = 7 * 3600 * 10 ** 9


def _ny(s):
    """Heure du SERVEUR donnée en texte -> instant New York (ns), comme les bougies du laboratoire."""
    return np.array([pd.Timestamp(s).value - H7], np.int64)


def test_nuits_ftmo_triple_au_bon_jour():
    # mardi 11/01/2022 10h serveur -> jeudi 13/01 10h : minuits du mardi (1) et du mercredi (devises 3, indices 1)
    a, b = _ny("2022-01-11 10:00"), _ny("2022-01-13 10:00")
    assert ZR.nuits_ftmo("EURUSD", a, b)[0] == 4
    assert ZR.nuits_ftmo("XAUUSD", a, b)[0] == 4
    assert ZR.nuits_ftmo("USA500IDXUSD", a, b)[0] == 2
    # vendredi 14/01 10h -> lundi 17/01 10h : devises 1 (vendredi simple, week-end 0), indices 3 (vendredi triple)
    a, b = _ny("2022-01-14 10:00"), _ny("2022-01-17 10:00")
    assert ZR.nuits_ftmo("EURUSD", a, b)[0] == 1
    assert ZR.nuits_ftmo("USA500IDXUSD", a, b)[0] == 3
    # une semaine complète : 7 nuits partout ; sans symbole : nuits calendaires (ancienne règle)
    a, b = _ny("2022-01-10 10:00"), _ny("2022-01-17 10:00")
    assert ZR.nuits_ftmo("EURUSD", a, b)[0] == 7 and ZR.nuits_ftmo("USA500IDXUSD", a, b)[0] == 7
    assert ZR.nuits_ftmo(None, _ny("2022-01-14 10:00"), _ny("2022-01-17 10:00"))[0] == 3


def test_nuits_crypto_du_moteur_identiques_a_chef_crypto():
    from collapsar.regarder.pistes import chef_crypto as CC
    a = np.array([_ny("2022-01-12 10:00")[0]] * 3)
    b = np.array([_ny(s)[0] for s in ("2022-01-13 10:00", "2022-01-15 10:00", "2022-01-19 10:00")])
    assert list(CC.nuits(a, b)) == [1, 5, 7]                 # mercredi 1, jeudi 1, vendredi 3, week-end 0, lundi/mardi
    assert list(VZ.nuits(None, True, a, b)) == [1, 5, 7]


def test_frais_crypto_du_verdict_commission_comprise():
    assert VZ.frais_crypto("BTC") == pytest.approx(0.00065 + 0.0000122)        # 0,066 % aller-retour
    assert VZ.frais_crypto("ETH") == pytest.approx(0.00065 + 0.000248)         # 0,090 %
    assert VZ.frais_crypto("ADA") == pytest.approx(0.00065 + 0.00031)          # 0,096 %


def test_un_trade_frais_et_nuits_a_la_main():
    """Un achat rempli à 100 (frais 0,1 %, facteur 1), risque 1 : TP1 (102) touché, puis stop au prix 99 pour les
    deux autres tiers -> (2 - 1 - 1) / 3 avant frais ; frais : 0,05 (entrée) + 0,05 / 3 (objectif) + 2 x 0,1 / 3."""
    t = pd.DataFrame([{"fill_ny": _ny("2022-01-11 10:00")[0], "entree": pd.Timestamp("2022-01-11 03:00"), "sens": 1,
                       "prix": 100.0, "risque": 1.0, "frais": 0.001, "facteur": 1.0,
                       "R_sans_nuit_0": 0.0, "R_sans_nuit_1": 0.0}])
    sorties = [_ny("2022-01-11 12:00")[0], _ny("2022-01-13 12:00")[0], _ny("2022-01-13 12:00")[0]]
    prix, natures = [102.0, 99.0, 99.0], [0, 1, 1]
    for g in (0, 1):
        s = 1 if g == 0 else -1
        part = []
        for q in range(3):
            t[f"t{g}{q}"], t[f"p{g}{q}"], t[f"k{g}{q}"] = sorties[q], prix[q], natures[q]
            part.append(((prix[q] - 100.0) * s - 100.0 * 0.001 * (1.0 if natures[q] == 1 else 0.5)) / 3.0)
            t[f"r{g}{q}"] = part[-1]
        t[f"R_sans_nuit_{g}"] = sum(part) - 0.05
    t = VZ.finir(t, None, True)                            # crypto : 30 %/an des deux côtés, triple le vendredi
    attendu_nuit = 0.30 / 360 * 100.0 * (0 + 2 + 2) / 3.0  # tiers 1 : 0 nuit ; tiers 2 et 3 : mardi + mercredi
    assert t["R"].iloc[0] == pytest.approx((2 - 1 - 1) / 3 - 0.05 - 0.05 / 3 - 0.2 / 3 - attendu_nuit)
    assert t["c0"].iloc[0] == pytest.approx(0.05)
    assert (t[["r00", "r01", "r02"]].sum(axis=1) - t["c0"] - t["R"]).abs().max() < 1e-12


def _compte_un_trade(r_parts, lo, hi, cl, sens=1, risque=0.005):
    fill = np.array([96 * 3 + 40], np.int64)                         # un mercredi, en journée
    ex = np.full((1, 2, 3), fill[0] + len(cl) - 1, np.int64)
    rp = np.array([[r_parts, [-x for x in r_parts]]], float)
    a = (fill, ex, rp, np.zeros(1), np.array([sens], np.int64), np.array([0.01]), np.array([30.0]),
         np.zeros(1, np.int64), np.array([len(cl)], np.int64), np.asarray(lo, np.float32), np.asarray(hi, np.float32),
         np.asarray(cl, np.float32))
    return a


def test_compte_un_trade_gagnant_et_son_jumeau():
    a = _compte_un_trade([1.0, 1.0, 1.0], [-0.5, 0.0, 2.0], [0.5, 2.0, 3.0], [0.0, 1.5, 3.0])
    r = VZ.simuler(*a, np.ones(1, np.int64), 0.005, 4, 0, 96 * 10, 0)
    assert r[1] == pytest.approx(100_000 * (1 + 0.005 * 3.0))             # +3 R à 0,5 % du solde
    assert r[2] == pytest.approx(-0.005 * 0.5 / 1.0)                       # pire point : -0,5 R au 1er quart d'heure
    r = VZ.simuler(*a, -np.ones(1, np.int64), 0.005, 4, 0, 96 * 10, 0)
    assert r[1] == pytest.approx(100_000 * (1 - 0.005 * 3.0))              # le jumeau vit le chemin inverse
    assert r[2] == pytest.approx(-0.005 * 3.0, rel=1e-6)


def test_challenge_mort_au_pire_point_meme_si_la_cloture_remonte():
    # un trade à 6 % de risque (le pire point touche -5 % dans la journée, la clôture finit à +0)
    a = _compte_un_trade([0.0, 0.0, 0.0], [-0.9, 0.0], [0.0, 0.1], [0.0, 0.0])
    r = VZ.simuler(*a, np.ones(1, np.int64), 0.06, 4, 0, 96 * 10, 1)
    assert r[0] == 1                                                        # mort à l'étape 1
    r = VZ.simuler(*a, np.ones(1, np.int64), 0.05, 4, 0, 96 * 10, 1)
    assert r[0] == 3                                                        # -4,5 % : vivant, inachevé
