"""PISTE « chef_crypto » : la stratégie DU CHEF DE PROJET (zones zones supply and demand gigognes) sur les cryptos — 16/10/2026.

CAHIER DES CHARGES ÉCRIT AVANT TOUT RÉSULTAT (liste fermée de 4 variantes, rien d'ajouté après coup).
Respect de sa stratégie : on ne la simplifie pas. Zones, descente gigogne, entrée, stop, sorties par tiers = le code
existant (collapsar/regarder/smc/nono.py et gigogne.py, docs/CASCADE_ZONES.md avenants 1 à 3), appelé tel quel. Seuls
changent : les frais (ceux des cryptos), les FRAIS DE NUIT (obligatoires, absents du calcul du coordinateur), les
données (avec week-ends quand elles existent) et le juge.

Variantes (liste fermée)
- V1 « Gigogne H4 stop A plancher 0.2 » = SA version figée (avenant 3) : zone zones supply and demand H4 vivante, contact du bord proche,
  descente H1 -> M30 -> M15 (zones vivantes du même sens qui chevauchent ; au moins 2 zones), ordre limite au milieu de
  la plus petite zone (200 bougies au plus), stop derrière la zone ± 0,2 ATR de l'unité d'entrée avec un minimum de
  0,2 x ATR journalier (dernier jour complet), TP1 2 R / TP2 sommet H1 / TP3 zone opposée H4 par tiers, 30 jours max.
- V2 « Gigogne H1 stop A plancher 0.2 » = la même logique avec départ H1 (cascade 3 de sa propre méthode :
  {H4, H1} -> {M15, M5}) : descente M30 -> M15, TP3 = zone opposée H1. Seule variante « à plus de trades ».
- K1 = V1, mais un trade n'est pris que si la cassure 24 h (bitcoin_journee.var_C, N = 24, telle quelle : regard à
  chaque heure pleine lun-ven, jours >= 92 bougies) a déclenché le MÊME JOUR serveur, DANS LE MÊME SENS, à une heure
  <= l'heure de la bougie d'entrée de son trade (donc connue avant). Conséquence assumée : pas de trade K1 le week-end.
- K2 = les trades de la cassure 24 h (mêmes règles, sortie milieu du canal ou 23h45 serveur), gardés seulement s'ils
  SORTENT d'une de ses zones : une zone zones supply and demand H4 vivante à l'entrée (confirmée avant, pas effacée), du même sens (demande
  pour un achat), dans laquelle le prix est entré pendant les 24 h précédant la cassure (après la confirmation de la
  zone ; plus bas <= haut de la zone pour une demande), et le prix d'entrée de la cassure est au-delà de la zone (au-
  dessus du haut pour un achat). Symétrique pour une vente.

Frais (aller-retour, part du montant)
- BTC 0,03 %, ETH 0,05 % (prudents, coordinateur) ; les ~20 autres cryptos (Binance) 0,05 %.
- Zones : frais appliqués comme dans trade_nono (entrée limite = demi-frais, TP = demi-frais, stop = frais entiers).
- NUIT (FTMO relevé, mains/conditions_ftmo.json) : 30 %/an achat ET vente, / 360 par nuit, à chaque minuit serveur
  franchi ; nuit du vendredi x 3, samedi et dimanche 0 (jour triple = vendredi). Comptée tiers par tiers (chaque tiers
  paie jusqu'à sa sortie). La cassure (fermée à 23h45) ne paie pas de nuit.
- Chiffres aussi donnés SANS la nuit, pour comparer au contrôle du coordinateur (+0,31 R BTC, +0,33 R ETH).

Données
- BTC / ETH : bougies de 15 min Binance (data/binance/BTCUSDT_M15.csv, ETHUSDT ; 7 j / 7) si présentes ; contrôle de
  fidélité sur les données du projet (dm.charger, Dukascopy, week-ends absents avant 2020) sans la nuit.
- Terrain NEUF : data/binance/<SYM>_M15.csv (heure serveur = New York + 7 h), toutes les cryptos sauf BTC et ETH (et les
  monnaies stables si présentes), triées par ordre alphabétique du nom de fichier ; groupe A = 1er, 3e, 5e...
  (développement), groupe B = 2e, 4e... (confirmation). Liste figée au premier lancement (groupes.json).
- Filtre COMMUN imposé par le coordinateur, appliqué AVANT tout résultat sur ces cryptos : les 7 premiers jours de
  chaque paire ignorés ; bougie dont le bas < 0,5 x clôture ou le haut > 2 x clôture -> bas / haut ramenés à
  min / max(ouverture, clôture) (mèches fausses) ; SAUF le krach éclair réel du 10/10/2025 (jours serveur 10 et 11/10),
  gardé tel quel. MATIC et POL restent séparés (ils ne se recouvrent pas dans le temps). Heures serveur répétées au
  passage à l'heure d'hiver : la première occurrence est gardée.

Compte
- Risque 0,5 % du compte par trade : gain = min(stop en part du prix, 0,5 %) x R (levier crypto FTMO 1:1 -> exposition
  <= 1 x le compte). Cassure (K2) : exposition = min(1, 0,5 % / agitation 14 j), R = gain / 0,5 %.
- Gain d'un trade compté le jour serveur de sa dernière sortie ; jours calendaires (les cryptos cotent 7 j / 7).
- Challenges FTMO : bande_bruit.challenge (départ tous les 10 jours, +10 % puis +5 %, mort à -5 % sur un jour ou
  -10 %, clôtures des jours) ; contre 20 jumeaux (sens tiré à pile ou face trade par trade, même taille, mêmes moments).

Juge
- Force contre le jumeau = moyenne((R - R_inverse) / 2) / écart type x racine(n) ; seuil max(3, racine(2 ln 4)) = 3
  (rappel : à l'échelle de tout le laboratoire SMC, le seuil serait 3,51).
- Mesures : trades, R moyen et médian après frais (avec nuit), gagnants %, force, %/mois, baisse max, pire jour,
  challenges réussis / morts contre jumeaux ; par période : avant 2022 / 2022-2023 / 2024-2026 et les deux moitiés.
- RETENUE (mécanique) : parmi V1, V2, K1, K2, celles dont le R moyen après frais (nuit comprise) est > 0 sur le groupe A
  AVANT 2022 et > 0 sur le groupe A 2022 ET APRÈS ; parmi elles, la plus forte (force du groupe A, toutes années).
  Aucune -> le groupe B reste fermé.
- CONFIRMATION : groupe B, UNE fois, version retenue seulement (verrou vie/pistes/chef_crypto/confirmation.json ; si
  le fichier existe, ne jamais recalculer). Confirmée si R moyen > 0 et force > 0 sur B ; prouvée si force >= 3.

Depuis Test_IA : venv_gpu\\Scripts\\python.exe -u -m collapsar.regarder.pistes.chef_crypto btc_eth|developpement|confirmation
"""
from __future__ import annotations

import json
import math
import sys
from datetime import datetime

import numpy as np
import pandas as pd
from numba import njit

from collapsar.donnees import marches as dm
from collapsar.regarder import bande_bruit as bb
from collapsar.regarder.pistes import bitcoin_journee as bj
from collapsar.regarder.smc import gigogne as G
from collapsar.regarder.smc import noyaux as K
from collapsar.regarder.smc.bougies import bougies
from collapsar.regarder.smc.nono import TENUE_JOURS

VIE = dm.RACINE / "collapsar" / "vie" / "pistes" / "chef_crypto"
BINANCE = dm.RACINE / "data" / "binance"
FRAIS = {"BTC": 0.0003, "ETH": 0.0005}
FRAIS_AUTRES = 0.0005
NUIT_AN = 0.30
RISQUE = 0.005
PLANCHER = 0.2
VARIANTES = ("V1", "V2", "K1", "K2")
NOMS = {"V1": "V1 Gigogne H4 stop A plancher 0.2 (sa version figée)",
        "V2": "V2 Gigogne H1 stop A plancher 0.2 (départ H1)",
        "K1": "K1 = V1 seulement si cassure 24 h même sens même jour",
        "K2": "K2 = cassure 24 h seulement si elle sort d'une zone H4"}
SEUIL = max(3.0, math.sqrt(2 * math.log(len(VARIANTES))))
STABLES = ("USDC", "BUSD", "TUSD", "FDUSD", "DAI", "USDP", "EUR", "USDT_")
PERIODES = {"avant 2022": ("2000-01-01", "2022-01-01"), "2022-2023": ("2022-01-01", "2024-01-01"),
            "2024-2026": ("2024-01-01", "2027-01-01"), "2022 et après": ("2022-01-01", "2027-01-01"),
            "tout": ("2000-01-01", "2027-01-01")}
FIN = pd.Timestamp("2100-01-01")
H7 = pd.Timedelta(hours=7)
JOUR_NS = 86400 * 10 ** 9


# ---------------------------------------------------------------- données
def charger_binance(nom: str) -> pd.DataFrame:
    d = pd.read_csv(BINANCE / f"{nom}_M15.csv")
    d["time"] = pd.to_datetime(d["time"]).astype("datetime64[ns]")      # pandas 3 lit en µs : le labo SMC compte en ns
    return d.drop_duplicates("time").sort_values("time").reset_index(drop=True)


def charger_autre(nom: str) -> pd.DataFrame:
    """Filtre commun imposé par le coordinateur (identique pour tous les chercheurs)."""
    d = charger_binance(nom)
    d = d[d["time"] >= d["time"].iloc[0] + pd.Timedelta(days=7)].reset_index(drop=True)
    oc_min = np.minimum(d["open"], d["close"])
    oc_max = np.maximum(d["open"], d["close"])
    krach = d["time"].dt.normalize().isin([pd.Timestamp("2025-10-10"), pd.Timestamp("2025-10-11")])
    fausse = ((d["low"] < 0.5 * d["close"]) | (d["high"] > 2 * d["close"])) & ~krach
    d.loc[fausse, "low"] = oc_min[fausse]
    d.loc[fausse, "high"] = oc_max[fausse]
    return d


def en_ny(d: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame({"ny": pd.to_datetime(d["time"]).astype("datetime64[ns]") - H7,"open": d["open"].astype(float),
                         "high": d["high"].astype(float), "low": d["low"].astype(float),
                         "close": d["close"].astype(float), "volume": d["volume"].astype(float)})


def construire(nom: str, m: pd.DataFrame, frais: float):
    return lambda u: bougies(nom, u, FIN, m, frais=frais, facteur_ouverture=1.0, volume_inclus=True)


def autres_cryptos() -> list[str]:
    noms = sorted(p.name[:-len("_M15.csv")] for p in BINANCE.glob("*_M15.csv"))
    out = []
    for n in noms:
        base = n[:-4] if n.endswith("USDT") else n
        if base in ("BTC", "ETH") or any(base.startswith(s) or base == s for s in STABLES):
            continue
        out.append(n)
    return out


# ---------------------------------------------------------------- frais de nuit (minuits serveur)
def _poids_minuits():
    k = np.arange(0, 30000)                              # jours depuis 1970-01-01 (un jeudi)
    veille = (k - 1 + 3) % 7                             # jour de la semaine de la veille (lundi = 0)
    w = np.where(veille <= 3, 1.0, np.where(veille == 4, 3.0, 0.0))
    return np.cumsum(w)


_W = _poids_minuits()


def nuits(t_entree_ny: np.ndarray, t_sortie_ny: np.ndarray) -> np.ndarray:
    """Nombre de nuits payées (vendredi x 3, week-end 0) entre deux instants (ns, heure de New York)."""
    a = (np.asarray(t_entree_ny, np.int64) + 7 * 3600 * 10 ** 9) // JOUR_NS
    b = (np.asarray(t_sortie_ny, np.int64) + 7 * 3600 * 10 ** 9) // JOUR_NS
    return _W[b] - _W[a]


# ---------------------------------------------------------------- le trade (copie de nono.trade_nono, stop A, + heures de sortie)
@njit(cache=True)
def trade_tiers_heures(o, h, l, c, bt, duree, mt, mo, mh, ml, i, f_min, b_min, sens, entree, risque, d2, d3, tenue, frais,
                       facteur):
    """Identique à nono.trade_nono avec sortie_cloture=False (stop A), mais rend aussi l'heure de sortie de chaque
    tiers (ns, New York) pour compter les nuits."""
    n = len(c)
    stop = entree - sens * risque
    cibles = np.array([entree + sens * 2.0 * risque, entree + sens * d2, entree + sens * d3])
    ouvert = np.array([True, True, True])
    sortie = np.zeros(3, np.int64)
    gain = 0.0
    cout = entree * frais * 0.5 * facteur
    reste = max(b_min - f_min - 1, 0)
    for s in range(reste + tenue + 1):
        if s < reste:
            k = f_min + 1 + s
            po, ph, pl = mo[k], mh[k], ml[k]
            tq = mt[k]
        elif s == reste:
            po, ph, pl = np.nan, -np.inf, np.inf
            tq = bt[i]
        else:
            ib = i + (s - reste)
            if ib >= n:
                break
            po, ph, pl = o[ib], h[ib], l[ib]
            tq = bt[ib]
        if (sens > 0 and pl <= stop) or (sens < 0 and ph >= stop):
            px = stop if np.isnan(po) else (min(stop, po) if sens > 0 else max(stop, po))
            for q in range(3):
                if ouvert[q]:
                    gain += (px - entree) * sens / 3.0
                    cout += entree * frais / 3.0
                    ouvert[q] = False
                    sortie[q] = tq
            return (gain - cout) / risque, cout / risque, sortie
        for q in range(3):
            if ouvert[q] and ((sens > 0 and ph >= cibles[q]) or (sens < 0 and pl <= cibles[q])):
                px = cibles[q] if np.isnan(po) else (max(cibles[q], po) if sens > 0 else min(cibles[q], po))
                gain += (px - entree) * sens / 3.0
                cout += entree * frais * 0.5 / 3.0
                ouvert[q] = False
                sortie[q] = tq
        if not (ouvert[0] or ouvert[1] or ouvert[2]):
            return (gain - cout) / risque, cout / risque, sortie
    fin = min(n - 1, i + tenue)
    for q in range(3):
        if ouvert[q]:
            gain += (c[fin] - entree) * sens / 3.0
            cout += entree * frais * 0.5 / 3.0
            sortie[q] = bt[fin] + duree
    return (gain - cout) / risque, cout / risque, sortie


def _nuit_R(t_e, sorties, entree, risque):
    """Coût des nuits en R (moyenne des trois tiers)."""
    nb = nuits(np.full(3, t_e), sorties)
    return float((nb * NUIT_AN / 360.0).mean() * entree / risque), float(nb.mean())


def trades_chef(nom: str, cons, departs=("H4", "H1")) -> tuple[pd.DataFrame, dict]:
    """Les trades de sa méthode gigogne (plancher 0,2) pour chaque départ ; rend aussi les données préparées."""
    P = G.preparer(cons, G.ECHELLE_45)
    B, Z = P["B"], P["Z"]
    s_px, s_ty, s_t = P["sommets"]
    BD = B["D1"]
    lignes = []
    for depart in departs:
        v = "V1" if depart == "H4" else "V2"
        xh, xb, xm, xs, xconf, xfin = Z[depart]
        for e in G.entrees(P, depart):
            BY, i, d, entree = B[e["unite"]], e["i"], e["sens"], e["entree"]
            t_e = BY.bt[i]
            jd = int(np.searchsorted(BD.bt, t_e, "right")) - 2          # dernier jour COMPLET
            atr_jour = BD.atr[jd] if jd >= 0 else np.nan
            risque = max(e["risque_zone"], PLANCHER * atr_jour)
            if not np.isfinite(risque):
                continue
            # --- comme gigogne._un_trade
            okx = (xs == -d) & (xconf < t_e) & (xfin > t_e)
            bords = (xb if d > 0 else xh)[okx]
            dist3 = (bords - entree) * d
            dist3 = dist3[dist3 >= 2 * risque]
            if not len(dist3):
                continue
            d3 = float(dist3.min())
            cand = (s_ty == d) & (s_t <= t_e)
            d2s = (s_px[cand] - entree) * d
            d2s = d2s[(d2s > 2 * risque) & (d2s < d3)]
            d2 = float(d2s.min()) if len(d2s) else (2 * risque + d3) / 2
            f_min, b_min = K._remplissage(BY.o, BY.mt, BY.ml, BY.mh, BY.bt, BY.duree, i, d, e["milieu"])
            tenue = int(TENUE_JOURS * 86400e9 // BY.duree)
            args = (BY.o, BY.h, BY.l, BY.c, BY.bt, BY.duree, BY.mt, BY.mo, BY.mh, BY.ml, i, f_min, b_min)
            r, cr, so = trade_tiers_heures(*args, d, entree, risque, d2, d3, tenue, BY.frais, BY.facteur[i])
            ri, _, soi = trade_tiers_heures(*args, -d, entree, risque, d2, d3, tenue, BY.frais, BY.facteur[i])
            t_fill = BY.mt[f_min]
            nr, nb = _nuit_R(t_fill, so, entree, risque)
            nri, _ = _nuit_R(t_fill, soi, entree, risque)
            lignes.append({"variante": v, "marche": nom, "unite": f"{depart}->{e['unite']}",
                           "entree": pd.Timestamp(BY.t[i]), "sortie": pd.Timestamp(int(so.max())), "sens": d,
                           "prix": entree, "R_sans_nuit": r, "R_inverse_sans_nuit": ri, "nuit_R": nr, "nuits": nb,
                           "R": r - nr, "R_inverse": ri - nri, "cout_R": cr, "stop_frac": risque / entree,
                           "risque_compte": min(risque / entree, RISQUE), "tp3_R": d3 / risque})
    return pd.DataFrame(lignes), P


# ---------------------------------------------------------------- la cassure 24 h (bitcoin_journee.var_C, N = 24, telle quelle)
def matrice_df(df: pd.DataFrame) -> dict:
    """Copie de bitcoin_journee.matrice pour des bougies données (heure serveur)."""
    t = pd.to_datetime(df["time"])
    jour = t.dt.normalize()
    jours = pd.date_range(jour.min(), jour.max(), freq="D")
    i = ((jour - jours[0]).dt.days).to_numpy()
    k = (t.dt.hour * 4 + t.dt.minute // 15).to_numpy()
    O, H, L, C = (np.full((len(jours), 96), np.nan) for _ in range(4))
    for X, col in ((O, "open"), (H, "high"), (L, "low"), (C, "close")):
        X[i, k] = df[col].to_numpy(float)
    nb = np.isfinite(C).sum(1)
    valide = (jours.dayofweek < 5) & (nb >= bj.BARRES_MIN)
    Cf = pd.DataFrame(C).ffill(axis=1).to_numpy()
    prev = np.c_[np.full(len(jours), np.nan), Cf[:, :-1]]
    manque = ~np.isfinite(C)
    for X in (O, H, L):
        X[manque] = prev[manque]
    C[manque] = prev[manque]
    premier = pd.DataFrame(O).bfill(axis=1).to_numpy()[:, :1]
    for X in (O, H, L, C):
        X[:] = np.where(np.isfinite(X), X, premier)
    for X in (O, H, L, C):
        X[~valide] = np.nan
    return {"O": O, "H": H, "L": L, "C": C, "valide": valide, "jours": jours}


def trades_cassure(df_serveur: pd.DataFrame, frais: float) -> pd.DataFrame:
    m = matrice_df(df_serveur)
    agit = bj.agitation(m)
    t = bj.trades(m, bj.var_C(m, 24), agit)
    expo = np.minimum(1.0, RISQUE / t["agitation"].to_numpy())
    s = t["sens"].to_numpy()
    r = t["r_prix"].to_numpy()
    t["R"] = expo * (s * r - frais) / RISQUE
    t["R_inverse"] = expo * (-s * r - frais) / RISQUE
    t["R_sans_nuit"], t["R_inverse_sans_nuit"] = t["R"], t["R_inverse"]
    t["serveur_entree"] = t["jour"] + pd.to_timedelta(t["m_entree"], unit="min")
    t["serveur_sortie"] = t["jour"] + pd.to_timedelta(t["m_sortie"], unit="min")
    t["prix_entree"] = [bj.prix(m, d, a) for d, a in zip(t["d"], t["m_entree"])]
    return t


def k1(tv1: pd.DataFrame, tc: pd.DataFrame) -> pd.DataFrame:
    """Trades V1 gardés si une cassure du même sens a déclenché le même jour serveur, à une heure <= leur bougie."""
    if not len(tv1):
        return tv1.assign(variante="K1")
    srv = pd.to_datetime(tv1["entree"]) + H7
    jour = srv.dt.normalize()
    garde = []
    par_jour = {k: g for k, g in tc.groupby("jour")}
    for j, s, sens in zip(jour, srv, tv1["sens"]):
        g = par_jour.get(j)
        garde.append(g is not None and bool(((g["sens"] == sens) & (g["serveur_entree"] <= s)).any()))
    return tv1[np.array(garde, bool)].assign(variante="K1")


def k2(tc: pd.DataFrame, P: dict, nom: str) -> pd.DataFrame:
    """Cassures gardées si elles sortent d'une zone zones supply and demand H4 vivante du même sens touchée dans les 24 h précédentes."""
    zh, zb, zm, zs, zconf, zfin = P["Z"]["H4"]
    base = P["base"]                                          # M15 (heure de New York)
    garde = []
    for _, x in tc.iterrows():
        t = int((x["serveur_entree"] - H7).value)
        s, px = int(x["sens"]), float(x["prix_entree"])
        ok = (zs == s) & (zconf <= t) & (zfin > t) & ((zh < px) if s > 0 else (zb > px))
        bon = False
        for z in np.flatnonzero(ok):
            a = int(np.searchsorted(base.bt, max(int(zconf[z]), t - JOUR_NS)))
            b = int(np.searchsorted(base.bt, t))
            if b > a and ((base.l[a:b].min() <= zh[z]) if s > 0 else (base.h[a:b].max() >= zb[z])):
                bon = True
                break
        garde.append(bon)
    out = tc[np.array(garde, bool)].copy()
    out["variante"], out["marche"] = "K2", nom
    out["entree"] = out["serveur_entree"] - H7
    out["sortie"] = out["serveur_sortie"] - H7
    out["risque_compte"] = RISQUE
    out["nuits"] = 0.0
    return out[["variante", "marche", "entree", "sortie", "sens", "R", "R_inverse", "R_sans_nuit",
                "R_inverse_sans_nuit", "risque_compte", "nuits"]]


# ---------------------------------------------------------------- juge
def compte(t: pd.DataFrame, de, a, signes=None, col="R"):
    """Gains journaliers (part du compte) sur les jours calendaires [de, a) bornés aux données."""
    R = t[col].to_numpy()
    if signes is not None:
        inv = t["R_inverse" if col == "R" else "R_inverse_sans_nuit"].to_numpy()
        R = np.where(signes > 0, R, inv)
    g = pd.Series(R * t["risque_compte"].to_numpy(),
                  index=(pd.to_datetime(t["sortie"]) + H7).dt.normalize())
    g = g.groupby(level=0).sum()
    debut = (pd.to_datetime(t["entree"]).min() + H7).normalize()
    jours = pd.date_range(max(pd.Timestamp(de), debut), max(g.index.max(), debut))
    return g.reindex(jours, fill_value=0.0)


def note(t: pd.DataFrame, de, a, challenges=True) -> dict:
    t = t[(pd.to_datetime(t["entree"]) >= de) & (pd.to_datetime(t["entree"]) < a)]
    n = len(t)
    if n < 10:
        return {"trades": n}
    r = t["R"].to_numpy()
    d = (t["R"] - t["R_inverse"]).to_numpy() / 2
    x = {"trades": n, "marches": int(t["marche"].nunique()), "R_moyen": float(r.mean()), "R_median": float(np.median(r)),
         "gagnants_pct": float((r > 0).mean() * 100), "R_moyen_sans_nuit": float(t["R_sans_nuit"].mean()),
         "force": float(d.mean() / d.std(ddof=1) * math.sqrt(n)) if d.std(ddof=1) > 0 else 0.0,
         "nuits_moy": float(t["nuits"].mean())}
    g = compte(t, de, a)
    mois = len(g) / 30.44
    courbe = g.cumsum()
    x.update({"pct_mois": float(g.sum() / mois * 100), "baisse_max_pct": float((courbe - courbe.cummax()).min() * 100),
              "pire_jour_pct": float(g.min() * 100)})
    if challenges:
        ch = bb.challenge(g)
        rng = np.random.default_rng(7)
        jum = [bb.challenge(compte(t, de, a, rng.choice([-1, 1], n)).reindex(g.index, fill_value=0.0))
               for _ in range(20)]
        x.update({"challenges_reussis_pct": ch["reussis_pct"], "challenges_morts_pct": ch["morts_pct"],
                  "jumeaux_reussis_pct": float(np.mean([j["reussis_pct"] for j in jum])),
                  "jumeaux_morts_pct": float(np.mean([j["morts_pct"] for j in jum]))})
    return x


def tableau(t: pd.DataFrame, titre: str) -> dict:
    res = {}
    for v in sorted(t["variante"].unique()):
        g = t[t["variante"] == v].sort_values("entree")
        res[v] = {p: note(g, de, a) for p, (de, a) in PERIODES.items()}
        for p, x in res[v].items():
            if "R_moyen" in x:
                print(f"{titre} | {v} | {p:13s} | {x['trades']:5d} tr | R {x['R_moyen']:+.3f} (sans nuit "
                      f"{x['R_moyen_sans_nuit']:+.3f}) méd {x['R_median']:+.2f} | gagn {x['gagnants_pct']:.0f} % | force "
                      f"{x['force']:+.2f} | {x['pct_mois']:+.2f} %/mois | baisse {x['baisse_max_pct']:.1f} % | pire j "
                      f"{x['pire_jour_pct']:.2f} % | chall {x['challenges_reussis_pct']:.0f}/{x['challenges_morts_pct']:.0f} "
                      f"(jum {x['jumeaux_reussis_pct']:.0f}/{x['jumeaux_morts_pct']:.0f})", flush=True)
            else:
                print(f"{titre} | {v} | {p:13s} | {x}", flush=True)
    return res


# ---------------------------------------------------------------- un marché complet (4 variantes)
def un_marche(nom: str, d_serveur: pd.DataFrame, frais: float, variantes=VARIANTES) -> pd.DataFrame:
    cache = VIE / "cache" / f"{nom}_{frais:.5f}.csv"
    if cache.exists():
        t = pd.read_csv(cache, parse_dates=["entree", "sortie"])
        return t[t["variante"].isin(variantes)]
    m = en_ny(d_serveur)
    tchef, P = trades_chef(nom, construire(nom, m, frais))
    tc = trades_cassure(d_serveur, frais)
    parts = [tchef, k1(tchef[tchef["variante"] == "V1"], tc), k2(tc, P, nom)] if len(tchef) else [k2(tc, P, nom)]
    t = pd.concat([p for p in parts if len(p)], ignore_index=True)
    cache.parent.mkdir(parents=True, exist_ok=True)
    t.to_csv(cache, index=False)
    print(f"  {nom}: " + ", ".join(f"{v} {int((t['variante'] == v).sum())}" for v in VARIANTES), flush=True)
    return t[t["variante"].isin(variantes)]


def _ecrire(f, obj):
    f.write_text(json.dumps(obj, ensure_ascii=False, indent=1, default=str), encoding="utf-8")


def btc_eth():
    VIE.mkdir(parents=True, exist_ok=True)
    out = {"quand": datetime.now().isoformat(timespec="seconds")}
    # 1) contrôle de fidélité : données du projet (Dukascopy), sans nuit, à comparer au contrôle du coordinateur
    ctrl = []
    for sym, f in (("BTCUSD", FRAIS["BTC"]), ("ETHUSD", FRAIS["ETH"])):
        d = dm.charger(sym, FIN)
        t, _ = trades_chef(sym, construire(sym, en_ny(d), f), departs=("H4",))
        t["source"] = "projet"
        ctrl.append(t)
        print(f"[contrôle projet] {sym} V1 : {len(t)} trades, R sans nuit {t['R_sans_nuit'].mean():+.3f}, "
              f"avec nuit {t['R'].mean():+.3f}", flush=True)
    ctrl = pd.concat(ctrl, ignore_index=True)
    ctrl.to_csv(VIE / "btc_eth_controle_projet.csv", index=False)
    out["controle_projet"] = {s: {"trades": int(len(g)), "R_sans_nuit": float(g["R_sans_nuit"].mean()),
                                  "R_avec_nuit": float(g["R"].mean())} for s, g in ctrl.groupby("marche")}
    # 2) Binance 7 j / 7 (week-ends compris)
    tous = []
    for nom, cle in (("BTCUSDT", "BTC"), ("ETHUSDT", "ETH")):
        if not (BINANCE / f"{nom}_M15.csv").exists():
            print(f"{nom} absent : Binance pas encore là", flush=True)
            continue
        tous.append(un_marche(nom, charger_autre(nom), FRAIS[cle]))
    if tous:
        t = pd.concat(tous, ignore_index=True)
        t.to_csv(VIE / "btc_eth_trades.csv", index=False)
        out["ensemble"] = tableau(t, "BTC+ETH")
        out["par_marche"] = {}
        for nom, g in t.groupby("marche"):
            out["par_marche"][nom] = tableau(g, nom)
    _ecrire(VIE / "btc_eth.json", out)


def groupes() -> dict:
    f = VIE / "groupes.json"
    if f.exists():
        return json.loads(f.read_text(encoding="utf-8"))
    liste = autres_cryptos()
    g = {"liste": liste, "A": liste[0::2], "B": liste[1::2], "quand": datetime.now().isoformat(timespec="seconds")}
    _ecrire(f, g)
    return g


def developpement():
    VIE.mkdir(parents=True, exist_ok=True)
    gr = groupes()
    print("groupe A :", gr["A"], "\ngroupe B (fermé) :", gr["B"], flush=True)
    parts = []
    for nom in gr["A"]:
        try:
            parts.append(un_marche(nom, charger_autre(nom), FRAIS_AUTRES))
        except Exception as e:
            print(f"  {nom} ignoré ({type(e).__name__}: {e})", flush=True)
    t = pd.concat(parts, ignore_index=True)
    t.to_csv(VIE / "developpement_trades.csv", index=False)
    res = tableau(t, "A")
    cand = [v for v in VARIANTES if v in res and res[v]["avant 2022"].get("R_moyen", -9) > 0
            and res[v]["2022 et après"].get("R_moyen", -9) > 0]
    retenue = max(cand, key=lambda v: res[v]["tout"]["force"]) if cand else None
    choix = {"candidates": cand, "retenue": retenue, "ouvrir_B": retenue is not None}
    print("CHOIX :", choix, flush=True)
    _ecrire(VIE / "developpement.json", {"quand": datetime.now().isoformat(timespec="seconds"), "groupe_A": gr["A"],
                                          "resultats": res, "choix": choix})


def confirmation():
    verrou = VIE / "confirmation.json"
    if verrou.exists():
        print("Confirmation DÉJÀ faite :", verrou.read_text(encoding="utf-8")[:2000])
        return
    dev = json.loads((VIE / "developpement.json").read_text(encoding="utf-8"))
    v = dev["choix"]["retenue"]
    if not v:
        print("Aucune version retenue : le groupe B reste fermé.")
        return
    gr = groupes()
    parts = []
    for nom in gr["B"]:
        try:
            parts.append(un_marche(nom, charger_autre(nom), FRAIS_AUTRES, (v,)))
        except Exception as e:
            print(f"  {nom} ignoré ({type(e).__name__}: {e})", flush=True)
    t = pd.concat(parts, ignore_index=True)
    t.to_csv(VIE / "confirmation_trades.csv", index=False)
    res = tableau(t, "B")
    x = res.get(v, {}).get("tout", {})
    sortie = {"quand": datetime.now().isoformat(timespec="seconds"), "variante": v, "groupe_B": gr["B"], "seuil": SEUIL,
              "resultats": res, "confirmee": bool(x.get("R_moyen", -9) > 0 and x.get("force", -9) > 0),
              "prouvee": bool(x.get("R_moyen", -9) > 0 and x.get("force", -9) >= SEUIL)}
    print("CONFIRMATION :", {k: sortie[k] for k in ("variante", "confirmee", "prouvee")})
    _ecrire(verrou, sortie)


if __name__ == "__main__":
    {"btc_eth": btc_eth, "developpement": developpement, "confirmation": confirmation}[
        sys.argv[1] if len(sys.argv) > 1 else "btc_eth"]()
