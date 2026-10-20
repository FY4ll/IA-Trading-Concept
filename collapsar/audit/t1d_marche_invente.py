"""AUDIT 1(d) : marchés INVENTÉS (loi connue) passés dans les moteurs du projet.
- tendance forte (+80 %/an, agitation 15 %/an) : la cassure C2 et les zones V1 du chef DOIVENT gagner ;
- tendance forte à la baisse (-80 %/an) : même chose dans l'autre sens (contrôle du signe) ;
- hasard pur (dérive 0) : le gain AVANT frais doit être ~0 ; un écart = biais des conventions d'exécution.
Depuis Test_IA : venv_gpu\\Scripts\\python.exe -u -m collapsar.audit.t1d_marche_invente
"""
import json
import math

import numpy as np
import pandas as pd

from collapsar.donnees import marches as dm
from collapsar.audit.t3_execution import tiers_minute
from collapsar.regarder.pistes import bitcoin_journee as BJ
from collapsar.regarder.smc import gigogne as G
from collapsar.regarder.smc import noyaux as K
from collapsar.regarder.smc.bougies import bougies
from collapsar.regarder.smc.nono import TENUE_JOURS, trade_nono

OUT = dm.RACINE / "collapsar" / "vie" / "audit"
FRAIS = 0.00012
import os
DEB, FIN = "2016-01-04", os.environ.get("AUDIT_FIN", "2019-01-01")
DERIVE = float(os.environ.get("AUDIT_DERIVE", "0.8"))


def minutes_inventees(derive_an: float, vol_an: float, graine: int) -> pd.DataFrame:
    t = pd.date_range(DEB, FIN, freq="1min", inclusive="left").astype("datetime64[ns]")   # le labo compte en ns
    n, sub = len(t), 5
    rng = np.random.default_rng(graine)
    s = vol_an / math.sqrt(525600 * sub)
    mu = derive_an / (525600 * sub) - 0.5 * s * s
    x = np.cumsum(mu + s * rng.standard_normal(n * sub)).reshape(n, sub)
    lp = np.log(1000.0) + x
    debut = np.r_[np.log(1000.0), lp[:-1, -1]]
    o = np.exp(debut)
    h = np.exp(np.maximum(lp.max(1), debut))
    l = np.exp(np.minimum(lp.min(1), debut))
    c = np.exp(lp[:, -1])
    return pd.DataFrame({"ny": t, "open": o, "high": h, "low": l, "close": c, "volume": 1.0})


def zones_v1(m1: pd.DataFrame) -> pd.DataFrame:
    cons = lambda u: bougies("INVENTE", u, pd.Timestamp(FIN), m1, frais=FRAIS, facteur_ouverture=1.0, volume_inclus=True)
    P = G.preparer(cons, G.ECHELLE_45)
    B, Z = P["B"], P["Z"]
    s_px, s_ty, s_t = P["sommets"]
    BD = B["D1"]
    xh, xb, xm, xs, xconf, xfin = Z["H4"]
    lignes = []
    for e in G.entrees(P, "H4"):
        BY, i, d = B[e["unite"]], e["i"], e["sens"]
        entree = e["entree"]
        t_e = BY.bt[i]
        jd = int(np.searchsorted(BD.bt, t_e, "right")) - 2
        atr_jour = BD.atr[jd] if jd >= 0 else np.nan
        risque = max(e["risque_zone"], 0.2 * atr_jour)
        if not np.isfinite(risque):
            continue
        okx = (xs == -d) & (xconf < t_e) & (xfin > t_e)
        dist3 = ((xb if d > 0 else xh)[okx] - entree) * d
        dist3 = dist3[dist3 >= 2 * risque]
        if not len(dist3):
            continue
        d3 = float(dist3.min())
        cand = (s_ty == d) & (s_t <= t_e)
        d2s = (s_px[cand] - entree) * d
        d2s = d2s[(d2s > 2 * risque) & (d2s < d3)]
        d2 = float(d2s.min()) if len(d2s) else (2 * risque + d3) / 2
        f_min, b_min = K._remplissage(BY.o, BY.mt, BY.ml, BY.mh, BY.bt, BY.duree, i, d, e["milieu"])
        tenue = int(TENUE_JOURS * 86400e9 // BY.duree)
        fin = min(BY.n - 1, i + tenue)
        lig = {"sens": d, "unite": e["unite"]}
        for nom, s in (("", d), ("_inv", -d)):
            r, cr = trade_nono(BY.o, BY.h, BY.l, BY.c, BY.mo, BY.mh, BY.ml, i, f_min, b_min, s, entree, risque, d2, d3,
                               False, tenue, BY.frais, BY.facteur[i])
            cibles = np.array([entree + s * 2.0 * risque, entree + s * d2, entree + s * d3])
            rm, _ = tiers_minute(BY.mt, BY.mo, BY.mh, BY.ml, f_min + 1, BY.bt[fin] + BY.duree, s, entree, risque,
                                 cibles, BY.frais, BY.facteur[i], BY.c[fin])
            lig[f"R{nom}"], lig[f"Rm{nom}"], lig[f"cout{nom}"] = r, rm, cr
        lignes.append(lig)
    return pd.DataFrame(lignes)


def cassure_c2(m1: pd.DataFrame) -> dict:
    q = m1.set_index("ny").resample("15min").agg({"open": "first", "high": "max", "low": "min", "close": "last"})
    jours = pd.DatetimeIndex(sorted(q.index.normalize().unique()))
    k = (q.index.hour * 4 + q.index.minute // 15).to_numpy()
    i = ((q.index.normalize() - jours[0]).days).to_numpy()
    O, H, L, C = (np.full((len(jours), 96), np.nan) for _ in range(4))
    for X, col in ((O, "open"), (H, "high"), (L, "low"), (C, "close")):
        X[i, k] = q[col].to_numpy()
    m = {"O": O, "H": H, "L": L, "C": C, "valide": np.ones(len(jours), bool), "jours": jours,
         "off": np.full(len(jours), 9)}
    agit = BJ.agitation(m)
    t = BJ.trades(m, BJ.var_C(m, 24), agit)
    brut = t["sens"] * t["r_prix"]
    g, _ = BJ.journalier(t, FRAIS * 1.25, 0.01)
    mois = len(jours) / 30.44
    return {"trades": len(t), "achats_pct": float((t["sens"] > 0).mean() * 100), "brut_moyen_pct": float(brut.mean() * 100),
            "force": float(brut.mean() / brut.std() * math.sqrt(len(t))), "pct_mois_cible1": float(g.sum() / mois * 100)}


def main():
    res = {}
    for nom, derive, graine in ((f"tendance +{DERIVE:.0%}/an", DERIVE, 11), (f"tendance -{DERIVE:.0%}/an", -DERIVE, 12), ("hasard pur", 0.0, 13),
                                ("hasard pur (2e tirage)", 0.0, 14)):
        m1 = minutes_inventees(derive, 0.15, graine)
        c2 = cassure_c2(m1)
        z = zones_v1(m1)
        dd = (z["R"] - z["R_inv"]) / 2
        out = {"prix_debut_fin": [float(m1["close"].iloc[0]), float(m1["close"].iloc[-1])], "cassure_C2": c2,
               "zones_V1": {"trades": len(z), "achats_pct": float((z["sens"] > 0).mean() * 100),
                            "R_moyen_projet": float(z["R"].mean()), "R_moyen_minute": float(z["Rm"].mean()),
                            "R_avant_frais_projet": float((z["R"] + z["cout"]).mean()),
                            "R_avant_frais_minute": float((z["Rm"] + z["cout"]).mean()),
                            "R_achats": float(z.loc[z["sens"] > 0, "R"].mean()) if (z["sens"] > 0).any() else None,
                            "R_ventes": float(z.loc[z["sens"] < 0, "R"].mean()) if (z["sens"] < 0).any() else None,
                            "force_jumeau": float(dd.mean() / dd.std() * math.sqrt(len(z))) if len(z) > 2 else None,
                            "cout_R_moyen": float(z["cout"].mean())}}
        res[nom] = out
        print(nom, json.dumps(out, default=float, ensure_ascii=False), flush=True)
        del m1
    (OUT / f"t1d_marche_invente_{FIN[:4]}.json").write_text(json.dumps(res, ensure_ascii=False, indent=1, default=float), encoding="utf-8")


if __name__ == "__main__":
    main()

