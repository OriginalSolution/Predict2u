#!/usr/bin/env python3
"""Nightly MASTER PIPELINE (22:45 GMT): rebuild next-day master codes from the night's engine codes.

Spec from Betting Strategies (NerdyTips), 19 Nov 2026, mirroring the codes booked by hand that day
(master EF56AX -> league-fit EJE4X9/8NN7CD -> U4.5 swaps 8YLN1H/FVNVRE -> odds halves C2NAPA/8Q627K
-> 1.42 split 8K9NGE/FFPGB0; >1.45 swaps AEMP9Z/8HN6J7; market codes CJEL25/CKHKHQ).

1) MASTER POOL: every SportyBet code already published for the target day (high_odds.json + strategy
   records), minus this pipeline's own output. One leg per match; on a clash the STRONGER code wins:
   strategy priority (STRENGTH), then the code with the lower geometric-mean leg price (higher
   per-leg implied probability). Started / unlisted games are dropped, prices refreshed from SportyBet.
   No DC, no NG anywhere. No cap on the pool.
2) LEAGUE-FIT: same rule as sure80_reverse: drop a leg priced > 1.08 x the median of that market in its
   league that day (>= 2 other fixtures). Solo legs without league peers are KEPT here.
3) U4.5 -> OVERS: Under 4.5 -> Over 2.5 when league >= 2.8 gpg, both teams' last 10 >= 60% over 2.5 and
   O2.5 <= 1.50; else -> Over 1.5 when league >= 2.5 gpg, both teams' last 10 >= 80% over 1.5 and
   O1.5 >= 1.15; else keep U4.5.
4) >1.45 SWAP: a leg above 1.45 is replaced on the same match by the first supported alternative
   <= 1.45 (>= 1.15, league-fit, data estimate > 80%) from ALTERNATIVES; no DC/NG/GG. Else dropped.
5) OUTPUT CODES (each needs >= 25 total odds; never padded; skipped codes are logged):
   a) Master Early / Master Late: pool by kick-off, halves of at most 35 legs (earliest 35 / latest 35).
   b) Low Odds / High Odds: lowest-priced half ascending / highest-priced half descending, 35 legs max each.
   c) Master <=1.42 (THE Master) and Above 1.42; more than 50 legs is dealt round-robin into <= 50-leg parts.
   d) Market groups: one code per market type, <= 25 legs per code (larger groups dealt round-robin).
Every code is HIGH RISK, SportyBet GH share code (no-login) with read-back. Never places a bet.
The pipeline's codes are derived from codes already booked, so they do not count toward the
2-codes-per-match usage of the strategy jobs (otherwise GG/NYSM/NT at 23:10+ would find no matches).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import os
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parent)]
import strategy_lib as lib  # noqa: E402
import sure80_reverse as sr  # noqa: E402

KIND = "pipeline"
OWN_PREFIX = "strategy-mp-"
HALF_CAP = 35
SLIP_CAP = 50          # engine rule: a code above 50 legs is split into <= 50-leg parts
GROUP_CAP = 25
SWAP_MAX = 1.45
SPLIT_AT = 1.42
MIN_ALT = 1.15
O25_GPG, O15_GPG = 2.8, 2.5
O25_TEAM, O15_TEAM = 0.60, 0.80
# Stronger code first. Unknown origins rank last; ties go to the lower geometric-mean leg price.
STRENGTH = ["sure80", "nt", "nysm-conservative", "nysm-main", "nysm-ts2", "gg", "rev-u45",
            "rev-u45-draw", "ttw", "form80", "mo25", "ah1", "hs15", "master", "sb-morning-master", "ho-master", "code-hub"]
ALTERNATIVES = {
    "o25": ["o15"], "u35": ["u45", "u55"], "u45": ["u55"],
    "h_o05": ["o15"], "a_o05": ["o15"], "h_o15": ["h_o05", "o15"], "a_o15": ["a_o05", "o15"],
    "home": ["dnb_home", "h_o05"], "away": ["dnb_away", "a_o05"],
    "dnb_home": ["h_o05"], "dnb_away": ["a_o05"], "gg": ["o15"], "o15": ["h_o05", "a_o05"],
}
GROUP_LABEL = {
    "o15": "Over 1.5 Group", "o25": "Over 2.5 Group", "u35": "Under 3.5 Group", "u45": "Under 4.5 Group",
    "u55": "Under 5.5 Group", "team_o05": "Team Over 0.5 Group", "team_o15": "Team Over 1.5 Group",
    "win": "Win Group", "dnb": "Draw No Bet Group", "gg": "GG Group",
}
KEY_TO_NAME = {v: k for k, v in sr.O.items()}


# ------------------------------------------------------------------ pure helpers
def leg_key(leg: dict) -> str:
    return f"{leg.get('marketId')}|{leg.get('specifier') or ''}|{leg.get('outcomeId')}"


def group_of(name: str | None, leg: dict) -> str:
    if name in ("h_o05", "a_o05"):
        return "team_o05"
    if name in ("h_o15", "a_o15"):
        return "team_o15"
    if name in ("home", "away"):
        return "win"
    if name in ("dnb_home", "dnb_away"):
        return "dnb"
    return name or f"m{leg.get('marketId')}"


def banned(leg: dict) -> bool:
    """No NG, no DC anywhere in the pipeline."""
    return lib.is_ng(leg) or str(leg.get("marketId")) in {"10", "60110"} or "double chance" in str(leg.get("market") or "").lower()


def strength(slip: dict) -> tuple:
    kind = str(slip.get("origin") or "").replace("strategy-", "")
    rank = STRENGTH.index(kind) if kind in STRENGTH else len(STRENGTH)
    prices = [float(leg.get("odds") or 0) for leg in slip.get("legs") or [] if float(leg.get("odds") or 0) > 1]
    geo = math.exp(sum(math.log(p) for p in prices) / len(prices)) if prices else 99.0
    return (rank, round(geo, 4))


def build_pool(slips: list[dict], day: str) -> tuple[list[dict], dict]:
    """Step 1: one leg per match from the stronger code. Returns (legs, log)."""
    log = {"codes": 0, "legs_in": 0, "clashes": 0, "dupes": 0, "banned": 0}
    chosen: dict[str, tuple] = {}
    for slip in sorted(slips, key=strength):
        if not slip.get("code") or str(slip.get("origin") or "").startswith(OWN_PREFIX):
            continue
        log["codes"] += 1
        for leg in slip.get("legs") or []:
            if not leg.get("eventId") or str(leg.get("date") or leg.get("kickoff") or "")[:10] != day:
                continue
            log["legs_in"] += 1
            if banned(leg):
                log["banned"] += 1
                continue
            eid = leg["eventId"]
            if eid in chosen:
                if leg_key(chosen[eid][0]) == leg_key(leg):
                    log["dupes"] += 1
                else:
                    log["clashes"] += 1   # weaker code loses (slips are walked strongest first)
                continue
            chosen[eid] = (dict(leg, sourceCode=slip["code"], sourceOrigin=slip.get("origin")), slip)
    return [pair[0] for pair in chosen.values()], log


def refresh(legs: list[dict], events: dict) -> tuple[list[dict], int]:
    """Drop started/unlisted games and legs whose outcome is gone; take the live price."""
    out, dropped = [], 0
    for leg in legs:
        row = events.get(leg["eventId"])
        key = odds_key(leg, row["odds"]) if row else None
        if not key:
            dropped += 1
            continue
        out.append(dict(leg, odds=row["odds"][key][0], _name=KEY_TO_NAME.get(key), _league=row["league"], _odds=row["odds"]))
    return out, dropped


def medians_by_key(rows: list[dict]) -> dict:
    out: dict = {}
    for row in rows:
        for key, (price, _) in row["odds"].items():
            out.setdefault((row["league"], key), []).append((row["eventId"], price))
    return out


def fits(league: str, eid: str, key: str, price: float, medians: dict) -> tuple[bool, float | None]:
    """8% league-fit; solo legs (fewer than 2 peers) are kept."""
    others = [p for e, p in medians.get((league, key), []) if e != eid]
    if len(others) < sr.LEAGUE_FIT_MIN_N:
        return True, None
    med = statistics.median(others)
    return price <= med * sr.LEAGUE_FIT_RATIO, round(med, 3)


def odds_key(leg: dict, odds: dict) -> str | None:
    """The live 'marketId|specifier|desc' key holding this leg's outcome."""
    head = f"{leg.get('marketId')}|{leg.get('specifier') or ''}|"
    for key, (_, oid) in odds.items():
        if key.startswith(head) and str(oid) == str(leg.get("outcomeId")):
            return key
    return None


def league_fit_step(legs: list[dict], medians: dict) -> tuple[list[dict], list[str]]:
    """Step 2. legs carry `_league` and `_odds` (live prices for the match)."""
    kept, dropped = [], []
    for leg in legs:
        key = odds_key(leg, leg.get("_odds") or {}) or leg_key(leg)
        ok, med = fits(leg["_league"], leg["eventId"], key, leg["odds"], medians)
        if ok:
            kept.append(dict(leg, leagueMedian=med))
        else:
            dropped.append(f"{leg.get('match')} {leg.get('selection')} @{leg['odds']} > median {med}")
    return kept, dropped


def team_rate(stats: dict, line: float) -> tuple[float, float] | None:
    home, away = (stats or {}).get("home") or [], (stats or {}).get("away") or []
    if len(home) < sr.TEAM_MIN_N or len(away) < sr.TEAM_MIN_N:
        return None
    rate = lambda rows: sum(1 for g in rows if g[0] + g[1] > line) / len(rows)  # noqa: E731
    return rate(home), rate(away)


def u45_to_overs(name: str | None, odds: dict, gpg: float | None, stats: dict | None) -> str | None:
    """Step 3: the replacement market for an Under 4.5 leg, or None to keep U4.5."""
    if name != "u45" or gpg is None:
        return None
    o25, o15 = sr.price(odds, "o25"), sr.price(odds, "o15")
    r25 = team_rate(stats, 2.5)
    if gpg >= O25_GPG and r25 and min(r25) >= O25_TEAM and o25 and o25 <= 1.50:
        return "o25"
    r15 = team_rate(stats, 1.5)
    if gpg >= O15_GPG and r15 and min(r15) >= O15_TEAM and o15 and o15 >= MIN_ALT:
        return "o15"
    return None


def swap_alternative(name: str | None, odds: dict, stats: dict | None, fit) -> str | None:
    """Step 4: first supported alternative <= 1.45 for a leg above 1.45, else None (drop).

    `fit(name, price) -> bool` is the league-fit check for this match.
    """
    for alt in ALTERNATIVES.get(name or "", []):
        if alt == "gg":
            continue
        price = sr.price(odds, alt)
        if price is None or not (MIN_ALT <= price <= SWAP_MAX) or not fit(alt, price):
            continue
        p = sr.estimate(alt, stats or {})
        if p is not None and p > sr.SURE_MIN:
            return alt
    return None


def deal(legs: list[dict], cap: int) -> list[list[dict]]:
    """Split into the fewest parts of <= cap legs, booking as many legs as possible.

    Two candidates: dealt round-robin (similar odds per part) or cut in order (first `cap`, next `cap`, ...).
    The one whose parts reaching 25 odds hold more legs wins; ties go to round-robin.
    """
    if len(legs) <= cap:
        return [list(legs)]
    n = math.ceil(len(legs) / cap)
    dealt = [legs[i::n] for i in range(n)]
    cut = [legs[i:i + cap] for i in range(0, len(legs), cap)]

    def score(parts):
        return sum(len(p) for p in parts if lib.product(leg["odds"] for leg in p) >= lib.MIN_TOTAL)
    return dealt if score(dealt) >= score(cut) else cut


def bookable(legs: list[dict], cap: int) -> bool:
    return bool(legs) and len(legs) <= cap and lib.product(leg["odds"] for leg in legs) >= lib.MIN_TOTAL


def outputs(pool: list[dict]) -> tuple[list[dict], list[dict]]:
    """Step 5: (codes, skipped). Each code = {"id", "label", "legs"}; skipped carries the reason."""
    codes, skipped = [], []

    def add(cid, label, legs, cap):
        legs = list(legs)
        if not legs:
            skipped.append({"id": cid, "label": label, "n": 0, "reason": "no legs"})
        elif bookable(legs, cap):
            codes.append({"id": cid, "label": label, "legs": legs})
        else:
            total = lib.product(leg["odds"] for leg in legs)
            skipped.append({"id": cid, "label": label, "n": len(legs), "total": round(total, 2),
                            "reason": f"under {lib.MIN_TOTAL:g}" if total < lib.MIN_TOTAL else f"over {cap} legs"})

    def parts(cid, label, legs):
        legs = list(legs)
        if len(legs) <= SLIP_CAP:
            add(cid, label, legs, SLIP_CAP)
            return
        for i, part in enumerate(deal(legs, SLIP_CAP), 1):
            add(f"{cid}-{i}", f"{label} {i}", part, SLIP_CAP)

    by_ko = sorted(pool, key=lambda leg: (leg.get("kickoff") or "", leg["eventId"]))
    half = math.ceil(len(by_ko) / 2)
    add("mp-early", "Master Early", by_ko[:half][:HALF_CAP], HALF_CAP)
    add("mp-late", "Master Late", by_ko[half:][-HALF_CAP:], HALF_CAP)
    by_price = sorted(pool, key=lambda leg: (leg["odds"], leg["eventId"]))
    lo, hi = by_price[:half], by_price[half:]
    add("mp-low", "Low Odds", lo[:HALF_CAP], HALF_CAP)
    add("mp-high", "High Odds", sorted(hi, key=lambda leg: -leg["odds"])[:HALF_CAP], HALF_CAP)
    parts("mp-master", "Master <=1.42", [leg for leg in by_price if leg["odds"] <= SPLIT_AT])
    parts("mp-above", "Above 1.42", [leg for leg in by_price if leg["odds"] > SPLIT_AT])
    groups: dict[str, list] = {}
    for leg in by_price:
        groups.setdefault(group_of(leg.get("_name"), leg), []).append(leg)
    for group, legs in sorted(groups.items()):
        label = GROUP_LABEL.get(group, f"Market {group} Group")
        chunks = deal(legs, GROUP_CAP)
        for i, chunk in enumerate(chunks, 1):
            suffix = f" {i}" if len(chunks) > 1 else ""
            add(f"mp-grp-{group}{suffix.strip() and '-' + suffix.strip()}", label + suffix, chunk, GROUP_CAP)
    return codes, skipped


# ------------------------------------------------------------------ network glue
def day_slips(repo: Path, day: str) -> list[dict]:
    slips = []
    try:
        doc = json.loads((repo / "high_odds.json").read_text())
        slips += [s for s in doc.get("slips") or [] if str(s.get("book") or s.get("bookmaker") or "").lower() == "sportybet"]
    except Exception:
        pass
    root = repo / "engine" / "data" / "strategy-codes"
    for path in root.glob(f"*/{day}.json"):
        if path.parent.name == KIND:
            continue
        try:
            rec = json.loads(path.read_text())
        except Exception:
            continue
        booked = rec.get("booked")
        rows = booked if isinstance(booked, list) else [booked] if isinstance(booked, dict) else []
        for b in rows:
            if b and b.get("code") and b.get("legs"):
                slips.append({"code": b["code"], "origin": f"strategy-{path.parent.name}", "legs": b["legs"]})
    seen, out = set(), []
    for s in slips:
        if s.get("code") and s["code"] not in seen:
            seen.add(s["code"])
            out.append(s)
    return out


def simulated_slips(day: dt.date, repo: Path, rows: list[dict]) -> list[dict]:
    """Dry-run input when tonight's codes do not exist yet: the 80% Sure / Reverse dry-run codes."""
    found = sr.select_all(rows, {}, lib.load_usage(repo, day.isoformat()))
    slips = []
    for kind in sr.KINDS:
        for i, part in enumerate(sr.split_codes(found[kind]["legs"]), 1):
            slips.append({"code": f"SIM-{kind}-{i}", "origin": f"strategy-{kind}", "legs": part})
    return slips


def run(day: dt.date, repo: Path, dry_run: bool = False, simulate: bool = False) -> dict:
    ds = day.isoformat()
    rows, _ = sr.load_rows(day)
    slips = simulated_slips(day, repo, rows) if simulate else day_slips(repo, ds)
    pool, log = build_pool(slips, ds)
    events = {row["eventId"]: row for row in rows}
    pool, log["started_or_gone"] = refresh(pool, events)
    medians = medians_by_key(rows)
    pool, log["league_fit_dropped"] = league_fit_step(pool, medians)
    cache, memo, final, swaps = {}, {}, [], {"u45": 0, "swap": 0, "drop": 0}
    for leg in pool:
        odds, row = leg["_odds"], events[leg["eventId"]]
        name = leg.get("_name")
        info = None
        if name == "u45" or leg["odds"] > SWAP_MAX:
            info = sr.fetch_stats(leg["eventId"], cache)
        if name == "u45":
            gpg = sr.season_gpg(info["sid"], cache, memo)[0] if info.get("sid") else None
            new = u45_to_overs(name, odds, gpg, info.get("stats"))
            if new:
                leg = dict(sr.make_leg(row["event"], odds, new, KIND) or leg, sourceCode=leg.get("sourceCode"), swappedFrom="Under 4.5", _name=new)
                swaps["u45"] += 1
        if leg["odds"] > SWAP_MAX:
            fit = lambda alt, price: fits(row["league"], leg["eventId"], sr.O[alt], price, medians)[0]  # noqa: E731
            alt = swap_alternative(leg.get("_name"), odds, info.get("stats") if info else None, fit)
            if not alt:
                swaps["drop"] += 1
                continue
            leg = dict(sr.make_leg(row["event"], odds, alt, KIND), sourceCode=leg.get("sourceCode"), swappedFrom=leg.get("selection"), _name=alt)
            swaps["swap"] += 1
        final.append(leg)
    # Runs last, after the U4.5 -> O2.5/O1.5 switch and the 1.45 swap: Over 1.5 <-> Under 3.5 at 1.39 (HANDOFF 5.10).
    guard = lib.leg_guard()
    before = len(guard.LOG)
    guard.enforce(final, "master_pipeline")
    for leg in final:
        if leg.get("ruleSwap") and guard.kind(leg):
            leg["_name"] = guard.kind(leg)
    log["o15_u35_rule"] = guard.LOG[before:]
    log.update({"u45_to_overs": swaps["u45"], "swapped_over_145": swaps["swap"], "dropped_over_145": swaps["drop"], "final": len(final)})
    codes, skipped = outputs(final)
    clean = lambda legs: [{k: v for k, v in leg.items() if not k.startswith("_")} for leg in legs]  # noqa: E731
    result = []
    for c in codes:
        legs = clean(c["legs"])
        if dry_run:
            result.append({"id": c["id"], "label": c["label"], "n": len(legs), "total": round(lib.product(leg["odds"] for leg in legs), 2)})
            continue
        booked = lib.book_confirmed(legs) if len(legs) <= lib.MAX_LEGS else {"code": None, "reason": "over 50 legs"}
        row = {"id": c["id"], "label": c["label"], "code": booked.get("code"), "n": len(booked.get("legs") or legs),
               "total": booked.get("total"), "reason": booked.get("reason")}
        if booked.get("code"):
            slip = lib.public_slip("mp", ds, booked["code"], booked["legs"], booked["total"])
            slip.update({"name": f"{c['label']} · HIGH RISK", "origin": OWN_PREFIX + c["id"].replace("mp-", ""),
                         "pipeline": c["id"], "master": c["id"] == "mp-master" or None})
            lib.publish_high_odds(repo, {k: v for k, v in slip.items() if v is not None})
        else:
            skipped.append({"id": c["id"], "label": c["label"], "n": len(legs), "reason": booked.get("reason")})
        row["legs"] = booked.get("legs") or []
        result.append(row)
    payload = {"strategy": KIND, "date": ds, "simulated": simulate, "log": log,
               "codes": [{k: v for k, v in r.items() if k != "legs"} for r in result], "skipped": skipped,
               "booked": [{"code": r["code"], "legs": r["legs"]} for r in result if r.get("code")],
               "legs": clean(final),
               "rules": {"leagueFitRatio": sr.LEAGUE_FIT_RATIO, "strength": STRENGTH, "halfCap": HALF_CAP,
                         "slipCap": SLIP_CAP, "groupCap": GROUP_CAP, "split": SPLIT_AT, "swapMax": SWAP_MAX}}
    if not dry_run:
        lib.write_record(repo, KIND, ds, payload)
    print(json.dumps({"master_pipeline": ds, "dry": dry_run, "simulated": simulate, "log": log,
                      "codes": payload["codes"], "skipped": skipped}, default=str))
    return payload


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--simulate", action="store_true", help="dry-run input from the 80%% Sure / Reverse dry runs")
    ap.add_argument("--repo")
    args = ap.parse_args(argv)
    day = lib.nightly_target(explicit=args.date)
    repo = Path(args.repo) if args.repo else lib.repo_root()
    dry = args.dry_run or args.simulate or os.environ.get("P2U_HEALTH_DRY_RUN") == "1"
    run(day, repo, dry_run=dry, simulate=args.simulate)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
