"""Les mains sur le compte démo Tradeco (direct/tradeco.py), testées sur un FAUX MetaTrader (15/10/2026)."""
from types import SimpleNamespace as NS

import pandas as pd
import pytest

from collapsar.direct import tradeco

MARDI = pd.Timestamp("2026-10-13 15:00")


class FauxMT5:
    TRADE_ACTION_DEAL, TRADE_ACTION_PENDING, TRADE_ACTION_SLTP, TRADE_ACTION_REMOVE = 1, 5, 6, 8
    ORDER_TYPE_BUY, ORDER_TYPE_SELL = 0, 1
    ORDER_TYPE_BUY_LIMIT, ORDER_TYPE_SELL_LIMIT, ORDER_TYPE_BUY_STOP, ORDER_TYPE_SELL_STOP = 2, 3, 4, 5
    ORDER_TIME_SPECIFIED = 2
    POSITION_TYPE_BUY, POSITION_TYPE_SELL = 0, 1
    ORDER_FILLING_FOK, ORDER_FILLING_IOC, ORDER_FILLING_RETURN = 0, 1, 2
    TRADE_RETCODE_DONE = 10009
    ACCOUNT_TRADE_MODE_DEMO = 0

    def __init__(self):
        self.positions, self.envois, self.ticket, self.algo, self.ordres = [], [], 100, True, []
        self.bid, self.ask = 1.1000, 1.1001
        self.capitaux, self.solde = 100_000.0, 100_000.0
        self.infos = {s: NS(trade_contract_size=100_000.0 if s in ("EURUSD", "USDJPY") else 100.0 if s == "XAUUSD" else 1.0,
                            volume_step=0.01, volume_min=0.01 if s != "US500Cash" else 0.1, volume_max=100.0, digits=5,
                            point=0.00001, filling_mode=2) for s in tradeco.SYMBOLES.values()}

    def symbol_info(self, s):
        return self.infos[s]

    def symbol_info_tick(self, s):
        return NS(bid=self.bid, ask=self.ask)

    def orders_get(self, symbol=None):
        return [o for o in self.ordres if symbol is None or o.symbol == symbol]

    def executer_ordre(self, o):
        """Tradeco exécute l'ordre à l'avance : il devient une position."""
        self.ordres.remove(o)
        self.ticket += 1
        self.positions.append(NS(ticket=self.ticket, symbol=o.symbol, volume=o.volume_current, magic=o.magic,
                                 type=0 if o.type in (2, 4) else 1, sl=0.0, tp=0.0))

    def positions_get(self, symbol=None):
        return [p for p in self.positions if symbol is None or p.symbol == symbol]

    def account_info(self):
        return NS(equity=self.capitaux, balance=self.solde, login=1, trade_mode=0)

    def last_error(self):
        return (1, "ok")

    def terminal_info(self):
        return NS(trade_allowed=self.algo)

    def order_send(self, d):
        self.envois.append(d)
        if d["action"] == self.TRADE_ACTION_PENDING:
            self.ticket += 1
            self.ordres.append(NS(ticket=self.ticket, symbol=d["symbol"], volume_current=d["volume"], type=d["type"],
                                  price_open=d["price"], magic=d["magic"], expiration=d["expiration"]))
        elif d["action"] == self.TRADE_ACTION_REMOVE:
            self.ordres = [o for o in self.ordres if o.ticket != d["order"]]
        elif d["action"] == self.TRADE_ACTION_SLTP:
            p = next(p for p in self.positions if p.ticket == d["position"])
            p.sl, p.tp = d["sl"], d["tp"]
        elif "position" in d:
            self.positions = [p for p in self.positions if p.ticket != d["position"]]
        else:
            self.ticket += 1
            self.positions.append(NS(ticket=self.ticket, symbol=d["symbol"], volume=d["volume"], magic=d["magic"],
                                     type=0 if d["type"] == self.ORDER_TYPE_BUY else 1, sl=d["sl"], tp=d["tp"]))
        return NS(retcode=10009, comment="fait")


@pytest.fixture
def faux(monkeypatch, tmp_path):
    f = FauxMT5()
    monkeypatch.setattr(tradeco, "mt5", f)
    monkeypatch.setattr(tradeco, "ETAT", tmp_path / "tradeco.json")
    monkeypatch.setattr(tradeco, "ARRET", tmp_path / "TRADECO_ARRET")
    return f


def _voulu(unites=0.0, stop=float("nan"), objectif=float("nan"), ouverture="2026-10-13 14:00:00", attente=None):
    return {"EURUSD": {"unites": unites, "stop": stop, "objectif": objectif, "ouverture": ouverture, "attente": attente}}


ACHAT_LIMITE = {"genre": 1, "prix": 1.0950, "unites": 100_000.0, "bougies": 40}


def test_ouvre_avec_stop_et_objectif_puis_ne_rouvre_pas_apres_un_stop_chez_le_courtier(faux):
    tradeco.synchroniser(_voulu(250_000, 1.095, 1.11), MARDI)
    (p,) = faux.positions
    assert p.volume == 2.5 and p.type == 0 and p.sl == 1.095 and p.tp == 1.11 and p.magic == tradeco.MAGIC
    faux.positions.clear()                                    # Tradeco l'a fermée sur son stop
    tradeco.synchroniser(_voulu(250_000, 1.095, 1.11), MARDI)
    assert not faux.positions, "même position voulue : on ne la rouvre pas"
    tradeco.synchroniser(_voulu(-100_000, 1.105, ouverture="2026-10-13 15:00:00"), MARDI)
    (p,) = faux.positions
    assert p.type == 1 and p.volume == 1.0, "nouvelle décision (vente) : exécutée"


def test_retournement_et_stop_qui_suit(faux):
    tradeco.synchroniser(_voulu(100_000, 1.09), MARDI)
    tradeco.synchroniser(_voulu(100_000, 1.0950), MARDI)
    assert faux.positions[0].sl == 1.095, "le stop suit celui du compte fictif"
    tradeco.synchroniser(_voulu(-50_000, 1.11, ouverture="2026-10-13 16:00:00"), MARDI)
    (p,) = faux.positions
    assert p.type == 1 and p.volume == 0.5
    tradeco.synchroniser(_voulu(0.0), MARDI)
    assert not faux.positions


def test_ne_touche_jamais_les_positions_des_autres(faux):
    faux.positions.append(NS(ticket=1, symbol="EURUSD", volume=3.0, magic=999, type=0, sl=0.0, tp=0.0))
    tradeco.synchroniser(_voulu(0.0), MARDI)
    assert len(faux.positions) == 1 and faux.positions[0].magic == 999


def test_coupe_circuit_ferme_tout_et_bloque(faux):
    tradeco.synchroniser(_voulu(100_000), MARDI)
    faux.capitaux = 95_400.0                                   # -4,6 % sur la journée
    fait = tradeco.synchroniser(_voulu(100_000), MARDI)
    assert not faux.positions and any("COUPE-CIRCUIT" in f for f in fait)
    faux.capitaux = 100_000.0
    tradeco.synchroniser(_voulu(200_000, ouverture="2026-10-13 18:00:00"), MARDI)
    assert not faux.positions, "après le coupe-circuit : plus aucun ordre"


def test_vendredi_soir_tout_est_ferme(faux):
    tradeco.synchroniser(_voulu(100_000), MARDI)
    tradeco.synchroniser(_voulu(100_000), pd.Timestamp("2026-10-16 22:45"))
    assert not faux.positions
    assert not tradeco.fin_de_semaine(pd.Timestamp("2026-10-16 22:30"))
    assert tradeco.fin_de_semaine(pd.Timestamp("2026-10-17 01:00"))


def test_taille_trop_petite_pour_le_courtier(faux):
    assert tradeco.lots("EURUSD", 400.0) == 0.0
    assert tradeco.lots("US500Cash", -5.0) == -5.0 and tradeco.lots("US500Cash", 0.05) == 0.0
    assert tradeco.lots("XAUUSD", 123.0) == 1.23


def test_bouton_trading_algo_eteint_rien_n_est_tente_puis_tout_se_fait(faux):
    faux.algo = False
    assert tradeco.synchroniser(_voulu(100_000), MARDI) == [tradeco.ALGO_ETEINT] and not faux.envois
    faux.algo = True
    tradeco.synchroniser(_voulu(100_000), MARDI)
    assert len(faux.positions) == 1, "dès que le bouton s'allume, la position voulue est prise"


# ---------------------------------------------------------------------- les ordres à l'avance (15/10)
def test_ordre_limite_pose_dans_metatrader_avec_expiration_puis_annule(faux):
    tradeco.synchroniser(_voulu(attente=ACHAT_LIMITE), MARDI)
    (o,) = faux.ordres
    assert o.type == faux.ORDER_TYPE_BUY_LIMIT and o.price_open == 1.095 and o.volume_current == 1.0
    assert o.expiration == int((MARDI + pd.Timedelta(minutes=15 * 40)).timestamp())
    tradeco.synchroniser(_voulu(attente=ACHAT_LIMITE), MARDI)
    assert len(faux.ordres) == 1, "même ordre voulu : rien de plus"
    tradeco.synchroniser(_voulu(attente=None), MARDI)
    assert not faux.ordres and not faux.positions, "annulé dans le compte fictif : annulé chez Tradeco"


def test_execute_des_deux_cotes_aucun_ordre_en_plus(faux):
    tradeco.synchroniser(_voulu(attente=ACHAT_LIMITE), MARDI)
    faux.executer_ordre(faux.ordres[0])
    n = len(faux.envois)
    tradeco.synchroniser(_voulu(100_000, 1.09, ouverture="2026-10-13 15:15:00"), MARDI)
    (p,) = faux.positions
    assert p.volume == 1.0 and p.sl == 1.09
    assert all(e["action"] == faux.TRADE_ACTION_SLTP for e in faux.envois[n:]), "seul le stop est posé"


def test_execute_chez_tradeco_seulement_garde_puis_ferme_si_l_ordre_fictif_expire(faux):
    tradeco.synchroniser(_voulu(attente=ACHAT_LIMITE), MARDI)
    faux.executer_ordre(faux.ordres[0])                       # le prix Tradeco a touché, pas le fictif
    tradeco.synchroniser(_voulu(attente=ACHAT_LIMITE), MARDI)
    assert len(faux.positions) == 1, "gardée tant que l'ordre fictif vit"
    tradeco.synchroniser(_voulu(attente=None), MARDI)         # l'ordre fictif expire sans s'exécuter
    assert not faux.positions


def test_execute_dans_le_fictif_seulement_pas_d_achat_en_retard(faux):
    tradeco.synchroniser(_voulu(attente=ACHAT_LIMITE), MARDI)
    faux.bid, faux.ask = 1.1050, 1.1051                       # le prix est reparti : Tradeco n'a pas exécuté
    fait = tradeco.synchroniser(_voulu(100_000, ouverture="2026-10-13 15:15:00"), MARDI)
    assert not faux.positions and not faux.ordres
    assert any("pas d'achat en retard" in f for f in fait)


def test_ordre_deja_executable_part_au_marche(faux):
    stop_achat = {"genre": 2, "prix": 1.0990, "unites": 50_000.0, "bougies": 8}   # le prix (1,1001) l'a déjà cassé
    tradeco.synchroniser(_voulu(attente=stop_achat), MARDI)
    assert not faux.ordres and len(faux.positions) == 1 and faux.positions[0].volume == 0.5


def test_fin_de_semaine_annule_aussi_les_ordres(faux):
    tradeco.synchroniser(_voulu(attente=ACHAT_LIMITE), MARDI)
    tradeco.synchroniser(_voulu(attente=ACHAT_LIMITE), pd.Timestamp("2026-10-16 23:00"))
    assert not faux.ordres