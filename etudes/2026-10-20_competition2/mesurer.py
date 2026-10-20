"""Compétition 2 : M1 momentum relatif, M2 modèle linéaire commun, M3 exposition gérée par la volatilité (PLAN_FIGE.md).
COFFRE (2024 ->) jamais chargé. Lancement UNIQUE (verrou).

    venv_gpu\\Scripts\\python.exe etudes\\2026-10-20_competition2\\mesurer.py
"""
from __future__ import annotations

import json
import math
import subprocess
import sys
import time
from pathlib import Path

ICI = Path(__file__).resolve().parent
RACINE = ICI.parents[1]
sys.path.insert(0, str(RACINE))

import numpy as np
import pandas as pd

from cerveau.mesure import portefeuille as PF

FIN_LUE = pd.Timestamp("2024-01-01")
DEVISES = ["EURUSD", "GBPUSD", "AUDUSD", "NZDUSD", "USDJPY", "USDCHF", "USDCAD"]
AUTRES = ["XAUUSD", "USA500IDXUSD", "USATECHIDXUSD", "USA30IDXUSD"]
UNIVERS = DEVISES + AUTRES
PERIODES = {"recherche": ("2012-01-01", "2020-01-01"), "validation": ("2020-01-01", "2024-01-01"),
            "total": ("2012-01-01", "2024-01-01")}
PERIODES_M2 = {"recherche": ("2013-01-01", "2020-01-01"), "validation": ("2020-01-01", "2024-01-01"),
               "total": ("2013-01-01", "2024-01-01")}
RES = ICI / "resultats"
VERROU = RES / "VERROU.json"
GIT = r"C:\Users\utilisateur\AppData\Local\GitHubDesktop\app-3.6.6\resources\app\git\cmd\git.exe"


def mercredis_pairs(jours: pd.DatetimeIndex) -> pd.DatetimeIndex:
    """Un mercredi sur deux (semaine ISO paire) : les jours de décision de M1 et M3."""
    m = jours[jours.dayofweek == 2]
    return m[np.asarray(m.isocalendar().week) % 2 == 0]


# ------------------------------------------------------------------------------------------------ M1
def m1(u: PF.Univers) -> dict:
    """Par période de 2 semaines : chaque jambe paie entrée + sortie (rotation complète, signal ET juges)."""
    dec = mercredis_pairs(u.jours)
    idx = u.jours.get_indexer(dec)
    lr = u.lr
    score = (lr.rolling(252, min_periods=240).sum() - lr.rolling(21, min_periods=20).sum()) / u.vol
    hist = u.dispo.cumsum() >= 273                                        # 13 mois d'historique
    r, df = u.r.to_numpy(), u.demi_frais.to_numpy()
    ach = (u.achat.to_numpy() / 360 * u.nuits.to_numpy())
    ven = (u.vente.to_numpy() / 360 * u.nuits.to_numpy())
    lignes = []
    for a, b in zip(idx[:-1], idx[1:]):
        s = score.iloc[a]
        ok = s.notna() & hist.iloc[a] & u.dispo.iloc[a] & u.vol.iloc[a].notna()
        noms = s[ok].index
        nb = len(noms)
        if nb < 4:
            continue
        k = math.ceil(nb / 4)
        ordre = s[noms].sort_values()
        longs, shorts = set(ordre.index[-k:]), set(ordre.index[:k])
        mt = u.montant_vol(0.10, math.sqrt(2 * k)).iloc[a]
        for nom in noms:
            j = u.marches.index(nom)
            n = mt[nom]
            brut = n * r[a + 1:b + 1, j].sum()
            couts = n * (df[a, j] + df[b, j])
            g_long = brut - couts - n * ach[a + 1:b + 1, j].sum()
            g_short = -brut - couts - n * ven[a + 1:b + 1, j].sum()
            choix = 1 if nom in longs else (-1 if nom in shorts else 0)
            g15_l = g_long - 0.5 * couts
            g15_s = g_short - 0.5 * couts
            lignes.append((u.jours[b], nom, choix, g_long, g_short, g15_l, g15_s, k / nb))
    t = pd.DataFrame(lignes, columns=["fin", "marche", "choix", "long", "short", "long15", "short15", "proba"])
    t["signal"] = np.where(t["choix"] > 0, t["long"], np.where(t["choix"] < 0, t["short"], 0.0))
    t["signal15"] = np.where(t["choix"] > 0, t["long15"], np.where(t["choix"] < 0, t["short15"], 0.0))
    t["tirage"] = t["proba"] * (t["long"] + t["short"])                   # espérance exacte du tirage au hasard
    t["pile"] = np.where(t["choix"] != 0, (t["long"] + t["short"]) / 2, 0.0)
    t["fin"] = pd.to_datetime(t["fin"])
    out = {}
    for nom, (a, b) in PERIODES.items():
        x = t[(t["fin"] >= a) & (t["fin"] < b)]
        per = x.groupby("fin")[["signal", "signal15", "tirage", "pile"]].sum()
        per.index = pd.DatetimeIndex(per.index)
        mens = PF.mensuel(per["signal"])
        res = {"periodes_2_semaines": int(len(per)), "jambes": int((x["choix"] != 0).sum()),
               "gain_pct_mois": float(mens.mean() / PF.CAPITAL * 100),
               "gain_pct_mois_frais_x1_5": float(PF.mensuel(per["signal15"]).mean() / PF.CAPITAL * 100),
               "pire_periode_pct": float(per["signal"].min() / PF.CAPITAL * 100),
               "contre_tirage": PF.avantage(mens, PF.mensuel(per["tirage"])),
               "contre_pile_ou_face": PF.avantage(mens, PF.mensuel(per["pile"]))}
        for grp, noms in (("devises", DEVISES), ("autres", AUTRES)):
            y = x[x["marche"].isin(noms)].groupby("fin")[["signal", "tirage"]].sum()
            y.index = pd.DatetimeIndex(y.index)
            res[f"contre_tirage_{grp}"] = PF.avantage(PF.mensuel(y["signal"]), PF.mensuel(y["tirage"]))
        out[nom] = res
    return out


# ------------------------------------------------------------------------------------------------ M2
def m2(u: PF.Univers) -> dict:
    lr = u.lr
    vol = u.vol
    feats = {}
    for h in (1, 5, 21, 63, 126, 252):
        feats[h] = lr.rolling(h, min_periods=h).sum() / (vol * math.sqrt(h))
    cible = (lr.shift(-1) / vol).clip(-5, 5)
    long_ = []
    for nom in u.marches:
        df_ = pd.DataFrame({f"f{h}": feats[h][nom] for h in feats})
        df_["y"] = cible[nom]
        df_["marche"] = nom
        long_.append(df_)
    tab = pd.concat(long_)
    X_cols = [f"f{h}" for h in feats]
    prev = pd.DataFrame(np.nan, index=u.jours, columns=u.marches)
    for annee in range(2013, 2024):
        debut = pd.Timestamp(f"{annee}-01-01")
        app = tab[(tab.index < debut - pd.Timedelta(days=2))].dropna()
        X, y = app[X_cols].to_numpy(), app["y"].to_numpy()
        w = np.linalg.solve(X.T @ X + 1.0 * np.eye(X.shape[1]), X.T @ y)      # ridge alpha = 1, sans constante
        jug = tab[(tab.index >= debut) & (tab.index < pd.Timestamp(f"{annee + 1}-01-01"))]
        Xj = jug[X_cols].to_numpy()
        p = Xj @ w
        for nom in u.marches:
            m = (jug["marche"] == nom).to_numpy() & np.isfinite(p)
            prev.loc[jug.index[m], nom] = p[m]
    seuil = (2 * u.demi_frais) / vol                                          # frais aller-retour en volatilités
    mt = u.montant_vol(0.10, math.sqrt(len(u.marches)))
    sens = np.sign(prev).where(prev.abs() > seuil, 0.0)
    cible_pos = (sens * mt).where(prev.notna())                                # NaN = garder (pas de prévision)
    sig = u.simuler(cible_pos)
    sig15 = u.simuler(cible_pos, 1.5)
    inv = u.simuler(-cible_pos)
    acheteur = u.simuler(mt.where(prev.notna()))
    out = {}
    for nom, (a, b) in PERIODES_M2.items():
        g = sig["gain"].sum(1)
        res = PF.resume(g, sig["ouvertures"], a, b, sig15["gain"].sum(1))
        ms = PF.mensuel(PF.periode(g, a, b))
        pile = (g + inv["gain"].sum(1)) / 2
        res["contre_pile_ou_face"] = PF.avantage(ms, PF.mensuel(PF.periode(pile, a, b)))
        res["contre_acheteur_risque_egal"] = PF.avantage(ms, PF.mensuel(PF.periode(acheteur["gain"].sum(1), a, b)),
                                                         risque_egal=True)
        res["part_du_temps_en_position_pct"] = float(100 * (PF.periode(sig["pos"], a, b) != 0).to_numpy().mean())
        for grp, noms in (("devises", DEVISES), ("autres", AUTRES)):
            gs = PF.mensuel(PF.periode(sig["gain"][noms].sum(1), a, b))
            gp = PF.mensuel(PF.periode((sig["gain"][noms].sum(1) + inv["gain"][noms].sum(1)) / 2, a, b))
            res[f"contre_pile_{grp}"] = PF.avantage(gs, gp)
        out[nom] = res
    return out


# ------------------------------------------------------------------------------------------------ M3
def m3(marche: str) -> dict:
    u = PF.Univers([marche], FIN_LUE)
    dec = mercredis_pairs(u.jours)
    var21 = u.lr.rolling(21, min_periods=21).var()[marche] * 252
    vol21 = np.sqrt(var21)
    geree = (PF.CAPITAL * 0.10 ** 2 / var21).clip(upper=300_000)
    inv_vol = (PF.CAPITAL * 0.10 / vol21).clip(upper=300_000)
    def cible(serie):
        c = pd.DataFrame(np.nan, index=u.jours, columns=[marche])
        c.loc[dec, marche] = serie.reindex(dec).to_numpy()
        return c
    sig = u.simuler(cible(geree))
    sig15 = u.simuler(cible(geree), 1.5)
    constant = u.simuler(cible(pd.Series(PF.CAPITAL, index=u.jours)))
    juge2 = u.simuler(cible(inv_vol))
    out = {}
    for nom, (a, b) in PERIODES.items():
        g = sig["gain"][marche]
        res = PF.resume(g, sig["ouvertures"], a, b, sig15["gain"][marche])
        ms = PF.mensuel(PF.periode(g, a, b))
        res["contre_montant_constant_risque_egal"] = PF.avantage(ms, PF.mensuel(PF.periode(constant["gain"][marche], a, b)),
                                                                 risque_egal=True)
        res["contre_taille_vol_risque_egal"] = PF.avantage(ms, PF.mensuel(PF.periode(juge2["gain"][marche], a, b)),
                                                           risque_egal=True)
        res["montant_moyen"] = float(PF.periode(sig["pos"][marche], a, b).mean())
        out[nom] = res
    return out


def criteres(r1, r2, r3) -> dict:
    def deux(p, cle):
        t = p["total"][cle]
        return t["avantage_pct_mois"] > 2 * t["incertitude"] and p["recherche"][cle]["avantage_pct_mois"] > 0 \
            and p["validation"][cle]["avantage_pct_mois"] > 0
    c = {}
    x = {"1_gain_positif_recherche_et_validation": r1["recherche"]["gain_pct_mois"] > 0 and r1["validation"]["gain_pct_mois"] > 0,
         "2_bat_le_tirage": deux(r1, "contre_tirage"),
         "3_bat_pile_ou_face": r1["total"]["contre_pile_ou_face"]["avantage_pct_mois"] > 0,
         "4_robuste_devises_et_autres": r1["total"]["contre_tirage_devises"]["avantage_pct_mois"] > 0
                                        and r1["total"]["contre_tirage_autres"]["avantage_pct_mois"] > 0,
         "5_frais_x1_5": r1["total"]["gain_pct_mois_frais_x1_5"] > 0,
         "6_assez_de_positions_et_activite": r1["total"]["jambes"] >= 100}
    x["CANDIDATE"] = all(x.values())
    c["M1_momentum_relatif"] = x
    x = {"1_gain_positif_recherche_et_validation": r2["recherche"]["gain_pct_mois"] > 0 and r2["validation"]["gain_pct_mois"] > 0,
         "2_bat_pile_ou_face": deux(r2, "contre_pile_ou_face"),
         "3_bat_acheteur_risque_egal": r2["total"]["contre_acheteur_risque_egal"]["avantage_pct_mois"] > 0,
         "4_robuste_devises_et_autres": r2["total"]["contre_pile_devises"]["avantage_pct_mois"] > 0
                                        and r2["total"]["contre_pile_autres"]["avantage_pct_mois"] > 0,
         "5_frais_x1_5": r2["total"]["gain_pct_mois_frais_x1_5"] > 0,
         "6_assez_de_positions_et_activite": r2["total"]["jours_ouverture"] >= 100
                                             and r2["total"]["plus_long_sans_ouvrir_jours"] <= 30}
    x["CANDIDATE"] = all(x.values())
    c["M2_modele_lineaire"] = x
    p = r3["USA500IDXUSD"]
    x = {"1_gain_positif_recherche_et_validation": p["recherche"]["gain_pct_mois"] > 0 and p["validation"]["gain_pct_mois"] > 0,
         "2_bat_montant_constant": deux(p, "contre_montant_constant_risque_egal"),
         "3_bat_taille_vol": p["total"]["contre_taille_vol_risque_egal"]["avantage_pct_mois"] > 0,
         "4_robuste": sum(r3[m]["total"]["contre_montant_constant_risque_egal"]["avantage_pct_mois"] > 0
                          for m in ("USATECHIDXUSD", "XAUUSD")) >= 1,
         "5_frais_x1_5": p["total"]["gain_pct_mois_frais_x1_5"] > 0,
         "6_assez_de_positions_et_activite": p["total"]["jours_ouverture"] >= 100
                                             and p["total"]["plus_long_sans_ouvrir_jours"] <= 30}
    x["CANDIDATE"] = all(x.values())
    c["M3_volatilite_geree"] = x
    return c


def main():
    RES.mkdir(exist_ok=True)
    if VERROU.exists():
        raise SystemExit(f"déjà lancé : {VERROU.read_text(encoding='utf-8')}")
    commit = subprocess.run([GIT, "rev-parse", "HEAD"], capture_output=True, text=True, cwd=RACINE).stdout.strip()
    sale = subprocess.run([GIT, "status", "--porcelain", "--", "cerveau", "core", str(ICI.relative_to(RACINE))],
                          capture_output=True, text=True, cwd=RACINE).stdout.strip()
    VERROU.write_text(json.dumps({"lance": time.strftime("%d/%m/%Y %H:%M:%S"), "commit": commit,
                                  "modifs_non_commitees": sale}, ensure_ascii=False, indent=1), encoding="utf-8")
    u = PF.Univers(UNIVERS, FIN_LUE)
    print(f"univers : {len(u.jours)} jours, {u.jours[0].date()} -> {u.jours[-1].date()}", flush=True)
    r1 = m1(u)
    print("M1 fait", flush=True)
    r2 = m2(u)
    print("M2 fait", flush=True)
    r3 = {m: m3(m) for m in ("USA500IDXUSD", "USATECHIDXUSD", "XAUUSD")}
    sortie = {"M1": r1, "M2": r2, "M3": r3, "criteres": criteres(r1, r2, r3)}
    (RES / "competition2.json").write_text(json.dumps(sortie, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    for per in ("recherche", "validation", "total"):
        x = r1[per]
        print(f"M1 {per:>10} : {x['gain_pct_mois']:+.3f} %/mois (x1,5 {x['gain_pct_mois_frais_x1_5']:+.3f}) | tirage "
              f"{x['contre_tirage']['avantage_pct_mois']:+.3f} ± {x['contre_tirage']['incertitude']:.3f} | devises "
              f"{x['contre_tirage_devises']['avantage_pct_mois']:+.3f} autres {x['contre_tirage_autres']['avantage_pct_mois']:+.3f}"
              f" | {x['jambes']} jambes", flush=True)
    for per in ("recherche", "validation", "total"):
        x = r2[per]
        print(f"M2 {per:>10} : {x['gain_pct_mois']:+.3f} %/mois (x1,5 {x['gain_pct_mois_frais_x1_5']:+.3f}) | pile "
              f"{x['contre_pile_ou_face']['avantage_pct_mois']:+.3f} ± {x['contre_pile_ou_face']['incertitude']:.3f} | "
              f"acheteur risque égal {x['contre_acheteur_risque_egal']['avantage_pct_mois']:+.3f} | en position "
              f"{x['part_du_temps_en_position_pct']:.0f} % | sans ouvrir max {x['plus_long_sans_ouvrir_jours']:.0f} j",
              flush=True)
    for m, r in r3.items():
        for per in ("recherche", "validation", "total"):
            x = r[per]
            print(f"M3 {m:>13} {per:>10} : {x['gain_pct_mois']:+.3f} %/mois | constant risque égal "
                  f"{x['contre_montant_constant_risque_egal']['avantage_pct_mois']:+.3f} ± "
                  f"{x['contre_montant_constant_risque_egal']['incertitude']:.3f} | taille vol "
                  f"{x['contre_taille_vol_risque_egal']['avantage_pct_mois']:+.3f} | pire baisse {x['pire_baisse_pct']:.1f} %",
                  flush=True)
    for h, c in sortie["criteres"].items():
        print(h, c, flush=True)


if __name__ == "__main__":
    main()
