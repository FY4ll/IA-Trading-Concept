"""Or détenu par le fonds coté SPDR Gold Shares (GLD), un jour de Bourse par ligne (fournée 1, fiche F001 ;
20/10/2026). Fichier DÉJÀ LOCAL : data/maitres/spdr_gld/gld_reserves_quotidiennes.csv (18/11/2004 -> 16/10/2026,
LISEZMOI à côté ; usage privé seulement, clause du fichier).

Contenu du fichier : 5 716 lignes dont 205 jours fériés de la Bourse de New York SANS valeur (lignes vides : écartées
ici) ; la colonne `variation_tonnes` du fichier est vide le lendemain de chaque jour férié -> elle est RECALCULÉE ici
entre deux jours de Bourse consécutifs.

DATE DE PUBLICATION (`publie`, heure du serveur = New York + 7 h) : les chiffres du jour d sont mis en ligne vers
6h00-6h30 New York le jour de Bourse suivant -> utilisables le JOUR DE BOURSE SUIVANT à 10h00 New York (17h00 serveur),
marge prudente de la fiche F001. Le jour de Bourse suivant = la ligne suivante du fichier (vrai calendrier de la
Bourse de New York) ; pour la dernière ligne avant la date limite (la suite du fichier n'est pas lue), le jour ouvré
suivant hors fériés fédéraux, Vendredi saint et fermetures exceptionnelles (jamais avant le vrai jour suivant).

Colonnes rendues : date, publie, tonnes_or, variation_tonnes, cloture (prix de la part), prime_decote_pct,
volume_parts.
"""
from __future__ import annotations

import pandas as pd
from pandas.tseries.holiday import GoodFriday

from cerveau.donnees_hors_prix import RACINE, couper, feries_us, jour_ouvre_suivant, limite_sure, ny_vers_serveur

FICHIER = RACINE / "data" / "maitres" / "spdr_gld" / "gld_reserves_quotidiennes.csv"
HEURE = pd.Timedelta(hours=10)          # New York, le jour de Bourse suivant
# Bourse de New York fermée hors fériés fédéraux (deuils nationaux, ouragan Sandy)
FERMETURES_BOURSE = ["2004-06-11", "2007-01-02", "2012-10-29", "2012-10-30", "2018-12-05"]


def _fermetures_prudentes() -> set:
    """Fériés fédéraux + Vendredi saint + fermetures exceptionnelles : contient tous les jours de fermeture de la
    Bourse de New York, donc le « jour ouvré suivant » n'est jamais AVANT le vrai jour de Bourse suivant."""
    vendredis_saints = GoodFriday.dates("2004-01-01", "2026-12-31")
    return set(feries_us("2004-01-01", "2026-12-31")) | set(vendredis_saints) | set(pd.to_datetime(FERMETURES_BOURSE))


def charger(limite=None) -> pd.DataFrame:
    """Avoirs du fonds GLD publiés STRICTEMENT avant `limite` (heure du serveur ; défaut et maximum : 2024-01-01).
    Les lignes du fichier datées à partir de la limite ne sont pas lues (même pas leur date)."""
    lim = limite_sure(limite)
    d = pd.read_csv(FICHIER, parse_dates=["date"])
    d = d[(d["date"] < lim.normalize()) & d["tonnes_or"].notna()].sort_values("date").reset_index(drop=True)
    d["variation_tonnes"] = d["tonnes_or"].diff()
    suivant = d["date"].shift(-1)
    if len(d):
        suivant.iloc[-1] = jour_ouvre_suivant(d["date"].iloc[-1], _fermetures_prudentes())
    d["publie"] = ny_vers_serveur(suivant + HEURE)
    cols = ["date", "publie", "tonnes_or", "variation_tonnes", "cloture", "prime_decote_pct", "volume_parts"]
    return couper(d[cols], lim)
