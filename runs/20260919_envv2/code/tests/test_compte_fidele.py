"""EXAMEN SUR LE COMPTE FIDÈLE (11/10/2026) : la note d'examen d'AUREXIS est calculée sur UN compte qui rejoue les
trades de tous les marchés dans l'ordre du temps, avec le budget de risque du vrai compte (4 %), les murs FTMO et le
frein -- et plus sur une addition de marchés comme si le budget n'existait pas (verdict de la nuit : 79 % des trades
du champion 442 refusés par le vrai compte)."""
import numpy as np
import pandas as pd
import pytest

from src.note_argent import note_compte_fidele


def _trades(name, n, start="2024-01-01 10:00", every_h=24, risk=0.01, res=0.005, hold_h=2):
    t0 = pd.Timestamp(start)
    return [{"marche": name, "ouvert": t0 + pd.Timedelta(hours=every_h * i),
             "ferme": t0 + pd.Timedelta(hours=every_h * i + hold_h), "risque": risk, "resultat": res}
            for i in range(n)]


def _entry(trades, start="2024-01-01", end="2024-04-30"):
    return {"trades": trades, "debut": pd.Timestamp(start), "fin": pd.Timestamp(end)}


def test_budget_refuses_what_the_real_account_would_refuse():
    """10 marchés qui ouvrent tous en même temps à 1 % de risque : le vrai compte n'en prend que 4 (budget 4 %)."""
    many = {f"M{i}": _entry(_trades(f"M{i}", 60)) for i in range(10)}
    out = note_compte_fidele(many, cfg={"n_sims": 200})
    assert out["compte_fidele"] and out["trades_pris"] == 4 * 60 and out["trades_refuses"] == 6 * 60
    assert out["n_marches"] == 10


def test_same_trades_spread_in_time_are_all_taken_and_score_better():
    """Mêmes trades gagnants, mais étalés dans le temps : tous pris -> plus de gain -> meilleure note."""
    piled = {f"M{i}": _entry(_trades(f"M{i}", 60)) for i in range(10)}
    spread = {f"M{i}": _entry(_trades(f"M{i}", 60, start=f"2024-01-01 {i:02d}:00", hold_h=0.5)) for i in range(10)}
    a = note_compte_fidele(piled, cfg={"n_sims": 200})
    b = note_compte_fidele(spread, cfg={"n_sims": 200})
    assert b["trades_refuses"] == 0 and b["mensuel"] > a["mensuel"] and b["note"] >= a["note"]


def test_mirrors_excluded_and_empty_is_safe():
    e = {"EURUSD": _entry(_trades("EURUSD", 20)), "EURUSD miroir": _entry(_trades("EURUSD miroir", 20, res=-0.005))}
    out = note_compte_fidele(e, cfg={"n_sims": 200})
    assert out["n_marches"] == 1 and out["trades_pris"] == 20 and out["mensuel"] > 0
    empty = note_compte_fidele({}, cfg={"n_sims": 100})
    assert empty["trades_pris"] == 0 and np.isfinite(empty["note"])


def test_losing_account_hits_the_wall_and_is_punished():
    lose = {f"M{i}": _entry(_trades(f"M{i}", 80, start=f"2024-01-01 {i:02d}:00", hold_h=0.5, res=-0.004))
            for i in range(5)}
    out = note_compte_fidele(lose, cfg={"n_sims": 200})
    assert out["arret"] == "total" and out["baisse_compte"] >= 0.09 and out["note"] < -5
    assert out["reussite"] == 0.0 and out["echec"] == 1.0, "mur touché pendant l'examen = challenge raté"


def test_daily_wall_counts_as_a_failed_challenge():
    """Un seul jour à -5 % (mur du jour), le reste gagnant : challenge raté quand même (règle FTMO)."""
    crash = [{"marche": f"M{i}", "ouvert": pd.Timestamp("2024-01-10 10:00"), "ferme": pd.Timestamp("2024-01-10 12:00"),
              "risque": 0.01, "resultat": -0.0125} for i in range(4)]
    good = _trades("M9", 80, start="2024-01-11 10:00", res=0.004)
    out = note_compte_fidele({"A": _entry(crash), "B": _entry(good)}, cfg={"n_sims": 200})
    assert out["murs_jour"] == 1 and out["echec"] == 1.0 and out["reussite"] == 0.0


def _mk(close, start="2024-01-01"):
    close = np.asarray(close, dtype=float)
    return pd.DataFrame({"time": pd.date_range(start, periods=len(close), freq="h"), "open": close,
                         "high": close * 1.0005, "low": close * 0.9995, "close": close, "f": 0.0})


def test_exam_uses_the_faithful_account_when_enabled(tmp_path):
    """Branchement réel : avec `compte_fidele`, la note de chaque période vient du compte fidèle (trades pris/refusés
    visibles), la moins bonne période fait la note ; l'or de la validation fixe n'est pas mêlé aux périodes tirées."""
    import src.continuous_trainer as ct
    rng = np.random.default_rng(6)
    gold = _mk(100 * np.cumprod(1 + rng.normal(0.0001, 0.002, 2400)), start="2020-01-01")
    p1 = _mk(100 * np.cumprod(1 + rng.normal(0.0004, 0.002, 900)), start="2023-03-01")
    p2 = _mk(100 * np.cumprod(1 + rng.normal(-0.0004, 0.002, 900)), start="2025-03-01")
    env_kwargs = dict(window_size=5, initial_balance=10000, transaction_cost=0.0, reward_type="pnl",
                      drawdown_penalty=0.0, max_position=1, feature_columns=["f"], risk_sizing_pct=0.005)
    spec = {"train_df": gold.iloc[:1200].reset_index(drop=True), "val_df": gold.iloc[1200:].reset_index(drop=True),
            "env_kwargs": env_kwargs, "hyperparams": {"n_steps": 64, "batch_size": 16}, "warm_start_path": None,
            "timesteps": 64, "generation": 1, "style": "H1", "slot": 0, "context_timeframes": [], "eval_windows": 1,
            "fitness_metric": "sortino",
            "extra_val": [("XAUUSD p1", p1), ("EURUSD p1", p1), ("XAUUSD p2", p2), ("EURUSD p2", p2)],
            "note_argent": {"n_sims": 200, "compte_fidele": True}, "out_path": str(tmp_path / "c")}
    out = ct._train_candidate_worker(spec)
    pf = out["metrics"]["portefeuille"]
    assert pf.get("compte_fidele") and [p["periode"] for p in pf["periodes"]] == [1, 2]
    assert all(p["trades_pris"] is not None for p in pf["periodes"])
    assert out["score"] == pytest.approx(min(p["note"] for p in pf["periodes"]))
    assert pf["n_marches"] == 2, "or + euro de la période, sans l'or de la validation fixe"
