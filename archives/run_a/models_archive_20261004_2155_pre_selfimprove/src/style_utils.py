"""Un style de trading est normalement une timeframe ("H1"). Un suffixe "T" ("H1T")
désigne une lignée distincte entraînée sur les MÊMES données que sa timeframe de base
mais avec un take-profit appris (voir environment.style_overrides)."""
import re

_VARIANT = re.compile(r"^([MHDW]\d+)T$")


def base_timeframe(style: str) -> str:
    m = _VARIANT.match(style or "")
    return m.group(1) if m else style
