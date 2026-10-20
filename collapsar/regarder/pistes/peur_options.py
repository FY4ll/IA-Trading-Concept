"""PISTE « peur_options » : l'information des marchés d'options (CBOE) pour trader les indices américains chez FTMO
(US500 = USA500IDXUSD, US100 = USATECHIDXUSD, US30 = USA30IDXUSD) — 16/10/2026.

CAHIER DES CHARGES ÉCRIT AVANT TOUT RÉSULTAT (rien n'est choisi après coup ; tout est figé ici).

Données (data/cboe/, voir LISEZMOI.md) : historiques publics de la CBOE (cdn.cboe.com) : VIX, VIX9D, VIX3M, VIX6M, VVIX,
SKEW (valeur de clôture du jour). Ratios puts/calls (totalpc, equitypc, indexpc, spxpc, vixpc) : la CBOE ne publie en
fichier que jusqu'au 04/10/2019 -> impossible à vérifier sur 2020-2023 : EXCLUS de la liste (gardés pour mémoire).
Heure : le VIX de clôture est arrêté à 16h15 heure de New York (fin des options sur le S&P 500) ; on n'utilise une
valeur du jour d QU'À PARTIR de l'ouverture du marché au comptant du jour de Bourse suivant (9h30 New York = 16h30
serveur), soit plus de 17 h après. Jours de Bourse = calendrier NYSE (fériés recalculés ici) : la CBOE publie des
valeurs du VIX certains jours fériés (séance électronique, ex. 04/07/2023) -> ces lignes sont IGNORÉES.

Règles communes
- Décision sur les données connues à la clôture du jour de Bourse d (VIX et compagnie à 16h15 ; clôture au comptant
  de l'US500 à 16h00 = dernière bougie de 15 min avant 23h00 serveur). Exécution au jour de Bourse suivant D, au prix
  d'ouverture de la première bougie de 15 min à partir de 16h30 serveur (9h30 New York) de chaque indice.
- Les règles se calculent sur le VIX et sur l'US500 (le VIX est l'agitation implicite du S&P 500) ; la même position
  est prise sur les 3 indices (US30 seulement depuis 09/2013 ; avant, 2 indices).
- Taille : chaque indice reçoit (agitation visée / agitation réalisée 20 jours de l'indice, clôtures au comptant) /
  nombre d'indices disponibles ; somme plafonnée à 4 fois le compte. Pour les signaux « à événement », la taille est
  figée au début du trade ; la prime de peur (V6) est réajustée chaque jour. Deux niveaux d'agitation visée, publiés
  tous les deux, aucun choisi : 10 % et 20 % par an (agitation du compte quand il est en position pleine).
- Frais FIDÈLES FTMO : collapsar.mains.frais_ftmo.frais(sym, prix) (écart relevé, ramené au prix du jour, x MARGE_PRUDENCE (1,25 jusqu'au 16/10, 1 depuis l'audit) de
  glissement déjà compris ; pas de commission sur les indices) : moitié à chaque changement de taille (|Δ taille|).
  Nuits : collapsar.mains.nuit.taux_nuit (taux du dollar du mois précédent + 3,75 %/an) / 360 par minuit serveur
  franchi (vendredi -> lundi = 3 nuits) ; l'achat paie, la vente reçoit ou paie selon le taux.

LISTE FERMÉE DES VARIANTES (9) — position décidée à la clôture de d, tenue à partir de l'ouverture de D
  V1 courbe_inversee : VIX > VIX3M (courbe des échéances inversée = peur extrême) -> ACHAT, tenu tant que l'inversion
     dure (sortie à l'ouverture qui suit la première clôture VIX <= VIX3M). Sources : Simon & Campasano (2014, Journal
     of Derivatives, « The VIX futures basis ») ; Fassas & Hourvouliades (2019, JRFM, « VIX futures as a market timing
     indicator ») : la pente de la courbe prédit le S&P 500.
  V2 fin_inversion : première clôture VIX < VIX3M après au moins un jour d'inversion (« retour au calme ») -> ACHAT
     10 jours. Même source (usage courant chez les praticiens).
  V3 inversion_courte : VIX9D > VIX (peur des 9 prochains jours plus forte que celle du mois) -> ACHAT 5 jours (un
     nouveau signal pendant le trade le prolonge). Source : CBOE, note de présentation du VIX9D (2011).
  V4 vix_tendu (Connors & Alvarez 2009, « Short Term Trading Strategies That Work », chapitre « VIX Stretches »,
     réglages publiés pris tels quels) : US500 > sa moyenne 200 jours ET VIX >= 1,05 x sa moyenne 10 jours trois
     clôtures de suite -> ACHAT ; sortie quand l'US500 clôture au-dessus de sa moyenne 5 jours (au plus 10 jours).
  V5 vix_haut_indice_bas : VIX > 1,10 x sa moyenne 20 jours ET US500 sous sa clôture d'il y a 5 jours -> ACHAT 5 jours
     (idée « VIX au-dessus de sa moyenne + baisse de l'indice », Connors 2004 « How Markets Really Work »).
  V6 prime_de_peur : prime = VIX² - agitation réalisée² de l'US500 (21 jours, en %² par an) ; exposition ACHETEUSE =
     min(2, max(0, prime / médiane de la prime sur 252 jours)) / 2 (0 à 1), réajustée chaque jour. Sources :
     Bollerslev, Tauchen & Zhou (2009, RFS, « Expected stock returns and variance risk premia ») ; Bekaert & Hoerova
     (2014, J. Econometrics).
  V7 vix_haut_annee : VIX > son 90e centile des 252 derniers jours -> ACHAT 10 jours. Source : Whaley (2000, « The
     investor fear gauge ») ; Giot (2005, J. Portfolio Mgmt) : VIX très haut -> rendements futurs plus forts.
  V8 vvix_extreme : VVIX > son 90e centile des 252 derniers jours -> ACHAT 5 jours. Source : Park (2015, J. Futures
     Markets, « Volatility of volatility and tail risk premiums ») ; usage praticien (« pics de VVIX = creux »).
  V9 skew_extreme : SKEW > son 90e centile des 252 derniers jours -> VENTE 10 jours (CBOE : le SKEW mesure la peur
     d'un krach). Littérature contradictoire (Faff & Liu 2017) : testé tel qu'annoncé.

JUGE
- Périodes : CHOIX = depuis le début des données (US500/US100 09/2011, US30 09/2013) -> 2019-12-31 ; VÉRIFICATION =
  2020-01-01 -> 2023-12-31 ; CACHÉE = 2024-01-01 -> fin des données (10/2026), ouverte UNE fois pour la variante
  retenue (verrou collapsar/vie/pistes/peur_options/cachee.json ; s'il existe, ne jamais recalculer). Chaque phase est
  calculée sur des données COUPÉES à la fin de sa période (rien d'après n'est lu).
- Deux témoins : (a) JUMEAU = mêmes trades, même taille, sens tiré à pile ou face trade par trade (force = moyenne de
  (R - R_inverse)/2 / écart type x racine(n) = force du gain avant frais par trade) ; (b) ACHETER ET GARDER à la même
  exposition moyenne (la hausse générale) : force = t de (exposition du jour - exposition moyenne) x rendement unitaire
  du jour, sommé par blocs de 10 jours sans chevauchement. Un signal acheteur bat le jumeau rien qu'avec la hausse
  générale : c'est (b) qui dit s'il y a une information.
- Seuil de preuve : max(3, racine(2 ln 9)) = 3.
- Variante retenue (règle figée) : sur la période de CHOIX, parmi les variantes dont le gain après frais est > 0 (niveau
  10 %), la plus forte contre « acheter et garder » ; si aucune -> rien n'est retenu, la période cachée reste fermée.
- La période cachée n'est ouverte que si, en VÉRIFICATION, la retenue a un gain après frais > 0 ET une force contre
  « acheter et garder » > 0.
- Challenges FTMO simulés (2 étapes, +10 % puis +5 %, départ tous les 10 jours de Bourse, gains en part du capital de
  départ) : mort si dans la journée serveur le compte au plus mauvais prix des bougies (latent compris, frais payés)
  descend à -5 % du début du jour, ou à -10 % du départ ; étape réussie à la clôture d'un jour >= objectif avec au moins
  4 jours de trading (jour avec un ordre) ; « inactif » (règle FTMO) si 30 jours sans aucun ordre ; « inachevé » à la fin
  de la période (rien n'est lu après). Contre 20 jumeaux et contre « acheter et garder » à la même exposition.
- Brique peu liée : corrélation jour par jour du compte retenu avec le compte « cassure + zones » au niveau 9 %
  (collapsar/regarder/pistes/compte_combine.py, rejoué tel quel, sans modification), sur les jours communs.
- Contrôles anti-défaut : dates du VIX (grandes journées connues), lignes du VIX les jours fériés, heure de la bougie
  d'entrée, et la retenue rejouée avec un jour de retard (si l'avantage disparaît avec un jour de plus, suspect).

Depuis Test_IA : venv_gpu\\Scripts\\python.exe -u -m collapsar.regarder.pistes.peur_options choix|verif|cachee|lien
"""
from __future__ import annotations

import json
import math
import sys
from datetime import datetime

import numpy as np
import pandas as pd
from pandas.tseries.holiday import (AbstractHolidayCalendar, GoodFriday, Holiday, USLaborDay, USMartinLutherKingJr,
                                    USMemorialDay, USPresidentsDay, USThanksgivingDay, nearest_workday)

from collapsar.donnees import marches as dm
from collapsar.mains.fiches import fiche
from collapsar.mains.frais_ftmo import frais as frais_ftmo
from collapsar.mains.nuit import taux_nuit

VIE = dm.RACINE / "collapsar" / "vie" / "pistes" / "peur_options"
CACHE = VIE / "cache"
CBOE = dm.RACINE / "data" / "cboe"
INDICES = {"US500": "USA500IDXUSD", "US100": "USATECHIDXUSD", "US30": "USA30IDXUSD"}
PERIODES = {"choix": ("2011-01-01", "2020-01-01"), "verification": ("2020-01-01", "2024-01-01"),
            "cachee": ("2024-01-01", "2026-10-17")}
NIVEAUX = (0.10, 0.20)
CAP_EXPO = 4.0
JUMEAUX = 20
VARIANTES = ("V1_courbe_inversee", "V2_fin_inversion", "V3_inversion_courte", "V4_vix_tendu",
             "V5_vix_haut_indice_bas", "V6_prime_de_peur", "V7_vix_haut_annee", "V8_vvix_extreme",
             "V9_skew_extreme")
SEUIL = max(3.0, math.sqrt(2 * math.log(len(VARIANTES))))


def log(msg: str):
    print(msg, flush=True)
    VIE.mkdir(parents=True, exist_ok=True)
    with open(VIE / "journal.txt", "a", encoding="utf-8") as f:
        f.write(msg + "\n")


# ---------------------------------------------------------------- calendrier NYSE
class NYSE(AbstractHolidayCalendar):
    rules = [Holiday("NewYears", month=1, day=1, observance=nearest_workday), USMartinLutherKingJr, USPresidentsDay,
             GoodFriday, USMemorialDay,
             Holiday("Juneteenth", month=6, day=19, start_date="2022-01-01", observance=nearest_workday),
             Holiday("July4", month=7, day=4, observance=nearest_workday), USLaborDay, USThanksgivingDay,
             Holiday("Christmas", month=12, day=25, observance=nearest_workday)]


SPECIAUX = ["2012-10-29", "2012-10-30", "2018-12-05", "2025-01-09"]   # Sandy, obsèques Bush, obsèques Carter


def jours_nyse(debut="2005-01-01", fin="2026-12-31") -> pd.DatetimeIndex:
    f = NYSE().holidays(debut, fin)
    # nouvel an tombant un samedi : NYSE ne ferme pas le vendredi 31/12 précédent
    f = f[~((f.month == 12) & (f.day == 31))]
    j = pd.bdate_range(debut, fin)
    return j[~j.isin(f) & ~j.isin(pd.DatetimeIndex(SPECIAUX))]


# ---------------------------------------------------------------- données CBOE
def charger_cboe(fin: str) -> pd.DataFrame:
    cols = {}
    for n in ("VIX", "VIX9D", "VIX3M", "VIX6M", "VVIX", "SKEW"):
        d = pd.read_csv(CBOE / f"{n}_History.csv")
        d["DATE"] = pd.to_datetime(d["DATE"], format="%m/%d/%Y")
        col = "CLOSE" if "CLOSE" in d.columns else n
        s = d.set_index("DATE")[col].astype(float)
        cols[n.lower()] = s[s > 0]
    df = pd.DataFrame(cols)
    j = jours_nyse("2005-01-01", fin)
    j = j[j < pd.Timestamp(fin)]
    df = df[df.index < pd.Timestamp(fin)]
    return df.reindex(j).ffill(limit=3)


# ---------------------------------------------------------------- prix des indices (15 min, heure serveur = NY + 7 h)
def grille(fin: str) -> dict:
    CACHE.mkdir(parents=True, exist_ok=True)
    f = CACHE / "grille.npz"
    if not f.exists():
        dfs = {k: dm.charger(s, pd.Timestamp("2100-01-01")) for k, s in INDICES.items()}
        t = pd.DatetimeIndex(sorted(set().union(*[set(d["time"]) for d in dfs.values()])))
        out = {"t": t.values.astype("datetime64[ns]").astype(np.int64)}
        for k, d in dfs.items():
            d = d.drop_duplicates("time").set_index("time").reindex(t)
            for c in ("open", "high", "low", "close"):
                out[f"{k}_{c}"] = d[c].to_numpy(float)
        np.savez_compressed(f, **out)
        del dfs
    z = np.load(f)
    t = pd.DatetimeIndex(z["t"].astype("datetime64[ns]"))
    garde = t < pd.Timestamp(fin)
    g = {"t": t[garde]}
    for k in INDICES:
        for c in ("open", "high", "low", "close"):
            g[f"{k}_{c}"] = z[f"{k}_{c}"][garde]
    return g


def quotidien(g: dict, jours: pd.DatetimeIndex) -> dict:
    """Par indice et jour de Bourse : indice de la bougie d'entrée (première bougie réelle 16h30 <= h < 23h00 serveur),
    son prix d'ouverture, la clôture au comptant (dernière bougie réelle avant 23h00)."""
    t = g["t"]
    date = t.normalize()
    hm = t.hour * 60 + t.minute
    out = {}
    for k in INDICES:
        reel = np.isfinite(g[f"{k}_close"])
        seance = reel & (hm >= 16 * 60 + 30) & (hm < 23 * 60)
        idx = np.flatnonzero(seance)
        d = pd.DataFrame({"date": date[idx], "i": idx, "h": hm[idx]})
        prem = d.groupby("date").first()
        dern = d.groupby("date").last()
        q = pd.DataFrame(index=jours)
        q["i_entree"] = prem["i"].reindex(jours)
        q["h_entree"] = prem["h"].reindex(jours)
        q["ouv"] = g[f"{k}_open"][q["i_entree"].fillna(0).astype(int).to_numpy()]
        q.loc[q["i_entree"].isna(), "ouv"] = np.nan
        ic = dern["i"].reindex(jours)
        q["clo"] = np.where(ic.notna(), g[f"{k}_close"][ic.fillna(0).astype(int).to_numpy()], np.nan)
        q["h_clo"] = dern["h"].reindex(jours)
        out[k] = q
    return out


# ---------------------------------------------------------------- signaux (décidés à la clôture de d)
def _tenir(trig: np.ndarray, h: int) -> np.ndarray:
    """Un déclenchement au jour d -> position sur les h jours de décision d .. d+h-1 (prolongée par un nouveau)."""
    out = np.zeros(len(trig))
    reste = 0
    for i, x in enumerate(trig):
        if x:
            reste = h
        if reste > 0:
            out[i] = 1.0
            reste -= 1
    return out


def signaux(cb: pd.DataFrame, spx: pd.Series) -> dict[str, pd.Series]:
    """Exposition voulue décidée à la clôture de chaque jour de Bourse (index = jour de décision)."""
    vix, v3, v9, vv, sk = cb["vix"], cb["vix3m"], cb["vix9d"], cb["vvix"], cb["skew"]
    s = spx.ffill(limit=3)
    out = {}
    inv = (vix > v3)
    out["V1_courbe_inversee"] = inv.astype(float).where(v3.notna(), 0.0)
    fin_inv = (vix < v3) & inv.shift(1, fill_value=False)
    out["V2_fin_inversion"] = pd.Series(_tenir(fin_inv.to_numpy(), 10), index=cb.index)
    out["V3_inversion_courte"] = pd.Series(_tenir((v9 > vix).to_numpy(), 5), index=cb.index)
    # V4 Connors « VIX stretches »
    sma200, sma5 = s.rolling(200).mean(), s.rolling(5).mean()
    tendu = (vix >= 1.05 * vix.rolling(10).mean())
    entree = (s > sma200) & tendu & tendu.shift(1, fill_value=False) & tendu.shift(2, fill_value=False)
    e4 = np.zeros(len(cb))
    dedans, n = False, 0
    for i in range(len(cb)):
        if dedans:
            n += 1
            if s.iloc[i] > sma5.iloc[i] or n >= 10:
                dedans = False
                continue
            e4[i] = 1.0
        elif entree.iloc[i]:
            dedans, n = True, 0
            e4[i] = 1.0
    out["V4_vix_tendu"] = pd.Series(e4, index=cb.index)
    t5 = (vix > 1.10 * vix.rolling(20).mean()) & (s < s.shift(5))
    out["V5_vix_haut_indice_bas"] = pd.Series(_tenir(t5.to_numpy(), 5), index=cb.index)
    r = np.log(s).diff()
    rv2 = (r ** 2).rolling(21).mean() * 252 * 1e4
    prime = vix ** 2 - rv2
    med = prime.rolling(252, min_periods=200).median()
    e6 = (prime / med).clip(0, 2) / 2
    e6 = e6.where(med > 0, 0.0).fillna(0.0)
    out["V6_prime_de_peur"] = e6
    q7 = vix.rolling(252, min_periods=200).quantile(0.90)
    out["V7_vix_haut_annee"] = pd.Series(_tenir((vix > q7).to_numpy(), 10), index=cb.index)
    q8 = vv.rolling(252, min_periods=200).quantile(0.90)
    out["V8_vvix_extreme"] = pd.Series(_tenir((vv > q8).to_numpy(), 5), index=cb.index)
    q9 = sk.rolling(252, min_periods=200).quantile(0.90)
    out["V9_skew_extreme"] = -pd.Series(_tenir((sk > q9).to_numpy(), 10), index=cb.index)
    return {k: v.fillna(0.0) for k, v in out.items()}


# ---------------------------------------------------------------- le laboratoire
class Labo:
    def __init__(self, fin: str):
        self.fin = fin
        self.g = grille(fin)
        self.cb = charger_cboe(fin)
        self.jours = self.cb.index
        self.q = quotidien(self.g, self.jours)
        spx = self.q["US500"]["clo"]
        self.sig = signaux(self.cb, spx)
        # agitation réalisée 20 jours (clôtures au comptant) et poids unitaires par indice, connus à la clôture de d
        sig_ind = {}
        for k, q in self.q.items():
            r = np.log(q["clo"].ffill(limit=3)).diff()
            sig_ind[k] = r.rolling(20, min_periods=15).std() * math.sqrt(252)
        self.sigma = pd.DataFrame(sig_ind)
        n = self.sigma.notna().sum(axis=1).replace(0, np.nan)
        self.w1 = (1.0 / self.sigma).div(n, axis=0)           # poids pour une agitation visée de 1 (100 %/an)
        tot = self.w1.sum(axis=1)
        self.w1 = self.w1.mul(np.minimum(1.0, CAP_EXPO / 0.2 / tot.replace(0, np.nan)), axis=0).fillna(0.0)
        # rendement « unitaire » ouverture -> ouverture suivante (pour les forces), poids connus à la décision
        u = 0.0
        for k, q in self.q.items():
            ro = q["ouv"].shift(-1) / q["ouv"] - 1                # du jour d'exécution D au suivant
            u = u + self.w1[k].shift(1).fillna(0.0) * ro.fillna(0.0)
        self.u = u                                              # indexé par jour d'exécution D
        # données de nuit et de frais par indice
        t = self.g["t"]
        self.date_bar = t.normalize()
        self.nuits = {}
        for k, s in INDICES.items():
            a, v = taux_nuit(fiche(s), pd.DatetimeIndex(self.date_bar))
            self.nuits[k] = (np.asarray(a, float), np.asarray(v, float))

    # positions par jour d'exécution
    def expositions(self, nom: str, decal: int = 1) -> pd.Series:
        """Exposition (signe compris) tenue à partir de l'ouverture du jour D : décision de la veille (décal = 1)."""
        return self.sig[nom].shift(decal).fillna(0.0)

    @staticmethod
    def blocs(e: pd.Series, continu: bool) -> np.ndarray:
        """Numéro de trade par jour (−1 = hors position). Un trade = suite de jours de même signe non nul."""
        sgn = np.sign(e.to_numpy())
        nouveau = (sgn != 0) & (np.r_[0, sgn[:-1]] != sgn)
        b = np.cumsum(nouveau) - 1
        return np.where(sgn != 0, b, -1)

    def tailles(self, e: pd.Series, niveau: float, continu: bool) -> pd.DataFrame:
        """Taille par indice (part du compte, signe compris) par jour d'exécution."""
        w = self.w1.shift(1).fillna(0.0).reindex(e.index).fillna(0.0) * niveau   # poids connus à la décision (veille)
        if not continu:
            b = self.blocs(e, continu)
            wf = w.groupby(b).transform("first")             # taille figée au début du trade
            wf.loc[b < 0, :] = 0.0
            w = wf
        return w.mul(e, axis=0)

    def compte(self, tailles: pd.DataFrame, debut: str, fin: str) -> pd.DataFrame:
        """Compte bougie par bougie -> une ligne par jour serveur : gain, pire moment (latent), ordres, gain avant frais."""
        t = self.g["t"]
        nb = len(t)
        M = np.zeros(nb)
        A = np.zeros(nb)
        Mb = np.zeros(nb)
        ordres = np.zeros(nb, bool)
        for k, s in INDICES.items():
            q = self.q[k]
            ok = q["i_entree"].notna() & tailles.index.isin(q.index)
            jours_ok = q.index[ok]
            ib = q.loc[jours_ok, "i_entree"].astype(int).to_numpy()
            if len(ib) == 0:
                continue
            P = self.g[f"{k}_open"][ib]
            qs = tailles.reindex(jours_ok)[k].to_numpy()
            C = pd.Series(self.g[f"{k}_close"]).ffill().to_numpy()
            reel = np.isfinite(self.g[f"{k}_close"])
            L = np.where(reel, self.g[f"{k}_low"], C)
            H = np.where(reel, self.g[f"{k}_high"], C)
            seg = np.searchsorted(ib, np.arange(nb), side="right") - 1      # segment en cours à chaque bougie
            Pn = np.r_[P[1:], np.nan]
            R = qs * (Pn / P - 1)
            R[-1] = 0.0
            CR = np.r_[0.0, np.cumsum(R)[:-1]]                                # réalisé avant chaque segment
            dq = np.abs(np.diff(np.r_[0.0, qs]))
            F = dq * np.asarray(frais_ftmo(s, P), float) / 2
            CF = np.cumsum(F)
            ordres[ib[dq > 1e-12]] = True
            dedans = seg >= 0
            sg = np.where(dedans, seg, 0)
            qk = np.where(dedans, qs[sg], 0.0)
            Pk = P[sg]
            with np.errstate(invalid="ignore", divide="ignore"):
                lat = np.where(dedans, qk * (C / Pk - 1), 0.0)
                adv = np.where(dedans, qk * (np.where(qk > 0, L, H) / Pk - 1), 0.0)
            base = np.where(dedans, CR[sg], 0.0)
            fr = np.where(dedans, CF[sg], 0.0)
            # nuits : à la première bougie réelle de chaque jour serveur, position tenue à la bougie réelle précédente
            ir = np.flatnonzero(reel)
            dr = self.date_bar[ir]
            premiere = np.r_[False, dr[1:] != dr[:-1]]
            kk = ir[premiere]
            kprev = ir[np.flatnonzero(premiere) - 1]
            qprev = np.where(seg[kprev] >= 0, qs[np.maximum(seg[kprev], 0)], 0.0)
            ecart_j = (dr[premiere] - dr[np.flatnonzero(premiere) - 1]).days.to_numpy()
            a, v = self.nuits[k]
            taux = np.where(qprev > 0, a[kk], v[kk])
            N = np.zeros(nb)
            N[kk] = np.abs(qprev) * taux / 360 * ecart_j
            CN = np.cumsum(N)
            lat = np.nan_to_num(lat)
            adv = np.nan_to_num(adv)
            M += base + lat - fr - CN
            A += base + np.minimum(adv, lat) - fr - CN
            Mb += base + lat
        df = pd.DataFrame({"d": self.date_bar, "M": M, "A": A, "Mb": Mb, "o": ordres})
        df = df[(df["d"] >= pd.Timestamp(debut)) & (df["d"] < pd.Timestamp(fin))]
        jour = df.groupby("d").agg(fin=("M", "last"), bas=("A", "min"), finb=("Mb", "last"), ordres=("o", "any"))
        debut_j = jour["fin"].shift(1)
        debut_j.iloc[0] = df["M"].iloc[0] if len(df) else 0.0
        jour["gain"] = jour["fin"] - debut_j
        jour["pire"] = np.minimum(0.0, jour["bas"] - debut_j)
        db = jour["finb"].shift(1)
        db.iloc[0] = df["Mb"].iloc[0] if len(df) else 0.0
        jour["gain_brut"] = jour["finb"] - db
        return jour[["gain", "pire", "gain_brut", "ordres"]]


# ---------------------------------------------------------------- mesures
def force(x: np.ndarray) -> float:
    x = np.asarray(x, float)
    x = x[np.isfinite(x)]
    return float(x.mean() / x.std(ddof=1) * math.sqrt(len(x))) if len(x) > 5 and x.std() > 0 else float("nan")


def challenges(j: pd.DataFrame, pas: int = 10, inactivite: bool = True) -> dict:
    g, w, o = j["gain"].to_numpy(), j["pire"].to_numpy(), j["ordres"].to_numpy()
    if not inactivite:                       # information seulement : comme si un autre robot gardait le compte actif
        o = np.ones(len(g), bool)
    dates = j.index
    n = len(g)
    res = {"reussis": 0, "morts": 0, "inactifs": 0, "inacheves": 0, "jours": []}
    for d0 in range(0, n, pas):
        i, issue = d0, None
        for but in (0.10, 0.05):
            v, ntrad, dernier = 0.0, 0, dates[i] if i < n else None
            fini = False
            while i < n:
                if (dates[i] - dernier).days > 30 and not o[i]:
                    issue = "inactifs"
                    break
                if v + w[i] <= -0.10 or w[i] <= -0.05:
                    issue = "morts"
                    break
                v += g[i]
                if o[i]:
                    ntrad += 1
                    dernier = dates[i]
                i += 1
                if v >= but and ntrad >= 4:
                    fini = True
                    break
            if issue or not fini:
                break
        if issue:
            res[issue] += 1
        elif fini:
            res["reussis"] += 1
            res["jours"].append(i - d0)
        else:
            res["inacheves"] += 1
    tot = max(1, sum(res[k] for k in ("reussis", "morts", "inactifs", "inacheves")))
    return {"departs": tot, **{f"{k}_pct": 100 * res[k] / tot for k in ("reussis", "morts", "inactifs", "inacheves")},
            "jours_median": float(np.median(res["jours"])) if res["jours"] else None}


def bilan_periode(lab: Labo, nom: str, niveau: float, debut: str, fin: str, avec_challenges=True,
                  decal: int = 1) -> dict:
    continu = nom.startswith("V6")
    e = lab.expositions(nom, decal)
    e = e[e.index < pd.Timestamp(fin)]
    T = lab.tailles(e, niveau, continu)
    j = lab.compte(T, debut, fin)
    mois = len(j) / 21.0
    courbe = j["gain"].cumsum()
    baisse = float((courbe - courbe.cummax()).min())
    dans = (e.index >= pd.Timestamp(debut)) & (e.index < pd.Timestamp(fin))
    ep = e[dans]
    b = lab.blocs(e, continu)[dans]
    u = lab.u.reindex(ep.index).fillna(0.0)
    gu = ep * u
    # force contre le jumeau : gain avant frais par trade
    par_trade = pd.Series(gu.to_numpy()).groupby(b).sum()
    par_trade = par_trade[par_trade.index >= 0]
    # force contre acheter et garder à la même exposition (moyenne de |e|, signe +)
    ebar = float(np.abs(ep).mean())
    diff = (ep - ebar) * u
    blocs10 = diff.groupby(np.arange(len(diff)) // 10).sum()
    out = {"trades": int(len(par_trade)), "temps_en_position_pct": float((ep != 0).mean() * 100),
           "exposition_moyenne": ebar,
           "gain_pct_mois": float(j["gain"].sum() / mois * 100),
           "gain_avant_frais_pct_mois": float(j["gain_brut"].sum() / mois * 100),
           "baisse_max_pct": baisse * 100, "pire_jour_pct": float(j["pire"].min() * 100),
           "force_jumeau": force(par_trade.to_numpy()), "force_contre_garder": force(blocs10.to_numpy()),
           "gain_unitaire_par_jour_en_position_pct": float(gu[ep != 0].mean() * 100) if (ep != 0).any() else None}
    # acheter et garder à la même exposition : compte réel (frais + nuits)
    eg = pd.Series(np.where(e.index >= pd.Timestamp(debut), ebar, 0.0), index=e.index)
    jg = lab.compte(lab.tailles(eg, niveau, True), debut, fin)
    out["garder_meme_expo_gain_pct_mois"] = float(jg["gain"].sum() / mois * 100)
    if avec_challenges:
        out["challenges"] = challenges(j)
        out["info_challenges_sans_inactivite"] = challenges(j, inactivite=False)
        rng = np.random.default_rng(11)
        bt = lab.blocs(e, continu)
        jum, jum2 = [], []
        for _ in range(JUMEAUX):
            sgn = rng.choice([-1.0, 1.0], max(1, bt.max() + 1))
            sj = np.where(bt >= 0, sgn[np.maximum(bt, 0)], 1.0)     # même trade, même taille, sens à pile ou face
            jj = lab.compte(T.mul(sj, axis=0), debut, fin)
            jum.append(challenges(jj))
            jum2.append(challenges(jj, inactivite=False))
        cles = ("reussis_pct", "morts_pct", "inactifs_pct", "inacheves_pct")
        out["challenges_jumeaux"] = {k: float(np.mean([x[k] for x in jum])) for k in cles}
        out["info_challenges_jumeaux_sans_inactivite"] = {k: float(np.mean([x[k] for x in jum2])) for k in cles}
        out["challenges_garder"] = challenges(jg)
    return out, j


def ecrire(nom: str, obj):
    (VIE / nom).write_text(json.dumps(obj, ensure_ascii=False, indent=1, default=str), encoding="utf-8")


def resume(p: str, nom: str, niv: float, r: dict):
    c = r.get("challenges", {})
    cj = r.get("challenges_jumeaux", {})
    cg = r.get("challenges_garder", {})
    log(f"{p:12s} {nom:24s} {niv * 100:3.0f} % | tr {r['trades']:4d} | pos {r['temps_en_position_pct']:5.1f} % | "
        f"{r['gain_pct_mois']:+.3f} %/mois (avant frais {r['gain_avant_frais_pct_mois']:+.3f}, garder "
        f"{r['garder_meme_expo_gain_pct_mois']:+.3f}) | baisse {r['baisse_max_pct']:.1f} | pire j {r['pire_jour_pct']:.2f} | "
        f"F jum {r['force_jumeau']:+.2f} F garder {r['force_contre_garder']:+.2f}"
        + (f" | chall réussis/morts/inactifs {c.get('reussis_pct', 0):.0f}/{c.get('morts_pct', 0):.0f}/"
           f"{c.get('inactifs_pct', 0):.0f} (jum {cj.get('reussis_pct', 0):.0f}/{cj.get('morts_pct', 0):.0f}, garder "
           f"{cg.get('reussis_pct', 0):.0f}/{cg.get('morts_pct', 0):.0f}) | sans inactivité "
           f"{r['info_challenges_sans_inactivite']['reussis_pct']:.0f}/{r['info_challenges_sans_inactivite']['morts_pct']:.0f}"
           f" (jum {r['info_challenges_jumeaux_sans_inactivite']['reussis_pct']:.0f}/"
           f"{r['info_challenges_jumeaux_sans_inactivite']['morts_pct']:.0f})" if c else ""))


# ---------------------------------------------------------------- phases
def controles(lab: Labo) -> dict:
    v = pd.read_csv(CBOE / "VIX_History.csv")
    v["DATE"] = pd.to_datetime(v["DATE"], format="%m/%d/%Y")
    j = jours_nyse("2011-01-01", lab.fin)
    hors = v[(v["DATE"] >= "2011-01-01") & (v["DATE"] < lab.fin) & ~v["DATE"].isin(j)]
    manquants = j[(j >= "2011-01-01") & ~j.isin(v["DATE"]) & (j < pd.Timestamp(lab.fin))]
    gros = {d: float(v.loc[v["DATE"] == d, "CLOSE"].iloc[0]) for d in ("2015-08-24", "2018-02-05")
            if (v["DATE"] == d).any() and pd.Timestamp(d) < pd.Timestamp(lab.fin)}
    h = {k: q["h_entree"].dropna().value_counts(normalize=True).head(3).to_dict() for k, q in lab.q.items()}
    # la plus grosse baisse de l'US500 au comptant doit coïncider avec la plus grosse hausse du VIX (même date)
    spx = lab.q["US500"]["clo"]
    rs = np.log(spx).diff()
    rv = np.log(lab.cb["vix"]).diff()
    top = rs.nsmallest(5).index
    acc = float(np.mean([rv.loc[d] > 0.10 for d in top]))
    return {"vix_lignes_hors_jours_de_bourse": [str(d.date()) for d in hors["DATE"]],
            "jours_de_bourse_sans_vix": [str(d.date()) for d in manquants],
            "vix_grandes_journees": gros, "heure_bougie_entree_minutes": h,
            "5_pires_jours_us500_vix_+10pct_meme_jour": acc,
            "5_pires_jours_us500": [str(d.date()) for d in top]}


def phase_choix():
    fin = PERIODES["choix"][1]
    lab = Labo(fin)
    ctrl = controles(lab)
    log(f"contrôles : {json.dumps(ctrl, ensure_ascii=False)[:1500]}")
    res = {"quand": datetime.now().isoformat(timespec="seconds"), "controles": ctrl, "variantes": {}}
    debut = PERIODES["choix"][0]
    for nom in VARIANTES:
        res["variantes"][nom] = {}
        for niv in NIVEAUX:
            r, _ = bilan_periode(lab, nom, niv, debut, fin)
            res["variantes"][nom][f"{niv * 100:.0f} %"] = r
            resume("choix", nom, niv, r)
        ecrire("choix.json", res)
    # règle figée
    cand = [(res["variantes"][n]["10 %"]["force_contre_garder"], n) for n in VARIANTES
            if res["variantes"][n]["10 %"]["gain_pct_mois"] > 0 and
            np.isfinite(res["variantes"][n]["10 %"]["force_contre_garder"])]
    retenue = max(cand)[1] if cand else None
    res["retenue"] = retenue
    log(f"RETENUE (règle figée) : {retenue}")
    if retenue:
        r1, _ = bilan_periode(lab, retenue, 0.10, debut, fin, avec_challenges=False, decal=2)
        res["controle_un_jour_de_retard"] = r1
        resume("choix+1j", retenue, 0.10, r1)
    ecrire("choix.json", res)


def phase_verif():
    choix = json.loads((VIE / "choix.json").read_text(encoding="utf-8"))
    debut, fin = PERIODES["verification"]
    lab = Labo(fin)
    res = {"quand": datetime.now().isoformat(timespec="seconds"), "retenue": choix["retenue"], "variantes": {}}
    ordre = [choix["retenue"]] + [n for n in VARIANTES if n != choix["retenue"]] if choix["retenue"] else VARIANTES
    for nom in ordre:
        res["variantes"][nom] = {}
        for niv in NIVEAUX:
            r, _ = bilan_periode(lab, nom, niv, debut, fin)
            res["variantes"][nom][f"{niv * 100:.0f} %"] = r
            resume("verif", nom, niv, r)
        ecrire("verification.json", res)
    ret = choix["retenue"]
    if ret:
        r = res["variantes"][ret]["10 %"]
        res["ouvrir_cachee"] = bool(r["gain_pct_mois"] > 0 and r["force_contre_garder"] > 0)
        log(f"vérification de la retenue {ret} : gain {r['gain_pct_mois']:+.3f} %/mois, force contre garder "
            f"{r['force_contre_garder']:+.2f} -> ouvrir la période cachée : {res['ouvrir_cachee']}")
    ecrire("verification.json", res)


def phase_cachee():
    verrou = VIE / "cachee.json"
    if verrou.exists():
        log("période cachée DÉJÀ ouverte : verrou présent, rien n'est recalculé")
        return
    v = json.loads((VIE / "verification.json").read_text(encoding="utf-8"))
    if not v.get("ouvrir_cachee"):
        log("vérification non concluante : la période cachée reste fermée")
        return
    ret = v["retenue"]
    debut, fin = PERIODES["cachee"]
    verrou.write_text(json.dumps({"ouverte": datetime.now().isoformat(timespec="seconds"), "variante": ret,
                                  "etat": "en cours"}, ensure_ascii=False), encoding="utf-8")
    lab = Labo(fin)
    res = {"ouverte": datetime.now().isoformat(timespec="seconds"), "variante": ret, "niveaux": {}}
    for niv in NIVEAUX:
        r, _ = bilan_periode(lab, ret, niv, debut, fin)
        res["niveaux"][f"{niv * 100:.0f} %"] = r
        resume("CACHEE", ret, niv, r)
    verrou.write_text(json.dumps(res, ensure_ascii=False, indent=1, default=str), encoding="utf-8")


def phase_lien():
    """Corrélation jour par jour avec le compte cassure + zones (niveau 9 %), sur les jours communs déjà autorisés."""
    from collapsar.regarder.pistes import compte_combine as CC
    v = json.loads((VIE / "verification.json").read_text(encoding="utf-8"))
    ret = v["retenue"]
    fin = PERIODES["cachee"][1] if (VIE / "cachee.json").exists() else PERIODES["verification"][1]
    lab = Labo(fin)
    e = lab.expositions(ret)
    j = lab.compte(lab.tailles(e, 0.10, ret.startswith("V6")), "2017-08-01", fin)
    # compte combiné niveau 9 % rejoué (même calcul que compte_combine.main, sans rien écrire dans son dossier)
    cc = json.loads((CC.VIE / "resultats.json").read_text(encoding="utf-8"))
    ag = {k: x / 100 for k, x in cc["calage_agitation_pct_an"].items()}
    L = CC.Labo()
    T = L.T
    n = len(T["fill"])
    T["_idx"] = np.arange(n)
    est_chef = T["brique"] == 0
    niv = 0.09
    r_chef = CC.REF_CHEF * (niv / math.sqrt(2)) / ag["chef"]
    c_cass = CC.REF_CASS * (niv / math.sqrt(2)) / ag["cassure"]
    a = np.where(est_chef, r_chef * T["base_a"], np.minimum(1.0, c_cass * T["base_a"]))
    U = CC.sous(T, np.ones(n, bool), a)
    _, var = L.compte(U, np.ones(n, np.int64), "2017-08-01", fin)
    var.index = pd.DatetimeIndex(var.index).normalize()
    commun = j.index.intersection(var.index)
    out = {"variante": ret, "jours_communs": int(len(commun)), "fin": fin}
    for p, (de, a_) in {"2017-08 -> 2019": ("2017-08-01", "2020-01-01"), "2020-2023": ("2020-01-01", "2024-01-01"),
                        "2024-2026": ("2024-01-01", fin), "tout": ("2017-08-01", fin)}.items():
        c = commun[(commun >= pd.Timestamp(de)) & (commun < pd.Timestamp(a_))]
        if len(c) > 30:
            out[p] = float(np.corrcoef(j.loc[c, "gain"], var.loc[c])[0, 1])
    log(f"lien avec cassure + zones : {out}")
    ecrire("lien_compte_combine.json", out)


if __name__ == "__main__":
    VIE.mkdir(parents=True, exist_ok=True)
    ph = sys.argv[1] if len(sys.argv) > 1 else "choix"
    log(f"===== peur_options {ph} {datetime.now().isoformat(timespec='seconds')}")
    {"choix": phase_choix, "verif": phase_verif, "cachee": phase_cachee, "lien": phase_lien}[ph]()
    log("FINI")
