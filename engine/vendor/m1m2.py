#!/usr/bin/env python3
"""Original M1 / M2 nightly slips (nysm_win_or_o25 v1). No upgrade, no combined slip.

M1 — favourite Team-or-Over-2.5 when win price <= 1.30 and Over 2.5 <= 1.50.
     Home → market 854 "Home Team or Over 2.5" Yes (outcome 74).
     Away → market 858 "Away or Over 2.5" Yes (outcome 74).
M2 — favourite Double Chance & Over 1.5 when win price <= 1.20 and Over 2.5 <= 1.40.
     Home → market 547 outcome 1727 "Home/Draw & Over 1.5".
     Away → market 547 outcome 1729 "Draw/Away & Over 1.5".
     Outcome 1728 is Home/Away (DC 12) and is never used.
MIXED — only when at least one favourite team-2+ (team Over 1.5) leg clears the
     same M1 prices and the normal gates. It is not an M1+M2 combination.

Relaxed thresholds (pw 1.35 / O2.5 1.55 and pw 1.25 / O2.5 1.45) are not used.
Normal Predict2u gates apply. Legs are not padded. A slip under 25 combined
odds is still booked and flagged (the prices are usually 1.05–1.15; padding
is forbidden). More than 50 legs is split by the shared splitter.

  python engine/vendor/m1m2.py
  python engine/vendor/m1m2.py --dry-run
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parent), str(HERE.parent.parent)]

import matchup_rules as MR
import publish_hot as PH
import sb_common as SB
from engine.paths import ENGINE_DIR, REPO_DIR

M1_PW, M1_O25 = 1.30, 1.50
M2_PW, M2_O25 = 1.20, 1.40
# Upgrade variant — present only so tests can prove it is not used.
RELAX_M1 = (1.35, 1.55)
RELAX_M2 = (1.25, 1.45)

LEDGER = ENGINE_DIR / "data" / "m1m2_ledger.json"


def qualifies(pw, o25, kind):
    """Original thresholds only. `kind` is 'M1' or 'M2'."""
    if pw is None or o25 is None:
        return False
    if kind == "M1":
        return pw <= M1_PW and o25 <= M1_O25
    if kind == "M2":
        return pw <= M2_PW and o25 <= M2_O25
    return False


def build_candidates(data):
    """Price-rule candidates for one not-started event. No network beyond `data`."""
    if not data or not SB.not_started(data) or not SB.in_window(data):
        return []
    home = data.get("homeTeamName") or ""
    away = data.get("awayTeamName") or ""
    league = SB.league_of(data)
    if SB.skip_fixture(home, away, league):
        return []
    markets = data.get("markets") or []
    x12, h, _d, a = SB.x12_of(markets)
    o25 = SB.find_outcome(markets, "18", "total=2.5", oid="12", desc_prefix="Over")
    if not (h and a and o25):
        return []
    side = "H" if h <= a else "A"
    pw = h if side == "H" else a
    fav = home if side == "H" else away
    ko = SB.kickoff(data)
    base = dict(
        eventId=data.get("eventId"), match=f"{home} v {away}", league=league,
        home=home, away=away, fav=fav, side=side, pw=pw, o25=o25[2], x12=x12 or "",
        kickoff=ko.isoformat().replace("+00:00", "Z") if ko else None,
        date=ko.date().isoformat() if ko else None,
        ko=ko.strftime("%H:%M") if ko else None,
        result="pending", matchStatus="Not start",
    )
    out = []
    if qualifies(pw, o25[2], "M1"):
        mid = "854" if side == "H" else "858"
        label = "Home Team or Over 2.5" if side == "H" else "Away or Over 2.5"
        got = SB.find_outcome(markets, mid, "total=2.5", oid="74", desc_is="Yes")
        if got:
            out.append(dict(base, rule="M1", marketId=mid, specifier="total=2.5", outcomeId="74",
                            market=label, selection=label,
                            odds=got[2],
                            reason=f"M1: pw {pw:.2f}<={M1_PW} and O2.5 {o25[2]:.2f}<={M1_O25}"))
    if qualifies(pw, o25[2], "M2"):
        oid = "1727" if side == "H" else "1729"
        sel = "Home/Draw & Over 1.5" if side == "H" else "Draw/Away & Over 1.5"
        got = SB.find_outcome(markets, "547", "total=1.5", oid=oid, desc_is=sel)
        if got and oid != "1728":
            out.append(dict(base, rule="M2", marketId="547", specifier="total=1.5", outcomeId=oid,
                            market="Double Chance & Over/Under 1.5", selection=sel,
                            odds=got[2],
                            reason=f"M2: pw {pw:.2f}<={M2_PW} and O2.5 {o25[2]:.2f}<={M2_O25}"))
    # Team 2+ (favourite team Over 1.5). MIXED exists only if one of these clears the gate.
    if qualifies(pw, o25[2], "M1"):
        tmid = "19" if side == "H" else "20"
        got = SB.find_outcome(markets, tmid, "total=1.5", oid="12", desc_prefix="Over")
        if got:
            sel = f"{'Home' if side == 'H' else 'Away'} over 1.5 goals"
            out.append(dict(base, rule="T2", marketId=tmid, specifier="total=1.5", outcomeId="12",
                            market="Team Over/Under", selection=sel, odds=got[2],
                            reason=f"team 2+: {fav} Over 1.5 @{got[2]:.2f} inside M1 prices"))
    return out


def apply_gate(p, enrich=True):
    if enrich and not (p.get("table") and p.get("x12")):
        try:
            MR.enrich(p)
        except Exception:
            pass
    ok, cls, why = MR.check(p)
    p["matchup"] = cls
    p["gateWhy"] = why
    return bool(ok) and not MR.is_btts_no(p) and not MR.is_dc_vetoed(p)


def select(candidates, enrich=True):
    """One leg per match per slip. Drop anything the normal gate rejects.

    M1 and M2 are separate slips (the same match may appear on both, as in the
    original nightly codes). MIXED is only the team-2+ legs that cleared.
    """
    kept = {"M1": [], "M2": [], "T2": []}
    dropped = []
    seen = {"M1": set(), "M2": set(), "T2": set()}
    for p in candidates:
        rule = p.get("rule")
        if rule not in kept or p.get("eventId") in seen[rule]:
            continue
        if not apply_gate(p, enrich=enrich):
            dropped.append({"match": p.get("match"), "rule": rule, "selection": p.get("selection"),
                            "reason": p.get("gateWhy")})
            continue
        seen[rule].add(p["eventId"])
        kept[rule].append(p)
    mixed = kept["T2"]
    return {"M1": kept["M1"], "M2": kept["M2"], "MIXED": mixed, "dropped": dropped}


def _product(legs):
    if not legs:
        return 0.0
    return round(math.prod(float(p["odds"]) for p in legs), 2)


def _slip(name, strategy, legs, codes, day):
    prod = _product(legs)
    return dict(
        name=name, strategy=strategy, date=day, label=name,
        legs=len(legs), totalOdds=prod, meetsFloor=prod >= 25,
        picks=legs, events=[p["eventId"] for p in legs],
        codes=codes, result="pending", status="pending",
        note=None if prod >= 25 else "Under 25 combined odds. Not padded.",
        verification="Original M1/M2 thresholds. Normal Predict2u gates. No upgrade, no combined slip.",
    )


def book_groups(groups, day, book=True):
    slips = []
    for key, title in (("M1", "M1 Team or Over 2.5"), ("M2", "M2 Double Chance & Over 1.5"), ("MIXED", "M1/M2 team 2+")):
        legs = groups.get(key) or []
        if key == "MIXED" and not legs:
            continue
        if not legs:
            continue
        legs = sorted(legs, key=lambda p: p.get("kickoff") or "")
        chunks = [legs]
        if len(legs) > 50:
            import split_codes as SC
            chunks = SC.split(legs, 50)
        for i, chunk in enumerate(chunks):
            name = title if len(chunks) == 1 else f"{title} · part {i + 1}/{len(chunks)}"
            codes = PH.book_legs(chunk) if book else {}
            if book and not codes:
                print(key, "no bookmaker returned a code", name, flush=True)
                continue
            slips.append(_slip(name, key if len(chunks) == 1 else f"{key}-{i + 1}", chunk, codes, day))
            print(name, len(chunk), _product(chunk),
                  {b: v[0]["code"] for b, v in codes.items()}, flush=True)
    return slips


def update_ledger(day, slips, dropped):
    try:
        led = json.loads(LEDGER.read_text()) if LEDGER.exists() else {}
    except Exception:
        led = {}
    led.setdefault("rules", {
        "M1": "pw<=1.30 and O2.5<=1.50 → Team or Over 2.5",
        "M2": "pw<=1.20 and O2.5<=1.40 → DC & Over 1.5",
        "MIXED": "team Over 1.5 only when it clears M1 prices and the normal gates",
        "upgrade": "not used",
    })
    days = led.setdefault("days", {})
    days[day] = {
        "built": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M GMT"),
        "slips": {
            s["strategy"]: {
                "name": s["name"],
                "codes": {b: v[0]["code"] for b, v in (s.get("codes") or {}).items()},
                "total": s.get("totalOdds"),
                "legs": s.get("legs"),
                "meetsFloor": s.get("meetsFloor"),
                "result": "pending",
            } for s in slips
        },
        "dropped": dropped[:80],
        "mixed": "built" if any(s["strategy"].startswith("MIXED") or s["strategy"] == "MIXED" for s in slips) else "not built (no team-2+ leg cleared the gates)",
    }
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    LEDGER.write_text(json.dumps(led, indent=1, ensure_ascii=False))


def run(days=4, book=True, publish=True):
    import concurrent.futures as cf
    day = dt.datetime.now(dt.timezone.utc).date().isoformat()
    ids = SB.upcoming_ids(days)
    print(f"m1m2: {len(ids)} events in {days} days", flush=True)
    with cf.ThreadPoolExecutor(12) as ex:
        events = list(ex.map(SB.fetch_event, ids))
    cands = []
    for data in events:
        cands.extend(build_candidates(data))
    print(f"m1m2 raw", {k: sum(1 for p in cands if p["rule"] == k) for k in ("M1", "M2", "T2")}, flush=True)
    groups = select(cands, enrich=True)
    print("m1m2 kept", {k: len(groups[k]) for k in ("M1", "M2", "MIXED")}, "dropped", len(groups["dropped"]), flush=True)
    slips = book_groups(groups, day, book=book) if book or groups["M1"] or groups["M2"] or groups["MIXED"] else []
    if not book:
        slips = []
        for key, title in (("M1", "M1 Team or Over 2.5"), ("M2", "M2 Double Chance & Over 1.5"), ("MIXED", "M1/M2 team 2+")):
            legs = groups[key]
            if not legs:
                continue
            slips.append(_slip(title, key, legs, {}, day))
    if publish and book:
        PH.upsert_model_slips(REPO_DIR, slips, replace_strategies={"M1", "M2", "MIXED"})
        update_ledger(day, slips, groups["dropped"])
    return {"day": day, "slips": slips, "dropped": groups["dropped"], "counts": {k: len(groups[k]) for k in ("M1", "M2", "MIXED")}}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--days", type=int, default=4)
    args = ap.parse_args(argv)
    out = run(days=args.days, book=not args.dry_run, publish=not args.dry_run)
    print(json.dumps({"counts": out["counts"], "slips": [
        {"name": s["name"], "legs": s["legs"], "odds": s["totalOdds"],
         "codes": {b: v[0]["code"] for b, v in (s.get("codes") or {}).items()}}
        for s in out["slips"]
    ]}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
