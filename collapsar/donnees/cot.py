"""Positionnement des fonds sur l'or (rapport COT désagrégé de la CFTC, or COMEX), SANS FUTUR (20/10/2026).

Les positions sont celles du MARDI, publiées le VENDREDI 15h30 heure de New York (22h30 serveur). Règles prudentes :
- semaine avec un jour férié fédéral américain (du lundi de la semaine des positions au vendredi) : publication
  supposée le lundi suivant 15h30 New York (le mardi si ce lundi est férié) ;
- paralysies de l'État fédéral (rattrapages étalés, dates exactes incertaines) : semaines EXCLUES ;
- l'info n'est utilisable qu'à l'ouverture du premier jour de cotation strictement après la publication.
Signaux (plan figé `collapsar/vie/cot_or/plan_fige.md`) : V1, V4, P52, P156, PL, PS, DIV, X52, X156.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from pandas.tseries.holiday import USFederalHolidayCalendar

from collapsar.donnees.marches import RACINE

FICHIER = RACINE / "data" / "maitres" / "cftc_cot" / "cot_desagrege_or_comex.csv"
EXCLUS = [(pd.Timestamp("2013-10-01"), pd.Timestamp("2013-11-19")),
          (pd.Timestamp("2018-12-24"), pd.Timestamp("2019-03-05")),
          (pd.Timestamp("2025-09-30"), pd.Timestamp("2025-11-30"))]
SIGNAUX = ("V1", "V4", "P52", "P156", "PL", "PS", "DIV", "X52", "X156")
HEURE_PUBLI = pd.Timedelta(hours=15, minutes=30)        # heure de New York


def charger(jusqua: pd.Timestamp | str | None = None) -> pd.DataFrame:
    """Lignes COT (date des positions <= jusqua), triées."""
    c = pd.read_csv(FICHIER, parse_dates=["date"])
    if jusqua is not None:
        c = c[c["date"] <= pd.Timestamp(jusqua)]
    return c.sort_values("date").reset_index(drop=True)


def _feries(debut="2005-01-01", fin="2027-12-31") -> set:
    return set(USFederalHolidayCalendar().holidays(debut, fin))


def publication(dates: pd.Series) -> pd.Series:
    """Instant de publication (heure de New York) de chaque date de positions, règle prudente des jours fériés."""
    fer = _feries()
    out = []
    for d in pd.DatetimeIndex(dates):
        lundi = d - pd.Timedelta(days=d.dayofweek)
        vendredi = lundi + pd.Timedelta(days=4)
        jours = pd.date_range(lundi, vendredi)
        pub = vendredi
        if any(j in fer for j in jours):
            pub = vendredi + pd.Timedelta(days=3)
            while pub in fer or pub.dayofweek >= 5:
                pub += pd.Timedelta(days=1)
        out.append(pub + HEURE_PUBLI)
    return pd.Series(out, index=dates.index if hasattr(dates, "index") else None)


def exclu(dates: pd.Series) -> np.ndarray:
    d = pd.DatetimeIndex(dates)
    m = np.zeros(len(d), bool)
    for a, b in EXCLUS:
        m |= (d >= a) & (d <= b)
    return m


def _rang_fenetre(x: pd.Series, n: int) -> pd.Series:
    """Rang en centile (0..1) de la valeur courante parmi les n dernières (courante comprise)."""
    def f(a):
        return (a[:-1] < a[-1]).mean() + 0.5 * (a[:-1] == a[-1]).mean() if len(a) > 1 else np.nan
    return x.rolling(n, min_periods=n).apply(f, raw=True)


def signaux(c: pd.DataFrame, cloture_mardi: pd.Series) -> pd.DataFrame:
    """Les 9 signaux, ligne par ligne, avec seulement le passé. `cloture_mardi` = clôture de l'or au jour des positions
    (même index que c ; dernière clôture connue <= date des positions)."""
    L = c["M_Money_Positions_Long_All"].astype(float)
    S = c["M_Money_Positions_Short_All"].astype(float)
    oi = c["Open_Interest_All"].astype(float)
    net = L - S
    s = pd.DataFrame({"date": c["date"]})
    s["V1"] = net.diff(1) / oi
    s["V4"] = net.diff(4) / oi
    no = net / oi
    s["P52"] = _rang_fenetre(no, 52)
    s["P156"] = _rang_fenetre(no, 156)
    s["PL"] = L / (L + S)
    s["PS"] = s["PL"].rolling(52, min_periods=52).mean()
    r4 = np.log(pd.Series(np.asarray(cloture_mardi, float), index=c.index)).diff(4)

    def z(x):
        m = x.rolling(156, min_periods=104).mean()
        e = x.rolling(156, min_periods=104).std()
        return (x - m) / e
    s["DIV"] = z(s["V4"]) - z(r4)
    for n in (52, 156):
        p = s[f"P{n}"]
        s[f"X{n}"] = np.where(p <= 0.10, 1.0, np.where(p >= 0.90, -1.0, 0.0))
        s.loc[p.isna(), f"X{n}"] = np.nan
    return s
