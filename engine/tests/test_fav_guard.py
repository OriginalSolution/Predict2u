import datetime as dt
import json

from engine import fav_guard as G

NOW = dt.datetime(2026, 11, 13, 2, 0, tzinfo=dt.timezone.utc)
DM13 = {"bookedAt": "2026-11-12T22:02:35+00:00", "codes": {"sportybet": [{"code": "BRGPD6"}]},
        "picks": [{"date": "2026-11-13", "ko": "12:30", "eventId": "a"}]}
GOOD = {"date": "2026-11-12", "leagues": [{"league": "England - Premier League", "fixtures": [{"ko": "2026-11-13T12:30"}]}],
        "picks": [{"eventId": "a"}], "slips": [{"name": "Safe slip"}],
        "homeCode": {"codes": {"sportybet": "X"}, "dayMasters": {"2026-11-13": DM13}}}
SHELL = {"date": "2026-11-12", "leagues": [], "picks": [], "slips": [{"name": "DC Shield Goals"}], "homeCode": {}}


def test_empty_section_is_a_problem():
    assert G.problems(SHELL, NOW)
    assert not G.problems(GOOD, NOW)


def test_repair_restores_from_snapshot_without_booking(tmp_path):
    (tmp_path / "home-picks.json").write_text(json.dumps(SHELL))
    (tmp_path / "fav-leagues.json").write_text(json.dumps(G.snapshot_from(GOOD, NOW)))
    changes, ok = G.repair_repo(tmp_path, history=False, now=NOW)
    assert ok and changes
    d = json.loads((tmp_path / "home-picks.json").read_text())
    assert d["leagues"] and d["homeCode"]["dayMasters"]["2026-11-13"]["codes"]
    assert d["slips"] == SHELL["slips"]


def test_snapshot_never_written_empty(tmp_path):
    assert G.write_snapshot(tmp_path, SHELL, NOW) is False
    assert not (tmp_path / "fav-leagues.json").exists()


def test_three_way_merge_keeps_concurrent_publish():
    # strategies job started from the shield copy (SHELL); daily published GOOD meanwhile
    ours = json.loads(json.dumps(SHELL))
    ours["slips"].insert(0, {"name": "Main · Verzzify Edge Banker"})
    base = json.loads(json.dumps(SHELL))
    theirs = json.loads(json.dumps(GOOD))
    theirs["slips"].append({"name": "DC Shield Goals"})
    m = G.merge_home(base, ours, theirs)
    assert m["leagues"] == GOOD["leagues"]
    assert m["homeCode"]["dayMasters"]["2026-11-13"]["codes"]
    names = [s["name"] for s in m["slips"]]
    assert "Safe slip" in names and "Main · Verzzify Edge Banker" in names and "DC Shield Goals" in names


def test_stale_daymaster_not_restored():
    old = {"leagues": GOOD["leagues"], "dayMasters": {"2026-11-11": DM13}}
    doc = json.loads(json.dumps(SHELL))
    G.repair(doc, [old], NOW)
    assert "2026-11-11" not in (doc.get("homeCode") or {}).get("dayMasters", {})
