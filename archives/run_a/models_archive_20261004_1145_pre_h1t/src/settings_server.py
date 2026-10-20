"""
settings_server.py
====================
Petit serveur HTTP LOCAL (aucune dépendance en plus de la bibliothèque
standard) qui permet de MODIFIER un sous-ensemble volontairement restreint
et sûr de réglages opérationnels EN DIRECT depuis le tableau de bord, sans
redémarrer le script.

SOUS-ENSEMBLE ÉDITABLE (voir WHITELIST ci-dessous) : uniquement des leviers
opérationnels (risque, fréquence de décision/cycle, notifications, dry-run)
-- JAMAIS l'architecture du modèle, l'espace d'action, les hyperparamètres
ou quoi que ce soit qui casserait le warm-start ou changerait la façon dont
l'agent apprend. Ces réglages-là restent à éditer directement dans
config/autonomous.yaml (et nécessitent un redémarrage, comme documenté
ailleurs dans ce fichier).

DOUBLE PERSISTANCE : chaque changement modifie IMMÉDIATEMENT le dictionnaire
de config PARTAGÉ en mémoire (le même objet `cfg` que l'entraînement continu
et la boucle de démo utilisent déjà) -- effet visible au cycle/à la décision
suivante, PAS besoin de redémarrer -- ET persiste dans
`data/settings_overrides.json`, réappliqué automatiquement à chaque
lancement (voir `load_overrides_into`).

SÉCURITÉ : par défaut, ce serveur n'écoute QUE sur 127.0.0.1 (jamais exposé
au-delà de la machine qui l'exécute) -- aucune authentification, parce qu'il
n'est alors jamais atteignable depuis l'extérieur. Mettre `dashboard.
lan_access: true` dans la config l'ouvre au réseau local (pour consulter le
tableau de bord depuis un téléphone/autre PC chez vous) -- dans ce cas, un
JETON généré une fois et persisté dans data/dashboard_token.txt devient
OBLIGATOIRE (?token=... dans l'URL) pour toute requête qui ne vient PAS de
127.0.0.1 : ce serveur permet de MODIFIER des réglages (dry-run, seuils de
risque...), donc l'ouvrir au Wi-Fi sans un minimum de protection laisserait
n'importe quel appareil du réseau (invité, objet connecté compromis...) les
changer. Pour un accès depuis l'extérieur de la maison, utilisez un tunnel
de confiance (SSH, Tailscale...), jamais une redirection de port ouverte sur
internet -- `lan_access` ne couvre QUE le réseau local.
"""
from __future__ import annotations
import json
import logging
import os
import secrets
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

log = logging.getLogger("settings_server")

OVERRIDES_PATH = os.path.join("data", "settings_overrides.json")
TOKEN_PATH = os.path.join("data", "dashboard_token.txt")


def _get_or_create_token() -> str:
    """Jeton STABLE d'un lancement à l'autre (persisté sur disque, comme
    data/settings_overrides.json) -- sans ça, l'URL à retenir/mettre en
    favori sur votre téléphone changerait à chaque redémarrage."""
    if os.path.exists(TOKEN_PATH):
        try:
            token = open(TOKEN_PATH, encoding="utf-8").read().strip()
            if token:
                return token
        except Exception:
            pass
    token = secrets.token_urlsafe(16)
    try:
        os.makedirs(os.path.dirname(TOKEN_PATH), exist_ok=True)
        with open(TOKEN_PATH, "w", encoding="utf-8") as f:
            f.write(token)
    except Exception:
        pass
    return token


def _lan_ip() -> str | None:
    """Meilleure estimation de l'IP locale de la machine sur le réseau
    (pas d'appel réseau réel : ouvre juste un socket UDP pour laisser l'OS
    choisir l'interface, comme il le ferait pour une vraie connexion)."""
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return None

# Chaque entrée : (type Python, bornes optionnelles, libellé lisible). Ajouter
# un réglage ici est la SEULE façon de le rendre éditable -- tout ce qui n'y
# figure pas est refusé par le serveur, jamais un simple oubli silencieux.
WHITELIST: dict[str, dict] = {
    "live.dry_run": {
        "type": bool,
        "label": "Dry-run (aucun ordre réel envoyé)",
    },
    "live.max_account_drawdown_pct": {
        "type": float, "min": 0.0, "max": 1.0,
        "label": "Seuil du coupe-circuit de compte (fraction, ex: 0.15 = 15%)",
    },
    "live.max_risk_pct_per_trade": {
        "type": float, "min": 0.0, "max": 1.0,
        "label": "Risque max par position (fraction de l'équité, ex: 0.02 = 2%)",
    },
    "live.max_stop_pct_executed": {
        "type": float, "min": 0.0, "max": 1.0,
        "label": "Distance de stop maximale réellement envoyée au broker (fraction du prix)",
    },
    "live.daily_loss_max_pct": {
        "type": float, "min": 0.0, "max": 1.0,
        "label": "Seuil de perte quotidienne (fraction, ex: 0.05 = 5% -- voir profil de risque)",
    },
    "live.risk_guard_z_threshold": {
        "type": float, "min": 0.5, "max": 10.0,
        "label": "Sensibilité du filet de sécurité de marché (écarts-types)",
    },
    "live.poll_seconds": {
        "type": int, "min": 5, "max": 3600,
        "label": "Fréquence de décision en démo (secondes)",
    },
    "continuous.cycle_interval_seconds": {
        "type": int, "min": 0, "max": 3600,
        "label": "Délai entre deux cycles d'entraînement (secondes)",
    },
    "notifications.enabled": {
        "type": bool,
        "label": "Notifications externes activées",
    },
    "notifications.notify_cycle_every_n": {
        "type": int, "min": 1, "max": 500,
        "label": "Alerte de résumé tous les N cycles",
    },
}


def _get_path(cfg: dict, path: str):
    section, key = path.split(".", 1)
    return cfg.get(section, {}).get(key)


def _set_path(cfg: dict, path: str, value) -> None:
    section, key = path.split(".", 1)
    cfg.setdefault(section, {})[key] = value


def _read_overrides() -> dict:
    if not os.path.exists(OVERRIDES_PATH):
        return {}
    try:
        with open(OVERRIDES_PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _persist_overrides(overrides: dict) -> None:
    os.makedirs(os.path.dirname(OVERRIDES_PATH), exist_ok=True)
    with open(OVERRIDES_PATH, "w", encoding="utf-8") as f:
        json.dump(overrides, f, indent=2)


def load_overrides_into(cfg: dict) -> None:
    """Appelé au démarrage (voir autonomous_agent.py) : réapplique au
    dictionnaire de config partagé les changements faits lors d'un
    lancement précédent depuis le tableau de bord. Ignore silencieusement
    un chemin qui ne serait plus dans WHITELIST (ex: après une mise à
    jour du projet)."""
    overrides = _read_overrides()
    for path, value in overrides.items():
        if path in WHITELIST:
            _set_path(cfg, path, value)
            log.info(f"Réglage restauré depuis data/settings_overrides.json : {path} = {value}")


def _validate(path: str, raw_value) -> bool | int | float:
    spec = WHITELIST[path]
    t = spec["type"]
    if t is bool:
        if isinstance(raw_value, bool):
            return raw_value
        if isinstance(raw_value, str):
            return raw_value.strip().lower() in ("1", "true", "on", "yes")
        raise ValueError(f"valeur booléenne attendue pour {path}")
    try:
        value = int(raw_value) if t is int else float(raw_value)
    except (TypeError, ValueError):
        raise ValueError(f"nombre attendu pour {path}")
    if "min" in spec and value < spec["min"]:
        raise ValueError(f"{path} doit être >= {spec['min']}")
    if "max" in spec and value > spec["max"]:
        raise ValueError(f"{path} doit être <= {spec['max']}")
    return value


def _settings_panel_html(cfg: dict) -> str:
    rows = []
    for path, spec in WHITELIST.items():
        value = _get_path(cfg, path)
        label = spec.get("label", path)
        if spec["type"] is bool:
            checked = "checked" if value else ""
            field = f'<input type="checkbox" id="{path}" {checked}>'
        else:
            step = "any" if spec["type"] is float else "1"
            field = (f'<input type="number" id="{path}" value="{value}" step="{step}" '
                      f'min="{spec.get("min", "")}" max="{spec.get("max", "")}">')
        rows.append(f"<tr><td>{label}</td><td>{field}</td></tr>")

    type_map = json.dumps({p: s["type"].__name__ for p, s in WHITELIST.items()})
    return f"""
<div class="card" id="settings-panel">
  <h2>Réglages en direct (sans redémarrage)</h2>
  <table class="settings-table">
    {''.join(rows)}
  </table>
  <button id="settings-save" type="button"
          style="margin-top:14px;padding:8px 16px;border-radius:8px;border:1px solid var(--border);
                 background:var(--accent-soft);color:var(--accent);font-weight:600;cursor:pointer;">
    Enregistrer
  </button>
  <p id="settings-status" class="sub"></p>
</div>
<script>
(function() {{
  var TYPES = {type_map};
  document.getElementById("settings-save").addEventListener("click", function() {{
    var payload = {{}};
    for (var path in TYPES) {{
      var el = document.getElementById(path);
      if (!el) continue;
      payload[path] = TYPES[path] === "bool" ? el.checked : Number(el.value);
    }}
    fetch("/api/settings" + window.location.search, {{
      method: "POST",
      headers: {{"Content-Type": "application/json"}},
      body: JSON.stringify(payload)
    }}).then(function(r) {{ return r.json(); }}).then(function(data) {{
      var status = document.getElementById("settings-status");
      var errKeys = Object.keys(data.errors || {{}});
      if (errKeys.length) {{
        status.textContent = "Erreur : " + JSON.stringify(data.errors);
        status.style.color = "var(--critical)";
      }} else {{
        status.textContent = "Enregistré (" + Object.keys(data.applied).length + " réglage(s)) -- effectif immédiatement.";
        status.style.color = "var(--ok)";
      }}
    }}).catch(function() {{
      document.getElementById("settings-status").textContent = "Échec de connexion au serveur de réglages.";
    }});
  }});
}})();
</script>
"""


def _is_authorized(client_ip: str, path: str, token: str | None) -> bool:
    """Toujours autorisé depuis la machine elle-même (127.0.0.1) -- sinon
    (accès réseau local, voir `dashboard.lan_access`), exige le jeton en
    query string (?token=...), sans quoi n'importe quel appareil du Wi-Fi
    pourrait modifier les réglages. Fonction pure (pas de dépendance à
    BaseHTTPRequestHandler) pour rester facilement testable."""
    if client_ip in ("127.0.0.1", "::1"):
        return True
    if token is None:
        # lan_access désactivé (pas de jeton émis) -- toute requête qui
        # n'est pas depuis la machine elle-même est refusée, jamais
        # autorisée par défaut.
        return False
    from urllib.parse import urlparse, parse_qs
    qs = parse_qs(urlparse(path).query)
    return qs.get("token", [None])[0] == token


def make_handler(cfg: dict, token: str | None = None):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            pass  # pas de bruit sur la console pour chaque requête HTTP

        def _authorized(self) -> bool:
            return _is_authorized(self.client_address[0], self.path, token)

        def _send_json(self, obj, status=200):
            body = json.dumps(obj).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _send_html(self, body_str: str, status=200):
            body = body_str.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if not self._authorized():
                self._send_json({"error": "jeton invalide ou manquant"}, status=403)
                return
            from urllib.parse import urlparse
            path_only = urlparse(self.path).path  # sans la query string (?token=...)
            if path_only == "/api/settings":
                current = {path: _get_path(cfg, path) for path in WHITELIST}
                self._send_json({"settings": current})
                return
            if path_only in ("/", "/settings"):
                try:
                    with open(os.path.join("reports", "dashboard.html"), encoding="utf-8") as f:
                        dashboard_html = f.read()
                except Exception:
                    dashboard_html = "<p>Dashboard indisponible pour l'instant.</p></body></html>"
                panel = _settings_panel_html(cfg)
                if "</body>" in dashboard_html:
                    page = dashboard_html.replace("</body>", panel + "</body>")
                else:
                    page = dashboard_html + panel
                self._send_html(page)
                return
            self.send_response(404)
            self.end_headers()

        def do_POST(self):
            if not self._authorized():
                self._send_json({"error": "jeton invalide ou manquant"}, status=403)
                return
            from urllib.parse import urlparse
            if urlparse(self.path).path != "/api/settings":
                self.send_response(404)
                self.end_headers()
                return
            length = int(self.headers.get("Content-Length", 0) or 0)
            raw = self.rfile.read(length) if length else b"{}"
            try:
                payload = json.loads(raw or b"{}")
            except Exception:
                self._send_json({"applied": {}, "errors": {"_": "JSON invalide"}}, status=400)
                return

            overrides = _read_overrides()
            applied, errors = {}, {}
            for path, raw_value in payload.items():
                if path not in WHITELIST:
                    errors[path] = "réglage non autorisé"
                    continue
                try:
                    value = _validate(path, raw_value)
                except ValueError as e:
                    errors[path] = str(e)
                    continue
                _set_path(cfg, path, value)  # effet immédiat, en mémoire, visible partout où cfg est partagé
                overrides[path] = value
                applied[path] = value
                log.info(f"Réglage modifié depuis le tableau de bord : {path} = {value}")
            if applied:
                _persist_overrides(overrides)
            self._send_json({"applied": applied, "errors": errors}, status=200 if not errors else 400)

    return Handler


def start_server(cfg: dict, port: int = 8765) -> ThreadingHTTPServer | None:
    """Démarre le serveur en arrière-plan (thread démon) et retourne
    l'instance (pour un arrêt propre éventuel), ou None si le port est déjà
    utilisé -- ne doit jamais empêcher le reste du système de démarrer.

    `dashboard.lan_access: true` (config) : écoute sur toutes les
    interfaces (0.0.0.0) au lieu de 127.0.0.1 seul -- accessible depuis un
    téléphone/autre appareil sur le MÊME réseau Wi-Fi (ex: Safari iPhone).
    Un jeton persisté (data/dashboard_token.txt) devient alors obligatoire
    pour toute requête qui ne vient pas de la machine elle-même (voir
    Handler._authorized) -- l'URL complète avec jeton est journalisée
    ci-dessous, à copier sur l'appareil distant."""
    load_overrides_into(cfg)
    lan_access = bool(cfg.get("dashboard", {}).get("lan_access"))
    host = "0.0.0.0" if lan_access else "127.0.0.1"
    token = _get_or_create_token() if lan_access else None
    try:
        server = ThreadingHTTPServer((host, port), make_handler(cfg, token))
    except OSError as e:
        log.warning(f"Impossible de démarrer le serveur de réglages sur le port {port} "
                    f"({type(e).__name__}: {e}) -- réglages éditables en direct indisponibles "
                    f"pour cette session, le reste du système n'est pas affecté.")
        return None
    thread = threading.Thread(target=server.serve_forever, name="SETTINGS_SERVER", daemon=True)
    thread.start()
    log.info(f"Serveur de réglages démarré sur http://127.0.0.1:{port}/ "
             f"(réglages opérationnels éditables en direct, sans redémarrage).")
    if lan_access:
        lan_ip = _lan_ip() or "<IP-de-cette-machine-sur-votre-Wi-Fi>"
        log.info(f"ACCÈS RÉSEAU LOCAL ACTIVÉ -- depuis un appareil sur le MÊME Wi-Fi (ex: Safari "
                 f"iPhone), ouvrez : http://{lan_ip}:{port}/?token={token} -- ce lien n'est valide "
                 f"que sur votre réseau domestique, jamais depuis internet. Jeton persisté dans "
                 f"{TOKEN_PATH}.")
    return server
