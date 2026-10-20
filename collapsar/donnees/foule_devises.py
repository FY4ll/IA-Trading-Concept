"""COLLECTEUR EN DIRECT (lecture seule) du positionnement des petits traders sur devises, or, argent, indices, pétrole
— 16/10/2026, piste « foule_devises ».

Pourquoi : aucune source gratuite et légale ne donne >= 3 ans d'historique du positionnement des clients particuliers
des courtiers (research_notes/Foule devises/notes.md). On enregistre donc dès maintenant ce qui est disponible, pour
tester plus tard la règle C1 (« la foule d'un seul côté -> jouer contre 24 h ») sur des données jamais vues.

Sources (uniquement des interfaces OFFICIELLES ; aucun grattage de page web ; aucun mot de passe affiché ni écrit
dans les journaux)
- gtrade (TOUJOURS, sans compte) : bourse gTrade sur chaînes publiques Arbitrum, Base, Polygon. Interface officielle
  documentée https://docs.gains.trade/developer/integrators/backend : « No auth is required for accessing REST GET
  endpoints … please fetch data only as necessary » -> 1 lecture de /open-trades par chaîne et par heure (~2 Mo en
  tout), /trading-variables/all (paires, prix des garanties) 1 fois par jour. On compte, par marché : comptes (adresses)
  acheteurs / vendeurs, trades, montants engagés en dollars (garantie x levier).
- cftc (TOUJOURS, sans compte) : fichier annuel des « Engagements des traders » (données publiques de l'État
  américain), retéléchargé 1 fois par jour -> data/foule_devises/cftc_brut/ (la piste refait cot_petits.csv).
- myfxbook (SI un compte est fourni) : interface officielle login.json + get-community-outlook.json.
- ig (SI une clé et un compte IG, démo par défaut, sont fournis) : interface officielle /session + /clientsentiment.
- oanda (SI un jeton OANDA est fourni) : interface officielle /v3/instruments/<X>/positionBook (photo toutes les
  20 min ; `rattraper_oanda` relit les photos PASSÉES avec le paramètre `time` : la seule voie vers un historique long).
  Accès : variables d'environnement MYFXBOOK_EMAIL, MYFXBOOK_MOTDEPASSE ; IG_CLE, IG_IDENTIFIANT, IG_MOTDEPASSE,
  IG_DEMO (1 par défaut) ; OANDA_JETON, OANDA_ENV (practice par défaut) — ou le fichier local
  data/foule_devises/acces.json (mêmes noms). Jamais affichés.
Exclues (conditions) : Dukascopy (robots interdits sans accord écrit), pages web Myfxbook / IG / FXSSI / Forex Factory.

Fichiers : data/foule_devises/direct/<source>_<AAAA-MM>.csv (ajout), une ligne par lecture et par marché :
utc (heure de la lecture), serveur (New York + 7 h), source, lieu (chaîne / courtier), symbole (nom FTMO),
nom_source, part_acheteurs (part des COMPTES acheteurs si connue, sinon des positions), comptes_acheteurs,
comptes_vendeurs, trades_acheteurs, trades_vendeurs, montant_acheteurs_usd, montant_vendeurs_usd, info (texte libre).
Journal : data/foule_devises/direct/journal.txt.

Usage (depuis Test_IA) :
  venv_gpu\\Scripts\\python.exe -u -m collapsar.donnees.foule_devises une_fois    (une lecture, pour une tâche planifiée)
  venv_gpu\\Scripts\\python.exe -u -m collapsar.donnees.foule_devises boucle      (toutes les heures, à HH:02 UTC)
  venv_gpu\\Scripts\\python.exe -u -m collapsar.donnees.foule_devises oanda_rattrapage 2017-01-01   (si jeton)
Arrêt de la boucle : créer data/foule_devises/direct/ARRET.
"""
from __future__ import annotations

import csv
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone

import pandas as pd
import requests

from collapsar.donnees.marches import RACINE

DOSSIER = RACINE / "data" / "foule_devises"
DIRECT = DOSSIER / "direct"
ACCES = DOSSIER / "acces.json"
COLONNES = ["utc", "serveur", "source", "lieu", "symbole", "nom_source", "part_acheteurs", "comptes_acheteurs",
            "comptes_vendeurs", "trades_acheteurs", "trades_vendeurs", "montant_acheteurs_usd",
            "montant_vendeurs_usd", "info"]
DELAI = 60
ENTETE = {"User-Agent": "Test_IA-recherche-personnelle (lecture seule, 1 fois par heure)"}

# gTrade : (de, vers) -> nom FTMO ; les fonds indiciels SPY / QQQ / DIA sont gardés sous leur nom (proches du S&P 500,
# du Nasdaq-100 et du Dow, mais pas identiques)
GTRADE_CHAINES = ("arbitrum", "base", "polygon")
DEVISES = ("EUR", "USD", "JPY", "GBP", "CHF", "AUD", "CAD", "NZD")
GTRADE_AUTRES = {("XAU", "USD"): "XAUUSD", ("XAG", "USD"): "XAGUSD", ("WTI", "USD"): "LIGHTCMDUSD",
                 ("SPX", "USD"): "USA500IDXUSD", ("SPY", "USD"): "SPY", ("QQQ", "USD"): "QQQ",
                 ("DIA", "USD"): "DIA", ("NDX", "USD"): "USATECHIDXUSD", ("DJI", "USD"): "USA30IDXUSD"}

# Myfxbook / IG / OANDA : noms des marchés suivis (même liste que la piste + grandes croisées)
MARCHES_FTMO = ("EURUSD", "GBPUSD", "USDJPY", "USDCHF", "USDCAD", "AUDUSD", "NZDUSD", "EURJPY", "EURGBP", "GBPJPY",
                "EURCHF", "XAUUSD", "XAGUSD")
OANDA_INSTRUMENTS = {"EUR_USD": "EURUSD", "GBP_USD": "GBPUSD", "USD_JPY": "USDJPY", "USD_CHF": "USDCHF",
                     "USD_CAD": "USDCAD", "AUD_USD": "AUDUSD", "NZD_USD": "NZDUSD", "EUR_JPY": "EURJPY",
                     "EUR_GBP": "EURGBP", "GBP_JPY": "GBPJPY", "EUR_CHF": "EURCHF", "XAU_USD": "XAUUSD",
                     "XAG_USD": "XAGUSD", "SPX500_USD": "USA500IDXUSD", "NAS100_USD": "USATECHIDXUSD",
                     "US30_USD": "USA30IDXUSD", "WTICO_USD": "LIGHTCMDUSD"}
IG_MARCHES = ("EURUSD", "GBPUSD", "USDJPY", "USDCHF", "USDCAD", "AUDUSD", "NZDUSD", "EURJPY", "EURGBP", "GBPJPY",
              "EURCHF", "GC", "SI", "CL", "ES", "NQ", "YM")


# ---------------------------------------------------------------- outils
def maintenant() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def serveur(utc: datetime) -> str:
    t = pd.Timestamp(utc).tz_convert("America/New_York").tz_localize(None) + pd.Timedelta(hours=7)
    return t.isoformat()


def journal(msg: str):
    DIRECT.mkdir(parents=True, exist_ok=True)
    ligne = f"{maintenant().isoformat()} {msg}"
    print(ligne, flush=True)
    with open(DIRECT / "journal.txt", "a", encoding="utf-8") as f:
        f.write(ligne + "\n")


def ecrire(source: str, lignes: list[dict]):
    if not lignes:
        return
    DIRECT.mkdir(parents=True, exist_ok=True)
    f = DIRECT / f"{source}_{maintenant():%Y-%m}.csv"
    neuf = not f.exists()
    with open(f, "a", newline="", encoding="utf-8") as h:
        w = csv.DictWriter(h, fieldnames=COLONNES, extrasaction="ignore")
        if neuf:
            w.writeheader()
        for x in lignes:
            w.writerow({k: x.get(k, "") for k in COLONNES})


def acces(nom: str) -> str | None:
    v = os.environ.get(nom)
    if v:
        return v
    if ACCES.exists():
        try:
            return json.loads(ACCES.read_text(encoding="utf-8")).get(nom) or None
        except Exception:
            return None
    return None


def _get(url, **kw):
    r = requests.get(url, timeout=DELAI, headers={**ENTETE, **kw.pop("headers", {})}, **kw)
    r.raise_for_status()
    return r


def _part(a, v):
    a, v = float(a or 0), float(v or 0)
    return round(a / (a + v), 6) if a + v > 0 else ""


# ---------------------------------------------------------------- gTrade
_GT_CACHE: dict[str, tuple[float, dict]] = {}


def _gt_variables(chaine: str) -> dict:
    """Paires et prix des garanties (relu au plus 1 fois par jour)."""
    t, v = _GT_CACHE.get(chaine, (0.0, None))
    if v is None or time.time() - t > 86400:
        j = _get(f"https://backend-{chaine}.gains.trade/trading-variables/all").json()
        paires = {i: (p.get("from"), p.get("to")) for i, p in enumerate(j.get("pairs", []))}
        garanties = {str(c["collateralIndex"]): (float(c["prices"]["collateralPriceUsd"]),
                                                 int(c["collateralConfig"]["decimals"]))
                     for c in j.get("collaterals", [])}
        v = {"paires": paires, "garanties": garanties}
        _GT_CACHE[chaine] = (time.time(), v)
    return v


def _gt_nom(de_vers) -> str | None:
    de, vers = de_vers
    if de in DEVISES and vers in DEVISES:
        return de + vers
    return GTRADE_AUTRES.get((de, vers))


def lire_gtrade(utc: datetime) -> list[dict]:
    out = []
    for ch in GTRADE_CHAINES:
        try:
            var = _gt_variables(ch)
            ot = _get(f"https://backend-{ch}.gains.trade/open-trades").json()
        except Exception as e:
            journal(f"gtrade {ch} : erreur {type(e).__name__} {str(e)[:200]}")
            continue
        agg: dict[str, dict] = {}
        for x in ot:
            t = x.get("trade", {})
            if not t.get("isOpen", True):
                continue
            i = int(t.get("pairIndex", -1))
            nom = _gt_nom(var["paires"].get(i, ("?", "?")))
            if nom is None:
                continue
            prix, dec = var["garanties"].get(str(t.get("collateralIndex")), (float("nan"), 18))
            montant = int(t.get("collateralAmount", 0)) / 10 ** dec * prix * int(t.get("leverage", 0)) / 1000.0
            a = agg.setdefault(nom, {"cA": set(), "cV": set(), "tA": 0, "tV": 0, "mA": 0.0, "mV": 0.0,
                                     "src": "/".join(var["paires"][i])})
            if t.get("long"):
                a["cA"].add(t.get("user")); a["tA"] += 1; a["mA"] += montant
            else:
                a["cV"].add(t.get("user")); a["tV"] += 1; a["mV"] += montant
        for nom, a in sorted(agg.items()):
            out.append({"utc": utc.isoformat(), "serveur": serveur(utc), "source": "gtrade", "lieu": ch,
                        "symbole": nom, "nom_source": a["src"], "part_acheteurs": _part(len(a["cA"]), len(a["cV"])),
                        "comptes_acheteurs": len(a["cA"]), "comptes_vendeurs": len(a["cV"]),
                        "trades_acheteurs": a["tA"], "trades_vendeurs": a["tV"],
                        "montant_acheteurs_usd": round(a["mA"], 2), "montant_vendeurs_usd": round(a["mV"], 2),
                        "info": f"open-trades {len(ot)} trades sur la chaîne"})
        time.sleep(2)
    return out


# ---------------------------------------------------------------- CFTC (1 fois par jour)
def lire_cftc(utc: datetime) -> list[dict]:
    brut = DOSSIER / "cftc_brut"
    brut.mkdir(parents=True, exist_ok=True)
    f = brut / f"deacot{utc.year}.zip"
    if f.exists() and time.time() - f.stat().st_mtime < 86400:
        return []
    r = _get(f"https://www.cftc.gov/files/dea/history/deacot{utc.year}.zip")
    f.write_bytes(r.content)
    journal(f"cftc : deacot{utc.year}.zip retéléchargé ({len(r.content)} octets)")
    return []


# ---------------------------------------------------------------- Myfxbook (si compte)
_MFX = {"session": None}


def lire_myfxbook(utc: datetime) -> list[dict]:
    email, mdp = acces("MYFXBOOK_EMAIL"), acces("MYFXBOOK_MOTDEPASSE")
    if not (email and mdp):
        return []
    base = "https://www.myfxbook.com/api/"
    for essai in range(2):
        if not _MFX["session"]:
            j = _get(base + "login.json", params={"email": email, "password": mdp}).json()
            if j.get("error"):
                journal("myfxbook : connexion refusée (message : " + str(j.get("message"))[:100] + ")")
                return []
            _MFX["session"] = j.get("session")
        j = _get(base + "get-community-outlook.json", params={"session": _MFX["session"]}).json()
        if not j.get("error"):
            break
        _MFX["session"] = None
    else:
        journal("myfxbook : lecture refusée")
        return []
    out = []
    for s in j.get("symbols", []):
        nom = str(s.get("name", "")).upper()
        out.append({"utc": utc.isoformat(), "serveur": serveur(utc), "source": "myfxbook", "lieu": "communaute",
                    "symbole": nom, "nom_source": s.get("name"),
                    "part_acheteurs": round(float(s.get("longPercentage", 0)) / 100, 4),
                    "comptes_acheteurs": "", "comptes_vendeurs": "",
                    "trades_acheteurs": s.get("longPositions", ""), "trades_vendeurs": s.get("shortPositions", ""),
                    "montant_acheteurs_usd": "", "montant_vendeurs_usd": "",
                    "info": json.dumps({"lots_achat": s.get("longVolume"), "lots_vente": s.get("shortVolume"),
                                        "prix_moy_achat": s.get("avgLongPrice"),
                                        "prix_moy_vente": s.get("avgShortPrice"),
                                        "part_positions_acheteuses_pct": s.get("longPercentage")})})
    return out


# ---------------------------------------------------------------- IG (si compte + clé)
def lire_ig(utc: datetime) -> list[dict]:
    cle, ident, mdp = acces("IG_CLE"), acces("IG_IDENTIFIANT"), acces("IG_MOTDEPASSE")
    if not (cle and ident and mdp):
        return []
    demo = (acces("IG_DEMO") or "1") != "0"
    base = "https://demo-api.ig.com/gateway/deal" if demo else "https://api.ig.com/gateway/deal"
    h = {"X-IG-API-KEY": cle, "Content-Type": "application/json", "Accept": "application/json", "Version": "2"}
    r = requests.post(base + "/session", json={"identifier": ident, "password": mdp}, headers={**ENTETE, **h},
                      timeout=DELAI)
    if r.status_code != 200:
        journal(f"ig : connexion refusée (code {r.status_code})")
        return []
    h.update({"CST": r.headers.get("CST", ""), "X-SECURITY-TOKEN": r.headers.get("X-SECURITY-TOKEN", ""),
              "Version": "1"})
    r = requests.get(base + "/clientsentiment", params={"marketIds": ",".join(IG_MARCHES)}, headers={**ENTETE, **h},
                     timeout=DELAI)
    if r.status_code != 200:
        journal(f"ig : lecture refusée (code {r.status_code})")
        return []
    out = []
    for s in r.json().get("clientSentiments", []):
        out.append({"utc": utc.isoformat(), "serveur": serveur(utc), "source": "ig", "lieu": "demo" if demo else "reel",
                    "symbole": s.get("marketId"), "nom_source": s.get("marketId"),
                    "part_acheteurs": round(float(s.get("longPositionPercentage", 0)) / 100, 4),
                    "info": "part des clients IG (positions) acheteurs"})
    return out


# ---------------------------------------------------------------- OANDA (si jeton)
def _oanda_base() -> str:
    return ("https://api-fxtrade.oanda.com" if (acces("OANDA_ENV") or "practice") == "live"
            else "https://api-fxpractice.oanda.com")


def _oanda_livre(instr: str, jeton: str, quand: str | None = None) -> dict | None:
    p = {"time": quand} if quand else None
    r = requests.get(f"{_oanda_base()}/v3/instruments/{instr}/positionBook", params=p, timeout=DELAI,
                     headers={**ENTETE, "Authorization": f"Bearer {jeton}"})
    if r.status_code != 200:
        return None
    return r.json().get("positionBook")


def _oanda_ligne(pb: dict, instr: str, utc: datetime, source="oanda") -> dict:
    lo = sum(float(b.get("longCountPercent", 0)) for b in pb.get("buckets", []))
    sh = sum(float(b.get("shortCountPercent", 0)) for b in pb.get("buckets", []))
    return {"utc": utc.isoformat(), "serveur": serveur(utc), "source": source, "lieu": _oanda_base().split("//")[1],
            "symbole": OANDA_INSTRUMENTS[instr], "nom_source": instr, "part_acheteurs": _part(lo, sh),
            "info": json.dumps({"photo": pb.get("time"), "prix": pb.get("price")})}


def lire_oanda(utc: datetime) -> list[dict]:
    jeton = acces("OANDA_JETON")
    if not jeton:
        return []
    out = []
    for instr in OANDA_INSTRUMENTS:
        pb = _oanda_livre(instr, jeton)
        if pb:
            out.append(_oanda_ligne(pb, instr, utc))
        time.sleep(0.3)
    if not out:
        journal("oanda : aucun livre de positions lisible avec ce jeton")
    return out


def rattraper_oanda(debut: str, pas_heures: int = 1):
    """Relit les photos PASSÉES du livre de positions OANDA (paramètre `time`) -> data/foule_devises/oanda_historique/.
    Lent et poli (0,3 s par appel). Reprend là où il s'était arrêté."""
    jeton = acces("OANDA_JETON")
    if not jeton:
        print("Pas de jeton OANDA (OANDA_JETON) : rien à faire.")
        return
    d = DOSSIER / "oanda_historique"
    d.mkdir(parents=True, exist_ok=True)
    for instr in OANDA_INSTRUMENTS:
        f = d / f"{instr}.csv"
        t = pd.Timestamp(debut, tz="UTC")
        if f.exists():
            deja = pd.read_csv(f)
            if len(deja):
                t = pd.Timestamp(deja["photo"].iloc[-1]) + pd.Timedelta(hours=pas_heures)
        fin = pd.Timestamp.now(tz="UTC")
        neuf = not f.exists()
        with open(f, "a", newline="", encoding="utf-8") as h:
            w = csv.writer(h)
            if neuf:
                w.writerow(["photo", "demande", "part_acheteurs", "prix"])
            vide = 0
            while t < fin and vide < 200:
                pb = _oanda_livre(instr, jeton, t.strftime("%Y-%m-%dT%H:%M:%SZ"))
                if pb:
                    x = _oanda_ligne(pb, instr, maintenant())
                    w.writerow([pb.get("time"), t.isoformat(), x["part_acheteurs"], pb.get("price")])
                    vide = 0
                else:
                    vide += 1
                t += pd.Timedelta(hours=pas_heures)
                time.sleep(0.3)
        journal(f"oanda rattrapage {instr} : fini jusqu'à {t}")


# ---------------------------------------------------------------- boucle
SOURCES = {"gtrade": lire_gtrade, "cftc": lire_cftc, "myfxbook": lire_myfxbook, "ig": lire_ig, "oanda": lire_oanda}


def une_fois():
    utc = maintenant()
    bilan = []
    for nom, f in SOURCES.items():
        try:
            lignes = f(utc)
            ecrire(nom, lignes)
            bilan.append(f"{nom} {len(lignes)}")
        except Exception as e:                       # une source en panne ne bloque pas les autres
            journal(f"{nom} : erreur {type(e).__name__} {str(e)[:200]}")
    journal("lecture : " + ", ".join(bilan))


def boucle():
    journal("boucle démarrée (pid %d)" % os.getpid())
    while not (DIRECT / "ARRET").exists():
        une_fois()
        t = maintenant()
        prochain = (t + timedelta(hours=1)).replace(minute=2, second=0)
        while maintenant() < prochain:
            if (DIRECT / "ARRET").exists():
                break
            time.sleep(30)
    journal("boucle arrêtée (fichier ARRET)")


if __name__ == "__main__":
    etape = sys.argv[1] if len(sys.argv) > 1 else "une_fois"
    if etape == "boucle":
        boucle()
    elif etape == "oanda_rattrapage":
        rattraper_oanda(sys.argv[2] if len(sys.argv) > 2 else "2017-01-01")
    else:
        une_fois()
