"""Les marchés FTMO.

- Source : bougies de 15 minutes (Dukascopy dans data/fx_intraday ; l'or depuis 2004 dans data/kaggle_gold).
- Toutes les échelles (1 h, 4 h, jour, semaine, mois) sont fabriquées à partir des 15 minutes.
- RÈGLE D'HONNÊTETÉ (CONCEPTION, section 8) : par défaut, `charger` ne rend QUE les bougies d'avant 2023.
  Les périodes d'examen (2023 -> septembre 2025) et les 12 mois cachés ne servent jamais à apprendre.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

RACINE = Path(__file__).resolve().parents[2]          # Test_IA
DOSSIER_M15 = RACINE / "data" / "fx_intraday"
OR_15M = RACINE / "data" / "kaggle_gold" / "XAU_15m_data.csv"
CACHE = RACINE / "collapsar" / "vie" / "cache" / "donnees"

FIN_APPRENTISSAGE = pd.Timestamp("2023-01-01")        # tout ce qui sert à apprendre est AVANT
FIN_EXAMEN = pd.Timestamp("2025-10-01")               # après : les mois cachés (verdict de vérité)

QUINZE = np.timedelta64(15, "m")
ECHELLES = ["15 min", "1 h", "4 h", "jour", "semaine", "mois"]
MIN_BOUGIES = 20_000                                  # un marché trop court avant 2023 est ignoré


def liste_marches() -> list[str]:
    noms = sorted(p.name[:-len("_M15.csv")] for p in DOSSIER_M15.glob("*_M15.csv"))
    if OR_15M.exists() and "XAUUSD" not in noms:
        noms.append("XAUUSD")
    return sorted(noms)


def _lire_brut(symbole: str) -> pd.DataFrame:
    if symbole == "XAUUSD" and OR_15M.exists():    # le petit fichier fx_intraday de l'or ne couvre que 2026
        df = pd.read_csv(OR_15M, sep=";")
        df.columns = [c.lower() for c in df.columns]
        df = df.rename(columns={"date": "time"})
        df["time"] = pd.to_datetime(df["time"], format="%Y.%m.%d %H:%M")
    else:
        df = pd.read_csv(DOSSIER_M15 / f"{symbole}_M15.csv")
        df["time"] = pd.to_datetime(df["time"])
    df["time"] = df["time"].astype("datetime64[ns]")   # 16/10 : pandas 3 lit en µs ; le reste du projet compte en ns
    df = df[["time", "open", "high", "low", "close", "volume"]].dropna()
    prix = df[["open", "high", "low", "close"]]
    df = df[(prix > 0).all(axis=1)]
    df = df.sort_values("time").drop_duplicates("time", keep="last").reset_index(drop=True)
    # une bougie dont le plus haut / plus bas ne contient pas ouverture et clôture est réparée
    df["high"] = df[["open", "high", "low", "close"]].max(axis=1)
    df["low"] = df[["open", "high", "low", "close"]].min(axis=1)
    return df


def charger(symbole: str, jusqua: pd.Timestamp = FIN_APPRENTISSAGE, cache: bool = True) -> pd.DataFrame:
    """Bougies de 15 minutes du marché, STRICTEMENT avant `jusqua` (par défaut : avant 2023).
    Le cache se refait tout seul si le fichier du marché a changé (ex. historique téléchargé plus long)."""
    source = OR_15M if (symbole == "XAUUSD" and OR_15M.exists()) else DOSSIER_M15 / f"{symbole}_M15.csv"
    version = int(source.stat().st_mtime) if source.exists() else 0
    fichier = CACHE / f"{symbole}_{jusqua:%Y%m%d}_{version}.npz"
    if cache and fichier.exists():
        z = np.load(fichier)
        return pd.DataFrame({"time": pd.to_datetime(z["time"]).astype("datetime64[ns]"), **{k: z[k] for k in
                             ("open", "high", "low", "close", "volume")}})
    df = _lire_brut(symbole)
    df = df[df["time"] < jusqua].reset_index(drop=True)
    if cache:
        CACHE.mkdir(parents=True, exist_ok=True)
        np.savez(fichier, time=df["time"].values.astype("datetime64[ns]"),
                 **{k: df[k].to_numpy(np.float64) for k in ("open", "high", "low", "close", "volume")})
    return df


def miroir(df: pd.DataFrame) -> pd.DataFrame:
    """Le marché RETOURNÉ (chaque hausse devient une baisse, au même niveau de prix) : pour l'entraînement seulement,
    afin qu'une tendance passée ne puisse pas être apprise par cœur (« vendre gros a toujours payé »)."""
    k = float(df["close"].iloc[0]) ** 2
    return pd.DataFrame({"time": df["time"].values, "open": k / df["open"].values, "high": k / df["low"].values,
                         "low": k / df["high"].values, "close": k / df["close"].values, "volume": df["volume"].values})


def debut_echelle(t: np.ndarray, echelle: str) -> np.ndarray:
    """Heure d'ouverture de la bougie de `echelle` qui contient chaque instant `t` (datetime64[ns])."""
    t = t.astype("datetime64[ns]")
    if echelle == "15 min":
        return t.astype("datetime64[m]").astype("datetime64[ns]") - (t.astype("datetime64[m]").astype(np.int64) % 15
                                                                        ).astype("timedelta64[m]")
    if echelle == "1 h":
        return t.astype("datetime64[h]").astype("datetime64[ns]")
    if echelle == "4 h":
        h = t.astype("datetime64[h]")
        return (h - (h.astype(np.int64) % 4).astype("timedelta64[h]")).astype("datetime64[ns]")
    if echelle == "jour":
        return t.astype("datetime64[D]").astype("datetime64[ns]")
    if echelle == "semaine":                 # la semaine des marchés commence le dimanche (ouverture du soir)
        j = t.astype("datetime64[D]")
        jour_semaine = (j.astype(np.int64) + 4) % 7           # 0 = dimanche (le 01/01/1970 était un jeudi)
        return (j - jour_semaine.astype("timedelta64[D]")).astype("datetime64[ns]")
    if echelle == "mois":
        return t.astype("datetime64[M]").astype("datetime64[ns]")
    raise ValueError(echelle)


def fin_echelle(debut: np.ndarray, echelle: str) -> np.ndarray:
    """Heure de fermeture (exclue) de chaque bougie de `echelle`."""
    d = debut.astype("datetime64[ns]")
    if echelle == "15 min":
        return d + QUINZE
    if echelle == "1 h":
        return d + np.timedelta64(1, "h")
    if echelle == "4 h":
        return d + np.timedelta64(4, "h")
    if echelle == "jour":
        return d + np.timedelta64(1, "D")
    if echelle == "semaine":
        return d + np.timedelta64(7, "D")
    if echelle == "mois":
        return (d.astype("datetime64[M]") + 1).astype("datetime64[ns]")
    raise ValueError(echelle)


def echelle(df: pd.DataFrame, nom: str) -> dict:
    """Bougies de l'échelle `nom` fabriquées à partir des 15 minutes : debut, fin, open, high, low, close, volume."""
    t = df["time"].values.astype("datetime64[ns]")
    if nom == "15 min":
        debut = t
        o, h, l, c, v = (df[k].to_numpy(np.float64) for k in ("open", "high", "low", "close", "volume"))
    else:
        cle = debut_echelle(t, nom)
        g = pd.DataFrame({"cle": cle, "open": df["open"].values, "high": df["high"].values,
                          "low": df["low"].values, "close": df["close"].values,
                          "volume": df["volume"].values}).groupby("cle", sort=True)
        a = g.agg(open=("open", "first"), high=("high", "max"), low=("low", "min"), close=("close", "last"),
                  volume=("volume", "sum"))
        debut = a.index.values.astype("datetime64[ns]")
        o, h, l, c, v = (a[k].to_numpy(np.float64) for k in ("open", "high", "low", "close", "volume"))
    return {"debut": debut, "fin": fin_echelle(debut, nom), "open": o, "high": h, "low": l, "close": c, "volume": v}


def dernieres_terminees(temps_15: np.ndarray, ech: dict, decision: np.ndarray | None = None) -> np.ndarray:
    """Pour chaque bougie (décision prise à sa clôture : `decision`, par défaut ouverture + 15 minutes), l'indice de
    la dernière bougie de l'échelle déjà TERMINÉE à ce moment-là (-1 s'il n'y en a pas). Elle ne voit jamais une
    bougie pas encore fermée."""
    if decision is None:
        decision = temps_15.astype("datetime64[ns]") + QUINZE
    return np.searchsorted(ech["fin"], decision.astype("datetime64[ns]"), side="right").astype(np.int64) - 1


DOSSIER_H1 = RACINE / "data" / "fx_h1"


def charger_horaire(symbole: str, avant: pd.Timestamp, jusqua: pd.Timestamp = FIN_APPRENTISSAGE) -> pd.DataFrame:
    """Bougies d'UNE HEURE du marché (data/fx_h1, Dukascopy, heure serveur) strictement avant `avant` (le début de
    ses bougies de 15 minutes) et avant `jusqua`. Vide si le fichier n'existe pas encore."""
    f = DOSSIER_H1 / f"{symbole}_H1.csv"
    if not f.exists():
        return pd.DataFrame(columns=["time", "open", "high", "low", "close", "volume"])
    df = pd.read_csv(f, parse_dates=["time"])
    df["time"] = df["time"].astype("datetime64[ns]")   # 16/10 (audit, défaut 1) : pandas 3 lit en µs ; projet en ns
    df = df[(df["time"] < min(avant, jusqua))].dropna()
    df = df[(df[["open", "high", "low", "close"]] > 0).all(axis=1)].sort_values("time").reset_index(drop=True)
    df["high"] = df[["open", "high", "low", "close"]].max(axis=1)
    df["low"] = df[["open", "high", "low", "close"]].min(axis=1)
    return df
