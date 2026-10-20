"""PÉRIODE D'ESSAI AVANT PROMOTION (10/10/2026) : le gagnant d'un cycle devient prétendant, repasse l'examen des cycles
suivants à côté du champion, et n'est promu que s'il fait mieux en cumulé (incident : génération 424 promue sur un seul
bon tirage, puis négative sur les suivants)."""
import json
import os
import shutil

import pytest

import src.continuous_trainer as ct


def _exam(p, c):
    return {"cycle": 0, "pretendant": p, "champion": c}


def test_verdict_waits_then_judges_the_cumulative():
    assert ct._trial_verdict([_exam([5.0, 6.0], [3.0, 6.0])], 4) is None, "essai en cours"
    lucky = [_exam([4.5, 6.5], [3.0, 6.5])] + [_exam([-9.0, -4.0], [-3.0, -2.0])] * 3
    assert ct._trial_verdict(lucky, 4) is False, "un seul bon tirage ne suffit plus (cas de la génération 424)"
    solid = [_exam([1.0, 2.0], [0.5, 2.0]), _exam([0.0, 1.0], [-1.0, 1.0]), _exam([2.0, 2.0], [2.0, 2.5]),
             _exam([-1.0, 3.0], [-1.5, 3.0])]
    assert ct._trial_verdict(solid, 4) is True
    worse_mean = [_exam([1.0, 1.0], [0.0, 9.0])] * 4
    assert ct._trial_verdict(worse_mean, 4) is False, "meilleur sur la moins bonne période mais moins bon en moyenne"


def test_period_notes_and_need():
    m = {"portefeuille": {"periodes": [{"note": -1.0}, {"note": 2.0}]}}
    assert ct._period_notes(m, -1.0) == [-1.0, 2.0] and ct._period_notes({}, 0.7) == [0.7]
    cfg = {"continuous": {"promotion_trial_by_style": {"AUREXIS": 4}}}
    assert ct._trial_need(cfg, "AUREXIS") == 4 and ct._trial_need(cfg, "H1") == 0 and ct._trial_need({}, "X") == 0


def test_trial_files_survive_and_are_dropped(tmp_path, monkeypatch):
    monkeypatch.setattr(ct, "MODELS_ROOT", str(tmp_path))
    src = os.path.join(str(tmp_path), "cand")
    open(src + ".zip", "w").write("cerveau")
    assert ct._trial_load("AUREXIS") is None
    ct._trial_save("AUREXIS", {"generation": 7, "exams": [_exam([1.0], [0.0])]}, model_path=src)
    t = ct._trial_load("AUREXIS")
    assert t["generation"] == 7 and open(os.path.join(ct._trial_dir("AUREXIS"), "agent.zip")).read() == "cerveau"
    ct._trial_drop("AUREXIS")
    assert ct._trial_load("AUREXIS") is None


def test_quick_exam_skipped_for_the_pretender(monkeypatch):
    """Le prétendant passe directement l'examen complet ; il ne fausse pas la barre du petit examen du champion."""
    seen = []

    def run_pool(specs, workers):
        seen.append([(s["out_path"], s.get("phase")) for s in specs])
        out = []
        for s in specs:
            q = {"champ": 0.0, "pret": 99.0, "c0": 0.1}[s["out_path"]]
            out.append({"style": "AUREXIS", "slot": 0, "quick_score": q, "score": q, "model_path": s["out_path"],
                        "eval_only": bool(s.get("eval_only")), "trial": bool(s.get("trial")), "quick": []})
        return out
    tr = ct.ContinuousEvolutionTrainer.__new__(ct.ContinuousEvolutionTrainer)
    tr.cfg = {}
    monkeypatch.setattr(tr, "_run_pool", run_pool)
    specs = [{"out_path": "champ", "eval_only": True, "phase": 1},
             {"out_path": "pret", "eval_only": True, "trial": True, "phase": 1},
             {"out_path": "c0", "phase": 1}]
    res = tr._two_stage_exam(specs, 4, 12)
    assert [p for p, _ in seen[0]] == ["champ", "c0"], "temps 1 sans le prétendant"
    assert "pret" in [p for p, _ in seen[1]] and all(ph is None for _, ph in seen[1])
    assert any(r["trial"] for r in res)


@pytest.fixture
def mini(tmp_path, monkeypatch):
    from src.data_loader import generate_synthetic_ohlcv, chronological_split
    from src.features import FEATURE_COLUMNS, add_technical_features, normalize_features
    monkeypatch.chdir(tmp_path)

    def get_data(primary_tf=None):
        df = add_technical_features(generate_synthetic_ohlcv(n_bars=1500, seed=3))
        tr, va, _ = chronological_split(df, 0.7, 0.3)
        tr, st = normalize_features(tr, columns=FEATURE_COLUMNS)
        va, _ = normalize_features(va, st, columns=FEATURE_COLUMNS)
        return tr, va, st, FEATURE_COLUMNS, []
    cfg = {"agent": {"policy": "MlpPolicy", "learning_rate": 3e-4, "n_steps": 64, "batch_size": 32,
                     "gamma": 0.99, "gae_lambda": 0.95, "ent_coef": 0.01},
           "continuous": {"candidates_per_cycle": 1, "timesteps_per_cycle": 64, "parallel_workers": 1,
                          "reevaluate_incumbent": True, "promotion_trial_by_style": {"H1": 2}},
           "memory": {"db_path": "mem.sqlite", "max_episodes": 500}}
    env_kwargs = dict(window_size=20, initial_balance=10000, transaction_cost=0.0002,
                      reward_type="risk_adjusted", drawdown_penalty=2.0, max_position=1)
    trainer = ct.ContinuousEvolutionTrainer(cfg, get_data, ["H1"], env_kwargs)
    trainer.run_one_cycle()                                   # crée le champion (aucun champion : immédiat)
    yield trainer
    trainer.close()


def _gen():
    return json.load(open(ct._champion_meta("H1"), encoding="utf-8"))["generation"]


def test_winner_becomes_pretender_not_champion(mini, monkeypatch):
    real = ct._train_candidate_worker

    def boosted(spec):                                         # le candidat bat nettement le champion
        r = real(spec)
        if not r.get("eval_only"):
            r["score"] = float(r["score"]) + 1000.0
        return r
    monkeypatch.setattr(ct, "_train_candidate_worker", boosted)
    g0 = _gen()
    assert ct._trial_load("H1") is None
    mini.run_one_cycle()
    t = ct._trial_load("H1")
    assert t is not None and len(t["exams"]) == 1, "le gagnant est mis à l'essai"
    assert _gen() == g0, "le champion n'est PAS remplacé tout de suite"
    monkeypatch.setattr(ct, "_train_candidate_worker", real)
    mini.run_one_cycle()                                       # 2e examen : le cerveau du prétendant DOIT se recharger
    t2 = ct._trial_load("H1")
    assert t2 is None or t2["generation"] != t["generation"], "examen compté (incident du cycle 435 : cerveau refusé)"


def test_unloadable_pretender_exam_is_not_counted(mini):
    _seed_trial(_exam([1000.0], [-1000.0]))
    p = os.path.join(ct._trial_dir("H1"), "meta.json")
    t = json.load(open(p, encoding="utf-8"))
    t["env_version"] = 1                                       # ancienne version : cerveau refusé au rechargement
    json.dump(t, open(p, "w", encoding="utf-8"))
    g0 = _gen()
    mini.run_one_cycle()
    t = ct._trial_load("H1")                                   # (un candidat du cycle peut le remplacer comme prétendant)
    assert _gen() == g0, "compté, son premier examen (+1000) l'aurait fait promouvoir"
    assert t is None or t["generation"] != 99 or len(t["exams"]) == 1, "examen non compté"


def test_old_gold_validation_no_longer_blocks_aurexis_style(mini, monkeypatch):
    """Incident du 12/10 : champion « validé » (anciens seuils sur l'or) -> 12 candidats bloqués, aucun prétendant
    possible. Avec validation_veto_by_style: false, le meilleur candidat devient prétendant malgré les seuils."""
    real = ct._train_candidate_worker

    def boosted(spec):
        r = real(spec)
        if not r.get("eval_only"):
            r["score"] = float(r["score"]) + 1000.0
        return r
    monkeypatch.setattr(ct, "_train_candidate_worker", boosted)
    monkeypatch.setattr(ct, "passes_validation", lambda *a, **k: False)
    meta = json.load(open(ct._champion_meta("H1"), encoding="utf-8"))
    meta["passes_validation"] = True
    json.dump(meta, open(ct._champion_meta("H1"), "w", encoding="utf-8"))
    mini.run_one_cycle()
    assert ct._trial_load("H1") is None, "ancien comportement : candidat bloqué par le veto"
    mini.cfg["continuous"]["validation_veto_by_style"] = {"H1": False}
    mini.run_one_cycle()
    assert ct._trial_load("H1") is not None, "sans le veto : il devient prétendant"


def _seed_trial(first_exam):
    shutil.copy(ct._champion_model("H1") + ".zip", "seed.zip")
    ct._trial_save("H1", {"generation": 99, "hyperparams": None, "exams": [first_exam]}, model_path="seed")


def test_leading_pretender_finishes_its_trial(mini, monkeypatch):
    """Incident du cycle 447 : le prétendant 446, en tête en cumulé, remplacé par un seul bon tirage d'un candidat."""
    assert ct._trial_leading([_exam([1.0, 2.0], [0.0, 2.0])]) and not ct._trial_leading([_exam([0.0], [1.0])])
    assert not ct._trial_leading([])
    mini.cfg["continuous"]["promotion_trial_by_style"]["H1"] = 4
    real = ct._train_candidate_worker

    def boosted(spec):
        r = real(spec)
        if not r.get("eval_only"):
            r["score"] = float(r["score"]) + 1000.0             # bat le champion ET le prétendant sur cet examen
        return r
    monkeypatch.setattr(ct, "_train_candidate_worker", boosted)
    _seed_trial(_exam([1000.0], [-1000.0]))                    # en tête
    mini.run_one_cycle()
    t = ct._trial_load("H1")
    assert t is not None and t["generation"] == 99 and len(t["exams"]) == 2, "il termine son essai"
    ct._trial_drop("H1")
    _seed_trial(_exam([-1000.0], [1000.0]))                    # derrière : remplaçable
    mini.run_one_cycle()
    t = ct._trial_load("H1")
    assert t is not None and t["generation"] != 99, "un prétendant qui perd son essai peut être remplacé"


def test_trial_passed_promotes_the_pretender(mini):
    _seed_trial(_exam([1000.0], [-1000.0]))
    g0 = _gen()
    mini.run_one_cycle()                                       # 2e examen -> le cumul tranche
    assert ct._trial_load("H1") is None and _gen() != g0, "essai réussi : nouveau champion"


def test_trial_failed_keeps_the_champion(mini):
    _seed_trial(_exam([-1000.0], [1000.0]))
    g0 = _gen()
    mini.run_one_cycle()
    t = ct._trial_load("H1")                                   # un candidat de CE cycle peut devenir le nouveau prétendant
    assert (t is None or t["generation"] != 99) and _gen() == g0, "essai raté : prétendant écarté, champion gardé"
