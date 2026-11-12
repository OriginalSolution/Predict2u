"""Merge nightly model slips into hot-picks.json without dropping hub slips.

Empty bookmaker sections are omitted (no code → the Hot page and carousel hide them).
`legs` stays an integer count, matching the existing Hot slip shape. The pick list
lives on `picks` so settle and prune can walk eventId + selection.
"""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

LINKS = {
    "sportybet": "https://www.sportybet.com/gh/?shareCode={}",
    "footballcom": "https://www.football.com/gh/?shareCode={}",
    "msport": "https://www.msport.com/gh/?shareCode={}",
    "betika": "https://betika.com/en-gh/share/{}",
    "betpawa": "https://www.betpawa.com.gh/share-betslip/{}",
}


def hot_path(repo: Path) -> Path:
    return Path(repo) / "hot-picks.json"


def load_hot(repo: Path) -> dict:
    p = hot_path(repo)
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text())
    except Exception:
        return {}


def save_hot(repo: Path, doc: dict) -> None:
    hot_path(repo).write_text(json.dumps(doc, indent=1, ensure_ascii=False))


def codes_from_book(raw: dict, n_legs: int) -> dict:
    """bookers.book_all result → carousel chip lists. Books that failed are absent."""
    out = {}
    for name, r in (raw or {}).items():
        if not isinstance(r, dict) or not r.get("code"):
            continue
        link = LINKS.get(name)
        if not link:
            continue
        out[name] = [{
            "code": r["code"],
            "totalOdds": r.get("totalOdds"),
            "legs": r.get("legs") or n_legs,
            "link": link.format(r["code"]),
        }]
    return out


def book_legs(legs):
    from engine import bookers
    return codes_from_book(bookers.book_all(list(legs)), len(legs))


def upsert_model_slips(repo: Path, slips: list[dict], replace_strategies: set[str] | None = None) -> dict:
    """Replace slips whose strategy is in this batch, keep every other model slip and the hub."""
    doc = load_hot(repo)
    keys = replace_strategies or {s.get("strategy") for s in slips}
    kept = [s for s in (doc.get("modelSlips") or []) if s.get("strategy") not in keys]
    # Hide a slip that booked on nobody.
    fresh = [s for s in slips if s.get("codes")]
    doc["modelSlips"] = fresh + kept
    doc["updatedAt"] = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    save_hot(repo, doc)
    return doc
