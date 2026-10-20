"""
market_brain.py
================
CERVEAU DE MARCHÉ de l'IA (05/10/2026) -- codé par nous, 100 % local, sans API externe.

Là où les agents RL ne voient que des indicateurs techniques H1, le cerveau construit chaque
jour un ÉTAT DE MARCHÉ structuré de l'or et apprend COMMENT ses moteurs le font bouger :

  prix / tendance   : momentum 5-120 j, distance aux moyennes 50/200, efficacité de tendance,
                      plus haut 1 an, cassures 20 j, RSI ;
  volatilité        : réalisée 20 j, ratio 20/120 (expansion/compression), ATR ;
  macro (FRED)      : taux réel 10 ans US (DFII10), dollar large (DTWEXBGS), inflation anticipée
                      (T10YIE), VIX, taux Fed -- avec leur DÉLAI DE PUBLICATION réel ;
  marchés liés      : argent (ratio or/argent), EURUSD, USDJPY.

Il prédit la probabilité que l'or monte sur l'horizon choisi (10 jours par défaut), validée en
walk-forward avec purge (jamais d'information future), et EXPLIQUE sa thèse : quels moteurs
poussent à la hausse, lesquels à la baisse, avec leur poids appris.
"""
from __future__ import annotations
import json
import os

import numpy as np
import pandas as pd

FRED_SERIES = {  # id -> délai de publication prudent (jours calendaires)
    "DFII10": 2, "DTWEXBGS": 7, "T10YIE": 2, "VIXCLS": 1, "FEDFUNDS": 35,
}
CROSS = ["XAGUSD", "EURUSD", "USDJPY"]

TECH_FEATURES = ["ret_5", "ret_20", "ret_60", "ret_120", "dist_sma50", "dist_sma200", "sma50_slope",
                 "er_20", "er_60", "dd_252", "brk_20", "rsi_14", "vol_20", "vol_ratio", "atr_pct"]
MACRO_FEATURES = ["ry_level", "ry_chg5", "ry_chg20", "usd_chg5", "usd_chg20", "bei_chg20",
                  "vix_level", "vix_chg5", "ff_chg90"]
CROSS_FEATURES = ["gsr_z60", "xag_ret20", "eur_ret20", "jpy_ret20"]

LABELS_FR = {
    "ret_5": "momentum 1 semaine", "ret_20": "momentum 1 mois", "ret_60": "momentum 3 mois",
    "ret_120": "momentum 6 mois", "dist_sma50": "écart à la moyenne 50 j", "dist_sma200": "écart à la moyenne 200 j",
    "sma50_slope": "pente de la moyenne 50 j", "er_20": "netteté de la tendance 1 mois",
    "er_60": "netteté de la tendance 3 mois", "dd_252": "recul depuis le plus haut annuel",
    "brk_20": "position dans le canal 20 j", "rsi_14": "RSI 14", "vol_20": "volatilité 1 mois",
    "vol_ratio": "expansion de volatilité", "atr_pct": "ATR", "ry_level": "taux réel US 10 ans",
    "ry_chg5": "variation du taux réel (1 sem.)", "ry_chg20": "variation du taux réel (1 mois)",
    "usd_chg5": "variation du dollar (1 sem.)", "usd_chg20": "variation du dollar (1 mois)",
    "bei_chg20": "variation de l'inflation anticipée", "vix_level": "niveau de peur (VIX)",
    "vix_chg5": "variation du VIX", "ff_chg90": "variation du taux Fed (3 mois)",
    "gsr_z60": "ratio or/argent (écart)", "xag_ret20": "momentum de l'argent",
    "eur_ret20": "momentum EURUSD (dollar faible si +)", "jpy_ret20": "momentum USDJPY",
}


# --- chargement ----------------------------------------------------------------------------------------
def load_gold_daily(cfg: dict) -> pd.DataFrame:
    from src.multi_timeframe import discover_files
    from src.data_loader import load_kaggle_ohlcv_csv
    d = load_kaggle_ohlcv_csv(discover_files(cfg["data"]["folder"])["D1"])
    d["time"] = pd.to_datetime(d["time"]).dt.normalize()
    return d.drop_duplicates("time").set_index("time").sort_index()


def load_fred(cache_dir: str = os.path.join("data", "cache")) -> dict[str, pd.Series]:
    out = {}
    for sid in FRED_SERIES:
        path = os.path.join(cache_dir, f"fred_hist_{sid}.json")
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8") as f:
            obs = json.load(f).get("observations", [])
        s = pd.Series({pd.Timestamp(o["date"]): pd.to_numeric(o["value"], errors="coerce") for o in obs}).dropna()
        out[sid] = s.sort_index()
    return out


def load_cross(cfg: dict) -> dict[str, pd.Series]:
    folder = (cfg.get("data") or {}).get("cross_asset_folder") or os.path.join(
        os.path.dirname(os.path.abspath(cfg["data"]["folder"])), "cross_asset")
    out = {}
    for sym in CROSS:
        p = os.path.join(folder, f"{sym}_D1.csv")
        if os.path.exists(p):
            d = pd.read_csv(p)
            out[sym] = pd.Series(d["close"].to_numpy(float), index=pd.to_datetime(d["time"]).dt.normalize()).sort_index()
    return out


def _available(s: pd.Series, index: pd.DatetimeIndex, lag_days: int) -> pd.Series:
    """Valeur connue à la clôture de chaque jour de `index` : publiée au plus tard `lag_days` avant."""
    shifted = s.copy()
    shifted.index = shifted.index + pd.Timedelta(days=lag_days)
    return shifted.reindex(shifted.index.union(index)).ffill().reindex(index)


# --- état de marché quotidien ------------------------------------------------------------------------
def build_daily_state(gold: pd.DataFrame, fred: dict | None = None, cross: dict | None = None) -> pd.DataFrame:
    """Une ligne par jour de cotation : tout ce qui est connu à la CLÔTURE de ce jour."""
    c, h, l = gold["close"], gold["high"], gold["low"]
    r = np.log(c).diff()
    f = pd.DataFrame(index=gold.index)
    for n in (5, 20, 60, 120):
        f[f"ret_{n}"] = c.pct_change(n)
    sma50, sma200 = c.rolling(50).mean(), c.rolling(200).mean()
    f["dist_sma50"] = c / sma50 - 1
    f["dist_sma200"] = c / sma200 - 1
    f["sma50_slope"] = sma50.pct_change(10)
    for n in (20, 60):
        f[f"er_{n}"] = (c.diff(n).abs() / c.diff().abs().rolling(n).sum()) * np.sign(c.diff(n))
    f["dd_252"] = c / c.rolling(252).max() - 1
    hi20, lo20 = h.rolling(20).max(), l.rolling(20).min()
    f["brk_20"] = (c - lo20) / (hi20 - lo20).replace(0, np.nan)
    delta = c.diff()
    up = delta.clip(lower=0).ewm(alpha=1 / 14).mean()
    dn = (-delta.clip(upper=0)).ewm(alpha=1 / 14).mean()
    f["rsi_14"] = 100 - 100 / (1 + up / dn.replace(0, np.nan))
    f["vol_20"] = r.rolling(20).std() * np.sqrt(252)
    f["vol_ratio"] = r.rolling(20).std() / r.rolling(120).std()
    tr = pd.concat([h - l, (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
    f["atr_pct"] = tr.rolling(14).mean() / c

    idx = gold.index
    fred = fred or {}
    if "DFII10" in fred:
        ry = _available(fred["DFII10"], idx, FRED_SERIES["DFII10"])
        f["ry_level"], f["ry_chg5"], f["ry_chg20"] = ry, ry.diff(5), ry.diff(20)
    if "DTWEXBGS" in fred:
        usd = _available(fred["DTWEXBGS"], idx, FRED_SERIES["DTWEXBGS"])
        f["usd_chg5"], f["usd_chg20"] = usd.pct_change(5), usd.pct_change(20)
    if "T10YIE" in fred:
        f["bei_chg20"] = _available(fred["T10YIE"], idx, FRED_SERIES["T10YIE"]).diff(20)
    if "VIXCLS" in fred:
        vix = _available(fred["VIXCLS"], idx, FRED_SERIES["VIXCLS"])
        f["vix_level"], f["vix_chg5"] = vix, vix.diff(5)
    if "FEDFUNDS" in fred:
        f["ff_chg90"] = _available(fred["FEDFUNDS"], idx, FRED_SERIES["FEDFUNDS"]).diff(63)

    cross = cross or {}
    if "XAGUSD" in cross:
        xag = _available(cross["XAGUSD"], idx, 0)
        gsr = np.log(c / xag)
        f["gsr_z60"] = (gsr - gsr.rolling(60).mean()) / gsr.rolling(60).std()
        f["xag_ret20"] = xag.pct_change(20)
    if "EURUSD" in cross:
        f["eur_ret20"] = _available(cross["EURUSD"], idx, 0).pct_change(20)
    if "USDJPY" in cross:
        f["jpy_ret20"] = _available(cross["USDJPY"], idx, 0).pct_change(20)
    f["close"] = c
    return f.replace([np.inf, -np.inf], np.nan)


def add_target(state: pd.DataFrame, horizon: int = 10) -> pd.DataFrame:
    s = state.copy()
    s["fwd_ret"] = s["close"].shift(-horizon) / s["close"] - 1
    s["y"] = (s["fwd_ret"] > 0).astype(float).where(s["fwd_ret"].notna())
    return s


# --- modèles ------------------------------------------------------------------------------------------
def make_model(kind: str):
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    from sklearn.impute import SimpleImputer
    if kind == "logit":
        from sklearn.linear_model import LogisticRegression
        return make_pipeline(SimpleImputer(strategy="median"), StandardScaler(),
                             LogisticRegression(C=0.05, max_iter=2000))
    if kind == "gbm":
        from sklearn.ensemble import HistGradientBoostingClassifier
        return HistGradientBoostingClassifier(max_depth=3, learning_rate=0.03, max_iter=300,
                                              min_samples_leaf=80, l2_regularization=1.0, random_state=7)
    raise ValueError(kind)


def walk_forward(data: pd.DataFrame, features: list[str], kind: str, horizon: int,
                 first_test_year: int = 2012, last_date=None, min_train_rows: int = 500) -> pd.DataFrame:
    """Réentraînement annuel à fenêtre croissante ; purge de `horizon` jours entre la fin de
    l'entraînement et le début du test (les cibles se chevauchent). Renvoie p_up hors échantillon."""
    out = []
    d = data[data.index <= last_date] if last_date is not None else data
    years = sorted({t.year for t in d.index if t.year >= first_test_year})
    for yr in years:
        test = d[d.index.year == yr]
        train_end = test.index[0] - pd.Timedelta(days=int(horizon * 1.5) + 1)
        train = d[(d.index <= train_end) & d["y"].notna()].dropna(subset=features, how="all")
        if len(train) < min_train_rows or len(test) == 0:
            continue
        usable = [f for f in features if train[f].notna().mean() > 0.5]  # moteurs déjà disponibles à cette date
        if not usable:
            continue
        m = make_model(kind)
        m.fit(train[usable], train["y"])
        p = m.predict_proba(test[usable])[:, 1]
        out.append(pd.DataFrame({"p_up": p}, index=test.index))
    return pd.concat(out) if out else pd.DataFrame(columns=["p_up"])


def explain_logit(model, row: pd.Series, features: list[str], top: int = 4) -> dict:
    """Contributions (coefficient x valeur standardisée) des moteurs pour UNE journée."""
    imp, sc, lr = model.steps[0][1], model.steps[1][1], model.steps[2][1]
    x = sc.transform(imp.transform(row[features].to_frame().T))[0]
    contrib = lr.coef_[0] * x
    order = np.argsort(contrib)
    pro = [(features[i], float(contrib[i])) for i in order[::-1][:top] if contrib[i] > 0]
    con = [(features[i], float(contrib[i])) for i in order[:top] if contrib[i] < 0]
    return {"pro": pro, "con": con}


def thesis_text(p_up: float, expl: dict, horizon: int) -> str:
    sens = "HAUSSIER" if p_up >= 0.5 else "BAISSIER"
    pro = ", ".join(LABELS_FR.get(k, k) for k, _ in expl["pro"]) or "aucun"
    con = ", ".join(LABELS_FR.get(k, k) for k, _ in expl["con"]) or "aucun"
    return (f"Biais {sens} à {horizon} jours (probabilité de hausse {p_up:.0%}). "
            f"Moteurs haussiers : {pro}. Moteurs baissiers : {con}.")


# --- traduction en trading (recherche) ---------------------------------------------------------------
def positions_from_proba(p: pd.Series, full_at: float = 0.15, long_only: bool = False) -> pd.Series:
    pos = ((p - 0.5) / full_at).clip(-1, 1)
    return pos.clip(lower=0) if long_only else pos


def backtest_daily(close: pd.Series, pos: pd.Series, cost: float = 0.0002, target_vol: float = 0.10,
                   vol_lookback: int = 20) -> pd.Series:
    """Position décidée à la clôture t, appliquée au rendement t -> t+1, taille ajustée pour viser
    `target_vol` de volatilité annuelle (même règle pour toutes les stratégies comparées)."""
    r = close.pct_change()
    vol = r.rolling(vol_lookback).std() * np.sqrt(252)
    lev = (target_vol / vol).clip(upper=3.0)
    exposure = (pos.reindex(close.index).fillna(0) * lev).shift(1).fillna(0)
    turnover = exposure.diff().abs().fillna(0)
    return (exposure * r - turnover * cost).fillna(0)


def perf(rets: pd.Series) -> dict:
    from src.ftmo_metrics import prop_firm_summary
    rets = rets.dropna()
    eq = (1 + rets).cumprod()
    sd = rets.std()
    out = {"sharpe": float(rets.mean() / sd * np.sqrt(252)) if sd > 0 else 0.0,
           "total_return": float(eq.iloc[-1] - 1) if len(eq) else 0.0,
           "max_drawdown": float(-(eq / eq.cummax() - 1).min()) if len(eq) else 0.0,
           "n_days": int(len(rets))}
    out["prop_firm"] = prop_firm_summary(rets.to_numpy(), n_sims=1500)
    return out
