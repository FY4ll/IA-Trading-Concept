"""Prevoir l'agitation des prochaines bougies M15 (lecture seule, donnees du projet).
Cible : log du range moyen (H-L) des h prochaines bougies. Predicteurs : profil heure x jour (appris sur la 1re moitie),
log range moyen des 4, 96 et 480 dernieres bougies. OLS sur 1re moitie, R2 hors echantillon sur la 2e moitie."""
import numpy as np, pandas as pd, sys
sys.path.insert(0, __file__.rsplit("\\", 1)[0])
from mesure_agitation import load, FILES

for name in ["EURUSD", "USDJPY", "XAUUSD", "USA500", "WTI", "BTCUSD"]:
    df = load(FILES[name])
    df = df[df.high > df.low]
    hl = np.log(df.high / df.low)
    lhl = np.log(hl)
    how = (df.index.dayofweek * 24 + df.index.hour).values
    n = len(df); half = n // 2
    seas_tab = pd.Series(lhl.values[:half]).groupby(how[:half]).mean()
    seas = pd.Series(how).map(seas_tab).fillna(seas_tab.mean()).values
    res = {}
    for h in (1, 4, 16, 96):
        tgt = np.log(pd.Series(hl.values).rolling(h).mean().shift(-h)).values
        # profil saisonnier moyen des h prochaines bougies
        seas_f = pd.Series(seas).rolling(h).mean().shift(-h).values
        f4 = np.log(pd.Series(hl.values).rolling(4).mean()).values
        f96 = np.log(pd.Series(hl.values).rolling(96).mean()).values
        f480 = np.log(pd.Series(hl.values).rolling(480).mean()).values
        seas_now = pd.Series(seas).rolling(96).mean().values  # niveau saisonnier moyen recent
        sets = {"saison_seule": [seas_f], "passe_recent_seul": [f4, f96, f480],
                "saison+passe": [seas_f, f4 - pd.Series(seas).rolling(4).mean().values, f96, f480]}
        for lab, cols in sets.items():
            X = np.column_stack([np.ones(n)] + cols)
            ok = ~np.isnan(X).any(1) & ~np.isnan(tgt) & np.isfinite(tgt)
            tr = ok.copy(); tr[half:] = False
            te = ok.copy(); te[:half + 480] = False
            b = np.linalg.lstsq(X[tr], tgt[tr], rcond=None)[0]
            p = X[te] @ b
            r2 = 1 - ((tgt[te] - p) ** 2).sum() / ((tgt[te] - tgt[tr].mean()) ** 2).sum()
            res[f"h{h}_{lab}"] = round(float(r2), 3)
    print(name, res, flush=True)
