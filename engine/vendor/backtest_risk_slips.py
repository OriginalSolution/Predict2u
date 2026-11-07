#!/usr/bin/env python3
"""Backtest Safe/Medium leg selection against settled pick history.

Uses unique settled legs from the code ledger + picks-history (won/lost only).
Simulates: sort by available score/confidence proxy, take top N, report
combined hit rate (all legs won) and per-leg hit rate for Safe (top 3-5)
and Medium (top 6-8 / top 12).
"""
import json, os
from collections import defaultdict

REPO = '/workspace/Predict2u'
LEDGER = '/workspace/predict2u-feed/code-ledger.json'

def load_settled():
  rows = {}
  # picks-history
  try:
    h = json.load(open(os.path.join(REPO, 'picks-history.json')))
    for day, rs in (h.get('days') or {}).items():
      for r in rs:
        res = (r.get('result') or '').lower()
        if res not in ('won', 'lost'): continue
        key = (day, r.get('match'), r.get('selection'), r.get('market'))
        score = r.get('score')
        try: score = float(score) if score is not None else None
        except Exception: score = None
        try: odds = float(r.get('odds') or 0) or None
        except Exception: odds = None
        rows[key] = dict(day=day, match=r.get('match'), selection=r.get('selection'),
                         market=r.get('market'), result=res, score=score, odds=odds, src='hist')
  except Exception as e:
    print('hist', e)
  # ledger legs (fill gaps; prefer hist)
  try:
    L = json.load(open(LEDGER))
    for v in L.values():
      day = v.get('date')
      for leg in v.get('legs') or []:
        res = (leg.get('result') or '').lower()
        if res not in ('won', 'lost'): continue
        key = (day, leg.get('match'), leg.get('selection'), None)
        if any(k[1]==leg.get('match') and k[2]==leg.get('selection') for k in rows): continue
        rows[key] = dict(day=day, match=leg.get('match'), selection=leg.get('selection'),
                         market=None, result=res, score=None, odds=None, src='ledger')
  except Exception as e:
    print('ledger', e)
  return list(rows.values())

def sim(day_rows, n):
  # rank by score desc, then shorter odds (proxy for confidence)
  ranked = sorted(day_rows, key=lambda r: (-(r['score'] if r['score'] is not None else 0.5), r['odds'] or 99))
  take = ranked[:n]
  if len(take) < n: return None
  hits = sum(1 for r in take if r['result']=='won')
  won_all = hits == n
  tot = 1.0
  for r in take:
    if r['odds']: tot *= r['odds']
  return dict(n=n, hits=hits, won_all=won_all, hit_rate=hits/n, odds=round(tot,2) if tot>1 else None)

def main():
  rows = load_settled()
  by_day = defaultdict(list)
  for r in rows: by_day[r['day']].append(r)
  print(f'settled picks: {len(rows)} across {len(by_day)} days')
  overall = {k: {'days':0,'all_won':0,'leg_hits':0,'leg_total':0,'odds':[]} for k in ('safe3','safe4','safe5','med6','med8','med12','high15')}
  for day, rs in sorted(by_day.items()):
    if len(rs) < 3: continue
    for key, n in (('safe3',3),('safe4',4),('safe5',5),('med6',6),('med8',8),('med12',12),('high15',15)):
      r = sim(rs, n)
      if not r: continue
      o = overall[key]; o['days'] += 1
      if r['won_all']: o['all_won'] += 1
      o['leg_hits'] += r['hits']; o['leg_total'] += r['n']
      if r['odds']: o['odds'].append(r['odds'])
  print('\nBacktest (highest-score legs per day against settled results)')
  print(f"{'tier':<8} {'n':>3} {'days':>5} {'slip_hit':>10} {'leg_hit':>10} {'avg_odds':>10}")
  for key, n in (('safe3',3),('safe4',4),('safe5',5),('med6',6),('med8',8),('med12',12),('high15',15)):
    o = overall[key]
    if not o['days']: continue
    slip = 100*o['all_won']/o['days']
    leg = 100*o['leg_hits']/o['leg_total'] if o['leg_total'] else 0
    avg = sum(o['odds'])/len(o['odds']) if o['odds'] else 0
    print(f"{key:<8} {n:>3} {o['days']:>5} {slip:>9.1f}% {leg:>9.1f}% {avg:>10.2f}")
  # write JSON for the report
  out = {k: dict(days=v['days'], slipHitRate=round(v['all_won']/v['days'],3) if v['days'] else None,
                 legHitRate=round(v['leg_hits']/v['leg_total'],3) if v['leg_total'] else None,
                 avgOdds=round(sum(v['odds'])/len(v['odds']),2) if v['odds'] else None)
         for k,v in overall.items() if v['days']}
  json.dump(out, open('/workspace/predict2u-feed/backtest-risk-slips.json','w'), indent=2)
  print('\nwrote backtest-risk-slips.json')
  return out

if __name__ == '__main__':
  main()
