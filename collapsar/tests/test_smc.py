"""Le laboratoire SMC (regarder/smc) : définitions figées, sans futur, trades et jumeau (15/10/2026)."""
import numpy as np
import pytest

from collapsar.regarder.smc import noyaux as K


def _marche(n=3000, graine=0):
    r = np.random.default_rng(graine).normal(0, 0.002, n)
    c = 100 * np.exp(np.cumsum(r))
    o = np.r_[c[0], c[:-1]]
    h = np.maximum(o, c) * (1 + np.abs(np.random.default_rng(graine + 1).normal(0, 0.001, n)))
    l = np.minimum(o, c) * (1 - np.abs(np.random.default_rng(graine + 2).normal(0, 0.001, n)))
    tr = np.maximum(h - l, np.maximum(np.abs(h - np.r_[c[0], c[:-1]]), np.abs(l - np.r_[c[0], c[:-1]])))
    atr = np.convolve(tr, np.ones(14) / 14, "full")[:n]
    return o, h, l, c, atr


def test_rien_ne_depend_du_futur():
    o, h, l, c, atr = _marche()
    coupe = 2000
    for f in (lambda *a: K.order_blocks(*a), ):
        plein = f(o, h, l, c, atr)
        court = f(o[:coupe], h[:coupe], l[:coupe], c[:coupe], atr[:coupe])
        ok_plein = plein[3] < coupe
        assert np.array_equal(plein[3][ok_plein], court[3]), "les OB confirmés avant la coupe ne changent pas"
    fp, fc_ = K.fvgs(h, l, atr), K.fvgs(h[:coupe], l[:coupe], atr[:coupe])
    assert np.array_equal(fp[3][fp[3] < coupe], fc_[3])
    sp = K.structure(h, l, c, atr)
    sc = K.structure(h[:coupe], l[:coupe], c[:coupe], atr[:coupe])
    assert np.array_equal(sp[0][:coupe], sc[0]) and np.allclose(sp[1][:coupe], sc[1], equal_nan=True)
    zp = K.zones_offre_demande(h, l, c, atr)
    zc = K.zones_offre_demande(h[:coupe], l[:coupe], c[:coupe], atr[:coupe])
    assert np.array_equal(zp[3][zp[3] < coupe], zc[3])


def test_fvg_haussier():
    h = np.array([10.0, 10.5, 11.0, 12.0, 12.5])
    l = np.array([9.5, 10.0, 10.8, 11.2, 12.1])
    atr = np.full(5, 1.0)
    fh, fb, fs, fc, comble = K.fvgs(h, l, atr)
    assert fs[0] == 1 and fb[0] == 10.0 and fh[0] == 10.8 and fc[0] == 2


def test_trade_zone_gagne_2R_puis_jumeau_perd():
    n = 200
    c = np.r_[np.full(10, 105.0), np.linspace(105, 100.05, 10), np.linspace(100.2, 120, n - 20)]
    o = np.r_[c[0], c[:-1]]
    h, l = np.maximum(o, c) + 0.05, np.minimum(o, c) - 0.05
    atr = np.full(n, 1.0)
    fct = np.ones(n)
    mt = np.arange(n, dtype=np.int64)               # une « minute » par bougie
    e, px, r, ri, cr, sp, reac = K.trade_zone(o, h, l, c, atr, fct, 0.0, mt, o, h, l, mt, 1, 101.0, 100.0, 1, 5, 0.2,
                                              2.0, 48, 500)
    assert e > 0 and px == 101.0 and r == pytest.approx(2.0, abs=0.05) and ri == pytest.approx(-1.0, abs=0.05)
    assert reac


def test_volume_profile_et_contacts():
    o, h, l, c, atr = _marche(4000, 3)
    v = np.ones(len(c))
    zh, zb, zs, zc, zdeb, zfin = K.zones_offre_demande(h, l, c, atr)
    fort = K.volume_fort(zh, zb, zc, h, l, v, atr)
    assert len(zc) > 10 and 0 < fort.sum() <= len(zc)
    fh, fb, fs, fc, fcom = K.fvgs(h, l, atr)
    vus = {1: 0, 2: 0, 3: 0}
    for z in np.flatnonzero(fort):
        for contact in (1, 2, 3):
            mt = np.arange(len(c), dtype=np.int64)
            res = K.trade_perso(o, h, l, c, atr, np.ones(len(c)), 0.0001, mt, o, h, l, mt, 1, int(z), zh, zb, zs, zc,
                                zfin, fh, fb, fc, fcom, contact, False, 0.2, 500)
            vus[contact] += res[0] >= 0
    assert vus[1] >= vus[2] >= vus[3], "il y a moins de 2es contacts que de 1ers"


def test_le_jumeau_n_est_pas_puni_par_ce_qui_precede_le_remplissage():
    """Une bougie « d'une heure » descend de 103,4 dans la zone (bord 101) : son plus haut est AVANT l'entrée. Suivi
    à la minute, le jumeau vendeur (stop à 102,2) n'est pas stoppé par ce plus haut."""
    n = 60
    c = np.r_[np.full(20, 104.0), np.full(n - 20, 100.9)]
    o = np.r_[c[0], c[:-1]]
    h, l = np.maximum(o, c) + 0.05, np.minimum(o, c) - 0.05
    atr = np.full(n, 1.0)
    bt = np.arange(n, dtype=np.int64) * 60
    mt = np.arange(n * 60, dtype=np.int64)
    mo = np.repeat(c, 60).astype(float)
    mo[20 * 60:20 * 60 + 30] = np.linspace(103.4, 101.2, 30)       # la descente avant le remplissage
    mh, ml = mo + 0.01, mo - 0.01
    e, px, r, ri, cr, sp, reac = K.trade_zone(o, h, l, c, atr, np.ones(n), 0.0, mt, mo, mh, ml, bt, 60, 101.0, 100.0,
                                              1, 10, 0.2, 2.0, 48, 500)
    assert e == 20 and ri > -1.0, "le plus haut d'avant l'entrée ne stoppe pas le jumeau"
