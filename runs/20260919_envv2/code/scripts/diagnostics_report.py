"""
Diagnostic à la demande (même calcul que le diagnostic quotidien de la boucle live) :

    python scripts/diagnostics_report.py [H1 H1T H1X] [--hypotheses]       (cwd = code/)

Écrit reports/diagnostics.json et reports/diagnostics.md ; avec --hypotheses, enregistre aussi les
nouvelles hypothèses de recherche (reports/research_journal.jsonl).
"""
import argparse, os, sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
os.chdir(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import yaml

from src.decision_journal import DecisionJournal
from src.diagnostics import run_diagnostics, write_reports, to_markdown


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("styles", nargs="*")
    ap.add_argument("--config", default="../run_config_A.yaml")
    ap.add_argument("--hypotheses", action="store_true")
    args = ap.parse_args()
    cfg = yaml.safe_load(open(args.config, encoding="utf-8"))
    styles = args.styles or cfg["data"]["timeframe_pool"]
    journal = DecisionJournal((cfg.get("journal") or {}).get("db_path", "data/decision_journal.sqlite"))
    diag = run_diagnostics(cfg, journal, styles)
    write_reports(diag)
    print(to_markdown(diag))
    if args.hypotheses:
        from src.research_engine import generate_hypotheses
        for h in generate_hypotheses(diag):
            print(f"nouvelle hypothèse : {h['key']} -- {h['hypothesis']}")


if __name__ == "__main__":
    main()
