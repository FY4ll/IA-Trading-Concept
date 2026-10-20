"""
MOTEUR DEVISES « SALLE DE MARCHÉ » (08/10/2026) -- ÉTUDE, ne touche à rien de ce qui tourne.

Les stratégies systématiques que les banques et les grands fonds appliquent aux devises, sur les 7 grandes
devises contre le dollar (euro, livre, yen, franc suisse, dollars australien, canadien, néo-zélandais) :
  1. PORTAGE : acheter les devises à taux d'intérêt élevé, vendre celles à taux faible (classement chaque
     semaine, les 3 plus hautes contre les 3 plus basses, dollar compris) -- gain = variation du prix + écart
     de taux, moins une marge du courtier sur les intérêts de nuit.
  2. TENDANCE : pour chaque devise, moyenne des signes de ses rendements sur 1, 3 et 12 mois (méthode classique
     des fonds de tendance), taille inversement proportionnelle à sa volatilité.
Paramètres STANDARDS de la littérature, aucun réglage optimisé. Chaque stratégie est ramenée à une volatilité
cible, puis combinée à risque égal. Coûts : écart de prix à chaque changement de position + marge sur les
intérêts de nuit.

Périodes (identiques au reste du projet) : développement 2013 -> 11/2021, validation 11/2021 -> 05/2023,
jeu sous clé 06/2023 -> aujourd'hui.

    python scripts/moteur_devises.py          (cwd = code/)
Écrit reports/moteur_devises.json.
"""
import json, os, sys, time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
os.chdir(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import numpy as np
import pandas as pd
import requests
import yaml

PAIRS = {"EUR": ("EURUSD", False), "GBP": ("GBPUSD", False), "AUD": ("AUDUSD", False), "NZD": ("NZDUSD", False),
         "JPY": ("USDJPY", True), "CHF": ("USDCHF", True), "CAD": ("USDCAD", True)}
RATES = {"USD": "IR3TIB01USM156N", "EUR": "IR3TIB01EZM156N", "GBP": "IR3TIB01GBM156N", "JPY": "IR3TIB01JPM156N",
         "CHF": "IR3TIB01CHM156N", "AUD": "IR3TIB01AUM156N", "CAD": "IR3TIB01CAM156N", "NZD": "IR3TIB01NZM156N"}
SPREAD = 0.00012          # coût par unité de position changée (≈ 1 point sur l'euro-dollar, prudent)
SWAP_MARKUP = 0.01        # marge du courtier sur les intérêts de nuit : 1 % par an de l'exposition
TARGET_VOL = 0.08         # volatilité annuelle visée par stratégie
DEV_END, VAL_END = pd.Timestamp("2021-11-03"), pd.Timestamp("2023-05-30")


def log(m):
    print(f"{time.strftime('%H:%M:%S')} {m}", flush=True)


def fred(series, key):
    cache = os.path.join("data", "devises", f"{series}.json")
    if os.path.exists(cache) and time.time() - os.path.getmtime(cache) < 86400:
        obs = json.load(open(cache, encoding="utf-8"))
    else:
        r = requests.get("https://api.stlouisfed.org/fred/series/observations",
                         params={"series_id": series, "api_key": key, "file_type": "json",
                                 "observation_start": "2010-01-01"}, timeout=30)
        r.raise_for_status()
        obs = [{"date": o["date"], "value": o["value"]} for o in r.json()["observations"]]
        os.makedirs(os.path.dirname(cache), exist_ok=True)
        json.dump(obs, open(cache, "w", encoding="utf-8"))
    s = pd.Series({pd.Timestamp(o["date"]): float(o["value"]) for o in obs if o["value"] not in (".", "")})
    return s.sort_index() / 100.0


def prices():
    import MetaTrader5 as mt5
    mt5.initialize()
    out = {}
    for ccy, (sym, inv) in PAIRS.items():
        r = mt5.copy_rates_range(sym, mt5.TIMEFRAME_D1, pd.Timestamp("2012-01-01").to_pydatetime(),
                                 pd.Timestamp.now().to_pydatetime())
        d = pd.DataFrame(r)
        s = pd.Series(d["close"].to_numpy(), index=pd.to_datetime(d["time"], unit="s").dt.normalize())
        out[ccy] = 1.0 / s if inv else s            # valeur de la devise en dollars
    return pd.DataFrame(out).sort_index().ffill().dropna()


def vol_scale(ret_strategy, target=TARGET_VOL):
    """Ramène une stratégie à la volatilité cible avec une estimation PASSÉE (63 jours, décalée d'un jour)."""
    vol = ret_strategy.rolling(63, min_periods=40).std().shift(1) * np.sqrt(252)
    return (target / vol).clip(0, 5).fillna(0.0)


def run(px, rates):
    ret = px.pct_change().fillna(0.0)
    # taux mensuels -> journaliers, décalés d'un mois (délai de publication) : aucune information du futur
    r = rates.reindex(pd.date_range(rates.index.min(), px.index.max(), freq="D")).ffill().shift(31)
    r = r.reindex(px.index).ffill()
    diff = r[list(PAIRS)].sub(r["USD"], axis=0)                        # écart de taux contre le dollar
    week = px.index.to_series().dt.to_period("W")
    rebal = week != week.shift(1)                                      # premier jour de chaque semaine
    # ---- 1) PORTAGE : classement des 8 devises (dollar = 0) ; 3 plus hautes achetées, 3 plus basses vendues
    allr = pd.concat([diff, pd.Series(0.0, index=diff.index, name="USD")], axis=1)
    rank = allr.rank(axis=1)
    w8 = (rank >= 6).astype(float) / 3 - (rank <= 3).astype(float) / 3
    w_carry = w8[list(PAIRS)].where(rebal).ffill().shift(1).fillna(0.0)   # le dollar = contrepartie
    # ---- 2) TENDANCE : moyenne des signes 1/3/12 mois, taille / volatilité de la devise
    sig = sum(np.sign(px.pct_change(n)) for n in (21, 63, 252)) / 3
    dvol = ret.rolling(63, min_periods=40).std() * np.sqrt(252)
    w_trend = (sig / dvol / len(PAIRS) * 0.1).where(rebal).ffill().shift(1).fillna(0.0)
    res = {}
    for name, w in (("portage", w_carry), ("tendance", w_trend)):
        gross = (w * ret).sum(axis=1) + (w * diff).sum(axis=1) / 252
        cost = w.diff().abs().sum(axis=1).fillna(0) * SPREAD + w.abs().sum(axis=1) * SWAP_MARKUP / 252
        raw = gross - cost
        k = vol_scale(raw)
        res[name] = {"ret": raw * k, "w": w.mul(k, axis=0)}
    combo = (res["portage"]["ret"] + res["tendance"]["ret"]) / np.sqrt(2)
    res["ensemble"] = {"ret": combo * vol_scale(combo).clip(0, 3)}
    return res


def stats(r, lo, hi):
    from src.ftmo_metrics import prop_firm_summary
    x = r[(r.index >= lo) & (r.index < hi)]
    x = x[x.index.dayofweek < 5]
    if len(x) < 60:
        return {}
    eq = (1 + x).cumprod()
    pf = prop_firm_summary(x.to_numpy(), n_sims=1000)
    m = (1 + x).groupby(x.index.to_period("M")).prod() - 1
    return {"jours": len(x), "rendement_annuel": float(eq.iloc[-1] ** (252 / len(x)) - 1),
            "regularite": float(x.mean() / (x.std() + 1e-12) * np.sqrt(252)),
            "baisse_max": float((eq / eq.cummax() - 1).min()), "mois_positifs": float((m > 0).mean()),
            "mois_median": float(m.median()), "pire_mois": float(m.min()), "pire_jour": float(x.min()),
            "challenge_ftmo": pf.get("challenge_pass"), "verification_ftmo": pf.get("verification_pass")}


def main():
    cfg = yaml.safe_load(open("../run_config_A.yaml", encoding="utf-8"))
    key = (cfg.get("fred") or {}).get("api_key") or ""
    if not key:
        raise SystemExit("clé FRED absente de la config")
    rates = pd.DataFrame({c: fred(s, key) for c, s in RATES.items()})
    log("taux 3 mois disponibles : " + ", ".join(f"{c} {rates[c].dropna().index.min().date()}->"
                                                  f"{rates[c].dropna().index.max().date()}" for c in rates))
    rates = rates.ffill()
    px = prices()
    log(f"prix journaliers : {len(px)} jours ({px.index.min().date()} -> {px.index.max().date()})")
    res = run(px, rates)
    from src.lockbox_gate import resolve_lockbox_start
    lock = resolve_lockbox_start(cfg)
    periods = {"developpement": (pd.Timestamp("2014-01-01"), DEV_END), "validation": (DEV_END, VAL_END),
               "sous_cle": (lock, pd.Timestamp.now())}
    report = {}
    for name in ("portage", "tendance", "ensemble"):
        report[name] = {p: stats(res[name]["ret"], *b) for p, b in periods.items()}
        for p, s in report[name].items():
            if s:
                log(f"  {name:9s} {p:14s} : {s['rendement_annuel']:+.1%}/an | régularité {s['regularite']:+.2f} | "
                    f"baisse max {s['baisse_max']:.1%} | mois positifs {s['mois_positifs']:.0%} | "
                    f"mois médian {s['mois_median']:+.2%} | pire mois {s['pire_mois']:+.1%} | "
                    f"challenge FTMO {(s['challenge_ftmo'] or 0):.0%}")
    # lien avec l'or (AUREX gagne quand l'or monte) : un 2e moteur utile doit être peu lié
    import MetaTrader5 as mt5
    g = pd.DataFrame(mt5.copy_rates_range("XAUUSD", mt5.TIMEFRAME_D1, pd.Timestamp("2014-01-01").to_pydatetime(),
                                          pd.Timestamp.now().to_pydatetime()))
    gr = pd.Series(g["close"].to_numpy(), index=pd.to_datetime(g["time"], unit="s").dt.normalize()).pct_change()
    c = pd.concat([res["ensemble"]["ret"], gr], axis=1).dropna().corr().iloc[0, 1]
    report["lien_avec_or"] = float(c)
    log(f"lien du moteur devises avec l'or (jour par jour) : {c:+.2f}")
    last = res["portage"]["w"].iloc[-1]
    report["positions_portage_actuelles"] = {k: float(v) for k, v in last.items()}
    log("positions de portage cette semaine : " + ", ".join(f"{k} {v:+.2f}" for k, v in last.items() if abs(v) > 1e-6))
    json.dump(report, open(os.path.join("reports", "moteur_devises.json"), "w", encoding="utf-8"), indent=1,
              default=str)
    log("TERMINÉ")


if __name__ == "__main__":
    main()
