"""
note_argent.py
==============
NOTE D'EXAMEN « ARGENT FTMO » (09/10/2026, accord de l'utilisateur : « fais le nécessaire »).

Pourquoi : l'ancienne note (qualité des gains - 2 x plus forte baisse) PUNISSAIT la taille -- la qualité des gains ne
change pas quand on double la taille, la baisse double. À stratégie égale, l'IA la plus timide était promue, alors
que la récompense d'entraînement lui demande de gagner de l'argent et que le challenge exige +10 %.

La nouvelle note mesure ce que FTMO mesure, sur UN compte qui trade TOUS les marchés en même temps (le portefeuille) :
  - le GAIN MENSUEL du compte (1 point par +1 %/mois) : plus de taille = plus de gain si l'IA a un avantage ;
  - la CHANCE DE RÉUSSIR LE CHALLENGE moins la chance d'échouer (-5 % sur un jour, -10 % au total), simulée sur ce
    compte : c'est ce terme qui rend la taille excessive perdante (le casino échoue) ;
  - la baisse n'est punie que PRÈS DES MURS (au-delà de `dd_wall`, scénarios de crise compris), jamais avant.

Approximation assumée : les marchés n'ont pas tous la même période d'examen ; le portefeuille est simulé en tirant,
pour chaque jour, un morceau de l'historique de CHAQUE marché indépendamment (on ignore leurs liens entre eux).
Les marchés « miroirs » (inversés, pour apprendre à vendre) n'entrent pas dans le compte : ce ne sont pas des marchés
réels, et le miroir d'un marché annulerait le marché lui-même.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

DAILY_LIMIT, TOTAL_LIMIT, TARGET = 0.05, 0.10, 0.10
# ÉQUILIBRE (mesuré, voir tests/test_note_argent.py) : la chance FTMO (réussite - échec, poids 5) est le critère
# PRINCIPAL ; le gain mensuel ne sert qu'à guider une IA trop timide (qui ne réussit ni n'échoue jamais) et il est
# PLAFONNÉ à `gain_cap` points -- sans plafond, une IA « casino » (8x la taille, 59 % d'échecs) avait la meilleure note.
DEFAULTS = {"month_unit": 0.01, "ftmo_weight": 5.0, "gain_cap": 1.5, "dd_wall": 0.06, "dd_slope": 25.0, "clip": 5.0,
            "n_sims": 1000, "horizon_days": 120, "block": 5}


def run_daily_returns(env, df) -> np.ndarray:
    """Rendements journaliers d'une partie rejouée (courbe d'équité de `env`, dates de `df`)."""
    eq = np.asarray(env.equity_curve, dtype=float)
    start = max(0, int(env.window_size) - 1)
    times = pd.to_datetime(df["time"]).iloc[start:start + len(eq)]
    if len(times) < 2:
        return np.zeros(0)
    s = pd.Series(eq[:len(times)], index=times.to_numpy())
    daily = s.groupby(s.index.normalize()).last()
    return daily.pct_change().dropna().to_numpy(dtype=float)


def monthly_return(rets) -> float:
    """Gain moyen par mois (21 jours de bourse) -- additif entre marchés tradés sur un même compte."""
    r = np.asarray(rets, dtype=float)
    return float(r.mean() * 21) if len(r) else 0.0


def simulate_portfolio(series: list, target: float = TARGET, n_sims: int = 1000, horizon_days: int = 120,
                       block: int = 5, seed: int = 7) -> dict:
    """Challenge FTMO simulé sur un compte qui trade tous les marchés de `series` à la fois : chaque jour simulé, le
    rendement du compte = somme des rendements d'un jour de chaque marché, tirés par morceaux de `block` jours
    consécutifs (indépendamment d'un marché à l'autre). Issue : réussite (+target), échec du jour (-5 % sur un jour),
    échec total (-10 % depuis le départ) ou ni l'un ni l'autre dans `horizon_days`."""
    series = [np.asarray(s, dtype=float) for s in series if len(s) >= block + 1]
    if not series:
        return {"pass": 0.0, "daily_breach": 0.0, "total_breach": 0.0, "timeout": 1.0, "median_days": None}
    rng = np.random.default_rng(seed)
    n_blocks = -(-horizon_days // block)
    total = np.zeros((n_sims, n_blocks * block))
    for s in series:
        starts = rng.integers(0, len(s) - block + 1, size=(n_sims, n_blocks))
        idx = (starts[:, :, None] + np.arange(block)).reshape(n_sims, -1)
        total += s[idx]
    total = total[:, :horizon_days]
    bal = np.cumprod(1.0 + total, axis=1)
    big = horizon_days + 1

    def first(mask):
        return np.where(mask.any(axis=1), mask.argmax(axis=1), big)

    d_day, d_tot, d_win = first(total <= -DAILY_LIMIT), first(bal <= 1 - TOTAL_LIMIT), first(bal >= 1 + target)
    end = np.minimum(np.minimum(d_day, d_tot), d_win)
    win = (d_win == end) & (d_win < big) & (d_win < d_day) & (d_win < d_tot)
    daily = (d_day == end) & (d_day < big)
    tot = (d_tot == end) & (d_tot < big) & ~daily
    days = d_win[win] + 1
    return {"pass": float(win.mean()), "daily_breach": float(daily.mean()), "total_breach": float(tot.mean()),
            "timeout": float(1.0 - win.mean() - daily.mean() - tot.mean()),
            "median_days": float(np.median(days)) if len(days) else None}


def wall_penalty(dd: float, cfg: dict) -> float:
    """Baisse punie seulement au-delà du mur maison (`dd_wall`), fortement (pente `dd_slope`)."""
    return float(cfg["dd_slope"]) * max(0.0, float(dd) - float(cfg["dd_wall"]))


DEATH_NOTE = -100.0      # mort FTMO pendant une partie du petit examen : toujours la pire note


def _note(month: float, sim: dict, drawdown: float, c: dict) -> dict:
    # 09/10 16h : PAS DE PLANCHER sur les pertes (avant : -5 sur le gain, -10 sur la note). Quand tous les candidats
    # perdaient, ils étaient tous bloqués à -10 : égalité artificielle, une veine à -8 %/mois a remplacé un champion à
    # -5,9 %/mois. La sélection doit toujours savoir qui perd le MOINS. Le plafond des gains (gain_cap) reste.
    breach = sim["daily_breach"] + sim["total_breach"]
    gain = float(min(month / float(c["month_unit"]), float(c["gain_cap"])))
    ftmo = float(c["ftmo_weight"]) * (sim["pass"] - breach)
    wall = wall_penalty(drawdown, c)
    return {"note": float(gain + ftmo - wall), "mensuel": month, "gain": gain,
            "ftmo": ftmo, "mur": wall, "reussite": sim["pass"], "echec": breach, "jours_median": sim["median_days"]}


def note_run(rets, max_drawdown: float, cfg: dict | None = None) -> float:
    """Note « argent » d'UNE partie (petit examen) : même formule que le portefeuille, sur ce seul marché. Mort FTMO
    pendant la partie (jour <= -5 % ou baisse >= 10 %) = note minimale."""
    c = {**DEFAULTS, **(cfg or {})}
    r = np.asarray(rets, dtype=float)
    if (len(r) and r.min() <= -DAILY_LIMIT) or max_drawdown >= TOTAL_LIMIT:
        return DEATH_NOTE
    sim = simulate_portfolio([r], n_sims=int(c["n_sims"]), horizon_days=int(c["horizon_days"]), block=int(c["block"]))
    return _note(monthly_return(r), sim, max_drawdown, c)["note"]


def account_trades(env, name: str) -> list:
    """Trades d'une partie rejouée, au format du compte fidèle (src/aurexis_live.replay_account) : marché, heures
    d'ouverture (bougie d'exécution) et de clôture, risque choisi, résultat en part du compte (frais déduits)."""
    times = pd.to_datetime(env.df["time"]).to_numpy()
    last = len(times) - 1
    default_risk = float(getattr(env, "risk_sizing_pct", 0.0) or 0.0)
    out = []
    for t in env.trade_log:
        risk = t.get("risk") or default_risk
        if t.get("open_step") is None or not risk:
            continue
        out.append({"marche": name, "ouvert": times[min(int(t["open_step"]), last)],
                    "ferme": times[min(int(t["step"]) + 1, last)], "risque": float(risk),
                    "resultat": float(t["pnl_pct"]) - float(t.get("cost_pct", 0.0) or 0.0)})
    return out


def note_compte_fidele(entries: dict, crisis_drawdown: float = 0.0, cfg: dict | None = None) -> dict:
    """NOTE SUR LE COMPTE FIDÈLE (11/10/2026, accord de l'utilisateur). Verdict de la nuit du 10 au 11 : le champion
    442 ouvrait tant de positions à la fois que 79 % de ses trades étaient REFUSÉS par le budget de risque du vrai
    compte (4 %) -- l'ancienne note additionnait les marchés comme si ce budget n'existait pas, et sélectionnait donc
    des IA sur un compte qui n'existe pas. Ici, les trades de TOUS les marchés réels de la période (`entries` : nom ->
    {"trades", "debut", "fin"}) sont rejoués sur UN compte dans l'ordre du temps (budget, murs FTMO, frein de baisse) ;
    la note (même formule) est calculée sur les rendements journaliers de CE compte."""
    from src.aurexis_live import replay_account
    c = {**DEFAULTS, **(cfg or {})}
    real = {k: e for k, e in entries.items() if "miroir" not in k}
    trades = [t for e in real.values() for t in e["trades"]]
    r = replay_account(trades, brake=bool(c.get("frein", True)))
    if real:
        t0 = min(pd.Timestamp(e["debut"]) for e in real.values()).normalize()
        t1 = max(pd.Timestamp(e["fin"]) for e in real.values()).normalize()
        days = pd.bdate_range(t0, t1)
    else:
        days = pd.DatetimeIndex([])
    j = pd.Series({pd.Timestamp(k): v for k, v in r["jours"].items()}, dtype=float)
    daily = j.reindex(days.union(j.index)).fillna(0.0)
    rets = daily.to_numpy(dtype=float)
    sim = simulate_portfolio([rets], n_sims=int(c["n_sims"]), horizon_days=int(c["horizon_days"]),
                             block=int(c["block"]))
    if r.get("arret") == "total" or r.get("murs_jour", 0):
        # le compte a RÉELLEMENT touché un mur pendant la période : challenge raté, pas une probabilité (après l'arrêt,
        # les jours sans trades diluaient l'échec dans la simulation)
        sim = {**sim, "pass": 0.0, "daily_breach": 1.0, "total_breach": 0.0}
    out = _note(monthly_return(rets), sim, max(float(r["baisse_max"]), float(crisis_drawdown)), c)
    out.update(murs_jour=r.get("murs_jour", 0),n_marches=len(real), compte_fidele=True, compte=r["compte"], baisse_compte=r["baisse_max"],
               trades_pris=r["trades_pris"], trades_refuses=r["trades_refuses"], arret=r.get("arret"))
    return out


def note_portefeuille(market_rets: dict, crisis_drawdown: float = 0.0, cfg: dict | None = None) -> dict:
    """Note de l'examen complet : un compte FTMO qui trade tous les marchés réels de `market_rets` (nom -> rendements
    journaliers) en même temps. `crisis_drawdown` = pire baisse vue sur l'or (fenêtres + scénarios de crise)."""
    c = {**DEFAULTS, **(cfg or {})}
    real = {k: np.asarray(v, dtype=float) for k, v in market_rets.items() if "miroir" not in k and len(v)}
    monthly = {k: monthly_return(v) for k, v in real.items()}
    sim = simulate_portfolio(list(real.values()), n_sims=int(c["n_sims"]), horizon_days=int(c["horizon_days"]),
                             block=int(c["block"]))
    out = _note(float(sum(monthly.values())), sim, crisis_drawdown, c)
    out.update(par_marche={k: round(v, 5) for k, v in monthly.items()}, n_marches=len(real))
    return out
