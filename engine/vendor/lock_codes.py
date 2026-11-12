#!/usr/bin/env python3
"""Pay-per-code lock: hides the Main banker, Medium and Hot Picks main slip codes from every public file.
Real codes go to private/locked-codes.json and an AES-GCM encrypted locked.enc (key only on the relay).
Usage: lock_codes.py REPO   (idempotent; run after hot picks and after build.py)"""
import json, os, re, sys, glob, base64, datetime as dt
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
FEED = os.environ.get('FEED_DIR') or os.environ.get('ENGINE_DIR') or os.path.dirname(os.path.abspath(__file__)); PRIV = os.environ.get('PRIV_DIR') or os.path.join(FEED, 'private')
STORE = os.path.join(PRIV, 'locked-codes.json'); RESEARCH = (__import__('os').environ.get('RESEARCH_DIR','/workspace/predict2u-research'))
PRICE, CUR = 50, 'GHS'
PH = re.compile(r'P2ULOCK-[a-z]+-\d{8}-[a-z]+\d*')
HTML_TXT = '🔒 Premium code · unlock on predict2u.com'
now = dt.datetime.now(dt.timezone.utc)

def key(): return bytes.fromhex(open(os.path.join(PRIV, 'lock.key')).read().strip())
def load(p, d=None):
  try: return json.load(open(p))
  except Exception: return d
def ph(i, book, n=0): return f'P2ULOCK-{i}-{book}' + (str(n) if n else '')
def real(c): return isinstance(c, str) and c and not PH.fullmatch(c)
def lv(v):  # normalise to list of {code,...}
  if isinstance(v, list): return [dict(x) if isinstance(x, dict) else {'code': x} for x in v]
  if isinstance(v, dict): return [dict(v)]
  return [{'code': v}] if v else []

def expiry(day, starts):
  ts = [s for s in starts if s]
  try: last = max(dt.datetime.fromisoformat(str(t).replace('Z', '+00:00')) for t in ts)
  except Exception: last = dt.datetime.fromisoformat(day + 'T23:59:00+00:00')
  if last.tzinfo is None: last = last.replace(tzinfo=dt.timezone.utc)
  return (last + dt.timedelta(hours=4)).strftime('%Y-%m-%dT%H:%M:%SZ')

def kind_home(s):
  n = (s.get('name') or '').lower()
  if s.get('risk') == 'medium' or n.startswith('medium slip'): return 'medium'
  if s.get('banker') is True or n.startswith('main banker'): return 'banker'
def legstart(l): return (l.get('date') or '') + 'T' + ((l.get('ko') or '23:59')[:5]) + ':00+00:00' if l.get('date') else None

def register(store, repo):
  files = sorted(f for f in glob.glob(RESEARCH + '/????-??-??.json') if os.path.basename(f)[:10] <= now.date().isoformat())
  d = load(files[-1], {}) if files else {}
  day = (d.get('date') or now.date().isoformat())
  for s in d.get('slips') or []:
    k = kind_home(s)
    if not k or s.get('earlier'): continue
    i = f'{k}-{day.replace("-", "")}'
    codes = {b: [{'code': c, 'totalOdds': (s.get('bookOdds') or {}).get(b), 'legs': (s.get('bookPicks') or {}).get(b)}] for b, c in (s.get('codes') or {}).items() if real(c)}
    if codes: store[i] = {'id': i, 'kind': k, 'title': 'Main Banker' if k == 'banker' else 'Medium slip', 'date': day, 'price': PRICE, 'currency': CUR,
                          'totalOdds': s.get('totalOdds'), 'codes': codes, 'expires': expiry(day, [legstart(l) for l in s.get('legs') or []])}
  h = load(os.path.join(repo, 'hot-picks.json'), {})
  if h.get('slips'):
    s = h['slips'][0]; hd = (h.get('updatedAt') or now.isoformat())[:10]; i = f'hot-{hd.replace("-", "")}'
    codes = {b: [x for x in lv(v) if real(x.get('code'))] for b, v in (s.get('codes') or {}).items()}
    codes = {b: v for b, v in codes.items() if v}
    st = {p.get('eventId'): p.get('start') for p in h.get('picks') or []}
    if codes: store[i] = {'id': i, 'kind': 'hot', 'title': 'Hot Picks main', 'date': hd, 'price': PRICE, 'currency': CUR, 'totalOdds': s.get('totalOdds'),
                          'codes': codes, 'expires': expiry(hd, [st.get(e) for e in s.get('events') or []])}
  # keep only the newest id per kind among the active ones
  return store

def mapping(store):
  fwd, rev = {}, {}
  for i, e in store.items():
    for b, L in e['codes'].items():
      for n, x in enumerate(L):
        p = ph(i, b, n); rev[p] = x['code']; fwd.setdefault(x['code'], p)
  return fwd, rev

def mask_doc(doc, store, fwd):
  """Structured mask of home-picks/picks/hot docs."""
  def slipmask(s):
    C = s.get('codes')
    if not isinstance(C, dict): return
    for b, v in list(C.items()):
      if isinstance(v, list):
        for x in v:
          if isinstance(x, dict) and x.get('code') in fwd: x['code'] = fwd[x['code']]; x['link'] = ''
      elif isinstance(v, str) and v in fwd:
        pass
    # per-book exact placeholders for home-style slips
    for b, v in list(C.items()):
      if isinstance(v, str) and v in fwd:
        i = fwd[v][8:].rsplit('-', 1)[0]; C[b] = ph(i, b) if ph(i, b) in REV else fwd[v]
    for k in ('code',):
      if s.get(k) in fwd: s[k] = fwd[s[k]]
    L = s.get('links')
    if isinstance(L, dict):
      for b in L:
        if any(c in str(L[b]) for c in fwd): L[b] = ''
    if isinstance(s.get('link'), str) and any(c in s['link'] for c in fwd): s['link'] = ''
    pid = {p[8:].rsplit('-', 1)[0] for p in PH.findall(json.dumps(C))}
    if pid:
      prev = s.get('locked') if isinstance(s.get('locked'), dict) else {}
      locked = {'id': sorted(pid)[0], 'price': PRICE, 'currency': CUR}
      if prev.get('odds') is not None: locked['odds'] = prev['odds']
      if prev.get('legs') is not None: locked['legs'] = prev['legs']
      s['locked'] = locked
      try:
        odds = s.get('totalOdds') if s.get('totalOdds') is not None else s.get('odds')
        if odds is not None and float(odds) > 25: s['premium'] = True
      except (TypeError, ValueError): pass
  for k in ('slips', 'byMarket', 'byTeam'):
    for s in doc.get(k) or []: slipmask(s)
  return doc

def mask_text(t, fwd=None, html=False):
  if fwd is None: fwd = mapping(load(STORE, {}))[0]
  for c in sorted(fwd, key=len, reverse=True):
    if len(c) >= 5: t = re.sub(r'(?<![A-Za-z0-9])' + re.escape(c) + r'(?![A-Za-z0-9])', HTML_TXT if html else fwd[c], t)
  return t

def _seal_public(repo, store):
  """File every odds>25 slip into the paywall store and blank code + picks."""
  try:
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    if root not in sys.path: sys.path.insert(0, root)
    from engine.premium import seal_repo_files
  except Exception as e:
    print('premium seal skipped', e); return []
  changed = seal_repo_files(repo, store, ph)
  if changed: print('premium sealed', changed)
  return changed

def main(repo):
  global REV
  store = load(STORE, {}) or {}
  # expire: unmask old ones in json, drop them
  exp = {i for i, e in store.items() if e['expires'] < now.strftime('%Y-%m-%dT%H:%M:%SZ')}
  register(store, repo)
  _seal_public(repo, store)
  exp = {i for i in exp if store[i]['expires'] < now.strftime('%Y-%m-%dT%H:%M:%SZ')}
  live = {i: e for i, e in store.items() if i not in exp}
  _, rev_old = mapping({i: store[i] for i in exp})
  fwd, REV = mapping(live)
  changed = []
  for p in glob.glob(os.path.join(repo, '*.json')) + glob.glob(os.path.join(repo, 'match', '*.html')) + glob.glob(os.path.join(repo, 'league', '*.html')) + [os.path.join(repo, x) for x in ('sitemap.xml', 'matches.html', 'leagues.html')]:
    if not os.path.isfile(p) or os.path.basename(p) in ('package.json', 'manifest.json'): continue
    t0 = open(p, encoding='utf-8').read(); t = t0
    if p.endswith('.json'):
      for a, b in rev_old.items(): t = t.replace(a, b)
      if any(c in t for c in fwd):
        try:
          doc = json.loads(t)
          if isinstance(doc, dict): t = json.dumps(mask_doc(doc, live, fwd), separators=(',', ':'), ensure_ascii=False)
        except Exception: pass
        t = mask_text(t, fwd)
    else: t = mask_text(t, fwd, html=True)
    if t != t0: open(p, 'w', encoding='utf-8').write(t); changed.append(os.path.basename(p))
  for c in fwd:  # share cards rendered for real locked codes
    q = os.path.join(repo, 'share', c + '.png')
    if os.path.exists(q): os.remove(q); changed.append('share/' + c + '.png')
  store = live
  json.dump(store, open(STORE, 'w'), indent=1); os.chmod(STORE, 0o600)
  pub = {i: {k: e[k] for k in ('codes', 'title', 'expires', 'price', 'currency', 'totalOdds')} for i, e in store.items()}
  n = os.urandom(12); ct = AESGCM(key()).encrypt(n, json.dumps(pub).encode(), b'p2u-lock-v1')
  enc = json.dumps({'v': 1, 'updated': now.strftime('%Y-%m-%dT%H:%M:%SZ'), 'ids': {i: {'title': e['title'], 'price': e['price'], 'currency': e['currency'], 'expires': e['expires']} for i, e in store.items()},
                    'iv': base64.b64encode(n).decode(), 'data': base64.b64encode(ct).decode()})
  ep = os.path.join(repo, 'locked.enc.json'); old = open(ep).read() if os.path.exists(ep) else ''
  if old:
    try:
      o = json.loads(old); oo = json.loads(AESGCM(key()).decrypt(base64.b64decode(o['iv']), base64.b64decode(o['data']), b'p2u-lock-v1'))
      if oo == pub: enc = None
    except Exception: pass
  if enc: open(ep, 'w').write(enc); changed.append('locked.enc.json')
  print('locked', sorted(store), 'expired', sorted(exp), 'changed', changed)

REV = {}
if __name__ == '__main__': main(sys.argv[1] if len(sys.argv) > 1 else (__import__('os').environ.get('REPO_DIR','/workspace/Predict2u')))
