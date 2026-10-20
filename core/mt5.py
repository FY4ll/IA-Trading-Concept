"""Les MAINS sur MetaTrader 5 (core, 20/10/2026) : reprises de collapsar/direct/tradeco.py, rendues génériques.

- compte DÉMO seulement : tout compte réel est refusé (sécurité) ;
- accès : fichier JSON hors du dépôt (par défaut %USERPROFILE%\\.collapsar\\acces_tradeco.json : « login » et
  « serveur » ; le mot de passe reste dans MetaTrader, jamais dans le code ni dans git) ;
- seules NOS positions sont touchées (numéro magique) ;
- stop / objectif du mauvais côté du prix : retirés avant l'envoi (MetaTrader les refuserait) ;
- coupe-circuit : -4,5 % sur la journée (minuit à Prague) ou -9 % depuis le départ.
MetaTrader5 n'est importé qu'à l'usage : le reste de core se teste sans lui.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import pandas as pd

TERMINAL = r"C:\Program Files\MetaTrader 5\terminal64.exe"
ACCES = Path.home() / ".collapsar" / "acces_tradeco.json"
COUPE_JOUR, COUPE_TOTAL = 0.045, 0.09


def _mt5():
    import MetaTrader5 as mt5
    return mt5


def _niveau(x) -> float:
    return 0.0 if x is None or (isinstance(x, float) and math.isnan(x)) else float(x)


class Mains:
    def __init__(self, magic: int, commentaire: str = "TestIA", acces: Path = ACCES, terminal: str = TERMINAL):
        self.magic, self.commentaire, self.acces, self.terminal = magic, commentaire, Path(acces), terminal

    # ------------------------------------------------------------------ connexion
    def connecter(self, symboles=()) -> None:
        """MetaTrader sur le compte démo du fichier d'accès (bascule si besoin). Refuse tout compte réel."""
        mt5 = _mt5()
        if not mt5.initialize(path=self.terminal, timeout=60000):
            raise RuntimeError(f"MetaTrader injoignable : {mt5.last_error()}")
        acces = json.loads(self.acces.read_text(encoding="utf-8"))
        a = mt5.account_info()
        if a is None or a.login != acces["login"]:
            if not mt5.login(acces["login"], server=acces["serveur"], timeout=60000):
                raise RuntimeError(f"connexion impossible : {mt5.last_error()}")
            a = mt5.account_info()
        if a is None or a.trade_mode != mt5.ACCOUNT_TRADE_MODE_DEMO:
            raise RuntimeError("compte non démo : aucun ordre (sécurité)")
        for s in symboles:
            mt5.symbol_select(s, True)

    def algo_permis(self) -> bool:
        """Bouton « Trading algo » allumé dans MetaTrader."""
        return bool(_mt5().terminal_info().trade_allowed)

    # ------------------------------------------------------------------ lecture
    def lots(self, symbole: str, unites: float) -> float:
        """Unités (onces pour l'or) -> lots, au pas du courtier (0 si trop petit)."""
        s = _mt5().symbol_info(symbole)
        v = abs(unites) / s.trade_contract_size
        v = math.floor(v / s.volume_step + 1e-9) * s.volume_step
        if v < s.volume_min:
            return 0.0
        return round(min(v, s.volume_max), 8) * (1 if unites > 0 else -1)

    def positions(self, symbole: str) -> list:
        return [p for p in (_mt5().positions_get(symbol=symbole) or []) if p.magic == self.magic]

    def ordres(self, symbole: str) -> list:
        return [o for o in (_mt5().orders_get(symbol=symbole) or []) if o.magic == self.magic]

    def ecart(self, symbole: str) -> float:
        """Écart du moment (prix d'achat - prix de vente), en prix."""
        t = _mt5().symbol_info_tick(symbole)
        return float(t.ask - t.bid)

    # ------------------------------------------------------------------ ordres
    def _remplissage(self, symbole: str) -> int:
        mt5 = _mt5()
        mode = mt5.symbol_info(symbole).filling_mode
        return mt5.ORDER_FILLING_IOC if mode & 2 else mt5.ORDER_FILLING_FOK if mode & 1 else mt5.ORDER_FILLING_RETURN

    def _envoyer(self, demande: dict) -> tuple[bool, str]:
        mt5 = _mt5()
        r = mt5.order_send(demande)
        if r is None:
            return False, f"pas de réponse ({mt5.last_error()})"
        return r.retcode == mt5.TRADE_RETCODE_DONE, f"code {r.retcode} {r.comment}"

    def ouvrir(self, symbole: str, volume: float, stop=None, objectif=None) -> tuple[bool, str]:
        """Ordre au marché ; `volume` en lots signé (+ achat, - vente)."""
        mt5 = _mt5()
        t, s = mt5.symbol_info_tick(symbole), mt5.symbol_info(symbole)
        achat = volume > 0
        sl, tp = round(_niveau(stop), s.digits), round(_niveau(objectif), s.digits)
        if sl and ((achat and sl >= t.bid) or (not achat and sl <= t.ask)):
            sl = 0.0
        if tp and ((achat and tp <= t.bid) or (not achat and tp >= t.ask)):
            tp = 0.0
        return self._envoyer({"action": mt5.TRADE_ACTION_DEAL, "symbol": symbole, "volume": abs(volume),
                              "price": t.ask if achat else t.bid,
                              "type": mt5.ORDER_TYPE_BUY if achat else mt5.ORDER_TYPE_SELL, "sl": sl, "tp": tp,
                              "deviation": 50, "magic": self.magic, "comment": self.commentaire,
                              "type_filling": self._remplissage(symbole)})

    def fermer(self, p, volume: float | None = None) -> tuple[bool, str]:
        """Ferme la position `p` (ou seulement `volume` lots : prise de bénéfice partielle)."""
        mt5 = _mt5()
        t = mt5.symbol_info_tick(p.symbol)
        achat = p.type == mt5.POSITION_TYPE_BUY
        return self._envoyer({"action": mt5.TRADE_ACTION_DEAL, "symbol": p.symbol,
                              "volume": p.volume if volume is None else min(abs(volume), p.volume),
                              "position": p.ticket, "type": mt5.ORDER_TYPE_SELL if achat else mt5.ORDER_TYPE_BUY,
                              "price": t.bid if achat else t.ask, "deviation": 50, "magic": self.magic,
                              "comment": self.commentaire + " ferme", "type_filling": self._remplissage(p.symbol)})

    def proteger(self, p, stop, objectif) -> tuple[bool, str] | None:
        """Déplace stop / objectif d'une position (rien si inchangés)."""
        mt5 = _mt5()
        s, t = mt5.symbol_info(p.symbol), mt5.symbol_info_tick(p.symbol)
        sl, tp = round(_niveau(stop), s.digits), round(_niveau(objectif), s.digits)
        achat = p.type == mt5.POSITION_TYPE_BUY
        if sl and ((achat and sl >= t.bid) or (not achat and sl <= t.ask)):
            sl = p.sl
        if tp and ((achat and tp <= t.bid) or (not achat and tp >= t.ask)):
            tp = p.tp
        if abs(sl - p.sl) < s.point / 2 and abs(tp - p.tp) < s.point / 2:
            return None
        return self._envoyer({"action": mt5.TRADE_ACTION_SLTP, "symbol": p.symbol, "position": p.ticket,
                              "sl": sl, "tp": tp, "magic": self.magic})

    def poser(self, symbole: str, genre: int, prix: float, volume: float, expiration: pd.Timestamp) -> tuple[bool, str]:
        """Ordre à l'avance : `genre` 1 = limite, 2 = stop (cassure). Déjà exécutable au prix du moment : au marché."""
        mt5 = _mt5()
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
            return self.ouvrir(symbole, volume)
        return self._envoyer({"action": mt5.TRADE_ACTION_PENDING, "symbol": symbole, "volume": abs(volume),
                              "type": type_, "price": prix, "sl": 0.0, "tp": 0.0,
                              "type_time": mt5.ORDER_TIME_SPECIFIED,
                              "expiration": int(pd.Timestamp(expiration).timestamp()), "magic": self.magic,
                              "comment": self.commentaire + " avance", "type_filling": mt5.ORDER_FILLING_RETURN})

    def annuler(self, o) -> tuple[bool, str]:
        return self._envoyer({"action": _mt5().TRADE_ACTION_REMOVE, "order": o.ticket, "magic": self.magic})

    def tout_fermer(self, symboles, raison: str) -> list[str]:
        fait = []
        for sym in symboles:
            for o in self.ordres(sym):
                fait.append(f"{sym} : ordre à l'avance annulé ({raison}) -> {self.annuler(o)[1]}")
            for p in self.positions(sym):
                fait.append(f"{sym} fermée ({raison}) : {self.fermer(p)[1]}")
        return fait

    # ------------------------------------------------------------------ coupe-circuit
    def coupe_circuit(self, etat: dict) -> str | None:
        """Rend la raison si le compte a perdu 4,5 % sur la journée (minuit à Prague) ou 9 % depuis le départ.
        `etat` (dict gardé par l'appelant) retient le départ et le solde de minuit."""
        a = _mt5().account_info()
        jour = pd.Timestamp.now(tz="Europe/Prague").strftime("%Y-%m-%d")
        etat.setdefault("depart", a.equity)
        if etat.get("jour") != jour:
            etat["jour"], etat["solde_minuit"] = jour, a.balance
        if a.equity <= etat["solde_minuit"] * (1 - COUPE_JOUR):
            return f"-{COUPE_JOUR * 100:.1f} % sur la journée"
        if a.equity <= etat["depart"] * (1 - COUPE_TOTAL):
            return f"-{COUPE_TOTAL * 100:.0f} % depuis le départ"
        return None
