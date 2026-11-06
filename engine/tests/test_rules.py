import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from engine.rules import check, classify, is_double_chance, is_btts_no, filter_picks


def pick(**kw):
    base = dict(match="Alpha v Beta", league="Test - League", market="1X2", selection="Alpha",
                odds=1.25, eventId="sr:match:1", marketId="1", specifier="", outcomeId="1",
                table="8 v 12/20", x12="1.40/4.00/8.00", case="table 8 v 12/20; 1X2 1.40/4.00/8.00")
    base.update(kw)
    return base


def test_double_chance_hard_veto():
    p = pick(market="Double chance", selection="1X", marketId="10", outcomeId="9")
    assert is_double_chance(p)
    ok, cls, why = check(p)
    assert not ok
    assert cls == "double-chance-veto"


def test_dc_text_only_veto():
    p = pick(market="", selection="Home or Draw", marketId="", outcomeId="")
    assert is_double_chance(p)


def test_skip_top5_v_top5():
    p = pick(table="2 v 4/18", case="table 2 v 4/18; 1X2 1.40/4.00/8.00")
    ok, cls, why = check(p)
    assert not ok and cls == "skip"


def test_skip_bottom3_v_bottom3():
    p = pick(table="17 v 18/18", case="table 17 v 18/18; 1X2 2.10/3.20/3.40")
    ok, cls, why = check(p)
    assert not ok and cls == "skip"


def test_middle_allows_gg_only():
    # fav ~1.75 and small table gap -> middle
    p = pick(selection="Yes", market="Both teams to score", marketId="29", specifier="", outcomeId="74",
             odds=1.22, table="6 v 12/20", x12="1.75/3.50/5.00",
             case="table 6 v 12/20; 1X2 1.75/3.50/5.00")
    cls, why = classify(p)
    assert cls == "middle"
    ok, cls, why = check(p)
    assert ok


def test_middle_rejects_home_win():
    p = pick(table="6 v 12/20", x12="1.75/3.50/5.00", case="table 6 v 12/20; 1X2 1.75/3.50/5.00")
    ok, cls, why = check(p)
    assert not ok and cls == "middle"


def test_even_rejects_over15():
    p = pick(selection="Over 1.5", market="Total goals", marketId="18", specifier="total=1.5", outcomeId="12",
             odds=1.22, table="9 v 10/20", x12="2.10/3.20/3.40",
             case="table 9 v 10/20; 1X2 2.10/3.20/3.40")
    ok, cls, why = check(p)
    assert not ok and cls == "even"


def test_mismatch_rejects_straight_win():
    p = pick(table="1 v 16/20", x12="1.25/5.50/12.00", case="table 1 v 16/20; 1X2 1.25/5.50/12.00")
    ok, cls, why = check(p)
    assert not ok and cls == "mismatch"


def test_filter_strips_dc():
    kept = filter_picks([
        pick(market="Double chance", selection="X2", marketId="10", outcomeId="11"),
        pick(selection="Yes", market="Both teams to score", marketId="29", specifier="", outcomeId="74",
             odds=1.22, table="6 v 12/20", x12="1.75/3.50/5.00",
             case="table 6 v 12/20; 1X2 1.75/3.50/5.00"),
    ])
    assert len(kept) == 1
    assert kept[0]["marketId"] == "29"


def test_btts_no_hard_veto():
    p = pick(selection="No", market="GG/NG", marketId="29", specifier="", outcomeId="76",
             odds=1.24, table="7 v 18/18", x12="1.46/3.20/9.70",
             case="table 7 v 18/18; 1X2 1.46/3.20/9.70")
    assert is_btts_no(p)
    ok, cls, why = check(p)
    assert not ok and cls == "btts-no-veto"


def test_btts_yes_not_vetoed_as_ng():
    p = pick(selection="Yes", market="GG/NG", marketId="29", specifier="", outcomeId="74",
             odds=1.22, table="7 v 18/18", x12="1.46/3.20/9.70",
             case="table 7 v 18/18; 1X2 1.46/3.20/9.70")
    assert not is_btts_no(p)


def test_filter_strips_ng():
    kept = filter_picks([
        pick(selection="No", market="Both teams to score", marketId="29", specifier="", outcomeId="76",
             odds=1.24, table="7 v 18/18", x12="1.46/3.20/9.70",
             case="table 7 v 18/18; 1X2 1.46/3.20/9.70"),
        pick(selection="Yes", market="Both teams to score", marketId="29", specifier="", outcomeId="74",
             odds=1.22, table="6 v 12/20", x12="1.75/3.50/5.00",
             case="table 6 v 12/20; 1X2 1.75/3.50/5.00"),
    ])
    assert len(kept) == 1
    assert kept[0]["outcomeId"] == "74"
