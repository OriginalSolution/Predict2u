#!/usr/bin/env python3
"""Audit site JSON for obscure-league non-goals legs; swap to goals and rebook.

Usage: rebook_obscure_leagues.py [REPO]
Exempts daily master slips (gateExempt / Code of the Day).
"""
from __future__ import annotations
import ast, concurrent.futures as cf, datetime as dt, json, math, os, sys
from pathlib import Path

REPO = Path(sys.argv[1] if len(sys.argv) > 1 else Path(__file__).resolve().parents[2])
D = Path(__file__).resolve().parent
sys.path.insert(0, str(D))
sys.path.insert(0, str(REPO / "engine"))
import matchup_rules as MR

NOW = dt.datetime.now(dt.timezone.utc)
REPORT = []

# ---- booking helpers (same extract pattern as hot_picks) ----
src = open(D / "book_home.py").read()
T = ast.parse(src)
keep = []
for n in T.body:
    if isinstance(n, (ast.Import, ast.ImportFrom, ast.FunctionDef)):
        keep.append(n)
    elif isinstance(n, ast.Assign) and all(isinstance(t, ast.Name) and t.id in ("MU", "BU", "FCU", "MAXL") for t in n.targets):
        keep.append(n)
G = {"__name__": "bh"}
exec(compile(ast.Module(body=keep, type_ignores=[]), "book_home_funcs", "exec"), G)

def sb(L):
    code, st = G["book"](L)
    if code and st == "ok":
        return dict(code=code, totalOdds=round(math.prod(float(p["odds"]) for p in L), 2), legs=len(L))
    ok = [p for p in L if G["book"]([p])[1] == "ok"]
    if not ok:
        return None
    code, st = G["book"](ok)
    return dict(code=code, totalOdds=round(math.prod(float(p["odds"]) for p in ok), 2), legs=len(ok)) if code and st == "ok" else None

def ms(L):
    m = G["mbook"](L)
    return dict(code=m["msport"], totalOdds=m["totalOdds"], legs=m["legs"]) if m else None

def bk(L):
    b = G["bkbook"](L)
    return dict(code=b["betika"], totalOdds=b["totalOdds"], legs=b["legs"]) if b else None

BOOK = {"sportybet": sb, "msport": ms, "betika": bk}
if "fc_book" in G:
    BOOK["footballcom"] = lambda L: (lambda r: dict(code=r["code"], totalOdds=r["totalOdds"], legs=r["legs"]) if r else None)(G["fc_book"](L))
try:
    import bp_book
    BOOK["betpawa"] = lambda L: (lambda r: dict(code=r["code"], totalOdds=r["totalOdds"], legs=r["legs"]) if r else None)(bp_book.book(L))
except Exception:
    pass

LINK = {
    "sportybet": "https://www.sportybet.com/gh/?shareCode={}",
    "msport": "https://www.msport.com/gh/?shareCode={}",
    "betika": "https://betika.com/en-gh/share/{}",
    "footballcom": "https://www.football.com/gh/?shareCode={}",
    "betpawa": "https://www.betpawa.com.gh/share-betslip/{}",
}


def slip_exempt(s: dict) -> bool:
    if s.get("gateExempt") or s.get("exempt") or s.get("dailyMaster"):
        return True
    name = str(s.get("name") or s.get("label") or "")
    if "code of the day" in name.lower() or "master accumulator" in name.lower():
        return True
    return False


def fix_legs(legs):
    """Return (new_legs, changes) applying obscure→goals swaps. Drops unswappable."""
    out, changes = [], []
    for p in legs or []:
        q = dict(p)
        try:
            MR.resolve_league(q)
        except Exception:
            pass
        if q.get("gateExempt") or q.get("exempt"):
            out.append(q)
            continue
        if not MR.is_obscure_league_non_goals(q):
            out.append(q)
            continue
        swapped = MR.swap_to_goals(q)
        if swapped:
            changes.append(
                dict(
                    match=q.get("match"),
                    league=q.get("league"),
                    old=f"{q.get('selection')}@{q.get('odds')}",
                    new=f"{swapped.get('selection')}@{swapped.get('odds')}",
                )
            )
            out.append(swapped)
        else:
            changes.append(
                dict(
                    match=q.get("match"),
                    league=q.get("league"),
                    old=f"{q.get('selection')}@{q.get('odds')}",
                    new=None,
                    dropped=True,
                )
            )
    return out, changes


def book_all(legs):
    codes = {}
    def one(b):
        fn = BOOK[b]
        parts = []
        for i in range(0, len(legs), 30):
            try:
                r = fn([dict(p) for p in legs[i : i + 30]])
            except Exception:
                r = None
            if r:
                parts.append(dict(r, link=LINK[b].format(r["code"])))
        return b, parts
    with cf.ThreadPoolExecutor(5) as ex:
        for b, parts in ex.map(one, list(BOOK)):
            if parts:
                codes[b] = parts
    return codes


def code_map(codes):
    out = {}
    for b, v in (codes or {}).items():
        if isinstance(v, list) and v:
            out[b] = v[0].get("code") if isinstance(v[0], dict) else v[0]
        elif isinstance(v, dict):
            out[b] = v.get("code") or v.get(b)
        elif isinstance(v, str):
            out[b] = v
    return out


def rebook_slip(section, slip, legs_key="legs"):
    if slip_exempt(slip):
        return False
    legs = slip.get(legs_key) or slip.get("picks") or []
    if not legs or not isinstance(legs, list):
        return False
    # only pick-shaped dicts
    if not any(isinstance(x, dict) and x.get("eventId") for x in legs):
        return False
    new_legs, changes = fix_legs(legs)
    if not changes:
        return False
    if not new_legs:
        REPORT.append(dict(section=section, name=slip.get("name"), action="drop-empty", changes=changes))
        return False
    old_codes = code_map(slip.get("codes"))
    # Also handle home-style flat codes
    if not old_codes and isinstance(slip.get("codes"), dict):
        old_codes = {b: (v if isinstance(v, str) else None) for b, v in slip["codes"].items()}
    new_codes = book_all(new_legs)
    slip[legs_key if legs_key in slip else ("picks" if "picks" in slip else "legs")] = new_legs
    if "picks" in slip and legs_key == "legs":
        # keep both in sync when both exist as pick lists
        if isinstance(slip.get("picks"), list) and slip["picks"] and isinstance(slip["picks"][0], dict) and slip["picks"][0].get("eventId"):
            slip["picks"] = new_legs
    slip["legs"] = len(new_legs) if not isinstance(slip.get("legs"), list) else new_legs
    if isinstance(slip.get("legs"), int):
        slip["legs"] = len(new_legs)
    slip["totalOdds"] = round(math.prod(float(x.get("odds") or 1) for x in new_legs), 2)
    if new_codes:
        # preserve shape: list-of-dict like hot, or home mixed
        if slip.get("codes") and isinstance(next(iter(slip["codes"].values()), None), str):
            slip["codes"] = {b: (v[0]["code"] if isinstance(v, list) and v else v) for b, v in new_codes.items()}
            slip["links"] = {b: LINK[b].format(slip["codes"][b]) for b in slip["codes"]}
            slip["bookOdds"] = {b: (v[0]["totalOdds"] if isinstance(v, list) and v else None) for b, v in new_codes.items()}
            slip["bookPicks"] = {b: (v[0]["legs"] if isinstance(v, list) and v else None) for b, v in new_codes.items()}
        else:
            slip["codes"] = new_codes
    REPORT.append(
        dict(
            section=section,
            name=slip.get("name") or slip.get("label") or slip.get("code"),
            old=old_codes,
            new=code_map(slip.get("codes")),
            legs=len(new_legs),
            totalOdds=slip.get("totalOdds"),
            changes=changes,
        )
    )
    print("rebook", section, slip.get("name"), old_codes, "->", code_map(slip.get("codes")), flush=True)
    return True


def audit_home():
    path = REPO / "home-picks.json"
    doc = json.loads(path.read_text())
    changed = False
    for s in doc.get("slips") or []:
        # home slips store legs as list
        if rebook_slip("home", s, "legs"):
            changed = True
    if changed:
        doc["DATA_UPDATED"] = NOW.strftime("%Y-%m-%dT%H:%M:%SZ")
        path.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n")
    return changed


def audit_hot():
    path = REPO / "hot-picks.json"
    doc = json.loads(path.read_text())
    changed = False
    for s in doc.get("slips") or []:
        if rebook_slip("hot-slips", s, "legs"):
            changed = True
    for key in ("byMarket", "byTeam", "sectionMasters"):
        for s in doc.get(key) or []:
            # these use picks as legs + codes
            before = json.dumps(s.get("codes") or {}, sort_keys=True)
            # prefer picks list for markets/teams
            legs_key = "picks" if isinstance(s.get("picks"), list) and s.get("picks") and isinstance(s["picks"][0], dict) else "legs"
            if rebook_slip(f"hot-{key}", s, legs_key):
                changed = True
            elif before != json.dumps(s.get("codes") or {}, sort_keys=True):
                changed = True
    # top-level picks list (display): swap in place without booking
    picks = doc.get("picks") or []
    new_picks, ch = fix_legs(picks)
    if ch:
        doc["picks"] = new_picks
        changed = True
        REPORT.append(dict(section="hot-picks-list", name="picks", changes=ch, action="swap-display-only"))
    if changed:
        doc["updatedAt"] = NOW.isoformat(timespec="seconds")
        path.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n")
    return changed


def audit_high():
    path = REPO / "high_odds.json"
    doc = json.loads(path.read_text())
    changed = False
    for s in doc.get("slips") or []:
        if s.get("gateExempt"):
            continue
        legs = s.get("legs") or []
        new_legs, ch = fix_legs(legs)
        if not ch:
            continue
        if not new_legs or math.prod(float(x.get("odds") or 1) for x in new_legs) < 25:
            # Drop from active list — old share code no longer matches a legal ticket.
            REPORT.append(dict(section="high_odds", name=s.get("name"), code=s.get("code"), action="dropped-under-25-after-obscure-filter", changes=ch, old={"sportybet": s.get("code")}))
            s["_dropObscure"] = True
            changed = True
            continue
        old = s.get("code")
        # book sporty primary then others
        codes = book_all(new_legs)
        sb = (codes.get("sportybet") or [{}])[0]
        if not sb.get("code"):
            REPORT.append(dict(section="high_odds", name=s.get("name"), code=old, action="rebook-failed", changes=ch))
            continue
        new_code = sb["code"]
        s["legs"] = new_legs
        s["code"] = new_code
        s["odds"] = sb.get("totalOdds") or round(math.prod(float(x.get("odds") or 1) for x in new_legs), 2)
        s["codes"] = {b: (v[0] if isinstance(v, list) and v else v) for b, v in codes.items()}
        s["replacementOf"] = s.get("replacementOf") or old
        changed = True
        REPORT.append(dict(section="high_odds", name=s.get("name"), old={"sportybet": old}, new=code_map(codes), changes=ch, legs=len(new_legs), totalOdds=s["odds"]))
        print("rebook high", old, "->", new_code, flush=True)
    if changed:
        kept=[]
        for s in doc.get("slips") or []:
            if s.pop("_dropObscure", None):
                hist=doc.setdefault("history", [])
                s["status"]=s.get("status") or "replaced"
                s["note"]=(s.get("note") or "") + " | removed: obscure-league non-goals could not form 25+"
                hist.append(s)
                continue
            kept.append(s)
        doc["slips"]=kept
        doc["updatedAt"] = NOW.isoformat(timespec="seconds").replace("+00:00", "Z")
        path.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n")
    return changed


def main():
    print("audit obscure leagues", REPO, flush=True)
    h = audit_home()
    t = audit_hot()
    hi = audit_high()
    out = REPO / "engine" / "obscure_rebook_report.json"
    out.write_text(json.dumps(dict(updatedAt=NOW.isoformat(timespec="seconds"), home=h, hot=t, high=hi, report=REPORT), indent=2))
    print("changed", dict(home=h, hot=t, high=hi), "events", len(REPORT))
    print("report", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
