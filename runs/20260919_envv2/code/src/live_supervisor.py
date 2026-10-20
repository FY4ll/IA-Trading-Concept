"""
live_supervisor.py
===================
Couche de supervision de la boucle live (05/10/2026, vision "Autonomous Trader V1") :
regroupe ce que src/demo_trader.py appelle à chaque cycle, sans toucher aux
décisions de l'IA elle-même :

  - régime de marché par style (src/market_regime.py) ;
  - filtre de marché sur les OUVERTURES (src/market_gate.py : news, spread, données, régime) ;
  - journal de décision traçable + exécutions vérifiées (src/decision_journal.py) ;
  - synchronisation des trades clôturés MT5 (src/trade_sync.py) ;
  - réduction / suspension / rollback d'un champion dégradé en live (src/live_rollback.py) ;
  - diagnostic quotidien en arrière-plan + hypothèses de recherche (src/diagnostics.py,
    src/research_engine.py) ; expériences lancées dans un PROCESSUS SÉPARÉ de basse priorité
    (scripts/regime_report.py) : la recherche ne peut jamais bloquer le trading.

Tout est désactivé tant que la config ne l'active pas (`journal.enabled`,
`live.market_gate.enabled`, `live.rollback.enabled`, `diagnostics.enabled`,
`research.auto_run_experiments`) -- comportement d'origine inchangé sinon.
"""
from __future__ import annotations
import json
import logging
import os
import subprocess
import sys
import threading
import time

from src.market_regime import detect_regime

log = logging.getLogger("live_supervisor")


class LiveSupervisor:
    def __init__(self, cfg: dict, connector):
        self.cfg = cfg
        self.connector = connector
        jcfg = cfg.get("journal") or {}
        self.journal = None
        if jcfg.get("enabled"):
            from src.decision_journal import DecisionJournal
            self.journal = DecisionJournal(jcfg.get("db_path", os.path.join("data", "decision_journal.sqlite")))
        self.gate = None
        if ((cfg.get("live") or {}).get("market_gate") or {}).get("enabled"):
            from src.market_gate import MarketGate
            self.gate = MarketGate(cfg)
        self.regime_cfg = cfg.get("regime") or {}
        self.rollback_cfg = (cfg.get("live") or {}).get("rollback") or {}
        self.diag_cfg = cfg.get("diagnostics") or {}
        self.research_cfg = cfg.get("research") or {}
        self.rb_states: dict[str, dict] = {}
        self.news: dict = {}
        self.spread_pct = None
        self._diag_thread = None
        self._research_proc = None
        self.market_status: dict = {}
        # NARRATEUR (08/10/2026) : ouvertures/sorties justifiées, intentions bloquées, bulletins (src/live_narrator.py)
        self.narrator = None
        try:
            from src.live_narrator import Narrator
            self.narrator = Narrator(cfg, connector)
        except Exception as e:
            import logging
            logging.getLogger("live_supervisor").warning(f"narrateur indisponible ({type(e).__name__}: {e})")

    @property
    def active(self) -> bool:
        return self.journal is not None or self.gate is not None

    # --- début de cycle ---------------------------------------------------------------------------------
    def start_cycle(self, eligible: list[dict]) -> list[dict]:
        if self.narrator is not None:
            try:
                self.narrator.maybe_bulletin([e["style"] for e in eligible])
            except Exception:
                pass
        if self.journal is not None:
            from src.trade_sync import sync_closed_trades
            sync_closed_trades(self.journal, self.connector)
            if self.rollback_cfg.get("enabled"):
                from src import live_rollback
                for e in eligible:
                    st = live_rollback.update(self.journal, e["style"], e["meta"].get("generation"),
                                              self.rollback_cfg, notify=self._notify)
                    if st:
                        self.rb_states[e["style"]] = st
                    else:
                        self.rb_states.pop(e["style"], None)
            self._maybe_run_diagnostics([e["style"] for e in eligible])
            self._maybe_run_research([e["style"] for e in eligible])
        self.news = self.gate.news_context() if self.gate is not None else {}
        self.spread_pct = None
        fn = getattr(self.connector, "get_current_spread_pct", None)
        if self.journal is not None and fn is not None:
            try:
                self.spread_pct = fn()
            except Exception:
                self.spread_pct = None
        return [self._apply_rollback(e) for e in eligible]

    def _apply_rollback(self, entry: dict) -> dict:
        st = self.rb_states.get(entry["style"])
        if not st or st.get("stage") != "ROLLBACK" or st.get("rollback_to") is None:
            return entry
        from src.continuous_trainer import _champion_dir
        from src.trading_env import env_version_matches
        d = os.path.join(_champion_dir(entry["style"]), "history", f"gen_{st['rollback_to']}")
        try:
            with open(os.path.join(d, "meta.json"), encoding="utf-8") as f:
                meta = json.load(f)
        except Exception:
            return entry
        if "feature_columns" not in meta or not env_version_matches(meta):
            return entry
        return {"style": entry["style"], "meta": meta, "model_path": os.path.join(d, "agent"),
                "stats_path": os.path.join(d, "norm_stats.json"), "rolled_back_from": entry["meta"].get("generation")}

    # --- par style ---------------------------------------------------------------------------------------
    def regime(self, df) -> dict:
        try:
            return detect_regime(df, self.regime_cfg)
        except Exception as e:
            log.warning(f"Régime de marché indisponible ({type(e).__name__}: {e}).")
            return {}

    def risk_scale(self, style: str) -> float:
        st = self.rb_states.get(style)
        return float(st.get("risk_scale", 1.0)) if st else 1.0

    def opening_blocks(self, style: str, df, regime: dict) -> list[str]:
        reasons = []
        st = self.rb_states.get(style)
        if st and st.get("stage") == "SUSPEND":
            reasons.append(f"style_suspended:gen{st.get('generation')}")
        if self.gate is not None:
            reasons += self.gate.check_opening(df, self.connector, regime, style=style)
        return reasons

    def record(self, *, style, entry, rt, raw_target, final_target, block_reasons, existing_position,
               regime, stop_pct, atr_multiplier, take_profit_rr, risk_pct, price=None, df=None, extra=None,
               limit_offset=None, manage=0):
        if self.journal is None:
            return
        from src.decision_journal import classify_action, wait_reason
        existing_dir = existing_position["direction"] if existing_position else 0
        action = classify_action(existing_dir, final_target)
        proba = getattr(rt, "last_proba", None)
        report = getattr(self.connector, "last_order_report", None)
        row = {
            "style": style, "generation": entry["meta"].get("generation"), "score": entry["meta"].get("score"),
            "p_short": (proba or {}).get("short"), "p_flat": (proba or {}).get("flat"),
            "p_long": (proba or {}).get("long"), "raw_target": raw_target, "final_target": final_target,
            "action": action, "wait_reason": wait_reason(action, raw_target, block_reasons, proba),
            "block_reasons": block_reasons, "existing_direction": existing_dir,
            "existing_ticket": (existing_position or {}).get("ticket"), "price": price,
            "spread_pct": self.spread_pct, "atr": regime.get("atr"), "regime": regime.get("regime"),
            "vol_class": regime.get("vol_class"), "vol_percentile": regime.get("vol_percentile"),
            "efficiency_ratio": regime.get("efficiency_ratio"), "structure": regime.get("structure"),
            "swing_high": regime.get("swing_high"), "swing_low": regime.get("swing_low"),
            "news_status": self.news.get("news_status"), "next_event": self.news.get("next_event"),
            "stop_pct": stop_pct, "atr_multiplier": atr_multiplier, "take_profit_rr": take_profit_rr,
            "risk_pct": risk_pct, "order_report": {"action": (report or {}).get("action")} if report else None,
        }
        try:
            from src.trader.notes import build_note
            last = df.iloc[-1] if df is not None and len(df) else None
            row["note"] = build_note(action, last, regime, extra, limit_offset if action.startswith(("OPEN", "REV")) else None,
                                     manage, row["wait_reason"])
        except Exception:
            row["note"] = None
        if self.narrator is not None:
            try:
                self.narrator.on_decision(row, existing_position)
            except Exception:
                pass
        decision_id = self.journal.record_decision(row)
        for leg in (report or {}).get("legs", []):
            self.journal.record_execution({"decision_id": decision_id, "style": style, **leg})
        self.market_status[style] = {"regime": regime.get("regime"), "vol_class": regime.get("vol_class"),
                                     "structure": regime.get("structure"), "action": action,
                                     "wait_reason": row["wait_reason"]}

    # --- tâches de fond ----------------------------------------------------------------------------------
    def _notify(self, msg: str):
        try:
            from src.notifier import send_alert
            send_alert(self.cfg, subject="Test_IA - supervision live", message=msg)
        except Exception:
            pass

    def _maybe_run_diagnostics(self, styles: list[str]):
        if not self.diag_cfg.get("enabled") or self.journal is None:
            return
        if self._diag_thread is not None and self._diag_thread.is_alive():
            return
        last = self.journal.get_kv("diagnostics_last_run", 0) or 0
        if time.time() - last < float(self.diag_cfg.get("interval_hours", 24)) * 3600:
            return
        self.journal.set_kv("diagnostics_last_run", time.time())

        def _run():
            try:
                from src.diagnostics import run_diagnostics, write_reports
                from src.research_engine import generate_hypotheses
                diag = run_diagnostics(self.cfg, self.journal, styles)
                write_reports(diag)
                new = generate_hypotheses(diag)
                flags = {st: s["flags"] for st, s in diag["styles"].items() if s["flags"]}
                self.journal.log_event("diagnostics", {"flags": flags, "new_hypotheses": [h["key"] for h in new],
                                                       "max_psi": (diag.get("drift") or {}).get("max_psi")})
                log.info(f"[diagnostic] terminé : drapeaux {flags or 'aucun'}, {len(new)} nouvelle(s) hypothèse(s).")
                if flags or new:
                    self._notify(f"Diagnostic : drapeaux {flags or 'aucun'} ; nouvelles hypothèses : "
                                 f"{', '.join(h['key'] for h in new) or 'aucune'}.")
            except Exception as e:
                log.warning(f"[diagnostic] échec ({type(e).__name__}: {e}).")

        self._diag_thread = threading.Thread(target=_run, name="DIAGNOSTICS", daemon=True)
        self._diag_thread.start()

    def _maybe_run_research(self, styles: list[str]):
        if not self.research_cfg.get("auto_run_experiments") or self.journal is None:
            return
        if self._research_proc is not None and self._research_proc.poll() is None:
            return
        last = self.journal.get_kv("research_last_run", 0) or 0
        if time.time() - last < float(self.research_cfg.get("interval_days", 7)) * 86400:
            return
        from src.research_engine import open_hypotheses
        pending = [h for h in open_hypotheses() if h.get("type") == "regime_filter" and h.get("style") in styles]
        if not pending:
            return
        self.journal.set_kv("research_last_run", time.time())
        todo = sorted({h["style"] for h in pending})
        script = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts", "regime_report.py")
        out = open(os.path.join("logs", f"research_{time.strftime('%Y%m%d_%H%M')}.txt"), "w", encoding="utf-8")
        flags = getattr(subprocess, "BELOW_NORMAL_PRIORITY_CLASS", 0)
        self._research_proc = subprocess.Popen([sys.executable, "-u", script, *todo, "--only-hypotheses"], stdout=out,
                                               stderr=subprocess.STDOUT, creationflags=flags)
        log.info(f"[recherche] expériences lancées en processus séparé (basse priorité) pour {todo}.")
        self.journal.log_event("research_started", {"styles": todo, "hypotheses": [h["id"] for h in pending]})
