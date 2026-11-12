"""Total odds above 25 flag a booking code as premium / locked."""
from engine.premium import (
    CURRENCY,
    PRICE,
    ID_RE,
    flag_slip,
    is_premium_odds,
    lock_id,
    seal_document,
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


def _ph(lid, book, n):
    return f"P2ULOCK-{lid}-{book}{n}"


def _model(name, odds, code, picks):
    return {
        "name": name,
        "label": name,
        "strategy": "safe50",
        "date": "2026-11-12",
        "totalOdds": odds,
        "legs": len(picks),
        "picks": picks,
        "codes": {"sportybet": [{"code": code, "totalOdds": odds, "legs": len(picks), "link": "https://www.sportybet.com/gh/?shareCode=" + code}]},
    }


def test_model_slips_lock_master_and_parts_over_25_only():
    picks_hi = [{"match": "Alpha v Beta", "selection": "Over 1.5", "odds": 1.4, "date": "2026-11-12"}]
    picks_free = [{"match": "Free v Game", "selection": "Under 2.5", "odds": 1.22, "date": "2026-11-12"}]
    doc = {"modelSlips": [
        _model("Safest market", 40.2, "MASTER9", picks_hi),
        _model("Safest market · part 1", 25.01, "PART901", picks_hi),
        _model("Safest market · part 2", 25, "FREE2500", picks_free),
    ]}
    store = {}
    assert seal_document(doc, store, _ph) == 2
    public = str(doc)
    assert "MASTER9" not in public and "PART901" not in public and "Alpha v Beta" not in public
    assert "FREE2500" in public and "Free v Game" in public
    assert doc["modelSlips"][0]["premium"] is True and doc["modelSlips"][0]["picks"] == 1
    assert doc["modelSlips"][2]["premium"] is False
    saved = store["hot-20261112"]["codes"]["sportybet"]
    assert {row["code"] for row in saved} == {"MASTER9", "PART901"}
    assert saved[0]["picks"][0]["match"] == "Alpha v Beta"


def test_morning_master_ho_master_and_verzzify_are_sealed():
    doc = {"slips": [
        {
            "code": "MORNING",
            "name": "SportyBet Stats · Master · HIGH RISK",
            "date": "2026-11-12",
            "odds": 26.5,
            "origin": "sb-morning-master",
            "share": "https://www.sportybet.com/gh/?shareCode=MORNING",
            "shareUrl": "https://predict2u.com/high-odds/#MORNING",
            "legs": [{"match": "Dawn v Dusk", "selection": "Over 1.5", "odds": 1.4, "date": "2026-11-12"}],
            "codes": {"sportybet": {"code": "MORNING", "legs": 1, "odds": 26.5, "link": "https://www.sportybet.com/gh/?shareCode=MORNING"}},
        },
        {
            "code": "HODAY",
            "name": "Ascending odds · master · HIGH RISK",
            "date": "2026-11-12",
            "odds": 80,
            "origin": "ho-master",
            "legs": [{"match": "Up v Down", "selection": "Home", "odds": 1.35, "date": "2026-11-12"}],
            "codes": {"sportybet": {"code": "HODAY", "legs": 1, "odds": 80, "link": "https://www.sportybet.com/gh/?shareCode=HODAY"}},
        },
        {
            "name": "Main · Verzzify Edge Banker",
            "totalOdds": 30,
            "date": "2026-11-12",
            "verzzify": True,
            "legs": [{"match": "Edge v Bank", "selection": "Home", "odds": 1.3, "date": "2026-11-12"}],
            "codes": {"sportybet": "VERZ1", "msport": "VERZ2"},
        },
    ]}
    store = {}
    assert seal_document(doc, store, _ph) == 3
    public = str(doc)
    for secret in ("MORNING", "HODAY", "VERZ1", "VERZ2", "Dawn v Dusk", "Up v Down", "Edge v Bank"):
        assert secret not in public
    assert doc["slips"][0]["origin"] == "sb-morning-master"
    assert doc["slips"][0]["locked"]["id"] == "hot-20261112"
    assert doc["slips"][1]["origin"] == "ho-master"
    assert doc["slips"][1]["odds"] == 80
    assert doc["slips"][2]["locked"]["id"] == "banker-20261112"
    assert store["hot-20261112"]["codes"]["sportybet"][0]["code"] == "MORNING"
    assert store["banker-20261112"]["codes"]["msport"][0]["code"] == "VERZ2"
    assert store["banker-20261112"]["codes"]["sportybet"][0]["picks"][0]["match"] == "Edge v Bank"


def test_seal_leaves_odds_at_25_readable():
    store = {}
    slip = _slip(totalOdds=25, code="FREE25", codes={"sportybet": "FREE25"})
    assert seal_slip(slip, store, lambda i, b, n: f"P2ULOCK-{i}-{b}{n}") is False
    assert slip["premium"] is False
    assert slip["code"] == "FREE25"
    assert slip["legs"][0]["match"] == "Alpha v Beta"
    assert store == {}
