"""Shared SportyBet / Sportradar helpers for the nightly strategy jobs.

Sportradar gismo returns event=exception for paths that still contain
`sr:match:`. The numeric id (`match_info/72221392`) is the one that resolves
teams, season and tables. Market lookup accepts id plus specifier and does
not treat a 1X2 outcome id as a Draw No Bet id.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import subprocess
from pathlib import Path

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36"
SR = "https://stats.fn.sportradar.com/sportybet/en/Europe:Berlin/gismo/"
UPCOMING = (
    "https://www.sportybet.com/api/gh/factsCenter/pcUpcomingEvents"
    "?sportId=sr%3Asport%3A1&marketId=1%2C18&pageSize=100&pageNum={page}&option=1"
)
EVENT = "https://www.sportybet.com/api/gh/factsCenter/event?eventId={eid}&productId=3"

# Women, youth, reserve/B, amateur, university, simulated. Cups are NOT in this list
# (M1/M2 allow cups; three_strategies adds its own cup skip).
SKIP = re.compile(
    r"\b(U-?\d{2}|youth|junior|reserves?|women|woman|ladies|primavera|academy|"
    r"amateur|university|college|ncaa|friendly|simulat|srl|esoccer|esports|"
    r"regionalliga|landesliga|isthmian|non-?league)\b|\(w\)",
    re.I,
)
TEAMX = re.compile(r"(\s(II|III|IV|B|C|W|U-?\d{2})|\s\(W\))$", re.I)

WINDOW_DAYS = 4  # standing rule: games within 4 days


def numeric_event_id(eid) -> str:
    return str(eid or "").rsplit(":", 1)[-1]


def stats_paths(eid) -> list[str]:
    """Sportradar paths that actually resolve. Never the raw sr:match id."""
    n = numeric_event_id(eid)
    if not n or n.startswith("sr"):
        return []
    return [f"match_info/{n}", f"stats_match_get/{n}"]


def cache_dir() -> Path:
    base = os.environ.get("STATS_CACHE") or str(
        Path(__file__).resolve().parents[1] / "data" / "stats-cache"
    )
    p = Path(base)
    p.mkdir(parents=True, exist_ok=True)
    return p


def curl_json(url, timeout=25, headers=None):
    cmd = ["curl", "-s", "-m", str(timeout), "-A", UA, "-H", "Accept: application/json"]
    for h in headers or []:
        cmd += ["-H", h]
    cmd.append(url)
    try:
        raw = subprocess.run(cmd, capture_output=True, text=True).stdout
        if raw and raw.strip()[:1] in "{[":
            return json.loads(raw)
    except Exception:
        return {}
    return {}


def sr_get(path):
    if not path or "sr:match:" in path:
        return None
    f = cache_dir() / (path.replace("/", "_") + ".json")
    if f.exists():
        try:
            return json.loads(f.read_text())
        except Exception:
            pass
    d = curl_json(SR + path, timeout=20)
    data = None
    try:
        doc = (d.get("doc") or [{}])[0]
        if doc.get("event") != "exception":
            data = doc.get("data")
    except Exception:
        data = None
    try:
        f.write_text(json.dumps(data))
    except Exception:
        pass
    return data


def event_context(eid):
    """Home/away uids and season id. Empty when Sportradar has no match."""
    hu = au = season = None
    for path in stats_paths(eid):
        md = sr_get(path) or {}
        mm = md.get("match") or md
        teams = mm.get("teams") or {}
        hu = hu or (teams.get("home") or {}).get("uid")
        au = au or (teams.get("away") or {}).get("uid")
        season = season or mm.get("_seasonid") or md.get("_seasonid")
        if hu and au and season:
            break
    return {"hu": hu, "au": au, "season": season}


def find_outcome(markets, mid, spec="", oid=None, desc_prefix=None, desc_is=None):
    """Return (market, outcome, odds) or None.

    spec '' matches an empty specifier only. A wrong outcome id does not fall
    through to a different outcome on the same market.
    """
    for m in markets or []:
        if str(m.get("id") or m.get("marketId") or "") != str(mid):
            continue
        if (m.get("specifier") or "") != (spec or ""):
            continue
        for o in m.get("outcomes") or []:
            if oid is not None and str(o.get("id")) != str(oid):
                continue
            desc = str(o.get("desc") or o.get("name") or "")
            if desc_prefix and not desc.startswith(desc_prefix):
                continue
            if desc_is and desc != desc_is:
                continue
            if o.get("isActive") not in (1, None, "1"):
                continue
            try:
                odds = float(o.get("odds") or 0)
            except Exception:
                continue
            if odds <= 1:
                continue
            return m, o, odds
    return None


def x12_of(markets):
    h = d = a = None
    got = find_outcome(markets, "1", "", oid="1")
    if got:
        h = got[2]
    got = find_outcome(markets, "1", "", oid="2")
    if got:
        d = got[2]
    got = find_outcome(markets, "1", "", oid="3")
    if got:
        a = got[2]
    if h and d and a:
        return f"{h:.2f}/{d:.2f}/{a:.2f}", h, d, a
    return None, h, d, a


def league_of(data) -> str:
    try:
        cat = data["sport"]["category"]
        parts = [x for x in (cat.get("name"), (cat.get("tournament") or {}).get("name")) if x]
        if parts:
            return " - ".join(parts)
    except Exception:
        pass
    return data.get("tournamentName") or ""


def kickoff(data):
    ts = data.get("estimateStartTime") or 0
    if not ts:
        return None
    return dt.datetime.fromtimestamp(ts / 1000, dt.timezone.utc)


def skip_fixture(home, away, league) -> bool:
    blob = f"{home} {away} {league}"
    if SKIP.search(blob):
        return True
    if TEAMX.search((home or "").strip()) or TEAMX.search((away or "").strip()):
        return True
    return False


def not_started(data, now=None) -> bool:
    st = str(data.get("matchStatus") or "Not start")
    if st not in ("Not start", "", "0"):
        return False
    ko = kickoff(data)
    if ko is None:
        return False
    now = now or dt.datetime.now(dt.timezone.utc)
    return ko > now


def in_window(data, days=WINDOW_DAYS, now=None) -> bool:
    ko = kickoff(data)
    if ko is None or not not_started(data, now):
        return False
    now = now or dt.datetime.now(dt.timezone.utc)
    return ko <= now + dt.timedelta(days=days)


def fetch_event(eid):
    return (curl_json(EVENT.format(eid=eid), timeout=25) or {}).get("data") or {}


def upcoming_ids(days=WINDOW_DAYS, max_pages=16):
    """Not-started football event ids kicking off within `days` (default 4)."""
    now = dt.datetime.now(dt.timezone.utc)
    end = now + dt.timedelta(days=days)
    ids = []
    for page in range(1, max_pages + 1):
        d = (curl_json(UPCOMING.format(page=page), timeout=40) or {}).get("data") or {}
        n = 0
        for t in d.get("tournaments") or []:
            for e in t.get("events") or []:
                n += 1
                ts = e.get("estimateStartTime") or 0
                ko = dt.datetime.fromtimestamp(ts / 1000, dt.timezone.utc) if ts else now
                st = str(e.get("matchStatus") or "Not start")
                if st not in ("Not start", "", "0"):
                    continue
                if now < ko <= end:
                    ids.append(e.get("eventId"))
        total = int(d.get("totalNum") or 0)
        if not n or page * 100 >= total:
            break
    return ids
