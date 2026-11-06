import json
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from engine import inbox


def test_loads_and_scrubs(tmp_path):
    payload = {
        "date": "2026-11-06",
        "source": "Bets For The Day",
        "picks": [{
            "match": "Alpha v Beta",
            "selection": "Yes",
            "eventId": "sr:match:99",
            "marketId": "29",
            "outcomeId": "74",
            "specifier": "",
            "odds": 1.33,
            "case": "from Bets For The Day research",
            "bot": "secret-bot",
        }]
    }
    (tmp_path / "drop.json").write_text(json.dumps(payload))
    picks = inbox.load_picks(tmp_path)
    assert len(picks) == 1
    assert "bot" not in picks[0]
    assert "Bets For The Day" not in picks[0]["case"]
    assert picks[0]["eventId"] == "sr:match:99"


def test_skips_smagpf(tmp_path):
    d = tmp_path / "smagpf"
    d.mkdir()
    (d / "2026-11-06.json").write_text(json.dumps({"picks": [{
        "match": "A v B", "selection": "Yes", "eventId": "sr:match:1",
        "marketId": "29", "outcomeId": "74"}]}))
    assert inbox.load_picks(tmp_path) == []


def test_merge_dedupes():
    a = [{"eventId": "sr:match:1", "marketId": "29", "specifier": "", "outcomeId": "74"}]
    b = [{"eventId": "sr:match:1", "marketId": "29", "specifier": "", "outcomeId": "74"},
         {"eventId": "sr:match:2", "marketId": "18", "specifier": "total=1.5", "outcomeId": "12"}]
    assert len(inbox.merge(a, b)) == 2
