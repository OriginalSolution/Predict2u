import math
import sys
from pathlib import Path

VENDOR = Path(__file__).resolve().parents[1] / "vendor"
sys.path.insert(0, str(VENDOR))
import sb_morning_markets as M


def test_odds_band_inclusive():
    assert M.in_odds_band(1.20)
    assert M.in_odds_band(1.60)
    assert M.in_odds_band("1.45")
    assert not M.in_odds_band(1.19)
    assert not M.in_odds_band(1.61)
    assert not M.in_odds_band(1.05)
    assert not M.in_odds_band(None)


def test_skips_youth_and_women():
    e = {"homeTeamName": "Hacken Gothenburg W", "awayTeamName": "Chelsea FC W",
         "sport": {"category": {"name": "International Clubs", "tournament": {"name": "UEFA Champions League Women"}}},
         "matchStatus": "Not start"}
    assert M.is_skipped_fixture(e)


def test_skips_reserves():
    e = {"homeTeamName": "CA Tigre Reserve", "awayTeamName": "Velez Sarsfield Reserve",
         "sport": {"category": {"name": "Argentina", "tournament": {"name": "Primera LPF, Reserves"}}},
         "matchStatus": "Not start"}
    assert M.is_skipped_fixture(e)


def test_keeps_senior_league():
    e = {"homeTeamName": "JS Djidjel", "awayTeamName": "CR Beni Thour",
         "sport": {"category": {"name": "Algeria", "tournament": {"name": "Ligue 2"}}},
         "matchStatus": "Not start"}
    assert M.is_skipped_fixture(e) is None


def test_vetoes_btts_no_and_dc12():
    mat = M.matrix(1.4, 1.1)
    assert M.model_prob("29", "", "No", "76", mat, 1.4, 1.1) is None
    assert M.model_prob("10", "", "Home or Away", "10", mat, 1.4, 1.1) is None
    assert M.model_prob("29", "", "Yes", "74", mat, 1.4, 1.1) > 0
    p = M.model_prob("1", "", "Home", "1", mat, 1.4, 1.1)
    assert p and 0.35 < p < 0.85


def test_half_lines_only():
    assert M.half_line("total=2.5") == 2.5
    assert M.half_line("total=3") is None
    assert M.half_line("total=1.5") == 1.5


def test_over_under_prob_sums():
    mat = M.matrix(1.3, 1.1)
    over = M.model_prob("18", "total=2.5", "Over 2.5", "12", mat, 1.3, 1.1)
    under = M.model_prob("18", "total=2.5", "Under 2.5", "13", mat, 1.3, 1.1)
    assert over and under
    assert abs((over + under) - 1) < 1e-9
