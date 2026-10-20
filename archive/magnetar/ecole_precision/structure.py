"""LES YEUX de l'école de la précision : ses zones d'offre et de demande VIVANTES de toutes les unités, les sommets /
creux confirmés, l'agitation — calculés UNE fois par marché (et par miroir) et rangés sur le disque.

Définitions (fixées avant tout résultat) :
- Unités : journalier, 4 h, 1 h, 30 min, 15 min (tous les marchés, à partir des bougies de 15 min) ; + 5 et 3 min pour les
  4 marchés à la minute. Journée = minuit du serveur. Une bougie d'unité n'est vue qu'une fois TERMINÉE.
- Zones (traduction fidèle de son indicateur, regarder/smc/nono.zones_nono ; même définition que
  regarder/smc/nono_v7.zones_graphique avec le graphique = l'unité de la zone) : à la clôture de la bougie i, bougie
  i-1 opposée + vide de prix (FVG) avec i-3 + cassure de la clôture i au-delà des bougies i-4 et i-5. Zone = la bougie
  i-1 (haut, bas). Elle disparaît à la 1re clôture d'une bougie de SON unité au-delà de son milieu (y compris la
  bougie i). Une zone de 4 h se juge donc sur un graphique 4 h, une zone de 3 min sur un graphique 3 min.
- Les 2 zones vivantes les plus proches de chaque côté : demande = les 2 milieux les plus HAUTS (les zones de demande
  vivantes sont sous les clôtures de leur unité), offre = les 2 milieux les plus BAS.
- Touchée : le prix (bougie de 15 min) est ENTRÉ dans la zone après qu'elle est devenue visible. Réaction : après le
  1er contact, une clôture de 15 min s'est éloignée du bord de la zone d'au moins max(hauteur de la zone, 0,25 agitation).
- Sommets / creux : fractal 2 (comme regarder/smc/multi.sommets_confirmes), confirmés 2 bougies plus tard.
- Agitation : moyenne (plus haut - plus bas) des 14 derniers jours terminés, en prix.
Tout est SANS FUTUR : à l'instant de décision (clôture d'une bougie de 15 min) on ne lit que des bougies terminées ;
les dates de fin / de contact / de réaction d'une zone ne sont comparées qu'à l'instant présent (testé :
tests/test_ecole_precision.py, calcul coupé à t = calcul complet).
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from numba import njit

from collapsar.ecole.precision import donnees as D
from collapsar.ecole.precision.reglages import CACHE, FREQ, R, UNITES
from collapsar.regarder.smc.nono import zones_nono

JAMAIS = np.int64(2 ** 62)
VERSION = 1
DUREE_NS = {u: int(pd.Timedelta(FREQ[u]).value) for u in UNITES}
QUINZE_NS = DUREE_NS["M15"]


# ============================================================================================== noyaux rapides
@njit(cache=True)
def table_min(a):
    n = len(a)
    L = 1
    while (1 << L) <= n:
        L += 1
    t = np.empty((L, n))
    t[0] = a
    for j in range(1, L):
        s = 1 << (j - 1)
        for i in range(n):
            t[j, i] = min(t[j - 1, i], t[j - 1, i + s]) if i + s < n else t[j - 1, i]
    return t


@njit(cache=True)
def table_max(a):
    n = len(a)
    L = 1
    while (1 << L) <= n:
        L += 1
    t = np.empty((L, n))
    t[0] = a
    for j in range(1, L):
        s = 1 << (j - 1)
        for i in range(n):
            t[j, i] = max(t[j - 1, i], t[j - 1, i + s]) if i + s < n else t[j - 1, i]
    return t


@njit(cache=True)
def premier_sous(tmin, i, x, strict):
    """Premier indice k >= i où a[k] < x (strict) ou a[k] <= x ; len(a) s'il n'y en a pas."""
    L, n = tmin.shape
    if i >= n:
        return n
    k = i
    for j in range(L - 1, -1, -1):
        if k + (1 << j) <= n:
            m = tmin[j, k]
            if (strict and m >= x) or ((not strict) and m > x):
                k += 1 << j
    return k


@njit(cache=True)
def premier_dessus(tmax, i, x, strict):
    """Premier indice k >= i où a[k] > x (strict) ou a[k] >= x ; len(a) s'il n'y en a pas."""
    L, n = tmax.shape
    if i >= n:
        return n
    k = i
    for j in range(L - 1, -1, -1):
        if k + (1 << j) <= n:
            m = tmax[j, k]
            if (strict and m <= x) or ((not strict) and m < x):
                k += 1 << j
    return k


@njit(cache=True)
def fins_zones(c_u, mid, side, ne):
    """Ligne de l'unité où chaque zone disparaît (1re clôture de son unité au-delà du milieu, à partir de sa
    naissance comprise) ; len(c_u) si elle vit encore à la fin des données."""
    n = len(c_u)
    tmin, tmax = table_min(c_u), table_max(c_u)
    fin = np.empty(len(mid), np.int64)
    for z in range(len(mid)):
        if side[z] > 0:
            fin[z] = premier_sous(tmin, ne[z], mid[z], True)
        else:
            fin[z] = premier_dessus(tmax, ne[z], mid[z], True)
    return fin


@njit(cache=True)
def contacts(tl, th, tcl, tch, A15, top, bot, side, vis, react_frac):
    """(1er contact, réaction) de chaque zone, en lignes de 15 min ; JAMAIS si aucun. tl / th / tcl / tch : tables des
    plus bas, plus hauts, clôtures (min et max) des bougies de 15 min."""
    T = tl.shape[1]
    nz = len(top)
    tou = np.full(nz, 2 ** 62, np.int64)
    rea = np.full(nz, 2 ** 62, np.int64)
    for z in range(nz):
        if vis[z] >= T:
            continue
        a = vis[z] + 1
        if side[z] > 0:
            k = premier_sous(tl, a, top[z], False)
        else:
            k = premier_dessus(th, a, bot[z], False)
        if k >= T:
            continue
        tou[z] = k
        ag = A15[k] if np.isfinite(A15[k]) else 0.0
        d = max(top[z] - bot[z], react_frac * ag)
        if side[z] > 0:
            r = premier_dessus(tch, k, top[z] + d, False)
        else:
            r = premier_sous(tcl, k, bot[z] - d, False)
        if r < T:
            rea[z] = r
    return tou, rea


@njit(cache=True)
def plus_proches(n_u, mid, side, ne, fin, K):
    """[n_u, 2, K] : à chaque ligne de l'unité (après sa clôture), les K zones de demande vivantes aux milieux les plus
    hauts (côté 0) et les K zones d'offre vivantes aux milieux les plus bas (côté 1) ; -1 si moins de K."""
    nz = len(mid)
    out = np.full((n_u, 2, K), -1, np.int32)
    dem = np.empty(nz, np.int64)      # triées par milieu croissant
    sup = np.empty(nz, np.int64)      # triées par milieu décroissant
    nd, ns, p = 0, 0, 0
    for r in range(n_u):
        while p < nz and ne[p] <= r:
            z = p
            p += 1
            if fin[z] <= r:
                continue
            if side[z] > 0:
                lo, hi = 0, nd
                while lo < hi:
                    m = (lo + hi) // 2
                    if mid[dem[m]] <= mid[z]:
                        lo = m + 1
                    else:
                        hi = m
                for q in range(nd, lo, -1):
                    dem[q] = dem[q - 1]
                dem[lo] = z
                nd += 1
            else:
                lo, hi = 0, ns
                while lo < hi:
                    m = (lo + hi) // 2
                    if mid[sup[m]] >= mid[z]:
                        lo = m + 1
                    else:
                        hi = m
                for q in range(ns, lo, -1):
                    sup[q] = sup[q - 1]
                sup[lo] = z
                ns += 1
        # disparitions à cette ligne : toujours un SUFFIXE (si la clôture passe sous le milieu d'une zone de demande,
        # elle passe aussi sous tous les milieux plus hauts ; symétrique pour l'offre)
        while nd > 0 and fin[dem[nd - 1]] <= r:
            nd -= 1
        while ns > 0 and fin[sup[ns - 1]] <= r:
            ns -= 1
        for k in range(K):
            if nd - 1 - k >= 0:
                out[r, 0, k] = dem[nd - 1 - k]
            if ns - 1 - k >= 0:
                out[r, 1, k] = sup[ns - 1 - k]
    return out


@njit(cache=True)
def sommets(h, l):
    """Sommets (1) et creux (-1) fractal 2 : (prix, bougie de confirmation, type) — comme multi.sommets_confirmes."""
    n = len(h)
    px, cf, ty = np.empty(2 * n), np.empty(2 * n, np.int64), np.empty(2 * n, np.int64)
    m = 0
    for j in range(2, n - 2):
        if h[j] > h[j - 1] and h[j] > h[j - 2] and h[j] > h[j + 1] and h[j] > h[j + 2]:
            px[m], cf[m], ty[m] = h[j], j + 2, 1
            m += 1
        if l[j] < l[j - 1] and l[j] < l[j - 2] and l[j] < l[j + 1] and l[j] < l[j + 2]:
            px[m], cf[m], ty[m] = l[j], j + 2, -1
            m += 1
    return px[:m], cf[:m], ty[:m]


@njit(cache=True)
def derniers_sommets(n_u, px, cf, ty):
    """[n_u, 4] : dernier sommet, avant-dernier sommet, dernier creux, avant-dernier creux confirmés (NaN sinon)."""
    out = np.full((n_u, 4), np.nan)
    s1, s2, c1, c2 = np.nan, np.nan, np.nan, np.nan
    p = 0
    for r in range(n_u):
        while p < len(px) and cf[p] <= r:
            if ty[p] > 0:
                s2, s1 = s1, px[p]
            else:
                c2, c1 = c1, px[p]
            p += 1
        out[r, 0], out[r, 1], out[r, 2], out[r, 3] = s1, s2, c1, c2
    return out


# ============================================================================================== calcul d'un marché
def bougies_unite(df15: pd.DataFrame, dfm: pd.DataFrame | None, u: str) -> dict:
    src = dfm if u in ("M5", "M3") else df15
    b = df15 if u == "M15" else D.reechantillonner(src, FREQ[u])
    debut = b["time"].values.astype("datetime64[ns]").astype(np.int64)
    return {"debut": debut, "fin": debut + DUREE_NS[u],
            **{k: b[k].to_numpy(np.float64) for k in ("open", "high", "low", "close")}}


def zones_unite(b: dict) -> dict:
    """Zones de l'unité (sans futur pour l'existence ; `fin` est une ligne de l'unité, comparée à l'instant présent)."""
    top, bot, mid, side, ne = zones_nono(b["open"], b["high"], b["low"], b["close"])
    fin = fins_zones(b["close"], mid, side, ne) if len(mid) else np.zeros(0, np.int64)
    return {"top": top, "bot": bot, "mid": mid, "side": side.astype(np.int64), "ne": ne.astype(np.int64), "fin": fin}


def calculer(t15: np.ndarray, o15, h15, l15, c15, dfm: pd.DataFrame | None, unites: tuple[str, ...], K: int = 2,
             df15: pd.DataFrame | None = None) -> dict:
    """Toute la structure d'un marché, à partir de ses bougies de 15 min (t15 = ouverture, ns) et de ses minutes
    (marchés à la minute). Rend des tableaux numpy (voir `ranger`)."""
    r = R().yeux
    if df15 is None:
        df15 = pd.DataFrame({"time": t15.astype("datetime64[ns]"), "open": o15, "high": h15, "low": l15, "close": c15})
    T = len(t15)
    dec = t15 + QUINZE_NS                                             # instant de décision = clôture de la bougie
    out = {"t15": t15, "o": o15, "h": h15, "l": l15, "c": c15}
    # agitation : moyenne des 14 derniers jours terminés
    bj = bougies_unite(df15, dfm, "D1")
    idx_j = np.searchsorted(bj["fin"], dec, side="right") - 1
    plage = bj["high"] - bj["low"]
    moy = pd.Series(plage).rolling(r.jours_agitation, min_periods=3).mean().to_numpy()
    A = np.where(idx_j >= 0, moy[np.clip(idx_j, 0, None)], np.nan)
    out["A"] = A
    tables = (table_min(l15), table_max(h15), table_min(c15), table_max(c15))
    for u in unites:
        b = bj if u == "D1" else bougies_unite(df15, dfm, u)
        n_u = len(b["close"])
        idx = (np.searchsorted(b["fin"], dec, side="right") - 1).astype(np.int64)
        z = zones_unite(b)
        vis = np.searchsorted(idx, z["ne"], side="left").astype(np.int64)        # 1re ligne de 15 min où elle se voit
        tou, rea = contacts(*tables, np.nan_to_num(A, nan=0.0), z["top"], z["bot"], z["side"], vis,
                            r.reaction_hauteur) if len(z["top"]) else (np.zeros(0, np.int64), np.zeros(0, np.int64))
        knn = plus_proches(n_u, z["mid"], z["side"], z["ne"], z["fin"], K)
        px, cf, ty = sommets(b["high"], b["low"])
        sw = derniers_sommets(n_u, px, cf, ty)
        if u in ("M5", "M3"):                    # rangés à la résolution de décision (15 min)
            ok = idx >= 0
            ii = np.clip(idx, 0, None)
            knn = np.where(ok[:, None, None], knn[ii], -1).astype(np.int32)
            sw = np.where(ok[:, None], sw[ii], np.nan)
            ligne = np.where(ok, np.arange(T), -1)
            cl = np.where(ok, b["close"][ii], np.nan)
        else:
            ligne = idx
            cl = b["close"]
        out[u] = {"ligne": ligne.astype(np.int32), "knn": knn.astype(np.int32), "sw": sw.astype(np.float32),
                  "cl": cl.astype(np.float32), "top": z["top"].astype(np.float32), "bot": z["bot"].astype(np.float32),
                  "side": z["side"].astype(np.int8), "vis": vis, "tou": tou, "rea": rea,
                  # pour les tests (fidélité à nono_v7) : naissance / fin en lignes de l'unité, temps des bougies
                  "ne": z["ne"], "fin": z["fin"], "debut_u": b["debut"]}
    return out


# ============================================================================================== cache sur disque
def dossier(nom: str, miroir: bool) -> Path:
    return CACHE / "yeux" / D.nom_variante(nom, miroir).replace("@", "_")


def preparer(nom: str, miroir: bool, forcer: bool = False) -> Path:
    """Calcule et range la structure d'un marché (ou de son miroir) si elle n'est pas déjà sur le disque."""
    d = dossier(nom, miroir)
    fait = d / "fait.json"
    if fait.exists() and not forcer and json.loads(fait.read_text())["version"] == VERSION:
        return d
    K = R().yeux.zones_par_cote
    df15 = D.quinze_variante(nom, miroir)
    dfm = D.minutes_variante(nom, miroir) if D.source(nom) == "minute" else None
    t15 = df15["time"].values.astype("datetime64[ns]").astype(np.int64)
    o, h, l, c = (df15[k].to_numpy(np.float64) for k in ("open", "high", "low", "close"))
    s = calculer(t15, o, h, l, c, dfm, D.unites(nom), K, df15)
    reel = D.quinze(nom)["close"].to_numpy(np.float64)
    d.mkdir(parents=True, exist_ok=True)
    np.save(d / "t15.npy", t15)
    for k in ("o", "h", "l", "c"):
        np.save(d / f"{k}.npy", s[k])
    np.save(d / "A.npy", s["A"].astype(np.float64))
    np.save(d / "demi.npy", D.demi_frais(nom, reel))
    for u in D.unites(nom):
        for k, v in s[u].items():
            if k in ("ne", "fin", "debut_u"):
                continue
            np.save(d / f"{u}_{k}.npy", v)
    fait.write_text(json.dumps({"version": VERSION, "lignes": len(t15), "debut": str(df15["time"].iloc[0]),
                                "fin": str(df15["time"].iloc[-1])}))
    return d


def preparer_tout(miroirs: bool = True, dire=print):
    """Les yeux de tous les marchés de l'école (et de leurs miroirs) : une fois pour toutes (~1 h au premier lancement)."""
    import time
    for nom in D.univers():
        for mir in ((False, True) if miroirs else (False,)):
            t0 = time.time()
            deja = (dossier(nom, mir) / "fait.json").exists()
            try:
                preparer(nom, mir)
            except Exception as e:                      # un marché sans données ne doit pas tout arrêter
                dire(f"yeux de {D.nom_variante(nom, mir)} : IMPOSSIBLE ({type(e).__name__}: {e})")
                continue
            if not deja:
                dire(f"yeux de {D.nom_variante(nom, mir)} prêts ({time.time() - t0:.0f} s)")


def lire(nom: str, miroir: bool) -> dict:
    """Tous les tableaux rangés d'un marché (lecture paresseuse : np.load en mémoire projetée)."""
    d = preparer(nom, miroir)
    x = {k: np.load(d / f"{k}.npy", mmap_mode="r") for k in ("t15", "o", "h", "l", "c", "A", "demi")}
    for u in D.unites(nom):
        x[u] = {k: np.load(d / f"{u}_{k}.npy", mmap_mode="r") for k in
                ("ligne", "knn", "sw", "cl", "top", "bot", "side", "vis", "tou", "rea")}
    return x
