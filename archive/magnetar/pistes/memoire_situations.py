"""LA MÉMOIRE DES SITUATIONS (18/10/2026, chef de projet, inspirée de la mouche : « reconnaître une situation et se
souvenir de ce qui a suivi »), mesurée sur l'OR AVANT de la donner à MAGNETAR. Mesure SANS IA, liste FIGÉE
(vie/memoire/plan_fige.md écrit et daté AVANT toute mesure).

1. LES SOUVENIRS : chaque clôture d'heure de l'or (bougies de 15 min, 2004 -> 09/2025), résumée par un petit vecteur de
   ce que voit un trader (position par rapport à ses zones D1 / H4 / H1, tendance 1 / 5 / 20 / 60 j, tendance de
   structure D1 / H4, agitation, compression, peur sur l'or GVZ publiée à J+1, heure, mouvement des 1 h et 4 h), et CE
   QUI A SUIVI (plus grande avance à la hausse et à la baisse sur 24 h et 72 h en agitations, gros mouvement = au moins
   3 agitations sur 72 h, son sens = le premier côté atteint, mouvement net).
2. RÈGLE ANTI-TRICHE (la même partout, à la mesure comme plus tard à l'entraînement) : à l'instant t, la mémoire ne
   contient QUE les moments dont la suite de 72 h était entièrement connue au moins 5 jours AVANT t
   (fin d'horizon + 5 j <= t). Jamais le moment présent ni ses voisins. Test piège : la version qui triche (toute la
   mémoire, futur compris, sauf le moment lui-même) doit être énormément meilleure.
3. LA MESURE : k plus proches souvenirs (k = 20 / 50 / 200), probabilité d'un gros mouvement et sens majoritaire des gros
   mouvements passés, contre le taux de base, des souvenirs tirés au hasard (même nombre) et la tendance 60 j seule ;
   puis trading quand la mémoire est confiante (entrée au marché, stop derrière la structure, stop suiveur 1 h, sans
   plafond, frais FTMO) contre le jumeau.
Périodes : échauffement (mémoire seulement) < 2008 ; choix 2008-2021 ; vérification 2022-2023 ; contrôle UNE fois
01/2024 -> 09/2025. Rien après 09/2025.

Depuis Test_IA : venv_gpu\\Scripts\\python.exe -u -m collapsar.regarder.pistes.memoire_situations plan|calcul|choix|verification|controle|rapport
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

from collapsar.donnees.marches import RACINE

SORTIE = RACINE / "collapsar" / "vie" / "memoire"
MARCHE = "XAUUSD"
QUINZE_NS = 15 * 60 * 10 ** 9
HEURE_NS = 3600 * 10 ** 9
JOUR_NS = 86400 * 10 ** 9
SEMAINE_NS = 7 * JOUR_NS
MOIS_NS = 30.4375 * JOUR_NS

# ============================================================================================== LISTE FIGÉE
PERIODES = {"choix": ("2008-01-01", "2022-01-01"), "verification": ("2022-01-01", "2024-01-01"),
            "controle": ("2024-01-01", "2025-10-01")}
NOM_P = {"choix": "2008-2021 (choix)", "verification": "2022-2023 (vérification)",
         "controle": "01/2024 -> 09/2025 (contrôle, une seule fois)"}
DEBUT_QUESTIONS = "2008-01-01"     # avant : échauffement (souvenirs seulement), sert aussi à la mise à l'échelle
H24, H72 = 96, 288                 # horizons en bougies de 15 min (24 h et 72 h de cotation)
GROS_A = 3.0                       # gros mouvement = au moins 3 agitations sur 72 h
MARGE_NS = 5 * JOUR_NS             # marge de la barrière anti-triche
KS = (20, 50, 200)
KMAX = max(KS)
MEMOIRE_MIN = 2000                 # une question n'est posée que si la mémoire contient au moins 2000 souvenirs
ALERTE = 2.0                       # « alerte » : probabilité de la mémoire >= 2 x le taux de base
MIN_GROS = 5                       # trading : au moins 5 gros mouvements parmi les voisins
PART_SENS = 2.0 / 3.0              # trading : au moins 2/3 de ces gros mouvements du même sens
UNITES_ZONES = ("D1", "H4", "H1")
TENDANCES_J = (1, 5, 20, 60)
I_T60 = 6 + 3                      # colonne de la tendance 60 j dans le vecteur
NOMS_V = ([f"zone {u} {c}" for u in UNITES_ZONES for c in ("demande", "offre")]
          + [f"tendance {h} j" for h in TENDANCES_J]
          + ["structure D1", "structure H4", "agitation / prix", "compression", "peur or GVZ (1 an)",
             "peur or GVZ (60 j)", "heure (sin)", "heure (cos)", "mouvement 1 h", "mouvement 4 h"])
NV = len(NOMS_V)
LOG20 = math.log1p(20.0)
# --- trading
MARGE_A = 0.1
RISQUE_MIN_A, RISQUE_MAX_A = 0.2, 3.0
HORIZON_TRADE = 2880               # 30 jours au plus
RISQUE_COMPTE = 0.5
# --- nombre de cases et seuil
N_DEJA = 1257
N_I = 4 * len(KS)                  # alerte contre base, contre hasard, contre tendance 60 j ; gain de précision (Brier)
N_II = 3 * len(KS)                 # sens contre 50 %, contre hasard, contre tendance 60 j
N_III = 2 * len(KS) + 1            # R moyen, avance sur le jumeau ; compte FTMO
N_TOTAL = N_DEJA + N_I + N_II + N_III
SEUIL = max(3.0, math.sqrt(2 * math.log(N_TOTAL)))


def plan_texte() -> str:
    L = [f"# LA MÉMOIRE DES SITUATIONS (or) — plan FIGÉ avant toute mesure ({datetime.now():%d/%m/%Y %H:%M})", "",
         "Mesure SANS IA sur l'or (XAUUSD, bougies de 15 min 2004 -> 09/2025, yeux de l'école de la précision "
         "`ecole/precision/structure.py`). Heure du serveur. A = agitation (moyenne plus haut - plus bas des 14 derniers "
         "jours terminés). Rien après 09/2025.", "",
         "## 1. Les souvenirs", "",
         "- Un moment = chaque clôture d'heure (bougie de 15 min qui finit à l'heure pile), A connue.",
         "- Son vecteur (" + str(NV) + " nombres, tout connu à la clôture, sans futur) : " + " ; ".join(NOMS_V) + ".",
         "  Zones : distance du prix au bord proche de la zone de demande vivante la plus proche (dessous) et de la zone "
         "d'offre (dessus), en A, transformée log(1 + d) (dans la zone ou au-delà : d négatif borné à -2 ; aucune zone : "
         "log 21). Tendances : (prix - clôture d'il y a h jours) / (A x racine(h)), bornée +-6. Structure : (signe des 2 "
         "derniers sommets + signe des 2 derniers creux) / 2. Agitation : log(A / prix). Compression : log(agitation 3 j "
         "/ agitation 14 j). GVZ : écart du niveau (log) à la moyenne de l'année et des 60 dernières valeurs, en écarts, "
         "valeur du jour J utilisée à J+1 08h00 (donnees/monde.py) ; absente (avant 2010) = 0. Heure : sinus / cosinus. "
         "Mouvement : (prix - prix 1 h / 4 h avant) / A.",
         f"- Mise à l'échelle : chaque nombre divisé par son écart-type sur l'échauffement (moments avant "
         f"{DEBUT_QUESTIONS}), sauf GVZ, sinus et cosinus (déjà à l'échelle) ; distance = distance euclidienne simple.",
         f"- Ce qui a suivi : plus grande avance à la hausse (plus haut - prix) / A et à la baisse (prix - plus bas) / A sur "
         f"{H24} et {H72} bougies de 15 min (24 h et 72 h de cotation) ; mouvement net (clôture - prix) / A ; GROS "
         f"MOUVEMENT = au moins {GROS_A:g} A d'un côté sur 72 h ; son SENS = le côté atteint le premier (les deux dans la "
         "même bougie : sens inconnu).", "",
         "## 2. Règle anti-triche (la même partout)", "",
         f"- Un souvenir n'entre dans la mémoire qu'à l'instant (clôture de la dernière bougie de ses 72 h) + "
         f"{MARGE_NS // JOUR_NS} jours. Le moment présent et ses voisins (8 jours) n'y sont donc jamais.",
         f"- Une question n'est posée qu'avec au moins {MEMOIRE_MIN} souvenirs, à partir de {DEBUT_QUESTIONS}.",
         "- Test « sans futur » : vecteurs calculés sur des données coupées à t = calcul complet ; prévisions inchangées si "
         "on remplace la suite des souvenirs pas encore permis par n'importe quoi.",
         "- TEST PIÈGE : la même mesure avec une mémoire qui triche (tous les moments, futur compris, sauf le moment "
         "lui-même), sur un moment sur 4 de la période de choix : elle doit être énormément meilleure.", "",
         "## 3. La mesure", "",
         f"- Pour chaque moment : les k plus proches souvenirs (k = {' / '.join(map(str, KS))}) ; probabilité d'un gros "
         "mouvement = part des voisins qui en ont eu un ; sens = majorité des sens de leurs gros mouvements.",
         "- Repères : TAUX DE BASE (part des gros mouvements dans toute la mémoire permise à cet instant), SOUVENIRS AU "
         "HASARD (k souvenirs tirés au hasard dans la mémoire permise), TENDANCE 60 J SEULE (k plus proches voisins sur "
         "la seule tendance 60 j pour la probabilité ; signe de la tendance 60 j pour le sens).",
         f"- (i) gros mouvements : ALERTE = probabilité >= {ALERTE:g} x le taux de base ; taux réel des gros mouvements "
         "pendant les alertes contre le taux de base (écart en points, force) ; contre les alertes des souvenirs au hasard "
         "et de la tendance 60 j seule (même règle) ; gain de précision (Brier : (y - base)² - (y - mémoire)², tous les "
         "moments). Descriptif : aire sous la courbe (chance qu'un moment à gros mouvement ait une probabilité plus haute "
         "qu'un autre).",
         "- (ii) sens : sur les moments qui ont VRAIMENT eu un gros mouvement de sens connu et où la mémoire donne un "
         "sens : part de sens justes contre 50 %, contre les souvenirs au hasard (même moments, apparié) et contre le "
         "signe de la tendance 60 j (apparié).",
         f"- (iii) trading : signal si alerte ET au moins {MIN_GROS} gros mouvements parmi les voisins ET au moins "
         f"{PART_SENS:.0%} du même sens ; entrée au marché à l'ouverture suivante dans ce sens ; stop derrière le dernier "
         f"creux (achat) / sommet (vente) confirmé H1 + {MARGE_A:g} A, sinon H4, risque entre {RISQUE_MIN_A:g} et "
         f"{RISQUE_MAX_A:g} A et plus qu'un aller-retour de frais, sinon pas de trade ; stop suiveur H1 (nouveaux "
         "creux / sommets, regarder/pistes/mouvements.trade_suiveur = moteur de l'arbre), AUCUN objectif, 30 jours au "
         "plus, frais FTMO du 16/10, nuits, glissement du stop ; un trade à la fois. Contre le JUMEAU (sens retourné, "
         "même stop de l'autre côté) : avance = (R - R retourné) / 2. Mesures : trades / mois, gagnants, R moyen "
         f"(force), part >= 5R / >= 10R. Compte FTMO 100 000 $ à {RISQUE_COMPTE:g} % par trade contre 200 jumeaux.",
         "- Incertitudes : grappes = semaines (moments et trades d'une même semaine ensemble).", "",
         "## Choix, jugement", "",
         "- Choix sur 2008-2021 SEULEMENT : pour (i) le k de plus grande force de l'alerte contre la base ; pour (ii) le k "
         "de plus grande force contre les souvenirs au hasard ; pour (iii) le k de plus grande force du R moyen (au moins "
         "100 trades). Vérification 2022-2023 (tous les k). Contrôle UNE fois 2024-2025 : les k retenus seulement.",
         f"- N = {N_DEJA} cases déjà jugées + {N_I} (i) + {N_II} (ii) + {N_III} (iii) = {N_TOTAL} -> seuil de preuve "
         f"max(3, racine(2 ln N)) = {SEUIL:.2f}.",
         "- (i) RÉELLE si l'écart alerte - base est > 0 sur les 3 périodes et sa force >= seuil au contrôle ; « au-delà de "
         "la tendance » si en plus elle bat la tendance 60 j seule au contrôle. (ii) RÉEL si le sens bat les souvenirs au "
         "hasard sur les 3 périodes avec force >= seuil au contrôle (même chose contre la tendance 60 j). (iii) PROUVÉ si "
         "R moyen > 0 sur les 3 périodes et force >= seuil au contrôle ; PROMETTEUR si > 0 sur les 3 avec force > 2 au "
         "contrôle ; sinon non.",
         "- Si (i) ou (ii) est réel au contrôle : décrire (sans l'appliquer) le nouveau sens de MAGNETAR."]
    return "\n".join(L) + "\n"


# ============================================================================================== 1. les souvenirs
def _a(x, k):
    return np.asarray(x[k])


def moments(x: dict) -> np.ndarray:
    """Lignes de 15 min qui finissent à l'heure pile, agitation connue."""
    t15 = np.asarray(x["t15"], np.int64)
    A = np.asarray(x["A"], np.float64)
    fin = t15 + QUINZE_NS
    return np.flatnonzero((fin % HEURE_NS == 0) & np.isfinite(A) & (A > 0))


def _g(d: np.ndarray) -> np.ndarray:
    return np.where(np.isnan(d), LOG20, np.where(d >= 0, np.log1p(np.clip(d, 0, 20)), np.clip(d, -2, 0)))


def peur_or(dec: np.ndarray, coupe_ns: int | None = None) -> np.ndarray:
    """[n, 2] : GVZ (écart à l'année, écart aux 60 dernières valeurs) CONNU à chaque instant (J+1 08h00) ; 0 sinon."""
    from collapsar.donnees import monde as M
    tb = M.tableau("gvz", coupe_ns)
    c = tb["connu"].to_numpy(np.int64)
    out = np.zeros((len(dec), 2))
    if not len(c):
        return out
    i = np.searchsorted(c, dec, side="right") - 1
    ok = (i >= 0) & ((dec - c[np.clip(i, 0, None)]) <= 10 * JOUR_NS)
    ii = np.clip(i, 0, None)
    for q, col in enumerate(("z250", "z60")):
        v = tb[col].to_numpy(np.float64)[ii]
        out[:, q] = np.where(ok & np.isfinite(v), np.clip(v, -5, 5), 0.0)
    return out


def vecteurs(x: dict, rows: np.ndarray, coupe_ns: int | None = None) -> np.ndarray:
    """[n, NV] : ce que voit un trader à la clôture des lignes `rows` (sans futur ; `coupe_ns` : GVZ publié avant)."""
    from collapsar.regarder.pistes import mouvements as MV
    rows = np.asarray(rows, np.int64)
    t15 = np.asarray(x["t15"], np.int64)
    c, A = np.asarray(x["c"], np.float64), np.asarray(x["A"], np.float64)
    dec = t15[rows] + QUINZE_NS
    p, Ar = c[rows], A[rows]
    cols = []
    for u in UNITES_ZONES:
        y = x[u]
        lg = np.asarray(y["ligne"]).astype(np.int64)[rows]
        knn = np.asarray(y["knn"])
        top, bot = np.asarray(y["top"], np.float64), np.asarray(y["bot"], np.float64)
        ok = lg >= 0
        kk = knn[np.clip(lg, 0, None)]
        zd, zo = kk[:, 0, 0].astype(np.int64), kk[:, 1, 0].astype(np.int64)
        dd = np.where(ok & (zd >= 0), (p - top[np.clip(zd, 0, None)]) / Ar, np.nan)
        do = np.where(ok & (zo >= 0), (bot[np.clip(zo, 0, None)] - p) / Ar, np.nan)
        cols += [_g(dd), _g(do)]
    fins = t15 + QUINZE_NS
    for h in TENDANCES_J:
        j = np.searchsorted(fins, dec - h * JOUR_NS, side="right") - 1
        cp = np.where(j >= 0, c[np.clip(j, 0, None)], np.nan)
        cols.append(np.nan_to_num(np.clip((p - cp) / (Ar * math.sqrt(h)), -6, 6)))
    for u in ("D1", "H4"):
        lg = np.asarray(x[u]["ligne"]).astype(np.int64)[rows]
        sw = np.asarray(x[u]["sw"], np.float64)[np.clip(lg, 0, None)]
        td = (np.nan_to_num(np.sign(sw[:, 0] - sw[:, 1])) + np.nan_to_num(np.sign(sw[:, 2] - sw[:, 3]))) / 2
        cols.append(np.where(lg >= 0, td, 0.0))
    cols.append(np.log(Ar / p))
    cp = MV.compression(x, rows)
    cols.append(np.where(np.isfinite(cp) & (cp > 0), np.log(np.clip(cp, 1e-3, None)), 0.0))
    g = peur_or(dec, coupe_ns)
    cols += [g[:, 0], g[:, 1]]
    hh = (dec % JOUR_NS) / HEURE_NS
    cols += [np.sin(2 * np.pi * hh / 24), np.cos(2 * np.pi * hh / 24)]
    for b in (4, 16):
        j = rows - b
        cols.append(np.where(j >= 0, np.clip((p - c[np.clip(j, 0, None)]) / Ar, -6, 6), 0.0))
    return np.stack(cols, 1)


@njit(cache=True)
def _suites(h, l, c, rows, p, A, h1, h2, g):
    n = len(rows)
    T = len(h)
    out = np.full((n, 6), np.nan)
    sens = np.zeros(n, np.int64)
    ok = np.zeros(n, np.bool_)
    for e in range(n):
        i = rows[e]
        if i + h2 >= T:
            continue
        ok[e] = True
        hi, lo = -np.inf, np.inf
        up, dn = p[e] + g * A[e], p[e] - g * A[e]
        s = 0
        for m in range(i + 1, i + h2 + 1):
            if h[m] > hi:
                hi = h[m]
            if l[m] < lo:
                lo = l[m]
            if s == 0:
                hu, ld = h[m] >= up, l[m] <= dn
                if hu and ld:
                    s = 2
                elif hu:
                    s = 1
                elif ld:
                    s = -1
            if m == i + h1:
                out[e, 0], out[e, 1], out[e, 4] = (hi - p[e]) / A[e], (p[e] - lo) / A[e], (c[m] - p[e]) / A[e]
        out[e, 2], out[e, 3], out[e, 5] = (hi - p[e]) / A[e], (p[e] - lo) / A[e], (c[i + h2] - p[e]) / A[e]
        sens[e] = s
    return out, sens, ok


def suites(x: dict, rows: np.ndarray) -> dict:
    """Ce qui a suivi chaque moment (sur le vrai chemin du prix) et l'instant où cette suite est entièrement connue."""
    rows = np.asarray(rows, np.int64)
    t15 = np.asarray(x["t15"], np.int64)
    h, l, c = (np.asarray(x[k], np.float64) for k in ("h", "l", "c"))
    A = np.asarray(x["A"], np.float64)
    out, s, ok = _suites(h, l, c, rows, c[rows], A[rows], H24, H72, GROS_A)
    gros = ok & (np.maximum(out[:, 2], out[:, 3]) >= GROS_A)
    fin = np.where(ok, t15[np.clip(rows + H72, 0, len(t15) - 1)] + QUINZE_NS, np.iinfo(np.int64).max // 2)
    return {"haut24": out[:, 0], "bas24": out[:, 1], "haut72": out[:, 2], "bas72": out[:, 3], "net24": out[:, 4],
            "net72": out[:, 5], "gros": gros, "sens": np.where(gros & (np.abs(s) == 1), s, 0).astype(np.int8),
            "gros24": ok & (np.maximum(out[:, 0], out[:, 1]) >= GROS_A), "ok": ok, "fin_ns": fin}


def echelle(V: np.ndarray, dec: np.ndarray) -> np.ndarray:
    """Écart-type de chaque nombre sur l'échauffement (avant DEBUT_QUESTIONS) ; 1 pour GVZ, sinus, cosinus."""
    e = V[dec < pd.Timestamp(DEBUT_QUESTIONS).value]
    s = e.std(0)
    s = np.where(s > 1e-9, s, 1.0)
    for k in ("peur or GVZ (1 an)", "peur or GVZ (60 j)", "heure (sin)", "heure (cos)"):
        s[NOMS_V.index(k)] = 1.0
    return s


# ============================================================================================== 2. la barrière
def limite_memoire(fin_ns: np.ndarray, dec_q: np.ndarray) -> np.ndarray:
    """Nombre de souvenirs permis à chaque question : ceux dont fin + marge <= instant de la question (les souvenirs
    sont rangés dans l'ordre du temps, leur fin est croissante : la mémoire permise est un début de liste)."""
    f = np.asarray(fin_ns, np.int64) + MARGE_NS
    assert (np.diff(f) >= 0).all()
    return np.searchsorted(f, np.asarray(dec_q, np.int64), side="right").astype(np.int64)


def voisins(Xq: np.ndarray, lim: np.ndarray, Xm: np.ndarray, K: int, soi: np.ndarray | None = None,
            bloc: int = 256) -> np.ndarray:
    """[nq, K] : indices des K plus proches souvenirs PERMIS (indice < lim de la question), du plus proche au plus loin ;
    -1 s'il y en a moins. `soi` (version qui triche) : indice du moment lui-même dans la mémoire, exclu."""
    Xq = np.ascontiguousarray(Xq, np.float32)
    Xm = np.ascontiguousarray(Xm, np.float32)
    lim = np.asarray(lim, np.int64)
    nq = len(Xq)
    out = np.full((nq, K), -1, np.int32)
    m2 = (Xm * Xm).sum(1)
    for a in range(0, nq, bloc):
        b = min(nq, a + bloc)
        L = int(lim[a:b].max())
        if L <= 0:
            continue
        D = m2[None, :L] - 2.0 * (Xq[a:b] @ Xm[:L].T)
        D[np.arange(L)[None, :] >= lim[a:b, None]] = np.inf
        if soi is not None:
            s = np.asarray(soi[a:b], np.int64)
            okk = (s >= 0) & (s < L)
            D[np.flatnonzero(okk), s[okk]] = np.inf
        kk = min(K, L)
        part = np.argpartition(D, kk - 1, axis=1)[:, :kk] if kk < L else np.tile(np.arange(L), (b - a, 1))
        dd = np.take_along_axis(D, part, 1)
        o = np.argsort(dd, 1, kind="stable")
        idx = np.take_along_axis(part, o, 1)
        ok = np.isfinite(np.take_along_axis(dd, o, 1))
        out[a:b, :kk] = np.where(ok, idx, -1)
    return out


def predire(idx: np.ndarray, k: int, gros: np.ndarray, sens: np.ndarray) -> dict:
    """Ce que disent les k premiers voisins : probabilité d'un gros mouvement, gros mouvements à la hausse / baisse."""
    sub = idx[:, :k]
    v = sub >= 0
    s = np.clip(sub, 0, None)
    g = gros[s] & v
    nv = v.sum(1)
    up = (g & (sens[s] > 0)).sum(1)
    dn = (g & (sens[s] < 0)).sum(1)
    return {"p": np.where(nv > 0, g.sum(1) / np.maximum(nv, 1), np.nan), "n_gros": g.sum(1), "up": up, "dn": dn,
            "n": nv}


def taux_base(lim: np.ndarray, gros: np.ndarray) -> np.ndarray:
    cg = np.r_[0, np.cumsum(gros.astype(np.int64))]
    lim = np.asarray(lim, np.int64)
    return np.where(lim > 0, cg[lim] / np.maximum(lim, 1), np.nan)


def au_hasard(lim: np.ndarray, K: int, graine: int = 20261018) -> np.ndarray:
    rng = np.random.default_rng(graine)
    lim = np.asarray(lim, np.int64)
    return np.where(lim[:, None] > 0, np.floor(rng.random((len(lim), K)) * lim[:, None]), -1).astype(np.int32)


# ============================================================================================== mesures
def incertitude(x: np.ndarray, grappes: np.ndarray) -> float:
    from collapsar.regarder.pistes.logique_inversee import incertitude as inc
    return inc(np.asarray(x, np.float64), np.asarray(grappes))


def moyenne(d: np.ndarray, sem: np.ndarray) -> dict:
    d = np.asarray(d, np.float64)
    if len(d) < 2:
        return {"n": int(len(d)), "m": float("nan"), "inc": float("nan"), "force": float("nan")}
    inc = incertitude(d, sem)
    return {"n": int(len(d)), "m": float(d.mean()), "inc": inc, "force": float(d.mean() / inc) if inc > 0 else float("nan")}


def ecart_deux(a: np.ndarray, sa: np.ndarray, b: np.ndarray, sb: np.ndarray) -> dict:
    """Écart de deux taux sur des moments différents (incertitudes ajoutées)."""
    A_, B_ = moyenne(a, sa), moyenne(b, sb)
    ii = math.sqrt(A_["inc"] ** 2 + B_["inc"] ** 2) if np.isfinite(A_["inc"]) and np.isfinite(B_["inc"]) else float("nan")
    e = A_["m"] - B_["m"]
    return {"m": e, "inc": ii, "force": e / ii if ii and ii > 0 else float("nan"), "n_a": A_["n"], "n_b": B_["n"],
            "taux_a": A_["m"], "taux_b": B_["m"]}


def aire(score: np.ndarray, y: np.ndarray) -> float:
    from scipy.stats import rankdata
    ok = np.isfinite(score)
    s, y = score[ok], y[ok].astype(bool)
    n1, n0 = y.sum(), (~y).sum()
    if n1 == 0 or n0 == 0:
        return float("nan")
    r = rankdata(s)
    return float((r[y].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))


def mesure_gros(pm: np.ndarray, pr: np.ndarray, pt: np.ndarray, pb: np.ndarray, y: np.ndarray, sem: np.ndarray) -> dict:
    y = y.astype(np.float64)
    al = np.isfinite(pm) & (pm >= ALERTE * pb)
    ar = np.isfinite(pr) & (pr >= ALERTE * pb)
    at = np.isfinite(pt) & (pt >= ALERTE * pb)
    return {"base_taux": float(np.nanmean(pb)), "reel_taux": float(y.mean()), "n": int(len(y)),
            "alertes_pct": float(al.mean() * 100),
            "alerte_contre_base": moyenne((y - pb)[al], sem[al]),
            "alerte_taux": float(y[al].mean()) if al.any() else float("nan"),
            "base_pendant_alerte": float(pb[al].mean()) if al.any() else float("nan"),
            "alerte_contre_hasard": ecart_deux(y[al], sem[al], y[ar], sem[ar]),
            "alerte_contre_t60": ecart_deux(y[al], sem[al], y[at], sem[at]),
            "hasard_alertes_pct": float(ar.mean() * 100), "t60_alertes_pct": float(at.mean() * 100),
            "brier": moyenne((y - pb) ** 2 - (y - np.nan_to_num(pm, nan=0.0)) ** 2, sem),
            "aire": aire(pm, y), "aire_hasard": aire(pr, y), "aire_t60": aire(pt, y)}


def mesure_sens(sm: np.ndarray, sr: np.ndarray, st: np.ndarray, vrai: np.ndarray, sem: np.ndarray) -> dict:
    """Sur les moments à gros mouvement de sens connu : sens de la mémoire contre 50 %, au hasard, tendance 60 j."""
    base = vrai != 0
    m = base & (sm != 0)
    juste = (sm == vrai).astype(np.float64)
    mr = m & (sr != 0)
    mt = m & (st != 0)
    return {"gros_sens_connu": int(base.sum()), "hausse_pct": float((vrai[base] > 0).mean() * 100) if base.any() else float("nan"),
            "donne_un_sens_pct": float(m.sum() / max(base.sum(), 1) * 100),
            "justes_pct": float(juste[m].mean() * 100) if m.any() else float("nan"),
            "contre_50": moyenne(juste[m] - 0.5, sem[m]),
            "contre_hasard": moyenne(juste[mr] - (sr == vrai)[mr], sem[mr]),
            "hasard_justes_pct": float((sr == vrai)[mr].mean() * 100) if mr.any() else float("nan"),
            "contre_t60": moyenne(juste[mt] - (st == vrai)[mt], sem[mt]),
            "t60_justes_pct": float((st == vrai)[mt].mean() * 100) if mt.any() else float("nan")}


def sens_majorite(pr: dict) -> np.ndarray:
    return np.sign(pr["up"] - pr["dn"]).astype(np.int8)


def signaux(pr: dict, pb: np.ndarray) -> np.ndarray:
    """Sens du trade (+1 / -1 / 0) quand la mémoire est confiante."""
    tot = pr["up"] + pr["dn"]
    part = np.where(tot > 0, pr["up"] / np.maximum(tot, 1), 0.5)
    conf = np.isfinite(pr["p"]) & (pr["p"] >= ALERTE * pb) & (pr["n_gros"] >= MIN_GROS)
    return np.where(conf & (part >= PART_SENS), 1, np.where(conf & (part <= 1 - PART_SENS), -1, 0)).astype(np.int8)


# ============================================================================================== 3. le trading
def stops_structure(x: dict, rows: np.ndarray, sens: np.ndarray) -> np.ndarray:
    """Stop derrière le dernier creux (achat) / sommet (vente) confirmé H1 + 0,1 A, sinon H4 ; NaN si aucun permis."""
    c, A, demi = (np.asarray(x[k], np.float64) for k in ("c", "A", "demi"))
    p, Ar, fr = c[rows], A[rows], 2 * demi[rows] * c[rows]
    st = np.full(len(rows), np.nan)
    for u in ("H1", "H4"):
        lg = np.asarray(x[u]["ligne"]).astype(np.int64)[rows]
        sw = np.asarray(x[u]["sw"], np.float64)[np.clip(lg, 0, None)]
        niv = np.where(sens > 0, sw[:, 2] - MARGE_A * Ar, sw[:, 0] + MARGE_A * Ar)
        rd = sens * (p - niv)
        ok = (lg >= 0) & np.isfinite(niv) & (rd >= RISQUE_MIN_A * Ar) & (rd <= RISQUE_MAX_A * Ar) & (rd > fr) & np.isnan(st)
        st = np.where(ok, niv, st)
    return st


def trades(x: dict, rows: np.ndarray, sens: np.ndarray, de_ns: int, a_ns: int) -> dict:
    """Trades des signaux (lignes de 15 min `rows`) joués par le moteur de l'arbre avec stop suiveur H1, sans objectif,
    un à la fois, et leur jumeau retourné."""
    from collapsar.ecole.precision import juge_trade as JT
    from collapsar.ecole.precision.reglages import R
    from collapsar.ecole.precision.univers import Univers
    from collapsar.regarder.pistes import logique_inversee as LI
    from collapsar.regarder.pistes import mouvements as MV
    t15 = np.asarray(x["t15"], np.int64)
    c, A = np.asarray(x["c"], np.float64), np.asarray(x["A"], np.float64)
    st = stops_structure(x, rows, sens)
    ok = np.isfinite(st) & (sens != 0)
    rows, sens, st = rows[ok], sens[ok].astype(np.float64), st[ok]
    debut = max(pd.Timestamp(int(t15[0])) + pd.Timedelta(days=45), pd.Timestamp(de_ns) - pd.Timedelta(days=5))
    U = Univers([(MARCHE, False)], debut, pd.Timestamp(a_ns) + pd.Timedelta(days=40), "cpu")
    ch = JT.chemin(U)
    gl = float(R().monde.frais_stop_glissement)
    m = np.searchsorted(t15, U.t_ns)
    assert np.array_equal(t15[np.clip(m, 0, len(t15) - 1)], U.t_ns)
    tv_l, tid_l, tv_s, tid_s = MV.suiveur_lignes(x, "H1", m - 1)
    dans = t15[rows] >= U.t_ns[0]
    rows, sens, st = rows[dans], sens[dans], st[dans]
    tU = np.searchsorted(U.t_ns, t15[rows]).astype(np.int64)
    assert np.array_equal(U.t_ns[np.clip(tU, 0, U.T - 1)], t15[rows])
    n = len(tU)
    p, Ar = c[rows], A[rows]
    mg = MARGE_A * Ar
    jo = lambda sg, s_: MV.jouer(*ch, tU, sg, s_, np.full(len(tU), np.nan), np.zeros(len(tU)), np.ones(len(tU), bool),
                                 HORIZON_TRADE, gl, tv_l, tid_l, tv_s, tid_s, mg)
    exe, ne, ns, rr, code, mfe = jo(sens, st)
    kg = LI.garder_un_a_la_fois(tU, exe, ns, code)
    tU, sens, st, p, Ar, mg, rows = tU[kg], sens[kg], st[kg], p[kg], Ar[kg], mg[kg], rows[kg]
    exe, ne, ns, rr, code, mfe = exe[kg], ne[kg], ns[kg], rr[kg], code[kg], mfe[kg]
    n = len(tU)
    tn = lambda k: np.where(k >= 0, U.t_ns[np.clip(k, 0, U.T - 1)], -1)
    rd = sens * (p - st)
    z = {"dec_ns": U.t_ns[tU] + QUINZE_NS, "sens": sens.astype(np.int8), "risque_A": rd / Ar, "risque_pct": rd / p * 100,
         "frais_R": (2.0 + gl) * U.demi[np.clip(tU + 1, 0, U.T - 1), 0] * p / rd,
         "exe": exe, "r": rr, "code": code, "ne_ns": tn(ne), "ns_ns": tn(ns), "mfe": mfe}
    if n:
        jo2 = MV.jouer(*ch, tU, -sens, 2 * p - st, np.full(n, np.nan), np.zeros(n), np.ones(n, bool), HORIZON_TRADE, gl,
                       tv_l, tid_l, tv_s, tid_s, mg)
        exe_j, ne_j, ns_j, rr_j, code_j, _ = jo2
        z.update({"exe_j": exe_j, "r_j": rr_j, "code_j": code_j, "ne_j_ns": tn(ne_j), "ns_j_ns": tn(ns_j)})
    del U, ch
    return z


def mesure_trades(z: dict, periode: str) -> dict:
    from collapsar.regarder.pistes import mouvements as MV
    if not len(z.get("exe", [])) or "exe_j" not in z:
        return {"variante": {"n": 0}}
    mois = MV.mois_periode(periode, z["dec_ns"])
    return {"variante": MV.bloc(z, mois), "retourne": MV.bloc(z, mois, "_j"), "avance_jumeau": MV.avance(z, "_j", True)}


# ============================================================================================== calcul
def _periode_ns(periode: str) -> tuple[int, int]:
    de, a = PERIODES[periode]
    return pd.Timestamp(de).value, pd.Timestamp(a).value


def calculer(dire=print) -> None:
    """Les souvenirs, leurs vecteurs, leur suite, et les voisins (honnêtes, au hasard, tendance 60 j seule, version qui
    triche) de chaque moment depuis 2008. Rangés dans vie/memoire/calcul/."""
    from collapsar.ecole.precision import structure as S
    t0 = time.time()
    x = S.lire(MARCHE, False)
    rows = moments(x)
    t15 = np.asarray(x["t15"], np.int64)
    dec = t15[rows] + QUINZE_NS
    V = vecteurs(x, rows)
    su = suites(x, rows)
    sc = echelle(V, dec)
    X = V / sc
    dire(f"{len(rows)} moments, vecteurs et suites ({time.time() - t0:.0f} s) ; gros mouvements {su['gros'][su['ok']].mean():.1%}")
    mem = su["ok"]                                   # souvenirs = moments dont la suite de 72 h existe dans les données
    im = np.flatnonzero(mem)
    q = np.flatnonzero(mem & (dec >= pd.Timestamp(DEBUT_QUESTIONS).value))
    lim = limite_memoire(su["fin_ns"][im], dec[q])
    garde = lim >= MEMOIRE_MIN
    q, lim = q[garde], lim[garde]
    Xm, Xq = X[im], X[q]
    nb = voisins(Xq, lim, Xm, KMAX)
    dire(f"voisins honnêtes : {len(q)} questions ({time.time() - t0:.0f} s)")
    nt = voisins(Xq[:, [I_T60]], lim, Xm[:, [I_T60]], KMAX)
    dire(f"voisins tendance 60 j seule ({time.time() - t0:.0f} s)")
    nr = au_hasard(lim, KMAX)
    # version qui TRICHE (test piège) : toute la mémoire, futur compris, sauf le moment lui-même ; 1 moment sur 4 du choix
    de_c, a_c = _periode_ns("choix")
    qc = np.flatnonzero((dec[q] >= de_c) & (dec[q] < a_c))[::4]
    soi = np.searchsorted(im, q[qc])
    ntr = voisins(Xq[qc], np.full(len(qc), len(im)), Xm, KMAX, soi=soi)
    dire(f"voisins de la version qui triche : {len(qc)} questions ({time.time() - t0:.0f} s)")
    dos = SORTIE / "calcul"
    dos.mkdir(parents=True, exist_ok=True)
    np.savez(dos / "souvenirs.npz", rows=rows, dec=dec, V=V, echelle=sc, **{k: v for k, v in su.items()})
    np.savez(dos / "voisins.npz", im=im, q=q, lim=lim, nb=nb, nt=nt, nr=nr, qc=qc, ntr=ntr)
    (dos / "fait.json").write_text(json.dumps({"date": datetime.now().isoformat(timespec="seconds"),
                                               "moments": int(len(rows)), "souvenirs": int(len(im)),
                                               "questions": int(len(q)), "triche": int(len(qc))}), encoding="utf-8")


def charger() -> dict:
    dos = SORTIE / "calcul"
    s = dict(np.load(dos / "souvenirs.npz"))
    v = dict(np.load(dos / "voisins.npz"))
    return {**s, **v}


def preparer_questions(C: dict, sel: np.ndarray) -> dict:
    """Pour les questions `sel` (indices dans C['q']) : vérité, repères, prévisions de chaque k."""
    im, q = C["im"], C["q"][sel]
    gros_m, sens_m = C["gros"][im], C["sens"][im].astype(np.int64)
    lim = C["lim"][sel]
    out = {"y": C["gros"][q], "vrai": C["sens"][q].astype(np.int64), "sem": C["dec"][q] // SEMAINE_NS,
           "pb": taux_base(lim, gros_m), "t60": np.sign(C["V"][q, I_T60]).astype(np.int64), "rows": C["rows"][q],
           "dec": C["dec"][q]}
    for k in KS:
        out[f"m{k}"] = predire(C["nb"][sel], k, gros_m, sens_m)
        out[f"r{k}"] = predire(C["nr"][sel], k, gros_m, sens_m)
        out[f"t{k}"] = predire(C["nt"][sel], k, gros_m, sens_m)
    return out


def mesures_k(Q: dict, k: int) -> dict:
    m, r, t = Q[f"m{k}"], Q[f"r{k}"], Q[f"t{k}"]
    return {"gros": mesure_gros(m["p"], r["p"], t["p"], Q["pb"], Q["y"], Q["sem"]),
            "sens": mesure_sens(sens_majorite(m), sens_majorite(r), Q["t60"], Q["vrai"], Q["sem"])}


def piege(C: dict) -> dict:
    """Test piège : même mesure, mémoire honnête contre mémoire qui triche, sur les mêmes moments (1 sur 4 du choix)."""
    im = C["im"]
    sel = np.searchsorted(C["q"], C["q"][C["qc"]])
    Q = preparer_questions(C, sel)
    gros_m, sens_m = C["gros"][im], C["sens"][im].astype(np.int64)
    out = {}
    for k in KS:
        tr = predire(C["ntr"], k, gros_m, sens_m)
        h = Q[f"m{k}"]
        dummy = Q[f"r{k}"]["p"]
        out[str(k)] = {"honnete": mesure_gros(h["p"], dummy, dummy, Q["pb"], Q["y"], Q["sem"]),
                       "triche": mesure_gros(tr["p"], dummy, dummy, Q["pb"], Q["y"], Q["sem"]),
                       "sens_honnete": mesure_sens(sens_majorite(h), sens_majorite(Q[f"r{k}"]), Q["t60"], Q["vrai"], Q["sem"]),
                       "sens_triche": mesure_sens(sens_majorite(tr), sens_majorite(Q[f"r{k}"]), Q["t60"], Q["vrai"], Q["sem"])}
    return out


def descriptif(C: dict) -> dict:
    """Ce que la mémoire retient (taux de gros mouvements par période, sur tous les souvenirs)."""
    im = C["im"]
    out = {}
    for per in ["echauffement"] + list(PERIODES):
        if per == "echauffement":
            m = C["dec"][im] < pd.Timestamp(DEBUT_QUESTIONS).value
        else:
            de, a = _periode_ns(per)
            m = (C["dec"][im] >= de) & (C["dec"][im] < a)
        j = im[m]
        g = C["gros"][j]
        out[per] = {"moments": int(len(j)), "gros72_pct": float(g.mean() * 100), "gros24_pct": float(C["gros24"][j].mean() * 100),
                    "gros_hausse_pct": float((C["sens"][j][g] > 0).mean() * 100) if g.any() else float("nan"),
                    "haut72_moy": float(np.nanmean(C["haut72"][j])), "bas72_moy": float(np.nanmean(C["bas72"][j])),
                    "net72_moy": float(np.nanmean(C["net72"][j]))}
    return out


def etape(periode: str, dire=print) -> dict:
    from collapsar.ecole.precision import structure as S
    from collapsar.regarder.pistes import mouvements as MV
    if periode == "controle" and (SORTIE / "controle.json").exists():
        raise SystemExit("le contrôle a déjà été fait (une seule fois)")
    C = charger()
    de, a = _periode_ns(periode)
    sel = np.flatnonzero((C["dec"][C["q"]] >= de) & (C["dec"][C["q"]] < a))
    Q = preparer_questions(C, sel)
    if periode == "controle":
        ch = json.loads((SORTIE / "choix.json").read_text(encoding="utf-8"))
        ks_i, ks_ii, ks_iii = [ch["k_gros"]], [ch["k_sens"]], [ch["k_trade"]]
    else:
        ks_i = ks_ii = ks_iii = list(KS)
    res = {"periode": periode, "date": datetime.now().isoformat(timespec="seconds"), "questions": int(len(sel)), "k": {}}
    for k in sorted(set(ks_i) | set(ks_ii)):
        res["k"][str(k)] = mesures_k(Q, k)
    x = S.lire(MARCHE, False)
    res["trades"] = {}
    for k in ks_iii:
        sg = signaux(Q[f"m{k}"], Q["pb"])
        on = sg != 0
        z = trades(x, Q["rows"][on], sg[on].astype(np.int64), de, a)
        res["trades"][str(k)] = mesure_trades(z, periode)
        res["trades"][str(k)]["signaux_pct"] = float(on.mean() * 100)
        if "exe_j" in z and len(z["exe"]):
            res["trades"][str(k)]["compte"] = MV.compte_contre_jumeaux(z, RISQUE_COMPTE, periode)
        np.savez(SORTIE / f"trades_{periode}_k{k}.npz", **z)
        b = res["trades"][str(k)]["variante"]
        dire(f"{periode} k={k} : {b.get('n', 0)} trades, R moyen {b.get('r', float('nan')):+.3f}")
    if periode == "choix":
        res["piege"] = piege(C)
        res["descriptif"] = descriptif(C)
        f_ = lambda d: d["force"] if np.isfinite(d.get("force", np.nan)) else -np.inf
        res["k_gros"] = max(KS, key=lambda k: f_(res["k"][str(k)]["gros"]["alerte_contre_base"]))
        res["k_sens"] = max(KS, key=lambda k: f_(res["k"][str(k)]["sens"]["contre_hasard"]))
        el = [k for k in KS if res["trades"][str(k)]["variante"].get("n", 0) >= 100]
        res["k_trade"] = max(el, key=lambda k: f_(res["trades"][str(k)]["variante"])) if el else KS[0]
        dire(f"retenus sur 2008-2021 : k gros {res['k_gros']}, k sens {res['k_sens']}, k trading {res['k_trade']}")
    else:
        ch = json.loads((SORTIE / "choix.json").read_text(encoding="utf-8"))
        for kk in ("k_gros", "k_sens", "k_trade"):
            res[kk] = ch[kk]
    (SORTIE / f"{periode}.json").write_text(json.dumps(res, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
    return res


# ============================================================================================== verdicts et rapport
def verdicts(ch: dict, ve: dict, co: dict) -> dict:
    kg, ks, kt = str(ch["k_gros"]), str(ch["k_sens"]), str(ch["k_trade"])
    g = [r["k"][kg]["gros"] for r in (ch, ve, co)]
    s = [r["k"][ks]["sens"] for r in (ch, ve, co)]
    t = [r["trades"][kt]["variante"] for r in (ch, ve, co)]
    pos = lambda xs, f: all(np.isfinite(f(x)) and f(x) > 0 for x in xs)
    i_reel = pos(g, lambda d: d["alerte_contre_base"]["m"]) and g[2]["alerte_contre_base"]["force"] >= SEUIL
    i_t60 = i_reel and g[2]["alerte_contre_t60"]["force"] >= SEUIL
    ii_reel = pos(s, lambda d: d["contre_hasard"]["m"]) and s[2]["contre_hasard"]["force"] >= SEUIL
    ii_t60 = pos(s, lambda d: d["contre_t60"]["m"]) and s[2]["contre_t60"]["force"] >= SEUIL
    r_ok = pos(t, lambda d: d.get("r", np.nan))
    f3 = t[2].get("force", np.nan)
    iii = "PROUVÉ" if r_ok and f3 >= SEUIL else ("PROMETTEUR (non prouvé)" if r_ok and f3 > 2 else "non")
    return {"i": "RÉELLE" if i_reel else "non", "i_t60": i_t60, "ii": "RÉEL" if ii_reel else "non", "ii_t60": ii_t60,
            "iii": iii}


def _f(x, n=3, signe=True):
    if x is None or (isinstance(x, float) and not np.isfinite(x)):
        return "—"
    return f"{x:+.{n}f}" if signe else f"{x:.{n}f}"


def _lire(nom):
    f = SORTIE / f"{nom}.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else None


def lignes_gros(r: dict, ks) -> list[str]:
    L = ["| k | taux de base | alertes (part du temps) | gros mouvements pendant l'alerte | écart à la base (force) | "
         "au hasard : taux pendant ses alertes ; écart (force) | tendance 60 j : taux ; écart (force) | précision Brier "
         "(force) | aire mémoire / hasard / tendance |", "|---|---|---|---|---|---|---|---|---|"]
    for k in ks:
        g = r["k"][str(k)]["gros"]
        ab, ah, at, br = g["alerte_contre_base"], g["alerte_contre_hasard"], g["alerte_contre_t60"], g["brier"]
        L.append(f"| {k} | {g['base_taux'] * 100:.1f} % | {g['alertes_pct']:.1f} % | {_f(g['alerte_taux'] * 100, 1, False)} % "
                 f"(base {_f(g['base_pendant_alerte'] * 100, 1, False)} %) | {_f(ab['m'] * 100, 1)} pts ({_f(ab['force'], 1)}) | "
                 f"{_f(ah['taux_b'] * 100, 1, False)} % ; {_f(ah['m'] * 100, 1)} pts ({_f(ah['force'], 1)}) | "
                 f"{_f(at['taux_b'] * 100, 1, False)} % ; {_f(at['m'] * 100, 1)} pts ({_f(at['force'], 1)}) | "
                 f"{_f(br['m'] * 1000, 2)} ‰ ({_f(br['force'], 1)}) | {_f(g['aire'], 3, False)} / {_f(g['aire_hasard'], 3, False)} / "
                 f"{_f(g['aire_t60'], 3, False)} |")
    return L


def lignes_sens(r: dict, ks) -> list[str]:
    L = ["| k | gros mouvements (sens connu) ; dont hausse | la mémoire donne un sens | sens justes | contre 50 % (force) | "
         "au hasard : justes ; écart (force) | tendance 60 j : justes ; écart (force) |", "|---|---|---|---|---|---|---|"]
    for k in ks:
        s = r["k"][str(k)]["sens"]
        L.append(f"| {k} | {s['gros_sens_connu']} ; {_f(s['hausse_pct'], 0, False)} % | {_f(s['donne_un_sens_pct'], 0, False)} % | "
                 f"{_f(s['justes_pct'], 1, False)} % | {_f(s['contre_50']['m'] * 100, 1)} pts ({_f(s['contre_50']['force'], 1)}) | "
                 f"{_f(s['hasard_justes_pct'], 1, False)} % ; {_f(s['contre_hasard']['m'] * 100, 1)} pts "
                 f"({_f(s['contre_hasard']['force'], 1)}) | {_f(s['t60_justes_pct'], 1, False)} % ; "
                 f"{_f(s['contre_t60']['m'] * 100, 1)} pts ({_f(s['contre_t60']['force'], 1)}) |")
    return L


def lignes_trades(r: dict, ks) -> list[str]:
    L = ["| k | signaux (part du temps) | trades | trades / mois | gagnants | R moyen ± incertitude (force) | médiane | "
         ">= 5R / >= 10R | durée | jumeau : R ; avance (force) | compte 0,5 % : gain / mois ; baisse max ; réussis / morts ; "
         "jumeaux |", "|---|---|---|---|---|---|---|---|---|---|---|"]
    for k in ks:
        t = r["trades"].get(str(k))
        if not t:
            continue
        b = t["variante"]
        if not b.get("n"):
            L.append(f"| {k} | {t.get('signaux_pct', 0):.1f} % | 0 | — | — | — | — | — | — | — | — |")
            continue
        aj, rj = t["avance_jumeau"], t["retourne"]
        c = t.get("compte")
        cc = (f"{c['reel']['gain_mois_pct']:+.2f} % ; {c['reel']['baisse_max_pct']:.1f} % ; {c['reel']['reussis']} / "
              f"{c['reel']['morts']} ; {c['jumeaux_gain_mois_moyen']:+.2f} % ({c['jumeaux_au_moins_aussi_bien_pct']:.0f} % "
              "aussi bons)") if c else "—"
        L.append(f"| {k} | {t['signaux_pct']:.1f} % | {b['n']} | {b['trades_mois']:.1f} | {b['gagnants_pct']:.0f} % | "
                 f"{_f(b['r'])} ± {_f(b['inc'], 3, False)} ({_f(b['force'], 1)}) | {_f(b['mediane'])} | {b['p5']:.1f} % / "
                 f"{b['p10']:.1f} % | {b['duree_h']:.0f} h | {_f(rj.get('r'))} ; {_f(aj['avance'])} ({_f(aj['force'], 1)}) | {cc} |")
    return L


def ecrire_rapport():
    ch, ve, co = _lire("choix"), _lire("verification"), _lire("controle")
    L = [f"# LA MÉMOIRE DES SITUATIONS — l'or (rapport du {datetime.now():%d/%m/%Y %H:%M})", "",
         "Mesure SANS IA. A = agitation (moyenne plus haut - plus bas des 14 derniers jours). Gros mouvement = au moins "
         f"{GROS_A:g} A d'un côté dans les 72 h. Force = écart / incertitude (grappes = semaines). N = {N_TOTAL} cases -> "
         f"seuil de preuve {SEUIL:.2f}.", ""]
    f_c = SORTIE / "conclusion.md"
    if f_c.exists():
        L.append(f_c.read_text(encoding="utf-8").strip() + "\n")
    if ch:
        L.append("## Ce qu'elle retient (tous les souvenirs)\n")
        L.append("| période | moments | gros mouvements 72 h | dont à la hausse | gros en 24 h | avance moy. hausse / baisse 72 h | net 72 h |")
        L.append("|---|---|---|---|---|---|---|")
        for per, d in ch["descriptif"].items():
            L.append(f"| {per} | {d['moments']} | {d['gros72_pct']:.1f} % | {_f(d['gros_hausse_pct'], 0, False)} % | "
                     f"{d['gros24_pct']:.1f} % | {d['haut72_moy']:.2f} / {d['bas72_moy']:.2f} A | {_f(d['net72_moy'], 2)} A |")
        L.append("")
        L.append("## Test piège (2008-2021, 1 moment sur 4) : mémoire honnête contre mémoire qui triche\n")
        L.append("| k | honnête : taux pendant l'alerte ; écart (force) ; aire | triche : taux pendant l'alerte ; écart (force) ; aire | "
                 "sens justes honnête / triche |")
        L.append("|---|---|---|---|")
        for k, d in ch["piege"].items():
            h, t = d["honnete"], d["triche"]
            L.append(f"| {k} | {_f(h['alerte_taux'] * 100, 1, False)} % ; {_f(h['alerte_contre_base']['m'] * 100, 1)} pts "
                     f"({_f(h['alerte_contre_base']['force'], 1)}) ; {_f(h['aire'], 3, False)} | "
                     f"{_f(t['alerte_taux'] * 100, 1, False)} % ; {_f(t['alerte_contre_base']['m'] * 100, 1)} pts "
                     f"({_f(t['alerte_contre_base']['force'], 1)}) ; {_f(t['aire'], 3, False)} | "
                     f"{_f(d['sens_honnete']['justes_pct'], 1, False)} % / {_f(d['sens_triche']['justes_pct'], 1, False)} % |")
        L.append("")
    if ch and ve and co:
        v = verdicts(ch, ve, co)
        L.append(f"## Contrôle 01/2024 -> 09/2025 (une seule fois) — (i) gros mouvements : **{v['i']}**"
                 f"{' (au-delà de la tendance)' if v['i_t60'] else ''} ; (ii) sens : **{v['ii']}**"
                 f"{' (bat aussi la tendance 60 j)' if v['ii_t60'] else ''} ; (iii) trading : **{v['iii']}**\n")
        for nom_p, r in (("choix", ch), ("verification", ve), ("controle", co)):
            L.append(f"### (i) gros mouvements, k = {ch['k_gros']} — {NOM_P[nom_p]}\n")
            L += lignes_gros(r, [ch["k_gros"]])
            L.append("")
        for nom_p, r in (("choix", ch), ("verification", ve), ("controle", co)):
            L.append(f"### (ii) sens des gros mouvements, k = {ch['k_sens']} — {NOM_P[nom_p]}\n")
            L += lignes_sens(r, [ch["k_sens"]])
            L.append("")
        for nom_p, r in (("choix", ch), ("verification", ve), ("controle", co)):
            L.append(f"### (iii) trading sur ses souvenirs, k = {ch['k_trade']} — {NOM_P[nom_p]}\n")
            L += lignes_trades(r, [ch["k_trade"]])
            L.append("")
    for nom_p, r in (("choix", ch), ("verification", ve)):
        if not r:
            continue
        L.append(f"## Tous les k — {NOM_P[nom_p]}\n")
        L += lignes_gros(r, KS)
        L.append("")
        L += lignes_sens(r, KS)
        L.append("")
        L += lignes_trades(r, KS)
        L.append("")
    f_plan = SORTIE / "plan_fige.md"
    if f_plan.exists():
        L.append(f_plan.read_text(encoding="utf-8").replace("# LA MÉMOIRE", "## LA MÉMOIRE").replace("\n## ", "\n### "))
    (SORTIE / "rapport.md").write_text("\n".join(L), encoding="utf-8")


def dire_(t):
    print(f"[{datetime.now():%d/%m %H:%M:%S}] {t}", flush=True)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("quoi", choices=["plan", "calcul", "choix", "verification", "controle", "rapport"])
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
    if a.quoi == "calcul":
        calculer(dire_)
        return
    if a.quoi in ("choix", "verification", "controle"):
        if not (SORTIE / "calcul" / "fait.json").exists():
            raise SystemExit("faire d'abord le calcul")
        if a.quoi != "choix" and not (SORTIE / "choix.json").exists():
            raise SystemExit("faire d'abord le choix sur 2008-2021")
        if a.quoi == "controle" and not (SORTIE / "verification.json").exists():
            raise SystemExit("faire d'abord la vérification 2022-2023")
        etape(a.quoi, dire_)
    ecrire_rapport()
    dire_("rapport écrit : " + str(SORTIE / "rapport.md"))


if __name__ == "__main__":
    main()
