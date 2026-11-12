#!/usr/bin/env python3
"""Orchestrate the Predict2u daily engine.

  python -m engine.pipeline collect   # SportyBet scan + house fav engine + inbox merge
  python -m engine.pipeline book      # book no-login bookmakers
  python -m engine.pipeline publish   # write picks.json / home-picks.json and prune
  python -m engine.pipeline settle    # grade every pending code
  python -m engine.pipeline daily     # collect + book + publish
  python -m engine.pipeline all       # daily + settle
  python -m engine.pipeline shield    # 21:00 DC Shield Goals + AH -1 scan
  python -m engine.pipeline morning  # 07:00 SportyBet stats markets (1.20–1.60)
  python -m engine.pipeline fav      # 06:00 "How favourites perform by league": stats + fresh day-master codes

Use --dry-run to skip live booking and git commits.
"""
from __future__ import annotations
import argparse
import datetime as dt
import json
import os
import subprocess
import sys
from pathlib import Path

from . import inbox, settle_codes, combine
from .bookers import book_all
from .paths import ENGINE_DIR, REPO_DIR, RESEARCH_DIR, VENDOR_DIR, SBJSON, ensure_dirs, environ
from .rules import apply_all, is_double_chance, is_dc_vetoed, is_btts_no


_RUN_DAY = None
def run_day():
    """One date per pipeline run (fixes runs that cross midnight UTC); book falls back to the newest research file."""
    global _RUN_DAY
    if _RUN_DAY is None:
        _RUN_DAY = os.environ.get('P2U_DAY') or dt.datetime.now(dt.timezone.utc).date().isoformat()
    return _RUN_DAY
def run(cmd, env, cwd=None, timeout=None, check=True):
    print("+", " ".join(cmd))
    return subprocess.run(cmd, env=env, cwd=cwd, timeout=timeout, check=check)


def collect(env, days=2, dry_run=False):
    ensure_dirs()
    run([sys.executable, str(VENDOR_DIR / "scan.py")], env=env, timeout=300)
    day = run_day()
    run([sys.executable, str(VENDOR_DIR / "run.py"), day, "--days", str(days)], env=env, cwd=str(RESEARCH_DIR), timeout=int(os.environ.get("P2U_COLLECT_TIMEOUT", "4200")))
    path = RESEARCH_DIR / f"{day}.json"
    if not path.exists():
        print("collect: no research file written")
        return path
    data = json.loads(path.read_text())
    extra = inbox.load_picks()
    for code in inbox.load_share_codes():
        extra.extend(combine.decode_share(code))
    if extra:
        report = combine.process(extra)
        extra_used = [p for s in report["slips"] for p in s["legs"]]
        print(f"inbox: kept {len(extra_used)} extra picks, dropped {len(report['dropped'])}, combined slips {len(report['slips'])}")
        data["picks"] = inbox.merge(data.get("picks") or [], extra_used)
        data["combinedSlips"] = [
            {k: s[k] for k in ("name", "label", "odds", "minOdds", "meetsFloor") } | {"legs": s["legs"]}
            for s in report["slips"]
        ]
        data["combinedReport"] = {"dropped": report["dropped"], "used": report["used"]}
        path.write_text(json.dumps(data, indent=1, ensure_ascii=False))
    # never let a DC or NG pick survive
    data = json.loads(path.read_text())
    data["picks"] = [p for p in data.get("picks") or [] if not is_dc_vetoed(p) and not is_btts_no(p)]
    path.write_text(json.dumps(data, indent=1, ensure_ascii=False))
    print("collect:", path, "picks", len(data.get("picks") or []))
    return path



def _book_combined(env, day, dry_run=False):
    path = RESEARCH_DIR / f"{day}.json"
    if not path.exists():
        return
    data = json.loads(path.read_text())
    slips = data.get("combinedSlips") or []
    if not slips:
        return
    for s in slips:
        if s.get("codes"):
            continue
        if dry_run:
            print("combined: dry-run, skip booking", s.get("label"), s.get("odds"))
            continue
        books = book_all(s.get("legs") or [])
        s["codes"] = books
        sporty = (books.get("sportybet") or {}).get("code") if isinstance(books.get("sportybet"), dict) else None
        data.setdefault("slips", []).append({
            "name": s.get("name") or "Combined selection",
            "totalOdds": s.get("odds"),
            "legs": s.get("legs") or [],
            "codes": {"sportybet": sporty} if sporty else {},
            "bookCodes": books,
        })
        print("combined booked", s.get("label"), s.get("odds"), {k: (v or {}).get("code") if isinstance(v, dict) else v for k, v in books.items()})
    path.write_text(json.dumps(data, indent=1, ensure_ascii=False))


def book(env, dry_run=False):
    day = run_day()
    if dry_run:
        print("book: dry-run, skipped live booking")
        return
    run([sys.executable, str(VENDOR_DIR / "book_home.py"), day], env=env, cwd=str(RESEARCH_DIR), timeout=900)
    _book_combined(env, day, dry_run=dry_run)
    run([sys.executable, str(VENDOR_DIR / "hot_picks.py"), str(REPO_DIR / "hot-picks.json")], env=env, cwd=str(RESEARCH_DIR), timeout=1500, check=False)
    run([sys.executable, str(VENDOR_DIR / "dc_shield.py")], env=env, timeout=900, check=False)
    run([sys.executable, str(VENDOR_DIR / "ah_minus_one.py")], env=env, timeout=900, check=False)
    run([sys.executable, str(VENDOR_DIR / "high_odds.py"), str(REPO_DIR)], env=env, timeout=1500, check=False)
    run([sys.executable, str(VENDOR_DIR / "three_strategies.py")], env=env, timeout=4200, check=False)
    run([sys.executable, str(VENDOR_DIR / "verzzify_banker.py")], env=env, timeout=900, check=False)
    run([sys.executable, str(VENDOR_DIR / "daily_master.py"), str(REPO_DIR)], env=env, timeout=600, check=False)
    run([sys.executable, str(VENDOR_DIR / "share_cards.py"), str(REPO_DIR)], env=env, timeout=600, check=False)


def _prune(env):
    """Drop settled, expired, kicked-off and dead-share codes from every live JSON."""
    run([sys.executable, str(VENDOR_DIR / "prune_live.py"), str(REPO_DIR)], env=env, timeout=120, check=False)


def _lock_premium(env, dry_run=False):
    """Flag odds > 25, then (when the lock key exists) hide those codes and picks."""
    for key in ("P2U_LOCK_KEY", "PRIV_DIR", "ENGINE_DIR", "REPO_DIR", "FEED_DIR"):
        if env.get(key):
            os.environ.setdefault(key, env[key])
    from .premium import lock_published
    lock_published(env.get("REPO_DIR") or REPO_DIR, dry_run=dry_run)


def publish(env, dry_run=False):
    # build.py exits 3 when nothing changed — that is not a failure
    b = run([sys.executable, str(VENDOR_DIR / "build.py"), str(REPO_DIR)], env=env, timeout=180, check=False)
    if b.returncode not in (0, 3):
        raise subprocess.CalledProcessError(b.returncode, b.args)
    run([sys.executable, str(VENDOR_DIR / "inject_exempt.py"), str(REPO_DIR)], env=env, timeout=60, check=False)
    _prune(env)
    _lock_premium(env, dry_run=dry_run)
    run([sys.executable, str(VENDOR_DIR / "high_odds.py"), str(REPO_DIR), "--settle-only"], env=env, timeout=300, check=False)
    run([sys.executable, str(VENDOR_DIR / "split_codes.py"), str(REPO_DIR)], env=env, timeout=900, check=False)
    run([sys.executable, str(VENDOR_DIR / "daily_master.py"), str(REPO_DIR)], env=env, timeout=300, check=False)
    # daily_master re-inserts ho-master parts; prune again so kicked-off pending codes cannot stay live.
    _prune(env)
    # Seal again: daily_master can put a >25 code back onto the public pages.
    _lock_premium(env, dry_run=dry_run)
    run([sys.executable, str(VENDOR_DIR / "build_record.py"), str(REPO_DIR)], env=env, timeout=60, check=False)


    run([sys.executable, str(VENDOR_DIR / "share_cards.py"), str(REPO_DIR)], env=env, timeout=180, check=False)
    if os.environ.get("TELEGRAM_BOT_TOKEN") and (os.environ.get("TELEGRAM_CHANNEL") or os.environ.get("TELEGRAM_CHAT_ID")):
        run([sys.executable, str(VENDOR_DIR / "telegram_post.py"), str(REPO_DIR), "--codes"], env=env, timeout=120, check=False)
    else:
        print("publish: Telegram skipped (TELEGRAM_BOT_TOKEN / TELEGRAM_CHANNEL not set)")

def shield(env, dry_run=False):
    """Nightly ~9 PM DC Shield Goals run (also books AH-1 scan into the inbox)."""
    run([sys.executable, str(VENDOR_DIR / "dc_shield.py")] + (["--skip-book"] if dry_run else []), env=env, timeout=900, check=True)
    run([sys.executable, str(VENDOR_DIR / "ah_minus_one.py")], env=env, timeout=900, check=False)


def morning(env, dry_run=False):
    """07:00 SportyBet stats markets: one 1.20–1.60 pick per match, booked and published."""
    cmd = [sys.executable, str(VENDOR_DIR / "sb_morning_markets.py")]
    if dry_run:
        cmd.append("--dry-run")
    run(cmd, env=env, timeout=1800, check=True)


def fav(env, days=2, dry_run=False):
    """Home "How favourites perform by league": fresh league stats + today's/tomorrow's day-master codes."""
    collect(env, days=days, dry_run=dry_run)
    cmd = [sys.executable, str(VENDOR_DIR / "fav_leagues.py"), str(REPO_DIR)] + (["--dry-run"] if dry_run else [])
    run(cmd, env=env, timeout=1200, check=True)


def settle(env):
    print(json.dumps(settle_codes.settle_files(REPO_DIR)))
    run([sys.executable, str(VENDOR_DIR / "inject_exempt.py"), str(REPO_DIR)], env=env, timeout=60, check=False)
    run([sys.executable, str(VENDOR_DIR / "high_odds.py"), str(REPO_DIR), "--settle-only"], env=env, timeout=300, check=False)
    run([sys.executable, str(VENDOR_DIR / "split_codes.py"), str(REPO_DIR)], env=env, timeout=900, check=False)
    run([sys.executable, str(VENDOR_DIR / "daily_master.py"), str(REPO_DIR)], env=env, timeout=300, check=False)
    # After settlement: drop settled, expired and kicked-off codes from live sections (history kept).
    _prune(env)
    run([sys.executable, str(VENDOR_DIR / "build_record.py"), str(REPO_DIR)], env=env, timeout=60, check=False)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("command", choices=("collect", "book", "publish", "settle", "daily", "all", "shield", "morning", "fav"))
    ap.add_argument("--days", type=int, default=2)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    ensure_dirs()
    env = environ()
    if args.command in ("daily", "all"):
        # Clear yesterday's and unusable codes before booking, so a failed collect still unpublishes them.
        _prune(env)
    if args.command in ("collect", "daily", "all"):
        collect(env, days=args.days, dry_run=args.dry_run)
    if args.command in ("book", "daily", "all"):
        book(env, dry_run=args.dry_run)
    if args.command == "shield":
        shield(env, dry_run=args.dry_run)
    if args.command == "fav":
        fav(env, days=args.days, dry_run=args.dry_run)
        # Favourites day masters land on home-picks.json. Odds above 25 are sealed here.
        if not args.dry_run:
            _lock_premium(env, dry_run=False)
        return 0
    if args.command == "morning":
        morning(env, dry_run=args.dry_run)
        # Morning writes the 25+ master straight into high_odds.json and home-picks.json.
        if not args.dry_run:
            _lock_premium(env, dry_run=False)
        return 0
    if args.command in ("publish", "daily", "all", "shield"):
        publish(env, dry_run=args.dry_run)
    if args.command in ("settle", "all"):
        settle(env)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
