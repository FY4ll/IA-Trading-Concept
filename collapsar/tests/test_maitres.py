"""Les maîtres : lecture des historiques réels (format commun) et juge (15/10/2026)."""
import numpy as np
import pandas as pd

from collapsar.maitres.juge import juger_standard
from collapsar.maitres.persistance import bilan, moities
from collapsar.maitres.trades import lire_hyperliquid, lire_ostium


def _ordre(i, trade, action, prix, t, collat, envoye=0, pct=10000, achat=True, trader="0xa", paire="EURUSD"):
    return {"id": i, "tradeID": trade, "trader": trader, "isBuy": achat, "orderType": "Market", "orderAction": action,
            "price": int(prix * 1e18), "executedAt": t, "collateral": int(collat * 1e6), "leverage": 2000,
            "notional": int(collat * 20 * 1e6), "closePercent": pct, "profitPercent": 0, "totalProfitPercent": 0,
            "amountSentToTrader": int(envoye * 1e6), "paire": paire}


def test_ostium_un_trade_par_ouverture_fermeture(tmp_path):
    f = tmp_path / "ordres.csv"
    pd.DataFrame([
        _ordre(1, 10, "Open", 1.10, 1_725_000_000, 100),
        _ordre(2, 10, "Close", 1.11, 1_725_003_600, 30, envoye=36, pct=3000),     # sortie partielle : +6 $
        _ordre(3, 10, "StopLoss", 1.09, 1_725_007_200, 70, envoye=56),            # le reste sur le stop : -14 $
        _ordre(4, 11, "Open", 2000.0, 1_725_000_000, 50, achat=False, paire="XAUUSD"),
        _ordre(5, 11, "Liquidation", 2100.0, 1_725_100_000, 50, envoye=0, paire="XAUUSD"),
        _ordre(6, 12, "Open", 1.2, 1_725_000_000, 10),                             # encore ouvert : ignoré
    ]).to_csv(f, index=False)
    t = lire_ostium(f).sort_values("marche").reset_index(drop=True)
    assert list(t["marche"]) == ["EURUSD", "XAUUSD"]
    eur, xau = t.iloc[0], t.iloc[1]
    assert eur["gain"] == 6 - 14 and eur["sens"] == 1 and eur["stop"] == 1.09 and np.isnan(eur["objectif"])
    assert eur["prix_entree"] == 1.10 and eur["levier"] == 20 and eur["volume"] == 2000
    assert xau["liquide"] and xau["sens"] == -1 and xau["gain"] == -50
    assert eur["debut"] < eur["fin"]


def test_hyperliquid_de_la_position_nulle_a_la_position_nulle(tmp_path):
    f = tmp_path / "0xb.csv"
    pd.DataFrame({"coin": ["xyz:GOLD"] * 3, "px": [2000, 2010, 2020], "sz": [1, 1, 2], "side": ["B", "B", "A"],
                  "time": [1_725_000_000_000, 1_725_000_060_000, 1_725_000_120_000],
                  "startPosition": [0, 1, 2], "closedPnl": [0, 0, 30], "fee": [1, 1, 2]}).to_csv(f, index=False)
    t = lire_hyperliquid(f)
    assert len(t) == 1 and t["marche"].iloc[0] == "XAUUSD" and t["sens"].iloc[0] == 1 and t["gain"].iloc[0] == 26


def _ev(bloc, ev, compte="0xa", marge=None, taille=None, prix=None, frais=0.0, delta=None, tx=None):
    return {"generation": "v2", "bloc": bloc, "heure": 1_700_000_000 + bloc * 3600, "tx": tx or f"t{bloc}",
            "index_log": 1, "evenement": ev, "compte": compte, "id_position": 1, "marge": marge, "taille": taille,
            "taille_ordre": None, "prix": prix, "frais": frais, "delta_marge": delta, "liquidateur": None}


def test_synthetix_gain_par_la_marge_et_liquidation(tmp_path):
    from collapsar.maitres.synthetix import SUJETS, decoder, keccak256
    from collapsar.maitres.trades import lire_synthetix
    assert keccak256(b"").hex() == "c5d2460186f7233c927e7db2dcc703c0e500b653ca82273b7bfad8045d85a470"
    assert any(n == "PositionModified" for n, _ in SUJETS.values())
    f = tmp_path / "evenements_XAU.csv"
    pd.DataFrame([
        _ev(1, "MarginTransferred", delta=1000.0), _ev(1, "PositionModified", marge=1000.0, taille=0.0, prix=2000.0),
        _ev(2, "PositionModified", marge=998.0, taille=1.0, prix=2000.0, frais=2.0),          # achat 1 once
        _ev(3, "PositionModified", marge=1006.0, taille=2.0, prix=2010.0, frais=2.0),         # +1 once (+10 réalisés)
        _ev(4, "PositionModified", marge=1022.0, taille=0.0, prix=2020.0, frais=4.0),         # tout fermé (+20)
        _ev(5, "MarginTransferred", delta=-1022.0), _ev(5, "PositionModified", marge=0.0, taille=0.0, prix=2020.0),
        _ev(6, "MarginTransferred", delta=500.0), _ev(6, "PositionModified", marge=500.0, taille=0.0, prix=2000.0),
        _ev(7, "PositionModified", marge=499.0, taille=-1.0, prix=2000.0, frais=1.0),         # vente
        _ev(8, "PositionLiquidated", taille=-1.0, prix=2450.0, frais=5.0),                    # liquidée
        _ev(9, "PositionModified", compte="0xb", marge=99.0, taille=0.5, prix=2000.0, frais=1.0),  # encore ouvert
    ]).to_csv(f, index=False)
    h = lambda bloc: 1_700_000_000 + bloc * 3600
    o = lambda genre, bloc, i, typ=None, prix=None, rempli=None, marche="XAU": {
        "genre": genre, "bloc": bloc, "heure": h(bloc) - 30, "tx": f"o{bloc}{i}{genre}", "index_log": 0,
        "contrat": "0xk", "compte": "0xa", "id_ordre": i, "marche": marche, "type": typ, "taille_ordre": -1.0,
        "prix_cible": prix, "reduction_seule": True, "prix_rempli": rempli}
    pd.DataFrame([o("place", 3, 1, 1, 1990.0), o("place", 3, 2, 0, 2030.0), o("place", 3, 3, 1, 1900.0, marche="XAG"),
                  o("rempli", 4, 2, rempli=2020.0, marche=None)]).to_csv(tmp_path / "ordres_conditionnels.csv",
                                                                         index=False)
    t = lire_synthetix(f).sort_values("debut").reset_index(drop=True)
    assert len(t) == 2 and (t["marche"] == "XAUUSD").all()
    assert t.iloc[0]["stop"] == 1990.0 and t.iloc[0]["objectif"] == 2030.0 and t.iloc[0]["sortie"] == "objectif"
    assert np.isnan(t.iloc[1]["stop"]) and t.iloc[1]["sortie"] == "liquidation"
    a, v = t.iloc[0], t.iloc[1]
    assert a["sens"] == 1 and abs(a["gain"] - 22.0) < 1e-9 and abs(a["prix_entree"] - 2005.0) < 1e-9
    assert abs(a["prix_sortie"] - 2020.0) < 1e-9 and abs(a["volume"] - 4010.0) < 1e-9 and not a["liquide"]
    assert abs(a["levier"] - 2000 / 998) < 1e-9
    assert v["sens"] == -1 and v["liquide"] and abs(v["gain"] + 500.0) < 1e-9 and v["prix_sortie"] == 2450.0
    # décodage d'un vrai événement de la chaîne (format : indexés d'abord, puis les données)
    mot = lambda x: format(x % (1 << 256), "064x")
    sujet = next(k for k, (n, c) in SUJETS.items() if n == "PositionModified" and len(c) == 9)
    log = {"topics": [sujet, "0x" + mot(7), "0x" + "0" * 24 + "ab" * 20], "blockNumber": "0x10",
           "blockTimestamp": "0x64", "transactionHash": "0x1", "logIndex": "0x2", "removed": False,
           "data": "0x" + "".join(mot(int(x * 1e18)) for x in (998, -1.5, -1.5, 2000, 0, 2, 0))}
    d = decoder(log, "v2")
    assert d["compte"] == "0x" + "ab" * 20 and d["taille"] == -1.5 and d["prix"] == 2000 and d["marge"] == 998
    assert d["frais"] == 2 and d["id_position"] == 7 and d["heure"] == 100


def _maitres(n_maitres, talent, rng):
    lignes = []
    for m in range(n_maitres):
        a = talent[m]
        for k in range(100):
            lignes.append({"maitre": f"m{m}", "source": "essai", "marche": "EURUSD", "debut": pd.Timestamp("2025-01-01") + pd.Timedelta(hours=k),
                           "fin": pd.Timestamp("2025-01-01") + pd.Timedelta(hours=k + 1), "volume": 1000.0,
                           "gain": float(rng.normal(a, 1.0)), "liquide": False, "levier": 10.0})
    return pd.DataFrame(lignes)


def test_le_talent_qui_dure_se_voit_et_le_hasard_non():
    rng = np.random.default_rng(0)
    vrai = _maitres(200, np.r_[np.full(20, 0.4), np.zeros(180)], rng)
    b = bilan(moities(vrai), "force")
    assert b["force_2de_moitie_retenus"] > b["force_2de_moitie_autres"] + 1, "les vrais talents restent bons"
    hasard = _maitres(200, np.zeros(200), rng)
    b = bilan(moities(hasard), "force")
    assert abs(b["force_2de_moitie_retenus"] - b["force_2de_moitie_autres"]) < 0.6, "des chanceux ne le restent pas"


def test_juge_rapporte_a_la_taille():
    t = pd.DataFrame({"maitre": "m", "source": "s", "marche": "EURUSD", "debut": pd.Timestamp("2025-01-01"),
                      "fin": pd.Timestamp("2025-01-02"), "liquide": False, "levier": 1.0,
                      "gain": [100.0] + [-1.0] * 40, "volume": [100_000.0] + [100.0] * 40})
    en_dollars = juger_standard(t).iloc[0]["force"]
    a_la_taille = juger_standard(t, rapporte_a_la_taille=True).iloc[0]["force"]
    assert en_dollars > 0 > a_la_taille, "un seul gros trade chanceux ne fait pas un maître"


def test_un_programme_qui_ferme_dans_la_seconde_n_est_pas_un_maitre():
    debut = pd.Timestamp("2025-01-01") + pd.to_timedelta(np.arange(300), "h")
    t = pd.DataFrame({"maitre": "rapide", "source": "s", "marche": "XAUUSD", "debut": debut, "fin": debut,
                      "liquide": False, "levier": 50.0, "gain": 1.0 + np.random.default_rng(0).normal(0, 0.1, 300),
                      "volume": 100.0})
    v = juger_standard(t).iloc[0]
    assert v["force"] > 3 and not v["maitre_retenu"]
    lent = t.assign(maitre="lent", fin=debut + pd.Timedelta(hours=2))
    assert juger_standard(lent).iloc[0]["maitre_retenu"]
