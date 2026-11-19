"""Master pipeline steps as pure functions (no network)."""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "engine" / "vendor"))
import master_pipeline as mp  # noqa: E402
import strategy_lib as lib  # noqa: E402
import sure80_reverse as sr  # noqa: E402

DAY = "2026-11-20"


def odds(**prices):
    return {sr.O[n]: [v, f"o-{n}"] for n, v in prices.items()}


def leg(eid, name, price, ko="12:00", day=DAY):
    mid, spec, _ = sr.O[name].split("|", 2)
    return {"eventId": eid, "marketId": mid, "specifier": spec or None, "outcomeId": f"o-{name}",
            "selection": name, "odds": price, "match": f"H{eid} v A{eid}", "date": day,
            "kickoff": f"{day}T{ko}:00Z", "_name": name}


def test_step1_pool_dedupes_and_stronger_code_wins():
    weak = {"code": "W", "origin": "strategy-rev-u45", "legs": [leg("1", "o25", 1.40), leg("2", "o15", 1.25)]}
    strong = {"code": "S", "origin": "strategy-sure80", "legs": [leg("1", "o15", 1.22), leg("3", "u45", 1.20)]}
    same = {"code": "D", "origin": "code-hub", "legs": [leg("3", "u45", 1.20)]}
    own = {"code": "M", "origin": "strategy-mp-master", "legs": [leg("9", "o15", 1.30)]}
    pool, log = mp.build_pool([weak, strong, same, own], DAY)
    by = {p["eventId"]: p for p in pool}
    assert set(by) == {"1", "2", "3"}
    assert by["1"]["sourceCode"] == "S" and by["1"]["_name"] == "o15"
    assert log["clashes"] == 1 and log["dupes"] == 1


def test_step1_strength_ties_use_lower_geometric_mean_price():
    a = {"code": "A", "origin": "code-hub", "legs": [leg("1", "o25", 1.60)]}
    b = {"code": "B", "origin": "code-hub", "legs": [leg("1", "o15", 1.20)]}
    pool, _ = mp.build_pool([a, b], DAY)
    assert pool[0]["sourceCode"] == "B"


def test_step1_drops_ng_dc_and_other_days():
    ng = dict(leg("1", "gg", 1.9), outcomeId="76", selection="No")
    dc = {"eventId": "2", "marketId": "10", "outcomeId": "9", "selection": "Home or Draw", "odds": 1.2, "date": DAY}
    other = leg("3", "o15", 1.3, day="2026-11-21")
    pool, log = mp.build_pool([{"code": "X", "origin": "code-hub", "legs": [ng, dc, other]}], DAY)
    assert pool == [] and log["banned"] == 2


def test_step1_refresh_drops_started_or_unlisted_and_takes_live_price():
    legs = [leg("1", "o15", 1.30), leg("2", "o15", 1.30)]
    events = {"1": {"league": "L", "odds": odds(o15=1.27)}}
    out, dropped = mp.refresh(legs, events)
    assert dropped == 1 and out[0]["odds"] == 1.27 and out[0]["_name"] == "o15"


def test_step2_league_fit_8pct_and_solo_kept():
    rows = [{"eventId": str(i), "league": "Uganda", "odds": odds(u35=1.24)} for i in range(2, 6)]
    rows.append({"eventId": "1", "league": "Uganda", "odds": odds(u35=1.45)})
    rows.append({"eventId": "9", "league": "Solo", "odds": odds(u35=1.45)})
    med = mp.medians_by_key(rows)
    a = dict(leg("1", "u35", 1.45), _league="Uganda", _odds=odds(u35=1.45))
    b = dict(leg("9", "u35", 1.45), _league="Solo", _odds=odds(u35=1.45))
    c = dict(leg("2", "u35", 1.24), _league="Uganda", _odds=odds(u35=1.24))
    kept, dropped = mp.league_fit_step([a, b, c], med)
    assert [k["eventId"] for k in kept] == ["9", "2"] and len(dropped) == 1
    assert mp.fits("Uganda", "1", sr.O["u35"], 1.33, med)[0]          # 1.24 x 1.08 = 1.339
    assert not mp.fits("Uganda", "1", sr.O["u35"], 1.35, med)[0]


def test_step3_u45_to_over25_then_over15_else_keep():
    hot = {"home": [(2, 2)] * 10, "away": [(3, 1)] * 10, "h2h": []}
    mid = {"home": [(1, 1)] * 9 + [(0, 0)], "away": [(2, 0)] * 10, "h2h": []}
    assert mp.u45_to_overs("u45", odds(o25=1.45, o15=1.18), 3.0, hot) == "o25"
    assert mp.u45_to_overs("u45", odds(o25=1.60, o15=1.18), 3.0, hot) == "o15"
    assert mp.u45_to_overs("u45", odds(o25=1.45, o15=1.18), 2.6, hot) == "o15"     # league < 2.8
    assert mp.u45_to_overs("u45", odds(o25=1.45, o15=1.20), 3.0, mid) == "o15"     # teams don't back O2.5
    assert mp.u45_to_overs("u45", odds(o25=1.45, o15=1.10), 3.0, mid) is None      # O1.5 too short
    assert mp.u45_to_overs("u45", odds(o25=1.45, o15=1.20), 2.4, mid) is None      # league too low
    assert mp.u45_to_overs("o15", odds(o25=1.45), 3.0, hot) is None


def test_step4_over145_swap_supported_alternative_or_drop():
    strong = {"home": [(2, 1)] * 10, "away": [(1, 2)] * 10, "h2h": []}
    ok = lambda name, price: True  # noqa: E731
    assert mp.swap_alternative("o25", odds(o25=1.70, o15=1.25), strong, ok) == "o15"
    assert mp.swap_alternative("u35", odds(u35=1.50, u45=1.20), {"home": [(1, 0)] * 10, "away": [(0, 1)] * 10}, ok) == "u45"
    assert mp.swap_alternative("o25", odds(o25=1.70, o15=1.50), strong, ok) is None            # alt still > 1.45
    assert mp.swap_alternative("o25", odds(o25=1.70, o15=1.25), strong, lambda n, p: False) is None  # league-fit
    weak = {"home": [(0, 0)] * 10, "away": [(0, 0)] * 10, "h2h": []}
    assert mp.swap_alternative("o25", odds(o25=1.70, o15=1.25), weak, ok) is None               # data says no
    assert "gg" not in sum(mp.ALTERNATIVES.values(), []) and all("dc" not in a for a in sum(mp.ALTERNATIVES.values(), []))


def _pool(n, price=1.30, step=0.0):
    return [dict(leg(str(i), "o15" if i % 2 else "h_o05", round(price + step * i, 2), ko=f"{(i % 24):02d}:00")) for i in range(n)]


def test_step5_outputs_halves_odds_split_and_groups():
    pool = _pool(60, 1.20, 0.01)
    codes, skipped = mp.outputs(pool)
    by = {c["id"]: c for c in codes}
    assert len(by["mp-early"]["legs"]) <= 35 and len(by["mp-late"]["legs"]) <= 35
    early, late = by["mp-early"]["legs"], by["mp-late"]["legs"]
    assert max(x["kickoff"] for x in early) <= min(x["kickoff"] for x in late)
    low, high = by["mp-low"]["legs"], by["mp-high"]["legs"]
    assert [x["odds"] for x in low] == sorted(x["odds"] for x in low)
    assert [x["odds"] for x in high] == sorted((x["odds"] for x in high), reverse=True)
    assert max(x["odds"] for x in low) <= min(x["odds"] for x in high)
    assert all(x["odds"] <= 1.42 for c in codes if c["id"].startswith("mp-master") for x in c["legs"])
    assert all(x["odds"] > 1.42 for c in codes if c["id"].startswith("mp-above") for x in c["legs"])
    groups = [c for c in codes if c["id"].startswith("mp-grp-")]
    assert groups and all(len(c["legs"]) <= 25 for c in groups)
    for c in codes:
        assert lib.product(x["odds"] for x in c["legs"]) >= 25, c["id"]
        assert len(c["legs"]) <= 50
    assert all(s["reason"] for s in skipped)


def test_step5_never_pads_and_logs_skips():
    codes, skipped = mp.outputs(_pool(6, 1.25))
    assert codes == [] and {s["id"] for s in skipped} >= {"mp-early", "mp-late", "mp-low", "mp-high", "mp-master"}
    assert any("under 25" in s["reason"] for s in skipped)


def test_step5_master_over_50_is_split_into_parts():
    codes, _ = mp.outputs(_pool(80, 1.30))
    parts = [c for c in codes if c["id"].startswith("mp-master-")]
    assert len(parts) == 2 and all(len(c["legs"]) == 40 for c in parts)
    big = [{"odds": 1.5}] * 26
    assert [len(p) for p in mp.deal(big, 25)] == [13, 13]          # both halves reach 25
    short = [{"odds": 1.2}] * 26
    assert [len(p) for p in mp.deal(short, 25)] == [25, 1]         # halves would both miss 25


def test_pipeline_slot_wiring():
    ticker = (ROOT / ".github/scripts/p2u_ticker.py").read_text()
    assert '("engine-master-pipeline.yml", "45", "22", "*")' in ticker
    wf = (ROOT / ".github/workflows/engine-master-pipeline.yml").read_text()
    assert 'cron: "45 22 * * *"' in wf and "p2u_gate.py --at 22:45 --job pipeline" in wf
    assert re.search(r"^  pipeline:\s*$", wf, re.M) and "p2u_push.sh main" in wf
    assert "group: predict2u-strategy-night" in wf
    wd = (ROOT / ".github/scripts/p2u_watchdog.py").read_text()
    assert 'wf="engine-master-pipeline.yml", at="22:45", job="pipeline"' in wd
