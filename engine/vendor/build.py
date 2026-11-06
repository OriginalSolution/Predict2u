#!/usr/bin/env python3
"""Merge pick exports into Predict2u/picks.json + picks-history.json (public, source-neutral).
Sources are read-only. Which source produced which slip is logged ONLY on the box:
/workspace/predict2u-feed/private/source-map-YYYY-MM-DD.json (never written to the repo).

PREDICT2U GRADING
  Pick score (0..1):
    p_imp = 1 / odds  (bookmaker implied probability; clamped to 0.05..0.97; no odds -> 0.5)
    if the source gave a confidence c:  score = 0.6 * c + 0.4 * p_imp
    else (confidence null):             score = 0.95 * p_imp   (small haircut for missing model view)
  Slip:
    combined = product of leg scores            (estimated chance the whole slip lands)
    avg      = mean leg score
    edge     = combined * total_odds            (>1 means the scores beat the price)
    rating   = 0.6 * combined + 0.25 * avg + 0.15 * min(edge, 1.5) / 1.5
    grade    = A if rating >= 0.55, B if rating >= 0.35, else C
  Only slips with total odds >= MIN_TOTAL_ODDS are kept.
  Slips are sorted by grade (A first), then rating, and labelled "Slip 1", "Slip 2", ... per day.
Bookmaker codes: sportybet from the source `code`; optional `msport` / `onexbet` (or `1xbet`)
fields on a source slip are passed through. Empty bookmakers are omitted.
"""
import json, os, sys, datetime as dt
SRC = (__import__('os').environ.get('INBOX_PARENT', (__import__('os').environ.get('ENGINE_DIR','')+'/inbox') if __import__('os').environ.get('ENGINE_DIR') else '/workspace/picks_export'))
SOURCES = []  # free lists are house strategy only (predict2u-research); never tipster/bot exports
MIN_TOTAL_ODDS = 25  # only slips whose total odds are >= this are published (site, emails, Telegram)
PRIV = os.environ.get('PRIV_DIR', os.path.join(os.environ.get('FEED_DIR', os.environ.get('ENGINE_DIR','/tmp')), 'private'))
REPO = sys.argv[1] if len(sys.argv) > 1 else (__import__('os').environ.get('REPO_DIR','/workspace/Predict2u'))
today = dt.datetime.now(dt.timezone.utc).date()
days = [(today + dt.timedelta(d)).isoformat() for d in range(0, 4)]  # today + upcoming only (Accra/UTC)
BOOK_LINKS = {'betika': 'https://betika.com/en-gh/share/{}', 'footballcom': 'https://www.football.com/gh/?shareCode={}', 'betpawa': 'https://www.betpawa.com.gh/share-betslip/{}', 'sportybet': 'https://www.sportybet.com/gh/?shareCode={}',
              'msport': 'https://www.msport.com/gh/?shareCode={}',
              'onexbet': 'https://1xbet.com/en/?coupon={}', 'betway': 'https://www.betway.com.gh/sport/soccer?bookingCode={}'}

def ko_iso(date, ko):
    ko = str(ko or '').strip()
    if 'T' in ko: return ko if ko.endswith('Z') or '+' in ko else ko + 'Z'
    if ':' in ko: return f"{date}T{ko[:5]}:00Z"
    return None

def score(odds, conf):
    try: p = min(0.97, max(0.05, 1.0 / float(odds)))
    except Exception: p = 0.5
    return round(0.6 * conf + 0.4 * p, 3) if isinstance(conf, (int, float)) else round(0.95 * p, 3)

slips, seen, private = [], {}, {}
for key in SOURCES:
    for day in days:
        f = f"{SRC}/{key}/{day}.json"
        if not os.path.exists(f): continue
        try: d = json.load(open(f))
        except Exception as e: print('skip', f, e, file=sys.stderr); continue
        for s in d.get('slips', []):
            code = str(s.get('code') or '').strip().upper()
            codes = {'sportybet': code} if code else {}
            for k, alias in (('msport', 'msport'), ('onexbet', 'onexbet'), ('onexbet', '1xbet')):
                v = str(s.get(alias) or '').strip()
                if v: codes[k] = v.upper()
            legs, lk = [], set()
            for l in s.get('legs', []):
                k = (l.get('match'), l.get('market'), l.get('selection'))
                if k in lk: continue
                lk.add(k)
                c = l.get('confidence'); c = c if isinstance(c, (int, float)) else None
                legs.append({'date': l.get('date') or day, 'kickoff': ko_iso(l.get('date') or day, l.get('ko')),
                    'league': l.get('league'), 'match': l.get('match'), 'market': l.get('market'),
                    'selection': l.get('selection'), 'odds': l.get('odds'),
                    'score': score(l.get('odds'), c), 'result': (l.get('result') or 'pending').lower()})
            if not legs: continue
            sig = code or json.dumps(legs, sort_keys=True)
            private[sig] = {'source': key, 'build': s.get('build')}
            if sig in seen:
                prev = seen[sig]; have = {(x['match'], x['market'], x['selection']): i for i, x in enumerate(prev['legs'])}
                for x in legs:
                    k = (x['match'], x['market'], x['selection'])
                    if k in have:
                        if prev['legs'][have[k]]['result'] == 'pending': prev['legs'][have[k]] = x
                    else: prev['legs'].append(x)
                continue
            sl = {'codes': codes, 'legs': legs}
            slips.append(sl); seen[sig] = sl

# Research (house strategy) slips -> also shown on the bankers board, with per-book codes/odds/notes
import glob as _glob
_RDIR=os.environ.get('RESEARCH_DIR','/workspace/predict2u-research')
_rfiles = sorted(f for f in _glob.glob(_RDIR+'/????-??-??.json') if os.path.basename(f)[:10] <= today.isoformat())
_rf = _rfiles[-1] if _rfiles else f"{_RDIR}/{today.isoformat()}.json"
if os.path.exists(_rf):
    try:
        _rd = json.load(open(_rf)); _conf = {p.get('eventId'): p.get('confidence') for p in _rd.get('picks') or []}
        sys.path.insert(0, (__import__('os').environ.get('RESEARCH_DIR','/workspace/predict2u-research')))
        import matchup_rules as _mr
        for s in _rd.get('slips') or []:
            if any(_mr.is_double_chance(l) for l in s.get('legs') or []): continue
            if s.get('earlier') or str(s.get('name') or '').lower().startswith('earlier code'): continue
            codes = {k: (str(v).strip() if k == 'betika' else str(v).strip().upper()) for k, v in (s.get('codes') or {}).items() if v}
            if not codes or codes.get('sportybet') in seen: continue
            legs = []
            for l in s.get('legs') or []:
                c = _conf.get(l.get('eventId')); c = c if isinstance(c, (int, float)) else None
                legs.append({'date': l.get('date'), 'kickoff': ko_iso(l.get('date'), l.get('ko')), 'league': l.get('league'),
                    'match': l.get('match'), 'market': l.get('market'), 'selection': l.get('selection'), 'odds': l.get('odds'),
                    'score': score(l.get('odds'), c), 'result': (l.get('result') or 'pending').lower()})
            if not legs: continue
            sl = {'codes': codes, 'legs': legs, 'house': True}
            for k in ('bookOdds', 'bookPicks', 'bookNotes', 'risk', 'name', 'banker', 'strategy'):
                if s.get(k) is not None: sl[k] = s[k]
            slips.append(sl); seen[codes.get('sportybet') or id(sl)] = sl
    except Exception as e: print('research slips skipped', e, file=sys.stderr)
    # risk dates fix: Safe/Medium should appear on the research day even if some legs are dated earlier
    _rday = os.path.basename(_rf)[:10]
    for _sl in slips:
      if _sl.get('risk') in ('safe','medium'):
        _sl.setdefault('dates', [])
        if _rday not in _sl['dates']: _sl['dates'].append(_rday)
        _sl['dates']=sorted(set(_sl['dates']))
        _sl['date']=_sl['dates'][0]

_rday = os.path.basename(_rf)[:10] if '_rf' in dir() and _rf else today.isoformat()
for sl in slips:
    L = sl['legs']; L.sort(key=lambda x: x['kickoff'] or '')
    sl['dates'] = sorted({x['date'] for x in L}); sl['date'] = sl['dates'][0]; sl['firstKickoff'] = L[0]['kickoff']
    # Keep Safe/Medium visible on the research card day (legs may all be tomorrow)
    if sl.get('risk') in ('safe','medium'):
        sl['dates'] = sorted(set(sl.get('dates') or []) | {_rday, today.isoformat()})
        sl['date'] = min(sl['dates'])
    tot = comb = 1.0
    for x in L: tot *= float(x['odds'] or 1); comb *= x['score']
    avg = sum(x['score'] for x in L) / len(L)
    edge = comb * tot
    rating = 0.6 * comb + 0.25 * avg + 0.15 * min(edge, 1.5) / 1.5
    sl.update(totalOdds=round(tot, 2), combined=round(comb, 4), rating=round(rating, 3),
              grade='A' if rating >= 0.55 else 'B' if rating >= 0.35 else 'C', picks=len(L))
    sl['links'] = {b: BOOK_LINKS[b].format(c) for b, c in sl['codes'].items() if b in BOOK_LINKS}
slips = [sl for sl in slips if sl['totalOdds'] >= MIN_TOTAL_ODDS or sl.get('risk') in ('safe','medium')]
# Max 4 days: drop slips with any leg kicking off more than 4 days ahead, or first leg older than 4 days
MAX_DAYS = 4
_now = dt.datetime.now(dt.timezone.utc)
def _kt(x):
    try: return dt.datetime.fromisoformat(str(x['kickoff']).replace('Z', '+00:00'))
    except Exception: return None
def _in_window(sl):
    ks = [k for k in (_kt(x) for x in sl['legs']) if k]
    if not ks: return True
    return max(ks) <= _now + dt.timedelta(days=MAX_DAYS) and min(ks) >= _now - dt.timedelta(days=MAX_DAYS)
slips = [sl for sl in slips if _in_window(sl)]
# Free-list prune: no slips dated before today, and no slips whose legs have all started or settled
_SETTLED = frozenset({'won', 'lost', 'void', 'push', 'settled'})
def _live(sl):
    if sl.get('earlier'): return False
    sd = (sl.get('date') or (min(sl.get('dates') or ['']) if sl.get('dates') else '') or '')[:10]
    if sd and sd < today.isoformat(): return False
    L = sl.get('legs') or []
    if L and all((x.get('result') or 'pending').lower() in _SETTLED for x in L): return False
    ks = [k for k in (_kt(x) for x in L) if k]
    if ks and len(ks) == len(L) and all(k <= _now for k in ks): return False
    return True
slips = [sl for sl in slips if _live(sl)]
def _risk_ord(s):
    return {'safe':0,'medium':1,'high':2}.get(s.get('risk'), 3 if s.get('house') else 4)
slips.sort(key=lambda s: (s['date'], _risk_ord(s), s['grade'], -s['rating']))
n = {}
for sl in slips:
    n[sl['date']] = n.get(sl['date'], 0) + 1; sl['label'] = f"Slip {n[sl['date']]}"
    sl['code'] = sl['codes'].get('sportybet'); sl['link'] = sl['links'].get('sportybet')

os.makedirs(PRIV, exist_ok=True)
json.dump({sl['label'] + ' ' + sl['date']: private.get(sl.get('code') or '', {}) | {'code': sl.get('code')} for sl in slips},
          open(f"{PRIV}/source-map-{today}.json", 'w'), indent=1)

hp = os.path.join(REPO, 'picks-history.json')
try: hist = json.load(open(hp))
except Exception: hist = {'days': {}}
for day in days:
    rows = [{'slip': sl['label'], 'grade': sl['grade'], 'code': sl.get('code'), **x}
            for sl in slips for x in sl['legs'] if x['date'] == day]
    if rows: hist['days'][day] = rows
cut = (today - dt.timedelta(60)).isoformat()
# scrub any legacy source fields
hist['days'] = {k: [{f: v for f, v in r.items() if f not in ('source', 'bot', 'build', 'confidence')} for r in rows]
                for k, rows in sorted(hist['days'].items()) if k >= cut}
hbody = json.dumps(hist, indent=0, ensure_ascii=False)
hchanged = not os.path.exists(hp) or open(hp).read() != hbody
if hchanged: open(hp, 'w').write(hbody)

out = {'window': [days[0], days[-1]], 'grading': 'see build notes: pick score blends model confidence with odds-implied probability; slip grade A/B/C',
       'slips': slips}
pj = os.path.join(REPO, 'picks.json')
old = None
try: old = json.load(open(pj)); old.pop('DATA_UPDATED', None)
except Exception: pass
_picks_same = old == json.loads(json.dumps(out, ensure_ascii=False)) and not hchanged
if not _picks_same:
    now = dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    json.dump({'DATA_UPDATED': now, **out}, open(pj, 'w'), separators=(',', ':'), ensure_ascii=False)
from collections import Counter
print('picks unchanged' if _picks_same else f"wrote {len(slips)} slips, {sum(len(s['legs']) for s in slips)} legs, DATA_UPDATED={now}, grades={dict(Counter(s['grade'] for s in slips))}")

# ---------------------------------------------------------------------------
# HOME: "Predict2U picks of the day" comes from the research run, not derived here.
# Source: /workspace/predict2u-research/YYYY-MM-DD.json
#   {updatedAt,date,leagues:[{league,games,favWinPct,sample,recentForm}],
#    picks:[{date,ko,league,match,market,selection,odds,confidence,leagueFavRate,sample,case,result,...}],slips:[...]}
# Copied (whitelisted fields only, source names scrubbed) to REPO/home-picks.json.
# Uses today's file, else the newest file dated <= today; if none exists the repo file is left untouched.
# ---------------------------------------------------------------------------
import glob, re as _re
RESEARCH = (__import__('os').environ.get('RESEARCH_DIR','/workspace/predict2u-research'))
_SCRUB = _re.compile(r'nerdy\s*tips|nerdy|bets\s*for\s*the\s*day|betsfortheday|smagpf', _re.I)
def _clean(v):
    if isinstance(v, str): return _SCRUB.sub('Predict2U', v)
    if isinstance(v, list): return [_clean(x) for x in v]
    if isinstance(v, dict): return {k: _clean(x) for k, x in v.items() if k not in ('source', 'bot', 'build', 'src', 'tipster')}
    return v
def home_build():
    files = sorted(f for f in glob.glob(RESEARCH + '/????-??-??.json') if os.path.basename(f)[:10] <= today.isoformat())
    if not files: print('home: no research file yet - home-picks.json left as is'); return False
    try: d = json.load(open(files[-1]))
    except Exception as e: print('home: unreadable', files[-1], e); return False
    leagues = d.get('leagues') or []
    for league in leagues:
      league['picks'] = [p for p in (league.get('picks') or []) if not _mr.is_double_chance(p)]
      league['qualifyingBands'] = [q for q in (league.get('qualifyingBands') or []) if not _mr.is_double_chance(q)]
    out = _clean({'date': d.get('date') or os.path.basename(files[-1])[:10], 'sourceUpdatedAt': d.get('updatedAt'),
                  'leagues': leagues, 'picks': [p for p in (d.get('picks') or []) if not _mr.is_double_chance(p)],
                  'slips': [s for s in (d.get('slips') or []) if not s.get('earlier') and not str(s.get('name') or '').lower().startswith('earlier code')],
                  'homeCode': d.get('homeCode')})
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import pick_history as _PH
        _PH.annotate(out, REPO, os.path.join(os.environ.get('ENGINE_DIR', os.path.join(REPO, 'engine')), 'data', 'pick_ledger.json'))
    except Exception as _e: print('hist: skipped', _e)
    hp = os.path.join(REPO, 'home-picks.json')
    old = None
    try: old = json.load(open(hp)); old.pop('DATA_UPDATED', None)
    except Exception: pass
    if old == json.loads(json.dumps(out)): print('home: unchanged'); return False
    json.dump({'DATA_UPDATED': dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'), **out}, open(hp, 'w'), separators=(',', ':'), ensure_ascii=False)
    print('home:', out['date'], len(out['picks']), 'picks', len(out['leagues']), 'leagues'); return True

_home_changed = home_build()
import subprocess as _sp
_prune=os.path.join(os.environ.get('VENDOR_DIR', os.path.dirname(os.path.abspath(__file__))), 'prune_live.py')
_pr = _sp.run([sys.executable, _prune, REPO], capture_output=True, text=True)
print((_pr.stdout or '').rstrip())
if _pr.stderr: print(_pr.stderr.rstrip(), file=sys.stderr)
_pruned = (_pr.stdout or '').strip().endswith('changed')
if _picks_same and not _home_changed and not _pruned:
    print('unchanged'); sys.exit(3)
