"""AH -1 Favourite (22:00 job, after Team To Win / 80% Form / Match Over 2.5). HANDOFF section 5.8.

Spec: Riddim Boss via Betting Strategies (NerdyTips), 21 Nov 2026 (tested as SportyBet 8H3ZTC).

1. Filter: the stronger team (1X2 favourite) must have a SportyBet full-time Asian Handicap -1 price
   strictly below 1.90 (market 16, hcp=-1 "Home (-1.0)" or hcp=1 "Away (-1.0)"). No AH -1 listed -> skip.
   SportyBet only.
2. Market by the weaker team's contribution (Sportradar last 10 competitive games + season table):
   - weak team scores often: scored in 6+ of last 10, OR weak team Over 0.5 < 1.50, OR season goals
     for >= 1.2 per game                                       -> match Over 2.5
   - weak team rarely scores: (scored in <= 4 of last 10 OR goals for < 0.9 per game) AND the strong
     team scored 2+ in 6+ of its last 10                         -> strong team Over 1.5
   - otherwise                                                  -> strong team to win
   Price floor 1.20: if the chosen market is under 1.20 (or not offered) step UP the ladder
   win -> strong team Over 1.5 -> match Over 2.5; nothing reaches 1.20 -> drop the match.
3. Standing rules: busy-day league filter (feed level, busy_day.py), top-5 v top-5 and bottom-3 v
   bottom-3 dropped (same table only), one pick per match, <= 25 legs and >= 25 odds per code, never
   padded, shared 2-codes-per-match usage cap (applied in sure80_reverse.run).
"""
from __future__ import annotations

import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import strategy_lib as lib  # noqa: E402
import night_trio as trio  # noqa: E402

KIND = "ah1"
KINDS = (KIND,)
AH_MAX = 1.90          # strictly below
FLOOR = 1.20           # minimum leg price
LAST_N = 10
OFTEN_SCORED = 6       # weak team scored in 6+ of last 10
OFTEN_O05 = 1.50       # weak team Over 0.5 below this
OFTEN_GPG = 1.2        # weak team goals for per game >=
RARE_SCORED = 4        # weak team scored in <= 4 of last 10
RARE_GPG = 0.9         # weak team goals for per game <
STRONG_2PLUS = 6       # strong team scored 2+ in 6+ of last 10
LADDER = ("win", "team_o15", "o25")
DETAIL_PRESCREEN = 2.20  # fetch the full event only when the favourite's 1X2 is <= this (AH -1 < 1.90 needs far shorter)
SB_EVENT = "https://www.sportybet.com/api/gh/factsCenter/event?eventId={}&productId=3"

AH_KEY = {"h": "16|hcp=-1|Home (-1.0)", "a": "16|hcp=1|Away (-1.0)"}
O05_KEY = {"h": "19|total=0.5|Over 0.5", "a": "20|total=0.5|Over 0.5"}
LEG_NAME = {  # sure80_reverse.O names used by make_leg
    ("win", "h"): "home", ("win", "a"): "away",
    ("team_o15", "h"): "h_o15", ("team_o15", "a"): "a_o15",
    ("o25", "h"): "o25", ("o25", "a"): "o25",
}
PRICE_KEY = {"home": "1||Home", "away": "1||Away", "h_o15": "19|total=1.5|Over 1.5",
             "a_o15": "20|total=1.5|Over 1.5", "o25": "18|total=2.5|Over 2.5"}


def price(odds: dict, key: str) -> float | None:
    row = odds.get(key)
    return float(row[0]) if row else None


def ah_minus_one(odds: dict, fav: str) -> float | None:
    return price(odds, AH_KEY[fav])


# ------------------------------------------------------------------ rules (pure)
def weak_profile(weak_last: list[tuple[int, int]] | None, weak_gpg: float | None, weak_o05: float | None) -> dict:
    last = list(weak_last or [])[:LAST_N]
    scored = sum(1 for gf, _ in last if gf > 0) if last else None
    if weak_gpg is None and last:
        weak_gpg = sum(gf for gf, _ in last) / len(last)
    often = ((scored is not None and scored >= OFTEN_SCORED)
             or (weak_o05 is not None and weak_o05 < OFTEN_O05)
             or (weak_gpg is not None and weak_gpg >= OFTEN_GPG))
    rare = ((scored is not None and scored <= RARE_SCORED)
            or (weak_gpg is not None and weak_gpg < RARE_GPG))
    return {"scored": scored, "gpg": None if weak_gpg is None else round(weak_gpg, 2), "often": often, "rare": rare}


def strong_two_plus(strong_last: list[tuple[int, int]] | None) -> int | None:
    last = list(strong_last or [])[:LAST_N]
    return sum(1 for gf, _ in last if gf >= 2) if last else None


def choose_market(weak: dict, strong_2p: int | None) -> tuple[str, str]:
    if weak["often"]:
        return "o25", "weak team scores often"
    if weak["rare"] and strong_2p is not None and strong_2p >= STRONG_2PLUS:
        return "team_o15", "weak team rarely scores, strong team 2+ in 6+"
    return "win", "otherwise"


def apply_floor(odds: dict, fav: str, market: str) -> tuple[str | None, float | None]:
    """Chosen market if >= 1.20, else the next rungs up (win -> team O1.5 -> O2.5)."""
    for rung in LADDER[LADDER.index(market):]:
        name = LEG_NAME[(rung, fav)]
        p = price(odds, PRICE_KEY[name])
        if p is not None and p >= FLOOR:
            return name, p
    return None, None


def decide(odds: dict, weak_last, weak_gpg, strong_last) -> tuple[str | None, dict]:
    """(sure80 leg name or None, info). Pure so tests can drive it."""
    sd = trio.sides(odds)
    if not sd:
        return None, {"why": "no 1X2"}
    fav, dog = sd
    ah = ah_minus_one(odds, fav)
    if ah is None:
        return None, {"why": "no AH -1"}
    if ah >= AH_MAX:
        return None, {"why": "AH -1 >= 1.90", "ah": ah}
    weak = weak_profile(weak_last, weak_gpg, price(odds, O05_KEY[dog]))
    s2 = strong_two_plus(strong_last)
    market, reason = choose_market(weak, s2)
    name, p = apply_floor(odds, fav, market)
    info = {"ah": ah, "fav": fav, "chosen": market, "reason": reason, "weakScored": weak["scored"],
            "weakGpg": weak["gpg"], "strong2plus": s2}
    if not name:
        info["why"] = "nothing reaches 1.20"
        return None, info
    info["stepped"] = name != LEG_NAME[(market, fav)]
    return name, info


# ------------------------------------------------------------------ data (network, cached)
def with_ah(row: dict, cache: dict) -> dict:
    """The upcoming feed lists only some AH lines; read the full event when -1 is missing.
    Returns the odds map for this strategy only (other strategies keep their own)."""
    odds = row["odds"]
    sd = trio.sides(odds)
    if not sd or AH_KEY[sd[0]] in odds:
        return odds
    if (price(odds, "1||Home" if sd[0] == "h" else "1||Away") or 99) > DETAIL_PRESCREEN:
        return odds
    key = "sbevent:" + str(row["eventId"])
    if key not in cache:
        try:
            cache[key] = (lib.http_json(SB_EVENT.format(str(row["eventId"]).replace(":", "%3A")), timeout=25) or {}).get("data") or {}
        except Exception:
            cache[key] = {}
    extra = lib.event_odds(cache[key]) if cache[key] else {}
    return {**extra, **odds} if extra else odds


def fetch(row: dict, cache: dict) -> dict:
    out = {"last": (None, None), "gpg": (None, None), "table": None}
    match = lib.sr_get("stats_match_get/" + str(row["eventId"]).split(":")[-1], cache)
    if not match or "teams" not in match:
        return out
    before = match["time"]["uts"]
    hu, au = match["teams"]["home"]["uid"], match["teams"]["away"]["uid"]
    hl = lib.sr_get(f"stats_team_lastx/{hu}/20", cache)
    al = lib.sr_get(f"stats_team_lastx/{au}/20", cache)
    out["last"] = (trio.competitive(hl, hu, before)[:LAST_N], trio.competitive(al, au, before)[:LAST_N])
    sid = match.get("_seasonid")
    table = lib.sr_get(f"stats_season_tables/{sid}", cache) if sid else None
    for block in (table or {}).get("tables") or []:
        rows = {(item.get("team") or {}).get("uid"): item for item in block.get("tablerows") or []}
        if hu in rows and au in rows:
            h, a = rows[hu], rows[au]
            out["table"] = {"home": int(h.get("pos") or 0), "away": int(a.get("pos") or 0), "n": len(rows)}
            gpg = lambda it: (it.get("goalsForTotal") / it["total"]) if it.get("total") and it.get("goalsForTotal") is not None else None  # noqa: E731
            out["gpg"] = (gpg(h), gpg(a))
            break
    return out


def select(rows: list[dict], cache: dict, usage: dict, make_leg) -> dict:
    out = {KIND: {"legs": [], "removed": {}}}

    def drop(why):
        out[KIND]["removed"][why] = out[KIND]["removed"].get(why, 0) + 1

    todo = []
    live = [r for r in rows if lib.can_take(usage, r["eventId"])]
    for _ in range(len(rows) - len(live)):
        drop("already on 2 codes")
    with ThreadPoolExecutor(8) as pool:
        full = list(pool.map(lambda r: with_ah(r, cache), live))
    for r, odds in zip(live, full):
        r = dict(r, odds=odds)
        sd = trio.sides(r["odds"])
        ah = ah_minus_one(r["odds"], sd[0]) if sd else None
        if ah is None:
            drop("no AH -1" if sd else "no 1X2")
        elif ah >= AH_MAX:
            drop("AH -1 >= 1.90")
        else:
            todo.append(r)
    with ThreadPoolExecutor(8) as pool:
        infos = list(pool.map(lambda r: fetch(r, cache), todo))
    for r, data in zip(todo, infos):
        clash = trio.table_clash(data["table"])
        if clash:
            drop(clash)
            continue
        fav, dog = trio.sides(r["odds"])
        idx = {"h": 0, "a": 1}
        name, info = decide(r["odds"], data["last"][idx[dog]], data["gpg"][idx[dog]], data["last"][idx[fav]])
        if not name:
            drop(info.get("why") or "no pick")
            continue
        leg = make_leg(r["event"], r["odds"], name, KIND, ahMinusOne=info["ah"], rule=info["chosen"],
                       stepped=info["stepped"])
        if leg:
            out[KIND]["legs"].append(leg)
        else:
            drop("market not offered")
    out[KIND]["legs"].sort(key=lambda x: (x.get("ahMinusOne") or 9, x["odds"]))  # strongest favourite first
    return out
