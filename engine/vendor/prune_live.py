#!/usr/bin/env python3
"""Keep only pending/upcoming tips on live pick sections (Africa/Accra = UTC+0).

Drops from home-picks.json, picks.json, hot-picks.json, high_odds.json (active slips),
engine/data/ho-masters (live publish), and Code-of-the-Day / dayMasters any slip that is:
  - marked earlier (superseded rebook), or
  - dated before today, or
  - whose legs have all kicked off, or
  - whose legs have all settled (won/lost/void/push).

Partially settled slips stay on live lists until every leg is settled (cards still show
per-leg results). Fully settled slips move to history only.

Settled history stays in high_odds.history, picks-history.json, record.json,
staked-codes.json, engine/data/code-ledger.json and /s/ share pages (proof + hit-rates).
Fully settled slips pruned from Home/Hot/Bankers are archived into the ledger first.
Empty sections are cleared.
"""
from __future__ import annotations
import json, os, sys, datetime as dt
from pathlib import Path

def _repo_root() -> Path:
    env = __import__('os').environ.get('REPO_DIR')
    if env:
        return Path(env)
    # Only treat argv[1] as the repo when this file is run as a script (not under pytest).
    if __name__ == '__main__' and len(sys.argv) > 1:
        p = Path(sys.argv[1])
        if p.is_dir():
            return p
    return Path(__file__).resolve().parents[2]

REPO = _repo_root()
# Accra is UTC+0 year-round
NOW = dt.datetime.now(dt.timezone.utc)
TODAY = NOW.date().isoformat()
SETTLED = frozenset({"won", "lost", "void", "push", "settled"})


def ko_dt(leg: dict):
    if not isinstance(leg, dict):
        return None
    for k in ("kickoff", "start", "koIso", "startTime"):
        v = leg.get(k)
        if not v:
            continue
        try:
            s = str(v).replace("Z", "+00:00")
            if "T" in s:
                t = dt.datetime.fromisoformat(s)
                return t if t.tzinfo else t.replace(tzinfo=dt.timezone.utc)
        except Exception:
            pass
    d, ko = leg.get("date"), leg.get("ko")
    if d and ko:
        try:
            ko = str(ko).strip()
            if "T" in ko:
                t = dt.datetime.fromisoformat(ko.replace("Z", "+00:00"))
                return t if t.tzinfo else t.replace(tzinfo=dt.timezone.utc)
            return dt.datetime.fromisoformat(f"{d}T{str(ko)[:5]}:00+00:00")
        except Exception:
            return None
    return None


def leg_settled(leg: dict) -> bool:
    return (leg.get("result") or "pending").lower() in SETTLED


def slip_date(slip: dict) -> str:
    d = slip.get("date")
    if d:
        return str(d)[:10]
    dates = slip.get("dates") or []
    if dates:
        return min(str(x)[:10] for x in dates if x)
    legs = slip.get("legs") or []
    ld = [str(l.get("date"))[:10] for l in legs if isinstance(l, dict) and l.get("date")]
    return min(ld) if ld else ""


def normalize_legs(slip: dict):
    raw = slip.get("legs")
    if isinstance(raw, list):
        return [l for l in raw if isinstance(l, dict)]
    return []


def double_chance(leg: dict) -> bool:
    """True only for banned DC: 12 always, or 1X/X2 priced above 1.35.
    Allowed 1X/X2 at 1.35 or below must NOT prune the slip.
    """
    try:
        import sys
        from pathlib import Path as _P
        feed = _P(__file__).resolve().parent
        for root in (feed, feed.parent / "predict2u-feed"):
            if str(root) not in sys.path:
                sys.path.insert(0, str(root))
        import matchup_rules as mr
        if hasattr(mr, "is_dc_vetoed"):
            p = dict(leg)
            if "selection" not in p and leg.get("outcomeDesc"):
                p["selection"] = leg.get("outcomeDesc")
            if "market" not in p and (leg.get("marketDesc") or leg.get("marketDescription")):
                p["market"] = leg.get("marketDesc") or leg.get("marketDescription")
            return bool(mr.is_dc_vetoed(p))
    except Exception:
        pass
    import re as _re
    mid = str(leg.get("marketId") or leg.get("mid") or "")
    sel = str(leg.get("selection") or leg.get("outcomeDesc") or "")
    mk = str(leg.get("market") or leg.get("marketDesc") or leg.get("marketDescription") or "")
    is_dc = mid in ("10", "60110") or bool(_re.search(r"double\s*chance", mk, _re.I)) or bool(
        _re.search(r"home\s+or\s+(?:draw|away)|draw\s+or\s+away|\b(?:1X|X2|12)\b", sel, _re.I)
    )
    if not is_dc:
        return False
    if _re.search(r"home\s+or\s+away|\b12\b", sel, _re.I) or str(leg.get("outcomeId") or "") in ("10", "13"):
        return True
    try:
        return float(leg.get("odds") or 0) > 1.35
    except Exception:
        return True


def slip_exempt(slip: dict) -> bool:
    """Pinned one-code exceptions stay until kickoffs pass (then settle/prune normally)."""
    if slip.get("gateExempt") or slip.get("exempt"):
        return True
    codes = []
    c = slip.get("code")
    if c:
        codes.append(str(c).upper())
    sb = (slip.get("codes") or {}).get("sportybet")
    if isinstance(sb, list):
        for x in sb:
            codes.append(str((x.get("code") if isinstance(x, dict) else x) or "").upper())
    elif sb:
        codes.append(str(sb).upper())
    try:
        import json
        from pathlib import Path as _P
        for path in (
            _P("/workspace/predict2u-feed/gate_exempt.json"),
            _P(__file__).resolve().parent / "gate_exempt.json",
            _P(__file__).resolve().parent.parent / "gate_exempt.json",
            _P(__file__).resolve().parent.parent / "engine" / "gate_exempt.json",
        ):
            if path.exists():
                doc = json.loads(path.read_text())
                pinned = {str(x).upper() for x in (doc.get("codes") or [])}
                if any(c in pinned for c in codes if c):
                    return True
                break
    except Exception:
        pass
    return False


def live_slip(slip: dict) -> bool:
    """True if the slip should stay on free code lists; banned DC is a hard veto."""
    if slip_exempt(slip):
        legs = normalize_legs(slip)
        if legs and all(leg_settled(l) for l in legs):
            return False
        kos = [ko_dt(l) for l in legs]
        known = [t for t in kos if t is not None]
        if known and all(t <= NOW for t in known) and len(known) == len(legs):
            return False
        return True
    if any(double_chance(l) for l in normalize_legs(slip)):
        return False
    if slip.get("earlier"):
        return False
    name = str(slip.get("name") or "")
    if name.lower().startswith("earlier code"):
        return False
    sd = slip_date(slip)
    if sd and sd < TODAY:
        return False
    legs = normalize_legs(slip)
    # Hot-style slips may only carry event ids; fall back to events + picks lookup later
    if not legs:
        # Keep if undated/empty legs only when slip itself is today's booking
        return (sd >= TODAY) if sd else True
    if str(slip.get("status") or "").lower() in SETTLED:
        return False
    if all(leg_settled(l) for l in legs):
        return False
    kos = [ko_dt(l) for l in legs]
    known = [t for t in kos if t is not None]
    if known and all(t <= NOW for t in known) and len(known) == len(legs):
        return False
    return True


def live_pick(p: dict) -> bool:
    if not isinstance(p, dict) or double_chance(p):
        return False
    if leg_settled(p):
        return False
    t = ko_dt(p)
    if t is not None and t <= NOW:
        return False
    d = str(p.get("date") or "")[:10]
    if d and d < TODAY:
        return False
    return True


def hot_slip_live(slip: dict, picks_by_eid: dict) -> bool:
    if slip.get("earlier"):
        return False
    if slip_exempt(slip):
        return live_slip(slip) if normalize_legs(slip) else True
    events = slip.get("events") or []
    legs = normalize_legs(slip)
    if legs:
        return live_slip(slip)
    # Hot slips carry event ids; their resolved picks must also be DC-free.
    if any(double_chance(picks_by_eid.get(eid) or {}) for eid in events):
        return False
    starts = []
    for eid in events:
        p = picks_by_eid.get(eid) or {}
        t = ko_dt(p) if p else None
        if t is None and p.get("start"):
            try:
                t = dt.datetime.fromisoformat(str(p["start"]).replace("Z", "+00:00"))
            except Exception:
                t = None
        if t is not None:
            starts.append(t)
    if starts and all(t <= NOW for t in starts):
        return False
    # bookedAt day must not be before today
    booked = str(slip.get("bookedAt") or "")[:10]
    if booked and booked < TODAY:
        return False
    return True



def archive_settled(slip: dict, section: str) -> None:
    """Persist a fully settled slip so Records/build_record can find it after prune.
    Never deletes history — only appends/merges into engine/data/code-ledger.json.
    """
    research = REPO / "engine" / "data"
    try:
        research.mkdir(parents=True, exist_ok=True)
    except OSError:
        return
    path = research / "code-ledger.json"
    try:
        acc = json.loads(path.read_text()) if path.exists() else {}
        if not isinstance(acc, dict):
            acc = {}
    except Exception:
        acc = {}
    codes = slip.get("codes") if isinstance(slip.get("codes"), dict) else None
    entries = []
    if codes:
        for book, code in codes.items():
            if isinstance(code, list):
                code = (code[0].get("code") if code and isinstance(code[0], dict) else code[0]) if code else None
            if not code:
                continue
            entries.append((book, code))
    else:
        code = slip.get("code")
        book = slip.get("book") or slip.get("bookmaker") or "sportybet"
        if code:
            entries.append((book, code))
    if not entries:
        return
    legs = normalize_legs(slip)
    results = [(l.get("result") or "pending").lower() for l in legs]
    status = str(slip.get("status") or "").lower()
    if status not in SETTLED:
        status = "lost" if "lost" in results else "won" if results and all(x in ("won", "void", "push") for x in results) else "settled"
    if status == "settled":
        status = "lost" if "lost" in results else "won"
    for book, code in entries:
        key = f"{str(book).lower()}:{str(code).upper()}"
        prev = acc.get(key) if isinstance(acc.get(key), dict) else {}
        ent = {
            "code": str(code).upper(),
            "book": str(book).lower(),
            "date": slip_date(slip) or TODAY,
            "name": slip.get("name") or slip.get("label") or slip.get("title") or section,
            "kind": slip.get("kind") or section,
            "odds": slip.get("odds") or slip.get("totalOdds"),
            "legs": legs,
            "hit": slip.get("hit"),
            "total": slip.get("total") or len(legs),
            "status": status if status in ("won", "lost") else prev.get("status") or status,
            "settled": slip.get("settledAt") or NOW.isoformat(timespec="seconds").replace("+00:00", "Z"),
            "section": section,
        }
        # never downgrade a settled status
        if prev.get("status") in ("won", "lost") and ent["status"] not in ("won", "lost"):
            ent["status"] = prev["status"]
        acc[key] = ent
    path.write_text(json.dumps(acc, ensure_ascii=False, separators=(",", ":")))



def prune_home(doc: dict) -> tuple[dict, list]:
    removed = []
    slips_in = doc.get("slips") or []
    keep = []
    for s in slips_in:
        if live_slip(s):
            keep.append(s)
        else:
            if normalize_legs(s) and all(leg_settled(l) for l in normalize_legs(s)):
                archive_settled(s, "home")
            removed.append(("home", (s.get("codes") or {}).get("sportybet") or s.get("name"), slip_date(s), "earlier" if s.get("earlier") else "stale"))
    doc["slips"] = keep
    picks_in = doc.get("picks") or []
    doc["picks"] = [p for p in picks_in if live_pick(p)]
    # homeCode: drop only if every match has started (best-effort via picks)
    hc = doc.get("homeCode")
    if isinstance(hc, dict):
        # keep homeCode while any published pick is still upcoming
        if not doc["picks"] and hc.get("codes"):
            # no upcoming individual picks left — clear the all-picks code from free list
            removed.append(("homeCode", "all-picks", TODAY, "no-upcoming-picks"))
            doc["homeCode"] = {}
    return doc, removed


def prune_picks(doc: dict) -> tuple[dict, list]:
    removed = []
    keep = []
    for s in doc.get("slips") or []:
        if live_slip(s):
            keep.append(s)
        else:
            if normalize_legs(s) and all(leg_settled(l) for l in normalize_legs(s)):
                archive_settled(s, "bankers")
            removed.append(("picks", s.get("code") or (s.get("codes") or {}).get("sportybet"), slip_date(s), "stale"))
    # relabel Slip N per day
    n = {}
    for s in keep:
        d = slip_date(s) or TODAY
        n[d] = n.get(d, 0) + 1
        s["label"] = f"Slip {n[d]}"
    doc["slips"] = keep
    return doc, removed


def prune_hot(doc: dict) -> tuple[dict, list]:
    removed = []
    picks = [p for p in (doc.get("picks") or []) if live_pick(p)]
    by_eid = {p.get("eventId"): p for p in picks if p.get("eventId")}
    # also index original for start times of filtered
    for p in doc.get("picks") or []:
        if p.get("eventId") and p["eventId"] not in by_eid:
            by_eid[p["eventId"]] = p
    keep_slips = []
    for s in doc.get("slips") or []:
        if hot_slip_live(s, by_eid):
            keep_slips.append(s)
        else:
            if normalize_legs(s) and all(leg_settled(l) for l in normalize_legs(s)):
                archive_settled(s, "hot")
            codes = s.get("codes") or {}
            sb = codes.get("sportybet")
            if isinstance(sb, list):
                code = (sb[0].get("code") if sb and isinstance(sb[0], dict) else sb[0]) if sb else None
            else:
                code = sb
            removed.append(("hot", code or s.get("name"), str(s.get("bookedAt") or "")[:10], "stale"))
    doc["picks"] = picks
    doc["slips"] = keep_slips
    # byMarket / byTeam / sectionMasters: drop entries whose picks all started
    for key in ("byMarket", "byTeam", "sectionMasters"):
        arr = doc.get(key)
        if not isinstance(arr, list):
            continue
        kept = []
        for m in arr:
            mp = [p for p in (m.get("picks") or []) if live_pick(p)]
            if not mp and (m.get("picks") or []):
                removed.append(("hot-" + key, m.get("market") or m.get("team") or m.get("section") or m.get("label") or m.get("name"), TODAY, "stale"))
                continue
            m = dict(m)
            if mp:
                m["picks"] = mp
            # still keep market booking codes if the market slip itself is live
            if hot_slip_live(m, by_eid) or mp:
                kept.append(m)
        doc[key] = kept
    return doc, removed



def prune_high_odds(doc: dict) -> tuple[dict, list]:
    """Move fully settled slips from active list into history; keep partials pending."""
    removed = []
    active, history = [], list(doc.get("history") or [])
    seen = {str(h.get("code") or "").upper() for h in history}
    for s in doc.get("slips") or []:
        legs = normalize_legs(s)
        status = str(s.get("status") or "").lower()
        fully = status in SETTLED or (legs and all(leg_settled(l) for l in legs))
        if fully:
            s = dict(s)
            if status not in ("won", "lost"):
                results = [(l.get("result") or "pending").lower() for l in legs]
                s["status"] = "lost" if "lost" in results else "won" if results and all(x in ("won", "void", "push") for x in results) else status or "settled"
            if not s.get("settledAt"):
                s["settledAt"] = NOW.isoformat(timespec="seconds").replace("+00:00", "Z")
            code = str(s.get("code") or "").upper()
            if code and code not in seen:
                history.insert(0, s); seen.add(code)
            archive_settled(s, "high-odds")
            removed.append(("high", s.get("code"), slip_date(s), s.get("status")))
        else:
            active.append(s)
    history.sort(key=lambda s: (s.get("settledAt") or s.get("date") or ""), reverse=True)
    won = sum(s.get("status") == "won" for s in history)
    lost = sum(s.get("status") == "lost" for s in history)
    doc["slips"] = active
    doc["history"] = history[:120]
    doc["record"] = dict(won=won, lost=lost, settled=won + lost, pending=len(active),
                         winRate=round(100 * won / (won + lost), 1) if won + lost else None)
    return doc, removed


def prune_ho_masters(dir_path: Path) -> list:
    """Mark settled masters; daily_master already skips republishing won/lost as active."""
    removed = []
    if not dir_path.exists():
        return removed
    for path in sorted(dir_path.glob("*.json")):
        try: doc = json.loads(path.read_text())
        except Exception: continue
        legs = doc.get("legList") or []
        if not legs: continue
        if str(doc.get("status") or "").lower() in ("won", "lost"): continue
        if all(leg_settled(l) for l in legs if isinstance(l, dict)):
            results = [(l.get("result") or "pending").lower() for l in legs]
            doc["status"] = "lost" if "lost" in results else "won"
            doc["settledAt"] = NOW.isoformat(timespec="seconds").replace("+00:00", "Z")
            path.write_text(json.dumps(doc, indent=1, ensure_ascii=False))
            removed.append(("ho-master", path.name, doc.get("date"), doc["status"]))
    return removed


def prune_daily_master(dir_path: Path) -> list:
    removed = []
    if not dir_path.exists():
        return removed
    for path in sorted(dir_path.glob("????-??-??.json")):
        try: doc = json.loads(path.read_text())
        except Exception: continue
        legs = doc.get("legList") or []
        if legs and all(leg_settled(l) for l in legs if isinstance(l, dict)):
            results = [(l.get("result") or "pending").lower() for l in legs]
            doc["status"] = "lost" if "lost" in results else "won"
            doc["settledAt"] = NOW.isoformat(timespec="seconds").replace("+00:00", "Z")
            path.write_text(json.dumps(doc, indent=1, ensure_ascii=False))
            removed.append(("daily-master", path.name, doc.get("date"), doc["status"]))
    return removed


def write_if_changed(path: Path, doc: dict) -> bool:
    body = json.dumps(doc, ensure_ascii=False, separators=(",", ":"))
    old = path.read_text() if path.exists() else None
    if old == body:
        return False
    path.write_text(body)
    return True


def main():
    removed_all = []
    changed = False

    hp = REPO / "home-picks.json"
    if hp.exists():
        doc = json.loads(hp.read_text())
        doc, rem = prune_home(doc)
        removed_all.extend(rem)
        if write_if_changed(hp, doc):
            changed = True
            print("home-picks pruned", len(doc.get("slips") or []), "slips", len(doc.get("picks") or []), "picks")
        else:
            print("home-picks unchanged")

    pj = REPO / "picks.json"
    if pj.exists():
        doc = json.loads(pj.read_text())
        doc, rem = prune_picks(doc)
        removed_all.extend(rem)
        # refresh DATA_UPDATED when slips change
        if rem:
            doc["DATA_UPDATED"] = NOW.strftime("%Y-%m-%dT%H:%M:%SZ")
            # shrink window to live range
            dates = sorted({slip_date(s) for s in doc.get("slips") or [] if slip_date(s)})
            if dates:
                doc["window"] = [dates[0], dates[-1]]
        if write_if_changed(pj, doc):
            changed = True
            print("picks.json pruned", len(doc.get("slips") or []), "slips")
        else:
            print("picks.json unchanged")

    ht = REPO / "hot-picks.json"
    if ht.exists():
        doc = json.loads(ht.read_text())
        doc, rem = prune_hot(doc)
        removed_all.extend(rem)
        if rem:
            doc["updatedAt"] = NOW.isoformat(timespec="seconds")
        if write_if_changed(ht, doc):
            changed = True
            print("hot-picks pruned", len(doc.get("slips") or []), "slips", len(doc.get("picks") or []), "picks")
        else:
            print("hot-picks unchanged")

    # High Odds: move fully settled slips to history (partials stay active for leg-by-leg view).
    ho = REPO / "high_odds.json"
    if ho.exists():
        doc = json.loads(ho.read_text())
        doc, rem = prune_high_odds(doc)
        removed_all.extend(rem)
        if rem:
            doc["updatedAt"] = NOW.isoformat(timespec="seconds").replace("+00:00", "Z")
        if write_if_changed(ho, doc):
            changed = True
            print("high_odds pruned", len(doc.get("slips") or []), "active", len(doc.get("history") or []), "history")
        else:
            print("high_odds unchanged")

    rem = prune_ho_masters(REPO / "engine" / "data" / "ho-masters")
    removed_all.extend(rem)
    rem = prune_daily_master(REPO / "engine" / "data" / "daily-master")
    removed_all.extend(rem)
    if rem:
        print("masters marked settled", len(rem))

    # homeCode.dayMasters: drop days whose booked legs are all settled/started
    hp = REPO / "home-picks.json"
    if hp.exists():
        doc = json.loads(hp.read_text())
        hc = doc.get("homeCode") or {}
        dm = hc.get("dayMasters") if isinstance(hc, dict) else None
        if isinstance(dm, dict) and dm:
            keep = {}
            for day, m in dm.items():
                picks = m.get("picks") or []
                if picks and all(leg_settled(p) if isinstance(p, dict) else False for p in picks):
                    removed_all.append(("dayMaster", day, day, "settled")); continue
                keep[day] = m
            if len(keep) != len(dm):
                hc = dict(hc); hc["dayMasters"] = keep; doc["homeCode"] = hc
                if write_if_changed(hp, doc):
                    changed = True
                    print("dayMasters pruned", list(keep))

    for kind, code, day, why in removed_all:
        print(f"  drop {kind} {code} day={day} ({why})")
    print("removed", len(removed_all), "changed" if changed else "no-file-change")
    return 0 if changed or True else 0


if __name__ == "__main__":
    sys.exit(main())
