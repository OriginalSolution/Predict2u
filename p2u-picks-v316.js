/* Predict2U v316 — Risk-tier slips (Safe / Medium / High) above 25+ high-risk; booking-code carousel. */
(function(){
  'use strict';
  var $=function(id){return document.getElementById(id);};
  var esc=function(s){return String(s==null?'':s).replace(/[&<>"']/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c];});};
  var ZONE='Africa/Accra',GR={A:0,B:1,C:2};
  var BOOKS=[['sportybet','SportyBet','book-sportybet.webp','#e41827'],['msport','MSport','book-msport.webp','#ffd325'],['betika','Betika','book-betika.webp','#00a651'],['footballcom','football.com','book-footballcom.webp','#282450'],['betpawa','Betpawa','book-betpawa.webp','#78be20'],['onexbet','1xBet','book-1xbet.webp','#1f6fb2']];
  function chips(s){var c=s.codes||{};if(!c.sportybet&&s.code)c=Object.assign({sportybet:s.code},c);return '<div class="p2u-chips">'+BOOKS.filter(function(b){return c[b[0]];}).map(function(b){var k=b[0],l=(s.links||{})[k]||(k==='sportybet'?s.link:''),o=(s.bookOdds||{})[k]||(k==='sportybet'?s.totalOdds:null);return '<div class="p2u-chip p2u-chip-'+k+'"><img src="'+b[2]+'" alt="" width="24" height="24" loading="lazy"><span class="p2u-chip-t"><span class="p2u-chip-n">'+b[1]+'</span>'+(l?'<a class="p2u-chip-c" target="_blank" rel="noopener" href="'+esc(l)+'">'+esc(c[k])+'</a>':'<span class="p2u-chip-c">'+esc(c[k])+'</span>')+'<span class="p2u-chip-o">'+(o?'@'+Number(o).toFixed(2):'')+((s.bookPicks||{})[k]?' · '+s.bookPicks[k]+' picks':'')+'</span></span><button type="button" class="p2u-chip-cp" data-copy="'+esc(c[k])+'" aria-label="Copy '+b[1]+' code">Copy</button></div>';}).join('')+'</div>';}
  var data=null,state={day:null};
  function stamp(d){return new Intl.DateTimeFormat('en-CA',{timeZone:ZONE,year:'numeric',month:'2-digit',day:'2-digit'}).format(d);}
  function ko(iso){if(!iso)return '';var d=new Date(iso);if(isNaN(d))return '';return d.toLocaleTimeString('en-GB',{timeZone:ZONE,hour:'2-digit',minute:'2-digit'});}
  function badge(r){r=r||'pending';return '<span class="bp-res bp-'+esc(r)+'">'+esc(r.toUpperCase())+'</span>';}
  function grade(g){return '<span class="bp-grade bp-g'+esc(g)+'">'+esc(g)+'</span>';}
  function pct(c){return c==null?'—':Math.round(c*100)+'%';}
  var RISK={safe:0,medium:1,high:2}, RLAB={safe:['Safe','Low risk · 3–5 picks · odds ~2–5'],medium:['Medium','Balanced · 6–8 picks · odds ~8–15'],high:['High risk','25+ odds · longer slip']};
  function riskBadge(r){r=r||'high';var L=RLAB[r]||RLAB.high;return '<span class="bp-risk bp-risk-'+esc(r)+'" title="'+esc(L[1])+'">'+esc(L[0])+'</span>';}
  function slipLabel(s){
    if(s.risk==='safe') return 'Safe slip';
    if(s.risk==='medium') return 'Medium slip';
    if(s.banker || /main banker/i.test(s.name||'')) return 'Banker (high risk)';
    if(s.name && /Alternative|Steady|Earlier/i.test(s.name)) return s.name.replace(/^Main banker:\s*/i,'').replace(/\s*\(>=25\)/,'');
    return s.name || 'High-risk slip';
  }
  function daySlips(){
    var today=stamp(new Date());
    return data.slips.filter(function(s){
        if((s.dates||[s.date]).indexOf(state.day)>=0) return true;
        // Safe/Medium: show whenever the user is viewing today (legs may kick off tomorrow)
        if((s.risk==='safe'||s.risk==='medium') && s.house && state.day===today) return true;
        return false;
      })
      .sort(function(a,b){var ra=RISK.hasOwnProperty(a.risk)?RISK[a.risk]:3,rb=RISK.hasOwnProperty(b.risk)?RISK[b.risk]:3;return ra-rb||(GR[a.grade]-GR[b.grade])||(b.rating-a.rating);})
      .map(function(s,i){return Object.assign({},s,{label:slipLabel(s)});});
  }
  var OPEN_KEY='p2u_books_open_v1';
  function openState(){try{return JSON.parse(sessionStorage.getItem(OPEN_KEY))||null;}catch(e){return null;}}
  function saveOpen(id,on){var st=openState()||{};st[id]=on;try{sessionStorage.setItem(OPEN_KEY,JSON.stringify(st));}catch(e){}}
  function legsHtml(s){return '<ul class="bp-card-legs">'+s.legs.map(function(x){return '<li><span>'+esc(ko(x.kickoff))+' '+esc(x.match)+'</span><b>'+esc(x.selection)+' @'+(x.odds==null?'—':Number(x.odds).toFixed(2))+'</b> '+badge(x.result)+'</li>';}).join('')+'</ul>';}
  function carousel(slips){
    var st=openState(),first=true;
    return BOOKS.map(function(b){
      var cards=slips.filter(function(s){return s.codes&&s.codes[b[0]];});
      if(!cards.length)return '';
      var open=st&&st.hasOwnProperty(b[0])?!!st[b[0]]:false;first=false;
      var pid='bp-panel-'+b[0];
      return '<div class="bp-book bp-book-'+b[0]+(open?' is-open':'')+'" style="--brand:'+b[3]+'"><button type="button" class="bp-book-h" data-book="'+b[0]+'" aria-expanded="'+open+'" aria-controls="'+pid+'"><img class="bp-blogo" src="'+b[2]+'" alt="'+b[1]+' logo" width="28" height="28" loading="lazy" decoding="async"><span>'+b[1]+' codes</span><small>'+cards.length+'</small><i class="bp-chev" aria-hidden="true"></i></button>'+
        '<div class="bp-book-p" id="'+pid+'" role="region"><div class="bp-book-in"><div class="bp-car" tabindex="0">'+cards.map(function(s,i){
        var code=s.codes[b[0]],link=(s.links||{})[b[0]],lid='bp-legs-'+b[0]+'-'+i;
        return '<div class="bp-card bp-card-'+esc(s.risk||'high')+'">'+riskBadge(s.risk)+grade(s.grade)+'<div class="bp-card-l"><img class="bp-clogo" src="'+b[2]+'" alt="" width="16" height="16" loading="lazy" decoding="async">'+esc(s.label)+'</div><div class="bp-card-code">'+esc(code)+'</div>'+
          '<div class="bp-card-m">@'+Number((s.bookOdds||{})[b[0]]||s.totalOdds).toFixed(2)+' · '+((s.bookPicks||{})[b[0]]||s.picks)+' picks'+(s.house?' · P2U banker':'')+'</div>'+((s.bookNotes||{})[b[0]]?'<div class="bp-card-n">⚠ '+esc(s.bookNotes[b[0]])+'</div>':'')+
          '<div class="bp-card-a"><button type="button" data-copy="'+esc(code)+'">Copy</button>'+(link?'<a target="_blank" rel="noopener" href="'+esc(link)+'" class="bp-open" aria-label="Open on '+b[1]+'">Open ↗</a>':'')+(window.P2UWA?'<a class="bp-wa" target="_blank" rel="noopener" href="'+P2UWA.href(s)+'" aria-label="Share on WhatsApp">WhatsApp</a>':'')+'</div>'+
          '<button type="button" class="bp-card-x" data-legs aria-expanded="false" aria-controls="'+lid+'">Show '+s.picks+' picks <i class="bp-chev" aria-hidden="true"></i></button>'+
          '<div class="bp-card-lp" id="'+lid+'"><div class="bp-book-in">'+legsHtml(s)+'</div></div></div>';
      }).join('')+'</div></div></div></div>';
    }).join('');
  }
  document.addEventListener('click',function(e){
    var h=e.target.closest&&e.target.closest('.bp-book-h');
    if(h){var on=h.getAttribute('aria-expanded')!=='true';h.setAttribute('aria-expanded',on);h.parentNode.classList.toggle('is-open',on);saveOpen(h.getAttribute('data-book'),on);return;}
    var x=e.target.closest&&e.target.closest('[data-legs]');
    if(x){var o=x.getAttribute('aria-expanded')!=='true';x.setAttribute('aria-expanded',o);x.parentNode.classList.toggle('is-open',o);x.firstChild.nodeValue=(o?'Hide ':'Show ')+x.firstChild.nodeValue.replace(/^(Show|Hide) /,'');}
  });
  function render(){
    var slips=daySlips(),legs=0,w=0,l=0;
    slips.forEach(function(s){s.legs.forEach(function(x){if(x.date!==state.day)return;legs++;if(x.result==='won')w++;if(x.result==='lost')l++;});});
    var nS=slips.filter(function(s){return s.risk==='safe';}).length,nM=slips.filter(function(s){return s.risk==='medium';}).length,nH=slips.length-nS-nM;
    $('bp-summary').textContent=slips.length+' slips · '+nS+' safe · '+nM+' medium · '+nH+' high-risk · '+legs+' picks · '+w+' won · '+l+' lost';
    var leg=$('bp-risk-legend');if(!leg){leg=document.createElement('div');leg.id='bp-risk-legend';leg.className='bp-risk-legend';var car=$('bp-carousel');if(car&&car.parentNode)car.parentNode.insertBefore(leg,car);}
    leg.innerHTML='<span>'+riskBadge('safe')+' odds ~2–5</span><span>'+riskBadge('medium')+' odds ~8–15</span><span>'+riskBadge('high')+' odds 25+</span>';
    $('bp-carousel').innerHTML=carousel(slips);
    var list=$('bp-list');
    if(!slips.length){list.innerHTML='<div class="p2u-bankers-empty">No slips for this day yet.</div>';return;}
    list.innerHTML=slips.map(function(s,i){
      var st=s.legs.some(function(x){return x.result==='lost';})?'lost':(s.legs.every(function(x){return x.result==='won'||x.result==='void';})?'won':'pending');
      return '<details class="bp-slip bp-slip-'+esc(s.risk||'high')+'"'+((s.risk==='safe'||s.risk==='medium')?' open':'')+'><summary><header><div class="bp-hl">'+riskBadge(s.risk)+grade(s.grade)+' <b>'+esc(s.label)+'</b> <small>'+s.picks+' picks'+(s.strategy?' · '+esc(s.strategy):'')+'</small></div><div class="bp-hr"><b>@'+Number(s.totalOdds).toFixed(2)+'</b> '+badge(st)+'</div></header>'+chips(s)+(window.P2UWA?'<div class="p2u-wa-row">'+P2UWA.button(s,'p2u-wa')+'</div>':'')+'</summary><table class="bp-legs"><thead><tr><th>KO</th><th>Match</th><th>Pick</th><th>Odds</th><th>P2U score</th><th>Result</th></tr></thead><tbody>'+
        s.legs.map(function(x){return '<tr><td data-l="KO">'+esc(ko(x.kickoff))+'</td><td class="bp-m"><div>'+esc(x.match)+'</div><small>'+esc(x.league)+'</small></td><td class="bp-p"><div>'+esc(x.selection)+'</div><small>'+esc(x.market)+'</small></td><td data-l="Odds">'+(x.odds==null?'—':Number(x.odds).toFixed(2))+'</td><td data-l="P2U">'+pct(x.score)+'</td><td data-l="Result">'+badge(x.result)+'</td></tr>';}).join('')+
        '</tbody></table></details>';
    }).join('');
  }
  document.addEventListener('click',function(e){
    var b=e.target.closest&&e.target.closest('[data-copy]');if(!b)return;if(b.closest('summary'))e.preventDefault();
    var c=b.getAttribute('data-copy'),done=function(){b.textContent='Copied ✓';b.classList.add('is-ok');setTimeout(function(){b.textContent='Copy';b.classList.remove('is-ok');},1600);};
    if(navigator.clipboard&&navigator.clipboard.writeText)navigator.clipboard.writeText(c).then(done,done);else done();
  });
  function riskCss(){if($('bp-risk-css'))return;var st=document.createElement('style');st.id='bp-risk-css';st.textContent=
    '.bp-risk{display:inline-block;font-size:.68rem;font-weight:900;letter-spacing:.04em;text-transform:uppercase;padding:3px 8px;border-radius:999px;margin-right:6px;vertical-align:middle}'+
    '.bp-risk-safe{background:#0f3d2a;color:#7ff0b8;border:1px solid #1f7a4d}.bp-risk-medium{background:#3a2a12;color:#ffd99a;border:1px solid #7a5a20}.bp-risk-high{background:#3a1520;color:#ffb0c0;border:1px solid #8a3048}'+
    '.bp-slip-safe{border-color:#1f7a4d;box-shadow:0 0 0 1px rgba(127,240,184,.18)}.bp-slip-medium{border-color:#7a5a20;box-shadow:0 0 0 1px rgba(255,217,154,.15)}'+
    '.bp-card-safe{outline:1px solid rgba(127,240,184,.35)}.bp-card-medium{outline:1px solid rgba(255,217,154,.3)}'+
    '.bp-risk-legend{display:flex;flex-wrap:wrap;gap:8px;margin:8px 0 12px;font-size:.82rem;color:#c3d0e2}.bp-risk-legend span{display:inline-flex;align-items:center;gap:6px}';
    document.head.appendChild(st);}
  function init(d){
    riskCss(); if(window.P2UWA)P2UWA.css();
    data=d;var days=[];d.slips.forEach(function(s){(s.dates||[s.date]).forEach(function(x){if(days.indexOf(x)<0)days.push(x);});});days.sort();
    var t=stamp(new Date());state.day=days.indexOf(t)>=0?t:(days.filter(function(x){return x>=t;})[0]||days[days.length-1]);
    $('bp-day').innerHTML=days.map(function(x){return '<option value="'+x+'"'+(x===state.day?' selected':'')+'>'+x+(x===t?' (today)':'')+'</option>';}).join('');
    $('bp-day').onchange=function(){state.day=this.value;render();};
    var up=new Date(d.DATA_UPDATED);
    $('bankers-meta').textContent='Updated '+up.toLocaleString('en-GB',{timeZone:ZONE,day:'numeric',month:'short',hour:'2-digit',minute:'2-digit'})+' GMT';
    render();
  }
  fetch('picks.json',{cache:'no-cache'}).then(function(r){if(!r.ok)throw new Error(r.status);return r.json();}).then(init)
    .catch(function(e){$('bankers-meta').textContent='Could not load picks ('+e.message+').';});
})();
