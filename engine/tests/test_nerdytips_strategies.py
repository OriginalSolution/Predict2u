"""Unit tests for NerdyTips strategy mappers (no network)."""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "engine" / "vendor"))
sys.path.insert(0, str(ROOT / "engine" / "gates"))
import nerdytips_strategies as nt
import optional_gates as og


def _ev(markets, home="Alpha FC", away="Beta United", league="England - Premier League"):
    return {
        "eventId": "sr:match:1",
        "homeTeamName": home,
        "awayTeamName": away,
        "sport": {"category": {"tournament": {"name": league}}},
        "estimateStartTime": 2000000000000,
        "markets": markets,
    }


def test_team_win_lt_150():
    ev = _ev([
        {"id": "1", "specifier": "", "outcomes": [
            {"id": "1", "desc": "Home", "odds": "1.40"},
            {"id": "2", "desc": "Draw", "odds": "4.20"},
            {"id": "3", "desc": "Away", "odds": "7.50"},
        ]}
    ])
    p = nt.team_win_lt_150(ev)
    assert p and p["selection"] == "Home" and p["odds"] == 1.40


def test_team_win_rejects_150():
    ev = _ev([
        {"id": "1", "specifier": "", "outcomes": [
            {"id": "1", "desc": "Home", "odds": "1.50"},
            {"id": "2", "desc": "Draw", "odds": "3.80"},
            {"id": "3", "desc": "Away", "odds": "5.50"},
        ]}
    ])
    assert nt.team_win_lt_150(ev) is None


def test_draw_rules_over15():
    ev = _ev([
        {"id": "1", "specifier": "", "outcomes": [
            {"id": "1", "desc": "Home", "odds": "1.55"},
            {"id": "2", "desc": "Draw", "odds": "3.80"},
            {"id": "3", "desc": "Away", "odds": "5.50"},
        ]},
        {"id": "18", "specifier": "total=1.5", "desc": "Over/Under", "outcomes": [
            {"id": "12", "desc": "Over", "odds": "1.22"},
            {"id": "13", "desc": "Under", "odds": "3.80"},
        ]},
    ])
    p = nt.draw_rules(ev)
    assert p and p["selection"] == "Over 1.5"


def test_exclusive_o25():
    ev = _ev([
        {"id": "18", "specifier": "total=3.5", "outcomes": [
            {"id": "12", "desc": "Over", "odds": "2.10"},
            {"id": "13", "desc": "Under", "odds": "1.65"},
        ]},
        {"id": "19", "specifier": "total=1.5", "outcomes": [
            {"id": "12", "desc": "Over", "odds": "1.45"},
            {"id": "13", "desc": "Under", "odds": "2.50"},
        ]},
        {"id": "18", "specifier": "total=2.5", "outcomes": [
            {"id": "12", "desc": "Over", "odds": "1.72"},
            {"id": "13", "desc": "Under", "odds": "2.00"},
        ]},
    ])
    # two markets with id 18 — outcome() returns first matching mid+spec
    p = nt.exclusive_o25(ev)
    assert p and p["selection"] == "Over 2.5"


def test_streak_2plus_filter():
    ev = _ev([
        {"id": "60010", "specifier": "", "outcomes": [
            {"id": "4", "desc": "Yes", "odds": "1.30"},
            {"id": "5", "desc": "No", "odds": "3.20"},
        ]},
        {"id": "1", "specifier": "", "outcomes": [
            {"id": "1", "desc": "Home", "odds": "1.60"},
            {"id": "2", "desc": "Draw", "odds": "3.70"},
            {"id": "3", "desc": "Away", "odds": "5.00"},
        ]},
        {"id": "18", "specifier": "total=2.5", "outcomes": [
            {"id": "12", "desc": "Over", "odds": "1.70"},
        ]},
    ])
    p = nt.streak_2plus(ev)
    assert p is not None
    assert p["strategy"] == "streak_2plus"


def test_betmines_requires_both_sides():
    ev = _ev([
        {"id": "18", "specifier": "total=2.5", "outcomes": [{"id": "12", "desc": "Over", "odds": "1.70"}]},
    ])
    assert nt.betmines_trends(ev, {}) is None
    assert nt.betmines_trends(ev, {"sr:match:1": {
        "pick": "Over 2.5", "supportHome": True, "supportAway": False,
        "priceOk": True, "leagueAvgOk": True, "h2hOk": True, "formOk": True, "tableOk": True,
    }}) is None
    p = nt.betmines_trends(ev, {"sr:match:1": {
        "pick": "Over 2.5", "supportHome": True, "supportAway": True,
        "priceOk": True, "leagueAvgOk": True, "h2hOk": True, "formOk": True, "tableOk": True,
    }})
    assert p and p["selection"] == "Over 2.5"


def test_optional_gates_disabled_by_default():
    picks = [{"selection": "GG", "odds": 1.70, "riddimEdge": True}]
    assert og.apply_optional_gates(picks, {"optional_gates": {"enabled": False}}) == picks
    # master off even if child true
    assert og.apply_optional_gates(picks, {"optional_gates": {"enabled": False, "gg_benched": True}}) == picks
    out = og.apply_optional_gates(picks, {"optional_gates": {"enabled": True, "gg_benched": True}})
    assert out == []


def test_optional_gates_describe_all_off():
    rows = og.describe_gates({"optional_gates": {"enabled": False, "gg_benched": True}})
    assert all(r["enabled"] is False for r in rows)
