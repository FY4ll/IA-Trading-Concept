"""Les marchés de l'école de la précision : bougies de 15 min (heure du serveur = New York + 7 h), minutes pour les
4 marchés à la minute, fiches FTMO (levier, nuits), frais FTMO réparés du 16/10 et marchés retournés (miroirs).

- 19 cryptos FTMO : bougies Binance (filtre commun, ecole/crypto_monde.charger), frais FTMO commission comprise
  (crypto_monde.frais_crypto, même source que les pistes), nuit 30 %/an, levier 1:1 (crypto_monde.fiche_crypto).
- 4 marchés à la minute (or Kaggle à l'heure du serveur ; S&P 500, Nasdaq, euro HistData à l'heure de New York + 7 h) :
  les bougies de 15 min sont FABRIQUÉES à partir des minutes (mêmes prix pour les zones 5 / 3 min et le simulateur).
- ~45 marchés FTMO en 15 min (data/fx_intraday, Dukascopy ; or Kaggle) sauf les cryptos Dukascopy.
Frais : mains/frais_ftmo.frais (écart FTMO mesuré ramené au prix de l'époque + commission), sauf cryptos Binance.
Rien n'est jamais lu à partir de reglages.periodes.fin_donnees (12 mois cachés).
"""
from __future__ import annotations

from dataclasses import replace
from functools import lru_cache

import numpy as np
import pandas as pd

from collapsar.donnees import marches as dm
from collapsar.ecole.precision.reglages import CACHE, R
from collapsar.mains.fiches import MIROIR, Fiche, fiche

QUINZE = pd.Timedelta(minutes=15)


@lru_cache(maxsize=1)
def univers() -> tuple[str, ...]:
    """Tous les marchés de l'école (noms sans miroir)."""
    r = R().marches
    m15 = [m for m in dm.liste_marches() if m not in r.exclure_15min]
    tous = list(r.cryptos_binance) + list(r.minutes) + m15
    seulement = getattr(r, "seulement", None)           # arbre spécialisé (ex. l'or seul) ; absent = tous les marchés
    if seulement:
        tous = [m for m in tous if m in set(seulement)]
    return tuple(tous)


def source(nom: str) -> str:
    r = R().marches
    if nom in r.cryptos_binance:
        return "binance"
    if nom in r.minutes:
        return "minute"
    return "m15"


def base(nom: str) -> str:
    """Le marché FTMO de la fiche (frais, levier, nuits)."""
    return R().marches.minutes[nom][1] if source(nom) == "minute" else nom


def famille(nom: str) -> str:
    return "crypto" if source(nom) == "binance" else fiche(base(nom)).famille


def unites(nom: str) -> tuple[str, ...]:
    from collapsar.ecole.precision.reglages import UNITES, UNITES_15
    return UNITES if source(nom) == "minute" else UNITES_15


# ------------------------------------------------------------------------------------------------ lecture
def _cache_npz(cle: str, fabrique) -> pd.DataFrame:
    f = CACHE / "brut" / f"{cle}.npz"
    if f.exists():
        z = np.load(f)
        return pd.DataFrame({"time": z["time"].astype("datetime64[ns]"), **{k: z[k] for k in ("open", "high", "low", "close")}})
    df = fabrique()
    f.parent.mkdir(parents=True, exist_ok=True)
    np.savez(f, time=df["time"].values.astype("datetime64[ns]"),
             **{k: df[k].to_numpy(np.float64) for k in ("open", "high", "low", "close")})
    return df


def _propre(df: pd.DataFrame) -> pd.DataFrame:
    df = df[["time", "open", "high", "low", "close"]].dropna()
    df = df[(df[["open", "high", "low", "close"]] > 0).all(axis=1)]
    df = df.sort_values("time", kind="stable").drop_duplicates("time", keep="last").reset_index(drop=True)
    df["high"] = df[["open", "high", "low", "close"]].max(axis=1)
    df["low"] = df[["open", "high", "low", "close"]].min(axis=1)
    df["time"] = df["time"].astype("datetime64[ns]")
    return df


def _minutes_brutes(nom: str) -> pd.DataFrame:
    src = R().marches.minutes[nom][0]
    p = R().periodes
    if src == "kaggle_or":
        df = pd.read_csv(dm.RACINE / "data" / "kaggle_gold" / "XAU_1m_data.csv", sep=";")
        df.columns = [c.lower() for c in df.columns]
        df["time"] = pd.to_datetime(df["date"], format="%Y.%m.%d %H:%M")          # déjà l'heure du serveur
    else:
        from collapsar.donnees.histdata import charger
        df = charger(src)
        df["time"] = df["ny"] + pd.Timedelta(hours=7)                              # New York -> serveur
    df = _propre(df)
    return df[(df["time"] >= p.debut_minutes) & (df["time"] < p.fin_donnees)].reset_index(drop=True)


def minutes(nom: str) -> pd.DataFrame:
    """Bougies d'une minute (heure du serveur) d'un marché à la minute, de debut_minutes à fin_donnees (exclue)."""
    p = R().periodes
    return _cache_npz(f"{nom.replace('@', '_')}_minutes_{p.fin_donnees:%Y%m%d}", lambda: _minutes_brutes(nom))


def reechantillonner(df: pd.DataFrame, freq: str) -> pd.DataFrame:
    r = df.set_index("time").resample(freq, label="left", closed="left").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
    r = r.reset_index()
    r["time"] = r["time"].astype("datetime64[ns]")
    return r


def quinze(nom: str) -> pd.DataFrame:
    """Bougies de 15 min réelles (heure du serveur), strictement avant fin_donnees."""
    p = R().periodes
    s = source(nom)
    if s == "binance":
        from collapsar.ecole import crypto_monde as cm
        df = cm.charger(nom, p.fin_donnees)
    elif s == "minute":
        df = _cache_npz(f"{nom.replace('@', '_')}_15_{p.fin_donnees:%Y%m%d}", lambda: reechantillonner(minutes(nom), "15min"))
    else:
        df = dm.charger(nom, p.fin_donnees)
    return _propre(df)


# ------------------------------------------------------------------------------------------------ miroir
@lru_cache(maxsize=256)
def k_miroir(nom: str) -> float:
    return float(quinze(nom)["close"].iloc[0]) ** 2


def retourner(df: pd.DataFrame, k: float) -> pd.DataFrame:
    """Le marché retourné (chaque hausse devient une baisse) avec une constante k FIXÉE par marché (la même pour les
    minutes et les 15 min, sinon les zones des deux échelles ne seraient plus au même endroit)."""
    return pd.DataFrame({"time": df["time"].values, "open": k / df["open"].values, "high": k / df["low"].values,
                         "low": k / df["high"].values, "close": k / df["close"].values})


def nom_variante(nom: str, miroir: bool) -> str:
    return nom + MIROIR if miroir else nom


def quinze_variante(nom: str, miroir: bool) -> pd.DataFrame:
    df = quinze(nom)
    return retourner(df, k_miroir(nom)) if miroir else df


def minutes_variante(nom: str, miroir: bool) -> pd.DataFrame:
    df = minutes(nom)
    return retourner(df, k_miroir(nom)) if miroir else df


# ------------------------------------------------------------------------------------------------ conditions FTMO
def fiche_variante(nom: str, miroir: bool) -> Fiche:
    """Fiche pour l'horloge (mains/horloge.py) : le `fichier` est le marché FTMO de base (+ « _MIROIR »), pour que les
    nuits de chaque époque (mains/nuit.py) et la nuit triple soient celles du vrai marché."""
    if source(nom) == "binance":
        from collapsar.ecole import crypto_monde as cm
        return cm.fiche_crypto(nom_variante(nom, miroir))
    f = fiche(base(nom) + (MIROIR if miroir else ""))
    return f


def demi_frais(nom: str, cloture_reelle: np.ndarray) -> np.ndarray:
    """Demi-frais (un passage d'ordre) à chaque bougie, en part du prix ; calculés sur le prix RÉEL (même pour un
    miroir : le coût est celui du vrai marché à cette époque)."""
    if source(nom) == "binance":
        from collapsar.ecole import crypto_monde as cm
        return np.full(len(cloture_reelle), cm.frais_crypto(nom) / 2)
    from collapsar.mains import frais_ftmo
    return np.asarray(frais_ftmo.frais(base(nom), np.asarray(cloture_reelle, float)), float) / 2


def sources_conversion(noms) -> list[str]:
    from collapsar.mains.fiches import taux_vers_dollar
    out = []
    for n in noms:
        if source(n) == "binance":
            continue
        s, _ = taux_vers_dollar(fiche(base(n)).cotation)
        if s and s not in out:
            out.append(s)
    return out
