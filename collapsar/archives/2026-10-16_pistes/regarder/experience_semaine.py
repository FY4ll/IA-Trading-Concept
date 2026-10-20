"""Expérience du 14/10 après-midi : une IA SIMPLE qui réapprend chaque année rapporte-t-elle de l'argent ?

- Elle regarde la vue d'ensemble (49 nombres, prix bruts seulement) de chaque marché le lundi à 10 h (heure du
  serveur) et prévoit le mouvement de la semaine (rapporté à l'agitation) avec une pondération simple (ridge).
- Chaque 1er janvier, elle réapprend sur les années passées (toutes depuis 2010, ou seulement les 3 dernières), puis
  joue l'année suivante sans rien changer (marche en avant : aucune année jugée n'a servi à apprendre).
- Position de chaque marché proportionnelle à sa conviction (bornée), tenue jusqu'à la fermeture forcée (avant le
  week-end ou une pause de plus de 2 h, une semaine au plus) ; frais réels FTMO de chaque marché.
- Le compte est réglé pour une agitation d'environ 2,5 % par mois (réglage fait sur l'année PRÉCÉDENTE seulement).
Les 12 mois cachés (après 09/2025) ne sont jamais lus.
Depuis Test_IA : venv_gpu\\Scripts\\python.exe -u -m collapsar.regarder.experience_semaine
"""
from __future__ import annotations

import json
from datetime import datetime

import numpy as np
import pandas as pd

from collapsar.donnees import marches as dm
from collapsar.mains.fiches import fiche
from collapsar.regarder.vision_trader import VisionTrader
from collapsar.yeux.graphique import Graphique
from collapsar.yeux.vue_ensemble import VueDEnsemble

ANNEES = range(2014, 2026)
AGITATION_MOIS = 0.025


def main():
    donnees = {}
    for m in dm.liste_marches():
        if len(dm.charger(m)) >= dm.MIN_BOUGIES:
            donnees[m] = dm.charger(m, jusqua=dm.FIN_EXAMEN)
    g = Graphique(donnees, "cpu")
    del donnees
    vue = VueDEnsemble(g)
    vt = VisionTrader(g, n_controle=1)
    X = vue.vue.numpy().astype(np.float64)
    lc = g.lc15.numpy().astype(np.float64)
    taille = vt.taille.numpy().astype(np.float64)
    duree = vt.duree.numpy()
    t = pd.DatetimeIndex(g.temps)
    lundi = np.asarray((t.dayofweek == 0) & (t.hour == 9) & (t.minute == 45))    # clôture de 10 h
    ok = lundi & vue.valide & vt.utilisable & (g.pas == 15)
    idx = np.flatnonzero(ok)
    d = duree[idx]
    fin = idx + d
    z = (lc[fin] - lc[idx]) / (taille[idx] * np.sqrt(np.maximum(d, 1)))          # mouvement en « agitations »
    frais = np.array([fiche(g.noms[m]).frais if True else 0 for m in g.marche[idx]])
    cout_z = frais / (taille[idx] * np.sqrt(np.maximum(d, 1)))
    rend = lc[fin] - lc[idx]                                                    # rendement réel (log)
    semaine = t[idx].normalize()
    annee = t[idx].year.to_numpy()
    Xs = X[idx]
    resultats = {}
    for fenetre in ("tout", "3 ans"):
        mois_pnl = []
        par_an = {}
        for a in ANNEES:
            ap = (annee < a) & (annee >= (2010 if fenetre == "tout" else a - 3))
            te = annee == a
            if ap.sum() < 1000 or te.sum() == 0:
                continue
            moy, et = Xs[ap].mean(0), Xs[ap].std(0) + 1e-9
            A = np.c_[(Xs[ap] - moy) / et, np.ones(ap.sum())]
            y = np.clip(z[ap], -5, 5)
            w = np.linalg.solve(A.T @ A + 1e3 * np.eye(A.shape[1]), A.T @ y)
            pa = A @ w
            echelle_p = pa.std() + 1e-12
            conv = lambda p: np.clip(p / echelle_p, -2, 2)
            # réglage de la taille sur les années d'apprentissage : agitation du compte par mois visée
            gain_ap = conv(pa) * (z[ap] - np.sign(pa) * cout_z[ap])
            par_sem_ap = pd.Series(gain_ap).groupby(semaine[ap]).sum()
            k = AGITATION_MOIS / (par_sem_ap.std() * np.sqrt(52 / 12) + 1e-12)
            Ac = np.c_[(Xs[te] - moy) / et, np.ones(te.sum())]
            pc = Ac @ w
            gain = k * conv(pc) * (z[te] - np.sign(pc) * cout_z[te])
            mois = pd.Series(gain, index=t[idx][te]).groupby(pd.Grouper(freq="ME")).sum() * 100
            mois_pnl.append(mois)
            lien = np.corrcoef(pc, z[te])[0, 1] * 100
            par_an[a] = {"lien_pct": lien, "gain_mois_pct": float(mois.mean()), "pire_mois_pct": float(mois.min()),
                         "mois_positifs_pct": float((mois > 0).mean() * 100)}
            print(f"{fenetre:6s} {a} : lien {lien:+5.2f} % | {mois.mean():+.2f} %/mois | pire mois {mois.min():+.2f} % "
                  f"| mois positifs {(mois > 0).mean():.0%}", flush=True)
        tous = pd.concat(mois_pnl)
        for nom, (de, a_) in {"2015-2019": (2015, 2019), "2020-2022": (2020, 2022), "2023-09/2025": (2023, 2025)}.items():
            m = tous[(tous.index.year >= de) & (tous.index.year <= a_)]
            cumul = m.cumsum()
            print(f"   {fenetre} {nom:13s} : {m.mean():+.2f} %/mois, mois positifs {(m > 0).mean():.0%}, pire mois "
                  f"{m.min():+.2f} %, baisse max {(cumul.cummax() - cumul).max():.1f} %", flush=True)
        resultats[fenetre] = par_an
    (dm.RACINE / "collapsar" / "vie" / f"experience_semaine_{datetime.now():%Y%m%d_%H%M}.json").write_text(
        json.dumps(resultats, ensure_ascii=False, indent=1, default=float), encoding="utf-8")


if __name__ == "__main__":
    main()
