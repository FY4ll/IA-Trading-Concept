"""Les MAINS de COLLAPSAR sur le compte DÉMO Tradeco (15/10/2026, ordre du chef de projet : « on voit les positions »).

Principe : la démo à blanc (direct/blanc.py) reste le cerveau et le juge (compte fictif aux frais FTMO) ; ce module
RECOPIE ses positions sur le compte démo Tradeco : même sens, même taille (en lots), même stop et même objectif posés
dans MetaTrader (ils s'y déclenchent seuls, à la seconde près).
- On n'agit que quand la position voulue CHANGE (sa « signature » : sens, taille, heure d'ouverture) : si Tradeco a
  fermé une position sur son stop alors que le compte fictif la garde encore, on ne la rouvre pas ;
- seules nos positions sont touchées (numéro magique) ; compte RÉEL refusé (démo seulement) ;
- coupe-circuit sur le compte Tradeco : -4,5 % sur la journée (depuis minuit à Prague) ou -9 % depuis le départ ->
  tout est fermé, plus aucun ordre (fichier vie/direct/TRADECO_ARRET), message sur le téléphone ;
- vendredi soir (dès 22h45 heure du serveur) : tout est fermé et rien ne s'ouvre avant la réouverture ;
- ordres à l'avance (limite / stop) posés pour de vrai dans MetaTrader, avec expiration (voir synchroniser).
Accès : %USERPROFILE%\\.collapsar\\acces_tradeco.json (numéro et serveur ; le mot de passe reste dans MetaTrader).
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import MetaTrader5 as mt5
import pandas as pd

from collapsar.donnees import marches as dm

TERMINAL = r"C:\Program Files\MetaTrader 5\terminal64.exe"
ACCES = Path.home() / ".collapsar" / "acces_tradeco.json"
DOSSIER = dm.RACINE / "collapsar" / "vie" / "direct"
ETAT = DOSSIER / "tradeco.json"
ARRET = DOSSIER / "TRADECO_ARRET"
SYMBOLES = {"EURUSD": "EURUSD", "USDJPY": "USDJPY", "XAUUSD": "XAUUSD", "USA500IDXUSD": "US500Cash"}
MAGIC = 15102026
COUPE_JOUR, COUPE_TOTAL = 0.045, 0.09
FIN_SEMAINE = (4, 22, 45)            # vendredi 22h45, heure du serveur
ALGO_ETEINT = "bouton « Trading algo » éteint dans MetaTrader : aucun ordre"


def connecter() -> None:
    """MetaTrader sur le compte démo Tradeco (bascule si besoin). Refuse tout compte réel."""
    if not mt5.initialize(path=TERMINAL, timeout=60000):
        raise RuntimeError(f"MetaTrader injoignable : {mt5.last_error()}")
    acces = json.loads(ACCES.read_text(encoding="utf-8"))
    a = mt5.account_info()
    if a is None or a.login != acces["login"]:
        if not mt5.login(acces["login"], server=acces["serveur"], timeout=60000):
            raise RuntimeError(f"connexion Tradeco impossible : {mt5.last_error()}")
        a = mt5.account_info()
    if a is None or a.trade_mode != mt5.ACCOUNT_TRADE_MODE_DEMO:
        raise RuntimeError("compte non démo : aucun ordre (sécurité)")
    for s in SYMBOLES.values():
        mt5.symbol_select(s, True)


def fin_de_semaine(temps_serveur: pd.Timestamp) -> bool:
    j, h, m = FIN_SEMAINE
    t = pd.Timestamp(temps_serveur)
    return t.dayofweek > j or (t.dayofweek == j and (t.hour, t.minute) >= (h, m))


def lots(symbole: str, unites: float) -> float:
    """Unités du compte fictif (onces, euros, points d'indice...) -> lots Tradeco, au pas du courtier (0 si trop petit)."""
    s = mt5.symbol_info(symbole)
    v = abs(unites) / s.trade_contract_size
    v = math.floor(v / s.volume_step + 1e-9) * s.volume_step
    if v < s.volume_min:
        return 0.0
    return round(min(v, s.volume_max), 8) * (1 if unites > 0 else -1)


def nos_positions(symbole: str) -> list:
    return [p for p in (mt5.positions_get(symbol=symbole) or []) if p.magic == MAGIC]


def _remplissage(symbole: str) -> int:
    mode = mt5.symbol_info(symbole).filling_mode
    return mt5.ORDER_FILLING_IOC if mode & 2 else mt5.ORDER_FILLING_FOK if mode & 1 else mt5.ORDER_FILLING_RETURN


def _envoyer(demande: dict) -> tuple[bool, str]:
    r = mt5.order_send(demande)
    if r is None:
        return False, f"pas de réponse ({mt5.last_error()})"
    return r.retcode == mt5.TRADE_RETCODE_DONE, f"code {r.retcode} {r.comment}"


def fermer(p) -> tuple[bool, str]:
    t = mt5.symbol_info_tick(p.symbol)
    achat = p.type == mt5.POSITION_TYPE_BUY
    return _envoyer({"action": mt5.TRADE_ACTION_DEAL, "symbol": p.symbol, "volume": p.volume, "position": p.ticket,
                     "type": mt5.ORDER_TYPE_SELL if achat else mt5.ORDER_TYPE_BUY, "price": t.bid if achat else t.ask,
                     "deviation": 50, "magic": MAGIC, "comment": "COLLAPSAR ferme", "type_filling": _remplissage(p.symbol)})


def _niveau(x) -> float:
    return 0.0 if x is None or (isinstance(x, float) and math.isnan(x)) else float(x)


def ouvrir(symbole: str, volume: float, stop, objectif) -> tuple[bool, str]:
    t = mt5.symbol_info_tick(symbole)
    s = mt5.symbol_info(symbole)
    achat = volume > 0
    prix = t.ask if achat else t.bid
    sl, tp = round(_niveau(stop), s.digits), round(_niveau(objectif), s.digits)
    # un stop / objectif du mauvais côté du prix serait refusé : on ouvre sans lui (le compte fictif l'a refusé aussi)
    if sl and ((achat and sl >= t.bid) or (not achat and sl <= t.ask)):
        sl = 0.0
    if tp and ((achat and tp <= t.bid) or (not achat and tp >= t.ask)):
        tp = 0.0
    return _envoyer({"action": mt5.TRADE_ACTION_DEAL, "symbol": symbole, "volume": abs(volume), "price": prix,
                     "type": mt5.ORDER_TYPE_BUY if achat else mt5.ORDER_TYPE_SELL, "sl": sl, "tp": tp, "deviation": 50,
                     "magic": MAGIC, "comment": "COLLAPSAR", "type_filling": _remplissage(symbole)})


def proteger(p, stop, objectif) -> tuple[bool, str] | None:
    s = mt5.symbol_info(p.symbol)
    sl, tp = round(_niveau(stop), s.digits), round(_niveau(objectif), s.digits)
    t = mt5.symbol_info_tick(p.symbol)
    achat = p.type == mt5.POSITION_TYPE_BUY
    if sl and ((achat and sl >= t.bid) or (not achat and sl <= t.ask)):
        sl = p.sl
    if tp and ((achat and tp <= t.bid) or (not achat and tp >= t.ask)):
        tp = p.tp
    if abs(sl - p.sl) < s.point / 2 and abs(tp - p.tp) < s.point / 2:
        return None
    return _envoyer({"action": mt5.TRADE_ACTION_SLTP, "symbol": p.symbol, "position": p.ticket, "sl": sl, "tp": tp,
                     "magic": MAGIC})


def _etat() -> dict:
    return json.loads(ETAT.read_text(encoding="utf-8")) if ETAT.exists() else {}


def _jour_prague() -> str:
    return pd.Timestamp.now(tz="Europe/Prague").strftime("%Y-%m-%d")


def coupe_circuit(etat: dict) -> str | None:
    """Rend la raison si le compte Tradeco a perdu 4,5 % sur la journée ou 9 % depuis le départ."""
    a = mt5.account_info()
    jour = _jour_prague()
    etat.setdefault("depart", a.equity)
    if etat.get("jour") != jour:
        etat["jour"], etat["solde_minuit"] = jour, a.balance
    if a.equity <= etat["solde_minuit"] * (1 - COUPE_JOUR):
        return f"-{COUPE_JOUR * 100:.1f} % sur la journée"
    if a.equity <= etat["depart"] * (1 - COUPE_TOTAL):
        return f"-{COUPE_TOTAL * 100:.0f} % depuis le départ"
    return None


def nos_ordres(symbole: str) -> list:
    return [o for o in (mt5.orders_get(symbol=symbole) or []) if o.magic == MAGIC]


def annuler(o) -> tuple[bool, str]:
    return _envoyer({"action": mt5.TRADE_ACTION_REMOVE, "order": o.ticket, "magic": MAGIC})


def poser(symbole: str, genre: int, prix: float, volume: float, expiration: pd.Timestamp) -> tuple[bool, str]:
    """Ordre à l'avance dans MetaTrader : `genre` 1 = limite (acheter plus bas / vendre plus haut), 2 = stop (cassure).
    S'il est DÉJÀ exécutable au prix du moment (le prix a passé le niveau), il part au marché : c'est ce que ferait
    MetaTrader (une limite d'achat au-dessus du prix s'exécute tout de suite, un stop déjà cassé aussi)."""
    s, t = mt5.symbol_info(symbole), mt5.symbol_info_tick(symbole)
    achat = volume > 0
    prix = round(prix, s.digits)
    if genre == 1:
        type_ = mt5.ORDER_TYPE_BUY_LIMIT if achat else mt5.ORDER_TYPE_SELL_LIMIT
        executable = (achat and t.ask <= prix) or (not achat and t.bid >= prix)
    else:
        type_ = mt5.ORDER_TYPE_BUY_STOP if achat else mt5.ORDER_TYPE_SELL_STOP
        executable = (achat and t.ask >= prix) or (not achat and t.bid <= prix)
    if executable:
        return ouvrir(symbole, volume, None, None)
    return _envoyer({"action": mt5.TRADE_ACTION_PENDING, "symbol": symbole, "volume": abs(volume), "type": type_,
                     "price": prix, "sl": 0.0, "tp": 0.0, "type_time": mt5.ORDER_TIME_SPECIFIED,
                     "expiration": int(pd.Timestamp(expiration).timestamp()), "magic": MAGIC,
                     "comment": "COLLAPSAR à l'avance", "type_filling": mt5.ORDER_FILLING_RETURN})


def _proche(a: float, b: float, symbole: str) -> bool:
    """Deux tailles égales à l'arrondi près (le compte fictif et le courtier n'arrondissent pas les lots pareil)."""
    s = mt5.symbol_info(symbole)
    return abs(a - b) <= max(1.01 * s.volume_step, 0.05 * max(abs(a), abs(b)))


def _tenu(ps) -> float:
    return sum(p.volume * (1 if p.type == mt5.POSITION_TYPE_BUY else -1) for p in ps)


def _tout_fermer(raison: str) -> list[str]:
    fait = []
    for sym in SYMBOLES.values():
        for o in nos_ordres(sym):
            fait.append(f"{sym} : ordre à l'avance annulé ({raison}) -> {annuler(o)[1]}")
        for p in nos_positions(sym):
            fait.append(f"{sym} fermée ({raison}) : {fermer(p)[1]}")
    return fait


def synchroniser(voulu: dict, temps_serveur: pd.Timestamp) -> list[str]:
    """`voulu` : {marché: {"unites", "stop", "objectif", "ouverture", "attente"}} (état final du compte fictif) ;
    "attente" = None ou {"genre": 1 limite / 2 stop, "prix", "unites", "bougies" (durée restante)}.
    Rend la liste de ce qui a été fait (pour le journal). À appeler MetaTrader déjà connecté (connecter()).

    Ordres à l'avance (15/10) : posés pour de vrai dans MetaTrader (on les voit, exécution au prix exact, expiration
    à l'heure choisie par l'IA), annulés quand le compte fictif les annule. Les deux prix diffèrent un peu, d'où :
    - exécuté chez Tradeco mais pas dans le compte fictif : la position est gardée tant que l'ordre fictif vit ;
      s'il disparaît sans s'exécuter (annulé, expiré), la position Tradeco qui en vient est fermée ;
    - exécuté dans le compte fictif mais pas chez Tradeco : on n'achète PAS en retard au marché ; l'ordre Tradeco
      est annulé."""
    etat = _etat()
    if ARRET.exists():
        return ["coupe-circuit actif : aucun ordre"]
    if not mt5.terminal_info().trade_allowed:
        # bouton « Trading algo » éteint dans MetaTrader : rien n'est tenté (ni noté : tout se fera quand il s'allume)
        return [ALGO_ETEINT]
    raison = coupe_circuit(etat)
    if raison or fin_de_semaine(temps_serveur):
        fait = _tout_fermer(f"coupe-circuit {raison}" if raison else "fin de semaine")
        if raison:
            ARRET.write_text(raison, encoding="utf-8")
            fait.append(f"COUPE-CIRCUIT : {raison}")
        etat["signatures"], etat["attentes"] = {}, {}
        _sauver(etat)
        return fait
    fait = []
    signatures = etat.setdefault("signatures", {})
    attentes = etat.setdefault("attentes", {})
    for marche, sym in SYMBOLES.items():
        v = voulu.get(marche, {"unites": 0.0})
        cible = lots(sym, v["unites"]) if v["unites"] else 0.0
        sig = f"{cible:+.2f}@{v.get('ouverture')}" if cible else "0"
        att = v.get("attente")
        att_lots = lots(sym, att["unites"]) if att else 0.0
        sig_att = f"{att['genre']}|{att['prix']:.10g}|{att_lots:+.2f}" if att and att_lots else "0"
        avait_attente = attentes.get(marche, "0") != "0"
        disparue = avait_attente and sig_att == "0"
        ps = nos_positions(sym)
        tenu = _tenu(ps)

        # 1. la position
        if sig != signatures.get(marche):
            remplie_fictif_seul = disparue and cible != 0 and _proche(tenu, 0.0, sym)
            if remplie_fictif_seul:
                fait.append(f"{sym} : ordre à l'avance exécuté dans le compte fictif mais pas chez Tradeco -> "
                            "pas d'achat en retard")
            elif not _proche(tenu, cible, sym):
                if ps and (cible == 0 or math.copysign(1, cible) != math.copysign(1, tenu) or abs(cible) < abs(tenu)):
                    for p in ps:
                        fait.append(f"{sym} : fermeture {p.volume} lot(s) -> {fermer(p)[1]}")
                    tenu = 0.0
                reste = round(cible - tenu, 8)
                if abs(reste) > 0:
                    ok, msg = ouvrir(sym, reste, v.get("stop"), v.get("objectif"))
                    fait.append(f"{sym} : {'achat' if reste > 0 else 'vente'} {abs(reste)} lot(s) -> {msg}")
            signatures[marche] = sig
        elif disparue and cible == 0 and ps:
            # l'ordre fictif est parti sans s'exécuter : la position Tradeco née de son ordre est fermée
            for p in ps:
                fait.append(f"{sym} : ordre à l'avance annulé ou expiré dans le compte fictif -> position Tradeco "
                            f"fermée : {fermer(p)[1]}")

        # 2. l'ordre à l'avance
        if sig_att != attentes.get(marche, "0"):
            for o in nos_ordres(sym):
                fait.append(f"{sym} : ordre à l'avance annulé -> {annuler(o)[1]}")
            if sig_att != "0":
                fin = pd.Timestamp(temps_serveur) + pd.Timedelta(minutes=15 * max(int(att["bougies"]), 1))
                ok, msg = poser(sym, int(att["genre"]), float(att["prix"]), att_lots, fin)
                genre = "limite" if int(att["genre"]) == 1 else "stop"
                fait.append(f"{sym} : ordre à l'avance {'achat' if att_lots > 0 else 'vente'} {genre} "
                            f"{abs(att_lots)} lot(s) à {att['prix']:.5g} -> {msg}")
            attentes[marche] = sig_att

        # 3. stop et objectif suivent ceux du compte fictif
        for p in nos_positions(sym):
            r = proteger(p, v.get("stop"), v.get("objectif"))
            if r is not None:
                fait.append(f"{sym} : stop / objectif mis à jour -> {r[1]}")
    _sauver(etat)
    return fait

def compte() -> dict:
    a = mt5.account_info()
    etat = _etat()
    return {"solde": a.balance, "capitaux": a.equity, "depart": etat.get("depart", a.equity),
            "positions": [f"{p.symbol} {'achat' if p.type == mt5.POSITION_TYPE_BUY else 'vente'} {p.volume} lot(s)"
                          for s in SYMBOLES.values() for p in nos_positions(s)],
            "ordres": [f"{o.symbol} {o.volume_current} lot(s) à {o.price_open}" for s in SYMBOLES.values()
                       for o in nos_ordres(s)]}


def _sauver(etat: dict):
    DOSSIER.mkdir(parents=True, exist_ok=True)
    ETAT.write_text(json.dumps(etat, ensure_ascii=False, indent=1), encoding="utf-8")
