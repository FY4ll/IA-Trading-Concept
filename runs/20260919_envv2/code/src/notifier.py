"""
notifier.py
============
Envoi d'une alerte externe (email, Discord ou ntfy.sh) quand un événement
CRITIQUE survient (voir src/account_guard.py) -- pour être informé même
loin de l'écran. 100% BEST-EFFORT : une erreur d'envoi est journalisée mais
ne doit JAMAIS interrompre la boucle de trading -- une alerte qui échoue ne
doit jamais devenir un second problème.

Trois canaux au choix (voir config/autonomous.yaml, section `notifications`) :
  - "email"   : SMTP standard (ex: Gmail avec un mot de passe d'application),
                aucune dépendance en plus de la bibliothèque standard.
  - "discord" : un webhook créé dans les paramètres d'un salon Discord --
                pas de compte de bot, pas de clé API, juste une URL.
  - "ntfy"    : https://ntfy.sh (ou un serveur ntfy auto-hébergé) -- aucune
                inscription, juste un nom de "topic" à choisir soi-même,
                reçu comme notification push sur téléphone/bureau.
Aucun des trois n'est un service PAYANT.
"""
from __future__ import annotations
import logging
import os

log = logging.getLogger("notifier")


def _cfg_or_env(notif_cfg: dict, key: str, env_var: str):
    """Valeur de config : variable d'environnement `env_var` PRIORITAIRE si
    définie (et non vide), sinon repli sur `notif_cfg[key]` (YAML) -- permet
    de garder les secrets (mot de passe SMTP, URL de webhook) hors du
    fichier de config versionné, voir README pour la liste des variables."""
    return os.environ.get(env_var) or notif_cfg.get(key)


def send_alert(cfg: dict, subject: str, message: str):
    notif_cfg = cfg.get("notifications") or {}
    if not notif_cfg.get("enabled"):
        log.warning(f"[notifications désactivées, voir config/autonomous.yaml] {subject}: {message}")
        return
    channel = notif_cfg.get("channel")
    try:
        if channel == "email":
            _send_email(notif_cfg, subject, message)
        elif channel == "discord":
            _send_discord(notif_cfg, subject, message)
        elif channel == "ntfy":
            _send_ntfy(notif_cfg, subject, message)
        else:
            log.warning(f"Canal de notification inconnu ou non configuré ({channel!r}) -- "
                        f"alerte journalisée seulement, voir ci-dessus.")
            return
        log.info(f"Alerte envoyée via {channel}.")
    except Exception as e:
        log.error(f"Échec d'envoi de la notification ({channel}) : {type(e).__name__}: {e} -- "
                  f"alerte journalisée seulement (voir ci-dessus), la boucle continue normalement.")


def _send_email(notif_cfg: dict, subject: str, message: str):
    import smtplib
    from email.mime.text import MIMEText

    host = _cfg_or_env(notif_cfg, "smtp_host", "NOTIFIER_SMTP_HOST")
    port = notif_cfg.get("smtp_port", 587)
    user = _cfg_or_env(notif_cfg, "smtp_user", "NOTIFIER_SMTP_USER")
    password = _cfg_or_env(notif_cfg, "smtp_password", "NOTIFIER_SMTP_PASSWORD")
    to_addr = _cfg_or_env(notif_cfg, "to_email", "NOTIFIER_TO_EMAIL") or user

    msg = MIMEText(message, _charset="utf-8")
    msg["Subject"] = subject
    msg["From"] = user
    msg["To"] = to_addr

    with smtplib.SMTP(host, port, timeout=15) as server:
        server.starttls()
        server.login(user, password)
        server.sendmail(user, [to_addr], msg.as_string())


def _send_discord(notif_cfg: dict, subject: str, message: str):
    import requests
    webhook_url = _cfg_or_env(notif_cfg, "webhook_url", "NOTIFIER_WEBHOOK_URL")
    resp = requests.post(webhook_url, json={"content": f"**{subject}**\n{message}"}, timeout=15)
    # Voir _send_ntfy ci-dessous pour le raisonnement complet (bug réel
    # trouvé le 22/09) -- requests ne lève PAS d'exception sur un code HTTP
    # d'erreur (4xx/5xx), seulement sur un échec de connexion -- sans ce
    # contrôle explicite, un webhook invalide/révoqué serait silencieusement
    # traité comme un succès par l'appelant (send_alert).
    resp.raise_for_status()


def _send_ntfy(notif_cfg: dict, subject: str, message: str):
    import requests
    topic = _cfg_or_env(notif_cfg, "ntfy_topic", "NOTIFIER_NTFY_TOPIC")
    server = (_cfg_or_env(notif_cfg, "ntfy_server", "NOTIFIER_NTFY_SERVER") or "https://ntfy.sh").rstrip("/")
    resp = requests.post(f"{server}/{topic}", data=message.encode("utf-8"),
                          headers={"Title": subject}, timeout=15)
    # BUG RÉEL trouvé le 22/09 : `requests.post` ne lève une exception QUE
    # pour un échec de connexion (DNS, timeout...), JAMAIS pour un code HTTP
    # d'erreur (ex: 429 "quota quotidien dépassé", observé en conditions
    # réelles sur ntfy.sh gratuit ce soir) -- sans `raise_for_status()`
    # explicite, `send_alert` journalisait "Alerte envoyée via ntfy" même
    # quand le serveur avait RÉELLEMENT refusé le message, rendant l'échec
    # invisible (l'utilisateur ne recevait plus rien depuis des heures sans
    # aucune trace dans les logs).
    resp.raise_for_status()
