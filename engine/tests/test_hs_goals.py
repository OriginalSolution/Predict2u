"""High-Scoring Teams O1.5/O2.5 (pure rules + selection/publish with stubs, no network)."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "engine" / "vendor"))
import hs_goals as hs  # noqa: E402
import strategy_lib as lib  # noqa: E402
import master_pipeline as mp  # noqa: E402

CFG = hs.load_config()


def test_config_file_and_defaults():
    raw = json.loads((ROOT / "engine" / "hs_goals.json").read_text())
    assert raw["min_scored"] == 1.5 and raw["min_conceded"] == 1.5
    assert (raw["o15_min"], raw["o15_max"], raw["o25_max"]) == (1.20, 1.30, 1.55)
    assert raw["max_legs"] == 25 and raw["combine"] == "mean"


def test_market_ladder():
    assert hs.pick_market(1.20, 1.70, CFG)[0] == "o15"
    assert hs.pick_market(1.30, 1.90, CFG)[0] == "o15"
    assert hs.pick_market(1.31, 1.50, CFG)[0] is None             # O1.5 above 1.30 -> reject
    assert hs.pick_market(1.19, 1.54, CFG)[0] == "o25"
    assert hs.pick_market(1.19, 1.55, CFG)[0] is None             # O2.5 must be below 1.55
    assert hs.pick_market(1.10, None, CFG)[0] is None
    assert hs.pick_market(None, 1.40, CFG)[0] is None


def test_team_averages_blend_season_and_last10():
    last = [(2, 2)] * 10                                          # 2.0 / 2.0
    av = hs.team_averages((14, 14, 14), last, CFG)                # season 1.0 / 1.0
    assert hs.team_passes(av, CFG) == (True, 1.5, 1.5)            # mean = 1.5 / 1.5
    av = hs.team_averages((13, 30, 14), last, CFG)                # scored mean 1.46
    assert hs.team_passes(av, CFG)[0] is False
    both = dict(CFG, combine="both")
    assert hs.team_passes(hs.team_averages((14, 14, 14), last, both), both)[0] is False
    assert hs.team_passes(hs.team_averages((28, 28, 14), last, both), both)[0] is True


def test_minimum_games_and_missing_stats():
    av = hs.team_averages((4, 4, 2), [(2, 2)] * 4, CFG)           # season 2 games, last 4 -> neither counts
    assert av == {"season": None, "last": None} and hs.team_passes(av, CFG) == (False, None, None)
    av = hs.team_averages(None, [(2, 2)] * 10, CFG)               # last 10 alone is enough under "mean"
    assert hs.team_passes(av, CFG)[0] is True


def odds(o15=None, o25=None):
    out = {"1||Home": [1.8, "1"], "1||Draw": [3.6, "2"], "1||Away": [4.0, "3"]}
    if o15:
        out[hs.O15] = [o15, "12"]
    if o25:
        out[hs.O25] = [o25, "12"]
    return out


def row(i, o):
    ev = {"eventId": f"sr:match:{i}", "homeTeamName": f"H{i}", "awayTeamName": f"A{i}", "estimateStartTime": 1795300000000,
          "sport": {"category": {"name": "England", "tournament": {"name": "Premier League"}}}}
    return {"event": ev, "eventId": ev["eventId"], "odds": o}


HIGH = {"home": {"season": (30, 30, 15), "last": [(2, 2)] * 10}, "away": {"season": (30, 30, 15), "last": [(2, 2)] * 10}}
LOW = {"home": {"season": (10, 30, 15), "last": [(0, 2)] * 10}, "away": HIGH["away"]}


def test_select_rules_cap_and_one_pick_per_match():
    rows = [row(1, odds(1.25, 1.8)), row(2, odds(1.15, 1.45)), row(3, odds(1.35, 1.9)), row(4, odds(1.25, 1.8)),
            row(5, odds(1.25, 1.8))]
    stats = {"sr:match:4": LOW}
    usage = {"sr:match:5": ["A", "B"]}
    out = hs.select(rows, {}, usage, CFG, fetch_fn=lambda eid, cache: stats.get(eid, HIGH))
    got = {leg["eventId"]: (leg["rule"], leg["selection"]) for leg in out["legs"]}
    assert got == {"sr:match:1": ("o15", "Over 1.5"), "sr:match:2": ("o25", "Over 2.5")}
    assert out["removed"] == {"already on 2 codes": 1, "Over 1.5 above 1.30": 1, "team averages under 1.5": 1}
    assert len({leg["eventId"] for leg in out["legs"]}) == len(out["legs"])


def legs(n, rule, free=2):
    return [{"eventId": f"sr:match:{rule}{i}", "rule": rule, "odds": 1.25, "free": free} for i in range(n)]


def test_plan_separate_codes_and_master_split_at_25():
    plan = hs.plan_codes(legs(3, "o15") + legs(2, "o25"), CFG)
    assert [(p["id"], len(p["legs"])) for p in plan] == [("hs15-o15", 3), ("hs15-o25", 2), ("hs15-master", 5)]
    plan = hs.plan_codes(legs(20, "o15") + legs(10, "o25"), CFG)
    assert [(p["id"], len(p["legs"])) for p in plan] == [
        ("hs15-o15", 20), ("hs15-o25", 10), ("hs15-master-1", 25), ("hs15-master-2", 5)]
    assert all(len(p["legs"]) <= 25 for p in plan)
    # a match with one free slot left goes on the master only (2-codes-per-match cap)
    plan = hs.plan_codes(legs(2, "o15") + legs(1, "o15", free=1), CFG)
    assert [(p["id"], len(p["legs"])) for p in plan] == [("hs15-o15", 2), ("hs15-master", 3)]
    assert hs.plan_codes(legs(1, "o15"), CFG) == []               # min 2 legs per code, never padded


def test_book_verified_reads_back_and_drops_started(monkeypatch):
    calls = []
    monkeypatch.setattr(lib, "book_sportybet", lambda sel: (calls.append(len(sel)) or f"C{len(calls)}", "ok"))

    def share(code):
        n = calls[-1]
        rows = [{"eventId": f"e{i}", "matchStatus": "Not start" if (code != "C1" or i) else "H1",
                 "markets": [{"outcomes": [{"odds": "1.25"}]}]} for i in range(n)]
        return {"outcomes": rows}
    monkeypatch.setattr(lib, "read_share", share)
    L = [{"eventId": f"e{i}", "marketId": "18", "specifier": "total=1.5", "outcomeId": "12"} for i in range(3)]
    res = hs.book_verified(L)
    assert res["code"] == "C2" and len(res["legs"]) == 2 and res["readBack"] and res["total"] == round(1.25 ** 2, 2)


def test_publish_to_hot_and_bankers_and_build_keeps_it(tmp_path):
    (tmp_path / "hot-picks.json").write_text(json.dumps({"modelSlips": [{"strategy": "M1", "codes": {"sportybet": [{}]}}]}))
    (tmp_path / "picks.json").write_text(json.dumps({"slips": [{"name": "Slip 1", "code": "OLD"}]}))
    leg = {"eventId": "sr:match:1", "marketId": "18", "specifier": "total=1.5", "outcomeId": "12", "market": "Over/Under",
           "selection": "Over 1.5", "odds": 1.25, "match": "H v A", "league": "England - Premier League",
           "date": "2026-11-22", "ko": "15:00", "kickoff": "2026-11-22T15:00:00Z", "rule": "o15"}
    code = {"id": "hs15-o15", "label": "High-Scoring O1.5/O2.5 · Over 1.5", "legs": [leg, dict(leg, eventId="sr:match:2", match="X v Y")],
            "code": "ABC123", "total": 1.56, "link": lib.SB_LINK.format("ABC123")}
    hs.publish(tmp_path, "2026-11-22", [code])
    hot = json.loads((tmp_path / "hot-picks.json").read_text())
    assert [s["strategy"] for s in hot["modelSlips"]] == ["hs15-o15", "M1"]
    assert hot["modelSlips"][0]["codes"]["sportybet"][0]["code"] == "ABC123"
    picks = json.loads((tmp_path / "picks.json").read_text())
    new = [s for s in picks["slips"] if s.get("hsId")]
    assert len(new) == 1 and new[0]["code"] == "ABC123" and new[0]["floorExempt"] and new[0]["picks"] == 2
    hs.publish(tmp_path, "2026-11-22", [dict(code, code="NEW999")])   # same day re-run replaces, never duplicates
    picks = json.loads((tmp_path / "picks.json").read_text())
    assert [s.get("code") for s in picks["slips"]] == ["OLD", "NEW999"]
    build = (ROOT / "engine" / "vendor" / "build.py").read_text()
    assert "strategy-codes', 'hs15'" in build and "sl.get('floorExempt')" in build


def test_wired_daily_before_publish_and_master_priority():
    assert mp.STRENGTH.index("hs15") == mp.STRENGTH.index("ah1") + 1
    assert lib.PUBLIC_NAME["hs15"] == "High-Scoring O1.5/O2.5"
    wf = (ROOT / ".github" / "workflows" / "engine-hs-goals.yml").read_text()
    assert 'cron: "30 21 * * *"' in wf and "--at 21:30 --job hs15" in wf and "engine/vendor/hs_goals.py" in wf
    assert "engine/data/strategy-codes/hs15" in wf and "picks.json" in wf and "hot-picks.json" in wf
    ticker = (ROOT / ".github" / "scripts" / "p2u_ticker.py").read_text()
    assert '("engine-hs-goals.yml", "30", "21", "*")' in ticker
    watchdog = (ROOT / ".github" / "scripts" / "p2u_watchdog.py").read_text()
    assert 'wf="engine-hs-goals.yml", at="21:30", job="hs15"' in watchdog
    assert "High-Scoring O1.5/O2.5" in (ROOT / "HANDOFF.md").read_text()


def test_published_codes_block_a_second_booking(tmp_path):
    import json
    (tmp_path / "hot-picks.json").write_text(json.dumps({"modelSlips": [
        {"strategy": "hs15-o15", "date": "2026-11-22", "codes": {"sportybet": [{"code": "AB12CD"}]}},
        {"strategy": "ah1-x", "date": "2026-11-22", "codes": {"sportybet": [{"code": "ZZ"}]}}]}))
    assert hs.published_codes(tmp_path, "2026-11-22") == ["AB12CD"]
    assert hs.published_codes(tmp_path, "2026-11-23") == []
    r = hs.run(__import__("datetime").date(2026, 11, 22), tmp_path)
    assert r == {"skipped": True}


def test_build_carries_live_hs15_slips_forward():
    src = (ROOT / "engine/vendor/build.py").read_text()
    assert "carry hs15 slips forward from the live picks.json" in src and "sl.get('floorExempt')" in src
