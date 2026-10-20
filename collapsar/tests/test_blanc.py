"""La démo en direct (direct/blanc.py) : l'état sauvé entre deux passages (15/10/2026)."""
import numpy as np
import pandas as pd
import pytest
import torch

from collapsar.direct import blanc
from collapsar.ecole.regard import ClasseRegard, Etat

AUCUNE_ANNONCE = pd.DataFrame({"temps": pd.to_datetime([]), "devise": []})


@pytest.fixture(autouse=True)
def sans_releve(monkeypatch):
    from collapsar.mains import fiches
    monkeypatch.setattr(fiches, "_reelles", lambda: {})


def _donnees(n):
    t = pd.date_range("2022-01-03", periods=n, freq="15min")
    c = 1.1 * np.exp(np.cumsum(np.random.default_rng(0).normal(0, 0.0005, n)))
    df = pd.DataFrame({"time": t, "open": c, "high": c * 1.0002, "low": c * 0.9998, "close": c, "volume": 1.0})
    return {"EURUSD": df}


def test_le_prochain_regard_dans_le_futur_survit_a_la_sauvegarde(monkeypatch, tmp_path):
    """Elle choisit de revenir dans 12 bougies : la bougie n'existe pas encore. Une bougie plus tard, il en reste 11
    (avant le 15/10 : l'heure retombait sur la dernière bougie connue et elle regardait toutes les 15 minutes)."""
    monkeypatch.setattr(blanc, "DOSSIER", tmp_path)
    monkeypatch.setattr(blanc, "ETAT", tmp_path / "blanc.json")
    d = _donnees(3000)
    c = ClasseRegard(["EURUSD"], "cpu", d, annonces=AUCUNE_ANNONCE)
    e = Etat(c.h, 1)
    t = c.h.T - 1
    e.recommencer(torch.tensor([True]), torch.tensor([t]))
    e.prochain[0] = t + 12
    s = {"debut": "x", "regards": 0, "journal": []}
    blanc.sauver(c, e, s)
    d2 = {"EURUSD": pd.concat([d["EURUSD"], d["EURUSD"].tail(1).assign(time=d["EURUSD"]["time"].iloc[-1] + pd.Timedelta(minutes=15))],
                              ignore_index=True)}
    c2 = ClasseRegard(["EURUSD"], "cpu", d2, annonces=AUCUNE_ANNONCE)
    e2 = blanc.restaurer(c2, s)
    assert int(e2.prochain[0]) - int(e2.comptes.t[0]) == 12
    e2.comptes.t[0] += 1                                       # une bougie passe
    assert int(e2.prochain[0]) - int(e2.comptes.t[0]) == 11, "elle ne regarde pas avant l'heure qu'elle a choisie"
    s["prochain_dans"] = 78                                    # rendez-vous pris avant la limite de 4 heures
    assert int(blanc.restaurer(c2, s).prochain[0]) - int(e2.comptes.t[0]) + 1 == 16


def test_un_ordre_a_l_avance_survit_au_passage_suivant(monkeypatch, tmp_path):
    monkeypatch.setattr(blanc, "DOSSIER", tmp_path)
    monkeypatch.setattr(blanc, "ETAT", tmp_path / "blanc.json")
    d = _donnees(3000)
    c = ClasseRegard(["EURUSD"], "cpu", d, annonces=AUCUNE_ANNONCE)
    e = Etat(c.h, 1)
    e.recommencer(torch.tensor([True]), torch.tensor([c.h.T - 1]))
    cpt = e.comptes
    cpt.att_type[0, 0], cpt.att_prix[0, 0], cpt.att_montant[0, 0], cpt.att_reste[0, 0] = 1, 1.05, 50_000.0, 40
    s = {"debut": "x", "regards": 0, "journal": []}
    blanc.sauver(c, e, s)
    e2 = blanc.restaurer(ClasseRegard(["EURUSD"], "cpu", d, annonces=AUCUNE_ANNONCE), s)
    c2 = e2.comptes
    assert (int(c2.att_type[0, 0]), float(c2.att_prix[0, 0]), float(c2.att_montant[0, 0]), int(c2.att_reste[0, 0])) == \
        (1, 1.05, 50_000.0, 40)
