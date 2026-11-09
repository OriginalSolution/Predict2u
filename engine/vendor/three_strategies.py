#!/usr/bin/env python3
"""Bets For The Day three-strategy set — daily High Odds masters (HIGH RISK, no guarantees).

Strategies (strategy-internal rules only; still never NG, never DC 12):
  1) O2.5 when >=2 of: O2.5 price 1.20–1.40; 1H O1.5 <2.00; league season avg goals/match >2.5
     (<20 games = unknown; missing = not a pass). Exclude reserves/youth/women/amateur/cups.
  2) Team top-3 OR won last 3: win if priced <=1.45 else DNB. Top flights only.
  3) Team bottom-3 OR winless last 3: double chance against it (1X/X2 only, never 12). Top flights only.
     2&3: no top-5 v top-5 or bottom-3 v bottom-3.
  Overlap (one pick/match): DC beats win/DNB on the same team; O2.5 that passes all 3 conditions
  beats a result pick; O2.5 that passes only 2 loses to a result pick.
  ASC master = 50 lowest odds; DESC = 50 highest; each split 25+25. Drop started. No padding.
  Extra screens (top-5 v bottom-3 top-flight straight wins): weaker to-score >1.70; stronger AH −1.0 <1.90.

Published via engine/data/ho-masters/ as HIGH RISK. Booked on SportyBet + Football.com/MSport/Betika/BetPawa.
"""
from __future__ import annotations
import datetime as dt, json, math, os, re, subprocess, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parent), str(HERE.parent.parent)]
import matchup_rules as MR
import split_codes as SC
from engine.paths import RESEARCH_DIR, ENGINE_DIR, REPO_DIR

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36"
SR = "https://stats.fn.sportradar.com/sportybet/en/Europe:Berlin/gismo/"
SKIP = re.compile(r"\b(U-?\d{2}|youth|junior|reserves?|women|woman|ladies|primavera|academy|amateur|"
                  r"friendly|cup|trophy|play-?off|qualifier|simulat|srl|esoccer|esports)\b|\(w\)", re.I)
TEAMX = re.compile(r"(\s(II|B|W|U-?\d{2})|\s\(W\))$")
TOP_FLIGHT = re.compile(r"(premier|primera|serie a|ligue 1|bundesliga|eredivisie|liga portugal|"
                        r"scottish premiership|belgian pro|superlig|superliga|ekstraklasa|"
                        r"allsvenskan|eliteserien|veikkausliiga|swiss super|austrian bundesliga|"
                        r"championship|primeira|laliga|la liga|serie a|ligue 1)", re.I)


def curl(url, t=25):
    r = subprocess.run(["curl", "-s", "-m", str(t), "-A", UA, "-H", "Accept: application/json", url], capture_output=True, text=True)
    try: return json.loads(r.stdout) if r.stdout and r.stdout.strip()[:1] in "{[" else {}
    except Exception: return {}


def G(path):
    d = curl(SR + path)
    return (d.get("doc") or [{}])[0].get("data") or {}


def skip_side(name, league=""):
    return bool(SKIP.search(f"{name} {league}") or TEAMX.search((name or "").strip()))


def outcome(markets, mid, spec, oid=None, startswith=None):
    for m in markets or []:
        if str(m.get("id")) != str(mid): continue
        if (m.get("specifier") or "") != (spec or ""): continue
        for o in m.get("outcomes") or []:
            if oid and str(o.get("id")) != str(oid): continue
            if startswith and not str(o.get("desc") or "").startswith(startswith): continue
            try: return m, o, float(o.get("odds") or 0)
            except Exception: return None
    return None


def upcoming(days=1):
    ids, now = [], dt.datetime.now(dt.timezone.utc)
    end = now + dt.timedelta(days=days)
    for page in range(1, 10):
        d = curl("https://www.sportybet.com/api/gh/factsCenter/pcUpcomingEvents"
                 f"?sportId=sr%3Asport%3A1&marketId=1%2C14%2C16%2C18%2C19%2C20%2C29&pageSize=100&pageNum={page}&option=1").get("data") or {}
        n = 0
        for t in d.get("tournaments") or []:
            for e in t.get("events") or []:
                n += 1; ts = e.get("estimateStartTime") or 0
                ko = dt.datetime.fromtimestamp(ts / 1000, dt.timezone.utc) if ts else now
                if now < ko <= end: ids.append(e.get("eventId"))
        if not n or page * 100 >= int(d.get("totalNum") or 0): break
    return ids


def fetch(eid): return curl(f"https://www.sportybet.com/api/gh/factsCenter/event?eventId={eid}&productId=3").get("data") or {}


def season_avg_goals(season_id):
    if not season_id: return None, 0
    t = G(f"stats_season_tables/{season_id}").get("tables") or []
    rows = [r for tb in t for r in (tb.get("tablerows") or [])]
    if not rows: return None, 0
    games = sum(int((r.get("winTotal") or 0) + (r.get("drawTotal") or 0) + (r.get("lossTotal") or 0)) for r in rows)
    goals = sum(int(r.get("goalsForTotal") or 0) for r in rows)
    n = games // max(1, len(set(r.get("team", {}).get("uid") for r in rows)))  # approx matches played
    # Prefer average from goals / (games/2) since each match counted twice in W+D+L sum
    matches = games / 2.0
    if matches < 1: return None, 0
    return (goals / matches if matches else None), matches


def table_pos(season_id):
    t = G(f"stats_season_tables/{season_id}").get("tables") or []
    rows = [r for tb in t for r in (tb.get("tablerows") or [])]
    N = max((len(tb.get("tablerows") or []) for tb in t), default=0)
    return {r["team"]["uid"]: r["pos"] for r in rows if r.get("team")}, N


def last3(uid, before_uts):
    ms = G(f"stats_team_lastx/{uid}/60").get("matches") or []
    out = []
    for z in sorted(ms, key=lambda z: -z.get("time", {}).get("uts", 0)):
        if z.get("time", {}).get("uts", 0) >= before_uts: continue
        out.append(z)
        if len(out) >= 3: break
    return out


def form_wins(uid, before_uts):
    L = last3(uid, before_uts); wins = 0
    for z in L:
        res = (z.get("result") or {})
        h, a = int(res.get("home") or 0), int(res.get("away") or 0)
        home = z.get("teams", {}).get("home", {}).get("uid") == uid
        if (home and h > a) or ((not home) and a > h): wins += 1
    return wins, len(L)


def leg(data, mid, spec, oid, market, selection, odds, case, strategy):
    home = data.get("homeTeamName") or ""; away = data.get("awayTeamName") or ""
    league = ""
    try: league = data["sport"]["category"]["tournament"]["name"]
    except Exception: league = data.get("tournamentName") or ""
    ts = data.get("estimateStartTime") or 0
    ko = dt.datetime.fromtimestamp(ts / 1000, dt.timezone.utc) if ts else None
    return dict(eventId=data.get("eventId"), match=f"{home} v {away}", league=league, marketId=str(mid),
                specifier=spec or "", outcomeId=str(oid), market=market, selection=selection, odds=float(odds),
                kickoff=ko.isoformat().replace("+00:00", "Z") if ko else None, date=ko.date().isoformat() if ko else None,
                ko=ko.strftime("%H:%M") if ko else None, case=case, strategy=strategy, result="pending", matchStatus="Not start")


def build_pool(days=1):
    """Return candidate picks keyed by eventId with priority tags."""
    ids = upcoming(days); pool = []; now = dt.datetime.now(dt.timezone.utc)
    print(f"three_strategies: scanning {len(ids)} events", flush=True)
    for eid in ids:
        data = fetch(eid)
        if not data: continue
        home = data.get("homeTeamName") or ""; away = data.get("awayTeamName") or ""
        league = ""
        try: league = data["sport"]["category"]["tournament"]["name"]
        except Exception: league = data.get("tournamentName") or ""
        if skip_side(home, league) or skip_side(away, league): continue
        if SKIP.search(league or ""): continue
        markets = data.get("markets") or []
        mm = data.get("match") or data  # sportradar ids sometimes nested
        # Prefer season id from event payload
        season_id = None
        try: season_id = data["sport"]["category"]["tournament"]["season"]["id"]
        except Exception:
            try: season_id = data.get("_seasonid") or (data.get("season") or {}).get("id")
            except Exception: season_id = None
        # Map SportyBet event → sportradar match via eventId (sr:match:N)
        hu = au = None
        try:
            md = G(f"match_detailsextended/{eid}")
            teams = (md.get("match") or md).get("teams") or {}
            hu = (teams.get("home") or {}).get("uid"); au = (teams.get("away") or {}).get("uid")
            season_id = season_id or (md.get("match") or md).get("_seasonid")
        except Exception: pass
        avg, n_matches = season_avg_goals(season_id) if season_id else (None, 0)
        pos, N = table_pos(season_id) if season_id else ({}, 0)
        hp, ap = pos.get(hu), pos.get(au)
        ts = data.get("estimateStartTime") or 0
        before = ts // 1000 if ts else int(now.timestamp())
        hw, hn = form_wins(hu, before) if hu else (0, 0)
        aw, an = form_wins(au, before) if au else (0, 0)

        # --- Strategy 1: O2.5 ---
        o25 = outcome(markets, "18", "total=2.5", oid="12", startswith="Over")
        fh15 = outcome(markets, "16", "total=1.5", oid="12", startswith="Over")  # 1H Over/Under often mid 16
        if not fh15: fh15 = outcome(markets, "21", "total=1.5", oid="12", startswith="Over")
        passes = 0; why = []
        if o25 and 1.20 <= o25[2] <= 1.40: passes += 1; why.append(f"O2.5@{o25[2]}")
        if fh15 and fh15[2] < 2.00: passes += 1; why.append(f"1HO1.5@{fh15[2]}")
        if avg is not None and n_matches >= 20 and avg > 2.5: passes += 1; why.append(f"avgG={avg:.2f}/n={n_matches:.0f}")
        o25_pick = None
        if o25 and passes >= 2 and not SKIP.search(league or ""):
            o25_pick = leg(data, "18", "total=2.5", o25[1].get("id") or "12", "Over/Under", o25[1].get("desc") or "Over 2.5",
                           o25[2], f"O2.5 {passes}/3: " + ", ".join(why), "o25-2of3")
            o25_pick["o25Passes"] = passes

        # --- Strategies 2 & 3: form / table (top flights) ---
        win_dnb = []; dc_against = []
        top = bool(TOP_FLIGHT.search(league or "")) and N >= 10
        if top and hp and ap:
            # no top5 v top5 / bottom3 v bottom3
            clash_top = hp <= 5 and ap <= 5
            clash_bot = hp > N - 3 and ap > N - 3
            if not clash_top and not clash_bot:
                for side, pos_, wins_, nform_, oid, dnb_oid, dc_oid, label in (
                    ("H", hp, hw, hn, "1", "1", "9", "Home"),
                    ("A", ap, aw, an, "3", "3", "11", "Away"),
                ):
                    strong = (pos_ is not None and pos_ <= 3) or (nform_ >= 3 and wins_ == 3)
                    weak = (pos_ is not None and pos_ > N - 3) or (nform_ >= 3 and wins_ == 0)
                    if strong:
                        w = outcome(markets, "1", "", oid=oid)
                        if w and w[2] <= 1.45 and not MR.is_btts_no({"outcomeId": oid, "marketId": "1"}):
                            win_dnb.append(leg(data, "1", "", oid, "1X2", label, w[2],
                                               f"top3/form win @{w[2]} pos={pos_} form={wins_}/{nform_}", "top3-form-win"))
                        else:
                            d = outcome(markets, "14", "", oid=dnb_oid)  # DNB marketId often 14
                            if not d: d = outcome(markets, "11", "", oid=dnb_oid)
                            if d and not MR.is_double_chance({"marketId": "14", "outcomeId": dnb_oid, "selection": "Draw no bet"}):
                                win_dnb.append(leg(data, "14", "", d[1].get("id") or dnb_oid, "Draw No Bet", f"{label} DNB", d[2],
                                                   f"top3/form DNB @{d[2]} (win>{1.45})", "top3-form-dnb"))
                    if weak:
                        # DC against the weak side: if home is weak → X2 (away or draw); if away weak → 1X
                        dc_oid2 = "11" if side == "H" else "9"
                        dc_sel = "Draw or Away" if side == "H" else "Home or Draw"
                        d = outcome(markets, "10", "", oid=dc_oid2)  # Double chance market
                        if not d: d = outcome(markets, "247", "", oid=dc_oid2)
                        if d and d[2] and not MR.is_dc_vetoed({"marketId": "10", "outcomeId": dc_oid2, "odds": d[2], "selection": dc_sel, "market": "Double Chance"}):
                            # still ban DC 12; 1X/X2 only at any price under the waiver? User said still never DC 12.
                            if dc_oid2 != "10":  # 10 would be 12 on some books; we use 9/11
                                dc_against.append(leg(data, "10", "", dc_oid2, "Double Chance", dc_sel, d[2],
                                                      f"bottom3/form DC against {label} @{d[2]}", "bottom3-form-dc"))

        # Overlap resolution
        chosen = None
        if dc_against: chosen = dc_against[0]
        elif win_dnb: chosen = win_dnb[0]
        if o25_pick:
            if chosen is None: chosen = o25_pick
            elif o25_pick.get("o25Passes", 0) >= 3: chosen = o25_pick  # O2.5 with all 3 beats result
            # else result pick wins over 2/3 O2.5
        if chosen: pool.append(chosen)

        # Extra screens: top5 v bottom3 straight-win overlays (weaker to-score >1.70; stronger AH-1 <1.90)
        if top and hp and ap and ((hp <= 5 and ap > N - 3) or (ap <= 5 and hp > N - 3)):
            strong_home = hp <= 5
            # weaker team to score (team over 0.5)
            weak_mid = "20" if strong_home else "19"
            weak_o = outcome(markets, weak_mid, "total=0.5", oid="12", startswith="Over")
            if weak_o and weak_o[2] > 1.70:
                pool.append(leg(data, weak_mid, "total=0.5", weak_o[1].get("id") or "12",
                                "Team Over/Under", weak_o[1].get("desc") or "Over 0.5", weak_o[2],
                                f"weaker to-score @{weak_o[2]} (top5 v bottom3)", "weaker-score"))
            # stronger AH -1.0
            ah_oid = "1714"  # common SportyBet AH home -1; fall back search
            ah = None
            for m in markets:
                if str(m.get("id")) not in ("16", "221", "223"): continue
                sp = m.get("specifier") or ""
                if "hcp=" not in sp: continue
                try: hcp = float(sp.split("hcp=")[1].split("|")[0])
                except Exception: continue
                want = -1.0 if strong_home else 1.0
                if abs(hcp - want) > 0.01 and abs(hcp + want) > 0.01: continue
                for o in m.get("outcomes") or []:
                    try: od = float(o.get("odds") or 0)
                    except Exception: continue
                    # home AH when strong_home and hcp negative, etc.
                    if strong_home and hcp < 0 and od < 1.90:
                        ah = (m, o, od); break
                    if (not strong_home) and hcp > 0 and od < 1.90:
                        ah = (m, o, od); break
                if ah: break
            if ah and ah[2] < 1.90:
                pool.append(leg(data, ah[0].get("id"), ah[0].get("specifier") or "", ah[1].get("id"),
                                ah[0].get("name") or "Asian Handicap", ah[1].get("desc") or "AH -1", ah[2],
                                f"stronger AH-1 @{ah[2]} (top5 v bottom3)", "ah-minus1-screen"))
    return pool


def one_per_match(pool):
    """Final de-dupe by eventId keeping highest-priority already resolved picks; screens may add 2nd market? Spec says one pick/match for main pool."""
    by = {}
    for p in pool:
        eid = p["eventId"]; cur = by.get(eid)
        if not cur: by[eid] = p; continue
        # Prefer result/DC over weaker-score/ah screens for the main masters; screens kept separately
        pri = {"bottom3-form-dc": 3, "top3-form-win": 2, "top3-form-dnb": 2, "o25-2of3": 1}.get
        if pri(p.get("strategy"), 0) > pri(cur.get("strategy"), 0): by[eid] = p
    return list(by.values())


def book_masters(pool, day):
    main = [p for p in pool if p.get("strategy") in ("o25-2of3", "top3-form-win", "top3-form-dnb", "bottom3-form-dc")]
    main = one_per_match(main)
    main = [p for p in main if p.get("kickoff") and p["kickoff"] > dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")]
    main.sort(key=lambda p: float(p["odds"]))
    asc = main[:50]; desc = list(reversed(main[-50:])) if main else []
    screens = [p for p in pool if p.get("strategy") in ("weaker-score", "ah-minus1-screen")]
    screens = [p for p in screens if p.get("kickoff") and p["kickoff"] > dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")]
    out = []
    def publish(name, key, legs, split=True):
        if not legs: return
        legs = sorted(legs, key=lambda p: p.get("kickoff") or "")
        if split and len(legs) > 25:
            a, b = legs[:25], legs[25:50]
            chunks = [("first 25", a), ("second 25", b), ("master", legs[:50])]
        else:
            chunks = [("set", legs)]
        rec = dict(key=key, name=name, date=day, riskLabel="HIGH RISK", waived=True,
                   verification="Bets For The Day three-strategy set. Strategy-internal rules only; HIGH RISK, no guarantees.",
                   parts=[], legList=legs[:50] if split else legs, legs=min(50, len(legs)) if split else len(legs),
                   totalOdds=round(math.prod(float(p["odds"]) for p in (legs[:50] if split else legs)), 2))
        for role, L in chunks:
            if not L: continue
            pt = SC.book_part(L, f"{name} · {role}")
            pt["label"] = f"{name} · {role} · HIGH RISK"; pt["source"] = key
            rec["parts"].append(pt)
            print(name, role, len(L), pt["totalOdds"], {b: L_[0]["code"] for b, L_ in pt["codes"].items()}, flush=True)
        path = ENGINE_DIR / "data" / "ho-masters" / f"{day}-{key}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        json.dump(rec, open(path, "w"), indent=1, ensure_ascii=False, default=str)
        out.append(path)
    publish("Ascending odds", "asc", asc, True)
    publish("Descending odds", "desc", desc, True)
    if screens:
        publish("Top5 v Bottom3 screens", "t5b3-screens", screens, False)
    return out


def main(days=1):
    day = dt.datetime.now(dt.timezone.utc).date().isoformat()
    pool = build_pool(days=days)
    print(f"pool {len(pool)} by strategy:", {k: sum(1 for p in pool if p.get("strategy") == k) for k in
          ("o25-2of3", "top3-form-win", "top3-form-dnb", "bottom3-form-dc", "weaker-score", "ah-minus1-screen")})
    paths = book_masters(pool, day)
    print("wrote", [str(p) for p in paths])
    return 0


if __name__ == "__main__":
    sys.exit(main(int(sys.argv[1]) if len(sys.argv) > 1 else 1))
