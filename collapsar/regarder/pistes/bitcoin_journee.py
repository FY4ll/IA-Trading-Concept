"""PISTE « BITCOIN DANS LA JOURNÉE » (BTCUSD, compte FTMO) — 16/10/2026.

CAHIER DES CHARGES ÉCRIT AVANT TOUT RÉSULTAT (liste fermée, 8 variantes, aucune ajoutée après coup).

Marché, heures, données
- BTCUSD, bougies de 15 min de dm.charger (heure du serveur MetaTrader = New York + 7 h ; l'heure d'une bougie = son
  début). Une journée = minuit serveur -> 23h45 serveur. TOUT est fermé au plus tard à 23h45 (prix de clôture de la
  bougie 23h30-23h45) : jamais de position à minuit serveur -> aucun frais de nuit (30 %/an des deux côtés chez FTMO).
- Jours tradés : lundi -> vendredi serveur seulement, et seulement les jours avec >= 92 bougies sur 96 (les données
  n'ont pas de week-end avant 2020, et seulement des morceaux de samedi/dimanche ensuite : règle identique pour toutes
  les périodes). Les rares bougies manquantes sont bouchées par le dernier prix connu.
- Heure UTC : serveur = UTC + 2 h (hiver de New York) ou + 3 h (été de New York), calculé pour chaque jour.

Variantes (sens = signe du signal ; une position à la fois ; entrée et sortie au prix de clôture d'une bougie)
- A1 élan UTC (Wen, Bouri, Xu, Zhao 2022 ; Gao, Han, Li, Zhou 2018) : signe du rendement de la première demi-heure
  du jour UTC (00h00-00h30 UTC) -> position pendant la dernière demi-heure du même jour UTC (23h30-24h00 UTC, soit
  01h30-02h00 ou 02h30-03h00 serveur le lendemain : à l'intérieur d'une journée serveur).
- A2 élan serveur : signe de 00h00-00h30 serveur -> position de 23h15 à 23h45 serveur.
- A3 élan demi-journée : signe de 00h00-12h00 serveur -> position de 12h00 à 23h45 serveur.
- B1 bande de bruit (Zarattini, Aziz, Barbon 2024, réglages du papier) sur la journée serveur : bruit(t) = moyenne
  sur les 14 jours tradés précédents de |prix(t) / ouverture - 1| ; bande haute = max(ouverture, clôture du jour tradé
  précédent) x (1 + bruit), basse = min(...) x (1 - bruit) ; regards toutes les 30 min (00h30 ... 23h30) : au-dessus
  -> achat, au-dessous -> vente ; sortie d'un achat si le prix passe sous max(bande haute, prix moyen du jour), d'une
  vente au-dessus de min(bande basse, prix moyen) ; sortie forcée 23h45 ; pas d'entrée à 23h45. (Prix moyen = moyenne
  des prix typiques, pas de volume fiable.)
- B2 bande de bruit, mêmes règles, regards toutes les 60 min (01h00 ... 23h00) + sortie forcée 23h45.
- C1 cassure horaire 12 h : à chaque heure pleine de 01h00 à 22h00 serveur, si la clôture de l'heure écoulée dépasse le
  plus haut des 12 heures qui la précèdent -> achat (sous le plus bas -> vente). Sortie à une heure pleine (jusqu'à
  23h00) si la clôture repasse le milieu du canal des 12 heures (calculé de la même façon), sinon à 23h45.
  Les heures précédentes sont celles des jours tradés précédents (le graphique tel qu'il s'affiche, trous compris).
- C2 cassure horaire 24 h : idem avec 24 heures.
- D1 effet d'heure (Padysak & Vojtko 2022, Quantpedia « Are There Seasonal Intraday or Overnight Anomalies in
  Bitcoin? », Gemini 2015-2022) : achat à 21h00 UTC, vente à 23h00 UTC, tous les jours. En hiver de New York cela
  traverse minuit serveur (23h00 -> 01h00) : fermé à 23h45 et rouvert à 00h00 (deux trades, deux frais, le quart
  d'heure 23h45-00h00 manque). Attention : publié en 02/2022 sur des données qui recouvrent notre période de choix ;
  2022-2023 et la période cachée sont hors de l'étude.
(Pas de variante « heures américaines » : pas trouvé de source publiée avec une règle précise.)

Taille : exposition = min(1 x le compte, cible / agitation), agitation = écart type des rendements journaliers (clôture
à clôture des jours tradés) sur les 14 jours tradés précédents ; cibles 0,5 / 1 / 1,5 % (levier FTMO 1:1 sur le
bitcoin -> plafond 1).

Frais par aller-retour (part du montant exposé) :
- a « FTMO mesuré » : écart relevé 0,0012 % x 1,25 ;
- b « prudent » : 0,01 % (RÈGLE DE RETENUE) ;
- c « très prudent » : 0,03 % (ajout du coordinateur avant les résultats : l'écart peut monter à 15-30 $ à certaines
  heures) ;
- d « fiche du projet » : 0,08 % x 1,25 (pour information seulement).

Juge
- Choix 2017-05 -> 2021, vérification 2022-2023, période cachée 2024-01 -> 2026-10 UNE fois (verrou cachee.json).
- Force contre le jumeau = moyenne(rendement brut) / écart type x racine(n) (= moyenne de (R - R_inverse)/2), seuil
  max(3, racine(2 ln 8)) = 3. Indication en plus : force corrigée de la dérive du bitcoin (on retire la hausse moyenne
  d'un quart d'heure x durée tenue x sens), car une règle toujours acheteuse profite de la hausse 2017-2021.
- RETENUE (mécanique) : sur 2017-05 -> 2021, gain > 0 au frais « prudent » (cible 1 %) ET force >= 3 ; parmi elles la
  meilleure régularité (gain / risque journalier). Puis vérification 2022-2023 : gain > 0 au frais prudent. Sinon : la
  période cachée n'est PAS ouverte.
- Challenges FTMO : départ tous les 10 jours tradés ; +10 % puis +5 % ; mort si, dans une journée, le compte descend
  de 5 % sous son niveau du matin (perte latente comprise, au plus bas / plus haut des bougies de 15 min) ou à -10 %
  du départ de la phase ; contre 20 jumeaux (sens tiré à pile ou face, mêmes moments, même taille). Espérance d'un
  challenge à 540 EUR remboursé si réussi = -540 x (1 - part réussie) (gains du compte financé non comptés).

CORRECTIONS DE L'AUDIT DU 16/10/2026 (collapsar/vie/audit/rapport.md ; écrites APRÈS avoir vu 2017-2023, la période
cachée n'a jamais été ouverte) :
- défaut 2 : la force (et la force sans dérive) se calcule sur les gains JOURNALIERS du compte taillé à cible 1 %
  (exposition = min(1, cible / agitation)), avant frais, jours tradables sans trade compris (comme crypto_flux
  « force_jour ») ; l'ancienne force non pondérée reste publiée (« force_brute », « force_sans_derive_brute ») ;
- défaut 6 : « réussis parmi les challenges terminés » et nombre d'inachevés publiés ;
- défaut 9 : frais a et b + commission crypto FTMO 0,0325 % par côté (0,065 % aller-retour) ; c et d inchangés ;
- défaut 10 : mois du calendrier (durée réelle de la période), plus jours tradés / 261 x 12 ;
- point 4 : %/mois aussi à cible 2 % (taille du challenge, challenges compris) et « plafond du tricheur » (sens connu
  d'avance) au frais de la règle.

Depuis Test_IA : venv_gpu\\Scripts\\python.exe -u -m collapsar.regarder.pistes.bitcoin_journee [cachee]
"""
from __future__ import annotations

import json
import math
import sys
from datetime import datetime

import numpy as np
import pandas as pd

from collapsar.donnees import marches as dm
from collapsar.mains.fiches import fiche
from collapsar.mains.frais_ftmo import MARGE_PRUDENCE

SYM = "BTCUSD"
VIE = dm.RACINE / "collapsar" / "vie" / "pistes" / "bitcoin_journee"
VARIANTES = ("A1", "A2", "A3", "B1", "B2", "C1", "C2", "D1")
COMMISSION_CRYPTO = 2 * 0.000325             # commission crypto FTMO 0,0325 % par côté = 0,065 % aller-retour
FRAIS = {"a_ftmo_0.0015%+comm": 0.000012 * MARGE_PRUDENCE + COMMISSION_CRYPTO,   # 16/10 : x 1,25 retiré (audit)
         "b_prudent_0.01%+comm": 0.0001 + COMMISSION_CRYPTO,
         "c_tres_prudent_0.03%+comm": 0.0003 + COMMISSION_CRYPTO, "d_fiche_0.1%": fiche(SYM).frais * MARGE_PRUDENCE}
FRAIS_REGLE = "b_prudent_0.01%+comm"
CIBLES = (0.005, 0.01, 0.015, 0.02)          # 2 % = taille du challenge (audit, point 4)
CIBLE_CHALLENGE = 0.02
JOURS_AGIT, JOURS_BRUIT, BARRES_MIN = 14, 14, 92
FIN = 1425                                   # 23h45 serveur, en minutes depuis minuit
JOURS_AN = 261.0                             # (ne sert plus aux durées : mois du calendrier depuis l'audit, défaut 10)
JOURS_MOIS_CAL = 365.25 / 12
SEUIL = max(3.0, math.sqrt(2 * math.log(len(VARIANTES))))
PERIODES = {"choix 2017-05 -> 2021": ("2017-05-01", "2022-01-01"),
            "vérification 2022-2023": ("2022-01-01", "2024-01-01"),
            "cachée 2024-01 -> 2026-10": ("2024-01-01", "2027-01-01")}


# ---------------------------------------------------------------- données
def matrice(jusqua: str) -> dict:
    """Journées calendaires x 96 quarts d'heure (O, H, L, C) ; valide = lun-ven avec >= 92 bougies."""
    cache = VIE / "cache" / f"jours_{jusqua}.npz"
    if cache.exists():
        z = np.load(cache)
        return {k: z[k] for k in z.files} | {"jours": pd.DatetimeIndex(z["jours"])}
    df = dm.charger(SYM, pd.Timestamp("2100-01-01"))
    df = df[df["time"] < pd.Timestamp(jusqua)]
    t = pd.to_datetime(df["time"])
    jour = t.dt.normalize()
    jours = pd.date_range(jour.min(), jour.max(), freq="D")
    i = ((jour - jours[0]).dt.days).to_numpy()
    k = (t.dt.hour * 4 + t.dt.minute // 15).to_numpy()
    O, H, L, C = (np.full((len(jours), 96), np.nan) for _ in range(4))
    for X, col in ((O, "open"), (H, "high"), (L, "low"), (C, "close")):
        X[i, k] = df[col].to_numpy()
    nb = np.isfinite(C).sum(1)
    valide = (jours.dayofweek < 5) & (nb >= BARRES_MIN)
    # bouchage dans la journée : bougie manquante = dernier prix connu (plat)
    Cf = pd.DataFrame(C).ffill(axis=1).to_numpy()
    prev = np.c_[np.full(len(jours), np.nan), Cf[:, :-1]]
    manque = ~np.isfinite(C)
    for X in (O, H, L):
        X[manque] = prev[manque]
    C[manque] = prev[manque]
    premier = pd.DataFrame(O).bfill(axis=1).to_numpy()[:, :1]     # bougies manquantes en début de journée
    for X in (O, H, L, C):
        X[:] = np.where(np.isfinite(X), X, premier)
    for X in (O, H, L, C):
        X[~valide] = np.nan
    off = np.array([7 + pd.Timestamp(j + pd.Timedelta(hours=12)).tz_localize("America/New_York")
                    .utcoffset().total_seconds() / 3600 for j in jours]).astype(int)
    m = {"O": O, "H": H, "L": L, "C": C, "valide": valide, "off": off, "jours": jours}
    cache.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(cache, O=O, H=H, L=L, C=C, valide=valide, off=off, jours=jours.to_numpy())
    return m


def agitation(m: dict) -> np.ndarray:
    """Écart type des rendements journaliers des 14 jours tradés PRÉCÉDENTS (connu avant le jour)."""
    v = np.flatnonzero(m["valide"])
    clo = m["C"][v, 95]
    r = pd.Series(clo).pct_change()
    s = r.rolling(JOURS_AGIT).std().shift(1).to_numpy()
    a = np.full(len(m["jours"]), np.nan)
    a[v] = s
    return a


def prix(m, d, M):
    """Prix à la minute M (multiple de 15) du jour serveur d."""
    return m["O"][d, 0] if M == 0 else m["C"][d, M // 15 - 1]


# ---------------------------------------------------------------- variantes -> liste (jour, sens, minute entrée, minute sortie)
def var_A1(m):
    out, val, off = [], m["valide"], m["off"]
    for u in range(len(val) - 1):
        if not (val[u] and val[u + 1]):
            continue
        o = off[u] * 60
        r = prix(m, u, o + 30) / prix(m, u, o) - 1
        if r != 0:
            e = off[u + 1] * 60
            out.append((u + 1, int(np.sign(r)), e - 30, e))
    return out


def var_A2(m):
    out = []
    for d in np.flatnonzero(m["valide"]):
        r = prix(m, d, 30) / prix(m, d, 0) - 1
        if r != 0:
            out.append((d, int(np.sign(r)), FIN - 30, FIN))
    return out


def var_A3(m):
    out = []
    for d in np.flatnonzero(m["valide"]):
        r = prix(m, d, 720) / prix(m, d, 0) - 1
        if r != 0:
            out.append((d, int(np.sign(r)), 720, FIN))
    return out


def var_B(m, pas: int):
    O, H, L, C, val = m["O"], m["H"], m["L"], m["C"], m["valide"]
    v = np.flatnonzero(val)
    mouv = np.abs(C[v] / O[v, :1] - 1)
    bruit = pd.DataFrame(mouv).rolling(JOURS_BRUIT).mean().shift(1).to_numpy()
    veille = np.r_[np.nan, C[v[:-1], 95]]
    moyen = np.cumsum((H[v] + L[v] + C[v]) / 3, axis=1) / np.arange(1, 97)
    regards = list(range(pas // 15 - 1, 94, pas // 15)) + [94]
    assert regards[-1] == 94 and (95 not in regards)          # le regard final de 23h45 ne doit jamais manquer
    out = []
    for j, d in enumerate(v):
        if not (np.isfinite(bruit[j]).all() and np.isfinite(veille[j])):
            continue
        haut = max(O[d, 0], veille[j]) * (1 + bruit[j])
        bas = min(O[d, 0], veille[j]) * (1 - bruit[j])
        pos, m_in = 0, 0
        for k in regards:
            c, fin, M = C[d, k], k == 94, (k + 1) * 15
            if pos > 0 and (c < max(haut[k], moyen[j, k]) or fin):
                out.append((d, 1, m_in, M)); pos = 0
            elif pos < 0 and (c > min(bas[k], moyen[j, k]) or fin):
                out.append((d, -1, m_in, M)); pos = 0
            if pos == 0 and not fin:
                if c > haut[k]:
                    pos, m_in = 1, M
                elif c < bas[k]:
                    pos, m_in = -1, M
        assert pos == 0
    return out


def var_C(m, N: int):
    H, L, C, val = m["H"], m["L"], m["C"], m["valide"]
    v = np.flatnonzero(val)
    hH = H[v].reshape(len(v), 24, 4).max(2).ravel()           # heures des jours tradés, bout à bout
    hL = L[v].reshape(len(v), 24, 4).min(2).ravel()
    hC = C[v].reshape(len(v), 24, 4)[:, :, 3].ravel()
    hautN = pd.Series(hH).rolling(N).max().shift(1).to_numpy()   # N heures AVANT l'heure g
    basN = pd.Series(hL).rolling(N).min().shift(1).to_numpy()
    out = []
    for j, d in enumerate(v):
        pos, m_in = 0, 0
        for h in range(1, 24):                                   # regard à h:00 = clôture de l'heure h-1
            g = j * 24 + h - 1
            if not (np.isfinite(hautN[g]) and np.isfinite(basN[g])):
                continue
            c, mil = hC[g], (hautN[g] + basN[g]) / 2
            if pos > 0 and c < mil:
                out.append((d, 1, m_in, h * 60)); pos = 0
            elif pos < 0 and c > mil:
                out.append((d, -1, m_in, h * 60)); pos = 0
            if pos == 0 and h <= 22:
                if c > hautN[g]:
                    pos, m_in = 1, h * 60
                elif c < basN[g]:
                    pos, m_in = -1, h * 60
        if pos != 0:
            out.append((d, pos, m_in, FIN))                      # sortie forcée 23h45
    return out


def var_D1(m):
    out, val, off = [], m["valide"], m["off"]
    for u in range(len(val)):
        a, b = (21 + off[u]) * 60, (23 + off[u]) * 60            # minutes depuis minuit serveur du jour u
        if a < FIN and val[u]:
            out.append((u, 1, a, min(b, FIN)))
        if b > 1440 and u + 1 < len(val) and val[u + 1]:
            out.append((u + 1, 1, max(a - 1440, 0), b - 1440))
    return out


GENERATEURS = {"A1": var_A1, "A2": var_A2, "A3": var_A3, "B1": lambda m: var_B(m, 30), "B2": lambda m: var_B(m, 60),
               "C1": lambda m: var_C(m, 12), "C2": lambda m: var_C(m, 24), "D1": var_D1}


def trades(m: dict, liste, agit) -> pd.DataFrame:
    lignes = []
    for d, s, a, b in liste:
        assert 0 <= a < b <= FIN
        e, x = prix(m, d, a), prix(m, d, b)
        k0, k1 = a // 15, b // 15                                 # bougies tenues : k0 .. k1-1
        lo, hi = m["L"][d, k0:k1].min(), m["H"][d, k0:k1].max()
        lignes.append((m["jours"][d], d, s, a, b, x / e - 1, lo / e - 1, 1 - hi / e, agit[d], k1 - k0))
    t = pd.DataFrame(lignes, columns=["jour", "d", "sens", "m_entree", "m_sortie", "r_prix", "adv_achat", "adv_vente",
                                      "agitation", "quarts"])
    t = t[np.isfinite(t["agitation"]) & (t["agitation"] > 0) & np.isfinite(t["r_prix"])].reset_index(drop=True)
    return t.sort_values(["d", "m_entree"]).reset_index(drop=True)


# ---------------------------------------------------------------- juge
def journalier(t, frais, cible, signes=None):
    """(gain du jour, pire point du jour) en part du compte, indexés par jour."""
    s = t["sens"].to_numpy() * (1 if signes is None else signes)
    expo = np.minimum(1.0, cible / t["agitation"].to_numpy())
    g = expo * (s * t["r_prix"].to_numpy() - frais)
    adv = np.where(s > 0, t["adv_achat"].to_numpy(), t["adv_vente"].to_numpy())
    pire_trade = expo * (np.minimum(adv, 0) - frais)
    gs = pd.Series(g, index=t["jour"])
    avant = gs.groupby(level=0).cumsum().to_numpy() - g
    w = pd.Series(np.minimum(avant + pire_trade, 0), index=t["jour"]).groupby(level=0).min()
    return gs.groupby(level=0).sum(), w


def challenge(g: np.ndarray, w: np.ndarray, pas: int = 10) -> dict:
    n = len(g)
    cs = np.r_[0.0, np.cumsum(g)]
    R = M = I = 0
    jr = []
    for d0 in range(0, n, pas):
        i, ok, fini = d0, True, False
        for but in (0.10, 0.05):
            base = cs[i]
            v_fin = cs[i + 1:] - base                            # après chaque jour
            v_deb = cs[i:-1] - base                              # au matin
            mort = (w[i:] <= -0.05) | (v_deb + w[i:] <= -0.10)
            gagne = v_fin >= but
            im = np.argmax(mort) if mort.any() else n
            ig = np.argmax(gagne) if gagne.any() else n
            if im == n and ig == n:
                fini = False
                break
            if im <= ig:
                ok = False
                break
            i, fini = i + ig + 1, True
        if not ok:
            M += 1
        elif fini:
            R += 1
            jr.append(i - d0)
        else:
            I += 1
    tot = max(1, R + M + I)
    p = R / tot
    return {"reussis_pct": 100 * p, "morts_pct": 100 * M / tot, "inacheves_pct": 100 * I / tot,
            "jours_median": float(np.median(jr)) if jr else None, "esperance_eur": -540 * (1 - p),
            "reussis_parmi_termines_pct": 100 * R / (R + M) if R + M else None,     # défaut 6 de l'audit
            "termines_n": int(R + M), "inacheves_n": int(I)}


def mois_calendrier(jours: pd.DatetimeIndex) -> float:
    """Durée réelle de la période en mois du calendrier (du premier au dernier jour compris) ; défaut 10."""
    jours = pd.DatetimeIndex(jours)
    return ((jours[-1] - jours[0]).days + 1) / JOURS_MOIS_CAL


def force_jour(x) -> float:
    """Force = moyenne / écart type x racine(n) d'une suite de gains journaliers (jours sans trade compris)."""
    x = np.asarray(x, float)
    sd = x.std(ddof=1) if len(x) > 1 else 0.0
    return float(x.mean() / sd * math.sqrt(len(x))) if sd > 0 else 0.0


def bilan(t: pd.DataFrame, jours_tradables: pd.DatetimeIndex, mu15: float, avec_challenges: bool = True) -> dict:
    if len(t) < 20:
        return {"trades": int(len(t))}
    s = t["sens"].to_numpy()
    brut = s * t["r_prix"].to_numpy()
    force_brute = float(brut.mean() / brut.std(ddof=1) * math.sqrt(len(t)))
    corr = brut - s * mu15 * t["quarts"].to_numpy()
    force_d_brute = float(corr.mean() / corr.std(ddof=1) * math.sqrt(len(t)))
    # défaut 2 : gains journaliers du compte taillé (cible 1 %), avant frais, jours tradables sans trade compris
    expo1 = np.minimum(1.0, 0.01 / t["agitation"].to_numpy())

    def par_jour(x):
        return pd.Series(x, index=t["jour"]).groupby(level=0).sum().reindex(jours_tradables, fill_value=0.0)

    force, force_d = force_jour(par_jour(expo1 * brut)), force_jour(par_jour(expo1 * corr))
    res = {"trades": int(len(t)), "achats_pct": float((s > 0).mean() * 100), "brut_moyen_pct_prix": float(brut.mean() * 100),
           "force": force, "force_sans_derive": force_d, "force_brute": force_brute,
           "force_sans_derive_brute": force_d_brute,
           "expo_moyenne_cible1": float(expo1.mean()), "frais": {}}
    mois = mois_calendrier(jours_tradables)                   # défaut 10 : mois du calendrier
    jours_par_an = len(jours_tradables) / mois * 12
    res["mois"] = mois
    for nom, f in FRAIS.items():
        g, w = journalier(t, f, 0.01)
        g = g.reindex(jours_tradables, fill_value=0.0)
        w = w.reindex(jours_tradables, fill_value=0.0)
        courbe = g.cumsum()
        g2, w2 = journalier(t, f, CIBLE_CHALLENGE)              # point 4 : taille du challenge
        g2 = g2.reindex(jours_tradables, fill_value=0.0)
        w2 = w2.reindex(jours_tradables, fill_value=0.0)
        c2 = g2.cumsum()
        res["frais"][nom] = {
            "gagnants_pct": float(((brut - f) > 0).mean() * 100),
            "gain_pct_mois_cible1": float(g.sum() / mois * 100),
            "regularite": float(g.mean() / g.std(ddof=1) * math.sqrt(jours_par_an)) if g.std() > 0 else 0.0,
            "baisse_max_pct": float((courbe - courbe.cummax()).min() * 100),
            "pire_jour_pct": float(g.min() * 100), "pire_point_jour_pct": float(w.min() * 100),
            "gain_pct_mois_cible2": float(g2.sum() / mois * 100),
            "baisse_max_pct_cible2": float((c2 - c2.cummax()).min() * 100),
            "pire_point_jour_pct_cible2": float(w2.min() * 100)}
    tricheur = np.where(brut >= 0, 1, -1)                     # sens connu d'avance (multiplie le sens du trade)
    res["plafond_tricheur"] = {"frais": FRAIS_REGLE, **{
        f"pct_mois_cible{int(c * 100)}": float(journalier(t, FRAIS[FRAIS_REGLE], c, tricheur)[0].sum() / mois * 100)
        for c in (0.01, CIBLE_CHALLENGE)}}
    if avec_challenges:
        res["challenges"] = {}
        rng = np.random.default_rng(7)
        signes_j = [rng.choice([-1, 1], len(t)) for _ in range(20)]
        for nom in list(FRAIS)[:3]:                            # a, b (règle), c
            for cible in CIBLES:
                def ch(sg):
                    g, w = journalier(t, FRAIS[nom], cible, sg)
                    return challenge(g.reindex(jours_tradables, fill_value=0.0).to_numpy(),
                                     w.reindex(jours_tradables, fill_value=0.0).to_numpy())
                elle = ch(None)
                jum = [ch(sg) for sg in signes_j]
                res["challenges"][f"{nom} | cible {cible * 100:.1f} %"] = {
                    "elle": elle, "jumeaux_reussis_pct": float(np.mean([j["reussis_pct"] for j in jum])),
                    "jumeaux_morts_pct": float(np.mean([j["morts_pct"] for j in jum])),
                    "jumeaux_esperance_eur": float(np.mean([j["esperance_eur"] for j in jum])),
                    "tricheur": ch(tricheur)}
    return res


def derive_15min(m, de, a) -> float:
    """Hausse moyenne d'un quart d'heure du bitcoin sur la période (jours tradés)."""
    j = m["jours"]
    sel = m["valide"] & (j >= pd.Timestamp(de)) & (j < pd.Timestamp(a))
    r = m["C"][sel] / m["O"][sel] - 1
    return float(np.nanmean(r))


def afficher(p, v, x):
    if "frais" not in x:
        print(f"{p} | {v}: {x}")
        return
    fb = x["frais"][FRAIS_REGLE]
    tr = x["plafond_tricheur"]
    print(f"{p[:12]:12s} {v} | {x['trades']:5d} trades | achats {x['achats_pct']:.0f} % | brut {x['brut_moyen_pct_prix']:+.4f} % | "
          f"force {x['force']:+.2f} (sans dérive {x['force_sans_derive']:+.2f} ; brute {x['force_brute']:+.2f}) | "
          f"%/mois a/b/c/d " + " / ".join(f"{x['frais'][k]['gain_pct_mois_cible1']:+.2f}" for k in FRAIS) +
          f" | b cible 2 % {fb['gain_pct_mois_cible2']:+.2f} | tricheur b {tr['pct_mois_cible1']:+.2f} / "
          f"{tr['pct_mois_cible2']:+.2f} | régularité b {fb['regularite']:+.2f} | baisse b {fb['baisse_max_pct']:.1f} % | "
          f"pire point {fb['pire_point_jour_pct']:.2f} %")
    for c in (0.01, CIBLE_CHALLENGE):
        e = x.get("challenges", {}).get(f"{FRAIS_REGLE} | cible {c * 100:.1f} %")
        if e:
            el, rt = e["elle"], e["elle"]["reussis_parmi_termines_pct"]
            print(f"    challenge b cible {c * 100:.0f} % : réussis {el['reussis_pct']:.0f} % (jumeaux "
                  f"{e['jumeaux_reussis_pct']:.0f} %, tricheur {e['tricheur']['reussis_pct']:.0f} %), morts "
                  f"{el['morts_pct']:.0f} %, inachevés {el['inacheves_n']} | réussis parmi les {el['termines_n']} terminés : "
                  f"{'-' if rt is None else f'{rt:.0f} %'}")


def main():
    phase = sys.argv[1] if len(sys.argv) > 1 else "apprentissage"
    VIE.mkdir(parents=True, exist_ok=True)
    verrou = VIE / "cachee.json"
    if phase == "cachee":
        if verrou.exists():
            print("Période cachée DÉJÀ évaluée :", verrou.read_text(encoding="utf-8"))
            return
        choix = json.loads((VIE / "choix.json").read_text(encoding="utf-8"))
        if not choix.get("ouvrir_cachee"):
            print("Aucune variante retenue + vérifiée : la période cachée reste fermée.", choix)
            return
        variantes, periodes = [choix["retenue"]], {k: v for k, v in PERIODES.items() if "cachée" in k}
        jusqua = "2027-01-01"
    else:
        variantes, periodes = list(VARIANTES), {k: v for k, v in PERIODES.items() if "cachée" not in k}
        jusqua = "2024-01-01"
    m = matrice(jusqua)
    agit = agitation(m)
    sortie = {"quand": datetime.now().isoformat(timespec="seconds"), "phase": phase, "seuil_force": SEUIL,
              "frais": FRAIS, "periodes": {}}
    tous = []
    for v in variantes:
        t = trades(m, GENERATEURS[v](m), agit)
        t["variante"] = v
        tous.append(t)
        for p, (de, a) in periodes.items():
            tp = t[(t["jour"] >= de) & (t["jour"] < a)].reset_index(drop=True)
            j = m["jours"]
            jt = j[m["valide"] & (j >= pd.Timestamp(de)) & (j < pd.Timestamp(a)) & np.isfinite(agit)]
            x = bilan(tp, pd.DatetimeIndex(jt), derive_15min(m, de, a))
            sortie["periodes"].setdefault(p, {})[v] = x
            afficher(p, v, x)
    if phase != "cachee":
        pc, pv = list(periodes)
        cand = {v: x for v, x in sortie["periodes"][pc].items()
                if "frais" in x and x["frais"][FRAIS_REGLE]["gain_pct_mois_cible1"] > 0 and x["force"] >= SEUIL}
        retenue = max(cand, key=lambda v: cand[v]["frais"][FRAIS_REGLE]["regularite"]) if cand else None
        verif = (retenue is not None and
                 sortie["periodes"][pv][retenue]["frais"][FRAIS_REGLE]["gain_pct_mois_cible1"] > 0)
        sortie["choix"] = {"candidates": list(cand), "retenue": retenue, "verification_positive": bool(verif),
                           "ouvrir_cachee": bool(verif)}
        (VIE / "choix.json").write_text(json.dumps(sortie["choix"], ensure_ascii=False, indent=1), encoding="utf-8")
        print("CHOIX :", sortie["choix"])
    f = verrou if phase == "cachee" else VIE / "apprentissage.json"
    f.write_text(json.dumps(sortie, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    pd.concat(tous).to_csv(VIE / f"trades_{phase}.csv", index=False)
    print(f"(enregistré : {f})")


if __name__ == "__main__":
    main()
