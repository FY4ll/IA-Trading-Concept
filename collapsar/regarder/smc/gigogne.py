"""ZONES GIGOGNES avec l'indicateur du chef de projet (docs/CASCADE_ZONES.md, avenant 1, figé).
Depuis Test_IA : venv_gpu\\Scripts\\python.exe -u -m collapsar.regarder.smc.gigogne apprentissage|cachee
"""
from __future__ import annotations

import json
import math
import sys
from datetime import datetime

import numpy as np
import pandas as pd

from collapsar.regarder.smc import noyaux as K
from collapsar.regarder.smc.bougies import MARCHES
from collapsar.regarder.smc.labo import VIE, note, periode
from collapsar.regarder.smc.multi import construire_m15, sommets_confirmes
from collapsar.regarder.smc.nono import (ATTENTE, STOPS, TENUE_JOURS, _construire_minutes, effacement, trade_nono,
                                          zones_nono)

FIN_APPRENTISSAGE = pd.Timestamp("2024-01-01")
SEUIL = math.sqrt(2 * math.log(468))
ECHELLE_MINUTES = ["D1", "H4", "H1", "M30", "M15", "M5", "M3"]
ECHELLE_45 = ["D1", "H4", "H1", "M30", "M15"]
DEPARTS = ("D1", "H4")
JAMAIS = np.iinfo(np.int64).max


def preparer(construire, echelle) -> dict:
    """Les bougies de chaque unité, les zones zones supply and demand (avec leur effacement sur la plus petite unité) et les sommets H1."""
    B = {u: construire(u) for u in echelle}
    base = B[echelle[-1]]                                 # le « graphique » : la plus petite unité
    h1 = B["H1"]
    s_px, s_cf, s_ty = sommets_confirmes(h1.h, h1.l)
    Z = {}
    for u in echelle:
        b = B[u]
        zh, zb, zm, zs, zc = zones_nono(b.o, b.h, b.l, b.c)
        conf = b.bt[zc] + b.duree
        Z[u] = (zh, zb, zm, zs, conf, effacement(zm, zs, conf, base.bt, base.duree, base.c))
    return {"B": B, "Z": Z, "base": base, "echelle": echelle, "sommets": (s_px, s_ty, h1.bt[s_cf] + h1.duree)}


def entrees(P: dict, depart: str):
    """Chaque entrée de la méthode gigogne depuis l'unité `depart` : dict (zone de départ, unité et zone d'entrée,
    bougie et prix d'entrée, risque derrière la zone, profondeur de la chaîne)."""
    B, Z, base, echelle = P["B"], P["Z"], P["base"], P["echelle"]
    xh, xb, xm, xs, xconf, xfin = Z[depart]
    dessous = echelle[echelle.index(depart) + 1:]
    for z in range(len(xs)):
        d = int(xs[z])
        proche = xh[z] if d > 0 else xb[z]
        k0 = int(np.searchsorted(base.bt, xconf[z]))
        k1 = int(np.searchsorted(base.bt, xfin[z])) if xfin[z] < JAMAIS else base.n
        if k1 <= k0:
            continue
        seg = base.l[k0:k1] <= proche if d > 0 else base.h[k0:k1] >= proche
        if not seg.any():
            continue
        t_in = base.bt[k0 + int(np.argmax(seg))]
        # descente : à chaque unité, la zone vivante du même sens qui chevauche la dernière retenue
        haut, bas, unite, zi, profondeur = xh[z], xb[z], depart, z, 1
        for u in dessous:
            uh, ub, um, us, uconf, ufin = Z[u]
            ok = (us == d) & (uconf <= t_in) & (ufin > t_in) & (ub <= haut) & (uh >= bas)
            if ok.any():
                idx = np.flatnonzero(ok)
                zi = int(idx[np.argmax(uh[idx])]) if d > 0 else int(idx[np.argmin(ub[idx])])
                haut, bas, unite, profondeur = uh[zi], ub[zi], u, profondeur + 1
        if unite == depart:
            continue                                      # pas de zone dans la zone : pas de trade
        uh, ub, um, us, uconf, ufin = Z[unite]
        BY = B[unite]
        milieu = um[zi]
        e0 = int(np.searchsorted(BY.bt, t_in))
        limite = min(xfin[z], ufin[zi])
        e1 = min(BY.n, e0 + ATTENTE, int(np.searchsorted(BY.bt, limite)) if limite < JAMAIS else BY.n)
        if e1 <= e0:
            continue
        touche = BY.l[e0:e1] <= milieu if d > 0 else BY.h[e0:e1] >= milieu
        if not touche.any():
            continue
        i = e0 + int(np.argmax(touche))
        entree = milieu if not ((d > 0 and BY.o[i] < milieu) or (d < 0 and BY.o[i] > milieu)) else BY.o[i]
        loin = ub[zi] if d > 0 else uh[zi]
        risque_zone = (entree - (loin - d * 0.2 * BY.atr[i])) * d
        if risque_zone <= 0:
            continue
        yield {"z": z, "sens": d, "unite": unite, "zi": zi, "i": i, "entree": entree, "milieu": milieu,
               "risque_zone": risque_zone, "profondeur": profondeur, "t_in": t_in,
               "largeur_atr": (uh[zi] - ub[zi]) / max(BY.atr[i], 1e-12)}


def trades(marche: str, construire, echelle, garder=None, planchers=None) -> pd.DataFrame:
    """`planchers` (avenant 2) : stop minimum en part de l'ATR journalier ; départ H4 et stop A seulement."""
    P = preparer(construire, echelle)
    B, Z = P["B"], P["Z"]
    s_px, s_ty, s_t = P["sommets"]
    BD = B["D1"]
    lignes = []
    for depart in (("H4",) if planchers else DEPARTS):
        noms = {s: f"Gigogne départ {depart} stop {s}" for s in STOPS}
        if planchers:
            noms = {p: f"Gigogne H4 stop A plancher {p}" for p in planchers}
        if garder is not None and not (set(noms.values()) & garder):
            continue
        xh, xb, xm, xs, xconf, xfin = Z[depart]
        for e in entrees(P, depart):
            BY, i, d = B[e["unite"]], e["i"], e["sens"]
            t_e = BY.bt[i]
            jd = int(np.searchsorted(BD.bt, t_e, "right")) - 2          # dernier jour COMPLET
            atr_jour = BD.atr[jd] if jd >= 0 else np.nan
            for cle in (planchers or [None]):
                risque = e["risque_zone"] if cle is None else max(e["risque_zone"], cle * atr_jour)
                if not np.isfinite(risque):
                    continue
                lignes += _un_trade(BY, i, d, e["entree"], risque, xs, xb, xh, xconf, xfin, s_ty, s_t, s_px,
                                    e["milieu"], noms, garder, marche, depart, e["unite"], cle)
    return pd.DataFrame(lignes)

def _un_trade(BY, i, d, entree, risque, xs, xb, xh, xconf, xfin, s_ty, s_t, s_px, milieu, noms, garder, marche, depart,
              unite, cle) -> list[dict]:
    """Un trade (et son jumeau) avec un risque donné ; `cle` = plancher du stop (avenant 2) ou None (stops A / B)."""
    lignes = []
    t_e = BY.bt[i]
    okx = (xs == -d) & (xconf < t_e) & (xfin > t_e)
    bords = (xb if d > 0 else xh)[okx]
    dist3 = (bords - entree) * d
    dist3 = dist3[dist3 >= 2 * risque]
    if not len(dist3):
        return lignes
    d3 = float(dist3.min())
    cand = (s_ty == d) & (s_t <= t_e)
    d2s = (s_px[cand] - entree) * d
    d2s = d2s[(d2s > 2 * risque) & (d2s < d3)]
    d2 = float(d2s.min()) if len(d2s) else (2 * risque + d3) / 2
    f_min, b_min = K._remplissage(BY.o, BY.mt, BY.ml, BY.mh, BY.bt, BY.duree, i, d, milieu)
    tenue = int(TENUE_JOURS * 86400e9 // BY.duree)
    for s in ([cle] if cle is not None else STOPS):
        if garder is not None and noms[s] not in garder:
            continue
        sortie_b = cle is None and s == "B"
        r, cr = trade_nono(BY.o, BY.h, BY.l, BY.c, BY.mo, BY.mh, BY.ml, i, f_min, b_min, d, entree, risque, d2, d3,
                           sortie_b, tenue, BY.frais, BY.facteur[i])
        ri, _ = trade_nono(BY.o, BY.h, BY.l, BY.c, BY.mo, BY.mh, BY.ml, i, f_min, b_min, -d, entree, risque, d2, d3,
                           sortie_b, tenue, BY.frais, BY.facteur[i])
        lignes.append({"famille": "gigogne", "concept": noms[s], "marche": marche, "unite": f"{depart}->{unite}",
                       "entree": pd.Timestamp(BY.t[i]), "sens": d, "prix": entree, "R": r, "R_inverse": ri,
                       "cout_R": cr, "stop_pct": risque / entree * 100, "reaction": False, "tp3_R": d3 / risque,
                       "etage_entree": unite})
    return lignes

def _juger(tr):
    res = []
    for (groupe, nom), g in tr.groupby(["groupe", "concept"]):
        ligne = {"groupe": groupe, "concept": nom, "marches": g["marche"].nunique()}
        for p in ("choix", "verification"):
            for k, v in note(periode(g, p)).items():
                ligne[f"{p}_{k}"] = v
        ligne["retenu"] = bool(ligne.get("choix_force", -9) >= 2 and ligne.get("choix_R_moyen", -9) > 0
                               and ligne.get("verification_force", -9) > 0 and ligne.get("verification_R_moyen", -9) > 0)
        res.append(ligne)
    return pd.DataFrame(res)


def _tous(jusqua, garder=None, planchers=None):
    from collapsar.donnees import marches as dm
    parts = []
    for marche in MARCHES:
        t = trades(marche, _construire_minutes(marche, jusqua), ECHELLE_MINUTES, garder, planchers)
        t["groupe"] = "4 marchés (minutes)"
        parts.append(t)
        print(f"[minutes] {marche} : {len(t)} trades", flush=True)
    for sym in dm.liste_marches():
        try:
            t = trades(sym, construire_m15(sym, jusqua), ECHELLE_45, garder, planchers)
        except Exception as e:
            print(f"[45] {sym} ignoré ({type(e).__name__}: {e})", flush=True)
            continue
        t["groupe"] = "45 marchés (15 min)"
        parts.append(t)
    return pd.concat([p for p in parts if len(p)], ignore_index=True)


def apprentissage():
    tr = _tous(FIN_APPRENTISSAGE)
    tr = tr[tr["entree"] < FIN_APPRENTISSAGE]
    tr.to_csv(VIE / "gigogne_trades_2015_2023.csv", index=False)
    res = _juger(tr)
    res.to_csv(VIE / "gigogne_variantes_2015_2023.csv", index=False)
    pd.set_option("display.width", 250)
    cols = ["groupe", "concept", "marches", "choix_trades", "choix_R_moyen", "choix_gagnants_pct", "choix_cout_R",
            "choix_stop_pct", "choix_force", "verification_trades", "verification_R_moyen", "verification_force", "retenu"]
    print(res[[c for c in cols if c in res]].round(3).to_string())
    print("étages d'entrée :", tr.drop_duplicates(["marche", "entree"])["etage_entree"].value_counts().to_dict())


def cachee():
    verrou = VIE / "cachee_gigogne.json"
    if verrou.exists():
        print("Période cachée DÉJÀ évaluée :", verrou)
        return
    res = pd.read_csv(VIE / "gigogne_variantes_2015_2023.csv")
    ret = res[res["retenu"]]
    if not len(ret):
        print("aucun candidat retenu : la période cachée reste fermée")
        return
    tr = periode(_tous(pd.Timestamp("2100-01-01"), set(ret["concept"])), "cachee")
    tr.to_csv(VIE / "gigogne_trades_cachee_2024_2026.csv", index=False)
    sortie = {"seuil": SEUIL, "quand": datetime.now().isoformat(timespec="seconds"), "candidats": []}
    for _, r in ret.iterrows():
        g = tr[(tr["groupe"] == r["groupe"]) & (tr["concept"] == r["concept"])]
        x = note(g) if len(g) else {"trades": 0}
        x.update({"groupe": r["groupe"], "concept": r["concept"],
                  "prouve": bool(x.get("force", 0) >= SEUIL and x.get("R_moyen", 0) > 0)})
        sortie["candidats"].append(x)
        print(f"{r['groupe']} | {r['concept']} : {x.get('trades')} trades, {x.get('R_moyen', 0):+.3f} R, force "
              f"{x.get('force', 0):+.2f} (seuil {SEUIL:.2f}) -> {'PROUVÉ' if x['prouve'] else 'non prouvé'}")
    verrou.write_text(json.dumps(sortie, ensure_ascii=False, indent=1, default=str), encoding="utf-8")


# ---------------------------------------------------------------------- avenant 2 : le stop minimum
PLANCHERS = (0.1, 0.2, 0.3)


def apprentissage_plancher():
    tr = _tous(FIN_APPRENTISSAGE, planchers=PLANCHERS)
    tr = tr[tr["entree"] < FIN_APPRENTISSAGE]
    tr.to_csv(VIE / "plancher_trades_2015_2023.csv", index=False)
    res = _juger(tr)
    res.to_csv(VIE / "plancher_variantes_2015_2023.csv", index=False)
    pd.set_option("display.width", 250)
    cols = ["groupe", "concept", "choix_trades", "choix_R_moyen", "choix_gagnants_pct", "choix_cout_R", "choix_stop_pct",
            "choix_force", "verification_trades", "verification_R_moyen", "verification_force", "retenu"]
    print(res[[c for c in cols if c in res]].round(3).to_string())


def cachee_plancher():
    verrou = VIE / "cachee_plancher.json"
    if verrou.exists():
        print("Période cachée DÉJÀ évaluée :", verrou)
        return
    res = pd.read_csv(VIE / "plancher_variantes_2015_2023.csv")
    ret = res[res["retenu"]]
    if not len(ret):
        print("aucun candidat retenu : la période cachée reste fermée")
        return
    seuil = math.sqrt(2 * math.log(474))
    tr = periode(_tous(pd.Timestamp("2100-01-01"), set(ret["concept"]), PLANCHERS), "cachee")
    tr.to_csv(VIE / "plancher_trades_cachee_2024_2026.csv", index=False)
    sortie = {"seuil": seuil, "quand": datetime.now().isoformat(timespec="seconds"), "candidats": []}
    for _, r in ret.iterrows():
        g = tr[(tr["groupe"] == r["groupe"]) & (tr["concept"] == r["concept"])]
        x = note(g) if len(g) else {"trades": 0}
        x.update({"groupe": r["groupe"], "concept": r["concept"],
                  "prouve": bool(x.get("force", 0) >= seuil and x.get("R_moyen", 0) > 0)})
        sortie["candidats"].append(x)
        print(f"{r['groupe']} | {r['concept']} : {x.get('trades')} trades, {x.get('R_moyen', 0):+.3f} R, force "
              f"{x.get('force', 0):+.2f} (seuil {seuil:.2f}) -> {'PROUVÉ' if x['prouve'] else 'non prouvé'}")
    verrou.write_text(json.dumps(sortie, ensure_ascii=False, indent=1, default=str), encoding="utf-8")


if __name__ == "__main__":
    {"apprentissage": apprentissage, "cachee": cachee, "plancher": apprentissage_plancher,
     "cachee_plancher": cachee_plancher}[sys.argv[1] if len(sys.argv) > 1 else "apprentissage"]()
