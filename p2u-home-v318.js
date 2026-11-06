/* Predict2U v353 hide-empty-codes — was v318b — favourites day-master codes on leagues section (Today/Tomorrow tabs); was v318. */
(function(){var _hcss=document.createElement('style');_hcss.textContent='.hp-odds{display:inline-flex;flex-direction:column;align-items:flex-end;background:#0f2a1a;border:1px solid #2ecc71;border-radius:10px;padding:4px 10px;line-height:1.15}.hp-odds b{font-size:1.15em;color:#2ecc71}.hp-odds small{font-size:.72em;opacity:.85}.hp-odds i{font-style:normal;font-size:.68em;opacity:.7}.hp-hist{margin:6px 0 4px;font-size:.8em;padding:6px 8px;border-left:3px solid #888;background:rgba(127,127,127,.08);border-radius:4px}.hp-hist.is-up{border-color:#2ecc71}.hp-hist.is-down{border-color:#e67e22}';document.head.appendChild(_hcss);
  'use strict';
  var $=function(id){return document.getElementById(id);};
  var esc=function(s){return String(s==null?'':s).replace(/[&<>"']/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c];});};
  var seoSlug=function(t){return String(t||'').toLowerCase().replace(/&/g,' and ').replace(/[^a-z0-9]+/g,'-').replace(/^-|-$/g,'').slice(0,72)||'item';};
  var matchHref=function(p){var m=p.match||'',sl=seoSlug(m),id=String(p.eventId||'').replace(/\D/g,'').slice(-8);if(id&&sl.indexOf(id)<0)sl+='-'+id;return 'match/'+sl+'.html';};
  var leagueHref=function(lg){return lg?('league/'+seoSlug(lg)+'.html'):'leagues.html';};
  var ZONE='Africa/Accra';
  function stamp(d){return new Intl.DateTimeFormat('en-CA',{timeZone:ZONE,year:'numeric',month:'2-digit',day:'2-digit'}).format(d);}
  function ko(iso){var d=new Date(iso);return isNaN(d)?'':d.toLocaleTimeString('en-GB',{timeZone:ZONE,hour:'2-digit',minute:'2-digit'});}
  function pct(x){return x==null?'—':Math.round(x*100)+'%';}
  function badge(r){r=r||'pending';return '<span class="bp-res bp-'+esc(r)+'">'+esc(r.toUpperCase())+'</span>';}
  var data;
  var MKN={fw:'Favourite win','1X':'Home or draw',X2:'Draw or away','12':'Home or away',o15:'Over 1.5',o25:'Over 2.5',u25:'Under 2.5',u35:'Under 3.5',btts:'BTTS Yes',nobtts:'BTTS No',hw:'Home win',aw:'Away win',d:'Draw'};
  var STN={favourite:'Favourite','balance':'Balance','draw-odds':'Draw odds','balance+draw-odds':'Balance + draw odds'};
  function stag(p){var s=p.strategy||'favourite';return '<span class="hp-stag hp-stag-'+esc(s.replace('+','-'))+'">'+esc(STN[s]||s)+'</span>';}
  function koTxt(p){if(p.ko&&String(p.ko).indexOf('T')>0)return ko(p.ko);return p.ko?String(p.ko).slice(0,5):'';}
  function rate(x){if(x==null||x==='')return '—';var n=Number(x);if(!isFinite(n))return esc(x);return Math.round(n<=1?n*100:n)+'%';}
  function render(){
    var P=(data.picks||[]).slice(),res=function(p){return String(p.result||'pending').toLowerCase();};
    var w=P.filter(function(p){return res(p)==='won';}),l=P.filter(function(p){return res(p)==='lost';}),pend=P.length-w.length-l.length;
    $('hp-tally').innerHTML='<div class="hp-t hp-tw"><b>'+w.length+'</b><span>Won today</span></div><div class="hp-t hp-tl"><b>'+l.length+'</b><span>Lost</span></div><div class="hp-t"><b>'+pend+'</b><span>Pending</span></div><div class="hp-t"><b>'+(w.length+l.length?Math.round(100*w.length/(w.length+l.length))+'%':'—')+'</b><span>Hit rate</span></div>'+
      (w.length?'<div class="hp-wonlist">'+w.map(function(p){return '<span>✓ '+esc(p.match)+' · '+esc(p.selection)+(p.score?' ('+esc(p.score)+')':'')+'</span>';}).join('')+'</div>':'');
    var hl=$('hp-list');if(hl){hl.innerHTML='';hl.hidden=true;}
  }
  var WHY=0;
  function oddsChip(p){if(p.odds==null)return '';var H=p.hist||{};return '<span class="hp-odds"><b>@'+Number(p.odds).toFixed(2)+'</b>'+(H.implied!=null?'<small>'+H.implied+'% implied</small>':'')+(H.band?'<i>band '+esc(H.band.replace('-','–'))+'</i>':'')+'</span>';}
  function histLine(p){var H=p.hist||{},b=[];if(!H.band)return '';
    if(H.site)b.push('our '+esc(H.market)+' picks in this band hit <b>'+H.site.rate+'%</b> (n='+H.site.n+')');else if(H.siteAll)b.push('our '+esc(H.market)+' picks hit <b>'+H.siteAll.rate+'%</b> overall (n='+H.siteAll.n+')');
    if(H.league)b.push('league '+H.league.rate+'% over '+H.league.n+' games');
    if(!b.length)return '';var cls=H.site&&H.implied!=null?(H.site.rate>=H.implied?' is-up':' is-down'):'';
    return '<p class="hp-hist'+cls+'">Falls in the <b>'+esc(H.band.replace('-','–'))+'</b> band · '+b.join(' · ')+'</p>';}
  function card(p){var i=WHY++,res=function(p){return String(p.result||'pending').toLowerCase();};{var c=Number(p.confidence);c=c>1?c/100:c;var g=c>=0.8?'A':c>=0.72?'B':'C';var r=res(p);
      return '<article class="hp-pick'+(r==='won'?' is-won':r==='lost'?' is-lost':'')+'" data-eid="'+esc(p.eventId||'')+'"><div class="hp-top"><span class="bp-grade bp-g'+g+'">'+g+'</span><div class="hp-mt"><b>'+esc(p.match)+'</b><small>'+esc(koTxt(p))+' · '+esc(p.league)+'</small></div>'+badge(r)+'</div>'+
        '<div class="hp-sel"><span>'+stag(p)+' '+esc(p.selection)+(p.market?' <small>'+esc(p.market)+'</small>':'')+'</span>'+oddsChip(p)+'</div>'+histLine(p)+
        '<dl class="hp-stats">'+(p.leagueFavRate!=null?'<div><dt>League fav. rate</dt><dd>'+rate(p.leagueFavRate)+'</dd></div>':'')+(p.sample!=null?'<div><dt>Sample</dt><dd>'+esc(p.sample)+' games</dd></div>':'')+(p.confidence!=null?'<div><dt>Our confidence</dt><dd>'+rate(p.confidence)+'</dd></div>':'')+'<div><dt>Score</dt><dd class="hp-score" data-score-eid="'+esc(p.eventId||'')+'">'+(p.score?esc(p.score):(window.P2UScores&&P2UScores.text(p.eventId))||'')+'</dd></div><div><dt>Result</dt><dd class="hp-resline" data-res-eid="'+esc(p.eventId||'')+'">'+badge(r)+'</dd></div></dl>'+
        (p['case']?'<button type="button" class="hp-why" aria-expanded="false" aria-controls="hpw'+i+'">Why this pick <i class="bp-chev" aria-hidden="true"></i></button><p class="hp-case" id="hpw'+i+'" hidden>'+esc(p['case'])+'</p>':'')+'<p class="hp-seo"><a href="'+matchHref(p)+'">Match page</a> · <a href="'+leagueHref(p.league)+'">League</a></p></article>';}
  }
  function codes(){var el=$('hp-code');if(!el)return;var h=data.homeCode||{},C=h.codes||[];
    if(!C.length){el.innerHTML='';el.hidden=true;return;}el.hidden=false;
    var fo2=function(x){return x?Number(x).toLocaleString('en-GB',{maximumFractionDigits:2}):'—';};
    var row=function(b,nm,L,key){return (L||[]).filter(function(c){var code=c[key]||c.code;return window.P2UCode?P2UCode.isReal(code):!!code;}).map(function(c,k){var code=c[key]||c.code;return '<div class="p2u-chip p2u-chip-'+b+'"><img src="book-'+b+'.webp" alt="" width="24" height="24" loading="lazy"><span class="p2u-chip-t"><span class="p2u-chip-n">'+nm+(L.length>1?' · code '+(k+1)+'/'+L.length:'')+'</span><a class="p2u-chip-c" target="_blank" rel="noopener" href="'+BKI[b][1]+encodeURIComponent(code)+'">'+esc(code)+'</a><span class="p2u-chip-o">@'+fo2(c.totalOdds)+' · '+esc(c.legs)+(c.of&&c.of>c.legs?'/'+esc(c.of):'')+' picks</span></span><button type="button" class="p2u-chip-cp" data-copy="'+esc(code)+'" aria-label="Copy '+nm+' code">Copy</button></div>';}).join('');};
    var chipHtml=row('sportybet','SportyBet',C,'sportybet')+row('msport','MSport',h.msport,'msport')+row('betika','Betika',h.betika,'betika')+row('footballcom','football.com',h.footballcom,'footballcom')+row('betpawa','Betpawa',h.betpawa,'betpawa')+row('betway','Betway',h.betway,'betway');
    el.innerHTML=(chipHtml?'<h2 class="hp-code-h">Book all of today’s picks</h2><div class="p2u-chips">'+chipHtml+'</div>':'')+
      (h.bookedAt?'<p class="hp-code-n">Booked '+new Date(h.bookedAt).toLocaleString('en-GB',{timeZone:ZONE,day:'numeric',month:'short',hour:'2-digit',minute:'2-digit'})+' GMT · picks that had already kicked off are left out. Tap a code to open it.</p>':'');}
  document.addEventListener('click',function(e){var w=e.target.closest&&e.target.closest('.hp-why');if(w){var o=w.getAttribute('aria-expanded')!=='true';w.setAttribute('aria-expanded',o);w.classList.toggle('is-open',o);var t=$(w.getAttribute('aria-controls'));if(t)t.hidden=!o;w.firstChild.nodeValue=o?'Hide why ':'Why this pick ';return;}
    var b=e.target.closest&&e.target.closest('#hp-code [data-copy],#hp-mkt [data-copy]');if(!b)return;var c=b.getAttribute('data-copy'),ok=function(){b.textContent='Copied ✓';setTimeout(function(){b.textContent='Copy';},1600);};
    if(navigator.clipboard)navigator.clipboard.writeText(c).then(ok,ok);else{var t=document.createElement('textarea');t.value=c;document.body.appendChild(t);t.select();try{document.execCommand('copy');}catch(_){}t.remove();ok();}});
  var BK=[['sportybet','SportyBet','codes','https://www.sportybet.com/gh/?shareCode='],['msport','MSport','msport','https://www.msport.com/gh/?shareCode='],['betika','Betika','betika','https://betika.com/en-gh/share/'],['footballcom','football.com','footballcom','https://www.football.com/gh/?shareCode='],['betpawa','Betpawa','betpawa','https://www.betpawa.com.gh/share-betslip/'],['betway','Betway','betway','https://www.betway.com.gh/sport/soccer?bookingCode=']];
  function bookedFor(ids){var h=data.homeCode||{},out=[];BK.forEach(function(k){(h[k[2]]||[]).forEach(function(c){var m=c.matches||[],code=c[k[0]]||c.code;if(!(window.P2UCode?P2UCode.isReal(code):!!code))return;if(ids.some(function(i){return m.indexOf(i)>=0;}))out.push({b:k[0],n:k[1],code:code,url:k[3]+encodeURIComponent(code)});});});return out;}
  function css(){if($('hp-lt-css'))return;var st=document.createElement('style');st.id='hp-lt-css';st.textContent=
    '.hp-lr{background:#111a27;border:1px solid #1f2a3a;border-radius:12px;padding:10px 12px;margin:8px 0}.hp-lr.is-off{opacity:.72}'+
    '.hp-lr-h{display:flex;flex-wrap:wrap;gap:6px 10px;align-items:center;justify-content:space-between}.hp-lr-h b{font-size:.95rem}.hp-lr-s{font-size:.8rem;color:#9fb0c6}'+
    '.hp-lr-st{font-size:.72rem;font-weight:700;padding:2px 8px;border-radius:99px;background:#1f2a3a;color:#9fb0c6}.hp-lr-st.ok{background:#0f3d2a;color:#5ee0a0}'+
    '.hp-lr-p{display:flex;flex-wrap:wrap;justify-content:space-between;gap:4px 10px;border-top:1px dashed #1f2a3a;margin-top:8px;padding-top:8px;font-size:.86rem}.hp-lr-p small{color:#9fb0c6}'+
    '.hp-bkd{display:flex;flex-wrap:wrap;gap:6px;width:100%;margin-top:4px}.hp-bkd>span{font-size:.72rem;font-weight:700;color:#5ee0a0;align-self:center}'+
    '.hp-bkd a{display:inline-flex;align-items:center;gap:5px;font-size:.75rem;padding:3px 8px;border-radius:99px;background:#16233a;color:#e6eefb;text-decoration:none;border:1px solid #27406a}.hp-bkd img{width:16px;height:16px;border-radius:4px}'+
    '.hp-stag{display:inline-block;font-size:.66rem;font-weight:800;letter-spacing:.02em;padding:1px 7px;border-radius:99px;background:#16233a;color:#bcd3ff;border:1px solid #2c4a7a;vertical-align:middle}.hp-stag-balance,.hp-stag-balance-draw-odds{background:#2a1f3d;color:#e0c8ff;border-color:#5b3f8a}.hp-stag-draw-odds{background:#3a2a12;color:#ffd99a;border-color:#7a5a20}'+
    '.hp-bkw{margin-top:8px;border-top:1px dashed #1f2a3a;padding-top:6px}.hp-bkw summary{cursor:pointer;color:#a9c9ff;font-size:.84rem;font-weight:700;padding:4px 0}.hp-bk-sc{overflow-x:auto}'+
    '.hp-bk{width:100%;border-collapse:collapse;font-size:.8rem;color:#e6eefb;margin:6px 0;min-width:520px}.hp-bk caption{text-align:left;font-weight:700;color:#e6eefb;padding:4px 0}.hp-bk th,.hp-bk td{padding:5px 6px;border-bottom:1px solid #1f2a3a;text-align:left}.hp-bk thead th{color:#c3d0e2;font-weight:700}.hp-bk th small{display:block;color:#b4c2d6;font-weight:400}'+
    '.hp-bk tr.is-used th,.hp-bk tr.is-used td{background:#0f2e22}.hp-bk-u{font-size:.66rem;background:#0f3d2a;color:#7ff0b8;border-radius:99px;padding:1px 6px}.hp-bk-s td{color:#7ff0b8;font-size:.76rem}.hp-bk-n{font-size:.76rem;color:#b4c2d6;margin:4px 0}'+
    '.hp-mkt{margin:14px 0}.hp-mkt-l{display:block;font-size:.85rem;color:#c3d0e2;margin:4px 0}.hp-mkt-s{width:100%;max-width:420px;font-size:1rem;padding:10px 12px;border-radius:10px;background:#111a27;color:#fff;border:1px solid #3a5a8a;min-height:44px}.hp-mkt-s:focus{outline:2px solid #7fb2ff;outline-offset:2px}'+
    '#hp-mkt-b .hp-code-c{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin:8px 0}#hp-mkt-b img{border-radius:6px}.hp-mk-sportybet{border-left:4px solid #e41827}.hp-mk-msport{border-left:4px solid #ffd400}.hp-mk-betika{border-left:4px solid #26a64a}'+
    '.p2u-chip .p2u-chip-c::after,.p2u-chip .p2u-chip-c::before,.cc-card .cc-code::after,.p2u-chip::before,.p2u-chip::after{content:none!important;display:none!important;animation:none!important}.p2u-chip .p2u-chip-c{background:none!important;-webkit-text-fill-color:currentColor!important;animation:none!important}#hp-code .p2u-chips{margin:8px 0}.hp-code-h small{display:block;font-size:.78rem;font-weight:500;color:#b9c8dc}.mk-p{margin:8px 0;border-radius:14px;background:linear-gradient(135deg,rgba(20,32,52,.92),rgba(12,18,30,.95));border:1px solid rgba(120,170,255,.28);box-shadow:0 0 0 1px rgba(255,255,255,.03),0 6px 18px rgba(0,0,0,.35);overflow:hidden}'+
    '.mk-p[open]{border-color:rgba(127,178,255,.7);box-shadow:0 0 18px rgba(80,140,255,.25)}.mk-p>summary{list-style:none;cursor:pointer;display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:6px 10px;padding:12px 40px 12px 14px;position:relative;min-height:44px}.mk-p>summary::-webkit-details-marker{display:none}'+
    '.mk-p>summary::after{content:"▾";position:absolute;right:14px;top:50%;transform:translateY(-50%);color:#9ec3ff;transition:transform .2s}.mk-p[open]>summary::after{transform:translateY(-50%) rotate(180deg)}'+
    '.mk-t b{display:block;color:#fff;font-size:1rem}.mk-t small{color:#c8d6ea;font-size:.8rem}.mk-logos{display:flex;flex-wrap:wrap;gap:4px}.mk-lg{display:inline-flex;align-items:center;gap:4px;padding:2px 6px;border-radius:999px;background:rgba(255,255,255,.07);font-size:.72rem}.mk-lg img{border-radius:4px}.mk-lg code{color:#fff;font-weight:700}'+
    '.mk-v{padding:4px 12px 12px}.mk-v h4{margin:8px 0 6px;font-size:.88rem;color:#ffd96a}.mk-chips{display:grid;gap:6px}.mk-act{grid-column:1/-1}'+
    
    '.mk-act{display:flex;gap:6px;justify-content:flex-end}.mk-act button,.mk-act a{min-height:36px;padding:6px 12px;border-radius:8px;border:1px solid rgba(127,178,255,.5);background:rgba(127,178,255,.12);color:#fff;font-size:.82rem;text-decoration:none;cursor:pointer}'+
    '.mk-pl summary{cursor:pointer;color:#9ec3ff;font-size:.85rem;padding:8px 0;min-height:36px}@media(max-width:340px){.mk-p>summary{padding:10px 34px 10px 10px}.mk-act{margin-left:0;width:100%}.mk-act>*{flex:1;text-align:center}.mk-v{padding:4px 8px 10px}}'+
    '.hp-mkt-p{list-style:none;margin:8px 0;padding:0}.hp-mkt-p li{display:flex;flex-wrap:wrap;justify-content:space-between;gap:4px 10px;padding:6px 0;border-bottom:1px dashed #1f2a3a;font-size:.88rem;color:#e6eefb}.hp-mkt-p small{color:#b4c2d6}'+
    '.hp-lr-r{font-size:.8rem;color:#9fb0c6;margin-top:6px}.hp-lr-tg{background:none;border:0;color:#7fb2ff;font-size:.8rem;cursor:pointer;padding:4px 0}';
    st.textContent+='.hp-seo{margin:10px 0 0;font-size:.8rem}.hp-seo a{color:#ffd36b;font-weight:800;min-height:40px;display:inline-flex;align-items:center;margin-right:6px}';
    document.head.appendChild(st);}
  function buckets(x){var B=x.buckets;if(!B)return '';var used={};(x.picks||[]).forEach(function(p){if(p.bucket)p.bucket.split('+').forEach(function(k){used[k]=1;});});
    var tr=function(r){var u=used[r.key];return '<tr'+(u?' class="is-used"':'')+'><th scope="row">'+esc(r.label)+(u?' <span class="hp-bk-u">today’s pick</span>':'')+'<small>'+esc(r.n)+' games'+(r.n<20?' · too few':'')+'</small></th><td>'+r.home+'/'+r.draw+'/'+r.away+'</td><td>'+r.fav+'%</td><td>'+r.o25+'/'+r.u25+'</td><td>'+r.o35+'/'+r.u35+'</td><td>'+r.btts+'%</td><td>'+r.dc1X+'/'+r.dcX2+'/'+r.dc12+'</td></tr>'+
      (r.strong&&r.strong.length?'<tr class="hp-bk-s"><td colspan="7">70%+: '+r.strong.map(function(s){return esc(MKN[s.market]||s.market)+' '+s.rate+'%';}).join(' · ')+'</td></tr>':'');};
    var tb=function(t,R){return '<table class="hp-bk"><caption>'+t+'</caption><thead><tr><th scope="col">Bucket</th><th scope="col">H/D/A %</th><th scope="col">Fav win</th><th scope="col">O/U 2.5</th><th scope="col">O/U 3.5</th><th scope="col">BTTS</th><th scope="col">1X/X2/12</th></tr></thead><tbody>'+R.map(tr).join('')+'</tbody></table>';};
    return '<details class="hp-bkw p2u-legible"><summary>Balanced vs unbalanced · High vs low draw odds</summary><div class="hp-bk-sc">'+tb('Balanced vs unbalanced',B.balance||[])+tb('High vs low draw odds',B.drawOdds||[])+'</div>'+
      '<p class="hp-bk-n">'+esc(B.sample)+' games, '+esc(B.priceSource)+'. Balanced: '+esc(B.cutoffs.balanced)+'. Low: '+esc(B.cutoffs.drawLow)+'. High: '+esc(B.cutoffs.drawHigh)+'.</p></details>';}
  var MORDER=['Home win','Away win','Draw no bet (home)','Draw no bet (away)','Over 0.5','Over 1.5','Over 2.5','Over 3.5','Under 2.5','Under 3.5','Under 4.5','BTTS Yes','BTTS No','Home team over 0.5','Away team over 0.5','Half-time over 0.5','Draw'];
  var BKI={sportybet:['SportyBet','https://www.sportybet.com/gh/?shareCode='],msport:['MSport','https://www.msport.com/gh/?shareCode='],betika:['Betika','https://betika.com/en-gh/share/'],footballcom:['football.com','https://www.football.com/gh/?shareCode='],betpawa:['Betpawa','https://www.betpawa.com.gh/share-betslip/'],betway:['Betway','https://www.betway.com.gh/sport/soccer?bookingCode=']};
  function fo(x){return Number(x).toLocaleString('en-GB',{maximumFractionDigits:2});}
  function chip(b,c,full){var parts=(c.parts||[c]).filter(function(x){return window.P2UCode?P2UCode.isReal(x&&x.code):!!(x&&x.code);});if(!parts.length)return '';return parts.map(function(c,i){return '<div class="p2u-chip p2u-chip-'+b+' mk-chip"><img src="book-'+b+'.webp" alt="'+BKI[b][0]+' logo" width="24" height="24" loading="lazy"><span class="p2u-chip-t"><span class="p2u-chip-n">'+BKI[b][0]+(parts.length>1?' '+(i+1)+'/'+parts.length:'')+'</span><a class="p2u-chip-c" target="_blank" rel="noopener" href="'+BKI[b][1]+encodeURIComponent(c.code)+'">'+esc(c.code)+'</a><span class="p2u-chip-o">@'+fo(c.totalOdds)+' · '+esc(c.legs)+(c.of>c.legs?'/'+esc(c.of):'')+' picks</span></span>'+'<button type="button" class="p2u-chip-cp" data-copy="'+esc(c.code)+'" aria-label="Copy '+BKI[b][0]+' code">Copy</button></div>';}).join('');}
  function variant(v,lab){if(!v)return '';var bk=Object.keys(BKI).filter(function(b){var x=v[b];if(!x)return false;var c=x.parts?x.parts[0]:x;return window.P2UCode?P2UCode.isReal(c&&(c.code||c)):!!(c&&(c.code||c));}),n=(v.picks||[]).length;
    return '<div class="mk-v"><h4>'+lab+' · '+n+' picks · '+fo(v.totalOdds)+' odds</h4><div class="mk-chips">'+bk.map(function(b){return chip(b,v[b],1);}).join('')+'</div>'+
      '<details class="mk-pl"><summary>Show '+n+' picks</summary><ul class="hp-mkt-p">'+(v.picks||[]).map(function(p){return '<li><span>'+esc(p.match)+' <small>'+esc((p.date||'').slice(5)+' '+(p.ko||''))+(p.rate?' · '+Math.round(p.rate*100)+'% of '+esc(p.n):'')+'</small></span><b>'+esc(p.selection)+' @'+Number(p.odds).toFixed(2)+'</b></li>';}).join('')+'</ul></details></div>';}
  function markets(){var host=$('hp-code');if(!host)return;var M=(data.homeCode||{}).byMarket||{};
    Object.keys(M).forEach(function(k){if(/double chance/i.test(k)||(M[k]&&M[k].picks&&!M[k].full))delete M[k];});
    var K=MORDER.filter(function(k){return M[k];}).concat(Object.keys(M).filter(function(k){return MORDER.indexOf(k)<0;}));
    var w=$('hp-mkt');if(!w){w=document.createElement('section');w.id='hp-mkt';w.className='hp-mkt p2u-legible';host.parentNode.insertBefore(w,host.nextSibling);}
    if(!K.length){w.hidden=true;return;}w.hidden=false;
    w.innerHTML='<h2 class="hp-code-h">Codes by market <small>'+K.length+' markets · tap to open</small></h2>'+K.map(function(k){var m=M[k],f=m.full||{},bk=Object.keys(BKI).filter(function(b){var x=f[b];if(!x)return false;var c=x.parts?x.parts[0]:x;return window.P2UCode?P2UCode.isReal(c&&(c.code||c)):!!(c&&(c.code||c));});
      return '<details class="mk-p"><summary><span class="mk-t"><b>'+esc(k)+'</b><small>'+(f.picks||[]).length+' picks · '+fo(f.totalOdds)+' odds</small></span><span class="mk-logos">'+bk.map(function(b){var c=f[b].parts?f[b].parts[0]:f[b];return '<span class="mk-lg"><img src="book-'+b+'.webp" alt="'+BKI[b][0]+'" width="18" height="18" loading="lazy"><code>'+esc(c.code)+'</code></span>';}).join('')+'</span></summary>'+
        variant(m.safe,'Safe (top 5)')+variant(m.full,'Full')+'</details>';}).join('');}
  var FL={Argentina:'🇦🇷',Azerbaijan:'🇦🇿',Bolivia:'🇧🇴',Botswana:'🇧🇼',Brazil:'🇧🇷',Chile:'🇨🇱',Colombia:'🇨🇴','Costa Rica':'🇨🇷',Cyprus:'🇨🇾',Ecuador:'🇪🇨',Egypt:'🇪🇬','El Salvador':'🇸🇻',France:'🇫🇷',Honduras:'🇭🇳',India:'🇮🇳',Iran:'🇮🇷',Iraq:'🇮🇶',Israel:'🇮🇱','Ivory Coast':'🇨🇮',Jordan:'🇯🇴',Kosovo:'🇽🇰',Mexico:'🇲🇽',Oman:'🇴🇲',Paraguay:'🇵🇾',Peru:'🇵🇪',Qatar:'🇶🇦',Romania:'🇷🇴',Russia:'🇷🇺',Rwanda:'🇷🇼',Senegal:'🇸🇳',Uganda:'🇺🇬',Uzbekistan:'🇺🇿',Venezuela:'🇻🇪',Zambia:'🇿🇲',Australia:'🇦🇺',England:'🏴󠁧󠁢󠁥󠁮󠁧󠁿',Spain:'🇪🇸',Germany:'🇩🇪',Italy:'🇮🇹',Portugal:'🇵🇹',Netherlands:'🇳🇱',Ghana:'🇬🇭',Nigeria:'🇳🇬','South Africa':'🇿🇦',Kenya:'🇰🇪',Morocco:'🇲🇦',Tunisia:'🇹🇳',Algeria:'🇩🇿',Turkey:'🇹🇷',Greece:'🇬🇷',Belgium:'🇧🇪',Scotland:'🏴󠁧󠁢󠁳󠁣󠁴󠁿',USA:'🇺🇸',Japan:'🇯🇵','Saudi Arabia':'🇸🇦',China:'🇨🇳','South Korea':'🇰🇷',Uruguay:'🇺🇾',Poland:'🇵🇱',Austria:'🇦🇹',Switzerland:'🇨🇭',Denmark:'🇩🇰',Sweden:'🇸🇪',Norway:'🇳🇴',Ukraine:'🇺🇦',Croatia:'🇭🇷',Serbia:'🇷🇸',Czechia:'🇨🇿',Guatemala:'🇬🇹',Tanzania:'🇹🇿',Cameroon:'🇨🇲'};
  function split(n){var i=String(n).indexOf(' - ');return i>0?[n.slice(0,i),n.slice(i+3)]:['',n];}
  function flag(n){var c=split(n)[0];if(/^International/.test(c))return /UEFA|Europ/.test(n)?'🇪🇺':/AFC|Asia/.test(n)?'🌏':/CAF|Africa/.test(n)?'🌍':/CONMEBOL|Libertadores|Sudamericana/.test(n)?'🌎':'🌐';return FL[c]||'⚽';}
  function fdate(f){return String(f.ko||'').slice(0,10);}
  function fko(f){var k=String(f.ko||'');return k.length>10?k.slice(11,16):'';}
  var LKEY='p2u-lg-open-',open={},day='';
  function save(){try{sessionStorage.setItem(LKEY+day,JSON.stringify(open));}catch(_){}}
  function css2(){if($('hp-lg2-css'))return;var st=document.createElement('style');st.id='hp-lg2-css';st.textContent=
    '.lg-tools{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin:8px 0 12px}.lg-tools input{flex:1 1 180px;min-width:0;min-height:44px;font-size:1rem;padding:8px 12px;border-radius:12px;background:#0d1522;color:#fff;border:1px solid #3a5a8a}.lg-tools input:focus{outline:2px solid #7fb2ff;outline-offset:2px}'+
    '.lg-tools button,.lg-days button{min-height:44px;padding:0 14px;border-radius:999px;border:1px solid #2c4a7a;background:#16233a;color:#e6eefb;font-weight:800;font-size:.85rem;cursor:pointer}.lg-days{display:flex;gap:8px;flex-wrap:wrap;margin:6px 0}.lg-days button[aria-pressed=true]{background:linear-gradient(135deg,#ffcc33,#ff7a18);color:#111;border-color:transparent}'+
    '.lg-sum{font-size:.85rem;color:#c3d0e2;margin:4px 0}.lg{background:#111a27;border:1px solid #24324a;border-radius:14px;margin:8px 0;overflow:hidden;transition:border-color .2s,box-shadow .2s}.lg.is-open{border-color:#3d6bb3;box-shadow:0 0 0 1px rgba(127,178,255,.25),0 6px 24px rgba(0,0,0,.35)}'+
    '.lg-h{all:unset;box-sizing:border-box;display:flex;align-items:center;gap:10px;width:100%;padding:12px;cursor:pointer;min-height:56px}.lg-h:focus-visible{outline:2px solid #7fb2ff;outline-offset:-2px}.lg-f{font-size:1.5rem;line-height:1;flex:none}'+
    '.lg-n{flex:1;min-width:0}.lg-n b{display:block;color:#fff;font-size:.98rem;overflow-wrap:anywhere}.lg-n small{display:block;color:#b4c2d6;font-size:.75rem}.lg-m{display:flex;flex-wrap:wrap;justify-content:flex-end;gap:4px;flex:none;max-width:48%}'+
    '.lg-chip{font-size:.7rem;font-weight:800;padding:3px 8px;border-radius:99px;background:#1f2a3a;color:#d6e2f3;white-space:nowrap}.lg-chip.p{background:#0f3d2a;color:#7ff0b8}.lg-chip.b{background:#3a2a12;color:#ffd99a}'+
    '.lg-cv{flex:none;width:10px;height:10px;border-right:2px solid #a9c9ff;border-bottom:2px solid #a9c9ff;transform:rotate(45deg);transition:transform .25s;margin:0 4px}.lg.is-open .lg-cv{transform:rotate(225deg)}'+
    '.lg-b{display:grid;grid-template-rows:0fr;transition:grid-template-rows .3s ease}.lg.is-open .lg-b{grid-template-rows:1fr}.lg-b>div{overflow:hidden;min-height:0}.lg-in{padding:0 12px 12px}'+
    '.lg-in h3{font-size:.82rem;text-transform:uppercase;letter-spacing:.08em;color:#a9c9ff;margin:12px 0 6px}.lg-fx{list-style:none;margin:0;padding:0}.lg-fx li{display:flex;gap:10px;justify-content:space-between;padding:7px 0;border-bottom:1px dashed #24324a;font-size:.88rem;color:#e6eefb}.lg-fx time{font-weight:800;color:#ffd36b;flex:none}.lg-fx span{flex:1;min-width:0;overflow-wrap:anywhere}.lg-fx em{font-style:normal;font-size:.7rem;color:#7ff0b8;flex:none}'+
    '.lg-in .hp-list{display:grid;grid-template-columns:repeat(auto-fill,minmax(min(100%,280px),1fr));gap:10px}.lg-ft{width:100%;border-collapse:collapse;font-size:.82rem;color:#e6eefb}.lg-ft th,.lg-ft td{padding:5px 6px;border-bottom:1px solid #24324a;text-align:left}.lg-ft thead th{color:#c3d0e2}'+
    '.lg-q{display:flex;flex-wrap:wrap;gap:6px;margin:0;padding:0;list-style:none}.lg-q li{font-size:.76rem;padding:3px 9px;border-radius:99px;background:#16233a;color:#d6e2f3;border:1px solid #2c4a7a}.lg-empty{color:#c3d0e2;font-size:.9rem;padding:10px 0}'+
    '.lg-dm{margin:10px 0 14px;padding:12px;border-radius:14px;background:#0d1522;border:1px solid #2c4a7a}.lg-dm h3{margin:0 0 6px;font-size:.82rem;text-transform:uppercase;letter-spacing:.08em;color:#a9c9ff}.lg-dm .lg-sum{margin:0 0 10px}.lg-dm-chips{display:flex;flex-wrap:wrap;gap:8px}.lg-dm-chips a{display:inline-flex;align-items:center;gap:6px;min-height:40px;padding:6px 12px;border-radius:10px;text-decoration:none;font-weight:800;font-size:.82rem;background:var(--brand,#c8101e);color:var(--on,#fff);border:1px solid rgba(0,0,0,.25);box-shadow:0 4px 14px rgba(0,0,0,.35)}.lg-dm-chips a img{width:18px;height:18px;border-radius:4px;background:#fff}.lg-dm-chips .lg-dm-meta{font-weight:600;opacity:.9;font-size:.72rem}'+
    '@media(max-width:400px){.lg-h{flex-wrap:wrap;position:relative;padding-right:34px}.lg-cv{position:absolute;right:12px;top:22px}.lg-m{max-width:none;width:100%;justify-content:flex-start;padding-left:34px}}@media(prefers-reduced-motion:reduce){.lg-b,.lg-cv{transition:none}}';
    document.head.appendChild(st);}
  function body(x,F){var f=Number(x.favWinPct);f=f<=1?f*100:f;var P=x.picks||[],ids=P.map(function(p){return p.eventId;}),bk=bookedFor(ids),h='';
    var pid={};P.forEach(function(p){pid[p.eventId]=1;});
    h+='<h3>Fixtures today</h3><ul class="lg-fx">'+F.map(function(z){return '<li><time>'+esc(fko(z))+'</time><span>'+esc(z.match)+'</span>'+(pid[z.eventId]||z.status==='pick'?'<em>✓ pick</em>':'')+'</li>';}).join('')+'</ul>';
    if(P.length)h+='<h3>Our picks</h3><div class="hp-list">'+P.map(function(p){var b=bookedFor([p.eventId]);return card(p).replace('</article>',(b.length?'<div class="hp-bkd"><span>✓ Booked</span>'+b.map(function(c){return '<a href="'+c.url+'" target="_blank" rel="noopener"><img src="book-'+c.b+'.webp" alt="'+c.n+' logo" width="16" height="16" loading="lazy">'+esc(c.n)+' '+esc(c.code)+'</a>';}).join('')+'</div>':'')+'</article>');}).join('')+'</div>';
    else h+='<p class="lg-empty">No pick in this league today'+(x.reason?': '+esc(x.reason):'.')+'</p>';
    var B=x.bands||{},bk2=Object.keys(B).sort();
    h+='<h3>How favourites perform</h3><p class="lg-sum">Favourite win '+(isFinite(f)?Math.round(f)+'%':'—')+' · '+esc(x.sample==null?'—':x.sample)+' priced games of '+esc(x.games==null?'—':x.games)+(x.recentForm?' · recent: '+esc(x.recentForm):'')+(x.thin?' · thin sample':'')+'</p>'+
      (bk2.length?'<div class="hp-bk-sc"><table class="lg-ft"><thead><tr><th scope="col">Fav. price band</th><th scope="col">Games</th><th scope="col">Fav. win</th></tr></thead><tbody>'+bk2.map(function(k){return '<tr><th scope="row">'+esc(k)+'</th><td>'+esc(B[k].n)+'</td><td>'+esc(B[k].winPct)+'%</td></tr>';}).join('')+'</tbody></table></div>':'');
    var Q=x.qualifyingBands||[];
    if(Q.length)h+='<h3>Qualifying bands</h3><ul class="lg-q">'+Q.map(function(b){return '<li>'+(b.bucket?esc(b.band)+': '+esc(MKN[b.market]||b.market):'Fav '+esc(b.band)+': '+esc(b.market))+' · '+Math.round(b.rate*100)+'% of '+esc(b.n)+'</li>';}).join('')+'</ul>';
    if(x.buckets)h+=buckets(x).replace('<details class="hp-bkw','<details open class="hp-bkw');
    if(bk.length)h+='<h3>Booked codes with this league</h3><div class="hp-bkd">'+bk.map(function(c){return '<a href="'+c.url+'" target="_blank" rel="noopener"><img src="book-'+c.b+'.webp" alt="'+c.n+' logo" width="16" height="16" loading="lazy">'+esc(c.n)+' '+esc(c.code)+'</a>';}).join('')+'</div>';
    return '<div class="lg-in">'+h+'</div>';}

  var DMBK=[['sportybet','SportyBet','#c8101e','#fff','https://www.sportybet.com/gh/?shareCode='],['footballcom','football.com','#282450','#fff','https://www.football.com/gh/?shareCode='],['msport','MSport','#ffd325','#111','https://www.msport.com/gh/?shareCode='],['betika','Betika','#00813f','#fff','https://betika.com/en-gh/share/'],['betpawa','Betpawa','#78be20','#0b0f14','https://www.betpawa.com.gh/share-betslip/'],['betway','Betway','#0b0b0b','#fff','https://www.betway.com.gh/sport/soccer?bookingCode=']];
  function dayMasterHTML(day){
    var dm=((data.homeCode||{}).dayMasters||{})[day];
    if(!dm||!dm.codes||!Object.keys(dm.codes).length) return '';
    var chips='';
    DMBK.forEach(function(k){
      var list=dm.codes[k[0]]; if(!list)return;
      if(!Array.isArray(list)) list=[{code:list}];
      list.forEach(function(c){
        var code=c.code||c[k[0]]||c; if(!(window.P2UCode?P2UCode.isReal(code):!!code))return;
        var url=c.link||(k[4]+encodeURIComponent(code));
        var meta=(c.totalOdds!=null?' @'+Number(c.totalOdds).toLocaleString('en-GB',{maximumFractionDigits:2}):'')+(c.legs!=null?' · '+c.legs+'p':'');
        chips+='<a class="p2u-chip-'+k[0]+'" style="--brand:'+k[2]+';--on:'+k[3]+'" href="'+esc(url)+'" target="_blank" rel="noopener" title="'+esc(k[1]+' '+code)+'"><img src="book-'+k[0]+'.webp" alt="" width="18" height="18" loading="lazy"><span>'+esc(k[1])+' '+esc(code)+'</span><span class="lg-dm-meta">'+esc(meta)+'</span></a>';
      });
    });
    if(!chips) return '';
    var note=dm.note?('<p class="lg-sum">'+esc(dm.note)+'</p>'):'';
    var head=esc(dm.label||'Favourites of the day')+' · '+esc(dm.legs||'—')+' of '+esc(dm.of||'—')+' picks · @'+(dm.totalOdds!=null?Number(dm.totalOdds).toLocaleString('en-GB',{maximumFractionDigits:2}):'—')+(dm.parts>1?' · '+dm.parts+' parts':'');
    return '<div class="lg-dm" role="region" aria-label="Favourites booking codes for '+esc(day)+'"><h3>Booking codes</h3><p class="lg-sum">'+head+'</p>'+note+'<div class="lg-dm-chips">'+chips+'</div></div>';
  }

  function leagues(){css();css2();var host=$('hp-leagues');var hd=host.parentNode.querySelector('h2');if(hd)hd.textContent='Today’s leagues & competitions';
    var L=(data.leagues||[]);
    var today=stamp(new Date()),dates={};L.forEach(function(x){(x.fixtures||[]).forEach(function(f){var d=fdate(f);if(d>=today)dates[d]=1;});});
    var D=Object.keys(dates).sort();
    if(!day||D.indexOf(day)<0)day=D.indexOf(today)>=0?today:(D[0]||today);
    try{open=JSON.parse(sessionStorage.getItem(LKEY+day)||'{}')||{};}catch(_){open={};}
    var rows=L.map(function(x){var F=(x.fixtures||[]).filter(function(f){return fdate(f)===day;}).sort(function(a,b){return String(a.ko).localeCompare(String(b.ko));});
      var P=(x.picks||[]).filter(function(p){return !p.date||p.date===day||F.some(function(f){return f.eventId===p.eventId;});});
      return {x:Object.assign({},x,{picks:P}),F:F,first:F.length?String(F[0].ko):'~'};}).filter(function(r){return r.F.length;});
    rows.sort(function(a,b){return a.first.localeCompare(b.first)||b.x.picks.length-a.x.picks.length;});
    var lbl=function(d){return d===today?'Today':(d===stamp(new Date(Date.now()+864e5))?'Tomorrow':d);};
    var games=rows.reduce(function(s,r){return s+r.F.length;},0),picks=rows.reduce(function(s,r){return s+r.x.picks.length;},0);
    if(!rows.length){host.innerHTML='<div class="p2u-bankers-empty">No leagues on today’s card yet.</div>';return;}
    host.innerHTML=(D.length>1?'<div class="lg-days" role="group" aria-label="Match day">'+D.map(function(d){return '<button type="button" data-lg-day="'+d+'" aria-pressed="'+(d===day)+'">'+lbl(d)+'</button>';}).join('')+'</div>':'')+
      '<p class="lg-sum">'+lbl(day)+': '+rows.length+' leagues · '+games+' games · '+picks+' picks. Tap a league to see everything.</p>'+dayMasterHTML(day)+
      '<div class="lg-tools"><input type="search" id="lg-q" placeholder="Search leagues or teams" aria-label="Search leagues or teams"><button type="button" data-lg-all="1">Expand all</button><button type="button" data-lg-all="0">Collapse all</button></div><div id="lg-list">'+
      rows.map(function(r,i){var x=r.x,id='lg'+i,o=!!open[x.league],P=x.picks.length,bk=bookedFor(x.picks.map(function(p){return p.eventId;})).length,sp=split(x.league);
        return '<section class="lg'+(o?' is-open':'')+'" data-lg="'+esc(x.league)+'" data-s="'+esc((x.league+' '+r.F.map(function(f){return f.match;}).join(' ')).toLowerCase())+'"><button type="button" class="lg-h" aria-expanded="'+o+'" aria-controls="'+id+'"><span class="lg-f" aria-hidden="true">'+flag(x.league)+'</span><span class="lg-n"><b>'+esc(sp[1])+'</b><small>'+esc(sp[0]||'')+(sp[0]?' · ':'')+'first KO '+esc(fko(r.F[0]))+'</small></span><span class="lg-m"><span class="lg-chip">'+r.F.length+' game'+(r.F.length>1?'s':'')+'</span>'+(P?'<span class="lg-chip p">'+P+' pick'+(P>1?'s':'')+'</span>':'')+(bk?'<span class="lg-chip b">✓ Booked</span>':'')+'</span><i class="lg-cv" aria-hidden="true"></i></button>'+
          '<div class="lg-b" id="'+id+'" role="region" aria-label="'+esc(x.league)+'"'+(o?'':' inert')+'><div>'+body(x,r.F)+'</div></div></section>';}).join('')+'</div><p class="lg-empty" id="lg-none" hidden>No league matches your search.</p>';
    $('lg-q').addEventListener('input',function(){var q=this.value.trim().toLowerCase(),n=0;host.querySelectorAll('.lg').forEach(function(s){var m=!q||s.getAttribute('data-s').indexOf(q)>=0;s.hidden=!m;if(m)n++;});$('lg-none').hidden=n>0;});
  }
  function setOpen(s,o){s.classList.toggle('is-open',o);s.querySelector('.lg-h').setAttribute('aria-expanded',o);var b=s.querySelector('.lg-b');if(o)b.removeAttribute('inert');else b.setAttribute('inert','');if(o)open[s.getAttribute('data-lg')]=1;else delete open[s.getAttribute('data-lg')];}
  document.addEventListener('click',function(e){if(!e.target.closest)return;var h=e.target.closest('.lg-h');if(h){var s=h.parentNode;setOpen(s,!s.classList.contains('is-open'));save();return;}
    var a=e.target.closest('[data-lg-all]');if(a){document.querySelectorAll('#lg-list .lg').forEach(function(s){if(!s.hidden)setOpen(s,a.getAttribute('data-lg-all')==='1');});save();return;}
    var d=e.target.closest('[data-lg-day]');if(d){day=d.getAttribute('data-lg-day');leagues();}});
  function init(d){data=d||{};
    var dd=$('hp-day');dd.innerHTML='<option>'+esc(d.date||'—')+'</option>';dd.disabled=true;
    $('hp-meta').textContent=d.DATA_UPDATED?'Updated '+new Date(d.DATA_UPDATED).toLocaleString('en-GB',{timeZone:ZONE,day:'numeric',month:'short',hour:'2-digit',minute:'2-digit'})+' GMT':'';
    codes();css();markets();render();leagues();if(window.P2UScores)P2UScores.refresh(data);}
  function missing(){init({date:'',picks:[],leagues:[]});$('hp-meta').textContent='Today’s picks are being prepared.';}
  fetch('home-picks.json',{cache:'no-cache'}).then(function(r){if(!r.ok)throw new Error(r.status);return r.json();}).then(init).catch(missing);
})();
