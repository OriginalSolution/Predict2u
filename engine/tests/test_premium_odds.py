"""Total odds above 25 flag a booking code as premium / locked."""
from engine.premium import (
    CURRENCY,
    PRICE,
    ID_RE,
    flag_slip,
    is_premium_odds,
    lock_id,
    seal_slip,
)


def _slip(**kw):
    base = dict(
        name="DC Shield Goals",
        date="2026-11-12",
        risk="safe",
        totalOdds=26,
        code="SECRET1",
        codes={"sportybet": "SECRET1", "msport": "SECRET2"},
        links={"sportybet": "https://www.sportybet.com/gh/?shareCode=SECRET1"},
        legs=[
            {"match": "Alpha v Beta", "selection": "Over 1.5", "odds": 1.3, "league": "Test"},
            {"match": "Gamma v Delta", "selection": "Under 3.5", "odds": 1.25, "league": "Test"},
        ],
    )
    base.update(kw)
    return base


def test_odds_above_25_are_premium():
    assert is_premium_odds(25.01) is True
    assert is_premium_odds(26) is True
    assert is_premium_odds("40.5") is True
    assert is_premium_odds(766.97) is True


def test_odds_at_or_under_25_stay_free():
    assert is_premium_odds(25) is False
    assert is_premium_odds(25.0) is False
    assert is_premium_odds(24.99) is False
    assert is_premium_odds(0) is False
    assert is_premium_odds(None) is False
    assert is_premium_odds("n/a") is False
    assert is_premium_odds(True) is False


def test_flag_sets_premium_and_paywall_fields():
    slip = flag_slip(_slip())
    assert slip["premium"] is True
    assert slip["locked"]["price"] == PRICE == 50
    assert slip["locked"]["currency"] == CURRENCY == "GHS"
    assert slip["locked"]["odds"] == 26
    assert slip["locked"]["legs"] == 2
    assert ID_RE.fullmatch(slip["locked"]["id"])
    assert slip["locked"]["id"] == "hot-20261112"
    # flagging does not hide anything by itself
    assert slip["code"] == "SECRET1"
    assert slip["legs"][0]["match"] == "Alpha v Beta"


def test_leg_date_aligns_home_and_bankers_copies():
    legs = [{"date": "2026-11-13", "match": "Alpha v Beta", "selection": "Over 1.5", "odds": 1.2}]
    home = _slip(date=None, targetDate="2026-11-13", legs=legs)
    bankers = _slip(date="2026-11-12", legs=legs)
    assert lock_id(home) == lock_id(bankers) == "hot-20261113"


def test_exact_25_is_not_flagged_premium():
    slip = flag_slip(_slip(totalOdds=25, name="Medium slip", risk="medium"))
    assert slip["premium"] is False
    assert "locked" not in slip
    assert lock_id(_slip(totalOdds=25, name="Medium slip", risk="medium")) == "medium-20261112"


def test_banker_and_verzzify_use_banker_id():
    assert lock_id(_slip(name="Main banker: code of the day", banker=True)) == "banker-20261112"
    assert lock_id(_slip(name="Main · Verzzify Edge Banker", verzzify=True)) == "banker-20261112"
    assert lock_id(_slip(name="Code of the Day", dailyMaster=True, origin="daily-master")) == "banker-20261112"


def test_seal_removes_code_and_picks_from_the_public_slip():
    store = {}

    def placeholder(lid, book, n):
        return f"P2ULOCK-{lid}-{book}{n}"

    slip = _slip(totalOdds=25.01)
    assert seal_slip(slip, store, placeholder) is True
    public = str(slip)
    assert "SECRET1" not in public
    assert "SECRET2" not in public
    assert "Alpha v Beta" not in public
    assert "Gamma v Delta" not in public
    assert "Over 1.5" not in public
    assert slip["premium"] is True
    assert slip["legs"] == []
    assert slip["legCount"] == 2
    assert slip["locked"]["legs"] == 2
    assert slip["locked"]["price"] == 50
    assert slip["codes"]["sportybet"].startswith("P2ULOCK-hot-20261112-sportybet")
    assert slip["links"]["sportybet"] == ""
    saved = store["hot-20261112"]["codes"]["sportybet"][0]
    assert saved["code"] == "SECRET1"
    assert saved["picks"][0]["match"] == "Alpha v Beta"
    assert saved["slipKey"]
    # a second seal must not duplicate the stored code
    again = _slip(totalOdds=30)
    seal_slip(again, store, placeholder)
    assert len(store["hot-20261112"]["codes"]["sportybet"]) == 1


def test_seal_leaves_odds_at_25_readable():
    store = {}
    slip = _slip(totalOdds=25, code="FREE25", codes={"sportybet": "FREE25"})
    assert seal_slip(slip, store, lambda i, b, n: f"P2ULOCK-{i}-{b}{n}") is False
    assert slip["premium"] is False
    assert slip["code"] == "FREE25"
    assert slip["legs"][0]["match"] == "Alpha v Beta"
    assert store == {}
