"""
trade_sync.py
==============
Synchronise les positions CLÔTURÉES de l'historique MT5 (source de vérité) vers
la table `trades` du journal de décision (05/10/2026, vision V1 §25-27, §74) :
profit net, R (profit / risque réel au stop), MFE/MAE (meilleur et pire prix
atteints pendant le trade, en R), raison de sortie (SL/TP/IA), et contexte de
marché à l'entrée repris de la décision qui a ouvert le trade.

Heures : les deals et bougies MT5 sont en HEURE SERVEUR ; open_time/close_time
sont stockés tels quels (heure serveur), les décisions en UTC.
"""
from __future__ import annotations
import logging
import time
from datetime import datetime, timezone

log = logging.getLogger("trade_sync")


def _server_time_str(epoch: int) -> str:
    return datetime.fromtimestamp(int(epoch), tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def sync_closed_trades(journal, connector, lookback_days: float = 7.0, backfill_days: float = 30.0) -> list[dict]:
    fn = getattr(connector, "get_closed_positions", None)
    if fn is None or journal is None:
        return []
    days = lookback_days if journal.get_kv("trade_sync_backfilled") else backfill_days
    try:
        closed = fn(time.time() - days * 86400)
    except Exception as e:
        log.warning(f"Synchronisation des trades impossible ({type(e).__name__}: {e}).")
        return []
    known = journal.known_position_ids()
    contract = None
    ctx_fn = getattr(connector, "_price_and_contract_size", None)
    new = []
    for p in closed:
        pid = int(p["position_id"])
        if pid in known:
            continue
        ex = journal.opening_execution(pid)
        dec = journal.decision(ex["decision_id"]) if ex and ex.get("decision_id") else None
        sl = p.get("sl") or (ex or {}).get("sl_actual")
        risk_usd = (ex or {}).get("risk_usd")
        if risk_usd is None and sl:
            if contract is None and ctx_fn is not None:
                try:
                    ctx = ctx_fn()
                    contract = ctx[1] if ctx else None
                except Exception:
                    contract = None
            if contract:
                risk_usd = abs(p["open_price"] - sl) * p["volume"] * contract
        net = p["profit"] + p["commission"] + p["swap"]
        r = net / risk_usd if risk_usd else None
        mfe_p = mae_p = mfe_r = mae_r = None
        path_fn = getattr(connector, "get_price_path", None)
        if path_fn is not None:
            try:
                hl = path_fn(p["open_epoch"], p["close_epoch"])
                if hl:
                    hi, lo = hl
                    d = p["direction"]
                    mfe_p = (hi - p["open_price"]) if d > 0 else (p["open_price"] - lo)
                    mae_p = (p["open_price"] - lo) if d > 0 else (hi - p["open_price"])
                    if sl:
                        dist = abs(p["open_price"] - sl)
                        if dist > 0:
                            mfe_r, mae_r = mfe_p / dist, mae_p / dist
            except Exception:
                pass
        row = {
            "position_id": pid, "style": p.get("style"), "generation": p.get("generation"),
            "decision_id": (ex or {}).get("decision_id"), "direction": p["direction"], "volume": p["volume"],
            "open_time": _server_time_str(p["open_epoch"]), "open_price": p["open_price"],
            "close_time": _server_time_str(p["close_epoch"]), "close_price": p["close_price"],
            "sl": sl, "tp": p.get("tp"), "profit": p["profit"], "commission": p["commission"], "swap": p["swap"],
            "net_profit": net, "risk_usd": risk_usd, "r_multiple": r, "mfe_price": mfe_p, "mae_price": mae_p,
            "mfe_r": mfe_r, "mae_r": mae_r, "close_reason": p.get("close_reason"),
            "regime_at_entry": (dec or {}).get("regime"), "vol_class_at_entry": (dec or {}).get("vol_class"),
            "structure_at_entry": (dec or {}).get("structure"),
        }
        journal.upsert_trade(row)
        new.append(row)
        r_txt = f"{r:+.2f}R" if r is not None else "R inconnu"
        log.info(f"[trades] {row['style']} position {pid} clôturée ({row['close_reason']}) : "
                 f"{net:+.2f}$ ({r_txt}).")
    if not journal.get_kv("trade_sync_backfilled"):
        journal.set_kv("trade_sync_backfilled", True)
    return new
