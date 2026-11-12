"""Health check: sandbox blocks writes, code walker, workflow command discovery."""
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from engine import health  # noqa: E402


def _sandboxed(code):
    env = health.sandbox_env()
    return subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True, timeout=60)


def test_guard_blocks_post_and_smtp():
    r = _sandboxed(
        "import urllib.request, smtplib\n"
        "try:\n urllib.request.urlopen(urllib.request.Request('https://example.invalid/x', data=b'1'))\n print('POST-ALLOWED')\n"
        "except Exception as e:\n print('POST-BLOCKED', type(e).__name__)\n"
        "try:\n smtplib.SMTP('localhost')\n print('SMTP-ALLOWED')\n"
        "except Exception as e:\n print('SMTP-BLOCKED')\n")
    assert "POST-BLOCKED" in r.stdout and "SMTP-BLOCKED" in r.stdout, r.stdout + r.stderr


def test_guard_curl_blocks_post():
    env = health.sandbox_env()
    r = subprocess.run(["curl", "-s", "-X", "POST", "-d", "a=1", "https://example.invalid/"], env=env, capture_output=True, text=True, timeout=30)
    assert r.returncode == 0 and r.stdout.strip() == "{}"


def test_sandbox_strips_secrets():
    os.environ["P2U_TEST_TOKEN"] = "x"
    try:
        assert "P2U_TEST_TOKEN" not in health.sandbox_env()
    finally:
        del os.environ["P2U_TEST_TOKEN"]


def test_walk_codes_finds_all_shapes():
    out = []
    node = {"date": "2030-01-01", "slips": [
        {"sportybet": "ABC123", "msport": {"code": "M1", "parts": [{"code": "M2"}]}},
        {"code": "BK9", "book": "betika", "status": "won"},
        {"betpawa": [{"code": "P1"}, "P2"]},
    ]}
    health.walk_codes(node, {}, out, "t.json")
    got = {(b, c) for b, c, _, _ in out}
    assert {("sportybet", "ABC123"), ("msport", "M1"), ("msport", "M2"), ("betika", "BK9"), ("betpawa", "P1"), ("betpawa", "P2")} <= got
    assert all(ctx.get("date") == "2030-01-01" for _, _, ctx, _ in out)


def test_registry_discovers_engine_commands():
    wfs = health.load_workflows()
    cmds = [c for w in wfs.values() for c in w["commands"]]
    assert any("engine.pipeline" in c for c in cmds)
    assert "engine-health.yml" in wfs
    # every scheduled, active workflow is on the on-time ticker
    on_ticker = {wf for wf, *_ in health.ticker_schedule()}
    assert "engine-health.yml" in on_ticker


def test_to_dry_adds_dry_run():
    assert health.to_dry("-m engine.pipeline daily")[-1] == "--dry-run"
    assert "--dry-run" not in health.to_dry("-m engine.pipeline settle")
