"""80% Sure, Reverse U4.5 and Reverse U4.5 + Draw rule (pure selection rules, no network)."""
import importlib.util
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "engine" / "vendor"))
import strategy_lib as lib  # noqa: E402
import sure80_reverse as s  # noqa: E402

_spec = importlib.util.spec_from_file_location("p2u_merge_live_t", ROOT / ".github/scripts/p2u_merge_live.py")


def odds(**prices):
    return {s.O[name]: [value, f"o-{name}"] for name, value in prices.items()}


def event(eid="sr:match:1", home="Alpha", away="Beta"):
    return {"eventId": eid, "homeTeamName": home, "awayTeamName": away, "estimateStartTime": 2000000000000,
            "sport": {"category": {"name": "Uganda", "tournament": {"name": "Premier League"}}}}


def strong_goals():
    # 10 games each with 3+ goals and both sides scoring
    return {"home": [(2, 1)] * 10, "away": [(1, 2)] * 10, "h2h": [(2, 2), (3, 1), (1, 2)]}


# ---------------------------------------------------------------- common rules
def test_split_codes_caps_25_two_codes_and_never_pads():
    legs = [{"eventId": f"e{i}", "odds": 1.30, "selection": "Over 1.5", "marketId": "18"} for i in range(60)]
    parts = s.split_codes(legs)
    assert len(parts) == 2 and all(len(p) == 25 for p in parts)
    assert all(lib.product(leg["odds"] for leg in p) >= 25 for p in parts)
    assert not {leg["eventId"] for leg in parts[0]} & {leg["eventId"] for leg in parts[1]}
    # 14 legs at 1.25 = 22.7 -> nothing (no padding)
    assert s.split_codes(legs[:14] and [dict(leg, odds=1.25) for leg in legs[:14]]) == []
    # 30 legs at 1.22: halves are 15 legs (19.7) -> one code of the best 25 (144)
    short = [dict(leg, odds=1.22) for leg in legs[:30]]
    one = s.split_codes(short)
    assert len(one) == 1 and len(one[0]) == 25


def test_split_codes_drops_ng_and_duplicates():
    legs = [{"eventId": f"e{i}", "odds": 1.4, "selection": "Over 1.5", "marketId": "18"} for i in range(12)]
    legs.append({"eventId": "e0", "odds": 1.4, "selection": "Over 2.5", "marketId": "18"})
    legs.append({"eventId": "ng", "odds": 3.0, "selection": "No", "marketId": "29", "outcomeId": "76"})
    parts = s.split_codes(legs)
    assert len(parts) == 1 and len(parts[0]) == 12
    assert all(leg["eventId"] != "ng" for leg in parts[0])


def test_match_limit_two_codes_overall():
    usage = {"e1": ["A", "B"]}
    assert not lib.can_take(usage, "e1") and lib.can_take(usage, "e2")


# ---------------------------------------------------------------- 80% Sure
def row(eid="e1", league="Uganda - Premier League", stats=None, table=None, **prices):
    return {"eventId": eid, "league": league, "odds": odds(**prices), "stats": stats or strong_goals(), "table": table}


def test_sure80_takes_supported_leg_in_band():
    r = row(o15=1.25, o25=1.80, u35=1.60)
    pick, why = s.sure80_pick(r, {})
    assert why == "ok" and pick["name"] in {"o15", "h_o05", "a_o05"} and 1.20 <= pick["odds"] <= 1.45
    assert pick["p"] > 0.80


def test_sure80_rejects_price_outside_120_145_and_weak_data():
    assert s.sure80_pick(row(o15=1.15, o25=1.50), {})[0] is None
    weak = {"home": [(0, 0)] * 5 + [(2, 1)] * 5, "away": [(0, 1)] * 5 + [(1, 2)] * 5, "h2h": []}
    pick, why = s.sure80_pick(row(stats=weak, o15=1.30), {})
    assert pick is None and "80" in why
    assert s.sure80_pick(row(stats={"home": [(1, 1)] * 3, "away": [(1, 1)] * 3}, o15=1.30), {})[1] == "no stats data"


def test_sure80_never_books_gg_ng_or_double_chance():
    r = row(gg=1.30)
    r["odds"]["10||Home or Draw"] = [1.25, "x"]
    assert s.sure80_pick(r, {})[0] is None


def test_sure80_drops_top5_v_top5_and_bottom3_v_bottom3():
    assert s.sure80_pick(row(o15=1.25, table={"home": 2, "away": 4, "n": 16}), {})[1] == "top-5 v top-5"
    assert s.sure80_pick(row(o15=1.25, table={"home": 15, "away": 16, "n": 16}), {})[1] == "bottom-3 v bottom-3"
    assert s.sure80_pick(row(o15=1.25, table={"home": 3, "away": 15, "n": 16}), {})[0]


def test_sure80_league_fit_uganda_example():
    # Uganda U3.5 @1.45 while the league's other fixtures sit around 1.24 -> drop
    low = {"home": [(1, 0)] * 10, "away": [(0, 1)] * 10, "h2h": [(1, 0)] * 3}
    target = row("u1", stats=low, u35=1.45)
    others = [row(f"u{i}", u35=1.24) for i in range(2, 6)]
    med = s.league_medians([target] + others)
    ok, median = s.league_fit(target, "u35", 1.45, med)
    assert not ok and median == 1.24
    pick, why = s.sure80_pick(target, med)
    assert pick is None or pick["name"] != "u35"
    # the same price fits when the league median is close
    med2 = s.league_medians([target] + [row(f"v{i}", u35=1.40) for i in range(2, 6)])
    assert s.league_fit(target, "u35", 1.45, med2)[0]
    # too few comparables -> conservative fallback cap
    assert not s.league_fit(target, "u35", 1.45, s.league_medians([target]))[0]
    assert s.league_fit(target, "u35", 1.30, s.league_medians([target]))[0]


def test_sure80_unders_take_wider_line_when_narrow_is_borderline():
    # under 3.5 in 8/10 and 8/9 games (84%, borderline); every game under 4.5
    st = {"home": [(1, 1)] * 8 + [(3, 1)] * 2, "away": [(1, 0)] * 8 + [(2, 2)], "h2h": []}
    p35 = s.estimate("u35", st)
    assert 0.80 < p35 < 0.85
    pick, _ = s.sure80_pick(row(stats=st, u35=1.22, u45=1.21), {})
    assert pick["name"] == "u45"


def test_sure80_win_needs_table_and_gf_ga():
    st = {"home": [(3, 0)] * 9 + [(1, 1)], "away": [(0, 2)] * 9 + [(1, 1)], "h2h": [(2, 0)] * 3}
    assert s.sure80_pick(row(stats=st, home=1.30), {})[0] is None            # no table -> no win pick
    pick, _ = s.sure80_pick(row(stats=st, home=1.30, table={"home": 2, "away": 12, "n": 16}), {})
    assert pick["name"] == "home"
    # GF/GA contradicts the pick -> estimate 0
    flipped = {"home": [(1, 0)] * 10, "away": [(4, 0)] * 10, "h2h": []}
    assert s.estimate("home", flipped) == 0.0


def test_sure80_leg_grades_with_settler_selection_names():
    leg = s.make_leg(event(), odds(h_o05=1.22), "h_o05", "sure80")
    assert leg["selection"] == "Alpha over 0.5 goals" and leg["marketId"] == "19"
    dnb = s.make_leg(event(), odds(dnb_home=1.30), "dnb_home", "sure80")
    assert dnb["marketId"] == "11" and dnb["selection"] == "Home"


# ---------------------------------------------------------------- Reverse U4.5
def pool_row(gpg=3.0, n=40, **prices):
    return {"odds": odds(**prices), "gpg": gpg, "season_n": n}


def test_reverse_pool_needs_u45_over_120_and_high_scoring_league():
    assert s.reverse_pool(pool_row(u45=1.28))[0]
    assert s.reverse_pool(pool_row(u4=1.30))[0]                                 # Under 4 when 4.5 absent
    assert not s.reverse_pool(pool_row(u45=1.20))[0]
    assert "goals/game" in s.reverse_pool(pool_row(gpg=2.6, u45=1.30))[1]
    assert not s.reverse_pool(pool_row(gpg=None, u45=1.30))[0]
    assert not s.reverse_pool(pool_row(n=5, u45=1.30))[0]


def test_reverse_pick_over15_then_over25_else_skip():
    assert s.reverse_pick(odds(o15=1.22, o25=1.70)) == "o15"
    assert s.reverse_pick(odds(o15=1.25, o25=1.70)) == "o15"
    assert s.reverse_pick(odds(o15=1.17, o25=1.45)) == "o25"
    assert s.reverse_pick(odds(o15=1.17, o25=1.55)) is None
    assert s.reverse_pick(odds(o15=1.30, o25=1.90)) is None


# ---------------------------------------------------------------- Reverse U4.5 + Draw rule
def test_draw_rule_clear_favourite():
    assert s.draw_rule_pick(odds(home=1.40, draw=4.60, away=6.50)) == "home"
    assert s.draw_rule_pick(odds(home=1.15, draw=7.0, away=13.0, h_o15=1.35)) == "h_o15"
    assert s.draw_rule_pick(odds(home=6.0, draw=4.20, away=1.45)) == "away"
    assert s.draw_rule_pick(odds(home=1.40, draw=3.60, away=6.50)) is None   # draw not > 3.70


def test_draw_rule_balanced_over25_or_gg():
    assert s.draw_rule_pick(odds(home=2.40, draw=3.40, away=2.70, o25=1.45, gg=1.50)) == "o25"
    assert s.draw_rule_pick(odds(home=2.40, draw=3.40, away=2.70, o25=1.60, gg=1.42)) == "gg"
    assert s.draw_rule_pick(odds(home=2.40, draw=3.40, away=2.70, o25=1.60, gg=1.60)) is None
    assert s.draw_rule_pick(odds(home=1.90, draw=3.50, away=3.80, o25=1.40)) is None  # neither clear nor balanced


# ---------------------------------------------------------------- wiring
def test_sure80_slot_is_on_ticker_gate_watchdog_and_push():
    ticker = (ROOT / ".github/scripts/p2u_ticker.py").read_text()
    assert '("engine-sure80.yml", "0", "22", "*")' in ticker
    wf = (ROOT / ".github/workflows/engine-sure80.yml").read_text()
    assert 'cron: "0 22 * * *"' in wf and "p2u_gate.py --at 22:00 --job sure80" in wf
    assert "p2u_push.sh main" in wf and "python -m engine.premium --lock" in wf
    assert re.search(r"^  sure80:\s*$", wf, re.M)
    watchdog = (ROOT / ".github/scripts/p2u_watchdog.py").read_text()
    assert 'wf="engine-sure80.yml", at="22:00", job="sure80"' in watchdog
    assert "80% Sure" in lib.PUBLIC_NAME["sure80"] and lib.PUBLIC_NAME["rev-u45"] and lib.PUBLIC_NAME["rev-u45-draw"]


def test_high_odds_push_merge_keeps_other_jobs_slips():
    import json
    sys.path.insert(0, str(ROOT))
    m = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(m)
    base = {"slips": [{"code": "OLD"}, {"code": "GONE"}]}
    ours = {"slips": [{"code": "MINE"}, {"code": "OLD"}, {"code": "GONE"}]}
    theirs = {"slips": [{"code": "DAILY"}, {"code": "OLD", "status": "won"}]}
    out = m.merge_high_odds(base, ours, theirs)
    assert [r["code"] for r in out["slips"]] == ["DAILY", "MINE", "OLD"]
    assert out["slips"][2]["status"] == "won"
    assert "\n" not in json.dumps(out, separators=(",", ":"))
    assert m.merge_slips([], [{"x": 1}], []) is None
