import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "engine" / "vendor"))
import ah_minus_one as ah


def test_deep_band_prefers_goals():
    targets = ah.choose_targets(1.24, "H")
    assert targets[0][0] == "18" and targets[0][1] == "total=2.5"


def test_soft_band_prefers_team_over_then_win():
    targets = ah.choose_targets(1.68, "A")
    assert targets[0] == ("20", "total=1.5", "12", "Over 1.5")
    assert targets[1][0] == "1"


def test_skip_women():
    ev = {
        "homeTeamName": "Alpha W",
        "awayTeamName": "Beta Ladies",
        "tournamentName": "Women Super League",
        "markets": [{"id": "16", "specifier": "hcp=-1", "outcomes": [{"id": "1", "desc": "Home", "odds": "1.40"}]}],
    }
    assert ah.pick_from_event(ev) is None
