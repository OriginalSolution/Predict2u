"""Historical context for every published pick (real settled data only, never fabricated).

Sources:
  * picks-history.json  — settled legs of published slips (site history)
  * engine/data/pick_ledger.json — every settled house pick (home-picks.json), accumulated daily
  * pick's own research stats (leagueFavRate / sample = league history from football-data closing odds)
Adds p['hist'] = {band, implied, site:{rate,n}, siteAll:{rate,n}, league:{rate,n}} — keys only when data exists.
"""
import json, os, re
BANDS = [(1.0, 1.15), (1.15, 1.30), (1.30, 1.50), (1.50, 1.80), (1.80, 2.50), (2.50, 1000.0)]
MIN_N = 5  # a site rate is only shown once the band has >= MIN_N settled legs


def band(o):
    try: o = float(o)
    except Exception: return None
    for lo, hi in BANDS:
        if lo <= o < hi:
            return f"{lo:.2f}-{hi:.2f}" if hi < 1000 else f"{lo:.2f}+"
    return None


def mkey(sel, market=''):
    s = (sel or '').strip(); m = (market or '').lower()
    x = re.search(r'\b(Over|Under)\s+(\d+(?:\.\d)?)', s, re.I)
    if x:
        team = bool(re.search(r'team', m)) or (len(s.split()) > 2 and not s.lower().startswith(('over', 'under')))
        return ('Team ' if team else '') + x.group(1).title() + ' ' + x.group(2)
    sl = s.lower()
    if sl in ('yes', 'gg', 'btts yes') or 'btts yes' in sl or ('both' in m and sl == 'yes'): return 'BTTS Yes'
    if sl in ('home', 'away', '1', '2') or 'to win' in sl or m in ('1x2',): return 'Win'
    if 'draw no bet' in m or 'dnb' in m: return 'Draw no bet'
    if 'or draw' in sl or 'draw or' in sl or sl in ('1x', 'x2'): return 'Double chance'
    return s or None


def _settled(r): return str(r or '').lower() in ('won', 'lost')


def load_rows(repo, ledger_path):
    rows = []
    try:
        h = json.load(open(os.path.join(repo, 'picks-history.json')))
        for legs in (h.get('days') or {}).values():
            for l in legs:
                if _settled(l.get('result')) and l.get('odds'):
                    rows.append((mkey(l.get('selection'), l.get('market')), band(l.get('odds')), l['result'].lower() == 'won', 'h:' + str(l.get('code')) + ':' + str(l.get('match')) + ':' + str(l.get('selection'))))
    except Exception: pass
    try: led = json.load(open(ledger_path))
    except Exception: led = {}
    for k, v in led.items():
        rows.append((v['m'], v['b'], v['won'], k))
    return rows, led


def update_ledger(led, picks):
    for p in picks or []:
        if not _settled(p.get('result')) or not p.get('odds') or not p.get('eventId'): continue
        k = 'p:' + p['eventId'] + ':' + str(p.get('selection'))
        led[k] = dict(m=mkey(p.get('selection'), p.get('market')), b=band(p.get('odds')), won=p['result'].lower() == 'won', d=p.get('date'))
    return led


def annotate(out, repo, ledger_path):
    picks = out.get('picks') or []
    try: led = json.load(open(ledger_path))
    except Exception: led = {}
    STATS.clear()
    try:
        prev = json.load(open(os.path.join(repo, 'home-picks.json')))
        led = update_ledger(led, list(prev.get('picks') or []) + [q for L in prev.get('leagues') or [] for q in (L.get('picks') or [])])
    except Exception: pass
    allp = list(picks) + [q for L in out.get('leagues') or [] for q in (L.get('picks') or [])]
    led = update_ledger(led, allp)
    os.makedirs(os.path.dirname(ledger_path), exist_ok=True)
    json.dump(led, open(ledger_path, 'w'), indent=0, sort_keys=True)
    rows, _ = load_rows(repo, ledger_path)
    seen = {}
    for m, b, w, k in rows:
        if k in seen: continue
        seen[k] = 1
        for key in ((m, b), (m, None)):
            c = STATS.setdefault(key, [0, 0]); c[0] += w; c[1] += 1
    full = {p.get('eventId'): p for p in picks if p.get('eventId')}

    def hist(p):
        src = full.get(p.get('eventId'), {})
        for f in ('leagueFavRate', 'sample', 'confidence', 'case'):
            if p.get(f) is None and src.get(f) is not None: p[f] = src[f]
        o = p.get('odds'); b = band(o); m = mkey(p.get('selection'), p.get('market')); H = {}
        try:
            if o and float(o) > 1: H['implied'] = round(100 / float(o), 1)
        except Exception: pass
        if b: H['band'] = b
        if m: H['market'] = m
        s = STATS.get((m, b))
        if s and s[1] >= MIN_N: H['site'] = dict(rate=round(100 * s[0] / s[1]), n=s[1])
        s = STATS.get((m, None))
        if s and s[1] >= MIN_N: H['siteAll'] = dict(rate=round(100 * s[0] / s[1]), n=s[1])
        lr, n = p.get('leagueFavRate'), p.get('sample')
        if lr is not None and n:
            r = float(lr); H['league'] = dict(rate=round(r * 100 if r <= 1 else r), n=int(n))
            if 'implied' in H: H['edge'] = round(H['league']['rate'] - H['implied'], 1)
        p['hist'] = H
    for p in allp: hist(p)
    return out


STATS = {}
