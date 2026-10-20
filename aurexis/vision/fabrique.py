"""Couche 2 -- la FABRIQUE de vision : à partir des bougies M15 d'un marché, tout ce que l'IA voit (indicateurs, toutes
les unités de temps M30 -> mois, contexte macro, vision du trader, boîte à outils). Même calcul pour tous les marchés,
à l'entraînement comme en direct. Équivalent exact de Run A src/aurexis_data.build_market_frame (prouvé par
tests/test_vision_equivalence.py)."""
from __future__ import annotations

import pandas as pd

from aurexis.donnees.reserve import recomposer, REGLES
from aurexis.vision import indicateurs, macro, outils, trader, unites_de_temps

COLONNE_ATR_BRUT = "atr_14_raw"      # ATR en prix, jamais normalisé (sert aux stops), comme Run A


def construire(nom: str, m15: pd.DataFrame, unites_contexte: list[str], dossier_macro: str | None,
               fred=None, boite_a_outils: bool = True) -> pd.DataFrame:
    trames = {"M15": m15}
    for u in unites_contexte:
        if u in REGLES:
            trames[u] = recomposer(m15, u)
    df, _ = unites_de_temps.fuse_mtf_frames(trames, "M15", unites_contexte)
    df = indicateurs.add_technical_features(df, fundamental_feed=None)
    df["fundamental_score"] = 0.0               # ancien score de nouvelles : neutre (aucun apport mesuré)
    if dossier_macro:
        df = macro.add_cross_asset_features(df, fred=fred, daily_provider=macro.csv_daily_provider(dossier_macro))
    df = trader.add_trader_vision(df, m5=None)
    if boite_a_outils:
        df = outils.add_toolbox(df)
    if "atr_14" in df.columns:
        df[COLONNE_ATR_BRUT] = df["atr_14"]
    df["symbol"] = nom
    return df
