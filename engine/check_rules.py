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

    if "DC 12" not in rules or "1.35" not in rules:
        fail("RULES.md must document the DC 12 veto and the 1.35 1X/X2 cap")
    if "NG" not in rules or "BTTS No" not in rules:
        fail("RULES.md must document the NG / BTTS No veto")
    if "25+" not in rules and "25 +" not in rules:
        fail("RULES.md must require 25+ main slips")

    if "def is_double_chance" not in mr or "def is_dc_vetoed" not in mr or "def is_btts_no" not in mr:
        fail("matchup_rules.py must define is_double_chance, is_dc_vetoed and is_btts_no")
    if not re.search(r"DC_1X_X2_MAX\s*=\s*1\.35", mr):
        fail("matchup_rules.py DC_1X_X2_MAX must be 1.35")
    if not re.search(r"MAX_LEG\s*=\s*1\.60", mr):
        fail("matchup_rules.py MAX_LEG must be 1.60")
    if abs(float(cfg["max_leg_odds"]) - 1.6) > 0.001:
        fail("config.json max_leg_odds must be 1.6")
    if int(cfg["min_main_slip_odds"]) != 25:
        fail("config.json min_main_slip_odds must be 25")
    if cfg.get("hard_vetoes") != ["double_chance_12", "double_chance_1x_x2_above_1.35", "btts_no", "obscure_league_non_goals"]:
        fail("config.json hard_vetoes drifted")
    if abs(float(cfg.get("dc_1x_x2_max") or 0) - 1.35) > 0.001:
        fail("config.json dc_1x_x2_max must be 1.35")

    if "is_btts_no" not in pipe or "is_dc_vetoed" not in pipe:
        fail("pipeline.py must strip vetoed DC and NG after collect")
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

    # Bookmaker deep-link formats (must load the booking code, not a 404 / bare homepage).
    build = (ENGINE / "vendor" / "build.py").read_text()
    hot = (ENGINE / "vendor" / "hot_picks.py").read_text()
    book_home = (ENGINE / "vendor" / "book_home.py").read_text()
    if "msport.com/gh/sports/share" in build or "msport.com/gh/sports/share" in hot or "msport.com/gh/sports/share" in book_home:
        fail("MSport share links must use https://www.msport.com/gh/?shareCode= (not /gh/sports/share)")
    if "betpawa.com.gh/#" in build or "betpawa.com.gh/#" in hot:
        fail("Betpawa share links must use /share-betslip/{code}, not /#code")
    if "share-betslip/{}" not in build and "share-betslip/{}" not in hot:
        # build uses BOOK_LINKS with {}; hot uses LINK with {}
        if "share-betslip/{}" not in build:
            fail("build.py BOOK_LINKS betpawa must be share-betslip/{}")

    hot_src = hot
    # `info` holds the code-hub selection details; rebinding it at top level
    # (e.g. `picks, info = _tp.select(...)`) crashed hot_picks.py with KeyError.
    if re.search(r"(?m)^[^\s#][^\n]*\binfo\s*=\s*_tp\.select", hot_src):
        fail("hot_picks.py must not rebind the hub `info` dict with thin_pool.select results")
    if "sectionMasters" not in hot_src:
        fail("hot_picks.py must build sectionMasters for each Hot page section")
    if not (ENGINE / "vendor" / "hot_section_masters.py").exists():
        fail("missing vendor/hot_section_masters.py")
    hsm = (ENGINE / "vendor" / "hot_section_masters.py").read_text()
    if "SECTION_BUILDERS" not in hsm:
        fail("hot_section_masters.py must define SECTION_BUILDERS")
    for sid in ("hot_matches", "hot_by_market", "trending_markets", "hot_teams", "most_backed_teams"):
        if sid not in hsm:
            fail(f"hot_section_masters.py missing section id {sid}")
    if "sectionMasters" not in rules:
        fail("RULES.md must document Hot sectionMasters")


    if "obscure_league_non_goals" not in cfg.get("hard_vetoes", []):
        fail("config.json hard_vetoes must include obscure_league_non_goals")
    majors = (cfg.get("major_leagues") or {}).get("patterns") or []
    if len(majors) < 20:
        fail("config.json major_leagues.patterns must list major competitions")
    if "ghana - premier league" not in [str(x).lower() for x in majors]:
        fail("major_leagues must include Ghana Premier League")
    if "obscure" not in rules.lower() or "goals only" not in rules.lower():
        fail("RULES.md must document obscure-league goals-only veto")
    mr = (ENGINE / "vendor" / "matchup_rules.py").read_text()
    for token in ("is_obscure_league_non_goals", "is_goals_market", "is_major_league", "swap_to_goals"):
        if token not in mr:
            fail(f"matchup_rules.py missing {token}")

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
