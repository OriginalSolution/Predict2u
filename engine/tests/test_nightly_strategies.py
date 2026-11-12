"""Nightly GG / NYSM v2 / NerdyTips Tomorrow / master. No network."""
import datetime as dt
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
import sys
sys.path[:0] = [str(ROOT / "engine" / "vendor"), str(ROOT / "engine"), str(ROOT)]

import gg_strategy as gg
import nysm_v2 as nysm
import nt_tomorrow as nt
import strategy_lib as lib
import strategy_master as master
from engine.settle_codes import grade


def _prices(**kw):
    base = {
        "29||Yes": [1.48, "74"],
        "18|total=2.5|Over 2.5": [1.64, "12"],
        "18|total=1.5|Over 1.5": [1.18, "12"],
        "1||Home": [2.10, "1"],
        "1||Draw": [3.70, "2"],
        "1||Away": [3.40, "3"],
    }
    base.update(kw)
    return base


def test_gg_odds_window():
    assert gg.odds_pass(_prices())["gg"] == 1.48
    assert gg.odds_pass(_prices(**{"29||Yes": [1.70, "74"]})) is None
    assert gg.odds_pass(_prices(**{"18|total=2.5|Over 2.5": [1.50, "12"]})) is None
    assert gg.odds_pass(_prices(**{"1||Draw": [3.40, "2"]})) is None
    assert gg.odds_pass(_prices(**{"18|total=1.5|Over 1.5": [1.25, "12"]})) is None


def test_league_tier_bands():
    assert gg.league_tier((40, 120, 20))["tier"] == "high"  # 3.00 goals per match
    assert gg.league_tier((40, 100, 10))["tier"] == "low"   # 2.50 is the low ceiling
    assert gg.league_tier((40, 108, 16))["tier"] == "mid"   # 2.70
    # Early season blends toward the previous season.
    blended = gg.league_tier((10, 20, 4), (60, 180, 40))
    assert blended["tier"] == "high"


def _row(**kw):
    row = dict(
        home="Alpha", away="Beta", country="England", league="League Two",
        home_odds=2.05, away_odds=3.40, draw=3.70, fav=2.05, tier="mid",
        home_n=10, away_n=10, home_gpg=1.6, away_gpg=1.5,
        home_pos=(8, 24, "League"), away_pos=(14, 24, "League"),
        away_fav=False, other_codes=0, gg=1.48, gg_outcome_id="74", event_id="sr:match:1",
    )
    row.update(kw)
    return row


def test_gg_filter_keeps_a_clean_mid_tier_row():
    out = gg.filter_rows([_row()], lambda row: [4, 5])
    assert len(out["keep"]) == 1
    assert out["keep"][0]["scored5"] == [4, 5]


@pytest.mark.parametrize("patch,reason", [
    ({"home": "Alpha Women"}, "women"),
    ({"tier": "high"}, "high-scoring"),
    ({"tier": "low"}, "low-scoring"),
    ({"tier": "unknown"}, "no stats"),
    ({"home_odds": 1.40, "away_odds": 6.0}, "always-exclude"),
    ({"home_pos": (2, 20, "L"), "away_pos": (4, 20, "L")}, "top-5"),
    ({"home_pos": (18, 20, "L"), "away_pos": (19, 20, "L")}, "bottom-3"),
    ({"away_fav": True, "home_odds": 3.2, "away_odds": 2.0}, "away favourite"),
    ({"home_pos": (8, 24, "A"), "away_pos": (14, 24, "B")}, "table unchecked"),
    ({"home_n": 5}, "<8"),
    ({"home_gpg": 1.0}, "1.3"),
    ({"other_codes": 2}, "2 other"),
])
def test_gg_filter_drops(patch, reason):
    out = gg.filter_rows([_row(**patch)], lambda row: [4, 4])
    assert out["keep"] == [], reason
    assert out["removed"], reason


def test_gg_filter_needs_four_of_last_five_scoring():
    out = gg.filter_rows([_row()], lambda row: [3, 5])
    assert out["keep"] == []
    assert "both-score" in next(iter(out["removed"]))


def test_pack_refuses_short_tickets_and_does_not_pad():
    short = [{"eventId": "a", "odds": 1.40, "selection": "Yes", "marketId": "29"}]
    kept, why = lib.pack_slip(short)
    assert kept == [] and "under" in why
    long = [{"eventId": str(i), "odds": 1.20, "selection": "Over 1.5", "marketId": "18"} for i in range(60)]
    parts = lib.chunk_bookable(long)
    assert len(parts) == 1 and len(parts[0]) == 50
    assert lib.product(leg["odds"] for leg in parts[0]) >= 25
    # The leftover 10 legs are under 25 and are not padded into a second code.


def test_pack_drops_ng_and_dc12_without_flipping():
    legs = [
        {"eventId": "a", "odds": 1.50, "selection": "No", "marketId": "29", "outcomeId": "76"},
        {"eventId": "b", "odds": 1.40, "selection": "Home or Away", "marketId": "10", "outcomeId": "10"},
    ]
    kept, why = lib.pack_slip(legs)
    assert kept == []
    assert "NG/DC 12" in why


def test_two_code_cap():
    usage = {"sr:match:1": ["A", "B"]}
    assert lib.can_take(usage, "sr:match:1") is False
    assert lib.take(usage, "sr:match:1", "C") is False
    assert lib.take(usage, "sr:match:2", "C") is True
    assert usage["sr:match:2"] == ["C"]


def _tree(**kw):
    row = dict(
        fo=1.35, sH=True, gap=0.8, fav=0.62, sDef=80, wAtt=50, sRaw=1.1, sg6=5,
        HA=130, HD=80, AA=50, AD=90, hd=1.1, ad=1.2, ldr=0.22, wdr=0.20,
        cls="Medium", mk={"O15": 0.5, "U35": 0.4},
        O={
            "1||Home": (1.35, "1"), "1||Away": (8.0, "3"), "1||Draw": (5.0, "2"),
            "18|total=1.5|Over 1.5": (1.22, "12"), "18|total=2.5|Over 2.5": (1.70, "12"),
            "18|total=3.5|Under 3.5": (1.28, "13"), "29||Yes": (1.55, "74"),
        },
        DNB={"Home": (1.15, "4"), "Away": (1.40, "5")},
        home="Alpha", away="Beta", women=False, top5=False, eid="sr:match:9",
    )
    row.update(kw)
    return row


def test_tree_short_favourite_versus_poor_attack():
    pick = nysm.tree_pick(_tree(fo=1.32, wAtt=60))
    assert pick["branch"].startswith("1 ")
    assert pick["selection"] == "Home"
    assert pick["market"] == "1X2"


def test_tree_elite_home_wins_and_elite_away_is_dnb():
    home = nysm.tree_pick(_tree(sDef=65, sg6=3, wAtt=80, fo=1.55, fav=0.60))
    assert home["branch"].startswith("2A") and home["market"] == "1X2"
    away = nysm.tree_pick(_tree(sH=False, sDef=65, sg6=3, wAtt=80, fo=1.55, fav=0.60, HA=70))
    assert "DNB" in away["branch"] and away["market"] == "Draw no bet"


def test_tree_messy_when_market_and_ppg_disagree():
    pick = nysm.tree_pick(_tree(fo=1.70, wAtt=80, fav=0.60, gap=-0.2, mk={"O15": 0.5, "U35": 0.5}))
    assert pick is None


def test_tree_close_both_attack_is_gg_unless_odds_filter():
    prices = {
        "1||Home": (2.20, "1"), "1||Away": (3.10, "3"), "1||Draw": (3.40, "2"),
        "18|total=1.5|Over 1.5": (1.22, "12"), "18|total=2.5|Over 2.5": (1.70, "12"),
        "18|total=3.5|Under 3.5": (1.28, "13"), "29||Yes": (1.55, "74"),
    }
    close = _tree(fav=0.42, gap=0.2, HA=90, AA=90, ldr=0.20, fo=2.20, O=prices, mk={"O15": 0.4, "U35": 0.4})
    pick = nysm.tree_pick(close)
    assert pick["branch"].startswith("3 ") and pick["key"] == "29||Yes"
    blocked_prices = {**prices, "1||Home": (1.45, "1")}
    blocked = _tree(fav=0.42, gap=0.2, HA=90, AA=90, ldr=0.20, fo=1.55, wAtt=80, O=blocked_prices, mk={"O15": 0.4, "U35": 0.4})
    assert nysm.tree_pick(blocked) is None


def test_tree_leaky_can_score_is_over_25_and_off_accumulator():
    pick = nysm.tree_pick(_tree(fav=0.60, sDef=120, sRaw=1.6, wAtt=90, sg6=6))
    assert pick["branch"].startswith("2C") and pick["key"].endswith("Over 2.5")
    assert nysm.slip_bucket(pick["branch"]) == "off"


def test_tree_fallback_and_womens_goals_dropped():
    pick = nysm.tree_pick(_tree(fo=1.80, wAtt=80, fav=0.50, gap=0.1, ldr=0.20, HA=70, AA=70, mk={"O15": 0.85, "U35": 0.4}))
    assert pick["branch"].startswith("5 ") and "O1.5" in pick["branch"]
    assert nysm.tree_pick(_tree(women=True, fo=1.32, wAtt=60))["market"] == "1X2"
    assert nysm.tree_pick(_tree(
        women=True, fo=2.20, wAtt=90, fav=0.42, gap=0.2, HA=90, AA=90, ldr=0.20,
        mk={"O15": 0.2, "U35": 0.2},
        O={
            "1||Home": (2.20, "1"), "1||Away": (3.10, "3"), "1||Draw": (3.40, "2"),
            "18|total=1.5|Over 1.5": (1.22, "12"), "18|total=2.5|Over 2.5": (1.70, "12"),
            "18|total=3.5|Under 3.5": (1.28, "13"), "29||Yes": (1.55, "74"),
        },
    )) is None


def test_tree_skips_top5_and_splits_main_from_conservative():
    assert nysm.tree_pick(_tree(top5=True, fo=1.32, wAtt=55)) is None
    short = nysm.tree_pick(_tree(eid="a", fo=1.32, wAtt=55))
    solid = nysm.tree_pick(_tree(eid="b", fav=0.60, sDef=90, wAtt=75, sg6=6, fo=1.70))
    slips = nysm.assign_slips([short, solid])
    assert [p["eid"] for p in slips["nysm-conservative"]] == ["a"]
    assert [p["eid"] for p in slips["nysm-main"]] == ["b"]
    assert nysm.slip_bucket(solid["branch"]) == "main"


def test_ts2_house_band_bar_and_league_cap():
    def row(eid, league, odds, bar, **kw):
        base = dict(
            eid=eid, match=f"H{eid} v A", league=league, home=f"H{eid}", away="A",
            HA=130, AA=100, HD=140, AD=140, hd=1.8, ad=1.8, nh=10, na=10,
            th={"SA": 120, "LD": 120, "RL": 1.40}, same=False, pos_gap=8,
            hpos=8, apos=16, N=20, women=False, youth=False, cup=False, both_elite=False,
            O={
                "1||Home": (1.70, "1"), "1||Away": (4.0, "3"),
                "19|total=1.5|Over 1.5": (odds, "12"),
            },
            bar={"home": (bar, 10)},
        )
        base.update(kw)
        return base
    kept = nysm.ts2_candidates([
        row("1", "Liga", 1.40, 0.80),
        row("2", "Liga", 1.35, 0.90),
        row("3", "Liga", 1.30, 0.90),  # third in the same league
        row("4", "Other", 1.10, 0.90),  # under the 1.20 band
        row("5", "Other", 1.40, 0.50),  # bar too low
        row("6", "Cup", 1.40, 0.80, cup=True),  # cup wants 85%
    ])
    assert [item["eid"] for item in kept] == ["3", "2"]


def test_nt_converts_1x2_and_keeps_only_agree_bookable():
    info = {
        "h": {"ppg": 2.1, "last5": "WWWWW", "gf": 1.8, "ga": 1.4},
        "a": {"ppg": 0.6, "last5": "LLLLL", "gf": 0.7, "ga": 1.6},
        "hh": {"ppg": 2.4, "gf": 1.6, "ga": 0.8},
        "aa": {"ppg": 0.4, "gf": 0.5, "ga": 1.8},
        "pos_h": {"pos": 2, "n": 16, "p": 10, "pts": 24, "tb": 0, "tbn": "League"},
        "pos_a": {"pos": 14, "n": 16, "p": 10, "pts": 8, "tb": 0, "tbn": "League"},
        "h2h": [],
    }
    row = {
        "m": "Alpha v Beta", "lg": "Some League", "trust": 8.0, "typ": "1X2", "fav": "H",
        "free": "", "xg": [1.6, 0.8], "l10": {"Over 1.5 Goals": [8, 8], "Both Teams Scored": [4, 4]},
        "warn": [], "women": False,
        "O": {
            "1||Home": [1.45, "1"], "1||Away": [6.0, "3"], "1||Draw": [4.2, "2"],
            "29||Yes": [1.48, "74"], "18|total=1.5|Over 1.5": [1.22, "12"],
        },
    }
    decided = nt.decide(dict(row), info)
    assert decided["conv"] is True
    assert decided["key"] in {"29||Yes", "18|total=1.5|Over 1.5"}
    assert decided["verdict"] in {"Agree", "Lean", "Disagree"}
    # Even games cannot keep Over 1.5.
    even = dict(row, O={**row["O"], "1||Home": [2.10, "1"], "1||Away": [2.20, "3"]})
    even_info = {
        "h": {"ppg": 1.4, "last5": "WDLWD", "gf": 1.2, "ga": 1.1},
        "a": {"ppg": 1.3, "last5": "DWLWD", "gf": 1.1, "ga": 1.2},
        "hh": {"ppg": 1.4, "gf": 1.1, "ga": 1.0}, "aa": {"ppg": 1.3, "gf": 1.0, "ga": 1.1},
        "pos_h": {"pos": 8, "n": 16, "p": 10, "pts": 14, "tb": 0, "tbn": "League"},
        "pos_a": {"pos": 9, "n": 16, "p": 10, "pts": 13, "tb": 0, "tbn": "League"},
        "h2h": [],
    }
    even_decided = nt.decide(dict(even, typ="Goals", xg=[1.4, 1.2], fav="H"), even_info)
    if even_decided.get("cls") == "even":
        assert even_decided.get("key") != "18|total=1.5|Over 1.5"


def test_nt_forensics_drop_flagged_and_unchecked_and_gg_cap():
    row = {"verdict": "Agree", "m": "Alpha v Beta", "od": 1.60, "key": "29||Yes", "tab": True, "check": "", "warn": []}
    assert "1.50" in nt.book_filters(dict(row), 0)["skipwhy"]
    flagged = dict(row, od=1.40, check="note [SB favourite differs from NT pick]")
    assert nt.book_filters(flagged, 0)["skipwhy"].startswith("flagged")
    unchecked = dict(row, od=1.40, tab=False, check="")
    assert nt.book_filters(unchecked, 0)["skipwhy"] == "table unchecked"
    warned = dict(row, od=1.40, warn=["late team news"])
    assert "warning" in nt.book_filters(warned, 0)["skipwhy"]
    crowded = dict(row, od=1.40)
    assert "2 other" in nt.book_filters(crowded, 2)["skipwhy"]


def test_master_swaps_ng_does_not_flip_and_skips_a_full_match():
    gg_leg = {"eventId": "m1", "selection": "Yes", "marketId": "29", "odds": 1.45, "match": "A v B", "kickoff": "2026-11-13T15:00:00Z"}
    ng_leg = {"eventId": "m1", "selection": "No", "marketId": "29", "outcomeId": "76", "odds": 1.40, "match": "A v B"}
    only_ng = {"eventId": "m2", "selection": "No", "marketId": "29", "outcomeId": "76", "odds": 1.30, "match": "C v D"}
    dc = {"eventId": "m3", "selection": "Home or Away", "marketId": "10", "outcomeId": "10", "odds": 1.25, "match": "E v F"}
    third = {"eventId": "m4", "selection": "Over 1.5", "marketId": "18", "odds": 1.22, "match": "G v H", "kickoff": "2026-11-13T18:00:00Z"}
    usage = {"m4": ["code-a", "code-b"]}
    chosen = master.choose([ng_leg, gg_leg, only_ng, dc, third], usage)
    assert [leg["eventId"] for leg in chosen] == ["m1"]
    assert chosen[0]["selection"] == "Yes"
    assert ng_leg["selection"] == "No"  # not rewritten into GG
    packed, why = lib.pack_slip(chosen)
    assert packed == [] and "under" in why


def test_master_books_when_the_product_clears_25():
    legs = [
        {"eventId": f"e{i}", "selection": "Over 1.5", "marketId": "18", "odds": 1.25,
         "match": f"H{i} v A{i}", "kickoff": f"2026-11-13T{10+i:02d}:00:00Z"}
        for i in range(16)
    ]
    chosen = master.choose(legs, {})
    packed, why = lib.pack_slip(chosen)
    assert why is None and len(packed) == 16
    assert lib.product(leg["odds"] for leg in packed) >= 25


def test_grade_draw_no_bet_and_gg():
    final = {"final": True, "score": "1:1"}
    assert grade("Home", "Alpha v Beta", final, {"market": "Draw no bet", "marketId": "11"}) == "void"
    assert grade("Home", "Alpha v Beta", {"final": True, "score": "2:0"}, {"market": "Draw no bet", "marketId": "11"}) == "won"
    assert grade("Yes", "Alpha v Beta", final) == "won"
    assert grade("No", "Alpha v Beta", final) == "lost"
    assert grade("Alpha over 1.5 goals", "Alpha v Beta", {"final": True, "score": "2:0"}) == "won"


def test_optional_gates_and_version_files_stay_paired():
    cfg = json.loads((ROOT / "engine" / "config.json").read_text())
    opt = cfg["optional_gates"]
    assert opt["enabled"] is False
    for key in (
        "sportybet_gh_only", "min_odds_every_code", "gg_benched", "riddim_edge_legs_below_1_50",
        "max_codes_per_event", "drop_top5_v_top5_bottom3_v_bottom3", "max_tips_per_code_25", "per_league_own_history",
    ):
        assert opt[key] is False
    build = (ROOT / "BUILD_VERSION.txt").read_text().strip()
    sw = (ROOT / "sw.js").read_text()
    assert f"VERSION='{build}'" in sw
    assert f"CACHE_VERSION='predict2u-{build}'" in sw


def test_prune_keeps_strategy_spec_1x_and_still_drops_ng(tmp_path, monkeypatch):
    import importlib.util
    spec = importlib.util.spec_from_file_location("prune_live", ROOT / "engine" / "vendor" / "prune_live.py")
    pl = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(pl)
    future = (dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=1)).strftime("%Y-%m-%dT18:00:00Z")
    day = future[:10]
    base = {"status": "pending", "date": day, "code": "ABCDEF", "legs": [{
        "eventId": "sr:match:1", "marketId": "10", "selection": "Home or Draw", "odds": 1.50,
        "kickoff": future, "date": day, "league": "England - Premier League", "result": "pending",
    }]}
    assert pl.live_slip(dict(base)) is False
    kept = dict(base, strategySpec=True)
    assert pl.live_slip(kept) is True
    banned = dict(base, strategySpec=True, legs=[{
        "eventId": "sr:match:1", "marketId": "29", "selection": "No", "outcomeId": "76",
        "kickoff": future, "date": day, "result": "pending",
    }])
    assert pl.live_slip(banned) is False


def test_nightly_target_rolls_after_18utc():
    evening = dt.datetime(2026, 11, 12, 23, 10, tzinfo=dt.timezone.utc)
    morning = dt.datetime(2026, 11, 13, 6, 0, tzinfo=dt.timezone.utc)
    assert lib.nightly_target(evening) == dt.date(2026, 11, 13)
    assert lib.nightly_target(morning) == dt.date(2026, 11, 13)
    assert lib.nightly_target(evening, "2026-11-14") == dt.date(2026, 11, 14)


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


def test_strategy_publish_respects_free_codes(tmp_path, monkeypatch):
    """Odds above 25 stay public while p2u-free-mode.js is on, and get flagged when it is off."""
    monkeypatch.delenv("P2U_LOCK_KEY", raising=False)
    monkeypatch.setenv("PRIV_DIR", str(tmp_path / "private"))
    legs = [{"eventId": "sr:match:1", "odds": 1.4, "selection": "Yes", "date": "2026-11-13"}]
    slip = lib.public_slip("gg", "2026-11-13", "ABCDEF", legs, 40.0)

    monkeypatch.setenv("P2U_FREE_CODES", "1")
    (tmp_path / "p2u-free-mode.js").write_text("window.P2U_FREE_CODES = true;\n")
    lib.publish_high_odds(tmp_path, slip)
    raw = (tmp_path / "high_odds.json").read_text()
    assert "\n" not in raw.strip()
    row = json.loads(raw)["slips"][0]
    assert row["code"] == "ABCDEF" and row["codes"]["sportybet"]["code"] == "ABCDEF"
    assert "premium" not in row and "locked" not in row

    monkeypatch.setenv("P2U_FREE_CODES", "0")
    (tmp_path / "p2u-free-mode.js").write_text("window.P2U_FREE_CODES = false;\n")
    paid = lib.public_slip("gg", "2026-11-13", "ABCDEF", legs, 40.0)
    lib.publish_high_odds(tmp_path, paid)
    raw = (tmp_path / "high_odds.json").read_text()
    assert "\n" not in raw.strip()
    row = json.loads(raw)["slips"][0]
    assert row["premium"] is True and row["code"] == "ABCDEF"


def test_strategy_jobs_use_the_ticker_gate_and_push_retry():
    ticker = (ROOT / ".github" / "scripts" / "p2u_ticker.py").read_text()
    jobs = (
        ("engine-gg.yml", "10", "23", "23:10", "gg"),
        ("engine-nysm.yml", "30", "23", "23:30", "nysm"),
        ("engine-nt-tomorrow.yml", "50", "23", "23:50", "nt"),
        ("engine-strategy-master.yml", "0", "6", "06:00", "master"),
    )
    for name, minute, hour, at, job in jobs:
        assert f'("{name}", "{minute}", "{hour}", "*")' in ticker
        text = (ROOT / ".github" / "workflows" / name).read_text()
        assert f'p2u_gate.py --at {at} --job {job}' in text
        assert "p2u_push.sh main" in text
        assert "python -m engine.premium --lock" in text
        assert "engine.premium --is-free" in text
        assert "P2U_LOCK_KEY" in text
    assert 'cron: "10 23 * * *"' in (ROOT / ".github" / "workflows" / "engine-gg.yml").read_text()
    assert 'cron: "30 23 * * *"' in (ROOT / ".github" / "workflows" / "engine-nysm.yml").read_text()
    assert 'cron: "50 23 * * *"' in (ROOT / ".github" / "workflows" / "engine-nt-tomorrow.yml").read_text()
    assert 'cron: "0 6 * * *"' in (ROOT / ".github" / "workflows" / "engine-strategy-master.yml").read_text()


def _short_legs(n, odds, prefix="e"):
    return [
        {"eventId": f"{prefix}{i}", "selection": "Over 1.5", "marketId": "18", "odds": odds,
         "match": f"H{i} v A{i}", "kickoff": f"2026-11-13T{10 + (i % 10):02d}:00:00Z"}
        for i in range(n)
    ]


def test_thin_day_uses_the_normal_ticket_first():
    normal = _short_legs(16, 1.25)
    wider = normal + [{"eventId": "cheap", "selection": "Yes", "marketId": "29", "odds": 1.05}]
    packed, why, used = lib.thin_pack(normal, wider)
    assert used is False and why is None
    assert [leg["eventId"] for leg in packed] == [leg["eventId"] for leg in normal]
    assert lib.product(leg["odds"] for leg in packed) >= 25


def test_thin_day_relaxes_only_when_the_ticket_is_short():
    short = _short_legs(8, 1.40)
    extra = _short_legs(8, 1.45, prefix="x")
    assert lib.pack_slip(short)[0] == []
    packed, why, used = lib.thin_pack(short, short + extra)
    assert used is True and why is None
    assert len(packed) == 16 and lib.product(leg["odds"] for leg in packed) >= 25
    slip = lib.public_slip("gg", "2026-11-13", "ABCDEF", packed, 40.0, relaxed=True)
    assert slip["relaxed"] is True and "Relaxed" in slip["name"]
    assert slip["highRisk"] is True and slip["riskLabel"] == "HIGH RISK"
    plain = lib.public_slip("gg", "2026-11-13", "ABCDEF", packed, 40.0)
    assert "relaxed" not in plain and "Relaxed" not in plain["name"]


def test_thin_day_still_blocks_ng_dc12_short_tickets_and_a_third_code():
    clean = _short_legs(4, 1.30)
    ng = {"eventId": "ng", "selection": "No", "marketId": "29", "outcomeId": "76", "odds": 8.0}
    dc = {"eventId": "dc", "selection": "Home or Away", "marketId": "10", "outcomeId": "10", "odds": 8.0}
    packed, _why, used = lib.thin_pack([], clean + [ng, dc])
    assert packed == [] and used is False
    assert ng["selection"] == "No"
    usage = {"full": ["code-a", "code-b"]}
    pooled = master.choose_pooled(clean + [ng, dc, {"eventId": "full", "selection": "Over 1.5", "marketId": "18", "odds": 1.40}], usage)
    assert [leg["eventId"] for leg in pooled] == [leg["eventId"] for leg in clean]
    assert all(not lib.absolute_ban(leg) for leg in pooled)


def test_gg_thin_day_opens_the_gg_band_and_an_unchecked_table_only():
    assert gg.odds_pass(_prices(**{"29||Yes": [1.10, "74"]})) is None
    assert gg.odds_pass(_prices(**{"29||Yes": [1.80, "74"]})) is None
    assert gg.odds_pass(_prices(**{"29||Yes": [1.10, "74"]}), relaxed=True)["gg"] == 1.10
    assert gg.odds_pass(_prices(**{"29||Yes": [1.80, "74"]}), relaxed=True)["gg"] == 1.80
    assert gg.odds_pass(_prices(**{"29||Yes": [1.80, "74"], "1||Draw": [3.40, "2"]}), relaxed=True) is None
    unchecked = _row(home_pos=(8, 24, "A"), away_pos=(14, 24, "B"))
    assert gg.filter_rows([unchecked], lambda row: [4, 5])["keep"] == []
    assert len(gg.filter_rows([unchecked], lambda row: [4, 5], relaxed=True)["keep"]) == 1
    top = _row(home_pos=(2, 20, "L"), away_pos=(4, 20, "L"))
    assert gg.filter_rows([top], lambda row: [4, 5], relaxed=True)["keep"] == []
    crowded = _row(other_codes=2)
    assert gg.filter_rows([crowded], lambda row: [4, 5], relaxed=True)["keep"] == []


def test_nt_thin_day_keeps_lean_warnings_unchecked_tables_and_the_hard_drops():
    base = {"verdict": "Agree", "m": "Alpha v Beta", "od": 1.40, "key": "29||Yes", "tab": True, "check": "", "warn": [], "eid": "m1", "trust": 6}
    lean = dict(base, verdict="Lean")
    assert nt.eligible_rows([lean], {}) == []
    assert nt.eligible_rows([lean], {}, relaxed=True)[0]["verdict"] == "Lean"
    warned = dict(base, warn=["late team news"])
    assert "warning" in nt.book_filters(dict(warned), 0)["skipwhy"]
    assert nt.book_filters(dict(warned), 0, relaxed=True)["verdict"] == "Agree"
    unchecked = dict(base, tab=False)
    assert nt.book_filters(dict(unchecked), 0)["skipwhy"] == "table unchecked"
    assert nt.book_filters(dict(unchecked), 0, relaxed=True)["verdict"] == "Agree"
    below = dict(base, od=1.10)
    assert "1.20" in nt.book_filters(dict(below), 0)["skipwhy"]
    assert nt.book_filters(dict(below), 0, relaxed=True)["verdict"] == "Agree"
    above_cap = dict(base, od=1.60)
    assert "1.50" in nt.book_filters(dict(above_cap), 0)["skipwhy"]
    assert nt.book_filters(dict(above_cap), 0, relaxed=True)["verdict"] == "Agree"
    too_high = dict(base, od=1.90)
    assert "1.75" in nt.book_filters(dict(too_high), 0, relaxed=True)["skipwhy"]
    crowded = dict(base)
    assert "2 other" in nt.book_filters(dict(crowded), 2, relaxed=True)["skipwhy"]


def test_ts2_thin_day_drops_only_the_floor():
    def row(eid, odds):
        return dict(
            eid=eid, match=f"H{eid} v A", league="Other", home=f"H{eid}", away="A",
            HA=130, AA=100, HD=140, AD=140, hd=1.8, ad=1.8, nh=10, na=10,
            th={"SA": 120, "LD": 120, "RL": 1.40}, same=False, pos_gap=8,
            hpos=8, apos=16, N=20, women=False, youth=False, cup=False, both_elite=False,
            O={"1||Home": (1.70, "1"), "1||Away": (4.0, "3"), "19|total=1.5|Over 1.5": (odds, "12")},
            bar={"home": (0.90, 10)},
        )
    assert nysm.ts2_candidates([row("4", 1.10)]) == []
    assert [item["eid"] for item in nysm.ts2_candidates([row("4", 1.10)], relaxed=True)] == ["4"]
    assert nysm.ts2_candidates([row("9", 1.80)], relaxed=True) == []


def test_unverified_table_stays_a_goals_fallback():
    event = {
        "eventId": "sr:match:1", "homeTeamName": "Alpha", "awayTeamName": "Beta",
        "sport": {"category": {"name": "England", "tournament": {"name": "League Two"}}},
    }
    prices = {
        "1||Home": [2.10, "1"], "1||Draw": [3.40, "2"], "1||Away": [3.20, "3"],
        "18|total=1.5|Over 1.5": [1.15, "12"], "18|total=1.5|Under 1.5": [5.50, "13"],
    }
    assert nysm.model_match(event, [], None, None, {}, prices) is None
    pick = nysm.tree_pick(nysm.unverified_price_row(event, prices))
    assert pick["key"].startswith("18|") and pick["selection"] == "Over 1.5"
    assert pick["tableChecked"] is False


def test_master_pools_across_strategies_only_on_a_thin_day():
    booked = _short_legs(16, 1.25, prefix="a")
    packed, _why, used = lib.thin_pack(master.choose(booked, {}), booked + _short_legs(4, 1.10, prefix="z"))
    assert used is False and len(packed) == 16
    short = _short_legs(8, 1.40, prefix="b")
    second = [
        {"eventId": f"b{i}", "selection": "Yes", "marketId": "29", "odds": 1.40, "match": f"H{i} v A{i}"}
        for i in range(8)
    ]
    one_each = master.choose(short, {})
    pooled = master.choose_pooled(short + second, {})
    packed, _why, used = lib.thin_pack(one_each, pooled)
    assert used is True and len(packed) == 16
    assert lib.product(leg["odds"] for leg in packed) >= 25
    ng = {"eventId": "b0", "selection": "No", "marketId": "29", "outcomeId": "76", "odds": 1.40}
    again = master.choose_pooled(short + [ng], {})
    assert all(leg["selection"] != "No" for leg in again)
    assert ng["selection"] == "No"
