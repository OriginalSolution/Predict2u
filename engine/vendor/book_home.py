#!/usr/bin/env python3
"""Book one SportyBet GH code (split if capped) for every home pick not yet kicked off.
Usage: book_home.py [YYYY-MM-DD]  -> writes homeCode into the research JSON."""
import json,sys,os,datetime as dt,math
import os as _os, sys as _sys; _sys.path.insert(0, _os.environ.get('ENGINE_DIR', str(__import__('pathlib').Path(__file__).resolve().parents[1]))); _sys.path.insert(0, _os.environ.get('VENDOR_DIR', str(__import__('pathlib').Path(__file__).resolve().parent)))
from sb_share_helper17 import book
D=os.environ.get('RESEARCH_DIR') or os.path.dirname(os.path.abspath(__file__))
day=next((a for a in sys.argv[1:] if not a.startswith('--')),None) or dt.date.today().isoformat()
f=os.path.join(D,day+'.json'); d=json.load(open(f))
now=dt.datetime.now(dt.timezone.utc)
import matchup_rules as _MR  # shared rules for every bookmaker
_ok={(p['eventId'],str(p.get('marketId')),p.get('specifier') or '',str(p.get('outcomeId'))) for p in _MR.apply_all([p for p in d['picks']])}
def _good(l): return (l.get('eventId'),str(l.get('marketId')),l.get('specifier') or '',str(l.get('outcomeId'))) in _ok
d['picks']=[p for p in d['picks'] if _good(p) or p.get('result') not in (None,'pending')]
d['slips']=[s for s in d.get('slips') or [] if all(_good(l) for l in s['legs'])]
def ko(p):
  try: return dt.datetime.fromisoformat(f"{p['date']}T{p['ko']}").replace(tzinfo=dt.timezone.utc)
  except Exception: return None
legs=[p for p in d['picks'] if p.get('eventId') and (ko(p) is None or ko(p)>now+dt.timedelta(minutes=2))]
if '--day-masters-only' in sys.argv:
  # Minimal bookers for day masters only (skip full home / market rebook).
  from sb_share_helper17 import book as _sb_book
  import fav_day_masters as _FDM
  import concurrent.futures as _cf
  import bp_book as _bp
  def sb_try(L):
    code,st=_sb_book(L)
    if code and st=='ok': return dict(code=code,totalOdds=round(math.prod(p['odds'] for p in L),2),legs=len(L),matches=[p['eventId'] for p in L])
    ok=[p for p in L if _sb_book([p])[1]=='ok']
    if not ok: return None
    code,st=_sb_book(ok)
    return dict(code=code,totalOdds=round(math.prod(p['odds'] for p in ok),2),legs=len(ok),matches=[p['eventId'] for p in ok]) if code and st=='ok' else None
  MU='https://www.msport.com/api/gh/orders/real-sports/order/share'
  def mcall(m,url,body=None):
    c=['curl','-s','-m','30','-A','Mozilla/5.0 Chrome/120','-H','Content-Type: application/json','-H','operid: 3','-X',m,url]
    if body: c+=['-d',json.dumps(body)]
    try: return json.loads(__import__('subprocess').run(c,capture_output=True,text=True).stdout)
    except Exception: return {}
  def msel(p): return {'eventId':p['eventId'],'marketId':str(p.get('marketId','')),'specifier':p.get('specifier') or '','outcomeId':str(p.get('outcomeId',''))}
  def mbook(L):
    ok=[p for p in L if p.get('marketId') and p.get('outcomeId') and mcall('POST',MU,{'selections':[msel(p)]}).get('bizCode')==10000]
    if not ok: return None
    r=mcall('POST',MU,{'selections':[msel(p) for p in ok]})
    if r.get('bizCode')!=10000: return None
    code=r['data']['shareCode']; b=mcall('GET',MU+'/'+code); B=(b.get('data') or {}).get('bettableBetSlip') or []
    tot=round(math.prod(float(x['outcome']['odds']) for x in B),2) if B else None
    return dict(msport=code,totalOdds=tot,legs=len(B) or len(ok),of=len(L),matches=[p['eventId'] for p in ok],link=f'https://www.msport.com/gh/?shareCode={code}')
  def ms_try(L):
    m=mbook(L)
    return dict(code=m['msport'],totalOdds=m['totalOdds'],legs=m['legs'],matches=m.get('matches')) if m else None
  BU='https://api.betika.com.gh/v2/share/'
  def bcall(m,url,body=None):
    c=['curl','-s','-m','30','-A','Mozilla/5.0 Chrome/120','-H','Content-Type: application/json','-X',m,url]
    if body: c+=['-d',json.dumps(body)]
    try: return json.loads(__import__('subprocess').run(c,capture_output=True,text=True).stdout)
    except Exception: return {}
  def bsel(p): return {'odd_key':'','outcome_id':str(p.get('outcomeId','')),'special_bet_value':p.get('specifier') or '','parent_match_id':p['eventId'].split(':')[-1],'sub_type_id':str(p.get('marketId','')),'has_parent':None,'parent_code':None}
  def bkbook(L):
    L=[p for p in L if p.get('marketId') and p.get('outcomeId')]
    if not L: return None
    r=bcall('POST',BU+'encode',{'profile_id':0,'bet_id':None,'token':None,'src':'MOBILE_WEB','product_type':'PREMATCH','betslip':[bsel(p) for p in L]})
    code=r.get('code')
    if not code: return None
    dd=bcall('GET',BU+'decode?code='+code+'&src=MOBILE_WEB').get('data') or []
    V=[x for x in dd if str(x.get('valid'))=='1']
    if not V: return None
    tot=round(math.prod(float(x['odd_value']) for x in V),2)
    ids={'sr:match:'+x['parent_match_id'] for x in V}
    return dict(betika=code,totalOdds=tot,legs=len(V),of=len(L),link=f'https://betika.com/en-gh/share/{code}',matches=sorted(ids))
  def bk_try(L):
    b=bkbook(L)
    return dict(code=b['betika'],totalOdds=b['totalOdds'],legs=b['legs'],matches=b['matches']) if b else None
  FCU='https://www.football.com/api/gh/orders/share'
  def fcall(m,url,body=None):
    c=['curl','-s','-m','30','-A','Mozilla/5.0 Chrome/120','-H','Content-Type: application/json','-H','Accept: application/json','-X',m,url]
    if body: c+=['-d',json.dumps(body)]
    try: return json.loads(__import__('subprocess').run(c,capture_output=True,text=True).stdout)
    except Exception: return {}
  def fsel(p): return {'eventId':p['eventId'],'marketId':str(p.get('marketId','')),'specifier':p.get('specifier') or None,'outcomeId':str(p.get('outcomeId',''))}
  def fc_book(L):
    L=[p for p in L if p.get('marketId') and p.get('outcomeId')]
    if not L: return None
    r=fcall('POST',FCU,{'selections':[fsel(p) for p in L]})
    if r.get('bizCode')!=10000:
      L=[p for p in L if fcall('POST',FCU,{'selections':[fsel(p)]}).get('bizCode')==10000]
      if not L: return None
      r=fcall('POST',FCU,{'selections':[fsel(p) for p in L]})
      if r.get('bizCode')!=10000: return None
    code=r['data']['shareCode']
    tot=round(math.prod(p['odds'] for p in L),2)
    return dict(code=code,totalOdds=tot,legs=len(L),matches=[p['eventId'] for p in L])
  def bp_try(L):
    try: return _bp.book(L)
    except Exception: return None
  BOOK={'sportybet':sb_try,'msport':ms_try,'betika':bk_try,'footballcom':fc_book,'betpawa':bp_try}
  _LINK={'sportybet':'https://www.sportybet.com/gh/?shareCode={}','msport':'https://www.msport.com/gh/?shareCode={}',
    'betika':'https://betika.com/en-gh/share/{}','footballcom':'https://www.football.com/gh/?shareCode={}','betpawa':'https://www.betpawa.com.gh/share-betslip/{}'}
  _PREV_DM=((d.get('homeCode') or {}).get('dayMasters') or {})
  _DM_CACHE={}
  for _day,_m in _PREV_DM.items():
    if isinstance(_m,dict) and _m.get('codes'):
      _DM_CACHE[tuple(sorted((p.get('eventId') or '')+':'+(str(p.get('outcomeId') or '')) for p in (_m.get('picks') or [])))]=_m
  def _dm_slip(name,L):
    key=tuple(sorted(p['eventId']+':'+str(p.get('outcomeId')) for p in L))
    e=dict(name=name,legKey=list(key),legs=len(L),totalOdds=round(math.prod(float(p['odds']) for p in L),2),events=[p['eventId'] for p in L],codes={},bookedAt=None)
    old=_DM_CACHE.get(key)
    if old and old.get('codes'):
      e['codes']=dict(old['codes']); e['bookedAt']=old.get('bookedAt')
    e['bookedAt']=e['bookedAt'] or now.isoformat(timespec='seconds')
    def _one(b):
      fn=BOOK[b]; parts=[]
      for i in range(0,len(L),30):
        try: r=fn([dict(p) for p in L[i:i+30]])
        except Exception: r=None
        if r:
          code=r.get('code') or r.get(b)
          if not code: continue
          parts.append(dict(code=code,totalOdds=r.get('totalOdds'),legs=r.get('legs') or len(L[i:i+30]),
                            link=_LINK.get(b,'').format(code),matches=r.get('matches') or [p['eventId'] for p in L[i:i+30]]))
      return b,parts
    todo=[b for b in BOOK if b not in e['codes']]
    if todo:
      with _cf.ThreadPoolExecutor(5) as ex:
        for b,parts in ex.map(_one,todo):
          if parts: e['codes'][b]=parts
    if e['codes']: _DM_CACHE[key]=e
    print('favDay',name,e['legs'],e['totalOdds'],{b:[(x['code'],x['totalOdds'],x['legs']) for x in v] for b,v in e['codes'].items()})
    return e
  def _dm_pass(L):
    out=[]
    for p in L:
      if _good(p): out.append(p); continue
      try: alt=_MR.swap_to_goals(p) if hasattr(_MR,'swap_to_goals') else None
      except Exception: alt=None
      if alt:
        try: _MR.enrich(alt); ok,_,_=_MR.check(alt)
        except Exception: ok=False
        if ok: out.append(alt)
    return out
  _dm=_FDM.build_day_masters(d.get('picks') or [], _dm_slip, pass_fn=_dm_pass, now=now, today=day, days_ahead=1)
  d.setdefault('homeCode',{})['dayMasters']=_dm
  json.dump(d,open(f,'w'),indent=1,ensure_ascii=False)
  print('dayMasters',{k:{'legs':v.get('legs'),'of':v.get('of'),'odds':v.get('totalOdds'),'codes':{b:[x.get('code') for x in (vv or [])] for b,vv in (v.get('codes') or {}).items()}} for k,v in _dm.items()})
  raise SystemExit(0)
def try_book(L):
  code,st=book(L)
  if code and st=='ok': return code,L
  return None,st
PREV_BM={g:v for g,v in ((d.get('homeCode') or {}).get('byMarket') or {}).items() if 'double chance' not in g.lower()}
MS_ONLY='--msport-only' in sys.argv
DAY_MASTERS_ONLY='--day-masters-only' in sys.argv
if MS_ONLY or DAY_MASTERS_ONLY: d.setdefault('homeCode',{})
elif '--markets-only' in sys.argv: pass
else:
  codes=[]; err=None
  for n in (1,2,3,4):  # split into n chunks if the full slip is refused
    size=math.ceil(len(legs)/n) if legs else 0; chunks=[legs[i:i+size] for i in range(0,len(legs),size)] if size else []
    out=[]
    for c in chunks:
      code,r=try_book(c)
      if not code:
        # drop legs one at a time that may be closed: try each alone
        ok=[p for p in c if book([p])[1]=='ok']
        code,r=try_book(ok) if ok else (None,'none open')
      if not code: err=r; out=None; break
      tot=round(math.prod(p['odds'] for p in r),2)
      out.append(dict(sportybet=code,totalOdds=tot,legs=len(r),link=f'https://www.sportybet.com/gh/?shareCode={code}',
                      matches=[p['eventId'] for p in r]))
    if out is not None: codes=out; break
  d['homeCode']=dict(bookedAt=now.isoformat(timespec='seconds'),codes=codes,status='ok' if codes else (err or 'no open picks'))
  json.dump(d,open(f,'w'),indent=1,ensure_ascii=False)
  print(json.dumps(d['homeCode'],indent=1)[:1500])

# ---- MSport GH: public share API (no login), same Betradar event/market/outcome ids ----
import subprocess
MU='https://www.msport.com/api/gh/orders/real-sports/order/share'
def mcall(m,url,body=None):
  c=['curl','-s','-m','30','-A','Mozilla/5.0 Chrome/120','-H','Content-Type: application/json','-H','operid: 3','-X',m,url]
  if body: c+=['-d',json.dumps(body)]
  try: return json.loads(subprocess.run(c,capture_output=True,text=True).stdout)
  except Exception: return {}
def msel(p): return {'eventId':p['eventId'],'marketId':str(p.get('marketId','')),'specifier':p.get('specifier') or '','outcomeId':str(p.get('outcomeId',''))}
def mbook(L):
  ok=[p for p in L if p.get('marketId') and p.get('outcomeId') and mcall('POST',MU,{'selections':[msel(p)]}).get('bizCode')==10000]
  if not ok: return None
  r=mcall('POST',MU,{'selections':[msel(p) for p in ok]})
  if r.get('bizCode')!=10000: return None
  code=r['data']['shareCode']; b=mcall('GET',MU+'/'+code); B=(b.get('data') or {}).get('bettableBetSlip') or []
  tot=round(math.prod(float(x['outcome']['odds']) for x in B),2) if B else None
  return dict(msport=code,totalOdds=tot,legs=len(B) or len(ok),of=len(L),matches=[p['eventId'] for p in ok],link=f'https://www.msport.com/gh/?shareCode={code}')
mcodes=[]
for c in d['homeCode'].get('codes') or []:
  L=[p for p in legs if p['eventId'] in set(c.get('matches') or [])]
  m=mbook(L)
  if m: mcodes.append(m)
  else:  # MSport caps slip size: split into halves
    h=math.ceil(len(L)/2)
    for part in (L[:h],L[h:]):
      m=mbook(part)
      if m: mcodes.append(m)
d['homeCode']['msport']=mcodes
json.dump(d,open(f,'w'),indent=1,ensure_ascii=False)
print('msport',json.dumps(mcodes))

# ---- Betika GH: public share API (no login): POST v2/share/encode, GET v2/share/decode. Same Betradar ids. ----
BU='https://api.betika.com.gh/v2/share/'
def bcall(m,url,body=None):
  c=['curl','-s','-m','30','-A','Mozilla/5.0 Chrome/120','-H','Content-Type: application/json','-X',m,url]
  if body: c+=['-d',json.dumps(body)]
  try: return json.loads(subprocess.run(c,capture_output=True,text=True).stdout)
  except Exception: return {}
def bsel(p): return {'odd_key':'','outcome_id':str(p.get('outcomeId','')),'special_bet_value':p.get('specifier') or '','parent_match_id':p['eventId'].split(':')[-1],'sub_type_id':str(p.get('marketId','')),'has_parent':None,'parent_code':None}
def bkbook(L):
  L=[p for p in L if p.get('marketId') and p.get('outcomeId')]
  if not L: return None
  r=bcall('POST',BU+'encode',{'profile_id':0,'bet_id':None,'token':None,'src':'MOBILE_WEB','product_type':'PREMATCH','betslip':[bsel(p) for p in L]})
  code=r.get('code')
  if not code: return None
  dd=bcall('GET',BU+'decode?code='+code+'&src=MOBILE_WEB').get('data') or []
  V=[x for x in dd if str(x.get('valid'))=='1']
  if not V: return None
  tot=round(math.prod(float(x['odd_value']) for x in V),2)
  ids={'sr:match:'+x['parent_match_id'] for x in V}
  return dict(betika=code,totalOdds=tot,legs=len(V),of=len(L),link=f'https://betika.com/en-gh/share/{code}',matches=sorted(ids))
bcodes=[]
for c in d['homeCode'].get('codes') or []:
  L=[p for p in legs if p['eventId'] in set(c.get('matches') or [])]
  b=bkbook(L)
  if b: bcodes.append(b)
d['homeCode']['betika']=bcodes
for c in d['homeCode'].get('msport') or []: pass
print('betika',json.dumps([{k:v for k,v in b.items() if k!='matches'} for b in bcodes]))


# ---- football.com GH (SportyBet group): same public share API + same Betradar ids; Betpawa GH via bp_book ----
FCU='https://www.football.com/api/gh/orders/share'
def fcall(m,url,body=None):
  c=['curl','-s','-m','30','-A','Mozilla/5.0 Chrome/120','-H','Content-Type: application/json','-H','Accept: application/json','-X',m,url]
  if body: c+=['-d',json.dumps(body)]
  try: return json.loads(subprocess.run(c,capture_output=True,text=True).stdout)
  except Exception: return {}
def fsel(p): return {'eventId':p['eventId'],'marketId':str(p.get('marketId','')),'specifier':p.get('specifier') or None,'outcomeId':str(p.get('outcomeId',''))}
def fc_book(L):
  L=[p for p in L if p.get('marketId') and p.get('outcomeId')]
  if not L: return None
  r=fcall('POST',FCU,{'selections':[fsel(p) for p in L]})
  if r.get('bizCode')!=10000:
    L=[p for p in L if fcall('POST',FCU,{'selections':[fsel(p)]}).get('bizCode')==10000]
    if not L: return None
    r=fcall('POST',FCU,{'selections':[fsel(p) for p in L]})
    if r.get('bizCode')!=10000: return None
  code=r['data']['shareCode']
  O=(fcall('GET',FCU+'/'+code).get('data') or {}).get('outcomes') or []
  od=[]
  for o in O:
    if o.get('matchStatus')!='Not start': continue
    for mk in o.get('markets') or []:
      for oc in mk.get('outcomes') or []: od.append(float(oc['odds']))
  tot=round(math.prod(od),2) if od else round(math.prod(p['odds'] for p in L),2)
  return dict(code=code,totalOdds=tot,legs=len(od) or len(L),matches=[o['eventId'] for o in O] or [p['eventId'] for p in L])
import bp_book
def bp_try(L):
  try: return bp_book.book(L)
  except Exception: return None
fcodes=[];pcodes=[]
for c in d['homeCode'].get('codes') or []:
  L=[p for p in legs if p['eventId'] in set(c.get('matches') or [])]
  x=fc_book(L)
  if x: fcodes.append(dict(footballcom=x['code'],totalOdds=x['totalOdds'],legs=x['legs'],of=len(L),link=f"https://www.football.com/gh/?shareCode={x['code']}",matches=x['matches']))
  y=bp_try(L)
  if y: pcodes.append(dict(betpawa=y['code'],totalOdds=y['totalOdds'],legs=y['legs'],of=len(L),link=(y.get('link') or ('https://www.betpawa.com.gh/share-betslip/'+y['code'])),matches=y['matches']))
d['homeCode']['footballcom']=fcodes;d['homeCode']['betpawa']=pcodes
json.dump(d,open(f,'w'),indent=1,ensure_ascii=False)
print('footballcom',[(x['footballcom'],x['totalOdds'],x['legs']) for x in fcodes],'betpawa',[(x['betpawa'],x['totalOdds'],x['legs']) for x in pcodes])

# ---- Slips (Banker code of the day + alternatives): book on SportyBet, MSport and Betika ----
# For the banker slip, a platform that is missing legs gets topped up with the next strongest open picks until it is back to >=25.
P={p['eventId']:p for p in d['picks']}
openP=[p for p in sorted(d['picks'],key=lambda p:-p['confidence']) if p.get('eventId') and (ko(p) is None or ko(p)>now+dt.timedelta(minutes=2)) ]
openP=[p for p in openP if not p.get('thinSample')]+[p for p in openP if p.get('thinSample')]
def full(l): return P.get(l['eventId'],l)
def sb_try(L):
  code,st=book(L)
  if code and st=='ok': return dict(code=code,totalOdds=round(math.prod(p['odds'] for p in L),2),legs=len(L),matches=[p['eventId'] for p in L])
  ok=[p for p in L if book([p])[1]=='ok']
  if not ok: return None
  code,st=book(ok)
  return dict(code=code,totalOdds=round(math.prod(p['odds'] for p in ok),2),legs=len(ok),matches=[p['eventId'] for p in ok]) if code and st=='ok' else None
def ms_try(L):
  m=mbook(L)
  if not m: return None
  return dict(code=m['msport'],totalOdds=m['totalOdds'],legs=m['legs'],matches=None)
def bk_try(L):
  b=bkbook(L)
  return dict(code=b['betika'],totalOdds=b['totalOdds'],legs=b['legs'],matches=b['matches']) if b else None
BOOK={'sportybet':sb_try,'msport':ms_try,'betika':bk_try,'footballcom':fc_book,'betpawa':bp_try}
for s in d.get('slips') or []:
  if s.get('earlier'): continue
  s.setdefault('codes',{});s.setdefault('bookOdds',{});s.setdefault('bookPicks',{});s.setdefault('bookNotes',{})
  base=[full(l) for l in s['legs']]
  if any(ko(p) and ko(p)<=now for p in base) and s['codes'].get('sportybet'): continue  # already booked and running
  for bk,fn in BOOK.items():
    if s['codes'].get(bk): continue
    L=list(base);r=fn(L);extra=[]
    pool=[p for p in openP if p['eventId'] not in {x['eventId'] for x in base}]
    while s.get('banker') and r and (r['totalOdds'] or 0)<25 and pool and len(L)<25:
      L=L+[pool.pop(0)];r2=fn(L)
      if r2 and r2['legs']>r['legs']: r=r2;extra.append(L[-1]['match'])
      elif r2 is None: L=L[:-1]
      else: L=L[:-1]
    if not r: s['bookNotes'][bk]='could not book';continue
    s['codes'][bk]=r['code'];s['bookOdds'][bk]=r['totalOdds'];s['bookPicks'][bk]=r['legs']
    miss=len(base)+len(extra)-r['legs']
    note=[]
    if miss>0: note.append(f"{miss} pick{'s' if miss>1 else ''} not available")
    if extra: note.append('topped up with '+', '.join(extra)+' to stay at 25+ odds')
    if r['totalOdds'] and r['totalOdds']<25 and s.get('risk') not in ('safe','medium'): note.append('under 25 odds on this site')
    if note: s['bookNotes'][bk]='; '.join(note)
    else: s['bookNotes'].pop(bk,None)
  s['bookedAt']=now.isoformat(timespec='seconds');s['bookStatus']='ok' if s['codes'].get('sportybet') else 'partial'
  print('slip',s['name'],s['totalOdds'],len(s['legs']),s['codes'],s['bookOdds'],s['bookPicks'],s['bookNotes'])
json.dump(d,open(f,'w'),indent=1,ensure_ascii=False)

# ---- Codes by market: candidates from market_cands.json (every market a match qualifies for), Safe (top 5) + Full variants,
# one code per variant per site, split into parts of <=MAXL legs, rebooked only when the variant's leg set changes ----
MAXL=30
MNAME={('1','','1'):'Home win',('1','','3'):'Away win',('1','','2'):'Draw',('10','','9'):'Double chance 1X',('10','','11'):'Double chance X2',('10','','10'):'Double chance 12',
  ('11','','4'):'Draw no bet (home)',('11','','5'):'Draw no bet (away)',('29','','74'):'BTTS Yes',('29','','76'):'BTTS No',('19','total=0.5','12'):'Home team over 0.5',('20','total=0.5','12'):'Away team over 0.5',
  ('68','total=0.5','12'):'Half-time over 0.5'}
for t in ('0.5','1.5','2.5','3.5','4.5'): MNAME[('18','total='+t,'12')]='Over '+t;MNAME[('18','total='+t,'13')]='Under '+t
MC=[]
try: MC=json.load(open(os.path.join(D,'market_cands.json')))
except Exception: pass
for p in d['picks']:  # make sure the day's main picks are in their market too
  if not any(m['eventId']==p['eventId'] and str(m['outcomeId'])==str(p.get('outcomeId')) and m['marketId']==p.get('marketId') and (m.get('specifier') or '')==(p.get('specifier') or '') for m in MC):
    MC.append(dict(p,score=p.get('confidence',0)))
G={}
MC=[m for m in MC if _good(m)]
for p in MC:
  if not p.get('eventId') or not (ko(p) is None or ko(p)>now+dt.timedelta(minutes=2)): continue
  g=MNAME.get((str(p.get('marketId')),p.get('specifier') or '',str(p.get('outcomeId'))))
  if g and all(x['eventId']!=p['eventId'] for x in G.get(g,[])): G.setdefault(g,[]).append(p)
def bookparts(fn,L):
  parts=[L[i:i+MAXL] for i in range(0,len(L),MAXL)];out=[]
  for c in parts:
    try: r=fn(list(c))
    except Exception: r=None
    if r: out.append(dict(code=r['code'],totalOdds=r['totalOdds'],legs=r['legs'],of=len(c)))
  return out
BM={}
for g,L in G.items():
  if len(L)<2: continue
  L=sorted(L,key=lambda p:-(p.get('score') or 0))
  V={'full':L}
  if len(L)>6: V['safe']=L[:5]
  BM[g]={}
  for v,LL in V.items():
    key=sorted(p['eventId']+':'+str(p['outcomeId']) for p in LL);old=(PREV_BM.get(g) or {}).get(v) or {}
    if old.get('legKey')==key:
      for bk,fn in BOOK.items():
        if bk not in old:
          parts=bookparts(fn,LL)
          if parts: old[bk]=dict(parts[0],parts=parts) if len(parts)>1 else parts[0]
      BM[g][v]=old;continue
    e=dict(legKey=key,totalOdds=round(math.prod(p['odds'] for p in LL),2),bookedAt=now.isoformat(timespec='seconds'),
      picks=[dict(eventId=p['eventId'],match=p['match'],league=p.get('league'),date=p.get('date'),ko=p.get('ko'),selection=p['selection'],odds=p['odds'],rate=p.get('rate') or p.get('leagueFavRate'),n=p.get('n') or p.get('sample')) for p in LL])
    for bk,fn in BOOK.items():
      parts=bookparts(fn,LL)
      if parts: e[bk]=dict(parts[0],parts=parts) if len(parts)>1 else parts[0]
    BM[g][v]=e;print('market',g,v,len(LL),{k:(x['code'],x['totalOdds'],x['legs']) for k,x in e.items() if isinstance(x,dict)})
d.setdefault('homeCode',{})['byMarket']=BM
json.dump(d,open(f,'w'),indent=1,ensure_ascii=False)

# ---- Favourites day masters (Today / Tomorrow tabs on "How favourites perform by league") ----
import fav_day_masters as _FDM
import concurrent.futures as _cf
_LINK={'sportybet':'https://www.sportybet.com/gh/?shareCode={}','msport':'https://www.msport.com/gh/?shareCode={}',
  'betika':'https://betika.com/en-gh/share/{}','footballcom':'https://www.football.com/gh/?shareCode={}','betpawa':'https://www.betpawa.com.gh/share-betslip/{}'}
_PREV_DM=((d.get('homeCode') or {}).get('dayMasters') or {})
_DM_CACHE={}
for _day,_m in _PREV_DM.items():
  if isinstance(_m,dict) and _m.get('codes'):
    _DM_CACHE[tuple(sorted((p.get('eventId') or '')+':'+(str(p.get('outcomeId') or '')) for p in (_m.get('picks') or [])))]=_m
def _dm_slip(name,L):
  key=tuple(sorted(p['eventId']+':'+str(p.get('outcomeId')) for p in L))
  e=dict(name=name,legKey=list(key),legs=len(L),totalOdds=round(math.prod(float(p['odds']) for p in L),2),events=[p['eventId'] for p in L],codes={},bookedAt=None)
  old=_DM_CACHE.get(key)
  if old and old.get('codes'):
    e['codes']=dict(old['codes']); e['bookedAt']=old.get('bookedAt')
  e['bookedAt']=e['bookedAt'] or now.isoformat(timespec='seconds')
  def _one(b):
    fn=BOOK[b]; parts=[]
    for i in range(0,len(L),30):
      try: r=fn([dict(p) for p in L[i:i+30]])
      except Exception: r=None
      if r:
        code=r.get('code') or r.get(b)
        if not code: continue
        parts.append(dict(code=code,totalOdds=r.get('totalOdds'),legs=r.get('legs') or len(L[i:i+30]),
                          link=_LINK.get(b,'').format(code),matches=r.get('matches') or [p['eventId'] for p in L[i:i+30]]))
    return b,parts
  todo=[b for b in BOOK if b not in e['codes']]
  if todo:
    with _cf.ThreadPoolExecutor(5) as ex:
      for b,parts in ex.map(_one,todo):
        if parts: e['codes'][b]=parts
  if e['codes']: _DM_CACHE[key]=e
  print('favDay',name,e['legs'],e['totalOdds'],{b:[(x['code'],x['totalOdds'],x['legs']) for x in v] for b,v in e['codes'].items()})
  return e
def _dm_pass(L):
  """Keep legs that already pass, else try goals swap for obscure leagues."""
  out=[]
  for p in L:
    if _good(p):
      out.append(p); continue
    try:
      alt=_MR.swap_to_goals(p) if hasattr(_MR,'swap_to_goals') else None
    except Exception:
      alt=None
    if alt:
      k=(alt.get('eventId'),str(alt.get('marketId')),alt.get('specifier') or '',str(alt.get('outcomeId')))
      # accept swap if check passes
      try:
        _MR.enrich(alt); ok,_,_= _MR.check(alt)
      except Exception:
        ok=False
      if ok: out.append(alt)
  return out
_dm=_FDM.build_day_masters(d.get('picks') or [], _dm_slip, pass_fn=_dm_pass, now=now, today=day, days_ahead=1)
d.setdefault('homeCode',{})['dayMasters']=_dm
json.dump(d,open(f,'w'),indent=1,ensure_ascii=False)
print('dayMasters',{k:{'legs':v.get('legs'),'of':v.get('of'),'odds':v.get('totalOdds'),'codes':{b:[x.get('code') for x in (vv or [])] for b,vv in (v.get('codes') or {}).items()}} for k,v in _dm.items()})
