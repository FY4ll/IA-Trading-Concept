"""PISTE « trois_briques » : UN compte FTMO Swing 100 000 $ qui fait tourner ENSEMBLE, sur une même grille de 15 min,
la cassure 24 h C2 (BTC + ETH), les zones du chef V1 (19 cryptos) et C1 « contre la foule » (17 cryptos) — 16/10/2026.

CAHIER DES CHARGES ÉCRIT AVANT TOUT RÉSULTAT (une seule configuration, rien n'est choisi après coup ; tout est publié).

AVERTISSEMENT ÉCRIT D'AVANCE : toutes les années utilisées ici (2017-2026) ont DÉJÀ été vues pour les trois briques
(cassure : bitcoin_journee, cassure_crypto, cassure_v3, compte_combine ; chef : chef_crypto, chef_compte_ftmo,
compte_combine ; C1 : crypto_flux développement / contrôle / groupe B, crypto_flux_compte). Ce calcul est une ESTIMATION
de ce que donnerait un compte qui fait tourner les trois ensemble, PAS une preuve. Aucune période cachée. Seul le direct
jugera.

Les trois briques (règles reprises telles quelles, pas re-choisies)
- Brique « cassure » = C2 telle qu'en démo (moteur collapsar/strategies/cassure.py : N = (24,), lundi -> vendredi, sortie
  au milieu du canal, sortie forcée 23h45 serveur donc aucune nuit, arrêt propre de la brique à -3 % dans la journée).
  Prix Dukascopy BTCUSD et ETHUSD. Taille : montant = min(1, c / agitation 14 j) x solde.
- Brique « zones » = V1 du chef « Gigogne H4 stop A plancher 0.2 », gestion A par tiers (2 R / sommet H1 / zone
  opposée), 19 cryptos, prix Binance filtrés ; trades et sorties repris TELS QUELS du cache de chef_compte_ftmo (même
  code). Taille : montant = r x solde / distance du stop ; au plus 4 positions de la brique, 1 par crypto.
- Brique « C1 » = version « compte financé » de crypto_flux_compte (point 2) : 17 cryptos (BTC, ETH, SOL, XRP, ADA,
  DOGE, LTC, BNB, LINK, AVAX, DOT, BCH, XLM, UNI, ETC, NEAR, ALGO), signal C1 de crypto_flux.signaux (part des comptes
  acheteurs Binance au centile 95 de 90 jours -> vente, centile 5 -> achat), décision à chaque fin d'heure UTC (tableaux
  du cache crypto_flux/cache/compte15_tableaux.npz, rien recalculé), entrée au prix de clôture de la bougie de 15 min qui
  finit à cette heure ; stop à 1,5 x l'agitation journalière (agitation horaire des 14 jours passés x racine(24)) vérifié
  à chaque bougie de 15 min, exécuté au prix du stop (frais entiers) ; sinon sortie 24 h après (clôture). Au plus 5
  positions de la brique, au plus 3 dans le même sens, 1 par crypto ; un signal sur une crypto déjà tenue par C1 est
  ignoré. Taille : montant = min(1, r1 / (1,5 x agitation journalière)) x solde. Son arrêt propre à -2 % (règle de son
  compte seul) est REMPLACÉ par l'arrêt global du compte ci-dessous. Prix : Binance comptant (mêmes bougies filtrées que
  les zones). C1 n'existe que depuis 10/2020 (BTC) et 01-02/2022 (les 16 autres) : avant, sa part du risque reste vide.

Grille et prix
- Une seule grille de 15 min à l'heure du serveur (New York + 7 h) depuis le 01/08/2017 (celle de chef_compte_ftmo) ;
  chaque quart d'heure : sorties prévues (stops, objectifs, fins), puis entrées, puis marquage de TOUTES les positions au
  plus mauvais prix de la bougie (plus bas pour un achat, plus haut pour une vente, pris au même instant : prudent),
  puis règles de sécurité et de challenge. Les pires points des briques s'additionnent.
- Un signal C1 décidé à la fin d'heure UTC h entre à la bougie serveur qui commence à h (prix = clôture de la bougie
  précédente, contrôle d'égalité avec le prix de crypto_flux publié). Stop touché dans une bougie : sortie au prix du stop
  au début de cette bougie (même convention que les zones), au plus tôt la bougie qui suit l'entrée.

Frais réels FTMO (part du montant, aller-retour) = commission 0,0325 % par côté + écart (compte_combine.frais_rt) ; écart
BTC 0,0015 %, ETH 0,025 %, autres 0,03 % -> BTC 0,0665 %, ETH 0,09 %, autres 0,095 % (les trois briques ; jusqu'au
16/10, audit défaut 5 : x 1,25 sur le tout -> 0,083125 / 0,1125 / 0,11875 %). Moitié à l'entrée,
moitié à la sortie normale ; frais entiers à une sortie par stop ou par arrêt de sécurité. Nuits : 30 %/an du montant
d'entrée / 360 par minuit serveur franchi (vendredi x 3, samedi et dimanche 0), pour chaque part ouverte (zones et C1 ;
la cassure ne dort jamais). Levier crypto Swing 1:1 : la somme des montants ouverts ne dépasse pas les fonds ; une taille
qui ne rentre pas est réduite à la marge libre.

Budget de risque (FIGÉ avant)
- Agitation visée du compte : 9 %/an (niveau fixé avant). UN TIERS du risque à chaque brique : chaque brique vise
  9 % / racine(3) = 5,196 %/an (si les briques sont indépendantes, le compte vise 9 %).
- Calage une seule fois, sur l'AGITATION (écart type des variations journalières du compte, jours calendaires, x
  racine(365)) et jamais sur le gain, chaque brique seule à une taille de référence, sans règles de sécurité :
  cassure c = 0,5 % et zones r = 0,25 % sur 2017-08 -> 2021-12 (comme compte_combine) ; C1 r1 = 0,15 % sur
  2022-03-01 -> 2023-03-01 (sa première année avec les 17 cryptos ; avant, seul BTC existe : calage impossible sans
  fausser la taille). Ce calage de C1 regarde l'agitation d'une année de la période 2022-2023 (déjà vue de toute façon).
  Taille de la brique = référence x 5,196 % / agitation mesurée ; tailles FIXES pour toutes les périodes.
- Règles de sécurité du compte (toujours actives) :
  (1) arrêt global du jour : fonds au plus mauvais prix de la bougie - solde du début du jour serveur <= -2,5 % du
      capital de départ -> tout est fermé à ce prix (frais entiers), plus aucune entrée ce jour ;
  (2) risque divisé par 2 pour chaque nouvelle position si les fonds (prix de la bougie précédente) sont à moins de 4 %
      du mur des -10 % (fonds < 94 000 $) ;
  (3) au plus 8 positions ouvertes au total (premier arrivé, premier servi ; même quart d'heure : zones, puis cassure,
      puis C1, dans l'ordre des cryptos) ;
  (4) l'arrêt propre de la cassure à -3 % est gardé (règle de la démo).

Jumeaux : 20 comptes identiques où le sens de CHAQUE trade (ou signal C1) des trois briques est tiré à pile ou face ;
mêmes moments, même taille, mêmes règles ; le jumeau des zones vit sa sortie miroir, celui de la cassure sort au même
moment, celui de C1 a son stop miroir.

Mesures, par période : 2018-2021 (01/01/2018 -> 31/12/2021 ; C1 = BTC seul depuis 10/2020), 2022-2023, 2024 -> 09/2026
(01/01/2024 -> 30/09/2026) ; en information « 2022 -> 09/2026 » (comparaison avec l'addition approchée de crypto_flux :
+1,15 %/mois, baisse -15,7 %) et « tout » (2018 -> 09/2026).
- Compte continu (départ 100 000 $ au début de la période, rien ne l'arrête au mur ; on note s'il est touché) : gain
  %/mois composé, baisse max (fonds au plus bas d'une bougie contre le plus haut), pire jour (dans la journée, latent
  compris, contre le solde du début du jour), agitation réalisée, trades/mois par brique, PART DU GAIN de chaque brique
  (gains et pertes réalisés de la brique, frais et nuits compris, / gain total), force contre le jumeau par brique
  (information : moyenne de taille x (R - R_inverse)/2 / écart type x racine(n), trades réellement pris).
- Challenges FTMO 2 étapes : départ tous les 10 jours (jour serveur, depuis le 01/08/2017, rangé dans la période où il
  commence) à 100 000 $ ; +10 % puis +5 % (nouveau compte le jour suivant) ; mort si fonds au plus bas d'une bougie <=
  solde du début du jour - 5 000 $ ou <= 90 000 $ ; objectif = fonds moins frais de sortie >= objectif avec >= 4 jours
  de trading -> tout fermé, étape réussie ; arrêté à 24 mois sans réussite (« inachevé »). Contre les 20 jumeaux.
  % réussis en moins de 6 mois et de 12 mois.
- Compte financé (jour suivant la réussite) : 12 mois, mêmes règles, retrait tous les 30 jours du gain au-dessus de
  100 000 $ ; survie 12 mois, gain mensuel = retraits bruts / 100 000 / 12.
- Espérance d'un challenge à 540 € (remboursé si réussi) : non réussi en 12 mois = abandonné (-540 €) ; réussi en 12 mois
  = 80 % des retraits du financé sur 12 mois (en €, dernier cours EURUSD des données). Départs retenus : >= 12 mois de
  données devant eux (fin des données = 30/09/2026) et, si réussi, financé connu sur 12 mois (ou mort avant).
- Revenu mensuel du trader avec 4 comptes de 100 000 $ (plafond FTMO 400 000 $) : (a) tant que les 4 sont financés et
  vivants : 4 x 80 % x gain mensuel financé ; (b) régime durable (rachat dès qu'un compte meurt, est abandonné ou finit
  ses 12 mois) : 4 x espérance / durée moyenne d'un cycle. (Calculs de compte_combine.bilan, repris tels quels.)

Simplifications assumées : bougies de 15 min ; prix Binance (zones, C1) et Dukascopy (cassure), pas ceux de FTMO ; fonds =
solde + latent au prix (sans frais de sortie futurs) ; limite du jour FTMO comptée contre le solde du début du jour ;
retraits possibles avec des positions ouvertes ; 11 des cryptos ne sont chez FTMO que depuis le 28/07/2025 ; les 4
comptes du trader font les mêmes trades (ils vivent et meurent ensemble).

AJOUT APRÈS LECTURE DES RÉSULTATS (16/10/2026, information seulement, aucun choix) : « controle » = deux comptes pour
expliquer l'écart avec l'addition approchée de crypto_flux : (i) cassure + zones seules aux tailles de compte_combine
niveau 9 % (moitié du risque chacune), dans CE simulateur (contrôle de fidélité : doit redonner compte_combine) ;
(ii) les trois briques aux tailles de l'addition approchée (cassure + zones niveau 9 % en moitiés + C1 à 0,15 %).

Depuis Test_IA : venv_gpu\\Scripts\\python.exe -u -m collapsar.regarder.pistes.trois_briques [controle]
"""
from __future__ import annotations

import json
import math
from datetime import datetime

import numpy as np
import pandas as pd
from numba import njit

from collapsar.donnees import marches as dm
from collapsar.regarder.pistes import chef_compte_ftmo as CF
from collapsar.regarder.pistes import compte_combine as CC
from collapsar.regarder.pistes import crypto_flux as cfx
from collapsar.regarder.pistes import crypto_flux_compte as CFC
from collapsar.strategies import cassure as cs

VIE = dm.RACINE / "collapsar" / "vie" / "pistes" / "trois_briques"
CACHE = VIE / "cache"
CAP = 100_000.0
NIVEAU = 0.09
PAR_BRIQUE = NIVEAU / math.sqrt(3)
REF = {"zones": 0.0025, "cassure": 0.005, "C1": 0.0015}
CALAGE = {"zones": ("2017-08-01", "2022-01-01"), "cassure": ("2017-08-01", "2022-01-01"),
          "C1": ("2022-03-01", "2023-03-01")}
STOP_GLOBAL, STOP_CASS = 0.025, 0.03
K_STOP, TENUE_C1 = 1.5, 96
MAX_TOT, MAX_ZONES, MAX_C1, MAX_C1_SENS = 8, 4, 5, 3
JUMEAUX = 20
FIN = "2026-10-01"
PERIODES = {"2018-2021": ("2018-01-01", "2022-01-01"), "2022-2023": ("2022-01-01", "2024-01-01"),
            "2024 -> 09/2026": ("2024-01-01", FIN), "2022 -> 09/2026 (info)": ("2022-01-01", FIN),
            "tout 2018 -> 09/2026": ("2018-01-01", FIN)}
NOMS_B = ("zones", "cassure", "C1")


def log(msg: str):
    print(msg, flush=True)
    with open(VIE / "journal.txt", "a", encoding="utf-8") as f:
        f.write(msg + "\n")


def pas_date(s) -> int:
    return int((pd.Timestamp(s) - CF.T0).value // CF.PAS_NS)


# ---------------------------------------------------------------- simulation du compte (bougie de 15 min)
@njit(cache=True)
def simuler(L, H, C, poids_nuit, fill, cr, sens, e, fr, a, brique, wt, xs, xp, xk, signes,
            stop_global, stop_cass, reduction, debut, fin, mode, max_jours_chall, jour_out, gain_b, pris):
    """Copie de compte_combine.simuler étendue à 3 briques (0 zones, 1 cassure, 2 C1) et à un plafond total.
    mode 0 = compte continu (jour_out[jour] = solde début, fonds fin, pire du jour, entrées ; gain_b = réalisé par brique ;
    pris[t] = 1 si le trade est pris). mode 1 = challenge 2 étapes puis financé 12 mois.
    res : mêmes cases que compte_combine (0..17) + 18 trades C1, 19 ignorés plafond C1, 20 ignorés plafond total,
    21 ignorés C1 déjà tenu."""
    n = len(fill)
    nmax = 8
    p_tid = np.full(nmax, -1, np.int64)
    p_qty = np.zeros(nmax)
    p_ouv = np.zeros((nmax, 3), np.bool_)
    cap = 100000.0
    solde = cap
    ref_jour = cap
    arret = False
    arret_c = False
    real_c = 0.0
    phase = 1 if mode == 1 else 0
    cible = 0.10
    jours_trade = 0
    dernier_jour_trade = -1
    pic = cap
    baisse = 0.0
    nb_tr = np.zeros(3, np.int64)
    ign = np.zeros(7, np.int64)
    fin_mort = 0
    retraits = 0.0
    nb_retraits = 0
    complet = 0
    debut_fin = -1
    arrets_g = 0
    arrets_c = 0
    jours_mur = 0
    mur_jour = False
    jour_reussite = np.full(2, -1.0)
    issue = 3
    jour0 = debut // 96
    ptr = np.searchsorted(fill, debut)
    k = debut
    jour_courant = -1
    while k < fin:
        jour = k // 96
        if jour != jour_courant:
            if mur_jour:
                jours_mur += 1
            mur_jour = False
            pn = poids_nuit[jour] if jour_courant >= 0 else 0.0
            for p in range(nmax):
                if p_tid[p] >= 0:
                    t = p_tid[p]
                    for q in range(3):
                        if p_ouv[p, q]:
                            v = p_qty[p] * wt[t, q] * e[t] * 0.30 / 360.0 * pn
                            solde -= v
                            gain_b[brique[t]] -= v
            if mode == 1 and phase < 3 and jour - jour0 > max_jours_chall:
                break
            if phase == 3:
                dj = jour - debut_fin
                if dj >= 365:
                    eq = solde
                    for p in range(nmax):
                        if p_tid[p] >= 0:
                            t = p_tid[p]
                            se = sens[t] * signes[t]
                            for q in range(3):
                                if p_ouv[p, q]:
                                    eq += p_qty[p] * wt[t, q] * ((C[cr[t], k - 1] - e[t]) * se - e[t] * fr[t])
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
            arret_c = False
            real_c = 0.0
            jour_courant = jour
            if mode == 0:
                jour_out[jour, 0] = solde
                jour_out[jour, 1] = solde
                jour_out[jour, 2] = 0.0
        # sorties prévues
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
                            v = p_qty[p] * wt[t, q] * ((xp[t, g, q] - e[t]) * se - e[t] * fr[t] * cf)
                            solde += v
                            gain_b[brique[t]] += v
                            if brique[t] == 1:
                                real_c += v
                            p_ouv[p, q] = False
                        else:
                            reste = True
                if not reste:
                    p_tid[p] = -1
        # fonds au prix connu (clôture de la bougie précédente), exposition, comptes par brique
        eq = solde
        expo = 0.0
        n_z = 0
        n_c1 = 0
        n_c1_achat = 0
        n_tot = 0
        kp = k - 1 if k > 0 else 0
        for p in range(nmax):
            if p_tid[p] >= 0:
                t = p_tid[p]
                se = sens[t] * signes[t]
                n_tot += 1
                if brique[t] == 0:
                    n_z += 1
                elif brique[t] == 2:
                    n_c1 += 1
                    if se > 0:
                        n_c1_achat += 1
                part = 0.0
                for q in range(3):
                    if p_ouv[p, q]:
                        eq += p_qty[p] * wt[t, q] * (C[cr[t], kp] - e[t]) * se
                        part += wt[t, q]
                expo += p_qty[p] * part * e[t]
        # entrées
        while ptr < n and fill[ptr] < k:
            ptr += 1
        while ptr < n and fill[ptr] == k:
            t = ptr
            ptr += 1
            b = brique[t]
            if arret or (b == 1 and arret_c):
                ign[3] += 1
                continue
            deja = False
            if b == 0 or b == 2:
                for p in range(nmax):
                    if p_tid[p] >= 0 and brique[p_tid[p]] == b and cr[p_tid[p]] == cr[t]:
                        deja = True
            if deja:
                if b == 0:
                    ign[1] += 1
                else:
                    ign[6] += 1
                continue
            if b == 0 and n_z >= 4:
                ign[0] += 1
                continue
            dr = sens[t] * signes[t]
            if b == 2:
                if n_c1 >= 5 or (dr > 0 and n_c1_achat >= 3) or (dr < 0 and n_c1 - n_c1_achat >= 3):
                    ign[4] += 1
                    continue
            if n_tot >= 8:
                ign[5] += 1
                continue
            mult = 0.5 if (reduction and eq < cap * 0.94) else 1.0
            montant = mult * a[t] * solde
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
                        p_ouv[p, q] = wt[t, q] > 0
                    break
            f0 = montant * fr[t] * 0.5
            solde -= f0
            eq -= f0
            gain_b[b] -= f0
            if b == 1:
                real_c -= f0
            elif b == 0:
                n_z += 1
            else:
                n_c1 += 1
                if dr > 0:
                    n_c1_achat += 1
            n_tot += 1
            expo += montant
            nb_tr[b] += 1
            if mode == 0:
                jour_out[jour, 3] += 1
                pris[t] = 1
            if jour != dernier_jour_trade:
                jours_trade += 1
                dernier_jour_trade = jour
        # marquage au pire prix de la bougie
        pire = solde
        pire_c = real_c
        for p in range(nmax):
            if p_tid[p] >= 0:
                t = p_tid[p]
                se = sens[t] * signes[t]
                px_w = L[cr[t], k] if se > 0 else H[cr[t], k]
                for q in range(3):
                    if p_ouv[p, q]:
                        v = p_qty[p] * wt[t, q] * (px_w - e[t]) * se
                        pire += v
                        if brique[t] == 1:
                            pire_c += v
        if pire < pic:
            bb = (pire - pic) / pic
            if bb < baisse:
                baisse = bb
        if pire <= 0.90 * cap:
            mur_jour = True
        if mode == 0:
            if pire - ref_jour < jour_out[jour, 2]:
                jour_out[jour, 2] = pire - ref_jour
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
        # règles de sécurité : arrêt global du jour, puis arrêt propre à la cassure
        tout = (not arret) and (pire - ref_jour <= -stop_global * cap)
        cass = (not tout) and (not arret_c) and (pire_c <= -stop_cass * cap)
        if tout or cass:
            if tout:
                arret = True
                arrets_g += 1
            else:
                arret_c = True
                arrets_c += 1
            for p in range(nmax):
                if p_tid[p] >= 0 and (tout or brique[p_tid[p]] == 1):
                    t = p_tid[p]
                    se = sens[t] * signes[t]
                    px_w = L[cr[t], k] if se > 0 else H[cr[t], k]
                    for q in range(3):
                        if p_ouv[p, q]:
                            v = p_qty[p] * wt[t, q] * ((px_w - e[t]) * se - e[t] * fr[t])
                            solde += v
                            gain_b[brique[t]] += v
                            if brique[t] == 1:
                                real_c += v
                            p_ouv[p, q] = False
                    p_tid[p] = -1
        eqc = solde
        cout_sortie = 0.0
        for p in range(nmax):
            if p_tid[p] >= 0:
                t = p_tid[p]
                se = sens[t] * signes[t]
                for q in range(3):
                    if p_ouv[p, q]:
                        eqc += p_qty[p] * wt[t, q] * (C[cr[t], k] - e[t]) * se
                        cout_sortie += p_qty[p] * wt[t, q] * e[t] * fr[t]
        if eqc > pic:
            pic = eqc
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
            k = (jour + 1) * 96
            if phase == 3:
                debut_fin = jour + 1
            jour_courant = -1
            continue
        if mode == 0:
            jour_out[jour, 1] = eqc
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
            k = prochain
        else:
            k += 1
    if issue == 3 and phase == 3:
        issue = 0
    res = np.zeros(22)
    res[0], res[1], res[2], res[3], res[4] = issue, k, baisse, nb_tr[0], nb_tr[1]
    res[5], res[6], res[7], res[8] = ign[0], ign[1], ign[2], ign[3]
    res[9], res[10], res[11], res[12] = fin_mort, retraits, nb_retraits, complet
    res[13], res[14], res[15], res[16], res[17] = arrets_g, arrets_c, jour_reussite[0], jour_reussite[1], jours_mur
    res[18], res[19], res[20], res[21] = nb_tr[2], ign[4], ign[5], ign[6]
    return res


@njit(cache=True)
def sorties_c1(L, H, C, row, fill, sens, e, sd, kstop, tenue):
    """Sortie de chaque signal C1 pour le sens joué (g = 0) et le sens inverse (g = 1) : stop à kstop x agitation du
    jour vérifié à chaque bougie (plus bas / plus haut), sinon clôture de la bougie fill + tenue - 1."""
    n = len(fill)
    xs = np.zeros((n, 2, 3), np.int64)
    xp = np.zeros((n, 2, 3))
    xk = np.zeros((n, 2, 3), np.int64)
    for t in range(n):
        f = fill[t]
        r = row[t]
        for g in range(2):
            dr = sens[t] if g == 0 else -sens[t]
            stop = e[t] * (1.0 - dr * kstop * sd[t])
            s_, p_, k_ = f + tenue, C[r, f + tenue - 1], 0
            for j in range(f, f + tenue):
                if (dr > 0 and L[r, j] <= stop) or (dr < 0 and H[r, j] >= stop):
                    s_, p_, k_ = max(j, f + 1), stop, 1
                    break
            for q in range(3):
                xs[t, g, q], xp[t, g, q], xk[t, g, q] = s_, p_, k_
    return xs, xp, xk


# ---------------------------------------------------------------- préparation des trois briques
def trades_cassure(npas: int):
    """Copie de compte_combine.trades_cassure avec le cache de cette piste."""
    reg = cs.Reglages(N=(24,), week_end=False, sortie="milieu", taille="14j", arret_jour=STOP_CASS)
    lignes, rangs = [], {}
    for sym in ("BTCUSD", "ETHUSD"):
        c = sym[:3]
        m = cs.matrice(sym, "dukascopy", False, CACHE)
        t = cs.trades(m, reg, CC.frais_rt(c))
        base = ((m["jours"] - CF.T0).days.to_numpy()) * 96
        Lr, Hr, Cr = (np.full(npas, np.nan) for _ in range(3))
        idx = (base[:, None] + np.arange(96)[None, :])
        ok = (idx >= 0) & (idx < npas) & np.isfinite(m["C"])
        Lr[idx[ok]], Hr[idx[ok]], Cr[idx[ok]] = m["L"][ok], m["H"][ok], m["C"][ok]
        Cr = pd.Series(Cr).ffill().bfill().to_numpy()
        Lr = np.where(np.isfinite(Lr), Lr, Cr)
        Hr = np.where(np.isfinite(Hr), Hr, Cr)
        rangs[c] = (Lr, Hr, Cr)
        d = t["d"].to_numpy()
        k0 = base[d] + t["m_entree"].to_numpy() // 15
        k1 = base[d] + t["m_sortie"].to_numpy() // 15
        g = pd.DataFrame({"crypto": c, "fill_pas": k0, "sortie_pas": k1, "sens": t["sens"].to_numpy(),
                          "prix": t["e"].to_numpy(), "sortie_prix": t["x"].to_numpy(), "frais": t["frais"].to_numpy(),
                          "agitation": t["agitation"].to_numpy()})
        g = g[(g["fill_pas"] >= 1) & (g["sortie_pas"] < npas)]
        assert np.allclose(Cr[g["fill_pas"] - 1], g["prix"]) and np.allclose(Cr[g["sortie_pas"] - 1], g["sortie_prix"])
        lignes.append(g)
        del m
    return pd.concat(lignes, ignore_index=True), rangs


def trades_c1(L, H, C, npas: int):
    """Signaux C1 (cache de crypto_flux_compte, rien recalculé) posés sur la grille serveur des zones."""
    z = np.load(CFC.VIE / "cache" / "compte15_tableaux.npz")
    grille = pd.date_range(CFC.DEBUT + pd.Timedelta(minutes=15), CFC.FIN, freq="15min").astype("datetime64[ns]")
    SIG, C1p, SD = z["SIG"], z["C"], z["SD"]
    parts = []
    for i, sym in enumerate(CFC.MARCHES):
        tt = np.flatnonzero(SIG[i] != 0)
        tt = tt[np.isfinite(C1p[i, tt]) & (C1p[i, tt] > 0) & np.isfinite(SD[i, tt]) & (SD[i, tt] > 0)]
        h = pd.DatetimeIndex(grille[tt])
        srv = cfx.serveur(h - pd.Timedelta(minutes=15))           # début serveur de la bougie qui finit à h
        pas_b = np.asarray((srv - CF.T0) // pd.Timedelta(minutes=15), np.int64)
        parts.append(pd.DataFrame({"crypto": sym.replace("USDT", ""), "fill_pas": pas_b + 1,
                                   "sens": SIG[i, tt].astype(np.int64), "prix_c1": C1p[i, tt], "sd": SD[i, tt],
                                   "h_utc": h}))
    t = pd.concat(parts, ignore_index=True)
    t = t[(t["fill_pas"] >= 1) & (t["fill_pas"] + TENUE_C1 < npas)].reset_index(drop=True)
    row = t["crypto"].map({c: j for j, c in enumerate(CF.CRYPTOS)}).to_numpy().astype(np.int64)
    fill = t["fill_pas"].to_numpy().astype(np.int64)
    e = C[row, fill - 1]
    ecart = np.abs(e / t["prix_c1"].to_numpy() - 1)
    t["prix"] = e
    t["row"] = row
    t["frais"] = t["crypto"].map(CC.frais_rt)
    t = t[np.isfinite(e) & (e > 0)].reset_index(drop=True)
    ctrl = {"signaux": int(len(t)), "prix_identique_pct": float((ecart[np.isfinite(ecart)] < 1e-9).mean() * 100),
            "prix_ecart_max_pct": float(np.nanmax(ecart) * 100), "prix_ecart_median_pct": float(np.nanmedian(ecart) * 100)}
    xs, xp, xk = sorties_c1(L, H, C, t["row"].to_numpy(), t["fill_pas"].to_numpy().astype(np.int64),
                            t["sens"].to_numpy(), t["prix"].to_numpy(), t["sd"].to_numpy(), K_STOP, TENUE_C1)
    return t, xs, xp, xk, ctrl


def preparer():
    t_z, (L, Hh, Cc), poids_nuit, npas = CF.tout_charger()
    t_z = t_z.copy()
    t_z["frais"] = t_z["crypto"].map(CC.frais_rt)
    xs_z, xp_z, xk_z = CF.tableaux_sortie(t_z, "A")
    t_k, rangs = trades_cassure(npas)
    t_1, xs_1, xp_1, xk_1, ctrl = trades_c1(L, Hh, Cc, npas)
    L2 = np.vstack([L, rangs["BTC"][0], rangs["ETH"][0]])
    H2 = np.vstack([Hh, rangs["BTC"][1], rangs["ETH"][1]])
    C2 = np.vstack([Cc, rangs["BTC"][2], rangs["ETH"][2]])
    del L, Hh, Cc
    nz, nk, n1 = len(t_z), len(t_k), len(t_1)
    fill = np.r_[t_z["fill_pas"].to_numpy(), t_k["fill_pas"].to_numpy(), t_1["fill_pas"].to_numpy()].astype(np.int64)
    cr = np.r_[t_z["crypto"].map({c: j for j, c in enumerate(CF.CRYPTOS)}).to_numpy(),
               t_k["crypto"].map({"BTC": 19, "ETH": 20}).to_numpy(), t_1["row"].to_numpy()].astype(np.int64)
    sens = np.r_[t_z["sens"].to_numpy(), t_k["sens"].to_numpy(), t_1["sens"].to_numpy()].astype(np.int64)
    e = np.r_[t_z["prix"].to_numpy(float), t_k["prix"].to_numpy(float), t_1["prix"].to_numpy(float)]
    fr = np.r_[t_z["frais"].to_numpy(float), t_k["frais"].to_numpy(float), t_1["frais"].to_numpy(float)]
    brique = np.r_[np.zeros(nz, np.int64), np.ones(nk, np.int64), np.full(n1, 2, np.int64)]
    un_tiers = [1.0, 0.0, 0.0]
    wt = np.r_[np.tile(CF.GESTIONS["A"][0], (nz, 1)), np.tile(un_tiers, (nk, 1)), np.tile(un_tiers, (n1, 1))]
    xs_k = np.zeros((nk, 2, 3), np.int64)
    xs_k[:, :, :] = t_k["sortie_pas"].to_numpy()[:, None, None]
    xp_k = np.zeros((nk, 2, 3))
    xp_k[:, :, :] = t_k["sortie_prix"].to_numpy()[:, None, None]
    xs = np.concatenate([xs_z, xs_k, xs_1]).astype(np.int64)
    xp = np.concatenate([xp_z, xp_k, xp_1]).astype(float)
    xk = np.concatenate([xk_z, np.zeros((nk, 2, 3), np.int64), xk_1]).astype(np.int64)
    base_a = np.r_[1.0 / t_z["stop_frac"].to_numpy(float), 1.0 / t_k["agitation"].to_numpy(float),
                   1.0 / (K_STOP * t_1["sd"].to_numpy(float))]
    ordre = np.lexsort((cr, brique, fill))
    T = {"fill": fill[ordre], "cr": cr[ordre], "sens": sens[ordre], "e": e[ordre], "fr": fr[ordre],
         "brique": brique[ordre], "wt": np.ascontiguousarray(wt[ordre]), "xs": np.ascontiguousarray(xs[ordre]),
         "xp": np.ascontiguousarray(xp[ordre]), "xk": np.ascontiguousarray(xk[ordre]), "base_a": base_a[ordre]}
    return T, (np.nan_to_num(L2), np.nan_to_num(H2), np.nan_to_num(C2)), poids_nuit, npas, ctrl


def sous(T: dict, garder: np.ndarray, a: np.ndarray) -> dict:
    out = {k: (v[garder] if isinstance(v, np.ndarray) else v) for k, v in T.items()}
    out["a"] = a[garder]
    return out


def tailles(T: dict, r: dict) -> np.ndarray:
    b = T["brique"]
    return np.where(b == 0, r["zones"] * T["base_a"],
                    np.minimum(1.0, np.where(b == 1, r["cassure"], r["C1"]) * T["base_a"]))


# ---------------------------------------------------------------- mesures
class Labo:
    def __init__(self):
        VIE.mkdir(parents=True, exist_ok=True)
        CACHE.mkdir(parents=True, exist_ok=True)
        self.T, (self.L, self.H, self.C), self.pn, self.npas, self.ctrl = preparer()
        self.fin = pas_date(FIN)
        self.ndays = self.npas // 96 + 2
        self.eurusd = float(dm.charger("EURUSD", pd.Timestamp("2100-01-01"))["close"].iloc[-1])
        rng = np.random.default_rng(7)
        self.jum = [rng.choice(np.array([-1, 1], np.int64), len(self.T["fill"])) for _ in range(JUMEAUX)]

    def run(self, U, signes, de, a_, mode, securite=True, jo=None, gb=None, pris=None):
        if jo is None:
            jo = np.zeros((1, 4))
        if gb is None:
            gb = np.zeros(3)
        if pris is None:
            pris = np.zeros(1, np.int8)
        return simuler(self.L, self.H, self.C, self.pn, U["fill"], U["cr"], U["sens"], U["e"], U["fr"], U["a"],
                       U["brique"], U["wt"], U["xs"], U["xp"], U["xk"], signes,
                       STOP_GLOBAL if securite else 10.0, STOP_CASS if securite else 10.0, securite, de, a_, mode, 730,
                       jo, gb, pris)

    def compte(self, U, signes, de, a_, securite=True):
        d0, d1 = pas_date(de), min(pas_date(a_), self.fin)
        jo = np.zeros((self.ndays, 4))
        gb = np.zeros(3)
        pris = np.zeros(len(U["fill"]), np.int8)
        r = self.run(U, signes, d0, d1, 0, securite, jo, gb, pris)
        j0, j1 = d0 // 96, d1 // 96
        jj = jo[j0:j1]
        fonds = pd.Series(jj[:, 1], index=CF.T0 + pd.to_timedelta(np.arange(j0, j1), unit="D"))
        fonds = fonds.where(jj[:, 0] > 0).ffill().fillna(CAP)
        var = fonds.pct_change().fillna(fonds.iloc[0] / CAP - 1)
        mois = (j1 - j0) / 30.44
        fin = float(fonds.iloc[-1])
        okj = jj[:, 0] > 0
        tot = float(gb.sum())
        x = {"mois": mois, "fonds_fin": fin, "gain_pct_mois": ((fin / CAP) ** (1 / mois) - 1) * 100,
             "baisse_max_pct": float(r[2] * 100),
             "pire_jour_pct": float(np.min(jj[okj, 2] / jj[okj, 0]) * 100) if okj.any() else 0.0,
             "agitation_pct_an": float(var.std(ddof=1) * math.sqrt(365) * 100),
             "trades_mois": {"zones": float(r[3] / mois), "cassure": float(r[4] / mois), "C1": float(r[18] / mois)},
             "gain_realise_usd": {n: float(gb[i]) for i, n in enumerate(NOMS_B)},
             "gain_pct_mois_simple_par_brique": {n: float(gb[i] / CAP / mois * 100) for i, n in enumerate(NOMS_B)},
             "part_du_gain_pct": {n: (float(gb[i] / tot * 100) if abs(tot) > 1e-9 else None)
                                  for i, n in enumerate(NOMS_B)},
             "ignores": {"zones_4_positions": int(r[5]), "zones_meme_crypto": int(r[6]), "marge": int(r[7]),
                         "arret_jour": int(r[8]), "C1_plafond_5_ou_sens": int(r[19]), "plafond_8_total": int(r[20]),
                         "C1_crypto_deja_tenue": int(r[21])},
             "arrets_globaux": int(r[13]), "arrets_cassure": int(r[14]), "jours_sous_mur": int(r[17])}
        return x, var, pris

    def force(self, U, pris, de, a_) -> dict:
        lo, hi = pas_date(de), pas_date(a_)
        out = {}
        for i, nom in enumerate(NOMS_B):
            m = (pris == 1) & (U["brique"] == i) & (U["fill"] >= lo) & (U["fill"] < hi)
            if m.sum() < 21:
                out[nom] = {"trades": int(m.sum()), "force": None}
                continue
            s, e, w, a = U["sens"][m], U["e"][m], U["wt"][m], U["a"][m]
            R = (w * (U["xp"][m, 0, :] - e[:, None]) * s[:, None] / e[:, None]).sum(1)
            Ri = (w * (U["xp"][m, 1, :] - e[:, None]) * (-s)[:, None] / e[:, None]).sum(1)
            d = a * (R - Ri) / 2
            out[nom] = {"trades": int(m.sum()), "force": float(d.mean() / d.std(ddof=1) * math.sqrt(len(d)))}
        return out

    def challenges(self, U):
        departs = np.arange(0, (self.fin - 1) // 96, 10) * 96
        out = []
        for signes in [np.ones(len(U["fill"]), np.int64)] + self.jum:
            out.append(np.array([self.run(U, signes, int(d), self.fin, 1) for d in departs]))
        return departs, np.stack(out)


def ecrire(obj):
    (VIE / "resultats.json").write_text(json.dumps(obj, ensure_ascii=False, indent=1, default=str), encoding="utf-8")


def main():
    VIE.mkdir(parents=True, exist_ok=True)
    log(f"===== trois_briques {datetime.now().isoformat(timespec='seconds')}")
    lab = Labo()
    T = lab.T
    n = len(T["fill"])
    b = T["brique"]
    log(f"trades : zones {(b == 0).sum()}, cassure {(b == 1).sum()}, signaux C1 {(b == 2).sum()} ; contrôle C1 "
        f"{lab.ctrl} ; EURUSD {lab.eurusd:.4f}")
    sortie = {"quand": datetime.now().isoformat(timespec="seconds"), "eurusd": lab.eurusd, "controle_c1": lab.ctrl,
              "trades_candidats": {"zones": int((b == 0).sum()), "cassure": int((b == 1).sum()),
                                   "C1_signaux": int((b == 2).sum())}}
    un = np.ones(n, np.int64)
    # 1) calage de l'agitation, chaque brique seule à sa taille de référence, sans règles de sécurité
    a_ref = tailles(T, REF)
    ag = {}
    for i, nom in enumerate(NOMS_B):
        garde = b == i
        x, _, _ = lab.compte(sous(T, garde, a_ref), un[garde], *CALAGE[nom], securite=False)
        ag[nom] = x["agitation_pct_an"] / 100
        log(f"calage {nom} ({CALAGE[nom][0]} -> {CALAGE[nom][1]}) : agitation {ag[nom] * 100:.2f} %/an à la taille "
            f"de référence {REF[nom] * 100:.3f} %")
    r = {nom: REF[nom] * PAR_BRIQUE / ag[nom] for nom in NOMS_B}
    log(f"tailles (tiers du risque, {PAR_BRIQUE * 100:.3f} %/an chacune) : zones {r['zones'] * 100:.3f} % par trade, "
        f"cassure c = {r['cassure'] * 100:.3f} %, C1 r1 = {r['C1'] * 100:.3f} %")
    sortie["calage"] = {"agitation_ref_pct_an": {k: v * 100 for k, v in ag.items()},
                        "tailles_pct": {k: v * 100 for k, v in r.items()}}
    a = tailles(T, r)
    U = sous(T, np.ones(n, bool), a)
    # 2) compte continu par période
    sortie["periodes"] = {}
    for p, (de, a_) in PERIODES.items():
        x, var, pris = lab.compte(U, un, de, a_)
        x["force_jumeau"] = lab.force(U, pris, de, a_)
        sortie["periodes"][p] = {"compte": x}
        tm, pg = x["trades_mois"], x["part_du_gain_pct"]
        log(f"{p:24s} | {x['gain_pct_mois']:+.2f} %/mois | baisse {x['baisse_max_pct']:.1f} % | pire jour "
            f"{x['pire_jour_pct']:.2f} % | agitation {x['agitation_pct_an']:.1f} %/an | tr/mois z {tm['zones']:.1f} "
            f"c {tm['cassure']:.1f} C1 {tm['C1']:.1f} | part du gain z/c/C1 "
            + " / ".join("-" if pg[k] is None else f"{pg[k]:.0f} %" for k in NOMS_B)
            + f" | %/mois par brique " + " / ".join(f"{v:+.2f}" for v in x["gain_pct_mois_simple_par_brique"].values())
            + f" | force {[(k, None if v['force'] is None else round(v['force'], 1)) for k, v in x['force_jumeau'].items()]}"
            + f" | arrêts {x['arrets_globaux']}/{x['arrets_cassure']} | ign {x['ignores']}")
    ecrire(sortie)
    # 3) challenges (vrai + 20 jumeaux)
    departs, R = lab.challenges(U)
    np.save(CACHE / "challenges.npy", R)
    dates = CF.T0 + pd.to_timedelta(departs // 96, unit="D")
    for p, (de, a_) in PERIODES.items():
        msk = np.asarray((dates >= pd.Timestamp(de)) & (dates < pd.Timestamp(a_)))
        v = CC.bilan(R[0][msk], departs[msk], lab.fin, lab.eurusd)
        jm = CC.moyenne([CC.bilan(R[i][msk], departs[msk], lab.fin, lab.eurusd) for i in range(1, len(R))])
        sortie["periodes"][p]["challenges"] = {"vrai": v, "jumeaux": jm}
        log(f"{p:24s} | chall {v['departs']} : réussis {v['reussis_pct']:.0f} % morts {v['morts_pct']:.0f} % "
            f"(jum {jm['reussis_pct']:.0f}/{jm['morts_pct']:.0f}) | <6 mois {v['reussis_6mois_pct']:.0f} % <12 mois "
            f"{v['reussis_12mois_pct']:.0f} % (jum {jm['reussis_12mois_pct']:.0f}) | financé {v['finance_cas']} cas survie "
            f"{v['finance_survie_pct']} gain/mois {v['finance_gain_pct_mois']} | espérance {v['esperance_eur']} € (jum "
            f"{jm['esperance_eur']}) sur {v['departs_esperance']} départs | revenu 4 comptes durable "
            f"{v['revenu_4comptes_durable_eur_mois']} €/mois, financés {v['revenu_4comptes_finances_eur_mois']}")
        ecrire(sortie)
    log("FINI")


def controle():
    """Ajouté après lecture (information) : fidélité du simulateur et écart avec l'addition approchée."""
    log(f"===== contrôle d'écart {datetime.now().isoformat(timespec='seconds')}")
    lab = Labo()
    T = lab.T
    n = len(T["fill"])
    b = T["brique"]
    un = np.ones(n, np.int64)
    ag = {}
    a_ref = tailles(T, REF)
    for i, nom in enumerate(NOMS_B[:2]):
        x, _, _ = lab.compte(sous(T, b == i, a_ref), un[b == i], *CALAGE[nom], securite=False)
        ag[nom] = x["agitation_pct_an"] / 100
    moitie = 0.09 / math.sqrt(2)
    r = {"zones": REF["zones"] * moitie / ag["zones"], "cassure": REF["cassure"] * moitie / ag["cassure"], "C1": 0.0015}
    a = tailles(T, r)
    res = {"tailles_pct": {k: v * 100 for k, v in r.items()}}
    pers = {k: PERIODES[k] for k in ("2022-2023", "2024 -> 09/2026", "2022 -> 09/2026 (info)")}
    for nom, garde in (("cassure + zones, moitiés 9 % (fidélité compte_combine)", b != 2),
                       ("trois briques aux tailles de l'addition approchée", np.ones(n, bool))):
        U = sous(T, garde, a)
        res[nom] = {}
        for p, (de, a_) in pers.items():
            x, _, _ = lab.compte(U, un[garde], de, a_)
            res[nom][p] = {k: x[k] for k in ("gain_pct_mois", "baisse_max_pct", "pire_jour_pct", "agitation_pct_an",
                                             "part_du_gain_pct")}
        departs = np.arange(0, (lab.fin - 1) // 96, 10) * 96
        Rv = np.array([lab.run(U, un[garde], int(d), lab.fin, 1) for d in departs])
        dates = CF.T0 + pd.to_timedelta(departs // 96, unit="D")
        for p, (de, a_) in pers.items():
            msk = np.asarray((dates >= pd.Timestamp(de)) & (dates < pd.Timestamp(a_)))
            v = CC.bilan(Rv[msk], departs[msk], lab.fin, lab.eurusd)
            res[nom][p]["challenges"] = v
            x = res[nom][p]
            log(f"{nom[:48]:48s} | {p:22s} | {x['gain_pct_mois']:+.2f} %/mois | baisse {x['baisse_max_pct']:.1f} % | "
                f"pire jour {x['pire_jour_pct']:.2f} % | agitation {x['agitation_pct_an']:.1f} | chall réussis "
                f"{v['reussis_pct']:.0f} % morts {v['morts_pct']:.0f} % | <12 mois {v['reussis_12mois_pct']:.0f} % | "
                f"espérance {v['esperance_eur']} €")
    (VIE / "controle.json").write_text(json.dumps(res, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    log("FINI contrôle")


if __name__ == "__main__":
    import sys
    controle() if len(sys.argv) > 1 and sys.argv[1] == "controle" else main()
