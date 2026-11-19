#!/usr/bin/env python3
"""Run by p2u_push.sh after rebasing this job's commit onto the latest main.

  p2u_merge_live.py BASE OURS THEIRS

home-picks.json is one-line JSON, so a git rebase conflict on it used to be
settled with `-X theirs`, i.e. this run's whole stale copy won and wiped what
other jobs had published since it checked out (that is how the favourites
by league section went empty on Nov 12). Here we redo it as a key-level 3-way
merge, then let engine.fav_guard put back the favourites section if it is
still empty. The result is amended into this run's commit.
"""
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from engine import fav_guard as G  # noqa: E402

FILE = G.HOME


def show(rev):
    if not rev:
        return None
    r = subprocess.run(["git", "-C", str(REPO), "show", f"{rev}:{FILE}"], capture_output=True, text=True)
    try:
        return json.loads(r.stdout) if r.returncode == 0 else None
    except Exception:
        return None


HIGH_ODDS = "high_odds.json"


def merge_slips(base, ours, theirs):
    """3-way merge of a list of slips keyed by `code`.

    Slips another job added since this run checked out are kept, slips either side
    removed stay removed, and this run's version wins for slips both sides have.
    Returns None when the list cannot be keyed (falls back to this run's copy).
    """
    def key(row):
        return row.get("code") if isinstance(row, dict) else None
    if not all(isinstance(x, list) for x in (base, ours, theirs)):
        return None
    if any(key(r) is None for r in base + ours + theirs):
        return None
    b, o, t = {key(r) for r in base}, {key(r) for r in ours}, {key(r) for r in theirs}
    added_theirs = [r for r in theirs if key(r) not in b and key(r) not in o]
    base_by, theirs_by = {key(r): r for r in base}, {key(r): r for r in theirs}
    kept_ours = []
    for r in ours:
        k = key(r)
        if k in b and k not in t:
            continue                      # the other job removed it (e.g. prune after settle)
        if k in t and base_by.get(k) == r:
            r = theirs_by[k]              # untouched here, so take the other job's update
        kept_ours.append(r)
    return added_theirs + kept_ours


def merge_high_odds(b, o, t):
    """high_odds.json: slip-level merge so a stale copy cannot wipe another job's codes."""
    merged = dict(o)
    for field in ("slips", "history"):
        m = merge_slips((b or {}).get(field) or [], o.get(field) or [], t.get(field) or [])
        if m is not None:
            merged[field] = m
    return merged


def show_file(rev, path):
    if not rev:
        return None
    r = subprocess.run(["git", "-C", str(REPO), "show", f"{rev}:{path}"], capture_output=True, text=True)
    try:
        return json.loads(r.stdout) if r.returncode == 0 else None
    except Exception:
        return None


def main(argv):
    base, ours, theirs = (argv + ["", "", ""])[:3]
    b, o, t = show(base), show(ours), show(theirs)
    hp = REPO / FILE
    cur = G._load(hp)
    msgs = []
    if base and b is not None and o is not None and t is not None and o != b and t != b and base != theirs:
        merged = G.merge_home(b, o, t)
        if merged != cur:
            hp.write_text(G._dump(merged))
            msgs.append("3-way merged home-picks.json with the newer main")
    hb, ho, ht = show_file(base, HIGH_ODDS), show_file(ours, HIGH_ODDS), show_file(theirs, HIGH_ODDS)
    if base and isinstance(ho, dict) and isinstance(ht, dict) and ho != (hb or {}) and ht != (hb or {}) and base != theirs:
        merged = merge_high_odds(hb if isinstance(hb, dict) else {}, ho, ht)
        hpath = REPO / HIGH_ODDS
        if merged != ho:
            hpath.write_text(json.dumps(merged, ensure_ascii=False, separators=(",", ":")))  # stays one-line JSON
            msgs.append("slip-merged high_odds.json with the newer main")
    changes, ok = G.repair_repo(REPO, extra_sources=[t] if t else [], history=False)
    msgs += changes
    if not ok:
        msgs.append("WARNING favourites section still empty")
    st = subprocess.run(["git", "-C", str(REPO), "status", "--porcelain", "--", FILE, G.SNAPSHOT, HIGH_ODDS], capture_output=True, text=True).stdout.strip()
    if st:
        subprocess.run(["git", "-C", str(REPO), "add", "--", FILE, G.SNAPSHOT, HIGH_ODDS], check=True)
        subprocess.run(["git", "-C", str(REPO), "commit", "--amend", "--no-edit", "--no-verify", "-q"], check=True)
        msgs.append("amended commit")
    print("p2u_merge_live:", "; ".join(msgs) or "nothing to do")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv[1:]))
    except SystemExit:
        raise
    except Exception as e:  # never block a push on the guard itself
        print("p2u_merge_live: skipped:", e)
        raise SystemExit(0)
