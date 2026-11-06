"""Hot page section master slips: one 25+ (aim) booked slip per Hot section.

Sections: Hot matches, Hot by market, Trending markets, Hot teams, Most-backed teams.
Rules: one market per game, upcoming only (already filtered upstream), matchup/_pass
applied by the caller, pack toward min 25 odds (keep under-floor rather than drop).
"""
from __future__ import annotations
import datetime as dt
import json
import math
import os
from pathlib import Path

SECTION_FLOOR = 25
SECTION_MAX_LEGS = 30
SECTION_MIN_LEGS = 5

SECTION_BUILDERS = (
    ("hot_matches", "Hot matches", "section_pool_hot_matches"),
    ("hot_by_market", "Hot by market", "section_pool_hot_by_market"),
    ("trending_markets", "Trending markets", "section_pool_trending_markets"),
    ("hot_teams", "Hot teams", "section_pool_hot_teams"),
    ("most_backed_teams", "Most-backed teams", "section_pool_most_backed_teams"),
)


def dedupe_event(pool):
    """One market per game; prefer higher hub count, then backing, then shorter odds."""
    best = {}
    for p in pool or []:
        e = p.get("eventId")
        if not e:
            continue
        cur = best.get(e)
        if not cur:
            best[e] = p
            continue
        a = (int(p.get("count") or 0), int(p.get("backing") or 0), -float(p.get("odds") or 9))
        b = (int(cur.get("count") or 0), int(cur.get("backing") or 0), -float(cur.get("odds") or 9))
        if a > b:
            best[e] = p
    return list(best.values())


def pack_floor(pool, floor=SECTION_FLOOR, max_legs=SECTION_MAX_LEGS, min_legs=SECTION_MIN_LEGS):
    """Aim for floor odds; keep leftover under-floor rather than dropping (combine rule)."""
    L = sorted(
        pool or [],
        key=lambda p: (-int(p.get("count") or 0), -int(p.get("backing") or 0), float(p.get("odds") or 1)),
    )
    out = []
    for p in L:
        out.append(p)
        if len(out) >= min_legs and math.prod(float(x.get("odds") or 1) for x in out) >= floor:
            break
        if len(out) >= max_legs:
            break
    return out


def section_pool_hot_matches(doc):
    return list(doc.get("picks") or [])


def section_pool_hot_by_market(doc):
    pool = []
    for m in doc.get("byMarket") or []:
        pool.extend(m.get("picks") or [])
    return pool


def section_pool_trending_markets(doc):
    by = {x.get("market"): x for x in (doc.get("byMarket") or []) if x.get("market")}
    pool = []
    for m in doc.get("markets") or []:
        sl = by.get(m.get("name"))
        if sl:
            pool.extend(sl.get("picks") or [])
    return pool or section_pool_hot_by_market(doc)


def section_pool_hot_teams(doc):
    pool = []
    for m in doc.get("byTeam") or []:
        pool.extend(m.get("picks") or [])
    return pool


def section_pool_most_backed_teams(doc):
    by = {x.get("team"): x for x in (doc.get("byTeam") or []) if x.get("team")}
    pool = []
    for m in doc.get("teams") or []:
        sl = by.get(m.get("name"))
        if sl:
            pool.extend(sl.get("picks") or [])
    return pool or section_pool_hot_teams(doc)


_POOL_FN = {
    "section_pool_hot_matches": section_pool_hot_matches,
    "section_pool_hot_by_market": section_pool_hot_by_market,
    "section_pool_trending_markets": section_pool_trending_markets,
    "section_pool_hot_teams": section_pool_hot_teams,
    "section_pool_most_backed_teams": section_pool_most_backed_teams,
}


def _betway_overlay(sl, today_iso, engine_dir=None):
    try:
        root = Path(engine_dir or os.environ.get("ENGINE_DIR") or Path(__file__).resolve().parents[1])
        bw = json.loads((root / "betway_codes.json").read_text())
    except Exception:
        return
    sb = ((sl.get("codes") or {}).get("sportybet") or [{}])
    sb0 = sb[0] if isinstance(sb, list) and sb else {}
    code = sb0.get("code") if isinstance(sb0, dict) else None
    e = (bw.get("bySlip") or {}).get(code) if code else None
    if e and bw.get("date") == today_iso:
        sl.setdefault("codes", {})["betway"] = [
            dict(
                code=e["code"],
                totalOdds=e.get("odds"),
                legs=e.get("picks"),
                link=f"https://www.betway.com.gh/sport/soccer?bookingCode={e['code']}",
            )
        ]


def _upcoming_only(pool, today):
    out = []
    for p in pool or []:
        d = p.get("date") or ""
        if d and d < today:
            continue
        out.append(p)
    return out


def _site_ban(p):
    """Hard site bans that must never appear on a published master (defense in depth)."""
    try:
        oid = str(p.get("outcomeId") or "")
        mid = str(p.get("marketId") or "")
        sel = (p.get("selection") or "").lower()
        mk = (p.get("market") or "").lower()
        if oid == "76":
            return True
        if "btts no" in sel or "gg no" in sel or "both teams to score: no" in sel or "both teams to score: no" in mk:
            return True
        if mid in ("10", "60110"):
            if "home or away" in sel or "double chance 12" in mk or " 12" in sel:
                return True
            if float(p.get("odds") or 0) > 1.35:
                return True
    except Exception:
        return False
    return False


def build_section_masters(doc, book_fn, pass_fn=None, today=None, engine_dir=None):
    """Build + book one master slip per Hot page section.

    book_fn(name, legs) -> slip dict with codes map (same shape as hot_picks.slip).
    pass_fn(legs) optional extra filter (matchup); default identity.
    """
    pass_fn = pass_fn or (lambda L: list(L or []))
    today = today or dt.datetime.now(dt.timezone.utc).date().isoformat()
    masters = []
    for sid, label, pool_name in SECTION_BUILDERS:
        raw = [p for p in _POOL_FN[pool_name](doc) if not _site_ban(p)]
        pool = pass_fn(dedupe_event(_upcoming_only(raw, today)))
        legs = pack_floor(pool)
        if not legs:
            print("sectionMaster skip", sid, "empty", flush=True)
            continue
        name = "Master · " + label
        sl = book_fn(name, legs)
        sl["section"] = sid
        sl["label"] = label
        sl["picks"] = legs
        tot = round(math.prod(float(x.get("odds") or 1) for x in legs), 2)
        sl["totalOdds"] = tot
        sl["legs"] = len(legs)
        sl["meetsFloor"] = tot >= SECTION_FLOOR
        if not sl["meetsFloor"]:
            sl["note"] = f"Only {len(legs)} qualifying picks, total odds {tot:.2f}, under {SECTION_FLOOR}."
        _betway_overlay(sl, today, engine_dir=engine_dir)
        masters.append(sl)
    return masters
