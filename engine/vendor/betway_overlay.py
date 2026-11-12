#!/usr/bin/env python3
"""Merge hand-booked Betway codes (betway_codes.json) into the newest research slips.
Entries are keyed by the slip's SportyBet code, so they vanish automatically when slips are rebooked.
Also drops Betway entries whose SportyBet slip is gone, earlier, or dated before today.
"""
import json, os, glob, datetime as dt, sys
sys.path.insert(0, os.environ.get('RESEARCH_DIR', '/workspace/predict2u-research'))
import matchup_rules as MR
FEED = os.path.dirname(os.path.abspath(__file__)); R = '/workspace/predict2u-research'
src_path = os.path.join(FEED, 'betway_codes.json')
src = json.load(open(src_path))
today = dt.datetime.now(dt.timezone.utc).date().isoformat()
files = sorted(f for f in glob.glob(R + '/????-??-??.json') if os.path.basename(f)[:10] <= today)
if not files: raise SystemExit(0)
p = files[-1]; d = json.load(open(p)); by = dict(src.get('bySlip') or {}); n = 0; ch = False
rday = d.get('date') or os.path.basename(p)[:10]
live_sporty = set()
for s in d.get('slips') or []:
  if s.get('earlier') or str(s.get('name') or '').lower().startswith('earlier code'): continue
  C = s.get('codes') or {}
  # Any legacy DC slip invalidates its Betway ticket: hide it and leave a clear pending note.
  if any(MR.is_double_chance(l) for l in s.get('legs') or []):
    if 'betway' in C:
      C.pop('betway'); (s.get('bookOdds') or {}).pop('betway', None); (s.get('bookPicks') or {}).pop('betway', None); ch = True
    s.setdefault('bookNotes', {})['betway'] = 'Pending DC-free rebooking'
    continue
  sb = C.get('sportybet')
  if sb: live_sporty.add(str(sb).strip().upper())
  e = None if s.get('earlier') else by.get(C.get('sportybet')) or by.get(str(C.get('sportybet') or '').upper())
  if e and src.get('date') == rday:
    new = dict(C, betway=e['code'])
    if new != C or (s.get('bookOdds') or {}).get('betway') != e['odds']:
      s['codes'] = new; s.setdefault('bookOdds', {})['betway'] = e['odds']; s.setdefault('bookPicks', {})['betway'] = e['picks']
      if e.get('note'): s.setdefault('bookNotes', {})['betway'] = e['note']
      ch = True
    n += 1
  elif 'betway' in C:
    C.pop('betway'); (s.get('bookOdds') or {}).pop('betway', None); (s.get('bookPicks') or {}).pop('betway', None); (s.get('bookNotes') or {}).pop('betway', None); ch = True
# Drop stale Betway map entries (wrong day, or SportyBet slip no longer live)
src_ch = False
if src.get('date') != today and src.get('date') != rday:
  by.clear(); src_ch = True
else:
  for k in list(by.keys()):
    if str(k).strip().upper() not in live_sporty:
      by.pop(k); src_ch = True
if src_ch:
  src['bySlip'] = by
  src['date'] = rday if rday >= today else today
  json.dump(src, open(src_path, 'w'), indent=0, ensure_ascii=False)
  # keep compact one-line-ish structure similar to before
  print('betway_codes.json pruned', len(by), 'live keys')
if ch: json.dump(d, open(p, 'w'), indent=1, ensure_ascii=False)
print('betway overlay', n, 'slips', 'changed' if ch else 'unchanged', 'map', len(by))
