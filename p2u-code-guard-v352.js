/* Predict2U v354 — hide bookmaker chips/sections with no real booking code.
   Data-driven: missing / placeholder / lock codes never render. */
(function(){
  'use strict';
  var BAD=/^(?:—|–|-|n\/?a|none|null|undefined|pending|not booked|unavailable|coming soon)?$/i;
  function extract(raw){
    if(raw==null)return '';
    if(typeof raw==='string'||typeof raw==='number')return String(raw).trim();
    if(typeof raw==='object'){
      if(Array.isArray(raw)){
        for(var i=0;i<raw.length;i++){var x=extract(raw[i]);if(x)return x;}
        return '';
      }
      return extract(raw.code||raw.sportybet||raw.msport||raw.betika||raw.footballcom||raw.betpawa||raw.betway||raw['1xbet']||raw.onexbet||'');
    }
    return '';
  }
  // codes the daily health check found dead (expired / no match left) — see dead-codes.json
  var DEAD={};
  function isReal(raw){
    var c=extract(raw);
    if(!c)return false;
    if(DEAD[c]||DEAD[c.toUpperCase()])return false;
    if(BAD.test(c))return false;
    if(/^P2ULOCK-/i.test(c))return false;
    if(/^TODO\b/i.test(c))return false;
    // booking codes are short alphanumerics (Betika can be mixed case)
    if(c.length<3||c.length>24)return false;
    if(!/^[A-Za-z0-9_-]+$/.test(c))return false;
    return true;
  }
  function parts(raw){
    if(raw==null)return [];
    var list=Array.isArray(raw)?raw:[raw];
    return list.filter(isReal).map(function(x){
      if(x&&typeof x==='object'&&!Array.isArray(x))return x;
      return {code:extract(x)};
    });
  }
  function hasBook(codes,book){
    if(!codes)return false;
    return parts(codes[book]).length>0;
  }
  function filterMap(codes){
    var out={},c=codes||{};
    Object.keys(c).forEach(function(k){
      var p=parts(c[k]);
      if(p.length)out[k]=Array.isArray(c[k])?p:(typeof c[k]==='object'&&c[k]&&c[k].code?Object.assign({},c[k],{code:extract(c[k])}):extract(c[k]));
    });
    return out;
  }
  function hide(el){if(!el||!el.style)return;el.hidden=true;el.setAttribute('hidden','');el.style.display='none';el.setAttribute('aria-hidden','true');}
  function sweep(root){
    root=root||document;
    // pending / unavailable chips
    root.querySelectorAll('.p2u-chip.is-pending,.bookchip.pending,.p2u-chip-unavailable').forEach(function(el){
      var chip=el.classList.contains('p2u-chip')||el.classList.contains('bookchip')?el:el.closest('.p2u-chip,.bookchip');
      hide(chip||el);
    });
    // chips whose code text is empty / dash / Not booked
    root.querySelectorAll('.p2u-chip,.bcod-chip,.bookchip,.cc-chip,.hp-bkd a,.lg-dm-chips a').forEach(function(el){
      var codeEl=el.querySelector('.p2u-chip-c,.cc-code,b,code')||el;
      var txt=(el.getAttribute('data-code')||codeEl.textContent||'').replace(/\s+/g,' ').trim();
      // strip bookmaker name prefix "SportyBet ABC" -> try last token
      var cand=txt;
      if(/\s/.test(cand)){var bits=cand.split(/\s+/);cand=bits[bits.length-1];}
      if(!isReal(cand)&&!isReal(txt))hide(el);
    });
    // carousel cards with em dash / empty code
    root.querySelectorAll('.cc-card').forEach(function(card){
      if(card.classList.contains('p2u-cc-lock')||card.querySelector('.p2u-lock,[data-p2u-premium-root]'))return;
      var code=(card.querySelector('.cc-code')||{}).textContent||'';
      if(!isReal(code))hide(card);
    });
    // empty chip rows / day-master blocks / bookmaker groups
    root.querySelectorAll('.p2u-chips,.lg-dm-chips,.bcod-chips,.hp-bkd,.bookchips').forEach(function(row){
      var kids=Array.prototype.filter.call(row.children,function(c){return !c.hidden&&c.style.display!=='none'&&c.getAttribute('aria-hidden')!=='true';});
      if(!kids.length)hide(row.closest('.lg-dm,.p2u-risk-card,.hot-slip,.bp-slip')&&row.classList.contains('lg-dm-chips')?row.closest('.lg-dm'):row);
      if(!kids.length&&row.classList.contains('lg-dm-chips')){var dm=row.closest('.lg-dm');if(dm)hide(dm);}
    });
    root.querySelectorAll('.bp-book').forEach(function(book){
      var cards=book.querySelectorAll('.bp-card');
      var live=Array.prototype.filter.call(cards,function(c){return !c.hidden&&c.style.display!=='none';});
      var emptyMsg=book.querySelector('.p2u-bankers-empty');
      if(!live.length)hide(book);
      else if(emptyMsg&&!book.querySelector('.bp-card:not([hidden])'))hide(book);
    });
    root.querySelectorAll('.lg-dm').forEach(function(dm){
      var chips=dm.querySelectorAll('.lg-dm-chips a, .lg-dm-chips .p2u-chip');
      var live=Array.prototype.filter.call(chips,function(c){return !c.hidden&&c.style.display!=='none';});
      if(!live.length)hide(dm);
    });
    root.querySelectorAll('details.hot-slip').forEach(function(d){
      if(d.classList.contains('hot-sec'))return; // section wrappers keep structure
      var chipRow=d.querySelector(':scope > .p2u-chips, :scope > summary + .p2u-chips');
      // only hide leaf slips that advertise codes but have none
      var chips=d.querySelectorAll('.p2u-chip');
      var live=Array.prototype.filter.call(chips,function(c){return !c.hidden&&c.style.display!=='none';});
      if(chipRow&&!live.length&&d.querySelector('.hot-mkt-code')==null){
        // keep market/team sections that still have pick lists
        if(!d.querySelector('.hot-list .hot-m'))hide(d);
      }
    });
  }
  var mo=null;
  function scrubPremium(root){
    if(isFree())return; // free-codes mode: nothing to hide
    (root||document).querySelectorAll('[data-p2u-premium-root]').forEach(function(box){
      if(box.querySelector('[data-p2u-unlocked]'))return;
      box.querySelectorAll('.p2u-chip,.cc-code,.bp-card-code,.bp-legs,.bp-card-legs,.p2u-risk-legs,.high-picks,.hot-list,.mk-pl,.bcod-main,.bcod-chips,.bcod-code,.lg-dm-chips,[data-copy],[data-cc-copy],[data-copy-code]').forEach(function(el){
        if(el.closest('.p2u-lock'))return;
        el.remove();
      });
      box.querySelectorAll('a[href]').forEach(function(a){
        if(a.closest('.p2u-lock'))return;
        var h=a.getAttribute('href')||'';
        if(/shareCode=|share-betslip|bookingCode=|\/share\//i.test(h))a.remove();
      });
    });
  }
  function arm(){
    sweep(document);
    scrubPremium(document);
    if(mo||typeof MutationObserver==='undefined')return;
    mo=new MutationObserver(function(muts){
      var need=false;
      for(var i=0;i<muts.length;i++){if(muts[i].addedNodes&&muts[i].addedNodes.length){need=true;break;}}
      if(need){clearTimeout(arm._t);arm._t=setTimeout(function(){sweep(document);scrubPremium(document);},40);}
    });
    try{mo.observe(document.documentElement,{childList:true,subtree:true});}catch(_){mo=null;}
  }
  var LIMIT=25;
  /* Free-codes switch lives in /p2u-free-mode.js (window.P2U_FREE_CODES). When on, no slip counts as premium. */
  function isFree(){return window.P2U_FREE_CODES===true;}
  function num(v){var n=Number(v);return isFinite(n)?n:null;}
  function oddsOf(s){
    if(!s)return null;
    if(s.locked&&typeof s.locked==='object'&&num(s.locked.odds)!=null)return num(s.locked.odds);
    var o=num(s.totalOdds);if(o!=null)return o;
    o=num(s.odds);return o;
  }
  function dayDigits(raw){var m=String(raw||'').match(/(\d{4})-(\d{2})-(\d{2})/);return m?m[1]+m[2]+m[3]:'';}
  function slipDay(s){
    var legs=s&&s.legs, ds=[], i, d;
    if(Array.isArray(legs)){for(i=0;i<legs.length;i++){var d=dayDigits(legs[i]&&(legs[i].date||legs[i].kickoff));if(d)ds.push(d);}}
    if(ds.length)return ds.sort()[0];
    d=dayDigits(s&&s.targetDate)||dayDigits(s&&s.date)||dayDigits(s&&s.bookedAt);
    if(d)return d;
    if(s&&Array.isArray(s.dates)){ds=[];for(i=0;i<s.dates.length;i++){d=dayDigits(s.dates[i]);if(d)ds.push(d);}if(ds.length)return ds.sort()[0];}
    try{return new Intl.DateTimeFormat('en-CA',{timeZone:'Africa/Accra',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date()).replace(/-/g,'');}catch(e){return '';}
  }
  function lockKind(s){
    var name=String((s&&(s.name||s.label))||'').toLowerCase();
    var risk=String((s&&s.risk)||'').toLowerCase();
    var origin=String((s&&s.origin)||'').toLowerCase();
    var strategy=String((s&&s.strategy)||'').toLowerCase();
    if((s&&(s.banker||s.verzzify||s.dailyMaster))||name.indexOf('main banker')===0||name.indexOf('main ·')===0||name.indexOf('code of the day')>=0||name.indexOf('verzzify')>=0||strategy.indexOf('verzzify')>=0||origin==='daily-master'||origin==='verzzify')return 'banker';
    if(risk==='medium'||name.indexOf('medium')===0)return 'medium';
    return 'hot';
  }
  function lockId(s){
    if(s&&s.locked&&typeof s.locked==='object'&&/^(banker|medium|hot)-\d{8}$/.test(s.locked.id||''))return s.locked.id;
    var d=slipDay(s);
    return d?lockKind(s)+'-'+d:'';
  }
  function legsOf(s){
    if(!s)return 0;
    if(s.locked&&typeof s.locked==='object'&&s.locked.legs!=null&&s.locked.legs!==''&&isFinite(Number(s.locked.legs)))return Number(s.locked.legs);
    if(typeof s.legCount==='number')return s.legCount;
    if(typeof s.legs==='number')return s.legs;
    if(typeof s.total==='number'&&s.total)return s.total;
    if(typeof s.picks==='number')return s.picks;
    if(Array.isArray(s.legs))return s.legs.length;
    if(Array.isArray(s.picks))return s.picks.length;
    return 0;
  }
  function isOdds(v){if(isFree())return false;var n=num(v);return n!=null&&n>LIMIT;}
  function isPremium(s){
    if(!s||isFree())return false;
    if(s.premium===true||s.premium==='true')return true;
    return isOdds(oddsOf(s));
  }
  function slipKey(s){
    var name=String((s&&(s.name||s.label))||'slip').toLowerCase().replace(/[^a-z0-9]+/g,'-').replace(/^-|-$/g,'').slice(0,40);
    var o=oddsOf(s);
    return name+'@'+(o==null?'':o.toFixed(2))+'x'+legsOf(s);
  }
  function escP(s){return String(s==null?'':s).replace(/[&<>"']/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c];});}
  function priceHtml(){return '$4.29 <span class="p2u-lock-fx">≈ GHS 50</span>';}
  function card(s){
    s=s||{};
    var id=lockId(s), o=oddsOf(s), n=legsOf(s);
    var title=s.name||s.label||'Premium booking code';
    var oddsTxt=o==null?'':('@'+Number(o).toLocaleString('en-GB',{maximumFractionDigits:2}));
    var fact=[oddsTxt, n+' legs'].filter(Boolean).join(' · ');
    var attrs=' data-p2u-lock="'+escP(id)+'" data-p2u-info="'+escP(id)+'" data-p2u-odds="'+escP(o==null?'':o)+'" data-p2u-legs="'+escP(n)+'" data-p2u-slip="'+escP(slipKey(s))+'" data-p2u-title="'+escP(title)+'"';
    return '<div class="p2u-lock" role="button" tabindex="0" aria-haspopup="dialog"'+attrs+'><b>🔒 '+escP(title)+'</b><p>'+escP(fact)+'. Unlock this booking code for '+priceHtml()+' (mobile money or card).</p><div class="p2u-lock-row"><button type="button" class="p2u-lock-btn" data-p2u-pay="'+escP(id)+'">Unlock for '+priceHtml()+'</button><button type="button" class="p2u-lock-r" data-p2u-restore="1">Already paid?</button></div></div>';
  }
  window.P2UPremium={LIMIT:LIMIT,free:isFree,is:isPremium,isOdds:isOdds,odds:oddsOf,legs:legsOf,id:lockId,key:slipKey,card:card,scrub:scrubPremium};
  window.P2UCode={isReal:isReal,extract:extract,parts:parts,hasBook:hasBook,filterMap:filterMap,sweep:sweep,arm:arm};
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',arm);else arm();
  try{
    if(window.fetch)fetch('/dead-codes.json?t='+Math.floor(Date.now()/600000),{cache:'no-cache'}).then(function(r){return r.ok?r.json():null;}).then(function(d){
      var c=(d&&d.codes)||{},n=0;
      Object.keys(c).forEach(function(k){var v=c[k]&&c[k].code;if(v){DEAD[String(v)]=1;DEAD[String(v).toUpperCase()]=1;n++;}});
      if(n&&document.body)sweep(document);
    }).catch(function(){});
  }catch(e){}
})();
/* Split parts (codes over 50 legs are split into parts of <= 50 per bookmaker). Empty bookmakers are hidden. */
(function(){if(typeof window==='undefined')return;var N={sportybet:'SportyBet',footballcom:'football.com',msport:'MSport',betika:'Betika',betpawa:'Betpawa'};
function e(s){return String(s==null?'':s).replace(/[&<>"']/g,function(c){return{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c];});}
function fo(x){return x==null?'':Number(x).toLocaleString('en-GB',{maximumFractionDigits:2});}
window.P2UParts={html:function(parts){if(!parts||!parts.length)return '';var h='<div class="p2u-parts" style="margin:10px 0;padding:10px;border:1px solid rgba(185,28,28,.5);border-radius:10px"><p style="margin:0 0 6px;font-weight:800;font-size:.82rem"><span style="background:#b91c1c;color:#fff;padding:2px 8px;border-radius:999px;font-size:.66rem;margin-right:6px">HIGH RISK</span>Split into '+parts.length+' parts (bookmakers take up to 50 picks per code)</p>';
parts.forEach(function(p,i){
if(window.P2UPremium&&P2UPremium.is(p)){h+='<div data-p2u-premium-root="1">'+P2UPremium.card(Object.assign({name:'Part '+(i+1)},p))+'</div>';return;}
var rows=Object.keys(N).map(function(b){return ((p.codes||{})[b]||[]).filter(function(c){return window.P2UCode?P2UCode.isReal(c&&c.code):!!(c&&c.code);}).map(function(c){return '<a class="p2u-chip p2u-chip-'+b+'" href="'+e(c.link)+'" target="_blank" rel="noopener" style="display:inline-flex;gap:6px;align-items:center;margin:3px;padding:5px 9px;border-radius:8px;text-decoration:none"><img src="/book-'+b+'.webp" alt="" width="18" height="18"><b>'+N[b]+' '+e(c.code)+'</b><small>@'+fo(c.totalOdds)+' · '+e(c.legs)+'p</small></a>';}).join('');}).join('');
if(rows)h+='<div style="margin:6px 0"><p style="margin:2px 0;font-size:.78rem;opacity:.85">Part '+(i+1)+' · '+e(p.legs)+' picks · @'+fo(p.totalOdds)+'</p>'+rows+'</div>';});return h+'</div>';}};})();
