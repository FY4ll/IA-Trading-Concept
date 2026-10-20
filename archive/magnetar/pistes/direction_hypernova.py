"""DIRECTION + PRÉCISION (17/10/2026, chef de projet : « c'est pas la Terre que je demande, c'est des TRADES À 2R
POSITIFS »). La précision vient de ses zones (entrée sur zone, stop derrière une structure) ; la DIRECTION doit venir
des sources qui ont fait leurs preuves dans le projet (ecole/precision/direction.py) : tendance de fond 20 / 60 / 120
jours, cassure 24 h BTC/ETH (C2), « contre la foule » Binance (C1).

Mesure SANS IA sur les 6,4 M trades candidats déjà joués par l'école « juger un trade » (vie/hypernova/juge_trade/,
résultats frais FTMO, glissement du stop et nuits compris) :
1. JUMEAU de la piste du juge (« son 1 % meilleur sans la foule, joué jusqu'à sa destination : +0,16 R en 2023 et
   2024-2025, 100 % d'achats crypto ») : mêmes trades rejoués avec le sens tiré à pile ou face (géométrie retournée
   autour du prix : entrée, stop, destination) et « acheter n'importe quel candidat crypto le même jour ».
2. FILTRE DE DIRECTION : liste FIGÉE (`COMBINAISONS`, écrite dans `plan_fige.md` AVANT la mesure) ; pour chacune, les
   candidats d'accord avec la source, ceux de sens opposé (jumeau naturel) et les témoins sur fausses zones d'accord
   avec la même source (les zones ajoutent-elles quelque chose à une bonne direction ?).
Périodes : 2023 (sélection) et 01/2024 -> 09/2025 (contrôle). Rien après 09/2025.

Depuis Test_IA : venv_gpu\\Scripts\\python.exe -u -m collapsar.regarder.pistes.direction_hypernova plan|sources|jumeau|filtres|rapport|tout
"""
from __future__ import annotations

import argparse
import json
import math
import time
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

from collapsar.ecole.precision import direction as DI
from collapsar.ecole.precision.reglages import VIE

SORTIE = VIE / "direction"
JT_DOS = VIE / "juge_trade"
SEMAINE_NS = 7 * 86400 * 10 ** 9
JOUR_NS = 86400 * 10 ** 9
MOIS = {"selection_2023": 12.0, "controle_2024_25": 21.0}
NOM_P = {"selection_2023": "2023", "controle_2024_25": "2024-2025"}
BTC_ETH = ("BTCUSDT", "ETHUSDT")

# ---------------------------------------------------------------------------------------------- LISTE FIGÉE
# (nom, sources qui doivent toutes être d'accord avec le sens du trade, groupes de marchés jugés)
COMBINAISONS = [
    ("tendance 20 j", ("t20",), ("tous", "cryptos", "minute", "45 marchés")),
    ("tendance 60 j", ("t60",), ("tous", "cryptos", "minute", "45 marchés")),
    ("tendance 120 j", ("t120",), ("tous", "cryptos", "minute", "45 marchés")),
    ("tendance : les 3 d'accord", ("t20", "t60", "t120"), ("tous", "cryptos", "minute", "45 marchés")),
    ("cassure 24 h (C2) en cours", ("c2",), ("BTC/ETH",)),
    ("contre la foule (C1) en cours", ("c1",), ("cryptos",)),
    ("tendance 3 d'accord + C1", ("t20", "t60", "t120", "c1"), ("cryptos",)),
    ("tendance 3 d'accord + C2", ("t20", "t60", "t120", "c2"), ("BTC/ETH",)),
    ("C1 + C2", ("c1", "c2"), ("BTC/ETH",)),
]
FACONS = ("C", "A")                      # C = tout à 2R ; A = tout à sa destination
N_CASES = sum(len(g) for _, _, g in COMBINAISONS) * len(FACONS) + 1   # + le test du jumeau (étape 1)
SEUIL = max(3.0, math.sqrt(2 * math.log(N_CASES)))


def plan_texte() -> str:
    L = [f"# Plan FIGÉ avant toute mesure ({datetime.now():%d/%m/%Y %H:%M})", "",
         "Sources (ecole/precision/direction.py, sans futur) : t20 / t60 / t120 = signe de la tendance de fond sur 20 / 60 / "
         "120 jours de cotation (dernier jour terminé) ; c2 = cassure 24 h en cours (BTC, ETH) ; c1 = signal « contre la "
         "foule » en cours (cryptos).", "",
         "| n° | combinaison (toutes les sources d'accord avec le sens du trade) | groupes jugés |", "|---|---|---|"]
    for i, (nom, src, gr) in enumerate(COMBINAISONS, 1):
        L.append(f"| {i} | {nom} ({' + '.join(src)}) | {', '.join(gr)} |")
    L += ["", f"Façons de jouer : C (tout à 2R) et A (tout à sa destination). Cases jugées sur 2024-2025 : "
              f"{N_CASES - 1} + le test du jumeau = N = {N_CASES} ; seuil de preuve = max(3, racine(2 ln N)) = {SEUIL:.2f}.",
          "Pour chaque case : vrais candidats d'accord ; vrais candidats de sens OPPOSÉ (jumeau naturel) ; témoins sur "
          "fausses zones d'accord avec la même source. Force = R moyen / incertitude (grappes = SEMAINE, tous marchés "
          "ensemble, car les cryptos et la tendance bougent ensemble).",
          "Verdict : PROUVÉ si R moyen > 0 sur 2024-2025 avec force >= seuil (et > 0 sur 2023) ; PROMETTEUR (non prouvé) "
          "si > 0 sur 2023 ET 2024-2025 avec force > 2 sur 2024-2025."]
    return "\n".join(L) + "\n"


# ---------------------------------------------------------------------------------------------- données
class Cand:
    """Les candidats assemblés (sans X), plus la période, le groupe, le marché de chacun."""

    def __init__(self):
        from collapsar.ecole.precision import juge_trade as JT
        D_ = JT.Donnees()
        self.D = D_
        self.info = D_.info
        self.marches = list(D_.info["marches"])
        g = np.asarray(D_.info["groupes"])
        self.marche = np.asarray(D_.marche, np.int64)
        self.groupe = g[self.marche]
        self.btc_eth = np.isin(np.asarray(self.marches)[self.marche], BTC_ETH)
        self.periode = np.asarray(D_.periode)
        self.ns = np.asarray(D_.ns, np.int64)
        self.inst = np.asarray(D_.cand_inst, np.int64)
        self.sens = np.asarray(D_.sens, np.int8)
        self.temoin = np.asarray(D_.temoin, bool)
        self.exe = np.asarray(D_.exe, bool)
        self.hit2 = np.asarray(D_.hit2, bool)
        self.rC = np.asarray(D_.rC, np.float64)
        self.rA = np.asarray(D_.rA, np.float64)
        self.fin = np.asarray(D_.fin, bool)
        self.limite = np.asarray(D_.limite, bool)


def calculer_sources(c: Cand, dire=print) -> np.ndarray:
    """[instants, 5] : sens proposé par chaque source à chaque instant (cache sur le disque)."""
    f = SORTIE / "sources_instants.npy"
    if f.exists():
        return np.load(f)
    D_ = c.D
    ns = np.asarray(D_.inst_ns, np.int64)
    im = np.asarray(D_.inst_marche, np.int64)
    out = np.zeros((len(ns), len(DI.NOMS)), np.int8)
    t0 = time.time()
    for j, nom in enumerate(c.marches):
        k = np.flatnonzero(im == j)
        out[k] = DI.signes(nom, ns[k])
        dire(f"sources {nom} : {len(k)} instants, part non nulle "
             + " ".join(f"{n} {np.mean(out[k, i] != 0) * 100:.0f} %" for i, n in enumerate(DI.NOMS))
             + f" ({time.time() - t0:.0f} s)")
    SORTIE.mkdir(parents=True, exist_ok=True)
    np.save(f, out)
    return out


# ---------------------------------------------------------------------------------------------- mesure
def incertitude(x: np.ndarray, grappes: np.ndarray) -> float:
    n = len(x)
    if n < 2:
        return float("nan")
    r = x - x.mean()
    _, inv = np.unique(grappes, return_inverse=True)
    s = np.bincount(inv, weights=r)
    return float(np.sqrt((s ** 2).sum()) / n)


def bloc(c: Cand, m: np.ndarray, mois: float) -> dict:
    """Mesure d'un ensemble de candidats (masque) : exécutés seulement, frais compris."""
    ie = np.flatnonzero(m & c.exe)
    if len(ie) == 0:
        return {"n_exe": 0}
    rC, rA, h2 = c.rC[ie], c.rA[ie], c.hit2[ie]
    sem = c.ns[ie] // SEMAINE_NS
    W = rC[h2].mean() if h2.any() else 2.0
    L = -rC[~h2].mean() if (~h2).any() else 1.0
    iC, iA = incertitude(rC, sem), incertitude(rA, sem)
    jours = np.unique(c.marche[ie] * 100_000 + c.ns[ie] // JOUR_NS)
    return {"n_exe": int(len(ie)), "achats_pct": float((c.sens[ie] > 0).mean() * 100),
            "hit2_pct": float(h2.mean() * 100), "seuil_pct": float(L / (W + L) * 100),
            "rC": float(rC.mean()), "rC_inc": iC, "forceC": float(rC.mean() / iC) if iC > 0 else float("nan"),
            "rA": float(rA.mean()), "rA_inc": iA, "forceA": float(rA.mean() / iA) if iA > 0 else float("nan"),
            "trades_mois": float(len(ie) / mois), "jours_marches_mois": float(len(jours) / mois)}


def masque_groupe(c: Cand, gr: str) -> np.ndarray:
    if gr == "tous":
        return np.ones(len(c.sens), bool)
    if gr == "BTC/ETH":
        return c.btc_eth
    return c.groupe == gr


def filtres(c: Cand, src_inst: np.ndarray, dire=print) -> dict:
    """Étape 2 : chaque combinaison FIGÉE, sur 2023 et 2024-2025."""
    from collapsar.ecole.precision import juge_trade as JT
    S = src_inst[c.inst]                                         # [candidats, 5]
    col = {n: i for i, n in enumerate(DI.NOMS)}
    ok = ~c.fin
    res = {}
    for p in ("selection_2023", "controle_2024_25"):
        mp = ok & (c.periode == JT.CODE_P[p])
        rp = {}
        for gr in ("tous", "cryptos", "BTC/ETH", "minute", "45 marchés"):
            mg = mp & masque_groupe(c, gr)
            rp[f"base|{gr}"] = {"tous les candidats": bloc(c, mg & ~c.temoin, MOIS[p]),
                                "témoins, tous": bloc(c, mg & c.temoin, MOIS[p])}
        for nom, srcs, groupes in COMBINAISONS:
            acc = np.ones(len(c.sens), bool)
            con = np.ones(len(c.sens), bool)
            for s in srcs:
                v = S[:, col[s]]
                acc &= (v != 0) & (v == c.sens)
                con &= (v != 0) & (v == -c.sens)
            for gr in groupes:
                mg = mp & masque_groupe(c, gr)
                rp[f"{nom}|{gr}"] = {"d'accord": bloc(c, mg & acc & ~c.temoin, MOIS[p]),
                                      "sens opposé": bloc(c, mg & con & ~c.temoin, MOIS[p]),
                                      "témoins d'accord": bloc(c, mg & acc & c.temoin, MOIS[p])}
        res[p] = rp
        dire(f"filtres {NOM_P[p]} mesurés")
    return res


# ---------------------------------------------------------------------------------------------- étape 1 : le jumeau
def notes_sans_foule(c: Cand, dire=print) -> dict:
    """Score du juge sans la foule (R attendu « tout à 2R », recalibré) pour les vrais candidats de 2022, 2023, 2024-25."""
    import torch
    from collapsar.ecole.precision import juge_trade as JT
    f = SORTIE / "notes_sans_foule.npz"
    if f.exists():
        z = np.load(f)
        return {k: z[k] for k in z.files}
    torch.set_num_threads(4)
    net = JT.charger_juge(JT_DOS / "juge_sans_foule.pt")
    out = {}
    for p in ("reglage", "selection_2023", "controle_2024_25"):
        ii = np.flatnonzero(~c.fin & (c.periode == JT.CODE_P[p]) & ~c.temoin)
        t0 = time.time()
        z = JT.predire_brut(net, c.D, ii, True)
        av = JT.r_attendus(torch.as_tensor(z) * net.cal_a + net.cal_b)
        out[f"idx_{p}"] = ii
        out[f"note_{p}"] = av["rC"].numpy()
        dire(f"notes du juge sans la foule, {p} : {len(ii)} candidats ({time.time() - t0:.0f} s)")
    SORTIE.mkdir(parents=True, exist_ok=True)
    np.savez(f, **out)
    return out


def geometrie(c: Cand, idx: np.ndarray, p: np.ndarray, A: np.ndarray) -> dict:
    """Entrée, stop, destination d'un candidat reconstruits depuis sa description (float16) et le prix / l'agitation
    de l'instant."""
    from collapsar.ecole.precision import juge_trade as JT
    d = np.asarray(c.D.desc[idx], np.float64)
    k = {n: i for i, n in enumerate(JT.NOMS_DESC)}
    sig = c.sens[idx].astype(np.float64)
    lim = c.limite[idx]
    e = np.where(lim, p + sig * d[:, k["entree_dist_A"]] * A, p)
    rA_ = d[:, k["risque_A"]]
    rd = np.where(rA_ < 19.9, rA_, np.exp(d[:, k["log_risque_A"]])) * A
    stop = e - sig * rd
    dR, dA = d[:, k["dest_en_R"]], d[:, k["dest_dist_A"]]
    dest = np.where(np.abs(dR) < 19.9, e + sig * dR * rd, e + sig * dA * A)
    return {"sens": sig, "limite": lim, "P": e, "stop": stop, "dest": dest,
            "dest_r": np.asarray(c.D.dest_r[idx], np.float64), "validite": np.asarray(c.D.validite[idx], np.int64)}


def rejouer(c: Cand, idx: np.ndarray, dire=print) -> dict:
    """Rejoue chaque candidat de `idx` deux fois sur le vrai chemin du prix : sens d'origine (géométrie reconstruite,
    pour vérifier) et sens RETOURNÉ (entrée, stop, destination retournés autour du prix de l'instant)."""
    import torch
    from collapsar.ecole.precision import juge_trade as JT
    from collapsar.ecole.precision import structure as S
    from collapsar.ecole.precision.reglages import R
    from collapsar.ecole.precision.univers import Univers
    torch.set_num_threads(4)
    n = len(idx)
    out = {k: np.full(n, np.nan) for k in ("rA_o", "rC_o", "rA_m", "rC_m")}
    out.update({k: np.zeros(n, bool) for k in ("exe_o", "exe_m", "hit2_m")})
    # candidat global -> fichier du marché et rang local
    fichiers = sorted((JT_DOS / "exemples").glob("*.npz"))
    debut_c = np.zeros(len(fichiers) + 1, np.int64)
    for i, f in enumerate(fichiers):
        with np.load(f) as z:
            debut_c[i + 1] = debut_c[i] + len(z["cand_inst"])
    mk = c.marche[idx]
    t0 = time.time()
    for j in np.unique(mk):
        sel = np.flatnonzero(mk == j)
        nom = c.marches[j]
        f = fichiers[j]
        with np.load(f) as z:
            inst_t, cand_inst = z["inst_t"], z["cand_inst"]
            inst_ns = z["inst_ns"]
        loc = idx[sel] - debut_c[j]
        t = inst_t[cand_inst[loc]].astype(np.int64)
        x = S.lire(nom, False)
        debut = pd.Timestamp(int(np.asarray(x["t15"][0])))
        U = Univers([(nom, False)], debut + pd.Timedelta(days=45), R().periodes.fin_donnees, "cpu")
        assert np.array_equal(U.t_ns[t] + int(pd.Timedelta(minutes=15).value), inst_ns[cand_inst[loc]]), nom
        p, A = U.c[t, 0].astype(np.float64), U.A[t, 0].astype(np.float64)
        g = geometrie(c, idx[sel], p, A)
        ch = JT.chemin(U)
        cand = {"t": t, **g}
        r = JT.resultats(ch, cand)
        out["exe_o"][sel], out["rA_o"][sel], out["rC_o"][sel] = r["exe"], r["rA"], r["rC"]
        m = dict(cand)
        m["sens"] = -g["sens"]
        m["P"], m["stop"], m["dest"] = 2 * p - g["P"], 2 * p - g["stop"], 2 * p - g["dest"]
        r = JT.resultats(ch, m)
        out["exe_m"][sel], out["rA_m"][sel], out["rC_m"][sel], out["hit2_m"][sel] = r["exe"], r["rA"], r["rC"], r["hit2"]
        dire(f"jumeau {nom} : {len(sel)} trades rejoués ({time.time() - t0:.0f} s)")
        del U, ch
    return out


def jumeau(c: Cand, dire=print, tirages: int = 2000) -> dict:
    from collapsar.ecole.precision import juge_trade as JT
    notes = notes_sans_foule(c, dire)
    seuil = float(np.quantile(notes["note_reglage"], 0.99))
    res = {"seuil_note": seuil}
    rng = np.random.default_rng(20261017)
    S = None
    for p in ("selection_2023", "controle_2024_25"):
        ii = notes[f"idx_{p}"]
        top = ii[notes[f"note_{p}"] >= seuil]
        f = SORTIE / f"jumeau_{p}.npz"
        if f.exists():
            z = np.load(f)
            rj = {k: z[k] for k in z.files}
        else:
            rj = rejouer(c, top, dire)
            np.savez(f, **rj)
        exe, rA, rC = c.exe[top], c.rA[top], c.rC[top]
        sem = c.ns[top] // SEMAINE_NS
        # vérification de la reconstruction : le sens d'origine rejoué doit redonner les résultats enregistrés
        meme_exe = float((rj["exe_o"] == exe).mean() * 100)
        both = exe & rj["exe_o"]
        ecart = np.abs(rj["rA_o"][both] - rA[both])
        verif = {"meme_execution_pct": meme_exe, "rA_ecart_median": float(np.median(ecart)) if both.any() else None,
                 "rA_identique_pct": float((ecart < 0.02).mean() * 100) if both.any() else None,
                 "rA_rejoue_moyen": float(np.nanmean(rj["rA_o"][rj["exe_o"]]))}
        # par candidat (non exécuté = 0) : le juge contre son jumeau (sens à pile ou face)
        xo = np.where(exe, rA, 0.0)
        xm = np.where(rj["exe_m"], np.nan_to_num(rj["rA_m"]), 0.0)
        xoC = np.where(exe, rC, 0.0)
        xmC = np.where(rj["exe_m"], np.nan_to_num(rj["rC_m"]), 0.0)
        dA, dC = (xo - xm) / 2, (xoC - xmC) / 2
        # tirages du jumeau : moyenne par trade exécuté
        moy_j = []
        for _ in range(tirages):
            pile = rng.random(len(top)) < 0.5
            e_ = np.where(pile, exe, rj["exe_m"])
            r_ = np.where(pile, rA, rj["rA_m"])
            moy_j.append(np.nanmean(r_[e_]) if e_.any() else np.nan)
        moy_j = np.asarray(moy_j)
        juge_A = float(rA[exe].mean())
        # « acheter n'importe quel candidat crypto le même jour » (vrais candidats, achats, exécutés)
        mp = ~c.fin & (c.periode == JT.CODE_P[p]) & ~c.temoin & c.exe & (c.groupe == "cryptos") & (c.sens > 0)
        jour_p = c.ns[mp] // JOUR_NS
        uj, inv = np.unique(jour_p, return_inverse=True)
        moyA = np.bincount(inv, weights=c.rA[mp]) / np.bincount(inv)
        moyC = np.bincount(inv, weights=c.rC[mp]) / np.bincount(inv)
        te = top[exe]
        k = np.searchsorted(uj, c.ns[te] // JOUR_NS)
        trouve = (k < len(uj)) & (uj[np.clip(k, 0, len(uj) - 1)] == c.ns[te] // JOUR_NS)
        poolA = np.where(trouve, moyA[np.clip(k, 0, len(uj) - 1)], np.nan)
        poolC = np.where(trouve, moyC[np.clip(k, 0, len(uj) - 1)], np.nan)
        diffA = rA[exe] - poolA
        okd = np.isfinite(diffA)
        semE = c.ns[te] // SEMAINE_NS
        # même marché, même jour
        mk = c.marche[mp] * 100_000 + c.ns[mp] // JOUR_NS
        um, invm = np.unique(mk, return_inverse=True)
        moyAm = np.bincount(invm, weights=c.rA[mp]) / np.bincount(invm)
        km = c.marche[te] * 100_000 + c.ns[te] // JOUR_NS
        q = np.searchsorted(um, km)
        trm = (q < len(um)) & (um[np.clip(q, 0, len(um) - 1)] == km)
        poolAm = np.where(trm, moyAm[np.clip(q, 0, len(um) - 1)], np.nan)
        diffAm = rA[exe] - poolAm
        okm = np.isfinite(diffAm)
        res[p] = {
            "n_top": int(len(top)), "n_exe": int(exe.sum()), "achats_pct": float((c.sens[top][exe] > 0).mean() * 100),
            "cryptos_pct": float((c.groupe[top][exe] == "cryptos").mean() * 100),
            "verification": verif,
            "juge_rA": juge_A, "juge_rA_inc": incertitude(rA[exe], sem[exe]),
            "juge_rC": float(rC[exe].mean()), "juge_hit2_pct": float(c.hit2[top][exe].mean() * 100),
            "jumeau_retourne_rA": float(np.nanmean(rj["rA_m"][rj["exe_m"]])) if rj["exe_m"].any() else None,
            "jumeau_retourne_exe_pct": float(rj["exe_m"].mean() * 100),
            "jumeau_retourne_hit2_pct": float(rj["hit2_m"][rj["exe_m"]].mean() * 100) if rj["exe_m"].any() else None,
            "jumeau_pile_face_rA_moyen": float(np.nanmean(moy_j)), "jumeau_pile_face_rA_sd": float(np.nanstd(moy_j)),
            "part_tirages_au_moins_juge_pct": float((moy_j >= juge_A).mean() * 100),
            "avance_sur_jumeau_A_par_candidat": float(dA.mean()), "force_avance_A": float(dA.mean() / incertitude(dA, sem)),
            "avance_sur_jumeau_C_par_candidat": float(dC.mean()), "force_avance_C": float(dC.mean() / incertitude(dC, sem)),
            "achats_crypto_meme_jour_rA": float(np.nanmean(poolA)), "achats_crypto_meme_jour_rC": float(np.nanmean(poolC)),
            "avance_sur_achats_meme_jour": float(diffA[okd].mean()),
            "force_avance_achats_meme_jour": float(diffA[okd].mean() / incertitude(diffA[okd], semE[okd])),
            "achats_meme_marche_meme_jour_rA": float(np.nanmean(poolAm)),
            "avance_sur_achats_meme_marche_jour": float(diffAm[okm].mean()) if okm.any() else None,
            "force_avance_meme_marche_jour": float(diffAm[okm].mean() / incertitude(diffAm[okm], semE[okm])) if okm.sum() > 1 else None,
            "tous_achats_crypto_rA": float(c.rA[mp].mean()), "tous_achats_crypto_rC": float(c.rC[mp].mean()),
        }
        dire(f"jumeau {NOM_P[p]} : juge {juge_A:+.3f} R ; jumeau pile ou face {np.nanmean(moy_j):+.3f} ; achats crypto "
             f"même jour {np.nanmean(poolA):+.3f}")
    return res


# ---------------------------------------------------------------------------------------------- rapport
def _f(x, n=3, signe=True):
    if x is None or (isinstance(x, float) and not np.isfinite(x)):
        return "—"
    return f"{x:+.{n}f}" if signe else f"{x:.{n}f}"


def ligne(lib: str, b: dict) -> str:
    if not b or b.get("n_exe", 0) == 0:
        return f"| {lib} | 0 | — | — | — | — | — | — | — |"
    return (f"| {lib} | {b['n_exe']} | {b['achats_pct']:.0f} % | {b['hit2_pct']:.1f} % ({b['seuil_pct']:.1f} %) | "
            f"{_f(b['rC'])} ± {_f(b['rC_inc'], 3, False)} | {_f(b['forceC'], 1)} | {_f(b['rA'])} ± {_f(b['rA_inc'], 3, False)} | "
            f"{_f(b['forceA'], 1)} | {b['trades_mois']:.0f} / {b['jours_marches_mois']:.0f} |")


ENTETE = ("| qui | trades exécutés | achats | 2R avant stop (seuil) | R moyen « tout à 2R » | force | R moyen « jusqu'à sa "
          "destination » | force | trades / jours-marchés par mois |\n|---|---|---|---|---|---|---|---|---|")


def verdicts(fl: dict) -> list[dict]:
    out = []
    for nom, _, groupes in COMBINAISONS:
        for gr in groupes:
            for fa in FACONS:
                a23 = fl["selection_2023"][f"{nom}|{gr}"]["d'accord"]
                a24 = fl["controle_2024_25"][f"{nom}|{gr}"]["d'accord"]
                op24 = fl["controle_2024_25"][f"{nom}|{gr}"]["sens opposé"]
                tm24 = fl["controle_2024_25"][f"{nom}|{gr}"]["témoins d'accord"]
                r23, r24 = a23.get("r" + fa, np.nan), a24.get("r" + fa, np.nan)
                f24 = a24.get("force" + fa, np.nan)
                if r24 > 0 and f24 >= SEUIL and r23 > 0:
                    v = "PROUVÉ"
                elif r24 > 0 and r23 > 0 and f24 > 2:
                    v = "prometteur, non prouvé"
                elif r24 > 0 and r23 > 0:
                    v = "positif, trop faible"
                else:
                    v = "non"
                out.append({"combinaison": nom, "groupe": gr, "facon": fa, "r23": r23, "f23": a23.get("force" + fa, np.nan),
                            "r24": r24, "f24": f24, "op24": op24.get("r" + fa, np.nan), "tm24": tm24.get("r" + fa, np.nan),
                            "h24": a24.get("hit2_pct", np.nan), "s24": a24.get("seuil_pct", np.nan),
                            "tm24_mois": a24.get("trades_mois", 0.0), "verdict": v})
    return out


def ecrire_rapport(fl: dict | None, jm: dict | None, conclusion: str = ""):
    L = [f"# HYPERNOVA — DIRECTION + PRÉCISION : trades à 2R positifs ? (rapport du {datetime.now():%d/%m/%Y %H:%M})", ""]
    L.append("Mesure SANS IA sur les trades candidats de l'école « juger un trade » (6,4 M, posés sur ses zones, joués sur "
             "le vrai chemin du prix, frais FTMO, glissement du stop et nuits compris). Les sources de direction sont "
             "calculées sans futur (`ecole/precision/direction.py`, testé). 2023 = sélection ; 01/2024 -> 09/2025 = "
             "contrôle. Rien après 09/2025.")
    L.append("« Seuil » = % de trades à 2R qu'il faut pour ne pas perdre, frais compris. Force = R moyen / incertitude "
             "(grappes = semaines, tous marchés ensemble). Les trades / mois sont ceux de l'ÉCHANTILLON de candidats "
             "(instants tirés au hasard, 3 candidats par instant) : seule la colonne jours-marchés donne un ordre "
             "d'idée de la fréquence réelle.")
    L.append(f"Nombre de cases jugées N = {N_CASES} -> seuil de preuve max(3, racine(2 ln N)) = {SEUIL:.2f}.\n")
    if conclusion:
        L.append(conclusion.strip() + "\n")
    f_plan = SORTIE / "plan_fige.md"
    if f_plan.exists():
        L.append(f_plan.read_text(encoding="utf-8").replace("# Plan", "## Plan") + "")
    if jm:
        L.append("## Étape 1 — le jumeau de la piste du juge (1 % meilleur du juge SANS la foule)\n")
        L.append("| | 2023 | 2024-2025 |\n|---|---|---|")
        a, b = jm["selection_2023"], jm["controle_2024_25"]
        rows = [("trades exécutés (achats / cryptos)", lambda x: f"{x['n_exe']} ({x['achats_pct']:.0f} % / {x['cryptos_pct']:.0f} %)"),
                ("juge : R moyen jusqu'à sa destination", lambda x: f"{_f(x['juge_rA'])} ± {_f(x['juge_rA_inc'], 3, False)}"),
                ("juge : R moyen tout à 2R (2R atteint)", lambda x: f"{_f(x['juge_rC'])} ({x['juge_hit2_pct']:.0f} %)"),
                ("jumeau RETOURNÉ (même trade, sens contraire)", lambda x: f"{_f(x['jumeau_retourne_rA'])} (exécutés {x['jumeau_retourne_exe_pct']:.0f} %)"),
                ("jumeau pile ou face (2 000 tirages)", lambda x: f"{_f(x['jumeau_pile_face_rA_moyen'])} ± {_f(x['jumeau_pile_face_rA_sd'], 3, False)}"),
                ("tirages du jumeau qui font au moins aussi bien (trades supposés indépendants : trop flatteur)",lambda x: f"{x['part_tirages_au_moins_juge_pct']:.1f} %"),
                ("avance du juge sur son jumeau (force)", lambda x: f"{_f(x['avance_sur_jumeau_A_par_candidat'])} R ({_f(x['force_avance_A'], 1)})"),
                ("acheter n'importe quel candidat crypto le même jour", lambda x: f"{_f(x['achats_crypto_meme_jour_rA'])}"),
                ("avance du juge sur ces achats (force)", lambda x: f"{_f(x['avance_sur_achats_meme_jour'])} R ({_f(x['force_avance_achats_meme_jour'], 1)})"),
                ("acheter un candidat du même marché le même jour", lambda x: f"{_f(x['achats_meme_marche_meme_jour_rA'])}"),
                ("avance du juge sur ceux-là (force)", lambda x: f"{_f(x['avance_sur_achats_meme_marche_jour'])} R ({_f(x['force_avance_meme_marche_jour'], 1)})"),
                ("tous les achats crypto de la période (R destination / 2R)", lambda x: f"{_f(x['tous_achats_crypto_rA'])} / {_f(x['tous_achats_crypto_rC'])}"),
                ("vérification : même exécution / même R au rejeu", lambda x: f"{x['verification']['meme_execution_pct']:.1f} % / {_f(x['verification']['rA_identique_pct'], 1, False)} %")]
        for lib, fct in rows:
            L.append(f"| {lib} | {fct(a)} | {fct(b)} |")
        L.append("")
    if fl:
        L.append("## Étape 2 — verdict par case (liste figée)\n")
        L.append("| combinaison | groupe | façon | 2023 : R (force) | 2024-25 : R (force) | 2024-25 : 2R atteint (seuil) | "
                 "2024-25 sens opposé | 2024-25 témoins d'accord | verdict |\n|---|---|---|---|---|---|---|---|---|")
        for v in verdicts(fl):
            L.append(f"| {v['combinaison']} | {v['groupe']} | {'tout à 2R' if v['facon'] == 'C' else 'destination'} | "
                     f"{_f(v['r23'])} ({_f(v['f23'], 1)}) | {_f(v['r24'])} ({_f(v['f24'], 1)}) | "
                     f"{_f(v['h24'], 1, False)} % ({_f(v['s24'], 1, False)} %) | {_f(v['op24'])} | {_f(v['tm24'])} | {v['verdict']} |")
        L.append("")
        for p in ("selection_2023", "controle_2024_25"):
            L.append(f"## Détail {NOM_P[p]}\n")
            rp = fl[p]
            for gr in ("tous", "cryptos", "BTC/ETH", "minute", "45 marchés"):
                L.append(f"### {gr} — sans filtre\n")
                L.append(ENTETE)
                for lib, b in rp[f"base|{gr}"].items():
                    L.append(ligne(lib, b))
                L.append("")
            for nom, _, groupes in COMBINAISONS:
                for gr in groupes:
                    L.append(f"### {nom} — {gr}\n")
                    L.append(ENTETE)
                    for lib, b in rp[f"{nom}|{gr}"].items():
                        L.append(ligne(lib, b))
                    L.append("")
    SORTIE.mkdir(parents=True, exist_ok=True)
    (SORTIE / "rapport.md").write_text("\n".join(L), encoding="utf-8")


def dire_(t):
    print(f"[{datetime.now():%d/%m %H:%M:%S}] {t}", flush=True)


def _ecrire_json(f: Path, obj):
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(obj, ensure_ascii=False, indent=1, default=float), encoding="utf-8")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("quoi", choices=["plan", "sources", "jumeau", "filtres", "rapport", "tout"])
    a = ap.parse_args(argv)
    SORTIE.mkdir(parents=True, exist_ok=True)
    if a.quoi == "plan":
        f = SORTIE / "plan_fige.md"
        if f.exists():
            raise SystemExit(f"{f} existe déjà : le plan est figé")
        f.write_text(plan_texte(), encoding="utf-8")
        dire_(f"plan figé : {f}")
        return
    if not (SORTIE / "plan_fige.md").exists():
        raise SystemExit("figer d'abord le plan (commande plan)")
    c = Cand()
    if a.quoi in ("sources", "filtres", "tout"):
        src = calculer_sources(c, dire_)
    if a.quoi in ("jumeau", "tout"):
        _ecrire_json(SORTIE / "jumeau.json", jumeau(c, dire_))
    if a.quoi in ("filtres", "tout"):
        _ecrire_json(SORTIE / "filtres.json", filtres(c, src, dire_))
    if a.quoi in ("rapport", "tout", "filtres", "jumeau"):
        lire = lambda n: json.loads((SORTIE / n).read_text(encoding="utf-8")) if (SORTIE / n).exists() else None
        f_c = SORTIE / "conclusion.md"
        ecrire_rapport(lire("filtres.json"), lire("jumeau.json"), f_c.read_text(encoding="utf-8") if f_c.exists() else "")
        dire_("rapport écrit : " + str(SORTIE / "rapport.md"))


if __name__ == "__main__":
    main()
