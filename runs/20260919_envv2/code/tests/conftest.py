"""
conftest.py
============
Config/fixtures partagées pytest pour tests/ -- pour l'instant, sert
uniquement à factoriser `DummyMonkeypatch` (voir ci-dessous), auparavant
dupliquée dans tests/test_autonomous.py, tests/test_fred_feed.py et
tests/test_fundamental_feed.py.
"""
from __future__ import annotations
import os


class DummyMonkeypatch:
    """Substitut MINIMAL de la fixture pytest `monkeypatch`, utilisé
    UNIQUEMENT dans le fallback `if __name__ == "__main__":` de certains
    fichiers de tests (lancement direct `python tests/test_X.py`, sans
    pytest -- voir le README, section Tests, pour pourquoi ce mode de
    secours existe encore). Jamais utilisé par les tests normaux exécutés
    via `pytest tests/`, qui reçoivent la VRAIE fixture `monkeypatch`.

    Fusion des TROIS définitions auparavant dupliquées (test_autonomous.py,
    test_fred_feed.py, test_fundamental_feed.py) : les trois avaient
    `chdir`, mais SEULE test_fundamental_feed.py n'avait PAS `setattr` --
    vérifié avant fusion qu'aucun de ses deux appels (test_fundamental_feed_
    neutral_on_failure, test_fundamental_feed_parses_local_rss) n'utilise
    `.setattr()`, donc l'ajouter ici est un SURENSEMBLE sans risque (une
    méthode supplémentaire inutilisée ne change aucun comportement), plutôt
    qu'une divergence silencieusement aplanie."""

    def chdir(self, path):
        os.chdir(path)

    def setattr(self, obj, name, value):
        setattr(obj, name, value)


import pytest


@pytest.fixture(autouse=True)
def _statistiques_aurexis_isolees(tmp_path, monkeypatch):
    """09/10/2026 : les tests construisent de faux marchés -- leurs statistiques ne doivent JAMAIS atterrir dans le
    vrai dossier lu par l'examen du jour (data/aurexis_stats)."""
    import src.aurexis_data as ad
    monkeypatch.setattr(ad, "STATS_DIR", str(tmp_path / "aurexis_stats"))
