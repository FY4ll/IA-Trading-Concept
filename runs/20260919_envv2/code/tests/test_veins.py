"""VEINES (08/10/2026) : plusieurs chemins d'apprentissage pour AUREXIS, nourris selon leurs progrès (principe du
blob proposé par l'utilisateur)."""
import os

import numpy as np
import pytest

import src.continuous_trainer as ct

MARKETS = ["EURUSD", "USDJPY", "XAUUSD miroir", "EURUSD miroir"]
CFG = {"max_veins": 2, "max_stall": 3, "min_trades": 100, "max_drawdown": 0.3, "min_mirror_gain": 0.25}


def _m(notes, dd=0.1, trades=300):
    return {"max_drawdown": dd, "n_trades": trades,
            "markets": [{"market": k, "score": v} for k, v in zip(MARKETS, notes)]}


CHAMP = _m([0.0, 0.0, -1.0, -1.0])


@pytest.fixture
def root(tmp_path, monkeypatch):
    monkeypatch.setattr(ct, "MODELS_ROOT", str(tmp_path))
    return tmp_path


def _cand(tmp_path, name, score, notes, vein_id=None, promoted=False):
    p = os.path.join(str(tmp_path), name)
    with open(p + ".zip", "w") as f:
        f.write(name)
    return {"style": "AUREXIS", "score": score, "metrics": _m(notes), "model_path": p, "vein_id": vein_id,
            "hyperparams": {"learning_rate": 1e-4}, "promoted": promoted}


def test_new_talent_selling_or_majority_but_never_reckless():
    assert ct._new_talent(_m([0.0, 0.0, -0.2, -0.3]), CHAMP, CFG)[0], "vend mieux sur les marchés inversés"
    assert ct._new_talent(_m([0.5, 0.0, -1.0, -1.0]), CHAMP, CFG)[0] is False, "1 seul marché meilleur"
    assert ct._new_talent(_m([0.5, 0.5, -1.0, -1.0]), CHAMP, CFG)[0] is False, "2 sur 4 : pas la majorité des 2/3"
    assert ct._new_talent(_m([0.5, 0.5, -0.8, -1.0]), CHAMP, CFG)[0], "3 marchés sur 4 meilleurs"
    assert ct._new_talent(_m([0.0, 0.0, 1.0, 1.0], dd=0.5), CHAMP, CFG)[0] is False, "s'effondre sur l'or"
    assert ct._new_talent(_m([0.0, 0.0, 1.0, 1.0], trades=20), CHAMP, CFG)[0] is False, "ne trade presque pas"
    assert ct._new_talent(_m([0.0, 0.0, 1.0, 1.0]), None, CFG)[0] is False


def test_vein_is_born_grows_thins_and_dies(root, tmp_path):
    veins, lines = ct._veins_update("AUREXIS", [], [_cand(tmp_path, "c1", -0.4, [0, 0, 0, 0])], CHAMP, 10, CFG)
    assert len(veins) == 1 and veins[0]["flux"] == 1.0 and os.path.exists(veins[0]["path"] + ".zip")
    vid = veins[0]["id"]
    # elle progresse : son nouveau cerveau remplace l'ancien, le flux grossit
    veins, _ = ct._veins_update("AUREXIS", veins, [_cand(tmp_path, "c2", -0.2, [0, 0, 0, 0], vein_id=vid)],
                                CHAMP, 11, CFG)
    assert veins[0]["score"] == -0.2 and veins[0]["flux"] == pytest.approx(1.5) and veins[0]["stall"] == 0
    assert open(veins[0]["path"] + ".zip").read() == "c2"
    # elle stagne 3 fois : elle s'amincit puis disparaît (fichier effacé)
    path = veins[0]["path"]
    for g in range(3):
        veins, lines = ct._veins_update("AUREXIS", veins, [_cand(tmp_path, f"s{g}", -0.5, [0, 0, -1, -1],
                                                                 vein_id=vid)], CHAMP, 12 + g, CFG)
    assert veins == [] and not os.path.exists(path + ".zip") and any("disparaît" in l for l in lines)
    assert ct._veins_load("AUREXIS") == []


def test_full_network_replaces_only_the_weakest_and_winner_merges(root, tmp_path):
    veins = []
    for i, s in enumerate([-0.6, -0.3]):
        veins, _ = ct._veins_update("AUREXIS", veins, [_cand(tmp_path, f"a{i}", s, [0, 0, 0, 0])], CHAMP, i, CFG)
    weak = min(veins, key=lambda v: v["score"])
    veins, _ = ct._veins_update("AUREXIS", veins, [_cand(tmp_path, "worse", -0.9, [0, 0, 0, 0])], CHAMP, 5, CFG)
    assert len(veins) == 2 and weak["id"] in [v["id"] for v in veins], "un talent plus faible ne remplace rien"
    veins, _ = ct._veins_update("AUREXIS", veins, [_cand(tmp_path, "better", -0.1, [0, 0, 0, 0])], CHAMP, 6, CFG)
    assert weak["id"] not in [v["id"] for v in veins] and not os.path.exists(weak["path"] + ".zip")
    winner = veins[0]
    veins, lines = ct._veins_update("AUREXIS", veins, [_cand(tmp_path, "w", 0.9, [0, 0, 0, 0], vein_id=winner["id"],
                                                             promoted=True)], CHAMP, 7, CFG)
    assert winner["id"] not in [v["id"] for v in veins] and any("chemin principal" in l for l in lines)


def test_real_cycles_feed_a_vein_end_to_end(tmp_path, monkeypatch):
    """Vrais cycles (miniatures) : le champion est réévalué, une veine semée est nourrie par le DERNIER candidat
    (le témoin #0 repart toujours du champion), son essai est compté, et rien ne casse."""
    import json
    import shutil
    from src.data_loader import generate_synthetic_ohlcv, chronological_split
    from src.features import FEATURE_COLUMNS, add_technical_features, normalize_features
    monkeypatch.chdir(tmp_path)

    def get_data(primary_tf=None):
        df = add_technical_features(generate_synthetic_ohlcv(n_bars=1500, seed=3))
        tr, va, _ = chronological_split(df, 0.7, 0.3)
        tr, st = normalize_features(tr, columns=FEATURE_COLUMNS)
        va, _ = normalize_features(va, st, columns=FEATURE_COLUMNS)
        return tr, va, st, FEATURE_COLUMNS, []
    _, va, _, _, _ = get_data()
    get_data.extra_val = {"H1": [("A", va), ("A miroir", va)]}
    cfg = {"agent": {"policy": "MlpPolicy", "learning_rate": 3e-4, "n_steps": 64, "batch_size": 32,
                     "gamma": 0.99, "gae_lambda": 0.95, "ent_coef": 0.01},
           "continuous": {"candidates_per_cycle": 2, "timesteps_per_cycle": 64, "parallel_workers": 1,
                          "reevaluate_incumbent": True,
                          "veins": {"enabled": True, "styles": ["H1"], "max_veins": 3, "min_trades": 0,
                                    "max_drawdown": 1.0}},
           "multi_market": {"selection": {"enabled": True, "gold_weight": 0.5}},
           "memory": {"db_path": "mem.sqlite", "max_episodes": 500}}
    env_kwargs = dict(window_size=20, initial_balance=10000, transaction_cost=0.0002,
                      reward_type="risk_adjusted", drawdown_penalty=2.0, max_position=1)
    trainer = ct.ContinuousEvolutionTrainer(cfg, get_data, ["H1"], env_kwargs)
    trainer.run_one_cycle()                                   # crée le champion
    os.makedirs(ct._veins_dir("H1"), exist_ok=True)
    seed_path = os.path.join(ct._veins_dir("H1"), "Vseed")
    shutil.copy(ct._champion_model("H1") + ".zip", seed_path + ".zip")
    ct._veins_save("H1", [{"id": "Vseed", "path": seed_path, "score": -99.0, "flux": 1.0, "stall": 0,
                           "tries": 0, "hyperparams": None, "reason": "test"}])
    trainer.run_one_cycle()                                   # champion réévalué + témoin + candidat de veine
    trainer.close()
    veins = json.load(open(os.path.join(ct._veins_dir("H1"), "veines.json"), encoding="utf-8"))
    seed = [v for v in veins if v["id"] == "Vseed"]
    promoted_away = not seed                                  # la veine a pu battre le champion (fusion)
    # 10/10 : « nourrie » = essayée une fois ; qu'elle progresse ou stagne dépend du tirage (test instable avant)
    assert promoted_away or seed[0]["tries"] == 1, "la veine a été nourrie"


def test_vein_judged_against_same_cycle_champion(root, tmp_path):
    """Correction du 08/10 : même résultat brut, mais le champion a moins bien réussi CE cycle -> c'est un progrès
    (le bruit commun à tous les candidats d'un cycle est retiré)."""
    veins, _ = ct._veins_update("AUREXIS", [], [_cand(tmp_path, "n", 0.20, [0, 0, 0, 0])], CHAMP, 1, CFG,
                                inc_score=0.30)
    assert veins[0]["gap"] == pytest.approx(-0.10)
    vid = veins[0]["id"]
    veins, lines = ct._veins_update("AUREXIS", veins, [_cand(tmp_path, "m", 0.20, [0, 0, 0, 0], vein_id=vid)],
                                    CHAMP, 2, CFG, inc_score=0.10)
    assert veins[0]["gap"] == pytest.approx(0.10) and any("PROGRESSE" in l for l in lines)


def test_vein_close_to_champion_is_protected_then_archived(root, tmp_path):
    veins, _ = ct._veins_update("AUREXIS", [], [_cand(tmp_path, "p", 0.25, [0, 0, 0, 0])], CHAMP, 1, CFG,
                                inc_score=0.30)
    vid = veins[0]["id"]
    for g in range(3):                       # max_stall = 3 : une veine lointaine serait morte ici
        veins, _ = ct._veins_update("AUREXIS", veins, [_cand(tmp_path, f"q{g}", -1.0, [0, 0, -1, -1], vein_id=vid)],
                                    CHAMP, 2 + g, CFG, inc_score=0.30)
    assert len(veins) == 1 and veins[0]["flux"] >= 0.3, "proche du champion : protégée"
    for g in range(3):
        veins, lines = ct._veins_update("AUREXIS", veins, [_cand(tmp_path, f"r{g}", -1.0, [0, 0, -1, -1],
                                                                 vein_id=vid)], CHAMP, 5 + g, CFG, inc_score=0.30)
    assert veins == [] and any("archivée" in l for l in lines)
    arch = os.path.join(ct._veins_dir("AUREXIS"), "archives")
    assert os.path.exists(os.path.join(arch, vid + ".zip")), "copie gardée pour pouvoir la relancer"


def test_feeding_follows_the_flux():
    veins = [{"id": "fort", "flux": 4.0}, {"id": "faible", "flux": 0.25}]
    picks = [ct._pick_vein(veins, g)["id"] for g in range(400)]
    assert 0.85 < picks.count("fort") / len(picks) < 0.99
    assert ct._pick_vein([], 3) is None
    assert ct._pick_vein(veins, 7)["id"] == ct._pick_vein(veins, 7)["id"], "reproductible"
