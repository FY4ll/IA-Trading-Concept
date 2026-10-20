"""MESURE AVANT GREFFE des yeux de la foule sur l'arbre HYPERNOVA (17/10/2026). Règles écrites AVANT tout résultat.

Années : seulement l'apprentissage et la sélection de l'arbre (jusqu'au 31/12/2023) ; rien après 09/2025 n'est lu.
Marchés : les 19 cryptos de l'école (reglages.yaml), non retournées.
Foule : collapsar/ecole/precision/foule.py (sans futur ; « rang 90 j » des comptes acheteurs, -1 = jamais aussi peu
d'acheteurs depuis 90 jours, +1 = jamais autant). Extrême = rang <= -0,9 ou >= +0,9 (= centiles 5 / 95 de C1).

A. LES ZONES DU CHEF RÉAGISSENT-ELLES PLUS SOUVENT QUAND LA FOULE EST À UN EXTRÊME ?
- Zones = celles que voit l'arbre (structure.py : journalier, 4 h, 1 h, 30 min, 15 min), au 1er contact (bougie de
  15 min k qui entre dans la zone). La foule est lue à la clôture de k.
- Réaction (horizon 24 h = 96 bougies, à partir de la clôture de k) : une clôture à au moins d au-delà du bord proche
  (d = max(hauteur, 0,25 agitation), comme les yeux) AVANT toute clôture au-delà du bord lointain (zone cassée).
- Foule FAVORABLE : zone de demande touchée quand la foule est au plus bas d'acheteurs (rang <= -0,9), zone d'offre
  touchée quand elle est au plus haut (rang >= +0,9) ; DÉFAVORABLE : l'inverse ; NEUTRE : le reste.
- TÉMOIN : pour chaque contact réel, une FAUSSE zone de même forme et à la même distance du prix, à un instant tiré au
  hasard sur le même marché et la même période ; même calcul, foule lue à cet instant-là. Si la foule aide autant les
  fausses zones, l'effet vient de la foule (C1), pas des zones.
- Incertitude : écart type regroupé par jour (les cryptos bougent ensemble).

B. C1 « CONTRE LA FOULE » AVEC DES ENTRÉES PAR ORDRE LIMITE (frais FTMO réels du 16/10)
- Signal C1 (crypto_flux, inchangé) : à chaque fin d'heure UTC, comptes acheteurs >= centile 95 (90 j) -> vendre,
  <= centile 5 -> acheter ; tenue jusqu'à h + 24 h (sortie au marché) ; une position (ou un ordre) à la fois par marché.
- Liste fermée des entrées : M = au marché (référence C1) ; L½, L1, L2 = ordre limite posé à h à 0,5 / 1 / 2 agitations
  horaires (écart type des rendements horaires des 14 jours passés) plus favorable, valable 6 h, exécuté si une bougie de
  15 min comptant le TRAVERSE (plus bas < limite pour un achat), au prix limite (ou à l'ouverture si elle est déjà
  meilleure) ; non exécuté = pas de trade.
- Coûts FTMO (crypto_flux.frais, 16/10) : commission 0,0325 % par côté + écart x marge de prudence, la MÊME pour un
  ordre limite (chez FTMO l'ordre limite paie aussi la commission et l'écart) ; nuit 30 %/an par minuit serveur franchi.
- Taille : comme C1, exposition = min(1, 0,5 % / (agitation horaire x racine(24))).
- Juge : gain %/mois du compte (somme des trades, pleine taille comme la piste), baisse max, gain par trade, part
  exécutée, « force jour » contre le même ordre dans l'autre sens (jumeau), sur <= 2021 et 2022-2023.

Depuis Test_IA : venv_gpu\\Scripts\\python.exe -u -m collapsar.regarder.pistes.foule_hypernova
Rapport : collapsar/vie/hypernova/foule/mesure.md (+ mesure.json).
"""
from __future__ import annotations

import json
import math
import time

import numpy as np
import pandas as pd
from numba import njit

from collapsar.ecole.precision import foule as FO
from collapsar.ecole.precision import structure as S
from collapsar.ecole.precision.reglages import R, UNITES_15, VIE
from collapsar.regarder.pistes import crypto_flux as CF

SORTIE = VIE / "foule"
FIN = pd.Timestamp("2024-01-01")                 # jamais au-delà (apprentissage + sélection seulement)
PERIODES = {"jusqu'à 2021": (pd.Timestamp("2010-01-01"), pd.Timestamp("2022-01-01")),
            "2022-2023": (pd.Timestamp("2022-01-01"), FIN)}
EXTREME = 0.9
HORIZON = 96
QUINZE = pd.Timedelta(minutes=15)
LIMITES = {"M (au marché, C1)": None, "L½ (0,5 agit.)": 0.5, "L1 (1 agit.)": 1.0, "L2 (2 agit.)": 2.0}
VALIDITE_H = 6


# ============================================================================================== A. zones
@njit(cache=True)
def reactions(c, k, top, bot, side, d, H):
    """1 si réaction (clôture à d au-delà du bord proche avant toute clôture au-delà du bord lointain, sous H
    bougies), 0 sinon."""
    n = len(c)
    out = np.zeros(len(k), np.int8)
    for z in range(len(k)):
        fin = min(n, k[z] + H + 1)
        for j in range(k[z], fin):
            if side[z] > 0:
                if c[j] < bot[z]:
                    break
                if c[j] >= top[z] + d[z]:
                    out[z] = 1
                    break
            else:
                if c[j] > top[z]:
                    break
                if c[j] <= bot[z] - d[z]:
                    out[z] = 1
                    break
    return out


def groupe(rang: np.ndarray, side: np.ndarray, present: np.ndarray) -> np.ndarray:
    """1 favorable, -1 défavorable, 0 neutre, -9 foule inconnue."""
    fav = np.where(side > 0, rang <= -EXTREME, rang >= EXTREME)
    dfav = np.where(side > 0, rang >= EXTREME, rang <= -EXTREME)
    return np.where(~present, -9, np.where(fav, 1, np.where(dfav, -1, 0)))


def evenements_zones(sym: str, rng: np.random.Generator) -> pd.DataFrame:
    x = S.lire(sym, False)
    t15 = np.asarray(x["t15"])
    c = np.asarray(x["c"], np.float64)
    A = np.asarray(x["A"], np.float64)
    T = len(t15)
    dec = FO.serveur_vers_utc_ns(t15.astype("datetime64[ns]") + np.timedelta64(15, "m"))
    fo = FO.valeurs_a(sym, False, dec)
    rang = fo[:, FO.NOMS.index("rang_90j")]
    pres = fo[:, FO.NOMS.index("comptes_presents")] > 0
    jour = pd.DatetimeIndex(t15.astype("datetime64[ns]")).normalize().asi8
    t_fin = FIN.value
    ok_t = pres & np.isfinite(A) & (A > 0) & (t15 < t_fin) & (np.arange(T) < T - HORIZON - 1)
    candidats = np.flatnonzero(ok_t)
    parts = []
    if not len(candidats):
        return pd.DataFrame()
    for u in UNITES_15:
        z = x[u]
        tou = np.asarray(z["tou"], np.int64)
        top, bot = np.asarray(z["top"], np.float64), np.asarray(z["bot"], np.float64)
        side = np.asarray(z["side"], np.int64)
        m = tou < T
        k = np.clip(tou, 0, T - 1)
        m &= ok_t[k]
        k, top, bot, side = k[m], top[m], bot[m], side[m]
        if not len(k):
            continue
        d = np.maximum(top - bot, 0.25 * A[k])
        y = reactions(c, k, top, bot, side, d, HORIZON)
        # témoin : même forme, même distance au prix, instant tiré au hasard (même marché, mêmes années)
        k2 = rng.choice(candidats, len(k))
        dec_ = c[k2] - c[k]
        y2 = reactions(c, k2, top + dec_, bot + dec_, side, d, HORIZON)
        for vrai, kk, yy in ((True, k, y), (False, k2, y2)):
            parts.append(pd.DataFrame({"marche": sym, "unite": u, "vraie": vrai, "side": side, "y": yy,
                                       "groupe": groupe(rang[kk], side, pres[kk]), "jour": jour[kk],
                                       "t": t15[kk]}))
    return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()


def taux(df: pd.DataFrame) -> tuple[float, float, int]:
    """Taux de réaction et son écart type regroupé par jour."""
    n = len(df)
    if n < 30:
        return float("nan"), float("nan"), n
    p = df["y"].mean()
    g = df.groupby("jour")["y"].agg(["sum", "count"])
    se = math.sqrt(((g["sum"] - p * g["count"]) ** 2).sum()) / n
    return float(p), float(se), n


def bilan_zones(ev: pd.DataFrame) -> list[dict]:
    out = []
    unites = {"toutes": list(UNITES_15), "grandes (jour, 4 h)": ["D1", "H4"], "petites (1 h, 30 min, 15 min)": ["H1", "M30", "M15"]}
    for per, (de, a) in PERIODES.items():
        e = ev[(ev["t"] >= de.value) & (ev["t"] < a.value)]
        for nu, us in unites.items():
            eu = e[e["unite"].isin(us)]
            ligne = {"periode": per, "unites": nu}
            for vrai in (True, False):
                ee = eu[eu["vraie"] == vrai]
                r = {g: taux(ee[ee["groupe"] == g]) for g in (1, 0, -1)}
                cle = "zones" if vrai else "temoin"
                ligne[cle] = {"favorable": r[1], "neutre": r[0], "defavorable": r[-1]}
                if np.isfinite(r[1][0]) and np.isfinite(r[0][0]):
                    ligne[cle]["ecart_fav"] = (r[1][0] - r[0][0], math.hypot(r[1][1], r[0][1]))
                else:
                    ligne[cle]["ecart_fav"] = (float("nan"), float("nan"))
            out.append(ligne)
    return out


# ============================================================================================== B. C1 en limite
def spot15(sym: str) -> pd.DataFrame:
    """Bougies 15 min comptant (filtre commun de crypto_flux), index = fin de bougie UTC."""
    d = pd.read_csv(CF.SPOT / f"{sym}_M15.csv")
    d["time"] = pd.to_datetime(d["time"])
    d = d[d["time"] >= d["time"].iloc[0] + pd.Timedelta(days=7)].reset_index(drop=True)
    oc_min, oc_max = np.minimum(d["open"], d["close"]), np.maximum(d["open"], d["close"])
    fausse = (d["low"] < 0.5 * d["close"]) | (d["high"] > 2 * d["close"])
    d.loc[fausse, "low"], d.loc[fausse, "high"] = oc_min[fausse], oc_max[fausse]
    fin = CF.utc_depuis_serveur(d["time"]) + QUINZE
    d.index = fin
    d = d[~d.index.duplicated()]
    return d[d.index < FIN][["open", "high", "low", "close"]]


def trades_limite(sym: str) -> pd.DataFrame:
    F = CF.caracteristiques(sym)
    if F is None:
        return pd.DataFrame()
    F = F[F.index < FIN]
    sig = CF.signaux(F)["C1"]
    sp = spot15(sym)
    fins = sp.index.as_unit("ns").asi8
    lo, hi, op = sp["low"].to_numpy(), sp["high"].to_numpy(), sp["open"].to_numpy()
    px, ag = F["prix"].to_numpy(), F["agit_h"].to_numpy()
    idx = F.index
    hh = pd.DatetimeIndex(idx).as_unit("ns").asi8
    lignes = []
    for nom, k in LIMITES.items():
        libre = 0
        for i in np.flatnonzero(sig):
            if hh[i] < libre or i + 24 >= len(px):
                continue
            e0, x, a = px[i], px[i + 24], ag[i]
            if not (np.isfinite(e0) and np.isfinite(x) and np.isfinite(a) and a > 0):
                continue
            s = int(sig[i])
            expo = min(1.0, CF.RISQUE / (a * math.sqrt(24)))
            res = {}
            for sens in (s, -s):                                 # l'ordre voulu et son jumeau (même ordre, autre sens)
                if k is None:
                    res[sens] = (e0, hh[i])
                    continue
                L = e0 * (1 - sens * k * a)
                j0 = int(np.searchsorted(fins, hh[i], side="right"))
                j1 = int(np.searchsorted(fins, hh[i] + VALIDITE_H * 3600 * 10 ** 9, side="right"))
                rem = None
                for j in range(j0, j1):
                    if (sens > 0 and lo[j] < L) or (sens < 0 and hi[j] > L):
                        prix = min(op[j], L) if sens > 0 else max(op[j], L)
                        rem = (prix, fins[j] - 15 * 60 * 10 ** 9)
                        break
                res[sens] = rem
            def net(sens):
                if res[sens] is None:
                    return 0.0, 0, None
                pe, te = res[sens]
                if te >= hh[i + 24]:
                    return 0.0, 0, None
                nuits = (CF.serveur(pd.DatetimeIndex([hh[i + 24]])).normalize()
                         - CF.serveur(pd.DatetimeIndex([te])).normalize()).days[0]
                cout = CF.frais(sym) + nuits * CF.NUIT_AN / 360.0
                return expo * (sens * (x / pe - 1) - cout), int(nuits), sens * (x / pe - 1)
            R1, n1, brut = net(s)
            R2, _, _ = net(-s)
            execute = res[s] is not None and brut is not None
            lignes.append({"variante": nom, "marche": sym, "h": idx[i], "sens": s, "execute": execute, "R": R1,
                           "R_inverse": R2, "brut": brut if execute else np.nan, "nuits": n1, "expo": expo,
                           "jour_sortie": CF.serveur(pd.DatetimeIndex([hh[i + 24]])).normalize()[0]})
            # le marché redevient libre : à la sortie si exécuté, sinon à la fin de validité de l'ordre
            libre = hh[i + 24] if execute else hh[i] + VALIDITE_H * 3600 * 10 ** 9
    return pd.DataFrame(lignes)


def bilan_limite(t: pd.DataFrame) -> list[dict]:
    out = []
    for per, (de, a) in PERIODES.items():
        tp = t[(t["h"] >= de) & (t["h"] < a)]
        if not len(tp):
            continue
        jours = pd.date_range(tp["jour_sortie"].min(), tp["jour_sortie"].max())
        mois = len(jours) / 30.44
        for v in LIMITES:
            tv = tp[tp["variante"] == v]
            ex = tv[tv["execute"]]
            g = pd.Series(ex["R"].to_numpy(), index=pd.DatetimeIndex(ex["jour_sortie"])).groupby(level=0).sum() \
                .reindex(jours, fill_value=0.0)
            dj = pd.Series(((tv["R"] - tv["R_inverse"]) / 2).to_numpy(), index=pd.DatetimeIndex(tv["jour_sortie"])) \
                .groupby(level=0).sum().reindex(jours, fill_value=0.0)
            courbe = g.cumsum()
            out.append({"periode": per, "variante": v, "signaux": int(len(tv)), "trades": int(len(ex)),
                        "marches": int(ex["marche"].nunique()),
                        "executes_pct": float(100 * len(ex) / max(len(tv), 1)),
                        "brut_par_trade_pct": float(100 * ex["brut"].mean()) if len(ex) else float("nan"),
                        "net_par_trade_pct_expo": float(100 * (ex["R"] / ex["expo"]).mean()) if len(ex) else float("nan"),
                        "pct_mois": float(100 * g.sum() / mois), "baisse_max_pct": float(100 * (courbe - courbe.cummax()).min()),
                        "force_jour": float(dj.mean() / dj.std(ddof=1) * math.sqrt(len(dj))) if dj.std() > 0 else 0.0,
                        "nuits_moy": float(ex["nuits"].mean()) if len(ex) else float("nan")})
    return out


# ============================================================================================== rapport
def _f(x, nd=1, pct=True):
    return "—" if not np.isfinite(x) else (f"{100 * x:.{nd}f} %" if pct else f"{x:+.{nd}f}")


def ecrire(zones: list[dict], lim: list[dict], ev: pd.DataFrame, duree: float):
    L = ["# Yeux de la foule pour HYPERNOVA — mesure avant greffe (17/10/2026)", "",
         "Code : `collapsar/regarder/pistes/foule_hypernova.py` (règles écrites avant le calcul, en tête du fichier). "
         "Années d'apprentissage et de sélection SEULEMENT (jusqu'au 31/12/2023) ; 19 cryptos de l'école ; foule lue sans "
         "futur (`ecole/precision/foule.py`). Les comptes acheteurs n'existent que depuis 09/2020 pour le bitcoin et "
         "12/2021 pour les autres : avant 2022, la mesure ne porte que sur le bitcoin.", "",
         "## A. Les zones réagissent-elles plus souvent quand la foule est à un extrême ?", "",
         "Réaction = le prix repart d'au moins max(hauteur, 0,25 agitation) dans les 24 h, avant de casser la zone. "
         "Favorable = zone de demande touchée quand la foule n'a jamais eu aussi peu d'acheteurs depuis 90 jours "
         "(ou zone d'offre quand elle n'en a jamais eu autant). Témoin = fausse zone de même forme, à la même distance "
         "du prix, à un instant tiré au hasard. Entre parenthèses : incertitude (1 écart type, regroupé par jour).", "",
         "| Période | Zones | Réaction foule favorable | neutre | défavorable | Écart favorable - neutre | Témoin : favorable | neutre | écart |",
         "|---|---|---|---|---|---|---|---|---|"]
    for z in zones:
        a, b = z["zones"], z["temoin"]
        cel = lambda r: f"{_f(r[0])} ({100 * r[1]:.1f}, n={r[2]})" if np.isfinite(r[0]) else f"— (n={r[2]})"
        ec = lambda e: f"{100 * e[0]:+.1f} pts ± {100 * e[1]:.1f}" if np.isfinite(e[0]) else "—"
        L.append(f"| {z['periode']} | {z['unites']} | {cel(a['favorable'])} | {cel(a['neutre'])} | {cel(a['defavorable'])} "
                 f"| **{ec(a['ecart_fav'])}** | {cel(b['favorable'])} | {cel(b['neutre'])} | {ec(b['ecart_fav'])} |")
    L += ["", "## B. C1 « contre la foule » avec des entrées par ordre limite (frais FTMO du 16/10)", "",
          "Pleine taille de la piste (0,5 % d'agitation par trade, toutes les cryptos ensemble), sortie 24 h après le "
          "signal. Force jour = contre le même ordre posé dans l'autre sens (seuil de preuve 3).", "",
          "| Période | Entrée | Signaux | Trades (exécutés) | Gain brut / trade | Net / trade (frais + nuits) | %/mois | Baisse max | Force jour |",
          "|---|---|---|---|---|---|---|---|---|"]
    for x in lim:
        L.append(f"| {x['periode']} | {x['variante']} | {x['signaux']} | {x['trades']} ({x['executes_pct']:.0f} %) | "
                 f"{x['brut_par_trade_pct']:+.3f} % | {x['net_par_trade_pct_expo']:+.3f} % | **{x['pct_mois']:+.2f}** | "
                 f"{x['baisse_max_pct']:.1f} % | {x['force_jour']:+.1f} |")
    L += ["", f"Contacts de zones comptés : {int(ev['vraie'].sum())} (+ autant de fausses zones). Calcul : {duree:.0f} s.", ""]
    SORTIE.mkdir(parents=True, exist_ok=True)
    (SORTIE / "mesure_tableaux.md").write_text("\n".join(L), encoding="utf-8")
    (SORTIE / "mesure.json").write_text(json.dumps({"zones": zones, "limite": lim}, ensure_ascii=False, indent=1,
                                                   default=float), encoding="utf-8")
    print("\n".join(L), flush=True)


def main():
    t0 = time.time()
    rng = np.random.default_rng(20261017)
    ev, tl = [], []
    for sym in FO.cryptos():
        t1 = time.time()
        e = evenements_zones(sym, rng)
        ev.append(e)
        t = trades_limite(sym)
        tl.append(t)
        print(f"{sym} : {int(e['vraie'].sum()) if len(e) else 0} contacts de zones, "
              f"{int((t['variante'] == 'M (au marché, C1)').sum()) if len(t) else 0} signaux C1 ({time.time() - t1:.0f} s)",
              flush=True)
    ev = pd.concat([e for e in ev if len(e)], ignore_index=True)
    tl = pd.concat([t for t in tl if len(t)], ignore_index=True)
    SORTIE.mkdir(parents=True, exist_ok=True)
    tl.to_pickle(SORTIE / "trades_c1_limite.pkl")
    ecrire(bilan_zones(ev), bilan_limite(tl), ev, time.time() - t0)


if __name__ == "__main__":
    main()
