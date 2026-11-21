/* Predict2U v288 — builds a small rolling public data bundle from data.js. */
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

// Keep current-data.js well under the 9 MB release-gate (release-gate-v264.js).
// The board date strip is a Mon–Sun week, and assert-matches-present.js requires
// at least one row in yesterday…today+7. So the live window starts at the earlier
// of this week's Monday and yesterday, and runs through today+7. Older stale
// fixtures (especially last weekend's still-NS rows) are dropped. Past rows in
// that window are kept as lean fixtures so the date strip still counts games;
// today/future keep analysis fields, but nulls, duplicate ids, odds aliases and
// reconstructable evidence text are stripped. A short hydrator at the foot of
// current-data.js restores odds aliases (1/X/2, 1X/12/X2, GG/NG) for page code.
const HARD_LIMIT=9*1024*1024;
const SIZE_BUDGET=8.5*1024*1024;
const FUTURE_DAYS=7;
const ODDS_ALIAS_TO_CANON={'1':'home','2':'away','X':'draw','12':'dc12','1X':'dc1x','X2':'dcx2','GG':'bttsYes','NG':'bttsNo'};
const ODDS_CANON_TO_ALIAS={'home':'1','away':'2','draw':'X','dc12':'12','dc1x':'1X','dcx2':'X2','bttsYes':'GG','bttsNo':'NG'};
const PAST_KEEP=['id','home','away','league','country','kickoff','matchDate','status','statusLong','homeGoals','awayGoals','htHome','htAway','elapsed','odds','sportyGameId','source'];
const ODDS_HYDRATOR=';(function(){var A={home:"1",away:"2",draw:"X",dc12:"12",dc1x:"1X",dcx2:"X2",bttsYes:"GG",bttsNo:"NG"};var M=window.MATCHES||[];for(var i=0;i<M.length;i++){var o=M[i]&&M[i].odds;if(!o)continue;for(var k in A){if(o[k]!=null&&o[A[k]]==null)o[A[k]]=o[k];}}}());\n';

function weekStartIso(today){
  const d=new Date(today+'T00:00:00Z');
  const wd=d.getUTCDay();
  const back=wd===0?6:wd-1;
  d.setUTCDate(d.getUTCDate()-back);
  return iso(d);
}
function publicFrom(today){
  const yesterday=iso(add(new Date(today+'T00:00:00Z'),-1));
  const monday=weekStartIso(today);
  return monday<yesterday?monday:yesterday;
}
function publicTo(today){
  return iso(add(new Date(today+'T00:00:00Z'),FUTURE_DAYS));
}
function roundOdds(v){
  if(typeof v!=='number'||!Number.isFinite(v))return v;
  return Math.round(v*100)/100;
}
function roundNum(v){
  if(typeof v!=='number'||!Number.isFinite(v)||Number.isInteger(v))return v;
  return Math.round(v*1000)/1000;
}
function compactOdds(odds){
  if(!odds||typeof odds!=='object')return odds;
  const out={};
  for(const [key,value] of Object.entries(odds)){
    if(value==null)continue;
    const num=roundOdds(value);
    const canon=ODDS_ALIAS_TO_CANON[key];
    if(canon){
      if(out[canon]==null)out[canon]=num;
      continue;
    }
    if(out[key]==null)out[key]=num;
  }
  return out;
}
function compactPeerIntel(intel,opts){
  if(!intel||typeof intel!=='object')return intel;
  const maxEvidence=opts&&opts.maxEvidence!=null?opts.maxEvidence:8;
  const dropNotes=!!(opts&&opts.dropNotes);
  const dropMeaning=!!(opts&&opts.dropMeaning);
  const out={};
  for(const [key,value] of Object.entries(intel)){
    if(key==='notes'&&dropNotes)continue;
    if(value==null)continue;
    if(key==='tips'){
      if(!Array.isArray(value)||!value.length)continue;
      out.tips=value.map(tip=>{
        if(!tip||typeof tip!=='object')return tip;
        const t={};
        for(const [tk,tv] of Object.entries(tip)){
          if(tv==null)continue;
          if(tk==='evidence'){
            const ev=(Array.isArray(tv)?tv:[]).slice(0,maxEvidence).map(row=>{
              if(!row||typeof row!=='object')return row;
              const e={};
              for(const [ek,evl] of Object.entries(row)){
                if(evl==null)continue;
                if(ek==='line')continue;
                if(dropMeaning&&ek==='meaning')continue;
                e[ek]=roundNum(evl);
              }
              return e;
            });
            if(ev.length)t.evidence=ev;
            continue;
          }
          t[tk]=roundNum(tv);
        }
        return t;
      });
      continue;
    }
    if((key==='home'||key==='away')&&value&&typeof value==='object'){
      const side={};
      for(const [sk,sv] of Object.entries(value)){
        if(sv==null)continue;
        side[sk]=roundNum(sv);
      }
      out[key]=side;
      continue;
    }
    if(Array.isArray(value)&&!value.length)continue;
    out[key]=roundNum(value);
  }
  return out;
}
function stripNulls(value){
  if(Array.isArray(value))return value.map(stripNulls);
  if(!value||typeof value!=='object')return roundNum(value);
  const out={};
  for(const [key,val] of Object.entries(value)){
    if(val==null)continue;
    if(Array.isArray(val)&&!val.length)continue;
    out[key]=stripNulls(val);
  }
  return out;
}
function leanPastRow(match){
  const out={};
  for(const key of PAST_KEEP){
    if(!match||match[key]==null)continue;
    if(key==='odds'){
      const compact=compactOdds(match[key])||{};
      const slim={};
      for(const k of ['home','draw','away']){
        if(compact[k]!=null)slim[k]=compact[k];
      }
      if(Object.keys(slim).length)out.odds=slim;
      continue;
    }
    out[key]=match[key];
  }
  return out;
}
function compactRow(match,today,opts){
  if(!match||typeof match!=='object')return match;
  const d=dateOf(match);
  if(d&&d<today)return leanPastRow(match);
  const row=Object.assign({},match);
  if(row.sportyEventId&&row.sportyEventId===row.id)delete row.sportyEventId;
  if(row.odds)row.odds=compactOdds(row.odds);
  if(row.peerIntel)row.peerIntel=compactPeerIntel(row.peerIntel,opts);
  return stripNulls(row);
}
function serializeBundle(meta,updated,governance,rows){
  const governanceLine=governance?`window.P2U_GOVERNANCE_CONTEXT=${JSON.stringify(governance)};\n`:'';
  return `/* AUTO-GENERATED by build-public-data.js — do not edit. */\nwindow.P2U_DATA_META=${JSON.stringify(meta)};\nwindow.DATA_UPDATED=${JSON.stringify(updated||meta.generatedAt)};\n${governanceLine}window.MATCHES=${JSON.stringify(rows)};\n${ODDS_HYDRATOR}`;
}
function fileSizeOf(meta,updated,governance,rows){
  return Buffer.byteLength(serializeBundle(meta,updated,governance,rows),'utf8');
}

// Compact every row; if the bundle is still over SIZE_BUDGET, apply emergency
// tiers (never drop today/future fixtures, never invent data).
function slimPublicRows(rows,today,opts){
  const options=Object.assign({maxEvidence:8,dropNotes:false,dropMeaning:false,keepPastFrom:null},opts||{});
  const keepFrom=options.keepPastFrom;
  const out=[];
  const stats={
    pastRows:0,leanedPast:0,droppedOldPast:0,compactedCurrent:0,
    droppedPeerIntel:0,droppedHeavy:0,maxEvidence:options.maxEvidence,
    dropNotes:options.dropNotes,dropMeaning:options.dropMeaning,keepPastFrom:keepFrom
  };
  for(const match of rows){
    const d=dateOf(match);
    if(d&&d<today){
      stats.pastRows++;
      if(keepFrom&&d<keepFrom){stats.droppedOldPast++;continue;}
      if(match&&match.peerIntel!==undefined)stats.droppedPeerIntel++;
      out.push(leanPastRow(match));
      stats.leanedPast++;
      continue;
    }
    out.push(compactRow(match,today,options));
    stats.compactedCurrent++;
  }
  return {rows:out,stats};
}
function slimToBudget(rows,today,meta,updated,governance){
  const tiers=[
    {name:'compact',opts:{}},
    {name:'yesterday-only-past',opts:{keepPastFrom:iso(add(new Date(today+'T00:00:00Z'),-1))}},
    {name:'trim-evidence',opts:{keepPastFrom:iso(add(new Date(today+'T00:00:00Z'),-1)),maxEvidence:4,dropMeaning:true}},
    {name:'drop-peer-notes',opts:{keepPastFrom:iso(add(new Date(today+'T00:00:00Z'),-1)),maxEvidence:4,dropMeaning:true,dropNotes:true}}
  ];
  let last=null;
  for(const tier of tiers){
    last=slimPublicRows(rows,today,tier.opts);
    last.stats.tier=tier.name;
    const size=fileSizeOf(meta,updated,governance,last.rows);
    last.stats.bytes=size;
    if(size<=SIZE_BUDGET)return last;
  }
  if(last.stats.bytes>HARD_LIMIT){
    throw new Error(
      `current-data.js would be ${(last.stats.bytes/1024/1024).toFixed(2)} MB after every slim tier; `+
      `the 9 MB release gate would fail. Shrink the source window or split a heavier field.`
    );
  }
  return last;
}

function run(now=new Date()){
  const {matches,updated,governance}=read();
  const today=iso(now);
  const from=publicFrom(today);
  const to=publicTo(today);
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
    version:'v288',generatedAt:new Date().toISOString(),sourceUpdatedAt:updated,
    today,window:{from,to},fallback,maxFixtureDate,totalSourceMatches:sourceMatches.length,publicMatches:rows.length,
    sharedGovernance:!!governance,hydratedFromFixtures,hydratedFromSportybet,
    profileReady:profileEnrichment?profileEnrichment.bothReady:0,
    profileAttached:profileEnrichment?profileEnrichment.attached:0
  };
  const slim=slimToBudget(rows,today,meta,updated,governance);
  rows=slim.rows;
  meta.publicMatches=rows.length;
  meta.slimmed=slim.stats;
  const body=serializeBundle(meta,updated,governance,rows);
  fs.writeFileSync(target,body,'utf8');
  fs.writeFileSync(metaTarget,JSON.stringify(meta,null,2)+'\n','utf8');
  const bytes=fs.statSync(target).size;
  if(bytes>HARD_LIMIT){
    throw new Error(`current-data.js is ${(bytes/1024/1024).toFixed(2)} MB; exceeds the 9 MB release gate.`);
  }
  console.log(`Public data: ${rows.length}/${sourceMatches.length} matches, ${(bytes/1024/1024).toFixed(2)} MB (tier ${slim.stats.tier}); shared governance ${governance?'included':'not present'}${hydratedFromSportybet?' (sportybet hydrate)':''}.`);
  return meta;
}
if(require.main===module)run();
module.exports={
  run,objectAssignment,slimPublicRows,slimToBudget,compactRow,compactOdds,compactPeerIntel,
  leanPastRow,publicFrom,publicTo,weekStartIso,serializeBundle,SIZE_BUDGET,HARD_LIMIT,ODDS_HYDRATOR,
  ODDS_CANON_TO_ALIAS
};
