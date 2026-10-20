"""Le SOCLE du cerveau modulaire (20/10/2026) : ce que tout module partage, et le registre qui permet d'en AJOUTER.

Un module = une classe qui hérite de `Module`, a un nom unique et une couche, et s'inscrit avec `enregistrer(...)`.
Ajouter un module ne touche à aucun autre : le registre le rend visible à la couche suivante (l'arbitre lira
`modules("perception")`). Chaque module a son propre journal (`journal()`), pour savoir QUI s'est trompé.

Couches (zones du cerveau) : perception (cortex), contexte (hippocampe), decision (arbitre), veto (amygdale),
apprentissage (dopamine), execution (cervelet), vigilance (locus coeruleus).
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

COUCHES = ("perception", "contexte", "decision", "veto", "apprentissage", "execution", "vigilance")
RACINE = Path(__file__).resolve().parents[1]
JOURNAUX = RACINE / "cerveau" / "journaux"

# Colonnes d'un avis de perception (une ligne = un avis) :
COLONNES_AVIS = ("module", "temps", "expire", "sens", "confiance", "zone_haut", "zone_bas", "entree", "stop",
                 "objectif", "atr")


@dataclass(frozen=True)
class Avis:
    """Ce qu'un module de perception dit à un instant : « à partir de `temps`, j'achète (sens +1) ou je vends (-1)
    à `entree`, invalidé à `stop`, destination `objectif` », avec sa confiance (0-1) et la zone qui le fonde."""
    module: str
    temps: pd.Timestamp
    expire: pd.Timestamp
    sens: int
    confiance: float
    zone_haut: float
    zone_bas: float
    entree: float
    stop: float
    objectif: float
    atr: float
    details: dict = field(default_factory=dict)


class Module(ABC):
    nom: str = ""
    couche: str = ""

    def journal(self, dossier: Path | None = None) -> logging.Logger:
        """Journal propre au module (fichier `<dossier>/<nom>.log`)."""
        log = logging.getLogger(f"cerveau.{self.nom}")
        if not log.handlers:
            d = Path(dossier) if dossier else JOURNAUX
            d.mkdir(parents=True, exist_ok=True)
            h = logging.FileHandler(d / f"{self.nom}.log", encoding="utf-8")
            h.setFormatter(logging.Formatter("%(asctime)s %(message)s", "%d/%m %H:%M:%S"))
            log.addHandler(h)
            log.setLevel(logging.INFO)
        return log


class ModulePerception(Module):
    couche = "perception"

    @abstractmethod
    def avis(self, bougies15: pd.DataFrame) -> pd.DataFrame:
        """Tous les avis du module sur l'historique donné (bougies de 15 min : time, open, high, low, close, volume),
        sans futur : chaque avis n'utilise que ce qui est connu à son `temps`. Colonnes : COLONNES_AVIS (+ détails)."""


_REGISTRE: dict[str, Module] = {}


def enregistrer(module: Module) -> Module:
    if module.couche not in COUCHES:
        raise ValueError(f"couche inconnue : {module.couche}")
    if not module.nom:
        raise ValueError("un module doit avoir un nom")
    if module.nom in _REGISTRE and _REGISTRE[module.nom] is not module:
        raise ValueError(f"nom déjà pris : {module.nom}")
    _REGISTRE[module.nom] = module
    return module


def modules(couche: str | None = None) -> list[Module]:
    return [m for m in _REGISTRE.values() if couche is None or m.couche == couche]


def module(nom: str) -> Module:
    return _REGISTRE[nom]
