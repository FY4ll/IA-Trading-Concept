"""Tests de L'AVIS SUR LES MARCHÉS (collapsar/ecole/precision/avis.py) :
- instants de l'avis : jours de semaine, dernière bougie FERMÉE à 08h00 serveur, rien si données trop vieilles ;
- sans futur : la table d'un vrai marché coupée à t = la table complète pour tous les avis donnés avant t ;
- calibration : un modèle trop sûr de lui est ramené à ses vraies fréquences ; un modèle qui se trompe de sens n'est
  JAMAIS retourné (pas d'avis : 50 %) ;
- format du message du matin et du plan.
Depuis Test_IA : $env:CUDA_VISIBLE_DEVICES='-1'; venv_gpu\\Scripts\\python.exe -m pytest collapsar/tests/test_avis.py -q
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from collapsar.ecole.precision import avis as AV

MIN = 60 * 10 ** 9
Q = 15 * MIN


def test_instants_jours_de_semaine_et_bougie_fermee():
    t15 = pd.Timestamp("2024-03-04").value + np.arange(14 * 96) * Q          # lundi 04/03 -> dimanche 17/03
    t15 = t15[~((t15 >= pd.Timestamp("2024-03-12").value) & (t15 < pd.Timestamp("2024-03-16").value))]  # trou
    inst, r = AV.instants(t15)
    jours = pd.DatetimeIndex(inst.astype("datetime64[ns]"))
    assert (jours.dayofweek < 5).all() and (jours.hour == 8).all() and (jours.minute == 0).all()
    assert (t15[r] + Q <= inst).all()                                       # bougie fermée à 08h00
    ok = np.isin(r, np.arange(len(t15)))
    assert ok.all()
    # la bougie fermée à 08h00 exactement est prise quand elle existe
    assert (t15[r][:5] + Q == inst[:5]).all()
    # mardi 12 -> vendredi 15 : 08h00 du 12 a sa bougie ; le 15 la dernière bougie a > 3 jours : pas d'avis
    assert pd.Timestamp("2024-03-15 08:00").value not in inst
    assert pd.Timestamp("2024-03-12 08:00").value in inst


@pytest.fixture(scope="module")
def argent():
    from collapsar.ecole.precision import structure as S
    d = S.dossier("XAGUSD", False)
    if not (d / "fait.json").exists():
        pytest.skip("yeux de XAGUSD absents")
    return S.lire("XAGUSD", False)


def test_table_sans_futur(argent):
    x = argent
    t15 = np.asarray(x["t15"], np.int64)
    N = int(np.searchsorted(t15, pd.Timestamp("2023-06-07 05:30").value))
    xc = {k: np.asarray(x[k])[:N] for k in ("t15", "o", "h", "l", "c", "A", "demi")}
    for u in ("D1", "H4", "H1", "M30", "M15"):
        if u in x:
            xc[u] = dict(x[u])
            xc[u]["ligne"] = np.asarray(x[u]["ligne"])[:N]
    full = AV.table_marche("XAGUSD", x)
    cut = AV.table_marche("XAGUSD", xc)
    coupe = t15[N - 1] + Q
    cols = list(AV.ENTREES) + ["prix", "A", "sommet_h4", "creux_h4", "dem_haut_D1", "off_bas_D1", "dem_haut_H4", "off_bas_H4"]
    a = full[full["inst"] <= coupe].reset_index(drop=True)
    b = cut[cut["inst"] <= coupe].reset_index(drop=True)
    assert len(a) == len(b) > 2000
    assert np.array_equal(a["inst"].to_numpy(), b["inst"].to_numpy())
    pd.testing.assert_frame_equal(a[cols], b[cols])
    # et la cible n'est jamais une entrée
    assert not any(c.startswith(("ret", "mvA", "fin")) for c in AV.ENTREES)


def _y(p, rng):
    return (rng.random(len(p)) < p).astype(int)


def test_calibration_ramene_aux_vraies_frequences():
    rng = np.random.default_rng(3)
    vrai = rng.uniform(0.3, 0.7, 60000)
    trop_sur = 1 / (1 + np.exp(-3 * np.log(vrai / (1 - vrai))))             # 3 fois trop sûr de lui
    cal, pente = AV.calibrer(trop_sur, _y(vrai, rng))
    assert 0.25 < pente < 0.45
    p = cal.predict_proba(AV._logit(trop_sur)[:, None])[:, 1]
    for lo in (0.3, 0.4, 0.5, 0.6):
        m = (vrai >= lo) & (vrai < lo + 0.1)
        assert abs(p[m].mean() - vrai[m].mean()) < 0.02


def test_calibration_ne_retourne_jamais_le_modele():
    rng = np.random.default_rng(4)
    vrai = rng.uniform(0.3, 0.7, 20000)
    cal, pente = AV.calibrer(vrai, _y(1 - vrai, rng))                       # le modèle se trompe de sens
    assert pente < 0
    p = cal.predict_proba(AV._logit(vrai)[:, None])[:, 1]
    assert np.allclose(p, 0.5)                                              # pas d'avis, pas d'avis retourné


def _ligne(**k):
    base = {"prix": 100.0, "A": 2.0, "off_bas_H4": 101.0, "off_haut_H4": 101.8, "off_bas_D1": 104.0, "off_haut_D1": 105.0,
            "dem_haut_H4": 97.0, "dem_bas_H4": 96.5, "dem_haut_D1": 95.0, "dem_bas_D1": 94.0, "sommet_h4": 102.5,
            "creux_h4": 98.0, "sommet_d1": 106.0, "creux_d1": 92.0}
    base.update(k)
    return pd.Series(base)


def test_plan_vente_sur_zone_d_offre():
    t = AV.plan_trade(_ligne(), -1)
    assert t.startswith("vente si réaction sur sa zone d'offre 4 h 101,00-101,80")
    assert "stop 102,00" in t and "destination 95,00 (sa zone journalière)" in t and "laisse courir" in t
    # une destination « derrière » le prix n'est jamais proposée
    t2 = AV.plan_trade(_ligne(dem_haut_D1=np.nan, creux_d1=103.0), -1)
    assert "pas de destination visible" in t2


def test_plan_achat_sans_zone_proche():
    t = AV.plan_trade(_ligne(dem_haut_H4=np.nan, dem_bas_H4=np.nan, dem_haut_D1=80.0, dem_bas_D1=79.0), 1)
    assert t.startswith("pas de zone de demande proche : achat au marché") and "stop 97,80" in t


def test_message_du_matin():
    av = {"nom": "Argent", 5: {"sens": -1, "conviction": 68.2, "p_hausse": 31.8},
          1: {"sens": 0, "conviction": 52.0, "p_hausse": 48.0}, 20: {"sens": -1, "conviction": 61.0, "p_hausse": 39.0},
          "raisons": ["tendance de fond 60 j baissière", "prix proche de sa zone d'offre 4 h", "peur sur l'or en hausse"],
          "plan": "vente si réaction sur sa zone d'offre 4 h 45,10-45,30, stop 45,45, destination 43,90, je laisse courir"}
    t = AV.texte_telephone(av, 5)
    assert t.startswith("Argent : BAISSE, conviction 68 % (5 jours). Pourquoi : tendance de fond 60 j baissière ;")
    assert "Plan : vente si réaction" in t and "1 j : rien 52 %" in t and "20 j : baisse 61 %" in t


def test_seuil_de_preuve_et_plan_fige():
    assert AV.N_TOTAL == 1355 and abs(AV.SEUIL - 3.80) < 0.01
    assert (AV.SORTIE / "plan_fige.md").exists()
