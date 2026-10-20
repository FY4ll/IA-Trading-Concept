"""
decision_journal.py
====================
Journal de décision TRAÇABLE (05/10/2026, vision "Autonomous Trader V1", §17,
§23, §26, §41, §58, §67) dans une base SQLite :

  decisions  : une ligne par style et par cycle -- probabilités du modèle,
               cible brute, chaque garde-fou qui l'a modifiée (raisons),
               action finale (OPEN_LONG/OPEN_SHORT/HOLD/CLOSE/REVERSE/WAIT),
               raison du WAIT, régime, volatilité, structure, news, spread.
  executions : chaque jambe d'ordre réellement envoyée -- prix/volume/SL/TP
               voulus contre réels (relus sur MT5 après envoi), slippage,
               latence, retcode, ticket de position.
  trades     : chaque position clôturée (historique MT5), reliée à la
               décision qui l'a ouverte -- profit, R, MFE/MAE, régime à
               l'entrée, raison de sortie (SL/TP/IA).
  events     : diagnostics, rollback, hypothèses de recherche.

Toutes les écritures sont best-effort : une erreur de journal ne doit JAMAIS
interrompre une décision réelle. Une connexion SQLite par appel (thread-safe).
"""
from __future__ import annotations
import json
import logging
import os
import sqlite3
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone

log = logging.getLogger("decision_journal")

DEFAULT_PATH = os.path.join("data", "decision_journal.sqlite")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS decisions (
    decision_id TEXT PRIMARY KEY, ts_utc TEXT, style TEXT, generation INTEGER, score REAL,
    p_short REAL, p_flat REAL, p_long REAL, raw_target REAL, final_target REAL,
    action TEXT, wait_reason TEXT, block_reasons TEXT, existing_direction INTEGER, existing_ticket INTEGER,
    price REAL, spread_pct REAL, atr REAL, regime TEXT, vol_class TEXT, vol_percentile REAL,
    efficiency_ratio REAL, structure TEXT, swing_high REAL, swing_low REAL, news_status TEXT, next_event TEXT,
    stop_pct REAL, atr_multiplier REAL, take_profit_rr REAL, risk_pct REAL, order_report TEXT
);
CREATE INDEX IF NOT EXISTS ix_decisions_style_ts ON decisions(style, ts_utc);
CREATE TABLE IF NOT EXISTS executions (
    id INTEGER PRIMARY KEY AUTOINCREMENT, decision_id TEXT, ts_utc TEXT, style TEXT, leg TEXT,
    direction INTEGER, volume_req REAL, volume_filled REAL, price_req REAL, price_filled REAL,
    slippage REAL, adverse_slippage REAL, sl_req REAL, tp_req REAL, sl_actual REAL, tp_actual REAL,
    retcode INTEGER, latency_ms REAL, position_ticket INTEGER, verified INTEGER, risk_usd REAL, note TEXT
);
CREATE INDEX IF NOT EXISTS ix_exec_ticket ON executions(position_ticket);
CREATE TABLE IF NOT EXISTS trades (
    position_id INTEGER PRIMARY KEY, style TEXT, generation INTEGER, decision_id TEXT, direction INTEGER,
    volume REAL, open_time TEXT, open_price REAL, close_time TEXT, close_price REAL, sl REAL, tp REAL,
    profit REAL, commission REAL, swap REAL, net_profit REAL, risk_usd REAL, r_multiple REAL,
    mfe_price REAL, mae_price REAL, mfe_r REAL, mae_r REAL, close_reason TEXT,
    regime_at_entry TEXT, vol_class_at_entry TEXT, structure_at_entry TEXT, synced_at TEXT
);
CREATE INDEX IF NOT EXISTS ix_trades_style ON trades(style, close_time);
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT, ts_utc TEXT, kind TEXT, style TEXT, payload TEXT
);
CREATE TABLE IF NOT EXISTS kv (k TEXT PRIMARY KEY, v TEXT);
"""

_DECISION_COLS = ["decision_id", "ts_utc", "style", "generation", "score", "p_short", "p_flat", "p_long",
                  "raw_target", "final_target", "action", "wait_reason", "block_reasons", "existing_direction",
                  "existing_ticket", "price", "spread_pct", "atr", "regime", "vol_class", "vol_percentile",
                  "efficiency_ratio", "structure", "swing_high", "swing_low", "news_status", "next_event",
                  "stop_pct", "atr_multiplier", "take_profit_rr", "risk_pct", "order_report"]
_EXEC_COLS = ["decision_id", "ts_utc", "style", "leg", "direction", "volume_req", "volume_filled", "price_req",
              "price_filled", "slippage", "adverse_slippage", "sl_req", "tp_req", "sl_actual", "tp_actual",
              "retcode", "latency_ms", "position_ticket", "verified", "risk_usd", "note"]
_TRADE_COLS = ["position_id", "style", "generation", "decision_id", "direction", "volume", "open_time",
               "open_price", "close_time", "close_price", "sl", "tp", "profit", "commission", "swap",
               "net_profit", "risk_usd", "r_multiple", "mfe_price", "mae_price", "mfe_r", "mae_r",
               "close_reason", "regime_at_entry", "vol_class_at_entry", "structure_at_entry", "synced_at"]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def classify_action(existing_direction: int, final_target: float) -> str:
    e = int(existing_direction or 0)
    f = 0 if abs(final_target or 0.0) <= 1e-9 else (1 if final_target > 0 else -1)
    if e == 0:
        return "WAIT" if f == 0 else ("OPEN_LONG" if f > 0 else "OPEN_SHORT")
    if f == 0:
        return "CLOSE"
    return "HOLD" if f == e else "REVERSE"


def wait_reason(action: str, raw_target: float, block_reasons: list[str], proba: dict | None) -> str | None:
    """Pourquoi l'IA n'ouvre pas (WAIT) ou pourquoi elle sort (CLOSE). None pour une ouverture/maintien."""
    if action not in ("WAIT", "CLOSE"):
        return None
    if block_reasons:
        return block_reasons[0]
    if abs(raw_target or 0.0) <= 1e-9:
        if action == "CLOSE":
            return "model_exit"
        if proba:
            edge = max(proba.get("long", 0), proba.get("short", 0))
            return f"model_flat:edge_insuffisant(p_dir={edge:.2f},p_flat={proba.get('flat', 0):.2f})"
        return "model_flat"
    return "unknown"


class DecisionJournal:
    def __init__(self, path: str = DEFAULT_PATH):
        self.path = path
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with self._conn() as c:
            c.executescript(_SCHEMA)

    @contextmanager
    def _conn(self):
        c = sqlite3.connect(self.path, timeout=10)
        try:
            yield c
            c.commit()
        finally:
            c.close()

    # --- écriture -----------------------------------------------------------------------------------------
    def new_decision_id(self) -> str:
        return uuid.uuid4().hex

    def record_decision(self, row: dict) -> str | None:
        try:
            row = dict(row)
            row.setdefault("decision_id", self.new_decision_id())
            row.setdefault("ts_utc", utc_now_iso())
            for k in ("block_reasons", "order_report"):
                if k in row and not isinstance(row[k], (str, type(None))):
                    row[k] = json.dumps(row[k], default=str)
            vals = [row.get(k) for k in _DECISION_COLS]
            with self._conn() as c:
                c.execute(f"INSERT OR REPLACE INTO decisions ({','.join(_DECISION_COLS)}) "
                          f"VALUES ({','.join('?' * len(_DECISION_COLS))})", vals)
            return row["decision_id"]
        except Exception as e:
            log.warning(f"Journal de décision : écriture impossible ({type(e).__name__}: {e}).")
            return None

    def record_execution(self, row: dict):
        try:
            row = dict(row)
            row.setdefault("ts_utc", utc_now_iso())
            vals = [row.get(k) for k in _EXEC_COLS]
            with self._conn() as c:
                c.execute(f"INSERT INTO executions ({','.join(_EXEC_COLS)}) "
                          f"VALUES ({','.join('?' * len(_EXEC_COLS))})", vals)
        except Exception as e:
            log.warning(f"Journal d'exécution : écriture impossible ({type(e).__name__}: {e}).")

    def upsert_trade(self, row: dict):
        try:
            row = dict(row)
            row.setdefault("synced_at", utc_now_iso())
            vals = [row.get(k) for k in _TRADE_COLS]
            with self._conn() as c:
                c.execute(f"INSERT OR REPLACE INTO trades ({','.join(_TRADE_COLS)}) "
                          f"VALUES ({','.join('?' * len(_TRADE_COLS))})", vals)
        except Exception as e:
            log.warning(f"Journal des trades : écriture impossible ({type(e).__name__}: {e}).")

    def log_event(self, kind: str, payload: dict, style: str | None = None):
        try:
            with self._conn() as c:
                c.execute("INSERT INTO events (ts_utc, kind, style, payload) VALUES (?,?,?,?)",
                          (utc_now_iso(), kind, style, json.dumps(payload, default=str)))
        except Exception:
            pass

    def set_kv(self, k: str, v):
        with self._conn() as c:
            c.execute("INSERT OR REPLACE INTO kv (k, v) VALUES (?, ?)", (k, json.dumps(v, default=str)))

    def get_kv(self, k: str, default=None):
        with self._conn() as c:
            r = c.execute("SELECT v FROM kv WHERE k=?", (k,)).fetchone()
        return json.loads(r[0]) if r else default

    # --- lecture ------------------------------------------------------------------------------------------
    def query(self, sql: str, params: tuple = ()) -> list[dict]:
        with self._conn() as c:
            c.row_factory = sqlite3.Row
            return [dict(r) for r in c.execute(sql, params).fetchall()]

    def known_position_ids(self) -> set[int]:
        return {r["position_id"] for r in self.query("SELECT position_id FROM trades")}

    def opening_execution(self, position_ticket: int) -> dict | None:
        rows = self.query("SELECT * FROM executions WHERE position_ticket=? AND leg='open' "
                          "ORDER BY id DESC LIMIT 1", (int(position_ticket),))
        return rows[0] if rows else None

    def decision(self, decision_id: str) -> dict | None:
        rows = self.query("SELECT * FROM decisions WHERE decision_id=?", (decision_id,))
        return rows[0] if rows else None

    def trades(self, style: str | None = None, generation: int | None = None, since: str | None = None) -> list[dict]:
        sql, p = "SELECT * FROM trades WHERE 1=1", []
        if style:
            sql += " AND style=?"; p.append(style)
        if generation is not None:
            sql += " AND generation=?"; p.append(int(generation))
        if since:
            sql += " AND close_time>=?"; p.append(since)
        return self.query(sql + " ORDER BY close_time", tuple(p))

    def action_stats(self, since: str) -> list[dict]:
        return self.query("SELECT style, action, COUNT(*) n FROM decisions WHERE ts_utc>=? "
                          "GROUP BY style, action ORDER BY style, action", (since,))

    def wait_reason_stats(self, since: str) -> list[dict]:
        return self.query(
            "SELECT style, CASE WHEN instr(wait_reason, ':')>0 THEN substr(wait_reason, 1, instr(wait_reason, ':')-1) "
            "ELSE wait_reason END AS reason, COUNT(*) n FROM decisions WHERE ts_utc>=? AND action IN ('WAIT','CLOSE') "
            "GROUP BY style, reason ORDER BY style, n DESC", (since,))


def summarize_r(trades: list[dict]) -> dict:
    """Statistiques par R : n, taux de gain, R moyen, profit factor, t-stat du R moyen."""
    import math
    rs = [t["r_multiple"] for t in trades if t.get("r_multiple") is not None]
    pnl = [t.get("net_profit") or 0.0 for t in trades]
    n = len(rs)
    out = {"n": len(trades), "n_r": n, "net_profit": round(sum(pnl), 2),
           "win_rate": (sum(1 for x in pnl if x > 0) / len(pnl)) if pnl else None}
    gains = sum(x for x in pnl if x > 0)
    losses = -sum(x for x in pnl if x < 0)
    out["profit_factor"] = (gains / losses) if losses > 0 else (None if gains == 0 else float("inf"))
    if n:
        mean = sum(rs) / n
        out["avg_r"] = mean
        out["total_r"] = sum(rs)
        if n > 1:
            sd = math.sqrt(sum((x - mean) ** 2 for x in rs) / (n - 1))
            out["t_stat"] = mean / (sd / math.sqrt(n)) if sd > 0 else None
        cum, peak, dd = 0.0, 0.0, 0.0
        for x in rs:
            cum += x
            peak = max(peak, cum)
            dd = min(dd, cum - peak)
        out["max_dd_r"] = dd
    return out
