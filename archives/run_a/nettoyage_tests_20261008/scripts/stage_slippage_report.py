"""
slippage_report.py
===================
Analyse agrégée du journal d'exécution (data/execution_log.jsonl, voir
MT5Connector._log_execution) -- audit institutionnel, section 6 ("Test du
Compte Cent" / "Analyse du Gap") : compare au tick près le prix DEMANDÉ par
l'IA et le prix RÉELLEMENT rempli par MT5, pour chaque ordre réel envoyé
(dry-run exclu -- rien n'est journalisé en dry-run, aucun ordre réel envoyé).

Objectif explicite du cahier des charges : si le slippage RÉEL mesuré ici
dépasse celui SIMULÉ dans l'environnement d'entraînement (voir
`environment.spread_volatility_multiplier`, `src/stress_test.py::
inject_macro_shocks` -- slippage_price_range), c'est le signal qu'il faut
resserrer les pénalités de friction côté entraînement. Ce script ne fait
QUE le diagnostic (ne recalibre rien automatiquement) -- ajuster les
pénalités reste une décision humaine.

100% best-effort, comme scripts/status_report.py : une erreur ici ne doit
jamais interrompre l'agent principal (processus séparé), et ce script est
conçu pour être lancé manuellement ou périodiquement, jamais dans le chemin
critique du trading.
"""
from __future__ import annotations
import json
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

ROOT = Path(__file__).resolve().parent.parent
EXECUTION_LOG_PATH = ROOT / "data" / "execution_log.jsonl"
# SORTIE STRUCTURÉE (LOT 2, phase 5, "frictions calibrables") : contrairement
# au reste de ce script (texte imprimé pour lecture humaine), ce fichier est
# la seule sortie MACHINE-LISABLE -- lue par src/stress_test.py::
# resolve_friction_params quand `frictions.profile: "calibrated"` (voir
# config/autonomous.yaml). Jamais écrite tant qu'il n'y a pas assez de
# mesures (voir MIN_SAMPLES_FOR_CALIBRATION) -- une calibration sur 2 ordres
# serait plus trompeuse qu'utile.
CALIBRATION_PATH = ROOT / "data" / "friction_calibration.json"
MIN_SAMPLES_FOR_CALIBRATION = 20


def _read_records(path: Path = EXECUTION_LOG_PATH) -> list[dict]:
    """Lit le journal d'exécution ligne par ligne (JSON Lines) -- une ligne
    corrompue/tronquée (ex: écriture interrompue par une coupure de courant)
    est ignorée plutôt que de faire échouer toute l'analyse."""
    if not path.exists():
        return []
    records = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return records


def _fmt_pct(x: float | None) -> str:
    return f"{x:.4%}" if x is not None else "N/A"


def build_report(records: list[dict]) -> str:
    """Construit le texte du rapport à partir des enregistrements déjà lus --
    séparée de `main()` pour être testable sans dépendre du système de
    fichiers réel (voir tests/test_slippage_report.py)."""
    if not records:
        return ("Aucun enregistrement dans le journal d'exécution "
                f"({EXECUTION_LOG_PATH}) -- soit aucun ordre réel n'a encore été "
                "envoyé, soit le système tourne encore en dry-run.")

    # Seuls les enregistrements avec un slippage_pct MESURABLE (prix demandé
    # ET rempli tous deux disponibles) entrent dans les statistiques
    # agrégées -- un ordre REJETÉ par MT5 (retcode != DONE) n'a souvent pas
    # de prix rempli valide, journalisé quand même (voir _log_execution)
    # pour la visibilité, mais exclu des moyennes de slippage.
    measurable = [r for r in records if r.get("slippage_pct") is not None]
    rejected = [r for r in records if r.get("retcode") not in (None, 10009)]  # 10009 = TRADE_RETCODE_DONE

    lines = [
        f"Journal d'exécution : {len(records)} ordre(s) réel(s) journalisé(s) "
        f"({len(measurable)} avec slippage mesurable, {len(rejected)} rejeté(s) par MT5).",
        "",
    ]

    if measurable:
        pct_values = [abs(r["slippage_pct"]) for r in measurable]
        pct_values_sorted = sorted(pct_values)
        n = len(pct_values_sorted)
        mean_abs = statistics.mean(pct_values)
        median_abs = statistics.median(pct_values)
        p90 = pct_values_sorted[min(n - 1, int(n * 0.90))]
        worst = pct_values_sorted[-1]
        lines += [
            f"Slippage ABSOLU (écart |rempli - demandé| / demandé) sur {n} ordre(s) :",
            f"  moyenne = {_fmt_pct(mean_abs)} | médiane = {_fmt_pct(median_abs)} | "
            f"P90 = {_fmt_pct(p90)} | pire cas = {_fmt_pct(worst)}",
            "",
        ]

        # DÉTAIL PAR STYLE (si journalisé) : un style peut trader à des
        # moments de la journée systématiquement plus/moins liquides que les
        # autres (ex: D1 qui décide souvent à heure fixe).
        by_style: dict[str, list[float]] = {}
        for r in measurable:
            by_style.setdefault(r.get("style") or "?", []).append(abs(r["slippage_pct"]))
        if len(by_style) > 1:
            lines.append("Détail par style :")
            for style, values in sorted(by_style.items()):
                lines.append(f"  {style} : moyenne={_fmt_pct(statistics.mean(values))} "
                              f"({len(values)} ordre(s))")
            lines.append("")

        lines += [
            "COMPARAISON AVEC LA SIMULATION (à faire manuellement, voir cahier des charges "
            "institutionnel section 6) : si la moyenne/P90 ci-dessus dépasse nettement le "
            "slippage simulé à l'entraînement (config `environment.spread_volatility_multiplier`, "
            "`src/stress_test.py::inject_macro_shocks` -- slippage_price_range), resserrez les "
            "pénalités de friction correspondantes plutôt que de laisser cet écart se creuser.",
            "",
        ]
    else:
        lines.append("Aucun ordre avec slippage mesurable (tous rejetés, ou prix manquants).")

    if rejected:
        lines.append(f"Ordre(s) rejeté(s) par MT5 (retcode != DONE) : {len(rejected)} -- "
                      f"retcodes observés : {sorted({r.get('retcode') for r in rejected})}")

    return "\n".join(lines)


def build_calibration(records: list[dict]) -> dict | None:
    """Calibration STRUCTURÉE dérivée des mesures RÉELLES (LOT 2, phase 5) --
    None si moins de MIN_SAMPLES_FOR_CALIBRATION ordres mesurables (pas assez
    de données pour une calibration significative, jamais une valeur
    fabriquée sur un échantillon minuscule).

    Calibre UNIQUEMENT `slippage_price_range` (voir
    src/stress_test.py::inject_macro_shocks) -- directement mesurable ici
    (`slippage` du journal d'exécution est déjà en UNITÉS DE PRIX, comme
    `slippage_price_range`). `spread_multiplier_range`, lui, N'EST PAS
    calibré : ce journal ne trace pas le spread "normal" au moment de
    chaque ordre, seulement le glissement d'exécution -- une calibration de
    ce paramètre nécessiterait une mesure supplémentaire non encore
    implémentée, jamais inventée ici à partir de données qui ne la
    contiennent pas."""
    measurable = [r for r in records if r.get("slippage") is not None]
    if len(measurable) < MIN_SAMPLES_FOR_CALIBRATION:
        return None
    abs_slippage = sorted(abs(r["slippage"]) for r in measurable)
    n = len(abs_slippage)
    p10 = abs_slippage[max(0, int(n * 0.10))]
    p90 = abs_slippage[min(n - 1, int(n * 0.90))]
    return {
        "computed_at": time.time(),
        "n_samples": n,
        "slippage_price_range": [round(p10, 6), round(max(p10, p90), 6)],
        "median_slippage_price": round(statistics.median(abs_slippage), 6),
        "note": ("spread_multiplier_range non calibré (non mesurable depuis ce journal) -- "
                 "reste à la valeur pessimiste par défaut, voir src/stress_test.py."),
    }


def main():
    records = _read_records()
    report = build_report(records)
    print(report)

    calibration = build_calibration(records)
    if calibration is not None:
        CALIBRATION_PATH.parent.mkdir(parents=True, exist_ok=True)
        with CALIBRATION_PATH.open("w", encoding="utf-8") as f:
            json.dump(calibration, f, indent=2)
        print(f"\nCalibration écrite dans {CALIBRATION_PATH} ({calibration['n_samples']} échantillons).")
    else:
        print(f"\nPas assez d'ordres mesurables (< {MIN_SAMPLES_FOR_CALIBRATION}) pour écrire une calibration.")

    # Envoi optionnel via le même canal que les autres alertes (best-effort,
    # comme status_report.py) -- seulement si le système est configuré et
    # qu'on trouve un minimum de données à rapporter, pour ne pas spammer un
    # rapport vide à chaque appel manuel de ce script en phase de test.
    if records:
        try:
            import yaml
            from src.notifier import send_alert
            cfg = yaml.safe_load((ROOT / "config" / "autonomous.yaml").read_text(encoding="utf-8"))
            send_alert(cfg, subject="Test_IA - rapport de slippage", message=report)
        except Exception:
            pass  # notification best-effort -- le rapport imprimé ci-dessus reste la sortie principale


if __name__ == "__main__":
    main()
