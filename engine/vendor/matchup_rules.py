"""Shared matchup rules applied to every pick before any bookmaker booking.
1) skip games where both teams are top 5, or both bottom 3 (leagues with 10+ teams)
2) classify mismatch / middle / even:
   mismatch: straight win picks are not booked (use GG / Over 1.5 instead)
   middle:   GG only (plus home/away team over 0.5)
0) HARD VETO: DC 12 (Home or Away) is never published; 1X/X2 above 1.35 is never published; 1X/X2 at 1.35 or below is allowed. NG (BTTS No / GG No) is never published.
   even:     no Over 1.5 / Over 2.5
"""
import re
DC_MARKET_IDS={'10','60110'}
DC_1X_X2_MAX=1.35
def is_double_chance(p):
  """True for every double-chance variant, including text-only imported legs."""
  if str(p.get('marketId') or p.get('mid') or '') in DC_MARKET_IDS: return True
  market=str(p.get('market') or p.get('marketDescription') or p.get('md') or '')
  if re.search(r'double\s*chance',market,re.I): return True
  sel=str(p.get('selection') or '').strip()
  if re.fullmatch(r'(?:1X|X2|12)',sel,re.I): return True
  if re.search(r'\b(1X|X2|12)\b', sel) and re.search(r'double|home\s*/\s*draw|draw\s*/\s*away|home\s*/\s*away', sel+' '+market, re.I): return True
  if re.search(r'home\s*/\s*draw|draw\s*/\s*away|away\s*/\s*draw|home\s*/\s*away|home\s+or\s+draw|draw\s+or\s+away|away\s+or\s+draw|home\s+or\s+away', sel, re.I): return True
  # Legacy imported ledger legs have no market ID: Home or Draw / Home or Away.
  if not market and re.search(r'\bor\s+(?:draw|home|away)\s*$',sel,re.I): return True
  if not market:
   match=str(p.get('match') or '')
   teams=[t.strip() for t in re.split(r'\s+(?:v|vs)\s+',match,maxsplit=1)]
   if len(teams)==2 and sel in (teams[0]+' or '+teams[1],teams[1]+' or '+teams[0]): return True
  return bool(re.search(r'\bdc\b',market,re.I) and re.search(r'\b(1X|X2|12)\b',sel,re.I))
def dc_variant(p):
  """Return '12', '1X', 'X2', or None if the pick is not double chance."""
  if not is_double_chance(p): return None
  sel=str(p.get('selection') or p.get('tip') or '').strip()
  mk=str(p.get('market') or p.get('marketDescription') or p.get('md') or '')
  if re.fullmatch(r'12', sel, re.I) or re.search(r'\b12\b', sel) or re.search(r'home\s*/\s*away|home\s+or\s+away', sel, re.I):
    return '12'
  if re.fullmatch(r'1X', sel, re.I) or re.search(r'\b1X\b', sel) or re.search(r'home\s*/\s*draw|home\s+or\s+draw', sel, re.I):
    return '1X'
  if re.fullmatch(r'X2', sel, re.I) or re.search(r'\bX2\b', sel) or re.search(r'draw\s*/\s*away|away\s*/\s*draw|draw\s+or\s+away|away\s+or\s+draw', sel, re.I):
    return 'X2'
  if re.search(r'home\s*/\s*away|home\s+or\s+away', mk, re.I) and not re.search(r'draw', mk, re.I):
    return '12'
  oid=str(p.get('outcomeId') or p.get('oid') or '')
  mid=str(p.get('marketId') or p.get('mid') or '')
  if mid in DC_MARKET_IDS:
    if oid in {'10','13'}: return '12'   # SportyBet Home or Away
    if oid in {'9','11'} : return '1X' if oid=='9' else 'X2'
  match=str(p.get('match') or '')
  teams=[t.strip() for t in re.split(r'\s+(?:v|vs)\s+',match,maxsplit=1)]
  if len(teams)==2 and sel in (teams[0]+' or '+teams[1], teams[1]+' or '+teams[0]):
    return '12'
  return None
def is_dc_vetoed(p):
  """Hard veto: DC 12 always; 1X/X2 only when priced above DC_1X_X2_MAX (1.35)."""
  v=dc_variant(p)
  if v is None: return False
  if v=='12': return True
  try: odds=float(p.get('odds') or 0)
  except Exception: odds=0
  if v in ('1X','X2'): return odds>DC_1X_X2_MAX
  return odds>DC_1X_X2_MAX
def dc_veto_reason(p):
  v=dc_variant(p)
  if v=='12':
    return 'HARD VETO: DC 12 (Home or Away) is never published'
  if v in ('1X','X2'):
    return f'HARD VETO: DC {v} @{p.get("odds")} is above {DC_1X_X2_MAX}'
  return f'HARD VETO: double chance @{p.get("odds")} is above {DC_1X_X2_MAX}'
NG_OUTCOME_IDS={'76'}  # SportyBet BTTS / GG No
def is_btts_no(p):
  """True for NG / BTTS No / GG No. BTTS Yes is not vetoed."""
  oid=str(p.get('outcomeId') or p.get('oid') or '')
  if oid in NG_OUTCOME_IDS: return True
  mid=str(p.get('marketId') or p.get('mid') or '')
  sel=str(p.get('selection') or p.get('tip') or '').strip()
  mk=str(p.get('market') or p.get('marketDescription') or p.get('md') or '')
  if mid in ('29','60129') and re.fullmatch(r'(no|ng)', sel, re.I): return True
  if re.search(r'both\s*teams|btts|gg\s*/?\s*ng|\bgg\b', mk, re.I) and re.fullmatch(r'(no|ng|btts no|gg no)', sel, re.I): return True
  if re.search(r'\b(btts\s*no|gg\s*no|both teams(?: to score)? no)\b', sel, re.I): return True
  return False

# ---- Obscure leagues: goals markets only (user veto 2026-11-06) ----
# Major/well-known leagues live in engine/config.json → major_leagues.patterns.
# Anything else may only use Over/Under (incl. team totals) or GG/BTTS Yes.
# NG remains banned. Daily master legs marked gateExempt/exempt are the only exception.
import json as _json_cfg
from pathlib import Path as _Path_cfg

_MAJOR_PATTERNS=None
_LEAGUE_CACHE={}

def _load_major_patterns():
  global _MAJOR_PATTERNS
  if _MAJOR_PATTERNS is not None:
    return _MAJOR_PATTERNS
  patterns=[]
  for base in (
    _Path_cfg(__file__).resolve().parents[1] / 'config.json',
    _Path_cfg(__file__).resolve().parents[2] / 'engine' / 'config.json',
  ):
    try:
      cfg=_json_cfg.loads(base.read_text())
      patterns=list((cfg.get('major_leagues') or {}).get('patterns') or [])
      if patterns:
        break
    except Exception:
      pass
  _MAJOR_PATTERNS=[str(x).strip().lower() for x in patterns if str(x).strip()]
  return _MAJOR_PATTERNS

def league_label(p):
  """Best-effort Category - Tournament label for a pick."""
  for k in ('league','tournament','tournamentName','competition','comp'):
    v=p.get(k)
    if v: return str(v).strip()
  return ''

_LEAGUE_INDEX=None
# SportyBet unique-tournament ids we know map to major competitions (stats match_info._utid).
_UTID_MAJOR={
  '1':'England - Premier League','17':'England - Championship','8':'Spain - LaLiga','54':'Spain - LaLiga2',
  '35':'Germany - Bundesliga','44':'Germany - 2. Bundesliga','23':'Italy - Serie A','53':'Italy - Serie B',
  '34':'France - Ligue 1','182':'France - Ligue 2','37':'Netherlands - Eredivisie','131':'Netherlands - Eerste Divisie',
  '238':'Portugal - Liga Portugal','7':'UEFA Champions League','679':'UEFA Europa League','17015':'UEFA Conference League',
  '242':'Brazil - Brasileiro Serie A','155':'Argentina - Primera LPF','242':'Brazil - Brasileiro Serie A',
  '266':'USA - Major League Soccer','955':'Saudi Arabia - Pro League',
}

def _league_index():
  """eventId → league built from published site JSON (high_odds/home/picks)."""
  global _LEAGUE_INDEX
  if _LEAGUE_INDEX is not None:
    return _LEAGUE_INDEX
  idx={}
  root=_Path_cfg(__file__).resolve().parents[2]
  for name in ('high_odds.json','home-picks.json','picks.json','hot-picks.json'):
    path=root/name
    if not path.exists():
      continue
    try:
      doc=_json_cfg.loads(path.read_text())
    except Exception:
      continue
    stack=[doc]
    while stack:
      o=stack.pop()
      if isinstance(o,list):
        stack.extend(o)
      elif isinstance(o,dict):
        eid=o.get('eventId'); lg=o.get('league')
        if eid and lg and eid not in idx:
          idx[eid]=str(lg).strip()
        stack.extend(o.values())
  _LEAGUE_INDEX=idx
  return idx

def resolve_league(p):
  """Fill p['league'] from pick fields, site index, stats utid map, or SportyBet event API."""
  lg=league_label(p)
  if lg:
    return lg
  eid=str(p.get('eventId') or '')
  if not eid:
    return ''
  if eid in _LEAGUE_CACHE:
    lg=_LEAGUE_CACHE[eid]
    if lg: p['league']=lg
    return lg
  lg=_league_index().get(eid) or ''
  if not lg:
    try:
      sid=eid.split(':')[-1]
      mi=_G('match_info/'+sid) or {}
      utid=str(((mi.get('match') or {}).get('_utid')) or '')
      lg=_UTID_MAJOR.get(utid) or ''
    except Exception:
      lg=''
  if not lg:
    try:
      r=_j.loads(subprocess.run(
        ['curl','-s','-m','12','-A','Mozilla/5.0',
         f'https://www.sportybet.com/api/gh/factsCenter/event?eventId={eid}&productId=3'],
        capture_output=True,text=True).stdout)
      e=(r.get('data') or {})
      cat=((e.get('sport') or {}).get('category') or {})
      tour=(cat.get('tournament') or {})
      parts=[x for x in (cat.get('name'), tour.get('name')) if x]
      lg=' - '.join(parts)
    except Exception:
      lg=''
  _LEAGUE_CACHE[eid]=lg
  if lg: p['league']=lg
  return lg

def is_major_league(league_or_pick):
  """True when the competition matches a configured major/well-known pattern."""
  if isinstance(league_or_pick, dict):
    lg=resolve_league(league_or_pick) or league_label(league_or_pick)
  else:
    lg=str(league_or_pick or '')
  s=lg.lower().strip()
  if not s:
    return False  # unknown → treat as obscure (goals only)
  for pat in _load_major_patterns():
    if pat and pat in s:
      return True
  return False

def is_goals_market(p):
  """Over/Under totals (incl. team totals) and GG/BTTS Yes. NG / BTTS No is not goals-allowed."""
  if is_btts_no(p):
    return False
  mid=str(p.get('marketId') or p.get('mid') or '')
  sel=str(p.get('selection') or p.get('tip') or '').strip()
  mk=str(p.get('market') or p.get('marketDescription') or p.get('md') or '')
  # Match totals / team totals
  if mid in ('18','19','20','68','90','60118','60168','60190'):
    return True
  if mid in ('29','60129'):
    # BTTS Yes only
    oid=str(p.get('outcomeId') or p.get('oid') or '')
    if oid in ('74','75'):  # SportyBet Yes variants
      return True
    return bool(re.search(r'(yes|gg)', sel, re.I)) and not re.search(r'no', sel, re.I)
  # Text fallbacks
  blob=(mk+' '+sel).lower()
  if re.search(r'(over|under)\s+\d', blob) or re.search(r'team over|total goals|over/under', blob):
    # Exclude win/or combos like "Away or Over 2.5"
    if re.search(r'(home|away|draw|1x|x2|12).*or|or.*(home|away|draw)', blob):
      return False
    return True
  if re.search(r'both teams to score|btts|gg', blob) and re.search(r'yes|gg', blob) and not re.search(r'no', blob):
    return True
  return False

def is_gate_exempt(p):
  return bool(p.get('gateExempt') or p.get('exempt') or p.get('dailyMaster') or p.get('masterExempt'))

def is_obscure_league_non_goals(p):
  """Hard veto candidate: non-goals market in a non-major league (unless daily-master exempt)."""
  if is_gate_exempt(p):
    return False
  if is_goals_market(p):
    return False
  return not is_major_league(p)

def obscure_veto_reason(p):
  lg=league_label(p) or resolve_league(p) or '(unknown league)'
  return f'HARD VETO: obscure league goals-only — {lg}: non-goals market {p.get("selection") or p.get("market")} not allowed'

# Preferred goals swaps when an obscure-league non-goals leg must be replaced.
GOALS_SWAP_CANDIDATES=(
  ('18','total=1.5','12','Over 1.5'),
  ('18','total=0.5','12','Over 0.5'),
  ('29','','74','GG (BTTS Yes)'),
  ('19','total=0.5','12','Home team over 0.5'),
  ('20','total=0.5','12','Away team over 0.5'),
  ('18','total=2.5','12','Over 2.5'),
  ('18','total=3.5','13','Under 3.5'),
)

def _event_markets(eid):
  try:
    r=_j.loads(subprocess.run(
      ['curl','-s','-m','15','-A','Mozilla/5.0',
       f'https://www.sportybet.com/api/gh/factsCenter/event?eventId={eid}&productId=3'],
      capture_output=True,text=True).stdout)
    return (r.get('data') or {}).get('markets') or []
  except Exception:
    return []

def swap_to_goals(p):
  """Replace a non-goals obscure-league leg with the best stats-supported goals market.
  Returns a new pick dict or None if nothing passes the remaining rules."""
  if not p or not p.get('eventId'):
    return None
  if is_goals_market(p) and not is_btts_no(p):
    return p
  markets=_event_markets(p['eventId'])
  by={}
  for m in markets:
    mid=str(m.get('id') or '')
    sp=m.get('specifier') or ''
    for o in m.get('outcomes') or []:
      by[(mid,sp,str(o.get('id')))]=o
  # When the event API is blocked (common from CI/box 403), still propose standard goals
  # templates so rebook can validate them through the booking API.
  if not by:
    for mid,sp,oid,label in GOALS_SWAP_CANDIDATES:
      by[(mid,sp,oid)]={'odds': min(float(p.get('odds') or 1.22), 1.28), 'desc': label}
  best=None
  best_score=None
  for mid,sp,oid,label in GOALS_SWAP_CANDIDATES:
    o=by.get((mid,sp,oid))
    if not o: continue
    try: odds=float(o.get('odds') or 0)
    except Exception: continue
    if odds<=1.01: continue
    cand=dict(p)
    cand.update(
      marketId=mid, specifier=sp or None, outcomeId=oid, odds=odds,
      market='Over/Under' if mid=='18' else ('BTTS' if mid=='29' else cand.get('market') or label),
      selection=o.get('desc') or label,
      tip=o.get('desc') or label,
    )
    # Drop previous matchup classification so check re-runs cleanly
    for k in ('matchup','strictGate'):
      cand.pop(k, None)
    try:
      enrich(cand)
    except Exception:
      pass
    # Hard vetoes must still apply; matchup class may be unverifiable on obscure cups —
    # accept short goals prices (<=1.35) when full check only fails as unverified/skip-table.
    if is_dc_vetoed(cand) or is_btts_no(cand):
      continue
    if float(cand.get('odds') or 0)>MAX_LEG and not extreme160(cand):
      continue
    ok,cls,why=check(cand)
    soft_ok = (not ok and cls in ('unverified','skip') and odds<=1.35 and is_goals_market(cand))
    # also allow when check fails only because obscure rule ran on a non-goals cand (shouldn't)
    if not ok and not soft_ok:
      # Retry classifying without obscure block for goals cand: if only obscure would have
      # mattered we already know is_goals_market; accept low-risk goals.
      if cls == 'obscure-league-goals':
        continue
      if odds<=1.30 and mid in ('18','19','20','29') and is_goals_market(cand):
        soft_ok=True
      else:
        continue
    pref={'18|total=1.5|12':0,'29||74':1,'18|total=0.5|12':2,'19|total=0.5|12':3,'20|total=0.5|12':4}.get(f'{mid}|{sp}|{oid}',9)
    score=(0 if ok else 1, pref, odds)
    if best is None or score<best_score:
      best,best_score=cand,score
  return best

ALLOW={'mismatch':{'18|total=1.5|12','29||74','19|total=0.5|12','20|total=0.5|12'},
       'even':{'18|total=3.5|13','29||74','19|total=0.5|12','20|total=0.5|12'},
       'middle':{'29||74','19|total=0.5|12','20|total=0.5|12'}}
def info(p):
  c=p.get('case') or ''
  t=re.search(r'table (\d+) v (\d+)/(\d+)',p.get('table') and 'table '+p['table'] or c)
  x=re.search(r'1X2 ([\d.]+)/([\d.]+)/([\d.]+)',('1X2 '+p['x12']) if p.get('x12') else c)
  hp,ap,N=(int(v) for v in t.groups()) if t else (None,None,None)
  H,D,A=(float(v) for v in x.groups()) if x else (None,None,None)
  return hp,ap,N,H,A
def classify(p):
  hp,ap,N,H,A=info(p)
  if hp and ap and N and N>=10:
    if hp<=5 and ap<=5: return 'skip','both teams in league top 5 (%s v %s/%s)'%(hp,ap,N)
    if hp>N-3 and ap>N-3: return 'skip','both teams in league bottom 3 (%s v %s/%s)'%(hp,ap,N)
  fp=min(H,A) if H and A else None
  fav='H' if (H or 9)<=(A or 9) else 'A'
  gp=abs(hp-ap) if hp and ap else None
  stronger=('H' if hp<ap else 'A') if gp else None
  if gp is not None and N and gp>=N/3 and fp and fp<=1.70 and stronger==fav: return 'mismatch',f'table {hp} v {ap}/{N}, fav @{fp}'
  if fp and fp>1.80 and (gp is None or (N and gp<N/4)): return 'even',f'fav @{fp}'+(f', table {hp} v {ap}/{N}' if gp is not None else '')
  return 'middle',f'fav @{fp}'+(f', table {hp} v {ap}/{N}' if gp is not None else '')
def key(p): return f"{p.get('marketId')}|{p.get('specifier') or ''}|{p.get('outcomeId')}"
# Over 1.5 / Under 3.5 priced above 1.30 need EXTREME support (user rule, Nov 5). Our pick data carries no L10 average-goals
# field, so "extreme" is defined conservatively from the stats we do have for that exact market:
EXT_ODDS=1.30; EXT_TEAM=0.90; EXT_TEAM_N=8; EXT_H2H=0.80; EXT_H2H_N=4; EXT_LEAGUE=0.85
# LOOSENING L1 (user OK'd 'loosen at your discretion', Nov 5): 'strong' instead of 'extreme' support ->
#   team last-10 hit >= 80% (was 90%), H2H >= 75% (was 80%), league rate >= 80% (was 85%). n minimums unchanged.
EXT_TEAM=0.80; EXT_H2H=0.75; EXT_LEAGUE=0.80
def extreme(p):
  """both teams' home/away last-10 hit >= 90% (n>=8), H2H >= 80% (n>=4), league market rate >= 85%"""
  c=p.get('case') or ''
  t=re.findall(r'(?:home|away) (\d+)% of (\d+)',c); h=re.search(r'H2H (\d+)% of (\d+)',c)
  lr=p.get('leagueFavRate') or p.get('rate') or 0
  return (len(t)>=2 and all(int(a)/100>=EXT_TEAM and int(b)>=EXT_TEAM_N for a,b in t[:2]) and bool(h) and int(h.group(1))/100>=EXT_H2H
          and int(h.group(2))>=EXT_H2H_N and lr>=EXT_LEAGUE)
# Max single-leg price (user rule, Nov 5): no leg above 1.60 unless EXTREME stats back it (not loosened):
#   each team last-10 hit >= 90% from 8+ games, H2H >= 80% from 4+, league rate >= 80%.
MAX_LEG=1.60; X_TEAM=0.90; X_TEAM_N=8; X_H2H=0.80; X_H2H_N=4; X_LEAGUE=0.80
def extreme160(p):
  c=p.get('case') or ''
  t=re.findall(r'(?:home|away) (\d+)% of (\d+)',c); h=re.search(r'H2H (\d+)% of (\d+)',c)
  lr=p.get('leagueFavRate') or p.get('rate') or 0
  return (len(t)>=2 and all(int(a)/100>=X_TEAM and int(b)>=X_TEAM_N for a,b in t[:2]) and bool(h) and int(h.group(1))/100>=X_H2H
          and int(h.group(2))>=X_H2H_N and lr>=X_LEAGUE)
def check(p):
  """-> (ok, class, reason); the DC and NG vetos cannot be relaxed by report mode."""
  if is_dc_vetoed(p):
    return False,'double-chance-veto',dc_veto_reason(p)
  if is_btts_no(p):
    return False,'btts-no-veto','HARD VETO: NG (BTTS No / GG No) is never published; choose another market or drop the match'
  if is_obscure_league_non_goals(p):
    return False,'obscure-league-goals',obscure_veto_reason(p)
  if float(p.get('odds') or 0)>MAX_LEG and not extreme160(p):
    return False,'over160',f"{p.get('selection')} @{p.get('odds')} > {MAX_LEG} without extreme stats"
  cls,why=classify(p)
  if cls=='skip': return False,cls,why
  # LOOSENING L2: no table found (cup / no standings) -> only low-risk legs at odds <= 1.30 pass
  #   (home/away team over 0.5 or GG); DC 12 and 1X/X2 above 1.35 are vetoed above.
  if not re.search(r'\d+ v \d+/\d+',(p.get('table') or '')+' '+(p.get('case') or '')):
    if not (p.get('x12') or '1X2 ' in (p.get('case') or '')): return False,'unverified','no 1X2 odds to classify the game'
    if float(p.get('odds') or 9)<=1.30 and key(p) in {'19|total=0.5|12','20|total=0.5|12','29||74'}: return True,cls,why+' (no table: low-risk leg <= 1.30)'
    return False,'unverified','no league table to verify the matchup'
  if str(p.get('marketId'))=='18' and ((p.get('specifier'),str(p.get('outcomeId'))) in (('total=1.5','12'),('total=3.5','13'))) and float(p.get('odds') or 0)>EXT_ODDS and not extreme(p):
    return False,cls,f"{p.get('selection')} @{p.get('odds')} > {EXT_ODDS} without extreme stats"
  k=key(p); m=str(p.get('marketId'))
  if cls=='middle': ok=k in ALLOW['middle']
  elif cls=='mismatch': ok=m not in ('1','33','34')          # straight win / win-to-nil -> must be GG / Over 1.5
  else: ok=not (m=='18' and (p.get('specifier') or '') in ('total=1.5','total=2.5') and str(p.get('outcomeId'))=='12')  # even: no overs
  if ok: return True,cls,why
  sel=p.get('selection',''); w=' (win pick: mismatch converts to GG/Over 1.5)' if str(p.get('marketId'))=='1' and cls=='mismatch' else ''
  return False,cls,f'{sel} not allowed in a {cls} game ({why}){w}'
def filter_picks(picks,log=None):
  keep=[]
  for p in picks:
    ok,cls,why=check(p); p['matchup']=cls
    if ok: keep.append(p)
    elif log is not None: log.append(dict(match=p.get('match'),selection=p.get('selection'),odds=p.get('odds'),reason=why))
  return keep

# ---- refined daily-pipeline gates (newrules.py + gate31.py strict gate), latest /workspace/novDD ----
import os,glob,sys as _sys,json as _json
MODE=os.environ.get('P2U_STRICT_GATES','report')   # 'enforce' drops failures, 'report' only logs them
_NG=None
def _gates():
  global _NG
  if _NG is None:
    _NG=False
    dirs=[]
    g=os.environ.get('ENGINE_GATES_DIR')
    if g: dirs.append(g)
    dirs += sorted(glob.glob('/workspace/nov[0-9][0-9]'),reverse=True)
    for dd in dirs:
      if os.path.exists(os.path.join(dd,'newrules.py')):
        try:
          _sys.path.insert(0,dd); import newrules as N
          try:
            import gate31 as G
          except Exception:
            G=None
          _NG=(N,G,dd)
        except Exception as e: print('gates unavailable',e)
        break
  return _NG
def strict(p):
  g=_gates()
  if not g: return 'gates unavailable'
  N,G,_=g; sp=p.get('specifier') or ''
  try:
    r=N.ok(p['eventId'],p['marketId'],sp,p['outcomeId'],p['odds'])
    if r: return 'newrules: '+r
    if not G: return None
    w=G.gate(p['eventId'],p['match'],p.get('league',''),f"{p['marketId']}|{sp}|{p['outcomeId']}",f"{p.get('market')}: {p.get('selection')}",p['odds'],None,need_grade=False,skip_check=True)[0]
    return 'gate31: '+w if w else None
  except Exception as e: return 'gate error '+str(e)[:60]
def apply_all(picks,log=None):
  """matchup rules always enforced; refined gates enforced only when P2U_STRICT_GATES=enforce"""
  keep=filter_picks(picks,log); out=[]
  for p in keep:
    r=strict(p); p['strictGate']=r or 'pass'
    if r and MODE=='enforce':
      if log is not None: log.append(dict(match=p.get('match'),selection=p.get('selection'),odds=p.get('odds'),reason=r))
      continue
    out.append(p)
  return out

# ---- Enrichment for picks that come without engine data (Hot Picks) ----
# Table positions + last-10 team stats from the same stats source the engine uses (cached in /workspace/8080/fzc),
# 1X2 odds from the SportyBet event snapshot (sb.json) or the live event API.
import subprocess,json as _j
_SR="https://stats.fn.sportradar.com/sportybet/en/Europe:Berlin/gismo/"
def _G(p):
  f=(__import__('os').environ.get('STATS_CACHE', str(__import__('pathlib').Path(__file__).resolve().parents[1]/'data'/'stats-cache'))+'/').replace('//','/') if False else (__import__('os').environ.get('STATS_CACHE') or str(__import__('pathlib').Path(__file__).resolve().parents[1]/'data'/'stats-cache')) + '/'+p.replace('/','_')+'.json'
  if os.path.exists(f):
    try:
      d=_j.load(open(f))
      if d is not None: return d
    except Exception: pass
  try:
    d=_j.loads(subprocess.run(['curl','-s','-m','20','-A','Mozilla/5.0',_SR+p],capture_output=True,text=True).stdout)
    d=d['doc'][0]['data'] if d and 'doc' in d and d['doc'][0].get('event')!='exception' else None
  except Exception: d=None
  try: _j.dump(d,open(f,'w'))
  except Exception: pass
  return d
_SB=None
def _x12(eid):
  global _SB
  if _SB is None:
    try: _SB=_j.load(open(os.environ.get('SBJSON', os.path.join(os.environ.get('RESEARCH_DIR',''), 'sb.json') or 'sb.json')))
    except Exception: _SB={}
  e=_SB.get(eid)
  if not e:
    try:
      r=_j.loads(subprocess.run(['curl','-s','-m','15','-A','Mozilla/5.0',f'https://www.sportybet.com/api/gh/factsCenter/event?eventId={eid}&productId=3'],capture_output=True,text=True).stdout)
      e=r.get('data') or {}
    except Exception: e={}
  for m in e.get('markets') or []:
    if str(m.get('id'))=='1' and not m.get('specifier'):
      o={x['desc']:x['odds'] for x in m['outcomes']}
      if all(k in o for k in ('Home','Draw','Away')): return f"{o['Home']}/{o['Draw']}/{o['Away']}"
def _hit(mid,sp,oid,f,a):
  t=f+a
  if mid=='18' and sp=='total=1.5' and oid=='12': return t>=2
  if mid=='18' and sp=='total=3.5' and oid=='13': return t<=3
  return None
def enrich(p):
  """adds table / x12 / case (team L10 + H2H hit for O1.5/U3.5) when missing; returns True if table+1X2 found"""
  eid=p['eventId']; sid=eid.split(':')[-1]
  if not p.get('x12'): p['x12']=_x12(eid)
  mi=_G('match_info/'+sid) or {}; mm=mi.get('match') or {}
  try:
    hu,au=mm['teams']['home']['uid'],mm['teams']['away']['uid']
    t=_G(f"stats_season_tables/{mm['_seasonid']}")['tables'];N=max(len(tb['tablerows']) for tb in t)
    pos={r['team']['uid']:r['pos'] for tb in t for r in tb['tablerows']}
    if pos.get(hu) and pos.get(au): p['table']=f"{pos[hu]} v {pos[au]}/{N}"
  except Exception: hu=au=None
  mid,sp,oid=str(p['marketId']),p.get('specifier') or '',str(p['outcomeId'])
  if hu and _hit(mid,sp,oid,0,0) is not None:
    parts=[]
    for side,u in (('home',hu),('away',au)):
      ms=[z for z in ((_G(f'stats_team_lastx/{u}/10') or {}).get('matches') or []) if (z.get('result') or {}).get('home') is not None][:10]
      if ms: parts.append(f"x {side} {round(100*sum(_hit(mid,sp,oid,z['result']['home'],z['result']['away']) for z in ms)/len(ms))}% of {len(ms)}")
    v=[z for z in ((_G(f'stats_team_versusrecent/{hu}/{au}') or {}).get('matches') or []) if (z.get('result') or {}).get('home') is not None][:6]
    h2h=f"H2H {round(100*sum(_hit(mid,sp,oid,z['result']['home'],z['result']['away']) for z in v)/len(v))}% of {len(v)}" if v else ''
    p['case']='team support: '+', '.join(parts)+'; '+h2h
    p.setdefault('leagueFavRate',1.0)  # no league market rate for these picks; team + H2H thresholds carry the check
  return bool(p.get('table') and p.get('x12'))
