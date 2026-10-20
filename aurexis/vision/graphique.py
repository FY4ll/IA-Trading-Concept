# Repris de Run A (src/trader/chart.py) le 08/10/2026 pour l'architecture v3 -- calculs IDENTIQUES (prouvé par
# tests/test_vision_equivalence.py). Toute modification doit garder ce test vert.
"""
chart.py -- ce que le trader voit sur son graphique, bougie M15 par bougie M15.

Règle d'or : à la clôture d'une bougie M15, il ne voit QUE les bougies H1/H4/jour déjà
clôturées, les sommets/creux déjà confirmés (k bougies après le pivot) et les niveaux déjà
connus (plus haut/bas d'hier, de la semaine passée, de la session asiatique une fois finie).
Heures : heure serveur du broker (comme MT5 en live).
"""
from __future__ import annotations
import numpy as np
import pandas as pd

DEFAULTS = {
    "asia_start": 1, "asia_end": 9,          # session asiatique (heure serveur)
    "swing_k_h1": 3, "swing_k_m15": 2,
    "round_step": 25.0,                       # chiffres ronds de l'or ($)
}


def load_m15(cfg: dict, start: str | None = None) -> pd.DataFrame:
    from aurexis.vision.unites_de_temps import discover_files
    from aurexis.donnees.reserve import lire_csv_ohlcv as load_kaggle_ohlcv_csv
    d = load_kaggle_ohlcv_csv(discover_files(cfg["data"]["folder"])["M15"])
    d["time"] = pd.to_datetime(d["time"])
    d = d.drop_duplicates("time").set_index("time").sort_index()[["open", "high", "low", "close"]]
    return d[d.index >= pd.Timestamp(start)] if start else d


def resample(m15: pd.DataFrame, rule: str) -> pd.DataFrame:
    o = m15.resample(rule, label="left", closed="left").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
    return o


def ema(s: pd.Series, n: int) -> pd.Series:
    return s.ewm(span=n, adjust=False).mean()


def atr(df: pd.DataFrame, n: int = 14) -> pd.Series:
    c = df["close"]
    tr = pd.concat([df["high"] - df["low"], (df["high"] - c.shift()).abs(), (df["low"] - c.shift()).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / n, adjust=False).mean()


def swings(df: pd.DataFrame, k: int) -> pd.DataFrame:
    """Derniers sommets/creux CONFIRMÉS (connus k bougies après le pivot) + structure HH/HL/LH/LL."""
    h, l = df["high"], df["low"]
    is_sh = (h == h.rolling(2 * k + 1, center=True).max())
    is_sl = (l == l.rolling(2 * k + 1, center=True).min())
    sh = h.where(is_sh).shift(k)   # valeur disponible à la clôture de la bougie pivot+k
    sl = l.where(is_sl).shift(k)
    sh1 = sh.ffill()
    sl1 = sl.ffill()
    sh2 = sh.dropna().shift(1).reindex(df.index).ffill()
    sl2 = sl.dropna().shift(1).reindex(df.index).ffill()
    struct = np.where((sh1 > sh2) & (sl1 > sl2), 1, np.where((sh1 < sh2) & (sl1 < sl2), -1, 0))
    return pd.DataFrame({"sh1": sh1, "sh2": sh2, "sl1": sl1, "sl2": sl2, "struct": struct}, index=df.index)


def _context(tf: pd.DataFrame, period: pd.Timedelta, prefix: str, k: int) -> pd.DataFrame:
    c = tf["close"]
    out = pd.DataFrame(index=tf.index)
    out["close"] = c
    out["ema20"], out["ema50"], out["ema200"] = ema(c, 20), ema(c, 50), ema(c, 200)
    out["atr"] = atr(tf)
    out["er20"] = (c.diff(20).abs() / c.diff().abs().rolling(20).sum())
    out["hi20"], out["lo20"] = tf["high"].rolling(20).max(), tf["low"].rolling(20).min()
    out = out.join(swings(tf, k))
    out.index = out.index + period            # disponible à la CLÔTURE de la bougie
    out.columns = [f"{prefix}_{c}" for c in out.columns]
    return out


def build_chart(m15: pd.DataFrame, params: dict | None = None) -> pd.DataFrame:
    p = {**DEFAULTS, **(params or {})}
    ch = m15.copy()
    ch["close_time"] = ch.index + pd.Timedelta(minutes=15)
    ch["atr_m15"] = atr(m15)
    rng = (ch["high"] - ch["low"]).replace(0, np.nan)
    body = (ch["close"] - ch["open"]).abs()
    ch["lower_wick"] = (ch[["open", "close"]].min(axis=1) - ch["low"]) / rng
    ch["upper_wick"] = (ch["high"] - ch[["open", "close"]].max(axis=1)) / rng
    ch["close_pos"] = (ch["close"] - ch["low"]) / rng
    ch["body_frac"] = body / rng
    m15sw = swings(m15, p["swing_k_m15"])
    ch["m15_sl1"], ch["m15_sh1"] = m15sw["sl1"], m15sw["sh1"]

    h1, h4 = resample(m15, "1h"), resample(m15, "4h")
    for tf, per, pre, k in ((h1, pd.Timedelta(hours=1), "h1", p["swing_k_h1"]),
                            (h4, pd.Timedelta(hours=4), "h4", 2)):
        ctx = _context(tf, per, pre, k).sort_index()
        ch = pd.merge_asof(ch.sort_values("close_time"), ctx, left_on="close_time", right_index=True,
                           direction="backward").set_index(ch.index)

    # jour serveur : plus haut / plus bas d'hier et de la semaine passée, ouverture du jour
    day = ch.index.normalize()
    daily = m15.groupby(m15.index.normalize()).agg(high=("high", "max"), low=("low", "min"), open=("open", "first"))
    prev = daily.shift(1)
    ch["pdh"], ch["pdl"] = prev["high"].reindex(day).to_numpy(), prev["low"].reindex(day).to_numpy()
    ch["day_open"] = daily["open"].reindex(day).to_numpy()
    monday = lambda idx: idx.normalize() - pd.to_timedelta(idx.dayofweek, unit="D")
    week = m15.groupby(monday(m15.index)).agg(high=("high", "max"), low=("low", "min"))
    prev_week = week.shift(1)
    wk = monday(ch.index)
    ch["pwh"] = prev_week["high"].reindex(wk).to_numpy()
    ch["pwl"] = prev_week["low"].reindex(wk).to_numpy()

    # range asiatique du jour, connu seulement une fois la session finie
    hour = ch.index.hour
    asia = m15[(m15.index.hour >= p["asia_start"]) & (m15.index.hour < p["asia_end"])]
    ar = asia.groupby(asia.index.normalize()).agg(high=("high", "max"), low=("low", "min"))
    ash, asl = ar["high"].reindex(day).to_numpy(), ar["low"].reindex(day).to_numpy()
    known = hour >= p["asia_end"]
    ch["ash"] = np.where(known, ash, np.nan)
    ch["asl"] = np.where(known, asl, np.nan)

    # biais de fond H4 et régime H1
    up = (ch["h4_close"] > ch["h4_ema50"]) & (ch["h4_ema20"] > ch["h4_ema50"]) & (ch["h4_struct"] >= 0)
    dn = (ch["h4_close"] < ch["h4_ema50"]) & (ch["h4_ema20"] < ch["h4_ema50"]) & (ch["h4_struct"] <= 0)
    ch["bias_h4"] = np.where(up, 1, np.where(dn, -1, 0))
    ch["range_h1"] = (ch["h1_er20"] < 0.25) & (ch["bias_h4"] == 0)
    ch["hour"] = hour
    ch["dow"] = ch.index.dayofweek
    ch["round_step"] = p["round_step"]
    return ch


LEVEL_COLS = {"pdh": "plus haut d'hier", "pdl": "plus bas d'hier", "pwh": "plus haut de la semaine passée",
              "pwl": "plus bas de la semaine passée", "ash": "plus haut asiatique", "asl": "plus bas asiatique",
              "h1_sh1": "dernier sommet H1", "h1_sl1": "dernier creux H1", "h1_sh2": "sommet H1 précédent",
              "h1_sl2": "creux H1 précédent", "h4_sh1": "dernier sommet H4", "h4_sl1": "dernier creux H4"}


def levels_at(row) -> list[tuple[float, str]]:
    """Tous les niveaux clés connus à cette bougie (prix, nom), chiffres ronds proches compris."""
    out = [(float(row[c]), name) for c, name in LEVEL_COLS.items() if c in row and pd.notna(row[c])]
    step = float(row.get("round_step", 25.0))
    base = np.floor(row["close"] / step) * step
    out += [(base + i * step, f"chiffre rond {base + i * step:.0f}") for i in (-2, -1, 0, 1, 2)]
    return out
