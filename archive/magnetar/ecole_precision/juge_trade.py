"""L'ÉCOLE « JUGER UN TRADE » de l'arbre HYPERNOVA (17/10/2026, ordre du chef de projet).

Idée : comme un trader qui a vu des milliers de graphiques, l'IA apprend d'abord à ESTIMER ce que vaut un trade AVANT de
le prendre. « Avec un objectif à 2 fois le risque, gagner plus d'1 trade sur 3 suffit » : on lui montre beaucoup de
trades qui ont valu 2R ET les perdants qui leur ressemblaient.

1. EXEMPLES (`exemples`) : sur tous les marchés réels de l'arbre (pas les miroirs), à des clôtures de 15 min tirées au
   hasard (plus souvent quand le prix est dans / près d'une de ses zones vivantes, à 0,5 agitation au plus), des TRADES
   CANDIDATS exprimés comme les mains de l'arbre (cerveau.py) : sens, entrée au marché ou ordre limite sur le bord proche
   / le milieu d'une de ses zones (toutes unités), stop derrière une zone (bord lointain) ou un creux / sommet, + marge,
   destination (zone opposée, sommet / creux, 2R, 3R), validité de l'ordre. Tirés UNIFORMÉMENT parmi les choix permis aux
   mains (mêmes règles : bon côté du prix, plus d'un aller-retour de frais, entrée à 6 agitations au plus).
   + 1 candidat TÉMOIN par instant : la géométrie d'un vrai candidat (distance de l'entrée, taille du risque en
   agitations, destination en R, unités...) posée à un autre instant, donc sur de FAUSSES zones au hasard.
   Résultat sur le vrai chemin du prix (`un_trade`, mêmes règles que simulateur.py : ordre à l'ouverture suivante, écart
   payé, bougie d'exécution jugée au pire, stop d'abord, stop + glissement, fermeture avant une pause > 2 h, nuits de
   chaque époque, validité de l'ordre) : exécuté ou non ; 1R / 2R / 3R touché avant le stop ; R final « tout à la
   destination » (A), « 80 % à 2R puis stop à l'entrée, le reste à la destination » (B), « tout à 2R » (C) ; durée.
   Ignorés (un seul trade, petit risque) : murs FTMO, inactivité, arrondi des lots, marge. Un trade encore ouvert après
   HORIZON bougies (10 jours) est fermé à l'ouverture suivante (comme si elle le fermait).
   SANS FUTUR dans les entrées : les yeux de vue.py (avec la foule) + la description du candidat (testé).
2. LE JUGE (`apprendre`) : un réseau prédit P(exécuté), P(1R / 2R / 3R avant le stop | exécuté), R attendu (A, B, C).
   Les exemples qui ont touché 2R pèsent POIDS_2R fois plus à l'apprentissage ; les probabilités sont ensuite RECALIBRÉES
   (correction exacte du poids sur la cote, puis ajustement sur 2022) pour rester honnêtes.
   Apprentissage : instants < 2022 ; réglages (arrêt, recalibration, seuils du classement) : 2022 ; mesures : 2023
   (sélection de l'arbre) et 01/2024 -> 09/2025 (contrôle). RIEN après 09/2025.
3. LA MESURE (`mesurer`, rapport `vie/hypernova/juge_trade/rapport.md`).
4. LA GREFFE PRÊTE (`greffer`, NON appliquée) : 8 notes du juge par marché (meilleur trade à 2R de chaque côté) ajoutées
   aux yeux de l'arbre, poids à ZÉRO (décisions identiques au départ, testé). Éteinte par défaut (réglage yeux.juge).

Depuis Test_IA :
  venv_gpu\\Scripts\\python.exe -u -m collapsar.ecole.precision.juge_trade exemples|assembler|apprendre|mesurer|tout
  venv_gpu\\Scripts\\python.exe -m collapsar.ecole.precision.juge_trade greffer --dossier <vie d'un arbre ARRÊTÉ>
"""
from __future__ import annotations

import argparse
import json
import math
import os
import shutil
import time
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from numba import njit
from torch import nn

from collapsar.ecole.precision import cerveau as C
from collapsar.ecole.precision import donnees as D
from collapsar.ecole.precision import structure as S
from collapsar.ecole.precision.reglages import R, VIE

DOSSIER = VIE / "juge_trade"
VERSION = 1
HORIZON = 960                       # bougies de 15 min (10 jours) : au-delà, le trade est fermé
P_MARCHE = 0.25                     # part des candidats au marché quand un ordre limite est aussi possible
P_PROCHE, P_LOIN = 0.12, 0.03       # chance de garder une clôture près / loin de ses zones
PROCHE_AGITATION = 0.5
N_REELS, N_TEMOINS = 3, 1           # candidats par instant gardé
POIDS_2R = 3.0                      # les trades qui ont touché 2R pèsent 3 fois plus à l'apprentissage
EMBARGO = pd.Timedelta(days=15)     # instants retirés avant chaque frontière (un trade ne déborde pas sur la suivante)
PERIODES = {"apprentissage": (None, "2022-01-01"), "reglage": ("2022-01-01", "2023-01-01"),
            "selection_2023": ("2023-01-01", "2024-01-01"), "controle_2024_25": ("2024-01-01", "2025-10-01")}
CODE_P = {"apprentissage": 0, "reglage": 1, "selection_2023": 2, "controle_2024_25": 3}
NJ = 8                              # notes du juge données à l'arbre par marché (greffe)

# codes de sortie d'un trade
STOP, DEST, FORCEE, HORIZON_C, REFUS, EXPIRE, FIN = 1, 4, 8, 64, 32, 256, 512


# ============================================================================================== 1. le chemin du prix
@njit(cache=True)
def un_trade(o, h, l, c, fx, ouvert, derniere, demi, nuit_a, nuit_v, nuits, t, sens, limite, P, stop0, dest,
             dest_r, tp1_r, part, validite, horizon, gl):
    """Un trade décidé à la clôture de la bougie t, joué comme simulateur.pas_comptes (une position, un marché).
    Rend (exécuté, ligne d'entrée, ligne de sortie, R frais et nuits compris, code de sortie).
    dest_r > 0 : destination à dest_r fois le risque de l'entrée RÉELLE ; tp1_r > 0 : objectif 1 à tp1_r fois le risque,
    `part` y est encaissée et le stop du reste passe à l'entrée (actif à la bougie suivante)."""
    T = len(o)
    lg = sens > 0
    sg = 1.0 if lg else -1.0
    pos = False
    att = limite
    reste = validite
    entree, st, u = np.nan, stop0, 0.0
    t1, d1, pt = np.nan, np.nan, 0.0
    tp1_fait = False
    pnl, risque = 0.0, np.nan
    ne = -1
    for n in range(t + 1, T):
        s = demi[n]
        oo, hh, ll = o[n], h[n], l[n]
        f = fx[n]
        # 1. un ordre en attente est annulé avant une pause de plus de 2 h
        if att and derniere[n]:
            return False, -1, n, np.nan, EXPIRE
        # 3. fermeture (pause, horizon) / ouverture au marché, à l'ouverture de la bougie
        if ouvert[n]:
            if pos and (derniere[n] or n - ne >= horizon):
                px = oo * (1 - s) if lg else oo * (1 + s)
                pnl += sg * u * (px - entree) * f
                return True, ne, n, pnl / risque, FORCEE if derniere[n] else HORIZON_C
            if (not limite) and n == t + 1:
                if derniere[n]:
                    return False, -1, n, np.nan, REFUS
                vente_o, achat_o = oo * (1 - s), oo * (1 + s)
                if not np.isfinite(st) or not ((lg and st < vente_o) or ((not lg) and st > achat_o)):
                    return False, -1, n, np.nan, REFUS
                px = achat_o if lg else vente_o
                pos, entree, ne, u = True, px, n, 1.0
                risque = abs(px - st) * f
                d1 = px + sg * dest_r * abs(px - st) if dest_r > 0 else dest
                t1 = px + sg * tp1_r * abs(px - st) if tp1_r > 0 else np.nan
                if np.isfinite(d1) and not ((lg and d1 > vente_o) or ((not lg) and d1 < achat_o)):
                    d1 = np.nan
                if np.isfinite(t1) and np.isfinite(d1) and sg * (d1 - t1) <= 0:
                    t1 = np.nan
                pt = part if np.isfinite(t1) else 0.0
        elif (not limite) and n == t + 1:
            return False, -1, n, np.nan, REFUS
        # 4. stop (d'abord : le pire cas), objectif 1, destination
        if pos and ouvert[n]:
            if np.isfinite(st) and ((lg and ll * (1 - s) <= st) or ((not lg) and hh * (1 + s) >= st)):
                if lg:
                    px = min(st, oo * (1 - s)) * (1 - gl * s)
                else:
                    px = max(st, oo * (1 + s)) * (1 + gl * s)
                pnl += sg * u * (px - entree) * f
                return True, ne, n, pnl / risque, STOP
            if pt > 0 and (not tp1_fait) and np.isfinite(t1) and \
                    ((lg and hh * (1 - s) >= t1) or ((not lg) and ll * (1 + s) <= t1)):
                px = max(t1, oo * (1 - s)) if lg else min(t1, oo * (1 + s))
                pnl += sg * pt * (px - entree) * f
                u -= pt
                tp1_fait = True
                st = entree
            if np.isfinite(d1) and (pt == 0 or tp1_fait or not np.isfinite(t1)) and \
                    ((lg and hh * (1 - s) >= d1) or ((not lg) and ll * (1 + s) <= d1)):
                px = max(d1, oo * (1 - s)) if lg else min(d1, oo * (1 + s))
                pnl += sg * u * (px - entree) * f
                return True, ne, n, pnl / risque, DEST
        # 5. l'ordre limite passe seulement si le prix va VRAIMENT au-delà du niveau
        if att:
            rempli = False
            if ouvert[n] and ((lg and ll * (1 + s) < P) or ((not lg) and hh * (1 - s) > P)):
                rempli = True
                px = min(P, oo * (1 + s)) if lg else max(P, oo * (1 - s))
                att = False
                pos, entree, ne, u = True, px, n, 1.0
                st = stop0
                risque = abs(px - st) * f
                d1 = px + sg * dest_r * abs(px - st) if dest_r > 0 else dest
                t1 = px + sg * tp1_r * abs(px - st) if tp1_r > 0 else np.nan
                if np.isfinite(t1) and np.isfinite(d1) and sg * (d1 - t1) <= 0:
                    t1 = np.nan
                pt = part if np.isfinite(t1) else 0.0
                # bougie d'exécution jugée au pire
                if (lg and ll * (1 - s) <= st) or ((not lg) and hh * (1 + s) >= st):
                    if lg:
                        px2 = min(st, oo * (1 - s)) * (1 - gl * s)
                    else:
                        px2 = max(st, oo * (1 + s)) * (1 + gl * s)
                    pnl += sg * (px2 - px) * f
                    return True, n, n, pnl / risque, STOP
            if not rempli:
                reste -= 1
                if reste <= 0:
                    return False, -1, n, np.nan, EXPIRE
        # 6. frais de nuit sur le prix d'ouverture
        if pos:
            taux = nuit_a[n] if lg else nuit_v[n]
            pnl -= u * o[n] * f * taux / 360.0 * nuits[n]
    if pos:
        n = T - 1
        px = c[n] * (1 - demi[n]) if lg else c[n] * (1 + demi[n])
        pnl += sg * u * (px - entree) * fx[n]
        return True, ne, n, pnl / risque, FIN
    return False, -1, T - 1, np.nan, FIN


@njit(cache=True)
def trades(o, h, l, c, fx, ouvert, derniere, demi, nuit_a, nuit_v, nuits, t, sens, limite, P, stop, dest, dest_r,
           tp1_r, part, validite, horizon, gl):
    n = len(t)
    exe = np.zeros(n, np.bool_)
    ne = np.full(n, -1, np.int64)
    ns = np.full(n, -1, np.int64)
    rr = np.full(n, np.nan)
    code = np.zeros(n, np.int64)
    for i in range(n):
        exe[i], ne[i], ns[i], rr[i], code[i] = un_trade(
            o, h, l, c, fx, ouvert, derniere, demi, nuit_a, nuit_v, nuits, t[i], sens[i], limite[i], P[i], stop[i],
            dest[i], dest_r[i], tp1_r[i], part[i], validite[i], horizon, gl)
    return exe, ne, ns, rr, code


def chemin(U, j: int = 0) -> tuple:
    """Les tableaux du simulateur d'un marché d'un monde (univers.py), dans l'ordre de `trades`."""
    col = lambda x: np.ascontiguousarray(np.asarray(x)[:, j])
    return (col(U.o), col(U.h), col(U.l), col(U.c), col(U.fx), col(U.ouvert), col(U.derniere), col(U.demi),
            col(U.nuit_a), col(U.nuit_v), col(U.nuits).astype(np.float64))


def resultats(ch: tuple, cand: dict, horizon: int = HORIZON) -> dict:
    """Les 5 façons de jouer chaque candidat sur le vrai chemin du prix : A (tout à la destination), B (80 % à 2R puis
    stop à l'entrée), et tout à 1R / 2R (= C) / 3R (pour « a touché kR avant le stop »)."""
    gl = float(R().monde.frais_stop_glissement)
    n = len(cand["t"])
    base = (np.asarray(cand["t"], np.int64), np.asarray(cand["sens"], np.float64), np.asarray(cand["limite"], np.bool_),
            np.asarray(cand["P"], np.float64), np.asarray(cand["stop"], np.float64))
    val = np.asarray(cand["validite"], np.int64)
    nan = np.full(n, np.nan)
    zero = np.zeros(n)
    d_abs, d_r = np.asarray(cand["dest"], np.float64), np.asarray(cand["dest_r"], np.float64)
    d_abs = np.where(d_r > 0, np.nan, d_abs)
    out = {}
    for nom, dest, dr, tr, part in (("A", d_abs, d_r, zero, zero), ("B", d_abs, d_r, zero + 2.0, zero + 0.8),
                                    ("1", nan, zero + 1, zero, zero), ("C", nan, zero + 2, zero, zero),
                                    ("3", nan, zero + 3, zero, zero)):
        exe, ne, ns, rr, code = trades(*ch, *base, dest, dr, tr, part, val, horizon, gl)
        out[nom] = (exe, ne, ns, rr, code)
    exe, ne, ns, rA, codeA = out["A"]
    fin = np.zeros(n, bool)
    for v in out.values():
        fin |= v[4] == FIN
    return {"exe": exe, "ne": ne, "duree": np.where(exe, out["A"][2] - ne, -1).astype(np.int32),
            "rA": rA.astype(np.float32), "rB": out["B"][3].astype(np.float32), "rC": out["C"][3].astype(np.float32),
            "hit1": out["1"][4] == DEST, "hit2": out["C"][4] == DEST, "hit3": out["3"][4] == DEST,
            "codeA": codeA.astype(np.int16), "fin": fin}


# ============================================================================================== 2. les candidats
def options(s: dict) -> dict:
    """Les niveaux que les mains de l'arbre peuvent choisir (cerveau.niveaux + mêmes règles que cerveau.politique),
    pour un seul marché (J = 1) : [n, 2 côtés, places]."""
    nv = C.niveaux(s)
    q = lambda x: x[:, 0]
    p, A, demi = s["p"][:, 0], s["A"][:, 0], s["demi"][:, 0]
    fr = 2 * demi * p
    sgn = torch.tensor([1.0, -1.0], device=p.device)[None, :, None]
    e, st, d = q(nv["entree"]), q(nv["stop"]), q(nv["dest"])
    p3, f3, A3 = p[:, None, None], fr[:, None, None], A[:, None, None]
    st_ok = q(nv["stop_ok"])
    derriere = st_ok[:, :, None, :] & (sgn[..., None] * (e[..., None] - st[:, :, None, :]) > f3[..., None])
    e_ok = q(nv["entree_ok"]) & (sgn * (p3 - e) > f3) & \
        ((p3 - e).abs() <= R().mains.entree_max_agitation * A3) & derriere.any(-1)
    m_ok = (st_ok & (sgn * (p3 - st) > f3)).any(-1)
    return {"e": e, "st": st, "d": d, "e_ok": e_ok, "m_ok": m_ok, "st_ok": st_ok, "d_ok": q(nv["dest_ok"]),
            "e_att": q(nv["entree_att"]), "st_att": q(nv["stop_att"]), "d_att": q(nv["dest_att"]),
            "p": p, "A": A, "fr": fr}


def _uniforme(masque: torch.Tensor, gen) -> torch.Tensor:
    r = torch.rand(masque.shape, generator=gen, device=masque.device)
    return torch.where(masque, r, -1.0).argmax(-1)


def _onehot(i: torch.Tensor, n: int, ok: torch.Tensor) -> torch.Tensor:
    return torch.nn.functional.one_hot(i.clamp(0, n - 1), n).float() * ok.float()[:, None]


NOMS_DESC = (["achat_vente", "limite", "entree_marche", "entree_proche", "entree_milieu"]
             + [f"entree_{u}" for u in ("D1", "H4", "H1", "M30", "M15", "M5", "M3")]
             + ["entree_dist_A", "entree_touchee", "entree_reaction", "entree_zone_dans_zone", "entree_hauteur_A",
                "entree_age", "stop_zone", "stop_sommet"]
             + [f"stop_{u}" for u in ("D1", "H4", "H1", "M30", "M15", "M5", "M3")]
             + ["marge_A", "risque_A", "stop_touchee", "stop_reaction", "stop_zone_dans_zone", "stop_hauteur_A",
                "stop_age", "dest_zone", "dest_sommet", "dest_R_fixe"]
             + [f"dest_{u}" for u in ("D1", "H4", "H1", "M30", "M15", "M5", "M3")]
             + ["dest_dist_A", "dest_en_R", "dest_touchee", "dest_reaction", "dest_zone_dans_zone", "dest_hauteur_A",
                "dest_age", "frais_en_R", "frais_A", "validite_jours", "temoin", "log_risque_A"])
ND = len(NOMS_DESC)


def decrire(c: dict) -> torch.Tensor:
    """[m, ND] : ce que le juge sait d'un candidat (rien du futur : des niveaux et ce qu'on sait des zones à l'instant)."""
    nu = 7
    m = c["sig"].shape[0]
    lim = c["limite"].float()
    e_type = torch.nn.functional.one_hot(c["e_type"], 3).float()
    e_u = _onehot(c["e_unite"], nu, c["e_unite"] >= 0)
    st_t = torch.nn.functional.one_hot(c["st_type"], 2).float()
    st_u = _onehot(c["st_unite"], nu, c["st_unite"] >= 0)
    d_t = torch.nn.functional.one_hot(c["d_type"], 3).float()
    d_u = _onehot(c["d_unite"], nu, c["d_unite"] >= 0)
    A, rd = c["A"].clamp(min=1e-12), c["rd"].clamp(min=1e-12)
    sig = c["sig"]
    x = torch.cat([sig[:, None], lim[:, None], e_type, e_u, (sig * (c["e"] - c["p"]) / A)[:, None], c["e_att"],
                   st_t, st_u, (c["marge"] / A)[:, None], (rd / A)[:, None], c["st_att"], d_t, d_u,
                   (sig * (c["dest"] - c["e"]) / A)[:, None], (sig * (c["dest"] - c["e"]) / rd)[:, None], c["d_att"],
                   (c["fr"] / rd)[:, None], (c["fr"] / A * 10)[:, None], (c["validite"].float() / 96 * lim)[:, None],
                   c["temoin"].float()[:, None], torch.log(rd / A)[:, None]], 1)
    assert x.shape == (m, ND)
    return torch.nan_to_num(x, nan=0.0, posinf=0.0, neginf=0.0).clamp(-20, 20)


def tirer(o: dict, k: int, gen) -> dict:
    """k candidats par instant, tirés uniformément parmi les choix permis aux mains (côté, au marché / ordre limite,
    entrée, stop, marge, destination parmi zones opposées / sommets-creux / 2R / 3R, validité). Instants sans choix
    possible : rien."""
    K = R().yeux.zones_par_cote
    nz = 7 * K
    n = o["p"].shape[0]
    dev = o["p"].device
    inst = torch.arange(n, device=dev).repeat_interleave(k)
    m = len(inst)
    ar = torch.arange(m, device=dev)
    E_ok, M_ok = o["e_ok"][inst], o["m_ok"][inst]
    cote_ok = M_ok | E_ok.any(-1)
    valide = cote_ok.any(-1)
    ic = _uniforme(cote_ok, gen)
    eok, mok = E_ok[ar, ic], M_ok[ar, ic]
    peut_lim = eok.any(-1)
    lim = peut_lim & (~mok | (torch.rand(m, generator=gen, device=dev) >= P_MARCHE))
    ie = _uniforme(eok, gen)
    sig = 1.0 - 2.0 * ic.float()
    p, A, fr = o["p"][inst], o["A"][inst], o["fr"][inst]
    e = torch.where(lim, o["e"][inst, ic, ie], p)
    st_all = o["st"][inst, ic]
    sok = o["st_ok"][inst, ic] & (sig[:, None] * (e[:, None] - st_all) > fr[:, None])
    valide &= sok.any(-1)
    i_s = _uniforme(sok, gen)
    marges = torch.tensor(R().mains.marges_stop, device=dev)
    marge = marges[torch.randint(len(marges), (m,), generator=gen, device=dev)] * A
    stop = st_all[ar, i_s] - sig * marge
    rd = sig * (e - stop)
    d_all = o["d"][inst, ic]
    dok = o["d_ok"][inst, ic] & (sig[:, None] * (d_all - e[:, None]) > fr[:, None])
    dok = torch.cat([dok, torch.ones(m, 2, dtype=torch.bool, device=dev)], 1)
    i_d = _uniforme(dok, gen)
    nd = d_all.shape[1]
    dest_r = torch.where(i_d == nd, 2, torch.where(i_d == nd + 1, 3, 0))
    dest = torch.where(dest_r > 0, e + sig * dest_r * rd, d_all[ar, i_d.clamp(max=nd - 1)])
    vals = torch.tensor(R().mains.validites_ordre, device=dev)
    validite = vals[torch.randint(len(vals), (m,), generator=gen, device=dev)]
    z5 = torch.zeros(m, 5, device=dev)
    c = {"inst": inst, "sig": sig, "limite": lim, "e": e, "stop": stop, "dest": dest, "dest_r": dest_r,
         "validite": validite, "p": p, "A": A, "fr": fr, "rd": rd, "marge": marge,
         "e_type": torch.where(lim, 1 + ie // nz, torch.zeros_like(ie)),
         "e_unite": torch.where(lim, (ie % nz) // K, torch.full_like(ie, -1)),
         "e_att": torch.where(lim[:, None], o["e_att"][inst, ic, ie], z5),
         "st_type": (i_s >= nz).long(), "st_unite": torch.where(i_s < nz, i_s // K, (i_s - nz) // 2),
         "st_att": o["st_att"][inst, ic, i_s],
         "d_type": torch.where(i_d < nz, 0, torch.where(i_d < nd, 1, 2)),
         "d_unite": torch.where(i_d < nz, i_d // K, torch.where(i_d < nd, (i_d - nz) // 2, torch.full_like(i_d, -1))),
         "d_att": torch.where((i_d < nd)[:, None], o["d_att"][inst, ic, i_d.clamp(max=nd - 1)], z5),
         "temoin": torch.zeros(m, dtype=torch.bool, device=dev)}
    return {k_: v[valide] for k_, v in c.items()}


def temoins(c: dict, o: dict, k: int, gen) -> dict:
    """Candidats TÉMOINS : k par instant ; chacun reprend la géométrie d'un vrai candidat tiré au hasard (au marché /
    limite, distance de l'entrée et taille du risque en agitations, destination en R, validité, description des
    zones) et la pose à cet instant-ci, du côté tiré à pile ou face : ses niveaux tombent sur de FAUSSES zones."""
    n = o["p"].shape[0]
    dev = o["p"].device
    if len(c["sig"]) == 0 or n == 0:
        return {kk: v[:0] for kk, v in c.items()}
    inst = torch.arange(n, device=dev).repeat_interleave(k)
    m = len(inst)
    j = torch.randint(len(c["sig"]), (m,), generator=gen, device=dev)
    sig = torch.where(torch.rand(m, generator=gen, device=dev) < 0.5, 1.0, -1.0)
    p, A, fr = o["p"][inst], o["A"][inst], o["fr"][inst]
    lim = c["limite"][j]
    de = (c["sig"][j] * (c["e"][j] - c["p"][j]) / c["A"][j].clamp(min=1e-12)).clamp(max=0)
    dist = torch.maximum(-de * A, 1.5 * fr)
    e = torch.where(lim, p - sig * dist, p)
    rd = torch.maximum(c["rd"][j] / c["A"][j].clamp(min=1e-12) * A, 1.5 * fr)
    stop = e - sig * rd
    dR = c["sig"][j] * (c["dest"][j] - c["e"][j]) / c["rd"][j].clamp(min=1e-12)
    dest = e + sig * dR * rd
    t = {kk: v[j] for kk, v in c.items()}
    t.update({"inst": inst, "sig": sig, "e": e, "stop": stop, "dest": dest, "p": p, "A": A, "fr": fr, "rd": rd,
              "marge": c["marge"][j] / c["A"][j].clamp(min=1e-12) * A,
              "temoin": torch.ones(m, dtype=torch.bool, device=dev)})
    return t


def pres_d_une_zone(s: dict, seuil: float = PROCHE_AGITATION) -> torch.Tensor:
    """[n] : le prix est dans une de ses zones vivantes, ou à `seuil` agitation au plus de son bord (toutes unités)."""
    p, A = s["p"][:, 0], s["A"][:, 0]
    top, bot, ok = s["top"][:, 0], s["bot"][:, 0], s["ok"][:, 0]
    pp, AA = p[:, None, None, None], A[:, None, None, None]
    dist = torch.maximum(torch.maximum(bot - pp, pp - top), torch.zeros_like(top)) / AA
    return ((dist <= seuil) & ok).flatten(1).any(-1)


# ============================================================================================== 3. les exemples
def groupe(nom: str) -> str:
    src = D.source(nom)
    return "cryptos" if src == "binance" else ("minute" if src == "minute" else "45 marchés")


def periode_de(ns: np.ndarray) -> np.ndarray:
    """Code de période de chaque instant de décision (-1 = embargo : retiré)."""
    t = pd.DatetimeIndex(ns.astype("datetime64[ns]"))
    out = np.full(len(t), -1, np.int8)
    for nom, (de, a) in PERIODES.items():
        de = pd.Timestamp(de) if de else pd.Timestamp("1990-01-01")
        a = pd.Timestamp(a)
        fin = a - EMBARGO if nom in ("apprentissage", "reglage") else a
        out[(t >= de) & (t < fin)] = CODE_P[nom]
    return out


def foule_neutre_si_besoin(X: torch.Tensor) -> torch.Tensor:
    """Le juge lit toujours les 19 yeux de la foule (neutres si l'arbre ne les a pas)."""
    from collapsar.ecole.precision import foule as FO
    from collapsar.ecole.precision import vue as V
    if V.foule_active():
        return X
    neutre = torch.as_tensor(FO.NEUTRE, device=X.device).expand(*X.shape[:-1], FO.NF)
    return torch.cat([X, neutre], -1)


def exemples_marche(nom: str, graine: int, dire=print, lot: int = 8192) -> dict:
    """Instants, ce que voit l'IA à chacun (yeux de vue.py + foule), candidats (vrais et témoins), résultats."""
    from collapsar.ecole.precision.univers import Univers
    from collapsar.ecole.precision.vue import Vue
    t0 = time.time()
    x = S.lire(nom, False)
    debut = pd.Timestamp(int(np.asarray(x["t15"][0])))
    U = Univers([(nom, False)], debut + pd.Timedelta(days=45), R().periodes.fin_donnees, "cpu")
    vue = Vue(U)
    T = U.T
    ok = np.zeros(T, bool)
    ok[U.premier[0]:T - 2] = True
    ok[:-1] &= U.ouvert[1:, 0] & ~U.derniere[1:, 0]
    ok &= U.A[:, 0] > 0
    lignes = np.flatnonzero(ok)
    rng = np.random.default_rng(graine)
    gen = torch.Generator().manual_seed(graine)
    morceaux_i, morceaux_c = [], []
    n_inst = 0
    with torch.no_grad():
        for a in range(0, len(lignes), lot):
            tt = torch.as_tensor(lignes[a:a + lot])
            s = vue.structure(tt, torch.zeros(len(tt), 1, dtype=torch.long))
            pres = pres_d_une_zone(s)
            garde = torch.as_tensor(rng.random(len(tt)) < np.where(pres.numpy(), P_PROCHE, P_LOIN))
            if not garde.any():
                continue
            s = {k: v[garde] for k, v in s.items()}
            X = foule_neutre_si_besoin(vue.caracteristiques(s)[:, 0])
            o = options(s)
            c = tirer(o, N_REELS, gen)
            tm = temoins(c, o, N_TEMOINS, gen)
            cc = {k: torch.cat([c[k], tm[k]]) for k in c}
            morceaux_i.append({"t": s["t"].numpy().astype(np.int64), "pres": pres[garde].numpy(),
                               "X": X.numpy().astype(np.float16)})
            d = decrire(cc).numpy().astype(np.float16)
            morceaux_c.append({"inst": cc["inst"].numpy() + n_inst, "desc": d,
                               **{k: cc[k].numpy() for k in ("sig", "limite", "e", "stop", "dest", "dest_r",
                                                               "validite", "temoin")}})
            n_inst += int(garde.sum())
    I = {k: np.concatenate([m[k] for m in morceaux_i]) for k in morceaux_i[0]}
    Cc = {k: np.concatenate([m[k] for m in morceaux_c]) for k in morceaux_c[0]}
    t_c = I["t"][Cc["inst"]]
    cand = {"t": t_c, "sens": Cc["sig"], "limite": Cc["limite"], "P": Cc["e"].astype(np.float64),
            "stop": Cc["stop"].astype(np.float64), "dest": Cc["dest"].astype(np.float64), "dest_r": Cc["dest_r"],
            "validite": Cc["validite"]}
    res = resultats(chemin(U), cand)
    ns = U.t_ns[I["t"]] + int(pd.Timedelta(minutes=15).value)
    out = {"inst_t": I["t"].astype(np.int32), "inst_ns": ns.astype(np.int64), "inst_pres": I["pres"],
           "X": I["X"], "cand_inst": Cc["inst"].astype(np.int32), "desc": Cc["desc"],
           "sens": Cc["sig"].astype(np.int8), "limite": Cc["limite"], "temoin": Cc["temoin"],
           "dest_r": Cc["dest_r"].astype(np.int8), "validite": Cc["validite"].astype(np.int16), **res}
    dire(f"exemples de {nom} : {len(I['t'])} instants ({I['pres'].mean() * 100:.0f} % près d'une zone), "
         f"{len(Cc['inst'])} candidats ({Cc['temoin'].mean() * 100:.0f} % témoins), exécutés "
         f"{res['exe'].mean() * 100:.0f} %, 2R avant le stop {res['hit2'][res['exe']].mean() * 100:.1f} % "
         f"({time.time() - t0:.0f} s)")
    return out


def construire_exemples(marches: list[str] | None = None, dire=print, forcer: bool = False):
    """Les exemples de tous les marchés réels de l'arbre (un fichier par marché, reprise possible)."""
    from collapsar.ecole.precision import foule as FO
    FO.activer()                                       # le juge voit la foule (neutre hors cryptos)
    dos = DOSSIER / "exemples"
    dos.mkdir(parents=True, exist_ok=True)
    tous = list(D.univers())
    for i, nom in enumerate(marches or tous):
        f = dos / f"{nom.replace('@', '_')}.npz"
        if f.exists() and not forcer:
            continue
        try:
            out = exemples_marche(nom, 20261017 + tous.index(nom), dire)
        except Exception as ex:                        # un marché sans données ne doit pas tout arrêter
            dire(f"exemples de {nom} : IMPOSSIBLE ({type(ex).__name__}: {ex})")
            continue
        tmp = f.with_name(f.stem + "_tmp.npz")
        np.savez(tmp, **out)
        os.replace(tmp, f)


# ============================================================================================== assemblage (disque)
CHAMPS_C = ("desc", "sens", "limite", "temoin", "dest_r", "validite", "exe", "ne", "duree", "rA", "rB", "rC", "hit1",
            "hit2", "hit3", "codeA", "fin")


def assembler(dire=print) -> dict:
    """Tous les marchés en quelques grands tableaux sur le disque (lus en mémoire projetée pour apprendre)."""
    src = sorted((DOSSIER / "exemples").glob("*.npz"))
    dos = DOSSIER / "donnees"
    dos.mkdir(parents=True, exist_ok=True)
    tailles = []
    for f in src:
        with np.load(f) as z:
            tailles.append((len(z["inst_t"]), len(z["cand_inst"]), z["X"].shape[1]))
    NI, NC, F = sum(a for a, _, _ in tailles), sum(b for _, b, _ in tailles), tailles[0][2]
    mm = lambda nom, forme, dt: np.lib.format.open_memmap(dos / f"{nom}.npy", "w+", dt, forme)
    X = mm("X", (NI, F), np.float16)
    I = {"inst_ns": np.zeros(NI, np.int64), "inst_pres": np.zeros(NI, bool), "inst_marche": np.zeros(NI, np.int16)}
    Cd = {"cand_inst": np.zeros(NC, np.int64)}
    marches = []
    a = b = 0
    for im, f in enumerate(src):
        with np.load(f) as z:
            ni, nc = len(z["inst_t"]), len(z["cand_inst"])
            X[a:a + ni] = z["X"]
            I["inst_ns"][a:a + ni] = z["inst_ns"]
            I["inst_pres"][a:a + ni] = z["inst_pres"]
            I["inst_marche"][a:a + ni] = im
            Cd["cand_inst"][b:b + nc] = z["cand_inst"].astype(np.int64) + a
            for k in CHAMPS_C:
                v = z[k]
                if k not in Cd:
                    Cd[k] = np.zeros((NC,) + v.shape[1:], v.dtype)
                Cd[k][b:b + nc] = v
            nom = f.stem
            marches.append(nom)
            a += ni
            b += nc
    X.flush()
    del X
    for k, v in {**I, **Cd}.items():
        np.save(dos / f"{k}.npy", v)
    noms = {n.replace("_", "@") if n.endswith("_M1") else n: n for n in marches}
    info = {"instants": int(NI), "candidats": int(NC), "F": int(F), "ND": ND, "marches": list(noms),
            "groupes": [groupe(n) for n in noms], "version": VERSION,
            "date": datetime.now().isoformat(timespec="seconds")}
    (dos / "info.json").write_text(json.dumps(info, ensure_ascii=False, indent=1), encoding="utf-8")
    dire(f"assemblage : {NI} instants, {NC} candidats, {len(marches)} marchés")
    return info


class Donnees:
    """Les exemples assemblés (mémoire projetée pour X, le reste en mémoire)."""

    def __init__(self, dos: Path | None = None):
        dos = Path(dos or DOSSIER / "donnees")
        self.info = json.loads((dos / "info.json").read_text(encoding="utf-8"))
        self.X = np.load(dos / "X.npy", mmap_mode="r")
        for k in ("inst_ns", "inst_pres", "inst_marche", "cand_inst") + CHAMPS_C:
            setattr(self, k, np.load(dos / f"{k}.npy", mmap_mode="r" if k == "desc" else None))
        self.periode = periode_de(self.inst_ns)[self.cand_inst]
        self.marche = self.inst_marche[self.cand_inst]
        self.groupe = np.asarray(self.info["groupes"])[self.marche]
        self.ns = self.inst_ns[self.cand_inst]

    def lot(self, idx: np.ndarray, sans_foule: bool = False) -> tuple[torch.Tensor, torch.Tensor]:
        o = np.argsort(idx, kind="stable")
        ii = idx[o]
        x = np.empty((len(idx), self.X.shape[1]), np.float32)
        d = np.empty((len(idx), ND), np.float32)
        x[o] = self.X[self.cand_inst[ii]]
        d[o] = self.desc[ii]
        x = torch.from_numpy(x)
        if sans_foule:
            x = sans_la_foule(x)
        return x, torch.from_numpy(d)

    def cibles(self, idx: np.ndarray) -> dict:
        return {k: torch.from_numpy(np.asarray(getattr(self, k)[idx])) for k in ("exe", "hit1", "hit2", "hit3", "rA",
                                                                                  "rB", "rC")}


def sans_la_foule(x: torch.Tensor) -> torch.Tensor:
    """Les 19 yeux de la foule (en dernier) remplacés par « foule absente » (juge sans la foule)."""
    from collapsar.ecole.precision import foule as FO
    x = x.clone()
    x[..., -FO.NF:] = torch.as_tensor(FO.NEUTRE)
    return x


# ============================================================================================== 4. le juge
# Têtes : 4 probabilités (cote) et, pour chaque façon de jouer (C, A, B), le R moyen SI le trade a touché 2R et SINON.
# R attendu = P(2R) x R(si 2R) + (1 - P(2R)) x R(sinon) : les moyennes conditionnelles ne sont pas faussées par le poids
# des trades à 2R (il est constant dans chaque groupe) ; seule P(2R) l'est, et sa correction est exacte.
TETES = ("exe", "hit1", "hit2", "hit3", "rC2", "rCn", "rA2", "rAn", "rB2", "rBn")
I_ = {k: i for i, k in enumerate(TETES)}


def r_attendus(z: torch.Tensor) -> dict:
    """Depuis les sorties RECALIBRÉES : probabilités et R attendus (si exécuté) des 3 façons de jouer."""
    p = lambda k: torch.sigmoid(z[..., I_[k]])
    out = {k: p(k) for k in ("exe", "hit1", "hit2", "hit3")}
    p2 = out["hit2"]
    for v in ("C", "A", "B"):
        out["r" + v] = p2 * z[..., I_[f"r{v}2"]] + (1 - p2) * z[..., I_[f"r{v}n"]]
    return out


class Juge(nn.Module):
    """Le regard du trader sur un trade : ce qu'il voit du marché (une fois par instant) + la description du trade."""

    def __init__(self, F: int, nd: int = ND, oubli: float = 0.1):
        super().__init__()
        self.F, self.nd = F, nd
        self.inst = nn.Sequential(nn.Linear(F, 256), nn.LayerNorm(256), nn.GELU(), nn.Dropout(oubli),
                                  nn.Linear(256, 256), nn.GELU())
        self.cand = nn.Sequential(nn.Linear(nd, 64), nn.GELU())
        self.joint = nn.Sequential(nn.Linear(256 + 64, 192), nn.LayerNorm(192), nn.GELU(), nn.Dropout(oubli),
                                   nn.Linear(192, 128), nn.GELU(), nn.Linear(128, len(TETES)))
        # recalibration (réglée sur 2022) : a * brut + b par tête (cote des probabilités, R moyens)
        self.register_buffer("cal_a", torch.ones(len(TETES)))
        self.register_buffer("cal_b", torch.zeros(len(TETES)))
        self.register_buffer("poids_2r", torch.tensor(POIDS_2R))

    def brut(self, x, d):
        return self.joint(torch.cat([self.inst(x), self.cand(d)], -1))

    def forward(self, x, d):
        return self.brut(x, d)

    def avis(self, x, d) -> dict:
        """Avis HONNÊTE (recalibré) : P(exécuté), P(1R / 2R / 3R avant le stop | exécuté), R attendus si exécuté."""
        return r_attendus(self.brut(x, d) * self.cal_a + self.cal_b)


def poids_exemples(exe: torch.Tensor, hit2: torch.Tensor, w: float = POIDS_2R) -> torch.Tensor:
    return torch.where(exe & hit2, w, 1.0)


def corriger_cote(logit: torch.Tensor, w: float) -> torch.Tensor:
    """Correction EXACTE d'un apprentissage où les exemples positifs pèsent w fois plus : la cote apprise est w fois la
    vraie (p/(1-p) multipliée par w), donc on retire log(w) au logit."""
    return logit - math.log(w)


def perte(z: torch.Tensor, cib: dict, w: torch.Tensor) -> torch.Tensor:
    bce = torch.nn.functional.binary_cross_entropy_with_logits
    exe = cib["exe"].float()
    h2 = cib["hit2"].float()
    l = bce(z[:, I_["exe"]], exe, reduction="none")
    for k in ("hit1", "hit2", "hit3"):
        l = l + exe * bce(z[:, I_[k]], cib[k].float(), reduction="none")
    for v in ("C", "A", "B"):
        y = torch.nan_to_num(cib["r" + v].float(), nan=0.0).clamp(-3, 10)
        l = l + 0.25 * exe * h2 * (z[:, I_[f"r{v}2"]] - y) ** 2 + 0.25 * exe * (1 - h2) * (z[:, I_[f"r{v}n"]] - y) ** 2
    return (l * w).sum() / w.sum()


def _platt(z: np.ndarray, y: np.ndarray, iters: int = 200) -> tuple[float, float]:
    """a, b tels que sigmoid(a z + b) soit honnête (régression logistique à 1 variable)."""
    zt, yt = torch.as_tensor(z, dtype=torch.float64), torch.as_tensor(y, dtype=torch.float64)
    ab = torch.tensor([1.0, 0.0], dtype=torch.float64, requires_grad=True)
    opt = torch.optim.LBFGS([ab], max_iter=iters, line_search_fn="strong_wolfe")

    def f():
        opt.zero_grad()
        l = torch.nn.functional.binary_cross_entropy_with_logits(ab[0] * zt + ab[1], yt)
        l.backward()
        return l
    opt.step(f)
    return float(ab[0]), float(ab[1])


def _lineaire(z: np.ndarray, y: np.ndarray) -> tuple[float, float]:
    A = np.stack([z, np.ones_like(z)], 1)
    a, b = np.linalg.lstsq(A, y, rcond=None)[0]
    return float(a), float(b)


@torch.no_grad()
def predire_brut(net: Juge, D_: Donnees, idx: np.ndarray, sans_foule: bool, lot: int = 32768) -> np.ndarray:
    net.eval()
    out = np.empty((len(idx), len(TETES)), np.float32)
    for a in range(0, len(idx), lot):
        x, d = D_.lot(idx[a:a + lot], sans_foule)
        out[a:a + lot] = net.brut(x, d).numpy()
    return out


def recalibrer(net: Juge, z: np.ndarray, D_: Donnees, idx: np.ndarray):
    """Recalibration sur 2022 (jamais appris) : d'abord la correction exacte du poids des trades à 2R (sur la cote de
    P(2R)), puis un ajustement a z + b par tête (probabilités : régression logistique ; R : droite)."""
    a, b = np.ones(len(TETES)), np.zeros(len(TETES))
    w = float(net.poids_2r)
    exe = np.asarray(D_.exe[idx])
    h2 = np.asarray(D_.hit2[idx])
    for i, k in enumerate(TETES):
        zi = z[:, i].astype(np.float64)
        b0 = -math.log(w) if k == "hit2" else 0.0
        if k.startswith(("exe", "hit")):
            m = np.ones(len(idx), bool) if k == "exe" else exe
            y = np.asarray(getattr(D_, k)[idx])[m]
            a[i], b[i] = _platt(zi[m] + b0, y.astype(np.float64))
            b[i] += a[i] * b0
        else:
            m = exe & (h2 if k.endswith("2") else ~h2)
            y = np.asarray(getattr(D_, k[:2])[idx])[m].astype(np.float64)
            ok = np.isfinite(y)
            a[i], b[i] = _lineaire(zi[m][ok], np.clip(y[ok], -3, 10))
    net.cal_a.copy_(torch.as_tensor(a, dtype=torch.float32))
    net.cal_b.copy_(torch.as_tensor(b, dtype=torch.float32))


def entrainer(D_: Donnees, sans_foule: bool = False, epoques: int = 6, paquet: int = 4096, vitesse: float = 5e-4,
              max_apprentissage: int | None = None, dire=print, graine: int = 0) -> tuple[Juge, dict]:
    """Apprend le juge sur les instants < 2022 (vrais candidats ET témoins), s'arrête sur 2022, recalibre sur 2022."""
    torch.manual_seed(graine)
    rng = np.random.default_rng(graine)
    ok = ~np.asarray(D_.fin)
    app = np.flatnonzero(ok & (D_.periode == CODE_P["apprentissage"]))
    reg = np.flatnonzero(ok & (D_.periode == CODE_P["reglage"]))
    if max_apprentissage and len(app) > max_apprentissage:
        app = np.sort(rng.choice(app, max_apprentissage, replace=False))
    reg_v = np.sort(rng.choice(reg, min(len(reg), 600_000), replace=False))
    net = Juge(D_.X.shape[1])
    opt = torch.optim.AdamW(net.parameters(), lr=vitesse, weight_decay=1e-3)
    meilleur, etat, patience = float("inf"), None, 0
    hist = []
    pas_total = epoques * math.ceil(len(app) / paquet)
    sched = torch.optim.lr_scheduler.OneCycleLR(opt, max_lr=vitesse, total_steps=pas_total, pct_start=0.05)
    for ep in range(epoques):
        t0 = time.time()
        net.train()
        ordre = rng.permutation(app)
        tot, nb = 0.0, 0
        for a in range(0, len(ordre), paquet):
            i = ordre[a:a + paquet]
            x, d = D_.lot(i, sans_foule)
            cib = D_.cibles(i)
            w = poids_exemples(cib["exe"], cib["hit2"], float(net.poids_2r))
            l = perte(net(x, d), cib, w)
            opt.zero_grad(set_to_none=True)
            l.backward()
            torch.nn.utils.clip_grad_norm_(net.parameters(), 1.0)
            opt.step()
            sched.step()
            tot += float(l)
            nb += 1
        net.eval()
        with torch.no_grad():
            lv, nv = 0.0, 0
            for a in range(0, len(reg_v), 32768):
                i = reg_v[a:a + 32768]
                x, d = D_.lot(i, sans_foule)
                cib = D_.cibles(i)
                lv += float(perte(net(x, d), cib, poids_exemples(cib["exe"], cib["hit2"], float(net.poids_2r)))) * len(i)
                nv += len(i)
        lv /= max(nv, 1)
        hist.append({"epoque": ep + 1, "perte_apprentissage": tot / max(nb, 1), "perte_2022": lv,
                     "duree_s": time.time() - t0})
        dire(f"  juge{' sans la foule' if sans_foule else ''} : époque {ep + 1}, perte {tot / max(nb, 1):.4f} "
             f"(2022 : {lv:.4f}), {time.time() - t0:.0f} s")
        if lv < meilleur - 1e-4:
            meilleur, etat, patience = lv, {k: v.clone() for k, v in net.state_dict().items()}, 0
        else:
            patience += 1
            if patience >= 2:
                break
    net.load_state_dict(etat)
    z = predire_brut(net, D_, reg_v, sans_foule)
    recalibrer(net, z, D_, reg_v)
    return net, {"historique": hist, "exemples_apprentissage": int(len(app)), "exemples_2022": int(len(reg))}


def sauver_juge(net: Juge, f: Path, info: dict):
    f.parent.mkdir(parents=True, exist_ok=True)
    tmp = f.with_suffix(".tmp")
    torch.save({"etat": net.state_dict(), "F": net.F, "nd": net.nd, "noms_desc": NOMS_DESC, "version": VERSION,
                "info": info}, tmp)
    os.replace(tmp, f)


def charger_juge(f: Path | None = None, appareil="cpu") -> Juge:
    e = torch.load(Path(f or DOSSIER / "juge.pt"), map_location=appareil, weights_only=False)
    net = Juge(e["F"], e["nd"]).to(appareil)
    net.load_state_dict(e["etat"])
    net.eval()
    return net


def apprendre(dire=print, epoques: int = 6, max_apprentissage: int | None = None):
    torch.set_num_threads(max(1, min(4, os.cpu_count() or 1)))
    D_ = Donnees()
    for sf, nom in ((False, "juge.pt"), (True, "juge_sans_foule.pt")):
        t0 = time.time()
        net, info = entrainer(D_, sans_foule=sf, epoques=epoques, max_apprentissage=max_apprentissage, dire=dire)
        info["duree_s"] = time.time() - t0
        sauver_juge(net, DOSSIER / nom, info)
        dire(f"{nom} appris ({info['exemples_apprentissage']} exemples, {info['duree_s'] / 60:.0f} min)")


# ============================================================================================== 5. la mesure
def erreur_grappes(x: np.ndarray, grappes: np.ndarray) -> float:
    """Incertitude d'une moyenne quand les exemples d'une même grappe (même marché, même semaine) se ressemblent."""
    n = len(x)
    if n < 2:
        return float("nan")
    r = x - x.mean()
    _, inv = np.unique(grappes, return_inverse=True)
    s = np.bincount(inv, weights=r)
    return float(np.sqrt((s ** 2).sum()) / n)


def bloc_mesure(D_: Donnees, idx: np.ndarray, mois: float) -> dict:
    exe = np.asarray(D_.exe[idx])
    ie = idx[exe]
    if len(ie) == 0:
        return {"n": int(len(idx)), "executes_pct": 0.0, "n_exe": 0}
    grappe = D_.marche[ie].astype(np.int64) * 10_000 + (D_.ns[ie] // (7 * 86400 * 10 ** 9)) % 10_000
    rC, rA, rB = (np.asarray(getattr(D_, k)[ie], np.float64) for k in ("rC", "rA", "rB"))
    h2 = np.asarray(D_.hit2[ie])
    W = rC[h2].mean() if h2.any() else 2.0
    L = -rC[~h2].mean() if (~h2).any() else 1.0
    jours = np.unique(D_.marche[ie].astype(np.int64) * 100_000 + D_.ns[ie] // (86400 * 10 ** 9))
    return {"n": int(len(idx)), "n_exe": int(len(ie)), "executes_pct": float(exe.mean() * 100),
            "achats_pct": float((np.asarray(D_.sens[ie]) > 0).mean() * 100),
            "hit1_pct": float(np.asarray(D_.hit1[ie]).mean() * 100), "hit2_pct": float(h2.mean() * 100),
            "hit3_pct": float(np.asarray(D_.hit3[ie]).mean() * 100), "seuil_2r_pct": float(L / (W + L) * 100),
            "rC": float(rC.mean()), "rC_inc": erreur_grappes(rC, grappe), "rA": float(rA.mean()),
            "rA_inc": erreur_grappes(rA, grappe), "rB": float(rB.mean()), "rB_inc": erreur_grappes(rB, grappe),
            "jours_marches_mois": float(len(jours) / mois), "duree_h": float(np.asarray(D_.duree[ie]).mean() / 4)}


def mesurer(dire=print) -> dict:
    torch.set_num_threads(max(1, min(4, os.cpu_count() or 1)))
    D_ = Donnees()
    juges = {"juge": charger_juge(DOSSIER / "juge.pt"), "sans_foule": charger_juge(DOSSIER / "juge_sans_foule.pt")}
    ok = ~np.asarray(D_.fin)
    tem = np.asarray(D_.temoin)
    idx = {p: np.flatnonzero(ok & (D_.periode == CODE_P[p])) for p in ("reglage", "selection_2023", "controle_2024_25")}
    notes = {}                            # score = R attendu « tout à 2R » si exécuté (honnête, recalibré)
    calib = {}
    for nj, net in juges.items():
        for p, ii in idx.items():
            z = predire_brut(net, D_, ii, nj == "sans_foule")
            av = r_attendus(torch.as_tensor(z) * net.cal_a + net.cal_b)
            notes[(nj, p)] = av["rC"].numpy()
            if nj == "juge":
                calib[p] = {k: av[k].numpy() for k in ("exe", "hit2", "rC")}
    # seuils du classement fixés sur 2022 (jamais sur les périodes mesurées)
    seuils = {}
    for nj in juges:
        for qui, masque in (("reels", ~tem), ("temoins", tem)):
            sc = notes[(nj, "reglage")][masque[idx["reglage"]]]
            seuils[(nj, qui)] = {k: float(np.quantile(sc, 1 - k / 100)) for k in (10, 5, 1)}
    mois = {"selection_2023": 12.0, "controle_2024_25": 21.0}
    res = {"periodes": {}, "calibration": {}}
    groupes = ["tous", "cryptos", "minute", "45 marchés"]
    for p in ("selection_2023", "controle_2024_25"):
        ii = idx[p]
        g = D_.groupe[ii]
        rp = {}
        for gr in groupes:
            mg = np.ones(len(ii), bool) if gr == "tous" else g == gr
            rows = {}
            reel, temo = mg & ~tem[ii], mg & tem[ii]
            rows["tous les candidats"] = bloc_mesure(D_, ii[reel], mois[p])
            rows["témoins (fausses zones), tous"] = bloc_mesure(D_, ii[temo], mois[p])
            for k in (10, 5, 1):
                for nj, qui, masque, lib in (("juge", "reels", reel, f"juge : ses {k} % meilleurs"),
                                             ("juge", "temoins", temo, f"témoins : {k} % meilleurs pour le juge"),
                                             ("sans_foule", "reels", reel, f"juge sans la foule : ses {k} % meilleurs")):
                    haut = masque & (notes[(nj, p)] >= seuils[(nj, qui)][k])
                    b = bloc_mesure(D_, ii[haut], mois[p])
                    b["part_gardee_pct"] = float(haut.sum() / max(masque.sum(), 1) * 100)
                    rows[lib] = b
            rp[gr] = rows
        res["periodes"][p] = rp
        # calibration (vrais candidats) : prévu contre réel, par dixièmes
        cp = calib[p]
        reel = ~tem[ii]
        exe = np.asarray(D_.exe[ii])
        tab = {}
        for k, m_, y in (("exe", reel, exe), ("hit2", reel & exe, np.asarray(D_.hit2[ii])),
                         ("rC", reel & exe, np.asarray(D_.rC[ii]))):
            pr, yy = cp[k][m_], y[m_].astype(np.float64)
            qs = np.quantile(pr, np.linspace(0, 1, 11))
            b = np.clip(np.searchsorted(qs, pr, side="right") - 1, 0, 9)
            tab[k] = [{"prevu": float(pr[b == q].mean()), "reel": float(np.nanmean(yy[b == q])), "n": int((b == q).sum())}
                      for q in range(10) if (b == q).any()]
        res["calibration"][p] = tab
    res["seuils"] = {f"{a}|{b}": v for (a, b), v in seuils.items()}
    res["info"] = D_.info
    res["juges"] = {nj: torch.load(DOSSIER / f, map_location="cpu", weights_only=False)["info"]
                    for nj, f in (("juge", "juge.pt"), ("sans_foule", "juge_sans_foule.pt"))}
    # exemples par période et ce que dit le classement sur 2022 (réglage)
    res["comptes"] = {p: {"candidats": int((~tem[ii]).sum()), "temoins": int(tem[ii].sum())} for p, ii in idx.items()}
    app = np.flatnonzero(ok & (D_.periode == CODE_P["apprentissage"]))
    res["comptes"]["apprentissage"] = {"candidats": int((~tem[app]).sum()), "temoins": int(tem[app].sum())}
    (DOSSIER / "mesure.json").write_text(json.dumps(res, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
    ecrire_rapport(res)
    dire("rapport écrit : " + str(DOSSIER / "rapport.md"))
    return res


def _f(x, n=2, signe=True):
    if x is None or (isinstance(x, float) and not np.isfinite(x)):
        return "—"
    return f"{x:+.{n}f}" if signe else f"{x:.{n}f}"


def ecrire_rapport(res: dict):
    L = []
    info = res["info"]
    c = res["comptes"]
    L.append("# COLLAPSAR — arbre HYPERNOVA : l'école « JUGER UN TRADE » (rapport du "
             f"{datetime.now():%d/%m/%Y %H:%M})\n")
    L.append("Le juge apprend à estimer ce que vaut un trade AVANT de le prendre : P(exécuté), P(1R / 2R / 3R avant le "
             "stop), R attendu. Trades candidats posés comme les mains de l'arbre (entrée au marché ou ordre limite sur "
             "ses zones, stop derrière une zone ou un creux / sommet, destination zone opposée / sommet / 2R / 3R), "
             "joués sur le vrai chemin du prix avec les règles et frais FTMO du simulateur de l'arbre.\n")
    nb = lambda x: f"{int(x):,}".replace(",", " ")
    L.append(f"- Exemples : {nb(info['instants'])} instants, {nb(info['candidats'])} candidats sur {len(info['marches'])} "
             "marchés réels (un sur quatre est un TÉMOIN posé sur de fausses zones).")
    L.append(f"- Apprentissage : instants < 2022 ({nb(c['apprentissage']['candidats'])} vrais + "
             f"{nb(c['apprentissage']['temoins'])} témoins) ; réglages (arrêt, recalibration, seuils du classement) : "
             "2022 ; mesures : 2023 et 01/2024 -> 09/2025, jamais utilisées. Rien après 09/2025.")
    L.append(f"- Trades à 2R mis en avant : poids {POIDS_2R:.0f} à l'apprentissage ; probabilités recalibrées sur 2022.")
    L.append("- R : résultat d'un trade en multiples de son risque, frais FTMO, glissement du stop et nuits compris. "
             "C = tout à 2R ; A = tout à sa destination ; B = 80 % à 2R puis stop à l'entrée, le reste à sa destination.")
    L.append("- « Seuil » = % de trades à 2R qu'il faut pour ne pas perdre, frais compris (mesuré sur le groupe). "
             "Force = R moyen / incertitude (grappes marché x semaine) ; au-delà de 2 : probablement réel. Le haut du "
             "classement est fixé par des seuils réglés sur 2022 (entre parenthèses : la part réellement gardée).\n")
    f_concl = DOSSIER / "conclusion.md"
    if f_concl.exists():
        L.append(f_concl.read_text(encoding="utf-8").strip() + "\n")
    noms_p = {"selection_2023": "2023 (sélection de l'arbre)", "controle_2024_25": "01/2024 -> 09/2025 (contrôle, jamais utilisé)"}
    for p, rp in res["periodes"].items():
        L.append(f"## {noms_p[p]}\n")
        for gr, rows in rp.items():
            L.append(f"### {gr}\n")
            L.append("| qui | candidats | exécutés | achats | 2R avant stop (seuil) | 1R / 3R | R moyen C (± incertitude) | "
                     "force C | R moyen A (± incertitude) | R moyen B | jours-marchés / mois | durée moy. |")
            L.append("|---|---|---|---|---|---|---|---|---|---|---|---|")
            for lib, b in rows.items():
                if b.get("n_exe", 0) == 0:
                    L.append(f"| {lib} | {b['n']} | 0 | — | — | — | — | — | — | — | — | — |")
                    continue
                force = b["rC"] / b["rC_inc"] if b["rC_inc"] and b["rC_inc"] > 0 else float("nan")
                part = f" ({b['part_gardee_pct']:.1f} %)" if "part_gardee_pct" in b else ""
                L.append(f"| {lib} | {b['n']}{part} | {b['executes_pct']:.0f} % | {b.get('achats_pct', float('nan')):.0f} % | "
                         f"{b['hit2_pct']:.1f} % ({b['seuil_2r_pct']:.1f} %) | {b['hit1_pct']:.0f} % / {b['hit3_pct']:.0f} % | "
                         f"{_f(b['rC'], 3)} ± {_f(b['rC_inc'], 3, False)} | {_f(force, 1)} | {_f(b['rA'], 3)} ± "
                         f"{_f(b['rA_inc'], 3, False)} | {_f(b['rB'], 3)} | {b['jours_marches_mois']:.0f} | {b['duree_h']:.0f} h |")
            L.append("")
        L.append("### Calibration (vrais candidats) : prévu contre réel, par dixièmes de l'avis du juge\n")
        cal = res["calibration"][p]
        L.append("| dixième | P(exécuté) prévu / réel | P(2R avant stop) prévu / réel | R « tout à 2R » prévu / réel |")
        L.append("|---|---|---|---|")
        for q in range(10):
            g = lambda k: cal[k][q] if q < len(cal[k]) else None
            a, b_, r = g("exe"), g("hit2"), g("rC")
            cell = lambda x, pct: "—" if x is None else (f"{x['prevu'] * 100:.0f} % / {x['reel'] * 100:.0f} %" if pct
                                                         else f"{x['prevu']:+.3f} / {x['reel']:+.3f}")
            L.append(f"| {q + 1} | {cell(a, True)} | {cell(b_, True)} | {cell(r, False)} |")
        L.append("")
    (DOSSIER / "rapport.md").write_text("\n".join(L), encoding="utf-8")


# ============================================================================================== 6. la greffe (prête)
_JUGE = {}


def active() -> bool:
    return bool(getattr(R().yeux, "juge", False))


def activer(oui: bool = True):
    R().yeux.juge = bool(oui)


def greffee(dossier: Path) -> bool:
    return (Path(dossier) / "juge.json").exists()


def juge_pour(dev, fichier: Path | None = None) -> Juge:
    cle = (str(dev), str(fichier))
    if cle not in _JUGE:
        _JUGE[cle] = charger_juge(fichier, dev)
    return _JUGE[cle]


def fichier_juge_greffe() -> Path | None:
    f = os.environ.get("COLLAPSAR_JUGE")
    return Path(f) if f else None


@torch.no_grad()
def notes_grille(s: dict, X: torch.Tensor, juge: Juge) -> torch.Tensor:
    """[n, J, NJ] : l'avis du juge sur une GRILLE fixe de trades à 2R pour chaque marché d'un regard, de chaque côté :
    au marché (stop derrière la zone ou le creux / sommet le plus proche à au moins 0,25 agitation) et un ordre limite
    sur le bord proche de la zone la plus proche de chaque unité (stop derrière son bord lointain) ; marge 0,1
    agitation, validité 1 jour. Par côté : meilleur R attendu (si exécuté), sa P(exécuté), sa P(2R avant stop), R moyen
    de la grille. Un côté sans trade possible : 0."""
    nv = C.niveaux(s)
    n, J = s["p"].shape[:2]
    dev = s["p"].device
    K = s["top"].shape[-1]
    nz = 7 * K
    p, A, demi = s["p"], s["A"], s["demi"]
    fr = 2 * demi * p
    sgn = torch.tensor([1.0, -1.0], device=dev)[None, None, :, None]
    p4, f4, A4 = p[..., None, None], fr[..., None, None], A[..., None, None]
    e_niv, s_niv = nv["entree"], nv["stop"]
    st_ok = nv["stop_ok"]
    derriere = st_ok[:, :, :, None, :] & (sgn[..., None] * (e_niv[..., None] - s_niv[:, :, :, None, :]) > f4[..., None])
    e_ok = nv["entree_ok"] & (sgn * (p4 - e_niv) > f4) & ((p4 - e_niv).abs() <= R().mains.entree_max_agitation * A4) & \
        derriere.any(-1)
    marge = 0.1 * A4
    # ordres limites : bord proche de la zone de rang 0 de chaque unité ; stop = son bord lointain + marge
    iz = torch.arange(7, device=dev) * K                                        # places « proche », rang 0
    eL = e_niv[..., iz]                                                         # [n,J,2,7]
    sL = s_niv[..., iz] - sgn * marge
    okL = e_ok[..., iz] & st_ok[..., iz] & (sgn * (eL - sL) > f4)
    # au marché : le stop valable le plus proche à au moins 0,25 agitation derrière le prix
    dist = sgn * (p4 - s_niv)
    okm = st_ok & (dist > torch.maximum(f4, 0.25 * A4))
    im = torch.where(okm, dist, torch.full_like(dist, float("inf"))).argmin(-1)
    sM = s_niv.gather(-1, im[..., None]).squeeze(-1) - sgn[..., 0] * marge[..., 0]
    okM = okm.any(-1)
    G = 8
    e = torch.cat([p[..., None, None].expand(n, J, 2, 1), eL], -1)            # [n,J,2,8]
    st = torch.cat([sM[..., None], sL], -1)
    ok = torch.cat([okM[..., None], okL], -1)
    lim = torch.cat([torch.zeros(n, J, 2, 1, dtype=torch.bool, device=dev), torch.ones(n, J, 2, 7, dtype=torch.bool, device=dev)], -1)
    sig = sgn.expand(n, J, 2, G)
    rd = (sig * (e - st)).clamp(min=1e-12)
    ims = torch.where(im < nz, im, im)                                          # place du stop au marché
    i_stop = torch.cat([ims[..., None], iz.expand(n, J, 2, 7)], -1)
    att_e = torch.cat([torch.zeros(n, J, 2, 1, 5, device=dev), nv["entree_att"][..., iz, :]], 3)
    att_s = nv["stop_att"].gather(3, i_stop[..., None].expand(-1, -1, -1, -1, 5))
    unite_e = torch.cat([torch.full((n, J, 2, 1), -1, device=dev, dtype=torch.long),
                         torch.arange(7, device=dev).expand(n, J, 2, 7)], -1)
    unite_s = torch.where(i_stop < nz, i_stop // K, (i_stop - nz) // 2)
    flat = lambda x: x.reshape(n * J * 2 * G, *x.shape[4:])
    rep = lambda x: x[:, :, None, None].expand(n, J, 2, G)
    c = {"sig": flat(sig), "limite": flat(lim), "e": flat(e), "p": flat(rep(p)), "A": flat(rep(A)),
         "fr": flat(rep(fr)), "rd": flat(rd), "marge": flat(rep(0.1 * A)), "dest": flat(e + sig * 2 * rd),
         "validite": torch.full((n * J * 2 * G,), 96, device=dev), "temoin": torch.zeros(n * J * 2 * G, dtype=torch.bool, device=dev),
         "e_type": flat(lim.long()), "e_unite": flat(unite_e), "e_att": flat(att_e),
         "st_type": flat((i_stop >= nz).long()), "st_unite": flat(unite_s), "st_att": flat(att_s),
         "d_type": torch.full((n * J * 2 * G,), 2, device=dev, dtype=torch.long),
         "d_unite": torch.full((n * J * 2 * G,), -1, device=dev, dtype=torch.long),
         "d_att": torch.zeros(n * J * 2 * G, 5, device=dev)}
    d = decrire(c)
    # 1re couche commune découpée (exactement la même opération) : le regard sur le marché une fois par marché
    lin = juge.joint[0]
    nh = lin.weight.shape[1] - juge.cand[0].out_features
    a_h = juge.inst(X.reshape(n * J, -1)) @ lin.weight[:, :nh].T
    a_c = juge.cand(d) @ lin.weight[:, nh:].T + lin.bias
    z1 = (a_c.reshape(n * J, 2 * G, -1) + a_h[:, None]).reshape(n * J * 2 * G, -1)
    av = r_attendus(juge.joint[1:](z1) * juge.cal_a + juge.cal_b)
    pe = av["exe"].reshape(n, J, 2, G)
    p2 = av["hit2"].reshape(n, J, 2, G)
    er = av["rC"].reshape(n, J, 2, G)
    erm = torch.where(ok, er, torch.full_like(er, -1e9))
    ib = erm.argmax(-1, keepdim=True)
    a_un = ok.any(-1)
    best = er.gather(-1, ib).squeeze(-1)
    moy = (er * ok).sum(-1) / ok.sum(-1).clamp(min=1)
    out = torch.stack([best, pe.gather(-1, ib).squeeze(-1), p2.gather(-1, ib).squeeze(-1), moy], -1) * a_un[..., None]
    return torch.nan_to_num(out.reshape(n, J, 2 * 4), nan=0.0).clamp(-10, 10)


@torch.no_grad()
def tenseur_notes(U, lot: int | None = None) -> torch.Tensor:
    """[T, M, NJ] : les notes du juge pour chaque instant et chaque marché d'un monde (calculées une fois à sa
    construction, comme les yeux de la foule)."""
    from collapsar.ecole.precision.vue import Vue
    juge = juge_pour(U.dev, fichier_juge_greffe())
    vue = Vue(U)
    T, M = U.T, U.M
    lot = lot or max(16, 8192 // max(M, 1))
    out = torch.zeros(T, M, NJ, device=U.dev)
    cols = torch.arange(M, device=U.dev)
    from collapsar.ecole.precision import monde as MO
    ancien, ancien_monde = active(), MO.active()
    activer(False)                                   # les yeux SANS les notes du juge (ce que le juge a appris à lire)
    MO.activer(False)                                # ni les yeux du monde (venus après le juge)
    try:
        for a in range(0, T, lot):
            t = torch.arange(a, min(a + lot, T), device=U.dev)
            cc = cols[None].expand(len(t), M)
            s = vue.structure(t, cc)
            X = foule_neutre_si_besoin(vue.caracteristiques(s))
            out[a:a + len(t)] = notes_grille(s, X, juge)
    finally:
        activer(ancien)
        MO.activer(ancien_monde)
    return out


def _grandir(w: torch.Tensor, ou: int) -> torch.Tensor:
    z = torch.zeros(*w.shape[:-1], NJ, dtype=w.dtype, device=w.device)
    return torch.cat([w[..., :ou], z, w[..., ou:]], -1)


def _entree_avant_apres() -> tuple[int, int, int]:
    from collapsar.ecole.precision import monde as MO
    from collapsar.ecole.precision import vue as V
    ancien = active()
    activer(False)
    try:
        avant = V.taille_caracteristiques()
    finally:
        activer(ancien)
    if MO.active():                                  # yeux du monde déjà greffés : le juge s'insère AVANT eux
        avant -= MO.NM
        return avant, avant + MO.NM + C.N_POS, avant + NJ + MO.NM + C.N_POS
    return avant, avant + C.N_POS, avant + NJ + C.N_POS


def greffer_etat(etat: dict) -> tuple[dict, bool]:
    """NJ colonnes à ZÉRO insérées dans la 1re couche des yeux du marché, juste avant la position (ordre des entrées :
    yeux, foule, notes du juge, position) ; mémoire de l'optimiseur agrandie de même."""
    ou, f_avant, f_apres = _entree_avant_apres()
    cle = "marche.0.weight"
    w = etat["cerveau"][cle]
    if w.shape[1] == f_apres:
        return etat, False
    if w.shape[1] != f_avant:
        raise ValueError(f"entrée du cerveau inattendue : {w.shape[1]} (attendu {f_avant} ou {f_apres})")
    etat = dict(etat)
    etat["cerveau"] = dict(etat["cerveau"])
    etat["cerveau"][cle] = _grandir(w, ou)
    opt = etat.get("opt")
    if opt:
        noms = [n for n, _ in C.Cerveau().named_parameters()]
        k = noms.index(cle)
        pid = opt["param_groups"][0]["params"][k]
        st = opt["state"].get(pid)
        if st:
            st = dict(st)
            for cc in ("exp_avg", "exp_avg_sq"):
                if cc in st and st[cc].shape == w.shape:
                    st[cc] = _grandir(st[cc], ou)
            etat["opt"] = {**opt, "state": {**opt["state"], pid: st}}
    return etat, True


def greffer(dossier: Path, dire=print) -> dict:
    """LA GREFFE sur un arbre ARRÊTÉ : sauvegarde, chaque branche (et sa meilleure version, la cime) reçoit les notes du
    juge avec des poids à zéro ; le juge est copié dans le dossier ; juge.json écrit (le cœur s'allume seul en mode
    juge au prochain démarrage)."""
    import psutil
    from collapsar.ecole.precision import foule as FO
    dossier = Path(dossier).resolve()
    if greffee(dossier):
        raise SystemExit(f"{dossier} : déjà greffé (juge.json existe)")
    v = dossier / "coeur.verrou"
    if v.exists():
        try:
            pid = int(v.read_text())
            if psutil.pid_exists(pid) and "python" in psutil.Process(pid).name().lower():
                raise SystemExit(f"le cœur bat encore (processus {pid}) : créer {dossier / 'ARRET'} et attendre sa fin")
        except ValueError:
            pass
    if FO.greffee(dossier):
        FO.activer()
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    sauve = dossier / "sauvegardes" / f"avant_juge_{stamp}"
    sauve.mkdir(parents=True)
    for nom in ("arbre.json", "cime.pt", "derniers_examens.json", "journal_croissance.jsonl"):
        if (dossier / nom).exists():
            shutil.copy2(dossier / nom, sauve / nom)
    shutil.copytree(dossier / "branches", sauve / "branches")
    dire(f"sauvegarde de l'arbre : {sauve}")
    shutil.copy2(DOSSIER / "juge.pt", dossier / "juge_trade.pt")
    fichiers = sorted((dossier / "branches").glob("*.pt")) + ([dossier / "cime.pt"] if (dossier / "cime.pt").exists() else [])
    faits = []
    for f in fichiers:
        e = torch.load(f, map_location="cpu", weights_only=False)
        e2, change = greffer_etat(e)
        if change:
            tmp = f.with_suffix(".pt.tmp")
            torch.save(e2, tmp)
            os.replace(tmp, f)
            faits.append(f.name)
    ou, f_avant, f_apres = _entree_avant_apres()
    info = {"date": datetime.now().isoformat(timespec="seconds"), "version": VERSION, "notes": NJ,
            "entree_avant": f_avant, "entree_apres": f_apres, "insertion": ou, "fichiers": faits,
            "juge": str(dossier / "juge_trade.pt"), "sauvegarde": str(sauve)}
    (dossier / "juge.json").write_text(json.dumps(info, ensure_ascii=False, indent=1), encoding="utf-8")
    try:
        from collapsar.arbre.journal import Journal
        Journal(dossier / "journal_croissance.jsonl").ecrire("greffe_juge", fichiers=faits, sauvegarde=str(sauve))
    except Exception:
        pass
    dire(f"greffe faite : {len(faits)} fichiers (entrée {f_avant} -> {f_apres}) ; juge.json écrit")
    return info


def defaire(dossier: Path, dire=print):
    """Retour arrière : remet la sauvegarde d'avant la greffe du juge (arbre arrêté)."""
    dossier = Path(dossier)
    info = json.loads((dossier / "juge.json").read_text(encoding="utf-8"))
    sauve = Path(info["sauvegarde"])
    shutil.rmtree(dossier / "branches")
    shutil.copytree(sauve / "branches", dossier / "branches")
    for nom in ("arbre.json", "cime.pt", "derniers_examens.json", "journal_croissance.jsonl"):
        if (sauve / nom).exists():
            shutil.copy2(sauve / nom, dossier / nom)
    (dossier / "juge.json").unlink()
    dire(f"greffe du juge défaite : état remis depuis {sauve}")


def allumer_si_greffe(dossier: Path) -> bool:
    """Appelé par le cœur au démarrage : un arbre greffé (juge.json) allume les notes du juge avec SON juge."""
    if not greffee(dossier):
        return False
    info = json.loads((Path(dossier) / "juge.json").read_text(encoding="utf-8"))
    os.environ["COLLAPSAR_JUGE"] = info["juge"]
    activer()
    return True


# ============================================================================================== commandes
def dire_(texte):
    print(f"[{datetime.now():%d/%m %H:%M:%S}] {texte}", flush=True)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("quoi", choices=["exemples", "assembler", "apprendre", "mesurer", "tout", "greffer", "defaire"])
    ap.add_argument("--marches", default=None, help="liste séparée par des virgules (exemples)")
    ap.add_argument("--dossier", default=None)
    ap.add_argument("--epoques", type=int, default=6)
    ap.add_argument("--max", type=int, default=None, help="nombre maximum d'exemples d'apprentissage")
    a = ap.parse_args(argv)
    if a.quoi in ("exemples", "tout"):
        torch.set_num_threads(max(1, min(4, os.cpu_count() or 1)))
        construire_exemples(a.marches.split(",") if a.marches else None, dire_)
    if a.quoi in ("assembler", "tout"):
        assembler(dire_)
    if a.quoi in ("apprendre", "tout"):
        from collapsar.ecole.precision import foule as FO
        FO.activer()
        apprendre(dire_, a.epoques, a.max)
    if a.quoi in ("mesurer", "tout"):
        from collapsar.ecole.precision import foule as FO
        FO.activer()
        mesurer(dire_)
    if a.quoi == "greffer":
        greffer(Path(a.dossier), dire_)
    if a.quoi == "defaire":
        defaire(Path(a.dossier), dire_)


if __name__ == "__main__":
    main()
