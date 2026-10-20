"""Corrections de l'audit du 16/10/2026, chantier B (bande_bruit, orb, bitcoin_journee) : petits cas calculés à la main.
Défauts 2, 3, 6, 7, 8, 9, 10 et point 4 de collapsar/vie/audit/rapport.md."""
import math

import numpy as np
import pandas as pd
import pytest

from collapsar.mains.fiches import fiche
from collapsar.regarder import bande_bruit as bb
from collapsar.regarder import orb
from collapsar.regarder.pistes import bitcoin_journee as bj

JOURS40 = pd.bdate_range("2021-01-04", periods=40)


def _t_bj():
    """Les mêmes 40 trades au format de bitcoin_journee."""
    return _t_bb().rename(columns={"brut": "r_prix"}).assign(quarts=4, adv_achat=0.0, adv_vente=0.0)


def _t_bb():
    """40 trades sur 40 jours : 20 jours calmes (agitation 1 %, levier 1 à cible 1 %) à +0,2 %, 20 jours agités
    (agitation 4 %, levier 0,25) à -0,4 %. Brut non pondéré : moyenne -0,1 % ; compte taillé : +0,05 %/jour."""
    calme = np.arange(40) % 2 == 0
    return pd.DataFrame({"jour": JOURS40, "sens": 1, "m_entree": 0, "brut": np.where(calme, 0.002, -0.004),
                         "frais": 0.0, "agitation": np.where(calme, 0.01, 0.04),
                         "levier_par_cible": np.minimum(bb.LEVIER_MAX / 0.02, 1 / np.where(calme, 0.01, 0.04))})


# ------------------------------------------------------------------ défaut 2 : force du compte taillé
def test_force_bande_bruit_ponderee_par_la_taille():
    x = bb.bilan(_t_bb(), JOURS40)
    # gains taillés : 20 x +0,002 et 20 x -0,001 -> moyenne 0,0005, écart type 0,0015 x racine(40/39) -> racine(39) / 3
    assert x["force_avant_frais"] == pytest.approx(math.sqrt(39) / 3, rel=1e-9)
    # ancienne force (non pondérée) : 20 x +0,002 et 20 x -0,004 -> -racine(39) / 3
    assert x["force_brute"] == pytest.approx(-math.sqrt(39) / 3, rel=1e-9)


def test_force_bitcoin_ponderee_par_la_taille():
    t = _t_bj()
    x = bj.bilan(t, JOURS40, mu15=0.0, avec_challenges=False)
    assert x["force"] == pytest.approx(math.sqrt(39) / 3, rel=1e-9)
    assert x["force_sans_derive"] == pytest.approx(math.sqrt(39) / 3, rel=1e-9)
    assert x["force_brute"] == pytest.approx(-math.sqrt(39) / 3, rel=1e-9)


def test_force_compte_les_jours_sans_trade_et_somme_les_trades_du_jour():
    # deux trades le même jour s'additionnent ; un jour sans trade compte pour 0
    j = pd.bdate_range("2021-01-04", periods=3)
    t = pd.DataFrame({"jour": [j[0]] * 2 + [j[1]] * 20, "brut": [0.001, 0.002] + [0.001] * 20, "frais": 0.0,
                      "sens": 1, "levier_par_cible": 100.0})       # levier 1 à cible 1 %
    x = bb.bilan(t, j)
    s = np.array([0.003, 0.02, 0.0])
    assert x["force_avant_frais"] == pytest.approx(s.mean() / s.std(ddof=1) * math.sqrt(3), rel=1e-9)


# ------------------------------------------------------------------ défaut 3 : séances trouées écartées
def _df_minutes(jours_minutes: dict) -> pd.DataFrame:
    lignes = []
    for jour, n in jours_minutes.items():
        t0 = pd.Timestamp(jour) + pd.Timedelta(hours=9, minutes=30)
        for m in range(n):
            lignes.append((t0 + pd.Timedelta(minutes=m), 100.0, 100.1, 99.9, 100.0, np.nan))
    return pd.DataFrame(lignes, columns=["ny", "open", "high", "low", "close", "ecart"])


def test_seances_trouees_ecartees():
    assert orb.minutes_min(0.05) == 371 and orb.minutes_min(orb.MANQUE_ANCIEN) == 300
    df = _df_minutes({"2021-01-04": 390, "2021-01-05": 371, "2021-01-06": 370, "2021-01-07": 300})
    s = orb.seances(df)
    assert sorted(s) == [pd.Timestamp("2021-01-04"), pd.Timestamp("2021-01-05")], "19 minutes manquantes : gardée ; 20 : écartée"
    assert len(orb.seances(df, orb.MANQUE_ANCIEN)) == 4, "l'ancien réglage gardait tout dès 300 minutes"


# ------------------------------------------------------------------ défaut 6 : réussis parmi les terminés
def test_challenge_reussis_parmi_les_termines():
    g = np.zeros(30)
    g[0], g[1] = 0.10, 0.05          # départ 0 : phase 1 puis phase 2 réussies
    g[10] = -0.06                    # départ 10 : mort à -6 % sur un jour ; départ 20 : données finies -> inachevé
    for e in (bb.challenge(pd.Series(g)), bj.challenge(g, np.minimum(g, 0))):
        assert e["reussis_pct"] == pytest.approx(100 / 3) and e["morts_pct"] == pytest.approx(100 / 3)
        assert e["termines_n"] == 2 and e["inacheves_n"] == 1
        assert e["reussis_parmi_termines_pct"] == pytest.approx(50.0)
    assert bb.challenge(pd.Series(np.zeros(5)))["reussis_parmi_termines_pct"] is None


# ------------------------------------------------------------------ défaut 7 : années du calendrier
def test_annees_du_calendrier_bande_bruit():
    jours = pd.bdate_range("2015-01-01", "2016-12-31")             # 522 jours ouvrés, 2 années
    assert len(jours) == 522
    an = (pd.Timestamp("2016-12-30") - pd.Timestamp("2015-01-01")).days + 1
    assert bb.annees(jours) == pytest.approx(an / 365.25) and bb.annees(jours) == pytest.approx(2.0, abs=0.01)
    t = pd.DataFrame({"jour": jours, "brut": 0.0001, "frais": 0.0, "sens": 1, "levier_par_cible": 100.0})
    x = bb.bilan(t, jours)
    assert x["gain_pct_an_cible1"] == pytest.approx(522 * 0.01 / (an / 365.25), rel=1e-9)   # et pas 5,22 / (522/252)


# ------------------------------------------------------------------ défaut 8 : -5 % jugé au pire point de la journée
def _t_pire(lignes):
    return pd.DataFrame(lignes, columns=["jour", "marche", "sens", "m_entree", "brut", "adv_achat", "adv_vente"]).assign(
        frais=0.0, levier_par_cible=100.0)                           # levier 1 à cible 1 %


def test_pire_point_du_jour_et_challenge():
    j = pd.bdate_range("2021-01-04", periods=10)
    # achat clos à +1 % mais descendu à -6 % pendant le trade
    t = _t_pire([(j[0], "US500", 1, 0, 0.01, -0.06, -0.02)])
    g, w = bb.journalier_pire(t, 0.01)
    assert g.iloc[0] == pytest.approx(0.01) and w.iloc[0] == pytest.approx(-0.06)
    g, w = g.reindex(j, fill_value=0.0), w.reindex(j, fill_value=0.0)
    assert bb.challenge(g)["morts_pct"] == 0, "à la clôture seule, rien ne meurt"
    assert bb.challenge(g, w=w)["morts_pct"] == 100, "au pire point (-6 %), le départ du jour 0 meurt"
    # sens retourné (jumeau) : c'est l'écart défavorable de la vente qui compte
    _, w_inv = bb.journalier_pire(t, 0.01, np.array([-1]))
    assert w_inv.iloc[0] == pytest.approx(-0.02)


def test_pire_point_gains_deja_faits_et_plusieurs_marches():
    j = pd.Timestamp("2021-01-04")
    t = _t_pire([(j, "US500", 1, 0, 0.02, 0.0, -0.01),             # +2 % réalisés d'abord
                 (j, "US500", -1, 120, -0.01, -0.03, -0.05),      # puis une vente qui descend à -5 %
                 (j, "NAS100", 1, 30, 0.0, -0.03, 0.0)])          # autre marché : -3 % au pire
    g, w = bb.journalier_pire(t, 0.01)
    assert g.iloc[0] == pytest.approx(0.01)
    # US500 : min(0 - 0,0 ; 0,02 - 0,05) = -0,03 ; NAS100 : -0,03 ; additionnés -> -0,06
    assert w.iloc[0] == pytest.approx(-0.06)


def test_moteur_bande_bruit_pire_point_coherent():
    rng = np.random.default_rng(3)
    n = 40
    C = 100 * np.exp(np.cumsum(rng.normal(0, 0.0012, (n, 390)), axis=1) + np.cumsum(rng.normal(0, 0.01, n))[:, None])
    O = np.c_[C[:, :1], C[:, :-1]]
    H, L = np.maximum(O, C) * 1.0003, np.minimum(O, C) * 0.9997
    t = bb.trades_matrice(pd.bdate_range("2021-01-04", periods=n), O, H, L, C, 0.0)
    assert len(t) > 5
    assert (t["adv_achat"] <= 0).all() and (t["adv_vente"] <= 0).all()
    ach, ven = t[t["sens"] > 0], t[t["sens"] < 0]
    assert (ach["brut"] >= ach["adv_achat"] - 1e-12).all() and (ven["brut"] >= ven["adv_vente"] - 1e-12).all()


# ------------------------------------------------------------------ défaut 9 : commission crypto dans a et b
def test_frais_bitcoin_avec_commission():
    assert bj.COMMISSION_CRYPTO == pytest.approx(0.00065)
    assert bj.FRAIS["a_ftmo_0.0015%+comm"] == pytest.approx(0.000012 + 0.00065)        # sans le x 1,25 (audit)
    assert bj.FRAIS[bj.FRAIS_REGLE] == pytest.approx(0.0001 + 0.00065)
    assert bj.FRAIS["c_tres_prudent_0.03%+comm"] == pytest.approx(0.0003 + 0.00065)
    assert bj.FRAIS["d_fiche_0.1%"] == pytest.approx(fiche("BTCUSD").frais), "colonne d gardée, sans le x 1,25"


# ------------------------------------------------------------------ défaut 10 : mois du calendrier (bitcoin)
def test_mois_du_calendrier_bitcoin():
    tous = pd.bdate_range("2022-01-03", "2022-12-30")
    troue = tous[::2]                                              # la moitié des jours sans données
    assert bj.mois_calendrier(troue) == pytest.approx(bj.mois_calendrier(tous), rel=1e-2)
    assert len(troue) / bj.JOURS_AN * 12 < 6.1, "l'ancienne formule (jours tradés / 261 x 12) aurait compté 6 mois"
    assert bj.mois_calendrier(tous) == pytest.approx(((tous[-1] - tous[0]).days + 1) / (365.25 / 12))
    t = pd.DataFrame({"jour": troue[:30], "sens": 1, "r_prix": 0.001, "agitation": 0.01, "quarts": 4, "adv_achat": 0.0, "adv_vente": 0.0})
    x = bj.bilan(t, troue, 0.0, avec_challenges=False)
    m = bj.mois_calendrier(troue)
    nom = "c_tres_prudent_0.03%+comm"
    assert x["frais"][nom]["gain_pct_mois_cible1"] == pytest.approx(30 * (0.001 - 0.0003 - 0.00065) / m * 100, rel=1e-9)


# ------------------------------------------------------------------ point 4 : cible 2 % et plafond du tricheur
def test_cible2_et_tricheur_bande_bruit():
    x = bb.bilan(_t_bb(), JOURS40)
    an = bb.annees(JOURS40)
    # aucun plafond de levier touché : la cible 2 % double exactement la cible 1 %
    assert x["gain_pct_mois_cible2"] == pytest.approx(2 * x["gain_pct_mois_cible1"], rel=1e-9)
    # tricheur : 20 x 1 x 0,002 + 20 x 0,25 x 0,004 = 0,06 sur la période
    assert x["plafond_tricheur_pct_mois_cible1"] == pytest.approx(0.06 / an / 12 * 100, rel=1e-9)
    assert x["plafond_tricheur_pct_mois_cible2"] == pytest.approx(0.12 / an / 12 * 100, rel=1e-9)


def test_cible2_et_tricheur_bitcoin():
    t = _t_bj()
    x = bj.bilan(t, JOURS40, mu15=0.0, avec_challenges=False)
    m, f = bj.mois_calendrier(JOURS40), bj.FRAIS[bj.FRAIS_REGLE]
    # cible 2 % : exposition 1 x 2 -> plafond 1 (jours calmes), 0,25 x 2 = 0,5 (jours agités)
    attendu2 = 20 * 1.0 * (0.002 - f) + 20 * 0.5 * (-0.004 - f)
    assert x["frais"][bj.FRAIS_REGLE]["gain_pct_mois_cible2"] == pytest.approx(attendu2 / m * 100, rel=1e-9)
    tr1 = 20 * 1.0 * (0.002 - f) + 20 * 0.25 * (0.004 - f)
    assert x["plafond_tricheur"]["pct_mois_cible1"] == pytest.approx(tr1 / m * 100, rel=1e-9)
