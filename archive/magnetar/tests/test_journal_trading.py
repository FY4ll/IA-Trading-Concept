"""Tests du JOURNAL DE TRADING (18/10/2026, collapsar/ecole/precision/journal_trading.py, journal_dessin.py,
journal_analyse.py) :
- HYPERNOVA et MAGNETAR (vraie cime figée, réglages de l'or) EXACTEMENT comme avant tant que rien n'est greffé ;
- un compte vit dans l'ordre du temps (une bougie à la fois) ;
- visibilité de l'Historique : « fermeture » (comme MT5) et « lendemain » (J+1 00h00 serveur), et SANS FUTUR (un trade
  non fermé, fermé plus tard ou fermé le jour même en mode lendemain ne change rien à ce qu'elle voit) ;
- un journal PAR COMPTE, continué seulement si la chronologie le permet ;
- greffe à zéro : mêmes décisions (partie, examen), apprentissage qui passe ; greffe d'UNE branche d'un arbre et retour ;
- prix de sortie et raisons cohérents avec le simulateur ; fichiers de log écrits, rotation, résumé, dessin d'un trade.
Depuis Test_IA : $env:CUDA_VISIBLE_DEVICES='-1'; venv_gpu\\Scripts\\python.exe -m pytest collapsar/tests/test_journal_trading.py -q
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

import numpy as np
import pandas as pd
import pytest
import torch

from collapsar.donnees.marches import RACINE
from collapsar.ecole.precision import journal_trading as JN
from collapsar.ecole.precision.reglages import R
from collapsar.mains.simulateur import CAPITAL

from test_ecole_precision import monde_invente, petite_ecole  # noqa: F401  (fixtures partagées)


@pytest.fixture(autouse=True)
def logs_eteints():
    JN.allumer_logs(None)
    yield
    JN.allumer_logs(None)


def _vieux(graine=4):
    from collapsar.ecole.precision import cerveau as C
    torch.manual_seed(graine)
    net = C.Cerveau()
    with torch.no_grad():                                    # des têtes « apprises » qui tradent souvent
        net.tetes.weight.normal_(0, 0.05)
        net.tetes.bias.normal_(0, 0.5)
        net.delai.weight.normal_(0, 0.05)
        net.tetes.bias[0] = -1.0
    return net


def _greffe(net, delai="fermeture"):
    from collapsar.ecole.precision import cerveau as C
    e2, change = JN.greffer_etat({"cerveau": net.state_dict()}, delai)
    assert change and JN.greffer_etat(e2)[1] is False
    neuf = C.Cerveau(journal=True, delai=delai)
    neuf.load_state_dict(e2["cerveau"])
    return neuf


def _univers():
    from collapsar.ecole.precision.univers import Univers
    return Univers([("EURUSD", False)], pd.Timestamp("2019-03-01"), pd.Timestamp("2019-09-01"), "cpu")


def _jouer(U, net, B=24, bougies=700, graine=1, logs=False, a_chaque=None):
    from collapsar.ecole.precision import jeu as JEU
    JN.allumer_logs("x" if logs else None)
    net.journal_logs = logs                                  # comme le cœur pour la cime à l'école
    tb = JEU.Table(U, B, 1)
    JN.equiper(tb, net, "ecole")
    assert (tb.carnet is not None) == (logs or net.n_journal > 0)
    rng = np.random.default_rng(0)
    tb.demarrer(np.ones(B, bool), np.zeros((B, 1), np.int64), rng.integers(U.premier[0], U.T - bougies - 200, B))
    dec = JEU.Decideur(tb, net, evaluer=True, graphe=False)
    torch.manual_seed(graine)
    c = tb.cpt
    gestes = []
    for k in range(bougies):
        qui = np.flatnonzero(c.actif & ((c.t >= tb.prochain) | tb.reveil))
        if len(qui):
            (choix, *_), _, paquet = dec(qui)
            gestes.append(choix["geste"][:len(qui)].clone())
            if a_chaque is not None:
                a_chaque(k, tb, qui)
            tb.appliquer(qui, JEU.niveaux_np(paquet[:, :len(qui)]))
        t_av = c.t.copy()
        act = c.actif.copy()
        tb.avancer()
        assert np.array_equal(c.t[act], np.minimum(t_av[act] + 1, U.T - 1))       # une bougie, dans l'ordre du temps
        c.actif &= ~(c.mort | c.reussi)
    return c.valeurs().copy(), torch.cat(gestes), tb


# ================================================================================================ rien ne change
def test_hypernova_et_magnetar_exactement_comme_avant():
    import empreinte_hypernova as E
    ref = np.load(E.FICHIER)
    out = E.calculer()
    for k in ref.files:
        assert np.array_equal(ref[k], out[k], equal_nan=ref[k].dtype.kind == "f"), k
    env = {**os.environ, "CUDA_VISIBLE_DEVICES": "-1"}
    env.pop("COLLAPSAR_PRECISION_REGLAGES", None)
    p = subprocess.run([sys.executable, "-m", "collapsar.tests.empreinte_magnetar", "comparer"], cwd=RACINE, env=env,
                       capture_output=True, text=True, timeout=600)
    assert p.returncode == 0 and "RESULTAT IDENTIQUE" in p.stdout, p.stdout[-2000:] + p.stderr[-2000:]


def test_eteint_par_defaut(monde_invente):
    import yaml
    from collapsar.ecole.precision import cerveau as C
    from collapsar.ecole.precision import jeu as JEU
    from collapsar.ecole.precision import reglages as RG
    for f in (RG.DEFAUT, RG.DEFAUT.with_name("reglages_or.yaml")):
        assert "journal" not in yaml.safe_load(f.read_text(encoding="utf-8"))
    assert C.Cerveau().n_journal == 0 and not JN.logs_actifs() and JN.delai_defaut() == "fermeture"
    U = _univers()
    lecon = JEU.Lecon(U, 8, np.random.default_rng(0))
    lecon.jouer(C.Cerveau(), 8)
    assert lecon.table.carnet is None
    ex = JEU.Examen(U, [["EURUSD"]], pd.Timestamp("2019-06-01"), pd.Timestamp("2019-08-15"), 30)
    old = R().monde.challenge_jours
    R().monde.challenge_jours = 5
    try:
        ex.jouer_un(C.Cerveau(), 1)
    finally:
        R().monde.challenge_jours = old
    assert next(iter(ex._tables.values()))[0].carnet is None


def test_tailles():
    from collapsar.ecole.precision import cerveau as C
    assert JN.NT == 12 and JN.NH == 147 and JN.NJ == 159 and len(JN.NOMS) == JN.NJ
    assert C.Cerveau(journal=True).F == C.Cerveau().F + JN.NJ


# ================================================================================================ greffe à zéro
def test_greffe_ne_change_aucune_decision(monde_invente):
    """Même partie (gestes, comptes) : ancien cerveau, ancien cerveau + fichiers de log, cerveau greffé qui VOIT son
    journal (non nul) ; même examen ; une leçon et un pas d'apprentissage passent avec le journal."""
    from collapsar.ecole.precision import cerveau as C
    from collapsar.ecole.precision import jeu as JEU
    U = _univers()
    vieux = _vieux()
    v0, g0, _ = _jouer(U, vieux, bougies=500)
    v1, g1, tb1 = _jouer(U, vieux, bougies=500, logs=True)
    neuf = _greffe(vieux)
    vus = []
    v2, g2, tb2 = _jouer(U, neuf, bougies=500, a_chaque=lambda k, tb, qui: vus.append(
        tb.carnet.historique(torch.as_tensor(qui), torch.as_tensor(tb.cpt.t[qui]), torch.zeros(len(qui), 1, 2, JN.NSIT))))
    assert len(g0) > 1000 and (g0 > 0).sum() > 300
    assert torch.equal(g0, g1) and np.array_equal(v0, v1) and len(tb1.carnet.histo) > 50
    assert torch.equal(g0, g2) and np.array_equal(v0, v2)
    assert (torch.cat(vus).abs() > 0).float().mean() > 0.3                    # elle voit bien quelque chose
    old = R().monde.challenge_jours
    R().monde.challenge_jours = 10
    try:
        ex = JEU.Examen(U, [["EURUSD"]], pd.Timestamp("2019-06-01"), pd.Timestamp("2019-08-15"), 10)
        x0 = ex.jouer_un(vieux, 5)
        x2 = ex.jouer_un(neuf, 5)
    finally:
        R().monde.challenge_jours = old
    assert x0["notes"] == x2["notes"] and x0["gains_pct_mois"] == x2["gains_pct_mois"] and set(x0) == set(x2)
    opt = torch.optim.AdamW(neuf.parameters(), lr=3e-4)
    lecon = JEU.Lecon(U, 16, np.random.default_rng(0))
    m, b = lecon.jouer(neuf, 64)
    assert m["pos"].shape[-1] == C.N_POS + JN.NJ
    a = JEU.apprendre(neuf, opt, lecon.table, m, 1, 256, 0.2, 0.003)
    assert np.isfinite(a["perte_decision"])
    assert neuf.marche[0].weight.grad is not None


def test_greffe_de_l_optimiseur_et_adapter():
    from collapsar.ecole.precision import cerveau as C
    torch.manual_seed(0)
    net = C.Cerveau()
    opt = torch.optim.AdamW(net.parameters(), lr=1e-3)
    net.marche[0].weight.sum().backward()
    opt.step()
    e2, _ = JN.greffer_etat({"cerveau": net.state_dict(), "opt": opt.state_dict(), "temperament": {"nom": "x"}}, "lendemain")
    w = e2["cerveau"]["marche.0.weight"]
    assert w.shape[1] == net.F + JN.NJ and (w[:, net.F:] == 0).all()
    assert torch.equal(w[:, :net.F], net.marche[0].weight.detach())
    assert e2["temperament"]["journal"]["delai_historique"] == "lendemain"
    neuf = C.cerveau_pour(e2["cerveau"])
    assert neuf.n_journal == JN.NJ
    o2 = torch.optim.AdamW(neuf.parameters(), lr=1e-3)
    o2.load_state_dict(e2["opt"])
    # un garde-fou qui ramène une branche sans journal à une cime au journal (et l'inverse)
    net.load_state_dict(C.adapter(neuf.state_dict(), net))
    neuf.load_state_dict(C.adapter(net.state_dict(), neuf))
    assert JN.choix_branche({"journal": {"delai_historique": "lendemain"}}, None) == (True, "lendemain")


# ================================================================================================ visibilité
@pytest.mark.parametrize("delai", ["fermeture", "lendemain"])
def test_visibilite_de_l_historique(monde_invente, monkeypatch, delai):
    """À chaque regard : les trades visibles sont EXACTEMENT ses trades fermés selon la règle (fermeture : fermé dans
    une bougie <= t ; lendemain : jour du serveur de la décision > jour de la fermeture) ; jamais un trade ouvert."""
    monkeypatch.setattr(JN, "ECHANTILLON", 10 ** 6)
    U = _univers()
    neuf = _greffe(_vieux(), delai)
    jd = pd.to_datetime(U.t_ns + JN.QUINZE_NS).normalize()
    jf = pd.to_datetime(U.t_ns).normalize()
    vus = {"cas": 0, "visibles": 0, "caches_meme_jour": 0}

    def verifier(k, tb, qui):
        if k % 7:
            return
        cn, c = tb.carnet, tb.cpt
        t = c.t[qui]
        vis = cn.visibles(torch.as_tensor(qui), torch.as_tensor(t)).numpy()
        tk = cn.hTk[torch.as_tensor(qui)].numpy()
        for i, b in enumerate(qui):
            visibles = set(tk[i][vis[i]].tolist())
            fermes = [h for h in cn.histo if h["compte"] == b]
            if delai == "fermeture":
                attendu = {h["ticket"] for h in fermes if h["fin_ligne"] <= t[i]}
            else:
                attendu = {h["ticket"] for h in fermes if jd[t[i]] > jf[h["fin_ligne"]]}
                vus["caches_meme_jour"] += sum(1 for h in fermes if h["fin_ligne"] <= t[i] and jd[t[i]] <= jf[h["fin_ligne"]])
            assert visibles == attendu, (b, t[i])
            ouverts = set(cn.p["ticket"][b][cn.p_open[b]].tolist())
            assert not (visibles & ouverts)
            vus["cas"] += 1
            vus["visibles"] += len(visibles)
    _jouer(U, neuf, B=16, bougies=900, a_chaque=verifier, logs=True)
    assert vus["cas"] > 100 and vus["visibles"] > 200
    if delai == "lendemain":
        assert vus["caches_meme_jour"] > 0                                    # la règle J+1 a bien caché des trades


def test_sans_futur_et_par_compte(monde_invente):
    """Ce qu'elle voit à t ne change pas si l'on ajoute un trade fermé APRÈS t (ou à un AUTRE compte) ; il change si
    le trade est visible."""
    U = _univers()
    neuf = _greffe(_vieux())
    _, _, tb = _jouer(U, neuf, B=8, bougies=500)
    cn = tb.carnet
    qui = np.arange(8)
    t = torch.as_tensor(tb.cpt.t[qui])
    q = torch.randn(8, 1, 2, JN.NSIT)
    f0 = cn.historique(torch.as_tensor(qui), t, q)
    tr = lambda b, vis: {"hS": np.zeros((1, JN.NSIT), np.float32), "hSens": np.array([1.0]), "hR": np.array([9.0]),
                         "hPnl": np.array([5.0]), "hHfin": np.array([0.0]), "hCh": np.full((1, 6), 3.0),
                         "hCat": np.array([0]), "hVis": np.array([vis]), "hTk": np.array([999])}
    cn._inserer(np.array([0]), tr(0, int(t[0]) + 1))                          # fermé plus tard : invisible
    assert torch.equal(cn.historique(torch.as_tensor(qui), t, q), f0)
    cn._inserer(np.array([1]), tr(1, int(t[1])))                              # visible, mais pour le compte 1 seulement
    f2 = cn.historique(torch.as_tensor(qui), t, q)
    assert not torch.equal(f2[1], f0[1])
    assert torch.equal(f2[0], f0[0]) and torch.equal(f2[2:], f0[2:])


def test_journal_continue_seulement_dans_l_ordre_du_temps(monde_invente):
    U = _univers()
    neuf = _greffe(_vieux())
    _, _, tb = _jouer(U, neuf, B=6, bougies=500)
    cn = tb.carnet
    n0 = cn.hN_np.copy()
    assert (n0 > 0).all()
    t = tb.cpt.t.copy()
    plus_tard = np.minimum(t + 50, U.T - 1)
    tb.demarrer(np.r_[True, True, True, False, False, False], np.zeros((3, 1), np.int64),
                np.r_[plus_tard[0], t[1] - 2000, plus_tard[2]])
    assert cn.hN_np[0] == n0[0] and cn.hN_np[2] == n0[2]                     # départ après sa dernière fermeture : continue
    assert cn.hN_np[1] == 0 and int(cn.hN[1]) == 0                            # départ plus tôt : journal vide
    assert np.array_equal(cn.hN_np[3:], n0[3:])
    cn.vider()
    assert (cn.hN_np == 0).all() and int(cn.hN.sum()) == 0


# ================================================================================================ sorties
def test_prix_de_sortie_et_raisons(monde_invente, monkeypatch):
    """Pour chaque trade fermé sans objectif 1 partiel : résultat en $ = sens x volume x (sortie - entrée) (aux nuits
    près) ; R du journal = R du simulateur ; raisons cohérentes."""
    monkeypatch.setattr(JN, "ECHANTILLON", 10 ** 6)
    U = _univers()
    rs = []
    vieux = _vieux()
    _, _, tb = _jouer(U, vieux, B=16, bougies=800, logs=True,
                      a_chaque=lambda k, tb, qui: None)
    h = JN.table_historique(tb.carnet.histo)
    assert len(h) > 100 and set(h["raison"]) <= set(JN.RAISONS)
    brut = pd.DataFrame(tb.carnet.histo)                                     # valeurs brutes (le fichier arrondit)
    plein = h[~h["objectif1_atteint"].astype(bool)]
    b = brut.loc[plein.index]
    sens = np.where(plein["sens"] == "achat", 1.0, -1.0)
    attendu = sens * b["vol"] * (b["prix_fin"] - b["prix_ouv"])
    plein = plein.assign(resultat_usd=b["pnl"])
    # sans nuit (ni minuit du serveur pendant le trade, ni ouverture à minuit) : égalité au centime
    nuit = (plein["ouverture"].str[:10] != plein["fermeture"].str[:10]) | plein["ouverture"].str.endswith("00:00")
    ecart = np.abs(plein["resultat_usd"] - attendu)
    assert h[["prix_ouverture", "prix_fermeture", "stop_origine", "stop_final", "resultat_usd", "r"]].notna().all().all()
    mauvais = plein[~nuit & ~(ecart <= 0.011)]
    assert (~nuit).sum() > 100 and mauvais.empty, mauvais[["raison", "ouverture", "fermeture", "prix_ouverture",
                                                           "prix_fermeture", "volume", "resultat_usd"]].to_string()
    assert (ecart[nuit] <= 0.05 * plein["risque_pct"][nuit] / 100 * CAPITAL + 1.0).mean() > 0.8
    st = h[h["raison"] == "stop"]
    assert len(st) and (st["r"] < -0.5).mean() > 0.9                          # un stop pris coûte ~1 R
    assert (h["meilleur_r"] >= h["r"] - 1e-9).all() and (h["pire_r"] <= h["r"] + 1e-9).all()
    o = JN.table_onglet(tb.carnet.onglet)
    assert len(o) > 100 and {"position", "ordre"} <= set(o["ligne"])


# ================================================================================================ greffe d'un arbre
def _arbre(d):
    from collapsar.arbre.jardinier import Arbre, Reglages
    from collapsar.ecole.precision import cerveau as C
    (d / "branches").mkdir(parents=True)
    a = Arbre(Reglages(places=3))
    for i, notes in enumerate(([0.1, 0.0, -0.1], [0.5, 0.5, 0.5], [0.2, 0.2, 0.2])):
        b = a.naitre([], {"nom": f"b{i}", "vitesse": 3e-4, "curiosite": 0.003})
        for s in notes:
            a.noter(b.nom, s)
        torch.manual_seed(i)
        net = C.Cerveau()
        opt = torch.optim.AdamW(net.parameters(), lr=3e-4)
        torch.save({"cerveau": net.state_dict(), "opt": opt.state_dict(), "temperament": b.temperament},
                   d / "branches" / f"{b.nom}.pt")
        torch.save({"cerveau": net.state_dict()}, d / "branches" / f"{b.nom}_meilleur.pt")
    a._elire_cime()
    a.fin_de_battement()
    a.sauver(d / "arbre.json")
    torch.save({"cerveau": torch.load(d / "branches" / "B.pt", weights_only=False)["cerveau"], "branche": "B",
                "generation": 1}, d / "cime.pt")
    (d / "journal_croissance.jsonl").write_text("", encoding="utf-8")


def test_greffe_d_une_seule_branche_et_retour(tmp_path):
    from collapsar.arbre.jardinier import Arbre
    from collapsar.ecole.precision import cerveau as C
    d = tmp_path / "or"
    _arbre(d)
    avant = {f.name: torch.load(f, weights_only=False)["cerveau"] for f in (d / "branches").glob("*.pt")}
    info = JN.greffer(d, branche="C", dire=lambda *_: None)
    assert info["fichiers"] == ["C.pt", "C_meilleur.pt"] and (d / "journal.json").exists()
    assert (d / "sauvegardes").exists()
    for f in (d / "branches").glob("*.pt"):
        e = torch.load(f, weights_only=False)["cerveau"]
        assert C.a_journal(e) == f.name.startswith("C")                      # une seule branche
        if not f.name.startswith("C"):
            assert all(torch.equal(e[k], v) for k, v in avant[f.name].items())
    assert Arbre.charger(d / "arbre.json").branches["C"].temperament["journal"]["delai_historique"] == "fermeture"
    assert not C.a_journal(torch.load(d / "cime.pt", weights_only=False)["cerveau"])        # la cime B intacte
    with pytest.raises(SystemExit):
        JN.greffer(d, nouvelle=True, dire=lambda *_: None)                  # une seule greffe
    JN.defaire(d, dire=lambda *_: None)
    assert not (d / "journal.json").exists()
    assert not C.a_journal(torch.load(d / "branches" / "C.pt", weights_only=False)["cerveau"])
    # --nouvelle : la plus faible (A) archivée, une branche « journal » née de la cime B
    info = JN.greffer(d, nouvelle=True, dire=lambda *_: None)
    assert info["remplacee"] == "A" and info["branches"] == ["D"]
    a = Arbre.charger(d / "arbre.json")
    assert a.cime == "B" and a.branches["D"].parents == ["B"] and a.branches["D"].temperament["nom"] == "journal"
    e = torch.load(d / "branches" / "D.pt", weights_only=False)
    cb = torch.load(d / "branches" / "B.pt", weights_only=False)["cerveau"]
    assert C.a_journal(e["cerveau"]) and not C.a_journal(cb)
    w = e["cerveau"]["marche.0.weight"]
    assert torch.equal(w[:, :-JN.NJ], cb["marche.0.weight"]) and (w[:, -JN.NJ:] == 0).all()
    JN.defaire(d, dire=lambda *_: None)
    assert (d / "branches" / "A.pt").exists() and not (d / "branches" / "D.pt").exists()


def test_coeur_avec_une_branche_au_journal_logs_et_dessin(petite_ecole, monkeypatch):
    """Petite école : 1 génération, arrêt, greffe d'UNE branche (--nouvelle), le cœur reprend : la branche au journal
    voit son journal, les fichiers de log sont écrits, le résumé et le dessin d'un trade marchent."""
    from collapsar.ecole.precision import journal_analyse as JA
    from collapsar.ecole.precision import journal_dessin as JD
    L, d = petite_ecole
    monkeypatch.setattr(R().monde, "challenge_jours", 10)
    monkeypatch.setattr(R().ecole, "bougies_par_lecon", 96)
    base = ["--dossier", str(d), "--appareil", "cpu", "--muet"]
    L.main(["--generations", "1"] + base)
    assert not (d / "journal_trades").exists()                              # rien tant que rien n'est greffé
    info = JN.greffer(d, nouvelle=True, dire=lambda *_: None)
    L.main(["--generations", "2"] + base)
    assert json.loads((d / "arbre.json").read_text(encoding="utf-8"))["battements"] == 2
    g = d / "journal_trades" / "g00002"
    nouvelle = info["branches"][0]
    assert (g / f"{nouvelle}_examen_historique.csv").exists() and (g / f"{nouvelle}_ecole_trade.csv").exists()
    h = pd.read_csv(g / f"{nouvelle}_ecole_historique.csv")
    assert len(h) > 0 and {"ticket", "ouverture", "prix_ouverture", "fermeture", "prix_fermeture", "stop_origine",
                           "stop_final", "raison", "resultat_usd", "r", "meilleur_r"} <= set(h.columns)
    texte = JA.resumer(JA.lire(d, 5, None, "tout"))
    assert "Catégorie" in texte and "Raison de sortie" in texte
    f = JD.dessiner(h.iloc[0], d / "essai.jpg")
    from PIL import Image
    w, hh = Image.open(f).size
    assert w <= 1400 and hh <= 1400
    lig = json.loads((d / "journal_croissance.jsonl").read_text(encoding="utf-8").splitlines()[-1])
    assert lig["quoi"] == "generation" and "_journal_s" in lig["temps"]


def test_rotation(tmp_path):
    for g in range(1, 131):
        (tmp_path / f"g{g:05d}").mkdir()
    JN.tourner(tmp_path)
    reste = sorted(int(p.name[1:]) for p in tmp_path.iterdir())
    assert reste == [50] + list(range(81, 131))                    # 50 dernières + une toutes les 50 (100 est dedans)
