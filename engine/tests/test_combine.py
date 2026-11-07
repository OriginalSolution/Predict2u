import datetime as dt
from engine.combine import (
    dedupe_one_per_game, filter_legs, is_started, pack_slips, process, product,
)


def _p(**kw):
    base = dict(
        match="Alpha v Beta", league="Test - League", market="Both teams to score",
        selection="Yes", odds=1.22, eventId="sr:match:1", marketId="29", specifier="",
        outcomeId="74", table="6 v 12/20", x12="1.75/3.50/5.00",
        case="table 6 v 12/20; 1X2 1.75/3.50/5.00", kickoff="2026-11-07T18:00:00+00:00",
    )
    base.update(kw)
    return base


def test_product_and_pack_reaches_floor():
    legs = [_p(eventId=f"sr:match:{i}", odds=2.0, kickoff=f"2026-11-07T{10+i:02d}:00:00+00:00") for i in range(10)]
    slips = pack_slips(legs, min_odds=25)
    assert slips
    assert all(s["odds"] >= 25 for s in slips)
    used = sum(len(s["legs"]) for s in slips)
    assert used == 10


def test_remainder_under_floor_is_merged_not_dropped():
    # 1.5^8 ~= 25.63; two leftover legs would be 2.25 alone and must be merged.
    legs = [_p(eventId=f"sr:match:{i}", odds=1.5, kickoff=f"2026-11-07T{10+i:02d}:00:00+00:00") for i in range(10)]
    slips = pack_slips(legs, min_odds=25)
    assert len(slips) == 1
    assert len(slips[0]["legs"]) == 10
    assert slips[0]["meetsFloor"] is True


def test_single_short_group_is_kept():
    legs = [_p(odds=1.4), _p(eventId="sr:match:2", odds=1.4)]
    slips = pack_slips(legs, min_odds=25)
    assert len(slips) == 1
    assert slips[0]["meetsFloor"] is False
    assert product(slips[0]["legs"]) == 1.96


def test_dedupe_keeps_one_market_per_game():
    a = _p(selection="Yes", odds=1.22)
    b = _p(market="1X2", selection="Home", marketId="1", outcomeId="1", odds=1.40)
    kept, dropped = dedupe_one_per_game([a, a, b])
    assert len(kept) == 1
    assert kept[0]["selection"] == "Yes"  # more copies
    assert any(d["reason"].startswith("duplicate") for d in dropped)


def test_filter_drops_dc_ng_and_started():
    now = dt.datetime(2026, 11, 6, 12, 0, tzinfo=dt.timezone.utc)
    dc = _p(market="Double chance", selection="12", marketId="10", outcomeId="10", odds=1.10)
    ng = _p(selection="No", market="GG/NG", marketId="29", outcomeId="76")
    started = _p(eventId="sr:match:9", kickoff="2026-11-06T11:00:00+00:00")
    ok = _p(eventId="sr:match:8", kickoff="2026-11-06T18:00:00+00:00")
    kept, dropped = filter_legs([dc, ng, started, ok], now=now, enrich=False)
    reasons = {d["reason"] for d in dropped}
    assert "double-chance-veto" in reasons
    assert "btts-no-veto" in reasons
    assert "started" in reasons
    assert len(kept) == 1
    assert kept[0]["eventId"] == "sr:match:8"


def test_is_started_numeric_ts():
    now = dt.datetime(2026, 11, 6, 12, 0, tzinfo=dt.timezone.utc)
    assert is_started({"ts": dt.datetime(2026, 11, 6, 11, 0, tzinfo=dt.timezone.utc).timestamp() * 1000}, now=now)
    assert not is_started({"ts": dt.datetime(2026, 11, 6, 13, 0, tzinfo=dt.timezone.utc).timestamp() * 1000}, now=now)


def test_process_combines_short_inbox_slips():
    # Pin "now" before the earliest kickoff so this does not flake after ~10:00 UTC.
    now = dt.datetime(2026, 11, 7, 8, 0, tzinfo=dt.timezone.utc)
    picks = [_p(eventId=f"sr:match:{i}", odds=1.4, kickoff=f"2026-11-07T{10+i:02d}:00:00+00:00") for i in range(12)]
    # 1.4^12 ~= 56.7
    report = process(picks, now=now, enrich=False, min_odds=25)
    assert report["slips"]
    assert all(s["odds"] >= 25 for s in report["slips"])
    assert len(report["used"]) == 12
