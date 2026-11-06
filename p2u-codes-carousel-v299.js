/* Predict2U v329 — booking-code carousel for home + Hot Picks.
   Home: home-picks.json → #hp-carousel. Hot: hot-picks.json slips → #hot-carousel (mountHot).
   Cards use brand colours; auto-scroll is slow, pauses on hover/touch, respects prefers-reduced-motion. */
(function(){
  'use strict';
  var BOOKS={
    sportybet:{n:'SportyBet',logo:'book-sportybet.webp',c:'#e41827',link:'https://www.sportybet.com/gh/?shareCode={c}'},
    msport:{n:'MSport',logo:'book-msport.webp',c:'#ffd325',link:'https://www.msport.com/gh/?shareCode={c}'},
    onexbet:{n:'1xBet',logo:'book-1xbet.webp',c:'#1f6fb2',link:'https://1xbet.com/en/?coupon={c}'},
    '22bet':{n:'22Bet',logo:'book-22bet.webp',c:'#1b5e20',link:null},
    betika:{n:'Betika',logo:'book-betika.webp',c:'#00b140',link:'https://betika.com/en-gh/share/{c}'},
    footballcom:{n:'football.com',logo:'book-footballcom.webp',c:'#282450',link:'https://www.football.com/gh/?shareCode={c}'},
    betpawa:{n:'Betpawa',logo:'book-betpawa.webp',c:'#78be20',link:'https://www.betpawa.com.gh/share-betslip/{c}'},
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
    (d.slips||[]).forEach(function(s){if(s.earlier||/^earlier code/i.test(String(s.name||'')))return;var C=s.codes||{};Object.keys(C).forEach(function(k){
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

  function logoFor(book){var B=BOOKS[book];return B&&B.logo?B.logo:('book-'+book+'.webp');}
  function sectionCard(s){
    var C=s.codes||{}, order=['sportybet','footballcom','msport','betika','betpawa','betway'];
    var primary=null, primaryBook=null;
    for(var i=0;i<order.length;i++){var L=C[order[i]]; if(!L)continue; if(!Array.isArray(L))L=[{code:L}]; if(L[0]&&(L[0].code||L[0])){primary=L[0]; primaryBook=order[i]; break;}}
    var code=primary?(primary.code||primary):'—';
    var odds=primary&&primary.totalOdds!=null?primary.totalOdds:s.totalOdds;
    var legs=primary&&primary.legs!=null?primary.legs:s.legs;
    var brand=(BOOKS[primaryBook]||{c:'#7fb2ff'}).c;
    var chips=order.filter(function(b){return C[b];}).map(function(b){
      var list=Array.isArray(C[b])?C[b]:[{code:C[b]}];
      return list.map(function(c){
        var cd=c.code||c, link=c.link||(BOOKS[b]&&BOOKS[b].link?BOOKS[b].link.replace('{c}',encodeURIComponent(cd)):null);
        var B=BOOKS[b]||{n:b,c:'#64748b'};
        return '<a class="cc-chip" style="--brand:'+B.c+'" '+(link?'href="'+esc(link)+'" target="_blank" rel="noopener"':'')+' title="'+esc(B.n)+' '+esc(cd)+'"><img src="'+esc(logoFor(b))+'" alt="" width="18" height="18" loading="lazy"><span>'+esc(cd)+'</span></a>';
      }).join('');
    }).join('');
    return '<div class="cc-card cc-section" style="--brand:'+brand+'"><div class="cc-top"><b>'+esc(s.label||s.name||'Section')+'</b></div>'+
      '<div class="cc-t">'+esc(s.name||'Master slip')+'</div><div class="cc-code">'+esc(code)+'</div><div class="cc-m">@'+fmt(odds)+' · '+esc(legs)+' picks'+(s.meetsFloor===false?' · under 25':'')+'</div>'+
      (s.note?'<div class="cc-n">⚠ '+esc(s.note)+'</div>':'')+
      '<div class="cc-chips">'+chips+'</div>'+
      '<div class="cc-a"><button type="button" data-cc-copy="'+esc(code)+'">Copy</button>'+
      (primary&&(primary.link||(BOOKS[primaryBook]&&BOOKS[primaryBook].link))?'<a target="_blank" rel="noopener" href="'+esc(primary.link||BOOKS[primaryBook].link.replace('{c}',encodeURIComponent(code)))+'">Open ↗</a>':'')+
      '</div></div>';
  }
  function cardsSectionMasters(d){
    return (d.sectionMasters||[]).filter(function(s){return s&&s.codes&&Object.keys(s.codes).length;}).map(sectionCard);
  }

  function mount(el,C,heading){
    if(!el)return;
    if(!C||!C.length){el.hidden=true;el.innerHTML='';return;}
    el.hidden=false;
    el.innerHTML='<h2 class="cc-h">'+(heading||'Booking codes')+'</h2><div class="cc-vp" tabindex="0" aria-label="Booking codes, swipe to scroll"><div class="cc-track">'+C.map(function(x){return typeof x==='string'?x:card(x);}).join('')+'</div></div>';
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
    cardsHot:cardsHot,cardsSectionMasters:cardsSectionMasters,
    mountHot:function(el,d){var C=cardsSectionMasters(d); if(C.length){mount(el,C,'Section master slips today'); el.classList.add('cc-sections');} else mount(el,cardsHot(d),'Hot Picks codes today');}
  };
  var hc=document.getElementById('hot-carousel');
  if(hc)fetch('hot-picks.json?t='+Date.now()).then(function(r){return r.json();}).then(function(d){window.P2UCarousel.mountHot(hc,d);}).catch(function(){});
  var hp=document.getElementById('hp-carousel');
  if(hp)fetch('home-picks.json',{cache:'no-cache'}).then(function(r){return r.json();}).then(function(d){mount(hp,cardsHome(d));}).catch(function(){});
})();
