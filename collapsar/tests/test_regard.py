"""La nouvelle école « elle choisit quand revenir regarder » : chaque mécanisme vérifié sur des prix fabriqués."""
import math

import numpy as np
import pandas as pd
import pytest
import torch

from collapsar.cerveau.humain import ACHETER, ATTENDRE, CHANGER, FERMER, GARDER, PROTEGER, VENDRE, TraderHumain
from collapsar.ecole.regard import (ClasseRegard, Etat, ProfesseurRegard, Regard, avantages_regards,
                                    jouer_comptes)
from collapsar.surveillance import carnet
from collapsar.yeux import faits

AUCUNE_ANNONCE = pd.DataFrame({"temps": pd.to_datetime([]), "devise": []})


@pytest.fixture(autouse=True)
def sans_releve(monkeypatch):
    from collapsar.mains import fiches
    monkeypatch.setattr(fiches, "_reelles", lambda: {})


def _marche(jours=70, graine=0, debut="2022-01-03"):
    t = pd.date_range(debut, periods=jours * 96, freq="15min")
    t = t[t.dayofweek < 5]
    r = np.random.default_rng(graine).normal(0, 0.0007, len(t))
    c = 1.1 * np.exp(np.cumsum(r))
    o = np.r_[c[0], c[:-1]]
    return pd.DataFrame({"time": t, "open": o, "high": np.maximum(o, c) * 1.0002, "low": np.minimum(o, c) * 0.9998,
                         "close": c, "volume": 1.0})


def _classe(**k):
    return ClasseRegard(["EURUSD"], "cpu", {"EURUSD": _marche(**k)}, annonces=AUCUNE_ANNONCE)


# ---------------------------------------------------------------------- l'avantage d'un regard
def test_avantage_regards_espaces():
    r = torch.ones(4, 1)
    v = torch.tensor([[0.5], [0.0], [0.2], [0.0]])
    qui = torch.tensor([[True], [False], [True], [False]])
    fin = torch.zeros(4, 1)
    adv = avantages_regards(r, v, qui, fin, torch.tensor([0.3]), gamma=0.5, lam=1.0)
    # regard en 2 : 1 + 0,5 x 1 + 0,25 x 0,3 - 0,2 ; regard en 0 : 1 + 0,5 + 0,25 x 0,2 - 0,5 + 0,25 x (regard 2)
    assert adv[2, 0].item() == pytest.approx(1.375)
    assert adv[0, 0].item() == pytest.approx(1.05 + 0.25 * 1.375)
    assert adv[1, 0].item() == 0


def test_fin_de_partie_coupe_l_avenir():
    r = torch.ones(4, 1)
    v = torch.tensor([[0.5], [0.0], [0.2], [0.0]])
    qui = torch.tensor([[True], [False], [True], [False]])
    fin = torch.tensor([[0.0], [1.0], [0.0], [0.0]])
    adv = avantages_regards(r, v, qui, fin, torch.tensor([0.3]), gamma=0.5, lam=1.0)
    assert adv[0, 0].item() == pytest.approx(1.5 - 0.5)      # rien après la fin de sa partie


# ---------------------------------------------------------------------- ses choix deviennent des ordres
def _regard(c, e, geste, position=0.5, stop_on=1.0, stop_dist=0.0, obj_on=1.0, obj_dist=0.0, regard=0.0,
            taille=0.01, risque=0.005, att_dist=0.0, att_limite=1.0, att_duree=math.log(16)):
    """`position` : son signe donne le sens (+ acheter, - vendre, 0 fermer) ; `risque` : part du compte par bougie
    du jour contre elle."""
    B, M = e.comptes.u.shape
    plein = lambda x: torch.full((B, M), float(x))
    sens = ACHETER if position > 0 else VENDRE if position < 0 else FERMER
    choix = {"geste": torch.full((B, M), geste, dtype=torch.long),
             "sens": torch.full((B, M), sens, dtype=torch.long), "taille": plein(math.log(risque)),
             "stop_on": plein(stop_on), "stop_dist": plein(stop_dist), "obj_on": plein(obj_on),
             "obj_dist": plein(obj_dist), "regard": torch.full((B,), float(regard)),
             "att_dist": plein(att_dist), "att_limite": plein(att_limite), "att_duree": plein(att_duree)}
    qui = torch.ones(B, dtype=torch.bool)
    z = torch.zeros(B)
    return Regard(qui, torch.zeros(B, M, dtype=torch.long), None, None, choix, z, z, torch.full((B, M), taille))


def _etat(c, depart=3000):
    e = Etat(c.h, 1)
    e.recommencer(torch.tensor([True]), torch.tensor([depart]))
    return e


def test_achat_avec_stop_dessous_et_objectif_dessus():
    c = _classe()
    e = _etat(c)
    prix = float(c.h.c[3000, 0])
    o = c.ordres(e, _regard(c, e, CHANGER, position=0.5))
    assert o.cible.item() == pytest.approx(0.005 * 100_000 / 0.01, rel=1e-5)    # 0,5 % / bougie du jour de 1 %
    assert o.stop.item() == pytest.approx(prix * 0.99)          # 1 bougie du jour (1 %) sous le prix
    assert o.objectif.item() == pytest.approx(prix * 1.01)


def test_vente_avec_stop_dessus():
    c = _classe()
    e = _etat(c)
    prix = float(c.h.c[3000, 0])
    o = c.ordres(e, _regard(c, e, CHANGER, position=-0.5, stop_dist=math.log(2), obj_on=0.0))
    assert o.cible.item() < 0
    assert o.stop.item() == pytest.approx(prix * 1.02)
    assert o.objectif.item() == 0.0                             # 0 = aucun objectif


def test_fermer_vise_zero_sans_protections():
    c = _classe()
    e = _etat(c)
    rg = _regard(c, e, CHANGER, position=0.5)
    c.avancer(e, c.ordres(e, rg), rg)
    assert e.comptes.u.item() > 0
    o = c.ordres(e, _regard(c, e, CHANGER, position=0.0))
    assert o.cible.item() == 0.0 and math.isnan(o.stop.item())


def test_ordre_limite_a_l_avance():
    c = _classe()
    e = _etat(c)
    prix = float(c.h.c[3000, 0])
    o = c.ordres(e, _regard(c, e, ATTENDRE, position=0.5, att_dist=0.0, att_limite=1.0, att_duree=math.log(16)))
    assert int(o.attente_type) == 1, "ordre limite"
    assert float(o.attente_prix) == pytest.approx(prix * 0.99), "acheter plus bas : une bougie du jour (1 %) sous le prix"
    assert float(o.attente_montant) > 0 and int(o.attente_duree) == 16
    assert math.isnan(o.cible.item()), "pas d'ordre au marché"
    o = c.ordres(e, _regard(c, e, ATTENDRE, position=-0.5, att_limite=0.0))
    assert int(o.attente_type) == 2 and float(o.attente_prix) == pytest.approx(prix * 0.99), "vendre si ça casse en dessous"


def test_annuler_un_ordre_a_l_avance():
    c = _classe()
    e = _etat(c)
    o = c.ordres(e, _regard(c, e, ATTENDRE, position=0.0))
    assert int(o.attente_type) == -1


def test_charger_un_eleve_d_avant_les_ordres_a_l_avance():
    neuf = TraderHumain()
    ancien = {k: v.clone() for k, v in neuf.state_dict().items() if ".attente." not in k}
    ancien["decisions.geste.weight"] = ancien["decisions.geste.weight"][:3] + 1.0
    ancien["decisions.geste.bias"] = torch.tensor([3.0, 2.0, 1.0])
    ancien["decisions.log_ecart"] = torch.tensor([-2.0, -0.1, -0.2, -0.3])
    a = TraderHumain()
    a.charger(ancien)
    assert torch.equal(a.decisions.geste.bias[:3], torch.tensor([3.0, 2.0, 1.0]))
    assert a.decisions.geste.bias[3].item() == -1.0 and a.decisions.log_ecart[0].item() == -2.0


def test_garder_ne_touche_a_rien():
    c = _classe()
    e = _etat(c)
    o = c.ordres(e, _regard(c, e, GARDER))
    assert math.isnan(o.cible.item()) and math.isnan(o.stop.item()) and math.isnan(o.objectif.item())


def test_proteger_ne_change_pas_la_position():
    c = _classe()
    e = _etat(c)
    rg = _regard(c, e, CHANGER, position=0.5, stop_on=0.0, obj_on=0.0)
    c.avancer(e, c.ordres(e, rg), rg)
    u = e.comptes.u.item()
    assert u > 0 and math.isnan(e.comptes.stop.item())
    rg = _regard(c, e, PROTEGER, position=-0.9)
    c.avancer(e, c.ordres(e, rg), rg)
    assert e.comptes.u.item() == u and not math.isnan(e.comptes.stop.item())


# ---------------------------------------------------------------------- regards et réveils
def test_elle_revient_a_l_heure_choisie():
    c = _classe()
    e = _etat(c)
    rg = _regard(c, e, GARDER, regard=math.log(12))
    c.noter_regard(e, rg)
    assert e.prochain.item() == 3000 + 12 and not e.reveil.item()


def test_stop_touche_la_reveille():
    c = _classe()
    e = _etat(c)
    rg = _regard(c, e, CHANGER, position=0.5, stop_dist=-3.0, obj_on=0.0, regard=math.log(400), taille=0.002)
    c.noter_regard(e, rg)
    c.avancer(e, c.ordres(e, rg), rg)
    for _ in range(300):
        if e.comptes.u.item() == 0:
            break
        c.avancer(e, Ordres_vides(), None)
    assert e.comptes.u.item() == 0, "le stop très serré aurait dû être touché"
    assert e.reveil.item(), "une position fermée sans elle la réveille"


def Ordres_vides():
    from collapsar.mains.simulateur import Ordres
    return Ordres()


# ---------------------------------------------------------------------- une vraie petite leçon
def test_une_lecon_complete_et_un_controle():
    torch.manual_seed(0)
    c = _classe()
    agent = TraderHumain()
    debut, fin = c.h.temps[0], c.h.temps[-1]
    prof = ProfesseurRegard([c], agent, parties=8, pas=60, paquet=64, epoques=1, de=debut, jusqua=fin, duree=300)
    jeu = prof.jouer()
    assert jeu["regards_par_jour"] > 0
    appris = prof.apprendre()
    assert all(np.isfinite(v) for v in appris.values())
    notes = []
    r = jouer_comptes(c, agent, torch.tensor([3000, 3100]), duree=200, carnet=notes)
    assert 0 <= r["murs_touches_pct"] <= 100 and r["regards_par_jour"] > 0
    assert notes and notes[0]["type"] == "regard"


def test_la_taille_d_un_ordre_a_l_avance_jamais_execute_n_est_pas_apprise():
    """15/10 : un ordre à l'avance qui ne s'exécute jamais n'a rien changé au compte ; apprendre sa taille ne serait
    que du bruit (l'élève grossissait). Ordre stop d'achat très loin -> jamais exécuté ; tout près -> exécuté."""
    from collapsar.cerveau.humain import ATT_MAX, ATT_MIN, ATTENDRE
    c = _classe()
    debut, fin = c.h.temps[0], c.h.temps[-1]
    sans = {}
    for nom, distance in (("loin", ATT_MAX), ("pres", ATT_MIN)):
        torch.manual_seed(0)
        agent = TraderHumain()
        with torch.no_grad():
            agent.decisions.geste.bias.copy_(torch.tensor([-10.0, -10.0, -10.0, 10.0]))      # ordre à l'avance
            agent.decisions.position.bias[:3] = torch.tensor([-10.0, -10.0, 10.0])          # achat
            agent.decisions.attente.bias.copy_(torch.tensor([distance, -10.0, 3.0]))        # ordre stop, long
            agent.decisions.log_ecart[4] = -3.0
            agent.decisions.regard.bias.fill_(math.log(50))
        prof = ProfesseurRegard([c], agent, parties=4, pas=200, paquet=64, epoques=1, de=debut, jusqua=fin, duree=1000)
        prof.jouer()
        m = prof.memoire
        pose = (m["choix"]["geste"] == ATTENDRE) & (m["choix"]["sens"] != 1)
        assert pose.any()
        sans[nom] = m["sans_taille"][pose].float().mean().item()
        assert all(np.isfinite(v) for v in prof.apprendre().values())
    assert sans["loin"] == 1.0, "jamais exécuté : taille jamais apprise"
    assert sans["pres"] < 0.5, "exécuté : taille apprise"


# ---------------------------------------------------------------------- 15/10 : ce qui la réveille avant l'heure
def test_elle_revient_au_plus_tard_dans_4_heures():
    assert int(TraderHumain.delai(torch.tensor(10.0))) == 16 and int(TraderHumain.delai(torch.tensor(0.0))) == 1
    assert int(TraderHumain.duree_attente(torch.tensor(10.0))) == 480, "un ordre à l'avance peut durer 5 jours"


def _attendre_reveil(c, e, bougies=16):
    from collapsar.mains.simulateur import Ordres
    for k in range(bougies):
        c.avancer(e, Ordres(), None)
        if bool(e.reveil[0]):
            return k + 1
    return None


def test_son_alerte_de_prix_la_reveille():
    c = _classe()
    e = _etat(c)
    e.reveil[:] = False
    rg = _regard(c, e, GARDER, regard=math.log(16))
    rg.choix["alerte"] = torch.full((1, 1, 2), -3.0)              # alertes tout près (1/20 de bougie du jour)
    c.noter_regard(e, rg)
    k = _attendre_reveil(c, e)
    assert k is not None and int(e.raison[0]) == 3
    note_texte = carnet.messages_regard({"type": "regard", "temps": pd.Timestamp("2022-03-01 10:00"),
                                         "retour": pd.Timestamp("2022-03-01 12:00"), "compte_pct": 0.0,
                                         "mur_jour_pct": 5.0, "reveil": "une alerte de prix",
                                         "gestes": [{"marche": "EURUSD", "geste": CHANGER, "position_dollars": 1e5,
                                                     "prix": 1.1, "stop": None, "objectif": None}]})[0][1]
    assert "Réveillée par une alerte de prix" in note_texte


def test_alertes_lointaines_et_marche_calme_elle_dort():
    c = _classe()
    e = _etat(c)
    e.reveil[:] = False
    rg = _regard(c, e, GARDER, regard=math.log(16), taille=0.05)
    rg.choix["alerte"] = torch.full((1, 1, 2), 1.1)               # 3 bougies du jour : loin
    c.noter_regard(e, rg)
    assert _attendre_reveil(c, e, 15) is None


def test_un_gros_mouvement_la_reveille():
    c = _classe()
    e = _etat(c)
    e.reveil[:] = False
    rg = _regard(c, e, GARDER, regard=math.log(16), taille=1e-5)   # « une bougie du jour » minuscule
    c.noter_regard(e, rg)                                         # (et pas d'alerte de prix)
    assert _attendre_reveil(c, e) is not None and int(e.raison[0]) == 4


def test_une_annonce_importante_la_reveille_15_minutes_avant():
    m = _marche()
    annonces = pd.DataFrame({"temps": [m["time"].iloc[3010] + pd.Timedelta(minutes=15)], "devise": ["USD"]})
    c = ClasseRegard(["EURUSD"], "cpu", {"EURUSD": m}, annonces=annonces)
    e = _etat(c)
    e.reveil[:] = False
    rg = _regard(c, e, GARDER, regard=math.log(16), taille=0.05)
    rg.choix["alerte"] = torch.full((1, 1, 2), 1.1)
    c.noter_regard(e, rg)
    k = _attendre_reveil(c, e)
    assert k is not None and int(e.raison[0]) == 5 and int(e.comptes.t[0]) >= 3008


def test_ses_trades_mesures_en_r():
    """Stop à 1 bougie du jour, objectif à 2 : objectif prévu ~2 R ; gagnants en positif, perdants vers -1 R au plus
    (elle rachète à chaque regard et replace ses protections : les sorties s'écartent un peu du plan)."""
    c = _classe(jours=120)
    agent = TraderHumain()
    with torch.no_grad():
        agent.decisions.geste.bias.copy_(torch.tensor([-10.0, -10.0, 10.0, -10.0]))
        agent.decisions.position.bias[:3] = torch.tensor([-10.0, -10.0, 10.0])
        agent.decisions.protections.bias.copy_(torch.tensor([10.0, 0.0, 10.0, math.log(2.0)]))
        agent.decisions.alerte.bias.fill_(1.1)
    r = jouer_comptes(c, agent, torch.tensor([3000, 4000, 5000]), duree=3000)
    assert r["trades_en_r"] > 5
    assert r["objectif_prevu_r"] == pytest.approx(2.0, rel=0.1)
    assert 0.3 < r["gain_moyen_r"] < 2.3 and -1.5 < r["perte_moyenne_r"] < 0
    note = {"type": "regard", "temps": pd.Timestamp("2026-10-14 15:00"), "retour": pd.Timestamp("2026-10-14 17:00"),
            "compte_pct": 0.0, "mur_jour_pct": 5.0,
            "gestes": [{"marche": "EURUSD", "geste": CHANGER, "position_dollars": 1e5, "prix": 1.1000, "stop": 1.0950,
                        "objectif": 1.1100}]}
    assert "Objectif : 1,1100 (2,0 R)" in carnet.messages_regard(note)[0][1]


def test_elle_ne_regarde_pas_entre_deux_regards():
    """Délai choisi de 16 bougies (le plus long depuis le 15/10), alertes lointaines, sans hasard : chaque compte
    regarde au départ puis toutes les 16 bougies (0, 16, ..., 144 : 10 regards en 150 bougies)."""
    c = _classe()
    agent = TraderHumain()
    with torch.no_grad():
        agent.decisions.regard.bias.fill_(math.log(16))
        agent.decisions.alerte.bias.fill_(1.1)
        agent.decisions.log_ecart[6:8] = -3.0
        agent.decisions.log_ecart[3] = -3.0
        agent.decisions.geste.bias.copy_(torch.tensor([10.0, -10.0, -10.0, -10.0]))      # garde toujours
    debut, fin = c.h.temps[0], c.h.temps[-1]
    prof = ProfesseurRegard([c], agent, parties=4, pas=150, paquet=64, epoques=1, de=debut, jusqua=fin, duree=1000)
    jeu = prof.jouer()
    assert jeu["regards_par_jour"] == pytest.approx(4 * 10 / (150 * 4 / 96), rel=0.01)


# ---------------------------------------------------------------------- les faits objectifs
def test_seances_ouvertes():
    # 17h serveur un mardi d'hiver = 10h à New York, 15h à Londres, minuit à Tokyo
    s = faits.seances(pd.DatetimeIndex([pd.Timestamp("2022-01-11 16:45")]))
    assert s.tolist() == [[0.0, 1.0, 1.0]]


def test_calendrier_heures_avant_et_depuis():
    annonces = pd.DataFrame({"temps": pd.to_datetime(["2022-01-11 15:30", "2022-01-12 15:30"]),
                             "devise": ["USD", "JPY"]})
    t = pd.DatetimeIndex([pd.Timestamp("2022-01-11 13:15")])            # décision à 13h30 : 2 h avant
    cal = faits.calendrier(t, ["EURUSD", "XAUUSD", "GBPCHF"], annonces)
    assert cal[0, 0, 0] == pytest.approx(2 / 48) and cal[0, 0, 2] == pytest.approx(0.1)
    assert cal[0, 1, 0] == pytest.approx(2 / 48)                        # l'or est coté en dollars
    assert cal[0, 2, 0] == 1.0 and cal[0, 2, 2] == 0.0                  # rien pour la livre et le franc suisse


# ---------------------------------------------------------------------- le carnet de bord
def test_carnet_au_format_valide():
    note = {"type": "regard", "temps": pd.Timestamp("2026-10-14 15:00"), "retour": pd.Timestamp("2026-10-19 15:00"),
            "compte_pct": 1.2, "mur_jour_pct": 4.3,
            "gestes": [{"marche": "EURUSD", "geste": CHANGER, "position_dollars": 200_000.0, "prix": 1.08,
                        "stop": 1.0773, "objectif": 1.0910}]}
    (titre, texte), = carnet.messages_regard(note)
    assert titre == "COLLAPSAR — Achat EURUSD"
    assert "Risque : 0,5 % du compte · Stop : 1,0773 · Objectif : 1,0910" in texte
    assert "Je garde et je reviens dans 5 jours : lundi 19/10 vers 14h" in texte
    assert "Compte : +1,2 % · Distance au mur du jour : 4,3 %" in texte
