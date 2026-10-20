"""AVIS + EXÉCUTION (18/10/2026) : l'avis du matin (ecole/precision/avis.py ; horizon 20 j par amendement, 5 j avec
--h5 ; --brut = avis avant calibration, --v2 = essai 3 années glissantes, choix sur 2014-2022) donne le SENS ; ses zones
donnent l'ENDROIT ; stop juste derrière la structure (élargi : frais <= 0,03 R), stop suiveur 1 h, aucun objectif.
Plan figé : vie/hypernova/avis/plan_fige.md. Moteur identique à la piste « monde » (regarder/pistes/monde.py :
même géométrie, même simulateur `mouvements.jouer`, jumeau, fausses zones, plafond 2R, compte FTMO).

Scénarios : REB (rebond sur ses zones D1 / 4 h / 1 h dans le sens de l'avis), CAS (cassure dans le sens de l'avis),
MAR (au marché à 08h00, stop derrière le dernier creux / sommet 4 h + 0,1 A). Seuil de conviction 55 / 60 / 65 %.
Choix (scénario, seuil) sur 2022 ; mesure 2023 ; lecture 01/2024 -> 09/2025 (déjà vue par d'autres pistes).

Depuis Test_IA : venv_gpu\\Scripts\\python.exe -u -m collapsar.regarder.pistes.avis_execution
"""
from __future__ import annotations

import json
import time
from datetime import datetime

import numpy as np
import pandas as pd

from collapsar.ecole.precision import avis as AV
from collapsar.ecole.precision import donnees as D
from collapsar.ecole.precision import juge_trade as JT
from collapsar.ecole.precision.reglages import R
from collapsar.regarder.pistes import monde as PM
from collapsar.regarder.pistes import mouvements as M

SORTIE = AV.SORTIE / "execution"
QUINZE_NS, HEURE_NS, JOUR_NS = AV.QUINZE_NS, AV.HEURE_NS, AV.JOUR_NS
MOIS_NS = 30.4375 * JOUR_NS
PERIODES = {"reglage": ("2022-01-01", "2023-01-01"), "mesure": ("2023-01-01", "2024-01-01"),
            "lecture": ("2024-01-01", "2025-10-01")}
NOM_P = {"reglage": "2022 (choix)", "mesure": "2023 (mesure)", "lecture": "01/2024 -> 09/2025 (lecture, déjà vue)"}
SCENARIOS = ("REB", "CAS", "MAR")
NOM_S = {"REB": "rebond sur ses zones dans le sens de l'avis", "CAS": "cassure de ses zones dans le sens de l'avis",
         "MAR": "au marché à 08h00, stop derrière le dernier creux / sommet 4 h"}
SEUILS = (55, 60, 65)
HORIZON_AVIS = 20                             # amendement du 18/10 15h35 : l'avis 5 j ne dépasse jamais 55 % sur 2022
VALIDITE_NS = 3 * JOUR_NS                     # un avis vaut jusqu'à l'avis suivant (vendredi -> lundi : 3 jours)
VARIANTES = [(s, k) for s in SCENARIOS for k in SEUILS]
MIN_TRADES = 100
RISQUES = (0.5, 1.0)


def vid(v) -> str:
    return f"{v[0]}-{v[1]}"


def _per_ns(per: str) -> tuple[int, int]:
    de, a = PERIODES[per]
    return pd.Timestamp(de).value, pd.Timestamp(a).value


def sens_avis(av: pd.DataFrame, dec_ns: np.ndarray, seuil: float) -> np.ndarray:
    """Sens de l'avis EN VIGUEUR à chaque instant (dernier avis publié, conviction >= seuil), 0 sinon."""
    inst = av["inst"].to_numpy(np.int64)
    dec_ns = np.asarray(dec_ns, np.int64)
    i = np.searchsorted(inst, dec_ns, side="right") - 1
    ii = np.clip(i, 0, None)
    ok = (i >= 0) & (dec_ns - inst[ii] < VALIDITE_NS)
    conv = av[f"conv{HORIZON_AVIS}"].to_numpy()[ii]
    p = av[f"p{HORIZON_AVIS}"].to_numpy()[ii]
    return np.where(ok & (conv >= seuil), np.where(p > 0.5, 1, -1), 0).astype(np.int8)


def geo_marche(x: dict, av: pd.DataFrame, gl: float) -> dict:
    """MAR : déclencheurs = les avis eux-mêmes (bougie fermée à 08h00)."""
    c, A, demi = (np.asarray(x[k], np.float64) for k in ("c", "A", "demi"))
    j = av["ligne"].to_numpy(np.int64)
    sens = np.where(av[f"p{HORIZON_AVIS}"].to_numpy() > 0.5, 1.0, -1.0)
    p, Aj = c[j], A[j]
    loin = np.where(sens > 0, av["creux_h4"].to_numpy(float), av["sommet_h4"].to_numpy(float))
    rd_z = sens * (p - (loin - sens * PM.MARGE_A * Aj))
    rd_z = np.where(np.isfinite(rd_z) & (rd_z > 0), rd_z, Aj)
    rd_min = (2.0 + gl) * demi[j] * p / PM.FRAIS_MAX_R
    rd = np.maximum(rd_z, rd_min)
    ok = np.isfinite(Aj) & (Aj > 0) & np.isfinite(rd) & (rd >= PM.RISQUE_MIN_A * Aj) & (rd <= PM.RISQUE_MAX_A * Aj)
    return {"j": j[ok], "sens": sens[ok], "stop": (p - sens * rd)[ok], "p": p[ok], "A": Aj[ok],
            "elargi": (rd > rd_z + 1e-12)[ok], "av_i": np.flatnonzero(ok)}


def trades_marche(nom: str, x: dict, av: pd.DataFrame, de_ns: int, a_ns: int, graine: int) -> dict:
    from collapsar.ecole.precision.univers import Univers
    from collapsar.regarder.pistes import logique_inversee as LI
    t15 = np.asarray(x["t15"], np.int64)
    debut = max(pd.Timestamp(int(t15[0])) + pd.Timedelta(days=45), pd.Timestamp(de_ns) - pd.Timedelta(days=5))
    if debut.value >= a_ns - 30 * JOUR_NS:
        return {}
    U = Univers([(nom, False)], debut, pd.Timestamp(a_ns) + pd.Timedelta(days=40), "cpu")
    ch = JT.chemin(U)
    gl = float(R().monde.frais_stop_glissement)
    m = np.searchsorted(t15, U.t_ns)
    assert np.array_equal(t15[np.clip(m, 0, len(t15) - 1)], U.t_ns), nom
    tv_l, tid_l, tv_s, tid_s = M.suiveur_lignes(x, PM.SUIVEUR, m - 1)
    ev = M.evenements_marche(x)
    geo = {}
    for fam in ("REB", "CAS"):
        g = PM.geometrie(x, ev, fam, gl)
        geo[fam] = {"j": ev["j"][g["idx"]].astype(np.int64), "sens": g["sens"], "stop": g["stop"], "p": g["p"],
                    "A": g["A"], "elargi": g["elargi"]}
    gm = geo_marche(x, av, gl)
    geo["MAR"] = gm
    rng = np.random.default_rng(graine)
    okf = np.zeros(U.T, bool)
    okf[:-2] = U.ouvert[1:-1, 0] & ~U.derniere[1:-1, 0]
    dec_u = U.t_ns + QUINZE_NS
    okf &= (dec_u >= de_ns) & (dec_u < a_ns) & (U.A[:, 0] > 0)
    lignes_f = np.flatnonzero(okf)
    out = {}
    jo = lambda tt, sg, st, ds, dr, sv, mm: M.jouer(*ch, tt.astype(np.int64), sg, st, ds, dr, sv, PM.HORIZON, gl,
                                                    tv_l, tid_l, tv_s, tid_s, mm)
    for v in VARIANTES:
        g = geo[v[0]]
        j = g["j"]
        dec = t15[j] + QUINZE_NS
        okp = (dec >= de_ns) & (dec < a_ns) & (t15[j] >= U.t_ns[0])
        if v[0] == "MAR":
            conv = av[f"conv{HORIZON_AVIS}"].to_numpy()[g["av_i"]]
            okp &= conv >= v[1]
        elif okp.any():
            sp = sens_avis(av, dec[okp], v[1])
            o2 = np.zeros(len(okp), bool)
            o2[np.flatnonzero(okp)] = (sp == g["sens"][okp]) & (sp != 0)
            okp = o2
        sel = np.flatnonzero(okp)
        if not len(sel):
            continue
        tU = np.searchsorted(U.t_ns, t15[j[sel]])
        ok_t = (tU < U.T) & (U.t_ns[np.clip(tU, 0, U.T - 1)] == t15[j[sel]])
        sel, tU = sel[ok_t], tU[ok_t]
        if not len(sel):
            continue
        sens, stop, p, Aj, el = g["sens"][sel], g["stop"][sel], g["p"][sel], g["A"][sel], g["elargi"][sel]
        n = len(sel)
        nan = np.full(n, np.nan)
        mg = PM.MARGE_A * Aj
        exe, ne, ns, rr, code, mfe = jo(tU, sens, stop, nan, np.zeros(n), np.ones(n, bool), mg)
        kg = LI.garder_un_a_la_fois(tU, exe, ns, code)
        tU, sens, stop, p, Aj, mg, el = tU[kg], sens[kg], stop[kg], p[kg], Aj[kg], mg[kg], el[kg]
        exe, ne, ns, rr, code, mfe = exe[kg], ne[kg], ns[kg], rr[kg], code[kg], mfe[kg]
        n = len(tU)
        nan = np.full(n, np.nan)
        rd = sens * (p - stop)
        tn = lambda k: np.where(k >= 0, U.t_ns[np.clip(k, 0, U.T - 1)], -1)
        z = {"dec_ns": U.t_ns[tU] + QUINZE_NS, "sens": sens.astype(np.int8), "risque_A": rd / Aj,
             "risque_pct": rd / p * 100, "elargi": el,
             "frais_R": (2.0 + gl) * U.demi[np.clip(tU + 1, 0, U.T - 1), 0] * p / rd,
             "exe": exe, "r": rr, "code": code, "ne_ns": tn(ne), "ns_ns": tn(ns), "mfe": mfe}
        if n:
            exe_j, ne_j, ns_j, rr_j, code_j, _ = jo(tU, -sens, 2 * p - stop, nan, np.zeros(n), np.ones(n, bool), mg)
            tf = rng.choice(lignes_f, n) if len(lignes_f) else tU
            pf, Af = U.c[tf, 0].astype(np.float64), U.A[tf, 0].astype(np.float64)
            rdf = rd / Aj * Af
            exe_f, _, ns_f, rr_f, code_f, _ = jo(tf, sens, pf - sens * rdf, nan, np.zeros(n), np.ones(n, bool),
                                                 PM.MARGE_A * Af)
            exe_c, _, ns_c, rr_c, code_c, _ = jo(tU, sens, stop, nan, np.full(n, 2.0), np.zeros(n, bool), mg)
            z.update({"exe_j": exe_j, "r_j": rr_j, "code_j": code_j, "ne_j_ns": tn(ne_j), "ns_j_ns": tn(ns_j),
                      "exe_f": exe_f, "r_f": rr_f, "code_f": code_f, "dec_f_ns": U.t_ns[tf] + QUINZE_NS,
                      "exe_c": exe_c, "r_c": rr_c, "code_c": code_c})
        out[vid(v)] = z
    del U, ch
    return out


def calculer(per: str, dire=print):
    from collapsar.ecole.precision import structure as S
    de_ns, a_ns = _per_ns(per)
    T = pd.read_pickle(AV.SORTIE / PANEL)
    if BRUT:                                     # pour information : l'avis AVANT calibration (appris <= 2021)
        T[f"p{HORIZON_AVIS}"], T[f"conv{HORIZON_AVIS}"] = T[f"praw{HORIZON_AVIS}"], T[f"convraw{HORIZON_AVIS}"]
    P = AV.panel()[["marche", "inst", "creux_h4", "sommet_h4"]]
    dos = SORTIE / per
    dos.mkdir(parents=True, exist_ok=True)
    acc = {vid(v): [] for v in VARIANTES}
    marches = list(D.univers())
    t0 = time.time()
    for im, nom in enumerate(marches):
        av = T[T["marche"] == nom].sort_values("inst").reset_index(drop=True)
        if not len(av):
            continue
        ex = P[P["marche"] == nom].sort_values("inst").reset_index(drop=True)
        av["creux_h4"], av["sommet_h4"] = ex["creux_h4"].to_numpy(), ex["sommet_h4"].to_numpy()
        av = av[av["age_j"] >= 130].reset_index(drop=True)
        x = S.lire(nom, False)
        tr = trades_marche(nom, x, av, de_ns, a_ns, 20261018 + im)
        for k, z in tr.items():
            z["marche"] = np.full(len(z["exe"]), im, np.int16)
            acc[k].append(z)
        dire(f"{per} {nom} : " + ", ".join(f"{k} {int(z['exe'].sum())}" for k, z in tr.items()) + f" ({time.time() - t0:.0f} s)")
    for k, mo in acc.items():
        if mo:
            np.savez(dos / f"{k}.npz", **{c: np.concatenate([m_[c] for m_ in mo]) for c in mo[0]})
    (dos / "marches.json").write_text(json.dumps(marches), encoding="utf-8")


def lire(per: str, k: str) -> dict | None:
    f = SORTIE / per / f"{k}.npz"
    if not f.exists():
        return None
    z = np.load(f)
    return {c: z[c] for c in z.files}


def mesurer_variante(z: dict, per: str) -> dict:
    de_ns, a_ns = _per_ns(per)
    mois = (a_ns - max(de_ns, int(z["dec_ns"].min()))) / MOIS_NS if len(z["dec_ns"]) else float("nan")
    res = {"variante": M.bloc(z, mois)}
    if "exe_j" in z and len(z["exe"]):
        res.update({"retourne": M.bloc(z, mois, "_j"), "fausses": M.bloc(z, mois, "_f"), "plafond2r": M.bloc(z, mois, "_c"),
                    "avance_jumeau": M.avance(z, "_j", True), "avance_fausses": M.avance(z, "_f", False),
                    "avance_plafond": M.avance(z, "_c", False)})
    noms = np.asarray(list(D.univers()))
    fam = np.asarray([AV.famille(n) for n in noms])[z["marche"]]
    res["familles"] = {f: M.bloc(z, mois, masque=(fam == f)) for f in AV.FAMILLES}
    return res


def compte(z: dict, risque: float, per: str, tirages: int = 200) -> dict:
    from collapsar.regarder.pistes import logique_inversee as LI
    de_ns, a_ns = _per_ns(per)
    if len(z["dec_ns"]):
        d0 = int(z["dec_ns"].min())
        de_ns = max(de_ns, d0 - d0 % JOUR_NS)
    ok = z["exe"] & (z["code"] != JT.FIN)
    reel = LI.compte(z["ne_ns"][ok], z["ns_ns"][ok], z["r"][ok], risque, de_ns, a_ns)
    rng = np.random.default_rng(20261018)
    okj = z["exe_j"] & (z["code_j"] != JT.FIN)
    gains = []
    for _ in range(tirages):
        pile = rng.random(len(ok)) < 0.5
        mr, mj = ok & pile, okj & ~pile
        c = LI.compte(np.r_[z["ne_ns"][mr], z["ne_j_ns"][mj]], np.r_[z["ns_ns"][mr], z["ns_j_ns"][mj]],
                      np.r_[z["r"][mr], z["r_j"][mj]], risque, de_ns, a_ns)
        gains.append(c["gain_mois_pct"])
    g = np.asarray(gains)
    return {"reel": reel, "jumeaux_gain_mois_moyen": float(g.mean()),
            "jumeaux_au_moins_aussi_bien_pct": float((g >= reel["gain_mois_pct"]).mean() * 100)}


BRUT = False
PANEL = "avis_panel.pkl"


def main():
    import sys
    import warnings
    global BRUT, SORTIE, SEUILS, VARIANTES, HORIZON_AVIS, PANEL
    warnings.filterwarnings("ignore", category=RuntimeWarning)
    if "--v2" in sys.argv:                       # essai 3 : avis par années glissantes, choix sur 2014-2022
        PANEL = "avis_panel_v2.pkl"
        HORIZON_AVIS = 5 if "--h5" in sys.argv else 20
        SORTIE = AV.SORTIE / f"execution_v2_{HORIZON_AVIS}j"
        PERIODES["reglage"] = ("2014-01-01", "2023-01-01")
    if "--brut" in sys.argv:
        BRUT, SORTIE, SEUILS = True, AV.SORTIE / "execution_brut", (52, 55, 60)
        HORIZON_AVIS = 5 if "--h5" in sys.argv else 20
        if "--h5" in sys.argv:
            SORTIE = AV.SORTIE / "execution_brut_5j"
        VARIANTES = [(s, k) for s in SCENARIOS for k in SEUILS]
    SORTIE.mkdir(parents=True, exist_ok=True)
    res = {"date": datetime.now().isoformat(timespec="seconds")}
    for per in PERIODES:
        calculer(per)
        res[per] = {}
        for v in VARIANTES:
            z = lire(per, vid(v))
            if z is not None and len(z["exe"]):
                res[per][vid(v)] = mesurer_variante(z, per)
    cand = {k: r["variante"] for k, r in res["reglage"].items() if r["variante"].get("n", 0) >= MIN_TRADES}
    choix = max(cand, key=lambda k: cand[k]["r"]) if cand else None
    res["choix"] = choix
    if choix:
        res["comptes"] = {per: {str(rk): compte(lire(per, choix), rk, per) for rk in RISQUES} for per in PERIODES
                          if lire(per, choix) is not None}
    (SORTIE / "resultats.json").write_text(json.dumps(res, indent=1, ensure_ascii=False, default=float), encoding="utf-8")
    print("choix sur 2022 :", choix)


if __name__ == "__main__":
    main()
