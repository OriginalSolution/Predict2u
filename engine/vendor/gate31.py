# Unified Oct 28 final gate: every strategy's legs pass the same standing rules before booking.
# Path-resolved for GitHub Actions: gate modules live in engine/gates/; snapshot JSONs
# soft-load (empty defaults) so hard vetoes still apply without box-only /workspace/novDD.
import json,re,sys,collections,os
from pathlib import Path as _P
_GATES=_P(os.environ.get('ENGINE_GATES_DIR') or (_P(__file__).resolve().parents[1]/'gates'))
for _p in (_GATES, _P(__file__).resolve().parent):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))
from _gate_data import load_json, find_file
import rules31 as R, flowrules as FR
from rulebook import viol
D=load_json('graded31.json', {})
SB=load_json('sbcombo31.json', {})
_X=load_json('mgst31.json', {})
MG=_X.get('MG') if isinstance(_X, dict) else {}
ST=_X.get('ST') if isinstance(_X, dict) else {}
if not isinstance(MG, dict): MG={}
if not isinstance(ST, dict): ST={}
_fx=load_json('fx31dc.json', [])
FX={f['eid']:f for f in (_fx or []) if isinstance(f, dict) and 'eid' in f}
OSM=(load_json('osm2_booked.json', {}) or {}).get('fired', {}) if True else {}
if not isinstance(OSM, dict): OSM={}
TH=load_json('market_thresholds_by_league.json', {})
LC={'Argentina Primera LPF':'ARG','Austria Bundesliga':'AUT','Belgium Pro League':'B1','Brazil Brasileiro Serie A':'BRA','China Super League':'CHN','Germany Bundesliga':'D1','Germany 2. Bundesliga':'D2','Denmark Superliga':'DNK',
 'England Premier League':'E0','England Championship':'E1','England League One':'E2','England League Two':'E3','England National League':'EC','France Ligue 1':'F1','France Ligue 2':'F2','Finland Veikkausliiga':'FIN','Greece Super League':'G1',
 'Italy Serie A':'I1','Italy Serie B':'I2','Ireland Premier Division':'IRL','Japan J1 League':'JPN','Mexico Liga MX':'MEX','Netherlands Eredivisie':'N1','Norway Eliteserien':'NOR','Portugal Liga Portugal':'P1','Poland Ekstraklasa':'POL',
 'Romania Superliga':'ROU','Russia Premier League':'RUS','Scotland Premiership':'SC0','Scotland Championship':'SC1','Scotland League One':'SC2','Scotland League Two':'SC3','Spain LaLiga':'SP1','Spain LALIGA HYPERMOTION':'SP2','Sweden Allsvenskan':'SWE','Switzerland Super League':'SWZ','Turkiye Super Lig':'T1','USA MLS':'USA'}
def _sp(key):
  a=key.split('|');return a[0],'|'.join(a[1:-1]),a[-1]  # Oct 31: Early Goals spec contains '|'
def ppg(e):
  m=MG.get(e)
  if not isinstance(m,dict) or 'teams' not in m:return None
  t=ST.get(str(m.get('_seasonid')))
  if not isinstance(t,dict):return None
  hu,au=m['teams']['home']['uid'],m['teams']['away']['uid']
  for tb in t.get('tables',[]):
    P={r['team']['uid']:r['pointsTotal']/r['total'] for r in tb.get('tablerows',[]) if r.get('total')}
    if hu in P and au in P:return P[hu],P[au]
def O(e):
  f=FX.get(e);return {k:v for k,v in (f or {}).get('O',{}).items()}
def mism(e):
  o=O(e);fav=min([o[k][0] for k in ('1||Home','1||Away') if k in o] or [9]);pp=ppg(e);why=[]
  if fav<=1.50:why.append(f"fav 1X2 {fav}")
  if pp:
    h,a=pp
    if abs(h-a)>=1.0:why.append(f"PPG gap {h:.2f} v {a:.2f}")
    elif (h>=1.9 and a<1.0) or (a>=1.9 and h<1.0):why.append(f"PPG {h:.2f} v {a:.2f}")
  return why
def mkind(key,pk):
  mid,spec,oc=_sp(key);p=pk.lower()
  if mid in('19','20') or 'team' in p or any(w in p for w in('1st','2nd','half','corner','card','booking','shot','offside','foul')):return None
  if 'under 3.5' in p or (mid in('18','60180') and 'total=3.5' in spec and oc.startswith('Under')):return 'U35'
  if 'over 1.5' in p or (mid in('18','60180') and 'total=1.5' in spec and oc.startswith('Over')):return 'O15'
def fam(key,pk):
  mid,spec,oc=_sp(key);p=(pk+' '+oc).lower()
  if mid in('18','60180') and 'total=' in spec:
    t=re.search(r'total=([\d.]+)',spec).group(1);return ('O' if oc.startswith('Over') else 'U')+t  # Oct 31 fix: Early Goals spec is 'minsnr=30|total=X'
  if mid=='29':return 'GG' if oc=='Yes' else 'NG'
  if mid in('1','60200','60100'):return {'Home':'HW','Away':'AW','Draw':'D'}.get(oc,'?')
  if mid=='10':return {'Home or Draw':'1X','Draw or Away':'X2','Home or Away':'12'}.get(oc)
  if mid=='11':return {'Home':'HDNB','Away':'ADNB'}.get(oc)
  if mid=='19' and oc.startswith('Over'):return 'HT+'
  if mid=='20' and oc.startswith('Over'):return 'AT+'
  return None
OVERS={'O0.5','O1.5','O2.5','O3.5','GG'};UNDERS={'U2.5','U3.5','U4.5','U1.5'}
def osm(e,f):
  fired=set(OSM.get(e,[]))
  if not fired or not f:return None,None
  under_b={'Under 2.5','U2.5','Under 3.5','U3.5'} & fired;over_b={'Over 1.5','O1.5','O2.5','GG'} & fired
  home_b={'1X','Home DNB','Home win'} & fired;away_b={'X2','Away DNB','Away win'} & fired
  if (f in OVERS and under_b):return 'Odds Signal Map clash: league trigger fired '+','.join(under_b),None
  if (f in UNDERS and over_b):return 'Odds Signal Map clash: league trigger fired '+','.join(over_b),None
  if f in('HW','HDNB','1X') and away_b or f in('AW','ADNB','X2') and home_b:return 'Odds Signal Map clash (opposite side)',None
  return None,'Odds Signal Map boost: league trigger fired '+','.join(sorted(fired))
THM={'O1.5':'Over 1.5','O2.5':'Over 2.5','U2.5':'Under 2.5','U3.5':'Under 3.5','GG':'BTTS Yes','HW':'Home win','AW':'Away win','HDNB':'Home DNB','ADNB':'Away DNB'}
def lthresh(e,lg,f,price):
  c=LC.get(lg);mk=THM.get(f)
  if not c or not mk or c not in TH:return None
  r=TH[c].get(mk+' (odds>=1.20)') or TH[c].get(mk)
  if not r:return None
  g=D.get(e);o=O(e)
  if not g or 'err' in g:return None
  x=R.Ctx(e,g,SB)
  F=dict(oH=(o.get('1||Home') or [None])[0],oD=(o.get('1||Draw') or [None])[0],oA=(o.get('1||Away') or [None])[0],oO=(o.get('18|total=2.5|Over 2.5') or [None])[0],mo=price,
    hPPG=x.vppg('h'),aPPG=x.vppg('a'),hGF=x.vgf('h'),hGA=x.vga('h'),aGF=x.vgf('a'),aGA=x.vga('a'),xg=x.xg())
  F['gap']=(F['hPPG'] or 0)-(F['aPPG'] or 0)
  ok=True
  for cl in r['rule'].split(' AND '):
    m_=re.match(r'(\w+) (<=|>=) ([\d.\-]+)',cl.strip())
    if not m_ or F.get(m_.group(1)) is None:return None
    v=F[m_.group(1)];t=float(m_.group(3));ok&=(v<=t if m_.group(2)=='<=' else v>=t)
  return (f"league threshold {c} {mk} [{r['label']}] {r['rule']}: {'MET' if ok else 'not met'} (league test {r['test_hit']}% n {r['test_n']}, base {r['base_train']}%)",ok,r['label'])
LTH={'O1.5':.75,'O2.5':.55,'U2.5':.55,'O3.5':.40,'U1.5':.30,'U3.5':.70,'U4.5':.85}
def lrate(e,f):
  if f not in LTH:return None,0
  s=str(MG.get(e,{}).get('_seasonid'));v=FR.LR.get(s) or {};G=v.get('cur') or []
  if len(G)<30 and v.get('prev'):G=G+v['prev']
  if len(G)<30:return None,len(G)
  ln=float(f[1:]);return sum((a+b>ln) if f[0]=='O' else (a+b<ln) for a,b in G)/len(G),len(G)
def worst_of(e,key):
  g=D.get(e)
  if not g or 'err' in g:return None
  mid,spec,oc=_sp(key)
  for c in g['cands']:
    if c['mid']==mid and (c['spec'] or '')==spec and c['oc']==oc:return c
CUPX=re.compile(r'cup|copa|pokal|puchar|pohar|coupe|coppa|ta[cç]a|beker|trophy|champions(?!hip)|libertadores|sudamericana|conference|europa|knockout|play-?off|super cup|\bMLS\b|major league soccer|\bUSL\b|canadian premier|liguilla|reducido|play-?offs?\b',re.I)  # P10 (approved Nov 2): league play-offs = cup games
WOM=re.compile(r'women|\(w\)|\bw\b|femin|lebring',re.I)
def gate(e,m,lg,key,pk,price,w=None,mode='main',need_grade=True,skip_check=False,allow_hi=False,ggband=False):
  r_=_gate(e,m,lg,key,pk,price,w,mode,need_grade,skip_check)
  if r_[0]:return r_
  why,notes,w=r_
  if WOM.search(lg+' '+m):return 'STRICT: women/Lebring',notes,w
  if price>1.50 and not allow_hi:return f'STRICT: price {price} > 1.50 cap',notes,w
  if w is None:return 'STRICT: no stats',notes,w
  if CUPX.search(lg) and w<0.85:return f'STRICT: cup leg worst {w:.0%} < 85%',notes,w
  tf=tbff(e,lg,key,pk,price,w,ggband)
  if tf:return tf,notes,w
  return None,notes,w
# Late Oct 26 run: trend-breaker filters (/workspace/rules/trend_breaker_filters.md, user-approved Oct 26) and
# league_market_rules.md FAIL FLAGS (odds-band x league x market study, user-approved Oct 26) applied in the shared gate = every section.
YRX=re.compile(r'youth|u1\d|u2[0-3]|reserve|(?<!willem)(?<!nb)\sii$| b$|primavera|academy',re.I)
def tbff(e,lg,key,pk,price,w,ggband=False):
  mid,spec,oc=_sp(key);f=fam(key,pk);k=mkind(key,pk);o=O(e)
  oH=(o.get('1||Home') or [None])[0];oD=(o.get('1||Draw') or [None])[0];oA=(o.get('1||Away') or [None])[0]
  # Oct 27 FH-15: no 2H Over 0.5 when match O2.5 >=1.70 (see rules31.check)
  if mid=='90' and spec=='total=0.5' and oc=='Over 0.5':
    _o25=(o.get('18|total=2.5|Over 2.5') or [None])[0]
    if _o25 is None or _o25>1.60:return f'NEW FH-15: no 2H Over 0.5 when match O2.5 is {_o25} (needs <=1.60, P5)'
  # DRAW>4.50 RULE (user Oct 28 06:18 GMT): no Over 1.5 / Over 2.5 when draw > 4.50 (favourite instead)
  if (k=='O15' or f in('O1.5','O2.5')) and oD and oD>4.50:return f'DRAW>4.50: no Overs with draw {oD} (book favourite instead)'
  # U3.5>1.40 FILTER (user Oct 28): match Over 1.5 only when match Under 3.5 is priced above 1.40
  if (k=='O15' or f=='O1.5'):
    _u35=(o.get('18|total=3.5|Under 3.5') or [None])[0]
    if _u35 is None or _u35<=1.40:return f'U3.5 FILTER: no Over 1.5 when Under 3.5 is {_u35} (needs >1.40)'
  # trend-breaker 1: no Over 1.5 when the 1X2 draw price is under 3.40
  if (k=='O15' or f=='O1.5') and oD and oD<3.40:return f'TREND-BREAKER: no Over 1.5 with draw {oD} < 3.40'
  # trend-breaker 2: no favourite win at 1.50 or shorter when the PPG gap is under 0.30
  if f in('HW','AW') and oH and oA:
    favside='HW' if oH<=oA else 'AW';favp=min(oH,oA)
    if f==favside and favp<=1.50:
      pp=ppg(e)
      if pp and abs(pp[0]-pp[1])<0.30:return f'TREND-BREAKER: fav win <=1.50 with PPG gap {abs(pp[0]-pp[1]):.2f} < 0.30'
    if f==favside and favp>1.80:return f'FAIL FLAG: favourite win priced {favp} > 1.80'
  # trend-breaker 3: skip 1st v 2nd for double chance
  if f in('1X','X2') or mid in('10','60110'):
    st,txt=FR.standings(e)
    if txt and re.search(r'overall (1 v 2|2 v 1)\b',txt):return 'TREND-BREAKER: no DC on 1st v 2nd'
  # fail flag: result pick when both sides are priced above 2.20
  if (f in('HW','AW','1X','X2','HDNB','ADNB') or mid in('10','11','60110')) and oH and oA and oH>2.20 and oA>2.20:return f'FAIL FLAG: result pick with both sides >2.20 ({oH}/{oA})'
  # fail flag: Over 2.5 except Bundesliga / Super Lig with fav <=1.30
  if f=='O2.5' or (mid=='60180' and 'total=2.5' in spec and oc.startswith('Over')):
    favp=min([x for x in(oH,oA) if x] or [9])
    if not(re.search(r'Germany Bundesliga$|Turkiye Super Lig|Turkey Super Lig',lg) and favp<=1.30):return 'FAIL FLAG: Over 2.5 (only Bundesliga/Super Lig fav <=1.30 allowed)'
  # fail flag: GG only through the GG band rule's own filters + 75% stats
  if f=='GG' and not ggband:return 'FAIL FLAG: GG only via the O2.5 1.60-1.69 GG band rule'
  # fail flag: Under 3.5 needs 80%+ worst-sample team stats
  if (k=='U35' or f=='U3.5') and (w is None or w<0.80):return f'FAIL FLAG: Under 3.5 needs worst 80%+ (has {0 if w is None else w:.0%})'
  # DC/DNB never on youth/reserve (DC4)
  if (f in('1X','X2','HDNB','ADNB') or mid in('10','11')) and YRX.search(lg+' '+(FX.get(e) or {}).get('home','')+' '+(FX.get(e) or {}).get('away','')):return 'DC4: no DC/DNB in youth/reserve'
  return None
def _gate(e,m,lg,key,pk,price,w=None,mode='main',need_grade=True,skip_check=False):
  notes=[];mid,spec,oc=_sp(key);f=fam(key,pk)
  if mid in ('10','60110') or f in ('1X','X2','12') or re.search(r'double\s*chance',pk,re.I):return 'HARD VETO: no double chance (1X, X2 or 12)',notes,w
  if 'lebring' in (m+lg).lower():return 'NO-LEBRING',notes,w
  if mid=='29' and oc=='No':return 'BTTS No banned',notes,w
  if f=='12' or (mid in('10','60110') and oc=='Home or Away'):return 'NO HOME OR AWAY (12) banned',notes,w
  if price<1.20:return f'price {price} < 1.20 (bump rule: needs a 1.20+ stronger line)',notes,w
  t5=R.top5(e)
  if t5:return f'top-5 v top-5 ({t5})',notes,w
  st,txt=FR.standings(e)
  if st and ('TOP' in st or 'BOTTOM' in st):return st,notes,w
  mm=mism(e);k=mkind(key,pk)
  # Skip mismatch filter when this event has no fixture/standings cache (Actions soft-load).
  _has_fx=(e in FX) or (e in MG)
  if _has_fx:
    if k=='U35' and mm:return 'MISMATCH: no Under 3.5 on a mismatch ('+'; '.join(mm)+')',notes,w
    if k=='O15' and not mm:return 'MISMATCH: Over 1.5 only on a mismatch (teams even)',notes,w
    notes.append('mismatch: '+'; '.join(mm) if mm else 'teams even')
  else:
    notes.append('mismatch: n/a (no fixture cache)')
  v=viol(lg,pk if not pk.startswith(('Over/Under: ','Over/Under - Early Goals: ')) else pk.split(': ',1)[1])
  if v:return v,notes,w
  c=worst_of(e,key)
  if c is not None:
    w=c['worst'] if w is None else min(w,c['worst'])
    if not skip_check:
      g=D[e];x=R.Ctx(e,g,SB);cc=dict(c);cc['p']=price;why=R.check(cc,x,mode)
      if why:return why,notes,w
  elif need_grade and w is None:return 'no graded stat sample for this market',notes,w
  if w is not None and w<0.75:return f'market stats worst sample {w:.0%} < 75%',notes,w
  lr,n=lrate(e,f)
  if f in LTH:
    if lr is None:notes.append(f'league season rate n/a (n={n})')
    elif lr<LTH[f]:return f"league's own season {f} rate {lr:.0%} (n {n}) < {LTH[f]:.0%}",notes,w
    else:notes.append(f"league season {f} {lr:.0%} of {n}")
  cl,boost=osm(e,f)
  if cl:return cl,notes,w
  if boost:notes.append(boost)
  th=lthresh(e,lg,f,price)
  if th:notes.append(th[0])
  return None,notes,w
