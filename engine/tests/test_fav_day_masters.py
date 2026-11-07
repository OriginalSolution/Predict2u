"""Unit tests for favourites day-master packing (no network)."""
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "engine" / "vendor"))
import fav_day_masters as FDM  # noqa: E402


def test_dedupe_one_per_game():
    pool = [
        {"eventId": "a", "confidence": 0.5, "odds": 1.2, "selection": "X"},
        {"eventId": "a", "confidence": 0.9, "odds": 1.3, "selection": "Y"},
        {"eventId": "b", "confidence": 0.4, "odds": 1.1, "selection": "Z"},
    ]
    out = FDM.dedupe_one_per_game(pool)
    assert len(out) == 2
    by = {p["eventId"]: p for p in out}
    assert by["a"]["selection"] == "Y"


def test_upcoming_drops_kicked_off():
    import datetime as dt
    now = dt.datetime(2026, 11, 6, 15, 0, tzinfo=dt.timezone.utc)
    picks = [
        {"eventId": "1", "date": "2026-11-06", "ko": "12:00", "match": "A v B"},
        {"eventId": "2", "date": "2026-11-06", "ko": "19:00", "match": "C v D"},
    ]
    kept, dropped = FDM.upcoming(picks, now=now)
    assert len(kept) == 1 and kept[0]["eventId"] == "2"
    assert len(dropped) == 1 and dropped[0]["reason"] == "kicked off"


def test_chunk_legs():
    # Balanced round-robin split (not greedy) so each part has similar leg counts /
    # odds instead of a short low-odds tail.
    legs = [{"eventId": str(i)} for i in range(65)]
    parts = FDM.chunk_legs(legs, max_legs=30)
    assert [len(p) for p in parts] == [22, 22, 21]
    assert all(len(p) <= 30 for p in parts)
    assert sum(len(p) for p in parts) == 65
    # Under the cap: single part.
    assert [len(p) for p in FDM.chunk_legs(legs[:30], max_legs=30)] == [30]


def test_build_day_masters_calls_book_fn():
    picks = []
    for i in range(10):
        picks.append({"eventId": f"e{i}", "date": "2026-11-06", "ko": "20:00", "odds": 1.2, "confidence": 0.8,
                      "match": f"M{i}", "selection": "Over 1.5", "marketId": "18", "specifier": "total=1.5", "outcomeId": "12"})
    for i in range(5):
        picks.append({"eventId": f"t{i}", "date": "2026-11-07", "ko": "15:00", "odds": 1.15, "confidence": 0.7,
                      "match": f"T{i}", "selection": "Under 3.5", "marketId": "18", "specifier": "total=3.5", "outcomeId": "13"})
    booked = []

    def book_fn(name, legs):
        booked.append((name, len(legs)))
        return {"name": name, "bookedAt": "2026-11-06T12:00:00+00:00",
                "codes": {"sportybet": [{"code": "TEST", "totalOdds": 2, "legs": len(legs), "link": "https://x"}]}}

    import datetime as dt
    now = dt.datetime(2026, 11, 6, 12, 0, tzinfo=dt.timezone.utc)
    masters = FDM.build_day_masters(picks, book_fn, now=now, today="2026-11-06", days_ahead=1)
    assert "2026-11-06" in masters and "2026-11-07" in masters
    assert masters["2026-11-06"]["legs"] == 10
    assert masters["2026-11-07"]["legs"] == 5
    assert masters["2026-11-06"]["codes"]["sportybet"][0]["code"] == "TEST"
    assert len(booked) == 2


def test_book_home_wires_day_masters():
    src = (ROOT / "engine" / "vendor" / "book_home.py").read_text()
    assert "fav_day_masters" in src
    assert "dayMasters" in src
    assert "--day-masters-only" in src


def test_home_ui_renders_day_masters():
    js = (ROOT / "p2u-home-v318.js").read_text()
    assert "dayMasterHTML" in js
    assert "dayMasters" in js
