"""Booking watchdog (.github/scripts/p2u_watchdog.py): missed or failed booking jobs are
caught up by the engine alone, and nothing is booked twice. No network."""
import datetime as dt
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / ".github" / "scripts"))
import p2u_watchdog as w  # noqa: E402

UTC = dt.timezone.utc
P = {p["key"]: p for p in w.PRODUCTS}


def at(h, m=0, day=14):
    return dt.datetime(2026, 11, day, h, m, tzinfo=UTC)


def done(conclusion, finished):
    return (conclusion, finished)


def test_slot_must_be_20_minutes_old():
    assert w.last_slot("22:00", at(22, 10)) == at(22, 0, 13)
    assert w.last_slot("22:00", at(22, 25)) == at(22, 0)


def test_missed_slot_with_no_run_is_dispatched():
    a, _ = w.decide(P["gg"], at(23, 40), [], {}, None)
    assert a == "dispatch"


def test_running_job_is_left_alone():
    a, _ = w.decide(P["daily-slips"], at(22, 40), [{"status": "in_progress"}], {}, False)
    assert a == "wait"


def test_successful_run_without_data_check_is_never_rebooked():
    # GG / NYSM / NT can legitimately book nothing: success is enough
    a, _ = w.decide(P["nysm"], at(23, 59), [{"status": "completed"}], {1: done("success", at(23, 45))}, None)
    assert a == "ok"


def test_published_codes_are_never_rebooked_even_after_a_failure():
    a, _ = w.decide(P["daily-slips"], at(23, 0), [{"status": "completed"}], {1: done("failure", at(22, 30))}, True)
    assert a == "ok"


def test_failed_run_retries_after_backoff_then_gives_up():
    p = P["strategies"]
    r1 = {1: done("failure", at(22, 50))}
    assert w.decide(p, at(22, 55), [{"status": "completed"}], r1, None)[0] == "wait"      # 10 min backoff
    assert w.decide(p, at(23, 5), [{"status": "completed"}], r1, None)[0] == "dispatch"
    r2 = {**r1, 2: done("failure", at(23, 10))}
    assert w.decide(p, at(23, 20), [{"status": "completed"}] * 2, r2, None)[0] == "wait"  # 30 min backoff
    assert w.decide(p, at(23, 45), [{"status": "completed"}] * 2, r2, None)[0] == "dispatch"
    r3 = {**r2, 3: done("failure", at(23, 50))}
    assert w.decide(p, at(23, 59), [{"status": "completed"}] * 3, r3, None)[0] == "give-up"


def test_success_with_missing_codes_is_forced_once_only():
    p = P["daily-slips"]
    one = {1: done("success", at(22, 40))}
    assert w.decide(p, at(23, 0), [{"status": "completed"}], one, False)[0] == "dispatch-force"
    two = {**one, 2: done("success", at(23, 30))}
    assert w.decide(p, at(23, 59), [{"status": "completed"}] * 2, two, False)[0] == "give-up"


def test_past_the_booking_window_nothing_is_booked():
    a, _ = w.decide(P["morning-tips"], at(20, 0), [], {}, False)
    assert a == "expired"


def test_hot_picks_waits_for_the_daily():
    a, _ = w.decide(P["hot-picks"], at(22, 30), [], {}, False, upstream_busy=True)
    assert a == "wait"
    assert P["hot-picks"]["after"] == "engine-daily.yml"


def test_data_checks_read_the_published_files(tmp_path, monkeypatch):
    monkeypatch.setattr(w, "ROOT", tmp_path)
    slot = at(22, 0, 13)
    hp = {"homeCode": {"bookedAt": "2026-11-13T22:02:35+00:00", "codes": [{"sportybet": "FE1FZL"}],
                       "dayMasters": {"2026-11-14": {"codes": ["sportybet"]}}}}
    (tmp_path / "home-picks.json").write_text(json.dumps(hp))
    assert w.check_daily(slot) is True
    assert w.check_daily(at(22, 0, 14)) is False          # yesterday's home code does not count for tonight
    assert w.check_fav(at(6, 0, 14)) is True
    assert w.check_fav(at(6, 0, 15)) is False
    (tmp_path / "hot-picks.json").write_text(json.dumps({"updatedAt": "2026-11-14T20:00:00Z",
        "slips": [{"bookedAt": "2026-11-13T13:23:55+00:00", "codes": {"sportybet": {"code": "ABC"}}}]}))
    assert w.check_hot(slot) is False                       # settle moves updatedAt; bookedAt decides
    (tmp_path / "engine/data/sb-morning").mkdir(parents=True)
    (tmp_path / "engine/data/sb-morning/2026-11-14.json").write_text(json.dumps({"date": "2026-11-14", "slips": [{}]}))
    assert w.check_morning(at(7, 0, 14)) is True
    assert w.check_morning(at(7, 0, 15)) is False


def test_every_product_workflow_exists_with_its_job_and_force_input():
    for p in w.PRODUCTS:
        txt = (ROOT / ".github/workflows" / p["wf"]).read_text()
        assert re.search(rf"^  {re.escape(p['job'])}:\s*$", txt, re.M), (p["wf"], p["job"])
        if p.get("force_input", True):
            assert re.search(r"^\s+force:\s*$", txt, re.M), p["wf"]
            assert f"--job {p['job']}" in txt and f"--at {p['at']}" in txt, p["wf"]


def test_watchdog_is_on_the_ticker_and_triggered_by_every_booking_workflow():
    src = (ROOT / ".github/scripts/p2u_ticker.py").read_text()
    assert '("engine-watchdog.yml", "5,35", "*", "*")' in src
    wd = (ROOT / ".github/workflows/engine-watchdog.yml").read_text()
    names = {f: re.search(r"^name:\s*(.+)$", (ROOT / ".github/workflows" / f).read_text(), re.M)[1].strip()
             for f in {p["wf"] for p in w.PRODUCTS} | {"engine-ticker.yml"}}
    for f, n in names.items():
        assert f'"{n}"' in wd, f"engine-watchdog.yml does not wake on {f} ({n})"


def test_watchdog_never_reenables_hand_disabled_workflows():
    for f in ("live-scores.yml", "news-sync.yml", "fixture-snapshot.yml", "future-fixtures.yml"):
        assert f not in w.CRITICAL
    src = (ROOT / ".github/scripts/p2u_watchdog.py").read_text()
    assert '"disabled_inactivity"' in src and "disabled_manually" not in src.split("def keep_enabled")[1].split("def ")[0]


def test_booking_endpoint_retries_transport_failures(monkeypatch):
    sys.path.insert(0, str(ROOT))
    from engine import bookers
    calls = []

    class R:
        def __init__(self, out):
            self.stdout = out

    answers = iter(["", "<html>502</html>", '{"bizCode":10000}'])
    monkeypatch.setattr(bookers.time, "sleep", lambda s: None)
    monkeypatch.setattr(bookers.subprocess, "run", lambda *a, **k: calls.append(1) or R(next(answers)))
    bookers._DOWN.clear()
    assert bookers._curl_json("POST", "https://x.test/api", {}) == {"bizCode": 10000}
    assert len(calls) == 3
    calls.clear()
    monkeypatch.setattr(bookers.subprocess, "run", lambda *a, **k: calls.append(1) or R('{"bizCode":4000}'))
    assert bookers._curl_json("POST", "https://x.test/api", {}) == {"bizCode": 4000}   # a refusal is not retried
    assert len(calls) == 1


def test_watchdog_script_compiles_and_has_no_undefined_names():
    pytest.importorskip("pyflakes")
    out = subprocess.run([sys.executable, "-m", "pyflakes", str(ROOT / ".github/scripts/p2u_watchdog.py"),
                          str(ROOT / ".github/monitor/monitor.py")], capture_output=True, text=True).stdout
    assert "undefined name" not in out, out
