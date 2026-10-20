"""
aurexis_data.py
===============
AUREXIS (06/10/2026) : le trader unique qui APPREND SUR PLUSIEURS MARCHÉS. Construit, pour chaque marché
additionnel (euro/dollar, dollar/yen, livre/dollar, S&P 500...), EXACTEMENT la même vision qu'AUREX sur l'or :
toutes les timeframes (M15 -> MN1, recomposées depuis les bougies M15 du marché), indicateurs techniques,
contexte macro (src/cross_asset.py) et vision du trader (src/trader/vision.py). Les variables de la vision sont
exprimées en ATR / en positions relatives : comparables d'un marché à l'autre.

Chaque marché est normalisé avec SES PROPRES statistiques, coupé AVANT le début de la validation de l'or (aucune
information de la période de validation ni de la lockbox ne fuit dans l'entraînement), puis concaténé à
l'entraînement de l'or avec une colonne `segment_id` : TradingEnv ne laisse jamais un trade traverser deux
marchés et tire chaque épisode dans un marché au hasard (voir TradingEnv.reset).

La validation, la porte lockbox et la décision live restent sur l'OR : AUREXIS est jugé sur le marché qu'il trade.
"""
from __future__ import annotations
import logging
import os

import numpy as np
import pandas as pd

log = logging.getLogger("aurexis_data")

DATA_ROOT = "C:/Users/utilisateur/Documents/Test_IA/data"
DEFAULT_MARKETS = {
    "EURUSD": f"{DATA_ROOT}/fx_intraday/EURUSD_M15.csv",
    "USDJPY": f"{DATA_ROOT}/fx_intraday/USDJPY_M15.csv",
    "US500": f"{DATA_ROOT}/fx_intraday/USA500IDXUSD_M15.csv",
    "GBPUSD": f"{DATA_ROOT}/kaggle_gbpusd/GBPUSD_m15_data.csv",
}
# FRAIS PAR MARCHÉ (09/10/2026) : coût d'un trade COMPLET (ouverture + fermeture : écart + commission), en part du
# montant traité -- même convention que `transaction_cost` de TradingEnv (payé une fois, à la clôture). Avant, tous
# les marchés payaient le coût calibré sur l'or (0,02 %) : sur l'euro, avec des stops serrés, les frais simulés
# mangeaient une grosse part du risque de chaque trade (mesuré sur 12 mois : -12,6 % avec, -6,9 % avec des frais
# réalistes, -4,4 % sans frais). Estimations prudentes (~1,5x les conditions FTMO publiques), à remplacer par les
# frais MESURÉS sur le compte FTMO dès qu'il est disponible (`multi_market.cost_round_trip` en config les surcharge).
COST_ROUND_TRIP = {
    "XAUUSD": 0.00012,
    **{s: 0.00010 for s in ("EURUSD", "USDJPY", "GBPUSD", "USDCHF", "AUDUSD", "USDCAD", "NZDUSD")},
    **{s: 0.00020 for s in ("AUDCAD", "AUDCHF", "AUDJPY", "AUDNZD", "CADCHF", "CADJPY", "CHFJPY", "EURAUD", "EURCAD",
                            "EURCHF", "EURGBP", "EURJPY", "EURNZD", "GBPAUD", "GBPCAD", "GBPCHF", "GBPJPY", "GBPNZD",
                            "NZDCAD", "NZDCHF", "NZDJPY")},
    **{s: 0.00012 for s in ("US500", "US100", "US30", "GER40")},
    **{s: 0.00016 for s in ("UK100", "FRA40")},
    **{s: 0.00024 for s in ("EU50", "JP225", "AUS200")},
    "XAGUSD": 0.00060, "USOIL": 0.00060, "UKOIL": 0.00060, "NATGAS": 0.00180,
    "BTCUSD": 0.00080, "ETHUSD": 0.00100, "LTCUSD": 0.00160, "XRPUSD": 0.00160,
}


def cost_round_trip(name: str, cfg: dict | None = None) -> float | None:
    """Coût d'un trade complet sur le marché `name` (« X miroir » = même coût que X), None si inconnu."""
    base = name.replace(" miroir", "")
    over = ((cfg or {}).get("multi_market") or {}).get("cost_round_trip") or {}
    v = over.get(base, COST_ROUND_TRIP.get(base))
    return float(v) if v is not None else None

def reference_cost(cfg: dict) -> float:
    """Frais de référence de l'environnement d'AUREXIS (`transaction_cost`, surcharge du style comprise)."""
    env = cfg.get("environment") or {}
    style = ((cfg.get("multi_market") or {}).get("styles") or ["AUREXIS"])[0]
    return float(((env.get("style_overrides") or {}).get(style) or {}).get("transaction_cost",
                                                                              env.get("transaction_cost", 0.0002)))


def add_cost_column(df: pd.DataFrame, name: str, reference_cost: float, cfg: dict | None = None) -> pd.DataFrame:
    """Colonne `cost_multiplier` (lue par TradingEnv, jamais vue par l'IA) = frais du marché / frais de référence de
    l'environnement (`transaction_cost`). Marché inconnu : multiplicateur 1 (frais de référence)."""
    c = cost_round_trip(name, cfg)
    df["cost_multiplier"] = np.float32(c / reference_cost if (c and reference_cost) else 1.0)
    return df


# Règles de recomposition M15 -> timeframes de contexte (étiquette = ouverture de la bougie, comme MT5).
_RULES = {"M30": "30min", "H1": "1h", "H4": "4h", "D1": "1D", "W1": "W-MON", "MN1": "MS"}

_cache: dict = {}
_train_info: dict = {}     # même clé que _cache : statistiques de normalisation + niveau d'inversion de l'entraînement
_val_cache: dict = {}


def _mirror_neutral(cols) -> list:
    return [c for c in cols if c.startswith("x_") or c.startswith(("tv_eur_", "tv_jpy_", "tv_spx_"))]


def _market_jobs(cfg: dict, max_bars_per_market: int) -> list:
    """(symbole, fichier, miroir, nb de bougies d'entraînement) pour chaque marché additionnel."""
    mm = (cfg.get("multi_market") or {})
    markets = mm.get("markets") or DEFAULT_MARKETS
    jobs = [(symbol, path, False, max_bars_per_market) for symbol, path in markets.items()]
    if mm.get("mirror"):
        # MARCHÉS MIROIRS (07/10/2026) : chaque marché (or compris) rejoué À L'ENVERS -- toute hausse devient une
        # baisse. AUREXIS voit autant de baisses que de hausses : il ne peut plus réussir en achetant toujours,
        # il doit apprendre à VENDRE.
        from src.multi_timeframe import discover_files
        gold_path = discover_files((cfg.get("data") or {}).get("folder", "")).get("M15")
        mirror_bars = int(mm.get("mirror_max_bars", 80000))
        # 09/10/2026 : `mirror_markets` = liste des marchés qui ont un miroir (défaut : tous). Avec ~35 marchés réels,
        # un miroir par marché doublerait la mémoire ; les devises et indices montent ET baissent déjà d'eux-mêmes.
        only = mm.get("mirror_markets")
        if gold_path and (only is None or "XAUUSD" in only):
            jobs.append(("XAUUSD", gold_path, True, mirror_bars))
        jobs += [(symbol, path, True, mirror_bars) for symbol, path in markets.items() if only is None or symbol in only]
    return jobs


STATS_DIR = os.path.join(DATA_ROOT, "aurexis_stats")


def save_market_stats(name: str, info: dict, cut) -> None:
    """09/10/2026 : statistiques de normalisation de la tranche d'entraînement d'un marché, sur le disque -- l'examen du
    jour (scripts/examen_du_jour.py) normalise les jours nouveaux EXACTEMENT comme l'entraînement. Best effort."""
    try:
        os.makedirs(STATS_DIR, exist_ok=True)
        payload = {"name": name, "k": info.get("k"), "cut": str(pd.Timestamp(cut)),
                   "stats": {c: [float(m), float(s)] for c, (m, s) in info["stats"].items()}}
        tmp = os.path.join(STATS_DIR, f"{name.replace(' ', '_')}.json.tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            import json
            json.dump(payload, f)
        os.replace(tmp, tmp[:-4])
    except Exception as e:
        log.warning(f"[AUREXIS] statistiques de {name} non enregistrées ({type(e).__name__}: {e})")


def load_market_stats(name: str) -> dict | None:
    import json
    try:
        with open(os.path.join(STATS_DIR, f"{name.replace(' ', '_')}.json"), encoding="utf-8") as f:
            d = json.load(f)
        d["stats"] = {c: tuple(v) for c, v in d["stats"].items()}
        return d
    except (OSError, ValueError, KeyError):
        return None


def load_m15(path: str) -> pd.DataFrame:
    head = pd.read_csv(path, nrows=2)
    if "time" in head.columns:                       # format Dukascopy (scripts/fetch_dukascopy.py)
        df = pd.read_csv(path)
    else:
        from src.data_loader import load_kaggle_ohlcv_csv
        df = load_kaggle_ohlcv_csv(path)
    df["time"] = pd.to_datetime(df["time"])
    df = df.sort_values("time").drop_duplicates("time").reset_index(drop=True)
    if "volume" not in df.columns:
        df["volume"] = 0.0
    return df[["time", "open", "high", "low", "close", "volume"]]


def mirror_m15(m15: pd.DataFrame, k: float | None = None) -> pd.DataFrame:
    """Marché à l'envers : prix p -> p0²/p (toute hausse devient une baisse de même ampleur relative). Le plus
    haut devient le plus bas et inversement ; volume et horaires inchangés. `k` (= p0²) imposé pour qu'une
    autre tranche du même marché soit inversée au même niveau de prix que l'entraînement."""
    k = float(m15["close"].iloc[0]) ** 2 if k is None else float(k)
    out = m15.copy()
    out["open"], out["close"] = k / m15["open"], k / m15["close"]
    out["high"], out["low"] = k / m15["low"], k / m15["high"]
    return out


def resample_ohlcv(m15: pd.DataFrame, tf: str) -> pd.DataFrame:
    rule = _RULES[tf]
    kw = {"label": "left", "closed": "left"}
    s = m15.set_index("time")
    out = pd.DataFrame({"open": s["open"].resample(rule, **kw).first(),
                        "high": s["high"].resample(rule, **kw).max(),
                        "low": s["low"].resample(rule, **kw).min(),
                        "close": s["close"].resample(rule, **kw).last(),
                        "volume": s["volume"].resample(rule, **kw).sum()}).dropna(subset=["open"])
    return out.reset_index()


def build_market_frame(symbol: str, m15: pd.DataFrame, context_tfs: list[str], cross_folder: str | None,
                       fred=None, toolbox: bool = False, daily: pd.Series | None = None) -> pd.DataFrame:
    """Même pipeline de features qu'AUREX (autonomous_agent._rebuild), pour un marché quelconque."""
    from src.multi_timeframe import fuse_mtf_frames
    from src.features import add_technical_features
    from src.trading_env import TradingEnv
    dfs = {"M15": m15}
    for tf in context_tfs:
        if tf in _RULES:
            dfs[tf] = resample_ohlcv(m15, tf)
    df, _ = fuse_mtf_frames(dfs, "M15", context_tfs)
    df = add_technical_features(df, fundamental_feed=None)
    df["fundamental_score"] = 0.0          # score de news calibré sur l'or : neutre ailleurs
    if cross_folder:
        from src import cross_asset
        df = cross_asset.add_cross_asset_features(df, fred=fred,
                                                  daily_provider=cross_asset.csv_daily_provider(cross_folder))
    from src.trader.vision import add_trader_vision
    df = add_trader_vision(df, m5=None)    # pas de M5 hors or : zoom M5 neutre
    if toolbox:
        from src.trader.toolbox import add_toolbox
        df = add_toolbox(df)
    if "atr_14" in df.columns:
        df[TradingEnv.ATR_RAW_COLUMN] = df["atr_14"]
    # 09/10 : vision des tendances de fond (src/trend_vision.py) -- `daily` = clôtures de l'historique COMPLET
    from src.trend_vision import add_trend_vision
    df = add_trend_vision(df, daily)
    df["symbol"] = symbol
    return df


def full_daily(path: str, mirror: bool = False, k: float | None = None) -> pd.Series:
    """Clôtures quotidiennes de TOUT l'historique d'un marché (inversées au niveau `k` pour un miroir)."""
    from src.trend_vision import daily_closes
    m15 = load_m15(path)
    return daily_closes(mirror_m15(m15, k) if mirror else m15)


def other_markets_train(cfg: dict, cols: list[str], context_tfs: list[str], cut_time,
                        max_bars_per_market: int = 120000, fred=None) -> list[pd.DataFrame]:
    """Marchés additionnels prêts pour l'entraînement : features, coupe AVANT `cut_time` (début de la validation
    de l'or, embargo inclus), normalisation propre à chaque marché, float32. Mis en cache par (marché, coupe)."""
    from src.features import normalize_features
    mm = (cfg.get("multi_market") or {})
    embargo = pd.Timedelta(hours=float(mm.get("embargo_hours", 48)))
    cut = pd.Timestamp(cut_time) - embargo
    data_cfg = cfg.get("data", {})
    cross_folder = data_cfg.get("cross_asset_folder") or os.path.join(
        os.path.dirname(os.path.abspath(data_cfg.get("folder", "."))), "cross_asset")
    out = []
    jobs = _market_jobs(cfg, max_bars_per_market)
    for symbol, path, mirror, n_bars in jobs:
        if not os.path.exists(path):
            log.warning(f"[AUREXIS] marché {symbol} : fichier introuvable ({path}) -- ignoré.")
            continue
        name = f"{symbol} miroir" if mirror else symbol
        key = (symbol, path, os.path.getmtime(path), cut.floor("D"), tuple(cols), n_bars, mirror)
        if key not in _cache:
            try:
                full = load_m15(path)
                m15 = full[full["time"] < cut].tail(n_bars + 3000).reset_index(drop=True)
                k = float(m15["close"].iloc[0]) ** 2 if len(m15) else None
                from src.trend_vision import daily_closes
                daily = daily_closes(mirror_m15(full, k) if mirror else full)      # tendances : tout l'historique
                del full
                if mirror:
                    m15 = mirror_m15(m15, k)
                symbol = name
                if len(m15) < 5000:
                    log.warning(f"[AUREXIS] marché {symbol} : seulement {len(m15)} bougies avant {cut.date()} -- ignoré.")
                    _cache[key] = None
                    continue
                df = build_market_frame(symbol, m15, context_tfs, cross_folder, fred=fred,
                                        toolbox=any(str(c).startswith("tb_") for c in cols), daily=daily)
                df = df.iloc[3000:].reset_index(drop=True)          # chauffe des indicateurs longs (EMA200 H4...)
                missing = [c for c in cols if c not in df.columns]
                if missing:
                    raise ValueError(f"variables manquantes : {missing[:5]}")
                df[cols] = df[cols].replace([np.inf, -np.inf], np.nan).ffill().fillna(0.0)
                dfn, stats = normalize_features(df, columns=cols)
                if mirror:
                    # macro et marchés liés : neutres sur un marché à l'envers (sinon relations apprises à l'envers)
                    dfn[_mirror_neutral(cols)] = 0.0
                dfn[cols] = dfn[cols].astype("float32")
                add_cost_column(dfn, symbol, reference_cost(cfg), cfg)        # frais propres à ce marché
                # 08/10 : on ne garde en mémoire que ce que l'entraînement lit (variables + prix + ATR brut) --
                # les ~200 colonnes intermédiaires (non normalisées, float64) doublaient la mémoire du programme
                # principal, qui garde ces marchés d'un cycle à l'autre.
                from src.trading_env import TradingEnv
                base = ["time", "open", "high", "low", "close", "volume", TradingEnv.ATR_RAW_COLUMN, "cost_multiplier"]
                dfn = dfn[[c for c in base if c in dfn.columns] + [c for c in cols if c not in base]].copy()
                _cache[key] = dfn
                _train_info[key] = {"stats": stats, "k": k, "name": symbol}
                save_market_stats(symbol, _train_info[key], cut)
                log.info(f"[AUREXIS] marché {symbol} prêt : {len(dfn)} bougies M15 "
                         f"({dfn['time'].iloc[0].date()} -> {dfn['time'].iloc[-1].date()}).")
            except Exception as e:
                log.warning(f"[AUREXIS] marché {symbol} : construction impossible ({type(e).__name__}: {e}) -- ignoré.")
                _cache[key] = None
        if _cache.get(key) is not None:
            out.append(_cache[key])
    return out


def mix_days(m15: pd.DataFrame, rng) -> pd.DataFrame | None:
    """MÉLANGEUR LOGIQUE (08/10/2026) : un marché qui n'a jamais existé mais qui reste crédible. On garde le
    calendrier de la période (mêmes jours, mêmes heures), et chaque jour reçoit le contenu d'un VRAI jour de la
    même période tiré au hasard. Chaque bougie garde son vrai mouvement relatif à la clôture précédente (écart du
    matin compris) : aucune bougie ne bouge plus que la plus forte bougie réelle, plus haut >= ouverture/clôture
    >= plus bas toujours vrai. Le prix est recousu en continu (pas de saut entre deux jours recollés)."""
    d = m15.reset_index(drop=True)
    if len(d) < 200:
        return None
    prev = d["close"].shift(1)
    rel = pd.DataFrame({k: np.log(d[k] / prev) for k in ("open", "high", "low", "close")})
    rel["volume"], rel["time"] = d["volume"].to_numpy(), pd.to_datetime(d["time"]).to_numpy()
    rel = rel.iloc[1:].reset_index(drop=True)
    day = pd.to_datetime(rel["time"]).dt.normalize()
    groups = [g for _, g in rel.groupby(day)]
    if len(groups) < 5:
        return None
    parts = []
    for target in groups:
        src = groups[int(rng.integers(len(groups)))].copy()
        st = pd.to_datetime(src["time"])
        src["time"] = (pd.Timestamp(target["time"].iloc[0]).normalize() + (st - st.dt.normalize())).to_numpy()
        parts.append(src)
    mixed = pd.concat(parts, ignore_index=True)
    c0 = float(np.log(d["close"].iloc[0]))
    lc = c0 + np.cumsum(mixed["close"].to_numpy())
    pc = np.concatenate([[c0], lc[:-1]])
    return pd.DataFrame({"time": pd.to_datetime(mixed["time"]), "open": np.exp(pc + mixed["open"].to_numpy()),
                         "high": np.exp(pc + mixed["high"].to_numpy()), "low": np.exp(pc + mixed["low"].to_numpy()),
                         "close": np.exp(lc), "volume": mixed["volume"].to_numpy()})


def quick_exam_frames(cfg: dict, cols: list[str], context_tfs: list[str], gold_stats: dict,
                      cut_time, val_start, val_end, seed: int, n_days: int = 42,
                      max_bars_per_market: int = 120000, fred=None) -> list[tuple[str, pd.DataFrame]]:
    """PETIT EXAMEN (08/10/2026) : à chaque cycle, UN marché tiré au hasard parmi l'or et les marchés
    d'entraînement (miroirs compris) et UNE période de `n_days` jours dans la validation (jamais vue à
    l'entraînement) -> [(nom, vraie période), (nom, même période passée au mélangeur)]. Normalisé avec les
    statistiques d'entraînement du marché. Différent à chaque cycle : impossible à apprendre par cœur."""
    from src.features import normalize_features
    from src.multi_timeframe import discover_files
    rng = np.random.default_rng(seed)
    mm = (cfg.get("multi_market") or {})
    cut = pd.Timestamp(cut_time) - pd.Timedelta(hours=float(mm.get("embargo_hours", 48)))
    data_cfg = cfg.get("data", {})
    cross_folder = data_cfg.get("cross_asset_folder") or os.path.join(
        os.path.dirname(os.path.abspath(data_cfg.get("folder", "."))), "cross_asset")
    gold_path = discover_files(data_cfg.get("folder", "")).get("M15")
    choices = ([("XAUUSD", gold_path, False, None)] if gold_path else []) + list(_market_jobs(cfg, max_bars_per_market))
    for _ in range(10):                                   # un tirage valide (données présentes sur la période)
        sym, path, mirror, n_bars = choices[int(rng.integers(len(choices)))]
        if not path or not os.path.exists(path):
            continue
        if sym == "XAUUSD" and not mirror:
            stats, k, name = gold_stats, None, "XAUUSD"
        else:
            key = (sym, path, os.path.getmtime(path), cut.floor("D"), tuple(cols), n_bars, mirror)
            info = _train_info.get(key)
            if info is None:
                continue
            stats, k, name = info["stats"], info["k"], info["name"]
        m15 = load_m15(path)
        win = m15[(m15["time"] >= pd.Timestamp(val_start)) & (m15["time"] < pd.Timestamp(val_end))]
        days = pd.to_datetime(win["time"]).dt.normalize().unique()
        if len(days) < n_days + 5:
            continue
        d0 = pd.Timestamp(days[int(rng.integers(len(days) - n_days))])
        d1 = d0 + pd.Timedelta(days=int(n_days * 7 / 5))
        i0 = int(np.searchsorted(m15["time"].to_numpy(), np.datetime64(d0)))
        hist = m15.iloc[max(0, i0 - 3000):i0].reset_index(drop=True)
        part = m15[(m15["time"] >= d0) & (m15["time"] < d1)].reset_index(drop=True)
        if len(part) < 1000:
            continue
        mixed = mix_days(part, rng)                       # repart du premier vrai prix de la période
        if mixed is None:
            continue
        out = []
        before = m15[m15["time"] < d0]
        for label, body in ((f"tirage {name} {d0:%d/%m/%Y} ({n_days} j)", part), (f"mélangé {name}", mixed)):
            src = pd.concat([hist, body], ignore_index=True)
            longue = pd.concat([before, body], ignore_index=True)         # tendances : tout l'historique d'avant
            if mirror:
                src, longue = mirror_m15(src, k), mirror_m15(longue, k)
            from src.trend_vision import daily_closes
            df = build_market_frame(name, src, context_tfs, cross_folder, fred=fred,
                                    toolbox=any(str(c).startswith("tb_") for c in cols), daily=daily_closes(longue))
            df = df[df["time"] >= d0].reset_index(drop=True)
            df[cols] = df[cols].replace([np.inf, -np.inf], np.nan).ffill().fillna(0.0)
            const = [c for c in cols if df[c].std() < 1e-12]          # variables absentes ici -> neutres
            dfn, _ = normalize_features(df, stats=stats, columns=cols)
            neutral = set(const) | (set(_mirror_neutral(cols)) if (mirror or label.startswith("mélangé")) else set())
            if neutral:
                dfn[list(neutral)] = 0.0
            dfn[cols] = dfn[cols].astype("float32")
            add_cost_column(dfn, name, reference_cost(cfg), cfg)
            out.append((label, dfn))
        return out
    return []


def rotation_window(cfg: dict, seed: int) -> tuple | None:
    """EXAMEN TOURNANT (09/10/2026) : constat -- le champion qui faisait +0,8 %/mois (36 % de réussite au challenge)
    sur la période d'examen FIXE (début 2023) aurait raté 99 % des challenges sur les 12 derniers mois : à force de
    rejouer la même période, la sélection fabriquait une IA adaptée à CETTE période. Désormais chaque cycle tire une
    période différente dans [from, to] ; les 12 derniers mois (après `to`) restent cachés pour le vrai verdict
    (scripts/examen_du_jour.py, prédiction). Retourne (début, fin) ou None si la rotation est désactivée."""
    rot = ((cfg.get("multi_market") or {}).get("selection") or {}).get("rotation") or {}
    if not rot.get("enabled"):
        return None
    lo, hi = pd.Timestamp(rot.get("from", "2023-01-01")), pd.Timestamp(rot.get("to", "2025-09-30"))
    span = pd.Timedelta(days=int(rot.get("days", 105)))
    rng = np.random.default_rng(seed)
    n_days = max(0, int((hi - span - lo).days))
    start = (lo + pd.Timedelta(days=int(rng.integers(0, n_days + 1)))).normalize()
    return start, start + span


def rotation_windows(cfg: dict, seed: int) -> list:
    """DEUX PÉRIODES PAR CYCLE (09/10/2026, accord de l'utilisateur) : le champion du cycle 399 avait été promu sur UNE
    période de début 2024 (+1,24 %/mois) puis perdait sur les 12 mois cachés. Avec `rotation.windows: 2`, la plage
    [from, to] est coupée en deux moitiés et une période est tirée dans CHACUNE (une ancienne, une récente) ; la note
    retenue est celle de la MOINS BONNE période (continuous_trainer). Une seule période si `windows` vaut 1."""
    rot = ((cfg.get("multi_market") or {}).get("selection") or {}).get("rotation") or {}
    if not rot.get("enabled"):
        return []
    n = max(1, int(rot.get("windows", 1)))
    lo, hi = pd.Timestamp(rot.get("from", "2023-01-01")), pd.Timestamp(rot.get("to", "2025-09-30"))
    edges = [lo + (hi - lo) * k / n for k in range(n + 1)]
    out = []
    for k in range(n):
        sub = {**cfg, "multi_market": {**cfg["multi_market"], "selection": {**cfg["multi_market"]["selection"],
               "rotation": {**rot, "from": str(edges[k].date()), "to": str(edges[k + 1].date())}}}}
        out.append(rotation_window(sub, seed + 7919 * k))
    return out


def gold_window(cfg: dict, cols: list[str], context_tfs: list[str], gold_stats: dict, val_start, val_end,
                max_val_bars: int = 7000, fred=None) -> list[tuple[str, pd.DataFrame]]:
    """L'or (vrai) sur la période tournante, normalisé avec les statistiques de l'or -- même construction que le
    petit examen. [] si indisponible."""
    from src.features import normalize_features
    from src.multi_timeframe import discover_files
    data_cfg = cfg.get("data", {})
    path = discover_files(data_cfg.get("folder", "")).get("M15")
    if not path or not os.path.exists(path):
        return []
    cross_folder = data_cfg.get("cross_asset_folder") or os.path.join(
        os.path.dirname(os.path.abspath(data_cfg.get("folder", "."))), "cross_asset")
    m15 = load_m15(path)
    i0 = int(np.searchsorted(m15["time"].to_numpy(), np.datetime64(pd.Timestamp(val_start))))
    src = m15.iloc[max(0, i0 - 3000):]
    src = src[src["time"] <= pd.Timestamp(val_end)].reset_index(drop=True)
    from src.trend_vision import daily_closes
    df = build_market_frame("XAUUSD", src, context_tfs, cross_folder, fred=fred,
                            toolbox=any(str(c).startswith("tb_") for c in cols), daily=daily_closes(m15))
    df = df[df["time"] >= pd.Timestamp(val_start)].tail(max_val_bars).reset_index(drop=True)
    if len(df) < 2000:
        return []
    df[cols] = df[cols].replace([np.inf, -np.inf], np.nan).ffill().fillna(0.0)
    dfn, _ = normalize_features(df, stats=gold_stats, columns=cols)
    dfn[cols] = dfn[cols].astype("float32")
    add_cost_column(dfn, "XAUUSD", reference_cost(cfg), cfg)
    from src.trading_env import TradingEnv
    keep = ["time", "open", "high", "low", "close", "volume", TradingEnv.ATR_RAW_COLUMN, "cost_multiplier"]
    return [("XAUUSD", dfn[[c for c in keep if c in dfn.columns] + [c for c in cols if c not in keep]].reset_index(drop=True))]


def other_markets_val(cfg: dict, cols: list[str], context_tfs: list[str], cut_time, val_start, val_end,
                      max_bars_per_market: int = 120000, max_val_bars: int = 20000,
                      fred=None, keep_windows: list | None = None) -> list[tuple[str, pd.DataFrame]]:
    """EXAMEN MULTI-MARCHÉS (07/10/2026) : pour chaque marché d'entraînement (miroirs compris), la MÊME période
    calendaire que la validation de l'or [val_start, val_end] -- jamais vue à l'entraînement (coupé avant
    `cut_time`) ni dans le jeu sous clé -- normalisée avec les statistiques de SA tranche d'entraînement (et
    inversée au même niveau de prix). Au plus `max_val_bars` bougies (les plus récentes) par marché. À appeler
    APRÈS other_markets_train (mêmes arguments) : un marché sans entraînement en cache est ignoré.
    Retourne [(nom, DataFrame)]."""
    from src.features import normalize_features
    mm = (cfg.get("multi_market") or {})
    embargo = pd.Timedelta(hours=float(mm.get("embargo_hours", 48)))
    cut = pd.Timestamp(cut_time) - embargo
    val_start, val_end = pd.Timestamp(val_start), pd.Timestamp(val_end)
    # examen tournant : de nouvelles périodes à chaque cycle -> on ne garde en mémoire que celles demandées
    # (`keep_windows`, ou cette seule période par défaut)
    keep = {(pd.Timestamp(a).floor("D"), pd.Timestamp(b).floor("D")) for a, b in (keep_windows or [(val_start, val_end)])}
    for k in [k for k in _val_cache if (k[1], k[2]) not in keep]:
        del _val_cache[k]
    data_cfg = cfg.get("data", {})
    cross_folder = data_cfg.get("cross_asset_folder") or os.path.join(
        os.path.dirname(os.path.abspath(data_cfg.get("folder", "."))), "cross_asset")
    jobs = []
    for symbol, path, mirror, n_bars in _market_jobs(cfg, max_bars_per_market):
        if not os.path.exists(path):
            continue
        key = (symbol, path, os.path.getmtime(path), cut.floor("D"), tuple(cols), n_bars, mirror)
        info = _train_info.get(key)
        if info is None:
            continue
        jobs.append((symbol, path, mirror, info, (key, val_start.floor("D"), val_end.floor("D"), max_val_bars)))
    # 12/10/2026 : les périodes d'examen sont tirées au sort à chaque cycle -> ~114 marchés-périodes reconstruits par
    # cycle (~3 s chacun, ~5 min) l'un après l'autre. Construits par plusieurs PROCESSUS en parallèle (calcul
    # identique, voir _build_exam_frame) ; repli à la suite si le parallèle échoue. Ordre de sortie inchangé.
    todo = [j for j in jobs if j[4] not in _val_cache]
    if todo:
        args = [(info["name"], path, mirror, info["k"], info["stats"], cols, context_tfs, cross_folder, fred,
                 val_start, val_end, max_val_bars, reference_cost(cfg), cfg) for _, path, mirror, info, _ in todo]
        n = max(1, int(mm.get("exam_build_workers", 4) or 1))
        frames = None
        if n > 1 and len(todo) > 1:
            try:
                from concurrent.futures import ProcessPoolExecutor
                with ProcessPoolExecutor(max_workers=min(n, len(todo))) as pool:
                    frames = list(pool.map(_build_exam_frame, args))
            except Exception as e:
                log.warning(f"[AUREXIS] construction parallèle des examens impossible ({type(e).__name__}: {e}) "
                            f"-> à la suite.")
        if frames is None:
            frames = [_build_exam_frame(a) for a in args]
        for j, (frame, msg) in zip(todo, frames):
            _val_cache[j[4]] = frame
            log.info(msg)
    out = []
    for symbol, path, mirror, info, vkey in jobs:
        if _val_cache.get(vkey) is not None:
            out.append((info["name"], _val_cache[vkey]))
    return out


def _build_exam_frame(a: tuple):
    """Une période d'examen d'un marché (fonction de haut niveau : exécutable dans un autre processus). Retourne
    (DataFrame ou None, message de journal)."""
    from src.features import normalize_features
    from src.trading_env import TradingEnv
    from src.trend_vision import daily_closes
    name, path, mirror, k, stats, cols, context_tfs, cross_folder, fred, val_start, val_end, max_val_bars, ref_cost, cfg = a
    keep = ["time", "open", "high", "low", "close", "volume", TradingEnv.ATR_RAW_COLUMN, "cost_multiplier"]
    try:
        m15 = load_m15(path)
        daily = daily_closes(mirror_m15(m15, k) if mirror else m15)   # tendances : tout l'historique
        i0 = int(np.searchsorted(m15["time"].to_numpy(), np.datetime64(val_start)))
        m15 = m15.iloc[max(0, i0 - 3000):]
        m15 = m15[m15["time"] <= val_end].reset_index(drop=True)
        if mirror:
            m15 = mirror_m15(m15, k)
        df = build_market_frame(name, m15, context_tfs, cross_folder, fred=fred,
                                toolbox=any(str(c).startswith("tb_") for c in cols), daily=daily)
        df = df[df["time"] >= val_start].tail(max_val_bars).reset_index(drop=True)
        if len(df) < 3000:                                # 09/10 : 5000 -> 3000 (périodes tournantes de ~3,5 mois)
            return None, f"[AUREXIS] examen {name} : seulement {len(df)} bougies -- ignoré."
        df[cols] = df[cols].replace([np.inf, -np.inf], np.nan).ffill().fillna(0.0)
        dfn, _ = normalize_features(df, stats=stats, columns=cols)
        if mirror:
            dfn[_mirror_neutral(cols)] = 0.0
        dfn[cols] = dfn[cols].astype("float32")
        add_cost_column(dfn, name, ref_cost, cfg)
        dfn = dfn[[c for c in keep if c in dfn.columns] + [c for c in cols if c not in keep]].reset_index(drop=True)
        return dfn, (f"[AUREXIS] examen {name} prêt : {len(dfn)} bougies "
                     f"({dfn['time'].iloc[0].date()} -> {dfn['time'].iloc[-1].date()}).")
    except Exception as e:
        return None, f"[AUREXIS] examen {name} : construction impossible ({type(e).__name__}: {e}) -- ignoré."
    return out


def combine_segments(gold_train: pd.DataFrame, others: list[pd.DataFrame],
                     cols: list[str] | None = None) -> pd.DataFrame:
    """Or (segment 0) + autres marchés (1..n), colonnes communes uniquement (jamais de NaN introduit par une
    colonne absente d'un marché, ex. spread mesuré), `segment_id` pour TradingEnv. Avec `cols`, ne garde que ce
    que TradingEnv lit (prix, ATR brut, temps, variables) : ~4x moins de mémoire par processus d'entraînement."""
    if not others:
        return gold_train
    from src.trading_env import TradingEnv
    frames = [gold_train] + others
    if any("cost_multiplier" in f.columns for f in others) and "cost_multiplier" not in gold_train.columns:
        gold_train = gold_train.assign(cost_multiplier=np.float32(1.0))   # or = frais de référence (09/10)
        frames[0] = gold_train
    common = [c for c in gold_train.columns if all(c in f.columns for f in others)]
    if cols is not None:
        keep = set(cols) | {"time", "open", "high", "low", "close", "volume", TradingEnv.ATR_RAW_COLUMN, "cost_multiplier"}
        common = [c for c in common if c in keep]
    parts = []
    for i, f in enumerate(frames):
        p = f[common].copy()
        p["segment_id"] = i
        parts.append(p)
    return pd.concat(parts, ignore_index=True)
