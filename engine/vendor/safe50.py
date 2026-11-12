#!/usr/bin/env python3
"""Safest market — one 1.20–1.60 selection per not-started match, Hot page.

For each not-started SportyBet match inside the 4-day window, score every
open market and keep the single selection in 1.20–1.60 with the highest
de-vigged fair probability. Two-way goals markets are preferred. Exotic and
extreme lines are dropped. Women, youth, reserve/B, amateur and university
sides are excluded. Lower leagues are goals-only.

Stats, table and form then have to agree (a sample under 55% for the line
is dropped; a pick with no stats at all is dropped). The normal Predict2u
gate runs after that, including the 1.30 cap on Over 1.5 / Under 3.5.
The best 50 are booked. A 50-leg master is split into two 25-leg codes.
Fewer than 50 is not padded. A remainder whose combined odds are under 25
is not booked as its own code.

  python engine/vendor/safe50.py
  python engine/vendor/safe50.py --dry-run
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
sys.path[:0] = [str(HERE), str(HERE.parent), str(HERE.parent.parent)]

import matchup_rules as MR
import publish_hot as PH
import sb_common as SB
from engine.paths import ENGINE_DIR, REPO_DIR

ODDS_LO, ODDS_HI = 1.20, 1.60
BAD = re.compile(
    r"corner|booking|card|shot|offside|foul|odd/even|exact|multi|clean sheet|"
    r"both halves|highest scoring|asian handicap|handicap|halftime/fulltime|"
    r"correct score|to score in both|win to nil|lead by|from behind|early goals|"
    r"winning margin|goal bounds|1up|2up|excluded|never down|in a row",
    re.I,
)
GOAL = re.compile(r"over/under", re.I)
NOT_PLAIN_GOALS = re.compile(
    r"&|early|corner|booking|card|shot|offside|foul|exact|multi|odd|even|"
    r"handicap|1x2|draw no|double chance|gg|btts|clean|score|asian",
    re.I,
)


def is_plain_goals(desc: str) -> bool:
    return bool(GOAL.search(desc or "")) and not NOT_PLAIN_GOALS.search(desc or "")


def extreme_line(spec, outcome, desc) -> int:
    """0 normal, 1 soft (Under 4 / half Over 0.5), 2 exotic (dropped)."""
    try:
        tot = float((spec or "total=2.5").split("=")[-1])
    except Exception:
        return 0
    oc = outcome or ""
    half = "Half" in (desc or "") or "half" in (desc or "")
    if oc.startswith("Under") and tot >= 4.5:
        return 2
    if oc.startswith("Under") and tot >= 4.0:
        return 1
    if oc.startswith("Over") and tot <= 0.5 and not half:
        return 2
    if oc.startswith("Over") and tot <= 0.5:
        return 1
    return 0


def score_event(data):
    """Best 1.20–1.60 selection on one event, or None. No stats yet."""
    if not data or not SB.in_window(data):
        return None
    home = data.get("homeTeamName") or ""
    away = data.get("awayTeamName") or ""
    league = SB.league_of(data)
    if SB.skip_fixture(home, away, league):
        return None
    lower = not MR.is_major_league(league)
    x12, _, _, _ = SB.x12_of(data.get("markets") or [])
    cands = []
    for m in data.get("markets") or []:
        if m.get("status") not in (0, None):
            continue
        desc = m.get("desc") or m.get("name") or ""
        if BAD.search(desc):
            continue
        spec = m.get("specifier") or ""
        outs = [o for o in (m.get("outcomes") or []) if o.get("isActive") in (1, None, "1")]
        if len(outs) < 2:
            continue
        goals = is_plain_goals(desc)
        if lower and not goals:
            continue
        if not lower and not (goals or desc in ("1X2", "Draw No Bet", "Double Chance")):
            continue
        try:
            inv = [1 / float(o["odds"]) for o in outs]
        except Exception:
            continue
        s = sum(inv)
        if s <= 0:
            continue
        for o, raw in zip(outs, inv):
            try:
                odds = float(o["odds"])
            except Exception:
                continue
            if not (ODDS_LO <= odds <= ODDS_HI):
                continue
            ext = extreme_line(spec, o.get("desc") or "", desc)
            if ext >= 2:
                continue
            # DC 12 is never a candidate. 1X/X2 above 1.35 is dropped here too.
            pick = dict(
                eventId=data.get("eventId"), match=f"{home} v {away}", league=league,
                marketId=str(m.get("id")), specifier=spec, outcomeId=str(o.get("id")),
                market=desc, selection=o.get("desc") or "", odds=odds,
                fair=raw / s, twoway=len(outs) == 2, goals=goals, ext=ext, lower=lower,
                x12=x12 or "",
            )
            if MR.is_btts_no(pick) or MR.is_dc_vetoed(pick):
                continue
            cands.append(pick)
    if not cands:
        return None
    cands.sort(key=lambda p: (-p["fair"], p["ext"], 0 if p["twoway"] else 1, 0 if p["goals"] else 1, p["odds"]))
    best = cands[0]
    ko = SB.kickoff(data)
    best.update(
        kickoff=ko.isoformat().replace("+00:00", "Z") if ko else None,
        date=ko.date().isoformat() if ko else None,
        ko=ko.strftime("%H:%M") if ko else None,
        result="pending", matchStatus="Not start",
        alts=len(cands),
    )
    return best


def _rates(sample):
    if not sample:
        return None
    n = len(sample)
    tot = o15 = o25 = u35 = u4 = 0
    for h, a in sample:
        g = h + a
        tot += g
        o15 += g >= 2
        o25 += g >= 3
        u35 += g <= 3
        u4 += g < 4
    return dict(n=n, avg=tot / n, o15=o15 / n, o25=o25 / n, u35=u35 / n, u4=u4 / n)


def line_supported(pick, samples) -> tuple[bool, str]:
    """False when every available sample contradicts the line, or there is no sample."""
    usable = [s for s in samples if s and s.get("n")]
    if not usable:
        return False, "no stats"
    spec = pick.get("specifier") or ""
    sel = pick.get("selection") or ""
    desc = pick.get("market") or ""
    if "Over/Under" not in desc or "total=" not in spec:
        # 1X2 / DNB: require a table (attached by the caller) rather than a goal rate.
        return bool(pick.get("table")), "no table" if not pick.get("table") else "table"
    try:
        line = float(spec.split("=")[-1])
    except Exception:
        return False, "bad line"
    under = sel.startswith("Under")
    over = sel.startswith("Over")
    if under and line >= 4:
        key = "u4"
    elif under and line >= 3.5:
        key = "u35"
    elif over and line <= 1.5:
        key = "o15"
    elif over and line <= 2.5:
        key = "o25"
    else:
        key = "avg"
    if key == "avg":
        avg = sum(s["avg"] for s in usable) / len(usable)
        if over and avg < line * 0.7:
            return False, f"avg {avg:.2f} soft for over {line}"
        if under and avg > line:
            return False, f"avg {avg:.2f} soft for under {line}"
        return True, f"avg {avg:.2f}"
    hit = sum(s[key] for s in usable) / len(usable)
    if hit < 0.55:
        return False, f"{key} {hit:.0%} < 55%"
    return True, f"{key} {hit:.0%}"


def form_samples(eid):
    """Home/away recent match totals from Sportradar. Empty when the id does not resolve."""
    ctx = SB.event_context(eid)
    hu, au, season = ctx.get("hu"), ctx.get("au"), ctx.get("season")
    table = ""
    if season and hu and au:
        d = SB.sr_get(f"stats_season_tables/{season}") or {}
        tables = d.get("tables") or []
        pos = {}
        N = 0
        for tb in tables:
            rs = tb.get("tablerows") or []
            N = max(N, len(rs))
            for r in rs:
                uid = (r.get("team") or {}).get("uid")
                if uid is not None:
                    pos[uid] = r.get("pos")
        if pos.get(hu) and pos.get(au) and N:
            table = f"{pos[hu]} v {pos[au]}/{N}"

    def totals(uid, home):
        if not uid:
            return []
        ms = (SB.sr_get(f"stats_team_lastx/{uid}") or {}).get("matches") or []
        out = []
        for z in sorted(ms, key=lambda z: -((z.get("time") or {}).get("uts") or 0)):
            res = z.get("result") or {}
            if res.get("home") is None:
                continue
            is_home = ((z.get("teams") or {}).get("home") or {}).get("uid") == uid
            if is_home != home:
                continue
            out.append((int(res.get("home") or 0), int(res.get("away") or 0)))
            if len(out) >= 8:
                break
        return out

    samples = []
    for uid, home in ((hu, True), (au, False)):
        r = _rates(totals(uid, home))
        if r:
            samples.append(r)
    return samples, table


def apply_sanity_and_gate(pick, samples, table):
    if table:
        pick["table"] = table
    ok, why = line_supported(pick, samples)
    pick["sanity"] = why
    if not ok:
        pick["gateWhy"] = why
        return False
    try:
        if not (pick.get("table") and pick.get("x12")):
            MR.enrich(pick)
    except Exception:
        pass
    passed, cls, reason = MR.check(pick)
    pick["matchup"] = cls
    pick["gateWhy"] = reason
    return bool(passed)


def rank(picks):
    return sorted(picks, key=lambda p: (-float(p.get("fair") or 0), int(p.get("ext") or 0), p.get("kickoff") or ""))


def split_plan(legs):
    """50 → master + two 25s. Shorter pools are not padded.

    A part is booked on its own only when its combined odds reach 25.
    A short remainder stays inside the master and is not a separate code.
    """
    legs = rank(legs)[:50]
    plan = [("Safest market", legs)]
    if len(legs) >= 50:
        a, b = legs[:25], legs[25:50]
        if _prod(a) >= 25:
            plan.append(("Safest market · part 1", a))
        if _prod(b) >= 25:
            plan.append(("Safest market · part 2", b))
    elif len(legs) > 25:
        a, b = legs[:25], legs[25:]
        if _prod(a) >= 25:
            plan.append(("Safest market · part 1", a))
        if _prod(b) >= 25:
            plan.append(("Safest market · part 2", b))
    return plan


def _prod(legs):
    if not legs:
        return 0.0
    return math.prod(float(p["odds"]) for p in legs)


def to_slip(name, legs, codes, day, strategy):
    prod = round(_prod(legs), 2)
    return dict(
        name=name, strategy=strategy, date=day, label=name,
        legs=len(legs), totalOdds=prod, meetsFloor=prod >= 25,
        picks=legs, events=[p["eventId"] for p in legs], codes=codes,
        result="pending", status="pending",
        note=None if prod >= 25 else "Under 25 combined odds. Not padded.",
        verification="Safest open 1.20–1.60 selection by de-vigged probability. Normal Predict2u gates.",
    )


def run(days=4, book=True, publish=True, limit_stats=180):
    import concurrent.futures as cf
    day = dt.datetime.now(dt.timezone.utc).date().isoformat()
    ids = SB.upcoming_ids(days)
    print(f"safe50: {len(ids)} events in {days} days", flush=True)
    with cf.ThreadPoolExecutor(12) as ex:
        events = list(ex.map(SB.fetch_event, ids))
    raw = []
    for data in events:
        p = score_event(data)
        if p:
            raw.append(p)
    raw = rank(raw)
    print(f"safe50 priced {len(raw)}", flush=True)
    # Stats are expensive. Check the highest-fair picks until 50 survive or the list ends.
    kept = []
    dropped = []
    checked = 0
    for p in raw:
        if len(kept) >= 50:
            break
        if checked >= max(limit_stats, 50):
            break
        checked += 1
        samples, table = form_samples(p["eventId"])
        if apply_sanity_and_gate(p, samples, table):
            kept.append(p)
        else:
            dropped.append({"match": p.get("match"), "selection": p.get("selection"), "reason": p.get("gateWhy") or p.get("sanity")})
    kept = rank(kept)[:50]
    print(f"safe50 kept {len(kept)} dropped {len(dropped)} checked {checked}", flush=True)
    slips = []
    for i, (name, legs) in enumerate(split_plan(kept)):
        strategy = "safe50" if i == 0 else f"safe50-part{i}"
        codes = PH.book_legs(legs) if book else {}
        if book and not codes:
            print("safe50 no code for", name, flush=True)
            continue
        slips.append(to_slip(name, legs, codes, day, strategy))
        print(name, len(legs), round(_prod(legs), 2), {b: v[0]["code"] for b, v in codes.items()}, flush=True)
    if publish and book:
        PH.upsert_model_slips(REPO_DIR, slips, replace_strategies={s["strategy"] for s in slips} | {"safe50", "safe50-part1", "safe50-part2"})
        path = ENGINE_DIR / "data" / "safe50" / f"{day}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        json.dump({"date": day, "kept": len(kept), "dropped": dropped[:80],
                   "slips": [{k: s[k] for k in ("name", "strategy", "legs", "totalOdds", "meetsFloor", "codes")} for s in slips]},
                  open(path, "w"), indent=1, ensure_ascii=False)
    return {"day": day, "slips": slips, "dropped": dropped, "kept": len(kept)}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--days", type=int, default=4)
    args = ap.parse_args(argv)
    out = run(days=args.days, book=not args.dry_run, publish=not args.dry_run)
    print(json.dumps({"kept": out["kept"], "slips": [
        {"name": s["name"], "legs": s["legs"], "odds": s["totalOdds"],
         "codes": {b: v[0]["code"] for b, v in (s.get("codes") or {}).items()}}
        for s in out["slips"]
    ]}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
