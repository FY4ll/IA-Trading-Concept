"""Le LABORATOIRE SMC (15/10/2026) : applique docs/SMC_DEFINITIONS.md (figé) à XAUUSD, NAS100, US500, EURUSD en M5,
M15, H1. Phase « apprentissage » : données < 2024 seulement (choix 2015-2021 + vérification 2022-2023) ; phase
« cachee » : candidats retenus seulement, une seule fois (verrou vie/smc/cachee.json).
Depuis Test_IA : venv_gpu\\Scripts\\python.exe -u -m collapsar.regarder.smc.labo apprentissage|cachee
"""
from __future__ import annotations

import json
import math
import pickle
import sys
from datetime import datetime

import numpy as np
import pandas as pd

from collapsar.donnees import marches as dm
from collapsar.regarder.smc import noyaux as K
from collapsar.regarder.smc.bougies import MARCHES, UNITES, bougies, minutes

VIE = dm.RACINE / "collapsar" / "vie" / "smc"
FIN_APPRENTISSAGE = pd.Timestamp("2024-01-01")
PERIODES = {"choix": (2015, 2021), "verification": (2022, 2023), "cachee": (2024, 2026)}
VARIANTES_TOTAL = 366
SEUIL = max(3.0, math.sqrt(2 * math.log(VARIANTES_TOTAL)))
KZ_LONDRES, KZ_NY = (120, 300), (420, 600)
CONCEPTS = ["OB", "FVG", "Inverse FVG", "Breaker", "Balayage", "BOS", "CHoCH"]
COMBOS = {1: "OB + FVG du départ + killzone NY", 2: "Balayage + FVG", 3: "OB + premium/discount",
          4: "Breaker + killzone", 5: "CHoCH + entrée FVG", 6: "Balayage + CHoCH", 7: "FVG + killzone NY",
          8: "OB qui provoque un BOS", 9: "Zone perso (1er contact) + killzone NY", 10: "Inverse FVG + premium/discount"}


def _m1(marche: str) -> pd.DataFrame:
    f = VIE / "cache" / f"{marche}.pkl"
    if f.exists():
        m = pickle.loads(f.read_bytes())
        if m["ny"].dtype != np.dtype("datetime64[ns]"):     # 16/10 (audit, défaut 1) : caches du 15/10 écrits en µs
            m["ny"] = m["ny"].astype("datetime64[ns]")
        return m
    f.parent.mkdir(parents=True, exist_ok=True)
    m = minutes(marche)
    f.write_bytes(pickle.dumps(m))
    return m


def _ligne(b, famille, nom, e, entree, r, r_inv, cr, stop_pct, reac, sens):
    return {"famille": famille, "concept": nom, "marche": b.marche, "unite": b.unite, "entree": b.t[e], "sens": sens,
            "prix": entree, "R": r, "R_inverse": r_inv, "cout_R": cr, "stop_pct": stop_pct, "reaction": bool(reac)}


def zones_trades(b, famille, nom, zh, zb, zs, zc, filtre=None):
    """filtre(bougie d'entrée, sens, prix) -> garder ?"""
    lignes, temoins = [], []
    rng = np.random.default_rng(len(zc) + b.n)
    for z in range(len(zc)):
        e, px, r, ri, cr, sp, reac = K.trade_zone(b.o, b.h, b.l, b.c, b.atr, b.facteur, b.frais, b.mt, b.mo, b.mh,
                                                    b.ml, b.bt, b.duree, zh[z], zb[z],
                                                    int(zs[z]), int(zc[z]), K.MARGE, K.RR, K.TENUE, K.VIE)
        if e < 0 or (filtre is not None and not filtre(e, int(zs[z]), px)):
            continue
        lignes.append(_ligne(b, famille, nom, e, px, r, ri, cr, sp, reac, int(zs[z])))
        # zone au hasard : même taille, même distance au prix, même côté, à un moment tiré au hasard
        s = int(zs[z])
        proche = zh[z] if s > 0 else zb[z]
        dist = (b.c[zc[z]] - proche) * s
        larg = zh[z] - zb[z]
        rr_ = int(rng.integers(100, b.n - 600))
        p2 = b.c[rr_] - s * dist
        touche, reac2 = K.reaction_zone(b.h, b.l, b.c, b.atr[rr_], p2, p2 - s * larg, s, rr_, K.VIE)
        if touche:
            temoins.append({"famille": famille, "concept": nom, "marche": b.marche, "unite": b.unite,
                            "entree": b.t[rr_], "reaction": bool(reac2)})
    return lignes, temoins


def signaux_trades(b, famille, nom, idx, sens):
    lignes, temoins = [], []
    rng = np.random.default_rng(len(idx) + 7)
    for i, s in zip(idx, sens):
        e, px, r, ri, cr, sp, reac = K.trade_signal(b.o, b.h, b.l, b.c, b.atr, b.facteur, b.frais, int(i), int(s),
                                                     K.RR, K.TENUE)
        if e < 0:
            continue
        lignes.append(_ligne(b, famille, nom, e, px, r, ri, cr, sp, reac, int(s)))
        rr_ = int(rng.integers(100, b.n - 100))
        temoins.append({"famille": famille, "concept": nom, "marche": b.marche, "unite": b.unite, "entree": b.t[rr_],
                        "reaction": bool(K.reaction_signal(b.h, b.l, b.atr, rr_, int(s), b.o[rr_]))})
    return lignes, temoins


def tout(b, garder=None):
    """Tous les concepts, combinaisons et variantes de la stratégie personnelle sur un jeu de bougies. `garder` :
    ensemble de noms de variantes à calculer (phase cachée) ou None (tout)."""
    veut = lambda nom: garder is None or nom in garder
    cassure, milieu, eh, el = K.structure(b.h, b.l, b.c, b.atr)
    oh, ob, os_, oc, oj = K.order_blocks(b.o, b.h, b.l, b.c, b.atr)
    fh, fb, fs, fc, fcomble = K.fvgs(b.h, b.l, b.atr)
    ii, ic = K.retournees(fh, fb, fs, fc, b.c)
    bi, bc = K.retournees(oh, ob, os_, oc, b.c)
    kz = lambda ny_only: (lambda e, s, p: (KZ_NY[0] <= b.minute[e] < KZ_NY[1]) or
                          (not ny_only and KZ_LONDRES[0] <= b.minute[e] < KZ_LONDRES[1]))
    pd_ok = lambda e, s, p: not np.isnan(milieu[e - 1]) and ((s > 0 and p < milieu[e - 1]) or (s < 0 and p > milieu[e - 1]))
    # balayages : plus haut / bas de la veille (premier du jour) ou sommets / creux égaux
    bal_i, bal_s = [], []
    deja_h, deja_l = -1, -1
    for i in range(b.n):
        if b.haut_veille[i] > 0 and b.h[i] > b.haut_veille[i] and b.c[i] < b.haut_veille[i] and deja_h != b.jour[i]:
            bal_i.append(i); bal_s.append(-1); deja_h = b.jour[i]
        elif not np.isnan(eh[i]) and b.c[i] < eh[i]:
            bal_i.append(i); bal_s.append(-1)
        if b.bas_veille[i] > 0 and b.l[i] < b.bas_veille[i] and b.c[i] > b.bas_veille[i] and deja_l != b.jour[i]:
            bal_i.append(i); bal_s.append(1); deja_l = b.jour[i]
        elif not np.isnan(el[i]) and b.c[i] > el[i]:
            bal_i.append(i); bal_s.append(1)
    bal_i, bal_s = np.array(bal_i, np.int64), np.array(bal_s, np.int64)
    lignes, temoins = [], []

    def ajoute(res):
        lignes.extend(res[0]); temoins.extend(res[1])

    # --- concepts seuls
    if veut("OB"):
        ajoute(zones_trades(b, "concept", "OB", oh, ob, os_, oc))
    if veut("FVG"):
        ajoute(zones_trades(b, "concept", "FVG", fh, fb, fs, fc))
    if veut("Inverse FVG"):
        ajoute(zones_trades(b, "concept", "Inverse FVG", fh[ii], fb[ii], -fs[ii], ic))
    if veut("Breaker"):
        ajoute(zones_trades(b, "concept", "Breaker", oh[bi], ob[bi], -os_[bi], bc))
    if veut("Balayage"):
        ajoute(signaux_trades(b, "concept", "Balayage", bal_i, bal_s))
    bos = np.flatnonzero(np.abs(cassure) == 1)
    choch = np.flatnonzero(np.abs(cassure) == 2)
    if veut("BOS"):
        ajoute(signaux_trades(b, "concept", "BOS", bos, np.sign(cassure[bos])))
    if veut("CHoCH"):
        ajoute(signaux_trades(b, "concept", "CHoCH", choch, np.sign(cassure[choch])))
    # --- combinaisons (listées d'avance)
    if veut(COMBOS[1]):
        avec_fvg = np.array([np.any(fs[np.searchsorted(fc, oj[z], "right"):np.searchsorted(fc, oc[z], "right")] == os_[z])
                             for z in range(len(oc))], bool)
        ajoute(zones_trades(b, "combinaison", COMBOS[1], oh[avec_fvg], ob[avec_fvg], os_[avec_fvg], oc[avec_fvg], kz(True)))

    def fvg_apres(idx, sens, fenetre):
        z = []
        for i, s in zip(idx, sens):
            a, b_ = np.searchsorted(fc, i, "right"), np.searchsorted(fc, i + fenetre, "right")
            k = np.flatnonzero(fs[a:b_] == s)
            if len(k):
                z.append(a + k[0])
        return np.array(z, np.int64)
    if veut(COMBOS[2]):
        z = fvg_apres(bal_i, bal_s, 5)
        ajoute(zones_trades(b, "combinaison", COMBOS[2], fh[z], fb[z], fs[z], fc[z]))
    if veut(COMBOS[3]):
        ajoute(zones_trades(b, "combinaison", COMBOS[3], oh, ob, os_, oc, pd_ok))
    if veut(COMBOS[4]):
        ajoute(zones_trades(b, "combinaison", COMBOS[4], oh[bi], ob[bi], -os_[bi], bc, kz(False)))
    if veut(COMBOS[5]):
        z = fvg_apres(choch, np.sign(cassure[choch]), 5)
        ajoute(zones_trades(b, "combinaison", COMBOS[5], fh[z], fb[z], fs[z], fc[z]))
    if veut(COMBOS[6]):
        idx, sen = [], []
        for i, s in zip(bal_i, bal_s):
            k = np.flatnonzero(cassure[i + 1:i + 11] == 2 * s)
            if len(k):
                idx.append(i + 1 + k[0]); sen.append(s)
        ajoute(signaux_trades(b, "combinaison", COMBOS[6], np.array(idx, np.int64), np.array(sen, np.int64)))
    if veut(COMBOS[7]):
        ajoute(zones_trades(b, "combinaison", COMBOS[7], fh, fb, fs, fc, kz(True)))
    if veut(COMBOS[8]):
        bos_ok = np.array([np.any(cassure[oj[z] + 1:oc[z] + 1] == os_[z]) for z in range(len(oc))], bool)
        ajoute(zones_trades(b, "combinaison", COMBOS[8], oh[bos_ok], ob[bos_ok], os_[bos_ok], oc[bos_ok]))
    if veut(COMBOS[10]):
        ajoute(zones_trades(b, "combinaison", COMBOS[10], fh[ii], fb[ii], -fs[ii], ic, pd_ok))
    # --- la stratégie personnelle
    zh, zb, zs, zc, zdeb, zfin = K.zones_offre_demande(b.h, b.l, b.c, b.atr)
    fort = K.volume_fort(zh, zb, zc, b.h, b.l, b.v, b.atr)
    ordre = np.argsort(fc, kind="stable")
    fh_, fb_, fc_, fcom_ = fh[ordre], fb[ordre], fc[ordre], fcomble[ordre]
    rng = np.random.default_rng(b.n)
    for contact in (1, 2, 3):
        for filtre in (False, True):
            for marge in (0.2, 0.5):
                nom = f"Perso contact {contact} {'avec' if filtre else 'sans'} filtre FVG marge {marge}"
                nom9 = COMBOS[9] if (contact == 1 and not filtre and marge == 0.2) else None
                if not (veut(nom) or (nom9 and veut(nom9))):
                    continue
                for z in np.flatnonzero(fort):
                    e, px, r, ri, cr, sp, reac, raison = K.trade_perso(
                        b.o, b.h, b.l, b.c, b.atr, b.facteur, b.frais, b.mt, b.mo, b.mh, b.ml, b.bt, b.duree, int(z),
                        zh, zb, zs, zc, zfin, fh_, fb_, fc_, fcom_, contact, filtre, marge, K.VIE)
                    if e < 0:
                        continue
                    if veut(nom):
                        lignes.append(_ligne(b, "perso", nom, e, px, r, ri, cr, sp, reac, int(zs[z])))
                        s = int(zs[z])
                        proche = zh[z] if s > 0 else zb[z]
                        rr_ = int(rng.integers(300, b.n - 600))
                        p2 = b.c[rr_] - s * (b.c[zc[z]] - proche) * s
                        t2, r2 = K.reaction_zone(b.h, b.l, b.c, b.atr[rr_], p2, p2 - s * (zh[z] - zb[z]), s, rr_, K.VIE)
                        if t2:
                            temoins.append({"famille": "perso", "concept": nom, "marche": b.marche, "unite": b.unite,
                                            "entree": b.t[rr_], "reaction": bool(r2)})
                    if nom9 and veut(nom9) and KZ_NY[0] <= b.minute[e] < KZ_NY[1]:
                        lignes.append(_ligne(b, "combinaison", nom9, e, px, r, ri, cr, sp, reac, int(zs[z])))
    return pd.DataFrame(lignes), pd.DataFrame(temoins)


def periode(df: pd.DataFrame, nom: str) -> pd.DataFrame:
    a, z = PERIODES[nom]
    an = pd.to_datetime(df["entree"]).dt.year
    return df[(an >= a) & (an <= z)]


def note(t: pd.DataFrame) -> dict:
    n = len(t)
    if n < 20:
        return {"trades": n}
    d = (t["R"] - t["R_inverse"]) / 2
    sd = d.std(ddof=1)
    r = t["R"].to_numpy()
    cumul = np.cumsum(r)
    pire = float((cumul - np.maximum.accumulate(np.r_[0, cumul])[1:]).min())
    serie = pire_serie = 0
    for x in r:
        serie = serie + 1 if x < 0 else 0
        pire_serie = max(pire_serie, serie)
    return {"trades": n, "R_moyen": float(r.mean()), "gagnants_pct": float((r > 0).mean() * 100),
            "cout_R": float(t["cout_R"].mean()), "stop_pct": float(t["stop_pct"].mean()),
            "force": float(d.mean() / sd * math.sqrt(n)) if sd > 0 else 0.0,
            "reaction_pct": float(t["reaction"].mean() * 100), "pire_serie": pire_serie, "pire_baisse_R": pire}


def apprentissage():
    lignes, temoins = [], []
    for marche in MARCHES:
        m1 = _m1(marche)
        for unite in UNITES:
            t0 = datetime.now()
            b = bougies(marche, unite, FIN_APPRENTISSAGE, m1)
            l_, t_ = tout(b)
            lignes.append(l_); temoins.append(t_)
            print(f"{marche} {unite} : {b.n} bougies, {len(l_)} trades ({(datetime.now() - t0).seconds} s)", flush=True)
    tr = pd.concat(lignes, ignore_index=True)
    te = pd.concat(temoins, ignore_index=True)
    tr = tr[pd.to_datetime(tr["entree"]) < FIN_APPRENTISSAGE]
    tr.to_csv(VIE / "trades_2015_2023.csv", index=False)
    te.to_csv(VIE / "temoins_hasard_2015_2023.csv", index=False)
    resultats = []
    for (fam, nom, marche, unite), g in tr.groupby(["famille", "concept", "marche", "unite"]):
        h = te[(te["concept"] == nom) & (te["marche"] == marche) & (te["unite"] == unite)]
        ligne = {"famille": fam, "concept": nom, "marche": marche, "unite": unite}
        for p in ("choix", "verification"):
            x = note(periode(g, p))
            for k, v in x.items():
                ligne[f"{p}_{k}"] = v
            hp = periode(h, p) if len(h) else h
            ligne[f"{p}_reaction_hasard_pct"] = float(hp["reaction"].mean() * 100) if len(hp) else np.nan
        ligne["retenu"] = bool(ligne.get("choix_force", -9) >= 2 and ligne.get("choix_R_moyen", -9) > 0
                               and ligne.get("verification_force", -9) > 0 and ligne.get("verification_R_moyen", -9) > 0)
        resultats.append(ligne)
    res = pd.DataFrame(resultats)
    res.to_csv(VIE / "variantes_2015_2023.csv", index=False)
    print(f"{len(res)} variantes mesurées ; retenues pour la période cachée : {int(res['retenu'].sum())}")
    print(res[res["retenu"]][["concept", "marche", "unite", "choix_force", "choix_R_moyen", "verification_force",
                              "verification_R_moyen"]].to_string())


def cachee():
    verrou = VIE / "cachee.json"
    if verrou.exists():
        print("Période cachée DÉJÀ évaluée (une seule fois) :", verrou)
        return
    res = pd.read_csv(VIE / "variantes_2015_2023.csv")
    ret = res[res["retenu"]]
    lignes = []
    for marche in ret["marche"].unique():
        m1 = _m1(marche)
        for unite in ret[ret["marche"] == marche]["unite"].unique():
            noms = set(ret[(ret["marche"] == marche) & (ret["unite"] == unite)]["concept"])
            b = bougies(marche, unite, pd.Timestamp("2100-01-01"), m1)
            l_, _ = tout(b, garder=noms)
            l_ = l_[l_["concept"].isin(noms)]
            lignes.append(periode(l_, "cachee"))
    tr = pd.concat(lignes, ignore_index=True) if lignes else pd.DataFrame()
    sortie = {"seuil": SEUIL, "quand": datetime.now().isoformat(timespec="seconds"), "candidats": []}
    for _, r in ret.iterrows():
        g = tr[(tr["concept"] == r["concept"]) & (tr["marche"] == r["marche"]) & (tr["unite"] == r["unite"])] if len(tr) else tr
        x = note(g) if len(g) else {"trades": 0}
        x.update({"concept": r["concept"], "marche": r["marche"], "unite": r["unite"],
                  "prouve": bool(x.get("force", 0) >= SEUIL and x.get("R_moyen", 0) > 0)})
        sortie["candidats"].append(x)
        print(f"{r['concept']} {r['marche']} {r['unite']} : {x.get('trades')} trades, {x.get('R_moyen', 0):+.3f} R, "
              f"force {x.get('force', 0):+.2f} (seuil {SEUIL:.2f}) -> {'PROUVÉ' if x['prouve'] else 'non prouvé'}")
    if len(tr):
        tr.to_csv(VIE / "trades_cachee_2024_2026.csv", index=False)
    verrou.write_text(json.dumps(sortie, ensure_ascii=False, indent=1, default=str), encoding="utf-8")


if __name__ == "__main__":
    VIE.mkdir(parents=True, exist_ok=True)
    {"apprentissage": apprentissage, "cachee": cachee}[sys.argv[1] if len(sys.argv) > 1 else "apprentissage"]()
