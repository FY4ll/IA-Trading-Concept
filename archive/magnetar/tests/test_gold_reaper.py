"""Tests de la branche GOLD REAPER de MAGNETAR (20/10/2026, ecole/precision/gold_reaper.py) :
- ses trades d'après la coupure (mois cachés) ne sont JAMAIS gardés ; ses morceaux qui se chevauchent = une position,
  sortie au moment où la moitié du volume est fermée ;
- son calendrier tombe sur les bords de 15 min (ordre décidé à la clôture d'avant, exécuté à l'ouverture) ;
- le professeur s'exprime avec les gestes des mains : choix possibles, ouverture au bon regard, fermeture au regard de
  sa sortie, stop près de 0,6 agitation sans dépasser le plafond, sens retourné sur le marché retourné ;
- la fidélité du rejeu se calcule ; l'imitation fait baisser la perte ; la laisse se relâche et apprend ;
- la greffe sur un petit arbre arrêté, une génération marquée [GOLD REAPER ... contrôle 2024-2025 non valable], les
  deux retours arrière ; aucune autre branche n'est touchée par le code.
Depuis Test_IA : $env:CUDA_VISIBLE_DEVICES='-1'; venv_gpu\\Scripts\\python.exe -m pytest collapsar/tests/test_gold_reaper.py -q
"""
from __future__ import annotations

import json
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest
import torch

from collapsar.ecole.precision import cerveau as C
from collapsar.ecole.precision import gold_reaper as GR
from collapsar.ecole.precision.reglages import R

from test_ecole_precision import chemin_minutes, monde_invente, petite_ecole  # noqa: F401  (fixtures partagées)
from test_mentor import mains_du_mentor  # noqa: F401

DE, JUSQUA = pd.Timestamp("2019-03-01"), pd.Timestamp("2019-07-20")


def trades_inventes(n: int = 40, graine: int = 4) -> pd.DataFrame:
    """Des « trades de Gold Reaper » inventés sur le marché inventé (prix pris dans ses minutes), parfois en morceaux."""
    m = chemin_minutes(220, 11, depart="2019-01-07")
    rng = np.random.default_rng(graine)
    tm = m.time.values
    ok = np.flatnonzero((tm >= np.datetime64("2019-03-12")) & (tm < np.datetime64("2019-07-10"))
                        & (pd.DatetimeIndex(tm).hour >= 8) & (pd.DatetimeIndex(tm).hour < 17))
    debuts = np.sort(rng.choice(ok, n, replace=False))
    lignes = []
    fin_prec = -1
    for i in debuts:
        if i <= fin_prec + 60:
            continue
        dur = int(rng.integers(20, 240))
        j = min(i + dur, len(m) - 1)
        s = int(rng.choice([-1, 1]))
        for k in range(int(rng.integers(1, 4))):
            jj = min(j + 7 * k, len(m) - 1)
            lignes.append({"to": pd.Timestamp(tm[i]), "tc": pd.Timestamp(tm[jj]), "s": s, "vol": 0.01 * (1 + k),
                           "p_open": float(m.close.iloc[i]), "p_close": float(m.close.iloc[jj]), "solde": 1000.0})
        fin_prec = j + 14
    t = pd.DataFrame(lignes).sort_values(["to", "tc"]).reset_index(drop=True)
    t["oz"] = t.vol * 100
    t["move"] = (t.p_close - t.p_open) * t.s
    return t


def _net(tendance=False):
    torch.manual_seed(0)
    t = {"symetrique": {"version": 1}, "precision": {"stop_max_agitation": GR.PLAFOND_STOP_A}}
    return C.regler_symetrie(C.regler_precision(C.Cerveau(tendance=tendance), t), t)


# ================================================================================================ ses trades
def test_coupure_et_positions(tmp_path):
    f = tmp_path / "gr.csv"
    lignes = ["Time;Type;Volume;Symbol;Price;Volume;Time;Price;Commission;Swap;Profit",
              "2025.09.30 10:00:00;Buy;0.02;XAUUSD;3800;0.02;2025.10.01 10:00:00;3810;-0.1;;20",     # ferme après : jeté
              "2025.10.02 10:00:00;Sell;0.02;XAUUSD;3800;0.02;2025.10.02 11:00:00;3790;-0.1;;20",    # mois caché : jeté
              "2025.03.03 10:00:00;Buy;0.01;XAUUSD;2900;0.01;2025.03.03 10:30:00;2905;-0.1;;5",
              "2025.03.03 10:00:05;Buy;0.03;XAUUSD;2900;0.03;2025.03.03 11:30:00;2910;-0.1;;30",
              "2025.03.03 10:20:00;Buy;0.01;XAUUSD;2902;0.01;2025.03.03 12:00:00;2908;-0.1;;6",
              "2025.03.04 10:00:00;Sell;0.02;XAUUSD;2950;0.02;2025.03.04 10:40:00;2940;-0.1;;20",
              "2025.01.01 00:00:00;Balance;;;;;;;;;1000"]
    f.write_text("\n".join(lignes), encoding="utf-8")
    t, bal = GR.charger_trades(f)
    assert len(t) == 4 and t.tc.max() < GR.COUPURE and t.to.max() < GR.COUPURE
    p = GR.positions(t)
    assert len(p) == 2                                           # 3 morceaux qui se chevauchent = 1 position
    a = p.iloc[0]
    assert a.sens == 1 and a.morceaux == 3 and a.lots == pytest.approx(0.05)
    assert a.t_ferm == pd.Timestamp("2025-03-03 11:30:00")       # la moitié du volume (0,03 sur 0,05) fermée à 11h30
    assert a.t_ferm_max == pd.Timestamp("2025-03-03 12:00:00")
    assert p.iloc[1].sens == -1 and a.move_ftmo < a.move_brut + GR.ECART_COURTIER


def test_bords_et_calendrier(monde_invente):
    s = pd.Series(pd.to_datetime(["2019-03-04 10:00:00", "2019-03-04 10:00:21", "2019-03-04 10:08:00",
                                  "2019-03-04 10:22:30"]))
    b = pd.to_datetime(GR.bord(s))                                # jamais AVANT sa décision
    assert list(b) == list(pd.to_datetime(["2019-03-04 10:00", "2019-03-04 10:15", "2019-03-04 10:15",
                                           "2019-03-04 10:30"]))
    p = GR.positions(trades_inventes())
    U = GR.univers(p, "cpu", "EURUSD", DE, JUSQUA)
    cal = GR.calendrier(U, p)
    tn = np.asarray(U.t_ns)
    ok = cal["couverte"]
    assert ok.sum() >= 10
    be = GR.bord(p.t_ouv)[ok]
    assert (tn[cal["te"][ok] + 1] >= be).all() and (tn[cal["te"][ok]] < be).all()      # exécuté à l'ouverture du bord
    assert (cal["tx"][ok] > cal["te"][ok]).all()


# ================================================================================================ le professeur
def test_professeur_rejeu_gestes_possibles(mains_du_mentor):
    p = GR.positions(trades_inventes())
    U = GR.univers(p, "cpu", "EURUSD", DE, JUSQUA)
    cal = GR.calendrier(U, p)
    ri = GR.risques(p)
    net = _net()
    rej = GR.rejouer(U, net, p, cal, ri, B=4, dire=lambda *_: None)
    st, m = rej["stats"], rej["memoire"]
    assert st["lp_min"] > -1e3                                   # aucun choix interdit par les masques des mains
    assert st["ouvertures"] > 10 and st["fermer"] > 5
    role, ch = m["role"], m["choix"]
    ouv = role == 1
    g = ch["geste"][:, 0]
    assert bool(((g == C.ACHAT_M) | (g == C.VENTE_M))[ouv].all()) and bool((g[role == 2] == C.FERMER).all())
    assert bool((g[(role == 0) | (role == 3)] == C.GARDER).all())
    # au bon regard : ouverture à te (au plus 1 bougie de retard), fermeture au regard de sa sortie
    gid, t = m["gid"].numpy(), m["t"].numpy()
    o = ouv.numpy()
    assert ((t[o] - cal["te"][gid[o]] >= 0) & (t[o] - cal["te"][gid[o]] <= GR.RETARD_MAX)).all()
    f = (role == 2).numpy()
    assert (t[f] >= cal["tx"][gid[f]]).all() and (t[f] - cal["tx"][gid[f]] <= 1).all()
    # sens retourné sur le marché retourné
    mir = m["miroir"].numpy()
    achat = (g == C.ACHAT_M).numpy()
    sens = cal["sens"][gid[o]]
    assert ((achat[o] == (sens > 0)) == ~mir[o]).all()
    # stops : distance près de la cible, jamais au-delà du plafond
    tr = [x for x in rej["trades"] if x.get("fin") in ("main", "stop")]
    d = np.array([abs(x["entree"] - x["stop"]) / x["A"] for x in tr])
    assert len(d) > 5 and (d <= GR.PLAFOND_STOP_A + 0.05).all() and np.median(np.abs(d - GR.STOP_CIBLE_A)) < 0.2
    fi = GR.fidelite(rej, p, cal, ri)
    assert fi["rejouees"] > 5 and np.isfinite(fi["lien"]) and "somme_pct_lui" in fi
    # les gestes d'un regard ne changent pas avec les poids (les mêmes leçons pour n'importe quel cerveau de cette forme)
    net2 = _net()
    with torch.no_grad():
        for q in net2.parameters():
            q.add_(0.1)
    rej2 = GR.rejouer(U, net2, p, cal, ri, B=4, dire=lambda *_: None)
    assert torch.equal(rej2["memoire"]["choix"]["geste"], ch["geste"]) and torch.equal(rej2["memoire"]["t"], m["t"])


def test_imitation_et_laisse(mains_du_mentor, tmp_path):
    p = GR.positions(trades_inventes())
    U = GR.univers(p, "cpu", "EURUSD", DE, JUSQUA)
    cal = GR.calendrier(U, p)
    ri = GR.risques(p)
    net = _net()
    rej = GR.rejouer(U, net, p, cal, ri, B=4, dire=lambda *_: None)
    m = rej["memoire"]
    ts, ta = GR.jours_de_test(p, U.de, U.jusqua)
    m["test"] = GR.etiqueter(m, U, p, ts, ta)
    assert 0 < int(m["test"].sum()) < len(m["test"])
    tb = GR._vue(U)
    idx = torch.nonzero(~m["test"]).squeeze(1)
    a0 = GR.accord(net, tb, m, idx)
    im = GR.imiter(net, tb, m, ~m["test"], m["test"], epoques=2, paquet=512, vitesse=1e-3, dire=lambda *_: None)
    assert im["apres_appris"]["perte_par_regard"] < a0["perte_par_regard"] - 0.5
    assert im["epoques"][-1]["choix_impossibles"] == 0
    # la laisse : relâchée de 0,8 par génération ; apprend sur les leçons écrites
    t = {"maitre": {"nee_a": 10, "laisse_depart": 1.0, "relache": 0.8}}
    assert GR.laisse(t, 10) == 1.0 and GR.laisse(t, 12) == pytest.approx(0.64) and GR.laisse({}, 3) == 0.0
    f = tmp_path / GR.LECONS
    meta = {"variantes": [list(v) for v in U.variantes], "de": str(U.de), "jusqua": str(U.jusqua), "T": int(U.T),
            "t0": int(U.t_ns[0]), "t1": int(U.t_ns[-1])}
    torch.save({"memoire": m, "meta": meta}, f)
    from collapsar.ecole.precision import jeu as JEU
    from collapsar.ecole.precision.univers import Univers
    U2 = Univers([("EURUSD", False)], pd.Timestamp("2019-03-01"), pd.Timestamp("2019-06-01"), "cpu")
    lecon = JEU.Lecon(U2, 16, np.random.default_rng(0))
    m2, _ = lecon.jouer(net, 48)
    tt = {"maitre": {"nee_a": 5, "laisse_depart": 1.0, "relache": 0.8, "lecons": str(f)}, "curiosite": 0.003}
    br = SimpleNamespace(net=net, opt=torch.optim.AdamW(net.parameters(), lr=3e-4), t=tt)
    avant = [q.detach().clone() for q in net.parameters()]
    e = SimpleNamespace(epoques=1, paquet=256, coupe=0.2, curiosite=0.003)
    a = GR.apprendre_en_laisse(br, lecon.table, m2, 6, e)
    assert a["laisse"] == pytest.approx(0.8) and np.isfinite(a["perte_mentor"]) and a["perte_mentor"] > 0
    assert 0 <= a["accord_geste_pct"] <= 100
    assert any(not torch.equal(x, q) for x, q in zip(avant, net.parameters()))
    GR._ECOLE.clear()


# ================================================================================================ la greffe
def test_greffe_generation_et_retours(petite_ecole, mains_du_mentor, monkeypatch, capsys):
    from collapsar.arbre.jardinier import Arbre
    L, d = petite_ecole
    monkeypatch.setattr(R().arbre, "places", 3)
    base = ["--dossier", str(d), "--appareil", "cpu", "--muet"]
    L.main(["--generations", "3"] + base)
    (d / "ARRET").write_text("")
    a = Arbre.charger(d / "arbre.json")
    cime = a.cime
    vivantes = sorted(b.nom for b in a.vivantes())
    sortie = d / GR.SOUS_DOSSIER
    r = GR.preparer(d, sortie, "cpu", B=4, epoques=1, trades=trades_inventes(), marche="EURUSD", de=DE, jusqua=JUSQUA,
                    dire=lambda *_: None)
    assert r["fidelite"]["rejouees"] > 5 and (sortie / GR.LECONS).exists() and (sortie / "branche.pt").exists()
    info = GR.appliquer(d, sortie / "branche.pt", None, dire=lambda *_: None)
    a2 = Arbre.charger(d / "arbre.json")
    nouv, faible = info["branche"], info["remplacee"]
    assert faible != cime and a2.branches[faible].morte is not None and (d / "archives" / f"{faible}.pt").exists()
    assert a2.branches[nouv].parents == [cime] and GR.est_gold_reaper(a2.branches[nouv].temperament)
    tn = a2.branches[nouv].temperament
    assert tn["maitre"]["nee_a"] == 3 and tn["symetrique"] and tn["precision"]["stop_max_agitation"] == GR.PLAFOND_STOP_A
    assert "NON VALABLE" in tn["maitre"]["controle_2024_2025"] and tn["jeunesse"] == GR.JEUNESSE
    assert (d / GR.FICHIER).exists() and any((d / "sauvegardes").glob("avant_gold_reaper_*"))
    with pytest.raises(SystemExit):
        GR.appliquer(d, sortie / "branche.pt", None, dire=lambda *_: None)          # une seule fois
    (d / "ARRET").unlink()
    capsys.readouterr()
    L.main(["--generations", "4"] + base)
    txt = capsys.readouterr().out
    assert f"{nouv} [SYMÉTRIQUE] [GOLD REAPER laisse 0.80" in txt and "contrôle 2024-2025 non valable" in txt
    lignes = [json.loads(x) for x in (d / "journal_croissance.jsonl").read_text(encoding="utf-8").splitlines()]
    g4 = [x for x in lignes if x.get("quoi") == "generation"][-1]
    assert g4["branches"][nouv]["laisse"]["laisse"] == pytest.approx(0.8)
    assert g4["branches"][nouv]["laisse"]["controle_2024_2025"] == "non valable"
    # retour léger puis complet
    GR.retirer(d, lambda *_: None)
    a3 = Arbre.charger(d / "arbre.json")
    assert a3.branches[nouv].morte is not None and not (d / GR.FICHIER).exists()
    (d / GR.FICHIER).write_text(json.dumps(info), encoding="utf-8")
    GR.defaire(d, lambda *_: None)
    a4 = Arbre.charger(d / "arbre.json")
    assert sorted(b.nom for b in a4.vivantes()) == vivantes and a4.battements == 3
    assert (d / "branches" / f"{faible}.pt").exists() and not (d / "archives" / f"{faible}.pt").exists()
    GR._ECOLE.clear()
