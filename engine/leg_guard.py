"""Final leg check run on every SportyBet booking (HANDOFF 5.10).

Hard rule from Riddim Boss (22 Nov 2026): "always switch to u3.5 when over 1.5 is greater than 1.39
and vice versa".
  - match Over 1.5 priced above the cap (1.39)  -> match Under 3.5 on the same match
  - match Under 3.5 priced above the cap        -> match Over 1.5 on the same match
  - the swap happens only when SportyBet lists the replacement at or under the cap; otherwise the
    leg is dropped (never booked at a breaking price). A swapped leg is never swapped back.
It runs last, after every strategy's own market logic (the master pipeline's U4.5 -> O2.5/O1.5 too).
Works on leg dicts and on bare selections (eventId, marketId, specifier, outcomeId): dicts are
changed in place and dropped items are removed from the list in place, so callers see the result.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

CFG_PATH = Path(__file__).with_name("leg_rules.json")
EVENT_URL = "https://www.sportybet.com/api/gh/factsCenter/event?eventId={eid}&productId=3"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36"
O15 = ("18", "total=1.5", "12", "Over 1.5")
U35 = ("18", "total=3.5", "13", "Under 3.5")
LABEL_KEYS = ("selection", "market", "pick", "label", "tip", "bet")
LOG: list[dict] = []          # every swap / drop this process made (dry-run reports read it)
_PRICES: dict[str, dict] = {}  # eventId -> {"o15": (price, id) | None, "u35": ...}


def config() -> dict:
    try:
        cfg = json.loads(CFG_PATH.read_text())
    except Exception:
        cfg = {}
    return {"enabled": bool(cfg.get("o15_u35_enabled", True)), "cap": float(cfg.get("o15_u35_cap", 1.39))}


def kind(item: dict) -> str | None:
    """'o15' / 'u35' for a full-match Over 1.5 / Under 3.5 leg, else None."""
    if str(item.get("marketId")) != "18":
        return None
    spec, oid = str(item.get("specifier") or ""), str(item.get("outcomeId") or "")
    if spec == O15[1] and oid == O15[2]:
        return "o15"
    if spec == U35[1] and oid == U35[2]:
        return "u35"
    return None


def fetch_prices(eid: str) -> dict:
    """SportyBet's live Over 1.5 / Under 3.5 prices for one event ({} when the event can't be read)."""
    if eid in _PRICES:
        return _PRICES[eid]
    if os.environ.get("P2U_LEG_GUARD_TRAP"):
        raise RuntimeError("leg_guard network fetch during tests: " + eid)
    out: dict = {}
    try:
        raw = subprocess.run(["curl", "-s", "-m", "20", "-A", UA, EVENT_URL.format(eid=eid)],
                             capture_output=True, text=True, timeout=35).stdout
        data = (json.loads(raw) or {}).get("data") or {}
        out = {"o15": None, "u35": None}
        for m in data.get("markets") or []:
            if str(m.get("id")) != "18":
                continue
            for o in m.get("outcomes") or []:
                key = (str(m.get("specifier") or ""), str(o.get("id")))
                name = "o15" if key == (O15[1], O15[2]) else "u35" if key == (U35[1], U35[2]) else None
                if not name or o.get("isActive") == 0:
                    continue
                try:
                    price = float(o.get("odds") or 0)
                except Exception:
                    continue
                if price > 1:
                    out[name] = (price, str(o.get("id")))
    except Exception:
        out = {}
    _PRICES[eid] = out
    return out


def _relabel(item: dict, old: str, new: str) -> None:
    for k in LABEL_KEYS:
        v = item.get(k)
        if isinstance(v, str) and old in v:
            item[k] = v.replace(old, new)


def _log(row: dict) -> None:
    LOG.append(row)
    print("leg-guard: " + json.dumps(row, ensure_ascii=False), file=sys.stderr)


def enforce(items: list, where: str = "", fetch=None) -> list:
    """Apply the Over 1.5 <-> Under 3.5 rule to `items` in place; returns the same list."""
    cfg = config()
    if not cfg["enabled"] or not items:
        return items
    cap, fetch = cfg["cap"], fetch or fetch_prices
    kept = []
    for item in items:
        k = kind(item) if isinstance(item, dict) else None
        if not k or item.get("ruleSwap"):
            kept.append(item)
            continue
        own_spec, alt = (O15, U35) if k == "o15" else (U35, O15)
        try:
            own_price = float(item.get("odds") or 0) or None
        except Exception:
            own_price = None
        if own_price is not None and own_price <= cap:
            kept.append(item)  # priced inside the cap when the strategy picked it
            continue
        prices = fetch(str(item.get("eventId"))) or {}
        if own_price is None:
            live = prices.get(k)
            if live is None:
                kept.append(item)  # cannot price it at all: the strategy's own checks stand
                continue
            own_price = live[0]
            if own_price <= cap:
                kept.append(item)
                continue
        alt_name = "u35" if k == "o15" else "o15"
        alt_live = prices.get(alt_name)
        row = {"where": where, "eventId": item.get("eventId"), "match": item.get("match"),
               "from": own_spec[3], "fromOdds": own_price, "cap": cap}
        if alt_live and alt_live[0] <= cap:
            item.update(specifier=alt[1], outcomeId=alt_live[1],
                        ruleSwap=f"{own_spec[3]} {own_price:g} > {cap:g} -> {alt[3]} {alt_live[0]:g}")
            if "odds" in item:
                item["odds"] = alt_live[0]
            _relabel(item, own_spec[3], alt[3])
            kept.append(item)
            _log({**row, "action": "swap", "to": alt[3], "toOdds": alt_live[0]})
        else:
            _log({**row, "action": "drop", "to": alt[3], "toOdds": alt_live[0] if alt_live else None,
                  "why": "replacement not listed" if not alt_live else "replacement above cap"})
    items[:] = kept
    return items
