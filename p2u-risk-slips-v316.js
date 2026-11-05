/* Predict2U v316 — Safe + Medium slips on the home page, above the 25+ all-picks codes. */
(function(){
  'use strict';
  var ZONE='Africa/Accra';
  var BOOKS=[['sportybet','SportyBet','book-sportybet.webp','https://www.sportybet.com/gh/?shareCode='],
    ['msport','MSport','book-msport.webp','https://www.msport.com/gh/sports/share?shareCode='],
    ['betika','Betika','book-betika.webp','https://betika.com/en-gh/share/'],
    ['footballcom','football.com','book-footballcom.webp','https://www.football.com/gh/?shareCode='],
    ['betpawa','Betpawa','book-betpawa.webp','https://www.betpawa.com.gh/#'],['betway','Betway','book-betway.webp','https://www.betway.com.gh/sport/soccer?bookingCode=']];
  function esc(s){return String(s==null?'':s).replace(/[&<>"']/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c];});}
  function css(){if(document.getElementById('p2u-risk-css'))return;var st=document.createElement('style');st.id='p2u-risk-css';st.textContent=
    '.p2u-risk{margin:14px 0}.p2u-risk-h{font-size:1.05rem;margin:0 0 6px;color:#fff}.p2u-risk-h small{display:block;font-size:.78rem;font-weight:500;color:#b9c8dc;margin-top:2px}'+
    '.p2u-risk-card{border-radius:16px;border:1px solid #24324a;background:linear-gradient(160deg,#0f1a2a,#0a111c);padding:12px 14px;margin:10px 0;overflow:hidden}'+
    '.p2u-risk-card.is-safe{border-color:#1f7a4d;box-shadow:0 0 0 1px rgba(127,240,184,.2)}.p2u-risk-card.is-medium{border-color:#7a5a20;box-shadow:0 0 0 1px rgba(255,217,154,.18)}'+
    '.p2u-risk-top{display:flex;flex-wrap:wrap;gap:8px 12px;align-items:center;justify-content:space-between}.p2u-risk-top b{color:#fff;font-size:1rem}'+
    '.p2u-risk-tag{font-size:.68rem;font-weight:900;letter-spacing:.04em;text-transform:uppercase;padding:3px 8px;border-radius:999px}'+
    '.p2u-risk-tag.safe{background:#0f3d2a;color:#7ff0b8}.p2u-risk-tag.medium{background:#3a2a12;color:#ffd99a}.p2u-risk-tag.high{background:#3a1520;color:#ffb0c0}'+
    '.p2u-risk-meta{font-size:.82rem;color:#c3d0e2}.p2u-risk-card details{margin-top:8px}.p2u-risk-card summary{cursor:pointer;color:#a9c9ff;font-weight:700;font-size:.85rem;padding:6px 0;min-height:36px;list-style:none}.p2u-risk-card summary::-webkit-details-marker{display:none}'+
    '.p2u-risk-legs{list-style:none;margin:0;padding:0}.p2u-risk-legs li{display:flex;flex-wrap:wrap;justify-content:space-between;gap:4px 10px;padding:6px 0;border-bottom:1px dashed #24324a;font-size:.86rem;color:#e6eefb}.p2u-risk-legs small{color:#b4c2d6}';
    document.head.appendChild(st);}
  function chips(s){
    var c=s.codes||{};
    return '<div class="p2u-chips">'+BOOKS.map(function(b){
      var raw=c[b[0]],hc=raw&&typeof raw==='object';
      var o=hc?raw.odds:(s.bookOdds&&s.bookOdds[b[0]])||s.totalOdds;
      var n=hc?raw.legs:(s.bookPicks&&s.bookPicks[b[0]])||(s.legs||[]).length;
      var code=hc?raw.code:raw;
      if(!code){
        if(!s.highOdds)return '';
        return '<div class="p2u-chip p2u-chip-'+b[0]+' is-pending"><img src="/'+b[2]+'" alt="" width="24" height="24"><span class="p2u-chip-t"><span class="p2u-chip-n">'+b[1]+'</span><span class="p2u-chip-c">Unavailable</span><span class="p2u-chip-o">'+esc((s.bookingPending||{})[b[0]]||'Not booked')+'</span></span><button type="button" class="p2u-chip-cp" disabled>Pending</button></div>';
      }
      return '<div class="p2u-chip p2u-chip-'+b[0]+'" data-book="'+b[0]+'" data-code="'+esc(code)+'" data-legs="'+esc(n)+'" data-odds="'+esc(o)+'"><img src="/'+b[2]+'" alt="" width="24" height="24" loading="lazy"><span class="p2u-chip-t"><span class="p2u-chip-n">'+b[1]+'</span><a class="p2u-chip-c" target="_blank" rel="noopener" href="'+b[3]+encodeURIComponent(code)+'">'+esc(code)+'</a><span class="p2u-chip-o">@'+Number(o).toFixed(2)+' · '+n+' picks</span></span><button type="button" class="p2u-chip-cp" data-copy="'+esc(code)+'" aria-label="Copy '+b[1]+' code">Copy</button></div>';
    }).join('')+'</div>';
  }
  document.addEventListener('click',function(e){var b=e.target.closest&&e.target.closest('.p2u-risk [data-copy],.high-wrap [data-copy]');if(!b)return;var c=b.getAttribute('data-copy'),ok=function(){b.textContent='Copied ✓';setTimeout(function(){b.textContent='Copy';},1600)};if(navigator.clipboard)navigator.clipboard.writeText(c).then(ok,ok);else{var t=document.createElement('textarea');t.value=c;document.body.appendChild(t);t.select();try{document.execCommand('copy')}catch(_){}t.remove();ok()}});
  function card(s){
    var r=s.risk||'high', lab=r==='safe'?'Safe slip':r==='medium'?'Medium slip':(s.name||'High-risk slip');
    var hint=r==='safe'?'Low risk · aim odds 2–5':r==='medium'?'Balanced · aim odds 8–15':'High risk · 25+ odds';
    return '<article class="p2u-risk-card is-'+esc(r)+'"><div class="p2u-risk-top"><div><span class="p2u-risk-tag '+esc(r)+'">'+esc(r==='safe'?'Safe':r==='medium'?'Medium':'High risk')+'</span> <b>'+esc(lab)+'</b></div>'+
      '<div class="p2u-risk-meta">@'+Number(s.totalOdds).toFixed(2)+' · '+(s.legs||[]).length+' picks · '+esc(hint)+'</div></div>'+chips(s)+(window.P2UWA?'<div class="p2u-wa-row">'+P2UWA.button(s,'p2u-wa')+'</div>':'')+
      '<details><summary>Show picks</summary><ul class="p2u-risk-legs">'+(s.legs||[]).map(function(l){return '<li><span>'+esc(l.match)+' <small>'+esc((l.date||'').slice(5)+' '+(l.ko||'').slice(0,5))+'</small></span><b>'+esc(l.selection)+' @'+Number(l.odds).toFixed(2)+'</b></li>';}).join('')+'</ul></details></article>';
  }
  function render(d){
    css(); if(window.P2UWA)P2UWA.css();
    var slips=(d.slips||[]).filter(function(s){return !s.earlier && s.codes && (s.codes.sportybet||s.codes.msport) && (s.risk==='safe'||s.risk==='medium'||/Safe slip|Medium slip/i.test(s.name||''));});
    slips.sort(function(a,b){return (a.risk==='safe'?0:1)-(b.risk==='safe'?0:1);});
    var host=document.getElementById('hp-risk');
    var anchor=document.getElementById('hp-code');
    if(!host){host=document.createElement('section');host.id='hp-risk';host.className='p2u-risk p2u-legible';
      if(anchor&&anchor.parentNode)anchor.parentNode.insertBefore(host,anchor);else return;}
    if(!slips.length){host.hidden=true;host.innerHTML='';return;}
    host.hidden=false;
    host.innerHTML='<h2 class="p2u-risk-h">Safe &amp; Medium slips <small>Lower risk first · high-risk 25+ codes stay below</small></h2>'+slips.map(card).join('');
  }
  function go(){if(!document.getElementById('hp-code'))return;fetch('/home-picks.json',{cache:'no-cache'}).then(function(r){return r.ok?r.json():null;}).then(function(d){if(d)render(d);}).catch(function(){});}
  window.P2URisk={chips:chips,css:css,legs:function(s){return '<details class="p2u-risk-picks"><summary>Show picks</summary><ul class="p2u-risk-legs">'+(s.legs||[]).map(function(l){return '<li><span>'+esc(l.match)+' <small>'+esc((l.date||'').slice(5)+' '+(l.ko||'').slice(0,5))+'</small></span><b>'+esc(l.selection)+' @'+Number(l.odds).toFixed(2)+'</b></li>';}).join('')+'</ul></details>';}};
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',go);else go();
})();
