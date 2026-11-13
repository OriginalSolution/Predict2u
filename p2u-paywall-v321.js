/* Predict2U v321 — pay-per-code unlock. Premium slip codes are never in the public files; the page shows a locked box,
   payment runs on Paystack (GHS, mobile money + card) and the relay returns the codes. Unlocks are remembered on this device. */
(function(){
  'use strict';
  var RELAY='https://p2u-relay-c0mn.onrender.com', RX=/P2ULOCK-([a-z]+-\d{8})-[a-z]+\d*/i, KEY='p2u-unlocks-v1';
  var BOOKS=[['sportybet','SportyBet','book-sportybet.webp','https://www.sportybet.com/gh/?shareCode='],['msport','MSport','book-msport.webp','https://www.msport.com/gh/?shareCode='],
    ['betika','Betika','book-betika.webp','https://betika.com/en-gh/share/'],['footballcom','football.com','book-footballcom.webp','https://www.football.com/gh/?shareCode='],['betpawa','Betpawa','book-betpawa.webp','https://www.betpawa.com.gh/share-betslip/']];
  var TITLE={banker:'Main Banker',medium:'Medium slip',hot:'Hot Picks main'};
  /* Display in USD; Paystack still charges GHS 50 (≈ $4.29 at 0.085815 USD/GHS on 2026-11-05). */
  var DISP_USD='4.29', DISP_NOTE='≈ GHS 50';
  var cfg=null, cfgP=null, got={};
  function esc(s){return String(s==null?'':s).replace(/[&<>"']/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c];});}
  function priceTxt(){return '$'+DISP_USD;}
  function priceHtml(){return '$'+DISP_USD+' <span class="p2u-lock-fx">'+DISP_NOTE+'</span>';}
  function store(){try{return JSON.parse(localStorage.getItem(KEY)||'{}')}catch(e){return {}}}
  function save(g){var s=store();s[g.id]={token:g.token,t:Date.now()};try{localStorage.setItem(KEY,JSON.stringify(s))}catch(e){} got[g.id]=g;}
  function device(){try{var d=localStorage.getItem('p2u-device');if(!d){d=Math.random().toString(36).slice(2)+Date.now().toString(36);localStorage.setItem('p2u-device',d)}return d}catch(e){return ''}}
  function post(p,b){return fetch(RELAY+p,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(b||{})}).then(function(r){return r.json().then(function(j){if(!r.ok)throw new Error(j.error||r.status);return j;});});}
  function config(){if(!cfgP)cfgP=fetch(RELAY+'/pay/config',{cache:'no-store'}).then(function(r){return r.json()}).then(function(j){cfg=j;return j}).catch(function(){cfg={enabled:false,locked:{}};return cfg});return cfgP;}
  function css(){if(document.getElementById('p2u-pw-css'))return;var s=document.createElement('style');s.id='p2u-pw-css';s.textContent=
    '.p2u-lock{border:1px dashed #c9a227;background:linear-gradient(160deg,#1d1a0c,#0d1320);border-radius:14px;padding:12px 14px;margin:8px 0;color:#f4ecd0;text-align:left}'+
    '.p2u-lock b{display:block;font-size:1rem;color:#ffe08a}.p2u-lock p{margin:4px 0 10px;font-size:.84rem;color:#d9d2b8}'+
    '.p2u-lock-fx{display:inline;font-size:.78em;font-weight:600;color:#b9c8dc;margin-left:4px}'+
    '.p2u-lock-btn{display:inline-flex;align-items:center;justify-content:center;min-height:44px;padding:0 18px;border-radius:999px;border:0;background:#ffcc33;color:#1a1400;font-weight:900;font-size:.95rem;cursor:pointer}'+
    '.p2u-lock-btn[disabled]{background:#4a4a4a;color:#e8e8e8;cursor:default}.p2u-lock-r{background:none;border:0;color:#a9c9ff;text-decoration:underline;font-size:.8rem;margin-left:10px;cursor:pointer;min-height:44px}'+
    '.p2u-lock-m{position:fixed;inset:0;background:rgba(0,0,0,.7);z-index:99999;display:flex;align-items:center;justify-content:center;padding:16px}'+
    '.p2u-lock-m>div{background:#0f1a2a;border:1px solid #c9a227;border-radius:16px;padding:18px;max-width:380px;width:100%;color:#fff}.p2u-lock-m input{width:100%;box-sizing:border-box;min-height:44px;border-radius:10px;border:1px solid #3a4a63;background:#0a111c;color:#fff;padding:0 12px;font-size:1rem;margin:8px 0 12px}'+
    '.p2u-lock-m small{color:#b9c8dc;display:block;margin-top:10px}.p2u-lock-x{float:right;background:none;border:0;color:#fff;font-size:1.4rem;cursor:pointer}.p2u-lock-err{color:#ffb0c0;font-size:.85rem}';
    document.head.appendChild(s);}
  function chips(g){var c=g.codes||{};return '<div class="p2u-chips" data-p2u-unlocked="'+esc(g.id)+'">'+BOOKS.filter(function(b){return c[b[0]]&&c[b[0]].length;}).map(function(b){return c[b[0]].map(function(x){
    var href=b[3]+encodeURIComponent(x.code);
    return '<div class="p2u-chip p2u-chip-'+b[0]+'"><img src="'+b[2]+'" alt="" width="24" height="24" loading="lazy"><span class="p2u-chip-t"><span class="p2u-chip-n">'+b[1]+'</span><a class="p2u-chip-c" target="_blank" rel="noopener" href="'+href+'">'+esc(x.code)+'</a><span class="p2u-chip-o">'+(x.totalOdds?'@'+Number(x.totalOdds).toFixed(2):'')+(x.legs?' · '+x.legs+' picks':'')+'</span></span><button type="button" class="p2u-chip-cp" data-copy="'+esc(x.code)+'">Copy</button></div>';}).join('');}).join('')+'</div>';}
  function box(id){var k=id.split('-')[0],m=(cfg&&cfg.locked&&cfg.locked[id])||{},on=cfg&&cfg.enabled,pl=priceHtml();
    if(got[id]&&got[id].codes)return chips(got[id]);
    return '<div class="p2u-lock" data-p2u-lock="'+esc(id)+'"><b>🔒 '+esc(m.title||TITLE[k]||'Premium slip')+' codes are locked</b><p>See the picks and odds free. Unlock the booking codes for every bookmaker for '+pl+' (mobile money or card).</p>'+
      (cfg?(on?'<button type="button" class="p2u-lock-btn" data-p2u-pay="'+esc(id)+'">Unlock for '+pl+'</button><button type="button" class="p2u-lock-r" data-p2u-restore="1">Already paid?</button>':'<button type="button" class="p2u-lock-btn" disabled>Unlock for '+pl+' · Coming soon</button>'):'<button type="button" class="p2u-lock-btn" disabled>Unlock for '+pl+'</button>')+'</div>';}
  var SEL='.p2u-chips,.bcod-main,.bcod-chips,.bcod-act,.bcod-also,.cc-card,.hp-bkd a,.p2u-chip,a,button';
  function scan(){
    var hits=[];
    var w=document.createTreeWalker(document.body,NodeFilter.SHOW_TEXT,null),n;while((n=w.nextNode())){if(RX.test(n.nodeValue))hits.push(n.parentElement);}
    document.querySelectorAll('[href*="P2ULOCK-" i],[data-copy*="P2ULOCK-" i],[data-cc-copy*="P2ULOCK-" i],[data-p2u-share*="P2ULOCK-" i],[data-cx*="P2ULOCK-" i]').forEach(function(e){hits.push(e);});
    if(!hits.length)return;css();
    hits.forEach(function(el){if(!el||!el.isConnected||el.closest('.p2u-lock'))return;
      var m=(el.textContent+' '+(el.getAttribute('href')||'')+' '+(el.getAttribute('data-copy')||'')+(el.getAttribute('data-cc-copy')||'')+(el.getAttribute('data-p2u-share')||'')+(el.getAttribute('data-cx')||'')).match(RX);if(!m)return;var id=m[1].toLowerCase();
      if(el.closest('summary,.nh-code')&&!el.closest('.p2u-chips')){[].forEach.call(el.childNodes,function(t){if(t.nodeType===3)t.nodeValue=t.nodeValue.replace(new RegExp(RX.source,'gi'),'🔒 Premium code');});['href','data-copy','data-cc-copy'].forEach(function(a){if(RX.test(el.getAttribute(a)||''))el.removeAttribute(a);});return;}
      var cc=el.closest('.cc-card');if(cc){var tr=cc.parentNode;if(tr&&tr.querySelector('[data-p2u-lock="'+id+'"],[data-p2u-unlocked="'+id+'"]')){cc.remove();return;}var d0=document.createElement('div');d0.className='cc-card p2u-cc-lock';d0.innerHTML=box(id);tr.replaceChild(d0,cc);return;}
      var c=el.closest('.p2u-chips,.bcod-main')||el.closest('.bcod-chips,.bcod-act,.bcod-also,.hp-bkd a')||el.closest('.p2u-chip')||el;
      if(c.classList.contains('p2u-dl')||c.classList.contains('bcod-copy')||c.classList.contains('bcod-open')||/bcod-(chips|act|also)/.test(c.className)||c.matches('.hp-bkd a')||c.closest('.p2u-wa-row')){c.remove();return;}
      var par=c.parentNode;if(!par)return;
      if(par.querySelector(':scope > [data-p2u-lock="'+id+'"],:scope > [data-p2u-unlocked="'+id+'"]')){c.remove();return;}
      var t=document.createElement('div');t.innerHTML=box(id);var nb=t.firstChild;par.replaceChild(nb,c);
    });
    document.querySelectorAll('.p2u-wa[href]').forEach(function(a){try{var t=decodeURIComponent(a.getAttribute('href'));if(RX.test(t))a.setAttribute('href',a.getAttribute('href'))}catch(e){}});
  }
  function refresh(){document.querySelectorAll('[data-p2u-lock]').forEach(function(e){var t=document.createElement('div');t.innerHTML=box(e.getAttribute('data-p2u-lock'));e.parentNode.replaceChild(t.firstChild,e);});}
  function modal(html){var m=document.createElement('div');m.className='p2u-lock-m';m.innerHTML='<div role="dialog" aria-modal="true"><button class="p2u-lock-x" aria-label="Close">&times;</button>'+html+'</div>';document.body.appendChild(m);
    m.addEventListener('click',function(e){if(e.target===m||e.target.classList.contains('p2u-lock-x'))m.remove();});return m;}
  function loadPop(){return new Promise(function(ok,no){if(window.PaystackPop)return ok();var s=document.createElement('script');s.src='https://js.paystack.co/v2/inline.js';s.onload=ok;s.onerror=no;document.head.appendChild(s);});}
  function verify(ref,id){return post('/pay/verify',{reference:ref,id:id}).then(function(g){save(g);refresh();return g;});}
  function pay(id){var m=cfg.locked[id]||{},pl=priceHtml(),pt=priceTxt();
    var md=modal('<b>Unlock '+esc(m.title||'slip')+' · '+pl+'</b><label style="display:block;margin-top:10px">Email for your receipt<input type="email" autocomplete="email" placeholder="you@example.com"></label><button class="p2u-lock-btn" style="width:100%">Pay '+pt+'</button><div class="p2u-lock-err"></div><small>Charged as GHS 50 via Paystack (mobile money or card). Codes show right after payment and stay unlocked on this device. 18+ only.</small>');
    var inp=md.querySelector('input'),btn=md.querySelector('.p2u-lock-btn'),err=md.querySelector('.p2u-lock-err');
    try{inp.value=localStorage.getItem('p2u-email')||''}catch(e){}
    btn.onclick=function(){var em=inp.value.trim();if(!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(em)){err.textContent='Enter a valid email.';return;}
      try{localStorage.setItem('p2u-email',em)}catch(e){}btn.disabled=true;btn.textContent='Opening payment…';
      post('/pay/init',{id:id,email:em,device:device(),back:location.href}).then(function(r){return loadPop().then(function(){md.remove();
        var p=new window.PaystackPop();p.resumeTransaction(r.access_code,{onSuccess:function(tx){verify(tx.reference||r.reference,id).catch(function(){alert('Payment received. If the codes do not show, tap "Already paid?" and enter your email.');});},onCancel:function(){}});
      }).catch(function(){location.href=r.authorization_url;});}).catch(function(e){btn.disabled=false;btn.textContent='Pay '+pt;err.textContent='Could not start payment: '+e.message;});};
  }
  function restore(){var md=modal('<b>Restore your unlocked codes</b><label style="display:block;margin-top:10px">Email you paid with<input type="email" autocomplete="email"></label><button class="p2u-lock-btn" style="width:100%">Restore</button><div class="p2u-lock-err"></div>');
    var inp=md.querySelector('input'),btn=md.querySelector('.p2u-lock-btn'),err=md.querySelector('.p2u-lock-err');try{inp.value=localStorage.getItem('p2u-email')||''}catch(e){}
    btn.onclick=function(){btn.disabled=true;post('/pay/restore',{email:inp.value.trim()}).then(function(r){(r.unlocks||[]).forEach(save);refresh();if((r.unlocks||[]).length)md.remove();else{err.textContent='No paid codes found for that email.';btn.disabled=false;}}).catch(function(e){err.textContent=e.message;btn.disabled=false;});};}
  document.addEventListener('click',function(e){var a=e.target.closest('[data-p2u-pay]');if(a){e.preventDefault();if(cfg&&cfg.enabled)pay(a.getAttribute('data-p2u-pay'));return;}
    if(e.target.closest('[data-p2u-restore]')){e.preventDefault();restore();return;}
    var c=e.target.closest('[data-p2u-unlocked] .p2u-chip-cp');if(c){try{navigator.clipboard.writeText(c.getAttribute('data-copy'));c.textContent='Copied';}catch(_){}}});
  function boot(){scan();new MutationObserver(function(){scan();}).observe(document.body,{childList:true,subtree:true});
    config().then(function(){var s=store();var ids=Object.keys(s);
      var q=new URLSearchParams(location.search),ref=q.get('reference')||q.get('trxref'),sid=q.get('p2uslip');
      var jobs=ids.map(function(id){return post('/unlock',{token:s[id].token}).then(function(g){got[id]=g;}).catch(function(){});});
      if(ref&&sid&&cfg.enabled)jobs.push(verify(ref,sid).catch(function(){}));
      return Promise.all(jobs);}).then(refresh);}
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot);else boot();
})();
