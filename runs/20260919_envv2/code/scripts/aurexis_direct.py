"""
AUREXIS EN DIRECT -- un passage (lancé toutes les 15 minutes par la tâche Windows « TestIA_AurexisDirect »).

Mode lu dans data/aurexis_live/mode.json : « blanc » (défaut : compte fictif, aucun ordre) ou « demo » (vrais ordres
sur le compte démo, activé uniquement par scripts/regle_demo_aurexis.py quand les critères sont remplis).
Indépendant de Run A (autre processus) : ne touche ni à l'entraînement ni au trading d'AUREX.

    python scripts/aurexis_direct.py            (cwd = code/)
"""
import json, os, sys, time
os.environ.setdefault("CUDA_VISIBLE_DEVICES", "-1")
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import numpy as np
import pandas as pd
import yaml

STYLE = "AUREXIS"


def mode() -> str:
    try:
        with open(os.path.join("data", "aurexis_live", "mode.json"), encoding="utf-8") as f:
            return json.load(f).get("mode", "blanc")
    except (OSError, ValueError):
        return "blanc"


def frame_from_rates(rates) -> pd.DataFrame:
    df = pd.DataFrame(rates)
    df["time"] = pd.to_datetime(df["time"], unit="s")
    df = df.rename(columns={"tick_volume": "volume"})
    return df[["time", "open", "high", "low", "close", "volume"]]


def main():
    from src import aurexis_live as al
    from src.aurexis_data import build_market_frame, load_market_stats, add_cost_column, cost_round_trip
    from src.features import normalize_features
    from src.trading_env import TradingEnv
    from src.agent import TradingAgent
    from src.lockbox_gate import eval_env_kwargs
    from src.episodic_memory import EpisodicMemory
    import MetaTrader5 as mt5
    t0 = time.time()
    os.makedirs(al.DIR, exist_ok=True)
    lock = os.path.join(al.DIR, "passage.lock")
    if os.path.exists(lock) and time.time() - os.path.getmtime(lock) < 13 * 60:
        print("passage précédent encore en cours -- ignoré"); return
    open(lock, "w").close()
    try:
        cfg = yaml.safe_load(open("../run_config_A.yaml", encoding="utf-8"))
        cdir = os.path.join("models", f"champion_{STYLE}")
        meta = json.load(open(os.path.join(cdir, "meta.json"), encoding="utf-8"))
        cols, ctx = meta["feature_columns"], meta.get("context_timeframes") or []
        gold_stats = {c: tuple(v) for c, v in json.load(open(os.path.join(cdir, "norm_stats.json"), encoding="utf-8")).items()}
        symbols = json.load(open(os.path.join(al.DIR, "symboles.json"), encoding="utf-8"))
        current_mode = mode()
        if current_mode == "demo":
            symbols.pop("XAUUSD", None)                      # l'or reste à AUREX : jamais deux IA sur un symbole
        kw = eval_env_kwargs(STYLE, cfg, meta)
        mem = EpisodicMemory(cfg["memory"]["db_path"], cfg["memory"]["max_episodes"],
                             private_styles=cfg["memory"].get("private_styles"))
        kw.update(memory_snapshot=mem.snapshot(dim=len(cols), sources=["backtest"], style=STYLE),
                  memory_top_k=cfg.get("memory", {}).get("similarity_top_k", 5))
        cross = os.path.join(os.path.dirname(os.path.abspath(cfg["data"]["folder"])), "cross_asset")
        if not mt5.initialize():
            raise SystemExit(f"MT5 indisponible : {mt5.last_error()}")
        book = al.load_state()
        agent, rows, decisions = None, [], {}
        # HEURE DU COURTIER (09/10 : un marché fermé a sa dernière bougie ET son dernier prix figés à la même heure --
        # les comparer entre eux le faisait passer pour ouvert) : la plus récente cotation parmi les cryptos (7j/7)
        server_now = None
        for s in ("BTCUSD", "ETHUSD", "LTCUSD", "XRPUSD"):
            tk = mt5.symbol_info_tick(s) if mt5.symbol_select(s, True) else None
            if tk is not None and tk.time:
                server_now = max(server_now or 0, int(tk.time))
        server_now = pd.Timestamp(server_now, unit="s") if server_now else None
        debut = os.path.join(al.DIR, "debut.json")             # date de démarrage du compte (règle de passage en démo)
        if not os.path.exists(debut):
            json.dump({"debut": time.time(), "le": time.strftime("%Y-%m-%d %H:%M")}, open(debut, "w", encoding="utf-8"))
        # MODE DÉMO : un connecteur MT5 par symbole (profil de risque FTMO appliqué) ; coupe-circuit du compte LU dans
        # l'état tenu par la boucle d'AUREX (src/account_guard, jamais écrit ici : un seul écrivain)
        connectors, guard_halted = {}, False
        if current_mode == "demo":
            import copy
            from src.risk_profile import apply_risk_profile
            from src.mt5_connector import MT5Connector
            from src import account_guard
            cfg_live = apply_risk_profile(copy.deepcopy(cfg))

            def conn_for(sym):
                if sym not in connectors:
                    c = copy.deepcopy(cfg_live)
                    c["live"]["symbol"] = sym
                    connectors[sym] = MT5Connector(c)
                    connectors[sym].connect()
                return connectors[sym]
            guard_halted = account_guard.is_halted()
            if guard_halted:
                n = al.demo_breaker({s: conn_for(s) for s in symbols.values() if s})
                rows.append({"heure": time.strftime("%Y-%m-%d %H:%M"), "marche": "TOUS",
                             "evenement": f"coupe-circuit du compte : {n} position(s) AUREXIS fermée(s)"})
        for name, sym in symbols.items():
            if not sym:
                continue
            try:
                mt5.symbol_select(sym, True)
                rates = mt5.copy_rates_from_pos(sym, mt5.TIMEFRAME_M15, 0, 3600)
                d1 = mt5.copy_rates_from_pos(sym, mt5.TIMEFRAME_D1, 0, 320)
                if rates is None or len(rates) < 3200 or d1 is None:
                    decisions[name] = "cotations indisponibles"; continue
                bars = frame_from_rates(rates).iloc[:-1].reset_index(drop=True)      # bougies CLÔTURÉES seulement
                day = str(bars["time"].iloc[-1].date())
                book.new_day(max(day, book.day or day))
                cost = cost_round_trip(name, cfg) or 0.0002
                seen = book.last_bar.get(name)
                new = bars[bars["time"] > pd.Timestamp(seen)] if seen else bars.iloc[0:0]
                book.follow_bars(name, new, cost)
                for t in book.trades:
                    if t["marche"] == name and t["raison"] in ("stop", "objectif"):
                        rows.append({"heure": t["ferme"], "marche": name, "evenement": f"sortie ({t['raison']})",
                                     "sens": t["sens"], "prix": t["sortie"], "resultat_compte": round(t["resultat_compte"], 6),
                                     "equite": round(book.equity, 2)})
                book.trades = [t for t in book.trades if t["marche"] != name]
                book.last_bar[name] = str(bars["time"].iloc[-1])
                ref = server_now or pd.Timestamp(mt5.symbol_info_tick(sym).time, unit="s")
                if ref - bars["time"].iloc[-1] > pd.Timedelta(minutes=45):
                    decisions[name] = "marché fermé"; continue
                stats = gold_stats if name == "XAUUSD" else (load_market_stats(name) or {}).get("stats")
                if not stats:
                    decisions[name] = "statistiques absentes"; continue
                daily = pd.Series(frame_from_rates(d1)["close"].to_numpy(float),
                                  index=frame_from_rates(d1)["time"].dt.normalize())
                raw = build_market_frame(name, bars, ctx, cross, fred=None,
                                         toolbox=any(str(c).startswith("tb_") for c in cols), daily=daily)
                raw[cols] = raw[cols].replace([np.inf, -np.inf], np.nan).ffill().fillna(0.0)
                dfn, _ = normalize_features(raw, stats=stats, columns=cols)
                dfn[cols] = dfn[cols].astype("float32")
                add_cost_column(dfn, name, float(kw.get("transaction_cost", 0.0002)), cfg)
                env = TradingEnv(dfn, feature_columns=cols, style=STYLE, **kw)
                env.reset()
                env.current_step = len(dfn) - 1
                if agent is None:
                    agent = TradingAgent.load(os.path.join(cdir, "agent"), env, {"algo": meta.get("algo", "PPO")})
                price = float(dfn["close"].iloc[-1])
                p = book.positions.get(name)
                if p is not None:
                    env.position, env.entry_price, env.stop_price = float(p.direction), p.entry, p.stop
                    env.take_profit_price, env._size, env._initial_risk = p.tp, p.size, p.initial_risk
                    env.unrealized_pnl_pct = book.unrealized(name, price)
                if env.trader_state:
                    env.live_state = {"stops_today": book.stops_today.get(name, 0), "day_pnl": book.day_pnl(),
                                      "bars_in_position": p.bars if p else 0}
                if getattr(env, "account_state", False):     # 11/10 : vision du compte -- les VRAIES valeurs
                    own = p.risk if p is not None else 0.0
                    env.live_state = {**(env.live_state or {}),
                                      "account_dd": max(0.0, 1.0 - book.equity / book.peak_equity),
                                      "other_risk_share": max(0.0, book.open_risk() - own) / al.RISK_BUDGET}
                d = al.decode(env, agent.predict(env._get_obs(), deterministic=True))
                d["risk"] *= book.brake()                       # frein de baisse : risque réduit après une baisse > 5 %
                target = 0 if (book.halted or guard_halted) else d["direction"]
                if current_mode == "demo" and not guard_halted:
                    try:                                        # le compte fictif continue en parallèle (comparaison)
                        rows.append({"heure": str(bars["time"].iloc[-1]), "marche": name, "evenement":
                                     "démo : " + al.demo_execute(conn_for(sym), target, d, meta.get("generation"))})
                    except Exception as e:
                        rows.append({"heure": str(bars["time"].iloc[-1]), "marche": name,
                                     "evenement": f"démo : ordre impossible ({type(e).__name__}: {e})"})
                when = str(bars["time"].iloc[-1])
                if p is not None and target == p.direction:
                    book.manage(name, d["manage"], price)
                    decisions[name] = f"garde {'achat' if p.direction > 0 else 'vente'}"
                else:
                    if p is not None:
                        pnl = book.close(name, price, cost, "signal", when)
                        rows.append({"heure": when, "marche": name, "evenement": "sortie (décision)",
                                     "sens": "achat" if p.direction > 0 else "vente", "prix": price,
                                     "resultat_compte": round(pnl, 6), "equite": round(book.equity, 2)})
                        book.trades.clear()
                    if target != 0 and not book.can_open(d["risk"]):
                        decisions[name] = f"voulait {'acheter' if target > 0 else 'vendre'} : budget de risque plein"
                        continue
                    if target != 0:
                        q = book.open(name, target, price, d["stop_pct"], d["tp_mult"], d["risk"], when)
                        rows.append({"heure": when, "marche": name, "evenement": "entrée",
                                     "sens": "achat" if target > 0 else "vente", "prix": price, "stop": round(q.stop, 6),
                                     "objectif": round(q.tp, 6) if q.tp else "", "risque": d["risk"],
                                     "equite": round(book.equity, 2)})
                    decisions[name] = {1: "achète", -1: "vend", 0: "à plat"}[target]
            except Exception as e:
                decisions[name] = f"erreur {type(e).__name__}: {e}"
        wall = book.check_walls()
        if wall and not book.halted:
            for name in list(book.positions):
                last = book.last_bar.get(name)
                tick = mt5.symbol_info_tick(symbols[name])
                pnl = book.close(name, float(tick.bid if book.positions[name].direction > 0 else tick.ask),
                                 cost_round_trip(name, cfg) or 0.0002, f"mur {wall}", str(last))
                rows.append({"heure": str(last), "marche": name, "evenement": f"fermé par le mur ({wall})",
                             "resultat_compte": round(pnl, 6), "equite": round(book.equity, 2)})
            book.halted = wall
        mt5.shutdown()
        al.append_journal(rows)
        al.save_state(book)
        resume = {"heure": time.strftime("%Y-%m-%d %H:%M"), "mode": current_mode, "equite": round(book.equity, 2),
                  "compte": round(book.equity / book.start_equity - 1, 5), "jour": round(book.day_pnl(), 5),
                  "positions": len(book.positions), "arret": book.halted, "decisions": decisions,
                  "duree_s": round(time.time() - t0)}
        json.dump(resume, open(os.path.join(al.DIR, "dernier_passage.json"), "w", encoding="utf-8"), indent=1)
        print(f"{resume['heure']} [{current_mode}] compte {resume['compte']:+.2%} (jour {resume['jour']:+.2%}), "
              f"{len(book.positions)} position(s), {len(rows)} événement(s), {resume['duree_s']} s", flush=True)
    finally:
        try:
            os.remove(lock)
        except OSError:
            pass


if __name__ == "__main__":
    os.chdir(os.environ.get("DIRECT_CODE") or os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    main()
