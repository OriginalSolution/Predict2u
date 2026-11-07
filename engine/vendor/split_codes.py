#!/usr/bin/env python3
"""ENGINE RULE: any code with more than 50 legs is auto-split into balanced parts of <= 50 legs
(e.g. 77 -> 39 + 38), each part booked on SportyBet, Football.com, MSport, Betika and BetPawa
(Betway needs login, never booked). Legs already kicked off are left out before booking; legs a
bookmaker does not offer are reported per part/bookmaker. Parts are settled from the parent legs.

    python3 engine/vendor/split_codes.py REPO     # splits >50-leg slips in high_odds.json (+ daily masters)
"""
import json, math, os, sys, datetime as dt
MAX_LEGS = 50
BOOKS = ('sportybet', 'footballcom', 'msport', 'betika', 'betpawa')
LINK = {'sportybet': 'https://www.sportybet.com/gh/?shareCode={}', 'footballcom': 'https://www.football.com/gh/?shareCode={}',
        'msport': 'https://www.msport.com/gh/?shareCode={}', 'betika': 'https://betika.com/en-gh/share/{}',
        'betpawa': 'https://www.betpawa.com.gh/share-betslip/{}'}
HERE = os.path.dirname(os.path.abspath(__file__))


def split(legs, max_legs=MAX_LEGS):
    L = sorted(legs, key=lambda p: p.get('kickoff') or '')
    if len(L) <= max_legs: return [L]
    n = -(-len(L) // max_legs)
    size = [len(L) // n + (1 if i < len(L) % n else 0) for i in range(n)]
    out, i = [], 0
    for s in size: out.append(L[i:i + s]); i += s  # contiguous by kickoff: part 1 = earlier games
    return out


def started(p, now):
    st = p.get('matchStatus')
    if st and st not in ('Not start',): return True
    try: return dt.datetime.fromisoformat(p['kickoff'].replace('Z', '+00:00')) <= now
    except Exception: return False


def _bookers():
    sys.path.insert(0, os.path.dirname(HERE)); sys.path.insert(0, os.path.dirname(os.path.dirname(HERE)))
    from engine import bookers
    return bookers


def book_part(legs, name):
    B = _bookers(); codes, missing = {}, {}
    for b in BOOKS:
        try: r = B.BOOKERS[b]([dict(p) for p in legs])
        except Exception: r = None
        if not r or not r.get('code'): missing[b] = 'not booked'; continue
        got = set(r.get('matches') or [])
        miss = [p['match'] for p in legs if got and p['eventId'] not in got]
        n = r.get('legs') or len(legs)
        if not got and n < len(legs): miss = [f'{len(legs) - n} leg(s)']
        codes[b] = [dict(code=r['code'], totalOdds=r.get('totalOdds'), legs=n, link=LINK[b].format(r['code']), matches=sorted(got) if got else None)]
        if miss: missing[b] = miss
    return dict(name=name, legs=len(legs), events=[p['eventId'] for p in legs], totalOdds=round(math.prod(float(p['odds']) for p in legs), 2),
                codes=codes, missing=missing)


def settle_parts(parent_legs, parts):
    res = {p['eventId']: (p.get('result') or 'pending').lower() for p in parent_legs}
    for pt in parts:
        for b, L in (pt.get('codes') or {}).items():
            for c in L:
                ev = c.get('matches') or pt['events']
                r = [res.get(e, 'pending') for e in ev]
                c['hit'] = r.count('won'); c['status'] = 'lost' if 'lost' in r else 'won' if r and all(x in ('won', 'void') for x in r) else 'pending'
        r = [res.get(e, 'pending') for e in pt['events']]
        pt['status'] = 'lost' if 'lost' in r else 'won' if r and all(x in ('won', 'void') for x in r) else 'pending'
    return parts


def ensure_parts(rec, legs_key='legList', base_name=None, now=None):
    """Book parts once per leg set; settle every call. rec gets parts, partsDropped (kicked off)."""
    now = now or dt.datetime.now(dt.timezone.utc)
    legs = rec.get(legs_key) or []
    if len(legs) <= MAX_LEGS:
        if rec.get('parts'): settle_parts(legs, rec['parts'])
        return rec
    if not rec.get('parts'):
        live = [p for p in legs if not started(p, now)]
        rec['partsDropped'] = [dict(match=p['match'], reason='already kicked off') for p in legs if started(p, now)]
        chunks = split(live)
        nm = base_name or rec.get('name') or rec.get('code')
        rec['parts'] = [book_part(c, f"{nm} · part {i + 1}/{len(chunks)}") for i, c in enumerate(chunks)]
        rec['partsBookedAt'] = now.isoformat(timespec='seconds').replace('+00:00', 'Z')
    settle_parts(legs, rec['parts'])
    return rec


def main(repo):
    p = os.path.join(repo, 'high_odds.json')
    try: ho = json.load(open(p))
    except Exception: return
    ch = False
    for s in (ho.get('slips') or []):
        if len(s.get('legs') or []) > MAX_LEGS and s.get('status', 'pending') == 'pending':
            ensure_parts(s, 'legs', base_name=s.get('name')); ch = True
    if ch: json.dump(ho, open(p, 'w'), ensure_ascii=False, separators=(',', ':'))


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else '/workspace/Predict2u')
