#!/usr/bin/env python3
"""Orchestrate the Predict2u daily engine.

  python -m engine.pipeline collect   # SportyBet scan + house fav engine + inbox merge
  python -m engine.pipeline book      # book no-login bookmakers
  python -m engine.pipeline publish   # write picks.json / home-picks.json and prune
  python -m engine.pipeline settle    # grade every pending code
  python -m engine.pipeline daily     # collect + book + publish
  python -m engine.pipeline all       # daily + settle
  python -m engine.pipeline shield    # 21:00 DC Shield Goals + AH -1 scan

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


def run(cmd, env, cwd=None, timeout=None, check=True):
    print("+", " ".join(cmd))
    return subprocess.run(cmd, env=env, cwd=cwd, timeout=timeout, check=check)


def collect(env, days=2, dry_run=False):
    ensure_dirs()
    run([sys.executable, str(VENDOR_DIR / "scan.py")], env=env, timeout=300)
    day = dt.date.today().isoformat()
    run([sys.executable, str(VENDOR_DIR / "run.py"), day, "--days", str(days)], env=env, cwd=str(RESEARCH_DIR), timeout=1500)
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
    day = dt.date.today().isoformat()
    if dry_run:
        print("book: dry-run, skipped live booking")
        return
    run([sys.executable, str(VENDOR_DIR / "book_home.py"), day], env=env, cwd=str(RESEARCH_DIR), timeout=900)
    _book_combined(env, day, dry_run=dry_run)
    run([sys.executable, str(VENDOR_DIR / "hot_picks.py"), str(REPO_DIR / "hot-picks.json")], env=env, cwd=str(RESEARCH_DIR), timeout=1500, check=False)
    run([sys.executable, str(VENDOR_DIR / "dc_shield.py")], env=env, timeout=900, check=False)
    run([sys.executable, str(VENDOR_DIR / "ah_minus_one.py")], env=env, timeout=900, check=False)
    run([sys.executable, str(VENDOR_DIR / "high_odds.py"), str(REPO_DIR)], env=env, timeout=1500, check=False)


def publish(env, dry_run=False):
    run([sys.executable, str(VENDOR_DIR / "build.py"), str(REPO_DIR)], env=env, timeout=180)
    run([sys.executable, str(VENDOR_DIR / "inject_exempt.py"), str(REPO_DIR)], env=env, timeout=60, check=False)
    run([sys.executable, str(VENDOR_DIR / "prune_live.py"), str(REPO_DIR)], env=env, timeout=60)
    if os.environ.get("P2U_LOCK_KEY") or (Path(env["PRIV_DIR"]) / "lock.key").exists():
        if os.environ.get("P2U_LOCK_KEY") and not (Path(env["PRIV_DIR"]) / "lock.key").exists():
            Path(env["PRIV_DIR"]).mkdir(parents=True, exist_ok=True)
            (Path(env["PRIV_DIR"]) / "lock.key").write_text(os.environ["P2U_LOCK_KEY"].strip() + "\n")
        try:
            run([sys.executable, str(VENDOR_DIR / "lock_codes.py"), str(REPO_DIR)], env=env, timeout=60)
        except Exception as e:
            print("lock failed:", e)
            if not dry_run:
                raise SystemExit("refusing to publish unlocked premium codes")
    else:
        print("publish: P2U_LOCK_KEY / lock.key missing — premium lock skipped (do not commit raw banker codes without it)")
    run([sys.executable, str(VENDOR_DIR / "high_odds.py"), str(REPO_DIR), "--settle-only"], env=env, timeout=300, check=False)
    run([sys.executable, str(VENDOR_DIR / "build_record.py"), str(REPO_DIR)], env=env, timeout=60, check=False)


    run([sys.executable, str(VENDOR_DIR / "share_cards.py"), str(REPO_DIR)], env=env, timeout=180, check=False)
    if os.environ.get("TELEGRAM_BOT_TOKEN") and (os.environ.get("TELEGRAM_CHANNEL") or os.environ.get("TELEGRAM_CHAT_ID")):
        run([sys.executable, str(VENDOR_DIR / "telegram_post.py"), str(REPO_DIR), "--codes"], env=env, timeout=120, check=False)
    else:
        print("publish: Telegram skipped (TELEGRAM_BOT_TOKEN / TELEGRAM_CHANNEL not set)")

def shield(env, dry_run=False):
    """Nightly ~9 PM DC Shield Goals run (also books AH-1 scan into the inbox)."""
    run([sys.executable, str(VENDOR_DIR / "dc_shield.py")] + (["--skip-book"] if dry_run else []), env=env, timeout=900, check=False)
    run([sys.executable, str(VENDOR_DIR / "ah_minus_one.py")], env=env, timeout=900, check=False)


def settle(env):
    print(json.dumps(settle_codes.settle_files(REPO_DIR)))
    run([sys.executable, str(VENDOR_DIR / "inject_exempt.py"), str(REPO_DIR)], env=env, timeout=60, check=False)
    run([sys.executable, str(VENDOR_DIR / "prune_live.py"), str(REPO_DIR)], env=env, timeout=60, check=False)
    run([sys.executable, str(VENDOR_DIR / "high_odds.py"), str(REPO_DIR), "--settle-only"], env=env, timeout=300, check=False)
    run([sys.executable, str(VENDOR_DIR / "build_record.py"), str(REPO_DIR)], env=env, timeout=60, check=False)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("command", choices=("collect", "book", "publish", "settle", "daily", "all", "shield"))
    ap.add_argument("--days", type=int, default=2)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    ensure_dirs()
    env = environ()
    if args.command in ("collect", "daily", "all"):
        collect(env, days=args.days, dry_run=args.dry_run)
    if args.command in ("book", "daily", "all"):
        book(env, dry_run=args.dry_run)
    if args.command == "shield":
        shield(env, dry_run=args.dry_run)
    if args.command in ("publish", "daily", "all", "shield"):
        publish(env, dry_run=args.dry_run)
    if args.command in ("settle", "all"):
        settle(env)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
