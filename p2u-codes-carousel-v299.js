/* Predict2U v329 — booking-code carousel for home + Hot Picks.
   Home: home-picks.json → #hp-carousel. Hot: hot-picks.json slips → #hot-carousel (mountHot).
   Cards use brand colours; auto-scroll is slow, pauses on hover/touch, respects prefers-reduced-motion. */
(function(){
  'use strict';
  var BOOKS={
    sportybet:{n:'SportyBet',logo:'book-sportybet.webp',c:'#e41827',link:'https://www.sportybet.com/gh/?shareCode={c}'},
    msport:{n:'MSport',logo:'book-msport.webp',c:'#ffd325',link:'https://www.msport.com/gh/sports/share?shareCode={c}'},
    onexbet:{n:'1xBet',logo:'book-1xbet.webp',c:'#1f6fb2',link:'https://1xbet.com/en/?coupon={c}'},
    betway:{n:'Betway',logo:'book-betway.webp',c:'#00a826',link:null},
    '22bet':{n:'22Bet',logo:'book-22bet.webp',c:'#1b5e20',link:null},
    betika:{n:'Betika',logo:'book-betika.webp',c:'#00b140',link:null},
    footballcom:{n:'football.com',logo:'book-footballcom.webp',c:'#282450',link:'https://www.football.com/gh/?shareCode={c}'},
    betpawa:{n:'Betpawa',logo:'book-betpawa.webp',c:'#78be20',link:'https://www.betpawa.com.gh/#{c}'},
    betway:{n:'Betway',logo:'book-betway.webp',c:'#00a826',link:'https://www.betway.com.gh/sport/soccer?bookingCode={c}'}
  };
  BOOKS['1xbet']=BOOKS.onexbet;
  var esc=function(s){return String(s==null?'':s).replace(/[&<>"']/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c];});};
  var fmt=function(o){if(!o)return '—';var n=Number(o);if(!isFinite(n))return '—';if(n<100000)return n.toLocaleString('en-GB',{maximumFractionDigits:2});var U=[[1e18,'Qi'],[1e15,'Q'],[1e12,'T'],[1e9,'B'],[1e6,'M'],[1e3,'K']];for(var i=0;i<U.length;i++){if(n>=U[i][0]){var v=n/U[i][0];return (v>=1000?Math.round(v).toLocaleString('en-GB'):v.toFixed(v<10?2:1).replace(/\.?0+$/,''))+U[i][1];}}return String(n);};
  function addFactory(out,seen){
    return function add(book,code,odds,legs,title,note,link){if(!code)return;code=String(code);if(book!=='betika')code=code.toUpperCase();var k=book+':'+code;if(seen[k])return;seen[k]=1;
      var B=BOOKS[book]||{n:book,logo:null,c:'#64748b',link:null};out.push({b:B,code:code,odds:odds,legs:legs,title:title,note:note,link:link||(B.link?B.link.replace('{c}',encodeURIComponent(code)):null)});}
  }
  function cardsHome(d){
    var out=[],seen={},h=d.homeCode||{},add=addFactory(out,seen);
    (h.codes||[]).forEach(function(c){add('sportybet',c.sportybet||c.code,c.totalOdds,c.legs,'All picks of the day',null,c.link);});
    Object.keys(h).forEach(function(k){if(k==='codes'||!Array.isArray(h[k]))return;h[k].forEach(function(c){add(k,c[k]||c.code,c.totalOdds,c.legs,'All picks of the day',c.of&&c.of>c.legs?(c.of-c.legs)+((c.of-c.legs)>1?' picks':' pick')+' not on '+((BOOKS[k]||{}).n||k):null,c.link);});});
    (d.slips||[]).forEach(function(s){var C=s.codes||{};Object.keys(C).forEach(function(k){
      add(k,C[k],(s.bookOdds||{})[k]||(k==='sportybet'?s.totalOdds:null),(s.bookPicks||{})[k]||(s.legs||[]).length,String(s.name||'Banker slip').replace(/\s*\(.*\)$/,''),(s.bookNotes||{})[k]);});});
    return out;
  }
  function cardsHot(d){
    var out=[],seen={},add=addFactory(out,seen);
    (d.slips||[]).forEach(function(s){
      var title=String(s.name||'Hot Picks').replace(/\s*\(.*\)$/,'');
      var C=s.codes||{};
      Object.keys(C).forEach(function(k){
        var list=C[k];
        if(!Array.isArray(list))list=list?[{code:list}]:[];
        list.forEach(function(c){
          if(!c)return;
          var code=typeof c==='string'?c:(c[k]||c.code);
          add(k,code,c.totalOdds!=null?c.totalOdds:s.totalOdds,c.legs!=null?c.legs:s.legs,title,null,c.link);
        });
      });
    });
    return out;
  }
  function card(x){return '<div class="cc-card" style="--brand:'+x.b.c+'"><div class="cc-top">'+(x.b.logo?'<img src="'+x.b.logo+'" alt="'+esc(x.b.n)+' logo" width="26" height="26" loading="lazy" decoding="async">':'')+'<b>'+esc(x.b.n)+'</b></div>'+
    '<div class="cc-t">'+esc(x.title)+'</div><div class="cc-code">'+esc(x.code)+'</div><div class="cc-m">@'+fmt(x.odds)+' · '+esc(x.legs)+' picks</div>'+(x.note?'<div class="cc-n">⚠ '+esc(x.note)+'</div>':'')+
    '<div class="cc-a"><button type="button" data-cc-copy="'+esc(x.code)+'">Copy</button>'+(x.link?'<a target="_blank" rel="noopener" href="'+esc(x.link)+'">Open ↗</a>':'')+'</div></div>';}
  function mount(el,C,heading){
    if(!el)return;
    if(!C||!C.length){el.hidden=true;el.innerHTML='';return;}
    el.hidden=false;
    el.innerHTML='<h2 class="cc-h">'+(heading||'Booking codes')+'</h2><div class="cc-vp" tabindex="0" aria-label="Booking codes, swipe to scroll"><div class="cc-track">'+C.map(card).join('')+'</div></div>';
    var vp=el.querySelector('.cc-vp'),paused=false,rm=window.matchMedia&&matchMedia('(prefers-reduced-motion: reduce)').matches,last=0,acc=0,resume;
    ['mouseenter','touchstart','focusin','pointerdown'].forEach(function(e){vp.addEventListener(e,function(){paused=true;clearTimeout(resume);},{passive:true});});
    ['mouseleave','touchend','focusout','pointerup'].forEach(function(e){vp.addEventListener(e,function(){clearTimeout(resume);resume=setTimeout(function(){paused=false;},2500);},{passive:true});});
    if(rm)return;
    function step(t){if(!vp.isConnected)return;var can=vp.scrollWidth>vp.clientWidth+4&&vp.offsetParent!==null;vp.style.scrollSnapType=(paused||!can)?'':'none';if(last&&can&&!paused&&!document.hidden){acc+=(t-last)*0.03;var px=Math.floor(acc);if(px){acc-=px;vp.scrollLeft=vp.scrollLeft+px;if(vp.scrollLeft+vp.clientWidth>=vp.scrollWidth-1)vp.scrollLeft=0;}}last=t;requestAnimationFrame(step);}
    requestAnimationFrame(step);
  }
  document.addEventListener('click',function(e){var b=e.target.closest&&e.target.closest('[data-cc-copy]');if(!b)return;var c=b.getAttribute('data-cc-copy'),ok=function(){b.textContent='Copied ✓';setTimeout(function(){b.textContent='Copy';},1600);};
    if(navigator.clipboard&&navigator.clipboard.writeText)navigator.clipboard.writeText(c).then(ok,ok);else ok();});
  window.P2UCarousel={
    mount:mount,
    cardsHome:cardsHome,
    cardsHot:cardsHot,
    mountHot:function(el,d){mount(el,cardsHot(d),'Hot Picks codes today');}
  };
  var hc=document.getElementById('hot-carousel');
  if(hc)fetch('hot-picks.json?t='+Date.now()).then(function(r){return r.json();}).then(function(d){window.P2UCarousel.mountHot(hc,d);}).catch(function(){});
  var hp=document.getElementById('hp-carousel');
  if(hp)fetch('home-picks.json',{cache:'no-cache'}).then(function(r){return r.json();}).then(function(d){mount(hp,cardsHome(d));}).catch(function(){});
})();
