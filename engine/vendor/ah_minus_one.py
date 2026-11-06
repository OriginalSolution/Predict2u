#!/usr/bin/env python3
"""AH −1 strategy: scan SportyBet and write legal alternative markets to the inbox.

Band: Asian Handicap −1 priced 1.20–1.90 (a nearby 1X2 win is often 1.15–1.55).
Mapping (from the saved AH −1 picker):
  AH < 1.50  -> Over 2.5, else team Over 2.5 (3+), else Over 3.5
  AH 1.50–1.90 -> team Over 1.5 (2+), else to-win if matchup_rules allows
Women, youth and reserve sides are skipped. DC and NG are never selected.
"""
from __future__ import annotations
import datetime as dt
import json
import os
import re
import subprocess
import sys
from pathlib import Path

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36"
AH_LO, AH_HI = 1.20, 1.90
DEEP = 1.50
SKIP_RE = re.compile(
    r"\b(U1[89]|U2[01]|U23|Reserve|Reserves|\bII\b|Youth|Women|Ladies|Womens|"
    r"Women's|SRL|Simulated|eSoccer|Esoccer|Esports|Friendly|Femin)\b",
    re.I,
)

sys.path.insert(0, str(Path(__file__).resolve().parent))
import matchup_rules as mr  # noqa: E402


def curl_json(url, timeout=25):
    raw = subprocess.run(
        ["curl", "-s", "-m", str(timeout), "-A", UA, "-H", "Accept: application/json", url],
        capture_output=True, text=True,
    ).stdout
    try:
        return json.loads(raw) if raw and raw.strip()[:1] in "{[" else {}
    except Exception:
        return {}


def choose_targets(ah_odds: float, side: str) -> list[tuple[str, str, str, str]]:
    """Preferred (marketId, specifier, outcomeId-or-desc, label) in order."""
    team_mid = "19" if side == "H" else "20"
    win_oid = "1" if side == "H" else "3"
    win_desc = "Home" if side == "H" else "Away"
    if ah_odds < DEEP:
        return [
            ("18", "total=2.5", "12", "Over 2.5"),
            (team_mid, "total=2.5", "12", "Over 2.5"),
            ("18", "total=3.5", "12", "Over 3.5"),
        ]
    return [
        (team_mid, "total=1.5", "12", "Over 1.5"),
        ("1", "", win_oid, win_desc),
    ]


def _outcome(markets, mid, spec, oid=None, desc=None):
    for m in markets or []:
        if str(m.get("id")) != str(mid):
            continue
        if (m.get("specifier") or "") != (spec or ""):
            continue
        for o in m.get("outcomes") or []:
            if oid and str(o.get("id")) != str(oid):
                continue
            if desc and (o.get("desc") or "") not in {desc, "Over", "Under", desc}:
                if desc not in {o.get("desc"), o.get("desc") and o.get("desc").split()[0]}:
                    # allow "Over 2.5" vs desc "Over"
                    if not (desc.startswith("Over") and (o.get("desc") or "").startswith("Over")) and not (
                        desc.startswith("Under") and (o.get("desc") or "").startswith("Under")
                    ):
                        if str(o.get("id")) != str(oid or ""):
                            continue
            return m, o
    return None


def find_ah(markets):
    """Return (side, ah_odds, outcome) for Home hcp=-1 or Away hcp=1."""
    found = []
    for m in markets or []:
        if str(m.get("id")) != "16":
            continue
        spec = m.get("specifier") or ""
        for o in m.get("outcomes") or []:
            desc = (o.get("desc") or "").lower()
            try:
                odds = float(o.get("odds") or 0)
            except Exception:
                continue
            if spec == "hcp=-1" and desc.startswith("home") and AH_LO <= odds <= AH_HI:
                found.append(("H", odds, o, spec))
            if spec == "hcp=1" and desc.startswith("away") and AH_LO <= odds <= AH_HI:
                found.append(("A", odds, o, spec))
    if not found:
        return None
    found.sort(key=lambda x: x[1])
    return found[0]


def pick_from_event(data: dict) -> dict | None:
    home = data.get("homeTeamName") or ""
    away = data.get("awayTeamName") or ""
    league = ""
    try:
        league = data["sport"]["category"]["tournament"]["name"]
    except Exception:
        league = data.get("tournamentName") or data.get("league") or ""
    blob = f"{home} {away} {league}"
    if SKIP_RE.search(blob):
        return None
    ah = find_ah(data.get("markets") or [])
    if not ah:
        return None
    side, ah_odds, _o, _spec = ah
    base = dict(
        eventId=data.get("eventId"),
        match=f"{home} v {away}",
        league=league,
        market="",
        selection="",
        odds=0,
        marketId="",
        specifier="",
        outcomeId="",
        case=f"AH -1 @{ah_odds} side={side}",
        table="",
        x12="",
        source="ah-minus-one",
    )
    # attach 1X2 if present so classify() works
    hit12 = _outcome(data.get("markets") or [], "1", "", oid="1")
    hitx = _outcome(data.get("markets") or [], "1", "", oid="2")
    hita = _outcome(data.get("markets") or [], "1", "", oid="3")
    if hit12 and hitx and hita:
        try:
            base["x12"] = f"{float(hit12[1]['odds']):.2f}/{float(hitx[1]['odds']):.2f}/{float(hita[1]['odds']):.2f}"
            base["case"] += f"; 1X2 {base['x12']}"
        except Exception:
            pass
    for mid, spec, oid, label in choose_targets(ah_odds, side):
        hit = _outcome(data.get("markets") or [], mid, spec, oid=oid, desc=label)
        if not hit:
            continue
        _m, o = hit
        try:
            odds = float(o.get("odds") or 0)
        except Exception:
            continue
        p = dict(base)
        p.update(
            marketId=str(mid),
            specifier=spec,
            outcomeId=str(o.get("id") or oid),
            market=_m.get("name") or _m.get("desc") or label,
            selection=o.get("desc") or label,
            odds=odds,
            ahOdds=ah_odds,
            ahSide=side,
        )
        if mr.is_double_chance(p) or mr.is_btts_no(p):
            continue
        if float(p.get("odds") or 0) > mr.MAX_LEG:
            continue
        ok, cls, why = mr.check(p)
        if ok:
            p["gate"] = cls
            p["gateWhy"] = why
            return p
        # No standings on the SportyBet event payload: apply the same class
        # rules from 1X2 prices so a short favourite is treated as a mismatch
        # (no straight win) instead of being dropped as unverified.
        if cls == "unverified" and p.get("x12"):
            try:
                h, d, a = (float(x) for x in p["x12"].split("/"))
            except Exception:
                continue
            fp = min(h, a)
            mid = str(p.get("marketId") or "")
            spec = p.get("specifier") or ""
            oid = str(p.get("outcomeId") or "")
            if fp <= 1.70 and mid not in ("1", "33", "34"):
                p["gate"] = "mismatch"
                p["gateWhy"] = f"no table; short fav @{fp} treated as mismatch"
                return p
            if fp > 1.80 and not (mid == "18" and spec in ("total=1.5", "total=2.5") and oid == "12"):
                p["gate"] = "even"
                p["gateWhy"] = f"no table; even fav @{fp}"
                return p
    return None


def upcoming_ids(days=2):
    ids = []
    cutoff = dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=days)
    now = dt.datetime.now(dt.timezone.utc)
    for page in range(1, 8):
        d = curl_json(
            "https://www.sportybet.com/api/gh/factsCenter/pcUpcomingEvents"
            f"?sportId=sr%3Asport%3A1&marketId=1%2C16%2C18%2C19%2C20&pageSize=100&pageNum={page}&option=1"
        ).get("data") or {}
        n = 0
        for t in d.get("tournaments") or []:
            for e in t.get("events") or []:
                n += 1
                ts = e.get("estimateStartTime") or 0
                ko = dt.datetime.fromtimestamp(ts / 1000, dt.timezone.utc) if ts else now
                if now <= ko <= cutoff:
                    ids.append(e.get("eventId"))
        if not n or page * 100 >= int(d.get("totalNum") or 0):
            break
    return ids


def fetch_event(eid: str) -> dict:
    url = f"https://www.sportybet.com/api/gh/factsCenter/event?eventId={eid}&productId=3"
    return curl_json(url).get("data") or {}


def main(argv=None):
    inbox = Path(os.environ.get("INBOX_DIR") or Path(__file__).resolve().parents[1] / "inbox")
    inbox.mkdir(parents=True, exist_ok=True)
    out = inbox / "ah-minus-one.json"
    ids = upcoming_ids(2)
    picks = []
    for eid in ids:
        data = fetch_event(eid)
        if not data:
            continue
        data.setdefault("eventId", eid)
        p = pick_from_event(data)
        if p:
            picks.append(p)
    doc = {"source": "ah-minus-one", "generated": dt.datetime.now(dt.timezone.utc).isoformat(), "picks": picks}
    out.write_text(json.dumps(doc, indent=1, ensure_ascii=False))
    print(f"ah-minus-one: scanned {len(ids)} events, kept {len(picks)} -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
