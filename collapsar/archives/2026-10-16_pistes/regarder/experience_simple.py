"""Expérience du 14/10 après-midi : le cerveau le PLUS SIMPLE (une pondération des 49 nombres de la vue d'ensemble,
incapable d'apprendre par cœur) trouve-t-il un lien sur le sens, sur des années jamais vues ?
Cible : mouvement du prix sur 1 h, 1 jour, 1 semaine (rapporté à l'agitation). Apprend 2010-2019, notée 2020-2022.
Aussi : le lien de chaque nombre seul (lesquels portent quelque chose ?).
Depuis Test_IA : venv_gpu\\Scripts\\python.exe -u -m collapsar.regarder.experience_simple
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from collapsar.donnees import marches as dm
from collapsar.regarder.exercices import DEBUT_CONTROLE, ECART
from collapsar.yeux.graphique import Graphique
from collapsar.yeux.vue_ensemble import FAMILLES, FOURCHETTES, GRANDS, PAS, PAS_GRANDS, VueDEnsemble

HORIZONS = {"1 h": 4, "1 jour": 96, "1 semaine": 480}


def noms_des_nombres():
    n = [f"bougé {k}" for k in PAS] + [f"fourchette {k}" for k in FOURCHETTES] + ["agitation jour", "agitation mois"]
    n += ["heure sin", "heure cos", "jour sin", "jour cos"] + [f"famille {f}" for f in FAMILLES] + ["frais"]
    n += [f"{g} bougé {k}" for g in GRANDS for k in PAS_GRANDS]
    return n


def main():
    donnees = {m: df for m in dm.liste_marches() if len(df := dm.charger(m)) >= dm.MIN_BOUGIES}
    g = Graphique(donnees, "cpu")
    del donnees
    vue = VueDEnsemble(g)
    X = vue.vue.numpy()
    lc = g.lc15.numpy().astype(np.float64)
    lh, ll = g.lh15.numpy().astype(np.float64), g.ll15.numpy().astype(np.float64)
    t = pd.DatetimeIndex(g.temps)
    cibles = {h: np.full(g.n, np.nan) for h in HORIZONS}
    for m in range(len(g.noms)):
        a, b = int(g.debut_marche[m]), int(g.debut_marche[m + 1])
        u = pd.Series(lh[a:b] - ll[a:b]).rolling(64, min_periods=16).mean().to_numpy()
        for h, k in HORIZONS.items():
            r = np.full(b - a, np.nan)
            r[:-k] = (lc[a + k:b] - lc[a:b - k]) / (u[:-k] * np.sqrt(k))
            cibles[h][a:b] = np.clip(r, -5, 5)
    ok = vue.valide & np.isfinite(cibles["1 semaine"])
    apprend = ok & (t < DEBUT_CONTROLE - ECART) & (t >= pd.Timestamp("2010-01-01"))
    controle = ok & (t >= DEBUT_CONTROLE)
    rng = np.random.default_rng(0)
    ia = rng.choice(np.flatnonzero(apprend), 2_000_000, replace=False)
    ic = np.flatnonzero(controle)
    noms = noms_des_nombres()
    for h in HORIZONS:
        y = cibles[h]
        Xa, ya = X[ia].astype(np.float64), y[ia]
        moy, et = Xa.mean(0), Xa.std(0) + 1e-9
        A = np.c_[(Xa - moy) / et, np.ones(len(Xa))]
        w = np.linalg.solve(A.T @ A + 1e3 * np.eye(A.shape[1]), A.T @ ya)          # pondération simple (ridge)
        pa = A @ w
        Ac = np.c_[(X[ic] - moy) / et, np.ones(len(ic))]
        pc = Ac @ w
        lien_a = np.corrcoef(pa, ya)[0, 1] * 100
        lien_c = np.corrcoef(pc, y[ic])[0, 1] * 100
        sens_c = np.mean(np.sign(pc) == np.sign(y[ic])) * 100
        print(f"{h:10s} : lien apprises {lien_a:+.2f} % | lien 2020-2022 {lien_c:+.2f} % | sens bien deviné "
              f"{sens_c:.2f} %", flush=True)
        if h == "1 semaine":
            seuls = [(np.corrcoef(X[ia, j], ya)[0, 1] * 100, np.corrcoef(X[ic, j], y[ic])[0, 1] * 100, noms[j])
                     for j in range(X.shape[1]) if X[ia, j].std() > 0]
            seuls.sort(key=lambda s: -abs(s[1]))
            print("   nombres seuls (1 semaine) : lien apprises | lien 2020-2022")
            for la, lcn, nom in seuls[:12]:
                print(f"     {nom:24s} {la:+6.2f} % | {lcn:+6.2f} %", flush=True)


if __name__ == "__main__":
    main()
