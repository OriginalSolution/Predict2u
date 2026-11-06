"""Obscure-league goals-only veto (user 2026-11-06)."""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from engine.rules import (
    check, is_goals_market, is_major_league, is_obscure_league_non_goals, is_btts_no,
)


def pick(**kw):
    base = dict(
        match="Alpha v Beta", league="Armenia - Premier League", market="1X2",
        selection="Home", odds=1.25, eventId="sr:match:obscure1", marketId="1",
        specifier="", outcomeId="1", table="8 v 12/20", x12="1.40/4.00/8.00",
        case="table 8 v 12/20; 1X2 1.40/4.00/8.00",
    )
    base.update(kw)
    return base


def test_major_league_patterns():
    assert is_major_league("England - Premier League")
    assert is_major_league("International Clubs - UEFA Champions League")
    assert is_major_league("Ghana - Premier League")
    assert is_major_league("Brazil - Brasileiro Serie A")
    assert is_major_league("USA - Major League Soccer")
    assert not is_major_league("Armenia - Premier League")
    assert not is_major_league("Wales - Cymru Premier")
    assert not is_major_league("Israel - Liga Alef")


def test_goals_market_detects_totals_and_gg():
    assert is_goals_market(pick(marketId="18", specifier="total=1.5", outcomeId="12", selection="Over 1.5", market="Over/Under"))
    assert is_goals_market(pick(marketId="19", specifier="total=0.5", outcomeId="12", selection="Over 0.5", market="Home team total"))
    assert is_goals_market(pick(marketId="29", specifier="", outcomeId="74", selection="Yes", market="Both teams to score"))
    assert not is_goals_market(pick(marketId="1", selection="Home"))
    assert not is_goals_market(pick(marketId="10", selection="1X", market="Double chance"))
    ng = pick(marketId="29", outcomeId="76", selection="No", market="Both teams to score")
    assert is_btts_no(ng)
    assert not is_goals_market(ng)


def test_obscure_non_goals_vetoed():
    p = pick()
    assert is_obscure_league_non_goals(p)
    ok, cls, why = check(p)
    assert not ok and cls == "obscure-league-goals"
    assert "obscure" in why.lower()


def test_obscure_goals_not_blocked_by_this_rule():
    p = pick(marketId="18", specifier="total=1.5", outcomeId="12", selection="Over 1.5",
             market="Over/Under", odds=1.22)
    assert is_goals_market(p)
    assert not is_obscure_league_non_goals(p)


def test_major_league_1x2_not_obscure_veto():
    p = pick(league="England - Premier League", marketId="1", selection="Home")
    assert is_major_league(p)
    assert not is_obscure_league_non_goals(p)


def test_daily_master_exempt():
    p = pick(gateExempt=True)
    assert not is_obscure_league_non_goals(p)


def test_config_and_rules_document_veto():
    import json
    cfg = json.loads((ROOT / "engine" / "config.json").read_text())
    assert "obscure_league_non_goals" in cfg["hard_vetoes"]
    assert len(cfg["major_leagues"]["patterns"]) >= 20
    rules = (ROOT / "engine" / "RULES.md").read_text().lower()
    assert "obscure" in rules and "goals only" in rules
