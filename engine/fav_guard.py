#!/usr/bin/env python3
"""Guard for the Home "How favourites perform by league" section.

That section lives in two keys of home-picks.json:
  - leagues                (league favourite stats + fixtures + league picks)
  - homeCode.dayMasters    (favourites day-master codes, Today / Tomorrow tabs)

Many jobs rewrite home-picks.json (daily, shield, strategies, settle, morning,
self-heal ...). Any of them could wipe those two keys, either by rebuilding the
file from a research "shell" with empty leagues or by a push rebase that keeps
its own stale copy. This module makes that impossible to stick:

  * fav-leagues.json (site root) is a snapshot owned by this guard and the
    06:00 favourites job. It is only ever written with non-empty leagues.
  * repair() puts leagues / live dayMasters back from that snapshot (or the
    git history) when home-picks.json has lost them. It never books codes.
  * merge_home() is a key-level 3-way merge used by .github/scripts/p2u_push.sh
    so a job that started from an older checkout can no longer overwrite what
    another job published meanwhile.

CLI:
  python -m engine.fav_guard check  [repo]   exit 1 when the section is empty
  python -m engine.fav_guard repair [repo]   restore it (no booking), refresh snapshot
  python -m engine.fav_guard snapshot [repo] refresh fav-leagues.json from home-picks.json
"""
from __future__ import annotations

import datetime as dt
import json
import subprocess
import sys
from pathlib import Path

SNAPSHOT = "fav-leagues.json"
HOME = "home-picks.json"


def _now():
    return dt.datetime.now(dt.timezone.utc)


def _load(p):
    try:
        return json.loads(Path(p).read_text())
    except Exception:
        return None


def _dump(doc):
    return json.dumps(doc, separators=(",", ":"), ensure_ascii=False)


def _ko(p):
    try:
        return dt.datetime.fromisoformat(f"{p['date']}T{p.get('ko') or '23:59'}").replace(tzinfo=dt.timezone.utc)
    except Exception:
        return None


def _day_live(day, m, now):
    """A day-master is worth showing when it is today/future and not every leg has kicked off."""
    if not isinstance(m, dict) or day < now.date().isoformat():
        return False
    kos = [_ko(p) for p in m.get("picks") or []]
    if m.get("codes") and kos and all(k is not None and k <= now for k in kos):
        return False
    return True


def day_masters(doc):
    return ((doc or {}).get("homeCode") or {}).get("dayMasters") or {}


def has_leagues(doc):
    L = (doc or {}).get("leagues")
    return isinstance(L, list) and any((x or {}).get("league") for x in L)


def problems(doc, now=None):
    now = now or _now()
    out = []
    if not has_leagues(doc):
        out.append("home-picks.json has no favourites league stats (leagues is empty)")
    return out


def warnings(doc, now=None):
    now = now or _now()
    live = {d: m for d, m in day_masters(doc).items() if _day_live(d, m, now) and m.get("codes")}
    return [] if live else ["no live favourites booking codes (homeCode.dayMasters has nothing for today/tomorrow)"]


# ------------------------------------------------------------------ snapshot
def snapshot_from(doc, now=None):
    now = now or _now()
    return {
        "updatedAt": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "date": (doc or {}).get("date"),
        "leagues": doc.get("leagues") or [],
        "dayMasters": {d: m for d, m in day_masters(doc).items() if _day_live(d, m, now)},
    }


def write_snapshot(repo, doc, now=None):
    """Refresh fav-leagues.json; never overwrite a good snapshot with empty leagues."""
    if not has_leagues(doc):
        return False
    p = Path(repo) / SNAPSHOT
    old = _load(p) or {}
    snap = snapshot_from(doc, now)
    # keep live day-masters the old snapshot had and this doc lost
    for d, m in (old.get("dayMasters") or {}).items():
        if d not in snap["dayMasters"] and _day_live(d, m, now or _now()):
            snap["dayMasters"][d] = m
    if {k: v for k, v in old.items() if k != "updatedAt"} == {k: v for k, v in snap.items() if k != "updatedAt"}:
        return False
    p.write_text(_dump(snap))
    return True


def git_history(repo, n=40):
    """Older published home-picks.json versions, newest first (empty on a shallow checkout)."""
    try:
        sh = subprocess.run(["git", "-C", str(repo), "rev-parse", "--is-shallow-repository"], capture_output=True, text=True, timeout=10).stdout.strip()
        if sh == "true":  # Actions checkouts are depth 1: pull in enough history to find a good copy
            subprocess.run(["git", "-C", str(repo), "fetch", "-q", "--deepen=150", "origin"], capture_output=True, timeout=120)
    except Exception:
        pass
    try:
        revs = subprocess.run(["git", "-C", str(repo), "log", f"-n{n}", "--format=%H", "--", HOME],
                              capture_output=True, text=True, timeout=30).stdout.split()
    except Exception:
        return
    for r in revs:
        try:
            raw = subprocess.run(["git", "-C", str(repo), "show", f"{r}:{HOME}"], capture_output=True, text=True, timeout=30).stdout
            yield json.loads(raw)
        except Exception:
            continue


# ------------------------------------------------------------------ repair
def repair(doc, sources, now=None):
    """Fill leagues / live dayMasters that `doc` lost from the first source that has them. No booking."""
    now = now or _now()
    changes = []
    sources = [s for s in sources if isinstance(s, dict)]
    def src_leagues(s):
        return s.get("leagues") if has_leagues(s) else None
    def src_dm(s):
        return s.get("dayMasters") if "dayMasters" in s and "homeCode" not in s else day_masters(s)
    if not has_leagues(doc):
        for s in sources:
            L = src_leagues(s)
            if L:
                doc["leagues"] = L
                changes.append(f"restored {len(L)} favourites leagues")
                break
    hc = doc.get("homeCode")
    if not isinstance(hc, dict):
        hc = {}
    dm = dict(hc.get("dayMasters") or {})
    for s in sources:
        for d, m in (src_dm(s) or {}).items():
            if _day_live(d, m, now) and m.get("codes") and not (dm.get(d) or {}).get("codes"):
                dm[d] = m
                changes.append(f"restored favourites codes for {d}")
    if dm != (hc.get("dayMasters") or {}):
        hc["dayMasters"] = dm
        doc["homeCode"] = hc
    return changes


def repair_repo(repo, extra_sources=(), history=True, now=None):
    repo = Path(repo)
    hp_path = repo / HOME
    doc = _load(hp_path)
    if not isinstance(doc, dict):
        return ["home-picks.json unreadable"], False
    changes = repair(doc, list(extra_sources) + [_load(repo / SNAPSHOT)], now)
    if problems(doc, now) and history:
        changes += repair(doc, git_history(repo), now)
    if changes:
        hp_path.write_text(_dump(doc))
    write_snapshot(repo, doc, now)
    return changes, not problems(doc, now)


# ------------------------------------------------------------------ 3-way merge
def _by_name(lst):
    out = {}
    for i, x in enumerate(lst or []):
        k = (x or {}).get("name") if isinstance(x, dict) else None
        out[k if k is not None else f"#{i}"] = x
    return out


def _merge_list_by_name(b, o, t):
    B, O, T = _by_name(b), _by_name(o), _by_name(t)
    out, seen = [], set()
    for k in list(T) + [k for k in O if k not in T]:
        if k in seen:
            continue
        seen.add(k)
        bv, ov, tv = B.get(k), O.get(k), T.get(k)
        if ov == bv:
            v = tv
        elif tv == bv:
            v = ov
        else:
            v = ov if ov is not None else tv
        if v is not None:
            out.append(v)
    return out


def _bookedat(m):
    return str((m or {}).get("bookedAt") or "")


def _merge_dict(b, o, t, conflict):
    b, o, t = b or {}, o or {}, t or {}
    out = {}
    for k in list(t) + [k for k in o if k not in t]:
        if k in out:
            continue
        bv, ov, tv = b.get(k), o.get(k), t.get(k)
        if ov == bv:
            v = tv
        elif tv == bv:
            v = ov
        else:
            v = conflict(k, bv, ov, tv)
        if v is not None:
            out[k] = v
    return out


def merge_home(base, ours, theirs):
    """Key-level 3-way merge of home-picks.json: keep both jobs' changes instead of one wiping the other."""
    if not isinstance(theirs, dict):
        return ours
    if not isinstance(ours, dict):
        return theirs
    base = base if isinstance(base, dict) else {}

    def dm_conflict(day, bv, ov, tv):
        if not ov:
            return tv
        if not tv:
            return ov
        return ov if _bookedat(ov) >= _bookedat(tv) else tv

    def hc_conflict(k, bv, ov, tv):
        if k == "dayMasters":
            return _merge_dict(bv, ov, tv, dm_conflict)
        return ov if ov is not None else tv

    def top_conflict(k, bv, ov, tv):
        if k == "homeCode":
            return _merge_dict(bv, ov, tv, hc_conflict)
        if k == "slips":
            return _merge_list_by_name(bv, ov, tv)
        if k in ("leagues", "picks"):
            return ov if ov else tv
        if k in ("DATA_UPDATED", "sourceUpdatedAt"):
            return max(str(ov or ""), str(tv or "")) or None
        return ov if ov is not None else tv

    return _merge_dict(base, ours, theirs, top_conflict)


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    cmd = argv[0] if argv else "check"
    repo = Path(argv[1]) if len(argv) > 1 else Path(__file__).resolve().parent.parent
    if cmd == "check":
        doc = _load(repo / HOME) or {}
        p = problems(doc)
        print("favGuard:", "; ".join(p + warnings(doc)) or "ok")
        return 1 if p else 0
    if cmd == "repair":
        changes, ok = repair_repo(repo)
        print("favGuard repair:", "; ".join(changes) if changes else "nothing to restore", "->", "ok" if ok else "STILL EMPTY")
        return 0 if ok else 1
    if cmd == "snapshot":
        print("favGuard snapshot:", "written" if write_snapshot(repo, _load(repo / HOME) or {}) else "unchanged")
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
