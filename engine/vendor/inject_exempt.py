#!/usr/bin/env python3
"""Inject gate-exempt one-code exceptions into Predict2u placements.

Placements: Code of the Day (home-picks Main slip), Hot Picks, High Odds.
Exempt codes bypass publishing gates/prune until kickoffs pass, then settle normally.
Never print tipster/bot names on the public site.
"""
from __future__ import annotations
import datetime as dt
import json
import sys
from pathlib import Path

FEED = Path(__file__).resolve().parent
REPO = Path(sys.argv[1] if len(sys.argv) > 1 else "/workspace/Predict2u")
EXEMPT_PATHS = [
    FEED / "gate_exempt.json",
    REPO / "engine" / "gate_exempt.json",
    Path("/workspace/predict2u-feed/gate_exempt.json"),
]
BOOKED = Path("/workspace/master06/booked.json")
SHARE = Path("/workspace/master06/share_F3PCEP.json")
NOW = dt.datetime.now(dt.timezone.utc)
TODAY = NOW.date().isoformat()
WARNING = "High-risk 69-leg accumulator, not safe or guaranteed, stake small"


def load(path, default=None):
    try:
        return json.loads(Path(path).read_text())
    except Exception:
        return default


def save(path, data):
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n")


def exempt_doc():
    for p in EXEMPT_PATHS:
        if p.exists():
            return load(p, {})
    return {}


def booked_payload(code: str):
    b = load(BOOKED, {})
    if (b.get("code") or "").upper() != code.upper():
        # allow share-only fallback
        return None
    return b


def home_legs(booked):
    out = []
    for L in booked.get("legs") or []:
        ko = str(L.get("ko") or "")
        date, time = (ko.split(" ", 1) + [""])[:2] if " " in ko else (TODAY, ko)
        out.append({
            "date": date or TODAY,
            "ko": (time or "")[:5],
            "match": L.get("match"),
            "market": L.get("marketDesc") or L.get("market"),
            "selection": L.get("outcomeDesc") or L.get("selection"),
            "odds": L.get("odds"),
            "eventId": L.get("eventId"),
            "marketId": str(L.get("marketId") or ""),
            "specifier": L.get("specifier"),
            "outcomeId": str(L.get("outcomeId") or ""),
            "result": "pending",
        })
    return out


def high_legs(booked):
    out = []
    for L in booked.get("legs") or []:
        ko = str(L.get("ko") or "")
        date, time = (ko.split(" ", 1) + [""])[:2] if " " in ko else (TODAY, ko)
        kick = None
        if date and time:
            kick = f"{date}T{time[:5]}:00Z"
        out.append({
            "eventId": L.get("eventId"),
            "marketId": str(L.get("marketId") or ""),
            "specifier": L.get("specifier") or "",
            "outcomeId": str(L.get("outcomeId") or ""),
            "date": date or TODAY,
            "ko": (time or "")[:5],
            "kickoff": kick,
            "league": L.get("league"),
            "match": L.get("match"),
            "market": L.get("marketDesc") or L.get("market"),
            "selection": L.get("outcomeDesc") or L.get("selection"),
            "odds": L.get("odds"),
            "liveOdds": L.get("odds"),
            "result": "pending",
            "matchStatus": L.get("matchStatus") or "Not start",
            "score": None,
            "played": None,
        })
    return out


def inject_home(entry, booked):
    path = REPO / "home-picks.json"
    doc = load(path, {}) or {}
    code = entry["code"]
    legs = home_legs(booked)
    slip = {
        "name": "Main banker: Banker code of the day",
        "label": "Code of the Day",
        "totalOdds": booked.get("combined_odds") or entry.get("odds"),
        "legs": legs,
        "picks": len(legs),
        "codes": {"sportybet": code},
        "links": {"sportybet": entry.get("share") or f"https://www.sportybet.com/gh/?shareCode={code}"},
        "bookOdds": {"sportybet": booked.get("combined_odds") or entry.get("odds")},
        "bookPicks": {"sportybet": len(legs)},
        "risk": "high",
        "highRisk": True,
        "warning": entry.get("warning") or WARNING,
        "gateExempt": True,
        "banker": True,
        "strategy": entry.get("warning") or WARNING,
        "bookStatus": "ok",
        "bookedAt": NOW.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "date": entry.get("date") or TODAY,
        "dates": [entry.get("date") or TODAY],
    }
    slips = [s for s in (doc.get("slips") or []) if not (
        s.get("gateExempt") or (s.get("codes") or {}).get("sportybet") == code or
        str(s.get("name") or "").lower().startswith("main banker")
    )]
    # drop superseded
    for old in entry.get("supersedes") or []:
        slips = [s for s in slips if (s.get("codes") or {}).get("sportybet") != old]
    slips.insert(0, slip)
    doc["slips"] = slips
    doc["DATA_UPDATED"] = NOW.strftime("%Y-%m-%dT%H:%M:%SZ")
    if not doc.get("date"):
        doc["date"] = TODAY
    save(path, doc)
    print("home-picks: injected", code)


def inject_hot(entry, booked):
    path = REPO / "hot-picks.json"
    doc = load(path, {}) or {}
    code = entry["code"]
    legs = home_legs(booked)
    events = [L["eventId"] for L in legs if L.get("eventId")]
    leg_key = [f"{L['eventId']}:{L['outcomeId']}" for L in legs if L.get("eventId")]
    slip = {
        "name": "Code of the Day · HIGH RISK",
        "legKey": leg_key,
        "legs": len(legs),
        "totalOdds": booked.get("combined_odds") or entry.get("odds"),
        "events": events,
        "picksDetail": legs,
        "codes": {
            "sportybet": [{
                "code": code,
                "totalOdds": booked.get("combined_odds") or entry.get("odds"),
                "legs": len(legs),
                "link": entry.get("share") or f"https://www.sportybet.com/gh/?shareCode={code}",
            }]
        },
        "bookedAt": NOW.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "highRisk": True,
        "warning": entry.get("warning") or WARNING,
        "gateExempt": True,
        "date": entry.get("date") or TODAY,
    }
    slips = [s for s in (doc.get("slips") or []) if not (s.get("gateExempt") or (
        isinstance((s.get("codes") or {}).get("sportybet"), list) and
        any((x.get("code") if isinstance(x, dict) else x) == code for x in ((s.get("codes") or {}).get("sportybet") or []))
    ))]
    for old in entry.get("supersedes") or []:
        slips = [s for s in slips if not (
            isinstance((s.get("codes") or {}).get("sportybet"), list) and
            any((x.get("code") if isinstance(x, dict) else x) == old for x in ((s.get("codes") or {}).get("sportybet") or []))
        )]
    slips.insert(0, slip)
    doc["slips"] = slips
    doc["mainNote"] = f"HIGH RISK — {entry.get('warning') or WARNING}"
    doc["updatedAt"] = NOW.strftime("%Y-%m-%dT%H:%M:%SZ")
    save(path, doc)
    print("hot-picks: injected", code)


def inject_high(entry, booked):
    path = REPO / "high_odds.json"
    doc = load(path, {}) or {}
    code = entry["code"]
    legs = high_legs(booked)
    last_ko = None
    for L in legs:
        if L.get("kickoff") and (last_ko is None or L["kickoff"] > last_ko):
            last_ko = L["kickoff"]
    slip = {
        "code": code,
        "bookmaker": "SportyBet",
        "book": "sportybet",
        "name": "Master accumulator · HIGH RISK",
        "date": entry.get("date") or TODAY,
        "odds": booked.get("combined_odds") or entry.get("odds"),
        "decodedOdds": booked.get("combined_odds") or entry.get("odds"),
        "share": entry.get("share") or f"https://www.sportybet.com/gh/?shareCode={code}",
        "shareUrl": f"https://predict2u.com/high-odds/#{code}",
        "verifiedAt": NOW.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "verification": entry.get("warning") or WARNING,
        "warning": entry.get("warning") or WARNING,
        "origin": "strategy",
        "status": "pending",
        "hit": 0,
        "lostLegs": 0,
        "total": len(legs),
        "settledAt": None,
        "live": False,
        "lastKickoff": last_ko,
        "riskScore": 100,
        "riskRating": "Extreme",
        "highRisk": True,
        "gateExempt": True,
        "addedAt": NOW.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "legs": legs,
        "codes": {
            "sportybet": {
                "code": code,
                "legs": len(legs),
                "odds": booked.get("combined_odds") or entry.get("odds"),
                "link": entry.get("share") or f"https://www.sportybet.com/gh/?shareCode={code}",
            }
        },
    }
    slips = [s for s in (doc.get("slips") or []) if s.get("code") != code and s.get("code") not in (entry.get("supersedes") or [])]
    history = [s for s in (doc.get("history") or []) if s.get("code") != code]
    slips.insert(0, slip)
    doc["slips"] = slips
    doc["history"] = history
    doc["updatedAt"] = NOW.strftime("%Y-%m-%dT%H:%M:%SZ")
    save(path, doc)
    print("high_odds: injected", code)


def main():
    doc = exempt_doc()
    entries = doc.get("entries") or []
    if not entries and doc.get("codes"):
        entries = [{"code": c, "warning": WARNING, "gateExempt": True} for c in doc["codes"]]
    if not entries:
        print("inject_exempt: no entries")
        return 0
    for entry in entries:
        code = entry["code"]
        if code.upper() == "DBKX8G":
            print("skip superseded", code)
            continue
        booked = booked_payload(code)
        if not booked:
            print("missing booked.json for", code)
            continue
        # expire after last kickoff
        latest = booked.get("latest_ko_gmt") or entry.get("latestKo")
        if latest:
            try:
                t = dt.datetime.strptime(latest, "%Y-%m-%d %H:%M").replace(tzinfo=dt.timezone.utc)
                # keep through the day of last KO; prune/settle handle removal after games finish
                if t.date() < NOW.date():
                    print("expired", code)
                    continue
            except Exception:
                pass
        if "codeOfTheDay" in (entry.get("placements") or ["codeOfTheDay", "hotPicks", "highOdds"]):
            inject_home(entry, booked)
        if "hotPicks" in (entry.get("placements") or ["codeOfTheDay", "hotPicks", "highOdds"]):
            inject_hot(entry, booked)
        if "highOdds" in (entry.get("placements") or ["codeOfTheDay", "hotPicks", "highOdds"]):
            inject_high(entry, booked)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
