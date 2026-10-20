"""Tests des hypothèses d'horaire / calendrier et de la mesure par fenêtres (compétition 1, 20/10/2026)."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from cerveau.mesure import fenetres as FE
from cerveau.perception import calendrier as CA
from core import donnees as D


@pytest.fixture(scope="module")
def sp():
    df = D.charger("USA500IDXUSD", pd.Timestamp("2019-01-01"))
    return df[df["time"] >= pd.Timestamp("2017-01-01")].reset_index(drop=True)


@pytest.fixture(scope="module")
def orx():
    df = D.charger("XAUUSD", pd.Timestamp("2019-01-01"))
    return df[df["time"] >= pd.Timestamp("2017-01-01")].reset_index(drop=True)


def test_asie_sans_nuit(orx):
    av = CA.HYPOTHESES["seance_asie"].avis(orx)
    assert ((av["temps"] - av["temps"].dt.normalize()) == pd.Timedelta(hours=1)).all()
    m = FE.Marche("XAUUSD", orx)
    ke, ks, s, t, pe, ps, ts = m.fenetres(av, "2017-03-01", "2018-12-01")
    assert len(ke) > 300 and (m.nuits_entre(t.asi8, ts.asi8) == 0).all()


def test_nuit_indice_traverse_minuit(sp):
    av = CA.HYPOTHESES["nuit_indice"].avis(sp)
    m = FE.Marche("USA500IDXUSD", sp)
    ke, ks, s, t, pe, ps, ts = m.fenetres(av, "2017-03-01", "2018-12-01")
    nuits = m.nuits_entre(t.asi8, ts.asi8)
    semaine = t.dayofweek <= 3
    assert (nuits[semaine] >= 1).all() and len(nuits) > 300
    # cohérent avec core.ftmo.horloge.nuits_payees sur les bougies
    assert np.array_equal(m.nuits_entre(m.t.asi8[ke], m.t.asi8[ks]), m.nuits_cumul[ks] - m.nuits_cumul[ke])
    # règle FTMO : aucune ouverture le vendredi soir (1 h avant la fermeture du week-end)
    assert (t.dayofweek == 4).sum() == 0
    assert m.interdite(t.asi8).sum() == 0
    assert np.isfinite(pe).all() and np.isfinite(ps).all()


def test_tournant_du_mois(sp):
    av = CA.HYPOTHESES["tournant_du_mois"].avis(sp)
    an = av[(av["temps"] >= "2017-02-01") & (av["temps"] < "2018-02-01")]
    assert len(an) == 12
    assert (an["expire"].dt.month != an["temps"].dt.month).all()


def test_elan_sans_futur(sp):
    """Le sens du jour ne dépend que des prix connus à 17:00 : couper l'historique à 17:30 ne le change pas."""
    av = CA.HYPOTHESES["elan_journee"].avis(sp)
    jour = av["temps"].dt.normalize().iloc[200]
    court = sp[sp["time"] < jour + pd.Timedelta(hours=17, minutes=30)].reset_index(drop=True)
    av2 = CA.HYPOTHESES["elan_journee"].avis(court)
    assert set(np.unique(av["sens"])) <= {-1, 1}
    a = av[av["temps"].dt.normalize() == jour]["sens"].iloc[0]
    b = av2[av2["temps"].dt.normalize() == jour]["sens"].iloc[0]
    assert a == b


def test_pnl_et_pile_ou_face(sp):
    m = FE.Marche("USA500IDXUSD", sp)
    av = CA.HYPOTHESES["nuit_indice"].avis(sp)
    ke, ks, s, _, pe, ps, ts = m.fenetres(av, "2017-06-01", "2018-06-01")
    plus, moins = m.pnl(ke, ks, s), m.pnl(ke, ks, -s)
    brut = m.montant[ke] * (m.o[ks] / m.o[ke] - 1)
    assert np.allclose(plus - moins, 2 * brut - m.montant[ke] * (m.achat[ke] - m.vente[ke]) / 360
                       * (m.nuits_cumul[ks] - m.nuits_cumul[ke]))
    assert ((plus + moins) / 2 < 0).all()                     # pile ou face : on paie toujours les frais
    assert (m.pnl(ke, ks, s, 1.5) <= plus).all()


def test_hasard_horaire_meme_mois(sp):
    m = FE.Marche("USA500IDXUSD", sp)
    av = CA.HYPOTHESES["nuit_indice"].avis(sp)
    ke, ks, s, t, pe, ps, ts = m.fenetres(av, "2017-06-01", "2017-09-01")
    h = m.hasard_horaire(ke[:20], ks[:20], s[:20], tirages=50)
    assert h.shape == (50, 20) and np.isfinite(h).all()


def test_trou_ouverture_sens_oppose_et_sans_futur(sp):
    av = CA.HYPOTHESES["trou_ouverture"].avis(sp)
    assert len(av) > 100 and set(np.unique(av["sens"])) <= {-1, 1}
    jour = av["temps"].dt.normalize().iloc[50]
    court = sp[sp["time"] < jour + pd.Timedelta(hours=16, minutes=45)].reset_index(drop=True)
    av2 = CA.HYPOTHESES["trou_ouverture"].avis(court)
    assert av[av["temps"].dt.normalize() == jour]["sens"].iloc[0] == av2[av2["temps"].dt.normalize() == jour]["sens"].iloc[0]
    # sens opposé au trou
    k = av["temps"].dt.normalize() == jour
    veille = CA.prix_a_cloture(sp, pd.DatetimeIndex([CA.jours_de_bourse(sp)[CA.jours_de_bourse(sp) < jour][-1]
                                                       + pd.Timedelta(hours=23)]))[0]
    ouv = CA.prix_a(sp, pd.DatetimeIndex([jour + pd.Timedelta(hours=16, minutes=30)]))[0]
    assert av[k]["sens"].iloc[0] == -np.sign(ouv / veille - 1)


def test_devises_retournement_sans_futur():
    from cerveau.perception.devises import PAIRES, RETOURNEMENT, devise_contre_dollar
    b = {p: D.charger(p, pd.Timestamp("2016-01-01")).query("time >= '2015-01-01'").reset_index(drop=True) for p in PAIRES}
    av = RETOURNEMENT.avis_multi(b)
    par_sem = av.groupby("temps").size()
    assert (par_sem == 4).all() and len(par_sem) > 40
    assert (av["temps"].dt.dayofweek == 0).all() and (av["expire"].dt.dayofweek == 4).all()
    # une semaine : les devises achetées sont les 2 plus baissées la semaine d'avant
    sem = RETOURNEMENT.semaines(b)
    lundi = par_sem.index[10]
    r = sem.loc[lundi - pd.Timedelta(days=3, hours=2) - pd.Timedelta(hours=-21) + pd.Timedelta(hours=-21)] \
        if False else sem[sem.index < lundi].iloc[-1]
    une = av[av["temps"] == lundi]
    achetees = set(une[une["sens"] * une["marche"].map(devise_contre_dollar) > 0]["marche"])
    assert achetees == set(r.sort_values().index[:2])
    # dollar-yen : le montant est en dollars, gain converti au prix de sortie
    m = FE.Marche("USDJPY", b["USDJPY"])
    assert m.base_dollar


def test_coffre_jamais_lu():
    """Le script de la compétition ne charge rien à partir du 01/01/2024."""
    import importlib.util
    from pathlib import Path
    p = Path(__file__).resolve().parents[2] / "etudes" / "2026-10-20_competition1" / "mesurer.py"
    spec = importlib.util.spec_from_file_location("mesurer_c1", p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert mod.FIN_LUE == pd.Timestamp("2024-01-01")
