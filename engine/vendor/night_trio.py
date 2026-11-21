#!/usr/bin/env python3
"""Team To Win, 80% Form and Match Over 2.5 — run inside the 22:00 job (sure80_reverse.run).

Spec from Betting Strategies (NerdyTips), 21 Nov 2026 (Riddim Boss: "push all these strategies
to predict2u to push daily on the site and fixed in engine").

Shared rules: SportyBet GH share codes only, not-started legs, no NG / no DC, >= 25 total odds and
<= 25 legs per code, never padded, a large pool is split into several 25-leg codes that each reach 25,
a match on at most 2 codes (shared strategy-usage file, after 80% Sure / Reverse U4.5 / + Draw),
drop top-5 v top-5 and bottom-3 v bottom-3 (shared table only). Strong team = 1X2 favourite.

1) TEAM TO WIN (``ttw``): favourite WIN when >= 2 of 7 checks pass:
   (a) favourite team-total Over 2.5 offered; (b) win < 1.45; (c) weaker team Over 0.5 > 1.65;
   (d) draw > 4.00; (e) GG > 1.70; (f) Under 3.5 > 1.60; (g) favourite Over 2.5 < 2.00.
   Ranked by checks passed, then lower win price.
2) 80% FORM (``form80``): each team's last 10 competitive games (Sportradar tournaments flagged
   friendly are excluded; fewer than 10 -> that team gives no signal). 8+ wins -> that team WIN;
   8+ losses -> opponent WIN; unbeaten 8+ (not an 8+ winner) -> that team DNB. Conflicting
   signals skip the match; WIN beats DNB for the same team. Ranked by signal strength, then price.
3) MATCH OVER 2.5 (``mo25``): only youth, high-scoring (>= 2.8 goals/game, sure80_reverse.season_gpg)
   or amateur/lower-tier leagues. Youth = YOUTH_RE on league/team names (U17-U23, youth, junior,
   primavera, reserves, academy...). Lower tier = Sportradar ``tournamentlevelorder`` >= 3 for the
   match's tournament, or AMATEUR_RE on the league name (amateur, regional, oberliga, serie d, ...).
   Book match Over 2.5 when >= 2 of 8 checks pass: (a) the favourite's ONLY team-goals market is team O2.5
   (no team O0.5 / O1.5 offered; so (a) and (h) never pass together); (b) favourite
   win < 1.45; (c) weaker team O0.5 < 1.50; (d) draw > 4.00; (e) GG < 1.60; (f) U3.5 > 1.60;
   (g) favourite O2.5 < 2.00; (h) favourite O1.5 < 1.50. Ranked by checks passed, then price.
"""
from __future__ import annotations

import math
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parent)]
import strategy_lib as lib  # noqa: E402

KINDS = ("ttw", "form80", "mo25")
CAP = 25
MIN_CHECKS = 2
FORM_N = 10
FORM_HIT = 8
YOUTH_RE = re.compile(r"\bu-?1[5-9]\b|\bu-?2[0-3]\b|under[- ]?(1\d|2[0-3])|youth|junior|juvenil|primavera|"
                      r"academy|reserves?\b|\bii\b|jong |next ?gen|sub-?(1\d|2[0-3])", re.I)
AMATEUR_RE = re.compile(r"amateur|regional|oberliga|landesliga|verbandsliga|bezirksliga|serie d|tercera|"
                        r"segunda (rfef|federaci)|primera rfef|national league (north|south)|isthmian|"
                        r"northern premier|southern league|state league|\bnpl\b|division (3|4|5|three|four|five)|"
                        r"liga (3|4)\b|3\. liga|4\. liga|third|fourth|non[- ]league", re.I)
K = {
    "home": "1||Home", "draw": "1||Draw", "away": "1||Away", "gg": "29||Yes",
    "o25": "18|total=2.5|Over 2.5", "u35": "18|total=3.5|Under 3.5",
    "h_o05": "19|total=0.5|Over 0.5", "a_o05": "20|total=0.5|Over 0.5",
    "h_o15": "19|total=1.5|Over 1.5", "a_o15": "20|total=1.5|Over 1.5",
    "h_o25": "19|total=2.5|Over 2.5", "a_o25": "20|total=2.5|Over 2.5",
    "dnb_home": "11||Home", "dnb_away": "11||Away",
}


def p(odds: dict, name: str) -> float | None:
    row = odds.get(K[name])
    return float(row[0]) if row else None


def sides(odds: dict):
    """(fav, dog) as 'h'/'a', or None without a full 1X2."""
    h, a = p(odds, "home"), p(odds, "away")
    if not (h and a and p(odds, "draw")):
        return None
    return ("h", "a") if h <= a else ("a", "h")


def lt(v, x):
    return v is not None and v < x


def gt(v, x):
    return v is not None and v > x


def ttw_checks(odds: dict) -> tuple[int, list[str]]:
    sd = sides(odds)
    if not sd:
        return 0, []
    f, d = sd
    win = p(odds, "home" if f == "h" else "away")
    checks = {
        "a": p(odds, f"{f}_o25") is not None,
        "b": lt(win, 1.45),
        "c": gt(p(odds, f"{d}_o05"), 1.65),
        "d": gt(p(odds, "draw"), 4.00),
        "e": gt(p(odds, "gg"), 1.70),
        "f": gt(p(odds, "u35"), 1.60),
        "g": lt(p(odds, f"{f}_o25"), 2.00),
    }
    passed = [k for k, v in checks.items() if v]
    return len(passed), passed


def only_team_o25(odds: dict, side: str) -> bool:
    """Match Over 2.5 check (a): team Over 2.5 offered and no team Over 0.5 / Over 1.5 for that team.

    (h) needs the favourite's team Over 1.5 price, so (a) and (h) can never both pass.
    """
    return (p(odds, f"{side}_o25") is not None and p(odds, f"{side}_o05") is None
            and p(odds, f"{side}_o15") is None)


def mo25_checks(odds: dict) -> tuple[int, list[str]]:
    sd = sides(odds)
    if not sd:
        return 0, []
    f, d = sd
    win = p(odds, "home" if f == "h" else "away")
    checks = {
        # (a) the favourite's ONLY team-goals market is team Over 2.5 (no team O0.5 / O1.5 offered)
        "a": only_team_o25(odds, f),
        "b": lt(win, 1.45),
        "c": lt(p(odds, f"{d}_o05"), 1.50),
        "d": gt(p(odds, "draw"), 4.00),
        "e": lt(p(odds, "gg"), 1.60),
        "f": gt(p(odds, "u35"), 1.60),
        "g": lt(p(odds, f"{f}_o25"), 2.00),
        "h": lt(p(odds, f"{f}_o15"), 1.50),
    }
    passed = [k for k, v in checks.items() if v]
    return len(passed), passed


def form_signal(results: list[tuple[int, int]] | None) -> dict | None:
    """results = a team's last competitive games (gf, ga), newest first. None if < 10."""
    if not results or len(results) < FORM_N:
        return None
    last = results[:FORM_N]
    w = sum(1 for g in last if g[0] > g[1])
    lo = sum(1 for g in last if g[0] < g[1])
    return {"w": w, "l": lo, "unbeaten": FORM_N - lo}


def form_pick(home: dict | None, away: dict | None) -> tuple[str | None, int, str]:
    """(market name in K, strength, reason). One pick per match; conflicts skip."""
    votes = {}

    def vote(name, s):
        votes[name] = max(votes.get(name, 0), s)
    if home:
        if home["w"] >= FORM_HIT:
            vote("home", home["w"])
        if home["l"] >= FORM_HIT:
            vote("away", home["l"])
        if home["unbeaten"] >= FORM_HIT and home["w"] < FORM_HIT:
            vote("dnb_home", home["unbeaten"])
    if away:
        if away["w"] >= FORM_HIT:
            vote("away", away["w"])
        if away["l"] >= FORM_HIT:
            vote("home", away["l"])
        if away["unbeaten"] >= FORM_HIT and away["w"] < FORM_HIT:
            vote("dnb_away", away["unbeaten"])
    if not votes:
        return None, 0, "no 80% signal" if (home or away) else "fewer than 10 verified games"
    teams = {"home" if n in ("home", "dnb_home") else "away" for n in votes}
    if len(teams) > 1:
        return None, 0, "conflict"
    team = teams.pop()
    name = team if team in votes else f"dnb_{team}"
    return name, max(votes.values()), "ok"


def table_clash(table: dict | None) -> str | None:
    if not table:
        return None
    h, a, n = table["home"], table["away"], table["n"]
    if h <= 5 and a <= 5:
        return "top-5 v top-5"
    if h > n - 3 and a > n - 3:
        return "bottom-3 v bottom-3"
    return None


def league_kind(league: str, home: str, away: str, level: int | None, gpg: float | None) -> str | None:
    if YOUTH_RE.search(f"{league} {home} {away}"):
        return "youth"
    if gpg is not None and gpg >= 2.8:
        return "high-scoring"
    if (level is not None and level >= 3) or AMATEUR_RE.search(league):
        return "lower-tier"
    return None


def split_many(legs: list[dict], cap: int = CAP) -> list[list[dict]]:
    """Several <= cap-leg codes that each reach 25 odds. Never padded.

    Round-robin over the fewest parts first (keeps the ranked best spread out); if a part misses 25,
    cut in rank order instead and keep only parts that reach 25 — whichever books more legs.
    """
    seen, uniq = set(), []
    for leg in legs:
        if leg["eventId"] not in seen and not lib.absolute_ban(leg):
            seen.add(leg["eventId"])
            uniq.append(leg)
    if not uniq:
        return []
    n = math.ceil(len(uniq) / cap)
    ok = lambda part: lib.product(x["odds"] for x in part) >= lib.MIN_TOTAL  # noqa: E731
    dealt = [part for part in (uniq[i::n] for i in range(n)) if ok(part)]
    cut = [part for part in (uniq[i:i + cap] for i in range(0, len(uniq), cap)) if ok(part)]
    count = lambda parts: sum(len(x) for x in parts)  # noqa: E731
    return dealt if count(dealt) >= count(cut) else cut


# ------------------------------------------------------------------ data
def competitive(lastx: dict | None, uid, before: int) -> list[tuple[int, int]]:
    tours = (lastx or {}).get("tournaments") or {}
    rows = []
    for m in (lastx or {}).get("matches") or []:
        if (m.get("result") or {}).get("home") is None or m.get("canceled") or m.get("time", {}).get("uts", 0) >= before - 3600:
            continue
        t = tours.get(str(m.get("_tid"))) or {}
        if t.get("friendly") or m.get("friendly"):
            continue
        rows.append(m)
    rows.sort(key=lambda m: -m["time"]["uts"])
    out = []
    for m in rows:
        home = m["teams"]["home"]["uid"] == uid
        out.append((m["result"]["home"], m["result"]["away"]) if home else (m["result"]["away"], m["result"]["home"]))
    return out


def fetch(row: dict, cache: dict) -> dict:
    out = {"form": (None, None), "table": None, "level": None, "sid": None}
    match = lib.sr_get("stats_match_get/" + row["eventId"].split(":")[-1], cache)
    if not match or "teams" not in match:
        return out
    before = match["time"]["uts"]
    hu, au = match["teams"]["home"]["uid"], match["teams"]["away"]["uid"]
    out["sid"] = match.get("_seasonid")
    hl = lib.sr_get(f"stats_team_lastx/{hu}/20", cache)
    al = lib.sr_get(f"stats_team_lastx/{au}/20", cache)
    out["form"] = (form_signal(competitive(hl, hu, before)), form_signal(competitive(al, au, before)))
    tour = ((hl or {}).get("tournaments") or {}).get(str(match.get("_tid"))) or {}
    out["level"] = tour.get("tournamentlevelorder")
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


def select(rows: list[dict], cache: dict, usage: dict, season_gpg, make_leg) -> dict:
    """Candidates per kind (ranked). `season_gpg(sid, cache, memo)` and `make_leg(event, odds, key, kind, **x)`
    come from sure80_reverse so the goals-per-game calc and leg shape match #37."""
    out = {k: {"legs": [], "removed": {}} for k in KINDS}

    def drop(kind, why):
        out[kind]["removed"][why] = out[kind]["removed"].get(why, 0) + 1

    todo = [r for r in rows if lib.can_take(usage, r["eventId"])]
    for r in rows:
        if r not in todo:
            for kind in KINDS:
                drop(kind, "already on 2 codes")
    with ThreadPoolExecutor(8) as pool:
        infos = list(pool.map(lambda r: fetch(r, cache), todo))
    memo: dict = {}
    for r, info in zip(todo, infos):
        odds, ev = r["odds"], r["event"]
        clash = table_clash(info["table"])
        if clash:
            for kind in KINDS:
                drop(kind, clash)
            continue
        sd = sides(odds)
        # 1) Team To Win
        n, passed = ttw_checks(odds)
        if sd and n >= MIN_CHECKS:
            key = "home" if sd[0] == "h" else "away"
            leg = make_leg(ev, odds, key, "ttw", checks="".join(passed))
            out["ttw"]["legs"].append(leg) if leg else drop("ttw", "no price")
        else:
            drop("ttw", f"under {MIN_CHECKS} checks")
        # 2) 80% Form
        name, strength, why = form_pick(*info["form"])
        leg = make_leg(ev, odds, name, "form80", formStrength=strength) if name else None
        if leg:
            out["form80"]["legs"].append(leg)
        else:
            drop("form80", why if not name else "market not offered")
        # 3) Match Over 2.5
        home, away = ev.get("homeTeamName") or "", ev.get("awayTeamName") or ""
        gpg = season_gpg(info["sid"], cache, memo)[0] if info["sid"] else None
        kind_l = league_kind(r["league"], home, away, info["level"], gpg)
        if not kind_l:
            drop("mo25", "not youth / high-scoring / lower-tier")
            continue
        n, passed = mo25_checks(odds)
        leg = make_leg(ev, odds, "o25", "mo25", checks="".join(passed), leagueKind=kind_l) if n >= MIN_CHECKS else None
        if leg:
            out["mo25"]["legs"].append(leg)
        else:
            drop("mo25", f"under {MIN_CHECKS} checks" if n < MIN_CHECKS else "no Over 2.5 price")
    out["ttw"]["legs"].sort(key=lambda x: (-len(x.get("checks") or ""), x["odds"]))
    out["form80"]["legs"].sort(key=lambda x: (-(x.get("formStrength") or 0), x["odds"]))
    out["mo25"]["legs"].sort(key=lambda x: (-len(x.get("checks") or ""), x["odds"]))
    return out
