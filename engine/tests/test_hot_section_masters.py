"""Unit tests for Hot page section-master packing (no network)."""
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "engine" / "vendor"))
import hot_section_masters as HSM  # noqa: E402


def test_dedupe_keeps_one_per_event():
    pool = [
        {"eventId": "a", "count": 10, "backing": 1, "odds": 1.2, "selection": "X"},
        {"eventId": "a", "count": 40, "backing": 9, "odds": 1.3, "selection": "Y"},
        {"eventId": "b", "count": 5, "backing": 1, "odds": 1.1, "selection": "Z"},
    ]
    out = HSM.dedupe_event(pool)
    assert len(out) == 2
    by = {p["eventId"]: p for p in out}
    assert by["a"]["selection"] == "Y"


def test_pack_floor_reaches_25():
    pool = [{"eventId": str(i), "count": 100 - i, "backing": 1, "odds": 1.25} for i in range(20)]
    out = HSM.pack_floor(pool, floor=25, min_legs=5)
    assert len(out) >= 5
    assert math.prod(p["odds"] for p in out) >= 25


def test_pack_floor_keeps_under_floor_pool():
    pool = [{"eventId": str(i), "count": 10, "backing": 1, "odds": 1.05} for i in range(6)]
    out = HSM.pack_floor(pool, floor=25, min_legs=5, max_legs=30)
    assert len(out) == 6
    assert math.prod(p["odds"] for p in out) < 25


def test_section_builders_cover_five_sections():
    ids = [x[0] for x in HSM.SECTION_BUILDERS]
    assert ids == ["hot_matches", "hot_by_market", "trending_markets", "hot_teams", "most_backed_teams"]


def test_build_section_masters_calls_book_fn():
    doc = {
        "picks": [{"eventId": f"e{i}", "count": 50 - i, "backing": 10, "odds": 1.3} for i in range(20)],
        "byMarket": [{"market": "Over 1.5 goals", "picks": [{"eventId": f"m{i}", "count": 40, "backing": 5, "odds": 1.28} for i in range(15)]}],
        "markets": [{"name": "Over 1.5 goals", "count": 100}],
        "byTeam": [{"team": "A", "picks": [{"eventId": f"t{i}", "count": 30, "backing": 3, "odds": 1.22} for i in range(12)]}],
        "teams": [{"name": "A", "count": 30}],
    }
    booked = []

    def book_fn(name, legs):
        booked.append(name)
        return {"name": name, "codes": {"sportybet": [{"code": "TEST", "totalOdds": 2, "legs": len(legs), "link": "https://x"}]}}

    masters = HSM.build_section_masters(doc, book_fn)
    assert len(masters) == 5
    assert len(booked) == 5
    assert all(m.get("section") for m in masters)


def test_hot_picks_wires_section_masters():
    src = (ROOT / "engine" / "vendor" / "hot_picks.py").read_text()
    assert "hot_section_masters" in src
    assert "sectionMasters" in src
    assert "--section-masters-only" in src


def test_carousel_renders_section_masters():
    js = (ROOT / "p2u-codes-carousel-v299.js").read_text()
    assert "cardsSectionMasters" in js
    assert "sectionCard" in js
