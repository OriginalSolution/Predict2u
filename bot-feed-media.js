/* Predict2U — media/report generator from the bot picks feed (picks.json + picks-history.json).
   Replaces the old data.js / API-Football generators. No network calls.
   Usage: node bot-feed-media.js picks|results|social|tracker [--date YYYY-MM-DD]
     picks   -> acca-1..N.png (one per SportyBet slip, today) + today.png (summary card)
     results -> results.png + results/<yesterday>.png (won/lost legs, yesterday)
     social  -> social-today.png + social-results.png
     tracker -> track-report.txt (per-bot / market / league record, last 30 days)
   Library: require('./bot-feed-media.js') -> { load, settledOn, record, picksOn } */
const fs=require('fs'),path=require('path');const HERE=__dirname;
const dstr=d=>d.toISOString().slice(0,10);
const arg=k=>{const i=process.argv.indexOf(k);return i>0?process.argv[i+1]:null;};
const TODAY=arg('--date')||dstr(new Date());
const YDAY=dstr(new Date(Date.parse(TODAY+'T12:00:00Z')-864e5));
function load(){
  let feed={slips:[]},hist={days:{}};
  try{feed=JSON.parse(fs.readFileSync(path.join(HERE,'picks.json'),'utf8'));}catch(e){}
  try{hist=JSON.parse(fs.readFileSync(path.join(HERE,'picks-history.json'),'utf8'));}catch(e){}
  return {feed,hist};
}
const {feed,hist}=load();
function legsOn(day){ // history first, fall back to feed
  if(hist.days&&hist.days[day])return hist.days[day];
  const out=[];(feed.slips||[]).forEach(s=>s.legs.forEach(x=>{if(x.date===day)out.push({source:s.source,bot:s.bot,code:s.code,...x});}));return out;
}
// dedupe the same match+pick across slips/bots for honest records
function uniq(legs){const m=new Map();legs.forEach(x=>{const k=x.source+'|'+x.match+'|'+x.market+'|'+x.selection;if(!m.has(k)||m.get(k).result==='pending')m.set(k,x);});return [...m.values()];}
const settledOn=day=>uniq(legsOn(day)).filter(x=>x.result==='won'||x.result==='lost');
const picksOn=day=>uniq(legsOn(day));
const record=l=>{const w=l.filter(x=>x.result==='won').length,lo=l.filter(x=>x.result==='lost').length;return {w,l:lo,n:w+lo,pct:w+lo?Math.round(100*w/(w+lo)):0};};
const slipsOn=day=>(feed.slips||[]).filter(s=>(s.dates||[s.date]).includes(day));
module.exports={load,settledOn,record,picksOn,slipsOn,TODAY,YDAY};
if(require.main!==module)return;

const esc=s=>String(s==null?'':s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const trunc=(s,n)=>{s=String(s||'');return s.length>n?s.slice(0,n-1)+'…':s;};
const kot=iso=>{const d=new Date(iso);return isNaN(d)?'':d.toISOString().slice(11,16);};
let logo='';try{logo='data:image/png;base64,'+fs.readFileSync(path.join(HERE,'icon-512.png')).toString('base64');}catch(e){}
const W=1080,pad=60,cw=W-pad*2;
function frame(title,sub,body,H){return `<svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}">
<rect width="${W}" height="${H}" fill="#0a0e17"/>${logo?`<image href="${logo}" x="${pad}" y="36" width="90" height="90"/>`:''}
<text x="${pad+110}" y="88" font-family="Arial,sans-serif" font-weight="bold" font-size="50" fill="#fff">Predict<tspan fill="#4CAF27">2u</tspan></text>
<text x="${pad+110}" y="120" font-family="Arial,sans-serif" font-weight="bold" font-size="20" fill="#8a93a6" letter-spacing="2">${esc(title)}</text>
<text x="${pad}" y="185" font-family="Arial,sans-serif" font-weight="bold" font-size="30" fill="#4CAF27">${esc(sub)}</text>
${body}
<text x="${W/2}" y="${H-60}" text-anchor="middle" font-family="Arial,sans-serif" font-size="22" fill="#7ee05a">predict2u.com · every result posted, win or lose</text>
<text x="${pad}" y="${H-24}" font-family="Arial,sans-serif" font-size="17" fill="#5a6478">Bot picks, not guarantees. 18+ · Gamble responsibly.</text></svg>`;}
function rowsSvg(legs,y0,withResult){let s='',y=y0;for(const x of legs){
  const col=x.result==='won'?'#4CAF27':x.result==='lost'?'#c0392b':'#3b4a63';
  s+=`<rect x="${pad}" y="${y}" width="${cw}" height="84" rx="14" fill="rgba(255,255,255,.05)" stroke="${col}" stroke-width="2"/>`;
  s+=`<text x="${pad+22}" y="${y+35}" font-family="Arial,sans-serif" font-weight="bold" font-size="26" fill="#fff">${esc(trunc(x.match,30))}</text>`;
  s+=`<text x="${pad+22}" y="${y+66}" font-family="Arial,sans-serif" font-size="19" fill="#8a93a6">${esc(kot(x.kickoff))} · ${esc(trunc(x.league,30))} · ${esc(trunc(x.market,24))}</text>`;
  s+=`<text x="${pad+cw-150}" y="${y+35}" text-anchor="end" font-family="Arial,sans-serif" font-weight="bold" font-size="23" fill="#cfd6e4">${esc(trunc(x.selection,17))}</text>`;
  s+=`<text x="${pad+cw-150}" y="${y+66}" text-anchor="end" font-family="Arial,sans-serif" font-size="20" fill="#fbbf24">@${x.odds==null?'—':Number(x.odds).toFixed(2)}</text>`;
  s+=`<rect x="${pad+cw-130}" y="${y+20}" width="112" height="44" rx="10" fill="${col}"/><text x="${pad+cw-74}" y="${y+50}" text-anchor="middle" font-family="Arial,sans-serif" font-weight="bold" font-size="19" fill="#fff">${esc((x.result||'pending').toUpperCase())}</text>`;
  y+=96;}return {s,y};}
async function write(name,svg){
  fs.writeFileSync(path.join(HERE,name+'.svg'),svg);
  try{const sharp=require('sharp');const buf=await sharp(Buffer.from(svg)).png().toBuffer();fs.writeFileSync(path.join(HERE,name+'.png'),buf);console.log(name+'.png written');return buf;}
  catch(e){console.log('PNG conversion failed for',name,e.message);return null;}
}
const MAX_SLIPS=+(process.env.MAX_SLIPS||12),MAX_LEGS=14;
async function picks(){
  const slips=[];const all=slipsOn(TODAY).map(s=>({...s,legs:s.legs.filter(x=>x.date===TODAY)})).filter(s=>s.legs.length)
    .sort((a,b)=>a.legs.length-b.legs.length||(a.firstKickoff||'').localeCompare(b.firstKickoff||''));
  { // fair share per bot, shortest slips first, capped at MAX_SLIPS
    const by={};all.forEach(s=>(by[s.source]=by[s.source]||[]).push(s));const keys=Object.keys(by);const pick=[];
    for(let i=0;pick.length<MAX_SLIPS&&keys.some(k=>by[k][i]);i++)keys.forEach(k=>{if(by[k][i]&&pick.length<MAX_SLIPS)pick.push(by[k][i]);});
    slips.push(...pick);
  }
  if(!slips.length){console.log('No bot slips for',TODAY,'— nothing to render (honest skip).');return;}
  let i=0;for(const s of slips){i++;const legs=s.legs.slice(0,MAX_LEGS);
    const tot=s.legs.reduce((a,x)=>a*Number(x.odds||1),1);
    const head=`<text x="${pad}" y="228" font-family="Arial,sans-serif" font-size="24" fill="#cfd6e4">${esc(s.bot)} · ${s.legs.length} legs · total @${tot.toFixed(2)}${s.legs.length>legs.length?` (first ${legs.length} shown)`:''}</text>`+
      (s.code?`<text x="${pad}" y="264" font-family="Arial,sans-serif" font-weight="bold" font-size="26" fill="#fbbf24">SportyBet code: ${esc(s.code)}</text>`:'');
    const r=rowsSvg(legs,290);await write('acca-'+i,frame("TODAY'S SLIP "+i+'/'+slips.length,TODAY,head+r.s,r.y+110));}
  // summary card: one line per slip
  let body='',y=230;for(const s of slips){const tot=s.legs.reduce((a,x)=>a*Number(x.odds||1),1);
    body+=`<rect x="${pad}" y="${y}" width="${cw}" height="70" rx="12" fill="rgba(255,255,255,.05)"/><text x="${pad+20}" y="${y+30}" font-family="Arial,sans-serif" font-weight="bold" font-size="24" fill="#fff">${esc(s.bot)} · ${s.legs.length} legs @${tot.toFixed(2)}</text><text x="${pad+20}" y="${y+58}" font-family="Arial,sans-serif" font-size="18" fill="#8a93a6">${esc(trunc(s.build||'',60))}</text><text x="${pad+cw-20}" y="${y+44}" text-anchor="end" font-family="Arial,sans-serif" font-weight="bold" font-size="28" fill="#fbbf24">${esc(s.code||'')}</text>`;y+=82;}
  const sv=frame("TODAY'S BOT SLIPS · SPORTYBET CODES",TODAY,body,y+110);await write('today',sv);
  fs.writeFileSync(path.join(HERE,'today-slips.txt'),slips.map((s,k)=>`${k+1}. ${s.bot} — ${s.legs.length} legs — code ${s.code||'n/a'} — ${s.link||''}`).join('\n')+'\n');
}
async function results(){
  const legs=settledOn(YDAY);if(!legs.length){console.log('No settled bot picks for',YDAY,'— no results image.');try{fs.unlinkSync(path.join(HERE,'results.png'));}catch(e){}return;}
  const r=record(legs);const show=legs.sort((a,b)=>(a.kickoff||'').localeCompare(b.kickoff||'')).slice(0,30);
  const per={};legs.forEach(x=>{(per[x.bot]=per[x.bot]||[]).push(x);});
  const head=`<text x="${pad}" y="228" font-family="Arial,sans-serif" font-size="26" fill="#cfd6e4">${r.w} won · ${r.l} lost · ${r.pct}% · `+Object.entries(per).map(([b,l])=>{const q=record(l);return `${esc(b)} ${q.w}-${q.l}`;}).join(' · ')+(legs.length>show.length?` (first ${show.length} shown)`:'')+`</text>`;
  const rr=rowsSvg(show,260);const buf=await write('results',frame("YESTERDAY'S RESULTS",YDAY,head+rr.s,rr.y+110));
  if(buf){fs.mkdirSync(path.join(HERE,'results'),{recursive:true});fs.writeFileSync(path.join(HERE,'results',YDAY+'.png'),buf);}
  console.log(`Results ${YDAY}: ${r.w}W ${r.l}L (${r.pct}%)`);
}
async function social(){
  const t=picksOn(TODAY);const slips=slipsOn(TODAY);
  if(t.length){const top=t.filter(x=>x.confidence!=null).sort((a,b)=>b.confidence-a.confidence).concat(t.filter(x=>x.confidence==null)).slice(0,8);
    const head=`<text x="${pad}" y="228" font-family="Arial,sans-serif" font-size="24" fill="#cfd6e4">${t.length} picks · ${slips.length} SportyBet slips · top confidence shown</text>`;
    const r=rowsSvg(top,260);await write('social-today',frame("TODAY'S BOT PICKS",TODAY,head+r.s,r.y+110));}
  else{try{fs.unlinkSync(path.join(HERE,'social-today.png'));}catch(e){}console.log('social-today: nothing to render');}
  const y=settledOn(YDAY);if(y.length){const r=record(y);
    const body=`<text x="${W/2}" y="420" text-anchor="middle" font-family="Arial,sans-serif" font-weight="900" font-size="130"><tspan fill="#4CAF27">${r.w}W</tspan><tspan fill="#5c6f5f"> – </tspan><tspan fill="#e07a7a">${r.l}L</tspan></text><text x="${W/2}" y="500" text-anchor="middle" font-family="Arial,sans-serif" font-size="34" fill="#cfd6e4">${r.pct}% strike rate</text>`;
    await write('social-results',frame("YESTERDAY'S RESULTS",YDAY,body,680));}
  else{try{fs.unlinkSync(path.join(HERE,'social-results.png'));}catch(e){}console.log('social-results: nothing settled');}
}
function tracker(){
  const all=[];for(let i=1;i<=30;i++){const d=dstr(new Date(Date.parse(TODAY+'T12:00:00Z')-i*864e5));settledOn(d).forEach(x=>all.push({...x,day:d}));}
  const grp=(f)=>{const m={};all.forEach(x=>{const k=f(x)||'?';(m[k]=m[k]||[]).push(x);});return Object.entries(m).map(([k,l])=>({k,...record(l)})).sort((a,b)=>b.n-a.n);};
  const line=o=>`  ${trunc(o.k,44).padEnd(45)} ${String(o.w).padStart(4)}W ${String(o.l).padStart(4)}L  ${String(o.pct).padStart(3)}%  (n=${o.n})`;
  const r=record(all);const y=record(settledOn(YDAY));
  const out=[`PREDICT2U BOT TRACKER — ${TODAY} (last 30 days, settled picks from picks-history.json)`,'',
    `Yesterday (${YDAY}): ${y.w}W ${y.l}L (${y.pct}%)`,`Last 30 days: ${r.w}W ${r.l}L (${r.pct}%), n=${r.n}`,'',
    'BY BOT',...grp(x=>x.bot).map(line),'','BY MARKET (top 15)',...grp(x=>x.market).slice(0,15).map(line),'','BY LEAGUE (top 15)',...grp(x=>x.league).slice(0,15).map(line),'',
    "TODAY'S SLIPS",...slipsOn(TODAY).map(s=>`  ${s.bot} — ${s.legs.filter(x=>x.date===TODAY).length} legs — code ${s.code||'n/a'} — ${s.link||''}`)];
  fs.writeFileSync(path.join(HERE,'track-report.txt'),out.join('\n')+'\n');console.log(out.slice(0,8).join('\n'));
}
(async()=>{const m=process.argv[2];
  if(m==='picks')await picks();else if(m==='results')await results();else if(m==='social')await social();else if(m==='tracker')tracker();
  else{console.log('usage: node bot-feed-media.js picks|results|social|tracker [--date YYYY-MM-DD]');process.exit(2);}})();
