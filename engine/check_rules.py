#!/usr/bin/env python3
"""Fail CI when engine code drifts from engine/RULES.md + engine/config.json."""
from __future__ import annotations
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENGINE = ROOT / "engine"
CFG_PATH = ENGINE / "config.json"
RULES_PATH = ENGINE / "RULES.md"


def fail(msg: str) -> None:
    print(f"check_rules: {msg}", file=sys.stderr)
    raise SystemExit(1)


def main() -> int:
    cfg = json.loads(CFG_PATH.read_text())
    rules = RULES_PATH.read_text()
    mr = (ENGINE / "vendor" / "matchup_rules.py").read_text()
    pipe = (ENGINE / "pipeline.py").read_text()
    bookers = (ENGINE / "bookers.py").read_text()
    inbox = (ENGINE / "inbox.py").read_text()

    if "Never publish or book **double chance**" not in rules and "double chance" not in rules.lower():
        fail("RULES.md must document the double-chance veto")
    if "NG" not in rules or "BTTS No" not in rules:
        fail("RULES.md must document the NG / BTTS No veto")
    if "25+" not in rules and "25 +" not in rules:
        fail("RULES.md must require 25+ main slips")

    if "def is_double_chance" not in mr or "def is_btts_no" not in mr:
        fail("matchup_rules.py must define is_double_chance and is_btts_no")
    if not re.search(r"MAX_LEG\s*=\s*1\.60", mr):
        fail("matchup_rules.py MAX_LEG must be 1.60")
    if abs(float(cfg["max_leg_odds"]) - 1.6) > 0.001:
        fail("config.json max_leg_odds must be 1.6")
    if int(cfg["min_main_slip_odds"]) != 25:
        fail("config.json min_main_slip_odds must be 25")
    if cfg["hard_vetoes"] != ["double_chance", "btts_no"]:
        fail("config.json hard_vetoes must be [double_chance, btts_no]")

    if "is_btts_no" not in pipe or "is_double_chance" not in pipe:
        fail("pipeline.py must strip both DC and NG after collect")
    if "ah_minus_one" not in pipe or "dc_shield" not in pipe or "high_odds.py" not in pipe:
        fail("pipeline.py must invoke dc_shield, high_odds and ah_minus_one")
    if "share_cards" not in pipe or "telegram_post" not in pipe:
        fail("pipeline.py must invoke share_cards and telegram_post")

    if "betway" in bookers.lower() and "NO_LOGIN" in bookers:
        # Betway may be mentioned as omitted; it must not be in NO_LOGIN.
        ns = ENGINE / "bookers.py"
        src = ns.read_text()
        m = re.search(r"NO_LOGIN\s*=\s*\((.*?)\)", src, re.S)
        if not m or "betway" in m.group(1):
            fail("bookers.NO_LOGIN must not include betway")
    if cfg["bookmakers"] != ["sportybet", "footballcom", "msport", "betika", "betpawa"]:
        fail("config.json bookmakers drifted")

    if "smagpf" not in inbox.lower():
        fail("inbox.py must ignore SMAGPF")

    if "combined" not in rules.lower() and "combine" not in rules.lower():
        fail("RULES.md must document combining short codes to 25+")
    if not cfg.get("combine_under_min_odds"):
        fail("config.json combine_under_min_odds must be true")
    if "combine" not in pipe:
        fail("pipeline.py must run the combine-to-25 inbox step")
    if not (ENGINE / "combine.py").exists():
        fail("missing engine/combine.py")

    for name in cfg["required_vendor"]:
        path = ENGINE / "vendor" / name
        if not path.exists():
            fail(f"missing vendor script {name}")

    wf = {
        "daily": ROOT / ".github/workflows/engine-daily.yml",
        "shield": ROOT / ".github/workflows/engine-shield.yml",
        "settle_morning": ROOT / ".github/workflows/engine-settle.yml",
        "settle_bihourly": ROOT / ".github/workflows/engine-settle.yml",
    }
    for key, path in wf.items():
        if not path.exists():
            fail(f"missing workflow {path.name}")
        text = path.read_text()
        cron = cfg["schedules"][key]
        if cron not in text:
            fail(f"{path.name} missing cron {cron}")

    print("check_rules: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
