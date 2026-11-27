"""Bankers sort must survive a slip whose date, grade, or rating is missing.

The 2026-11-26 22:00 engine-daily runs died in build.py when a combined slip
(kickoff set, date null) was sorted against dated house slips.
"""
import datetime as dt
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
VENDOR = ROOT / "engine" / "vendor"
sys.path.insert(0, str(VENDOR))
import slip_order  # noqa: E402


def _risk(s):
    return {"safe": 0, "medium": 1, "high": 2}.get(s.get("risk"), 4)


def test_sort_key_accepts_missing_date_grade_and_rating():
    # The production crash: one slip's date is None, the other's is a string.
    dated = [
        {"date": None, "grade": "C", "rating": 0.1},
        {"date": "2026-11-27", "grade": "A", "rating": 0.9},
        {"date": "2026-11-26", "grade": "B", "rating": 0.2},
    ]
    with pytest.raises(TypeError, match="NoneType.*str|str.*NoneType"):
        sorted(dated, key=lambda s: (s["date"], _risk(s), s["grade"], -s["rating"]))
    holes = dated + [
        {"date": "2026-11-27", "grade": None, "rating": None},
        {"grade": "C"},
    ]
    ordered = sorted(holes, key=lambda s: slip_order.slip_sort_key(s, _risk))
    assert [s.get("date") for s in ordered[:3]] == ["2026-11-26", "2026-11-27", "2026-11-27"]
    assert ordered[-1].get("date") is None


def test_leg_date_uses_kickoff_then_today():
    kick = {"date": None, "kickoff": "2026-11-28T18:00:00+00:00"}
    assert slip_order.stamp_leg(kick, "2026-11-27") == "2026-11-28"
    assert kick["date"] == "2026-11-28"
    blank = {"date": None, "ko": None}
    assert slip_order.stamp_leg(blank, "2026-11-27") == "2026-11-27"


def _leg(match, odds, date=None, kickoff=None):
    return {
        "date": date, "ko": None, "kickoff": kickoff, "league": "England - Premier League",
        "match": match, "market": "Over/Under", "selection": "Over 1.5", "odds": odds,
        "result": "pending",
    }


def test_build_publishes_dateless_combined_slip(tmp_path):
    """The crash shape: one dated house slip plus a combined slip with null date/grade/rating."""
    today = dt.datetime.now(dt.timezone.utc).date()
    tomorrow = (today + dt.timedelta(days=1)).isoformat()
    today_s = today.isoformat()
    kick = f"{tomorrow}T20:00:00+00:00"
    # 5 x 2.00 = 32, above the 25 floor, so both slips reach the sort.
    house = [_leg(f"H{i} v A{i}", 2.0, date=tomorrow, kickoff=f"{tomorrow}T1{i}:00:00Z") for i in range(5)]
    combined = [_leg(f"C{i} v D{i}", 2.0, date=None, kickoff=kick) for i in range(5)]
    bare = [_leg(f"E{i} v F{i}", 2.0, date=None, kickoff=None) for i in range(5)]
    research = tmp_path / "research"
    research.mkdir()
    (research / f"{today_s}.json").write_text(json.dumps({
        "date": today_s,
        "picks": [],
        "slips": [
            {"name": "House", "codes": {"sportybet": "HOUSE1"}, "legs": house},
            {"name": "Combined selection", "codes": {"sportybet": "COMB01"}, "date": None,
             "grade": None, "rating": None, "legs": combined},
            {"name": "Combined selection", "codes": {"sportybet": "BARE01"}, "date": None,
             "grade": None, "rating": None, "legs": bare},
        ],
    }))
    env = os.environ.copy()
    env.update({
        "RESEARCH_DIR": str(research),
        "PRIV_DIR": str(tmp_path / "private"),
        "REPO_DIR": str(tmp_path),
        "ENGINE_DIR": str(ROOT / "engine"),
        "PYTHONPATH": os.pathsep.join([str(VENDOR), str(ROOT / "engine"), str(ROOT)]),
    })
    proc = subprocess.run(
        [sys.executable, str(VENDOR / "build.py"), str(tmp_path)],
        cwd=str(ROOT), env=env, capture_output=True, text=True, timeout=60,
    )
    assert proc.returncode in (0, 3), proc.stderr + proc.stdout
    picks = json.loads((tmp_path / "picks.json").read_text())
    by_code = {s.get("code"): s for s in picks["slips"]}
    assert set(by_code) >= {"HOUSE1", "COMB01", "BARE01"}
    assert by_code["COMB01"]["date"] == tomorrow
    assert all(leg["date"] == tomorrow for leg in by_code["COMB01"]["legs"])
    assert by_code["BARE01"]["date"] == today_s
    assert all(isinstance(s["date"], str) and s["date"] for s in picks["slips"])
    assert all(s.get("grade") in ("A", "B", "C") and isinstance(s.get("rating"), (int, float)) for s in picks["slips"])
    # Re-running the same file must not raise either.
    again = subprocess.run(
        [sys.executable, str(VENDOR / "build.py"), str(tmp_path)],
        cwd=str(ROOT), env=env, capture_output=True, text=True, timeout=60,
    )
    assert again.returncode in (0, 3), again.stderr + again.stdout
