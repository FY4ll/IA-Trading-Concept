"""Tests de l'école de la précision (collapsar/ecole/precision) :
- ses zones d'offre et de demande sont identiques à la traduction fidèle de son indicateur (regarder/smc/nono_v7) ;
- les yeux sont SANS FUTUR (calcul coupé à t = calcul complet, structure ET vue de la carte graphique) ;
- un trade calculé à la main (ordre limite, stop de structure, objectif 1 à 80 %, stop à l'entrée, frais, nuit) ;
- le simulateur suit mains/simulateur.py pour un trade simple ;
- une politique au hasard perd environ les frais ; un tricheur (qui connaît l'avenir) gagne énormément ;
- reprise après arrêt, verrou contre deux écoles, fichier ARRET.
Depuis Test_IA : $env:CUDA_VISIBLE_DEVICES='-1'; venv_gpu\\Scripts\\python.exe -m pytest collapsar/tests/test_ecole_precision.py -q
"""
from __future__ import annotations

import json
import subprocess
import sys
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest
import torch

from collapsar.ecole.precision import donnees as D
from collapsar.ecole.precision import simulateur as SIM
from collapsar.ecole.precision import structure as S
from collapsar.ecole.precision.reglages import R, UNITES, UNITES_15
from collapsar.mains.simulateur import CAPITAL


# ================================================================================================ données inventées
def chemin_minutes(jours: int, graine: int, depart="2019-01-07", prix=1.10, pas=0.00012) -> pd.DataFrame:
    """Marché inventé SANS AVANTAGE (marche au hasard en prix, du lundi au vendredi), en bougies d'une minute."""
    rng = np.random.default_rng(graine)
    t = pd.date_range(depart, periods=jours * 1440, freq="1min")
    t = t[t.dayofweek < 5]
    sous = 4
    x = prix + np.cumsum(rng.normal(0, pas / 2, len(t) * sous))
    x = x.reshape(len(t), sous)
    o = np.r_[prix, x[:-1, -1]]
    return pd.DataFrame({"time": t.values.astype("datetime64[ns]"), "open": o,
                         "high": np.maximum(x.max(1), o), "low": np.minimum(x.min(1), o), "close": x[:, -1]})


def structure_inventee(jours=160, graine=0, minutes=False):
    m = chemin_minutes(jours, graine)
    q = D.reechantillonner(m, "15min")
    t15 = q["time"].values.astype("datetime64[ns]").astype(np.int64)
    s = S.calculer(t15, *(q[k].to_numpy(float) for k in ("open", "high", "low", "close")), m if minutes else None,
                   UNITES if minutes else UNITES_15, R().yeux.zones_par_cote, q)
    return m, q, s


# ================================================================================================ zones fidèles
def test_zones_identiques_a_sa_traduction_fidele():
    from collapsar.regarder.smc.nono_v7 import zones_graphique
    m, q, s = structure_inventee(40, 1, minutes=True)
    for u in UNITES:
        b = S.bougies_unite(q, m, u)
        bd = pd.DataFrame({"time": b["debut"].astype("datetime64[ns]"), "open": b["open"], "high": b["high"],
                           "low": b["low"], "close": b["close"]})
        ref = zones_graphique({u: bd}, u, (u,))
        z = S.zones_unite(b)
        assert len(ref) > (0 if u in ("D1", "H4") else 5), u
        assert len(z["top"]) == len(ref), u
        np.testing.assert_allclose(z["top"], ref["haut"].to_numpy())
        np.testing.assert_allclose(z["bot"], ref["bas"].to_numpy())
        np.testing.assert_array_equal(z["side"], ref["sens"].to_numpy())
        np.testing.assert_array_equal(z["ne"], ref["k_naissance"].to_numpy())
        fin_ref = np.where(ref["k_fin"].to_numpy() < 0, len(b["close"]), ref["k_fin"].to_numpy())
        np.testing.assert_array_equal(z["fin"], fin_ref)
        # les 2 zones vivantes les plus proches, à des lignes tirées au hasard : comme un calcul brut
        knn = S.plus_proches(len(b["close"]), z["mid"], z["side"], z["ne"], z["fin"], 2)
        for r in np.random.default_rng(0).integers(0, len(b["close"]), 40):
            vivantes = (z["ne"] <= r) & (z["fin"] > r)
            for cote, sens, ordre in ((0, 1, -1), (1, -1, 1)):
                ids = np.flatnonzero(vivantes & (z["side"] == sens))
                attendu = ids[np.argsort(ordre * z["mid"][ids], kind="stable")][:2]
                obtenu = knn[r, cote][knn[r, cote] >= 0]
                np.testing.assert_allclose(np.sort(z["mid"][obtenu]), np.sort(z["mid"][attendu]))


# ================================================================================================ sans futur
def test_yeux_sans_futur_structure():
    m, q, s = structure_inventee(60, 2, minutes=True)
    K = R().yeux.zones_par_cote
    for coupe in (pd.Timestamp("2019-02-05 13:00"), pd.Timestamp("2019-02-21 07:45")):
        mc, qc = m[m["time"] < coupe], q[q["time"] < coupe].reset_index(drop=True)
        t15 = qc["time"].values.astype("datetime64[ns]").astype(np.int64)
        sc = S.calculer(t15, *(qc[k].to_numpy(float) for k in ("open", "high", "low", "close")), mc, UNITES, K, qc)
        T = len(t15)
        np.testing.assert_array_equal(np.nan_to_num(sc["A"]), np.nan_to_num(s["A"][:T]))
        for u in UNITES:
            a, b = s[u], sc[u]
            np.testing.assert_array_equal(a["ligne"][:T], b["ligne"])
            for r in np.random.default_rng(3).integers(200, T, 300):
                lg = b["ligne"][r]
                if lg < 0:
                    continue
                ia, ib = a["knn"][lg], b["knn"][lg]
                np.testing.assert_array_equal(ia, ib)                 # mêmes zones (nées dans le même ordre)
                ok = ib >= 0
                for cle in ("top", "bot", "side", "vis"):
                    np.testing.assert_array_equal(a[cle][ia[ok]], b[cle][ib[ok]])
                for cle in ("tou", "rea"):                            # touchée / réaction : vues à l'instant r
                    np.testing.assert_array_equal(a[cle][ia[ok]] <= r, b[cle][ib[ok]] <= r)
                np.testing.assert_array_equal(np.nan_to_num(a["sw"][lg]), np.nan_to_num(b["sw"][lg]))


def _univers_reel_ou_rien():
    if not (S.dossier("EURUSD", False) / "fait.json").exists():
        pytest.skip("yeux de EURUSD pas encore calculés")


def test_yeux_sans_futur_vue_carte_graphique():
    """Ce que voit le cerveau à t ne dépend pas des données après t (vrai euro-dollar)."""
    _univers_reel_ou_rien()
    from collapsar.ecole.precision.univers import Univers
    from collapsar.ecole.precision.vue import Vue
    de = pd.Timestamp("2019-01-01")
    U1 = Univers([("EURUSD", False)], de, pd.Timestamp("2019-04-01"), "cpu")
    U2 = Univers([("EURUSD", False)], de, pd.Timestamp("2019-09-01"), "cpu")
    assert (U1.temps == U2.temps[:U1.T]).all()
    v1, v2 = Vue(U1), Vue(U2)
    t = torch.arange(U1.premier[0], U1.T - 3 * 96, 37)
    cols = torch.zeros(len(t), 1, dtype=torch.long)
    f1 = v1.caracteristiques(v1.structure(t, cols))
    f2 = v2.caracteristiques(v2.structure(t, cols))
    torch.testing.assert_close(f1, f2)


# ================================================================================================ un trade à la main
def univers_minimal(o, h, l, c, jour, nuits, demi=1e-4, nuit_achat=0.05):
    T = len(o)
    col = lambda x: np.asarray(x, float)[:, None]
    return SimpleNamespace(o=col(o), h=col(h), l=col(l), c=col(c), fx=np.ones((T, 1)), ouvert=np.ones((T, 1), bool),
                           derniere=np.zeros((T, 1), bool), demi=np.full((T, 1), demi),
                           nuit_a=np.full((T, 1), nuit_achat), nuit_v=np.full((T, 1), nuit_achat),
                           nuits=col(nuits), jour=np.asarray(jour, np.int64), levier=np.array([30.0]),
                           pas_u=np.array([1.0]), pas_d=np.array([100.0]), min_u=np.array([0.0]),
                           fin_challenge=lambda t0: np.full_like(t0, T - 1))


def test_un_trade_calcule_a_la_main():
    """Ordre limite d'achat à 99 (zone), stop 98 (derrière la zone), objectif 1 à 101 (80 %), destination 104 ;
    exécution, TP1, stop à l'entrée, une nuit, puis le reste sort à l'entrée (glissement compris)."""
    s = 1e-4
    o = [100.0, 99.8, 99.6, 99.3, 101.0, 100.0]
    h = [100.1, 100.2, 99.7, 101.3, 101.5, 100.1]
    l = [99.9, 99.5, 98.7, 99.2, 100.5, 98.8]
    c = [100.0, 99.9, 99.2, 101.0, 101.2, 99.0]
    U = univers_minimal(o, h, l, c, jour=[0, 0, 0, 0, 1, 1], nuits=[0, 0, 0, 0, 1, 0], demi=s)
    cp = SIM.Comptes(U, 1, 1)
    cp.recommencer(np.array([True]), np.array([[0]]), np.array([0]))
    cp.ord_act[0, 0], cp.ord_prix[0, 0], cp.ord_u[0, 0] = SIM.LIMITE, 99.0, 1000.0
    cp.ord_stop[0, 0], cp.ord_tp1[0, 0], cp.ord_part[0, 0], cp.ord_dest[0, 0] = 98.0, 101.0, 0.8, 104.0
    cp.ord_duree[0, 0] = 10
    cp.pas(1.0)                                     # bougie 1 : le plus bas 99,5 n'atteint pas 99
    assert cp.u[0, 0] == 0 and cp.att[0, 0] == 1
    cp.pas(1.0)                                     # bougie 2 : exécuté à 99, le stop 98 n'est pas touché
    assert cp.evt[0, 0] & SIM.EXECUTE and cp.u[0, 0] == 1000 and cp.entree[0, 0] == 99.0
    cp.pas(1.0)                                     # bougie 3 : TP1 à 101, 800 fermés, stop -> 99
    assert cp.evt[0, 0] & SIM.TP1 and cp.u[0, 0] == 200 and cp.stop[0, 0] == 99.0
    assert cp.solde[0] == pytest.approx(CAPITAL + 800 * (101 - 99))
    cp.pas(1.0)                                     # bougie 4 : une nuit sur 200 unités au prix d'ouverture 101
    nuit = 200 * 101.0 * 0.05 / 360
    assert cp.solde[0] == pytest.approx(CAPITAL + 1600 - nuit)
    cp.pas(1.0)                                     # bougie 5 : le reste sort à l'entrée, moins le glissement
    sortie = 99.0 * (1 - s)
    attendu = CAPITAL + 1600 - nuit + 200 * (sortie - 99.0)
    assert cp.evt[0, 0] & SIM.STOP and cp.u[0, 0] == 0
    assert cp.solde[0] == pytest.approx(attendu, abs=1e-6)
    assert cp.r_ferme[0, 0] == pytest.approx((attendu - CAPITAL) / 1000.0)        # 1 R = 1000 x (99 - 98)


def test_bougie_d_execution_jugee_au_pire():
    """Ordre limite exécuté dans une bougie qui touche aussi le stop : le stop est pris dans la même bougie."""
    U = univers_minimal([100, 99.5, 99], [100.2, 99.6, 99.2], [99.8, 97.5, 98.8], [100, 98.0, 99],
                        jour=[0, 0, 0], nuits=[0, 0, 0], demi=1e-4)
    cp = SIM.Comptes(U, 1, 1)
    cp.recommencer(np.array([True]), np.array([[0]]), np.array([0]))
    cp.ord_act[0, 0], cp.ord_prix[0, 0], cp.ord_u[0, 0], cp.ord_stop[0, 0] = SIM.LIMITE, 99.0, 1000.0, 98.0
    cp.ord_tp1[0, 0], cp.ord_dest[0, 0], cp.ord_duree[0, 0] = np.nan, np.nan, 5
    cp.pas(1.0)
    assert cp.evt[0, 0] & SIM.EXECUTE and cp.evt[0, 0] & SIM.STOP and cp.u[0, 0] == 0
    assert cp.solde[0] == pytest.approx(CAPITAL + 1000 * (98.0 * (1 - 1e-4) - 99.0))


def test_simulateur_suit_celui_du_projet():
    """Achat au marché avec stop et objectif : même résultat que mains/simulateur.py (glissement du stop retiré)."""
    from collapsar.mains.horloge import Horloge
    from collapsar.mains.simulateur import Comptes as ComptesProjet, Ordres
    q = D.reechantillonner(chemin_minutes(12, 5), "15min")
    h = Horloge({"EURUSD": q}, ["EURUSD"], "cpu")
    U = SimpleNamespace(o=h.o.numpy(), h=h.h.numpy(), l=h.l.numpy(), c=h.c.numpy(), fx=h.fx.numpy(),
                        ouvert=h.ouvert.numpy(), derniere=h.derniere.numpy(),
                        demi=np.broadcast_to(h.demi_ecart.numpy(), (h.T, 1)).copy(),
                        nuit_a=np.broadcast_to(h.nuit_achat.numpy(), (h.T, 1)).copy(),
                        nuit_v=np.broadcast_to(h.nuit_vente.numpy(), (h.T, 1)).copy(),
                        nuits=h.nuits_regle.numpy()[h.regle_nuit.numpy()].T.copy(), jour=h.jour.numpy(),
                        levier=h.levier.numpy(), pas_u=h.pas_unites.numpy(), pas_d=h.pas_dollars.numpy(),
                        min_u=h.min_unites.numpy(), fin_challenge=lambda t0: np.full_like(t0, h.T - 1))
    t0 = 300
    o1 = float(h.o[t0 + 1, 0])
    unites = 100_000.0
    stop, objectif = o1 - 0.004, o1 + 0.004
    projet = ComptesProjet(h, 1)
    projet.recommencer(torch.tensor([True]), torch.tensor([t0]))
    nan = torch.full((1, 1), float("nan"), dtype=torch.float64)
    d64 = lambda x: torch.tensor([[x]], dtype=torch.float64)
    projet.pas(Ordres(cible=d64(unites * o1), stop=d64(stop), objectif=d64(objectif)))
    cp = SIM.Comptes(U, 1, 1)
    cp.recommencer(np.array([True]), np.array([[0]]), np.array([t0]))
    cp.ord_act[0, 0], cp.ord_u[0, 0], cp.ord_stop[0, 0], cp.ord_dest[0, 0] = SIM.MARCHE, unites, stop, objectif
    cp.pas(0.0)
    assert float(projet.u[0, 0]) == pytest.approx(cp.u[0, 0])
    for _ in range(600):
        if float(projet.u[0, 0]) == 0 and cp.u[0, 0] == 0:
            break
        projet.pas(Ordres(cible=nan, stop=nan, objectif=nan))
        cp.pas(0.0)
    assert cp.u[0, 0] == 0 and float(projet.u[0, 0]) == 0
    assert cp.solde[0] == pytest.approx(float(projet.solde[0]), abs=1e-6)
    assert cp.solde[0] != CAPITAL


# ================================================================================================ hasard et tricheur
def test_au_hasard_on_perd_les_frais():
    """Ouvertures et fermetures au hasard sur un marché sans avantage : le gain avant frais est ~0, on perd les frais."""
    rng = np.random.default_rng(7)
    T, B = 4000, 300
    x = 100 + np.cumsum(rng.normal(0, 0.05, (T, 4)), 0).reshape(T, 4)
    o = np.r_[100.0, x[:-1, -1]]
    U = univers_minimal(o, np.maximum(x.max(1), o), np.minimum(x.min(1), o), x[:, -1], jour=np.arange(T) // 96,
                        nuits=(np.arange(T) % 96 == 0).astype(float), demi=2e-4, nuit_achat=0.03)
    cp = SIM.Comptes(U, B, 1)
    cp.recommencer(np.ones(B, bool), np.zeros((B, 1), np.int64), np.zeros(B, np.int64))
    frais, nuit = np.zeros(B), np.zeros(B)
    for t in range(T - 2):
        a = rng.random(B)
        plat = cp.u[:, 0] == 0
        cp.ord_act[:, 0] = np.where(plat & (a < 0.05), SIM.MARCHE, np.where(~plat & (a < 0.05), SIM.FERMER, SIM.RIEN))
        cp.ord_u[:, 0] = np.where(rng.random(B) < 0.5, -1.0, 1.0) * 200
        cp.ord_stop[:, 0] = np.where(cp.ord_u[:, 0] > 0, 1.0, 1e9)            # aucun stop atteint
        cp.pas(1.0)
        frais += cp.frais
        nuit += cp.nuit
        cp.mort[:] = False
    v = cp.valeurs()
    brut = v - CAPITAL + frais + nuit
    se = brut.std(ddof=1) / np.sqrt(B)
    assert abs(brut.mean()) < 3 * se                       # avant frais : rien
    assert (v - CAPITAL).mean() < -0.5 * (frais + nuit).mean()  # après frais : on perd environ les frais
    assert (frais + nuit).mean() > 0


@pytest.fixture
def monde_invente(monkeypatch):
    """Un « euro-dollar » inventé sans avantage, servi à l'école à la place des vraies données (yeux calculés)."""
    m = chemin_minutes(220, 11, depart="2019-01-07")
    q = D.reechantillonner(m, "15min")
    t15 = q["time"].values.astype("datetime64[ns]").astype(np.int64)
    s = S.calculer(t15, *(q[k].to_numpy(float) for k in ("open", "high", "low", "close")), None, UNITES_15,
                   R().yeux.zones_par_cote, q)
    x = {"t15": t15, "o": s["o"], "h": s["h"], "l": s["l"], "c": s["c"], "A": s["A"], "demi": np.full(len(t15), 3e-5)}
    for u in UNITES_15:
        x[u] = {k: v for k, v in s[u].items() if k not in ("ne", "fin", "debut_u")}
    monkeypatch.setattr(S, "lire", lambda nom, mir: x)
    return x


def _jouer_table(U, net_ou_tricheur, B, bougies, graine=0):
    from collapsar.ecole.precision import jeu as JEU
    tb = JEU.Table(U, B, 1)
    rng = np.random.default_rng(graine)
    dep = rng.integers(U.premier[0], U.T - bougies - 200, B)
    tb.demarrer(np.ones(B, bool), np.zeros((B, 1), np.int64), dep)
    c = tb.cpt
    dec = None if callable(net_ou_tricheur) and not isinstance(net_ou_tricheur, torch.nn.Module) else \
        JEU.Decideur(tb, net_ou_tricheur, evaluer=False, graphe=False)
    frais, nuit = np.zeros(B), np.zeros(B)
    torch.manual_seed(graine)
    for _ in range(bougies):
        masque = c.actif & ((c.t >= tb.prochain) | tb.reveil)
        qui = np.flatnonzero(masque)
        if len(qui):
            if dec is None:
                tb.appliquer(qui, net_ou_tricheur(tb, qui))
            else:
                _, _, paquet = dec(qui)
                tb.appliquer(qui, JEU.niveaux_np(paquet[:, :len(qui)]))
        r, fini, actifs = tb.avancer()
        frais += c.frais
        nuit += c.nuit
        c.actif &= ~(c.mort | c.reussi)
    return c.valeurs(), frais, nuit


def test_politique_au_hasard_perd_environ_les_frais(monde_invente):
    """Le cerveau NEUF (choix au hasard) à travers toute la chaîne : yeux, niveaux de structure, ordres, simulateur."""
    from collapsar.ecole.precision import cerveau as C
    from collapsar.ecole.precision.univers import Univers
    U = Univers([("EURUSD", False)], pd.Timestamp("2019-03-01"), pd.Timestamp("2019-09-01"), "cpu")
    torch.manual_seed(0)
    v, frais, nuit = _jouer_table(U, C.Cerveau(), 200, 1500)
    brut = v - CAPITAL + frais + nuit
    se = brut.std(ddof=1) / np.sqrt(len(v))
    assert (frais + nuit).mean() > 0
    assert abs(brut.mean()) < 3 * se + 1e-9
    assert (v - CAPITAL).mean() < 0


def test_un_tricheur_gagne_enormement(monde_invente):
    """Un tricheur qui connaît le prix 4 h plus tard, à travers la table, les ordres et le simulateur, gagne gros :
    preuve que la chaîne ne détruit pas un avantage."""
    from collapsar.ecole.precision.univers import Univers
    U = Univers([("EURUSD", False)], pd.Timestamp("2019-03-01"), pd.Timestamp("2019-09-01"), "cpu")

    def tricheur(tb, qui):
        c = tb.cpt
        t = c.t[qui]
        p = U.c[t, 0]
        futur = U.o[np.minimum(t + 17, U.T - 1), 0] - U.o[np.minimum(t + 1, U.T - 1), 0]
        sig = np.where(futur >= 0, 1.0, -1.0)
        plat = c.u[qui, 0] == 0
        rd = U.A[t, 0]                                      # stop à une agitation
        n = len(qui)
        return {"entree": p[:, None], "stop": (p - sig * rd)[:, None], "tp1": np.full((n, 1), np.nan),
                "part": np.zeros((n, 1)), "dest": np.full((n, 1), np.nan), "rd": rd[:, None],
                "sig": sig[:, None], "ouvre": plat[:, None], "limite": np.zeros((n, 1), bool),
                "ferme": ~plat[:, None], "risque_pct": np.full((n, 1), 1.0), "validite": np.full((n, 1), 16),
                "delai": np.full(n, 16)}
    v, frais, nuit = _jouer_table(U, tricheur, 100, 2000)
    mois = 2000 / 96 / 30.4
    assert ((v / CAPITAL - 1) * 100 / mois).mean() > 5.0          # plus de 5 % par mois


# ================================================================================================ reprise
@pytest.fixture
def petite_ecole(monde_invente, monkeypatch, tmp_path):
    from collapsar.ecole.precision import coeur as L
    from collapsar.ecole.precision import jeu as JEU
    from collapsar.ecole.precision.univers import Univers
    r = R()
    for sec, k, v in (("ecole", "comptes", 24), ("ecole", "bougies_par_lecon", 24), ("ecole", "lecons_par_generation", 1),
                      ("ecole", "epoques", 1), ("ecole", "paquet", 256), ("monde", "challenge_jours", 4),
                      ("selection", "pas_jours", 20), ("arbre", "places", 2)):
        monkeypatch.setattr(getattr(r, sec), k, v)
    monkeypatch.setattr(S, "preparer_tout", lambda **k: None)
    monkeypatch.setattr(L, "debuts_marches", lambda: {"EURUSD": pd.Timestamp("2019-01-07")})
    monkeypatch.setattr(L, "monde_apprentissage", lambda rng, dev, debuts: Univers(
        [("EURUSD", bool(rng.random() < 0.5))], pd.Timestamp("2019-03-01"), pd.Timestamp("2019-06-01"), dev))

    def examen(de, jusqua, dev):
        U = Univers([("EURUSD", False)], pd.Timestamp("2019-06-01"), pd.Timestamp("2019-08-15"), dev)
        return U, JEU.Examen(U, [["EURUSD"]], pd.Timestamp("2019-06-01"), pd.Timestamp("2019-08-15"), 20)
    monkeypatch.setattr(L, "monde_examen", examen)
    monkeypatch.setenv("COLLAPSAR_MUET", "1")
    return L, tmp_path


def _arbre(d):
    return json.loads((d / "arbre.json").read_text(encoding="utf-8"))


def _generations(d):
    return [json.loads(x)["generation"] for x in (d / "journal_croissance.jsonl").read_text(encoding="utf-8").splitlines()
            if json.loads(x).get("quoi") == "generation"]


def test_reprise_apres_arret(petite_ecole, capsys):
    L, d = petite_ecole
    base = ["--dossier", str(d), "--appareil", "cpu", "--muet"]
    L.main(["--generations", "1"] + base)
    a1 = _arbre(d)
    assert a1["battements"] == 1 and (d / "cime.pt").exists() and not (d / "EN_COURS").exists()
    poids = {n: torch.load(d / "branches" / f"{n}.pt", weights_only=False)["cerveau"] for n, b in a1["branches"].items()
             if b["morte"] is None}
    assert len(poids) == 2 and (d / "images" / "arbre.jpg").exists() and (d / "images" / "courbe.jpg").exists()
    L.main(["--generations", "2"] + base)
    assert "reprend après la génération 1" in capsys.readouterr().out
    assert _arbre(d)["battements"] == 2
    assert _generations(d) == [1, 2]
    # arrêt propre : rien ne tourne, rien n'est perdu
    (d / "ARRET").write_text("")
    L.main(["--generations", "5"] + base)
    assert _arbre(d)["battements"] == 2
    assert not (d / "EN_COURS").exists()


def test_l_arbre_coupe_et_divise(petite_ecole, monkeypatch):
    """La plus faible est coupée (archivée, pas effacée), la cime se divise pour reprendre la place."""
    L, d = petite_ecole
    monkeypatch.setattr(R().arbre, "jeunesse", 1)
    monkeypatch.setattr(R().arbre, "coupe_force", -1e9)          # pour le test : la cime coupe toujours la plus faible
    L.main(["--generations", "2", "--dossier", str(d), "--appareil", "cpu", "--muet"])
    a = _arbre(d)
    mortes = [n for n, b in a["branches"].items() if b["cause"] == "coupée"]
    filles = [n for n, b in a["branches"].items() if b["parents"]]
    assert mortes and filles
    assert all((d / "archives" / f"{n}.pt").exists() for n in mortes)
    assert sum(b["morte"] is None for b in a["branches"].values()) == 2


def test_verrou_contre_deux_ecoles(tmp_path):
    from collapsar.ecole.precision.coeur import verrou
    p = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    try:
        (tmp_path / "coeur.verrou").write_text(str(p.pid))
        with pytest.raises(SystemExit):
            verrou(tmp_path)
    finally:
        p.kill()
