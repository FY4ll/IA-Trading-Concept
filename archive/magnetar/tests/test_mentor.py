"""Tests du MENTOR de MAGNETAR et de son APPRENTIE (19/10/2026, ecole/precision/mentor.py) :
- le mentor s'exprime avec les gestes des mains : ses numéros redonnent EXACTEMENT ses niveaux dans cerveau.politique
  (entrée, stop, risque, validité, suiveur 4 h après +1R, délai), et ces choix sont possibles pour ses mains ;
- ses règles figées : décision seulement quand une bougie de 4 h s'est terminée, sens = les trois tendances d'accord,
  ordre limite au bord proche d'une zone 4 h / 1 h touchée puis réagie, stop <= 0,4 agitation, 0,5 %, laisser courir,
  revenir à la clôture de 4 h ; son jumeau tire le sens à pile ou face ;
- les regards plus espacés (+ 8 h, 1 jour) ne changent rien aux autres cerveaux (mêmes poids, même forme) ;
- l'imitation fait baisser la perte ; la récompense en laisse apprend ; la laisse se relâche ;
- la greffe sur un petit arbre arrêté (sauvegarde, branche née de la mère, la plus faible archivée), une génération avec
  la branche marquée [APPRENTIE], puis les deux retours arrière.
Depuis Test_IA : $env:CUDA_VISIBLE_DEVICES='-1'; venv_gpu\\Scripts\\python.exe -m pytest collapsar/tests/test_mentor.py -q
"""
from __future__ import annotations

import json
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest
import torch

from collapsar.ecole.precision import cerveau as C
from collapsar.ecole.precision import mentor as MT
from collapsar.ecole.precision import tendance as TD
from collapsar.ecole.precision.reglages import R, UNITES

from test_ecole_precision import monde_invente, petite_ecole  # noqa: F401  (fixtures partagées)


@pytest.fixture
def mains_du_mentor(monde_invente, monkeypatch):
    """Le stop suiveur, le suiveur après +1R et la tendance de fond allumés (comme MAGNETAR), sur le marché inventé."""
    for k, v in (("suiveur", True), ("suiveur_unites", ["D1", "H4", "H1", "M15"]), ("suiveur_depart_pct", 10.0),
                 ("suiveur_1r", True), ("suiveur_1r_unites", ["H1", "H4"]), ("suiveur_1r_agitations", [1.0])):
        monkeypatch.setattr(R().mains, k, v, raising=False)
    monkeypatch.setattr(R().yeux, "tendance", True, raising=False)
    x = monde_invente
    J = TD.jours_ohlc(x["t15"], x["h"], x["l"], x["c"])
    monkeypatch.setattr(TD, "_jours", lambda nom: J)
    return x


def _univers():
    from collapsar.ecole.precision.univers import Univers
    return Univers([("EURUSD", False)], pd.Timestamp("2019-05-15"), pd.Timestamp("2019-08-10"), "cpu")


def _mains():
    """Un cerveau quelconque de la forme de l'apprentie (stops <= 0,4 agitation) : sert à relire les numéros."""
    torch.manual_seed(0)
    net = C.Cerveau(tendance=True, suiveur_1r=True)
    return C.regler_precision(net, {"precision": {"stop_max_agitation": 0.4}})


def _partie(U, B=48, bougies=900, graine=0, jumeau=False, avec=None):
    """Le mentor tient B comptes ; `avec(tb, qui, choix, lv, s, t, pos, d)` est appelé à chaque regard."""
    from collapsar.ecole.precision import jeu as JEU
    tb = JEU.Table(U, B, 1)
    rng = np.random.default_rng(graine)
    tb.demarrer(np.ones(B, bool), np.zeros((B, 1), np.int64), rng.integers(U.premier[0], U.T - bougies - 300, B))
    c = tb.cpt
    torch.manual_seed(graine)
    n_ouv = 0
    for _ in range(bougies):
        qui = np.flatnonzero(c.actif & ((c.t >= tb.prochain) | tb.reveil))
        if len(qui):
            t, cols, fc, pos = tb.entrees(qui)
            s = tb.vue.structure(t, cols)
            d = torch.as_tensor(c.t[qui] - tb.dernier[qui])
            jum = torch.ones(len(qui), dtype=torch.bool) if jumeau else None
            choix, lv = MT.decider(U, s, t, pos, d, jum)
            if avec is not None:
                avec(tb, qui, choix, lv, s, t, pos, d, fc)
            g = JEU.niveaux_np(JEU.paquet_niveaux(lv))
            n_ouv += int(g["ouvre"].sum())
            tb.appliquer(qui, g)
        tb.avancer()
        c.actif &= ~(c.mort | c.reussi)
    return tb, n_ouv


def test_numeros_du_mentor(mains_du_mentor):
    ix = MT.numeros()
    r = R().mains
    assert r.risques_pct[ix["risque"]] == 0.5 and r.parts_tp1[ix["part"]] == 0.0 and r.marges_stop[ix["marge"]] == 0.05
    assert r.validites_ordre[ix["validite"]] == 16
    from collapsar.ecole.precision import suiveur as SV
    u, ag, nom = SV.options_1r()[ix["suiveur"] - SV.n_options()]
    assert SV.unites()[u] == "H4" and ag == 0 and "4 h" in nom
    K, NU = R().yeux.zones_par_cote, len(UNITES)
    assert ix["courir"] == NU * K + NU * 2


def test_niveaux_identiques_aux_mains_et_choix_possibles(mains_du_mentor):
    """Mêmes numéros -> mêmes niveaux dans cerveau.politique ; ses choix sont permis par les masques de ses mains."""
    from collapsar.ecole.precision import jeu as JEU
    U = _univers()
    net = _mains()
    vu = {"ouv": 0, "ecart": 0.0, "lp_min": 0.0}

    def comparer(tb, qui, choix, lv, s, t, pos, d, fc):
        o = lv["ouvre"]
        if not bool(o.any()):
            return
        car, pos2, _ = JEU.yeux_complets(tb, s, t, pos, torch.as_tensor(qui), net)
        out = C.politique(net, s, torch.cat([car, pos2], -1), fc, pos2, choix)
        lv2 = out[5]
        for k in ("entree", "stop", "rd", "sig", "risque_pct", "validite", "part", "suiveur_u", "suiveur_tp1",
                  "suiveur_marge", "suiveur_1r", "suiveur_ag"):
            vu["ecart"] = max(vu["ecart"], float((lv[k][o].float() - lv2[k][o].float()).abs().max()))
        assert torch.isnan(lv2["dest"][o]).all() and torch.isnan(lv2["tp1"][o]).all()
        assert torch.equal(lv["delai"], lv2["delai"]) and torch.equal(lv["ouvre"], lv2["ouvre"])
        assert torch.equal(lv["limite"], lv2["limite"]) and torch.equal(lv["ferme"], lv2["ferme"])
        vu["lp_min"] = min(vu["lp_min"], float(out[1].min()))
        vu["ouv"] += int(o.sum())
    _partie(U, avec=comparer)
    assert vu["ouv"] > 10
    assert vu["ecart"] < 1e-5
    assert vu["lp_min"] > MT.PLANCHER_LP                     # aucun choix impossible pour ses mains


def test_regles_figees(mains_du_mentor):
    U = _univers()
    iu4 = UNITES.index("H4")
    vu = {"ouv": 0, "hors_moment": 0, "contre_tendance": 0, "regards": 0}

    def verifier(tb, qui, choix, lv, s, t, pos, d, fc):
        n = len(qui)
        cc = s["cc"]
        tt = t[:, None]
        moment = (d <= 0)[:, None] | (U.tLIGNES[tt, cc, iu4] != U.tLIGNES[(t - d.clamp(min=0)).clamp(min=0)[:, None], cc, iu4])
        agit = choix["geste"] != C.GARDER
        vu["hors_moment"] += int((agit & ~moment).sum())
        o = lv["ouvre"]
        sg = U.tTEND[tt, cc][..., :3]
        accord = (sg[..., 0] == sg[..., 1]) & (sg[..., 1] == sg[..., 2]) & (sg[..., 0] != 0)
        vu["contre_tendance"] += int((o & ~(accord & (lv["sig"] == sg[..., 0]))).sum())
        if o.any():
            A = s["A"][o]
            dist = lv["sig"][o] * (lv["entree"][o] - lv["stop"][o])
            assert bool((dist <= 0.4 * A + 1e-6).all()) and bool((dist > 0).all())
            assert bool((lv["risque_pct"][o] == 0.5).all()) and bool((lv["part"][o] == 0).all())
            assert bool(torch.isnan(lv["dest"][o]).all()) and bool(lv["limite"][o].all())
            assert bool((lv["suiveur_1r"][o] == 1).all())
            p = s["p"][o]
            assert bool((lv["sig"][o] * (p - lv["entree"][o]) > 0).all())          # ordre limite du bon côté
        # revenir à la prochaine clôture de 4 h
        fin = torch.as_tensor(np.asarray(U.t_ns)[t.numpy()] + MT.QUART_NS)
        reste = 16 - (fin % MT.QUATRE_H_NS) // MT.QUART_NS
        assert bool((lv["delai"] <= reste).all()) and bool((lv["delai"] >= 1).all())
        assert bool(((reste < 16) | (lv["delai"] == 16)).all())
        vu["ouv"] += int(o.sum())
        vu["regards"] += n
    tb, n = _partie(U, avec=verifier)
    assert vu["ouv"] > 10 and vu["hors_moment"] == 0 and vu["contre_tendance"] == 0
    # positions jamais fermées à la main (aucun geste « fermer » sur une position)
    assert vu["regards"] > vu["ouv"]


def test_zones_touchees_et_reagies(mains_du_mentor):
    """Version 1 : seulement des zones touchées puis réagies ; « zone vierge acceptée » (v2) en ouvre au moins autant."""
    U = _univers()
    vu = {"v1": 0, "v2": 0, "pas_reagie": 0}

    def verifier(tb, qui, choix, lv, s, t, pos, d, fc):
        o = lv["ouvre"]
        e1, place, _, _ = MT.zones_valables(s, "v1")
        e2, _, _, _ = MT.zones_valables(s, "v2")
        vu["v1"] += int(e1.sum())
        vu["v2"] += int(e2.sum())
        assert bool((e2 | ~e1).all())                                   # v1 valable => v2 valable
        if o.any():
            K = R().yeux.zones_par_cote
            c = (lv["sig"] < 0).long()
            pl = choix["entree"]
            iu, k = pl // K, pl % K
            b, j = torch.nonzero(o, as_tuple=True)
            vu["pas_reagie"] += int((~(s["tou"][b, j, iu[b, j], c[b, j], k[b, j]]
                                       & s["rea"][b, j, iu[b, j], c[b, j], k[b, j]])).sum())
            assert bool(torch.isin(iu[o], torch.tensor([UNITES.index("H4"), UNITES.index("H1")])).all())
    _partie(U, avec=verifier)
    assert vu["v1"] > 0 and vu["v2"] >= vu["v1"] and vu["pas_reagie"] == 0


def test_jumeau_tire_le_sens(mains_du_mentor):
    """Son jumeau : mêmes moments, sens à pile ou face (environ moitié des ouvertures contre le sens du mentor)."""
    U = _univers()
    vu = {"ouv": 0, "contre": 0, "deux_cotes": 0, "sans_zone": 0}

    def compter(tb, qui, choix, lv, s, t, pos, d, fc):
        o = lv["ouvre"]
        sg = U.tTEND[t[:, None], s["cc"]][..., 0]
        ex, _, _, _ = MT.zones_valables(s)
        cm = (sg < 0).long()
        autre = ex.gather(2, (1 - cm)[..., None]).squeeze(2)
        cote = (lv["sig"] < 0).long()
        vu["sans_zone"] += int((o & ~ex.gather(2, cote[..., None]).squeeze(2)).sum())     # jamais sans zone
        vu["ouv"] += int(o.sum())
        vu["contre"] += int((o & (lv["sig"] != sg)).sum())
        # son jumeau aurait pu ouvrir des deux côtés : pile ou face
        m_ouvrirait = choix["geste"] != C.GARDER
        vu["deux_cotes"] += int((m_ouvrirait & (choix["geste"] != C.FERMER) & autre & ex.gather(2, cm[..., None]).squeeze(2)).sum())
    _partie(U, jumeau=True, avec=compter, bougies=1500)
    assert vu["ouv"] > 20 and vu["sans_zone"] == 0
    if vu["deux_cotes"] >= 30:
        assert 0.25 < vu["contre"] / vu["deux_cotes"] < 0.75
    else:
        assert vu["contre"] <= vu["deux_cotes"]
    # pile ou face, vérifié directement : les mêmes regards, jumeau ou non, et une graine qui change
    tb, _ = _partie(U, B=8, bougies=50)
    qui = np.flatnonzero(tb.cpt.actif)
    t, cols, fc, pos = tb.entrees(qui)
    s = tb.vue.structure(t, cols)
    s2 = dict(s)
    ex = torch.ones(len(qui), 1, 2, dtype=torch.bool)
    pl = torch.zeros(len(qui), 1, 2, dtype=torch.long)
    p = s["p"]
    ent = torch.stack([p - 0.1 * s["A"], p + 0.1 * s["A"]], -1)
    loin = torch.stack([p - 0.3 * s["A"], p + 0.3 * s["A"]], -1)
    ancien = MT.zones_valables
    MT.zones_valables = lambda s_, v="v1": (ex, pl, ent, loin)
    try:
        sg = U.tTEND[t[:, None], s["cc"]][..., :3].clone()
        U.tTEND[t[:, None], s["cc"], 0:3] = 1.0                                 # tendance d'accord : achat
        d = torch.zeros(len(qui), dtype=torch.long)
        pos0 = torch.zeros_like(pos)
        _, lv_m = MT.decider(U, s2, t, pos0, d, None)
        assert bool(lv_m["ouvre"].all()) and bool((lv_m["sig"] == 1).all())
        signes = []
        for k in range(40):
            torch.manual_seed(k)
            _, lv_j = MT.decider(U, s2, t, pos0, d, torch.ones(len(qui), dtype=torch.bool))
            assert bool(lv_j["ouvre"].all())
            signes.append(lv_j["sig"])
        part = float((torch.stack(signes) < 0).float().mean())
        assert 0.35 < part < 0.65
    finally:
        MT.zones_valables = ancien
        U.tTEND[t[:, None], s["cc"], 0:3] = sg


def test_d_depuis_compte():
    fc = torch.zeros(5, C.N_COMPTE)
    fc[:, 8] = torch.tensor([0.0, 1 / 16, 1.0, 3.9375, 4.0])
    assert MT.d_depuis_compte(fc).tolist() == [0, 1, 16, 63, 64]


# ================================================================================================ regards plus espacés
def test_regards_longs_ne_changent_pas_les_autres_cerveaux():
    torch.manual_seed(1)
    a = C.Cerveau()
    torch.manual_seed(1)
    b = C.Cerveau(delais=tuple(R().mains.delais_regard))                    # la liste des réglages = comme avant
    assert a.delais_regard is None and b.delais_regard is None
    sa, sb = a.state_dict(), b.state_dict()
    assert list(sa) == list(sb) and all(torch.equal(sa[k], sb[k]) for k in sa)
    assert "delais" not in C.forme(sa) and "delais_t" not in sa
    long = C.Cerveau(delais=C.REGARDS_LONGS[7])
    assert long.delai.out_features == 7 and C.forme(long.state_dict())["delais"] == C.REGARDS_LONGS[7]
    assert "delais_t" not in long.state_dict()
    assert C.cerveau_pour(long.state_dict()).delais_regard == C.REGARDS_LONGS[7]
    with pytest.raises(ValueError):
        C.Cerveau(delais=(1, 2, 3))
    # adapter : 5 -> 7 (délais en plus gardés tels quels) et 7 -> 5 (retirés)
    x = C.adapter(sa, long)
    assert x["delai.weight"].shape[0] == 7 and torch.equal(x["delai.weight"][:5], sa["delai.weight"])
    long.load_state_dict(x)
    y = C.adapter(long.state_dict(), a)
    assert y["delai.weight"].shape[0] == 5
    a.load_state_dict(y)


def test_regards_longs_dans_la_politique(monde_invente):
    """Le délai 6 de l'apprentie = 96 bougies (1 jour) ; les 5 premiers = ceux des réglages."""
    from collapsar.ecole.precision import jeu as JEU
    from collapsar.ecole.precision.univers import Univers
    U = Univers([("EURUSD", False)], pd.Timestamp("2019-03-01"), pd.Timestamp("2019-06-01"), "cpu")
    net = C.Cerveau(delais=C.REGARDS_LONGS[7])
    with torch.no_grad():
        net.delai.bias[:] = -10.0
        net.delai.bias[6] = 10.0
    tb = JEU.Table(U, 16, 1)
    tb.demarrer(np.ones(16, bool), np.zeros((16, 1), np.int64), np.full(16, U.premier[0] + 100))
    (choix, *_, lv), _ = tb.regarder(net, np.arange(16))
    assert bool((choix["delai"] == 6).all()) and bool((lv["delai"] == 96).all())
    tb.appliquer(np.arange(16), lv)
    assert bool((tb.prochain - tb.cpt.t == 96).all())


# ================================================================================================ l'apprentie
def _apprentie():
    torch.manual_seed(3)
    mere = C.Cerveau(journal=True)
    t = MT.temperament_apprentie({"nom": "symetrique", "vitesse": 3e-4, "curiosite": 0.003, "symetrique": {"version": 1},
                                  "precision": {"stop_max_agitation": 0.4}, "journal": {"version": 1}}, "N2", "v1", 5)
    return MT.cerveau_apprentie(mere.state_dict(), t), t


def test_laisse_se_relache():
    t = {"mentor": {"nee_a": 10, "laisse_depart": 1.0, "relache": 0.8}}
    assert MT.laisse(t, 10) == 1.0 and MT.laisse(t, 11) == pytest.approx(0.8) and MT.laisse(t, 20) == pytest.approx(0.8 ** 10)
    assert MT.laisse({}, 5) == 0.0 and MT.laisse(None, 5) == 0.0


def test_apprentie_forme(mains_du_mentor):
    net, t = _apprentie()
    fo = C.forme(net.state_dict())
    assert fo["journal"] and fo["tendance"] and fo["suiveur_1r"] and fo["delais"] == C.REGARDS_LONGS[7]
    assert net.symetrique and net.stop_max_agitation == 0.4 and MT.est_apprentie(t) and t["jeunesse"] == MT.JEUNESSE
    with pytest.raises(ValueError):
        MT.temperament_apprentie({"nom": "precision"}, "X")                 # la mère doit être symétrique


def test_imitation_fait_baisser_la_perte(mains_du_mentor, monkeypatch):
    from collapsar.ecole.precision import jeu as JEU
    monkeypatch.setattr(R().monde, "challenge_jours", 10)          # départs étalés jusqu'à l'été (tendance 120 j connue)
    U = _univers()
    net, t = _apprentie()
    lecon = JEU.Lecon(U, 48, np.random.default_rng(2))
    m, st = MT.regarder_le_mentor(lecon, net, 1500)
    assert st["regards"] > 0 and st["ouvertures"] > 0 and m["pos"].shape[-1] == net.F - C.taille_caracteristiques()
    a0 = MT.accord(net, lecon.table, m)
    opt = torch.optim.AdamW(net.parameters(), lr=1e-3)
    net.train()
    i = torch.arange(len(m["t"]))
    for _ in range(40):
        s, fm, cm = MT._lot(lecon.table, m, i)
        p, hors = MT.perte_imitation(net, s, fm, m["fc"][i], m["pos"][i], cm)
        opt.zero_grad()
        p.backward()
        opt.step()
        assert hors == 0
    a1 = MT.accord(net, lecon.table, m)
    assert a1["perte_par_regard"] < a0["perte_par_regard"] - 1.0
    assert a1["geste_le_plus_probable_pct"] >= a0["geste_le_plus_probable_pct"]
    assert a1["delai_pct"] > a0["delai_pct"]


def test_recompense_en_laisse(mains_du_mentor, monkeypatch):
    from collapsar.ecole.precision import jeu as JEU
    monkeypatch.setattr(R().monde, "challenge_jours", 10)
    U = _univers()
    net, t = _apprentie()
    br = SimpleNamespace(net=net, opt=torch.optim.AdamW(net.parameters(), lr=3e-4), t=t)
    lecon = JEU.Lecon(U, 16, np.random.default_rng(0))
    m, _ = lecon.jouer(net, 64)
    avant = [p.detach().clone() for p in net.parameters()]
    e = SimpleNamespace(epoques=1, paquet=256, coupe=0.2, curiosite=0.003)
    a = MT.apprendre_en_laisse(br, lecon.table, m, 6, e)
    assert a["laisse"] == pytest.approx(0.8) and np.isfinite(a["perte_mentor"]) and a["perte_mentor"] > 0
    assert 0 <= a["accord_geste_pct"] <= 100 and np.isfinite(a["perte_decision"])
    assert any(not torch.equal(x, p) for x, p in zip(avant, net.parameters()))


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
    # la mère : la cime, rendue symétrique (comme N2) pour le test
    f = d / "branches" / f"{cime}.pt"
    e = torch.load(f, weights_only=False)
    e["temperament"] = {**e["temperament"], "symetrique": {"version": 1}, "precision": {"stop_max_agitation": 0.4}}
    torch.save(e, f)
    sortie = d / "mentor" / "apprentie.pt"
    MT.preparer(d, cime, sortie, "cpu", 1, 1, dire=lambda *_: None, comptes=24, bougies=60)
    info = MT.appliquer(d, sortie, None, cime, dire=lambda *_: None)
    a2 = Arbre.charger(d / "arbre.json")
    nouv = info["branche"]
    faible = info["remplacee"]
    assert faible != cime and a2.branches[faible].morte is not None and (d / "archives" / f"{faible}.pt").exists()
    assert a2.branches[nouv].parents == [cime] and MT.est_apprentie(a2.branches[nouv].temperament)
    assert a2.branches[nouv].temperament["mentor"]["nee_a"] == 3
    assert (d / MT.FICHIER).exists() and any((d / "sauvegardes").glob("avant_mentor_*"))
    with pytest.raises(SystemExit):
        MT.appliquer(d, sortie, None, cime, dire=lambda *_: None)          # une seule fois
    (d / "ARRET").unlink()
    capsys.readouterr()
    L.main(["--generations", "4"] + base)
    sortie_txt = capsys.readouterr().out
    assert f"{nouv} [SYMÉTRIQUE] [APPRENTIE laisse 0.80" in sortie_txt
    lignes = [json.loads(x) for x in (d / "journal_croissance.jsonl").read_text(encoding="utf-8").splitlines()]
    g4 = [x for x in lignes if x.get("quoi") == "generation"][-1]
    assert g4["branches"][nouv]["laisse"]["laisse"] == pytest.approx(0.8)
    # retour léger puis complet
    MT.retirer(d, lambda *_: None)
    a3 = Arbre.charger(d / "arbre.json")
    assert a3.branches[nouv].morte is not None and not (d / MT.FICHIER).exists()
    (d / MT.FICHIER).write_text(json.dumps(info), encoding="utf-8")
    MT.defaire(d, lambda *_: None)
    a4 = Arbre.charger(d / "arbre.json")
    assert sorted(b.nom for b in a4.vivantes()) == vivantes and a4.battements == 3
    assert (d / "branches" / f"{faible}.pt").exists() and not (d / "archives" / f"{faible}.pt").exists()
