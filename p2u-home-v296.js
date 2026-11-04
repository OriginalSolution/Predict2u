/* Predict2U v296 — Picks of the Day, reads home-picks.json (research feed). */
(function(){
  'use strict';
  var $=function(id){return document.getElementById(id);};
  var esc=function(s){return String(s==null?'':s).replace(/[&<>"']/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c];});};
  var ZONE='Africa/Accra';
  function stamp(d){return new Intl.DateTimeFormat('en-CA',{timeZone:ZONE,year:'numeric',month:'2-digit',day:'2-digit'}).format(d);}
  function ko(iso){var d=new Date(iso);return isNaN(d)?'':d.toLocaleTimeString('en-GB',{timeZone:ZONE,hour:'2-digit',minute:'2-digit'});}
  function pct(x){return x==null?'—':Math.round(x*100)+'%';}
  function badge(r){r=r||'pending';return '<span class="bp-res bp-'+esc(r)+'">'+esc(r.toUpperCase())+'</span>';}
  var data;
  function koTxt(p){if(p.ko&&String(p.ko).indexOf('T')>0)return ko(p.ko);return p.ko?String(p.ko).slice(0,5):'';}
  function rate(x){if(x==null||x==='')return '—';var n=Number(x);if(!isFinite(n))return esc(x);return Math.round(n<=1?n*100:n)+'%';}
  function render(){
    var P=(data.picks||[]).slice(),res=function(p){return String(p.result||'pending').toLowerCase();};
    var w=P.filter(function(p){return res(p)==='won';}),l=P.filter(function(p){return res(p)==='lost';}),pend=P.length-w.length-l.length;
    $('hp-tally').innerHTML='<div class="hp-t hp-tw"><b>'+w.length+'</b><span>Won today</span></div><div class="hp-t hp-tl"><b>'+l.length+'</b><span>Lost</span></div><div class="hp-t"><b>'+pend+'</b><span>Pending</span></div><div class="hp-t"><b>'+(w.length+l.length?Math.round(100*w.length/(w.length+l.length))+'%':'—')+'</b><span>Hit rate</span></div>'+
      (w.length?'<div class="hp-wonlist">'+w.map(function(p){return '<span>✓ '+esc(p.match)+' · '+esc(p.selection)+(p.score?' ('+esc(p.score)+')':'')+'</span>';}).join('')+'</div>':'');
    if(!P.length){$('hp-list').innerHTML='<div class="p2u-bankers-empty">Today’s picks are being prepared. Check back soon.</div>';return;}
    P.sort(function(a,b){return (res(a)==='won'?0:1)-(res(b)==='won'?0:1)||String(a.ko||'').localeCompare(String(b.ko||''));});
    $('hp-list').innerHTML=P.map(function(p,i){var c=Number(p.confidence);c=c>1?c/100:c;var g=c>=0.8?'A':c>=0.72?'B':'C';var r=res(p);
      return '<article class="hp-pick'+(r==='won'?' is-won':r==='lost'?' is-lost':'')+'"><div class="hp-top"><span class="bp-grade bp-g'+g+'">'+g+'</span><div class="hp-mt"><b>'+esc(p.match)+'</b><small>'+esc(koTxt(p))+' · '+esc(p.league)+'</small></div>'+badge(r)+'</div>'+
        '<div class="hp-sel"><span>'+esc(p.selection)+(p.market?' <small>'+esc(p.market)+'</small>':'')+'</span><b>@'+(p.odds==null?'—':Number(p.odds).toFixed(2))+'</b></div>'+
        '<dl class="hp-stats"><div><dt>League fav. rate</dt><dd>'+rate(p.leagueFavRate)+'</dd></div><div><dt>Sample</dt><dd>'+(p.sample==null?'—':esc(p.sample)+' games')+'</dd></div><div><dt>Our confidence</dt><dd>'+rate(p.confidence)+'</dd></div><div><dt>Result</dt><dd>'+esc(p.score||r)+'</dd></div></dl>'+
        (p['case']?'<button type="button" class="hp-why" aria-expanded="false" aria-controls="hpw'+i+'">Why this pick <i class="bp-chev" aria-hidden="true"></i></button><p class="hp-case" id="hpw'+i+'" hidden>'+esc(p['case'])+'</p>':'')+'</article>';}).join('');
  }
  function codes(){var el=$('hp-code');if(!el)return;var h=data.homeCode||{},C=h.codes||[];
    if(!C.length){el.innerHTML='';el.hidden=true;return;}el.hidden=false;
    el.innerHTML='<h2 class="hp-code-h"><img src="book-sportybet.webp" alt="SportyBet logo" width="28" height="28" decoding="async"> Book all of today’s picks on SportyBet</h2>'+C.map(function(c,k){
      return '<div class="hp-code-c"><div class="hp-code-i"><small>'+(C.length>1?'Code '+(k+1)+' of '+C.length+' · ':'')+esc(c.legs)+' picks · total odds '+Number(c.totalOdds).toLocaleString('en-GB',{maximumFractionDigits:2})+'</small><b>'+esc(c.sportybet)+'</b></div>'+
        '<div class="bp-card-a"><button type="button" data-copy="'+esc(c.sportybet)+'">Copy</button><a class="bp-open" target="_blank" rel="noopener" href="https://www.sportybet.com/gh/?shareCode='+encodeURIComponent(c.sportybet)+'" aria-label="Open code on SportyBet">Open ↗</a></div></div>';}).join('')+
      ((h.msport||[]).length?'<h2 class="hp-code-h hp-code-h-ms"><img src="book-msport.webp" alt="MSport logo" width="28" height="28" decoding="async"> Book all of today’s picks on MSport</h2>'+h.msport.map(function(c,k){
      return '<div class="hp-code-c hp-code-ms"><div class="hp-code-i"><small>'+(h.msport.length>1?'Code '+(k+1)+' of '+h.msport.length+' · ':'')+esc(c.legs)+(c.of&&c.of>c.legs?' of '+esc(c.of):'')+' picks · total odds '+(c.totalOdds?Number(c.totalOdds).toLocaleString('en-GB',{maximumFractionDigits:2}):'—')+'</small><b>'+esc(c.msport)+'</b>'+(c.of&&c.of>c.legs?'<small class="hp-code-w">'+(c.of-c.legs)+' pick'+(c.of-c.legs>1?'s are':' is')+' not available on MSport</small>':'')+'</div>'+
        '<div class="bp-card-a"><button type="button" data-copy="'+esc(c.msport)+'">Copy</button><a class="bp-open" target="_blank" rel="noopener" href="https://www.msport.com/gh/sports/share?shareCode='+encodeURIComponent(c.msport)+'" aria-label="Open code on MSport">Open ↗</a></div></div>';}).join(''):'')+
      (h.bookedAt?'<p class="hp-code-n">Booked '+new Date(h.bookedAt).toLocaleString('en-GB',{timeZone:ZONE,day:'numeric',month:'short',hour:'2-digit',minute:'2-digit'})+' GMT · picks that had already kicked off are left out.</p>':'');}
  document.addEventListener('click',function(e){var w=e.target.closest&&e.target.closest('.hp-why');if(w){var o=w.getAttribute('aria-expanded')!=='true';w.setAttribute('aria-expanded',o);w.classList.toggle('is-open',o);var t=$(w.getAttribute('aria-controls'));if(t)t.hidden=!o;w.firstChild.nodeValue=o?'Hide why ':'Why this pick ';return;}
    var b=e.target.closest&&e.target.closest('#hp-code [data-copy]');if(!b)return;var c=b.getAttribute('data-copy'),ok=function(){b.textContent='Copied ✓';setTimeout(function(){b.textContent='Copy';},1600);};
    if(navigator.clipboard)navigator.clipboard.writeText(c).then(ok,ok);else{var t=document.createElement('textarea');t.value=c;document.body.appendChild(t);t.select();try{document.execCommand('copy');}catch(_){}t.remove();ok();}});
  var BK=[['sportybet','SportyBet','codes','https://www.sportybet.com/gh/?shareCode='],['msport','MSport','msport','https://www.msport.com/gh/sports/share?shareCode='],['betika','Betika','betika','https://betika.com/en-gh/share/']];
  function bookedFor(ids){var h=data.homeCode||{},out=[];BK.forEach(function(k){(h[k[2]]||[]).forEach(function(c){var m=c.matches||[];if(c[k[0]]&&ids.some(function(i){return m.indexOf(i)>=0;}))out.push({b:k[0],n:k[1],code:c[k[0]],url:k[3]+encodeURIComponent(c[k[0]])});});});return out;}
  function css(){if($('hp-lt-css'))return;var st=document.createElement('style');st.id='hp-lt-css';st.textContent=
    '.hp-lr{background:#111a27;border:1px solid #1f2a3a;border-radius:12px;padding:10px 12px;margin:8px 0}.hp-lr.is-off{opacity:.72}'+
    '.hp-lr-h{display:flex;flex-wrap:wrap;gap:6px 10px;align-items:center;justify-content:space-between}.hp-lr-h b{font-size:.95rem}.hp-lr-s{font-size:.8rem;color:#9fb0c6}'+
    '.hp-lr-st{font-size:.72rem;font-weight:700;padding:2px 8px;border-radius:99px;background:#1f2a3a;color:#9fb0c6}.hp-lr-st.ok{background:#0f3d2a;color:#5ee0a0}'+
    '.hp-lr-p{display:flex;flex-wrap:wrap;justify-content:space-between;gap:4px 10px;border-top:1px dashed #1f2a3a;margin-top:8px;padding-top:8px;font-size:.86rem}.hp-lr-p small{color:#9fb0c6}'+
    '.hp-bkd{display:flex;flex-wrap:wrap;gap:6px;width:100%;margin-top:4px}.hp-bkd>span{font-size:.72rem;font-weight:700;color:#5ee0a0;align-self:center}'+
    '.hp-bkd a{display:inline-flex;align-items:center;gap:5px;font-size:.75rem;padding:3px 8px;border-radius:99px;background:#16233a;color:#e6eefb;text-decoration:none;border:1px solid #27406a}.hp-bkd img{width:16px;height:16px;border-radius:4px}'+
    '.hp-lr-r{font-size:.8rem;color:#9fb0c6;margin-top:6px}.hp-lr-tg{background:none;border:0;color:#7fb2ff;font-size:.8rem;cursor:pointer;padding:4px 0}';
    document.head.appendChild(st);}
  function leagues(){css();
    var L=(data.leagues||[]).slice();
    if(!L.length){$('hp-leagues').innerHTML='<div class="p2u-bankers-empty">League table coming with today’s picks.</div>';return;}
    var hasStatus=L.some(function(x){return x.status;});
    if(hasStatus)L.sort(function(a,b){var r=function(x){return x.status==='pick'?0:x.qualifies?1:2;};return r(a)-r(b)||(Number(b.favWinPct)||0)-(Number(a.favWinPct)||0);});
    var withP=L.filter(function(x){return (x.picks||[]).length;}).length;
    var row=function(x){var f=Number(x.favWinPct);f=f<=1?f*100:f;var P=x.picks||[],on=P.length>0;
      var q=(x.qualifyingBands||[]).map(function(b){return 'fav '+esc(b.band)+': '+esc(b.market)+' '+Math.round(b.rate*100)+'% of '+esc(b.n);}).join(' · ');
      return '<div class="hp-lr'+(on?'':' is-off')+'"><div class="hp-lr-h"><b>'+esc(x.league)+'</b><span class="hp-lr-st'+(on?' ok':'')+'">'+(on?P.length+' pick'+(P.length>1?'s':''):'No pick')+'</span></div>'+
        '<div class="hp-lr-s"><span class="hp-bar"><i style="width:'+Math.round(f||0)+'%"></i></span>Fav. win '+(isFinite(f)?Math.round(f)+'%':'—')+' · '+esc(x.games==null?'—':x.games)+' games'+(q?' · '+q:'')+'</div>'+
        P.map(function(p){var bk=bookedFor([p.eventId]);return '<div class="hp-lr-p"><span>'+esc(p.match)+' <small>'+esc(String(p.ko||'').slice(0,5))+'</small></span><b>'+esc(p.selection)+' @'+Number(p.odds).toFixed(2)+'</b>'+
          (bk.length?'<div class="hp-bkd"><span>✓ Booked</span>'+bk.map(function(c){return '<a href="'+c.url+'" target="_blank" rel="noopener"><img src="book-'+c.b+'.webp" alt="'+c.n+' logo" width="16" height="16" loading="lazy">'+esc(c.n)+' '+esc(c.code)+'</a>';}).join('')+'</div>':'')+'</div>';}).join('')+
        (!on&&x.reason?'<div class="hp-lr-r">No pick: '+esc(x.reason)+'</div>':'')+'</div>';};
    var top=L.filter(function(x){return (x.picks||[]).length;}),rest=L.filter(function(x){return !(x.picks||[]).length;});
    $('hp-leagues').innerHTML=(hasStatus?'<p class="hp-lr-s">'+withP+' of '+L.length+' leagues on today’s card have a pick. Every pick is booked on the sites shown.</p>':'')+top.map(row).join('')+
      (rest.length?'<button type="button" class="hp-lr-tg" aria-expanded="false" data-lr-tg>Show '+rest.length+' leagues with no pick today ▾</button><div class="hp-lr-rest" hidden>'+rest.map(row).join('')+'</div>':'');
  }
  document.addEventListener('click',function(e){var t=e.target.closest&&e.target.closest('[data-lr-tg]');if(!t)return;var r=t.nextElementSibling,o=r.hidden;r.hidden=!o;t.setAttribute('aria-expanded',o);t.textContent=(o?'Hide':'Show')+' '+r.children.length+' leagues with no pick today '+(o?'▴':'▾');});
  function init(d){data=d||{};
    var dd=$('hp-day');dd.innerHTML='<option>'+esc(d.date||'—')+'</option>';dd.disabled=true;
    $('hp-meta').textContent=d.DATA_UPDATED?'Updated '+new Date(d.DATA_UPDATED).toLocaleString('en-GB',{timeZone:ZONE,day:'numeric',month:'short',hour:'2-digit',minute:'2-digit'})+' GMT':'';
    codes();render();leagues();}
  function missing(){init({date:'',picks:[],leagues:[]});$('hp-meta').textContent='Today’s picks are being prepared.';}
  fetch('home-picks.json',{cache:'no-cache'}).then(function(r){if(!r.ok)throw new Error(r.status);return r.json();}).then(init).catch(missing);
})();
