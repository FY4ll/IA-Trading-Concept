"""
diagnostics.py
===============
Auto-diagnostic (05/10/2026, vision "Autonomous Trader V1", §29, §41, §48, §72) :

  - résultats LIVE de chaque champion (journal de décision) contre ce que la
    lockbox annonçait : t-stat du R moyen, taux de gain (test binomial),
    profit factor -> drapeaux edge_degradation / win_rate_drop ;
  - fréquence : trades live par jour contre la lockbox -> inactivity /
    overtrading (jamais de trades forcés : c'est un signal d'enquête) ;
  - raisons des WAIT, actions par style ;
  - exécution : slippage défavorable, latence, ouvertures non vérifiées,
    remplissages partiels ;
  - dérive des variables (PSI) entre les 30 derniers jours et la lockbox ;
  - régimes récents contre la lockbox ; résultats live par régime/volatilité.

Écrit reports/diagnostics.json et reports/diagnostics.md (lu pour le rapport du
dimanche) et alimente src/research_engine.py. Ne lit que des fichiers locaux
(CSV, journal SQLite, meta.json) : aucun appel MT5, utilisable dans un thread
séparé sans gêner le trading.
"""
from __future__ import annotations
import json
import logging
import math
import os
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd

from src.decision_journal import summarize_r

log = logging.getLogger("diagnostics")

REPORT_JSON = os.path.join("reports", "diagnostics.json")
REPORT_MD = os.path.join("reports", "diagnostics.md")
DRIFT_FEATURES = ["return_1", "volatility_10", "atr_pct", "adx_14", "rsi_14", "trend_signal", "bb_pct"]
BARS_PER_DAY_H1 = 23.0


def psi(expected: np.ndarray, actual: np.ndarray, bins: int = 10) -> float:
    """Population Stability Index (quantiles de la référence) : < 0.1 stable, 0.1-0.25 modéré, > 0.25 fort."""
    expected = expected[np.isfinite(expected)]
    actual = actual[np.isfinite(actual)]
    if len(expected) < 50 or len(actual) < 20:
        return float("nan")
    edges = np.unique(np.quantile(expected, np.linspace(0, 1, bins + 1)))
    if len(edges) < 3:
        return 0.0
    edges[0], edges[-1] = -np.inf, np.inf
    e = np.histogram(expected, edges)[0] / len(expected)
    a = np.histogram(actual, edges)[0] / len(actual)
    e, a = np.clip(e, 1e-4, None), np.clip(a, 1e-4, None)
    return float(np.sum((a - e) * np.log(a / e)))


def _group_r(trades: list[dict], key: str) -> dict:
    out: dict[str, list] = {}
    for t in trades:
        out.setdefault(str(t.get(key) or "UNKNOWN"), []).append(t)
    return {k: summarize_r(v) for k, v in out.items()}


def style_diagnostics(journal, style: str, meta: dict, now: datetime) -> dict:
    gen = meta.get("generation")
    lock = meta.get("lockbox") or {}
    val = meta.get("metrics") or {}
    trades_gen = journal.trades(style=style, generation=gen)
    trades_all = journal.trades(style=style)
    s = summarize_r(trades_gen)
    flags = []
    if s.get("n_r", 0) >= 20 and s.get("t_stat") is not None and s["t_stat"] < -2.0:
        flags.append("edge_degradation")
    p0 = val.get("win_rate")
    if p0 and s.get("n", 0) >= 20 and s.get("win_rate") is not None:
        z = (s["win_rate"] - p0) / math.sqrt(p0 * (1 - p0) / s["n"])
        s["win_rate_z_vs_validation"] = z
        if z < -2.0:
            flags.append("win_rate_drop")
    lock_pf = lock.get("profit_factor")
    if lock_pf and s.get("n", 0) >= 20 and s.get("profit_factor") is not None and s["profit_factor"] < min(1.0, 0.8 * lock_pf):
        flags.append("profit_factor_low")

    since7 = (now - timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")
    actions = {r["action"]: r["n"] for r in journal.action_stats(since7) if r["style"] == style}
    waits = {r["reason"]: r["n"] for r in journal.wait_reason_stats(since7) if r["style"] == style}
    first = journal.query("SELECT MIN(ts_utc) t FROM decisions WHERE style=?", (style,))
    days_obs = None
    if first and first[0]["t"]:
        t0 = datetime.strptime(first[0]["t"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
        days_obs = min(7.0, (now - t0).total_seconds() / 86400)
    expected_per_day = (lock.get("n_trades", 0) / (lock.get("n_bars", 1) / BARS_PER_DAY_H1)) if lock.get("n_bars") else None
    opens = actions.get("OPEN_LONG", 0) + actions.get("OPEN_SHORT", 0) + actions.get("REVERSE", 0)
    freq = {"opens_7d": opens, "days_observed": days_obs, "expected_trades_per_day": expected_per_day}
    if days_obs and days_obs >= 3 and expected_per_day:
        ratio = (opens / days_obs) / expected_per_day
        freq["ratio_vs_lockbox"] = ratio
        if ratio < 0.25:
            flags.append("inactivity")
        elif ratio > 3.0:
            flags.append("overtrading")
    return {"generation": gen, "live_current_generation": s, "live_all_generations": summarize_r(trades_all),
            "lockbox": {k: lock.get(k) for k in ("sharpe", "max_drawdown", "total_return", "n_trades", "profit_factor")},
            "lockbox_prop_firm": lock.get("prop_firm"), "actions_7d": actions, "wait_reasons_7d": waits,
            "frequency": freq, "live_by_regime": _group_r(trades_all, "regime_at_entry"),
            "live_by_vol_class": _group_r(trades_all, "vol_class_at_entry"), "flags": flags}


def execution_diagnostics(journal, now: datetime) -> dict:
    since = (now - timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")
    rows = journal.query("SELECT * FROM executions WHERE ts_utc>=?", (since,))
    opens = [r for r in rows if r["leg"] == "open"]
    adv = [r["adverse_slippage"] for r in rows if r.get("adverse_slippage") is not None]
    lat = [r["latency_ms"] for r in rows if r.get("latency_ms") is not None]
    return {"n_orders_7d": len(rows), "n_opens_7d": len(opens),
            "unverified_opens": sum(1 for r in opens if r.get("retcode") == 10009 and not r.get("verified")),
            "rejected": sum(1 for r in rows if r.get("retcode") not in (None, 10009, 10008)),
            "partial_fills": sum(1 for r in opens if r.get("note") and "partiel" in r["note"]),
            "avg_adverse_slippage": float(np.mean(adv)) if adv else None,
            "latency_ms_p50": float(np.percentile(lat, 50)) if lat else None,
            "latency_ms_p95": float(np.percentile(lat, 95)) if lat else None}


def drift_diagnostics(cfg: dict, recent_days: int = 30) -> dict:
    from src.multi_timeframe import discover_files
    from src.data_loader import load_kaggle_ohlcv_csv
    from src.features import add_technical_features
    from src.lockbox_gate import resolve_lockbox_start
    from src.market_regime import regime_series
    files = discover_files(cfg["data"]["folder"])
    if "H1" not in files:
        return {"error": "pas de fichier H1"}
    df = load_kaggle_ohlcv_csv(files["H1"])
    lockbox_start = resolve_lockbox_start(cfg)
    df = df[df["time"] >= lockbox_start - pd.Timedelta(days=60)].reset_index(drop=True)
    df = add_technical_features(df, fundamental_feed=None)
    end = df["time"].max()
    recent = df[df["time"] >= end - pd.Timedelta(days=recent_days)]
    ref = df[(df["time"] >= lockbox_start) & (df["time"] < end - pd.Timedelta(days=recent_days))]
    out = {"recent_from": str(recent["time"].min()), "recent_to": str(end), "features": {}}
    for c in DRIFT_FEATURES:
        if c in df.columns:
            out["features"][c] = psi(ref[c].to_numpy(float), recent[c].to_numpy(float))
    vals = [v for v in out["features"].values() if np.isfinite(v)]
    out["max_psi"] = max(vals) if vals else None
    regs = regime_series(df)
    rr = regs.loc[recent.index]
    rf = regs.loc[ref.index]
    out["regime_recent"] = {k: float(v) for k, v in rr["regime"].value_counts(normalize=True).items()}
    out["regime_lockbox"] = {k: float(v) for k, v in rf["regime"].value_counts(normalize=True).items()}
    out["vol_recent"] = {k: float(v) for k, v in rr["vol_class"].value_counts(normalize=True).items()}
    return out


def run_diagnostics(cfg: dict, journal, styles: list[str], models_dir: str = "models",
                    now: datetime | None = None, with_drift: bool = True) -> dict:
    now = now or datetime.now(timezone.utc)
    diag = {"generated_at": now.strftime("%Y-%m-%d %H:%M UTC"), "styles": {}}
    for st in styles:
        try:
            with open(os.path.join(models_dir, f"champion_{st}", "meta.json"), encoding="utf-8") as f:
                meta = json.load(f)
        except Exception:
            continue
        diag["styles"][st] = style_diagnostics(journal, st, meta, now)
    diag["execution"] = execution_diagnostics(journal, now)
    if with_drift:
        try:
            diag["drift"] = drift_diagnostics(cfg)
        except Exception as e:
            diag["drift"] = {"error": f"{type(e).__name__}: {e}"}
    return diag


def _pct(x):
    return "n/a" if x is None else f"{x:.0%}"


def to_markdown(diag: dict) -> str:
    L = [f"# Diagnostic de l'IA ({diag['generated_at']})", ""]
    for st, s in diag["styles"].items():
        g = s["live_current_generation"]
        L.append(f"## {st} (gén. {s['generation']})")
        avg = f"{g['avg_r']:+.2f}R" if g.get("avg_r") is not None else "n/a"
        t = f"{g['t_stat']:+.2f}" if g.get("t_stat") is not None else "n/a"
        L.append(f"- Live (génération actuelle) : {g['n']} trades, gain {_pct(g.get('win_rate'))}, R moyen {avg}, "
                 f"t={t}, net {g['net_profit']:+.2f}$")
        lk = s["lockbox"]
        if lk.get("sharpe") is not None:
            L.append(f"- Lockbox : Sharpe {lk['sharpe']:.2f}, DD {lk['max_drawdown']:.1%}, {lk['n_trades']} trades")
        fr = s["frequency"]
        if fr.get("ratio_vs_lockbox") is not None:
            L.append(f"- Fréquence : {fr['opens_7d']} ouvertures sur {fr['days_observed']:.1f} j "
                     f"({fr['ratio_vs_lockbox']:.1f}x l'attendu lockbox)")
        if s["wait_reasons_7d"]:
            L.append("- Raisons d'attente/sortie (7 j) : " + ", ".join(f"{k} {v}" for k, v in s["wait_reasons_7d"].items()))
        L.append(f"- Drapeaux : {', '.join(s['flags']) or 'aucun'}")
        L.append("")
    ex = diag.get("execution") or {}
    L.append("## Exécution (7 j)")
    L.append(f"- {ex.get('n_orders_7d', 0)} ordres, {ex.get('rejected', 0)} refusés, {ex.get('unverified_opens', 0)} "
             f"ouvertures non vérifiées, {ex.get('partial_fills', 0)} remplissages partiels")
    if ex.get("avg_adverse_slippage") is not None:
        L.append(f"- Slippage défavorable moyen {ex['avg_adverse_slippage']:+.3f}$, latence p50 "
                 f"{ex.get('latency_ms_p50') or 0:.0f} ms / p95 {ex.get('latency_ms_p95') or 0:.0f} ms")
    dr = diag.get("drift") or {}
    if dr.get("features"):
        L.append("")
        L.append(f"## Dérive des variables (30 derniers jours vs lockbox) : PSI max {dr.get('max_psi') or 0:.2f}")
        L.append("- " + ", ".join(f"{k} {v:.2f}" for k, v in dr["features"].items() if np.isfinite(v)))
        L.append("- Régimes récents : " + ", ".join(f"{k} {v:.0%}" for k, v in dr.get("regime_recent", {}).items()))
    return "\n".join(L) + "\n"


def write_reports(diag: dict):
    os.makedirs("reports", exist_ok=True)
    with open(REPORT_JSON, "w", encoding="utf-8") as f:
        json.dump(diag, f, indent=1, default=str)
    with open(REPORT_MD, "w", encoding="utf-8") as f:
        f.write(to_markdown(diag))
