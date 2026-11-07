import re
ARG=r'^Argentina';RW=r'Rwanda';PAN=r'^Panama';KAZ=r'^Kazakhstan Premier';THA=r'Thai League 1';UKR=r'^Ukraine Premier';FIJ=r'^Fiji'
ITAB=r'^Italy Serie [AB]\b';ITABC=r'^Italy Serie [ABC]\b';ITA=r'^Italy'
GOALY=[r'^Turkiye 2\. Lig',r'^Germany Oberliga',r'^Kosovo',r'^Norway (2nd|3rd) Division',r'^San Marino',r'^USA MLS']
DRAWE=[r'^Saudi',r'^Italy Serie [BC]\b',r'^Scotland Championship',r'^Austria Bundesliga',r'CAF Confederations',r'^Denmark Superliga',r'^Chile Primera Division',r'^Germany 3\. Liga',r'^Egypt',r'Nakotnes',r'^Lithuania I Lyga',r'^Malta Premier',r'^Russia Premier',r'^Serbia Super']
AV={'WIN':[ITAB,r'^Uruguay Primera Division',r'^Saudi',r'^Serbia Super']+DRAWE,
 'DNB':[ARG,RW,PAN,KAZ,THA],'GG':[r'^Hungary NB I$',ARG,RW,r'^Colombia (Liga DIMAYOR|Primera A)',r'^Guatemala Liga Nacional',THA],
 'O15':[ARG,RW,PAN,KAZ,THA,FIJ],'O25':[ITABC,KAZ,RW,ARG,UKR,THA],'O35':[ITA,KAZ,RW,ARG,THA,UKR],
 'U35':GOALY,'U25':GOALY,'U15':GOALY,'TS':[ARG,RW,THA,PAN,KAZ,UKR]}
HALF=('1st','2nd','Half','half','Corner','Shot','Booking','Card')
def kind(pk):
  if any(h in pk for h in HALF):return None
  p=pk.replace('Over/Under: ','').replace('Over/Under - ','')
  if 'DNB' in p or 'Draw No Bet' in p:return 'DNB'
  if p.startswith(('GG','GG/NG: Yes')) or p=='GG':return 'GG'
  if 'to win' in p or p.startswith('1X2'):return 'WIN'
  m=re.search(r'(Over|Under) (\d\.5)',p) or re.match(r'([OU])(\d\.5)',p)
  team=' Over/Under' in pk and not pk.startswith('Over/Under') or re.search(r'\w Over 1\.5$',pk.split(':')[0]) and pk.split(':')[0] not in('Over 1.5',)
  if m:
    ou=m.group(1)[0];ln=m.group(2)
    if team:return 'TS' if ou=='O' and ln=='0.5' else None
    if 'Draw or Over 2.5' in p:return 'O25'
    if 'Draw or Under' in p:return 'U25'
    return f"{ou}{ln.replace('.','')}"
def viol(lg,pk):
  k=kind(pk)
  if not k or k not in AV:return None
  for r in AV[k]:
    if re.search(r,lg):return f"{k} AVOID in {lg} (rulebook)"
