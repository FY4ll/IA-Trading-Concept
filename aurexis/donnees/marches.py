"""Couche 1 -- le CATALOGUE des marchés FTMO : nom (comme chez FTMO), famille, fichier source des bougies M15.
Un marché n'est utilisable que si son fichier existe (téléchargements Dukascopy : runs/.../code/scripts/
fetch_dukascopy.py). Liste FTMO exacte et noms MT5 à confirmer avec l'essai FTMO."""
from __future__ import annotations
import os

DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data")
DUKA = os.path.join(DATA, "fx_intraday")

_FOREX = ["EURUSD", "GBPUSD", "USDJPY", "USDCHF", "AUDUSD", "USDCAD", "NZDUSD", "EURGBP", "EURJPY", "GBPJPY", "EURCHF",
          "EURAUD", "EURCAD", "EURNZD", "GBPCHF", "GBPAUD", "GBPCAD", "GBPNZD", "AUDJPY", "AUDCHF", "AUDCAD", "AUDNZD",
          "NZDJPY", "NZDCHF", "NZDCAD", "CADJPY", "CADCHF", "CHFJPY"]
# nom FTMO -> (famille, symbole Dukascopy)
_AUTRES = {
    "XAGUSD": ("métal", "XAGUSD"),
    "US500": ("indice", "USA500IDXUSD"), "US100": ("indice", "USATECHIDXUSD"), "US30": ("indice", "USA30IDXUSD"),
    "GER40": ("indice", "DEUIDXEUR"), "UK100": ("indice", "GBRIDXGBP"), "JP225": ("indice", "JPNIDXJPY"),
    "FRA40": ("indice", "FRAIDXEUR"), "EU50": ("indice", "EUSIDXEUR"), "AUS200": ("indice", "AUSIDXAUD"),
    "USOIL": ("énergie", "LIGHTCMDUSD"), "UKOIL": ("énergie", "BRENTCMDUSD"), "NATGAS": ("énergie", "GASCMDUSD"),
    "BTCUSD": ("crypto", "BTCUSD"), "ETHUSD": ("crypto", "ETHUSD"), "LTCUSD": ("crypto", "LTCUSD"),
    "XRPUSD": ("crypto", "XRPUSD"),
}

MARCHES: dict[str, dict] = {"XAUUSD": {"famille": "métal", "source": os.path.join(DATA, "kaggle_gold", "XAU_15m_data.csv")}}
MARCHES.update({n: {"famille": "devise", "source": os.path.join(DUKA, f"{n}_M15.csv")} for n in _FOREX})
MARCHES.update({n: {"famille": f, "source": os.path.join(DUKA, f"{s}_M15.csv")} for n, (f, s) in _AUTRES.items()})


def disponibles() -> list[str]:
    """Marchés dont les bougies sont déjà téléchargées."""
    return [n for n, m in MARCHES.items() if os.path.exists(m["source"])]


def source(nom: str) -> str:
    return MARCHES[nom]["source"]
