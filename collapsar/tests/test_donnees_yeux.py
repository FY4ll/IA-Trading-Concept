"""Données et yeux : la règle d'honnêteté, et elle ne voit JAMAIS une bougie pas encore fermée."""
import numpy as np
import pandas as pd
import torch

from collapsar.donnees import marches as dm
from collapsar.regarder.exercices import Exercices, HORIZONS
from collapsar.yeux.graphique import LARGEUR, Graphique


def _marche(n=12000, graine=0, debut="2021-11-01"):
    rng = np.random.default_rng(graine)
    t = pd.date_range(debut, periods=n * 2, freq="15min")
    t = t[t.dayofweek < 5][:n]                                    # pas de week-end, comme un vrai marché
    c = 100 * np.exp(np.cumsum(rng.normal(0, 0.001, n)))
    o = np.r_[c[0], c[:-1]]
    return pd.DataFrame({"time": t, "open": o, "high": np.maximum(o, c) * 1.0005,
                         "low": np.minimum(o, c) * 0.9995, "close": c, "volume": rng.uniform(1, 10, n)})


def test_charger_rend_seulement_avant_2023():
    df = dm.charger("EURUSD", cache=False)
    assert len(df) > dm.MIN_BOUGIES and df["time"].max() < dm.FIN_APPRENTISSAGE


def test_debuts_des_echelles():
    t = np.array(["2024-05-15T13:47:00"], dtype="datetime64[ns]")       # un mercredi
    assert str(dm.debut_echelle(t, "4 h")[0])[:19] == "2024-05-15T12:00:00"
    assert str(dm.debut_echelle(t, "semaine")[0])[:10] == "2024-05-12"     # le dimanche d'avant
    assert str(dm.debut_echelle(t, "mois")[0])[:10] == "2024-05-01"
    assert str(dm.fin_echelle(dm.debut_echelle(t, "mois"), "mois")[0])[:10] == "2024-06-01"


def test_seulement_des_bougies_terminees():
    df = _marche()
    t = df["time"].values.astype("datetime64[ns]")
    decision = t + dm.QUINZE
    for nom in dm.ECHELLES:
        ech = dm.echelle(df, nom)
        d = dm.dernieres_terminees(t, ech)
        ok = d >= 0
        assert (ech["fin"][d[ok]] <= decision[ok]).all(), nom
        suivante = np.minimum(d + 1, len(ech["fin"]) - 1)
        pas_fini = (d + 1 < len(ech["fin"]))
        assert (ech["fin"][suivante[pas_fini]] > decision[pas_fini]).all(), nom


def test_le_futur_ne_change_pas_ce_quelle_voit():
    a, b = _marche(graine=1), _marche(graine=2)
    g = Graphique({"A": a, "B": b})
    i = 9000
    avant = g.voir(torch.tensor([i, len(a) + 5000]))
    a2, b2 = a.copy(), b.copy()
    for df, k in ((a2, i + 1), (b2, 5001)):                     # on change tout ce qui vient APRÈS la décision
        df.loc[k:, ["open", "high", "low", "close"]] *= 1.5
        df.loc[k:, "volume"] *= 3
    g2 = Graphique({"A": a2, "B": b2})
    apres = g2.voir(torch.tensor([i, len(a) + 5000]))
    for x, y in zip(avant, apres):
        assert torch.allclose(x, y, atol=1e-5)
    f, extra = avant
    assert f.shape == (2, len(dm.ECHELLES), LARGEUR, 6) and torch.isfinite(f).all() and torch.isfinite(extra).all()


def _horaire(n=3000, graine=5, fin="2021-10-29"):
    rng = np.random.default_rng(graine)
    t = pd.date_range(end=fin, periods=n * 2, freq="1h")
    t = t[t.dayofweek < 5][-n:]
    c = 100 * np.exp(np.cumsum(rng.normal(0, 0.002, n)))
    o = np.r_[c[0], c[:-1]]
    return pd.DataFrame({"time": t, "open": o, "high": np.maximum(o, c) * 1.001, "low": np.minimum(o, c) * 0.999,
                         "close": c, "volume": rng.uniform(1, 10, n)})


def test_tout_l_historique_bougies_horaires_puis_15_minutes():
    m15 = _marche(n=8000)                                       # commence le 01/11/2021
    h1 = _horaire()
    g = Graphique({"A": m15}, horaires={"A": h1})
    assert g.n == len(h1) + len(m15) and g.n_h1["A"] == len(h1)
    f, x = g.voir(torch.tensor([100, len(h1) + 3000]))
    assert f[0, 0, :, 5].sum() == 0, "sur les années horaires, la case 15 minutes est vide (et elle le sait)"
    assert f[0, 1, :, 5].sum() > 0 and f[1, 0, :, 5].sum() > 0, "l'échelle 1 h est remplie ; ensuite, le 15 min aussi"
    # le futur ne change rien à ce qu'elle voit, même sur une ligne horaire
    h2 = h1.copy()
    h2.loc[101:, ["open", "high", "low", "close"]] *= 1.3
    g2 = Graphique({"A": m15}, horaires={"A": h2})
    for a, b in zip(g.voir(torch.tensor([100])), g2.voir(torch.tensor([100]))):
        assert torch.allclose(a, b, atol=1e-5)
    ex = Exercices(g, debut_controle=pd.Timestamp("2022-02-01"), debut_apprentissage=pd.Timestamp("2000-01-01"))
    i = 500                                                     # une ligne horaire : réponse « 1 h » = bougie suivante
    attendu = float(g.lc15[i + 1] - g.lc15[i]) > 0
    assert bool(ex.sens[i, 0]) == attendu and bool(ex.valide[i, 0])
    assert not ex.valide[len(h1) - 1, 0], "aucune réponse n'enjambe la jonction heure -> 15 minutes"
    assert (pd.DatetimeIndex(g.temps)[ex.idx_apprend.numpy()] < pd.Timestamp("2021-11-01")).any(), \
        "elle apprend aussi sur les années horaires"


def test_exercices_retournes():
    from collapsar.cerveau.reseau import Cerveau
    g = Graphique({"A": _marche(n=20000, debut="2021-06-01")})
    ex = Exercices(g, debut_controle=pd.Timestamp("2022-02-01"), debut_apprentissage=pd.Timestamp("2021-06-01"))
    c = Cerveau()
    idx = ex.idx_apprend[:64]
    p0, p1 = ex.perte(c, idx), ex.perte(c, idx, miroir=1.0)
    assert torch.isfinite(p0) and torch.isfinite(p1) and not torch.isclose(p0, p1)


def test_les_racines_n_apprennent_pas_les_annees_de_l_ecole():
    g = Graphique({"A": _marche(n=20000, debut="2021-06-01")})
    ex = Exercices(g, debut_controle=pd.Timestamp("2022-02-01"), debut_apprentissage=pd.Timestamp("2021-09-01"))
    t = pd.DatetimeIndex(g.temps)
    assert (t[ex.idx_apprend.numpy()] >= pd.Timestamp("2021-09-01")).all()


def test_exercices_ne_debordent_pas_sur_le_controle():
    g = Graphique({"A": _marche(n=20000, debut="2021-06-01")})
    debut = pd.Timestamp("2022-02-01")
    ex = Exercices(g, debut_controle=debut, debut_apprentissage=pd.Timestamp("2000-01-01"))
    t = pd.DatetimeIndex(g.temps)
    semaine = HORIZONS["1 semaine"]
    fin_reponses = t[np.minimum(ex.idx_apprend.numpy() + semaine, g.n - 1)]
    assert (fin_reponses < debut).all(), "aucune réponse d'apprentissage ne vient de la période de contrôle"
    assert (t[ex.idx_controle.numpy()] >= debut).all() and len(ex.idx_controle) > 0
