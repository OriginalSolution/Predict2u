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
  function isReal(raw){
    var c=extract(raw);
    if(!c)return false;
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
  function arm(){
    sweep(document);
    if(mo||typeof MutationObserver==='undefined')return;
    mo=new MutationObserver(function(muts){
      var need=false;
      for(var i=0;i<muts.length;i++){if(muts[i].addedNodes&&muts[i].addedNodes.length){need=true;break;}}
      if(need){clearTimeout(arm._t);arm._t=setTimeout(function(){sweep(document);},40);}
    });
    try{mo.observe(document.documentElement,{childList:true,subtree:true});}catch(_){mo=null;}
  }
  window.P2UCode={isReal:isReal,extract:extract,parts:parts,hasBook:hasBook,filterMap:filterMap,sweep:sweep,arm:arm};
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',arm);else arm();
})();
/* Split parts (codes over 50 legs are split into parts of <= 50 per bookmaker). Empty bookmakers are hidden. */
(function(){if(typeof window==='undefined')return;var N={sportybet:'SportyBet',footballcom:'football.com',msport:'MSport',betika:'Betika',betpawa:'Betpawa'};
function e(s){return String(s==null?'':s).replace(/[&<>"']/g,function(c){return{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c];});}
function fo(x){return x==null?'':Number(x).toLocaleString('en-GB',{maximumFractionDigits:2});}
window.P2UParts={html:function(parts){if(!parts||!parts.length)return '';var h='<div class="p2u-parts" style="margin:10px 0;padding:10px;border:1px solid rgba(185,28,28,.5);border-radius:10px"><p style="margin:0 0 6px;font-weight:800;font-size:.82rem"><span style="background:#b91c1c;color:#fff;padding:2px 8px;border-radius:999px;font-size:.66rem;margin-right:6px">HIGH RISK</span>Split into '+parts.length+' parts (bookmakers take up to 50 picks per code)</p>';
parts.forEach(function(p,i){var rows=Object.keys(N).map(function(b){return ((p.codes||{})[b]||[]).filter(function(c){return window.P2UCode?P2UCode.isReal(c&&c.code):!!(c&&c.code);}).map(function(c){return '<a class="p2u-chip p2u-chip-'+b+'" href="'+e(c.link)+'" target="_blank" rel="noopener" style="display:inline-flex;gap:6px;align-items:center;margin:3px;padding:5px 9px;border-radius:8px;text-decoration:none"><img src="/book-'+b+'.webp" alt="" width="18" height="18"><b>'+N[b]+' '+e(c.code)+'</b><small>@'+fo(c.totalOdds)+' · '+e(c.legs)+'p</small></a>';}).join('');}).join('');
if(rows)h+='<div style="margin:6px 0"><p style="margin:2px 0;font-size:.78rem;opacity:.85">Part '+(i+1)+' · '+e(p.legs)+' picks · @'+fo(p.totalOdds)+'</p>'+rows+'</div>';});return h+'</div>';}};})();
