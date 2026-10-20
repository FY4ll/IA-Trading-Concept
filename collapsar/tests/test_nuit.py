"""Frais de nuit de chaque époque calés sur la TABLE FTMO relevée (achat et vente séparés) ; miroir ; le simulateur
les applique (audit du 16/10/2026, défaut 11)."""
import json

import numpy as np
import pandas as pd
import pytest
import torch

from collapsar.mains import nuit
from collapsar.mains.fiches import fiche
from collapsar.mains.horloge import Horloge
from collapsar.mains.simulateur import Comptes, Ordres

pytestmark = pytest.mark.skipif(nuit._taux() is None or nuit._table()[1] is None,
                                reason="taux non téléchargés (python -m collapsar.donnees.taux) ou table FTMO absente")
TABLE = json.loads(nuit.MESURE.read_text(encoding="utf-8"))
RELEVE = pd.Timestamp(TABLE["quand"]).normalize()


@pytest.fixture(autouse=True)
def sans_releve(monkeypatch):
    from collapsar.mains import fiches
    monkeypatch.setattr(fiches, "_reelles", lambda: {})


def _taux(t):
    return nuit._taux().reindex(pd.DatetimeIndex([t]).normalize(), method="ffill").iloc[0]


def test_au_jour_du_releve_on_retrouve_la_table_achat_et_vente():
    for sym, nom in (("EURUSD", "EURUSD"), ("USDJPY", "USDJPY"), ("USA500IDXUSD", "US500"), ("XAUUSD", "XAUUSD"),
                     ("DEUIDXEUR", "GER40")):
        a, v = nuit.taux_nuit(fiche(sym), pd.DatetimeIndex([RELEVE + pd.Timedelta(hours=12)]))
        m = TABLE["marches"][nom]
        assert a[0] == pytest.approx(m["nuit_achat"]) and v[0] == pytest.approx(m["nuit_vente"]), nom


def test_devise_calcul_a_la_main_en_2015():
    """EURUSD : m = (achat + vente) / 2 relevés, d = (USD - EUR) au relevé - (achat - vente) / 2 ;
    en 2015 : achat = (USD - EUR)(2015) - d + m, vente = -((USD - EUR)(2015) - d) + m."""
    m = TABLE["marches"]["EURUSD"]
    marge = (m["nuit_achat"] + m["nuit_vente"]) / 2
    r0 = _taux(RELEVE)
    d = (r0["USD"] - r0["EUR"]) - (m["nuit_achat"] - m["nuit_vente"]) / 2
    t = pd.Timestamp("2015-06-10 12:00")
    r = _taux(t)
    base = r["USD"] - r["EUR"]
    a, v = nuit.taux_nuit(fiche("EURUSD"), pd.DatetimeIndex([t]))
    assert a[0] == pytest.approx(base - d + marge) and v[0] == pytest.approx(-(base - d) + marge)
    a24, _ = nuit.taux_nuit(fiche("EURUSD"), pd.DatetimeIndex(["2024-06-10 12:00"]))
    assert a[0] < a24[0], "2015 (taux proches de zéro) coûte moins que 2024 (dollar à ~5 %)"


def test_indice_achat_moins_cher_vente_plus_chere_qu_avant():
    """L'audit : US500 achat 7,6 %/an (ancien modèle) contre 5,7 % relevé ; vente -0,1 % contre +2,1 %."""
    t = pd.DatetimeIndex([RELEVE + pd.Timedelta(hours=12)])
    a, v = nuit.taux_nuit(fiche("USA500IDXUSD"), t)
    ancien_achat = _taux(RELEVE)["USD"] + nuit.MARGE["indice"]
    assert a[0] < ancien_achat and v[0] > -_taux(RELEVE)["USD"] + nuit.MARGE["indice"]
    am, vm = nuit.taux_nuit(fiche("USA500IDXUSD_MIROIR"), t)
    assert am[0] == pytest.approx(v[0]) and vm[0] == pytest.approx(a[0])


def test_decalage_aberrant_pas_prolonge_dans_le_passe():
    """UK100 : décalage relevé ~13 %/an (> 5 %) -> décalage 0, marge mesurée gardée (pas de frais reçus offerts en 2015)."""
    m = TABLE["marches"]["UK100"]
    marge, d = nuit.marge_et_decalage(fiche("GBRIDXGBP"), "UK100", "GBRIDXGBP")
    assert d == 0.0 and marge == pytest.approx((m["nuit_achat"] + m["nuit_vente"]) / 2)
    a, v = nuit.taux_nuit(fiche("GBRIDXGBP"), pd.DatetimeIndex(["2015-06-10 12:00"]))
    assert a[0] > 0 and v[0] > 0


def test_crypto_prend_la_table_et_energie_garde_sa_fiche():
    a, v = nuit.taux_nuit(fiche("BTCUSD"), pd.DatetimeIndex(["2021-01-05 12:00"]))
    assert a[0] == pytest.approx(TABLE["marches"]["BTCUSD"]["nuit_achat"]) == pytest.approx(0.30)
    assert v[0] == pytest.approx(TABLE["marches"]["BTCUSD"]["nuit_vente"])
    f = fiche("LIGHTCMDUSD")
    a, v = nuit.taux_nuit(f, pd.DatetimeIndex(["2021-01-05 12:00"]))
    assert a[0] == f.nuit_achat and v[0] == f.nuit_vente and a[0] >= 0, "pétrole : jamais de frais reçus offerts"


def test_le_simulateur_applique_les_frais_de_l_epoque():
    t = pd.date_range("2015-06-09 22:00", periods=16, freq="15min")       # passe minuit du serveur
    df = pd.DataFrame({"time": t, "open": 1.1, "high": 1.1, "low": 1.1, "close": 1.1, "volume": 1.0})
    h = Horloge({"EURUSD": df}, ["EURUSD"], nuit_historique=True)
    assert h.nuit_achat.shape == (16, 1)
    c = Comptes(h, 1)
    c.recommencer(torch.tensor([True]), torch.tensor([0]))
    c.pas(Ordres(cible=torch.tensor([[1_000_000.0]], dtype=torch.float64)))
    payes = sum(float(c.pas(Ordres())["nuit"][0]) for _ in range(14))
    attendu = 1_000_000.0 * 1.1 / 1.1 * float(h.nuit_achat[-1, 0]) / 360          # une nuit (mardi -> mercredi)
    assert payes == pytest.approx(attendu, rel=0.02)
