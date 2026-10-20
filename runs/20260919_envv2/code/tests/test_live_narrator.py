"""Le narrateur (08/10/2026) : l'IA prévient, se justifie, et ne se tait jamais longtemps."""
from datetime import datetime

import pytest

from src.live_narrator import Narrator

CFG = {"live": {"narrator": {"enabled": True, "bulletin_hours": [8, 14, 20], "blocked_every_hours": 4,
                             "timezone": "Europe/Paris"}}}
NOTE = ("ACHAT au marché -- biais H4 haussier, plus bas d'hier à 0.8 ATR sous le prix, "
        "prochaine news majeure dans 5 h, volatilité haute.")


class Conn:
    def get_open_positions_by_style(self, styles):
        return {"AUREX": {"direction": 1, "price_open": 4128.0, "sl": 4100.0, "tp": 4184.0, "profit": 0.0}}

    def get_account_equity(self):
        return 100_000.0


@pytest.fixture
def nar(tmp_path, monkeypatch):
    n = Narrator(CFG, Conn(), state_path=str(tmp_path / "n.json"))
    sent = []
    monkeypatch.setattr(n, "_send", lambda s, m: sent.append((s, m)))
    return n, sent


def _row(action, raw=1.0, final=1.0, block=None, wait=None):
    return {"style": "AUREX", "action": action, "raw_target": raw, "final_target": final, "block_reasons": block or [],
            "wait_reason": wait, "p_long": 0.52, "p_flat": 0.18, "p_short": 0.30, "note": NOTE, "price": 4127.5,
            "risk_pct": 0.0025, "take_profit_rr": 2.0, "next_event": "2026-10-09T12:30:00Z USD Non-Farm Payrolls"}


def test_opening_is_announced_with_its_justification_in_plain_words(nar):
    n, sent = nar
    n.on_decision(_row("OPEN_LONG"), None)
    subject, msg = sent[0]
    assert "ouvre un ACHAT" in subject and "4128.00" in msg and "stop 4100.00" in msg and "objectif 4184.00" in msg
    assert "risque ≈ 250 $" in msg and "gain visé ≈ 500 $" in msg
    assert "acheter 52%" in msg and "tendance sur 4 heures à la hausse" in msg and "H4" not in msg
    assert "fois le mouvement habituel" in msg and "ATR" not in msg
    assert "Non-Farm Payrolls" in msg and "09/10 à 14h30" in msg, "heure de Paris"


def test_closing_by_the_ai_gives_the_result(nar):
    n, sent = nar
    n.on_decision(_row("CLOSE", raw=0.0, final=0.0, wait="model_exit"), {"direction": 1, "profit": 410.0})
    assert "ferme sa position" in sent[0][0] and "+410 $" in sent[0][1] and "elle n'y croit plus" in sent[0][1]


def test_blocked_intention_is_told_but_not_every_15_minutes(nar):
    n, sent = nar
    row = _row("WAIT", raw=1.0, final=0.0, block=["trend_discipline:D1_trend_signal"])
    n.on_decision(row, None, now=1000.0)
    n.on_decision(row, None, now=1000.0 + 3600)
    assert len(sent) == 1 and "voudrait acheter" in sent[0][0]
    assert "tendance de fond (journalière) va dans l'autre sens" in sent[0][1]
    n.on_decision(row, None, now=1000.0 + 4 * 3600)
    assert len(sent) == 2, "de nouveau après 4 heures"
    n.on_decision(_row("WAIT", raw=0.0, final=0.0, wait="model_flat"), None, now=1e9)
    assert len(sent) == 2, "pas d'intention -> pas de message"


def test_bulletins_three_times_a_day_never_twice_never_on_weekends(nar):
    n, sent = nar
    n.on_decision(_row("WAIT", raw=1.0, final=0.0, block=["trend_discipline:x"]), None, now=0.0)
    sent.clear()
    from zoneinfo import ZoneInfo
    tz = ZoneInfo("Europe/Paris")
    n.maybe_bulletin(["AUREX"], now=datetime(2026, 10, 8, 13, 59, tzinfo=tz))
    assert sent == []
    n.maybe_bulletin(["AUREX"], now=datetime(2026, 10, 8, 14, 0, tzinfo=tz))
    n.maybe_bulletin(["AUREX"], now=datetime(2026, 10, 8, 14, 30, tzinfo=tz))
    assert len(sent) == 1 and "point de 14h" in sent[0][0]
    assert "pas de position" in sent[0][1] and "acheter 52%" in sent[0][1] and "Compte : 100 000 $" in sent[0][1]
    n.maybe_bulletin(["AUREX"], now=datetime(2026, 10, 10, 14, 0, tzinfo=tz))   # samedi
    assert len(sent) == 1


def test_disabled_narrator_says_nothing(tmp_path, monkeypatch):
    n = Narrator({"live": {"narrator": {"enabled": False}}}, Conn(), state_path=str(tmp_path / "n.json"))
    sent = []
    monkeypatch.setattr(n, "_send", lambda s, m: sent.append((s, m)))
    n.on_decision(_row("OPEN_LONG"), None)
    n.maybe_bulletin(["AUREX"])
    assert sent == []
