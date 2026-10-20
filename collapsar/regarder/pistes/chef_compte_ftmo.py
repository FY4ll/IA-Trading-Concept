"""PISTE « chef_compte_ftmo » : un COMPTE FTMO 100 000 $ (Swing) qui applique la stratégie DU CHEF DE PROJET (V1) sur
toutes les cryptos à la fois — 16/10/2026.

CAHIER DES CHARGES ÉCRIT AVANT TOUT RÉSULTAT (rien n'est choisi après coup ; tout est figé ici).

Avertissement écrit d'avance : toutes les années 2017-2026 ont DÉJÀ été vues pour V1 (piste chef_crypto, groupes A et B,
confirmation ouverte une fois). Ce calcul est une ESTIMATION DE COMPTE (ce que donnerait sa méthode sur un vrai compte
FTMO avec une politique de risque figée), PAS une preuve d'avantage. Aucune période n'est cachée ici.

La stratégie (respectée, pas simplifiée)
- V1 « Gigogne H4 stop A plancher 0.2 » = sa version figée, EXACTEMENT celle de chef_crypto : zone zones supply and demand H4 vivante,
  contact du bord proche, descente H1 -> M30 -> M15, ordre limite au milieu de la plus petite zone (200 bougies au plus),
  stop derrière la zone ± 0,2 ATR de l'unité d'entrée avec un minimum de 0,2 x ATR journalier (dernier jour complet),
  objectifs 2 R / sommet H1 / zone opposée H4, 30 jours max. Code du laboratoire appelé tel quel (gigogne.preparer,
  gigogne.entrees, noyaux._remplissage) ; la sortie est une copie de chef_crypto.trade_tiers_heures qui rend en plus
  le prix et la nature de chaque sortie (contrôle : même R que chef_crypto à frais égaux).
- Gestion de sortie (A) PRINCIPALE = celle de V1 telle que testée : trois tiers (2 R, sommet H1, zone opposée), stop fixe.
- Gestion de sortie (B) EN INFORMATION = celle décrite par le chef de projet : 80 % de la position à 2 R (= 1er objectif
  de V1), 20 % jusqu'à la zone opposée (objectif 3 de V1) ; après le 1er objectif, le stop des 20 % passe au prix
  d'entrée (actif à partir de la bougie suivante : on ne sait pas l'ordre dans la bougie). Même entrée, même stop.

Marchés (liste fermée) : cryptos présentes À LA FOIS chez FTMO (research_notes/FTMO conditions crypto/notes.md, 32
cryptos) et dans data/binance : BTC, ETH, ADA, DOT, LTC, XRP, DOGE, XMR, BCH, BNB, SOL, AVAX, LINK, NEAR, ALGO, ETC,
XLM, UNI, VET (VECUSD = VeChain chez FTMO). 19 cryptos. Absentes chez FTMO : ATOM, EOS, FIL, MATIC/POL, TRX.
Données : bougies Binance 15 min (heure serveur = New York + 7 h), FILTRE COMMUN du LISEZMOI / coordinateur
(chef_crypto.charger_autre tel quel : 7 premiers jours ignorés, mèches fausses ramenées, krach du 10/10/2025 gardé).
XMR s'arrête le 20/02/2024 chez Binance (gardé jusque-là).

Frais (aller-retour, part du montant) = commission 0,065 % + écart 0,03 % (BTC écart 0,0015 %) = 0,095 % (BTC
0,0665 %) ; jusqu'au 16/10 (audit, défaut 5) : le tout x 1,25 de glissement non mesuré = 0,11875 % (BTC 0,083125 %),
réglage gardé : mains/frais_ftmo.MARGE_PRUDENCE (sur l'écart seulement). Convention de V1 : entrée limite = demi-frais, objectif ou fin des 30 jours = demi-frais,
stop = frais entiers (glissement). Sortie forcée par le compte (arrêt du jour, objectif du challenge atteint) = frais
entiers. NUIT : 30 %/an du montant d'entrée, / 360 par minuit serveur franchi (vendredi x 3, samedi et dimanche 0 :
7 nuits par semaine, comme chef_crypto), payée par chaque part encore ouverte.

Politique de risque FIGÉE (principale, « P1 ») :
- 0,25 % du solde par trade (taille = 0,25 % du solde / distance du stop en part du prix) ;
- levier crypto Swing 1:1 : la somme des montants ouverts ne dépasse pas les fonds du compte (une taille qui ne
  rentre pas est réduite à la marge libre ; plus de marge libre = trade ignoré) ;
- au plus 4 positions ouvertes (les suivantes ignorées), au plus 1 position par crypto ;
- arrêt de la journée (jour serveur = jour FTMO) si les pertes du jour (réalisées + latentes, soit fonds au plus bas de
  la bougie - solde au début du jour, comme FTMO) atteignent -2 % du capital de départ : tout est fermé au plus mauvais
  prix de la bougie, plus aucune entrée jusqu'au lendemain ;
- risque divisé par 2 (0,125 %) si les fonds sont à moins de 4 % du mur des -10 % (fonds < 94 % du capital de départ).
Variante d'INFORMATION (pas de choix) « P2 » : 0,5 % par trade, au plus 6 positions ; le reste identique.
Combinaisons calculées : A+P1 (PRINCIPALE), A+P2, B+P1, B+P2 (information seulement).

Mesures, par période (avant 2022, 2022-2023, 2024-2026) et au total
- Compte continu par période : départ 100 000 $ au début de la période, sans arrêt au mur (on note s'il est touché) :
  gain %/mois (composé), baisse max (fonds au plus bas dans la journée contre le plus haut atteint), pire jour (dans la
  journée, latent compris, contre le solde du début du jour), trades/mois pris, signaux ignorés.
- Challenges FTMO 2 étapes : départ tous les 10 jours (jour serveur) à 100 000 $ ; étape 1 +10 %, étape 2 +5 % (nouveau
  compte au jour suivant) ; mort si fonds au plus bas d'une bougie <= solde du début du jour - 5 000 $ ou <= 90 000 $ ;
  objectif = fonds (frais de sortie déduits) >= objectif avec au moins 4 jours de trading (jour où une position est
  ouverte) -> tout est fermé, étape réussie. Pas de limite de temps ; inachevé si les données finissent avant.
  Contre 20 JUMEAUX : mêmes signaux, mêmes moments, même politique, sens tiré à pile ou face trade par trade (le jumeau
  vit sa propre sortie : chemin inverse, stops et objectifs miroir) ; le compte du jumeau applique les mêmes règles.
- Compte financé (après l'étape 2, au jour suivant) : 12 mois (365 jours), mêmes règles de mort ; retrait tous les
  30 jours du gain au-dessus de 100 000 $ (le solde revient à 100 000 $ ; simplification : retrait possible même avec
  des positions ouvertes) ; à 12 mois, le gain restant (fonds - 100 000 $ si positif) compte comme dernier retrait.
  Survie 12 mois (%), gain mensuel moyen financé (= retraits bruts / 100 000 $ / 12).
- Espérance d'un challenge à 540 € : -540 € + si réussi [540 € remboursés au 1er retrait s'il y en a un + 80 % des
  retraits bruts sur 12 mois, convertis en € au dernier cours EURUSD des données]. Moyenne sur les départs dont l'issue
  est connue (mort, ou réussi avec 12 mois de financé dans les données) ; les autres sont comptés à part.
- En information : R moyen par trade aux frais FTMO (sans politique de compte), force contre le jumeau (moyenne de
  (R - R_inverse)/2 / écart type x racine(n)).

Simplifications assumées (écrites d'avance)
- Bougies de 15 min : pire prix de chaque bougie pris au même instant pour toutes les positions (prudent) ; sortie
  d'une part comptée au début de la bougie (de l'unité d'entrée) où elle a lieu ; la bougie d'entrée n'est pas suivie
  après le remplissage au-delà de ce que fait V1 (limite connue de chef_crypto).
- Fonds = solde + latent au prix (sans les frais de sortie futurs), comme l'affiche MetaTrader.
- Prix Binance (pas ceux de FTMO) ; les 22 « nouvelles » cryptos ne sont chez FTMO que depuis le 28/07/2025.

Depuis Test_IA : venv_gpu\\Scripts\\python.exe -u -m collapsar.regarder.pistes.chef_compte_ftmo trades|compte
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
from collapsar.regarder.pistes import chef_crypto as CC
from collapsar.regarder.smc import gigogne as G
from collapsar.regarder.smc import noyaux as K
from collapsar.regarder.smc.nono import TENUE_JOURS

VIE = dm.RACINE / "collapsar" / "vie" / "pistes" / "chef_compte_ftmo"
CACHE = VIE / "cache"
CRYPTOS = ["BTC", "ETH", "ADA", "DOT", "LTC", "XRP", "DOGE", "XMR", "BCH", "BNB", "SOL", "AVAX", "LINK", "NEAR", "ALGO",
           "ETC", "XLM", "UNI", "VET"]
from collapsar.mains.frais_ftmo import MARGE_PRUDENCE as GLISSEMENT        # 1,25 jusqu'au 16/10 (audit, défaut 5)

COMMISSION, ECART, ECART_BTC = 0.00065, 0.0003, 0.000015
NUIT_AN = 0.30
CAPITAL = 100_000.0
PRIX_CHALLENGE = 540.0
PART_TRADER = 0.80
T0 = pd.Timestamp("2017-08-01")                 # début de la grille (heure serveur, minuit)
PAS_NS = 15 * 60 * 10 ** 9
PAR_JOUR = 96
H7 = pd.Timedelta(hours=7)
POLITIQUES = {"P1": (0.0025, 4), "P2": (0.005, 6)}
GESTIONS = {"A": (np.array([1 / 3, 1 / 3, 1 / 3]), False), "B": (np.array([0.8, 0.2, 0.0]), True)}
PERIODES = {"avant 2022": ("2017-08-01", "2022-01-01"), "2022-2023": ("2022-01-01", "2024-01-01"),
            "2024-2026": ("2024-01-01", "2026-10-16"), "tout": ("2017-08-01", "2026-10-16")}
JUMEAUX = 20


def frais(c: str) -> float:
    """Commission (tarif fixe) + écart x marge de prudence (16/10 : avant, (commission + écart) x 1,25)."""
    return COMMISSION + (ECART_BTC if c == "BTC" else ECART) * GLISSEMENT


def pas_de(t_serveur_ns) -> np.ndarray:
    return (np.asarray(t_serveur_ns, np.int64) - T0.value) // PAS_NS


# ---------------------------------------------------------------- une sortie (copie de chef_crypto.trade_tiers_heures)
@njit(cache=True)
def trade_parts(o, h, l, c, bt, duree, mt, mo, mh, ml, i, f_min, b_min, sens, entree, risque, cibles, poids, nul, tenue):
    """Même parcours que chef_crypto.trade_tiers_heures (stop vérifié d'abord, puis les objectifs), avec des parts de
    poids quelconques et, si `nul`, le stop du reste ramené au prix d'entrée après le 1er objectif (bougie suivante).
    Rend pour chaque part : heure de sortie (ns, New York), prix, nature (0 objectif, 1 stop, 2 fin des 30 jours)."""
    n = len(c)
    stop = entree - sens * risque
    ouvert = poids > 0
    t_s = np.zeros(3, np.int64)
    p_s = np.zeros(3)
    k_s = np.zeros(3, np.int64)
    for q in range(3):
        if not ouvert[q]:
            t_s[q] = mt[f_min]
            p_s[q] = entree
    reste = max(b_min - f_min - 1, 0)
    for s in range(reste + tenue + 1):
        if s < reste:
            k = f_min + 1 + s
            po, ph, pl = mo[k], mh[k], ml[k]
            tq = mt[k]
        elif s == reste:
            po, ph, pl = np.nan, -np.inf, np.inf
            tq = bt[i]
        else:
            ib = i + (s - reste)
            if ib >= n:
                break
            po, ph, pl = o[ib], h[ib], l[ib]
            tq = bt[ib]
        if (sens > 0 and pl <= stop) or (sens < 0 and ph >= stop):
            px = stop if np.isnan(po) else (min(stop, po) if sens > 0 else max(stop, po))
            for q in range(3):
                if ouvert[q]:
                    ouvert[q] = False
                    t_s[q], p_s[q], k_s[q] = tq, px, 1
            return t_s, p_s, k_s
        premier = False
        for q in range(3):
            if ouvert[q] and ((sens > 0 and ph >= cibles[q]) or (sens < 0 and pl <= cibles[q])):
                px = cibles[q] if np.isnan(po) else (max(cibles[q], po) if sens > 0 else min(cibles[q], po))
                ouvert[q] = False
                t_s[q], p_s[q], k_s[q] = tq, px, 0
                if q == 0:
                    premier = True
        if not (ouvert[0] or ouvert[1] or ouvert[2]):
            return t_s, p_s, k_s
        if nul and premier:
            stop = entree
    fin = min(n - 1, i + tenue)
    for q in range(3):
        if ouvert[q]:
            t_s[q], p_s[q], k_s[q] = bt[fin] + duree, c[fin], 2
    return t_s, p_s, k_s


def R_trade(e, risque, sens, fr, fill_ny, t_s, p_s, k_s, poids) -> float:
    """R après frais et nuits d'une sortie (même convention que chef_crypto)."""
    gain = float(np.sum(poids * (p_s - e) * sens))
    cout = e * fr * 0.5 + float(np.sum(poids * e * fr * np.where(k_s == 1, 1.0, 0.5)))
    nb = CC.nuits(np.full(3, fill_ny), t_s)
    nuit = float(np.sum(poids * nb * NUIT_AN / 360.0 * e))
    return (gain - cout - nuit) / risque


def trades_crypto(c: str) -> tuple[pd.DataFrame, dict]:
    """Les trades V1 d'une crypto (sortie A et B, sens et jumeau inverse) + ses bougies 15 min sur la grille."""
    ft, fg = CACHE / f"{c}_trades.pkl", CACHE / f"{c}_grille.npz"
    if ft.exists() and fg.exists():
        z = np.load(fg)
        return pd.read_pickle(ft), {k: z[k] for k in z.files}
    nom = c + "USDT"
    d = CC.charger_autre(nom)
    grille = {"pas": pas_de(d["time"].to_numpy().astype("datetime64[ns]").astype(np.int64)).astype(np.int64),
              "l": d["low"].to_numpy(float), "h": d["high"].to_numpy(float), "c": d["close"].to_numpy(float)}
    fr = frais(c)
    P = G.preparer(CC.construire(nom, CC.en_ny(d), fr), G.ECHELLE_45)
    B, Z = P["B"], P["Z"]
    s_px, s_ty, s_t = P["sommets"]
    BD = B["D1"]
    xh, xb, xm, xs, xconf, xfin = Z["H4"]
    lignes = []
    for e in G.entrees(P, "H4"):
        BY, i, d_, entree = B[e["unite"]], e["i"], e["sens"], e["entree"]
        t_e = BY.bt[i]
        jd = int(np.searchsorted(BD.bt, t_e, "right")) - 2
        atr_jour = BD.atr[jd] if jd >= 0 else np.nan
        risque = max(e["risque_zone"], CC.PLANCHER * atr_jour)
        if not np.isfinite(risque):
            continue
        okx = (xs == -d_) & (xconf < t_e) & (xfin > t_e)
        bords = (xb if d_ > 0 else xh)[okx]
        dist3 = (bords - entree) * d_
        dist3 = dist3[dist3 >= 2 * risque]
        if not len(dist3):
            continue
        d3 = float(dist3.min())
        cand = (s_ty == d_) & (s_t <= t_e)
        d2s = (s_px[cand] - entree) * d_
        d2s = d2s[(d2s > 2 * risque) & (d2s < d3)]
        d2 = float(d2s.min()) if len(d2s) else (2 * risque + d3) / 2
        f_min, b_min = K._remplissage(BY.o, BY.mt, BY.ml, BY.mh, BY.bt, BY.duree, i, d_, e["milieu"])
        tenue = int(TENUE_JOURS * 86400e9 // BY.duree)
        args = (BY.o, BY.h, BY.l, BY.c, BY.bt, BY.duree, BY.mt, BY.mo, BY.mh, BY.ml, i, f_min, b_min)
        fill_ny = int(BY.mt[f_min])
        ligne = {"crypto": c, "unite": e["unite"], "entree": pd.Timestamp(BY.t[i]), "fill_ny": fill_ny, "sens": d_,
                 "prix": entree, "risque": risque, "stop_frac": risque / entree, "frais": fr, "tp3_R": d3 / risque}
        # contrôle : la sortie de chef_crypto à l'identique
        r_ref, _, so = CC.trade_tiers_heures(*args, d_, entree, risque, d2, d3, tenue, BY.frais, BY.facteur[i])
        ligne["R_ref_sans_nuit"] = float(r_ref)
        ligne["nuit_ref"] = CC._nuit_R(fill_ny, so, entree, risque)[0]
        for gest, (poids, nul) in GESTIONS.items():
            for jum, s in (("", d_), ("_inv", -d_)):
                cibles = np.array([entree + s * 2.0 * risque,
                                   entree + s * (d3 if gest == "B" else d2), entree + s * d3])
                t_s, p_s, k_s = trade_parts(*args, s, entree, risque, cibles, poids, nul, tenue)
                ligne[f"{gest}{jum}_t"] = t_s.copy()
                ligne[f"{gest}{jum}_p"] = p_s.copy()
                ligne[f"{gest}{jum}_k"] = k_s.copy()
                ligne[f"R_{gest}{jum}"] = R_trade(entree, risque, s, fr, fill_ny, t_s, p_s, k_s, poids)
        lignes.append(ligne)
    t = pd.DataFrame(lignes)
    CACHE.mkdir(parents=True, exist_ok=True)
    t.to_pickle(ft)
    np.savez(fg, **grille)
    del P, B, Z, d
    return t, grille


# ---------------------------------------------------------------- le compte (bougie de 15 min par bougie de 15 min)
@njit(cache=True)
def simuler(L, H, C, poids_nuit, fill, cr, sens, e, sf, fr, xs, xp, xk, w, signes, risque0, maxpos, stop_jour,
            debut, fin, mode, jour_out):
    """mode 0 = compte continu de `debut` à `fin` (rien n'arrête, jour_out[jour] = (solde début, fonds fin, pire du jour
    contre le début, trades ouverts)) ; mode 1 = challenge 2 étapes puis financé 12 mois.
    Rend : res[0..] = (issue, pas_fin, baisse_max, trades, ign_pos, ign_crypto, ign_marge, ign_arret, finance_mort,
    retraits_bruts, nb_retraits, finance_complet, jours_mur, jours_5pct, arrets_jour, jour_etape1, jour_etape2)."""
    n = len(fill)
    nmax = 8
    p_tid = np.full(nmax, -1, np.int64)
    p_qty = np.zeros(nmax)
    p_ouv = np.zeros((nmax, 3), np.bool_)
    cap = 100000.0
    solde = cap
    ref_jour = cap
    arret = False
    phase = 1 if mode == 1 else 0
    cible = 0.10
    jours_trade = 0
    dernier_jour_trade = -1
    pic = cap
    baisse = 0.0
    nb_tr = 0
    ign = np.zeros(4, np.int64)
    fin_mort = 0
    retraits = 0.0
    nb_retraits = 0
    complet = 0
    debut_fin = -1
    jours_mur = 0
    jours_5 = 0
    arrets = 0
    jour_reussite = np.full(2, -1.0)
    mur_jour = False
    cinq_jour = False
    issue = 3                                                   # 0 réussi, 1 mort étape 1, 2 mort étape 2, 3 inachevé
    ptr = np.searchsorted(fill, debut)
    k = debut
    jour_courant = -1
    while k < fin:
        jour = k // 96
        if jour != jour_courant:
            if jour_courant >= 0 and mode == 0:
                if mur_jour:
                    jours_mur += 1
                if cinq_jour:
                    jours_5 += 1
            mur_jour = False
            cinq_jour = False
            # nuits
            pn = poids_nuit[jour] if jour_courant >= 0 else 0.0
            for p in range(nmax):
                if p_tid[p] >= 0:
                    t = p_tid[p]
                    for q in range(3):
                        if p_ouv[p, q]:
                            solde -= p_qty[p] * w[q] * e[t] * 0.30 / 360.0 * pn
            # financé : retraits tous les 30 jours, fin à 365 jours
            if phase == 3:
                dj = jour - debut_fin
                if dj >= 365:
                    eq = solde
                    for p in range(nmax):
                        if p_tid[p] >= 0:
                            t = p_tid[p]
                            g = 0 if signes[t] > 0 else 1
                            se = sens[t] * signes[t]
                            for q in range(3):
                                if p_ouv[p, q]:
                                    eq += p_qty[p] * w[q] * ((C[cr[t], k] - e[t]) * se - e[t] * fr[t])
                    if eq > cap:
                        retraits += eq - cap
                        nb_retraits += 1
                    complet = 1
                    issue = 0
                    break
                if dj > 0 and dj % 30 == 0 and solde > cap:
                    retraits += solde - cap
                    nb_retraits += 1
                    solde = cap
            ref_jour = solde
            arret = False
            jour_courant = jour
            if mode == 0:
                jour_out[jour, 0] = solde
                jour_out[jour, 2] = 0.0
        # sorties prévues
        nouv = 0
        for p in range(nmax):
            if p_tid[p] >= 0:
                t = p_tid[p]
                g = 0 if signes[t] > 0 else 1
                se = sens[t] * signes[t]
                reste = False
                for q in range(3):
                    if p_ouv[p, q]:
                        if xs[t, g, q] <= k:
                            cf = 1.0 if xk[t, g, q] == 1 else 0.5
                            solde += p_qty[p] * w[q] * ((xp[t, g, q] - e[t]) * se - e[t] * fr[t] * cf)
                            p_ouv[p, q] = False
                        else:
                            reste = True
                if not reste:
                    p_tid[p] = -1
        # fonds avant entrées (pour la taille et la marge)
        eq = solde
        expo = 0.0
        nouv_ouv = 0
        for p in range(nmax):
            if p_tid[p] >= 0:
                t = p_tid[p]
                se = sens[t] * signes[t]
                nouv_ouv += 1
                part = 0.0
                for q in range(3):
                    if p_ouv[p, q]:
                        eq += p_qty[p] * w[q] * (C[cr[t], k] - e[t]) * se
                        part += w[q]
                expo += p_qty[p] * part * e[t]
        # entrées
        while ptr < n and fill[ptr] < k:
            ptr += 1
        while ptr < n and fill[ptr] == k:
            t = ptr
            ptr += 1
            if arret:
                ign[3] += 1
                continue
            if nouv_ouv >= maxpos:
                ign[0] += 1
                continue
            deja = False
            for p in range(nmax):
                if p_tid[p] >= 0 and cr[p_tid[p]] == cr[t]:
                    deja = True
            if deja:
                ign[1] += 1
                continue
            r = risque0 * (0.5 if eq < cap * 0.94 else 1.0)
            montant = r * solde / sf[t]
            libre = eq - expo
            if montant > libre:
                montant = libre
            if montant <= 0.0:
                ign[2] += 1
                continue
            for p in range(nmax):
                if p_tid[p] < 0:
                    p_tid[p] = t
                    p_qty[p] = montant / e[t]
                    for q in range(3):
                        p_ouv[p, q] = w[q] > 0
                    break
            solde -= montant * fr[t] * 0.5
            eq -= montant * fr[t] * 0.5
            expo += montant
            nouv_ouv += 1
            nb_tr += 1
            if mode == 0:
                jour_out[jour, 3] += 1
            if jour != dernier_jour_trade:
                jours_trade += 1
                dernier_jour_trade = jour
        # marquage au pire prix de la bougie
        pire = solde
        eqc = solde
        cout_sortie = 0.0
        for p in range(nmax):
            if p_tid[p] >= 0:
                t = p_tid[p]
                se = sens[t] * signes[t]
                c_ = cr[t]
                px_w = L[c_, k] if se > 0 else H[c_, k]
                for q in range(3):
                    if p_ouv[p, q]:
                        pire += p_qty[p] * w[q] * (px_w - e[t]) * se
                        eqc += p_qty[p] * w[q] * (C[c_, k] - e[t]) * se
                        cout_sortie += p_qty[p] * w[q] * e[t] * fr[t]
        if pire < pic:
            b = (pire - pic) / pic
            if b < baisse:
                baisse = b
        if eqc > pic:
            pic = eqc
        if mode == 0:
            if pire - ref_jour < jour_out[jour, 2]:
                jour_out[jour, 2] = pire - ref_jour
            if pire <= 0.90 * cap:
                mur_jour = True
            if pire - ref_jour <= -0.05 * cap:
                cinq_jour = True
        else:
            if pire - ref_jour <= -0.05 * cap or pire <= 0.90 * cap:
                if phase == 1:
                    issue = 1
                elif phase == 2:
                    issue = 2
                else:
                    issue = 0
                    fin_mort = 1
                break
        # arrêt du jour à -2 %
        if pire - ref_jour <= -stop_jour * cap and not arret:
            arret = True
            arrets += 1
            for p in range(nmax):
                if p_tid[p] >= 0:
                    t = p_tid[p]
                    se = sens[t] * signes[t]
                    px_w = L[cr[t], k] if se > 0 else H[cr[t], k]
                    for q in range(3):
                        if p_ouv[p, q]:
                            solde += p_qty[p] * w[q] * ((px_w - e[t]) * se - e[t] * fr[t])
                            p_ouv[p, q] = False
                    p_tid[p] = -1
            eqc = solde
            cout_sortie = 0.0
        # objectif du challenge
        if (phase == 1 or phase == 2) and jours_trade >= 4 and eqc - cout_sortie >= cap * (1.0 + cible):
            jour_reussite[phase - 1] = jour
            phase += 1
            for p in range(nmax):
                p_tid[p] = -1
            solde = cap
            pic = cap
            jours_trade = 0
            dernier_jour_trade = -1
            cible = 0.05
            k = (jour + 1) * 96                                 # nouveau compte le jour suivant
            if phase == 3:
                debut_fin = jour + 1
            jour_courant = -1
            continue
        if mode == 0:
            jour_out[jour, 1] = eqc
        # saut quand rien n'est ouvert
        ouvert = False
        for p in range(nmax):
            if p_tid[p] >= 0:
                ouvert = True
        if not ouvert:
            prochain = (jour + 1) * 96
            if ptr < n and fill[ptr] < prochain:
                prochain = fill[ptr]
            if prochain <= k:
                prochain = k + 1
            if mode == 0:
                jour_out[jour, 1] = solde
            k = prochain
        else:
            k += 1
    if issue == 3 and phase == 3:
        issue = 0                                               # réussi, financé coupé par la fin des données
    if mode == 0 and jour_courant >= 0:
        if mur_jour:
            jours_mur += 1
        if cinq_jour:
            jours_5 += 1
    res = np.zeros(17)
    res[15], res[16] = jour_reussite[0], jour_reussite[1]
    res[0], res[1], res[2], res[3] = issue, k, baisse, nb_tr
    res[4], res[5], res[6], res[7] = ign[0], ign[1], ign[2], ign[3]
    res[8], res[9], res[10], res[11] = fin_mort, retraits, nb_retraits, complet
    res[12], res[13], res[14] = jours_mur, jours_5, arrets
    return res


# ---------------------------------------------------------------- assemblage
def tout_charger():
    parts, grilles = [], {}
    for c in CRYPTOS:
        t, g = trades_crypto(c)
        print(f"  {c}: {len(t)} trades V1", flush=True)
        parts.append(t)
        grilles[c] = g
    t = pd.concat(parts, ignore_index=True)
    t["fill_pas"] = pas_de(t["fill_ny"].to_numpy() + H7.value)
    t = t[t["fill_pas"] >= 0].sort_values(["fill_pas", "crypto"]).reset_index(drop=True)
    npas = int(max(g["pas"].max() for g in grilles.values())) + 2
    nc = len(CRYPTOS)
    L, Hh, Cc = (np.full((nc, npas), np.nan) for _ in range(3))
    for j, c in enumerate(CRYPTOS):
        g = grilles[c]
        ok = g["pas"] >= 0
        L[j, g["pas"][ok]], Hh[j, g["pas"][ok]], Cc[j, g["pas"][ok]] = g["l"][ok], g["h"][ok], g["c"][ok]
        Cc[j] = pd.Series(Cc[j]).ffill().to_numpy()
        manque = ~np.isfinite(L[j])
        L[j, manque], Hh[j, manque] = Cc[j, manque], Cc[j, manque]
    jours = np.arange(npas // 96 + 2)
    veille = (pd.Timestamp(T0) + pd.to_timedelta(jours - 1, unit="D")).dayofweek.to_numpy()
    poids_nuit = np.where(veille <= 3, 1.0, np.where(veille == 4, 3.0, 0.0))
    return t, (np.nan_to_num(L), np.nan_to_num(Hh), np.nan_to_num(Cc)), poids_nuit, npas


def tableaux_sortie(t: pd.DataFrame, gest: str):
    xs =np.stack([np.stack(t[f"{gest}_t"].to_numpy()), np.stack(t[f"{gest}_inv_t"].to_numpy())], axis=1)
    xp = np.stack([np.stack(t[f"{gest}_p"].to_numpy()), np.stack(t[f"{gest}_inv_p"].to_numpy())], axis=1)
    xk = np.stack([np.stack(t[f"{gest}_k"].to_numpy()), np.stack(t[f"{gest}_inv_k"].to_numpy())], axis=1)
    xs = pas_de(xs + H7.value)
    fp = t["fill_pas"].to_numpy()[:, None, None]
    xs = np.maximum(xs, fp + 1).astype(np.int64)
    return xs, xp.astype(float), xk.astype(np.int64)


def pas_date(s) -> int:
    return int((pd.Timestamp(s) - T0).value // PAS_NS)


def note_trades(t: pd.DataFrame, gest: str) -> dict:
    out = {}
    for p, (de, a) in PERIODES.items():
        g = t[(t["entree"] + H7 >= de) & (t["entree"] + H7 < a)]
        if len(g) < 10:
            out[p] = {"trades": len(g)}
            continue
        r, ri = g[f"R_{gest}"].to_numpy(), g[f"R_{gest}_inv"].to_numpy()
        dd = (r - ri) / 2
        out[p] = {"trades": int(len(g)), "R_moyen": float(r.mean()), "R_median": float(np.median(r)),
                  "gagnants_pct": float((r > 0).mean() * 100),
                  "force": float(dd.mean() / dd.std(ddof=1) * math.sqrt(len(g)))}
    return out


def compte():
    VIE.mkdir(parents=True, exist_ok=True)
    t, (L, Hh, Cc), poids_nuit, npas = tout_charger()
    eurusd = float(dm.charger("EURUSD", pd.Timestamp("2100-01-01"))["close"].iloc[-1])
    print(f"{len(t)} trades V1 au total, EURUSD {eurusd:.4f}", flush=True)
    # contrôle de fidélité : sortie A = chef_crypto
    ctrl_R = t["R_ref_sans_nuit"] - t["nuit_ref"]
    ecart = float(np.abs(ctrl_R - t["R_A"]).max())
    print(f"contrôle sortie A contre chef_crypto : écart max {ecart:.2e} R", flush=True)
    t.drop(columns=[c for c in t.columns if c.endswith(("_t", "_p", "_k"))]).to_csv(VIE / "trades_v1.csv", index=False)
    fill = t["fill_pas"].to_numpy().astype(np.int64)
    cr = t["crypto"].map({c: j for j, c in enumerate(CRYPTOS)}).to_numpy().astype(np.int64)
    sens = t["sens"].to_numpy().astype(np.int64)
    e = t["prix"].to_numpy(float)
    sf = t["stop_frac"].to_numpy(float)
    fr = t["frais"].to_numpy(float)
    rng = np.random.default_rng(7)
    signes_j = [rng.choice(np.array([-1, 1], np.int64), len(t)) for _ in range(JUMEAUX)]
    vrai = np.ones(len(t), np.int64)
    premier_jour = int(fill.min() // 96)
    sortie = {"quand": datetime.now().isoformat(timespec="seconds"), "trades_v1": int(len(t)), "eurusd": eurusd,
              "controle_ecart_R": ecart, "cryptos": CRYPTOS,
              "trades_par_crypto": t["crypto"].value_counts().to_dict(), "combinaisons": {}}
    for gest in GESTIONS:
        w = GESTIONS[gest][0]
        xs, xp, xk = tableaux_sortie(t, gest)
        sortie[f"trades_{gest}"] = note_trades(t, gest)
        for pol, (r0, mp) in POLITIQUES.items():
            nom = f"{gest}+{pol}"
            print(f"===== {nom}", flush=True)
            res = {"comptes": {}, "challenges": {}}

            def run(signes, de, a, mode, jo):
                return simuler(L, Hh, Cc, poids_nuit, fill, cr, sens, e, sf, fr, xs, xp, xk, w, signes, r0, mp, 0.02,
                               de, a, mode, jo)
            # 1) comptes continus par période
            for p, (de, a) in PERIODES.items():
                d0, d1 = pas_date(de), min(pas_date(a), npas - 1)
                jo = np.zeros((npas // 96 + 2, 4))
                r = run(vrai, d0, d1, 0, jo)
                j0, j1 = d0 // 96, d1 // 96
                jj = jo[j0:j1]
                jj = jj[jj[:, 0] > 0] if (jj[:, 0] > 0).any() else jj
                fin_eq = float(jj[-1, 1]) if len(jj) else CAPITAL
                mois = (j1 - j0) / 30.44
                pire_j = float(np.min(jj[:, 2] / np.maximum(jj[:, 0], 1))) if len(jj) else 0.0
                res["comptes"][p] = {
                    "mois": mois, "fonds_fin": fin_eq,
                    "gain_pct_mois": float(((fin_eq / CAPITAL) ** (1 / mois) - 1) * 100),
                    "gain_simple_pct_mois": float((fin_eq / CAPITAL - 1) / mois * 100),
                    "baisse_max_pct": float(r[2] * 100), "pire_jour_pct": pire_j * 100,
                    "trades": int(r[3]), "trades_mois": float(r[3] / mois),
                    "ignores_positions": int(r[4]), "ignores_meme_crypto": int(r[5]), "ignores_marge": int(r[6]),
                    "ignores_arret_jour": int(r[7]), "arrets_du_jour": int(r[14]),
                    "jours_sous_mur_10pct": int(r[12]), "jours_perte_5pct": int(r[13])}
                x = res["comptes"][p]
                print(f"{nom} | {p:11s} | {x['gain_pct_mois']:+.2f} %/mois | baisse {x['baisse_max_pct']:.1f} % | pire j "
                      f"{x['pire_jour_pct']:.2f} % | {x['trades_mois']:.1f} tr/mois | ign pos {x['ignores_positions']} "
                      f"crypto {x['ignores_meme_crypto']} marge {x['ignores_marge']} arrêt {x['ignores_arret_jour']} | "
                      f"jours -5 % {x['jours_perte_5pct']} mur {x['jours_sous_mur_10pct']}", flush=True)
            # 2) challenges tous les 10 jours (vrai + 20 jumeaux)
            departs = np.arange(premier_jour, (npas - 1) // 96, 10) * 96
            jo0 = np.zeros((1, 4))

            def serie(signes):
                return np.array([run(signes, int(d), npas - 1, 1, jo0) for d in departs])
            vraie = serie(vrai)
            jum = [serie(s) for s in signes_j]
            dates = [T0 + pd.Timedelta(int(d) * PAS_NS) for d in departs]
            np.save(CACHE / f"challenges_{nom}.npy", np.stack([vraie] + jum))
            for p, (de, a) in PERIODES.items():
                m = np.array([(pd.Timestamp(de) <= x < pd.Timestamp(a)) for x in dates])
                res["challenges"][p] = {"vrai": bilan_challenges(vraie[m], departs[m], npas, eurusd),
                                        "jumeaux": moyenne([bilan_challenges(j[m], departs[m], npas, eurusd)
                                                            for j in jum])}
                v, jm = res["challenges"][p]["vrai"], res["challenges"][p]["jumeaux"]
                print(f"{nom} | {p:11s} | chall {v['departs']} : réussis {v['reussis_pct']:.0f} % morts "
                      f"{v['morts_pct']:.0f} % inach {v['inacheves_pct']:.0f} % (jum {jm['reussis_pct']:.0f}/"
                      f"{jm['morts_pct']:.0f}) | en 12 mois {v['reussis_en_12_mois_pct']:.0f} % (jum "
                      f"{jm['reussis_en_12_mois_pct']:.0f}) | médiane {v['mois_reussite_median']} mois, mort "
                      f"{v['mois_mort_median']} mois | financé survie {v['finance_survie_pct']} % gain/mois "
                      f"{v['finance_gain_pct_mois']} | espérance {v['esperance_eur']} € (jum {jm['esperance_eur']}) | "
                      f"abandon 12 mois {v['esperance_abandon_12mois_eur']} € (jum {jm['esperance_abandon_12mois_eur']})",
                      flush=True)
            sortie["combinaisons"][nom] = res
            _ecrire(VIE / "resultats.json", sortie)
    _ecrire(VIE / "resultats.json", sortie)


def bilan_challenges(r: np.ndarray, departs: np.ndarray, npas: int, eurusd: float) -> dict:
    n = len(r)
    if n == 0:
        return {"departs": 0}
    issue = r[:, 0]
    reussi = issue == 0
    mort = (issue == 1) | (issue == 2)
    inach = issue == 3
    complet = reussi & (r[:, 11] == 1) | reussi & (r[:, 8] == 1)      # financé connu sur 12 mois (ou mort avant)
    connu = mort | complet
    gains = r[:, 9]
    valeur = np.where(complet, -PRIX_CHALLENGE + np.where(r[:, 10] > 0, PRIX_CHALLENGE, 0.0)
                      + PART_TRADER * gains / eurusd, -PRIX_CHALLENGE)
    out = {"departs": int(n), "reussis_pct": float(reussi.mean() * 100), "morts_pct": float(mort.mean() * 100),
           "morts_etape1_pct": float((issue == 1).mean() * 100), "morts_etape2_pct": float((issue == 2).mean() * 100),
           "inacheves_pct": float(inach.mean() * 100), "reussis_finance_connu": int(complet.sum()),
           "issue_connue": int(connu.sum())}
    j0 = departs / 96
    duree = (r[:, 16] - j0) / 30.44                                     # mois jusqu'à la fin de l'étape 2
    duree_mort = (r[:, 1] / 96 - j0) / 30.44
    out["reussis_en_12_mois_pct"] = float((reussi & (duree <= 12)).mean() * 100)
    out["mois_reussite_median"] = round(float(np.median(duree[reussi])), 1) if reussi.sum() else None
    out["mois_etape1_median"] = round(float(np.median((r[r[:, 15] >= 0, 15] - j0[r[:, 15] >= 0]) / 30.44)), 1) \
        if (r[:, 15] >= 0).sum() else None
    out["mois_mort_median"] = round(float(np.median(duree_mort[mort])), 1) if mort.sum() else None
    # ajouté APRÈS avoir vu le grand nombre d'inachevés (lecture, pas un choix) : un challenge non réussi en 12 mois est
    # abandonné (540 € perdus) ; départs ayant au moins 12 mois de données devant eux
    vite = reussi & (duree <= 12)
    assez = j0 <= npas / 96 - 365
    garde = assez & (~vite | complet)
    v12 = np.where(vite, valeur, -PRIX_CHALLENGE)
    out["esperance_abandon_12mois_eur"] = round(float(v12[garde].mean()), 0) if garde.sum() else None
    out["departs_abandon_12mois"] = int(garde.sum())
    if complet.sum():
        out["finance_survie_pct"] = round(float((r[complet, 8] == 0).mean() * 100), 1)
        out["finance_gain_pct_mois"] = round(float((gains[complet] / CAPITAL / 12 * 100).mean()), 2)
        out["finance_gain_trader_eur_12mois"] = round(float((PART_TRADER * gains[complet] / eurusd).mean()), 0)
    else:
        out["finance_survie_pct"] = None
        out["finance_gain_pct_mois"] = None
    out["esperance_eur"] = round(float(valeur[connu].mean()), 0) if connu.sum() else None
    return out


def moyenne(lst: list[dict]) -> dict:
    out = {}
    for k in lst[0]:
        v = [x[k] for x in lst if x.get(k) is not None]
        out[k] = round(float(np.mean(v)), 2) if v else None
    return out


def _ecrire(f, obj):
    f.write_text(json.dumps(obj, ensure_ascii=False, indent=1, default=str), encoding="utf-8")


def trades():
    tout_charger()


if __name__ == "__main__":
    {"trades": trades, "compte": compte}[sys.argv[1] if len(sys.argv) > 1 else "compte"]()
