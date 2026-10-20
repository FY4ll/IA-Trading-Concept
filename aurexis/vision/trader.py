# Repris de Run A (src/trader/vision.py) le 08/10/2026 pour l'architecture v3 -- calculs IDENTIQUES (prouvé par
# tests/test_vision_equivalence.py). Toute modification doit garder ce test vert.
"""
vision.py -- tout ce que le TRADER (style "M15R") voit, ajouté comme variables d'observation de
son réseau (préfixe "tv_"), en plus des indicateurs techniques, du contexte M30/H1/H4/D1/W1/MN1
(fusion multi-timeframe) et des marchés liés/macro (src/cross_asset.py) :

  zoom M5      : élan et position de clôture des dernières bougies M5 (le détail de l'entrée) ;
  niveaux      : distance (en ATR H1) au plus haut/bas d'hier, de la semaine passée, du mois passé,
                 de la session asiatique, aux derniers sommets/creux H1, H4 et D1, au chiffre rond ;
  structure    : HH/HL/LH/LL en H1, H4 et D1, biais H4, régime H1 (range/tendance), position par
                 rapport aux EMA20/50 H1, H4 et D1 ;
  bougie M15   : mèches, corps, position de clôture ;
  temps        : heure (sin/cos), jour de la semaine, session asiatique connue ou non.

Même code en entraînement (CSV) et en live (bougies MT5), sans aucune information future : chaque
valeur n'utilise que des bougies déjà clôturées (voir src/trader/chart.py).
"""
from __future__ import annotations
import numpy as np
import pandas as pd

from aurexis.vision import graphique as chart

TV_COLUMNS = [
    "tv_m5_ret1", "tv_m5_ret3", "tv_m5_cpos",
    "tv_d_pdh", "tv_d_pdl", "tv_d_pwh", "tv_d_pwl", "tv_d_pmh", "tv_d_pml", "tv_d_ash", "tv_d_asl",
    "tv_d_h1sh", "tv_d_h1sl", "tv_d_h4sh", "tv_d_h4sl", "tv_d_d1sh", "tv_d_d1sl", "tv_d_round", "tv_d_dayopen",
    "tv_h1_struct", "tv_h4_struct", "tv_d1_struct", "tv_bias_h4", "tv_range_h1", "tv_h1_er20",
    "tv_ema20_h1", "tv_ema50_h1", "tv_ema20_h4", "tv_ema50_h4", "tv_ema20_d1", "tv_ema50_d1",
    "tv_lower_wick", "tv_upper_wick", "tv_body", "tv_cpos",
    "tv_hour_sin", "tv_hour_cos", "tv_dow", "tv_asia_known", "tv_atr_ratio",
    # v2 (05/10/2026) : calendrier économique (NFP/CPI/FOMC réels) et volume
    "tv_ev_to_next", "tv_ev_since_last", "tv_ev_window", "tv_ev_today",
    "tv_vol_rel", "tv_vol_rel4",
    # v3 (05/10/2026) : marchés liés EN INTRADAY (historique Dukascopy 2018->, live MT5) -- dollar contre
    # euro et yen, appétit pour le risque (S&P 500) : rendement sur 1, 4 et 16 bougies M15 (z-score).
    "tv_eur_r1", "tv_eur_r4", "tv_eur_r16", "tv_jpy_r1", "tv_jpy_r4", "tv_jpy_r16",
    "tv_spx_r1", "tv_spx_r4", "tv_spx_r16",
]
CLIP = 10.0
FX_DIR = "C:/Users/utilisateur/Documents/Test_IA/data/fx_intraday"
# clé -> (fichier historique Dukascopy, symbole MT5 du broker)
INTRADAY = {"eur": ("EURUSD", "EURUSD"), "jpy": ("USDJPY", "USDJPY"), "spx": ("USA500IDXUSD", "US500Cash")}


def load_intraday_history() -> dict[str, pd.Series]:
    """Clôtures M15 (heure serveur, horodatées à l'OUVERTURE de la bougie) des marchés liés."""
    import os
    out = {}
    for key, (hist, _) in INTRADAY.items():
        p = os.path.join(FX_DIR, f"{hist}_M15.csv")
        if os.path.exists(p):
            d = pd.read_csv(p, parse_dates=["time"])
            out[key] = pd.Series(d["close"].to_numpy(float), index=d["time"]).sort_index()
    return out


def _intraday_features(close_time: pd.Series, series: dict[str, pd.Series]) -> pd.DataFrame:
    out = pd.DataFrame(index=range(len(close_time)))
    ct = pd.DataFrame({"close_time": pd.to_datetime(close_time).to_numpy()})
    for key in INTRADAY:
        cols = [f"tv_{key}_r1", f"tv_{key}_r4", f"tv_{key}_r16"]
        s = series.get(key)
        if s is None or len(s) < 120:
            for c in cols:
                out[c] = 0.0
            continue
        s = s[~s.index.duplicated()].sort_index()
        r1 = s.pct_change()
        sd = r1.rolling(96, min_periods=30).std()
        f = pd.DataFrame({cols[0]: r1 / sd, cols[1]: s.pct_change(4) / (sd * 2), cols[2]: s.pct_change(16) / (sd * 4)})
        f.index = f.index + pd.Timedelta(minutes=15)          # connu à la clôture de la bougie du marché lié
        f = f.replace([np.inf, -np.inf], np.nan).dropna().sort_index()
        f.index = f.index.astype(ct["close_time"].dtype)      # v3 : même précision de date des deux côtés
        m = pd.merge_asof(ct, f, left_on="close_time", right_index=True, direction="backward",
                          tolerance=pd.Timedelta(hours=2))      # marché fermé depuis > 2 h -> neutre
        for c in cols:
            out[c] = m[c].to_numpy()
    return out
EVENTS_CSV = "C:/Users/utilisateur/Documents/Test_IA/data/macro_events_real.csv"
FF_CACHE = "data/cache/ff_calendar.json"
_FF_KEYWORDS = ("FOMC", "Federal Funds", "Non-Farm", "CPI")


def _utc_to_server(ts: pd.Series) -> pd.Series:
    """Heure serveur du broker = heure de New York + 7 h (minuit serveur = 17 h NY, la clôture forex)."""
    t = pd.to_datetime(ts, utc=True, format="ISO8601").dt.tz_convert("America/New_York").dt.tz_localize(None)
    return t + pd.Timedelta(hours=7)


def load_events(include_live_calendar: bool = True) -> np.ndarray:
    """Heures serveur (triées) des annonces majeures : CSV réel 2015-2026 (+ calendrier live FOMC/NFP/CPI USD)."""
    import os, json
    times = []
    try:
        ev = pd.read_csv(EVENTS_CSV, comment="#", header=None, names=["time", "kind"])
        times.append(_utc_to_server(ev["time"]))
    except Exception:
        pass
    if include_live_calendar and os.path.exists(FF_CACHE):
        try:
            with open(FF_CACHE, encoding="utf-8") as f:
                ff = json.load(f).get("events", [])
            sel = [e["time_utc"] for e in ff if e.get("country") == "USD" and e.get("impact") == "High"
                   and any(k.lower() in e.get("title", "").lower() for k in _FF_KEYWORDS)]
            if sel:
                times.append(_utc_to_server(pd.Series(sel)))
        except Exception:
            pass
    if not times:
        return np.array([], dtype="datetime64[ns]")
    t = pd.concat(times).dropna().sort_values().drop_duplicates()
    t = t[~(t.diff() < pd.Timedelta(minutes=30))]          # doublons CSV / calendrier live
    return t.to_numpy(dtype="datetime64[ns]")


def _event_features(close_time: pd.Series, events: np.ndarray) -> pd.DataFrame:
    now = close_time.to_numpy(dtype="datetime64[ns]")
    if len(events) == 0:
        z = np.zeros(len(now))
        return pd.DataFrame({"tv_ev_to_next": z + 1, "tv_ev_since_last": z + 1, "tv_ev_window": z, "tv_ev_today": z})
    idx = np.searchsorted(events, now, side="left")
    nxt = np.where(idx < len(events), events[np.minimum(idx, len(events) - 1)], np.datetime64("NaT"))
    prv = np.where(idx > 0, events[np.maximum(idx - 1, 0)], np.datetime64("NaT"))
    h_to = (nxt - now) / np.timedelta64(1, "h")
    h_since = (now - prv) / np.timedelta64(1, "h")
    h_to = np.where(np.isfinite(h_to), h_to, 72.0)
    h_since = np.where(np.isfinite(h_since), h_since, 72.0)
    return pd.DataFrame({
        "tv_ev_to_next": np.clip(h_to, 0, 72) / 72.0,
        "tv_ev_since_last": np.clip(h_since, 0, 72) / 72.0,
        "tv_ev_window": ((h_to <= 1.0) | (h_since <= 1.0)).astype(float),
        "tv_ev_today": (h_to <= 24.0).astype(float),
    })


def has_trader_columns(columns) -> bool:
    return any(str(c).startswith("tv_") for c in (list(columns) if columns is not None else []))


def _m5_features(m5: pd.DataFrame) -> pd.DataFrame:
    m5 = m5.copy()
    m5.index = pd.to_datetime(m5["time"]) if "time" in m5.columns else m5.index
    c = m5["close"]
    r = c.pct_change()
    sd = r.rolling(288, min_periods=50).std()
    rng = (m5["high"] - m5["low"]).replace(0, np.nan)
    out = pd.DataFrame({"tv_m5_ret1": r / sd, "tv_m5_ret3": c.pct_change(3) / (sd * np.sqrt(3)),
                        "tv_m5_cpos": (c - m5["low"]) / rng - 0.5}, index=m5.index)
    out.index = out.index + pd.Timedelta(minutes=5)          # disponible à la clôture de la bougie M5
    return out.sort_index()


def add_trader_vision(df: pd.DataFrame, m5: pd.DataFrame | None = None, events: np.ndarray | None = None,
                      include_live_calendar: bool = False,
                      intraday: dict[str, pd.Series] | None = None) -> pd.DataFrame:
    """`df` : bougies M15 (colonnes time/open/high/low/close[/volume], + toute autre colonne conservée).
    `events` : heures serveur des annonces majeures (défaut : load_events())."""
    df = df.copy()
    t = pd.to_datetime(df["time"])
    m15 = pd.DataFrame({"open": df["open"].to_numpy(), "high": df["high"].to_numpy(),
                        "low": df["low"].to_numpy(), "close": df["close"].to_numpy()}, index=t.to_numpy())
    m15.index.name = "time"
    m15 = m15[~m15.index.duplicated()]
    ch = chart.build_chart(m15)
    atr = ch["h1_atr"].replace(0, np.nan)
    c = ch["close"]

    def dist(col):
        return (c - ch[col]) / atr

    # contexte journalier (structure et EMA D1), disponible à la fin de chaque jour serveur
    d1 = chart.resample(m15, "1D")
    d1ctx = chart._context(d1, pd.Timedelta(days=1), "d1", 2).sort_index()
    ch = pd.merge_asof(ch.sort_values("close_time"), d1ctx[["d1_sh1", "d1_sl1", "d1_struct", "d1_ema20", "d1_ema50"]],
                       left_on="close_time", right_index=True, direction="backward").set_index(ch.index)
    # plus haut / bas du mois précédent
    month = m15.groupby(m15.index.to_period("M")).agg(high=("high", "max"), low=("low", "min")).shift(1)
    per = ch.index.to_period("M")
    ch["pmh"], ch["pml"] = month["high"].reindex(per).to_numpy(), month["low"].reindex(per).to_numpy()

    step = 25.0
    f = pd.DataFrame(index=ch.index)
    for col, src in (("tv_d_pdh", "pdh"), ("tv_d_pdl", "pdl"), ("tv_d_pwh", "pwh"), ("tv_d_pwl", "pwl"),
                     ("tv_d_pmh", "pmh"), ("tv_d_pml", "pml"), ("tv_d_ash", "ash"), ("tv_d_asl", "asl"),
                     ("tv_d_h1sh", "h1_sh1"), ("tv_d_h1sl", "h1_sl1"), ("tv_d_h4sh", "h4_sh1"),
                     ("tv_d_h4sl", "h4_sl1"), ("tv_d_d1sh", "d1_sh1"), ("tv_d_d1sl", "d1_sl1"),
                     ("tv_d_dayopen", "day_open"), ("tv_ema20_h1", "h1_ema20"), ("tv_ema50_h1", "h1_ema50"),
                     ("tv_ema20_h4", "h4_ema20"), ("tv_ema50_h4", "h4_ema50"), ("tv_ema20_d1", "d1_ema20"),
                     ("tv_ema50_d1", "d1_ema50")):
        f[col] = dist(src)
    f["tv_d_round"] = (c - np.round(c / step) * step) / atr
    f["tv_h1_struct"], f["tv_h4_struct"], f["tv_d1_struct"] = ch["h1_struct"], ch["h4_struct"], ch["d1_struct"]
    f["tv_bias_h4"] = ch["bias_h4"]
    f["tv_range_h1"] = ch["range_h1"].astype(float)
    f["tv_h1_er20"] = ch["h1_er20"]
    f["tv_lower_wick"], f["tv_upper_wick"] = ch["lower_wick"], ch["upper_wick"]
    f["tv_body"], f["tv_cpos"] = ch["body_frac"], ch["close_pos"]
    hour = ch.index.hour + ch.index.minute / 60.0
    f["tv_hour_sin"], f["tv_hour_cos"] = np.sin(2 * np.pi * hour / 24), np.cos(2 * np.pi * hour / 24)
    f["tv_dow"] = ch.index.dayofweek / 4.0
    f["tv_asia_known"] = ch["ash"].notna().astype(float)
    f["tv_atr_ratio"] = ch["atr_m15"] / atr

    ev = events if events is not None else load_events(include_live_calendar)
    evf = _event_features(ch["close_time"], ev)
    for col in evf.columns:
        f[col] = evf[col].to_numpy()
    intr = _intraday_features(ch["close_time"].reset_index(drop=True),
                              intraday if intraday is not None else load_intraday_history())
    for col in intr.columns:
        f[col] = intr[col].to_numpy()
    if "volume" in df.columns:
        vol = pd.Series(df["volume"].to_numpy(dtype=float), index=t.to_numpy())
        vol = vol[~vol.index.duplicated()].reindex(ch.index).clip(lower=0)
        base = vol.rolling(96, min_periods=20).mean()
        f["tv_vol_rel"] = np.log((vol + 1) / (base + 1))
        v4 = vol.rolling(4).sum()
        f["tv_vol_rel4"] = np.log((v4 + 1) / (v4.rolling(96, min_periods=20).mean() + 1))
    else:
        f["tv_vol_rel"] = 0.0
        f["tv_vol_rel4"] = 0.0

    if m5 is not None and len(m5):
        mf = _m5_features(m5)
        f = pd.merge_asof(f.assign(close_time=ch["close_time"]).sort_values("close_time"), mf,
                          left_on="close_time", right_index=True, direction="backward").set_index(f.index)
        f = f.drop(columns=["close_time"])
    for col in ("tv_m5_ret1", "tv_m5_ret3", "tv_m5_cpos"):
        if col not in f:
            f[col] = 0.0
    f = f[TV_COLUMNS].replace([np.inf, -np.inf], np.nan).fillna(0.0).clip(-CLIP, CLIP)
    vals = f.reindex(pd.DatetimeIndex(t)).to_numpy()
    for i, col in enumerate(TV_COLUMNS):
        df[col] = vals[:, i]
    df[TV_COLUMNS] = df[TV_COLUMNS].fillna(0.0)
    return df
