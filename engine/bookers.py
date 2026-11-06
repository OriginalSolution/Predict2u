"""No-login public booking APIs. Betway is omitted (it needs a logged-in account)."""
from __future__ import annotations
import json
import math
import subprocess

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36"
SPORTY_SHARE = "https://www.sportybet.com/api/gh/orders/share"
MSPORT_SHARE = "https://www.msport.com/api/gh/orders/real-sports/order/share"
BETIKA_SHARE = "https://api.betika.com.gh/v2/share/"
FOOTBALL_SHARE = "https://www.football.com/api/gh/orders/share"
NO_LOGIN = ("sportybet", "footballcom", "msport", "betika", "betpawa")


def _curl_json(method, url, body=None, headers=None, timeout=30):
    cmd = ["curl", "-s", "-m", str(timeout), "-A", UA, "-X", method, url]
    for h in headers or ["Content-Type: application/json", "Accept: application/json"]:
        cmd += ["-H", h]
    if body is not None:
        cmd += ["-d", json.dumps(body)]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True).stdout
        return json.loads(out) if out and out.strip()[:1] in "{[" else {}
    except Exception:
        return {}


def sportybet(legs):
    from sb_share_helper17 import book
    code, status = book(legs)
    if code and status == "ok":
        tot = round(math.prod(float(p.get("odds") or 1) for p in legs), 2)
        return {"code": code, "totalOdds": tot, "legs": len(legs), "matches": [p["eventId"] for p in legs]}
    return None


def msport(legs):
    def sel(p):
        return {"eventId": p["eventId"], "marketId": str(p.get("marketId") or ""), "specifier": p.get("specifier") or "", "outcomeId": str(p.get("outcomeId") or "")}
    ok = [p for p in legs if p.get("marketId") and p.get("outcomeId") and _curl_json("POST", MSPORT_SHARE, {"selections": [sel(p)]}, ["Content-Type: application/json", "operid: 3"]).get("bizCode") == 10000]
    if not ok:
        return None
    r = _curl_json("POST", MSPORT_SHARE, {"selections": [sel(p) for p in ok]}, ["Content-Type: application/json", "operid: 3"])
    if r.get("bizCode") != 10000:
        return None
    code = r["data"]["shareCode"]
    b = _curl_json("GET", MSPORT_SHARE + "/" + code, headers=["Content-Type: application/json", "operid: 3"])
    B = ((b.get("data") or {}).get("bettableBetSlip")) or []
    tot = round(math.prod(float(x["outcome"]["odds"]) for x in B), 2) if B else None
    return {"code": code, "totalOdds": tot, "legs": len(B) or len(ok), "matches": [p["eventId"] for p in ok]}


def betika(legs):
    L = [p for p in legs if p.get("marketId") and p.get("outcomeId")]
    if not L:
        return None
    def sel(p):
        return {"odd_key": "", "outcome_id": str(p.get("outcomeId") or ""), "special_bet_value": p.get("specifier") or "", "parent_match_id": p["eventId"].split(":")[-1], "sub_type_id": str(p.get("marketId") or ""), "has_parent": None, "parent_code": None}
    r = _curl_json("POST", BETIKA_SHARE + "encode", {"profile_id": 0, "bet_id": None, "token": None, "src": "MOBILE_WEB", "product_type": "PREMATCH", "betslip": [sel(p) for p in L]})
    code = r.get("code")
    if not code:
        return None
    dd = _curl_json("GET", BETIKA_SHARE + "decode?code=" + code + "&src=MOBILE_WEB").get("data") or []
    V = [x for x in dd if str(x.get("valid")) == "1"]
    if not V:
        return None
    tot = round(math.prod(float(x["odd_value"]) for x in V), 2)
    return {"code": code, "totalOdds": tot, "legs": len(V), "matches": sorted("sr:match:" + x["parent_match_id"] for x in V)}


def footballcom(legs):
    L = [p for p in legs if p.get("marketId") and p.get("outcomeId")]
    if not L:
        return None
    def sel(p):
        return {"eventId": p["eventId"], "marketId": str(p.get("marketId") or ""), "specifier": p.get("specifier") or None, "outcomeId": str(p.get("outcomeId") or "")}
    r = _curl_json("POST", FOOTBALL_SHARE, {"selections": [sel(p) for p in L]})
    if r.get("bizCode") != 10000:
        L = [p for p in L if _curl_json("POST", FOOTBALL_SHARE, {"selections": [sel(p)]}).get("bizCode") == 10000]
        if not L:
            return None
        r = _curl_json("POST", FOOTBALL_SHARE, {"selections": [sel(p) for p in L]})
        if r.get("bizCode") != 10000:
            return None
    code = r["data"]["shareCode"]
    tot = round(math.prod(float(p.get("odds") or 1) for p in L), 2)
    return {"code": code, "totalOdds": tot, "legs": len(L), "matches": [p["eventId"] for p in L]}


def betpawa(legs):
    try:
        import bp_book
        return bp_book.book(legs)
    except Exception:
        return None


BOOKERS = {
    "sportybet": sportybet,
    "footballcom": footballcom,
    "msport": msport,
    "betika": betika,
    "betpawa": betpawa,
}


def book_all(legs, skip=None):
    skip = set(skip or [])
    out = {}
    for name, fn in BOOKERS.items():
        if name in skip:
            continue
        try:
            out[name] = fn(list(legs))
        except Exception as e:
            out[name] = {"error": str(e)[:200]}
    return out
