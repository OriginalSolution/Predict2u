#!/usr/bin/env python3
"""Run-once-per-slot gate for scheduled Predict2u workflows.

GitHub's cron on this repo fires hours late and sometimes twice, while the
on-time scheduler (engine-ticker.yml) dispatches the same workflow at the
right minute. This gate makes the late duplicate a cheap no-op so codes are
not booked twice and emails are not sent twice.

  python3 .github/scripts/p2u_gate.py --at 22:00 --job daily

Writes run=true|false to $GITHUB_OUTPUT. It says false when, inside the slot
window (6h before the scheduled time to 18h after), an older run of this
workflow is still in flight, or already finished with the real job (--job)
succeeding. Dry runs are ignored. Any API error fails open (run=true).
"""
from __future__ import annotations
import argparse, datetime as dt, json, os, sys, urllib.request

API = os.environ.get("GITHUB_API_URL", "https://api.github.com")


def gh(path: str):
    req = urllib.request.Request(API + path, headers={
        "Authorization": f"Bearer {os.environ['GH_TOKEN']}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    })
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def slot_window(at: str, now: dt.datetime, window_h: float = 6):
    hh, mm = (int(x) for x in at.split(":"))
    slot = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
    if now < slot - dt.timedelta(hours=6):
        slot -= dt.timedelta(days=1)
    return slot, slot - dt.timedelta(hours=window_h)


def decide(at: str, job: str, window_h: float = 6) -> tuple[bool, str]:
    repo = os.environ["GITHUB_REPOSITORY"]
    me = int(os.environ["GITHUB_RUN_ID"])
    now = dt.datetime.now(dt.timezone.utc)
    slot, start = slot_window(at, now, window_h)
    wid = gh(f"/repos/{repo}/actions/runs/{me}")["workflow_id"]
    since = start.strftime("%Y-%m-%dT%H:%M:%SZ")
    runs = gh(f"/repos/{repo}/actions/workflows/{wid}/runs?per_page=50&created=%3E%3D{since}")["workflow_runs"]
    for r in sorted(runs, key=lambda r: r["id"]):
        if r["id"] >= me or "dry run" in (r.get("display_title") or "").lower():
            continue
        if r["status"] != "completed":
            return False, f"older run {r['html_url']} is still {r['status']} for slot {slot:%F %H:%M}Z"
        jobs = gh(f"/repos/{repo}/actions/runs/{r['id']}/jobs?per_page=50")["jobs"]
        if any(j["name"] == job and j.get("conclusion") == "success" for j in jobs):
            return False, f"slot {slot:%F %H:%M}Z already done by {r['html_url']}"
    return True, f"no successful run yet for slot {slot:%F %H:%M}Z"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--at", required=True, help="scheduled time HH:MM UTC")
    ap.add_argument("--job", required=True, help="name of the job that does the real work")
    ap.add_argument("--window-hours", type=float, default=6, help="how far before the slot a run still counts (use 1 for workflows with several slots a day)")
    a = ap.parse_args()
    if os.environ.get("P2U_GATE_BYPASS", "").lower() in ("1", "true"):
        ok, why = True, "bypass (manual force / dry run)"
    else:
        try:
            ok, why = decide(a.at, a.job, a.window_hours)
        except Exception as e:  # never block a run because the API hiccuped
            ok, why = True, f"gate check failed open: {e}"
    print(("RUN: " if ok else "SKIP: ") + why)
    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a") as f:
            f.write(f"run={'true' if ok else 'false'}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
