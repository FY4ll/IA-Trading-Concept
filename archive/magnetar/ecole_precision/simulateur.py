"""Le simulateur FTMO de l'école de la précision : les règles de mains/simulateur.py (compte FTMO de 100 000 $, ordres
à l'ouverture de la bougie suivante, écart payé, stop d'abord si stop et objectif dans la même bougie, fermeture avant
une pause de plus de 2 h, frais de nuit au minuit du serveur, murs FTMO au pire moment de la bougie, inactivité 30 jours,
4 jours de trading pour réussir), réécrites en boucles compilées (rapides pour des milliers de comptes), avec en plus
la GESTION DU CHEF DE PROJET, comme dans MetaTrader avec un programme de gestion :
- chaque position porte un stop, un OBJECTIF 1 (TP1) avec la part à y encaisser (0, 50 ou 80 % de la position de
  départ) et une DESTINATION (objectif final, ou aucune : « laisser courir ») ;
- TP1 touché : la part est fermée au prix de TP1, et le stop du reste passe À L'ENTRÉE (actif dès la bougie suivante) ;
- un ORDRE LIMITE porte ses protections (stop, TP1, part, destination), comme un ordre MetaTrader avec stop et
  objectif ; s'il s'exécute, la bougie d'exécution est jugée au PIRE : si son plus bas (achat) atteint le stop, le stop
  est pris dans la même bougie ; TP1 et destination ne sont jamais pris dans la bougie d'exécution ;
- un stop paie l'écart PLUS un demi-frais de glissement (mesuré : ~+0,5 fiche) ;
- taille trop grosse pour la marge (levier FTMO) : ramenée à ce que permet la marge (comme un trader qui réduit son lot).
Frais : l'écart est dans les prix (achat à prix x (1 + demi-frais), vente à prix x (1 - demi-frais)), demi-frais de
CHAQUE bougie (frais FTMO de l'époque). Codes d'événements par position (bits) : 1 stop, 2 TP1, 4 destination,
8 fermée avant une pause, 16 ordre limite exécuté, 32 refusé, 64 fermée par elle, 128 ouverte au marché, 256 ordre
expiré, 512 stop remonté par le stop suiveur.
COMPTE SWING (19/10/2026, réglage `mains.compte: swing`, arbre de l'or ; univers.py) : aucune fermeture forcée avant
les pauses ni le week-end, ordres en attente gardés ; la position du vendredi vit le lundi : frais de nuit FTMO
(horloge.nuits_payees : nuit triple le mercredi pour les métaux, samedi et dimanche à 0) et écart d'ouverture du lundi
subi comme sur MT5 (stop, objectif, ordre limite pris au prix d'ouverture s'il est déjà dépassé, murs au pire de la
bougie). Pas de nouvelle position dans les 2 dernières heures avant une pause de plus de 2 h (`sans_ouv`).
STOP SUIVEUR (18/10/2026, arbre de l'or ; un CHOIX de l'IA, jamais imposé ; aucune position n'en a si elle ne l'a pas
choisi, et alors rien ne change, prouvé par tests/test_suiveur.py) : la position porte une unité (`sv_u`, place dans les
tableaux de sommets / creux du monde, -1 = aucun), le moment où il commence (`sv_tp1` : dès l'entrée, ou seulement après
l'objectif 1) et une marge en prix. À l'ouverture de chaque bougie n (avant le contrôle du stop), s'il y a un NOUVEAU creux
(achat) / sommet (vente) confirmé de cette unité depuis l'entrée (ou depuis l'objectif 1), connu à la clôture de n - 1, le
stop passe juste derrière (marge), seulement s'il est plus favorable que l'ancien (jamais reculé) et encore du bon côté du
prix d'ouverture. Même règle que regarder/pistes/mouvements.trade_suiveur (égalité testée). Après l'objectif 1, le stop
du reste passe à l'entrée SAUF si le suiveur l'a déjà mis plus loin.
STOP SUIVEUR APRÈS +1R (19/10/2026, accord du chef de projet ; options d'UNE branche, suiveur.py) : la position porte en
plus `sv_1r` (le suiveur n'agit qu'APRÈS +1R atteint : avant, seul le stop d'origine compte) et `sv_ag` (> 0 : variante
par agitation, en prix : le stop suit à `sv_ag` sous le plus haut atteint (achat) / au-dessus du plus bas (vente), au lieu
des creux / sommets confirmés). +1R atteint = le meilleur prix de sortie depuis l'entrée (plus haut x (1 - demi-frais)
pour un achat, plus bas x (1 + demi-frais) pour une vente, bougies TERMINÉES ; la bougie d'exécution d'un ordre limite ne
compte pas) à au moins une fois la distance entrée -> stop d'origine (`sv_r0`) au-delà de l'entrée. Vérifié à l'ouverture
de chaque bougie, avant le contrôle du stop. Jamais reculé, jamais au-delà du prix d'ouverture (mêmes gardes que le
suiveur d'avant). Sans `sv_1r` (toutes les autres positions) : exactement comme avant (empreintes identiques).
"""
from __future__ import annotations

import numpy as np
from numba import njit

from collapsar.mains.simulateur import CAPITAL, INACTIVITE_JOURS, JOURS_TRADING_MIN, MUR_JOUR, MUR_TOTAL, OBJECTIF_FTMO

STOP, TP1, DEST, FORCEE, EXECUTE, REFUS, ELLE, OUVERTE, EXPIRE, SUIVI = 1, 2, 4, 8, 16, 32, 64, 128, 256, 512
RIEN, MARCHE, LIMITE, FERMER = 0, 1, 2, 3
SANS_SUIVEUR_V = np.full((1, 1, 1, 2), np.nan)          # monde sans sommets / creux pour le suiveur (jamais lus)
SANS_SUIVEUR_ID = np.zeros((1, 1, 1, 2), np.int64)


@njit(cache=True)
def _suivre(lg, u_, m, n, sw_v, sw_id, ref, marge, st, oo, s):
    """Nouveau stop proposé par le stop suiveur à l'ouverture de la bougie n (NaN = pas de changement)."""
    k = 0 if lg else 1
    if n < 1 or sw_id[n - 1, m, u_, k] <= ref:
        return np.nan
    v = sw_v[n - 1, m, u_, k]
    if not np.isfinite(v):
        return np.nan
    if lg:
        cand = v - marge
        if cand > st and cand < oo * (1 - s):
            return cand
    else:
        cand = v + marge
        if cand < st and cand > oo * (1 + s):
            return cand
    return np.nan


@njit(cache=True)
def _suivre_agitation(lg, haut, ag, st, oo, s):
    """Stop suiveur par agitation (après +1R) : `ag` (prix) sous le plus haut atteint (achat) / au-dessus du plus bas
    (vente) ; NaN = pas de changement (jamais reculé, jamais au-delà du prix d'ouverture)."""
    if lg:
        cand = haut - ag
        if cand > st and cand < oo * (1 - s):
            return cand
    else:
        cand = haut + ag
        if cand < st and cand > oo * (1 + s):
            return cand
    return np.nan


@njit(cache=True)
def _arrondi_lot(du, o, fx, pu, pdl, mu):
    pas = pu if pu > 0 else pdl / (o * fx)
    q = np.floor(abs(du) / pas + 0.5) * pas
    if q < mu:
        q = 0.0
    return q * (1.0 if du >= 0 else -1.0), pas


@njit(cache=True)
def _plafond_marge(du, o, fx, lev, valeur_o, engage, pas, mu):
    """Ramène une ouverture à ce que permet la marge (engagé <= valeur du compte, levier FTMO)."""
    reste = valeur_o - engage
    if reste <= 0:
        return 0.0
    umax = reste * lev / (o * fx)
    if abs(du) <= umax:
        return du
    q = np.floor(umax / pas) * pas
    if q < mu or q <= 0:
        return 0.0
    return q * (1.0 if du >= 0 else -1.0)


@njit(cache=True)
def pas_comptes(o, h, l, c, fx, ouvert, derniere, demi, nuit_a, nuit_v, nuits, jour, levier, pas_u, pas_d, min_u,
                col, t, actif, solde, solde_minuit, jour_cpt, jours_trades, jour_dernier, jour_debut,
                u, entree, stop, tp1, part, dest, tp1_fait, u_init, risque, pnl_trade,
                att, att_prix, att_u, att_stop, att_tp1, att_part, att_dest, att_reste,
                ord_act, ord_u, ord_prix, ord_stop, ord_tp1, ord_part, ord_dest, ord_duree,
                glissement, capital,
                valeur_out, mort_out, inactif_out, reussi_out, evt, r_ferme, frais_out, nuit_out,
                sw_v, sw_id, sv_u, sv_tp1, sv_m, sv_id, sv_n, att_sv_u, att_sv_tp1, att_sv_m,
                ord_sv_u, ord_sv_tp1, ord_sv_m, sans_ouv, nuit_debut,
                sv_1r, sv_ag, sv_r0, sv_haut, sv_on, sv_dern, att_sv_1r, att_sv_ag, ord_sv_1r, ord_sv_ag):
    """Une bougie pour tous les comptes `actif` : chacun passe de son instant t à t + 1. Les ordres (ord_*) sont ceux
    décidés à la clôture de t (ord_act 0 rien, 1 au marché, 2 ordre limite, 3 fermer / annuler). Les tableaux d'état
    sont modifiés sur place ; les sorties (valeur, mort, inactif, réussi, événements, R des trades fermés, frais et
    nuits payés) sont écrites pour chaque compte. Stop suiveur : sw_v / sw_id [T, M, unités, 2] (dernier creux / sommet
    confirmé connu à la clôture de chaque bougie et son numéro), sv_* l'état de chaque position, att_sv_* celui d'un
    ordre limite en attente, ord_sv_* les choix de ce regard (sv_u = -1 : aucun suiveur).
    `derniere` [T, M] : fermeture forcée + ordres annulés (compte Normal ; tout à False en compte Swing) ;
    `sans_ouv` [T, M] : aucune nouvelle position à cette bougie (compte Normal : le même tableau que `derniere` ;
    compte Swing : les 2 dernières heures avant une pause de plus de 2 h, règle FTMO contre le jeu des écarts) ;
    `nuit_debut` (compte Swing) : les frais de nuit sont payés par toute position OUVERTE AU PASSAGE de minuit (au début
    de la bougie, au prix de clôture d'avant minuit), même si elle se ferme à l'ouverture qui suit (stop pris dans
    l'écart du lundi, fermeture à la main) ; False (compte Normal, HYPERNOVA) : comme avant, payés après la bougie par
    les positions encore ouvertes.
    Suiveur après +1R : sv_1r / sv_ag / sv_r0 / sv_haut / sv_on / sv_dern (état de chaque position : après +1R ?,
    distance par agitation en prix (0 = creux / sommets), distance d'origine entrée -> stop, meilleur prix de sortie
    atteint, +1R déjà atteint, dernier stop posé par le suiveur), att_sv_1r / att_sv_ag (ordre en attente),
    ord_sv_1r / ord_sv_ag (choix de ce regard). Tout à False / 0 : comme avant."""
    B, J = col.shape
    T = o.shape[0]
    for b in range(B):
        for j in range(J):
            evt[b, j] = 0
            r_ferme[b, j] = np.nan
        frais_out[b] = 0.0
        nuit_out[b] = 0.0
        mort_out[b] = False
        inactif_out[b] = False
        reussi_out[b] = False
        if not actif[b]:
            continue
        n = t[b] + 1
        if n > T - 1:
            n = T - 1
        if jour[n] != jour_cpt[b]:
            solde_minuit[b] = solde[b]
            jour_cpt[b] = jour[n]
        ouvre_cpt = False
        # 1. consignes : ordre limite posé ou annulé ; 2. pause > 2 h : ordre annulé
        for j in range(J):
            m = col[b, j]
            if m < 0:
                continue
            a = ord_act[b, j]
            if a == LIMITE and u[b, j] == 0 and att[b, j] == 0:
                att[b, j] = 1
                att_prix[b, j] = ord_prix[b, j]
                att_u[b, j] = ord_u[b, j]
                att_stop[b, j] = ord_stop[b, j]
                att_tp1[b, j] = ord_tp1[b, j]
                att_part[b, j] = ord_part[b, j]
                att_dest[b, j] = ord_dest[b, j]
                att_reste[b, j] = ord_duree[b, j]
                att_sv_u[b, j] = ord_sv_u[b, j]
                att_sv_tp1[b, j] = ord_sv_tp1[b, j]
                att_sv_m[b, j] = ord_sv_m[b, j]
                att_sv_1r[b, j] = ord_sv_1r[b, j]
                att_sv_ag[b, j] = ord_sv_ag[b, j]
            elif a == FERMER and att[b, j] == 1:
                att[b, j] = 0
            if derniere[n, m]:
                att[b, j] = 0
        # frais de nuit au PASSAGE de minuit (compte Swing) : positions ouvertes entre t et n
        if nuit_debut:
            tp = t[b]
            for j in range(J):
                m = col[b, j]
                if m < 0 or u[b, j] == 0 or nuits[n, m] == 0:
                    continue
                taux = nuit_a[n, m] if u[b, j] > 0 else nuit_v[n, m]
                nu = abs(u[b, j]) * c[tp, m] * fx[tp, m] * taux / 360.0 * nuits[n, m]
                solde[b] -= nu
                pnl_trade[b, j] -= nu
                nuit_out[b] += nu
        # valeur et marge à l'ouverture
        valeur_o = solde[b]
        engage = 0.0
        for j in range(J):
            m = col[b, j]
            if m < 0 or u[b, j] == 0:
                continue
            valeur_o += u[b, j] * (o[n, m] - entree[b, j]) * fx[n, m]
            engage += abs(u[b, j]) * o[n, m] * fx[n, m] / levier[m]
        # 3. ordres au marché à l'ouverture (fermer, fermeture forcée avant une pause, ouvrir)
        for j in range(J):
            m = col[b, j]
            if m < 0 or not ouvert[n, m]:
                continue
            s = demi[n, m]
            oo = o[n, m]
            f = fx[n, m]
            a = ord_act[b, j]
            if u[b, j] != 0 and (a == FERMER or derniere[n, m]):
                px = oo * (1 - s) if u[b, j] > 0 else oo * (1 + s)
                g = u[b, j] * (px - entree[b, j]) * f
                solde[b] += g
                pnl_trade[b, j] += g
                frais_out[b] += abs(u[b, j]) * px * f * s / (1 + s)
                engage -= abs(u[b, j]) * oo * f / levier[m]
                evt[b, j] |= ELLE if a == FERMER else FORCEE
                r_ferme[b, j] = pnl_trade[b, j] / risque[b, j] if risque[b, j] > 0 else np.nan
                u[b, j] = 0.0
                stop[b, j] = np.nan
                tp1[b, j] = np.nan
                dest[b, j] = np.nan
            elif a == MARCHE and u[b, j] == 0 and att[b, j] == 0 and not sans_ouv[n, m]:
                du, pas = _arrondi_lot(ord_u[b, j], oo, f, pas_u[m], pas_d[m], min_u[m])
                du = _plafond_marge(du, oo, f, levier[m], valeur_o, engage, pas, min_u[m])
                st = ord_stop[b, j]
                vente_o, achat_o = oo * (1 - s), oo * (1 + s)
                bon_stop = (du > 0 and st < vente_o) or (du < 0 and st > achat_o)
                if du == 0 or not bon_stop or not np.isfinite(st):
                    evt[b, j] |= REFUS
                    continue
                px = achat_o if du > 0 else vente_o
                u[b, j] = du
                entree[b, j] = px
                stop[b, j] = st
                t1, d1 = ord_tp1[b, j], ord_dest[b, j]
                tp1[b, j] = t1 if np.isfinite(t1) and ((du > 0 and t1 > vente_o) or (du < 0 and t1 < achat_o)) else np.nan
                dest[b, j] = d1 if np.isfinite(d1) and ((du > 0 and d1 > vente_o) or (du < 0 and d1 < achat_o)) else np.nan
                part[b, j] = ord_part[b, j] if np.isfinite(tp1[b, j]) else 0.0
                tp1_fait[b, j] = False
                u_init[b, j] = abs(du)
                risque[b, j] = abs(du) * abs(px - st) * f
                pnl_trade[b, j] = 0.0
                frais_out[b] += abs(du) * px * f * s / (1 + s)
                engage += abs(du) * oo * f / levier[m]
                evt[b, j] |= OUVERTE
                ouvre_cpt = True
                sv_u[b, j] = ord_sv_u[b, j]
                sv_n[b, j] = 0
                sv_1r[b, j] = False
                if sv_u[b, j] >= 0:
                    sv_tp1[b, j] = ord_sv_tp1[b, j]
                    sv_m[b, j] = ord_sv_m[b, j]
                    sv_id[b, j] = sw_id[n - 1, m, sv_u[b, j], 0 if du > 0 else 1]
                    if ord_sv_1r[b, j]:            # suiveur après +1R (suiveur.py, une branche)
                        sv_1r[b, j] = True
                        sv_ag[b, j] = ord_sv_ag[b, j]
                        sv_r0[b, j] = abs(px - st)
                        sv_haut[b, j] = px
                        sv_on[b, j] = False
        # 4. stop, TP1, destination (le stop d'abord : le pire cas)
        for j in range(J):
            m = col[b, j]
            if m < 0 or u[b, j] == 0 or not ouvert[n, m]:
                continue
            s = demi[n, m]
            oo, hh, ll = o[n, m], h[n, m], l[n, m]
            f = fx[n, m]
            lg = u[b, j] > 0
            if sv_u[b, j] >= 0 and sv_1r[b, j] and not sv_on[b, j]:
                # suiveur après +1R : +1R atteint (bougies terminées) ? avant, seul le stop d'origine compte
                if (lg and sv_haut[b, j] - entree[b, j] >= sv_r0[b, j]) or \
                        ((not lg) and entree[b, j] - sv_haut[b, j] >= sv_r0[b, j]):
                    sv_on[b, j] = True
            if sv_u[b, j] >= 0 and ((not sv_tp1[b, j]) or tp1_fait[b, j]) and np.isfinite(stop[b, j]) and \
                    ((not sv_1r[b, j]) or sv_on[b, j]):
                if sv_1r[b, j] and sv_ag[b, j] > 0:
                    nv = _suivre_agitation(lg, sv_haut[b, j], sv_ag[b, j], stop[b, j], oo, s)
                else:
                    nv = _suivre(lg, sv_u[b, j], m, n, sw_v, sw_id, sv_id[b, j], sv_m[b, j], stop[b, j], oo, s)
                if np.isfinite(nv):
                    stop[b, j] = nv
                    sv_n[b, j] += 1
                    evt[b, j] |= SUIVI
                    sv_dern[b, j] = nv
            st = stop[b, j]
            if np.isfinite(st) and ((lg and ll * (1 - s) <= st) or ((not lg) and hh * (1 + s) >= st)):
                if lg:
                    px = min(st, oo * (1 - s)) * (1 - glissement * s)
                else:
                    px = max(st, oo * (1 + s)) * (1 + glissement * s)
                g = u[b, j] * (px - entree[b, j]) * f
                solde[b] += g
                pnl_trade[b, j] += g
                frais_out[b] += abs(u[b, j]) * px * f * s * (1 + glissement) / (1 + s)
                evt[b, j] |= STOP
                r_ferme[b, j] = pnl_trade[b, j] / risque[b, j] if risque[b, j] > 0 else np.nan
                u[b, j] = 0.0
                stop[b, j] = np.nan
                tp1[b, j] = np.nan
                dest[b, j] = np.nan
                continue
            t1 = tp1[b, j]
            if part[b, j] > 0 and (not tp1_fait[b, j]) and np.isfinite(t1) and \
                    ((lg and hh * (1 - s) >= t1) or ((not lg) and ll * (1 + s) <= t1)):
                px = max(t1, oo * (1 - s)) if lg else min(t1, oo * (1 + s))
                q, pas = _arrondi_lot(part[b, j] * u_init[b, j], oo, f, pas_u[m], pas_d[m], min_u[m])
                if q >= abs(u[b, j]) - 0.5 * pas or abs(u[b, j]) - q < max(0.5 * pas, min_u[m]):
                    q = abs(u[b, j])
                dq = q if lg else -q
                g = dq * (px - entree[b, j]) * f
                solde[b] += g
                pnl_trade[b, j] += g
                frais_out[b] += q * px * f * s / (1 + s)
                u[b, j] -= dq
                tp1_fait[b, j] = True
                evt[b, j] |= TP1
                if u[b, j] == 0:
                    r_ferme[b, j] = pnl_trade[b, j] / risque[b, j] if risque[b, j] > 0 else np.nan
                    stop[b, j] = np.nan
                    tp1[b, j] = np.nan
                    dest[b, j] = np.nan
                    continue
                if sv_u[b, j] < 0:
                    stop[b, j] = entree[b, j]      # le reste ne peut plus perdre (hors frais) : stop à l'entrée
                else:                              # ... sauf si le stop suiveur l'a déjà mis plus loin
                    stop[b, j] = max(stop[b, j], entree[b, j]) if lg else min(stop[b, j], entree[b, j])
                    if sv_tp1[b, j]:               # suiveur « après l'objectif 1 » : les creux / sommets à venir
                        sv_id[b, j] = sw_id[n - 1, m, sv_u[b, j], 0 if lg else 1]
            d1 = dest[b, j]
            if np.isfinite(d1) and (part[b, j] == 0 or tp1_fait[b, j] or not np.isfinite(t1)) and \
                    ((lg and hh * (1 - s) >= d1) or ((not lg) and ll * (1 + s) <= d1)):
                px = max(d1, oo * (1 - s)) if lg else min(d1, oo * (1 + s))
                g = u[b, j] * (px - entree[b, j]) * f
                solde[b] += g
                pnl_trade[b, j] += g
                frais_out[b] += abs(u[b, j]) * px * f * s / (1 + s)
                evt[b, j] |= DEST
                r_ferme[b, j] = pnl_trade[b, j] / risque[b, j] if risque[b, j] > 0 else np.nan
                u[b, j] = 0.0
                stop[b, j] = np.nan
                tp1[b, j] = np.nan
                dest[b, j] = np.nan
            if sv_1r[b, j] and u[b, j] != 0:       # suiveur après +1R : meilleur prix de sortie atteint (bougie finie)
                if lg:
                    sv_haut[b, j] = max(sv_haut[b, j], hh * (1 - s))
                else:
                    sv_haut[b, j] = min(sv_haut[b, j], ll * (1 + s))
        # 5. ordres limites : passent seulement si le prix va VRAIMENT au-delà du niveau
        for j in range(J):
            m = col[b, j]
            if m < 0 or att[b, j] == 0:
                continue
            if ouvert[n, m] and not sans_ouv[n, m]:      # (compte Normal : déjà annulé à `derniere`, rien ne change)
                s = demi[n, m]
                oo, hh, ll = o[n, m], h[n, m], l[n, m]
                f = fx[n, m]
                P = att_prix[b, j]
                achat = att_u[b, j] > 0
                if (achat and ll * (1 + s) < P) or ((not achat) and hh * (1 - s) > P):
                    px = min(P, oo * (1 + s)) if achat else max(P, oo * (1 - s))
                    du, pas = _arrondi_lot(att_u[b, j], oo, f, pas_u[m], pas_d[m], min_u[m])
                    du = _plafond_marge(du, oo, f, levier[m], valeur_o, engage, pas, min_u[m])
                    att[b, j] = 0
                    if du == 0:
                        evt[b, j] |= REFUS
                        continue
                    st = att_stop[b, j]
                    u[b, j] = du
                    entree[b, j] = px
                    stop[b, j] = st
                    tp1[b, j] = att_tp1[b, j]
                    dest[b, j] = att_dest[b, j]
                    part[b, j] = att_part[b, j] if np.isfinite(att_tp1[b, j]) else 0.0
                    tp1_fait[b, j] = False
                    u_init[b, j] = abs(du)
                    risque[b, j] = abs(du) * abs(px - st) * f
                    pnl_trade[b, j] = 0.0
                    frais_out[b] += abs(du) * px * f * s / (1 + s)
                    engage += abs(du) * oo * f / levier[m]
                    evt[b, j] |= EXECUTE
                    ouvre_cpt = True
                    sv_u[b, j] = att_sv_u[b, j]
                    sv_n[b, j] = 0
                    sv_1r[b, j] = False
                    if sv_u[b, j] >= 0:
                        sv_tp1[b, j] = att_sv_tp1[b, j]
                        sv_m[b, j] = att_sv_m[b, j]
                        sv_id[b, j] = sw_id[n - 1, m, sv_u[b, j], 0 if achat else 1]
                        if att_sv_1r[b, j]:        # suiveur après +1R : la bougie d'exécution ne compte pas
                            sv_1r[b, j] = True
                            sv_ag[b, j] = att_sv_ag[b, j]
                            sv_r0[b, j] = abs(px - st)
                            sv_haut[b, j] = px
                            sv_on[b, j] = False
                    # la bougie d'exécution jugée au pire : le stop est-il atteint dans la même bougie ?
                    if (achat and ll * (1 - s) <= st) or ((not achat) and hh * (1 + s) >= st):
                        if achat:
                            px2 = min(st, oo * (1 - s)) * (1 - glissement * s)
                        else:
                            px2 = max(st, oo * (1 + s)) * (1 + glissement * s)
                        g = du * (px2 - px) * f
                        solde[b] += g
                        pnl_trade[b, j] += g
                        frais_out[b] += abs(du) * px2 * f * s * (1 + glissement) / (1 + s)
                        evt[b, j] |= STOP
                        r_ferme[b, j] = pnl_trade[b, j] / risque[b, j] if risque[b, j] > 0 else np.nan
                        u[b, j] = 0.0
                        stop[b, j] = np.nan
                        tp1[b, j] = np.nan
                        dest[b, j] = np.nan
                    continue
            att_reste[b, j] -= 1
            if att_reste[b, j] <= 0:
                att[b, j] = 0
                evt[b, j] |= EXPIRE
        # jours de trading (FTMO) : un jour où au moins un trade a été ouvert
        if ouvre_cpt:
            if jour_dernier[b] != jour_cpt[b]:
                jours_trades[b] += 1
            jour_dernier[b] = jour_cpt[b]
        # 6. frais de nuit (taux de l'époque, nuit triple FTMO) sur le prix d'ouverture (compte Normal, comme avant)
        for j in range(J):
            m = col[b, j]
            if nuit_debut or m < 0 or u[b, j] == 0:
                continue
            taux = nuit_a[n, m] if u[b, j] > 0 else nuit_v[n, m]
            nu = abs(u[b, j]) * o[n, m] * fx[n, m] * taux / 360.0 * nuits[n, m]
            solde[b] -= nu
            pnl_trade[b, j] -= nu
            nuit_out[b] += nu
        # 7. murs FTMO au pire moment de la bougie, inactivité, réussite
        valeur = solde[b]
        pire = solde[b]
        for j in range(J):
            m = col[b, j]
            if m < 0 or u[b, j] == 0:
                continue
            valeur += u[b, j] * (c[n, m] - entree[b, j]) * fx[n, m]
            pp = l[n, m] if u[b, j] > 0 else h[n, m]
            pire += u[b, j] * (pp - entree[b, j]) * fx[n, m]
        mur = (pire < solde_minuit[b] - MUR_JOUR * capital) or (pire < (1 - MUR_TOTAL) * capital)
        der = jour_dernier[b] if jour_dernier[b] > jour_debut[b] else jour_debut[b]
        inactif = (not mur) and (jour_cpt[b] - der >= INACTIVITE_JOURS)
        if mur or inactif:
            v = valeur if inactif else pire
            solde[b] = v
            valeur = v
            for j in range(J):
                u[b, j] = 0.0
                att[b, j] = 0
                stop[b, j] = np.nan
                tp1[b, j] = np.nan
                dest[b, j] = np.nan
        reussi = (not (mur or inactif)) and valeur >= (1 + OBJECTIF_FTMO) * capital and \
            jours_trades[b] >= JOURS_TRADING_MIN
        valeur_out[b] = valeur
        mort_out[b] = mur or inactif
        inactif_out[b] = inactif
        reussi_out[b] = reussi
        t[b] = n


@njit(cache=True)
def valeurs(c, fx, col, t, solde, u, entree):
    """Valeur de chaque compte à la clôture de son instant t."""
    B, J = col.shape
    v = np.empty(B)
    for b in range(B):
        x = solde[b]
        for j in range(J):
            m = col[b, j]
            if m >= 0 and u[b, j] != 0:
                x += u[b, j] * (c[t[b], m] - entree[b, j]) * fx[t[b], m]
        v[b] = x
    return v


class Comptes:
    """L'état de B comptes (paniers de J marchés au plus) dans un Univers, et le pas d'une bougie."""

    CHAMPS_BJ = ("u", "entree", "stop", "tp1", "part", "dest", "u_init", "risque", "pnl_trade",
                 "att_prix", "att_u", "att_stop", "att_tp1", "att_part", "att_dest")

    def __init__(self, U, B: int, J: int):
        self.U, self.B, self.J = U, B, J
        self.col = np.full((B, J), -1, np.int64)
        self.t = np.zeros(B, np.int64)
        self.fin = np.zeros(B, np.int64)                  # dernière ligne du challenge
        self.debut = np.zeros(B, np.int64)
        self.actif = np.zeros(B, np.bool_)
        self.solde = np.full(B, CAPITAL)
        self.solde_minuit = np.full(B, CAPITAL)
        self.jour_cpt = np.zeros(B, np.int64)
        self.jours_trades = np.zeros(B, np.int64)
        self.jour_dernier = np.full(B, -1, np.int64)
        self.jour_debut = np.zeros(B, np.int64)
        for k in self.CHAMPS_BJ:
            setattr(self, k, np.zeros((B, J)))
        for k in ("stop", "tp1", "dest", "att_stop", "att_tp1", "att_dest"):
            getattr(self, k)[:] = np.nan
        self.tp1_fait = np.zeros((B, J), np.bool_)
        self.att = np.zeros((B, J), np.int64)
        self.att_reste = np.zeros((B, J), np.int64)
        self.valeur = np.full(B, CAPITAL)
        self.mort = np.zeros(B, np.bool_)
        self.inactif = np.zeros(B, np.bool_)
        self.reussi = np.zeros(B, np.bool_)
        self.evt = np.zeros((B, J), np.int64)
        self.r_ferme = np.full((B, J), np.nan)
        self.frais = np.zeros(B)
        self.nuit = np.zeros(B)
        # stop suiveur (choix de l'IA) : sommets / creux du monde s'il les a (univers.py, réglage mains.suiveur)
        self.a_suiveur = getattr(U, "sw_v", None) is not None
        self.sw_v = U.sw_v if self.a_suiveur else SANS_SUIVEUR_V
        self.sw_id = U.sw_id if self.a_suiveur else SANS_SUIVEUR_ID
        self.sv_u = np.full((B, J), -1, np.int64)
        self.sv_tp1 = np.zeros((B, J), np.bool_)
        self.sv_m = np.zeros((B, J))
        self.sv_id = np.zeros((B, J), np.int64)
        self.sv_n = np.zeros((B, J), np.int64)
        self.att_sv_u = np.full((B, J), -1, np.int64)
        self.att_sv_tp1 = np.zeros((B, J), np.bool_)
        self.att_sv_m = np.zeros((B, J))
        # suiveur après +1R (une branche, suiveur.py) : rien de choisi = tout à False / 0 = comme avant
        self.sv_1r = np.zeros((B, J), np.bool_)
        self.sv_ag = np.zeros((B, J))
        self.sv_r0 = np.zeros((B, J))
        self.sv_haut = np.zeros((B, J))
        self.sv_on = np.zeros((B, J), np.bool_)
        self.sv_dern = np.full((B, J), np.nan)
        self.att_sv_1r = np.zeros((B, J), np.bool_)
        self.att_sv_ag = np.zeros((B, J))
        self.ordres_vides()

    def ordres_vides(self):
        B, J = self.B, self.J
        self.ord_act = np.zeros((B, J), np.int64)
        self.ord_u = np.zeros((B, J))
        self.ord_prix = np.full((B, J), np.nan)
        self.ord_stop = np.full((B, J), np.nan)
        self.ord_tp1 = np.full((B, J), np.nan)
        self.ord_part = np.zeros((B, J))
        self.ord_dest = np.full((B, J), np.nan)
        self.ord_duree = np.zeros((B, J), np.int64)
        self.ord_sv_u = np.full((B, J), -1, np.int64)
        self.ord_sv_tp1 = np.zeros((B, J), np.bool_)
        self.ord_sv_m = np.zeros((B, J))
        self.ord_sv_1r = np.zeros((B, J), np.bool_)
        self.ord_sv_ag = np.zeros((B, J))

    def recommencer(self, masque: np.ndarray, cols: np.ndarray, departs: np.ndarray):
        """Nouveaux challenges pour les comptes `masque` : panier `cols` [n, J], départ `departs` [n]."""
        i = np.flatnonzero(masque)
        if not len(i):
            return
        self.col[i] = cols
        self.t[i] = departs
        self.debut[i] = departs
        self.fin[i] = self.U.fin_challenge(departs)
        self.actif[i] = True
        self.solde[i] = CAPITAL
        self.solde_minuit[i] = CAPITAL
        self.jour_cpt[i] = self.U.jour[departs]
        self.jour_debut[i] = self.U.jour[departs]
        self.jours_trades[i] = 0
        self.jour_dernier[i] = -1
        for k in self.CHAMPS_BJ:
            getattr(self, k)[i] = 0.0
        for k in ("stop", "tp1", "dest", "att_stop", "att_tp1", "att_dest"):
            getattr(self, k)[i] = np.nan
        self.tp1_fait[i] = False
        self.att[i] = 0
        self.att_reste[i] = 0
        self.valeur[i] = CAPITAL
        self.sv_u[i] = -1
        self.att_sv_u[i] = -1
        self.sv_n[i] = 0
        self.sv_1r[i] = False
        self.att_sv_1r[i] = False
        self.sv_on[i] = False

    def valeurs(self) -> np.ndarray:
        U = self.U
        return valeurs(U.c, U.fx, self.col, self.t, self.solde, self.u, self.entree)

    def pas(self, glissement: float = 1.0):
        U = self.U
        if not self.a_suiveur and self.ord_sv_u.max(initial=-1) >= 0:
            raise ValueError("stop suiveur demandé dans un monde sans sommets / creux (réglage mains.suiveur éteint)")
        pas_comptes(U.o, U.h, U.l, U.c, U.fx, U.ouvert, U.derniere, U.demi, U.nuit_a, U.nuit_v, U.nuits, U.jour,
                    U.levier, U.pas_u, U.pas_d, U.min_u,
                    self.col, self.t, self.actif, self.solde, self.solde_minuit, self.jour_cpt, self.jours_trades,
                    self.jour_dernier, self.jour_debut,
                    self.u, self.entree, self.stop, self.tp1, self.part, self.dest, self.tp1_fait, self.u_init,
                    self.risque, self.pnl_trade,
                    self.att, self.att_prix, self.att_u, self.att_stop, self.att_tp1, self.att_part, self.att_dest,
                    self.att_reste,
                    self.ord_act, self.ord_u, self.ord_prix, self.ord_stop, self.ord_tp1, self.ord_part, self.ord_dest,
                    self.ord_duree, glissement, CAPITAL,
                    self.valeur, self.mort, self.inactif, self.reussi, self.evt, self.r_ferme, self.frais, self.nuit,
                    self.sw_v, self.sw_id, self.sv_u, self.sv_tp1, self.sv_m, self.sv_id, self.sv_n,
                    self.att_sv_u, self.att_sv_tp1, self.att_sv_m, self.ord_sv_u, self.ord_sv_tp1, self.ord_sv_m,
                    getattr(U, "sans_ouverture", U.derniere), getattr(U, "compte", "normal") == "swing",
                    self.sv_1r, self.sv_ag, self.sv_r0, self.sv_haut, self.sv_on, self.sv_dern,
                    self.att_sv_1r, self.att_sv_ag, self.ord_sv_1r, self.ord_sv_ag)
        self.ordres_vides()
