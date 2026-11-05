/* Predict2U v318 — live scores on home picks.
   Tries the Render relay (CORS) first; falls back to sync home-picks / live-scores.json. */
(function(global){
  'use strict';
  var RELAY='https://p2u-relay.onrender.com';
  var scores={}; // eventId -> {status,score,played,kickoff,home,away,source}
  var timer=null, lastFetch=0, source='sync';

  function esc(s){return String(s==null?'':s).replace(/[&<>"']/g,function(c){return{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c];});}
  function isLive(st){return st && !/^(Not start|Ended|Cancelled|Postponed|Abandoned)$/i.test(st);}
  function label(e){
    if(!e) return '—';
    if(e.score) return e.score+(isLive(e.status)?' LIVE':'')+(e.status==='Ended'?' FT':'');
    if(isLive(e.status)) return e.status;
    return '—';
  }
  function resultOf(e, pickResult){
    if(pickResult==='won'||pickResult==='lost'||pickResult==='void') return pickResult;
    if(!e) return pickResult||'pending';
    if(e.status==='Ended' && e.score) return 'ended';
    if(isLive(e.status)) return 'live';
    return pickResult||'pending';
  }

  function css(){
    if(document.getElementById('p2u-live-css')) return;
    var st=document.createElement('style'); st.id='p2u-live-css';
    st.textContent=
      '.hp-score{font-weight:800;color:#e6eefb}.hp-score.is-live{color:#ffd36b}.hp-score.is-ft{color:#7ff0b8}'+
      '.hp-livepill{display:inline-flex;align-items:center;gap:5px;font-size:.68rem;font-weight:900;letter-spacing:.06em;text-transform:uppercase;padding:2px 7px;border-radius:999px;margin-left:6px;vertical-align:middle}'+
      '.hp-livepill.live{background:#3a2a12;color:#ffd99a;border:1px solid #7a5a20;animation:hpPulse 1.4s ease-in-out infinite}'+
      '.hp-livepill.ft{background:#0f3d2a;color:#7ff0b8;border:1px solid #1f7a4d}'+
      '.hp-livepill.sync{background:#1f2a3a;color:#c3d0e2;border:1px solid #2c4a7a}'+
      '@keyframes hpPulse{0%,100%{opacity:1}50%{opacity:.55}}'+
      '.hp-livebar{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin:8px 0 4px;font-size:.8rem;color:#b4c2d6}'+
      '.hp-livebar b{color:#fff}'+
      '@media(prefers-reduced-motion:reduce){.hp-livepill.live{animation:none}}';
    document.head.appendChild(st);
  }

  var applying=false, lastBarHtml='';
  function apply(){
    if(applying) return;
    applying=true;
    try{
    css();
    var nLive=0,nFt=0;
    document.querySelectorAll('[data-score-eid]').forEach(function(dd){
      var id=dd.getAttribute('data-score-eid'); if(!id) return;
      var e=scores[id];
      var txt=label(e);
      dd.textContent=txt==='—'? '—' : (e&&e.score? e.score : txt);
      dd.classList.toggle('is-live', !!(e&&isLive(e.status)));
      dd.classList.toggle('is-ft', !!(e&&e.status==='Ended'&&e.score));
      if(e&&isLive(e.status)) nLive++;
      if(e&&e.status==='Ended'&&e.score) nFt++;
      // pill next to match title
      var art=dd.closest('.hp-pick');
      if(art){
        var top=art.querySelector('.hp-top .hp-mt b')||art.querySelector('.hp-mt b');
        var pill=art.querySelector('.hp-livepill');
        if(e&&(isLive(e.status)||(e.status==='Ended'&&e.score))){
          if(!pill){pill=document.createElement('span');pill.className='hp-livepill'; if(top) top.appendChild(pill); else art.querySelector('.hp-top').appendChild(pill);}
          if(isLive(e.status)){pill.className='hp-livepill live';pill.textContent='LIVE'+(e.score?' '+e.score:'');}
          else {pill.className='hp-livepill ft';pill.textContent='FT '+e.score;}
        } else if(pill){pill.remove();}
      }
    });
    var bar=document.getElementById('hp-livebar');
    if(!bar){
      var host=document.getElementById('hp-tally')||document.getElementById('hp-meta');
      if(host){bar=document.createElement('div');bar.id='hp-livebar';bar.className='hp-livebar';host.parentNode.insertBefore(bar, host.nextSibling);}
    }
    if(bar){
      var ago=lastFetch? Math.max(0, Math.round((Date.now()-lastFetch)/1000)) : null;
      var html='<span>Scores · <b>'+esc(source)+'</b>'+(ago!=null?' · '+ago+'s ago':'')+'</span>'+
        (nLive?'<span class="hp-livepill live">'+nLive+' live</span>':'')+
        (nFt?'<span class="hp-livepill ft">'+nFt+' finished</span>':'')+
        (!nLive&&!nFt?'<span class="hp-livepill sync">waiting for kick-off</span>':'');
      if(html!==lastBarHtml){ lastBarHtml=html; bar.innerHTML=html; }
    }
    if(nLive && !timer) timer=setInterval(function(){ refresh(null,true); }, 60000);
    if(!nLive && timer){ clearInterval(timer); timer=null; }
    } finally { applying=false; }
  }

  function mergeSync(data){
    (data&&data.picks||[]).forEach(function(p){
      if(!p.eventId) return;
      if(p.score || p.result==='won' || p.result==='lost'){
        scores[p.eventId]=scores[p.eventId]||{};
        if(p.score) scores[p.eventId].score=p.score;
        if(p.result==='won'||p.result==='lost') scores[p.eventId].status=scores[p.eventId].status||'Ended';
        scores[p.eventId].source=scores[p.eventId].source||'sync';
      }
    });
  }

  function chunks(arr,n){var o=[]; for(var i=0;i<arr.length;i+=n) o.push(arr.slice(i,i+n)); return o;}

  function fetchRelay(ids){
    if(!ids.length) return Promise.resolve(false);
    return Promise.all(chunks(ids,80).map(function(part){
      return fetch(RELAY+'/events?ids='+part.map(encodeURIComponent).join(','),{cache:'no-cache'})
        .then(function(r){ if(!r.ok) throw 0; return r.json(); })
        .then(function(j){
          var E=(j&&j.events)||{};
          Object.keys(E).forEach(function(id){ scores[id]=Object.assign({},scores[id],E[id],{source:'live'}); });
          return true;
        });
    })).then(function(rows){ return rows.some(Boolean); }).catch(function(){ return false; });
  }

  function fetchStaticFallback(){
    return fetch('live-scores.json',{cache:'no-cache'}).then(function(r){ return r.ok?r.json():null; }).then(function(j){
      if(!j||!j.events) return false;
      Object.keys(j.events).forEach(function(id){ if(!scores[id]||scores[id].source!=='live') scores[id]=Object.assign({},j.events[id],{source:'sync'}); });
      return true;
    }).catch(function(){ return false; });
  }

  function refresh(data, force){
    if(data) mergeSync(data);
    var ids=[];
    if(data&&data.picks) data.picks.forEach(function(p){ if(p.eventId) ids.push(p.eventId); });
    document.querySelectorAll('[data-score-eid]').forEach(function(el){ var id=el.getAttribute('data-score-eid'); if(id&&ids.indexOf(id)<0) ids.push(id); });
    // unique
    ids=ids.filter(function(v,i,a){return a.indexOf(v)===i;});
    apply(); // show sync first
    return fetchRelay(ids).then(function(ok){
      if(ok){ source='live relay'; lastFetch=Date.now(); apply(); return; }
      return fetchStaticFallback().then(function(ok2){
        source=ok2?'sync file':'sync picks';
        lastFetch=Date.now();
        apply();
      });
    });
  }

  function text(eid){ return label(scores[eid]); }

  global.P2UScores={refresh:refresh, text:text, apply:apply, _scores:function(){return scores;}};

  // If home already rendered before this script, still run
  if(document.readyState==='loading') document.addEventListener('DOMContentLoaded', function(){ css(); boot(); });
  else { css(); boot(); }

  function boot(){
    try{
      var moTimer=null;
      var mo=new MutationObserver(function(){
        if(applying) return;
        if(moTimer) return;
        moTimer=setTimeout(function(){ moTimer=null; apply(); }, 50);
      });
      mo.observe(document.body,{childList:true,subtree:true});
    }catch(_){}
    setInterval(function(){ refresh(null,true); }, 120000);
  }
})(window);
