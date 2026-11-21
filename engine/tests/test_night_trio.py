"""Team To Win, 80% Form and Match Over 2.5 (pure rules, no network)."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "engine" / "vendor"))
import night_trio as t  # noqa: E402
import strategy_lib as lib  # noqa: E402
import sure80_reverse as sr  # noqa: E402
import master_pipeline as mp  # noqa: E402


def odds(**prices):
    return {t.K[n]: [v, f"o-{n}"] for n, v in prices.items()}


def test_ttw_counts_seven_checks_for_the_favourite():
    o = odds(home=1.40, draw=4.50, away=7.0, h_o25=1.95, a_o05=1.80, gg=1.85, u35=1.70)
    n, passed = t.ttw_checks(o)
    assert n == 7 and passed == list("abcdefg")
    away_fav = odds(home=3.5, draw=3.4, away=2.1, a_o25=2.60)
    n, passed = t.ttw_checks(away_fav)
    assert passed == ["a"]                       # only "offered"; everything else fails -> not booked
    assert t.ttw_checks(odds(home=1.4))[0] == 0  # no full 1X2


def test_mo25_counts_checks():
    o = odds(home=1.35, draw=4.80, away=8.0, h_o25=1.90, h_o15=1.30, a_o05=1.45, gg=1.55, u35=1.65)
    assert t.mo25_checks(o) == (7, list("bcdefgh"))      # O1.5 offered -> (a) fails; (a) and (h) exclusive
    only = odds(home=1.35, draw=4.80, away=8.0, h_o25=1.90, a_o05=1.45, gg=1.55, u35=1.65)
    assert t.mo25_checks(only) == (7, list("abcdefg"))


def test_mo25_check_a_only_when_team_o25_is_the_only_team_goals_market():
    base = dict(home=2.6, draw=3.3, away=2.8)
    assert t.mo25_checks(odds(h_o25=2.2, **base))[1] == ["a"]
    assert "a" not in t.mo25_checks(odds(h_o25=2.2, h_o05=1.20, **base))[1]
    assert "a" not in t.mo25_checks(odds(h_o25=2.2, h_o15=1.70, **base))[1]
    assert "a" not in t.mo25_checks(odds(**base))[1]
    # the weaker team's markets don't matter; Team To Win (a) is unchanged (offered is enough)
    assert t.mo25_checks(odds(h_o25=2.2, a_o05=1.9, **base))[1][0] == "a"
    assert "a" in t.ttw_checks(odds(h_o25=2.2, h_o05=1.20, **base))[1]
    assert t.mo25_checks(odds(home=2.3, draw=3.2, away=3.1, gg=1.75, u35=1.40))[0] == 0


def g(w, d, lo):
    return [(2, 0)] * w + [(1, 1)] * d + [(0, 2)] * lo


def test_form_signal_needs_ten_games():
    assert t.form_signal(g(8, 1, 0)) is None
    assert t.form_signal(g(8, 1, 1)) == {"w": 8, "l": 1, "unbeaten": 9}


def test_form_pick_rules_and_conflicts():
    win8, lose8, unb8, meh = (t.form_signal(x) for x in (g(8, 1, 1), g(1, 1, 8), g(5, 4, 1), g(4, 2, 4)))
    assert t.form_pick(win8, meh)[0] == "home"
    assert t.form_pick(meh, lose8)[0] == "home"             # opponent of an 8+ loser wins
    assert t.form_pick(lose8, meh)[0] == "away"
    assert t.form_pick(unb8, meh)[0] == "dnb_home"
    assert t.form_pick(meh, unb8)[0] == "dnb_away"
    assert t.form_pick(unb8, lose8)[0] == "home"            # win beats DNB for the same team
    assert t.form_pick(win8, win8) == (None, 0, "conflict")
    assert t.form_pick(unb8, unb8)[2] == "conflict"
    assert t.form_pick(None, None)[2] == "fewer than 10 verified games"
    assert t.form_pick(meh, meh)[2] == "no 80% signal"


def test_competitive_excludes_friendlies_and_future_games():
    lastx = {"tournaments": {"1": {"friendly": False}, "2": {"friendly": True}}, "matches": [
        {"_tid": 1, "time": {"uts": 100}, "result": {"home": 2, "away": 0}, "teams": {"home": {"uid": 7}, "away": {"uid": 8}}},
        {"_tid": 2, "time": {"uts": 200}, "result": {"home": 0, "away": 5}, "teams": {"home": {"uid": 7}, "away": {"uid": 9}}},
        {"_tid": 1, "time": {"uts": 300}, "result": {"home": 1, "away": 3}, "teams": {"home": {"uid": 9}, "away": {"uid": 7}}},
        {"_tid": 1, "time": {"uts": 99999}, "result": {"home": 1, "away": 0}, "teams": {"home": {"uid": 7}, "away": {"uid": 9}}},
    ]}
    assert t.competitive(lastx, 7, 10000) == [(3, 1), (2, 0)]


def test_league_kind_youth_high_scoring_lower_tier():
    assert t.league_kind("England - Premier League 2 U21", "A", "B", 1, 2.5) == "youth"
    assert t.league_kind("Italy - Primavera 1", "A", "B", 1, None) == "youth"
    assert t.league_kind("Norway - Eliteserien", "A", "B", 1, 3.1) == "high-scoring"
    assert t.league_kind("Germany - Oberliga", "A", "B", None, 2.4) == "lower-tier"
    assert t.league_kind("Spain - Some Cup", "A", "B", 3, 2.4) == "lower-tier"
    assert t.league_kind("Spain - LaLiga", "A", "B", 1, 2.4) is None


def test_top5_bottom3_drop():
    assert t.table_clash({"home": 1, "away": 5, "n": 20}) == "top-5 v top-5"
    assert t.table_clash({"home": 18, "away": 20, "n": 20}) == "bottom-3 v bottom-3"
    assert t.table_clash({"home": 1, "away": 20, "n": 20}) is None and t.table_clash(None) is None


def test_split_many_25_leg_codes_each_reaching_25_never_padded():
    legs = [{"eventId": f"e{i}", "odds": 1.30, "selection": "Home", "marketId": "1"} for i in range(63)]
    parts = t.split_many(legs)
    assert len(parts) == 3 and all(len(x) <= 25 for x in parts)
    assert all(lib.product(x["odds"] for x in part) >= 25 for part in parts)
    short = [dict(x, odds=1.20) for x in legs[:30]]
    one = t.split_many(short)                     # 15+15 would both miss 25; 25 in rank order books
    assert [len(x) for x in one] == [25]
    assert t.split_many(short[:10]) == []
    ng = [{"eventId": "n", "odds": 9.0, "selection": "No", "marketId": "29", "outcomeId": "76"}]
    assert t.split_many(ng) == []


def test_select_ranks_and_respects_usage(monkeypatch):
    def ev(eid):
        return {"eventId": eid, "homeTeamName": "H" + eid, "awayTeamName": "A" + eid, "estimateStartTime": 2000000000000,
                "sport": {"category": {"name": "Germany", "tournament": {"name": "Oberliga"}}}}
    rows = []
    for eid, o in (("1", odds(home=1.40, draw=4.5, away=7.0, h_o25=1.9, o25=1.45)),
                   ("2", odds(home=1.30, draw=5.0, away=9.0, o25=1.40)),
                   ("3", odds(home=1.20, draw=6.0, away=12.0, o25=1.30))):
        o.update({sr.O["o25"]: o.get(t.K["o25"], [1.5, "x"])})
        rows.append({"eventId": eid, "event": ev(eid), "league": "Germany - Oberliga", "odds": o})
    sig = t.form_signal(g(8, 1, 1))
    monkeypatch.setattr(t, "fetch", lambda r, c: {"form": (sig, None), "table": None, "level": 5, "sid": None})
    out = t.select(rows, {}, {"3": ["A", "B"]}, lambda *a: (None, 0), sr.make_leg)
    assert [x["eventId"] for x in out["ttw"]["legs"]] == ["1", "2"]      # 1 passes more checks
    assert out["ttw"]["removed"]["already on 2 codes"] == 1
    assert {x["eventId"] for x in out["form80"]["legs"]} == {"1", "2"}
    assert all(x["selection"] == "Over 2.5" for x in out["mo25"]["legs"])


def test_wiring_names_master_priority_and_site_sections():
    assert lib.PUBLIC_NAME["ttw"] == "Team To Win" and lib.PUBLIC_NAME["form80"] == "80% Form"
    assert lib.PUBLIC_NAME["mo25"] == "Match Over 2.5"
    s = mp.STRENGTH
    assert s.index("rev-u45-draw") < s.index("ttw") < s.index("form80") < s.index("mo25")
    assert sr.ALL_KINDS[-4:] == ("ttw", "form80", "mo25", "ah1")  # AH -1 Favourite books last
    wf = (ROOT / ".github/workflows/engine-sure80.yml").read_text()
    for kind in t.KINDS:
        assert f"engine/data/strategy-codes/{kind}" in wf
    html = (ROOT / "high-odds/index.html").read_text()
    assert 'id="strategy-sections"' in html
    for kind in t.KINDS:
        assert f"'strategy-{kind}'" in html
