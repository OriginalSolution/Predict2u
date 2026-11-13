"""The nightly NYSM / NerdyTips jobs must reach the end of run() without a crash.

Nov 12-13: both printed their summary with a name that only existed inside a
nested helper (nysm_v2 `tree_picks`, nt_tomorrow `chosen`). The NameError hit
after write_record, the job failed and the commit step never ran. These tests
drive run() end to end with the network stubbed out. No booking, no network.
"""
import datetime as dt
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "engine" / "vendor"), str(ROOT / "engine"), str(ROOT)]

import nysm_v2 as nysm  # noqa: E402
import nt_tomorrow as nt  # noqa: E402
import strategy_lib as lib  # noqa: E402

DAY = dt.date(2030, 1, 2)


def _no_booking(*_a, **_k):
    raise AssertionError("tests must never book")


@pytest.fixture
def offline(monkeypatch):
    monkeypatch.setattr(lib, "fetch_upcoming", lambda *_a, **_k: [])
    monkeypatch.setattr(lib, "http_json", lambda *_a, **_k: {})
    monkeypatch.setattr(lib, "sr_get", lambda *_a, **_k: {})
    monkeypatch.setattr(lib, "book_confirmed", _no_booking)
    monkeypatch.setattr(lib, "book_sportybet", _no_booking)
    monkeypatch.setattr(nt, "fetch_tomorrow_html", lambda: "<html></html>")
    monkeypatch.setattr(nt, "fetch_detail", lambda _url: "")


@pytest.mark.parametrize("dry_run", [True, False])
def test_nysm_run_reaches_the_summary(offline, tmp_path, capsys, dry_run):
    payload = nysm.run(DAY, tmp_path, dry_run=dry_run)
    summary = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert summary["nysm"] == DAY.isoformat()
    assert summary["treePicks"] == 0 == payload["treePicks"]
    assert set(summary["slips"]) == {"nysm-main", "nysm-conservative", "nysm-ts2"}
    if not dry_run:
        assert list(tmp_path.rglob("*.json")), "write_record should have written the night record"


@pytest.mark.parametrize("dry_run", [True, False])
def test_nt_tomorrow_run_reaches_the_summary(offline, tmp_path, capsys, dry_run):
    payload = nt.run(tmp_path, dry_run=dry_run, day=DAY)
    summary = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert summary["nt"] == DAY.isoformat()
    assert summary["chosen"] == 0 == payload["chosen"]
    if not dry_run:
        assert list(tmp_path.rglob("*.json"))


def test_engine_has_no_undefined_names():
    """Same scan the 23:15 health check runs, but before a PR can merge."""
    pyflakes = pytest.importorskip("pyflakes")
    out = subprocess.run([sys.executable, "-m", "pyflakes", str(ROOT / "engine")], capture_output=True, text=True).stdout
    bad = [line for line in out.splitlines() if "undefined name" in line]
    assert not bad, "\n".join(bad)
