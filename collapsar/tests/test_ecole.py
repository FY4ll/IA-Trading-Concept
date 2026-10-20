"""L'école tourne de bout en bout sur un petit marché inventé : jouer, apprendre, contrôler."""
import numpy as np
import pandas as pd
import pytest
import torch

from collapsar.cerveau.agent import Agent
from collapsar.cerveau.reseau import Cerveau
from collapsar.ecole.classe import Classe, Professeur, controler


def _eurusd():
    rng = np.random.default_rng(0)
    t = pd.date_range("2021-09-01", "2022-12-30", freq="15min")
    t = t[t.dayofweek < 5]
    c = 1.1 * np.exp(np.cumsum(rng.normal(0, 0.0007, len(t))))
    o = np.r_[c[0], c[:-1]]
    return pd.DataFrame({"time": t, "open": o, "high": np.maximum(o, c) * 1.0003, "low": np.minimum(o, c) * 0.9997,
                         "close": c, "volume": 1.0})


@pytest.mark.parametrize("yeux_figes", [True, False])
def test_une_lecon_complete(monkeypatch, yeux_figes):
    from collapsar.mains import fiches
    monkeypatch.setattr(fiches, "_reelles", lambda: {})
    classe = Classe(["EURUSD"], parties=6, donnees={"EURUSD": _eurusd()})
    agent = Agent(Cerveau(), yeux_figes=yeux_figes)
    avant = [p.clone() for p in agent.cerveau.parameters()]
    prof = Professeur(classe, agent, pas=12, paquet=24, epoques=2)
    s = prof.jouer()
    assert 0 <= s["agit"] <= 1 and np.isfinite(s["recompense"])
    av, retours = prof.avantages()
    assert av.shape == (12, 6) and retours.shape == (12, 6, 3) and torch.isfinite(av).all()
    b = prof.apprendre()
    assert all(np.isfinite(v) for v in b.values())
    inchanges = all(torch.equal(p, q) for p, q in zip(avant, agent.cerveau.parameters()))
    assert inchanges == yeux_figes, "yeux figés : l'école ne touche pas aux yeux des racines"
    ctrl = controler(classe, agent, comptes_n=3, duree=40)
    assert np.isfinite(ctrl["gain_moyen_mois_pct"]) and 0 <= ctrl["murs_touches_pct"] <= 100
    assert classe.h.temps[classe.fin_apprentissage] < pd.Timestamp("2022-06-22"), "elle n'apprend pas sur le contrôle"


def test_ecole_par_avis_de_bout_en_bout(monkeypatch):
    from collapsar.cerveau.agent import AgentAvis
    from collapsar.yeux.avis import N_AVIS, Avis
    from collapsar.mains import fiches
    monkeypatch.setattr(fiches, "_reelles", lambda: {})
    df = _eurusd()
    avis = Avis.calculer(Cerveau(), {"EURUSD": df}, lot=2048)
    assert avis.table.shape == (len(df), N_AVIS) and torch.isfinite(avis.table.float()).all()
    classe = Classe(["EURUSD"], parties=4, donnees={"EURUSD": df}, avis=avis,
                    apprendre_de=pd.Timestamp("2021-10-15"), apprendre_jusqua=pd.Timestamp("2022-05-01"))
    assert classe.g is None, "par avis : pas besoin des graphiques"
    agent = AgentAvis()
    prof = Professeur([classe], agent, pas=10, paquet=20, epoques=2)
    avant = [p.clone() for p in agent.encodeur.parameters()]
    prof.jouer()
    assert prof.memoire["lu"].shape == (10, 4, 1, N_AVIS)
    prof.apprendre()
    assert not all(torch.equal(p, q) for p, q in zip(avant, agent.encodeur.parameters())), "l'encodeur apprend"
    t = classe.h.temps
    assert t[classe.fin_apprentissage] < pd.Timestamp("2022-05-01")
    ctrl = controler(classe, agent, comptes_n=2, duree=30)
    assert np.isfinite(ctrl["gain_moyen_mois_pct"])


def test_imiter_puis_ameliorer_en_laisse(monkeypatch):
    import copy
    from collapsar.cerveau.agent import AgentAvis
    from collapsar.ecole.demonstration import TenirSonAvis
    from collapsar.ecole.imitation import Imitateur
    from collapsar.yeux.avis import Avis
    from collapsar.mains import fiches
    monkeypatch.setattr(fiches, "_reelles", lambda: {})
    df = _eurusd()
    avis = Avis.calculer(Cerveau(), {"EURUSD": df}, lot=2048)
    avis.normaliser({"EURUSD": np.arange(5000)})
    classe = Classe(["EURUSD"], parties=8, donnees={"EURUSD": df}, avis=avis,
                    apprendre_de=pd.Timestamp("2021-10-15"), apprendre_jusqua=pd.Timestamp("2022-05-01"))
    maitre = TenirSonAvis(avis, ["EURUSD"], "1 h", 1, conviction=0.5, lignes={"EURUSD": np.arange(5000)})
    assert np.isfinite(controler(classe, maitre, comptes_n=2, duree=50)["gain_moyen_mois_pct"])
    agent = AgentAvis()
    imit = Imitateur([classe], agent, maitre, pas=40, paquet=64, epoques=3)
    assert imit.regarder_le_maitre()["agit_maitre"] > 0, "le maître trade"
    b = imit.apprendre()
    assert np.isfinite(b["quand"]) and 0 <= b["rappel"] <= 1
    reference = copy.deepcopy(agent)
    prof = Professeur([classe], agent, pas=10, paquet=40, epoques=1, reference=reference, laisse=0.5)
    prof.jouer()
    assert np.isfinite(prof.echauffer()["perte_horloges"])
    assert all(np.isfinite(v) for v in prof.apprendre().values())


def test_parties_d_un_mois_et_curiosite_minimum(monkeypatch):
    from collapsar.ecole.classe import CURIOSITE_MIN
    from collapsar.mains import fiches
    monkeypatch.setattr(fiches, "_reelles", lambda: {})
    classe = Classe(["EURUSD"], parties=4, donnees={"EURUSD": _eurusd()})
    classe.duree_partie = 5
    agent = Agent(Cerveau())
    with torch.no_grad():
        agent.mains.bias[0] = -50.0                            # un élève qui ne voudrait plus jamais agir
    loi, _ = agent.lois(torch.full((4, 1), -50.0), torch.zeros(4, 1), CURIOSITE_MIN)
    assert torch.allclose(loi.probs, torch.full((4, 1), CURIOSITE_MIN)), "il garde 2 % de chances d'essayer"
    prof = Professeur(classe, agent, pas=12, paquet=24, epoques=1)
    prof.jouer()
    assert prof.memoire["fin"][4].all(), "au bout de la durée d'une partie, le compte repart à neuf"


def test_elle_sent_le_danger_pres_des_murs():
    from collapsar.ecole.classe import danger, ressenti
    cap = 100_000.0
    minuit = torch.tensor([100_000.0, 100_000.0, 100_000.0, 98_000.0])
    valeur = torch.tensor([100_500.0, 97_500.0, 96_000.0, 91_000.0])
    d = danger(valeur, minuit, cap)
    assert torch.allclose(d, torch.tensor([0.0, 0.5, 0.8, 1.0]))     # loin, mi-chemin du jour, 4/5, mur total
    perte, gain = torch.full((4,), -0.1), torch.full((4,), 0.1)
    assert torch.allclose(ressenti(perte, d), torch.tensor([-0.1, -0.2, -0.356, -0.5]))
    assert torch.equal(ressenti(gain, d), gain), "un gain compte tel quel"


def test_le_miroir_retourne_le_marche_et_joue_avec_le_vrai(monkeypatch):
    from collapsar.donnees.marches import miroir
    from collapsar.mains import fiches
    monkeypatch.setattr(fiches, "_reelles", lambda: {})
    df = _eurusd()
    m = miroir(df)
    r_vrai, r_miroir = np.diff(np.log(df["close"].values)), np.diff(np.log(m["close"].values))
    assert np.allclose(r_vrai, -r_miroir) and (m["high"] >= m["low"]).all()
    assert fiches.fiche("EURUSD_MIROIR").frais == fiches.fiche("EURUSD").frais
    vrai = Classe(["EURUSD"], parties=4, donnees={"EURUSD": df})
    retourne = Classe(["EURUSD_MIROIR"], parties=4, donnees={"EURUSD_MIROIR": m})
    prof = Professeur([vrai, retourne], Agent(Cerveau()), pas=8, paquet=16, epoques=1)
    s = prof.jouer()
    assert prof.memoire["r"].shape == (8, 8) and np.isfinite(s["recompense"])
    assert all(np.isfinite(v) for v in prof.apprendre().values())


def test_le_juge_tourne_et_ne_voit_pas_les_mois_caches(monkeypatch):
    from collapsar.juge.examen import Juge
    from collapsar.mains import fiches
    monkeypatch.setattr(fiches, "_reelles", lambda: {})
    rng = np.random.default_rng(1)
    t = pd.date_range("2021-01-01", "2025-09-30 23:45", freq="15min")
    t = t[t.dayofweek < 5]
    c = 1.1 * np.exp(np.cumsum(rng.normal(0, 0.0007, len(t))))
    df = pd.DataFrame({"time": t, "open": c, "high": c * 1.0003, "low": c * 0.9997, "close": c, "volume": 1.0})
    juge = Juge(["EURUSD"], donnees={"EURUSD": df})
    agent = Agent(Cerveau())
    e1, e2 = juge.examiner(agent, 1, comptes_n=3), juge.examiner(agent, 2, comptes_n=3)
    assert e1["periode"] != e2["periode"], "examen tournant : d'autres dates à chaque examen"
    assert np.isfinite(e1["note"])
    futur = df.copy()
    futur.loc[len(futur)] = [pd.Timestamp("2025-10-02"), 1, 1, 1, 1, 1]
    with pytest.raises(AssertionError):
        Juge(["EURUSD"], donnees={"EURUSD": futur})
    # le juge rapide : tous les marchés sur la même horloge, un compte = un marché, un mois = 30 jours
    from collapsar.cerveau.agent import AgentAvis
    from collapsar.ecole.demonstration import TenirSonAvis
    from collapsar.juge import examen
    from collapsar.yeux.avis import Avis
    gbp = df.copy()
    gbp[["open", "high", "low", "close"]] *= 1.2
    donnees = {"EURUSD": df, "GBPUSD": gbp}
    monkeypatch.setattr(examen, "donnees_examen", lambda marches, fin=None: {m: donnees[m] for m in marches})
    avis = Avis.calculer(Cerveau(), donnees, lot=4096)
    rapide = examen.JugeMarches(["EURUSD", "GBPUSD"], avis)
    r = rapide.examiner(AgentAvis(), 1, comptes_par_marche=2)
    u = rapide.examiner_compte_unique(AgentAvis(), 3, comptes=2, jours=30)
    assert u["marches"] == 2 and np.isfinite(u["gain_moyen_mois_pct"]) and 0 <= u["murs_touches_pct"] <= 100
    assert r["marches"] == 2 and set(r["par_marche"]) == {"EURUSD", "GBPUSD"} and np.isfinite(r["gain_moyen_mois_pct"])
    maitre = TenirSonAvis(avis, ["EURUSD", "GBPUSD"], "1 h", 1, 0.5, 1.0,
                          lignes={"EURUSD": np.arange(3000), "GBPUSD": np.arange(3000)})
    assert np.isfinite(rapide.examiner(maitre, 2, comptes_par_marche=1)["gain_moyen_mois_pct"])
