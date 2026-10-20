"""Lecture du fichier de réglages de l'école de la précision.

Par défaut : reglages.yaml (à côté) = l'arbre HYPERNOVA. Un AUTRE arbre de la même école (même simulateur, même
mécanique) a son propre fichier, choisi AVANT tout import par la variable d'environnement
COLLAPSAR_PRECISION_REGLAGES (chemin du fichier) ; c'est ce que fait son lanceur (ex. arbre_or.py -> reglages_or.yaml).
Le nom de l'arbre (`nom:`) et son dossier de vie (`vie:`) sont lus en tête de ce fichier ; sans eux : HYPERNOVA.
Les yeux calculés (CACHE) sont PARTAGÉS par tous les arbres (mêmes définitions, mêmes données) : seulement lus si déjà faits.
"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import yaml

from collapsar.donnees.marches import RACINE

DEFAUT = Path(__file__).with_name("reglages.yaml")
VARIABLE = "COLLAPSAR_PRECISION_REGLAGES"


def _chemin(x: str | Path) -> Path:
    p = Path(x)
    if p.is_absolute():
        return p
    return (Path(__file__).parent / p) if (Path(__file__).parent / p).exists() else RACINE / p


FICHIER = _chemin(os.environ[VARIABLE]) if os.environ.get(VARIABLE) else DEFAUT
_TETE = yaml.safe_load(FICHIER.read_text(encoding="utf-8")) or {}
NOM = str(_TETE.get("nom", "HYPERNOVA"))   # nom de l'arbre (HYPERNOVA : chef de projet, 16/10/2026)
VIE = RACINE / _TETE["vie"] if _TETE.get("vie") else RACINE / "collapsar" / "vie" / "hypernova"
CACHE = RACINE / "collapsar" / "vie" / "hypernova" / "cache"      # yeux partagés par tous les arbres de l'école
UNITES = ("D1", "H4", "H1", "M30", "M15", "M5", "M3")
FREQ = {"D1": "1D", "H4": "4h", "H1": "1h", "M30": "30min", "M15": "15min", "M5": "5min", "M3": "3min"}
UNITES_15 = UNITES[:5]                 # marchés en 15 min
UNITES_BRUTES = ("D1", "H4", "H1", "M15")
CAPITAL = 100_000.0


def _ns(x):
    return SimpleNamespace(**{k: _ns(v) if isinstance(v, dict) and k != "minutes" else v for k, v in x.items()})


def lire(fichier: Path) -> SimpleNamespace:
    """Un fichier de réglages, vérifié (périodes dans l'ordre, rien après les 12 mois cachés)."""
    d = yaml.safe_load(Path(fichier).read_text(encoding="utf-8"))
    d = {k: v for k, v in d.items() if k not in ("nom", "vie")}
    r = _ns(d)
    p = r.periodes
    for k in vars(p):
        setattr(p, k, pd.Timestamp(getattr(p, k)))
    if getattr(r, "examen_tournant", None) is None:
        assert p.apprentissage_fin <= p.selection_de < p.selection_jusqua <= p.rapport_de < p.rapport_jusqua <= p.fin_donnees
    else:
        # EXAMEN TOURNANT (tournant.py, arbre de l'or) : la sélection (réservoir de blocs) est DANS les années
        # d'apprentissage, blocs exclus des mondes d'apprentissage ; le rapport reste après les deux, jamais appris
        assert p.selection_de < p.selection_jusqua <= p.rapport_de < p.rapport_jusqua <= p.fin_donnees
        assert p.apprentissage_fin <= p.rapport_de
    assert p.fin_donnees <= pd.Timestamp("2025-10-01"), "les 12 mois cachés ne doivent jamais être chargés"
    return r


@lru_cache(maxsize=1)
def R() -> SimpleNamespace:
    return lire(FICHIER)


def _periode(de: pd.Timestamp, jusqua: pd.Timestamp) -> str:
    fin = jusqua - pd.Timedelta(days=1)
    if de.month == 1 and de.day == 1 and fin.month == 12 and fin.day == 31:
        return f"{de:%Y}" if de.year == fin.year else f"{de:%Y}-{fin:%Y}"
    return f"{de:%m/%Y} -> {fin:%m/%Y}"


def etiquette_selection() -> str:
    """« 2023 », « 2022-2023 » ou « 01/2023 -> 06/2024 » : la période de l'examen de sélection, pour les textes."""
    p = R().periodes
    return _periode(p.selection_de, p.selection_jusqua)


def etiquette_rapport() -> str:
    p = R().periodes
    return _periode(p.rapport_de, p.rapport_jusqua)
