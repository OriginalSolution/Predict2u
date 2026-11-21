"""Busy-day league filter (engine/vendor/busy_day.py, HANDOFF 5.7)."""
import datetime as dt
import json
import sys
from pathlib import Path

import pytest

VENDOR = Path(__file__).resolve().parents[1] / "vendor"
sys.path.insert(0, str(VENDOR))
import busy_day as bd  # noqa: E402
import strategy_lib as lib  # noqa: E402

NOW = dt.datetime(2026, 11, 21, 9, 0, tzinfo=dt.timezone.utc)
DAY = "2026-11-21"


def ev(i, country, league, home="Home FC", away="Away FC", day=DAY, hour=15):
    d = dt.date.fromisoformat(day)
    ts = dt.datetime(d.year, d.month, d.day, hour, tzinfo=dt.timezone.utc).timestamp() * 1000
    return {"eventId": f"sr:match:{i}", "estimateStartTime": int(ts), "matchStatus": "Not start",
            "homeTeamName": f"{home} n{i}", "awayTeamName": f"{away} n{i}",
            "sport": {"category": {"name": country, "tournament": {"name": league}}}}


@pytest.fixture(autouse=True)
def _isolate(tmp_path, monkeypatch):
    monkeypatch.setenv("P2U_BUSY_LOG_DIR", str(tmp_path / "busy-day"))
    monkeypatch.delenv("P2U_BUSY_THRESHOLD", raising=False)
    monkeypatch.delenv("P2U_BUSY_FILTER", raising=False)
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    monkeypatch.setattr(bd, "_CFG", None)
    monkeypatch.setattr(bd, "_CAPABLE", None)
    monkeypatch.setattr(bd, "_FULL_COUNTS", None)
    yield


CAP = {"Norway|Eliteserien": {"n": 13, "won": 12, "rate": 0.92, "capable": True},
       "Japan|J1 League": {"n": 23, "won": 11, "rate": 0.48, "capable": False}}


def test_config_file_is_valid_and_documented():
    cfg = json.loads((Path(__file__).resolve().parents[1] / "busy_day.json").read_text())
    assert cfg["busy_threshold"] == 300 and cfg["enabled"] is True
    assert cfg["capable"]["min_sample"] >= 5 and 0.5 <= cfg["capable"]["min_hit_rate"] <= 1
    for country, league in [("England", "Championship"), ("Germany", "2. Bundesliga"), ("Italy", "Serie B"),
                            ("Spain", "LALIGA HYPERMOTION"), ("France", "Ligue 2"), ("USA", "MLS"), ("Mexico", "Liga MX")]:
        assert bd._lookup(cfg["known"], country, league), (country, league)
    handoff = (Path(__file__).resolve().parents[2] / "HANDOFF.md").read_text()
    assert "busy_day.json" in handoff and "Busy-day league filter" in handoff


@pytest.mark.parametrize("country,league,home,want", [
    ("England", "Premier League", "Arsenal", "known"),
    ("England", "Championship", "Leeds", "known"),
    ("International Clubs", "UEFA Champions League", "Real Madrid", "known"),
    ("International", "World Cup Qualification, UEFA", "Spain", "known"),
    ("Portugal", "Taca de Portugal", "Benfica", "known"),
    ("Norway", "Eliteserien", "Molde", "capable"),
    ("Japan", "J1 League", "Kashima", "excluded"),           # top flight, poor record
    ("England", "League Two", "Barrow", "excluded"),          # lower tier
    ("England Amateur", "National League South", "Bath", "excluded"),
    ("Spain Amateur", "Tercera Federacion, Group 1", "X", "excluded"),
    ("Italy", "Serie D, Group A", "X", "excluded"),
    ("Germany Amateur", "Regionalliga West", "X", "excluded"),  # regional
    ("Germany Amateur", "Women Bundesliga", "Wolfsburg", "excluded"),
    ("Italy", "Serie A, Women", "Roma", "excluded"),
    ("Spain", "U19 Division de Honor Juvenil", "X", "excluded"),
    ("Mexico", "U21 Liga MX", "X", "excluded"),
    ("Italy", "Primavera 1", "Inter", "excluded"),
    ("El Salvador", "Primera Division, Reserves", "X", "excluded"),
    ("Simulated Reality League", "Premier League SRL", "X", "excluded"),
])
def test_classify(country, league, home, want):
    assert bd.classify(country, league, home, "Other", capable=CAP) == want


def test_reserve_and_b_teams_dropped_even_in_known_cup():
    assert bd.classify("Portugal", "Taca de Portugal", "Benfica B", "Porto", capable=CAP) == "excluded"
    assert bd.classify("Germany", "DFB Pokal", "Bayern Munich II", "Koln", capable=CAP) == "excluded"
    assert bd.classify("Argentina", "Primera LPF", "Argentinos Juniors", "Boca", capable=CAP) == "known"


def busy_feed(n_lower=310):
    events = [ev(i, "England", "Premier League") for i in range(5)]
    events += [ev(100 + i, "Norway", "Eliteserien") for i in range(3)]
    events += [ev(200 + i, "Italy", "Serie D, Group A") for i in range(n_lower)]
    events += [ev(900 + i, "Germany Amateur", "Women Bundesliga") for i in range(20)]
    return events


def test_busy_day_keeps_known_and_capable_only(tmp_path):
    events = busy_feed()
    kept = bd.filter_events(events, job="t", complete=True, now=NOW, capable=CAP)
    assert {bd.event_fields(e)[1] for e in kept} == {"Premier League", "Eliteserien"}
    assert len(kept) == 8
    line = json.loads((tmp_path / "busy-day" / DAY / "t.jsonl").read_text().splitlines()[-1])
    # women's games do not count toward the busy threshold
    assert line["busy"] is True and line["fixtures"] == 318 and line["threshold"] == 300
    assert line["kept"] == 8 and line["dropped"] == 330 and line["known"] == 5 and line["capable"] == 3


def test_quiet_day_keeps_full_pool(tmp_path):
    events = busy_feed(n_lower=100)
    kept = bd.filter_events(events, job="t", complete=True, now=NOW, capable=CAP)
    assert kept == events
    line = json.loads((tmp_path / "busy-day" / DAY / "t.jsonl").read_text())
    assert line["busy"] is False and line["dropped"] == 0


def test_each_date_decided_on_its_own_count():
    events = busy_feed() + [ev(5000 + i, "Italy", "Serie D, Group A", day="2026-11-22") for i in range(10)]
    kept = bd.filter_events(events, job="t", complete=True, now=NOW, capable=CAP)
    assert sum(1 for e in kept if bd.event_day(e) == "2026-11-22") == 10


def test_threshold_and_switch_are_configurable(monkeypatch):
    events = busy_feed(n_lower=100)
    monkeypatch.setenv("P2U_BUSY_THRESHOLD", "50")
    monkeypatch.setattr(bd, "_CFG", None)
    assert len(bd.filter_events(events, complete=True, now=NOW, capable=CAP, log=False)) == 8
    monkeypatch.setenv("P2U_BUSY_FILTER", "0")
    monkeypatch.setattr(bd, "_CFG", None)
    assert len(bd.filter_events(busy_feed(), complete=True, now=NOW, capable=CAP, log=False)) == len(busy_feed())


def test_sticky_busy_from_earlier_log(tmp_path):
    folder = tmp_path / "busy-day" / DAY
    folder.mkdir(parents=True)
    (folder / "morning.jsonl").write_text(json.dumps({"fixtures": 520}) + "\n")
    events = busy_feed(n_lower=50)  # games started; feed now looks quiet
    kept = bd.filter_events(events, job="t", complete=True, now=NOW, capable=CAP)
    assert len(kept) == 8


def test_capable_derived_from_settled_logs(tmp_path):
    repo = tmp_path / "repo"
    (repo / "engine" / "data").mkdir(parents=True)
    legs = []
    for i in range(10):  # 9/10 qualified Norway rows
        legs.append({"league": "Norway - Eliteserien", "match": f"A{i} v B{i}", "odds": 1.3, "result": "won" if i else "lost"})
    for i in range(9):   # unqualified but unique name: counts for Sweden
        legs.append({"league": "Allsvenskan", "match": f"S{i} v T{i}", "odds": 1.4, "result": "won"})
    for i in range(12):  # ambiguous "Super League": counted for nobody
        legs.append({"league": "Super League", "match": f"G{i} v H{i}", "odds": 1.4, "result": "won"})
    for i in range(10):  # Japan J1 at 40%
        legs.append({"league": "Japan - J1 League", "match": f"J{i} v K{i}", "odds": 1.5, "result": "won" if i < 4 else "lost"})
    legs.append({"league": "Norway - Eliteserien", "match": "A1 v B1", "odds": 1.3, "result": "won"})  # duplicate
    legs.append({"league": "Norway - Eliteserien", "match": "P v Q", "odds": 1.3, "result": "pending"})
    (repo / "engine" / "data" / "code-ledger.json").write_text(json.dumps({"sportybet:X": {"legs": legs}}))
    (repo / "picks-history.json").write_text(json.dumps({"days": {DAY: []}}))
    cfg = json.loads((Path(__file__).resolve().parents[1] / "busy_day.json").read_text())
    cap = bd.capable_leagues(cfg, repo)
    assert cap["Norway|Eliteserien"] == {"n": 10, "won": 9, "rate": 0.9, "capable": True}
    assert cap["Sweden|Allsvenskan"]["capable"] is True
    assert cap["Greece|Super League"]["n"] == 0 and cap["Switzerland|Super League"]["n"] == 0
    assert cap["Japan|J1 League"]["capable"] is False
    cfg["capable"]["never"] = ["Norway|Eliteserien"]
    cfg["capable"]["always"] = ["Japan|J1 League"]
    cap = bd.capable_leagues(cfg, repo)
    assert cap["Norway|Eliteserien"]["capable"] is False and cap["Japan|J1 League"]["capable"] is True


def test_fetch_upcoming_applies_rule(monkeypatch):
    feed = busy_feed()
    monkeypatch.setattr(bd, "_CAPABLE", CAP)
    def fake(url, **_k):
        first = "pageNum=1&" in url
        return {"data": {"totalNum": len(feed), "tournaments": [{"events": feed}] if first else []}}
    monkeypatch.setattr(lib, "http_json", fake)
    real = bd.filter_events
    monkeypatch.setattr(bd, "filter_events", lambda events, **k: real(events, now=NOW, **k))
    assert len(lib.fetch_upcoming()) == 8
    assert len(lib.fetch_upcoming(busy_filter=False)) == len(feed)


def test_safe_filter_never_crashes(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("x")
    monkeypatch.setattr(bd, "filter_events", boom)
    assert bd.safe_filter([1, 2]) == [1, 2]
