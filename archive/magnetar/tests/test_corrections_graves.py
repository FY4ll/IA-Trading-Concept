"""Tests des CORRECTIONS GRAVES de MAGNETAR (20/10/2026, audit vie/arbre_or/audit_manques/rapport.md) :
1. JUGE : note au GAIN RÉEL (min(gain - jumeau, gain)), réussite comparée à celle du jumeau ; examen qui TOURNE (blocs
   tirés à chaque génération, les mêmes pour toutes les branches) ; blocs NEUFS joués à part (témoin, hors note) ;
2. APPRENTISSAGE : planchers de vitesse et de curiosité, plancher du hasard ;
3. ORDRES : un ordre limite plafonné en distance ; un ordre en attente n'empêche plus d'ouvrir au marché ni de le
   remplacer ; ouvertures réellement exécutées comptées à part ;
4. P2 : la « meilleure version » n'est enregistrée que si les garde-fous passent ;
5. FRAIS : écart par heure (réouverture, avant une pause), annonces.
Réglages absents (HYPERNOVA) : tout comme avant (empreinte d'HYPERNOVA vérifiée par test_suiveur.py).
Depuis Test_IA : $env:CUDA_VISIBLE_DEVICES='-1'; venv_gpu\\Scripts\\python.exe -m pytest collapsar/tests/test_corrections_graves.py -q
"""
from __future__ import annotations

import json
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest
import torch

from collapsar.ecole.precision import simulateur as SIM
from collapsar.ecole.precision.reglages import R

from test_ecole_precision import monde_invente, petite_ecole  # noqa: F401  (fixtures partagées)
from test_trois_changements import _vieux


# ================================================================================================ 1. juge
def test_note_au_gain_reel_et_reussite_contre_le_jumeau(monkeypatch):
    from collapsar.ecole.precision import jeu as JEU
    z = np.zeros(4, bool)
    g = np.array([-0.5, 1.0, 1.0, -2.0])
    gj = np.array([-1.0, -1.0, 2.0, -1.0])
    bas = np.zeros(4)
    jours = np.full(4, np.nan)
    avant = JEU.note_challenges(z, jours, z, z, g, gj, bas)
    np.testing.assert_allclose(avant, g - gj)                                   # réglage absent : comme avant
    monkeypatch.setattr(R().note, "gain_reel", True, raising=False)
    np.testing.assert_allclose(JEU.note_challenges(z, jours, z, z, g, gj, bas), [-0.5, 1.0, -1.0, -2.0])
    # « perdre moins que le hasard » ne rapporte plus rien ; gagner plus que lui (et gagner tout court) oui
    reussi = np.array([True, True, False, False])
    j_ = np.array([10.0, 30.0, np.nan, np.nan])
    a = JEU.note_challenges(reussi, j_, z, z, g, gj, bas)
    monkeypatch.setattr(R().note, "reussite_contre_jumeau", True, raising=False)
    b = JEU.note_challenges(reussi, j_, z, z, g, gj, bas, reussi_j=reussi, jours_j=j_)
    np.testing.assert_allclose(b, [-0.5, 1.0, -1.0, -2.0])                      # mêmes réussites : rien en plus
    c = JEU.note_challenges(reussi, j_, z, z, g, gj, bas, reussi_j=z, jours_j=jours)
    np.testing.assert_allclose(c, a)                                            # jumeau sans réussite : bonus entier


@pytest.fixture
def tournant5(monde_invente, monkeypatch):
    """Examen tournant sur le marché inventé : 5 blocs de 20 jours (un par mois, mars -> juillet 2019), le dernier NEUF."""
    from collapsar.ecole.precision import tournant as TN
    monkeypatch.setattr(R(), "examen_tournant", SimpleNamespace(
        graine=5, de="2019-03-01", jusqua="2019-08-01", tranche_mois=1, bloc_jours=20, marge_avant_jours=3,
        marge_apres_jours=3, blocs_par_generation=2, marches=["EURUSD"], appris_jusqua="2019-06-15"), raising=False)
    monkeypatch.setattr(R().monde, "challenge_jours", 20)
    return TN


def test_l_examen_tourne_et_les_blocs_neufs_sont_un_temoin(tournant5, monkeypatch):
    TN = tournant5
    assert [b["debut"] for b in TN.blocs()] == ["2019-03-01", "2019-04-01", "2019-05-01", "2019-06-01", "2019-07-01"]
    U, ex = TN.monde_examen_tournant("cpu")
    tirages = {tuple(ex.tirage(g)) for g in range(1, 12)}
    assert len(tirages) > 2 and all(len(t) == 2 for t in tirages)                 # change d'une génération à l'autre
    assert ex.tirage(7) == ex.tirage(7)                                          # le même pour toutes les branches
    monkeypatch.setattr(R().examen_tournant, "temoins_neufs", True, raising=False)
    U, ex = TN.monde_examen_tournant("cpu")
    for g in range(1, 8):
        ch = ex.tirer(g)
        assert 4 in ch and len(ch) == 3 and set(ch) - {4} <= {0, 1, 2, 3}       # neuf toujours là, + 2 tirés parmi 4
    x = ex.jouer_un(_vieux(1), 1)
    n = np.asarray(x["notes"])
    tem = np.asarray(ex.temoin)
    assert tem.sum() == 2 and x["note"] == pytest.approx(n[~tem].mean())          # la note ignore le témoin
    assert x["temoin"]["blocs"] == [4] and x["temoin"]["gain_pct_mois"] == pytest.approx(
        np.asarray(x["gains_pct_mois"])[tem].mean())
    assert x["note_toutes"] == pytest.approx(n.mean())
    monkeypatch.setattr(R().examen_tournant, "note_cotes", "moins_bon", raising=False)
    xa, xb = ex.jouer_un(_vieux(1), 1), ex.jouer_un(_vieux(2), 1)
    assert len(xa["notes_selection_blocs"]) == 2                                  # écarts de coupe sans le témoin
    pan = np.asarray(ex.panier)
    na = np.asarray(xa["notes"])
    assert xa["note"] == pytest.approx(min(na[~tem & (pan == 0)].mean(), na[~tem & (pan == 1)].mean()))


def test_passage_a_la_note_au_gain_reel(tmp_path, monkeypatch):
    from collapsar.arbre.jardinier import Arbre, Reglages
    from collapsar.ecole.precision import tournant as TN
    d = tmp_path / "or"
    d.mkdir()
    a = Arbre(Reglages(places=2))
    for nom_t in ("x", "y"):
        b = a.naitre([], {"nom": nom_t})
        for s in (0.1, 0.2, 0.3):
            a.noter(b.nom, s)
        b.record = 0.3
    a.sauver(d / "arbre.json")
    (d / "journal_croissance.jsonl").write_text("", encoding="utf-8")
    assert TN.passer_gain_reel(d, lambda *_: None) is False                     # réglage absent : rien
    monkeypatch.setattr(R().note, "gain_reel", True, raising=False)
    assert TN.passer_gain_reel(d, lambda *_: None) is True
    a2 = Arbre.charger(d / "arbre.json")
    assert all(b.scores == [] and b.record is None for b in a2.vivantes())
    info = json.loads((d / TN.FICHIER_GAIN_REEL).read_text(encoding="utf-8"))
    assert len(info["notes_avant"]["A"]) == 3
    assert TN.passer_gain_reel(d, lambda *_: None) is False                     # une seule fois


# ================================================================================================ 2. apprentissage
def test_planchers_de_vitesse_et_de_curiosite(petite_ecole, monkeypatch):
    L, d = petite_ecole
    monkeypatch.setattr(R().arbre, "vitesse_min", 1e-4, raising=False)
    monkeypatch.setattr(R().arbre, "curiosite_min", 0.003, raising=False)
    br = L.Branche("A", {"vitesse": 3e-5, "curiosite": 0.0005}, "cpu")
    assert br.t["vitesse"] == 1e-4 and br.t["curiosite"] == 0.003
    assert all(g["lr"] == 1e-4 for g in br.opt.param_groups)
    monkeypatch.setattr(R().arbre, "vitesse_min", None)
    monkeypatch.setattr(R().arbre, "curiosite_min", None)
    assert L.Branche("B", {"vitesse": 3e-5, "curiosite": 0.0005}, "cpu").t["vitesse"] == 3e-5   # absent : comme avant


def test_plancher_du_hasard(monde_invente):
    from collapsar.ecole.precision import jeu as JEU
    from collapsar.ecole.precision.univers import Univers
    U = Univers([("EURUSD", False)], pd.Timestamp("2019-03-01"), pd.Timestamp("2019-09-01"), "cpu")
    lecon = JEU.Lecon(U, 16, np.random.default_rng(0))
    net = _vieux(1)
    torch.manual_seed(0)
    m, _ = lecon.jouer(net, 64)
    etat = {k: v.clone() for k, v in net.state_dict().items()}
    res = []
    for plancher in (None, (50.0, 1.0)):
        net.load_state_dict(etat)
        opt = torch.optim.AdamW(net.parameters(), lr=1e-3)
        torch.manual_seed(1)
        for _ in range(3):
            a = JEU.apprendre(net, opt, lecon.table, m, 1, 256, 0.2, 0.0, plancher=plancher)
        res.append(a["hasard"])
    assert res[1] > res[0]                                                       # le plancher pousse le hasard vers le haut


# ================================================================================================ 3. ordres
def _table_avec_ordre(U, B=24):
    from collapsar.ecole.precision import jeu as JEU
    tb = JEU.Table(U, B, 1)
    dep = np.random.default_rng(0).integers(U.premier[0], U.T - 900, B)
    tb.demarrer(np.ones(B, bool), np.zeros((B, 1), np.int64), dep)
    c = tb.cpt
    p = U.c[c.t, 0]
    c.att[:, 0] = 1
    c.att_prix[:, 0] = p * 0.97                                                 # ordre d'achat limite loin du prix
    c.att_u[:, 0] = 1000.0
    c.att_stop[:, 0] = p * 0.96
    c.att_reste[:, 0] = 96
    return tb


def test_ordre_en_attente_n_empeche_plus_d_ouvrir(monde_invente, monkeypatch):
    from collapsar.ecole.precision import cerveau as C
    from collapsar.ecole.precision import jeu as JEU
    from collapsar.ecole.precision.univers import Univers
    U = Univers([("EURUSD", False)], pd.Timestamp("2019-03-01"), pd.Timestamp("2019-09-01"), "cpu")
    net = _vieux(1)
    with torch.no_grad():
        net.tetes.bias[C.ACHAT_M] = 30.0                                       # elle veut acheter au marché
    qui = np.arange(24)
    for permis in (False, True):
        monkeypatch.setattr(R().mains, "marche_annule_ordre", permis, raising=False)
        tb = _table_avec_ordre(U)
        torch.manual_seed(0)
        dec = JEU.Decideur(tb, net, evaluer=False, graphe=False)
        (choix, *_), _, paquet = dec(qui)
        g = choix["geste"][:, 0].numpy()
        if not permis:
            assert not (g == C.ACHAT_M).any()                                  # avant : bloquée par l'ordre en attente
            continue
        assert (g == C.ACHAT_M).mean() > 0.5
        lv = JEU.niveaux_np(paquet[:, :len(qui)])
        tb.appliquer(qui, lv)
        ach = lv["ouvre"][:, 0] & ~lv["limite"][:, 0]
        assert (tb.cpt.att[ach, 0] == 0).all()                                  # l'ordre en attente est annulé
        tb.avancer()
        ev = tb.cpt.evt[:, 0]
        assert ((ev[ach] & SIM.OUVERTE) != 0).mean() > 0.5                      # et l'achat au marché part


def test_ordre_limite_plafonne_en_distance(monde_invente, monkeypatch):
    from collapsar.ecole.precision import jeu as JEU
    from collapsar.ecole.precision.univers import Univers
    from collapsar.ecole.precision import cerveau as C
    U = Univers([("EURUSD", False)], pd.Timestamp("2019-03-01"), pd.Timestamp("2019-09-01"), "cpu")
    net = _vieux(2)
    with torch.no_grad():
        net.tetes.bias[C.ACHAT_L] = net.tetes.bias[C.VENTE_L] = 3.0
    for cap in (6.0, 1.5):
        monkeypatch.setattr(R().mains, "entree_max_agitation", cap)
        tb = JEU.Table(U, 64, 1)
        dep = np.random.default_rng(1).integers(U.premier[0], U.T - 900, 64)
        tb.demarrer(np.ones(64, bool), np.zeros((64, 1), np.int64), dep)
        dec = JEU.Decideur(tb, net, evaluer=False, graphe=False)
        d = []
        for _ in range(200):
            c = tb.cpt
            qui = np.flatnonzero(c.actif & ((c.t >= tb.prochain) | tb.reveil))
            if len(qui):
                _, _, paquet = dec(qui)
                lv = JEU.niveaux_np(paquet[:, :len(qui)])
                lim = lv["limite"][:, 0] & lv["ouvre"][:, 0]
                p = U.c[c.t[qui], 0]
                A = U.A[c.t[qui], 0]
                d += list(np.abs(p - lv["entree"][:, 0])[lim] / A[lim])
                tb.appliquer(qui, lv)
            tb.avancer()
            tb.cpt.actif &= ~(tb.cpt.mort | tb.cpt.reussi)
        assert len(d) > 20 and max(d) <= cap + 1e-6


def test_ouvertures_executees_comptees_a_part(monde_invente, monkeypatch):
    from collapsar.ecole.precision import jeu as JEU
    from collapsar.ecole.precision.univers import Univers
    U = Univers([("EURUSD", False)], pd.Timestamp("2019-03-01"), pd.Timestamp("2019-09-01"), "cpu")
    monkeypatch.setattr(R().monde, "challenge_jours", 10)
    ex = JEU.Examen(U, [["EURUSD"]], pd.Timestamp("2019-06-01"), pd.Timestamp("2019-08-15"), 10)
    x0 = ex.jouer_un(_vieux(1), 5)
    assert "executions" not in x0                                               # réglage absent : comme avant
    monkeypatch.setattr(R().selection, "mesurer_executions", True, raising=False)
    x = ex.jouer_un(_vieux(1), 5)
    e = x["executions"]
    assert e["ouvertures_marche"] + e["ordres_limites_executes"] == x["trades_r"] + e["sans_resultat"]
    assert e["ordres_limites_poses"] >= e["ordres_limites_executes"]
    assert e["ouvertures_executees_mois"] == pytest.approx(x["trades_mois"])
    assert len(x["gains_jumeau_pct_mois"]) == len(x["gains_pct_mois"]) and len(x["r_par_challenge"]) == x["challenges"]
    assert np.allclose(x["notes"], x0["notes"])                                  # les mesures ne changent rien


# ================================================================================================ 4. P2
def test_meilleure_version_seulement_si_les_garde_fous_passent(petite_ecole, monkeypatch):
    L, d = petite_ecole
    base = ["--dossier", str(d), "--appareil", "cpu", "--muet"]
    monkeypatch.setattr(R().selection, "trades_mois_min", 1e9)                    # toutes paralysées à l'examen
    monkeypatch.setattr(R().gardefous, "meilleure_apres_gardefous", True, raising=False)
    L.main(["--generations", "1"] + base)
    assert not list((d / "branches").glob("*_meilleur.pt"))
    lignes = [json.loads(x) for x in (d / "journal_croissance.jsonl").read_text(encoding="utf-8").splitlines()]
    assert sum(x.get("quoi") == "garde_fou" for x in lignes) == 2


def test_avant_la_correction_une_version_paralysee_devenait_la_meilleure(petite_ecole, monkeypatch):
    L, d = petite_ecole
    base = ["--dossier", str(d), "--appareil", "cpu", "--muet"]
    monkeypatch.setattr(R().selection, "trades_mois_min", 1e9)
    L.main(["--generations", "1"] + base)
    assert len(list((d / "branches").glob("*_meilleur.pt"))) == 2


# ================================================================================================ 5. frais
def test_frais_par_heure_et_annonces():
    from collapsar.ecole.precision import frais_honnetes as FH
    Q = 15 * 60 * 10 ** 9
    t = pd.Timestamp("2019-03-04 01:00").value + np.arange(96 * 2) * Q
    t = t[(t - t[0]) % (24 * 4 * Q) < 23 * 4 * Q]                               # 23 h par jour, pause d'une heure
    ouvert = np.ones((len(t), 2), bool)
    fh = SimpleNamespace(reouverture=3.0, avant_pause=2.0, annonce=4.0, minutes_avant=0, minutes_apres=15)
    a = np.array([pd.Timestamp("2019-03-04 15:30").value, pd.Timestamp("2019-03-05 14:35").value])
    f, bil = FH.facteurs(t, ouvert, fh, annonces_ns=a)
    i = lambda s: int(np.flatnonzero(t == pd.Timestamp(s).value)[0])
    assert f[i("2019-03-04 23:45"), 0] == 2.0 and f[i("2019-03-05 01:00"), 0] == 3.0      # avant la pause, réouverture
    assert f[i("2019-03-04 01:00"), 0] == 1.0                                    # le tout début n'est pas une réouverture
    assert f[i("2019-03-04 15:30"), 1] == 4.0 and f[i("2019-03-04 15:15"), 1] == 1.0 and f[i("2019-03-04 15:45"), 1] == 1.0
    assert f[i("2019-03-05 14:30"), 0] == 4.0 and f[i("2019-03-05 14:45"), 0] == 4.0      # annonce à 14h35 : 2 bougies
    assert bil["annonce"] == 3 and (f == 1.0).mean() > 0.9


def test_frais_honnetes_dans_le_monde_et_stop_plus_cher(monde_invente, monkeypatch):
    from collapsar.ecole.precision.univers import Univers
    U0 = Univers([("EURUSD", False)], pd.Timestamp("2019-03-01"), pd.Timestamp("2019-09-01"), "cpu")
    assert not hasattr(U0, "facteur_frais")                                      # réglage absent : comme avant
    fh = SimpleNamespace(reouverture=3.0, avant_pause=2.0, annonce=4.0, minutes_avant=0, minutes_apres=15,
                         annonce_devises=["USD"])
    monkeypatch.setattr(R(), "frais_honnetes", fh, raising=False)
    U = Univers([("EURUSD", False)], pd.Timestamp("2019-03-01"), pd.Timestamp("2019-09-01"), "cpu")
    np.testing.assert_allclose(U.demi, U0.demi * U.facteur_frais)
    assert (U.facteur_frais == 4.0).sum() > 10                                   # annonces de 2019 rencontrées
    assert torch.allclose(U.tDEMI.cpu(), torch.as_tensor(U.demi, dtype=torch.float32))
