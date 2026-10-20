"""
dashboard.py
=============
Vue d'ensemble simple de ce qui se passe RÉELLEMENT dans le système --
avec la population évolutive, l'ensemble multi-styles, la recherche
adaptative, le stress-test et le filet de sécurité qui tournent tous en
même temps, lire les logs ligne par ligne ne suffit plus pour se faire une
idée d'ensemble en un coup d'œil.

Génère un simple fichier HTML STATIQUE (`reports/dashboard.html`), régénéré
à chaque cycle d'entraînement ET à chaque décision de démo -- ouvrez-le
dans un navigateur (Ctrl+R pour rafraîchir) pendant que le système tourne.
Pas de serveur, pas de dépendance : lit trois petits fichiers JSON déjà
écrits ailleurs (training_status.json, live_status.json, reliability.json)
et les met en forme.
"""
from __future__ import annotations
import html
import json
import os
import threading
import time

from src.io_utils import read_json_safe

# EVOLUTION (continuous_trainer.py) et la boucle de démo (demo_trader.py)
# tournent dans des threads DIFFÉRENTS et peuvent toutes les deux appeler
# write_training_status/write_live_status -> même fichier
# settings_snapshot.json, même fichier dashboard.html. Sans ce verrou, deux
# écritures concurrentes pourraient produire un fichier tronqué/corrompu ou
# une lecture (le navigateur) au milieu d'une écriture. Un Lock simple
# suffit : les fonctions internes (_render_locked, _write_settings_snapshot)
# supposent TOUJOURS que l'appelant détient déjà le verrou, jamais
# d'acquisition imbriquée.
_file_lock = threading.Lock()

REPORTS_DIR = "reports"
HISTORY_PATH = os.path.join(REPORTS_DIR, "score_history.jsonl")
HISTORY_MAX_ENTRIES = 2000          # borne la taille du fichier sur un système qui tourne H24 pendant des mois
HISTORY_PRUNE_CHECK_EVERY = 50      # ne vérifie/tronque le fichier qu'un cycle sur N (append-only le reste du temps)
HISTORY_PRUNE_SIZE_HINT_BYTES = 2_000_000  # évite même un stat coûteux si le fichier est visiblement encore petit
_append_count_since_prune = 0
RENDER_DEBOUNCE_SECONDS = 30  # évite de régénérer le HTML complet plus d'1x/30s quand les données n'ont pas changé
_last_render_sig = None
_last_render_time = 0.0
TRAINING_STATUS_PATH = os.path.join(REPORTS_DIR, "training_status.json")
LIVE_STATUS_PATH = os.path.join(REPORTS_DIR, "live_status.json")
RELIABILITY_PATH = os.path.join(REPORTS_DIR, "reliability.json")
SETTINGS_PATH = os.path.join(REPORTS_DIR, "settings_snapshot.json")
DASHBOARD_PATH = os.path.join(REPORTS_DIR, "dashboard.html")
HOURLY_REPORT_PATH = os.path.join(REPORTS_DIR, "hourly_report.json")
MARKET_STATUS_PATH = os.path.join("data", "cache", "market_status.json")
SPREAD_PATH = os.path.join("data", "cache", "live_spread.json")
ACCOUNT_GUARD_PATH = os.path.join("data", "account_guard_state.json")


def _read_json(path: str) -> dict:
    # Factorisé dans src/io_utils.py (tâche de nettoyage, audit
    # institutionnel) -- auparavant dupliquée à l'identique ici, dans
    # src/continuous_trainer.py et src/demo_trader.py.
    return read_json_safe(path)


def write_training_status(status: dict, cfg: dict | None = None):
    with _file_lock:
        os.makedirs(REPORTS_DIR, exist_ok=True)
        with open(TRAINING_STATUS_PATH, "w", encoding="utf-8") as f:
            json.dump(status, f, indent=2)
        _append_history_locked(status)
        if cfg is not None:
            _write_settings_snapshot_locked(cfg)
        _render_locked()


def _append_history_locked(status: dict):
    """Journal APPEND-ONLY (une ligne JSON par cycle) du score de CHAQUE
    style à CHAQUE génération -- contrairement à `champion_<TF>/meta.json`
    (uniquement l'état ACTUEL, écrasé à chaque nouveau champion), c'est ce
    fichier qui permet de retracer l'évolution génération par génération
    dans le graphique du tableau de bord (voir _history_chart_svg). Ne lève
    jamais d'exception visible (même logique que le reste du module) --
    l'historique est un bonus d'affichage, jamais un chemin critique.
    Suppose que l'appelant détient déjà `_file_lock`."""
    try:
        entry = {
            "generation": status.get("generation"),
            "styles": {tf: s.get("score") for tf, s in status.get("styles", {}).items()},
        }
        with open(HISTORY_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
        _prune_history_if_needed_locked()
    except Exception:
        pass


def _prune_history_if_needed_locked():
    """Tronque `score_history.jsonl` à HISTORY_MAX_ENTRIES lignes -- mais
    seulement de temps en temps (tous les HISTORY_PRUNE_CHECK_EVERY appels),
    puisque l'écrasement complet du fichier est justement ce que l'append
    ci-dessus évite à chaque cycle. Un léger dépassement transitoire de
    HISTORY_MAX_ENTRIES entre deux prunes est sans conséquence (borne
    approximative, pas stricte)."""
    global _append_count_since_prune
    _append_count_since_prune += 1
    if _append_count_since_prune < HISTORY_PRUNE_CHECK_EVERY:
        return
    _append_count_since_prune = 0
    try:
        if os.path.getsize(HISTORY_PATH) < HISTORY_PRUNE_SIZE_HINT_BYTES:
            return
    except OSError:
        return
    with open(HISTORY_PATH, encoding="utf-8") as f:
        lines = f.readlines()
    if len(lines) > HISTORY_MAX_ENTRIES:
        with open(HISTORY_PATH, "w", encoding="utf-8") as f:
            f.writelines(lines[-HISTORY_MAX_ENTRIES:])


def _read_history() -> list[dict]:
    if not os.path.exists(HISTORY_PATH):
        return []
    entries = []
    try:
        with open(HISTORY_PATH, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entries.append(json.loads(line))
                except Exception:
                    continue
    except Exception:
        return []
    return entries


def write_live_status(status: dict, cfg: dict | None = None):
    with _file_lock:
        os.makedirs(REPORTS_DIR, exist_ok=True)
        with open(LIVE_STATUS_PATH, "w", encoding="utf-8") as f:
            json.dump(status, f, indent=2)
        if cfg is not None:
            _write_settings_snapshot_locked(cfg)
        _render_locked()


def _write_settings_snapshot_locked(cfg: dict):
    """Extrait les réglages les plus utiles à voir d'un coup d'œil (pas
    toute la config) -- écrit à part pour que render() reste indépendant
    de la présence ou non de `cfg` à chaque appel. Suppose que l'appelant
    détient déjà `_file_lock` (jamais appelée directement de l'extérieur)."""
    try:
        snapshot = {
            "symbol": cfg.get("live", {}).get("symbol"),
            "dry_run": cfg.get("live", {}).get("dry_run"),
            "ensemble": cfg.get("live", {}).get("ensemble"),
            "risk_guard": cfg.get("live", {}).get("risk_guard"),
            "poll_seconds": cfg.get("live", {}).get("poll_seconds"),
            "learn_stop_loss": cfg.get("agent", {}).get("learn_stop_loss"),
            "stop_loss_pct": cfg.get("live", {}).get("stop_loss_pct"),
            "timeframe_pool": cfg.get("data", {}).get("timeframe_pool"),
            "population_size": cfg.get("continuous", {}).get("population_size"),
            "min_generations_before_demo": cfg.get("validation", {}).get("min_generations_before_demo"),
            "min_trades_for_confidence": cfg.get("reliability", {}).get("min_trades_for_confidence"),
            "market_hours_use_mt5": cfg.get("market_hours", {}).get("use_mt5_detection", True),
            "settings_port": cfg.get("dashboard", {}).get("settings_port", 8765),
            # ÉTIQUETTE DE DÉPLOIEMENT (ex: "V4") : purement informative --
            # `label` est choisi à la main par l'utilisateur à chaque mise en
            # prod significative, `start_generation` est la génération lue au
            # moment de ce déploiement. Sert à afficher "V4 (+N depuis
            # déploiement)" au lieu du seul numéro de cycle absolu, qui ne
            # dit rien de quand la version actuelle a été mise en route.
            "deployment_label": cfg.get("deployment", {}).get("label"),
            "deployment_start_generation": cfg.get("deployment", {}).get("start_generation"),
        }
        os.makedirs(REPORTS_DIR, exist_ok=True)
        with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
            json.dump(snapshot, f, indent=2)
    except Exception:
        pass


_CHART_COLORS = ["#4caf7d", "#4f9fd6", "#b784d1", "#d4a24c", "#d1706a", "#8f8f4f", "#5fb9b0"]


def _history_chart_svg(entries: list[dict]) -> str:
    """Graphique SVG en ligne, INLINE (aucune dépendance JS, aucune requête
    réseau) du score de CHAQUE style au fil des générations -- même
    principe que le graphique du rapport ponctuel déjà livré, mais LIVE :
    reconstruit à chaque régénération du tableau de bord à partir de
    `reports/score_history.jsonl`, donc toujours à jour au prochain
    rafraîchissement de la page (voir le <meta refresh> dans le head)."""
    if len(entries) < 2:
        return "<p class='dim'>Pas encore assez de cycles pour tracer une courbe.</p>"

    if len(entries) > 300:
        step = len(entries) // 300 + 1
        entries = entries[::step] + [entries[-1]]

    styles = sorted({tf for e in entries for tf in e.get("styles", {})})
    gens = [e["generation"] for e in entries if e.get("generation") is not None]
    if not gens:
        return "<p class='dim'>Pas encore assez de cycles pour tracer une courbe.</p>"
    scores = [v for e in entries for v in e.get("styles", {}).values() if v is not None]
    if not scores:
        return "<p class='dim'>Pas encore assez de cycles pour tracer une courbe.</p>"

    x_min, x_max = min(gens), max(gens)
    y_min, y_max = min(scores), max(scores)
    if x_max == x_min:
        x_max = x_min + 1
    pad = (y_max - y_min) * 0.1 or 0.5
    y_min, y_max = y_min - pad, y_max + pad

    W, H, pad_l, pad_r, pad_t, pad_b = 760, 260, 40, 12, 12, 24
    gw, gh = W - pad_l - pad_r, H - pad_t - pad_b

    def X(g):
        return pad_l + (g - x_min) / (x_max - x_min) * gw

    def Y(v):
        return pad_t + gh - (v - y_min) / (y_max - y_min) * gh

    parts = [f'<svg viewBox="0 0 {W} {H}" style="width:100%;height:auto;display:block;" '
             f'font-family="IBM Plex Mono, monospace">']
    for v in {round(y_min + pad, 2), 0, round(y_max - pad, 2)}:
        y = Y(v)
        parts.append(f'<line x1="{pad_l}" x2="{W - pad_r}" y1="{y:.1f}" y2="{y:.1f}" '
                      f'stroke="var(--border)" stroke-width="1" stroke-dasharray="{"0" if v == 0 else "3 3"}"/>')
        parts.append(f'<text x="4" y="{y + 4:.1f}" font-size="10" fill="var(--text-dim)">{v:+.1f}</text>')

    legend = []
    for i, tf in enumerate(styles):
        color = _CHART_COLORS[i % len(_CHART_COLORS)]
        pts = [(e["generation"], e["styles"].get(tf)) for e in entries if e.get("styles", {}).get(tf) is not None]
        pts.sort(key=lambda p: p[0])
        if len(pts) >= 2:
            d = " ".join(f'{"M" if i == 0 else "L"}{X(g):.1f},{Y(v):.1f}' for i, (g, v) in enumerate(pts))
            parts.append(f'<path d="{d}" fill="none" stroke="{color}" stroke-width="2"/>')
        if pts:
            g, v = pts[-1]
            parts.append(f'<circle cx="{X(g):.1f}" cy="{Y(v):.1f}" r="3.5" fill="{color}"/>')
        legend.append(f'<span style="display:inline-flex;align-items:center;gap:5px;margin-right:14px;">'
                      f'<span style="width:10px;height:3px;background:{color};display:inline-block;border-radius:2px;"></span>{tf}</span>')
    parts.append(f'<text x="{pad_l}" y="{H - 4}" font-size="10" fill="var(--text-dim)">gén. {x_min}</text>')
    parts.append(f'<text x="{W - pad_r - 50}" y="{H - 4}" font-size="10" fill="var(--text-dim)">gén. {x_max}</text>')
    parts.append("</svg>")
    return f'<div style="margin-bottom:8px;font-size:12px;">{"".join(legend)}</div>' + "".join(parts)


def _pill(label: str, tone: str) -> str:
    return f"<span class='pill pill-{tone}'>{label}</span>"


def _style_rows(training: dict) -> str:
    rows = []
    for tf, s in sorted(training.get("styles", {}).items(), key=lambda kv: -kv[1].get("score", 0)):
        badge = _pill("éligible démo", "ok") if s.get("passes_validation") else _pill("en apprentissage", "muted")
        score = s.get("score", 0)
        rows.append(
            f"<tr><td class='mono'>{tf}</td><td class='num'>{score:+.3f}</td>"
            f"<td class='num'>{s.get('generation', '?')}</td><td>{badge}</td></tr>"
        )
    return "\n".join(rows) or "<tr><td colspan='4' class='dim'>Aucun style entraîné pour l'instant.</td></tr>"


def _position_rows(live: dict) -> str:
    """Une ligne par position ACTIVE (exposition finale non nulle pour ce
    style), triées par PnL flottant décroissant -- remplace l'ancien
    affichage à position unique (`final_exposure`/`n_eligible_styles`
    globaux) devenu incorrect depuis le passage au multi-position
    indépendant par style (voir demo_trader.py, `write_live_status`)."""
    positions = [p for p in live.get("positions", []) if abs(p.get("final_target", 0) or 0) > 1e-9]
    if not positions:
        return "<tr><td colspan='6' class='dim'>Aucune position active pour l'instant.</td></tr>"
    positions.sort(key=lambda p: p.get("profit") if p.get("profit") is not None else float("-inf"), reverse=True)
    rows = []
    for p in positions:
        direction = p.get("direction") or 0
        sens = "ACHAT" if direction > 0 else "VENTE" if direction < 0 else "?"
        volume = f"{p['volume']:.2f}" if p.get("volume") is not None else "?"
        profit = p.get("profit")
        profit_str = f"{profit:+.2f}$" if profit is not None else "non mesuré"
        guard = _pill("filet actif", "warn") if p.get("risk_guard_triggered") else ""
        rows.append(
            f"<tr><td class='mono'>{p.get('style', '?')}</td><td class='num'>{p.get('generation', '?')}</td>"
            f"<td class='mono'>{sens}</td><td class='num'>{volume}</td>"
            f"<td class='num'>{profit_str}</td><td>{guard}</td></tr>"
        )
    return "\n".join(rows)


def _reliability_block(reliability: dict) -> str:
    """Une entrée par style (voir reliability_tracker.py -- chaque style
    live est comparé à SON PROPRE backtest walk-forward, plus d'agrégat
    global unique)."""
    styles = reliability.get("styles") if reliability else None
    if not styles:
        return "<p class='dim'>Pas encore de rapport de fiabilité (aucun trade live enregistré).</p>"
    blocks = []
    for style, style_report in styles.items():
        verdict = style_report.get("verdict", "")
        tone = "warn" if "ÉCART" in verdict else ("muted" if not style_report.get("confident") else "ok")
        blocks.append(
            f"<p class='verdict verdict-{tone}'><strong>{html.escape(str(style))}</strong> : "
            f"{html.escape(str(verdict))}</p>"
        )
    return "\n".join(blocks)


def render():
    """Point d'entrée PUBLIC (appelé isolément au démarrage par
    autonomous_agent.py) -- acquiert `_file_lock` lui-même. Ne JAMAIS
    appeler depuis write_training_status/write_live_status (qui détiennent
    déjà le verrou : utilisent _render_locked() directement, sinon
    deadlock avec un Lock non réentrant)."""
    with _file_lock:
        _render_locked()


def write_hourly_report(report: dict):
    """Enregistre le dernier rapport horaire compilé (voir la conversation
    de supervision -- Claude compile ce rapport à la main chaque heure et
    l'appelle depuis un script ponctuel, PAS depuis le process d'entraînement
    lui-même) pour qu'il apparaisse directement sur ce tableau de bord, en
    plus de l'Artifact publié séparément -- demande explicite de
    l'utilisateur pour ne pas avoir à jongler entre deux endroits.
    `report` attend : timestamp (unix), generation, headline (résumé 1-2
    phrases), highlights (liste de points clés courts), forecast (texte),
    verdict (texte), artifact_url (lien vers le rapport complet illustré).
    Appelé depuis un script Python à part (autre process) : le verrou
    `_file_lock` de CE module ne protège donc pas contre une écriture
    concurrente du process d'entraînement principal -- risque accepté
    (rare, sans conséquence : la prochaine régénération normale, en fin de
    cycle, écrase de toute façon avec un état cohérent)."""
    with _file_lock:
        os.makedirs(REPORTS_DIR, exist_ok=True)
        with open(HOURLY_REPORT_PATH, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
        _render_locked()


def _hourly_report_block(report: dict) -> str:
    if not report:
        return "<p class='dim'>Aucun rapport horaire compilé pour l'instant.</p>"
    age_min = (time.time() - report["timestamp"]) / 60.0 if report.get("timestamp") else None
    age_str = f"il y a {age_min:.0f} min" if age_min is not None else ""
    highlights = "".join(f"<li>{html.escape(str(h))}</li>" for h in report.get("highlights", []))
    link = (f'<p class="sub"><a href="{html.escape(str(report["artifact_url"]), quote=True)}" '
            f'style="color:var(--accent);" target="_blank" rel="noopener">Rapport complet illustré '
            f'(historique, graphique, avis détaillé)</a></p>'
            if report.get("artifact_url") else "")
    return f"""
    <p class="sub" style="margin-top:0;">Génération {html.escape(str(report.get('generation', '?')))} &middot; {html.escape(age_str)}</p>
    <p style="margin:8px 0;">{html.escape(str(report.get('headline', '')))}</p>
    <ul style="margin:8px 0; padding-left:20px; font-size:13.5px;">{highlights}</ul>
    <p class="sub"><strong>Prévisions :</strong> {html.escape(str(report.get('forecast', '')))}</p>
    <p class="sub"><strong>Avis :</strong> {html.escape(str(report.get('verdict', '')))}</p>
    {link}"""


def _render_locked():
    """Régénère reports/dashboard.html à partir des 3 fichiers JSON déjà
    écrits par continuous_trainer.py, demo_trader.py et
    reliability_tracker.py. Ne lève jamais d'exception visible (un
    dashboard qui plante ne doit jamais interrompre l'entraînement/la
    démo) -- une erreur reste journalisée mais silencieuse pour l'appelant.
    Suppose que l'appelant détient déjà `_file_lock`.
    """
    global _last_render_sig, _last_render_time
    try:
        training = _read_json(TRAINING_STATUS_PATH)
        live = _read_json(LIVE_STATUS_PATH)
        reliability = _read_json(RELIABILITY_PATH)
        settings = _read_json(SETTINGS_PATH)
        market = _read_json(MARKET_STATUS_PATH)
        spread = _read_json(SPREAD_PATH)
        account_guard = _read_json(ACCOUNT_GUARD_PATH)
        hourly_report = _read_json(HOURLY_REPORT_PATH)

        # Debounce : régénérer le HTML complet (SVG de l'historique inclus)
        # coûte cher si appelé à chaque cycle d'entraînement/décision de
        # démo. On saute la régénération quand aucune des sources JSON n'a
        # changé depuis le dernier rendu ET que ce dernier date de moins de
        # RENDER_DEBOUNCE_SECONDS -- le fichier déjà sur disque reste donc
        # affiché tel quel (légèrement périmé, jamais plus de
        # RENDER_DEBOUNCE_SECONDS). Un vrai changement de données force
        # toujours un rendu immédiat, quel que soit le temps écoulé.
        sig = hash(json.dumps(
            [training, live, reliability, settings, market, spread, account_guard, hourly_report],
            sort_keys=True, default=str))
        now = time.time()
        if sig == _last_render_sig and (now - _last_render_time) < RENDER_DEBOUNCE_SECONDS:
            return
        _last_render_sig = sig
        _last_render_time = now

        history_chart = _history_chart_svg(_read_history())

        is_open = market.get("is_open")
        market_pill = _pill("MARCHÉ OUVERT", "ok") if is_open is True \
            else _pill("MARCHÉ FERMÉ", "warn") if is_open is False \
            else _pill("statut inconnu", "muted")
        market_age = ""
        if market.get("checked_at"):
            age_min = (time.time() - market["checked_at"]) / 60.0
            market_age = f"<span class='dim'>vérifié il y a {age_min:.0f} min (cotations MT5)</span>"
        spread_str = f"{spread['spread_pct']:.4%}" if spread.get("spread_pct") is not None else "non mesuré"

        deployment_prefix = ""
        dep_label = settings.get("deployment_label")
        if dep_label:
            # ALIAS LOCAL (18/09) : cette fonction assigne plus bas une
            # variable locale nommée `html` (le HTML final assemblé), ce qui
            # masque le MODULE `html` importé en haut du fichier pour TOUTE
            # la fonction (portée déterminée à la compilation en Python,
            # pas ligne par ligne) -- `html.escape` ici levait
            # UnboundLocalError avant même d'atteindre cette assignation
            # locale plus bas. Import local sous un autre nom pour éviter
            # le conflit, sans toucher à la variable `html` existante.
            import html as _html_mod
            dep_start = settings.get("deployment_start_generation")
            current_gen = training.get("generation")
            if isinstance(dep_start, int) and isinstance(current_gen, int):
                deployment_prefix = f"{_html_mod.escape(str(dep_label))} &middot; +{max(current_gen - dep_start, 0)} &middot; "
            else:
                deployment_prefix = f"{_html_mod.escape(str(dep_label))} &middot; "

        plateau_note = (f"{_pill('plateau', 'warn')} " if training.get("plateau") else "")
        risk_note = (f"{_pill('filet de sécurité actif', 'warn')} " if live.get("risk_guard_triggered") else "")
        blended_stop_pct = live.get("blended_stop_pct")
        stop_pct_str = (f"{blended_stop_pct:.2%} (choisi par l'agent)" if blended_stop_pct is not None
                        else f"{settings.get('stop_loss_pct', 0):.2%} (fixe, config)"
                        if settings.get("stop_loss_pct") else "aucun")

        account_guard_banner = ""
        if account_guard.get("halted"):
            halted_age = ""
            if account_guard.get("halted_at"):
                age_h = (time.time() - account_guard["halted_at"]) / 3600.0
                halted_age = f" (il y a {age_h:.1f} h)"
            account_guard_banner = f"""
  <div class="card" style="border-color:#c0392b;background:rgba(192,57,43,0.08);">
    <h2 style="color:#c0392b;">⛔ Coupe-circuit de compte DÉCLENCHÉ{halted_age}</h2>
    <p class="sub">Équité tombée à <strong>{account_guard.get('equity_at_halt', 0):.2f}</strong>,
    soit <strong>{account_guard.get('drawdown_at_halt', 0):.1%}</strong> sous son pic
    ({account_guard.get('peak_equity', 0):.2f}). Aucun ordre n'est envoyé tant que ceci n'est
    pas résolu manuellement (voir src/account_guard.py::reset()). L'entraînement continue
    normalement en arrière-plan.</p>
  </div>"""

        html = f"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta http-equiv="refresh" content="60">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Barlow+Semi+Condensed:wght@500;600;700&family=IBM+Plex+Mono:wght@400;500;600&display=swap">
<title>Poste de contrôle XAUUSD</title>
<style>
  :root {{
    --bg: #eef1f4;
    --surface: #ffffff;
    --surface-2: #e4e8ec;
    --border: #d3d9de;
    --text: #1c2128;
    --text-dim: #5b6470;
    --accent: #a8792e;
    --accent-soft: #f3e6cf;
    --ok: #2f7d4f;
    --ok-soft: #dcf0e3;
    --warn: #9a6a12;
    --warn-soft: #f5e6c4;
    --critical: #a33a2e;
  }}
  @media (prefers-color-scheme: dark) {{
    :root:not([data-theme="light"]) {{
      --bg: #14161c;
      --surface: #1c1f27;
      --surface-2: #262a34;
      --border: #333947;
      --text: #eceae3;
      --text-dim: #9298a4;
      --accent: #d4a24c;
      --accent-soft: #3a3021;
      --ok: #6fcf8f;
      --ok-soft: #1f3327;
      --warn: #e0a339;
      --warn-soft: #3a3121;
      --critical: #e3695c;
    }}
  }}
  :root[data-theme="dark"] {{
    --bg: #14161c;
    --surface: #1c1f27;
    --surface-2: #262a34;
    --border: #333947;
    --text: #eceae3;
    --text-dim: #9298a4;
    --accent: #d4a24c;
    --accent-soft: #3a3021;
    --ok: #6fcf8f;
    --ok-soft: #1f3327;
    --warn: #e0a339;
    --warn-soft: #3a3121;
    --critical: #e3695c;
  }}

  * {{ box-sizing: border-box; }}
  body {{
    font-family: "IBM Plex Mono", ui-monospace, monospace;
    background: var(--bg); color: var(--text);
    margin: 0; padding: 28px 20px; line-height: 1.5;
  }}
  .wrap {{ max-width: 980px; margin: 0 auto; }}
  h1 {{
    font-family: "Barlow Semi Condensed", sans-serif;
    font-size: 26px; font-weight: 700; letter-spacing: 0.3px;
    margin: 0 0 2px 0; text-wrap: balance;
  }}
  .eyebrow {{
    font-size: 11px; text-transform: uppercase; letter-spacing: 1.4px;
    color: var(--accent); font-weight: 600; margin-bottom: 6px;
  }}
  .updated {{ color: var(--text-dim); font-size: 12.5px; margin-bottom: 24px; }}

  .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(230px, 1fr)); gap: 14px; margin-bottom: 14px; }}
  .card {{
    background: var(--surface); border: 1px solid var(--border);
    border-radius: 10px; padding: 18px 20px;
  }}
  .card + .card {{ margin-top: 14px; }}
  .card h2 {{
    font-family: "Barlow Semi Condensed", sans-serif;
    font-size: 13px; text-transform: uppercase; letter-spacing: 1px;
    color: var(--text-dim); font-weight: 600; margin: 0 0 14px 0;
  }}
  .metric {{
    font-family: "Barlow Semi Condensed", sans-serif;
    font-size: 30px; font-weight: 700; font-variant-numeric: tabular-nums;
    line-height: 1.1;
  }}
  .metric-label {{ font-size: 12px; color: var(--text-dim); margin-top: 2px; }}
  .dim {{ color: var(--text-dim); }}
  .sub {{ font-size: 13px; color: var(--text-dim); margin: 10px 0 0 0; }}

  table {{ width: 100%; border-collapse: collapse; font-size: 13.5px; font-variant-numeric: tabular-nums; }}
  td, th {{ padding: 9px 10px; text-align: left; border-bottom: 1px solid var(--border); }}
  th {{ font-family: "Barlow Semi Condensed", sans-serif; font-size: 11.5px; text-transform: uppercase;
        letter-spacing: 0.6px; color: var(--text-dim); font-weight: 600; }}
  tr:last-child td {{ border-bottom: none; }}
  td.mono {{ font-weight: 600; }}
  td.num {{ text-align: right; font-variant-numeric: tabular-nums; }}
  th:nth-child(2), th:nth-child(3) {{ text-align: right; }}

  .settings-table td:first-child {{ color: var(--text-dim); width: 55%; }}
  .settings-table td:last-child {{ font-weight: 600; }}

  .pill {{
    display: inline-block; font-size: 11px; font-weight: 600; letter-spacing: 0.4px;
    text-transform: uppercase; padding: 3px 9px; border-radius: 20px;
  }}
  .pill-ok {{ background: var(--ok-soft); color: var(--ok); }}
  .pill-warn {{ background: var(--warn-soft); color: var(--warn); }}
  .pill-muted {{ background: var(--surface-2); color: var(--text-dim); }}

  .verdict {{ font-size: 14px; margin: 0; padding: 12px 14px; border-radius: 8px; border: 1px solid var(--border); }}
  .verdict-ok {{ background: var(--ok-soft); color: var(--ok); border-color: transparent; }}
  .verdict-warn {{ background: var(--warn-soft); color: var(--warn); border-color: transparent; }}
  .verdict-muted {{ background: var(--surface-2); color: var(--text-dim); border-color: transparent; }}
</style>
</head>
<body>
<div class="wrap">
  <div class="eyebrow">Poste de contrôle &middot; évolution continue &amp; démo</div>
  <h1>{settings.get("symbol", "XAUUSD")} — état du système</h1>
  <div class="updated">Régénéré le {time.strftime("%Y-%m-%d %H:%M:%S")} — ouvrez ce fichier dans un navigateur,
  rafraîchissez (Ctrl+R) pour voir l'état actuel. Cette page est en LECTURE SEULE --
  pour modifier des réglages en direct sans redémarrer, ouvrez
  <a href="http://127.0.0.1:{settings.get("settings_port", 8765)}/" style="color:var(--accent);">
  http://127.0.0.1:{settings.get("settings_port", 8765)}/</a>.</div>
{account_guard_banner}
  <div class="grid">
    <div class="card">
      <h2>Évolution continue</h2>
      <div class="metric">{deployment_prefix}Gén. {training.get("generation", "?")}</div>
      <div class="metric-label">meilleur score jamais atteint : {training.get("best_ever_score", 0):+.3f}</div>
      <p class="sub">{plateau_note}{training.get("cycles_since_improvement", 0)} cycle(s) sans amélioration</p>
    </div>

    <div class="card">
      <h2>Démo — positions actives</h2>
      <div class="metric">{sum(1 for p in live.get("positions", []) if abs(p.get("final_target", 0) or 0) > 1e-9)}</div>
      <div class="metric-label">position(s) ouverte(s), une par style indépendant</div>
      <p class="sub">{risk_note}{live.get("n_eligible_styles", 0)} style(s) éligible(s) à la décision</p>
      <p class="sub">Stop-loss : <strong>{stop_pct_str}</strong></p>
    </div>

    <div class="card">
      <h2>Marché</h2>
      <div class="metric">{market_pill}</div>
      <div class="metric-label">{market_age or "en attente d'une première mesure MT5"}</div>
      <p class="sub">Spread réel mesuré : <strong>{spread_str}</strong></p>
    </div>
  </div>

  <div class="card">
    <h2>Positions actives (triées par PnL flottant décroissant)</h2>
    <table>
      <tr><th>Style</th><th>Génération</th><th>Sens</th><th>Volume</th><th>PnL flottant</th><th>Statut</th></tr>
      {_position_rows(live)}
    </table>
  </div>

  <div class="card">
    <h2>Styles / lignées entraînées</h2>
    <table>
      <tr><th>Style</th><th>Score</th><th>Génération</th><th>Statut</th></tr>
      {_style_rows(training)}
    </table>
  </div>

  <div class="card">
    <h2>Progression par génération</h2>
    {history_chart}
  </div>

  <div class="card">
    <h2>Dernier rapport horaire</h2>
    {_hourly_report_block(hourly_report)}
  </div>

  <div class="card">
    <h2>Fiabilité backtest vs réel</h2>
    {_reliability_block(reliability)}
    <p class="sub">{sum(s.get("n_live_trades", 0) for s in reliability.get("styles", {}).values())} trade(s) réel(s) enregistré(s), tous styles confondus
    &middot; seuil de confiance : {reliability.get("min_trades_for_confidence", "?")} trades (par style).</p>
  </div>

  <div class="card">
    <h2>Réglages actifs</h2>
    <table class="settings-table">
      <tr><td>Dry-run (aucun ordre réel envoyé)</td><td>{"oui" if settings.get("dry_run") else "non"}</td></tr>
      <tr><td>Ensemble multi-styles</td><td>{"activé" if settings.get("ensemble") else "désactivé"}</td></tr>
      <tr><td>Filet de sécurité indépendant</td><td>{"activé" if settings.get("risk_guard") else "désactivé"}</td></tr>
      <tr><td>Stop-loss décidé par l'agent</td><td>{"activé (trader, pas règle fixe)" if settings.get("learn_stop_loss") else f"désactivé (fixe : {settings.get('stop_loss_pct', 0):.2%})"}</td></tr>
      <tr><td>Détection marché via MT5</td><td>{"activée" if settings.get("market_hours_use_mt5") else "désactivée"}</td></tr>
      <tr><td>Pool de styles</td><td>{", ".join(settings.get("timeframe_pool") or []) or "?"}</td></tr>
      <tr><td>Lignées par style (population)</td><td>{settings.get("population_size", "?")}</td></tr>
      <tr><td>Générations minimales avant démo</td><td>{settings.get("min_generations_before_demo", "?")}</td></tr>
    </table>
  </div>
</div>
</body>
</html>"""
        os.makedirs(REPORTS_DIR, exist_ok=True)
        with open(DASHBOARD_PATH, "w", encoding="utf-8") as f:
            f.write(html)
    except Exception:
        pass  # un dashboard cassé ne doit jamais interrompre l'entraînement/la démo
