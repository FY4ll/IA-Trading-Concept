"""Les mains : chaque règle du simulateur vérifiée sur des prix calculés à la main."""
import math

import pandas as pd
import pytest
import torch

from collapsar.mains.horloge import Horloge
from collapsar.mains.simulateur import CAPITAL, Comptes, Ordres

NAN = float("nan")
S = 0.00003                    # demi-écart de l'euro-dollar (frais d'un trade complet 0,006 %)


@pytest.fixture(autouse=True)
def sans_releve(monkeypatch):
    """Les tests utilisent les conditions de référence, pas le relevé du courtier (qui change)."""
    from collapsar.mains import fiches
    monkeypatch.setattr(fiches, "_reelles", lambda: {})


def _df(debut, bougies):
    """bougies : liste de (o, h, l, c) ou d'un seul prix (bougie plate), toutes les 15 minutes."""
    t = pd.date_range(debut, periods=len(bougies), freq="15min")
    rows = [b if isinstance(b, tuple) else (b, b, b, b) for b in bougies]
    return pd.DataFrame({"time": t, "open": [r[0] for r in rows], "high": [r[1] for r in rows],
                         "low": [r[2] for r in rows], "close": [r[3] for r in rows], "volume": 1.0})


def _compte(bougies, debut="2022-01-11 10:00", marches=("EURUSD",), autres=None):
    donnees = {"EURUSD": _df(debut, bougies)} if isinstance(bougies, list) else dict(bougies)
    donnees.update(autres or {})
    h = Horloge(donnees, list(marches))
    c = Comptes(h, 1)
    c.recommencer(torch.tensor([True]), torch.tensor([0]))
    return c


def _o(**k):
    return Ordres(**{n: torch.tensor([[v] if not isinstance(v, list) else v], dtype=torch.float64)
                     for n, v in k.items()})


def test_achat_paye_l_ecart_et_suit_le_prix():
    c = _compte([1.0, 1.0, (1.0, 1.02, 1.0, 1.01), 1.01])
    c.pas(_o(cible=100_000.0))
    assert c.u.item() == pytest.approx(100_000)
    assert c.entree.item() == pytest.approx(1.0 * (1 + S))
    r = c.pas(Ordres())
    assert r["valeur"].item() == pytest.approx(CAPITAL + 100_000 * (1.01 - (1 + S)))


def test_fermer_et_perte_coupee():
    c = _compte([1.0, 1.0, 0.99, 0.99])
    c.pas(_o(cible=100_000.0))
    c.pas(_o(cible=0.0))
    assert c.u.item() == 0
    assert c.solde.item() == pytest.approx(CAPITAL + 100_000 * (0.99 * (1 - S) - (1 + S)))


def test_stop_et_objectif_dans_la_meme_bougie_le_stop_gagne():
    c = _compte([1.0, 1.0, (1.0, 1.03, 0.98, 1.0), 1.0])
    c.pas(_o(cible=100_000.0, stop=0.99, objectif=1.02))
    c.pas(Ordres())
    assert c.u.item() == 0
    assert c.solde.item() == pytest.approx(CAPITAL + 100_000 * (0.99 - (1 + S)))


def test_trou_de_prix_le_stop_part_au_prix_d_ouverture():
    c = _compte([1.0, 1.0, (0.97, 0.975, 0.96, 0.97), 0.97])
    c.pas(_o(cible=100_000.0, stop=0.99))
    c.pas(Ordres())
    assert c.solde.item() == pytest.approx(CAPITAL + 100_000 * (0.97 * (1 - S) - (1 + S)))


def test_ordre_limite_seulement_si_le_prix_va_au_dela():
    c = _compte([1.0, (1.0, 1.0, 0.995, 1.0), (1.0, 1.0, 0.99, 0.995), 1.0])
    c.pas(_o(attente_type=1, attente_prix=0.995, attente_montant=99_500.0, attente_duree=10))
    assert c.u.item() == 0, "le prix a seulement touché 0,995 : pas exécuté"
    c.pas(Ordres())
    assert c.u.item() == pytest.approx(100_000) and c.entree.item() == pytest.approx(0.995)


def test_ordre_a_l_avance_expire():
    c = _compte([1.0, 1.0, 1.0, (1.0, 1.0, 0.98, 1.0)])
    c.pas(_o(attente_type=1, attente_prix=0.99, attente_montant=99_000.0, attente_duree=2))
    c.pas(Ordres())
    c.pas(Ordres())
    assert c.u.item() == 0 and c.att_type.item() == 0


def test_stop_du_mauvais_cote_refuse():
    c = _compte([1.0, 1.0, 1.0])
    r = c.pas(_o(cible=100_000.0, stop=1.01))
    assert math.isnan(c.stop.item()) and r["refus"].item() == 1


def test_retournement_garde_le_nouveau_stop():
    c = _compte([1.0, 1.0, 1.0, 1.0])
    c.pas(_o(cible=100_000.0, stop=0.99))
    c.pas(_o(cible=-100_000.0, stop=1.01, objectif=0.98))
    assert c.u.item() == pytest.approx(-100_000)
    assert c.stop.item() == pytest.approx(1.01) and c.objectif.item() == pytest.approx(0.98)


def test_argent_engage_trop_grand_refuse():
    c = _compte([1.0, 1.0, 1.0])
    r = c.pas(_o(cible=CAPITAL * 150))                  # levier 1:30 sur les devises (compte Swing mesuré)
    assert c.u.item() == 0 and r["refus"].item() == 1


def test_pas_de_lot_pas_de_micro_reajustement():
    c = _compte([1.0, 1.0, 1.0001, 1.0002, 1.0])
    c.pas(_o(cible=100_000.0))
    frais = [c.pas(_o(cible=100_000.0))["frais"].item() for _ in range(2)]
    assert frais == [0.0, 0.0], "un réajustement plus petit que 0,01 lot n'est pas envoyé"


def test_fermeture_forcee_avant_le_week_end():
    vendredi = _df("2022-01-14 20:15", [1.0, 1.0, 1.0, 1.0])        # dernière bougie : vendredi 21:00 (UTC)
    lundi = _df("2022-01-16 22:00", [1.0, 1.0])                      # réouverture dimanche soir
    df = pd.concat([vendredi, lundi], ignore_index=True)
    c = _compte({"EURUSD": df})
    c.pas(_o(cible=100_000.0))
    r1 = c.pas(Ordres())
    assert c.u.item() == pytest.approx(100_000) and r1["forcees"].item() == 0
    r2 = c.pas(_o(cible=100_000.0))                                   # elle veut garder : interdit
    assert c.u.item() == 0 and r2["forcees"].item() == 1
    assert c.h.heures_pause[0, 0].item() == pytest.approx(1.0), "à 20:15, fermeture forcée dans 1 heure"


def test_frais_de_nuit_triples_le_mercredi():
    # les données sont à l'heure du serveur : minuit du mercredi 12 au jeudi 13/01/2022 -> triple
    c = _compte([1.0] * 8, debut="2022-01-12 23:15")
    c.pas(_o(cible=100_000.0))
    nuits = [c.pas(Ordres())["nuit"].item() for _ in range(4)]
    assert sum(1 for n in nuits if n > 0) == 1
    assert max(nuits) == pytest.approx(100_000 * 0.02 / 360 * 3)


def test_releve_frais_de_nuit_par_sens_et_taille_minimum(monkeypatch):
    from collapsar.mains import fiches
    monkeypatch.setattr(fiches, "_reelles", lambda: {"EURUSD": {"pas_unites": 1000, "min_unites": 10_000,
                                                                "nuit_achat": 0.038, "nuit_vente": -0.01}})
    f = fiches.fiche("EURUSD")
    assert f.nuit_achat == 0.038 and f.nuit_vente == 0.02, "le plus cher des deux ; reçu en vrai -> notre estimation"
    c = _compte([1.0] * 4)
    c.pas(_o(cible=5_000.0))
    assert c.u.item() == 0, "en dessous de la taille minimum : pas d'ordre"
    c.pas(_o(cible=20_000.0))
    assert c.u.item() == pytest.approx(20_000)


def test_mur_du_jour_depuis_minuit_a_prague():
    # 10:00 UTC : achat de 1 000 000 $ (levier 10) puis chute de 0,6 % = -6 000 $ > 5 % ? non : 6 % du capital
    c = _compte([1.0, 1.0, (1.0, 1.0, 0.994, 0.999), 0.999])
    c.pas(_o(cible=1_000_000.0))
    r = c.pas(Ordres())
    assert r["mort"].item(), "au pire moment de la bougie, -6 % : partie perdue"
    assert c.u.item() == 0


def test_minuit_ftmo_a_prague_depuis_l_heure_serveur():
    from collapsar.mains.horloge import heure_prague
    t = pd.DatetimeIndex(["2022-01-12 00:45", "2022-01-12 01:00", "2022-07-12 00:45", "2022-07-12 01:00"])
    p = heure_prague(t)
    assert [x.strftime("%d %H:%M") for x in p] == ["11 23:45", "12 00:00", "11 23:45", "12 00:00"], \
        "minuit à Prague = 1h du serveur, été comme hiver"


def test_conversion_du_yen_en_dollars():
    usdjpy = _df("2022-01-11 10:00", [100.0, 100.0, 101.0, 101.0])
    eurusd = _df("2022-01-11 10:00", [1.0] * 4)
    c = _compte({"USDJPY": usdjpy, "EURUSD": eurusd}, marches=("USDJPY",))
    c.pas(_o(cible=100_000.0))                       # 1 000 dollars-unités... 100 000 $ = 100 000 unités d'USD
    r = c.pas(Ordres())
    gain_yen = c.u.item() * (101.0 - c.entree.item())
    assert r["valeur"].item() == pytest.approx(CAPITAL + gain_yen / 101.0)


def test_un_seul_compte_pour_tous_les_marches():
    eur = _df("2022-01-11 10:00", [1.0, 1.0, 0.98, 0.98])
    gbp = _df("2022-01-11 10:00", [1.3, 1.3, 1.3, 1.3])
    c = _compte({"EURUSD": eur, "GBPUSD": gbp}, marches=("EURUSD", "GBPUSD"))
    # 16/10 : levier FTMO Swing 1:30 -> 1,5 M$ + 0,75 M$ (22,5 x le compte ; 5 M$ = 50 x était refusé)
    c.pas(Ordres(cible=torch.tensor([[1_500_000.0, 750_000.0]], dtype=torch.float64)))
    marche, compte = c.vue()
    assert marche.shape == (1, 2, 13) and compte.shape == (1, 7)
    assert (marche[0, :, 0] > 0).all(), "elle voit ses DEUX positions"
    r = c.pas(Ordres())
    assert r["mort"].item(), "la perte sur l'euro (-4 %) + l'écart : le même compte, le même mur"


def test_plus_10_en_un_seul_jour_ne_suffit_pas():
    c = _compte([1.0, 1.0, 1.06, 1.06])
    c.pas(_o(cible=2_000_000.0))
    r = c.pas(Ordres())
    assert not r["reussi"].item() and not r["mort"].item(), "FTMO : au moins 4 jours de trading"
    assert c.jours_trades.item() == 1


def test_challenge_reussi_a_plus_10_apres_4_jours_de_trading():
    c = _compte([1.0, 1.0, 1.06, 1.06])
    c.jours_trades[:] = 3                              # trois jours de trading déjà faits, un autre jour
    c.jour_dernier_trade[:] = c.jour - 1
    c.pas(_o(cible=2_000_000.0))
    r = c.pas(Ordres())
    assert c.jours_trades.item() == 4
    assert r["reussi"].item() and not r["mort"].item()


def test_trente_jours_sans_trade_compte_termine():
    t = pd.DatetimeIndex(["2022-01-11 10:00", "2022-01-11 10:15", "2022-02-15 10:00", "2022-02-15 10:15"])
    df = pd.DataFrame({"time": t, "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0, "volume": 1.0})
    c = _compte({"EURUSD": df})
    r = c.pas(Ordres())
    assert not r["mort"].item()
    r = c.pas(Ordres())
    assert r["mort"].item() and r["inactif"].item(), "35 jours sans ouvrir un trade : FTMO termine le compte"
    assert r["valeur"].item() == pytest.approx(CAPITAL)
