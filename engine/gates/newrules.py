import json,re,sys,collections,os
from pathlib import Path as _P
_GATES=_P(os.environ.get('ENGINE_GATES_DIR') or _P(__file__).resolve().parent)
if str(_GATES) not in sys.path:
    sys.path.insert(0, str(_GATES))
_EV=None
LOG=str(_GATES/'newrules_log.jsonl')
def EV():
    global _EV
    if _EV is None:
        try:
            from _gate_data import load_json
            _EV=load_json('ev31.json', {})
        except Exception:
            _EV={}
    return _EV
PROII=re.compile(r"^willem ii\b",re.I)  # Oct 31 approved R3 fix: pro clubs with II in name
YT=re.compile(r"\bu-?1\d\b|\bu-?2\d\b|youth|reserve|\s(ii|iii)$|\biii\b|academy|castilla|primavera|next gen|next pro|juvenil|jong |amateur|\s(b|2)$|\bb\b",re.I)
YL=re.compile(r"u-?1\d|u-?2\d|youth|reserve|primavera|juvenil|next pro|amateur|women|development|academy",re.I)  # Oct 31 approved: II in league names (NB II, II Liga) no longer blocks
PLAYOFF=re.compile(r'\bMLS\b|major league soccer|\bUSL\b|canadian premier|liguilla|reducido|play-?off|knockout',re.I)
WOM=re.compile(r"women|\(w\)|\bwfc\b|ladies|femin",re.I)
_mm={}
def mism(e):
    if e not in _mm:
        try:
            import gate31 as G;_mm[e]=bool(G.mism(e))
        except Exception:_mm[e]=False
    return _mm[e]
def info(eid,mid,spec,oid):
    d=EV().get(eid) or {}
    md=od=None;o25=dr=px=ph=pa=None;mid_=str(mid)
    for m in d.get('markets',[]):
        for o in m.get('outcomes',[]):
            if str(m['id'])==str(mid) and (m.get('specifier') or '')==(spec or '') and str(o['id'])==str(oid):md=m.get('desc') or m.get('name');od=o['desc'];px=float(o['odds'])
            if str(m['id'])=='18' and m.get('specifier')=='total=2.5' and o['desc']=='Over 2.5':o25=float(o['odds'])
            if str(m['id'])=='1' and o['desc']=='Draw':dr=float(o['odds'])
            if str(m['id'])=='1' and o['desc']=='Home':ph=float(o['odds'])
            if str(m['id'])=='1' and o['desc']=='Away':pa=float(o['odds'])
    cat=(d.get('sport') or {}).get('category') or {}
    lg=f"{cat.get('name','')}|{(cat.get('tournament') or {}).get('name','')}"
    return dict(mid=mid_,ph=ph,pa=pa,px=px,md=md or '',od=od or '',o25=o25,dr=dr,h=d.get('homeTeamName',''),a=d.get('awayTeamName',''),lg=lg,st=d.get('matchStatus'),ko=d.get('estimateStartTime',0))
def mism_(L):
    if L.get('mm') is None:L['mm']=mism(L['eid'])
    return L['mm']
_pos={}
def pos(e):
    if e not in _pos:
        try:
            import gate31 as G
            t5=G.R.top5(e);st,_=G.FR.standings(e)
            _pos[e]=('top-5 v top-5 ('+t5+')') if t5 else (st if st and ('TOP' in st or 'BOTTOM' in st) else None)
        except Exception as ex:_pos[e]=None
    return _pos[e]
def why(L,price,n):
    md,od=L['md'],L['od'];full=md+' '+od
    if L['mid'] in ('10','60110') or re.search(r'double\s*chance',md,re.I):return 'HARD VETO: no double chance (1X, X2 or 12)'
    if L['st'] not in (None,'Not start'):return 'started'
    import time
    if L['ko'] and L['ko']<time.time()*1000:return 'started'
    if WOM.search(L['h']+' '+L['a']+' '+L['lg']):return 'women'
    if any(YT.search(t) and not PROII.search(t) for t in (L['h'],L['a'])) or YL.search(L['lg']):return 'R3 youth/reserve/amateur/B'
    if od=='Home or Away':return '12'
    if L.get('eid') and pos(L['eid']):return 'top/bottom-5 clash: '+pos(L['eid'])
    if re.search(r'GG/NG|Both Teams',md,re.I) and od.strip().lower()=='no':return 'BTTS No'
    if 'lebring' in full.lower():return 'Lebring'
    if price>1.50:return '>1.50'
    isU=od.startswith('Under') or ' Under ' in od and ' or ' not in od
    if re.search(r'(Home|Draw|Away|1X|X2|12)( Team)? or (Over|Under)',full) and price>=1.20:return 'R2 result-or-goals combo'
    if isU and price>=1.30:return 'R1 Under >=1.30'
    # P8 (approved Nov 2): no offsides markets in any section
    if re.search(r'offside',md,re.I):return 'P8 offsides market'
    # P10 (approved Nov 2): league play-offs/knockout ties = cup games; no home win / home DNB from regular-season home form
    if PLAYOFF.search(L['lg']) and (md in('1X2','Draw No Bet','1X2 - 1UP','1X2 - 2UP') or md.startswith('1X2')) and od=='Home':return 'P10 play-off tie: no home win/DNB'
    # P9 (approved Nov 2): no team-total Under on the favourite when O2.5 < 1.70, any slip size
    if isU and not re.search(r'corner|card|booking|shot|offside|foul',md,re.I) and L['o25'] and L['o25']<1.70 and L['ph'] and L['pa']:
        _ml=md.lower().replace('1st half - ','').replace('2nd half - ','')
        _hs=L['mid'] in ('19','69','91') or (L['h'] and _ml.startswith(L['h'].lower()))
        _as=L['mid'] in ('20','70','92') or (L['a'] and _ml.startswith(L['a'].lower()))
        if (_hs and L['ph']<L['pa']) or (_as and L['pa']<L['ph']):return 'P9 favourite team Under with O2.5<1.70'
    # P1 (approved Oct 31): no team-total Under for a side priced 1.30 or shorter to win
    if isU and not re.search(r'corner|card|booking|shot|offside|foul',md,re.I):
        hs=L['mid'] in ('19','69','91') or (L['h'] and md.lower().replace('1st half - ','').replace('2nd half - ','').startswith(L['h'].lower()))
        as_=L['mid'] in ('20','70','92') or (L['a'] and md.lower().replace('1st half - ','').replace('2nd half - ','').startswith(L['a'].lower()))
        if hs and L['ph'] and L['ph']<=1.30:return 'P1 team Under on <=1.30 favourite'
        if as_ and L['pa'] and L['pa']<=1.30:return 'P1 team Under on <=1.30 favourite'
        # FH-14 (applied from Oct 26 in every section): no 1st-half team Under 1.5 on the favourite
        if md.lower().startswith('1st half - ') and od=='Under 1.5' and L['ph'] and L['pa']:
            if (hs and L['ph']<L['pa']) or (as_ and L['pa']<L['ph']):return 'FH-14: favourite 1H team U1.5'
    # P6 (approved Nov 1): no team-total Under on the favourite priced 1.80 or shorter to win
    if isU and not re.search(r'corner|card|booking|shot|offside|foul',md,re.I):
        hs=L['mid'] in ('19','69','91') or (L['h'] and md.lower().replace('1st half - ','').replace('2nd half - ','').startswith(L['h'].lower()))
        as_=L['mid'] in ('20','70','92') or (L['a'] and md.lower().replace('1st half - ','').replace('2nd half - ','').startswith(L['a'].lower()))
        if L['ph'] and L['pa']:
            if hs and L['ph']<=1.80 and L['ph']<L['pa']:return 'P6 team Under on <=1.80 favourite'
            if as_ and L['pa']<=1.80 and L['pa']<L['ph']:return 'P6 team Under on <=1.80 favourite'
    # P3 (approved Nov 1): no team shots/SOT/corners Overs on a side priced 4.00+ to win
    if (od.startswith('Over') or ' Over ' in od) and re.search(r'corner|shot',md,re.I):
        ml=md.lower();hside=('home team' in ml or ml.startswith(L['h'].lower()) if L['h'] else 'home team' in ml) or ('home' in ml and 'corner' in ml and 'away' not in ml)
        aside=('away team' in ml or (L['a'] and ml.startswith(L['a'].lower()))) or ('away' in ml and 'corner' in ml and 'home' not in ml)
        if hside and L['ph'] and L['ph']>=4.0:return 'P3 team shots/corners Over on 4.00+ side'
        if aside and L['pa'] and L['pa']>=4.0:return 'P3 team shots/corners Over on 4.00+ side'
    # P7 (approved Nov 1): no 1st-half Under 2.5 when match O2.5 is under 1.50
    if md.lower().startswith('1st half - over/under') and od=='Under 2.5' and L['o25'] and L['o25']<1.50:return 'P7 1H U2.5 with O2.5<1.50'
    # P4 (approved Oct 31): no away DNB in the DC Decoder
    if L.get('slip') and re.search(r'dc ?decoder|dcd',L['slip'],re.I) and md=='Draw No Bet' and od=='Away':return 'P4 away DNB in DC Decoder'
    if md=='Over/Under' and od=='Over 2.5' and price>1.30:return 'R4 O2.5 >1.30'
    if md=='Over/Under' and od in('Over 1.5','Over 2.5') and (L['dr'] or 0)>4.5:return 'draw>4.50 blocks Over'
    if isU and '2nd half' in md.lower() and L.get('mm'):return '2H Under in mismatch'
    # Standing-rule backstop (Nov 2 run): existing Oct 24 mismatch rule, trend-breaker and FH-15, enforced on every slip
    sp=L.get('spec') or ''
    if L['mid'] in ('18','60180') and od=='Over 1.5':
        if (L['dr'] or 9)<3.40:return 'TB: match O1.5 with draw <3.40'
        if not mism_(L):return 'MM(b): match O1.5 only on a mismatch'
    if L['mid'] in ('18','60180') and od=='Under 3.5' and mism_(L):return 'MM(a): no match U3.5 on a mismatch'
    if md.lower().startswith('2nd half - over/under') and od=='Over 0.5' and (L['o25'] or 9)>1.60:return 'P5: 2H O0.5 needs O2.5 <=1.60'
    if isU and n<=10 and L['o25'] and L['o25']<1.70:return 'R7 Under with O2.5<1.70 (<=10 legs)'
    return None
def filt(legs,name='',key=None,nsize=None,log=True):
    """legs: list of dict eid,mid,spec,oid,price. returns kept list (same objects)."""
    n=nsize or len(legs);kept=[];drop=[];seen=set();lgc=collections.Counter();bk=0
    for x in legs:
        e,mi,sp,oi,pr=key(x) if key else (x['eid'],x['mid'],x['spec'],x['oid'],x.get('price'))
        L=info(e,mi,sp,oi);L['slip']=name;L['eid']=e;L['spec']=sp;L.setdefault('mm',None)
        if 'under' in L['od'].lower() and '2nd half' in L['md'].lower():L['mm']=mism(e)
        if L['mm'] is None and False:pass
        p=float(pr or 0) or L['px'] or 1.3
        r=why(L,p,n)
        if not r and e in seen:r='one leg per match'
        if not r and lgc[L['lg']]>=2:r='max 2 per league'
        if not r and re.search(r'booking|card',L['md'],re.I) and bk>=1:r='max 1 bookings leg'
        if r:drop.append((x,r,L));continue
        seen.add(e);lgc[L['lg']]+=1;bk+=bool(re.search(r'booking|card',L['md'],re.I));kept.append((x,L,p))
    big=len(kept)>=50 and n>=50
    out=[]
    for x,L,p in kept:
        if p<1.20 and not big:drop.append((x,'<1.20 (slip <50)',L))
        else:out.append(x)
    if not log:
        if len(out)<=10 and n>10 and not nsize:out=filt(out,name,key=key,nsize=len(out),log=False)
        return out
    with open(LOG,'a') as f:
        for x,r,L in drop:f.write(json.dumps(dict(slip=name,m=L['h']+' v '+L['a'],mk=L['md']+' – '+L['od'],why=r))+'\n')
    if drop:print(f'[newrules] {name}: {len(legs)} -> {len(out)} ({collections.Counter(r for _,r,_ in drop)})',flush=True)
    if len(out)<=10 and n>10 and not nsize:
        # R7 loophole fix (Nov 1 run): re-check R7 on the final slip size, not the pre-filter size
        out=filt(out,name+' [R7 final-size recheck]',key=key,nsize=len(out),log=log)
    return out

def ok(eid,mid,spec,oid,price,n=40):
    """pre-selection check (no slip-level rules): returns reason string or None"""
    L=info(eid,mid,spec,oid);L['slip']='pre';L['eid']=eid;L['spec']=spec;L['mm']=None
    if 'under' in L['od'].lower() and '2nd half' in L['md'].lower():L['mm']=mism(eid)
    return why(L,float(price or 0) or L['px'] or 1.3,n)
