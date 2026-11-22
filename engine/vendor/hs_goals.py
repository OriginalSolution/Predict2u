#!/usr/bin/env python3
"""High-Scoring Teams O1.5/O2.5 (kind `hs15`). Daily 21:30 GMT, next Accra day. HANDOFF section 5.9.

Rule (Riddim Boss, 21 Nov 2026): teams that score AND concede a lot.
- Both teams: average goals scored >= 1.5 AND average goals conceded >= 1.5 per game
  (Sportradar season table + last 10 competitive games; how they combine is `combine` in
  engine/hs_goals.json, default the mean of the two windows).
- Match Over 1.5 priced 1.20-1.30 -> book Over 1.5.
- Over 1.5 below 1.20 -> book match Over 2.5, only when Over 2.5 is below 1.55.
- Anything else is rejected.
Standing rules: busy-day league filter (feed level), one pick per match, shared 2-codes-per-match
usage cap, at most 25 legs per code (bigger pools are split into parts).

Codes (SportyBet GH, every one read back from the share endpoint before it is published):
  Over 1.5 code(s), Over 2.5 code(s), and a master code of all legs.
Published on the Hot tab (hot-picks.json modelSlips) and the Bankers tab (picks.json slips, kept by
build.py from engine/data/strategy-codes/hs15/<day>.json), plus the record the master pipeline reads.
These are low-odds banker codes: the 25-odds floor of the high-odds strategies does not apply; they
are never padded.

  python engine/vendor/hs_goals.py [--date YYYY-MM-DD] [--dry-run] [--force]
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parent)]
import strategy_lib as lib  # noqa: E402
import night_trio as trio  # noqa: E402

KIND = "hs15"
NAME = "High-Scoring O1.5/O2.5"
CONFIG_PATH = HERE.parent / "hs_goals.json"
O15 = "18|total=1.5|Over 1.5"
O25 = "18|total=2.5|Over 2.5"
DEFAULTS = {"min_scored": 1.5, "min_conceded": 1.5, "combine": "mean", "min_season_games": 3, "min_last_games": 5,
            "last_n": 10, "o15_min": 1.20, "o15_max": 1.30, "o25_max": 1.55, "max_legs": 25, "min_legs_per_code": 2}


def load_config(path: Path | None = None) -> dict:
    try:
        cfg = json.loads(Path(path or CONFIG_PATH).read_text())
    except Exception:
        cfg = {}
    return {**DEFAULTS, **{k: v for k, v in cfg.items() if not k.startswith("_")}}


# ------------------------------------------------------------------ rules (pure)
def team_averages(season: tuple | None, last: list[tuple[int, int]] | None, cfg: dict) -> dict:
    """{'season': (scored, conceded, n) | None, 'last': (...) | None} after the minimum-games checks."""
    out = {"season": None, "last": None}
    if season and season[2] and season[2] >= cfg["min_season_games"]:
        out["season"] = (season[0] / season[2], season[1] / season[2], season[2])
    rows = list(last or [])[: cfg["last_n"]]
    if len(rows) >= cfg["min_last_games"]:
        out["last"] = (sum(r[0] for r in rows) / len(rows), sum(r[1] for r in rows) / len(rows), len(rows))
    return out


def team_passes(av: dict, cfg: dict) -> tuple[bool, float | None, float | None]:
    """(passes, scored avg used, conceded avg used)."""
    mode = cfg["combine"]
    windows = {"season": [av["season"]], "last10": [av["last"]], "both": [av["season"], av["last"]],
               "mean": [av["season"], av["last"]]}.get(mode, [av["season"], av["last"]])
    have = [w for w in windows if w]
    if not have or (mode == "both" and len(have) < 2):
        return False, None, None
    ok = lambda s, c: s >= cfg["min_scored"] and c >= cfg["min_conceded"]  # noqa: E731
    if mode == "both":
        return all(ok(w[0], w[1]) for w in have), round(min(w[0] for w in have), 2), round(min(w[1] for w in have), 2)
    s = sum(w[0] for w in have) / len(have)
    c = sum(w[1] for w in have) / len(have)
    return ok(s, c), round(s, 2), round(c, 2)


def pick_market(o15: float | None, o25: float | None, cfg: dict) -> tuple[str | None, str]:
    if o15 is None:
        return None, "no Over 1.5 price"
    if cfg["o15_min"] <= o15 <= cfg["o15_max"]:
        return "o15", "Over 1.5 in 1.20-1.30"
    if o15 < cfg["o15_min"]:
        if o25 is not None and o25 < cfg["o25_max"]:
            return "o25", "Over 1.5 under 1.20 -> Over 2.5 under 1.55"
        return None, "Over 1.5 under 1.20, no Over 2.5 under 1.55"
    return None, "Over 1.5 above 1.30"


# ------------------------------------------------------------------ data
def fetch(event_id: str, cache: dict) -> dict:
    out = {"home": {"season": None, "last": None}, "away": {"season": None, "last": None}}
    match = lib.sr_get("stats_match_get/" + str(event_id).split(":")[-1], cache)
    if not match or "teams" not in match:
        return out
    before = match["time"]["uts"]
    uids = {"home": match["teams"]["home"]["uid"], "away": match["teams"]["away"]["uid"]}
    for side, uid in uids.items():
        lastx = lib.sr_get(f"stats_team_lastx/{uid}/20", cache)
        out[side]["last"] = trio.competitive(lastx, uid, before)
    sid = match.get("_seasonid")
    table = lib.sr_get(f"stats_season_tables/{sid}", cache) if sid else None
    for block in (table or {}).get("tables") or []:
        rows = {(it.get("team") or {}).get("uid"): it for it in block.get("tablerows") or []}
        if all(u in rows for u in uids.values()):
            for side, uid in uids.items():
                it = rows[uid]
                if it.get("total") and it.get("goalsForTotal") is not None and it.get("goalsAgainstTotal") is not None:
                    out[side]["season"] = (it["goalsForTotal"], it["goalsAgainstTotal"], it["total"])
            break
    return out


def load_rows(day: dt.date) -> list[dict]:
    now = dt.datetime.now(dt.timezone.utc)
    rows = []
    for event in lib.fetch_upcoming("1,18"):  # busy-day league filter applies here
        kick = lib.event_kick(event)
        if not kick or kick.date() != day or kick <= now + dt.timedelta(minutes=10):
            continue
        country, league = lib.league_of(event)
        home, away = event.get("homeTeamName") or "", event.get("awayTeamName") or ""
        if lib.youth_or_sim(home, away, country, league) or lib.women_match(home, away, league):
            continue
        rows.append({"event": event, "eventId": event.get("eventId"), "odds": lib.event_odds(event)})
    return rows


def select(rows: list[dict], cache: dict, usage: dict, cfg: dict, fetch_fn=None) -> dict:
    fetch_fn = fetch_fn or fetch
    out = {"legs": [], "removed": {}}

    def drop(why):
        out["removed"][why] = out["removed"].get(why, 0) + 1

    todo = []
    for r in rows:
        if not lib.can_take(usage, r["eventId"]):
            drop("already on 2 codes")
            continue
        o15 = (r["odds"].get(O15) or [None])[0]
        o25 = (r["odds"].get(O25) or [None])[0]
        market, why = pick_market(o15, o25, cfg)
        if not market:
            drop(why)
            continue
        todo.append((r, market))
    with ThreadPoolExecutor(8) as pool:
        infos = list(pool.map(lambda x: fetch_fn(x[0]["eventId"], cache), todo))
    for (r, market), info in zip(todo, infos):
        checks = {}
        for side in ("home", "away"):
            av = team_averages(info[side]["season"], info[side]["last"], cfg)
            ok, s, c = team_passes(av, cfg)
            checks[side] = {"ok": ok, "scored": s, "conceded": c,
                            "seasonGames": av["season"][2] if av["season"] else None,
                            "lastGames": av["last"][2] if av["last"] else None}
        if not (checks["home"]["ok"] and checks["away"]["ok"]):
            drop("no stats" if any(checks[s]["scored"] is None for s in checks) else "team averages under 1.5")
            continue
        key = O15 if market == "o15" else O25
        leg = lib.leg_from_key(r["event"], key, r["odds"], market="Over/Under",
                               selection="Over 1.5" if market == "o15" else "Over 2.5")
        if not leg:
            drop("market not offered")
            continue
        leg.update({"strategy": KIND, "rule": market, "teamAverages": checks,
                    "free": 2 - len(usage.get(r["eventId"]) or [])})
        out["legs"].append(leg)
    out["legs"].sort(key=lambda x: x["odds"])
    return out


def plan_codes(legs: list[dict], cfg: dict) -> list[dict]:
    """[{'id', 'label', 'legs'}]: Over 1.5 part(s), Over 2.5 part(s), master part(s). One pick per match.
    A match with only one free usage slot goes on the master only (2-codes-per-match cap)."""
    cap, min_n = int(cfg["max_legs"]), int(cfg["min_legs_per_code"])

    def parts(rows):
        return [rows[i:i + cap] for i in range(0, len(rows), cap)]

    plan = []
    for market, label in (("o15", "Over 1.5"), ("o25", "Over 2.5")):
        rows = [leg for leg in legs if leg["rule"] == market and leg.get("free", 2) >= 2]
        if len(rows) < min_n:
            continue
        chunks = parts(rows)
        for i, chunk in enumerate(chunks, 1):
            suffix = f" · part {i}" if len(chunks) > 1 else ""
            plan.append({"id": f"{KIND}-{market}" + (f"-{i}" if len(chunks) > 1 else ""), "label": f"{NAME} · {label}{suffix}", "legs": chunk})
    if len(legs) >= min_n:
        chunks = parts(legs)
        for i, chunk in enumerate(chunks, 1):
            suffix = f" · part {i}" if len(chunks) > 1 else ""
            plan.append({"id": f"{KIND}-master" + (f"-{i}" if len(chunks) > 1 else ""), "label": f"{NAME} · Master{suffix}", "legs": chunk})
    return plan


# ------------------------------------------------------------------ booking (read back, no 25 floor)
def book_verified(legs: list[dict], tries: int = 3) -> dict:
    pending = lib.leg_guard().enforce(list(legs), "hs_goals.book_verified")
    for _ in range(tries):
        if not pending:
            break
        code, status = lib.book_sportybet([lib.selection_body(leg) for leg in pending])
        if not code:
            return {"code": None, "reason": status or "book failed", "legs": []}
        data = lib.read_share(code)
        total, started = lib.share_total(data)
        rows = data.get("outcomes") or []
        if len(rows) != len(pending) and not started:
            return {"code": None, "reason": f"read-back has {len(rows)} of {len(pending)} legs", "legs": []}
        if started:
            pending = [leg for leg in pending if leg["eventId"] not in started]
            continue
        return {"code": code, "total": round(total, 2), "legs": pending, "link": lib.SB_LINK.format(code), "readBack": True}
    return {"code": None, "reason": "legs kept starting", "legs": []}


def leg_public(leg: dict) -> dict:
    keep = ("eventId", "marketId", "specifier", "outcomeId", "market", "selection", "odds", "match", "league",
            "date", "ko", "kickoff", "rule", "teamAverages")
    row = {k: leg.get(k) for k in keep if leg.get(k) is not None}
    if not row.get("kickoff") and leg.get("date") and leg.get("ko"):
        row["kickoff"] = f"{leg['date']}T{leg['ko']}:00Z"
    row["result"] = "pending"
    row["matchStatus"] = "Not start"
    return row


def hot_slip(code: dict, day: str) -> dict:
    legs = [leg_public(x) for x in code["legs"]]
    return {
        "name": code["label"], "strategy": code["id"], "date": day, "label": code["label"], "legs": len(legs),
        "totalOdds": code["total"], "meetsFloor": code["total"] >= 25, "picks": legs,
        "events": [x["eventId"] for x in legs],
        "codes": {"sportybet": [{"code": code["code"], "totalOdds": code["total"], "legs": len(legs), "link": code["link"]}]},
        "result": "pending", "status": "pending",
        "note": "Teams that score and concede 1.5+ a game. Low-odds banker code, not padded.",
        "verification": "Both teams avg scored and conceded >= 1.5 (season + last 10). O1.5 1.20-1.30, else O2.5 under 1.55. Read back from SportyBet.",
    }


def bankers_slip(code: dict, day: str) -> dict:
    """picks.json slip shape (same fields build.py writes)."""
    legs = []
    for x in code["legs"]:
        p = leg_public(x)
        legs.append({"date": p.get("date") or day, "kickoff": p.get("kickoff"), "league": p.get("league"), "match": p.get("match"),
                     "market": p.get("market"), "selection": p.get("selection"), "odds": p.get("odds"),
                     "score": round(0.95 * min(0.97, 1 / float(p["odds"])), 3), "result": "pending"})
    legs.sort(key=lambda x: x["kickoff"] or "")
    comb = 1.0
    for x in legs:
        comb *= x["score"]
    avg = sum(x["score"] for x in legs) / len(legs)
    rating = round(0.6 * comb + 0.25 * avg + 0.15 * min(comb * code["total"], 1.5) / 1.5, 3)
    dates = sorted({x["date"] for x in legs})
    return {
        "codes": {"sportybet": code["code"]}, "legs": legs, "house": True, "name": code["label"], "strategy": NAME,
        "hsId": code["id"], "floorExempt": True, "dates": dates, "date": dates[0], "firstKickoff": legs[0]["kickoff"],
        "totalOdds": code["total"], "combined": round(comb, 4), "rating": rating,
        "grade": "A" if rating >= 0.55 else "B" if rating >= 0.35 else "C", "picks": len(legs),
        "links": {"sportybet": code["link"]}, "label": code["label"], "code": code["code"], "link": code["link"],
    }


def publish(repo: Path, day: str, booked: list[dict]) -> None:
    import publish_hot as PH
    ids = {b["id"] for b in booked}
    PH.upsert_model_slips(repo, [hot_slip(b, day) for b in booked],
                          replace_strategies=ids | {f"{KIND}-o15", f"{KIND}-o25", f"{KIND}-master"})
    upsert_bankers(repo, [bankers_slip(b, day) for b in booked], day)


def upsert_bankers(repo: Path, slips: list[dict], day: str) -> None:
    path = repo / "picks.json"
    try:
        doc = json.loads(path.read_text())
    except Exception:
        doc = {"slips": []}
    kept = [s for s in doc.get("slips") or [] if not (s.get("hsId") and s.get("date") == day)]
    doc["slips"] = kept + slips
    doc["DATA_UPDATED"] = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    path.write_text(json.dumps(doc, separators=(",", ":"), ensure_ascii=False))


def published_codes(repo: Path, ds: str) -> list[str]:
    """Codes this strategy already has live for the day (records do not survive between runners)."""
    try:
        doc = json.loads((repo / "hot-picks.json").read_text())
    except Exception:
        return []
    out = []
    for s in doc.get("modelSlips") or []:
        if str(s.get("strategy", "")).startswith(KIND + "-") and s.get("date") == ds:
            out += [c.get("code") for c in ((s.get("codes") or {}).get("sportybet") or []) if c.get("code")]
    return out


def run(day: dt.date, repo: Path, dry_run: bool = False, force: bool = False) -> dict:
    ds = day.isoformat()
    cfg = load_config()
    rec = repo / "engine" / "data" / "strategy-codes" / KIND / f"{ds}.json"
    if not dry_run and not force and rec.exists():
        try:
            if any(b.get("code") for b in json.loads(rec.read_text()).get("booked") or []):
                print(json.dumps({"hs_goals": ds, "skipped": "already booked for this day (use --force)"}))
                return {"skipped": True}
        except Exception:
            pass
    if not dry_run and not force and published_codes(repo, ds):
        print(json.dumps({"hs_goals": ds, "skipped": "codes already published for this day (use --force)"}))
        return {"skipped": True}
    usage = lib.load_usage(repo, ds)
    rows = load_rows(day)
    found = select(rows, {}, usage, cfg)
    plan = plan_codes(found["legs"], cfg)
    booked = []
    for item in plan:
        if dry_run:
            booked.append({**item, "code": None, "dryRun": True, "total": round(lib.product(x["odds"] for x in item["legs"]), 2)})
            continue
        res = book_verified(item["legs"])
        if res.get("code"):
            for leg in res["legs"]:
                lib.take(usage, leg["eventId"], res["code"])
            booked.append({**item, **res})
        else:
            booked.append({**item, "code": None, "reason": res.get("reason")})
    good = [b for b in booked if b.get("code")]
    if not dry_run:
        lib.save_usage(repo, ds, usage)
        if good:
            publish(repo, ds, good)
        lib.write_record(repo, KIND, ds, {
            "strategy": KIND, "name": NAME, "date": ds, "seen": len(rows), "qualifying": len(found["legs"]),
            "removed": found["removed"], "rules": cfg,
            "booked": [{"id": b["id"], "label": b["label"], "code": b.get("code"), "total": b.get("total"),
                        "reason": b.get("reason"), "link": b.get("link"), "legs": b["legs"] if b.get("code") else []} for b in booked],
            "bankersSlips": [bankers_slip(b, ds) for b in good],
        })
    summary = {"hs_goals": ds, "dry": dry_run, "seen": len(rows), "qualifying": len(found["legs"]), "removed": found["removed"],
               "codes": [{"id": b["id"], "label": b["label"], "n": len(b["legs"]), "total": b.get("total"),
                          "code": b.get("code"), "reason": b.get("reason")} for b in booked],
               "legs": [f"{x['match']} | {x['selection']} @{x['odds']} | {x['league']}" for x in found["legs"]]}
    print(json.dumps(summary, ensure_ascii=False))
    return summary


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--repo")
    args = ap.parse_args(argv)
    day = lib.nightly_target(explicit=args.date)
    repo = Path(args.repo) if args.repo else lib.repo_root()
    dry = args.dry_run or os.environ.get("P2U_HEALTH_DRY_RUN") == "1"
    run(day, repo, dry_run=dry, force=args.force)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
