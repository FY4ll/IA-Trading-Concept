"""La vision du trader : le vrai chemin du prix, bougie par bougie, sans jamais tricher en faveur de l'IA."""
import math

import numpy as np
import pandas as pd
import torch

from collapsar.cerveau.trader import CerveauTrader, greffer
from collapsar.regarder.vision_trader import SONDE_OBJECTIFS, SONDE_STOPS, VisionTrader
from collapsar.yeux.graphique import Graphique

DEBUT_CTRL = pd.Timestamp("2022-02-01")


def _plat(n=20000, debut="2021-06-01"):
    t = pd.date_range(debut, periods=n * 2, freq="15min")
    t = t[t.dayofweek < 5][:n]                                    # week-ends fermés, comme un vrai marché
    c = np.full(n, 100.0)
    return pd.DataFrame({"time": t, "open": c, "high": c * 1.0005, "low": c * 0.9995, "close": c,
                         "volume": np.ones(n)})


def _vision(df, nom="EURUSD"):
    g = Graphique({nom: df})
    return g, VisionTrader(g, debut_controle=DEBUT_CTRL, debut_apprentissage=pd.Timestamp("2000-01-01"),
                           n_controle=2000)


def _poser(df, k, u, o, h, l, c):
    """Bougie k, prix en tailles de bougie autour de 100."""
    df.loc[k, ["open", "high", "low", "close"]] = [100 * math.exp(x * u) for x in (o, h, l, c)]


def _un_mardi(df):
    t = df["time"]
    return int(np.flatnonzero((t.dt.dayofweek == 1) & (t.dt.hour == 12) & (t < DEBUT_CTRL))[3])


def _coup(vt, i, sens, stop, objectif):
    r, a = vt.resultat(torch.tensor([i]), torch.tensor([float(sens)]), torch.tensor([float(stop)]),
                       torch.tensor([[float(objectif)]]))
    return float(r[0, 0]), bool(a[0, 0])


def test_objectif_atteint_avant_le_stop():
    df = _plat()
    i = _un_mardi(df)
    u = math.log(1.0005 / 0.9995)
    _poser(df, i + 1, u, 0, 1.5, -0.5, 1)
    _poser(df, i + 2, u, 1, 3, 0.8, 2.5)
    g, vt = _vision(df)
    assert abs(float(vt.taille[i]) - u) < 1e-6
    r, a = _coup(vt, i, +1, 1, 2)
    assert a and abs(r - 2) < 1e-3, "objectif 2 fois le risque atteint à la 2e bougie"
    r, a = _coup(vt, i, -1, 1, 2)
    assert not a and abs(r + 1) < 1e-3, "la vente, elle, prend son stop (1,5 taille de hausse)"


def test_stop_et_objectif_dans_la_meme_bougie_compte_le_stop():
    df = _plat()
    i = _un_mardi(df)
    u = math.log(1.0005 / 0.9995)
    _poser(df, i + 1, u, 0, 3, -1.5, 0)
    g, vt = _vision(df)
    r, a = _coup(vt, i, +1, 1, 2)
    assert not a and abs(r + 1) < 1e-3


def test_stop_saute_par_un_trou_se_paie_a_l_ouverture():
    df = _plat()
    i = _un_mardi(df)
    u = math.log(1.0005 / 0.9995)
    _poser(df, i + 1, u, -3, -2.9, -3.5, -3.2)
    g, vt = _vision(df)
    r, a = _coup(vt, i, +1, 1, math.inf)
    assert not a and abs(r + 3) < 1e-3, "on perd 3 tailles, pas 1"


def test_fermeture_forcee_avant_le_week_end():
    df = _plat()
    t = df["time"]
    i = int(np.flatnonzero((t.dt.dayofweek == 4) & (t.dt.hour == 22) & (t.dt.minute == 0) & (t < DEBUT_CTRL))[2])
    u = math.log(1.0005 / 0.9995)
    for k in range(i + 1, i + 8):                                  # jusqu'à 23h45, dernière bougie de la semaine
        _poser(df, k, u, 0.5, 0.9, 0.1, 0.5)
    _poser(df, i + 8, u, 9, 9.5, 8.9, 9)                           # lundi : énorme hausse, trop tard
    g, vt = _vision(df)
    assert int(vt.duree[i]) == 7
    r, a = _coup(vt, i, +1, 1000, 5)                               # pas de stop, objectif lointain
    assert not a and abs(r - 0.5) < 1e-3, "fermé vendredi soir à +0,5 taille"
    i_dernier = i + 7
    assert int(vt.duree[i_dernier]) == 0, "à la dernière bougie avant le week-end, on n'ouvre rien"


def test_apprendre_noter_greffer():
    from collapsar.cerveau.reseau import Cerveau
    rng = np.random.default_rng(0)
    df = _plat(n=24000)
    c = 100 * np.exp(np.cumsum(rng.normal(0, 0.001, len(df))))
    o = np.r_[c[0], c[:-1]]
    df = df.assign(open=o, high=np.maximum(o, c) * 1.0003, low=np.minimum(o, c) * 0.9997, close=c)
    g, vt = _vision(df, "BTCUSD")                                  # frais élevés : le hasard doit perdre
    t = pd.DatetimeIndex(g.temps)
    assert (t[vt.idx_controle.numpy()] >= DEBUT_CTRL).all()
    fin_apprentissage = t[np.minimum(vt.idx_apprend.numpy() + vt.duree[vt.idx_apprend].numpy(), g.n - 1)]
    assert (fin_apprentissage < DEBUT_CTRL).all(), "aucun coup d'apprentissage ne se termine dans le contrôle"
    racines = Cerveau()
    cerveau = CerveauTrader()
    assert greffer(cerveau, racines.state_dict()) > 0
    assert torch.equal(cerveau.tronc[0].weight, racines.tronc[0].weight)
    idx = vt.idx_apprend[:32]
    p0, p1 = vt.perte(cerveau, idx), vt.perte(cerveau, idx, miroir=1.0)
    assert torch.isfinite(p0) and torch.isfinite(p1)
    opt = torch.optim.AdamW(cerveau.parameters(), lr=1e-3)
    travail = vt.entrainer(cerveau, opt, 0.05, 64, torch.Generator().manual_seed(0))
    assert travail["exercices"] > 0
    note = vt.controler(cerveau)
    assert vt.resultats_sondes().shape == (len(vt.idx_controle), 2 * len(SONDE_STOPS) * len(SONDE_OBJECTIFS))
    assert all(math.isfinite(v) for v in note.values())
    assert note["hasard"] < 0, "au hasard, les frais font perdre"
