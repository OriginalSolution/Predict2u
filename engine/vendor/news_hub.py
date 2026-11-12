#!/usr/bin/env python3
"""Build news-hub.json: fixture previews, injuries, transfers (public RSS) + settled code record."""
import json, os, re, sys, glob, html, datetime as dt, urllib.request, concurrent.futures as cf
import xml.etree.ElementTree as ET
REPO = sys.argv[1] if len(sys.argv) > 1 else '/workspace/Predict2u'
R = os.environ.get('RESEARCH_DIR') or '/workspace/predict2u-research'; FEED = os.path.dirname(os.path.abspath(__file__))
# On Actions the ledger/event cache live in a cached dir (NEWS_STATE_DIR); the box keeps them beside this file.
_ST = os.environ.get('NEWS_STATE_DIR') or FEED; os.makedirs(_ST, exist_ok=True)
LEDGER = os.path.join(_ST, 'code-ledger.json'); EV = os.path.join(_ST, 'event-cache.json')
UA = {'User-Agent': 'Mozilla/5.0 (predict2u.com news builder)'}
now = dt.datetime.now(dt.timezone.utc)
def get(u, t=20):
    return urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=t).read()
FEEDS = [('BBC Sport', 'https://feeds.bbci.co.uk/sport/football/rss.xml'),
         ('Sky Sports', 'https://www.skysports.com/rss/11095'),
         ('The Guardian', 'https://www.theguardian.com/football/rss'),
         ('ESPN', 'https://www.espn.com/espn/rss/soccer/news')]
def clean(s):
    s = re.sub(r'<[^>]+>', ' ', html.unescape(s or '')); return re.sub(r'\s+', ' ', s).strip()
def parse(src, raw):
    out = []
    for it in ET.fromstring(raw).iter('item'):
        t = clean(it.findtext('title')); l = (it.findtext('link') or '').strip()
        if not t or not l.startswith('http'): continue
        s = clean(it.findtext('description'))
        if len(s) > 220: s = s[:217].rsplit(' ', 1)[0] + '…'
        pd = it.findtext('pubDate') or ''
        try: ts = dt.datetime.strptime(pd.strip()[:25], '%a, %d %b %Y %H:%M:%S').replace(tzinfo=dt.timezone.utc).isoformat()
        except Exception: ts = ''
        img = ''
        for el in it.iter():
            tag = el.tag.split('}')[-1]
            if tag in ('thumbnail', 'content') and el.get('url', '').startswith('http') and (tag == 'thumbnail' or 'image' in (el.get('medium', '') + el.get('type', 'image'))): img = el.get('url'); break
            if tag == 'enclosure' and 'image' in el.get('type', '') and el.get('url', '').startswith('http'): img = el.get('url'); break
        out.append(dict(title=t, summary=s, source=src, link=l.split('?at_medium')[0], published=ts, image=img))
    return out
items = []
for src, u in FEEDS:
    try: items += parse(src, get(u))
    except Exception as e: print('feed fail', src, u, e, file=sys.stderr)
seen = set(); uniq = []
for x in items:
    k = re.sub(r'\W+', '', x['title'].lower())[:60]
    if k in seen or x['link'] in seen: continue
    seen.add(k); seen.add(x['link']); uniq.append(x)
uniq.sort(key=lambda x: x['published'], reverse=True)
# our fixtures (today + tomorrow)
day = now.strftime('%Y-%m-%d'); tom = (now + dt.timedelta(days=1)).strftime('%Y-%m-%d')
fx = []; resf = sorted(glob.glob(os.path.join(R, '20??-??-??.json')))
cur = json.load(open(resf[-1])) if resf else {}
if not resf:  # Actions refresh job: no research file, use the published picks
    try: cur = json.load(open(os.path.join(REPO, 'home-picks.json')))
    except Exception: cur = {}
for p in cur.get('picks', []):
    if p.get('date') in (day, tom) and p.get('match'): fx.append(dict(date=p['date'], ko=p.get('ko'), league=p.get('league'), match=p['match']))
fx = sorted({(f['date'], f['ko'] or '', f['league'] or '', f['match']): f for f in fx}.values(), key=lambda f: (f['date'], f['ko'] or ''))
STOP = {'fc','sc','cf','afc','ac','united','city','club','de','real','the','sp','rj','fk','cd','ca','v','and'}
teams = set()
for f in fx:
    for side in f['match'].split(' v '):
        for w in re.findall(r'[A-Za-zÀ-ÿ]{4,}', side):
            if w.lower() not in STOP: teams.add(w.lower())
LEAG = ['premier league','championship','la liga','serie a','bundesliga','ligue 1','champions league','europa','conference league','eredivisie','mls','fa cup','carabao']
INJ = re.compile(r'\b(injur\w*|ruled out|sidelined|hamstring|knee|ankle|groin|surgery|fitness|suspen\w*|ban(ned)?|red card|team news|doubt|out for)\b', re.I)
TRF = re.compile(r'\b(transfer\w*|sign(s|ed|ing)?|deal|loan|bid|fee|contract|move to|joins?|gossip|target|£\d|€\d|release clause|free agent)\b', re.I)
PRE = re.compile(r'\b(preview|predict\w*|vs\.?|clash|faces?|facing|host|travel to|ahead of|team news|line-?ups?|kick-?off|fixtures?|tonight|tomorrow|this weekend|derby|press conference|build-up|will play|set to play)\b', re.I)
REP = re.compile(r'\b(beat|beats|thrash\w*|win at|wins at|survive\w*|claim\w*|cruise\w*|draw with|stun\w*|romp|story of|revisit\w*|record)\b', re.I)
def hits_team(x):
    t = (x['title'] + ' ' + x['summary']).lower(); return sum(1 for w in teams if re.search(r'\b' + re.escape(w) + r'\b', t))
inj, trf, pre = [], [], []
for x in uniq:
    if re.match(r'(Football Daily|Football Weekly|Quiz|.*podcast|.*\bF1\b|.*Formula 1|.*\bGP\b)', x['title'], re.I): continue
    t = x['title'] + ' ' + x['summary']; ht = hits_team(x); x['ourFixture'] = ht > 0
    if INJ.search(t): inj.append(x)
    elif TRF.search(t): trf.append(x)
    elif PRE.search(t) or (ht and not REP.search(x['title'])): x['preview'] = bool(PRE.search(t)); pre.append(x)
key = lambda x: (not x['ourFixture'], 0 if not x['published'] else -dt.datetime.fromisoformat(x['published']).timestamp())
inj.sort(key=key); pre.sort(key=lambda x: (not x.get('preview'),) + key(x))
inj, trf, pre = inj[:14], trf[:14], pre[:14]
def alive(x):
    try:
        r = urllib.request.urlopen(urllib.request.Request(x['link'], headers=UA, method='GET'), timeout=12); return r.status < 400
    except Exception: return False
allx = inj + trf + pre
with cf.ThreadPoolExecutor(12) as ex: ok = dict(zip([id(x) for x in allx], ex.map(alive, allx)))
inj, trf, pre = [[x for x in L if ok[id(x)]] for L in (inj, trf, pre)]
# ---------- code ledger ----------
from matchup_rules import is_double_chance as dc_leg
def dc_entry(e):
    return bool(re.search(r'double\s*chance', str(e.get('name') or ''), re.I)) or any(dc_leg(l) for l in e.get('legs') or [])
try: led = json.load(open(LEDGER))
except Exception: led = {}
# Actions: fold in the engine's own append-only ledger (engine/data/code-ledger.json) so the hub
# keeps the full code history without the box. Existing entries keep their settled state.
_seed = os.environ.get('NEWS_SEED_LEDGER')
if _seed and os.path.exists(_seed):
    try:
        for _k, _e in (json.load(open(_seed)) or {}).items():
            if _k not in led and isinstance(_e, dict) and _e.get('legs'): led[_k] = _e
    except Exception as e: print('seed ledger', e, file=sys.stderr)
# Hard site-wide veto: purge legacy DC entries before settlement or publication.
for k in list(led):
    if dc_entry(led[k]): led.pop(k)
def addc(code, book, date, name, odds, legs, kind):
    if not code or not legs or re.search(r'double\s*chance', str(name or ''), re.I) or any(dc_leg(l) for l in legs): return
    k = book + ':' + code
    e = led.get(k) or dict(code=code, book=book, date=date, name=name, kind=kind, odds=odds, firstSeen=now.isoformat(timespec='seconds'))
    e.update(odds=odds or e.get('odds'), legs=legs if not e.get('legs') or e.get('settled') is None else e['legs']); led[k] = e
for f in resf:
    d = json.load(open(f)); dd = d.get('date') or os.path.basename(f)[:10]
    pk = {p['eventId']: p for p in d.get('picks', []) if p.get('eventId')}
    L = lambda l: dict(eventId=l.get('eventId'), match=l['match'], selection=l['selection'], odds=l.get('odds'), result=l.get('result'))
    for s in d.get('slips', []):
        for bk, c in (s.get('codes') or {}).items():
            addc(c, bk, dd, re.sub(r'^Earlier code: ', '', s['name']), (s.get('bookOdds') or {}).get(bk, s.get('totalOdds')), [L(l) for l in s['legs']], 'banker' if s.get('banker') else 'alt')
    h = d.get('homeCode') or {}
    for blk in [h.get('codes') or [], h.get('msport') or [], h.get('betika') or []]:
        for c in (blk if isinstance(blk, list) else [blk]):
            for bk in ('sportybet', 'msport', 'betika', 'footballcom', 'betpawa'):
                if isinstance(c, dict) and isinstance(c.get(bk), str):
                    addc(c[bk], bk, dd, 'All picks of the day', c.get('totalOdds'), [L(pk[m]) for m in c.get('matches', []) if m in pk], 'all')
    for g, V in (h.get('byMarket') or {}).items():
        for v, e in V.items():
            for bk, c in e.items():
                if isinstance(c, dict) and c.get('code'):
                    for part in (c.get('parts') or [c]):
                        addc(part['code'], bk, dd, f'{g} ({v})', part.get('totalOdds'), [L(p) for p in e.get('picks', [])], 'market')
try:
    for dd, legs in (json.load(open(os.path.join(REPO, 'picks-history.json'))).get('days') or {}).items():
        S = {}
        for l in legs:
            if l.get('code'): S.setdefault(l['code'], []).append(l)
        for c, ls in S.items():
            o = 1
            for l in ls: o *= float(l.get('odds') or 1)
            addc(c, 'sportybet', dd, ls[0].get('slip') or 'Slip', round(o, 2), [dict(match=l['match'], selection=l['selection'], odds=l.get('odds'), result=l.get('result')) for l in ls], 'slip')
except Exception as e: print('history', e, file=sys.stderr)
try: evc = json.load(open(EV))
except Exception: evc = {}
need = {l['eventId'] for e in led.values() for l in e['legs'] if l.get('eventId') and (l.get('result') or 'pending') == 'pending' and not (evc.get(l['eventId']) or {}).get('final')}
def fetch(eid):
    try:
        d = json.loads(get(f'https://www.sportybet.com/api/gh/factsCenter/event?eventId={eid}&productId=3'))['data']
        return eid, dict(final=d.get('matchStatus') == 'Ended' and bool(d.get('setScore')), score=d.get('setScore'), status=d.get('matchStatus'), home=d.get('homeTeamName'), away=d.get('awayTeamName'))
    except Exception: return eid, None
with cf.ThreadPoolExecutor(8) as ex:
    for eid, v in ex.map(fetch, list(need)):
        if v: evc[eid] = v
json.dump(evc, open(EV, 'w'))
def settle(l):
    r = (l.get('result') or 'pending').lower()
    if r in ('won', 'lost', 'void'): return r
    ev = evc.get(l.get('eventId') or '')
    if not ev or not ev.get('final'): return 'pending'
    h, a = map(int, str(ev['score']).replace('-', ':').split(':')[:2]); s = l['selection'].strip(); tot = h + a
    m = re.match(r'(Over|Under) (\d+(?:\.\d+)?)$', s, re.I)
    if m: return 'won' if (tot > float(m[2])) == (m[1].lower() == 'over') else 'lost'
    H, A = (re.split(r'\s+v(?:s)?\s+', l.get('match') or '', maxsplit=1) + [''])[:2]
    tm = re.match(r'^(.+?)\s+(over|under)\s+(\d+(?:\.\d+)?)\s*goals?$', s, re.I)
    if tm:
        team, side, line = tm.group(1).strip(), tm.group(2).lower(), float(tm.group(3))
        tl = team.lower()
        if tl in ('home', '1') or team == H.strip(): goals = h
        elif tl in ('away', '2') or team == A.strip(): goals = a
        elif H.strip() and (tl == H.strip().lower() or H.strip().lower() in tl or tl in H.strip().lower()): goals = h
        elif A.strip() and (tl == A.strip().lower() or A.strip().lower() in tl or tl in A.strip().lower()): goals = a
        else: return 'pending'
        return 'won' if (goals > line) == (side == 'over') else 'lost'
    out = {'1': h > a, 'X': h == a, '2': a > h}
    def tok(x):
        x = x.strip(); return '1' if x == H.strip() else '2' if x == A.strip() else 'X' if x.lower() == 'draw' else None
    ps = [tok(x) for x in re.split(r'\s+or\s+', s)]
    if ps and all(ps): return 'won' if any(out[p] for p in ps) else 'lost'
    if s.lower() in ('gg', 'both teams to score', 'yes', 'btts yes', 'gg (btts yes)'): return 'won' if h and a else 'lost'
    return 'pending'
for e in led.values():
    for l in e['legs']:
        l['result'] = settle(l); ev = evc.get(l.get('eventId') or '')
        if ev and ev.get('score'): l['score'] = ev['score']
    rs = [l['result'] for l in e['legs']]
    e['hit'] = rs.count('won'); e['total'] = len(rs)
    e['status'] = 'lost' if 'lost' in rs else 'won' if all(r in ('won', 'void') for r in rs) else 'pending'
    e['settled'] = None if e['status'] == 'pending' else e['status']
json.dump(led, open(LEDGER, 'w'), indent=1, ensure_ascii=False)
def og(x):
    try:
        h = get(x['link'], 12)[:300000].decode('utf-8', 'ignore')
        m = re.search(r'<meta[^>]+(?:property|name)=["\'](?:og:image|twitter:image)["\'][^>]+content=["\']([^"\']+)', h) or re.search(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+(?:property|name)=["\']og:image', h)
        if m and m.group(1).startswith('http'): x['image'] = html.unescape(m.group(1))
    except Exception: pass
need = [x for x in pre + inj + trf if not x.get('image')]
with cf.ThreadPoolExecutor(8) as ex: list(ex.map(og, need))
for x in pre + inj + trf:
    if x.get('image', '').startswith('http:'): x['image'] = 'https:' + x['image'][5:]
codes = sorted((e for e in led.values() if not str(e.get('code') or '').startswith('P2ULOCK-')), key=lambda e: (e.get('date') or '', e.get('firstSeen') or ''), reverse=True)
# win rate over distinct slips (same legs booked on several sites count once)
slips = {}
for e in codes:
    if e['status'] != 'pending': slips[(e['date'], e['name'], e['total'])] = e['status']
w = sum(1 for v in slips.values() if v == 'won'); n = len(slips)
pub = [dict(code=e['code'], book=e['book'], date=e['date'], name=e['name'], kind=e['kind'], odds=e['odds'], status=e['status'], hit=e['hit'], total=e['total'],
            legs=[dict(match=l['match'], selection=l['selection'], result=l['result'], score=l.get('score')) for l in e['legs']]) for e in codes[:60]]
out = dict(updatedAt=now.isoformat(timespec='seconds'), sources=sorted({s for s, _ in FEEDS}) + ['SportyBet match centre (final scores)'],
           fixtures=fx[:80], previews=pre, injuries=inj, transfers=trf,
           record=dict(won=w, lost=n - w, settled=n, pending=sum(1 for e in codes if e['status'] == 'pending'), winRate=round(100 * w / n, 1) if n else None),
           codes=pub)
p = os.path.join(REPO, 'news-hub.json'); old = open(p).read() if os.path.exists(p) else ''
new = json.dumps(out, indent=1, ensure_ascii=False)
strip = lambda o: {k: v for k, v in o.items() if k != 'updatedAt'}
if not old or strip(json.loads(old)) != strip(out): open(p, 'w').write(new)
print('previews', len(pre), 'injuries', len(inj), 'transfers', len(trf), 'fixtures', len(fx), 'codes', len(codes), 'record', out['record'])
