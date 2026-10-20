"""VERDICT FINAL des zones du chef de projet (indicateur « zones supply and demand », zones gigognes) avec le JUGE ENTIÈREMENT CORRIGÉ
(16/10/2026 au soir). Résultats : collapsar/vie/pistes/verdict_zones_corrige/.

CAHIER ÉCRIT AVANT TOUT RÉSULTAT DE CE CALCUL. Les règles de zones ne sont PAS changées : ce sont celles déjà écrites
(docs/CASCADE_ZONES.md et avenants 1 à 3 ; zones_retouchees.py ; zones_retouchees_v7.py = traduction fidèle nono_v7).
Le code de ces pistes est appelé tel quel (zones_v7, P_depart, descente, entree_y, gigogne.preparer / entrees,
noyaux._remplissage) ; la sortie est chef_compte_ftmo.trade_parts (même parcours que chef_crypto.trade_tiers_heures,
contrôlé trade par trade) pour avoir aussi le prix et la nature de chaque sortie (nécessaires au compte).

Juge corrigé (audit du 16/10, chantiers A, B, C)
- Heures en nanosecondes partout (chantier A).
- Frais FTMO (chantier C) : écart relevé SANS le x 1,25 (mains/frais_ftmo.MARGE_PRUDENCE = 1) ; entrée par ordre limite
  = demi-frais (x facteur de l'écart de la 1re heure de New York, mesuré : US500 1,16, Nasdaq 1,07, autres indices 1,1) ;
  objectif ou fin des 30 jours = demi-frais ; stop = frais entiers (= demi-frais + 0,5 fiche de glissement, mesuré) ;
  aucune entrée au marché. Cryptos Binance : commission FTMO 0,0325 %/côté + écart relevé (crypto_flux.frais :
  BTC 0,066 %, ETH 0,090 %, autres 0,096 % aller-retour). Les 47 marchés et les 4 marchés à la minute : frais_ftmo.frais
  (cryptos Dukascopy du groupe des 47 : commission comprise).
- Nuits (chantier C) : taux FTMO achat et vente séparés (mains/nuit.taux_nuit ; cryptos 30 %/an des deux côtés), par
  minuit serveur franchi, nuit triple au bon jour (zones_retouchees.nuits_ftmo : mercredi devises / métaux / obligations,
  vendredi indices / énergies / cryptos ; samedi et dimanche 0), tiers par tiers.
- Force (chantier B) = moyenne((R - R_inverse) / 2) / écart type x racine(n), le jumeau prenant le sens inverse aux mêmes
  moments avec ses propres frais et nuits. Ici chaque trade risque la même part du compte : la force en R est déjà
  « pondérée par la taille » (le défaut 2 concernait les règles taillées à l'agitation).
- Compte (chantier B) : challenges jugés au PIRE POINT de chaque bougie de 15 min (somme des pires prix des positions
  ouvertes, prudent), « réussis / morts PARMI LES TERMINÉS » (FTMO n'a pas de limite de temps ; inachevés à part).

Lignes (liste fermée, une ligne = traduction x version x unité de départ x stop), au 1er CONTACT (V1), entrée par ordre
limite au MILIEU, 200 bougies de l'unité de la zone d'entrée au plus, sorties par tiers (2 R / sommet H1 / bord de la plus
proche zone opposée de l'unité de départ, vivante ; pas de trade sans objectif 3 à 2 R au moins), 30 jours au plus.
Stop « A » = bord opposé de la zone d'entrée ± 0,2 ATR de son unité ; « A+plancher » = le même avec un minimum de
0,2 x ATR journalier (dernier jour complet), comme sa pratique (avenants 2-3).
1. Traduction FIDÈLE (nono_v7) :
   - « seule U » : chaque unité U seule (D1, H4, H1, M30, M15 ; + M5, M3 pour les 4 marchés à la minute) : zone de U
     sur son propre graphique (effacée par les clôtures de U), 1er contact du bord proche sur le graphique d'entrée,
     entrée au milieu de la zone U elle-même, objectif 3 = zone opposée de U ; stops A et A+plancher ;
   - « gigogne U » : départ U (toutes les unités sauf la plus petite), descente dans les zones affichées sur le graphique
     d'entrée (au moins 2 zones), entrée au milieu de la plus petite ; stops A et A+plancher.
   Graphique d'entrée : M15 (cryptos, 47 marchés), M3 (4 marchés à la minute).
2. SA PRATIQUE « Gigogne H4 stop A plancher 0.2 » (avenant 3) et la même au départ D1 et H1 = les lignes
   « fidèle | gigogne | D1 / H4 / H1 | A+plancher » ci-dessus (sur son indicateur, donc la traduction fidèle).
3. ANCIENNE traduction (gigogne.preparer / entrees : effacement de toutes les zones à la clôture de la plus petite unité,
   celle qui donnait +0,19 R au départ H4 et +0,44 R au départ D1 sur les cryptos) : départs D1, H4, H1, A+plancher.

Groupes : (a) or, Nasdaq, S&P 500, euro à la minute ; (b) 19 cryptos FTMO (Binance 15 min, filtre commun) ; (c) les 47
marchés de dm.liste_marches() en 15 min. Toutes les années disponibles (2015 -> 10/2026 ; cryptos selon Binance).

Mesures par ligne et par groupe : trades, trades par semaine (sur la durée des données du groupe), % gagnants, R moyen
après frais et nuits, R médian, force, R moyen par période (avant 2022 / 2022-2023 / 2024-2026), par année 2022 ... 2026.
Colonne « avant corrections » = les chiffres DÉJÀ PUBLIÉS (rapports zones_retouchees, chef_compte_ftmo), pas recalculés.

Compte FTMO 100 000 $ (Swing), seulement pour les lignes choisies ainsi (règle écrite avant tout résultat, sans regarder
2024-2026) : les 3 lignes (tous groupes) au meilleur R moyen AVANT 2024 parmi celles qui ont au moins 100 trades et un R
moyen > 0 avant 2024 ; plus « ancienne | gigogne | H4 | A+plancher » des cryptos (sa version en démo) si elle n'y est
pas. Une ligne de plus de 60 000 trades n'est pas simulée (mémoire). Politique : risque 0,25 % puis 0,5 % du solde par
trade, 4 positions au plus (les suivantes ignorées), marge = montant / levier FTMO Swing (fiche : devises 30, indices /
métaux / énergies 15, cryptos 1 ; taille réduite à la marge libre) ; fonds suivis bougie de 15 min par bougie de 15 min
(pire prix de la bougie) ; sortie de chaque tiers datée à la 1re bougie de 15 min où son prix est atteint ; frais
d'entrée au remplissage, frais de sortie et nuits à la sortie de chaque tiers. Compte continu par période (départ
100 000 $, rien ne l'arrête) : %/mois composé, baisse max (pire point contre le plus haut). Challenges : départ tous les
10 jours (jour serveur), +10 % puis +5 % (nouveau compte le lendemain), 4 jours de trading au moins, mort si le pire
point <= solde du début du jour - 5 000 $ ou <= 90 000 $ ; pas de limite de temps (inachevé si les données finissent) ;
contre 20 jumeaux (mêmes signaux, mêmes moments, même politique, sens à pile ou face trade par trade).

Années : TOUTES ont déjà été vues pour cette famille (laboratoire SMC, chef_crypto, chef_compte_ftmo, zones_retouchees).
Ce calcul est un constat avec le juge corrigé, pas une preuve ; rien n'est choisi sur 2024-2026.

Depuis Test_IA : venv_gpu\\Scripts\\python.exe -u -m collapsar.regarder.pistes.verdict_zones_corrige
                 frais | calculer <crypto|minutes|45> | juger | compte
"""
from __future__ import annotations

import gc
import json
import math
import sys
from datetime import datetime

import numpy as np
import pandas as pd
from numba import njit

from collapsar.donnees import marches as dm
from collapsar.mains import frais_ftmo as FF
from collapsar.mains.fiches import fiche
from collapsar.mains.nuit import taux_nuit
from collapsar.regarder.pistes import chef_compte_ftmo as CF
from collapsar.regarder.pistes import chef_crypto as CC
from collapsar.regarder.pistes import zones_retouchees as ZR
from collapsar.regarder.pistes import zones_retouchees_v7 as V7
from collapsar.regarder.smc import gigogne as G
from collapsar.regarder.smc import noyaux as K
from collapsar.regarder.smc.bougies import MARCHES
from collapsar.regarder.smc.multi import construire_m15, sommets_confirmes
from collapsar.regarder.smc.nono import TENUE_JOURS, _construire_minutes

VIE = dm.RACINE / "collapsar" / "vie" / "pistes" / "verdict_zones_corrige"
CACHE = VIE / "cache"
BARRES = VIE / "barres"
FIN = pd.Timestamp("2100-01-01")
JAMAIS = np.iinfo(np.int64).max
ORDRE = ("D1", "H4", "H1", "M30", "M15", "M5", "M3")
PLANCHER = 0.2
POIDS = np.full(3, 1.0 / 3.0)
H7 = 7 * 3600 * 10 ** 9
T0 = pd.Timestamp("2014-12-01")                  # début de la grille du compte (heure serveur, minuit, un lundi)
PAS = 15 * 60 * 10 ** 9
CAPITAL = 100_000.0
RISQUES = (0.0025, 0.005)
MAXPOS = 4
JUMEAUX = 20
MAX_TRADES_COMPTE = 60_000
GROUPES = {"minutes": "or, Nasdaq, S&P 500, euro (minutes, graphique M3)",
           "crypto": "19 cryptos FTMO (Binance, 15 min)", "45": "47 marchés (15 min)"}
PERIODES = {"avant 2022": ("2000-01-01", "2022-01-01"), "2022-2023": ("2022-01-01", "2024-01-01"),
            "2024-2026": ("2024-01-01", "2027-01-01"), "tout": ("2000-01-01", "2027-01-01")}
ANNEES = (2022, 2023, 2024, 2025, 2026)
SA_DEMO = ("crypto", "ancienne|gigogne|H4|A+plancher")

# chiffres DÉJÀ PUBLIÉS avant les corrections B / C (heures déjà corrigées) : vie/pistes/zones_retouchees/rapport.md
# (§ 0, 2 et 5 ; frais x 1,25, nuits calendaires) et chef_crypto/rapport.md (V2 : groupe A seul, frais sans commission)
AVANT = {
    "crypto": {"fidèle|gigogne|H4|A+plancher": "822 tr, -0,11 R", "fidèle|gigogne|D1|A+plancher": "185 tr, -0,01 R",
               "fidèle|seule|D1|A+plancher": "444 tr, -0,04 R", "fidèle|seule|H4|A+plancher": "3 832 tr, -0,06 R",
               "fidèle|seule|H1|A+plancher": "16 231 tr, -0,14 R", "fidèle|seule|M30|A+plancher": "34 978 tr, -0,12 R",
               "fidèle|seule|M15|A+plancher": "77 456 tr, -0,14 R",
               "ancienne|gigogne|H4|A+plancher": "802 tr, +0,19 R", "ancienne|gigogne|D1|A+plancher": "136 tr, +0,44 R",
               "ancienne|gigogne|H1|A+plancher": "1 510 tr, -0,04 R (12 cryptos, frais sans commission)"},
    "minutes": {"fidèle|gigogne|H4|A+plancher": "288 tr, -0,17 R", "fidèle|gigogne|D1|A+plancher": "43 tr, -0,05 R",
                "fidèle|seule|D1|A+plancher": "66 tr, +0,08 R", "fidèle|seule|H4|A+plancher": "698 tr, -0,20 R",
                "fidèle|seule|H1|A+plancher": "3 372 tr, -0,20 R", "fidèle|seule|M30|A+plancher": "7 327 tr, -0,12 R",
                "fidèle|seule|M15|A+plancher": "16 232 tr, -0,19 R",
                "ancienne|gigogne|H4|A+plancher": "234 tr, -0,03 R", "ancienne|gigogne|D1|A+plancher": "35 tr, +0,00 R"},
    "45": {"fidèle|gigogne|H4|A+plancher": "1 553 tr, -0,31 R", "fidèle|gigogne|D1|A+plancher": "376 tr, -0,28 R",
           "fidèle|seule|D1|A+plancher": "947 tr, -0,22 R", "fidèle|seule|H4|A+plancher": "7 216 tr, -0,29 R",
           "fidèle|seule|H1|A+plancher": "35 917 tr, -0,32 R", "fidèle|seule|M30|A+plancher": "82 720 tr, -0,32 R",
           "fidèle|seule|M15|A+plancher": "179 911 tr, -0,32 R",
           "ancienne|gigogne|H4|A+plancher": "1 533 tr, -0,31 R", "ancienne|gigogne|D1|A+plancher": "287 tr, -0,39 R"},
}
AVANT_COMPTE = {"ancienne|gigogne|H4|A+plancher": {
    0.0025: "+0,15 %/mois, baisse -12,4 %, challenges 36 % réussis / 0 % morts / 64 % inachevés (jumeaux 4 / 62) "
            "[0,25 %, 4 positions, 1 par crypto, arrêt du jour -2 %, frais x 1,25]",
    0.005: "-0,03 %/mois, baisse -25,7 %, 50 / 45 / 5 % (jumeaux 15 / 77) [0,5 %, 6 positions, frais x 1,25]"}}


def frais_crypto(c: str) -> float:
    """Aller-retour FTMO d'une crypto Binance : commission 0,065 % + écart relevé (crypto_flux.frais, sans x 1,25)."""
    from collapsar.regarder.pistes.crypto_flux import frais
    return float(frais(c + "USDT"))


def marches(groupe):
    """(nom, fabrique de bougies, symbole de fiche ou None, frais(prix), crypto ?)"""
    if groupe == "crypto":
        for c in CF.CRYPTOS:
            nom, fr = c + "USDT", frais_crypto(c)
            yield c, (lambda nom=nom, fr=fr: CC.construire(nom, CC.en_ny(CC.charger_autre(nom)), fr)), None, \
                (lambda p, fr=fr: fr), True
    elif groupe == "minutes":
        for m, sym in MARCHES.items():
            yield m, (lambda m=m: _construire_minutes(m, FIN)), sym, (lambda p, sym=sym: FF.frais(sym, p)), False
    else:
        for sym in dm.liste_marches():
            yield sym, (lambda sym=sym: construire_m15(sym, FIN)), sym, (lambda p, sym=sym: FF.frais(sym, p)), False


def nuits(sym, crypto, t_entree, t_sortie) -> np.ndarray:
    if crypto:
        return CC.nuits(t_entree, t_sortie)
    return ZR.nuits_ftmo(sym, t_entree, t_sortie)


# ---------------------------------------------------------------- un trade
@njit(cache=True)
def premier_contact(h, l, k0, k1, proche, d):
    for k in range(k0, k1):
        if (d > 0 and l[k] <= proche) or (d < 0 and h[k] >= proche):
            return k
    return -1


def contact(base, Zu, z) -> int:
    xh, xb, xm, xs, xconf, xfin = Zu[:6]
    k0 = int(np.searchsorted(base.bt, xconf[z]))
    k1 = int(np.searchsorted(base.bt, xfin[z])) if xfin[z] < JAMAIS else base.n
    if k1 <= k0:
        return -1
    d = int(xs[z])
    return int(premier_contact(base.h, base.l, k0, k1, float(xh[z] if d > 0 else xb[z]), d))


def un_trade(P, depart, unite, e, fr, plancher) -> dict | None:
    """Le trade et son jumeau (mêmes objectifs que zones_retouchees.un_trade) ; R sans nuit, détail des 3 sorties."""
    B, Z = P["B"], P["Z"]
    s_px, s_ty, s_t = P["sommets"]
    BD, BY = B["D1"], B[unite]
    xh, xb, xm, xs, xconf, xfin = Z[depart][:6]
    i, d, entree = e["i"], e["sens"], e["entree"]
    t_e = BY.bt[i]
    risque = e["risque_zone"]
    if plancher:
        jd = int(np.searchsorted(BD.bt, t_e, "right")) - 2
        risque = max(risque, plancher * (BD.atr[jd] if jd >= 0 else np.nan))
    if not np.isfinite(risque) or risque <= 0:
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
    fac = float(BY.facteur[i])
    row = {"unite_entree": unite, "entree": pd.Timestamp(BY.t[i]), "fill_ny": int(BY.mt[f_min]), "sens": d,
           "prix": float(entree), "risque": float(risque), "frais": fr, "facteur": fac, "tp3_R": d3 / risque,
           "duree_unite": int(BY.duree)}
    for g, s in ((0, d), (1, -d)):
        cibles = np.array([entree + s * 2.0 * risque, entree + s * d2, entree + s * d3])
        t_s, p_s, k_s = CF.trade_parts(*args, s, entree, risque, cibles, POIDS, False, tenue)
        part = ((p_s - entree) * s - entree * fr * np.where(k_s == 1, 1.0, 0.5)) / 3.0 / risque
        row[f"R_sans_nuit_{g}"] = float(part.sum() - entree * fr * 0.5 * fac / risque)
        for q in range(3):
            row[f"t{g}{q}"], row[f"p{g}{q}"], row[f"k{g}{q}"], row[f"r{g}{q}"] = \
                int(t_s[q]), float(p_s[q]), int(k_s[q]), float(part[q])
    r_ref, _, _ = CC.trade_tiers_heures(*args, d, entree, risque, d2, d3, tenue, fr, fac)
    row["ecart_controle"] = abs(float(r_ref) - row["R_sans_nuit_0"])
    return row


def finir(t: pd.DataFrame, sym, crypto) -> pd.DataFrame:
    """Nuits FTMO tiers par tiers (taux du sens joué à l'entrée), R final du trade et de son jumeau."""
    if not len(t):
        return t
    fill = t["fill_ny"].to_numpy(np.int64)
    if crypto:
        ta = tv = np.full(len(t), CC.NUIT_AN)
    else:
        ta, tv = taux_nuit(fiche(sym), pd.DatetimeIndex(t["entree"]))
        ta, tv = np.asarray(ta, float), np.asarray(tv, float)
    s = t["sens"].to_numpy()
    k = t["prix"].to_numpy() / t["risque"].to_numpy() / 360.0 / 3.0
    for g in (0, 1):
        sg = s if g == 0 else -s
        taux = np.where(sg > 0, ta, tv)
        tot = np.zeros(len(t))
        for q in range(3):
            nb = nuits(sym, crypto, fill, t[f"t{g}{q}"].to_numpy(np.int64))
            nr = taux * nb * k
            t[f"n{g}{q}"] = nb
            t[f"r{g}{q}"] = t[f"r{g}{q}"] - nr
            tot += nr
        t[f"nuit_R_{g}"] = tot
        t[f"R_{g}"] = t[f"R_sans_nuit_{g}"] - tot
    t["R"], t["R_inverse"] = t["R_0"], t["R_1"]
    t["c0"] = t["prix"] * t["frais"] * 0.5 * t["facteur"] / t["risque"]
    return t


# ---------------------------------------------------------------- un marché
def calcul_marche(groupe, nom, fab, sym, fr_fn, crypto) -> dict:
    E = "M3" if groupe == "minutes" else "M15"
    B = V7.construire_tout(fab, groupe, E)
    base = B[E]
    unites = [u for u in ORDRE if u in B]
    h1 = B["H1"]
    s_px, s_cf, s_ty = sommets_confirmes(h1.h, h1.l)
    S = (s_px, s_ty, h1.bt[s_cf] + h1.duree)
    Ze = V7.zones_v7(B, E, [u for u in V7.UNITES_V7 if u in B])
    lignes = []

    def ajoute(P, dep, unite, e, trad, version, U):
        fr = float(fr_fn(e["entree"]))
        for nomstop, pl in (("A", None), ("A+plancher", PLANCHER)):
            if trad == "ancienne" and pl is None:
                continue
            r = un_trade(P, dep, unite, e, fr, pl)
            if r is None:
                continue
            r.update({"ligne": f"{trad}|{version}|{U}|{nomstop}", "marche": nom, "z": int(e["z"])})
            lignes.append(r)

    for U in unites:
        ZU = V7.zones_v7(B, U, (U,))[U]
        # 1) l'unité seule : entrée au milieu de la zone U elle-même
        P = {"B": B, "Z": {U: ZU[:6]}, "base": base, "echelle": [U], "sommets": S}
        for z in range(len(ZU[3])):
            kc = contact(base, ZU, z)
            if kc < 0:
                continue
            e = ZR.entree_y(P, U, z, U, z, base.bt[kc], bord=False)
            if e is not None:
                e["z"] = z
                ajoute(P, U, U, e, "fidèle", "seule", U)
        # 2) la gigogne au départ U
        if U != unites[-1]:
            P = V7.P_depart(B, U, E, ZU, Ze)
            for z in range(len(ZU[3])):
                kc = contact(base, ZU, z)
                if kc < 0:
                    continue
                t_in = base.bt[kc]
                ch = ZR.descente(P, U, z, t_in, 2)
                if ch is None:
                    continue
                unite, zi, _ = ch
                e = ZR.entree_y(P, U, z, unite, zi, t_in, bord=False)
                if e is not None:
                    e["z"] = z
                    ajoute(P, U, unite, e, "fidèle", "gigogne", U)
    # 3) l'ancienne traduction (gigogne.preparer / entrees, appelés tels quels)
    P = G.preparer(lambda u: B[u], G.ECHELLE_MINUTES if groupe == "minutes" else G.ECHELLE_45)
    for dep in ("D1", "H4", "H1"):
        for e in G.entrees(P, dep):
            e["prix_ordre"] = e["milieu"]
            ajoute(P, dep, e["unite"], e, "ancienne", "gigogne", dep)
    t = finir(pd.DataFrame(lignes), sym, crypto)
    m15 = B["M15"]
    BARRES.mkdir(parents=True, exist_ok=True)
    np.savez(BARRES / f"{groupe}_{nom}.npz", bt=m15.bt, l=m15.l, h=m15.h, c=m15.c)
    out = {"trades": t, "debut": int(base.bt[0]), "fin": int(base.bt[-1] + base.duree),
           "levier": float(fiche(sym).levier) if sym else 1.0}
    del B, P, Ze
    gc.collect()
    return out


def calculer(groupe):
    CACHE.mkdir(parents=True, exist_ok=True)
    for nom, fab, sym, fr_fn, crypto in marches(groupe):
        f = CACHE / f"{groupe}_{nom}.pkl"
        if f.exists():
            continue
        t0 = datetime.now()
        try:
            x = calcul_marche(groupe, nom, fab, sym, fr_fn, crypto)
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"[{groupe}] {nom} ignoré ({type(e).__name__}: {e})", flush=True)
            continue
        pd.to_pickle(x, f)
        t = x["trades"]
        ec = float(t["ecart_controle"].max()) if len(t) else 0.0
        print(f"[{groupe}] {nom} : {len(t)} trades, {t['ligne'].nunique() if len(t) else 0} lignes, contrôle sortie "
              f"{ec:.1e} R | {(datetime.now() - t0).seconds} s", flush=True)
        del x, t
        gc.collect()


# ---------------------------------------------------------------- juge
COLS = ["ligne", "marche", "entree", "R", "R_inverse", "R_sans_nuit_0", "nuit_R_0", "c0", "ecart_controle", "risque",
        "prix"]


def charger(groupe, colonnes=COLS, ligne=None):
    ts, debut, fin, lev = [], [], [], {}
    for f in sorted(CACHE.glob(f"{groupe}_*.pkl")):
        x = pd.read_pickle(f)
        t = x["trades"]
        nom = f.stem[len(groupe) + 1:]
        debut.append(x["debut"])
        fin.append(x["fin"])
        lev[nom] = x["levier"]
        if not len(t):
            continue
        if ligne is not None:
            t = t[t["ligne"] == ligne]
        ts.append(t[colonnes] if colonnes else t)
        del x
    t = pd.concat(ts, ignore_index=True) if ts else pd.DataFrame(columns=colonnes)
    return t, (min(debut), max(fin)) if debut else (0, 0), lev


def force(r, ri) -> float | None:
    dd = (np.asarray(r) - np.asarray(ri)) / 2
    if len(dd) < 10 or dd.std(ddof=1) <= 0:
        return None
    return float(dd.mean() / dd.std(ddof=1) * math.sqrt(len(dd)))


def mesures(g: pd.DataFrame, semaines: float) -> dict:
    an = pd.to_datetime(g["entree"]).dt.year
    r = g["R"].to_numpy()
    n = len(r)
    x = {"trades": n, "trades_semaine": n / semaines if semaines > 0 else None}
    if n == 0:
        return x
    x.update({"gagnants_pct": float((r > 0).mean() * 100), "R_moyen": float(r.mean()), "R_median": float(np.median(r)),
              "force": force(r, g["R_inverse"]), "R_moyen_sans_nuit": float(g["R_sans_nuit_0"].mean()),
              "nuit_R_moyen": float(g["nuit_R_0"].mean()), "frais_entree_R_moyen": float(g["c0"].mean()),
              "trades_10R": int((r >= 10).sum()), "ecart_controle_max": float(g["ecart_controle"].max())})
    ent = pd.to_datetime(g["entree"])
    x["periodes"] = {}
    for p, (de, a) in PERIODES.items():
        m = ((ent >= de) & (ent < a)).to_numpy()
        x["periodes"][p] = {"trades": int(m.sum()), "R_moyen": float(r[m].mean()) if m.any() else None,
                            "force": force(r[m], g["R_inverse"].to_numpy()[m])}
    m = (ent < "2024-01-01").to_numpy()
    x["avant_2024"] = {"trades": int(m.sum()), "R_moyen": float(r[m].mean()) if m.any() else None,
                       "force": force(r[m], g["R_inverse"].to_numpy()[m])}
    x["annees"] = {}
    for a in ANNEES:
        m = (an == a).to_numpy()
        x["annees"][str(a)] = {"trades": int(m.sum()), "R_moyen": float(r[m].mean()) if m.any() else None}
    return x


def choisir(res: dict) -> list:
    """Règle écrite avant (en-tête) : meilleur R moyen avant 2024, >= 100 trades et R > 0 avant 2024 ; + sa démo."""
    cand = []
    for gr, x in res.items():
        for ligne, y in x["lignes"].items():
            a = y.get("avant_2024", {})
            if a.get("trades", 0) >= 100 and (a.get("R_moyen") or -9) > 0 and y["trades"] <= MAX_TRADES_COMPTE:
                cand.append((a["R_moyen"], gr, ligne))
    cand.sort(reverse=True)
    choix = [(gr, ligne) for _, gr, ligne in cand[:3]]
    if SA_DEMO not in choix:
        choix.append(SA_DEMO)
    return choix


def juger():
    VIE.mkdir(parents=True, exist_ok=True)
    res = {}
    for groupe, titre in GROUPES.items():
        t, (de, a), _ = charger(groupe)
        if not len(t):
            print(f"{groupe} : pas calculé", flush=True)
            continue
        semaines = (a - de) / (7 * 86400e9)
        x = {"titre": titre, "marches": int(t["marche"].nunique()), "debut": str(pd.Timestamp(de)),
             "fin": str(pd.Timestamp(a)), "semaines": semaines, "lignes": {}}
        for ligne, g in t.groupby("ligne", sort=True):
            y = mesures(g, semaines)
            y["avant_corrections"] = AVANT.get(groupe, {}).get(ligne, "non publié")
            x["lignes"][ligne] = y
            p = y["periodes"]
            print(f"{groupe:7s} {ligne:32s} | {y['trades']:6d} tr {y['trades_semaine']:6.2f}/sem | gagn "
                  f"{y['gagnants_pct']:4.0f} % | R {y['R_moyen']:+.3f} méd {y['R_median']:+.2f} | force "
                  f"{(y['force'] if y['force'] is not None else float('nan')):+.2f} | "
                  + " / ".join(f"{(p[k]['R_moyen'] if p[k]['R_moyen'] is not None else float('nan')):+.2f}"
                               f" ({p[k]['trades']})" for k in ("avant 2022", "2022-2023", "2024-2026"))
                  + f" | ans " + " ".join(f"{(v['R_moyen'] if v['R_moyen'] is not None else float('nan')):+.2f}"
                                           for v in y["annees"].values())
                  + f" | avant : {y['avant_corrections']}", flush=True)
        res[groupe] = x
        del t
        gc.collect()
    sortie = {"quand": datetime.now().isoformat(timespec="seconds"), "groupes": res, "choix_compte": choisir(res)}
    _ecrire(VIE / "resultats.json", sortie)
    print("lignes choisies pour le compte :", sortie["choix_compte"], flush=True)


# ---------------------------------------------------------------- compte FTMO
def pas_de(t_ny) -> np.ndarray:
    return (np.asarray(t_ny, np.int64) + H7 - T0.value) // PAS


def preparer_compte(groupe: str, ligne: str):
    """Tableaux du compte pour une ligne : trades triés par remplissage, sorties par tiers datées à la bougie de 15 min,
    chemins (pire / clôture) en R de chaque trade."""
    t, _, lev = charger(groupe, colonnes=None, ligne=ligne)
    t = t.sort_values(["fill_ny", "marche"]).reset_index(drop=True)
    n = len(t)
    fill = pas_de(t["fill_ny"].to_numpy(np.int64))
    ex = np.zeros((n, 2, 3), np.int64)
    rp = np.zeros((n, 2, 3))
    offs = np.zeros(n, np.int64)
    lens = np.zeros(n, np.int64)
    lo_l, hi_l, cl_l = [], [], []
    pos = 0
    for nom, idx in t.groupby("marche").groups.items():
        z = np.load(BARRES / f"{groupe}_{nom}.npz")
        st = pas_de(z["bt"])
        s0, s1 = int(st.min()), int(st.max())
        C = np.full(s1 - s0 + 1, np.nan)
        L, Hh = C.copy(), C.copy()
        C[st - s0], L[st - s0], Hh[st - s0] = z["c"], z["l"], z["h"]
        C = pd.Series(C).ffill().to_numpy()
        trou = ~np.isfinite(L)
        L[trou], Hh[trou] = C[trou], C[trou]
        for j in np.asarray(idx):
            r = t.loc[j]
            e, risque, d = float(r["prix"]), float(r["risque"]), int(r["sens"])
            w = max(1, int(r["duree_unite"]) // PAS)
            fin_j = int(fill[j])
            for g in (0, 1):
                s = d if g == 0 else -d
                for q in range(3):
                    tq, pq, kq = int(r[f"t{g}{q}"]), float(r[f"p{g}{q}"]), int(r[f"k{g}{q}"])
                    a = int(pas_de(tq))
                    es = a
                    if kq != 2:
                        lo_, hi_ = max(a - s0, 0), min(a - s0 + w, len(C))
                        if hi_ > lo_:
                            seg_l, seg_h = L[lo_:hi_], Hh[lo_:hi_]
                            adverse = (kq == 1)
                            touche = ((seg_l <= pq) if (s > 0) == adverse else (seg_h >= pq))
                            es = s0 + lo_ + (int(np.argmax(touche)) if touche.any() else hi_ - lo_ - 1)
                    es = max(es, int(fill[j]))
                    ex[j, g, q] = es
                    rp[j, g, q] = float(r[f"r{g}{q}"])
                    fin_j = max(fin_j, es)
            a0, a1 = int(fill[j]) - s0, fin_j - s0 + 1
            a0c, a1c = max(a0, 0), min(a1, len(C))
            if a1c <= a0c:
                seg = np.full(1, e)
                sl = sh = sc = seg
            else:
                sl, sh, sc = L[a0c:a1c], Hh[a0c:a1c], C[a0c:a1c]
            lo_l.append(((sl - e) / risque).astype(np.float32))
            hi_l.append(((sh - e) / risque).astype(np.float32))
            cl_l.append(((sc - e) / risque).astype(np.float32))
            offs[j], lens[j] = pos, len(sl)
            pos += len(sl)
        del z, C, L, Hh
    lo, hi, cl = (np.concatenate(x) if x else np.zeros(1, np.float32) for x in (lo_l, hi_l, cl_l))
    # l'ordre des trades dans les chemins suit les groupes par marché : offs/lens sont rangés par index de trade
    sf = (t["risque"] / t["prix"]).to_numpy(float)
    levier = t["marche"].map(lev).to_numpy(float)
    controle = float(np.abs(rp[:, 0, :].sum(1) - t["c0"].to_numpy() - t["R"].to_numpy()).max())
    return {"t": t, "fill": fill.astype(np.int64), "ex": ex, "rp": rp, "c0": t["c0"].to_numpy(float),
            "sens": t["sens"].to_numpy(np.int64), "sf": sf, "lev": levier, "off": offs, "len": lens,
            "lo": lo, "hi": hi, "cl": cl, "controle_R": controle}


@njit(cache=True)
def simuler(fill, ex, rp, c0, sens, sf, lev, off, ln, lo, hi, cl, signes, r0, maxpos, debut, fin, mode):
    """mode 0 : compte continu de `debut` à `fin` (rien ne l'arrête) ; mode 1 : challenge (+10 % puis +5 %, mort au pire
    point à -5 % du jour ou -10 %). Rend (issue 0 réussi / 1 mort étape 1 / 2 mort étape 2 / 3 inachevé, fonds à la fin,
    baisse max, trades pris, signaux ignorés, pas de fin)."""
    n = len(fill)
    s_t = np.full(maxpos, -1, np.int64)
    s_r = np.zeros(maxpos)
    s_m = np.zeros(maxpos)
    s_o = np.zeros((maxpos, 3), np.bool_)
    cap = 100000.0
    solde = cap
    pic = cap
    baisse = 0.0
    ref = cap
    phase = 1
    cible = 0.10
    jours = 0
    dernier = -1
    issue = 3
    nb = 0
    ign = 0
    eqc = cap
    jour_courant = -1
    ptr = np.searchsorted(fill, debut)
    k = debut
    while k < fin:
        jour = k // 96
        if jour != jour_courant:
            ref = solde
            jour_courant = jour
        # sorties de la bougie
        for p in range(maxpos):
            t = s_t[p]
            if t >= 0:
                g = 0 if signes[t] > 0 else 1
                reste = False
                for q in range(3):
                    if s_o[p, q]:
                        if ex[t, g, q] <= k:
                            solde += s_r[p] * rp[t, g, q]
                            s_o[p, q] = False
                        else:
                            reste = True
                if not reste:
                    s_t[p] = -1
        # fonds et marge avant les entrées
        eqc = solde
        utilise = 0.0
        npos = 0
        for p in range(maxpos):
            t = s_t[p]
            if t >= 0:
                npos += 1
                se = sens[t] * signes[t]
                i = off[t] + min(k - fill[t], ln[t] - 1)
                m = cl[i] * se
                for q in range(3):
                    if s_o[p, q]:
                        eqc += s_r[p] * m / 3.0
                utilise += s_m[p]
        # entrées
        while ptr < n and fill[ptr] < k:
            ptr += 1
        while ptr < n and fill[ptr] == k:
            t = ptr
            ptr += 1
            if npos >= maxpos:
                ign += 1
                continue
            rd = r0 * solde
            besoin = rd / sf[t] / lev[t]
            libre = eqc - utilise
            if besoin > libre:
                rd = rd * libre / besoin if libre > 0 else 0.0
                besoin = max(libre, 0.0)
            if rd <= 0.0:
                ign += 1
                continue
            for p in range(maxpos):
                if s_t[p] < 0:
                    s_t[p] = t
                    s_r[p] = rd
                    s_m[p] = besoin
                    for q in range(3):
                        s_o[p, q] = True
                    break
            solde -= rd * c0[t]
            eqc -= rd * c0[t]
            utilise += besoin
            npos += 1
            nb += 1
            if jour != dernier:
                jours += 1
                dernier = jour
        # marquage au pire prix de la bougie et à la clôture
        pire = solde
        eqc = solde
        for p in range(maxpos):
            t = s_t[p]
            if t >= 0:
                se = sens[t] * signes[t]
                i = off[t] + min(k - fill[t], ln[t] - 1)
                w = lo[i] if se > 0 else -hi[i]
                m = cl[i] * se
                for q in range(3):
                    if s_o[p, q]:
                        pire += s_r[p] * w / 3.0
                        eqc += s_r[p] * m / 3.0
        if (pire - pic) / pic < baisse:
            baisse = (pire - pic) / pic
        if eqc > pic:
            pic = eqc
        if mode == 1:
            if pire <= ref - 0.05 * cap or pire <= 0.90 * cap:
                issue = phase
                break
            if eqc >= cap * (1.0 + cible) and jours >= 4:
                if phase == 2:
                    issue = 0
                    break
                phase = 2
                cible = 0.05
                for p in range(maxpos):
                    s_t[p] = -1
                solde = cap
                pic = cap
                jours = 0
                dernier = -1
                k = (jour + 1) * 96
                jour_courant = -1
                continue
        ouvert = False
        for p in range(maxpos):
            if s_t[p] >= 0:
                ouvert = True
        if ouvert:
            k += 1
        else:
            prochain = fill[ptr] if ptr < n else fin
            k = max(prochain, k + 1)
    res = np.zeros(6)
    res[0], res[1], res[2], res[3], res[4], res[5] = issue, eqc, baisse, nb, ign, k
    return res


def bilan_challenges(r: np.ndarray, departs: np.ndarray) -> dict:
    issue = r[:, 0]
    fini = issue != 3
    reussi = issue == 0
    mort = (issue == 1) | (issue == 2)
    nf = int(fini.sum())
    duree = (r[:, 5] - departs) / 96 / 30.44
    return {"departs": int(len(r)), "termines": nf, "inacheves": int((~fini).sum()),
            "reussis_parmi_termines_pct": float(reussi.sum() / nf * 100) if nf else None,
            "morts_parmi_termines_pct": float(mort.sum() / nf * 100) if nf else None,
            "reussis_pct_de_tous": float(reussi.mean() * 100) if len(r) else None,
            "mois_median_reussite": float(np.median(duree[reussi])) if reussi.any() else None}


def moyenne(lst: list) -> dict:
    out = {}
    for k in lst[0]:
        v = [x[k] for x in lst if x.get(k) is not None]
        out[k] = float(np.mean(v)) if v else None
    return out


def compte():
    res = json.loads((VIE / "resultats.json").read_text(encoding="utf-8"))
    sortie = {"quand": datetime.now().isoformat(timespec="seconds"), "lignes": {}}
    for groupe, ligne in res["choix_compte"]:
        n_tr = res["groupes"][groupe]["lignes"][ligne]["trades"]
        cle = f"{groupe} | {ligne}"
        if n_tr > MAX_TRADES_COMPTE:
            sortie["lignes"][cle] = {"note": f"{n_tr} trades : non simulé (mémoire)"}
            continue
        t0 = datetime.now()
        D = preparer_compte(groupe, ligne)
        fill = D["fill"]
        fin_donnees = int(max(D["ex"].max(), fill.max()) + 1)
        a = (D["fill"], D["ex"], D["rp"], D["c0"], D["sens"], D["sf"], D["lev"], D["off"], D["len"], D["lo"], D["hi"],
             D["cl"])
        rng = np.random.default_rng(7)
        jum = [rng.choice(np.array([-1, 1], np.int64), len(fill)) for _ in range(JUMEAUX)]
        vrai = np.ones(len(fill), np.int64)
        x = {"trades": int(len(fill)), "controle_R_max": D["controle_R"], "par_risque": {}}
        for r0 in RISQUES:
            y = {"comptes": {}, "challenges": {}}
            for p, (de, a_) in PERIODES.items():
                d0 = max(int(pas_de(pd.Timestamp(de).value - H7)), int(fill.min()) // 96 * 96)
                d1 = min(int(pas_de(pd.Timestamp(a_).value - H7)), fin_donnees)
                if d1 <= d0:
                    continue
                r = simuler(*a, vrai, r0, MAXPOS, d0, d1, 0)
                mois = (d1 - d0) / 96 / 30.44
                y["comptes"][p] = {"mois": mois, "fonds_fin": float(r[1]),
                                   "pct_mois": float(((r[1] / CAPITAL) ** (1 / mois) - 1) * 100),
                                   "baisse_max_pct": float(r[2] * 100), "trades_pris": int(r[3]),
                                   "ignores": int(r[4])}
            departs = np.arange(int(fill.min()) // 96, fin_donnees // 96, 10) * 96
            vr = np.array([simuler(*a, vrai, r0, MAXPOS, int(d), fin_donnees, 1) for d in departs])
            jr = [np.array([simuler(*a, s, r0, MAXPOS, int(d), fin_donnees, 1) for d in departs]) for s in jum]
            dates = T0 + pd.to_timedelta(departs * 15, unit="min")
            for p, (de, a_) in PERIODES.items():
                m = np.asarray((dates >= de) & (dates < a_))
                if not m.any():
                    continue
                y["challenges"][p] = {"vrai": bilan_challenges(vr[m], departs[m]),
                                      "jumeaux": moyenne([bilan_challenges(j[m], departs[m]) for j in jr])}
            x["par_risque"][str(r0)] = y
            c, ch = y["comptes"].get("tout", {}), y["challenges"].get("tout", {})
            print(f"{cle} | risque {r0 * 100:.2f} % | {c.get('pct_mois', float('nan')):+.2f} %/mois | baisse "
                  f"{c.get('baisse_max_pct', float('nan')):.1f} % | challenges {ch.get('vrai')} | jumeaux "
                  f"{ch.get('jumeaux')}", flush=True)
        x["avant_corrections"] = AVANT_COMPTE.get(ligne) if groupe == "crypto" else None
        sortie["lignes"][cle] = x
        print(f"{cle} : {(datetime.now() - t0).seconds} s, contrôle R {D['controle_R']:.1e}", flush=True)
        _ecrire(VIE / "compte.json", sortie)
        del D, a
        gc.collect()
    _ecrire(VIE / "compte.json", sortie)


# ---------------------------------------------------------------- vérification des frais (avant de calculer)
def verifier_frais():
    from collapsar.regarder.pistes import crypto_flux
    from collapsar.regarder.smc import bougies as BG
    out = {"MARGE_PRUDENCE_frais_ftmo": FF.MARGE_PRUDENCE, "chef_compte_ftmo_GLISSEMENT": CF.GLISSEMENT,
           "noyaux_GLISSEMENT_STOP_fiche": K.GLISSEMENT_STOP, "noyaux_GLISSEMENT_MARCHE_fiche": K.GLISSEMENT_MARCHE,
           "convention": "entrée limite = 1/2 frais x facteur d'ouverture ; objectif = 1/2 frais ; stop = frais entiers",
           "marches": {}}
    jours = {"relevé (prix du 15/10/2026)": None, "prix du 03/06/2019": pd.Timestamp("2019-06-03")}
    for nom, sym in (("or", "XAUUSD"), ("US500", "USA500IDXUSD"), ("Nasdaq", "USATECHIDXUSD"), ("euro-dollar", "EURUSD"),
                     ("BTC (Dukascopy, 47 marchés)", "BTCUSD")):
        x = {}
        for k, j in jours.items():
            p = FF._prix_au_releve(sym) if j is None else float(dm.charger(sym, j)["close"].iloc[-1])
            fr = float(np.asarray(FF.frais(sym, p)))
            x[k] = {"prix": p, "aller_retour_pct": fr * 100, "trade_objectif_pct": fr * 100,
                    "trade_stop_pct": fr * 1.5 * 100}
        f = fiche(sym)
        ta, tv = taux_nuit(f, pd.DatetimeIndex([pd.Timestamp("2026-10-15"), pd.Timestamp("2019-06-03")]))
        x["nuit_achat_vente_%an_2026"] = [float(ta[0]) * 100, float(tv[0]) * 100]
        x["nuit_achat_vente_%an_2019"] = [float(ta[1]) * 100, float(tv[1]) * 100]
        x["nuit_triple"] = {2: "mercredi", 4: "vendredi", -1: "calendrier"}[ZR.jour_triple(sym)]
        x["facteur_ouverture_NY"] = {"USA500IDXUSD": 1.16, "USATECHIDXUSD": 1.07}.get(
            sym, 1.1 if f.famille == "indice" else 1.0)
        x["levier_FTMO"] = f.levier
        out["marches"][nom] = x
    for c in ("BTC", "ETH", "ADA", "SOL"):
        out["marches"][f"{c} (Binance, groupe cryptos)"] = {"aller_retour_pct": frais_crypto(c) * 100,
                                                            "nuit_%an": CC.NUIT_AN * 100, "nuit_triple": "vendredi"}
    out["non_utilises_ici"] = {
        "chef_crypto.FRAIS (SANS commission, utilisé par direct/chef_zones.py, non modifié)":
            {k: v * 100 for k, v in CC.FRAIS.items()},
        "bougies.FRAIS du labo (contrôle seulement)": {k: v * 100 for k, v in BG.FRAIS.items()},
        "chef_compte_ftmo.frais (ETH 0,095 % : écart forfaitaire 0,03 %)": {c: CF.frais(c) * 100 for c in ("BTC", "ETH",
                                                                                                         "ADA")},
        "crypto_flux.frais": {c: crypto_flux.frais(c + "USDT") * 100 for c in ("BTC", "ETH", "ADA")}}
    VIE.mkdir(parents=True, exist_ok=True)
    _ecrire(VIE / "frais.json", out)
    print(json.dumps(out, ensure_ascii=False, indent=1, default=str), flush=True)


def _ecrire(f, obj):
    f.write_text(json.dumps(obj, ensure_ascii=False, indent=1, default=str), encoding="utf-8")


if __name__ == "__main__":
    VIE.mkdir(parents=True, exist_ok=True)
    a = sys.argv[1] if len(sys.argv) > 1 else "juger"
    if a == "calculer":
        calculer(sys.argv[2])
    else:
        {"frais": verifier_frais, "juger": juger, "compte": compte}[a]()
