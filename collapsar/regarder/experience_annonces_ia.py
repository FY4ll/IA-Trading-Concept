"""Expérience du 14/10 : l'IA APPREND elle-même quoi faire des surprises économiques (pas de règle « suivre »).

Situations : chaque marché (devises, indices, or, argent, pétrole...) à la clôture de la bougie d'une annonce
importante qui concerne une de ses devises (ou le dollar, qui fait bouger tout le monde).
Ce qu'elle voit : la surprise de l'annonce (taille, sens), son genre (taux, prix, emploi, activité, consommation,
autre), quelle devise du marché est concernée (achat ou vente du marché), la réaction déjà faite par le prix pendant
la bougie de l'annonce, l'agitation, la famille du marché, et les mouvements récents (1 jour, 1 semaine, 1 mois).
Avec des croisements simples (surprise x genre, surprise x famille, surprise x côté) : une pondération simple ne
peut pas les inventer seule.
Elle prévoit le mouvement de la journée suivante ; chaque 1er janvier elle réapprend sur les années passées puis
joue l'année suivante sans rien changer. Argent : une position par (annonce, marché) proportionnelle à sa
conviction, regroupée par annonce, 0,5 % de risque par journée d'agitation, frais réels, sortie avant le week-end.
Depuis Test_IA : venv_gpu\\Scripts\\python.exe -u -m collapsar.regarder.experience_annonces_ia
"""
from __future__ import annotations

import json
import os
from datetime import datetime

import numpy as np
import pandas as pd

from collapsar.donnees import calendrier
from collapsar.donnees import marches as dm
from collapsar.mains.fiches import DEVISES, fiche

JOUR = 96
RISQUE = 0.005
# genres d'annonce (noms anglais de Forex Factory et français de MetaTrader)
GENRES = {"taux": r"Rate|Cash Rate|Monetary Policy|FOMC|Bank Rate|Taux|Décision",
          "prix": r"CPI|PPI|Inflation|Price|IPC|IPP|HICP|IPCH|Prix",
          "emploi": r"Employment|Payroll|Non-Farm|Unemployment|Jobless|Claimant|Labor|Emploi|Chômage|Salaire|ADP",
          "activite": r"PMI|GDP|Production|ISM|Orders|Sentiment|Confidence|ZEW|Ifo|PIB|Climat|Commandes|Confiance",
          "consommation": r"Retail|Spending|Sales|Consumer|Ventes|Consomm|Dépenses"}
FAMILLES = ("devise", "metal", "indice", "energie", "crypto", "obligation")


def devises_du_marche(m: str, f) -> tuple[str | None, str | None]:
    """(devise « achat » : sa hausse fait monter le marché, devise « vente » : sa hausse le fait baisser)."""
    if f.famille == "devise":
        return m[:3], m[3:]
    return None, f.cotation            # indices, or... : le prix est exprimé dans cette devise


def situations() -> pd.DataFrame:
    # source du calendrier : « ff » (Forex Factory 2007 -> 04/2025) ou « mt5 » (MetaTrader 5, 2017 -> aujourd'hui,
    # la MÊME source que le direct ; importances haute ET moyenne, MetaTrader classe surtout le dollar en haute)
    if os.environ.get("COLLAPSAR_CALENDRIER", "ff") == "mt5":
        cal = calendrier.charger_mt5()
        garder = os.environ.get("COLLAPSAR_IMPORTANCES", "High,Medium").split(",")
        cal = cal[cal["importance"].isin(garder) & cal["z"].notna()].reset_index(drop=True)
    else:
        cal = calendrier.charger()
        cal = cal[(cal["importance"] == "High") & cal["z"].notna()].reset_index(drop=True)
    cal["id"] = np.arange(len(cal))
    for genre, motif in GENRES.items():
        cal[genre] = cal["annonce"].str.contains(motif, regex=True)
    lignes = []
    for m in dm.liste_marches():
        if len(dm.charger(m)) < dm.MIN_BOUGIES:
            continue
        try:
            f = fiche(m)
        except ValueError:
            continue
        # jamais au-delà de 09/2025, sauf pour le verdict de vérité sur les 12 mois cachés (EXAMEN_FIN_DONNEES)
        df = dm.charger(m, jusqua=pd.Timestamp(os.environ.get("EXAMEN_FIN_DONNEES", str(dm.FIN_EXAMEN.date()))))
        t = df["time"].values.astype("datetime64[ns]")
        o, h, l, c = (np.log(df[k].to_numpy(np.float64)) for k in ("open", "high", "low", "close"))
        u = pd.Series(h - l).rolling(64, min_periods=16).mean().shift(1).to_numpy()
        pause = np.r_[(t[1:] - (t[:-1] + np.timedelta64(15, "m"))) > np.timedelta64(2, "h"), True]
        fins = np.flatnonzero(pause)
        achat, vente = devises_du_marche(m, f)
        concernees = {d for d in (achat, vente, "USD") if d}
        ev = cal[cal["devise"].isin(concernees)]
        i = np.searchsorted(t, ev["temps"].values.astype("datetime64[ns]"), side="right") - 1
        ok = (i >= 2200) & (i < len(t) - JOUR - 1)
        ok &= (ev["temps"].values.astype("datetime64[ns]") - t[np.clip(i, 0, None)]) < np.timedelta64(15, "m")
        for (_, e), k in zip(ev[ok].iterrows(), i[ok]):
            if not np.isfinite(u[k]) or u[k] <= 0:
                continue
            prochaine = fins[np.searchsorted(fins, k, side="left")]
            if prochaine == k:
                continue
            sortie = min(k + JOUR, prochaine)
            aj = u[k] * np.sqrt(JOUR)
            cote = 1.0 if e["devise"] == achat else -1.0 if e["devise"] == vente else 0.0
            lignes.append({
                "id": e["id"], "temps": e["temps"], "marche": m, "famille": f.famille, "z": e["z"],
                "cote": cote, "dollar_seul": float(cote == 0.0), "haute": float(e["importance"] == "High"),
                **{g: float(e[g]) for g in GENRES},
                "reaction": (c[k] - o[k]) / u[k],
                "bouge_jour": (c[k] - c[k - 96]) / aj, "bouge_semaine": (c[k] - c[k - 480]) / (u[k] * np.sqrt(480)),
                "bouge_mois": (c[k] - c[k - 2100]) / (u[k] * np.sqrt(2100)),
                "agitation": np.log(u[k] / np.nanmean(u[k - 2100:k])),
                "cible": (c[sortie] - c[k]) / aj, "frais": f.frais / aj})
    return pd.DataFrame(lignes)


def entrees(x: pd.DataFrame) -> np.ndarray:
    z = x["z"].to_numpy()
    cols = [z * x["cote"], np.abs(z), x["reaction"], x["reaction"] * np.abs(z), x["bouge_jour"],
            x["bouge_semaine"], x["bouge_mois"], x["agitation"].fillna(0)]
    for g in GENRES:
        cols.append(z * x["cote"] * x[g])
    cols.append(z * x["cote"] * x["haute"])
    for fam in FAMILLES:
        dans = (x["famille"] == fam).to_numpy(float)
        cols += [dans, z * dans * x["dollar_seul"], z * x["cote"] * dans, x["reaction"] * dans]
    return np.clip(np.nan_to_num(np.stack([np.asarray(v, float) for v in cols], 1)), -10, 10)


def main():
    x = situations()
    x["annee"] = x["temps"].dt.year
    print(f"{len(x):,} situations (annonce x marché), {x['marche'].nunique()} marchés".replace(",", " "), flush=True)
    X, y = entrees(x), np.clip(x["cible"].to_numpy(), -5, 5)
    resultats, morceaux = {}, []
    for a in range(2013, 2026):
        ap, te = (x["annee"] < a).to_numpy(), (x["annee"] == a).to_numpy()
        if te.sum() == 0:
            continue
        moy, et = X[ap].mean(0), X[ap].std(0) + 1e-9
        A = np.c_[(X[ap] - moy) / et, np.ones(ap.sum())]
        w = np.linalg.solve(A.T @ A + 1e3 * np.eye(A.shape[1]), A.T @ y[ap])
        echelle = (A @ w).std() + 1e-12
        p = np.c_[(X[te] - moy) / et, np.ones(te.sum())] @ w
        # elle ne prend un coup que si le gain prévu dépasse nettement les frais (un trader ne joue pas à perte
        # certaine : 2011-2015, l'euro-franc suisse bloqué ne bougeait plus et les frais valaient des journées entières)
        conv = np.clip(p / echelle, -2, 2) * (np.abs(p) > 2 * x.loc[te, "frais"].to_numpy())
        d = x[te].assign(gain=conv * y[te] - np.abs(conv) * x.loc[te, "frais"], conv=np.abs(conv))   # mouvements aberrants bornés
        # un coup par annonce : moyenne pondérée de ses marchés (le risque d'une annonce est réparti)
        par = d.groupby("id").apply(lambda g: pd.Series({"temps": g["temps"].iloc[0],
                                                          "gain": g["gain"].sum() / max(len(g), 1)}),
                                    include_groups=False)
        morceaux.append(par)
        lien = np.corrcoef(p, y[te])[0, 1] * 100
        resultats[a] = {"lien_pct": lien}
        print(f"{a} : lien prévu/réel {lien:+.2f} % sur {te.sum():,} situations".replace(",", " "), flush=True)
    tout = pd.concat(morceaux)
    print("   (coups pris : %d sur %d situations)" % ((tout["gain"] != 0).sum(), len(tout)))
    for nom, (de, a_) in {"2013-2019": ("2013", "2020"), "2020-2022": ("2020", "2023"),
                          "2023-04/2025": ("2023", "2025-04-08")}.items():
        p = tout[(tout["temps"] >= de) & (tout["temps"] < a_)]
        mois = (p.set_index("temps")["gain"] * RISQUE * 100).groupby(pd.Grouper(freq="ME")).sum()
        cumul = mois.cumsum()
        print(f"   {nom:13s} : {mois.mean():+.2f} %/mois, mois positifs {(mois > 0).mean():.0%}, pire mois "
              f"{mois.min():+.2f} %, baisse max {(cumul.cummax() - cumul).max():.1f} %", flush=True)
        resultats[nom] = {"gain_mois_pct": float(mois.mean()), "baisse_max_pct": float((cumul.cummax() - cumul).max())}
    # d'où vient le gain (2020 -> 04/2025) : par famille de marchés
    (dm.RACINE / "collapsar" / "vie" / f"experience_annonces_ia_{datetime.now():%Y%m%d_%H%M}.json").write_text(
        json.dumps(resultats, ensure_ascii=False, indent=1, default=float), encoding="utf-8")


if __name__ == "__main__":
    main()
