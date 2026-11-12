#!/usr/bin/env python3
"""Refresh the Home "How favourites perform by league" section on its own.

  python3 engine/vendor/fav_leagues.py <repo> [--dry-run]

Reads today's research file (RESEARCH_DIR/<today>.json, written by
`python -m engine.pipeline collect`) and updates only two keys of
home-picks.json:
  - leagues                (league favourite stats + fixtures + league picks)
  - homeCode.dayMasters    (favourites day-master codes, Today / Tomorrow tabs)
Day-master codes are booked fresh through engine.bookers.book_all (no-login
SportyBet, football.com, MSport, Betika, Betpawa; Betway skipped) for picks
that have not kicked off. Days in the past, or whose legs have all kicked off,
are dropped. Everything else in home-picks.json is left as it is.
"""
from __future__ import annotations
import datetime as dt
import json
import os
import re
import sys
from pathlib import Path

VENDOR = Path(__file__).resolve().parent
ENGINE = VENDOR.parent
for p in (str(ENGINE.parent), str(ENGINE), str(VENDOR)):
    if p not in sys.path:
        sys.path.insert(0, p)

import fav_day_masters as FDM  # noqa: E402
import matchup_rules as MR  # noqa: E402

LINK = {
    "sportybet": "https://www.sportybet.com/gh/?shareCode={}",
    "footballcom": "https://www.football.com/gh/?shareCode={}",
    "msport": "https://www.msport.com/gh/?shareCode={}",
    "betika": "https://betika.com/en-gh/share/{}",
    "betpawa": "https://www.betpawa.com.gh/share-betslip/{}",
}
_SCRUB = re.compile(r"nerdy\s*tips|nerdy|bets\s*for\s*the\s*day|betsfortheday|smagpf", re.I)


def _clean(v):
    if isinstance(v, str):
        return _SCRUB.sub("Predict2U", v)
    if isinstance(v, list):
        return [_clean(x) for x in v]
    if isinstance(v, dict):
        return {k: _clean(x) for k, x in v.items() if k not in ("source", "bot", "build", "src", "tipster")}
    return v


def _key(p):
    return (p.get("eventId"), str(p.get("marketId")), p.get("specifier") or "", str(p.get("outcomeId")))


def _ko(p):
    try:
        return dt.datetime.fromisoformat(f"{p['date']}T{p['ko']}").replace(tzinfo=dt.timezone.utc)
    except Exception:
        return None


def make_pass_fn(picks):
    ok = {_key(p) for p in MR.apply_all([dict(p) for p in picks])}

    def pass_fn(L):
        out = []
        for p in L:
            if _key(p) in ok:
                out.append(p)
                continue
            try:
                alt = MR.swap_to_goals(p) if hasattr(MR, "swap_to_goals") else None
                if alt:
                    MR.enrich(alt)
                    if MR.check(alt)[0]:
                        out.append(alt)
            except Exception:
                pass
        return out
    return pass_fn


def make_book_fn(now, dry_run=False):
    from engine.bookers import book_all

    def book_fn(name, legs):
        codes = {}
        if not dry_run:
            for bk, r in book_all([dict(p) for p in legs]).items():
                code = (r or {}).get("code") if isinstance(r, dict) else None
                if not code:
                    print("favLeagues", name, bk, "not booked", (r or {}).get("error", "") if isinstance(r, dict) else "", flush=True)
                    continue
                codes[bk] = [{"code": code, "totalOdds": r.get("totalOdds"), "legs": r.get("legs") or len(legs),
                              "link": LINK[bk].format(code), "matches": r.get("matches") or [p["eventId"] for p in legs]}]
        return {"name": name, "bookedAt": now.isoformat(timespec="seconds"), "codes": codes}
    return book_fn


def live_day_masters(dm, now):
    """Drop past days and days whose legs have all kicked off."""
    today = now.date().isoformat()
    keep = {}
    for day, m in (dm or {}).items():
        if day < today or not isinstance(m, dict):
            continue
        kos = [_ko(p) for p in m.get("picks") or []]
        if m.get("codes") and kos and all(k is not None and k <= now for k in kos):
            continue
        keep[day] = m
    return keep


def main(argv):
    repo = Path(next((a for a in argv if not a.startswith("--")), os.environ.get("REPO_DIR") or ENGINE.parent))
    dry = "--dry-run" in argv
    now = dt.datetime.now(dt.timezone.utc)
    day = os.environ.get("P2U_DAY") or now.date().isoformat()
    research = Path(os.environ.get("RESEARCH_DIR") or ENGINE / "data")
    hp_path = repo / "home-picks.json"
    hp = json.loads(hp_path.read_text())
    hc = dict(hp.get("homeCode") or {})
    rf = research / f"{day}.json"
    if rf.exists():
        d = json.loads(rf.read_text())
        picks = [p for p in d.get("picks") or [] if not MR.is_double_chance(p)]
        leagues = d.get("leagues") or []
        for L in leagues:
            L["picks"] = [p for p in (L.get("picks") or []) if not MR.is_double_chance(p)]
            L["qualifyingBands"] = [q for q in (L.get("qualifyingBands") or []) if not MR.is_double_chance(q)]
        if leagues:
            hp["leagues"] = _clean(leagues)
        dm = FDM.build_day_masters(picks, make_book_fn(now, dry), pass_fn=make_pass_fn(picks), now=now, today=day, days_ahead=1)
        merged = live_day_masters(hc.get("dayMasters"), now)
        for k, m in dm.items():
            if m.get("codes") or k not in merged:
                merged[k] = m
        hc["dayMasters"] = merged
        print("favLeagues", day, "leagues", len(leagues), "picks", len(picks),
              {k: {b: [x["code"] for x in v] for b, v in (m.get("codes") or {}).items()} for k, m in merged.items()}, flush=True)
    else:
        print("favLeagues: no research file", rf, "- only dropping stale day-master codes")
        hc["dayMasters"] = live_day_masters(hc.get("dayMasters"), now)
    hp["homeCode"] = hc
    hp["DATA_UPDATED"] = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    if dry:
        print("favLeagues: dry run, home-picks.json not written")
        return 0
    hp_path.write_text(json.dumps(hp, separators=(",", ":"), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
