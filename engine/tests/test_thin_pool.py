"""Thin-pool fallback runs only when the qualified pool is too small, and never breaks hard rules."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "engine" / "vendor"))

from engine.vendor import thin_pool as tp


def gg(**kw):
    base = dict(
        match="Alpha v Beta", league="England - Premier League", market="Both teams to score",
        selection="Yes", odds=1.22, eventId="sr:match:gg", marketId="29", specifier="",
        outcomeId="74", table="6 v 12/20", x12="1.75/3.50/5.00",
        case="table 6 v 12/20; 1X2 1.75/3.50/5.00", date="2099-06-01",
    )
    base.update(kw)
    return base


def over15(**kw):
    """Fails the normal extreme-stats bar (Over 1.5 above 1.30) but is a legal goals leg."""
    base = dict(
        match="Gamma v Delta", league="England - Premier League", market="Over/Under",
        selection="Over 1.5", odds=1.45, eventId="sr:match:o15", marketId="18",
        specifier="total=1.5", outcomeId="12", table="8 v 14/20", x12="1.70/3.60/5.20",
        case="table 8 v 14/20; 1X2 1.70/3.60/5.20", date="2099-06-01",
    )
    base.update(kw)
    return base


def test_fallback_does_not_run_when_pool_is_large(capsys):
    pool = [gg(eventId=f"sr:match:{i}", match=f"Home{i} v Away{i}") for i in range(6)]
    pool.append(over15())
    chosen, info = tp.select(pool)
    assert info["used"] is False
    assert info["qualified"] >= 6
    assert all(p["eventId"] != "sr:match:o15" for p in chosen)
    assert "thin-pool fallback used" not in capsys.readouterr().out


def test_fallback_adds_goals_legs_only_when_thin(capsys):
    pool = [
        gg(eventId="sr:match:1"),
        over15(),
        over15(eventId="sr:match:o15b", match="Echo v Foxtrot", league="Armenia - Premier League"),
    ]
    chosen, info = tp.select(pool)
    ids = {p["eventId"] for p in chosen}
    assert info["used"] is True
    assert info["qualified"] == 1
    assert "sr:match:o15" in ids
    assert "sr:match:o15b" in ids  # obscure league, goals market still allowed
    assert "thin-pool fallback used" in capsys.readouterr().out
    assert all(p.get("thinPoolFallback") for p in chosen if p["eventId"] != "sr:match:1")


def test_fallback_rejects_hard_rules(capsys):
    pool = [
        gg(eventId="sr:match:1"),
        dict(match="A v B", league="England - Premier League", market="Both teams to score",
             selection="No", odds=1.20, eventId="sr:ng", marketId="29", specifier="",
             outcomeId="76", date="2099-06-01"),
        dict(match="A v B", league="England - Premier League", market="Double chance",
             selection="Home or Away", odds=1.10, eventId="sr:dc12", marketId="10",
             specifier="", outcomeId="10", date="2099-06-01"),
        dict(match="A v B", league="England - Premier League", market="Double chance",
             selection="Home or Draw", odds=1.50, eventId="sr:dc1x", marketId="10",
             specifier="", outcomeId="9", date="2099-06-01"),
        dict(match="A v B", league="Armenia - Premier League", market="1X2",
             selection="Home", odds=1.25, eventId="sr:obscure", marketId="1",
             specifier="", outcomeId="1", table="8 v 12/20", x12="1.40/4.00/8.00",
             case="table 8 v 12/20; 1X2 1.40/4.00/8.00", date="2099-06-01"),
        dict(match="A v B", league="England - Premier League", market="Double chance",
             selection="Home or Draw", odds=1.30, eventId="sr:dcshort", marketId="10",
             specifier="", outcomeId="9", table="6 v 12/20", x12="1.75/3.50/5.00",
             case="table 6 v 12/20; 1X2 1.75/3.50/5.00", date="2099-06-01"),
    ]
    chosen, info = tp.select(pool)
    ids = {p["eventId"] for p in chosen}
    assert info["used"] is True
    assert "sr:ng" not in ids
    assert "sr:dc12" not in ids
    assert "sr:dc1x" not in ids
    assert "sr:obscure" not in ids
    assert "sr:dcshort" in ids  # 1X at 1.30 is allowed by the hard rule
    assert "thin-pool fallback used" in capsys.readouterr().out
