"""Tests du CERVEAU SYMÉTRIQUE de MAGNETAR (19/10/2026, ecole/precision/symetrie.py) :
- la vue miroir est une involution exacte (miroir(miroir(x)) = x) pour toutes les formes de cerveau (journal, foule,
  tendance), et elle est bien le « graphique retourné » : les yeux calculés sur les prix réfléchis autour du prix
  (x -> 2 p - x) = la vue miroir ; le résumé de situation du journal s'échange achat <-> vente ;
- le cerveau symétrique : probabilité de chaque choix en x = celle du choix miroir en miroir(x) (niveaux réfléchis) ;
  monde parfaitement symétrique : P(achat) = P(vente) ; positions, ordres et journal remplis par une vraie partie ;
- sans le réglage, rien ne change (empreintes : test_trois_changements / test_suiveur) ; l'apprentissage et l'examen
  passent ; les anciennes sorties « vendre » ne reçoivent plus rien ;
- la greffe sur un petit arbre arrêté (branche née de la cime, la plus faible archivée, sauvegarde, preuves), une
  génération avec la branche marquée [SYMÉTRIQUE], puis les deux retours arrière.
Depuis Test_IA : $env:CUDA_VISIBLE_DEVICES='-1'; venv_gpu\\Scripts\\python.exe -m pytest collapsar/tests/test_symetrie.py -q
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest
import torch

from collapsar.ecole.precision import cerveau as C
from collapsar.ecole.precision import symetrie as SY
from collapsar.ecole.precision.reglages import R

from test_ecole_precision import monde_invente, petite_ecole  # noqa: F401  (fixtures partagées)


def _net(journal=False, tendance=False, graine=0):
    torch.manual_seed(graine)
    net = C.Cerveau(journal=journal, tendance=tendance)
    with torch.no_grad():                                   # des têtes non nulles : un cerveau qui a des préférences
        for p in net.parameters():
            p.add_(torch.randn_like(p) * 0.3)
    return C.regler_symetrie(net, {"symetrique": {"version": 1}})


@pytest.mark.parametrize("journal,tendance,foule", [(False, False, False), (True, False, False), (True, True, True),
                                                    (False, True, False)])
def test_vue_miroir_involution(journal, tendance, foule, monkeypatch):
    monkeypatch.setattr(R().yeux, "foule", foule)
    net = C.Cerveau(journal=journal, tendance=tendance)
    rang, signe = SY.plan_vue(net.F, net.n_journal, net.n_tendance)
    assert len(rang) == net.F and sorted(rang) == list(range(net.F))           # un simple rangement
    assert np.array_equal(rang[rang], np.arange(net.F))                       # deux fois = rien
    assert np.all(signe * signe[rang] == 1)
    x = torch.randn(3, 2, net.F)
    m = SY.miroir_vue(x, net)
    assert torch.equal(SY.miroir_vue(m, net), x) and not torch.equal(m, x)
    # quelques places vérifiées à la main : sens de la position inversé, onglet Trade inchangé
    p0 = net.F - net.n_tendance - net.n_journal - C.N_POS
    assert torch.equal(m[..., p0], -x[..., p0]) and torch.equal(m[..., p0 + 1], x[..., p0 + 1])
    assert torch.equal(m[..., p0 + 2], -x[..., p0 + 2]) and torch.equal(m[..., p0 + 3], x[..., p0 + 3])


def test_reglage_symetrie():
    net = C.Cerveau()
    assert C.regler_symetrie(net, None).symetrique is False
    assert C.regler_symetrie(net, {"nom": "precision"}).symetrique is False
    assert C.regler_symetrie(net, {"symetrique": {"version": 1}}).symetrique is True
    assert SY.est_symetrique({"symetrique": {"version": 1}}) and not SY.est_symetrique({})


def _univers(appareil="cpu", deux=False):
    from collapsar.ecole.precision.univers import Univers
    v = [("EURUSD", False), ("EURUSD", True)] if deux else [("EURUSD", False)]
    return Univers(v, pd.Timestamp("2019-03-01"), pd.Timestamp("2019-09-01"), appareil)


@pytest.mark.parametrize("journal", [False, True])
def test_cerveau_symetrique_miroir_exact(monde_invente, journal):
    """Vraies parties (positions, ordres, journal) : yeux des prix réfléchis = vue miroir, décisions miroir, monde
    symétrique sans préférence."""
    U = _univers()
    net = _net(journal=journal, graine=3)
    p = SY.prouver_miroir(net, U, B=96, bougies=150)
    assert p["involution_exacte"] and p["vue_miroir_differente"] and p["autres_choix_identiques"]
    assert p["en_position"] + p["ordre_en_attente"] > 0
    if journal:
        assert p["journal_non_vide"] > 0
    assert p["yeux_prix_reflechis_ecart_max"] < 1e-3
    assert p["situation_journal_ecart_max"] < 1e-4
    e = p["ecarts_max_x_contre_miroir"]
    assert max(e["lp"], e["lp_exec"], e["hasard"], e["lp_geste"], e["valeur"]) < 1e-4 and e["niveaux_prix"] < 1e-3
    assert p["ouvertures_tirees"]["achats"] + p["ouvertures_tirees"]["ventes"] > 0
    assert abs(p["monde_symetrique_P_achat"] - p["monde_symetrique_P_vente"]) < 1e-6         # (arrondis de la machine)
    assert p["monde_symetrique_P_achat"] > 0


def test_cerveau_ordinaire_pas_symetrique(monde_invente):
    """Contrôle : le MÊME cerveau sans le réglage n'a pas cette propriété (la preuve sait échouer)."""
    U = _univers()
    net = _net(graine=4)
    net.symetrique = False
    from collapsar.ecole.precision import jeu as JEU  # noqa: F401
    tb = SY._monter(net, U, 64, 80, 1)
    qui = np.flatnonzero(tb.cpt.actif)
    s, fm, fc, pos, car = SY._entrees(tb, net, qui)
    m, sm = SY.miroir_vue(fm, net), SY.miroir_structure(s)
    net.voir_lois = True
    with torch.no_grad():
        _, _, _, _, _, lv = C.politique(net, s, fm, fc, pos)
        _, _, _, _, _, lv2 = C.politique(net, sm, m, fc, m[..., car.shape[-1]:])
    assert float((lv["lp_geste"] - lv2["lp_geste"][..., list(SY.GESTE_MIROIR)]).abs().max()) > 1e-2


def test_vente_par_les_neurones_de_l_achat(monde_invente):
    """Les anciennes sorties « vendre » (marché, limite) ne servent plus : aucun gradient ; les sorties « acheter »,
    elles, apprennent aussi des ventes."""
    U = _univers()
    net = _net(graine=5)
    tb = SY._monter(net, U, 64, 120, 2)
    qui = np.flatnonzero(tb.cpt.actif)
    s, fm, fc, pos, _ = SY._entrees(tb, net, qui)
    torch.manual_seed(0)
    with torch.no_grad():
        ch, *_ = C.politique(net, s, fm, fc, pos)
    ch = {**ch, "geste": torch.where(s["slot"], torch.full_like(ch["geste"], C.VENTE_M), ch["geste"])}
    net.zero_grad()
    _, lp, *_ = C.politique(net, s, fm, fc, pos, ch)
    lp[torch.isfinite(lp) & (lp > -1e6)].sum().backward()
    gw = net.tetes.weight.grad
    assert float(gw[C.VENTE_M].abs().sum()) == 0 and float(gw[C.VENTE_L].abs().sum()) == 0
    assert float(gw[C.ACHAT_M].abs().sum()) > 0


def test_apprentissage_et_examen(monde_invente):
    from collapsar.ecole.precision import jeu as JEU
    U = _univers()
    net = _net(graine=6)
    avant = [p.detach().clone() for p in net.parameters()]
    opt = torch.optim.AdamW(net.parameters(), lr=3e-4, weight_decay=1e-4)
    lecon = JEU.Lecon(U, 32, np.random.default_rng(3))
    m, b = lecon.jouer(net, 64)
    a = JEU.apprendre(net, opt, lecon.table, m, 1, 256, 0.2, 0.003)
    assert np.isfinite(a["perte_decision"]) and a["regards_appris"] > 0
    assert any(not torch.equal(x, p) for x, p in zip(avant, net.parameters()))
    r = R()
    ancien = r.monde.challenge_jours
    r.monde.challenge_jours = 10
    try:
        ex = JEU.Examen(U, [["EURUSD"]], pd.Timestamp("2019-06-01"), pd.Timestamp("2019-08-15"), 10)
        x = ex.jouer_un(net, 5)
    finally:
        r.monde.challenge_jours = ancien
    assert np.isfinite(x["note"]) and "jumeau" in x


def test_greffe_generation_et_retours(petite_ecole, monkeypatch, capsys):
    """Petit arbre : 3 générations, arrêt, greffe (cime intacte, la plus faible archivée, branche née de la cime avec les
    mêmes poids), une génération avec la branche marquée, retour léger puis retour complet."""
    from collapsar.arbre.jardinier import Arbre
    L, d = petite_ecole
    monkeypatch.setattr(R().arbre, "places", 3)
    base = ["--dossier", str(d), "--appareil", "cpu", "--muet"]
    L.main(["--generations", "3"] + base)
    (d / "ARRET").write_text("")
    a = Arbre.charger(d / "arbre.json")
    cime = a.cime
    vivantes = [b.nom for b in a.vivantes()]
    faible = min((b for b in a.vivantes() if b.nom != cime and b.score is not None), key=lambda b: b.score).nom
    monkeypatch.setattr(SY, "_univers_preuve", lambda appareil="cpu": _univers(appareil, deux=True))
    info = SY.appliquer(d, None, lambda *_: None, leger=True)
    assert info["cime"] == cime and info["remplacee"] == faible
    a2 = Arbre.charger(d / "arbre.json")
    nouv = info["branche"]
    assert a2.branches[faible].morte is not None and (d / "archives" / f"{faible}.pt").exists()
    assert a2.branches[nouv].parents == [cime] and SY.est_symetrique(a2.branches[nouv].temperament)
    e_c = torch.load(d / "branches" / f"{cime}.pt", weights_only=False)
    e_s = torch.load(d / "branches" / f"{nouv}.pt", weights_only=False)
    assert all(torch.equal(e_c["cerveau"][k], e_s["cerveau"][k]) for k in e_c["cerveau"])      # mêmes poids
    assert SY.est_symetrique(e_s["temperament"]) and (d / "symetrique" / "preuves.json").exists()
    assert (d / "sauvegardes").exists() and (d / SY.FICHIER).exists()
    with pytest.raises(SystemExit):
        SY.appliquer(d, None, lambda *_: None, leger=True)                     # une seule fois
    (d / "ARRET").unlink()
    capsys.readouterr()
    L.main(["--generations", "4"] + base)
    sortie = capsys.readouterr().out
    assert f"{nouv} [SYMÉTRIQUE]" in sortie
    # retour léger : la branche symétrique archivée, l'arbre continue
    SY.retirer(d, lambda *_: None)
    a3 = Arbre.charger(d / "arbre.json")
    assert a3.branches[nouv].morte is not None and not (d / SY.FICHIER).exists()
    # retour complet : la vie d'avant la greffe (fichier remis pour le test)
    (d / SY.FICHIER).write_text(json.dumps(info), encoding="utf-8")
    SY.defaire(d, lambda *_: None)
    a4 = Arbre.charger(d / "arbre.json")
    assert sorted(b.nom for b in a4.vivantes()) == sorted(vivantes) and a4.battements == 3
    assert (d / "branches" / f"{faible}.pt").exists() and not (d / "archives" / f"{faible}.pt").exists()
