#!/usr/bin/env python3
"""NerdyTips Tomorrow picks, trust 5.0+, independent check must Agree.

1X2 picks are converted to GG, or to GG / Over 1.5 in a mismatch. Only Agree
verdicts are booked. Flagged legs and table-unchecked legs are dropped.
GG above 1.50 and prices outside 1.20–1.75 are dropped.

No owner cookie and no password are stored. The public Tomorrow board and
public match pages are fetched anonymously (a timezone cookie only, so
kickoffs stay on GMT). A page with no visible confidence score is skipped.
"""
from __future__ import annotations

import argparse
import datetime as dt
import difflib
import html as html_lib
import json
import re
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parent)]
import strategy_lib as lib

TRUST_MIN = 5.0
CODE_ID = "nt"
UA_HEADERS = ["X-Requested-With: XMLHttpRequest", "Referer: https://nerdytips.com/all-matches?d=1"]
MONTHS = {name: i for i, name in enumerate(
    ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], 1)}
YOUTH_TEAM = re.compile(r"Res\.|Reserve|\bII\b|\bB\b$|U-?1\d|U-?2\d|Youth|Academy|\(Am\)|\bJong |Primavera|Juniores", re.I)
YOUTH_LEAGUE = re.compile(r"Reserve|U-?1\d|U-?2\d|Youth|Primavera|Juniores|Premier League Cup|Central Youth", re.I)
WOMEN = re.compile(r"Women|\bW\b|Feminin|Frauen|Damen|Femenin|WSL|NWSL|Womens|Liga F\b", re.I)
DATE_RE = re.compile(r"^[A-Z][a-z]{2} \d{1,2}$")
NAME = {
    "1||Home": "Home win", "1||Away": "Away win",
    "10||Home or Draw": "Home or draw (1X)", "10||Draw or Away": "Draw or away (X2)",
    "18|total=1.5|Over 1.5": "Over 1.5", "18|total=3.5|Under 3.5": "Under 3.5",
    "29||Yes": "GG (BTTS Yes)",
    "19|total=0.5|Over 0.5": "Home team to score (O0.5)",
    "20|total=0.5|Over 0.5": "Away team to score (O0.5)",
}
ALLOW = {
    "mismatch": {"18|total=1.5|Over 1.5", "29||Yes", "19|total=0.5|Over 0.5", "20|total=0.5|Over 0.5", "10||Home or Draw", "10||Draw or Away"},
    "even": {"18|total=3.5|Under 3.5", "29||Yes", "19|total=0.5|Over 0.5", "20|total=0.5|Over 0.5", "10||Home or Draw", "10||Draw or Away"},
    "middle": {"29||Yes", "19|total=0.5|Over 0.5", "20|total=0.5|Over 0.5", "10||Home or Draw", "10||Draw or Away"},
}
KEEP_KEYS = [
    "1||Home", "1||Draw", "1||Away", "10||Home or Draw", "10||Draw or Away",
    "18|total=1.5|Over 1.5", "18|total=2.5|Over 2.5", "18|total=3.5|Under 3.5",
    "18|total=2.5|Under 2.5", "29||Yes", "19|total=0.5|Over 0.5", "20|total=0.5|Over 0.5",
]


def american_to_decimal(token) -> float | None:
    if token is None:
        return None
    text = str(token).strip()
    try:
        if text.startswith(("+", "-")):
            value = float(text)
            return round((1 + value / 100) if value > 0 else (1 + 100 / abs(value)), 2)
        return float(text)
    except Exception:
        return None


def page_text(raw: str) -> list[str]:
    raw = re.sub(r"<script.*?</script>|<style.*?</style>|<svg.*?</svg>", "", raw, flags=re.S)
    raw = re.sub(r"<[^>]+>", "\n", raw)
    return [html_lib.unescape(line).strip() for line in raw.split("\n") if html_lib.unescape(line).strip()]


def confidence_after(lines: list[str], key: str, start: int = 0):
    try:
        index = lines.index(key, start)
    except ValueError:
        return None
    for cursor in range(index + 1, min(index + 8, len(lines))):
        if lines[cursor] == "/10":
            try:
                return float(lines[cursor - 1])
            except Exception:
                return None
    return None


def parse_title_date(title: str) -> dt.date | None:
    match = re.search(r"([A-Z][a-z]{2}) (\d{1,2}), (\d{4})", title or "")
    if not match:
        return None
    month = MONTHS.get(match.group(1))
    if not month:
        return None
    return dt.date(int(match.group(3)), month, int(match.group(2)))


def parse_list(raw: str) -> list[dict]:
    found = {}
    pattern = re.compile(
        r'<a href="(/match-details/[^"]+)" data-match="(\d+)" data-kick="([^"]*)"[^>]*>\s*<span class="sr-only">([^<]*)</span>',
        re.S,
    )
    for match in pattern.finditer(raw):
        url, ident, kick, sr = match.groups()
        if ident in found:
            continue
        sr = html_lib.unescape(sr)
        row = {"id": ident, "url": "https://nerdytips.com" + url, "kick": kick, "sr": sr}
        parsed = re.match(
            r"(.*) vs (.*), (.*), kick-off (\d\d:\d\d)\. Odds: ([-+\d.]+) home, ([-+\d.]+) draw, ([-+\d.]+) away\.(?: Best tip: (.*), odds ([-+\d.]+), confidence ([\d.]+)/10\.)?",
            sr,
        )
        if parsed:
            groups = parsed.groups()
            row.update(home=groups[0], away=groups[1], league=groups[2],
                       o1=american_to_decimal(groups[4]), ox=american_to_decimal(groups[5]), o2=american_to_decimal(groups[6]),
                       tip=groups[7], trust=float(groups[9]) if groups[9] else None)
        found[ident] = row
    return list(found.values())


def parse_detail(raw: str) -> dict:
    title_match = re.search(r"<title>([^<]+)</title>", raw)
    title = html_lib.unescape(title_match.group(1)) if title_match else ""
    lines = page_text(raw)
    if title and title not in lines:
        lines = [title] + lines
    out = {"title": title, "date": parse_title_date(title), "warnings": [html_lib.unescape(x).strip() for x in re.findall(r'md-warn__t">(.*?)</p>', raw, re.S)]}
    teams = re.match(r"(.*) vs (.*) Prediction - ", title)
    if teams:
        out["home"], out["away"] = teams.group(1), teams.group(2)
    for key, name in (("Best Tip", "c_best"), ("1x2 Tip", "c_1x2"), ("Total Goals", "c_tg"), ("Both Teams To Score", "c_btts"), ("Bet Builder Tip", "c_bb")):
        out[name] = confidence_after(lines, key)
    try:
        index = lines.index("Best Tip")
        # Phrase sitting in front of the confidence, e.g. "Vasteras SK FK or draw".
        if index + 3 < len(lines) and lines[index + 4] == "/10":
            out["free"] = lines[index + 3]
    except ValueError:
        pass
    try:
        index = lines.index("xG")
        out["xg"] = [float(lines[index + 2]), float(lines[index + 4])]
    except Exception:
        out["xg"] = None
    try:
        index = lines.index("Overview Last 10 Matches")

        def pair(name):
            cursor = lines.index(name, index)
            return [int(lines[cursor + 2]), int(lines[cursor + 4])]

        out["l10"] = {name: pair(name) for name in ["Wins", "Over 1.5 Goals", "Over 2.5 Goals", "Over 3.5 Goals", "Both Teams Scored"]}
    except Exception:
        out["l10"] = None
    try:
        form = []
        index = lines.index("Overview Last 10 Matches")
        recent = lines.index("Recent Matches", index)
        for block_start in (recent,):
            letters = [token for token in lines[block_start:block_start + 40] if token in {"W", "D", "L"}]
            # Two form strings of five sit near the top of each club block; take the first ten letters in pairs of five.
            if len(letters) >= 10:
                form = [letters[:5], letters[5:10]]
        out["form5"] = form or None
    except Exception:
        out["form5"] = None
    return out


def norm_name(value: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", (value or "").lower().replace("-", " "))


def similar(left: str, right: str) -> float:
    left, right = norm_name(left), norm_name(right)
    if left and (left in right or right in left):
        return 1.0
    return difflib.SequenceMatcher(None, left, right).ratio()


def match_fixture(row: dict, fixtures: list[dict]) -> dict | None:
    kick = row.get("kick")
    if not kick:
        return None
    hour, minute = kick.split(":")
    plus = (dt.datetime.strptime(kick, "%H:%M") + dt.timedelta(hours=1)).strftime("%H:%M")
    cand = [fix for fix in fixtures if fix["kick"] in {kick, plus}]
    if not cand:
        return None
    best = max(cand, key=lambda fix: (similar(row.get("home") or "", fix["home"]) + similar(row.get("away") or "", fix["away"])) / 2)
    score = (similar(row.get("home") or "", best["home"]) + similar(row.get("away") or "", best["away"])) / 2
    if score < 0.62:
        return None
    best = dict(best)
    best["sim"] = round(score, 2)
    return best


def _ppg(pos):
    if pos and pos.get("p"):
        return round(pos["pts"] / pos["p"], 2)
    return None


def classify(row: dict, info: dict) -> tuple:
    prices = row["O"]
    home = (prices.get("1||Home") or [None])[0]
    away = (prices.get("1||Away") or [None])[0]
    fav_price = min(value for value in (home, away) if value) if (home or away) else None
    fav_side = "H" if (home or 9) <= (away or 9) else "A"
    home_pos, away_pos = info.get("pos_h"), info.get("pos_a")
    notes = []
    table = bool(home_pos and away_pos and home_pos.get("pos") and away_pos.get("pos") and home_pos.get("tb") == away_pos.get("tb") and home_pos.get("p"))
    if table and re.search(r"Cup|Copa|Coupe|Pokal|Coppa|Champions|Conference League|Europa", (home_pos.get("tbn") or "") + " " + row.get("lg", ""), re.I):
        table = False
        notes.append("cup table not used")
    if table:
        size = home_pos["n"]
        gap = abs(home_pos["pos"] - away_pos["pos"])
        ppg_gap = abs(_ppg(home_pos) - _ppg(away_pos))
        stronger = "H" if (_ppg(home_pos), -home_pos["pos"]) > (_ppg(away_pos), -away_pos["pos"]) else "A"
        top5 = home_pos["pos"] <= 5 and away_pos["pos"] <= 5 and size >= 8
        bottom3 = home_pos["pos"] > size - 3 and away_pos["pos"] > size - 3 and size >= 8
    else:
        size = gap = None
        top5 = bottom3 = False
        if info.get("h") and info.get("a"):
            ppg_gap = abs(info["h"]["ppg"] - info["a"]["ppg"])
            stronger = "H" if info["h"]["ppg"] >= info["a"]["ppg"] else "A"
        else:
            ppg_gap = stronger = None
    big = (ppg_gap is not None and ppg_gap >= 0.6) or (gap is not None and size and gap >= size / 3)
    if big and fav_price and fav_price <= 1.70 and stronger == fav_side:
        kind = "mismatch"
    elif fav_price and fav_price > 1.80 and (ppg_gap is None or ppg_gap < 0.4) and (gap is None or (size and gap < size / 4)):
        kind = "even"
    else:
        kind = "middle"
    return kind, top5, bottom3, table


def _h2h_scores(info):
    found = []
    for line in info.get("h2h") or []:
        match = re.search(r"(\d+)-(\d+)", line)
        if match:
            found.append((int(match.group(1)), int(match.group(2))))
    return found


def side_eval(info: dict, side: str, double_chance: bool):
    own, other = (info.get("h"), info.get("a")) if side == "H" else (info.get("a"), info.get("h"))
    own_venue, other_venue = (info.get("hh"), info.get("aa")) if side == "H" else (info.get("aa"), info.get("hh"))
    own_pos, other_pos = (info.get("pos_h"), info.get("pos_a")) if side == "H" else (info.get("pos_a"), info.get("pos_h"))
    if not own or not other:
        return "Disagree", "couldn't verify form", 0
    hits = 0
    hits += own["ppg"] - other["ppg"] >= (0.3 if double_chance else 0.5)
    hits += own["last5"].count("L") <= (2 if double_chance else 1) and own["last5"].count("W") >= (2 if double_chance else 3)
    if own_venue and other_venue:
        hits += own_venue["ppg"] >= other_venue["ppg"] + (0.2 if double_chance else 0.5)
    table_ok = None
    if own_pos and other_pos and own_pos.get("pos") and other_pos.get("pos"):
        table_ok = own_pos["pos"] < other_pos["pos"]
        hits += bool(table_ok)
    need = 3 if table_ok is not None else 2.5
    verdict = "Agree" if hits >= need else "Lean" if hits >= 2 else "Disagree"
    return verdict, f"PPG L10 {own['ppg']} v {other['ppg']}", hits


def _goals(form):
    return (form["gf"] + form["ga"]) if form else None


def check_market(row: dict, key: str, info: dict):
    if key == "1||Home":
        return side_eval(info, "H", False)
    if key == "1||Away":
        return side_eval(info, "A", False)
    if key == "10||Home or Draw":
        return side_eval(info, "H", True)
    if key == "10||Draw or Away":
        return side_eval(info, "A", True)
    home, away = info.get("h"), info.get("a")
    if not home or not away:
        return "Disagree", "couldn't verify form", 0
    if key.startswith("18|total=1.5"):
        total = (_goals(home) + _goals(away)) / 2
        venue = (_goals(info.get("hh")) + _goals(info.get("aa"))) / 2 if info.get("hh") and info.get("aa") else total
        xg = sum(row["xg"]) if row.get("xg") else None
        last = (row.get("l10") or {}).get("Over 1.5 Goals")
        scores = _h2h_scores(info)
        hits = 0
        hits += last is not None and min(last) >= 7
        hits += xg is not None and xg >= 2.4
        hits += (sum(x + y >= 2 for x, y in scores) >= 2) if len(scores) >= 2 else 0
        core = min(total, venue) >= 2.6
        verdict = "Agree" if core and hits >= 2 else "Lean" if min(total, venue) >= 2.3 and hits >= 1 else "Disagree"
        return verdict, f"avg match goals L10 {total:.2f}", hits + core
    if key.startswith("18|total=3.5"):
        total = (_goals(home) + _goals(away)) / 2
        venue = (_goals(info.get("hh")) + _goals(info.get("aa"))) / 2 if info.get("hh") and info.get("aa") else total
        xg = sum(row["xg"]) if row.get("xg") else None
        scores = _h2h_scores(info)
        heavy = sum(x + y >= 4 for x, y in scores)
        ok = max(total, venue) <= 2.6 and (xg is None or xg <= 2.7) and heavy <= 1
        verdict = "Agree" if ok else "Lean" if max(total, venue) <= 3.0 else "Disagree"
        return verdict, f"avg match goals L10 {total:.2f}", 0
    if key == "29||Yes":
        xg = row.get("xg")
        last = (row.get("l10") or {}).get("Both Teams Scored")
        scores = _h2h_scores(info)
        core = home["gf"] >= 1.2 and away["gf"] >= 1.2 and home["ga"] >= 1.0 and away["ga"] >= 1.0
        venue_ok = info.get("hh") and info.get("aa") and info["hh"]["gf"] >= 1.0 and info["aa"]["gf"] >= 1.0
        hits = 0
        hits += last is not None and min(last) >= 5
        hits += xg is not None and min(xg) >= 1.1
        hits += (sum(x > 0 and y > 0 for x, y in scores) >= 2) if len(scores) >= 2 else 0
        verdict = "Agree" if core and venue_ok and hits >= 2 else "Lean" if core and hits >= 1 else "Disagree"
        return verdict, "GG form", hits + bool(core) + bool(venue_ok)
    if key.startswith("19|") or key.startswith("20|"):
        side = "H" if key.startswith("19|") else "A"
        own, other = (home, away) if side == "H" else (away, home)
        venue = info.get("hh") if side == "H" else info.get("aa")
        xg = row["xg"][0 if side == "H" else 1] if row.get("xg") else None
        ok = own["gf"] >= 1.2 and other["ga"] >= 1.0 and (not venue or venue["gf"] >= 1.0) and (xg is None or xg >= 1.0)
        return ("Agree" if ok else "Lean"), "team to score", 0
    return "Disagree", "unsupported market", 0


def keys_for(row: dict, kind: str):
    free = (row.get("free") or "").lower()
    if free:
        if "maximum 3" in free:
            return ["18|total=3.5|Under 3.5"], False, None
        if "wins or draw" in free or "or draw" in free:
            return ["10||Home or Draw" if free.startswith("home") or "home" in free[:12] else "10||Draw or Away"], False, None
        if "team wins" in free or free.strip() in {"home", "away", "1", "2"}:
            return None, True, "1||Home" if "home" in free else "1||Away"
        if "away team scores" in free:
            return ["20|total=0.5|Over 0.5"], False, None
        if "home team scores" in free:
            return ["19|total=0.5|Over 0.5"], False, None
        if "both teams" in free:
            return ["29||Yes"], False, None
        if "at least 2" in free or "minimum 2" in free or "at least 3" in free:
            return ["18|total=1.5|Over 1.5"], False, None
    kind_name = row.get("typ")
    if kind_name == "1X2":
        return None, True, "1||Home" if row.get("fav") == "H" else "1||Away"
    if kind_name == "BTTS":
        return ["29||Yes"], False, None
    xg = sum(row["xg"]) if row.get("xg") else 0
    return (["18|total=1.5|Over 1.5"] if xg >= 2.3 else ["18|total=3.5|Under 3.5"]), False, None


def decide(row: dict, info: dict | None) -> dict:
    """Attach verdict / key. 1X2 becomes GG, or GG/Over 1.5 when the game is a mismatch."""
    women = row.get("women") or bool(WOMEN.search(f"{row.get('m')} {row.get('lg')}"))
    if women:
        row.update(verdict="Skip", skipwhy="women's match", key=None)
        return row
    if not info or not info.get("h") or not info.get("a"):
        row.update(verdict="Disagree", key=None, check="couldn't verify (no form data)")
        return row
    kind, top5, bottom3, table = classify(row, info)
    row["cls"], row["tab"] = kind, table
    if top5 or bottom3:
        row.update(verdict="Skip", skipwhy="both teams in league top 5" if top5 else "both teams in league bottom 3", key=None)
        return row
    keys, convert, base = keys_for(row, kind)
    if keys is None:
        convert = True
        keys = ["29||Yes", "18|total=1.5|Over 1.5"] if kind == "mismatch" else ["29||Yes"]
    allowed = [key for key in keys if key in ALLOW[kind]]
    barred = [key for key in keys if key not in ALLOW[kind]]
    scored = []
    for key in allowed:
        if key not in row["O"]:
            continue
        verdict, text, score = check_market(row, key, info)
        scored.append((verdict, key, text, score, row["O"][key][0], row["O"][key][1]))
    row["conv"] = convert
    row["base"] = base
    if not scored:
        row.update(verdict="Skip" if barred and not allowed else "Disagree",
                   skipwhy=("rule: " + ", ".join(NAME.get(key, key) for key in barred) + f" not allowed in {kind} game") if barred and not allowed else "no market on SportyBet",
                   key=None)
        return row
    rank = {"Agree": 2, "Lean": 1, "Disagree": 0}
    verdict, key, text, score, odd, oid = max(scored, key=lambda item: (rank[item[0]], item[3], item[4] >= 1.20, item[1].startswith("18")))
    if convert and base:
        base_verdict = side_eval(info, "H" if base == "1||Home" else "A", False)
        text = f"[NT {NAME.get(base, base)} -> converted ({kind} game, options {'GG/O1.5' if kind == 'mismatch' else 'GG only'}); my check on the win itself: {base_verdict[0]}] " + text
        book_fav = "H" if row["O"].get("1||Home", [9])[0] <= row["O"].get("1||Away", [9])[0] else "A"
        if (base == "1||Home" and book_fav != "H") or (base == "1||Away" and book_fav != "A"):
            text += " [SB favourite differs from NT pick]"
    row.update(verdict=verdict, key=key, check=text, od=odd, oid=oid, tip=NAME.get(key, key), score=score)
    if not table and verdict == "Agree" and (row.get("trust") or 0) < 8:
        row["verdict"] = "Lean"
        row["check"] += " [table unverified and trust <8 -> downgraded]"
    return row


def book_filters(row: dict, usage_count: int) -> dict:
    """Forensics from book10.py. Agree legs that fail here are not booked."""
    if row.get("verdict") != "Agree":
        return row
    home, away = (row.get("m") or " v ").split(" v ", 1) if " v " in (row.get("m") or "") else ("", "")
    if YOUTH_TEAM.search(home) or YOUTH_TEAM.search(away):
        row.update(verdict="Skip", skipwhy="reserve/B team")
    elif usage_count >= 2:
        row.update(verdict="Skip", skipwhy="already on 2 other codes")
    elif not row.get("tab"):
        row.update(verdict="Skip", skipwhy="table unchecked")
    elif "[SB favourite differs" in (row.get("check") or ""):
        row.update(verdict="Skip", skipwhy="flagged: SB favourite differs from NT pick")
    elif row.get("key") == "29||Yes" and (row.get("od") or 0) > 1.50:
        row.update(verdict="Skip", skipwhy=f"GG @{row.get('od')} above the 1.50 GG cap")
    elif row.get("warn"):
        row.update(verdict="Skip", skipwhy="flagged by a NerdyTips warning: " + " / ".join(row["warn"]))
    elif (row.get("od") or 0) > 1.75:
        row.update(verdict="Skip", skipwhy=f"odds {row.get('od')} above 1.75 cap")
    elif (row.get("od") or 0) < 1.20:
        row.update(verdict="Skip", skipwhy=f"odds {row.get('od')} below 1.20")
    return row


def _form_from_lastx(lastx, uid, before, venue=None):
    matches = [
        match for match in (lastx or {}).get("matches") or []
        if (match.get("result") or {}).get("home") is not None and match.get("time", {}).get("uts", 0) < before - 3600
    ]
    matches.sort(key=lambda match: -match["time"]["uts"])
    if venue is not None:
        matches = [match for match in matches if (match["teams"]["home"]["uid"] == uid) == venue]
    matches = matches[:10]
    if not matches:
        return None
    sequence = ""
    scored = conceded = 0
    for match in matches:
        home = match["teams"]["home"]["uid"] == uid
        gf, ga = (match["result"]["home"], match["result"]["away"]) if home else (match["result"]["away"], match["result"]["home"])
        scored += gf
        conceded += ga
        sequence += "W" if gf > ga else "D" if gf == ga else "L"
    return {"n": len(matches), "ppg": round((3 * sequence.count("W") + sequence.count("D")) / len(matches), 2),
            "gf": round(scored / len(matches), 2), "ga": round(conceded / len(matches), 2), "last5": sequence[:5]}


def independent(event_id: str, cache: dict) -> dict | None:
    match = lib.sr_get("stats_match_get/" + event_id.split(":")[-1], cache)
    if not match or "teams" not in match:
        return None
    before = match["time"]["uts"]
    home_uid = match["teams"]["home"]["uid"]
    away_uid = match["teams"]["away"]["uid"]
    home_last = lib.sr_get(f"stats_team_lastx/{home_uid}", cache) or {}
    away_last = lib.sr_get(f"stats_team_lastx/{away_uid}", cache) or {}
    info = {
        "h": _form_from_lastx(home_last, home_uid, before),
        "a": _form_from_lastx(away_last, away_uid, before),
        "hh": _form_from_lastx(home_last, home_uid, before, True),
        "aa": _form_from_lastx(away_last, away_uid, before, False),
    }
    table = lib.sr_get(f"stats_season_tables/{match.get('_seasonid')}", cache) if match.get("_seasonid") else None
    positions = {}
    for index, block in enumerate((table or {}).get("tables") or []):
        for item in block.get("tablerows") or []:
            uid = item.get("team", {}).get("uid")
            if uid in (home_uid, away_uid) and uid not in positions:
                positions[uid] = {
                    "pos": item.get("pos"), "n": len(block.get("tablerows") or []), "p": item.get("total"),
                    "pts": item.get("pointsTotal"), "tb": index, "tbn": block.get("name"),
                }
    info["pos_h"] = positions.get(home_uid)
    info["pos_a"] = positions.get(away_uid)
    versus = lib.sr_get(f"stats_team_versus/{home_uid}/{away_uid}", cache) or {}
    meetings = [
        played for played in versus.get("matches") or []
        if (played.get("result") or {}).get("home") is not None and played.get("time", {}).get("uts", 0) < before - 3600
    ]
    meetings.sort(key=lambda played: -played["time"]["uts"])
    info["h2h"] = [
        f"{played['teams']['home']['name']} {played['result']['home']}-{played['result']['away']} {played['teams']['away']['name']}"
        for played in meetings[:3]
    ]
    return info


def _choose_type(detail: dict) -> tuple[str, float, bool]:
    visible = [("1X2", detail.get("c_1x2")), ("Goals", detail.get("c_tg")), ("BTTS", detail.get("c_btts")), ("BB", detail.get("c_bb"))]
    best = detail.get("c_best") or 0
    winners = [name for name, value in visible if value == best and value]
    if winners:
        return winners[0], best, False
    name, value = max(visible, key=lambda item: item[1] or 0)
    return name, value or 0, True


def fetch_tomorrow_html() -> str:
    import subprocess
    cmd = ["curl", "-sS", "-m", "40", "-A", lib.UA, "-b", "tz_offset_v2=0", "https://nerdytips.com/all-matches?d=1"]
    html = subprocess.run(cmd, capture_output=True, text=True).stdout or ""
    keys = re.findall(r'data-lg-k="([^"]+)"', html)
    for offset in range(0, len(keys), 20):
        group = ",".join(keys[offset:offset + 20])
        payload = lib.http_json(
            "https://nerdytips.com/all-matches/rows?d=1&g=" + group,
            headers=UA_HEADERS + ["Cookie: tz_offset_v2=0"],
        )
        if not payload.get("ok"):
            continue
        for value in (payload.get("groups") or {}).values():
            html += "\n" + (value if isinstance(value, str) else json.dumps(value))
    return html


def fetch_detail(url: str) -> str:
    import subprocess
    return subprocess.run(
        ["curl", "-sS", "-m", "30", "-A", lib.UA, "-b", "tz_offset_v2=0", url],
        capture_output=True, text=True,
    ).stdout or ""


def run(repo: Path, dry_run: bool = False, day: dt.date | None = None) -> dict:
    anonymous_note = (
        "Fetched the public Tomorrow board and public match pages with no account. "
        "tz_offset_v2=0 is a timezone cookie so kickoffs stay on GMT, not a login. "
        "A match page with no /10 confidence is skipped. No password or session cookie is stored. "
        "If NerdyTips starts hiding confidence, xG or form behind a signed-in account, this job books nothing."
    )
    html = fetch_tomorrow_html()
    listed = parse_list(html)
    details = {}
    with ThreadPoolExecutor(8) as pool:
        pages = list(pool.map(lambda row: (row["id"], fetch_detail(row["url"])) if row.get("url") else (row["id"], ""), listed))
    for ident, page in pages:
        if page:
            details[ident] = parse_detail(page)
    # Fixture date is whatever the Tomorrow pages say. Fall back to the night-job date.
    dates = [item["date"] for item in details.values() if item.get("date")]
    target = day or (Counter(dates).most_common(1)[0][0] if dates else lib.nightly_target())
    fixtures = []
    now_ms = dt.datetime.now(dt.timezone.utc)
    for event in lib.fetch_upcoming("1,10,18,19,20,29"):
        kick = lib.event_kick(event)
        if not kick or kick.date() != target or kick <= now_ms + dt.timedelta(minutes=10):
            continue
        country, league = lib.league_of(event)
        if "srl" in league.lower() or "simulated" in league.lower():
            continue
        fixtures.append({
            "eid": event.get("eventId"), "ko": int(event.get("estimateStartTime") or 0),
            "kick": kick.strftime("%H:%M"), "home": event.get("homeTeamName"), "away": event.get("awayTeamName"),
            "league": league, "country": country, "O": lib.event_odds(event), "event": event,
        })
    usage = lib.load_usage(repo, target.isoformat())
    cache = {}
    pooled = []
    skipped = Counter()
    for row in listed:
        detail = details.get(row["id"]) or {}
        home = detail.get("home") or row.get("home")
        away = detail.get("away") or row.get("away")
        if not home or not away:
            skipped["no names"] += 1
            continue
        if detail.get("date") and detail["date"] != target:
            skipped["not the Tomorrow date"] += 1
            continue
        typ, trust, hidden = _choose_type(detail)
        if trust < TRUST_MIN and not (row.get("trust") or 0) >= TRUST_MIN:
            skipped["NT trust below 5.0"] += 1
            continue
        trust = trust if trust >= TRUST_MIN else row.get("trust") or trust
        name = f"{home} v {away}"
        league = row.get("league") or ""
        if YOUTH_TEAM.search(name) or YOUTH_LEAGUE.search(league):
            skipped["youth/reserve"] += 1
            continue
        joined = match_fixture({"home": home, "away": away, "kick": row.get("kick")}, fixtures)
        if not joined:
            skipped["no SportyBet match"] += 1
            continue
        if YOUTH_TEAM.search(f"{joined['home']} v {joined['away']}") or YOUTH_LEAGUE.search(joined["league"]):
            skipped["youth/reserve"] += 1
            continue
        nt_odds = [row.get("o1"), row.get("ox"), row.get("o2")]
        if None in nt_odds:
            nt_odds = [joined["O"].get("1||Home", [None])[0], joined["O"].get("1||Draw", [None])[0], joined["O"].get("1||Away", [None])[0]]
        if None in nt_odds:
            skipped["no 1X2"] += 1
            continue
        pooled.append({
            "eid": joined["eid"], "kick": joined["kick"], "ko": joined["ko"],
            "m": f"{joined['home']} v {joined['away']}", "lg": joined["league"],
            "trust": trust, "hidden": hidden, "typ": typ, "free": detail.get("free") or row.get("tip"),
            "fav": "H" if nt_odds[0] <= nt_odds[2] else "A",
            "xg": detail.get("xg"), "l10": detail.get("l10"), "warn": detail.get("warnings") or [],
            "women": bool(WOMEN.search(name + " " + league + " " + joined["league"])),
            "O": {key: joined["O"][key] for key in KEEP_KEYS if joined["O"].get(key)},
            "event": joined["event"],
        })
    verdicts = []
    for row in pooled:
        info = independent(row["eid"], cache)
        decide(row, info)
        book_filters(row, len(usage.get(row["eid"]) or []))
        verdicts.append(row)
    agree = [row for row in verdicts if row.get("verdict") == "Agree" and (row.get("od") or 0) >= 1.20 and row.get("key")]
    agree.sort(key=lambda row: (-row["trust"], -row.get("score", 0), -row["od"]))
    agree = agree[:30]
    # One market per match, and only while the match is still under two codes.
    chosen = []
    seen = set()
    for row in agree:
        if row["eid"] in seen or not lib.can_take(usage, row["eid"]):
            continue
        seen.add(row["eid"])
        chosen.append(row)
    legs = []
    for row in chosen:
        mid, spec, desc = row["key"].split("|", 2)
        kick = dt.datetime.fromtimestamp(row["ko"] / 1000, dt.timezone.utc) if row.get("ko") else None
        legs.append({
            "eventId": row["eid"], "marketId": mid, "specifier": spec or None, "outcomeId": str(row["oid"]),
            "market": row.get("tip") or desc, "selection": "Yes" if row["key"] == "29||Yes" else (desc if desc in {"Over 1.5", "Under 3.5", "Home", "Away"} else row.get("tip") or desc),
            "odds": float(row["od"]), "match": row["m"], "league": row.get("lg"),
            "date": target.isoformat(), "ko": row.get("kick"),
            "kickoff": kick.isoformat().replace("+00:00", "Z") if kick else None,
            "result": "pending", "matchStatus": "Not start", "tableChecked": bool(row.get("tab")),
            "trust": row["trust"], "strategy": CODE_ID, "converted": bool(row.get("conv")),
        })
    # Team-to-score labels need the "over N goals" shape so the existing settler can grade them.
    for leg in legs:
        if leg["marketId"] in {"19", "20"} and "goals" not in leg["selection"].lower():
            side = leg["match"].split(" v ")[0 if leg["marketId"] == "19" else 1]
            leg["selection"] = f"{side} over 0.5 goals"
        if leg["selection"] in {"Home or draw (1X)", "Draw or away (X2)"}:
            leg["selection"] = "Home or Draw" if leg["marketId"] == "10" and "Home" in leg["selection"] else leg["selection"]
            if "Draw or away" in leg["market"] or leg["selection"].startswith("Draw or away"):
                leg["selection"] = "Draw or Away"
            elif "Home or draw" in leg["market"] or "Home or draw" in leg["selection"]:
                leg["selection"] = "Home or Draw"
    packed, why = lib.pack_slip(legs, cap=30)
    result = {"code": None, "reason": why, "n": len(packed), "total": round(lib.product(leg["odds"] for leg in packed), 4) if packed else 0, "legs": packed}
    if packed and not dry_run:
        booked = lib.book_confirmed(packed)
        result.update(booked)
        if booked.get("code"):
            for leg in booked["legs"]:
                lib.take(usage, leg["eventId"], booked["code"])
            lib.publish_high_odds(repo, lib.public_slip(CODE_ID, target.isoformat(), booked["code"], booked["legs"], booked["total"]))
            lib.save_usage(repo, target.isoformat(), usage)
    elif dry_run and packed:
        result["dryRun"] = True
    payload = {
        "strategy": CODE_ID,
        "date": target.isoformat(),
        "anonymous": anonymous_note,
        "listed": len(listed),
        "details": len(details),
        "fixtures": len(fixtures),
        "pooled": len(pooled),
        "skipped": dict(skipped),
        "agree": len(agree),
        "booked": {k: v for k, v in result.items() if k != "legs"} | {"n": len(result.get("legs") or [])},
        "legs": result.get("legs") or [],
        "verdicts": [{k: row.get(k) for k in ("m", "trust", "verdict", "tip", "od", "cls", "skipwhy", "key")} for row in verdicts],
        "conflicts": [
            "1X2 picks become GG or Over 1.5. That follows this strategy. It can ignore a straight win the site would book in a major league.",
            "1X/X2 is allowed by the verdict table at whatever price SportyBet shows, including above 1.35. Flagged. The card is marked strategySpec so prune does not delete it for that cap.",
            "Over 1.5 / Under 3.5 are not held to the 1.30 cap, and GG is capped by this strategy at 1.50 rather than the site 1.60 cap.",
            "Obscure leagues are not forced to goals-only beyond the mismatch/middle/even market list. 1X/X2 in an obscure league is a non-goals leg. Flagged.",
            "SportyBet GH only. Under 25 books nothing (this strategy already refused a short ticket; the site would combine it).",
            "At most 30 Agree legs, matching the source booker, not the site 50-leg split onto every bookmaker.",
        ],
    }
    if not dry_run:
        lib.write_record(repo, CODE_ID, target.isoformat(), payload)
    print(json.dumps({
        "nt": target.isoformat(), "listed": len(listed), "pooled": len(pooled),
        "verdicts": dict(Counter(row.get("verdict") for row in verdicts)),
        "skips": dict(Counter(row.get("skipwhy") for row in verdicts if row.get("skipwhy"))),
        "agree": len(agree), "chosen": len(chosen), "booked": result.get("code") or result.get("reason"), "dry": dry_run,
    }, default=str))
    return payload


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--repo")
    args = parser.parse_args(argv)
    repo = Path(args.repo) if args.repo else lib.repo_root()
    day = dt.date.fromisoformat(args.date) if args.date else None
    run(repo, dry_run=args.dry_run, day=day)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
