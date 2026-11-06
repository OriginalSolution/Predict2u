"""Favourites day masters: book today's (and tomorrow's) house favourites picks
as one slip per day (split into <=MAX_LEGS parts when huge), across every
no-login bookmaker. Shown on the Home page "How favourites perform by league"
section for the selected day tab.

Rules: one market per game, drop kicked-off, never NG, DC 12 banned and
1X/X2 only <=1.35, obscure leagues goals-only, 1.60 / strong-stats caps via
matchup_rules.apply_all.
"""
from __future__ import annotations
import datetime as dt
import math
from typing import Callable


MAX_LEGS = 30
MIN_SHOW = 1  # even a short leftover slip is published (user wants codes available)


def _ko(p, now=None):
    now = now or dt.datetime.now(dt.timezone.utc)
    try:
        return dt.datetime.fromisoformat(f"{p['date']}T{p['ko']}").replace(tzinfo=dt.timezone.utc)
    except Exception:
        return None


def upcoming(picks, now=None):
    now = now or dt.datetime.now(dt.timezone.utc)
    kept, dropped = [], []
    for p in picks or []:
        ko = _ko(p, now)
        if ko is not None and ko <= now + dt.timedelta(minutes=2):
            dropped.append({"match": p.get("match"), "selection": p.get("selection"), "reason": "kicked off", "ko": p.get("ko")})
            continue
        kept.append(p)
    return kept, dropped


def dedupe_one_per_game(picks):
    """One market per eventId; prefer higher confidence, then shorter odds."""
    best = {}
    for p in picks or []:
        e = p.get("eventId")
        if not e:
            continue
        cur = best.get(e)
        if not cur:
            best[e] = p
            continue
        a = (float(p.get("confidence") or 0), -float(p.get("odds") or 9))
        b = (float(cur.get("confidence") or 0), -float(cur.get("odds") or 9))
        if a > b:
            best[e] = p
    return list(best.values())


def group_by_date(picks):
    by = {}
    for p in picks or []:
        d = p.get("date")
        if d:
            by.setdefault(d, []).append(p)
    return by


def chunk_legs(legs, max_legs=MAX_LEGS):
    L = list(legs or [])
    if not L:
        return []
    return [L[i : i + max_legs] for i in range(0, len(L), max_legs)]


def _slim(p):
    return {
        "eventId": p.get("eventId"),
        "match": p.get("match"),
        "league": p.get("league"),
        "date": p.get("date"),
        "ko": p.get("ko"),
        "selection": p.get("selection"),
        "odds": p.get("odds"),
        "marketId": p.get("marketId"),
        "specifier": p.get("specifier"),
        "outcomeId": p.get("outcomeId"),
        "confidence": p.get("confidence"),
    }


def build_day_masters(
    picks,
    book_fn: Callable,
    pass_fn=None,
    now=None,
    today=None,
    days_ahead=1,
    max_legs=MAX_LEGS,
):
    """Build + book one master (possibly multi-part) per calendar day.

    book_fn(name, legs) -> slip dict with codes map (same shape as hot_picks.slip).
    pass_fn(legs) optional extra filter (matchup.apply_all); default identity.
    days_ahead=1 means today + tomorrow.
    """
    pass_fn = pass_fn or (lambda L: list(L or []))
    now = now or dt.datetime.now(dt.timezone.utc)
    today = today or now.date().isoformat()
    end = (dt.date.fromisoformat(today) + dt.timedelta(days=days_ahead)).isoformat()

    by = group_by_date(picks)
    masters = {}
    for day in sorted(d for d in by if today <= d <= end):
        raw = by[day]
        open_legs, kicked = upcoming(raw, now=now)
        filtered = pass_fn(open_legs)
        # track rule drops
        kept_ids = {(p.get("eventId"), str(p.get("marketId")), p.get("specifier") or "", str(p.get("outcomeId"))) for p in filtered}
        rule_drops = []
        for p in open_legs:
            k = (p.get("eventId"), str(p.get("marketId")), p.get("specifier") or "", str(p.get("outcomeId")))
            if k not in kept_ids:
                rule_drops.append({"match": p.get("match"), "selection": p.get("selection"), "reason": "failed site rules", "odds": p.get("odds")})
        legs = dedupe_one_per_game(filtered)
        # prefer earlier KO then higher confidence for stable packing
        legs = sorted(legs, key=lambda p: (p.get("ko") or "", -float(p.get("confidence") or 0)))
        dropped = kicked + rule_drops
        if len(legs) < MIN_SHOW:
            masters[day] = {
                "date": day,
                "label": "Favourites of the day",
                "legs": 0,
                "of": len(raw),
                "totalOdds": 0,
                "codes": {},
                "picks": [],
                "dropped": dropped,
                "note": "No upcoming qualifying picks left for this day.",
            }
            continue
        parts = chunk_legs(legs, max_legs=max_legs)
        all_codes = {}
        booked_at = None
        for i, part in enumerate(parts):
            name = f"Favourites · {day}" + (f" · part {i+1}" if len(parts) > 1 else "")
            sl = book_fn(name, part)
            booked_at = booked_at or sl.get("bookedAt")
            for bk, vals in (sl.get("codes") or {}).items():
                all_codes.setdefault(bk, [])
                if isinstance(vals, list):
                    all_codes[bk].extend(vals)
                else:
                    all_codes[bk].append(vals)
        tot = round(math.prod(float(x.get("odds") or 1) for x in legs), 2)
        masters[day] = {
            "date": day,
            "label": "Favourites of the day",
            "name": f"Favourites · {day}",
            "legs": len(legs),
            "of": len(raw),
            "totalOdds": tot,
            "parts": len(parts),
            "codes": all_codes,
            "picks": [_slim(p) for p in legs],
            "dropped": dropped,
            "bookedAt": booked_at,
            "meetsFloor": tot >= 25,
        }
        if not masters[day]["meetsFloor"]:
            masters[day]["note"] = (
                f"{len(legs)} of {len(raw)} picks still open (rest kicked off / vetoed); "
                f"combined odds {tot:.2f}."
            )
        print(
            "favDayMaster",
            day,
            "legs",
            len(legs),
            "of",
            len(raw),
            "odds",
            tot,
            "parts",
            len(parts),
            "codes",
            {b: [(x.get("code"), x.get("totalOdds"), x.get("legs")) for x in v] for b, v in all_codes.items()},
            flush=True,
        )
    return masters
