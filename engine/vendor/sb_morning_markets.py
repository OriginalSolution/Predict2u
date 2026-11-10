#!/usr/bin/env python3
"""SportyBet morning markets — one best 1.20–1.60 pick per match.

Pulls today's not-started football from SportyBet GH, scores every modelable
market with SportyBet-hosted Sportradar tables, last-x form, H2H and a Poisson
goal model, then books the best pick per match (odds 1.20–1.60 inclusive)
across the no-login bookies and publishes slips onto home-picks.json.

  python engine/vendor/sb_morning_markets.py
  python engine/vendor/sb_morning_markets.py --dry-run
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import datetime as dt
import json
import math
import os
import re
import subprocess
import sys
import time
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve()
ENGINE_DIR = Path(os.environ.get("ENGINE_DIR") or HERE.parents[1])
VENDOR_DIR = Path(os.environ.get("VENDOR_DIR") or HERE.parent)
REPO_DIR = Path(os.environ.get("REPO_DIR") or ENGINE_DIR.parent)
RESEARCH_DIR = Path(os.environ.get("RESEARCH_DIR") or (ENGINE_DIR / "data"))
sys.path.insert(0, str(ENGINE_DIR))
sys.path.insert(0, str(VENDOR_DIR))

from bookers import book_all  # noqa: E402

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36"
SB_UPCOMING = "https://www.sportybet.com/api/gh/factsCenter/pcUpcomingEvents?sportId=sr%3Asport%3A1&marketId=1%2C18&pageSize=100&pageNum={page}&option=1"
SB_EVENT = "https://www.sportybet.com/api/gh/factsCenter/event?eventId={eid}&productId=3"
SR = "https://stats.fn.sportradar.com/sportybet/en/Europe:Berlin/gismo/"
CACHE = Path(os.environ.get("STATS_CACHE") or (RESEARCH_DIR / "stats-cache"))

ODDS_MIN = 1.20
ODDS_MAX = 1.60
MIN_EV = 0.04
MIN_FORM = 6
KO_BUFFER_MIN = 10
LEGS_PER_SLIP = 5
STRATEGY = "SportyBet Stats"
YOUTH = re.compile(
    r"U\d\d\b|U-\d\d|Res\.|Reserve|Jong |Next Gen|Women|Primavera|Youth|"
    r"Femen|Futures|Simulated|SRL|Esoccer|Academy",
    re.I,
)
TEAMX = re.compile(r"\bII\b|\b2$|\bB$|\bW$")


def curl_json(url, timeout=30, tries=3):
    for i in range(tries):
        try:
            raw = subprocess.run(
                ["curl", "-s", "-m", str(timeout), "-A", UA, url],
                capture_output=True, text=True,
            ).stdout
            if raw and raw.strip()[:1] in "{[":
                return json.loads(raw)
        except Exception:
            time.sleep(1 + i)
    return {}


def sr_get(path):
    CACHE.mkdir(parents=True, exist_ok=True)
    f = CACHE / (path.replace("/", "_") + ".json")
    if f.exists():
        try:
            return json.loads(f.read_text())
        except Exception:
            pass
    d = curl_json(SR + path)
    data = None
    if d and "doc" in d and d["doc"] and d["doc"][0].get("event") != "exception":
        data = d["doc"][0].get("data")
    try:
        f.write_text(json.dumps(data))
    except Exception:
        pass
    return data


def now_utc():
    return dt.datetime.now(dt.timezone.utc)


def today_accra():
    return now_utc().date().isoformat()  # Africa/Accra == UTC+0


def ts_ms(e):
    t = e.get("estimateStartTime") or e.get("startTime") or 0
    return t / 1000.0 if t > 1e12 else float(t or 0)


def scan_upcoming():
    events = {}
    for page in range(1, 40):
        data = (curl_json(SB_UPCOMING.format(page=page), timeout=40) or {}).get("data") or {}
        tours = data.get("tournaments") or []
        new = [e for t in tours for e in (t.get("events") or [])]
        for e in new:
            events[e["eventId"]] = e
        if not new or len(events) >= int(data.get("totalNum") or 0):
            break
    return events


def is_skipped_fixture(e):
    home = (e.get("homeTeamName") or "").strip()
    away = (e.get("awayTeamName") or "").strip()
    lg = ((e.get("sport") or {}).get("category") or {})
    tname = (lg.get("tournament") or {}).get("name") or ""
    cname = lg.get("name") or ""
    blob = f"{home} v {away}|{cname}|{tname}"
    if YOUTH.search(blob) or TEAMX.search(home) or TEAMX.search(away):
        return "youth/reserve/women/virtual"
    if str(e.get("matchStatus") or "Not start") not in {"Not start", "0", ""}:
        return "started"
    return None


def eligible_today(events, day=None):
    day = day or today_accra()
    cutoff = time.time() + KO_BUFFER_MIN * 60
    out, skipped = [], {}
    for e in events.values():
        ts = ts_ms(e)
        if not ts:
            continue
        ko = dt.datetime.fromtimestamp(ts, dt.timezone.utc)
        if ko.date().isoformat() != day:
            continue
        why = is_skipped_fixture(e)
        if why:
            skipped[e.get("homeTeamName", "?") + " v " + e.get("awayTeamName", "?")] = why
            continue
        if ts <= cutoff:
            skipped[e.get("homeTeamName", "?") + " v " + e.get("awayTeamName", "?")] = "kickoff too soon"
            continue
        out.append(e)
    out.sort(key=ts_ms)
    return out, skipped


def fact(eid):
    try:
        return curl_json(SB_EVENT.format(eid=eid)).get("data") or {}
    except Exception:
        return {}


def poisson(lam, k):
    if lam <= 0:
        return 1.0 if k == 0 else 0.0
    return math.exp(-lam) * lam ** k / math.factorial(k)


def matrix(lh, la, n=11):
    ph = [poisson(lh, i) for i in range(n)]
    pa = [poisson(la, j) for j in range(n)]
    return [[ph[i] * pa[j] for j in range(n)] for i in range(n)]


def sum_where(M, pred):
    return sum(M[i][j] for i in range(len(M)) for j in range(len(M[0])) if pred(i, j))


def half_line(spec, key="total"):
    if not spec:
        return None
    m = re.search(rf"{key}=([\d.]+)", str(spec))
    if not m:
        return None
    v = float(m.group(1))
    # Half-lines only (1.5, 2.5…). Integer lines can push; avoid banker's round(1.5)==2.
    if abs(v - math.floor(v) - 0.5) > 1e-9:
        return None
    return v



def market_1x2(ev):
    for mkt in ev.get("markets") or []:
        if str(mkt.get("id") or "") != "1":
            continue
        odds = {}
        for o in mkt.get("outcomes") or []:
            if str(o.get("isActive", 1)) != "1":
                continue
            try:
                odds[o.get("desc")] = float(o["odds"])
            except (TypeError, ValueError):
                pass
        return odds
    return {}


def devig(odds_map):
    inv = {k: 1.0 / v for k, v in odds_map.items() if v}
    s = sum(inv.values())
    if s <= 0:
        return {}
    return {k: v / s for k, v in inv.items()}

def estimate_lambdas(info, last_h, last_a, h2h, hu, au):
    """Season + form blend. Returns (lh, la, games_h, games_a, src) or None."""
    mm = (info or {}).get("match") or {}
    season = mm.get("_seasonid")
    if not season:
        return None
    tables = sr_get(f"stats_season_tables/{season}") or {}
    # season fixtures for GF/GA
    fx = sr_get(f"stats_season_fixtures2/{season}") or {}
    gls = defaultdict(lambda: [0, 0, 0])  # for, against, n
    now = time.time()
    for m in fx.get("matches") or []:
        r = m.get("result") or {}
        if r.get("home") is None:
            continue
        if (m.get("time") or {}).get("uts", 0) >= now:
            continue
        h, a = m["teams"]["home"]["uid"], m["teams"]["away"]["uid"]
        gh, ga = r["home"], r["away"]
        gls[h][0] += gh; gls[h][1] += ga; gls[h][2] += 1
        gls[a][0] += ga; gls[a][1] += gh; gls[a][2] += 1
    gh_, ga_ = gls.get(hu, [0, 0, 0]), gls.get(au, [0, 0, 0])

    def form_gls(rows, uid, n=6):
        gf = ga = 0
        used = 0
        for z in rows[:n]:
            r = z.get("result") or {}
            if r.get("home") is None:
                continue
            home = z["teams"]["home"]["uid"] == uid
            gf += r["home"] if home else r["away"]
            ga += r["away"] if home else r["home"]
            used += 1
        return [gf, ga, used]

    fh, fa = form_gls(last_h, hu), form_gls(last_a, au)
    # need enough form even if season is thin (cups)
    if fh[2] < MIN_FORM or fa[2] < MIN_FORM:
        return None

    def rate(season_row, form_row, is_home):
        # goals scored / conceded per game, blend 55% season (if >=3) + 45% last-6
        def per(row, idx):
            return (row[idx] / row[2]) if row[2] else None
        s_for, s_ag = per(season_row, 0), per(season_row, 1)
        f_for, f_ag = per(form_row, 0), per(form_row, 1)
        if season_row[2] >= 6 and s_for is not None:
            att = 0.55 * s_for + 0.45 * f_for
            opp = 0.55 * s_ag + 0.45 * f_ag
        else:
            att, opp = f_for, f_ag
        return att, opp

    hatt, happ = rate(gh_, fh, True)
    aatt, aapp = rate(ga_, fa, False)
    # each side's expected goals: avg of their attack and opponent's defence
    lh = max(0.2, (hatt + aapp) / 2 * 1.12)
    la = max(0.2, (aatt + happ) / 2 * 0.9)
    # light H2H nudge
    h2h_rows = []
    for z in (h2h or {}).get("matches") or []:
        r = z.get("result") or {}
        if r.get("home") is None:
            continue
        if (z.get("time") or {}).get("uts", 0) >= now:
            continue
        home = z["teams"]["home"]["uid"] == hu
        h2h_rows.append((r["home"] if home else r["away"], r["away"] if home else r["home"]))
    if len(h2h_rows) >= 4:
        hf = sum(a for a, _ in h2h_rows) / len(h2h_rows)
        af = sum(b for _, b in h2h_rows) / len(h2h_rows)
        lh = 0.85 * lh + 0.15 * max(0.2, hf)
        la = 0.85 * la + 0.15 * max(0.2, af)
    return lh, la, fh[2], fa[2], "season+form+h2h" if len(h2h_rows) >= 4 else "season+form"


def table_pos(info, hu, au):
    mm = (info or {}).get("match") or {}
    season = mm.get("_seasonid")
    if not season:
        return None, None, None
    try:
        tabs = (sr_get(f"stats_season_tables/{season}") or {}).get("tables") or []
        pos = {r["team"]["uid"]: r["pos"] for tb in tabs for r in tb.get("tablerows") or []}
        n = max((len(tb.get("tablerows") or []) for tb in tabs), default=0)
        return pos.get(hu), pos.get(au), n
    except Exception:
        return None, None, None


def last_matches(uid):
    data = sr_get(f"stats_team_lastx/{uid}/60") or {}
    rows = data.get("matches") or []
    rows = sorted(rows, key=lambda z: -((z.get("time") or {}).get("uts") or 0))
    return rows


def perspective(rows, uid, n=6):
    out = []
    for z in rows:
        r = z.get("result") or {}
        if r.get("home") is None:
            continue
        home = z["teams"]["home"]["uid"] == uid
        out.append((r["home"] if home else r["away"], r["away"] if home else r["home"]))
        if len(out) >= n:
            break
    return out


def model_prob(mid, spec, desc, oid, M, lh, la):
    """Return model probability for a market, or None if we will not book it."""
    mid = str(mid)
    desc = (desc or "").strip()
    # House vetoes
    if mid == "29" and desc.lower() in {"no", "ng", "btts no"}:
        return None
    if mid == "10" and desc.lower() in {"home or away", "12"}:
        return None

    pH = sum_where(M, lambda i, j: i > j)
    pD = sum_where(M, lambda i, j: i == j)
    pA = sum_where(M, lambda i, j: i < j)

    if mid == "1":
        return {"Home": pH, "Draw": pD, "Away": pA}.get(desc)
    if mid == "10":
        return {"Home or Draw": pH + pD, "Draw or Away": pD + pA, "Home or Away": pH + pA}.get(desc)
    if mid == "11":
        if desc == "Home" and pH + pA > 0:
            return pH / (pH + pA)
        if desc == "Away" and pH + pA > 0:
            return pA / (pH + pA)
        return None
    if mid == "18":
        line = half_line(spec)
        if line is None:
            return None
        need = math.floor(line) + 1  # over 2.5 -> 3+
        tot_over = sum_where(M, lambda i, j: i + j >= need)
        if desc.lower().startswith("over"):
            return tot_over
        if desc.lower().startswith("under"):
            return 1 - tot_over
        return None
    if mid == "19":
        line = half_line(spec)
        if line is None:
            return None
        need = math.floor(line) + 1
        p = sum_where(M, lambda i, j: i >= need)
        if desc.lower().startswith("over"):
            return p
        if desc.lower().startswith("under"):
            return 1 - p
        return None
    if mid == "20":
        line = half_line(spec)
        if line is None:
            return None
        need = math.floor(line) + 1
        p = sum_where(M, lambda i, j: j >= need)
        if desc.lower().startswith("over"):
            return p
        if desc.lower().startswith("under"):
            return 1 - p
        return None
    if mid == "29":
        btts = sum_where(M, lambda i, j: i > 0 and j > 0)
        if desc.lower() in {"yes", "gg"}:
            return btts
        return None
    # First-half: ~45% of full-time goals
    if mid in {"60", "68", "64"}:
        Mh = matrix(lh * 0.45, la * 0.45)
        if mid == "60":
            return {"Home": sum_where(Mh, lambda i, j: i > j),
                    "Draw": sum_where(Mh, lambda i, j: i == j),
                    "Away": sum_where(Mh, lambda i, j: i < j)}.get(desc)
        if mid == "64":
            h = sum_where(Mh, lambda i, j: i > j)
            a = sum_where(Mh, lambda i, j: i < j)
            if desc == "Home" and h + a:
                return h / (h + a)
            if desc == "Away" and h + a:
                return a / (h + a)
            return None
        if mid == "68":
            line = half_line(spec)
            if line is None:
                return None
            need = math.floor(line) + 1
            tot_over = sum_where(Mh, lambda i, j: i + j >= need)
            if desc.lower().startswith("over"):
                return tot_over
            if desc.lower().startswith("under"):
                return 1 - tot_over
            return None
    if mid in {"83", "90", "85", "86"}:
        M2 = matrix(lh * 0.55, la * 0.55)
        if mid == "83":
            return {"Home": sum_where(M2, lambda i, j: i > j),
                    "Draw": sum_where(M2, lambda i, j: i == j),
                    "Away": sum_where(M2, lambda i, j: i < j)}.get(desc)
        if mid == "86":
            h = sum_where(M2, lambda i, j: i > j)
            a = sum_where(M2, lambda i, j: i < j)
            if desc == "Home" and h + a:
                return h / (h + a)
            if desc == "Away" and h + a:
                return a / (h + a)
            return None
        if mid == "85":
            h = sum_where(M2, lambda i, j: i > j)
            d = sum_where(M2, lambda i, j: i == j)
            a = sum_where(M2, lambda i, j: i < j)
            return {"Home or Draw": h + d, "Draw or Away": d + a, "Home or Away": h + a}.get(desc)
        if mid == "90":
            line = half_line(spec)
            if line is None:
                return None
            need = math.floor(line) + 1
            tot_over = sum_where(M2, lambda i, j: i + j >= need)
            if desc.lower().startswith("over"):
                return tot_over
            if desc.lower().startswith("under"):
                return 1 - tot_over
            return None
    return None


MARKET_RANK = {
    "1": 0, "10": 1, "18": 2, "29": 3, "11": 4, "19": 5, "20": 6,
    "60": 7, "68": 8, "64": 9, "83": 10, "90": 11, "85": 12, "86": 13,
}


def in_odds_band(odds):
    try:
        od = float(odds)
    except (TypeError, ValueError):
        return False
    return ODDS_MIN - 1e-9 <= od <= ODDS_MAX + 1e-9


def score_event(e, ev, info):
    name = f"{e.get('homeTeamName')} v {e.get('awayTeamName')}"
    if not ev or ev.get("matchStatus") not in {"Not start", "0", "", None}:
        return None, "started or no event"
    mm = (info or {}).get("match") or {}
    teams = mm.get("teams") or {}
    hu = (teams.get("home") or {}).get("uid")
    au = (teams.get("away") or {}).get("uid")
    if not hu or not au:
        return None, "no sportradar teams"
    last_h, last_a = last_matches(hu), last_matches(au)
    h2h = sr_get(f"stats_team_versusrecent/{hu}/{au}") or {}
    est = estimate_lambdas(info, last_h, last_a, h2h, hu, au)
    if not est:
        return None, "insufficient form/stats"
    lh, la, nh, na, src = est
    hp, ap, ntab = table_pos(info, hu, au)
    # common-sense: skip top-5 v top-5 / bottom-3 v bottom-3 in a 10+ team table
    if hp and ap and ntab and ntab >= 10 and ((hp <= 5 and ap <= 5) or (hp > ntab - 3 and ap > ntab - 3)):
        return None, f"even matchup ({hp} v {ap}/{ntab})"
    M = matrix(lh, la)
    pH = sum_where(M, lambda i, j: i > j)
    pA = sum_where(M, lambda i, j: i < j)
    board = devig(market_1x2(ev))
    if board:
        if board.get("Home", 0) >= 0.55 and pH < 0.40:
            return None, "model disagrees with the 1X2 board (home favourite)"
        if board.get("Away", 0) >= 0.55 and pA < 0.40:
            return None, "model disagrees with the 1X2 board (away favourite)"
    lg = ((e.get("sport") or {}).get("category") or {})
    league = f"{lg.get('name') or ''} - {(lg.get('tournament') or {}).get('name') or ''}".strip(" -")
    cands = []
    for mkt in ev.get("markets") or []:
        mid = str(mkt.get("id") or "")
        spec = mkt.get("specifier") or ""
        mname = mkt.get("name") or mkt.get("marketName") or mid
        for o in mkt.get("outcomes") or []:
            if str(o.get("isActive", 1)) != "1":
                continue
            if not in_odds_band(o.get("odds")):
                continue
            odds = float(o["odds"])
            implied = 1.0 / odds
            true_p = model_prob(mid, spec, o.get("desc"), o.get("id"), M, lh, la)
            if true_p is None or true_p <= 0 or true_p >= 0.995:
                continue
            ev_val = true_p * odds - 1.0
            if ev_val < MIN_EV:
                continue
            # reject "vacuum" totals far from the goal expectation (Under 5.5, team Under 3.5, etc.)
            line = half_line(spec)
            if line is not None:
                if mid == "18" and abs(line - (lh + la)) >= 1.5:
                    continue
                if mid == "19" and abs(line - lh) >= 1.25:
                    continue
                if mid == "20" and abs(line - la) >= 1.25:
                    continue
                if mid == "68" and abs(line - 0.45 * (lh + la)) >= 1.25:
                    continue
                if mid == "90" and abs(line - 0.55 * (lh + la)) >= 1.25:
                    continue
            cands.append({
                "eventId": e["eventId"],
                "match": name,
                "league": league,
                "market": mname,
                "selection": o.get("desc"),
                "odds": odds,
                "marketId": mid,
                "specifier": spec,
                "outcomeId": str(o.get("id")),
                "true_p": round(true_p, 4),
                "implied": round(implied, 4),
                "ev": round(ev_val, 4),
                "why": (
                    f"{src}; λ {lh:.2f}-{la:.2f}; model {true_p:.0%} vs implied {implied:.0%} "
                    f"(edge {ev_val:.0%})"
                    + (f"; table {hp} v {ap}/{ntab}" if hp and ap else "")
                ),
                "lambda": [round(lh, 3), round(la, 3)],
                "form_games": [nh, na],
            })
    if not cands:
        return None, "no 1.20–1.60 market with an edge"
    cands.sort(key=lambda c: (-c["ev"], -c["true_p"], MARKET_RANK.get(c["marketId"], 99), c["odds"]))
    best = cands[0]
    best["alternatives"] = [
        {k: a[k] for k in ("market", "selection", "odds", "ev", "true_p")}
        for a in cands[1:6]
    ]
    ko = dt.datetime.fromtimestamp(ts_ms(e), dt.timezone.utc)
    best["date"] = ko.date().isoformat()
    best["ko"] = ko.strftime("%H:%M")
    return best, None


def chunk(items, n):
    return [items[i:i + n] for i in range(0, len(items), n)]


def codes_from(books):
    out, odds, picks, notes = {}, {}, {}, {}
    for name, res in (books or {}).items():
        if not isinstance(res, dict):
            notes[name] = str(res)[:160]
            continue
        if res.get("error"):
            notes[name] = str(res["error"])[:160]
            continue
        code = res.get("code")
        if not code:
            notes[name] = "no code"
            continue
        out[name] = code
        if res.get("totalOdds") is not None:
            odds[name] = res["totalOdds"]
        if res.get("legs") is not None:
            picks[name] = res["legs"]
    return out, odds, picks, notes


def book_slip(legs):
    payload = []
    for p in legs:
        payload.append({
            "eventId": p["eventId"],
            "marketId": p["marketId"],
            "specifier": p.get("specifier") or None,
            "outcomeId": p["outcomeId"],
            "odds": p["odds"],
            "match": p.get("match"),
        })
    return book_all(payload)


def publish(slips, day, report, dry_run=False):
    path = REPO_DIR / "home-picks.json"
    doc = {}
    if path.exists():
        try:
            doc = json.loads(path.read_text())
        except Exception:
            doc = {}
    existing = [
        s for s in (doc.get("slips") or [])
        if s.get("strategy") != STRATEGY
    ]
    doc["DATA_UPDATED"] = now_utc().strftime("%Y-%m-%dT%H:%M:%SZ")
    doc["date"] = doc.get("date") or day
    doc.setdefault("leagues", doc.get("leagues") or [])
    doc.setdefault("picks", doc.get("picks") or [])
    doc.setdefault("homeCode", doc.get("homeCode") or {})
    doc["slips"] = existing + slips
    out_dir = RESEARCH_DIR / "sb-morning"
    out_dir.mkdir(parents=True, exist_ok=True)
    report_path = out_dir / f"{day}.json"
    report_path.write_text(json.dumps(report, indent=1, ensure_ascii=False))
    if dry_run:
        print("publish: dry-run, not writing home-picks.json")
        return path, report_path
    path.write_text(json.dumps(doc, indent=1, ensure_ascii=False))
    return path, report_path


def make_slip(part, idx, parts, day):
    tot = round(math.prod(p["odds"] for p in part), 2)
    risk = "safe" if tot <= 2.2 else "medium"
    books = book_all and None  # placeholder, filled by caller
    return tot, risk


def run(day=None, dry_run=False):
    day = day or today_accra()
    print(f"sb_morning_markets day={day} dry_run={dry_run}")
    events = scan_upcoming()
    fixtures, skipped = eligible_today(events, day)
    print(f"upcoming={len(events)} today_eligible={len(fixtures)} skipped={len(skipped)}")
    with cf.ThreadPoolExecutor(6) as pool:
        evs = list(pool.map(lambda e: fact(e["eventId"]), fixtures))
        infos = list(pool.map(lambda e: sr_get("match_info/" + e["eventId"].split(":")[-1]), fixtures))
    picks, rejected = [], dict(skipped)
    for e, ev, info in zip(fixtures, evs, infos):
        best, why = score_event(e, ev, info)
        name = f"{e.get('homeTeamName')} v {e.get('awayTeamName')}"
        if not best:
            rejected[name] = why
            print(f"  skip {name}: {why}")
            continue
        picks.append(best)
        print(
            f"  PICK {best['ko']} {name} | {best['market']} {best['selection']} "
            f"@ {best['odds']} ev={best['ev']:.2%} p={best['true_p']:.0%} — {best['why']}"
        )
    picks.sort(key=lambda p: (p["ko"], -p["ev"]))
    slips = []
    if not dry_run and picks:
        for i, part in enumerate(chunk(picks, LEGS_PER_SLIP), 1):
            tot = round(math.prod(p["odds"] for p in part), 2)
            print(f"booking slip {i} ({len(part)} legs, {tot} odds)")
            books = book_slip(part)
            codes, book_odds, book_picks, notes = codes_from(books)
            print("  codes", codes, "notes", notes or "")
            legs = []
            for p in part:
                legs.append({
                    "eventId": p["eventId"],
                    "match": p["match"],
                    "league": p.get("league"),
                    "date": p["date"],
                    "ko": p["ko"],
                    "market": p["market"],
                    "selection": p["selection"],
                    "odds": p["odds"],
                    "marketId": p["marketId"],
                    "specifier": p.get("specifier") or "",
                    "outcomeId": p["outcomeId"],
                    "true_p": p["true_p"],
                    "ev": p["ev"],
                    "why": p["why"],
                    "result": "pending",
                })
            nparts = math.ceil(len(picks) / LEGS_PER_SLIP)
            name = "SportyBet Stats"
            if nparts > 1:
                name = f"SportyBet Stats · part {i}/{nparts}"
            slips.append({
                "name": name,
                "totalOdds": tot,
                "legs": legs,
                "codes": codes,
                "bookOdds": book_odds,
                "bookPicks": book_picks,
                "bookNotes": notes,
                "risk": "safe" if tot <= 2.2 else "medium",
                "strategy": STRATEGY,
                "bookedAt": now_utc().isoformat(timespec="seconds"),
                "bookStatus": "ok" if codes.get("sportybet") else "partial",
                "targetDate": day,
                "note": (
                    "One best SportyBet market per match, odds 1.20–1.60, "
                    "scored from SportyBet tables, form, H2H and a Poisson model."
                ),
            })
    elif dry_run:
        for i, part in enumerate(chunk(picks, LEGS_PER_SLIP), 1):
            tot = round(math.prod(p["odds"] for p in part), 2)
            print(f"dry-run slip {i}: {len(part)} legs, {tot} odds")
    report = {
        "date": day,
        "generatedAt": now_utc().isoformat(),
        "eligible": len(fixtures),
        "picked": len(picks),
        "picks": [{k: p[k] for k in p if k != "alternatives"} | {"alternatives": p.get("alternatives")} for p in picks],
        "rejected": rejected,
        "slips": [
            {"name": s["name"], "totalOdds": s["totalOdds"], "codes": s.get("codes"), "legs": len(s["legs"])}
            for s in slips
        ],
    }
    publish(slips, day, report, dry_run=dry_run or not slips)
    print(json.dumps({"picked": len(picks), "slips": len(slips), "rejected": len(rejected)}, indent=2))
    return report


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--date", help="YYYY-MM-DD in Africa/Accra")
    args = ap.parse_args(argv)
    run(day=args.date, dry_run=args.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
