#!/usr/bin/env python3
"""Bets For The Day — strategies 1–5, High Odds, HIGH RISK.

  1) Over 2.5 when at least 2 of: price 1.20–1.40; 1st-half Over 1.5 < 2.00;
     league average goals/match > 2.5 (n>=20).
  2) Top-3 or won-last-3: win if priced <=1.45, otherwise Draw No Bet.
  3) Bottom-3 or winless-last-3: double chance against that side (1X/X2 only).
  4) Top-5 v bottom-3: weaker side to score (team Over 0.5) priced above 1.70.
  5) Top-5 v bottom-3: stronger side Asian Handicap -1 priced under 1.90.

Every candidate then goes through the normal Predict2u gates (matchup_rules.check):
no NG, no DC 12, 1X/X2 only at <=1.35, obscure leagues goals-only, no leg above
1.60 without extreme stats, Over 1.5 / Under 3.5 above 1.30 only with extreme
stats, one market per game, no padding, <=50 legs. A slip that cannot reach 25
combined odds is still booked (combine rule) and marked under the floor.

Nov 9 pool-0 cause (verified on a live event):
  * Team/season lookup called Sportradar as match_detailsextended/sr:match:N.
    That path returns event=exception. The numeric id (match_info/N) resolves.
    With no season, league-average, table and form all stayed empty, so
    strategies 2–5 never fired and strategy 1 could not collect its 2nd condition.
  * Draw No Bet was requested as market 14/11 with 1X2 outcome ids 1 and 3.
    SportyBet DNB is market 11, outcomes 4 (Home) and 5 (Away).
"""
from __future__ import annotations

import datetime as dt
import json
import math
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parent), str(HERE.parent.parent)]
import matchup_rules as MR
import split_codes as SC
import sb_common as SB
from engine.paths import ENGINE_DIR

SKIP_EXTRA = re.compile(r"\b(cup|trophy|play-?off|qualifier)\b", re.I)
TOP_FLIGHT = re.compile(
    r"(premier|primera|serie a|ligue 1|bundesliga|eredivisie|liga portugal|"
    r"scottish premiership|belgian pro|superlig|superliga|ekstraklasa|"
    r"allsvenskan|eliteserien|veikkausliiga|swiss super|austrian bundesliga|"
    r"championship|laliga|la liga)",
    re.I,
)


def outcome(markets, mid, spec, oid=None, startswith=None):
    return SB.find_outcome(markets, mid, spec or "", oid=oid, desc_prefix=startswith)


def stats_paths(eid):
    return SB.stats_paths(eid)


def dnb_outcome_id(side: str) -> str:
    """SportyBet market 11: 4 = Home, 5 = Away. Ids 1 and 3 are 1X2, not DNB."""
    return "4" if side == "H" else "5"


def event_context(eid):
    return SB.event_context(eid)


def _G(path):
    return SB.sr_get(path) or {}


def season_avg_goals(season_id):
    if not season_id:
        return None, 0
    tables = (_G(f"stats_season_tables/{season_id}").get("tables") or [])
    rows = [r for tb in tables for r in (tb.get("tablerows") or [])]
    if not rows:
        return None, 0
    games = sum(int((r.get("winTotal") or 0) + (r.get("drawTotal") or 0) + (r.get("lossTotal") or 0)) for r in rows)
    goals = sum(int(r.get("goalsForTotal") or 0) for r in rows)
    matches = games / 2.0
    if matches < 1:
        return None, 0
    return goals / matches, matches


def table_pos(season_id):
    tables = (_G(f"stats_season_tables/{season_id}").get("tables") or [])
    rows = [r for tb in tables for r in (tb.get("tablerows") or [])]
    N = max((len(tb.get("tablerows") or []) for tb in tables), default=0)
    return {r["team"]["uid"]: r["pos"] for r in rows if r.get("team")}, N


def last3(uid, before_uts):
    ms = (_G(f"stats_team_lastx/{uid}/60") or _G(f"stats_team_lastx/{uid}")).get("matches") or []
    out = []
    for z in sorted(ms, key=lambda z: -((z.get("time") or {}).get("uts") or 0)):
        if (z.get("time") or {}).get("uts", 0) >= before_uts:
            continue
        out.append(z)
        if len(out) >= 3:
            break
    return out


def form_wins(uid, before_uts):
    L = last3(uid, before_uts)
    wins = 0
    for z in L:
        res = z.get("result") or {}
        h, a = int(res.get("home") or 0), int(res.get("away") or 0)
        home = ((z.get("teams") or {}).get("home") or {}).get("uid") == uid
        if (home and h > a) or ((not home) and a > h):
            wins += 1
    return wins, len(L)


def leg(data, mid, spec, oid, market, selection, odds, case, strategy):
    home = data.get("homeTeamName") or ""
    away = data.get("awayTeamName") or ""
    league = SB.league_of(data)
    ko = SB.kickoff(data)
    return dict(
        eventId=data.get("eventId"), match=f"{home} v {away}", league=league,
        marketId=str(mid), specifier=spec or "", outcomeId=str(oid),
        market=market, selection=selection, odds=float(odds),
        kickoff=ko.isoformat().replace("+00:00", "Z") if ko else None,
        date=ko.date().isoformat() if ko else None,
        ko=ko.strftime("%H:%M") if ko else None,
        case=case, strategy=strategy, result="pending", matchStatus="Not start",
    )


def ah_minus_one(markets, strong_home):
    """Asian Handicap -1 for the stronger side only (market 16, that side's outcome)."""
    want = -1.0 if strong_home else 1.0
    side = "Home" if strong_home else "Away"
    for m in markets or []:
        if str(m.get("id")) != "16":
            continue
        sp = m.get("specifier") or ""
        if "hcp=" not in sp:
            continue
        try:
            hcp = float(sp.split("hcp=")[1].split("|")[0])
        except Exception:
            continue
        if abs(hcp - want) > 0.01:
            continue
        for o in m.get("outcomes") or []:
            desc = str(o.get("desc") or "")
            if not desc.startswith(side):
                continue
            try:
                od = float(o.get("odds") or 0)
            except Exception:
                continue
            if 1.01 < od < 1.90:
                return m, o, od
    return None


def picks_for_event(data, ctx=None):
    """Strategy candidates for one event. `ctx` is event_context plus table/form.

    An empty ctx (what the sr:match lookup produced) cannot satisfy strategies
    2–5 or the league-average leg of strategy 1.
    """
    ctx = ctx or {}
    if not data:
        return []
    home = data.get("homeTeamName") or ""
    away = data.get("awayTeamName") or ""
    league = SB.league_of(data)
    if SB.skip_fixture(home, away, league) or SKIP_EXTRA.search(league or ""):
        return []
    markets = data.get("markets") or []
    out = []
    o25 = outcome(markets, "18", "total=2.5", oid="12", startswith="Over")
    fh15 = outcome(markets, "68", "total=1.5", oid="12", startswith="Over")
    if not fh15:
        fh15 = outcome(markets, "68", "total=1.5", startswith="Over")
    passes = 0
    why = []
    if o25 and 1.20 <= o25[2] <= 1.40:
        passes += 1
        why.append(f"O2.5@{o25[2]}")
    if fh15 and fh15[2] < 2.00:
        passes += 1
        why.append(f"1HO1.5@{fh15[2]}")
    avg, n_matches = ctx.get("avg"), ctx.get("n_matches") or 0
    if avg is not None and n_matches >= 20 and avg > 2.5:
        passes += 1
        why.append(f"avgG={avg:.2f}/n={n_matches:.0f}")
    if o25 and passes >= 2:
        pick = leg(data, "18", "total=2.5", o25[1].get("id") or "12", "Over/Under",
                   o25[1].get("desc") or "Over 2.5", o25[2],
                   f"O2.5 {passes}/3: " + ", ".join(why), "o25-2of3")
        pick["o25Passes"] = passes
        out.append(pick)

    hp, ap, N = ctx.get("hp"), ctx.get("ap"), ctx.get("N") or 0
    hw, hn = ctx.get("hw") or 0, ctx.get("hn") or 0
    aw, an = ctx.get("aw") or 0, ctx.get("an") or 0
    top = (bool(TOP_FLIGHT.search(league or "")) or N >= 16) and N >= 10
    if top and hp and ap:
        clash_top = hp <= 5 and ap <= 5
        clash_bot = hp > N - 3 and ap > N - 3
        if not clash_top and not clash_bot:
            for side, pos_, wins_, nform_, oid, label in (
                ("H", hp, hw, hn, "1", "Home"),
                ("A", ap, aw, an, "3", "Away"),
            ):
                strong = (pos_ is not None and pos_ <= 3) or (nform_ >= 3 and wins_ == 3)
                weak = (pos_ is not None and pos_ > N - 3) or (nform_ >= 3 and wins_ == 0)
                if strong:
                    w = outcome(markets, "1", "", oid=oid)
                    if w and w[2] <= 1.45:
                        out.append(leg(data, "1", "", oid, "1X2", label, w[2],
                                       f"top3/form win @{w[2]} pos={pos_} form={wins_}/{nform_}",
                                       "top3-form-win"))
                    else:
                        dnb_oid = dnb_outcome_id(side)
                        d = outcome(markets, "11", "", oid=dnb_oid)
                        if d:
                            out.append(leg(data, "11", "", d[1].get("id") or dnb_oid, "Draw No Bet",
                                           f"{label} DNB", d[2],
                                           f"top3/form DNB @{d[2]} (win>{1.45})", "top3-form-dnb"))
                if weak:
                    dc_oid = "11" if side == "H" else "9"
                    dc_sel = "Draw or Away" if side == "H" else "Home or Draw"
                    d = outcome(markets, "10", "", oid=dc_oid)
                    if d and not MR.is_dc_vetoed({
                        "marketId": "10", "outcomeId": dc_oid, "odds": d[2],
                        "selection": dc_sel, "market": "Double Chance",
                    }):
                        out.append(leg(data, "10", "", dc_oid, "Double Chance", dc_sel, d[2],
                                       f"bottom3/form DC against {label} @{d[2]}", "bottom3-form-dc"))
        if (hp <= 5 and ap > N - 3) or (ap <= 5 and hp > N - 3):
            strong_home = hp <= 5
            weak_mid = "20" if strong_home else "19"
            weak_o = outcome(markets, weak_mid, "total=0.5", oid="12", startswith="Over")
            if weak_o and weak_o[2] > 1.70:
                out.append(leg(data, weak_mid, "total=0.5", weak_o[1].get("id") or "12",
                                "Team Over/Under", weak_o[1].get("desc") or "Over 0.5", weak_o[2],
                                f"weaker to-score @{weak_o[2]} (top5 v bottom3)", "weaker-score"))
            ah = ah_minus_one(markets, strong_home)
            if ah:
                out.append(leg(data, ah[0].get("id"), ah[0].get("specifier") or "", ah[1].get("id"),
                                ah[0].get("desc") or "Asian Handicap", ah[1].get("desc") or "AH -1", ah[2],
                                f"stronger AH-1 @{ah[2]} (top5 v bottom3)", "ah-minus1-screen"))
    x12, _, _, _ = SB.x12_of(markets)
    if hp and ap and N:
        table = f"{hp} v {ap}/{N}"
    else:
        table = ""
    for p in out:
        if x12:
            p["x12"] = x12
        if table:
            p["table"] = table
    return out


def gate_ok(p, enrich=True):
    """Normal Predict2u gate. Enrich only when table/1X2 are still missing."""
    if enrich and not (p.get("table") and p.get("x12")):
        try:
            MR.enrich(p)
        except Exception:
            pass
    if MR.is_btts_no(p) or MR.is_dc_vetoed(p) or MR.is_obscure_league_non_goals(p):
        ok, cls, why = MR.check(p)
        p["matchup"] = cls
        p["gateWhy"] = why
        return False
    ok, cls, why = MR.check(p)
    p["matchup"] = cls
    p["gateWhy"] = why
    return bool(ok)


def resolve_one(picks):
    """One pick per match among legs that already passed the gate.

    DC beats a win/DNB. Over 2.5 with 3/3 conditions beats a result pick.
    Over 2.5 with only 2/3 loses to a result pick that itself cleared the gate.
    A result pick the gate rejected does not hide a legal Over 2.5.
    """
    main = [p for p in picks if p.get("strategy") in ("o25-2of3", "top3-form-win", "top3-form-dnb", "bottom3-form-dc")]
    screens = [p for p in picks if p.get("strategy") in ("weaker-score", "ah-minus1-screen")]
    dc = [p for p in main if p.get("strategy") == "bottom3-form-dc"]
    win = [p for p in main if p.get("strategy") in ("top3-form-win", "top3-form-dnb")]
    o25 = [p for p in main if p.get("strategy") == "o25-2of3"]
    chosen = None
    if dc:
        chosen = dc[0]
    elif win:
        chosen = win[0]
    if o25:
        if chosen is None or o25[0].get("o25Passes", 0) >= 3:
            chosen = o25[0]
    out = []
    if chosen:
        out.append(chosen)
    out.extend(screens)
    return out


def _ctx_for(eid, data):
    ctx = event_context(eid)
    season = ctx.get("season")
    avg, n_matches = season_avg_goals(season) if season else (None, 0)
    pos, N = table_pos(season) if season else ({}, 0)
    hu, au = ctx.get("hu"), ctx.get("au")
    ts = data.get("estimateStartTime") or 0
    before = ts // 1000 if ts else int(dt.datetime.now(dt.timezone.utc).timestamp())
    hw, hn = form_wins(hu, before) if hu else (0, 0)
    aw, an = form_wins(au, before) if au else (0, 0)
    ctx.update(avg=avg, n_matches=n_matches, hp=pos.get(hu), ap=pos.get(au), N=N,
               hw=hw, hn=hn, aw=aw, an=an)
    return ctx


def build_pool(days=4, ids=None, fetch=None):
    import concurrent.futures as cf
    ids = list(upcoming_ids(days) if ids is None else ids)
    fetch = fetch or SB.fetch_event
    print(f"three_strategies: scanning {len(ids)} events (days={days})", flush=True)
    with cf.ThreadPoolExecutor(12) as ex:
        evs = list(ex.map(fetch, ids))
    pool = []
    diag = dict(events=0, no_data=0, raw=0, gated=0, dropped=0)
    live = [(eid, data) for eid, data in zip(ids, evs) if data]
    diag["no_data"] = len(ids) - len(live)
    diag["events"] = len(live)

    def _one(item):
        eid, data = item
        return data, _ctx_for(eid, data)

    with cf.ThreadPoolExecutor(12) as ex:
        ready = list(ex.map(_one, live))
    for data, ctx in ready:
        raw = picks_for_event(data, ctx)
        diag["raw"] += len(raw)
        kept = []
        for p in raw:
            if gate_ok(p):
                kept.append(p)
            else:
                diag["dropped"] += 1
        kept = resolve_one(kept)
        diag["gated"] += len(kept)
        pool.extend(kept)
    print("three_strategies diag", diag, flush=True)
    return pool


def upcoming_ids(days=4):
    return SB.upcoming_ids(days)


def one_per_match(pool):
    by = {}
    pri = {"bottom3-form-dc": 3, "top3-form-win": 2, "top3-form-dnb": 2, "o25-2of3": 1}.get
    for p in pool:
        eid = p["eventId"]
        cur = by.get(eid)
        if not cur or pri(p.get("strategy"), 0) > pri(cur.get("strategy"), 0):
            by[eid] = p
    return list(by.values())


def book_masters(pool, day, book=True):
    now = dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")
    main = [p for p in pool if p.get("strategy") in ("o25-2of3", "top3-form-win", "top3-form-dnb", "bottom3-form-dc")]
    main = [p for p in one_per_match(main) if p.get("kickoff") and p["kickoff"] > now]
    main.sort(key=lambda p: float(p["odds"]))
    # Never pad to 50. ASC = lowest odds, DESC = highest, each capped at 50.
    asc = main[:50]
    desc = list(reversed(main[-50:])) if main else []
    screens = [p for p in pool if p.get("strategy") in ("weaker-score", "ah-minus1-screen")]
    screens = [p for p in screens if p.get("kickoff") and p["kickoff"] > now]
    # Screens are a second market on a top5-v-bottom3 game. Keep one per event.
    screens = one_per_match(screens)
    out = []

    def publish(name, key, legs):
        if not legs:
            return
        legs = sorted(legs, key=lambda p: p.get("kickoff") or "")[:50]
        prod = math.prod(float(p["odds"]) for p in legs)
        # 25+25 only when each half can stand as its own code. A short pool is one slip.
        if len(legs) >= 50:
            chunks = [("first 25", legs[:25]), ("second 25", legs[25:50]), ("master", legs[:50])]
        else:
            chunks = [("set", legs)]
        rec = dict(
            key=key, name=name, date=day, riskLabel="HIGH RISK", waived=False,
            meetsFloor=prod >= 25,
            verification="Bets For The Day. Normal Predict2u gates applied. HIGH RISK, no guarantees.",
            parts=[], legList=legs, legs=len(legs), totalOdds=round(prod, 2),
        )
        for role, L in chunks:
            if not L:
                continue
            if book:
                pt = SC.book_part(L, f"{name} · {role}")
            else:
                pt = dict(name=f"{name} · {role}", legs=len(L), events=[p["eventId"] for p in L],
                          totalOdds=round(math.prod(float(p["odds"]) for p in L), 2), codes={}, missing={})
            pt["label"] = f"{name} · {role} · HIGH RISK"
            pt["source"] = key
            pt["meetsFloor"] = math.prod(float(p["odds"]) for p in L) >= 25
            rec["parts"].append(pt)
            print(name, role, len(L), pt["totalOdds"],
                  {b: L_[0]["code"] for b, L_ in (pt.get("codes") or {}).items() if L_}, flush=True)
        path = ENGINE_DIR / "data" / "ho-masters" / f"{day}-{key}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        if book:
            json.dump(rec, open(path, "w"), indent=1, ensure_ascii=False, default=str)
            out.append(path)
        else:
            out.append(rec)
        return rec

    publish("Ascending odds", "asc", asc)
    # DESC is the 50 highest. When the pool is at most 50 that is the same
    # leg set as ASC (only the order changes) and the share API returns the
    # same code. Book it only when the sets differ.
    if desc and {p["eventId"] for p in desc} != {p["eventId"] for p in asc}:
        publish("Descending odds", "desc", desc)
    if screens:
        publish("Top5 v Bottom3 screens", "t5b3-screens", screens)
    return out


def main(days=4, book=True):
    day = dt.datetime.now(dt.timezone.utc).date().isoformat()
    pool = build_pool(days=days)
    print("pool", len(pool), "by strategy:", {
        k: sum(1 for p in pool if p.get("strategy") == k)
        for k in ("o25-2of3", "top3-form-win", "top3-form-dnb", "bottom3-form-dc", "weaker-score", "ah-minus1-screen")
    })
    paths = book_masters(pool, day, book=book)
    print("wrote", [str(p) for p in paths])
    return 0


if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else "4"
    sys.exit(main(int(arg)))
