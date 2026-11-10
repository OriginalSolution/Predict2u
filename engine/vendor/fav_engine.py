BANDS=[(1.0, 1.35, '1.20-1.35'), (1.35, 1.5, '1.36-1.50'), (1.5, 1.7, '1.51-1.70'), (1.7, 2.0, '1.71-2.00'), (2.0, 2.4, '2.01-2.40')]
def bandof(p):
  for lo,hi,nm in BANDS:
    if lo<p<=hi: return nm
import json,re,os,sys,time,subprocess,collections,math,csv,concurrent.futures as cf
import os as _os, sys as _sys; _sys.path.insert(0, _os.environ.get('ENGINE_DIR', str(__import__('pathlib').Path(__file__).resolve().parents[1]))); _sys.path.insert(0, _os.environ.get('VENDOR_DIR', str(__import__('pathlib').Path(__file__).resolve().parent)));from sb_share_helper17 import UA
SR="https://stats.fn.sportradar.com/sportybet/en/Europe:Berlin/gismo/"
def curl(u):
  for i in range(3):
    try:return json.loads(subprocess.run(['curl','-s','-m','30','-A',UA,u],capture_output=True,text=True).stdout)
    except Exception:time.sleep(1)
def G(p):
  f=(__import__('os').environ.get('STATS_CACHE', str(__import__('pathlib').Path(__file__).resolve().parents[1]/'data'/'stats-cache'))+'/').replace('//','/') if False else (__import__('os').environ.get('STATS_CACHE') or str(__import__('pathlib').Path(__file__).resolve().parents[1]/'data'/'stats-cache')) + '/'+p.replace('/','_')+'.json'
  if os.path.exists(f):
    d=json.load(open(f))
    if d is not None: return d
  d=curl(SR+p);d=d['doc'][0]['data'] if d and 'doc' in d and d['doc'][0].get('event')!='exception' else None
  json.dump(d,open(f,'w'));return d
E=json.load(open(os.environ.get('SBJSON', os.path.join(os.environ.get('RESEARCH_DIR', os.path.dirname(os.path.abspath(__file__))), 'sb.json'))));now=max(time.time()*1000+15*60000,float(os.environ['WSTART']))
YOUTH=re.compile(r'U\d\d\b|U-\d\d|Res\.|Reserve|Jong |Next Gen|Women|Primavera|Youth|Femen|Futures|Simulated|SRL|Esoccer|Academy',re.I)
TEAMX=re.compile(r'\bII\b|\b2$|\bB$|\bW$')  # B/2/W/II suffixes only on team names (a 'Serie B' tournament is a senior league)
P=[e for e in E.values() if now<e['estimateStartTime']<float(os.environ['WEND'])]
EXC={}
P2=[]
for e in P:
  nm=e['homeTeamName']+' v '+e['awayTeamName']
  if YOUTH.search(nm+'|'+e['sport']['category']['tournament']['name']) or TEAMX.search(e['homeTeamName'].strip()) or TEAMX.search(e['awayTeamName'].strip()): EXC[nm]='youth/reserve/women/virtual'
  else: P2.append(e)
P=P2;print('fixtures',len(P))
with cf.ThreadPoolExecutor(6) as x: MI=list(x.map(lambda e:G('match_info/'+e['eventId'].split(':')[-1]),P))
def lastx(u): return G(f'stats_team_lastx/{u}/60') or {}
# seasons per utid: current + previous from teams' history
SEAS=collections.defaultdict(set)
for m in MI:
  if not m or 'match' not in m or '_seasonid' not in m['match']: continue
  mm=m['match'];ut=mm['_utid'] if '_utid' in mm else (m.get('uniquetournament') or {}).get('_id');SEAS[ut].add(mm['_seasonid'])
  for side in('home','away'):
    for z in lastx(mm['teams'][side]['uid']).get('matches',[]):
      if z.get('_utid')==ut and z.get('_seasonid'): SEAS[ut].add(z['_seasonid'])
allS={s for v in SEAS.values() for s in v}
with cf.ThreadPoolExecutor(6) as x: FX=dict(x.map(lambda s:(s,G(f'stats_season_fixtures2/{s}')),allS))
SEASTATE={}
def model(gh_,ga_):
  # Poisson model price (fair 1X2 odds) from each side's season goals for/against so far; needs >=3 games each
  if gh_[2]<3 or ga_[2]<3: return None
  lh=max(0.2,(gh_[0]/gh_[2]+ga_[1]/ga_[2])/2*1.12);la=max(0.2,(ga_[0]/ga_[2]+gh_[1]/gh_[2])/2*0.9)
  ph=[math.exp(-lh)*lh**k/math.factorial(k) for k in range(11)];pa=[math.exp(-la)*la**k/math.factorial(k) for k in range(11)]
  H=sum(ph[i]*pa[j] for i in range(11) for j in range(i));D=sum(ph[i]*pa[i] for i in range(11));A=max(1e-6,1-H-D)
  return (1/H,1/D,1/A)
def rows_sr(ut):
  ss=sorted(SEAS[ut],key=lambda s:-int(s))[:3];R=[]
  for s in ss:
    d=FX.get(s)
    if not d: continue
    ms=sorted([m for m in d.get('matches',[]) if (m.get('result') or {}).get('home') is not None and m['time']['uts']<time.time()],key=lambda m:m['time']['uts'])
    pts=collections.defaultdict(lambda:[0,0]);gls=collections.defaultdict(lambda:[0,0,0])
    for m in ms:
      h,a=m['teams']['home']['uid'],m['teams']['away']['uid'];gh,ga=m['result']['home'],m['result']['away']
      fav=None;band=None
      if pts[h][1]>=3 and pts[a][1]>=3:
        dh,da=pts[h][0]/pts[h][1]+0.3,pts[a][0]/pts[a][1]
        dd=abs(dh-da)
        if dd>=0.15: fav='H' if dh>da else 'A';band='1.20-1.35' if dd>=1.2 else '1.36-1.50' if dd>=0.9 else '1.51-1.70' if dd>=0.6 else '1.71-2.00' if dd>=0.35 else '2.01-2.40'
      R.append(dict(gh=gh,ga=ga,fav=fav,band=band,season=s,x=model(gls[h],gls[a])))
      for t,g1,g2 in((h,gh,ga),(a,ga,gh)): pts[t][0]+=3 if g1>g2 else 1 if g1==g2 else 0;pts[t][1]+=1;gls[t][0]+=g1;gls[t][1]+=g2;gls[t][2]+=1
    SEASTATE[s]=gls
  return R,len(ss),'PPG proxy'
def rows_fd(files,season_filter=None):
  R=[]
  for f in files:
    for r in csv.DictReader(open(f,encoding='utf-8-sig',errors='ignore')):
      if season_filter and r.get('Season') not in season_filter: continue
      try:
        gh=int(r.get('FTHG') or r.get('HG'));ga=int(r.get('FTAG') or r.get('AG'))
        oh=float(r.get('AvgCH') or r.get('PSCH') or r.get('B365CH') or r.get('AvgH'));oa=float(r.get('AvgCA') or r.get('PSCA') or r.get('B365CA') or r.get('AvgA'))
      except Exception: continue
      fp=min(oh,oa);fav='H' if oh<oa else 'A'
      band=bandof(fp)
      try: odr=float(r.get('AvgCD') or r.get('PSCD') or r.get('B365CD') or r.get('AvgD'))
      except Exception: odr=None
      R.append(dict(gh=gh,ga=ga,fav=fav if band else None,band=band,x=(oh,odr,oa) if odr else None))
  return R
FD={'England - Championship':(['mmz4281_2627_E1.csv','mmz4281_2526_E1.csv','mmz4281_2425_E1.csv'],None),'England - League One':(['mmz4281_2627_E2.csv','mmz4281_2526_E2.csv','mmz4281_2425_E2.csv'],None),'Brazil - Brasileiro Serie A':(['new_BRA.csv'],{'2024','2025','2026'}),'Argentina - Primera LPF':(['ARG.csv'],{'2024','2025','2026'}),'Belgium - Pro League':(['mmz4281_2627_B1.csv','mmz4281_2526_B1.csv','mmz4281_2425_B1.csv'],None)}
def profile(R):
  n=collections.Counter();c=collections.Counter()
  for r in R:
    gh,ga=r['gh'],r['ga'];n['all']+=1
    for k,v in(('hw',gh>ga),('hnl',gh>=ga),('hcs',ga==0),('aw',ga>gh),('anl',ga>=gh),('o25',gh+ga>=3),('u25',gh+ga<=2),('u35',gh+ga<=3)): c[k]+=v
    if r['fav']:
      ff,fa=(gh,ga) if r['fav']=='H' else (ga,gh)
      for b in(r['band'],'fall'):
        n[b]+=1
        for k,v in(('w',ff>fa),('nl',ff>=fa),('cs',fa==0),('wtn',ff>fa and fa==0),('o25',ff+fa>=3),('u25',ff+fa<=2),('u35',ff+fa<=3),('os',fa>0)): c[b+'_'+k]+=v
  return n,c
BMK=('hw','d','aw','fw','1X','X2','12','o15','o25','u25','u35','btts','nobtts','o05','o35','u45','hg','ag','dnbH','dnbA')
def isbal(x):
  pH,pA=1/x[0],1/x[2];t=1/x[0]+1/x[1]+1/x[2];return min(x[0],x[2])>=2.10 or abs(pH-pA)/t<0.12
def bprofile(R):
  X=[r for r in R if r.get('x')];
  if len(X)<40: return None
  ds=sorted(r['x'][1] for r in X);lo,hi=ds[len(ds)//3],ds[2*len(ds)//3]
  out=dict(cut=dict(drawLow=round(lo,2),drawHigh=round(hi,2)),n=len(X),b={})
  for r in X:
    gh,ga=r['gh'],r['ga'];fh=r['x'][0]<=r['x'][2]
    v=dict(hw=gh>ga,d=gh==ga,aw=ga>gh,fw=(gh>ga) if fh else (ga>gh),o15=gh+ga>=2,o25=gh+ga>=3,u25=gh+ga<=2,u35=gh+ga<=3,btts=gh>0 and ga>0,nobtts=gh==0 or ga==0)
    v['1X']=gh>=ga;v.update(o05=gh+ga>=1,o35=gh+ga>=4,u45=gh+ga<=4,hg=gh>=1,ag=ga>=1,dnbH=gh>ga,dnbA=ga>gh);v['X2']=ga>=gh;v['12']=gh!=ga
    bb='bal' if isbal(r['x']) else 'unbal';db='lowD' if r['x'][1]<=lo else 'highD' if r['x'][1]>=hi else 'midD'
    for k in (bb,db,bb+'+'+db):
      z=out['b'].setdefault(k,dict(n=0,**{m:0 for m in BMK}));z['n']+=1
      for m in BMK: z[m]+=v[m]
  for z in out['b'].values():
    dn=z['n']-z['d']
    for m in BMK: z[m]=round(z[m]/(dn if m in('dnbH','dnbA') else z['n']),3) if (dn if m in('dnbH','dnbA') else z['n']) else 0
  return out
BPROF={}
BMKT={'hw':('1','','Home','home win','team'),'aw':('1','','Away','away win','team'),'1X':('10','','Home or Draw','home or Draw','team'),'X2':('10','','Draw or Away','draw or away','team'),'12':('10','','Home or Away','home or away','team'),
 'o15':('18','total=1.5','Over 1.5','Over 1.5','tot'),'o25':('18','total=2.5','Over 2.5','Over 2.5','tot'),'u25':('18','total=2.5','Under 2.5','Under 2.5','tot'),'u35':('18','total=3.5','Under 3.5','Under 3.5','tot'),'btts':('29','','Yes','BTTS Yes','tot'),'nobtts':('29','','No','BTTS No','tot'),'d':('1','','Draw','Draw','tot'),'o05':('18','total=0.5','Over 0.5','Over 0.5','tot'),'o35':('18','total=3.5','Over 3.5','Over 3.5','tot'),'u45':('18','total=4.5','Under 4.5','Under 4.5','tot'),'hg':('19','total=0.5','Over 0.5','home over 0.5 goals','team'),'ag':('20','total=0.5','Over 0.5','away over 0.5 goals','team'),'dnbH':('11','','Home','home (draw no bet)','team'),'dnbA':('11','','Away','away (draw no bet)','team')}
BCOND={'hw':lambda f,a:f>a,'aw':lambda f,a:a>f,'1X':lambda f,a:f>=a,'X2':lambda f,a:a>=f,'12':lambda f,a:f!=a,'o15':lambda f,a:f+a>=2,'o25':lambda f,a:f+a>=3,'u25':lambda f,a:f+a<=2,'u35':lambda f,a:f+a<=3,'btts':lambda f,a:f>0 and a>0,'nobtts':lambda f,a:f==0 or a==0,'d':lambda f,a:f==a,'o05':lambda f,a:f+a>=1,'o35':lambda f,a:f+a>=4,'u45':lambda f,a:f+a<=4,'hg':lambda f,a:f>=1,'ag':lambda f,a:a>=1,'dnbH':lambda f,a:f>a if f!=a else None,'dnbA':lambda f,a:a>f if f!=a else None}
NEWMK={tuple(BMKT[k][:3]) for k in ('o05','o35','u45','hg','ag','dnbH','dnbA')}
EV=[]
def ev(e):
  try: return json.loads(subprocess.run(['curl','-s','-m','30','-A',UA,f"https://www.sportybet.com/api/gh/factsCenter/event?eventId={e['eventId']}&productId=3"],capture_output=True,text=True).stdout)['data']
  except Exception: return None
with cf.ThreadPoolExecutor(6) as x: EV=list(x.map(ev,P))
def od(e,mid,sp,desc):
  for m in e.get('markets',[]):
    if str(m['id'])==mid and (m.get('specifier') or '')==sp:
      for o in m['outcomes']:
        if o['desc']==desc and str(o.get('isActive',1))=='1': return m,o
PROFS={};legs=[];NEAR=[];WEAK=[];MC=[]
def persp(z,u):
  r=z.get('result') or {}
  if r.get('home') is None: return None
  h=z['teams']['home']['uid']==u;return dict(f=r['home'] if h else r['away'],a=r['away'] if h else r['home'],home=h,s=f"{r['home']}-{r['away']}")
for m,e in zip(MI,EV):
  if not m or 'match' not in m or '_seasonid' not in m['match'] or not e: EXC[(e or {}).get('homeTeamName','?')]='no data';continue
  nm=e['homeTeamName']+' v '+e['awayTeamName']
  if e.get('matchStatus')!='Not start': EXC[nm]='started';continue
  lg=e['sport']['category']['name']+' - '+e['sport']['category']['tournament']['name']
  mm=m['match'];ut=mm['_utid'] if '_utid' in mm else (m.get('uniquetournament') or {}).get('_id')
  if lg in FD:
    if lg not in PROFS: R=rows_fd(*FD[lg]);PROFS[lg]=(profile(R),'closing odds (football-data.co.uk), 3 seasons');BPROF[lg]=bprofile(R)
  else:
    key=lg
    if key not in PROFS:
      R,ns,src=rows_sr(ut);PROFS[key]=(profile(R),f'PPG proxy, {ns} season(s)');BPROF[key]=bprofile(R)
  (n,c),src=PROFS[lg]
  if n['all']<12: EXC[nm]=f"thin league history (n={n['all']})";continue
  hu,au=mm['teams']['home']['uid'],mm['teams']['away']['uid'];ut0=mm['_dt']['uts']
  try:
    t=G(f"stats_season_tables/{mm['_seasonid']}")['tables'];N=max(len(tb['tablerows']) for tb in t);pos={r['team']['uid']:r['pos'] for tb in t for r in tb['tablerows']}
    hp,ap=pos.get(hu),pos.get(au)
  except Exception: hp=ap=N=None
  if hp and ap and N and N>=10 and ((hp<=5 and ap<=5) or (hp>N-3 and ap>N-3)): EXC[nm]=f'top-5 v top-5 / bottom-3 v bottom-3 ({hp} v {ap}/{N})';continue
  x=[od(e,'1','',k) for k in('Home','Draw','Away')]
  if not all(x): EXC[nm]='no 1X2';continue
  H,D,A=(float(y[1]['odds']) for y in x);fs='H' if H<A else 'A';fp=min(H,A);band=bandof(fp)
  TH=[y for y in (persp(z,hu) for z in sorted(lastx(hu).get('matches',[]),key=lambda z:-z['time']['uts']) if z['time']['uts']<ut0) if y]
  TA=[y for y in (persp(z,au) for z in sorted(lastx(au).get('matches',[]),key=lambda z:-z['time']['uts']) if z['time']['uts']<ut0) if y]
  V=[y for y in (persp(z,hu) for z in (G(f'stats_team_versusrecent/{hu}/{au}') or {}).get('matches',[]) if z['time']['uts']<ut0) if y][:6]
  if len(TH)<6 or len(TA)<6: EXC[nm]='insufficient team form';continue
  fn={'H':e['homeTeamName'],'A':e['awayTeamName']}
  # candidate (rate,n,label,market,cond(f,a) from home persp, sides needing team support)
  C=[]
  def add(rate,nn,label,mk,cond,kind,strat='favourite'): C.append((rate,nn,label,mk,cond,kind,strat))
  if band and n[band]>=12 and not (src.startswith('PPG') and False):
    k=band;nn=n[k];F=fs;fav=fn[F]
    hd=lambda f,a,F=F:(f,a) if F=='H' else (a,f)
    add(c[k+'_w']/nn,nn,f'{fav} to win',('1','','Home' if F=='H' else 'Away'),lambda f,a,hd=hd:hd(f,a)[0]>hd(f,a)[1],'team')
    add(c[k+'_nl']/nn,nn,f'{fav} or Draw',('10','','Home or Draw' if F=='H' else 'Draw or Away'),lambda f,a,hd=hd:hd(f,a)[0]>=hd(f,a)[1],'team')
    add(c[k+'_cs']/nn,nn,f'{fav} clean sheet',('31' if F=='H' else '32','','Yes'),lambda f,a,hd=hd:hd(f,a)[1]==0,'team')
    add(c[k+'_wtn']/nn,nn,f'{fav} win to nil',('33' if F=='H' else '34','','Yes'),lambda f,a,hd=hd:hd(f,a)[0]>hd(f,a)[1] and hd(f,a)[1]==0,'team')
    add(c[k+'_o25']/nn,nn,'Over 2.5 (fav games)',('18','total=2.5','Over 2.5'),lambda f,a:f+a>=3,'tot')
    add(c[k+'_u25']/nn,nn,'Under 2.5 (fav games)',('18','total=2.5','Under 2.5'),lambda f,a:f+a<=2,'tot')
    add(c[k+'_u35']/nn,nn,'Under 3.5 (fav games)',('18','total=3.5','Under 3.5'),lambda f,a:f+a<=3,'tot')
  BP=BPROF.get(lg);bk=None
  if BP:
    if lg in FD: xx=(H,D,A)
    else:
      st=SEASTATE.get(mm['_seasonid'],{});xx=model(st.get(hu,[0,0,0]),st.get(au,[0,0,0]))
    if xx:
      bb='bal' if isbal(xx) else 'unbal';db='lowD' if xx[1]<=BP['cut']['drawLow'] else 'highD' if xx[1]>=BP['cut']['drawHigh'] else 'midD'
      bk=dict(balance=bb,draw=db,price='market' if lg in FD else 'model',x=[round(v,2) for v in xx])
      for key,strat in ((bb+'+'+db,'balance+draw-odds'),(bb,'balance'),(db,'draw-odds')):
        z=BP['b'].get(key)
        if not z or z['n']<12 or 'midD' in key: continue
        for m in BMK:
          if m in ('12','nobtts'): continue  # hard: DC 12 and NG never enter the pool
          if m=='fw':
            if z['fw']>=0.60: m2='hw' if H<A else 'aw'; mi=BMKT[m2];add(z['fw'],z['n'],f"{fn['H' if H<A else 'A']} to win",mi[:3],BCOND[m2],'team',(strat,key,'favourite win'))
            continue
          if z[m]>=0.60:
            mi=BMKT[m];lab=mi[3].replace('home',e['homeTeamName']).replace('away',e['awayTeamName']) if mi[4]=='team' else mi[3]
            add(z[m],z['n'],lab[0].upper()+lab[1:],mi[:3],BCOND[m],mi[4],(strat,key,mi[3]))
  hh=[y for y in TH if y['home']][:10];aa=[y for y in TA if not y['home']][:10]
  def _r(cond,ys,fl):
    v=[cond(y['f'],y['a']) if fl(y) else cond(y['a'],y['f']) for y in ys];v=[x for x in v if x is not None];return (sum(v)/len(v) if v else 0),len(v)
  _seen=set()
  for rate,nn,label,mk,cond,kind,strat in sorted(C,key=lambda t:-t[0]):
    if str(mk[0]) in ('10','60110'): continue  # hard DC veto: try another market
    if rate<0.70 or nn<20 or tuple(mk) in _seen: continue
    o=od(e,*mk)
    if not o or float(o[1]['odds'])<1.03: continue
    rh,nh_=_r(cond,hh,lambda y:True);ra,na_=_r(cond,aa,lambda y:True);rv,nv_=_r(cond,V,lambda y:y['home'])
    if min(rh,ra)<0.6 or (nv_>=3 and rv<0.5): continue
    _seen.add(tuple(mk))
    MC.append(dict(eventId=e['eventId'],match=nm,league=lg,ko=time.strftime('%H:%M',time.gmtime(e['estimateStartTime']/1000)),date=time.strftime('%Y-%m-%d',time.gmtime(e['estimateStartTime']/1000)),
      marketId=str(o[0]['id']),specifier=o[0].get('specifier') or '',outcomeId=str(o[1]['id']),odds=float(o[1]['odds']),selection=label.replace(' (fav games)',''),
      rate=round(rate,3),n=nn,support=round(min(rh,ra),2),h2h=round(rv,2) if nv_ else None,score=round(rate*min(1,math.sqrt(nn/100))*(0.9+0.1*min(rh,ra)),3)))
  best=None;best_relax=None;why=[]
  for rate,nn,label,mk,cond,kind,strat in sorted(C,key=lambda t:-t[0]):
    if str(mk[0])=='29' and str(mk[2]).lower() in ('no','ng'): continue  # hard: never book NG
    is_dc=str(mk[0]) in ('10','60110')
    if is_dc and re.search(r'home or away|\b12\b', str(label)+' '+str(mk[2]), re.I): continue
    if rate<0.60: break
    if tuple(mk) in NEWMK: continue
    o=od(e,*mk)
    if not o or float(o[1]['odds'])<1.10: continue
    if is_dc and float(o[1]['odds'])>1.35: continue  # hard: 1X/X2 above 1.35
    # team-level: home team's home games (home persp) and away team's away games (convert to home persp)
    hh=[y for y in TH if y['home']][:10];aa=[y for y in TA if not y['home']][:10]
    rh=sum(cond(y['f'],y['a']) for y in hh)/max(1,len(hh));ra=sum(cond(y['a'],y['f']) for y in aa)/max(1,len(aa))
    l10h=sum(cond(y['f'],y['a']) if y['home'] else cond(y['a'],y['f']) for y in TH[:10])/10 if kind=='tot' else None
    rv=sum(cond(y['f'],y['a']) if y['home'] else cond(y['a'],y['f']) for y in V)/max(1,len(V))
    if kind=='tot': strict_sup=min(rh,ra)>=0.6; relax_sup=min(rh,ra)>=0.5
    else: strict_sup=rh>=0.6 and ra>=0.6; relax_sup=rh>=0.5 and ra>=0.5
    if len(V)>=3 and rv<0.5: strict_sup=False
    if len(V)>=3 and rv<0.4: relax_sup=False
    row=dict(strat=strat,rate=rate,n=nn,label=label,o=o,rh=rh,ra=ra,nh=len(hh),na=len(aa),rv=rv,nv=len(V))
    # Normal day: 70% hit, 20+ games, 60% team support, and no double chance.
    if (not is_dc) and rate>=0.70 and nn>=20 and strict_sup and best is None:
      best=row; break
    if rate>=0.60 and nn>=12 and relax_sup and best_relax is None:
      best_relax=row
    if not strict_sup: why.append(f"{label}: team {rh:.0%}/{ra:.0%} H2H {rv:.0%}")
  if not best and not best_relax:
    EXC[nm]='no favourite-band or bucket market >=70% (n>=20) with team support'+(f" (e.g. {why[0]})" if why else '');continue
  b=best or best_relax;o=b['o']
  packed=dict(strategy=b['strat'] if isinstance(b['strat'],str) else b['strat'][0],bucket=None if isinstance(b['strat'],str) else b['strat'][1],bucketInfo=bk,fp=fp,band=band,bandn=n[band],bstats={k2:round(c[band+'_'+k2]/n[band],2) for k2 in('w','nl','cs','wtn','o25','u25','u35','os')} if band and n[band] else {},match=nm,league=lg,src=src,ko=time.strftime('%H:%M',time.gmtime(e['estimateStartTime']/1000)),eventId=e['eventId'],marketId=str(o[0]['id']),specifier=o[0].get('specifier') or '',outcomeId=o[1]['id'],odds=float(o[1]['odds']),pick=b['label'],
    rate=round(b['rate'],3),n=b['n'],team=f"{e['homeTeamName']} home {b['rh']:.0%} of {b['nh']}, {e['awayTeamName']} away {b['ra']:.0%} of {b['na']}",h2h=f"{b['rv']:.0%} of {b['nv']} ({[y['s'] for y in V]})",
    table=f"{hp or '?'} v {ap or '?'}/{N or '?'}",x12=f'{H}/{D}/{A}',score=b['rate']*min(1,math.sqrt(b['n']/100))*(1.05 if src.startswith('closing') else 1)*(0.9+0.1*min(b['rh'],b['ra'])))
  if best: legs.append(packed)
  else:
    packed['thinPoolFallback']=True
    NEAR.append(packed)
legs.sort(key=lambda l:-l['score']);NEAR.sort(key=lambda l:-l['score'])
try:
  import thin_pool as _tp
  if _tp.pool_is_thin(legs) and NEAR:
    kept=[]
    for l in NEAR:
      p=dict(marketId=l.get('marketId'),specifier=l.get('specifier'),outcomeId=l.get('outcomeId'),selection=l.get('pick'),odds=l.get('odds'),league=l.get('league'),market=l.get('market') or '',match=l.get('match'))
      if _tp.hard_blocked(p) or not _tp.relaxed_ok(p): continue
      kept.append(l)
    NEAR=kept
    print(f"thin-pool fallback: fav engine stored {len(NEAR)} near-miss leg(s); strict pool {len(legs)}", flush=True)
  elif not _tp.pool_is_thin(legs):
    NEAR=[]  # normal filters stand when the qualified pool is already large enough
except Exception as _e:
  print('thin-pool near-miss filter skipped', _e)
json.dump(legs,open('cands.json','w'),indent=1,ensure_ascii=False);json.dump(NEAR,open('near.json','w'),indent=1,ensure_ascii=False);json.dump(EXC,open('excluded.json','w'),indent=1,ensure_ascii=False);json.dump({e['homeTeamName']+' v '+e['awayTeamName']:dict(league=e['sport']['category']['name']+' - '+e['sport']['category']['tournament']['name'],ko=time.strftime('%Y-%m-%d %H:%M',time.gmtime(e['estimateStartTime']/1000)),eventId=e['eventId']) for e in E.values()},open('fixtures_index.json','w'),ensure_ascii=False)
json.dump(MC,open('market_cands.json','w'),indent=1,ensure_ascii=False)
json.dump({k:dict(src=v[1],n=v[0][0],c=v[0][1],buckets=BPROF.get(k)) for k,v in PROFS.items()},open('profiles.json','w'),indent=1,ensure_ascii=False)
print(len(legs),collections.Counter(v.split(' (')[0] for v in EXC.values()))
for l in legs: print(round(l['score'],3),l['ko'],l['match'],'|',l['league'][:26],'|',l['pick'],l['odds'],'|',l['rate'],l['n'],'|',l['team'],'| H2H',l['h2h'][:40])
