"""LES YEUX DU MONDE — contexte géopolitique et peur (18/10/2026, chef de projet : sur son compte FTMO validé, le SENS
lui venait « de mes zones ET des tensions géopolitiques qui couraient »). Ce sont des INFORMATIONS, jamais des règles.

Séries quotidiennes, publiques et gratuites, rangées dans Test_IA/data/monde (et data/cboe, déjà là) :
| nom          | quoi                                                                    | source / fichier                         |
|--------------|-------------------------------------------------------------------------|------------------------------------------|
| gpr          | risque géopolitique (Caldara et Iacoviello, 10 journaux, depuis 1985)   | data_gpr_daily_recent.xls, colonne GPRD  |
| gpr_menaces  | sa partie « menaces » (guerre menacée, tensions)                        | GPRD_THREAT                              |
| gpr_actes    | sa partie « actes » (guerre commencée, attentats)                       | GPRD_ACT                                 |
| epu          | incertitude économique et politique américaine (Baker, Bloom, Davis)    | All_Daily_Policy_Data.csv                |
| vix          | peur sur les actions américaines (30 jours)                             | data/cboe/VIX_History.csv (clôture)      |
| vix3m        | même chose à 3 mois                                                     | data/cboe/VIX3M_History.csv              |
| vvix         | peur sur la peur (agitation attendue du VIX)                            | data/cboe/VVIX_History.csv               |
| ovx          | peur sur le pétrole                                                     | OVX_History.csv (Cboe)                   |
| gvz          | peur sur l'or                                                           | GVZ_History.csv (Cboe)                   |
| gdelt_noir   | noirceur des articles de guerre dans le monde (- ton moyen, GDELT)      | gdelt_conflit.csv (depuis 2017)          |
| gdelt_part   | part des articles du monde qui parlent de guerre (GDELT)                | gdelt_conflit.csv (depuis 2017)          |
Par pays (GPRC_RUS, GPRC_ISR...) : seulement MENSUEL (data_gpr_export.xls) : rangé, pas utilisé ici.

DÉLAI DE PUBLICATION (règle unique, prudente) : une valeur datée du jour J (jour des articles pour GPR / EPU / GDELT,
jour de séance à New York pour la Cboe) n'est utilisable qu'à partir de J+1 à 08h00 HEURE DU SERVEUR (= J+1 01h00 à New
York, après la fin du jour J partout : clôture Cboe 16h15 New York, articles du jour J tous parus). Rien n'est lu dont
l'instant d'utilisation tombe à partir de reglages.periodes.fin_donnees (12 mois cachés). Testé : calcul coupé à t =
calcul complet (tests/test_monde.py).
Pièges : le fichier GPR quotidien est mis en ligne par l'auteur environ une fois par semaine (le 13/10/2026 il allait
jusqu'au 13/10, dernier jour peut-être partiel) : en direct, la valeur la plus récente peut avoir plusieurs jours de
retard. La Cboe met ses fichiers à jour le soir même ; l'EPU le soir même aussi (17/10 23h55 GMT : jour du 17 inclus).

Depuis Test_IA : venv_gpu\\Scripts\\python.exe -m collapsar.donnees.monde telecharger|voir
"""
from __future__ import annotations

import argparse
import time
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

from collapsar.donnees.marches import RACINE

DOSSIER = RACINE / "data" / "monde"
CBOE = RACINE / "data" / "cboe"
JOUR_NS = 86400 * 10 ** 9
HEURE_NS = 3600 * 10 ** 9
DELAI_NS = JOUR_NS + 8 * HEURE_NS            # valeur du jour J utilisable à J+1 08h00 (heure du serveur)
FIN_DONNEES = pd.Timestamp("2025-10-01")      # = reglages.periodes.fin_donnees (vérifié par le test)

SERIES = ("gpr", "gpr_menaces", "gpr_actes", "epu", "vix", "vix3m", "vvix", "ovx", "gvz", "gdelt_noir", "gdelt_part")
NOM_S = {"gpr": "risque géopolitique (GPR)", "gpr_menaces": "GPR menaces", "gpr_actes": "GPR actes",
         "epu": "incertitude économique (EPU)", "vix": "peur actions (VIX)", "vix3m": "peur actions 3 mois",
         "vvix": "peur sur la peur (VVIX)", "ovx": "peur pétrole (OVX)", "gvz": "peur or (GVZ)",
         "gdelt_noir": "noirceur des articles de guerre (GDELT)", "gdelt_part": "part des articles de guerre (GDELT)"}

URLS = {"data_gpr_daily_recent.xls": "https://www.matteoiacoviello.com/gpr_files/data_gpr_daily_recent.xls",
        "data_gpr_export.xls": "https://www.matteoiacoviello.com/gpr_files/data_gpr_export.xls",
        "OVX_History.csv": "https://cdn.cboe.com/api/global/us_indices/daily_prices/OVX_History.csv",
        "GVZ_History.csv": "https://cdn.cboe.com/api/global/us_indices/daily_prices/GVZ_History.csv",
        "All_Daily_Policy_Data.csv": "https://www.policyuncertainty.com/media/All_Daily_Policy_Data.csv"}
URLS_CBOE = {f"{k}_History.csv": f"https://cdn.cboe.com/api/global/us_indices/daily_prices/{k}_History.csv"
             for k in ("VIX", "VIX3M", "VVIX")}
GDELT_REQ = "(war OR military OR missile OR airstrike OR invasion OR terrorist)"
GDELT_DEBUT = "2017-01-01"


# ============================================================================================== téléchargement
def telecharger(cboe: bool = False, gdelt: bool = True, dire=print):
    """Fichiers publics et gratuits (aucun compte, aucune clé)."""
    import requests
    DOSSIER.mkdir(parents=True, exist_ok=True)
    h = {"User-Agent": "Mozilla/5.0"}
    todo = [(DOSSIER, URLS)] + ([(CBOE, URLS_CBOE)] if cboe else [])
    for dos, urls in todo:
        for f, u in urls.items():
            r = requests.get(u, headers=h, timeout=120)
            r.raise_for_status()
            (dos / f).write_bytes(r.content)
            dire(f"{f} : {len(r.content)} octets")
    if gdelt:
        telecharger_gdelt(dire)


def telecharger_gdelt(dire=print, fin: str | None = None):
    """GDELT (API publique « DOC 2.0 », une requête toutes les 6 s) : par trimestre, ton moyen des articles de guerre et
    nombre d'articles (de guerre / de tous les articles du monde surveillés) par jour UTC."""
    import requests
    from urllib.parse import quote
    fin = pd.Timestamp(fin or pd.Timestamp.now().normalize())
    bornes = list(pd.date_range(GDELT_DEBUT, fin, freq="QS")) + [fin]
    morceaux = []
    for a, b in zip(bornes[:-1], bornes[1:]):
        for mode in ("timelinetone", "timelinevolraw"):
            u = (f"https://api.gdeltproject.org/api/v2/doc/doc?query={quote(GDELT_REQ)}&mode={mode}&format=csv"
                 f"&startdatetime={a:%Y%m%d}000000&enddatetime={b:%Y%m%d}000000")
            for essai in range(8):
                time.sleep(20)                                           # l'accès public se bloque vite (18/10)
                try:
                    r = requests.get(u, timeout=120, headers={"User-Agent": "Mozilla/5.0"})
                except requests.RequestException as e:
                    dire(f"GDELT {mode} {a:%Y-%m-%d} : erreur {e!r}, nouvel essai")
                    continue
                if r.status_code == 200 and r.text.strip():
                    break
                dire(f"GDELT {mode} {a:%Y-%m-%d} : refus {r.status_code}, attente {60 * (essai + 1)} s")
                time.sleep(60 * (essai + 1))
            else:
                raise RuntimeError(f"GDELT {mode} {a:%Y-%m-%d} : {r.status_code}")
            from io import StringIO
            d = pd.read_csv(StringIO(r.text.lstrip("﻿")))
            d["mode"] = mode
            morceaux.append(d)
        dire(f"GDELT {a:%Y-%m-%d} -> {b:%Y-%m-%d} fait")
    d = pd.concat(morceaux, ignore_index=True)
    d.to_csv(DOSSIER / "gdelt_brut.csv", index=False)
    d["jour"] = pd.to_datetime(d["Date"]).dt.normalize()                 # jour UTC des articles
    d = d.drop_duplicates(["Date", "Series", "mode"], keep="last")        # bornes des trimestres en double
    ton = d[d["mode"] == "timelinetone"].groupby("jour")["Value"].mean()
    vol = d[d["mode"] == "timelinevolraw"]
    nb = vol[vol["Series"] == "Article Count"].groupby("jour")["Value"].sum()
    tot = vol[vol["Series"] == "Total Monitored Articles"].groupby("jour")["Value"].sum()
    out = pd.DataFrame({"ton": ton, "articles": nb, "total": tot})
    out.index.name = "date"
    out.to_csv(DOSSIER / "gdelt_conflit.csv")
    dire(f"gdelt_conflit.csv : {len(out)} jours")


# ============================================================================================== lecture brute
def _cboe(f: Path, col: str) -> pd.Series:
    d = pd.read_csv(f)
    d.columns = [c.strip().upper() for c in d.columns]
    s = pd.Series(pd.to_numeric(d[col.upper()], errors="coerce").to_numpy(),
                  index=pd.to_datetime(d["DATE"], format="%m/%d/%Y"))
    return s


@lru_cache(maxsize=None)
def _gpr() -> pd.DataFrame:
    d = pd.read_excel(DOSSIER / "data_gpr_daily_recent.xls")
    d = d[pd.to_numeric(d["DAY"], errors="coerce").notna()]
    d.index = pd.to_datetime(d["DAY"].astype(int).astype(str), format="%Y%m%d")
    return d


def lire_brut(nom: str) -> pd.Series:
    """Série quotidienne brute (index = jour J de la valeur, sans heure), TOUTES dates (aucune coupe ici)."""
    if nom in ("gpr", "gpr_menaces", "gpr_actes"):
        col = {"gpr": "GPRD", "gpr_menaces": "GPRD_THREAT", "gpr_actes": "GPRD_ACT"}[nom]
        g = _gpr()
        s = pd.Series(pd.to_numeric(g[col], errors="coerce").to_numpy(), index=g.index)
    elif nom == "epu":
        d = pd.read_csv(DOSSIER / "All_Daily_Policy_Data.csv")
        s = pd.Series(d["daily_policy_index"].to_numpy(float),
                      index=pd.to_datetime(dict(year=d["year"], month=d["month"], day=d["day"])))
    elif nom in ("vix", "vix3m"):
        s = _cboe(CBOE / f"{nom.upper()}_History.csv", "CLOSE")
    elif nom == "vvix":
        s = _cboe(CBOE / "VVIX_History.csv", "VVIX")
    elif nom in ("ovx", "gvz"):
        s = _cboe(DOSSIER / f"{nom.upper()}_History.csv", nom.upper())
    elif nom in ("gdelt_noir", "gdelt_part"):
        f = DOSSIER / "gdelt_conflit.csv"
        if not f.exists():
            return pd.Series(dtype=float, index=pd.DatetimeIndex([], dtype="datetime64[ns]"))
        d = pd.read_csv(f, parse_dates=["date"]).set_index("date")
        if nom == "gdelt_noir":
            s = -d["ton"]
        else:
            s = d["articles"] / d["total"] * 100 if "total" in d.columns else d["articles"]
    else:
        raise KeyError(nom)
    s = s[np.isfinite(s.to_numpy(float))]
    if nom != "gdelt_noir":
        s = s[s > 0]
    s.index = pd.DatetimeIndex(s.index).normalize().as_unit("ns")
    s = s[~s.index.duplicated(keep="last")].sort_index()
    return s.astype(float)


def connu_ns(jours: pd.DatetimeIndex | np.ndarray) -> np.ndarray:
    """Instant (heure du serveur, ns) à partir duquel la valeur du jour J est utilisable : J+1 08h00."""
    j = np.asarray(pd.DatetimeIndex(jours).normalize().as_unit("ns").asi8, np.int64)
    return j + DELAI_NS


@lru_cache(maxsize=None)
def serie(nom: str) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """(jour J en ns, instant où la valeur est connue en ns, valeur) : seulement ce qui est connu AVANT fin_donnees."""
    s = lire_brut(nom)
    j = np.asarray(s.index.as_unit("ns").asi8, np.int64)
    c = connu_ns(s.index)
    k = c < FIN_DONNEES.value
    return j[k], c[k], s.to_numpy(float)[k]


def valeurs_a(nom: str, t_ns: np.ndarray, vieux_jours: float = 10.0) -> np.ndarray:
    """Dernière valeur CONNUE à chaque instant (serveur, ns) ; NaN si aucune ou plus vieille que `vieux_jours`."""
    _, c, v = serie(nom)
    t_ns = np.asarray(t_ns, np.int64)
    if not len(c):
        return np.full(len(t_ns), np.nan)
    i = np.searchsorted(c, t_ns, side="right") - 1
    ok = (i >= 0)
    ii = np.clip(i, 0, None)
    ok &= (t_ns - c[ii]) <= vieux_jours * JOUR_NS
    return np.where(ok, v[ii], np.nan)


# ============================================================================================== mesures dérivées
def _log(v: np.ndarray, nom: str) -> np.ndarray:
    return v if nom == "gdelt_noir" else np.log(v)


def niveau_z(v: np.ndarray, nom: str, n: int = 250) -> np.ndarray:
    """(x - moyenne des n valeurs PRÉCÉDENTES) / leur écart, x en logarithme (ton GDELT : tel quel)."""
    x = pd.Series(_log(v, nom))
    p = x.shift(1).rolling(n, min_periods=n // 2)
    return ((x - p.mean()) / p.std()).to_numpy()


def haut_n(v: np.ndarray, n: int = 30) -> np.ndarray:
    """Vrai si la valeur dépasse le plus haut des n valeurs PRÉCÉDENTES (toutes connues avant elle)."""
    x = pd.Series(v)
    m = x.shift(1).rolling(n, min_periods=n).max()
    return (x > m).to_numpy() & m.notna().to_numpy()


def saut_z(v: np.ndarray, nom: str, n: int = 60) -> np.ndarray:
    return niveau_z(v, nom, n)


@lru_cache(maxsize=None)
def _tableau(nom: str) -> pd.DataFrame:
    j, c, v = serie(nom)
    return pd.DataFrame({"jour": j, "connu": c, "v": v, "z250": niveau_z(v, nom, 250), "z60": saut_z(v, nom, 60),
                         "haut30": haut_n(v, 30)})


def tableau(nom: str, coupe_ns: int | None = None) -> pd.DataFrame:
    """Par valeur publiée : jour, instant connu, valeur, z sur 1 an, z sur 60 valeurs, nouveau plus haut de 30 valeurs.
    `coupe_ns` (tests « sans futur ») : recalculé comme si rien n'était publié à partir de cet instant."""
    if coupe_ns is None:
        return _tableau(nom)
    j, c, v = serie(nom)
    k = c < coupe_ns
    j, c, v = j[k], c[k], v[k]
    return pd.DataFrame({"jour": j, "connu": c, "v": v, "z250": niveau_z(v, nom, 250), "z60": saut_z(v, nom, 60),
                         "haut30": haut_n(v, 30)})


TENSION_MA, TENSION_FEN, TENSION_Q = 7, 365, 0.8


def tension_a(t_ns: np.ndarray, coupe_ns: int | None = None) -> np.ndarray:
    """Vrai si une TENSION géopolitique court à l'instant t : moyenne des 7 dernières valeurs du GPR (connues) au-dessus
    du centile 80 de cette moyenne sur les 365 valeurs précédentes."""
    _, c, v = serie("gpr")
    if coupe_ns is not None:
        k = c < coupe_ns
        c, v = c[k], v[k]
    t_ns = np.asarray(t_ns, np.int64)
    if not len(c):
        return np.zeros(len(t_ns), bool)
    ma = pd.Series(v).rolling(TENSION_MA).mean()
    q = ma.shift(1).rolling(TENSION_FEN, min_periods=TENSION_FEN // 2).quantile(TENSION_Q)
    flag = (ma > q).to_numpy() & q.notna().to_numpy()
    i = np.searchsorted(c, t_ns, side="right") - 1
    ok = (i >= 0) & ((t_ns - c[np.clip(i, 0, None)]) <= 10 * JOUR_NS)
    return np.where(ok, flag[np.clip(i, 0, None)], False)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("quoi", choices=["telecharger", "gdelt", "voir"])
    ap.add_argument("--cboe", action="store_true", help="retélécharger aussi VIX, VIX3M, VVIX dans data/cboe")
    a = ap.parse_args(argv)
    if a.quoi == "telecharger":
        telecharger(a.cboe, gdelt=False)
    elif a.quoi == "gdelt":
        telecharger_gdelt()
    else:
        for n in SERIES:
            j, c, v = serie(n)
            if len(j):
                print(f"{n:12s} {len(j):6d} valeurs  {pd.Timestamp(j[0]):%Y-%m-%d} -> {pd.Timestamp(j[-1]):%Y-%m-%d}")
            else:
                print(f"{n:12s} absente")


if __name__ == "__main__":
    main()
