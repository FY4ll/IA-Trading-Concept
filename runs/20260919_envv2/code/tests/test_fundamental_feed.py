"""
test_fundamental_feed.py
=========================
Vérifie que l'auto-alimentation fondamentale (sentiment RSS FinBERT) ne
plante jamais, même sans accès réseau : les échecs de source doivent se
résoudre en scores neutres, jamais en exception.

Usage : python -m pytest tests/test_fundamental_feed.py -v
"""
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.fundamental_feed import AutoFundamentalFeed


def test_fundamental_feed_neutral_on_failure(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    cfg = {"fundamental": {"enabled": True,
                            "rss_feeds": ["http://invalid.local.test/rss"]}}
    ff = AutoFundamentalFeed(cfg)
    news = ff.refresh_news_sentiment()
    assert news == {}


def test_fundamental_feed_parses_local_rss(tmp_path, monkeypatch):
    # Isolation : AutoFundamentalFeed écrit/lit son cache dans "data/cache/"
    # (chemin relatif au cwd) -- sans chdir vers un répertoire vide dédié à
    # CE test, il lit/pollue le cache réel du projet (ou celui d'un autre
    # test), ce qui casse l'assertion len(news) == 1 dès que ce cache n'est
    # pas vide (ex: agent de production qui tourne en parallèle).
    monkeypatch.chdir(tmp_path)
    fake_rss = """<?xml version="1.0"?>
    <rss version="2.0"><channel><title>Test</title>
    <item><title>Strong jobs report boosts investor confidence</title>
    <pubDate>Mon, 01 Sep 2025 15:00:00 GMT</pubDate></item>
    </channel></rss>"""
    cfg = {"fundamental": {"enabled": True, "rss_feeds": [fake_rss]}}
    ff = AutoFundamentalFeed(cfg)
    news = ff.refresh_news_sentiment()
    assert len(news) == 1
    assert list(news.values())[0] > 0  # titre positif -> score positif


def _fake_history(values):
    import pandas as pd
    idx = pd.date_range("2024-01-01", periods=len(values), freq="D")
    return pd.Series(values, index=idx, dtype=float)


def test_macro_only_varies_over_time_without_news(tmp_path, monkeypatch):
    import numpy as np
    import pandas as pd
    import src.fred_feed as fred_feed
    monkeypatch.chdir(tmp_path)
    rng = np.random.default_rng(0)
    hist = {sid: _fake_history(np.cumsum(rng.normal(size=300))) for sid in fred_feed._SIGNAL_WEIGHTS}
    monkeypatch.setattr(fred_feed, "_fetch_history", lambda feed, sid: hist[sid])
    monkeypatch.setattr(fred_feed, "HIST_START", "2024-01-01")
    cfg = {"fundamental": {"enabled": True, "macro_only": True}, "fred": {"api_key": "x"}}
    ff = AutoFundamentalFeed(cfg)
    monkeypatch.setattr(ff, "refresh_news_sentiment",
                        lambda: (_ for _ in ()).throw(AssertionError("news must not be fetched in macro_only")))
    df = pd.DataFrame({"time": pd.date_range("2024-06-01", periods=48, freq="h")})
    out = ff.align_to_bars(df, refresh=True)
    assert len(out) == 48
    assert out.between(-1.0, 1.0).all()
    daily = fred_feed.macro_score_series(ff._fred)
    assert daily.dropna().std() > 0.05  # le score doit varier (pas constant comme avant le reset)


def test_macro_score_is_point_in_time(tmp_path, monkeypatch):
    import numpy as np
    import pandas as pd
    import src.fred_feed as fred_feed
    monkeypatch.chdir(tmp_path)
    rng = np.random.default_rng(1)
    base = {sid: np.cumsum(rng.normal(size=120)) for sid in fred_feed._SIGNAL_WEIGHTS}
    monkeypatch.setattr(fred_feed, "HIST_START", "2024-01-01")
    cfg = {"fred": {"api_key": "x"}}
    feed = fred_feed.FredFeed(cfg)
    monkeypatch.setattr(fred_feed, "_fetch_history", lambda f, sid: _fake_history(base[sid]))
    before = fred_feed.macro_score_series(feed)
    altered = {sid: v.copy() for sid, v in base.items()}
    for v in altered.values():
        v[100:] += 50.0  # choc APRÈS le jour 100 : ne doit pas changer les scores antérieurs
    monkeypatch.setattr(fred_feed, "_fetch_history", lambda f, sid: _fake_history(altered[sid]))
    after = fred_feed.macro_score_series(feed)
    cutoff = pd.Timestamp("2024-01-01") + pd.Timedelta(days=100)
    pd.testing.assert_series_equal(before[before.index <= cutoff].dropna(), after[after.index <= cutoff].dropna())


if __name__ == "__main__":
    import tempfile, pathlib
    from conftest import DummyMonkeypatch  # voir tests/conftest.py -- fusion des 3 définitions dupliquées
    test_fundamental_feed_neutral_on_failure(pathlib.Path(tempfile.mkdtemp()), DummyMonkeypatch())
    test_fundamental_feed_parses_local_rss(pathlib.Path(tempfile.mkdtemp()), DummyMonkeypatch())
    print("SMOKE TEST fundamental_feed: SUCCESS")
