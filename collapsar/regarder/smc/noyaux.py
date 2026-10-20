"""Les calculs rapides du laboratoire SMC (numba). Chaque fonction suit docs/SMC_DEFINITIONS.md (figé) ; aucune ne
regarde une bougie après celle qui confirme une information."""
from __future__ import annotations

import numpy as np
from numba import njit

FRACTAL = 2
K_DEPART = 2.0
FVG_MIN = 0.1
EGAUX = 0.1
MARGE = 0.2
RR = 2.0
TENUE = 48
VIE = 500
REACTION = 1.0


# ---------------------------------------------------------------------- structure
@njit(cache=True)
def structure(h, l, c, atr):
    """Sommets / creux confirmés (fractal 2), cassures en clôture (1 BOS haussier, 2 CHoCH haussier, -1 BOS baissier,
    -2 CHoCH baissier), milieu du dernier couple sommet-creux confirmés, niveaux de sommets / creux égaux actifs."""
    n = len(c)
    cassure = np.zeros(n, np.int64)
    milieu = np.full(n, np.nan)
    egal_haut = np.full(n, np.nan)
    egal_bas = np.full(n, np.nan)
    sh, sl = np.nan, np.nan            # dernier sommet / creux confirmé (non cassé pour la cassure)
    sh_vu, sl_vu = np.nan, np.nan      # dernier sommet / creux confirmé (pour le premium / discount)
    sh_prec, sl_prec = np.nan, np.nan
    eh, el = np.nan, np.nan
    sens = 0
    for i in range(n):
        j = i - FRACTAL                 # la bougie j devient un sommet confirmé à la clôture de i
        if j >= FRACTAL:
            est_h, est_l = True, True
            for k in range(1, FRACTAL + 1):
                if not (h[j] > h[j - k] and h[j] > h[j + k]):
                    est_h = False
                if not (l[j] < l[j - k] and l[j] < l[j + k]):
                    est_l = False
            if est_h:
                if not np.isnan(sh_vu) and abs(h[j] - sh_vu) <= EGAUX * atr[i]:
                    eh = max(h[j], sh_vu)
                sh_prec, sh, sh_vu = sh_vu, h[j], h[j]
            if est_l:
                if not np.isnan(sl_vu) and abs(l[j] - sl_vu) <= EGAUX * atr[i]:
                    el = min(l[j], sl_vu)
                sl_prec, sl, sl_vu = sl_vu, l[j], l[j]
        if not np.isnan(sh) and c[i] > sh:
            cassure[i] = 1 if sens == 1 else 2
            sens = 1
            sh = np.nan
        elif not np.isnan(sl) and c[i] < sl:
            cassure[i] = -1 if sens == -1 else -2
            sens = -1
            sl = np.nan
        if not np.isnan(sh_vu) and not np.isnan(sl_vu):
            milieu[i] = (sh_vu + sl_vu) / 2
        if not np.isnan(eh) and h[i] > eh:
            egal_haut[i] = eh
            eh = np.nan
        if not np.isnan(el) and l[i] < el:
            egal_bas[i] = el
            el = np.nan
    return cassure, milieu, egal_haut, egal_bas


# ---------------------------------------------------------------------- zones
@njit(cache=True)
def order_blocks(o, h, l, c, atr):
    """OB : dernière bougie opposée (la suivante part dans l'autre sens) avant un départ >= 2 ATR en <= 3 bougies.
    Rend (haut, bas, sens, bougie de confirmation, bougie de l'OB)."""
    n = len(c)
    hs, bs = np.empty(n), np.empty(n)
    ss, cs, js = np.empty(n, np.int64), np.empty(n, np.int64), np.empty(n, np.int64)
    m_ = 0
    for j in range(n - 1):
        if c[j] < o[j] and c[j + 1] > o[j + 1]:
            m = -1.0
            for k in range(1, 4):
                if j + k >= n:
                    break
                m = max(m, h[j + k])
                if m - c[j] >= K_DEPART * atr[j]:
                    hs[m_], bs[m_], ss[m_], cs[m_], js[m_] = h[j], l[j], 1, j + k, j
                    m_ += 1
                    break
        elif c[j] > o[j] and c[j + 1] < o[j + 1]:
            m = 1e18
            for k in range(1, 4):
                if j + k >= n:
                    break
                m = min(m, l[j + k])
                if c[j] - m >= K_DEPART * atr[j]:
                    hs[m_], bs[m_], ss[m_], cs[m_], js[m_] = h[j], l[j], -1, j + k, j
                    m_ += 1
                    break
    return hs[:m_].copy(), bs[:m_].copy(), ss[:m_].copy(), cs[:m_].copy(), js[:m_].copy()


@njit(cache=True)
def fvgs(h, l, atr):
    """FVG : écart entre la mèche de la bougie i-2 et celle de la bougie i (>= 0,1 ATR), et bougie où il est comblé."""
    n = len(h)
    hs, bs = np.empty(n), np.empty(n)
    ss, cs = np.empty(n, np.int64), np.empty(n, np.int64)
    m = 0
    for i in range(2, n):
        if l[i] > h[i - 2] and l[i] - h[i - 2] >= FVG_MIN * atr[i]:
            hs[m], bs[m], ss[m], cs[m] = l[i], h[i - 2], 1, i
            m += 1
        elif h[i] < l[i - 2] and l[i - 2] - h[i] >= FVG_MIN * atr[i]:
            hs[m], bs[m], ss[m], cs[m] = l[i - 2], h[i], -1, i
            m += 1
    comble = np.full(m, n, np.int64)
    for z in range(m):
        for i in range(cs[z] + 1, n):
            if (ss[z] > 0 and l[i] <= bs[z]) or (ss[z] < 0 and h[i] >= hs[z]):
                comble[z] = i
                break
    return hs[:m].copy(), bs[:m].copy(), ss[:m].copy(), cs[:m].copy(), comble


@njit(cache=True)
def retournees(zh, zb, zs, zc, c):
    """Zone cassée en clôture de l'autre côté -> zone de sens inverse (inverse FVG, breaker). Rend l'index de la
    zone d'origine et la bougie de la cassure (= confirmation de la nouvelle zone)."""
    n = len(c)
    m = len(zc)
    idx, conf = np.empty(m, np.int64), np.empty(m, np.int64)
    k_ = 0
    for z in range(m):
        for i in range(zc[z] + 1, min(n, zc[z] + 1 + 500)):
            if (zs[z] > 0 and c[i] < zb[z]) or (zs[z] < 0 and c[i] > zh[z]):
                idx[k_], conf[k_] = z, i
                k_ += 1
                break
    return idx[:k_].copy(), conf[:k_].copy()


@njit(cache=True)
def zones_offre_demande(h, l, c, atr):
    """Base de 1 à 3 bougies (étendue <= 0,5 ATR) puis départ >= 2 ATR en <= 3 bougies. Rend aussi la bougie où la
    zone est invalidée (clôture au-delà du bord opposé)."""
    n = len(c)
    petite = (h - l) <= 0.5 * atr
    hs, bs = np.empty(n), np.empty(n)
    ss, cs, debs = np.empty(n, np.int64), np.empty(n, np.int64), np.empty(n, np.int64)
    m = 0
    for j in range(n - 1):
        if not petite[j] or petite[j + 1]:
            continue
        b = 1
        while b < 3 and j - b >= 0 and petite[j - b]:
            b += 1
        haut, bas = h[j - b + 1], l[j - b + 1]
        for k in range(j - b + 2, j + 1):
            haut = max(haut, h[k])
            bas = min(bas, l[k])
        mh, ml = -1.0, 1e18
        for k in range(1, 4):
            if j + k >= n:
                break
            mh = max(mh, h[j + k])
            ml = min(ml, l[j + k])
            if mh - haut >= K_DEPART * atr[j]:
                hs[m], bs[m], ss[m], cs[m], debs[m] = haut, bas, 1, j + k, j - b + 1
                m += 1
                break
            if bas - ml >= K_DEPART * atr[j]:
                hs[m], bs[m], ss[m], cs[m], debs[m] = haut, bas, -1, j + k, j - b + 1
                m += 1
                break
    fin = np.full(m, n, np.int64)
    for z in range(m):
        for i in range(cs[z] + 1, n):
            if (ss[z] > 0 and c[i] < bs[z]) or (ss[z] < 0 and c[i] > hs[z]):
                fin[z] = i
                break
    return hs[:m].copy(), bs[:m].copy(), ss[:m].copy(), cs[:m].copy(), debs[:m].copy(), fin

@njit(cache=True)
def volume_fort(zh, zb, zc, h, l, v, atr, x=200, top=0.2):
    """Zone touchant une tranche du top 20 % du volume profile des X bougies avant la confirmation."""
    m = len(zc)
    ok = np.zeros(m, np.bool_)
    for z in range(m):
        i0 = zc[z] - x
        if i0 < 0:
            continue
        pas = 0.25 * atr[zc[z]]
        if pas <= 0:
            continue
        bas_p = 1e18
        haut_p = -1e18
        for i in range(i0, zc[z]):
            bas_p = min(bas_p, l[i]); haut_p = max(haut_p, h[i])
        nb = int((haut_p - bas_p) / pas) + 1
        if nb <= 0 or nb > 5000:
            continue
        prof = np.zeros(nb)
        for i in range(i0, zc[z]):
            a = int((l[i] - bas_p) / pas)
            b = int((h[i] - bas_p) / pas)
            part = v[i] / (b - a + 1)
            for k in range(a, b + 1):
                prof[k] += part
        if prof.max() <= 0:
            continue
        seuil = np.quantile(prof, 1.0 - top)
        a = int((zb[z] - bas_p) / pas)
        b = int((zh[z] - bas_p) / pas)
        for k in range(max(a, 0), min(b, nb - 1) + 1):
            if prof[k] >= seuil and prof[k] > 0:
                ok[z] = True
                break
    return ok


# ---------------------------------------------------------------------- un trade et son jumeau
@njit(cache=True)
def _suivre(o, h, l, c, i0, sens, entree, stop, objectif, tenue, verifier_entree):
    """Suit une position à partir de la bougie i0 : (prix de sortie, stop touché, bougie). `verifier_entree` : la bougie
    i0 compte (entrée à son ouverture) ; sinon on commence à la suivante (bougie d'entrée déjà suivie à la minute)."""
    n = len(c)
    debut = i0 if verifier_entree else i0 + 1
    for i in range(debut, min(n, i0 + tenue + 1)):
        if (sens > 0 and l[i] <= stop) or (sens < 0 and h[i] >= stop):
            px = min(stop, o[i]) if sens > 0 else max(stop, o[i])
            return px, True, i
        if (sens > 0 and h[i] >= objectif) or (sens < 0 and l[i] <= objectif):
            px = max(objectif, o[i]) if sens > 0 else min(objectif, o[i])
            return px, False, i
    fin = min(n - 1, i0 + tenue)
    return c[fin], False, fin


@njit(cache=True)
def _minutes_de_la_bougie(mt, t_bougie, duree):
    a = np.searchsorted(mt, t_bougie)
    b = np.searchsorted(mt, t_bougie + duree)
    return a, b


# Glissement, en fiches (audit du 16/10, défaut 5) : stop touché +0,5 fiche (MESURÉ : 0,005 à 0,007 % sur 4 stops
# d'AUREX chez Tradeco) ; entrée au marché 0 (mesuré nul sur 11 ordres ; 0,5 jusqu'au 16/10, prudence non mesurée).
GLISSEMENT_STOP = 0.5
GLISSEMENT_MARCHE = 0.0


@njit(cache=True)
def _cout(entree, frais, facteur, touche, entree_marche):
    """Frais d'un trade en prix : demi-fiche à l'entrée (x facteur de l'écart de l'ouverture de New York, mesuré),
    demi-fiche à la sortie, + glissement du stop s'il est touché, + glissement d'une entrée au marché."""
    cout = entree * frais * (0.5 * facteur + 0.5)
    if touche:
        cout += GLISSEMENT_STOP * frais * entree
    if entree_marche:
        cout += GLISSEMENT_MARCHE * frais * entree
    return cout


@njit(cache=True)
def _resultat_limite(o, h, l, c, mt, mo, mh, ml, bt, duree, i0, f_min, b_min, sens, entree, risque, gain_vise, tenue,
                     frais, facteur):
    """Entrée par ordre limite rempli à la minute f_min de la bougie i0 : la suite de la bougie d'entrée est suivie
    MINUTE par MINUTE à partir de la minute suivante (ce qui s'est passé avant le remplissage ne compte pas, pour le
    trade comme pour son jumeau), puis bougie par bougie."""
    stop = entree - sens * risque
    objectif = entree + sens * gain_vise
    for k in range(f_min + 1, b_min):
        if (sens > 0 and ml[k] <= stop) or (sens < 0 and mh[k] >= stop):
            px = min(stop, mo[k]) if sens > 0 else max(stop, mo[k])
            return ((px - entree) * sens - _cout(entree, frais, facteur, True, False)) / risque, \
                _cout(entree, frais, facteur, True, False) / risque
        if (sens > 0 and mh[k] >= objectif) or (sens < 0 and ml[k] <= objectif):
            px = max(objectif, mo[k]) if sens > 0 else min(objectif, mo[k])
            return ((px - entree) * sens - _cout(entree, frais, facteur, False, False)) / risque, \
                _cout(entree, frais, facteur, False, False) / risque
    px, touche, _ = _suivre(o, h, l, c, i0, sens, entree, stop, objectif, tenue, False)
    cout = _cout(entree, frais, facteur, touche, False)
    return ((px - entree) * sens - cout) / risque, cout / risque


@njit(cache=True)
def _remplissage(o, mt, ml, mh, bt, duree, i, sens, proche):
    """Minute où l'ordre limite est rempli dans la bougie i (ou celle d'ouverture si la bougie ouvre déjà au-delà)."""
    a, b = _minutes_de_la_bougie(mt, bt[i], duree)
    if (sens > 0 and o[i] <= proche) or (sens < 0 and o[i] >= proche):
        return a, b
    for k in range(a, b):
        if (sens > 0 and ml[k] <= proche) or (sens < 0 and mh[k] >= proche):
            return k, b
    return b - 1, b


@njit(cache=True)
def trade_zone(o, h, l, c, atr, facteur, frais, mt, mo, mh, ml, bt, duree, haut, bas, sens, conf, marge, rr, tenue, vie):
    """Ordre limite au bord proche au 1er contact. Rend (bougie d'entrée ou -1, prix, R, R inverse, coût en R,
    stop en % du prix, réaction)."""
    n = len(c)
    proche = haut if sens > 0 else bas
    loin = bas if sens > 0 else haut
    a = atr[conf]
    for i in range(conf + 1, min(n, conf + 1 + vie)):
        touche = (l[i] <= proche) if sens > 0 else (h[i] >= proche)
        if touche:
            entree = proche
            if (sens > 0 and o[i] < proche) or (sens < 0 and o[i] > proche):
                entree = o[i]                       # ouverture déjà dans la zone : rempli à l'ouverture (mieux)
            stop = loin - sens * marge * a
            risque = (entree - stop) * sens
            if risque <= 0:
                return -1, 0.0, 0.0, 0.0, 0.0, 0.0, False
            f_min, b_min = _remplissage(o, mt, ml, mh, bt, duree, i, sens, proche)
            r, cr = _resultat_limite(o, h, l, c, mt, mo, mh, ml, bt, duree, i, f_min, b_min, sens, entree, risque,
                                     rr * risque, tenue, frais, facteur[i])
            r_inv, _ = _resultat_limite(o, h, l, c, mt, mo, mh, ml, bt, duree, i, f_min, b_min, -sens, entree, risque,
                                        rr * risque, tenue, frais, facteur[i])
            reac = False
            for k in range(i + 1, min(n, i + 48)):   # réaction mesurée à partir de la bougie suivante
                if (sens > 0 and h[k] >= proche + REACTION * a) or (sens < 0 and l[k] <= proche - REACTION * a):
                    reac = True
                    break
                if (sens > 0 and c[k] < loin) or (sens < 0 and c[k] > loin):
                    break
            return i, entree, r, r_inv, cr, risque / entree * 100, reac
        if (sens > 0 and c[i] < loin) or (sens < 0 and c[i] > loin):
            break
    return -1, 0.0, 0.0, 0.0, 0.0, 0.0, False

@njit(cache=True)
def reaction_zone(h, l, c, atr_ref, proche, loin, sens, depart, vie):
    """Pour les zones au hasard : (touchée ?, réaction ?) avec la même règle que trade_zone."""
    n = len(c)
    for i in range(depart + 1, min(n, depart + 1 + vie)):
        if (sens > 0 and l[i] <= proche) or (sens < 0 and h[i] >= proche):
            for k in range(i + 1, min(n, i + 48)):
                if (sens > 0 and h[k] >= proche + REACTION * atr_ref) or (sens < 0 and l[k] <= proche - REACTION * atr_ref):
                    return True, True
                if (sens > 0 and c[k] < loin) or (sens < 0 and c[k] > loin):
                    return True, False
            return True, False
        if (sens > 0 and c[i] < loin) or (sens < 0 and c[i] > loin):
            return False, False
    return False, False


@njit(cache=True)
def _resultat_marche(o, h, l, c, e, sens, entree, risque, gain_vise, tenue, frais, facteur):
    """Entrée au marché à l'ouverture de la bougie e : toute la bougie e vient après l'entrée."""
    px, touche, _ = _suivre(o, h, l, c, e, sens, entree, entree - sens * risque, entree + sens * gain_vise, tenue, True)
    cout = _cout(entree, frais, facteur, touche, True)
    return ((px - entree) * sens - cout) / risque, cout / risque


@njit(cache=True)
def trade_signal(o, h, l, c, atr, facteur, frais, i, sens, rr, tenue):
    """Entrée à l'ouverture suivante ; stop au-delà de l'extrême de la bougie du signal ± 0,2 ATR."""
    n = len(c)
    if i + 1 >= n:
        return -1, 0.0, 0.0, 0.0, 0.0, 0.0, False
    e = i + 1
    entree = o[e]
    stop = (l[i] - MARGE * atr[i]) if sens > 0 else (h[i] + MARGE * atr[i])
    risque = (entree - stop) * sens
    if risque <= 0:
        return -1, 0.0, 0.0, 0.0, 0.0, 0.0, False
    r, cr = _resultat_marche(o, h, l, c, e, sens, entree, risque, rr * risque, tenue, frais, facteur[e])
    r_inv, _ = _resultat_marche(o, h, l, c, e, -sens, entree, risque, rr * risque, tenue, frais, facteur[e])
    return e, entree, r, r_inv, cr, risque / entree * 100, reaction_signal(h, l, atr, e, sens, entree)


@njit(cache=True)
def reaction_signal(h, l, atr, e, sens, entree):
    n = len(h)
    a = atr[e - 1] if e >= 1 else atr[e]
    for k in range(e, min(n, e + 48)):
        up = h[k] >= entree + REACTION * a
        dn = l[k] <= entree - REACTION * a
        if sens > 0:
            if dn:
                return False
            if up:
                return True
        else:
            if up:
                return False
            if dn:
                return True
    return False


# ---------------------------------------------------------------------- la stratégie personnelle
@njit(cache=True)
def trade_perso(o, h, l, c, atr, facteur, frais, mt, mo, mh, ml, bt, duree, z, zh, zb, zs, zc, zfin, fh, fb, fc, fcomble,
                contact, filtre_fvg, marge, vie):
    """Zone z (offre / demande à volume fort) : trade à la `contact`-ième entrée dans la zone (après contact-1
    contacts réussis : sortie >= 0,5 ATR dans le sens du rebond) ; filtre FVG ; objectif = bord de la plus proche zone
    opposée valide (gain / risque >= 1,5). Rend (bougie, prix, R, R inverse, coût R, stop %, réaction, raison)
    raison : 0 trade, 1 jamais atteint, 2 filtre FVG, 3 pas d'objectif / ratio < 1,5."""
    n = len(c)
    sens = zs[z]
    haut, bas = zh[z], zb[z]
    proche = haut if sens > 0 else bas
    loin = bas if sens > 0 else haut
    a = atr[zc[z]]
    dedans = False
    entrees = 0
    for i in range(zc[z] + 1, min(n, zc[z] + 1 + vie)):
        touche = (l[i] <= proche) if sens > 0 else (h[i] >= proche)
        if not dedans and touche:
            entrees += 1
            dedans = True
            if entrees == contact:
                entree = proche
                if (sens > 0 and o[i] < proche) or (sens < 0 and o[i] > proche):
                    entree = o[i]
                if filtre_fvg:                       # FVG non comblés confirmés dans les 5 000 bougies précédentes
                    f_fin = np.searchsorted(fc, i)
                    f_debut = np.searchsorted(fc, i - 5000)
                    for f in range(f_debut, f_fin):
                        if fc[f] < i and fcomble[f] > i:
                            if sens > 0 and fh[f] <= bas and bas - fh[f] <= a:
                                return -1, 0.0, 0.0, 0.0, 0.0, 0.0, False, 2
                            if sens < 0 and fb[f] >= haut and fb[f] - haut <= a:
                                return -1, 0.0, 0.0, 0.0, 0.0, 0.0, False, 2
                stop = loin - sens * marge * a
                risque = (entree - stop) * sens
                if risque <= 0:
                    return -1, 0.0, 0.0, 0.0, 0.0, 0.0, False, 3
                cible = np.nan
                for y in range(len(zc)):
                    if zs[y] == -sens and zc[y] < i and zfin[y] > i:
                        bord = zb[y] if sens > 0 else zh[y]
                        if (bord - entree) * sens > 0:
                            if np.isnan(cible) or (bord - entree) * sens < (cible - entree) * sens:
                                cible = bord
                if np.isnan(cible) or (cible - entree) * sens < 1.5 * risque:
                    return -1, 0.0, 0.0, 0.0, 0.0, 0.0, False, 3
                gain = (cible - entree) * sens
                f_min, b_min = _remplissage(o, mt, ml, mh, bt, duree, i, sens, proche)
                r, cr = _resultat_limite(o, h, l, c, mt, mo, mh, ml, bt, duree, i, f_min, b_min, sens, entree, risque,
                                         gain, vie, frais, facteur[i])
                r_inv, _ = _resultat_limite(o, h, l, c, mt, mo, mh, ml, bt, duree, i, f_min, b_min, -sens, entree,
                                            risque, gain, vie, frais, facteur[i])
                reac = False
                for k in range(i + 1, min(n, i + 48)):
                    if (sens > 0 and h[k] >= proche + 1.0 * a) or (sens < 0 and l[k] <= proche - 1.0 * a):
                        reac = True
                        break
                    if (sens > 0 and c[k] < loin) or (sens < 0 and c[k] > loin):
                        break
                return i, entree, r, r_inv, cr, risque / entree * 100, reac, 0
        if dedans and ((sens > 0 and h[i] >= proche + 0.5 * a) or (sens < 0 and l[i] <= proche - 0.5 * a)):
            dedans = False                           # contact réussi : il en sort de 0,5 ATR dans le sens du rebond
        if (sens > 0 and c[i] < loin) or (sens < 0 and c[i] > loin):
            break
    return -1, 0.0, 0.0, 0.0, 0.0, 0.0, False, 1
