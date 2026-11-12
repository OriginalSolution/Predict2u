"""Flag booking codes whose total odds are strictly above 25.

The site paywall (p2u-paywall) sells three slip ids per day — banker, medium
and hot — because that is what the existing relay accepts. Every premium slip
is filed under one of those ids. Price stays GHS 50. This module does not
touch Paystack keys or amounts.

`stamp` only writes the flag. `seal_slip` (used by lock_codes.py when the lock
key is present) copies the real booking code and the pick list into the
private store, then blanks them on the public slip.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

ODDS_LOCK = 25.0  # strictly above — 25.00 stays free
PRICE = 50
CURRENCY = "GHS"
ID_RE = re.compile(r"^(banker|medium|hot)-\d{8}$")
PUBLIC_JSON = ("home-picks.json", "picks.json", "hot-picks.json", "high_odds.json")
# Keys that mean "this dict is a single bookmaker code", not a slip.
_CODE_KEYS = {
    "code", "legs", "odds", "link", "totalOdds", "matches", "of", "parts",
    "sportybet", "msport", "betika", "footballcom", "betpawa", "betway",
    "onexbet", "1xbet",
}
_PICK_FIELDS = ("match", "selection", "market", "odds", "league", "ko", "date", "kickoff")


def is_premium_odds(value) -> bool:
    """True only when total odds are strictly greater than 25."""
    if value is None or isinstance(value, bool):
        return False
    try:
        return float(value) > ODDS_LOCK
    except (TypeError, ValueError):
        return False


def slip_odds(slip):
    if not isinstance(slip, dict):
        return None
    for key in ("totalOdds", "odds"):
        value = slip.get(key)
        if value is None or isinstance(value, bool):
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return None


def leg_count(slip) -> int:
    if not isinstance(slip, dict):
        return 0
    locked = slip.get("locked")
    if isinstance(locked, dict) and isinstance(locked.get("legs"), (int, float)) and not isinstance(locked.get("legs"), bool):
        return int(locked["legs"])
    if isinstance(slip.get("legCount"), (int, float)) and not isinstance(slip.get("legCount"), bool):
        return int(slip["legCount"])
    legs = slip.get("legs")
    if isinstance(legs, bool):
        legs = None
    if isinstance(legs, (int, float)):
        return int(legs)
    if isinstance(legs, list) and legs:
        return len(legs)
    for key in ("total", "picks"):
        value = slip.get(key)
        if isinstance(value, bool):
            continue
        if isinstance(value, (int, float)):
            return int(value)
        if isinstance(value, list) and value and not isinstance(value[0], (int, float)):
            return len(value)
    if isinstance(legs, list):
        return len(legs)
    return 0


def lock_kind(slip) -> str:
    """Map a slip onto a relay-valid product: banker, medium or hot."""
    name = str((slip or {}).get("name") or (slip or {}).get("label") or "").lower()
    risk = str((slip or {}).get("risk") or "").lower()
    origin = str((slip or {}).get("origin") or "").lower()
    strategy = str((slip or {}).get("strategy") or "").lower()
    if (
        (slip or {}).get("banker") is True
        or (slip or {}).get("verzzify")
        or (slip or {}).get("dailyMaster")
        or name.startswith("main banker")
        or name.startswith("main ·")
        or "code of the day" in name
        or "verzzify" in name
        or "verzzify" in strategy
        or origin in ("daily-master", "verzzify")
    ):
        return "banker"
    if risk == "medium" or name.startswith("medium"):
        return "medium"
    return "hot"


def _day_digits(raw) -> str:
    match = re.match(r"(\d{4})-(\d{2})-(\d{2})", str(raw or ""))
    return "".join(match.groups()) if match else ""


def slip_day(slip, day=None) -> str:
    """Match day used in the paywall id.

    Leg dates win over the card date. Home and Bankers copies of the same
    slip sometimes carry different card dates; the games do not.
    """
    forced = _day_digits(day) if day else ""
    if forced and not isinstance(slip, dict):
        return forced
    if isinstance(day, str) and forced and day and not (isinstance(slip, dict) and slip.get("legs")):
        return forced
    leg_days = []
    if isinstance(slip, dict) and isinstance(slip.get("legs"), list):
        for leg in slip["legs"]:
            if isinstance(leg, dict):
                digits = _day_digits(leg.get("date") or leg.get("kickoff"))
                if digits:
                    leg_days.append(digits)
    if leg_days:
        return min(leg_days)
    if forced:
        return forced
    if isinstance(slip, dict):
        for key in ("targetDate", "date", "bookedAt"):
            digits = _day_digits(slip.get(key))
            if digits:
                return digits
        dates = slip.get("dates")
        if isinstance(dates, list):
            found = [d for d in (_day_digits(x) for x in dates) if d]
            if found:
                return min(found)
    return ""


def lock_id(slip, day=None) -> str:
    existing = (slip or {}).get("locked")
    if isinstance(existing, dict) and ID_RE.fullmatch(str(existing.get("id") or "")):
        return str(existing["id"])
    digits = slip_day(slip, day)
    if len(digits) != 8:
        return ""
    return f"{lock_kind(slip)}-{digits}"


def slip_key(slip) -> str:
    name = re.sub(
        r"[^a-z0-9]+",
        "-",
        str((slip or {}).get("name") or (slip or {}).get("label") or "slip").lower(),
    ).strip("-")[:40]
    odds = slip_odds(slip)
    odds_s = "" if odds is None else f"{odds:.2f}"
    return f"{name}@{odds_s}x{leg_count(slip)}"


def is_slip(doc) -> bool:
    """A booked slip, not a single leg and not one bookmaker's code object."""
    if not isinstance(doc, dict):
        return False
    if "totalOdds" not in doc and "odds" not in doc:
        return False
    if "codes" in doc or ("code" in doc and ("name" in doc or "label" in doc or "legs" in doc or "strategy" in doc)):
        # bare {code, odds, legs, link} entries live inside codes{}
        if "codes" not in doc and "name" not in doc and "label" not in doc and "strategy" not in doc and "match" not in doc:
            if set(doc.keys()) <= _CODE_KEYS:
                return False
        return True
    return False


def flag_slip(slip, day=None):
    """Set premium from total odds > 25. Does not remove codes or picks."""
    if not isinstance(slip, dict):
        return slip
    odds = slip_odds(slip)
    premium = is_premium_odds(odds)
    slip["premium"] = premium
    if not premium:
        return slip
    count = leg_count(slip)
    prev = slip.get("locked") if isinstance(slip.get("locked"), dict) else {}
    lid = ""
    if ID_RE.fullmatch(str(prev.get("id") or "")):
        lid = str(prev["id"])
    else:
        lid = lock_id(slip, day)
    locked = {
        "price": PRICE,
        "currency": CURRENCY,
        "odds": odds,
        "legs": count,
    }
    if lid:
        locked["id"] = lid
    elif prev.get("id"):
        locked["id"] = prev["id"]
    slip["locked"] = locked
    return slip


def flag_document(doc, day=None):
    """Walk a public feed and flag every slip. Legs are not walked."""
    if isinstance(doc, list):
        for item in doc:
            flag_document(item, day)
        return doc
    if not isinstance(doc, dict):
        return doc
    here = day or (doc.get("date") if isinstance(doc.get("date"), str) else None)
    if is_slip(doc):
        flag_slip(doc, here)
    for key, value in doc.items():
        if key in ("legs", "picks") and isinstance(value, list):
            continue
        if isinstance(value, (dict, list)):
            flag_document(value, here)
    return doc


def _brief_rows(raw):
    if not isinstance(raw, list):
        return []
    out = []
    for leg in raw:
        if not isinstance(leg, dict):
            continue
        brief = {k: leg[k] for k in _PICK_FIELDS if leg.get(k) not in (None, "")}
        if brief:
            out.append(brief)
    return out


def _briefs(slip):
    """Pick text lives on `legs` for most slips and on `picks` for model slips."""
    rows = _brief_rows(slip.get("legs"))
    if rows:
        return rows
    return _brief_rows(slip.get("picks"))


def _code_items(slip):
    """Yield (book, item dict) for real or placeholder codes on a slip."""
    codes = slip.get("codes")
    if isinstance(codes, dict):
        for book, raw in codes.items():
            items = raw if isinstance(raw, list) else [raw]
            for item in items:
                if isinstance(item, str):
                    item = {"code": item}
                if isinstance(item, dict):
                    code = item.get("code") or item.get(book)
                    if code:
                        yield book, dict(item, code=code)
    elif isinstance(slip.get("code"), str) and slip.get("code"):
        yield "sportybet", {"code": slip["code"], "totalOdds": slip_odds(slip), "legs": leg_count(slip), "link": slip.get("link") or slip.get("share") or ""}


def _ensure_entry(store, slip, day):
    lid = lock_id(slip, day)
    if not ID_RE.fullmatch(lid or ""):
        return None
    entry = store.get(lid)
    if entry:
        return entry
    kind = lid.split("-", 1)[0]
    titles = {"banker": "Main Banker", "medium": "Medium slip", "hot": "Hot Picks main"}
    digits = lid.split("-", 1)[1]
    entry = {
        "id": lid,
        "kind": kind,
        "title": titles.get(kind, "Premium slip"),
        "date": f"{digits[0:4]}-{digits[4:6]}-{digits[6:8]}",
        "price": PRICE,
        "currency": CURRENCY,
        "totalOdds": slip_odds(slip),
        "codes": {},
        "expires": f"{digits[0:4]}-{digits[4:6]}-{digits[6:8]}T23:59:00Z",
    }
    store[lid] = entry
    return entry


def seal_slip(slip, store, placeholder, day=None):
    """Copy code + picks into store, then blank them on the public slip.

    `placeholder(lock_id, book, index) -> str` must match the paywall
    (`P2ULOCK-{id}-{book}{n}`). Returns True when the slip is premium.
    Non-premium slips are flagged and left readable.
    """
    if not isinstance(slip, dict) or not is_slip(slip):
        return False
    flag_slip(slip, day)
    if not slip.get("premium"):
        return False
    entry = _ensure_entry(store, slip, day)
    if entry is None:
        # No relay id (no match day). Leave the code in place rather than delete it.
        return False
    lid = entry.get("id") or ""
    briefs = _briefs(slip)
    count = leg_count(slip)
    placeholders = {}
    seen = {}
    for book, item in _code_items(slip):
        code = str(item.get("code") or "")
        if not code or code.startswith("P2ULOCK-"):
            if code:
                placeholders.setdefault(book, code)
            continue
        index = 0
        if entry is not None:
            bucket = entry["codes"].setdefault(book, [])
            existing = next((i for i, row in enumerate(bucket) if row.get("code") == code), None)
            if existing is None:
                row = {
                    "code": code,
                    "totalOdds": item.get("totalOdds") or item.get("odds") or slip_odds(slip),
                    "legs": item.get("legs") if isinstance(item.get("legs"), int) else count,
                    "slipKey": slip_key(slip),
                    "title": slip.get("name") or slip.get("label") or entry.get("title") or "",
                }
                if briefs:
                    row["picks"] = briefs
                bucket.append(row)
                existing = len(bucket) - 1
            elif briefs and not bucket[existing].get("picks"):
                bucket[existing]["picks"] = briefs
                bucket[existing]["slipKey"] = slip_key(slip)
            index = existing
        if lid and book not in seen:
            placeholders[book] = placeholder(lid, book, index)
            seen[book] = True
    _blank_public(slip, placeholders, count)
    return True


def _blank_public(slip, placeholders, count):
    """Remove booking codes and pick text. Keep odds, leg count and the flag."""
    odds = slip_odds(slip)
    flag_slip(slip)
    slip["legCount"] = count
    if isinstance(slip.get("locked"), dict):
        slip["locked"]["legs"] = count
        if odds is not None:
            slip["locked"]["odds"] = odds
    if isinstance(slip.get("legs"), list):
        slip["legs"] = []
    if isinstance(slip.get("picks"), list):
        slip["picks"] = count
    codes = slip.get("codes")
    if isinstance(codes, dict):
        blank = {}
        for book, raw in codes.items():
            ph = placeholders.get(book, "")
            if isinstance(raw, list):
                blank[book] = [{"code": ph, "totalOdds": odds, "legs": count}] if ph else []
            elif isinstance(raw, dict):
                blank[book] = {"code": ph, "odds": raw.get("odds") or odds, "legs": count, "link": ""} if ph else {"code": "", "link": ""}
            else:
                blank[book] = ph
        slip["codes"] = blank
    if isinstance(slip.get("code"), str):
        slip["code"] = placeholders.get("sportybet", "")
    for key in ("link", "share", "shareUrl"):
        if isinstance(slip.get(key), str):
            slip[key] = ""
    if isinstance(slip.get("links"), dict):
        slip["links"] = {k: "" for k in slip["links"]}
    slip["premium"] = True


def seal_document(doc, store, placeholder, day=None):
    """Seal every premium slip in a feed. Returns how many slips were sealed."""
    found = []

    def walk(node, here):
        if isinstance(node, list):
            for item in node:
                walk(item, here)
            return
        if not isinstance(node, dict):
            return
        day_here = here or (node.get("date") if isinstance(node.get("date"), str) else None)
        if is_slip(node):
            found.append((node, day_here))
        for key, value in node.items():
            if key in ("legs", "picks") and isinstance(value, list):
                continue
            if isinstance(value, (dict, list)):
                walk(value, day_here)

    walk(doc, day)
    n = 0
    for slip, here in found:
        if seal_slip(slip, store, placeholder, here):
            n += 1
    return n


def stamp_file(path):
    with open(path, encoding="utf-8") as handle:
        doc = json.load(handle)
    flag_document(doc)
    text = json.dumps(doc, ensure_ascii=False, separators=(",", ":"))
    # keep a trailing newline when the source had one
    with open(path, encoding="utf-8") as handle:
        raw = handle.read()
    if raw.endswith("\n"):
        text += "\n"
    if text != raw:
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text)
        return True
    return False


def stamp_repo(repo):
    changed = []
    for name in PUBLIC_JSON:
        path = os.path.join(repo, name)
        if os.path.isfile(path) and stamp_file(path):
            changed.append(name)
    return changed


def lock_published(repo=None, dry_run=False) -> int:
    """Flag odds above 25, then hide the code and the picks when the lock key exists.

    Used by the morning pipeline and by the M1/M2 and strategies workflows after
    they write home-picks, hot-picks and high_odds. Price and Paystack are untouched.
    """
    from .paths import PRIV_DIR, REPO_DIR, VENDOR_DIR, ensure_dirs

    repo = str(repo or os.environ.get("REPO_DIR") or REPO_DIR)
    stamp_repo(repo)
    key_path = Path(os.environ.get("PRIV_DIR") or PRIV_DIR) / "lock.key"
    if os.environ.get("P2U_LOCK_KEY") and not key_path.exists():
        ensure_dirs()
        key_path.parent.mkdir(parents=True, exist_ok=True)
        key_path.write_text(os.environ["P2U_LOCK_KEY"].strip() + "\n")
        os.chmod(key_path, 0o600)
    if os.environ.get("P2U_LOCK_KEY") or key_path.exists():
        env = os.environ.copy()
        env["PRIV_DIR"] = str(key_path.parent)
        env["REPO_DIR"] = repo
        proc = subprocess.run([sys.executable, str(VENDOR_DIR / "lock_codes.py"), repo], env=env)
        if proc.returncode != 0:
            print("lock failed:", proc.returncode)
            if not dry_run:
                raise SystemExit("refusing to publish unlocked premium codes")
            return proc.returncode
    else:
        print("publish: P2U_LOCK_KEY / lock.key missing — premium lock skipped (do not commit raw banker codes without it)")
    return 0


def main(argv=None):
    args = list(argv if argv is not None else sys.argv[1:])
    do_lock = False
    if "--lock" in args:
        do_lock = True
        args = [a for a in args if a != "--lock"]
    repo = args[0] if args else os.environ.get("REPO_DIR", ".")
    if do_lock:
        return lock_published(repo)
    changed = stamp_repo(repo)
    print("premium flagged", changed or "unchanged")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
