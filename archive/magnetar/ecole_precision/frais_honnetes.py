"""FRAIS HONNÊTES de l'or (20/10/2026, corrections graves de l'audit de MAGNETAR, ordre du chef de projet) — réglage
`frais_honnetes` de reglages_or.yaml SEULEMENT ; HYPERNOVA n'en a pas : rien ne change pour lui.

Avant : un seul écart, relevé une fois sur le compte d'essai FTMO (15/10/2026, 03h34 serveur = séance d'Asie,
mains/conditions_ftmo.json : 0,0111 % du prix), appliqué à toute heure et pendant les annonces ; glissement d'un stop =
un demi-écart, partout.

Ce que le projet a mesuré (sources) :
- FTMO, séance d'Asie (15/10 03h34 serveur) : 0,0111 % (le seul relevé FTMO) -> reste la BASE à toute heure ;
- Tradeco, Londres + New York (16/10 15h30 -> 22h00 Paris, 91 relevés, vie/releves/ecarts_tradeco_20261016.json) :
  écart de l'or très stable (10e / 90e centiles à ±5 % de la médiane), « facteur d'ouverture » de New York = 1,00 (le
  premier quart d'heure de New York n'est pas plus cher) ; ce relevé est d'un autre courtier, il ne permet donc PAS de
  baisser l'écart FTMO de Londres / New York : on garde la base (prudent) ;
- bougies de l'or (minute, 2016-2023) : AUCUNE colonne d'écart ; essai de l'estimer par le rebond des prix
  (corrections_graves/ecart_heures.md) : rien d'exploitable (les prix sont ceux d'un seul côté).
Rien dans le projet ne mesure l'écart à la réouverture quotidienne ni pendant une annonce : les facteurs ci-dessous
sont des HYPOTHÈSES PRUDENTES (connues des traders : l'écart de l'or s'ouvre fortement à la réouverture et pendant
les grandes annonces américaines), écrites dans les réglages pour être changées dès qu'un relevé existera
(surveillance/releve_ecarts.py, séance de nuit ou d'annonce).

Modèle (multiplie le demi-écart de chaque bougie de 15 min, donc tout ce qui le paie : entrée et sortie au marché,
stop + son glissement, et le seuil d'un ordre limite / objectif) :
- `reouverture` : 1re bougie après une pause du marché (> 20 min : pause quotidienne, week-end) ;
- `avant_pause` : dernière bougie avant une pause ;
- `annonce` : bougie(s) de 15 min qui touchent la fenêtre [annonce - minutes_avant, annonce + minutes_apres) d'une
  annonce 3 étoiles des devises `annonce_devises` (calendrier MetaTrader, heure du serveur, yeux/faits.annonces_importantes).
  Le stop qui part dans cette bougie paie donc (1 + glissement) x annonce demi-écarts au lieu de (1 + glissement).
Pas de futur : un facteur ne dépend que de l'heure de la bougie (le calendrier est connu à l'avance) ; ce qu'elle voit
du demi-écart (yeux) est celui de la bougie CLOSE, jamais celui de la bougie qui vient.
"""
from __future__ import annotations

import numpy as np

QUINZE_NS = 15 * 60 * 10 ** 9
PAUSE_NS = 20 * 60 * 10 ** 9


def _annonces_ns(devises) -> np.ndarray:
    from collapsar.yeux.faits import annonces_importantes
    a = annonces_importantes()
    a = a[a["devise"].isin(list(devises))]
    return np.sort(a["temps"].values.astype("datetime64[ns]").astype(np.int64))


def facteurs(t_ns: np.ndarray, ouvert: np.ndarray, fh, annonces_ns: np.ndarray | None = None) -> tuple[np.ndarray, dict]:
    """[T, M] facteurs du demi-écart et un petit bilan {réouvertures, avant pause, bougies d'annonce} (en bougies)."""
    t_ns = np.asarray(t_ns, np.int64)
    T, M = ouvert.shape
    f = np.ones((T, M))
    bil = {"reouverture": 0, "avant_pause": 0, "annonce": 0}
    k_re = float(getattr(fh, "reouverture", 1.0))
    k_av = float(getattr(fh, "avant_pause", 1.0))
    k_an = float(getattr(fh, "annonce", 1.0))
    for j in range(M):
        o = np.flatnonzero(np.asarray(ouvert[:, j], bool))
        if len(o) < 2:
            continue
        tt = t_ns[o]
        d = np.diff(tt)
        re = o[np.r_[False, d > PAUSE_NS]]
        av = o[np.r_[d > PAUSE_NS, False]]
        f[re, j] *= k_re
        f[av, j] *= k_av
        bil["reouverture"] += len(re)
        bil["avant_pause"] += len(av)
    if k_an != 1.0:
        a = _annonces_ns(getattr(fh, "annonce_devises", ["USD"])) if annonces_ns is None else np.sort(np.asarray(annonces_ns, np.int64))
        av_ns = int(float(getattr(fh, "minutes_avant", 0)) * 60e9)
        ap_ns = int(float(getattr(fh, "minutes_apres", 15)) * 60e9)
        # bougie n = [t_n, t_n + 15 min) ; touchée si elle coupe [a - avant, a + après)
        k = np.searchsorted(a, t_ns + QUINZE_NS + av_ns, side="left")       # annonces avec a - avant < t_n + 15 min
        k0 = np.searchsorted(a, t_ns - ap_ns, side="right")                 # annonces avec a + après > t_n
        touche = k > k0
        f[touche, :] *= k_an
        bil["annonce"] = int(touche.sum())
    return f, bil


def appliquer(U, fh) -> dict:
    """Multiplie U.demi (avant que les yeux ne le rangent sur la carte) ; rend le bilan."""
    f, bil = facteurs(U.t_ns, U.ouvert, fh)
    U.demi = U.demi * f
    U.facteur_frais = f
    return bil
