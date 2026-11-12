"""Regression tests for M1/M2, Safest market, and the Nov 9 pool-0 matcher bug."""
import datetime as dt
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "engine"), str(ROOT / "engine" / "vendor")]

import m1m2  # noqa: E402
import publish_hot as PH  # noqa: E402
import safe50  # noqa: E402
import three_strategies as TS  # noqa: E402
import verzzify_banker as VZ  # noqa: E402


def future_ms(days=1):
    return int((dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=days)).timestamp() * 1000)


def premier(home_odds="1.18"):
    return {
        "eventId": "sr:match:99",
        "homeTeamName": "Arsenal",
        "awayTeamName": "Wolves",
        "matchStatus": "Not start",
        "estimateStartTime": future_ms(),
        "sport": {"category": {"name": "England", "tournament": {"name": "Premier League"}}},
        "markets": [
            {"id": "1", "outcomes": [
                {"id": "1", "desc": "Home", "odds": home_odds, "isActive": 1},
                {"id": "2", "desc": "Draw", "odds": "6.00", "isActive": 1},
                {"id": "3", "desc": "Away", "odds": "12.00", "isActive": 1},
            ]},
            {"id": "18", "specifier": "total=2.5", "outcomes": [
                {"id": "12", "desc": "Over 2.5", "odds": "1.40", "isActive": 1},
                {"id": "13", "desc": "Under 2.5", "odds": "2.80", "isActive": 1},
            ]},
            {"id": "68", "specifier": "total=1.5", "outcomes": [
                {"id": "12", "desc": "Over 1.5", "odds": "2.40", "isActive": 1},
            ]},
            {"id": "854", "specifier": "total=2.5", "outcomes": [
                {"id": "74", "desc": "Yes", "odds": "1.08", "isActive": 1},
                {"id": "76", "desc": "No", "odds": "7.00", "isActive": 1},
            ]},
            {"id": "858", "specifier": "total=2.5", "outcomes": [
                {"id": "74", "desc": "Yes", "odds": "1.40", "isActive": 1},
            ]},
            {"id": "547", "specifier": "total=1.5", "outcomes": [
                {"id": "1727", "desc": "Home/Draw & Over 1.5", "odds": "1.12", "isActive": 1},
                {"id": "1728", "desc": "Home/Away & Over 1.5", "odds": "1.05", "isActive": 1},
                {"id": "1729", "desc": "Draw/Away & Over 1.5", "odds": "2.40", "isActive": 1},
            ]},
            {"id": "11", "specifier": "", "outcomes": [
                {"id": "4", "desc": "Home", "odds": "1.30", "isActive": 1},
                {"id": "5", "desc": "Away", "odds": "3.40", "isActive": 1},
            ]},
            {"id": "19", "specifier": "total=1.5", "outcomes": [
                {"id": "12", "desc": "Over 1.5", "odds": "1.40", "isActive": 1},
            ]},
            {"id": "10", "outcomes": [
                {"id": "9", "desc": "Home or Draw", "odds": "1.10", "isActive": 1},
                {"id": "10", "desc": "Home or Away", "odds": "1.08", "isActive": 1},
                {"id": "11", "desc": "Draw or Away", "odds": "1.90", "isActive": 1},
            ]},
        ],
    }


def test_sportradar_path_is_numeric_not_sr_match():
    paths = TS.stats_paths("sr:match:72221392")
    assert paths == ["match_info/72221392", "stats_match_get/72221392"]
    assert all("sr:match:" not in p for p in paths)
    # The Nov 9 lookup used this path and Sportradar returned event=exception.
    assert "match_detailsextended/sr:match:72221392" not in paths


def test_pool_zero_without_numeric_context_and_picks_once_context_exists():
    """O2.5 in band alone is one of three conditions. No 1H price under 2.00 and
    no season (the sr:match failure) → zero picks. A numeric-id context that
    supplies the league average and the table produces the Over 2.5 leg."""
    data = premier()
    assert TS.picks_for_event(data, {}) == []
    ctx = dict(avg=2.8, n_matches=22, hp=2, ap=14, N=20, hw=3, hn=3, aw=0, an=3)
    picks = TS.picks_for_event(data, ctx)
    assert any(p["strategy"] == "o25-2of3" and p["marketId"] == "18" for p in picks)


def test_dnb_uses_market_11_outcomes_4_and_5():
    data = premier(home_odds="1.70")  # win above 1.45, so the strong side is DNB
    # Drop the O2.5 band so strategy 1 cannot fire and hide the DNB.
    data["markets"] = [m for m in data["markets"] if not (str(m.get("id")) == "18")]
    ctx = dict(avg=None, n_matches=0, hp=1, ap=12, N=20, hw=3, hn=3, aw=1, an=3)
    picks = TS.picks_for_event(data, ctx)
    dnb = [p for p in picks if p["strategy"] == "top3-form-dnb"]
    assert dnb and dnb[0]["marketId"] == "11" and dnb[0]["outcomeId"] == "4"
    assert TS.dnb_outcome_id("H") == "4" and TS.dnb_outcome_id("A") == "5"
    # The old matcher asked for 1X2 outcome id 1 on the DNB market and got nothing.
    assert TS.outcome(data["markets"], "11", "", oid="1") is None


def test_gate_drops_dc12_ng_and_1x_above_135():
    base = dict(eventId="sr:match:1", match="A v B", league="England - Premier League",
                x12="1.20/5.00/9.00", table="2 v 16/20", odds=1.20)
    dc12 = dict(base, marketId="10", outcomeId="10", selection="Home or Away", market="Double Chance")
    high = dict(base, marketId="10", outcomeId="9", selection="Home or Draw", market="Double Chance", odds=1.40)
    ng = dict(base, marketId="29", outcomeId="76", selection="No", market="GG/NG")
    assert TS.gate_ok(dict(dc12), enrich=False) is False
    assert TS.gate_ok(dict(high), enrich=False) is False
    assert TS.gate_ok(dict(ng), enrich=False) is False


def test_original_thresholds_ignore_the_upgrade():
    assert m1m2.qualifies(1.30, 1.50, "M1")
    assert not m1m2.qualifies(1.32, 1.52, "M1")  # upgrade would have taken this
    assert m1m2.M1_PW == 1.30 and m1m2.RELAX_M1 == (1.35, 1.55)
    assert m1m2.qualifies(1.20, 1.40, "M2")
    assert not m1m2.qualifies(1.22, 1.42, "M2")
    assert m1m2.RELAX_M2 == (1.25, 1.45)


def test_m1_books_yes_not_dc12_and_mixed_only_with_team2():
    cands = m1m2.build_candidates(premier("1.18"))
    rules = {p["rule"] for p in cands}
    assert rules == {"M1", "M2", "T2"}
    m1 = next(p for p in cands if p["rule"] == "M1")
    assert m1["marketId"] == "854" and m1["outcomeId"] == "74"
    assert m1["selection"] == "Home Team or Over 2.5"
    m2 = next(p for p in cands if p["rule"] == "M2")
    assert m2["outcomeId"] == "1727" and m2["outcomeId"] != "1728"
    # Stamp a mismatch table so the normal gate can pass without a network enrich.
    for p in cands:
        p["table"] = "2 v 16/20"
        p["x12"] = "1.18/6.00/12.00"
    groups = m1m2.select(cands, enrich=False)
    assert groups["M1"] and groups["M2"] and groups["MIXED"]
    # No team-2+ candidate → MIXED is empty even if M1 and M2 exist.
    only = [p for p in cands if p["rule"] != "T2"]
    assert m1m2.select(only, enrich=False)["MIXED"] == []


def test_m1_above_relax_but_inside_upgrade_is_not_a_candidate():
    data = premier("1.32")
    for m in data["markets"]:
        if str(m.get("id")) == "18" and m.get("specifier") == "total=2.5":
            for o in m["outcomes"]:
                if str(o["id"]) == "12":
                    o["odds"] = "1.52"
    assert m1m2.build_candidates(data) == []


def test_safe50_prefers_two_way_goals_and_drops_extreme_lines():
    data = {
        "eventId": "sr:match:7",
        "homeTeamName": "Home FC",
        "awayTeamName": "Away FC",
        "matchStatus": "Not start",
        "estimateStartTime": future_ms(),
        "sport": {"category": {"name": "Romania", "tournament": {"name": "Liga III"}}},
        "markets": [
            {"id": "1", "status": 0, "desc": "1X2", "outcomes": [
                {"id": "1", "desc": "Home", "odds": "1.25", "isActive": 1},
                {"id": "2", "desc": "Draw", "odds": "5.00", "isActive": 1},
                {"id": "3", "desc": "Away", "odds": "8.00", "isActive": 1},
            ]},
            {"id": "18", "status": 0, "desc": "Over/Under", "specifier": "total=4.5", "outcomes": [
                {"id": "13", "desc": "Under 4.5", "odds": "1.20", "isActive": 1},
                {"id": "12", "desc": "Over 4.5", "odds": "4.20", "isActive": 1},
            ]},
            {"id": "18", "status": 0, "desc": "Over/Under", "specifier": "total=1.5", "outcomes": [
                {"id": "12", "desc": "Over 1.5", "odds": "1.28", "isActive": 1},
                {"id": "13", "desc": "Under 1.5", "odds": "3.40", "isActive": 1},
            ]},
        ],
    }
    best = safe50.score_event(data)
    assert best["marketId"] == "18" and best["specifier"] == "total=1.5"
    assert best["selection"].startswith("Over")
    assert safe50.extreme_line("total=4.5", "Under 4.5", "Over/Under") == 2
    assert safe50.extreme_line("total=1.5", "Over 1.5", "Over/Under") == 0


def test_safe50_does_not_book_a_short_split():
    short = [{"eventId": str(i), "odds": 1.05, "fair": 0.9, "ext": 0, "kickoff": "2026-11-13T18:00:00Z"} for i in range(30)]
    plan = safe50.split_plan(short)
    assert [name for name, _ in plan] == ["Safest market"]
    full = [{"eventId": str(i), "odds": 1.30, "fair": 0.7, "ext": 0, "kickoff": f"2026-11-13T{i%24:02d}:00:00Z"} for i in range(50)]
    names = [name for name, legs in safe50.split_plan(full)]
    assert names[0] == "Safest market"
    assert "Safest market · part 1" in names and "Safest market · part 2" in names
    assert all(len(legs) <= 50 for _, legs in safe50.split_plan(full))


def test_safe50_sanity_drops_contradiction_and_missing_stats():
    pick = dict(market="Over/Under", specifier="total=1.5", selection="Over 1.5")
    assert safe50.line_supported(pick, [])[0] is False
    soft = [dict(n=8, avg=1.2, o15=0.25, o25=0.1, u35=0.9, u4=1.0)]
    assert safe50.line_supported(pick, soft)[0] is False
    firm = [dict(n=8, avg=3.1, o15=0.8, o25=0.5, u35=0.4, u4=0.7)]
    assert safe50.line_supported(pick, firm)[0] is True


def test_verzzify_does_not_bypass_an_unverified_leg():
    src = Path(VZ.__file__).read_text()
    assert "MR.enrich" in src
    assert 'p["gate"]' not in src
    assert 'UA = "Mozilla/5.0"' not in src
    assert "Chrome/124" in src
    p = dict(eventId="sr:match:1", match="Arsenal v Wolves", league="England - Premier League",
             marketId="18", specifier="total=1.5", outcomeId="12", market="Over/Under",
             selection="Over 1.5", odds=1.25, x12="1.20/5.00/9.00", table="1 v 16/18",
             source="verzzify-scan", date=dt.datetime.now(dt.timezone.utc).date().isoformat(),
             confidence=None, leagueFavRate=None, sample=None)
    ok, why = VZ.eligible(p)
    assert ok, why
    bare = dict(p)
    bare.pop("table")
    bare.pop("x12")
    # No table and no 1X2: still unverified. Do not call the network enrich.
    bare_ok, bare_why = VZ.eligible.__wrapped__(bare) if hasattr(VZ.eligible, "__wrapped__") else (None, None)
    if bare_ok is None:
        import matchup_rules as MR
        assert MR.check(dict(bare, x12="", table=""))[0] is False


def test_publish_hides_a_slip_with_no_codes(tmp_path):
    doc = PH.upsert_model_slips(tmp_path, [
        {"name": "M1", "strategy": "M1", "codes": {"sportybet": [{"code": "ABCDE", "totalOdds": 2, "legs": 3, "link": "https://x"}]}},
        {"name": "empty", "strategy": "M2", "codes": {}},
    ])
    assert [s["strategy"] for s in doc["modelSlips"]] == ["M1"]
    again = PH.upsert_model_slips(tmp_path, [], replace_strategies={"M1"})
    assert again["modelSlips"] == []


def test_hot_page_and_carousel_render_model_slips_and_hide_empty():
    hot = (ROOT / "p2u-hot-v309.js").read_text()
    car = (ROOT / "p2u-codes-carousel-v299.js").read_text()
    assert "modelSlips" in hot and "if(models.length)" in hot
    assert "cardsModel" in car and "cardsModel(d).concat" in car


def test_desc_is_not_a_second_copy_of_the_same_legs():
    legs = []
    for i, odds in enumerate((1.22, 1.30, 1.38)):
        legs.append(dict(eventId=f"e{i}", odds=odds, strategy="o25-2of3",
                         kickoff="2026-11-20T18:00:00Z", marketId="18", specifier="total=2.5", outcomeId="12"))
    out = TS.book_masters(legs, "2026-11-12", book=False)
    assert [r["key"] for r in out] == ["asc"]
    assert out[0]["legs"] == 3 and out[0]["meetsFloor"] is False


def test_ledger_seed_has_original_slips_and_not_the_upgrade():
    led = json.loads((ROOT / "engine" / "data" / "m1m2_ledger.json").read_text())
    assert led["days"]["2026-11-06"]["M1"]["code"] == "AGH31Q"
    assert led["days"]["2026-11-07"]["M1"]["code"] == "8J5FKM"
    blob = json.dumps(led)
    assert "CBL50Z" not in blob and "9YK06D" not in blob and "AXQY77" not in blob
