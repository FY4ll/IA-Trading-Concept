# Repris de Run A (src/risk_engine.py, version du 08/10/2026) pour l'architecture v3 -- calculs IDENTIQUES
# (prouvé par tests/test_cerveau_equivalence.py). Toute modification doit garder ce test vert.
"""
risk_engine.py
===============
Fonctions de risque PURES et DÉTERMINISTES (aucun I/O, aucun appel MT5) --
seule source de vérité pour le calcul de distance de stop et de taille de
position, utilisée à la fois par MT5Connector (exécution réelle) et
TradingEnv (simulation), pour éliminer la duplication de règles entre les
deux (LOT 2, phase 2 -- avant ce module, chacun réimplémentait sa propre
version avec des règles divergentes).

Chaque fonction ici réplique EXACTEMENT une formule qui existait déjà dans
src/mt5_connector.py (voir docstrings individuelles pour la correspondance) --
aucune nouvelle règle de risque n'est inventée dans ce module, seulement
extraite et partagée.
"""
from __future__ import annotations
from dataclasses import dataclass

# Bornes de sécurité pour un stop dérivé de l'ATR (LOT 2, phase 2/3) : un ATR
# quasi nul (marché mort) ou aberrant (pic de données) ne doit jamais produire
# un stop dégénéré. Source UNIQUE -- TradingEnv et MT5Connector référencent
# ces mêmes valeurs (voir TradingEnv.ATR_STOP_PCT_FLOOR/CEILING).
ATR_STOP_PCT_FLOOR = 0.002
ATR_STOP_PCT_CEILING = 0.15


@dataclass(frozen=True)
class SymbolSpec:
    """Caractéristiques d'un symbole nécessaires au calcul de risque -- lues
    depuis mt5.symbol_info() côté connecteur (voir MT5Connector._symbol_spec),
    ou depuis une config par symbole côté environnement de simulation. Ne
    vient JAMAIS de config/risk_profiles/ (qui ne définit que des
    pourcentages de risque/compte, pas ces caractéristiques de marché -- voir
    src/risk_profile.py)."""
    volume_min: float = 0.01
    volume_step: float = 0.01
    volume_max: float = 100.0
    contract_size: float = 100.0
    digits: int = 2
    stops_level_points: float = 0.0
    point: float = 0.0


def atr_stop_distance_pct(atr_price_units: float | None, multiplier: float, price: float,
                            floor_pct: float, ceiling_pct: float) -> float:
    """Distance de stop (fraction du prix) = multiple x ATR courant, bornée
    à [floor_pct, ceiling_pct] -- même formule que
    TradingEnv._compute_atr_stop_loss_buckets (ici pour UN SEUL multiplicateur,
    pas la liste des buckets). `atr_price_units=None` ou `price<=0` -> floor_pct
    (jamais un stop dégénéré)."""
    if atr_price_units is None or price <= 0:
        return floor_pct
    pct = multiplier * atr_price_units / price
    return min(max(pct, floor_pct), ceiling_pct)


def cap_stop_pct(stop_pct: float | None, max_stop_pct: float | None) -> float | None:
    """Plafond d'exécution sur la distance de stop -- réplique le bloc
    `max_stop_pct_executed` en tête de MT5Connector.send_order."""
    if stop_pct is None or max_stop_pct is None:
        return stop_pct
    return min(stop_pct, max_stop_pct)


def lots_from_risk(equity: float, risk_pct: float, price: float, stop_pct: float | None,
                     contract_size: float) -> float:
    """Réplique EXACTEMENT MT5Connector._risk_based_lots : lots pour une
    exposition PLEINE (1.0) tels que la perte au stop = equity * risk_pct.
    0.0 (jamais d'exception) si une entrée est invalide/manquante."""
    if not stop_pct or stop_pct <= 0 or equity <= 0 or price <= 0 or contract_size <= 0:
        return 0.0
    stop_distance_price = price * stop_pct
    return (equity * risk_pct) / (stop_distance_price * contract_size)


def notional_lots(equity: float, price: float, contract_size: float) -> float:
    """Réplique EXACTEMENT MT5Connector._notional_lots : repli sans stop
    disponible -- lots dont la valeur notionnelle = 100% de l'équité, sans
    levier."""
    if equity <= 0 or price <= 0 or contract_size <= 0:
        return 0.0
    return equity / (contract_size * price)


def round_volume(raw_volume: float, spec: SymbolSpec, floor_if_positive: bool = False) -> float:
    """Réplique EXACTEMENT MT5Connector._round_volume : arrondi au pas de lot
    + plancher/plafond broker, mêmes défauts (step=0.01, vol_min=step,
    vol_max=raw_volume) si spec dégénéré."""
    step = spec.volume_step or 0.01
    vol_min = spec.volume_min or step
    vol_max = spec.volume_max or raw_volume
    if raw_volume < vol_min:
        return round(vol_min, 2) if (floor_if_positive and raw_volume > 0) else 0.0
    stepped = round(raw_volume / step) * step
    return round(min(max(stepped, vol_min), vol_max), 2)


def tighten_stop_or_cancel(raw_volume: float, floored_volume: float, stop_pct: float | None,
                             equity: float, price: float, risk_pct: float,
                             spec: SymbolSpec) -> tuple[float | None, bool]:
    """Réplique EXACTEMENT le bloc de MT5Connector.send_order (garde-fou
    risque après arrondi au lot minimum + garde-fou dur stops_level) : si le
    lot a été PLANCHER (floored_volume > raw_volume, arrondi au-delà du lot
    idéal-risque), resserre `stop_pct` pour que le risque monétaire reste
    borné à equity*risk_pct -- ne l'élargit JAMAIS. Puis annule (retourne
    cancel=True) si ce stop resserré tombe sous le minimum imposé par le
    broker (spec.stops_level_points/spec.point). Retourne
    (stop_pct_effectif, cancel) -- l'appelant doit annuler l'ordre entier si
    cancel=True, ne jamais envoyer `stop_pct_effectif` dans ce cas."""
    effective_stop_pct = stop_pct
    if stop_pct is not None and floored_volume > raw_volume > 0:
        if floored_volume > 0 and spec.contract_size > 0 and price > 0:
            max_loss_dollars = equity * risk_pct
            tightened = max_loss_dollars / (floored_volume * spec.contract_size * price)
            if tightened < effective_stop_pct:
                effective_stop_pct = tightened
    if (effective_stop_pct is not None and spec.stops_level_points > 0
            and spec.point > 0 and price > 0):
        min_stop_pct = (spec.stops_level_points * spec.point) / price
        if effective_stop_pct < min_stop_pct:
            return effective_stop_pct, True
    return effective_stop_pct, False
