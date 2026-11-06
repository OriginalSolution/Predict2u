#!/usr/bin/env python3
"""Build Safe (low risk) and Medium (balanced) slips from open high-confidence picks.

Safe:  3-5 highest-confidence legs, total odds about 2-5.
Medium: 6-8 legs (up to 12 if prices are short), total odds about 8-15.
Both are booked by book_home.py like other house slips.
"""
import datetime as dt

def _started(p, now=None, pad_min=15):
  now = now or dt.datetime.now(dt.timezone.utc)
  try:
    return dt.datetime.fromisoformat(f"{p['date']}T{p['ko']}").replace(tzinfo=dt.timezone.utc) <= now + dt.timedelta(minutes=pad_min)
  except Exception:
    return False

def _leg(p):
  return {k: p[k] for k in ('date','ko','match','market','selection','odds','eventId','marketId','specifier','outcomeId') if k in p}

def band_slip(name, pool, lo, hi, nmin, nmax, risk, hard_max=None):
  """Greedily take highest-confidence picks into the odds band [lo, hi]."""
  hard_max = hard_max or nmax
  legs, tot = [], 1.0
  for p in pool:
    if len(legs) >= hard_max: break
    od = float(p.get('odds') or 1)
    nxt = tot * od
    # once in band with enough legs, stop before overshooting hi
    if len(legs) >= nmin and tot >= lo and nxt > hi: break
    legs.append(p); tot = nxt
    if tot >= lo and len(legs) >= nmin and (tot >= (lo + hi) / 2 or len(legs) >= nmax):
      if tot >= lo: break
  if len(legs) < nmin or tot < lo * 0.9:  # allow slight under for short prices
    return None
  return dict(
    name=name, totalOdds=round(tot, 2),
    legs=[_leg(p) for p in legs],
    codes=dict(sportybet=None, msport=None, betika=None, footballcom=None, betpawa=None),
    risk=risk,
    banker=False,
    strategy=f'{risk} risk · {len(legs)} strongest open picks · target odds {lo}-{hi}',
  )

def build(picks, now=None):
  """Return [safe, medium] (skipping None) from today's picks list."""
  now = now or dt.datetime.now(dt.timezone.utc)
  solid = [p for p in sorted(picks, key=lambda p: -float(p.get('confidence') or 0))
           if p.get('eventId') and not p.get('thinSample') and not _started(p, now)]
  safe = band_slip('Safe slip (low risk)', solid, lo=2.0, hi=5.0, nmin=3, nmax=5, risk='safe')
  used = {l['eventId'] for l in (safe['legs'] if safe else [])}
  # Medium: prefer a mix that reaches 8-15; allow up to 12 legs when prices are short
  # Medium: prefer slightly longer prices so 6-8 legs can reach ~8-15 odds
  mpool = [p for p in solid if float(p.get('odds') or 0) >= 1.18] or solid
  medium = band_slip('Medium slip (balanced)', mpool, lo=8.0, hi=15.0, nmin=6, nmax=8, risk='medium', hard_max=10)
  if medium is None:
    medium = band_slip('Medium slip (balanced)', solid, lo=7.5, hi=15.0, nmin=6, nmax=10, risk='medium', hard_max=14)
  # Avoid duplicating the exact same leg set as safe
  out = []
  if safe: out.append(safe)
  if medium:
    mid_ids = frozenset(l['eventId'] for l in medium['legs'])
    if not safe or mid_ids != frozenset(l['eventId'] for l in safe['legs']):
      out.append(medium)
  return out

def inject(day_doc, now=None):
  """Insert/refresh Safe+Medium at the front of day_doc['slips'], preserving booked codes when legs match."""
  new = build(day_doc.get('picks') or [], now=now)
  if not new: return day_doc
  prev = {frozenset(l['eventId'] for l in s.get('legs') or []): s
          for s in (day_doc.get('slips') or []) if (s.get('risk') in ('safe','medium') or 'Safe slip' in (s.get('name') or '') or 'Medium slip' in (s.get('name') or ''))}
  kept = []
  for s in new:
    key = frozenset(l['eventId'] for l in s['legs'])
    old = prev.get(key)
    if old and (old.get('codes') or {}).get('sportybet'):
      for k in ('codes','bookOdds','bookPicks','bookNotes','bookStatus','bookedAt'):
        if k in old: s[k] = old[k]
    kept.append(s)
  # Drop previous safe/medium (and earlier copies of them) then prepend
  rest = [s for s in (day_doc.get('slips') or [])
          if s.get('risk') not in ('safe','medium')
          and 'Safe slip' not in (s.get('name') or '')
          and 'Medium slip' not in (s.get('name') or '')
          and not (s.get('earlier') and ('Safe slip' in (s.get('name') or '') or 'Medium slip' in (s.get('name') or '')))]
  # Mark high-risk slips
  for s in rest:
    if not s.get('risk') and not s.get('earlier'):
      s['risk'] = 'high'
  day = day_doc.get('date')
  for s in kept:
    if day:
      s['date']=day
      for l in s.get('legs') or []:
        l.setdefault('date', l.get('date') or day)
  day_doc['slips'] = kept + rest
  return day_doc

if __name__ == '__main__':
  import json, sys, os
  day = (sys.argv[1] if len(sys.argv) > 1 else dt.date.today().isoformat())
  path = os.path.join(os.path.dirname(os.path.abspath(__file__)), day + '.json')
  d = json.load(open(path))
  inject(d)
  json.dump(d, open(path, 'w'), indent=1, ensure_ascii=False)
  for s in d['slips']:
    if s.get('risk') in ('safe','medium') or 'Safe' in s.get('name','') or 'Medium' in s.get('name',''):
      print(s['name'], s['totalOdds'], len(s['legs']), s.get('risk'), s.get('codes'))
