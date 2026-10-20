"""
live_narrator.py -- le NARRATEUR (08/10/2026, demande explicite : « une IA qui tient au courant, qui ne se tait pas
pour ouvrir d'un coup, et qui se justifie »).

Envoie sur le téléphone (src/notifier.send_alert), en français simple :
  1. chaque OUVERTURE (sens, prix, stop, objectif, risque) avec sa justification (ce qu'elle voit + à quel point
     elle est sûre d'elle) ;
  2. chaque SORTIE décidée par l'IA (résultat) -- les sorties au stop/objectif sont déjà signalées par
     state_reconciliation ;
  3. les INTENTIONS BLOQUÉES (elle voudrait ouvrir, une règle l'en empêche), au plus une fois toutes les N heures ;
  4. un BULLETIN à heures fixes (heure de Paris), hors week-end, même quand elle ne fait rien.
La justification DÉCRIT la situation vue par l'IA et sa confiance ; elle ne prétend pas être son raisonnement.
"""
from __future__ import annotations
import json
import logging
import os
import time
from datetime import datetime, timezone

log = logging.getLogger("live_narrator")

REASONS = [("trend_discipline", "la tendance de fond (journalière) va dans l'autre sens"),
           ("stop_cap", "plafond de stops du jour atteint"), ("cooldown", "pause après une sortie récente"),
           ("risk_guard", "marché trop agité"), ("exclusive_group", "une stratégie de la même famille est déjà en position"),
           ("not_eligible", "plus autorisée à ouvrir de nouvelles positions"),
           ("conflict", "une autre IA détient une position dans l'autre sens"),
           ("news", "annonce économique imminente"), ("regime", "conditions de marché défavorables")]
WORDS = [("biais H4 haussier", "tendance sur 4 heures à la hausse"), ("biais H4 baissier", "tendance sur 4 heures à la baisse"),
         ("pas de biais H4", "pas de tendance nette sur 4 heures"),
         ("structure H1 haussière (HH/HL)", "sommets et creux de plus en plus hauts sur l'heure"),
         ("structure H1 baissière (LH/LL)", "sommets et creux de plus en plus bas sur l'heure"),
         ("H1 en range", "marché sans direction sur l'heure"), (" ATR ", " fois le mouvement habituel "),
         ("news majeure", "annonce économique majeure"), ("volatilité EXTRÊME", "marché extrêmement agité"),
         ("volatilité haute", "marché agité"), ("volatilité basse", "marché calme"),
         ("dernier sommet H1", "dernier sommet de l'heure"), ("dernier creux H1", "dernier creux de l'heure"),
         ("dernier sommet H4", "dernier sommet sur 4 heures"), ("dernier creux H4", "dernier creux sur 4 heures"),
         ("dernier sommet D1", "dernier sommet journalier"), ("dernier creux D1", "dernier creux journalier"),
         ("(EURUSD)", "(vu sur l'euro-dollar)"), ("veut sécuriser à break-even", "veut remonter son stop à son prix d'entrée"),
         ("fait suivre son stop", "fait suivre son stop")]


def _plain(text: str | None) -> str:
    if not text:
        return ""
    t = f" {text} "
    for a, b in WORDS:
        t = t.replace(a, b)
    return t.strip()


def _reason(block_reasons) -> str | None:
    for r in block_reasons or []:
        for key, txt in REASONS:
            if str(r).startswith(key):
                return txt
    return str(block_reasons[0]) if block_reasons else None


def _context(note: str | None) -> str:
    """La partie « situation » de la note (après le tiret), en mots simples."""
    if not note or " -- " not in note:
        return ""
    return _plain(note.split(" -- ", 1)[1].rstrip("."))


def _probas(p: dict | None) -> str:
    if not p:
        return ""
    return (f"acheter {p.get('long', 0):.0%}, attendre {p.get('flat', 0):.0%}, vendre {p.get('short', 0):.0%}")


def _event(next_event: str | None, tz) -> str:
    if not next_event:
        return ""
    try:
        ts, rest = next_event.split(" ", 1)
        when = datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(tz)
        return f"prochaine annonce importante : {rest} le {when:%d/%m à %Hh%M}"
    except Exception:
        return f"prochaine annonce importante : {next_event}"


class Narrator:
    def __init__(self, cfg: dict, connector, state_path: str = os.path.join("data", "narrateur.json")):
        self.cfg = cfg
        self.connector = connector
        ncfg = (cfg.get("live") or {}).get("narrator") or {}
        self.enabled = bool(ncfg.get("enabled"))
        self.hours = [int(h) for h in ncfg.get("bulletin_hours", [8, 14, 20])]
        self.blocked_every = float(ncfg.get("blocked_every_hours", 4)) * 3600
        try:
            from zoneinfo import ZoneInfo
            self.tz = ZoneInfo(ncfg.get("timezone", "Europe/Paris"))
        except Exception:
            self.tz = timezone.utc
        self.state_path = state_path
        self.state = self._load()
        self.last: dict = {}                            # dernière décision connue par style

    # ------------------------------------------------------------------ état
    def _load(self) -> dict:
        try:
            with open(self.state_path, encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError):
            return {}

    def _save(self):
        try:
            os.makedirs(os.path.dirname(self.state_path) or ".", exist_ok=True)
            with open(self.state_path, "w", encoding="utf-8") as f:
                json.dump(self.state, f)
        except OSError:
            pass

    def _send(self, subject: str, message: str):
        log.info(f"[narrateur] {subject} | {message}")
        try:
            from src.notifier import send_alert
            send_alert(self.cfg, subject=subject, message=message)
        except Exception as e:
            log.warning(f"[narrateur] envoi impossible ({type(e).__name__}: {e})")

    # ------------------------------------------------------------------ décisions
    def on_decision(self, row: dict, existing_position: dict | None, now: float | None = None):
        """Appelé après chaque décision (row = ligne du journal de décision, avec note et probabilités)."""
        if not self.enabled:
            return
        now = time.time() if now is None else now
        style, action = row.get("style"), row.get("action")
        self.last[style] = {**row, "existing_position": existing_position}
        ctx = _context(row.get("note"))
        probas = _probas({"long": row.get("p_long") or 0, "flat": row.get("p_flat") or 0, "short": row.get("p_short") or 0})
        if action in ("OPEN_LONG", "OPEN_SHORT", "REVERSE"):
            if action == "REVERSE" and existing_position:
                self._send(f"Test_IA - {style} retourne sa position",
                           f"{style} ferme sa position ({existing_position.get('profit', 0):+.0f} $ en cours) pour "
                           f"prendre le sens inverse.")
            self._opening(style, row, ctx, probas)
        elif action == "CLOSE" and existing_position:
            why = "elle n'y croit plus" if row.get("wait_reason") == "model_exit" else (_reason(row.get("block_reasons")) or "")
            self._send(f"Test_IA - {style} ferme sa position",
                       f"{style} sort de son {'ACHAT' if existing_position.get('direction') == 1 else 'VENTE'} : "
                       f"résultat {existing_position.get('profit', 0):+.0f} $. Pourquoi : {why}."
                       + (f" Ce qu'elle voit : {ctx}." if ctx else ""))
        elif action == "WAIT" and abs(row.get("raw_target") or 0) > 1e-9 and row.get("block_reasons"):
            key = f"bloque_{style}"
            if now - float(self.state.get(key, float("-inf"))) >= self.blocked_every:
                side = "acheter" if (row.get("raw_target") or 0) > 0 else "vendre"
                self._send(f"Test_IA - {style} voudrait {side}",
                           f"{style} voudrait {side} ({probas}), mais c'est bloqué : {_reason(row.get('block_reasons'))}. "
                           f"Je réessaierai à chaque bougie." + (f" Ce qu'elle voit : {ctx}." if ctx else ""))
                self.state[key] = now
                self._save()

    def _opening(self, style, row, ctx, probas):
        side = "ACHAT" if (row.get("final_target") or 0) > 0 else "VENTE"
        pos = None
        try:
            pos = self.connector.get_open_positions_by_style([style]).get(style)
        except Exception:
            pass
        price = (pos or {}).get("price_open") or row.get("price")
        sl, tp = (pos or {}).get("sl"), (pos or {}).get("tp")
        eq = None
        try:
            eq = self.connector.get_account_equity()
        except Exception:
            pass
        risk_usd = eq * row["risk_pct"] if eq and row.get("risk_pct") else None
        rr = row.get("take_profit_rr")
        parts = [f"{style} ouvre un {side} à {price:.2f}" if price else f"{style} ouvre un {side}"]
        if sl:
            parts.append(f"stop {sl:.2f}" + (f" (risque ≈ {risk_usd:.0f} $)" if risk_usd else ""))
        if tp:
            parts.append(f"objectif {tp:.2f}" + (f" (gain visé ≈ {risk_usd * rr:.0f} $)" if risk_usd and rr else ""))
        why = [f"elle est à {probas}"] if probas else []
        if ctx:
            why.append(ctx)
        ev = _event(row.get("next_event"), self.tz)
        if ev:
            why.append(ev)
        self._send(f"Test_IA - {style} ouvre un {side}", ", ".join(parts) + ". Pourquoi : " + " ; ".join(why) + ".")

    # ------------------------------------------------------------------ bulletins
    def maybe_bulletin(self, styles: list[str], now: datetime | None = None):
        if not self.enabled:
            return
        now = now or datetime.now(self.tz)
        local = now.astimezone(self.tz)
        if local.weekday() >= 5 or local.hour not in self.hours:
            return
        slot = f"{local:%Y-%m-%d}-{local.hour:02d}"
        if self.state.get("bulletin") == slot:
            return
        self.state["bulletin"] = slot
        self._save()
        lines = []
        for style in styles:
            r = self.last.get(style)
            if not r:
                continue
            pos = r.get("existing_position")
            probas = _probas({"long": r.get("p_long") or 0, "flat": r.get("p_flat") or 0, "short": r.get("p_short") or 0})
            if pos:
                state = (f"en {'ACHAT' if pos.get('direction') == 1 else 'VENTE'} depuis {pos.get('price_open', 0):.2f}, "
                         f"{pos.get('profit', 0):+.0f} $ en cours")
            else:
                why = _reason(r.get("block_reasons")) or ("pas assez sûre d'elle" if r.get("action") == "WAIT" else "")
                state = "pas de position" + (f" ({why})" if why else "")
            ctx = _context(r.get("note"))
            lines.append(f"{style} : {state}. Elle est à {probas}." + (f" Elle voit : {ctx}." if ctx else ""))
            ev = _event(r.get("next_event"), self.tz)
            if ev and ev not in " ".join(lines):
                lines.append(ev.capitalize() + ".")
        try:
            eq = self.connector.get_account_equity()
            if eq:
                lines.append(f"Compte : {eq:,.0f} $".replace(",", " "))
        except Exception:
            pass
        if lines:
            self._send(f"Test_IA - point de {local.hour}h", " ".join(lines))
