#!/usr/bin/env python3
"""NerdyTips / Betting Strategies candidate generators (inbox picks).

Each strategy is a pure function over a SportyBet event payload. Candidates are
written to engine/inbox/nerdytips-*.json and then pass through the EXISTING
Predict2u rule pipeline (matchup_rules, obscure goals-only, no NG, no DC 12,
1X/X2 ≤1.35, combine-to-25, ≤50-leg split, all no-login bookmakers).

Strategies
----------
1) streak_2plus     — market 60010 "Any Team To Score 2+ Goals in a Row" YES <1.40
                      → book team Win / team to score 2+ / match Over 2.5
2) team_win_lt_150  — win-only legs strictly below 1.50
3) draw_rules       — draw>3.50 & unbalanced 1X2 → Over 1.5
                      draw<3.10 & balanced → Under 3.5
                      draw>4.00 & balanced → GG (exception path; still subject to site rules)
4) heavy_home_fav   — Home AH −1.0 in 1.20–1.90 (filter) → Home Win / O2.5 / Home 2+
5) team_total_o25   — a team's Over 2.5 <2.00 → Win / team 2+ / match O2.5
6) exclusive_o25    — Under 3.5 >1.50 AND one team Over 1.5 <1.60 → match Over 2.5
7) betmines_trends  — both sides support pick; price vs trend, league avg, H2H,
                      last 3–5 scores, table (reads optional research JSON)

Reference Nov 7 codes (manual QA only): AJ8D6U, FMCFQU, 8N84AX, BVJQ7E, DJ3X8P,
CFDPD8, CQGJSM, FZQFND, E4HFPR.
"""
from __future__ import annotations
import datetime as dt, json, os, re, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parent), str(HERE.parent.parent)]
try:
    import matchup_rules as MR
except Exception:  # pragma: no cover
    MR = None

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36"
SKIP = re.compile(
    r"\b(U-?\d{2}|youth|junior|reserves?|women|woman|ladies|primavera|academy|amateur|"
    r"friendly|simulat|srl|esoccer|esports)\b|\(w\)",
    re.I,
)
STRATEGIES = (
    "streak_2plus",
    "team_win_lt_150",
    "draw_rules",
    "heavy_home_fav",
    "team_total_o25",
    "exclusive_o25",
    "betmines_trends",
)


def curl_json(url, timeout=25):
    raw = subprocess.run(
        ["curl", "-s", "-m", str(timeout), "-A", UA, "-H", "Accept: application/json", url],
        capture_output=True, text=True,
    ).stdout
    try:
        return json.loads(raw) if raw and raw.strip()[:1] in "{[" else {}
    except Exception:
        return {}


def outcome(markets, mid, spec="", oid=None, startswith=None, desc_re=None):
    for m in markets or []:
        if str(m.get("id")) != str(mid):
            continue
        if (m.get("specifier") or "") != (spec or ""):
            continue
        for o in m.get("outcomes") or []:
            desc = str(o.get("desc") or "")
            if oid is not None and str(o.get("id")) != str(oid):
                continue
            if startswith and not desc.startswith(startswith):
                continue
            if desc_re and not re.search(desc_re, desc, re.I):
                continue
            try:
                return m, o, float(o.get("odds") or 0)
            except Exception:
                return None
    return None


def x12_prices(markets):
    hit = outcome(markets, "1", "", oid="1"), outcome(markets, "1", "", oid="2"), outcome(markets, "1", "", oid="3")
    try:
        h = hit[0][2] if hit[0] else None
        d = hit[1][2] if hit[1] else None
        a = hit[2][2] if hit[2] else None
        return h, d, a
    except Exception:
        return None, None, None


def unbalanced(h, d, a) -> bool:
    if not h or not a:
        return False
    return abs(h - a) / max(h, a) >= 0.25 or min(h, a) <= 1.70


def balanced(h, d, a) -> bool:
    if not h or not a:
        return False
    return abs(h - a) / max(h, a) < 0.20 and min(h, a) > 1.80


def base_pick(ev, m, o, selection, strategy, extra=None):
    home = ev.get("homeTeamName") or ""
    away = ev.get("awayTeamName") or ""
    try:
        league = ev["sport"]["category"]["tournament"]["name"]
    except Exception:
        league = ev.get("tournamentName") or ""
    ts = ev.get("estimateStartTime") or 0
    ko = dt.datetime.fromtimestamp(ts / 1000, dt.timezone.utc) if ts else None
    h, d, a = x12_prices(ev.get("markets") or [])
    p = {
        "eventId": ev.get("eventId") or ev.get("event_id"),
        "match": f"{home} v {away}",
        "home": home,
        "away": away,
        "league": league,
        "market": m.get("desc") or m.get("name") or selection,
        "marketId": str(m.get("id")),
        "specifier": m.get("specifier") or "",
        "selection": selection,
        "outcomeId": str(o.get("id")),
        "odds": float(o.get("odds") or 0),
        "kickoff": ko.isoformat() if ko else None,
        "ts": ts,
        "strategy": strategy,
        "source": "nerdytips",
        "x12": f"{h}/{d}/{a}" if h and d and a else None,
    }
    if extra:
        p.update(extra)
    return p


def passes_site_rules(p: dict) -> bool:
    """Hard vetoes only; full matchup/check runs later in the pipeline."""
    if MR is None:
        return True
    if MR.is_btts_no(p):
        return False
    if MR.is_dc_vetoed(p):
        return False
    if MR.is_obscure_league_non_goals(p):
        return False
    return True


def pick_book_from_filter(ev, strategy, prefer):
    """prefer: list of (mid, spec, oid, selection) in priority order."""
    markets = ev.get("markets") or []
    for mid, spec, oid, sel in prefer:
        hit = outcome(markets, mid, spec, oid=oid)
        if not hit:
            continue
        m, o, odds = hit
        if odds <= 1.0:
            continue
        p = base_pick(ev, m, o, sel, strategy)
        if passes_site_rules(p):
            return p
    return None


# ---------- strategy functions ----------

def streak_2plus(ev: dict) -> dict | None:
    """Filter: market 60010 YES strictly <1.40 → book Win / team 2+ / O2.5."""
    markets = ev.get("markets") or []
    filt = outcome(markets, "60010", "", desc_re=r"yes|2\+")
    if not filt:
        # some feeds use outcome id 4 / Yes
        filt = outcome(markets, "60010", "", oid="4")
    if not filt or filt[2] >= 1.40:
        return None
    h, d, a = x12_prices(markets)
    side = "H" if (h and a and h <= a) else "A"
    team_mid = "19" if side == "H" else "20"
    win_oid = "1" if side == "H" else "3"
    win_sel = "Home" if side == "H" else "Away"
    return pick_book_from_filter(ev, "streak_2plus", [
        ("1", "", win_oid, win_sel),
        (team_mid, "total=1.5", "12", "Over 1.5"),
        ("18", "total=2.5", "12", "Over 2.5"),
    ])


def team_win_lt_150(ev: dict) -> dict | None:
    markets = ev.get("markets") or []
    h, d, a = x12_prices(markets)
    cands = []
    if h and h < 1.50:
        cands.append(("1", "", "1", "Home", h))
    if a and a < 1.50:
        cands.append(("1", "", "3", "Away", a))
    if not cands:
        return None
    cands.sort(key=lambda x: x[4])
    mid, spec, oid, sel, _ = cands[0]
    hit = outcome(markets, mid, spec, oid=oid)
    if not hit:
        return None
    m, o, odds = hit
    p = base_pick(ev, m, o, sel, "team_win_lt_150")
    return p if passes_site_rules(p) else None


def draw_rules(ev: dict) -> dict | None:
    markets = ev.get("markets") or []
    h, d, a = x12_prices(markets)
    if not d:
        return None
    if d > 3.50 and unbalanced(h, d, a):
        return pick_book_from_filter(ev, "draw_rules_o15", [("18", "total=1.5", "12", "Over 1.5")])
    if d < 3.10 and balanced(h, d, a):
        return pick_book_from_filter(ev, "draw_rules_u35", [("18", "total=3.5", "13", "Under 3.5")])
    if d > 4.00 and balanced(h, d, a):
        # GG exception path — still must pass site rules (NG banned; GG allowed)
        hit = outcome(markets, "29", "", oid="74") or outcome(markets, "29", "", startswith="Yes")
        if hit:
            m, o, odds = hit
            p = base_pick(ev, m, o, "GG", "draw_rules_gg")
            return p if passes_site_rules(p) else None
    return None


def heavy_home_fav(ev: dict) -> dict | None:
    markets = ev.get("markets") or []
    ah = outcome(markets, "16", "hcp=-1", startswith="Home")
    if not ah or not (1.20 <= ah[2] <= 1.90):
        return None
    return pick_book_from_filter(ev, "heavy_home_fav", [
        ("1", "", "1", "Home"),
        ("18", "total=2.5", "12", "Over 2.5"),
        ("19", "total=1.5", "12", "Over 1.5"),
    ])


def team_total_o25(ev: dict) -> dict | None:
    markets = ev.get("markets") or []
    cands = []
    for mid, side in (("19", "H"), ("20", "A")):
        hit = outcome(markets, mid, "total=2.5", oid="12")
        if hit and hit[2] < 2.00:
            cands.append((side, hit[2], mid))
    if not cands:
        return None
    cands.sort(key=lambda x: x[1])
    side, _, team_mid = cands[0]
    win_oid = "1" if side == "H" else "3"
    win_sel = "Home" if side == "H" else "Away"
    return pick_book_from_filter(ev, "team_total_o25", [
        ("1", "", win_oid, win_sel),
        (team_mid, "total=1.5", "12", "Over 1.5"),
        ("18", "total=2.5", "12", "Over 2.5"),
    ])


def exclusive_o25(ev: dict) -> dict | None:
    markets = ev.get("markets") or []
    u35 = outcome(markets, "18", "total=3.5", oid="13")
    if not u35 or u35[2] <= 1.50:
        return None
    team_ok = False
    for mid in ("19", "20"):
        t = outcome(markets, mid, "total=1.5", oid="12")
        if t and t[2] < 1.60:
            team_ok = True
            break
    if not team_ok:
        return None
    return pick_book_from_filter(ev, "exclusive_o25", [("18", "total=2.5", "12", "Over 2.5")])


def betmines_trends(ev: dict, trends: dict | None = None) -> dict | None:
    """Both teams must support the pick. Uses optional trends map keyed by eventId.

    Expected trends[eventId] = {
      'pick': 'Over 2.5'|'Home'|'Away'|'GG'|...,
      'supportHome': True, 'supportAway': True,
      'priceOk': True, 'leagueAvgOk': True, 'h2hOk': True,
      'formOk': True, 'tableOk': True
    }
    Without trends data this strategy yields nothing (no padding).
    """
    trends = trends or {}
    eid = ev.get("eventId") or ev.get("event_id")
    t = trends.get(eid) or trends.get(str(eid))
    if not t:
        return None
    if not (t.get("supportHome") and t.get("supportAway")):
        return None
    for flag in ("priceOk", "leagueAvgOk", "h2hOk", "formOk", "tableOk"):
        if t.get(flag) is False:
            return None
    pick = (t.get("pick") or "Over 2.5").strip()
    markets = ev.get("markets") or []
    mapping = {
        "Over 2.5": ("18", "total=2.5", "12", "Over 2.5"),
        "Over 1.5": ("18", "total=1.5", "12", "Over 1.5"),
        "Under 3.5": ("18", "total=3.5", "13", "Under 3.5"),
        "Home": ("1", "", "1", "Home"),
        "Away": ("1", "", "3", "Away"),
        "GG": ("29", "", "74", "GG"),
    }
    mid, spec, oid, sel = mapping.get(pick, mapping["Over 2.5"])
    hit = outcome(markets, mid, spec, oid=oid)
    if not hit and pick == "GG":
        hit = outcome(markets, "29", "", startswith="Yes")
    if not hit:
        return None
    m, o, odds = hit
    p = base_pick(ev, m, o, sel, "betmines_trends", extra={"trend": t})
    return p if passes_site_rules(p) else None


STRATEGY_FNS = {
    "streak_2plus": streak_2plus,
    "team_win_lt_150": team_win_lt_150,
    "draw_rules": draw_rules,
    "heavy_home_fav": heavy_home_fav,
    "team_total_o25": team_total_o25,
    "exclusive_o25": exclusive_o25,
}


def skip_event(ev: dict) -> bool:
    home = ev.get("homeTeamName") or ""
    away = ev.get("awayTeamName") or ""
    try:
        league = ev["sport"]["category"]["tournament"]["name"]
    except Exception:
        league = ev.get("tournamentName") or ""
    return bool(SKIP.search(f"{home} {away} {league}"))


def upcoming_ids(days=1):
    ids, now = [], dt.datetime.now(dt.timezone.utc)
    end = now + dt.timedelta(days=days)
    for page in range(1, 8):
        d = curl_json(
            "https://www.sportybet.com/api/gh/factsCenter/pcUpcomingEvents"
            f"?sportId=sr%3Asport%3A1&marketId=1%2C14%2C16%2C18%2C19%2C20%2C29&pageSize=100&pageNum={page}&option=1"
        ).get("data") or {}
        n = 0
        for t in d.get("tournaments") or []:
            for e in t.get("events") or []:
                n += 1
                ts = e.get("estimateStartTime") or 0
                ko = dt.datetime.fromtimestamp(ts / 1000, dt.timezone.utc) if ts else now
                if now < ko <= end:
                    ids.append(e.get("eventId"))
        if not n or page * 100 >= int(d.get("totalNum") or 0):
            break
    return ids


def fetch_event(eid: str) -> dict:
    data = curl_json(f"https://www.sportybet.com/api/gh/factsCenter/event?eventId={eid}&productId=3").get("data") or {}
    if data:
        data.setdefault("eventId", eid)
    return data


def load_trends():
    research = Path(os.environ.get("RESEARCH_DIR") or HERE.parent / "data")
    for name in ("betmines_trends.json", "nerdytips_trends.json"):
        p = research / name
        if p.exists():
            try:
                return json.loads(p.read_text())
            except Exception:
                pass
    return {}


def scan(days=1, limit=120) -> dict:
    trends = load_trends()
    by_strategy = {s: [] for s in STRATEGIES}
    seen_eid = set()
    for eid in upcoming_ids(days)[:limit]:
        ev = fetch_event(eid)
        if not ev or skip_event(ev):
            continue
        eid = ev.get("eventId") or eid
        for name, fn in STRATEGY_FNS.items():
            p = fn(ev)
            if p and eid not in seen_eid:
                # one market per game across these strategies (first hit wins by strategy order)
                by_strategy[name].append(p)
                seen_eid.add(eid)
                break
        if eid not in seen_eid:
            p = betmines_trends(ev, trends)
            if p:
                by_strategy["betmines_trends"].append(p)
                seen_eid.add(eid)
    return by_strategy


def write_inbox(by_strategy: dict) -> Path:
    inbox = Path(os.environ.get("INBOX_DIR") or HERE.parent / "inbox")
    inbox.mkdir(parents=True, exist_ok=True)
    picks = []
    for name in STRATEGIES:
        for p in by_strategy.get(name) or []:
            picks.append(p)
    doc = {
        "source": "nerdytips-strategies",
        "generated": dt.datetime.now(dt.timezone.utc).isoformat(),
        "strategies": {k: len(v) for k, v in by_strategy.items()},
        "picks": picks,
        "note": "Candidates only — existing Predict2u pipeline applies all standing rules; no padding.",
    }
    out = inbox / "nerdytips-strategies.json"
    out.write_text(json.dumps(doc, indent=1, ensure_ascii=False))
    # also per-strategy files for debugging
    for name, rows in by_strategy.items():
        (inbox / f"nerdytips-{name}.json").write_text(
            json.dumps({"source": name, "picks": rows, "generated": doc["generated"]}, indent=1, ensure_ascii=False)
        )
    print(f"nerdytips: {sum(len(v) for v in by_strategy.values())} picks -> {out} ({doc['strategies']})")
    return out


def main(argv=None):
    by = scan(days=1)
    write_inbox(by)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
