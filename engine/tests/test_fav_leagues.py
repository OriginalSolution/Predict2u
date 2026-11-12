"""fav_leagues: stale day-master codes are dropped, live ones kept (no network)."""
import datetime as dt
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "engine" / "vendor"))
import fav_leagues as FL  # noqa: E402


def test_live_day_masters_drops_past_and_kicked_off():
    now = dt.datetime(2026, 11, 12, 15, 0, tzinfo=dt.timezone.utc)
    dm = {
        "2026-11-11": {"codes": {"sportybet": [{"code": "OLD"}]}, "picks": [{"date": "2026-11-11", "ko": "20:00"}]},
        "2026-11-12": {"codes": {"sportybet": [{"code": "GONE"}]}, "picks": [{"date": "2026-11-12", "ko": "12:00"}]},
        "2026-11-13": {"codes": {"sportybet": [{"code": "LIVE"}]}, "picks": [{"date": "2026-11-13", "ko": "18:00"}]},
    }
    assert list(FL.live_day_masters(dm, now)) == ["2026-11-13"]


def test_pipeline_has_fav_command_and_ticker_slot():
    assert '"fav"' in (ROOT / "engine" / "pipeline.py").read_text()
    assert "engine-fav-leagues.yml" in (ROOT / ".github" / "scripts" / "p2u_ticker.py").read_text()
