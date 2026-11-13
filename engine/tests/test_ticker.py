"""On-time ticker (.github/scripts/p2u_ticker.py). No network.

Nov 12: PR #17 added the 23:10 GG, 23:30 NYSM and 23:50 NerdyTips slots at
22:07, but the ticker started at 19:33 kept its old in-memory list until
01:14, and the post-merge ticker saw it alive and exited. None of the three
started on time. The ticker now reloads SCHEDULE from main and a newer-logic
ticker replaces an older one.
"""
import datetime as dt
import os
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / ".github" / "scripts"
os.environ.setdefault("GITHUB_REPOSITORY", "OriginalSolution/Predict2u")
sys.path.insert(0, str(SCRIPTS))
import p2u_ticker as t  # noqa: E402

SRC = (SCRIPTS / "p2u_ticker.py").read_text()
NIGHT = [("engine-gg.yml", "10", "23", "*"), ("engine-nysm.yml", "30", "23", "*"), ("engine-nt-tomorrow.yml", "50", "23", "*")]


def without(src, rows):
    for wf, m, h, d in rows:
        row = re.escape(f'("{wf}", "{m}", "{h}", "{d}"),')
        src, n = re.subn(r"\n\s*" + row + r"[^\n]*", "", src)
        assert n == 1, wf
    return src


@pytest.fixture
def gh(monkeypatch):
    """Fake GitHub: main's ticker source per sha, live ticker runs, dispatch/cancel log."""
    state = {"head": "a" * 40, "src": {}, "runs": [], "dispatched": [], "cancelled": [], "created": {}}
    monkeypatch.setenv("GITHUB_RUN_ID", "100")
    monkeypatch.setattr(t, "main_head", lambda: state["head"])
    monkeypatch.setattr(t, "source_at", lambda sha: state["src"][sha])
    monkeypatch.setattr(t, "live_tickers", lambda: [r for r in state["runs"] if r["id"] != 100])
    monkeypatch.setattr(t, "dispatch", lambda wf: state["dispatched"].append(wf))
    monkeypatch.setattr(t, "cancel", lambda rid: state["cancelled"].append(rid))
    monkeypatch.setattr(t, "runs_since", lambda wf, since: state["created"].get(wf, 0))
    monkeypatch.setattr(t, "log", lambda msg: None)
    monkeypatch.setattr(t.time, "sleep", lambda s: None)
    t._logic_cache.clear()
    return state


def test_schedule_parses_and_carries_the_pr17_night_slots():
    rows = t.read_schedule(SRC)
    assert rows == [tuple(r) for r in t.SCHEDULE]
    for slot in NIGHT + [("engine-strategy-master.yml", "0", "6", "*")]:
        assert slot in rows


def test_every_gated_workflow_has_a_ticker_slot_at_its_gate_time():
    rows = t.read_schedule(SRC)
    for wf in sorted((ROOT / ".github" / "workflows").glob("*.yml")):
        for hh, mm in re.findall(r"p2u_gate\.py --at (\d\d):(\d\d)", wf.read_text()):
            at = dt.datetime(2030, 1, 6, int(hh), int(mm))  # a Sunday, so weekly slots match too
            assert any(name == wf.name and t.matches(at, m, h, d) for name, m, h, d in rows), \
                f"{wf.name} gates on {hh}:{mm} but the ticker never starts it then"
    for name, *_ in rows:
        assert (ROOT / ".github" / "workflows" / name).exists(), name


def test_logic_id_ignores_schedule_edits_only():
    assert t.logic_id(without(SRC, NIGHT)) == t.logic_id(SRC)
    assert t.logic_id(SRC.replace("GRACE = int(", "GRACE  = int(")) != t.logic_id(SRC)


def test_nov12_merge_mid_lifetime_puts_new_slots_on_the_clock(gh, monkeypatch):
    old_src = without(SRC, NIGHT)
    gh["src"]["a" * 40] = old_src
    monkeypatch.setenv("GITHUB_SHA", "a" * 40)
    plan = t.Plan(t.logic_id(old_src), old_src)
    fired = set()
    t.tick(plan, dt.datetime(2026, 11, 12, 23, 10, 2, tzinfo=dt.timezone.utc), fired)
    assert "engine-gg.yml" not in gh["dispatched"]  # the old list really lacks it
    gh["head"] = "b" * 40  # PR #17 merges
    gh["src"]["b" * 40] = SRC
    plan.refresh()
    assert all(slot in plan.schedule for slot in NIGHT)
    assert "engine-ticker.yml" not in gh["dispatched"]  # schedule-only change: hot reload, no hand-off
    for minute, wf in ((10, "engine-gg.yml"), (30, "engine-nysm.yml"), (50, "engine-nt-tomorrow.yml")):
        t.tick(plan, dt.datetime(2026, 11, 12, 23, minute, 1, tzinfo=dt.timezone.utc), fired)
        assert gh["dispatched"].count(wf) == 1
    # Run-once: the next minutes in grace do not fire again.
    t.tick(plan, dt.datetime(2026, 11, 12, 23, 51, 1, tzinfo=dt.timezone.utc), fired)
    assert gh["dispatched"].count("engine-nt-tomorrow.yml") == 1


def test_slot_with_an_existing_run_is_not_redispatched(gh, monkeypatch):
    monkeypatch.setenv("GITHUB_SHA", "a" * 40)
    plan = t.Plan(t.logic_id(SRC), SRC)
    gh["created"]["engine-nysm.yml"] = 1
    t.tick(plan, dt.datetime(2026, 11, 13, 23, 31, tzinfo=dt.timezone.utc), set())
    assert "engine-nysm.yml" not in gh["dispatched"]


def test_logic_change_on_main_dispatches_one_fresh_ticker(gh, monkeypatch):
    monkeypatch.setenv("GITHUB_SHA", "a" * 40)
    plan = t.Plan(t.logic_id(SRC), SRC)
    newer = SRC.replace("GRACE = int(", "GRACE  = int(")
    gh["head"] = "c" * 40
    gh["src"]["c" * 40] = newer
    plan.refresh()
    gh["head"] = "d" * 40  # another commit, same logic
    gh["src"]["d" * 40] = newer
    plan.refresh()
    assert gh["dispatched"] == ["engine-ticker.yml"]


def test_newer_logic_cancels_an_old_ticker_and_starts_at_once(gh):
    gh["src"]["0" * 40] = "SCHEDULE = []\nOLD = 1\n"
    gh["runs"] = [{"id": 90, "head_sha": "0" * 40, "status": "in_progress"}]
    assert t.take_over(t.logic_id(SRC)) is True
    assert gh["cancelled"] == [90]


def test_same_logic_older_ticker_keeps_the_clock(gh):
    gh["src"]["e" * 40] = SRC
    gh["runs"] = [{"id": 90, "head_sha": "e" * 40, "status": "in_progress"}]
    assert t.take_over(t.logic_id(SRC)) is False
    assert gh["cancelled"] == []


def test_same_logic_older_ticker_that_hands_over_lets_the_new_one_start(gh):
    gh["src"]["e" * 40] = SRC
    gh["runs"] = [{"id": 90, "head_sha": "e" * 40, "status": "in_progress"}]
    calls = {"n": 0}
    real = t.live_tickers

    def finishing():
        calls["n"] += 1
        if calls["n"] > 2:
            gh["runs"] = []
        return real()

    t.live_tickers = finishing
    try:
        assert t.take_over(t.logic_id(SRC)) is True
    finally:
        t.live_tickers = real


def test_a_late_starting_older_same_logic_ticker_wins_the_tie(gh, monkeypatch):
    monkeypatch.setenv("GITHUB_SHA", "e" * 40)
    gh["src"]["e" * 40] = SRC
    plan = t.Plan(t.logic_id(SRC), SRC)
    gh["runs"] = [{"id": 90, "head_sha": "e" * 40, "status": "in_progress"}]
    assert plan.should_yield() is True
    gh["runs"] = [{"id": 120, "head_sha": "e" * 40, "status": "in_progress"}]
    assert plan.should_yield() is False


def test_unreadable_main_keeps_the_current_schedule(gh, monkeypatch):
    monkeypatch.setenv("GITHUB_SHA", "a" * 40)
    plan = t.Plan(t.logic_id(SRC), SRC)
    gh["head"] = "f" * 40
    gh["src"]["f" * 40] = "SCHEDULE = [('x.yml', '61x', '*', '*')]\n"
    before = list(plan.schedule)
    plan.refresh()
    assert plan.schedule == before and gh["dispatched"] == []
