"""Tests des YEUX DU MONDE (collapsar/donnees/monde.py, collapsar/ecole/precision/monde.py, piste regarder/pistes/monde.py) :
- publication : une valeur du jour J n'est vue qu'à J+1 08h00 (heure du serveur) ; rien après fin_donnees ;
- sans futur : calcul coupé à t = calcul complet (tableaux des séries, yeux du monde, tension géopolitique) ;
- marché retourné : tout change de signe sauf « monde absent » ; éteints par défaut ;
- LA GREFFE ne change aucune décision au départ (vraie branche de l'arbre copiée, vrais marchés) ; sauvegarde, retour
  arrière ; le cœur d'un arbre greffé s'allume seul en mode monde et continue à battre ;
- piste : événements séparés de plus de 10 jours, entrée après l'instant connu, stop élargi -> frais <= 0,03 R.
Depuis Test_IA : $env:CUDA_VISIBLE_DEVICES='-1'; venv_gpu\\Scripts\\python.exe -m pytest collapsar/tests/test_monde.py -q
"""
from __future__ import annotations

import json
import shutil

import numpy as np
import pandas as pd
import pytest
import torch

from collapsar.donnees import monde as MW
from collapsar.ecole.precision import monde as MO
from collapsar.ecole.precision import structure as S
from collapsar.ecole.precision.reglages import R, VIE

from test_ecole_precision import monde_invente, petite_ecole  # noqa: F401  (fixtures partagées)

JOUR = 86400 * 10 ** 9
HEURE = 3600 * 10 ** 9


@pytest.fixture(autouse=True)
def monde_eteint(monkeypatch):
    monkeypatch.setattr(R().yeux, "monde", False, raising=False)


def _donnees_ou_rien():
    if not (MW.DOSSIER / "data_gpr_daily_recent.xls").exists() or not (MW.CBOE / "VIX_History.csv").exists():
        pytest.skip("données du monde absentes")


def test_publication_et_fin_donnees():
    _donnees_ou_rien()
    assert MW.FIN_DONNEES == R().periodes.fin_donnees
    for s in MW.SERIES:
        j, c, v = MW.serie(s)
        if not len(j):
            continue
        assert (c - j == JOUR + 8 * HEURE).all()                          # J+1 08h00
        assert c.max() < R().periodes.fin_donnees.value                     # rien des 12 mois cachés
        assert np.all(np.diff(j) > 0)
    # la valeur du GPR datée du 10/03/2020 : invisible à 07h59 le 11, visible à 08h00
    j, c, v = MW.serie("gpr")
    k = int(np.searchsorted(j, pd.Timestamp("2020-03-10").value))
    t = np.array([pd.Timestamp("2020-03-11 07:59").value, pd.Timestamp("2020-03-11 08:00").value])
    x = MW.valeurs_a("gpr", t)
    assert x[1] == v[k] and x[0] == v[k - 1]


@pytest.mark.parametrize("coupe", ["2014-06-17 13:00", "2020-03-12 08:00", "2022-02-24 09:30"])
def test_sans_futur_tableaux_et_yeux(coupe):
    _donnees_ou_rien()
    tc = pd.Timestamp(coupe).value
    for s in ("gpr", "epu", "vix", "ovx"):
        a, b = MW.tableau(s), MW.tableau(s, tc)
        n = len(b)
        assert n > 300 and b["connu"].max() < tc
        pd.testing.assert_frame_equal(a.iloc[:n].reset_index(drop=True), b.reset_index(drop=True))
    t = pd.date_range(pd.Timestamp(coupe) - pd.Timedelta(days=40), pd.Timestamp(coupe), freq="37min",
                      inclusive="left").as_unit("ns").asi8
    np.testing.assert_array_equal(MO.valeurs_a(t), MO.valeurs_a(t, coupe_ns=tc))
    np.testing.assert_array_equal(MW.tension_a(t), MW.tension_a(t, tc))


def test_yeux_voient_quelque_chose_et_miroir():
    _donnees_ou_rien()
    temps = pd.date_range("2020-02-01", "2020-04-30", freq="15min")
    F, idx = MO.tenseurs([("XAUUSD", False), ("XAUUSD", True), ("BTCUSDT", False)], temps, "cpu")
    assert F.shape == (len(temps), 2, MO.NM) and idx.tolist() == [0, 1, 0]
    x = F[:, 0].numpy()
    i = MO.NOMS.index
    assert (x[:, i("monde_absent")] == 0).all()
    assert np.abs(x[:, i("vix_niveau")]).max() > 1.0                     # mars 2020 : la peur est bien vue
    assert x[:, i("vix_haut30")].max() == 1.0
    np.testing.assert_array_equal(F[:, 1, MO.SENS].numpy(), -x[:, MO.SENS])
    np.testing.assert_array_equal(F[:, 1, ~MO.SENS].numpy(), x[:, ~MO.SENS])
    vide = MO.valeurs_a(pd.date_range("1980-01-01", periods=5, freq="1D").as_unit("ns").asi8)
    assert (vide == MO.NEUTRE).all()


def test_eteints_par_defaut_et_taille():
    import yaml
    from collapsar.ecole.precision import cerveau as C
    from collapsar.ecole.precision import vue as V
    from collapsar.ecole.precision.reglages import FICHIER
    assert yaml.safe_load(FICHIER.read_text(encoding="utf-8"))["yeux"]["monde"] is False
    assert not MO.active() and V.N_MONDE == MO.NM
    n0 = V.taille_caracteristiques()
    MO.activer()
    try:
        assert V.taille_caracteristiques() == n0 + MO.NM
        assert C.Cerveau().F == n0 + MO.NM + C.N_POS
    finally:
        MO.activer(False)


# ================================================================================================ la greffe
def _branche_reelle(tmp_path):
    from collapsar.ecole.precision import foule as FO
    source = VIE / "branches"
    if MO.greffee(VIE):
        sauves = sorted((VIE / "sauvegardes").glob("avant_monde_*"))
        if not sauves:
            pytest.skip("arbre greffé sans sauvegarde d'avant la greffe")
        source = sauves[-1] / "branches"
    br = [f for f in sorted(source.glob("*.pt")) if not f.stem.endswith("_meilleur")]
    if not br or not (S.dossier("BTCUSDT", False) / "fait.json").exists():
        pytest.skip("pas de branche réelle ou yeux BTC absents")
    if FO.greffee(VIE) and not FO.fichier_cache("BTCUSDT").exists():
        pytest.skip("arbre greffé foule mais cache de la foule absent")
    f = tmp_path / br[0].name
    shutil.copy2(br[0], f)                                                 # copie : l'arbre vivant n'est pas touché
    return torch.load(f, map_location="cpu", weights_only=False), FO.greffee(VIE)


def test_greffe_ne_change_aucune_decision(tmp_path, monkeypatch):
    """Vraie branche de l'arbre (copiée), vrais marchés (bitcoin + or retourné, début 2022, invasion de l'Ukraine) :
    avant / après la greffe, mêmes gestes, mêmes comptes, alors que les yeux du monde voient bien quelque chose."""
    _donnees_ou_rien()
    from collapsar.ecole.precision import cerveau as C
    from collapsar.ecole.precision import foule as FO
    from collapsar.ecole.precision import vue as V
    from collapsar.ecole.precision.univers import Univers
    from test_foule import _jouer
    etat, foule = _branche_reelle(tmp_path)
    monkeypatch.setattr(R().yeux, "foule", bool(foule), raising=False)   # l'arbre vivant voit la foule s'il est greffé
    var = [("BTCUSDT", False), ("XAUUSD", True)]
    de, a = pd.Timestamp("2022-02-01"), pd.Timestamp("2022-03-20")
    net0 = C.Cerveau()
    net0.load_state_dict(etat["cerveau"])
    U0 = Univers(var, de, a, "cpu")
    v0, g0, _ = _jouer(U0, net0, 48, 600, 5)
    t = torch.arange(int(U0.premier.max()), U0.T, 97)
    cols = torch.tensor([[0, 1]]).expand(len(t), 2)
    f0 = V.Vue(U0).caracteristiques(V.Vue(U0).structure(t, cols))
    etat2, change = MO.greffer_etat(etat)
    assert change and MO.greffer_etat(etat2)[1] is False                    # une seule greffe
    MO.activer()
    try:
        net1 = C.Cerveau()
        net1.load_state_dict(etat2["cerveau"])
        opt = torch.optim.AdamW(net1.parameters(), lr=1e-4)
        if etat2.get("opt"):
            opt.load_state_dict(etat2["opt"])
        U1 = Univers(var, de, a, "cpu")
        f1 = V.Vue(U1).caracteristiques(V.Vue(U1).structure(t, cols))
        m = f1[..., -MO.NM:]
        assert (m[:, 0, :-3].abs() > 0).float().mean() > 0.5                # le monde est bien vu
        torch.testing.assert_close(m[:, 1, torch.as_tensor(MO.SENS)], -m[:, 0, torch.as_tensor(MO.SENS)])  # or retourné
        assert torch.equal(f1[..., :-MO.NM], f0)                           # le reste des yeux : identique
        v1, g1, _ = _jouer(U1, net1, 48, 600, 5)
    finally:
        MO.activer(False)
        FO.activer(False)
    assert len(g0) > 300 and (g0 > 0).any()
    assert torch.equal(g0, g1)
    np.testing.assert_array_equal(v0, v1)


def _mini_arbre(d, etat):
    (d / "branches").mkdir(parents=True)
    torch.save(etat, d / "branches" / "A.pt")
    torch.save({"cerveau": etat["cerveau"], "generation": 3}, d / "branches" / "A_meilleur.pt")
    torch.save({"cerveau": etat["cerveau"], "generation": 3, "branche": "A"}, d / "cime.pt")
    (d / "arbre.json").write_text("{}", encoding="utf-8")


def test_greffe_sur_dossier_sauvegarde_et_retour(tmp_path):
    from collapsar.ecole.precision import cerveau as C
    torch.manual_seed(0)
    net = C.Cerveau()
    opt = torch.optim.AdamW(net.parameters(), lr=1e-3)
    net.marche[0].weight.sum().backward()
    opt.step()
    d = tmp_path / "arbre"
    _mini_arbre(d, {"cerveau": net.state_dict(), "opt": opt.state_dict(), "temperament": {}})
    info = MO.greffer(d, dire=lambda *a: None)
    assert MO.greffee(d) and len(info["fichiers"]) == 3
    for f in ("A.pt", "A_meilleur.pt"):
        w = torch.load(d / "branches" / f, weights_only=False)["cerveau"]["marche.0.weight"]
        assert w.shape[1] == net.F + MO.NM
        ou = info["insertion"]
        assert (w[:, ou:ou + MO.NM] == 0).all()
        torch.testing.assert_close(torch.cat([w[:, :ou], w[:, ou + MO.NM:]], 1), net.marche[0].weight.detach())
    e = torch.load(d / "branches" / "A.pt", weights_only=False)
    ea = [s["exp_avg"] for s in e["opt"]["state"].values() if s["exp_avg"].dim() == 2 and s["exp_avg"].shape[0] == 256]
    assert ea and ea[0].shape[1] == net.F + MO.NM
    with pytest.raises(SystemExit):
        MO.greffer(d, dire=lambda *a: None)
    MO.defaire(d, dire=lambda *a: None)
    assert not MO.greffee(d)
    w = torch.load(d / "branches" / "A.pt", weights_only=False)["cerveau"]["marche.0.weight"]
    assert w.shape[1] == net.F


def test_coeur_greffe_bat_en_mode_monde(petite_ecole):
    """Petite école (euro inventé 2019) : 1 génération sans le monde, arrêt, greffe, le cœur reprend SEUL en mode monde
    (entrées agrandies) et bat encore ; un réglage allumé sur un arbre non greffé est refusé."""
    _donnees_ou_rien()
    L, d = petite_ecole
    base = ["--dossier", str(d), "--appareil", "cpu", "--muet"]
    L.main(["--generations", "1"] + base)
    a = json.loads((d / "arbre.json").read_text(encoding="utf-8"))
    vivantes = [n for n, b in a["branches"].items() if b["morte"] is None]
    f0 = torch.load(d / "branches" / f"{vivantes[0]}.pt", weights_only=False)["cerveau"]["marche.0.weight"].shape[1]
    MO.activer()
    with pytest.raises(SystemExit):
        L.main(["--generations", "2"] + base)
    MO.activer(False)
    MO.greffer(d, dire=lambda *x: None)
    L.main(["--generations", "2"] + base)
    assert MO.active()
    assert json.loads((d / "arbre.json").read_text(encoding="utf-8"))["battements"] == 2
    for n, b in json.loads((d / "arbre.json").read_text(encoding="utf-8"))["branches"].items():
        if b["morte"] is None:
            w = torch.load(d / "branches" / f"{n}.pt", weights_only=False)["cerveau"]["marche.0.weight"]
            assert w.shape[1] == f0 + MO.NM


# ================================================================================================ la piste
def test_piste_evenements_et_entree():
    _donnees_ou_rien()
    from collapsar.regarder.pistes import monde as PM
    for s in ("gpr:haut30", "vix:saut2"):
        j, c = PM.evenements_signal(s)
        assert len(j) > 50 and (np.diff(j) > PM.ESPACEMENT_J * JOUR).all()
        assert (c - j == JOUR + 8 * HEURE).all()
    d = PM.table_marche("XAUUSD")
    ok = d["ok"].to_numpy()
    assert (d["te"].to_numpy()[ok] >= d["E"].to_numpy()[ok]).all()          # entrée après l'instant connu
    s = d["sortie5"].to_numpy()
    assert (s[s > 0] > d["te"].to_numpy()[s > 0]).all()


def test_piste_stop_elargi_frais():
    from collapsar.regarder.pistes import monde as PM
    gl = float(R().monde.frais_stop_glissement)
    n = 6
    x = {"c": np.full(10, 100.0), "A": np.full(10, 2.0), "demi": np.full(10, 2e-4)}
    ev = {"j": np.arange(n), "genre": np.array([1, 1, 2, 2, 1, 1]), "side": np.array([1, -1, 1, -1, 1, 1]),
          "top": np.array([99.95, 100.6, 99.9, 101.0, 99.0, 99.9]), "bot": np.array([99.9, 100.05, 99.0, 100.1, 98.0, 99.8])}
    for fam in ("REB", "CAS"):
        g = PM.geometrie(x, ev, fam, gl)
        rd = g["sens"] * (g["p"] - g["stop"])
        assert (rd > 0).all() and ((2 + gl) * 2e-4 * 100 / rd <= PM.FRAIS_MAX_R + 1e-9).all()
        assert (rd >= PM.RISQUE_MIN_A * 2.0 - 1e-9).all() and (rd <= PM.RISQUE_MAX_A * 2.0 + 1e-9).all()
    g = PM.geometrie(x, ev, "REB", gl)
    assert g["elargi"].any()                                                # zone serrée : stop élargi
