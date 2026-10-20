"""Chantier C de l'audit du 16/10/2026 (défauts 5, 11, 12) : frais sans le x 1,25 ni la demi-fiche des entrées au
marché (glissement des stops gardé), nuit triple du mercredi OU du vendredi selon le marché, levier du compte FTMO
Swing mesuré. Chaque attendu est calculé à la main."""
import json

import numpy as np
import pandas as pd
import pytest
import torch

from collapsar.mains import frais_ftmo, horloge
from collapsar.mains.fiches import Fiche, fiche
from collapsar.mains.horloge import Horloge, nuits_payees
from collapsar.mains.simulateur import CAPITAL, Comptes, Ordres

TABLE = json.loads(frais_ftmo.MESURE.read_text(encoding="utf-8"))["marches"]


@pytest.fixture(autouse=True)
def sans_releve(monkeypatch):
    from collapsar.mains import fiches
    monkeypatch.setattr(fiches, "_reelles", lambda: {})


def _df(debut, n, prix=1.0):
    t = pd.date_range(debut, periods=n, freq="15min")
    return pd.DataFrame({"time": t, "open": prix, "high": prix, "low": prix, "close": prix, "volume": 1.0})


def _o(**k):
    return Ordres(**{n: torch.tensor([[v]], dtype=torch.float64) for n, v in k.items()})


# ---------------------------------------------------------------- frais (défaut 5)
def test_frais_ftmo_sans_marge_de_prudence(monkeypatch):
    assert frais_ftmo.MARGE_PRUDENCE == 1.0 and frais_ftmo.GLISSEMENT == 1.0
    monkeypatch.setattr(frais_ftmo, "_prix_au_releve", lambda sym: 4000.0)
    e = TABLE["XAUUSD"]["ecart_pct"] / 100
    assert frais_ftmo.frais("XAUUSD", 4000.0) == pytest.approx(e + 0.000014)        # écart + commission métaux
    assert frais_ftmo.frais("XAUUSD", 2000.0) == pytest.approx(2 * e + 0.000014), "écart constant en points"
    e = TABLE["BTCUSD"]["ecart_pct"] / 100
    assert frais_ftmo.frais("BTCUSD", 4000.0) == pytest.approx(e + 0.00065)          # commission crypto PAS multipliée
    assert float(frais_ftmo.frais("EURUSD", 1.1)) == pytest.approx(0.00006)          # devises : la fiche


def test_la_marge_de_prudence_ne_touche_que_l_ecart(monkeypatch):
    monkeypatch.setattr(frais_ftmo, "_prix_au_releve", lambda sym: 4000.0)
    monkeypatch.setattr(frais_ftmo, "MARGE_PRUDENCE", 1.25)
    e = TABLE["BTCUSD"]["ecart_pct"] / 100
    assert frais_ftmo.frais("BTCUSD", 4000.0) == pytest.approx(1.25 * e + 0.00065)


def test_frais_crypto_des_pistes():
    from collapsar.regarder.pistes import chef_compte_ftmo as CF, compte_combine as CB, crypto_flux as cf
    assert cf.frais("BTCUSDT") == pytest.approx(0.00065 + 0.0000122)                 # 0,0662 % (avant 0,083 %)
    assert cf.frais("ETHUSDT") == pytest.approx(0.00065 + 0.000248)                  # 0,0898 % (avant 0,112 %)
    assert cf.frais("SOLUSDT") == pytest.approx(0.00065 + 0.00031)                   # 0,096 % (avant 0,12 %)
    assert CF.frais("BTC") == pytest.approx(0.00065 + 0.000015)
    assert CF.frais("ADA") == pytest.approx(0.00065 + 0.0003)
    assert CB.frais_rt("ETH") == pytest.approx(0.00065 + 0.00025)


def test_cout_du_labo_smc_stop_garde_marche_retire():
    from collapsar.regarder.smc import noyaux as K
    assert K.GLISSEMENT_STOP == 0.5 and K.GLISSEMENT_MARCHE == 0.0
    # entrée 100, fiche 0,1 % : demi-fiche entrée 0,05 + demi-fiche sortie 0,05 + stop 0,05 ; entrée au marché : + 0
    assert K._cout(100.0, 0.001, 1.0, True, True) == pytest.approx(0.15)
    assert K._cout(100.0, 0.001, 1.0, False, True) == pytest.approx(0.10)
    assert K._cout(100.0, 0.001, 1.16, False, False) == pytest.approx(100 * 0.001 * (0.5 * 1.16 + 0.5))


def test_nono_sortie_au_marche_sans_glissement():
    from collapsar.regarder.smc import nono
    o = np.array([100.0, 100.0, 100.0])
    c = np.array([99.9, 99.9, 99.9])
    m = np.array([100.0])
    # achat à 100, risque 1, clôture de la bougie d'entrée sous l'entrée -> sortie B au marché à 99,9
    r, cr = nono.trade_nono(o, o + 0.1, o - 0.1, c, m, m, m, 0, 0, 0, 1, 100.0, 1.0, 3.0, 4.0, True, 5, 0.001, 1.0)
    assert cr == pytest.approx(0.05 + 0.05)                  # demi-fiche entrée limite + demi-fiche sortie (avant 0,15)
    assert r == pytest.approx(-0.1 - 0.1)


def test_smc_combinaisons_entree_au_marche():
    from collapsar.regarder.pistes import smc_combinaisons as SC
    o = np.array([100.0, 100.0, 100.0])
    h = np.array([100.0, 100.5, 100.0])
    l = np.array([100.0, 98.0, 100.0])
    c = np.array([100.0, 99.0, 100.0])
    # achat à 100, risque 1, objectif 2 : stop touché à la bougie 1 -> frais 0,5 + 0,5 + 0,5 (stop) = 1,5 fiche
    r, k = SC.suivre(o, h, l, c, 0, 2, 1, 100.0, 1.0, 2.0, 0.001)
    assert k == 1 and r == pytest.approx(-1.0 - 1.5 * 0.1)
    h2 = np.array([100.0, 102.5, 100.0])
    l2 = np.array([100.0, 99.5, 100.0])
    r, k = SC.suivre(o, h2, l2, c, 0, 2, 1, 100.0, 1.0, 2.0, 0.001)
    assert k == 1 and r == pytest.approx(2.0 - 1.0 * 0.1)                           # objectif : 1 fiche (avant 1,5)
    assert SC.FRAIS_CRYPTO["BTCUSD"] == pytest.approx(0.0006622)


# ---------------------------------------------------------------- nuits (défaut 11)
def test_nuits_payees_calcul_a_la_main():
    t = pd.DatetimeIndex(["2022-01-10 12:00", "2022-01-11 00:15", "2022-01-12 00:15", "2022-01-13 00:15",
                          "2022-01-14 00:15", "2022-01-15 00:15", "2022-01-16 00:15", "2022-01-17 00:15"])
    # minuits franchis : lundi, mardi, mercredi, jeudi, vendredi, samedi, dimanche (lundi = 0)
    assert list(nuits_payees(t, 4)) == [0, 1, 1, 1, 1, 3, 0, 0], "triple le vendredi, samedi et dimanche gratuits"
    assert list(nuits_payees(t, 2)) == [0, 1, 1, 3, 1, 1, 0, 0], "triple le mercredi"
    trou = pd.DatetimeIndex(["2022-01-14 23:45", "2022-01-17 00:15"])          # vendredi soir -> lundi (week-end)
    assert list(nuits_payees(trou, 2)) == [0, 1] and list(nuits_payees(trou, 4)) == [0, 3]


def test_horloge_triple_par_marche_7_nuits_par_semaine():
    donnees = {"BTCUSD": _df("2022-01-10 00:00", 7 * 96 + 2), "EURUSD": _df("2022-01-10 00:00", 7 * 96 + 2)}
    h = Horloge(donnees, ["BTCUSD", "EURUSD"])
    assert h.regle_nuit.tolist() == [2, 1], "BTC : vendredi (FTMO jour_triple 5), euro-dollar : mercredi (3)"
    n = h.nuits(torch.arange(h.T))
    assert n.sum(0).tolist() == [7.0, 7.0]
    i_ven = int(np.flatnonzero((h.temps.dayofweek == 5) & (h.temps.hour == 0) & (h.temps.minute == 0))[0])
    i_jeu = int(np.flatnonzero((h.temps.dayofweek == 3) & (h.temps.hour == 0) & (h.temps.minute == 0))[0])
    assert n[i_ven].tolist() == [3.0, 1.0] and n[i_jeu].tolist() == [1.0, 3.0]


def test_ecole_qui_remplace_nuit_garde_sa_regle():
    donnees = {"BTCUSD": _df("2022-01-14 23:00", 12)}
    h = Horloge(donnees, ["BTCUSD"])
    h.nuit = (h.nuit > 0).double()                       # écoles crypto : une nuit chaque jour, jamais triple
    assert h.nuits(torch.arange(h.T)).sum().item() == 1.0


def test_marche_invente_garde_l_ancienne_regle():
    f = Fiche("MONDE", "MONDE", "monde", "USD", 0.0001, 30.0, 0.1, 0.1, 0.0, 0.0)
    h = Horloge({"MONDE": _df("2022-01-12 23:00", 7 * 96)}, ["MONDE"], fiches={"MONDE": f})
    assert h.regle_nuit.tolist() == [0]
    assert torch.equal(h.nuits(torch.arange(h.T))[:, 0], h.nuit)


def test_simulateur_bitcoin_triple_le_vendredi_pas_le_mercredi():
    for debut, attendu in (("2022-01-14 23:15", 3), ("2022-01-12 23:15", 1)):
        h = Horloge({"BTCUSD": _df(debut, 8)}, ["BTCUSD"])
        c = Comptes(h, 1)
        c.recommencer(torch.tensor([True]), torch.tensor([0]))
        c.pas(_o(cible=50_000.0))
        payes = sum(c.pas(Ordres())["nuit"].item() for _ in range(5))
        assert payes == pytest.approx(c.u.item() * 1.0 * fiche("BTCUSD").nuit_achat / 360 * attendu), debut


# ---------------------------------------------------------------- levier (défaut 12)
def test_levier_du_compte_swing_mesure():
    assert fiche("EURUSD").levier == 30 and fiche("GBPJPY").levier == 30
    assert fiche("XAUUSD").levier == 15 and fiche("USA500IDXUSD").levier == 15 and fiche("DEUIDXEUR").levier == 15
    assert fiche("BTCUSD").levier == 1 and fiche("LIGHTCMDUSD").levier == 15 and fiche("GASCMDUSD").levier == 9
    assert fiche("USTBONDTRUSD").levier == 10, "pas relevé : valeur de la famille"


def test_simulateur_refuse_au_dela_du_levier_30_sur_les_devises():
    for fois, accepte in ((29, True), (31, False)):
        h = Horloge({"EURUSD": _df("2022-01-11 10:00", 3)}, ["EURUSD"])
        c = Comptes(h, 1)
        c.recommencer(torch.tensor([True]), torch.tensor([0]))
        r = c.pas(_o(cible=CAPITAL * fois))
        assert (c.u.item() != 0) == accepte and r["refus"].item() == (0 if accepte else 1)
