"""SportyBet GH share-code helper for 2026-10-17 fixtures (sbcombo17.json).

Market ID cheat-sheet (SportyBet factsCenter / orders/share):
  1   = 1X2 (outcomes: Home / Draw / Away)
  10  = Double chance (Home or Draw / Home or Away / Draw or Away)
  11  = Draw no bet
  18  = Over/Under total goals (specifier total=X.5, outcomes Over X.5 / Under X.5)
  19  = Home team total goals O/U
  20  = Away team total goals O/U
  29  = BTTS / GG (Yes / No)
  35  = 1X2 & Over/Under combo
  36  = 1X2 & BTTS combo
  37  = Double chance & Over/Under combo
  546 = Double chance & BTTS
  547 / 548 = related combo markets
  854–865 = additional combo / special markets

Selection dict keys for book():
  eventId, marketId, specifier (str or None), outcomeId
"""
import json, subprocess

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36"
SHARE_URL = "https://www.sportybet.com/api/gh/orders/share"


def book(selections):
    """POST selections to SportyBet share API.

    selections: list of dicts with keys eventId, marketId, specifier, outcomeId.
    Returns (shareCode_or_None, status_str).
    """
    if not selections:
        return None, "empty"
    payload = {"selections": []}
    for s in selections:
        payload["selections"].append({
            "eventId": s["eventId"],
            "marketId": s["marketId"],
            "specifier": s.get("specifier") or None,
            "outcomeId": s["outcomeId"],
        })
    r = subprocess.run(
        [
            "curl", "-s", "-A", UA,
            "-H", "Content-Type: application/json",
            "-H", "Accept: application/json",
            "-X", "POST", SHARE_URL,
            "-d", json.dumps(payload),
        ],
        capture_output=True, text=True,
    )
    try:
        j = json.loads(r.stdout)
    except Exception:
        return None, (r.stdout or r.stderr or "")[:200]
    if j.get("bizCode") != 10000:
        return None, j.get("message") or str(j)[:200]
    data = j.get("data") or {}
    bad = [x for x in data.get("outcomes", []) if x.get("matchStatus") != "Not start"]
    status = f"{len(bad)} not open" if bad else "ok"
    return data.get("shareCode"), status
