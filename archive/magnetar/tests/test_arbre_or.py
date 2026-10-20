"""Tests de l'ARBRE DE L'OR (18/10/2026, collapsar/ecole/precision/arbre_or.py + reglages_or.yaml + graine.py) :
- réglages séparés : HYPERNOVA garde les siens (nom, dossier, marchés, examen), l'arbre de l'or a les siens ;
- graine copiée de l'arbre source SANS rien y toucher (octets et dates identiques), seulement entre deux générations ;
- verrous indépendants, et le gardien ne confond jamais les deux cœurs ;
- mondes de l'or dans les deux sens, part du mouvement attrapée et gros trades à l'examen (réglage éteint par défaut).
Depuis Test_IA : $env:CUDA_VISIBLE_DEVICES='-1'; venv_gpu\\Scripts\\python.exe -m pytest collapsar/tests/test_arbre_or.py -q
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest
import torch

from collapsar.donnees.marches import RACINE
from collapsar.ecole.precision import reglages as RG
from collapsar.ecole.precision.reglages import R

from test_ecole_precision import monde_invente  # noqa: F401  (fixture partagée)

OR = Path(RG.__file__).with_name("reglages_or.yaml")


# ================================================================================================ réglages
def test_reglages_separes_et_hypernova_intact():
    assert RG.FICHIER == RG.DEFAUT and RG.NOM == "HYPERNOVA" and RG.VIE == RACINE / "collapsar" / "vie" / "hypernova"
    assert getattr(R().arbre, "graine", None) is None                       # HYPERNOVA : graine habituelle
    assert getattr(R().selection, "mesurer_mouvement", False) is False      # examen d'HYPERNOVA inchangé
    assert getattr(R().marches, "seulement", None) is None
    o = RG.lire(OR)
    p = o.periodes
    # 19/10 (EXAMEN TOURNANT, tournant.py) : apprentissage jusqu'à fin 2023 hors blocs d'examen ; sélection = le
    # réservoir des blocs 2010 -> 2023 (avant : apprentissage jusqu'à fin 2022, sélection 2023 seule)
    assert p.apprentissage_fin == pd.Timestamp("2024-01-01")
    assert (p.selection_de, p.selection_jusqua) == (pd.Timestamp("2010-01-01"), pd.Timestamp("2024-01-01"))
    assert o.examen_tournant.de == "2010-01-01" and o.examen_tournant.jusqua == "2024-01-01"
    assert getattr(R(), "examen_tournant", None) is None                    # HYPERNOVA : examen fixe
    assert (p.rapport_de, p.rapport_jusqua) == (pd.Timestamp("2024-01-01"), pd.Timestamp("2025-10-01"))
    assert p.fin_donnees <= pd.Timestamp("2025-10-01")
    assert list(o.marches.seulement) == ["XAUUSD@M1", "XAUUSD"]
    assert o.selection.paniers == [["XAUUSD@M1"], ["XAUUSD@M1_MIROIR"]]
    # mêmes yeux et mêmes mains qu'HYPERNOVA : les cerveaux hérités ont exactement les mêmes entrées et sorties ; seul
    # ajout (18/10) : le STOP SUIVEUR, greffé sans perte (suiveur.py, tests/test_suiveur.py), absent chez HYPERNOVA
    # 19/10 : 2e ajout, le COMPTE SWING (mains.compte, univers.regles_compte, tests/test_swing_peur.py) ; HYPERNOVA :
    # absent = compte « normal », comme avant
    # 19/10 soir (trois changements) : le SUIVEUR APRÈS +1R (mains.suiveur_1r*) et la TENDANCE DE FOND (yeux.tendance),
    # absents chez HYPERNOVA
    suiv = {"suiveur", "suiveur_unites", "suiveur_depart_pct", "compte", "ouverture_interdite_avant_pause_h",
            "suiveur_1r", "suiveur_1r_unites", "suiveur_1r_agitations", "suiveur_1r_depart_pct"}
    # 20/10 (corrections graves, tests/test_corrections_graves.py) : ordre limite à 1,5 agitation au plus (HYPERNOVA 6)
    # et ordre en attente remplaçable (marche_annule_ordre), MAGNETAR seulement
    corr = {"entree_max_agitation", "marche_annule_ordre"}
    assert {k: v for k, v in vars(o.mains).items() if k not in suiv | corr} == \
        {k: v for k, v in vars(R().mains).items() if k not in corr}
    assert o.mains.entree_max_agitation == 1.5 and R().mains.entree_max_agitation == 6.0
    assert o.mains.marche_annule_ordre is True and getattr(R().mains, "marche_annule_ordre", False) is False
    assert o.mains.suiveur is True and not (suiv & set(vars(R().mains)))
    assert o.mains.compte == "swing" and getattr(R().selection, "mesurer_sorties", False) is False
    assert {k: v for k, v in vars(o.yeux).items() if k != "tendance"} == vars(R().yeux)
    assert o.yeux.tendance is True and getattr(R().yeux, "tendance", False) is False
    # plafond de carte graphique : seulement pour l'arbre de l'or (HYPERNOVA : aucun)
    from collapsar.ecole.precision.coeur import plafond_carte
    assert getattr(R(), "carte_max_go", None) is None and plafond_carte("cuda") is None
    # 19/10 soir : MAGNETAR seule sur la carte (HYPERNOVA finie) : plafond relevé, en laissant >= 1,5 Go à Windows
    assert 0 < o.carte_max_go <= 3.5
    # 19/10 soir : apprentissage apparié, juge sur tous les blocs x 8 parties, note du côté le moins bon (or seulement)
    assert o.ecole.apprentissage_apparie is True and getattr(R().ecole, "apprentissage_apparie", False) is False
    assert o.examen_tournant.note_cotes == "moins_bon" and o.examen_tournant.parties_par_bloc >= 1


def test_lanceur_choisit_les_reglages_de_l_or():
    code = ("import collapsar.ecole.precision.arbre_or as A; from collapsar.ecole.precision import reglages as RG, "
            "donnees as D, jeu as JEU; import json; print(json.dumps([RG.NOM, str(RG.VIE), str(RG.CACHE), "
            "list(D.univers()), JEU.paniers_selection()]))")
    env = {**os.environ, "CUDA_VISIBLE_DEVICES": "-1"}
    env.pop(RG.VARIABLE, None)
    out = subprocess.run([sys.executable, "-c", code], cwd=RACINE, env=env, capture_output=True, text=True, timeout=180)
    assert out.returncode == 0, out.stderr[-2000:]
    nom, vie, cache, univers, paniers = json.loads(out.stdout.strip().splitlines()[-1])
    nom_yaml = re.search(r"^nom:\s*(\S+)", OR.read_text(encoding="utf-8"), re.M).group(1)
    assert nom == nom_yaml
    assert Path(vie) == RACINE / "collapsar" / "vie" / "arbre_or"
    assert Path(cache) == RG.CACHE                                       # yeux partagés (déjà calculés, lus seulement)
    assert univers == ["XAUUSD@M1", "XAUUSD"]
    assert paniers == [["XAUUSD@M1"], ["XAUUSD@M1_MIROIR"]]


# ================================================================================================ graine
def _empreinte(d: Path) -> dict:
    return {str(f.relative_to(d)): (hashlib.sha256(f.read_bytes()).hexdigest(), f.stat().st_mtime_ns)
            for f in sorted(d.rglob("*")) if f.is_file()}


def _arbre_source(d: Path) -> dict:
    """Un petit arbre source : cime B, 2e meilleure C, une branche morte D, la foule greffée."""
    from collapsar.arbre.jardinier import Arbre, Reglages
    from collapsar.ecole.precision import cerveau as C
    (d / "branches").mkdir(parents=True)
    a = Arbre(Reglages(places=3))
    poids = {}
    for i, (nom_t, notes) in enumerate((("x", [0.1, 0.2, 0.0]), ("y", [0.5, 0.6, 0.7]), ("z", [0.3, 0.3, 0.3]),
                                        ("w", [0.9, 0.9, 0.9]))):
        b = a.naitre([], {"nom": nom_t, "vitesse": 1e-4 * (i + 1), "curiosite": 0.002, "alertes": 1})
        for s in notes:
            a.noter(b.nom, s)
        torch.manual_seed(i)
        net = C.Cerveau()
        opt = torch.optim.AdamW(net.parameters(), lr=1e-4)
        torch.save({"cerveau": net.state_dict(), "opt": opt.state_dict(), "temperament": b.temperament},
                   d / "branches" / f"{b.nom}.pt")
        poids[b.nom] = net.state_dict()
    a.mourir("D", "coupée")
    a._elire_cime()
    a.fin_de_battement()
    a.sauver(d / "arbre.json")
    (d / "foule.json").write_text(json.dumps({"version": 1}), encoding="utf-8")
    return poids


def _graine(src: Path):
    return SimpleNamespace(source=str(src), branches=[
        {"nom": "heritiere", "de": "cime"}, {"nom": "curieuse", "de": "cime", "curiosite_x": 2.0},
        {"nom": "seconde", "de": "deuxieme"},
        {"nom": "temoin", "de": "neuve", "temperament": {"nom": "temoin", "vitesse": 3e-4, "curiosite": 0.003,
                                                          "garder": 1.5, "limite": 0.5}}])


def test_graine_copiee_sans_toucher_la_source(tmp_path, monkeypatch):
    from collapsar.ecole.precision import coeur as L
    from collapsar.ecole.precision import graine as GR
    src, dest = tmp_path / "source", tmp_path / "or"
    poids = _arbre_source(src)
    avant = _empreinte(src)
    monkeypatch.setattr(R().arbre, "places", 4)
    g = _graine(src)
    info = GR.copier_source(g, dest, dire=lambda *_: None)
    assert (info["cime"], info["deuxieme"]) == ("B", "C")                  # la morte (D, meilleure note) est ignorée
    assert (dest / "foule.json").exists()                                  # les mêmes yeux que la source
    coeur = L.Coeur(dest, "cpu")
    noms = GR.planter(coeur, g, dire=lambda *_: None)
    assert noms == ["A", "B", "C", "D"] and (dest / "arbre.json").exists()
    t = {n: coeur.branches[n].t for n in noms}
    assert [t[n]["nom"] for n in noms] == ["heritiere", "curieuse", "seconde", "temoin"]
    egal = lambda a, b: all(torch.equal(a[k].cpu(), b[k].cpu()) for k in a)
    assert egal(coeur.branches["A"].net.state_dict(), poids["B"]) and egal(coeur.branches["B"].net.state_dict(), poids["B"])
    assert egal(coeur.branches["C"].net.state_dict(), poids["C"])
    assert not egal(coeur.branches["D"].net.state_dict(), poids["B"])
    assert t["B"]["curiosite"] == pytest.approx(2 * t["A"]["curiosite"])
    assert "alertes" not in t["A"] and "HYPERNOVA" not in t["D"]["heritage"]
    assert _empreinte(src) == avant                                         # RIEN n'a bougé dans l'arbre source
    # une seconde fois : la copie déjà faite est reprise telle quelle
    assert GR.copier_source(g, dest, dire=lambda *_: None)["date"] == info["date"]


def test_graine_attend_la_fin_d_une_generation(tmp_path):
    """Si l'arbre source bat, la copie n'a lieu que juste après une de ses sauvegardes (fenêtre sûre)."""
    from collapsar.ecole.precision import graine as GR
    src = tmp_path / "source"
    _arbre_source(src)
    (src / "coeur.verrou").write_text(str(os.getpid()))                    # « il bat » (ce programme python)
    vieux = time.time() - 600
    os.utime(src / "arbre.json", (vieux, vieux))
    with pytest.raises(RuntimeError):
        GR.copier_source(_graine(src), tmp_path / "or1", dire=lambda *_: None, attente_max_s=2)
    recent = time.time() - 10                                              # une génération vient de finir
    os.utime(src / "arbre.json", (recent, recent))
    info = GR.copier_source(_graine(src), tmp_path / "or2", dire=lambda *_: None, attente_max_s=5)
    assert info["source_battait"] is True


# ================================================================================================ verrous / gardien
def test_verrous_independants(tmp_path):
    from collapsar.ecole.precision.coeur import verrou
    p = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    try:
        (tmp_path / "hypernova").mkdir()
        (tmp_path / "hypernova" / "coeur.verrou").write_text(str(p.pid))   # HYPERNOVA bat
        with pytest.raises(SystemExit):
            verrou(tmp_path / "hypernova")
        f = verrou(tmp_path / "arbre_or")                                  # l'arbre de l'or a le sien : libre
        assert f.read_text() == str(os.getpid())
        assert (tmp_path / "hypernova" / "coeur.verrou").read_text() == str(p.pid)
    finally:
        p.kill()


def test_le_gardien_ne_confond_pas_les_deux_coeurs():
    g = (RACINE / "collapsar" / "surveillance" / "gardien.ps1").read_text(encoding="utf-8-sig")
    motif_h = re.search(r"CommandLine -match '(collapsar\\\.ecole\\\.precision\\\.coeur)'", g).group(1)
    motif_o = re.search(r"CommandLine -match '(collapsar\\\.ecole\\\.precision\\\.arbre_or)'", g).group(1)
    py = r"C:\x\venv_gpu\Scripts\python.exe -u -m "
    hyper, orr = py + "collapsar.ecole.precision.coeur --generations 1000", py + "collapsar.ecole.precision.arbre_or --generations 1000"
    assert re.search(motif_h, hyper) and not re.search(motif_h, orr)
    assert re.search(motif_o, orr) and not re.search(motif_o, hyper)
    assert "Join-Path $vie 'arbre_or'" in g and "Join-Path $orDos 'EN_COURS'" in g and "Join-Path $orDos 'ARRET'" in g


# ================================================================================================ mondes / examen
def test_monde_de_l_or_dans_les_deux_sens(monkeypatch):
    from collapsar.ecole.precision import coeur as L
    vu = {}
    monkeypatch.setattr(L, "Univers", lambda v, de, jusqua, dev: vu.setdefault("v", v))
    monkeypatch.setattr(R().ecole, "reel_et_miroir", True, raising=False)
    monkeypatch.setattr(R().ecole, "marches_min_monde", 1, raising=False)
    v = L.monde_apprentissage(np.random.default_rng(0), "cpu", {"XAUUSD": pd.Timestamp("2004-06-11")})
    assert sorted(v) == [("XAUUSD", False), ("XAUUSD", True)]


def test_mouvement_parcouru_a_la_main():
    from collapsar.ecole.precision.jeu import mouvement_parcouru
    # 3 journées de 4 bougies ; clôtures de fin de journée : 103, 99, 104
    c = np.array([100, 101, 102, 103, 102, 100, 99, 99, 100, 102, 103, 104], float)[:, None]
    U = SimpleNamespace(c=c, jour=np.repeat([0, 1, 2], 4))
    # du départ (100) à la fin (104) : |103-100| + |99-103| + |104-99| = 12
    assert mouvement_parcouru(U, np.array([[0]]), np.array([0]), np.array([11]))[0] == pytest.approx(12.0)
    # dans une seule journée : le seul écart départ -> fin
    assert mouvement_parcouru(U, np.array([[0]]), np.array([4]), np.array([6]))[0] == pytest.approx(3.0)
    assert mouvement_parcouru(U, np.array([[-1]]), np.array([0]), np.array([11]))[0] == 0.0


def test_examen_mesure_le_mouvement_seulement_si_demande(monde_invente, monkeypatch):
    from collapsar.ecole.precision import cerveau as C
    from collapsar.ecole.precision import jeu as JEU
    from collapsar.ecole.precision.univers import Univers
    U = Univers([("EURUSD", False)], pd.Timestamp("2019-06-01"), pd.Timestamp("2019-08-15"), "cpu")
    monkeypatch.setattr(R().monde, "challenge_jours", 10)
    torch.manual_seed(0)
    net = C.Cerveau()
    ex = JEU.Examen(U, [["EURUSD"]], pd.Timestamp("2019-06-01"), pd.Timestamp("2019-08-15"), 10)
    x0 = ex.jouer_un(net, 1)
    assert "part_mouvement_pct" not in x0                                   # HYPERNOVA : rien ne change
    monkeypatch.setattr(R().selection, "mesurer_mouvement", True, raising=False)
    ex2 = JEU.Examen(U, [["EURUSD"]], pd.Timestamp("2019-06-01"), pd.Timestamp("2019-08-15"), 10)
    x = ex2.jouer_un(net, 1)
    assert x["note"] == pytest.approx(x0["note"]) and x["gain_pct_mois"] == pytest.approx(x0["gain_pct_mois"])
    for k in ("part_mouvement_pct", "trades_5r_pct", "trades_10r_pct"):
        assert k in x and k in x["jumeau"]
    assert -100 <= x["part_mouvement_pct"] <= 100 and np.isfinite(x["part_mouvement_pct"])
    assert "part_mouvement_pct" in next(iter(x["par_panier"].values()))
