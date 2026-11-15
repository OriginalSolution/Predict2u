/* Predict2U v276 — builds a small rolling public data bundle from data.js. */
'use strict';
const fs=require('fs');
const path=require('path');
const ROOT=__dirname;
const source=path.join(ROOT,'data.js');
const target=path.join(ROOT,'current-data.js');
const metaTarget=path.join(ROOT,'data-meta.json');
function balanced(text,start,open,close){let depth=0,quote=null,escaped=false;for(let i=start;i<text.length;i++){const ch=text[i];if(quote){if(escaped)escaped=false;else if(ch==='\\')escaped=true;else if(ch===quote)quote=null;continue;}if(ch==='"'||ch==="'"){quote=ch;continue;}if(ch===open)depth++;else if(ch===close&&--depth===0)return i+1;}return-1;}
function objectAssignment(raw,name){const marker=raw.indexOf(`window.${name}`);if(marker<0)return null;const eq=raw.indexOf('=',marker),start=raw.indexOf('{',eq);if(eq<0||start<0)return null;const end=balanced(raw,start,'{','}');if(end<0)return null;try{return JSON.parse(raw.slice(start,end));}catch(_){return null;}}
function arrayAssignment(raw,name){const marker=raw.indexOf(`window.${name}`);if(marker<0)return [];const eq=raw.indexOf('=',marker),start=raw.indexOf('[',eq);if(eq<0||start<0)return [];const end=balanced(raw,start,'[',']');if(end<0)return [];try{const rows=JSON.parse(raw.slice(start,end));return Array.isArray(rows)?rows:[];}catch(_){return [];}}
function read(){
  const raw=fs.readFileSync(source,'utf8');
  const match=raw.match(/window\.MATCHES\s*=\s*(\[[\s\S]*\])\s*;?\s*$/);
  if(!match)throw new Error('data.js does not contain window.MATCHES.');
  const updated=(raw.match(/window\.DATA_UPDATED\s*=\s*["']([^"']+)["']/)||[])[1]||null;
  const governance=objectAssignment(raw,'P2U_GOVERNANCE_CONTEXT');
  return {matches:JSON.parse(match[1]),updated,governance};
}
function readFixtures(){
  const file=path.join(ROOT,'fixtures.js');
  if(!fs.existsSync(file))return [];
  try{return arrayAssignment(fs.readFileSync(file,'utf8'),'FIXTURES');}
  catch(_){return [];}
}
function readSportybet(){
  try{
    const {readSportybetRows,sportyRowToFixture}=require('./hydrate-fixtures-from-sportybet.js');
    return readSportybetRows().map(sportyRowToFixture);
  }catch(_){return [];}
}
const iso=d=>d.toISOString().slice(0,10);
const add=(d,n)=>{const x=new Date(d);x.setUTCDate(x.getUTCDate()+n);return x;};
const dateOf=m=>String(m&&m.matchDate||m&&m.kickoff||'').slice(0,10);
function inWindow(m,from,to){const d=dateOf(m);return d&&d>=from&&d<=to;}
// Keep current-data.js under the 9 MB site-quality limit (release-gate-v264.js). Rows dated before
// today are kept for the date strip / history, but their per-match analysis is dead weight: SMT tips
// skip past fixtures (similar-strength-tips.js isOpenFixture) and the team page rebuilds the peer
// panel from venue PPG (fromFixture) when peerIntel is absent. Tier 1 always drops past peerIntel
// (~2 MB); tier 2 also drops past streak/profile blocks only if the bundle is still over budget.
const SIZE_BUDGET=8.5*1024*1024;
const PAST_HEAVY=['homeStreaks','awayStreaks','homeProfile','awayProfile'];
function slimPastRows(rows,today){
  const out={pastRows:0,droppedPeerIntel:0,droppedHeavy:0};
  const past=rows.filter(m=>{const d=dateOf(m);return d&&d<today;});
  out.pastRows=past.length;
  for(const m of past){if(m&&m.peerIntel!==undefined){delete m.peerIntel;out.droppedPeerIntel++;}}
  if(JSON.stringify(rows).length>SIZE_BUDGET){
    for(const m of past){for(const k of PAST_HEAVY){if(m&&m[k]!==undefined){delete m[k];out.droppedHeavy++;}}}
  }
  return out;
}
function run(now=new Date()){
  const {matches,updated,governance}=read();
  const today=iso(now);
  const from=iso(add(new Date(today+'T00:00:00Z'),-7));
  const to=iso(add(new Date(today+'T00:00:00Z'),7));
  let sourceMatches=matches;
  let hydratedFromFixtures=false;
  let hydratedFromSportybet=false;
  if(!sourceMatches.length){
    const fixtures=readFixtures();
    if(fixtures.length){
      sourceMatches=fixtures;
      hydratedFromFixtures=true;
      console.warn(`data.js has 0 matches — hydrating public bundle from ${fixtures.length} fixtures.js row(s) so dates still load.`);
    }
  }
  let rows=sourceMatches.filter(m=>inWindow(m,from,to));
  if(!rows.some(m=>dateOf(m)>=today)){
    const fixtureRows=readFixtures().filter(m=>inWindow(m,from,to)&&dateOf(m)>=today);
    if(fixtureRows.length){
      const seen=new Set(rows.map(m=>`${dateOf(m)}|${String(m.home||'').toLowerCase()}|${String(m.away||'').toLowerCase()}`));
      let added=0;
      for(const row of fixtureRows){
        const key=`${dateOf(row)}|${String(row.home||'').toLowerCase()}|${String(row.away||'').toLowerCase()}`;
        if(seen.has(key))continue;
        rows.push(row);
        seen.add(key);
        added++;
      }
      if(added){
        hydratedFromFixtures=true;
        console.warn(`Public bundle pulled ${added} current fixture(s) from fixtures.js.`);
      }
    }
  }
  const sporty=readSportybet();
  const sportyCurrent=sporty.filter(m=>inWindow(m,from,to));
  if((!rows.length||!rows.some(m=>dateOf(m)>=today))&&sportyCurrent.length){
    const seen=new Set(rows.map(m=>`${dateOf(m)}|${String(m.home||'').toLowerCase()}|${String(m.away||'').toLowerCase()}`));
    for(const row of sportyCurrent){
      const key=`${dateOf(row)}|${String(row.home||'').toLowerCase()}|${String(row.away||'').toLowerCase()}`;
      if(seen.has(key))continue;
      rows.push(row);
      sourceMatches.push(row);
      seen.add(key);
    }
    hydratedFromSportybet=true;
    console.warn(`Public bundle had no current dates — hydrated ${sportyCurrent.length} SportyBet fixture(s) so the date strip loads.`);
  }
  const dates=sourceMatches.map(dateOf).filter(Boolean).sort();
  const maxFixtureDate=dates[dates.length-1]||null;
  let fallback=false;
  if(!rows.length&&maxFixtureDate){
    fallback=true;
    const max=new Date(maxFixtureDate+'T00:00:00Z');
    const fallbackFrom=iso(add(max,-7));
    rows=sourceMatches.filter(m=>{const d=dateOf(m);return d&&d>=fallbackFrom&&d<=maxFixtureDate;});
  }
  rows.sort((a,b)=>dateOf(a).localeCompare(dateOf(b))||String(a.kickoff||'').localeCompare(String(b.kickoff||'')));
  let profileEnrichment=null;
  try{
    const {enrichMatches,loadLedger,writeSmtBundle}=require('./enrich-fixtures-from-profiles.js');
    profileEnrichment=enrichMatches(rows,loadLedger());
    if(profileEnrichment&&profileEnrichment.bothReady){
      console.warn(`Profile ledger attached to ${profileEnrichment.bothReady}/${rows.length} fixture(s) so Market Edges and Auto Picks can publish.`);
    }
    try{
      const smtRows=writeSmtBundle(rows);
      if(profileEnrichment)profileEnrichment.smtRows=smtRows;
      console.warn(`SMT board: ${smtRows} similar-market tip(s).`);
    }catch(error){
      console.warn(`SMT board skipped: ${error&&error.message?error.message:error}`);
    }
  }catch(error){
    console.warn(`Profile enrich skipped: ${error&&error.message?error.message:error}`);
  }
  const meta={
    version:'v287',generatedAt:new Date().toISOString(),sourceUpdatedAt:updated,
    today,window:{from,to},fallback,maxFixtureDate,totalSourceMatches:sourceMatches.length,publicMatches:rows.length,
    sharedGovernance:!!governance,hydratedFromFixtures,hydratedFromSportybet,
    profileReady:profileEnrichment?profileEnrichment.bothReady:0,
    profileAttached:profileEnrichment?profileEnrichment.attached:0
  };
  const slim=slimPastRows(rows,today);
  meta.slimmed=slim;
  const governanceLine=governance?`window.P2U_GOVERNANCE_CONTEXT=${JSON.stringify(governance)};\n`:'';
  fs.writeFileSync(target,`/* AUTO-GENERATED by build-public-data.js — do not edit. */\nwindow.P2U_DATA_META=${JSON.stringify(meta)};\nwindow.DATA_UPDATED=${JSON.stringify(updated||meta.generatedAt)};\n${governanceLine}window.MATCHES=${JSON.stringify(rows)};\n`,'utf8');
  fs.writeFileSync(metaTarget,JSON.stringify(meta,null,2)+'\n','utf8');
  console.log(`Public data: ${rows.length}/${matches.length} matches, ${(fs.statSync(target).size/1024/1024).toFixed(2)} MB; shared governance ${governance?'included':'not present'}${hydratedFromSportybet?' (sportybet hydrate)':''}.`);
  return meta;
}
if(require.main===module)run();
module.exports={run,objectAssignment,slimPastRows,SIZE_BUDGET};
