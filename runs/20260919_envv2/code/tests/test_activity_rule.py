"""Activité minimale pour devenir champion (08/10/2026) : une IA qui ne trade presque pas ne peut pas être promue."""
import src.continuous_trainer as ct

CFG = {"continuous": {"min_activity_by_style": {"AUREXIS": {"min_trades": 100, "min_market_trades": 200}}}}


def _m(gold_trades, market_trades):
    return {"n_trades": gold_trades, "markets": [{"market": f"M{i}", "n_trades": t} for i, t in enumerate(market_trades)]}


def test_rule_only_for_configured_style():
    assert ct._activity_rule(CFG, "AUREXIS") == {"min_trades": 100, "min_market_trades": 200, "min_avg_market_trades": 0.0}
    assert ct._activity_rule(CFG, "AUREX") is None and ct._activity_rule({}, "AUREXIS") is None


def test_lazy_ai_is_not_active_enough():
    act = ct._activity_rule(CFG, "AUREXIS")
    assert not ct._active_enough(_m(28, [0, 1, 0, 2]), act), "le cas réel du 08/10 : 28 trades sur l'or"
    assert not ct._active_enough(_m(260, [5, 3, 2]), act), "actif sur l'or mais presque rien ailleurs"
    assert ct._active_enough(_m(260, [80, 70, 60]), act)
    assert ct._active_enough({"n_trades": 150}, act), "sans examen des autres marchés : seul l'or compte"


def test_activity_counted_on_all_markets():
    """09/10 : le meilleur candidat du cycle 400 (+4,35 %/mois) écarté pour 65 trades sur l'or alors qu'il trade ~50
    marchés. Règle multi-marchés : 10 trades par marché en moyenne ; l'or n'est qu'un marché parmi les autres."""
    act = ct._activity_rule({"continuous": {"min_activity_by_style": {"AUREXIS": {
        "min_trades": 0, "min_market_trades": 0, "min_avg_market_trades": 10}}}}, "AUREXIS")
    assert ct._active_enough(_m(65, [30] * 50), act), "le cas du cycle 400 : actif partout, prudent sur l'or"
    assert not ct._active_enough(_m(300, [2] * 50), act), "actif sur l'or seulement : toujours écarté"
    assert not ct._active_enough(_m(0, [0] * 50), act), "une IA qui ne fait rien : toujours écartée"


def test_confidence_counts_all_markets():
    assert ct._trade_count(_m(65, [30] * 50)) == 65 + 1500
    assert ct._trade_count({"n_trades": 120}) == 120


def test_excluded_winner_is_kept(tmp_path, monkeypatch):
    monkeypatch.setattr(ct, "MODELS_ROOT", str(tmp_path))
    src = tmp_path / "cand"
    (tmp_path / "cand.zip").write_bytes(b"cerveau")
    ct._keep_excluded("AUREXIS", 400, {"model_path": str(src), "score": 6.48, "metrics": _m(65, [30] * 3)})
    kept = list((tmp_path / "ecartes_AUREXIS").glob("gen400_*"))
    assert sorted(p.suffix for p in kept) == [".json", ".zip"]

def test_mean_period_note_for_promotion():
    """Incident du cycle 402 : il faut aussi ne pas être moins bon que le champion EN MOYENNE sur les périodes."""
    cand = {"portefeuille": {"periodes": [{"note": -15.87}, {"note": -19.00}]}}
    champ = {"portefeuille": {"periodes": [{"note": -8.34}, {"note": -19.13}]}}
    assert ct._mean_period_note(cand) < ct._mean_period_note(champ)
    assert ct._mean_period_note({"portefeuille": {"periodes": [{"note": 1.0}]}}) is None
    assert ct._mean_period_note({}) is None


def test_cycle_notification_is_plain_and_complete():
    champ = {"portefeuille": {"periodes": [{"mensuel": 0.0238, "reussite": 0.85, "note": 5.7},
                                           {"mensuel": 0.0112, "reussite": 0.40, "note": 2.0}]}}
    cands = [{"style": "AUREXIS", "score": 3.0, "metrics": {"portefeuille": {"periodes": [
                 {"mensuel": 0.03, "reussite": 0.9, "note": 3}, {"mensuel": 0.015, "reussite": 0.5, "note": 3.1}]}}},
             {"style": "AUREXIS", "score": -1e6, "inactif": True, "metrics": {}}]
    msg = ct._cycle_message("AUREXIS", 407, champ, cands, promoted=True)
    assert msg.startswith("Cycle 407 : Champion : +2.4 % / +1.1 % par mois (challenge réussi 85 % / 40 %)")
    assert "Meilleur candidat : +3.0 % / +1.5 % (réussi 90 % / 50 %)" in msg
    assert "1 écarté(s) pour manque d'activité" in msg and msg.endswith("NOUVEAU CHAMPION")
