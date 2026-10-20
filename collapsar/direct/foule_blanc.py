"""SUIVI À BLANC de la version « compte financé » de C1 (piste crypto_flux : comptes acheteurs extrêmes, contraire)
— 16/10/2026.

AUCUN ordre, AUCUN accès MetaTrader, AUCUNE clé, AUCUN message téléphone. Deux comptes FICTIFS de 100 000 $.

Données (API publiques Binance, contrats perpétuels USD-M, sans compte) :
- part des comptes acheteurs : futures/data/globalLongShortAccountRatio (5 min, 30 DERNIERS JOURS seulement), raccordée
  à l'historique data/binance_futures/metrics (fichiers journaliers jusqu'au 14/10/2026 UTC) et conservée dans
  vie/direct/foule_historique/<SYM>.csv (colonnes utc_ms = convention des fichiers, api_ms = horodatage de l'API,
  ratio = acheteurs / vendeurs = count_long_short_ratio, part_acheteurs, source). Mesuré le 16/10 :
  fichier(T - 5 min) = API(T), donc utc_ms = api_ms - 5 min. Raccord sans doublon (une ligne par utc_ms, l'historique
  d'abord) ; TOUT trou de la série (pas de 5 min manquant) est signalé au journal ;
- prix : bougies 1 h du perpétuel (fapi/v1/klines ; clôture, plus haut, plus bas de l'heure) ;
- financement réel : fapi/v1/fundingRate.

Règles : EXACTEMENT celles figées dans regarder/pistes/crypto_flux.py (signal C1) et crypto_flux_compte.py (point 2,
« compte financé ») ; le signal appelle cf.centile, les constantes viennent de ces deux fichiers :
- à chaque fin d'heure UTC h : part des comptes connue à h (ligne des fichiers datée <= h - 15 min, au plus 1 h, soit
  la valeur d'horodatage API h - 10 min) ; >= centile 95 des 90 jours passés -> vente ; <= centile 5 -> achat ;
- 17 cryptos (ordre fixe de cfc.MARCHES) ; risque 150 $ (0,15 % du départ) ; stop 1,5 x agitation journalière
  (écart type des rendements horaires des 14 jours passés x racine(24)) ; montant = 150 / (1,5 x agitation) ; stop vu
  sur le plus haut / plus bas de l'heure, exécuté au prix du stop ; 5 positions au plus dont 3 dans le même sens,
  1 par crypto ; arrêt du jour serveur à -2 % (fonds au plus mauvais prix de l'heure) : tout fermé, plus d'entrée ;
  sortie à 24 h à la clôture.
- Comptabilités en parallèle (deux comptes indépendants, mêmes signaux) :
  ftmo   : frais aller-retour cf.frais (BTC 0,083 %, ETH 0,112 %, autres 0,12 % = commission 0,0325 %/côté + écart),
           moitié à l'entrée, moitié à la sortie ; nuit 30 %/an / 360 par minuit serveur franchi ;
  bourse : 0,05 %/côté + financement réel à chaque règlement (entrée < règlement <= heure traitée).
- Seule différence avec le test : prix du perpétuel au lieu du comptant (mesuré identique dans la recherche du défaut).
Calendrier : toutes les 5 min (vers :00:30, :05:30...) lecture de la foule ; l'heure h est traitée dès h + 5 min
(attente au plus 30 min d'une donnée manquante, puis traitée avec ce qui existe et le trou est signalé).
Le compte commence à la première heure pleine après le premier lancement ; après un arrêt, les heures manquées sont
rattrapées dans l'ordre.

Fichiers : journal vie/logs/foule_blanc.txt, état vie/direct/foule_blanc.json, trades vie/direct/foule_blanc_trades.csv,
contrôle vie/direct/foule_blanc_rejeu.json. Arrêt volontaire : vie/direct/FOULE_ARRET.
Contrôle avant lancement : --rejouer (25 derniers jours, données de l'API) : signaux du programme heure par heure
(données tronquées à ce qui était connu) contre crypto_flux.caracteristiques + signaux calculés sur les mêmes données,
et compte du programme contre crypto_flux_compte.simuler. --essai : une heure, rien n'est écrit sauf le journal.
Depuis Test_IA : venv_gpu\\Scripts\\python.exe -u -m collapsar.direct.foule_blanc [--essai | --rejouer]
"""
from __future__ import annotations

import json
import math
import os
import shutil
import sys
import tempfile
import time
import traceback
from datetime import datetime

import numpy as np
import pandas as pd
import requests

from collapsar.donnees import marches as dm
from collapsar.regarder.pistes import crypto_flux as cf
from collapsar.regarder.pistes import crypto_flux_compte as cfc

MARCHES = list(cfc.MARCHES)
CAP, RISQUE_USD, K_STOP = cfc.CAP, cfc.RISQUE_USD, cfc.K_STOP
MAXPOS, MAXSENS, STOP_JOUR = cfc.MAXPOS, cfc.MAXSENS, cfc.STOP_JOUR
TENUE = pd.Timedelta(hours=cfc.TENUE)
NUIT_JOUR = cf.NUIT_AN / 360.0
COMPTAS = {"ftmo": {"frais": {s: cf.frais(s) for s in MARCHES}, "nuit": True, "financement": False},
           "bourse": {"frais": {s: 0.0010 for s in MARCHES}, "nuit": False, "financement": True}}

FAPI = "https://fapi.binance.com"
H = pd.Timedelta(hours=1)
M5 = pd.Timedelta(minutes=5)
DECALAGE_FICHIER = M5                       # fichier(T - 5 min) = API(T)
CONNU_APRES = M5                            # une ligne d'horodatage API T est publiée au plus tard vers T + 5 min
DELAI_TRAITEMENT = M5                       # l'heure h est traitée à partir de h + 5 min
ATTENTE_MAX = pd.Timedelta(minutes=30)
DEBUT_HIST = pd.Timestamp("2026-05-01")     # assez pour 90 jours + rejeu de 25 jours
API_JOURS = pd.Timedelta(days=29, hours=23)
HEURES_PRIX = 400                           # 14 jours d'agitation + marge
JOURS_REJEU = 25

FICHIERS = dm.RACINE / "data" / "binance_futures" / "metrics"
DOSSIER = dm.RACINE / "collapsar" / "vie" / "direct"
HIST = DOSSIER / "foule_historique"
ETAT = DOSSIER / "foule_blanc.json"
TRADES = DOSSIER / "foule_blanc_trades.csv"
REJEU = DOSSIER / "foule_blanc_rejeu.json"
ARRET = DOSSIER / "FOULE_ARRET"
VERROU = DOSSIER / "foule_blanc.verrou"
JOURNAL = dm.RACINE / "collapsar" / "vie" / "logs" / "foule_blanc.txt"
ENTETE_TRADES = ("compta,marche,sens,entree_utc,sortie_utc,prix_entree,prix_sortie,montant_usd,rendement_brut_pct,"
                 "frais_usd,nuits_financement_usd,resultat_usd,sortie\n")
_PREFIXE = ""


def log(texte: str) -> None:
    ligne = f"[{datetime.now():%d/%m %H:%M:%S}] {_PREFIXE}{texte}"
    print(ligne, flush=True)
    JOURNAL.parent.mkdir(parents=True, exist_ok=True)
    with JOURNAL.open("a", encoding="utf-8") as f:
        f.write(ligne + "\n")


def usd(x: float) -> str:
    return f"{x:,.0f}".replace(",", " ")


def maintenant() -> pd.Timestamp:
    return pd.Timestamp.now("UTC").tz_localize(None)


def ms(t) -> int:
    return int(pd.Timestamp(t).value // 10 ** 6)


def jour_serveur(h: pd.Timestamp) -> str:
    return str(cf.serveur(pd.DatetimeIndex([h]))[0].normalize().date())


# ---------------------------------------------------------------- API publique
_S = requests.Session()


def _get(chemin: str, params: dict, pause: float = 0.2):
    err = None
    for essai in range(6):
        try:
            r = _S.get(FAPI + chemin, params=params, timeout=20)
        except requests.RequestException as e:
            err = e
            time.sleep(5 * (essai + 1))
            continue
        if r.status_code in (418, 429) or r.status_code >= 500:
            err = f"HTTP {r.status_code}"
            time.sleep(60 if r.status_code in (418, 429) else 5 * (essai + 1))
            continue
        j = r.json()
        if r.status_code != 200 or (isinstance(j, dict) and "code" in j):
            raise RuntimeError(f"Binance {chemin} {params} : {j}")
        time.sleep(pause)
        return j
    raise RuntimeError(f"Binance injoignable ({chemin}) : {err}")


def foule_api(sym: str, depuis: pd.Timestamp) -> pd.DataFrame:
    """Lignes 5 min de l'API d'horodatage >= depuis (au plus 30 jours en arrière). Colonnes : utc_ms (convention des
    fichiers), api_ms, ratio, part_acheteurs, source."""
    now = maintenant()
    debut = max(pd.Timestamp(depuis), now - API_JOURS).ceil("5min")
    lignes, s, fin = [], ms(debut), ms(now)
    while s <= fin:
        e = s + 499 * 300_000
        lignes += _get("/futures/data/globalLongShortAccountRatio",
                       {"symbol": sym, "period": "5m", "limit": 500, "startTime": s, "endTime": e})
        s = e + 300_000
    if not lignes:
        return pd.DataFrame(columns=["utc_ms", "api_ms", "ratio", "part_acheteurs", "source"])
    d = pd.DataFrame(lignes)
    api = d["timestamp"].astype("int64")
    out = pd.DataFrame({"utc_ms": api - 300_000, "api_ms": api, "ratio": d["longShortRatio"].astype(float),
                        "part_acheteurs": d["longAccount"].astype(float), "source": "direct"})
    return out.drop_duplicates("api_ms", keep="last").sort_values("api_ms").reset_index(drop=True)


def klines(sym: str, intervalle: str, debut: pd.Timestamp) -> pd.DataFrame:
    """Bougies CLOSES du perpétuel depuis l'ouverture `debut`. Index = fin de la bougie (UTC)."""
    pas = pd.Timedelta(intervalle.replace("m", "min"))
    now_ms = ms(maintenant())
    lignes, s = [], ms(debut)
    while True:
        j = _get("/fapi/v1/klines", {"symbol": sym, "interval": intervalle, "startTime": s, "limit": 1500}, pause=0.3)
        if not j:
            break
        lignes += j
        if len(j) < 1500:
            break
        s = int(j[-1][0]) + 1
    d = pd.DataFrame([x[:11] for x in lignes], columns=["ouv", "open", "high", "low", "close", "volume", "ferm",
                                                       "qv", "count", "taker_buy_volume", "tbq"])
    d = d[d["ferm"].astype("int64") < now_ms].drop_duplicates("ouv", keep="last")
    out = pd.DataFrame({c: d[c].astype(float).to_numpy() for c in ("open", "high", "low", "close", "volume",
                                                                    "taker_buy_volume")},
                       index=pd.DatetimeIndex(pd.to_datetime(d["ouv"].astype("int64"), unit="ms")).astype("datetime64[ns]") + pas)
    out["utc_ms"] = d["ouv"].astype("int64").to_numpy()
    return out.sort_index()


def financement(sym: str, debut: pd.Timestamp, fin: pd.Timestamp) -> pd.Series:
    """Taux réglés entre debut et fin, rangés à l'heure (ceil) de leur règlement arrondi à la seconde, comme
    crypto_flux_compte.preparer."""
    lignes, s = [], ms(debut)
    while True:
        j = _get("/fapi/v1/fundingRate", {"symbol": sym, "startTime": s, "endTime": ms(fin), "limit": 1000})
        lignes += j
        if len(j) < 1000:
            break
        s = int(j[-1]["fundingTime"]) + 1
    if not lignes:
        return pd.Series(dtype=float)
    t = pd.DatetimeIndex(pd.to_datetime(np.array([int(x["fundingTime"]) for x in lignes]) // 1000, unit="s")).astype("datetime64[ns]")
    fs = pd.Series([float(x["fundingRate"]) for x in lignes], index=t).groupby(level=0).sum().sort_index()
    return fs.groupby(fs.index.ceil("h")).sum()


# ---------------------------------------------------------------- historique de la foule (raccord)
def historique_fichier(sym: str) -> pd.DataFrame:
    me = pd.read_csv(FICHIERS / f"{sym}.csv", usecols=["utc_ms", "count_long_short_ratio"])
    me = me[(me["utc_ms"] >= ms(DEBUT_HIST)) & np.isfinite(me["count_long_short_ratio"])
            & (me["count_long_short_ratio"] > 0)]
    me = me.drop_duplicates("utc_ms", keep="last").sort_values("utc_ms")
    return pd.DataFrame({"utc_ms": me["utc_ms"].astype("int64").to_numpy(),
                         "api_ms": (me["utc_ms"] + 300_000).astype("int64").to_numpy(),
                         "ratio": me["count_long_short_ratio"].to_numpy(float), "part_acheteurs": np.nan,
                         "source": "fichier"})


def trous(utc_ms: np.ndarray) -> list[tuple[pd.Timestamp, pd.Timestamp, int]]:
    """(dernière valeur avant, première après, valeurs 5 min manquantes) pour chaque saut > 5 min."""
    u = np.asarray(utc_ms, np.int64)
    k = np.flatnonzero(np.diff(u) > 300_000)
    return [(pd.Timestamp(int(u[i]), unit="ms"), pd.Timestamp(int(u[i + 1]), unit="ms"),
             int((u[i + 1] - u[i]) // 300_000 - 1)) for i in k]


def _dire_trous(sym: str, liste, ou: str, etat: dict | None) -> None:
    for a, b, n in liste[:20]:
        texte = (f"TROU foule {sym} ({ou}) : rien entre {a:%d/%m %H:%M} et {b:%d/%m %H:%M} UTC (convention fichier), "
                 f"{n} valeur(s) de 5 min manquante(s)")
        log(texte)
        if etat is not None:
            etat.setdefault("trous", []).append(f"{datetime.now():%d/%m %H:%M} {texte}")
            etat["trous"] = etat["trous"][-50:]
    if len(liste) > 20:
        log(f"TROU foule {sym} ({ou}) : ... et {len(liste) - 20} autres trous")


def raccorder(sym: str, store: pd.DataFrame | None = None, ecrire: bool = True, etat: dict | None = None,
              bavard: bool = False) -> pd.DataFrame:
    """Charge (ou crée depuis l'historique) la série de la foule et y ajoute les nouvelles lignes de l'API, sans
    doublon ; signale tout trou."""
    f = HIST / f"{sym}.csv"
    init = False
    if store is None:
        if f.exists():
            store = pd.read_csv(f)
            bavard = True
        else:
            store = historique_fichier(sym)
            init = True
            h_tr = [x for x in trous(store["utc_ms"].to_numpy())]
            log(f"{sym} : historique fichiers {pd.Timestamp(int(store['utc_ms'].iloc[0]), unit='ms'):%d/%m/%Y} -> "
                f"{pd.Timestamp(int(store['utc_ms'].iloc[-1]), unit='ms'):%d/%m/%Y %H:%M} UTC, {len(store)} lignes, "
                f"{len(h_tr)} trou(s) dans l'historique gardé")
            _dire_trous(sym, h_tr, "historique fichiers", etat)
    dernier = int(store["utc_ms"].iloc[-1])
    depuis_api = pd.Timestamp(dernier + 300_000, unit="ms") + DECALAGE_FICHIER     # horodatage API de la ligne suivante
    neuf = foule_api(sym, maintenant() - API_JOURS if init else depuis_api)
    if init and len(neuf):
        com = store.merge(neuf[["utc_ms", "ratio"]], on="utc_ms", suffixes=("", "_api"))
        ecart = float((com["ratio"] - com["ratio_api"]).abs().max()) if len(com) else float("nan")
        log(f"{sym} : chevauchement fichiers / API {len(com)} lignes, écart max du ratio {ecart:.4f} "
            f"(l'API arrondit à 4 décimales)")
    ajout = neuf[neuf["utc_ms"] > dernier]
    if len(ajout):
        tr = trous(np.r_[dernier, ajout["utc_ms"].to_numpy(np.int64)])
        _dire_trous(sym, tr, "raccord historique / direct" if init else "direct", etat)
        if init or bavard:
            log(f"{sym} : +{len(ajout)} valeurs de l'API, jusqu'à {pd.Timestamp(int(ajout['api_ms'].iloc[-1]), unit='ms'):%d/%m %H:%M} UTC"
                f"{'' if tr else ', raccord sans trou'}")
        store = pd.concat([store, ajout], ignore_index=True)
    if ecrire:
        HIST.mkdir(parents=True, exist_ok=True)
        if init or not f.exists():
            store.to_csv(f, index=False)
        elif len(ajout):
            ajout.to_csv(f, mode="a", header=False, index=False)
    return store


# ---------------------------------------------------------------- signal C1 (règle figée)
def serie_horaire(store: pd.DataFrame, grille: pd.DatetimeIndex) -> pd.Series:
    """Part des comptes connue à chaque fin d'heure : comme crypto_flux.caracteristiques (ligne datée T utilisée si
    T + 15 min <= h, au plus 1 h)."""
    x = pd.DataFrame({"t": pd.DatetimeIndex(pd.to_datetime(store["utc_ms"].to_numpy(np.int64), unit="ms")).astype("datetime64[ns]") + pd.Timedelta(minutes=15),
                      "c": store["ratio"].to_numpy(float)})
    x = x[np.isfinite(x["c"]) & (x["c"] > 0)].sort_values("t")
    m = pd.merge_asof(pd.DataFrame({"h": grille}), x, left_on="h", right_on="t", direction="backward",
                      tolerance=pd.Timedelta(hours=1))
    return pd.Series(m["c"].to_numpy(), index=grille)


def signal_c1(store: pd.DataFrame, h: pd.Timestamp) -> dict:
    """Sens C1 à la fin d'heure h (+1 achat, -1 vente, 0 rien), avec seulement les 90 jours passés."""
    grille = pd.date_range(h - cf.W90 * H, h, freq="h").astype("datetime64[ns]")
    deb = ms(grille[0] - 2 * H)
    u = store["utc_ms"].to_numpy(np.int64)
    c = serie_horaire(store.iloc[int(np.searchsorted(u, deb)):], grille)
    b, v = cf.centile(c, .05, cf.W90).iloc[-1], cf.centile(c, .95, cf.W90).iloc[-1]
    x = c.iloc[-1]
    achat, vente = bool(x <= b), bool(x >= v)            # NaN -> faux, comme cf.signaux
    return {"sens": 1 if achat and not vente else -1 if vente and not achat else 0, "ratio": float(x),
            "c05": float(b), "c95": float(v)}


# ---------------------------------------------------------------- prix
def prix_assurer(cache: dict, sym: str, depuis: pd.Timestamp) -> None:
    d = cache.get(sym)
    if d is None or d.index.min() > depuis:
        cache[sym] = klines(sym, "1h", depuis - H)
        return
    neuf = klines(sym, "1h", d.index.max() - H)
    d = pd.concat([d, neuf])
    d = d[~d.index.duplicated(keep="last")].sort_index()
    cache[sym] = d.iloc[-3000:]


def entrees_heure(d: pd.DataFrame, h: pd.Timestamp) -> dict:
    """Clôture (et celle de l'heure d'avant), plus haut, plus bas, agitation journalière à h — comme
    caracteristiques (prix du perpétuel) + preparer."""
    grille = pd.date_range(h - HEURES_PRIX * H, h, freq="h")
    cl = d["close"].reindex(grille)
    lr = np.log(cl).diff()
    agit = lr.rolling(14 * 24, min_periods=7 * 24).std().iloc[-1]
    cf_ = cl.ffill()
    return {"C": float(cf_.iloc[-1]), "Cp": float(cf_.iloc[-2]), "Hh": float(d["high"].get(h, np.nan)),
            "Lw": float(d["low"].get(h, np.nan)), "SD": float(agit * math.sqrt(24))}


# ---------------------------------------------------------------- compte fictif (= crypto_flux_compte.simuler)
class Compte:
    def __init__(self, nom: str, d: dict | None = None):
        d = d or {}
        self.nom = nom
        self.solde = float(d.get("solde", 0.0))                        # gain cumulé en $ (départ 100 000 $)
        self.pos = d.get("positions", {})
        for p in self.pos.values():
            p["t0"] = pd.Timestamp(p["t0"])
        self.jour = d.get("jour")
        self.arret = bool(d.get("arret", False))
        self.jours = d.get("jours", {})                                # jour serveur -> [début, plus bas, fin, entrées]
        self.n_trades = int(d.get("n_trades", 0))

    def vers_dict(self, X: dict | None = None) -> dict:
        pos = {}
        for s, p in self.pos.items():
            q = dict(p, t0=str(p["t0"]))
            if X and s in X and np.isfinite(X[s]["C"]):
                q["latent_usd"] = round(p["montant"] * p["sens"] * (X[s]["C"] / p["pe"] - 1.0), 2)
                q["prix"] = X[s]["C"]
            pos[s] = q
        fonds = self.jours.get(self.jour, [None, None, None])[2] if self.jour else 0.0
        return {"solde": self.solde, "fonds_usd": None if fonds is None else CAP + fonds, "jour": self.jour,
                "arret": self.arret, "positions": pos, "jours": self.jours, "n_trades": self.n_trades}

    def _latent(self, X: dict, cle: str) -> float:
        return sum(p["montant"] * p["sens"] * (X[s][cle] / p["pe"] - 1.0) for s, p in self.pos.items())

    def _fermer(self, s: str, x: float, h: pd.Timestamp, ty: str, fr: float, sortie: list) -> None:
        p = self.pos.pop(s)
        g = p["sens"] * (x / p["pe"] - 1.0)
        self.solde += p["montant"] * (g - fr * 0.5)
        self.n_trades += 1
        sortie.append({"compta": self.nom, "marche": s, "sens": p["sens"], "entree": p["t0"], "sortie": h,
                       "prix_entree": p["pe"], "prix_sortie": x, "montant": p["montant"], "g": g,
                       "frais": p["montant"] * fr, "couts": p["couts"],
                       "resultat": p["montant"] * (g - fr) - p["couts"], "type": ty})

    def heure(self, h: pd.Timestamp, jour: str, X: dict, sig: dict, fun: dict) -> tuple[list, list]:
        """Une fin d'heure, pas à pas comme crypto_flux_compte.simuler (même ordre des opérations)."""
        regle = COMPTAS[self.nom]
        fr = regle["frais"]
        sorties, ouvertes = [], []
        if jour != self.jour:
            if self.jour is not None:
                self.jours[self.jour][2] = self.solde + self._latent(X, "Cp")
                if regle["nuit"]:
                    nd = (pd.Timestamp(jour) - pd.Timestamp(self.jour)).days
                    for p in self.pos.values():
                        c = p["montant"] * NUIT_JOUR * nd
                        self.solde -= c
                        p["couts"] += c
            eq = self.solde + self._latent(X, "Cp")
            self.jours[jour] = [eq, eq, eq, 0]
            self.jour = jour
            self.arret = False
        jo = self.jours[jour]
        if regle["financement"]:
            for s, p in self.pos.items():
                if p["t0"] < h:
                    c = p["montant"] * p["sens"] * fun.get(s, 0.0)
                    self.solde -= c
                    p["couts"] += c
        for s in MARCHES:                                              # sorties : stop puis temps
            if s not in self.pos:
                continue
            p, x, ty = self.pos[s], -1.0, "temps"
            if p["sens"] > 0 and X[s]["Lw"] <= p["stp"]:
                x, ty = p["stp"], "stop"
            elif p["sens"] < 0 and X[s]["Hh"] >= p["stp"]:
                x, ty = p["stp"], "stop"
            elif h >= p["t0"] + TENUE:
                x = X[s]["C"]
            if x > 0:
                self._fermer(s, x, h, ty, fr[s], sorties)
        pire, pires = self.solde, {}                                   # fonds au plus mauvais prix de l'heure
        for s in MARCHES:
            if s in self.pos:
                p = self.pos[s]
                w = X[s]["Lw"] if p["sens"] > 0 else X[s]["Hh"]
                if not (w > 0):
                    w = X[s]["C"]
                pires[s] = w
                pire += p["montant"] * p["sens"] * (w / p["pe"] - 1.0)
        if pire < jo[1]:
            jo[1] = pire
        if (not self.arret) and pire - jo[0] <= -STOP_JOUR:
            self.arret = True
            for s in MARCHES:
                if s in self.pos:
                    self._fermer(s, pires[s], h, "arrêt du jour", fr[s], sorties)
        if not self.arret:                                             # entrées
            n_ouv = len(self.pos)
            n_achat = sum(1 for p in self.pos.values() if p["sens"] > 0)
            for s in MARCHES:
                if sig[s]["sens"] == 0 or s in self.pos:
                    continue
                if not (X[s]["C"] > 0 and X[s]["SD"] > 0):
                    continue
                dr = sig[s]["sens"]
                if n_ouv >= MAXPOS:
                    break
                if dr > 0 and n_achat >= MAXSENS:
                    continue
                if dr < 0 and (n_ouv - n_achat) >= MAXSENS:
                    continue
                pe, sd = X[s]["C"], X[s]["SD"]
                p = {"sens": dr, "pe": pe, "montant": RISQUE_USD / (K_STOP * sd), "stp": pe * (1.0 - dr * K_STOP * sd),
                     "t0": h, "couts": 0.0}
                self.solde -= p["montant"] * fr[s] * 0.5
                self.pos[s] = p
                ouvertes.append((s, p))
                n_ouv += 1
                n_achat += dr > 0
                jo[3] += 1
        jo[2] = self.solde + self._latent(X, "C")
        return sorties, ouvertes


def ecrire_trades(sorties: list) -> None:
    if not sorties:
        return
    neuf = not TRADES.exists()
    with TRADES.open("a", encoding="utf-8") as f:
        if neuf:
            f.write(ENTETE_TRADES)
        for t in sorties:
            f.write(f"{t['compta']},{t['marche']},{'achat' if t['sens'] > 0 else 'vente'},{t['entree']:%Y-%m-%d %H:%M},"
                    f"{t['sortie']:%Y-%m-%d %H:%M},{t['prix_entree']:.8g},{t['prix_sortie']:.8g},{t['montant']:.2f},"
                    f"{t['g'] * 100:.4f},{t['frais']:.2f},{t['couts']:.2f},{t['resultat']:.2f},{t['type']}\n")


# ---------------------------------------------------------------- une heure
def pret(h: pd.Timestamp, stores: dict, cache: dict, now: pd.Timestamp) -> tuple[bool, list, list]:
    besoin = ms(h - 10 * pd.Timedelta(minutes=1))                     # ligne API h - 10 min (= fichier h - 15 min)
    manque_f = [s for s in MARCHES if int(stores[s]["api_ms"].iloc[-1]) < besoin]
    manque_p = [s for s in MARCHES if s not in cache or cache[s].index.max() < h]
    if (manque_f or manque_p) and now < h + ATTENTE_MAX:
        return False, manque_f, manque_p
    return True, manque_f, manque_p


def traiter_heure(h: pd.Timestamp, stores: dict, cache: dict, comptes: dict, ecrire: bool = True) -> dict:
    jour = jour_serveur(h)
    sig = {s: signal_c1(stores[s], h) for s in MARCHES}
    X = {s: entrees_heure(cache[s], h) for s in MARCHES}
    fun = {}
    ouvertes_b = [s for s, p in comptes["bourse"].pos.items() if p["t0"] < h]
    for s in ouvertes_b:
        f = financement(s, h - 2 * H, h + pd.Timedelta(minutes=1))
        fun[s] = float(f.get(h, 0.0))
    texte = []
    for nom, c in comptes.items():
        sorties, ouvertes = c.heure(h, jour, X, sig, fun)
        if ecrire:
            ecrire_trades(sorties)
        for t in sorties:
            texte.append(f"{nom} sortie {t['marche'][:-4]} {'achat' if t['sens'] > 0 else 'vente'} ({t['type']}) "
                         f"{t['resultat']:+.0f} $")
        for s, p in ouvertes:
            texte.append(f"{nom} ENTRÉE {s[:-4]} {'achat' if p['sens'] > 0 else 'vente'} à {p['pe']:.6g}, "
                         f"{p['montant']:.0f} $, stop {p['stp']:.6g}")
    sg = " ".join(f"{s[:-4]}{'+' if x['sens'] > 0 else '-'}" for s, x in sig.items() if x["sens"])
    log(f"{h:%d/%m %H}h UTC (jour serveur {jour}) | signaux : {sg or 'aucun'} | "
        + " | ".join(f"{n} fonds {usd(CAP + c.jours[jour][2])} $ ({len(c.pos)} pos.)" for n, c in comptes.items())
        + ("" if not texte else " | " + " ; ".join(texte)))
    return {"heure": str(h), "signaux": {s[:-4]: x for s, x in sig.items() if x["sens"]}, "X": X}


# ---------------------------------------------------------------- boucle en direct
def ecrire_etat(etat: dict) -> None:
    tmp = ETAT.with_suffix(".tmp")
    tmp.write_text(json.dumps(etat, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    os.replace(tmp, ETAT)


def prendre_verrou():
    import msvcrt
    f = open(VERROU, "a+")
    try:
        msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
    except OSError:
        log("une autre instance du suivi à blanc tourne déjà : sortie")
        sys.exit(0)
    return f


def boucle() -> None:
    DOSSIER.mkdir(parents=True, exist_ok=True)
    verrou = prendre_verrou()
    etat = json.loads(ETAT.read_text(encoding="utf-8")) if ETAT.exists() else {}
    if not etat:
        etat = {"debut": str(maintenant()), "prochaine_heure": str(maintenant().ceil("h")), "comptes": {},
                "trous": []}
    comptes = {n: Compte(n, etat["comptes"].get(n)) for n in COMPTAS}
    log(f"démarrage du suivi à blanc C1 (AUCUN ordre) ; prochaine heure traitée {etat['prochaine_heure']} UTC ; "
        f"positions ftmo {len(comptes['ftmo'].pos)}, bourse {len(comptes['bourse'].pos)}")
    stores, cache, arret_dit = {}, {}, False
    while True:
        if ARRET.exists():
            if not arret_dit:
                log("FOULE_ARRET présent : suivi en pause")
                arret_dit = True
            time.sleep(60)
            continue
        arret_dit = False
        try:
            now = maintenant()
            for s in MARCHES:
                stores[s] = raccorder(s, stores.get(s), ecrire=True, etat=etat)
            h = pd.Timestamp(etat["prochaine_heure"])
            while maintenant() >= h + DELAI_TRAITEMENT:
                for s in MARCHES:
                    prix_assurer(cache, s, h - HEURES_PRIX * H)
                ok, mf, mp = pret(h, stores, cache, maintenant())
                if not ok:
                    break
                if mf:
                    log(f"TROU {h:%d/%m %H}h : foule absente pour {', '.join(mf)} (traité avec la dernière valeur "
                        f"de moins d'1 h, sinon pas de signal)")
                if mp:
                    log(f"TROU {h:%d/%m %H}h : prix absent pour {', '.join(mp)} (dernière clôture reprise)")
                r = traiter_heure(h, stores, cache, comptes)
                h = h + H
                etat["prochaine_heure"] = str(h)
                etat["derniere_heure"] = r["heure"]
                etat["signaux_derniere_heure"] = r["signaux"]
                etat["comptes"] = {n: c.vers_dict(r["X"]) for n, c in comptes.items()}
                ecrire_etat(etat)
            etat["derniere_lecture"] = str(maintenant())
            etat["foule"] = {s[:-4]: {"derniere_api_utc": str(pd.Timestamp(int(stores[s]["api_ms"].iloc[-1]), unit="ms")),
                                      "ratio": float(stores[s]["ratio"].iloc[-1]),
                                      "part_acheteurs": float(stores[s]["part_acheteurs"].iloc[-1])}
                             for s in MARCHES}
            ecrire_etat(etat)
        except Exception as e:
            log(f"erreur {type(e).__name__}: {e} | {traceback.format_exc(limit=3).splitlines()[-2].strip()}")
        now = maintenant()
        prochain = now.floor("5min") + M5 + pd.Timedelta(seconds=30)
        time.sleep(max(5.0, (prochain - now).total_seconds()))
    verrou.close()


# ---------------------------------------------------------------- essai
def essai() -> None:
    global _PREFIXE
    _PREFIXE = "[essai] "
    now = maintenant()
    h = (now - DELAI_TRAITEMENT).floor("h")
    stores = {s: raccorder(s, None, ecrire=False) for s in MARCHES}
    cache = {}
    for s in MARCHES:
        prix_assurer(cache, s, h - HEURES_PRIX * H)
    ok, mf, mp = pret(h, stores, cache, now + ATTENTE_MAX)
    log(f"heure {h} UTC ; foule manquante {mf or 'aucune'} ; prix manquants {mp or 'aucun'}")
    for s in MARCHES:
        sg, X = signal_c1(stores[s], h), entrees_heure(cache[s], h)
        log(f"{s:9s} ratio {sg['ratio']:.4f} (c5 {sg['c05']:.4f}, c95 {sg['c95']:.4f}) -> "
            f"{['vente', 'rien', 'achat'][sg['sens'] + 1]:5s} | prix {X['C']:.6g} | agitation/jour {X['SD'] * 100:.2f} % "
            f"| montant si trade {RISQUE_USD / (K_STOP * X['SD']):.0f} $")
    comptes = {n: Compte(n) for n in COMPTAS}
    traiter_heure(h, stores, cache, comptes, ecrire=False)
    log("essai terminé (rien d'écrit sauf ce journal)")


# ---------------------------------------------------------------- contrôle : rejouer les 25 derniers jours
def rejouer(jours: int = JOURS_REJEU) -> dict:
    global _PREFIXE
    _PREFIXE = "[rejeu] "
    t_debut = time.time()
    now = maintenant()
    log(f"contrôle : {jours} derniers jours, données de l'API ; rien n'est écrit dans l'historique ni dans l'état")
    stores = {s: raccorder(s, None, ecrire=False) for s in MARCHES}
    h_fin = (now - DELAI_TRAITEMENT).floor("h")
    for s in MARCHES:
        h_fin = min(h_fin, (pd.Timestamp(int(stores[s]["api_ms"].iloc[-1]), unit="ms") + pd.Timedelta(minutes=10)).floor("h"))
    heures = pd.date_range(h_fin - pd.Timedelta(days=jours) + H, h_fin, freq="h").astype("datetime64[ns]")
    log(f"heures rejouées : {heures[0]} -> {heures[-1]} UTC ({len(heures)})")
    # (1) le programme, heure par heure, avec seulement ce qui était publié à cette heure
    sig_prog = np.zeros((len(MARCHES), len(heures)), np.int8)
    prog_sig = {}
    for i, s in enumerate(MARCHES):
        st = stores[s]
        connu = (pd.DatetimeIndex(pd.to_datetime(st["api_ms"].to_numpy(np.int64), unit="ms")).astype("datetime64[ns]") + CONNU_APRES).to_numpy()
        for j, h in enumerate(heures):
            k = int(np.searchsorted(connu, np.datetime64(h), "right"))
            x = signal_c1(st.iloc[:k], h)
            sig_prog[i, j] = x["sens"]
            prog_sig[(s, h)] = x
    log(f"signaux du programme : {int((sig_prog != 0).sum())} heures avec signal")
    # (2) crypto_flux.py tel quel sur les mêmes données (dossier temporaire au format data/binance_futures)
    tmp = tempfile.mkdtemp(prefix="foule_rejeu_")
    fut0, fin0 = cf.FUT, cf.FIN_TOUT
    sig_cf = np.zeros_like(sig_prog)
    arr = {k: np.full((len(MARCHES), len(heures)), np.nan) for k in ("C", "SD", "Hh", "Lw", "FUN")}
    cache = {}
    try:
        for d in ("klines15m", "metrics"):
            os.makedirs(os.path.join(tmp, d))
        cf.FUT, cf.FIN_TOUT = type(cf.FUT)(tmp), pd.Timestamp("2100-01-01")
        for i, s in enumerate(MARCHES):
            k15 = klines(s, "15m", heures[0] - pd.Timedelta(days=100))
            k15[["utc_ms", "close", "volume", "taker_buy_volume"]].to_csv(os.path.join(tmp, "klines15m", f"{s}.csv"),
                                                                         index=False)
            st = stores[s]
            pd.DataFrame({"utc_ms": st["utc_ms"], "sum_open_interest": 1.0, "count_long_short_ratio": st["ratio"],
                          "sum_toptrader_long_short_ratio": 1.0}).to_csv(os.path.join(tmp, "metrics", f"{s}.csv"),
                                                                         index=False)
            F = cf.caracteristiques(s, prix_perp=True)
            sig_cf[i] = pd.Series(cf.signaux(F)["C1"], index=F.index).reindex(heures).fillna(0).astype(np.int8)
            arr["C"][i] = F["prix"].ffill().reindex(heures).to_numpy()
            arr["SD"][i] = (F["agit_h"] * math.sqrt(24)).reindex(heures).to_numpy()
            fin15 = k15.index.ceil("h")
            g = pd.DataFrame({"h": k15["high"].to_numpy(), "l": k15["low"].to_numpy()}, index=fin15)
            g = g.groupby(level=0).agg({"h": "max", "l": "min"}).reindex(heures)
            arr["Hh"][i], arr["Lw"][i] = g["h"].to_numpy(), g["l"].to_numpy()
            fu = financement(s, heures[0] - 2 * H, heures[-1] + pd.Timedelta(minutes=1))
            arr["FUN"][i] = fu.reindex(heures).fillna(0.0).to_numpy()
            prix_assurer(cache, s, heures[0] - HEURES_PRIX * H)
            print(f"  {s} : crypto_flux {int((sig_cf[i] != 0).sum())} signaux, programme {int((sig_prog[i] != 0).sum())}",
                  flush=True)
    finally:
        cf.FUT, cf.FIN_TOUT = fut0, fin0
        shutil.rmtree(tmp, ignore_errors=True)
    diff = np.argwhere(sig_prog != sig_cf)
    res = {"quand": str(datetime.now()), "heures": [str(heures[0]), str(heures[-1])], "n_heures": len(heures),
           "signaux_programme": int((sig_prog != 0).sum()), "signaux_crypto_flux": int((sig_cf != 0).sum()),
           "differences": [(MARCHES[i], str(heures[j]), int(sig_prog[i, j]), int(sig_cf[i, j])) for i, j in diff[:50]],
           "n_differences": int(len(diff)),
           "signaux_par_marche": {s[:-4]: {"achats": int((sig_cf[i] > 0).sum()), "ventes": int((sig_cf[i] < 0).sum())}
                                  for i, s in enumerate(MARCHES)}}
    log(f"SIGNAUX : programme {res['signaux_programme']}, crypto_flux {res['signaux_crypto_flux']}, "
        f"différences {res['n_differences']}" + (f" : {res['differences'][:5]}" if len(diff) else " -> IDENTIQUES"))
    # (3) le compte du programme contre crypto_flux_compte.simuler (mêmes heures, NaN ajoutés après la fin pour que
    #     simuler accepte des entrées jusqu'à la dernière heure)
    pad = cfc.TENUE + 1
    grille = pd.date_range(heures[0], periods=len(heures) + pad, freq="h").astype("datetime64[ns]")
    srv = cf.serveur(grille).normalize()
    j0 = srv.min()
    JOUR = ((srv - j0).days).to_numpy().astype(np.int64)
    P = lambda a, v=np.nan: np.c_[a, np.full((len(MARCHES), pad), v)]          # noqa: E731
    un = np.ones((len(MARCHES), len(grille)), np.int8)
    res["compte"] = {}
    for nom, regle in COMPTAS.items():
        fr = np.array([regle["frais"][s] for s in MARCHES])
        jo, tr = cfc.simuler(P(arr["C"]), P(arr["Hh"]), P(arr["Lw"]), P(sig_cf, 0).astype(np.int8), P(arr["SD"]),
                             P(arr["FUN"], 0.0), JOUR, fr, regle["financement"], regle["nuit"], un, RISQUE_USD, K_STOP,
                             MAXPOS, MAXSENS, STOP_JOUR, cfc.TENUE, NUIT_JOUR)
        ref = sorted((MARCHES[int(r[0])], grille[int(r[1])], grille[int(r[2])], int(r[3]), float(r[4]), float(r[5]),
                      ["temps", "stop", "arrêt du jour"][int(r[6])]) for r in tr)
        c = Compte(nom)
        mes = []
        for h in heures:
            X = {s: entrees_heure(cache[s], h) for s in MARCHES}
            sig = {s: prog_sig[(s, h)] for s in MARCHES}
            fun = {s: float(arr["FUN"][i, heures.get_loc(h)]) for i, s in enumerate(MARCHES)}
            so, _ = c.heure(h, jour_serveur(h), X, sig, fun)
            mes += so
        mien = sorted((t["marche"], t["entree"], t["sortie"], t["sens"], t["montant"], t["g"], t["type"]) for t in mes)
        pareil = len(ref) == len(mien) and all(
            a[0] == b[0] and a[1] == b[1] and a[2] == b[2] and a[3] == b[3] and a[6] == b[6]
            and abs(a[4] - b[4]) <= 1e-6 * abs(a[4]) and abs(a[5] - b[5]) <= 1e-9 for a, b in zip(ref, mien))
        # début de chaque jour serveur (jours entièrement dans le rejeu)
        dj = []
        for jr, v in c.jours.items():
            d = (pd.Timestamp(jr) - j0).days
            if 0 <= d < len(jo) and np.isfinite(jo[d, 0]) and pd.Timestamp(jr) > j0:
                dj.append(abs(jo[d, 0] - v[0]))
        ecart_jour = float(max(dj)) if dj else 0.0
        res["compte"][nom] = {"trades_simuler": len(ref), "trades_programme": len(mien), "identiques": bool(pareil),
                              "ecart_max_debut_de_jour_usd": ecart_jour,
                              "resultat_trades_fermes_usd": float(sum(t["resultat"] for t in mes)),
                              "positions_ouvertes_fin": {s: p["sens"] for s, p in c.pos.items()},
                              "fonds_fin_usd": CAP + c.jours[c.jour][2],
                              "stops": sum(t["type"] == "stop" for t in mes),
                              "arrets_jour": sum(t["type"] == "arrêt du jour" for t in mes)}
        log(f"COMPTE {nom} : simuler {len(ref)} trades, programme {len(mien)} -> "
            f"{'IDENTIQUES' if pareil else 'DIFFÉRENTS'} ; écart max début de jour {ecart_jour:.6f} $ ; fonds fin "
            f"{usd(CAP + c.jours[c.jour][2])} $ ; trades fermés {res['compte'][nom]['resultat_trades_fermes_usd']:+.0f} $ ; "
            f"positions ouvertes {res['compte'][nom]['positions_ouvertes_fin']}")
    res["verdict"] = bool(res["n_differences"] == 0 and all(x["identiques"] and x["ecart_max_debut_de_jour_usd"] < 0.01
                                                            for x in res["compte"].values()))
    res["duree_s"] = round(time.time() - t_debut)
    REJEU.write_text(json.dumps(res, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    log(f"VERDICT DU CONTRÔLE : {'OK, mêmes signaux et mêmes trades' if res['verdict'] else 'ÉCHEC'} "
        f"({res['duree_s']} s) -> {REJEU.name}")
    return res


if __name__ == "__main__":
    if "--rejouer" in sys.argv:
        rejouer()
    elif "--essai" in sys.argv:
        essai()
    else:
        boucle()
