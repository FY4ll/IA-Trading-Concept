"""Les bougies du laboratoire SMC (docs/SMC_DEFINITIONS.md, partie A) : M5, M15, H1 à l'heure de New York, avec ATR,
volume de cotation, killzones, facteur d'écart de l'ouverture de New York."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from collapsar.donnees import marches as dm

MARCHES = {"XAUUSD": "XAUUSD", "NAS100": "USATECHIDXUSD", "US500": "USA500IDXUSD", "EURUSD": "EURUSD"}
UNITES = {"M5": "5min", "M15": "15min", "H1": "1h"}
UNITES_FOND = {"H4": "4h", "D1": "1D", "M3": "3min", "M30": "30min"}   # multi-unités, cascade zones supply and demand
FREQ = {**UNITES, **UNITES_FOND}
FRAIS = {"XAUUSD": 0.00012, "NAS100": 0.00012, "US500": 0.00012, "EURUSD": 0.00006}   # fiches FTMO, aller-retour
FACTEUR_OUVERTURE = {"NAS100": 1.07, "US500": 1.16, "XAUUSD": 1.0, "EURUSD": 1.0}      # 1re heure de New York
DEBUT = pd.Timestamp("2015-01-01")


@dataclass
class Bougies:
    marche: str
    unite: str
    t: np.ndarray          # heure de New York (datetime64)
    o: np.ndarray
    h: np.ndarray
    l: np.ndarray
    c: np.ndarray
    v: np.ndarray          # volume de cotation
    atr: np.ndarray
    minute: np.ndarray     # minute de la journée (New York)
    jour: np.ndarray       # numéro du jour de New York
    haut_veille: np.ndarray
    bas_veille: np.ndarray
    facteur: np.ndarray    # élargissement de l'écart (1re heure de la séance de New York)
    frais: float
    bt: np.ndarray         # début de chaque bougie (entier, nanosecondes)
    duree: int             # durée d'une bougie (nanosecondes)
    mt: np.ndarray         # les minutes (pour suivre la bougie d'entrée minute par minute)
    mo: np.ndarray
    mh: np.ndarray
    ml: np.ndarray

    @property
    def n(self) -> int:
        return len(self.c)


def minutes(marche: str) -> pd.DataFrame:
    if marche == "XAUUSD":
        df = pd.read_csv(dm.RACINE / "data" / "kaggle_gold" / "XAU_1m_data.csv", sep=";")
        df.columns = [c.lower() for c in df.columns]
        df["ny"] = (pd.to_datetime(df["date"], format="%Y.%m.%d %H:%M") - pd.Timedelta(hours=7)).astype("datetime64[ns]")
    else:
        from collapsar.donnees.histdata import charger
        df = charger({"NAS100": "NSXUSD", "US500": "SPXUSD", "EURUSD": "EURUSD"}[marche])
        df["volume"] = np.nan
    df = df[df["ny"] >= DEBUT - pd.Timedelta(days=40)]
    return df[["ny", "open", "high", "low", "close", "volume"]].dropna(subset=["close"])


def _volume_dukascopy(marche: str) -> pd.Series:
    """Volume de cotation Dukascopy des bougies de 15 min (heure serveur - 7 h = New York)."""
    d = dm.charger(MARCHES[marche], jusqua=pd.Timestamp("2100-01-01"))
    return pd.Series(d["volume"].to_numpy(float), index=pd.to_datetime(d["time"]) - pd.Timedelta(hours=7))


def bougies(marche: str, unite: str, jusqua: pd.Timestamp, m1: pd.DataFrame | None = None,
            frais: float | None = None, facteur_ouverture: float | None = None, volume_inclus: bool = False) -> Bougies:
    """`m1` : les plus petites bougies disponibles (minutes, ou bougies de 15 min pour les ~45 marchés). Les trois
    derniers arguments servent aux marchés hors des 4 de base (frais de leur fiche, volume déjà dans `m1`)."""
    m1 = minutes(marche) if m1 is None else m1
    m1 = m1[m1["ny"] < jusqua]
    g = m1.set_index("ny").resample(FREQ[unite], label="left", closed="left")
    b = g.agg({"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}).dropna(
        subset=["open"])
    if marche != "XAUUSD" and not volume_inclus:
        v15 = _volume_dukascopy(marche)
        if unite == "M15":
            b["volume"] = v15.reindex(b.index).to_numpy()
        elif unite in ("M5", "M3"):
            b["volume"] = v15.reindex(b.index.floor("15min")).to_numpy() / (3 if unite == "M5" else 5)
        else:
            b["volume"] = v15.resample(FREQ[unite]).sum().reindex(b.index).to_numpy()
    b["volume"] = b["volume"].fillna(0.0)
    o, h, l, c = (b[k].to_numpy(float) for k in ("open", "high", "low", "close"))
    tr = np.maximum(h - l, np.maximum(np.abs(h - np.r_[c[0], c[:-1]]), np.abs(l - np.r_[c[0], c[:-1]])))
    atr = pd.Series(tr).rolling(14, min_periods=14).mean().to_numpy()
    t = b.index
    minute = (t.hour * 60 + t.minute).to_numpy()
    jours = t.normalize()
    jour_num = ((jours - pd.Timestamp("2000-01-01")).days).to_numpy()
    par_jour = b.groupby(jours).agg(hh=("high", "max"), ll=("low", "min"))
    veille = par_jour.shift(1)
    hv = veille["hh"].reindex(jours).to_numpy()
    lv = veille["ll"].reindex(jours).to_numpy()
    fo = FACTEUR_OUVERTURE[marche] if facteur_ouverture is None else facteur_ouverture
    facteur = np.where((minute >= 570) & (minute < 630), fo, 1.0)
    garde = np.isfinite(atr) & (t >= DEBUT)
    sel = lambda x: np.ascontiguousarray(x[garde])
    m = m1.sort_values("ny")
    tns = t.values.astype("datetime64[ns]")      # 16/10 : pandas 3 lit les heures en µs ; tout le labo compte en ns
    return Bougies(marche, unite, sel(tns), sel(o), sel(h), sel(l), sel(c), sel(b["volume"].to_numpy(float)),
                   sel(atr), sel(minute).astype(np.int64), sel(jour_num).astype(np.int64), sel(np.nan_to_num(hv)),
                   sel(np.nan_to_num(lv)), sel(facteur), FRAIS[marche] if frais is None else frais,
                   sel(tns).astype(np.int64),
                   int(pd.Timedelta(FREQ[unite]).value), m["ny"].to_numpy().astype("datetime64[ns]").astype(np.int64),
                   m["open"].to_numpy(float), m["high"].to_numpy(float), m["low"].to_numpy(float))
