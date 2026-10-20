"""Le journal de croissance : chaque battement, naissance, fusion, coupe, changement de cime, porte franchie.
Une ligne par événement, écrite dès qu'il arrive ; c'est de là que viennent les images et le rapport final."""
from __future__ import annotations

import json
from pathlib import Path

from collapsar.arbre.jardinier import maintenant


class Journal:
    def __init__(self, fichier: Path):
        self.fichier = fichier
        fichier.parent.mkdir(parents=True, exist_ok=True)

    def ecrire(self, quoi: str, **details):
        ligne = {"heure": maintenant(), "quoi": quoi, **details}
        with open(self.fichier, "a", encoding="utf-8") as f:
            f.write(json.dumps(ligne, ensure_ascii=False) + "\n")

    def lire(self) -> list[dict]:
        if not self.fichier.exists():
            return []
        with open(self.fichier, encoding="utf-8") as f:
            return [json.loads(l) for l in f if l.strip()]
