/* Predict2U v299 — home auto-scrolling booking-code carousel, data-driven from home-picks.json.
   Cards come from: homeCode.codes[] (SportyBet all-picks), homeCode.<book>[] ({<book>|code,totalOdds,legs,of,link}),
   and slips[].codes {<book>:CODE} with optional bookOdds/bookPicks/bookNotes {<book>:...}. Unknown books get a neutral card. */
(function(){
  'use strict';
  var BOOKS={
    sportybet:{n:'SportyBet',logo:'book-sportybet.webp',c:'#e41827',link:'https://www.sportybet.com/gh/?shareCode={c}'},
    msport:{n:'MSport',logo:'book-msport.webp',c:'#ffd325',link:'https://www.msport.com/gh/sports/share?shareCode={c}'},
    onexbet:{n:'1xBet',logo:'book-1xbet.webp',c:'#1f6fb2',link:'https://1xbet.com/en/?coupon={c}'},
    betway:{n:'Betway',logo:'book-betway.webp',c:'#00a826',link:null},
    '22bet':{n:'22Bet',logo:'book-22bet.webp',c:'#1b5e20',link:null},
    betika:{n:'Betika',logo:'book-betika.webp',c:'#00b140',link:null}
  };
  BOOKS['1xbet']=BOOKS.onexbet;
  var esc=function(s){return String(s==null?'':s).replace(/[&<>"']/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c];});};
  var fmt=function(o){return o?Number(o).toLocaleString('en-GB',{maximumFractionDigits:2}):'—';};
  function cards(d){
    var out=[],seen={},h=d.homeCode||{};
    function add(book,code,odds,legs,title,note,link){if(!code)return;code=String(code).toUpperCase();var k=book+':'+code;if(seen[k])return;seen[k]=1;
      var B=BOOKS[book]||{n:book,logo:null,c:'#64748b',link:null};out.push({b:B,code:code,odds:odds,legs:legs,title:title,note:note,link:link||(B.link?B.link.replace('{c}',encodeURIComponent(code)):null)});}
    (h.codes||[]).forEach(function(c){add('sportybet',c.sportybet||c.code,c.totalOdds,c.legs,'All picks of the day',null,c.link);});
    Object.keys(h).forEach(function(k){if(k==='codes'||!Array.isArray(h[k]))return;h[k].forEach(function(c){add(k,c[k]||c.code,c.totalOdds,c.legs,'All picks of the day',c.of&&c.of>c.legs?(c.of-c.legs)+((c.of-c.legs)>1?' picks':' pick')+' not on '+((BOOKS[k]||{}).n||k):null,c.link);});});
    (d.slips||[]).forEach(function(s){var C=s.codes||{};Object.keys(C).forEach(function(k){
      add(k,C[k],(s.bookOdds||{})[k]||(k==='sportybet'?s.totalOdds:null),(s.bookPicks||{})[k]||(s.legs||[]).length,String(s.name||'Banker slip').replace(/\s*\(.*\)$/,''),(s.bookNotes||{})[k]);});});
    return out;
  }
  function card(x){return '<div class="cc-card" style="--brand:'+x.b.c+'"><div class="cc-top">'+(x.b.logo?'<img src="'+x.b.logo+'" alt="'+esc(x.b.n)+' logo" width="26" height="26" loading="lazy" decoding="async">':'')+'<b>'+esc(x.b.n)+'</b></div>'+
    '<div class="cc-t">'+esc(x.title)+'</div><div class="cc-code">'+esc(x.code)+'</div><div class="cc-m">@'+fmt(x.odds)+' · '+esc(x.legs)+' picks</div>'+(x.note?'<div class="cc-n">⚠ '+esc(x.note)+'</div>':'')+
    '<div class="cc-a"><button type="button" data-cc-copy="'+esc(x.code)+'">Copy</button>'+(x.link?'<a target="_blank" rel="noopener" href="'+esc(x.link)+'">Open ↗</a>':'')+'</div></div>';}
  function mount(d){
    var el=document.getElementById('hp-carousel');if(!el)return;var C=cards(d);if(!C.length){el.hidden=true;return;}
    el.hidden=false;el.innerHTML='<h2 class="cc-h">Booking codes</h2><div class="cc-vp" tabindex="0" aria-label="Booking codes, swipe to scroll"><div class="cc-track">'+C.map(card).join('')+'</div></div>';
    var vp=el.querySelector('.cc-vp'),paused=false,rm=window.matchMedia&&matchMedia('(prefers-reduced-motion: reduce)').matches,last=0,acc=0,resume;
    ['mouseenter','touchstart','focusin','pointerdown'].forEach(function(e){vp.addEventListener(e,function(){paused=true;clearTimeout(resume);},{passive:true});});
    ['mouseleave','touchend','focusout','pointerup'].forEach(function(e){vp.addEventListener(e,function(){clearTimeout(resume);resume=setTimeout(function(){paused=false;},2500);},{passive:true});});
    if(rm||vp.scrollWidth<=vp.clientWidth+4)return;
    function step(t){vp.style.scrollSnapType=paused?'':'none';if(last&&!paused&&!document.hidden){acc+=(t-last)*0.03;var px=Math.floor(acc);if(px){acc-=px;vp.scrollLeft+=px;if(vp.scrollLeft+vp.clientWidth>=vp.scrollWidth-1)vp.scrollLeft=0;}}last=t;requestAnimationFrame(step);}
    requestAnimationFrame(step);
  }
  document.addEventListener('click',function(e){var b=e.target.closest&&e.target.closest('[data-cc-copy]');if(!b)return;var c=b.getAttribute('data-cc-copy'),ok=function(){b.textContent='Copied ✓';setTimeout(function(){b.textContent='Copy';},1600);};
    if(navigator.clipboard&&navigator.clipboard.writeText)navigator.clipboard.writeText(c).then(ok,ok);else ok();});
  fetch('home-picks.json',{cache:'no-cache'}).then(function(r){return r.json();}).then(mount).catch(function(){});
})();
