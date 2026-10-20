import numpy as np

def clip(v):
    return float(np.clip(v, -10.0, 10.0))

def weighted(per_window, key, MIN=5):
    weights = np.array([m["n_trades"] for m in per_window], dtype=np.float64)
    reliable = weights >= MIN
    values = np.array([m[key] for m in per_window], dtype=np.float64)
    if reliable.any():
        return float(np.average(values, weights=np.where(reliable, weights, 0.0)))
    return float(np.mean(values))

# H4 gen:340 EXACT case that just broke (raw sortino BEFORE clipping)
h4_340_raw_sortino = [97.7791138745587, 0.0, 0.0, 0.17078508740192933]
h4_340_ntrades =     [1, 0, 0, 4]

# Simulate compute_metrics clipping happening PER WINDOW before aggregation
clipped = [clip(s) for s in h4_340_raw_sortino]
print("sortino par fenetre apres clip:", [round(c,3) for c in clipped])

windows = [{"n_trades": n, "sortino": s} for n, s in zip(h4_340_ntrades, clipped)]
sortino_agg = weighted(windows, "sortino")
drawdown = 0.03765079050981265
score = sortino_agg - 2.0 * drawdown
print(f"H4 gen:340 recorrige : sortino_agg={sortino_agg:.4f} score={score:.4f}")
assert abs(score) < 5, f"Score encore anormalement eleve: {score}"
print("OK -- score dans une plage realiste")

# Stress-test: even 3 tiny windows all at the clip ceiling should stay bounded
extreme = [{"n_trades": 1, "sortino": 10.0}, {"n_trades": 1, "sortino": 10.0}, {"n_trades": 0, "sortino": 0.0}, {"n_trades": 1, "sortino": 10.0}]
print("Cas extreme (toutes fenetres a 1 trade, sortino plafonne a 10) :", weighted(extreme, "sortino"))

# Sanity: normal D1-like case still unaffected (weights >=5 present)
d1_windows = [
    {"n_trades": 0,  "sortino": 0.0},
    {"n_trades": 72, "sortino": clip(3.127752032175931)},
    {"n_trades": 28, "sortino": clip(0.8034906501367193)},
    {"n_trades": 0,  "sortino": 0.0},
]
sortino_d1 = weighted(d1_windows, "sortino")
print(f"D1 (verif non-regression) : sortino={sortino_d1:.6f} (attendu ~2.4769588)")
assert abs(sortino_d1 - 2.4769588452049516) < 1e-6
print("OK -- aucune regression sur D1")
