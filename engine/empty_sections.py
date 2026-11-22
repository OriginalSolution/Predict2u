#!/usr/bin/env python3
"""Empty strategy sections are never published (HANDOFF §5.11).

A strategy section with zero valid codes is omitted from the public feeds.
History cards that have codes are kept. high_odds.json stays one-line JSON.
Each strategy keeps its own origin (strategy-ttw, strategy-form80, …) so the
site can group codes; a generic "strategy" overwrite is forbidden.
"""
from __future__ import annotations

import json
from pathlib import Path

# Public High-tab sections and the same origin key used when a strategy publishes.
# Other strategy-* origins (sure80, hs15, master, …) follow the same rule.
HIGH_TAB_SECTIONS = (
    ("strategy-ttw", "Team To Win"),
    ("strategy-form80", "80% Form"),
    ("strategy-mo25", "Match Over 2.5"),
    ("strategy-ah1", "AH -1 Favourite"),
)

# Origins the High Odds board already uses that must not be rewritten.
KEEP_ORIGINS = frozenset({"ho-master", "daily-master", "code-hub"})

# Longest-first so "Reverse U4.5 + Draw" wins over "Reverse U4.5".
_PUBLIC_NAMES = (
    ("rev-u45-draw", "Reverse U4.5 + Draw"),
    ("hs15", "High-Scoring O1.5/O2.5"),
    ("nysm-conservative", "Model conservative"),
    ("nysm-main", "Model main"),
    ("nysm-ts2", "Team to score 2+"),
    ("sure80", "80% Sure"),
    ("rev-u45", "Reverse U4.5"),
    ("form80", "80% Form"),
    ("mo25", "Match Over 2.5"),
    ("ah1", "AH -1 Favourite"),
    ("ttw", "Team To Win"),
    ("master", "Code of the Day"),
    ("nt", "Checked goals"),
    ("gg", "GG goals"),
    ("mp", "Master"),
)


def has_valid_code(slip: dict) -> bool:
    """True when the card has a bookable/published booking code."""
    if not isinstance(slip, dict):
        return False
    code = slip.get("code")
    if isinstance(code, str) and code.strip():
        return True
    codes = slip.get("codes")
    if isinstance(codes, dict):
        for value in codes.values():
            if isinstance(value, dict) and str(value.get("code") or "").strip():
                return True
            if isinstance(value, list) and any(
                isinstance(row, dict) and str(row.get("code") or "").strip() for row in value
            ):
                return True
            if isinstance(value, str) and value.strip():
                return True
    return False


def _name_strategy_id(name: str) -> str | None:
    text = str(name or "")
    if " · " in text:
        text = text.split(" · ", 1)[0]
    for sid, label in _PUBLIC_NAMES:
        if text == label or text.startswith(label + " ") or text.startswith(label + "·"):
            return sid
    return None


def preserve_origin(slip: dict) -> str:
    """Keep a specific strategy origin; only fill one in when it is missing or generic."""
    if not isinstance(slip, dict):
        return "code-hub"
    origin = str(slip.get("origin") or "").strip()
    if origin.startswith("strategy-") or origin in KEEP_ORIGINS:
        return origin
    pipeline = str(slip.get("pipeline") or "").strip()
    if pipeline:
        return pipeline if pipeline.startswith("strategy-") else f"strategy-{pipeline}"
    for key in ("strategy", "kind", "slipId"):
        sid = str(slip.get(key) or "").strip()
        if sid and sid not in {"strategy", "code-hub"}:
            return sid if sid.startswith("strategy-") else f"strategy-{sid}"
    sid = _name_strategy_id(slip.get("name") or "")
    if sid:
        return f"strategy-{sid}"
    if origin == "strategy" or slip.get("strategyJob") or slip.get("strategySpec"):
        return "strategy"
    return origin or "code-hub"


def drop_empty_strategy_cards(slips: list | None) -> list:
    """Drop cards with no valid code. Cards that have codes, including history, stay."""
    return [row for row in (slips or []) if has_valid_code(row)]


def sections_to_publish(slips: list | None, sections: tuple = HIGH_TAB_SECTIONS) -> list[dict]:
    """Only sections that have at least one valid code. All-empty → []."""
    rows = [s for s in (slips or []) if has_valid_code(s)]
    out = []
    for origin, title in sections:
        found = [s for s in rows if s.get("origin") == origin]
        if found:
            out.append({"origin": origin, "title": title, "slips": found})
    return out


def prepare_high_odds_doc(doc: dict | None) -> dict:
    """Repair origins, drop empty live cards, keep history cards that have codes.

    high_odds.json stays compact one-line when written with compact_text().
    """
    doc = dict(doc or {})
    slips = []
    for row in doc.get("slips") or []:
        if not isinstance(row, dict):
            continue
        row = dict(row)
        row["origin"] = preserve_origin(row)
        slips.append(row)
    history = []
    for row in doc.get("history") or []:
        if not isinstance(row, dict):
            continue
        row = dict(row)
        row["origin"] = preserve_origin(row)
        history.append(row)
    doc["slips"] = drop_empty_strategy_cards(slips)
    # History: keep every card that still has a code; never wipe settled proofs.
    doc["history"] = drop_empty_strategy_cards(history)
    return doc


def compact_text(doc: dict) -> str:
    """one-line JSON, as required for high_odds.json."""
    return json.dumps(doc, ensure_ascii=False, separators=(",", ":"))


def write_high_odds(path: Path, doc: dict) -> dict:
    prepared = prepare_high_odds_doc(doc)
    Path(path).write_text(compact_text(prepared))
    return prepared
