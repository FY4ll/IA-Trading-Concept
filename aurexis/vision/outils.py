# Repris de Run A (src/trader/toolbox.py) le 08/10/2026 pour l'architecture v3 -- calculs IDENTIQUES (prouvé par
# tests/test_vision_equivalence.py). Toute modification doit garder ce test vert.
"""
toolbox.py -- LA BOÎTE À OUTILS COMPLÈTE DU TRADER (07/10/2026, AUREXIS).

Tous les outils qu'un trader met sur son graphique, calculés à la clôture de chaque bougie M15, sans jamais
regarder le futur (les unités de temps supérieures n'utilisent que des bougies déjà CLÔTURÉES, les sommets/creux
ne comptent qu'une fois confirmés). Distances exprimées en ATR (comparables d'un marché à l'autre), oscillateurs
recentrés, tout borné à ±CLIP.

  tendance      Ichimoku (tenkan/kijun, nuage, chikou), Supertrend, SAR parabolique, Aroon, Heikin-Ashi,
                régression linéaire (pente, R²), ADX/DI
  momentum      stochastique, Williams %R, CCI, ROC, MFI, TSI, RSI
  volatilité    Keltner, Donchian, squeeze (Bollinger dans Keltner), volatilité 20/100
  niveaux       pivots classiques jour (P, R1-R3, S1-S3) et semaine (P, R1, S1), Fibonacci de la dernière
                jambe H1, VWAP jour et semaine (+ bandes), profil de volume 5 jours (POC, zone de valeur)
  volume        OBV, oscillateur de volume
  price action  fair value gaps, order blocks, chasses de liquidité, cassure/changement de structure (BOS/CHoCH),
                bougies (avalement, marteau/étoile filante, doji, inside bar, étoile du matin/soir)
  multi-UT      RSI, stochastique, Supertrend, Ichimoku, Aroon sur H1, H4 et journalier

    df = add_toolbox(df)      # df : time, open, high, low, close, volume (bougies M15, une ligne par bougie)
"""
from __future__ import annotations
import numpy as np
import pandas as pd

CLIP = 10.0
_HTF = {"H1": "1h", "H4": "4h", "D1": "1D"}


def _ema(s, n):
    return s.ewm(span=n, adjust=False).mean()


def _atr(h, l, c, n=14):
    tr = pd.concat([h - l, (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / n, adjust=False).mean()


def _rsi(c, n=14):
    d = c.diff()
    up, dn = d.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean(), (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    return 100 - 100 / (1 + up / (dn + 1e-12))


def _stoch(h, l, c, n=14, d=3):
    lo, hi = l.rolling(n).min(), h.rolling(n).max()
    k = 100 * (c - lo) / (hi - lo + 1e-12)
    return k, k.rolling(d).mean()


def _supertrend(h, l, c, n=10, mult=3.0):
    a = _atr(h, l, c, n).to_numpy()
    hl2 = ((h + l) / 2).to_numpy()
    cc = c.to_numpy()
    up, dn = hl2 - mult * a, hl2 + mult * a
    fu, fd = up.copy(), dn.copy()
    trend = np.ones(len(cc))
    for i in range(1, len(cc)):
        fu[i] = max(up[i], fu[i - 1]) if cc[i - 1] > fu[i - 1] else up[i]
        fd[i] = min(dn[i], fd[i - 1]) if cc[i - 1] < fd[i - 1] else dn[i]
        trend[i] = 1 if cc[i] > fd[i - 1] else (-1 if cc[i] < fu[i - 1] else trend[i - 1])
    line = np.where(trend > 0, fu, fd)
    return pd.Series(trend, index=c.index), pd.Series(line, index=c.index)


def _psar(h, l, step=0.02, mx=0.2):
    hh, ll = h.to_numpy(), l.to_numpy()
    n = len(hh)
    sar = np.zeros(n); trend = np.ones(n)
    af, ep = step, hh[0]
    sar[0] = ll[0]
    for i in range(1, n):
        prev = sar[i - 1]
        if trend[i - 1] > 0:
            s = min(prev + af * (ep - prev), ll[i - 1], ll[i - 2] if i > 1 else ll[i - 1])
            if ll[i] < s:
                trend[i], s, ep, af = -1, ep, ll[i], step
            else:
                trend[i] = 1
                if hh[i] > ep:
                    ep, af = hh[i], min(af + step, mx)
        else:
            s = max(prev + af * (ep - prev), hh[i - 1], hh[i - 2] if i > 1 else hh[i - 1])
            if hh[i] > s:
                trend[i], s, ep, af = 1, ep, hh[i], step
            else:
                trend[i] = -1
                if ll[i] < ep:
                    ep, af = ll[i], min(af + step, mx)
        sar[i] = s
    return pd.Series(trend, index=h.index), pd.Series(sar, index=h.index)


def _ichimoku(h, l, c, a):
    tenkan = (h.rolling(9).max() + l.rolling(9).min()) / 2
    kijun = (h.rolling(26).max() + l.rolling(26).min()) / 2
    span_a = ((tenkan + kijun) / 2).shift(26)                       # nuage projeté : valeur calculée il y a 26 bougies
    span_b = ((h.rolling(52).max() + l.rolling(52).min()) / 2).shift(26)
    top, bot = np.maximum(span_a, span_b), np.minimum(span_a, span_b)
    pos = np.where(c > top, (c - top) / a, np.where(c < bot, (c - bot) / a, 0.0))
    return {"tk": (tenkan - kijun) / a, "kijun": (c - kijun) / a, "cloud": pd.Series(pos, index=c.index),
            "thick": (span_a - span_b) / a, "chikou": (c - c.shift(26)) / a}


def _aroon(h, l, n=25):
    up = h.rolling(n + 1).apply(lambda x: float(np.argmax(x)) / n, raw=True)
    dn = l.rolling(n + 1).apply(lambda x: float(np.argmin(x)) / n, raw=True)
    return up - dn


def _linreg(c, n=50):
    x = np.arange(n, dtype=float); xm = x.mean(); sxx = ((x - xm) ** 2).sum()

    def f(y):
        ym = y.mean()
        b = ((x - xm) * (y - ym)).sum() / sxx
        res = y - (ym + b * (x - xm))
        tot = ((y - ym) ** 2).sum()
        return b, 1 - (res ** 2).sum() / tot if tot > 0 else 0.0
    arr = c.to_numpy(float)
    slope = np.full(len(arr), np.nan); r2 = np.full(len(arr), np.nan)
    if len(arr) >= n:
        win = np.lib.stride_tricks.sliding_window_view(arr, n)
        ym = win.mean(axis=1, keepdims=True)
        b = ((x - xm) * (win - ym)).sum(axis=1) / sxx
        fit = ym + b[:, None] * (x - xm)
        tot = ((win - ym) ** 2).sum(axis=1)
        rr = 1 - ((win - fit) ** 2).sum(axis=1) / np.where(tot > 0, tot, np.nan)
        slope[n - 1:], r2[n - 1:] = b, rr
    return pd.Series(slope, index=c.index), pd.Series(r2, index=c.index)


def _candles(o, h, l, c):
    body, rng = (c - o), (h - l).replace(0, np.nan)
    upper, lower = h - np.maximum(o, c), np.minimum(o, c) - l
    po, pc = o.shift(), c.shift()
    eng_bull = (c > o) & (pc < po) & (c >= po) & (o <= pc)
    eng_bear = (c < o) & (pc > po) & (c <= po) & (o >= pc)
    hammer = (lower >= 2 * body.abs()) & (upper <= 0.3 * rng)
    star = (upper >= 2 * body.abs()) & (lower <= 0.3 * rng)
    doji = body.abs() <= 0.1 * rng
    inside = (h <= h.shift()) & (l >= l.shift())
    p2o, p2c = o.shift(2), c.shift(2)
    morning = (p2c < p2o) & (body.shift().abs() <= 0.3 * rng.shift()) & (c > o) & (c > (p2o + p2c) / 2)
    evening = (p2c > p2o) & (body.shift().abs() <= 0.3 * rng.shift()) & (c < o) & (c < (p2o + p2c) / 2)
    score = (eng_bull.astype(int) - eng_bear.astype(int) + hammer.astype(int) - star.astype(int)
             + morning.astype(int) - evening.astype(int))
    return score.astype(float), doji.astype(float), inside.astype(float)


def _smart_money(o, h, l, c, a, lookback=60):
    """Fair value gaps, order blocks, chasses de liquidité, BOS/CHoCH -- boucle causale."""
    o, h, l, c, a = (x.to_numpy(float) for x in (o, h, l, c, a))
    n = len(c)
    fvg_bull = np.zeros(n); fvg_bear = np.zeros(n); ob_bull = np.zeros(n); ob_bear = np.zeros(n)
    sweep = np.zeros(n); bos = np.zeros(n)
    bull_gaps, bear_gaps = [], []                 # (haut, bas) des écarts non comblés
    last_ob_bull = last_ob_bear = None
    swing_hi = swing_lo = np.nan
    last_bos, last_bos_i = 0, -10 ** 9
    for i in range(2, n):
        ai = a[i] if a[i] > 0 else np.nan
        if l[i] > h[i - 2]:
            bull_gaps.append((l[i], h[i - 2], i))
        if h[i] < l[i - 2]:
            bear_gaps.append((l[i - 2], h[i], i))
        bull_gaps = [g for g in bull_gaps if l[i] > g[1] and i - g[2] <= lookback]       # comblé si le prix y retourne
        bear_gaps = [g for g in bear_gaps if h[i] < g[0] and i - g[2] <= lookback]
        if bull_gaps:
            fvg_bull[i] = (c[i] - bull_gaps[-1][0]) / ai
        if bear_gaps:
            fvg_bear[i] = (c[i] - bear_gaps[-1][1]) / ai
        # order block : dernière bougie opposée avant un déplacement >= 2 ATR en 3 bougies
        if i >= 4 and np.isfinite(ai):
            if c[i] - o[i - 2] >= 2 * ai and c[i - 3] < o[i - 3]:
                last_ob_bull = (h[i - 3], l[i - 3])
            if o[i - 2] - c[i] >= 2 * ai and c[i - 3] > o[i - 3]:
                last_ob_bear = (h[i - 3], l[i - 3])
        if last_ob_bull is not None:
            ob_bull[i] = (c[i] - last_ob_bull[0]) / ai
        if last_ob_bear is not None:
            ob_bear[i] = (c[i] - last_ob_bear[1]) / ai
        # chasse de liquidité : mèche au-delà du plus haut/bas des 20 bougies précédentes, clôture revenue dedans
        if i >= 21:
            ph, pl = h[i - 20:i].max(), l[i - 20:i].min()
            if h[i] > ph and c[i] < ph:
                sweep[i] = -1
            elif l[i] < pl and c[i] > pl:
                sweep[i] = 1
        # structure : sommet/creux confirmés (2 bougies de chaque côté) ; cassure par une clôture
        if i >= 4:
            j = i - 2
            if h[j] == h[j - 2:j + 3].max():
                swing_hi = h[j]
            if l[j] == l[j - 2:j + 3].min():
                swing_lo = l[j]
        if np.isfinite(swing_hi) and c[i] > swing_hi and c[i - 1] <= swing_hi:
            last_bos, last_bos_i = (2 if last_bos < 0 else 1), i         # 2 = changement de caractère (CHoCH)
        elif np.isfinite(swing_lo) and c[i] < swing_lo and c[i - 1] >= swing_lo:
            last_bos, last_bos_i = (-2 if last_bos > 0 else -1), i
        bos[i] = last_bos * np.exp(-(i - last_bos_i) / 32.0)
    s = lambda x: pd.Series(x, dtype=float)
    return s(fvg_bull), s(fvg_bear), s(ob_bull), s(ob_bear), s(sweep), s(bos)


def _osc_block(df, prefix):
    """Outils principaux d'une unité de temps (utilisé pour M15, H1, H4, D1)."""
    o, h, l, c, v = (df[k] for k in ("open", "high", "low", "close", "volume"))
    a = _atr(h, l, c).replace(0, np.nan)
    k, d = _stoch(h, l, c)
    st_dir, st_line = _supertrend(h, l, c)
    ich = _ichimoku(h, l, c, a)
    out = {f"{prefix}_rsi": (_rsi(c) - 50) / 50, f"{prefix}_stoch_k": (k - 50) / 50, f"{prefix}_stoch_d": (d - 50) / 50,
           f"{prefix}_st_dir": st_dir, f"{prefix}_st_dist": (c - st_line) / a,
           f"{prefix}_ich_tk": ich["tk"], f"{prefix}_ich_cloud": ich["cloud"], f"{prefix}_ich_kijun": ich["kijun"],
           f"{prefix}_aroon": _aroon(h, l)}
    return pd.DataFrame(out, index=df.index)


def _merge_htf(base_time: pd.Series, htf: pd.DataFrame, cols) -> pd.DataFrame:
    """Valeurs de la dernière bougie supérieure CLÔTURÉE au moment de la clôture M15 (anti-fuite : décalage 1)."""
    h = htf[cols].shift(1)
    h["__t"] = htf.index
    left = pd.DataFrame({"__t": pd.to_datetime(base_time).to_numpy()})
    m = pd.merge_asof(left.sort_values("__t"), h.sort_values("__t"), on="__t", direction="backward")
    return m.drop(columns="__t").set_index(base_time.index)


def _resample(m15: pd.DataFrame, rule: str) -> pd.DataFrame:
    x = m15.set_index("time")[["open", "high", "low", "close", "volume"]]
    r = x.resample(rule, label="left", closed="left").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"})
    return r.dropna(subset=["open"])


def _vwap(df, a, period):
    tp = (df["high"] + df["low"] + df["close"]) / 3
    v = df["volume"].clip(lower=0) + 1e-9
    key = pd.to_datetime(df["time"]).dt.to_period(period)
    cv = v.groupby(key).cumsum()
    vw = (tp * v).groupby(key).cumsum() / cv
    var = ((tp - vw) ** 2 * v).groupby(key).cumsum() / cv
    sd = np.sqrt(var).replace(0, np.nan)
    # 1re bougie de la période : pas encore d'écart-type -> bande neutre (0)
    return (df["close"] - vw) / a, ((df["close"] - vw) / sd).clip(-4, 4).fillna(0.0)


def _pivots(df, day_atr):
    t = pd.to_datetime(df["time"])
    out = {}
    for per, name, keys in (("D", "pj", ("p", "r1", "s1", "r2", "s2", "r3", "s3")), ("W", "ps", ("p", "r1", "s1"))):
        g = df.assign(_k=t.dt.to_period(per)).groupby("_k").agg(h=("high", "max"), l=("low", "min"), c=("close", "last"))
        prev = g.shift(1)                                           # niveaux de la période PRÉCÉDENTE (déjà connus)
        p = (prev["h"] + prev["l"] + prev["c"]) / 3
        lv = {"p": p, "r1": 2 * p - prev["l"], "s1": 2 * p - prev["h"], "r2": p + (prev["h"] - prev["l"]),
              "s2": p - (prev["h"] - prev["l"]), "r3": prev["h"] + 2 * (p - prev["l"]), "s3": prev["l"] - 2 * (prev["h"] - p)}
        key = t.dt.to_period(per)
        for k in keys:
            out[f"tb_{name}_{k}"] = (df["close"].to_numpy() - lv[k].reindex(key).to_numpy()) / day_atr
    return pd.DataFrame(out, index=df.index)


def _fibonacci(df, h1_atr):
    """Position du prix dans la dernière jambe H1 (creux -> sommet confirmés) et distance au niveau Fibonacci le plus proche."""
    h1 = _resample(df, "1h")
    hh, ll = h1["high"].to_numpy(), h1["low"].to_numpy()
    k = 3
    sh_t, sl_t, sh, sl = [], [], [], []
    for j in range(k, len(h1) - k):
        if hh[j] == hh[j - k:j + k + 1].max():
            sh_t.append(h1.index[j + k] + pd.Timedelta(hours=1)); sh.append(hh[j])       # connu k bougies après
        if ll[j] == ll[j - k:j + k + 1].min():
            sl_t.append(h1.index[j + k] + pd.Timedelta(hours=1)); sl.append(ll[j])
    t = pd.to_datetime(df["time"]) + pd.Timedelta(minutes=15)                            # clôture de la bougie M15
    left = pd.DataFrame({"t": t.to_numpy()})
    a = pd.merge_asof(left, pd.DataFrame({"t": sh_t, "sh": sh, "sh_t": sh_t}).sort_values("t"), on="t")
    b = pd.merge_asof(left, pd.DataFrame({"t": sl_t, "sl": sl, "sl_t": sl_t}).sort_values("t"), on="t")
    rng = (a["sh"] - b["sl"]).to_numpy()
    c = df["close"].to_numpy()
    pos = np.where(rng > 0, (c - b["sl"].to_numpy()) / np.where(rng > 0, rng, np.nan), np.nan)
    up_leg = (b["sl_t"] < a["sh_t"]).to_numpy()
    retr = np.where(up_leg, 1 - pos, pos)                         # retracement depuis l'extrémité de la jambe
    levels = np.array([0.236, 0.382, 0.5, 0.618, 0.786])
    near = levels[np.nanargmin(np.abs(np.nan_to_num(retr, nan=9)[:, None] - levels[None, :]), axis=1)]
    dist = (retr - near) * rng / h1_atr
    return pd.DataFrame({"tb_fib_pos": np.clip(pos, -0.5, 1.5) - 0.5, "tb_fib_retr": np.clip(retr, -0.5, 1.5),
                         "tb_fib_near": dist, "tb_fib_leg": np.where(up_leg, 1.0, -1.0), "tb_fib_range": rng / h1_atr},
                        index=df.index)


def _volume_profile(df, day_atr, days=5, bins=48):
    t = pd.to_datetime(df["time"])
    day = t.dt.normalize()
    udays = day.drop_duplicates().to_numpy()
    poc = pd.Series(np.nan, index=udays); vah = poc.copy(); val = poc.copy()
    tp = ((df["high"] + df["low"] + df["close"]) / 3).to_numpy(); v = df["volume"].clip(lower=0).to_numpy() + 1e-9
    dvals = day.to_numpy()
    starts = np.searchsorted(dvals, udays)
    for i in range(days, len(udays)):
        a0, a1 = starts[i - days], starts[i]                     # profil des `days` jours PRÉCÉDENTS (clôturés)
        p, w = tp[a0:a1], v[a0:a1]
        if len(p) < 20:
            continue
        hist, edges = np.histogram(p, bins=bins, weights=w)
        mid = (edges[:-1] + edges[1:]) / 2
        j = int(np.argmax(hist)); poc.iloc[i] = mid[j]
        order = np.argsort(-hist); cum = np.cumsum(hist[order]) / hist.sum()
        va = mid[order[:int(np.searchsorted(cum, 0.7)) + 1]]
        vah.iloc[i], val.iloc[i] = va.max(), va.min()
    c = df["close"].to_numpy()
    P, H, L = (s.reindex(day).to_numpy() for s in (poc, vah, val))
    inside = np.where(c > H, (c - H) / day_atr, np.where(c < L, (c - L) / day_atr, 0.0))
    return pd.DataFrame({"tb_vp_poc": (c - P) / day_atr, "tb_vp_va": inside}, index=df.index)


def add_toolbox(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    if "volume" not in df.columns:
        df["volume"] = 1.0
    base = df[["time", "open", "high", "low", "close", "volume"]].copy()
    base["time"] = pd.to_datetime(base["time"])
    o, h, l, c, v = (base[k].astype(float) for k in ("open", "high", "low", "close", "volume"))
    a = _atr(h, l, c).replace(0, np.nan)
    d1 = _resample(base, "1D")
    day_atr = _merge_htf(base["time"], pd.DataFrame({"a": _atr(d1["high"], d1["low"], d1["close"])}), ["a"])["a"].to_numpy()
    h1 = _resample(base, "1h")
    h1_atr = _merge_htf(base["time"], pd.DataFrame({"a": _atr(h1["high"], h1["low"], h1["close"])}), ["a"])["a"].to_numpy()
    out = {}
    # --- M15 : tendance, momentum, volatilité, volume
    blk = _osc_block(base, "tb_m15")
    out.update({k: blk[k] for k in blk.columns})
    ich = _ichimoku(h, l, c, a)
    out["tb_m15_ich_thick"], out["tb_m15_ich_chikou"] = ich["thick"], ich["chikou"]
    psar_dir, psar = _psar(h, l)
    out["tb_psar_dir"], out["tb_psar_dist"] = psar_dir, (c - psar) / a
    plus = h.diff().clip(lower=0).where(h.diff() > -l.diff(), 0.0)
    minus = (-l.diff()).clip(lower=0).where(-l.diff() > h.diff(), 0.0)
    tr_s = (a * 14)
    di_p = 100 * plus.ewm(alpha=1 / 14, adjust=False).mean() * 14 / tr_s
    di_m = 100 * minus.ewm(alpha=1 / 14, adjust=False).mean() * 14 / tr_s
    adx = (100 * (di_p - di_m).abs() / (di_p + di_m + 1e-12)).ewm(alpha=1 / 14, adjust=False).mean()
    out["tb_di"], out["tb_adx"] = (di_p - di_m) / 50, adx / 50 - 0.5
    ha_c = (o + h + l + c) / 4
    hc = ha_c.to_numpy(dtype=float).copy()
    hoa = hc.copy()
    for i in range(1, len(hoa)):
        hoa[i] = (hoa[i - 1] + hc[i - 1]) / 2
    ha_dir = np.sign(hc - hoa)
    streak = np.zeros(len(ha_dir))
    for i in range(1, len(ha_dir)):
        streak[i] = streak[i - 1] + ha_dir[i] if np.sign(streak[i - 1]) == ha_dir[i] else ha_dir[i]
    out["tb_ha_streak"] = pd.Series(np.clip(streak, -10, 10) / 5, index=base.index)
    slope, r2 = _linreg(c)
    out["tb_lr_slope"], out["tb_lr_r2"] = slope * 50 / a, r2 - 0.5
    hi = h.rolling(14).max(); lo = l.rolling(14).min()
    out["tb_willr"] = (c - hi) / (hi - lo + 1e-12) + 0.5
    tp = (h + l + c) / 3
    md = tp.rolling(20).apply(lambda x: np.abs(x - x.mean()).mean(), raw=True)
    out["tb_cci"] = (tp - tp.rolling(20).mean()) / (0.015 * md + 1e-12) / 200
    out["tb_roc"] = (c - c.shift(10)) / a
    mf = tp * v
    pos_mf = mf.where(tp > tp.shift(), 0.0).rolling(14).sum(); neg_mf = mf.where(tp < tp.shift(), 0.0).rolling(14).sum()
    out["tb_mfi"] = (100 - 100 / (1 + pos_mf / (neg_mf + 1e-12))) / 50 - 1
    m = c.diff()
    out["tb_tsi"] = _ema(_ema(m, 25), 13) / (_ema(_ema(m.abs(), 25), 13) + 1e-12)
    ema20 = _ema(c, 20)
    out["tb_keltner"] = (c - ema20) / (2 * a)
    dh, dl = h.rolling(20).max(), l.rolling(20).min()
    out["tb_donchian"] = (c - dl) / (dh - dl + 1e-12) - 0.5
    bb_sd = c.rolling(20).std()
    out["tb_squeeze"] = np.log((2 * bb_sd + 1e-12) / (1.5 * a))
    r = c.pct_change()
    out["tb_vol_ratio"] = np.log((r.rolling(20).std() + 1e-12) / (r.rolling(100).std() + 1e-12))
    obv = (np.sign(c.diff()).fillna(0) * v).cumsum()
    out["tb_obv"] = (obv - obv.shift(20)) / (v.rolling(20).mean() * 20 + 1e-9)
    out["tb_vosc"] = (_ema(v, 5) - _ema(v, 20)) / (_ema(v, 20) + 1e-9)
    # --- bougies et smart money (M15)
    sc, doji, inside = _candles(o, h, l, c)
    out["tb_candle"], out["tb_doji"], out["tb_inside"] = sc, doji, inside
    fb, fbe, obb, obe, sw, bos = _smart_money(o, h, l, c, a)
    for k, s in (("tb_fvg_bull", fb), ("tb_fvg_bear", fbe), ("tb_ob_bull", obb), ("tb_ob_bear", obe),
                 ("tb_sweep", sw), ("tb_bos", bos)):
        s.index = base.index
        out[k] = s
    # --- niveaux : pivots, VWAP, Fibonacci, profil de volume
    out.update(_pivots(base, day_atr).to_dict("series"))
    vd, vdz = _vwap(base, a, "D")
    vw, vwz = _vwap(base, a, "W")
    out["tb_vwap_d"], out["tb_vwap_d_band"], out["tb_vwap_w"], out["tb_vwap_w_band"] = vd, vdz / 2, vw, vwz / 2
    out.update(_fibonacci(base, h1_atr).to_dict("series"))
    out.update(_volume_profile(base, day_atr).to_dict("series"))
    # --- multi-unités de temps (bougies supérieures clôturées)
    for tf, rule in _HTF.items():
        hf = _resample(base, rule)
        blk = _osc_block(hf.reset_index(), f"tb_{tf.lower()}")
        blk.index = hf.index
        merged = _merge_htf(base["time"], blk, list(blk.columns))
        out.update({k: merged[k] for k in merged.columns})
    tb = pd.DataFrame(out, index=df.index).replace([np.inf, -np.inf], np.nan)
    # valeur manquante ponctuelle (bougie plate -> ATR nul, pas encore de sommet confirmé...) : dernière valeur
    # connue (passé uniquement), sinon neutre -- jamais un NaN dans l'observation de l'IA
    tb = tb.ffill().fillna(0.0).clip(-CLIP, CLIP).astype("float64")
    for col in tb.columns:
        df[col] = tb[col].to_numpy()
    return df


def toolbox_columns() -> list[str]:
    """Liste ordonnée des colonnes produites (calculée sur un petit jeu synthétique, toujours la même)."""
    n = 6000
    t = pd.date_range("2024-01-01", periods=n, freq="15min")
    rng = np.random.default_rng(0)
    c = 100 + np.cumsum(rng.normal(0, 0.1, n))
    df = pd.DataFrame({"time": t, "open": c, "high": c + 0.1, "low": c - 0.1, "close": c, "volume": 1.0})
    return [k for k in add_toolbox(df).columns if k.startswith("tb_")]


def has_toolbox_columns(columns) -> bool:
    return any(str(c).startswith("tb_") for c in (columns or []))
