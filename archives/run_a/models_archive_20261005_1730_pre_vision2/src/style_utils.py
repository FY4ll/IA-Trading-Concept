"""Un style de trading est normalement une timeframe ("H1"). Un suffixe désigne une lignée
distincte entraînée sur les MÊMES bougies que sa timeframe de base :
  - "T" ("H1T") : avec un take-profit appris (voir environment.style_overrides) ;
  - "X" ("H1X") : avec en plus des variables hors XAUUSD (voir src/cross_asset.py) ;
  - "XT" ("H1XT") : les deux ;
Styles NOMMÉS (pas une timeframe) :
  - "TRADER" : le trader complet -- il VOIT toutes les timeframes (M5 -> MN1), ses niveaux, la structure, la
    macro (src/trader/vision.py, src/cross_asset.py) et choisit ordre marché/limite, stop et objectif. Il
    DÉCIDE toutes les 15 min (rythme M15) et garde une position de quelques minutes à plusieurs jours."""
import re

_VARIANT = re.compile(r"^([MHDW]\d+)[TX]{1,2}$")
# Rythme de décision (bougie de base) des styles nommés.
NAMED_STYLES = {"TRADER": "M15"}


def base_timeframe(style: str) -> str:
    if style in NAMED_STYLES:
        return NAMED_STYLES[style]
    m = _VARIANT.match(style or "")
    return m.group(1) if m else style
