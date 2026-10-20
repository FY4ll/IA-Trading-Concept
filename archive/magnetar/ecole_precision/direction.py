"""LES PROPOSITIONS DE DIRECTION de l'arbre HYPERNOVA (17/10/2026, chef de projet : « la précision vient de ses zones,
la DIRECTION doit venir des sources qui ont fait leurs preuves dans le projet »). Ce sont des INFORMATIONS données à
l'IA, jamais des règles : elle apprend seule si et quand s'en servir.

Trois sources, calculées SANS FUTUR à chaque instant de décision (heure du serveur = New York + 7 h, clôture d'une
bougie de 15 min) :
1. TENDANCE DE FOND (tous les marchés) : signe de la clôture du dernier jour TERMINÉ moins celle d'il y a 20 / 60 / 120
   jours de cotation (même définition que regarder/smc/filtre_tendance.py) ; et sa FORCE pour les yeux : rendement
   logarithmique / (agitation journalière des 60 derniers jours x racine(N)), bornée à +-3.
2. CASSURE 24 H (C2, bitcoin et ether seulement, regarder/pistes/bitcoin_journee.var_C N = 24) : à chaque heure pleine
   du lundi au vendredi (serveur), clôture de l'heure > plus haut des 24 heures de cotation précédentes -> achat
   (< plus bas -> vente) ; sortie au retour au milieu du canal ou à 23h45 ; nouvelle entrée jusqu'à 22h. Proposition =
   le sens de la cassure EN COURS (0 sinon). Version recalculée heure par heure (une heure sans bougie = dernier prix
   connu) : aucune journée n'est jugée « complète » à l'avance (l'original écarte les jours de moins de 92 bougies, ce
   qui demande de connaître la fin du jour).
3. CONTRE LA FOULE (C1, cryptos, regarder/pistes/crypto_flux.py) : part des comptes acheteurs Binance (ligne connue 15
   min après son heure) au-dessus de son centile 95 des 90 jours précédents -> vente pendant 24 h, sous le centile 5 ->
   achat pendant 24 h (un nouveau signal n'est pris qu'à la fin des 24 h). Proposition = le sens du signal EN COURS.
Rien n'est lu à partir de reglages.periodes.fin_donnees (12 mois cachés). Testé : calcul coupé à t = calcul complet
(tests/test_direction.py).
"""
from __future__ import annotations

from functools import lru_cache

import numpy as np
import pandas as pd

from collapsar.ecole.precision import donnees as D
from collapsar.ecole.precision.reglages import R

JOUR_NS = 86400 * 10 ** 9
HEURE_NS = 3600 * 10 ** 9
DUREES = (20, 60, 120)
JOURS_AGIT = 60
C2_MARCHES = ("BTCUSDT", "ETHUSDT")
C2_N = 24
C2_FIN_MIN = 1425                       # 23h45 serveur
C1_FENETRE = 90 * 24                    # heures
C1_TENUE = 24                           # heures
C1_RETARD = 15 * 60 * 10 ** 9           # une ligne « metrics » n'est connue que 15 min après son heure


# ============================================================================================== 1. tendance de fond
def clotures_jour(t15_ns: np.ndarray, close: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """(début de chaque jour serveur, dernière clôture du jour) à partir de bougies de 15 min (ouverture, ns)."""
    t15_ns = np.asarray(t15_ns, np.int64)
    jour = t15_ns - t15_ns % JOUR_NS
    fin = np.r_[jour[1:] != jour[:-1], True]
    return jour[fin], np.asarray(close, np.float64)[fin]


def tendance_aux(jours: np.ndarray, clo: np.ndarray, t_ns: np.ndarray, durees=DUREES) -> tuple[np.ndarray, np.ndarray]:
    """Signes [n, len(durees)] et forces [n, len(durees)] à chaque instant t (serveur, ns) : seuls les jours TERMINÉS
    avant le jour de t comptent (le jour de t n'est jamais regardé)."""
    t_ns = np.asarray(t_ns, np.int64)
    k = np.searchsorted(jours, t_ns - t_ns % JOUR_NS) - 1          # dernier jour fermé avant le jour de t
    lr = np.log(clo)
    r1 = np.r_[np.nan, np.diff(lr)]
    sd = pd.Series(r1).rolling(JOURS_AGIT, min_periods=JOURS_AGIT // 2).std().to_numpy()
    signes = np.zeros((len(t_ns), len(durees)), np.int8)
    forces = np.zeros((len(t_ns), len(durees)), np.float32)
    for i, n in enumerate(durees):
        ok = k - n >= 0
        kk = np.clip(k, 0, None)
        d = np.where(ok, lr[kk] - lr[np.clip(k - n, 0, None)], np.nan)
        signes[:, i] = np.where(ok, np.sign(d), 0).astype(np.int8)
        s = sd[kk]
        f = np.where(ok & np.isfinite(s) & (s > 0), d / np.where(s > 0, s, 1.0) / np.sqrt(n), 0.0)
        forces[:, i] = np.clip(np.nan_to_num(f), -3, 3)
    return signes, forces


@lru_cache(maxsize=128)
def _jours(nom: str) -> tuple[np.ndarray, np.ndarray]:
    df = D.quinze(nom)
    return clotures_jour(df["time"].values.astype("datetime64[ns]").astype(np.int64), df["close"].to_numpy(float))


def tendance(nom: str, t_ns: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    return tendance_aux(*_jours(nom), t_ns)


# ============================================================================================== 2. cassure 24 h (C2)
def c2_intervalles(t15_ns: np.ndarray, h15, l15, c15, n: int = C2_N) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """(début, fin, sens) des cassures 24 h (bitcoin_journee.var_C) à partir de bougies de 15 min (ouverture, serveur).
    Heures des jours lun-ven mises bout à bout ; une heure sans bougie = dernier prix connu (rien du futur)."""
    t = np.asarray(t15_ns, np.int64)
    heure = t - t % HEURE_NS
    jour = t - t % JOUR_NS
    dow = ((jour // JOUR_NS) + 3) % 7                                # 1970-01-01 = jeudi -> lundi = 0
    ok = dow < 5
    if not ok.any():
        z = np.zeros(0, np.int64)
        return z, z, z.astype(np.int8)
    t, heure, jour = t[ok], heure[ok], jour[ok]
    h15, l15, c15 = (np.asarray(x, np.float64)[ok] for x in (h15, l15, c15))
    jours = np.unique(jour)
    ij = np.searchsorted(jours, jour)
    ih = (heure - jour) // HEURE_NS
    g = ij * 24 + ih
    G = len(jours) * 24
    H = np.full(G, -np.inf)
    L = np.full(G, np.inf)
    C = np.full(G, np.nan)
    np.maximum.at(H, g, h15)
    np.minimum.at(L, g, l15)
    o = np.lexsort((t, g))
    go = g[o]
    der = np.r_[go[1:] != go[:-1], True]                              # dernière bougie de chaque heure
    C[go[der]] = c15[o][der]
    vide = ~np.isfinite(C)
    C = pd.Series(C).ffill().to_numpy()
    H = np.where(vide, C, H)
    L = np.where(vide, C, L)
    haut = pd.Series(H).rolling(n).max().shift(1).to_numpy()
    bas = pd.Series(L).rolling(n).min().shift(1).to_numpy()
    deb, fin, sens = [], [], []
    for j in range(len(jours)):
        pos, m_in = 0, 0
        for h in range(1, 24):
            gg = j * 24 + h - 1
            if not (np.isfinite(haut[gg]) and np.isfinite(bas[gg]) and np.isfinite(C[gg])):
                continue
            c, mil = C[gg], (haut[gg] + bas[gg]) / 2
            if (pos > 0 and c < mil) or (pos < 0 and c > mil):
                deb.append(jours[j] + m_in * 60 * 10 ** 9)
                fin.append(jours[j] + h * HEURE_NS)
                sens.append(pos)
                pos = 0
            if pos == 0 and h <= 22:
                if c > haut[gg]:
                    pos, m_in = 1, h * 60
                elif c < bas[gg]:
                    pos, m_in = -1, h * 60
        if pos != 0:
            deb.append(jours[j] + m_in * 60 * 10 ** 9)
            fin.append(jours[j] + C2_FIN_MIN * 60 * 10 ** 9)
            sens.append(pos)
    return np.asarray(deb, np.int64), np.asarray(fin, np.int64), np.asarray(sens, np.int8)


def en_cours(deb: np.ndarray, fin: np.ndarray, sens: np.ndarray, t_ns: np.ndarray) -> np.ndarray:
    """Sens de l'intervalle [début, fin) qui contient t (0 sinon). Intervalles triés, sans chevauchement."""
    t_ns = np.asarray(t_ns, np.int64)
    if not len(deb):
        return np.zeros(len(t_ns), np.int8)
    i = np.searchsorted(deb, t_ns, side="right") - 1
    ii = np.clip(i, 0, None)
    return np.where((i >= 0) & (t_ns < fin[ii]), sens[ii], 0).astype(np.int8)


@lru_cache(maxsize=8)
def _c2(nom: str):
    df = D.quinze(nom)
    return c2_intervalles(df["time"].values.astype("datetime64[ns]").astype(np.int64), df["high"].to_numpy(float),
                          df["low"].to_numpy(float), df["close"].to_numpy(float))


def c2(nom: str, t_ns: np.ndarray) -> np.ndarray:
    """Proposition C2 à chaque instant (serveur, ns) : sens de la cassure 24 h en cours (bitcoin et ether), 0 sinon."""
    if nom not in C2_MARCHES:
        return np.zeros(len(t_ns), np.int8)
    return en_cours(*_c2(nom), t_ns)


# ============================================================================================== 3. contre la foule (C1)
def c1_intervalles(connu_ns: np.ndarray, ratio: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """(début, fin, sens) des signaux C1 (crypto_flux) sur une grille horaire UTC, à partir des lignes « metrics »
    (instant où chacune devient connue, ratio comptes acheteurs / vendeurs)."""
    connu_ns = np.asarray(connu_ns, np.int64)
    ratio = np.asarray(ratio, np.float64)
    k = np.isfinite(ratio) & (ratio > 0)
    connu_ns, ratio = connu_ns[k], ratio[k]
    if len(connu_ns) < 2:
        z = np.zeros(0, np.int64)
        return z, z, z.astype(np.int8)
    o = np.argsort(connu_ns, kind="stable")
    connu_ns, ratio = connu_ns[o], ratio[o]
    g0 = (connu_ns[0] // HEURE_NS + 1) * HEURE_NS
    grille = np.arange(g0, connu_ns[-1] + 1, HEURE_NS, dtype=np.int64)
    i = np.searchsorted(connu_ns, grille, side="right") - 1
    ok = (i >= 0) & (grille - connu_ns[np.clip(i, 0, None)] <= HEURE_NS)
    c = pd.Series(np.where(ok, ratio[np.clip(i, 0, None)], np.nan))
    prec = c.shift(1).rolling(C1_FENETRE, min_periods=C1_FENETRE // 3)
    c05, c95 = prec.quantile(0.05).to_numpy(), prec.quantile(0.95).to_numpy()
    cv = c.to_numpy()
    achat = (cv <= c05) & np.isfinite(cv) & np.isfinite(c05)          # une comparaison à NaN est fausse
    vente = (cv >= c95) & np.isfinite(cv) & np.isfinite(c95)
    s = np.where(achat & ~vente, 1, np.where(vente & ~achat, -1, 0))
    deb, sens = [], []
    libre = 0
    for j in np.flatnonzero(s):
        if j < libre:
            continue
        deb.append(grille[j])
        sens.append(s[j])
        libre = j + C1_TENUE
    deb = np.asarray(deb, np.int64)
    return deb, deb + C1_TENUE * HEURE_NS, np.asarray(sens, np.int8)


@lru_cache(maxsize=32)
def _c1(nom: str):
    from collapsar.ecole.precision import foule as FO
    f = FO.FUT / "metrics" / f"{nom}.csv"
    if not f.exists():
        z = np.zeros(0, np.int64)
        return z, z, z.astype(np.int8)
    m = pd.read_csv(f, usecols=["utc_ms", "count_long_short_ratio"])
    connu = m["utc_ms"].to_numpy(np.int64) * 1_000_000 + C1_RETARD
    k = connu < FO._fin_utc_ns()                                       # rien après fin_donnees
    return c1_intervalles(connu[k], m["count_long_short_ratio"].to_numpy(float)[k])


def c1(nom: str, t_ns: np.ndarray) -> np.ndarray:
    """Proposition C1 à chaque instant (serveur, ns) : sens du signal « contre la foule » en cours (cryptos), 0 sinon."""
    if nom not in tuple(R().marches.cryptos_binance):
        return np.zeros(len(t_ns), np.int8)
    from collapsar.ecole.precision import foule as FO
    return en_cours(*_c1(nom), FO.serveur_vers_utc_ns(pd.DatetimeIndex(np.asarray(t_ns, np.int64).astype("datetime64[ns]"))))


# ============================================================================================== toutes ensemble
NOMS = ("t20", "t60", "t120", "c2", "c1")


def signes(nom: str, t_ns: np.ndarray) -> np.ndarray:
    """[n, 5] : sens proposé par chaque source à chaque instant (serveur, ns) : t20, t60, t120, c2, c1 (0 = rien)."""
    s, _ = tendance(nom, t_ns)
    return np.concatenate([s, c2(nom, t_ns)[:, None], c1(nom, t_ns)[:, None]], 1).astype(np.int8)
