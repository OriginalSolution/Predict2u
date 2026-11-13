#!/usr/bin/env python3
"""Booking watchdog: catch up any booking job that was missed or failed, on its own.

Runs from engine-watchdog.yml (every 30 min via the ticker, redundant GitHub crons, and
right after any booking workflow or the ticker itself finishes). No assistant, no human.

For every booking product it looks at the latest slot that is at least 20 minutes old and
still worth booking (its games have not started yet), then:

  * a run is queued or running          -> wait
  * published data shows the codes      -> ok
  * data missing / run never succeeded  -> re-dispatch the workflow, with backoff
                                           (10, 30, 60 min) and at most 3 tries per slot

No double booking:
  * products with a reliable "codes are on the site" test are only re-run when that test
    says the codes are missing; a run that succeeded yet left nothing is re-run with
    force=true at most `max_forced` times;
  * products without such a test (GG, NYSM, NT, ... can legitimately book nothing) are only
    re-run when no run of their real job succeeded, so the run-once gate (p2u_gate.py)
    still decides and a successful slot is never booked again.

It also keeps the clock alive: restarts the on-time ticker when none is running, and
re-enables engine workflows GitHub switched off for inactivity (never ones disabled by hand).
Standard library only. Times are UTC (= Africa/Accra).
"""
from __future__ import annotations

import datetime as dt
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

API = os.environ.get("GITHUB_API_URL", "https://api.github.com")
REPO = os.environ.get("GITHUB_REPOSITORY", "OriginalSolution/Predict2u")
ROOT = Path(os.environ.get("REPO_DIR") or Path(__file__).resolve().parents[2])
MIN_AGE = dt.timedelta(minutes=20)       # leave the ticker's own slot alone
MAX_ATTEMPTS = 3                         # real-job runs per slot, including the scheduled one
BACKOFF_MIN = (10, 30, 60)               # wait after the n-th finished attempt before the next
DRY = os.environ.get("P2U_WATCHDOG_DRY", "").lower() in ("1", "true")

# key, workflow, slot HH:MM, real job name, hours after the slot it is still worth booking,
# data check name (None = no reliable check), forced re-runs allowed when it succeeded but data is missing,
# workflow it must wait for, whether the workflow takes a `force` input
PRODUCTS = [
    dict(key="favourites", wf="engine-fav-leagues.yml", at="06:00", job="fav", valid_h=11, check="fav", max_forced=1),
    dict(key="code-of-the-day", wf="engine-strategy-master.yml", at="06:00", job="master", valid_h=11),
    dict(key="morning-tips", wf="engine-morning.yml", at="07:00", job="morning", valid_h=9, check="morning", max_forced=1),
    dict(key="dc-shield", wf="engine-shield.yml", at="21:00", job="shield", valid_h=13),
    dict(key="m1m2", wf="engine-m1m2.yml", at="21:45", job="m1m2", valid_h=13),
    dict(key="daily-slips", wf="engine-daily.yml", at="22:00", job="daily", valid_h=14, check="daily", max_forced=1),
    dict(key="hot-picks", wf="engine-hot-picks.yml", at="22:00", job="hot", valid_h=16, check="hot", max_forced=1,
         after="engine-daily.yml", force_input=False, own_slot=False),
    dict(key="strategies", wf="engine-strategies.yml", at="22:30", job="strategies", valid_h=13),
    dict(key="gg", wf="engine-gg.yml", at="23:10", job="gg", valid_h=13),
    dict(key="nysm", wf="engine-nysm.yml", at="23:30", job="nysm", valid_h=12),
    dict(key="nt-tomorrow", wf="engine-nt-tomorrow.yml", at="23:50", job="nt", valid_h=12),
]
# Workflows the booking chain needs. Only these are ever re-enabled, and only from "disabled_inactivity".
CRITICAL = sorted({p["wf"] for p in PRODUCTS} | {"engine-ticker.yml", "engine-watchdog.yml", "engine-health.yml",
                                                 "engine-settle.yml", "sportybet-odds.yml", "monitor.yml"})


# ---------------------------------------------------------------- GitHub
def gh(method: str, path: str, body: dict | None = None):
    req = urllib.request.Request(API + path, method=method, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Authorization": f"Bearer {os.environ.get('GH_TOKEN') or os.environ.get('GITHUB_TOKEN', '')}",
                                          "Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"})
    with urllib.request.urlopen(req, timeout=30) as r:
        raw = r.read()
        return json.loads(raw) if raw else {}


def gh_retry(method: str, path: str, body: dict | None = None, tries: int = 3):
    for i in range(tries):
        try:
            return gh(method, path, body)
        except urllib.error.HTTPError as e:
            if e.code < 500 and e.code != 429 or i == tries - 1:
                raise
        except Exception:
            if i == tries - 1:
                raise
        time.sleep(5 * (i + 1))


def parse_ts(v):
    try:
        t = dt.datetime.fromisoformat(str(v).strip().replace("Z", "+00:00"))
        return t if t.tzinfo else t.replace(tzinfo=dt.timezone.utc)
    except Exception:
        return None


# ---------------------------------------------------------------- published data
def _load(name: str):
    try:
        return json.loads((ROOT / name).read_text())
    except Exception:
        return None


def _has_code(codes) -> bool:
    """True when a codes block holds at least one booked code (dict, list or nested shapes)."""
    if isinstance(codes, str):
        return bool(codes.strip())
    if isinstance(codes, dict):
        if isinstance(codes.get("code"), str) and codes["code"]:
            return True
        return any(_has_code(v) for k, v in codes.items() if k not in ("matches", "legs", "totalOdds", "link", "status"))
    if isinstance(codes, list):
        return any(_has_code(x) for x in codes)
    return False


def check_daily(slot: dt.datetime) -> bool:
    """The 22:00 daily books the home code: homeCode.bookedAt after the slot and a code present."""
    hc = (_load("home-picks.json") or {}).get("homeCode") or {}
    t = parse_ts(hc.get("bookedAt"))
    return bool(t and t >= slot - dt.timedelta(hours=1) and _has_code(hc.get("codes")))


def check_hot(slot: dt.datetime) -> bool:
    """Hot Picks slips booked after the slot (updatedAt moves on every settle, so use bookedAt)."""
    doc = _load("hot-picks.json") or {}
    for s in doc.get("slips") or []:
        t = parse_ts(s.get("bookedAt"))
        if t and t >= slot - dt.timedelta(hours=1) and _has_code(s.get("codes")):
            return True
    return False


def check_fav(slot: dt.datetime) -> bool:
    day = slot.date().isoformat()
    dm = (((_load("home-picks.json") or {}).get("homeCode") or {}).get("dayMasters") or {}).get(day) or {}
    if dm.get("codes"):
        return True
    return any(_has_code((p or {}).get("codes")) for p in (dm.get("parts") or dm.get("slips") or []))


def check_morning(slot: dt.datetime) -> bool:
    doc = _load(f"engine/data/sb-morning/{slot.date().isoformat()}.json") or {}
    return doc.get("date") == slot.date().isoformat() and bool(doc.get("slips") or doc.get("picks"))


CHECKS = {"daily": check_daily, "hot": check_hot, "fav": check_fav, "morning": check_morning}


# ---------------------------------------------------------------- decisions
def last_slot(at: str, now: dt.datetime) -> dt.datetime:
    hh, mm = (int(x) for x in at.split(":"))
    s = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
    if s > now - MIN_AGE:
        s -= dt.timedelta(days=1)
    return s


def runs_for(wf: str, since: dt.datetime) -> list[dict]:
    q = urllib.parse.quote(">=" + since.strftime("%Y-%m-%dT%H:%M:%SZ"))
    runs = gh_retry("GET", f"/repos/{REPO}/actions/workflows/{wf}/runs?per_page=50&created={q}").get("workflow_runs") or []
    return [r for r in runs if "dry run" not in (r.get("display_title") or "").lower()]


def job_result(run: dict, job: str):
    """Conclusion of the real job in a finished run, or None when it never ran (gated / skipped)."""
    jobs = gh_retry("GET", f"/repos/{REPO}/actions/runs/{run['id']}/jobs?per_page=50").get("jobs") or []
    for j in jobs:
        if j.get("name") == job and j.get("conclusion") not in (None, "skipped"):
            return j["conclusion"], parse_ts(j.get("completed_at")) or parse_ts(run.get("updated_at"))
    return None


def decide(p: dict, now: dt.datetime, runs: list[dict], results: dict, published, upstream_busy: bool = False):
    """Pure decision. results: run id -> (conclusion, completed_at) for finished runs whose real job ran.
    Returns (action, reason) with action in ok | wait | dispatch | dispatch-force | give-up | expired."""
    slot = last_slot(p["at"], now)
    if now > slot + dt.timedelta(hours=p["valid_h"]):
        return "expired", f"slot {slot:%m-%d %H:%M} is past its booking window"
    if upstream_busy:
        return "wait", f"waiting for {p.get('after')} to finish"
    if any(r.get("status") != "completed" for r in runs):
        return "wait", "a run is queued or running"
    if published is True:
        return "ok", f"codes for the {slot:%m-%d %H:%M} slot are published"
    done = sorted((v for v in results.values()), key=lambda v: v[1] or slot)
    successes = sum(1 for c, _ in done if c == "success")
    attempts = len(done)
    if published is None and successes:
        return "ok", f"{p['wf']} succeeded for the {slot:%m-%d %H:%M} slot"
    if published is False and successes:
        if successes > p.get("max_forced", 0):
            return "give-up", f"ran {successes}x successfully but its codes are still not on the site"
        action = "dispatch-force"
    else:
        action = "dispatch"
    if attempts >= MAX_ATTEMPTS + (1 if action == "dispatch-force" else 0):
        return "give-up", f"{attempts} attempts for the {slot:%m-%d %H:%M} slot all failed"
    if done:
        wait = BACKOFF_MIN[min(attempts, len(BACKOFF_MIN)) - 1]
        last = done[-1][1]
        if last and now - last < dt.timedelta(minutes=wait):
            return "wait", f"backoff: last attempt finished {int((now - last).total_seconds() // 60)} min ago (waits {wait})"
    why = "codes missing" if published is False else "no successful run"
    return action, f"{why} for the {slot:%m-%d %H:%M} slot (attempt {attempts + 1})"


def dispatch(p: dict, force: bool) -> None:
    body = {"ref": "main"}
    if force and p.get("force_input", True):
        body["inputs"] = {"force": "true"}
    gh_retry("POST", f"/repos/{REPO}/actions/workflows/{p['wf']}/dispatches", body)


# ---------------------------------------------------------------- clock + registry
def ticker_live() -> int:
    n = 0
    for status in ("in_progress", "queued"):
        n += int(gh_retry("GET", f"/repos/{REPO}/actions/workflows/engine-ticker.yml/runs?status={status}&per_page=5").get("total_count") or 0)
    return n


def keep_ticker_alive(log) -> None:
    if ticker_live():
        log("ticker: running")
        return
    last = (gh_retry("GET", f"/repos/{REPO}/actions/workflows/engine-ticker.yml/runs?per_page=1").get("workflow_runs") or [{}])[0]
    ended = parse_ts(last.get("updated_at"))
    if ended and dt.datetime.now(dt.timezone.utc) - ended < dt.timedelta(minutes=3):
        time.sleep(90)  # the finished ticker's own hand-over step may be starting the next one
        if ticker_live():
            log("ticker: handed over by itself")
            return
    if DRY:
        log("ticker: NOT running (dry run, not restarted)")
        return
    gh_retry("POST", f"/repos/{REPO}/actions/workflows/engine-ticker.yml/dispatches", {"ref": "main"})
    log("ticker: was not running -> restarted")


def keep_enabled(log) -> None:
    wfs = gh_retry("GET", f"/repos/{REPO}/actions/workflows?per_page=100").get("workflows") or []
    for w in wfs:
        name = Path(w["path"]).name
        if name in CRITICAL and w.get("state") == "disabled_inactivity":
            if not DRY:
                gh_retry("PUT", f"/repos/{REPO}/actions/workflows/{w['id']}/enable")
            log(f"registry: {name} was disabled for inactivity -> re-enabled")


# ---------------------------------------------------------------- issue
ISSUE_TITLE = "[watchdog] Booking catch-up needs attention"


def sync_issue(problems: list[str], log) -> None:
    if DRY:
        return
    found = gh_retry("GET", f"/repos/{REPO}/issues?state=open&labels=monitor&per_page=100") or []
    issue = next((i for i in found if i.get("title") == ISSUE_TITLE and "pull_request" not in i), None)
    url = f"{os.environ.get('GITHUB_SERVER_URL', 'https://github.com')}/{REPO}/actions/runs/{os.environ.get('GITHUB_RUN_ID', '')}"
    if problems:
        body = ("The booking watchdog could not get these codes booked by itself:\n\n" + "\n".join(f"- {x}" for x in problems)
                + f"\n\nLast seen: {dt.datetime.now(dt.timezone.utc):%Y-%m-%d %H:%M} UTC - [run]({url})\n\nCloses by itself when they are booked or the slot passes.")
        if issue:
            gh_retry("PATCH", f"/repos/{REPO}/issues/{issue['number']}", {"body": body})
        else:
            try:
                gh("POST", f"/repos/{REPO}/labels", {"name": "monitor", "color": "d93f0b"})
            except Exception:
                pass
            gh_retry("POST", f"/repos/{REPO}/issues", {"title": ISSUE_TITLE, "body": body, "labels": ["monitor"]})
        log(f"issue: {len(problems)} open problem(s)")
    elif issue:
        gh_retry("POST", f"/repos/{REPO}/issues/{issue['number']}/comments", {"body": f"All booking products are fine again - [run]({url}). Closing."})
        gh_retry("PATCH", f"/repos/{REPO}/issues/{issue['number']}", {"state": "closed", "state_reason": "completed"})
        log("issue: closed (all fine)")


# ---------------------------------------------------------------- main
def main() -> int:
    lines: list[str] = []

    def log(msg: str) -> None:
        print(msg, flush=True)
        lines.append(msg)

    now = dt.datetime.now(dt.timezone.utc)
    for step in (keep_enabled, keep_ticker_alive):
        try:
            step(log)
        except Exception as e:
            log(f"{step.__name__}: failed ({e})")
    problems: list[str] = []
    busy: dict[str, bool] = {}
    for p in PRODUCTS:
        slot = last_slot(p["at"], now)
        try:
            if now > slot + dt.timedelta(hours=p["valid_h"]):
                log(f"{p['key']}: idle (slot {slot:%m-%d %H:%M} past its window)")
                continue
            since = slot - dt.timedelta(hours=6) if p.get("own_slot", True) else slot - dt.timedelta(minutes=30)
            runs = runs_for(p["wf"], since)
            busy[p["wf"]] = any(r.get("status") != "completed" for r in runs)
            results = {}
            for r in runs:
                if r.get("status") == "completed":
                    jr = job_result(r, p["job"])
                    if jr:
                        results[r["id"]] = jr
            chk = CHECKS.get(p.get("check") or "")
            published = chk(slot) if chk else None
            upstream = bool(p.get("after")) and busy.get(p["after"], False)
            action, why = decide(p, now, runs, results, published, upstream)
            if action.startswith("dispatch"):
                if not DRY:
                    dispatch(p, action == "dispatch-force")
                    # a fresh daily re-books Hot Picks too, so Hot Picks waits for it
                    busy[p["wf"]] = True
                log(f"{p['key']}: {why} -> {'would dispatch' if DRY else 'dispatched'} {p['wf']}{' (force)' if action == 'dispatch-force' else ''}")
            else:
                log(f"{p['key']}: {action} - {why}")
                if action == "give-up":
                    problems.append(f"{p['key']} ({p['wf']}): {why}")
        except Exception as e:
            log(f"{p['key']}: check failed ({e})")
    try:
        sync_issue(problems, log)
    except Exception as e:
        log(f"issue sync failed ({e})")
    out = os.environ.get("GITHUB_STEP_SUMMARY")
    if out:
        with open(out, "a") as f:
            f.write("## Booking watchdog\n\n" + "\n".join(f"- {x}" for x in lines) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
