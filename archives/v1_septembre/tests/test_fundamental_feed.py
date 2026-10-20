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


if __name__ == "__main__":
    import tempfile, pathlib
    from conftest import DummyMonkeypatch  # voir tests/conftest.py -- fusion des 3 définitions dupliquées
    test_fundamental_feed_neutral_on_failure(pathlib.Path(tempfile.mkdtemp()), DummyMonkeypatch())
    test_fundamental_feed_parses_local_rss(pathlib.Path(tempfile.mkdtemp()), DummyMonkeypatch())
    print("SMOKE TEST fundamental_feed: SUCCESS")
