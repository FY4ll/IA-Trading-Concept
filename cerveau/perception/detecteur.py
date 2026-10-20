"""DÉTECTEUR DE ZONES codé à la main (couche perception, 20/10/2026) : la méthode manuelle du chef de projet, une
instance par unité de temps (D1, H4, H1, M15). Rien n'est appris. Règles : PLAN_FIGE.md de
etudes/2026-10-20_couche1_perception (zone de son indicateur confirmée par le profil de volume, entrée au 2e contact au
milieu, pas de FVG non comblé derrière, objectif = zone opposée, stop derrière la zone).
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from numba import njit

from cerveau.perception import zones as Z
from cerveau.socle import COLONNES_AVIS, ModulePerception, enregistrer
from core import donnees as D

ECHELLES = {"D1": "jour", "H4": "4 h", "H1": "1 h", "M15": "15 min"}
REGLAGES = {"fenetre_volume": 200, "pas_volume_atr": 0.25, "top_volume": 0.20, "reaction_atr": 0.5,
            "fvg_taille_atr": 0.1, "fvg_distance_atr": 1.0, "marge_stop_atr": 0.2, "validite_bougies": 200}


@njit(cache=True)
def _fvg_derriere(sens, haut, bas, j, k_pose, atr, fh, fb, fk, fc, dist_atr):
    """Pour chaque zone : un FVG non comblé au moment k_pose, entièrement derrière la zone, à moins de dist_atr × ATR
    de son bord (le FVG du motif de la zone, formé en k = j, est exclu) ?"""
    m = len(sens)
    out = np.zeros(m, np.bool_)
    for z in range(m):
        d = dist_atr * atr[z]
        for f in range(len(fk)):
            if fk[f] > k_pose[z] or fc[f] <= k_pose[z] or fk[f] == j[z]:
                continue
            if sens[z] > 0:
                if fh[f] <= bas[z] and bas[z] - fh[f] <= d:
                    out[z] = True
                    break
            else:
                if fb[f] >= haut[z] and fb[f] - haut[z] <= d:
                    out[z] = True
                    break
    return out


@njit(cache=True)
def _objectif(sens, entree, k_pose, zh, zb, zs, zi, zfin):
    """Bord proche de la plus proche zone opposée vivante en k_pose, au-delà de l'entrée ; NaN s'il n'y en a pas."""
    m = len(sens)
    out = np.full(m, np.nan)
    for z in range(m):
        meilleur = np.nan
        for y in range(len(zs)):
            if zs[y] != -sens[z] or zi[y] > k_pose[z] or zfin[y] <= k_pose[z]:
                continue
            if sens[z] > 0 and zb[y] > entree[z]:
                if np.isnan(meilleur) or zb[y] < meilleur:
                    meilleur = zb[y]
            elif sens[z] < 0 and zh[y] < entree[z]:
                if np.isnan(meilleur) or zh[y] > meilleur:
                    meilleur = zh[y]
        out[z] = meilleur
    return out


class DetecteurZones(ModulePerception):
    def __init__(self, unite: str):
        self.unite = unite
        self.nom = f"zones_{unite}"

    def bougies(self, bougies15: pd.DataFrame) -> dict:
        return D.echelle(bougies15, ECHELLES[self.unite])

    def avis(self, bougies15: pd.DataFrame, compter: dict | None = None) -> pd.DataFrame:
        r = REGLAGES
        b = self.bougies(bougies15)
        o, h, l, c, v = (np.ascontiguousarray(b[k], dtype=np.float64) for k in ("open", "high", "low", "close", "volume"))
        fin_t = b["fin"].astype("datetime64[ns]")
        atr = Z.atr14(h, l, c)
        zh, zb, zm, zs, zi = Z.zones(o, h, l, c)
        zfin = Z.effacement(zm, zs, zi, c)
        n_zones = len(zs)
        ok_vol, rang = Z.profil_volume(h, l, v, atr, zh, zb, zi, r["fenetre_volume"], r["pas_volume_atr"], r["top_volume"])
        sel = np.flatnonzero(ok_vol & np.isfinite(atr[zi]))
        kc, kr = Z.premier_contact_et_reaction(h, l, c, zh[sel], zb[sel], zs[sel], zi[sel], zfin[sel], atr,
                                               r["reaction_atr"])
        arme = kr >= 0
        s = sel[arme]
        k_pose = kr[arme]
        a_z = atr[zi[s]]
        fh, fb, fs, fk, fc = Z.fvg(h, l, atr, r["fvg_taille_atr"])
        bloque = _fvg_derriere(zs[s], zh[s], zb[s], zi[s] - 1, k_pose, a_z, fh, fb, fk, fc, r["fvg_distance_atr"])
        obj = _objectif(zs[s], zm[s], k_pose, zh, zb, zs, zi, zfin)
        garde = ~bloque & np.isfinite(obj)
        if compter is not None:
            compter.update({"zones": int(n_zones), "confirmees_volume": int(len(sel)),
                            "premier_contact_reagi": int(arme.sum()), "bloquees_fvg": int(bloque.sum()),
                            "sans_zone_opposee": int((~bloque & ~np.isfinite(obj)).sum()), "avis": int(garde.sum())})
        s, k_pose, a_z, obj = s[garde], k_pose[garde], a_z[garde], obj[garde]
        sens = zs[s]
        stop = np.where(sens > 0, zb[s] - r["marge_stop_atr"] * a_z, zh[s] + r["marge_stop_atr"] * a_z)
        expire_k = np.minimum(k_pose + r["validite_bougies"], len(c) - 1)
        conf = np.clip((rang[s] - (1 - r["top_volume"])) / r["top_volume"], 0.0, 1.0)
        return pd.DataFrame({
            "module": self.nom, "temps": pd.to_datetime(fin_t[k_pose]), "expire": pd.to_datetime(fin_t[expire_k]),
            "sens": sens.astype(int), "confiance": conf, "zone_haut": zh[s], "zone_bas": zb[s], "entree": zm[s],
            "stop": stop, "objectif": obj, "atr": a_z, "naissance": pd.to_datetime(fin_t[zi[s]]),
        })[list(COLONNES_AVIS) + ["naissance"]]


DETECTEURS = {u: enregistrer(DetecteurZones(u)) for u in ("D1", "H4", "H1", "M15")}
