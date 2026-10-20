"""PREUVE de l'étape 2 (partie juge) : le nouvel examen donne EXACTEMENT la même note que Run A au champion actuel
(or en fenêtres + scénarios de crise + autres marchés), et le petit examen aussi."""
import os
import sys

import numpy as np
import pytest

from aurexis.tests.test_cerveau_equivalence import CHAMPION, KW, STAGE  # noqa: F401 -- mêmes réglages


def _frame(nom, n=4500):
    import json
    from aurexis.donnees import marches, reserve
    from aurexis.vision.fabrique import construire
    m15 = reserve.lire(nom, marches.source(nom)).tail(n + 3000).reset_index(drop=True)
    df = construire(nom, m15, ["M30", "H1", "H4", "D1", "W1", "MN1"], None)
    cols = json.load(open(os.path.join(os.path.dirname(CHAMPION), "meta.json"), encoding="utf-8"))["feature_columns"]
    df = df.reindex(columns=list(df.columns) + [c for c in cols if c not in df.columns], fill_value=0.0)
    df = df.iloc[3000:].reset_index(drop=True)
    df[cols] = ((df[cols] - df[cols].mean()) / (df[cols].std() + 1e-8)).clip(-5, 5).fillna(0.0).astype("float32")
    return df, cols


def test_meme_note_que_run_a():
    if STAGE not in sys.path:
        sys.path.append(STAGE)
    import src.backtester as ob
    import src.continuous_trainer as oc
    from src.agent import TradingAgent as OldAgent
    from src.trading_env import TradingEnv as OldEnv
    from aurexis.cerveau.agent import TradingAgent
    from aurexis.cerveau.simulateur import TradingEnv
    from aurexis.juge import examen
    val, cols = _frame("XAUUSD")
    autres = [("EURUSD", _frame("EURUSD", 3000)[0]), ("BTCUSD", _frame("BTCUSD", 3000)[0])]
    kw = {**KW, "feature_columns": cols}
    old_agent = OldAgent.load(CHAMPION, OldEnv(val, **kw), {"algo": "PPO", "device": "cpu"})
    new_agent = TradingAgent.load(CHAMPION, TradingEnv(val, **kw), {"algo": "PPO", "device": "cpu"})
    m_old = ob.evaluate_agent_walkforward(old_agent, val, kw, n_windows=2, stress_test=True,
                                          stress_seed=oc._stress_seed_for_style("AUREXIS"), timeframe="M15")
    s_old = m_old["sortino"] - 2.0 * m_old["max_drawdown"]
    s_old = oc._multi_market_score(old_agent, {"extra_val": autres, "env_kwargs": kw, "style": "AUREXIS"},
                                   s_old, m_old, "sortino")
    r = examen.examen_complet(new_agent, val, autres, kw, poids_or=0.5, fenetres=2, crises=True)
    assert np.isclose(r["score"], s_old, rtol=0, atol=1e-12), (r["score"], s_old)
    for k in ("sharpe", "max_drawdown", "total_return", "n_trades", "gold_score", "markets_score"):
        assert np.isclose(r["metrics"][k], m_old[k], rtol=0, atol=1e-12), k
    assert [p["score"] for p in r["metrics"]["markets"]] == [p["score"] for p in m_old["markets"]]
    q = examen.petit_examen(new_agent, autres, kw)
    q_old = oc._quick_exam_result(old_agent, {"quick_exam": autres, "env_kwargs": kw, "style": "AUREXIS",
                                              "out_path": os.path.join(os.environ.get("TEMP", "."), "q_old"),
                                              "generation": 0, "slot": 0, "context_timeframes": [], "hyperparams": {}})
    assert np.isclose(q["score"], q_old["quick_score"], rtol=0, atol=1e-12)
    assert examen.assez_actif(m_old, 100, 200) == oc._active_enough(m_old, {"min_trades": 100, "min_market_trades": 200})
