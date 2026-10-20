"""Récompense « trade par trade » (08/10/2026) : rien pendant le trade, le résultat en R à la clôture."""
import numpy as np

from src.data_loader import generate_synthetic_ohlcv
from src.trading_env import TradingEnv


def test_reward_only_at_trade_close_in_r_units():
    df = generate_synthetic_ohlcv(n_bars=400, seed=7)
    env = TradingEnv(df, window_size=10, feature_columns=["close"], transaction_cost=0.0, reward_type="trade_r")
    env.reset()
    rewards = []
    for a in [2, 2, 2, 2, 1, 1, 0, 0, 1]:            # achat tenu 4 bougies puis sortie, vente tenue puis sortie
        _, r, term, _, _ = env.step(a)
        rewards.append(r)
        if term:
            break
    closes = [t["pnl_pct"] for t in env.trade_log]
    assert len(closes) == 2
    non_zero = [r for r in rewards if r != 0.0]
    assert len(non_zero) == 2, "une récompense par trade clôturé, zéro pendant qu'il tourne"
    for r, p in zip(non_zero, closes):
        assert np.isclose(r, np.clip(p / 0.01, -3, 5) - 0.05)


def test_incomplete_champion_sheet_is_refused_not_a_crash():
    """Incident du 08/10 23h37 : une fiche de champion sans « sharpe » faisait planter le cycle."""
    from src.backtester import passes_validation
    cfg = {"validation": {"min_sharpe_to_go_live": 1.0, "max_drawdown_allowed": 0.3}}
    assert passes_validation({"n_trades": 118, "max_drawdown": 0.03}, cfg, style="AUREXIS") is False


def test_reset_restarts_the_count():
    df = generate_synthetic_ohlcv(n_bars=200, seed=8)
    env = TradingEnv(df, window_size=10, feature_columns=["close"], transaction_cost=0.0, reward_type="trade_r")
    env.reset()
    for a in [2, 2, 1]:
        env.step(a)
    env.reset()
    _, r, _, _, _ = env.step(1)
    assert r == 0.0
