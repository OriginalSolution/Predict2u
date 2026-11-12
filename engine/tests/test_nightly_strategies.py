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
