"""La sélection v3 prend les MÊMES décisions que Run A (note fiable, tri du petit examen, promotion, talents, veines)."""
import os
import sys

import pytest

from aurexis.juge import selection as S
from aurexis.tests.test_cerveau_equivalence import STAGE


@pytest.fixture(scope="module")
def old():
    if STAGE not in sys.path:
        sys.path.append(STAGE)
    import src.continuous_trainer as ct
    return ct


def _m(notes, dd=0.1, trades=300):
    mk = ["EURUSD", "USDJPY", "XAUUSD miroir", "EURUSD miroir"]
    return {"max_drawdown": dd, "n_trades": trades, "markets": [{"market": k, "score": v, "n_trades": 30}
                                                                for k, v in zip(mk, notes)]}


def test_note_fiable_identique(old):
    for s in (-1.3, -0.2, 0.0, 0.4, 2.0):
        for n in (0, 5, 60, 300, 900):
            assert S.note_fiable(s, n, 300) == old._confident_score(s, n, 300)


def test_talents_identiques(old):
    champ = _m([0, 0, -1, -1])
    rules = {"min_trades": 100, "max_drawdown": 0.3, "min_mirror_gain": 0.25}
    for notes, dd, tr in [([0, 0, -.2, -.3], .1, 300), ([.5, 0, -1, -1], .1, 300), ([.5, .5, -.8, -1], .1, 300),
                          ([1, 1, 1, 1], .5, 300), ([1, 1, 1, 1], .1, 20)]:
        assert S.nouveau_talent(_m(notes, dd, tr), champ, rules) == old._new_talent(_m(notes, dd, tr), champ, rules)


def test_tri_et_promotion():
    retenus = S.tri_petit_examen({"a": 0.30, "b": -0.10, "c": -0.60}, note_champion=0.0, marge=0.25, garder=1)
    assert retenus == {"a", "b"}
    assert S.tri_petit_examen({"a": -2.0, "b": -3.0}, 0.0, 0.25, 1) == {"a"}, "le meilleur passe toujours"
    actif = lambda m: m.get("n_trades", 0) >= 100
    champ = {"score": -0.3, "metrics": {"n_trades": 260}}
    feignant = {"score": 0.07, "metrics": {"n_trades": 28}}
    bon = {"score": -0.2, "metrics": {"n_trades": 300}}
    assert S.promotion(champ, [feignant], 300, 0.05, actif) is None, "jamais une IA qui ne trade pas"
    assert S.promotion(champ, [feignant, bon], 300, 0.05, actif) is bon
    assert S.promotion({"score": 0.07, "metrics": {"n_trades": 28}}, [bon], 300, 0.05, actif) is bon


def test_veines_identiques(old, tmp_path, monkeypatch):
    monkeypatch.setattr(old, "MODELS_ROOT", str(tmp_path / "old"))
    rules = {"max_veins": 2, "max_stall": 3, "min_trades": 100, "max_drawdown": 0.3, "min_mirror_gain": 0.25}
    champ = _m([0, 0, -1, -1])

    def zipf(name):
        p = str(tmp_path / name)
        open(p + ".zip", "w").write(name)
        return p
    seq = [(0.20, [0, 0, 0, 0], None), (0.35, [0, 0, 0, 0], "first"), (0.10, [0, 0, -1, -1], "first")]
    v_new, v_old = [], []
    for g, (score, notes, vein) in enumerate(seq):
        f = zipf(f"c{g}")
        vid_new = v_new[0]["id"] if (vein and v_new) else None
        vid_old = v_old[0]["id"] if (vein and v_old) else None
        v_new, _ = S.faire_vivre_veines(str(tmp_path / "new"), v_new,
                                        [{"id": f"c{g}", "score": score, "metrics": _m(notes), "fichier": f,
                                          "veine": vid_new}], champ, 0.3, g, rules)
        f2 = zipf(f"AUREXIS_0_{g}")
        v_old, _ = old._veins_update("AUREXIS", v_old, [{"style": "AUREXIS", "score": score, "metrics": _m(notes),
                                                          "model_path": f2, "vein_id": vid_old}], champ, g, rules,
                                     inc_score=0.3)
        assert [(round(v["gap"], 9), round(v["flux"], 9), v["stall"]) for v in v_new] == \
               [(round(v["gap"], 9), round(v["flux"], 9), v["stall"]) for v in v_old]
