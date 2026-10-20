"""Le connaisseur du risque (repère de l'examen) : il suit une tendance forte sans jamais toucher un mur, et son
risque se partage selon la distance au mur."""
import dataclasses

import numpy as np
import torch

from collapsar.juge.examen_humain import jouer_connaisseur_risque
from collapsar.mondes.ecole import ClasseMonde, departs_monde
from collapsar.mondes.generateur import tirer_lois


def _monde(graine, **modif):
    lois = dataclasses.replace(tirer_lois(np.random.default_rng(graine), 2), **modif)
    return ClasseMonde(lois, "cpu", jours=260)


def test_suit_une_tendance_forte_sans_mur():
    forte = {"probas_regimes": {"rien": 0.0, "tendance": 1.0, "retour": 0.0}, "force_tendance": 0.6,
             "duree_regimes_jours": {"rien": 10.0, "tendance": 60.0, "retour": 10.0}}
    gains, murs = [], []
    for g in range(3):
        c = _monde(g, **forte)
        r = jouer_connaisseur_risque(c, departs_monde(c, 3, 4000), 4000)
        gains.append(r["gain_moyen_pct"])
        murs.append(r["murs_touches_pct"])
    assert np.mean(gains) > 0, f"tendance forte et longue : il doit gagner ({gains})"
    assert max(murs) == 0, "10 % de la distance au mur : jamais de mur"


def test_tailles_regulieres():
    c = _monde(7)
    r = jouer_connaisseur_risque(c, departs_monde(c, 3, 3000), 3000)
    assert r["taille_max_sur_mediane"] < 10, "pas de position soudain beaucoup plus grosse (règle FTMO)"
