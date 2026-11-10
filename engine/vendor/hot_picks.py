#!/usr/bin/env python3
"""Hot Picks: aggregate the public SportyBet GH code hub (featured shared codes), pick the most-backed
selection per upcoming match, and book the slips on every site book_home.py supports.
Usage: hot_picks.py OUT_JSON   (rebooks only when a slip's legs change)"""
import concurrent.futures as cf,json,sys,os,ast,math,subprocess,datetime as dt,collections
D=os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0,D); import os as _os, sys as _sys; _sys.path.insert(0, _os.environ.get('ENGINE_DIR', str(__import__('pathlib').Path(__file__).resolve().parents[1]))); _sys.path.insert(0, _os.environ.get('VENDOR_DIR', str(__import__('pathlib').Path(__file__).resolve().parent)))
# reuse booking functions from book_home.py without running its script body
src=open(os.path.join(D,'book_home.py')).read(); T=ast.parse(src); keep=[]
for n in T.body:
  if isinstance(n,(ast.Import,ast.ImportFrom,ast.FunctionDef)): keep.append(n)
  elif isinstance(n,ast.Assign) and all(isinstance(t,ast.Name) and t.id in ('MU','BU','FCU','MAXL') for t in n.targets): keep.append(n)
G={'__name__':'bh'}; exec(compile(ast.Module(body=keep,type_ignores=[]),'book_home_funcs','exec'),G)
book=G['book']
import hot_section_masters as HSM
def sb(L):
  code,st=book(L)
  if code and st=='ok': return dict(code=code,totalOdds=round(math.prod(p['odds'] for p in L),2),legs=len(L))
  ok=[p for p in L if book([p])[1]=='ok']
  if not ok: return None
  code,st=book(ok)
  return dict(code=code,totalOdds=round(math.prod(p['odds'] for p in ok),2),legs=len(ok)) if code and st=='ok' else None
def ms(L):
  m=G['mbook'](L); return dict(code=m['msport'],totalOdds=m['totalOdds'],legs=m['legs']) if m else None
def bk(L):
  b=G['bkbook'](L); return dict(code=b['betika'],totalOdds=b['totalOdds'],legs=b['legs']) if b else None
BOOK={'sportybet':sb,'msport':ms,'betika':bk}
if 'fc_book' in G: BOOK['footballcom']=lambda L:(lambda r:dict(code=r['code'],totalOdds=r['totalOdds'],legs=r['legs']) if r else None)(G['fc_book'](L))
try:
  import bp_book; BOOK['betpawa']=lambda L:(lambda r:dict(code=r['code'],totalOdds=r['totalOdds'],legs=r['legs']) if r else None)(bp_book.book(L))
except Exception: pass
LINK={'sportybet':'https://www.sportybet.com/gh/?shareCode={}','msport':'https://www.msport.com/gh/?shareCode={}',
  'betika':'https://betika.com/en-gh/share/{}','footballcom':'https://www.football.com/gh/?shareCode={}','betpawa':'https://www.betpawa.com.gh/share-betslip/{}'}
OUT=sys.argv[1]; now=dt.datetime.now(dt.timezone.utc); nowms=now.timestamp()*1000
SECTION_ONLY='--section-masters-only' in sys.argv
UA="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36"

if SECTION_ONLY:
  # Booking-only rebuild from existing hot-picks.json (no hub scrape).
  doc=json.load(open(OUT))
  prev={s['name']:s for s in (doc.get('slips') or [])+(doc.get('byMarket') or [])+(doc.get('byTeam') or [])+(doc.get('sectionMasters') or []) if s.get('name')}
  CACHE={}
  def _seed(lst):
    for x in lst or []:
      if x.get('legKey') and x.get('codes'): CACHE.setdefault(tuple(x['legKey']),x)
  _seed(doc.get('slips')); _seed(doc.get('byMarket')); _seed(doc.get('byTeam')); _seed(doc.get('sectionMasters'))
  _PH=__import__("re").compile(r'^P2ULOCK-')
  def _strip_ph(codes):
    out={}
    for b,v in (codes or {}).items():
      keep=[]
      for x in (v if isinstance(v,list) else [v]):
        cd=(x.get('code') if isinstance(x,dict) else x) or ''
        if _PH.match(str(cd)): continue
        keep.append(x)
      if keep: out[b]=keep
    return out
  for k,v in list(CACHE.items()):
    cleaned=_strip_ph(v.get('codes'))
    if cleaned: CACHE[k]=dict(v,codes=cleaned)
    else: CACHE.pop(k,None)
  def slip(name,L):
    key=sorted(p['eventId']+':'+p['outcomeId'] for p in L); old=prev.get(name) or {}
    e=dict(name=name,legKey=key,legs=len(L),totalOdds=round(math.prod(float(p['odds']) for p in L),2),events=[p['eventId'] for p in L])
    oc=_strip_ph(old.get('codes') or {})
    e['codes']=dict(oc) if old.get('legKey')==key else {}
    e['bookedAt']=old.get('bookedAt') if e['codes'] else None
    c=CACHE.get(tuple(key))
    if c:
      for b,v in _strip_ph(c.get('codes') or {}).items(): e['codes'].setdefault(b,v)
      e['bookedAt']=e['bookedAt'] or c.get('bookedAt')
    e['bookedAt']=e['bookedAt'] or now.isoformat(timespec='seconds')
    def one(b):
      fn=BOOK[b]; parts=[]
      for i in range(0,len(L),30):
        try: r=fn([dict(p) for p in L[i:i+30]])
        except Exception: r=None
        if r: parts.append(dict(r,link=LINK[b].format(r['code'])))
      return b,parts
    todo=[b for b in BOOK if b not in e['codes']]
    with cf.ThreadPoolExecutor(5) as ex:
      for b,parts in ex.map(one,todo):
        if parts: e['codes'][b]=parts
    if e['codes']: CACHE[tuple(key)]=e
    print(name,e['legs'],e['totalOdds'],{b:[(x['code'],x['totalOdds'],x['legs']) for x in v] for b,v in e['codes'].items()})
    return e
  eng=str(__import__('pathlib').Path(D).resolve().parent)
  try:
    import matchup_rules as _MR
    _RC={}
    def _pass(L):
      rows=[]
      for p in L or []:
        try: _MR.enrich(p)
        except Exception: pass
        rows.append(p)
      try:
        import thin_pool as _tp
        chosen, _info = _tp.select(rows)
        return chosen
      except Exception:
        return [p for p in rows if _MR.check(p)[0]]
  except Exception:
    def _pass(L): return list(L or [])
  doc['sectionMasters']=HSM.build_section_masters(doc, slip, pass_fn=_pass, today=now.date().isoformat(), engine_dir=eng)
  doc['updatedAt']=now.isoformat(timespec='seconds')
  json.dump(doc,open(OUT,'w'),indent=1,ensure_ascii=False)
  print('sectionMasters',[(m.get('section'),m.get('label'),m.get('legs'),m.get('totalOdds'),{b:(v[0].get('code') if isinstance(v,list) and v else None) for b,v in (m.get('codes') or {}).items()}) for m in doc['sectionMasters']])
  sys.exit(0)

codes={}
for p in range(1,80):
  try: j=json.loads(subprocess.run(['curl','-s','-m','20','-A',UA,'-H','Accept: application/json',f'https://www.sportybet.com/api/gh/orders/bookingCode/featured?pageNum={p}&pageSize=20'],capture_output=True,text=True).stdout)
  except Exception: break
  dd=j.get('data') or []
  if not dd: break
  for c in dd: codes[c['shareCode']]=c
if len(codes)<5: print('code hub returned no public data',len(codes)); sys.exit(2)
sel=collections.Counter(); w=collections.Counter(); info={}; teams=collections.Counter(); mk=collections.Counter(); ev=collections.Counter()
HOT=15
HOT_FALLBACK=8  # used only when the 15+ pool cannot fill the site
MAXDAYS=4  # only legs kicking off within 4 days
selC=collections.defaultdict(set); teamC=collections.defaultdict(set); mkC=collections.defaultdict(set); evC=collections.defaultdict(set)
for cc,c in codes.items():
  pop=c.get('popularity') or 0
  for s in c.get('shareCodeDetail') or []:
    if s.get('sportId')!='sr:sport:1' or (s.get('startTime') or 0)<nowms+120000 or (s.get('startTime') or 0)>nowms+MAXDAYS*86400000: continue
    k=(s['eventId'],str(s['marketId']),s.get('marketSpecifiers') or '',str(s['outcomeId']))
    if cc in selC[k]: continue
    selC[k].add(cc); w[k]+=pop; info[k]=s; evC[s['eventId']].add(cc)
    teamC[s['homeTeamName']].add(cc); teamC[s['awayTeamName']].add(cc)
sel=collections.Counter({k:len(v) for k,v in selC.items()}); ev=collections.Counter({k:len(v) for k,v in evC.items()})
teams=collections.Counter({k:len(v) for k,v in teamC.items()})
best={}
for k,n in sel.items():
  if str(k[1]) in ('10','60110'): continue  # hard DC veto; next eligible market can win
  e=k[0]
  if e not in best or (n,w[k])>(sel[best[e]],w[best[e]]): best[e]=k
wide=[]
for e,k in best.items():
  s=info[k]; n=sel[k]
  if n<HOT_FALLBACK: continue
  t=dt.datetime.fromtimestamp(s['startTime']/1000,dt.timezone.utc)
  mname=s['marketDescription']+(' '+s['marketSpecifiers'].split('=')[-1] if s.get('marketSpecifiers') else '')
  wide.append(dict(eventId=e,marketId=k[1],specifier=k[2] or None,outcomeId=k[3],odds=float(s['odds']),
    match=f"{s['homeTeamName']} vs {s['awayTeamName']}",market=mname,selection=f"{mname}: {s['outcomeDescription']}",
    date=t.date().isoformat(),ko=t.strftime('%H:%M'),start=t.isoformat(),count=n,matchCount=ev[e],share=round(100*n/len(codes),1),
    pickShare=round(100*n/ev[e]),backing=w[k],icon=s.get('tournamentIcon')))
wide.sort(key=lambda p:(-p['count'],-p['backing']))
# Normal hot list is selections backed by 15+ public slips. A thinner day may use 8+.
import matchup_rules as _MR
import thin_pool as _tp
for p in wide:
  try: _MR.enrich(p)
  except Exception: pass
core=[p for p in wide if p['count']>=HOT]
picks, info=_tp.select(core, quiet=True)
if info['used']:
  wider, info2=_tp.select(wide, quiet=True)
  if info2['used']:
    print(info2['log'], flush=True)
  else:
    print(f"thin-pool fallback used: hot backing floor {HOT}->{HOT_FALLBACK}, qualified {info2['qualified']} (matchup rules unchanged)", flush=True)
  picks=wider
_hdrop=[]
def _pass(L):
  rows=[]
  for p in L or []:
    try: _MR.enrich(p)
    except Exception: pass
    rows.append(p)
  chosen, info=_tp.select(rows)
  if info.get('used'): _hdrop.append(dict(note=info.get('log'), candidates=len(rows), added=info.get('added')))
  return chosen
prev={}
try: prev={s['name']:s for s in json.load(open(OUT)).get('slips',[])}
except Exception: pass
CACHE={}
def _seed(lst):
  for x in lst or []:
    if x.get('legKey') and x.get('codes'): CACHE.setdefault(tuple(x['legKey']),x)
try:
  _o=json.load(open(OUT)); _seed(_o.get('slips')); _seed(_o.get('byMarket')); _seed(_o.get('byTeam'))
except Exception: pass
def slip(name,L):
  key=sorted(p['eventId']+':'+p['outcomeId'] for p in L); old=prev.get(name) or {}
  e=dict(name=name,legKey=key,legs=len(L),totalOdds=round(math.prod(p['odds'] for p in L),2),events=[p['eventId'] for p in L])
  oc=old.get('codes') or {}
  e['codes']=dict(oc) if old.get('legKey')==key else {}
  e['bookedAt']=old.get('bookedAt') if e['codes'] else None
  c=CACHE.get(tuple(key))
  if c:
    for b,v in (c.get('codes') or {}).items(): e['codes'].setdefault(b,v)
    e['bookedAt']=e['bookedAt'] or c.get('bookedAt')
  e['bookedAt']=e['bookedAt'] or now.isoformat(timespec='seconds')
  def one(b):
    fn=BOOK[b]; parts=[]
    for i in range(0,len(L),30):
      try: r=fn([dict(p) for p in L[i:i+30]])
      except Exception: r=None
      if r: parts.append(dict(r,link=LINK[b].format(r['code'])))
    return b,parts
  todo=[b for b in BOOK if b not in e['codes']]
  with cf.ThreadPoolExecutor(5) as ex:
    for b,parts in ex.map(one,todo):
      if parts: e['codes'][b]=parts
  if e['codes']: CACHE[tuple(key)]=e
  print(name,e['legs'],e['totalOdds'],{b:[(x['code'],x['totalOdds'],x['legs']) for x in v] for b,v in e['codes'].items()})
  return e

slips=[]
# main: top picks by popularity until total odds >= 25 (at least 5 legs, at most 30)
L=[]
for p in picks:
  L.append(p)
  if len(L)>=5 and math.prod(x['odds'] for x in L)>=25: break
  if len(L)>=30: break
mainOdds=math.prod(x['odds'] for x in L) if L else 0
mainNote=None if mainOdds>=25 else f"Only {len(picks)} hot picks (15+ slips) today, total odds {mainOdds:.2f}, under 25."
if L: slips.append(slip('Hot Picks slip',L))
for n in (5,10):
  if len(picks)>=n and n!=len(L): slips.append(slip(f'Top {n} hot picks',picks[:n]))
if len(picks)>len(L) and len(picks) not in (5,10): slips.append(slip('All hot picks',picks[:60]))

# ---- Hot by market: normalised clean market names, top pick per match per market ----
def norm(s):
  mid=int(s['marketId']); o=s['outcomeDescription']; sp=s.get('marketSpecifiers') or ''
  tot=sp.split('total=')[-1] if 'total=' in sp else ''
  H,A=s['homeTeamName'],s['awayTeamName']
  if mid==1: return {'Home':'Home win','Away':'Away win','Draw':'Draw'}.get(o)
  if mid==10: return {'Home or Draw':'Double chance 1X','Draw or Away':'Double chance X2','Home or Away':'Double chance 12'}.get(o)
  if mid==11: return 'Draw no bet'
  if mid==18 and tot in('0.5','1.5','2.5','3.5','4.5'): return o.split()[0]+' '+tot+' goals'
  if mid==29: return 'Both teams to score' if o=='Yes' else 'Both teams to score: No'
  if mid in(19,20) and tot in('0.5','1.5','2.5') and o.startswith('Over'): return ('Home' if mid==19 else 'Away')+' team over '+tot
  if mid==60: return {'Home':'1st half home win','Away':'1st half away win','Draw':'1st half draw'}.get(o)
  if mid==68 and tot in('0.5','1.5'): return '1st half '+o.split()[0].lower()+' '+tot
  if mid==90 and tot in('0.5','1.5'): return '2nd half '+o.split()[0].lower()+' '+tot
  return None
def tlabel(s,mk):
  H,A=s['homeTeamName'],s['awayTeamName']
  if mk.startswith('Home') or mk in('Double chance 1X','1st half home win'): return H
  if mk.startswith('Away') or mk in('Double chance X2','1st half away win'): return A
  if mk=='Draw no bet': return H if s['outcomeDescription'].startswith(('Home','1')) or s['outcomeDescription']==H else A
  return f"{H} vs {A}"
bym=collections.defaultdict(dict)
def mname_of(s): return norm(s) or (s['marketDescription']+(' '+s['marketSpecifiers'].split('=')[-1] if s.get('marketSpecifiers') else '')+': '+s['outcomeDescription'])
for k,cs in selC.items(): mkC[mname_of(info[k])]|=cs
for k,n in sel.items():
  if n<HOT or str(k[1]) in ('10','60110'): continue
  s=info[k]; m=norm(s)
  if not m: continue
  e=k[0]; cur=bym[m].get(e)
  if cur and (sel[cur],w[cur])>=(n,w[k]): continue
  bym[m][e]=k
MO=['Home win','Away win','Draw','Draw no bet','Over 0.5 goals','Over 1.5 goals','Over 2.5 goals','Over 3.5 goals','Under 2.5 goals','Under 3.5 goals','Under 4.5 goals','Both teams to score','Both teams to score: No','Home team over 0.5','Home team over 1.5','Away team over 0.5','Away team over 1.5','1st half home win','1st half away win','1st half draw','1st half over 0.5','1st half over 1.5','2nd half over 0.5','2nd half over 1.5']
byMarket=[]
for m,evs in bym.items():
  if len(mkC[m])<HOT: continue
  L=[]
  for e,k in evs.items():
    s=info[k]; t=dt.datetime.fromtimestamp(s['startTime']/1000,dt.timezone.utc)
    L.append(dict(eventId=e,marketId=k[1],specifier=k[2] or None,outcomeId=k[3],odds=float(s['odds']),
      match=f"{s['homeTeamName']} vs {s['awayTeamName']}",team=tlabel(s,m),market=m,selection=f"{m}: {s['outcomeDescription']}",
      date=t.date().isoformat(),ko=t.strftime('%H:%M'),start=t.isoformat(),count=sel[k],backing=w[k]))
  L=_pass(L)
  if not L: continue
  L.sort(key=lambda p:(-p['count'],-p['backing'])); L=L[:30]
  sl=slip('Hot by market: '+m,L); sl['market']=m; sl['picks']=L; sl['backed']=len(mkC[m])
  byMarket.append(sl)
byMarket.sort(key=lambda x:(MO.index(x['market']) if x['market'] in MO else 99,-x['backed']))
prev.update({x['name']:x for x in (json.load(open(OUT)).get('byMarket',[])+json.load(open(OUT)).get('byTeam',[]) if os.path.exists(OUT) else [])})
byTeam=[]
for tm,n in teams.most_common():
  if n<HOT: break
  bestk={}
  for k,c in sel.items():
    s=info[k]
    if c<HOT or str(k[1]) in ('10','60110') or not norm(s) or tm not in (s['homeTeamName'],s['awayTeamName']): continue
    if k[0] not in bestk or (c,w[k])>(sel[bestk[k[0]]],w[bestk[k[0]]]): bestk[k[0]]=k
  if not bestk: continue
  L=[]
  for e,k in bestk.items():
    s=info[k]; t=dt.datetime.fromtimestamp(s['startTime']/1000,dt.timezone.utc)
    L.append(dict(eventId=e,marketId=k[1],specifier=k[2] or None,outcomeId=k[3],odds=float(s['odds']),
      match=f"{s['homeTeamName']} vs {s['awayTeamName']}",team=tm,market=mname_of(s),selection=f"{mname_of(s)}: {s['outcomeDescription']}",
      date=t.date().isoformat(),ko=t.strftime('%H:%M'),start=t.isoformat(),count=sel[k],backing=w[k]))
  L=_pass(L)
  if not L: continue
  L.sort(key=lambda p:(-p['count'],-p['backing']))
  sl=slip('Hot team: '+tm,L); sl['team']=tm; sl['picks']=L; sl['backed']=n; byTeam.append(sl)
ALLB=set(BOOK)
full=lambda x:ALLB<=set(k for k,v in (x.get('codes') or {}).items() if v)
print('dropped incomplete byMarket',[x['name'] for x in byMarket if not full(x)],'byTeam',sum(1 for x in byTeam if not full(x)))
byMarket=[x for x in byMarket if full(x)]; byTeam=[x for x in byTeam if full(x)]
out=dict(hotRule=HOT,maxDays=MAXDAYS,mainNote=mainNote,byTeam=byTeam,updatedAt=now.isoformat(timespec='seconds'),codesAnalysed=len(codes),selectionsAnalysed=sum(sel.values()),
  picks=picks[:60],markets=[dict(name=x['market'],count=x['backed']) for x in byMarket],teams=[dict(name=x['team'],count=x['backed']) for x in byTeam],slips=slips,byMarket=byMarket)
out['sectionMasters']=HSM.build_section_masters(out, slip, pass_fn=_pass, today=now.date().isoformat(), engine_dir=str(__import__('pathlib').Path(D).resolve().parent))
json.dump(out,open(OUT,'w'),indent=1,ensure_ascii=False)
json.dump(_hdrop,open(os.path.join(D,'hot_dropped.json'),'w'),indent=1,ensure_ascii=False)
print('codes',len(codes),'hotSelections',len(picks),'hotSelAll',sum(1 for v in sel.values() if v>=HOT),'markets',len(byMarket),'teams',len(byTeam),'mainOdds',round(mainOdds,2),'sectionMasters',len(out.get('sectionMasters') or []))
