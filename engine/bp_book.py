"""Betpawa Ghana: public no-login booking (POST /api/sportsbook/v3/booking-number). Events matched to our
Betradar ids via the SPORTRADAR widget id on Betpawa's public search; markets mapped by type + handicap(=line*4)."""
import json,subprocess,math,re,urllib.parse
B='https://www.betpawa.com.gh/api/sportsbook/'
HD=['-A','Mozilla/5.0 Chrome/120','-H','x-pawa-brand: betpawa-ghana','-H','x-pawa-language: en','-H','devicetype: web','-H','Accept: application/json','-H','Content-Type: application/json']
def call(m,u,body=None):
  c=['curl','-s','-m','25']+HD+['-X',m,B+u]
  if body is not None: c+=['-d',json.dumps(body)]
  try: return json.loads(subprocess.run(c,capture_output=True,text=True).stdout)
  except Exception: return {}
MK={'1':('3743',None,{'1':'1','2':'X','3':'2'}),'10':('4693',None,{'9':'1X','10':'12','11':'X2'}),'11':('4703',None,{'4':'1','5':'2'}),
    '18':('5000','t',{'12':'Over','13':'Under'}),'19':('5006','t',{'12':'Over','13':'Under'}),'20':('5003','t',{'12':'Over','13':'Under'}),
    '68':('4958','t',{'12':'Over','13':'Under'}),'29':('3795',None,{'74':'Yes','76':'No'})}
_ev={};_full={}
def find_event(p):
  sr=p['eventId'].split(':')[-1]
  if sr in _ev: return _ev[sr]
  teams=re.split(r'\s+v(?:s)?\s+',p.get('match',''))
  qs=[]
  for t in teams:
    w=[x for x in re.split(r'\W+',t) if len(x)>2 and x.lower() not in ('fc','club','cd','sc','ac','afc','cf','real','united','city','sporting','atletico','deportivo')]
    qs+= [t]+sorted(w,key=len,reverse=True)[:2]
  for q in qs:
    r=call('GET','v3/search?name='+urllib.parse.quote(q))
    for e in r.get('events') or []:
      if any(w.get('type')=='SPORTRADAR' and str(w.get('id'))==sr for w in e.get('widgets') or []):
        _ev[sr]=e['id']; return e['id']
  _ev[sr]=None; return None
def price(p):
  m=MK.get(str(p.get('marketId')))
  if not m: return None
  eid=find_event(p)
  if not eid: return None
  if eid not in _full: _full[eid]=call('GET','v4/events/'+eid)
  want=m[2].get(str(p.get('outcomeId')))
  h=None
  if m[1]:
    mm=re.search(r'total=([\d.]+)',p.get('specifier') or '')
    if not mm: return None
    h=round(float(mm.group(1))*4)
  for mk in _full[eid].get('markets') or []:
    if mk['marketType']['id']!=m[0]: continue
    for r in mk['row']:
      if h is not None and r.get('handicap')!=h: continue
      for pr in r['prices']:
        if pr['name']==want and not pr.get('suspended') and (pr.get('odds') or 0)>1: return pr['id'],pr['odds']
  return None
def book(L):
  """returns dict(code,totalOdds,legs,matches) or None"""
  S=[];ids=[];od=[]
  for p in L:
    x=price(p)
    if x and p['eventId'] not in ids: S.append(x[0]);od.append(x[1]);ids.append(p['eventId'])
  if not S: return None
  r=call('POST','v3/booking-number',{'selections':{'selections':[{'type':'COMBO' if len(S)>1 else 'SINGLE','selections':S}]}})
  code=r.get('code')
  if not code: return None
  v=call('GET','v3/booking-number/'+code).get('items') or []
  n=sum(len(i.get('selections') or []) for i in v) or len(S)
  return dict(code=code,totalOdds=round(math.prod(od),2),legs=n,matches=ids,link='https://www.betpawa.com.gh/share-betslip/'+code)
