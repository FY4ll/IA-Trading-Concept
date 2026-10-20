"""L'école des mille mondes : un monde se joue comme un vrai marché, le connaisseur mesure le gagnable, un monde neuf
remplace un ancien, et sa mémoire d'expérience suit son compte."""
import dataclasses
import math

import numpy as np
import torch

from collapsar.cerveau.humain import TraderHumain
from collapsar.ecole.regard import Etat, ProfesseurRegard, jouer_comptes
from collapsar.mains.simulateur import Ordres
from collapsar.mondes.ecole import ClasseMonde, ControleMondes, departs_monde, jouer_connaisseur, nouveau_monde
from collapsar.mondes.generateur import tirer_lois

JOURS = 200


def _monde(graine=0, **modif):
    lois = dataclasses.replace(tirer_lois(np.random.default_rng(graine), 2), **modif)
    return ClasseMonde(lois, "cpu", jours=JOURS)


def test_un_monde_se_joue_comme_un_marche():
    c = _monde()
    assert c.h.M == 2 and c.h.T == JOURS * 96
    assert c.derive.shape == (c.h.T, 2)
    assert all(f.famille == "monde" and f.frais > 0 for f in c.h.fiches)
    agent = TraderHumain()
    r = jouer_comptes(c, agent, departs_monde(c, 3, duree=600), duree=600)
    assert 0 <= r["murs_touches_pct"] <= 100 and r["regards_par_jour"] > 0


def test_le_connaisseur_gagne_quand_la_tendance_est_forte_et_rien_sans_avantage():
    forte = {"probas_regimes": {"rien": 0.0, "tendance": 1.0, "retour": 0.0}, "force_tendance": 0.5,
             "duree_regimes_jours": {"rien": 10.0, "tendance": 20.0, "retour": 10.0}}
    gains = [jouer_connaisseur(_monde(g, **forte), departs_monde(_monde(g, **forte), 4, 2000), 2000)["gain_moyen_pct"]
             for g in range(3)]
    assert np.mean(gains) > 0.3, f"le connaisseur doit gagner une tendance forte : {gains}"
    rien = {"probas_regimes": {"rien": 1.0, "tendance": 0.0, "retour": 0.0}, "explosions_par_mois": 0.0}
    c = _monde(5, **rien)
    assert abs(jouer_connaisseur(c, departs_monde(c, 4, 2000), 2000)["gain_moyen_pct"]) < 0.5


def test_un_monde_neuf_remplace_l_ancien():
    rng = np.random.default_rng(3)
    a, b = nouveau_monde(rng, 1.0, jours=JOURS), nouveau_monde(rng, 1.0, jours=JOURS)
    debut, fin = a.h.temps[0], a.h.temps[-1]
    prof = ProfesseurRegard([a], TraderHumain(), parties=4, pas=20, paquet=32, epoques=1, de=debut, jusqua=fin,
                            duree=1000)
    prof.jouer()
    prof.apprendre()
    prof.installer(0, b, debut, fin)
    assert prof.mondes[0] is b and prof.etats[0].comptes.h is b.h
    jeu = prof.jouer()
    assert jeu["regards_par_jour"] > 0


def test_memoire_d_experience_suit_le_compte():
    c = _monde(1)
    e = Etat(c.h, 1)
    e.recommencer(torch.tensor([True]), torch.tensor([3000]))
    prix = float(c.h.c[3000, 0])
    cible = torch.tensor([[1_000_000.0, 0.0]], dtype=torch.float64)
    c.avancer(e, Ordres(cible=cible), None)
    for _ in range(200):
        c.avancer(e, Ordres(), None)
    valeur = float(e.comptes.valeur(c.h.c[e.comptes.t], c.h.fx[e.comptes.t])[0])
    assert e.memoire.shape == (1, 2)
    assert float(e.memoire.abs().sum()) > 0, "après 200 bougies en position, sa mémoire a bougé"
    if abs(valeur - 100_000) > 50 and e.comptes.u[0, 0] != 0:
        assert math.copysign(1, float(e.memoire[0, 0])) == math.copysign(1, valeur - 100_000)


def test_controle_des_mondes():
    ctrl = ControleMondes(1.0, "cpu", mondes=2, comptes=2, jours=JOURS, duree=1500)
    r = ctrl.noter(TraderHumain())
    assert "gagnable_pct" in r and "capture_pct" in r and r["intensite"] == 1.0
    assert ctrl.noter(TraderHumain())["gagnable_pct"] == r["gagnable_pct"], "le gagnable est calculé une fois"
