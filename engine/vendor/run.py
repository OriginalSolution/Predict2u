#!/usr/bin/env python3
"""Usage: run.py YYYY-MM-DD [--days N] [--book]  -> /workspace/predict2u-research/YYYY-MM-DD.json"""
import json,os,sys,subprocess,datetime as dt,math,itertools,csv
import os as _os, sys as _sys; _sys.path.insert(0, _os.environ.get('ENGINE_DIR', str(__import__('pathlib').Path(__file__).resolve().parents[1]))); _sys.path.insert(0, _os.environ.get('VENDOR_DIR', str(__import__('pathlib').Path(__file__).resolve().parent)))
D=os.environ.get('RESEARCH_DIR') or os.path.dirname(os.path.abspath(__file__));os.chdir(D)
_VENDOR=os.environ.get('VENDOR_DIR') or os.path.dirname(os.path.abspath(__file__))
day=sys.argv[1] if len(sys.argv)>1 and not sys.argv[1].startswith('-') else dt.date.today().isoformat()
days=int(sys.argv[sys.argv.index('--days')+1]) if '--days' in sys.argv else 1
d0=dt.datetime.fromisoformat(day).replace(tzinfo=dt.timezone.utc)
env=dict(os.environ,WSTART=str(d0.timestamp()*1000),WEND=str((d0+dt.timedelta(days=days)).timestamp()*1000))
if '--skip-engine' not in sys.argv:
  subprocess.run([sys.executable,os.path.join(_VENDOR,'fav_engine.py')],env=env,check=True,stdout=open('engine.log','w'),stderr=subprocess.STDOUT)
C=json.load(open('cands.json'));X=json.load(open('excluded.json'));PR=json.load(open('profiles.json'))
def ko_date(l): 
  return day  # engine gives HH:MM only; date derived below
import time
leagues=[]
for lg,v in sorted(PR.items(),key=lambda kv:-(kv[1]['c'].get('fall_w',0)/max(1,kv[1]['n'].get('fall',0)))):
  n,c=v['n'],v['c'];f=n.get('fall',0)
  leagues.append(dict(league=lg,games=n.get('all',0),favWinPct=round(100*c.get('fall_w',0)/f,1) if f else None,sample=f,
    bands={b:dict(n=n[b],winPct=round(100*c[b+'_w']/n[b],1)) for b in n if b not in('all','fall') and n[b]},
    recentForm=f"home win {round(100*c.get('hw',0)/max(1,n.get('all',0)))}%, O2.5 {round(100*c.get('o25',0)/max(1,n.get('all',0)))}%",source=v['src'],
    thin=f<60))
MK=('w','cs','wtn','o25','u25','u35');MKN={'w':'favourite to win','nl':'favourite or draw','cs':'favourite clean sheet','wtn':'favourite win to nil','o25':'over 2.5','u25':'under 2.5','u35':'under 3.5'}
FX={}
try: FX=json.load(open('fixtures_index.json'))
except Exception: pass
_w0,_w1=d0.strftime('%Y-%m-%d'),(d0+dt.timedelta(days=days)).strftime('%Y-%m-%d')
for L in leagues:
  n,c=PR[L['league']]['n'],PR[L['league']]['c'];q=[]
  for b in n:
    if b in('all','fall') or n[b]<20: continue
    r,k=max((c.get(b+'_'+k,0)/n[b],k) for k in MK)
    if r>=0.70: q.append(dict(band=b,n=n[b],market=MKN[k],rate=round(r,3)))
  BP=PR[L['league']].get('buckets')
  if BP:
    nm={'bal':'Balanced','unbal':'Unbalanced','lowD':'Low draw odds','highD':'High draw odds'}
    def row(k):
      z=BP['b'].get(k)
      if not z: return None
      best=[(m,z[m]) for m in ('fw','o15','o25','u25','u35','btts','nobtts','hw','aw','d') if z[m]>=0.70 and z['n']>=20]
      return dict(key=k,label=' + '.join(nm.get(x,x) for x in k.split('+')),n=z['n'],home=round(100*z['hw']),draw=round(100*z['d']),away=round(100*z['aw']),fav=round(100*z['fw']),
        o25=round(100*z['o25']),u25=round(100*z['u25']),o35=round(100*(1-z['u35'])),u35=round(100*z['u35']),btts=round(100*z['btts']),dc1X=round(100*z['1X']),dcX2=round(100*z['X2']),dc12=round(100*z['12']),
        enough=z['n']>=20,strong=[dict(market=m,rate=round(100*r)) for m,r in best])
    L['buckets']=dict(cutoffs=dict(balanced='favourite price >= 2.10 or |pH-pA| < 0.12',drawLow=f"draw odds <= {BP['cut']['drawLow']} (bottom third)",drawHigh=f"draw odds >= {BP['cut']['drawHigh']} (top third)"),
      priceSource='closing market odds' if PR[L['league']]['src'].startswith('closing') else 'model prices from goals for/against',sample=BP['n'],
      balance=[r for r in (row('bal'),row('unbal')) if r],drawOdds=[r for r in (row('lowD'),row('highD')) if r],
      combos=[r for r in (row(k) for k in ('bal+lowD','bal+highD','unbal+lowD','unbal+highD')) if r])
    q+=[dict(band=r['label'],n=r['n'],market=s_['market'],rate=s_['rate']/100,bucket=True) for g in (L['buckets']['balance'],L['buckets']['drawOdds']) for r in g for s_ in r['strong'][:1]]
  L['qualifies']=bool(q);L['qualifyingBands']=q
  fx=[dict(match=m,ko=v['ko'],eventId=v['eventId']) for m,v in FX.items() if v['league']==L['league'] and _w0<=v['ko'][:10]<_w1]
  L['fixtures']=[]
  for f in sorted(fx,key=lambda f:f['ko']):
    r=X.get(f['match']);f['status']='pick' if any(p['eventId']==f['eventId'] for p in C) else 'no pick';f['reason']=None if f['status']=='pick' else (r or 'kicked off or no SportyBet price')
    L['fixtures'].append(f)
  L['reason']=None
  if not q: L['reason']="favourites don't reach 70% in any price band with 20+ games"
EV={}
try: EV=json.load(open(os.environ.get('SBJSON', os.path.join(os.environ.get('RESEARCH_DIR', D if 'D' in dir() else '.'), 'sb.json'))))
except Exception: pass
picks=[]
for l in C:
  e=EV.get(l['eventId']) or next((v for v in EV.values() if v.get('eventId')==l['eventId']),None)
  date=time.strftime('%Y-%m-%d',time.gmtime(e['estimateStartTime']/1000)) if e else day
  mk={'29':'Both teams to score','1':'1X2','10':'Double chance','18':'Total goals','31':'Home clean sheet','32':'Away clean sheet','33':'Home win to nil','34':'Away win to nil'}.get(l['marketId'],l['marketId'])
  thin=l['n']<60
  BN={'bal':'balanced','unbal':'unbalanced','lowD':'low draw odds','highD':'high draw odds'}
  bi=l.get('bucketInfo') or {}
  head=(f"{l['league']}: favourites at {l['band']} -> this market hit" if l.get('strategy','favourite')=='favourite' else
        f"{l['league']}: {' + '.join(BN.get(x,x) for x in l['bucket'].split('+'))} games ({bi.get('price')} prices {'/'.join(map(str,bi.get('x') or []))}) -> this market hit")
  case=(f"{head} {l['rate']:.0%} over {l['n']} games ({l['src']}); fav price {l['fp']} (1X2 {l['x12']}); "
        f"table {l['table']}; team support: {l['team']}; H2H {l['h2h'].split(' (')[0]}. Risk: "+("thin league sample; " if thin else "")+
        ("away favourite; " if l['x12'].split('/')[2]==str(l['fp']) else "")+("short single-leg price, mainly adds safety" if l['odds']<1.3 else "price band volatility"))
  picks.append(dict(date=date,ko=l['ko'],league=l['league'],match=l['match'],market=mk,selection=l['pick'].replace(' (fav games)',''),odds=l['odds'],
    confidence=round(l['score'],3),leagueFavRate=l['rate'],sample=l['n'],case=case,result='pending',eventId=l['eventId'],marketId=l['marketId'],
    specifier=l['specifier'],outcomeId=l['outcomeId'],thinSample=thin,strategy=l.get('strategy','favourite'),bucket=l.get('bucket')))
import matchup_rules as _MR
_mrlog=[];picks=_MR.apply_all(picks,_mrlog)
json.dump(_mrlog,open('matchup_dropped.json','w'),indent=1,ensure_ascii=False)
prev={}
try: prev=json.load(open(f'{day}.json'))
except Exception: pass
_now=dt.datetime.now(dt.timezone.utc)
def _started(p):
  try: return dt.datetime.fromisoformat(f"{p['date']}T{p['ko']}").replace(tzinfo=dt.timezone.utc)<=_now+dt.timedelta(minutes=15)
  except Exception: return False
_new={p['eventId'] for p in picks}
for p in prev.get('picks') or []:
  if p.get('eventId') not in _new and (_started(p) or p.get('result') not in (None,'pending')): picks.append(p)
picks.sort(key=lambda p:-(p.get('confidence') or p.get('score') or 0))
def slip(name,pool,target=25.0,maxlegs=20):
  legs=[];tot=1.0
  for p in pool:
    if tot>=target or len(legs)>=maxlegs: break
    legs.append(p);tot*=p['odds']
  return dict(name=name,totalOdds=round(tot,2),legs=[{k:p[k] for k in('date','ko','match','market','selection','odds','eventId','marketId','specifier','outcomeId')} for p in legs],codes=dict(sportybet=None,msport=None,betika=None)) if tot>=target else None
for L in leagues:
  L['picks']=[dict(eventId=p['eventId'],match=p['match'],selection=p['selection'],market=p['market'],odds=p['odds'],ko=p['ko'],date=p['date'],strategy=p.get('strategy','favourite'),bucket=p.get('bucket')) for p in picks if p['league']==L['league'] and not _MR.is_double_chance(p)]
  L['status']='pick' if L['picks'] else 'no pick'
  if not L['picks'] and not L['reason']:
    rs=[f['reason'] for f in L['fixtures'] if f['reason']]
    L['reason']=('no fixture passed: '+'; '.join(sorted(set(r.split(' (e.g.')[0] for r in rs)))) if rs else 'no fixture in the window'
leagues.sort(key=lambda L:(0 if L['picks'] else 1 if L['qualifies'] else 2,-(L['favWinPct'] or 0)))
solid=[p for p in picks if not p['thinSample']]
solid_all=solid;solid=[p for p in solid if not _started(p)]
S=[slip('Steady acca (>=25)',solid),
   slip('Alternative A: higher prices (>=25)',[p for p in solid if p['odds']>=1.25]),
   slip('Alternative B: skip the top 5 (>=25)',solid[6:]+[p for p in picks if p['thinSample']])]
open_=[p for p in solid if not _started(p)]
B=slip('Main banker: Banker code of the day',open_+[p for p in picks if p['thinSample'] and not _started(p)])
if B: B['banker']=True;B['strategy']='strongest qualifying-league favourites, total odds >= 25'
S=[B]+S
seen=set();S2=[]
for s_ in S:
  if s_ and frozenset(l['eventId'] for l in s_['legs']) not in seen: seen.add(frozenset(l['eventId'] for l in s_['legs']));S2.append(s_)
S=S2
try:
  import risk_slips as _rsmod
  _tmp={'picks':picks,'slips':S}; _rsmod.inject(_tmp); S=_tmp['slips']
  seen=set(frozenset(l['eventId'] for l in s['legs']) for s in S if not s.get('earlier'))
except Exception as _e:
  print('risk_slips skipped', _e)
_pv={frozenset(l['eventId'] for l in ps['legs']):ps for ps in prev.get('slips') or [] if not ps.get('earlier')}
for s_ in S:  # same legs as an already booked slip -> keep its codes (no rebooking)
  o=_pv.get(frozenset(l['eventId'] for l in s_['legs']))
  if o:
    for k in('codes','bookOdds','bookPicks','bookNotes','bookStatus','bookedAt'):
      if k in o: s_[k]=o[k]
for ps in prev.get('slips') or []:  # keep earlier booked slips of the day (codes already shared)
  if (ps.get('codes') or {}).get('sportybet') and frozenset(l['eventId'] for l in ps['legs']) not in seen:
    ps['banker']=False;ps['earlier']=True;ps['name']=ps['name'] if ps['name'].startswith('Earlier code') else 'Earlier code: '+ps['name'];S.append(ps);seen.add(frozenset(l['eventId'] for l in ps['legs']))
if '--book' in sys.argv:
  from sb_share_helper17 import book
  S=[x for x in S]
  for s in S:
    try: s['codes']['sportybet'],s['bookStatus']=book(s['legs'])
    except Exception as ex: s['bookStatus']=str(ex)[:120]
out=dict(updatedAt=dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'),date=day,days=days,strategy='Favourites price-band + balance/draw-odds bucket strategy: league favourite hit rate by price band (>=70%, n>=20), team home/away support >=60%, H2H >=50%, excludes youth/women/virtual and top-5 v top-5',
  leagues=leagues,picks=picks,slips=S,excluded=X)
if prev.get('homeCode'): out['homeCode']=prev['homeCode']
json.dump(out,open(f'{day}.json','w'),indent=1,ensure_ascii=False)
print(len(leagues),'leagues',len(picks),'picks',[(s['name'],s['totalOdds'],len(s['legs']),s['codes']['sportybet']) for s in S])
