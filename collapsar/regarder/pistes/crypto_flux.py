"""PISTE « crypto_flux » : l'information propre aux cryptos (flux d'ordres, financement, positions ouvertes, prime
du perpétuel) — 16/10/2026.

CAHIER DES CHARGES ÉCRIT AVANT TOUT RÉSULTAT (liste fermée de 11 variantes, rien d'ajouté après coup).

Données (dépôt public officiel data.binance.vision, contrats perpétuels USD-M, rangées par
data/binance_futures/outils/binance_futures.py dans data/binance_futures/<type>/<SYM>.csv, colonne utc_ms = heure UTC
exacte, colonne time = heure serveur New York + 7 h)
- klines15m : bougies 15 min du perpétuel -> volume acheteur agressif (taker_buy_volume) et volume total.
- funding : taux de financement publiés (utc_ms = heure de règlement ; ramené à un équivalent 8 h = taux x 8 / intervalle).
- metrics : positions ouvertes (sum_open_interest), part des comptes acheteurs/vendeurs (count_long_short_ratio),
  positions des « top traders » (sum_toptrader_long_short_ratio), toutes les 5 min.
- premium1h : prime du perpétuel sur l'indice comptant, bougies 1 h.
- PRIX DU TRADE = bougies 15 min COMPTANT data/binance/<SYM>_M15.csv (filtre commun du coordinateur, identique à
  chef_crypto : 7 premiers jours ignorés, mèches fausses ramenées sauf le krach du 10-11/10/2025), reconverties en UTC.

Heures (tout ce qui décide est connu AVANT l'entrée)
- Grille de décision : chaque fin d'heure UTC h. Entrée au prix de clôture de la bougie comptant 15 min qui finit à h,
  sortie au prix de clôture de la bougie qui finit à h + tenue.
- Flux : bougies du perpétuel CLOSES avant h (ouverture + 15 min <= h).
- Financement : dernier taux dont l'heure de règlement est <= h (le règlement de 16h00:00.002 n'est utilisé qu'à 17h).
  Taux plus vieux que 24 h -> inconnu.
- Metrics : RETARD DE SÉCURITÉ de 15 min (ligne datée T utilisée seulement si T <= h - 15 min), car l'heure exacte de
  publication de ces fichiers n'est pas documentée ; ligne plus vieille que 1 h -> inconnue.
- Prime : bougie 1 h utilisée à sa clôture (ouverture + 1 h <= h).
- Seuils « extrêmes » = centiles calculés sur le PASSÉ seulement (fenêtre glissante qui s'arrête à h - 1 h ;
  90 jours, ou 180 jours pour le financement et la prime ; au moins 1/3 de la fenêtre remplie).

Variantes (liste fermée ; sens +1 achat / -1 vente ; tenue fixe ; une position à la fois par marché et par variante :
un signal pendant une position ouverte est ignoré)
- F1 FIN_CONTRAIRE (tenue 72 h) : financement >= centile 95 (180 j) -> vente ; <= centile 5 -> achat.
  Sources : Schmeling, Schrimpf, Todorov, « Crypto carry », BIS Working Paper 1087 (2023) : un portage (financement)
  élevé annonce des krachs / rendements faibles ; Christin, Routledge, Soska, Zetlin-Jones, « The Crypto Carry Trade »
  (2023).
- F2 FIN_ELAN (tenue 72 h) : élan 7 jours (rendement des 168 h passées) > 0 ET financement entre la médiane et le
  centile 95 (180 j) -> achat ; élan < 0 ET financement entre le centile 5 et la médiane -> vente (la foule suit la
  tendance sans excès). Sources : Liu & Tsyvinski, « Risks and Returns of Cryptocurrency », RFS 2021 (élan) ; usage
  courant des traders (financement = confirmation sans surchauffe).
- O1 OI_HAUSSE_PRIX_BAISSE (tenue 24 h) : variation des positions ouvertes sur 24 h >= centile 90 ET rendement 24 h
  <= centile 10 -> achat (vendeurs à découvert entrés en masse, cascade puis rebond) ; positions >= c90 ET rendement
  >= c90 -> vente. Source : pratique des traders (Coinglass, Glassnode « leverage-driven moves ») ; pas d'étude
  académique avec règle précise.
- O2 LIQUIDATION_REBOND (tenue 24 h) : variation des positions ouvertes sur 4 h <= centile 5 (fermetures forcées) ET
  rendement 4 h <= centile 5 -> achat ; positions <= c5 ET rendement >= c95 -> vente (rachats forcés épuisés).
  Source : pratique des traders (« long squeeze / short squeeze »), Kaiko Research sur les liquidations.
- L1 FLUX_SUITE (tenue 4 h) : déséquilibre du flux sur 1 h (volume acheteur agressif / volume - 0,5) >= centile 95
  (90 j) -> achat ; <= c5 -> vente. Sources : Cont, Kukanov, Stoikov (2014) « The price impact of order book events » ;
  Silantyev (2019) « Order flow analysis of cryptocurrency markets », Digital Finance.
- L2 FLUX_RETOUR (tenue 24 h) : déséquilibre sur 4 h >= c95 -> vente ; <= c5 -> achat (pression de prix qui se
  résorbe). Sources : Hendershott & Menkveld (2014) « Price pressures », JFE ; Makarov & Schoar (2020) « Trading and
  arbitrage in cryptocurrency markets », JFE (le flux explique les prix).
- L3 FLUX_DERIVE (tenue 24 h) : déséquilibre sur 24 h >= c90 ET rendement 24 h <= c10 -> vente (les acheteurs
  agressifs sont absorbés par des vendeurs patients) ; déséquilibre <= c10 ET rendement >= c90 -> achat. Source :
  pratique des traders de flux (« divergence du delta cumulé », absorption).
- P1 PRIME_CONTRAIRE (tenue 72 h) : prime moyenne des 8 dernières heures >= c95 (180 j) -> vente ; <= c5 -> achat.
  Source : He, Manela, Ross, von Wachter, « Fundamentals of Perpetual Futures » (2022-2024) : l'écart perpétuel -
  comptant suit l'humeur et se referme.
- C1 COMPTES_CONTRAIRE (tenue 24 h) : part des comptes acheteurs (count_long_short_ratio) >= c95 (90 j) -> vente ;
  <= c5 -> achat. Source : sentiment de la foule comme indicateur contraire (Kumar & Lee 2006, J. Finance ; positions
  des clients particuliers chez les courtiers).
- T1 TOP_CONTRE_FOULE (tenue 24 h) : écart log(ratio des positions des top traders) - log(ratio des comptes) >= c95
  (90 j) -> achat (les gros sont plus acheteurs que la foule) ; <= c5 -> vente. Source : « argent averti contre
  foule » (positions des commerciaux du COT ; usage courant sur les ratios Binance).
- S1 SURCHAUFFE (tenue 72 h) : financement >= c90 ET positions ouvertes 24 h >= c90 ET rendement 24 h >= c90 -> vente ;
  financement <= c10 ET positions >= c90 ET rendement <= c10 -> achat. Source : BIS WP 1087 (portage + levier -> krach).

Coûts (obligatoires)
- Frais FTMO crypto par aller-retour (commission 0,0325 % par côté + écart, notes du 16/10) : BTC 0,066 %, ETH 0,090 %,
  autres 0,096 % (avant l'audit du 16/10 : x 1,25 de glissement non mesuré sur le tout = 0,083 / 0,112 / 0,12 %).
- Nuit : 30 %/an du montant, achat ET vente, / 360 par minuit SERVEUR franchi (7 nuits par semaine, comme chef_crypto :
  4 nuits + vendredi x 3).

Compte
- Taille : exposition = min(1, 0,5 % / agitation sur la tenue), agitation = écart type des rendements horaires des 14
  jours passés x racine(tenue en heures). Levier crypto FTMO 1:1 (Swing) -> plafond 1 par trade. Gain compté le jour
  serveur de la sortie ; jours calendaires (7 j / 7). Exposition totale maximale signalée.
- Challenges : bande_bruit.challenge (départ tous les 10 jours) ; contre 20 jumeaux (sens tiré à pile ou face, mêmes
  moments, même taille).

Juge (BRIEF du coordinateur pour cette piste)
- Marchés : DÉVELOPPEMENT = BTCUSDT, ETHUSDT + groupe A (1 symbole sur 2 par ordre alphabétique de data/binance/ hors
  BTC/ETH, en commençant par le 1er = chef_crypto/groupes.json) ; années jusqu'au 31/12/2023. CONTRÔLE = mêmes marchés
  01/2024 -> 10/2026. CONFIRMATION = groupe B, toutes années, UNE fois (verrou vie/pistes/crypto_flux/confirmation.json),
  seulement si le contrôle est positif après frais.
- Force contre le jumeau = moyenne(sens x rendement) / écart type x racine(n) (= moyenne de (R - R_inverse)/2) ;
  seuil max(3, racine(2 ln 11)) = 3. Comme les cryptos bougent ensemble, AUSSI une « force journalière » : mêmes calculs
  sur la somme par jour (exposition x sens x rendement) de tous les trades sortis ce jour-là (plus honnête).
- RETENUE (mécanique, en développement) : gain %/mois après frais et nuits > 0 ET force >= 3 ET force journalière >= 3 ;
  parmi elles, la plus forte force journalière. Aucune -> contrôle et confirmation NE SONT PAS ouverts.
- CONTRÔLE (une fois, verrou controle.json) : variante retenue seulement ; positive si gain après frais > 0 et force > 0.
- CONFIRMATION (une fois) : confirmée si gain après frais > 0 et force > 0 ; prouvée si force >= 3.
- Comparaison avec la cassure 24 h C2 (bitcoin_journee.var_C N = 24 via chef_crypto.trades_cassure, mêmes marchés,
  mêmes frais, taille 0,5 % d'agitation) : lien (corrélation) des gains journaliers, en développement pour toutes les
  variantes.
- Recherche du défaut (pour la variante retenue ou la meilleure) : retard supplémentaire de 1 h sur toute
  l'information ; prix du perpétuel au lieu du comptant ; part du gain venant de BTC/ETH ; meilleure année retirée.

Depuis Test_IA : venv_gpu\\Scripts\\python.exe -u -m collapsar.regarder.pistes.crypto_flux alignement|developpement|controle|confirmation
"""
from __future__ import annotations

import json
import math
import sys
from datetime import datetime

import numpy as np
import pandas as pd

from collapsar.donnees import marches as dm
from collapsar.regarder import bande_bruit as bb

VIE = dm.RACINE / "collapsar" / "vie" / "pistes" / "crypto_flux"
SPOT = dm.RACINE / "data" / "binance"
FUT = dm.RACINE / "data" / "binance_futures"
GROUPES = dm.RACINE / "collapsar" / "vie" / "pistes" / "chef_crypto" / "groupes.json"
VARIANTES = ("F1", "F2", "O1", "O2", "L1", "L2", "L3", "P1", "C1", "T1", "S1")
TENUE = {"F1": 72, "F2": 72, "O1": 24, "O2": 24, "L1": 4, "L2": 24, "L3": 24, "P1": 72, "C1": 24, "T1": 24, "S1": 72}
NOMS = {"F1": "financement extrême contraire", "F2": "financement + élan", "O1": "positions en hausse + prix extrême",
        "O2": "positions fondent (liquidations) contraire", "L1": "flux 1 h suite", "L2": "flux 4 h retour",
        "L3": "flux 24 h contre prix (absorption)", "P1": "prime du perpétuel contraire",
        "C1": "comptes acheteurs contraire", "T1": "top traders contre foule", "S1": "surchauffe (financement+positions+prix)"}
SEUIL = max(3.0, math.sqrt(2 * math.log(len(VARIANTES))))
RISQUE = 0.005
NUIT_AN = 0.30
FIN_DEV, DEBUT_CTRL = pd.Timestamp("2024-01-01"), pd.Timestamp("2024-01-01")
FIN_TOUT = pd.Timestamp("2026-10-01")
H = pd.Timedelta(hours=1)
W90, W180 = 90 * 24, 180 * 24


COMMISSION = 0.00065                  # FTMO crypto : 0,0325 % par côté
ECART = {"BTC": 0.0000122, "ETH": 0.000248}   # relevés sur le compte FTMO (15/10) ; autres cryptos : 0,031 %
ECART_AUTRES = 0.00031


def frais(sym: str) -> float:
    """Aller-retour FTMO = commission + écart x marge de prudence (16/10, audit défaut 5 : le x 1,25 sur le tout est
    retiré ; avant : BTC 0,083 %, ETH 0,112 %, autres 0,12 % ; maintenant 0,066 / 0,090 / 0,096 %)."""
    from collapsar.mains.frais_ftmo import MARGE_PRUDENCE
    return COMMISSION + ECART.get(sym[:3], ECART_AUTRES) * MARGE_PRUDENCE


# ---------------------------------------------------------------- données
def utc_depuis_serveur(t: pd.Series) -> pd.DatetimeIndex:
    """Heure serveur (New York + 7 h, heures répétées en novembre dans l'ordre) -> UTC sans fuseau."""
    ny = pd.DatetimeIndex(pd.to_datetime(t) - pd.Timedelta(hours=7)).astype("datetime64[ns]")
    ete = ~ny.duplicated(keep="first")            # 1re occurrence d'une heure répétée = heure d'été
    return ny.tz_localize("America/New_York", ambiguous=ete).tz_convert("UTC").tz_localize(None)


def spot_heures(sym: str) -> pd.Series:
    """Prix comptant (filtre commun du coordinateur) à chaque fin d'heure UTC (clôture de la bougie qui finit à h)."""
    d = pd.read_csv(SPOT / f"{sym}_M15.csv")
    d["time"] = pd.to_datetime(d["time"])
    d = d[d["time"] >= d["time"].iloc[0] + pd.Timedelta(days=7)].reset_index(drop=True)
    oc_min, oc_max = np.minimum(d["open"], d["close"]), np.maximum(d["open"], d["close"])
    krach = d["time"].dt.normalize().isin([pd.Timestamp("2025-10-10"), pd.Timestamp("2025-10-11")])
    fausse = ((d["low"] < 0.5 * d["close"]) | (d["high"] > 2 * d["close"])) & ~krach
    d.loc[fausse, "low"], d.loc[fausse, "high"] = oc_min[fausse], oc_max[fausse]
    fin = utc_depuis_serveur(d["time"]) + pd.Timedelta(minutes=15)
    s = pd.Series(d["close"].to_numpy(float), index=fin)
    s = s[~s.index.duplicated()]
    s = s[s.index.minute == 0]
    grille = pd.date_range(s.index.min(), s.index.max(), freq="h")
    return s.reindex(grille).ffill(limit=2)


def _ms(x):
    return pd.DatetimeIndex(pd.to_datetime(np.asarray(x, np.int64), unit="ms")).astype("datetime64[ns]")


def caracteristiques(sym: str, decal: int = 0, prix_perp: bool = False) -> pd.DataFrame | None:
    """Tableau horaire (index = fin d'heure UTC h) : prix, agitation, et toute l'information connue à h.
    decal = heures de retard supplémentaire appliquées à toute l'information (test du défaut)."""
    if not (FUT / "klines15m" / f"{sym}.csv").exists():
        return None
    k = pd.read_csv(FUT / "klines15m" / f"{sym}.csv", usecols=["utc_ms", "close", "volume", "taker_buy_volume"])
    kfin = _ms(k["utc_ms"]) + pd.Timedelta(minutes=15)
    heure = kfin.ceil("h")                                   # bougie close au plus tard à cette fin d'heure
    agr = pd.DataFrame({"v": k["volume"].to_numpy(), "tb": k["taker_buy_volume"].to_numpy()}, index=heure)
    agr = agr.groupby(level=0).sum()
    perp = pd.Series(k["close"].to_numpy(float), index=kfin)
    perp = perp[perp.index.minute == 0]
    del k
    px = perp if prix_perp else spot_heures(sym)
    debut = max(px.index.min(), agr.index.min())
    grille = pd.date_range(debut, min(px.index.max(), FIN_TOUT), freq="h").astype("datetime64[ns]")
    F = pd.DataFrame(index=grille)
    F["prix"] = px.reindex(grille)
    lr = np.log(F["prix"]).diff()
    F["agit_h"] = lr.rolling(14 * 24, min_periods=7 * 24).std()
    info = pd.DataFrame(index=grille)
    a = agr.reindex(grille).fillna(0.0)
    for w in (1, 4, 24):
        v, tb = a["v"].rolling(w).sum(), a["tb"].rolling(w).sum()
        info[f"flux{w}"] = np.where(v > 0, tb / v.where(v > 0) - 0.5, np.nan)
    for w in (4, 24, 168):
        info[f"ret{w}"] = np.log(F["prix"] / F["prix"].shift(w))
    # financement
    f = FUT / "funding" / f"{sym}.csv"
    if f.exists():
        fu = pd.read_csv(f)
        fs = pd.DataFrame({"t": _ms(fu["utc_ms"]), "fin": fu["taux"] * 8.0 / fu["intervalle_h"].clip(lower=1)})
        g = pd.DataFrame({"h": grille})
        m = pd.merge_asof(g, fs.sort_values("t"), left_on="h", right_on="t", direction="backward",
                          tolerance=pd.Timedelta(hours=24))
        info["fin"] = m["fin"].to_numpy()
    else:
        info["fin"] = np.nan
    # metrics (retard de sécurité 15 min)
    f = FUT / "metrics" / f"{sym}.csv"
    if f.exists():
        me = pd.read_csv(f, usecols=["utc_ms", "sum_open_interest", "count_long_short_ratio",
                                     "sum_toptrader_long_short_ratio"])
        me["t"] = _ms(me["utc_ms"]) + pd.Timedelta(minutes=15)
        me = me.sort_values("t")
        g = pd.DataFrame({"h": grille})
        col = {}
        for c in ("sum_open_interest", "count_long_short_ratio", "sum_toptrader_long_short_ratio"):
            x = me.loc[np.isfinite(me[c]) & (me[c] > 0), ["t", c]]          # chaque colonne séparément (trous propres)
            col[c] = pd.merge_asof(g, x, left_on="h", right_on="t", direction="backward",
                                   tolerance=pd.Timedelta(hours=1))[c].to_numpy()
        oi = pd.Series(np.log(col["sum_open_interest"]), index=grille)
        info["doi4"], info["doi24"] = oi - oi.shift(4), oi - oi.shift(24)
        info["comptes"] = col["count_long_short_ratio"]
        info["top_foule"] = np.log(col["sum_toptrader_long_short_ratio"]) - np.log(info["comptes"])
        del me
    else:
        for c in ("doi4", "doi24", "comptes", "top_foule"):
            info[c] = np.nan
    # prime du perpétuel
    f = FUT / "premium1h" / f"{sym}.csv"
    if f.exists():
        pr = pd.read_csv(f, usecols=["utc_ms", "close"])
        ps = pd.Series(pr["close"].to_numpy(float), index=_ms(pr["utc_ms"]) + H)
        ps = ps[~ps.index.duplicated()].reindex(grille)
        info["prime8"] = ps.rolling(8, min_periods=6).mean()
    else:
        info["prime8"] = np.nan
    if decal:
        info = info.shift(decal)
    return pd.concat([F, info], axis=1)


def centile(x: pd.Series, q: float, w: int) -> pd.Series:
    return x.shift(1).rolling(w, min_periods=w // 3).quantile(q)


def signaux(F: pd.DataFrame) -> dict[str, np.ndarray]:
    """Sens voulu à chaque fin d'heure, pour chaque variante (0 = rien)."""
    S = {}

    def sens(achat, vente):
        a = np.asarray(achat.fillna(False) if hasattr(achat, "fillna") else achat, bool)
        v = np.asarray(vente.fillna(False) if hasattr(vente, "fillna") else vente, bool)
        return np.where(a & ~v, 1, np.where(v & ~a, -1, 0)).astype(np.int8)

    fin = F["fin"]
    f95, f05 = centile(fin, .95, W180), centile(fin, .05, W180)
    f90, f10, f50 = centile(fin, .90, W180), centile(fin, .10, W180), centile(fin, .50, W180)
    S["F1"] = sens(fin <= f05, fin >= f95)
    r168 = F["ret168"]
    S["F2"] = sens((r168 > 0) & (fin > f50) & (fin < f95), (r168 < 0) & (fin < f50) & (fin > f05))
    r24, r4 = F["ret24"], F["ret4"]
    r24_90, r24_10 = centile(r24, .90, W90), centile(r24, .10, W90)
    d24 = F["doi24"]
    d24_90 = centile(d24, .90, W90)
    S["O1"] = sens((d24 >= d24_90) & (r24 <= r24_10), (d24 >= d24_90) & (r24 >= r24_90))
    d4 = F["doi4"]
    d4_05 = centile(d4, .05, W90)
    r4_05, r4_95 = centile(r4, .05, W90), centile(r4, .95, W90)
    S["O2"] = sens((d4 <= d4_05) & (r4 <= r4_05), (d4 <= d4_05) & (r4 >= r4_95))
    l1 = F["flux1"]
    S["L1"] = sens(l1 >= centile(l1, .95, W90), l1 <= centile(l1, .05, W90))
    l4 = F["flux4"]
    S["L2"] = sens(l4 <= centile(l4, .05, W90), l4 >= centile(l4, .95, W90))
    l24 = F["flux24"]
    S["L3"] = sens((l24 <= centile(l24, .10, W90)) & (r24 >= r24_90), (l24 >= centile(l24, .90, W90)) & (r24 <= r24_10))
    p8 = F["prime8"]
    S["P1"] = sens(p8 <= centile(p8, .05, W180), p8 >= centile(p8, .95, W180))
    c = F["comptes"]
    S["C1"] = sens(c <= centile(c, .05, W90), c >= centile(c, .95, W90))
    t = F["top_foule"]
    S["T1"] = sens(t >= centile(t, .95, W90), t <= centile(t, .05, W90))
    S["S1"] = sens((fin <= f10) & (d24 >= d24_90) & (r24 <= r24_10), (fin >= f90) & (d24 >= d24_90) & (r24 >= r24_90))
    return S


def serveur(t: pd.DatetimeIndex) -> pd.DatetimeIndex:
    return pd.DatetimeIndex(t).tz_localize("UTC").tz_convert("America/New_York").tz_localize(None) + pd.Timedelta(hours=7)


def trades_marche(sym: str, F: pd.DataFrame, S: dict, variantes=VARIANTES) -> pd.DataFrame:
    px, ag = F["prix"].to_numpy(), F["agit_h"].to_numpy()
    idx = F.index
    out = []
    for v in variantes:
        h, s = TENUE[v], S[v]
        libre = 0
        for i in np.flatnonzero(s):
            if i < libre or i + h >= len(px):
                continue
            e, x, a = px[i], px[i + h], ag[i]
            if not (np.isfinite(e) and np.isfinite(x) and np.isfinite(a) and a > 0):
                continue
            out.append((v, sym, idx[i], idx[i + h], int(s[i]), x / e - 1, min(1.0, RISQUE / (a * math.sqrt(h)))))
            libre = i + h
    t = pd.DataFrame(out, columns=["variante", "marche", "entree", "sortie", "sens", "r", "expo"])
    if not len(t):
        return t
    se, ss = serveur(t["entree"]), serveur(t["sortie"])
    t["jour_sortie"] = ss.normalize()
    t["nuits"] = (ss.normalize() - se.normalize()).days
    cout = frais(sym) + t["nuits"] * NUIT_AN / 360.0
    t["R"] = t["expo"] * (t["sens"] * t["r"] - cout)                 # part du compte
    t["R_inverse"] = t["expo"] * (-t["sens"] * t["r"] - cout)
    return t


# ---------------------------------------------------------------- cassure 24 h C2 (même code que chef_crypto)
def trades_c2(sym: str) -> pd.DataFrame:
    from collapsar.regarder.pistes import chef_crypto as cc
    t = cc.trades_cassure(cc.charger_autre(sym), frais(sym))
    return pd.DataFrame({"variante": "C2", "marche": sym, "jour_sortie": pd.to_datetime(t["jour"]),
                         "R": t["R"] * cc.RISQUE, "R_inverse": t["R_inverse"] * cc.RISQUE,
                         "entree": pd.to_datetime(t["serveur_entree"]), "sortie": pd.to_datetime(t["serveur_sortie"]),
                         "sens": t["sens"], "r": t["r_prix"], "nuits": 0,
                         "expo": np.minimum(1.0, cc.RISQUE / t["agitation"].to_numpy())})


# ---------------------------------------------------------------- juge
def compte(t: pd.DataFrame, de, a, signes=None) -> pd.Series:
    R = t["R"].to_numpy() if signes is None else np.where(signes > 0, t["R"], t["R_inverse"])
    g = pd.Series(R, index=pd.DatetimeIndex(t["jour_sortie"])).groupby(level=0).sum()
    jours = pd.date_range(pd.Timestamp(de), pd.Timestamp(a) - pd.Timedelta(days=1))
    return g.reindex(jours, fill_value=0.0)


def note(t: pd.DataFrame, de, a, challenges=True) -> dict:
    t = t[(t["entree"] >= de) & (t["entree"] < a)]
    n = len(t)
    if n < 20:
        return {"trades": n}
    de = max(pd.Timestamp(de), pd.Timestamp(t["entree"].min()).normalize())
    a = min(pd.Timestamp(a), pd.Timestamp(t["jour_sortie"].max()) + pd.Timedelta(days=1))
    d = (t["R"] - t["R_inverse"]).to_numpy() / 2
    g = compte(t, de, a)
    dj = (pd.Series(d, index=pd.DatetimeIndex(t["jour_sortie"])).groupby(level=0).sum()
          .reindex(g.index, fill_value=0.0))
    mois = len(g) / 30.44
    courbe = g.cumsum()
    x = {"trades": n, "marches": int(t["marche"].nunique()), "achats_pct": float((t["sens"] > 0).mean() * 100),
         "gagnants_pct": float((t["R"] > 0).mean() * 100),
         "brut_pct_prix": float((t["sens"] * t["r"]).mean() * 100),
         "force": float(d.mean() / d.std(ddof=1) * math.sqrt(n)),
         "force_jour": float(dj.mean() / dj.std(ddof=1) * math.sqrt(len(dj))) if dj.std() > 0 else 0.0,
         "pct_mois": float(g.sum() / mois * 100), "pct_mois_sans_frais": float(dj.sum() / mois * 100),
         "baisse_max_pct": float((courbe - courbe.cummax()).min() * 100), "pire_jour_pct": float(g.min() * 100),
         "nuits_moy": float(t["nuits"].mean()), "debut": str(de.date()), "fin": str(a.date())}
    if challenges:
        ch = bb.challenge(g)
        rng = np.random.default_rng(7)
        jum = [bb.challenge(compte(t, de, a, rng.choice([-1, 1], n))) for _ in range(20)]
        x.update({"chall_reussis_pct": ch["reussis_pct"], "chall_morts_pct": ch["morts_pct"],
                  "jum_reussis_pct": float(np.mean([j["reussis_pct"] for j in jum])),
                  "jum_morts_pct": float(np.mean([j["morts_pct"] for j in jum]))})
    return x


def expo_max(t: pd.DataFrame) -> float:
    ev = pd.concat([pd.Series(t["expo"].to_numpy(), index=t["entree"]),
                    pd.Series(-t["expo"].to_numpy(), index=t["sortie"])]).sort_index(kind="stable")
    return float(ev.groupby(level=0).sum().cumsum().max()) if len(ev) else 0.0


def ligne(nom, x):
    if "force" not in x:
        return f"{nom} | {x}"
    s = (f"{nom} | {x['trades']:5d} tr | brut {x['brut_pct_prix']:+.3f} % | force {x['force']:+.2f} (jour "
         f"{x['force_jour']:+.2f}) | {x['pct_mois']:+.2f} %/mois (sans frais {x['pct_mois_sans_frais']:+.2f}) | baisse "
         f"{x['baisse_max_pct']:.1f} % | pire j {x['pire_jour_pct']:.2f} %")
    if "chall_reussis_pct" in x:
        s += (f" | chall {x['chall_reussis_pct']:.0f}/{x['chall_morts_pct']:.0f} (jum {x['jum_reussis_pct']:.0f}/"
              f"{x['jum_morts_pct']:.0f})")
    return s


def _ecrire(f, obj):
    f.write_text(json.dumps(obj, ensure_ascii=False, indent=1, default=str), encoding="utf-8")


def groupes() -> dict:
    g = json.loads(GROUPES.read_text(encoding="utf-8"))
    return {"dev": ["BTCUSDT", "ETHUSDT"] + g["A"], "B": g["B"]}


def tous_trades(marches, variantes=VARIANTES, decal=0, prix_perp=False, c2=True, etiquette="") -> pd.DataFrame:
    parts = []
    for sym in marches:
        cache = VIE / "cache" / f"{sym}_d{decal}_{'perp' if prix_perp else 'spot'}.pkl"
        if cache.exists():
            t = pd.read_pickle(cache)
        else:
            F = caracteristiques(sym, decal, prix_perp)
            if F is None:
                print(f"  {sym}: pas de perpétuel", flush=True)
                continue
            t = trades_marche(sym, F, signaux(F), VARIANTES)
            del F
            if c2 and not decal and not prix_perp:
                try:
                    t = pd.concat([t, trades_c2(sym)], ignore_index=True)
                except Exception as e:
                    print(f"  {sym}: C2 impossible ({e})", flush=True)
            cache.parent.mkdir(parents=True, exist_ok=True)
            t.to_pickle(cache)
        print(f"  {etiquette}{sym}: " + ", ".join(f"{v} {int((t['variante'] == v).sum())}"
                                                for v in list(variantes) + ["C2"] if (t['variante'] == v).any()),
              flush=True)
        parts.append(t[t["variante"].isin(list(variantes) + ["C2"])])
    return pd.concat(parts, ignore_index=True)


def lien_c2(t: pd.DataFrame, v: str, de, a) -> float:
    tv = t[(t["variante"] == v) & (t["entree"] >= de) & (t["entree"] < a)]
    tc = t[(t["variante"] == "C2") & (t["entree"] >= de) & (t["entree"] < a)]
    if len(tv) < 20 or len(tc) < 20:
        return float("nan")
    g1, g2 = compte(tv, de, a), compte(tc, de, a)
    m = (g1 != 0) | (g2 != 0)
    return float(np.corrcoef(g1[m], g2[m])[0, 1])


# ---------------------------------------------------------------- phases
def alignement():
    """Perpétuel contre comptant (rendements 15 min, décalage -2..+2) et heures de règlement du financement."""
    VIE.mkdir(parents=True, exist_ok=True)
    res = []
    for sym in ("BTCUSDT", "ETHUSDT", "SOLUSDT"):
        k = pd.read_csv(FUT / "klines15m" / f"{sym}.csv", usecols=["time", "utc_ms", "close"])
        s = pd.read_csv(SPOT / f"{sym}_M15.csv", usecols=["time", "close"])
        s = s.drop_duplicates("time")
        k = k.drop_duplicates("time")
        for debut in ("2020-07-13", "2021-01-11", "2023-01-16", "2023-07-17", "2026-01-12", "2026-07-13"):
            a, b = pd.Timestamp(debut), pd.Timestamp(debut) + pd.Timedelta(days=14)
            ks = k[(pd.to_datetime(k["time"]) >= a) & (pd.to_datetime(k["time"]) < b)].set_index("time")["close"]
            ss = s[(pd.to_datetime(s["time"]) >= a) & (pd.to_datetime(s["time"]) < b)].set_index("time")["close"]
            j = pd.concat([ks.pct_change().rename("p"), ss.pct_change().rename("s")], axis=1).dropna()
            if len(j) < 100:
                continue
            lk = {lag: round(float(j["s"].corr(j["p"].shift(-lag))), 3) for lag in (-2, -1, 0, 1, 2)}
            res.append({"symbole": sym, "debut": debut, "bougies": len(j), **{f"decal{l:+d}": c for l, c in lk.items()},
                        "ecart_prix_median_pct": round(float((ks / ss - 1).abs().median() * 100), 4)})
            print(res[-1], flush=True)
    # comptant reconverti en UTC (passages d'heure compris) contre perpétuel en UTC exact, fins d'heure
    for sym in ("BTCUSDT", "ETHUSDT"):
        sp = spot_heures(sym)
        k = pd.read_csv(FUT / "klines15m" / f"{sym}.csv", usecols=["utc_ms", "close"])
        pp = pd.Series(k["close"].to_numpy(float), index=_ms(k["utc_ms"]) + pd.Timedelta(minutes=15))
        pp = pp[pp.index.minute == 0]
        for a, b in (("2020-11-01", "2020-11-15"), ("2021-03-10", "2021-03-20"), ("2023-07-01", "2023-07-20"),
                     ("2025-11-01", "2025-11-10"), ("2026-03-05", "2026-03-15")):
            x, y = sp[a:b].pct_change(), pp[a:b].pct_change()
            res.append({"symbole": sym, "comptant_utc_contre_perp_horaire": f"{a} -> {b}",
                        **{f"decal{l:+d}": round(float(x.corr(y.shift(-l))), 3) for l in (-1, 0, 1)}})
            print(res[-1], flush=True)
    fu = pd.read_csv(FUT / "funding" / "BTCUSDT.csv")
    t = _ms(fu["utc_ms"])
    regl = {"BTC_heures_utc_de_reglement": sorted(pd.Series(t.hour).value_counts().head(6).index.tolist()),
            "BTC_retard_max_ms_apres_heure_pleine": int((fu["utc_ms"] % 3600000).max())}
    me = pd.read_csv(FUT / "metrics" / "BTCUSDT.csv", usecols=["utc_ms"])
    regl["metrics_minutes"] = sorted(pd.Series(_ms(me["utc_ms"]).minute).unique().tolist())[:12]
    print(regl)
    _ecrire(VIE / "alignement.json", {"perp_contre_comptant": res, "reglages_heures": regl})


def developpement():
    VIE.mkdir(parents=True, exist_ok=True)
    gr = groupes()
    print("développement :", gr["dev"], flush=True)
    t = tous_trades(gr["dev"])
    de, a = pd.Timestamp("2020-01-01"), FIN_DEV
    res, liens, expo = {}, {}, {}
    for v in list(VARIANTES) + ["C2"]:
        tv = t[t["variante"] == v]
        res[v] = note(tv, de, a)
        liens[v] = lien_c2(t, v, de, a) if v != "C2" else 1.0
        if v != "C2":
            expo[v] = expo_max(tv[(tv["entree"] >= de) & (tv["entree"] < a)])
        print(ligne(f"DEV {v} {NOMS.get(v, 'cassure 24 h'):42s}", res[v]) + f" | lien C2 {liens[v]:+.2f}", flush=True)
    cand = [v for v in VARIANTES if "force" in res[v] and res[v]["pct_mois"] > 0 and res[v]["force"] >= SEUIL
            and res[v]["force_jour"] >= SEUIL]
    retenue = max(cand, key=lambda v: res[v]["force_jour"]) if cand else None
    choix = {"candidates": cand, "retenue": retenue, "ouvrir_controle": retenue is not None}
    print("CHOIX :", choix, flush=True)
    t[(t["entree"] < a)].to_csv(VIE / "developpement_trades.csv", index=False)
    _ecrire(VIE / "developpement.json", {"quand": datetime.now().isoformat(timespec="seconds"), "marches": gr["dev"],
                                         "seuil": SEUIL, "resultats": res, "lien_c2": liens, "expo_max": expo,
                                         "choix": choix})


def defauts(v: str, marches, de, a) -> dict:
    """Recherche du défaut sur la variante v : retard +1 h, prix du perpétuel, sans BTC/ETH, meilleure année retirée."""
    out = {}
    t1 = tous_trades(marches, (v,), decal=1, etiquette="retard+1h ")
    out["retard_1h"] = note(t1[t1["variante"] == v], de, a, challenges=False)
    t2 = tous_trades(marches, (v,), prix_perp=True, etiquette="perp ")
    out["prix_perpetuel"] = note(t2[t2["variante"] == v], de, a, challenges=False)
    t0 = tous_trades(marches, (v,))
    t0 = t0[(t0["variante"] == v) & (t0["entree"] >= de) & (t0["entree"] < a)]
    out["sans_btc_eth"] = note(t0[~t0["marche"].isin(["BTCUSDT", "ETHUSDT"])], de, a, challenges=False)
    an = t0.groupby(t0["entree"].dt.year)["R"].sum()
    out["par_annee_pct_compte"] = {int(k): round(float(x) * 100, 2) for k, x in an.items()}
    if len(an) > 1:
        pire = int(an.idxmax())
        out["meilleure_annee_retiree"] = {"annee": pire, **note(t0[t0["entree"].dt.year != pire], de, a, challenges=False)}
    for k, x in out.items():
        if isinstance(x, dict) and "force" in x:
            print(ligne(f"DÉFAUT {v} {k}", x), flush=True)
    return out


def controle():
    verrou = VIE / "controle.json"
    if verrou.exists():
        print("Contrôle DÉJÀ fait :", verrou.read_text(encoding="utf-8")[:1500])
        return
    dev = json.loads((VIE / "developpement.json").read_text(encoding="utf-8"))
    v = dev["choix"]["retenue"]
    if not v:
        print("Aucune variante retenue : contrôle fermé.")
        return
    gr = groupes()
    t = tous_trades(gr["dev"])
    de, a = DEBUT_CTRL, FIN_TOUT
    x = note(t[t["variante"] == v], de, a)
    x["lien_c2"] = lien_c2(t, v, de, a)
    print(ligne(f"CONTRÔLE {v}", x), flush=True)
    sortie = {"quand": datetime.now().isoformat(timespec="seconds"), "variante": v, "resultat": x,
              "defauts_developpement": defauts(v, gr["dev"], pd.Timestamp("2020-01-01"), FIN_DEV),
              "positif": bool(x.get("pct_mois", -9) > 0 and x.get("force", -9) > 0)}
    _ecrire(verrou, sortie)


def confirmation():
    verrou = VIE / "confirmation.json"
    if verrou.exists():
        print("Confirmation DÉJÀ faite :", verrou.read_text(encoding="utf-8")[:1500])
        return
    ctrl = json.loads((VIE / "controle.json").read_text(encoding="utf-8"))
    if not ctrl["positif"]:
        print("Contrôle négatif : groupe B fermé.")
        return
    v = ctrl["variante"]
    gr = groupes()
    t = tous_trades(gr["B"])
    res = {}
    for p, (de, a) in {"tout": ("2020-01-01", FIN_TOUT), "jusqu'à 2023": ("2020-01-01", FIN_DEV),
                       "2024-2026": (DEBUT_CTRL, FIN_TOUT)}.items():
        res[p] = note(t[t["variante"] == v], pd.Timestamp(de), pd.Timestamp(a))
        print(ligne(f"CONFIRMATION {v} {p}", res[p]), flush=True)
    x = res["tout"]
    _ecrire(verrou, {"quand": datetime.now().isoformat(timespec="seconds"), "variante": v, "groupe_B": gr["B"],
                     "resultats": res, "confirmee": bool(x.get("pct_mois", -9) > 0 and x.get("force", -9) > 0),
                     "prouvee": bool(x.get("pct_mois", -9) > 0 and x.get("force", -9) >= SEUIL)})


if __name__ == "__main__":
    {"alignement": alignement, "developpement": developpement, "controle": controle,
     "confirmation": confirmation}[sys.argv[1] if len(sys.argv) > 1 else "developpement"]()
