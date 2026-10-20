"""Couche 1 -- la RÉSERVE de données : un seul format pour tous les marchés (bougies de 15 minutes, heure du serveur
du courtier = New York + 7 h), lue depuis les fichiers sources puis gardée en copie rapide (.npz) dans
aurexis/reserve/. Transformations de données : recomposition en unités plus longues, marché INVERSÉ (apprendre à
vendre), MÉLANGEUR de vrais jours. Repris de Run A (src/data_loader.py, src/aurexis_data.py), calculs identiques."""
from __future__ import annotations
import os

import numpy as np
import pandas as pd

RESERVE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "reserve")
REGLES = {"M30": "30min", "H1": "1h", "H4": "4h", "D1": "1D", "W1": "W-MON", "MN1": "MS"}
COLONNES = ["time", "open", "high", "low", "close", "volume"]


# ----------------------------------------------------------------------------------------------- lecture des sources
def _separateur(chemin: str) -> str:
    with open(chemin, "r", encoding="utf-8", errors="ignore") as f:
        premiere = f.readline()
    n = {s: premiere.count(s) for s in [";", ",", "\t"]}
    return max(n, key=n.get) if max(n.values()) > 0 else ","


def lire_csv_ohlcv(chemin: str, nrows: int | None = None) -> pd.DataFrame:
    """CSV OHLCV de source quelconque (Kaggle, export MT5…) : séparateur, colonne(s) date/heure et noms détectés."""
    brut = pd.read_csv(chemin, sep=_separateur(chemin), nrows=nrows)
    brut.columns = [c.strip() for c in brut.columns]
    bas = {c.lower(): c for c in brut.columns}

    def col(*noms):
        for n in noms:
            if n in bas:
                return bas[n]
        return None
    d, h, dh = col("date"), col("time"), col("datetime", "timestamp", "gmt time", "local time")
    if dh:
        t = pd.to_datetime(brut[dh], errors="coerce")
    elif d and h and d != h:
        t = pd.to_datetime(brut[d].astype(str).str.replace(".", "-", regex=False) + " " + brut[h].astype(str),
                           errors="coerce")
    elif d:
        t = pd.to_datetime(brut[d].astype(str).str.replace(".", "-", regex=False), errors="coerce")
    else:
        raise ValueError(f"aucune colonne date/heure dans {chemin} ({list(brut.columns)})")
    o, hi, lo, c, v = col("open"), col("high"), col("low"), col("close"), col("volume", "vol", "tick_volume", "tickvol")
    for nom, x in [("open", o), ("high", hi), ("low", lo), ("close", c)]:
        if x is None:
            raise ValueError(f"colonne {nom} introuvable dans {chemin}")
    df = pd.DataFrame({"time": t, "open": pd.to_numeric(brut[o], errors="coerce"),
                       "high": pd.to_numeric(brut[hi], errors="coerce"), "low": pd.to_numeric(brut[lo], errors="coerce"),
                       "close": pd.to_numeric(brut[c], errors="coerce"),
                       "volume": pd.to_numeric(brut[v], errors="coerce") if v else 0.0})
    df = df.dropna(subset=["time", "open", "high", "low", "close"])
    return df.sort_values("time").drop_duplicates(subset="time").reset_index(drop=True)


def charger_m15(chemin: str) -> pd.DataFrame:
    """Bougies de 15 minutes d'un fichier source (format Dukascopy « time,open,… » ou CSV générique)."""
    tete = pd.read_csv(chemin, nrows=2)
    df = pd.read_csv(chemin) if "time" in tete.columns else lire_csv_ohlcv(chemin)
    df["time"] = pd.to_datetime(df["time"]).astype("datetime64[ns]")   # même précision pour toutes les sources
    df = df.sort_values("time").drop_duplicates("time").reset_index(drop=True)
    if "volume" not in df.columns:
        df["volume"] = 0.0
    return df[COLONNES]


# ----------------------------------------------------------------------------------------------- la réserve
def lire(nom: str, source: str) -> pd.DataFrame:
    """Bougies M15 du marché `nom` : copie rapide de la réserve si elle est à jour, sinon relue de `source`."""
    os.makedirs(RESERVE, exist_ok=True)
    rapide = os.path.join(RESERVE, f"{nom}.npz")
    if os.path.exists(rapide) and os.path.getmtime(rapide) >= os.path.getmtime(source):
        z = np.load(rapide)
        return pd.DataFrame({"time": pd.to_datetime(z["time"]), **{c: z[c] for c in COLONNES[1:]}})
    df = charger_m15(source)
    np.savez(rapide, time=df["time"].to_numpy().astype("datetime64[ns]"),
             **{c: df[c].to_numpy(np.float64) for c in COLONNES[1:]})
    return df


# ----------------------------------------------------------------------------------------------- transformations
def recomposer(m15: pd.DataFrame, unite: str) -> pd.DataFrame:
    """Bougies M15 -> unité plus longue (étiquette = ouverture de la bougie, comme MT5)."""
    kw = {"label": "left", "closed": "left"}
    s = m15.set_index("time")
    r = REGLES[unite]
    out = pd.DataFrame({"open": s["open"].resample(r, **kw).first(), "high": s["high"].resample(r, **kw).max(),
                        "low": s["low"].resample(r, **kw).min(), "close": s["close"].resample(r, **kw).last(),
                        "volume": s["volume"].resample(r, **kw).sum()}).dropna(subset=["open"])
    return out.reset_index()


def inverser(m15: pd.DataFrame, k: float | None = None) -> pd.DataFrame:
    """Marché à l'envers : p -> k/p (k = p0², ou imposé pour inverser une autre tranche au même niveau)."""
    k = float(m15["close"].iloc[0]) ** 2 if k is None else float(k)
    out = m15.copy()
    out["open"], out["close"] = k / m15["open"], k / m15["close"]
    out["high"], out["low"] = k / m15["low"], k / m15["high"]
    return out


def melanger_jours(m15: pd.DataFrame, rng) -> pd.DataFrame | None:
    """Mélangeur logique : calendrier conservé, chaque jour = un vrai jour de la période tiré au hasard ; aucune
    bougie plus forte que la plus forte bougie réelle ; prix recousu en continu."""
    d = m15.reset_index(drop=True)
    if len(d) < 200:
        return None
    prec = d["close"].shift(1)
    rel = pd.DataFrame({k: np.log(d[k] / prec) for k in ("open", "high", "low", "close")})
    rel["volume"], rel["time"] = d["volume"].to_numpy(), pd.to_datetime(d["time"]).to_numpy()
    rel = rel.iloc[1:].reset_index(drop=True)
    jours = [g for _, g in rel.groupby(pd.to_datetime(rel["time"]).dt.normalize())]
    if len(jours) < 5:
        return None
    morceaux = []
    for cible in jours:
        src = jours[int(rng.integers(len(jours)))].copy()
        st = pd.to_datetime(src["time"])
        src["time"] = (pd.Timestamp(cible["time"].iloc[0]).normalize() + (st - st.dt.normalize())).to_numpy()
        morceaux.append(src)
    m = pd.concat(morceaux, ignore_index=True)
    c0 = float(np.log(d["close"].iloc[0]))
    lc = c0 + np.cumsum(m["close"].to_numpy())
    pc = np.concatenate([[c0], lc[:-1]])
    return pd.DataFrame({"time": pd.to_datetime(m["time"]), "open": np.exp(pc + m["open"].to_numpy()),
                         "high": np.exp(pc + m["high"].to_numpy()), "low": np.exp(pc + m["low"].to_numpy()),
                         "close": np.exp(lc), "volume": m["volume"].to_numpy()})
