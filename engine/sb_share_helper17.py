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
import json, subprocess, time

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
    cmd = [
        "curl", "-s", "-m", "40", "-A", UA,
        "-H", "Content-Type: application/json",
        "-H", "Accept: application/json",
        "-X", "POST", SHARE_URL,
        "-d", json.dumps(payload),
    ]
    j, last = None, ""
    # A timeout / reset / HTML error page is retried; a JSON refusal is final.
    for attempt in range(3):
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            last = (r.stdout or r.stderr or "")[:200]
            j = json.loads(r.stdout)
            break
        except Exception as e:
            last = last or str(e)[:200]
            j = None
            if attempt < 2:
                time.sleep(3 * (attempt + 1))
    if not isinstance(j, dict):
        return None, last
    if j.get("bizCode") != 10000:
        return None, j.get("message") or str(j)[:200]
    data = j.get("data") or {}
    def _pending(st):
        s = str(st or "").strip().lower()
        return s in {"not start", "0", ""}
    bad = [x for x in data.get("outcomes", []) if not _pending(x.get("matchStatus"))]
    status = f"{len(bad)} not open" if bad else "ok"
    return data.get("shareCode"), status
