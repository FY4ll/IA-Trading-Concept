"""
state_reconciliation.py
========================
Module de RÉCONCILIATION D'ÉTAT (audit institutionnel, section 5 --
"synchroniser immédiatement la mémoire interne de l'IA avec MT5. Si une
divergence est détectée (ex: un Stop Loss a sauté chez le broker à cause du
spread mais l'IA ne l'a pas enregistré), l'IA doit s'aligner sur la réalité
du broker.").

PROBLÈME RÉEL RÉSOLU : `_LiveMemoryTracker` (voir src/demo_trader.py), qui
alimente la mémoire épisodique à partir des décisions RÉELLEMENT prises en
démo, ne connaît QUE ce que le modèle a lui-même décidé -- il ne re-vérifie
jamais auprès de MT5 si une position a effectivement été ouverte/fermée
comme prévu. Deux scénarios concrets où ça diverge :
  1. Un stop-loss posé côté broker (voir MT5Connector._stop_loss_field) se
     déclenche ENTRE deux cycles de décision (`live.poll_seconds`) -- le
     tracker interne croit toujours la position ouverte, alors qu'elle est
     déjà fermée chez le broker.
  2. Un redémarrage du script (crash, mise à jour, coupure électrique) pendant
     qu'une position réelle est ouverte -- `_StyleRuntime`/`_LiveMemoryTracker`
     repartent à zéro (`entry_price=None`), sans savoir qu'une position existe
     déjà chez le broker.

Dans les deux cas, la mémoire épisodique (donc l'apprentissage futur) et la
logique de cooldown/coordination inter-styles raisonneraient sur un état
FAUX sans ce module -- silencieusement, jusqu'à ce que la prochaine décision
du modèle révèle l'incohérence de façon indirecte (ex: une tentative
d'ouverture alors qu'une position existe déjà, ou l'inverse).

Le broker (MT5) est TOUJOURS la source de vérité -- jamais l'inverse.
"""
from __future__ import annotations
import logging

log = logging.getLogger("state_reconciliation")


def reconcile_state(connector, cfg: dict, runtimes: dict, broker_positions: dict | None = None) -> list[dict]:
    """Compare, POUR CHAQUE style de `runtimes` (voir
    src/demo_trader.py::_StyleRuntime), ce que son tracker interne
    (`rt.tracker`, voir _LiveMemoryTracker) croit être la position ouverte à
    ce que MT5 rapporte RÉELLEMENT (`connector.get_open_positions_by_style`).

    `broker_positions` (optionnel) : permet à l'appelant de réutiliser un
    résultat déjà récupéré CE cycle (voir demo_trader.py, où `open_by_style`
    est déjà lu pour la coordination inter-styles) plutôt que de refaire un
    appel MT5 redondant. Si None, ce module fait lui-même l'appel (usage au
    DÉMARRAGE, voir src/demo_trader.py::run_demo_trading_loop, où rien n'a
    encore été récupéré ce cycle-là).

    Ne lève JAMAIS d'exception : une réconciliation qui échoue à interroger
    MT5 (connexion temporairement indisponible) ne doit jamais empêcher le
    démarrage ni un cycle de démo -- elle retourne simplement une liste vide
    (rien à corriger CETTE fois, retentée au prochain appel).

    Retourne la liste des divergences détectées (vide si tout concorde) --
    chaque divergence est un dict structuré (utile pour les tests ET pour
    un futur tableau de bord), en plus d'un log.warning + une alerte
    best-effort (voir src/notifier.py) déjà envoyés pour chacune.

    ALIGNEMENT (le broker fait TOUJOURS foi) : en cas de divergence, le
    tracker interne du style concerné est corrigé pour refléter la réalité
    MT5 -- SIMPLIFICATION DOCUMENTÉE : l'exposition fractionnaire exacte
    (`entry_exposure`, potentiellement une valeur d'ensemble pondérée comme
    0.65) qui a mené à la position réelle n'est pas reconstruite depuis MT5
    (qui n'expose qu'une direction/un volume, pas la conviction d'origine du
    modèle) -- le tracker est donc réaligné sur ±1.0 (pleine conviction dans
    la direction réelle) plutôt que sur la valeur fractionnaire perdue. Le
    contexte de marché au moment de l'ouverture réelle (`entry_context`,
    utilisé pour indexer la mémoire épisodique) est mis à None plutôt que
    reconstruit à partir d'une supposition -- un signal manquant explicite
    est préférable à un signal silencieusement faux.
    """
    recognized_styles = list(runtimes.keys())
    if not recognized_styles:
        return []

    if broker_positions is None:
        try:
            broker_positions = connector.get_open_positions_by_style(recognized_styles)
        except Exception as e:
            log.warning(f"[réconciliation d'état] impossible d'interroger MT5 ({type(e).__name__}: {e}) "
                        f"-- aucune correction cette fois, retentée au prochain appel.")
            return []

    discrepancies = []
    for style, rt in runtimes.items():
        tracker = getattr(rt, "tracker", None)
        if tracker is None:
            continue  # style pas encore chargé (aucun modèle -> rien à réconcilier)

        broker_pos = broker_positions.get(style)
        broker_has_position = broker_pos is not None
        internal_has_position = abs(tracker.entry_exposure) > 1e-9
        internal_direction = 1 if tracker.entry_exposure > 0 else (-1 if tracker.entry_exposure < 0 else 0)
        broker_direction = broker_pos["direction"] if broker_pos else 0

        mismatch = (internal_has_position != broker_has_position) or (
            internal_has_position and broker_has_position and internal_direction != broker_direction
        )
        if not mismatch:
            continue

        discrepancy = {
            "style": style,
            "internal_entry_exposure": tracker.entry_exposure,
            "internal_entry_price": tracker.entry_price,
            "broker_direction": broker_direction if broker_has_position else None,
            "broker_volume": broker_pos["volume"] if broker_has_position else None,
            "broker_price_open": broker_pos["price_open"] if broker_has_position else None,
            "broker_ticket": broker_pos["ticket"] if broker_has_position else None,
        }
        discrepancies.append(discrepancy)

        broker_summary = ("AUCUNE position ouverte." if not broker_has_position else
                           f"ticket={broker_pos['ticket']} direction={broker_direction:+d} "
                           f"volume={broker_pos['volume']} prix_entrée={broker_pos['price_open']}.")
        log.warning(
            f"[réconciliation d'état] divergence détectée pour le style '{style}' -- mémoire interne : "
            f"exposition={tracker.entry_exposure:+.2f} (prix d'entrée={tracker.entry_price}), MT5 réel : "
            f"{broker_summary} -> alignement de la mémoire interne sur la réalité MT5 "
            f"(le broker fait toujours foi)."
        )
        try:
            from src.notifier import send_alert
            send_alert(
                cfg,
                subject=f"Test_IA - divergence d'état détectée ({style})",
                message=(
                    f"Divergence détectée entre la mémoire interne et l'état réel MT5 pour le style "
                    f"'{style}' : mémoire interne (exposition={tracker.entry_exposure:+.2f}, "
                    f"prix d'entrée={tracker.entry_price}) vs MT5 réel "
                    + (f"(aucune position ouverte)" if not broker_has_position else
                       f"(ticket={broker_pos['ticket']}, direction={broker_direction:+d}, "
                       f"volume={broker_pos['volume']}, prix d'entrée={broker_pos['price_open']})")
                    + f". Cause probable : stop-loss déclenché côté broker sans que l'IA ne l'enregistre, "
                    f"ou redémarrage du script pendant qu'une position réelle était ouverte. "
                    f"La mémoire interne a été réalignée automatiquement sur la réalité MT5."
                ),
            )
        except Exception:
            pass

        # ALIGNEMENT SUR LA RÉALITÉ DU BROKER (voir docstring -- le broker fait toujours foi).
        if broker_has_position:
            tracker.entry_exposure = float(broker_direction)  # ±1.0, conviction exacte perdue -- voir docstring
            tracker.entry_price = broker_pos["price_open"]
            tracker.entry_context = None
        else:
            tracker.entry_exposure = 0.0
            tracker.entry_price = None
            tracker.entry_context = None

    return discrepancies
