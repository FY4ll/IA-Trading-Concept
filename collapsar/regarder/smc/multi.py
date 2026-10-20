"""Stratégie personnelle MULTI-UNITÉS (docs/SMC_MULTI_UT.md, figé) : zones de fond H4 / journalier à volume fort,
affinées sur la bougie avant l'explosion (M15 / M5), entrée au 1er contact, sorties par tiers (2 R, sommet H1, zone
opposée de fond), point mort ou non. Mêmes frais, même jumeau, même protocole.
Depuis Test_IA : venv_gpu\\Scripts\\python.exe -u -m collapsar.regarder.smc.multi apprentissage|cachee
"""
from __future__ import annotations

import json
import math
import sys
from datetime import datetime

import numpy as np
import pandas as pd
from numba import njit

from collapsar.regarder.smc import noyaux as K
from collapsar.regarder.smc.bougies import MARCHES, bougies
from collapsar.regarder.smc.labo import VIE, _m1, note, periode

FIN_APPRENTISSAGE = pd.Timestamp("2024-01-01")
SEUIL = math.sqrt(2 * math.log(430))
FONDS, PETITES, MARGES, POINT_MORT = ("H4", "D1"), ("M15", "M5"), (0.2, 0.5), (True, False)
TENUE_JOURS = 30


@njit(cache=True)
def sommets_confirmes(h, l):
    """Sommets (1) et creux (-1) fractal 2 : (prix, bougie de confirmation, type)."""
    n = len(h)
    px, cf, ty = np.empty(n), np.empty(n, np.int64), np.empty(n, np.int64)
    m = 0
    for j in range(2, n - 2):
        if h[j] > h[j - 1] and h[j] > h[j - 2] and h[j] > h[j + 1] and h[j] > h[j + 2]:
            px[m], cf[m], ty[m] = h[j], j + 2, 1
            m += 1
        if l[j] < l[j - 1] and l[j] < l[j - 2] and l[j] < l[j + 1] and l[j] < l[j + 2]:
            px[m], cf[m], ty[m] = l[j], j + 2, -1
            m += 1
    return px[:m].copy(), cf[:m].copy(), ty[:m].copy()


@njit(cache=True)
def affiner(o, h, l, c, atr, a, e, sens, base_haut, base_bas):
    """La bougie avant l'explosion, dans les bougies [a, e) de la petite unité : dernière bougie opposée suivie d'un
    départ >= 2 ATR en <= 3 bougies qui emmène le prix au-delà de la base de fond. Rend son index ou -1."""
    for k in range(a, e - 1):
        opposee = (c[k] < o[k] and c[k + 1] > o[k + 1]) if sens > 0 else (c[k] > o[k] and c[k + 1] < o[k + 1])
        if not opposee:
            continue
        mh, ml = -1e18, 1e18
        for j in range(1, 4):
            if k + j >= len(c):
                break
            mh = max(mh, h[k + j])
            ml = min(ml, l[k + j])
            if sens > 0 and mh - c[k] >= K.K_DEPART * atr[k] and mh > base_haut:
                return k
            if sens < 0 and c[k] - ml >= K.K_DEPART * atr[k] and ml < base_bas:
                return k
    return -1


@njit(cache=True)
def trade_tiers(o, h, l, c, mo, mh, ml, i, f_min, b_min, sens, entree, risque, d2, d3, point_mort, tenue, frais,
                facteur):
    """Position en trois tiers : TP1 à 2 R, TP2 à d2, TP3 à d3 (distances depuis l'entrée) ; stop à 1 R ; point mort
    après TP1 (option). Bougie d'entrée suivie à la minute après le remplissage. Rend (R total, coût en R)."""
    n = len(c)
    stop = entree - sens * risque
    cibles = np.array([entree + sens * 2.0 * risque, entree + sens * d2, entree + sens * d3])
    ouvert = np.array([True, True, True])
    gain = 0.0
    cout = entree * frais * 0.5 * facteur                 # entrée (ordre limite : écart seulement)
    # minutes restantes de la bougie d'entrée, puis bougies suivantes
    reste = max(b_min - f_min - 1, 0)
    pas_total = reste + tenue
    for s in range(pas_total):
        if s < reste:
            k = f_min + 1 + s
            po, ph, pl = mo[k], mh[k], ml[k]
        else:
            ib = i + 1 + (s - reste)
            if ib >= n:
                break
            po, ph, pl = o[ib], h[ib], l[ib]
        if (sens > 0 and pl <= stop) or (sens < 0 and ph >= stop):
            px = min(stop, po) if sens > 0 else max(stop, po)
            for q in range(3):
                if ouvert[q]:
                    gain += (px - entree) * sens / 3.0
                    cout += entree * frais * (0.5 + 0.5) / 3.0          # sortie + glissement du stop
                    ouvert[q] = False
            return (gain - cout) / risque, cout / risque
        for q in range(3):
            if ouvert[q] and ((sens > 0 and ph >= cibles[q]) or (sens < 0 and pl <= cibles[q])):
                px = max(cibles[q], po) if sens > 0 else min(cibles[q], po)
                gain += (px - entree) * sens / 3.0
                cout += entree * frais * 0.5 / 3.0
                ouvert[q] = False
                if q == 0 and point_mort:
                    stop = entree
        if not (ouvert[0] or ouvert[1] or ouvert[2]):
            return (gain - cout) / risque, cout / risque
    fin = min(n - 1, i + tenue)
    for q in range(3):
        if ouvert[q]:
            gain += (c[fin] - entree) * sens / 3.0
            cout += entree * frais * 0.5 / 3.0
    return (gain - cout) / risque, cout / risque


def trades_marche(marche: str, jusqua: pd.Timestamp, garder: set | None = None, construire=None,
                  petites=PETITES) -> pd.DataFrame:
    """`construire(unité)` -> Bougies (par défaut : les minutes vérifiées des 4 marchés de base)."""
    if construire is None:
        m1 = _m1(marche)
        construire = lambda u: bougies(marche, u, jusqua, m1)
    h1 = construire("H1")
    s_px, s_cf, s_ty = sommets_confirmes(h1.h, h1.l)
    s_t = h1.bt[s_cf] + h1.duree                          # heure où le sommet / creux est connu
    lignes = []
    for fond in FONDS:
        B = construire(fond)
        zh, zb, zs, zc, zdeb, zfin = K.zones_offre_demande(B.h, B.l, B.c, B.atr)
        fort = K.volume_fort(zh, zb, zc, B.h, B.l, B.v, B.atr)
        fin_conf = B.bt[zc] + B.duree                     # la zone de fond est connue à la clôture du départ
        mort = np.where(zfin < B.n, B.bt[np.minimum(zfin, B.n - 1)] + B.duree, np.iinfo(np.int64).max)
        for petite in petites:
            b = construire(petite)
            tenue = int(TENUE_JOURS * 86400e9 // b.duree)
            for z in np.flatnonzero(fort):
                sens = int(zs[z])
                a = int(np.searchsorted(b.bt, B.bt[zdeb[z]]))
                e = int(np.searchsorted(b.bt, fin_conf[z]))
                k = affiner(b.o, b.h, b.l, b.c, b.atr, a, e, sens, zh[z], zb[z])
                if k < 0:
                    continue
                rh, rb = min(b.h[k], zh[z]), max(b.l[k], zb[z])
                if rh <= rb:
                    continue
                proche, loin = (rh, rb) if sens > 0 else (rb, rh)
                f_proche, f_loin = (zh[z], zb[z]) if sens > 0 else (zb[z], zh[z])
                a_fond = B.atr[zc[z]]
                limite_t = fin_conf[z] + 500 * B.duree
                dedans, i_entree = False, -1
                for i in range(e, b.n):
                    if b.bt[i] > limite_t:
                        break
                    if not dedans and ((sens > 0 and b.l[i] <= f_proche) or (sens < 0 and b.h[i] >= f_proche)):
                        dedans = True
                    if dedans and ((sens > 0 and b.l[i] <= proche) or (sens < 0 and b.h[i] >= proche)):
                        i_entree = i
                        break
                    if dedans and ((sens > 0 and b.h[i] >= f_proche + 0.5 * a_fond) or
                                   (sens < 0 and b.l[i] <= f_proche - 0.5 * a_fond)):
                        break                                 # 1er contact fini sans toucher la zone affinée
                    if (sens > 0 and b.c[i] < f_loin) or (sens < 0 and b.c[i] > f_loin):
                        break
                if i_entree < 0:
                    continue
                i = i_entree
                entree = proche if not ((sens > 0 and b.o[i] < proche) or (sens < 0 and b.o[i] > proche)) else b.o[i]
                t_e = b.bt[i]
                # TP3 : plus proche zone opposée de fond valide à l'entrée
                ok = (zs == -sens) & (fin_conf < t_e) & (mort > t_e)
                bords = np.where(sens > 0, zb, zh)[ok]
                dist3 = (bords - entree) * sens
                dist3 = dist3[dist3 > 0]
                for marge in MARGES:
                    stop = loin - sens * marge * b.atr[i]
                    risque = (entree - stop) * sens
                    if risque <= 0 or not len(dist3) or dist3.min() < 2 * risque:
                        continue
                    d3 = float(dist3.min())
                    # TP2 : plus proche sommet (creux) H1 confirmé, entre TP1 et TP3
                    cand = (s_ty == sens) & (s_t <= t_e)
                    d2s = (s_px[cand] - entree) * sens
                    d2s = d2s[(d2s > 2 * risque) & (d2s < d3)]
                    d2 = float(d2s.min()) if len(d2s) else (2 * risque + d3) / 2
                    f_min, b_min = K._remplissage(b.o, b.mt, b.ml, b.mh, b.bt, b.duree, i, sens, proche)
                    for pm in POINT_MORT:
                        nom = f"Multi {fond}->{petite} marge {marge} {'point mort' if pm else 'sans point mort'}"
                        if garder is not None and nom not in garder:
                            continue
                        r, cr = trade_tiers(b.o, b.h, b.l, b.c, b.mo, b.mh, b.ml, i, f_min, b_min, sens, entree, risque,
                                            d2, d3, pm, tenue, b.frais, b.facteur[i])
                        r_inv, _ = trade_tiers(b.o, b.h, b.l, b.c, b.mo, b.mh, b.ml, i, f_min, b_min, -sens, entree,
                                               risque, d2, d3, pm, tenue, b.frais, b.facteur[i])
                        lignes.append({"famille": "multi", "concept": nom, "marche": marche, "unite": f"{fond}->{petite}",
                                       "entree": pd.Timestamp(b.t[i]), "sens": sens, "prix": entree, "R": r,
                                       "R_inverse": r_inv, "cout_R": cr, "stop_pct": risque / entree * 100,
                                       "reaction": False, "tp2_R": d2 / risque, "tp3_R": d3 / risque})
    return pd.DataFrame(lignes)


def apprentissage():
    tr = pd.concat([trades_marche(m, FIN_APPRENTISSAGE) for m in MARCHES], ignore_index=True)
    tr = tr[tr["entree"] < FIN_APPRENTISSAGE]
    tr.to_csv(VIE / "multi_trades_2015_2023.csv", index=False)
    res = []
    for (nom, marche), g in tr.groupby(["concept", "marche"]):
        ligne = {"concept": nom, "marche": marche}
        for p in ("choix", "verification"):
            for k, v in note(periode(g, p)).items():
                ligne[f"{p}_{k}"] = v
        ligne["retenu"] = bool(ligne.get("choix_force", -9) >= 2 and ligne.get("choix_R_moyen", -9) > 0
                               and ligne.get("verification_force", -9) > 0 and ligne.get("verification_R_moyen", -9) > 0)
        res.append(ligne)
    res = pd.DataFrame(res)
    res.to_csv(VIE / "multi_variantes_2015_2023.csv", index=False)
    cols = ["concept", "marche", "choix_trades", "choix_R_moyen", "choix_gagnants_pct", "choix_cout_R", "choix_stop_pct",
            "choix_force", "verification_trades", "verification_R_moyen", "verification_force", "retenu"]
    print(res[[c for c in cols if c in res]].round(3).to_string())
    print(f"retenues : {int(res['retenu'].sum())} / {len(res)}")


def cachee():
    verrou = VIE / "cachee_multi.json"
    if verrou.exists():
        print("Période cachée DÉJÀ évaluée :", verrou)
        return
    res = pd.read_csv(VIE / "multi_variantes_2015_2023.csv")
    ret = res[res["retenu"]]
    sortie = {"seuil": SEUIL, "quand": datetime.now().isoformat(timespec="seconds"), "candidats": []}
    lignes = []
    for marche in ret["marche"].unique():
        noms = set(ret[ret["marche"] == marche]["concept"])
        t = trades_marche(marche, pd.Timestamp("2100-01-01"), noms)
        lignes.append(periode(t, "cachee"))
    tr = pd.concat(lignes, ignore_index=True) if lignes else pd.DataFrame()
    for _, r in ret.iterrows():
        g = tr[(tr["concept"] == r["concept"]) & (tr["marche"] == r["marche"])] if len(tr) else tr
        x = note(g) if len(g) else {"trades": 0}
        x.update({"concept": r["concept"], "marche": r["marche"],
                  "prouve": bool(x.get("force", 0) >= SEUIL and x.get("R_moyen", 0) > 0)})
        sortie["candidats"].append(x)
        print(f"{r['concept']} {r['marche']} : {x.get('trades')} trades, {x.get('R_moyen', 0):+.3f} R, force "
              f"{x.get('force', 0):+.2f} (seuil {SEUIL:.2f}) -> {'PROUVÉ' if x['prouve'] else 'non prouvé'}")
    if len(tr):
        tr.to_csv(VIE / "multi_trades_cachee_2024_2026.csv", index=False)
    verrou.write_text(json.dumps(sortie, ensure_ascii=False, indent=1, default=str), encoding="utf-8")


# ---------------------------------------------------------------------- avenant 1 : les ~45 marchés (bougies de 15 min)
def construire_m15(sym: str, jusqua: pd.Timestamp):
    from collapsar.donnees import marches as dm
    from collapsar.mains.fiches import fiche
    d = dm.charger(sym, jusqua=jusqua)
    m = pd.DataFrame({"ny": pd.to_datetime(d["time"]) - pd.Timedelta(hours=7), "open": d["open"], "high": d["high"],
                      "low": d["low"], "close": d["close"], "volume": d["volume"].astype(float)})
    f = fiche(sym)
    fo = {"US100": 1.07, "US500": 1.16}.get(f.nom, 1.1 if f.famille == "indice" else 1.0)
    return lambda u: bougies(sym, u, jusqua, m, frais=f.frais, facteur_ouverture=fo, volume_inclus=True)


def _note_groupe(tr):
    res = []
    for nom, g in tr.groupby("concept"):
        ligne = {"concept": nom, "marches": g["marche"].nunique()}
        for p in ("choix", "verification"):
            for k, v in note(periode(g, p)).items():
                ligne[f"{p}_{k}"] = v
        ligne["retenu"] = bool(ligne.get("choix_force", -9) >= 2 and ligne.get("choix_R_moyen", -9) > 0
                               and ligne.get("verification_force", -9) > 0 and ligne.get("verification_R_moyen", -9) > 0)
        res.append(ligne)
    return pd.DataFrame(res)


def apprentissage45():
    from collapsar.donnees import marches as dm
    parts = []
    for sym in dm.liste_marches():
        try:
            t = trades_marche(sym, FIN_APPRENTISSAGE, construire=construire_m15(sym, FIN_APPRENTISSAGE), petites=("M15",))
        except Exception as e:
            print(f"{sym} : ignoré ({type(e).__name__}: {e})", flush=True)
            continue
        print(f"{sym} : {len(t)} trades", flush=True)
        parts.append(t)
    tr = pd.concat(parts, ignore_index=True)
    tr = tr[tr["entree"] < FIN_APPRENTISSAGE]
    tr.to_csv(VIE / "multi45_trades_2015_2023.csv", index=False)
    res = _note_groupe(tr)
    res.to_csv(VIE / "multi45_variantes_2015_2023.csv", index=False)
    cols = ["concept", "marches", "choix_trades", "choix_R_moyen", "choix_gagnants_pct", "choix_cout_R",
            "choix_stop_pct", "choix_force", "verification_trades", "verification_R_moyen", "verification_force", "retenu"]
    print(res[[c for c in cols if c in res]].round(3).to_string())


def cachee45():
    from collapsar.donnees import marches as dm
    verrou = VIE / "cachee_multi45.json"
    if verrou.exists():
        print("Période cachée DÉJÀ évaluée :", verrou)
        return
    res = pd.read_csv(VIE / "multi45_variantes_2015_2023.csv")
    ret = res[res["retenu"]]
    seuil = math.sqrt(2 * math.log(438))
    sortie = {"seuil": seuil, "quand": datetime.now().isoformat(timespec="seconds"), "candidats": []}
    if len(ret):
        noms = set(ret["concept"])
        parts = []
        for sym in dm.liste_marches():
            fin = pd.Timestamp("2100-01-01")
            try:
                parts.append(periode(trades_marche(sym, fin, noms, construire_m15(sym, fin), ("M15",)), "cachee"))
            except Exception:
                continue
        tr = pd.concat(parts, ignore_index=True)
        tr.to_csv(VIE / "multi45_trades_cachee_2024_2026.csv", index=False)
        for nom in noms:
            g = tr[tr["concept"] == nom]
            x = note(g) if len(g) else {"trades": 0}
            x.update({"concept": nom, "prouve": bool(x.get("force", 0) >= seuil and x.get("R_moyen", 0) > 0)})
            sortie["candidats"].append(x)
            print(f"{nom} : {x.get('trades')} trades, {x.get('R_moyen', 0):+.3f} R, force {x.get('force', 0):+.2f} "
                  f"(seuil {seuil:.2f}) -> {'PROUVÉ' if x['prouve'] else 'non prouvé'}")
    else:
        print("aucun candidat retenu : la période cachée reste fermée")
        return
    verrou.write_text(json.dumps(sortie, ensure_ascii=False, indent=1, default=str), encoding="utf-8")


if __name__ == "__main__":
    {"apprentissage": apprentissage, "cachee": cachee, "apprentissage45": apprentissage45, "cachee45": cachee45}[sys.argv[1] if len(sys.argv) > 1 else "apprentissage"]()
