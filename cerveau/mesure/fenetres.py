"""Mesure de FENÊTRES de position (entrée -> sortie à heure fixe) contre trois juges (20/10/2026) : hasard d'horaire
(mêmes fenêtres déplacées au hasard dans le même mois), pile ou face (espérance exacte), acheteur permanent à risque
égal. Taille selon la volatilité (connue la veille), frais FTMO (écart + commission, nuits de chaque époque, nuit
triple). Gains en $ sur un compte de 100 000 $, non réinvestis. Plan : etudes/2026-10-20_competition1/PLAN_FIGE.md.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

from core.ftmo import frais as F
from core.ftmo.fiches import fiche
from core.ftmo.horloge import nuits_payees, regle_nuit
from core.ftmo.nuit import taux_nuit

CAPITAL = 100_000.0
VOL_CIBLE = 0.10
FENETRE_VOL = 60


class Marche:
    """Les bougies de 15 min d'un marché (cotation en dollars) et tout ce qu'il faut pour chiffrer une fenêtre."""

    def __init__(self, sym: str, b15: pd.DataFrame):
        f = fiche(sym)
        # cotation en dollars (EURUSD, indices US, or) ou paire dont le dollar est la BASE (USDJPY : montant en dollars)
        self.base_dollar = f.cotation != "USD" and sym.startswith("USD")
        if f.cotation != "USD" and not self.base_dollar:
            raise ValueError(f"{sym} : cotation {f.cotation} (prévu : dollars)")
        self.sym, self.f = sym, f
        self.t = pd.DatetimeIndex(b15["time"]).as_unit("ns")
        self.o = b15["open"].to_numpy(float)
        self.c = b15["close"].to_numpy(float)
        self.n = len(self.t)
        regle = regle_nuit(f)
        self.jour_triple = {1: 2, 2: 4}.get(regle)            # nuit triple (lundi = 0) ; None = 1 par minuit
        nuits = nuits_payees(self.t, self.jour_triple) if regle else np.r_[0.0, (np.diff(self.t.normalize().asi8) > 0)]
        self.nuits_cumul = np.cumsum(nuits)
        self.achat, self.vente = taux_nuit(f, self.t)
        self.demi_frais = np.asarray(F.frais(sym, self.o), float) / 2
        # taille : volatilité des 60 derniers rendements journaliers, connue à la VEILLE
        jour = self.t.normalize()
        cl = pd.Series(self.c, index=self.t).groupby(jour).last()
        vol = np.log(cl).diff().rolling(FENETRE_VOL, min_periods=FENETRE_VOL).std().shift(1)
        montant = (CAPITAL * VOL_CIBLE / (vol * math.sqrt(252))).clip(upper=CAPITAL * f.levier)
        self.montant = montant.reindex(jour).to_numpy()          # $ engagés pour une entrée ce jour-là
        self.jours = cl.index
        self.clot_jour = cl.to_numpy()
        self.montant_jour = montant.to_numpy()
        # FTMO (pratiques interdites, vérifié le 20/10/2026, docs/FTMO_REGLES_VERIFIEES.md) : pas d'OUVERTURE dans les
        # 2 h avant une fermeture du marché de 2 h ou plus. Fermetures retenues : week-ends et jours fériés = trous de
        # 20 h ou plus dans nos données (les trous quotidiens de 6-12 h des indices Dukascopy ne sont PAS des
        # fermetures FTMO, où ils cotent ~23 h / 24).
        quinze = np.int64(15 * 60 * 10**9)
        ti = self.t.asi8
        trou = np.r_[ti[1:] - ti[:-1] - quinze, np.int64(0)]
        self.debuts_fermeture = ti[trou >= np.int64(20 * 3600 * 10**9)] + quinze
        self.ouverture_interdite = self.interdite(ti)

    DEUX_H = np.int64(2 * 3600 * 10**9)
    TRENTE_MIN = np.int64(30 * 60 * 10**9)
    QUINZE = np.int64(15 * 60 * 10**9)

    def interdite(self, instants_ns: np.ndarray) -> np.ndarray:
        f = self.debuts_fermeture
        k = np.searchsorted(f, instants_ns, side="left")
        ecart = np.where(k < len(f), f[np.minimum(k, max(len(f) - 1, 0))] - instants_ns, np.iinfo(np.int64).max) \
            if len(f) else np.full(len(instants_ns), np.iinfo(np.int64).max)
        return ecart <= self.DEUX_H

    def instants(self, quand) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Prix à des instants : ouverture de la bougie qui commence dans les 30 min ; sinon clôture de la bougie qui
        FINIT exactement à l'instant (ex. 23:00 = clôture de la bougie de 22:45). Rend (indice pour les nuits, prix,
        trouvé ?)."""
        x = pd.DatetimeIndex(quand).as_unit("ns").asi8
        ti = self.t.asi8
        k = np.searchsorted(ti, x, side="left")
        kc = np.minimum(k, self.n - 1)
        ouvre = (k < self.n) & (ti[kc] - x <= self.TRENTE_MIN)
        kp = np.maximum(k - 1, 0)
        finit = (k > 0) & (ti[kp] + self.QUINZE == x)
        prix = np.where(ouvre, self.o[kc], np.where(finit, self.c[kp], np.nan))
        return kc, prix, ouvre | finit

    def indices(self, quand) -> np.ndarray:
        return np.searchsorted(self.t.asi8, pd.DatetimeIndex(quand).as_unit("ns").asi8, side="left")

    def nuits_entre(self, te_ns: np.ndarray, ts_ns: np.ndarray) -> np.ndarray:
        """Nuits payées entre deux INSTANTS (minuits du serveur franchis ; nuit triple, samedi et dimanche à 0, comme
        core.ftmo.horloge.nuits_payees)."""
        de = (np.asarray(te_ns, np.int64) // 86_400_000_000_000)
        ds = (np.asarray(ts_ns, np.int64) // 86_400_000_000_000)
        if self.jour_triple is None:
            return (ds - de).astype(float)
        d0 = int(min(de.min(), ds.min())) if len(de) else 0
        k = np.arange(d0, int(max(de.max(), ds.max())) + 1 if len(de) else d0 + 1)
        semaine = (k + 3) % 7                                    # 01/01/1970 = jeudi (lundi = 0)
        poids = np.where(semaine == self.jour_triple, 3.0, np.where(semaine >= 5, 0.0, 1.0))
        cumul = np.r_[0.0, np.cumsum(poids)]
        return cumul[ds - d0] - cumul[de - d0]

    def pnl(self, ke: np.ndarray, ks: np.ndarray, sens: np.ndarray, facteur_frais: float = 1.0,
            pe: np.ndarray | None = None, ps: np.ndarray | None = None,
            te: np.ndarray | None = None, ts: np.ndarray | None = None) -> np.ndarray:
        """Gain en $ de chaque fenêtre (entrée en ke, sortie en ks : indices pour la taille et les frais ; prix pe / ps,
        par défaut l'ouverture de ces bougies ; instants te / ts (ns) pour les nuits, par défaut l'heure de ces
        bougies), frais compris."""
        m = self.montant[ke]
        pe = self.o[ke] if pe is None else pe
        ps = self.o[ks] if ps is None else ps
        te = self.t.asi8[ke] if te is None else te
        ts = self.t.asi8[ks] if ts is None else ts
        # m dollars de la base : gain en devise de cotation m × (ps - pe) / pe, converti au prix de sortie si la
        # cotation n'est pas le dollar (USDJPY : m × (1 - pe / ps))
        brut = sens * m * ((1 - pe / ps) if self.base_dollar else (ps / pe - 1))
        ecart = facteur_frais * m * (self.demi_frais[ke] + (ps / pe) * self.demi_frais[ks])
        nuits = self.nuits_entre(te, ts)
        taux = np.where(sens > 0, self.achat[ke], self.vente[ke])
        return brut - ecart - m * taux / 360 * nuits

    def fenetres(self, avis: pd.DataFrame, debut, fin):
        """Avis -> (ke, ks, sens, instant d'entrée, prix d'entrée, prix de sortie, instant de sortie) des fenêtres dans [debut, fin) :
        prix trouvés aux instants prévus (`instants`), taille connue, entrée permise par FTMO."""
        te = pd.DatetimeIndex(avis["temps"]).as_unit("ns")
        ts = pd.DatetimeIndex(avis["expire"]).as_unit("ns")
        ke, pe, ok_e = self.instants(te)
        ks, ps, ok_s = self.instants(ts)
        sens = avis["sens"].to_numpy(int)
        ok = ok_e & ok_s & (ke < ks) & (te >= pd.Timestamp(debut)) & (te < pd.Timestamp(fin))
        ok &= np.isfinite(self.montant[ke])
        ok &= ~self.interdite(te.asi8)                             # règle FTMO : pas d'ouverture avant une fermeture
        return ke[ok], ks[ok], sens[ok], te[ok], pe[ok], ps[ok], ts[ok]

    def hasard_horaire(self, ke, ks, sens, tirages: int = 200, graine: int = 0) -> np.ndarray:
        """[tirages, n] : chaque fenêtre (même durée en bougies, même sens) déplacée à un départ tiré au hasard parmi
        les bougies du même mois."""
        rng = np.random.default_rng(graine)
        duree = ks - ke
        mois = np.asarray(self.t.year * 12 + self.t.month)
        debut_mois = {}
        for m in np.unique(mois[ke]):
            idx = np.flatnonzero(mois == m)
            debut_mois[m] = (idx[0], idx[-1])
        out = np.empty((tirages, len(ke)))
        for i, (a, d) in enumerate(zip(ke, duree)):
            lo, hi = debut_mois[mois[a]]
            hi = min(hi, self.n - 1 - d)
            dep = rng.integers(lo, max(lo + 1, hi + 1), size=tirages)
            ok = np.isfinite(self.montant[dep]) & ~self.ouverture_interdite[dep]
            dep = np.where(ok, dep, a)
            out[:, i] = self.pnl(dep, dep + d, np.full(tirages, sens[i]))
        return out

    def acheteur_mensuel(self, debut, fin) -> pd.Series:
        """Gains mensuels ($) de l'acheteur permanent : taille selon la volatilité chaque jour, frais de nuit compris."""
        j = self.jours
        m = (j >= pd.Timestamp(debut)) & (j < pd.Timestamp(fin))
        cl = self.clot_jour
        r = np.r_[np.nan, cl[1:] / cl[:-1] - 1]
        mt = self.montant_jour
        kj = self.indices(j)
        kj = np.minimum(kj, self.n - 1)
        nuits = np.r_[0.0, np.diff(self.nuits_cumul[kj])]
        g = mt * r - mt * self.achat[kj] / 360 * nuits
        s = pd.Series(np.where(m, g, np.nan), index=j).dropna()
        return s.groupby(s.index.to_period("M")).sum()


def mensuel(gains: np.ndarray, heures: pd.DatetimeIndex) -> pd.Series:
    return pd.Series(gains, index=heures).groupby(heures.to_period("M")).sum()


def avantage(a: pd.Series, b: pd.Series, risque_egal: bool = False) -> dict:
    a, b = a.align(b, join="outer", fill_value=0.0)
    if risque_egal and b.std(ddof=1) > 0:
        b = b * a.std(ddof=1) / b.std(ddof=1)
    d = (a - b) / CAPITAL * 100                                         # en % du compte par mois
    inc = float(d.std(ddof=1) / math.sqrt(len(d))) if len(d) > 1 else float("nan")
    return {"avantage_pct_mois": float(d.mean()), "incertitude": inc,
            "force": float(d.mean() / inc) if inc and inc > 0 else 0.0}
