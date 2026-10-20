"""Règle de passage automatique d'AUREXIS en démo (09/10/2026) : jamais sans les trois critères, retour à blanc si ça
tourne mal."""
from __future__ import annotations
import importlib.util
import os

_s = importlib.util.spec_from_file_location("regle", os.path.join(os.path.dirname(__file__), "..", "scripts",
                                                                   "regle_demo_aurexis.py"))
R = importlib.util.module_from_spec(_s)
_s.loader.exec_module(R)


def _log(tmp_path, evals):
    lines = []
    for i, notes in enumerate(evals):
        lines.append(f"2026-10-10 0{i % 10}:00:00,000 [EVOLUTION] [continuous_trainer]   [AUREXIS] champion réévalué sur "
                     f"les données de ce cycle : score=1.0 (mémorisé 1.0)\n")
        for k, n in enumerate(notes, start=1):
            lines.append(f"x [AUREXIS] période {k} : compte tous marchés +1.00%/mois, challenge réussi 50% / raté 0% "
                         f"-> note {n:+.2f}\n")
        lines.append("x       [AUREXIS] compte tous marchés : +1.00%/mois, challenge FTMO réussi 50% -> note +1 [moins bonne des périodes]\n")
        lines.append("x   [AUREXIS] score=-9.0 sharpe=0.1\n")
        for k in (1, 2):                                       # un candidat juste après : ne doit pas être compté
            lines.append(f"x [AUREXIS] période {k} : compte tous marchés -9%/mois -> note -9.00\n")
    d = tmp_path / "logs"
    d.mkdir()
    (d / "stderr_test.txt").write_text("".join(lines), encoding="utf-8")
    return str(d)


def test_streak_counts_only_the_champion_and_needs_both_periods(tmp_path):
    d = _log(tmp_path, [[-1.0, 2.0]] + [[1.5, 0.3]] * 4)
    assert R.champion_streak(d) == (4, 5)


def test_streak_breaks_on_one_bad_period(tmp_path):
    d = _log(tmp_path, [[1.0, 1.0]] * 6 + [[2.0, -0.1]])
    assert R.champion_streak(d)[0] == 0


def _c(a, b, c, perf=0.01):
    return {"examen_tournant": {"ok": a, "detail": ""}, "douze_mois": {"ok": b, "detail": ""},
            "semaine_reelle": {"ok": c, "detail": ""}, "_perf_blanc": perf, "_generation": 1}


def test_demo_only_with_all_three_criteria():
    assert R.decide(_c(True, True, True), "blanc")[0] == "demo"
    for combo in [(False, True, True), (True, False, True), (True, True, False)]:
        assert R.decide(_c(*combo), "blanc")[0] == "blanc"


def test_back_to_paper_when_demo_goes_wrong():
    assert R.decide(_c(True, True, True, perf=-0.06), "demo")[0] == "blanc"
    assert R.decide(_c(False, False, False, perf=0.02), "demo")[0] == "demo", "un critère qui fléchit ne coupe pas tout seul"