"""Drop-folder contract for extra picks (teammate bots cannot be called from cron).

Drop a JSON file into engine/inbox/ (or engine/inbox/<source>/YYYY-MM-DD.json).
Files named README*, schema*, or starting with _ are ignored. SMAGPF is ignored.
Bot/tipster names are stripped before picks enter the house pipeline.
"""
from __future__ import annotations
import json
import re
from pathlib import Path

from .paths import INBOX_DIR

SCRUB = re.compile(r'nerdy\s*tips|nerdy|bets\s*for\s*the\s*day|betsfortheday|betting strategies|smagpf|tipster', re.I)
SKIP_SOURCES = {"smagpf"}
REQUIRED = ("match", "selection", "eventId", "marketId", "outcomeId")


def _clean(v):
    if isinstance(v, str):
        return SCRUB.sub("Predict2U", v)
    if isinstance(v, list):
        return [_clean(x) for x in v]
    if isinstance(v, dict):
        return {k: _clean(x) for k, x in v.items() if k not in ("source", "bot", "build", "src", "tipster")}
    return v


def iter_files(inbox: Path | None = None):
    root = Path(inbox or INBOX_DIR)
    if not root.exists():
        return
    for path in sorted(root.rglob("*.json")):
        if path.name.startswith("_") or path.name.startswith("schema") or path.name == "example.json":
            continue
        if path.parent.name.lower() in SKIP_SOURCES or path.stem.lower() in SKIP_SOURCES:
            continue
        yield path


def load_picks(inbox: Path | None = None) -> list[dict]:
    picks = []
    for path in iter_files(inbox) or []:
        try:
            data = json.loads(path.read_text())
        except Exception as e:
            print("inbox skip", path, e)
            continue
        rows = data if isinstance(data, list) else data.get("picks") or data.get("legs") or []
        for raw in rows:
            p = _clean(raw)
            if not all(p.get(k) for k in REQUIRED):
                continue
            p.setdefault("specifier", "")
            p.setdefault("odds", 0)
            p.setdefault("market", "")
            p.setdefault("result", "pending")
            p["inboxFile"] = path.name
            picks.append(p)
    return picks


def merge(house_picks: list[dict], extra: list[dict]) -> list[dict]:
    seen = {(p.get("eventId"), str(p.get("marketId")), p.get("specifier") or "", str(p.get("outcomeId"))) for p in house_picks}
    out = list(house_picks)
    for p in extra:
        key = (p.get("eventId"), str(p.get("marketId")), p.get("specifier") or "", str(p.get("outcomeId")))
        if key in seen:
            continue
        seen.add(key)
        out.append(p)
    return out


def load_share_codes(inbox: Path | None = None) -> list[str]:
    """SportyBet share codes listed in inbox JSON (not yet decoded into picks)."""
    codes = []
    seen = set()
    for path in iter_files(inbox) or []:
        try:
            data = json.loads(path.read_text())
        except Exception:
            continue
        if not isinstance(data, dict):
            continue
        raw = data.get("shareCodes") or data.get("share_codes")
        if isinstance(raw, str):
            raw = raw.replace(",", " ").split()
        extra = list(raw or [])
        if isinstance(data.get("code"), str) and not (data.get("picks") or data.get("legs")):
            extra.append(data["code"])
        for c in extra:
            if isinstance(c, str) and c.strip() and c.strip() not in seen:
                seen.add(c.strip())
                codes.append(c.strip())
    return codes
