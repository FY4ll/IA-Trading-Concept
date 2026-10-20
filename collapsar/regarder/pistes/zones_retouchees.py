"""PISTE « zones_retouchees » : la stratégie DU CHEF DE PROJET sur des zones DÉJÀ TOUCHÉES (16/10/2026).

CAHIER DES CHARGES ÉCRIT AVANT TOUT RÉSULTAT (rien n'est réglé après coup ; aucun calcul de cette piste n'a tourné avant
l'écriture de cet en-tête, précisions du chef de projet comprises).

Paroles du chef de projet (mot pour mot)
- « cette stratégie se base déjà sur des zones qui ont DÉJÀ ÉTÉ TOUCHÉES » (le code V1 entre au 1er contact).
- « s'il a rebondi au MILIEU une 1re fois, il y a plus de chances qu'il rebondisse une 2e fois au milieu ; c'est un jeu
  de probabilité ».
- « regarder aussi s'il a rebondi juste à L'ENTRÉE de la zone : ça peut être un moyen de savoir si la zone est valide
  et d'entrer ; pas forcément qu'au milieu ».
- « il ne faut pas oublier le SYSTÈME : tu commences en JOURNALIER, tu repères des GROSSES zones, tu viens PEAUFINER en
  plus petites zones. C'est ça qui est important. »

Ce qui ne change pas (V1 = « Gigogne H4 stop A plancher 0.2 », code du laboratoire appelé tel quel ou copié à
l'identique, contrôlé) : zones zones supply and demand (smc/nono.zones_nono, version prudente), effacement à la 1re clôture de la plus petite
unité au-delà du milieu, descente gigogne (smc/gigogne.entrees : à chaque unité plus petite, la zone vivante du même sens
qui chevauche la dernière retenue ; au moins 2 zones), entrée par ordre limite au MILIEU de la plus petite zone (200
bougies de son unité au plus, avant l'effacement de la zone de départ et de la zone d'entrée), stop A = bord opposé de
la plus petite zone ± 0,2 ATR de son unité avec un minimum de 0,2 x ATR journalier (dernier jour complet), sorties par
tiers (2 R / sommet H1 / bord de la plus proche zone opposée de l'unité de DÉPART, vivante ; trade ignoré si pas de TP3
au-delà de 2 R), 30 jours max ; sortie : copie de chef_crypto.trade_tiers_heures (= nono.trade_nono stop A + heures de
sortie). Un trade par zone de départ et par règle.

LE SYSTÈME (précision essentielle, en tête du rapport) : la condition « déjà touchée / a réagi / à l'entrée / au
milieu » porte sur la GROSSE zone, celle de DÉPART ; l'entrée se fait ensuite dans la petite zone trouvée en descendant
(D1 -> H4 -> H1 -> M30 -> M15 (-> M5 -> M3 pour les 4 marchés à la minute)), exactement comme gigogne.entrees, à
l'instant du contact retenu. Deux départs comparés : JOURNALIER (D1) et H4.

Définitions (zone de départ X, sur la plus petite unité du groupe = « graphique » : M3 à la minute, M15 sinon)
- Contact = 1re bougie du graphique dont la mèche atteint le bord proche (bord haut d'une demande, bas d'une offre).
- Demi-tour / réaction après un contact = une bougie SUIVANTE atteint le bord proche + une hauteur de zone (s'éloigne
  d'une hauteur au-delà du bord d'entrée), avant l'effacement (clôture au-delà du milieu = zone effacée, plus rien).
- Contact suivant = 1re bougie après la bougie de réaction qui retouche le bord proche.
- Profondeur du demi-tour = pénétration maximale (bord proche - plus bas, pour une demande) / hauteur de zone, sur les
  bougies du contact jusqu'à la bougie AVANT la réaction (0 = bord d'entrée, 0,5 = milieu, 1 = bord opposé). Classes :
  « entrée » < 0,35 ; « milieu » 0,35-0,65 ; « profond » > 0,65.

Règles (liste FERMÉE), pour chaque départ D1 et H4, condition sur la zone de départ :
- V1 : 1er contact (le code actuel).
- R2 : pas de trade au 1er contact ; 2e contact après une 1re réaction ; descente et entrée au milieu à ce 2e contact.
- R3 : idem au 3e contact (zone touchée 2 fois, 2 réactions).
- R2M : R2 seulement si le 1er demi-tour est « milieu » (0,35-0,65) ; entrée au milieu (de la plus petite zone).
- R2E : R2 seulement si le 1er demi-tour est « entrée » (< 0,35) ; entrée au BORD D'ENTRÉE de la plus petite zone (bord
  haut pour un achat), stop A inchangé (même prix de stop ; 1 R = entrée -> stop, plancher 0,2 ATR jour inchangé).
- R2E-milieu : même condition que R2E, entrée au milieu.
  Si au contact retenu la descente ne trouve pas de petite zone, ou si le prix n'atteint pas le prix d'entrée dans les
  200 bougies : pas de trade pour cette zone (on ne passe pas au contact suivant).
Version de COMPARAISON, condition sur la PETITE zone d'entrée (filtre des trades V1, même départ) : à la minute du
remplissage d'un trade V1, on compte les contacts déjà commencés de sa petite zone d'entrée Y (mêmes définitions, sur le
graphique, depuis la confirmation de Y jusqu'à son effacement) : p-V1 = Y jamais touchée avant (contact n° 1) ; p-R2 =
contact n° 2 ; p-R3 = n° 3 ; p-R2M = n° 2 et 1er demi-tour de Y au milieu ; p-R2E = n° 2 et 1er demi-tour de Y à
l'entrée (entrée au milieu, comme V1).
Total : 3 groupes x 2 départs x (6 + 5) = 66 variantes -> seuil de preuve max(3, racine(2 ln 66)) = 3 (à l'échelle de
tout le laboratoire SMC + cette piste : racine(2 ln 540) = 3,55, rappelé dans le rapport).

Marchés, données, frais (obligatoires)
- (a) 19 cryptos FTMO (liste de chef_compte_ftmo : BTC, ETH, ADA, DOT, LTC, XRP, DOGE, XMR, BCH, BNB, SOL, AVAX, LINK,
  NEAR, ALGO, ETC, XLM, UNI, VET), bougies Binance 15 min, filtre commun du LISEZMOI (chef_crypto.charger_autre tel
  quel). Frais FTMO crypto = (commission 0,0325 %/côté x 2 + écart 0,03 % ; BTC 0,0015 %) x MARGE_PRUDENCE (1,25 jusqu'au 16/10, 1 depuis l'audit) (chef_compte_ftmo.frais).
  Nuits 30 %/an des deux côtés, / 360 par minuit serveur, vendredi x 3, samedi et dimanche 0 (chef_crypto.nuits).
- (b) or, Nasdaq, S&P 500, euro-dollar à la minute (nono._construire_minutes, échelle D1 ... M3).
- (c) les 47 marchés de dm.liste_marches() en bougies de 15 min (multi.construire_m15, échelle D1 ... M15).
  (b) et (c) : frais = collapsar.mains.frais_ftmo.frais(sym, prix d'entrée) (écart FTMO relevé, x MARGE_PRUDENCE (1,25 jusqu'au 16/10, 1 depuis l'audit) compris) avec la
  convention de V1 (entrée limite = demi-frais x facteur d'ouverture, objectif = demi-frais, stop = frais entiers) ;
  nuits = taux_nuit(fiche(sym), heure d'entrée) du sens joué / 360 x nombre de minuits serveur franchis (nuits
  calendaires : le week-end compte 3 nuits, ce qui revient à 7 nuits par semaine), tiers par tiers. 16/10 au soir
  (audit, défaut 11) : nuits FTMO = nuits_ftmo (triple le mercredi pour devises / métaux, le vendredi pour indices /
  énergies, samedi et dimanche 0 ; toujours 7 par semaine).
- Le jumeau (sens inverse, même entrée, même stop et mêmes objectifs en miroir) paie ses propres frais et nuits.
- Pour le contrôle de fidélité seulement : R « frais du laboratoire, sans nuit » (frais des fiches de bougies.py).

Mesures, par groupe x départ x règle, par période (avant 2022, 2022-2023, 2024-2026, toutes années ; date d'entrée,
heure de New York) : trades, % gagnants, gain moyen d'un gagnant (R), perte moyenne d'un perdant (R), MOYENNE de tous les
trades en R (après frais et nuits), R médian, trades >= 10 R, force contre le jumeau (moyenne de (R - R_inverse)/2 /
écart type x racine(n)) ; compte en information (chef_crypto.note : risque 0,5 % du compte par trade, cryptos plafonnées
au levier 1:1 = min(stop en part du prix, 0,5 %)) : %/mois, baisse max, pire jour, challenges FTMO (bande_bruit.challenge,
départ tous les 10 jours) contre 20 jumeaux — pour les règles « grosse zone » seulement (calcul trop long pour les 66).
En plus : (i) MÊMES ZONES : sur les zones de départ qui ont à la fois un trade V1 et un trade R2 (ou R3), R moyen de
chacun (lecture, pas une règle : savoir qu'une zone sera retouchée n'est pas connu au 1er contact) ; (ii) répartition
de la profondeur du 1er demi-tour des trades R2 (entrée / milieu / profond) et R moyen du trade au 2e contact pour
chaque classe.

MESURE DIRECTE DES PROBABILITÉS (indépendante des gains), sur les zones de DÉPART (D1 et H4), par groupe :
- toutes les zones zones supply and demand de départ (y compris celles effacées ensuite : pas de biais de survie), suivies sur le
  graphique pendant 200 bougies de leur unité après leur confirmation (D1 : 200 jours ; H4 : ~33 jours) ;
- ici, définition du coordinateur : réaction = le prix s'éloigne d'une hauteur au-delà du bord d'entrée AVANT de
  clôturer au-delà du bord OPPOSÉ (une clôture au-delà du bord opposé = zone cassée, fin du suivi) ; contacts et
  profondeur comme plus haut ;
- P(réaction au 1er contact | 1er contact) ; P(2e contact | 1re réaction) ; P(réaction au 2e contact | 1re réaction
  quelconque / au milieu / à l'entrée / profonde) ; P(le 2e demi-tour est aussi au milieu | 1er au milieu et 2e
  réaction) ; P(2e aussi à l'entrée | 1er à l'entrée et 2e réaction) ; répartition de la profondeur du 1er demi-tour ;
- TÉMOIN HASARD (comme zones_milieu.py) : pour chaque vraie zone, une fausse zone de même hauteur, même sens, à la même
  distance du prix (clôture de confirmation -> bord proche), posée à une bougie de son unité tirée au hasard (graine
  fixée par marché et départ), suivie de la même façon. Écart vraie - témoin avec un écart type binomial (z).

Juge (règles écrites d'avance)
- Années : V1 a DÉJÀ été évaluée sur toutes les années (or / indices / euro et 47 marchés : choix 2015-2021,
  vérification 2022-2023, période cachée 2024-2026 ouverte le 15/10 (avenant 3) ; cryptos : 2017-2026 dans chef_crypto
  et chef_compte_ftmo). R2, R3, R2M, R2E, R2E-milieu, les versions « petite zone » et le départ D1 avec plancher n'ont
  JAMAIS été calculés : toutes leurs années sont neuves pour ces règles, MAIS ces règles ont été dites par le chef de
  projet après avoir vu les résultats de V1 : il n'y a plus de période vraiment cachée pour cette famille.
- Pas de conclusion sur moins de 30 trades (nombre exact donné).
- « Meilleure que V1 » (même groupe, même départ) : R moyen plus haut que V1 sur au moins 2 des 3 périodes ET sur toutes
  les années. « Tient debout » : R moyen > 0 après frais et nuits sur chacune des 3 périodes et force > 0 (toutes
  années). « Prouvée » : tient debout et force (toutes années) >= 3.
- Probabilités : « propre à ses zones » si l'écart vraie - témoin a un z >= 3.

Contrôles de fidélité (avant de lire un résultat) : (1) au 1er contact, mes entrées = gigogne.entrees à l'identique
(départs D1 et H4) ; (2) V1 H4 « frais du laboratoire, sans nuit » = vie/smc/strategie_chef_trades_REPRISE_controle.csv
(or / indices / euro, 47 marchés) ; (3) V1 H4 crypto = R_A de chef_compte_ftmo (cache).

AVENANT 1 — DIAGNOSTIC DE FRÉQUENCE (16/10/2026, écrit AVANT de compter ; aucun gain regardé)
Information du chef de projet : « en général j'ai facilement 4-5 trades par semaine sur plusieurs indices ».
- Indices : US500 (USA500IDXUSD), US100 (USATECHIDXUSD), US30 (USA30IDXUSD), GER40 (DEUIDXEUR), bougies 15 min,
  échelle D1 -> M15 ; en plus US500 et US100 à la minute (échelle D1 -> M3). Fenêtre : 2024-01-01 -> fin des données.
- Par semaine et par unité de départ (D1, H4, H1, M30) : zones zones supply and demand créées, zones vivantes (moyenne au début de chaque
  semaine), 1ers contacts, chaînes gigognes complètes au contact (au moins 2 zones), remplissages au milieu de la
  petite zone, trades V1 (TP3 >= 2 R) ; et l'étape où chaque zone est perdue : jamais touchée (encore vivante / pas
  revenue), pas de zone dans la zone, milieu jamais atteint (coupé par la fenêtre de 200 bougies ou par un effacement),
  pas d'objectif 3 au-delà de 2 R. En plus : combien de figures « bougie opposée + FVG » existent, et combien
  survivent à l'exigence de cassure (BOS) sur les bougies i-4 / i-5 ; part des contacts où la bougie de contact efface
  déjà la zone (clôture au-delà du milieu).
- Ensuite seulement (avenant 2, écrit après ce comptage et AVANT tout gain) : une liste fermée de détections plus
  fréquentes, choisie UNIQUEMENT sur le nombre de trades par semaine (cible 4-5 sur les 4 indices réunis).

AVENANT 2 — DÉTECTION CALÉE SUR LA FRÉQUENCE (16/10/2026, écrit après le comptage de l'avenant 1, qui ne contient
AUCUN gain, et AVANT de regarder un gain). Constat du comptage (4 indices, 15 min, 2024-2026, trades V1 par semaine,
les 4 réunis) : départ D1 0,05 ; H4 0,30 ; H1 1,1 ; M30 2,1. Pertes principales : « pas de zone dans la zone » (~80 %
des 1ers contacts au départ H4) et contact dont la bougie efface déjà la zone (~60 %). Ajouté au diagnostic : délai
entre la confirmation et le 1er contact, part des zones dont la clôture de confirmation est déjà dans la zone.
Liste FERMÉE de détections (règles V1 inchangées sauf le point dit) :
- F1 : départ M30 ;
- F2 : départ H1, chaîne d'au moins 1 zone (sans petite zone dedans : entrée au milieu de la zone H1 elle-même, stop
  derrière elle) ;
- F3 : départ H4, chaîne d'au moins 1 zone ;
- F4 : départ H1, effacement de toutes les zones à la clôture au-delà du BORD OPPOSÉ (au lieu du milieu) ;
- F5 : départ H4, effacement au bord opposé ;
- F6 : départ M30, effacement au bord opposé.
CHOIX MÉCANIQUE : celle dont le nombre de trades V1 par semaine (4 indices réunis, 15 min, 2024-2026) est le plus
proche de 4,5 ; à égalité (écart < 0,3), celle dont l'unité de départ est la plus grande. Seul ce NOMBRE est regardé.
Ensuite, la détection choisie est calculée sur les 3 groupes avec V1 / R2 / R3 / R2M / R2E / R2E-milieu (condition
sur sa zone de départ), mêmes frais, mêmes mesures, mêmes probabilités ; ses résultats sont donnés à part (6 variantes
de plus par groupe : seuil inchangé à 3).

Résultat du choix (nombres seulement, choix_frequence.json) : F4 (départ H1, effacement au bord opposé) = 3,57 trades
V1 par semaine sur les 4 indices -> RETENUE (F6 5,78 ; F2 8,55 ; F1 2,14 ; F3 2,15 ; F5 1,04).

AVENANT 3 — « R2 PAR UNITÉ » (16/10/2026, écrit AVANT tout résultat de ces règles). Paroles du chef de projet :
« chaque zone, dans n'importe quelle unité, a sa valeur ; les zones H1 aussi ont une grande valeur ; il faut filtrer
pour trouver des zones dans des zones, mais si une H1 a résisté une 1re fois, elle résistera une 2e fois ».
- Pour CHAQUE unité U séparément (D1, H4, H1, M30, M15) : zones zones supply and demand de U (effacement zones supply and demand au milieu, sur le
  graphique) ; entrée par ordre limite au MILIEU de la zone U elle-même (pas de descente), au contact n (1 = repère,
  2 = zone qui a déjà résisté une fois : 1er contact puis réaction d'une hauteur, puis retour au bord proche) ; 200
  bougies de U au plus pour le remplissage ; stop A derrière la zone U (± 0,2 ATR de U, minimum 0,2 ATR journalier) ;
  TP1 2 R, TP2 sommet H1, TP3 plus proche zone OPPOSÉE de U vivante (>= 2 R, sinon pas de trade), 30 jours max ; mêmes
  frais, nuits, jumeau.
- « avec zone autour » : au moment du contact, une zone zones supply and demand vivante du même sens d'une unité PLUS GRANDE chevauche la
  zone U (sans objet pour D1) ; « sans » : toutes les zones de U.
- Variantes : 5 unités x contacts {1, 2} x {sans, avec} - D1 avec = 18 par groupe (54).
- Probabilités par unité (mêmes définitions que plus haut : bord opposé, 200 bougies de U, témoin hasard).
- Total des variantes de la piste : 66 + 18 (F4) + 54 = 138 -> seuil de preuve racine(2 ln 138) = 3,14 (laboratoire
  entier : racine(2 ln 612) = 3,58).

AVENANT 4 : traduction fidèle nono_v7 -> collapsar/regarder/pistes/zones_retouchees_v7.py (cahier dans son en-tête).

AVENANT 5 — CORRECTION DES HEURES (16/10/2026, audit indépendant : pandas 3 lisait les heures en microsecondes, le
laboratoire compte en nanosecondes ; corrigé à la source dans bougies.py / marches.py / histdata.py). TOUS les calculs
de cette piste faits avant la correction (comptages de fréquence, choix F4 / F2, trades, résultats) sont archivés dans
vie/pistes/zones_retouchees/avant_correction_heures/ et REFAITS entièrement ; les choix de détection (avenant 2 et sa
copie v7) sont refaits avec la MÊME règle mécanique sur les comptages corrigés (nombres seulement). Le rapport donne V1
avant / après correction.

Depuis Test_IA : venv_gpu\\Scripts\\python.exe -u -m collapsar.regarder.pistes.zones_retouchees calculer <crypto|minutes|45>
                 venv_gpu\\Scripts\\python.exe -u -m collapsar.regarder.pistes.zones_retouchees juger
                 venv_gpu\\Scripts\\python.exe -u -m collapsar.regarder.pistes.zones_retouchees frequence
"""
from __future__ import annotations

import gc
import json
import math
import sys
import zlib
from datetime import datetime
from functools import lru_cache

import numpy as np
import pandas as pd
from numba import njit

from collapsar.donnees import marches as dm
from collapsar.mains.fiches import fiche
from collapsar.mains.frais_ftmo import frais as frais_ftmo
from collapsar.mains.nuit import taux_nuit
from collapsar.regarder.pistes import chef_compte_ftmo as CF
from collapsar.regarder.pistes import chef_crypto as CC
from collapsar.regarder.smc import gigogne as G
from collapsar.regarder.smc import noyaux as K
from collapsar.regarder.smc.bougies import MARCHES
from collapsar.regarder.smc.multi import construire_m15
from collapsar.regarder.smc.nono import ATTENTE, TENUE_JOURS, _construire_minutes, zones_nono

VIE = dm.RACINE / "collapsar" / "vie" / "pistes" / "zones_retouchees"
CACHE = VIE / "cache"
FIN = pd.Timestamp("2100-01-01")
JAMAIS = np.iinfo(np.int64).max
JOUR_NS = 86400 * 10 ** 9
H7NS = 7 * 3600 * 10 ** 9
PLANCHER = 0.2
RISQUE = 0.005
DEPARTS = ("D1", "H4")
GROSSE = ("V1", "R2", "R3", "R2M", "R2E", "R2E-milieu")
PETITE = ("p-V1", "p-R2", "p-R3", "p-R2M", "p-R2E")
ENTREE_MAX, MILIEU_MAX = 0.35, 0.65
FENETRE_PROBA = 200
MIN_TRADES = 30
SEUIL = max(3.0, math.sqrt(2 * math.log(138)))
SEUIL_LABO = math.sqrt(2 * math.log(612))
UNITES_PAR = ("D1", "H4", "H1", "M30", "M15")
PERIODES = {"avant 2022": ("2000-01-01", "2022-01-01"), "2022-2023": ("2022-01-01", "2024-01-01"),
            "2024-2026": ("2024-01-01", "2027-01-01"), "tout": ("2000-01-01", "2027-01-01")}
GROUPES = {"crypto": "19 cryptos FTMO (Binance, 15 min)", "minutes": "or, Nasdaq, S&P 500, euro (minutes)",
           "45": "47 marchés (15 min)"}


@lru_cache(maxsize=None)
def _cumul_nuits(jour_triple: int) -> np.ndarray:
    """Cumul des nuits payées : élément k = nuits des minuits serveur situés avant le début du jour k (jours depuis le
    01/01/1970, un jeudi). La nuit du jour `jour_triple` (lundi = 0) compte 3, samedi et dimanche 0, les autres 1 ;
    `jour_triple` = -1 : nuits calendaires (chaque minuit compte 1)."""
    k = np.arange(0, 40000)
    veille = (k - 1 + 3) % 7                             # jour de la semaine de la veille (lundi = 0)
    if jour_triple < 0:
        return np.cumsum(np.ones(len(k)))
    return np.cumsum(np.where(veille == jour_triple, 3.0, np.where(veille >= 5, 0.0, 1.0)))


def jour_triple(sym: str | None) -> int:
    """Jour de la nuit triple chez FTMO (mains/horloge.regle_nuit : mercredi = 2 pour devises / métaux / obligations,
    vendredi = 4 pour indices / énergies / cryptos) ; -1 (calendrier) pour un marché sans règle."""
    if sym is None:
        return -1
    from collapsar.mains.horloge import regle_nuit
    return {1: 2, 2: 4}.get(regle_nuit(fiche(sym)), -1)


def nuits_ftmo(sym: str | None, t_entree_ny, t_sortie_ny) -> np.ndarray:
    """Nuits payées chez FTMO entre deux instants (ns, heure de New York ; minuit serveur = New York + 7 h), avec le
    triple au bon jour (audit du 16/10, défaut 11) ; avant le 16/10 au soir, ce moteur comptait les nuits calendaires
    (week-end = 3 nuits pour tous les marchés)."""
    W = _cumul_nuits(jour_triple(sym))
    a = (np.asarray(t_entree_ny, np.int64) + H7NS) // JOUR_NS
    b = (np.asarray(t_sortie_ny, np.int64) + H7NS) // JOUR_NS
    return W[b] - W[a]


def classe(p: float) -> str:
    if not np.isfinite(p):
        return "aucune"
    return "entrée" if p < ENTREE_MAX else ("milieu" if p <= MILIEU_MAX else "profond")


# ---------------------------------------------------------------- l'histoire d'une zone (contacts, réactions, profondeur)
@njit(cache=True)
def historique(h, l, c, k0, kend, haut, bas, d, nmax, oppose_casse):
    """Contacts du bord proche sur les bougies [k0, kend) : (indices des contacts, indices des réactions, profondeurs,
    cassée). `oppose_casse` : une clôture au-delà du bord opposé arrête le suivi (mesure des probabilités) ; sinon la
    fin `kend` est l'effacement zones supply and demand (déjà calculé)."""
    cont = np.full(nmax, -1, np.int64)
    reac = np.full(nmax, -1, np.int64)
    prof = np.full(nmax, np.nan)
    hauteur = haut - bas
    if hauteur <= 0:
        return cont, reac, prof, False
    proche = haut if d > 0 else bas
    oppose = bas if d > 0 else haut
    cible = proche + d * hauteur
    k = k0
    n = 0
    while n < nmax:
        while k < kend and not ((d > 0 and l[k] <= proche) or (d < 0 and h[k] >= proche)):
            k += 1
        if k >= kend:
            break
        cont[n] = k
        p = 0.0
        reagi = False
        while k < kend:
            if k > cont[n] and ((d > 0 and h[k] >= cible) or (d < 0 and l[k] <= cible)):
                reac[n] = k
                reagi = True
                break
            pen = (proche - l[k]) / hauteur if d > 0 else (h[k] - proche) / hauteur
            if pen > p:
                p = pen
            if oppose_casse and ((d > 0 and c[k] < oppose) or (d < 0 and c[k] > oppose)):
                prof[n] = p
                return cont, reac, prof, True
            k += 1
        prof[n] = p
        if not reagi:
            break
        k += 1
        n += 1
    return cont, reac, prof, False


# ---------------------------------------------------------------- la descente gigogne et l'entrée (copie de gigogne.entrees)
def partage(cons):
    """Les bougies de toutes les unités gardent UNE seule copie des minutes (mémoire)."""
    ref = {}

    def f(u):
        b = cons(u)
        if not ref:
            ref["m"] = (b.mt, b.mo, b.mh, b.ml)
        else:
            b.mt, b.mo, b.mh, b.ml = ref["m"]
        return b
    return f


def preparer(cons, echelle, efface="milieu") -> dict:
    """Copie de gigogne.preparer ; `efface` = "milieu" (zones supply and demand, identique) ou "oppose" (avenant 2 : clôture au-delà du
    bord opposé)."""
    if efface == "milieu":
        return G.preparer(cons, echelle)
    from collapsar.regarder.smc.multi import sommets_confirmes
    from collapsar.regarder.smc.nono import effacement
    B = {u: cons(u) for u in echelle}
    base = B[echelle[-1]]
    h1 = B["H1"]
    s_px, s_cf, s_ty = sommets_confirmes(h1.h, h1.l)
    Z = {}
    for u in echelle:
        b = B[u]
        zh, zb, zm, zs, zc = zones_nono(b.o, b.h, b.l, b.c)
        conf = b.bt[zc] + b.duree
        niveau = np.where(zs > 0, zb, zh)
        Z[u] = (zh, zb, zm, zs, conf, effacement(niveau, zs, conf, base.bt, base.duree, base.c))
    return {"B": B, "Z": Z, "base": base, "echelle": echelle, "sommets": (s_px, s_ty, h1.bt[s_cf] + h1.duree)}


def descente(P, depart, z, t_in, chaine_min=2):
    B, Z, echelle = P["B"], P["Z"], P["echelle"]
    xh, xb, xm, xs, xconf, xfin = Z[depart]
    d = int(xs[z])
    haut, bas, unite, zi, profondeur = xh[z], xb[z], depart, z, 1
    for u in echelle[echelle.index(depart) + 1:]:
        uh, ub, um, us, uconf, ufin = Z[u]
        ok = (us == d) & (uconf <= t_in) & (ufin > t_in) & (ub <= haut) & (uh >= bas)
        if ok.any():
            idx = np.flatnonzero(ok)
            zi = int(idx[np.argmax(uh[idx])]) if d > 0 else int(idx[np.argmin(ub[idx])])
            haut, bas, unite, profondeur = uh[zi], ub[zi], u, profondeur + 1
    if unite == depart:
        return (depart, z, 1) if chaine_min <= 1 else None
    return unite, zi, profondeur


def entree_y(P, depart, z, unite, zi, t_in, bord: bool):
    """Comme gigogne.entrees à partir de t_in ; `bord` : ordre limite au bord d'entrée de la petite zone (R2E)."""
    B, Z = P["B"], P["Z"]
    xh, xb, xm, xs, xconf, xfin = Z[depart]
    d = int(xs[z])
    uh, ub, um, us, uconf, ufin = Z[unite]
    BY = B[unite]
    prix = (uh[zi] if d > 0 else ub[zi]) if bord else um[zi]
    e0 = int(np.searchsorted(BY.bt, t_in))
    limite = min(xfin[z], ufin[zi])
    e1 = min(BY.n, e0 + ATTENTE, int(np.searchsorted(BY.bt, limite)) if limite < JAMAIS else BY.n)
    if e1 <= e0:
        return None
    touche = BY.l[e0:e1] <= prix if d > 0 else BY.h[e0:e1] >= prix
    if not touche.any():
        return None
    i = e0 + int(np.argmax(touche))
    entree = prix if not ((d > 0 and BY.o[i] < prix) or (d < 0 and BY.o[i] > prix)) else BY.o[i]
    loin = ub[zi] if d > 0 else uh[zi]
    risque_zone = (entree - (loin - d * 0.2 * BY.atr[i])) * d
    if risque_zone <= 0:
        return None
    return {"i": i, "entree": entree, "prix_ordre": prix, "risque_zone": risque_zone, "sens": d}


def un_trade(P, depart, unite, e, frais_fn, crypto):
    """Le trade (plancher 0,2 ATR jour, tiers, comme chef_crypto.trades_chef) et son jumeau : R sans nuit (frais FTMO),
    R frais du laboratoire, nuits par tiers. None si pas de TP3 au-delà de 2 R."""
    B, Z = P["B"], P["Z"]
    s_px, s_ty, s_t = P["sommets"]
    BD, BY = B["D1"], B[unite]
    xh, xb, xm, xs, xconf, xfin = Z[depart]
    i, d, entree = e["i"], e["sens"], e["entree"]
    t_e = BY.bt[i]
    jd = int(np.searchsorted(BD.bt, t_e, "right")) - 2
    atr_jour = BD.atr[jd] if jd >= 0 else np.nan
    risque = max(e["risque_zone"], PLANCHER * atr_jour)
    if not np.isfinite(risque):
        return None
    okx = (xs == -d) & (xconf < t_e) & (xfin > t_e)
    dist3 = ((xb if d > 0 else xh)[okx] - entree) * d
    dist3 = dist3[dist3 >= 2 * risque]
    if not len(dist3):
        return None
    d3 = float(dist3.min())
    cand = (s_ty == d) & (s_t <= t_e)
    d2s = (s_px[cand] - entree) * d
    d2s = d2s[(d2s > 2 * risque) & (d2s < d3)]
    d2 = float(d2s.min()) if len(d2s) else (2 * risque + d3) / 2
    f_min, b_min = K._remplissage(BY.o, BY.mt, BY.ml, BY.mh, BY.bt, BY.duree, i, d, e["prix_ordre"])
    tenue = int(TENUE_JOURS * 86400e9 // BY.duree)
    args = (BY.o, BY.h, BY.l, BY.c, BY.bt, BY.duree, BY.mt, BY.mo, BY.mh, BY.ml, i, f_min, b_min)
    fr = float(frais_fn(entree))
    r, cr, so = CC.trade_tiers_heures(*args, d, entree, risque, d2, d3, tenue, fr, BY.facteur[i])
    ri, _, soi = CC.trade_tiers_heures(*args, -d, entree, risque, d2, d3, tenue, fr, BY.facteur[i])
    rl, _, _ = CC.trade_tiers_heures(*args, d, entree, risque, d2, d3, tenue, BY.frais, BY.facteur[i])
    fill = int(BY.mt[f_min])
    if crypto:
        nb, nbi = float(CC.nuits(np.full(3, fill), so).mean()), float(CC.nuits(np.full(3, fill), soi).mean())
    elif P.get("sym") is not None:                    # 16/10 soir : nuit triple au bon jour (FTMO), week-end 0
        nb = float(nuits_ftmo(P["sym"], np.full(3, fill), so).mean())
        nbi = float(nuits_ftmo(P["sym"], np.full(3, fill), soi).mean())
    else:                                             # sans symbole (comptages de fréquence) : nuits calendaires
        j0 = (fill + H7NS) // JOUR_NS
        nb = float(((so + H7NS) // JOUR_NS - j0).mean())
        nbi = float(((soi + H7NS) // JOUR_NS - j0).mean())
    return {"unite": f"{depart}->{unite}", "entree": pd.Timestamp(BY.t[i]), "fill_ny": fill,
            "sortie": pd.Timestamp(int(so.max())), "sens": d, "prix": entree, "risque": risque,
            "stop_frac": risque / entree, "frais": fr, "cout_R": cr, "R_sans_nuit": r, "R_inverse_sans_nuit": ri,
            "R_labo": rl, "nuits": nb, "nuits_inv": nbi, "tp3_R": d3 / risque}


# ---------------------------------------------------------------- un marché
def probas_unite(nom, P, U) -> list[dict]:
    """Mesure directe des probabilités sur les zones de l'unité U et leurs témoins hasard (bord opposé, 200 bougies)."""
    B, Z, base = P["B"], P["Z"], P["base"]
    BX = B[U]
    xh, xb, xm, xs, xconf, xfin = Z[U]
    _, _, _, _, xc = zones_nono(BX.o, BX.h, BX.l, BX.c)
    out = []
    rng = np.random.default_rng(zlib.crc32(f"{nom}|{U}".encode()))
    for z in range(len(xs)):
        d, haut, bas = int(xs[z]), float(xh[z]), float(xb[z])
        hauteur = haut - bas
        if hauteur <= 0 or BX.n < FENETRE_PROBA + 60:
            continue
        j0 = int(rng.integers(50, BX.n - FENETRE_PROBA - 1))
        ecart = BX.c[xc[z]] - (haut if d > 0 else bas)
        p_t = BX.c[j0] - ecart
        h_t, b_t = (p_t, p_t - hauteur) if d > 0 else (p_t + hauteur, p_t)
        for genre, conf, hh, bb_ in (("zone", xconf[z], haut, bas), ("témoin", BX.bt[j0] + BX.duree, h_t, b_t)):
            k0 = int(np.searchsorted(base.bt, conf))
            kend = int(np.searchsorted(base.bt, conf + FENETRE_PROBA * BX.duree))
            cont, reac, prof, casse = historique(base.h, base.l, base.c, k0, kend, hh, bb_, d, 2, True)
            if cont[0] < 0:
                continue
            out.append({"marche": nom, "depart": U, "genre": genre, "annee": pd.Timestamp(int(base.bt[cont[0]])).year,
                        "reac1": bool(reac[0] >= 0), "prof1": prof[0], "contact2": bool(cont[1] >= 0),
                        "reac2": bool(reac[1] >= 0), "prof2": prof[1]})
    return out


def trades_marche(nom, cons, echelle, sym_fiche, frais_fn, crypto, departs=DEPARTS, chaine_min=2, efface="milieu",
                  par_unite=True):
    P = preparer(partage(cons), echelle, efface)
    P["sym"] = None if crypto else sym_fiche
    B, Z, base = P["B"], P["Z"], P["base"]
    lignes, probas, ctrl = [], [], {}
    standard = chaine_min == 2 and efface == "milieu"
    for depart in departs:
        BX = B[depart]
        xh, xb, xm, xs, xconf, xfin = Z[depart]
        _, _, _, _, xc = zones_nono(BX.o, BX.h, BX.l, BX.c)
        ref = {(e["z"], e["i"], e["unite"], round(float(e["entree"]), 9)) for e in G.entrees(P, depart)} \
            if standard else set()
        mien = set()
        for z in range(len(xs)):
            d = int(xs[z])
            k0 = int(np.searchsorted(base.bt, xconf[z]))
            k1 = int(np.searchsorted(base.bt, xfin[z])) if xfin[z] < JAMAIS else base.n
            if k1 <= k0:
                continue
            cont, reac, prof, _ = historique(base.h, base.l, base.c, k0, k1, xh[z], xb[z], d, 3, False)
            p1 = prof[0] if reac[0] >= 0 else np.nan
            for var in GROSSE:
                kc = {"V1": cont[0], "R3": cont[2]}.get(var, cont[1])
                if kc < 0:
                    continue
                if var == "R2M" and classe(p1) != "milieu":
                    continue
                if var in ("R2E", "R2E-milieu") and classe(p1) != "entrée":
                    continue
                t_in = base.bt[kc]
                ch = descente(P, depart, z, t_in, chaine_min)
                if ch is None:
                    continue
                unite, zi, profondeur = ch
                e = entree_y(P, depart, z, unite, zi, t_in, bord=(var == "R2E"))
                if e is None:
                    continue
                if var == "V1":
                    mien.add((z, e["i"], unite, round(float(e["entree"]), 9)))
                row = un_trade(P, depart, unite, e, frais_fn, crypto)
                if row is None:
                    continue
                row.update({"variante": var, "depart": depart, "marche": nom, "z": z, "prof1": p1,
                            "contact": pd.Timestamp(int(t_in)), "etages": profondeur})
                if var == "V1":                       # version « condition sur la petite zone » (filtre de V1)
                    uh, ub, um, us, uconf, ufin = Z[unite]
                    a = int(np.searchsorted(base.bt, uconf[zi]))
                    b = int(np.searchsorted(base.bt, ufin[zi])) if ufin[zi] < JAMAIS else base.n
                    kf = int(np.searchsorted(base.bt, row["fill_ny"], "right")) - 1
                    cy, ry, py, _ = historique(base.h, base.l, base.c, a, b, uh[zi], ub[zi], d, 4, False)
                    row["n_petite"] = int(((cy >= 0) & (cy <= kf)).sum())
                    row["prof1_petite"] = py[0] if 0 <= ry[0] <= kf else np.nan
                lignes.append(row)
        ctrl[depart] = {"gigogne_entrees": len(ref), "mes_entrees_V1": len(mien), "identiques": len(ref & mien)}
    # ------------------------------------------------ avenant 3 : R2 par unité (entrée au milieu de la zone elle-même)
    if par_unite:
        echelle = P["echelle"]
        for U in UNITES_PAR:
            xh, xb, xm, xs, xconf, xfin = Z[U]
            plus_grandes = echelle[:echelle.index(U)]
            for z in range(len(xs)):
                d = int(xs[z])
                k0 = int(np.searchsorted(base.bt, xconf[z]))
                k1 = int(np.searchsorted(base.bt, xfin[z])) if xfin[z] < JAMAIS else base.n
                if k1 <= k0:
                    continue
                cont, reac, prof, _ = historique(base.h, base.l, base.c, k0, k1, xh[z], xb[z], d, 2, False)
                for n in (1, 2):
                    kc = cont[n - 1]
                    if kc < 0:
                        continue
                    t_in = base.bt[kc]
                    e = entree_y(P, U, z, U, z, t_in, bord=False)
                    if e is None:
                        continue
                    row = un_trade(P, U, U, e, frais_fn, crypto)
                    if row is None:
                        continue
                    autour = False
                    for u in plus_grandes:
                        uh, ub, um, us, uconf, ufin = Z[u]
                        if ((us == d) & (uconf <= t_in) & (ufin > t_in) & (ub <= xh[z]) & (uh >= xb[z])).any():
                            autour = True
                            break
                    row.update({"variante": f"U{n}", "depart": U, "marche": nom, "z": z, "autour": autour,
                                "prof1": prof[0] if reac[0] >= 0 else np.nan, "contact": pd.Timestamp(int(t_in))})
                    lignes.append(row)
    # ------------------------------------------------ probabilités : vraies zones et témoins hasard
    for U in (UNITES_PAR if par_unite else departs):
        probas += probas_unite(nom, P, U)
    t = pd.DataFrame(lignes)
    if len(t):
        if crypto:
            ta = tv = np.full(len(t), CC.NUIT_AN)
        else:
            ta, tv = taux_nuit(fiche(sym_fiche), pd.DatetimeIndex(t["entree"]))
            ta, tv = np.asarray(ta, float), np.asarray(tv, float)
        s = t["sens"].to_numpy()
        taux, taux_i = np.where(s > 0, ta, tv), np.where(s > 0, tv, ta)
        k = t["prix"].to_numpy() / t["risque"].to_numpy() / 360.0
        t["nuit_R"] = taux * t["nuits"].to_numpy() * k
        t["R"] = t["R_sans_nuit"] - t["nuit_R"]
        t["R_inverse"] = t["R_inverse_sans_nuit"] - taux_i * t["nuits_inv"].to_numpy() * k
        t["risque_compte"] = np.minimum(t["stop_frac"], RISQUE) if crypto else RISQUE
    del P, B, Z, base
    gc.collect()
    return t, pd.DataFrame(probas), ctrl


def marches_du_groupe(groupe):
    """(nom, construire, échelle, symbole de fiche, frais(prix), crypto ?)"""
    if groupe == "crypto":
        for c in CF.CRYPTOS:
            nom, fr = c + "USDT", CF.frais(c)
            yield c, (lambda nom=nom, fr=fr: CC.construire(nom, CC.en_ny(CC.charger_autre(nom)), fr)), \
                G.ECHELLE_45, None, (lambda p, fr=fr: fr), True
    elif groupe == "minutes":
        for m in MARCHES:
            sym = MARCHES[m]
            yield m, (lambda m=m: _construire_minutes(m, FIN)), G.ECHELLE_MINUTES, sym, \
                (lambda p, sym=sym: frais_ftmo(sym, p)), False
    else:
        for sym in dm.liste_marches():
            yield sym, (lambda sym=sym: construire_m15(sym, FIN)), G.ECHELLE_45, sym, \
                (lambda p, sym=sym: frais_ftmo(sym, p)), False


DETECTIONS = {"F1": ("M30", 2, "milieu"), "F2": ("H1", 1, "milieu"), "F3": ("H4", 1, "milieu"),
              "F4": ("H1", 2, "oppose"), "F5": ("H4", 2, "oppose"), "F6": ("M30", 2, "oppose")}


def detection_choisie():
    f = VIE / "choix_frequence.json"
    return json.loads(f.read_text(encoding="utf-8"))["choisie"] if f.exists() else None


def calculer(groupe, detection=None):
    CACHE.mkdir(parents=True, exist_ok=True)
    if detection:
        dep, cm, ef = DETECTIONS[detection]
        opts = {"departs": (dep,), "chaine_min": cm, "efface": ef, "par_unite": False}
        prefixe = f"{detection}_{groupe}"
    else:
        opts, prefixe = {}, groupe
    for nom, fab, echelle, sym, frais_fn, crypto in marches_du_groupe(groupe):
        f = CACHE / f"{prefixe}_{nom}.pkl"
        if f.exists():
            continue
        t0 = datetime.now()
        try:
            t, p, ctrl = trades_marche(nom, fab(), echelle, sym, frais_fn, crypto, **opts)
        except Exception as e:
            print(f"[{groupe}] {nom} ignoré ({type(e).__name__}: {e})", flush=True)
            continue
        pd.to_pickle({"trades": t, "probas": p, "controle": ctrl}, f)
        n = t["variante"].value_counts().to_dict() if len(t) else {}
        print(f"[{prefixe}] {nom} : {n} | contrôle {ctrl} | {(datetime.now() - t0).seconds} s", flush=True)
        gc.collect()


# ---------------------------------------------------------------- juge
def charger_groupe(groupe):
    ts, ps, cs = [], [], {}
    for f in sorted(CACHE.glob(f"{groupe}_*.pkl")):
        x = pd.read_pickle(f)
        nom = f.stem[len(groupe) + 1:]
        if len(x["trades"]):
            ts.append(x["trades"])
        if len(x["probas"]):
            ps.append(x["probas"])
        cs[nom] = x["controle"]
    return (pd.concat(ts, ignore_index=True) if ts else pd.DataFrame(),
            pd.concat(ps, ignore_index=True) if ps else pd.DataFrame(), cs)


def variantes(t: pd.DataFrame) -> dict:
    """Les 11 règles par départ : 6 « grosse zone » + 5 filtres « petite zone » de V1."""
    out = {}
    gros = t[t["variante"].isin(GROSSE)]
    for dep in [d for d in ("D1", "H4", "H1", "M30") if d in set(gros["depart"])]:
        td = gros[gros["depart"] == dep]
        for v in GROSSE:
            out[(dep, v)] = td[td["variante"] == v]
        v1 = td[td["variante"] == "V1"]
        if "n_petite" not in v1 or v1["n_petite"].isna().all():
            continue
        cl = v1["prof1_petite"].map(classe)
        out[(dep, "p-V1")] = v1[v1["n_petite"] == 1]
        out[(dep, "p-R2")] = v1[v1["n_petite"] == 2]
        out[(dep, "p-R3")] = v1[v1["n_petite"] == 3]
        out[(dep, "p-R2M")] = v1[(v1["n_petite"] == 2) & (cl == "milieu")]
        out[(dep, "p-R2E")] = v1[(v1["n_petite"] == 2) & (cl == "entrée")]
    u = t[t["variante"].isin(("U1", "U2"))]
    for U in UNITES_PAR:
        for n in (1, 2):
            g = u[(u["depart"] == U) & (u["variante"] == f"U{n}")]
            if not len(g):
                continue
            out[(f"unité {U}", f"contact {n} sans")] = g
            if U != "D1":
                out[(f"unité {U}", f"contact {n} avec")] = g[g["autour"].astype(bool)]
    return out


def reference(cle: str) -> str:
    """La règle de comparaison : V1 du même départ, ou le 1er contact de la même unité."""
    if cle.startswith("unité"):
        return cle.replace("contact 2", "contact 1")
    return cle.split(" ")[0] + " V1"


def mesures(g: pd.DataFrame, de, a, challenges: bool) -> dict:
    g = g[(pd.to_datetime(g["entree"]) >= de) & (pd.to_datetime(g["entree"]) < a)].sort_values("entree")
    n = len(g)
    if n == 0:
        return {"trades": 0}
    r = g["R"].to_numpy()
    x = {"trades": n, "R_moyen": float(r.mean()), "R_median": float(np.median(r)),
         "gagnants_pct": float((r > 0).mean() * 100),
         "gain_moyen_gagnant": float(r[r > 0].mean()) if (r > 0).any() else None,
         "perte_moyenne_perdant": float(r[r <= 0].mean()) if (r <= 0).any() else None,
         "trades_10R": int((r >= 10).sum()), "R_moyen_sans_nuit": float(g["R_sans_nuit"].mean()),
         "R_moyen_frais_labo": float(g["R_labo"].mean()), "marches": int(g["marche"].nunique())}
    if n >= 10:
        dd = (g["R"] - g["R_inverse"]).to_numpy() / 2
        x["force"] = float(dd.mean() / dd.std(ddof=1) * math.sqrt(n)) if dd.std(ddof=1) > 0 else 0.0
        c = CC.note(g, de, a, challenges=challenges)
        for k in ("pct_mois", "baisse_max_pct", "pire_jour_pct", "challenges_reussis_pct", "challenges_morts_pct",
                  "jumeaux_reussis_pct", "jumeaux_morts_pct"):
            if k in c:
                x[k] = c[k]
    return x


def verdict(res_v: dict, res_v1: dict) -> str:
    tout = res_v["tout"]
    if tout["trades"] < MIN_TRADES:
        return f"trop peu de trades ({tout['trades']}) : pas de conclusion"
    per = ("avant 2022", "2022-2023", "2024-2026")
    mots = []
    if res_v1 is not res_v:
        mieux = sum(1 for p in per if res_v[p].get("R_moyen", -99) > res_v1[p].get("R_moyen", 99))
        mots.append("meilleure que V1" if mieux >= 2 and tout["R_moyen"] > res_v1["tout"].get("R_moyen", 99)
                    else "pas meilleure que V1")
    debout = all(res_v[p].get("R_moyen", -1) > 0 for p in per) and tout.get("force", -1) > 0
    peu = [p for p in per if res_v[p]["trades"] < MIN_TRADES]
    if debout and tout.get("force", 0) >= SEUIL:
        mots.append("PROUVÉE")
    else:
        mots.append("tient debout" if debout else "ne tient pas (une période <= 0 ou force <= 0)")
    if peu:
        mots.append("périodes < 30 trades : " + ", ".join(f"{p} ({res_v[p]['trades']})" for p in peu))
    return " ; ".join(mots)


def probabilites(p: pd.DataFrame) -> dict:
    def taux(num, den):
        n = int(den.sum())
        return (float(num[den].mean() * 100) if n else None), n
    out = {}
    for (dep, genre), g in p.groupby(["depart", "genre"]):
        c1 = g["prof1"].map(classe)
        r1, c2, r2 = g["reac1"], g["contact2"], g["reac2"]
        c2cl = g["prof2"].map(classe)
        x = {}
        x["P_reaction_1er_contact"] = taux(r1, pd.Series(True, index=g.index))
        x["P_2e_contact_si_reaction1"] = taux(c2, r1)
        base = r1 & c2
        x["P_reaction_2e_si_reaction1"] = taux(r2, base)
        for k in ("milieu", "entrée", "profond"):
            x[f"P_reaction_2e_si_1er_{k}"] = taux(r2, base & (c1 == k))
        x["P_2e_aussi_milieu_si_1er_milieu"] = taux(c2cl == "milieu", base & r2 & (c1 == "milieu"))
        x["P_2e_aussi_entree_si_1er_entree"] = taux(c2cl == "entrée", base & r2 & (c1 == "entrée"))
        reag = g[r1]
        x["profondeur_1er_demi_tour_pct"] = {k: float((reag["prof1"].map(classe) == k).mean() * 100) if len(reag) else None
                                             for k in ("entrée", "milieu", "profond")}
        x["zones_touchees"] = int(len(g))
        out[f"{dep} {genre}"] = x
    # écarts vraie - témoin (z binomial)
    for dep in sorted(set(p["depart"])):
        a, b = out.get(f"{dep} zone"), out.get(f"{dep} témoin")
        if not a or not b:
            continue
        ec = {}
        for k, v in a.items():
            if isinstance(v, tuple) and v[0] is not None and b[k][0] is not None and v[1] and b[k][1]:
                p1, n1, p2, n2 = v[0] / 100, v[1], b[k][0] / 100, b[k][1]
                pp = (p1 * n1 + p2 * n2) / (n1 + n2)
                se = math.sqrt(max(pp * (1 - pp) * (1 / n1 + 1 / n2), 1e-12))
                ec[k] = {"ecart_points": (p1 - p2) * 100, "z": (p1 - p2) / se}
        out[f"{dep} écart zone - témoin"] = ec
    return out


def comparaisons(t: pd.DataFrame) -> dict:
    out = {}
    gros = t[t["variante"].isin(GROSSE)]
    for dep in sorted(set(gros["depart"])):
        td = gros[gros["depart"] == dep]
        v1 = td[td["variante"] == "V1"].set_index(["marche", "z"])["R"]
        for v in ("R2", "R3"):
            rv = td[td["variante"] == v].set_index(["marche", "z"])["R"]
            com = v1.index.intersection(rv.index)
            out[f"{dep} mêmes zones V1 / {v}"] = {"zones": int(len(com)),
                                                 "R_moyen_V1": float(v1.loc[com].mean()) if len(com) else None,
                                                 f"R_moyen_{v}": float(rv.loc[com].mean()) if len(com) else None}
        r2 = td[td["variante"] == "R2"]
        out[f"{dep} R2 selon le 1er demi-tour"] = {
            k: {"trades": int(len(g)), "R_moyen": float(g["R"].mean()), "gagnants_pct": float((g["R"] > 0).mean() * 100)}
            for k, g in r2.groupby(r2["prof1"].map(classe))}
    u2 = t[t["variante"] == "U2"]
    for U, gu in u2.groupby("depart"):
        out[f"unité {U} contact 2 selon le 1er demi-tour"] = {
            k: {"trades": int(len(g)), "R_moyen": float(g["R"].mean()), "gagnants_pct": float((g["R"] > 0).mean() * 100)}
            for k, g in gu.groupby(gu["prof1"].map(classe))}
    return out


def _ecrire(f, obj):
    f.write_text(json.dumps(obj, ensure_ascii=False, indent=1, default=str), encoding="utf-8")


def juger():
    sortie = {"quand": datetime.now().isoformat(timespec="seconds"), "seuil": SEUIL, "seuil_labo": SEUIL_LABO,
              "groupes": {}}
    jeux = list(GROUPES.items())
    det = detection_choisie()
    if det:
        jeux += [(f"{det}_{g}", f"{titre} — détection {det} {DETECTIONS[det]}") for g, titre in GROUPES.items()]
    seulement = sys.argv[2:] if len(sys.argv) > 2 else None
    for groupe, titre in jeux:
        if seulement and groupe not in seulement:
            continue
        t, p, ctrl = charger_groupe(groupe)
        if not len(t):
            print(f"{groupe} : pas encore calculé", flush=True)
            continue
        res = {"titre": titre, "marches": int(t["marche"].nunique()), "controle_entrees": ctrl, "regles": {}}
        V = variantes(t)
        for (dep, v), g in V.items():
            res["regles"][f"{dep} {v}"] = {per: mesures(g, de, a, challenges=v in GROSSE)
                                           for per, (de, a) in PERIODES.items()}
        for cle, x in res["regles"].items():
            ref = res["regles"].get(reference(cle))
            x["verdict"] = verdict(x, x if ref is None or reference(cle) == cle else ref)
        res["probabilites"] = probabilites(p) if len(p) else {}
        res["comparaisons"] = comparaisons(t)
        sortie["groupes"][groupe] = res
        _ecrire(VIE / f"resultats_{groupe}.json", res)
        # affichage
        print(f"\n===== {titre} ({res['marches']} marchés) | contrôle entrées : "
              f"{sum(c[d]['identiques'] for c in ctrl.values() for d in c)} identiques / "
              f"{sum(c[d]['gigogne_entrees'] for c in ctrl.values() for d in c)} (gigogne) / "
              f"{sum(c[d]['mes_entrees_V1'] for c in ctrl.values() for d in c)} (moi)", flush=True)
        for nomr, x in res["regles"].items():
            for per in PERIODES:
                y = x[per]
                if y["trades"] == 0:
                    print(f"{nomr:16s} | {per:10s} | 0 trade")
                    continue
                print(f"{nomr:16s} | {per:10s} | {y['trades']:5d} tr | R {y['R_moyen']:+.3f} (méd {y['R_median']:+.2f}, "
                      f"sans nuit {y['R_moyen_sans_nuit']:+.3f}, labo {y['R_moyen_frais_labo']:+.3f}) | gagn "
                      f"{y['gagnants_pct']:.0f} % | +{y['gain_moyen_gagnant'] or 0:.2f} / {y['perte_moyenne_perdant'] or 0:.2f}"
                      f" | >=10R {y['trades_10R']} | force {y.get('force', float('nan')):+.2f} | "
                      f"{y.get('pct_mois', float('nan')):+.2f} %/mois | chall {y.get('challenges_reussis_pct', float('nan')):.0f}/"
                      f"{y.get('challenges_morts_pct', float('nan')):.0f} (jum {y.get('jumeaux_reussis_pct', float('nan')):.0f}/"
                      f"{y.get('jumeaux_morts_pct', float('nan')):.0f})", flush=True)
            print(f"{nomr:16s} -> {x['verdict']}", flush=True)
        print(json.dumps(res["probabilites"], ensure_ascii=False, default=str), flush=True)
        print(json.dumps(res["comparaisons"], ensure_ascii=False, default=str), flush=True)
    sortie["controle_fidelite"] = fidelite()
    print("FIDÉLITÉ :", json.dumps(sortie["controle_fidelite"], ensure_ascii=False), flush=True)
    _ecrire(VIE / "resultats.json", sortie)


def fidelite() -> dict:
    out = {}
    ref = pd.read_csv(dm.RACINE / "collapsar" / "vie" / "smc" / "strategie_chef_trades_REPRISE_controle.csv")
    ref["entree"] = pd.to_datetime(ref["entree"])
    for groupe, nomg in (("minutes", "4 marchés (minutes)"), ("45", "45 marchés (15 min)")):
        t, _, _ = charger_groupe(groupe)
        if not len(t):
            continue
        a = t[(t["depart"] == "H4") & (t["variante"] == "V1")][["marche", "entree", "sens", "R_labo"]]
        b = ref[ref["groupe"] == nomg][["marche", "entree", "sens", "R"]]
        m = a.merge(b, on=["marche", "entree", "sens"], how="outer", indicator=True)
        deux = m[m["_merge"] == "both"]
        out[groupe] = {"moi": int(len(a)), "reference": int(len(b)), "communs": int(len(deux)),
                       "ecart_R_max": float((deux["R_labo"] - deux["R"]).abs().max()) if len(deux) else None,
                       "seulement_moi_apres_15oct": int(((m["_merge"] == "left_only") &
                                                         (m["entree"] >= "2026-10-15")).sum()),
                       "seulement_moi": int((m["_merge"] == "left_only").sum()),
                       "seulement_reference": int((m["_merge"] == "right_only").sum())}
    t, _, _ = charger_groupe("crypto")
    if len(t):
        a = t[(t["depart"] == "H4") & (t["variante"] == "V1")]
        ecarts, n_ref = [], 0
        for c in CF.CRYPTOS:
            f = CF.CACHE / f"{c}_trades.pkl"
            if not f.exists():
                continue
            r = pd.read_pickle(f)[["entree", "R_A"]]
            n_ref += len(r)
            m = a[a["marche"] == c].merge(r, on="entree")
            ecarts.append((m["R"] - m["R_A"]).abs().max() if len(m) else np.nan)
        out["crypto"] = {"moi": int(len(a)), "reference": n_ref, "ecart_R_max": float(np.nanmax(ecarts))}
    return out


# ---------------------------------------------------------------- avenant 1 : diagnostic de fréquence (aucun gain)
INDICES = {"US500": "USA500IDXUSD", "US100": "USATECHIDXUSD", "US30": "USA30IDXUSD", "GER40": "DEUIDXEUR"}
INDICES_MINUTES = {"US500": "US500", "US100": "NAS100"}
DEBUT_FREQ = pd.Timestamp("2024-01-01")
SEMAINE_NS = 7 * JOUR_NS
ETAPES = ["zones créées", "1ers contacts", "jamais touchée (créée dans la fenêtre)", "contact qui efface déjà la zone",
          "pas de zone dans la zone", "chaîne complète", "milieu pas atteint : effacement d'abord",
          "milieu pas atteint : fenêtre de 200 bougies", "remplie", "pas d'objectif 3 >= 2 R", "trade V1"]


def figures_bos(b, t0) -> dict:
    """Figures « bougie opposée + FVG » (la bougie j = i-1) et celles qui ont aussi la cassure sur i-4 / i-5."""
    o, h, l, c = b.o, b.h, b.l, b.c
    i = np.arange(5, b.n)
    j = i - 1
    dem = (c[j] < o[j]) & (l[j] > h[j - 2])
    off = (c[j] > o[j]) & (h[j] < l[j - 2])
    bos_d = c[i] > np.maximum(h[i - 4], h[i - 5])
    bos_o = c[i] < np.minimum(l[i - 4], l[i - 5])
    dans = b.bt[i] >= t0
    return {"figures": int((dans & (dem | off)).sum()), "avec_cassure": int((dans & ((dem & bos_d) | (off & bos_o))).sum())}


def entonnoir(P, depart, t0, chaine_min=2):
    B, Z, base = P["B"], P["Z"], P["base"]
    xh, xb, xm, xs, xconf, xfin = Z[depart]
    tfin = int(base.bt[-1] + base.duree)
    sem = (tfin - t0) / SEMAINE_NS
    n = dict.fromkeys(ETAPES, 0)
    n["contacts (tous, retouches comprises)"] = 0
    n["2es contacts (après une réaction)"] = 0
    delais, de_suite, dedans = [], 0, 0
    BX = B[depart]
    _, _, _, _, xc = zones_nono(BX.o, BX.h, BX.l, BX.c)
    for z in range(len(xs)):
        d = int(xs[z])
        cree = t0 <= xconf[z] < tfin
        n["zones créées"] += int(cree)
        k0 = int(np.searchsorted(base.bt, xconf[z]))
        k1 = int(np.searchsorted(base.bt, xfin[z])) if xfin[z] < JAMAIS else base.n
        if k1 <= k0:
            continue
        cont, reac, prof, _ = historique(base.h, base.l, base.c, k0, k1, xh[z], xb[z], d, 6, False)
        n["contacts (tous, retouches comprises)"] += int(((cont >= 0) & (base.bt[np.maximum(cont, 0)] >= t0)).sum())
        if cont[0] < 0:
            n["jamais touchée (créée dans la fenêtre)"] += int(cree)
            continue
        if cont[1] >= 0 and base.bt[cont[1]] >= t0:
            n["2es contacts (après une réaction)"] += 1
        t_in = int(base.bt[cont[0]])
        if t_in < t0:
            continue
        n["1ers contacts"] += 1
        delais.append((t_in - xconf[z]) / 3600e9)
        de_suite += int(cont[0] == k0)
        dedans += int((BX.c[xc[z]] <= xh[z]) if d > 0 else (BX.c[xc[z]] >= xb[z]))
        if xfin[z] < JAMAIS and cont[0] == k1 - 1:
            n["contact qui efface déjà la zone"] += 1
        ch = descente(P, depart, z, t_in, chaine_min)
        if ch is None:
            n["pas de zone dans la zone"] += 1
            continue
        n["chaîne complète"] += 1
        unite, zi, _ = ch
        e = entree_y(P, depart, z, unite, zi, t_in, bord=False)
        if e is None:
            BY = B[unite]
            ufin = Z[unite][5]
            e0 = int(np.searchsorted(BY.bt, t_in))
            limite = min(xfin[z], ufin[zi])
            k_lim = int(np.searchsorted(BY.bt, limite)) if limite < JAMAIS else BY.n
            n["milieu pas atteint : effacement d'abord" if k_lim < e0 + ATTENTE else
              "milieu pas atteint : fenêtre de 200 bougies"] += 1
            continue
        n["remplie"] += 1
        row = un_trade(P, depart, unite, e, lambda p: 0.0, False)
        n["trade V1" if row is not None else "pas d'objectif 3 >= 2 R"] += 1
    semaines = np.arange(t0, tfin, SEMAINE_NS)
    vivantes = float(np.mean([((xconf <= w) & (xfin > w)).sum() for w in semaines])) if len(semaines) else 0.0
    m = max(1, n["1ers contacts"])
    return {"semaines": sem, "par_semaine": {k: v / sem for k, v in n.items()}, "total": n,
            "zones_vivantes_moyenne": vivantes,
            "delai_median_confirmation_contact_heures": float(np.median(delais)) if delais else None,
            "contact_des_la_1re_bougie_pct": 100 * de_suite / m,
            "cloture_de_confirmation_deja_dans_la_zone_pct": 100 * dedans / m}


def frequence():
    t0 = int(DEBUT_FREQ.value)
    sortie = {"quand": datetime.now().isoformat(timespec="seconds"), "debut": str(DEBUT_FREQ), "marches": {}}
    jeux = [(f"{k} (15 min)", lambda s=s: construire_m15(s, FIN), G.ECHELLE_45) for k, s in INDICES.items()]
    jeux += [(f"{k} (minutes)", lambda m=m: _construire_minutes(m, FIN), G.ECHELLE_MINUTES)
             for k, m in INDICES_MINUTES.items()]
    for nom, fab, echelle in jeux:
        P = G.preparer(partage(fab()), echelle)
        x = {"zones_creees_par_semaine": {}, "cassure_BOS": {}, "departs": {}}
        tfin = int(P["base"].bt[-1] + P["base"].duree)
        sem = (tfin - t0) / SEMAINE_NS
        if sem <= 1:
            x = {"donnees_jusqu_au": str(pd.Timestamp(tfin))}
            print(f"{nom}: données finies le {pd.Timestamp(tfin)} (avant la fenêtre)", flush=True)
            sortie["marches"][nom] = x
            del P
            gc.collect()
            continue
        for u in echelle:
            conf = P["Z"][u][4]
            x["zones_creees_par_semaine"][u] = float(((conf >= t0) & (conf < tfin)).sum() / sem)
            x["cassure_BOS"][u] = figures_bos(P["B"][u], t0)
        for dep in ("D1", "H4", "H1", "M30"):
            x["departs"][dep] = entonnoir(P, dep, t0)
            ps = x["departs"][dep]["par_semaine"]
            print(f"{nom:16s} départ {dep:3s} | " + " | ".join(f"{k} {v:.2f}" for k, v in ps.items())
                  + f" | vivantes {x['departs'][dep]['zones_vivantes_moyenne']:.0f}", flush=True)
        print(f"{nom:16s} zones/semaine {json.dumps({k: round(v, 1) for k, v in x['zones_creees_par_semaine'].items()})}"
              f" | figures FVG sans/avec cassure {json.dumps(x['cassure_BOS'])}", flush=True)
        sortie["marches"][nom] = x
        del P
        gc.collect()
    tot = {}
    for dep in ("D1", "H4", "H1", "M30"):
        tot[dep] = {k: sum(sortie["marches"][f"{i} (15 min)"]["departs"][dep]["par_semaine"][k] for i in INDICES)
                    for k in sortie["marches"]["US500 (15 min)"]["departs"][dep]["par_semaine"]}
        print(f"4 INDICES (15 min) départ {dep} : " + " | ".join(f"{k} {v:.2f}" for k, v in tot[dep].items()), flush=True)
    sortie["quatre_indices_15min_par_semaine"] = tot
    _ecrire(VIE / "frequence.json", sortie)


def choix_frequence():
    """Avenant 2 : on ne regarde QUE le nombre de trades V1 par semaine (4 indices, 15 min, 2024-2026)."""
    f = VIE / "choix_frequence.json"
    if f.exists():
        print("choix déjà fait :", f.read_text(encoding="utf-8"))
        return
    t0 = int(DEBUT_FREQ.value)
    res = {}
    for nomd, (dep, cm, ef) in DETECTIONS.items():
        tot = {}
        for k, s in INDICES.items():
            P = preparer(partage(construire_m15(s, FIN)), G.ECHELLE_45, ef)
            e = entonnoir(P, dep, t0, cm)
            for a, v in e["par_semaine"].items():
                tot[a] = tot.get(a, 0.0) + v
            del P
            gc.collect()
        res[nomd] = {"regle": {"depart": dep, "chaine_min": cm, "effacement": ef}, "par_semaine_4_indices": tot}
        print(f"{nomd} {dep} chaîne>={cm} effacement {ef} : trades V1/semaine {tot['trade V1']:.2f} | 2es contacts "
              f"{tot['2es contacts (après une réaction)']:.2f}", flush=True)
    ordre = {"D1": 0, "H4": 1, "H1": 2, "M30": 3}
    ecart = {k: abs(v["par_semaine_4_indices"]["trade V1"] - 4.5) for k, v in res.items()}
    mini = min(ecart.values())
    proches = [k for k in res if ecart[k] - mini < 0.3]
    choisie = min(proches, key=lambda k: ordre[DETECTIONS[k][0]])
    _ecrire(f, {"quand": datetime.now().isoformat(timespec="seconds"), "cible": 4.5, "candidates": res,
                "choisie": choisie})
    print("CHOISIE :", choisie, DETECTIONS[choisie], flush=True)


if __name__ == "__main__":
    VIE.mkdir(parents=True, exist_ok=True)
    action = sys.argv[1] if len(sys.argv) > 1 else "juger"
    if action == "calculer":
        calculer(sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else None)
    elif action == "frequence":
        frequence()
    elif action == "choix_frequence":
        choix_frequence()
    elif action == "calculer_choisie":
        calculer(sys.argv[2], detection_choisie())
    else:
        juger()
