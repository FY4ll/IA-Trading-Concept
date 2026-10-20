"""
risk_profile.py
================
Charge un "profil de risque" (config/risk_profiles/<nom>.yaml, ex: FTMO) et
fusionne ses valeurs dans cfg["live"] au démarrage -- ALIMENTE les seuils
déjà en place (mt5_connector.py::max_risk_pct_per_trade,
account_guard.py::max_account_drawdown_pct/perte quotidienne), ne crée
AUCUN second système parallèle de garde-fous.

Le choix du profil (`live.risk_profile`) n'est volontairement PAS
éditable en direct depuis le tableau de bord (voir settings_server.py) --
changer toute la posture de risque à chaud sur un compte réel est trop
sensible pour un simple bouton, contrairement aux VALEURS qu'un profil
fixe, qui restent éditables comme avant une fois chargées dans cfg["live"].
"""
from __future__ import annotations
import os
import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import yaml

log = logging.getLogger("risk_profile")

PROFILES_DIR = "config/risk_profiles"


def load_risk_profile(name: str) -> dict:
    path = os.path.join(PROFILES_DIR, f"{name}.yaml")
    if not os.path.exists(path):
        available = sorted(f[:-5] for f in os.listdir(PROFILES_DIR)) if os.path.isdir(PROFILES_DIR) else []
        raise FileNotFoundError(
            f"Profil de risque '{name}' introuvable ({path}). Profils disponibles : {available}"
        )
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def apply_risk_profile(cfg: dict) -> dict:
    """Appelé UNE FOIS au démarrage (voir autonomous_agent.py), avant toute
    autre lecture de cfg["live"]. Si `live.risk_profile` est absent, ne
    touche à RIEN -- comportement actuel du projet, inchangé (aucun profil
    = aucune régression pour un déploiement existant)."""
    profile_name = cfg.get("live", {}).get("risk_profile")
    if not profile_name:
        return cfg
    profile = load_risk_profile(profile_name)
    live = cfg.setdefault("live", {})

    per_trade = profile.get("per_trade", {})
    if "max_risk_pct" in per_trade:
        live["max_risk_pct_per_trade"] = per_trade["max_risk_pct"]

    total_dd = profile.get("total_drawdown", {})
    if total_dd.get("enabled", True):
        live["max_account_drawdown_pct"] = total_dd.get("max_pct", live.get("max_account_drawdown_pct"))
        live["total_drawdown_mode"] = total_dd.get("mode", "trailing")
    else:
        live["max_account_drawdown_pct"] = None

    daily = profile.get("daily_loss", {})
    live["daily_loss_enabled"] = bool(daily.get("enabled", False))
    if live["daily_loss_enabled"]:
        live["daily_loss_max_pct"] = daily.get("max_pct")
        live["daily_loss_basis"] = daily.get("basis", "equity")
        live["daily_loss_reset_time_local"] = daily.get("reset_time_local", "00:00")
        live["daily_loss_reset_timezone"] = daily.get("reset_timezone", "UTC")

    # COORDINATION INTER-STYLES (19/09, arbitrage priorité par score --
    # voir demo_trader.py) : le hedging (positions BUY/SELL simultanées sur
    # le même symbole) n'est PAS interdit par toutes les prop firms -- FTMO
    # l'autoriserait explicitement selon une source, d'autres l'interdisent
    # strictement. La bonne valeur dépend donc de la firme visée, jamais un
    # blocage en dur : "priority_by_score" (le style au meilleur score
    # walk-forward garde/prend la priorité, l'autre est fermé ou bloqué),
    # "temporal_hierarchy" (voir TIMEFRAME_HIERARCHY dans demo_trader.py --
    # arbitre sur le RANG du timeframe primaire, jamais sur le score : le
    # style supérieur garde TOUJOURS la priorité, le style inférieur qui
    # s'opposerait à lui est TOUJOURS bloqué, quel que soit l'écart de
    # niveau -- zéro hedging toléré, durci le 18/09 après un cas observé en
    # démo entre H1 et H4) ou "disabled" (comportement d'origine -- chaque
    # style agit indépendamment, hedging possible). `"disabled"` par défaut
    # si absent du profil (aucune régression pour un profil existant qui ne
    # connaît pas encore ce champ).
    conflict = profile.get("conflict_resolution", {})
    live["conflict_resolution"] = conflict.get("mode", "disabled")

    # PLAFOND D'EXPOSITION CUMULÉE (19/09, voir
    # mt5_connector.py::_cumulative_exposure_refusal) : borne la SOMME du
    # risque pire-cas de toutes les positions ouvertes simultanément. Devenu
    # nécessaire avec le budget de risque dynamique (option B), qui peut
    # structurellement dépasser max_risk_pct_per_trade quand plusieurs
    # styles ouvrent l'un après l'autre dans le même sens -- ce que
    # l'ancienne répartition fixe (option A) rendait impossible par
    # construction. Désactivé si absent du profil (aucune régression pour
    # un profil existant qui ne connaît pas encore ce champ).
    cumulative = profile.get("cumulative_exposure", {})
    live["cumulative_exposure_enabled"] = bool(cumulative.get("enabled", False))
    if live["cumulative_exposure_enabled"]:
        live["cumulative_exposure_max_pct"] = cumulative.get("max_pct")

    log.info(
        f"Profil de risque '{profile_name}' ({profile.get('name', profile_name)}) appliqué : "
        f"risque/trade={live.get('max_risk_pct_per_trade')}, "
        f"drawdown total={live.get('max_account_drawdown_pct')} (mode={live.get('total_drawdown_mode')}), "
        f"perte quotidienne={'activée à ' + str(live.get('daily_loss_max_pct')) if live['daily_loss_enabled'] else 'désactivée'}, "
        f"coordination inter-styles={live['conflict_resolution']}, "
        f"exposition cumulée={'plafonnée à ' + str(live.get('cumulative_exposure_max_pct')) if live['cumulative_exposure_enabled'] else 'non plafonnée'}."
    )
    return cfg


def current_reset_boundary_utc(now_utc: datetime, reset_time_local: str, tz_name: str) -> datetime:
    """Instant UTC (aware) du DERNIER passage de l'heure de reset -- en
    heure LOCALE de la firme (ex: "00:00" / "Europe/Prague" pour FTMO), pas
    un champ UTC figé : la conversion via `zoneinfo` (bibliothèque
    standard, base de données IANA) applique automatiquement le bon
    décalage (hiver/été) pour LA DATE CONCERNÉE -- aucun ajustement manuel
    2x/an, aucune dérive.

    `now_utc` DOIT être aware (tzinfo défini, UTC) -- sinon la conversion
    vers `tz_name` n'a pas de sens.
    """
    if now_utc.tzinfo is None:
        raise ValueError("now_utc doit être timezone-aware (UTC)")
    parts = reset_time_local.split(":")
    if len(parts) != 2 or not all(p.isdigit() for p in parts):
        raise ValueError(
            f"reset_time_local invalide : {reset_time_local!r} -- format attendu \"HH:MM\""
        )
    hour, minute = int(parts[0]), int(parts[1])
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        raise ValueError(
            f"reset_time_local invalide : {reset_time_local!r} -- heure/minute hors bornes"
        )
    tz = ZoneInfo(tz_name)
    local_now = now_utc.astimezone(tz)
    candidate_local = local_now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if candidate_local > local_now:
        candidate_local -= timedelta(days=1)
    return candidate_local.astimezone(ZoneInfo("UTC"))
