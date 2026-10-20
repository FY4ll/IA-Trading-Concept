"""Envoi d'un message et d'une image sur le téléphone du chef de projet (même canal que Run A, lu dans sa config,
jamais affiché). Au mieux : un envoi raté est journalisé et n'arrête jamais l'arbre."""
from __future__ import annotations

import base64
from pathlib import Path

import requests
import yaml

from collapsar.donnees.marches import RACINE

CONFIG_RUN_A = RACINE / "runs" / "20260919_envv2" / "run_config_A.yaml"


def _canal() -> tuple[str, str] | None:
    try:
        cfg = yaml.safe_load(CONFIG_RUN_A.read_text(encoding="utf-8")).get("notifications") or {}
    except Exception:
        return None
    if not cfg.get("enabled") or cfg.get("channel") != "ntfy" or not cfg.get("ntfy_topic"):
        return None
    return (cfg.get("ntfy_server") or "https://ntfy.sh").rstrip("/"), cfg["ntfy_topic"]


def _entete(texte: str) -> str:
    """Les en-têtes n'acceptent pas les accents : encodage standard des en-têtes de courrier."""
    return "=?UTF-8?B?" + base64.b64encode(texte.encode("utf-8")).decode("ascii") + "?="


def envoyer_texte(titre: str, message: str) -> bool:
    canal = _canal()
    if canal is None:
        return False
    serveur, sujet = canal
    try:
        r = requests.post(f"{serveur}/{sujet}", data=message.encode("utf-8"), timeout=15,
                          headers={"Title": _entete(titre)})
        r.raise_for_status()
        return True
    except Exception as e:
        print(f"[téléphone] envoi raté ({type(e).__name__})", flush=True)
        return False


def envoyer_image(fichier: Path, titre: str, message: str) -> bool:
    canal = _canal()
    if canal is None:
        return False
    serveur, sujet = canal
    try:
        r = requests.put(f"{serveur}/{sujet}", data=Path(fichier).read_bytes(), timeout=30,
                         headers={"Filename": Path(fichier).name, "Title": _entete(titre),
                                  "Message": _entete(message.replace("\n", "\\n"))})
        r.raise_for_status()
        return True
    except Exception as e:
        print(f"[téléphone] envoi raté ({type(e).__name__})", flush=True)
        return False


if __name__ == "__main__":                      # utilisé par le gardien : python -m ... "titre" "message"
    import sys
    envoyer_texte(sys.argv[1], sys.argv[2])
