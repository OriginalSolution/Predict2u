#!/usr/bin/env python3
"""Builds staked-codes.json: every code shown on the site, with per-leg live score and WON/LOST/PENDING."""
import json, os, re, sys, subprocess, concurrent.futures as cf, datetime as dt
REPO = sys.argv[1] if len(sys.argv) > 1 else '/workspace/Predict2u'
F = os.environ.get('NEWS_STATE_DIR') or '/workspace/predict2u-feed'
os.makedirs(F, exist_ok=True)
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36'
def get(u):
    r = subprocess.run(['curl', '-s', '-m', '20', '-A', UA, '-H', 'Accept: application/json', u], capture_output=True, text=True)
    return json.loads(r.stdout)
try: led = json.load(open(f'{F}/code-ledger.json'))
except Exception: led = {}
now = dt.datetime.now(dt.timezone.utc)
cut = (now - dt.timedelta(days=4)).date().isoformat()
codes = {k: dict(code=v['code'], book=v['book'], name=v.get('name'), odds=v.get('odds'), date=v.get('date'),
                 legs=[dict(eventId=l.get('eventId'), match=l['match'], selection=l['selection'], odds=l.get('odds'), result=l.get('result')) for l in v['legs']])
         for k, v in led.items() if (v.get('date') or '') >= cut}
def side(desc, H, A):
    return re.sub(r'\bHome\b', H, re.sub(r'\bAway\b', A, desc))
def share(book, code):
    host = 'www.football.com' if book == 'footballcom' else 'www.sportybet.com'
    try: d = get(f'https://{host}/api/gh/orders/share/{code}')['data']
    except Exception: return None
    legs = []
    for o in d.get('outcomes') or []:
        m = o['markets'][0]; oc = m['outcomes'][0]; H, A = o['homeTeamName'], o['awayTeamName']
        sel = side(oc['desc'], H, A)
        legs.append(dict(eventId=o['eventId'], match=f'{H} v {A}', selection=sel, market=m.get('desc'), odds=float(oc.get('odds') or 0) or None,
                         kickoff=o.get('estimateStartTime'), score=o.get('setScore'), status=o.get('matchStatus'), league=o['sport']['category']['tournament']['name']))
    return legs
try: hot = json.load(open(f'{REPO}/hot-picks.json'))
except Exception: hot = {}
for s in (hot.get('slips') or []) + (hot.get('byMarket') or []):
    for bk, arr in (s.get('codes') or {}).items():
        for i, c in enumerate(arr if isinstance(arr, list) else [arr]):
            if isinstance(c, dict) and c.get('code'):
                k = f"{bk}:{c['code']}"
                codes.setdefault(k, dict(code=c['code'], book=bk, name=s['name'] + (f' (part {i+1})' if len(arr) > 1 else ''), odds=c.get('totalOdds'), date=now.date().isoformat(), legs=[], sib=f"sportybet:{(s['codes'].get('sportybet') or [{}])[min(i, len(s['codes'].get('sportybet') or [1])-1)].get('code')}"))
# Fetch SportyBet/football.com shares (rich legs) for every code of those books
sh = [k for k, v in codes.items() if v['book'] in ('sportybet', 'footballcom')]
with cf.ThreadPoolExecutor(8) as ex:
    for k, legs in zip(sh, ex.map(lambda k: share(codes[k]['book'], codes[k]['code']), sh)):
        if legs: codes[k]['legs'] = legs
for k, v in codes.items():
    if not v['legs'] and v.get('sib') in codes: v['legs'] = [dict(l) for l in codes[v['sib']]['legs']]
    v.pop('sib', None)
# Event status/score for every leg not already final
try: evc = json.load(open(f'{F}/event-cache.json'))
except Exception: evc = {}
need = {l['eventId'] for v in codes.values() for l in v['legs'] if l.get('eventId') and not (evc.get(l['eventId']) or {}).get('final')}
def fetch(eid):
    try:
        d = get(f'https://www.sportybet.com/api/gh/factsCenter/event?eventId={eid}&productId=3')['data']
        return eid, dict(final=d.get('matchStatus') == 'Ended' and bool(d.get('setScore')), score=d.get('setScore'), status=d.get('matchStatus'), kickoff=d.get('estimateStartTime'), played=d.get('playedSeconds'), home=d.get('homeTeamName'), away=d.get('awayTeamName'))
    except Exception: return eid, None
with cf.ThreadPoolExecutor(10) as ex:
    for eid, v in ex.map(fetch, list(need)):
        if v: evc[eid] = v
json.dump(evc, open(f'{F}/event-cache.json', 'w'))
def settle(l, ev):
    r = (l.get('result') or 'pending').lower()
    if r in ('won', 'lost', 'void'): return r
    if not ev or not ev.get('final'): return 'pending'
    h, a = map(int, ev['score'].split(':')); s = l['selection'].strip(); tot = h + a
    m = re.match(r'(Over|Under) (\d+(?:\.\d+)?)$', s)
    if m: return 'won' if (tot > float(m[2])) == (m[1] == 'Over') else 'lost'
    H, A = (l['match'].split(' v ') + [''])[:2]
    out = {'1': h > a, 'X': h == a, '2': a > h}
    tok = lambda x: '1' if x.strip() == H.strip() else '2' if x.strip() == A.strip() else 'X' if x.strip().lower() == 'draw' else None
    ps = [tok(x) for x in s.split(' or ')]
    if all(ps): return 'won' if any(out[p] for p in ps) else 'lost'
    if s.lower() in ('gg', 'yes', 'both teams to score'): return 'won' if h and a else 'lost'
    if s.lower() in ('ng', 'no'): return 'won' if not (h and a) else 'lost'
    return 'pending'
for v in codes.values():
    for l in v['legs']:
        ev = evc.get(l.get('eventId') or '') or {}
        for f in ('score', 'status', 'kickoff', 'played'):
            if ev.get(f) is not None: l[f] = ev[f]
        l['result'] = settle(l, ev)
    rs = [l['result'] for l in v['legs']]
    v['status'] = 'pending' if not rs else 'lost' if 'lost' in rs else 'won' if all(r in ('won', 'void') for r in rs) else 'pending'
    v['hit'] = rs.count('won'); v['live'] = any(l.get('status') not in (None, 'Not start', 'Ended') for l in v['legs'])
out = dict(updatedAt=now.isoformat(timespec='seconds'), codes=codes)
json.dump(out, open(f'{REPO}/staked-codes.json', 'w'), ensure_ascii=False, separators=(',', ':'))
print(len(codes), 'codes', sum(1 for v in codes.values() if v['legs']), 'with legs')
ix = {}
for k in codes: b, c = k.split(':', 1); ix.setdefault(c, []).append(b)
json.dump(ix, open(f'{REPO}/staked-index.json', 'w'), separators=(',', ':'))
json.dump({k: v['status'] for k, v in codes.items()}, open(f'{REPO}/staked-status.json', 'w'), separators=(',', ':'))
