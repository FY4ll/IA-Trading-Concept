import sys
sys.path.insert(0, r"C:\Users\utilisateur\Documents\Test_IA\runs\20260919_envv2\code")
import numpy as np

MIN_TRADES_FOR_RELIABLE_STATS = 5

def weighted(per_window, key):
    weights = np.array([m["n_trades"] for m in per_window], dtype=np.float64)
    reliable = weights >= MIN_TRADES_FOR_RELIABLE_STATS
    reliable_weights = np.where(reliable, weights, 0.0) if reliable.any() else weights
    values = np.array([m[key] for m in per_window], dtype=np.float64)
    if reliable_weights.sum() <= 0:
        return float(np.mean(values))
    return float(np.average(values, weights=reliable_weights))

# M30 champion gen:29 per_window (from meta.json)
m30_windows = [
    {"n_trades": 49, "sortino": 0.06844264947750987, "sharpe": 0.41170079853352515, "total_return": 0.003088078832202301},
    {"n_trades": 0,  "sortino": 0.0, "sharpe": 0.0, "total_return": 0.0},
    {"n_trades": 3,  "sortino": 2057.865947796153, "sharpe": 1.949542728761224, "total_return": 0.001974021998113029},
    {"n_trades": 15, "sortino": -0.02211804158595334, "sharpe": -0.44254451111597687, "total_return": -0.0029513588250104084},
]
sortino = weighted(m30_windows, "sortino")
sharpe = weighted(m30_windows, "sharpe")
total_return = weighted(m30_windows, "total_return")
drawdown = 0.01967741097477603
score = sortino - 2.0 * drawdown
print(f"M30 corrige : sortino={sortino:.4f} sharpe={sharpe:.4f} total_return={total_return:.5f} score={score:.4f}")

# H4 champion gen:69 per_window
h4_windows = [
    {"n_trades": 38, "sortino": 0.023154783159419875, "sharpe": 0.0430492409075943, "total_return": 0.0012800318852035364},
    {"n_trades": 3,  "sortino": 118.51118398063264, "sharpe": 1.2254598865320034, "total_return": 0.022475093471929775},
    {"n_trades": 0,  "sortino": 0.0, "sharpe": 0.0, "total_return": 0.0},
    {"n_trades": 59, "sortino": -0.07541952756166179, "sharpe": -0.12043675578086699, "total_return": -0.013356282404636488},
]
sortino_h4 = weighted(h4_windows, "sortino")
sharpe_h4 = weighted(h4_windows, "sharpe")
total_return_h4 = weighted(h4_windows, "total_return")
drawdown_h4 = 0.08893741265596829
score_h4 = sortino_h4 - 2.0 * drawdown_h4
print(f"H4 corrige : sortino={sortino_h4:.4f} sharpe={sharpe_h4:.4f} total_return={total_return_h4:.5f} score={score_h4:.4f}")

# Sanity check: a normal case (D1 champion) should be UNCHANGED by the fix
d1_windows = [
    {"n_trades": 0,  "sortino": 0.0, "sharpe": 0.0, "total_return": 0.0},
    {"n_trades": 72, "sortino": 3.127752032175931, "sharpe": 2.128868128380705, "total_return": 0.2527925888491196},
    {"n_trades": 28, "sortino": 0.8034906501367193, "sharpe": 0.8573080690083639, "total_return": 0.08574324440910797},
    {"n_trades": 0,  "sortino": 0.0, "sharpe": 0.0, "total_return": 0.0},
]
sortino_d1 = weighted(d1_windows, "sortino")
print(f"D1 (verif non-regression) : sortino={sortino_d1:.6f} (attendu ~2.4769588)")
assert abs(sortino_d1 - 2.4769588452049516) < 1e-6, "REGRESSION: D1 ne devrait pas changer"
print("OK -- aucune regression sur un cas normal (D1)")
