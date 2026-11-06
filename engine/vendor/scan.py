import json,os,subprocess,time
UA="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36"
OUT=os.environ.get("SBJSON") or os.path.join(os.environ.get("RESEARCH_DIR") or os.path.dirname(os.path.abspath(__file__)), "sb.json")
E={}
for p in range(1,120):
  u=f"https://www.sportybet.com/api/gh/factsCenter/pcUpcomingEvents?sportId=sr%3Asport%3A1&marketId=1%2C18&pageSize=100&pageNum={p}&option=1"
  d=json.loads(subprocess.run(['curl','-s','-m','40','-A',UA,u],capture_output=True,text=True).stdout)['data']
  if not d or 'tournaments' not in d: print('stop',p);break
  new=[e for t in d['tournaments'] for e in t['events']]
  for e in new: E[e['eventId']]=e
  if not new or len(E)>=d['totalNum']: break
os.makedirs(os.path.dirname(OUT) or '.', exist_ok=True)
json.dump(E,open(OUT,'w'));print(len(E), OUT)
