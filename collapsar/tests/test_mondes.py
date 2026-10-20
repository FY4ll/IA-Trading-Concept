"""Le générateur de l'école des mille mondes : des bougies valides, des lois qui font ce qu'elles disent."""
import dataclasses

import numpy as np

from collapsar.mondes.generateur import BOUGIES_JOUR, fabriquer, tirer_lois
from collapsar.mondes.verifier import qualite_tendance


def _monde(graine=0, **modif):
    lois = tirer_lois(np.random.default_rng(graine), 3)
    return fabriquer(dataclasses.replace(lois, **modif), jours=260)


def test_bougies_valides_et_jours_de_semaine():
    d, v = _monde()
    assert len(d) == 3
    for df in d.values():
        assert len(df) == 260 * BOUGIES_JOUR
        assert np.isfinite(df[["open", "high", "low", "close"]].to_numpy()).all()
        assert (df["high"] >= df[["open", "close"]].max(axis=1)).all()
        assert (df["low"] <= df[["open", "close"]].min(axis=1)).all()
        assert (df["time"].dt.dayofweek < 5).all()
    assert v["derive"].shape == (260 * BOUGIES_JOUR, 3)


def test_meme_graine_meme_monde():
    a, _ = _monde(4)
    b, _ = _monde(4)
    assert np.array_equal(a["MONDE0"]["close"].to_numpy(), b["MONDE0"]["close"].to_numpy())


def test_une_tendance_forte_se_suit_et_le_hasard_ne_donne_rien():
    tend = {"probas_regimes": {"rien": 0.0, "tendance": 1.0, "retour": 0.0}, "force_tendance": 0.6,
            "duree_regimes_jours": {"rien": 10.0, "tendance": 30.0, "retour": 10.0}}
    q_tendance = np.mean([qualite_tendance(df, 10) for g in range(4) for df in _monde(g, **tend)[0].values()])
    rien = {"probas_regimes": {"rien": 1.0, "tendance": 0.0, "retour": 0.0}}
    q_rien = np.mean([qualite_tendance(df, 10) for g in range(4) for df in _monde(g, **rien)[0].values()])
    assert q_tendance > 1.0, "une tendance forte et longue doit se voir"
    assert abs(q_rien) < 0.5, "le hasard pur ne donne pas d'avantage"


def test_les_demarrages_font_des_mouvements_forts_apres_un_calme():
    calme = {"probas_regimes": {"rien": 1.0, "tendance": 0.0, "retour": 0.0}, "explosions_par_mois": 4.0,
             "force_explosion": 3.0, "duree_explosion_jours": 1.0, "sauts_par_mois": 0.0, "annonces_par_semaine": 0.0}
    d, v = _monde(2, **calme)
    assert v["explosion"].any(), "des démarrages ont eu lieu"
    c = np.log(d["MONDE0"]["close"].to_numpy())
    debuts = np.flatnonzero(v["explosion"][1:] & ~v["explosion"][:-1]) + 1
    gains = []
    for d0 in debuts:
        fin = d0 + 1
        while fin < len(c) and v["explosion"][fin]:
            fin += 1
        sens = np.sign(v["tendance"][d0:fin, 0].sum())
        gains.append(sens * (c[fin - 1] - c[d0 + 3]))                 # entré après la première heure
    agit_jour = np.std(np.diff(c[::BOUGIES_JOUR]))
    assert np.mean(gains) > 1.0 * agit_jour, "après l'allumage, le mouvement continue (le terrain des 10R)"


def test_verite_conservee():
    tend = {"probas_regimes": {"rien": 0.0, "tendance": 1.0, "retour": 0.0}}
    _, v = _monde(1, **tend)
    assert (v["regime"] == 1).all() and (np.abs(v["derive"]) > 0).all()
