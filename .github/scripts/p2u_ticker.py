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
- The live ticker follows main. Every minute it reads main's HEAD; when it
  moves, it re-reads SCHEDULE from this file at main, so a slot merged at
  22:07 is on the clock by 22:08 (Nov 12: the PR #17 night slots were merged
  while a 19:33 ticker held the old list and nothing started them).
- If the ticker logic itself changed on main, the live ticker dispatches a
  fresh ticker and keeps working until that one takes over.
- One ticker at a time. A new ticker cancels older tickers that run different
  ticker logic (it is the newer code) and starts at once, so there is no gap.
  An older ticker with the same logic already follows main, so the new one
  waits a few minutes for it to hand over and exits if it is still alive.
  A running ticker also yields to a same-logic ticker with a lower run id.
Times are UTC (= Africa/Accra).
"""
from __future__ import annotations
import ast, base64, datetime as dt, hashlib, json, os, sys, time, urllib.error, urllib.parse, urllib.request
from pathlib import Path

API = os.environ.get("GITHUB_API_URL", "https://api.github.com")
REPO = os.environ["GITHUB_REPOSITORY"]
REF = os.environ.get("P2U_TICKER_REF", "main")
GRACE = int(os.environ.get("P2U_TICKER_GRACE_MIN", "15"))
LIFETIME = int(os.environ.get("P2U_TICKER_SECONDS", str(5 * 3600 + 40 * 60)))
SELF = "engine-ticker.yml"
SELF_PATH = ".github/scripts/p2u_ticker.py"

# (workflow file, minute, hour, day-of-week)  cron-style fields: "*", "*/n", "a,b"
SCHEDULE = [
    ("engine-fav-leagues.yml", "0", "6", "*"),      # favourites by league: stats + day-master codes (books)
    ("engine-strategy-master.yml", "0", "6", "*"),  # Code of the Day from the night's strategy codes (books)
    ("engine-morning.yml", "0", "7", "*"),          # SportyBet morning markets + master (books)
    ("engine-shield.yml", "0", "21", "*"),          # DC Shield Goals (books)
    ("engine-m1m2.yml", "45", "21", "*"),           # M1/M2 and Safest market (books)
    ("engine-daily.yml", "0", "22", "*"),           # daily collect, book, publish (books)
    ("engine-strategies.yml", "30", "22", "*"),     # three strategies + Verzzify banker (books)
    ("engine-gg.yml", "10", "23", "*"),             # GG / BTTS Yes for the next Accra day (books)
    ("engine-nysm.yml", "30", "23", "*"),           # NYSM v2 Main, Conservative, TS2+ (books)
    ("engine-nt-tomorrow.yml", "50", "23", "*"),    # NerdyTips Tomorrow, trust 5.0+, Agree only (books)
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
    ("engine-health.yml", "30", "7", "*"),         # health: post-run check of the night/morning jobs
    ("engine-health.yml", "0", "18", "*"),         # health: preflight — dry-run every strategy for tomorrow
    ("engine-health.yml", "15", "23", "*"),        # health: post-run check of the evening booking jobs
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


def read_schedule(src: str) -> list[tuple[str, str, str, str]]:
    """SCHEDULE from ticker source, without executing it."""
    for node in ast.parse(src).body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "SCHEDULE" for t in node.targets):
            rows = ast.literal_eval(node.value)
            out = []
            for row in rows:
                wf, minute, hour, dow = (str(x) for x in row)
                if not wf.endswith(".yml"):
                    raise ValueError(f"bad workflow {wf!r}")
                for spec in (minute, hour, dow):
                    for part in spec.split(","):
                        if not (part == "*" or part.isdigit() or (part.startswith("*/") and part[2:].isdigit() and int(part[2:]) > 0)):
                            raise ValueError(f"bad field {spec!r} for {wf}")
                out.append((wf, minute, hour, dow))
            if not out:
                raise ValueError("empty SCHEDULE")
            return out
    raise ValueError("no SCHEDULE in ticker source")


def logic_id(src: str) -> str:
    """Fingerprint of the ticker logic with the SCHEDULE literal blanked out,
    so a schedule-only edit is hot-reloaded and a logic edit hands over."""
    lines = src.splitlines()
    for node in ast.parse(src).body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "SCHEDULE" for t in node.targets):
            lines[node.lineno - 1:node.end_lineno] = ["SCHEDULE = ..."]
            break
    return hashlib.sha1("\n".join(lines).encode()).hexdigest()[:12]


def source_at(ref: str) -> str:
    doc = api("GET", f"/repos/{REPO}/contents/{SELF_PATH}?ref={urllib.parse.quote(ref)}")
    return base64.b64decode(doc["content"]).decode()


def main_head() -> str:
    return api("GET", f"/repos/{REPO}/commits/{urllib.parse.quote(REF)}")["sha"]


_logic_cache: dict[str, str | None] = {}


def logic_at(sha: str) -> str | None:
    if sha not in _logic_cache:
        try:
            _logic_cache[sha] = logic_id(source_at(sha))
        except Exception as e:
            log(f"could not read ticker source at {sha[:8]} ({e})")
            _logic_cache[sha] = None
    return _logic_cache[sha]


def live_tickers() -> list[dict]:
    """Other ticker runs that are queued or running."""
    me = int(os.environ["GITHUB_RUN_ID"])
    out = []
    for status in ("in_progress", "queued"):
        runs = api("GET", f"/repos/{REPO}/actions/workflows/{SELF}/runs?per_page=20&status={status}").get("workflow_runs") or []
        out += [r for r in runs if r["id"] != me]
    return out


def cancel(run_id: int):
    api("POST", f"/repos/{REPO}/actions/runs/{run_id}/cancel")


def take_over(my_logic: str) -> bool:
    """True when this ticker should run. Cancels older tickers on other logic."""
    me = int(os.environ["GITHUB_RUN_ID"])
    for _ in range(12):  # up to 4 minutes for a same-logic predecessor to hand over
        older = [r for r in live_tickers() if r["id"] < me]
        same = []
        for r in older:
            theirs = logic_at(r["head_sha"])
            if theirs == my_logic:
                same.append(r)
            else:
                # Older logic (e.g. no schedule reload): this ticker is the newer
                # code, so it replaces that run instead of leaving it in charge.
                log(f"cancelling older ticker run {r['id']} (sha {r['head_sha'][:8]}, logic {theirs}); taking over")
                try:
                    cancel(r["id"])
                except Exception as e:
                    log(f"could not cancel run {r['id']} ({e})")
        if not same:
            return True
        time.sleep(20)
    log("an older ticker with the same logic is alive and follows main; exiting")
    return False


class Plan:
    """The slot list, kept in step with main."""

    def __init__(self, my_logic: str, local_src: str):
        self.my_logic = my_logic
        self.schedule = read_schedule(local_src)
        self.head = os.environ.get("GITHUB_SHA", "")
        self.handoff_for: str | None = None

    def refresh(self) -> None:
        try:
            head = main_head()
        except Exception as e:
            log(f"could not read {REF} HEAD ({e}); keeping {len(self.schedule)} slots")
            return
        if head == self.head:
            return
        try:
            src = source_at(head)
            schedule = read_schedule(src)
            logic = logic_id(src)
        except Exception as e:
            log(f"{REF} moved to {head[:8]} but its schedule is unreadable ({e}); keeping the current one")
            self.head = head
            return
        self.head = head
        _logic_cache[head] = logic
        if schedule != self.schedule:
            added = sorted(set(schedule) - set(self.schedule))
            removed = sorted(set(self.schedule) - set(schedule))
            log(f"{REF} {head[:8]}: schedule reloaded ({len(schedule)} slots; +{added} -{removed})")
            self.schedule = schedule
        if logic != self.my_logic and self.handoff_for != logic:
            # The new ticker cancels this one when it starts (see take_over), so
            # this run keeps dispatching until then and there is no gap.
            self.handoff_for = logic
            try:
                dispatch(SELF)
                log(f"ticker logic changed on {REF} ({self.my_logic} -> {logic}); dispatched a fresh ticker to take over")
            except Exception as e:
                self.handoff_for = None
                log(f"could not dispatch a fresh ticker ({e}); will retry")

    def should_yield(self) -> bool:
        """Two same-logic tickers can only overlap when an older queued run
        started late. The lower run id keeps the clock; the other leaves."""
        me = int(os.environ["GITHUB_RUN_ID"])
        try:
            for r in live_tickers():
                if r["id"] < me and r["status"] == "in_progress" and logic_at(r["head_sha"]) == self.my_logic:
                    log(f"older ticker run {r['id']} runs the same logic; leaving the clock to it")
                    return True
        except Exception:
            pass
        return False


def tick(plan: Plan, now: dt.datetime, fired: set) -> None:
    for wf, minute, hour, dow in plan.schedule:
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


def main() -> int:
    local_src = Path(__file__).read_text()
    my_logic = logic_id(local_src)
    try:
        if not take_over(my_logic):
            return 0
    except Exception as e:
        log(f"could not list tickers ({e}); assuming none alive")
    plan = Plan(my_logic, local_src)
    end = time.time() + LIFETIME
    fired: set[tuple[str, str]] = set()
    log(f"ticker up for {LIFETIME // 60} min, grace {GRACE} min, {len(plan.schedule)} slots, logic {my_logic}, sha {plan.head[:8]}")
    loops = 0
    while time.time() < end:
        plan.refresh()
        if loops % 5 == 4 and plan.should_yield():
            return 0
        tick(plan, dt.datetime.now(dt.timezone.utc), fired)
        loops += 1
        time.sleep(max(5, 60 - dt.datetime.now(dt.timezone.utc).second))
    log("lifetime reached; handing over to the next ticker")
    # Only a ticker that lived its full span hands over, so a crash can never
    # turn into a tight dispatch loop (the cron restart covers that case).
    open(os.environ.get("GITHUB_OUTPUT", os.devnull), "a").write("handoff=true\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
