# Oct 23 rule engine (= rules22 + NO-HA ban): standing rules + Oct 18 forensic rules + DC1-DC5 + PPG/KoK v2 + bust_forensics.md lessons (Oct 19-20) + "Only No is off".
import re,json,pickle,csv,collections,difflib,unicodedata
SAMPLES=[('hv8','h','v8'),('hsv','h','sv'),('hl10','h','l10'),('av8','a','v8'),('asv','a','sv'),('al10','a','l10'),('h2h',None,'h2h')]
_Y=re.compile(r'women|\bw\b|\(w\)|u1\d|u2\d|youth|reserve|(?<!willem)(?<!nb)\sii$|jong |primavera|next pro|junior|academy|next gen',re.I)
class _YY:
    def search(self,s):
        return _Y.search(s) or any(t.strip().lower().endswith(' b') for t in s.split('|')[0].split(' v '))
YOUTH=_YY()
LOWSC=re.compile(r'slovenia\|prvaliga|russia\|premier league|qatar|poland\|ii liga',re.I)
CAUTION=re.compile(r'tercera|serie c|malta|cyprus|primera federacion',re.I)
def avoid(lg):l=lg.lower();return 'morocco' in l or 'south africa' in l or ('turk' in l and '1. lig' in l) or ('egypt' in l and ('2' in l or 'second' in l))
from _gate_data import load_json, load_pickle, open_text, csv_dict_rows
NOHIST=set()
_fh=open_text('oct31_odds_match_combo.md')
if _fh:
    for ln in _fh:
        m=re.match(r'- \d\d:\d\d (.+?) \(.*\) \[.*\]: league not in history',ln.strip())
        if m:NOHIST.add(m.group(1))
    _fh.close()
F={r['eid']:r for r in (load_pickle('feat31.pkl', []) or []) if isinstance(r, dict) and 'eid' in r}
_EV=load_json('ev31.json', {})
FHFAV={}
for _e,_d in _EV.items():
    for _m in (_d or {}).get('markets',[]):
        if str(_m['id'])=='60' and not _m.get('specifier'):
            _p=[float(o['odds']) for o in _m['outcomes'] if o['desc'] in('Home','Away') and o.get('odds')]
            if _p:FHFAV[_e]=min(_p)
# NEW Oct 23 CUP-1: knockout cup ties (league samples come from a different context; ET/penalties)
CUPKO=re.compile(r'cup|copa|pohar|pokal|coupe|coppa|ta[cç]a|beker|trophy|libertadores|sudamericana|dimayor|knockout|play-?off',re.I)
def norm(s):return re.sub(r'[^a-z0-9 ]','',unicodedata.normalize('NFKD',s).encode('ascii','ignore').decode().lower()).strip()
REC=collections.defaultdict(lambda:[0,0]);FAMREC=collections.defaultdict(lambda:[0,0])
def famof(mk):
    m=mk.lower()
    if 'double chance' in m:return 'DC'
    if 'draw no bet' in m:return 'DNB'
    if 'over 1.5' in m and 'team' not in m:return 'O15'
    if 'over 0.5' in m:return 'TO05'
    if '1x2' in m:return 'WIN'
    return 'OTH'
for r in csv_dict_rows('team_tip_log.csv'):
    if r.get('result') not in('W','L'):continue
    rel=r.get('team_relied_on') or 'both';ts=[r['home'],r['away']] if rel in('both','') else [rel]
    for t in ts:k=norm(t);REC[k][r['result']=='L']+=1;FAMREC[(k,famof(r['market']))][r['result']=='L']+=1
TN=list(REC)
def rec(t):
    m=difflib.get_close_matches(norm(t),TN,1,0.88);return (m[0],REC[m[0]]) if m else (None,None)
def famrec(t,fam):
    m=difflib.get_close_matches(norm(t),TN,1,0.88);return FAMREC.get((m[0],fam)) if m else None
# ---------- sample helpers ----------
def worst_of(S,f):
    rs={}
    for k,s,w in SAMPLES:
        L=S['h2h'] if k=='h2h' else S[s][w];r=[]
        for x in L:
            try:v=f(*x[:4])
            except Exception:v=None
            if v is not None:r.append(bool(v))
        need=4 if k in('h2h','hsv','asv') else 5
        if len(r)>=need:rs[k]=(sum(r),len(r))
    if not rs:return None
    return min(a/b for a,b in rs.values())
class Ctx:
    def __init__(s,eid,g,SB):
        s.eid=eid;s.m=g['m'];s.lg=g['lg'];s.S=g['S'];s.ko=g['ko'];s.youth=bool(YOUTH.search(s.m+'|'+s.lg))
        mk=None
        for k,v in SB.items():
            if v['eid']==eid:mk=v['mk'];break
        s.mk=mk or {}
        def P(k):
            try:return float(s.mk[k])
            except Exception:return None
        s.P=P;s.ph=P('1||Home');s.pd=P('1||Draw');s.pa=P('1||Away')
        s.fav='h' if (s.ph or 99)<=(s.pa or 99) else 'a';s.dog='a' if s.fav=='h' else 'h'
        r=F.get(eid) or {};s.omc=r.get('omc');s.feat=r
        # NEW Oct 22: youth/reserve check also uses Sportradar team names (SportyBet lists Flora U21 as 'Tallinna FC Flora')
        if not s.youth and YOUTH.search(f"{r.get('sr_h') or ''} v {r.get('sr_a') or ''}|{r.get('tname') or ''}"):s.youth=True;s.youth_sr=True
        s.nohist=s.m in NOHIST
    def V(s,side):return s.S[side]['v8']
    def L10(s,side):return s.S[side]['l10']
    def tg(s,z,side):return z[0] if side=='h' else z[1]
    def og(s,z,side):return z[1] if side=='h' else z[0]
    def rate(s,L,f):return sum(1 for z in L if f(z))/len(L) if L else 0
    def vwin(s,side):return s.rate(s.V(side),lambda z:s.tg(z,side)>s.og(z,side))
    def vdraw(s,side):return s.rate(s.V(side),lambda z:z[0]==z[1])
    def l10draw(s,side):return s.rate(s.L10(side),lambda z:z[0]==z[1])
    def vppg(s,side):
        L=s.S[side]['sv'] or s.V(side)
        return sum(3 if s.tg(z,side)>s.og(z,side) else 1 if z[0]==z[1] else 0 for z in L)/len(L) if L else 0
    def vgf(s,side):L=s.V(side);return sum(s.tg(z,side) for z in L)/len(L) if L else 0
    def vga(s,side):L=s.V(side);return sum(s.og(z,side) for z in L)/len(L) if L else 0
    def vsc(s,side):return s.rate(s.V(side),lambda z:s.tg(z,side)>0)
    def vcc(s,side):return s.rate(s.V(side),lambda z:s.og(z,side)>0)
    def vsc2(s,side):return s.rate(s.V(side),lambda z:s.tg(z,side)>=2)
    def vcc2(s,side):return s.rate(s.V(side),lambda z:s.og(z,side)>=2)
    def vtot(s,side):L=s.V(side);return sum(z[0]+z[1] for z in L)/len(L) if L else 0
    def vo15(s,side):return s.rate(s.V(side),lambda z:z[0]+z[1]>=2)
    def l10o15(s,side):return s.rate(s.L10(side),lambda z:z[0]+z[1]>=2)
    def v1h(s,side):
        L=[z for z in s.V(side) if z[2] is not None];return sum(z[2]+z[3] for z in L)/len(L) if L else 9
    def xg(s):return (s.vgf('h')+s.vga('a')+s.vgf('a')+s.vga('h'))/2
    def hist(s,key):
        o=s.omc
        if not o:return None
        v=o['br'].get(key)
        return (v[0],v[1]) if v and v[1]>=10 else None
def side_of(c):
    o=c['oc'].lower()
    if o.startswith('home'):return 'h'
    if o.startswith('away'):return 'a'
    return None
RES={'WIN','WIN1UP','WIN2UP','FHWIN','WEH','2HWIN','WIN&O'}
_FXO={f['eid']:f.get('O',{}) for f in (load_json('fx31dc.json', []) or []) if isinstance(f, dict) and 'eid' in f}
def check(c,x,mode='main'):
    """returns None if the candidate passes, else the rule that blocks it"""
    f=c['fam'];o=c['oc'].lower();md=c['mdesc'].lower();mid=c['mid'];S=x.S
    if mid=='29' and o=='no':return 'BTTS No (only excluded market)'
    if 'lebring' in x.m.lower():return 'NO-LEBRING: Lebring left out of every slip (user rule, Oct 23)'
    # NEW Oct 28 FH-15 (Oct 26 settle): no 2nd-half Over 0.5 when the match Over 2.5 is priced 1.70+.
    # 2H O0.5 legs Oct 23/25/26: O2.5 <1.70 went 17W-0L; O2.5 1.70+ went 13W-6L (68%): Bhayangkara 0:0, Nea Salamina 0:0 (Oct 26), Tottori 0:0, Genoa, Sunderland (Oct 25), Akhmat (Oct 23).
    if mid=='90' and c.get('spec')=='total=0.5' and o=='over 0.5':
        _o25=(_FXO.get(x.eid,{}).get('18|total=2.5|Over 2.5') or [None])[0]
        if _o25 is None or _o25>1.60:return f'NEW FH-15: no 2H Over 0.5 when match O2.5 is {_o25} (needs <=1.60, P5)'
    # NEW Oct 23 CUP-1 (Oct 21 Zlate Moravce + Oct 22 Columbus, Al Wasl, Palmeiras, Firpo, Barranquilla, Metropolitanos): main legs in knockout cup ties need worst 85%+ (tier A/B)
    if mode=='main' and CUPKO.search(x.lg.split('|',1)[-1] if '|' in x.lg else x.lg) and c['worst']<0.85:return 'NEW CUP-1: knockout cup tie needs worst 85%+'
    # NEW Oct 23 standing ban (user, Oct 22): never Double Chance Home or Away (12), incl. DC 1UP and DC combos
    if 'home or away' in o or 'home/away' in o or ('double chance' in md and o in('12','1 or 2')):return 'NO-HA: Double Chance Home or Away (12) banned'
    # NEW Oct 22 data-integrity check: team-total market labelled with a club name that is neither team in the fixture
    if mid in('19','20','69','70','91','92') and ' Over/Under' in c['mdesc']:
        pre=re.sub(r'^(1st|2nd) half - ','',c['mdesc'],flags=re.I).split(' Over/Under')[0].strip()
        hn,an=x.m.split(' v ',1)
        if pre and pre.lower() not in(hn.lower(),an.lower()) and not pre.lower().startswith(('home team','away team')):return f'data check: SportyBet labels this team total "{pre}", not a team in the fixture'
    if f=='STAT':
        if 'booking' in md:return 'P-BK: bookings markets barred (no referee data; 0/2 Oct 19-20)'
        if 'corner handicap' in md:
            sd=side_of(c)
            if sd==x.dog and abs(x.vppg('h')-x.vppg('a'))>=1.0:return 'F-CH: corner handicap on the underdog in a siege game'
        return None
    if f in RES:
        sd=side_of(c) or ('h' if 'home' in md else 'a')
        if x.youth:return 'DC4 ext: no result legs on youth/reserve'
        if x.vppg(sd)<1.30:return 'PPG v2: side venue PPG <1.30'
        if c['worst']<0.5:return 'FH-8: result worst <50%'
        pr=x.ph if sd=='h' else x.pa
        if f in('WIN','WIN1UP','WIN2UP','WIN&O') and pr and pr>=1.70:return 'F: no straight-win/2UP on favourites priced 1.70+'
        if sd=='h' and avoid(x.lg):return 'avoid-list home favourite'
        if sd=='a' and x.nohist and f in('WIN','WIN1UP','WIN2UP'):return "F: no away-win legs on 'league not in history'"
        if f in('WIN','WIN1UP','WIN2UP') and x.vgf('a' if sd=='h' else 'h')>x.vgf(sd):return 'F-Porto: opponent venue goals-for higher than the backed side'
        h=x.hist('Home win' if sd=='h' else 'Away win')
        if h and h[0]/h[1]<0.65:return f'odds-match win history {h[0]}/{h[1]} <65%'
        return None
    if f=='DC':
        if x.youth:return 'DC4: no DC on youth/reserve (team or tournament name)'
        H,A='h','a'
        if o=='home or away':
            if max(x.vwin(H),x.vwin(A))<0.6 or max(x.vdraw(H),x.vdraw(A),x.l10draw(H),x.l10draw(A))>=0.3:return 'DC1: 12 needs a 60%+ venue winner and no 30%+ drawer'
        if o=='home or draw':
            if x.vwin(H)<0.4:return 'DC2: 1X needs home venue win 40%+'
            if (x.ph or 0)>(x.pa or 99):return 'F: no DC 1X on the market underdog'
        if o=='draw or away':
            if x.vwin(A)<0.5:return 'DC3: X2 needs away win 50%+ away'
            if (x.pa or 0)>(x.ph or 99):return 'F: no DC X2 on the market underdog'
        k={'home or draw':'1X','draw or away':'X2','home or away':'12'}[o];h=x.hist(k)
        if h and h[0]/h[1]<0.75:return f'odds-match {k} history {h[0]}/{h[1]} <75%'
        return None
    if f=='DNB':
        sd=side_of(c);od='a' if sd=='h' else 'h'
        if x.youth:return 'DC4: no DNB on youth/reserve'
        if x.vppg(sd)<1.30 or x.vwin(sd)<0.6:return 'F-DNB: side venue PPG 1.30+ and win 60%+'
        if x.vdraw(od)>=0.3:return 'F-DNB: opponent draws 30%+ at venue'
        return None
    if f in('O1.5','EG1.5'):
        if x.nohist:return "F: no Over 1.5/Early Goals on 'league not in history'"
        if not((x.vtot('h')+x.vtot('a'))/2>=2.8 and x.vo15('h')>=0.75 and x.vo15('a')>=0.75 and x.vga('h')+x.vga('a')>=2.125):return 'rule 2: Over 1.5 venue-goals bar'
        if x.l10o15('h')<0.6 or x.l10o15('a')<0.6:return 'v2: a side <60% 2+ goal games in L10'
        if x.vsc(x.dog)<0.6:return 'F: weaker side scores in <60% of venue games'
        if CAUTION.search(x.lg) and c['worst']<0.85:return 'rule 2 caution league needs worst 85%+'
        if x.youth and c['worst']<0.75:return 'F: youth Over 1.5 needs 75%+'
        h=x.hist('O1.5')
        if h and h[0]/h[1]<0.75:return f'odds-match O1.5 history {h[0]}/{h[1]} <75%'
        return None
    if f in('O2.5','EG2.5','O&GG','O3.5','EG3.5','O2.0','O3.0'):
        if c['worst']<0.70:return 'F: Over 2.5+/Early Goals O2.5 needs worst 70%+'
        if f in('O3.5','EG3.5') and c['worst']<0.75:return 'FHG-11: O3.5 needs worst 75%+'
        if x.l10o15('h')<0.6 or x.l10o15('a')<0.6:return 'F: both sides 2+ goal games 60%+'
        if x.youth and min(x.vtot('h'),x.vtot('a'))<3.5:return 'F: youth Over 2.5 only when both venue goal avgs 3.5+'
        h=x.hist('O2.5')
        if h and h[0]/h[1]<0.60:return f'F: similar-games O2.5 {h[0]}/{h[1]} <60%'
        return None
    if f in('HT0.5','AT0.5'):
        sd='h' if f=='HT0.5' else 'a';od='a' if sd=='h' else 'h'
        if LOWSC.search(x.lg):return 'rule 1: low-scoring league'
        if x.vsc(sd)<0.8 or x.vcc(od)<0.75:return 'rule 1 (tightened): team scores 80%+ / opponent concedes 75%+'
        if x.youth and sd=='a':return 'F: no team O0.5 on a youth away side'
        return None
    if f in('HT1.5','AT1.5','HT2.5','AT2.5'):
        sd='h' if f.startswith('HT') else 'a';od='a' if sd=='h' else 'h'
        if x.vsc2(sd)<0.7 or x.vcc2(od)<0.6:return 'F: team O1.5 needs 2+ in 70% venue and opponent concedes 2+ in 60%'
        return None
    if f in('XorO25','XorGG'):
        # both branches must be independently 70%+
        if mid in('854','860'):b1=lambda h,a,hh,ha:h>a
        elif mid in('858','862'):b1=lambda h,a,hh,ha:a>h
        else:b1=lambda h,a,hh,ha:h==a
        b2=(lambda h,a,hh,ha:h+a>2.5) if f=='XorO25' else (lambda h,a,hh,ha:h>0 and a>0)
        w1,w2=worst_of(S,b1),worst_of(S,b2)
        if w1 is None or w2 is None or w1<0.7 or w2<0.7:return f"F: combo branches need 70%+ each ({(w1 or 0):.0%}/{(w2 or 0):.0%})"
        return None
    if f=='GG':
        if x.youth:return 'F: no BTTS Yes on youth'
        if x.vsc('h')<0.7 or x.vsc('a')<0.7:return 'F: BTTS Yes needs both teams scoring in 70%+ of venue games'
        return None
    if f.startswith('U'):
        t=float(f.split('_')[1]);m_=f[1:].split('_')[0]
        # NEW Oct 22 FH-11 (validated Oct 20 + Oct 21): the favourite's own team Under 2.5 or lower is barred.
        # FH-filter favourites scored 3+ in 8/21 (Oct 20) and 10/22 (Oct 21) matches; Borneo and Navbahor team U2.5 both lost Oct 21.
        if m_ in('19','20') and t<=2.5:
            sd='h' if m_=='19' else 'a';pr=x.ph if sd=='h' else x.pa
            if sd==x.fav and (mode=='fh' or (pr and pr<=2.00)):return 'NEW FH-11: no team Under 2.5 on the favourite'
        # NEW Oct 25 FH-11b (Oct 23 Shamrock Rovers U3.5 4:0, IK Oddevold U3.5 7:0; validated on Oct 22 America de Cali U3.5 0:4; only win Zrinjski 1:0):
        # in the 1st Half Filter the favourite's own team Under is barred at ANY line (FH-11 covered only <=2.5).
        if mode=='fh' and m_ in('19','20'):
            sd='h' if m_=='19' else 'a'
            if sd==x.fav:return 'NEW FH-11b: no team Under (any line) on the favourite in the 1st Half Filter'
        # NEW Oct 28 FH-14 (Oct 25: favourite's own 1H team Under 1.5 went 2W-6L - Marseille 2:0 HT, Juventus 0:2 HT, Apollon 0:2 HT, Ferencvaros 3:0 HT, Racing United 1:2 HT, Castellon 2:0 HT;
        # holds on Oct 23: Middlesbrough 1H U1.5 lost 1:3 HT): no 1H team Under (any line) on the 1X2 favourite, in every section.
        if m_ in('69','70'):
            sd='h' if m_=='69' else 'a'
            if sd==x.fav:return 'NEW FH-14: no 1H team Under on the favourite (all sections)'
        # NEW Oct 25 FH-13 (Oct 23 FC Goa 1:1 HT, Vihren 1:1 HT lost, Chernomorets/Zebbug won; validated on Oct 22 Buducnost 1:1 HT lost): 2W-3L over 2 days.
        if mode=='fh' and m_=='68' and t<=1.5:return 'NEW FH-13: no 1H match Under 1.5 in the 1st Half Filter'
        # NEW Oct 22 FH-12 (validated Oct 20 + Oct 21): no full-time match unders in the 1st Half Filter.
        # FH-filter matches had 5+ goals in 6/21 (Oct 20) and 7/22 (Oct 21), 4+ goals in 10/21 and 12/22; Kolbotn U4.5 lost 3:4.
        if mode=='fh' and m_ in('18','60180'):return 'NEW FH-12: no full-time match unders in the 1st Half Filter'
        # NEW Oct 23 FH-12M: FH-12 extended to main for matches that qualify for the 1st Half Filter (either side 1H 1X2 <=2.00).
        # Oct 22: Ferencvaros U4.5 (4:1), Buducnost U3.5 (3:3), America de Cali U3.5 (0:4) lost, Tractor U3.5 won; FH-12 match-goal evidence Oct 20/21.
        if mode=='main' and m_ in('18','60180','19','20') and FHFAV.get(x.eid,9)<=2.00:return 'NEW FH-12M: no full-time unders in main on 1st-Half-Filter matches'
        if m_ in('18','60180') and t<=3.5 and x.xg()>2.6 and t>=3.5:return f'Under 3.5 needs expected goals <=2.6 (xg {x.xg():.2f})'
        if m_ in('18','60180') and t<=2.5 and x.xg()>2.3:return f'F: Under 2.5 needs expected goals <=2.3 (xg {x.xg():.2f})'
        if m_=='68' and t<=1.5 and x.v1h('h')+x.v1h('a')>=2.0:return 'F: 1H Under 1.5 needs combined venue 1H goal avg <1.0 per side'
        if m_=='90' and c['worst']<0.80:return 'F: 2H Under 2.5 needs worst 80%+'
        if m_ in('19','20'):
            sd='h' if m_=='19' else 'a'
            if t>=3.5 and (x.rate(x.V(sd),lambda z:x.tg(z,sd)>=4)>=0.1):return 'F: team Under 3.5 needs that team 4+ goals <10%'
        if mode=='fhg':return 'goals-over filter'
        return None
    if f in('1H0.5','2H0.5','H1H0.5','A1H0.5','H2H0.5','A2H0.5','1H1.0','2H1.0','2H1.5','1HGG','2HGG','SBH','HSH','BHO1.5','1H1.5'):
        if f=='1H1.5' and mode!='main':return 'FHG patch 1: 1H O1.5 is filter only'
        if x.youth and f!='2H0.5':return 'patch 10: youth sides, FT goals only (half markets barred)'
        if c['worst']<0.75 and f in('1H0.5','2H0.5'):return 'patch 8: 1H/2H O0.5 needs every sample 75%+'
        return None
    return None
def tlnote(m):
    out=[];ban=False
    for t in m.split(' v '):
        k,rr=rec(t)
        if rr:out.append(f"{t} {rr[0]}-{rr[1]} in tracked tips");ban|=rr[1]>=2 and rr[1]>rr[0]
    return out,ban
EARLY={'60200','60100','60180','60110'}
def tier(w):return 'A' if w>=0.9 else 'B' if w>=0.85 else 'C' if w>=0.75 else 'D'
def top5(eid):
    r=F.get(eid) or {}
    for a in r.get('ht') or []:
        for b in r.get('at') or []:
            if a['tid']==b['tid'] and a['N']>=6 and a['pos'] and b['pos'] and a['pos']<=5 and b['pos']<=5:return f"{a['pos']} v {b['pos']} of {a['N']}"
def pos(eid):
    r=F.get(eid) or {}
    for a in r.get('ht') or []:
        for b in r.get('at') or []:
            if a['tid']==b['tid']:return (a['pos'],b['pos'],a['N'])

# NEW NO-HA-SUB (user, Oct 23): a match whose top pick would be DC Home or Away (12) gets GG Yes or Over 1.5 instead,
# whichever has the higher worst-sample hit rate (tie -> avg). Price must be 1.20+; if neither qualifies the match is DROPPED (never pad).
# No other market may stand in for a 12 pick.
def noha_sub(all_cands,ok):
    """all_cands: every graded cand for the match (incl. blocked); ok: passing cands sorted best-first.
    Returns (list_to_use, note). If the best raw cand (ranked by worst/avg, ignoring the ban) is a 12 pick, returns only the GG/O1.5 replacement."""
    raw=sorted([c for c in all_cands if 1.15<=c['p']<=1.60],key=lambda c:(-c['worst'],-c['avg']))
    if not raw or 'home or away' not in raw[0]['oc'].lower():return ok,None
    alt=[c for c in all_cands if c['p']>=1.20 and ((c['mid']=='29' and c['oc']=='Yes') or (c['mid']=='18' and c.get('spec')=='total=1.5' and c['oc'].lower().startswith('over')))]
    # Oct 25: the replacement must itself pass (worst 75%+, tier C or better); Oct 23 tier-D GG subs Pachern/Oberwart and O1.5 Kafr Qasim lost
    alt=[c for c in alt if c['worst']>=0.75]
    alt.sort(key=lambda c:(-c['worst'],-c['avg']))
    if not alt:return [],'NO-HA-SUB: 12 pick dropped (no GG/Over 1.5 at 1.20+ grading 75%+)'
    return [alt[0]],f"NO-HA-SUB: 12 pick replaced by {alt[0]['mdesc']} {alt[0]['oc']} @{alt[0]['p']}"
