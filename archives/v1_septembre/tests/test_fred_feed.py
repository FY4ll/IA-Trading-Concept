"""
test_fred_feed.py
===================
Vérifie l'intégration FRED (src/fred_feed.py) : repli neutre sans clé API,
calcul du fred_score avec données mockées, et respect du TTL du cache
(pas de re-fetch avant expiration).

Usage : python -m pytest tests/test_fred_feed.py -v
"""
import sys, os, json, time
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.fred_feed import FredFeed, _cache_path, _zscore_last


def test_fred_score_neutral_without_api_key(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    ff = FredFeed({"fred": {"api_key": ""}})
    assert ff.compute_fred_score() == 0.0


def test_fred_score_with_mocked_observations(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    ff = FredFeed({"fred": {"api_key": "fake-key"}})

    # DFII10 en baisse (bullish or) -> dernière valeur bien en dessous de la
    # moyenne récente. Les autres séries restent plates (z-score None,
    # ignorées de la moyenne pondérée).
    def fake_fetch_series(series_id):
        if series_id == "DFII10":
            return [{"date": f"2025-01-{i:02d}", "value": str(v)}
                     for i, v in enumerate([2.0] * 10 + [0.5], start=1)]
        return [{"date": "2025-01-01", "value": "1.0"}]

    monkeypatch.setattr(ff, "fetch_series", fake_fetch_series)
    score = ff.compute_fred_score()
    # DFII10 bas -> bullish -> score positif
    assert score > 0.0
    assert -1.0 <= score <= 1.0


def test_zscore_last_needs_two_values():
    assert _zscore_last([]) is None
    assert _zscore_last([{"date": "2025-01-01", "value": "1.0"}]) is None
    assert _zscore_last([{"date": "2025-01-01", "value": "."},
                          {"date": "2025-01-02", "value": "2.0"}]) is None


def test_zscore_last_constant_series_is_none():
    obs = [{"date": "2025-01-01", "value": "1.0"}] * 5
    assert _zscore_last(obs) is None


def test_cache_ttl_prevents_refetch(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    ff = FredFeed({"fred": {"api_key": "fake-key"}})

    os.makedirs("data/cache", exist_ok=True)
    cache_path = _cache_path("DFII10")
    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump({"_fetched_at": time.time(), "observations": [{"date": "2025-01-01", "value": "1.5"}]}, f)

    calls = []

    def fake_get(*args, **kwargs):
        calls.append(1)
        raise AssertionError("ne doit pas re-fetcher : cache encore valide (TTL 1h)")

    import requests
    monkeypatch.setattr(requests, "get", fake_get)

    observations = ff.fetch_series("DFII10")
    assert observations == [{"date": "2025-01-01", "value": "1.5"}]
    assert calls == []


def test_cache_expired_triggers_refetch(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    ff = FredFeed({"fred": {"api_key": "fake-key"}})

    os.makedirs("data/cache", exist_ok=True)
    cache_path = _cache_path("DFII10")
    stale_time = time.time() - 7200  # 2h dans le passé, TTL = 1h
    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump({"_fetched_at": stale_time, "observations": [{"date": "2025-01-01", "value": "1.5"}]}, f)

    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {"observations": [{"date": "2025-02-01", "value": "1.9"}]}

    calls = []

    def fake_get(*args, **kwargs):
        calls.append(1)
        return FakeResponse()

    import requests
    monkeypatch.setattr(requests, "get", fake_get)

    observations = ff.fetch_series("DFII10")
    assert observations == [{"date": "2025-02-01", "value": "1.9"}]
    assert calls == [1]


if __name__ == "__main__":
    import tempfile, pathlib
    from conftest import DummyMonkeypatch  # voir tests/conftest.py -- fusion des 3 définitions dupliquées

    mp = DummyMonkeypatch()
    test_fred_score_neutral_without_api_key(pathlib.Path(tempfile.mkdtemp()), mp)
    test_fred_score_with_mocked_observations(pathlib.Path(tempfile.mkdtemp()), mp)
    test_zscore_last_needs_two_values()
    test_zscore_last_constant_series_is_none()
    test_cache_ttl_prevents_refetch(pathlib.Path(tempfile.mkdtemp()), mp)
    test_cache_expired_triggers_refetch(pathlib.Path(tempfile.mkdtemp()), mp)
    print("SMOKE TEST fred_feed: SUCCESS")
