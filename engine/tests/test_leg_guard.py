import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "engine"))
sys.path.insert(0, str(ROOT / "engine" / "vendor"))
import leg_guard as g  # noqa: E402


def leg(kind, odds, eid="sr:match:1", **kw):
    spec, oid, sel = (("total=1.5", "12", "Over 1.5") if kind == "o15" else ("total=3.5", "13", "Under 3.5"))
    return dict(eventId=eid, marketId="18", specifier=spec, outcomeId=oid, odds=odds, selection=sel, market="Over/Under", match="A v B", **kw)


def prices(o15, u35):
    return lambda eid: {"o15": (o15, "12") if o15 else None, "u35": (u35, "13") if u35 else None}


def test_config_has_the_cap():
    cfg = json.loads((ROOT / "engine" / "leg_rules.json").read_text())
    assert cfg["o15_u35_cap"] == 1.39 and cfg["o15_u35_enabled"] is True
    assert g.config() == {"enabled": True, "cap": 1.39}


def test_over15_above_cap_swaps_to_under35():
    L = [leg("o15", 1.45)]
    g.enforce(L, "t", fetch=prices(1.45, 1.30))
    assert len(L) == 1 and L[0]["specifier"] == "total=3.5" and L[0]["outcomeId"] == "13"
    assert L[0]["odds"] == 1.30 and L[0]["selection"] == "Under 3.5" and "ruleSwap" in L[0]
    assert g.LOG[-1]["action"] == "swap"


def test_under35_above_cap_swaps_to_over15():
    L = [leg("u35", 1.50)]
    g.enforce(L, "t", fetch=prices(1.25, 1.50))
    assert L[0]["specifier"] == "total=1.5" and L[0]["outcomeId"] == "12" and L[0]["odds"] == 1.25 and L[0]["selection"] == "Over 1.5"


def test_both_above_cap_or_not_listed_drops():
    L = [leg("o15", 1.45, "e1"), leg("u35", 1.6, "e2")]
    g.enforce(L, "t", fetch=lambda eid: {"o15": (1.45, "12"), "u35": (1.42, "13")} if eid == "e1" else {"o15": None, "u35": (1.6, "13")})
    assert L == []
    assert [r["action"] for r in g.LOG[-2:]] == ["drop", "drop"]
    assert g.LOG[-1]["why"] == "replacement not listed"


def test_inside_cap_and_other_markets_untouched_without_fetch():
    def boom(eid):
        raise AssertionError("no fetch needed")
    other = dict(eventId="x", marketId="18", specifier="total=2.5", outcomeId="12", odds=1.8)
    L = [leg("o15", 1.39), leg("u35", 1.2), other, dict(eventId="y", marketId="1", outcomeId="1", odds=2.0)]
    g.enforce(L, "t", fetch=boom)
    assert len(L) == 4 and L[0]["specifier"] == "total=1.5" and L[2] is other


def test_never_swaps_back_and_bare_selections_are_priced_live():
    L = [leg("o15", 1.45)]
    g.enforce(L, "t", fetch=prices(1.45, 1.30))
    g.enforce(L, "t", fetch=prices(1.25, 1.45))  # even if prices flip, a swapped leg stays put
    assert L[0]["specifier"] == "total=3.5"
    sel = [{"eventId": "e", "marketId": "18", "specifier": "total=1.5", "outcomeId": "12"}]
    g.enforce(sel, "t", fetch=prices(1.5, 1.33))
    assert sel[0]["specifier"] == "total=3.5" and sel[0]["outcomeId"] == "13"


def test_wired_into_every_booking_path():
    src = lambda p: (ROOT / p).read_text()  # noqa: E731
    assert 'leg_guard.enforce(selections, "sb_share_helper17.book")' in src("engine/sb_share_helper17.py")
    assert '"bookers.book_all")' in src("engine/bookers.py")
    lib = src("engine/vendor/strategy_lib.py")
    for where in ("strategy_lib.book_sportybet", "strategy_lib.book_confirmed", "strategy_lib.pack_slip", "strategy_lib.chunk_bookable"):
        assert where in lib
    assert 'enforce(legs, f"sure80:{kind}")' in src("engine/vendor/sure80_reverse.py")
    mp = src("engine/vendor/master_pipeline.py")
    assert mp.index("u45_to_overs(name") < mp.index('guard.enforce(final, "master_pipeline")') < mp.index("codes, skipped = outputs(final)")
    assert '"hs_goals.book_verified"' in src("engine/vendor/hs_goals.py")
    assert "5.10" in src("HANDOFF.md") and "Over 1.5" in src("HANDOFF.md")


def test_high_scoring_band_is_unaffected():
    cfg = json.loads((ROOT / "engine" / "hs_goals.json").read_text())
    assert cfg["o15_max"] <= g.config()["cap"]
