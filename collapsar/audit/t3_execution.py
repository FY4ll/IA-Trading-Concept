"""AUDIT 3 : exécution du labo SMC (V1 du chef, « Gigogne H4 stop A plancher 0.2 ») sur les 4 marchés à la minute.
(a) stop et objectif dans la même bougie : le projet suppose le stop -> on refait CHAQUE trade minute par minute ;
(b) ordre limite rempli au simple contact : part des trades où le prix n'a fait que toucher le niveau ;
(d) minutes manquantes.
Depuis Test_IA : venv_gpu\\Scripts\\python.exe -u -m collapsar.audit.t3_execution
"""
import json
import math

import numpy as np
import pandas as pd
from numba import njit

from collapsar.donnees import marches as dm
from collapsar.regarder.smc import gigogne as G
from collapsar.regarder.smc import noyaux as K
from collapsar.regarder.smc.bougies import MARCHES, bougies, minutes
from collapsar.regarder.smc.nono import TENUE_JOURS, trade_nono

OUT = dm.RACINE / "collapsar" / "vie" / "audit"
FIN = pd.Timestamp("2024-01-01")
PLANCHER = 0.2


@njit(cache=True)
def tiers_minute(mt, mo, mh, ml, k0, t_fin, sens, entree, risque, cibles, frais, facteur, c_fin):
    """Même règle que trade_nono (stop A, tiers), mais TOUT le parcours à la minute. Rend (R, minutes ambiguës)."""
    stop = entree - sens * risque
    ouvert = np.array([True, True, True])
    gain = 0.0
    cout = entree * frais * 0.5 * facteur
    amb = 0
    k = k0
    n = len(mt)
    while k < n and mt[k] < t_fin:
        st = (sens > 0 and ml[k] <= stop) or (sens < 0 and mh[k] >= stop)
        if st:
            for q in range(3):
                if ouvert[q] and ((sens > 0 and mh[k] >= cibles[q]) or (sens < 0 and ml[k] <= cibles[q])):
                    amb += 1
            px = min(stop, mo[k]) if sens > 0 else max(stop, mo[k])
            for q in range(3):
                if ouvert[q]:
                    gain += (px - entree) * sens / 3.0
                    cout += entree * frais / 3.0
                    ouvert[q] = False
            return (gain - cout) / risque, amb
        for q in range(3):
            if ouvert[q] and ((sens > 0 and mh[k] >= cibles[q]) or (sens < 0 and ml[k] <= cibles[q])):
                px = max(cibles[q], mo[k]) if sens > 0 else min(cibles[q], mo[k])
                gain += (px - entree) * sens / 3.0
                cout += entree * frais * 0.5 / 3.0
                ouvert[q] = False
        if not (ouvert[0] or ouvert[1] or ouvert[2]):
            return (gain - cout) / risque, amb
        k += 1
    for q in range(3):
        if ouvert[q]:
            gain += (c_fin - entree) * sens / 3.0
            cout += entree * frais * 0.5 / 3.0
    return (gain - cout) / risque, amb


def un_marche(marche: str, ns: bool = True):
    """`ns` : heures converties en nanosecondes (ce que le labo suppose). False = tel que lu par pandas 3 (µs)."""
    m1 = minutes(marche)
    m1 = m1[m1["ny"] < FIN]
    if ns:
        m1 = m1.assign(ny=m1["ny"].astype("datetime64[ns]"))
    cons = lambda u: bougies(marche, u, FIN, m1)
    P = G.preparer(cons, G.ECHELLE_MINUTES)
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
        risque = max(e["risque_zone"], PLANCHER * atr_jour)
        if not np.isfinite(risque):
            continue
        okx = (xs == -d) & (xconf < t_e) & (xfin > t_e)
        bords = (xb if d > 0 else xh)[okx]
        dist3 = (bords - entree) * d
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
        t_fin = BY.bt[fin] + BY.duree
        ligne = {"marche": marche, "entree": pd.Timestamp(BY.t[i]), "unite": e["unite"], "sens": d, "prix": entree,
                 "stop_pct": risque / entree * 100}
        for nom, s in (("", d), ("_inv", -d)):
            cibles = np.array([entree + s * 2.0 * risque, entree + s * d2, entree + s * d3])
            r, _ = trade_nono(BY.o, BY.h, BY.l, BY.c, BY.mo, BY.mh, BY.ml, i, f_min, b_min, s, entree, risque, d2, d3,
                              False, tenue, BY.frais, BY.facteur[i])
            rm, amb = tiers_minute(BY.mt, BY.mo, BY.mh, BY.ml, f_min + 1, t_fin, s, entree, risque, cibles, BY.frais,
                                   BY.facteur[i], BY.c[fin])
            ligne[f"R_projet{nom}"] = r
            ligne[f"R_minute{nom}"] = rm
            ligne[f"amb_minute{nom}"] = amb
        # (b) remplissage au simple contact : de combien le prix a-t-il dépassé le niveau dans la bougie d'entrée ?
        a_, b_ = K._minutes_de_la_bougie(BY.mt, BY.bt[i], BY.duree)
        if b_ <= a_:
            depasse = np.nan
        elif d > 0:
            depasse = e["milieu"] - BY.ml[a_:b_].min()
        else:
            depasse = BY.mh[a_:b_].max() - e["milieu"]
        # 2e chance : le dépassement maximal pendant les 200 bougies d'attente suivantes (un ordre réel non rempli au
        # contact pourrait l'être plus tard)
        ligne["depassement_pct_prix"] = depasse / entree * 100
        ligne["demi_frais_pct_prix"] = BY.frais / 2 * 100
        lignes.append(ligne)
    t = pd.DataFrame(lignes)
    # (d) minutes manquantes dans la séance de New York (9h30-16h, jours de semaine)
    ny = m1["ny"]
    rth = m1[(ny.dt.dayofweek < 5) & ((ny.dt.hour * 60 + ny.dt.minute) >= 570) & ((ny.dt.hour * 60 + ny.dt.minute) < 960)]
    jours = rth["ny"].dt.normalize().nunique()
    manque = 1 - len(rth) / (jours * 390) if jours else np.nan
    return t, manque


def main():
    parts, manques, brut = [], {}, []
    for mk in MARCHES:
        t, mq = un_marche(mk, ns=True)
        manques[mk] = mq
        parts.append(t)
        print(mk, len(t), "trades (heures en ns) ; minutes manquantes en séance NY :", round(mq * 100, 2), "%", flush=True)
        tb, _ = un_marche(mk, ns=False)
        brut.append(tb)
        print(mk, len(tb), "trades (tel que le projet, heures en µs)", flush=True)
    t = pd.concat(parts, ignore_index=True)
    tb = pd.concat(brut, ignore_index=True)
    t.to_csv(OUT / "t3_trades_v1_minute.csv", index=False)
    tb.to_csv(OUT / "t3_trades_v1_tel_quel_us.csv", index=False)
    res = {"minutes_manquantes_seance_pct": {k: v * 100 for k, v in manques.items()}}
    # comparaison avec le fichier du projet (plancher 0.2, 4 marchés minutes)
    pj = pd.read_csv(dm.RACINE / "collapsar" / "vie" / "smc" / "plancher_trades_2015_2023.csv", parse_dates=["entree"])
    pj = pj[(pj["concept"] == "Gigogne H4 stop A plancher 0.2") & pj["groupe"].str.startswith("4")]
    for nom, x, col in (("fichier du projet", pj, "R"), ("rejoué tel quel (µs)", tb, "R_projet"),
                        ("corrigé (ns), moteur du projet", t, "R_projet"), ("corrigé (ns), moteur minute", t, "R_minute")):
        x = x[x["entree"] < FIN]
        inv = {"R": "R_inverse", "R_projet": "R_projet_inv", "R_minute": "R_minute_inv"}[col]
        dd = (x[col] - x[inv]) / 2
        res[f"V1 4 marchés 2015-2023 : {nom}"] = {"trades": len(x), "R_moyen": float(x[col].mean()),
                                                  "force": float(dd.mean() / dd.std() * math.sqrt(len(x)))}
        print(nom, res[f"V1 4 marchés 2015-2023 : {nom}"], flush=True)
    for per, (a, z) in {"2015-2021": (2015, 2021), "2022-2023": (2022, 2023), "2015-2023": (2015, 2023)}.items():
        g = t[(t["entree"].dt.year >= a) & (t["entree"].dt.year <= z)]
        dif = g["R_minute"] - g["R_projet"]
        dd_p = (g["R_projet"] - g["R_projet_inv"]) / 2
        dd_m = (g["R_minute"] - g["R_minute_inv"]) / 2
        touche_seul = (g["depassement_pct_prix"] < g["demi_frais_pct_prix"]).fillna(False)
        res[per] = {"trades": len(g), "R_projet": g["R_projet"].mean(), "R_minute": g["R_minute"].mean(),
                    "ecart_R_moyen": dif.mean(), "trades_changes_pct": float((dif.abs() > 1e-9).mean() * 100),
                    "force_projet": float(dd_p.mean() / dd_p.std(ddof=1) * math.sqrt(len(g))),
                    "force_minute": float(dd_m.mean() / dd_m.std(ddof=1) * math.sqrt(len(g))),
                    "minute_ambigue_pct": float((g["amb_minute"] > 0).mean() * 100),
                    "rempli_au_simple_contact_pct": float(touche_seul.mean() * 100),
                    "R_minute_si_contact_seul": float(g.loc[touche_seul, "R_minute"].mean()) if touche_seul.any() else None,
                    "R_minute_si_depasse": float(g.loc[~touche_seul, "R_minute"].mean()),
                    "R_minute_sans_les_contacts_seuls": float(g.loc[~touche_seul, "R_minute"].mean())}
        for mk in MARCHES:
            gm = g[g["marche"] == mk]
            res[per][mk] = {"trades": len(gm), "R_projet": gm["R_projet"].mean(), "R_minute": gm["R_minute"].mean()}
        print(per, json.dumps(res[per], default=float, ensure_ascii=False), flush=True)
    (OUT / "t3_execution.json").write_text(json.dumps(res, ensure_ascii=False, indent=1, default=float), encoding="utf-8")


if __name__ == "__main__":
    main()
