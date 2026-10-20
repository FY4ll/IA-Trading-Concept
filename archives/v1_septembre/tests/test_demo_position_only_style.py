"""LOT 2 (suite), 21/09 : bug réel trouvé en démo réelle -- un style (H4)
détenant une position réelle ouverte repasse sous les seuils de validation
(un nouveau candidat moins bon a remplacé le champion validé) et se
retrouve totalement abandonné : `close_orphan_positions` ne le touche pas
(son tag reste reconnu), et la boucle de décision (filtrée sur
`_scan_eligible_styles`) ne le traite plus non plus. Sa position reste
ouverte, gérée par personne côté IA (le stop-loss posé au broker reste la
seule protection). Corrigé via `_position_only_entries` (src/demo_trader.py) :
un style hors de l'éligibilité mais avec une position réelle reste dans la
boucle de décision UNIQUEMENT pour gérer/fermer cette position, jamais pour
en ouvrir une nouvelle."""
from __future__ import annotations
import json
import os

from src.features import FEATURE_COLUMNS


def _write_meta(tf, gen, score, passes_validation):
    from src.continuous_trainer import _champion_meta, _champion_stats, _champion_dir
    from src.trading_env import ENV_VERSION
    os.makedirs(_champion_dir(tf), exist_ok=True)
    with open(_champion_meta(tf), "w", encoding="utf-8") as f:
        json.dump({"generation": gen, "score": score, "updated_at": 123.0 + gen,
                    "primary_timeframe": tf, "context_timeframes": [],
                    "feature_columns": FEATURE_COLUMNS, "passes_validation": passes_validation,
                    "env_version": ENV_VERSION, "metrics": {}}, f)
    with open(_champion_stats(tf), "w", encoding="utf-8") as f:
        json.dump({}, f)


def test_position_only_entries_includes_ineligible_style_with_open_position(tmp_path, monkeypatch):
    """Coeur de `_position_only_entries` : un style NON éligible mais avec
    une position réelle ouverte doit être renvoyé (marqué `position_only`) ;
    un style non éligible SANS position ne doit jamais apparaître (rien à
    gérer -- comportement d'origine, correctement abandonné)."""
    monkeypatch.chdir(tmp_path)
    from src.demo_trader import _position_only_entries

    _write_meta("H4", gen=10, score=1.0, passes_validation=False)  # a une position
    _write_meta("M15", gen=5, score=0.5, passes_validation=False)  # n'a AUCUNE position

    open_by_style = {"H4": {"ticket": 1, "direction": -1, "volume": 0.1, "price_open": 4300.0}}
    result = _position_only_entries({}, eligible_styles=set(), open_by_style=open_by_style)

    styles = {e["style"] for e in result}
    assert styles == {"H4"}, f"seul H4 (a une position) doit apparaître, obtenu {styles}"
    assert result[0]["position_only"] is True


def test_position_only_entries_excludes_already_eligible_style(tmp_path, monkeypatch):
    """Un style DÉJÀ éligible ne doit jamais être dupliqué dans
    `_position_only_entries`, même s'il a une position ouverte -- il est
    déjà couvert par `_scan_eligible_styles`."""
    monkeypatch.chdir(tmp_path)
    from src.demo_trader import _position_only_entries

    _write_meta("M30", gen=20, score=3.0, passes_validation=True)
    open_by_style = {"M30": {"ticket": 2, "direction": 1, "volume": 0.1, "price_open": 4300.0}}
    result = _position_only_entries({}, eligible_styles={"M30"}, open_by_style=open_by_style)
    assert result == []


def test_ineligible_style_with_open_position_can_still_close_it(tmp_path, monkeypatch):
    """Scénario RÉEL de l'incident : H4 a une position ouverte mais n'est
    plus éligible. Sa décision de FERMETURE (target=0) doit toujours partir
    -- avant le correctif, H4 n'était même plus dans la boucle, aucun ordre
    ne partait jamais, quelle que soit sa décision."""
    monkeypatch.chdir(tmp_path)
    import src.demo_trader as demo_trader_module
    from tests.test_autonomous import _CoordFakeConnector, _patch_style_runtime, _coord_cfg, _COORD_ENV_KWARGS

    _write_meta("H4", gen=10, score=1.0, passes_validation=False)
    _patch_style_runtime(monkeypatch, demo_trader_module, {"H4": (0.0, None)})  # veut fermer

    fake = _CoordFakeConnector(preexisting={"H4": -1})  # position SHORT existante
    demo_trader_module.run_demo_trading_loop(
        _coord_cfg(["H4"], "disabled"), _COORD_ENV_KWARGS, connector=fake, max_iterations=1)

    h4_calls = [c for c in fake.calls if c["style"] == "H4"]
    assert len(h4_calls) == 1, "H4 doit être traité (plus abandonné) malgré son inéligibilité"
    assert h4_calls[0]["target"] == 0.0


def _write_history_snapshot(tf, gen, score):
    """Crée un snapshot archivé models/champion_<tf>/history/gen_<gen>/
    complet (meta+stats+un vrai .zip bidon, seule l'EXISTENCE du fichier
    compte pour _resolve_entry_for_open_position, jamais son contenu)."""
    from src.continuous_trainer import _champion_dir
    from src.trading_env import ENV_VERSION
    snap_dir = os.path.join(_champion_dir(tf), "history", f"gen_{gen}")
    os.makedirs(snap_dir, exist_ok=True)
    with open(os.path.join(snap_dir, "meta.json"), "w", encoding="utf-8") as f:
        json.dump({"generation": gen, "score": score, "updated_at": 999.0 + gen,
                    "primary_timeframe": tf, "context_timeframes": [],
                    "feature_columns": FEATURE_COLUMNS, "passes_validation": True,
                    "env_version": ENV_VERSION, "metrics": {}}, f)
    with open(os.path.join(snap_dir, "norm_stats.json"), "w", encoding="utf-8") as f:
        json.dump({}, f)
    with open(os.path.join(snap_dir, "agent.zip"), "wb") as f:
        f.write(b"fake-zip-content")


def test_resolve_entry_returns_unchanged_when_no_open_position(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from src.demo_trader import _resolve_entry_for_open_position
    entry = {"style": "H4", "meta": {"generation": 204}, "model_path": "x", "stats_path": "y"}
    assert _resolve_entry_for_open_position(entry, None) is entry


def test_resolve_entry_returns_unchanged_when_same_generation(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from src.demo_trader import _resolve_entry_for_open_position
    entry = {"style": "H4", "meta": {"generation": 134}, "model_path": "x", "stats_path": "y"}
    pos = {"opened_by_generation": 134}
    assert _resolve_entry_for_open_position(entry, pos) is entry


def test_resolve_entry_falls_back_when_no_snapshot_archived(tmp_path, monkeypatch):
    """Cas réel de l'incident SANS le correctif d'archivage disponible
    (snapshot manquant, ex: généré avant l'ajout de _archive_snapshot) --
    doit retomber sur le champion courant sans jamais planter."""
    monkeypatch.chdir(tmp_path)
    from src.demo_trader import _resolve_entry_for_open_position
    entry = {"style": "H4", "meta": {"generation": 204}, "model_path": "current/model", "stats_path": "current/stats"}
    pos = {"opened_by_generation": 134}  # aucun snapshot gen_134 archivé
    result = _resolve_entry_for_open_position(entry, pos)
    assert result is entry, "sans snapshot disponible, repli sur le champion courant"


def test_resolve_entry_loads_exact_snapshot_when_available(tmp_path, monkeypatch):
    """Coeur du correctif : reproduit EXACTEMENT l'incident H4 -- position
    ouverte par la génération 134, champion actuel déjà à la génération
    204, snapshot archivé de la génération 134 disponible -> doit charger
    CE snapshot, pas le champion courant."""
    monkeypatch.chdir(tmp_path)
    from src.demo_trader import _resolve_entry_for_open_position
    _write_history_snapshot("H4", gen=134, score=0.762)

    entry = {"style": "H4", "meta": {"generation": 204, "score": 1.03}, "position_only": True,
             "model_path": "models/champion_H4/agent", "stats_path": "models/champion_H4/norm_stats.json"}
    pos = {"opened_by_generation": 134}
    result = _resolve_entry_for_open_position(entry, pos)

    assert result is not entry
    assert result["meta"]["generation"] == 134, "doit utiliser le meta DE LA GENERATION QUI A OUVERT, pas l'actuel"
    assert "history" in result["model_path"] and "gen_134" in result["model_path"]
    assert result["position_only"] is True, "le marqueur position_only doit être préservé"


def test_resolve_entry_falls_back_on_env_version_mismatch(tmp_path, monkeypatch):
    """Un snapshot archivé d'une VIEILLE version d'environnement (avant un
    changement d'espace d'observation/action, ENV_VERSION différent) ne
    doit jamais être chargé -- filet de sécurité déjà existant
    (env_version_matches), réutilisé ici."""
    monkeypatch.chdir(tmp_path)
    from src.demo_trader import _resolve_entry_for_open_position
    from src.continuous_trainer import _champion_dir
    import json as _json
    snap_dir = os.path.join(_champion_dir("H4"), "history", "gen_134")
    os.makedirs(snap_dir, exist_ok=True)
    with open(os.path.join(snap_dir, "meta.json"), "w", encoding="utf-8") as f:
        _json.dump({"generation": 134, "feature_columns": FEATURE_COLUMNS, "env_version": 1}, f)  # version obsolète
    with open(os.path.join(snap_dir, "norm_stats.json"), "w", encoding="utf-8") as f:
        _json.dump({}, f)
    with open(os.path.join(snap_dir, "agent.zip"), "wb") as f:
        f.write(b"fake")

    entry = {"style": "H4", "meta": {"generation": 204}, "model_path": "x", "stats_path": "y"}
    result = _resolve_entry_for_open_position(entry, {"opened_by_generation": 134})
    assert result is entry, "env_version incompatible -> repli sur le champion courant, jamais le vieux snapshot"


def test_ineligible_style_cannot_reopen_after_position_force_closed_same_cycle(tmp_path, monkeypatch):
    """GARDE-FOU anti-ouverture : H1 (non éligible) détient une position
    LONGUE ; H4 (éligible, bien meilleur score) veut ouvrir SHORT et gagne
    l'arbitrage de priorité -> ferme la position de H1 DANS CE MÊME CYCLE.
    Si H1 (toujours "position_only" ce cycle, puisqu'il avait une position
    au DÉBUT du cycle) essaie ensuite de rouvrir (son modèle veut toujours
    +1.0), cette réouverture doit être BLOQUÉE -- H1 n'est plus validé, il
    ne doit jamais prendre un NOUVEAU risque, seulement liquider l'ancien."""
    monkeypatch.chdir(tmp_path)
    import src.demo_trader as demo_trader_module
    from tests.test_autonomous import _CoordFakeConnector, _patch_style_runtime, _coord_cfg, _COORD_ENV_KWARGS

    _write_meta("H1", gen=10, score=3.0, passes_validation=False)
    _write_meta("H4", gen=20, score=8.0, passes_validation=True)
    # H1 veut ROUVRIR (+1.0) alors qu'il n'est plus valide ; H4 ouvre SHORT
    # et gagne (meilleur score) -> ferme H1 avant que H1 ne soit traité.
    _patch_style_runtime(monkeypatch, demo_trader_module, {"H1": (1.0, 0.02), "H4": (-1.0, 0.02)})

    fake = _CoordFakeConnector(preexisting={"H1": 1})  # H1 déjà LONG
    demo_trader_module.run_demo_trading_loop(
        _coord_cfg(["H1", "H4"], "priority_by_score"), _COORD_ENV_KWARGS,
        connector=fake, max_iterations=1)

    h1_calls = [c for c in fake.calls if c["style"] == "H1"]
    # 1er appel : fermeture forcée par H4 (coordination). 2e appel (le tour
    # de H1 dans la boucle) : sa tentative de réouverture doit être ramenée à 0.
    assert len(h1_calls) == 2, f"attendu 2 appels pour H1 (fermeture forcée + tentative bloquée), obtenu {len(h1_calls)}"
    assert h1_calls[0]["target"] == 0.0, "1er appel : fermeture forcée par la coordination"
    assert h1_calls[1]["target"] == 0.0, (
        "2e appel : la tentative de RÉOUVERTURE de H1 (style non éligible) doit être bloquée à 0, "
        "jamais laissée partir à +1.0"
    )
