"""Verdict FIDÈLE de l'IA des annonces (14/10/2026) : le vrai compte FTMO (simulateur `mains/`).

- L'IA (pondération simple réapprise chaque 1er janvier sur les années passées, `regarder/experience_annonces_ia.py`)
  décide à la clôture de la bougie de chaque annonce importante, sur chaque marché concerné ; elle ne joue que si le
  gain prévu dépasse nettement les frais.
- Chaque annonce engage 0,5 % de risque (par journée d'agitation) réparti sur ses marchés, tenu un jour.
- UN compte de 100 000 $ pour tous les marchés ; frais réels, frais de nuit, fermeture forcée avant toute pause de plus
  de 2 h (week-end), murs FTMO au pire moment de chaque bougie (-5 % par jour, -10 % au total), réussite à +10 %.
- Challenges de 90 jours qui démarrent tous les 2 jours entre 01/2023 et 04/2025 (fin du calendrier historique).
Depuis Test_IA : venv_gpu\\Scripts\\python.exe -u -m collapsar.juge.examen_annonces [risque, ex. 0.005]
"""
from __future__ import annotations

import json
import sys
from datetime import datetime

import numpy as np
import pandas as pd
import torch

from collapsar.donnees import marches as dm
from collapsar.mains.horloge import Horloge
from collapsar.mains.simulateur import CAPITAL, Comptes, Ordres
from collapsar.regarder.experience_annonces_adaptative import predictions_adaptatives
from collapsar.regarder.experience_annonces_ia import entrees, situations

import os
DEBUT = pd.Timestamp(os.environ.get("EXAMEN_DEBUT", "2023-01-01"))
FIN = pd.Timestamp(os.environ.get("EXAMEN_FIN", "2025-04-08"))
# au-delà de 09/2025 : les 12 MOIS CACHÉS, lus seulement pour le verdict de vérité décidé avec le chef de projet
FIN_DONNEES = pd.Timestamp(os.environ.get("EXAMEN_FIN_DONNEES", str(dm.FIN_EXAMEN.date())))
DUREE_CHALLENGE = pd.Timedelta(days=90)
ECART_DEPARTS = pd.Timedelta(days=2)
JOUR = 96


def dire(t):
    print(f"[{datetime.now():%H:%M:%S}] {t}", flush=True)


def decisions(risque: float) -> pd.DataFrame:
    """Les décisions de l'IA sur 2023 -> 04/2025, chaque année jouée avec ce qu'elle a appris AVANT."""
    # 14/10 16h : réapprise CHAQUE MOIS sur tout le passé à poids égal (meilleure que chaque année, et que les
    # mémoires courtes : regarder/experience_annonces_adaptative.py)
    x = situations()
    X, y = entrees(x), np.clip(x["cible"].to_numpy(), -5, 5)
    conv = predictions_adaptatives(x, X, y, None, debut=str(DEBUT.date()),
                                   apprendre_de=os.environ.get("EXAMEN_APPRENDRE_DE"))
    d = x.assign(conv=conv)
    d = d[np.isfinite(d["conv"])]
    d = d[(d["conv"] != 0) & (d["temps"] >= DEBUT) & (d["temps"] < FIN)].copy()
    d["n_marches"] = d.groupby("id")["marche"].transform("size")
    # agitation d'une journée en part du prix (la cible est en « journées d'agitation ») : retrouvée par marché
    return d


def main():
    risque = float(sys.argv[1]) if len(sys.argv) > 1 else 0.005
    dire("décisions de l'IA (réapprise chaque année)...")
    d = decisions(risque)
    marches = sorted(d["marche"].unique())
    donnees = {}
    for m in dm.liste_marches():
        if len(dm.charger(m)) >= dm.MIN_BOUGIES:
            df = dm.charger(m, jusqua=min(FIN + pd.Timedelta(days=2), FIN_DONNEES))
            donnees[m] = df[df["time"] >= DEBUT - pd.Timedelta(days=40)].reset_index(drop=True)
    h = Horloge(donnees, marches, "cpu")
    dire(f"{len(d):,} décisions sur {len(marches)} marchés, horloge de {h.T:,} instants".replace(",", " "))
    # position voulue (dollars) de chaque marché à chaque instant de l'horloge
    T, M = h.T, len(marches)
    delta = np.zeros((T + 1, M))
    tm = h.temps.values
    for j, m in enumerate(marches):
        df = donnees[m]
        t_m = df["time"].values.astype("datetime64[ns]")
        lc = np.log(df["close"].to_numpy())
        u = pd.Series(np.log(df["high"].to_numpy()) - np.log(df["low"].to_numpy())).rolling(64, min_periods=16) \
            .mean().shift(1).to_numpy()
        pause = np.r_[(t_m[1:] - (t_m[:-1] + np.timedelta64(15, "m"))) > np.timedelta64(2, "h"), True]
        fins = np.flatnonzero(pause)
        dm_ = d[d["marche"] == m]
        k = np.searchsorted(t_m, dm_["temps"].values.astype("datetime64[ns]"), side="right") - 1
        for (_, r), kk in zip(dm_.iterrows(), k):
            if kk < 64 or not np.isfinite(u[kk]):
                continue
            sortie = min(kk + JOUR, fins[np.searchsorted(fins, kk, side="left")])
            aj = u[kk] * np.sqrt(JOUR)                                  # journée d'agitation, en part du prix
            dollars = r["conv"] * risque * CAPITAL / aj / r["n_marches"]
            i0 = np.searchsorted(tm, t_m[kk], side="left")              # décision à la clôture de la bougie
            i1 = np.searchsorted(tm, t_m[sortie], side="left")          # sortie décidée à la clôture de cette bougie
            if i1 > i0:
                delta[i0, j] += dollars
                delta[i1, j] -= dollars
        _ = lc
    cible = np.cumsum(delta[:-1], 0)
    change = np.r_[np.ones((1, M), bool), np.abs(np.diff(cible, axis=0)) > 1e-6]
    cible_t = torch.from_numpy(np.where(change, cible, np.nan))
    # les challenges
    departs = pd.date_range(DEBUT, FIN - DUREE_CHALLENGE, freq=ECART_DEPARTS)
    i_dep = torch.from_numpy(np.searchsorted(tm, departs.values, side="left")).long()
    B = len(departs)
    comptes = Comptes(h, B)
    comptes.recommencer(torch.ones(B, dtype=torch.bool), i_dep)
    fin_t = torch.from_numpy(np.searchsorted(tm, (departs + DUREE_CHALLENGE).values, side="left")).long()
    vivant = torch.ones(B, dtype=torch.bool)
    etat = np.array(["en cours"] * B, dtype=object)
    valeur_fin = np.full(B, np.nan)
    baisse_max = np.zeros(B)
    sommet = np.full(B, CAPITAL)
    pas = 0
    while vivant.any():
        c = cible_t[comptes.t.clamp(max=T - 1)]
        c = torch.where(vivant[:, None], c, torch.full_like(c, float("nan")))
        r = comptes.pas(Ordres(cible=c))
        v = r["valeur"].numpy()
        sommet = np.maximum(sommet, np.where(vivant.numpy(), v, sommet))
        baisse_max = np.maximum(baisse_max, np.where(vivant.numpy(), (sommet - v) / CAPITAL * 100, 0))
        fini = vivant & (r["mort"] | r["reussi"] | (comptes.t >= fin_t) | r["fin_histoire"])
        for b in torch.nonzero(fini).flatten().tolist():
            etat[b] = "mur" if bool(r["mort"][b]) else "réussi" if bool(r["reussi"][b]) else "90 jours"
            valeur_fin[b] = v[b]
        vivant = vivant & ~fini
        pas += 1
        if pas % 2000 == 0:
            dire(f"  {pas} bougies, {int(vivant.sum())} challenges encore en cours")
    gain = (valeur_fin / CAPITAL - 1) * 100
    res = {"risque": risque, "challenges": B, "reussis_pct": float((etat == "réussi").mean() * 100),
           "murs_pct": float((etat == "mur").mean() * 100), "gain_moyen_3mois_pct": float(np.nanmean(gain)),
           "gain_median_3mois_pct": float(np.nanmedian(gain)), "positifs_pct": float((gain > 0).mean() * 100),
           "baisse_max_moyenne_pct": float(baisse_max.mean()), "pire_baisse_pct": float(baisse_max.max())}
    dire(f"VERDICT FIDÈLE (risque {risque:.2%} par annonce) : {B} challenges de 90 jours | réussis "
         f"{res['reussis_pct']:.0f} % | murs {res['murs_pct']:.0f} % | gain moyen {res['gain_moyen_3mois_pct']:+.2f} % "
         f"sur 3 mois (médiane {res['gain_median_3mois_pct']:+.2f} %) | positifs {res['positifs_pct']:.0f} % | "
         f"baisse max moyenne {res['baisse_max_moyenne_pct']:.1f} % (pire {res['pire_baisse_pct']:.1f} %)")
    (dm.RACINE / "collapsar" / "vie" / f"examen_annonces_{datetime.now():%Y%m%d_%H%M}.json").write_text(
        json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
