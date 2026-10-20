"""PISTE « hyrotrader » : C1 seul, puis C1 + cassure C2, simulés chez HyroTrader (compte Bybit simulé, 100 000 $,
2 étapes) — 16/10/2026.

CAHIER DES CHARGES ÉCRIT AVANT TOUT RÉSULTAT (une liste fermée de 12 comptes = 2 stratégies x 2 coûts x 3 niveaux ;
rien n'est choisi ni ajouté après coup ; tout est publié).

AVERTISSEMENT ÉCRIT D'AVANCE : toutes les années utilisées (2020 -> 09/2026) ont DÉJÀ été vues pour C1 (crypto_flux :
développement, contrôle, groupe B ; crypto_flux_compte ; trois_briques) et pour la cassure C2 (bitcoin_journee,
cassure_crypto, cassure_v3, compte_combine, trois_briques). Ce calcul est une ESTIMATION de ce que donneraient ces
règles chez HyroTrader, PAS une preuve. Aucune période cachée. Seul le direct jugera.

Règles HyroTrader (relevées sur hyrotrader.com le 16/10/2026, programme « 2 étapes », 100 000 $)
- Étape 1 : +10 % ; étape 2 : +5 % ; au moins 5 jours de trading par étape ; durée illimitée.
- Perte du jour 5 % du capital de départ (5 000 $). Version standard « suiveuse » : mesurée depuis le PLUS HAUT des fonds
  atteint dans la journée, gains latents compris, remise à zéro à 00h00 UTC (la version « fixe » depuis le début du jour
  est une option payante « Swing » ; la page de calcul de la FAQ décrit la version fixe : on simule la suiveuse, plus
  sévère, et on le signale).
- Perte totale 10 % FIXE : fonds (latent compris) <= 90 000 $ = compte perdu.
- Perte RÉALISÉE d'un seul trade <= 3 % du capital de départ (contrôle manuel ; ici compté comme faute).
- Règle de répartition (examen seulement, pas le compte financé) : un jour (UTC, trades fermés ce jour) ne compte pas
  pour plus de 40 % de l'objectif ; le surplus reste sur le compte mais ne compte pas ; un jour perdant compte en entier.
- Valeur totale des positions <= 2 x le capital de départ ; levier jusqu'à 150x (sans effet ici).
- Compte financé : partage 80 % (jusqu'à 90 % « à la discrétion » de la société : on garde 80 %) ; retrait sur demande,
  toutes positions fermées, au plus 5 % du capital de départ par retrait, le surplus non demandé n'est pas payé ; prix du
  challenge remboursé au 1er paiement. Mêmes pertes du jour / totale qu'à l'examen.
- Prix 100 000 $ 2 étapes : 599 $ (relevé 10/2026 ; 579 $ en 07/2026). Capital maximum par trader : 200 000 $.
- Frais Bybit niveau de base : faiseur 0,02 %, preneur 0,055 % par côté ; financement réel des perpétuels.

Données et heures
- Prix du trade = bougies de 15 min du PERPÉTUEL Binance USD-M (data/binance_futures/klines15m, colonne utc_ms ; proxy
  de Bybit, même instrument), grille UTC depuis le 01/01/2020 00h00 jusqu'au 01/10/2026. Filtre commun du coordinateur
  : 7 premiers jours ignorés, mèches fausses (bas < 0,5 x clôture ou haut > 2 x clôture) ramenées à l'ouverture /
  clôture, sauf le krach réel des 10-11/10/2025. Entrée « au début de la bougie k » = clôture de la bougie k - 1.
- Financement réel (data/binance_futures/funding, taux tel que réglé) : une position ouverte au moment d'un règlement
  paie taux x montant au prix du moment si elle achète, le reçoit si elle vend (taux négatif : l'inverse).
- Marchés de (A) : les 25 cryptos de data/binance/ en perpétuel (ADA, ALGO, ATOM, AVAX, BCH, BNB, BTC, DOGE, DOT, EOS,
  ETC, ETH, FIL, LINK, LTC, MATIC puis POL, NEAR, SOL, TRX, UNI, VET, XLM, XMR, XRP). EOS s'arrête en 05/2025, MATIC en
  09/2024 (remplacé par POL). Présence réelle de chacune chez Bybit / HyroTrader non vérifiée une par une.

Brique C1 « contre la foule » (règle de crypto_flux.signaux, prise telle quelle)
- Part des comptes acheteurs Binance (count_long_short_ratio) >= centile 95 de 90 jours -> vente, <= centile 5 ->
  achat ; décision à chaque fin d'heure UTC (retard de sécurité de 15 min sur la donnée) ; entrée au début de la bougie
  de 15 min qui commence à cette heure ; sortie 24 h après (96 bougies) ; stop à 1,5 x l'agitation journalière
  (agitation horaire des 14 jours passés du perpétuel x racine(24)) vérifié à chaque bougie, exécuté au prix du stop.
- Une position C1 par crypto (un signal sur une crypto déjà tenue par C1 est ignoré). Taille : montant = min(1, r1 /
  (1,5 x agitation journalière)) x 100 000 $ (montant fixe, pas de croissance du compte). C1 n'existe que depuis 10/2020
  pour BTC et 01/2022 pour les autres (données de comptes).
- (A) C1 seul : au plus 8 positions, au plus 5 dans le même sens. (B) : C1 au plus 6 positions, au plus 4 dans le même
  sens.

Brique C2 « cassure 24 h » (moteur collapsar/strategies/cassure.py, réglages de la démo : N = 24, lundi -> vendredi
serveur, sortie au milieu du canal, sortie forcée 23h45 serveur, taille « 14 j ») sur BTCUSDT et ETHUSDT perpétuels
(bougies à l'heure serveur reconstruites depuis le même fichier) ; heures converties en UTC. Taille : montant =
min(1, c / agitation 14 j) x 100 000 $. Son arrêt propre à -3 % est REMPLACÉ par l'arrêt interne du compte ci-dessous.
Stop de protection : la perte au stop d'un trade ne dépasse pas 2,5 % du capital (voir plus bas).

Coûts (2 variantes, liste fermée) — glissement prudent du brief : frais x MARGE_PRUDENCE (1,25 jusqu'au 16/10, 1 depuis l'audit)
- (1) « preneur » : 0,055 % par côté à l'entrée et à la sortie -> 0,06875 % par côté.
- (2) « faiseur 70 % » : entrée et sortie normale = 70 % faiseur 0,02 % + 30 % preneur 0,055 % = 0,0305 % -> 0,038125 %
  par côté (aucun coût d'exécution défavorable compté : optimiste) ; une sortie par stop ou par arrêt de sécurité est
  au marché : preneur 0,06875 %.
- + financement réel dans les deux variantes.

Budget de risque (liste fermée : 3 niveaux)
- Agitation visée du compte : 9 / 12 / 15 %/an. (A) : tout à C1. (B) : moitié du risque à chaque brique, chacune vise
  niveau / racine(2).
- Calage UNE fois, sur l'AGITATION (écart type des variations journalières UTC du compte x racine(365)), jamais sur le
  gain, chaque brique seule à sa taille de référence (C1 r1 = 0,15 %, C2 c = 0,5 %), coût (1), sans arrêt interne :
  C1 sur 2022-03-01 -> 2023-03-01 (première année avec toutes les cryptos ; en (A) avec les 25 cryptos et les plafonds
  de (A), en (B) avec ceux de (B)), C2 sur 2020-01-15 -> 2022-01-01. Taille = référence x visée / agitation mesurée ;
  tailles FIXES pour toutes les périodes et les deux coûts.

Règles du compte (toujours actives)
- Plafond de 8 positions ouvertes au total (même quart d'heure : C2 avant C1, puis ordre des cryptos).
- Stop de chaque trade <= 2,5 % du capital (règle des 3 % de HyroTrader) : distance du stop = min(distance de la règle,
  2,5 % x 100 000 / montant).
- Valeur totale ouverte <= 2 x 100 000 $ : une taille qui ne rentre pas est réduite (refusée sous 1 000 $).
- Arrêt interne du jour : fonds au plus mauvais prix de la bougie <= plus haut du jour UTC - 3 % du capital -> tout est
  fermé à ce prix (frais preneur), plus aucune entrée jusqu'à 00h00 UTC.

Fonds, plus haut du jour (prudent) : à chaque bougie, fonds au plus mauvais prix de la bougie (plus bas pour un achat,
plus haut pour une vente, au même instant) comparés au plus haut du jour atteint AVANT cette bougie ; le plus haut du jour
est ensuite mis à jour avec les fonds au MEILLEUR prix de la bougie (les deux extrêmes additionnés : prudent).

Mesures, par période : 2020-2021, 2022-2023, 2024 -> 09/2026 (début réel = première entrée possible de la stratégie).
- Compte continu (100 000 $ au début de la période, rien ne l'arrête) : gain %/mois (simple, montants fixes), baisse max,
  pire jour (depuis le plus haut du jour), jours où la règle des 5 % aurait été cassée, arrêts internes, agitation
  réalisée, trades/mois par brique, %/mois par brique, financement payé, force contre le jumeau par brique (information :
  moyenne de montant x sens x rendement à l'heure de sortie prévue / écart type x racine(n), trades pris).
- Challenges 2 étapes : départ tous les 10 jours UTC depuis la première entrée possible, rangés dans la période où ils
  commencent ; étape réussie dès que la progression comptée (jours fermés plafonnés à 40 % de l'objectif + aujourd'hui
  en fermant tout) atteint l'objectif avec >= 5 jours de trading -> tout fermé, étape suivante le lendemain (nouveau
  compte 100 000 $) ; mort si règle du jour ou mur des 90 000 $ ; inachevé à 24 mois. Contre 20 jumeaux (sens de chaque
  trade tiré à pile ou face, mêmes moments, même taille, stop miroir). % réussis < 3 et < 6 mois.
- Règle des 40 % : part des réussites retardées par la règle (jour où l'objectif brut était atteint < jour de réussite)
  et retard moyen.
- Compte financé (le lendemain de la réussite), 12 mois : mêmes règles de mort ; tous les 7 jours à 00h00 UTC, si le gain
  dépasse 125 $ : retrait de min(gain, 5 % = 5 000 $), le compte revient à 100 000 $ (le surplus au-delà de 5 % est perdu,
  règle de la société) ; à 12 mois, dernier retrait (plafonné). Positions ouvertes gardées au retrait (approximation).
  Survie 12 mois, gain mensuel = retraits / 100 000 / 12.
- Espérance $ par challenge : non réussi en 12 mois = -599 $ ; réussi en 12 mois = -599 + 599 (remboursé si au moins un
  paiement) + 80 % des retraits du financé sur 12 mois. Départs gardés : >= 12 mois de données devant eux et, si réussi,
  financé connu sur 12 mois (ou mort avant).
- Revenu mensuel pour le capital maximum (200 000 $ = 2 comptes de 100 000 $, mêmes trades, ils vivent et meurent
  ensemble) : (a) tant que financés : 2 x 80 % x gain mensuel financé ; (b) régime durable (rachat dès qu'un compte meurt,
  est abandonné ou finit ses 12 mois) : 2 x espérance / durée moyenne d'un cycle.

Simplifications assumées : prix et financement Binance au lieu de Bybit ; bougies de 15 min ; exécution au prix exact
(stop au prix du stop) ; les ordres faiseurs sont supposés remplis au prix voulu ; HyroTrader est un compte SIMULÉ :
rien ne garantit que ses prix, frais et financement collent à la Bourse.

AJOUT APRÈS LECTURE DES RÉSULTATS (16/10/2026, information seulement, aucun choix, aucune taille changée) :
« sensibilite » = les 12 comptes rejoués (sans jumeaux) avec deux autres lectures des règles : (i) plus haut du jour
compté à la clôture de chaque bougie (moins sévère que le meilleur prix de la bougie) ; (ii) retrait seulement quand le
gain atteint 5 % (regard chaque jour à 00h00 UTC), comme l'écrit la FAQ « demander un paiement quand le gain atteint
5 % » — garde plus de coussin contre le mur des 90 000 $ ; (iii) les deux. Raison : les comptes financés meurent
presque tous dans le cahier (krach du 10/10/2025, baisse 11/2025 -> 05/2026).

Depuis Test_IA : $env:CUDA_VISIBLE_DEVICES='-1'; venv_gpu\\Scripts\\python.exe -u -m collapsar.regarder.pistes.hyrotrader [sensibilite]
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
from collapsar.regarder.pistes import crypto_flux as cf
from collapsar.strategies import cassure as cs

VIE = dm.RACINE / "collapsar" / "vie" / "pistes" / "hyrotrader"
CACHE = VIE / "cache"
FUT = dm.RACINE / "data" / "binance_futures"
CAP = 100_000.0
PRIX = 599.0
PART = 0.80
COMPTES_MAX = 2                                   # 200 000 $ = 2 comptes de 100 000 $
G0 = pd.Timestamp("2020-01-01")
GFIN = pd.Timestamp("2026-10-01")
PAS = pd.Timedelta(minutes=15)
MARCHES = ["ADAUSDT", "ALGOUSDT", "ATOMUSDT", "AVAXUSDT", "BCHUSDT", "BNBUSDT", "BTCUSDT", "DOGEUSDT", "DOTUSDT",
           "EOSUSDT", "ETCUSDT", "ETHUSDT", "FILUSDT", "LINKUSDT", "LTCUSDT", "MATICUSDT", "NEARUSDT", "POLUSDT",
           "SOLUSDT", "TRXUSDT", "UNIUSDT", "VETUSDT", "XLMUSDT", "XMRUSDT", "XRPUSDT"]
NIVEAUX = (0.09, 0.12, 0.15)
REF = {"C1": 0.0015, "C2": 0.005}
CALAGE = {"C1": ("2022-03-01", "2023-03-01"), "C2": ("2020-01-15", "2022-01-01")}
K_STOP, TENUE_C1 = 1.5, 96
from collapsar.mains.frais_ftmo import MARGE_PRUDENCE as GLISSEMENT     # 1,25 jusqu'au 16/10 (audit, défaut 5 :
PRENEUR = 0.00055 * GLISSEMENT                                            # glissement réel au marché mesuré nul)
FAISEUR70 = (0.7 * 0.0002 + 0.3 * 0.00055) * GLISSEMENT
COUTS = {"1 preneur": (PRENEUR, PRENEUR, PRENEUR), "2 faiseur 70 %": (FAISEUR70, FAISEUR70, PRENEUR)}
PLAFONDS = {"A": (8, 5), "B": (6, 4)}              # C1 : positions, même sens
MAX_TOT, LEVIER, STOP_MAX, ARRET_INT = 8, 2.0, 0.025, 0.03
JUMEAUX = 20
PERIODES = {"2020-2021": ("2020-01-01", "2022-01-01"), "2022-2023": ("2022-01-01", "2024-01-01"),
            "2024 -> 09/2026": ("2024-01-01", "2026-10-01")}
STRATS = {"A": "C1 seul (25 cryptos)", "B": "C1 + cassure C2 BTC/ETH (moitié du risque chacune)"}


def log(msg: str):
    print(msg, flush=True)
    with open(VIE / "journal.txt", "a", encoding="utf-8") as f:
        f.write(msg + "\n")


def pas_de(t) -> np.ndarray:
    return np.asarray((pd.DatetimeIndex(t) - G0) // PAS, np.int64)


# ---------------------------------------------------------------- données
def _filtre(d: pd.DataFrame, t: pd.Series) -> pd.DataFrame:
    """Filtre commun : 7 premiers jours ignorés, mèches fausses ramenées sauf le krach du 10-11/10/2025."""
    d = d[t >= t.iloc[0] + pd.Timedelta(days=7)].copy()
    t = t[t >= t.iloc[0] + pd.Timedelta(days=7)]
    oc_min, oc_max = np.minimum(d["open"], d["close"]), np.maximum(d["open"], d["close"])
    krach = (t >= "2025-10-10") & (t < "2025-10-12")
    faux = ((d["low"] < 0.5 * d["close"]) | (d["high"] > 2 * d["close"])) & ~krach
    d.loc[faux, "low"], d.loc[faux, "high"] = oc_min[faux], oc_max[faux]
    return d


def matrice_perp(sym: str) -> dict:
    """Copie de cassure.matrice (bouchage identique, 5 jours) sur les bougies du perpétuel à l'heure serveur."""
    k = pd.read_csv(FUT / "klines15m" / f"{sym}.csv", usecols=["time", "open", "high", "low", "close", "volume"])
    k["time"] = pd.to_datetime(k["time"])
    k = k.sort_values("time", kind="stable").drop_duplicates("time", keep="last").reset_index(drop=True)
    df = _filtre(k, k["time"]).reset_index(drop=True)
    t = pd.to_datetime(df["time"])
    jour = t.dt.normalize()
    jours = pd.date_range(jour.min(), jour.max(), freq="D")
    i = ((jour - jours[0]).dt.days).to_numpy()
    kk = (t.dt.hour * 4 + t.dt.minute // 15).to_numpy()
    O, H, L, C = (np.full((len(jours), 96), np.nan) for _ in range(4))
    V = np.zeros((len(jours), 96))
    for X, col in ((O, "open"), (H, "high"), (L, "low"), (C, "close")):
        X[i, kk] = df[col].to_numpy()
    V[i, kk] = np.nan_to_num(df["volume"].to_numpy(float))
    nb = np.isfinite(C).sum(1)
    valide = np.asarray(jours.dayofweek < 5) & (nb >= cs.BARRES_MIN)
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
    V[~valide] = 0.0
    return {"O": O, "H": H, "L": L, "C": C, "V": V, "valide": valide, "jours": jours, "sym": sym, "source": "perp"}


def serveur_vers_utc(srv: pd.DatetimeIndex) -> pd.DatetimeIndex:
    ny = pd.DatetimeIndex(srv) - pd.Timedelta(hours=7)
    return (ny.tz_localize("America/New_York", ambiguous="NaT", nonexistent="NaT").tz_convert("UTC")
            .tz_localize(None).astype("datetime64[ns]"))


def preparer() -> dict:
    f = CACHE / "donnees.npz"
    if f.exists():
        z = np.load(f)
        return {k: z[k] for k in z.files}
    CACHE.mkdir(parents=True, exist_ok=True)
    K = int((GFIN - G0) // PAS)
    S = len(MARCHES)
    H, L, C =(np.full((S, K), np.nan) for _ in range(3))
    FUN = np.zeros((S, K))
    c1 = []
    for i, sym in enumerate(MARCHES):
        k = pd.read_csv(FUT / "klines15m" / f"{sym}.csv", usecols=["utc_ms", "open", "high", "low", "close"])
        k = k.drop_duplicates("utc_ms").sort_values("utc_ms").reset_index(drop=True)
        t = pd.Series(pd.to_datetime(k["utc_ms"], unit="ms"))
        k = _filtre(k, t)
        kk = ((k["utc_ms"].to_numpy(np.int64) - G0.value // 10**6) // 900_000)
        ok = (kk >= 0) & (kk < K)
        H[i, kk[ok]], L[i, kk[ok]], C[i, kk[ok]] = (k[c].to_numpy(float)[ok] for c in ("high", "low", "close"))
        premier = int(kk[ok].min())
        c = pd.Series(C[i]).ffill().to_numpy().copy()
        c[:premier] = np.nan
        C[i] = c
        H[i] = np.where(np.isfinite(H[i]), H[i], c)
        L[i] = np.where(np.isfinite(L[i]), L[i], c)
        del k
        fu = pd.read_csv(FUT / "funding" / f"{sym}.csv")
        kf = (fu["utc_ms"].to_numpy(np.int64) - G0.value // 10**6) // 900_000
        okf = (kf >= 0) & (kf < K)
        np.add.at(FUN[i], kf[okf], fu["taux"].to_numpy(float)[okf])
        F = cf.caracteristiques(sym, prix_perp=True)
        sig = cf.signaux(F)["C1"]
        sd = (F["agit_h"] * math.sqrt(24)).to_numpy()
        h = F.index
        m = (sig != 0) & np.isfinite(sd) & (sd > 0)
        kh = pas_de(h[m])
        c1.append(pd.DataFrame({"fill": kh, "row": i, "sens": sig[m].astype(np.int64), "sd": sd[m]}))
        del F
        log(f"  {sym} : {int(ok.sum())} bougies, {int(m.sum())} heures avec signal C1, financement "
            f"{int(okf.sum())} règlements")
    c1 = pd.concat(c1, ignore_index=True)
    c1 = c1[(c1["fill"] >= 1) & (c1["fill"] + TENUE_C1 < K)].reset_index(drop=True)
    # cassure C2 (BTC, ETH)
    c2 = []
    ctrl = {}
    for sym in ("BTCUSDT", "ETHUSDT"):
        i = MARCHES.index(sym)
        m = matrice_perp(sym)
        reg = cs.Reglages(N=(24,), week_end=False, sortie="milieu", taille="14j", arret_jour=None)
        t = cs.trades(m, reg, 0.0)
        e_srv = pd.DatetimeIndex(t["jour"]) + pd.to_timedelta(t["m_entree"], unit="min")
        s_srv = pd.DatetimeIndex(t["jour"]) + pd.to_timedelta(t["m_sortie"], unit="min")
        eu, su = serveur_vers_utc(e_srv), serveur_vers_utc(s_srv)
        ok = ~(pd.isna(eu) | pd.isna(su))
        g = pd.DataFrame({"fill": pas_de(eu[ok]), "k1": pas_de(su[ok]), "row": i,
                          "sens": t["sens"].to_numpy()[ok].astype(np.int64), "agit": t["agitation"].to_numpy()[ok],
                          "e": t["e"].to_numpy()[ok]})
        g = g[(g["fill"] >= 1) & (g["k1"] < K)]
        egal = np.abs(C[i, g["fill"].to_numpy() - 1] / g["e"].to_numpy() - 1)
        ctrl[sym] = {"trades": int(len(g)), "prix_identique_pct": float((egal < 1e-9).mean() * 100),
                     "ecart_max_pct": float(np.nanmax(egal) * 100), "heures_ambigues_retirees": int((~ok).sum())}
        c2.append(g)
        del m
    c2 = pd.concat(c2, ignore_index=True)
    log(f"  C2 : {ctrl}")
    out = {"H": np.nan_to_num(H), "L": np.nan_to_num(L), "C": np.nan_to_num(C), "FUN": FUN,
           "c1_fill": c1["fill"].to_numpy(np.int64), "c1_row": c1["row"].to_numpy(np.int64),
           "c1_sens": c1["sens"].to_numpy(np.int64), "c1_sd": c1["sd"].to_numpy(float),
           "c2_fill": c2["fill"].to_numpy(np.int64), "c2_k1": c2["k1"].to_numpy(np.int64),
           "c2_row": c2["row"].to_numpy(np.int64), "c2_sens": c2["sens"].to_numpy(np.int64),
           "c2_agit": c2["agit"].to_numpy(float), "ctrl": np.array(json.dumps(ctrl))}
    np.savez(f, **out)
    return out


def trades_strategie(D: dict, strat: str) -> dict:
    """Liste des trades candidats triés (fill, brique C2 avant C1, ordre des cryptos)."""
    n1 = len(D["c1_fill"])
    parts = {"fill": [D["c1_fill"]], "row": [D["c1_row"]], "sens": [D["c1_sens"]],
             "k1": [D["c1_fill"] + TENUE_C1], "brique": [np.zeros(n1, np.int64)],
             "dist": [K_STOP * D["c1_sd"]], "base": [1.0 / (K_STOP * D["c1_sd"])]}
    if strat == "B":
        n2 = len(D["c2_fill"])
        parts["fill"].append(D["c2_fill"]); parts["row"].append(D["c2_row"]); parts["sens"].append(D["c2_sens"])
        parts["k1"].append(D["c2_k1"]); parts["brique"].append(np.ones(n2, np.int64))
        parts["dist"].append(np.full(n2, 10.0)); parts["base"].append(1.0 / D["c2_agit"])
    T = {k: np.concatenate(v) for k, v in parts.items()}
    ordre = np.lexsort((T["row"], -T["brique"], T["fill"]))
    return {k: np.ascontiguousarray(v[ordre]) for k, v in T.items()}


def tailles(T: dict, r1: float, c: float) -> np.ndarray:
    return np.minimum(1.0, np.where(T["brique"] == 0, r1, c) * T["base"])


# ---------------------------------------------------------------- simulateur
@njit(cache=True)
def simuler(H, L, C, FUN, fill, row, sens, brique, k1s, dist, a, signes, fee_in, fee_out, fee_stop,
            max_c1, max_c1_sens, regles, debut, fin, mode, max_jours, jo, gb, pris, fun_b,
            pic_cloture=False, seuil_ret=125.0, pas_ret=7):
    """mode 0 = compte continu (jo[jour] = fonds début, fonds fin, pire écart au plus haut du jour, entrées).
    mode 1 = challenge 2 étapes puis financé 12 mois. Montants fixes en dollars."""
    cap = 100000.0
    n = len(fill)
    nmax = 8
    p_t = np.full(nmax, -1, np.int64)
    p_qty = np.zeros(nmax)
    p_pe = np.zeros(nmax)
    p_stop = np.zeros(nmax)
    p_dir = np.zeros(nmax, np.int64)
    p_cum = np.zeros(nmax)
    solde = cap
    phase = 1 if mode == 1 else 0
    cible = 0.10
    compte = 0.0
    jour_reel = 0.0
    jt = 0
    dernier_jt = -1
    pic_jour = cap
    arret = False
    pic = cap
    baisse = 0.0
    nb_tr = np.zeros(2, np.int64)
    ign = np.zeros(6, np.int64)
    arrets = 0
    jours_casse = 0
    casse_jour = False
    viol = 0
    issue = 3
    jr = np.full(2, -1.0)
    brut = np.full(2, -1.0)
    retraits = 0.0
    nb_ret = 0
    dernier_ret = 0
    debut_fin = -1
    fin_mort = 0
    complet = 0
    jour0 = debut // 96
    ptr = np.searchsorted(fill, debut)
    k = debut
    cur = -1
    while k < fin:
        jour = k // 96
        if jour != cur:
            if casse_jour:
                jours_casse += 1
            casse_jour = False
            if cur >= 0 and (phase == 1 or phase == 2):
                compte += jour_reel if jour_reel <= 0.0 else min(jour_reel, 0.4 * cible * cap)
            jour_reel = 0.0
            eq0 = solde
            for p in range(nmax):
                if p_t[p] >= 0:
                    eq0 += p_qty[p] * p_dir[p] * (C[row[p_t[p]], k - 1] - p_pe[p])
            if mode == 1 and phase < 3 and jour - jour0 > max_jours:
                break
            if phase == 3:
                dj = jour - debut_fin
                if dj >= 365:
                    if eq0 > cap:
                        retraits += min(eq0 - cap, 0.05 * cap)
                        nb_ret += 1
                    complet = 1
                    issue = 0
                    break
                if dj - dernier_ret >= pas_ret:
                    dernier_ret = dj
                    if eq0 - cap >= seuil_ret:
                        retraits += min(eq0 - cap, 0.05 * cap)
                        nb_ret += 1
                        solde -= eq0 - cap
                        eq0 = cap
            pic_jour = eq0
            arret = False
            cur = jour
            if mode == 0:
                jo[jour, 0] = eq0
                jo[jour, 1] = eq0
                jo[jour, 2] = 0.0
        # 1) sorties à l'heure prévue (prix = clôture de la bougie précédente)
        for p in range(nmax):
            if p_t[p] >= 0 and k1s[p_t[p]] <= k:
                t = p_t[p]
                px = C[row[t], k1s[t] - 1]
                v = p_qty[p] * (p_dir[p] * (px - p_pe[p]) - px * fee_out)
                solde += v
                jour_reel += v
                gb[brique[t]] += v
                p_cum[p] += v
                if p_cum[p] < -0.03 * cap:
                    viol += 1
                p_t[p] = -1
        # 2) entrées (prix = clôture de la bougie précédente)
        while ptr < n and fill[ptr] < k:
            ptr += 1
        while ptr < n and fill[ptr] == k:
            t = ptr
            ptr += 1
            if arret:
                ign[0] += 1
                continue
            r = row[t]
            pe = C[r, k - 1]
            if not (pe > 0.0):
                continue
            b = brique[t]
            n_tot = 0
            n_c1 = 0
            n_c1_a = 0
            expo = 0.0
            deja = False
            for p in range(nmax):
                if p_t[p] >= 0:
                    n_tot += 1
                    expo += p_qty[p] * p_pe[p]
                    if brique[p_t[p]] == b and row[p_t[p]] == r:
                        deja = True
                    if brique[p_t[p]] == 0:
                        n_c1 += 1
                        if p_dir[p] > 0:
                            n_c1_a += 1
            if deja:
                ign[1] += 1
                continue
            dr = sens[t] * signes[t]
            if b == 0 and (n_c1 >= max_c1 or (dr > 0 and n_c1_a >= max_c1_sens)
                           or (dr < 0 and n_c1 - n_c1_a >= max_c1_sens)):
                ign[2] += 1
                continue
            if n_tot >= nmax:
                ign[3] += 1
                continue
            montant = a[t] * cap
            if montant > 2.0 * cap - expo:
                montant = 2.0 * cap - expo
                ign[4] += 1
            if montant < 1000.0:
                ign[5] += 1
                continue
            d = dist[t]
            dmax = 0.025 * cap / montant
            if d > dmax:
                d = dmax
            for p in range(nmax):
                if p_t[p] < 0:
                    p_t[p] = t
                    p_qty[p] = montant / pe
                    p_pe[p] = pe
                    p_dir[p] = dr
                    p_stop[p] = pe * (1.0 - dr * d)
                    p_cum[p] = -montant * fee_in
                    break
            solde -= montant * fee_in
            jour_reel -= montant * fee_in
            gb[b] -= montant * fee_in
            nb_tr[b] += 1
            if mode == 0:
                jo[jour, 3] += 1
                pris[t] = 1
            if jour != dernier_jt:
                jt += 1
                dernier_jt = jour
        # 3) financement réglé au début de la bougie
        for p in range(nmax):
            if p_t[p] >= 0:
                t = p_t[p]
                f = FUN[row[t], k]
                if f != 0.0:
                    v = p_qty[p] * C[row[t], k - 1] * p_dir[p] * f
                    solde -= v
                    jour_reel -= v
                    gb[brique[t]] -= v
                    fun_b[brique[t]] += v
                    p_cum[p] -= v
        # 4) stops dans la bougie
        for p in range(nmax):
            if p_t[p] >= 0:
                t = p_t[p]
                r = row[t]
                touche = (p_dir[p] > 0 and L[r, k] <= p_stop[p]) or (p_dir[p] < 0 and H[r, k] >= p_stop[p])
                if touche:
                    px = p_stop[p]
                    v = p_qty[p] * (p_dir[p] * (px - p_pe[p]) - px * fee_stop)
                    solde += v
                    jour_reel += v
                    gb[brique[t]] += v
                    p_cum[p] += v
                    if p_cum[p] < -0.03 * cap:
                        viol += 1
                    p_t[p] = -1
        # 5) fonds au pire et au meilleur prix de la bougie
        pire = solde
        meilleur = solde
        for p in range(nmax):
            if p_t[p] >= 0:
                r = row[p_t[p]]
                if p_dir[p] > 0:
                    pire += p_qty[p] * (L[r, k] - p_pe[p])
                    meilleur += p_qty[p] * (H[r, k] - p_pe[p])
                else:
                    pire += p_qty[p] * (p_pe[p] - H[r, k])
                    meilleur += p_qty[p] * (p_pe[p] - L[r, k])
        ecart = pire - pic_jour
        if pire - pic < baisse:
            baisse = pire - pic
        if ecart <= -0.05 * cap or pire <= 0.90 * cap:
            casse_jour = True
        if mode == 0:
            if ecart < jo[jour, 2]:
                jo[jour, 2] = ecart
        elif ecart <= -0.05 * cap or pire <= 0.90 * cap:
            if phase == 1:
                issue = 1
            elif phase == 2:
                issue = 2
            else:
                issue = 0
                fin_mort = 1
            break
        # 6) arrêt interne du jour
        if regles and (not arret) and ecart <= -0.03 * cap:
            arret = True
            arrets += 1
            for p in range(nmax):
                if p_t[p] >= 0:
                    t = p_t[p]
                    r = row[t]
                    px = L[r, k] if p_dir[p] > 0 else H[r, k]
                    v = p_qty[p] * (p_dir[p] * (px - p_pe[p]) - px * fee_stop)
                    solde += v
                    jour_reel += v
                    gb[brique[t]] += v
                    p_cum[p] += v
                    if p_cum[p] < -0.03 * cap:
                        viol += 1
                    p_t[p] = -1
            meilleur = solde if meilleur < solde else meilleur
        if pic_cloture:
            meilleur = solde
            for p in range(nmax):
                if p_t[p] >= 0:
                    meilleur += p_qty[p] * p_dir[p] * (C[row[p_t[p]], k] - p_pe[p])
        if meilleur > pic_jour:
            pic_jour = meilleur
        # 7) fonds à la clôture
        eqc = solde
        frais_sortie = 0.0
        ouvert = False
        for p in range(nmax):
            if p_t[p] >= 0:
                r = row[p_t[p]]
                eqc += p_qty[p] * p_dir[p] * (C[r, k] - p_pe[p])
                frais_sortie += p_qty[p] * C[r, k] * fee_out
                ouvert = True
        if eqc > pic:
            pic = eqc
        if mode == 0:
            jo[jour, 1] = eqc
        if (phase == 1 or phase == 2) and jt >= 5:
            auj = jour_reel + (eqc - solde) - frais_sortie
            if brut[phase - 1] < 0 and eqc - frais_sortie - cap >= cible * cap:
                brut[phase - 1] = jour
            prog = compte + (auj if auj <= 0.0 else min(auj, 0.4 * cible * cap))
            if prog >= cible * cap:
                jr[phase - 1] = jour
                phase += 1
                for p in range(nmax):
                    p_t[p] = -1
                solde = cap
                pic = cap
                compte = 0.0
                jour_reel = 0.0
                jt = 0
                dernier_jt = -1
                cible = 0.05
                k = (jour + 1) * 96
                if phase == 3:
                    debut_fin = jour + 1
                    dernier_ret = 0
                cur = -1
                continue
        if not ouvert:
            prochain = (jour + 1) * 96
            if ptr < n and fill[ptr] < prochain:
                prochain = fill[ptr]
            if prochain <= k:
                prochain = k + 1
            k = prochain
        else:
            k += 1
    if issue == 3 and phase == 3:
        issue = 0
    res = np.zeros(24)
    res[0], res[1], res[2], res[3], res[4] = issue, k, baisse, nb_tr[0], nb_tr[1]
    res[5], res[6], res[7], res[8] = jr[0], jr[1], brut[0], brut[1]
    res[9], res[10], res[11], res[12] = fin_mort, retraits, nb_ret, complet
    res[13], res[14], res[15] = arrets, jours_casse, viol
    for i in range(6):
        res[16 + i] = ign[i]
    return res


# ---------------------------------------------------------------- laboratoire
class Labo:
    def __init__(self):
        D = preparer()
        self.ctrl = json.loads(str(D["ctrl"]))
        self.H, self.L, self.C, self.FUN = D["H"], D["L"], D["C"], D["FUN"]
        self.D = D
        self.K = self.C.shape[1]
        self.ndays = self.K // 96 + 2

    def run(self, T, a, signes, de, a_, mode, couts, strat, regles=True, jo=None, gb=None, pris=None, fb=None,
            sens_=(False, 125.0, 7)):
        jo = np.zeros((1, 4)) if jo is None else jo
        gb = np.zeros(2) if gb is None else gb
        fb = np.zeros(2) if fb is None else fb
        pris = np.zeros(1, np.int8) if pris is None else pris
        mc, ms = PLAFONDS[strat]
        return simuler(self.H, self.L, self.C, self.FUN, T["fill"], T["row"], T["sens"], T["brique"], T["k1"],
                       T["dist"], a, signes, *couts, mc, ms, regles, int(de), int(a_), mode, 730, jo, gb, pris, fb,
                       *sens_)

    def premier(self, T) -> int:
        return int(T["fill"].min())

    def compte(self, T, a, signes, de, a_, couts, strat, regles=True) -> tuple[dict, np.ndarray]:
        d0 = max(int(pas_de([pd.Timestamp(de)])[0]), (self.premier(T) // 96) * 96)
        d1 = min(int(pas_de([pd.Timestamp(a_)])[0]), self.K)
        jo = np.zeros((self.ndays, 4))
        gb, fb = np.zeros(2), np.zeros(2)
        pris = np.zeros(len(T["fill"]), np.int8)
        r = self.run(T, a, signes, d0, d1, 0, couts, strat, regles, jo, gb, pris, fb)
        j0, j1 = d0 // 96, d1 // 96
        jj = jo[j0:j1]
        fonds = pd.Series(np.r_[CAP, jj[:, 1]])
        var = fonds.diff().dropna() / CAP
        mois = (j1 - j0) / 30.44
        x = {"debut": str((G0 + pd.Timedelta(days=j0)).date()), "mois": mois,
             "gain_pct_mois": float((jj[-1, 1] - CAP) / CAP / mois * 100),
             "baisse_max_pct": float(r[2] / CAP * 100), "pire_jour_pct": float(jj[:, 2].min() / CAP * 100),
             "jours_regle_5pct_cassee": int(r[14]), "arrets_internes": int(r[13]), "fautes_3pct": int(r[15]),
             "agitation_pct_an": float(var.std(ddof=1) * math.sqrt(365) * 100),
             "trades_mois": {"C1": float(r[3] / mois), "C2": float(r[4] / mois)},
             "gain_pct_mois_par_brique": {"C1": float(gb[0] / CAP / mois * 100), "C2": float(gb[1] / CAP / mois * 100)},
             "financement_paye_pct_mois": {"C1": float(fb[0] / CAP / mois * 100), "C2": float(fb[1] / CAP / mois * 100)},
             "ignores": {"arret": int(r[16]), "deja_tenu": int(r[17]), "plafond_C1": int(r[18]),
                         "plafond_8": int(r[19]), "reduits_levier_2x": int(r[20]), "trop_petits": int(r[21])}}
        return x, pris

    def force(self, T, a, pris, de, a_) -> dict:
        lo, hi = pas_de([pd.Timestamp(de)])[0], pas_de([pd.Timestamp(a_)])[0]
        out = {}
        for b, nom in ((0, "C1"), (1, "C2")):
            m = (pris == 1) & (T["brique"] == b) & (T["fill"] >= lo) & (T["fill"] < hi)
            if m.sum() < 21:
                out[nom] = None
                continue
            r = self.C[T["row"][m], T["k1"][m] - 1] / self.C[T["row"][m], T["fill"][m] - 1] - 1
            d = a[m] * T["sens"][m] * r
            out[nom] = float(d.mean() / d.std(ddof=1) * math.sqrt(len(d)))
        return out

    def challenges(self, T, a, couts, strat, jumeaux) -> tuple[np.ndarray, np.ndarray]:
        j_prem = self.premier(T) // 96 + 1
        departs = np.arange(j_prem, self.K // 96 - 1, 10) * 96
        out = []
        for signes in [np.ones(len(T["fill"]), np.int64)] + jumeaux:
            out.append(np.array([self.run(T, a, signes, int(d), self.K, 1, couts, strat) for d in departs]))
        return departs, np.stack(out)


def bilan(r: np.ndarray, departs: np.ndarray, K: int) -> dict:
    n = len(r)
    if n == 0:
        return {"departs": 0}
    j0 = departs / 96
    dernier = K / 96 - 1
    issue = r[:, 0]
    reussi = (issue == 0) & (r[:, 6] >= 0)
    mort = (issue == 1) | (issue == 2)
    d_reus = r[:, 6] - j0
    d_fin = r[:, 1] / 96 - j0
    v3, v6, v12 = (reussi & (d_reus <= x) for x in (91.3, 182.6, 365.25))
    complet = (r[:, 12] == 1) | (r[:, 9] == 1)
    assez = j0 <= dernier - 365
    garde = assez & (~v12 | complet)
    mort12 = mort & (d_fin <= 365.25) & ~v12
    valeur = np.where(v12, -PRIX + PRIX * (r[:, 11] > 0) + PART * r[:, 10], -PRIX)
    duree_fin = np.where(r[:, 9] == 1, r[:, 1] / 96 - (r[:, 6] + 1), 365.0)
    duree = np.where(v12, d_reus + duree_fin, np.where(mort12, d_fin, 365.25)) / 30.44
    retard = np.r_[(r[reussi, 5] - r[reussi, 7]), (r[reussi, 6] - r[reussi, 8])]
    retard = retard[np.isfinite(retard)]
    out = {"departs": int(n), "reussis_pct": float(reussi.mean() * 100), "morts_pct": float(mort.mean() * 100),
           "morts_etape1_pct": float((issue == 1).mean() * 100), "inacheves_24mois_pct": float((issue == 3).mean() * 100),
           "reussis_3mois_pct": float(v3.mean() * 100), "reussis_6mois_pct": float(v6.mean() * 100),
           "reussis_12mois_pct": float(v12.mean() * 100),
           "mois_reussite_median": float(np.median(d_reus[reussi]) / 30.44) if reussi.any() else None,
           "etapes_retardees_par_regle_40pct": float((retard > 0).mean() * 100) if len(retard) else None,
           "retard_moyen_jours_40pct": float(retard.mean()) if len(retard) else None,
           "fautes_3pct_par_trade": int(r[:, 15].sum()), "departs_esperance": int(garde.sum())}
    fc = v12 & complet & assez
    if fc.any():
        out["finance_cas"] = int(fc.sum())
        out["finance_survie_pct"] = float((r[fc, 9] == 0).mean() * 100)
        out["finance_gain_pct_mois"] = float((r[fc, 10] / CAP / 12 * 100).mean())
        out["finance_retraits_nb_moyen"] = float(r[fc, 11].mean())
    else:
        out["finance_cas"], out["finance_survie_pct"], out["finance_gain_pct_mois"] = 0, None, None
    if garde.any():
        out["esperance_usd"] = float(valeur[garde].mean())
        out["cycle_mois_moyen"] = float(duree[garde].mean())
        out["revenu_200k_durable_usd_mois"] = float(COMPTES_MAX * valeur[garde].mean() / duree[garde].mean())
    else:
        out["esperance_usd"] = out["cycle_mois_moyen"] = out["revenu_200k_durable_usd_mois"] = None
    if out["finance_gain_pct_mois"] is not None:
        out["revenu_200k_finances_usd_mois"] = float(COMPTES_MAX * PART * out["finance_gain_pct_mois"] / 100 * CAP)
    else:
        out["revenu_200k_finances_usd_mois"] = None
    return out


def moyenne(lst: list[dict]) -> dict:
    out = {}
    for k in lst[0]:
        v = [x[k] for x in lst if isinstance(x.get(k), (int, float)) and x.get(k) is not None]
        out[k] = float(np.mean(v)) if v else None
    return out


def ecrire(obj):
    (VIE / "resultats.json").write_text(json.dumps(obj, ensure_ascii=False, indent=1, default=str), encoding="utf-8")


def main():
    VIE.mkdir(parents=True, exist_ok=True)
    log(f"===== hyrotrader {datetime.now().isoformat(timespec='seconds')}")
    lab = Labo()
    log(f"contrôle C2 (prix d'entrée = grille UTC) : {lab.ctrl}")
    sortie = {"quand": datetime.now().isoformat(timespec="seconds"), "controle_c2": lab.ctrl, "calage": {},
              "comptes": {}}
    rng = np.random.default_rng(7)
    for strat in ("A", "B"):
        T = trades_strategie(lab.D, strat)
        n = len(T["fill"])
        un = np.ones(n, np.int64)
        jum = [rng.choice(np.array([-1, 1], np.int64), n) for _ in range(JUMEAUX)]
        log(f"=== {strat} {STRATS[strat]} : {int((T['brique'] == 0).sum())} signaux C1, "
            f"{int((T['brique'] == 1).sum())} trades C2 candidats")
        # calage (agitation seulement, coût 1, sans arrêt interne)
        a_ref = tailles(T, REF["C1"], REF["C2"])
        ag = {}
        for b, nom in ((0, "C1"), (1, "C2")) if strat == "B" else ((0, "C1"),):
            g = T["brique"] == b
            U = {k: v[g] for k, v in T.items()}
            x, _ = lab.compte(U, a_ref[g], un[g], *CALAGE[nom], COUTS["1 preneur"], strat, regles=False)
            ag[nom] = x["agitation_pct_an"] / 100
            log(f"calage {strat} {nom} ({CALAGE[nom][0]} -> {CALAGE[nom][1]}) : agitation {ag[nom] * 100:.2f} %/an "
                f"à la taille de référence {REF[nom] * 100:.2f} %")
        sortie["calage"][strat] = {k: v * 100 for k, v in ag.items()}
        for niv in NIVEAUX:
            par = niv / (math.sqrt(2) if strat == "B" else 1.0)
            r1 = REF["C1"] * par / ag["C1"]
            c = REF["C2"] * par / ag["C2"] if strat == "B" else 0.0
            a = tailles(T, r1, c)
            for nc, couts in COUTS.items():
                cle = f"{strat} | {nc} | niveau {niv * 100:.0f} %"
                res = {"strategie": STRATS[strat], "cout": nc, "niveau_pct": niv * 100, "r1_pct": r1 * 100,
                       "c2_c_pct": c * 100, "periodes": {}}
                log(f"--- {cle} : C1 r1 = {r1 * 100:.3f} % par trade, C2 c = {c * 100:.3f} %")
                for p, (de, a_) in PERIODES.items():
                    x, pris = lab.compte(T, a, un, de, a_, couts, strat)
                    x["force_jumeau"] = lab.force(T, a, pris, de, a_)
                    res["periodes"][p] = {"compte": x}
                    log(f"{p:16s} | depuis {x['debut']} | {x['gain_pct_mois']:+.2f} %/mois | baisse "
                        f"{x['baisse_max_pct']:.1f} % | pire jour {x['pire_jour_pct']:.2f} % | jours >5 % "
                        f"{x['jours_regle_5pct_cassee']} | arrêts {x['arrets_internes']} | agitation "
                        f"{x['agitation_pct_an']:.1f} | tr/mois C1 {x['trades_mois']['C1']:.0f} C2 "
                        f"{x['trades_mois']['C2']:.0f} | %/mois C1 {x['gain_pct_mois_par_brique']['C1']:+.2f} C2 "
                        f"{x['gain_pct_mois_par_brique']['C2']:+.2f} | financement C1 "
                        f"{x['financement_paye_pct_mois']['C1']:+.3f} C2 {x['financement_paye_pct_mois']['C2']:+.3f}"
                        f" | force {x['force_jumeau']} | ign {x['ignores']}")
                departs, R = lab.challenges(T, a, couts, strat, jum)
                np.save(CACHE / f"challenges_{strat}_{nc[0]}_{int(niv * 100)}.npy", R)
                dates = G0 + pd.to_timedelta(departs // 96, unit="D")
                for p, (de, a_) in PERIODES.items():
                    msk = np.asarray((dates >= pd.Timestamp(de)) & (dates < pd.Timestamp(a_)))
                    v = bilan(R[0][msk], departs[msk], lab.K)
                    jm = moyenne([bilan(R[i][msk], departs[msk], lab.K) for i in range(1, len(R))])
                    res["periodes"][p]["challenges"] = {"vrai": v, "jumeaux": jm}
                    if v["departs"] == 0:
                        continue
                    log(f"{p:16s} | chall {v['departs']} : réussis {v['reussis_pct']:.0f} % morts {v['morts_pct']:.0f} %"
                        f" (jum {jm['reussis_pct']:.0f}/{jm['morts_pct']:.0f}) | <3 m {v['reussis_3mois_pct']:.0f} % <6 m "
                        f"{v['reussis_6mois_pct']:.0f} % <12 m {v['reussis_12mois_pct']:.0f} % | 40 % : "
                        f"{v['etapes_retardees_par_regle_40pct']} % retardées, {v['retard_moyen_jours_40pct']} j | "
                        f"financé {v['finance_cas']} survie {v['finance_survie_pct']} gain/mois "
                        f"{v['finance_gain_pct_mois']} | espérance {v['esperance_usd']} $ (jum {jm['esperance_usd']}) "
                        f"sur {v['departs_esperance']} | 200 k$ durable {v['revenu_200k_durable_usd_mois']} $/mois, "
                        f"financés {v['revenu_200k_finances_usd_mois']} | fautes 3 % {v['fautes_3pct_par_trade']}")
                sortie["comptes"][cle] = res
                ecrire(sortie)
    log("FINI")


SENSIBILITES = {"cahier (plus haut au meilleur prix, retrait hebdo >= 125 $)": (False, 125.0, 7),
                "plus haut du jour à la clôture des bougies": (True, 125.0, 7),
                "retrait seulement quand le gain atteint 5 % (regard chaque jour)": (False, 5000.0, 1),
                "les deux": (True, 5000.0, 1)}


def sensibilite():
    """AJOUT APRÈS LECTURE (information seulement, aucun choix) : effet de deux lectures des règles."""
    log(f"===== sensibilité {datetime.now().isoformat(timespec='seconds')}")
    lab = Labo()
    res = json.loads((VIE / "resultats.json").read_text(encoding="utf-8"))
    out = {}
    for strat in ("A", "B"):
        T = trades_strategie(lab.D, strat)
        for cle, x in res["comptes"].items():
            if not cle.startswith(strat):
                continue
            a = tailles(T, x["r1_pct"] / 100, x["c2_c_pct"] / 100)
            couts = COUTS[x["cout"]]
            j_prem = lab.premier(T) // 96 + 1
            departs = np.arange(j_prem, lab.K // 96 - 1, 10) * 96
            dates = G0 + pd.to_timedelta(departs // 96, unit="D")
            un = np.ones(len(T["fill"]), np.int64)
            out[cle] = {}
            for nom, s in SENSIBILITES.items():
                R = np.array([lab.run(T, a, un, int(d), lab.K, 1, couts, strat, sens_=s) for d in departs])
                out[cle][nom] = {}
                for p, (de, a_) in PERIODES.items():
                    msk = np.asarray((dates >= pd.Timestamp(de)) & (dates < pd.Timestamp(a_)))
                    v = bilan(R[msk], departs[msk], lab.K)
                    out[cle][nom][p] = {k: v.get(k) for k in ("reussis_pct", "morts_pct", "reussis_12mois_pct",
                                                              "finance_cas", "finance_survie_pct",
                                                              "finance_gain_pct_mois", "esperance_usd",
                                                              "revenu_200k_durable_usd_mois")}
                log(f"{cle:34s} | {nom[:40]:40s} | " + " | ".join(
                    f"{p} réussis {w['reussis_pct']:.0f} % morts {w['morts_pct']:.0f} % survie financé "
                    f"{w['finance_survie_pct']} esp {None if w['esperance_usd'] is None else round(w['esperance_usd'])} $"
                    for p, w in out[cle][nom].items()))
    (VIE / "sensibilite.json").write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    log("FINI sensibilité")


if __name__ == "__main__":
    sensibilite() if len(sys.argv) > 1 and sys.argv[1] == "sensibilite" else main()
