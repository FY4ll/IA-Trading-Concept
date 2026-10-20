"""PISTE « crypto_flux » — SUITE (16/10/2026, demande du coordinateur) : coûts par lieu, version « compte financé » de
C1, combinaison avec la cassure C2 et les zones du chef.

AVERTISSEMENT ÉCRIT D'AVANCE : toutes les années utilisées ici ont DÉJÀ été vues pour C1 (développement, contrôle et
groupe B ouverts dans crypto_flux.py). Tout ce qui suit est une ESTIMATION, PAS une preuve ; le seul juge restant est
le DIRECT. Les règles ci-dessous sont FIGÉES avant tout calcul (aucune n'est ajustée après coup ; tout est publié).

1. COÛTS PAR LIEU (mêmes trades C1 que crypto_flux.py : signal, tenue 24 h, taille 0,5 % d'agitation, 25 cryptos)
   (a) FTMO actuel : BTC 0,083 %, ETH 0,112 %, autres 0,12 % par aller-retour + nuit 30 %/an par minuit serveur.
   (b) Bourse, perpétuel, ordres au marché (preneur) : 0,05 % par côté + FINANCEMENT RÉEL : à chaque règlement T avec
       entrée < T <= sortie (heure de règlement arrondie à la seconde), l'acheteur paie taux x montant, le vendeur le
       reçoit (taux négatif : l'inverse). Fichiers data/binance_futures/funding.
   (c) Bourse, perpétuel, ordres limites (faiseur) : 70 % exécutés à 0,02 % par côté au même prix, 30 % en preneur à
       0,05 % -> 0,029 % par côté (aucun coût d'exécution défavorable compté : estimation optimiste) + financement réel.
   (d) Contrats à terme micro CME (BTC et ETH seulement) : commission 0,03 % aller-retour + écart 1 pas (micro bitcoin :
       5 points ; micro ether : 0,50 point ; en part du prix d'entrée), aucun financement (la base des contrats à terme
       n'est pas comptée). Séance CME (heure de New York) : dimanche 18h -> vendredi 17h, pause 17h-18h chaque jour :
       un trade dont l'entrée ou la sortie tombe hors séance est retiré.
   Tableau : %/mois après coûts, baisse max, force contre le jumeau ; groupes « développement » (BTC, ETH + A) et B ;
   périodes jusqu'à 2023 et 2024 -> 09/2026.

2. VERSION « COMPTE FINANCÉ » (figée ici)
   - Marchés (17, présents chez FTMO ou les sociétés crypto) : BTC, ETH, SOL, XRP, ADA, DOGE, LTC, BNB, LINK, AVAX, DOT,
     BCH, XLM, UNI, ETC, NEAR, ALGO.
   - Signal C1 tel quel (crypto_flux.signaux), décision à chaque fin d'heure UTC, entrée au prix comptant de clôture.
   - Risque 0,15 % du capital de DÉPART (150 $ sur 100 000 $) par trade ; stop à 1,5 x l'agitation journalière
     (agitation horaire des 14 jours passés x racine(24)) ; montant = 150 $ / (1,5 x agitation journalière).
     Stop vérifié sur les plus hauts / plus bas HORAIRES du comptant (bougies 15 min regroupées), exécuté au prix du stop.
   - Au plus 5 positions ouvertes, au plus 3 dans le même sens, 1 par crypto. Si plus de signaux que de places à la
     même heure : ordre fixe de la liste ci-dessus.
   - Arrêt du jour : si les fonds au plus mauvais prix de l'heure (latent compris) descendent de 2 % du capital de
     départ sous le solde du début du jour serveur -> tout est fermé à ces prix, plus aucune entrée ce jour-là.
   - Sortie à 24 h (clôture) si le stop n'a pas été touché.
   - Coûts (a) FTMO et (b) bourse preneur, comme au point 1 (moitié des frais à l'entrée, moitié à la sortie ; nuit
     payée à chaque minuit serveur franchi en (a) ; financement réel à chaque règlement en (b)).
   - Mesures par période (jusqu'à 2023 ; 2024 -> 09/2026) : %/mois, baisse max (fonds au plus bas contre le plus haut),
     pire jour (au plus bas dans la journée), force (sens x rendement brut par trade), challenges contre 20 JUMEAUX
     (sens tiré à pile ou face à chaque signal, mêmes règles de compte rejouées).
   - Challenge FTMO 2 étapes : départ tous les 10 jours ; +10 % puis +5 % (fin de journée, >= 4 jours avec une entrée),
     mort si fonds au plus bas <= solde du début du jour - 5 % du capital ou <= départ de l'étape - 10 % ; inachevé à
     24 mois. Société crypto type : une étape +10 %, -5 %/jour, -10 % au total, pas de minimum de jours.
   - Compte financé 12 mois après réussite (mêmes règles de mort ; retrait tous les 30 jours du gain au-dessus du
     niveau de départ, qui redevient le niveau de départ ; le reste compté à 12 mois).
   - Espérance d'un challenge 100 k$ à 540 € (remboursé à la réussite, même prix supposé pour la société crypto) :
     réussi en moins de 12 mois = 80 % des retraits du financé sur 12 mois (en €, dernier cours EURUSD) ; sinon -540 €.
     Départs gardés : >= 12 mois de données devant eux et, si réussi, financé connu sur 12 mois ou mort avant.
   - Taille fixe en dollars (pas de croissance du compte) : le chemin du compte ne dépend pas du jour de départ ; les
     challenges sont lus sur le compte continu (les positions ouvertes au passage d'étape continuent : approximation).

3. COMBINAISON (information) : compte = version « compte financé » de C1 au coût (b) + les deux briques de
   compte_combine au NIVEAU 9 % (cassure C2 BTC/ETH et zones du chef V1, telles quelles, recalculées par
   compte_combine.Labo, avec LEURS coûts FTMO : la cassure ne paie pas de nuit et ses frais FTMO 0,083-0,11 % sont proches
   de (b) ; les zones paient 30 %/an de nuit, plus cher que le financement moyen). Le niveau 9 % est celui que
   compte_combine présente comme seul positif : choix fait sur des années vues. Additions jour par jour (variations
   journalières en dollars), 2022-01 -> 2026-09. Mesures : %/mois, baisse max (clôtures journalières), pire jour
   (approché), lien jour par jour, challenges FTMO 2 étapes et espérance (sans jumeaux).

4. VARIANTE « C1-JOUR » (ajoutée le 16/10/2026 à la demande du coordinateur, ÉCRITE AVANT TOUT CALCUL, raisonnée sur la
   structure des coûts FTMO et non sur les résultats ; ESTIMATION, ANNÉES DÉJÀ VUES)
   - Même signal C1, mêmes entrées (fin d'heure UTC, une position à la fois par marché tant que les 24 h d'origine ne
     sont pas écoulées).
   - La position est FERMÉE à 23h45 serveur (clôture de la bougie 23h30-23h45) : jamais de position à minuit serveur,
     donc aucune nuit FTMO. Elle est ROUVERTE à 00h15 serveur le lendemain (clôture de la bougie 00h00-00h15),
     au même sens et à la même taille, SEULEMENT si le signal est toujours actif : C1 de la dernière fin d'heure UTC
     <= 00h15 serveur a le MÊME signe que le signal d'entrée (part des comptes encore dans l'extrême de 90 jours du même
     côté). Sortie définitive 24 h après l'entrée d'origine, ou à 23h45 si la réouverture n'a pas lieu (signal éteint ou
     24 h déjà atteintes).
   - Coût FTMO : frais d'un aller-retour par morceau (2 allers-retours si la position traverse minuit), aucune nuit.
     Comparée à C1 d'origine (un aller-retour + la nuit payée).
   - Mesures : (i) pleine taille (0,5 % d'agitation, comme crypto_flux) par groupe (développement, B) et période
     (jusqu'à 2023, 2024 -> 09/2026), challenges contre 20 jumeaux (sens tiré au hasard, même réouverture : celle-ci
     dépend du signal, pas du sens joué) ; (ii) version « compte financé » du point 2 (17 cryptos, 0,15 %, stop 1,5 x
     agitation du jour gardé au même prix après réouverture — pas de réouverture si le prix l'a déjà franchi —, 5
     positions dont 3 dans le même sens, une position fermée la nuit garde sa place, arrêt du jour -2 %) sur une grille de
     15 min (stops vérifiés sur les plus hauts / plus bas de 15 min), C1 d'origine recalculé sur la même grille pour
     comparer ; (iii) 3e brique avec cassure + zones (niveau 9 %), coût FTMO pour les trois.

Depuis Test_IA : venv_gpu\\Scripts\\python.exe -u -m collapsar.regarder.pistes.crypto_flux_compte couts|compte|combine|jour
"""
from __future__ import annotations

import json
import math
import sys
from datetime import datetime

import numpy as np
import pandas as pd
from numba import njit

from collapsar.donnees import marches as dm
from collapsar.regarder.pistes import crypto_flux as cf

VIE = cf.VIE
SORTIE = VIE / "suite.json"
CAP = 100_000.0
PRIX_EUR = 540.0
PART = 0.80
MARCHES = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "ADAUSDT", "DOGEUSDT", "LTCUSDT", "BNBUSDT", "LINKUSDT",
           "AVAXUSDT", "DOTUSDT", "BCHUSDT", "XLMUSDT", "UNIUSDT", "ETCUSDT", "NEARUSDT", "ALGOUSDT"]
RISQUE_USD, K_STOP, MAXPOS, MAXSENS, STOP_JOUR, TENUE = 150.0, 1.5, 5, 3, 0.02 * CAP, 24
JUMEAUX = 20
PERIODES = {"jusqu'à 2023": ("2020-01-01", "2024-01-01"), "2024 -> 09/2026": ("2024-01-01", "2026-10-01")}
DEBUT, FIN = pd.Timestamp("2020-01-01"), pd.Timestamp("2026-10-01")
PAS_CME = {"BTCUSDT": 5.0, "ETHUSDT": 0.5}


def lire_sortie() -> dict:
    return json.loads(SORTIE.read_text(encoding="utf-8")) if SORTIE.exists() else {}


def ecrire_sortie(cle, val):
    s = lire_sortie()
    s[cle] = val
    s["quand_" + cle] = datetime.now().isoformat(timespec="seconds")
    cf._ecrire(SORTIE, s)


# ---------------------------------------------------------------- financement
def financement(sym: str) -> pd.Series:
    fu = pd.read_csv(cf.FUT / "funding" / f"{sym}.csv")
    t = pd.DatetimeIndex(pd.to_datetime(fu["utc_ms"] // 1000, unit="s")).astype("datetime64[ns]")
    return pd.Series(fu["taux"].to_numpy(float), index=t).groupby(level=0).sum().sort_index()


def somme_fin(fs: pd.Series, entree, sortie) -> np.ndarray:
    """Somme des taux réglés à T avec entrée < T <= sortie."""
    cs = np.r_[0.0, np.cumsum(fs.to_numpy())]
    ti = fs.index.to_numpy()
    a = np.searchsorted(ti, np.asarray(entree, "datetime64[ns]"), "right")
    b = np.searchsorted(ti, np.asarray(sortie, "datetime64[ns]"), "right")
    return cs[b] - cs[a]


def seance_cme(t_utc) -> np.ndarray:
    ny = pd.DatetimeIndex(t_utc).tz_localize("UTC").tz_convert("America/New_York")
    h, wd = ny.hour.to_numpy(), ny.dayofweek.to_numpy()
    ok = (h != 17)
    ok &= ~((wd == 4) & (h >= 17)) & (wd != 5) & ~((wd == 6) & (h < 18))
    return ok


# ---------------------------------------------------------------- 1. coûts par lieu
def couts():
    gr = cf.groupes()
    out = {}
    for groupe, marches in (("développement (BTC, ETH + A)", gr["dev"]), ("groupe B", gr["B"])):
        parts = []
        for sym in marches:
            t = pd.read_pickle(cf.VIE / "cache" / f"{sym}_d0_spot.pkl")
            t = t[t["variante"] == "C1"].copy()
            if not len(t):
                continue
            fs = financement(sym)
            t["fin"] = somme_fin(fs, t["entree"], t["sortie"])
            parts.append(t)
        t = pd.concat(parts, ignore_index=True)
        s, r, ex = t["sens"].to_numpy(), t["r"].to_numpy(), t["expo"].to_numpy()
        lieux = {}
        lieux["a FTMO"] = (t["R"].to_numpy(), t["R_inverse"].to_numpy(), np.ones(len(t), bool))
        for nom, cote in (("b bourse preneur", 0.0005), ("c bourse faiseur 70 %", 0.7 * 0.0002 + 0.3 * 0.0005)):
            c = 2 * cote
            lieux[nom] = (ex * (s * r - c - s * t["fin"].to_numpy()), ex * (-s * r - c + s * t["fin"].to_numpy()),
                          np.ones(len(t), bool))
        pas = t["marche"].map(PAS_CME).to_numpy(float)
        px = t["prix_entree"].to_numpy(float) if "prix_entree" in t else np.nan
        # prix d'entrée : reconstruit à partir des prix horaires (le cache ne le garde pas)
        if not np.isfinite(px).all():
            px = np.full(len(t), np.nan)
            for sym in ("BTCUSDT", "ETHUSDT"):
                m = (t["marche"] == sym).to_numpy()
                if m.any():
                    sp = cf.spot_heures(sym)
                    px[m] = sp.reindex(pd.DatetimeIndex(t.loc[m, "entree"])).to_numpy()
        c_cme = 0.0003 + pas / px
        ok = np.isfinite(c_cme) & seance_cme(t["entree"]) & seance_cme(t["sortie"])
        lieux["d CME micro (BTC, ETH)"] = (ex * (s * r - c_cme), ex * (-s * r - c_cme), ok)
        res_g = {}
        for nom, (R, Ri, ok) in lieux.items():
            u = t[ok].copy()
            u["R"], u["R_inverse"] = R[ok], Ri[ok]
            u["nuits"] = u["nuits"] if nom.startswith("a") else 0
            res_g[nom] = {}
            for p, (de, a) in PERIODES.items():
                x = cf.note(u, pd.Timestamp(de), pd.Timestamp(a), challenges=False)
                res_g[nom][p] = x
                print(cf.ligne(f"{groupe[:12]} | {nom:22s} | {p:15s}", x), flush=True)
        fin_moy = t.groupby(t["entree"] >= "2024-01-01").apply(lambda g: float((g["sens"] * g["fin"]).mean() * 100))
        res_g["financement_paye_moyen_pct_par_trade"] = {("2024+" if k else "jusqu'à 2023"): v for k, v in fin_moy.items()}
        out[groupe] = res_g
    ecrire_sortie("couts_par_lieu", out)


# ---------------------------------------------------------------- 2. version « compte financé »
def heures_hl(sym: str, grille: pd.DatetimeIndex):
    """Plus haut / plus bas horaires du comptant (filtre commun), indexés par la fin d'heure UTC."""
    d = pd.read_csv(cf.SPOT / f"{sym}_M15.csv")
    d["time"] = pd.to_datetime(d["time"])
    d = d[d["time"] >= d["time"].iloc[0] + pd.Timedelta(days=7)].reset_index(drop=True)
    oc_min, oc_max = np.minimum(d["open"], d["close"]), np.maximum(d["open"], d["close"])
    krach = d["time"].dt.normalize().isin([pd.Timestamp("2025-10-10"), pd.Timestamp("2025-10-11")])
    fausse = ((d["low"] < 0.5 * d["close"]) | (d["high"] > 2 * d["close"])) & ~krach
    d.loc[fausse, "low"], d.loc[fausse, "high"] = oc_min[fausse], oc_max[fausse]
    fin = (cf.utc_depuis_serveur(d["time"]) + pd.Timedelta(minutes=15)).ceil("h")
    g = pd.DataFrame({"h": d["high"].to_numpy(float), "l": d["low"].to_numpy(float)}, index=fin)
    g = g.groupby(level=0).agg({"h": "max", "l": "min"}).reindex(grille)
    return g["h"].to_numpy(), g["l"].to_numpy()


def preparer():
    cache = VIE / "cache" / "compte_tableaux.npz"
    grille = pd.date_range(DEBUT, FIN, freq="h", inclusive="left").astype("datetime64[ns]")
    if cache.exists():
        z = np.load(cache)
        return {k: z[k] for k in z.files} | {"grille": grille}
    S, T = len(MARCHES), len(grille)
    C, Hh, Lw, SD, FUN = (np.full((S, T), np.nan) for _ in range(5))
    SIG = np.zeros((S, T), np.int8)
    for i, sym in enumerate(MARCHES):
        F = cf.caracteristiques(sym)
        sig = pd.Series(cf.signaux(F)["C1"], index=F.index).reindex(grille).fillna(0).astype(np.int8)
        SIG[i] = sig.to_numpy()
        C[i] = F["prix"].reindex(grille).ffill().to_numpy()
        SD[i] = (F["agit_h"] * math.sqrt(24)).reindex(grille).to_numpy()
        Hh[i], Lw[i] = heures_hl(sym, grille)
        fs = financement(sym)
        h = fs.index.ceil("h")
        FUN[i] = fs.groupby(h).sum().reindex(grille).fillna(0.0).to_numpy()
        del F
        print(f"  {sym} prêt ({int((SIG[i] != 0).sum())} heures avec signal)", flush=True)
    srv = cf.serveur(grille)
    jour_srv = srv.normalize()
    j0 = jour_srv.min()
    JOUR = ((jour_srv - j0).days).to_numpy().astype(np.int64)
    FR = np.array([cf.frais(s) for s in MARCHES])
    cache.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(cache, C=C, Hh=Hh, Lw=Lw, SD=SD, FUN=FUN, SIG=SIG, JOUR=JOUR, FR=FR,
                        J0=np.array([j0.value], np.int64))
    return {"C": C, "Hh": Hh, "Lw": Lw, "SD": SD, "FUN": FUN, "SIG": SIG, "JOUR": JOUR, "FR": FR,
            "J0": np.array([j0.value], np.int64), "grille": grille}


@njit(cache=True)
def simuler(C, Hh, Lw, SIG, SD, FUN, JOUR, frais_rt, use_fund, use_nuit, signes, risque, kstop, maxpos, maxsens,
            stop_jour, tenue, nuit_jour):
    S, T = C.shape
    nd = JOUR[-1] + 1
    jo = np.full((nd, 4), np.nan)
    ouvert = np.zeros(S, np.bool_)
    sens = np.zeros(S, np.int64)
    qty = np.zeros(S)
    pe = np.zeros(S)
    stp = np.zeros(S)
    t0 = np.zeros(S, np.int64)
    maxtr = 400000
    tr = np.zeros((maxtr, 7))           # marché, t0, t1, sens, montant, rendement brut, type (0 temps, 1 stop, 2 arrêt jour)
    ntr = 0
    solde = 0.0
    cur = -1
    arret = False
    for t in range(T):
        d = JOUR[t]
        if d != cur:
            if cur >= 0:
                eq = solde
                for s in range(S):
                    if ouvert[s]:
                        eq += qty[s] * sens[s] * (C[s, t - 1] / pe[s] - 1.0)
                jo[cur, 2] = eq
                if use_nuit:
                    for s in range(S):
                        if ouvert[s]:
                            solde -= qty[s] * nuit_jour * (d - cur)
            eq = solde
            for s in range(S):
                if ouvert[s]:
                    eq += qty[s] * sens[s] * (C[s, t - 1] / pe[s] - 1.0)
            jo[d, 0] = eq
            jo[d, 1] = eq
            jo[d, 3] = 0.0
            cur = d
            arret = False
        # financement réglé pendant l'heure (t-1, t]
        if use_fund:
            for s in range(S):
                if ouvert[s] and t0[s] < t:
                    solde -= qty[s] * sens[s] * FUN[s, t]
        # sorties : stop puis temps
        for s in range(S):
            if not ouvert[s]:
                continue
            x = -1.0
            ty = 0
            if sens[s] > 0 and Lw[s, t] <= stp[s]:
                x = stp[s]
                ty = 1
            elif sens[s] < 0 and Hh[s, t] >= stp[s]:
                x = stp[s]
                ty = 1
            elif t >= t0[s] + tenue:
                x = C[s, t]
            if x > 0:
                g = sens[s] * (x / pe[s] - 1.0)
                solde += qty[s] * (g - frais_rt[s] * 0.5)
                ouvert[s] = False
                if ntr < maxtr:
                    tr[ntr, 0], tr[ntr, 1], tr[ntr, 2], tr[ntr, 3] = s, t0[s], t, sens[s]
                    tr[ntr, 4], tr[ntr, 5], tr[ntr, 6] = qty[s], g, ty
                    ntr += 1
        # fonds au plus mauvais prix de l'heure
        pire = solde
        for s in range(S):
            if ouvert[s]:
                w = Lw[s, t] if sens[s] > 0 else Hh[s, t]
                if not (w > 0):
                    w = C[s, t]
                pire += qty[s] * sens[s] * (w / pe[s] - 1.0)
        if pire < jo[d, 1]:
            jo[d, 1] = pire
        if (not arret) and pire - jo[d, 0] <= -stop_jour:
            arret = True
            for s in range(S):
                if ouvert[s]:
                    w = Lw[s, t] if sens[s] > 0 else Hh[s, t]
                    if not (w > 0):
                        w = C[s, t]
                    g = sens[s] * (w / pe[s] - 1.0)
                    solde += qty[s] * (g - frais_rt[s] * 0.5)
                    ouvert[s] = False
                    if ntr < maxtr:
                        tr[ntr, 0], tr[ntr, 1], tr[ntr, 2], tr[ntr, 3] = s, t0[s], t, sens[s]
                        tr[ntr, 4], tr[ntr, 5], tr[ntr, 6] = qty[s], g, 2
                        ntr += 1
        # entrées
        if not arret and t + tenue < T:
            n_ouv = 0
            n_achat = 0
            for s in range(S):
                if ouvert[s]:
                    n_ouv += 1
                    if sens[s] > 0:
                        n_achat += 1
            for s in range(S):
                if SIG[s, t] == 0 or ouvert[s]:
                    continue
                if not (C[s, t] > 0 and SD[s, t] > 0):
                    continue
                dr = SIG[s, t] * signes[s, t]
                if n_ouv >= maxpos:
                    break
                if dr > 0 and n_achat >= maxsens:
                    continue
                if dr < 0 and (n_ouv - n_achat) >= maxsens:
                    continue
                ouvert[s] = True
                sens[s] = dr
                pe[s] = C[s, t]
                qty[s] = risque / (kstop * SD[s, t])
                stp[s] = pe[s] * (1.0 - dr * kstop * SD[s, t])
                t0[s] = t
                solde -= qty[s] * frais_rt[s] * 0.5
                n_ouv += 1
                if dr > 0:
                    n_achat += 1
                jo[d, 3] += 1
        eq = solde
        for s in range(S):
            if ouvert[s]:
                eq += qty[s] * sens[s] * (C[s, t] / pe[s] - 1.0)
        jo[d, 2] = eq
    return jo, tr[:ntr]


def challenge(S0, M, E, N, d0, etapes, mini, max_jours=730):
    """(issue 0 réussi / 1 mort / 3 inachevé, jour de réussite) sur les tableaux journaliers (dollars)."""
    n = len(S0)
    d = d0
    for but in etapes:
        base, jt = S0[d] if d < n else np.nan, 0
        while True:
            if d >= n or d - d0 > max_jours:
                return 3, -1
            if M[d] - S0[d] <= -0.05 * CAP or M[d] - base <= -0.10 * CAP:
                return 1, -1
            jt += N[d] > 0
            if E[d] - base >= but * CAP and jt >= mini:
                d += 1
                break
            d += 1
    return 0, d - 1


def finance(S0, M, E, d1):
    """Compte financé de d1 à d1+365 : (gains retirés en $, mort, complet)."""
    n = len(S0)
    if d1 >= n:
        return 0.0, False, False
    base = S0[d1]
    retire = 0.0
    for k in range(365):
        d = d1 + k
        if d >= n:
            return retire, False, False
        if M[d] - S0[d] <= -0.05 * CAP or M[d] - base <= -0.10 * CAP:
            return retire, True, True
        if k > 0 and k % 30 == 0 and E[d] > base:
            retire += E[d] - base
            base = E[d]
    d = d1 + 364
    if E[d] > base:
        retire += E[d] - base
    return retire, False, True


def bilan_challenges(jo, jours, de, a, regle, eurusd):
    S0, M, E, N = jo[:, 0], jo[:, 1], jo[:, 2], jo[:, 3]
    ok = np.isfinite(S0)
    S0, M, E, N = (np.where(ok, x, 0.0) for x in (S0, M, E, N))
    etapes, mini = ((0.10, 0.05), 4) if regle == "FTMO" else ((0.10,), 0)
    d_de = int(np.searchsorted(jours, np.datetime64(pd.Timestamp(de))))
    d_a = int(np.searchsorted(jours, np.datetime64(pd.Timestamp(a))))
    if (N > 0).any():
        d_de = max(d_de, int(np.argmax(N > 0)))           # pas de départ avant le premier trade possible
    n = len(S0)
    res = []
    for d0 in range(d_de, d_a, 10):
        iss, dr = challenge(S0, M, E, N, d0, etapes, mini)
        v12 = iss == 0 and dr - d0 <= 365
        v6 = iss == 0 and dr - d0 <= 183
        val, garde = None, d0 + 365 <= n
        if v12:
            retire, mort, complet = finance(S0, M, E, dr + 1)
            garde = garde and complet
            val = PART * retire / eurusd
        else:
            val = -PRIX_EUR
        res.append((iss, v6, v12, val, garde))
    if not res:
        return {"departs": 0}
    r = np.array([(x[0], x[1], x[2], x[3], x[4]) for x in res], dtype=float)
    g = r[:, 4] > 0
    return {"departs": len(r), "reussis_pct": float((r[:, 0] == 0).mean() * 100),
            "morts_pct": float((r[:, 0] == 1).mean() * 100), "reussis_6mois_pct": float(r[:, 1].mean() * 100),
            "reussis_12mois_pct": float(r[:, 2].mean() * 100),
            "esperance_eur": float(r[g, 3].mean()) if g.any() else None, "departs_esperance": int(g.sum())}


def mesures_compte(jo, tr, jours, de, a):
    d_de = int(np.searchsorted(jours, np.datetime64(pd.Timestamp(de))))
    d_a = int(np.searchsorted(jours, np.datetime64(pd.Timestamp(a))))
    N = np.nan_to_num(jo[:, 3])
    if (N > 0).any():
        d_de = max(d_de, int(np.argmax(N > 0)))           # mois comptés à partir du premier trade possible
    S0, M, E = jo[d_de:d_a, 0], jo[d_de:d_a, 1], jo[d_de:d_a, 2]
    ok = np.isfinite(S0)
    S0, M, E = S0[ok], M[ok], E[ok]
    if not len(E):
        return {}
    pic = np.maximum.accumulate(np.r_[S0[0], E])[:-1]
    mois = len(E) / 30.44
    j_t = tr[:, 1].astype(np.int64)
    return {"gain_pct_mois": float((E[-1] - S0[0]) / CAP / mois * 100),
            "baisse_max_pct": float(np.min(M - np.maximum(pic, S0)) / CAP * 100),
            "pire_jour_pct": float(np.min(M - S0) / CAP * 100), "jours": int(len(E))}


def compte():
    eurusd = float(dm.charger("EURUSD", pd.Timestamp("2100-01-01"))["close"].iloc[-1])
    D = preparer()
    grille = D["grille"]
    j0 = pd.Timestamp(int(D["J0"][0]))
    nd = int(D["JOUR"][-1]) + 1
    jours = (j0 + pd.to_timedelta(np.arange(nd), unit="D")).to_numpy()
    S, T = D["C"].shape
    rng = np.random.default_rng(7)
    jum = [rng.choice(np.array([-1, 1], np.int8), (S, T)) for _ in range(JUMEAUX)]
    un = np.ones((S, T), np.int8)
    out = {"eurusd": eurusd}
    series = {}
    for cout, (uf, un_) in {"a FTMO": (False, True), "b bourse preneur": (True, False)}.items():
        fr = D["FR"] if cout.startswith("a") else np.full(S, 0.0010)
        args = (D["C"], D["Hh"], D["Lw"], D["SIG"], D["SD"], D["FUN"], D["JOUR"], fr, uf, un_)
        reste = (RISQUE_USD, K_STOP, MAXPOS, MAXSENS, STOP_JOUR, TENUE, cf.NUIT_AN / 360.0)
        jo, tr = simuler(*args, un, *reste)
        series[cout] = (jo, tr)
        jos = [simuler(*args, sg, *reste)[0] for sg in jum]
        res_c = {}
        for p, (de, a) in PERIODES.items():
            x = mesures_compte(jo, tr, jours, de, a)
            msk = (grille[tr[:, 1].astype(np.int64)] >= pd.Timestamp(de)) & (grille[tr[:, 1].astype(np.int64)] < pd.Timestamp(a))
            g = tr[msk, 5]
            x["trades"] = int(msk.sum())
            x["trades_mois"] = float(msk.sum() / (x.get("jours", 1) / 30.44))
            x["force"] = float(g.mean() / g.std(ddof=1) * math.sqrt(len(g))) if len(g) > 20 else None
            x["stops_pct"] = float((tr[msk, 6] == 1).mean() * 100) if msk.any() else None
            x["arrets_jour"] = int((tr[msk, 6] == 2).sum())
            x["montant_moyen_usd"] = float(tr[msk, 4].mean()) if msk.any() else None
            for regle in ("FTMO", "crypto"):
                v = bilan_challenges(jo, jours, de, a, regle, eurusd)
                jm = [bilan_challenges(j, jours, de, a, regle, eurusd) for j in jos]
                x[f"challenge_{regle}"] = v
                x[f"jumeaux_{regle}"] = {k: float(np.mean([j[k] for j in jm if j.get(k) is not None]))
                                         for k in ("reussis_pct", "morts_pct", "reussis_6mois_pct", "reussis_12mois_pct",
                                                   "esperance_eur")
                                         if any(j.get(k) is not None for j in jm)}
            res_c[p] = x
            f = x["challenge_FTMO"]
            fj = x["jumeaux_FTMO"]
            c = x["challenge_crypto"]
            print(f"{cout:17s} | {p:15s} | {x['trades']:5d} tr | {x['gain_pct_mois']:+.2f} %/mois | baisse "
                  f"{x['baisse_max_pct']:.1f} % | pire j {x['pire_jour_pct']:.2f} % | force {x['force']:+.2f} | "
                  f"FTMO {f['reussis_pct']:.0f}/{f['morts_pct']:.0f} <6 m {f['reussis_6mois_pct']:.0f} <12 m "
                  f"{f['reussis_12mois_pct']:.0f} esp {f['esperance_eur']} (jum {fj.get('reussis_pct', 0):.0f}/"
                  f"{fj.get('morts_pct', 0):.0f}, esp {fj.get('esperance_eur')}) | crypto {c['reussis_pct']:.0f}/"
                  f"{c['morts_pct']:.0f} <12 m {c['reussis_12mois_pct']:.0f} esp {c['esperance_eur']}", flush=True)
        out[cout] = res_c
        np.save(VIE / "cache" / f"compte_jours_{cout[0]}.npy", jo)
    np.save(VIE / "cache" / "compte_jours_dates.npy", jours.astype("datetime64[ns]").astype(np.int64))
    ecrire_sortie("compte_finance", out)


# ---------------------------------------------------------------- 3. combinaison (générale)
def briques_9pct(de, a):
    """Variations journalières en dollars des deux briques de compte_combine au niveau 9 % (coûts FTMO)."""
    from collapsar.regarder.pistes import compte_combine as CC
    lab = CC.Labo()
    T = lab.T
    n = len(T["fill"])
    T["_idx"] = np.arange(n)
    est_chef, est_cass = T["brique"] == 0, T["brique"] == 1
    un = np.ones(n, np.int64)
    a_ref = np.where(est_chef, CC.REF_CHEF * T["base_a"], np.minimum(1.0, CC.REF_CASS * T["base_a"]))
    ag = {}
    for nom, garde in (("chef", est_chef), ("cassure", est_cass)):
        x, _ = lab.compte(CC.sous(T, garde, a_ref), un[garde], *CC.CALAGE, securite=False)
        ag[nom] = x["agitation_pct_an"] / 100
    niv = 0.09
    r_chef = CC.REF_CHEF * (niv / math.sqrt(2)) / ag["chef"]
    c_cass = CC.REF_CASS * (niv / math.sqrt(2)) / ag["cassure"]
    aa = np.where(est_chef, r_chef * T["base_a"], np.minimum(1.0, c_cass * T["base_a"]))
    var = {}
    for nom, garde in (("cassure C2", est_cass), ("zones du chef", est_chef)):
        _, v = lab.compte(CC.sous(T, garde, aa), un[garde], de, a)
        var[nom] = v * CAP                                  # variation journalière en dollars (approchée)
    return var, lab.eurusd


def combiner(sources: dict, cle: str, de="2022-01-01", a="2026-10-01"):
    """sources = {nom: (tableau journalier jo [S0, M, E, N], dates)} ; chaque source est évaluée seule, puis
    + cassure + zones. Addition jour par jour (approchée)."""
    var, eurusd = briques_9pct(de, a)
    idx = pd.date_range(de, pd.Timestamp(a) - pd.Timedelta(days=1))
    briques = {k: v.reindex(idx, fill_value=0.0) for k, v in var.items()}
    out = {"niveau_briques": "9 %", "periode": f"{de} -> 2026-09-30", "lien_jour_par_jour": {}, "comptes": {}}
    comptes = {"cassure C2 + zones (niveau 9 %)": (None, list(briques.values()))}
    for nom, (jo, jours) in sources.items():
        c1 = pd.DataFrame(jo, index=pd.DatetimeIndex(jours), columns=["S0", "M", "E", "N"]).dropna()
        dc1 = (c1["E"] - c1["S0"]).reindex(idx, fill_value=0.0)
        m1 = (c1["M"] - c1["S0"]).reindex(idx, fill_value=0.0)
        n1 = c1["N"].reindex(idx, fill_value=0.0)
        comptes[f"{nom} seul"] = ((dc1, m1, n1), [])
        comptes[f"{nom} + cassure + zones"] = ((dc1, m1, n1), list(briques.values()))
        out["lien_jour_par_jour"][nom] = {k: float(np.corrcoef(dc1[(dc1 != 0) | (v != 0)], v[(dc1 != 0) | (v != 0)])[0, 1])
                                          for k, v in briques.items()}
    print("liens :", out["lien_jour_par_jour"], flush=True)
    for nom, (c1, autres) in comptes.items():
        zero = pd.Series(0.0, index=idx)
        dc1, m1, n1 = c1 if c1 is not None else (zero, zero, zero)
        aut = sum(autres) if autres else zero
        d = dc1 + aut
        E = CAP + d.cumsum()
        S0 = E - d
        M = S0 + np.minimum(m1 + np.minimum(aut, 0.0), d)
        N = n1 + (1.0 if autres else 0.0)
        jo_c = np.c_[S0.to_numpy(), M.to_numpy(), E.to_numpy(), N.to_numpy()]
        res = {}
        for p, (pd_, pa) in {"2022-2023": ("2022-01-01", "2024-01-01"), "2024 -> 09/2026": ("2024-01-01", a),
                             "tout": (de, a)}.items():
            msk = (idx >= pd.Timestamp(pd_)) & (idx < pd.Timestamp(pa))
            s0, mm, ee = S0[msk].to_numpy(), M[msk].to_numpy(), E[msk].to_numpy()
            pic = np.maximum.accumulate(np.r_[s0[0], ee])[:-1]
            x = {"gain_pct_mois": float((ee[-1] - s0[0]) / CAP / (msk.sum() / 30.44) * 100),
                 "baisse_max_pct": float(np.min(mm - np.maximum(pic, s0)) / CAP * 100),
                 "pire_jour_pct": float(np.min(mm - s0) / CAP * 100),
                 "agitation_pct_an": float(d[msk].std() / CAP * math.sqrt(365) * 100)}
            x["challenge_FTMO"] = bilan_challenges(jo_c, idx.to_numpy(), pd_, pa, "FTMO", eurusd)
            res[p] = x
            f = x["challenge_FTMO"]
            print(f"{nom:40s} | {p:15s} | {x['gain_pct_mois']:+.2f} %/mois | baisse {x['baisse_max_pct']:.1f} % | "
                  f"pire j {x['pire_jour_pct']:.2f} % | agitation {x['agitation_pct_an']:.1f} %/an | FTMO "
                  f"{f.get('reussis_pct', 0):.0f}/{f.get('morts_pct', 0):.0f} <6 m {f.get('reussis_6mois_pct', 0):.0f}"
                  f" <12 m {f.get('reussis_12mois_pct', 0):.0f} esp {f.get('esperance_eur')}", flush=True)
        out["comptes"][nom] = res
    ecrire_sortie(cle, out)


def combine():
    jours = np.load(VIE / "cache" / "compte_jours_dates.npy").astype("datetime64[ns]")
    combiner({"C1 (coût b)": (np.load(VIE / "cache" / "compte_jours_b.npy"), jours)}, "combinaison")


# ---------------------------------------------------------------- 4. C1-JOUR
def spot15(sym: str) -> pd.DataFrame:
    """Bougies 15 min comptant (filtre commun), indexées par la FIN de bougie en UTC."""
    d = pd.read_csv(cf.SPOT / f"{sym}_M15.csv")
    d["time"] = pd.to_datetime(d["time"])
    d = d[d["time"] >= d["time"].iloc[0] + pd.Timedelta(days=7)].reset_index(drop=True)
    oc_min, oc_max = np.minimum(d["open"], d["close"]), np.maximum(d["open"], d["close"])
    krach = d["time"].dt.normalize().isin([pd.Timestamp("2025-10-10"), pd.Timestamp("2025-10-11")])
    fausse = ((d["low"] < 0.5 * d["close"]) | (d["high"] > 2 * d["close"])) & ~krach
    d.loc[fausse, "low"], d.loc[fausse, "high"] = oc_min[fausse], oc_max[fausse]
    fin = cf.utc_depuis_serveur(d["time"]) + pd.Timedelta(minutes=15)
    x = pd.DataFrame({"c": d["close"].to_numpy(float), "h": d["high"].to_numpy(float), "l": d["low"].to_numpy(float)},
                     index=fin)
    return x[~x.index.duplicated()]


def vers_utc(srv: pd.DatetimeIndex) -> pd.DatetimeIndex:
    """Heure serveur -> UTC (sans ambiguïté pour 23h45 et 00h15 serveur = 16h45 / 17h15 à New York)."""
    ny = pd.DatetimeIndex(srv) - pd.Timedelta(hours=7)
    return ny.tz_localize("America/New_York").tz_convert("UTC").tz_localize(None).astype("datetime64[ns]")


def _prix_a(p: pd.Series, tt: pd.DatetimeIndex) -> np.ndarray:
    """Dernière clôture connue à chaque instant tt (fin de bougie <= tt)."""
    i = np.searchsorted(p.index.to_numpy(), tt.to_numpy(), "right") - 1
    v = p.to_numpy()
    return np.where(i >= 0, v[np.clip(i, 0, None)], np.nan)


def morceaux_jour(t: pd.DataFrame, px: pd.Series, act: pd.Series, frais_rt: float) -> pd.DataFrame:
    """Trades C1 d'origine -> trades C1-JOUR (1 ou 2 morceaux). px = clôtures 15 min (fin UTC), act = signal C1 horaire."""
    e = pd.DatetimeIndex(t["entree"]).astype("datetime64[ns]")
    s24 = pd.DatetimeIndex(t["sortie"]).astype("datetime64[ns]")
    jsrv = cf.serveur(e).normalize()
    c_utc = vers_utc(jsrv + pd.Timedelta(hours=23, minutes=45))
    r_utc = vers_utc(jsrv + pd.Timedelta(days=1, minutes=15))
    p = px.sort_index()
    un = np.asarray(s24 <= c_utc)
    fin1 = pd.DatetimeIndex(np.where(un, s24, c_utc))
    a_act = _prix_a(act.sort_index().astype(float), r_utc.floor("h"))
    s = t["sens"].to_numpy()
    rouvre = (~un) & np.asarray(r_utc < s24) & (a_act == s)
    pe, p1 = _prix_a(p, e), _prix_a(p, fin1)
    p2a, p2b = _prix_a(p, r_utc), _prix_a(p, s24)
    g1 = p1 / pe - 1
    g2 = np.where(rouvre, p2b / p2a - 1, 0.0)
    n_ar = 1 + rouvre.astype(int)
    out = t.copy()
    fin = pd.DatetimeIndex(np.where(rouvre, s24, fin1))
    out["sortie"] = fin
    out["jour_sortie"] = cf.serveur(fin).normalize()
    out["nuits"] = 0
    out["rouverte"] = rouvre
    out["r"] = (1 + g1) * (1 + g2) - 1                       # rendement composé des morceaux (information)
    ok = np.isfinite(g1) & np.isfinite(g2)
    ex = out["expo"].to_numpy()
    out["R"] = ex * (s * (g1 + g2) - n_ar * frais_rt)
    out["R_inverse"] = ex * (-s * (g1 + g2) - n_ar * frais_rt)
    return out[ok]


def jour_pleine_taille():
    gr = cf.groupes()
    res = {}
    for groupe, marches in (("développement (BTC, ETH + A)", gr["dev"]), ("groupe B", gr["B"])):
        orig, jr = [], []
        for sym in marches:
            t = pd.read_pickle(cf.VIE / "cache" / f"{sym}_d0_spot.pkl")
            t = t[t["variante"] == "C1"].copy()
            if not len(t):
                continue
            F = cf.caracteristiques(sym)
            act = pd.Series(cf.signaux(F)["C1"], index=F.index)
            del F
            px = spot15(sym)["c"]
            orig.append(t)
            jr.append(morceaux_jour(t, px, act, cf.frais(sym)))
        o, j = pd.concat(orig, ignore_index=True), pd.concat(jr, ignore_index=True)
        res[groupe] = {"rouvertes_pct": float(j["rouverte"].mean() * 100)}
        for nom, u in (("C1 d'origine (nuit payée)", o), ("C1-JOUR", j)):
            res[groupe][nom] = {}
            for p, (de, a) in PERIODES.items():
                x = cf.note(u, pd.Timestamp(de), pd.Timestamp(a))
                res[groupe][nom][p] = x
                print(cf.ligne(f"{groupe[:12]} | {nom:25s} | {p:15s}", x), flush=True)
        print(f"{groupe}: morceaux rouverts {res[groupe]['rouvertes_pct']:.0f} %", flush=True)
    ecrire_sortie("c1_jour_pleine_taille", res)


def preparer15():
    cache = VIE / "cache" / "compte15_tableaux.npz"
    grille = pd.date_range(DEBUT + pd.Timedelta(minutes=15), FIN, freq="15min").astype("datetime64[ns]")
    if cache.exists():
        z = np.load(cache)
        return {k: z[k] for k in z.files} | {"grille": grille}
    S, T = len(MARCHES), len(grille)
    C, Hh, Lw, SD = (np.full((S, T), np.nan) for _ in range(4))
    SIG, ACT = np.zeros((S, T), np.int8), np.zeros((S, T), np.int8)
    for i, sym in enumerate(MARCHES):
        F = cf.caracteristiques(sym)
        sh = pd.Series(cf.signaux(F)["C1"], index=F.index).astype(float)
        SIG[i] = sh.reindex(grille).fillna(0).astype(np.int8).to_numpy()       # décisions aux fins d'heure
        ACT[i] = sh.reindex(grille).ffill().fillna(0).astype(np.int8).to_numpy()
        SD[i] = (F["agit_h"] * math.sqrt(24)).reindex(grille).ffill().to_numpy()
        del F
        x = spot15(sym).reindex(grille)
        C[i] = x["c"].ffill(limit=8).to_numpy()
        Hh[i], Lw[i] = x["h"].to_numpy(), x["l"].to_numpy()
        print(f"  {sym} prêt (15 min)", flush=True)
    srv = cf.serveur(grille)
    hm = srv.hour * 60 + srv.minute
    FERME = np.asarray(hm == 23 * 60 + 45)
    REOUV = np.asarray(hm == 15)
    jour_srv = (srv - pd.Timedelta(minutes=15)).normalize()      # jour serveur de la bougie (fin 00h00 = veille)
    j0 = jour_srv.min()
    JOUR = ((jour_srv - j0).days).to_numpy().astype(np.int64)
    FR = np.array([cf.frais(s) for s in MARCHES])
    np.savez_compressed(cache, C=C, Hh=Hh, Lw=Lw, SD=SD, SIG=SIG, ACT=ACT, FERME=FERME, REOUV=REOUV, JOUR=JOUR, FR=FR,
                        J0=np.array([j0.value], np.int64))
    return {"C": C, "Hh": Hh, "Lw": Lw, "SD": SD, "SIG": SIG, "ACT": ACT, "FERME": FERME, "REOUV": REOUV, "JOUR": JOUR,
            "FR": FR, "J0": np.array([j0.value], np.int64), "grille": grille}


@njit(cache=True)
def simuler15(C, Hh, Lw, SIG, ACT, SD, JOUR, FERME, REOUV, frais_rt, use_nuit, mode_jour, signes, risque, kstop,
              maxpos, maxsens, stop_jour, tenue, nuit_jour):
    """Compte « financé » sur grille 15 min. etat : 0 libre, 1 ouvert, 2 fermé pour la nuit (garde sa place)."""
    S, T = C.shape
    nd = JOUR[-1] + 1
    jo = np.full((nd, 4), np.nan)
    etat = np.zeros(S, np.int64)
    sens = np.zeros(S, np.int64)
    sig0 = np.zeros(S, np.int64)
    qty = np.zeros(S)
    pe = np.zeros(S)
    stp = np.zeros(S)
    t0 = np.zeros(S, np.int64)
    maxtr = 600000
    tr = np.zeros((maxtr, 7))           # marché, t0 (entrée d'origine), fin du morceau, sens, montant, brut, type
    ntr = 0
    solde = 0.0
    cur = -1
    arret = False
    for t in range(T):
        d = JOUR[t]
        if d != cur:
            if cur >= 0:
                eq = solde
                for s in range(S):
                    if etat[s] == 1:
                        eq += qty[s] * sens[s] * (C[s, t - 1] / pe[s] - 1.0)
                jo[cur, 2] = eq
                if use_nuit:
                    for s in range(S):
                        if etat[s] == 1:
                            solde -= qty[s] * nuit_jour * (d - cur)
            eq = solde
            for s in range(S):
                if etat[s] == 1:
                    eq += qty[s] * sens[s] * (C[s, t - 1] / pe[s] - 1.0)
            jo[d, 0] = eq
            jo[d, 1] = eq
            jo[d, 3] = 0.0
            cur = d
            arret = False
        # sorties
        for s in range(S):
            if etat[s] == 2 and t >= t0[s] + tenue:
                etat[s] = 0
            if etat[s] != 1:
                continue
            x = -1.0
            ty = 0
            nouvel = 0
            if sens[s] > 0 and Lw[s, t] <= stp[s]:
                x = stp[s]
                ty = 1
            elif sens[s] < 0 and Hh[s, t] >= stp[s]:
                x = stp[s]
                ty = 1
            elif t >= t0[s] + tenue:
                x = C[s, t]
            elif mode_jour and FERME[t]:
                x = C[s, t]
                ty = 3
                nouvel = 2
            if x > 0:
                g = sens[s] * (x / pe[s] - 1.0)
                solde += qty[s] * (g - frais_rt[s] * 0.5)
                etat[s] = nouvel
                if ntr < maxtr:
                    tr[ntr, 0], tr[ntr, 1], tr[ntr, 2], tr[ntr, 3] = s, t0[s], t, sens[s]
                    tr[ntr, 4], tr[ntr, 5], tr[ntr, 6] = qty[s], g, ty
                    ntr += 1
        # réouverture à 00h15 serveur
        if mode_jour and REOUV[t]:
            for s in range(S):
                if etat[s] != 2:
                    continue
                c = C[s, t]
                ok = (not arret) and t < t0[s] + tenue and ACT[s, t] == sig0[s] and c > 0
                ok = ok and ((sens[s] > 0 and c > stp[s]) or (sens[s] < 0 and c < stp[s]))
                if ok:
                    etat[s] = 1
                    pe[s] = c
                    solde -= qty[s] * frais_rt[s] * 0.5
                else:
                    etat[s] = 0
        # fonds au plus mauvais prix
        pire = solde
        for s in range(S):
            if etat[s] == 1:
                w = Lw[s, t] if sens[s] > 0 else Hh[s, t]
                if not (w > 0):
                    w = C[s, t]
                pire += qty[s] * sens[s] * (w / pe[s] - 1.0)
        if pire < jo[d, 1]:
            jo[d, 1] = pire
        if (not arret) and pire - jo[d, 0] <= -stop_jour:
            arret = True
            for s in range(S):
                if etat[s] == 1:
                    w = Lw[s, t] if sens[s] > 0 else Hh[s, t]
                    if not (w > 0):
                        w = C[s, t]
                    g = sens[s] * (w / pe[s] - 1.0)
                    solde += qty[s] * (g - frais_rt[s] * 0.5)
                    if ntr < maxtr:
                        tr[ntr, 0], tr[ntr, 1], tr[ntr, 2], tr[ntr, 3] = s, t0[s], t, sens[s]
                        tr[ntr, 4], tr[ntr, 5], tr[ntr, 6] = qty[s], g, 2
                        ntr += 1
                if etat[s] != 0:
                    etat[s] = 0
        # entrées (fins d'heure seulement : SIG nul ailleurs)
        if not arret and t + tenue < T:
            n_ouv = 0
            n_achat = 0
            for s in range(S):
                if etat[s] != 0:
                    n_ouv += 1
                    if sens[s] > 0:
                        n_achat += 1
            for s in range(S):
                if SIG[s, t] == 0 or etat[s] != 0:
                    continue
                if not (C[s, t] > 0 and SD[s, t] > 0):
                    continue
                dr = SIG[s, t] * signes[s, t]
                if n_ouv >= maxpos:
                    break
                if dr > 0 and n_achat >= maxsens:
                    continue
                if dr < 0 and (n_ouv - n_achat) >= maxsens:
                    continue
                etat[s] = 1
                sens[s] = dr
                sig0[s] = SIG[s, t]
                pe[s] = C[s, t]
                qty[s] = risque / (kstop * SD[s, t])
                stp[s] = pe[s] * (1.0 - dr * kstop * SD[s, t])
                t0[s] = t
                solde -= qty[s] * frais_rt[s] * 0.5
                n_ouv += 1
                if dr > 0:
                    n_achat += 1
                jo[d, 3] += 1
        eq = solde
        for s in range(S):
            if etat[s] == 1:
                eq += qty[s] * sens[s] * (C[s, t] / pe[s] - 1.0)
        jo[d, 2] = eq
    return jo, tr[:ntr]


def jour_compte():
    eurusd = float(dm.charger("EURUSD", pd.Timestamp("2100-01-01"))["close"].iloc[-1])
    D = preparer15()
    grille = D["grille"]
    j0 = pd.Timestamp(int(D["J0"][0]))
    nd = int(D["JOUR"][-1]) + 1
    jours = (j0 + pd.to_timedelta(np.arange(nd), unit="D")).to_numpy()
    S, T = D["C"].shape
    rng = np.random.default_rng(7)
    jum = [rng.choice(np.array([-1, 1], np.int8), (S, T)) for _ in range(JUMEAUX)]
    un = np.ones((S, T), np.int8)
    out, sources = {"eurusd": eurusd}, {}
    for nom, (nuit, mj) in {"C1 d'origine (nuit payée)": (True, False), "C1-JOUR": (False, True)}.items():
        args = (D["C"], D["Hh"], D["Lw"], D["SIG"], D["ACT"], D["SD"], D["JOUR"], D["FERME"], D["REOUV"], D["FR"],
                nuit, mj)
        reste = (RISQUE_USD, K_STOP, MAXPOS, MAXSENS, STOP_JOUR, 96, cf.NUIT_AN / 360.0)
        jo, tr = simuler15(*args, un, *reste)
        jos = [simuler15(*args, sg, *reste)[0] for sg in jum]
        res = {}
        for p, (de, a) in PERIODES.items():
            x = mesures_compte(jo, tr, jours, de, a)
            te = grille[tr[:, 1].astype(np.int64)]
            msk = np.asarray((te >= pd.Timestamp(de)) & (te < pd.Timestamp(a)))
            g = pd.Series(tr[msk, 5]).groupby([tr[msk, 0], tr[msk, 1]]).sum().to_numpy()
            x["trades"] = int(len(g))
            x["morceaux"] = int(msk.sum())
            x["force"] = float(g.mean() / g.std(ddof=1) * math.sqrt(len(g))) if len(g) > 20 else None
            x["stops_pct"] = float((tr[msk, 6] == 1).sum() / max(1, len(g)) * 100)
            for regle in ("FTMO", "crypto"):
                v = bilan_challenges(jo, jours, de, a, regle, eurusd)
                jm = [bilan_challenges(j, jours, de, a, regle, eurusd) for j in jos]
                x[f"challenge_{regle}"] = v
                x[f"jumeaux_{regle}"] = {k: float(np.mean([j[k] for j in jm if j.get(k) is not None]))
                                         for k in ("reussis_pct", "morts_pct", "reussis_6mois_pct", "reussis_12mois_pct",
                                                   "esperance_eur") if any(j.get(k) is not None for j in jm)}
            res[p] = x
            f, fj = x["challenge_FTMO"], x["jumeaux_FTMO"]
            print(f"{nom:26s} | {p:15s} | {x['trades']:5d} tr ({x['morceaux']} morceaux) | {x['gain_pct_mois']:+.2f} %/mois"
                  f" | baisse {x['baisse_max_pct']:.1f} % | pire j {x['pire_jour_pct']:.2f} % | force {x['force']:+.2f} | "
                  f"FTMO {f['reussis_pct']:.0f}/{f['morts_pct']:.0f} <6 m {f['reussis_6mois_pct']:.0f} <12 m "
                  f"{f['reussis_12mois_pct']:.0f} esp {f['esperance_eur']} (jum {fj.get('reussis_pct', 0):.0f}/"
                  f"{fj.get('morts_pct', 0):.0f} esp {fj.get('esperance_eur')})", flush=True)
        out[nom] = res
        sources[nom] = (jo, jours)
    ecrire_sortie("c1_jour_compte", out)
    combiner(sources, "c1_jour_combinaison")


def jour():
    jour_pleine_taille()
    jour_compte()


if __name__ == "__main__":
    {"couts": couts, "compte": compte, "combine": combine, "jour": jour}[sys.argv[1]]()
