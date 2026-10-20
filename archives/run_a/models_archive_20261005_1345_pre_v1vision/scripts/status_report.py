"""
status_report.py
=================
Rapport de statut périodique (3x/jour, toutes les 8h, voir la tâche planifiée
Windows "TestIA_StatusReport") -- maintenant que le système tourne en
production 24/7 sans écran, l'utilisateur a demandé un point régulier plutôt
que de devoir se connecter en AnyDesk pour vérifier que tout va bien.

Réutilise le même canal que les alertes critiques (src/notifier.py, ntfy) --
un seul endroit à surveiller sur le téléphone. 100% best-effort : une erreur
ici ne doit jamais interrompre l'agent principal (processus séparé).
"""
from __future__ import annotations
import json
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.notifier import send_alert

ROOT = Path(__file__).resolve().parent.parent
ANOMALY_PATTERNS = re.compile(
    r"Traceback|OSError|Exception|ERREUR|Erreur|├ëCHEC|Échec|CRITICAL|refus", re.IGNORECASE
)


def _read_progress() -> str:
    path = ROOT / "models" / "_progress.json"
    if not path.exists():
        return "models/_progress.json introuvable."
    data = json.loads(path.read_text(encoding="utf-8"))
    return (
        f"Génération {data.get('generation')} | "
        f"Meilleur score jamais atteint : {data.get('best_ever_score'):.3f} | "
        f"Cycles sans amélioration : {data.get('cycles_since_improvement')}"
    )


def _read_mt5_status(cfg: dict) -> str:
    try:
        import MetaTrader5 as mt5
    except ImportError:
        return "Package MetaTrader5 non disponible."
    if not mt5.initialize():
        return f"Connexion MT5 impossible : {mt5.last_error()}"
    try:
        account = mt5.account_info()
        if account is None:
            return "Aucun compte MT5 connecté."
        symbol = (cfg.get("live") or {}).get("symbol", "XAUUSD")
        positions = mt5.positions_get(symbol=symbol) or ()
        pos_str = "aucune" if not positions else ", ".join(
            f"{p.type_str if hasattr(p, 'type_str') else p.type} {p.volume} lots @ {p.price_open} "
            f"(PnL flottant {p.profit:.2f})" for p in positions
        )
        demo = account.trade_mode == mt5.ACCOUNT_TRADE_MODE_DEMO
        return (
            f"Compte {account.login} ({account.server}), {'DÉMO' if demo else 'RÉEL !!'} | "
            f"Equity={account.equity:.2f} {account.currency} | Balance={account.balance:.2f} | "
            f"Position(s) ouverte(s) : {pos_str}"
        )
    finally:
        mt5.shutdown()


def _process_health() -> str:
    import subprocess
    out = subprocess.run(
        ["powershell", "-NoProfile", "-Command",
         "(Get-Process -Name python -ErrorAction SilentlyContinue | Measure-Object).Count;"
         "(Get-Process -Name terminal64 -ErrorAction SilentlyContinue | Measure-Object).Count"],
        capture_output=True, text=True, timeout=20,
    )
    lines = [l.strip() for l in out.stdout.strip().splitlines() if l.strip()]
    python_running = lines[0] != "0" if len(lines) > 0 else False
    mt5_running = lines[1] != "0" if len(lines) > 1 else False
    return (
        f"Agent Python : {'EN COURS' if python_running else 'ARRÊTÉ !!'} | "
        f"Terminal MT5 : {'EN COURS' if mt5_running else 'ARRÊTÉ !!'}"
    )


def _recent_anomalies(hours: int = 8) -> str:
    log_path = ROOT / "logs" / "autonomous_agent.log"
    if not log_path.exists():
        return "Aucun fichier de log trouvé."
    cutoff = datetime.now() - timedelta(hours=hours)
    hits = []
    with log_path.open(encoding="utf-8", errors="replace") as f:
        for line in f:
            if not ANOMALY_PATTERNS.search(line):
                continue
            m = re.match(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})", line)
            if m:
                try:
                    ts = datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S")
                    if ts < cutoff:
                        continue
                except ValueError:
                    pass
            hits.append(line.strip())
    if not hits:
        return f"Aucune anomalie détectée sur les {hours} dernières heures."
    tail = hits[-10:]
    prefix = f"({len(hits)} ligne(s) suspecte(s), les {len(tail)} dernières)\n" if len(hits) > len(tail) else ""
    return prefix + "\n".join(tail)


def main():
    cfg = yaml.safe_load((ROOT / "config" / "autonomous.yaml").read_text(encoding="utf-8"))

    report = (
        f"[ÉVOLUTION] {_read_progress()}\n\n"
        f"[MT5] {_read_mt5_status(cfg)}\n\n"
        f"[PROCESSUS] {_process_health()}\n\n"
        f"[ANOMALIES] {_recent_anomalies()}"
    )
    subject = f"Rapport Test_IA -- {datetime.now().strftime('%d/%m %H:%M')}"
    send_alert(cfg, subject, report)
    print(report)


if __name__ == "__main__":
    main()
