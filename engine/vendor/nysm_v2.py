#!/usr/bin/env python3
"""NYSM decision tree v2 — Main, Conservative and TS2+ slips.

Tree order and definitions follow e_sources/nysm/decision_tree_v2.md and v2tree.py.
TS2+ follows the Team-to-score-2+ section of that note (ts2.py), including the
house band 1.20–1.50, the 75% venue bar (85% in cups), one tip per match,
max two per league, and top-5 / bottom-5 skips.

GG and leaky branches stay off accumulators, as the note says.
A slip is booked only at combined odds of 25 or more. Nothing is padded.
The one-day English non-league name list inside ts2.py is not applied.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parent)]
import strategy_lib as lib

RL = {"Low": 1.50, "Medium": 1.40, "High": 1.60, "Inflated": 2.10}
TH = {
    "SA": (125, 120, 115, 110),
    "EA": (150, 150, 140, 135),
    "LD": (130, 120, 115, 110),
    "VL": (160, 150, 145, 135),
    "O15": (100, 95, 90, 95),
    "O25": (130, 125, 120, 120),
    "U35": (115, 110, 105, 100),
    "RL": (1.50, 1.40, 1.60, 2.10),
    "RVL": (1.80, 1.70, 2.00, 2.50),
}
IX = {"Low": 0, "Medium": 1, "High": 2, "Inflated": 3}
CUP_RE = re.compile(r"cup|copa|coupe|pokal|coppa|trophy", re.I)
TPL = {20: [4, 8, 14, 17, 20], 16: [3, 6, 11, 14, 16], 12: [3, 5, 8, 10, 12], 10: [2, 4, 7, 9, 10], 8: [2, 5, 8]}
TIER5 = ["Elite", "Upper", "Mid", "Lower", "Relegation"]
TIER3 = ["Top", "Upper-mid", "Bottom"]


def table_tier(pos: int, size: int) -> str:
    template = min(TPL, key=lambda width: abs(width - size))
    scaled = max(1, math.ceil(pos * template / max(size, 1)))
    names = TIER3 if template == 8 else TIER5
    for index, bound in enumerate(TPL[template]):
        if scaled <= bound:
            return names[index]
    return names[-1]


def league_class(latg: float) -> str:
    if latg < 2.40:
        return "Low"
    if latg <= 3.00:
        return "Medium"
    if latg <= 3.40:
        return "High"
    return "Inflated"


def thresholds(cls: str) -> dict:
    index = IX[cls]
    return {key: values[index] for key, values in TH.items()}


def tree_pick(row: dict) -> dict | None:
    """One pick for a modelled match, or None. `row` is the v2tree feature dict.

    Keys used: fo, sH, gap, fav, sDef, wAtt, sRaw, sg6, HA, HD, AA, AD, hd, ad,
    ldr, wdr, cls, mk, O (key -> (odds, outcomeId)), DNB (side -> (odds, outcomeId)),
    home, away, women, top5.
    """
    if row.get("top5"):
        return None
    prices = row.get("O") or {}
    home_fav = bool(row.get("sH"))
    side = "Home" if home_fav else "Away"
    name = row["home"] if home_fav else row["away"]
    price = float(row["fo"])
    stronger_def = row.get("sDef")
    weaker_att = row.get("wAtt")
    stronger_raw = row.get("sRaw")
    last6 = row.get("sg6")
    elite = stronger_def is not None and stronger_def <= 70 and last6 is not None and last6 <= 4
    leaky = stronger_def is not None and stronger_def > 100 and stronger_raw is not None and stronger_raw >= RL[row["cls"]]
    can_score = weaker_att is not None and weaker_att >= 85
    very_poor = weaker_att is not None and weaker_att < 70
    draw_heavy = (row.get("ldr") or 0) >= 0.29 or (row.get("wdr") or 0) >= 0.35
    close = row["fav"] < 0.45 or row["gap"] < 0.4
    clear = row["fav"] >= 0.55

    def priced(key):
        found = prices.get(key)
        return (float(found[0]), str(found[1])) if found else None

    def result_pick(branch, force_dnb=False):
        if price <= 1.60 and not force_dnb:
            quote = priced("1||" + side)
            if not quote:
                return None
            return {"pick": f"{name} Win", "key": "1||" + side, "odds": quote[0], "oid": quote[1],
                    "branch": branch, "selection": side, "market": "1X2"}
        quote = (row.get("DNB") or {}).get(side)
        if not quote:
            return None
        return {"pick": f"{name} DNB", "key": "11||" + side, "odds": float(quote[0]), "oid": str(quote[1]),
                "branch": branch, "selection": side, "market": "Draw no bet"}

    def goals(label, key, branch, market):
        quote = priced(key)
        if not quote:
            return None
        return {"pick": label, "key": key, "odds": quote[0], "oid": quote[1], "branch": branch,
                "selection": label, "market": market}

    pick = None
    if price <= 1.40 and very_poor:
        pick = result_pick("1 Short fav v very poor attack")
    elif clear and row["gap"] < 0:
        pick = None
    elif clear:
        if elite:
            pick = result_pick("2A Elite home Win") if home_fav else result_pick("2A Elite away DNB", True)
        elif not home_fav and (row.get("HA") or 0) >= 85:
            pick = result_pick("2 Stronger away v home that can score")
        elif draw_heavy:
            pick = result_pick("2 Draw-heavy weaker, stronger home") if home_fav else None
        elif very_poor:
            pick = result_pick("2 Weaker attack very poor")
        elif leaky:
            if can_score:
                pick = goals("Over 2.5", "18|total=2.5|Over 2.5", "2C Leaky + can score O2.5", "Over/Under")
            else:
                pick = result_pick("2C Leaky + cannot score (single)")
        elif can_score:
            pick = goals("Over 1.5", "18|total=1.5|Over 1.5", "2B Solid + can score O1.5", "Over/Under")
        else:
            pick = result_pick("2B Solid + cannot score")
    elif close:
        if (row.get("ldr") or 0) >= 0.29:
            pick = None
        elif (row.get("HA") or 0) >= 85 and (row.get("AA") or 0) >= 85:
            home_od = (prices.get("1||Home") or [9])[0]
            away_od = (prices.get("1||Away") or [9])[0]
            draw_od = (prices.get("1||Draw") or [9])[0]
            if not (min(home_od, away_od) < 1.50 or max(home_od, away_od) >= 7 or draw_od >= 4.50):
                pick = goals("Yes", "29||Yes", "3 Close, both attack>=85 GG", "GG")
        elif row.get("cls") == "High" and (row.get("HD") or 0) > 100 and (row.get("hd") or 0) >= 1.6 and (row.get("AD") or 0) > 100 and (row.get("ad") or 0) >= 1.6:
            pick = goals("Yes", "29||Yes", "3 Both leaky High GG (watch)", "GG")
    if pick is None:
        market = row.get("mk") or {}
        if (market.get("O15") or 0) >= 0.80 and row.get("cls") != "Low":
            pick = goals("Over 1.5", "18|total=1.5|Over 1.5", "5 Fallback TierA O1.5", "Over/Under")
        elif (market.get("U35") or 0) >= 0.80 and row.get("cls") in ("Low", "Medium"):
            pick = goals("Under 3.5", "18|total=3.5|Under 3.5", "5 Fallback TierA U3.5", "Over/Under")
    if not pick:
        return None
    if row.get("women") and str(pick["key"]).split("|", 1)[0] in {"18", "19", "20", "29"}:
        return None
    pick["eid"] = row.get("eid")
    pick["match"] = f"{row.get('home')} v {row.get('away')}"
    pick["tableChecked"] = not row.get("unverifiedTable")
    return pick


def slip_bucket(branch: str) -> str:
    """Where a tree branch is allowed to sit.

    GG (branch 3) and leaky (branch 2C, including the singles-only line) stay
    off accumulators. Safer branches form the Conservative slip. The rest of
    the accumulator branches form Main. A match is on one of those slips.
    """
    if branch.startswith("3 ") or branch.startswith("2C"):
        return "off"
    if (
        branch.startswith("1 ")
        or "Solid + can score" in branch
        or branch.startswith("5 ")
        or branch.startswith("2 Draw-heavy")
        or (branch.startswith("2A") and "DNB" in branch)
    ):
        return "conservative"
    return "main"


def branch_rank(branch: str) -> int:
    if branch.startswith("1 "):
        return 0
    if "Solid + can score" in branch:
        return 1
    if branch.startswith("5 "):
        return 2
    if branch.startswith("2 Draw-heavy"):
        return 3
    if "Solid + cannot score" in branch:
        return 4
    if branch.startswith("2A"):
        return 5
    return 6


def assign_slips(picks: list[dict]) -> dict[str, list[dict]]:
    """One market per match. Off-accumulator branches are not booked."""
    ordered = sorted(picks, key=lambda pick: (branch_rank(pick["branch"]), pick.get("odds") or 9))
    used = set()
    out = {"nysm-main": [], "nysm-conservative": []}
    for pick in ordered:
        if pick["eid"] in used:
            continue
        bucket = slip_bucket(pick["branch"])
        if bucket == "off":
            continue
        key = "nysm-conservative" if bucket == "conservative" else "nysm-main"
        used.add(pick["eid"])
        out[key].append(pick)
    return out


def ts2_candidates(rows: list[dict], relaxed: bool = False) -> list[dict]:
    """Team Over 1.5 candidates that pass the v2.2 qualify rules and the house band.

    `rows` items need: eid, match, league, HA, AA, HD, AD, hd, ad, nh, na, th (SA/LD/RL),
    same, gap (table positions), hpos, apos, N, home, away, O, bar (side -> (rate, n)), cup.
    """
    found = []
    for row in rows:
        if row.get("women") or row.get("youth"):
            continue
        if (row.get("nh") or 0) < 4 or (row.get("na") or 0) < 4:
            continue
        prices = row.get("O") or {}
        n_teams = row.get("N") or 0
        home_pos, away_pos = row.get("hpos"), row.get("apos")
        if home_pos and away_pos and n_teams:
            if (home_pos <= 5 and away_pos <= 5) or (home_pos > n_teams - 5 and away_pos > n_teams - 5):
                continue
        for side, market_id, attack, opp_def, opp_raw, venue_n in (
            ("home", "19", row.get("HA"), row.get("AD"), row.get("ad"), row.get("nh")),
            ("away", "20", row.get("AA"), row.get("HD"), row.get("hd"), row.get("na")),
        ):
            line = (row.get("th") or {}).get("SA")
            if attack is None or line is None or attack < line:
                continue
            win_key = "1||" + side.title()
            win = (prices.get(win_key) or [9])[0]
            leak_line = (row.get("th") or {}).get("LD")
            raw_line = (row.get("th") or {}).get("RL")
            leak = opp_def is not None and leak_line is not None and opp_def >= leak_line
            raw_leak = opp_raw is not None and raw_line is not None and opp_raw >= raw_line
            if not (leak or win <= 1.90):
                continue
            position_gap = row.get("pos_gap")
            if position_gap is None:
                position_gap = row.get("gap") if row.get("gap") is not None else 99
            tight = bool(row.get("same") or position_gap <= 2)
            other = row.get("AA") if side == "home" else row.get("HA")
            both_strong = other is not None and line is not None and other >= line
            if tight and not both_strong:
                continue
            quote = prices.get(f"{market_id}|total=1.5|Over 1.5")
            if not quote:
                continue
            points = 0
            if (venue_n or 0) < 8:
                points += 2
            if tight:
                points += 1
            if row.get("both_elite"):
                points += 2
            if 1 / float(quote[0]) < 0.50:
                points += 2
            if leak and not raw_leak:
                points += 2
            tier = "A" if points <= 1 else "B" if points <= 3 else "C" if points <= 5 else "NoBet"
            if (venue_n or 0) < 8 and tier == "A":
                tier = "B"
            if tier not in {"A", "B"}:
                continue
            odds = float(quote[0])
            # Thin day: drop the 1.20 floor only. The 1.50 house cap stays.
            if relaxed:
                if not (1.0 < odds <= 1.50):
                    continue
            elif not (1.20 <= odds <= 1.50):
                continue
            bar = (row.get("bar") or {}).get(side)
            rate = None if not bar else bar[0]
            need = 0.85 if row.get("cup") else 0.75
            if rate is None or rate < need:
                continue
            team = row["home"] if side == "home" else row["away"]
            found.append({
                "eid": row["eid"], "match": row.get("match"), "league": row.get("league"),
                "team": team, "side": side, "key": f"{market_id}|total=1.5|Over 1.5",
                "odds": odds, "oid": str(quote[1]), "tier": tier, "pts": points,
                "bar": rate, "branch": f"TS2 {tier}",
                "selection": f"{team} over 1.5 goals", "market": "Team total",
            })
    found.sort(key=lambda item: (0 if item["tier"] == "A" else 1, item["pts"], -item["bar"], item["odds"]))
    per_match, per_league = {}, {}
    kept = []
    for item in found:
        if item["eid"] in per_match:
            continue
        league = item.get("league") or ""
        if per_league.get(league, 0) >= 2:
            continue
        per_match[item["eid"]] = item
        per_league[league] = per_league.get(league, 0) + 1
        kept.append(item)
    return kept


def _implied(prices, over_key, under_key):
    over_p, under_p = prices.get(over_key), prices.get(under_key)
    if not over_p or not under_p:
        return None
    return (1 / over_p[0]) / ((1 / over_p[0]) + (1 / under_p[0]))


def model_match(event: dict, table_rows: list[dict], home_uid, away_uid, ga6: dict, cache_prices: dict | None = None) -> dict | None:
    """Build the feature row the tree reads. Returns None when the table cannot be checked."""
    if not table_rows:
        return None
    by_uid = {row["team"]["uid"]: row for row in table_rows if row.get("team")}
    if home_uid not in by_uid or away_uid not in by_uid:
        return None
    if any("goalsForHome" not in row for row in table_rows):
        return None
    rows = table_rows
    size = len(rows)
    home_played = sum(row.get("home") or 0 for row in rows)
    away_played = sum(row.get("away") or 0 for row in rows)
    if home_played < size or away_played < size:
        return None
    league_home = sum(row.get("goalsForHome") or 0 for row in rows) / home_played
    league_away = sum(row.get("goalsForAway") or 0 for row in rows) / away_played
    latg = league_home + league_away
    if latg <= 0:
        return None
    team_goals = latg / 2
    cls = league_class(latg)
    home, away = by_uid[home_uid], by_uid[away_uid]
    if not home.get("home") or not away.get("away"):
        return None
    ha = home["goalsForHome"] / home["home"]
    hd = home["goalsAgainstHome"] / home["home"]
    aa = away["goalsForAway"] / away["away"]
    ad = away["goalsAgainstAway"] / away["away"]
    prices = cache_prices if cache_prices is not None else lib.event_odds(event)
    if None in (prices.get("1||Home"), prices.get("1||Draw"), prices.get("1||Away")):
        return None
    home_odds, draw_odds, away_odds = prices["1||Home"][0], prices["1||Draw"][0], prices["1||Away"][0]
    overround = 1 / home_odds + 1 / draw_odds + 1 / away_odds
    p_home, p_away = (1 / home_odds) / overround, (1 / away_odds) / overround
    home_is_fav = p_home >= p_away
    fav_prob = max(p_home, p_away)
    home_ppg = home["pointsTotal"] / max(home.get("total") or 1, 1)
    away_ppg = away["pointsTotal"] / max(away.get("total") or 1, 1)
    gap = (home_ppg - away_ppg) * (1 if home_is_fav else -1)
    draws = sum(row.get("drawTotal") or 0 for row in rows)
    played = sum(row.get("total") or 0 for row in rows)
    league_draw = draws / max(played, 1)
    home_draw = (home.get("drawTotal") or 0) / max(home.get("total") or 1, 1)
    away_draw = (away.get("drawTotal") or 0) / max(away.get("total") or 1, 1)
    country, league = lib.league_of(event)
    home_name = event.get("homeTeamName") or ""
    away_name = event.get("awayTeamName") or ""
    top5 = home.get("pos", 99) <= 5 and away.get("pos", 99) <= 5
    dnb = {}
    if prices.get("11||Home"):
        dnb["Home"] = tuple(prices["11||Home"])
    if prices.get("11||Away"):
        dnb["Away"] = tuple(prices["11||Away"])
    return {
        "eid": event.get("eventId"),
        "home": home_name, "away": away_name,
        "league": f"{country} - {league}".strip(" -"),
        "cls": cls, "th": thresholds(cls),
        "fo": home_odds if home_is_fav else away_odds,
        "sH": home_is_fav, "fav": fav_prob, "gap": gap,
        "sDef": (hd if home_is_fav else ad) / team_goals * 100,
        "wAtt": (aa if home_is_fav else ha) / team_goals * 100,
        "sRaw": hd if home_is_fav else ad,
        "sg6": ga6.get(home_uid if home_is_fav else away_uid),
        "HA": ha / team_goals * 100, "HD": hd / team_goals * 100,
        "AA": aa / team_goals * 100, "AD": ad / team_goals * 100,
        "hd": hd, "ad": ad, "nh": home["home"], "na": away["away"],
        "ldr": league_draw, "wdr": away_draw if home_is_fav else home_draw,
        "mk": {
            "O15": _implied(prices, "18|total=1.5|Over 1.5", "18|total=1.5|Under 1.5"),
            "U35": _implied(prices, "18|total=3.5|Under 3.5", "18|total=3.5|Over 3.5"),
        },
        "O": {key: tuple(value) for key, value in prices.items()},
        "DNB": dnb,
        "women": lib.women_match(home_name, away_name, league),
        "youth": lib.youth_or_sim(home_name, away_name, country, league),
        "top5": top5,
        "hpos": home.get("pos"), "apos": away.get("pos"), "N": size,
        "pos_gap": abs((home.get("pos") or 0) - (away.get("pos") or 0)),
        "same": table_tier(home.get("pos") or 1, size) == table_tier(away.get("pos") or 1, size),
        "both_elite": table_tier(home.get("pos") or 1, size) in {"Elite", "Top"} and table_tier(away.get("pos") or 1, size) in {"Elite", "Top"},
        "match": f"{home_name} v {away_name}",
        "cup": bool(CUP_RE.search(league or "")),
        "ko": lib.event_kick(event),
    }


def unverified_price_row(event: dict, prices: dict) -> dict | None:
    """Price-only row when the clubs are not on one checked table. Thin-day only.

    Fav and gap stay in the middle so the tree does not invent a win from a
    missing table. A goals fallback can still fire from the prices.
    """
    if None in (prices.get("1||Home"), prices.get("1||Draw"), prices.get("1||Away")):
        return None
    country, league = lib.league_of(event)
    home_name = event.get("homeTeamName") or ""
    away_name = event.get("awayTeamName") or ""
    dnb = {}
    if prices.get("11||Home"):
        dnb["Home"] = tuple(prices["11||Home"])
    if prices.get("11||Away"):
        dnb["Away"] = tuple(prices["11||Away"])
    return {
        "eid": event.get("eventId"),
        "home": home_name, "away": away_name,
        "league": f"{country} - {league}".strip(" -"),
        "cls": "Medium", "th": thresholds("Medium"),
        "fo": 2.0, "sH": True, "fav": 0.50, "gap": 0.0,
        "sDef": None, "wAtt": None, "sRaw": None, "sg6": None,
        "HA": None, "HD": None, "AA": None, "AD": None,
        "hd": None, "ad": None, "nh": 0, "na": 0,
        "ldr": 0, "wdr": 0,
        "mk": {
            "O15": _implied(prices, "18|total=1.5|Over 1.5", "18|total=1.5|Under 1.5"),
            "U35": _implied(prices, "18|total=3.5|Under 3.5", "18|total=3.5|Over 3.5"),
        },
        "O": {key: tuple(value) for key, value in prices.items()},
        "DNB": dnb,
        "women": lib.women_match(home_name, away_name, league),
        "youth": lib.youth_or_sim(home_name, away_name, country, league),
        "top5": False, "unverifiedTable": True,
        "hpos": None, "apos": None, "N": 0,
        "pos_gap": 99, "same": False, "both_elite": False,
        "match": f"{home_name} v {away_name}",
        "cup": bool(CUP_RE.search(league or "")),
        "ko": lib.event_kick(event),
    }


def _table_pair(match, cache):
    if not match or "teams" not in match:
        return None, None, None
    season = match.get("_seasonid")
    table = lib.sr_get(f"stats_season_tables/{season}", cache) if season else None
    home_uid = match["teams"]["home"]["uid"]
    away_uid = match["teams"]["away"]["uid"]
    block = None
    for candidate in (table or {}).get("tables") or []:
        uids = {row.get("team", {}).get("uid") for row in candidate.get("tablerows") or []}
        if home_uid in uids and away_uid in uids:
            block = candidate.get("tablerows") or []
            break
    return home_uid, away_uid, block


def _ga6(uid, before_uts, cache) -> int | None:
    lastx = lib.sr_get(f"stats_team_lastx/{uid}", cache) or {}
    matches = [
        match for match in lastx.get("matches") or []
        if (match.get("result") or {}).get("home") is not None
        and match.get("time", {}).get("uts", 0) < before_uts
        and not match.get("canceled")
    ]
    matches.sort(key=lambda match: -match["time"]["uts"])
    recent = matches[:6]
    if len(recent) < 6:
        return None
    total = 0
    for match in recent:
        home = match["teams"]["home"]["uid"] == uid
        total += match["result"]["away"] if home else match["result"]["home"]
    return total


def _venue_bar(uid, venue, before_uts, cache):
    lastx = lib.sr_get(f"stats_team_lastx/{uid}/20", cache) or {}
    matches = [
        match for match in lastx.get("matches") or []
        if (match.get("result") or {}).get("home") is not None
        and match.get("time", {}).get("uts", 0) < before_uts
        and match["teams"][venue]["uid"] == uid
        and not match.get("canceled")
    ]
    matches.sort(key=lambda match: -match["time"]["uts"])
    recent = matches[:10]
    if not recent:
        return None
    rate = sum(match["result"][venue] >= 2 for match in recent) / len(recent)
    return rate, len(recent)


def pick_to_leg(event, pick, day: str) -> dict:
    kick = lib.event_kick(event)
    country, league = lib.league_of(event)
    mid, spec, _desc = pick["key"].split("|", 2)
    return {
        "eventId": event.get("eventId") or pick.get("eid"),
        "marketId": mid,
        "specifier": spec or None,
        "outcomeId": str(pick["oid"]),
        "market": pick.get("market"),
        "selection": pick.get("selection"),
        "odds": float(pick["odds"]),
        "match": pick.get("match") or f"{event.get('homeTeamName')} v {event.get('awayTeamName')}",
        "league": f"{country} - {league}".strip(" -"),
        "date": day,
        "ko": kick.strftime("%H:%M") if kick else None,
        "kickoff": kick.isoformat().replace("+00:00", "Z") if kick else None,
        "result": "pending",
        "matchStatus": "Not start",
        "branch": pick.get("branch"),
        "tableChecked": pick.get("tableChecked", True),
        "strategy": pick.get("strategy"),
    }


def run(day: dt.date, repo: Path, dry_run: bool = False) -> dict:
    cache = {}
    usage = lib.load_usage(repo, day.isoformat())
    now = dt.datetime.now(dt.timezone.utc)
    events = []
    for event in lib.fetch_upcoming("1,10,11,18,19,20,29"):
        kick = lib.event_kick(event)
        if not kick or kick.date() != day or kick <= now + dt.timedelta(minutes=10):
            continue
        country, league = lib.league_of(event)
        if lib.youth_or_sim(event.get("homeTeamName") or "", event.get("awayTeamName") or "", country, league):
            continue
        if "srl" in league.lower() or "simulated" in league.lower():
            continue
        events.append(event)

    def _prices_for(event):
        prices = lib.event_odds(event)
        if "11||Home" not in prices or "19|total=1.5|Over 1.5" not in prices:
            detail = lib.http_json(
                f"https://www.sportybet.com/api/gh/factsCenter/event?eventId={event.get('eventId')}&productId=3"
            ).get("data") or {}
            if detail.get("markets"):
                prices = lib.event_odds(detail)
        return prices

    def gather(relaxed: bool):
        """One pass. relaxed keeps an unverified table and drops the TS2 1.20 floor."""
        tree_picks = []
        ts2_rows = []
        skipped = 0
        for event in events:
            match = lib.sr_get("stats_match_get/" + str(event.get("eventId")).split(":")[-1], cache)
            home_uid, away_uid, block = _table_pair(match, cache)
            prices = _prices_for(event)
            before = (match.get("time") or {}).get("uts") if match else None
            before = before or int(kick_ts(event))
            if block and home_uid and away_uid:
                ga6 = {home_uid: _ga6(home_uid, before, cache), away_uid: _ga6(away_uid, before, cache)}
                row = model_match(event, block, home_uid, away_uid, ga6, prices)
            elif relaxed:
                skipped += 1
                row = unverified_price_row(event, prices)
                home_uid = away_uid = None
            else:
                skipped += 1
                continue
            if not row or row.get("youth"):
                skipped += 1
                continue
            if home_uid and away_uid:
                row["bar"] = {
                    "home": _venue_bar(home_uid, "home", before, cache),
                    "away": _venue_bar(away_uid, "away", before, cache),
                }
            pick = tree_pick(row)
            if pick and lib.can_take(usage, row["eid"]):
                pick["event"] = event
                tree_picks.append(pick)
            if lib.can_take(usage, row["eid"]):
                ts2_rows.append(row | {"event": event})
        grouped = assign_slips(tree_picks)
        ts2 = []
        used_ids = {pick["eid"] for bucket in grouped.values() for pick in bucket}
        for cand in ts2_candidates([{k: v for k, v in row.items() if k != "event"} for row in ts2_rows], relaxed=relaxed):
            if cand["eid"] in used_ids or not lib.can_take(usage, cand["eid"]):
                continue
            ts2.append(cand)
        grouped["nysm-ts2"] = ts2
        return grouped, skipped

    def legs_of(picks, slip_id):
        out = []
        for pick in picks:
            event = pick.get("event") or event_by_id.get(pick["eid"]) or {}
            leg = pick_to_leg(event, pick, day.isoformat())
            leg["strategy"] = slip_id
            if lib.can_take(usage, leg["eventId"]):
                out.append(leg)
        return out

    event_by_id = {event.get("eventId"): event for event in events}
    normal_slips, skipped_table = gather(False)
    relaxed_slips = None
    booked = {}
    qualifying = []
    for slip_id in ("nysm-main", "nysm-conservative", "nysm-ts2"):
        normal_legs = legs_of(normal_slips.get(slip_id) or [], slip_id)
        packed, why = lib.pack_slip(normal_legs)
        used_relaxed = False
        if not packed:
            if relaxed_slips is None:
                relaxed_slips, extra_skipped = gather(True)
                skipped_table += extra_skipped
            relaxed_legs = legs_of((relaxed_slips or {}).get(slip_id) or [], slip_id)
            packed, why, used_relaxed = lib.thin_pack(normal_legs, relaxed_legs)
            qualifying.extend(relaxed_legs)
        else:
            qualifying.extend(normal_legs)
        picks = (relaxed_slips or normal_slips).get(slip_id) if used_relaxed else normal_slips.get(slip_id)
        entry = {"id": slip_id, "candidates": len(picks or []), "reason": why, "n": len(packed),
                 "total": round(lib.product(leg["odds"] for leg in packed), 2) if packed else 0,
                 "legs": packed, "relaxed": used_relaxed}
        if packed and not dry_run:
            result = lib.book_confirmed(packed)
            entry.update({k: v for k, v in result.items() if k != "legs"})
            entry["legs"] = result.get("legs") or []
            if result.get("code"):
                for leg in entry["legs"]:
                    lib.take(usage, leg["eventId"], result["code"])
                lib.publish_high_odds(repo, lib.public_slip(
                    slip_id, day.isoformat(), result["code"], entry["legs"], result["total"], relaxed=used_relaxed,
                ))
        elif dry_run and packed:
            entry["dryRun"] = True
        booked[slip_id] = entry
    if not dry_run:
        lib.save_usage(repo, day.isoformat(), usage)
    payload = {
        "strategy": "nysm-v2",
        "date": day.isoformat(),
        "events": len(events),
        "tableUnchecked": skipped_table,
        "relaxed": any(row.get("relaxed") for row in booked.values()),
        "qualifying": qualifying,
        "slips": {key: {k: v for k, v in row.items() if k != "legs"} | {"legs": row.get("legs")} for key, row in booked.items()},
        "conflicts": [
            "Tree Win/DNB is not limited to goals markets, so obscure leagues can carry a result pick. Published with strategySpec so prune keeps the card; flagged against the goals-only rule.",
            "Win is allowed up to 1.60 and DNB can be shorter or longer. The 1.60 extreme-stats cap and the 1.30 Over 1.5 / Under 3.5 cap are not applied.",
            "3–5 legs at the preferred <=1.39 prices cannot reach 25. The full qualifying set is booked, or nothing is. No padding.",
            "Bottom-3 v bottom-3 is not skipped on Main/Conservative (the tree only skips top-5). TS2+ does skip bottom-5.",
            "SportyBet GH only. Under 25 books nothing rather than combining.",
            "GG and leaky branches stay off the accumulators, so they are not booked.",
        ],
    }
    if not dry_run:
        lib.write_record(repo, "nysm", day.isoformat(), payload)
    summary = {key: {"candidates": row["candidates"], "n": row["n"], "total": row["total"], "code": row.get("code"), "reason": row.get("reason")} for key, row in booked.items()}
    print(json.dumps({"nysm": day.isoformat(), "events": len(events), "tableUnchecked": skipped_table, "treePicks": len(tree_picks), "slips": summary, "dry": dry_run}, default=str))
    return payload


def kick_ts(event) -> float:
    kick = lib.event_kick(event)
    return kick.timestamp() if kick else 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--repo")
    args = parser.parse_args(argv)
    day = lib.nightly_target(explicit=args.date)
    repo = Path(args.repo) if args.repo else lib.repo_root()
    run(day, repo, dry_run=args.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
