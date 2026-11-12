#!/usr/bin/env python3
"""Shared helpers for the nightly GG / NYSM / NerdyTips / master jobs.

SportyBet Ghana share codes only (no-login). Never places a bet and never logs in.
A slip is booked only when the combined price is at least 25. Nothing is padded.
One match may sit on at most two codes. NG and DC 12 legs are never booked.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import subprocess
from pathlib import Path

MIN_TOTAL = 25.0
MAX_LEGS = 50
MAX_CODES_PER_EVENT = 2
SB_SHARE = "https://www.sportybet.com/api/gh/orders/share"
SB_LINK = "https://www.sportybet.com/gh/?shareCode={}"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36"
SR_HOSTS = (
    "https://lsc.fn.sportradar.com/sportybet/en/Etc:UTC/gismo/",
    "https://stats.fn.sportradar.com/sportybet/en/Europe:Berlin/gismo/",
)

# Public names never include a tipster or a bot.
PUBLIC_NAME = {
    "gg": "GG goals",
    "nysm-main": "Model main",
    "nysm-conservative": "Model conservative",
    "nysm-ts2": "Team to score 2+",
    "nt": "Checked goals",
    "master": "Code of the Day",
}

YOUTH_RE = re.compile(
    r"women|wfc|lfc|ladies|female|femen|u-?1\d|u-?2[0-3]|youth|juvenil|reserve|"
    r"srl|simulated|jong |academy|primavera|juniores|esoccer|friendly",
    re.I,
)
BAD_TEAM_RE = re.compile(r"\bii\b| 2$|\bb$", re.I)
WOMEN_RE = re.compile(r"women|\bW\b|Feminin|Frauen|Damen|Femenin|WSL|NWSL|Womens|Liga F\b", re.I)


def repo_root() -> Path:
    env = os.environ.get("REPO_DIR")
    if env:
        return Path(env)
    return Path(__file__).resolve().parents[2]


def nightly_target(now: dt.datetime | None = None, explicit: str | None = None) -> dt.date:
    """Fixture date these jobs are building.

    From 18:00 UTC the night jobs target the next Accra day, which the 06:00
    master then publishes as that day's code. A morning dispatch targets today.
    """
    if explicit:
        return dt.date.fromisoformat(explicit)
    now = now or dt.datetime.now(dt.timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=dt.timezone.utc)
    if now.hour >= 18:
        return now.date() + dt.timedelta(days=1)
    return now.date()


def product(odds) -> float:
    total = 1.0
    for odd in odds:
        total *= float(odd)
    return total


def is_ng(leg: dict) -> bool:
    sel = str(leg.get("selection") or leg.get("outcomeDesc") or "").strip().lower()
    mid = str(leg.get("marketId") or "")
    if sel in {"no", "ng", "btts no", "gg no", "both teams to score no"}:
        return True
    if mid in {"29", "60129"} and sel in {"no", "ng"}:
        return True
    if str(leg.get("outcomeId") or "") in {"76"}:
        return True
    return False


def is_dc12(leg: dict) -> bool:
    sel = str(leg.get("selection") or "").strip().lower()
    mid = str(leg.get("marketId") or "")
    oid = str(leg.get("outcomeId") or "")
    if sel in {"12", "home or away"}:
        return True
    if mid in {"10", "60110"} and (oid in {"10", "13"} or "home or away" in sel):
        return True
    return False


def absolute_ban(leg: dict) -> bool:
    """NG and DC 12 are never booked, including on a strategy-spec slip."""
    return is_ng(leg) or is_dc12(leg)


def pack_slip(legs: list[dict], cap: int = MAX_LEGS) -> tuple[list[dict], str | None]:
    """Keep a real qualifying set, or book nothing.

    Never pads. A set whose combined price is under 25 is not booked.
    More than `cap` legs is cut to the first `cap` (caller orders them);
    a leftover chunk under 25 is not booked and is not filled with extras.
    """
    clean = [leg for leg in legs if not absolute_ban(leg)]
    dropped = len(legs) - len(clean)
    if not clean:
        why = "no legs" if not legs else "only NG/DC 12 legs"
        return [], why
    kept = clean[:cap]
    note = ""
    if len(clean) > cap:
        note = f" capped at {cap} (left {len(clean) - cap} unbooked, not padded)"
    if dropped:
        note += f" dropped {dropped} NG/DC 12"
    if product(leg.get("odds") or 0 for leg in kept) < MIN_TOTAL:
        return [], f"product {product(leg.get('odds') or 0 for leg in kept):.4f} under {MIN_TOTAL:g}{note}"
    return kept, (note.strip() or None)


def thin_pack(normal: list[dict], relaxed: list[dict], cap: int = MAX_LEGS):
    """Book the normal ticket. One relaxed pass only when that ticket is under 25.

    Returns (packed, reason, used_relaxed). NG, DC 12 and the 25 minimum stay in pack_slip.
    """
    packed, why = pack_slip(normal, cap=cap)
    if packed:
        return packed, why, False
    packed, why = pack_slip(relaxed, cap=cap)
    return packed, why, bool(packed)


def tag_relaxed(slip: dict) -> dict:
    """Mark a thin-day slip. It stays HIGH RISK."""
    slip["relaxed"] = True
    slip["highRisk"] = True
    slip["riskRating"] = "HIGH"
    slip["riskLabel"] = "HIGH RISK"
    name = str(slip.get("name") or "")
    if "Relaxed" not in name:
        if " · HIGH RISK" in name:
            slip["name"] = name.replace(" · HIGH RISK", " · Relaxed · HIGH RISK", 1)
        else:
            slip["name"] = f"{name} · Relaxed".strip()
    note = str(slip.get("warning") or "")
    if "Thin-day" not in note:
        slip["warning"] = (note + " Thin-day relaxed filters. Still HIGH RISK. Not safe or guaranteed.").strip()
    return slip


def chunk_bookable(legs: list[dict], cap: int = MAX_LEGS) -> list[list[dict]]:
    """Split a long qualifying list into bookable parts. Parts under 25 are omitted."""
    clean = [leg for leg in legs if not absolute_ban(leg)]
    if not clean:
        return []
    parts = [clean[i:i + cap] for i in range(0, len(clean), cap)]
    return [part for part in parts if product(leg.get("odds") or 0 for leg in part) >= MIN_TOTAL]


def can_take(usage: dict, event_id: str, limit: int = MAX_CODES_PER_EVENT) -> bool:
    return len(usage.get(event_id) or []) < limit


def take(usage: dict, event_id: str, code_id: str, limit: int = MAX_CODES_PER_EVENT) -> bool:
    """Record event_id on code_id when that would not be a third code."""
    have = usage.setdefault(event_id, [])
    if code_id in have:
        return True
    if len(have) >= limit:
        return False
    have.append(code_id)
    return True


def usage_path(repo: Path, day: str) -> Path:
    return repo / "engine" / "data" / "strategy-usage" / f"{day}.json"


def load_usage(repo: Path, day: str) -> dict:
    path = usage_path(repo, day)
    try:
        raw = json.loads(path.read_text())
    except Exception:
        raw = {}
    events = {eid: list(codes) for eid, codes in (raw.get("events") or {}).items()}
    _merge_published(repo, day, events)
    return events


def save_usage(repo: Path, day: str, events: dict) -> None:
    path = usage_path(repo, day)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"date": day, "events": events}, indent=1) + "\n")


def _codes_of_slip(slip: dict) -> list[str]:
    found = []
    code = slip.get("code")
    if code:
        found.append(str(code))
    codes = slip.get("codes") or {}
    sb = codes.get("sportybet")
    if isinstance(sb, list):
        for item in sb:
            if isinstance(item, dict) and item.get("code"):
                found.append(str(item["code"]))
            elif isinstance(item, str):
                found.append(item)
    elif isinstance(sb, dict) and sb.get("code"):
        found.append(str(sb["code"]))
    elif isinstance(sb, str):
        found.append(sb)
    return found


def _merge_published(repo: Path, day: str, events: dict) -> None:
    """Count codes already published for this fixture date."""
    blobs = []
    for name in ("high_odds.json", "home-picks.json", "hot-picks.json", "picks.json"):
        path = repo / name
        if path.exists():
            try:
                blobs.append(json.loads(path.read_text()))
            except Exception:
                pass
    master = repo / "engine" / "data" / "daily-master" / f"{day}.json"
    if master.exists():
        try:
            blobs.append(json.loads(master.read_text()))
        except Exception:
            pass
    root = repo / "engine" / "data" / "strategy-codes"
    if root.exists():
        for path in root.glob(f"*/*{day}*.json"):
            try:
                blobs.append(json.loads(path.read_text()))
            except Exception:
                pass

    def walk(node, sink):
        if isinstance(node, list):
            for item in node:
                walk(item, sink)
        elif isinstance(node, dict):
            if node.get("code") or (isinstance(node.get("codes"), dict) and node.get("legs") is not None):
                sink.append(node)
            for value in node.values():
                if isinstance(value, (dict, list)):
                    walk(value, sink)

    slips = []
    for blob in blobs:
        walk(blob, slips)
    for slip in slips:
        codes = _codes_of_slip(slip)
        if not codes:
            continue
        legs = slip.get("legList") or slip.get("legs") or []
        if isinstance(legs, dict):
            legs = [legs]
        if not isinstance(legs, list):
            continue
        for leg in legs:
            if not isinstance(leg, dict):
                continue
            eid = leg.get("eventId")
            if not eid:
                continue
            leg_day = str(leg.get("date") or slip.get("date") or "")[:10]
            if leg_day and leg_day != day:
                continue
            have = events.setdefault(eid, [])
            for code in codes:
                if code not in have:
                    have.append(code)


def http_json(url: str, timeout: int = 30, method: str = "GET", body: dict | None = None, headers: list | None = None):
    cmd = ["curl", "-sS", "-m", str(timeout), "-A", UA, "-H", "Accept: application/json"]
    for header in headers or []:
        cmd += ["-H", header]
    if method != "GET":
        cmd += ["-X", method]
    if body is not None:
        cmd += ["-H", "Content-Type: application/json", "-d", json.dumps(body)]
    cmd.append(url)
    try:
        out = subprocess.run(cmd, capture_output=True, text=True).stdout
        if not out or out.strip()[:1] not in "{[":
            return {}
        return json.loads(out)
    except Exception:
        return {}


def sr_get(path: str, cache: dict | None = None):
    if cache is not None and path in cache:
        return cache[path]
    data = None
    for host in SR_HOSTS:
        payload = http_json(host + path, timeout=25)
        try:
            data = (payload.get("doc") or [{}])[0].get("data")
        except Exception:
            data = None
        if data:
            break
    if cache is not None:
        cache[path] = data
    return data


def specifier(value) -> str:
    return "" if value is None else str(value)


def event_odds(event: dict) -> dict:
    """Map 'marketId|specifier|desc' -> [odds, outcomeId] for active prices."""
    odds = {}
    for market in event.get("markets") or []:
        spec = specifier(market.get("specifier"))
        mid = str(market.get("id"))
        for outcome in market.get("outcomes") or []:
            if outcome.get("isActive") == 0:
                continue
            try:
                price = float(outcome.get("odds") or 0)
            except Exception:
                continue
            if price <= 1:
                continue
            odds[f"{mid}|{spec}|{outcome.get('desc')}"] = [price, str(outcome.get("id"))]
    return odds


def event_kick(event: dict) -> dt.datetime | None:
    ts = event.get("estimateStartTime") or 0
    if not ts:
        return None
    return dt.datetime.fromtimestamp(ts / 1000, dt.timezone.utc)


def league_of(event: dict) -> tuple[str, str]:
    try:
        cat = event["sport"]["category"]
        return cat.get("name") or "", (cat.get("tournament") or {}).get("name") or ""
    except Exception:
        return "", event.get("tournamentName") or ""


def youth_or_sim(home: str, away: str, country: str = "", league: str = "") -> bool:
    blob = " ".join([country or "", league or "", home or "", away or ""])
    if YOUTH_RE.search(blob):
        return True
    if BAD_TEAM_RE.search(home or "") or BAD_TEAM_RE.search(away or ""):
        return True
    low = blob.lower()
    if "srl" in low or "esoccer" in low or "simulated" in low:
        return True
    return False


def women_match(home: str, away: str, league: str = "") -> bool:
    return bool(WOMEN_RE.search(f"{home} {away} {league}"))


def fetch_upcoming(market_ids: str = "1,10,11,18,19,20,29") -> list[dict]:
    ids = market_ids.replace(",", "%2C")
    events = []
    page = 1
    total = None
    while page < 40:
        url = (
            "https://www.sportybet.com/api/gh/factsCenter/pcUpcomingEvents"
            f"?sportId=sr%3Asport%3A1&marketId={ids}&pageSize=100&pageNum={page}&option=1"
        )
        payload = http_json(url, timeout=40)
        data = payload.get("data") or {}
        if total is None:
            total = int(data.get("totalNum") or 0)
        tournaments = data.get("tournaments") or []
        if not tournaments:
            break
        for tournament in tournaments:
            events.extend(tournament.get("events") or [])
        if page * 100 >= total:
            break
        page += 1
    return events


def book_sportybet(selections: list[dict]) -> tuple[str | None, str]:
    """POST the public Ghana share endpoint. Does not log in and does not place a bet."""
    if not selections:
        return None, "empty"
    payload = {"selections": []}
    for sel in selections:
        payload["selections"].append({
            "eventId": sel["eventId"],
            "marketId": str(sel["marketId"]),
            "specifier": sel.get("specifier") or None,
            "outcomeId": str(sel["outcomeId"]),
        })
    response = http_json(SB_SHARE, timeout=40, method="POST", body=payload)
    if response.get("bizCode") != 10000:
        return None, (response.get("message") or "book failed")[:200]
    data = response.get("data") or {}
    code = data.get("shareCode")
    bad = [
        row for row in data.get("outcomes") or []
        if str(row.get("matchStatus") or "").strip().lower() not in {"not start", "0", ""}
    ]
    return code, ("ok" if not bad else f"{len(bad)} not open")


def read_share(code: str) -> dict:
    response = http_json(f"{SB_SHARE}/{code}", timeout=30)
    return response.get("data") or {}


def share_total(data: dict) -> tuple[float, set]:
    total = 1.0
    started = set()
    for row in data.get("outcomes") or []:
        market = (row.get("markets") or [{}])[0]
        outcome = (market.get("outcomes") or [{}])[0]
        try:
            total *= float(outcome.get("odds") or 0)
        except Exception:
            pass
        if str(row.get("matchStatus") or "").strip().lower() not in {"not start", "0", ""}:
            started.add(row.get("eventId"))
    return total, started


def selection_body(leg: dict) -> dict:
    return {
        "eventId": leg["eventId"],
        "marketId": str(leg["marketId"]),
        "specifier": leg.get("specifier") or None,
        "outcomeId": str(leg["outcomeId"]),
    }


def book_confirmed(legs: list[dict]) -> dict:
    """Book, drop legs that have already started, rebook, refuse a ticket under 25."""
    pending = list(legs)
    code, status = book_sportybet([selection_body(leg) for leg in pending])
    if not code:
        return {"code": None, "reason": status or "book failed", "legs": []}
    data = read_share(code)
    total, started = share_total(data)
    if started:
        pending = [leg for leg in pending if leg.get("eventId") not in started]
        packed, why = pack_slip(pending)
        if not packed:
            return {"code": None, "reason": why or "started legs left the ticket under 25", "legs": [], "droppedStarted": list(started)}
        return book_confirmed(packed)
    if total < MIN_TOTAL:
        return {
            "code": None,
            "reason": f"share read-back {total:.2f} under {MIN_TOTAL:g}",
            "legs": pending,
            "wouldHave": code,
        }
    return {"code": code, "status": status, "total": round(total, 2), "legs": pending, "link": SB_LINK.format(code)}


def public_slip(slip_id: str, day: str, code: str, legs: list[dict], total: float, part: int | None = None, relaxed: bool = False) -> dict:
    name = PUBLIC_NAME.get(slip_id, "Strategy")
    if part:
        name = f"{name} {part}"
    link = SB_LINK.format(code)
    slip = {
        "code": code,
        "bookmaker": "SportyBet",
        "book": "sportybet",
        "name": f"{name} · HIGH RISK",
        "date": day,
        "odds": total,
        "share": link,
        "legs": legs,
        "origin": f"strategy-{slip_id}",
        "strategyJob": True,
        "strategySpec": True,
        "status": "pending",
        "riskRating": "HIGH",
        "riskLabel": "HIGH RISK",
        "highRisk": True,
        "warning": "HIGH RISK accumulator. Not safe or guaranteed. Records only — no bet is placed here.",
        "codes": {"sportybet": {"code": code, "legs": len(legs), "odds": total, "link": link}},
        "lastKickoff": max((leg.get("kickoff") or "") for leg in legs) if legs else None,
    }
    if relaxed:
        tag_relaxed(slip)
    return slip


def publish_high_odds(repo: Path, slip: dict) -> None:
    path = repo / "high_odds.json"
    try:
        doc = json.loads(path.read_text()) if path.exists() else {}
    except Exception:
        doc = {}
    if not isinstance(doc, dict):
        doc = {}
    slips = [row for row in (doc.get("slips") or []) if row.get("code") != slip.get("code")]
    slips.insert(0, slip)
    doc["slips"] = slips
    path.write_text(json.dumps(doc, ensure_ascii=False, separators=(",", ":")))
    # Odds above 25 are sealed only when paid mode is on. Free mode (p2u-free-mode.js) leaves the code public.
    lock_public(repo)


def lock_public(repo: Path) -> None:
    """Same premium lock the morning, M1/M2 and strategies jobs run after they publish.

    `P2U_FREE_CODES` / `p2u-free-mode.js` wins: free mode does not flag or hide a code.
    Paid mode files the code in the paywall store and blanks it on the public feeds.
    `high_odds.json` stays one-line JSON either way.
    """
    import sys
    root = str(repo)
    if root not in sys.path:
        sys.path.insert(0, root)
    from engine.premium import lock_published
    lock_published(root)


def write_record(repo: Path, kind: str, day: str, payload: dict) -> Path:
    path = repo / "engine" / "data" / "strategy-codes" / kind / f"{day}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=1, ensure_ascii=False) + "\n")
    return path


def leg_from_key(event: dict, key: str, odds_map: dict, **extra) -> dict | None:
    price = odds_map.get(key)
    if not price:
        return None
    mid, spec, desc = key.split("|", 2)
    kick = event_kick(event)
    country, league = league_of(event)
    home = event.get("homeTeamName") or extra.get("home") or ""
    away = event.get("awayTeamName") or extra.get("away") or ""
    row = {
        "eventId": event.get("eventId") or extra.get("eventId"),
        "marketId": mid,
        "specifier": spec or None,
        "outcomeId": str(price[1]),
        "market": extra.get("market") or desc,
        "selection": extra.get("selection") or desc,
        "odds": float(price[0]),
        "match": f"{home} v {away}",
        "home": home,
        "away": away,
        "league": f"{country} - {league}".strip(" -"),
        "country": country,
        "date": kick.date().isoformat() if kick else extra.get("date"),
        "ko": kick.strftime("%H:%M") if kick else extra.get("ko"),
        "kickoff": kick.isoformat().replace("+00:00", "Z") if kick else None,
        "result": "pending",
        "matchStatus": "Not start",
    }
    row.update({k: v for k, v in extra.items() if k not in row})
    return row
