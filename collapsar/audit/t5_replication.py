"""AUDIT 5 : réplications INDÉPENDANTES (code écrit de zéro, lecture directe des fichiers bruts, aucun module du
projet pour les calculs) : (i) bande de bruit US500 2015-2023 ; (ii) cassure C2 BTC ; (iii) zones zones supply and demand H4 de l'or.
Depuis Test_IA : venv_gpu\\Scripts\\python.exe -u -m collapsar.audit.t5_replication
"""
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

RACINE = Path(__file__).resolve().parents[2]
OUT = RACINE / "collapsar" / "vie" / "audit"
res = {}


def p(*a):
    print(*a, flush=True)


# ====================================================================== (i) bande de bruit, S&P 500 (HistData SPXUSD)
def spx_minutes():
    fs = sorted((RACINE / "data" / "minutes_histdata" / "SPXUSD").glob("*.csv"))
    df = pd.concat([pd.read_csv(f) for f in fs], ignore_index=True)
    df["ny"] = pd.to_datetime(df["t"].astype(str), format="%Y%m%d %H%M%S")
    return df.drop_duplicates("ny").set_index("ny").sort_index()[["open", "high", "low", "close"]]


def bande(df, de="2015-01-01", a="2024-01-01", cible=0.02, levmax=4.0, frais=0.0, vwap=True, regard=30):
    x = df[(df.index >= de) & (df.index < a)]
    mn = x.index.hour * 60 + x.index.minute - 570
    x = x[(mn >= 0) & (mn < 390)].copy()
    x["m"] = (x.index.hour * 60 + x.index.minute - 570)
    x["j"] = x.index.normalize()
    piv = {k: x.pivot_table(index="j", columns="m", values=k) for k in ("open", "high", "low", "close")}
    nb = piv["close"].notna().sum(1)
    garde = nb >= 370                                        # séance quasi complète
    O, H, L, C = (piv[k][garde].reindex(columns=range(390)) for k in ("open", "high", "low", "close"))
    C = C.ffill(axis=1).bfill(axis=1)
    O = O.fillna(C); H = H.fillna(C); L = L.fillna(C)
    jours = C.index
    C_, O_, H_, L_ = C.to_numpy(), O.to_numpy(), H.to_numpy(), L.to_numpy()
    ouv = O_[:, 0]
    veille = np.r_[np.nan, C_[:-1, 389]]
    sig = pd.DataFrame(np.abs(C_ / ouv[:, None] - 1)).rolling(14).mean().shift(1).to_numpy()
    ret_j = pd.Series(C_[:, 389]).pct_change()
    vol = ret_j.rolling(14).std().shift(1).to_numpy()
    moyen = np.cumsum((H_ + L_ + C_) / 3, axis=1) / np.arange(1, 391)
    regards = list(range(regard - 1, 390, regard))
    jour_g, trades = [], []
    for k in range(len(jours)):
        if not (np.isfinite(sig[k]).all() and np.isfinite(veille[k]) and np.isfinite(vol[k]) and vol[k] > 0):
            continue
        ub = max(ouv[k], veille[k]) * (1 + sig[k])
        lb = min(ouv[k], veille[k]) * (1 - sig[k])
        lev = min(levmax, cible / vol[k])
        pos, px = 0, 0.0
        g = 0.0
        for m in regards:
            c = C_[k, m]
            last = m == 389
            stop_l = max(ub[m], moyen[k, m]) if vwap else ub[m]
            stop_s = min(lb[m], moyen[k, m]) if vwap else lb[m]
            if pos == 1 and (c < stop_l or last):
                r = c / px - 1; g += lev * (r - frais); trades.append(r); pos = 0
            elif pos == -1 and (c > stop_s or last):
                r = 1 - c / px; g += lev * (r - frais); trades.append(r); pos = 0
            if pos == 0 and not last:
                if c > ub[m]:
                    pos, px = 1, c
                elif c < lb[m]:
                    pos, px = -1, c
        jour_g.append((jours[k], g))
    s = pd.Series(dict(jour_g))
    tous = pd.Series(0.0, index=pd.DatetimeIndex(jours[(jours >= de) & (jours < a)]))
    tous.loc[s.index] = s.values
    ans = (tous.index[-1] - tous.index[0]).days / 365.25
    compo = float((1 + tous).prod() ** (1 / ans) - 1)
    return {"trades": len(trades), "brut_moyen_pct": float(np.mean(trades) * 100),
            "gain_simple_pct_an": float(tous.sum() / ans * 100), "gain_compose_pct_an": compo * 100,
            "rapport_annuel": float(tous.mean() / tous.std() * math.sqrt(252)),
            "par_annee_pct": {int(y): float(v * 100) for y, v in tous.groupby(tous.index.year).sum().items()}}


p("=== (i) bande de bruit S&P 500")
spx = spx_minutes()
out = {}
for nom, kw in {"papier: cible 2 %, levier max 4, sans frais": dict(cible=0.02, frais=0.0),
                "papier + frais SPY du papier (~0,006 % aller-retour)": dict(cible=0.02, frais=0.00006),
                "cible 2 % + frais fiche projet x1,25 (0,015 %)": dict(cible=0.02, frais=0.00015),
                "cible 2 % + frais FTMO réalistes US500 (~0,01 %)": dict(cible=0.02, frais=0.0001),
                "cible 1 % (taille du projet) + fiche x1,25": dict(cible=0.01, frais=0.00015),
                "2015-2021 cible 1 % sans frais": dict(cible=0.01, frais=0.0, a="2022-01-01"),
                "2015-2021 cible 1 % fiche x1,25": dict(cible=0.01, frais=0.00015, a="2022-01-01")}.items():
    out[nom] = bande(spx, **kw)
    p(nom, {k: (round(v, 3) if isinstance(v, float) else v) for k, v in out[nom].items() if k != "par_annee_pct"})
    p("   par année :", {k: round(v, 1) for k, v in out[nom]["par_annee_pct"].items()})
res["bande_bruit_independante"] = out
proj = pd.read_csv(RACINE / "collapsar" / "vie" / "bande_bruit" / "trades_apprentissage.csv", parse_dates=["jour"])
pu = proj[(proj["marche"] == "US500") & (proj["jour"] < "2022-01-01")]
res["bande_bruit_projet_US500_2015_2021"] = {"trades": len(pu), "brut_moyen_pct": float(pu["brut"].mean() * 100)}
p("projet US500 2015-2021 :", res["bande_bruit_projet_US500_2015_2021"])
del spx

# ====================================================================== (ii) cassure C2 du bitcoin (Dukascopy 15 min)
p("=== (ii) cassure C2 BTC")
b = pd.read_csv(RACINE / "data" / "fx_intraday" / "BTCUSD_M15.csv")
b["time"] = pd.to_datetime(b["time"])
b = b[(b["time"] < "2024-01-01")].drop_duplicates("time").set_index("time").sort_index()
b = b[(b[["open", "high", "low", "close"]] > 0).all(axis=1)]
b["j"] = b.index.normalize()
b["q"] = b.index.hour * 4 + b.index.minute // 15
cnt = b.groupby("j").size()
ok_j = cnt[(cnt >= 92) & (cnt.index.dayofweek < 5)].index
bb = b[b["j"].isin(ok_j)]
Cq = bb.pivot_table(index="j", columns="q", values="close").reindex(columns=range(96)).ffill(axis=1).bfill(axis=1)
Hq = bb.pivot_table(index="j", columns="q", values="high").reindex(columns=range(96)).fillna(Cq)
Lq = bb.pivot_table(index="j", columns="q", values="low").reindex(columns=range(96)).fillna(Cq)
jours = Cq.index
nj = len(jours)
Hh = Hq.to_numpy().reshape(nj, 24, 4).max(2).ravel()
Lh = Lq.to_numpy().reshape(nj, 24, 4).min(2).ravel()
Ch = Cq.to_numpy().reshape(nj, 24, 4)[:, :, 3].ravel()
haut = pd.Series(Hh).rolling(24).max().shift(1).to_numpy()
bas = pd.Series(Lh).rolling(24).min().shift(1).to_numpy()
clo = Cq.to_numpy()[:, 95]
sd = pd.Series(clo).pct_change().rolling(14).std().shift(1).to_numpy()
Cflat = Cq.to_numpy()
tr = []
for j in range(nj):
    pos, e = 0, 0.0
    for h in range(1, 24):
        g = j * 24 + h - 1
        if not (np.isfinite(haut[g]) and np.isfinite(bas[g])):
            continue
        c, mil = Ch[g], (haut[g] + bas[g]) / 2
        if pos == 1 and c < mil:
            tr.append((jours[j], 1, c / e - 1, sd[j])); pos = 0
        elif pos == -1 and c > mil:
            tr.append((jours[j], -1, c / e - 1, sd[j])); pos = 0
        if pos == 0 and h <= 22:
            if c > haut[g]:
                pos, e = 1, c
            elif c < bas[g]:
                pos, e = -1, c
    if pos:
        tr.append((jours[j], pos, Cflat[j, 94] / e - 1, sd[j]))    # sortie 23h45 = clôture de la bougie 23h30
t = pd.DataFrame(tr, columns=["jour", "sens", "r", "sd"]).dropna()
t = t[t["sd"] > 0]
out = {}
for per, (de, a) in {"choix 2017-05 -> 2021": ("2017-05-01", "2022-01-01"), "vérification 2022-2023": ("2022-01-01", "2024-01-01")}.items():
    tp = t[(t["jour"] >= de) & (t["jour"] < a)]
    jt = [j for j in jours if pd.Timestamp(de) <= j < pd.Timestamp(a)]
    mois = len(jt) / 261 * 12
    expo = np.minimum(1, 0.01 / tp["sd"])
    brut = tp["sens"] * tp["r"]
    o = {"trades": len(tp), "brut_moyen_pct": float(brut.mean() * 100),
         "force_non_ponderee": float(brut.mean() / brut.std() * math.sqrt(len(tp))),
         "force_ponderee_par_la_taille": float((expo * brut).mean() / (expo * brut).std() * math.sqrt(len(tp)))}
    for f in (0.0001, 0.001, 0.0008313 * 1.0):
        o[f"pct_mois_frais_{f * 100:.4f}%"] = float((expo * (brut - f)).sum() / mois * 100)
    out[per] = o
    p(per, {k: round(v, 3) for k, v in o.items()})
res["cassure_C2_independante"] = out

# ====================================================================== (iii) zones zones supply and demand H4 de l'or : décompte indépendant
p("=== (iii) zones zones supply and demand H4 de l'or")
g = pd.read_csv(RACINE / "data" / "kaggle_gold" / "XAU_1m_data.csv", sep=";")
g.columns = [c.lower() for c in g.columns]
g["ny"] = pd.to_datetime(g["date"], format="%Y.%m.%d %H:%M") - pd.Timedelta(hours=7)
g = g[(g["ny"] >= "2014-11-20") & (g["ny"] < "2024-01-01")].set_index("ny")
h4 = g.resample("4h", label="left", closed="left").agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
o_, h_, l_, c_ = (h4[k].to_numpy() for k in ("open", "high", "low", "close"))
haus, bais = 0, 0
for i in range(5, len(c_)):
    j = i - 1
    if c_[j] < o_[j] and l_[j] > h_[j - 2] and c_[i] > max(h_[i - 4], h_[i - 5]):
        haus += 1
    if c_[j] > o_[j] and h_[j] < l_[j - 2] and c_[i] < min(l_[i - 4], l_[i - 5]):
        bais += 1
from collapsar.regarder.smc.nono import zones_nono                    # comparaison seulement
zh, zb, zm, zs, zc = zones_nono(o_, h_, l_, c_)
res["zones_nono_or_H4_2015_2023"] = {"bougies_H4": len(c_), "independant_hausse": haus, "independant_baisse": bais,
                                    "projet_hausse": int((zs > 0).sum()), "projet_baisse": int((zs < 0).sum())}
p(res["zones_nono_or_H4_2015_2023"])
(OUT / "t5_replication.json").write_text(json.dumps(res, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
p("FINI")
