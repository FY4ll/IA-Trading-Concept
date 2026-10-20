"""Tests des YEUX DE LA FOULE de l'arbre HYPERNOVA (collapsar/ecole/precision/foule.py) :
- sans futur : calcul coupé à t = calcul complet (données inventées ET vraies données BTC) ; heures de publication
  (ligne « metrics » datée T vue à T + 15 min, financement vu après son règlement, bougie vue close) ;
- marché retourné : ce qui a un sens change de signe ; hors cryptos et avant les données : neutre + « foule absente » ;
- éteints par défaut (l'arbre actuel n'est pas touché) ;
- LA GREFFE ne change aucune décision au départ (vraie branche de l'arbre copiée, vrais marchés) ; sauvegarde, retour
  arrière ; le cœur d'un arbre greffé s'allume seul en mode foule et continue à battre.
Depuis Test_IA : $env:CUDA_VISIBLE_DEVICES='-1'; venv_gpu\\Scripts\\python.exe -m pytest collapsar/tests/test_foule.py -q
"""
from __future__ import annotations

import json
import shutil

import numpy as np
import pandas as pd
import pytest
import torch

from collapsar.ecole.precision import foule as FO
from collapsar.ecole.precision import structure as S
from collapsar.ecole.precision.reglages import R, VIE

from test_ecole_precision import monde_invente, petite_ecole  # noqa: F401  (fixtures partagées)

MIN = 60 * 10 ** 9


@pytest.fixture(autouse=True)
def foule_eteinte(monkeypatch):
    """Chaque test part foule éteinte ; l'état d'origine est remis après (même si un test l'allume)."""
    monkeypatch.setattr(R().yeux, "foule", False, raising=False)


# ================================================================================================ données inventées
def brut_invente(jours=200, graine=0, debut="2021-01-01"):
    rng = np.random.default_rng(graine)
    t0 = pd.Timestamp(debut).value
    m5 = t0 + np.arange(jours * 288) * 5 * MIN
    keep = rng.random(len(m5)) > 0.02                                   # quelques trous
    m5 = m5[keep]
    ratio = np.exp(np.cumsum(rng.normal(0, 0.003, len(m5))))
    oi = 1e4 * np.exp(np.cumsum(rng.normal(0, 0.002, len(m5))))
    fu = t0 + np.arange(jours * 3) * 8 * 60 * MIN + 2_000_000             # règlement 2 ms après l'heure pleine
    k15 = t0 + np.arange(jours * 96) * 15 * MIN
    v = rng.gamma(2.0, 100.0, len(k15))
    h1 = t0 + np.arange(jours * 24) * 60 * MIN
    return {"metrics": {"connu": m5 + 15 * MIN, "oi": oi, "ratio": ratio},
            "funding": {"connu": fu, "taux": rng.normal(1e-4, 1e-4, len(fu))},
            "klines": {"connu": k15 + 15 * MIN, "v": v, "tb": v * rng.uniform(0.3, 0.7, len(v))},
            "prime": {"connu": h1 + 60 * MIN, "p": rng.normal(0, 5e-4, len(h1))}}


def _compare_coupe(brut, coupes):
    g, x = FO.calculer(brut)
    assert len(g) > 1000
    for t in coupes:
        tn = pd.Timestamp(t).value
        gc, xc = FO.calculer(FO.couper(brut, tn))
        assert gc[-1] <= tn and gc[0] == g[0]
        n = len(gc)
        np.testing.assert_array_equal(gc, g[:n])
        np.testing.assert_allclose(xc, x[:n], atol=1e-6, rtol=0)
    return g, x


def test_sans_futur_donnees_inventees():
    b = brut_invente()
    g, x = _compare_coupe(b, ["2021-03-17 13:15", "2021-05-02 07:40", "2021-06-30 23:59"])
    assert (np.abs(x[:, :14]) > 0).mean() > 0.5                          # les yeux voient vraiment quelque chose


def test_heures_de_publication():
    """La ligne « metrics » datée T n'est vue qu'à T + 15 min ; le financement de 08h00:00,002 n'est vu qu'à 08h15 ;
    une bougie de 15 min n'est vue que close."""
    b = brut_invente(30)
    g, x = FO.calculer(b)
    i = FO.NOMS.index
    m = b["metrics"]
    T = pd.Timestamp("2021-01-10 12:00").value
    j = int(np.searchsorted(m["connu"] - 15 * MIN, T))
    assert m["connu"][j] - 15 * MIN == T
    part = lambda r: (r / (1 + r) - 0.5) * 4
    a = int(np.searchsorted(g, T + 15 * MIN))
    assert x[a, i("part_acheteurs")] == pytest.approx(part(m["ratio"][j]), abs=1e-6)
    assert x[a - 1, i("part_acheteurs")] == pytest.approx(part(m["ratio"][j - 3]), abs=1e-6)   # à 12h00 : ligne 11h45
    fu = b["funding"]
    h8 = pd.Timestamp("2021-01-10 08:00").value
    k = int(np.searchsorted(fu["connu"], h8))                              # règlement 08:00:00,002
    a8 = int(np.searchsorted(g, h8))
    assert x[a8, i("financement")] == pytest.approx(np.arcsinh(fu["taux"][k - 1] / 1e-4) / 2, abs=1e-6)
    assert x[a8 + 1, i("financement")] == pytest.approx(np.arcsinh(fu["taux"][k] / 1e-4) / 2, abs=1e-6)
    kl = b["klines"]
    a = int(np.searchsorted(g, T))
    o = int(np.searchsorted(kl["connu"], T))                               # bougie ouverte à 11h45, close à 12h00
    attendu = (kl["tb"][o - 3:o + 1].sum() / kl["v"][o - 3:o + 1].sum() - 0.5) * 10
    assert x[a, i("flux_1h")] == pytest.approx(attendu, abs=1e-5)


def _btc_ou_rien():
    if not (FO.FUT / "metrics" / "BTCUSDT.csv").exists():
        pytest.skip("données Binance absentes")


def test_sans_futur_vraies_donnees_btc():
    _btc_ou_rien()
    b = FO.lire_brut("BTCUSDT")
    _compare_coupe(b, ["2021-02-03 05:15", "2022-11-09 17:45"])


def test_rien_apres_fin_donnees():
    _btc_ou_rien()
    b = FO.lire_brut("BTCUSDT")
    fin = R().periodes.fin_donnees.value
    assert all(d["connu"].max() < fin for d in b.values())


def test_miroir_et_neutre():
    _btc_ou_rien()
    dec = FO.serveur_vers_utc_ns(pd.date_range("2019-06-01", "2022-06-01", freq="7h") + pd.Timedelta(minutes=15))
    a, m = FO.valeurs_a("BTCUSDT", False, dec), FO.valeurs_a("BTCUSDT", True, dec)
    np.testing.assert_array_equal(m[:, FO.SENS], -a[:, FO.SENS])
    np.testing.assert_array_equal(m[:, ~FO.SENS], a[:, ~FO.SENS])
    avant = dec < pd.Timestamp("2020-01-01").value
    assert avant.any() and (a[avant] == FO.NEUTRE).all()
    assert (a[~avant, FO.NOMS.index("foule_absente")] == 0).mean() > 0.99
    temps = pd.date_range("2021-03-01", periods=500, freq="15min")
    F, idx = FO.tenseurs([("EURUSD", False), ("BTCUSDT", False), ("XAUUSD@M1", True)], temps, "cpu")
    assert F.shape == (500, 2, FO.NF) and idx.tolist() == [1, 0, 1]
    assert (F[:, 1] == torch.as_tensor(FO.NEUTRE)).all()
    assert (F[:, 0, FO.NOMS.index("comptes_presents")] == 1).all()


def test_heure_serveur_vers_utc():
    t = pd.DatetimeIndex(["2022-07-01 10:00", "2022-01-03 09:00"])         # été : UTC+3 ; hiver : UTC+2
    assert list(pd.to_datetime(FO.serveur_vers_utc_ns(t))) == [pd.Timestamp("2022-07-01 07:00"),
                                                                pd.Timestamp("2022-01-03 07:00")]


def test_eteints_par_defaut_et_taille():
    from collapsar.ecole.precision import cerveau as C
    from collapsar.ecole.precision import vue as V
    import yaml
    from collapsar.ecole.precision.reglages import FICHIER
    assert yaml.safe_load(FICHIER.read_text(encoding="utf-8"))["yeux"]["foule"] is False
    assert not FO.active()
    n0 = V.taille_caracteristiques()
    FO.activer()
    try:
        assert V.taille_caracteristiques() == n0 + FO.NF
        assert C.Cerveau().F == n0 + FO.NF + C.N_POS
    finally:
        FO.activer(False)


# ================================================================================================ la greffe
def _branche_reelle(tmp_path):
    source = VIE / "branches"
    if FO.greffee(VIE):                     # l'arbre vivant est déjà greffé : une branche d'AVANT la greffe
        sauves = sorted((VIE / "sauvegardes").glob("avant_foule_*"))
        if not sauves:
            pytest.skip("arbre greffé sans sauvegarde d'avant la greffe")
        source = sauves[-1] / "branches"
    br = sorted(source.glob("*.pt"))
    br = [f for f in br if not f.stem.endswith("_meilleur")]
    if not br or not (S.dossier("BTCUSDT", False) / "fait.json").exists() or not FO.fichier_cache("BTCUSDT").exists():
        pytest.skip("pas de branche réelle ou yeux BTC absents")
    f = tmp_path / br[0].name
    shutil.copy2(br[0], f)                                                 # copie : l'arbre vivant n'est pas touché
    return torch.load(f, map_location="cpu", weights_only=False)


def _jouer(U, net, B, bougies, graine):
    from collapsar.ecole.precision import jeu as JEU
    tb = JEU.Table(U, B, 2)
    rng = np.random.default_rng(graine)
    lo = int(U.premier.max())
    tb.demarrer(np.ones(B, bool), np.tile(np.arange(2), (B, 1)), rng.integers(lo, U.T - bougies - 10, B))
    dec = JEU.Decideur(tb, net, evaluer=False, graphe=False)
    torch.manual_seed(graine)
    c = tb.cpt
    gestes = []
    for _ in range(bougies):
        qui = np.flatnonzero(c.actif & ((c.t >= tb.prochain) | tb.reveil))
        if len(qui):
            (choix, *_), _, paquet = dec(qui)
            gestes.append(choix["geste"][:len(qui)].clone())
            tb.appliquer(qui, JEU.niveaux_np(paquet[:, :len(qui)]))
        tb.avancer()
        c.actif &= ~(c.mort | c.reussi)
    return c.valeurs().copy(), torch.cat(gestes), tb


def test_greffe_ne_change_aucune_decision(tmp_path):
    """Vraie branche de l'arbre (copiée), vrais marchés (bitcoin + éther retourné, début 2022) : avant / après la
    greffe, mêmes gestes, mêmes comptes à la fin, alors que les yeux de la foule voient bien quelque chose."""
    from collapsar.ecole.precision import cerveau as C
    from collapsar.ecole.precision import vue as V
    from collapsar.ecole.precision.univers import Univers
    etat = _branche_reelle(tmp_path)
    var = [("BTCUSDT", False), ("ETHUSDT", True)]
    de, a = pd.Timestamp("2022-02-01"), pd.Timestamp("2022-03-20")
    net0 = C.Cerveau()
    net0.load_state_dict(etat["cerveau"])
    U0 = Univers(var, de, a, "cpu")
    v0, g0, tb0 = _jouer(U0, net0, 48, 600, 5)
    t = torch.arange(int(U0.premier.max()), U0.T, 97)
    cols = torch.tensor([[0, 1]]).expand(len(t), 2)
    f0 = V.Vue(U0).caracteristiques(V.Vue(U0).structure(t, cols))
    etat2, change = FO.greffer_etat(etat)
    assert change and FO.greffer_etat(etat2)[1] is False                    # une seule greffe
    FO.activer()
    try:
        net1 = C.Cerveau()
        net1.load_state_dict(etat2["cerveau"])
        opt = torch.optim.AdamW(net1.parameters(), lr=1e-4)
        if etat2.get("opt"):
            opt.load_state_dict(etat2["opt"])                              # mémoire de l'optimiseur aux bonnes tailles
        U1 = Univers(var, de, a, "cpu")
        f1 = V.Vue(U1).caracteristiques(V.Vue(U1).structure(t, cols))
        foule = f1[..., -FO.NF:]
        assert (foule[:, 0, :14].abs() > 0).float().mean() > 0.5           # la foule est bien vue (BTC)
        assert (foule[:, 1, :14].abs() > 0).float().mean() > 0.5           # et sur l'éther retourné
        assert torch.equal(f1[..., :-FO.NF], f0)                           # le reste des yeux : identique
        v1, g1, _ = _jouer(U1, net1, 48, 600, 5)
    finally:
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


def test_greffe_sur_dossier_sauvegarde_et_retour(tmp_path, monkeypatch):
    from collapsar.ecole.precision import cerveau as C
    monkeypatch.setattr(FO, "preparer_tout", lambda dire=print: None)
    torch.manual_seed(0)
    net = C.Cerveau()
    opt = torch.optim.AdamW(net.parameters(), lr=1e-3)
    net.marche[0].weight.sum().backward()
    opt.step()
    d = tmp_path / "arbre"
    _mini_arbre(d, {"cerveau": net.state_dict(), "opt": opt.state_dict(), "temperament": {}})
    info = FO.greffer(d, dire=lambda *a: None)
    assert FO.greffee(d) and len(info["fichiers"]) == 3
    for f in ("A.pt", "A_meilleur.pt"):
        w = torch.load(d / "branches" / f, weights_only=False)["cerveau"]["marche.0.weight"]
        assert w.shape[1] == net.F + FO.NF
        ou = info["insertion"]
        assert (w[:, ou:ou + FO.NF] == 0).all()
        torch.testing.assert_close(torch.cat([w[:, :ou], w[:, ou + FO.NF:]], 1), net.marche[0].weight.detach())
    e = torch.load(d / "branches" / "A.pt", weights_only=False)
    ea = [s["exp_avg"] for s in e["opt"]["state"].values() if s["exp_avg"].dim() == 2 and s["exp_avg"].shape[0] == 256]
    assert ea and ea[0].shape[1] == net.F + FO.NF
    assert (d / "sauvegardes").exists()
    with pytest.raises(SystemExit):
        FO.greffer(d, dire=lambda *a: None)
    FO.defaire(d, dire=lambda *a: None)
    assert not FO.greffee(d)
    w = torch.load(d / "branches" / "A.pt", weights_only=False)["cerveau"]["marche.0.weight"]
    assert w.shape[1] == net.F


def test_coeur_greffe_bat_en_mode_foule(petite_ecole, monkeypatch):
    """Petite école (euro inventé) : 1 génération sans foule, arrêt, greffe, le cœur reprend SEUL en mode foule
    (entrées agrandies) et bat encore ; un réglage allumé sur un arbre non greffé est refusé."""
    L, d = petite_ecole
    base = ["--dossier", str(d), "--appareil", "cpu", "--muet"]
    L.main(["--generations", "1"] + base)
    a = json.loads((d / "arbre.json").read_text(encoding="utf-8"))
    vivantes = [n for n, b in a["branches"].items() if b["morte"] is None]
    f0 = torch.load(d / "branches" / f"{vivantes[0]}.pt", weights_only=False)["cerveau"]["marche.0.weight"].shape[1]
    FO.activer()
    with pytest.raises(SystemExit):
        L.main(["--generations", "2"] + base)
    FO.activer(False)
    monkeypatch.setattr(FO, "preparer_tout", lambda dire=print: None)
    FO.greffer(d, dire=lambda *x: None)
    L.main(["--generations", "2"] + base)
    assert FO.active()
    assert json.loads((d / "arbre.json").read_text(encoding="utf-8"))["battements"] == 2
    for n, b in json.loads((d / "arbre.json").read_text(encoding="utf-8"))["branches"].items():
        if b["morte"] is None:
            w = torch.load(d / "branches" / f"{n}.pt", weights_only=False)["cerveau"]["marche.0.weight"]
            assert w.shape[1] == f0 + FO.NF
