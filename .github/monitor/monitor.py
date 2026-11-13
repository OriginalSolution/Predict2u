"""Generic self-healing monitor driven by checks.json. Standard library only.

Each check: name, url, optional expect (200), contains (text), timeout (s), method,
headers_env ({header: ENV_NAME}), json_ok_field (JSON key that must be true),
redeploy_hook_env (env var with a deploy hook URL, POSTed when the check fails twice),
payment (true = also email when it goes down / comes back).

Predict2u additions (all optional per check):
  max_age_hours  the answer must carry a timestamp no older than this (data feeds)
  time_field     JSON key holding that timestamp (default "updatedAt")
  time_regex     or a regex whose first group is the timestamp (JS feeds)
  catchup        true = when this feed is stale/broken, dispatch the booking watchdog
                 (engine-watchdog.yml). The watchdog only re-runs a booking job whose
                 codes are missing and never books twice, so this fix is safe.
The monitor never merges PRs, never re-enables workflows, never touches payments or free mode.
"""
from __future__ import annotations

import concurrent.futures as cf
import datetime as dt
import json
import os
import re
import socket
import ssl
import time

from monitor_lib import Result, gh, http, load_state, now_iso, save_state, send_email, sync_issues, write_summary

HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG = json.load(open(os.path.join(HERE, "checks.json"), encoding="utf-8"))
state = load_state()
emails: list[tuple[str, str]] = []
catchup_reasons: list[str] = []


def feed_age_hours(c: dict, body: bytes):
    """Age in hours of the feed's own timestamp, or None when it has none we can read."""
    try:
        if c.get("time_regex"):
            m = re.search(c["time_regex"], body.decode("utf-8", "replace"))
            raw = m.group(1) if m else None
        else:
            raw = json.loads(body).get(c.get("time_field", "updatedAt"))
        t = dt.datetime.fromisoformat(str(raw).strip().replace("Z", "+00:00"))
        t = t if t.tzinfo else t.replace(tzinfo=dt.timezone.utc)
        return (dt.datetime.now(dt.timezone.utc) - t).total_seconds() / 3600
    except Exception:  # noqa: BLE001
        return None


def one(c: dict) -> Result:
    headers = {h: os.environ.get(env, "") for h, env in (c.get("headers_env") or {}).items()}
    if headers:
        headers.setdefault("Authorization", "Bearer " + next(iter(headers.values())))
    expect, timeout = int(c.get("expect", 200)), float(c.get("timeout", 20))
    for attempt in range(2):  # the second try also wakes sleeping free services
        status, body, err = http(c["url"], method=c.get("method", "GET"), headers=headers, timeout=timeout, retries=0)
        good = status == expect and (not c.get("contains") or c["contains"].encode() in body)
        if good and c.get("json_ok_field"):
            try:
                good = bool(json.loads(body).get(c["json_ok_field"]))
            except ValueError:
                good = False
        if good:
            break
        time.sleep(5)
    r = Result(c["name"], good, f"{status}" if good else f"answered {status or err} (expected {expect})")
    if good and c.get("max_age_hours"):
        age = feed_age_hours(c, body)
        if age is None:
            r.ok, r.detail = False, "answered but its timestamp could not be read"
        elif age > float(c["max_age_hours"]):
            r.ok, r.detail = False, f"stale: last updated {age:.1f} h ago (limit {c['max_age_hours']} h)"
        else:
            r.detail = f"{status}, updated {age:.1f} h ago"
    if not r.ok and c.get("catchup"):
        catchup_reasons.append(c["name"])
        r.fixes.append("asked the booking watchdog to re-book anything missing")
    if not r.ok and c.get("redeploy_hook_env") and os.environ.get(c["redeploy_hook_env"]):
        s, _, e = http(os.environ[c["redeploy_hook_env"]], method="POST", timeout=20, retries=0)
        r.fixes.append(f"asked for a redeploy ({s or e})")
    if c.get("payment"):
        key = "down:" + c["name"]
        if not good and not state.get(key):
            emails.append((f"Payments alert: {c['name']} is DOWN", f"{c['name']} failed at {now_iso()} UTC: {r.detail}"))
        if good and state.get(key):
            emails.append((f"Payments: {c['name']} is back up", f"{c['name']} answered again at {now_iso()} UTC."))
        state[key] = not good
    return r


def cert(host: str) -> Result:
    try:
        with socket.create_connection((host, 443), timeout=10) as sock, \
                ssl.create_default_context().wrap_socket(sock, server_hostname=host) as s:
            end = dt.datetime.strptime(s.getpeercert()["notAfter"], "%b %d %H:%M:%S %Y %Z").replace(tzinfo=dt.timezone.utc)
        days = (end - dt.datetime.now(dt.timezone.utc)).days
        return Result(f"HTTPS certificate: {host}", days >= 10, f"{days} days left")
    except Exception as e:  # noqa: BLE001
        return Result(f"HTTPS certificate: {host}", False, f"HTTPS failed ({type(e).__name__})")


def main() -> int:
    with cf.ThreadPoolExecutor(max_workers=8) as ex:
        results = list(ex.map(one, CONFIG.get("checks", []))) + list(ex.map(cert, CONFIG.get("certificates", [])))
    actions = []
    if catchup_reasons and os.environ.get("GITHUB_REPOSITORY") and os.environ.get("GITHUB_TOKEN"):
        s, _ = gh("POST", f"/repos/{os.environ['GITHUB_REPOSITORY']}/actions/workflows/engine-watchdog.yml/dispatches", {"ref": "main"})
        actions.append(f"dispatched the booking watchdog ({s}) for: {', '.join(catchup_reasons)}")
    actions += sync_issues(results)
    notes = [send_email(s, b) for s, b in emails]
    state["last_run"] = now_iso()
    save_state(state)
    write_summary(results, actions + notes)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
