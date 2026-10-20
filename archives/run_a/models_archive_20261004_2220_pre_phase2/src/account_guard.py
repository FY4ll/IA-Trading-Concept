"""
account_guard.py
==================
Coupe-circuit au niveau du COMPTE -- le troisième et dernier filet de
sécurité, indépendant des deux autres :
  1. le stop CHOISI PAR L'AGENT limite la perte d'UNE position (voir
     src/trading_env.py, agent.learn_stop_loss) ;
  2. src/risk_guard.py réduit l'exposition si le MARCHÉ sort
     statistiquement de l'ordinaire, indépendamment de ce que décide
     l'agent ;
  3. ICI : si l'ÉQUITÉ RÉELLE DU COMPTE, elle, a baissé de plus de
     `live.max_account_drawdown_pct` depuis son plus haut jamais atteint --
     toutes causes confondues (une série de pertes, un bug, un
     comportement inattendu de l'agent) -- tout nouvel ordre est bloqué et
     une alerte est envoyée (voir src/notifier.py), jusqu'à intervention
     humaine EXPLICITE (voir reset()). Ni l'agent ni un signal de marché ne
     peuvent lever ce blocage eux-mêmes : c'est précisément le but d'un
     coupe-circuit -- la dernière ligne de défense doit rester en dehors du
     système qu'elle surveille.

N'est appelé QUE par la boucle de démo (src/demo_trader.py) -- ne touche
JAMAIS à l'entraînement (src/continuous_trainer.py), qui continue de
tourner normalement même si ce coupe-circuit est déclenché (rien
n'empêche de continuer à apprendre pendant qu'on met le trading en pause
pour revue humaine).

État persisté dans un fichier JSON (survit aux redémarrages du script --
un compte qui a déjà dépassé le seuil hier reste bloqué aujourd'hui tant
que personne n'a explicitement appelé reset()).
"""
from __future__ import annotations
import json
import logging
import os
import threading
import time
from datetime import datetime, timezone

from src.risk_profile import current_reset_boundary_utc

log = logging.getLogger("account_guard")

STATE_PATH = os.path.join("data", "account_guard_state.json")
# Protège la lecture-calcul-écriture de l'état contre un appel concurrent
# (en pratique un seul thread -- la boucle de démo -- appelle check(), mais
# un Lock coûte rien et évite toute mauvaise surprise si ça change un jour).
_lock = threading.Lock()


def _read_state() -> dict:
    if not os.path.exists(STATE_PATH):
        return {}
    try:
        with open(STATE_PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _write_state(state: dict):
    os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)


def reset():
    """Remet le coupe-circuit à zéro (le prochain contrôle repart d'un
    nouveau pic d'équité = l'équité mesurée à ce moment-là) -- à appeler
    EXPLICITEMENT après une revue humaine de ce qui s'est passé, jamais
    automatiquement par le système lui-même. En pratique : supprimez
    data/account_guard_state.json, ou appelez cette fonction."""
    with _lock:
        if os.path.exists(STATE_PATH):
            os.remove(STATE_PATH)
    log.info("Coupe-circuit de compte réinitialisé -- reparti d'un nouveau pic d'équité.")


def is_halted() -> bool:
    """Consultation sans effet de bord (utilisée par le dashboard) : True
    si le coupe-circuit est actuellement déclenché."""
    return bool(_read_state().get("halted"))


def check(connector, cfg: dict) -> bool:
    """Retourne True si le trading peut continuer, False si le coupe-circuit
    est (ou vient d'être) déclenché -- l'appelant (demo_trader.py) doit
    alors sauter le cycle de décision SANS envoyer aucun ordre, exactement
    comme pour un marché fermé.

    Deux règles INDÉPENDANTES, chacune peut déclencher seule :
      1. DRAWDOWN TOTAL (`live.max_account_drawdown_pct`, comme avant) --
         `live.total_drawdown_mode` choisit la référence : "trailing"
         (défaut, comportement d'origine -- pic d'équité historique, monte
         avec de nouveaux sommets) ou "static" (référence FIGÉE à la
         première équité jamais observée, ex: capital initial d'un
         challenge FTMO 2-Step -- ne bouge JAMAIS, même après un nouveau
         sommet). Absent/0 désactive cette règle.
      2. PERTE QUOTIDIENNE (`live.daily_loss_enabled`/`daily_loss_max_pct`,
         voir src/risk_profile.py) -- référence réinitialisée à l'équité
         courante à chaque passage de `daily_loss_reset_time_local` (heure
         LOCALE de la firme, ex: 00:00 Europe/Prague pour FTMO -- le
         passage heure d'été/hiver est géré par zoneinfo, jamais une dérive
         manuelle). Désactivée par défaut (comportement d'origine du
         projet, qui n'avait aucune notion de "journée").

    Les deux règles partagent le MÊME état "halted" -- une fois l'une ou
    l'autre déclenchée, tout s'arrête jusqu'à reset() explicite, comme pour
    un vrai coupe-circuit (peu importe LAQUELLE des deux causes l'arrêt).
    """
    live_cfg = cfg.get("live", {})
    total_threshold = live_cfg.get("max_account_drawdown_pct")
    daily_enabled = live_cfg.get("daily_loss_enabled", False)
    daily_threshold = live_cfg.get("daily_loss_max_pct")
    if not total_threshold and not (daily_enabled and daily_threshold):
        return True  # aucune des deux règles n'est configurée -> rien à surveiller

    equity = connector.get_account_equity()
    if equity is None:
        # CORRECTIF FAIL-SAFE (19/09, audit institutionnel item "heartbeat /
        # perte de connexion") : jusqu'ici, une équité illisible (connexion
        # MT5 perturbée, terminal déconnecté...) faisait `return True` --
        # "rien à évaluer, ne pas bloquer". C'est l'INVERSE de ce qu'un
        # coupe-circuit doit faire : une connexion cassée est exactement le
        # moment où on veut LE PLUS de prudence, pas moins -- désactiver la
        # dernière ligne de défense pile quand elle est le plus nécessaire
        # était un vrai trou de sécurité. Bloque désormais CE cycle par
        # précaution -- sans déclencher le halt PERSISTANT (`state["halted"]
        # = True`, qui nécessite un reset() humain) : un simple blip
        # transitoire (un poll manqué) ne doit pas exiger une intervention
        # manuelle, le cycle suivant réessaiera normalement dès que l'équité
        # redevient lisible. Voir aussi MT5Connector.seconds_since_last_success
        # pour la détection de coupure prolongée (>5s avec position ouverte),
        # qui déclenche elle une alerte immédiate côté demo_trader.py.
        log.warning("Équité du compte illisible (connexion MT5 perturbée ?) -- cycle de "
                    "trading bloqué par précaution (pas de halt persistant pour un blip isolé).")
        return False
    if equity <= 0:
        return False  # équité nulle/négative : coupe-circuit, on bloque par prudence

    with _lock:
        state = _read_state()
        if state.get("halted"):
            # AUTO-REPRISE LE LENDEMAIN (19/09, audit institutionnel item 1) --
            # UNIQUEMENT pour la cause "perte quotidienne" : une fois qu'une
            # NOUVELLE journée de trading a commencé (même frontière que celle
            # utilisée par la règle elle-même, voir current_reset_boundary_utc
            # ci-dessous), le blocage se lève tout seul et la référence
            # quotidienne repart de l'équité actuelle -- exactement le
            # comportement "bloque jusqu'au lendemain" demandé. La cause
            # "drawdown total" N'EST JAMAIS concernée par cette reprise
            # automatique : elle continue d'exiger un reset() humain explicite
            # (voir docstring du module) -- un drawdown structurel mérite une
            # revue humaine, pas juste l'écoulement d'une journée.
            # `live.daily_loss_auto_resume` (défaut True) permet de désactiver
            # entièrement cette reprise automatique et de revenir à l'ancien
            # comportement (manuel pour les deux causes) si préféré.
            auto_resume = live_cfg.get("daily_loss_auto_resume", True)
            if auto_resume and state.get("halted_reason") == "perte quotidienne" and daily_enabled:
                reset_local = live_cfg.get("daily_loss_reset_time_local", "00:00")
                reset_tz = live_cfg.get("daily_loss_reset_timezone", "UTC")
                current_period_start_iso = current_reset_boundary_utc(
                    datetime.now(timezone.utc), reset_local, reset_tz).isoformat()
                if state.get("daily_period_start") != current_period_start_iso:
                    log.info(f"Coupe-circuit (perte quotidienne) levé AUTOMATIQUEMENT -- nouvelle "
                              f"journée de trading commencée ({reset_local} {reset_tz}). Référence "
                              f"quotidienne repartie de l'équité actuelle ({equity:.2f}).")
                    try:
                        from src.notifier import send_alert
                        send_alert(cfg, subject="Test_IA - reprise automatique (nouvelle journée)",
                                   message=(f"Coupe-circuit de perte quotidienne (déclenché "
                                            f"précédemment) levé automatiquement -- nouvelle journée "
                                            f"de trading ({reset_local} {reset_tz}). Équité actuelle : "
                                            f"{equity:.2f}."))
                    except Exception:
                        pass
                    # PAS de `return False` ici : on retombe dans l'évaluation
                    # normale ci-dessous avec un état rafraîchi (halted=False,
                    # référence quotidienne = équité ACTUELLE) -- exactement
                    # comme un passage normal de frontière de journée pour la
                    # règle "PERTE QUOTIDIENNE" plus bas (section 2), qui fait
                    # déjà la même chose. Cette nouvelle journée démarre donc
                    # avec un compteur de perte à 0%, pas favorisée ni
                    # pénalisée par rapport à un jour qui n'aurait jamais été
                    # bloqué -- une nouvelle chute ne redéclenchera le
                    # coupe-circuit qu'au PROCHAIN appel de check() où
                    # `daily_drawdown` dépasse à nouveau le seuil.
                    state = {**state, "halted": False, "daily_reference_equity": equity,
                             "daily_period_start": current_period_start_iso}
                else:
                    return False  # même journée : reste bloqué
            else:
                return False  # déjà déclenché (drawdown total, ou reprise auto désactivée) : reset() humain requis

        # --- 1) DRAWDOWN TOTAL ---
        initial_equity = state.get("initial_equity", equity)  # figé au premier check() jamais fait
        peak_equity = max(state.get("peak_equity", equity), equity)
        mode = live_cfg.get("total_drawdown_mode", "trailing")
        total_reference = initial_equity if mode == "static" else peak_equity
        total_drawdown = (total_reference - equity) / total_reference if total_reference > 0 else 0.0

        if total_threshold and total_drawdown >= total_threshold:
            _halt(cfg, live_cfg, equity, reason="drawdown total",
                  detail=f"en baisse de {total_drawdown:.1%} depuis sa référence "
                          f"{'FIXE (mode static)' if mode == 'static' else 'la plus haute atteinte (mode trailing)'} "
                          f"({total_reference:.2f}) -- seuil configuré {total_threshold:.1%}",
                  extra_state={"initial_equity": initial_equity, "peak_equity": peak_equity})
            return False

        # --- 2) PERTE QUOTIDIENNE ---
        daily_reference_equity = state.get("daily_reference_equity", equity)
        daily_period_start_iso = state.get("daily_period_start")
        if daily_enabled:
            reset_local = live_cfg.get("daily_loss_reset_time_local", "00:00")
            reset_tz = live_cfg.get("daily_loss_reset_timezone", "UTC")
            current_period_start = current_reset_boundary_utc(datetime.now(timezone.utc), reset_local, reset_tz)
            current_period_start_iso = current_period_start.isoformat()
            if daily_period_start_iso != current_period_start_iso:
                # Nouvelle journée de trading (heure locale de la firme) --
                # la référence repart de l'équité ACTUELLE, comme le solde
                # relevé à l'heure de reset chez un vrai broker.
                daily_reference_equity = equity
                daily_period_start_iso = current_period_start_iso

            daily_drawdown = ((daily_reference_equity - equity) / daily_reference_equity
                               if daily_reference_equity > 0 else 0.0)
            if daily_threshold and daily_drawdown >= daily_threshold:
                _halt(cfg, live_cfg, equity, reason="perte quotidienne",
                      detail=f"en baisse de {daily_drawdown:.1%} depuis la référence du jour "
                              f"({daily_reference_equity:.2f}, reset {reset_local} {reset_tz}) -- "
                              f"seuil configuré {daily_threshold:.1%}",
                      extra_state={"initial_equity": initial_equity, "peak_equity": peak_equity,
                                   "daily_reference_equity": daily_reference_equity,
                                   "daily_period_start": daily_period_start_iso})
                return False
        else:
            daily_period_start_iso = None

        _write_state({
            "halted": False, "initial_equity": initial_equity, "peak_equity": peak_equity,
            "daily_reference_equity": daily_reference_equity, "daily_period_start": daily_period_start_iso,
        })
        return True


def _halt(cfg: dict, live_cfg: dict, equity: float, reason: str, detail: str, extra_state: dict):
    """Factorise le déclenchement (état + log + alerte) entre les deux
    règles -- même mécanisme, seul le message/la cause diffère."""
    new_state = {"halted": True, "equity_at_halt": equity, "halted_reason": reason,
                 "halted_at": time.time(), **extra_state}
    _write_state(new_state)
    message = (
        f"COUPE-CIRCUIT DÉCLENCHÉ ({reason}) sur {live_cfg.get('symbol', '?')} : équité {equity:.2f} {detail}. "
        f"Tout nouvel ordre est bloqué jusqu'à intervention manuelle "
        f"(supprimez data/account_guard_state.json après avoir compris ce qui s'est passé)."
    )
    log.critical(message)
    from src.notifier import send_alert
    send_alert(cfg, subject="Coupe-circuit declenche - Test_IA", message=message)
