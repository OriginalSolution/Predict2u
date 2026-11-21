"""Busy-day league filter shared by every booking strategy (HANDOFF section 5.7).

Rule (Riddim Boss, 21 Nov 2026): on a BUSY match day, picks may come only from
KNOWN leagues (major nations' top two tiers, MLS, Liga MX, major cups) and
CAPABLE leagues (other senior men's top flights with a proven hit record in our
own settled logs). Lower tiers, amateur, regional, women's, youth and reserve
football is dropped. Quiet days keep the full pool unchanged.

A day is busy when the open (not started) senior fixtures listed for that date
reach ``busy_threshold`` (engine/busy_day.json, default 300). With
``sticky_busy`` a day that was counted busy by an earlier run stays busy, so a
Saturday does not turn "quiet" in the evening just because games have started.

Entry points call :func:`filter_events` on raw SportyBet ``pcUpcomingEvents``
event dicts. Every call logs one line per fixture date to
``engine/data/busy-day/<date>/<job>.jsonl`` (committed by the workflows) and
prints a ``busy-day:`` line to the workflow output.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path

ENGINE = Path(os.environ.get("ENGINE_DIR") or Path(__file__).resolve().parents[1])
CONFIG_PATH = ENGINE / "busy_day.json"

_CFG: dict | None = None
_CAPABLE: dict | None = None
_FULL_COUNTS: dict | None = None


# ------------------------------------------------------------------ config
def repo_root() -> Path:
    env = os.environ.get("REPO_DIR")
    return Path(env) if env else ENGINE.parent


def load_config(path: Path | None = None) -> dict:
    global _CFG
    if path is None and _CFG is not None:
        return _CFG
    try:
        cfg = json.loads(Path(path or CONFIG_PATH).read_text())
    except Exception:
        cfg = {"enabled": False}
    if os.environ.get("P2U_BUSY_THRESHOLD"):
        cfg["busy_threshold"] = int(os.environ["P2U_BUSY_THRESHOLD"])
    if os.environ.get("P2U_BUSY_FILTER", "").strip().lower() in {"0", "off", "false", "no"}:
        cfg["enabled"] = False
    if path is None:
        _CFG = cfg
    return cfg


def norm(text) -> str:
    s = unicodedata.normalize("NFKD", str(text or "")).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def _name_match(name: str, patterns) -> bool:
    n = norm(name)
    for p in patterns or []:
        if str(p).endswith("*"):
            if n.startswith(norm(str(p)[:-1])):
                return True
        elif n == norm(p):
            return True
    return False


def _lookup(table: dict, country: str, league: str) -> bool:
    c = norm(country)
    for k, leagues in (table or {}).items():
        if norm(k) == c and _name_match(league, leagues):
            return True
    return False


# ------------------------------------------------------------------ event fields
def event_fields(event: dict) -> tuple[str, str, str, str]:
    cat = ((event.get("sport") or {}).get("category") or {})
    country = cat.get("name") or event.get("categoryName") or ""
    league = (cat.get("tournament") or {}).get("name") or event.get("tournamentName") or event.get("league") or ""
    return country, league, event.get("homeTeamName") or "", event.get("awayTeamName") or ""


def event_day(event: dict) -> str | None:
    ts = event.get("estimateStartTime") or event.get("startTime") or 0
    if not ts:
        return None
    ts = ts / 1000 if ts > 1e12 else ts
    return dt.datetime.fromtimestamp(ts, dt.timezone.utc).date().isoformat()  # Accra == UTC


def is_open(event: dict, now: dt.datetime) -> bool:
    if str(event.get("matchStatus") or "Not start") not in {"Not start", "", "0"}:
        return False
    ts = event.get("estimateStartTime") or 0
    if not ts:
        return True
    return dt.datetime.fromtimestamp((ts / 1000 if ts > 1e12 else ts), dt.timezone.utc) > now


def is_senior(country: str, league: str, home: str, away: str, cfg: dict | None = None) -> bool:
    cfg = cfg or load_config()
    rx = re.compile(cfg.get("non_senior_regex") or r"$^", re.I)
    if rx.search(f"{country} | {league} | {home} | {away}"):
        return False
    team_rx = re.compile(cfg.get("reserve_team_regex") or r"$^", re.I)
    return not (team_rx.search(home.strip()) or team_rx.search(away.strip()))


# ------------------------------------------------------------------ capable leagues
def _split_log_league(name: str) -> tuple[str, str]:
    name = str(name or "")
    if " - " in name:
        c, l = name.split(" - ", 1)
        return c, l
    return "", name


def capable_leagues(cfg: dict | None = None, repo: Path | None = None) -> dict:
    """Score every configured candidate top flight from our settled legs.

    Sources: engine/data/code-ledger.json legs and picks-history.json picks
    (won/lost only, deduped by match + odds). A log row counts toward a
    candidate when it names the same country and league, or - for rows that
    carry only a league name - when that name belongs to exactly one league
    in the known + candidate lists (so "Eliteserien" counts, "Super League"
    does not). Returns {"Country|League": {"n", "won", "rate", "capable"}}.
    """
    global _CAPABLE
    use_cache = cfg is None and repo is None
    if use_cache and _CAPABLE is not None:
        return _CAPABLE
    cfg = cfg or load_config()
    repo = repo or repo_root()
    cap = cfg.get("capable") or {}
    tops = cap.get("top_flights") or {}
    known = cfg.get("known") or {}
    # which (country, league) names an unqualified league name could mean
    owners: dict[str, set] = {}
    for table in (known, tops):
        for c, leagues in table.items():
            for lg in leagues:
                owners.setdefault(norm(str(lg).rstrip("*")), set()).add(norm(c))

    rows = []
    seen = set()

    def add(league, match, odds, result):
        if result not in ("won", "lost"):
            return
        key = (norm(match), round(float(odds or 0), 2), norm(league))
        if key in seen:
            return
        seen.add(key)
        rows.append((league, result == "won"))

    for src in cap.get("sources") or []:
        p = repo / src
        try:
            data = json.loads(p.read_text())
        except Exception:
            continue
        if isinstance(data, dict) and isinstance(data.get("days"), dict):
            for picks in data["days"].values():
                for r in picks or []:
                    add(r.get("league"), r.get("match"), r.get("odds"), str(r.get("result") or "").lower())
        elif isinstance(data, dict):
            for code in data.values():
                for leg in (code or {}).get("legs") or [] if isinstance(code, dict) else []:
                    add(leg.get("league"), leg.get("match"), leg.get("odds"), str(leg.get("result") or "").lower())

    stats: Counter = Counter()
    wins: Counter = Counter()
    for league, won in rows:
        c, l = _split_log_league(league)
        cands = []
        for tc, leagues in tops.items():
            if not _name_match(l, leagues):
                continue
            if c:
                if norm(c) == norm(tc):
                    cands.append(tc)
            elif len(owners.get(norm(l), set())) == 1:
                cands.append(tc)
        if len(cands) == 1:
            for lg in tops[cands[0]]:
                if _name_match(l, [lg]):
                    k = f"{cands[0]}|{lg}"
                    stats[k] += 1
                    wins[k] += won
                    break

    min_n = int(cap.get("min_sample", 8))
    min_rate = float(cap.get("min_hit_rate", 0.70))
    always = {norm(x) for x in cap.get("always") or []}
    never = {norm(x) for x in cap.get("never") or []}
    out = {}
    for tc, leagues in tops.items():
        for lg in leagues:
            k = f"{tc}|{lg}"
            n, w = stats.get(k, 0), wins.get(k, 0)
            rate = round(w / n, 3) if n else None
            ok = n >= min_n and rate is not None and rate >= min_rate
            if norm(k) in always:
                ok = True
            if norm(k) in never:
                ok = False
            out[k] = {"n": n, "won": w, "rate": rate, "capable": ok}
    if use_cache:
        _CAPABLE = out
    return out


def classify(country: str, league: str, home: str = "", away: str = "", cfg: dict | None = None,
             capable: dict | None = None) -> str:
    """'known', 'capable' or 'excluded' (the busy-day verdict for one fixture)."""
    cfg = cfg or load_config()
    if not is_senior(country, league, home, away, cfg):
        return "excluded"
    if _lookup(cfg.get("known") or {}, country, league):
        return "known"
    capable = capable_leagues() if capable is None else capable
    for k, v in capable.items():
        if not v.get("capable"):
            continue
        tc, lg = k.split("|", 1)
        if norm(tc) == norm(country) and _name_match(league, [lg]):
            return "capable"
    return "excluded"


# ------------------------------------------------------------------ busy decision
def day_counts(events, now: dt.datetime | None = None, cfg: dict | None = None) -> Counter:
    """Open senior fixtures per date (YYYY-MM-DD, Accra/UTC)."""
    cfg = cfg or load_config()
    now = now or dt.datetime.now(dt.timezone.utc)
    out: Counter = Counter()
    seen = set()
    for e in events:
        eid = e.get("eventId")
        if eid in seen:
            continue
        seen.add(eid)
        day = event_day(e)
        if day and is_open(e, now) and is_senior(*event_fields(e), cfg):
            out[day] += 1
    return out


def full_counts() -> Counter:
    """Counts from the full SportyBet upcoming feed, fetched once per process."""
    global _FULL_COUNTS
    if _FULL_COUNTS is None:
        try:
            sys.path.insert(0, str(Path(__file__).resolve().parent))
            import strategy_lib as lib
            _FULL_COUNTS = day_counts(lib.fetch_upcoming("1", busy_filter=False))
        except Exception as exc:  # network down: never block a job on the count
            print(f"busy-day: count fetch failed ({exc}); treating days as quiet", flush=True)
            _FULL_COUNTS = Counter()
    return _FULL_COUNTS


def peak_logged(day: str, cfg: dict | None = None) -> int:
    cfg = cfg or load_config()
    folder = log_dir(cfg) / day
    best = 0
    for f in folder.glob("*.jsonl") if folder.is_dir() else []:
        for line in f.read_text().splitlines():
            try:
                best = max(best, int(json.loads(line).get("fixtures") or 0))
            except Exception:
                continue
    return best


def is_busy(fixtures: int, cfg: dict | None = None, day: str | None = None) -> tuple[bool, int]:
    """(busy, fixtures used). Sticky: an earlier logged peak for the day counts."""
    cfg = cfg or load_config()
    n = fixtures
    if day and cfg.get("sticky_busy", True):
        n = max(n, peak_logged(day, cfg))
    return n >= int(cfg.get("busy_threshold", 300)), n


# ------------------------------------------------------------------ logging
def log_dir(cfg: dict | None = None) -> Path:
    cfg = cfg or load_config()
    env = os.environ.get("P2U_BUSY_LOG_DIR")
    if env:
        return Path(env)
    return repo_root() / (cfg.get("log_dir") or "engine/data/busy-day")


def job_name() -> str:
    env = os.environ.get("P2U_JOB")
    if env:
        return re.sub(r"[^A-Za-z0-9_.-]+", "-", env)
    return Path(sys.argv[0] or "engine").stem or "engine"


def write_log(day: str, entry: dict, cfg: dict | None = None) -> None:
    line = json.dumps(entry, separators=(",", ":"), sort_keys=True)
    print("busy-day: " + line, flush=True)
    try:
        folder = log_dir(cfg) / day
        folder.mkdir(parents=True, exist_ok=True)
        with open(folder / f"{job_name()}.jsonl", "a") as fh:
            fh.write(line + "\n")
    except Exception as exc:
        print(f"busy-day: log write failed ({exc})", flush=True)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        try:
            with open(summary, "a") as fh:
                fh.write(
                    f"- busy-day {day}: {'BUSY' if entry['busy'] else 'quiet'} - {entry['fixtures']} open senior fixtures "
                    f"(threshold {entry['threshold']}); kept {entry['kept']}, dropped {entry['dropped']}\n"
                )
        except Exception:
            pass


# ------------------------------------------------------------------ the filter
def filter_events(events, job: str | None = None, complete: bool = False, now: dt.datetime | None = None,
                  cfg: dict | None = None, capable: dict | None = None, counts: Counter | None = None,
                  log: bool = True, horizon_days: int = 2) -> list:
    """Apply the busy-day rule to raw SportyBet events; returns the kept list.

    ``complete`` means ``events`` is the whole upcoming feed, so the busy count
    can be taken from it; otherwise the full feed is fetched once to count.
    Only events on a busy date are touched; others pass through unchanged.
    """
    cfg = cfg or load_config()
    events = list(events or [])
    if not cfg.get("enabled", True) or not events:
        return events
    if job:
        os.environ.setdefault("P2U_JOB", job)
    now = now or dt.datetime.now(dt.timezone.utc)
    if counts is None:
        counts = day_counts(events, now, cfg) if complete else full_counts()
    capable = capable_leagues() if capable is None else capable
    last = (now + dt.timedelta(days=horizon_days)).date().isoformat()
    verdict: dict[str, tuple[bool, int]] = {}
    kept, stats = [], {}
    for e in events:
        day = event_day(e)
        if not day:
            kept.append(e)
            continue
        if day not in verdict:
            verdict[day] = is_busy(int(counts.get(day, 0)), cfg, day)
        busy, _ = verdict[day]
        st = stats.setdefault(day, {"kept": 0, "dropped": 0, "known": 0, "capable": 0, "drop_leagues": Counter()})
        if not busy:
            st["kept"] += 1
            kept.append(e)
            continue
        country, league, home, away = event_fields(e)
        cls = classify(country, league, home, away, cfg, capable)
        if cls == "excluded":
            st["dropped"] += 1
            st["drop_leagues"][f"{country} - {league}"] += 1
        else:
            st["kept"] += 1
            st[cls] += 1
            kept.append(e)
    if log:
        for day, st in sorted(stats.items()):
            if day > last:
                continue
            busy, n = verdict[day]
            write_log(day, {
                "ts": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "job": job_name(), "script": Path(sys.argv[0] or "").stem, "date": day,
                "fixtures": int(counts.get(day, 0)), "fixturesUsed": n,
                "threshold": int(cfg.get("busy_threshold", 300)), "busy": busy,
                "input": st["kept"] + st["dropped"], "kept": st["kept"], "dropped": st["dropped"],
                "known": st["known"], "capable": st["capable"],
                "topDropped": dict(st["drop_leagues"].most_common(5)),
            }, cfg)
    return kept


def safe_filter(events, complete: bool = False, job: str | None = None) -> list:
    """filter_events for the older entry points: never crash a booking job.
    On an internal error the pool passes through unchanged (logged)."""
    try:
        return filter_events(events, job=job, complete=complete)
    except Exception as exc:  # pragma: no cover - defensive
        print(f"busy-day: filter skipped ({exc!r}); pool unchanged", flush=True)
        return list(events or [])


def allow_fields(country: str, league: str, home: str, away: str, day: str, job: str | None = None) -> bool:
    """Single-fixture check for code that already holds parsed fields."""
    cfg = load_config()
    if not cfg.get("enabled", True):
        return True
    busy, _ = is_busy(int(full_counts().get(day, 0)), cfg, day)
    return (not busy) or classify(country, league, home, away, cfg) != "excluded"


def main(argv=None) -> int:
    """Dry run: python engine/vendor/busy_day.py [YYYY-MM-DD ...] - counts before/after, no log."""
    import strategy_lib as lib
    argv = list(sys.argv[1:] if argv is None else argv)
    events = lib.fetch_upcoming("1", busy_filter=False)
    cfg = load_config()
    counts = day_counts(events, cfg=cfg)
    days = argv or sorted(counts)[:2]
    cap = capable_leagues()
    print("capable leagues:", ", ".join(k for k, v in cap.items() if v["capable"]) or "none")
    for day in days:
        todays = [e for e in events if event_day(e) == day]
        kept = filter_events(todays, counts=counts, cfg=cfg, capable=cap, log=False)
        busy, n = is_busy(int(counts.get(day, 0)), cfg, day)
        print(json.dumps({"date": day, "openSenior": int(counts.get(day, 0)), "listed": len(todays),
                          "threshold": cfg.get("busy_threshold"), "busy": busy, "kept": len(kept),
                          "dropped": len(todays) - len(kept)}))
    return 0


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    raise SystemExit(main())
