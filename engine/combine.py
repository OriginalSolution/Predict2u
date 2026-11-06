"""Combine short inbox / imported slips into 25+ tickets instead of dropping them.

Source share codes under min_main_slip_odds are decoded (or accepted as
already-decoded picks), started games / DC / NG are removed, matchup rules
and the odds cap are applied, one market is kept per game, then surviving
legs are packed into one or more slips at or above the minimum. Leftover
legs that cannot form another 25+ slip are merged into the last slip so
they are never discarded for being under the floor.
"""
from __future__ import annotations
import datetime as dt
import json
import math
import os
import subprocess
import time
from pathlib import Path

from .rules import check, is_btts_no, is_dc_vetoed
from .paths import ENGINE_DIR, VENDOR_DIR
import sys
if str(VENDOR_DIR) not in sys.path:
    sys.path.insert(0, str(VENDOR_DIR))
import matchup_rules as mr  # noqa: E402

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36"
MIN_SLIP_DEFAULT = 25


def fetch_x12(event_id: str):
    if not event_id:
        return None
    from urllib.parse import quote
    url = f"https://www.sportybet.com/api/gh/factsCenter/event?eventId={quote(event_id, safe='')}&productId=3"
    raw = subprocess.run(["curl","-s","-m","18","-A",UA,"-H","Accept: application/json",url], capture_output=True, text=True).stdout
    try:
        e = (json.loads(raw) or {}).get("data") or {}
    except Exception:
        return None
    for m in e.get("markets") or []:
        if str(m.get("id")) == "1" and not (m.get("specifier") or ""):
            odds = {x.get("desc"): x.get("odds") for x in m.get("outcomes") or []}
            if all(k in odds for k in ("Home", "Draw", "Away")):
                return f"{odds['Home']}/{odds['Draw']}/{odds['Away']}"
    return None


def attach_x12(picks):
    cache = {}
    for p in picks:
        if p.get("x12"):
            continue
        eid = p.get("eventId")
        if eid not in cache:
            cache[eid] = fetch_x12(eid)
        if cache[eid]:
            p["x12"] = cache[eid]
            case = p.get("case") or ""
            if "1X2 " not in case:
                p["case"] = (case + "; " if case else "") + f"1X2 {cache[eid]}"
    return picks


def load_min_odds() -> float:
    cfg = ENGINE_DIR / "config.json"
    try:
        return float(json.loads(cfg.read_text()).get("min_main_slip_odds") or MIN_SLIP_DEFAULT)
    except Exception:
        return float(MIN_SLIP_DEFAULT)


def product(legs) -> float:
    tot = 1.0
    for p in legs:
        tot *= float(p.get("odds") or 1)
    return round(tot, 2)


def is_started(p, now=None) -> bool:
    now = now or dt.datetime.now(dt.timezone.utc)
    raw = p.get("kickoff") or p.get("ko") or p.get("estimateStartTime") or p.get("ts")
    if isinstance(raw, (int, float)) and raw > 10_000_000:
        ko = dt.datetime.fromtimestamp(raw / 1000.0, dt.timezone.utc)
    elif isinstance(raw, str) and raw:
        s = raw.replace("Z", "+00:00")
        try:
            ko = dt.datetime.fromisoformat(s)
            if ko.tzinfo is None:
                ko = ko.replace(tzinfo=dt.timezone.utc)
        except Exception:
            ko = None
    else:
        ko = None
    if ko and ko <= now:
        return True
    status = str(p.get("matchStatus") or p.get("status") or "").strip().lower()
    if status in {"ended", "live", "playing", "1st half", "2nd half", "halftime", "ht", "finished", "closed"}:
        return True
    return False


def decode_share(code: str) -> list[dict]:
    url = f"https://www.sportybet.com/api/gh/orders/share/{code}?_t={int(time.time() * 1000)}"
    raw = subprocess.run(
        ["curl", "-s", "-m", "20", "-A", UA, "-H", "Accept: application/json", url],
        capture_output=True, text=True,
    ).stdout
    try:
        data = (json.loads(raw) or {}).get("data") or {}
    except Exception:
        return []
    out = []
    for ev in data.get("outcomes") or []:
        home, away = ev.get("homeTeamName"), ev.get("awayTeamName")
        ts = ev.get("estimateStartTime")
        ko = dt.datetime.fromtimestamp(ts / 1000, dt.timezone.utc) if ts else None
        league = ((ev.get("sport") or {}).get("category") or {}).get("tournament") or {}
        country = ((ev.get("sport") or {}).get("category") or {}).get("name")
        lg = league.get("name")
        if country and lg:
            lg = f"{country} - {lg}"
        for m in ev.get("markets") or []:
            for o in m.get("outcomes") or []:
                try:
                    odds = float(o.get("odds") or 0)
                except Exception:
                    odds = 0
                out.append({
                    "eventId": ev.get("eventId"),
                    "match": f"{home} v {away}",
                    "league": lg,
                    "market": m.get("name") or m.get("desc") or "",
                    "marketId": str(m.get("id") or ""),
                    "specifier": m.get("specifier") or "",
                    "selection": o.get("desc") or "",
                    "outcomeId": str(o.get("id") or ""),
                    "odds": odds,
                    "kickoff": ko.isoformat() if ko else None,
                    "ts": ts,
                    "matchStatus": ev.get("matchStatus") or ev.get("status"),
                    "sourceCode": code,
                })
    return out


def filter_legs(picks, now=None, enrich=True, apply_rules=True):
    """Drop started / DC / NG / rule failures. Returns (kept, dropped)."""
    now = now or dt.datetime.now(dt.timezone.utc)
    kept, dropped = [], []
    for raw in picks:
        p = dict(raw)
        if is_started(p, now=now):
            dropped.append({**_brief(p), "reason": "started"})
            continue
        if is_dc_vetoed(p):
            dropped.append({**_brief(p), "reason": "double-chance-veto"})
            continue
        if is_btts_no(p):
            dropped.append({**_brief(p), "reason": "btts-no-veto"})
            continue
        if not apply_rules:
            kept.append(p)
            continue
        if enrich:
            try:
                mr.enrich(p)
            except Exception:
                pass
        if not p.get("x12"):
            attach_x12([p])
        ok, cls, why = check(p)
        if not ok:
            dropped.append({**_brief(p), "reason": why or cls, "gate": cls})
            continue
        p["matchup"] = cls
        p["gateWhy"] = why
        kept.append(p)
    return kept, dropped


def _brief(p):
    return {k: p.get(k) for k in ("eventId", "match", "market", "selection", "odds", "marketId", "specifier", "outcomeId", "sourceCode") if p.get(k) is not None}


def dedupe_one_per_game(picks):
    """Keep a single passing market per eventId. Prefer more source copies, then shorter odds."""
    from collections import defaultdict
    by = defaultdict(list)
    for p in picks:
        by[p.get("eventId")].append(p)
    kept, dropped = [], []
    for eid, group in by.items():
        if len(group) == 1:
            kept.append(group[0])
            continue
        # identical market: keep one
        keys = {(p.get("marketId"), p.get("specifier") or "", p.get("outcomeId")) for p in group}
        if len(keys) == 1:
            kept.append(group[0])
            for extra in group[1:]:
                dropped.append({**_brief(extra), "reason": "duplicate-same-market"})
            continue

        def score(p):
            key = (p.get("marketId"), p.get("specifier") or "", p.get("outcomeId"))
            freq = sum(1 for x in group if (x.get("marketId"), x.get("specifier") or "", x.get("outcomeId")) == key)
            return (freq, -float(p.get("odds") or 9), -len(str(p.get("selection") or "")))

        winner = max(group, key=score)
        kept.append(winner)
        for extra in group:
            if extra is winner:
                continue
            if (extra.get("marketId"), extra.get("specifier") or "", extra.get("outcomeId")) == (
                winner.get("marketId"), winner.get("specifier") or "", winner.get("outcomeId")
            ):
                dropped.append({**_brief(extra), "reason": "duplicate-same-market"})
            else:
                dropped.append({**_brief(extra), "reason": "duplicate-other-market", "kept": extra.get("selection") and winner.get("selection")})
    return kept, dropped


def pack_slips(legs, min_odds=None):
    """Pack legs into slips at or above min_odds. Do not drop a leftover under-25 group; merge it."""
    min_odds = float(min_odds if min_odds is not None else load_min_odds())
    ordered = sorted(legs, key=lambda p: (p.get("kickoff") or p.get("ko") or "", p.get("match") or ""))
    slips, cur = [], []
    for p in ordered:
        cur.append(p)
        if product(cur) >= min_odds:
            slips.append(cur)
            cur = []
    if cur:
        if slips:
            slips[-1].extend(cur)
        else:
            slips.append(cur)
    out = []
    for i, s in enumerate(slips, 1):
        out.append({
            "name": "Combined selection",
            "label": f"Combined {i}",
            "odds": product(s),
            "legs": s,
            "minOdds": min_odds,
            "meetsFloor": product(s) >= min_odds,
        })
    return out


def _unique_candidates(picks):
    """Collapse identical markets before the expensive enrich/check."""
    seen = {}
    extras = []
    for p in picks:
        key = (p.get("eventId"), p.get("marketId"), p.get("specifier") or "", p.get("outcomeId"))
        if key in seen:
            extras.append({**_brief(p), "reason": "duplicate-same-market"})
        else:
            seen[key] = p
    return list(seen.values()), extras

def process(picks, now=None, min_odds=None, enrich=True):
    min_odds = float(min_odds if min_odds is not None else load_min_odds())
    cheap, dropped = filter_legs(picks, now=now, enrich=False, apply_rules=False)
    # Re-run check (and optional enrich) once per unique market.
    unique, dup_same = _unique_candidates(cheap)
    dropped.extend(dup_same)
    filtered, rule_drop = filter_legs(unique, now=now, enrich=enrich)
    dropped.extend(rule_drop)
    deduped, dup_drop = dedupe_one_per_game(filtered)
    dropped.extend(dup_drop)
    slips = pack_slips(deduped, min_odds=min_odds)
    return {
        "minOdds": min_odds,
        "input": len(picks),
        "used": [_brief(p) | {"odds": p.get("odds"), "matchup": p.get("matchup")} for s in slips for p in s["legs"]],
        "dropped": dropped,
        "slips": slips,
    }


def process_share_codes(codes, now=None, min_odds=None, enrich=True):
    picks = []
    for code in codes:
        picks.extend(decode_share(code))
    return process(picks, now=now, min_odds=min_odds, enrich=enrich)
