"""
status_files.py
================
Fichiers d'état JSON lus par l'opérateur (Claude) pour les rapports -- remplace
l'ancien tableau de bord HTML et son serveur de réglages (supprimés le 05/10/2026
à la demande de l'utilisateur : il ne les regardait jamais). Aucun HTML, aucun
serveur, aucun navigateur : seulement reports/training_status.json,
reports/live_status.json et l'historique reports/score_history.jsonl.
"""
from __future__ import annotations
import json
import os
import threading

_file_lock = threading.Lock()

REPORTS_DIR = "reports"
HISTORY_PATH = os.path.join(REPORTS_DIR, "score_history.jsonl")
HISTORY_MAX_ENTRIES = 2000
TRAINING_STATUS_PATH = os.path.join(REPORTS_DIR, "training_status.json")
LIVE_STATUS_PATH = os.path.join(REPORTS_DIR, "live_status.json")


def _write_json_atomic(path: str, data: dict) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str)
    os.replace(tmp, path)


def write_training_status(status: dict, cfg: dict | None = None):
    with _file_lock:
        _write_json_atomic(TRAINING_STATUS_PATH, status)
        try:
            entry = {"generation": status.get("generation"),
                     "styles": {tf: s.get("score") for tf, s in status.get("styles", {}).items()}}
            with open(HISTORY_PATH, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")
            _prune_history()
        except Exception:
            pass


def _prune_history():
    if os.path.getsize(HISTORY_PATH) < 2_000_000:
        return
    with open(HISTORY_PATH, encoding="utf-8") as f:
        lines = f.readlines()
    if len(lines) > HISTORY_MAX_ENTRIES:
        with open(HISTORY_PATH, "w", encoding="utf-8") as f:
            f.writelines(lines[-HISTORY_MAX_ENTRIES:])


def read_history() -> list[dict]:
    if not os.path.exists(HISTORY_PATH):
        return []
    out = []
    with open(HISTORY_PATH, encoding="utf-8") as f:
        for line in f:
            try:
                out.append(json.loads(line))
            except Exception:
                continue
    return out


def write_live_status(status: dict, cfg: dict | None = None):
    with _file_lock:
        _write_json_atomic(LIVE_STATUS_PATH, status)
