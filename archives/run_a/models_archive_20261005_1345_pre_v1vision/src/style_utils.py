"""Un style de trading est normalement une timeframe ("H1"). Un suffixe désigne une lignée
distincte entraînée sur les MÊMES bougies que sa timeframe de base :
  - "T" ("H1T") : avec un take-profit appris (voir environment.style_overrides) ;
  - "X" ("H1X") : avec en plus des variables hors XAUUSD (voir src/cross_asset.py) ;
  - "XT" ("H1XT") : les deux."""
import re

_VARIANT = re.compile(r"^([MHDW]\d+)[TX]{1,2}$")


def base_timeframe(style: str) -> str:
    m = _VARIANT.match(style or "")
    return m.group(1) if m else style
