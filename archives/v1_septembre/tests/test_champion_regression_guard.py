"""Bug réel trouvé le 21/09 en observant H4 en démo réelle : un candidat
gen:204 au score walk-forward MEILLEUR que le champion gen:134 alors en
cours (validé, servant activement la démo) a quand même ÉCRASÉ ses poids --
alors que gen:204 lui-même ne passait PAS la validation (une seule fenêtre
sur quatre à 1 seul trade, sous le plancher anti-dégénérescence). Résultat :
la démo a perdu un style qui fonctionnait, remplacé par un qui ne satisfait
plus les seuils de qualité. Demande explicite de l'utilisateur : "l'évolution
doit être capable d'ALLER en démo, jamais en faire SORTIR un style déjà
validé." Corrigé dans src/continuous_trainer.py::run_one_cycle -- un
candidat qui ne passe pas la validation ne peut déployer ses poids QUE si
rien n'était encore validé pour ce style (bootstrap), jamais remplacer un
champion démo actuellement validé."""
from __future__ import annotations
import json
import os
from unittest.mock import patch

import src.continuous_trainer as ct
from tests.test_autonomous import BASE_CFG, _make_data_fn


def _cfg():
    cfg = dict(BASE_CFG)
    cfg["continuous"] = {**BASE_CFG["continuous"], "candidates_per_cycle": 1,
                          "min_trades_for_confident_score": 0}  # désactive le discount -- comparaison sur score brut
    cfg["memory"] = {"db_path": "mem_regression_guard.sqlite", "max_episodes": 500}
    cfg["validation"] = {"min_sharpe_to_go_live": -999, "max_drawdown_allowed": 1.0,
                          "min_generations_before_demo": 0, "min_trades_to_go_live": 30}
    return cfg


def _read_champion_meta():
    with open(os.path.join("models", "champion_H1", "meta.json"), encoding="utf-8") as f:
        return json.load(f)


def _metrics(sharpe, drawdown, n_trades):
    def _fn(agent, df, env_kwargs, n_windows=3, **kwargs):
        return {"total_return": 0.05, "sharpe": sharpe, "max_drawdown": drawdown,
                 "win_rate": 0.55, "profit_factor": 1.3, "n_trades": n_trades}
    return _fn


def test_better_but_invalid_candidate_never_overwrites_a_validated_champion(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    env_kwargs = dict(window_size=20, initial_balance=10000, transaction_cost=0.0002,
                       reward_type="risk_adjusted", drawdown_penalty=2.0, max_position=1)
    trainer = ct.ContinuousEvolutionTrainer(_cfg(), _make_data_fn(), ["H1"], env_kwargs)

    # Cycle 1 : premier candidat, VALIDE (50 trades >= min_trades_to_go_live=30) -> déployé et validé.
    with patch.object(ct, "evaluate_agent_walkforward", side_effect=_metrics(1.5, 0.05, 50)):
        trainer.run_one_cycle()
    meta_v1 = _read_champion_meta()
    assert meta_v1["passes_validation"] is True
    score_v1 = meta_v1["score"]

    # Cycle 2 : candidat bien MEILLEUR en score brut (sharpe 5.0) mais NE
    # PASSE PAS la validation (10 trades < 30) -- ne doit PAS remplacer le
    # champion validé du cycle 1.
    with patch.object(ct, "evaluate_agent_walkforward", side_effect=_metrics(5.0, 0.02, 10)):
        trainer.run_one_cycle()
    meta_after_cycle2 = _read_champion_meta()
    assert meta_after_cycle2["passes_validation"] is True, \
        "le champion déployé doit rester VALIDÉ -- jamais remplacé par un candidat qui ne l'est pas"
    assert meta_after_cycle2["score"] == score_v1, \
        "le fichier de champion déployé ne doit PAS avoir changé (toujours le candidat du cycle 1)"

    # Une promotion bloquée par ce garde-fou est traitée comme un NON-
    # ÉVÉNEMENT complet pour la recherche (même convention que le veto de
    # stabilité multi-actifs déjà existant, voir stability_veto ci-dessus
    # dans ce même fichier) : le score de référence NE progresse PAS tant
    # que rien n'est réellement déployé -- cohérent, pas une régression.
    assert trainer.champion_score["H1"] == score_v1, \
        "une promotion bloquée est un non-événement pour la recherche, comme le veto de stabilité existant"

    trainer.close()


def test_bootstrap_first_candidate_deploys_even_when_not_validated(tmp_path, monkeypatch):
    """Comportement D'ORIGINE préservé : le tout premier candidat pour un
    style qui n'a ENCORE AUCUN champion doit être déployé même s'il ne passe
    pas la validation -- rien à protéger (aucune régression possible), et le
    style doit pouvoir apparaître au tableau de bord / suivre sa progression
    dès le premier cycle, comme avant ce correctif."""
    monkeypatch.chdir(tmp_path)
    env_kwargs = dict(window_size=20, initial_balance=10000, transaction_cost=0.0002,
                       reward_type="risk_adjusted", drawdown_penalty=2.0, max_position=1)
    trainer = ct.ContinuousEvolutionTrainer(_cfg(), _make_data_fn(), ["H1"], env_kwargs)

    with patch.object(ct, "evaluate_agent_walkforward", side_effect=_metrics(5.0, 0.02, 10)):  # ne valide pas
        trainer.run_one_cycle()

    meta = _read_champion_meta()
    assert meta["passes_validation"] is False
    assert meta["score"] != 0, "doit quand même être déployé (bootstrap, rien à protéger)"
    trainer.close()


def test_validating_candidate_replaces_previous_even_if_previous_was_deployed_unvalidated(tmp_path, monkeypatch):
    """Un candidat qui PASSE la validation doit toujours pouvoir remplacer
    le champion actuel, que celui-ci soit validé ou non -- le garde-fou ne
    bloque QUE les remplacements par un candidat non-validant d'un champion
    DÉJÀ validé, jamais l'inverse (l'évolution doit pouvoir ALLER en démo)."""
    monkeypatch.chdir(tmp_path)
    env_kwargs = dict(window_size=20, initial_balance=10000, transaction_cost=0.0002,
                       reward_type="risk_adjusted", drawdown_penalty=2.0, max_position=1)
    trainer = ct.ContinuousEvolutionTrainer(_cfg(), _make_data_fn(), ["H1"], env_kwargs)

    with patch.object(ct, "evaluate_agent_walkforward", side_effect=_metrics(1.0, 0.05, 10)):  # bootstrap, non validé
        trainer.run_one_cycle()
    assert _read_champion_meta()["passes_validation"] is False

    with patch.object(ct, "evaluate_agent_walkforward", side_effect=_metrics(3.0, 0.02, 50)):  # meilleur ET validant
        trainer.run_one_cycle()
    meta = _read_champion_meta()
    assert meta["passes_validation"] is True
    assert meta["metrics"]["sharpe"] == 3.0, "doit bien être le candidat du cycle 2, déployé normalement"
    trainer.close()
