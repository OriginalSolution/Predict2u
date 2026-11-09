#!/usr/bin/env python3
"""Verzzify Banker of the Day — research-backed slip for the Bankers page (odds > 25).

Strategy (ALL normal Predict2u rules apply: no NG, no DC 12, 1X/X2 only ≤1.35, obscure
leagues goals-only, ≤50 picks/code, matchup/1.60/strong-stats gates):

  Verzzify Edge Banker
  --------------------
  1. Start from today's house favourites research (home-picks / research JSON) plus
     settled-site history (engine pick_history + picks-history.json).
  2. Keep a pick only when ALL hold:
       • matchup_rules.check passes (hard vetoes + class gates)
       • odds between 1.12 and 1.45 (banker band)
       • if hist.site band hit-rate exists with n≥20: site rate ≥ implied% + 3
       • else if leagueFavRate & sample≥50: league rate ≥ 0.78
       • confidence ≥ 0.72 when present
       • not youth/reserves/women; one market per game
  3. Rank by (site_edge or league_edge, confidence, -odds). Pack until combined odds
     first exceeds 25 (and ≤50 legs). No padding with weak legs.
  4. Book on SportyBet + Football.com, MSport, Betika, BetPawa. Write to
     engine/inbox/p2u/<date>-verzzify.json so high_odds/build publish paths and the
     bankers page (picks.json / home slips) can pick it up; also inject a Main slip
     into home-picks.json via a small post-step in daily_master / build.

Documented in engine/RULES.md § Verzzify Edge Banker.
"""
from __future__ import annotations
import datetime as dt, json, math, os, re, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parent), str(HERE.parent.parent)]
import matchup_rules as MR
import pick_history as PH
from engine.paths import REPO_DIR, RESEARCH_DIR, ENGINE_DIR, INBOX_DIR
from engine import bookers

SKIP = re.compile(r"\b(U-?\d{2}|youth|junior|reserves?|women|woman|ladies|primavera|academy)\b|\(w\)", re.I)
MIN_TOTAL = 25.0
MAX_LEGS = 50
BAND_LO, BAND_HI = 1.12, 1.45


def load_json(p, d=None):
    try: return json.load(open(p))
    except Exception: return d


def research_picks(day):
    files = sorted(RESEARCH_DIR.glob("????-??-??.json"))
    files = [f for f in files if f.name[:10] <= day]
    if not files:
        hp = load_json(REPO_DIR / "home-picks.json", {})
        return list(hp.get("picks") or [])
    d = load_json(files[-1], {})
    return list(d.get("picks") or [])


def edge(p):
    H = p.get("hist") or {}
    imp = H.get("implied")
    if H.get("site") and H["site"].get("n", 0) >= 20 and imp is not None:
        return H["site"]["rate"] - imp, "site"
    lr, n = p.get("leagueFavRate"), p.get("sample") or 0
    if lr is not None and n >= 50 and imp is not None:
        rate = lr * 100 if lr <= 1 else lr
        return rate - imp, "league"
    if lr is not None and n >= 50:
        rate = lr * 100 if lr <= 1 else lr
        return rate - 78, "league-floor"
    return None, None


def eligible(p):
    if SKIP.search(f"{p.get('match','')} {p.get('league','')}"): return False, "youth/women"
    try: o = float(p.get("odds") or 0)
    except Exception: return False, "odds"
    if not (BAND_LO <= o <= BAND_HI): return False, "band"
    if MR.is_btts_no(p) or (MR.is_double_chance(p) and MR.is_dc_vetoed(p)): return False, "hard-veto"
    if MR.is_obscure_league_non_goals(p): return False, "obscure-non-goals"
    ok, cls, why = MR.check(p)
    if not ok: return False, f"gate:{cls}:{why}"
    e, src = edge(p)
    if src == "site" and e is not None and e < 3: return False, "site-edge"
    if src == "league" and e is not None and e < 0: return False, "league-edge"
    if src == "league-floor" and e is not None and e < 0: return False, "league-floor"
    if src is None: return False, "no-hist"
    c = p.get("confidence")
    if c is not None:
        c = c / 100 if c > 1 else c
        if c < 0.72: return False, "confidence"
    return True, src


def pack(cands):
    """Greedy pack: highest edge first until product > 25."""
    cands = sorted(cands, key=lambda p: (-(edge(p)[0] or 0), -(p.get("confidence") or 0), float(p["odds"])))
    seen, out, prod = set(), [], 1.0
    for p in cands:
        if p["eventId"] in seen: continue
        if len(out) >= MAX_LEGS: break
        out.append(p); seen.add(p["eventId"]); prod *= float(p["odds"])
        if prod >= MIN_TOTAL and len(out) >= 5: break
    if math.prod(float(p["odds"]) for p in out) < MIN_TOTAL: return []  # refuse to pad
    return out


def book(legs):
    codes = {}
    for name, fn in bookers.BOOKERS.items():
        try: r = fn([dict(p) for p in legs])
        except Exception: r = None
        if r and r.get("code"):
            codes[name] = dict(code=r["code"], legs=r.get("legs") or len(legs), odds=r.get("totalOdds"),
                               link={"sportybet": "https://www.sportybet.com/gh/?shareCode={}",
                                     "footballcom": "https://www.football.com/gh/?shareCode={}",
                                     "msport": "https://www.msport.com/gh/?shareCode={}",
                                     "betika": "https://betika.com/en-gh/share/{}",
                                     "betpawa": "https://www.betpawa.com.gh/share-betslip/{}"}.get(name, "{}").format(r["code"]))
    return codes


def main():
    day = dt.datetime.now(dt.timezone.utc).date().isoformat()
    picks = research_picks(day)
    # Attach hist from pick_history
    try:
        out = dict(picks=picks, leagues=[])
        PH.annotate(out, str(REPO_DIR), str(ENGINE_DIR / "data" / "pick_ledger.json"))
        picks = out["picks"]
    except Exception as e: print("hist annotate skipped", e)
    kept, dropped = [], []
    for p in picks:
        if str(p.get("date") or day) < day: continue
        ok, why = eligible(p)
        if ok: kept.append(p)
        else: dropped.append(dict(match=p.get("match"), selection=p.get("selection"), reason=why))
    slip = pack(kept)
    tot = round(math.prod(float(p["odds"]) for p in slip), 2) if slip else 0
    print(f"verzzify: candidates {len(kept)} packed {len(slip)} @{tot} (dropped {len(dropped)})")
    if not slip:
        print("verzzify: no banker today (would be under 25 without padding)"); return 0
    codes = book(slip)
    sb = (codes.get("sportybet") or {}).get("code")
    rec = dict(date=day, name="Verzzify Edge Banker", strategy="verzzify-edge-banker",
               totalOdds=tot, legs=[{k: p.get(k) for k in ("eventId","match","league","market","selection","odds","marketId","specifier","outcomeId","date","ko","kickoff","hist","confidence","leagueFavRate","sample")} for p in slip],
               codes=codes, code=sb, verification="Verzzify Edge Banker: site/league historical edge over implied, banker band 1.12–1.45, all Predict2u rules",
               dropped=dropped[:50])
    d = INBOX_DIR / "p2u"; d.mkdir(parents=True, exist_ok=True)
    # Merge into today's inbox slips so high_odds + bankers publish pick it up
    inbox = load_json(d / f"{day}.json", {"date": day, "slips": []}) or {"date": day, "slips": []}
    inbox["slips"] = [s for s in (inbox.get("slips") or []) if s.get("strategy") != "verzzify-edge-banker"]
    inbox["slips"].insert(0, dict(name=rec["name"], code=sb, odds=tot, legs=rec["legs"], strategy="verzzify-edge-banker",
                                  verification=rec["verification"], codes={k: v["code"] for k, v in codes.items()},
                                  links={k: v["link"] for k, v in codes.items()}, bookOdds={k: v["odds"] for k, v in codes.items()},
                                  bookPicks={k: v["legs"] for k, v in codes.items()}))
    json.dump(inbox, open(d / f"{day}.json", "w"), indent=1, ensure_ascii=False)
    json.dump(rec, open(ENGINE_DIR / "data" / f"verzzify-banker-{day}.json", "w"), indent=1, ensure_ascii=False)
    # Inject as Main slip on home-picks so banker pop / bankers page see it
    hp = load_json(REPO_DIR / "home-picks.json")
    if hp is not None and sb:
        slips = [s for s in (hp.get("slips") or []) if not s.get("verzzify")]
        slips.insert(0, dict(name="Main · Verzzify Edge Banker", totalOdds=tot, legs=rec["legs"],
                             codes={k: v["code"] for k, v in codes.items()}, bookOdds={k: v["odds"] for k, v in codes.items()},
                             bookPicks={k: v["legs"] for k, v in codes.items()}, verzzify=True,
                             verification=rec["verification"]))
        hp["slips"] = slips
        json.dump(hp, open(REPO_DIR / "home-picks.json", "w"), ensure_ascii=False, separators=(",", ":"))
    print("verzzify booked", {k: v["code"] for k, v in codes.items()}, "@", tot)
    return 0


if __name__ == "__main__":
    sys.exit(main())
