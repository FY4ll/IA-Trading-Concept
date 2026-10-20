"""Un COMPTE suivi heure par heure pour un système qui décide une fois par jour (20/10/2026) : taille selon la
volatilité, stop large, frais FTMO (écart + commission, nuits de chaque époque, nuit triple), gains en dollars non
réinvestis. Sert à la tendance de fond et à ses juges (même code, seul le sens change). Plan figé :
etudes/2026-10-20_couche1_tendance/PLAN_FIGE.md.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

from core import donnees as D
from core.ftmo import frais as F
from core.ftmo.fiches import fiche, taux_vers_dollar
from core.ftmo.horloge import nuits_payees, regle_nuit
from core.ftmo.nuit import taux_nuit

CAPITAL = 100_000.0
VOL_CIBLE = 0.10


def heures(b15: pd.DataFrame) -> dict:
    h1 = D.echelle(b15, "1 h")
    return {"t": pd.DatetimeIndex(pd.to_datetime(h1["debut"])).as_unit("ns"),
            **{k: np.asarray(h1[k], float) for k in ("open", "high", "low", "close")}}


TAILLES = ("fixe", "capital", "vol", "capital_vol")


def simuler(sym: str, h1: dict, jours: pd.DataFrame, sens: np.ndarray, stop_atr: float = 3.0,
            taille: str = "fixe", seuil: float = 0.10) -> dict:
    """`jours` : une ligne par clôture de jour (fin, close, vol_jour, atr) ; `sens` : le sens voulu à chaque clôture
    (+1, -1, 0). Rend la valeur du compte à chaque heure (clôture et pire moment) et les heures d'ouverture des trades.
    `taille` (20/10, section 8 de la mission) :
      fixe        = taille calculée à l'entrée sur 100 000 $, gardée jusqu'à la sortie (règle du test du 20/10) ;
      capital     = taille calculée à l'entrée sur la valeur ACTUELLE du compte, gardée jusqu'à la sortie ;
      vol         = taille recalculée chaque jour (volatilité du jour, 100 000 $), ajustée si l'écart dépasse `seuil` ;
      capital_vol = les deux : chaque jour, volatilité du jour × valeur actuelle du compte.
    Un ajustement paie l'écart sur la part achetée ou vendue ; le stop ne bouge pas."""
    if taille not in TAILLES:
        raise ValueError(taille)
    f = fiche(sym)
    t = pd.DatetimeIndex(h1["t"]).as_unit("ns")           # toujours en nanosecondes (pandas peut lire en µs)
    o, h, l, c = h1["open"], h1["high"], h1["low"], h1["close"]
    n = len(t)
    src, inv = taux_vers_dollar(f.cotation)
    if src is None:
        fx = np.ones(n)
    elif src == sym and inv:
        fx = 1.0 / c                                   # ex. dollar-yen : un yen vaut 1 / cours en dollars
    else:
        raise ValueError(f"conversion en dollars non prévue pour {sym}")
    regle = regle_nuit(f)
    nuits = nuits_payees(t, {1: 2, 2: 4}[regle]) if regle else np.r_[0.0, (np.diff(t.normalize().asi8) > 0).astype(float)]
    achat, vente = taux_nuit(f, t)
    demi_frais = np.asarray(F.frais(sym, c), float) / 2      # part du montant, par passage d'ordre
    # décisions -> bougie d'exécution (1re heure qui commence après la clôture du jour)
    kx = np.searchsorted(t.asi8, pd.DatetimeIndex(pd.to_datetime(jours["fin"])).as_unit("ns").asi8, side="left")
    dec_sens = np.full(n, -9, np.int64)
    dec_unites = np.zeros(n)
    dec_stop = np.zeros(n)
    prix_j = jours["close"].to_numpy(float)
    vol = jours["vol_jour"].to_numpy(float)
    atr = jours["atr"].to_numpy(float)
    fx_j = 1.0 / prix_j if (src == sym and inv) else np.ones(len(prix_j))
    for i in range(len(jours)):
        if kx[i] >= n:
            continue
        s = int(sens[i])
        if not (np.isfinite(vol[i]) and vol[i] > 0 and np.isfinite(atr[i])):
            s = 0
        montant = CAPITAL * VOL_CIBLE / (vol[i] * math.sqrt(252)) if s else 0.0
        montant = min(montant, CAPITAL * f.levier)
        dec_sens[kx[i]] = s
        dec_unites[kx[i]] = montant / (prix_j[i] * fx_j[i]) if s else 0.0
        dec_stop[kx[i]] = stop_atr * atr[i] if s else 0.0
    caisse = CAPITAL
    u = 0.0                                              # unités détenues (signées)
    entree = stop = 0.0
    eq_c, eq_p = np.empty(n), np.empty(n)
    ouvertures, en_pos, a_l_achat = [], 0, 0
    frais_total = nuits_total = volume_total = 0.0
    sur_capital = taille in ("capital", "capital_vol")
    for k in range(n):
        if k > 0 and u != 0 and nuits[k] > 0:
            taux = achat[k] if u > 0 else vente[k]
            cout_nuit = abs(u) * c[k - 1] * fx[k - 1] * taux / 360 * nuits[k]
            caisse -= cout_nuit
            nuits_total += cout_nuit
        if dec_sens[k] != -9:
            voulu = dec_sens[k]
            actuel = int(np.sign(u))
            valeur = caisse + (u * (o[k] - entree) * fx[k] if u != 0 else 0.0)
            facteur = max(valeur, 0.0) / CAPITAL if sur_capital else 1.0
            if voulu != actuel:
                if u != 0:                                # sortie à l'ouverture
                    f_ = abs(u) * o[k] * fx[k] * demi_frais[k]
                    caisse += u * (o[k] - entree) * fx[k] - f_
                    frais_total += f_
                    volume_total += abs(u) * o[k] * fx[k]
                    u = 0.0
                if voulu != 0:                            # entrée à l'ouverture
                    u = voulu * dec_unites[k] * facteur
                    entree = o[k]
                    stop = o[k] - voulu * dec_stop[k]
                    f_ = abs(u) * o[k] * fx[k] * demi_frais[k]
                    caisse -= f_
                    frais_total += f_
                    volume_total += abs(u) * o[k] * fx[k]
                    ouvertures.append(t[k])
            elif voulu != 0 and taille in ("vol", "capital_vol"):
                cible = voulu * dec_unites[k] * facteur   # même sens : ajustement à la volatilité du jour
                if abs(cible - u) > seuil * abs(u):
                    du = cible - u
                    if abs(cible) > abs(u):
                        entree = (u * entree + du * o[k]) / cible
                    else:
                        caisse += (u - cible) * (o[k] - entree) * fx[k]
                    f_ = abs(du) * o[k] * fx[k] * demi_frais[k]
                    caisse -= f_
                    frais_total += f_
                    volume_total += abs(du) * o[k] * fx[k]
                    u = cible
        pire = caisse + (u * ((l[k] if u > 0 else h[k]) - entree) * fx[k] if u != 0 else 0.0)
        if u != 0:
            touche = (u > 0 and l[k] <= stop) or (u < 0 and h[k] >= stop)
            if touche:
                px = min(o[k], stop) if u > 0 else max(o[k], stop)
                f_ = abs(u) * px * fx[k] * demi_frais[k]
                caisse += u * (px - entree) * fx[k] - f_
                frais_total += f_
                volume_total += abs(u) * px * fx[k]
                pire = min(pire, caisse)
                u = 0.0
        if u != 0:
            en_pos += 1
            a_l_achat += u > 0
        eq_c[k] = caisse + (u * (c[k] - entree) * fx[k] if u != 0 else 0.0)
        eq_p[k] = min(pire, eq_c[k])
    return {"t": t, "eq": eq_c, "pire": eq_p, "ouvertures": pd.DatetimeIndex(ouvertures),
            "en_position_pct": 100 * en_pos / n, "achat_pct": 100 * a_l_achat / max(en_pos, 1),
            "frais_total": frais_total, "nuits_total": nuits_total, "volume_total": volume_total}


def mesures_relatives(r: dict, debut, fin) -> dict:
    """Mêmes mesures que `mesures`, mais en % de la VALEUR du compte (comparables entre tailles fixes et tailles qui
    suivent le capital) : rendement mensuel composé, baisse depuis le plus haut, pire jour contre la clôture de la
    veille, challenge FTMO sur un compte neuf (seuils en % de la valeur au départ du challenge)."""
    t, eq, pire = _periode(r, debut, fin)
    k0 = np.searchsorted(r["t"].asi8, t.asi8[0]) - 1
    depart = r["eq"][k0] if k0 >= 0 else CAPITAL
    fin_mois = pd.Series(eq, index=t).resample("ME").last()
    g = (fin_mois / fin_mois.shift(1).fillna(depart) - 1) * 100
    sommet = np.maximum.accumulate(np.r_[depart, eq])[1:]
    baisse = float(np.max((sommet - pire) / sommet * 100))
    jour = t.normalize()
    df = pd.DataFrame({"eq": eq, "pire": pire}, index=t)
    par_jour = pd.DataFrame({"fin": df["eq"].groupby(jour).last(), "pire": df["pire"].groupby(jour).min()})
    veille = par_jour["fin"].shift(1).fillna(depart)
    perte_jour = (par_jour["pire"] - veille) / veille * 100
    ouv = r["ouvertures"][(r["ouvertures"] >= debut) & (r["ouvertures"] < fin)]
    ans = (t[-1] - t[0]).days / 365.25
    total = float(eq[-1] / depart - 1)
    return {"rendement_total_pct": 100 * total, "rendement_an_pct": 100 * ((1 + total) ** (1 / ans) - 1),
            "gain_pct_mois": float(g.mean()), "volatilite_an_pct": float(g.std(ddof=1) * math.sqrt(12)),
            "gain_sur_vol": float(g.mean() / g.std(ddof=1) * math.sqrt(12)) if g.std(ddof=1) > 0 else float("nan"),
            "pire_baisse_pct": baisse, "pire_jour_pct": float(perte_jour.min()),
            "jours_sous_5pct": int((perte_jour <= -5).sum()), "trades_an": float(len(ouv) / ans),
            "frais_pct_an": 100 * r["frais_total"] / CAPITAL / ans, "nuits_pct_an": 100 * r["nuits_total"] / CAPITAL / ans,
            "rotation_x_an": r["volume_total"] / CAPITAL / ans,
            "challenge": challenge(par_jour, ouv, debut, fin, relatif=True),
            "par_annee_pct": {str(a): round(float(v), 2) for a, v in
                              (pd.Series(eq, index=t).resample("YE").last().pct_change().fillna(
                                  pd.Series(eq, index=t).resample("YE").last().iloc[0] / depart - 1) * 100).items()}}


def _periode(r: dict, debut, fin):
    m = (r["t"] >= debut) & (r["t"] < fin)
    return r["t"][m], r["eq"][m], r["pire"][m]


def mensuel(r: dict, debut, fin) -> pd.Series:
    """Gain de chaque mois (en % de 100 000 $), du début à la fin de la période."""
    t, eq, _ = _periode(r, debut, fin)
    k0 = np.searchsorted(r["t"].asi8, t.asi8[0]) - 1
    depart = r["eq"][k0] if k0 >= 0 else CAPITAL
    fin_mois = pd.Series(eq, index=t).resample("ME").last()
    return fin_mois.diff().fillna(fin_mois.iloc[0] - depart) / CAPITAL * 100


def mesures(r: dict, debut, fin) -> dict:
    t, eq, pire = _periode(r, debut, fin)
    g = mensuel(r, debut, fin)
    sommet = np.maximum.accumulate(eq)
    baisse = float(np.max((sommet - pire) / CAPITAL * 100))
    jour = t.normalize()
    df = pd.DataFrame({"eq": eq, "pire": pire}, index=t)
    par_jour = pd.DataFrame({"fin": df["eq"].groupby(jour).last(), "pire": df["pire"].groupby(jour).min()})
    veille = par_jour["fin"].shift(1)
    veille.iloc[0] = eq[0]
    perte_jour = (par_jour["pire"] - veille) / CAPITAL * 100
    ouv = r["ouvertures"][(r["ouvertures"] >= debut) & (r["ouvertures"] < fin)]
    ans = (t[-1] - t[0]).days / 365.25
    return {"gain_pct_mois": float(g.mean()), "volatilite_an_pct": float(g.std(ddof=1) * math.sqrt(12)),
            "gain_sur_vol": float(g.mean() / g.std(ddof=1) * math.sqrt(12)) if g.std(ddof=1) > 0 else float("nan"),
            "pire_baisse_pct": baisse, "pire_jour_pct": float(perte_jour.min()),
            "jours_sous_5pct": int((perte_jour <= -5).sum()), "trades_an": float(len(ouv) / ans),
            "challenge": challenge(par_jour, ouv, debut, fin)}


def challenge(par_jour: pd.DataFrame, ouvertures: pd.DatetimeIndex, debut, fin, relatif: bool = False) -> dict:
    """Un challenge FTMO qui démarre au début de chaque mois : réussi à +10 % (clôture d'un jour) avant -10 % au total,
    une journée à -5 % (pire moment contre la clôture de la veille) ou 30 jours sans ouvrir de trade. `relatif` : les
    seuils sont des % de la valeur du compte au départ (pour une taille qui suit le capital), sinon de 100 000 $."""
    jours = pd.DatetimeIndex(par_jour.index).as_unit("ns")
    fins, pires = par_jour["fin"].to_numpy(), par_jour["pire"].to_numpy()
    jours_ouv = set(pd.DatetimeIndex(ouvertures).as_unit("ns").normalize())
    res = {"reussi": 0, "mur": 0, "inactivite": 0, "non_conclu": 0}
    departs = pd.date_range(pd.Timestamp(debut), pd.Timestamp(fin), freq="MS")
    for d in departs:
        k0 = int(np.searchsorted(jours.asi8, pd.Timestamp(d).as_unit("ns").value))
        if k0 >= len(jours) or k0 == 0:
            continue
        e0 = fins[k0 - 1]
        base = e0 if relatif else CAPITAL
        veille = e0
        dernier = jours[k0]                                  # ouvrir le compte = un 1er trade le jour du départ
        issue = "non_conclu"
        for k in range(k0, len(jours)):
            if jours[k] in jours_ouv:
                dernier = jours[k]
            if pires[k] - veille <= -0.05 * base or pires[k] <= e0 - 0.10 * base:
                issue = "mur"
                break
            if (jours[k] - dernier).days >= 30:
                issue = "inactivite"
                break
            if fins[k] >= e0 + 0.10 * base:
                issue = "reussi"
                break
            veille = fins[k]
        res[issue] += 1
    total = max(1, sum(res.values()))
    return {k: round(100 * v / total, 1) for k, v in res.items()} | {"departs": total}


def comparer(sys_m: pd.Series, juge_m: pd.Series, risque_egal: bool = False) -> dict:
    """Avantage mensuel du système sur un juge, incertitude par trimestres. `risque_egal` : le juge est d'abord ramené
    à la même volatilité mensuelle que le système."""
    a, b = sys_m.align(juge_m, join="inner")
    if risque_egal and b.std(ddof=1) > 0:
        b = b * a.std(ddof=1) / b.std(ddof=1)
    d = a - b
    q = d.groupby(d.index.to_period("Q")).sum()
    inc = float(q.std(ddof=1) / math.sqrt(len(q)) / 3) if len(q) > 1 else float("nan")
    av = float(d.mean())
    return {"avantage": av, "incertitude": inc, "bat": bool(inc > 0 and av > 2 * inc)}
