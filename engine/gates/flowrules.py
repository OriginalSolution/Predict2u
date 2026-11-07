# Standing rules for DC Flow (hardcoded Oct 24 after user complaint): every strategy's rule set via rules31 + standings + league support.
import json,re,sys
from pathlib import Path as _P
_HERE=_P(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))
from _gate_data import load_json
import rules31 as R
from rulebook import viol
D=load_json('graded31.json', {})
SB=load_json('sbcombo31.json', {})
_X=load_json('mgst31.json', {})
MG=_X.get('MG') if isinstance(_X, dict) else {}
ST=_X.get('ST') if isinstance(_X, dict) else {}
if not isinstance(MG, dict): MG={}
if not isinstance(ST, dict): ST={}
LR=load_json('lgrate.json', {})
GDR=r'^(Argentina|Kenya|Azerbaijan|Ecuador|Cameroon|El Salvador|Ethiopia|Fiji|Rwanda|Panama|Senegal|Singapore|Kyrgyzstan|Macao|Kazakhstan)|India Indian Super League|^Hungary NB I$|Canadian Premier League|Thai League 1|^Ukraine Premier'
LTH={'O1.5':.75,'O2.5':.55,'U2.5':.55,'O3.5':.40,'U1.5':.30}
FAM={'O1.5':('18','total=1.5','Over 1.5','O1.5'),'O2.5':('18','total=2.5','Over 2.5','O2.5'),'O3.5':('18','total=3.5','Over 3.5','O3.5'),
 'U2.5':('18','total=2.5','Under 2.5','U18_2.5'),'U1.5':('18','total=1.5','Under 1.5','U18_1.5'),'Home Win':('1','','Home','WIN'),'Away Win':('1','','Away','WIN'),'Draw':('1','','Draw','OTH')}
def standings(eid):
  m=MG.get(eid)
  if not isinstance(m,dict) or 'teams' not in m:return None,None
  t=ST.get(str(m.get('_seasonid')));hu,au=m['teams']['home']['uid'],m['teams']['away']['uid']
  for tb in (t or {}).get('tables',[]) if isinstance(t,dict) else []:
    P={r['team']['uid']:r for r in tb.get('tablerows',[])};N=len(P)
    if hu in P and au in P and N>=6:
      h,a=P[hu],P[au];txt=f"overall {h['pos']} v {a['pos']} of {N}; home table {h.get('posHome')} v away table {a.get('posAway')}"
      t5=lambda x:x and x<=5;b5=lambda x:x and x>N-5
      if t5(h['pos']) and t5(a['pos']):return 'TOP-5 v TOP-5 (overall)',txt
      if b5(h['pos']) and b5(a['pos']):return 'BOTTOM-5 v BOTTOM-5 (overall)',txt
      if t5(h.get('posHome')) and t5(a.get('posAway')):return 'TOP-5 v TOP-5 (split home/away tables)',txt
      if b5(h.get('posHome')) and b5(a.get('posAway')):return 'BOTTOM-5 v BOTTOM-5 (split home/away tables)',txt
      return None,txt
  return None,'no table'
def lrate(eid,pk):
  if pk not in LTH:return None,0
  s=str(MG.get(eid,{}).get('_seasonid'));v=LR.get(s) or {};G=v.get('cur') or []
  if len(G)<30 and v.get('prev'):G=G+v['prev']
  if len(G)<30:return None,len(G)
  ln=float(pk[1:]);return sum((a+b>ln) if pk[0]=='O' else (a+b<ln) for a,b in G)/len(G),len(G)
def screen(r,wmin=.60):
  """r: dict eid,m,lg,pk,price. Returns (reason or None, info dict)."""
  e=r['eid'];info={};lg=r['lg']
  if 'lebring' in r['m'].lower():return 'Lebring',info
  g=D.get(e)
  if not g or 'err' in g:return 'no Sportradar samples (main engine requires them)',info
  x=R.Ctx(e,g,SB)
  if x.youth:return 'women/youth/reserve/B side',info
  if len(x.V('h'))<5 or len(x.V('a'))<5:return '<5 venue games',info
  st,txt=standings(e);info['table']=txt
  if st:return st,info
  if 'malta' in lg.lower():return 'Malta (caution league, excluded from every slip)',info
  tl,ban=R.tlnote(r['m'])
  if ban:return 'tip-log red flag: '+'; '.join(tl),info
  mid,spec,oc,fam=FAM[r['pk']]
  gc=[c for c in g['cands'] if c['mid']==mid and (c['spec'] or '')==spec and c['oc']==oc]
  c=dict(gc[0]) if gc else dict(mid=mid,spec=spec,oc=oc,mdesc='1X2' if mid=='1' else 'Over/Under',fam=fam,worst=r.get('w',0),avg=r.get('w',0))
  c['p']=r['price'];info['worst7']=c['worst']
  if c['worst']<wmin:return f"worst over all 7 samples (incl. H2H/L10) {c['worst']:.0%} < {wmin:.0%}",info
  if R.CUPKO.search(lg) and c['worst']<.85:return 'cup needs 85%+',info
  why=R.check(c,x,'main')
  if why:return why,info
  if r['pk'][0]=='O' and re.search(GDR,lg):return 'rulebook Group D: no Over legs',info
  rb={'O1.5':'Over 1.5','O2.5':'Over 2.5','O3.5':'Over 3.5','U1.5':'Under 1.5','U2.5':'Under 2.5','Home Win':'1X2 Home to win','Away Win':'1X2 Away to win','Draw':'1X2: Draw'}[r['pk']]
  v=viol(lg,rb)
  if v:return v,info
  lr,n=lrate(e,r['pk']);info['league']=f"{lr:.0%} of {n}" if lr is not None else f"n={n}"
  if r['pk'] in LTH:
    if lr is None:return f'league sample too small (n={n})',info
    if lr<LTH[r['pk']]:return f"league {r['pk']} rate {lr:.0%} < {LTH[r['pk']]:.0%}",info
  return None,info
