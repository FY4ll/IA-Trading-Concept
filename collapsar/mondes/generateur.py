"""Le générateur de l'ÉCOLE DES MILLE MONDES (validée par le chef de projet le 14/10/2026 au soir).

Chaque monde = quelques marchés inventés, avec des LOIS CACHÉES tirées au hasard, qui changent en cours de route. Elle
ne sait jamais dans quel monde elle est : son métier est de deviner quelle loi gouverne le marché maintenant, d'en
profiter, et de se retirer quand il n'y a rien (« chercher l'avantage comme un joueur de poker »).

Les lois viennent de la recherche en finance (pas de dessins de trader) :
- agitation en vagues (Engle, Nobel 2003) : l'agitation d'un jour suit une marche lente, avec des chocs ;
- queues épaisses : les variations suivent une loi de Student (grosses bougies plus fréquentes qu'en cloche) ;
- rythme de la journée : séances d'Asie, de Londres, de New York (agitation plus forte aux ouvertures) ;
- RÉGIMES (Hamilton 1989), chacun avec sa durée moyenne, qui se succèdent au hasard :
    * « rien » : aucun avantage (le hasard pur, frais compris : il faut s'abstenir) ;
    * « tendance » (Moskowitz, Ooi, Pedersen 2012) : le prix dérive dans un sens pendant des jours ou des semaines ;
    * « retour au calme » : le prix est rappelé vers un niveau qui bouge lentement ;
- annonces : à heures fixes certains jours, un saut de prix, parfois prolongé dans les heures suivantes ;
- un FACTEUR COMMUN (comme le dollar) : tous les marchés du monde y sont plus ou moins liés, et la tendance peut
  vivre dans ce facteur (elle touche alors tous les marchés à la fois).
Chaque monde a ses réglages tirés au hasard ; beaucoup de mondes n'ont presque aucun avantage, comme la réalité.
On garde la VÉRITÉ (régime, dérive cachée) : elle sert à noter l'école (« part du gagnable capturée »).
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

BOUGIES_JOUR = 96
# rythme de la journée (heure serveur = New York + 7) : calme la nuit d'Asie, ouverture de Londres (~10h serveur),
# chevauchement Londres-New York (~15h-18h serveur), calme en fin de soirée
_RYTHME = np.array([0.55, 0.5, 0.55, 0.6, 0.65, 0.65, 0.6, 0.6, 0.7, 0.9, 1.3, 1.35, 1.2, 1.1, 1.15, 1.5, 1.75,
                    1.6, 1.3, 1.05, 0.9, 0.75, 0.65, 0.6])


@dataclass
class Lois:
    """Les réglages cachés d'un monde (tirés par `tirer_lois`)."""
    marches: int
    agitation_jour: np.ndarray            # [M] agitation moyenne d'un jour (part du prix)
    persistance_agitation: float          # 0,90 -> 0,995 : les vagues durent plus ou moins longtemps
    choc_agitation: float                 # taille des chocs sur l'agitation
    queues: float                         # degrés de liberté de Student (3 = très épais, 30 = presque en cloche)
    force_rythme: float                   # 0 = pas de rythme de journée, 1 = rythme type, 2,5 = indices très marqués
    vague_lente: float                    # taille de la vague d'agitation LENTE (années agitées comme 2020)
    rebond: float                         # petit rebond d'une bougie sur l'autre (achat-vente), 0 -> 0,08
    sauts_par_mois: float                 # nouvelles imprévues : sauts brusques RARES (14/10 : 0,1 -> 2 par mois ;
                                          # jusqu'à 20 rendait les mondes bien plus violents que le réel)
    taille_saut: float                    # en agitations de 15 minutes
    lien_facteur: np.ndarray              # [M] lien de chaque marché au facteur commun (-1 -> 1)
    part_facteur: float                   # part de l'agitation qui vient du facteur commun
    duree_regimes_jours: dict             # durée moyenne de chaque régime
    probas_regimes: dict                  # fréquence de chaque régime
    force_tendance: float                 # dérive par jour, en part de l'agitation d'un jour
    tendance_dans_facteur: bool           # la tendance touche tous les marchés via le facteur commun
    demi_vie_retour_jours: float          # mémoire du niveau de référence du retour au calme (jours)
    force_retour: float                   # part de l'écart au niveau effacée chaque jour
    annonces_par_semaine: float
    taille_annonce: float                 # saut, en agitations de 15 minutes
    suite_annonce: float                  # part du saut qui se prolonge dans les heures suivantes
    # « démarrages » (15/10/2026, le terrain des trades à 10R) : après un calme, un mouvement fort démarre d'un coup
    # (un quart du mouvement dans la première heure) puis se prolonge (élan après le début d'un fort mouvement :
    # Gao et al. 2018, Baltussen et al. 2021 ; l'agitation qui sort d'une période calme)
    explosions_par_mois: float = 0.0
    force_explosion: float = 0.0          # taille totale du mouvement, en agitations d'un jour
    duree_explosion_jours: float = 1.0
    graine: int = 0
    infos: dict = field(default_factory=dict)


def tirer_lois(rng: np.random.Generator, marches: int = 4, intensite: float = 1.0) -> Lois:
    """`intensite` : force des lois qui donnent un avantage (tendance, retour au calme). 1 = exercices faciles du début
    d'école ; autour de 0,3-0,4, les mondes sont aussi durs que les vrais marchés (mesuré le 14/10, voir
    `mondes/verifier.py`)."""
    agit = np.exp(rng.uniform(np.log(0.003), np.log(0.025), marches))
    regimes = ("rien", "tendance", "retour")
    poids = rng.dirichlet([2.0, 1.0, 1.0])
    if rng.random() < 0.3:                                   # 30 % des mondes : rien du tout à gagner
        poids = np.array([1.0, 0.0, 0.0])
    return Lois(
        marches=marches, agitation_jour=agit,
        persistance_agitation=float(rng.uniform(0.90, 0.995)), choc_agitation=float(rng.uniform(0.05, 0.25)),
        queues=float(np.exp(rng.uniform(np.log(3.0), np.log(30.0)))), force_rythme=float(rng.uniform(0.0, 2.5)),
        vague_lente=float(rng.uniform(0.0, 0.5)), rebond=float(rng.uniform(0.0, 0.08)),
        sauts_par_mois=float(np.exp(rng.uniform(np.log(0.1), np.log(2)))), taille_saut=float(rng.uniform(5, 25)),
        lien_facteur=rng.uniform(-1.0, 1.0, marches), part_facteur=float(rng.uniform(0.0, 0.7)),
        duree_regimes_jours={r: float(np.exp(rng.uniform(np.log(3), np.log(60)))) for r in regimes},
        probas_regimes=dict(zip(regimes, poids.tolist())),
        force_tendance=float(np.exp(rng.uniform(np.log(0.03), np.log(0.5)))) * intensite,
        tendance_dans_facteur=bool(rng.random() < 0.4),
        demi_vie_retour_jours=float(np.exp(rng.uniform(np.log(5), np.log(60)))),
        force_retour=float(rng.uniform(0.0, 0.05)) * intensite,     # 14/10 : 0,3 / jour = bien plus fort que le réel
        annonces_par_semaine=float(rng.choice([0.0, 1.0, 3.0, 6.0])), taille_annonce=float(rng.uniform(2.0, 10.0)),
        suite_annonce=float(rng.uniform(-0.3, 0.6)),
        explosions_par_mois=float(rng.choice([0.0, 0.5, 1.0, 2.0, 4.0])),
        force_explosion=float(rng.uniform(1.0, 4.0)) * intensite,
        duree_explosion_jours=float(np.exp(rng.uniform(np.log(0.25), np.log(3.0)))),
        graine=int(rng.integers(1 << 31)))


def calendrier(debut="2010-01-04", jours: int = 520) -> pd.DatetimeIndex:
    """Les instants de cotation (heure serveur) : du lundi 00:00 au vendredi 23:45, comme les devises."""
    fin = pd.Timestamp(debut) + pd.Timedelta(days=int(jours * 7 / 5) + 7)
    t = pd.date_range(debut, fin, freq="15min", inclusive="left")
    return t[t.dayofweek < 5][: jours * BOUGIES_JOUR]


def _regimes(rng, lois: Lois, n_jours: int) -> np.ndarray:
    """Suite des régimes jour par jour (0 rien, 1 tendance, 2 retour), chacun dure ~sa durée moyenne."""
    noms = ("rien", "tendance", "retour")
    p = np.array([lois.probas_regimes[k] for k in noms])
    sortie = np.empty(n_jours, np.int64)
    j = 0
    while j < n_jours:
        r = int(rng.choice(3, p=p))
        d = max(1, int(rng.exponential(lois.duree_regimes_jours[noms[r]])))
        sortie[j:j + d] = r
        j += d
    return sortie


def fabriquer(lois: Lois, jours: int = 520, debut="2010-01-04", prix0=None) -> tuple[dict, dict]:
    """Un monde : {nom: bougies de 15 minutes} et la vérité cachée {regime [T], derive [T, M] (par bougie)}."""
    rng = np.random.default_rng(lois.graine)
    t = calendrier(debut, jours)
    T, M = len(t), lois.marches
    n_jours = T // BOUGIES_JOUR + 1
    jour = np.arange(T) // BOUGIES_JOUR

    # agitation en vagues : log de l'agitation journalière = marche lente rappelée vers sa moyenne
    phi, choc = lois.persistance_agitation, lois.choc_agitation
    z = np.zeros((n_jours, M + 1))
    bruit = rng.normal(0, choc, (n_jours, M + 1))
    for d in range(1, n_jours):
        z[d] = phi * z[d - 1] + bruit[d]
    # vague LENTE : une deuxième marche, très persistante (mémoire de l'agitation sur des mois)
    lente = np.zeros((n_jours, M + 1))
    bruit_l = rng.normal(0, 0.03, (n_jours, M + 1))
    for d in range(1, n_jours):
        lente[d] = 0.997 * lente[d - 1] + bruit_l[d]
    lente = lente / (lente.std(0) + 1e-9) * lois.vague_lente
    z = z + lente
    z -= z.mean(0)
    rythme = _RYTHME[t.hour.to_numpy()] ** lois.force_rythme
    rythme /= np.sqrt((rythme ** 2).mean())
    sig = np.exp(z[jour])                                                       # [T, M+1] (dernier = facteur)
    base = lois.agitation_jour / np.sqrt(BOUGIES_JOUR)                         # agitation d'une bougie [M]

    # queues épaisses (Student ramenée à une agitation de 1)
    nu = lois.queues
    eps = rng.standard_t(nu, (T, M + 1)) * np.sqrt((nu - 2) / nu) if nu > 2.05 else rng.standard_t(2.05, (T, M + 1))
    f = eps[:, M] * sig[:, M] * rythme                                          # le facteur commun
    a = np.sqrt(lois.part_facteur)
    propre = eps[:, :M] * sig[:, :M] * rythme[:, None]
    propre[1:] = propre[1:] - lois.rebond * propre[:-1]                      # rebond achat-vente
    # nouvelles imprévues : sauts brusques rares, n'importe quand
    sauts = rng.random((T, M)) < lois.sauts_par_mois / (21 * BOUGIES_JOUR)
    propre = propre + np.where(sauts, rng.normal(0, lois.taille_saut, (T, M)), 0.0)
    bruit_m = (a * lois.lien_facteur[None, :] * f[:, None] + np.sqrt(1 - a ** 2 * lois.lien_facteur[None, :] ** 2)
               * propre) * base[None, :]

    # régimes et dérive cachée
    reg_j = _regimes(rng, lois, n_jours)
    regime = reg_j[jour]
    derive = np.zeros((T, M))
    sens_j = np.zeros((n_jours, M))
    debut_reg = np.r_[True, reg_j[1:] != reg_j[:-1]]
    sens_courant = rng.choice([-1.0, 1.0], M)
    for d in range(n_jours):                                  # un nouveau sens à chaque nouvelle période de tendance
        if debut_reg[d] and reg_j[d] == 1:
            if lois.tendance_dans_facteur:
                s = rng.choice([-1.0, 1.0])
                sens_courant = s * np.sign(lois.lien_facteur + 1e-9)
            else:
                sens_courant = rng.choice([-1.0, 1.0], M)
        sens_j[d] = sens_courant
    force = lois.force_tendance * base * np.sqrt(BOUGIES_JOUR) / BOUGIES_JOUR     # dérive par bougie [M]
    derive = np.where((regime == 1)[:, None], sens_j[jour] * force[None, :], 0.0)

    # démarrages : seulement quand le marché est calme (agitation sous sa médiane)
    explosion = np.zeros(T, bool)
    if lois.explosions_par_mois > 0 and lois.force_explosion > 0:
        agit_j = z[:, :M].mean(1)
        calme = (agit_j < np.median(agit_j))[jour]
        tirage = rng.random(T) < lois.explosions_par_mois / (21 * BOUGIES_JOUR)
        total = lois.force_explosion * base * np.sqrt(BOUGIES_JOUR)             # [M], en log du prix
        for d0 in np.flatnonzero(tirage & calme):
            duree = max(8, int(lois.duree_explosion_jours * BOUGIES_JOUR * rng.uniform(0.5, 1.5)))
            fin = min(T, d0 + duree)
            sens = (rng.choice([-1.0, 1.0]) * np.sign(lois.lien_facteur + 1e-9) if rng.random() < 0.5
                    else rng.choice([-1.0, 1.0], M))
            allumage = min(4, fin - d0)
            derive[d0:d0 + allumage] += sens * total * 0.25 / allumage
            if fin > d0 + allumage:
                derive[d0 + allumage:fin] += sens * total * 0.75 / (fin - d0 - allumage)
            explosion[d0:fin] = True

    # annonces : jours et heures fixes (13:30, 15:00, 17:00 serveur), saut puis éventuellement une suite
    annonce = np.zeros(T, bool)
    if lois.annonces_par_semaine > 0:
        heures = np.isin(t.hour * 100 + t.minute, [1530, 1700, 1100])
        tirage = rng.random(T) < lois.annonces_par_semaine / (5 * 3)
        annonce = heures & tirage
    saut = np.where(annonce[:, None], rng.normal(0, lois.taille_annonce, (T, M)) * base[None, :]
                    * np.abs(lois.lien_facteur)[None, :], 0.0)
    suite = np.zeros((T, M))
    if lois.suite_annonce != 0 and annonce.any():
        k = np.exp(-np.arange(48) / 12.0)
        k = k / k.sum() * lois.suite_annonce
        for m in range(M):
            suite[:, m] = np.convolve(saut[:, m], np.r_[0.0, k], mode="full")[:T]

    # retour au calme (seulement en régime « retour ») : chaque jour, une part `force_retour` de l'écart au niveau de
    # référence est effacée ; le niveau suit le prix avec une mémoire de `demi_vie_retour_jours` (5 -> 60 jours)
    lam = 1 - (1 - min(lois.force_retour, 0.95)) ** (1 / BOUGIES_JOUR)
    lent = 1 - 0.5 ** (1 / (lois.demi_vie_retour_jours * BOUGIES_JOUR))
    x = np.zeros((T, M))
    niveau = np.zeros(M)
    p = np.zeros(M)
    rappel_tout = np.zeros((T, M))
    choc_total = bruit_m + derive + saut + suite
    retour = (regime == 2)
    for i in range(T):
        rappel = -lam * (p - niveau) if retour[i] else 0.0
        p = p + choc_total[i] + rappel
        niveau = niveau + lent * (p - niveau)
        x[i] = p
        rappel_tout[i] = rappel
    prix0 = np.asarray(prix0 if prix0 is not None else np.exp(rng.uniform(0, 4, M)))
    close = prix0[None, :] * np.exp(x)
    ouverture = np.vstack([prix0[None, :], close[:-1]])
    meche = np.abs(rng.normal(0, 0.6, (2, T, M))) * base[None, None, :] * sig[None, :, :M] * rythme[None, :, None]
    haut = np.maximum(ouverture, close) * np.exp(meche[0])
    bas = np.minimum(ouverture, close) * np.exp(-meche[1])
    donnees = {}
    for m in range(M):
        donnees[f"MONDE{m}"] = pd.DataFrame({"time": t, "open": ouverture[:, m], "high": haut[:, m],
                                             "low": bas[:, m], "close": close[:, m], "volume": 1.0})
    # « tendance » : dérive cachée qui ne dépend pas du hasard ; « rappel » : retour au calme à la bougie i, calculé
    # avec ce qui est connu à la fin de la bougie i-1 (jamais avec le hasard à venir)
    verite = {"regime": regime, "tendance": derive, "rappel": rappel_tout, "derive": derive + rappel_tout,
              "annonce": annonce, "explosion": explosion}
    return donnees, verite
