"""DONNÉES HORS PRIX du cerveau (fournée 1 de l'usine, 20/10/2026) : chaque chargeur rend un tableau avec une
colonne `publie` = instant où l'information est devenue PUBLIQUE, à l'heure du serveur MetaTrader (New York + 7 h,
comme les prix). Un module ne doit utiliser une valeur qu'à partir de cet instant.

Règle d'honnêteté : un chargeur ne rend JAMAIS une valeur publiée à partir de la date limite (par défaut le
01/01/2024 : le coffre 2024-01-01 -> 2026-10-13 est fermé) ; une date limite plus tardive est refusée.

Sources (fichiers dans data/hors_prix/<source>/, hors git) :
- cftc_tff.py      : positions des gérants d'actifs / fonds à effet de levier sur 7 devises (CFTC, hebdomadaire)
- fed_liquidite.py : bilan de la Fed, compte du Trésor, pensions inversées (FRED / ALFRED)
- fomc.py          : décisions de la Fed, prévues et exceptionnelles, avec l'heure de l'annonce
- gld.py           : or détenu par le fonds GLD (data/maitres/spdr_gld, déjà local)
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
from pandas.tseries.holiday import USFederalHolidayCalendar

RACINE = Path(__file__).resolve().parents[2]            # Test_IA
DOSSIER = RACINE / "data" / "hors_prix"
COFFRE = pd.Timestamp("2024-01-01")                     # rien de publié à partir de cette date n'est rendu
DECALAGE_SERVEUR = pd.Timedelta(hours=7)                # heure du serveur = heure de New York + 7 h


def limite_sure(limite=None) -> pd.Timestamp:
    """La date limite demandée (heure du serveur), jamais après le coffre."""
    lim = COFFRE if limite is None else pd.Timestamp(limite)
    if lim > COFFRE:
        raise ValueError(f"date limite {lim:%Y-%m-%d} refusée : le coffre ({COFFRE:%Y-%m-%d} ->) est fermé")
    return lim


def ny_vers_serveur(t) -> pd.Series:
    """Heure locale de New York (sans fuseau) -> heure du serveur MetaTrader. Le serveur suit l'heure d'été de
    New York (New York + 7 h toute l'année) : le décalage est donc constant."""
    return pd.to_datetime(t) + DECALAGE_SERVEUR


def couper(df: pd.DataFrame, limite=None) -> pd.DataFrame:
    """Garde seulement ce qui est publié STRICTEMENT avant la date limite, trié par instant de publication."""
    lim = limite_sure(limite)
    df = df.copy()
    for c in ("date", "publie"):                        # pandas 3 lit en µs ; le reste du projet compte en ns
        df[c] = pd.to_datetime(df[c]).astype("datetime64[ns]")
    return df[df["publie"] < lim].sort_values(["publie"], kind="stable").reset_index(drop=True)


def feries_us(debut="2000-01-01", fin="2026-12-31") -> pd.DatetimeIndex:
    """Jours fériés fédéraux américains (calendrier officiel de pandas ; les jours de deuil national exceptionnels
    sont traités à part par chaque chargeur)."""
    return USFederalHolidayCalendar().holidays(debut, fin)


def jour_ouvre_suivant(jour: pd.Timestamp, feries: set, inclus: bool = False) -> pd.Timestamp:
    """Premier jour de semaine non férié après `jour` (ou `jour` lui-même si `inclus` et ouvré)."""
    j = pd.Timestamp(jour).normalize()
    if not inclus:
        j += pd.Timedelta(days=1)
    while j.dayofweek >= 5 or j in feries:
        j += pd.Timedelta(days=1)
    return j
