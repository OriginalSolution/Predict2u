#!/usr/bin/env python3
"""Build public Track record (record.json) from the code ledger — settled codes only."""
import json, os, sys, datetime as dt
from collections import defaultdict

FEED = (__import__('os').environ.get('FEED_DIR','/workspace/predict2u-feed'))
REPO = sys.argv[1] if len(sys.argv) > 1 else (__import__('os').environ.get('REPO_DIR','/workspace/Predict2u'))
LEDGER = os.path.join(FEED, 'code-ledger.json')
STAKE = 10.0  # flat GH₵ stake for ROI

def load():
  try: return json.load(open(LEDGER))
  except Exception: return {}

def slip_type(e):
  name = (e.get('name') or '').lower()
  kind = (e.get('kind') or 'slip').lower()
  if 'safe slip' in name or e.get('risk') == 'safe': return 'safe'
  if 'medium slip' in name or e.get('risk') == 'medium': return 'medium'
  if kind == 'banker' or 'banker' in name: return 'banker'
  if kind == 'alt' or 'alternative' in name or 'steady' in name: return 'alternative'
  if kind == 'market': return 'market'
  if kind == 'all': return 'all-picks'
  if kind == 'hot' or 'hot' in name: return 'hot'
  return kind or 'slip'

def market_of(e):
  name = e.get('name') or ''
  if e.get('kind') == 'market':
    # "Over 1.5 (full)" / "Home win (safe)"
    return name.split(' (')[0].strip() or 'Market'
  # derive from dominant leg selection pattern
  legs = e.get('legs') or []
  if not legs: return 'Other'
  sels = [str(l.get('selection') or '') for l in legs]
  def bucket(s):
    sl = s.lower()
    if sl.startswith('over '): return 'Over ' + s.split(' ', 1)[1] if ' ' in s else 'Over'
    if sl.startswith('under '): return 'Under ' + s.split(' ', 1)[1] if ' ' in s else 'Under'
    if ' or draw' in sl or ' or ' in sl: return 'Double chance'
    if sl in ('draw', 'x'): return 'Draw'
    if 'btts' in sl or 'both teams' in sl or sl in ('gg', 'yes', 'no'): return 'BTTS'
    return 'Match result / other'
  from collections import Counter
  c = Counter(bucket(s) for s in sels)
  return c.most_common(1)[0][0]

def roi_block(rows):
  """rows: list of settled entries with odds + status."""
  n = len(rows)
  if not n: return dict(n=0, won=0, lost=0, winRate=None, staked=0, returned=0, profit=0, roi=None)
  won = sum(1 for r in rows if r['status'] == 'won')
  lost = n - won
  staked = STAKE * n
  returned = sum(STAKE * float(r.get('odds') or 0) for r in rows if r['status'] == 'won')
  profit = round(returned - staked, 2)
  return dict(
    n=n, won=won, lost=lost,
    winRate=round(100.0 * won / n, 1),
    stake=STAKE, staked=round(staked, 2), returned=round(returned, 2),
    profit=profit, roi=round(100.0 * profit / staked, 1) if staked else None,
  )

def streak(sorted_rows):
  """Current and best streaks from newest-first or oldest-first list of statuses."""
  # expect oldest first
  cur = best_w = best_l = 0
  cur_kind = None
  seq = 0
  for r in sorted_rows:
    st = r['status']
    if st == cur_kind: seq += 1
    else: cur_kind = st; seq = 1
    if st == 'won': best_w = max(best_w, seq)
    if st == 'lost': best_l = max(best_l, seq)
  # current from the end (most recent)
  cur_st = sorted_rows[-1]['status'] if sorted_rows else None
  cur_n = 0
  for r in reversed(sorted_rows):
    if r['status'] != cur_st: break
    cur_n += 1
  return dict(current=cur_st, currentLen=cur_n, bestWin=best_w, bestLoss=best_l)

def build():
  led = load()
  codes = list(led.values())
  settled = [e for e in codes if e.get('status') in ('won', 'lost')]
  pending = sum(1 for e in codes if e.get('status') == 'pending')

  # Distinct slips (same legs on several books count once) for headline
  distinct = {}
  for e in settled:
    key = (e.get('date'), e.get('name'), e.get('total') or len(e.get('legs') or []))
    # prefer sportybet copy if present
    if key not in distinct or e.get('book') == 'sportybet':
      distinct[key] = e
  distinct_rows = list(distinct.values())

  by_type = defaultdict(list)
  by_book = defaultdict(list)
  by_market = defaultdict(list)
  by_day = defaultdict(list)
  for e in settled:
    by_type[slip_type(e)].append(e)
    by_book[e.get('book') or 'unknown'].append(e)
    by_market[market_of(e)].append(e)
    by_day[e.get('date') or 'unknown'].append(e)

  # For distinct-based type/day (headline honesty)
  d_type = defaultdict(list); d_day = defaultdict(list)
  for e in distinct_rows:
    d_type[slip_type(e)].append(e)
    d_day[e.get('date') or 'unknown'].append(e)

  # Chronological distinct for streak
  chrono = sorted(distinct_rows, key=lambda e: (e.get('date') or '', e.get('firstSeen') or ''))
  # Recent list: newest first, include all settled codes (per book) but cap
  recent = sorted(settled, key=lambda e: (e.get('date') or '', e.get('firstSeen') or ''), reverse=True)

  # Pick-level from ledger legs (unique match+selection+date)
  picks = {}
  for e in codes:
    for l in e.get('legs') or []:
      r = (l.get('result') or '').lower()
      if r not in ('won', 'lost'): continue
      k = (e.get('date'), l.get('match'), l.get('selection'))
      picks[k] = r
  pw = sum(1 for r in picks.values() if r == 'won')
  pl = sum(1 for r in picks.values() if r == 'lost')

  def pack(groups, use_distinct_style=False):
    out = []
    for k, rows in sorted(groups.items(), key=lambda kv: -len(kv[1])):
      b = roi_block(rows)
      b['key'] = k
      out.append(b)
    return out

  overall = roi_block(distinct_rows)
  overall_codes = roi_block(settled)

  out = dict(
    DATA_UPDATED=dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
    stakeCurrency='GHS',
    flatStake=STAKE,
    note='Figures use only settled booking codes from our published slips. Pending codes are excluded. ROI assumes a flat GH₵10 stake on every settled code (no cash-out). The same slip booked on several sites is counted once in the headline, and once per site in the by-site table.',
    overall=dict(
      **overall,
      pending=pending,
      codesSettled=overall_codes['n'],
      codesWon=overall_codes['won'],
      codesLost=overall_codes['lost'],
    ),
    streak=streak(chrono),
    byType=pack(d_type),
    bySite=pack(by_book),
    byMarket=pack(by_market),
    byDay=[{**roi_block(by_day[d]), 'key': d} for d in sorted(by_day.keys(), reverse=True)],
    picks=dict(settled=pw + pl, won=pw, lost=pl, winRate=round(100.0 * pw / (pw + pl), 1) if (pw + pl) else None),
    recent=[dict(
      code=e.get('code'), book=e.get('book'), date=e.get('date'), name=e.get('name'),
      kind=slip_type(e), odds=e.get('odds'), status=e.get('status'),
      hit=e.get('hit'), total=e.get('total'),
      profit=round(STAKE * float(e['odds']) - STAKE, 2) if e.get('status') == 'won' else -STAKE,
    ) for e in recent[:40]],
  )
  path = os.path.join(REPO, 'record.json')
  body = json.dumps(out, indent=1, ensure_ascii=False)
  old = open(path).read() if os.path.exists(path) else None
  changed = old != body
  if changed: open(path, 'w').write(body)
  print('record', 'wrote' if changed else 'unchanged', 'settled_slips', overall['n'], 'winRate', overall['winRate'], 'roi', overall['roi'], 'pending', pending)
  return changed

if __name__ == '__main__':
  build()
