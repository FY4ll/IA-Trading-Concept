"""Des avis aux trades, sur les bougies de 15 min (20/10/2026) : exécution de l'ordre limite, sortie fixe (le sens
seul), gestion du chef de projet (80 % à 2 R, stop à l'entrée, reste vers la zone opposée). Le même trade peut être
rejoué dans l'autre sens ou en achat (les juges) : même entrée, même heure, mêmes distances.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from numba import njit

from core.ftmo import frais as F

PART_2R = 0.80
DUREE_MAX = pd.Timedelta(days=30)
HORIZON_BOUGIES = 20


@njit(cache=True)
def _remplir(o, h, l, k0, k1, sens, entree):
    """1re bougie de 15 min (de k0 à k1 exclu) qui atteint le prix de l'ordre limite ; prix d'ouverture s'il ouvre déjà
    au-delà. Rend (k, prix) ; k = -1 si jamais exécuté."""
    m = len(k0)
    kf = np.full(m, -1, np.int64)
    px = np.full(m, np.nan)
    for t in range(m):
        for k in range(k0[t], min(k1[t], len(o))):
            if sens[t] > 0 and l[k] <= entree[t]:
                kf[t], px[t] = k, min(o[k], entree[t])
                break
            if sens[t] < 0 and h[k] >= entree[t]:
                kf[t], px[t] = k, max(o[k], entree[t])
                break
    return kf, px


@njit(cache=True)
def gestion(o, h, l, c, t0, kf, P, d, d_obj, t_fin, s, part):
    """Résultat en R (avant frais) du trade de sens s (+1 / -1) entré en kf au prix P : stop à d, `part` fermée à 2 d
    puis stop à l'entrée, reste à d_obj (tout à d_obj si d_obj <= 2 d), sortie au plus tard à t_fin. Dans une bougie :
    le stop d'abord. La bougie d'entrée NE COMPTE POUR PERSONNE (correctif du 20/10 03h25 : son plus haut / plus bas
    peut dater d'AVANT l'entrée ; le compter « stoppait » à tort le jumeau inversé)."""
    m = len(kf)
    R = np.zeros(m)
    n = len(o)
    for t in range(m):
        st = s[t]
        stop = P[t] - st * d[t]
        tp1 = P[t] + st * 2 * d[t]
        obj = P[t] + st * d_obj[t]
        partiel = d_obj[t] > 2 * d[t]
        reste = 1.0
        fini = False
        for k in range(kf[t] + 1, n):
            if t0[k] >= t_fin[t]:
                R[t] += reste * st * (o[k] - P[t]) / d[t]
                fini = True
                break
            touche = (st > 0 and l[k] <= stop) or (st < 0 and h[k] >= stop)
            if touche:
                px = stop
                if (st > 0 and o[k] < stop) or (st < 0 and o[k] > stop):
                    px = o[k]
                R[t] += reste * st * (px - P[t]) / d[t]
                fini = True
                break
            if partiel and reste == 1.0 and ((st > 0 and h[k] >= tp1) or (st < 0 and l[k] <= tp1)):
                px = tp1
                if (st > 0 and o[k] > tp1) or (st < 0 and o[k] < tp1):
                    px = o[k]
                R[t] += part * st * (px - P[t]) / d[t]
                reste = 1.0 - part
                stop = P[t]
                if (st > 0 and h[k] >= obj) or (st < 0 and l[k] <= obj):
                    R[t] += reste * st * (obj - P[t]) / d[t]
                    fini = True
                    break
                continue
            if (st > 0 and h[k] >= obj) or (st < 0 and l[k] <= obj):
                px = obj
                if (st > 0 and o[k] > obj) or (st < 0 and o[k] < obj):
                    px = o[k]
                R[t] += reste * st * (px - P[t]) / d[t]
                fini = True
                break
        if not fini:
            R[t] += reste * st * (c[n - 1] - P[t]) / d[t]
    return R


def trades(avis: pd.DataFrame, b15: pd.DataFrame, fins_u: np.ndarray) -> pd.DataFrame:
    """Exécute les avis et rend un trade par avis exécuté, avec les deux mesures pour : le signal, son inverse, l'achat.
    `b15` : les bougies de l'exécution (depuis le correctif : les bougies d'UNE MINUTE) ;
    `fins_u` : heures de fin des bougies de l'unité du détecteur (sortie fixe = 20 bougies u après l'entrée)."""
    t0 = b15["time"].to_numpy("datetime64[ns]")
    o, h, l, c = (b15[k].to_numpy(np.float64) for k in ("open", "high", "low", "close"))
    k0 = np.searchsorted(t0, avis["temps"].to_numpy("datetime64[ns]"), side="left")
    k1 = np.searchsorted(t0, avis["expire"].to_numpy("datetime64[ns]"), side="left")
    sens = avis["sens"].to_numpy(np.int64)
    kf, P = _remplir(o, h, l, k0, k1, sens, avis["entree"].to_numpy(np.float64))
    ok = kf >= 0
    a = avis[ok].reset_index(drop=True)
    kf, P, sens = kf[ok], P[ok], sens[ok]
    d_prevu = (a["entree"] - a["stop"]).abs().to_numpy()
    d = np.maximum((P - a["stop"].to_numpy()) * sens, 0.5 * d_prevu)        # 1 R réel (au moins la moitié du prévu)
    d_obj = (a["objectif"].to_numpy() - P) * sens
    t_fill = t0[kf]
    t_fin = (pd.to_datetime(t_fill) + DUREE_MAX).to_numpy("datetime64[ns]")
    cout = np.asarray(F.frais("XAUUSD", P), float) * P                      # aller-retour, en prix
    out = a.copy()
    out["entree_reelle"], out["heure_entree"] = P, pd.to_datetime(t_fill)
    out["risque_prix"], out["cout_R"] = d, cout / d
    # (b) gestion : signal, inverse, achat
    t0_i, t_fin_i = t0.astype(np.int64), t_fin.astype(np.int64)
    for nom, s in (("b_signal", sens), ("b_inverse", -sens), ("b_achat", np.ones_like(sens))):
        out[nom] = gestion(o, h, l, c, t0_i, kf, P, d, d_obj, t_fin_i, s, PART_2R) - cout / d
    # (a) le sens seul : sortie à l'ouverture de la 1re bougie de 15 min après la fin de la 20e bougie u
    ku = np.searchsorted(fins_u.astype("datetime64[ns]"), t_fill, side="right")
    t_sortie = fins_u[np.minimum(ku + HORIZON_BOUGIES, len(fins_u) - 1)].astype("datetime64[ns]")
    ks = np.minimum(np.searchsorted(t0, t_sortie, side="left"), len(o) - 1)
    mouvement = o[ks] - P
    atr = a["atr"].to_numpy()
    for nom, s in (("a_signal", sens), ("a_inverse", -sens), ("a_achat", np.ones_like(sens))):
        out[nom] = (s * mouvement - cout) / atr
    out["mois"] = out["heure_entree"].dt.to_period("M")
    return out
