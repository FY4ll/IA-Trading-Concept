"""Le calendrier économique (14/10/2026 : « les marchés sont un ensemble d'informations, pas juste des graphiques »).

Source : historique Forex Factory 2007 -> 04/2025 (data/calendrier/forex_factory_2007_2025.csv, jeu public Hugging Face
« Ehsanrs2/Forex_Factory_Calendar ») : heure exacte, devise, importance, annonce, valeur publiée, attendue, précédente,
et le sens habituel de l'effet (« publié au-dessus de l'attendu = bon pour la devise », ou l'inverse).

La SURPRISE d'une annonce = (publié - attendu), dans le sens « bon pour la devise », rapportée à la taille habituelle
des surprises de CETTE annonce calculée uniquement sur ses publications PASSÉES (jamais l'avenir).
Heures converties à l'heure du serveur (New York + 7 h), comme les prix.
"""
from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pandas as pd

from collapsar.donnees import marches as dm

FICHIER = dm.RACINE / "data" / "calendrier" / "forex_factory_2007_2025.csv"
CACHE = dm.RACINE / "collapsar" / "vie" / "cache" / "calendrier.pkl"
MULTIPLES = {"K": 1e3, "M": 1e6, "B": 1e9, "T": 1e12}
MIN_HISTOIRE = 8                      # publications passées nécessaires pour connaître la taille habituelle


MT5_HISTOIRE = dm.RACINE / "data" / "calendrier" / "mt5_calendrier_histoire.csv"
MT5_DIRECT = Path.home() / "AppData" / "Roaming" / "MetaQuotes" / "Terminal" / "Common" / "Files" / \
    "collapsar_calendrier_direct.csv"
IMPORTANCES_MT5 = {3: "High", 2: "Medium", 1: "Low"}


def _lire_mt5(fichier: Path) -> pd.DataFrame:
    d = pd.read_csv(fichier, sep=";", encoding="latin-1")
    t = pd.to_datetime(d["temps"], format="%Y.%m.%d %H:%M")
    # CORRECTION D'HEURE (vérifiée le 14/10, regarder/verifier_heures_annonces.py) : le calendrier de MetaTrader est
    # à une heure FIXE (celle de l'été), alors que l'heure du serveur (New York + 7 h, comme nos prix) recule d'une
    # heure en hiver : sans correction, le prix réagit 4 bougies AVANT l'heure du calendrier, chaque hiver
    ny = (t - pd.Timedelta(hours=7)).dt.tz_localize("America/New_York", ambiguous=True, nonexistent="shift_forward")
    decalage_ny = ny.dt.tz_localize(None) - ny.dt.tz_convert("UTC").dt.tz_localize(None)     # -4 h été, -5 h hiver
    hiver = decalage_ny == pd.Timedelta(hours=-5)
    d["temps"] = t - pd.to_timedelta(np.where(hiver, 1, 0), unit="h")
    return d


def charger_mt5(direct: bool = False) -> pd.DataFrame:
    """Le calendrier de METATRADER 5 (programme MQL5\\Experts\\Collapsar\\ExportCalendrier : historique depuis 2010,
    valeurs attendues depuis 2017 ; et le direct, rafraîchi chaque minute). Déjà à l'heure du serveur.
    Même forme que `charger()` : temps, devise, importance, annonce, surprise, z, id.
    Sens « bon pour la devise » de chaque annonce : MetaTrader l'indique pour chaque publication (impact +1/-1) ; le
    sens de l'annonce = celui le plus souvent constaté (propriété de l'annonce, pas d'un prix). La taille habituelle
    des surprises ne vient que des publications PASSÉES."""
    d = _lire_mt5(MT5_HISTOIRE)
    if direct and MT5_DIRECT.exists():
        d = pd.concat([d, _lire_mt5(MT5_DIRECT)]).drop_duplicates("id_valeur", keep="last")
    d = d[d["publie"].notna() & d["attendu"].notna()].sort_values("temps").reset_index(drop=True)
    ecart = d["publie"] - d["attendu"]
    constat = np.sign(ecart) * d["impact"]
    sens = constat.where(constat != 0).groupby(d["id_annonce"]).transform(lambda s: np.sign(s.sum()) or 1.0)
    d["surprise"] = ecart * sens.fillna(1.0)
    taille = d.groupby("id_annonce")["surprise"].transform(lambda s: s.abs().expanding().mean().shift(1))
    rang = d.groupby("id_annonce").cumcount()
    with np.errstate(divide="ignore", invalid="ignore"):
        z = d["surprise"] / taille
    return pd.DataFrame({"temps": d["temps"], "devise": d["devise"],
                         "importance": d["importance"].map(IMPORTANCES_MT5), "annonce": d["annonce"],
                         "surprise": d["surprise"],
                         "z": np.where((rang >= MIN_HISTOIRE) & (taille > 0), np.clip(z, -5, 5), np.nan),
                         "id_valeur": d["id_valeur"]})


def _nombre(texte) -> float:
    if not isinstance(texte, str) or not texte.strip():
        return np.nan
    t = texte.strip().replace(",", "").replace("<", "").replace(">", "")
    m = re.match(r"^(-?\d+(?:\.\d+)?)\s*([KMBT%]?)", t)
    if not m:
        return np.nan
    return float(m.group(1)) * MULTIPLES.get(m.group(2), 1.0)


def heure_serveur(utc: pd.Series) -> pd.Series:
    """UTC -> heure du serveur MetaTrader (New York + 7 h)."""
    return utc.dt.tz_convert("America/New_York").dt.tz_localize(None) + pd.Timedelta(hours=7)


def charger(cache: bool = True) -> pd.DataFrame:
    """Annonces chiffrées (publiée ET attendue connues), avec leur surprise normalisée `z` (dans le sens « bon pour la
    devise »), triées par heure du serveur."""
    if cache and CACHE.exists() and CACHE.stat().st_mtime > FICHIER.stat().st_mtime:
        return pd.read_pickle(CACHE)
    df = pd.read_csv(FICHIER)
    utc = pd.to_datetime(df["DateTime"], utc=True)
    # CORRECTION D'HEURE (vérifiée le 14/10, regarder/verifier_heures_annonces.py) : l'Iran a supprimé l'heure d'été
    # en 2022, mais le fichier marque encore les étés 2023+ en « +04:30 » alors que les heures affichées sont en
    # +03:30 : sans correction, le prix réagit 4 bougies (1 h) APRÈS l'heure du fichier (étés 2023 et 2024)
    faux = (utc.dt.year >= 2023) & df["DateTime"].str.endswith("+04:30")
    utc = utc + pd.to_timedelta(np.where(faux, 1, 0), unit="h")
    df = pd.DataFrame({
        "temps": heure_serveur(utc), "devise": df["Currency"], "importance": df["Impact"].str.split().str[0],
        "annonce": df["Event"], "publie": df["Actual"].map(_nombre), "attendu": df["Forecast"].map(_nombre),
        "inverse": df["Detail"].fillna("").str.contains("'Actual' less than 'Forecast' is good", regex=False)})
    df = df[df["publie"].notna() & df["attendu"].notna()].sort_values("temps").reset_index(drop=True)
    brut = (df["publie"] - df["attendu"]) * np.where(df["inverse"], -1.0, 1.0)
    df["surprise"] = brut
    # taille habituelle des surprises de cette annonce, sur ses publications PASSÉES seulement
    taille = (df.groupby(["devise", "annonce"])["surprise"]
              .transform(lambda s: s.abs().expanding().mean().shift(1)))
    rang = df.groupby(["devise", "annonce"]).cumcount()
    with np.errstate(divide="ignore", invalid="ignore"):
        z = brut / taille
    df["z"] = np.where((rang >= MIN_HISTOIRE) & (taille > 0), np.clip(z, -5, 5), np.nan)
    if cache:
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        df.to_pickle(CACHE)
    return df
