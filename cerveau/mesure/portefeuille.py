"""PORTEFEUILLE JOURNALIER sur plusieurs marchés (20/10/2026, compétition 2) : positions en montant ($) décidées à la
clôture de chaque jour (23:00 serveur = 16:00 New York), frais FTMO (demi-écart sur chaque changement, nuits de chaque
époque), règle FTMO « pas d'ouverture avant le week-end » (le vendredi : seulement réduire). Gains en $ sur 100 000 $,
non réinvestis. Plan : etudes/2026-10-20_competition2/PLAN_FIGE.md.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

from cerveau.perception.calendrier import prix_a_cloture
from core import donnees as D
from core.ftmo import frais as F
from core.ftmo.fiches import fiche
from core.ftmo.horloge import nuits_payees, regle_nuit
from core.ftmo.nuit import taux_nuit

CAPITAL = 100_000.0
H23 = pd.Timedelta(hours=23)


class Univers:
    def __init__(self, marches: list[str], fin: pd.Timestamp, debut: pd.Timestamp = pd.Timestamp("2010-01-01")):
        self.marches = list(marches)
        prix = {}
        for s in self.marches:
            b = D.charger(s, fin)
            b = b[b["time"] >= debut].reset_index(drop=True)
            jours = pd.DatetimeIndex(sorted(set(pd.DatetimeIndex(b["time"]).normalize())))
            jours = jours[jours.dayofweek < 5]
            prix[s] = pd.Series(prix_a_cloture(b, jours + H23), index=jours)
        self.P = pd.DataFrame(prix).sort_index()                          # clôtures (NaN = pas de prix ce jour)
        self.jours = self.P.index
        n, M = self.P.shape
        self.base_dollar = np.array([s.startswith("USD") and fiche(s).cotation != "USD" for s in self.marches])
        Pf = self.P.ffill(limit=3)
        p0, p1 = Pf.shift(1).to_numpy(), Pf.to_numpy()
        r = np.where(self.base_dollar[None, :], 1 - p0 / p1, p1 / p0 - 1)    # gain en $ par $ tenu (achat)
        self.r = pd.DataFrame(np.nan_to_num(r), index=self.jours, columns=self.marches)
        self.dispo = self.P.notna()
        t = (self.jours + H23)
        self.demi_frais = pd.DataFrame({s: np.asarray(F.frais(s, Pf[s].bfill().to_numpy()), float) / 2
                                        for s in self.marches}, index=self.jours)
        ach, ven, nuits = {}, {}, {}
        for s in self.marches:
            f = fiche(s)
            a, v = taux_nuit(f, t)
            ach[s], ven[s] = a, v
            regle = regle_nuit(f)
            nuits[s] = nuits_payees(t, {1: 2, 2: 4}[regle]) if regle else np.r_[0.0, np.ones(len(t) - 1)]
        self.achat = pd.DataFrame(ach, index=self.jours)
        self.vente = pd.DataFrame(ven, index=self.jours)
        self.nuits = pd.DataFrame(nuits, index=self.jours)
        lr = np.log(self.P.ffill(limit=3)).diff()
        if self.base_dollar.any():
            lr.loc[:, self.base_dollar] = -lr.loc[:, self.base_dollar]   # sens « devise contre dollar »
        self.lr = lr                                                       # rendement log, sens de l'achat en $
        self.vol = lr.rolling(60, min_periods=60).std()                   # connue à la clôture du jour
        self.vendredi = np.asarray(self.jours.dayofweek == 4)

    def montant_vol(self, cible_an: float = 0.10, diviseur: float = 1.0) -> pd.DataFrame:
        """Montant ($) qui vise `cible_an` de volatilité par an pour chaque marché (divisé par `diviseur`)."""
        lev = np.array([fiche(s).levier for s in self.marches])
        m = CAPITAL * cible_an / (self.vol * math.sqrt(252)) / diviseur
        return m.clip(upper=pd.Series(CAPITAL * lev, index=self.marches), axis=1)

    def simuler(self, cible: pd.DataFrame, facteur_frais: float = 1.0) -> dict:
        """`cible` [jours × marchés] : montant voulu ($, signé) à la clôture de chaque jour ; NaN = garder. Rend les
        gains journaliers par marché ($), les positions, les jours d'OUVERTURE (nouvelle position ou agrandissement)."""
        c = cible.reindex(index=self.jours, columns=self.marches).to_numpy(float)
        n, M = c.shape
        pos = np.zeros((n, M))
        actuel = np.zeros(M)
        ouvre = np.zeros(n, bool)
        dispo = self.dispo.to_numpy()
        for d in range(n):
            voulu = np.where(np.isnan(c[d]) | ~dispo[d], actuel, c[d])
            if self.vendredi[d]:                                       # avant le week-end : seulement réduire
                retourne = np.sign(voulu) * np.sign(actuel) < 0
                grandit = np.abs(voulu) > np.abs(actuel)
                voulu = np.where(retourne, 0.0, np.where(grandit, actuel, voulu))
            ouvre[d] = bool(np.any((np.abs(voulu) > np.abs(actuel) + 1e-9) | (np.sign(voulu) * np.sign(actuel) < 0)))
            pos[d] = voulu
            actuel = voulu
        prec = np.vstack([np.zeros((1, M)), pos[:-1]])
        r = self.r.to_numpy()
        df = self.demi_frais.to_numpy()
        taux = np.where(prec > 0, self.achat.to_numpy(), self.vente.to_numpy())
        gain = prec * r - facteur_frais * np.abs(pos - prec) * df - np.abs(prec) * taux / 360 * self.nuits.to_numpy()
        return {"gain": pd.DataFrame(gain, index=self.jours, columns=self.marches),
                "pos": pd.DataFrame(pos, index=self.jours, columns=self.marches),
                "ouvertures": self.jours[ouvre]}


def periode(s: pd.Series | pd.DataFrame, a, b):
    return s[(s.index >= pd.Timestamp(a)) & (s.index < pd.Timestamp(b))]


def mensuel(gain_jour: pd.Series) -> pd.Series:
    return gain_jour.groupby(gain_jour.index.to_period("M")).sum()


def avantage(a: pd.Series, b: pd.Series, risque_egal: bool = False) -> dict:
    """Avantage mensuel (% du compte) de a sur b ; incertitude par TRIMESTRES ramenée au mois."""
    a, b = a.align(b, join="outer", fill_value=0.0)
    if risque_egal and b.std(ddof=1) > 0:
        b = b * a.std(ddof=1) / b.std(ddof=1)
    d = (a - b) / CAPITAL * 100
    q = d.groupby(d.index.asfreq("Q")).sum()
    inc = float(q.std(ddof=1) / math.sqrt(len(q)) / 3) if len(q) > 1 else float("nan")
    return {"avantage_pct_mois": float(d.mean()), "incertitude": inc,
            "force": float(d.mean() / inc) if inc and inc > 0 else 0.0}


def resume(gain_jour: pd.Series, ouvertures: pd.DatetimeIndex, a, b, gain_jour_15: pd.Series | None = None) -> dict:
    g = periode(gain_jour, a, b)
    m = mensuel(g)
    cumul = g.cumsum().to_numpy()
    o = ouvertures[(ouvertures >= pd.Timestamp(a)) & (ouvertures < pd.Timestamp(b))]
    ecarts = np.diff(np.r_[pd.Timestamp(a).value, o.asi8, pd.Timestamp(b).value]) / 86_400e9 if len(o) else [np.inf]
    out = {"gain_pct_mois": float(m.mean() / CAPITAL * 100),
           "volatilite_an_pct": float(m.std(ddof=1) / CAPITAL * 100 * math.sqrt(12)),
           "pire_jour_pct": float(g.min() / CAPITAL * 100),
           "pire_baisse_pct": float(np.max(np.maximum.accumulate(np.r_[0, cumul])[1:] - cumul) / CAPITAL * 100),
           "jours_ouverture": int(len(o)), "plus_long_sans_ouvrir_jours": float(np.max(ecarts))}
    if gain_jour_15 is not None:
        out["gain_pct_mois_frais_x1_5"] = float(mensuel(periode(gain_jour_15, a, b)).mean() / CAPITAL * 100)
    return out
