"""LE CERVEAU SYMÉTRIQUE de MAGNETAR (19/10/2026 soir, accord explicite du chef de projet), sur UNE branche.

LE CONSTAT : malgré l'apprentissage apparié (or réel + or retourné aux mêmes dates) et la note « côté le moins bon »,
toutes les branches achètent 91-96 % du temps, même sur l'or retourné ; leurs ventes perdent ; elles n'explorent presque
plus la vente. Leur cerveau a deux sorties séparées « acheter » et « vendre » : l'une a pris l'habitude de gagner.

L'IDÉE : l'achat et la vente sont jugés par les MÊMES neurones.
1. LA VUE MIROIR (`miroir_vue`) : ce que serait sa vue si le graphique était retourné autour du prix actuel :
   zones de demande <-> zones d'offre, sommets <-> creux (et leurs distances), tendance des sommets / creux et clôtures
   brutes de signe inversé, sa position et son ordre inversés (sens), son journal achat <-> vente (catégories et trades
   ressemblants des deux côtés échangés), yeux de la foule retournés (comme foule.SENS), tendance de fond inversée
   (comme tendance.retourner). Le compte (solde, murs, nombre de positions...) ne change pas. Tout le reste (agitation,
   frais, heure, séances, pauses) non plus. C'est un simple rangement + changements de signe : appliqué deux fois, il
   rend exactement la vue de départ (testé). `miroir_structure` fait la même chose sur les prix eux-mêmes (réflexion
   autour du prix : niveau x -> 2 p - x) : ses yeux calculés sur ces prix retournés = la vue miroir (testé).
2. LE CERVEAU (cerveau.politique, `net.symetrique`) : le même corps lit la vue x et la vue miroir(x). La tête « acheter »
   de x donne le score de MONTÉE s(x) ; la même tête lue sur miroir(x) donne le score de vente s(miroir(x)). Le score
   « rien » (et « fermer ») est la moyenne des deux lectures : il ne peut pas pencher d'un côté. Geste = tirage sur
   [rien, acheter au marché, vendre au marché, acheter par ordre limite, vendre par ordre limite, fermer] avec ces
   scores. Les paramètres d'un trade (entrée, stop, marge, destination, objectif 1, part, risque, validité, suiveur)
   sont tirés par les mêmes têtes, depuis la vue du côté choisi : x pour un achat, miroir(x) pour une vente. Les niveaux
   proposés sont déjà décrits « dans le sens du trade » (cerveau._dyn) : niveau d'achat de miroir(x) = niveau de vente
   de x, retraduit en prix de vente tout seul. Délai de regard et valeur attendue : moyenne des deux lectures.
   Résultat : aucune préférence d'achat possible par construction (testé : P(achat | x) = P(vente | miroir(x)) ; sur un
   monde où chaque situation a son miroir, achats et ventes ont la même probabilité totale).
3. DÉPART : la branche naît de la CIME (mêmes poids : sa partie « achat » est exactement celle de la cime, sa partie
   « vente » = les mêmes poids sur la vue miroir ; les anciennes sorties « vendre » de la cime ne servent plus).

LIMITE CONNUE (mesurée, pas cachée) : l'or retourné du projet est k / prix (donnees.retourner), pas une réflexion
exacte : sa vue n'est la vue miroir de l'or réel qu'à peu près (agitation et distances relatives au prix légèrement
différentes) : voir `mesurer_reel_retourne` et le rapport de greffe.

Greffe (arbre ARRÊTÉ, ARRET en place) depuis Test_IA :
  $env:COLLAPSAR_PRECISION_REGLAGES="...\\collapsar\\ecole\\precision\\reglages_or.yaml"
  venv_gpu\\Scripts\\python.exe -m collapsar.ecole.precision.symetrie appliquer [--dossier D] [--code-avant C]
Retour arrière : `... symetrie defaire` (vie d'avant la greffe) ou `... symetrie retirer` (la branche seule est archivée,
l'arbre continue). Sans le mot « symetrique » dans le tempérament d'une branche, ce code ne change rien (empreintes).
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import torch

from collapsar.ecole.precision.reglages import R, UNITES, UNITES_BRUTES, VIE

VERSION = 1
FICHIER = "symetrique.json"
GESTE_MIROIR = (0, 2, 1, 4, 3, 5)              # rien, achat <-> vente (marché, limite), fermer
_PLANS: dict = {}


# ============================================================================================== la vue miroir
def plan_vue(F: int, n_journal: int, n_tendance: int) -> tuple[np.ndarray, np.ndarray]:
    """(rang, signe) [F] : vue_miroir[i] = vue[rang[i]] * signe[i]. Ordre des entrées du cerveau : yeux du marché
    (vue.caracteristiques : zones, sommets / creux, clôtures brutes, unités connues, divers, heure, [foule]), position
    (jeu.entrees_np, 11), [journal : onglet Trade (12) + Historique (147)], [tendance de fond (12)]."""
    from collapsar.ecole.precision import cerveau as C
    from collapsar.ecole.precision import vue as V
    yeux = R().yeux
    K, nb, NU = yeux.zones_par_cote, yeux.bougies_brutes, len(UNITES)
    if V.juge_active() or V.monde_active():
        raise NotImplementedError("vue miroir : notes du juge / yeux du monde non prévus (éteints sur MAGNETAR)")
    rang, signe = [], []

    def bloc(r, s=None):
        o = len(rang)
        rang.extend(o + int(x) for x in r)
        signe.extend([1.0] * len(r) if s is None else list(map(float, s)))
    # zones [U, 2 côtés, K, 8] : côté demande <-> côté offre (les distances sont déjà « dans le sens du côté »)
    bloc([((u * 2 + (1 - c)) * K + k) * 8 + f for u in range(NU) for c in range(2) for k in range(K) for f in range(8)])
    # sommets / creux [U, 9] : (s1, s2, c1, c2) distances, (s1, s2, c1, c2) connus, tendance des sommets / creux
    perm9 = (2, 3, 0, 1, 6, 7, 4, 5, 8)
    bloc([u * 9 + perm9[f] for u in range(NU) for f in range(9)], [-1.0 if f == 8 else 1.0 for _ in range(NU) for f in range(9)])
    nbrut = len(UNITES_BRUTES) * nb                     # clôtures brutes (clôture - prix) / agitation : signe inversé
    bloc(range(nbrut), [-1.0] * nbrut)
    bloc(range(NU + 4 + 7))                             # unités connues, agitation / frais / pause / ouvert, heure
    if V.foule_active():                                # yeux de la foule (foule.py) : retournés comme le marché retourné
        from collapsar.ecole.precision import foule as FO
        bloc(range(FO.NF), np.where(FO.SENS, -1.0, 1.0))
    if len(rang) != V.taille_caracteristiques():
        raise AssertionError(f"vue miroir : {len(rang)} yeux rangés contre {V.taille_caracteristiques()}")
    pos = np.ones(C.N_POS)
    pos[[0, 2]] = -1.0                                  # sens de la position, sens de l'ordre en attente
    bloc(range(C.N_POS), pos)
    if n_journal:
        from collapsar.ecole.precision import journal_trading as JN
        assert n_journal == JN.NJ, n_journal
        bloc(range(JN.NT))                              # onglet Trade : tout est déjà « dans le sens du trade »
        compte = list(range(17))
        compte[7:11], compte[11:15] = list(range(11, 15)), list(range(7, 11))   # achat <-> vente (rebond, cassure)
        cote = (JN.NH - 17) // 2
        bloc(compte + [17 + cote + i for i in range(cote)] + [17 + i for i in range(cote)])   # ressemblants achat <-> vente
    if n_tendance:
        from collapsar.ecole.precision import tendance as TD
        assert n_tendance == TD.NTD, n_tendance
        bloc(range(TD.NTD), [-1.0] * TD.NTD)            # tendance de fond : tout s'inverse (tendance.retourner)
    if len(rang) != F:
        raise AssertionError(f"vue miroir : {len(rang)} entrées rangées contre {F} pour ce cerveau")
    return np.asarray(rang, np.int64), np.asarray(signe, np.float32)


def _plan(net, dev):
    from collapsar.ecole.precision import vue as V
    cle = (net.F, net.n_journal, net.n_tendance, V.foule_active(), str(dev))
    if cle not in _PLANS:
        r, s = plan_vue(net.F, net.n_journal, net.n_tendance)
        _PLANS[cle] = (torch.as_tensor(r, device=dev), torch.as_tensor(s, device=dev))
    return _PLANS[cle]


def miroir_vue(fm: torch.Tensor, net) -> torch.Tensor:
    """[n, J, F] -> la même vue, graphique retourné (rangement + signes, involution exacte)."""
    rang, signe = _plan(net, fm.device)
    return fm.index_select(-1, rang) * signe


def miroir_structure(s: dict) -> dict:
    """La structure (vue.Vue.structure) du graphique RÉFLÉCHI autour du prix actuel p (niveau x -> 2 p - x) : zones de
    demande <-> d'offre, sommets <-> creux, clôtures brutes inversées ; agitation, frais, heure inchangés."""
    p = s["p"]
    P5 = p[:, :, None, None, None]
    out = dict(s)
    out["top"] = 2 * P5 - s["bot"].flip(3)
    out["bot"] = 2 * P5 - s["top"].flip(3)
    for k in ("ok", "tou", "rea", "age", "dans"):
        out[k] = s[k].flip(3)
    out["sw"] = 2 * p[:, :, None, None] - s["sw"][..., [2, 3, 0, 1]]
    out["brut"] = -s["brut"]
    return out


def miroir_choix(choix: dict) -> dict:
    """Les mêmes choix vus dans le graphique retourné : achat <-> vente ; les niveaux (rangés par côté) et le reste
    gardent leur numéro."""
    g = torch.as_tensor(GESTE_MIROIR, device=choix["geste"].device)
    return {**choix, "geste": g[choix["geste"]]}


def logits_geste(t_x: torch.Tensor, t_m: torch.Tensor) -> torch.Tensor:
    """Scores des 6 gestes du cerveau symétrique à partir des têtes lues sur x et sur miroir(x) : rien et fermer = moyenne
    des deux lectures ; acheter = tête « acheter » sur x ; vendre = la MÊME tête sur miroir(x)."""
    from collapsar.ecole.precision import cerveau as C
    moy = lambda i: 0.5 * (t_x[..., i] + t_m[..., i])
    return torch.stack([moy(C.GARDER), t_x[..., C.ACHAT_M], t_m[..., C.ACHAT_M], t_x[..., C.ACHAT_L], t_m[..., C.ACHAT_L],
                        moy(C.FERMER)], -1)


def est_symetrique(temperament) -> bool:
    return isinstance(temperament, dict) and bool(temperament.get("symetrique"))


# ============================================================================================== preuves et mesures
def _monter(net, U, B: int, bougies: int, graine: int, cols: np.ndarray | None = None, departs=None):
    """Une table jouée `bougies` bougies (positions, ordres, journal qui se remplissent) ; rend la table."""
    from collapsar.ecole.precision import jeu as JEU
    from collapsar.ecole.precision import journal_trading as JN
    tb = JEU.Table(U, B, 1)
    JN.equiper(tb, net, "ecole")
    rng = np.random.default_rng(graine)
    if cols is None:
        ok = np.flatnonzero(U.premier < U.T - bougies - 200)
        cols = rng.choice(ok, B)[:, None]
    if departs is None:
        departs = np.asarray([rng.integers(U.premier[c], U.T - bougies - 100) for c in cols[:, 0]])
    tb.demarrer(np.ones(B, bool), cols, departs)
    dec = JEU.Decideur(tb, net, evaluer=False, graphe=False)
    torch.manual_seed(graine)
    c = tb.cpt
    for _ in range(bougies):
        qui = np.flatnonzero(c.actif & ((c.t >= tb.prochain) | tb.reveil))
        if len(qui):
            _, _, paquet = dec(qui)
            tb.appliquer(qui, JEU.niveaux_np(paquet[:, :len(qui)]))
        tb.avancer()
        c.actif &= ~(c.mort | c.reussi)
    return tb


def _entrees(tb, net, qui):
    from collapsar.ecole.precision import jeu as JEU
    t, cols, fc, pos = tb.entrees(qui)
    s = tb.vue.structure(t, cols)
    car, pos, _ = JEU.yeux_complets(tb, s, t, pos, torch.as_tensor(np.asarray(qui, np.int64), device=t.device), net)
    return s, torch.cat([car, pos], -1), fc, pos, car


@torch.no_grad()
def prouver_miroir(net, U, B: int = 256, bougies: int = 300, graine: int = 5) -> dict:
    """Sur de VRAIES situations (or réel et retourné, positions, ordres et journal remplis par une partie) :
    (1) miroir(miroir(x)) = x exactement ; (2) yeux calculés sur les prix réfléchis = vue miroir ; (3) le cerveau
    symétrique : probabilité de chaque choix en x = celle du choix miroir en miroir(x), niveaux réfléchis ; (4) monde
    parfaitement symétrique (chaque situation + son miroir) : P(achat) totale = P(vente) totale."""
    from collapsar.ecole.precision import cerveau as C
    from collapsar.ecole.precision import journal_trading as JN
    assert getattr(net, "symetrique", False)
    tb = _monter(net, U, B, bougies, graine)
    qui = np.flatnonzero(tb.cpt.actif)
    s, fm, fc, pos, car = _entrees(tb, net, qui)
    out = {"situations": int(len(qui)), "en_position": int((pos[..., 0] != 0).sum()),
           "ordre_en_attente": int((pos[..., 1] != 0).sum())}
    if net.n_journal:
        out["journal_non_vide"] = int((pos[..., C.N_POS + JN.NT + 4] > 0).sum())
    m = miroir_vue(fm, net)
    out["involution_exacte"] = bool(torch.equal(miroir_vue(m, net), fm))
    out["vue_miroir_differente"] = bool(not torch.equal(m, fm))
    sm = miroir_structure(s)
    car_m = tb.vue.caracteristiques(sm)
    nc = car.shape[-1]
    out["yeux_prix_reflechis_ecart_max"] = float((car_m - m[..., :nc]).abs().max())
    q, qm = JN.situation(s, tb.U.tTEMPS[s["t"]]), JN.situation(sm, tb.U.tTEMPS[s["t"]])
    out["situation_journal_ecart_max"] = float((qm - q.flip(2)).abs().max())
    pos_m = m[..., nc:]
    ec = {"lp": 0.0, "lp_exec": 0.0, "hasard": 0.0, "valeur": 0.0, "lp_geste": 0.0, "niveaux_prix": 0.0}
    autres_ok = True
    net.voir_lois = True
    try:
        n_ach, n_ven = 0, 0
        for k in range(4):
            torch.manual_seed(100 + k)
            ch, lp, lpe, hz, val, lv = C.politique(net, s, fm, fc, pos)
            _, lp2, lpe2, hz2, val2, lv2 = C.politique(net, sm, m, fc, pos_m, miroir_choix(ch))
            o = lv["ouvre"]
            n_ach += int((o & (lv["sig"] > 0)).sum())
            n_ven += int((o & (lv["sig"] < 0)).sum())
            for nom, a, b in (("lp", lp, lp2), ("lp_exec", lpe, lpe2), ("hasard", hz, hz2), ("valeur", val, val2),
                              ("lp_geste", lv["lp_geste"], lv2["lp_geste"][..., list(GESTE_MIROIR)])):
                ec[nom] = max(ec[nom], float((a - b).abs().max()))
            p = s["p"]
            for kk in ("entree", "stop", "tp1", "dest"):         # niveaux des ouvertures : réfléchis (x -> 2 p - x)
                a, b = lv[kk][o], (2 * p - lv2[kk])[o]
                autres_ok &= bool(torch.equal(torch.isnan(a), torch.isnan(b)))
                f = ~torch.isnan(a)
                if f.any():
                    ec["niveaux_prix"] = max(ec["niveaux_prix"], float(((a - b).abs()[f] / s["A"][o][f]).max()))
            autres_ok &= bool(torch.equal(lv["sig"][o], -lv2["sig"][o]))
            for kk in ("ouvre", "limite", "ferme", "validite", "delai"):
                autres_ok &= bool(torch.equal(lv[kk], lv2[kk]))
            for kk in ("risque_pct", "part", "suiveur_u", "suiveur_tp1", "suiveur_1r", "suiveur_ag"):
                if kk in lv:
                    autres_ok &= bool(torch.allclose(lv[kk][o], lv2[kk][o], atol=1e-4, equal_nan=True))
        out["ouvertures_tirees"] = {"achats": n_ach, "ventes": n_ven}
        out["ecarts_max_x_contre_miroir"] = ec
        out["autres_choix_identiques"] = bool(autres_ok)
        # monde parfaitement symétrique : chaque situation et son miroir
        _, _, _, _, _, lv = C.politique(net, s, fm, fc, pos)
        _, _, _, _, _, lv2 = C.politique(net, sm, m, fc, pos_m)
        pg = torch.cat([lv["lp_geste"], lv2["lp_geste"]]).exp() * torch.cat([s["slot"], s["slot"]])[..., None]
        tot = pg.sum((0, 1)).double()
        out["monde_symetrique_P_achat"] = float(tot[C.ACHAT_M] + tot[C.ACHAT_L]) / float(tot.sum())
        out["monde_symetrique_P_vente"] = float(tot[C.VENTE_M] + tot[C.VENTE_L]) / float(tot.sum())
    finally:
        net.voir_lois = False
    return out


@torch.no_grad()
def mesurer_reel_retourne(nets: dict, U, B: int = 512, graine: int = 9) -> dict:
    """Comptes NEUFS (sans position, journal vide) aux MÊMES instants sur l'or réel (colonne réelle) et sur l'or retourné
    (colonne miroir) : (1) écart entre la vue miroir de l'or réel et la vue de l'or retourné ; (2) pour chaque cerveau :
    P(acheter) et P(vendre) moyennes sur l'or réel et sur l'or retourné, et l'écart entre P(acheter | réel) et
    P(vendre | retourné) aux mêmes instants (0 = décision exactement miroir)."""
    from collapsar.ecole.precision import cerveau as C
    j_reel = [j for j, (_, mir) in enumerate(U.variantes) if not mir][0]
    j_mir = [j for j, (_, mir) in enumerate(U.variantes) if mir][0]
    rng = np.random.default_rng(graine)
    lo = int(max(U.premier[j_reel], U.premier[j_mir]))
    t0 = rng.integers(lo, U.T - 400, B // 2)
    cols = np.r_[np.full(B // 2, j_reel), np.full(B // 2, j_mir)][:, None]
    dep = np.r_[t0, t0]
    out = {"instants": int(B // 2)}
    net0 = next(iter(nets.values()))
    tb = _monter(net0, U, B, 0, graine, cols, dep)
    qui = np.arange(B)
    s, fm, fc, pos, car = _entrees(tb, net0, qui)
    h = B // 2
    m = miroir_vue(fm[:h], net0)[..., :car.shape[-1]]
    d = (m - car[h:]).abs()
    out["vue"] = {"ecart_moyen": float(d.mean()), "ecart_median": float(d.median()),
                  "part_valeurs_egales_a_0_01_pres_pct": float((d <= 0.01).float().mean() * 100),
                  "part_valeurs_egales_a_0_05_pres_pct": float((d <= 0.05).float().mean() * 100),
                  "zones_presentes_identiques_pct": float((m[..., :len(UNITES) * 2 * R().yeux.zones_par_cote * 8:8]
                                                           == car[h:, :, :len(UNITES) * 2 * R().yeux.zones_par_cote * 8:8])
                                                          .float().mean() * 100)}
    for nom, net in nets.items():
        s, fm, fc, pos, _ = _entrees(tb, net, qui)
        net.voir_lois = True
        try:
            _, _, _, _, _, lv = C.politique(net, s, fm, fc, pos)
        finally:
            net.voir_lois = False
        pg = lv["lp_geste"].exp()[:, 0]                                       # [B, 6]
        ach = pg[:, C.ACHAT_M] + pg[:, C.ACHAT_L]
        ven = pg[:, C.VENTE_M] + pg[:, C.VENTE_L]
        part = lambda a, b: float(a.mean() / (a.mean() + b.mean()) * 100)
        out[nom] = {"reel_P_achat_pct": float(ach[:h].mean() * 100), "reel_P_vente_pct": float(ven[:h].mean() * 100),
                    "retourne_P_achat_pct": float(ach[h:].mean() * 100), "retourne_P_vente_pct": float(ven[h:].mean() * 100),
                    "reel_part_achats_pct": part(ach[:h], ven[:h]), "retourne_part_achats_pct": part(ach[h:], ven[h:]),
                    "ecart_moyen_P_achat_reel_contre_P_vente_retourne": float((ach[:h] - ven[h:]).abs().mean()),
                    "lien_P_achat_reel_P_vente_retourne": float(np.corrcoef(ach[:h].numpy(), ven[h:].numpy())[0, 1])
                    if float(ach[:h].std()) > 0 and float(ven[h:].std()) > 0 else float("nan")}
    return out


@torch.no_grad()
def partie_cotes(net, U, B: int = 256, bougies: int = 600, graine: int = 21) -> dict:
    """Une partie (comptes appariés : moitié or réel, moitié or retourné aux mêmes départs) : ouvertures par côté du
    monde et par sens, regards, trades fermés et leur R moyen par sens."""
    from collapsar.ecole.precision import jeu as JEU
    from collapsar.ecole.precision import journal_trading as JN
    j_reel = [j for j, (_, mir) in enumerate(U.variantes) if not mir][0]
    j_mir = [j for j, (_, mir) in enumerate(U.variantes) if mir][0]
    rng = np.random.default_rng(graine)
    lo = int(max(U.premier[j_reel], U.premier[j_mir]))
    t0 = rng.integers(lo, U.T - bougies - 100, B // 2)
    cols = np.r_[np.full(B // 2, j_reel), np.full(B // 2, j_mir)][:, None]
    tb = JEU.Table(U, B, 1)
    JN.equiper(tb, net, "ecole")
    tb.demarrer(np.ones(B, bool), cols, np.r_[t0, t0])
    dec = JEU.Decideur(tb, net, evaluer=False, graphe=False)
    torch.manual_seed(graine)
    from collapsar.ecole.precision import simulateur as SIM
    c = tb.cpt
    cpt = {k: {"gestes_achat": 0, "gestes_vente": 0, "positions_achat": 0, "positions_vente": 0, "regards": 0,
               "r": {1: [], -1: []}} for k in ("reel", "retourne")}
    cote = np.where(np.arange(B) < B // 2, "reel", "retourne")
    for _ in range(bougies):
        qui = np.flatnonzero(c.actif & ((c.t >= tb.prochain) | tb.reveil))
        if len(qui):
            _, _, paquet = dec(qui)
            g = JEU.niveaux_np(paquet[:, :len(qui)])
            for i, b in enumerate(qui):
                cpt[cote[b]]["regards"] += 1
                if g["ouvre"][i, 0]:                      # décision d'ouvrir (au marché ou ordre limite posé)
                    cpt[cote[b]]["gestes_achat" if g["sig"][i, 0] > 0 else "gestes_vente"] += 1
            tb.appliquer(qui, g)
        # sens de ce qui peut s'ouvrir ou se fermer à cette bougie : position, sinon ordre en attente, sinon ordre envoyé
        sens = np.sign(c.u[:, 0])
        sens = np.where(sens != 0, sens, np.sign(c.att_u[:, 0]) * (c.att[:, 0] > 0))
        sens = np.where(sens != 0, sens, np.sign(c.ord_u[:, 0]))
        actifs = c.actif.copy()
        tb.avancer()
        ev = c.evt[:, 0]
        for b in np.flatnonzero(((ev & (SIM.OUVERTE | SIM.EXECUTE)) != 0) & actifs):
            sg = np.sign(c.u[b, 0]) or sens[b]
            cpt[cote[b]]["positions_achat" if sg > 0 else "positions_vente"] += 1
        rr = c.r_ferme[:, 0]
        for b in np.flatnonzero(np.isfinite(rr) & actifs):
            cpt[cote[b]]["r"][1 if sens[b] >= 0 else -1].append(float(rr[b]))
        c.actif &= ~(c.mort | c.reussi)
    out = {}
    for k, v in cpt.items():
        po = v["positions_achat"] + v["positions_vente"]
        go = v["gestes_achat"] + v["gestes_vente"]
        out[k] = {"regards": v["regards"], "gestes_ouvrir": go,
                  "gestes_part_achats_pct": 100 * v["gestes_achat"] / go if go else float("nan"),
                  "positions_ouvertes": po, "positions_achat": v["positions_achat"], "positions_vente": v["positions_vente"],
                  "part_achats_pct": 100 * v["positions_achat"] / po if po else float("nan"),
                  "trades_achats": len(v["r"][1]), "trades_ventes": len(v["r"][-1]),
                  "r_achats": float(np.mean(v["r"][1])) if v["r"][1] else float("nan"),
                  "r_ventes": float(np.mean(v["r"][-1])) if v["r"][-1] else float("nan")}
    return out


def _univers_preuve(appareil: str = "cpu"):
    """Le petit monde réel des preuves (comme trois_changements) : l'or à la minute, réel et retourné, 02-10/2021."""
    from collapsar.ecole.precision.univers import Univers
    return Univers([("XAUUSD@M1", False), ("XAUUSD@M1", True)], pd.Timestamp("2021-02-01"), pd.Timestamp("2021-10-01"),
                   appareil)


def preuves(cime_net, sym_net, U, leger: bool = False) -> dict:
    """`leger` (tests) : petites tailles."""
    p = prouver_miroir(sym_net, U, *((64, 120) if leger else ()))
    mesure = mesurer_reel_retourne({"cime": cime_net, "symetrique": sym_net}, U, *((64,) if leger else ()))
    parties = {k: partie_cotes(n, U, *((32, 150) if leger else ())) for k, n in (("cime", cime_net), ("symetrique", sym_net))}
    return {"miroir": p, "reel_contre_retourne": mesure, "parties": parties}


def preuves_ok(x: dict) -> bool:
    p = x["miroir"]
    e = p["ecarts_max_x_contre_miroir"]
    return bool(p["involution_exacte"] and p["vue_miroir_differente"] and p["autres_choix_identiques"]
                and p["yeux_prix_reflechis_ecart_max"] < 1e-2 and p["situation_journal_ecart_max"] < 1e-3
                and max(e["lp"], e["lp_exec"], e["hasard"], e["lp_geste"]) < 1e-3 and e["valeur"] < 1e-4
                and e["niveaux_prix"] < 1e-3
                and abs(p["monde_symetrique_P_achat"] - p["monde_symetrique_P_vente"]) < 1e-6)


# ============================================================================================== la greffe
def _allumer(dossier: Path):
    from collapsar.ecole.precision import journal_trading as JN
    from collapsar.ecole.precision import suiveur as SV
    from collapsar.ecole.precision import tendance as TD
    JN._allumer_comme_l_arbre(dossier)
    if (dossier / "tendance.json").exists():
        TD.activer()
    if (dossier / "suiveur_1r.json").exists() and SV.active():
        R().mains.suiveur_1r = True


def appliquer(dossier: Path | None = None, code_avant: Path | None = None, dire=print, leger: bool = False) -> dict:
    """UNE branche « symetrique » née de la cime (mêmes poids, cerveau symétrique) remplace la branche la plus faible hors
    cime (archivée). Sauvegarde complète d'abord (vie + code d'avant si donné). Preuves écrites ; rien n'est changé si
    elles échouent."""
    from collapsar.arbre.jardinier import Arbre
    from collapsar.arbre.journal import Journal
    from collapsar.ecole.precision import cerveau as C
    from collapsar.ecole.precision import suiveur as SV
    dossier = (Path(dossier) if dossier else VIE).resolve()
    if (dossier / FICHIER).exists():
        raise SystemExit(f"{dossier} : le cerveau symétrique est déjà greffé ({FICHIER})")
    if SV._pid_vivant(dossier / "coeur.verrou"):
        raise SystemExit("le cœur bat encore : créer ARRET et attendre sa fin")
    if not (dossier / "ARRET").exists():
        raise SystemExit(f"{dossier / 'ARRET'} doit être en place pendant la manipulation")
    _allumer(dossier)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    sauve = dossier / "sauvegardes" / f"avant_symetrique_{stamp}"
    shutil.copytree(dossier, sauve / "vie", ignore=shutil.ignore_patterns("journal_trades", "sauvegardes", "precision",
                                                                         "contrefactuel", "symetrique"))
    if code_avant is not None and Path(code_avant).exists():
        shutil.copytree(code_avant, sauve / "code_avant")
    dire(f"sauvegarde complète : {sauve}")
    out = dossier / "symetrique"
    out.mkdir(exist_ok=True)
    arbre = Arbre.charger(dossier / "arbre.json")
    cime = arbre.cime
    faible = SV.la_plus_faible(arbre, {cime})
    if faible is None:
        raise SystemExit("aucune branche à remplacer (hors cime)")
    dire(f"cime {cime} (niveau {arbre.branches[cime].score:+.2f}) ; remplacée : {faible} (niveau "
         f"{arbre.branches[faible].score:+.2f})")
    e = torch.load(dossier / "branches" / f"{cime}.pt", map_location="cpu", weights_only=False)
    tc = dict(e.get("temperament") or arbre.branches[cime].temperament)
    tc.pop("alertes", None)
    t = {**tc, "nom": "symetrique", "symetrique": {"version": VERSION, "geste": "rien/fermer = moyenne x et miroir(x)"},
         "heritage": f"cime {cime}, cerveau symétrique (achat et vente jugés par les mêmes neurones, {stamp})"}
    cime_net = C.regler_symetrie(C.regler_precision(C.cerveau_pour(e["cerveau"]), tc), tc)
    sym = C.regler_symetrie(C.regler_precision(C.cerveau_pour(e["cerveau"]), t), t)
    assert sym.symetrique and not cime_net.symetrique
    U = _univers_preuve()
    x = preuves(cime_net, sym, U, leger)
    x.update({"cime": cime, "remplacee": faible, "date": datetime.now().isoformat(timespec="seconds"),
              "monde": "XAUUSD@M1 réel + retourné, 02/2021 -> 10/2021 (processeur)"})
    (out / "preuves.json").write_text(json.dumps(x, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
    dire("preuves : " + json.dumps(x["miroir"], ensure_ascii=False, default=float))
    dire("réel contre retourné : " + json.dumps(x["reel_contre_retourne"], ensure_ascii=False, default=float))
    dire("parties : " + json.dumps(x["parties"], ensure_ascii=False, default=float))
    if not preuves_ok(x):
        raise SystemExit(f"PREUVE RATÉE (rien n'est changé dans l'arbre) : voir {out / 'preuves.json'}")
    journal = Journal(dossier / "journal_croissance.jsonl")
    arbre.mourir(faible, "coupée")
    (dossier / "archives").mkdir(exist_ok=True)
    for f in (f"{faible}.pt", f"{faible}_meilleur.pt"):
        if (dossier / "branches" / f).exists():
            shutil.move(str(dossier / "branches" / f), str(dossier / "archives" / f))
    journal.ecrire("coupe", branche=faible, raison="archivée (place pour la branche au cerveau symétrique, 19/10)")
    b = arbre.naitre([cime], t)
    opt = torch.optim.AdamW(sym.parameters(), lr=float(t.get("vitesse", R().ecole.vitesse)), weight_decay=1e-4)
    tmp = dossier / "branches" / f"{b.nom}.pt.tmp"
    torch.save({"cerveau": sym.state_dict(), "opt": opt.state_dict(), "temperament": t}, tmp)
    os.replace(tmp, dossier / "branches" / f"{b.nom}.pt")
    journal.ecrire("naissance", branche=b.nom, parents=[cime], temperament=t, heritage=t["heritage"])
    arbre._elire_cime()
    arbre.sauver(dossier / "arbre.json")
    fx = dossier / "derniers_examens.json"
    if fx.exists():
        ex = json.loads(fx.read_text(encoding="utf-8"))
        ex.pop(faible, None)
        fx.write_text(json.dumps(ex, ensure_ascii=False, default=float), encoding="utf-8")
    info = {"date": datetime.now().isoformat(timespec="seconds"), "version": VERSION, "branche": b.nom, "cime": cime,
            "remplacee": faible, "sauvegarde": str(sauve), "preuves": str(out / "preuves.json")}
    journal.ecrire("symetrique", **{k: v for k, v in info.items() if k != "date"})
    (dossier / FICHIER).write_text(json.dumps(info, ensure_ascii=False, indent=1), encoding="utf-8")
    dire(f"branche {b.nom} « symetrique » née de la cime {cime} ; {faible} archivée")
    return info


def defaire(dossier: Path | None = None, dire=print):
    """Retour arrière complet (arbre arrêté) : la vie de l'arbre d'avant la greffe (sauvegarde) ; le code peut rester
    (sans le mot « symetrique » dans un tempérament il ne change rien)."""
    from collapsar.ecole.precision import suiveur as SV
    dossier = (Path(dossier) if dossier else VIE).resolve()
    if SV._pid_vivant(dossier / "coeur.verrou"):
        raise SystemExit("le cœur bat encore : l'arrêter d'abord (fichier ARRET)")
    info = json.loads((dossier / FICHIER).read_text(encoding="utf-8"))
    sauve = Path(info["sauvegarde"]) / "vie"
    shutil.rmtree(dossier / "branches")
    shutil.copytree(sauve / "branches", dossier / "branches")
    for nom in ("arbre.json", "cime.pt", "derniers_examens.json", "journal_croissance.jsonl", "note_cotes.json"):
        if (sauve / nom).exists():
            shutil.copy2(sauve / nom, dossier / nom)
    for f in (f"{info['remplacee']}.pt", f"{info['remplacee']}_meilleur.pt"):
        (dossier / "archives" / f).unlink(missing_ok=True)
    (dossier / FICHIER).unlink(missing_ok=True)
    dire(f"cerveau symétrique défait : vie remise depuis {sauve}")


def retirer(dossier: Path | None = None, dire=print):
    """Retour arrière léger (arbre arrêté) : la branche symétrique (et ses filles) est archivée, l'arbre continue (la
    cime se divise pour reprendre la place)."""
    from collapsar.arbre.jardinier import Arbre
    from collapsar.arbre.journal import Journal
    from collapsar.ecole.precision import suiveur as SV
    dossier = (Path(dossier) if dossier else VIE).resolve()
    if SV._pid_vivant(dossier / "coeur.verrou"):
        raise SystemExit("le cœur bat encore : l'arrêter d'abord (fichier ARRET)")
    arbre = Arbre.charger(dossier / "arbre.json")
    journal = Journal(dossier / "journal_croissance.jsonl")
    sym = [b.nom for b in arbre.vivantes() if est_symetrique(b.temperament)]
    if arbre.cime in sym and len(sym) == len(arbre.vivantes()):
        raise SystemExit("toutes les branches sont symétriques : utiliser « defaire »")
    for n in sym:
        arbre.mourir(n, "coupée")
        for f in (f"{n}.pt", f"{n}_meilleur.pt"):
            if (dossier / "branches" / f).exists():
                shutil.move(str(dossier / "branches" / f), str(dossier / "archives" / f))
        journal.ecrire("coupe", branche=n, raison="cerveau symétrique retiré (retour arrière)")
    arbre._elire_cime()
    arbre.sauver(dossier / "arbre.json")
    (dossier / FICHIER).unlink(missing_ok=True)
    dire(f"branches symétriques archivées : {sym} ; cime {arbre.cime}")


def main(argv=None):
    ap = argparse.ArgumentParser(description="cerveau symétrique de MAGNETAR (19/10)")
    ap.add_argument("quoi", choices=["appliquer", "defaire", "retirer"])
    ap.add_argument("--dossier", default=None)
    ap.add_argument("--code-avant", default=None)
    a = ap.parse_args(argv)
    d = Path(a.dossier) if a.dossier else None
    if a.quoi == "appliquer":
        appliquer(d, Path(a.code_avant) if a.code_avant else None)
    elif a.quoi == "defaire":
        defaire(d)
    else:
        retirer(d)


if __name__ == "__main__":
    main()
