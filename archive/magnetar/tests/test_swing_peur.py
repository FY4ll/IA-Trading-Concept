"""Tests du COMPTE SWING et de la PEUR DU MUR CORRIGÉE (19/10/2026, MAGNETAR) :
- compte Normal : exactement comme avant (le même tableau pour la fermeture forcée et l'interdiction d'ouvrir) ;
- compte Swing, sur l'or avec la vraie horloge FTMO : une position du vendredi est encore ouverte le lundi, avec UNE
  nuit payée (or : nuit triple le mercredi, vendredi -> lundi = 1), l'écart d'ouverture du lundi subi au prix d'ouverture
  (stop pris dans l'écart, ordre limite exécuté au prix d'ouverture), la nuit du week-end payée même si la position se
  ferme à l'ouverture du lundi ; aucune nouvelle position dans les 2 dernières heures avant le week-end ;
- la peur « pres_des_murs » (rien loin des murs, rien au-dessus du plus haut solde réalisé du jour, x5 au mur) et
  « fermeture_r » (résultat en R à la fermeture) ;
- un cœur avec une branche « sans_peur » greffée, compte Swing et mesure des sorties : la génération se termine, puis
  retour arrière.
Depuis Test_IA : $env:CUDA_VISIBLE_DEVICES='-1'; venv_gpu\\Scripts\\python.exe -m pytest collapsar/tests/test_swing_peur.py -q
"""
from __future__ import annotations

import json
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from collapsar.ecole.precision import jeu as JEU
from collapsar.ecole.precision import simulateur as SIM
from collapsar.ecole.precision.reglages import R
from collapsar.ecole.precision.univers import regles_compte
from collapsar.mains.horloge import Horloge
from collapsar.mains.simulateur import CAPITAL

from test_ecole_precision import monde_invente, petite_ecole  # noqa: F401  (fixtures partagées)

S = 1e-4                       # demi-frais
NA, NV = 0.05, 0.02            # frais de nuit annuels (achat, vente)


# ================================================================================================ l'or, vraie horloge
def _or(gap_bas=1980.0):
    """Or en 15 min du mercredi 09/01/2019 01h00 au mardi 15/01 (heures du serveur, pause quotidienne d'1 h, week-end
    du vendredi 23h45 au lundi 01h00) ; prix plat à 2000, le lundi ouvre en écart à `gap_bas`."""
    t = pd.date_range("2019-01-09 01:00", "2019-01-15 23:45", freq="15min")
    t = t[(t.dayofweek < 5) & (t.hour >= 1)]
    p = np.full(len(t), 2000.0)
    o, h, l, c = p.copy(), p.copy(), p.copy(), p.copy()
    im = int(np.flatnonzero(t == pd.Timestamp("2019-01-14 01:00"))[0])
    o[im], h[im], l[im], c[im] = gap_bas, gap_bas + 5, gap_bas - 5, gap_bas + 2
    o[im + 1:] = h[im + 1:] = l[im + 1:] = c[im + 1:] = gap_bas + 2
    return pd.DataFrame({"time": t, "open": o, "high": h, "low": l, "close": c})


def _monde(df, compte: str, hmin: float = 2.0):
    hz = Horloge({"XAUUSD": df}, ["XAUUSD"], "cpu")
    T = hz.T
    der, sans = regles_compte(compte, hz.derniere.numpy(), hz.heures_pause.numpy(), hz.ouvert.numpy(), hmin)
    U = SimpleNamespace(o=hz.o.numpy(), h=hz.h.numpy(), l=hz.l.numpy(), c=hz.c.numpy(), fx=hz.fx.numpy(),
                        ouvert=hz.ouvert.numpy(), derniere=der, sans_ouverture=sans, compte=compte,
                        pause_longue=hz.derniere.numpy(), demi=np.full((T, 1), S), nuit_a=np.full((T, 1), NA),
                        nuit_v=np.full((T, 1), NV), nuits=hz.nuits_regle.numpy()[hz.regle_nuit.numpy()].T.copy(),
                        jour=hz.jour.numpy(), levier=hz.levier.numpy(), pas_u=hz.pas_unites.numpy(),
                        pas_d=hz.pas_dollars.numpy(), min_u=hz.min_unites.numpy(),
                        fin_challenge=lambda t0: np.full_like(t0, T - 1))
    i = lambda s: int(np.flatnonzero(hz.temps == pd.Timestamp(s))[0])
    return U, i


def _compte(U, t0):
    cp = SIM.Comptes(U, 1, 1)
    cp.recommencer(np.array([True]), np.array([[0]]), np.array([t0]))
    return cp


def _acheter(cp, stop, unites=50.0):
    cp.ord_act[0, 0], cp.ord_u[0, 0], cp.ord_stop[0, 0] = SIM.MARCHE, unites, stop
    cp.ord_tp1[0, 0] = cp.ord_dest[0, 0] = np.nan


def _jusqua(cp, n, U):
    """Pas jusqu'à l'instant n ; rend les événements et les nuits de chaque pas {instant: (evt, nuit, u)}."""
    vu = {}
    while cp.t[0] < n:
        cp.pas(1.0)
        vu[int(cp.t[0])] = (int(cp.evt[0, 0]), float(cp.nuit[0]), float(cp.u[0, 0]))
    return vu


def test_compte_normal_comme_avant():
    d = np.random.default_rng(0).random((50, 2)) < 0.1
    der, sans = regles_compte("normal", d, np.zeros((50, 2), np.float32), np.ones((50, 2), bool), 2.0)
    assert der is d and sans is d                         # le même tableau qu'avant, pour les deux usages


def test_nuits_de_l_or_triple_le_mercredi():
    U, i = _monde(_or(), "swing")
    assert U.nuits[i("2019-01-10 01:00"), 0] == 3          # nuit du mercredi : triple (FTMO, métaux)
    assert U.nuits[i("2019-01-11 01:00"), 0] == 1          # jeudi
    assert U.nuits[i("2019-01-14 01:00"), 0] == 1          # vendredi -> lundi : 1 seule (samedi et dimanche à 0)
    assert U.nuits[i("2019-01-15 01:00"), 0] == 1
    assert U.pause_longue[i("2019-01-11 23:45"), 0] and not U.derniere.any()


def test_position_du_vendredi_encore_ouverte_le_lundi():
    U, i = _monde(_or(), "swing")
    fin_ven, lundi = i("2019-01-11 23:45"), i("2019-01-14 01:00")
    cp = _compte(U, i("2019-01-11 17:45"))
    _acheter(cp, 1950.0)                                    # exécuté vendredi 18h00, stop loin de l'écart
    vu = _jusqua(cp, lundi, U)
    entree = 2000.0 * (1 + S)
    assert cp.entree[0, 0] == pytest.approx(entree)
    assert not vu[fin_ven][0] & SIM.FORCEE and vu[fin_ven][2] == 50.0       # rien de forcé avant le week-end
    evt, nuit, u = vu[lundi]
    assert u == 50.0 and evt == 0                           # toujours ouverte le lundi
    assert nuit == pytest.approx(50 * 2000.0 * NA / 360 * 1)                  # UNE nuit, au prix d'avant minuit
    assert sum(x[1] for x in vu.values()) == pytest.approx(nuit)             # et aucune autre depuis vendredi 18h
    # valeur du compte : l'écart du lundi est subi (clôture 1982)
    assert cp.valeurs()[0] == pytest.approx(CAPITAL + 50 * (1982.0 - entree) - nuit)
    # compte Normal : fermée de force à la dernière bougie du vendredi
    Un, _ = _monde(_or(), "normal")
    cn = _compte(Un, i("2019-01-11 17:45"))
    _acheter(cn, 1950.0)
    vn = _jusqua(cn, fin_ven, Un)
    assert vn[fin_ven][0] & SIM.FORCEE and cn.u[0, 0] == 0


def test_ecart_du_lundi_stop_pris_au_prix_d_ouverture_et_nuit_payee():
    U, i = _monde(_or(), "swing")
    lundi = i("2019-01-14 01:00")
    cp = _compte(U, i("2019-01-11 17:45"))
    _acheter(cp, 1990.0)                                    # le lundi ouvre à 1980 : SOUS le stop
    vu = _jusqua(cp, lundi, U)
    evt, nuit, u = vu[lundi]
    assert evt & SIM.STOP and u == 0
    entree = 2000.0 * (1 + S)
    sortie = 1980.0 * (1 - S) * (1 - S)                     # au prix d'ouverture (pas au stop), glissement compris
    assert nuit == pytest.approx(50 * 2000.0 * NA / 360)    # la nuit du week-end est payée quand même
    assert cp.solde[0] == pytest.approx(CAPITAL + 50 * (sortie - entree) - nuit)
    assert cp.r_ferme[0, 0] == pytest.approx((cp.solde[0] - CAPITAL) / (50 * (entree - 1990.0)))
    assert cp.r_ferme[0, 0] < -1.0                          # l'écart coûte plus que le risque prévu


def test_pas_d_ouverture_dans_les_2_heures_avant_le_week_end_et_limite_le_lundi():
    U, i = _monde(_or(), "swing")
    lundi = i("2019-01-14 01:00")
    # au marché, exécution prévue vendredi 22h15 : refusée en silence (rien n'est ouvert)
    cp = _compte(U, i("2019-01-11 22:00"))
    _acheter(cp, 1950.0)
    cp.pas(1.0)
    assert cp.u[0, 0] == 0 and not cp.evt[0, 0] & SIM.OUVERTE
    # sans l'interdiction (hmin = 0) : ouverte
    U0, _ = _monde(_or(), "swing", hmin=0.0)
    c0 = _compte(U0, i("2019-01-11 22:00"))
    _acheter(c0, 1950.0)
    c0.pas(1.0)
    assert c0.u[0, 0] == 50.0
    # ordre limite d'achat à 2000,5 posé vendredi 21h45 : il passerait dès 22h00, mais attend (fenêtre interdite),
    # reste en attente pendant le week-end et s'exécute au prix d'ouverture du lundi (1980 < 2000,5)
    cl = _compte(U, i("2019-01-11 21:45"))
    cl.ord_act[0, 0], cl.ord_u[0, 0], cl.ord_prix[0, 0], cl.ord_stop[0, 0] = SIM.LIMITE, 50.0, 2000.5, 1900.0
    cl.ord_tp1[0, 0] = cl.ord_dest[0, 0] = np.nan
    cl.ord_duree[0, 0] = 400
    vu = _jusqua(cl, lundi, U)
    assert all(x[2] == 0 for t, x in vu.items() if t < lundi) and cl.att[0, 0] == 0
    assert vu[lundi][0] & SIM.EXECUTE and cl.entree[0, 0] == pytest.approx(1980.0 * (1 + S))
    # compte Normal : l'ordre est annulé avant le week-end
    Un, _ = _monde(_or(), "normal")
    cn = _compte(Un, i("2019-01-11 21:45"))
    cn.ord_act[0, 0], cn.ord_u[0, 0], cn.ord_prix[0, 0], cn.ord_stop[0, 0] = SIM.LIMITE, 50.0, 1990.0, 1900.0
    cn.ord_tp1[0, 0] = cn.ord_dest[0, 0] = np.nan
    cn.ord_duree[0, 0] = 400
    _jusqua(cn, lundi, Un)
    assert cn.u[0, 0] == 0 and cn.att[0, 0] == 0


def test_univers_swing(monde_invente, monkeypatch):
    from collapsar.ecole.precision.univers import Univers
    de, a = pd.Timestamp("2019-03-01"), pd.Timestamp("2019-05-01")
    Un = Univers([("EURUSD", False)], de, a, "cpu")
    assert Un.compte == "normal" and Un.sans_ouverture is Un.derniere and Un.derniere.any()
    monkeypatch.setattr(R().mains, "compte", "swing", raising=False)
    monkeypatch.setattr(R().mains, "ouverture_interdite_avant_pause_h", 2.0, raising=False)
    Us = Univers([("EURUSD", False)], de, a, "cpu")
    assert Us.compte == "swing" and not Us.derniere.any()
    assert np.array_equal(Us.pause_longue, Un.derniere)
    assert Us.sans_ouverture[Un.derniere].all() and Us.sans_ouverture.sum() == 8 * Un.derniere.sum()


# ================================================================================================ la peur
def test_multiplicateur_de_peur():
    d = np.array([0.0, 0.25, 0.5, 0.75, 1.0])
    np.testing.assert_allclose(JEU.multiplicateur_peur(d), [1, 1, 1, 3, 5])


def test_douleur_pres_des_murs():
    g = lambda va, vb: (vb - va) / CAPITAL * 100
    # trade gagnant qui oscille AU-DESSUS du plus haut solde réalisé : l'argent tel quel, même près d'un mur
    assert JEU.douleur_pres_des_murs(g(101000, 100500), 101000, 100500, 100000, 0.9) == pytest.approx(-0.5)
    # sous le solde réalisé mais loin des murs (moins de la moitié de la perte permise) : l'argent tel quel
    assert JEU.douleur_pres_des_murs(g(99000, 98500), 99000, 98500, 100000, 0.3) == pytest.approx(-0.5)
    # près du mur (70 % de la perte du jour consommée) : x2,6 sur la baisse sous le solde réalisé
    assert JEU.douleur_pres_des_murs(g(97000, 96500), 97000, 96500, 100000, 0.7) == pytest.approx(-0.5 * 2.6)
    # une baisse qui traverse le solde réalisé : seule la part SOUS lui fait plus mal
    assert JEU.douleur_pres_des_murs(g(100200, 99800), 100200, 99800, 100000, 1.0) == pytest.approx(-0.4 - 4 * 0.2)
    # un gain ne fait jamais mal
    assert JEU.douleur_pres_des_murs(g(96500, 97000), 96500, 97000, 100000, 0.9) == pytest.approx(0.5)


def test_ressenti_de_branche():
    cpt = SimpleNamespace(r_ferme=np.array([[np.nan], [2.5], [-1.0]]), jour_cpt=np.array([5, 5, 6]),
                          solde_minuit=np.array([CAPITAL, CAPITAL, 96000.0]), solde=np.array([CAPITAL, 102500, 96000.0]),
                          valeur=np.array([99000.0, 102500, 96000.0]))
    t = SimpleNamespace(cpt=cpt, peur={"mode": "fermeture_r"}, haut_solde=np.full(3, CAPITAL))
    np.testing.assert_allclose(JEU.Table._ressenti_branche(t, None, None, None), [0.0, 2.5, -1.0])
    t.peur = {"mode": "pres_des_murs", "seuil": 0.5, "max": 5.0}
    v_avant = np.array([99500.0, 102000, 97000.0])
    gain = (cpt.valeur - v_avant) / CAPITAL * 100
    r = JEU.Table._ressenti_branche(t, gain, v_avant, np.array([5, 5, 5]))
    # compte 2 : nouveau jour -> référence = solde de minuit (96 000) : la baisse 97 000 -> 96 000 est au-dessus
    np.testing.assert_allclose(r, gain)
    np.testing.assert_allclose(t.haut_solde, [CAPITAL, 102500, 96000.0])
    with pytest.raises(ValueError):
        t.peur = {"mode": "autre"}
        JEU.Table._ressenti_branche(t, gain, v_avant, np.array([5, 5, 5]))


# ================================================================================================ le cœur
def test_empreinte_magnetar_swing():
    """Vrais réglages de l'or (compte Swing) et vraie cime figée : exactement l'empreinte écrite le 19/10."""
    import os
    import subprocess
    import sys
    from collapsar.donnees.marches import RACINE
    env = {**os.environ, "CUDA_VISIBLE_DEVICES": "-1"}
    env.pop("COLLAPSAR_PRECISION_REGLAGES", None)
    p = subprocess.run([sys.executable, "-m", "collapsar.tests.empreinte_magnetar", "swing"], cwd=RACINE, env=env,
                       capture_output=True, text=True, timeout=900)
    assert p.returncode == 0 and "RESULTAT IDENTIQUE" in p.stdout, p.stdout[-2000:] + p.stderr[-2000:]


def test_coeur_branche_sans_peur_compte_swing(petite_ecole, monkeypatch):
    from collapsar.arbre.jardinier import Arbre
    from collapsar.ecole.precision import peur as PE
    L, d = petite_ecole
    monkeypatch.setattr(R().mains, "compte", "swing", raising=False)
    monkeypatch.setattr(R().mains, "ouverture_interdite_avant_pause_h", 2.0, raising=False)
    monkeypatch.setattr(R().selection, "mesurer_sorties", True, raising=False)
    monkeypatch.setattr(R().monde, "challenge_jours", 10)
    monkeypatch.setattr(R().ecole, "bougies_par_lecon", 96)
    base = ["--dossier", str(d), "--appareil", "cpu", "--muet"]
    L.main(["--generations", "1"] + base)
    a1 = Arbre.charger(d / "arbre.json")
    info = PE.greffer(d, dire=lambda *_: None)
    assert info["cime"] == a1.cime and info["remplacee"] != a1.cime and (d / "peur.json").exists()
    with pytest.raises(SystemExit):
        PE.greffer(d, dire=lambda *_: None)                  # une seule greffe
    L.main(["--generations", "2"] + base)
    a = Arbre.charger(d / "arbre.json")
    assert a.battements == 2 and a.branches[info["branche"]].temperament["peur"] == PE.CHOIX
    assert "peur" not in a.branches[a1.cime].temperament                     # la cime : la peur d'avant
    lig = [json.loads(x) for x in (d / "journal_croissance.jsonl").read_text(encoding="utf-8").splitlines()]
    g2 = [x for x in lig if x.get("quoi") == "generation"][-1]
    ex = g2["branches"][info["branche"]]["examen"]
    assert {"sorties_pct", "gardes_pause_pct"} <= set(ex) and ex["sorties_pct"].get("forcee", 0.0) == 0.0
    PE.defaire(d, dire=lambda *_: None)
    assert not (d / "peur.json").exists() and (d / "branches" / f"{info['remplacee']}.pt").exists()
