"""Settle every pending pick/code on published Predict2u JSON files (won / lost / void)."""
from __future__ import annotations
import concurrent.futures as cf
import json
import re
import subprocess
from pathlib import Path

from .paths import REPO_DIR, RESEARCH_DIR, SBJSON

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36"
PUBLIC_FILES = ("home-picks.json", "picks.json", "hot-picks.json", "high_odds.json", "staked-codes.json")


def _get(url):
    try:
        out = subprocess.run(["curl", "-s", "-m", "20", "-A", UA, url], capture_output=True, text=True).stdout
        return json.loads(out) if out else {}
    except Exception:
        return {}


def fetch_event(eid: str) -> dict | None:
    d = _get(f"https://www.sportybet.com/api/gh/factsCenter/event?eventId={eid}&productId=3").get("data") or {}
    if not d:
        return None
    ended = d.get("matchStatus") == "Ended" and bool(d.get("setScore"))
    voided = d.get("matchStatus") in ("Cancelled", "Postponed", "Abandoned")
    return {
        "final": ended,
        "void": voided,
        "score": d.get("setScore"),
        "status": d.get("matchStatus"),
        "home": d.get("homeTeamName"),
        "away": d.get("awayTeamName"),
    }


def grade(selection: str, match: str, ev: dict) -> str:
    if ev.get("void"):
        return "void"
    if not ev.get("final") or not ev.get("score"):
        return "pending"
    try:
        h, a = map(int, str(ev["score"]).replace("-", ":").split(":")[:2])
    except Exception:
        return "pending"
    s = (selection or "").strip()
    tot = h + a
    m = re.match(r"(Over|Under)\s+(\d+(?:\.\d+)?)$", s, re.I)
    if m:
        return "won" if (tot > float(m.group(2))) == (m.group(1).lower() == "over") else "lost"
    teams = re.split(r"\s+v(?:s)?\s+", match or "", maxsplit=1)
    H, A = (teams + [""])[:2]
    # Team totals: "Sevilla over 0.5 goals" / "home over 0.5 goals" / "away under 1.5 goals"
    tm = re.match(r"^(.+?)\s+(over|under)\s+(\d+(?:\.\d+)?)\s*goals?$", s, re.I)
    if tm:
        team, side, line = tm.group(1).strip(), tm.group(2).lower(), float(tm.group(3))
        tl = team.lower()
        if tl in ("home", "1") or team == H.strip():
            goals = h
        elif tl in ("away", "2") or team == A.strip():
            goals = a
        elif H.strip() and (tl == H.strip().lower() or H.strip().lower() in tl or tl in H.strip().lower()):
            goals = h
        elif A.strip() and (tl == A.strip().lower() or A.strip().lower() in tl or tl in A.strip().lower()):
            goals = a
        else:
            return "pending"
        return "won" if (goals > line) == (side == "over") else "lost"
    out = {"1": h > a, "X": h == a, "2": a > h}

    def tok(x):
        x = x.strip()
        if x == H.strip():
            return "1"
        if x == A.strip():
            return "2"
        if x.lower() == "draw":
            return "X"
        return None

    parts = [tok(x) for x in re.split(r"\s+or\s+", s)]
    if parts and all(parts):
        return "won" if any(out[p] for p in parts) else "lost"
    sl = s.lower()
    if sl in ("gg", "yes", "both teams to score", "btts yes", "gg (btts yes)"):
        return "won" if h and a else "lost"
    if sl in ("ng", "no", "btts no"):
        return "won" if not (h and a) else "lost"
    if sl == "home":
        return "won" if h > a else "lost"
    if sl == "away":
        return "won" if a > h else "lost"
    return "pending"


def _walk(obj, acc):
    if isinstance(obj, list):
        for x in obj:
            _walk(x, acc)
    elif isinstance(obj, dict):
        if (obj.get("eventId") or obj.get("eid")) and obj.get("selection"):
            acc.append(obj)
        for x in obj.values():
            _walk(x, acc)


def settle_mapping(picks: list[dict], events: dict) -> int:
    n = 0
    for p in picks:
        cur = (p.get("result") or "pending").lower()
        if cur in ("won", "lost", "void"):
            continue
        ev = events.get(p.get("eventId") or p.get("eid")) or {}
        nxt = grade(p.get("selection") or "", p.get("match") or "", ev)
        if ev.get("score"):
            p["score"] = ev["score"]
        if ev.get("status"):
            p["matchStatus"] = ev["status"]
        if nxt != cur:
            p["result"] = nxt
            n += 1
    return n


def settle_files(repo: Path | None = None) -> dict:
    repo = Path(repo or REPO_DIR)
    files = [repo / name for name in PUBLIC_FILES]
    research = list(Path(RESEARCH_DIR).glob("????-??-??.json"))
    blobs = []
    for path in files + research:
        if not path.exists():
            continue
        try:
            blobs.append((path, json.loads(path.read_text())))
        except Exception:
            continue
    picks = []
    for _, data in blobs:
        _walk(data, picks)
    eids = sorted({p.get("eventId") or p.get("eid") for p in picks if (p.get("result") or "pending").lower() not in ("won", "lost", "void")})
    events = {}
    with cf.ThreadPoolExecutor(8) as pool:
        for eid, ev in zip(eids, pool.map(fetch_event, eids)):
            if ev:
                events[eid] = ev
    changed = 0
    for path, data in blobs:
        rows = []
        _walk(data, rows)
        n = settle_mapping(rows, events)
        if n:
            path.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")))
            changed += n
        print(f"settle {path.name}: {n} updates")
    return {"pending_looked_up": len(eids), "updated": changed, "events": len(events)}


if __name__ == "__main__":
    print(json.dumps(settle_files()))
