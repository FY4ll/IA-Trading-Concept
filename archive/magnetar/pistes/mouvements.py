"""LES MOUVEMENTS DU JOUR (18/10/2026, chef de projet : « les marchés font souvent 3-4 % dans la journée et nous n'en
attrapons que des miettes ; mes zones servent à suivre le mouvement : au contact, soit le prix REBONDIT et part loin,
soit il CASSE la zone et le mouvement CONTINUE ; il faut le reconnaître et le LAISSER COURIR »).

Tous nos tests précédents plafonnaient la sortie (2R / 3R ou 24 h). Ici, mesure SANS IA, liste FIGÉE (plan_fige.md écrit
et daté AVANT toute mesure), avec une sortie NON PLAFONNÉE au STOP SUIVEUR :
1. TAILLE DU GÂTEAU : amplitude de chaque jour (en % et en agitations), part d'un « trader parfait » qui connaît le sens
   du jour, entre après les premiers x % du mouvement et sort au stop suiveur ; notre capture actuelle pour comparer.
2. CONTINUATION : un mouvement a fait 0,5 / 1 agitation depuis l'ouverture du jour (ou depuis le bord d'une de ses zones
   touchée) : probabilité d'atteindre 2 / 3 agitations avant de revenir au départ, selon 5 conditions.
3. SES ZONES, LES DEUX SCÉNARIOS (rebond / cassure) avec stop suiveur, contre le jumeau (sens à pile ou face), les
   fausses zones (même géométrie, autre instant) et la même entrée plafonnée à 2R ; compte FTMO 100 000 $.
Moteur des trades : celui de juge_trade.un_trade (= simulateur de l'arbre : ordre à l'ouverture suivante, écart payé,
stop d'abord + glissement, bougie d'exécution au pire, nuits, fermeture avant une pause > 2 h, frais FTMO du 16/10),
recopié avec en plus la gestion du STOP SUIVEUR (`trade_suiveur`, testé à la main).
Périodes : choix <= 2021 ; vérification 2022-2023 ; contrôle UNE fois 01/2024 -> 09/2025. Rien après 09/2025.

Depuis Test_IA : venv_gpu\\Scripts\\python.exe -u -m collapsar.regarder.pistes.mouvements plan|choix|verification|controle|rapport
"""
from __future__ import annotations

import argparse
import json
import math
import time
from datetime import datetime

import numpy as np
import pandas as pd
from numba import njit

from collapsar.ecole.precision import donnees as D
from collapsar.ecole.precision import juge_trade as JT
from collapsar.ecole.precision.reglages import VIE, R, UNITES

SORTIE = VIE / "mouvements"
QUINZE_NS = 15 * 60 * 10 ** 9
HEURE_NS = 3600 * 10 ** 9
JOUR_NS = 86400 * 10 ** 9
SEMAINE_NS = 7 * JOUR_NS
MOIS_NS = 30.4375 * JOUR_NS

# ============================================================================================== LISTE FIGÉE
PERIODES = {"choix": (None, "2022-01-01"), "verification": ("2022-01-01", "2024-01-01"),
            "controle": ("2024-01-01", "2025-10-01")}
NOM_P = {"choix": "<= 2021 (choix)", "verification": "2022-2023 (vérification)",
         "controle": "01/2024 -> 09/2025 (contrôle, une seule fois)"}
GROUPES = ("tous", "cryptos", "minute", "45 marchés")
NOM_G = {"tous": "tous (66)", "cryptos": "cryptos (19)", "minute": "or-indices-euro à la minute (4)",
         "45 marchés": "45 marchés", "métaux": "zoom métaux (or + argent)"}
METAUX = ("XAUUSD", "XAUUSD@M1", "XAGUSD")
# --- 1. gâteau
JOUR_MIN_BOUGIES = 40              # un jour de moins de 40 bougies de 15 min est ignoré (jour incomplet)
X_PARFAIT = (0.25, 0.5)            # le trader parfait entre après les premiers 25 % / 50 % du mouvement du jour
GROS_JOUR_PCT = 3.0                # « gros jour » = amplitude >= 3 %
# --- 2. continuation
COURSES = ((0.5, 2.0), (0.5, 3.0), (1.0, 2.0), (1.0, 3.0))   # (déjà fait, objectif) en agitations
HORIZON_COURSE = 480               # 5 jours de bougies de 15 min ; au-delà : « non résolu »
CONDITIONS = ("alignees", "fond60", "compression", "annonce", "foule")
NOM_C = {"alignees": "unités alignées (tendance D1, H4 et H1 du même sens)",
         "fond60": "tendance de fond 60 j du même sens",
         "compression": "compression avant (agitation des 3 derniers jours < 0,7 x celle des 14)",
         "annonce": "jour d'annonce majeure (taux, emploi américain, prix) d'une devise du marché ou du dollar",
         "foule": "foule crypto : signal « contre la foule » en cours du même sens (cryptos)"}
COMPRESSION = 0.7
ANNONCES = r"Salaires non-agricoles|IPC|CPI|[Dd][ée]cision.*[Tt]aux|FOMC"
RETENUES_MAX = 12                  # cases de continuation retenues sur <= 2021 (|force| >= 2) pour le contrôle
FORCE_RETENUE = 2.0
# --- 3. ses zones
UNITES_ZONES = ("D1", "H4", "H1")
ATTENTE = 96                       # après le 1er contact, 24 h au plus pour la clôture de rebond / de cassure
MARGE_A = 0.1                      # marge derrière la zone, le creux ou le sommet (agitation)
RISQUE_MIN_A, RISQUE_MAX_A = 0.2, 3.0
DEST_MIN_R = 1.0                   # « zone suivante » plus proche que 1R : pas de destination (stop suiveur seul)
HORIZON = 2880                     # 30 jours : au-delà le trade est fermé (presque jamais : nuits, week-ends)
SUIVEURS = ("M15", "H1")
SORTIES = {"S": "stop suiveur seul (aucun objectif)", "D": "stop suiveur + sortie à la zone suivante de l'unité de départ"}
STOPS = {"Z": "stop derrière la zone touchée (+ 0,1 agitation)",
         "G": "stop derrière la PETITE zone dedans (unité plus petite, entièrement dans la grande, touchée et respectée) "
              "si elle existe, sinon derrière la grande"}
VARIANTES = ([("REB", st, tr, so) for st in STOPS for tr in SUIVEURS for so in SORTIES]
             + [("CAS", "Z", tr, so) for tr in SUIVEURS for so in SORTIES])
MIN_TRADES = 100
TIRAGES = 200
RISQUES = (1.0, 0.5)
# --- nombre de cases et seuil
N_DEJA = 65
N_CONT = 2 * len(COURSES) * ((len(CONDITIONS) - 1) * len(GROUPES) + 1) + len(COURSES)   # + rebond / cassure (zone)
N_TRADES = len(VARIANTES) * 4                     # variante, jumeau, fausses zones, plafonnée à 2R
N_COMPTES = len(RISQUES)
N_TOTAL = N_DEJA + N_CONT + N_TRADES + N_COMPTES
SEUIL = max(3.0, math.sqrt(2 * math.log(N_TOTAL)))


def vid(v) -> str:
    return "-".join(v)


def groupe(nom: str) -> str:
    return JT.groupe(nom)


def plan_texte() -> str:
    L = [f"# LES MOUVEMENTS DU JOUR — plan FIGÉ avant toute mesure ({datetime.now():%d/%m/%Y %H:%M})", "",
         "Mesure SANS IA sur les 66 marchés de l'arbre (19 cryptos, 4 à la minute : or, S&P 500, Nasdaq, euro ; 43 "
         "autres « 45 marchés »), résultats aussi par groupe et zoom métaux (or 15 min, or minute, argent). Heure du "
         "serveur ; journée = minuit du serveur. Agitation (A) = moyenne (plus haut - plus bas) des 14 derniers jours "
         "terminés (structure.py). Rien après 09/2025.", "",
         f"Périodes : choix {NOM_P['choix']} ; {NOM_P['verification']} ; {NOM_P['controle']}.", "",
         "## 1. Taille du gâteau (descriptif, aucun choix)", "",
         f"- Jours d'au moins {JOUR_MIN_BOUGIES} bougies de 15 min. Amplitude = (plus haut - plus bas) / ouverture en %, "
         f"et / A ; part des jours >= {GROS_JOUR_PCT:.0f} % ; mouvement net |clôture - ouverture| / A.",
         f"- Trader parfait : connaît le sens du jour (clôture >= ouverture = hausse) ; entre quand le prix a fait "
         f"{' / '.join(f'{x:.0%}' for x in X_PARFAIT)} du mouvement favorable du jour (plus haut - ouverture en hausse), "
         "au prix exact + demi-écart ; stop de départ à l'ouverture du jour - 0,1 A ; stop suiveur derrière chaque "
         "NOUVEAU creux (sommet) confirmé de l'unité M15 ou H1 (- 0,1 A) ; sortie au stop (glissement compris) ou à la "
         "dernière clôture du jour. Bougie d'entrée jugée au pire. Capture en % du prix et en A, frais compris.",
         "- Notre capture actuelle : trades de la meilleure piste précédente (logique inversée C1-MS-3R) et les mêmes "
         "entrées sur ses zones plafonnées à 2R (étape 3), en A par trade et par jour-marché.", "",
         "## 2. Continuation (probabilités)", "",
         "- Départ « jour » : ouverture du jour ; le 1er seuil atteint dans la journée (ouverture +- s A) donne le sens "
         "(une bougie qui touche les deux : ignoré). Départ « zone » : bord proche d'une de ses zones vivantes D1 / H4 / "
         "H1 au 1er contact ; sens = 1er seuil +- s A atteint dans les 24 h (rebond = sens de la zone, cassure = "
         "l'autre).",
         f"- Courses (s -> objectif) : {', '.join(f'{a} -> {b}' for a, b in COURSES)} agitations ; succès = objectif "
         f"avant le retour au départ (une bougie qui touche les deux = retour) ; {HORIZON_COURSE // 96} jours au plus "
         "(sinon non résolu, exclu). Taux du hasard pur (marche au hasard) = s / objectif.",
         "- Conditions, lues à la clôture de la bougie du seuil (sans futur) : " + " ; ".join(NOM_C.values()) + ".",
         f"- Annonces : calendrier MetaTrader (heures corrigées, donnees/calendrier._lire_mt5), importance haute ET nom "
         f"« {ANNONCES} », devises du marché (paire : les deux ; autres : devise de cotation) + dollar ; jour du serveur.",
         "- Pour chaque case (départ x course x condition x groupe) : taux AVEC la condition contre taux SANS ; force = "
         "écart / incertitude (grappes = semaines, tous marchés ensemble).",
         f"- Choix sur <= 2021 : cases avec |force| >= {FORCE_RETENUE:.0f} (au plus {RETENUES_MAX}, les plus fortes) ; "
         "vérification 2022-2023 ; contrôle UNE fois de ces cases seulement. Réelle si même signe sur les 3 périodes et "
         "|force| >= seuil au contrôle.", "",
         "## 3. Ses zones : rebond et cassure, sortie NON PLAFONNÉE", "",
         f"- Zones vivantes D1, H4, H1 (structure.py, fidèle à son indicateur), 1er contact (bougie de 15 min dans la "
         f"zone) alors qu'elle est vivante. Dans les {ATTENTE // 4} h qui suivent, tant qu'elle vit, la 1re clôture de "
         "15 min hors de la zone décide : du bon côté = REBOND (entrée dans le sens de la zone) ; au-delà du bord "
         "lointain = CASSURE (entrée dans le sens de la cassure). Entrée au marché à l'ouverture suivante.",
         "- Stops : " + " ; ".join(f"{k} = {v}" for k, v in STOPS.items()) + " ; cassure : stop de l'autre côté de la "
         f"zone + 0,1 A. Risque entre {RISQUE_MIN_A} et {RISQUE_MAX_A} A (et plus d'un aller-retour de frais), sinon pas "
         "de trade.",
         "- Stop suiveur (unité M15 ou H1) : à l'ouverture de chaque bougie, s'il y a un NOUVEAU creux (achat) / sommet "
         "(vente) confirmé depuis l'entrée, le stop monte (descend) juste derrière (- 0,1 A de l'entrée), jamais en "
         "arrière, jamais au-delà du prix.",
         "- Sorties : " + " ; ".join(f"{k} = {v}" for k, v in SORTIES.items()) + f" (zone suivante = bord proche de la "
         f"zone de la même unité la plus proche dans le sens du trade, au moins {DEST_MIN_R:.0f}R plus loin). Fermeture "
         f"avant une pause > 2 h (règle du simulateur) ; {HORIZON // 96} jours au plus.",
         "- Un seul trade à la fois par variante et par marché.", "",
         "| n° | variante | scénario | stop | suiveur | sortie |", "|---|---|---|---|---|---|"]
    for i, v in enumerate(VARIANTES, 1):
        L.append(f"| {i} | {vid(v)} | {'rebond' if v[0] == 'REB' else 'cassure'} | {v[1]} | {v[2]} | {v[3]} |")
    L += ["", "Comparaisons de chaque variante :",
          "- JUMEAU : mêmes trades, sens à pile ou face (trade retourné autour du prix de la décision, même stop suiveur "
          "de l'autre côté) ; avance = (R - R retourné) / 2.",
          "- FAUSSES ZONES (témoin) : même sens, même risque en A, même destination en R, même stop suiveur, posés à un "
          "instant tiré au hasard sur le même marché et la même période.",
          "- PLAFONNÉE À 2R : même entrée, même stop, stop FIXE et objectif 2R (l'ancienne façon) : ce que « laisser "
          "courir » change.",
          "Mesures : trades / mois, % gagnants, R moyen frais compris (force = R moyen / incertitude, grappes = "
          "semaines), médiane, part des trades >= 5R et >= 10R et part des gains bruts venant d'eux, durée moyenne.", "",
          "## Choix, jugement, compte", "",
          f"- Choix sur <= 2021 SEULEMENT : parmi les {len(VARIANTES)} variantes avec au moins {MIN_TRADES} trades, la plus "
          "grande force. Vérification 2022-2023 (toutes). Contrôle UNE fois 2024-2025 : la retenue et ses 3 comparaisons.",
          f"- Compte FTMO 100 000 $ de la retenue à {' puis '.join(f'{r:g} %' for r in RISQUES)} de risque par trade "
          "(gains réalisés à la sortie) : gain / mois, baisse max, challenges +10 % réussis / morts (-5 % jour, -10 % "
          f"total), jours médians, un départ tous les 7 jours, contre {TIRAGES} jumeaux ; sur les 3 périodes.",
          f"- N = {N_DEJA} déjà jugées + {N_CONT} cases de continuation + {N_TRADES} cases de trades + {N_COMPTES} "
          f"comptes = {N_TOTAL} -> seuil de preuve max(3, racine(2 ln N)) = {SEUIL:.2f}.",
          "- PROUVÉ si R moyen > 0 sur les 3 périodes et force >= seuil au contrôle ; PROMETTEUR (non prouvé) si > 0 sur "
          "les 3 avec force > 2 au contrôle ; sinon non."]
    return "\n".join(L) + "\n"


# ============================================================================================== noyaux rapides
@njit(cache=True)
def trade_suiveur(o, h, l, c, fx, ouvert, derniere, demi, nuit_a, nuit_v, nuits, t, sens, stop0, dest, dest_r,
                  horizon, gl, tv_l, tid_l, tv_s, tid_s, marge, suivre):
    """Un trade au MARCHÉ décidé à la clôture de la bougie t, joué comme juge_trade.un_trade (même ordre des règles,
    mêmes prix), avec en plus le STOP SUIVEUR : à l'ouverture de chaque bougie n, si un NOUVEAU creux (achat) / sommet
    (vente) a été confirmé depuis l'entrée (tid[n] > tid à l'entrée ; tv[n], tid[n] = ce qui est connu à la clôture de
    n - 1), le stop passe juste derrière (marge), s'il est plus favorable que l'ancien et encore du bon côté du prix.
    dest : niveau absolu (NaN = aucun) ; dest_r > 0 : objectif à dest_r fois le risque de l'entrée réelle.
    Rend (exécuté, entrée, sortie, R frais et nuits compris, code de sortie, plus grande avance en R)."""
    T = len(o)
    lg = sens > 0
    sg = 1.0 if lg else -1.0
    pos = False
    entree, st, d1 = np.nan, stop0, np.nan
    pnl, risque, rd = 0.0, np.nan, np.nan
    ne = -1
    id0 = 0
    mfe = 0.0
    for n in range(t + 1, T):
        s = demi[n]
        oo, hh, ll = o[n], h[n], l[n]
        f = fx[n]
        if ouvert[n]:
            if pos and (derniere[n] or n - ne >= horizon):
                px = oo * (1 - s) if lg else oo * (1 + s)
                pnl += sg * (px - entree) * f
                return True, ne, n, pnl / risque, JT.FORCEE if derniere[n] else JT.HORIZON_C, mfe / rd
            if n == t + 1:
                if derniere[n]:
                    return False, -1, n, np.nan, JT.REFUS, np.nan
                vente_o, achat_o = oo * (1 - s), oo * (1 + s)
                if not np.isfinite(st) or not ((lg and st < vente_o) or ((not lg) and st > achat_o)):
                    return False, -1, n, np.nan, JT.REFUS, np.nan
                px = achat_o if lg else vente_o
                pos, entree, ne = True, px, n
                rd = abs(px - st)
                risque = rd * f
                d1 = px + sg * dest_r * rd if dest_r > 0 else dest
                if np.isfinite(d1) and not ((lg and d1 > vente_o) or ((not lg) and d1 < achat_o)):
                    d1 = np.nan
                id0 = tid_l[n] if lg else tid_s[n]
        elif n == t + 1:
            return False, -1, n, np.nan, JT.REFUS, np.nan
        if pos and ouvert[n]:
            # stop suiveur : nouveau creux / sommet confirmé avant l'ouverture de n
            if suivre:
                if lg and tid_l[n] > id0 and np.isfinite(tv_l[n]):
                    cand = tv_l[n] - marge
                    if cand > st and cand < oo * (1 - s):
                        st = cand
                elif (not lg) and tid_s[n] > id0 and np.isfinite(tv_s[n]):
                    cand = tv_s[n] + marge
                    if cand < st and cand > oo * (1 + s):
                        st = cand
            if (lg and ll * (1 - s) <= st) or ((not lg) and hh * (1 + s) >= st):
                if lg:
                    px = min(st, oo * (1 - s)) * (1 - gl * s)
                else:
                    px = max(st, oo * (1 + s)) * (1 + gl * s)
                pnl += sg * (px - entree) * f
                return True, ne, n, pnl / risque, JT.STOP, mfe / rd
            if np.isfinite(d1) and ((lg and hh * (1 - s) >= d1) or ((not lg) and ll * (1 + s) <= d1)):
                px = max(d1, oo * (1 - s)) if lg else min(d1, oo * (1 + s))
                pnl += sg * (px - entree) * f
                return True, ne, n, pnl / risque, JT.DEST, max(mfe, sg * (px - entree)) / rd
            fav = (hh * (1 - s) - entree) if lg else (entree - ll * (1 + s))
            if fav > mfe:
                mfe = fav
        if pos:
            taux = nuit_a[n] if lg else nuit_v[n]
            pnl -= o[n] * f * taux / 360.0 * nuits[n]
    if pos:
        n = T - 1
        px = c[n] * (1 - demi[n]) if lg else c[n] * (1 + demi[n])
        pnl += sg * (px - entree) * fx[n]
        return True, ne, n, pnl / risque, JT.FIN, mfe / rd
    return False, -1, T - 1, np.nan, JT.FIN, np.nan


@njit(cache=True)
def jouer(o, h, l, c, fx, ouvert, derniere, demi, nuit_a, nuit_v, nuits, t, sens, stop, dest, dest_r, suivre, horizon,
          gl, tv_l, tid_l, tv_s, tid_s, marge):
    n = len(t)
    exe = np.zeros(n, np.bool_)
    ne = np.full(n, -1, np.int64)
    ns = np.full(n, -1, np.int64)
    rr = np.full(n, np.nan)
    code = np.zeros(n, np.int64)
    mfe = np.full(n, np.nan)
    for i in range(n):
        exe[i], ne[i], ns[i], rr[i], code[i], mfe[i] = trade_suiveur(
            o, h, l, c, fx, ouvert, derniere, demi, nuit_a, nuit_v, nuits, t[i], sens[i], stop[i], dest[i], dest_r[i],
            horizon, gl, tv_l, tid_l, tv_s, tid_s, marge[i], suivre[i])
    return exe, ne, ns, rr, code, mfe


@njit(cache=True)
def parfait(o, h, l, c, ds, de, A, demi, x, tv_l, tid_l, tv_s, tid_s, gl):
    """Le trader parfait de chaque jour [ds, de) : sens = clôture >= ouverture ; entrée au prix exact quand le prix a fait
    x du mouvement favorable du jour ; stop de départ ouverture - 0,1 A ; stop suiveur (nouveaux creux / sommets) ;
    sortie au stop ou à la dernière clôture. Rend la capture en prix (frais compris ; NaN si pas d'entrée)."""
    nd = len(ds)
    out = np.full(nd, np.nan)
    for k in range(nd):
        a, b = ds[k], de[k]
        O = o[a]
        Ak = A[a]
        if not (np.isfinite(Ak) and Ak > 0):
            continue
        lg = c[b - 1] >= O
        sg = 1.0 if lg else -1.0
        M = 0.0
        for n in range(a, b):
            v = (h[n] - O) if lg else (O - l[n])
            if v > M:
                M = v
        if M <= 0:
            continue
        niv = O + sg * x * M
        st = O - sg * 0.1 * Ak
        e = np.nan
        ne = -1
        for n in range(a, b):
            if (lg and h[n] >= niv) or ((not lg) and l[n] <= niv):
                s = demi[n]
                if lg:
                    e = max(niv, o[n]) * (1 + s)
                else:
                    e = min(niv, o[n]) * (1 - s)
                ne = n
                break
        if ne < 0:
            continue
        id0 = tid_l[ne] if lg else tid_s[ne]
        sortie = np.nan
        for n in range(ne, b):
            s = demi[n]
            if n > ne:
                if lg and tid_l[n] > id0 and np.isfinite(tv_l[n]):
                    cand = tv_l[n] - 0.1 * Ak
                    if cand > st and cand < o[n] * (1 - s):
                        st = cand
                elif (not lg) and tid_s[n] > id0 and np.isfinite(tv_s[n]):
                    cand = tv_s[n] + 0.1 * Ak
                    if cand < st and cand > o[n] * (1 + s):
                        st = cand
            if (lg and l[n] * (1 - s) <= st) or ((not lg) and h[n] * (1 + s) >= st):
                if lg:
                    sortie = min(st, o[n] * (1 - s)) * (1 - gl * s) if n > ne else st * (1 - gl * s)
                else:
                    sortie = max(st, o[n] * (1 + s)) * (1 + gl * s) if n > ne else st * (1 + gl * s)
                break
        if not np.isfinite(sortie):
            s = demi[b - 1]
            sortie = c[b - 1] * (1 - s) if lg else c[b - 1] * (1 + s)
        out[k] = sg * (sortie - e)
    return out


@njit(cache=True)
def courses(h, l, i0, dep, fin_trig, A, s_A, g1, g2, horizon):
    """Pour chaque départ (ligne i0, prix dep) : le 1er seuil dep +- s_A A atteint avant fin_trig (exclu) donne le sens
    et la ligne du seuil ; puis, pour les objectifs g1 et g2 (en A) : 1 = objectif avant le retour au départ, 0 = retour
    (une bougie qui touche les deux = retour), -1 = non résolu (horizon). Objectif déjà atteint dans la bougie du seuil =
    succès ; le reste de la bougie du seuil n'est pas lu (ordre inconnu)."""
    T = len(h)
    n = len(i0)
    sens = np.zeros(n, np.int64)
    trig = np.full(n, -1, np.int64)
    res = np.full((n, 2), -2, np.int64)
    for e in range(n):
        a = i0[e]
        Ae = A[e]
        if not (np.isfinite(Ae) and Ae > 0):
            continue
        haut, bas = dep[e] + s_A * Ae, dep[e] - s_A * Ae
        j = -1
        d = 0
        for m in range(a, min(fin_trig[e], T)):
            up = h[m] >= haut
            dn = l[m] <= bas
            if up and dn:
                break
            if up or dn:
                j = m
                d = 1 if up else -1
                break
        if j < 0:
            continue
        sens[e], trig[e] = d, j
        for q in range(2):
            g = g1 if q == 0 else g2
            cible = dep[e] + d * g * Ae
            if (d > 0 and h[j] >= cible) or (d < 0 and l[j] <= cible):
                res[e, q] = 1
                continue
            r = -1
            for m in range(j + 1, min(T, j + 1 + horizon)):
                retour = (d > 0 and l[m] <= dep[e]) or (d < 0 and h[m] >= dep[e])
                if retour:
                    r = 0
                    break
                if (d > 0 and h[m] >= cible) or (d < 0 and l[m] <= cible):
                    r = 1
                    break
            res[e, q] = r
    return sens, trig, res


@njit(cache=True)
def evenements(c, ligne, fin, top, bot, side, tou, attente):
    """Pour chaque zone : (genre, ligne de décision) ; genre 1 = rebond (1re clôture de 15 min hors de la zone du bon
    côté), 2 = cassure (1re clôture au-delà du bord lointain), 0 = rien (pas de contact, zone morte avant, ou rien dans
    `attente` bougies). La zone doit être vivante à la clôture précédant chaque bougie lue (ligne de l'unité < fin)."""
    T = len(c)
    nz = len(top)
    genre = np.zeros(nz, np.int64)
    dec = np.full(nz, -1, np.int64)
    for z in range(nz):
        k = tou[z]
        if k < 1 or k >= T:
            continue
        for j in range(k, min(T, k + attente)):
            if ligne[j - 1] < 0 or ligne[j - 1] >= fin[z]:
                break
            if side[z] > 0:
                if c[j] > top[z]:
                    genre[z], dec[z] = 1, j
                    break
                if c[j] < bot[z]:
                    genre[z], dec[z] = 2, j
                    break
            else:
                if c[j] < bot[z]:
                    genre[z], dec[z] = 1, j
                    break
                if c[j] > top[z]:
                    genre[z], dec[z] = 2, j
                    break
    return genre, dec


@njit(cache=True)
def min_plage(t, a, b):
    """Minimum de a[a..b] (inclus) avec une table creuse (structure.table_min)."""
    n = b - a + 1
    k = 0
    while (1 << (k + 1)) <= n:
        k += 1
    return min(t[k, a], t[k, b - (1 << k) + 1])


@njit(cache=True)
def petites(j_ev, k_ev, cote, gtop, gbot, ligne_v, knn_v, top_v, bot_v, vis_v, tou_v, tl, th, mieux):
    """Pour chaque rebond : le bord lointain de la petite zone (unité v) entièrement dans la grande, du même côté,
    vivante et visible à la décision, touchée depuis, et respectée (prix jamais au-delà de son bord lointain entre le
    contact et la décision) ; `mieux` = valeur déjà trouvée (on garde la plus serrée). NaN si aucune."""
    out = mieux.copy()
    for e in range(len(j_ev)):
        j, k = j_ev[e], k_ev[e]
        lv = ligne_v[j]
        if lv < 0:
            continue
        cc = 0 if cote[e] > 0 else 1
        for q in range(knn_v.shape[2]):
            z = knn_v[lv, cc, q]
            if z < 0 or vis_v[z] > j or tou_v[z] > j:
                continue
            if top_v[z] > gtop[e] + 1e-12 or bot_v[z] < gbot[e] - 1e-12:
                continue
            if cote[e] > 0:
                if min_plage(tl, k, j) <= bot_v[z]:
                    continue
                if not np.isfinite(out[e]) or bot_v[z] > out[e]:
                    out[e] = bot_v[z]
            else:
                if -min_plage(th, k, j) >= top_v[z]:
                    continue
                if not np.isfinite(out[e]) or top_v[z] < out[e]:
                    out[e] = top_v[z]
    return out


# ============================================================================================== outils sans futur
def _periode_ns(periode: str) -> tuple[int, int]:
    de, a = PERIODES[periode]
    return (pd.Timestamp(de).value if de else 0), pd.Timestamp(a).value


def _change(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    return (a != b) & ~(np.isnan(a) & np.isnan(b))


def suiveur_lignes(x: dict, u: str, prec: np.ndarray):
    """(creux, n° du creux, sommet, n° du sommet) de l'unité u CONNUS à l'ouverture de chaque bougie dont la bougie
    précédente (en lignes de 15 min de structure.py) est `prec` : rien du futur (lignes d'unité fermées seulement)."""
    sw = np.asarray(x[u]["sw"], np.float64)
    nc = np.r_[0, np.cumsum(_change(sw[1:, 2], sw[:-1, 2]) | _change(sw[1:, 3], sw[:-1, 3]))].astype(np.int64)
    ns = np.r_[0, np.cumsum(_change(sw[1:, 0], sw[:-1, 0]) | _change(sw[1:, 1], sw[:-1, 1]))].astype(np.int64)
    lg = np.asarray(x[u]["ligne"]).astype(np.int64)
    pp = np.asarray(prec, np.int64)
    ok = pp >= 0
    li = np.where(ok, lg[np.clip(pp, 0, None)], -1)
    ok &= li >= 0
    lc = np.clip(li, 0, None)
    return (np.where(ok, sw[lc, 2], np.nan), np.where(ok, nc[lc], 0), np.where(ok, sw[lc, 0], np.nan),
            np.where(ok, ns[lc], 0))


def tendance_unites(x: dict, rows: np.ndarray) -> np.ndarray:
    """[n, 3] : tendance de structure de D1, H4, H1 à la clôture des lignes `rows` : +1 si les 2 derniers sommets ET
    creux montent, -1 s'ils descendent, 0 sinon."""
    out = np.zeros((len(rows), len(UNITES_ZONES)), np.int8)
    for i, u in enumerate(UNITES_ZONES):
        lg = np.asarray(x[u]["ligne"]).astype(np.int64)[rows]
        sw = np.asarray(x[u]["sw"], np.float64)[np.clip(lg, 0, None)]
        hausse = (sw[:, 0] > sw[:, 1]) & (sw[:, 2] > sw[:, 3])
        baisse = (sw[:, 0] < sw[:, 1]) & (sw[:, 2] < sw[:, 3])
        out[:, i] = np.where(lg >= 0, np.where(hausse, 1, np.where(baisse, -1, 0)), 0)
    return out


def jours_de(t15: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """(début, fin exclue, date du jour) des jours du serveur, en lignes de 15 min."""
    j = t15 - t15 % JOUR_NS
    ds = np.flatnonzero(np.r_[True, j[1:] != j[:-1]])
    de = np.r_[ds[1:], len(t15)]
    return ds, de, j[ds]


def compression(x: dict, rows: np.ndarray) -> np.ndarray:
    """Agitation des 3 derniers jours TERMINÉS / celle des 14 derniers (jours du serveur avant le jour de la ligne)."""
    t15 = np.asarray(x["t15"], np.int64)
    h, l = np.asarray(x["h"]), np.asarray(x["l"])
    ds, de, jd = jours_de(t15)
    rg = np.maximum.reduceat(h, ds) - np.minimum.reduceat(l, ds)
    m3 = pd.Series(rg).rolling(3).mean().to_numpy()
    m14 = pd.Series(rg).rolling(14, min_periods=3).mean().to_numpy()
    k = np.searchsorted(jd, t15[rows] - t15[rows] % JOUR_NS) - 1                 # dernier jour terminé
    kk = np.clip(k, 0, None)
    return np.where(k >= 0, m3[kk] / m14[kk], np.nan)


_ANN = {}


def jours_annonces(nom: str) -> np.ndarray:
    """Jours du serveur (ns, minuit) avec une annonce majeure d'une devise du marché ou du dollar (< fin_donnees)."""
    from collapsar.donnees import calendrier as CA
    from collapsar.mains.fiches import fiche
    if "cal" not in _ANN:
        d = CA._lire_mt5(CA.MT5_HISTOIRE)
        d = d[(d["temps"] < R().periodes.fin_donnees) & (d["importance"] == 3)]
        d = d[d["annonce"].astype(str).str.contains(ANNONCES, regex=True)]
        _ANN["cal"] = d[["temps", "devise"]].reset_index(drop=True)
    cal = _ANN["cal"]
    if D.source(nom) == "binance":
        dev = {"USD"}
    else:
        f = fiche(D.base(nom))
        b = D.base(nom)
        dev = {b[:3], b[3:6], "USD"} if f.famille == "devise" else {f.cotation, "USD"}
    t = cal.loc[cal["devise"].isin(dev), "temps"].values.astype("datetime64[ns]").astype(np.int64)
    return np.unique(t - t % JOUR_NS)


def conditions(nom: str, x: dict, rows: np.ndarray, sens: np.ndarray) -> dict:
    """Les 5 conditions (booléens) à la clôture des lignes `rows`, pour un mouvement de sens `sens`."""
    from collapsar.ecole.precision import direction as DI
    t15 = np.asarray(x["t15"], np.int64)
    dec = t15[rows] + QUINZE_NS
    tu = tendance_unites(x, rows)
    out = {"alignees": (tu == sens[:, None]).all(1) & (sens != 0)}
    sg, _ = DI.tendance(nom, dec)
    out["fond60"] = (sg[:, 1] == sens) & (sens != 0)
    out["compression"] = np.nan_to_num(compression(x, rows), nan=9.0) < COMPRESSION
    ja = jours_annonces(nom)
    out["annonce"] = np.isin(t15[rows] - t15[rows] % JOUR_NS, ja)          # jour du serveur de la bougie du seuil
    out["foule"] = (DI.c1(nom, dec) == sens) & (sens != 0) if D.source(nom) == "binance" else np.zeros(len(rows), bool)
    return out


# ============================================================================================== 1. le gâteau
def gateau_marche(nom: str, x: dict, de_ns: int, a_ns: int) -> pd.DataFrame:
    t15 = np.asarray(x["t15"], np.int64)
    o, h, l, c = (np.asarray(x[k], np.float64) for k in ("o", "h", "l", "c"))
    A, demi = np.asarray(x["A"], np.float64), np.asarray(x["demi"], np.float64)
    ds, de, jd = jours_de(t15)
    H, Lw = np.maximum.reduceat(h, ds), np.minimum.reduceat(l, ds)          # jours contigus : un segment par jour
    ok = ((de - ds) >= JOUR_MIN_BOUGIES) & (jd >= de_ns) & (jd < a_ns) & np.isfinite(A[ds]) & (A[ds] > 0)
    ds, de, jd, H, Lw = ds[ok], de[ok], jd[ok], H[ok], Lw[ok]
    if not len(ds):
        return pd.DataFrame()
    O, C, Ad = o[ds], c[de - 1], A[ds]
    df = pd.DataFrame({"marche": nom, "jour": jd, "amp_pct": (H - Lw) / O * 100, "amp_A": (H - Lw) / Ad,
                       "net_A": np.abs(C - O) / Ad, "A_pct": Ad / O * 100, "frais_pct": 2 * demi[ds] * 100})
    prec = np.arange(len(t15)) - 1
    gl = float(R().monde.frais_stop_glissement)
    # repère AJOUTÉ après le plan (descriptif) : même entrée, sans stop suiveur (stop à l'ouverture - 0,1 A, tenu
    # jusqu'à la clôture du jour)
    vide_v, vide_i = np.full(len(t15), np.nan), np.zeros(len(t15), np.int64)
    for xx in X_PARFAIT:
        cap = parfait(o, h, l, c, ds.astype(np.int64), de.astype(np.int64), A, demi, xx, vide_v, vide_i, vide_v, vide_i, gl)
        df[f"parfait_tenir_{int(xx * 100)}_pct"] = cap / O * 100
        df[f"parfait_tenir_{int(xx * 100)}_A"] = cap / Ad
    for u in SUIVEURS:
        tv_l, tid_l, tv_s, tid_s = suiveur_lignes(x, u, prec)
        for xx in X_PARFAIT:
            cap = parfait(o, h, l, c, ds.astype(np.int64), de.astype(np.int64), A, demi, xx, tv_l, tid_l, tv_s, tid_s, gl)
            df[f"parfait_{u}_{int(xx * 100)}_pct"] = cap / O * 100
            df[f"parfait_{u}_{int(xx * 100)}_A"] = cap / Ad
    return df


# ============================================================================================== 2. continuation
def zones_unite(x: dict, u: str) -> dict:
    """Zones d'une unité avec leur ligne de disparition (recalculée : 1re clôture de l'unité au-delà du milieu)."""
    from collapsar.ecole.precision import structure as S
    y = x[u]
    top, bot = np.asarray(y["top"], np.float64), np.asarray(y["bot"], np.float64)
    side, vis, tou = np.asarray(y["side"]).astype(np.int64), np.asarray(y["vis"]).astype(np.int64), np.asarray(y["tou"]).astype(np.int64)
    lg = np.asarray(y["ligne"]).astype(np.int64)
    T = len(lg)
    okv = vis < T
    ne = np.where(okv, lg[np.clip(vis, 0, T - 1)], 2 ** 40)
    fin = S.fins_zones(np.asarray(y["cl"], np.float64), (top + bot) / 2, side, np.clip(ne, 0, len(y["cl"]))) \
        if len(top) else np.zeros(0, np.int64)
    fin = np.where(okv, fin, -1)
    return {"top": top, "bot": bot, "side": side, "vis": vis, "tou": tou, "ligne": lg, "fin": fin.astype(np.int64)}


def contacts_vivants(x: dict, u: str, Z: dict) -> np.ndarray:
    """Zones de l'unité dont le 1er contact a lieu alors qu'elles sont vivantes (à la clôture précédente)."""
    T = len(Z["ligne"])
    k = Z["tou"]
    ok = (k >= 1) & (k < T)
    kk = np.clip(k - 1, 0, T - 1)
    ok &= (Z["ligne"][kk] >= 0) & (Z["ligne"][kk] < Z["fin"]) & (Z["vis"] <= kk)
    return np.flatnonzero(ok)


def continuation_marche(nom: str, x: dict, de_ns: int, a_ns: int) -> pd.DataFrame:
    t15 = np.asarray(x["t15"], np.int64)
    o, h, l = (np.asarray(x[k], np.float64) for k in ("o", "h", "l"))
    A = np.asarray(x["A"], np.float64)
    ds, de, jd = jours_de(t15)
    okj = ((de - ds) >= JOUR_MIN_BOUGIES) & np.isfinite(A[ds]) & (A[ds] > 0)
    blocs = []
    # départ « jour »
    i0, dep, fin, Ae = ds[okj], o[ds[okj]], de[okj], A[ds[okj]]
    blocs.append(("jour", i0, dep, fin, Ae, np.zeros(len(i0), np.int64), np.full(len(i0), -1)))
    # départ « zone » : bord proche au 1er contact (zones vivantes D1 / H4 / H1)
    for iu, u in enumerate(UNITES_ZONES):
        Z = zones_unite(x, u)
        zz = contacts_vivants(x, u, Z)
        k = Z["tou"][zz]
        dep_z = np.where(Z["side"][zz] > 0, Z["top"][zz], Z["bot"][zz])
        blocs.append(("zone", k, dep_z, np.minimum(k + ATTENTE, len(t15)), A[k], Z["side"][zz], np.full(len(zz), iu)))
    # repère AJOUTÉ après le plan (descriptif, jamais choisi) : départ à l'ouverture d'une bougie tirée au hasard, seuil
    # dans les 24 h : le vrai taux de base du marché avec le même horizon de 5 jours
    import zlib
    rng = np.random.default_rng(zlib.crc32(nom.encode()))
    ok_h = np.flatnonzero(np.isfinite(A) & (A > 0))
    ok_h = ok_h[ok_h < len(t15) - 1]
    if len(ok_h):
        rh = np.sort(rng.choice(ok_h, min(len(ok_h), int(okj.sum())), replace=False))
        blocs.append(("hasard", rh, o[rh], np.minimum(rh + ATTENTE, len(t15)), A[rh], np.zeros(len(rh), np.int64),
                      np.full(len(rh), -1)))
    out = []
    for nom_d, i0, dep, fin, Ae, side, unite in blocs:
        if not len(i0):
            continue
        for s_A in sorted({a for a, _ in COURSES}):
            gs = [g for a, g in COURSES if a == s_A]
            sens, trig, res = courses(h, l, np.asarray(i0, np.int64), np.asarray(dep, np.float64),
                                      np.asarray(fin, np.int64), np.asarray(Ae, np.float64), s_A, gs[0], gs[1],
                                      HORIZON_COURSE)
            ok = trig >= 0
            dec = t15[np.clip(trig, 0, None)] + QUINZE_NS
            ok &= (dec >= de_ns) & (dec < a_ns)
            if not ok.any():
                continue
            rows = trig[ok]
            se = sens[ok]
            cond = conditions(nom, x, rows, se)
            for q, g in enumerate(gs):
                d = pd.DataFrame({"marche": nom, "depart": nom_d, "s": s_A, "g": g, "sens": se, "dec": dec[ok],
                                  "res": res[ok, q], "rebond": (se == side[ok]) & (side[ok] != 0),
                                  "unite": unite[ok]})
                for k_, v in cond.items():
                    d[k_] = v
                out.append(d)
    return pd.concat(out, ignore_index=True) if out else pd.DataFrame()


# ============================================================================================== 3. ses zones
def evenements_marche(x: dict) -> dict:
    """Tous les rebonds / cassures des zones D1, H4, H1 : ligne de contact, de décision, côté, bords, unité, genre."""
    c = np.asarray(x["c"], np.float64)
    acc = {k: [] for k in ("k", "j", "side", "top", "bot", "unite", "genre")}
    for iu, u in enumerate(UNITES_ZONES):
        Z = zones_unite(x, u)
        zz = contacts_vivants(x, u, Z)
        if not len(zz):
            continue
        genre, dec = evenements(c, Z["ligne"], Z["fin"][zz], Z["top"][zz], Z["bot"][zz], Z["side"][zz], Z["tou"][zz],
                                ATTENTE)
        m = genre > 0
        acc["k"].append(Z["tou"][zz][m])
        acc["j"].append(dec[m])
        acc["side"].append(Z["side"][zz][m])
        acc["top"].append(Z["top"][zz][m])
        acc["bot"].append(Z["bot"][zz][m])
        acc["unite"].append(np.full(int(m.sum()), iu))
        acc["genre"].append(genre[m])
    return {k: (np.concatenate(v) if v else np.zeros(0)) for k, v in acc.items()}


def stop_petite_zone(x: dict, ev: dict, idx: np.ndarray) -> np.ndarray:
    """Bord lointain de la petite zone la plus serrée dans la grande (rebonds `idx`) ; NaN si aucune."""
    from collapsar.ecole.precision import structure as S
    l, h = np.asarray(x["l"], np.float64), np.asarray(x["h"], np.float64)
    tl, th = S.table_min(l), S.table_min(-h)
    best = np.full(len(idx), np.nan)
    unites_x = [u for u in UNITES if u in x]
    for e_u in range(len(UNITES_ZONES)):
        m = ev["unite"][idx] == e_u
        if not m.any():
            continue
        plus_petites = unites_x[unites_x.index(UNITES_ZONES[e_u]) + 1:]
        ii = idx[m]
        b = best[m]
        for v in plus_petites:
            y = x[v]
            b = petites(ev["j"][ii].astype(np.int64), ev["k"][ii].astype(np.int64), ev["side"][ii].astype(np.int64),
                        ev["top"][ii], ev["bot"][ii], np.asarray(y["ligne"]).astype(np.int64),
                        np.asarray(y["knn"]).astype(np.int64), np.asarray(y["top"], np.float64),
                        np.asarray(y["bot"], np.float64), np.asarray(y["vis"]).astype(np.int64),
                        np.asarray(y["tou"]).astype(np.int64), tl, th, b)
        best[m] = b
    return best


def zone_suivante(x: dict, ev: dict, idx: np.ndarray, sens: np.ndarray, p: np.ndarray) -> np.ndarray:
    """Bord proche de la zone vivante de la même unité la plus proche dans le sens du trade (achat : offre au-dessus,
    bord bas ; vente : demande en dessous, bord haut), vue à la décision ; NaN si aucune."""
    out = np.full(len(idx), np.nan)
    for e_u, u in enumerate(UNITES_ZONES):
        m = np.flatnonzero(ev["unite"][idx] == e_u)
        if not len(m):
            continue
        y = x[u]
        lg = np.asarray(y["ligne"]).astype(np.int64)[ev["j"][idx[m]].astype(np.int64)]
        knn = np.asarray(y["knn"]).astype(np.int64)
        top, bot = np.asarray(y["top"], np.float64), np.asarray(y["bot"], np.float64)
        vis = np.asarray(y["vis"]).astype(np.int64)
        for q, i in enumerate(m):
            if lg[q] < 0:
                continue
            j = int(ev["j"][idx[i]])
            if sens[i] > 0:
                cand = [bot[z] for z in knn[lg[q], 1] if z >= 0 and vis[z] <= j and bot[z] > p[i]]
                out[i] = min(cand) if cand else np.nan
            else:
                cand = [top[z] for z in knn[lg[q], 0] if z >= 0 and vis[z] <= j and top[z] < p[i]]
                out[i] = max(cand) if cand else np.nan
    return out


def geometries(x: dict, ev: dict) -> dict:
    """Pour chaque famille de stop (REB-Z, REB-G, CAS-Z) : événements gardés, sens, stop, zone suivante."""
    c, A = np.asarray(x["c"], np.float64), np.asarray(x["A"], np.float64)
    demi = np.asarray(x["demi"], np.float64)
    out = {}
    j = ev["j"].astype(np.int64)
    for fam in ("REB-Z", "REB-G", "CAS-Z"):
        reb = fam.startswith("REB")
        idx = np.flatnonzero(ev["genre"] == (1 if reb else 2))
        side = ev["side"][idx]
        sens = side if reb else -side
        p, Aj = c[j[idx]], A[j[idx]]
        marge = MARGE_A * Aj
        if reb:
            loin = np.where(sens > 0, ev["bot"][idx], ev["top"][idx])
            if fam == "REB-G":
                pz = stop_petite_zone(x, ev, idx)
                loin = np.where(np.isfinite(pz), pz, loin)
        else:
            loin = np.where(sens > 0, ev["bot"][idx], ev["top"][idx])     # cassure : l'autre côté de la zone
        stop = loin - sens * marge
        rd = sens * (p - stop)
        fr = 2 * demi[j[idx]] * p
        ok = np.isfinite(Aj) & (Aj > 0) & (rd >= RISQUE_MIN_A * Aj) & (rd <= RISQUE_MAX_A * Aj) & (rd > fr)
        idx, sens, stop, p, Aj = idx[ok], sens[ok], stop[ok], p[ok], Aj[ok]
        dest = zone_suivante(x, ev, idx, sens, p)
        dest = np.where(sens * (dest - p) >= DEST_MIN_R * sens * (p - stop), dest, np.nan)
        out[fam] = {"idx": idx, "sens": sens.astype(np.float64), "stop": stop, "dest": dest, "p": p, "A": Aj}
    return out


def trades_marche(nom: str, x: dict, de_ns: int, a_ns: int, variantes: list, graine: int,
                  comparaisons: bool = True) -> dict:
    """Les trades des variantes sur un marché pour une période : la variante (un trade à la fois) et, pour les trades
    gardés : jumeau retourné, fausses zones, même entrée plafonnée à 2R (stop fixe)."""
    from collapsar.ecole.precision.univers import Univers
    from collapsar.regarder.pistes import logique_inversee as LI
    t15 = np.asarray(x["t15"], np.int64)
    debut = max(pd.Timestamp(int(t15[0])) + pd.Timedelta(days=45), pd.Timestamp(de_ns) - pd.Timedelta(days=5))
    if debut.value >= a_ns - 30 * JOUR_NS:
        return {}
    U = Univers([(nom, False)], debut, pd.Timestamp(a_ns) + pd.Timedelta(days=40), "cpu")
    ch = JT.chemin(U)
    gl = float(R().monde.frais_stop_glissement)
    m = np.searchsorted(t15, U.t_ns)
    assert np.array_equal(t15[np.clip(m, 0, len(t15) - 1)], U.t_ns), nom
    suiv = {u: suiveur_lignes(x, u, m - 1) for u in SUIVEURS}
    ev = evenements_marche(x)
    geo = geometries(x, ev)
    rng = np.random.default_rng(graine)
    # instants permis aux fausses zones : même marché, même période
    okf = np.zeros(U.T, bool)
    okf[:-2] = U.ouvert[1:-1, 0] & ~U.derniere[1:-1, 0]
    dec_u = U.t_ns + QUINZE_NS
    okf &= (dec_u >= de_ns) & (dec_u < a_ns) & (U.A[:, 0] > 0)
    lignes_f = np.flatnonzero(okf)
    out = {}
    for v in variantes:
        fam = f"{v[0]}-{v[1]}"
        g = geo[fam]
        j = ev["j"][g["idx"]].astype(np.int64)
        dec = t15[j] + QUINZE_NS
        okp = (dec >= de_ns) & (dec < a_ns) & (t15[j] >= U.t_ns[0])
        sel = np.flatnonzero(okp)
        if not len(sel):
            continue
        tU = np.searchsorted(U.t_ns, t15[j[sel]])
        assert np.array_equal(U.t_ns[np.clip(tU, 0, U.T - 1)], t15[j[sel]])
        sens, stop, p, Aj = g["sens"][sel], g["stop"][sel], g["p"][sel], g["A"][sel]
        dest = g["dest"][sel] if v[3] == "D" else np.full(len(sel), np.nan)
        tv_l, tid_l, tv_s, tid_s = suiv[v[2]]
        n = len(sel)
        un = np.ones(n, bool)
        mg = MARGE_A * Aj
        jo = lambda tt, sg, st, ds, dr, sv, mm: jouer(*ch, tt.astype(np.int64), sg, st, ds, dr, sv, HORIZON, gl,
                                                       tv_l, tid_l, tv_s, tid_s, mm)
        exe, ne, ns, rr, code, mfe = jo(tU, sens, stop, dest, np.zeros(n), un, mg)
        kg = LI.garder_un_a_la_fois(tU, exe, ns, code)
        tU, sens, stop, dest, p, Aj, mg = tU[kg], sens[kg], stop[kg], dest[kg], p[kg], Aj[kg], mg[kg]
        exe, ne, ns, rr, code, mfe = exe[kg], ne[kg], ns[kg], rr[kg], code[kg], mfe[kg]
        n = len(tU)
        rd = sens * (p - stop)
        tn = lambda k: np.where(k >= 0, U.t_ns[np.clip(k, 0, U.T - 1)], -1)
        z = {"dec_ns": U.t_ns[tU] + QUINZE_NS, "sens": sens.astype(np.int8), "unite": ev["unite"][g["idx"][sel][kg]].astype(np.int8),
             "risque_A": rd / Aj, "risque_pct": rd / p * 100, "a_dest": np.isfinite(dest),
             # frais estimés en R (descriptif) : écart à l'entrée et à la sortie + glissement d'un stop
             "frais_R": (2.0 + gl) * U.demi[np.clip(tU + 1, 0, U.T - 1), 0] * p / rd,
             "exe": exe, "r": rr, "code": code, "ne_ns": tn(ne), "ns_ns": tn(ns), "mfe": mfe}
        if comparaisons and n:
            # jumeau : retourné autour du prix de la décision
            exe_j, ne_j, ns_j, rr_j, code_j, _ = jo(tU, -sens, 2 * p - stop, 2 * p - dest, np.zeros(n), np.ones(n, bool), mg)
            # fausses zones : même sens, même risque en A, même destination en R, autre instant
            tf = rng.choice(lignes_f, n) if len(lignes_f) else tU
            pf, Af = U.c[tf, 0].astype(np.float64), U.A[tf, 0].astype(np.float64)
            rdf = rd / Aj * Af
            dR = sens * (dest - p) / rd
            exe_f, _, ns_f, rr_f, code_f, _ = jo(tf, sens, pf - sens * rdf, pf + sens * dR * rdf, np.zeros(n),
                                                 np.ones(n, bool), MARGE_A * Af)
            # même entrée, stop fixe, objectif 2R
            exe_c, _, ns_c, rr_c, code_c, _ = jo(tU, sens, stop, np.full(n, np.nan), np.full(n, 2.0), np.zeros(n, bool), mg)
            z.update({"exe_j": exe_j, "r_j": rr_j, "code_j": code_j, "ne_j_ns": tn(ne_j), "ns_j_ns": tn(ns_j),
                      "exe_f": exe_f, "r_f": rr_f, "code_f": code_f, "dec_f_ns": U.t_ns[tf] + QUINZE_NS,
                      "exe_c": exe_c, "r_c": rr_c, "code_c": code_c, "ne_c_ns": tn(ne), "ns_c_ns": tn(ns_c)})
        out[vid(v)] = z
    del U, ch
    return out


# ============================================================================================== calcul d'une période
def calculer(periode: str, variantes: list, continuation: bool = True, dire=print) -> dict:
    from collapsar.ecole.precision import structure as S
    de_ns, a_ns = _periode_ns(periode)
    dos = SORTIE / periode
    dos.mkdir(parents=True, exist_ok=True)
    gats, conts = [], []
    acc = {vid(v): [] for v in variantes}
    marches = list(D.univers())
    t0 = time.time()
    for im, nom in enumerate(marches):
        x = S.lire(nom, False)
        g = gateau_marche(nom, x, de_ns, a_ns)
        if len(g):
            gats.append(g)
        if continuation:
            cdf = continuation_marche(nom, x, de_ns, a_ns)
            if len(cdf):
                conts.append(cdf)
        tr = trades_marche(nom, x, de_ns, a_ns, variantes, 20261018 + im)
        for k, z in tr.items():
            z["marche"] = np.full(len(z["exe"]), im, np.int16)
            acc[k].append(z)
        dire(f"{periode} {nom} : {len(g)} jours, " + ", ".join(f"{k} {int(z['exe'].sum())}" for k, z in tr.items())
             + f" trades ({time.time() - t0:.0f} s)")
    pd.concat(gats, ignore_index=True).to_pickle(dos / "gateau.pkl")
    if continuation:
        pd.concat(conts, ignore_index=True).to_pickle(dos / "continuation.pkl")
    for k, morceaux in acc.items():
        if morceaux:
            np.savez(dos / f"{k}.npz", **{c: np.concatenate([m_[c] for m_ in morceaux]) for c in morceaux[0]})
    (dos / "marches.json").write_text(json.dumps(marches), encoding="utf-8")
    return {"marches": marches}


def lire_trades(periode: str, k: str) -> dict:
    z = np.load(SORTIE / periode / f"{k}.npz")
    return {c: z[c] for c in z.files}


# ============================================================================================== mesures
def incertitude(x: np.ndarray, grappes: np.ndarray) -> float:
    from collapsar.regarder.pistes.logique_inversee import incertitude as inc
    return inc(np.asarray(x, np.float64), np.asarray(grappes))


def mois_periode(periode: str, dec_ns: np.ndarray) -> float:
    de_ns, a_ns = _periode_ns(periode)
    if not len(dec_ns):
        return float("nan")
    return (a_ns - max(de_ns, int(dec_ns.min()))) / MOIS_NS


def bloc(z: dict, mois: float, suf: str = "", masque=None) -> dict:
    exe, r, code = z["exe" + suf], z["r" + suf], z["code" + suf]
    ok = exe & (code != JT.FIN) & np.isfinite(r)
    if masque is not None:
        ok &= masque
    n = int(ok.sum())
    if n == 0:
        return {"n": 0}
    rr = r[ok]
    dec = z["dec_f_ns" if suf == "_f" else "dec_ns"][ok]
    inc = incertitude(rr, dec // SEMAINE_NS)
    pos = rr[rr > 0].sum()
    ns_k, ne_k = ("ns" + suf + "_ns", "ne" + suf + "_ns") if suf in ("", "_j") else (None, None)
    out = {"n": n, "trades_mois": n / mois, "gagnants_pct": float((rr > 0).mean() * 100), "r": float(rr.mean()),
           "inc": inc, "force": float(rr.mean() / inc) if inc > 0 else float("nan"), "mediane": float(np.median(rr)),
           "p5": float((rr >= 5).mean() * 100), "p10": float((rr >= 10).mean() * 100),
           "part5": float(rr[rr >= 5].sum() / pos * 100) if pos > 0 else 0.0,
           "part10": float(rr[rr >= 10].sum() / pos * 100) if pos > 0 else 0.0,
           "stop_pct": float((code[ok] == JT.STOP).mean() * 100), "dest_pct": float((code[ok] == JT.DEST).mean() * 100),
           "force_pct": float(np.isin(code[ok], (JT.FORCEE, JT.HORIZON_C)).mean() * 100),
           "achats_pct": float((z["sens"][ok] > 0).mean() * 100)}
    if suf == "":
        out["duree_h"] = float(((z["ns_ns"] - z["ne_ns"])[ok]).mean() / HEURE_NS)
        out["capture_A"] = float((rr * z["risque_A"][ok]).mean())
        out["capture_pct"] = float((rr * z["risque_pct"][ok]).mean())
        out["risque_A"] = float(np.median(z["risque_A"][ok]))
        out["mfe_med"] = float(np.nanmedian(z["mfe"][ok]))
        if "frais_R" in z:
            out["frais_R"] = float(z["frais_R"][ok].mean())
    if suf == "_c":
        out["capture_A"] = float((rr * z["risque_A"][ok]).mean())
        out["capture_pct"] = float((rr * z["risque_pct"][ok]).mean())
    return out


def avance(z: dict, autre: str, moitie: bool) -> dict:
    fin = (z["code"] == JT.FIN) | (z["code" + autre] == JT.FIN)
    a = np.where(z["exe"], np.nan_to_num(z["r"]), 0.0)[~fin]
    b = np.where(z["exe" + autre], np.nan_to_num(z["r" + autre]), 0.0)[~fin]
    d = (a - b) / (2 if moitie else 1)
    inc = incertitude(d, z["dec_ns"][~fin] // SEMAINE_NS)
    return {"avance": float(d.mean()) if len(d) else float("nan"), "inc": inc,
            "force": float(d.mean() / inc) if inc and inc > 0 else float("nan")}


def mesurer_variante(z: dict, periode: str, noms: list) -> dict:
    mois = mois_periode(periode, z["dec_ns"])
    res = {"variante": bloc(z, mois)}
    if "exe_j" in z:
        res.update({"retourne": bloc(z, mois, "_j"), "fausses": bloc(z, mois, "_f"), "plafond2r": bloc(z, mois, "_c"),
                    "avance_jumeau": avance(z, "_j", True), "avance_fausses": avance(z, "_f", False),
                    "avance_plafond": avance(z, "_c", False)})
    grp = np.asarray([groupe(noms[i]) for i in z["marche"]]) if len(z["marche"]) else np.zeros(0, str)
    met = np.isin(np.asarray(noms)[z["marche"]], METAUX) if len(z["marche"]) else np.zeros(0, bool)
    res["groupes"] = {gname: bloc(z, mois, masque=(grp == gname)) for gname in GROUPES[1:]}
    res["groupes"]["métaux"] = bloc(z, mois, masque=met)
    res["unites"] = {u: bloc(z, mois, masque=(z["unite"] == i)) for i, u in enumerate(UNITES_ZONES)}
    return res


def mesurer_gateau(periode: str, noms: list) -> dict:
    g = pd.read_pickle(SORTIE / periode / "gateau.pkl")
    g["groupe"] = g["marche"].map(groupe)
    cols = [c_ for c_ in g.columns if c_.startswith("parfait_")]

    def resume(d):
        r = {"jours": int(len(d)), "amp_pct_moy": float(d["amp_pct"].mean()), "amp_pct_med": float(d["amp_pct"].median()),
             "gros_jours_pct": float((d["amp_pct"] >= GROS_JOUR_PCT).mean() * 100), "amp_A": float(d["amp_A"].mean()),
             "net_A": float(d["net_A"].mean()), "A_pct": float(d["A_pct"].mean()), "frais_pct": float(d["frais_pct"].mean())}
        for c_ in cols:
            r[c_] = float(d[c_].mean())
            if c_.endswith("_pct"):
                r[c_ + "_part"] = float(d[c_].sum() / d["amp_pct"].sum() * 100)
        return r
    out = {"groupes": {gn: resume(g if gn == "tous" else g[g["groupe"] == gn]) for gn in GROUPES}}
    out["groupes"]["métaux"] = resume(g[g["marche"].isin(METAUX)])
    out["marches"] = {m_: resume(d) for m_, d in g.groupby("marche")}
    return out


def taux(d: pd.DataFrame) -> tuple[float, float, int]:
    """Taux de succès (résolus seulement) et son incertitude (grappes = semaines)."""
    r = d[d["res"] >= 0]
    if not len(r):
        return float("nan"), float("nan"), 0
    y = (r["res"] == 1).to_numpy(float)
    return float(y.mean()), incertitude(y, r["dec"].to_numpy() // SEMAINE_NS), int(len(r))


def cases_continuation(c: pd.DataFrame) -> list[dict]:
    c = c.copy()
    c["groupe"] = c["marche"].map(groupe)
    out = []
    for (dep, s, g), d0 in c.groupby(["depart", "s", "g"]):
        for gn in GROUPES:
            d = d0 if gn == "tous" else d0[d0["groupe"] == gn]
            if not len(d):
                continue
            p, inc, n = taux(d)
            base = {"depart": dep, "s": s, "g": g, "groupe": gn, "n": n, "p": p, "hasard": s / g,
                    "non_resolus_pct": float((d["res"] < 0).mean() * 100)}
            out.append({**base, "condition": "base"})
            if dep == "hasard":
                continue
            for cond in CONDITIONS:
                if cond == "foule" and gn != "cryptos":
                    continue
                a, b = d[d[cond]], d[~d[cond]]
                pa, ia, na = taux(a)
                pb, ib, nb = taux(b)
                ec = pa - pb
                ii = math.sqrt(ia ** 2 + ib ** 2) if np.isfinite(ia) and np.isfinite(ib) else float("nan")
                out.append({**base, "condition": cond, "p_avec": pa, "n_avec": na, "p_sans": pb, "n_sans": nb,
                            "ecart": ec, "inc": ii, "force": ec / ii if ii and ii > 0 else float("nan")})
            if dep == "zone" and gn == "tous":
                a, b = d[d["rebond"]], d[~d["rebond"]]
                pa, ia, na = taux(a)
                pb, ib, nb = taux(b)
                ii = math.sqrt(ia ** 2 + ib ** 2)
                out.append({**base, "condition": "rebond_contre_cassure", "p_avec": pa, "n_avec": na, "p_sans": pb,
                            "n_sans": nb, "ecart": pa - pb, "inc": ii, "force": (pa - pb) / ii if ii > 0 else float("nan")})
        # zoom métaux (descriptif)
        d = d0[d0["marche"].isin(METAUX)]
        if len(d):
            p, inc, n = taux(d)
            out.append({"depart": dep, "s": s, "g": g, "groupe": "métaux", "n": n, "p": p, "hasard": s / g,
                        "non_resolus_pct": float((d["res"] < 0).mean() * 100), "condition": "base"})
    return out


def cle_case(r: dict) -> str:
    return f"{r['depart']}|{r['s']}|{r['g']}|{r['groupe']}|{r['condition']}"


# ============================================================================================== compte FTMO
def compte_contre_jumeaux(z: dict, risque_pct: float, periode: str, tirages: int = TIRAGES, graine: int = 20261018) -> dict:
    from collapsar.regarder.pistes import logique_inversee as LI
    de_ns, a_ns = _periode_ns(periode)
    if len(z["dec_ns"]):
        d0 = int(z["dec_ns"].min())
        de_ns = max(de_ns, d0 - d0 % JOUR_NS)
    ok = z["exe"] & (z["code"] != JT.FIN)
    reel = LI.compte(z["ne_ns"][ok], z["ns_ns"][ok], z["r"][ok], risque_pct, de_ns, a_ns)
    rng = np.random.default_rng(graine)
    okj = z["exe_j"] & (z["code_j"] != JT.FIN)
    gains, reus, morts = [], [], []
    for _ in range(tirages):
        pile = rng.random(len(ok)) < 0.5
        mr, mj = ok & pile, okj & ~pile
        c = LI.compte(np.r_[z["ne_ns"][mr], z["ne_j_ns"][mj]], np.r_[z["ns_ns"][mr], z["ns_j_ns"][mj]],
                      np.r_[z["r"][mr], z["r_j"][mj]], risque_pct, de_ns, a_ns)
        gains.append(c["gain_mois_pct"])
        reus.append(c["reussis"])
        morts.append(c["morts"])
    gains = np.asarray(gains)
    return {"reel": reel, "jumeaux_gain_mois_moyen": float(gains.mean()), "jumeaux_gain_mois_sd": float(gains.std()),
            "jumeaux_au_moins_aussi_bien_pct": float((gains >= reel["gain_mois_pct"]).mean() * 100),
            "jumeaux_reussis_moyen": float(np.mean(reus)), "jumeaux_morts_moyen": float(np.mean(morts))}


# ============================================================================================== capture actuelle
def capture_actuelle() -> dict:
    """La meilleure piste précédente (logique inversée C1-MS-3R) : capture en A par trade et par jour-marché crypto."""
    from collapsar.regarder.pistes import logique_inversee as LI
    out = {}
    for per in ("selection", "controle"):
        f = LI.SORTIE / per / "C1-MS-3R.npz"
        if not f.exists():
            continue
        z = dict(np.load(f))
        ok = z["exe"] & (z["code"] != JT.FIN) & np.isfinite(z["r"])
        cap = z["r"][ok] * z["risque_A"][ok]
        de_ns, a_ns = LI._periode_ns(per)
        jours = (a_ns - max(de_ns, int(z["dec_ns"].min()))) / JOUR_NS
        out[per] = {"trades": int(ok.sum()), "capture_A_trade": float(cap.mean()), "r": float(z["r"][ok].mean()),
                    "capture_A_jour_marche": float(cap.sum() / (jours * len(R().marches.cryptos_binance)))}
    return out


# ============================================================================================== étapes
def etape(periode: str, dire=print) -> dict:
    if periode == "controle":
        if (SORTIE / "controle.json").exists():
            raise SystemExit("le contrôle a déjà été fait (une seule fois)")
        ch = json.loads((SORTIE / "choix.json").read_text(encoding="utf-8"))
        k = ch["retenue"]
        variantes = [tuple(k.split("-"))]
    else:
        variantes = VARIANTES
    calculer(periode, variantes, True, dire)
    noms = json.loads((SORTIE / periode / "marches.json").read_text(encoding="utf-8"))
    res = {"periode": periode, "date": datetime.now().isoformat(timespec="seconds"), "gateau": mesurer_gateau(periode, noms),
           "variantes": {}}
    for v in variantes:
        f = SORTIE / periode / f"{vid(v)}.npz"
        if f.exists():
            res["variantes"][vid(v)] = mesurer_variante(lire_trades(periode, vid(v)), periode, noms)
    cases = cases_continuation(pd.read_pickle(SORTIE / periode / "continuation.pkl"))
    if periode == "choix":
        elig = [(m_["variante"].get("force", -np.inf), k) for k, m_ in res["variantes"].items()
                if m_["variante"].get("n", 0) >= MIN_TRADES]
        elig = [(f_ if np.isfinite(f_) else -np.inf, k) for f_, k in elig]
        res["retenue"] = max(elig)[1]
        fortes = sorted([r for r in cases if r["condition"] not in ("base",) and np.isfinite(r.get("force", np.nan))
                         and abs(r["force"]) >= FORCE_RETENUE], key=lambda r: -abs(r["force"]))[:RETENUES_MAX]
        res["cases_retenues"] = [cle_case(r) for r in fortes]
        res["cases"] = cases
        dire(f"variante retenue sur <= 2021 : {res['retenue']} ; cases de continuation retenues : {len(fortes)}")
    elif periode == "verification":
        res["cases"] = cases
    else:
        ch = json.loads((SORTIE / "choix.json").read_text(encoding="utf-8"))
        garde = set(ch["cases_retenues"])
        res["cases"] = [r for r in cases if cle_case(r) in garde or r["condition"] in ("base", "rebond_contre_cassure")]
        res["retenue"] = ch["retenue"]
    # compte FTMO de la retenue
    k = res.get("retenue") or json.loads((SORTIE / "choix.json").read_text(encoding="utf-8"))["retenue"]
    if (SORTIE / periode / f"{k}.npz").exists():
        z = lire_trades(periode, k)
        res["comptes"] = {str(rk): compte_contre_jumeaux(z, rk, periode) for rk in RISQUES}
    (SORTIE / f"{periode}.json").write_text(json.dumps(res, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
    return res


def verdict(ch: dict, ve: dict, co: dict) -> str:
    k = ch["retenue"]
    r1 = ch["variantes"][k]["variante"].get("r", np.nan)
    r2 = ve["variantes"][k]["variante"].get("r", np.nan)
    b = co["variantes"][k]["variante"]
    r3, f3 = b.get("r", np.nan), b.get("force", np.nan)
    if r1 > 0 and r2 > 0 and r3 > 0 and f3 >= SEUIL:
        return "PROUVÉ"
    if r1 > 0 and r2 > 0 and r3 > 0 and f3 > 2:
        return "PROMETTEUR (non prouvé)"
    if r1 > 0 and r2 > 0 and r3 > 0:
        return "positif mais trop faible (non)"
    return "non"


# ============================================================================================== rapport
def _f(x, n=3, signe=True):
    if x is None or (isinstance(x, float) and not np.isfinite(x)):
        return "—"
    return f"{x:+.{n}f}" if signe else f"{x:.{n}f}"


def _lire(nom):
    f = SORTIE / f"{nom}.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else None


ENT_V = ("| variante | trades | trades / mois | gagnants | R moyen ± incertitude (force) ; frais estimés en R | médiane | >= 5R / >= 10R "
         "(part des gains) | durée moy. | capture / trade (A ; % prix) | jumeau : avance (force) | fausses zones : R ; avance "
         "(force) | plafonnée 2R : R ; avance (force) |\n|---|---|---|---|---|---|---|---|---|---|---|---|")


def ligne_v(k: str, m: dict) -> str:
    b = m["variante"]
    if b.get("n", 0) == 0:
        return f"| {k} | 0 | — | — | — | — | — | — | — | — | — | — |"
    fr = f" ; frais ≈ {b['frais_R']:.3f}" if "frais_R" in b else ""
    s = (f"| {k} | {b['n']} | {b['trades_mois']:.1f} | {b['gagnants_pct']:.0f} % | {_f(b['r'])} ± {_f(b['inc'], 3, False)} "
         f"({_f(b['force'], 1)}){fr} | {_f(b['mediane'])} | {b['p5']:.1f} % / {b['p10']:.1f} % ({b['part5']:.0f} % / "
         f"{b['part10']:.0f} %) | {b['duree_h']:.0f} h | {_f(b['capture_A'])} ; {_f(b['capture_pct'], 3)} % |")
    if "avance_jumeau" in m:
        aj, af, ac = m["avance_jumeau"], m["avance_fausses"], m["avance_plafond"]
        s += (f" {_f(aj['avance'])} ({_f(aj['force'], 1)}) | {_f(m['fausses'].get('r'))} ; {_f(af['avance'])} "
              f"({_f(af['force'], 1)}) | {_f(m['plafond2r'].get('r'))} ; {_f(ac['avance'])} ({_f(ac['force'], 1)}) |")
    else:
        s += " — | — | — |"
    return s


def lignes_gateau(g: dict) -> list[str]:
    L = ["| groupe | jours | amplitude moy. / médiane | jours >= 3 % | amplitude en A | net du jour en A | trader parfait "
         "25 % M15 : % ; A ; part de l'amplitude | parfait 50 % M15 | parfait 25 % H1 | parfait 50 % H1 | parfait 25 % "
         "tenu jusqu'à la clôture (repère ajouté) | frais aller-retour |",
         "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for gn in list(GROUPES) + ["métaux"]:
        r = g["groupes"][gn]
        p = lambda u, x: (f"{r[f'parfait_{u}_{x}_pct']:+.2f} % ; {r[f'parfait_{u}_{x}_A']:+.2f} A ; "
                          f"{r[f'parfait_{u}_{x}_pct_part']:.0f} %") if f"parfait_{u}_{x}_pct" in r else "—"
        L.append(f"| {NOM_G[gn]} | {r['jours']} | {r['amp_pct_moy']:.2f} % / {r['amp_pct_med']:.2f} % | "
                 f"{r['gros_jours_pct']:.0f} % | {r['amp_A']:.2f} | {r['net_A']:.2f} | {p('M15', 25)} | {p('M15', 50)} | "
                 f"{p('H1', 25)} | {p('H1', 50)} | {p('tenir', 25)} | {r['frais_pct']:.3f} % |")
    return L


def lignes_cases(cases: list, filtre=None) -> list[str]:
    L = ["| départ | course | groupe | condition | taux base (hasard) | avec / sans la condition | écart (force) | "
         "cas avec / sans |", "|---|---|---|---|---|---|---|---|"]
    base = {(r["depart"], r["s"], r["g"], r["groupe"]): r for r in cases if r["condition"] == "base"}
    for r in cases:
        if r["condition"] == "base" or (filtre and not filtre(r)):
            continue
        b = base.get((r["depart"], r["s"], r["g"], r["groupe"]), {})
        nomc = "rebond contre cassure" if r["condition"] == "rebond_contre_cassure" else r["condition"]
        L.append(f"| {r['depart']} | {r['s']:g} -> {r['g']:g} A | {r['groupe']} | {nomc} | {b.get('p', np.nan) * 100:.1f} % "
                 f"({r['hasard'] * 100:.0f} %) | {r['p_avec'] * 100:.1f} % / {r['p_sans'] * 100:.1f} % | "
                 f"{r['ecart'] * 100:+.1f} pts ({_f(r['force'], 1)}) | {r['n_avec']} / {r['n_sans']} |")
    return L


def lignes_base(cases: list) -> list[str]:
    L = ["| départ | course | " + " | ".join(NOM_G[g] for g in list(GROUPES) + ["métaux"]) + " | hasard pur |",
         "|---|---|" + "---|" * (len(GROUPES) + 2)]
    base = {(r["depart"], r["s"], r["g"], r["groupe"]): r for r in cases if r["condition"] == "base"}
    for dep in ("jour", "zone", "hasard"):
        for s, g in COURSES:
            cells = []
            for gn in list(GROUPES) + ["métaux"]:
                b = base.get((dep, s, g, gn))
                cells.append(f"{b['p'] * 100:.1f} % ({b['n']} ; {b['non_resolus_pct']:.0f} % nr)" if b else "—")
            nomd = "au hasard (repère ajouté)" if dep == "hasard" else dep
            L.append(f"| {nomd} | {s:g} -> {g:g} A | " + " | ".join(cells) + f" | {s / g * 100:.0f} % |")
    return L


def lignes_compte(c: dict) -> list[str]:
    L = ["| risque / trade | gain / mois | baisse max | challenges : réussis / morts (terminés / départs) | jours médians "
         f"| positions en même temps (max) | {TIRAGES} jumeaux : gain / mois | jumeaux au moins aussi bons | jumeaux : "
         "réussis / morts |", "|---|---|---|---|---|---|---|---|---|"]
    for rk, x in c.items():
        r = x["reel"]
        L.append(f"| {rk} % | {r['gain_mois_pct']:+.2f} % | {r['baisse_max_pct']:.1f} % | {r['reussis']} / {r['morts']} "
                 f"({r['termines']} / {r['departs']}) | {_f(r['jours_median_termine'], 0, False)} | "
                 f"{r['positions_simultanees_max']} | {x['jumeaux_gain_mois_moyen']:+.2f} % ± {x['jumeaux_gain_mois_sd']:.2f} | "
                 f"{x['jumeaux_au_moins_aussi_bien_pct']:.0f} % | {x['jumeaux_reussis_moyen']:.1f} / {x['jumeaux_morts_moyen']:.1f} |")
    return L


def ecrire_rapport():
    ch, ve, co = _lire("choix"), _lire("verification"), _lire("controle")
    L = [f"# HYPERNOVA — LES MOUVEMENTS DU JOUR : ses zones, rebond ou cassure, et on LAISSE COURIR (rapport du "
         f"{datetime.now():%d/%m/%Y %H:%M})", ""]
    L.append("Mesure SANS IA. Trades joués sur le vrai chemin du prix par le moteur de l'arbre (frais FTMO du 16/10 dont "
             "la commission crypto, glissement du stop, nuits, bougie d'exécution au pire, fermeture avant une pause > 2 h) "
             "avec un STOP SUIVEUR et AUCUN plafond. R = résultat en multiples du risque, frais compris. A = agitation "
             "(moyenne plus haut - plus bas des 14 derniers jours). Force = moyenne / incertitude (grappes = semaines, "
             f"tous marchés ensemble). N = {N_TOTAL} cases (dont {N_DEJA} déjà jugées) -> seuil de preuve = {SEUIL:.2f}.\n")
    f_c = SORTIE / "conclusion.md"
    if f_c.exists():
        L.append(f_c.read_text(encoding="utf-8").strip() + "\n")
    # 1. gâteau
    L.append("## 1. La taille du gâteau\n")
    for nom_p, r in (("choix", ch), ("verification", ve), ("controle", co)):
        if r:
            L.append(f"### {NOM_P[nom_p]}\n")
            L += lignes_gateau(r["gateau"])
            L.append("")
    cap = capture_actuelle()
    if cap:
        L.append("Notre capture actuelle (meilleure piste précédente, logique inversée C1-MS-3R, cryptos) : " + " ; ".join(
            f"{k} : {v['trades']} trades, {v['capture_A_trade']:+.3f} A par trade, {v['capture_A_jour_marche']:+.4f} A "
            "par jour-marché" for k, v in cap.items()) + ".\n")
    # 2. continuation
    for nom_p, r in (("choix", ch), ("verification", ve), ("controle", co)):
        if not r:
            continue
        L.append(f"## 2. Continuation — {NOM_P[nom_p]}\n")
        L.append("Taux de succès (objectif avant retour au départ, cas résolus) ; entre parenthèses le nombre de cas et la "
                 "part « nr » non résolue en 5 jours (exclue). Le « hasard pur » s / objectif ne tient pas compte de "
                 "l'horizon de 5 jours (qui exclut surtout les longues courses) : le vrai repère est la ligne « au "
                 "hasard » (même course partant d'une bougie tirée au hasard, ajoutée après le plan, descriptive).\n")
        L += lignes_base(r["cases"])
        L.append("")
        if nom_p == "choix":
            L.append(f"Cases retenues (|force| >= {FORCE_RETENUE:g}, au plus {RETENUES_MAX}) : "
                     + (", ".join(ch["cases_retenues"]) or "aucune") + "\n")
        garde = set(ch["cases_retenues"]) if ch else set()
        L += lignes_cases(r["cases"], (lambda x_: cle_case(x_) in garde or x_["condition"] == "rebond_contre_cassure")
                          if nom_p != "choix" else (lambda x_: x_["groupe"] == "tous" or cle_case(x_) in garde))
        L.append("")
    # 3. trades
    if ch:
        k = ch["retenue"]
        if co and ve:
            L.append(f"## 3. Contrôle 01/2024 -> 09/2025 (une seule fois) : {k} — verdict : **{verdict(ch, ve, co)}**\n")
            L.append(ENT_V)
            for nom_p, r in (("choix", ch), ("verification", ve), ("controle", co)):
                L.append(ligne_v(f"{k} {NOM_P[nom_p]}", r["variantes"][k]))
            L.append("")
            L.append("Par groupe et par unité de zone (contrôle) :\n")
            L.append(ENT_V)
            m_ = co["variantes"][k]
            for gn, b in m_["groupes"].items():
                L.append(ligne_v(f"{k} — {NOM_G.get(gn, gn)}", {"variante": b}))
            for u, b in m_["unites"].items():
                L.append(ligne_v(f"{k} — zones {u}", {"variante": b}))
            L.append("")
        for nom_p, r in (("choix", ch), ("verification", ve), ("controle", co)):
            if r and "comptes" in r:
                L.append(f"### Compte FTMO 100 000 $ de {k} — {NOM_P[nom_p]} (un départ tous les 7 jours, +10 % / -5 % "
                         "par jour / -10 % au total)\n")
                L += lignes_compte(r["comptes"])
                L.append("")
        for nom_p, r in (("choix", ch), ("verification", ve)):
            if not r:
                continue
            L.append(f"## 3. Les {len(VARIANTES)} variantes — {NOM_P[nom_p]}" + (f" : retenue **{k}**" if nom_p == "choix" else "") + "\n")
            L.append(ENT_V)
            for v in VARIANTES:
                if vid(v) in r["variantes"]:
                    L.append(ligne_v(vid(v), r["variantes"][vid(v)]))
            L.append("")
            L.append("Par groupe (variante seule) :\n")
            L.append("| variante | " + " | ".join(NOM_G[g] for g in list(GROUPES[1:]) + ["métaux"]) + " |")
            L.append("|---|" + "---|" * len(GROUPES))
            for v in VARIANTES:
                m_ = r["variantes"].get(vid(v))
                if not m_:
                    continue
                cells = [f"{b['r']:+.3f} ({b['n']}, force {_f(b['force'], 1)})" if b.get("n") else "—"
                         for b in (m_["groupes"][g] for g in list(GROUPES[1:]) + ["métaux"])]
                L.append(f"| {vid(v)} | " + " | ".join(cells) + " |")
            L.append("")
    # gâteau par marché (choix)
    if ch:
        L.append("## Annexe — gâteau par marché (<= 2021)\n")
        L.append("| marché | jours | amplitude moy. | jours >= 3 % | net en A | parfait 25 % M15 (% ; part) |")
        L.append("|---|---|---|---|---|---|")
        for m_, r in ch["gateau"]["marches"].items():
            L.append(f"| {m_} | {r['jours']} | {r['amp_pct_moy']:.2f} % | {r['gros_jours_pct']:.0f} % | {r['net_A']:.2f} | "
                     f"{r['parfait_M15_25_pct']:+.2f} % ; {r['parfait_M15_25_pct_part']:.0f} % |")
        L.append("")
    f_plan = SORTIE / "plan_fige.md"
    if f_plan.exists():
        L.append(f_plan.read_text(encoding="utf-8").replace("# LES MOUVEMENTS", "## LES MOUVEMENTS").replace("\n## ", "\n### "))
    (SORTIE / "rapport.md").write_text("\n".join(L), encoding="utf-8")


def dire_(t):
    print(f"[{datetime.now():%d/%m %H:%M:%S}] {t}", flush=True)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("quoi", choices=["plan", "choix", "verification", "controle", "rapport"])
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
    if a.quoi in ("choix", "verification", "controle"):
        if a.quoi != "choix" and not (SORTIE / "choix.json").exists():
            raise SystemExit("faire d'abord le choix sur <= 2021")
        if a.quoi == "controle" and not (SORTIE / "verification.json").exists():
            raise SystemExit("faire d'abord la vérification 2022-2023")
        etape(a.quoi, dire_)
    ecrire_rapport()
    dire_("rapport écrit : " + str(SORTIE / "rapport.md"))


if __name__ == "__main__":
    main()
