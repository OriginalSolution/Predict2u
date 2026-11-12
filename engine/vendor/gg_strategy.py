#!/usr/bin/env python3
"""Nightly SportyBet GG / BTTS-Yes strategy.

Odds screen from live_gg_scan.py (GG 1.20–1.55, Over 2.5 1.60–1.69,
Over 1.5 1.15–1.20, draw above 3.50, both 1X2 prices present).
Stats screen from st.py + tier.py + filt2.py. Books BTTS Yes only.

SportyBet Ghana share code only. Combined price must be at least 25 or
nothing is booked. No padding. A match already on 2 codes is left out.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parent)]
import strategy_lib as lib

CODE_ID = "gg"


def odds_pass(prices: dict, relaxed: bool = False) -> dict | None:
    """Return the screened prices, or None when the exact band misses.

    A thin-day rerun drops only the 1.20 GG floor and the 1.55 GG cap.
    The Over 2.5, Over 1.5 and draw bands stay.
    """
    gg = prices.get("29||Yes")
    over25 = prices.get("18|total=2.5|Over 2.5")
    over15 = prices.get("18|total=1.5|Over 1.5")
    home = prices.get("1||Home")
    draw = prices.get("1||Draw")
    away = prices.get("1||Away")
    if not all([gg, over25, over15, home, draw, away]):
        return None
    g, o25, o15, h, d, a = gg[0], over25[0], over15[0], home[0], draw[0], away[0]
    gg_ok = g > 1.0 if relaxed else (1.20 <= g <= 1.55)
    if not (gg_ok and 1.60 <= o25 <= 1.69 and 1.15 <= o15 <= 1.20 and d > 3.50):
        return None
    return {
        "gg": g, "o25": o25, "o15": o15, "home_odds": h, "draw": d, "away_odds": a,
        "away_fav": bool(a < h), "gg_outcome_id": str(gg[1]),
    }


def league_tier(current: tuple[int, int, int] | None, previous: tuple[int, int, int] | None = None) -> dict | None:
    """Blend this season with the previous one until 60 matches, then label the league.

    current/previous = (matches, goals, both-teams-scored count).
    high: goals/match >= 2.90, or >= 2.75 with a GG rate >= 0.55.
    low: goals/match <= 2.50. Otherwise mid.
    """
    if not current or current[0] <= 0:
        return None
    n, goals, gg = current
    weight = min(1.0, n / 60.0)
    if previous and previous[0] > 0 and weight < 1:
        gpg = weight * goals / n + (1 - weight) * previous[1] / previous[0]
        ggr = weight * gg / n + (1 - weight) * previous[2] / previous[0]
    else:
        gpg = goals / n
        ggr = gg / n
    if gpg >= 2.90 or (gpg >= 2.75 and ggr >= 0.55):
        tier = "high"
    elif gpg <= 2.50:
        tier = "low"
    else:
        tier = "mid"
    return {"n": n, "gpg": round(gpg, 2), "gg_rate": round(ggr, 3), "tier": tier}


def filter_rows(rows: list[dict], scored5, relaxed: bool = False) -> dict:
    """filt2.py keep / watch / drop. `scored5(row)` -> [home_scored_in_last5, away_scored_in_last5].

    A thin-day rerun keeps a row whose league table could not be checked.
    Top-5 and bottom-3 still drop when the two clubs share a table.
    """
    keep, watch, removed, samples = [], [], {}, {}

    def drop(key, name):
        removed[key] = removed.get(key, 0) + 1
        samples.setdefault(key, []).append(name)

    for row in rows:
        name = f"{row.get('home')} v {row.get('away')}"
        blob = " ".join([str(row.get("country") or ""), str(row.get("league") or ""), str(row.get("home") or ""), str(row.get("away") or "")])
        if lib.YOUTH_RE.search(blob) or lib.BAD_TEAM_RE.search(row.get("home") or "") or lib.BAD_TEAM_RE.search(row.get("away") or ""):
            drop("women/youth/reserve/simulated", name)
            continue
        fav = min(row["home_odds"], row["away_odds"])
        dog = max(row["home_odds"], row["away_odds"])
        row["fav"] = fav
        tier = row.get("tier") or "unknown"
        if row.get("nodata") or tier == "unknown":
            drop("no stats data", name)
            continue
        if fav < 1.50 or dog >= 7.0 or row["draw"] >= 4.50:
            drop("always-exclude (fav<1.50/dog>=7/draw>=4.50)", name)
            continue
        cond = fav >= 1.80 or row["draw"] < 4.00
        if tier == "high":
            drop("high-scoring league", name)
            continue
        if tier == "low":
            if cond:
                watch.append(row)
            drop("low-scoring league" + (" (watch-list)" if cond else ""), name)
            continue
        if not cond:
            drop("fav<1.80 and draw>=4.00", name)
            continue
        if min(row.get("home_n") or 0, row.get("away_n") or 0) < 8:
            drop("<8 games data", name)
            continue
        if min(row.get("home_gpg") or 0, row.get("away_gpg") or 0) < 1.3:
            drop("last-10 goals <1.3", name)
            continue
        home_pos, away_pos = row.get("home_pos"), row.get("away_pos")
        shared = bool(home_pos and away_pos and home_pos[2] == away_pos[2])
        if not shared:
            if not relaxed:
                drop("table unchecked", name)
                continue
        else:
            if home_pos[0] <= 5 and away_pos[0] <= 5:
                drop("top-5 v top-5", name)
                continue
            if home_pos[0] > home_pos[1] - 3 and away_pos[0] > away_pos[1] - 3:
                drop("bottom-3 v bottom-3", name)
                continue
        if row.get("away_fav"):
            drop("away favourite", name)
            continue
        try:
            last = scored5(row)
        except Exception:
            last = None
        row["scored5"] = last
        if not last or min(last) < 4:
            drop("both-score evidence <4/5", name)
            continue
        if int(row.get("other_codes") or 0) >= 2:
            drop("already on 2 other codes", name)
            continue
        keep.append(row)
    return {"keep": keep, "watch": watch, "removed": removed, "samples": samples}


def _finished(matches, before_uts):
    rows = [
        match for match in matches or []
        if (match.get("result") or {}).get("home") is not None
        and match.get("time", {}).get("uts", 0) < before_uts - 3600
        and not match.get("canceled")
    ]
    rows.sort(key=lambda match: -match["time"]["uts"])
    return rows


def attach_stats(row: dict, cache: dict) -> None:
    try:
        match = lib.sr_get("stats_match_get/" + row["event_id"].split(":")[-1], cache)
        if not match or "teams" not in match:
            row["nodata"] = "no match"
            return
        kick = match["time"]["uts"]
        row["sid"] = match.get("_seasonid")
        row["utid"] = match.get("_utid")
        table = lib.sr_get(f"stats_season_tables/{row['sid']}", cache) if row.get("sid") else None
        for side in ("home", "away"):
            uid = match["teams"][side]["uid"]
            lastx = lib.sr_get(f"stats_team_lastx/{uid}", cache) or {}
            recent = _finished(lastx.get("matches"), kick)[:10]
            scored = sum(
                match_row["result"]["home"] if match_row["teams"]["home"]["uid"] == uid else match_row["result"]["away"]
                for match_row in recent
            )
            pos = None
            if table and table.get("tables"):
                for block in table["tables"]:
                    for item in block.get("tablerows") or []:
                        if item.get("team", {}).get("uid") == uid:
                            pos = (item.get("pos"), len(block.get("tablerows") or []), block.get("name"))
            row[f"{side}_n"] = len(recent)
            row[f"{side}_gpg"] = round(scored / len(recent), 2) if recent else None
            row[f"{side}_pos"] = pos
            row[f"_{side}_uid"] = uid
            row["_ko"] = kick
    except Exception as exc:
        row["nodata"] = str(exc)[:80]


def season_goals(sid, cache: dict):
    data = lib.sr_get(f"stats_season_fixtures2/{sid}/1", cache)
    if not data:
        return None
    matches = [
        match for match in data.get("matches") or []
        if (match.get("result") or {}).get("home") is not None and not match.get("canceled")
    ]
    if not matches:
        return None
    goals = sum(match["result"]["home"] + match["result"]["away"] for match in matches)
    both = sum(1 for match in matches if match["result"]["home"] > 0 and match["result"]["away"] > 0)
    return len(matches), goals, both


def attach_tier(row: dict, cache: dict, memo: dict) -> None:
    sid = row.get("sid")
    if row.get("nodata") or not sid:
        return
    if sid in memo:
        row.update(memo[sid])
        return
    current = season_goals(sid, cache)
    if not current:
        return
    counts = {}
    match = lib.sr_get("stats_match_get/" + row["event_id"].split(":")[-1], cache) or {}
    for side in ("home", "away"):
        uid = (match.get("teams") or {}).get(side, {}).get("uid")
        if not uid:
            continue
        lastx = lib.sr_get(f"stats_team_lastx/{uid}/30", cache) or lib.sr_get(f"stats_team_lastx/{uid}", cache) or {}
        for played in lastx.get("matches") or []:
            other = played.get("_seasonid")
            if other and int(other) != int(sid) and played.get("_utid") == row.get("utid"):
                counts[other] = counts.get(other, 0) + 1
    previous = None
    if counts:
        previous_id = max(counts, key=lambda item: int(item))
        previous = season_goals(previous_id, cache)
    tier = league_tier(current, previous)
    if not tier:
        return
    memo[sid] = tier
    row.update(tier)


def scored_last5(row: dict, cache: dict) -> list[int]:
    out = []
    kick = row.get("_ko")
    for side in ("home", "away"):
        uid = row.get(f"_{side}_uid")
        lastx = lib.sr_get(f"stats_team_lastx/{uid}", cache) or {}
        recent = _finished(lastx.get("matches"), kick or 0)[:5]
        out.append(sum(
            1 for match in recent
            if (match["result"]["home"] if match["teams"]["home"]["uid"] == uid else match["result"]["away"]) > 0
        ))
    return out


def to_leg(row: dict, day: str) -> dict:
    kick = row.get("kickoff_gmt")
    return {
        "eventId": row["event_id"],
        "marketId": "29",
        "specifier": None,
        "outcomeId": str(row["gg_outcome_id"]),
        "market": "GG",
        "selection": "Yes",
        "odds": float(row["gg"]),
        "match": f"{row['home']} v {row['away']}",
        "home": row["home"],
        "away": row["away"],
        "league": f"{row.get('country') or ''} - {row.get('league') or ''}".strip(" -"),
        "country": row.get("country"),
        "date": day,
        "ko": kick,
        "kickoff": f"{day}T{kick}:00Z" if kick else None,
        "result": "pending",
        "matchStatus": "Not start",
        "tableChecked": True,
        "strategy": CODE_ID,
    }


def scan(day: dt.date, usage: dict, cache: dict | None = None, relaxed: bool = False) -> dict:
    cache = cache if cache is not None else {}
    screened = []
    seen = 0
    for event in lib.fetch_upcoming("1,18,29"):
        kick = lib.event_kick(event)
        if not kick or kick.date() != day:
            continue
        if kick <= dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=10):
            continue
        seen += 1
        country, league = lib.league_of(event)
        home, away = event.get("homeTeamName") or "", event.get("awayTeamName") or ""
        if "srl" in league.lower() or "simulated" in league.lower() or "esoccer" in (country + league).lower():
            continue
        prices = odds_pass(lib.event_odds(event), relaxed=relaxed)
        if not prices:
            continue
        screened.append({
            "date": day.isoformat(),
            "kickoff_gmt": kick.strftime("%H:%M"),
            "country": country,
            "league": league,
            "home": home,
            "away": away,
            "event_id": event.get("eventId"),
            **prices,
        })
    memo = {}
    for row in screened:
        row["other_codes"] = len(usage.get(row["event_id"]) or [])
        attach_stats(row, cache)
        attach_tier(row, cache, memo)
    result = filter_rows(screened, lambda row: scored_last5(row, cache), relaxed=relaxed)
    result["screened"] = len(screened)
    result["seen"] = seen
    return result


def append_log(repo: Path, day: str, legs: list[dict], code: str | None) -> None:
    path = repo / "engine" / "data" / "gg" / "live_gg_log.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = ["date", "kickoff_gmt", "country", "league", "home", "away", "event_id", "gg", "o25", "o15", "draw",
              "home_odds", "away_odds", "away_fav", "booking_code", "score", "gg_hit", "home_gpg_l10", "away_gpg_l10",
              "home_n_l10", "away_n_l10"]
    new = not path.exists()
    with path.open("a", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        if new:
            writer.writeheader()
        for leg in legs:
            writer.writerow({
                "date": day, "kickoff_gmt": leg.get("ko"), "country": leg.get("country"), "league": leg.get("league"),
                "home": leg.get("home"), "away": leg.get("away"), "event_id": leg.get("eventId"),
                "gg": leg.get("odds"), "booking_code": code or "",
            })


def _collect(day: dt.date, usage: dict, relaxed: bool) -> tuple[dict, list[dict]]:
    found = scan(day, usage, relaxed=relaxed)
    legs = []
    for row in found["keep"]:
        if not lib.can_take(usage, row["event_id"]):
            continue
        leg = to_leg(row, day.isoformat())
        home_pos, away_pos = row.get("home_pos"), row.get("away_pos")
        leg["tableChecked"] = bool(home_pos and away_pos and home_pos[2] == away_pos[2])
        if relaxed:
            leg["relaxed"] = True
        legs.append(leg)
    return found, legs


def run(day: dt.date, repo: Path, dry_run: bool = False) -> dict:
    usage = lib.load_usage(repo, day.isoformat())
    found, legs = _collect(day, usage, False)
    parts = lib.chunk_bookable(legs)
    used_relaxed = False
    if not parts:
        found, legs = _collect(day, usage, True)
        parts = lib.chunk_bookable(legs)
        used_relaxed = bool(parts)
    booked = []
    if dry_run:
        for index, part in enumerate(parts, 1):
            booked.append({
                "dryRun": True, "part": index, "n": len(part),
                "total": round(lib.product(leg["odds"] for leg in part), 2),
                "legs": part,
            })
    else:
        for index, part in enumerate(parts, 1):
            result = lib.book_confirmed(part)
            result["part"] = index
            if result.get("code"):
                for leg in result["legs"]:
                    lib.take(usage, leg["eventId"], result["code"])
                slip = lib.public_slip(CODE_ID, day.isoformat(), result["code"], result["legs"], result["total"], index if len(parts) > 1 else None, relaxed=used_relaxed)
                lib.publish_high_odds(repo, slip)
                append_log(repo, day.isoformat(), result["legs"], result["code"])
            booked.append(result)
        lib.save_usage(repo, day.isoformat(), usage)
    payload = {
        "strategy": CODE_ID,
        "date": day.isoformat(),
        "seen": found.get("seen"),
        "screened": found.get("screened"),
        "kept": len(found["keep"]),
        "watch": len(found["watch"]),
        "removed": found["removed"],
        "booked": [{k: v for k, v in row.items() if k != "legs"} | {"n": len(row.get("legs") or [])} for row in booked],
        "relaxed": used_relaxed,
        "qualifying": legs,
        "legs": [leg for row in booked if row.get("code") for leg in (row.get("legs") or [])],
        "conflicts": [
            "SportyBet GH only — standing rule books every no-login bookmaker.",
            "Under 25 books nothing — standing rule combines short codes instead of dropping them.",
            "No single leg cap at 1.30/1.60 — GG prices in this band are about 1.45–1.55.",
            "Obscure leagues stay on GG, which is a goals market, so that veto does not bite.",
            "Away favourites, high-scoring leagues and low-scoring leagues are dropped by the strategy even when a goals pick would pass the site rules.",
        ],
    }
    if not dry_run:
        lib.write_record(repo, CODE_ID, day.isoformat(), payload)
    print(json.dumps({"gg": day.isoformat(), "seen": payload["seen"], "screened": payload["screened"], "kept": payload["kept"], "watch": payload["watch"], "removed": payload["removed"], "parts": len(booked), "dry": dry_run}, default=str))
    return payload


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
