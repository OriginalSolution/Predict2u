#!/usr/bin/env python3
"""On-time dispatcher for the Predict2u workflows (engine-ticker.yml).

GitHub's own cron on this repo starts runs 4-8 hours late and drops many of
them (the 07:00 morning job ran at 14:50, the 22:00 daily at 02:43, the
"every 2h" settle ran 3 times a day). workflow_dispatch starts immediately,
so this job stays alive ~5h40m, checks the clock every minute, dispatches
whatever is due, then dispatches its own next run.

Rules:
- A slot is dispatched only within GRACE minutes after its time, and only when
  no run of that workflow was created since the slot. Nothing is caught up
  hours late; the (late) GitHub cron stays as the fallback, and p2u_gate.py
  makes that fallback a no-op once the on-time run has succeeded.
- One ticker at a time: a new ticker waits a few minutes for older tickers
  to finish and exits if one is still alive.
Times are UTC (= Africa/Accra).
"""
from __future__ import annotations
import datetime as dt, json, os, sys, time, urllib.error, urllib.parse, urllib.request

API = os.environ.get("GITHUB_API_URL", "https://api.github.com")
REPO = os.environ["GITHUB_REPOSITORY"]
REF = os.environ.get("P2U_TICKER_REF", "main")
GRACE = int(os.environ.get("P2U_TICKER_GRACE_MIN", "15"))
LIFETIME = int(os.environ.get("P2U_TICKER_SECONDS", str(5 * 3600 + 40 * 60)))
SELF = "engine-ticker.yml"

# (workflow file, minute, hour, day-of-week)  cron-style fields: "*", "*/n", "a,b"
SCHEDULE = [
    ("engine-morning.yml", "0", "7", "*"),          # SportyBet morning markets + master (books)
    ("engine-shield.yml", "0", "21", "*"),          # DC Shield Goals (books)
    ("engine-daily.yml", "0", "22", "*"),           # daily collect, book, publish (books)
    ("engine-strategies.yml", "30", "22", "*"),     # three strategies + Verzzify banker (books)
    ("engine-settle.yml", "45", "1", "*"),
    ("engine-settle.yml", "15", "*/2", "*"),
    ("sportybet-odds.yml", "19", "*/3", "*"),
    ("engine-self-heal.yml", "15", "6,14,22", "*"),
    ("daymasters-guard.yml", "10,40", "*", "*"),
    ("engine-refresh.yml", "25", "*", "*"),         # news hub + live-scores snapshot
    ("daily-picks-email.yml", "15", "0", "*"),
    ("results-email.yml", "30", "0", "*"),
    ("tracker-email.yml", "45", "0", "*"),
    ("post-social.yml", "50", "0", "*"),
    ("weekly-digest.yml", "0", "18", "0"),          # Sundays
]


def api(method: str, path: str, body: dict | None = None):
    req = urllib.request.Request(API + path, method=method, data=json.dumps(body).encode() if body is not None else None, headers={
        "Authorization": f"Bearer {os.environ['GH_TOKEN']}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    })
    with urllib.request.urlopen(req, timeout=30) as r:
        raw = r.read()
        return json.loads(raw) if raw else {}


def field_ok(spec: str, value: int) -> bool:
    for part in spec.split(","):
        if part == "*" or (part.startswith("*/") and value % int(part[2:]) == 0) or (part.isdigit() and int(part) == value):
            return True
    return False


def matches(t: dt.datetime, minute: str, hour: str, dow: str) -> bool:
    return field_ok(minute, t.minute) and field_ok(hour, t.hour) and field_ok(dow, (t.weekday() + 1) % 7)


def due_slot(now: dt.datetime, minute: str, hour: str, dow: str):
    base = now.replace(second=0, microsecond=0)
    for back in range(GRACE + 1):
        t = base - dt.timedelta(minutes=back)
        if matches(t, minute, hour, dow):
            return t
    return None


def runs_since(wf: str, since: dt.datetime) -> int:
    q = urllib.parse.quote(">=" + since.strftime("%Y-%m-%dT%H:%M:%SZ"))
    return int(api("GET", f"/repos/{REPO}/actions/workflows/{wf}/runs?per_page=1&created={q}").get("total_count") or 0)


def dispatch(wf: str):
    api("POST", f"/repos/{REPO}/actions/workflows/{wf}/dispatches", {"ref": REF})


def log(msg: str):
    print(f"{dt.datetime.now(dt.timezone.utc):%Y-%m-%d %H:%M:%S}Z {msg}", flush=True)


def other_tickers_alive() -> bool:
    me = int(os.environ["GITHUB_RUN_ID"])
    for status in ("in_progress", "queued"):
        runs = api("GET", f"/repos/{REPO}/actions/workflows/{SELF}/runs?per_page=20&status={status}").get("workflow_runs") or []
        if any(r["id"] < me for r in runs):
            return True
    return False


def main() -> int:
    for _ in range(12):  # up to 4 minutes for the previous ticker to hand over
        try:
            if not other_tickers_alive():
                break
        except Exception as e:
            log(f"could not list tickers ({e}); assuming none alive")
            break
        time.sleep(20)
    else:
        log("another ticker is alive; exiting")
        return 0
    end = time.time() + LIFETIME
    fired: set[tuple[str, str]] = set()
    log(f"ticker up for {LIFETIME // 60} min, grace {GRACE} min, {len(SCHEDULE)} slots")
    while time.time() < end:
        now = dt.datetime.now(dt.timezone.utc)
        for wf, minute, hour, dow in SCHEDULE:
            slot = due_slot(now, minute, hour, dow)
            if slot is None:
                continue
            key = (wf, slot.isoformat())
            if key in fired:
                continue
            try:
                n = runs_since(wf, slot)
                if n:
                    log(f"{wf} slot {slot:%H:%M}Z already has {n} run(s); not dispatching")
                else:
                    dispatch(wf)
                    log(f"dispatched {wf} for slot {slot:%H:%M}Z")
                fired.add(key)
            except urllib.error.HTTPError as e:
                log(f"{wf}: HTTP {e.code} {e.read()[:200]!r}; will retry next minute")
            except Exception as e:
                log(f"{wf}: {e}; will retry next minute")
        time.sleep(max(5, 60 - dt.datetime.now(dt.timezone.utc).second))
    log("lifetime reached; handing over to the next ticker")
    # Only a ticker that lived its full span hands over, so a crash can never
    # turn into a tight dispatch loop (the cron restart covers that case).
    open(os.environ.get("GITHUB_OUTPUT", os.devnull), "a").write("handoff=true\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
