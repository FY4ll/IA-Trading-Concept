"""LA LOGIQUE INVERSÉE (18/10/2026, chef de projet : « des trades à 2R positifs »).

Étude précédente (vie/hypernova/direction/) : filtrer les trades posés sur ses zones par une source de direction ramène
à zéro, pas au-dessus ; le signal C1 vaut 24 h alors que les trades sur zone durent ~100 h. Ici on RETOURNE la logique :
la SOURCE choisit le MOMENT et le SENS ; la STRUCTURE (ses zones, les creux / sommets) sert seulement à placer le stop
(et l'entrée d'un ordre limite) ; l'objectif est 2R (ou 3R) ; une sortie au temps ferme le trade comme le signal
d'origine (24 h pour C1, fin de journée pour C2).

Mesure SANS IA, liste FIGÉE (`VARIANTES`, `TEMOINS`, écrites dans plan_fige.md AVANT toute mesure). Chaque trade est
joué par le moteur de l'école « juger un trade » (juge_trade.un_trade = simulateur de l'arbre : ordre à l'ouverture
suivante, écart payé, bougie d'exécution jugée au pire, stop d'abord + glissement, nuits, frais FTMO du 16/10).
Sélection : instants < 2024 (2020-2023 selon les données de la foule) ; contrôle UNE fois : 01/2024 -> 09/2025, pour la
seule variante retenue (+ ses comparaisons). Rien après 09/2025.

Depuis Test_IA : venv_gpu\\Scripts\\python.exe -u -m collapsar.regarder.pistes.logique_inversee plan|selection|controle|rapport
"""
from __future__ import annotations

import argparse
import json
import math
import time
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from numba import njit

from collapsar.ecole.precision import direction as DI
from collapsar.ecole.precision import juge_trade as JT
from collapsar.ecole.precision.reglages import VIE, R

SORTIE = VIE / "logique_inversee"
QUINZE_NS = 15 * 60 * 10 ** 9
HEURE_NS = 3600 * 10 ** 9
JOUR_NS = 86400 * 10 ** 9
SEMAINE_NS = 7 * JOUR_NS
MOIS_NS = 30.4375 * JOUR_NS

# ---------------------------------------------------------------------------------------------- LISTE FIGÉE
N_LIMITE_A = 1.0           # ordre limite : bord proche de la zone à 1 agitation au plus du prix
STOP_MIN_A = 0.25          # la structure du stop est à au moins 0,25 agitation derrière le prix (ou l'entrée)
STOP_MAX_A = 2.0           # risque (entrée -> stop) de 2 agitations au plus, sinon pas de trade
MARGE_A = 0.1              # marge derrière la structure
VALIDITE = 96              # ordre limite valable 24 h (et au plus jusqu'à la sortie au temps)
RETARD_MAX_NS = HEURE_NS   # un signal pris plus d'1 h après son heure (bougies manquantes) est ignoré
TENUE_NS = 24 * HEURE_NS
C2_SORTIE_NS = DI.C2_FIN_MIN * 60 * 10 ** 9        # 23h45 (heure du serveur)
UNITES_SOMMETS = ("H1", "H4")

PERIODES = {"selection": ("2020-01-01", "2024-01-01"), "controle": ("2024-01-01", "2025-10-01")}
NOM_P = {"selection": "2020-2023 (sélection)", "controle": "01/2024 -> 09/2025 (contrôle, une seule fois)"}

DECLENCHEURS = {
    "C1": "contre la foule (C1) : part des acheteurs Binance au-dessus de son centile 95 des 90 j -> vente, sous le "
          "centile 5 -> achat (19 cryptos) ; sortie au temps 24 h après le signal",
    "C2": "cassure 24 h (C2) : clôture de l'heure au-delà du plus haut / plus bas des 24 h, lun-ven à l'heure pleine "
          "(BTC, ETH) ; sortie au temps à 23h45 (fin de journée du serveur)",
    "T": "TÉMOIN tendance de fond seule : 20, 60 et 120 jours d'accord, chaque jour à 00h00 du serveur (19 cryptos) ; "
         "sortie au temps 24 h",
}
PLACEMENTS = {
    "MZ": "au marché ; stop derrière la zone la plus proche (bord lointain d'une de ses zones vivantes du bon côté, "
          "toutes unités) + 0,1 agitation",
    "MS": "au marché ; stop derrière le creux (achat) / sommet (vente) confirmé le plus proche de l'unité 1 h ou 4 h "
          "+ 0,1 agitation",
    "LZ": "ordre limite sur le bord proche de la zone vivante la plus proche dans le bon sens (à 1 agitation au plus, "
          "valable 24 h et au plus jusqu'à la sortie au temps) ; stop derrière cette zone + 0,1 agitation",
}
OBJECTIFS = (2, 3)
VARIANTES = [(d, p, o) for d in ("C1", "C2") for p in PLACEMENTS for o in OBJECTIFS]      # éligibles (12)
TEMOINS = [("T", p, o) for p in PLACEMENTS for o in OBJECTIFS]                           # témoins (6)
N_DEJA = 43                                       # cases déjà jugées (vie/hypernova/direction)
N_TOTAL = N_DEJA + len(VARIANTES) + len(TEMOINS) + 2 + 2   # + jumeau, sans structure, 2 comptes FTMO
SEUIL = max(3.0, math.sqrt(2 * math.log(N_TOTAL)))
MIN_TRADES = 100                                  # une variante doit avoir >= 100 trades exécutés en sélection
TIRAGES = 200                                     # jumeaux du compte FTMO


def vid(v) -> str:
    return f"{v[0]}-{v[1]}-{v[2]}R"


def marches_de(d: str) -> tuple[str, ...]:
    return tuple(DI.C2_MARCHES) if d == "C2" else tuple(R().marches.cryptos_binance)


def plan_texte() -> str:
    L = [f"# LOGIQUE INVERSÉE — plan FIGÉ avant toute mesure ({datetime.now():%d/%m/%Y %H:%M})", "",
         "La source choisit le MOMENT et le SENS ; la structure place seulement le stop (et l'entrée d'un ordre limite). "
         "Moteur : juge_trade.un_trade (= simulateur de l'arbre, frais FTMO du 16/10, glissement du stop, nuits, bougie "
         "d'exécution au pire). Décision à la clôture de la 1re bougie de 15 min qui suit le signal (1 h de retard au "
         "plus), entrée au marché à l'ouverture suivante.", "",
         "## Déclencheurs", ""]
    L += [f"- **{k}** : {v}" for k, v in DECLENCHEURS.items()]
    L += ["", "## Placements (structure SANS FUTUR : structure.py, lue à la ligne de la décision)", ""]
    L += [f"- **{k}** : {v}" for k, v in PLACEMENTS.items()]
    L += ["", f"Règles communes : structure à au moins {STOP_MIN_A} agitation derrière le prix (ou l'entrée) et plus d'un "
          f"aller-retour de frais ; risque de {STOP_MAX_A} agitations au plus ; marge {MARGE_A} agitation ; pas de "
          "structure valable = pas de trade. Un seul trade à la fois par variante et par marché (un signal qui arrive "
          "pendant un trade ou un ordre en attente est ignoré).", "",
          "Sortie : objectif 2R (ou 3R) mesuré depuis l'entrée RÉELLE, stop, ou sortie au temps (à l'ouverture de la "
          "1re bougie à / après l'heure de sortie), au premier des trois.", "",
          "## Liste des variantes", "", "| n° | variante | déclencheur | placement | objectif | rôle |", "|---|---|---|---|---|---|"]
    for i, v in enumerate(VARIANTES + TEMOINS, 1):
        L.append(f"| {i} | {vid(v)} | {v[0]} | {v[1]} | {v[2]}R | {'témoin' if v[0] == 'T' else 'éligible'} |")
    L += ["", "## Comparaisons (pour chaque variante)", "",
          "- **Jumeau** : mêmes trades (même instant, même type d'ordre, mêmes distances), sens tiré à pile ou face = "
          "moyenne du trade et de son retourné (entrée, stop retournés autour du prix de la décision). Avance = (R du "
          "trade - R du retourné) / 2 par signal (non exécuté = 0).",
          "- **Sans la structure** : même instant, même sens, même sortie ; stop à distance FIXE = médiane (sur 2020-2023, "
          "placements de la variante) du risque en agitations ; pour l'ordre limite, entrée aussi à la distance médiane.",
          "- **Témoin tendance** (T) : même placement et même objectif, moment = chaque jour, sens = tendance de fond.", "",
          "## Choix et jugement", "",
          f"- Choix sur 2020-2023 SEULEMENT : parmi les 12 éligibles avec au moins {MIN_TRADES} trades exécutés, la plus "
          "grande FORCE (R moyen frais compris / incertitude, grappes = semaines, tous marchés ensemble).",
          "- Jugement UNE fois sur 01/2024 -> 09/2025 : la retenue, son jumeau, sa version sans la structure, le témoin T "
          "de même placement et même objectif ; compte FTMO 100 000 $ à 0,25 % et 0,5 % de risque par trade (gain / mois, "
          "baisse max, challenges réussis / morts parmi les terminés, un départ tous les 7 jours, contre 200 jumeaux).",
          f"- N total = {N_DEJA} déjà jugées + {len(VARIANTES)} variantes + {len(TEMOINS)} témoins + 2 comparaisons + 2 "
          f"comptes = {N_TOTAL} -> seuil de preuve max(3, racine(2 ln N)) = {SEUIL:.2f}.",
          "- PROUVÉ si R moyen > 0 sur 2024-2025 avec force >= seuil (et > 0 sur 2020-2023) ; PROMETTEUR (non prouvé) si "
          "> 0 sur les deux périodes avec force > 2 sur 2024-2025 ; sinon non.",
          "- Greffe préparée (éteinte, non appliquée) seulement si PROUVÉ ou PROMETTEUR."]
    return "\n".join(L) + "\n"


# ---------------------------------------------------------------------------------------------- la structure
def _unites(x: dict) -> list[str]:
    from collapsar.ecole.precision.reglages import UNITES
    return [u for u in UNITES if u in x]


def zones_cote(x: dict, r: int, cote: int) -> list[tuple[float, float]]:
    """(haut, bas) des zones vivantes du côté `cote` (0 = demande, 1 = offre), toutes unités, vues à la ligne r de 15 min
    (les 2 plus proches de chaque unité, structure.plus_proches)."""
    out = []
    for u in _unites(x):
        lg = int(x[u]["ligne"][r])
        if lg < 0:
            continue
        for z in np.asarray(x[u]["knn"][lg, cote]):
            z = int(z)
            if z >= 0 and int(x[u]["vis"][z]) <= r:
                out.append((float(x[u]["top"][z]), float(x[u]["bot"][z])))
    return out


def sommets_cote(x: dict, r: int, sens: int) -> list[float]:
    """Les 2 derniers creux (achat) ou sommets (vente) confirmés des unités 1 h et 4 h, vus à la ligne r."""
    out = []
    for u in UNITES_SOMMETS:
        if u not in x:
            continue
        lg = int(x[u]["ligne"][r])
        if lg < 0:
            continue
        sw = np.asarray(x[u]["sw"][lg], np.float64)
        for v in (sw[2:4] if sens > 0 else sw[0:2]):
            if np.isfinite(v):
                out.append(float(v))
    return out


def placer(x: dict, r: int, sens: int, placement: str):
    """(limite, entrée, stop) du placement à la décision de la ligne r (clôture de la bougie r), ou None. Ne lit que la
    ligne r des tableaux de structure.py (déjà sans futur)."""
    p, A = float(x["c"][r]), float(x["A"][r])
    if not (np.isfinite(A) and A > 0 and np.isfinite(p)):
        return None
    fr = 2 * float(x["demi"][r]) * p
    sg = 1.0 if sens > 0 else -1.0
    marge = MARGE_A * A
    dmin = max(fr, STOP_MIN_A * A)
    if placement in ("MZ", "MS"):
        if placement == "MZ":
            niv = [(b if sg > 0 else t) for t, b in zones_cote(x, r, 0 if sg > 0 else 1)]
        else:
            niv = sommets_cote(x, r, int(sg))
        best = None
        for v in niv:
            d = sg * (p - v)
            if d >= dmin and d + marge <= STOP_MAX_A * A and (best is None or d < best[0]):
                best = (d, v)
        if best is None:
            return None
        return False, p, best[1] - sg * marge
    # LZ : bord proche de la zone la plus proche (côté demande pour un achat, offre pour une vente)
    best = None
    for t, b in zones_cote(x, r, 0 if sg > 0 else 1):
        e, loin = (t, b) if sg > 0 else (b, t)
        de = sg * (p - e)
        st = loin - sg * marge
        rd = sg * (e - st)
        if de > fr and de <= N_LIMITE_A * A and sg * (e - loin) >= dmin and rd <= STOP_MAX_A * A and \
                (best is None or de < best[0]):
            best = (de, e, st)
    if best is None:
        return None
    return True, best[1], best[2]


# ---------------------------------------------------------------------------------------------- les déclencheurs
def _periode_ns(periode: str) -> tuple[int, int]:
    de, a = PERIODES[periode]
    return pd.Timestamp(de).value, pd.Timestamp(a).value


def declencheurs(d: str, nom: str, t15: np.ndarray, de_ns: int, a_ns: int):
    """(ligne de décision r, sens, heure de sortie au temps [serveur, ns]) des signaux de `d` dont la décision tombe dans
    [de, a). Décision = clôture de la 1re bougie de 15 min close à / après le signal (retard d'1 h au plus)."""
    t15 = np.asarray(t15, np.int64)
    dec = t15 + QUINZE_NS
    vide = (np.zeros(0, np.int64), np.zeros(0, np.int8), np.zeros(0, np.int64))
    if d == "C2":
        deb, _, s = DI._c2(nom)
        r = np.searchsorted(dec, deb, side="left")
        ok = r < len(dec)
        r = np.clip(r, 0, len(dec) - 1)
        ok &= (dec[r] >= deb) & (dec[r] - deb <= RETARD_MAX_NS)
        sortie = deb - deb % JOUR_NS + C2_SORTIE_NS
    elif d == "C1":
        from collapsar.ecole.precision import foule as FO
        deb, _, s = DI._c1(nom)                                           # heure UTC
        if not len(deb):
            return vide
        utc = FO.serveur_vers_utc_ns(pd.DatetimeIndex(dec.astype("datetime64[ns]")))
        sm = np.minimum.accumulate(utc[::-1])[::-1]                      # toutes les décisions suivantes sont >= sm
        r = np.searchsorted(sm, deb, side="left")
        ok = r < len(dec)
        r = np.clip(r, 0, len(dec) - 1)
        ok &= (utc[r] >= deb) & (utc[r] - deb <= RETARD_MAX_NS)
        sortie = dec[r] + TENUE_NS
    elif d == "T":
        j = np.unique(dec - dec % JOUR_NS)
        j = j[(j >= de_ns - JOUR_NS) & (j < a_ns)]
        r = np.searchsorted(dec, j, side="left")
        ok = r < len(dec)
        r = np.clip(r, 0, len(dec) - 1)
        ok &= (dec[r] >= j) & (dec[r] - j <= RETARD_MAX_NS) & (dec[r] >= de_ns) & (dec[r] < a_ns)
        r = r[ok]
        sg, _ = DI.tendance(nom, dec[r])
        s = np.where((sg[:, 0] == sg[:, 1]) & (sg[:, 1] == sg[:, 2]), sg[:, 0], 0).astype(np.int8)
        ok = s != 0
        sortie = dec[r] + TENUE_NS
    else:
        raise ValueError(d)
    ok &= (dec[r] >= de_ns) & (dec[r] < a_ns)
    return r[ok].astype(np.int64), np.asarray(s)[ok].astype(np.int8), np.asarray(sortie)[ok].astype(np.int64)


# ---------------------------------------------------------------------------------------------- le chemin du prix
@njit(cache=True)
def jouer(o, h, l, c, fx, ouvert, derniere, demi, nuit_a, nuit_v, nuits, t, sens, limite, P, stop, dest_r, t_sortie,
          validite_max, gl):
    """Chaque trade joué par juge_trade.un_trade (= simulateur de l'arbre), avec une sortie au temps : fermé à
    l'ouverture de la bougie t_sortie s'il est encore ouvert. Un ordre limite vit au plus jusqu'à t_sortie - 1."""
    n = len(t)
    exe = np.zeros(n, np.bool_)
    ne = np.full(n, -1, np.int64)
    ns = np.full(n, -1, np.int64)
    rr = np.full(n, np.nan)
    code = np.zeros(n, np.int64)
    for i in range(n):
        ti = t[i]
        if t_sortie[i] <= ti + 1:
            code[i] = 32                                                     # REFUS
            ns[i] = ti + 1
            continue
        if limite[i]:
            v = min(validite_max, t_sortie[i] - ti - 1)
            e, a, b, r, cd = JT.un_trade(o, h, l, c, fx, ouvert, derniere, demi, nuit_a, nuit_v, nuits, ti, sens[i],
                                         True, P[i], stop[i], np.nan, dest_r[i], 0.0, 0.0, v, t_sortie[i] - ti, gl)
            if e:                                                            # même remplissage, sortie au temps exacte
                e, a, b, r, cd = JT.un_trade(o, h, l, c, fx, ouvert, derniere, demi, nuit_a, nuit_v, nuits, ti,
                                             sens[i], True, P[i], stop[i], np.nan, dest_r[i], 0.0, 0.0, v,
                                             t_sortie[i] - a, gl)
        else:
            e, a, b, r, cd = JT.un_trade(o, h, l, c, fx, ouvert, derniere, demi, nuit_a, nuit_v, nuits, ti, sens[i],
                                         False, np.nan, stop[i], np.nan, dest_r[i], 0.0, 0.0, 1, t_sortie[i] - ti - 1, gl)
        exe[i], ne[i], ns[i], rr[i], code[i] = e, a, b, r, cd
    return exe, ne, ns, rr, code


def garder_un_a_la_fois(t: np.ndarray, exe: np.ndarray, ns: np.ndarray, code: np.ndarray) -> np.ndarray:
    """Un seul trade (ou ordre en attente) à la fois : un signal dont la décision tombe pendant le précédent est ignoré.
    Fermé à l'ouverture d'une bougie (sortie au temps / pause) : on peut entrer à cette même ouverture."""
    garde = np.zeros(len(t), bool)
    libre = -1                                    # 1re bougie d'entrée permise
    for i in np.argsort(t, kind="stable"):
        if t[i] + 1 < libre:
            continue
        garde[i] = True
        if exe[i] or code[i] == JT.EXPIRE:
            libre = ns[i] + (0 if code[i] in (JT.HORIZON_C, JT.FORCEE) else 1)
    return garde


# ---------------------------------------------------------------------------------------------- calcul d'un marché
def geometries(x: dict, rows: np.ndarray, sens: np.ndarray, placement: str):
    lim = np.zeros(len(rows), bool)
    P = np.full(len(rows), np.nan)
    st = np.full(len(rows), np.nan)
    ok = np.zeros(len(rows), bool)
    for i, (r, s) in enumerate(zip(rows, sens)):
        g = placer(x, int(r), int(s), placement)
        if g is not None:
            ok[i] = True
            lim[i], P[i], st[i] = g
    return ok, lim, P, st


def medianes_placements(periode: str = "selection", dire=print) -> dict:
    """Médiane (en agitations) du risque et de la distance d'entrée de chaque (déclencheur, placement), sur TOUS les
    placements trouvés de la période (avant le « un à la fois ») : distances du témoin « sans la structure »."""
    from collapsar.ecole.precision import structure as S
    de_ns, a_ns = _periode_ns(periode)
    acc = {}
    for d in ("C1", "C2", "T"):
        for nom in marches_de(d):
            x = S.lire(nom, False)
            rows, sens, _ = declencheurs(d, nom, x["t15"], de_ns, a_ns)
            A = np.asarray(x["A"])[rows]
            p = np.asarray(x["c"])[rows]
            for pl in PLACEMENTS:
                ok, lim, P, st = geometries(x, rows, sens, pl)
                e = np.where(lim, P, p)
                a = acc.setdefault(f"{d}-{pl}", {"risque": [], "entree": []})
                a["risque"].append((sens * (e - st) / A)[ok])
                a["entree"].append((sens * (p - P) / A)[ok & lim])
        dire(f"médianes {d} : faites")
    out = {}
    for k, a in acc.items():
        rq, en = np.concatenate(a["risque"]), np.concatenate(a["entree"])
        out[k] = {"risque_A": float(np.median(rq)) if len(rq) else float("nan"),
                  "entree_A": float(np.median(en)) if len(en) else 0.0, "n": int(len(rq))}
    return out


def calculer_marche(nom: str, variantes: list, periode: str, medianes: dict, dire=print) -> dict:
    """Tous les trades des variantes sur un marché : la variante, son jumeau retourné, sa version sans la structure."""
    from collapsar.ecole.precision import structure as S
    from collapsar.ecole.precision.univers import Univers
    de_ns, a_ns = _periode_ns(periode)
    x = S.lire(nom, False)
    t15 = np.asarray(x["t15"], np.int64)
    debut = max(pd.Timestamp(int(t15[0])) + pd.Timedelta(days=45), pd.Timestamp(de_ns) - pd.Timedelta(days=5))
    U = Univers([(nom, False)], debut, R().periodes.fin_donnees, "cpu")
    ch = JT.chemin(U)
    gl = float(R().monde.frais_stop_glissement)
    trig = {}
    out = {}
    for v in variantes:
        d, pl, obj = v
        if nom not in marches_de(d):
            continue
        if d not in trig:
            trig[d] = declencheurs(d, nom, t15, de_ns, a_ns)
        rows, sens, sortie = trig[d]
        ok, lim, P, st = geometries(x, rows, sens, pl)
        rows, sens, sortie, lim, P, st = rows[ok], sens[ok], sortie[ok], lim[ok], P[ok], st[ok]
        tU = np.searchsorted(U.t_ns, t15[rows])
        assert np.array_equal(U.t_ns[np.clip(tU, 0, U.T - 1)], t15[rows]), nom
        tS = np.searchsorted(U.t_ns, sortie, side="left").astype(np.int64)
        p = U.c[tU, 0].astype(np.float64)
        A = U.A[tU, 0].astype(np.float64)
        sg = sens.astype(np.float64)
        dr = np.full(len(tU), float(obj))
        jouer_ = lambda li, PP, ss, sgn: jouer(*ch, tU.astype(np.int64), sgn, li, PP, ss, dr, tS, VALIDITE, gl)
        exe, ne, ns, rr, code = jouer_(lim, P, st, sg)
        g = garder_un_a_la_fois(tU, exe, ns, code)
        # le jumeau (géométrie retournée autour du prix de la décision) et la version sans la structure
        exe_j, ne_j, ns_j, rr_j, code_j = jouer_(lim, 2 * p - P, 2 * p - st, -sg)
        m = medianes[f"{d}-{pl}"]
        P_s = np.where(lim, p - sg * m["entree_A"] * A, p)
        st_s = np.where(lim, P_s, p) - sg * m["risque_A"] * A
        exe_s, ne_s, ns_s, rr_s, code_s = jouer_(lim, P_s, st_s, sg)
        e_ = np.where(lim, P, p)
        tn = lambda k: np.where(k >= 0, U.t_ns[np.clip(k, 0, U.T - 1)], -1)
        out[vid(v)] = {"dec_ns": (t15[rows] + QUINZE_NS)[g], "sens": sens[g], "limite": lim[g],
                       "risque_A": (sg * (e_ - st) / A)[g], "entree_A": (sg * (p - P) / A)[g],
                       "exe": exe[g], "r": rr[g], "code": code[g], "ne_ns": tn(ne)[g], "ns_ns": tn(ns)[g],
                       "exe_j": exe_j[g], "r_j": rr_j[g], "code_j": code_j[g], "ne_j_ns": tn(ne_j)[g], "ns_j_ns": tn(ns_j)[g],
                       "exe_s": exe_s[g], "r_s": rr_s[g], "code_s": code_s[g]}
    del U, ch
    return out


def calculer(variantes: list, periode: str, medianes: dict, dire=print) -> dict:
    """Toutes les variantes sur tous leurs marchés ; un fichier npz par variante et par période."""
    marches = sorted({n for v in variantes for n in marches_de(v[0])}, key=lambda n: list(R().marches.cryptos_binance).index(n))
    acc = {vid(v): [] for v in variantes}
    t0 = time.time()
    for im, nom in enumerate(marches):
        res = calculer_marche(nom, variantes, periode, medianes, dire)
        for k, v in res.items():
            v["marche"] = np.full(len(v["exe"]), im, np.int16)
            acc[k].append(v)
        dire(f"{periode} {nom} : " + ", ".join(f"{k} {int(v['exe'].sum())}" for k, v in res.items())
             + f" trades ({time.time() - t0:.0f} s)")
    dos = SORTIE / periode
    dos.mkdir(parents=True, exist_ok=True)
    out = {}
    for k, morceaux in acc.items():
        z = {c: np.concatenate([m[c] for m in morceaux]) for c in morceaux[0]}
        np.savez(dos / f"{k}.npz", **z)
        out[k] = z
    (dos / "marches.json").write_text(json.dumps(marches), encoding="utf-8")
    return out


def lire_trades(periode: str, k: str) -> dict:
    z = np.load(SORTIE / periode / f"{k}.npz")
    return {c: z[c] for c in z.files}


# ---------------------------------------------------------------------------------------------- mesure
def incertitude(x: np.ndarray, grappes: np.ndarray) -> float:
    n = len(x)
    if n < 2:
        return float("nan")
    r = x - x.mean()
    _, inv = np.unique(grappes, return_inverse=True)
    s = np.bincount(inv, weights=r)
    return float(np.sqrt((s ** 2).sum()) / n)


def mois_de(z: dict, periode: str) -> float:
    de_ns, a_ns = _periode_ns(periode)
    if not len(z["dec_ns"]):
        return float("nan")
    return (a_ns - max(de_ns, int(z["dec_ns"].min()))) / MOIS_NS


def bloc(z: dict, mois: float, obj: int, suffixe: str = "") -> dict:
    """Mesure des trades exécutés (frais compris ; trades encore ouverts à la fin des données exclus)."""
    exe, r, code = z["exe" + suffixe], z["r" + suffixe], z["code" + suffixe]
    ok = exe & (code != JT.FIN) & np.isfinite(r)
    n = int(ok.sum())
    if n == 0:
        return {"n_signaux": int(len(exe)), "n_exe": 0}
    rr = r[ok]
    hit = code[ok] == JT.DEST
    sem = z["dec_ns"][ok] // SEMAINE_NS
    W = rr[hit].mean() if hit.any() else float(obj)
    L = -rr[~hit].mean() if (~hit).any() else 1.0
    inc = incertitude(rr, sem)
    return {"n_signaux": int(len(exe)), "n_exe": n, "exe_pct": float(n / max(len(exe), 1) * 100),
            "trades_mois": float(n / mois), "achats_pct": float((z["sens"][ok] > 0).mean() * 100),
            "objectif_pct": float(hit.mean() * 100), "seuil_pct": float(L / (W + L) * 100) if (W + L) > 0 else float("nan"),
            "stop_pct": float((code[ok] == JT.STOP).mean() * 100),
            "temps_pct": float(np.isin(code[ok], (JT.HORIZON_C, JT.FORCEE)).mean() * 100),
            "r": float(rr.mean()), "inc": inc, "force": float(rr.mean() / inc) if inc > 0 else float("nan"),
            "mediane": float(np.median(rr))}


def avance(z: dict, autre: str, moitie: bool) -> dict:
    """Avance par signal sur une autre version des mêmes signaux (non exécuté = 0) ; moitie : (x - jumeau) / 2."""
    fin = (z["code"] == JT.FIN) | (z["code" + autre] == JT.FIN)
    x = np.where(z["exe"], np.nan_to_num(z["r"]), 0.0)[~fin]
    y = np.where(z["exe" + autre], np.nan_to_num(z["r" + autre]), 0.0)[~fin]
    d = (x - y) / (2 if moitie else 1)
    sem = z["dec_ns"][~fin] // SEMAINE_NS
    inc = incertitude(d, sem)
    return {"avance": float(d.mean()) if len(d) else float("nan"), "inc": inc,
            "force": float(d.mean() / inc) if inc and inc > 0 else float("nan")}


def mesurer_variante(z: dict, periode: str, obj: int) -> dict:
    mois = mois_de(z, periode)
    b = bloc(z, mois, obj)
    bj = bloc(z, mois, obj, "_j")
    bs = bloc(z, mois, obj, "_s")
    # jumeau à pile ou face = la moyenne du trade et de son retourné
    rj = (b.get("r", np.nan) * b.get("n_exe", 0) + bj.get("r", np.nan) * bj.get("n_exe", 0)) / max(
        b.get("n_exe", 0) + bj.get("n_exe", 0), 1)
    return {"mois": mois, "variante": b, "retourne": bj, "sans_structure": bs, "jumeau_r": float(rj),
            "avance_jumeau": avance(z, "_j", True), "avance_sans_structure": avance(z, "_s", False),
            "risque_A_median": float(np.median(z["risque_A"])) if len(z["risque_A"]) else float("nan"),
            "limites_remplies_pct": float(z["exe"][z["limite"]].mean() * 100) if z["limite"].any() else None}


# ---------------------------------------------------------------------------------------------- compte FTMO
@njit(cache=True)
def challenges(entree, sortie, gain, jour, departs, mur_jour, mur_total, objectif):
    """Pour chaque départ : 1 = réussi (+objectif), -1 = mort (mur du jour ou mur total), 0 = en cours à la fin.
    Trades triés par heure de sortie ; un trade compte s'il est ENTRÉ après le départ ; gains réalisés à la sortie."""
    nd = len(departs)
    etat = np.zeros(nd, np.int64)
    fin = np.zeros(nd, np.int64)
    for k in range(nd):
        s = departs[k]
        bal, js, jc = 0.0, 0.0, -1
        for i in range(len(gain)):
            if entree[i] < s:
                continue
            if jour[i] != jc:
                jc, js = jour[i], 0.0
            bal += gain[i]
            js += gain[i]
            if js <= -mur_jour or bal <= -mur_total:
                etat[k], fin[k] = -1, sortie[i]
                break
            if bal >= objectif:
                etat[k], fin[k] = 1, sortie[i]
                break
    return etat, fin


def compte(entree: np.ndarray, sortie: np.ndarray, rr: np.ndarray, risque_pct: float, de_ns: int, a_ns: int) -> dict:
    """Compte FTMO 100 000 $ : risque fixe en % du capital de départ par trade ; gains réalisés à la sortie (la perte
    latente d'un trade ouvert n'est pas comptée : 1R au plus par trade, stop + glissement)."""
    o = np.argsort(sortie, kind="stable")
    e, s, g = entree[o], sortie[o], rr[o] * risque_pct
    eq = np.cumsum(g)
    pic = np.maximum.accumulate(np.r_[0.0, eq])[1:]
    mois = (a_ns - de_ns) / MOIS_NS
    jour = (s - HEURE_NS) // JOUR_NS                       # jour de Prague ~ serveur - 1 h
    departs = np.arange(de_ns, a_ns, 7 * JOUR_NS, dtype=np.int64)
    et, fn = challenges(e, s, g, jour, departs, 5.0, 10.0, 10.0)
    term = et != 0
    # positions ouvertes en même temps (au plus)
    ev = np.r_[np.c_[entree, np.ones(len(entree))], np.c_[sortie, -np.ones(len(sortie))]]
    ev = ev[np.lexsort((ev[:, 1], ev[:, 0]))]
    simult = int(np.cumsum(ev[:, 1]).max()) if len(ev) else 0
    return {"gain_mois_pct": float(eq[-1] / mois) if len(eq) else 0.0, "gain_total_pct": float(eq[-1]) if len(eq) else 0.0,
            "baisse_max_pct": float((pic - eq).max()) if len(eq) else 0.0, "departs": int(len(departs)),
            "termines": int(term.sum()), "reussis": int((et == 1).sum()), "morts": int((et == -1).sum()),
            "jours_median_termine": float(np.median((fn[term] - departs[term]) / JOUR_NS)) if term.any() else None,
            "positions_simultanees_max": simult}


def compte_contre_jumeaux(z: dict, risque_pct: float, periode: str, tirages: int = TIRAGES, graine: int = 20261018) -> dict:
    de_ns, a_ns = _periode_ns(periode)
    if len(z["dec_ns"]):
        de_ns = max(de_ns, int(z["dec_ns"].min()) - int(z["dec_ns"].min()) % JOUR_NS)   # depuis le 1er signal
    ok = z["exe"] & (z["code"] != JT.FIN)
    reel = compte(z["ne_ns"][ok], z["ns_ns"][ok], z["r"][ok], risque_pct, de_ns, a_ns)
    rng = np.random.default_rng(graine)
    okj = z["exe_j"] & (z["code_j"] != JT.FIN)
    gains, reus, morts = [], [], []
    for _ in range(tirages):
        pile = rng.random(len(ok)) < 0.5
        m_r, m_j = ok & pile, okj & ~pile
        e = np.r_[z["ne_ns"][m_r], z["ne_j_ns"][m_j]]
        s = np.r_[z["ns_ns"][m_r], z["ns_j_ns"][m_j]]
        r = np.r_[z["r"][m_r], z["r_j"][m_j]]
        c = compte(e, s, r, risque_pct, de_ns, a_ns)
        gains.append(c["gain_mois_pct"])
        reus.append(c["reussis"])
        morts.append(c["morts"])
    gains = np.asarray(gains)
    return {"reel": reel, "jumeaux_gain_mois_moyen": float(gains.mean()), "jumeaux_gain_mois_sd": float(gains.std()),
            "jumeaux_au_moins_aussi_bien_pct": float((gains >= reel["gain_mois_pct"]).mean() * 100),
            "jumeaux_reussis_moyen": float(np.mean(reus)), "jumeaux_morts_moyen": float(np.mean(morts))}


# ---------------------------------------------------------------------------------------------- étapes
def etape_selection(dire=print) -> dict:
    med = medianes_placements("selection", dire)
    (SORTIE / "medianes_2020_2023.json").write_text(json.dumps(med, ensure_ascii=False, indent=1), encoding="utf-8")
    tout = VARIANTES + TEMOINS
    trades = calculer(tout, "selection", med, dire)
    res = {"medianes": med, "variantes": {}}
    for v in tout:
        res["variantes"][vid(v)] = mesurer_variante(trades[vid(v)], "selection", v[2])
    elig = [(res["variantes"][vid(v)]["variante"].get("force", -np.inf), vid(v)) for v in VARIANTES
            if res["variantes"][vid(v)]["variante"].get("n_exe", 0) >= MIN_TRADES]
    elig = [(f if np.isfinite(f) else -np.inf, k) for f, k in elig]
    res["retenue"] = max(elig)[1]
    res["date"] = datetime.now().isoformat(timespec="seconds")
    (SORTIE / "selection.json").write_text(json.dumps(res, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
    dire(f"variante retenue sur 2020-2023 : {res['retenue']}")
    return res


def etape_controle(dire=print) -> dict:
    sel = json.loads((SORTIE / "selection.json").read_text(encoding="utf-8"))
    if (SORTIE / "controle.json").exists():
        raise SystemExit("le contrôle a déjà été fait (une seule fois)")
    k = sel["retenue"]
    d, pl, o = k.split("-")
    v = (d, pl, int(o[:-1]))
    temoin = ("T", pl, int(o[:-1]))
    trades = calculer([v, temoin], "controle", sel["medianes"], dire)
    res = {"retenue": k, "variante": mesurer_variante(trades[k], "controle", v[2]),
           "temoin": mesurer_variante(trades[vid(temoin)], "controle", v[2]), "comptes": {}, "comptes_selection": {}}
    sel_tr = lire_trades("selection", k)
    for rk in (0.25, 0.5):
        res["comptes"][str(rk)] = compte_contre_jumeaux(trades[k], rk, "controle")
        res["comptes_selection"][str(rk)] = compte_contre_jumeaux(sel_tr, rk, "selection")
    res["date"] = datetime.now().isoformat(timespec="seconds")
    (SORTIE / "controle.json").write_text(json.dumps(res, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
    return res


def verdict(sel: dict, ctl: dict) -> str:
    k = sel["retenue"]
    r23 = sel["variantes"][k]["variante"].get("r", np.nan)
    b = ctl["variante"]["variante"]
    r24, f24 = b.get("r", np.nan), b.get("force", np.nan)
    if r24 > 0 and f24 >= SEUIL and r23 > 0:
        return "PROUVÉ"
    if r24 > 0 and r23 > 0 and f24 > 2:
        return "PROMETTEUR (non prouvé)"
    if r24 > 0 and r23 > 0:
        return "positif mais trop faible (non)"
    return "non"


# ---------------------------------------------------------------------------------------------- rapport
def _f(x, n=3, signe=True):
    if x is None or (isinstance(x, float) and not np.isfinite(x)):
        return "—"
    return f"{x:+.{n}f}" if signe else f"{x:.{n}f}"


ENTETE = ("| variante | signaux / trades exécutés (ordres limites remplis) | trades / mois | achats | objectif atteint (seuil) | "
          "stop / temps | R moyen ± incertitude (force) | médiane | jumeau : R moyen ; avance (force) | sans la structure : "
          "R moyen ; avance (force) |\n|---|---|---|---|---|---|---|---|---|---|")


def ligne_variante(k: str, m: dict) -> str:
    b = m["variante"]
    if b.get("n_exe", 0) == 0:
        return f"| {k} | {b.get('n_signaux', 0)} / 0 | — | — | — | — | — | — | — | — |"
    aj, as_ = m["avance_jumeau"], m["avance_sans_structure"]
    lim = f" ({m['limites_remplies_pct']:.0f} %)" if m.get("limites_remplies_pct") is not None else ""
    return (f"| {k} | {b['n_signaux']} / {b['n_exe']}{lim} | {b['trades_mois']:.1f} | {b['achats_pct']:.0f} % | "
            f"{b['objectif_pct']:.1f} % ({b['seuil_pct']:.1f} %) | {b['stop_pct']:.0f} % / {b['temps_pct']:.0f} % | "
            f"{_f(b['r'])} ± {_f(b['inc'], 3, False)} ({_f(b['force'], 1)}) | {_f(b['mediane'])} | "
            f"{_f(m['jumeau_r'])} ; {_f(aj['avance'])} ({_f(aj['force'], 1)}) | "
            f"{_f(m['sans_structure'].get('r'))} ; {_f(as_['avance'])} ({_f(as_['force'], 1)}) |")


def lignes_compte(c: dict) -> list[str]:
    L = ["| risque / trade | gain / mois | baisse max | challenges : réussis / morts (terminés / départs) | jours médians "
         "| positions en même temps (max) | 200 jumeaux : gain / mois | jumeaux au moins aussi bons | jumeaux : réussis / morts |",
         "|---|---|---|---|---|---|---|---|---|"]
    for rk, x in c.items():
        r = x["reel"]
        L.append(f"| {rk} % | {r['gain_mois_pct']:+.2f} % | {r['baisse_max_pct']:.1f} % | {r['reussis']} / {r['morts']} "
                 f"({r['termines']} / {r['departs']}) | {_f(r['jours_median_termine'], 0, False)} | "
                 f"{r['positions_simultanees_max']} | {x['jumeaux_gain_mois_moyen']:+.2f} % ± {x['jumeaux_gain_mois_sd']:.2f} | "
                 f"{x['jumeaux_au_moins_aussi_bien_pct']:.0f} % | {x['jumeaux_reussis_moyen']:.1f} / {x['jumeaux_morts_moyen']:.1f} |")
    return L


def ecrire_rapport(conclusion: str = ""):
    sel = json.loads((SORTIE / "selection.json").read_text(encoding="utf-8")) if (SORTIE / "selection.json").exists() else None
    ctl = json.loads((SORTIE / "controle.json").read_text(encoding="utf-8")) if (SORTIE / "controle.json").exists() else None
    L = [f"# HYPERNOVA — LA LOGIQUE INVERSÉE : la source choisit le moment, la structure place le stop "
         f"(rapport du {datetime.now():%d/%m/%Y %H:%M})", ""]
    L.append("Mesure SANS IA. Chaque trade est joué sur le vrai chemin du prix par le moteur de l'arbre (frais FTMO du "
             "16/10 dont la commission crypto, glissement du stop, nuits, bougie d'exécution jugée au pire). R = résultat "
             "en multiples du risque, frais compris. « Seuil » = % de trades à l'objectif qu'il faut pour ne pas perdre "
             "(mesuré). Force = R moyen / incertitude (grappes = semaines, tous marchés ensemble). Jumeau = mêmes trades, "
             "sens à pile ou face. « Sans la structure » = même moment, même sens, même sortie, stop à distance fixe "
             "(médiane de la variante, en agitations).")
    L.append(f"N total = {N_TOTAL} cases (dont {N_DEJA} déjà jugées) -> seuil de preuve = {SEUIL:.2f}.\n")
    if conclusion:
        L.append(conclusion.strip() + "\n")
    if ctl and sel:
        k = ctl["retenue"]
        L.append(f"## Jugement 01/2024 -> 09/2025 (une seule fois) : {k} — verdict : **{verdict(sel, ctl)}**\n")
        L.append(ENTETE)
        L.append(ligne_variante(f"{k} (2020-2023)", sel["variantes"][k]))
        L.append(ligne_variante(f"{k} (2024-2025)", ctl["variante"]))
        tk = "T-" + "-".join(k.split("-")[1:])
        L.append(ligne_variante(f"{tk} témoin (2020-2023)", sel["variantes"][tk]))
        L.append(ligne_variante(f"{tk} témoin (2024-2025)", ctl["temoin"]))
        L.append("")
        L.append("### Compte FTMO 100 000 $ — 2024-2025 (un départ de challenge tous les 7 jours, +10 % / -5 % par jour / "
                 "-10 % au total)\n")
        L += lignes_compte(ctl["comptes"])
        L.append("\n### Même compte sur 2020-2023 (période de choix)\n")
        L += lignes_compte(ctl["comptes_selection"])
        L.append("")
    if sel:
        L.append(f"## Choix sur 2020-2023 : retenue **{sel['retenue']}** (plus grande force parmi les éligibles avec au "
                 f"moins {MIN_TRADES} trades)\n")
        L.append(ENTETE)
        for v in VARIANTES + TEMOINS:
            L.append(ligne_variante(vid(v) + (" (témoin)" if v[0] == "T" else ""), sel["variantes"][vid(v)]))
        L.append("")
        L.append("Distances du témoin « sans la structure » (médianes 2020-2023, en agitations) : "
                 + " ; ".join(f"{k} risque {v['risque_A']:.2f}" + (f", entrée {v['entree_A']:.2f}" if k.endswith("LZ") else "")
                              for k, v in sel["medianes"].items()) + "\n")
    f_plan = SORTIE / "plan_fige.md"
    if f_plan.exists():
        L.append(f_plan.read_text(encoding="utf-8").replace("# LOGIQUE", "## LOGIQUE").replace("\n## ", "\n### "))
    (SORTIE / "rapport.md").write_text("\n".join(L), encoding="utf-8")


def dire_(t):
    print(f"[{datetime.now():%d/%m %H:%M:%S}] {t}", flush=True)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("quoi", choices=["plan", "selection", "controle", "rapport"])
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
    if a.quoi == "selection":
        etape_selection(dire_)
    if a.quoi == "controle":
        etape_controle(dire_)
    f_c = SORTIE / "conclusion.md"
    ecrire_rapport(f_c.read_text(encoding="utf-8") if f_c.exists() else "")
    dire_("rapport écrit : " + str(SORTIE / "rapport.md"))


if __name__ == "__main__":
    main()
