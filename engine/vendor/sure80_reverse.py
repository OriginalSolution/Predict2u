#!/usr/bin/env python3
"""Nightly 22:00 SportyBet GH strategies: 80% Sure, Reverse U4.5, Reverse U4.5 + Draw rule.

Strategy notes from Betting Strategies (NerdyTips), 19 Nov 2026. Reference log:
8K0AGB, 15 legs @34.14, won 17 Nov.

Common rules (all three):
- SportyBet Ghana share codes only (no-login share endpoint + read-back in strategy_lib.book_confirmed).
- Matches kick off on the target day (the next GMT day when run at 22:00).
- No NG. Max 25 legs per code, at least 25 combined odds per code, up to 2 codes (50 legs) per strategy.
- Never padded: a code that cannot reach 25 odds inside the rules is not booked.
- A match sits on at most 2 codes overall (strategy-usage file shared with GG / NYSM / NT / master).
- Never places a bet. Codes come only from SportyBet's share response.

1) 80% SURE  (code id ``sure80``)
- Legs 1.20-1.45. No double chance, no NG, no GG.
- Markets: team Over 0.5, match O1.5/O2.5, U3.5/U4.5/U5.5, win (1X2), DNB.
- Data estimate > 80% from the last 10 results of each team (scored/conceded,
  goal totals, W/D/L = GF/GA and recent scores) plus head-to-head (>= 3 meetings).
  Win/DNB also need a shared league table with the pick ranked above the opponent.
- Drop top-5 v top-5 and bottom-3 v bottom-3 (shared table only).
- Unders: take the narrowest line whose estimate is clear (>= 85%); a borderline
  narrow line (80-85%) gives way to the wider line.
- LEAGUE-FIT: the price must be <= LEAGUE_FIT_RATIO x the median price of the same
  market in the same league that day (other fixtures, at least LEAGUE_FIT_MIN_N).
  With fewer comparables the leg must be <= LEAGUE_FIT_FALLBACK_MAX.

2) REVERSE U4.5  (``rev-u45``)
- Pool: Under 4.5 (Under 4 when 4.5 is not offered) priced > 1.20 AND the league
  scores >= 2.8 goals/game on current-season results (>= 10 finished games).
  Lower and youth leagues are included; simulated/eSoccer are not.
- Book Over 1.5 when 1.20-1.25. If Over 1.5 < 1.20, book Over 2.5 when <= 1.50. Else skip.

3) REVERSE U4.5 + DRAW RULE  (``rev-u45-draw``)
- Same pool as #2.
- Draw > 3.70 and a clear favourite: favourite win, else favourite team Over 1.5.
- Balanced 1X2: Over 2.5, else GG (GG allowed here only).
- Legs 1.20-1.50.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parent)]
import strategy_lib as lib  # noqa: E402
import night_trio as trio  # noqa: E402
import ah1_fav as ah1  # noqa: E402

KINDS = ("sure80", "rev-u45", "rev-u45-draw")
ALL_KINDS = KINDS + trio.KINDS + ah1.KINDS   # trio (Team To Win, 80% Form, Match Over 2.5), then AH -1 Favourite
CODE_CAP = 25          # legs per code
MAX_CODES = 2          # codes per strategy per night (50 legs)
SURE_MIN = 0.80        # data estimate must be strictly above this
SURE_CLEAR = 0.85      # an Under line at or above this is "clear"; 0.80-0.85 is borderline
SURE_BAND = (1.20, 1.45)
TEAM_MIN_N = 6         # finished games per team needed for an estimate
H2H_MIN_N = 3          # meetings needed before H2H counts
LEAGUE_FIT_RATIO = 1.08    # leg price may be at most 8% longer than the league median
LEAGUE_FIT_MIN_N = 2       # other fixtures needed for a league median
LEAGUE_FIT_FALLBACK_MAX = 1.35
HIGH_SCORING_GPG = 2.8
SEASON_MIN_N = 10
REV_O15 = (1.20, 1.25)
REV_O25_MAX = 1.50
DRAW_MIN = 3.70
DRAW_BAND = (1.20, 1.50)
CLEAR_FAV_MAX = 1.75   # favourite price at most this ...
CLEAR_FAV_RATIO = 2.2  # ... and the underdog at least 2.2x the favourite
BALANCED_RATIO = 1.6   # max/min of home/away prices at most this

O = {
    "home": "1||Home", "draw": "1||Draw", "away": "1||Away",
    "dnb_home": "11||Home", "dnb_away": "11||Away",
    "o15": "18|total=1.5|Over 1.5", "o25": "18|total=2.5|Over 2.5",
    "u35": "18|total=3.5|Under 3.5", "u45": "18|total=4.5|Under 4.5", "u55": "18|total=5.5|Under 5.5",
    "u4": "18|total=4|Under 4",
    "h_o05": "19|total=0.5|Over 0.5", "a_o05": "20|total=0.5|Over 0.5",
    "h_o15": "19|total=1.5|Over 1.5", "a_o15": "20|total=1.5|Over 1.5",
    "gg": "29||Yes",
}


def price(odds: dict, name: str) -> float | None:
    row = odds.get(O[name])
    return float(row[0]) if row else None


def in_band(value, band) -> bool:
    return value is not None and band[0] <= value <= band[1]


# ------------------------------------------------------------------ selection helpers
def split_codes(legs: list[dict], cap: int = CODE_CAP, max_codes: int = MAX_CODES) -> list[list[dict]]:
    """Up to `max_codes` codes of at most `cap` legs, each >= 25 odds. Never padded.

    `legs` is ordered best-first. Two codes are dealt round-robin so both reach 25
    when they can; otherwise one code from the best `cap` legs; otherwise nothing.
    """
    clean = [leg for leg in legs if not lib.absolute_ban(leg)]
    seen, uniq = set(), []
    for leg in clean:
        if leg["eventId"] not in seen:
            seen.add(leg["eventId"])
            uniq.append(leg)
    uniq = uniq[: cap * max_codes]

    def ok(part):
        return part and len(part) <= cap and lib.product(leg["odds"] for leg in part) >= lib.MIN_TOTAL

    if len(uniq) > cap and max_codes >= 2:
        parts = [uniq[0::2], uniq[1::2]]
        if all(ok(part) for part in parts):
            return parts
    first = uniq[:cap]
    return [first] if ok(first) else []


def league_medians(rows: list[dict]) -> dict:
    """{(league, market): [(eventId, price), ...]} over every fixture of the day."""
    out: dict = {}
    for row in rows:
        for name in O:
            value = price(row["odds"], name)
            if value:
                out.setdefault((row["league"], name), []).append((row["eventId"], value))
    return out


def league_fit(row: dict, name: str, value: float, medians: dict) -> tuple[bool, float | None]:
    others = [p for eid, p in medians.get((row["league"], name), []) if eid != row["eventId"]]
    if len(others) < LEAGUE_FIT_MIN_N:
        return value <= LEAGUE_FIT_FALLBACK_MAX, None
    med = statistics.median(others)
    return value <= med * LEAGUE_FIT_RATIO, round(med, 3)


def _rate(values) -> float | None:
    values = list(values)
    return sum(values) / len(values) if values else None


def estimate(market: str, stats: dict) -> float | None:
    """Data probability for a market from last-10 results and H2H.

    stats = {"home": [(gf, ga), ...], "away": [(gf, ga), ...], "h2h": [(home_goals, away_goals), ...]}
    (each team's own results, newest first; h2h oriented to this fixture's home team).
    Returns the mean of the home-side, away-side and (with >= 3 meetings) H2H rates, or
    None when a side has fewer than TEAM_MIN_N games. Any single source under 0.70 -> 0.
    """
    home, away, h2h = stats.get("home") or [], stats.get("away") or [], stats.get("h2h") or []
    if len(home) < TEAM_MIN_N or len(away) < TEAM_MIN_N:
        return None
    tot = lambda g: g[0] + g[1]  # noqa: E731
    lines = {"o15": (1.5, True), "o25": (2.5, True), "u35": (3.5, False), "u45": (4.5, False), "u55": (5.5, False)}
    if market in lines:
        line, over = lines[market]
        hit = (lambda g: tot(g) > line) if over else (lambda g: tot(g) < line)
        parts = [_rate(map(hit, home)), _rate(map(hit, away))]
        if len(h2h) >= H2H_MIN_N:
            parts.append(_rate(map(hit, h2h)))
    elif market in ("h_o05", "a_o05"):
        if market == "h_o05":
            parts = [_rate(g[0] > 0 for g in home), _rate(g[1] > 0 for g in away)]
            if len(h2h) >= H2H_MIN_N:
                parts.append(_rate(g[0] > 0 for g in h2h))
        else:
            parts = [_rate(g[0] > 0 for g in away), _rate(g[1] > 0 for g in home)]
            if len(h2h) >= H2H_MIN_N:
                parts.append(_rate(g[1] > 0 for g in h2h))
    elif market in ("home", "away", "dnb_home", "dnb_away"):
        side_home = market in ("home", "dnb_home")
        me, them = (home, away) if side_home else (away, home)
        meet = [(g[0], g[1]) if side_home else (g[1], g[0]) for g in h2h]
        if market.startswith("dnb"):
            def dnb(rows, mine_wins=True):
                dec = [g for g in rows if g[0] != g[1]]
                return _rate((g[0] > g[1]) == mine_wins for g in dec) if dec else 0.0
            parts = [dnb(me), dnb(them, mine_wins=False)]
            if len(meet) >= H2H_MIN_N:
                parts.append(dnb(meet))
        else:
            parts = [_rate(g[0] > g[1] for g in me), _rate(g[0] < g[1] for g in them)]
            if len(meet) >= H2H_MIN_N:
                parts.append(_rate(g[0] > g[1] for g in meet))
        gf_me, ga_me = _rate(g[0] for g in me), _rate(g[1] for g in me)
        gf_them, ga_them = _rate(g[0] for g in them), _rate(g[1] for g in them)
        if not (gf_me > gf_them and ga_me < ga_them):   # GF/GA must back the pick
            return 0.0
    else:
        return None
    if min(parts) < 0.70:
        return 0.0
    return round(sum(parts) / len(parts), 3)


def table_clash(table: dict | None) -> str | None:
    """table = {"home": pos, "away": pos, "n": size} for a shared table, else None."""
    if not table:
        return None
    h, a, n = table["home"], table["away"], table["n"]
    if h <= 5 and a <= 5:
        return "top-5 v top-5"
    if h > n - 3 and a > n - 3:
        return "bottom-3 v bottom-3"
    return None


def sure80_pick(row: dict, medians: dict) -> tuple[dict | None, str]:
    """Best 80% Sure leg for a fixture, or (None, reason).

    row: {"eventId", "league", "odds", "stats", "table"} — odds from strategy_lib.event_odds.
    """
    clash = table_clash(row.get("table"))
    if clash:
        return None, clash
    stats = row.get("stats") or {}
    if len(stats.get("home") or []) < TEAM_MIN_N or len(stats.get("away") or []) < TEAM_MIN_N:
        return None, "no stats data"
    cands = []
    misses = {}

    def consider(name):
        value = price(row["odds"], name)
        if not in_band(value, SURE_BAND):
            return None
        fit, med = league_fit(row, name, value, medians)
        if not fit:
            misses["league-fit"] = misses.get("league-fit", 0) + 1
            return None
        p = estimate(name, stats)
        if p is None or p <= SURE_MIN:
            misses["data <=80%"] = misses.get("data <=80%", 0) + 1
            return None
        return {"name": name, "odds": value, "p": p, "median": med}

    for name in ("h_o05", "a_o05", "o15", "o25"):
        c = consider(name)
        if c:
            cands.append(c)
    # unders: narrowest clear line; a borderline narrower line gives way to the wider one
    for name in ("u35", "u45", "u55"):
        c = consider(name)
        if not c:
            continue
        cands.append(c)
        if c["p"] >= SURE_CLEAR:
            break
    table = row.get("table")
    for name, mine, theirs in (("home", "home", "away"), ("away", "away", "home"),
                               ("dnb_home", "home", "away"), ("dnb_away", "away", "home")):
        if not table or table[mine] >= table[theirs]:
            continue   # results picks need a shared table with the pick ranked higher
        c = consider(name)
        if c:
            cands.append(c)
    if not cands:
        return None, (max(misses, key=misses.get) if misses else "no market in 1.20-1.45")
    best = max(cands, key=lambda c: (c["p"], -c["odds"]))
    return best, "ok"


def reverse_pool(row: dict) -> tuple[bool, str]:
    """Shared pool for #2 and #3: U4.5 (or U4) > 1.20 and league gpg >= 2.8."""
    u = price(row["odds"], "u45")
    if u is None:
        u = price(row["odds"], "u4")
    if u is None:
        return False, "no Under 4.5 / Under 4"
    if u <= 1.20:
        return False, "Under 4.5 <= 1.20"
    gpg, n = row.get("gpg"), row.get("season_n") or 0
    if gpg is None or n < SEASON_MIN_N:
        return False, "no current-season goals data"
    if gpg < HIGH_SCORING_GPG:
        return False, f"league under {HIGH_SCORING_GPG} goals/game"
    return True, "ok"


def reverse_pick(odds: dict) -> str | None:
    o15, o25 = price(odds, "o15"), price(odds, "o25")
    if in_band(o15, REV_O15):
        return "o15"
    if o15 is not None and o15 < REV_O15[0] and o25 is not None and o25 <= REV_O25_MAX:
        return "o25"
    return None


def draw_rule_pick(odds: dict) -> str | None:
    h, d, a = price(odds, "home"), price(odds, "draw"), price(odds, "away")
    if not (h and d and a):
        return None
    fav, dog = min(h, a), max(h, a)
    if dog / fav <= BALANCED_RATIO:
        for name in ("o25", "gg"):
            value = price(odds, name)
            if in_band(value, DRAW_BAND) and (name != "o25" or value <= REV_O25_MAX):
                return name
        return None
    if d > DRAW_MIN and fav <= CLEAR_FAV_MAX and dog / fav >= CLEAR_FAV_RATIO:
        side = "home" if h <= a else "away"
        for name in (side, ("h_o15" if side == "home" else "a_o15")):
            if in_band(price(odds, name), DRAW_BAND):
                return name
    return None


LABEL = {
    "home": ("1X2", "Home"), "away": ("1X2", "Away"),
    "dnb_home": ("Draw No Bet", "Home"), "dnb_away": ("Draw No Bet", "Away"),
    "o15": ("Over/Under", "Over 1.5"), "o25": ("Over/Under", "Over 2.5"),
    "u35": ("Over/Under", "Under 3.5"), "u45": ("Over/Under", "Under 4.5"), "u55": ("Over/Under", "Under 5.5"),
    "gg": ("GG/NG", "Yes"),
}


def make_leg(event: dict, odds: dict, name: str, kind: str, **extra) -> dict | None:
    home, away = event.get("homeTeamName") or "", event.get("awayTeamName") or ""
    if name in LABEL:
        market, sel = LABEL[name]
    else:  # team totals grade as "<Team> over N goals"
        line = "0.5" if name.endswith("o05") else "1.5"
        team = home if name.startswith("h_") else away
        market, sel = f"{'Home' if name.startswith('h_') else 'Away'} Over/Under", f"{team} over {line} goals"
    leg = lib.leg_from_key(event, O[name], odds, market=market, selection=sel)
    if not leg:
        return None
    leg.update({"strategy": kind, **extra})
    return leg


# ------------------------------------------------------------------ data (network)
def _results(lastx: dict | None, uid, before: int) -> list[tuple[int, int]]:
    rows = [m for m in (lastx or {}).get("matches") or []
            if (m.get("result") or {}).get("home") is not None and not m.get("canceled")
            and m.get("time", {}).get("uts", 0) < before - 3600]
    rows.sort(key=lambda m: -m["time"]["uts"])
    out = []
    for m in rows[:10]:
        home = m["teams"]["home"]["uid"] == uid
        r = m["result"]
        out.append((r["home"], r["away"]) if home else (r["away"], r["home"]))
    return out


def fetch_stats(event_id: str, cache: dict, need_h2h: bool = True) -> dict:
    out = {"stats": None, "table": None, "sid": None}
    match = lib.sr_get("stats_match_get/" + event_id.split(":")[-1], cache)
    if not match or "teams" not in match:
        return out
    before = match["time"]["uts"]
    hu, au = match["teams"]["home"]["uid"], match["teams"]["away"]["uid"]
    out["sid"] = match.get("_seasonid")
    if not need_h2h:
        return out
    stats = {
        "home": _results(lib.sr_get(f"stats_team_lastx/{hu}", cache), hu, before),
        "away": _results(lib.sr_get(f"stats_team_lastx/{au}", cache), au, before),
    }
    versus = lib.sr_get(f"stats_team_versus/{hu}/{au}", cache) or {}
    meet = [m for m in versus.get("matches") or []
            if (m.get("result") or {}).get("home") is not None and m.get("time", {}).get("uts", 0) < before - 3600]
    meet.sort(key=lambda m: -m["time"]["uts"])
    stats["h2h"] = [((m["result"]["home"], m["result"]["away"]) if m["teams"]["home"]["uid"] == hu
                     else (m["result"]["away"], m["result"]["home"])) for m in meet[:6]]
    out["stats"] = stats
    table = lib.sr_get(f"stats_season_tables/{out['sid']}", cache) if out["sid"] else None
    for block in (table or {}).get("tables") or []:
        pos = {}
        for item in block.get("tablerows") or []:
            uid = item.get("team", {}).get("uid")
            if uid in (hu, au):
                pos[uid] = item.get("pos")
        if hu in pos and au in pos:
            out["table"] = {"home": int(pos[hu]), "away": int(pos[au]), "n": len(block.get("tablerows") or [])}
            break
    return out


def season_gpg(sid, cache: dict, memo: dict):
    if sid in memo:
        return memo[sid]
    data = lib.sr_get(f"stats_season_fixtures2/{sid}/1", cache) or {}
    done = [m for m in data.get("matches") or [] if (m.get("result") or {}).get("home") is not None and not m.get("canceled")]
    res = (round(sum(m["result"]["home"] + m["result"]["away"] for m in done) / len(done), 2), len(done)) if done else (None, 0)
    memo[sid] = res
    return res


def load_rows(day: dt.date) -> tuple[list[dict], int]:
    rows = []
    now = dt.datetime.now(dt.timezone.utc)
    for event in lib.fetch_upcoming("1,11,16,18,19,20,29"):
        kick = lib.event_kick(event)
        if not kick or kick.date() != day or kick <= now + dt.timedelta(minutes=10):
            continue
        country, league = lib.league_of(event)
        blob = f"{country} {league} {event.get('homeTeamName')} {event.get('awayTeamName')}".lower()
        if "srl" in blob or "simulated" in blob or "esoccer" in blob:
            continue
        rows.append({"event": event, "eventId": event.get("eventId"), "league": f"{country} - {league}",
                     "odds": lib.event_odds(event), "ko": kick})
    return rows, len(rows)


# ------------------------------------------------------------------ run
def select_all(rows: list[dict], cache: dict, usage: dict) -> dict:
    medians = league_medians(rows)
    out = {k: {"legs": [], "removed": {}} for k in KINDS}

    def drop(kind, why):
        out[kind]["removed"][why] = out[kind]["removed"].get(why, 0) + 1

    memo: dict = {}
    for row in rows:
        eid = row["eventId"]
        if not lib.can_take(usage, eid):
            for kind in KINDS:
                drop(kind, "already on 2 codes")
            continue
        odds = row["odds"]
        sure_price = any(in_band(price(odds, n), SURE_BAND) for n in O if n not in ("draw", "u4", "gg", "h_o15", "a_o15"))
        rev_candidate = (price(odds, "u45") or price(odds, "u4") or 0) > 1.20
        if not (sure_price or rev_candidate):
            for kind in KINDS:
                drop(kind, "price screen")
            continue
        info = fetch_stats(eid, cache, need_h2h=sure_price)
        row.update(info)
        if sure_price:
            pick, why = sure80_pick(row, medians)
            if pick:
                leg = make_leg(row["event"], odds, pick["name"], "sure80", dataP=pick["p"], leagueMedian=pick["median"],
                               tableChecked=bool(row.get("table")))
                if leg:
                    out["sure80"]["legs"].append(leg)
            else:
                drop("sure80", why)
        else:
            drop("sure80", "no market in 1.20-1.45")
        if rev_candidate and row.get("sid"):
            row["gpg"], row["season_n"] = season_gpg(row["sid"], cache, memo)
        ok, why = reverse_pool(row)
        if not ok:
            drop("rev-u45", why)
            drop("rev-u45-draw", why)
            continue
        for kind, fn in (("rev-u45", reverse_pick), ("rev-u45-draw", draw_rule_pick)):
            name = fn(odds)
            leg = make_leg(row["event"], odds, name, kind, leagueGpg=row["gpg"]) if name else None
            if leg:
                out[kind]["legs"].append(leg)
            else:
                drop(kind, "no rule price")
    out["sure80"]["legs"].sort(key=lambda leg: (-leg["dataP"], leg["odds"]))
    for kind in ("rev-u45", "rev-u45-draw"):
        out[kind]["legs"].sort(key=lambda leg: (-(leg.get("leagueGpg") or 0), leg["odds"]))
    return out


def run(day: dt.date, repo: Path, dry_run: bool = False, only: tuple = ALL_KINDS) -> dict:
    usage = lib.load_usage(repo, day.isoformat())
    rows, seen = load_rows(day)
    cache: dict = {}
    found = select_all(rows, cache, usage)
    if any(k in trio.KINDS for k in only):
        found.update(trio.select(rows, cache, usage, season_gpg, make_leg))
    if any(k in ah1.KINDS for k in only):
        found.update(ah1.select(rows, cache, usage, make_leg))
    summary = {}
    for kind in [k for k in ALL_KINDS if k in only]:
        # the shared 2-codes-per-match usage, including codes booked earlier in this same run
        legs = [leg for leg in found[kind]["legs"] if lib.can_take(usage, leg["eventId"])]
        capped = len(found[kind]["legs"]) - len(legs)
        lib.leg_guard().enforce(legs, f"sure80:{kind}")  # final Over 1.5 <-> Under 3.5 rule (HANDOFF 5.10)
        parts = trio.split_many(legs) if kind in trio.KINDS + ah1.KINDS else split_codes(legs)
        booked = []
        for index, part in enumerate(parts, 1):
            if dry_run:
                booked.append({"dryRun": True, "part": index, "n": len(part),
                               "total": round(lib.product(leg["odds"] for leg in part), 2), "legs": part})
                for leg in part:
                    lib.take(usage, leg["eventId"], f"dry-{kind}-{index}")
                continue
            result = lib.book_confirmed(part)
            result["part"] = index
            if result.get("code"):
                for leg in result["legs"]:
                    lib.take(usage, leg["eventId"], result["code"])
                slip = lib.public_slip(kind, day.isoformat(), result["code"], result["legs"], result["total"],
                                       index if len(parts) > 1 else None)
                lib.publish_high_odds(repo, slip)
            booked.append(result)
        if not dry_run:
            lib.save_usage(repo, day.isoformat(), usage)
        payload = {
            "strategy": kind, "date": day.isoformat(), "seen": seen,
            "qualifying": len(found[kind]["legs"]), "cappedByUsage": capped, "removed": found[kind]["removed"],
            "booked": [{k: v for k, v in b.items() if k != "legs"} | {"n": len(b.get("legs") or [])} for b in booked],
            "legs": [leg for b in booked if b.get("code") for leg in (b.get("legs") or [])],
            "rules": {"cap": CODE_CAP, "minTotal": lib.MIN_TOTAL, "leagueFitRatio": LEAGUE_FIT_RATIO,
                      "sureMin": SURE_MIN, "highScoringGpg": HIGH_SCORING_GPG},
        }
        if not dry_run:
            lib.write_record(repo, kind, day.isoformat(), payload)
        summary[kind] = {"qualifying": payload["qualifying"], "cappedByUsage": capped,
                         "codes": [{"n": b.get("n") or len(b.get("legs") or []), "total": b.get("total"),
                                    "code": b.get("code"), "reason": b.get("reason")} for b in booked],
                         "removed": payload["removed"]}
    print(json.dumps({"sure80_reverse": day.isoformat(), "seen": seen, "dry": dry_run, "strategies": summary}, default=str))
    return summary


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--repo")
    parser.add_argument("--only", help="comma list of " + ",".join(ALL_KINDS))
    args = parser.parse_args(argv)
    day = lib.nightly_target(explicit=args.date)
    repo = Path(args.repo) if args.repo else lib.repo_root()
    dry = args.dry_run or os.environ.get("P2U_HEALTH_DRY_RUN") == "1"
    only = tuple(k for k in (args.only or "").split(",") if k in ALL_KINDS) or ALL_KINDS
    run(day, repo, dry_run=dry, only=only)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
