#!/usr/bin/env python3
"""06:00 Africa/Accra master. One selection per match from that day's booked strategy codes.

NG is never kept: if another qualifying selection exists for the match it is
used instead. An NG leg is never rewritten into GG. DC 12 is dropped.
Combined price under 25 publishes nothing and nothing is padded.
The card is Code of the Day, on Hot Picks and on High Odds, marked HIGH RISK.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parent)]
import strategy_lib as lib

SOURCES = ("gg", "nysm", "nt")


def load_completed(repo: Path, day: str) -> list[tuple[str, dict]]:
    found = []
    root = repo / "engine" / "data" / "strategy-codes"
    for kind in SOURCES:
        path = root / kind / f"{day}.json"
        if not path.exists():
            continue
        try:
            payload = json.loads(path.read_text())
        except Exception:
            continue
        found.append((kind, payload))
    return found


def completed_legs(repo: Path, day: str) -> list[dict]:
    rows = []
    for kind, payload in load_completed(repo, day):
        if kind == "nysm":
            for slip in (payload.get("slips") or {}).values():
                if slip.get("code"):
                    rows.extend(slip.get("legs") or [])
            continue
        if kind == "gg":
            parts = payload.get("booked") or []
            if isinstance(parts, list) and any(part.get("code") for part in parts):
                rows.extend(payload.get("legs") or [])
            continue
        booked = payload.get("booked") or {}
        if isinstance(booked, dict) and booked.get("code"):
            rows.extend(payload.get("legs") or [])
    return rows


def choose(legs: list[dict], usage: dict) -> list[dict]:
    """One non-NG selection per match, skipping a match already on two codes."""
    grouped: dict[str, list[dict]] = {}
    for leg in legs:
        eid = leg.get("eventId")
        if not eid:
            continue
        grouped.setdefault(eid, []).append(leg)
    chosen = []
    for eid, options in grouped.items():
        if not lib.can_take(usage, eid):
            continue
        usable = [leg for leg in options if not lib.is_dc12(leg) and not lib.absolute_ban(leg)]
        # absolute_ban includes NG. A separate NG option is not flipped into GG;
        # it is simply not eligible. Another real selection on the match can still be used.
        if not usable:
            continue
        goals = [leg for leg in usable if str(leg.get("marketId")) in {"18", "19", "20", "29", "68", "90"}]
        pick = (goals or usable)[0]
        if lib.is_ng(pick):
            continue
        chosen.append(dict(pick))
    chosen.sort(key=lambda leg: (leg.get("kickoff") or "", leg.get("match") or ""))
    return chosen


def publish_master(repo: Path, day: str, code: str, legs: list[dict], total: float) -> None:
    for leg in legs:
        leg["gateExempt"] = True
        leg["strategySpec"] = True
        leg.setdefault("result", "pending")
    record = {
        "code": code,
        "date": day,
        "legs": len(legs),
        "totalOdds": total,
        "link": lib.SB_LINK.format(code),
        "name": f"Code of the Day · {day}",
        "riskLabel": "HIGH RISK",
        "uncertainLegs": 0,
        "note": "HIGH RISK Code of the Day from the night's strategy codes. Not safe or guaranteed.",
        "bookedAt": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "legList": legs,
        "status": "pending",
        "origin": "strategy-master",
        "strategySpec": True,
        "gateExempt": True,
        "strategyJob": True,
    }
    path = repo / "engine" / "data" / "daily-master" / f"{day}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, indent=1, ensure_ascii=False) + "\n")
    # The existing publisher puts the record on High Odds, Hot Picks and Home.
    os.environ["REPO_DIR"] = str(repo)
    sys.argv = ["daily_master.py", str(repo)]
    import daily_master
    daily_master.REPO = str(repo)
    daily_master.DIR = os.path.join(str(repo), "engine", "data", "daily-master")
    daily_master.main()


def run(day: dt.date, repo: Path, dry_run: bool = False) -> dict:
    usage = lib.load_usage(repo, day.isoformat())
    source = completed_legs(repo, day.isoformat())
    chosen = choose(source, usage)
    packed, why = lib.pack_slip(chosen)
    payload = {
        "strategy": "master",
        "date": day.isoformat(),
        "sourceLegs": len(source),
        "chosen": len(chosen),
        "reason": why,
        "code": None,
        "total": round(lib.product(leg["odds"] for leg in packed), 2) if packed else 0,
        "legs": packed,
        "conflicts": [
            "One selection per match taken from the strategy codes that actually booked.",
            "NG is dropped or replaced by a different qualifying selection. It is never rewritten as GG.",
            "DC 12 is dropped.",
            "Under 25 publishes nothing. The standing rule would combine short slips; this master does not pad.",
            "SportyBet GH only.",
            "Code of the Day is the documented gateExempt exception, so an obscure-league result leg that survived the strategy spec stays on the card.",
            "1X/X2 above 1.35 can remain when a strategy code contained it. The card is strategySpec. Flagged against the 1.35 cap.",
            "The 1.30 and 1.60 single-leg caps are not re-applied.",
        ],
    }
    if not packed:
        payload["published"] = False
    elif dry_run:
        payload["dryRun"] = True
        payload["published"] = False
    else:
        booked = lib.book_confirmed(packed)
        payload.update({k: v for k, v in booked.items() if k != "legs"})
        payload["legs"] = booked.get("legs") or []
        if booked.get("code"):
            publish_master(repo, day.isoformat(), booked["code"], payload["legs"], booked["total"])
            for leg in payload["legs"]:
                lib.take(usage, leg["eventId"], booked["code"])
            lib.save_usage(repo, day.isoformat(), usage)
            payload["published"] = True
        else:
            payload["published"] = False
    if not dry_run:
        lib.write_record(repo, "master", day.isoformat(), payload)
    print(json.dumps({"master": day.isoformat(), "source": len(source), "chosen": len(chosen), "published": payload.get("published"), "reason": payload.get("reason"), "code": payload.get("code")}, default=str))
    return payload


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--repo")
    args = parser.parse_args(argv)
    # 06:00 job publishes the Accra day that just started, unless a date is given.
    if args.date:
        day = dt.date.fromisoformat(args.date)
    else:
        day = dt.datetime.now(dt.timezone.utc).date()
    repo = Path(args.repo) if args.repo else lib.repo_root()
    run(day, repo, dry_run=args.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
