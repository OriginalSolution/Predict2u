#!/usr/bin/env python3
"""Proposed NerdyTips GLOBAL gates — DISABLED by default.

These conflict with standing user rules (all bookmakers, 50-pick cap, GG allowed,
existing combine/min-odds behaviour). They must stay off until the user explicitly
enables them in engine/config.json → optional_gates.enabled.

Usage:
  from engine.gates.optional_gates import apply_optional_gates
  picks = apply_optional_gates(picks, cfg)

Each gate is a pure filter / transform. When disabled, apply_optional_gates is a no-op.
"""
from __future__ import annotations
import json
from collections import defaultdict
from pathlib import Path

DEFAULTS = {
    "enabled": False,  # master switch — must stay false unless user says otherwise
    "sportybet_gh_only": False,          # conflicts: all bookmakers
    "min_odds_every_code": False,        # 25+ already required for MAIN slips; this would force ALL codes
    "gg_benched": False,                 # conflicts: GG allowed under standing rules
    "riddim_edge_legs_below_1_50": False,
    "max_codes_per_event": False,        # max 2 distinct codes per eventId
    "max_codes_per_event_n": 2,
    "drop_top5_v_top5_bottom3_v_bottom3": False,  # already in matchup_rules for classified leagues
    "max_tips_per_code_25": False,       # conflicts: standing 50-pick cap (+ split)
    "per_league_own_history": False,
}


def load_optional(cfg: dict | None = None) -> dict:
    cfg = cfg or {}
    opt = dict(DEFAULTS)
    opt.update((cfg.get("optional_gates") or {}))
    return opt


def gate_sportybet_gh_only(bookmakers: list[str], opt: dict) -> list[str]:
    if not (opt.get("enabled") and opt.get("sportybet_gh_only")):
        return bookmakers
    return [b for b in bookmakers if b == "sportybet"]


def gate_min_odds(slip: dict, opt: dict, min_odds: float = 25.0) -> bool:
    """Return True if slip may publish."""
    if not (opt.get("enabled") and opt.get("min_odds_every_code")):
        return True
    try:
        return float(slip.get("odds") or slip.get("totalOdds") or 0) >= float(min_odds)
    except Exception:
        return False


def gate_gg_benched(pick: dict, opt: dict) -> bool:
    """Return True if pick is allowed."""
    if not (opt.get("enabled") and opt.get("gg_benched")):
        return True
    sel = str(pick.get("selection") or "").lower()
    mk = str(pick.get("market") or "").lower()
    if sel in ("gg", "yes", "btts yes", "both teams to score") or "both teams" in mk:
        return False
    return True


def gate_riddim_edge_leg(pick: dict, opt: dict) -> bool:
    if not (opt.get("enabled") and opt.get("riddim_edge_legs_below_1_50")):
        return True
    if not pick.get("riddimEdge"):
        return True
    try:
        return float(pick.get("odds") or 0) < 1.50
    except Exception:
        return False


def gate_max_codes_per_event(slips: list[dict], opt: dict) -> list[dict]:
    if not (opt.get("enabled") and opt.get("max_codes_per_event")):
        return slips
    nmax = int(opt.get("max_codes_per_event_n") or 2)
    counts: dict[str, int] = defaultdict(int)
    out = []
    for s in slips:
        eids = {l.get("eventId") or l.get("eid") for l in (s.get("legs") or []) if isinstance(l, dict)}
        eids.discard(None)
        # allow slip if every event still under cap
        if any(counts[e] >= nmax for e in eids):
            continue
        for e in eids:
            counts[e] += 1
        out.append(s)
    return out


def gate_max_tips_25(legs: list[dict], opt: dict) -> list[list[dict]]:
    """Split into chunks of 25 when enabled; otherwise return [legs] unchanged.
    Standing rule is 50 — this gate stays off."""
    if not (opt.get("enabled") and opt.get("max_tips_per_code_25")):
        return [legs]
    size = 25
    return [legs[i:i + size] for i in range(0, len(legs), size)] or [[]]


def apply_optional_gates(picks: list[dict], cfg: dict | None = None) -> list[dict]:
    opt = load_optional(cfg)
    if not opt.get("enabled"):
        return picks
    out = []
    for p in picks:
        if not gate_gg_benched(p, opt):
            continue
        if not gate_riddim_edge_leg(p, opt):
            continue
        out.append(p)
    return out


def describe_gates(cfg: dict | None = None) -> list[dict]:
    opt = load_optional(cfg)
    rows = []
    for k, default in DEFAULTS.items():
        if k == "enabled":
            continue
        rows.append({
            "gate": k,
            "enabled": bool(opt.get("enabled") and opt.get(k)),
            "default": default,
            "master_enabled": bool(opt.get("enabled")),
        })
    return rows


if __name__ == "__main__":
    cfg_path = Path(__file__).resolve().parents[1] / "config.json"
    cfg = json.loads(cfg_path.read_text()) if cfg_path.exists() else {}
    print(json.dumps(describe_gates(cfg), indent=2))
