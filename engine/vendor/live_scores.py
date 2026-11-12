#!/usr/bin/env python3
"""live-scores.json: score/status snapshot for today's home picks (home live-score fallback).

Moved out of the old box-sync.sh heredoc so GitHub Actions can run it unattended.
Reads the SportyBet event cache written by news_hub.py (NEWS_STATE_DIR on Actions,
/workspace/predict2u-feed on the box) and home-picks.json; writes compact JSON.
  python3 engine/vendor/live_scores.py <repo>
"""
import datetime as dt, json, os, sys

REPO = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("REPO_DIR") or "/workspace/Predict2u"
STATE = os.environ.get("NEWS_STATE_DIR") or "/workspace/predict2u-feed"
ev = {}
try:
    ev = json.load(open(os.path.join(STATE, "event-cache.json")))
except Exception:
    pass
try:
    h = json.load(open(os.path.join(REPO, "home-picks.json")))
except Exception:
    h = {"picks": []}
out = {}
for p in h.get("picks") or []:
    eid = p.get("eventId")
    if not eid:
        continue
    e = ev.get(eid) or {}
    out[eid] = {"eventId": eid, "status": e.get("status") or p.get("matchStatus") or ("Ended" if p.get("result") in ("won", "lost") else "Not start"),
                "score": e.get("score") or p.get("score"), "played": e.get("played"), "home": e.get("home"), "away": e.get("away")}
path = os.path.join(REPO, "live-scores.json")
try:
    old = json.load(open(path))
except Exception:
    old = None
if old is None or old.get("events") != out or old.get("date") != h.get("date"):
    json.dump({"DATA_UPDATED": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "date": h.get("date"), "events": out},
              open(path, "w"), separators=(",", ":"))
print("live-scores", len(out))
