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
    changes, ok = G.repair_repo(REPO, extra_sources=[t] if t else [], history=False)
    msgs += changes
    if not ok:
        msgs.append("WARNING favourites section still empty")
    st = subprocess.run(["git", "-C", str(REPO), "status", "--porcelain", "--", FILE, G.SNAPSHOT], capture_output=True, text=True).stdout.strip()
    if st:
        subprocess.run(["git", "-C", str(REPO), "add", "--", FILE, G.SNAPSHOT], check=True)
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
