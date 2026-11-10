#!/usr/bin/env python3
"""Thin-pool fallback for the daily engine.

Normal filters stay in force when the day's qualified pool can fill the site
(at least MIN_LEGS bookable legs). When it cannot, non-hard filters are
loosened once so the site can still publish fresh codes that day.

Loosened only on a thin day:
  - matchup allow-lists (skip / middle / even / unverified / over-1.60)
  - extreme-stats bar on short goals prices
  - favourite sample floors (see fav_engine near-miss file)
  - hot-pick backing floor (15 -> 8)
  - DC Shield newrules / gate31 / short-price caps

Never loosened, even when the pool is thin:
  - NG / BTTS No / GG No
  - double chance 12
  - 1X or X2 priced above 1.35
  - obscure / non-major leagues: goals markets only (Over/Under, GG)
  - 50-leg bookmaker split (split_codes.py)

The fallback logs a line that starts with "thin-pool fallback used".
A day that already has enough qualified legs does not log that line and
does not admit extra picks.
"""
from __future__ import annotations

import datetime as dt

import matchup_rules as mr

MIN_LEGS = 6
RELAX_ODDS = 1.85
RELAX_MAJOR_NON_GOALS = 1.50


def hard_blocked(p: dict) -> bool:
    """Standing hard rules. True means the leg must never be published."""
    if not isinstance(p, dict):
        return True
    try:
        if mr.is_dc_vetoed(p) or mr.is_btts_no(p):
            return True
        if hasattr(mr, "is_obscure_league_non_goals") and mr.is_obscure_league_non_goals(p):
            return True
    except Exception:
        return True
    return False


def relaxed_ok(p: dict) -> bool:
    """Non-hard filters only. Hard rules still reject the leg."""
    if hard_blocked(p):
        return False
    try:
        odds = float(p.get("odds") or 0)
    except (TypeError, ValueError):
        return False
    if odds <= 1.0 or odds > RELAX_ODDS:
        return False
    if mr.is_goals_market(p):
        return True
    if mr.is_double_chance(p):
        return (not mr.is_dc_vetoed(p)) and odds <= mr.DC_1X_X2_MAX
    if mr.is_major_league(p) and odds <= RELAX_MAJOR_NON_GOALS:
        return True
    return False


def pool_is_thin(picks, min_legs: int = MIN_LEGS) -> bool:
    n = 0
    for p in picks or []:
        if isinstance(p, dict):
            n += 1
    return n < min_legs


def _eid(p: dict) -> str:
    return str(p.get("eventId") or p.get("eid") or p.get("match") or id(p))


def still_bookable(p: dict, now: dt.datetime | None = None) -> bool:
    """False once the leg's kickoff is in the past. Undated legs stay eligible."""
    now = now or dt.datetime.now(dt.timezone.utc)
    for key in ("kickoff", "start", "koIso"):
        raw = p.get(key)
        if not raw or "T" not in str(raw):
            continue
        try:
            t = dt.datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
            if t.tzinfo is None:
                t = t.replace(tzinfo=dt.timezone.utc)
            return t > now
        except Exception:
            continue
    day, ko = p.get("date"), p.get("ko")
    if day and ko and "T" not in str(ko):
        try:
            t = dt.datetime.fromisoformat(f"{str(day)[:10]}T{str(ko)[:5]}:00+00:00")
            return t > now
        except Exception:
            pass
    if day and str(day)[:10] < now.date().isoformat() and not ko:
        return False
    return True


def _annotate_strict(p: dict) -> dict:
    try:
        r = mr.strict(p)
    except Exception as e:
        r = "gate error " + str(e)[:60]
    p["strictGate"] = r or "pass"
    if r and getattr(mr, "MODE", "report") == "enforce":
        return None
    return p


def select(candidates, extras=None, min_legs: int = MIN_LEGS, quiet: bool = False):
    """Return (picks, info).

    `info["used"]` is False when the normal qualified pool is already large
    enough — extras and matchup rejects are ignored. When the pool is thin,
    rejects and `extras` that pass `relaxed_ok` are added and a fallback line
    is logged.
    """
    normal = []
    rejected = []
    for raw in candidates or []:
        if not isinstance(raw, dict):
            continue
        p = dict(raw)
        try:
            ok, cls, why = mr.check(p)
        except Exception as e:
            ok, cls, why = False, "error", str(e)
        p["matchup"] = cls
        if ok and not hard_blocked(p):
            kept = _annotate_strict(p)
            if kept is None:
                rejected.append(p)
            else:
                normal.append(kept)
        else:
            rejected.append(p)
    if not pool_is_thin(normal, min_legs):
        return normal, {"used": False, "qualified": len(normal), "added": 0, "log": ""}
    added = []
    seen = {_eid(p) for p in normal}
    for p in list(rejected) + [dict(x) for x in (extras or []) if isinstance(x, dict)]:
        eid = _eid(p)
        if eid in seen:
            continue
        if not still_bookable(p) or not relaxed_ok(p):
            continue
        p = dict(p)
        p["thinPoolFallback"] = True
        p["matchup"] = p.get("matchup") or "thin-pool"
        added.append(p)
        seen.add(eid)
    msg = (
        f"thin-pool fallback used: qualified {len(normal)}, added {len(added)} "
        f"by loosening non-hard filters only"
    )
    if not quiet:
        print(msg, flush=True)
    return normal + added, {
        "used": True,
        "qualified": len(normal),
        "added": len(added),
        "log": msg,
    }
