"""AH -1 Favourite (pure rules + selection with stubbed data, no network)."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "engine" / "vendor"))
import ah1_fav as ah  # noqa: E402
import strategy_lib as lib  # noqa: E402
import sure80_reverse as sr  # noqa: E402
import master_pipeline as mp  # noqa: E402

KEYS = {"home": "1||Home", "draw": "1||Draw", "away": "1||Away", "o25": "18|total=2.5|Over 2.5",
        "h_o15": "19|total=1.5|Over 1.5", "a_o15": "20|total=1.5|Over 1.5",
        "h_o05": "19|total=0.5|Over 0.5", "a_o05": "20|total=0.5|Over 0.5",
        "ah_h": ah.AH_KEY["h"], "ah_a": ah.AH_KEY["a"]}


def odds(**prices):
    return {KEYS[n]: [v, f"o-{n}"] for n, v in prices.items()}


SCORES_OFTEN = [(1, 2)] * 6 + [(0, 1)] * 4     # scored in 6 of 10
SCORES_RARELY = [(1, 2)] * 4 + [(0, 1)] * 6    # scored in 4 of 10
MIDDLE = [(1, 2)] * 5 + [(0, 1)] * 5           # 5 of 10
STRONG_2P = [(2, 0)] * 6 + [(1, 0)] * 4        # 2+ in 6 of 10
STRONG_WEAK = [(2, 0)] * 5 + [(1, 0)] * 5      # 2+ in 5 of 10
BASE = dict(home=1.35, draw=5.0, away=8.0, o25=1.45, h_o15=1.40, a_o05=1.80)


def test_ah_filter_strictly_below_190_and_must_be_listed():
    assert ah.decide(odds(**BASE), MIDDLE, 1.0, STRONG_WEAK)[1]["why"] == "no AH -1"
    assert ah.decide(odds(ah_h=1.90, **BASE), MIDDLE, 1.0, STRONG_WEAK)[1]["why"] == "AH -1 >= 1.90"
    assert ah.decide(odds(ah_h=1.89, **BASE), MIDDLE, 1.0, STRONG_WEAK)[0] == "home"


def test_away_favourite_uses_away_minus_one():
    o = odds(home=6.0, draw=4.5, away=1.40, ah_a=1.70, ah_h=1.10, o25=1.5, a_o15=1.5, h_o05=1.9)
    name, info = ah.decide(o, MIDDLE, 1.0, STRONG_WEAK)
    assert info["fav"] == "a" and info["ah"] == 1.70 and name == "away"


def test_weak_team_scores_often_gives_over_25():
    assert ah.decide(odds(ah_h=1.5, **BASE), SCORES_OFTEN, 1.0, STRONG_2P)[0] == "o25"     # 6+ of 10
    assert ah.decide(odds(ah_h=1.5, **BASE), MIDDLE, 1.2, STRONG_2P)[0] == "o25"           # gpg 1.2+
    o = odds(ah_h=1.5, **dict(BASE, a_o05=1.49))
    assert ah.decide(o, SCORES_RARELY, 0.5, STRONG_2P)[0] == "o25"                         # O0.5 < 1.50 wins over "rarely"


def test_weak_team_rarely_scores_and_strong_scores_2plus_gives_team_o15():
    assert ah.decide(odds(ah_h=1.5, **BASE), SCORES_RARELY, 1.0, STRONG_2P)[0] == "h_o15"
    assert ah.decide(odds(ah_h=1.5, **BASE), MIDDLE, 0.89, STRONG_2P)[0] == "h_o15"         # gpg < 0.9
    assert ah.decide(odds(ah_h=1.5, **BASE), SCORES_RARELY, 1.0, STRONG_WEAK)[0] == "home"  # strong only 5 of 10


def test_otherwise_strong_team_to_win():
    name, info = ah.decide(odds(ah_h=1.5, **BASE), MIDDLE, 1.0, STRONG_2P)
    assert name == "home" and info["chosen"] == "win" and not info["stepped"]


def test_floor_steps_up_the_ladder_and_drops():
    low_win = dict(BASE, home=1.15)
    name, info = ah.decide(odds(ah_h=1.1, **low_win), MIDDLE, 1.0, STRONG_2P)
    assert name == "h_o15" and info["stepped"]                       # win 1.15 -> team O1.5 1.40
    name, _ = ah.decide(odds(ah_h=1.1, **dict(low_win, h_o15=1.19)), MIDDLE, 1.0, STRONG_2P)
    assert name == "o25"                                             # -> Over 2.5
    name, info = ah.decide(odds(ah_h=1.1, **dict(low_win, h_o15=1.19, o25=1.19)), MIDDLE, 1.0, STRONG_2P)
    assert name is None and info["why"] == "nothing reaches 1.20"
    # Over 2.5 is the top rung: a low O2.5 is dropped, never stepped down
    name, _ = ah.decide(odds(ah_h=1.1, **dict(BASE, o25=1.18)), SCORES_OFTEN, 1.0, STRONG_2P)
    assert name is None
    assert ah.decide(odds(ah_h=1.5, **dict(BASE, home=1.20)), MIDDLE, 1.0, STRONG_2P)[0] == "home"  # 1.20 is enough


def event(i, o):
    markets = {}
    for key, (price, oid) in o.items():
        mid, spec, desc = key.split("|")
        markets.setdefault((mid, spec), []).append({"id": oid, "odds": str(price), "desc": desc, "isActive": 1})
    return {"eventId": f"sr:match:{i}", "homeTeamName": f"H{i}", "awayTeamName": f"A{i}", "estimateStartTime": 1795300000000,
            "sport": {"category": {"name": "England", "tournament": {"name": "Premier League"}}},
            "markets": [{"id": m, "specifier": s or None, "outcomes": outs} for (m, s), outs in markets.items()]}


def rows_for(specs):
    out = []
    for i, o in specs:
        ev = event(i, o)
        out.append({"event": ev, "eventId": ev["eventId"], "league": "England - Premier League",
                    "odds": lib.event_odds(ev)})
    return out


def test_select_applies_clash_cap_and_one_pick_per_match(monkeypatch):
    rows = rows_for([(1, odds(ah_h=1.4, **BASE)), (2, odds(ah_h=1.6, **BASE)), (3, odds(ah_h=1.3, **BASE)),
                     (4, odds(ah_h=1.95, **BASE)), (5, odds(**BASE))])
    tables = {"sr:match:2": {"home": 2, "away": 4, "n": 20}}  # top-5 v top-5

    def fake_fetch(row, cache):
        return {"last": (STRONG_2P, MIDDLE), "gpg": (2.0, 1.0), "table": tables.get(row["eventId"])}
    monkeypatch.setattr(ah, "fetch", fake_fetch)
    monkeypatch.setattr(ah, "with_ah", lambda row, cache: row["odds"])
    usage = {"sr:match:3": ["X", "Y"]}
    out = ah.select(rows, {}, usage, sr.make_leg)["ah1"]
    assert [leg["eventId"] for leg in out["legs"]] == ["sr:match:1"]
    assert out["removed"] == {"already on 2 codes": 1, "AH -1 >= 1.90": 1, "no AH -1": 1, "top-5 v top-5": 1}
    leg = out["legs"][0]
    assert leg["strategy"] == "ah1" and leg["selection"] == "Home" and leg["ahMinusOne"] == 1.4


def test_with_ah_reads_full_event_only_when_needed(monkeypatch):
    row = rows_for([(7, odds(**BASE))])[0]
    calls = []
    full = event(7, odds(ah_h=1.55, **BASE))
    monkeypatch.setattr(lib, "http_json", lambda url, **k: calls.append(url) or {"data": full})
    got = ah.with_ah(row, {})
    assert ah.price(got, ah.AH_KEY["h"]) == 1.55 and len(calls) == 1
    long_fav = rows_for([(8, odds(**dict(BASE, home=2.5, away=2.9)))])[0]
    assert ah.with_ah(long_fav, {}) is long_fav["odds"] and len(calls) == 1


def test_wired_into_the_22_00_job_master_and_site():
    assert sr.ALL_KINDS[-1] == "ah1" and sr.ALL_KINDS.index("ah1") > sr.ALL_KINDS.index("mo25")
    assert mp.STRENGTH.index("ah1") == mp.STRENGTH.index("mo25") + 1
    assert lib.PUBLIC_NAME["ah1"] == "AH -1 Favourite"
    html = (ROOT / "high-odds" / "index.html").read_text()
    assert "['strategy-ah1','AH -1 Favourite'" in html
    wf = (ROOT / ".github" / "workflows" / "engine-sure80.yml").read_text()
    assert "engine/data/strategy-codes/ah1" in wf
    assert 'fetch_upcoming("1,11,16,18,19,20,29")' in (ROOT / "engine" / "vendor" / "sure80_reverse.py").read_text()
    handoff = (ROOT / "HANDOFF.md").read_text()
    assert "AH -1 Favourite" in handoff
