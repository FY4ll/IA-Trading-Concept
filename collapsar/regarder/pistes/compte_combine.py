"""PISTE « compte_combine » : UN compte FTMO Swing 100 000 $ qui fait tourner ENSEMBLE la cassure 24 h C2 (BTC + ETH)
et les zones du chef de projet V1 (19 cryptos) — 16/10/2026.

CAHIER DES CHARGES ÉCRIT AVANT TOUT RÉSULTAT (rien n'est choisi après coup ; tout est figé ici).

Avertissement écrit d'avance : toutes les années 2017-2026 ont DÉJÀ été vues pour les deux briques (cassure : bitcoin_journee,
cassure_crypto, cassure_v3 ; chef : chef_crypto, chef_compte_ftmo). Ce calcul est une ESTIMATION de ce que donnerait un
compte qui fait tourner les deux ensemble, PAS une preuve. Aucune période n'est cachée ; aucune variante n'est choisie
sur les résultats (les 3 niveaux de risque sont tous publiés).

Brique 1 — cassure 24 h « C2 », telle qu'en démo (moteur collapsar/strategies/cassure.py, réglages N = (24,), lundi ->
  vendredi, sortie au milieu du canal, taille sur l'agitation 14 jours, arrêt de la brique à -3 % dans la journée,
  sortie forcée 23h45 serveur, donc aucune nuit). Prix Dukascopy BTCUSD et ETHUSD (ceux de C2). Taille d'un trade :
  montant = min(1, c / agitation_14j) x solde, c = niveau de la brique (même c pour BTC et ETH).
Brique 2 — zones du chef V1 « Gigogne H4 stop A plancher 0.2 », gestion A par tiers (2 R / sommet H1 / zone opposée),
  19 cryptos (BTC, ETH, ADA, DOT, LTC, XRP, DOGE, XMR, BCH, BNB, SOL, AVAX, LINK, NEAR, ALGO, ETC, XLM, UNI, VET), prix
  Binance filtrés : trades et sorties repris TELS QUELS du cache de chef_compte_ftmo (même code, rien recalculé).
  Taille : montant = r x solde / distance du stop ; au plus 4 positions de la brique, 1 par crypto (sa politique P1).
  (BTC et ETH peuvent donc être tenus en même temps par les deux briques : positions séparées, comme dans MT5.)

Frais réels FTMO (part du montant, aller-retour) = commission 0,065 % + écart ; écart BTC 0,0015 %, ETH 0,025 %,
  autres 0,03 % -> BTC 0,0665 %, ETH 0,09 %, autres 0,095 % (jusqu'au 16/10, audit défaut 5 : le tout x 1,25 de
  glissement non mesuré -> 0,083125 / 0,1125 / 0,11875 %). Moitié à l'entrée, moitié à la sortie normale ;
  frais entiers à une sortie par stop ou par arrêt de sécurité (glissement). Nuits : 30 %/an du montant d'entrée / 360
  par minuit serveur franchi (vendredi x 3, samedi et dimanche 0), payées par chaque part ouverte (brique 2 seulement en
  pratique). Levier crypto Swing 1:1 : la somme des montants ouverts (les deux briques) ne dépasse pas les fonds ; une
  taille qui ne rentre pas est réduite à la marge libre (premier arrivé, premier servi).

Budget de risque (FIXÉ avant) :
- Liste FERMÉE de 3 niveaux : agitation visée du compte 6 %, 9 %, 12 % par an.
- Moitié du risque à chaque brique : chaque brique vise une agitation de (niveau / racine(2)) par an (si les deux
  briques sont indépendantes, le compte vise alors exactement le niveau ; chaque brique porte la moitié de la variance).
- Calage (une seule fois, sur 2017-08 -> 2021-12 seulement, sur l'AGITATION et jamais sur le gain) : chaque brique est
  simulée seule à une taille de référence (cassure c = 0,5 %, chef r = 0,25 %), sans les règles de sécurité du compte ;
  agitation = écart type des variations journalières du compte (jours calendaires) x racine(365). Taille de la brique =
  taille de référence x (niveau / racine(2)) / agitation mesurée. Ces tailles restent FIXES pour toutes les périodes
  (l'agitation réelle de chaque période est publiée).
- Deux règles de sécurité du compte (toujours actives) :
  (1) arrêt global de la journée : si fonds au plus mauvais prix de la bougie de 15 min - solde du début du jour serveur
      <= -2,5 % du capital de départ -> tout est fermé à ce prix (frais entiers), plus aucune entrée ce jour ;
  (2) risque divisé par 2 pour chaque nouvelle position si les fonds (au prix de la bougie précédente) sont à moins de
      4 % du mur des -10 % (fonds < 94 % du capital de départ).
- « Chaque brique seule au même risque » = la brique seule, à SA taille du niveau, avec les mêmes règles de sécurité.
=> 9 comptes : {combiné, cassure seule, chef seul} x {6, 9, 12 %}.

Mesures, par période (avant 2022 = 2017-08-01 -> 2021-12-31, 2022-2023, 2024-2026 = 2024-01-01 -> 10/2026) et au total
- Compte continu (départ 100 000 $ au début de la période, rien ne l'arrête au mur ; on note s'il est touché) : gain
  %/mois composé, baisse max (fonds au plus bas d'une bougie contre le plus haut atteint), pire jour (dans la journée,
  latent compris, contre le solde du début du jour), agitation réalisée (%/an), trades/mois par brique.
- Lien entre les briques : corrélation des variations journalières (jours calendaires) de « cassure seule » et « chef
  seul » au niveau 9 % (le lien ne dépend presque pas du niveau).
- Force contre le jumeau par brique (information) : moyenne de (R - R_inverse)/2 / écart type x racine(n).
- Challenges FTMO 2 étapes : départ tous les 10 jours (jour serveur, depuis le 01/08/2017) à 100 000 $ ; +10 % puis +5 %
  (nouveau compte le jour suivant) ; mort si fonds au plus bas d'une bougie <= solde du début du jour - 5 000 $ ou
  <= 90 000 $ ; objectif = fonds moins frais de sortie >= objectif avec >= 4 jours de trading (jour où une position est
  ouverte) -> tout fermé, étape réussie. Calcul arrêté à 24 mois sans réussite (« inachevé »). Contre 20 JUMEAUX (mêmes
  moments, même taille, sens tiré à pile ou face trade par trade ; le jumeau du chef vit sa propre sortie miroir, celui de
  la cassure sort au même moment). % réussis en moins de 6 mois et de 12 mois.
- Compte financé (au jour suivant la réussite) : 12 mois (365 jours), mêmes règles de mort et de sécurité, retrait tous
  les 30 jours du gain au-dessus de 100 000 $ (simplification : possible avec des positions ouvertes) ; à 12 mois le reste
  au-dessus de 100 000 $ compte comme dernier retrait. Survie 12 mois, gain mensuel = retraits bruts / 100 000 / 12.
- Espérance d'un challenge à 540 € (remboursé si réussi) : un challenge non réussi en 12 mois est abandonné (-540 €) ;
  réussi en 12 mois = -540 + 540 + 80 % des retraits du financé sur 12 mois (en € au dernier cours EURUSD des données).
  Départs retenus : >= 12 mois de données devant eux et, si réussi, financé connu sur 12 mois (ou mort avant).
- Revenu mensuel moyen du trader avec 4 comptes de 100 000 $ (plafond FTMO 400 000 $ par stratégie) :
  (a) tant que les 4 comptes sont financés et vivants : 4 x 80 % x gain mensuel financé ;
  (b) en régime durable (on rachète un challenge dès qu'un compte meurt, est abandonné ou finit ses 12 mois) :
      4 x espérance par challenge / durée moyenne d'un cycle (challenge + financé), en € par mois.

Simplifications assumées : bougies de 15 min, pire prix pris au même instant pour toutes les positions (prudent) ;
prix Binance (chef) et Dukascopy (cassure), pas ceux de FTMO ; fonds = solde + latent au prix (sans frais de sortie
futurs) ; les 11 « nouvelles » cryptos ne sont chez FTMO que depuis le 28/07/2025 ; l'arrêt -3 % propre à la cassure est
gardé tel quel (à ces tailles, l'arrêt global -2,5 % agit presque toujours avant).

Depuis Test_IA : venv_gpu\\Scripts\\python.exe -u -m collapsar.regarder.pistes.compte_combine
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
from collapsar.strategies import cassure as cs

VIE = dm.RACINE / "collapsar" / "vie" / "pistes" / "compte_combine"
CACHE = VIE / "cache"
CAP = 100_000.0
PRIX = 540.0
PART = 0.80
NIVEAUX = (0.06, 0.09, 0.12)
REF_CASS, REF_CHEF = 0.005, 0.0025
STOP_GLOBAL, STOP_CASS = 0.025, 0.03
JUMEAUX = 20
FIN_DONNEES = "2026-10-16"
PERIODES = {"avant 2022": ("2017-08-01", "2022-01-01"), "2022-2023": ("2022-01-01", "2024-01-01"),
            "2024-2026": ("2024-01-01", FIN_DONNEES), "tout": ("2017-08-01", FIN_DONNEES)}
CALAGE = ("2017-08-01", "2022-01-01")


def frais_rt(c: str) -> float:
    """Commission FTMO (tarif fixe) + écart x marge de prudence (16/10, audit défaut 5 : avant, le tout x 1,25)."""
    ecart = {"BTC": 0.000015, "ETH": 0.00025}.get(c, 0.0003)
    return 0.00065 + ecart * CF.GLISSEMENT


def log(msg: str):
    print(msg, flush=True)
    with open(VIE / "journal.txt", "a", encoding="utf-8") as f:
        f.write(msg + "\n")


# ---------------------------------------------------------------- simulation du compte (bougie de 15 min)
@njit(cache=True)
def simuler(L, H, C, poids_nuit, fill, cr, sens, e, fr, a, brique, wt, xs, xp, xk, signes,
            stop_global, stop_cass, reduction, maxpos_chef, debut, fin, mode, max_jours_chall, jour_out):
    """mode 0 = compte continu de `debut` à `fin` ; jour_out[jour] = (solde début, fonds fin, pire du jour contre le
    début, trades ouverts). mode 1 = challenge 2 étapes (arrêté à max_jours_chall) puis financé 12 mois.
    res = (issue 0 réussi/1 mort étape 1/2 mort étape 2/3 inachevé, pas_fin, baisse_max, trades_chef, trades_cass,
    ign_pos, ign_crypto, ign_marge, ign_arret, finance_mort, retraits, nb_retraits, finance_complet, arrets_globaux,
    arrets_cass, jour_etape1, jour_etape2, jours_mur)."""
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
    nb_tr = np.zeros(2, np.int64)
    ign = np.zeros(4, np.int64)
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
                            solde -= p_qty[p] * wt[t, q] * e[t] * 0.30 / 360.0 * pn
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
                            if brique[t] == 1:
                                real_c += v
                            p_ouv[p, q] = False
                        else:
                            reste = True
                if not reste:
                    p_tid[p] = -1
        # fonds au prix connu (clôture de la bougie précédente) et exposition
        eq = solde
        expo = 0.0
        n_chef = 0
        kp = k - 1 if k > 0 else 0
        for p in range(nmax):
            if p_tid[p] >= 0:
                t = p_tid[p]
                se = sens[t] * signes[t]
                if brique[t] == 0:
                    n_chef += 1
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
            if arret or (brique[t] == 1 and arret_c):
                ign[3] += 1
                continue
            if brique[t] == 0:
                if n_chef >= maxpos_chef:
                    ign[0] += 1
                    continue
                deja = False
                for p in range(nmax):
                    if p_tid[p] >= 0 and brique[p_tid[p]] == 0 and cr[p_tid[p]] == cr[t]:
                        deja = True
                if deja:
                    ign[1] += 1
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
            if brique[t] == 1:
                real_c -= f0
            else:
                n_chef += 1
            expo += montant
            nb_tr[brique[t]] += 1
            if mode == 0:
                jour_out[jour, 3] += 1
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
            b = (pire - pic) / pic
            if b < baisse:
                baisse = b
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
    res = np.zeros(18)
    res[0], res[1], res[2], res[3], res[4] = issue, k, baisse, nb_tr[0], nb_tr[1]
    res[5], res[6], res[7], res[8] = ign[0], ign[1], ign[2], ign[3]
    res[9], res[10], res[11], res[12] = fin_mort, retraits, nb_retraits, complet
    res[13], res[14], res[15], res[16], res[17] = arrets_g, arrets_c, jour_reussite[0], jour_reussite[1], jours_mur
    return res


# ---------------------------------------------------------------- préparation des deux briques
def trades_cassure(npas: int):
    """Trades C2 sur BTCUSD et ETHUSD Dukascopy, posés sur la grille de chef_compte_ftmo (T0 = 01/08/2017)."""
    reg = cs.Reglages(N=(24,), week_end=False, sortie="milieu", taille="14j", arret_jour=STOP_CASS)
    lignes, rangs = [], {}
    for j, sym in enumerate(("BTCUSD", "ETHUSD")):
        c = sym[:3]
        m = cs.matrice(sym, "dukascopy", False, CACHE)
        t = cs.trades(m, reg, frais_rt(c))
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
        g = pd.DataFrame({"brique": 1, "crypto": c, "jour": t["jour"].to_numpy(), "fill_pas": k0, "sortie_pas": k1,
                          "sens": t["sens"].to_numpy(), "prix": t["e"].to_numpy(), "sortie_prix": t["x"].to_numpy(),
                          "frais": t["frais"].to_numpy(), "agitation": t["agitation"].to_numpy(),
                          "r_prix": t["r_prix"].to_numpy()})
        g = g[(g["fill_pas"] >= 1) & (g["sortie_pas"] < npas)]
        # contrôle : le prix d'entrée / sortie posé sur la grille = celui du moteur
        assert np.allclose(Cr[g["fill_pas"] - 1], g["prix"]) and np.allclose(Cr[g["sortie_pas"] - 1], g["sortie_prix"])
        lignes.append(g)
        del m
    return pd.concat(lignes, ignore_index=True), rangs


def preparer():
    t_chef, (L, Hh, Cc), poids_nuit, npas = CF.tout_charger()
    t_chef = t_chef.copy()
    t_chef["frais"] = t_chef["crypto"].map(frais_rt)
    xs_c, xp_c, xk_c = CF.tableaux_sortie(t_chef, "A")
    t_cass, rangs = trades_cassure(npas)
    marches = list(CF.CRYPTOS) + ["BTC_duka", "ETH_duka"]
    L2 = np.vstack([L, rangs["BTC"][0], rangs["ETH"][0]])
    H2 = np.vstack([Hh, rangs["BTC"][1], rangs["ETH"][1]])
    C2 = np.vstack([Cc, rangs["BTC"][2], rangs["ETH"][2]])
    del L, Hh, Cc
    nc, nk = len(t_chef), len(t_cass)
    # tableaux unifiés (chef d'abord, puis cassure), triés par moment d'entrée
    fill = np.r_[t_chef["fill_pas"].to_numpy(), t_cass["fill_pas"].to_numpy()].astype(np.int64)
    cr = np.r_[t_chef["crypto"].map({c: j for j, c in enumerate(CF.CRYPTOS)}).to_numpy(),
               t_cass["crypto"].map({"BTC": 19, "ETH": 20}).to_numpy()].astype(np.int64)
    sens = np.r_[t_chef["sens"].to_numpy(), t_cass["sens"].to_numpy()].astype(np.int64)
    e = np.r_[t_chef["prix"].to_numpy(float), t_cass["prix"].to_numpy(float)]
    fr = np.r_[t_chef["frais"].to_numpy(float), t_cass["frais"].to_numpy(float)]
    brique = np.r_[np.zeros(nc, np.int64), np.ones(nk, np.int64)]
    wt = np.r_[np.tile(CF.GESTIONS["A"][0], (nc, 1)), np.tile([1.0, 0.0, 0.0], (nk, 1))]
    xs_k = np.zeros((nk, 2, 3), np.int64)
    xs_k[:, :, :] = t_cass["sortie_pas"].to_numpy()[:, None, None]
    xp_k = np.zeros((nk, 2, 3))
    xp_k[:, :, :] = t_cass["sortie_prix"].to_numpy()[:, None, None]
    xs = np.concatenate([xs_c, xs_k]).astype(np.int64)
    xp = np.concatenate([xp_c, xp_k]).astype(float)
    xk = np.concatenate([xk_c, np.zeros((nk, 2, 3), np.int64)]).astype(np.int64)
    base_a = np.r_[1.0 / t_chef["stop_frac"].to_numpy(float), 1.0 / t_cass["agitation"].to_numpy(float)]
    ordre = np.lexsort((cr, brique, fill))
    T = {"fill": fill[ordre], "cr": cr[ordre], "sens": sens[ordre], "e": e[ordre], "fr": fr[ordre],
         "brique": brique[ordre], "wt": np.ascontiguousarray(wt[ordre]), "xs": np.ascontiguousarray(xs[ordre]),
         "xp": np.ascontiguousarray(xp[ordre]), "xk": np.ascontiguousarray(xk[ordre]), "base_a": base_a[ordre]}
    jours_t = np.r_[t_chef["fill_pas"].to_numpy() // 96, t_cass["fill_pas"].to_numpy() // 96][ordre]
    T["date"] = (CF.T0 + pd.to_timedelta(jours_t, unit="D")).to_numpy()
    # information « force contre le jumeau » : chef = (R - R_inverse)/2 (sa gestion A), cassure = sens x rendement
    info = {"chef": t_chef[["fill_pas", "R_A", "R_A_inv"]].copy(), "cass": t_cass[["fill_pas", "sens", "r_prix",
                                                                                     "agitation"]].copy()}
    return T, (np.nan_to_num(L2), np.nan_to_num(H2), np.nan_to_num(C2)), poids_nuit, npas, marches, info


def sous(T: dict, garder: np.ndarray, a: np.ndarray) -> dict:
    out = {k: (v[garder] if isinstance(v, np.ndarray) else v) for k, v in T.items()}
    out["a"] = a[garder]
    return out


def pas_date(s) -> int:
    return int((pd.Timestamp(s) - CF.T0).value // CF.PAS_NS)


# ---------------------------------------------------------------- mesures
class Labo:
    def __init__(self):
        VIE.mkdir(parents=True, exist_ok=True)
        CACHE.mkdir(parents=True, exist_ok=True)
        self.T, (self.L, self.H, self.C), self.pn, self.npas, self.marches, self.info = preparer()
        self.ndays = self.npas // 96 + 2
        self.eurusd = float(dm.charger("EURUSD", pd.Timestamp("2100-01-01"))["close"].iloc[-1])
        rng = np.random.default_rng(7)
        self.jum = [rng.choice(np.array([-1, 1], np.int64), len(self.T["fill"])) for _ in range(JUMEAUX)]

    def run(self, U, signes, de, a_, mode, securite=True, jo=None):
        if jo is None:
            jo = np.zeros((1, 4))
        return simuler(self.L, self.H, self.C, self.pn, U["fill"], U["cr"], U["sens"], U["e"], U["fr"], U["a"],
                       U["brique"], U["wt"], U["xs"], U["xp"], U["xk"], signes,
                       STOP_GLOBAL if securite else 10.0, STOP_CASS, securite, 4, de, a_, mode, 730, jo)

    def compte(self, U, signes, de, a_, securite=True):
        d0, d1 = pas_date(de), min(pas_date(a_), self.npas - 1)
        jo = np.zeros((self.ndays, 4))
        r = self.run(U, signes, d0, d1, 0, securite, jo)
        j0, j1 = d0 // 96, d1 // 96
        jj = jo[j0:j1]
        fonds = pd.Series(jj[:, 1], index=CF.T0 + pd.to_timedelta(np.arange(j0, j1), unit="D"))
        fonds = fonds.where(jj[:, 0] > 0).ffill().fillna(CAP)
        var = fonds.pct_change().fillna(fonds.iloc[0] / CAP - 1)
        mois = (j1 - j0) / 30.44
        fin = float(fonds.iloc[-1])
        okj = jj[:, 0] > 0
        return {"mois": mois, "fonds_fin": fin, "gain_pct_mois": ((fin / CAP) ** (1 / mois) - 1) * 100,
                "baisse_max_pct": float(r[2] * 100),
                "pire_jour_pct": float(np.min(jj[okj, 2] / jj[okj, 0]) * 100) if okj.any() else 0.0,
                "agitation_pct_an": float(var.std(ddof=1) * math.sqrt(365) * 100),
                "trades_chef_mois": float(r[3] / mois), "trades_cass_mois": float(r[4] / mois),
                "ignores": {"positions_chef": int(r[5]), "meme_crypto": int(r[6]), "marge": int(r[7]),
                            "arret": int(r[8])},
                "arrets_globaux": int(r[13]), "arrets_cassure": int(r[14]), "jours_sous_mur": int(r[17])}, var

    def challenges(self, U):
        departs = np.arange(0, (self.npas - 1) // 96, 10) * 96
        out = []
        for signes in [np.ones(len(U["fill"]), np.int64)] + self.jum_de(U):
            out.append(np.array([self.run(U, signes, int(d), self.npas - 1, 1) for d in departs]))
        return departs, np.stack(out)

    def jum_de(self, U):
        return [s[U["_idx"]] for s in self.jum]


def bilan(r: np.ndarray, departs: np.ndarray, npas: int, eurusd: float) -> dict:
    n = len(r)
    if n == 0:
        return {"departs": 0}
    j0 = departs / 96
    dernier = npas / 96 - 1
    issue = r[:, 0]
    reussi = issue == 0
    mort = (issue == 1) | (issue == 2)
    d_reus = r[:, 16] - j0
    d_fin = r[:, 1] / 96 - j0
    v6 = reussi & (d_reus <= 182.6)
    v12 = reussi & (d_reus <= 365.25)
    complet = (r[:, 12] == 1) | (r[:, 9] == 1)
    assez = j0 <= dernier - 365
    garde = assez & (~v12 | complet)
    mort12 = mort & (d_fin <= 365.25) & ~v12
    valeur = np.where(v12, PART * r[:, 10] / eurusd, -PRIX)
    duree_fin = np.where(r[:, 9] == 1, r[:, 1] / 96 - (r[:, 16] + 1), 365.0)
    duree = np.where(v12, d_reus + duree_fin, np.where(mort12, d_fin, 365.25)) / 30.44
    out = {"departs": int(n), "reussis_pct": float(reussi.mean() * 100), "morts_pct": float(mort.mean() * 100),
           "inacheves_24mois_pct": float((issue == 3).mean() * 100),
           "reussis_6mois_pct": float(v6.mean() * 100), "reussis_12mois_pct": float(v12.mean() * 100),
           "morts_avant_12mois_pct": float(mort12.mean() * 100),
           "mois_reussite_median": float(np.median(d_reus[reussi]) / 30.44) if reussi.any() else None,
           "departs_esperance": int(garde.sum())}
    fc = v12 & complet & assez
    if fc.any():
        out["finance_cas"] = int(fc.sum())
        out["finance_survie_pct"] = float((r[fc, 9] == 0).mean() * 100)
        out["finance_gain_pct_mois"] = float((r[fc, 10] / CAP / 12 * 100).mean())
    else:
        out["finance_cas"], out["finance_survie_pct"], out["finance_gain_pct_mois"] = 0, None, None
    if garde.any():
        out["esperance_eur"] = float(valeur[garde].mean())
        out["cycle_mois_moyen"] = float(duree[garde].mean())
        out["revenu_4comptes_durable_eur_mois"] = float(4 * valeur[garde].mean() / duree[garde].mean())
    else:
        out["esperance_eur"] = out["cycle_mois_moyen"] = out["revenu_4comptes_durable_eur_mois"] = None
    if out["finance_gain_pct_mois"] is not None:
        out["revenu_4comptes_finances_eur_mois"] = float(4 * PART * out["finance_gain_pct_mois"] / 100 * CAP / eurusd)
    else:
        out["revenu_4comptes_finances_eur_mois"] = None
    return out


def moyenne(lst: list[dict]) -> dict:
    out = {}
    for k in lst[0]:
        v = [x[k] for x in lst if x.get(k) is not None]
        out[k] = float(np.mean(v)) if v else None
    return out


def force(x: np.ndarray) -> float:
    return float(x.mean() / x.std(ddof=1) * math.sqrt(len(x))) if len(x) > 20 and x.std() > 0 else float("nan")


def ecrire(obj):
    (VIE / "resultats.json").write_text(json.dumps(obj, ensure_ascii=False, indent=1, default=str), encoding="utf-8")


def main():
    VIE.mkdir(parents=True, exist_ok=True)
    log(f"===== compte_combine {datetime.now().isoformat(timespec='seconds')}")
    lab = Labo()
    T = lab.T
    n = len(T["fill"])
    T["_idx"] = np.arange(n)
    est_chef, est_cass = T["brique"] == 0, T["brique"] == 1
    log(f"trades : chef {est_chef.sum()}, cassure {est_cass.sum()} (BTC {(est_cass & (T['cr'] == 19)).sum()}, "
        f"ETH {(est_cass & (T['cr'] == 20)).sum()}) ; EURUSD {lab.eurusd:.4f}")
    sortie = {"quand": datetime.now().isoformat(timespec="seconds"), "eurusd": lab.eurusd,
              "trades": {"chef": int(est_chef.sum()), "cassure": int(est_cass.sum())}}
    # 1) calage de l'agitation (2017-08 -> 2021-12, tailles de référence, sans règles de sécurité)
    un = np.ones(n, np.int64)
    a_ref = np.where(est_chef, REF_CHEF * T["base_a"], np.minimum(1.0, REF_CASS * T["base_a"]))
    ag = {}
    for nom, garde in (("chef", est_chef), ("cassure", est_cass)):
        U = sous(T, garde, a_ref)
        x, _ = lab.compte(U, un[garde], *CALAGE, securite=False)
        ag[nom] = x["agitation_pct_an"] / 100
        log(f"calage {nom} : agitation {ag[nom] * 100:.2f} %/an à la taille de référence")
    sortie["calage_agitation_pct_an"] = {k: v * 100 for k, v in ag.items()}
    # 2) force contre le jumeau (information)
    fz = {}
    for p, (de, a_) in PERIODES.items():
        lo, hi = pas_date(de), pas_date(a_)
        ch = lab.info["chef"]
        s = (ch["fill_pas"] >= lo) & (ch["fill_pas"] < hi)
        cc = lab.info["cass"]
        s2 = (cc["fill_pas"] >= lo) & (cc["fill_pas"] < hi)
        fz[p] = {"chef": force(((ch["R_A"] - ch["R_A_inv"]) / 2)[s].to_numpy()),
                 "cassure": force((cc["sens"] * cc["r_prix"] / cc["agitation"])[s2].to_numpy())}
    sortie["force_jumeau"] = fz
    log(f"force contre le jumeau : {fz}")
    sortie["niveaux"] = {}
    for niv in NIVEAUX:
        r_chef = REF_CHEF * (niv / math.sqrt(2)) / ag["chef"]
        c_cass = REF_CASS * (niv / math.sqrt(2)) / ag["cassure"]
        a = np.where(est_chef, r_chef * T["base_a"], np.minimum(1.0, c_cass * T["base_a"]))
        nom_n = f"{niv * 100:.0f} %"
        log(f"===== niveau {nom_n} : chef {r_chef * 100:.3f} % par trade, cassure c = {c_cass * 100:.3f} %")
        res_n = {"risque_chef_par_trade_pct": r_chef * 100, "cassure_c_pct": c_cass * 100, "comptes": {}}
        variations = {}
        for compte, garde in (("combiné", np.ones(n, bool)), ("cassure seule", est_cass), ("chef seul", est_chef)):
            U = sous(T, garde, a)
            res_c = {"periodes": {}, "challenges": {}}
            for p, (de, a_) in PERIODES.items():
                x, var = lab.compte(U, un[garde], de, a_)
                res_c["periodes"][p] = x
                variations[(compte, p)] = var
                log(f"{nom_n} | {compte:13s} | {p:10s} | {x['gain_pct_mois']:+.2f} %/mois | baisse "
                    f"{x['baisse_max_pct']:.1f} % | pire jour {x['pire_jour_pct']:.2f} % | agitation "
                    f"{x['agitation_pct_an']:.1f} %/an | tr/mois chef {x['trades_chef_mois']:.1f} cass "
                    f"{x['trades_cass_mois']:.1f} | arrêts {x['arrets_globaux']} / {x['arrets_cassure']} | "
                    f"ign {x['ignores']}")
            departs, R = lab.challenges(U)
            np.save(CACHE / f"challenges_{niv * 100:.0f}_{compte.replace(' ', '_')}.npy", R)
            dates = CF.T0 + pd.to_timedelta(departs // 96, unit="D")
            for p, (de, a_) in PERIODES.items():
                msk = np.asarray((dates >= pd.Timestamp(de)) & (dates < pd.Timestamp(a_)))
                v = bilan(R[0][msk], departs[msk], lab.npas, lab.eurusd)
                jm = moyenne([bilan(R[i][msk], departs[msk], lab.npas, lab.eurusd) for i in range(1, len(R))])
                res_c["challenges"][p] = {"vrai": v, "jumeaux": jm}
                log(f"{nom_n} | {compte:13s} | {p:10s} | chall {v['departs']} : réussis {v['reussis_pct']:.0f} % "
                    f"morts {v['morts_pct']:.0f} % (jum {jm['reussis_pct']:.0f}/{jm['morts_pct']:.0f}) | <6 mois "
                    f"{v['reussis_6mois_pct']:.0f} % <12 mois {v['reussis_12mois_pct']:.0f} % (jum "
                    f"{jm['reussis_12mois_pct']:.0f}) | financé {v['finance_cas']} cas survie "
                    f"{v['finance_survie_pct']} gain/mois {v['finance_gain_pct_mois']} | espérance "
                    f"{v['esperance_eur']} € (jum {jm['esperance_eur']}) | revenu 4 comptes durable "
                    f"{v['revenu_4comptes_durable_eur_mois']} €/mois, financés {v['revenu_4comptes_finances_eur_mois']}")
            res_n["comptes"][compte] = res_c
            sortie["niveaux"][nom_n] = res_n
            ecrire(sortie)
        lien = {}
        for p in PERIODES:
            va, vb = variations[("cassure seule", p)], variations[("chef seul", p)]
            lien[p] = float(np.corrcoef(va.to_numpy(), vb.to_numpy())[0, 1])
        res_n["lien_jour_par_jour"] = lien
        log(f"{nom_n} | lien jour par jour cassure / chef : {lien}")
        ecrire(sortie)
    ecrire(sortie)
    log("FINI")


if __name__ == "__main__":
    main()
