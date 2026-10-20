"""Mesures locales (lecture seule) sur les bougies M15 du projet :
saisonnalite intrajournaliere, jour de semaine, persistance de l'agitation,
prevision HAR sur volatilite issue des bougies, effet NFP, sauts > 4 sigma."""
import numpy as np, pandas as pd, os, sys, json

D = r"C:\Users\utilisateur\Documents\Test_IA\data"
FILES = {
    "EURUSD": D + r"\fx_intraday\EURUSD_M15.csv",
    "USDJPY": D + r"\fx_intraday\USDJPY_M15.csv",
    "GBPUSD": D + r"\fx_intraday\GBPUSD_M15.csv",
    "XAUUSD": D + r"\kaggle_gold\XAU_15m_data.csv",
    "XAGUSD": D + r"\fx_intraday\XAGUSD_M15.csv",
    "USA500": D + r"\fx_intraday\USA500IDXUSD_M15.csv",
    "DEU40": D + r"\fx_intraday\DEUIDXEUR_M15.csv",
    "WTI": D + r"\fx_intraday\LIGHTCMDUSD_M15.csv",
    "BTCUSD": D + r"\fx_intraday\BTCUSD_M15.csv",
}

def load(path):
    df = pd.read_csv(path, sep=None, engine="python") if "kaggle" in path else pd.read_csv(path)
    df.columns = [c.strip().lower() for c in df.columns]
    tcol = [c for c in df.columns if "time" in c or "date" in c][0]
    df["t"] = pd.to_datetime(df[tcol])
    df = df[["t", "open", "high", "low", "close"]].dropna().sort_values("t").drop_duplicates("t")
    df = df[(df.high >= df.low) & (df.low > 0)]
    return df.set_index("t")

def har_oos(y, h, start_frac=0.5):
    """y = log daily vol proxy (pd.Series). Target = mean of y over next h days.
    Expanding-window OLS re-estimated every 21 days. Returns OOS R2 vs expanding mean, and R2 of random walk."""
    d = y.values
    n = len(d)
    yd = d
    yw = pd.Series(d).rolling(5).mean().values
    ym = pd.Series(d).rolling(22).mean().values
    tgt = pd.Series(d).rolling(h).mean().shift(-h).values
    X = np.column_stack([np.ones(n), yd, yw, ym])
    ok = ~np.isnan(X).any(1) & ~np.isnan(tgt)
    idx = np.where(ok)[0]
    s = idx[int(len(idx) * start_frac)]
    preds, trues, bench, rw = [], [], [], []
    beta = None
    for k, i in enumerate(idx[idx >= s]):
        if beta is None or k % 21 == 0:
            tr = idx[idx <= i - h]
            beta = np.linalg.lstsq(X[tr], tgt[tr], rcond=None)[0]
            mu = tgt[tr].mean()
        preds.append(X[i] @ beta); trues.append(tgt[i]); bench.append(mu); rw.append(yd[i])
    p, t, b, r = map(np.array, (preds, trues, bench, rw))
    sse = ((t - p) ** 2).sum(); sst = ((t - b) ** 2).sum()
    return 1 - sse / sst, 1 - ((t - r) ** 2).sum() / sst, beta

def main():
    out = {}
    for name, path in FILES.items():
        if not os.path.exists(path):
            continue
        df = load(path)
        r = np.log(df.close).diff()
        gap = df.index.to_series().diff() != pd.Timedelta(minutes=15)
        r[gap] = np.nan  # pas de rendement a travers un trou (week-end, pause)
        df["r"] = r
        df["hl"] = np.log(df.high / df.low)
        df = df[df.hl.notna()]
        # bougies immobiles (marche ferme / pas de cotation) exclues
        act = df[(df.high > df.low)]
        res = {"debut": str(df.index[0].date()), "fin": str(df.index[-1].date()), "bougies": int(len(df))}
        # 1) saisonnalite par heure (heure du fichier), mesure = moyenne du range high-low de la bougie
        hr = act.groupby(act.index.hour)["hl"].mean()
        hr = hr[act.groupby(act.index.hour).size() > 0.3 * act.groupby(act.index.hour).size().max()]
        res["heure_pic"] = int(hr.idxmax()); res["heure_creux"] = int(hr.idxmin())
        res["ratio_pic_creux_range_horaire"] = round(float(hr.max() / hr.min()), 2)
        res["profil_horaire_rel"] = {int(k): round(float(v / hr.mean()), 2) for k, v in hr.items()}
        # 2) quotidien : range jour (H-L), RV jour (somme r^2 M15), Parkinson
        g = act.groupby(act.index.date)
        day = pd.DataFrame({"H": g.high.max(), "L": g.low.min(), "O": g.open.first(), "C": g.close.last(),
                            "rv": g.r.apply(lambda x: np.nansum(x ** 2)), "n": g.size()})
        day = day[day.n >= 0.6 * day.n.median()]
        day.index = pd.to_datetime(day.index)
        day["park"] = (np.log(day.H / day.L) ** 2) / (4 * np.log(2))
        u = np.log(day.H / day.O); dd = np.log(day.L / day.O); c = np.log(day.C / day.O)
        day["gk"] = 0.5 * (u - dd) ** 2 - (2 * np.log(2) - 1) * c ** 2
        day["cc"] = c ** 2
        day = day[(day.rv > 0) & (day.park > 0) & (day.gk > 0)]
        lrv = np.log(day.rv); lpk = np.log(day.park); lgk = np.log(day.gk)
        res["corr_log_parkinson_vs_log_RV15m"] = round(float(np.corrcoef(lpk, lrv)[0, 1]), 3)
        res["corr_log_GK_vs_log_RV15m"] = round(float(np.corrcoef(lgk, lrv)[0, 1]), 3)
        lcc = np.log(day.cc[day.cc > 0]); res["corr_log_ocsq_vs_log_RV15m"] = round(float(np.corrcoef(lcc, lrv[lcc.index])[0, 1]), 3)
        res["vol_annuelle_moy_%"] = round(float(np.sqrt(day.rv.mean() * 252) * 100), 1)
        res["vol_de_vol_ecart_type_log_vol_jour"] = round(float(np.std(0.5 * lrv)), 3)
        ac = {L: round(float(lrv.autocorr(L)), 3) for L in (1, 5, 22, 66)}
        res["autocorr_log_RV_jour"] = ac
        phi = lrv.autocorr(1)
        res["demi_vie_AR1_jours"] = round(float(np.log(0.5) / np.log(phi)), 1) if 0 < phi < 1 else None
        # lag where ACF drops below half of lag-1 ACF
        acf = [lrv.autocorr(L) for L in range(1, 250)]
        half = next((L + 1 for L, a in enumerate(acf) if a < 0.5 * acf[0]), None)
        res["lag_acf_moitie_de_acf1_jours"] = half
        # 3) prevision HAR hors echantillon (2e moitie), cible : log RV et log Parkinson, horizons 1 et 5 jours
        for lab, y in (("logRV", lrv), ("logParkinson", lpk)):
            for h in (1, 5):
                r2, r2rw, b = har_oos(y, h)
                res[f"HAR_R2_hors_ech_{lab}_h{h}"] = round(float(r2), 3)
                res[f"marche_aleatoire_R2_{lab}_h{h}"] = round(float(r2rw), 3)
        # 4) jour de semaine (range journalier moyen relatif)
        dw = np.sqrt(day.park).groupby(day.index.dayofweek).mean()
        res["range_jour_par_jour_semaine_rel"] = {int(k): round(float(v / dw.mean()), 2) for k, v in dw.items()}
        # 5) sauts : rendements M15 > 4 ecarts-types locaux (ecart-type = vol du jour precedent x profil horaire)
        prof = act.groupby(act.index.hour)["r"].apply(lambda x: np.sqrt(np.nanmean(x ** 2)))
        prof = prof / np.sqrt((prof ** 2).mean())
        dayvol = np.sqrt(day.rv / day.n).shift(1)  # vol par bougie, jour precedent
        a2 = act.copy(); a2["d"] = pd.to_datetime(a2.index.date)
        a2 = a2.join(dayvol.rename("dv"), on="d")
        a2["sig"] = a2.dv * a2.index.hour.map(prof).values
        z = (a2.r / a2.sig).replace([np.inf, -np.inf], np.nan).dropna()
        years = (df.index[-1] - df.index[0]).days / 365.25
        res["sauts_M15_sup_4sigma_par_an"] = round(float((z.abs() > 4).sum() / years), 1)
        res["sauts_M15_sup_6sigma_par_an"] = round(float((z.abs() > 6).sum() / years), 1)
        res["part_bougies_sup_4sigma_%"] = round(float((z.abs() > 4).mean() * 100), 3)
        res["kurtosis_z_M15"] = round(float(pd.Series(z).kurt()), 1)
        # quotidien : rendement jour > 4 sigma (sigma = EWMA centre de masse 60 j des RV passees)
        dr = np.log(day.C / day.O)
        ew = np.sqrt(day.rv.ewm(com=60).mean().shift(1))
        zd = (dr / ew).dropna()
        res["jours_sup_4sigma_par_an"] = round(float((zd.abs() > 4).sum() / years), 2)
        # indice de queue (Hill, 2,5 % plus grandes |z| M15)
        a = np.sort(np.abs(z.values))[::-1]; k = int(len(a) * 0.025)
        res["indice_queue_Hill_M15_top2.5%"] = round(float(1 / np.mean(np.log(a[:k] / a[k]))), 2)
        # 6) effet NFP approx. : 1er vendredi du mois ; heure de la bougie la plus agitee
        fri = act[(act.index.dayofweek == 4)]
        first = fri[fri.index.day <= 7]
        other = fri[fri.index.day > 7]
        slot = lambda x: x.index.hour * 4 + x.index.minute // 15
        m1 = first.groupby(slot(first))["hl"].mean(); m2 = other.groupby(slot(other))["hl"].mean()
        ratio = (m1 / m2).dropna()
        s0 = int(ratio.idxmax())
        res["NFP_bougie_max_heure_fichier"] = f"{s0 // 4:02d}:{(s0 % 4) * 15:02d}"
        res["NFP_ratio_range_bougie_vs_autres_vendredis"] = round(float(ratio.max()), 2)
        res["NFP_ratio_bougies_suivantes"] = [round(float(ratio.get(s0 + j, np.nan)), 2) for j in range(0, 13)]
        out[name] = res
        print(name, json.dumps(res, ensure_ascii=False), flush=True)
    json.dump(out, open(os.path.join(os.path.dirname(__file__), "mesures.json"), "w"), indent=1, ensure_ascii=False)

if __name__ == "__main__":
    main()
