"""Rebook a list of teammate SportyBet share codes under all house rules.

  python -m engine.teamcodes CODE1 CODE2 ... [--void X Y] [--dry-run]

Each code is decoded and filtered (started, DC 12 / DC > 1.35, NG, obscure
league non-goals, matchup / 1.60 cap / strong-stats via rules.check), one
market per game. Codes still >= min odds stay as their own slip; the rest are
pooled, deduped and packed into 25+ slips. Identical slips are merged.
SportyBet is booked here; the slips are written to inbox/p2u/<today>.json so
vendor/high_odds.py publishes them and books Football.com/MSport/Betika/BetPawa.
No bot or tipster names are kept.
"""
from __future__ import annotations
import argparse, datetime as dt, json, sys
from . import combine
from .bookers import sportybet
from .paths import INBOX_DIR, ENGINE_DIR
if str(ENGINE_DIR) not in sys.path:
    sys.path.insert(0, str(ENGINE_DIR))


def build(codes, void=(), min_odds=None):
    min_odds = float(min_odds or combine.load_min_odds())
    void = {c.upper() for c in void}
    slips, pool, report = [], [], {"codes": {}, "dropped": []}
    for code in codes:
        if code.upper() in void:
            report["codes"][code] = "void"
            continue
        raw = combine.decode_share(code)
        r = combine.process(raw, min_odds=1e18)  # filter only; one slip with all survivors
        legs = [p for s in r["slips"] for p in s["legs"]]
        report["dropped"] += r["dropped"]
        odds = combine.product(legs) if legs else 0
        report["codes"][code] = {"in": len({p['eventId'] for p in raw}), "kept": len(legs), "odds": round(odds, 2)}
        if legs and odds >= min_odds:
            slips.append({"legs": legs, "src": [code]})
        else:
            pool += legs
    if pool:
        r = combine.process(pool, min_odds=min_odds, enrich=False)
        for s in r["slips"]:
            slips.append({"legs": s["legs"], "src": sorted({p.get('sourceCode') for p in s['legs']}), "combined": True})
    seen, out = set(), []
    for s in slips:
        fp = frozenset((p["eventId"], p.get("marketId"), p.get("specifier") or "", p.get("outcomeId")) for p in s["legs"])
        if fp in seen:
            continue
        seen.add(fp)
        s["odds"] = round(combine.product(s["legs"]), 2)
        out.append(s)
    return out, report


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("codes", nargs="+")
    ap.add_argument("--void", nargs="*", default=[])
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    slips, report = build(a.codes, a.void)
    today = dt.datetime.now(dt.timezone.utc).date().isoformat()
    res = []
    for i, s in enumerate(slips, 1):
        name = ("Combined selection" if s.get("combined") else "Verified High Odds") + f" {i}"
        b = None if a.dry_run else sportybet(s["legs"])
        res.append({"name": name, "code": (b or {}).get("code"), "odds": s["odds"], "legs": s["legs"], "src": s["src"]})
        print(name, s["odds"], len(s["legs"]), (b or {}).get("code"), "from", ",".join(s["src"]))
    if not a.dry_run:
        d = INBOX_DIR / "p2u"; d.mkdir(parents=True, exist_ok=True)
        (d / f"{today}.json").write_text(json.dumps({"date": today, "slips": [{k: v for k, v in r.items() if k != "src"} for r in res if r["code"]]}, indent=1, ensure_ascii=False))
        (d / f"{today}.report.json").write_text(json.dumps(report | {"slips": [{k: v for k, v in r.items() if k != 'legs'} for r in res]}, indent=1, ensure_ascii=False))
    print(json.dumps(report["codes"]))
    from collections import Counter
    print("drop reasons:", Counter(str(x.get("reason"))[:40] for x in report["dropped"]).most_common(15))
    return 0


if __name__ == "__main__":
    sys.exit(main())
