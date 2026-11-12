/* Predict2U v324 — pay-per-code unlock. Premium slip codes are never in the public files; the page shows a locked box,
   payment runs on Paystack (GHS, mobile money + card) and the relay returns the codes. Unlocks are remembered on this device. */
(function(){
  'use strict';
  var RELAY='https://p2u-relay.onrender.com', RX=/P2ULOCK-([a-z]+-\d{8})-[a-z]+\d*/i, KEY='p2u-unlocks-v1';
  var BOOKS=[['sportybet','SportyBet','book-sportybet.webp','https://www.sportybet.com/gh/?shareCode='],['msport','MSport','book-msport.webp','https://www.msport.com/gh/?shareCode='],
    ['betika','Betika','book-betika.webp','https://betika.com/en-gh/share/'],['footballcom','football.com','book-footballcom.webp','https://www.football.com/gh/?shareCode='],['betpawa','Betpawa','book-betpawa.webp','https://www.betpawa.com.gh/share-betslip/'],['betway','Betway','book-betway.webp','https://www.betway.com.gh/sport/soccer?bookingCode=']];
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
    '.p2u-lock{border:1.5px dashed #e0b83a;background:linear-gradient(160deg,#2a240e,#111a2b);border-radius:14px;padding:clamp(10px,3vw,16px);margin:8px 0;color:#fff7dc;text-align:left;cursor:pointer;max-width:100%;box-sizing:border-box;overflow-wrap:anywhere;word-break:normal;line-height:1.4}'+
    '.p2u-lock:focus-visible{outline:3px solid #ffd54a;outline-offset:2px}'+
    '.p2u-lock b{display:block;font-size:clamp(.95rem,3.6vw,1.1rem);font-weight:800;color:#ffd54a;letter-spacing:.01em}.p2u-lock p{margin:6px 0 10px;font-size:clamp(.85rem,3.2vw,.95rem);color:#f1ead2}'+
    '.p2u-lock-fx{display:inline-block;font-size:.85em;font-weight:700;color:#d6e2f2;margin-left:4px;white-space:nowrap}'+
    '.p2u-lock-row{display:flex;flex-wrap:wrap;gap:6px 10px;align-items:center}'+
    '.p2u-lock-btn{display:inline-flex;align-items:center;justify-content:center;flex-wrap:wrap;gap:4px;min-height:44px;max-width:100%;padding:8px 18px;border-radius:999px;border:0;background:#ffcc33;color:#1a1400;font-weight:900;font-size:clamp(.88rem,3.4vw,1rem);line-height:1.2;text-align:center;white-space:normal;cursor:pointer;box-sizing:border-box}'+
    '.p2u-lock-btn .p2u-lock-fx{color:#3a2e00}.p2u-lock-btn[disabled]{background:#5a5a5a;color:#fff;cursor:not-allowed}.p2u-lock-btn[disabled] .p2u-lock-fx{color:#e6e6e6}'+
    '.p2u-lock-r{background:none;border:0;color:#bcd6ff;text-decoration:underline;font-size:clamp(.8rem,3vw,.9rem);cursor:pointer;min-height:44px;padding:0 4px}'+
    '.p2u-lock-m{position:fixed;inset:0;background:rgba(0,0,0,.78);z-index:99999;display:flex;align-items:center;justify-content:center;padding:max(12px,env(safe-area-inset-top)) 12px max(12px,env(safe-area-inset-bottom));box-sizing:border-box}'+
    '.p2u-lock-m>div{position:relative;background:#0f1a2a;border:1.5px solid #e0b83a;border-radius:16px;padding:clamp(16px,4.5vw,24px);padding-top:clamp(18px,5vw,26px);max-width:420px;width:100%;max-height:calc(100dvh - 24px);overflow:auto;box-sizing:border-box;color:#fff;overflow-wrap:anywhere;line-height:1.45;font-size:clamp(.88rem,3.4vw,1rem);box-shadow:0 12px 40px rgba(0,0,0,.6)}'+
    '.p2u-lock-m h2{margin:0 36px 6px 0;font-size:clamp(1.05rem,4.6vw,1.3rem);color:#ffd54a;line-height:1.25}.p2u-lock-m b{color:#ffd54a;display:block;margin-right:36px;font-size:clamp(1rem,4.2vw,1.15rem)}'+
    '.p2u-lock-pr{font-size:clamp(1.4rem,7vw,1.9rem);font-weight:900;color:#fff;margin:6px 0 4px}.p2u-lock-pr .p2u-lock-fx{font-size:.55em}'+
    '.p2u-lock-m ul{margin:8px 0 14px;padding-left:1.2em;color:#e8eef7}.p2u-lock-m li{margin:3px 0}'+
    '.p2u-lock-m input{width:100%;box-sizing:border-box;min-height:44px;border-radius:10px;border:1px solid #4a5e7d;background:#0a111c;color:#fff;padding:0 12px;font-size:1rem;margin:8px 0 12px}'+
    '.p2u-lock-m small{color:#c9d6e8;display:block;margin-top:10px;font-size:clamp(.78rem,3vw,.88rem)}.p2u-lock-x{position:absolute;top:8px;right:8px;width:44px;height:44px;background:none;border:0;color:#fff;font-size:1.6rem;line-height:1;cursor:pointer;border-radius:50%}.p2u-lock-x:focus-visible,.p2u-lock-m button:focus-visible{outline:3px solid #ffd54a;outline-offset:2px}.p2u-lock-err{color:#ffc0cc;font-size:.9rem}'+
    '.p2u-lock-soon{display:block;text-align:center;margin-top:8px;color:#ffd54a;font-weight:700}'+
    '.p2u-lock-picks{list-style:none;margin:8px 0 0;padding:0}.p2u-lock-picks li{display:flex;flex-wrap:wrap;justify-content:space-between;gap:4px 10px;padding:6px 0;border-top:1px dashed rgba(224,184,58,.35);font-size:.86rem;color:#fff7dc}.p2u-lock-picks small{color:#d6e2f2}';
    document.head.appendChild(s);}
  function codeList(g,book,slipKey){
    var L=(g.codes||{})[book]||[];
    if(!Array.isArray(L))L=L?[{code:L}]:[];
    if(!slipKey)return L;
    var hit=L.filter(function(x){return x&&x.slipKey===slipKey;});
    return hit.length?hit:L;
  }
  function pickList(rows){
    var seen={},items=[];
    rows.forEach(function(x){(x.picks||[]).forEach(function(p){
      if(!p||!p.match)return;
      var k=p.match+'|'+p.selection;
      if(seen[k])return;seen[k]=1;
      items.push('<li><span>'+esc(p.match)+(p.league?' <small>'+esc(p.league)+'</small>':'')+'</span><b>'+esc(p.selection)+(p.odds?' @'+Number(p.odds).toFixed(2):'')+'</b></li>');
    });});
    return items.length?'<ul class="p2u-lock-picks">'+items.join('')+'</ul>':'';
  }
  function chips(g,slipKey){var c=g.codes||{},rows=[];return '<div class="p2u-chips" data-p2u-unlocked="'+esc(g.id)+'">'+BOOKS.filter(function(b){return codeList(g,b[0],slipKey).length;}).map(function(b){return codeList(g,b[0],slipKey).map(function(x){
    rows.push(x);
    var href=b[3]+encodeURIComponent(x.code);
    return '<div class="p2u-chip p2u-chip-'+b[0]+'"><img src="'+b[2]+'" alt="" width="24" height="24" loading="lazy"><span class="p2u-chip-t"><span class="p2u-chip-n">'+b[1]+'</span><a class="p2u-chip-c" target="_blank" rel="noopener" href="'+href+'">'+esc(x.code)+'</a><span class="p2u-chip-o">'+(x.totalOdds?'@'+Number(x.totalOdds).toFixed(2):'')+(x.legs?' · '+x.legs+' picks':'')+'</span></span><button type="button" class="p2u-chip-cp" data-copy="'+esc(x.code)+'">Copy</button></div>';}).join('');}).join('')+pickList(rows)+'</div>';}
  function metaOf(el){if(!el||!el.getAttribute)return {};return {odds:el.getAttribute('data-p2u-odds'),legs:el.getAttribute('data-p2u-legs'),slip:el.getAttribute('data-p2u-slip'),title:el.getAttribute('data-p2u-title')};}
  function lockAttrs(id,meta){return ' data-p2u-lock="'+esc(id)+'" data-p2u-info="'+esc(id)+'"'+(meta.odds!=null&&meta.odds!==''?' data-p2u-odds="'+esc(meta.odds)+'"':'')+(meta.legs!=null&&meta.legs!==''?' data-p2u-legs="'+esc(meta.legs)+'"':'')+(meta.slip?' data-p2u-slip="'+esc(meta.slip)+'"':'')+(meta.title?' data-p2u-title="'+esc(meta.title)+'"':'');}
  function box(id,el){var k=id.split('-')[0],m=(cfg&&cfg.locked&&cfg.locked[id])||{},on=cfg&&cfg.enabled,pl=priceHtml(),meta=metaOf(el);
    if(got[id]&&got[id].codes)return chips(got[id], meta.slip);
    var premium=meta.odds!=null&&meta.odds!=='';
    var oddsN=premium?Number(meta.odds):NaN;
    var fact=premium?((isFinite(oddsN)?'@'+oddsN.toLocaleString('en-GB',{maximumFractionDigits:2}):'')+(meta.legs!=null&&meta.legs!==''?' · '+esc(meta.legs)+' legs':'')):'';
    var title=meta.title||m.title||TITLE[k]||'Premium slip';
    var blurb=premium?(esc(fact)+'. Unlock this booking code for '+pl+' (mobile money or card). The code and the picks stay hidden until then.'):('See the picks and odds free. Unlock the booking codes for every bookmaker for '+pl+' (mobile money or card).');
    return '<div class="p2u-lock" role="button" tabindex="0" aria-haspopup="dialog"'+lockAttrs(id,meta)+'><b>🔒 '+esc(title)+(premium?'':' codes are locked')+'</b><p>'+blurb+'</p><div class="p2u-lock-row">'+
      (cfg&&on?'<button type="button" class="p2u-lock-btn" data-p2u-pay="'+esc(id)+'">Unlock for '+pl+'</button><button type="button" class="p2u-lock-r" data-p2u-restore="1">Already paid?</button>':'<button type="button" class="p2u-lock-btn" data-p2u-info="'+esc(id)+'">Unlock for '+pl+(cfg?' · Coming soon':'')+'</button>')+'</div></div>';}
  function info(id,el){var k=id.split('-')[0],m=(cfg&&cfg.locked&&cfg.locked[id])||{},on=cfg&&cfg.enabled,meta=metaOf(el),t=meta.title||m.title||TITLE[k]||'Premium slip';
    var facts='';
    if(meta.odds){var oddsN=Number(meta.odds);facts='<p style="margin:4px 0">Total odds <b>'+(isFinite(oddsN)?'@'+oddsN.toLocaleString('en-GB',{maximumFractionDigits:2}):esc(meta.odds))+'</b>'+(meta.legs?' · '+esc(meta.legs)+' legs':'')+'. The booking code and the picks stay locked until you pay.</p>';}
    var md=modal('<h2 id="p2u-lock-h">🔒 '+esc(t)+'</h2><div class="p2u-lock-pr">'+priceHtml()+'</div>'+facts+'<p style="margin:4px 0">One-time unlock. You get:</p><ul><li>Booking codes for SportyBet, MSport, Betika, football.com and Betpawa</li><li>The picks on this slip</li><li>One-tap open and copy for each code</li><li>Stays unlocked on this device</li></ul>'+
      (on?'<button type="button" class="p2u-lock-btn" style="width:100%" data-p2u-go="1">Unlock for '+priceTxt()+'</button><button type="button" class="p2u-lock-r" data-p2u-restore="1">Already paid?</button>':'<button type="button" class="p2u-lock-btn" style="width:100%" disabled>Pay '+priceTxt()+' · Coming soon</button><span class="p2u-lock-soon">Payments open very soon. The free picks and odds are still above.</span>')+
      '<small>Charged as GHS 50 via Paystack (mobile money or card). 18+ only. Gamble responsibly.</small>');
    var g=md.querySelector('[data-p2u-go]');if(g)g.onclick=function(){md.p2uClose();pay(id);};}
  var SEL='.p2u-chips,.bcod-main,.bcod-chips,.bcod-act,.bcod-also,.cc-card,.hp-bkd a,.p2u-chip,a,button';
  function scan(){
    var hits=[];
    var w=document.createTreeWalker(document.body,NodeFilter.SHOW_TEXT,null),n;while((n=w.nextNode())){if(RX.test(n.nodeValue))hits.push(n.parentElement);}
    document.querySelectorAll('[href*="P2ULOCK-" i],[data-copy*="P2ULOCK-" i],[data-cc-copy*="P2ULOCK-" i],[data-p2u-share*="P2ULOCK-" i],[data-cx*="P2ULOCK-" i]').forEach(function(e){hits.push(e);});
    if(!hits.length)return;css();
    hits.forEach(function(el){if(!el||!el.isConnected||el.closest('.p2u-lock'))return;
      var m=(el.textContent+' '+(el.getAttribute('href')||'')+' '+(el.getAttribute('data-copy')||'')+(el.getAttribute('data-cc-copy')||'')+(el.getAttribute('data-p2u-share')||'')+(el.getAttribute('data-cx')||'')).match(RX);if(!m)return;var id=m[1].toLowerCase();
      if(el.closest('summary,.nh-code')&&!el.closest('.p2u-chips')){[].forEach.call(el.childNodes,function(t){if(t.nodeType===3)t.nodeValue=t.nodeValue.replace(new RegExp(RX.source,'gi'),'🔒 Premium code');});['href','data-copy','data-cc-copy'].forEach(function(a){if(RX.test(el.getAttribute(a)||''))el.removeAttribute(a);});return;}
      var cc=el.closest('.cc-card');if(cc){var tr=cc.parentNode;if(tr&&tr.querySelector('[data-p2u-lock="'+id+'"],[data-p2u-unlocked="'+id+'"]')){cc.remove();return;}var d0=document.createElement('div');d0.className='cc-card p2u-cc-lock';d0.innerHTML=box(id);tr.replaceChild(d0,cc);return;}var bp=el.closest('.bp-card');if(bp){var trb=bp.parentNode;if(trb&&trb.querySelector('[data-p2u-lock="'+id+'"],[data-p2u-unlocked="'+id+'"]')){bp.remove();return;}var risk=bp.querySelector('.bp-risk'),gr=bp.querySelector('.bp-grade');var d1=document.createElement('div');d1.className=(bp.className||'bp-card')+' p2u-bp-lock';d1.innerHTML=(risk?risk.outerHTML:'')+(gr?gr.outerHTML:'')+box(id);trb.replaceChild(d1,bp);return;}
      var c=el.closest('.p2u-chips,.bcod-main')||el.closest('.bcod-chips,.bcod-act,.bcod-also,.hp-bkd a')||el.closest('.p2u-chip')||el;
      if(c.classList.contains('p2u-dl')||c.classList.contains('bcod-copy')||c.classList.contains('bcod-open')||/bcod-(chips|act|also)/.test(c.className)||c.matches('.hp-bkd a')||c.closest('.p2u-wa-row')){c.remove();return;}
      var par=c.parentNode;if(!par)return;
      if(par.querySelector(':scope > [data-p2u-lock="'+id+'"],:scope > [data-p2u-unlocked="'+id+'"]')){c.remove();return;}
      var t=document.createElement('div');t.innerHTML=box(id,el);var nb=t.firstChild;par.replaceChild(nb,c);
    });
    document.querySelectorAll('.p2u-wa[href]').forEach(function(a){try{var t=decodeURIComponent(a.getAttribute('href'));if(RX.test(t))a.setAttribute('href',a.getAttribute('href'))}catch(e){}});
  }
  function refresh(){document.querySelectorAll('[data-p2u-lock]').forEach(function(e){var t=document.createElement('div');t.innerHTML=box(e.getAttribute('data-p2u-lock'),e);if(t.firstChild)e.parentNode.replaceChild(t.firstChild,e);});}
  function modal(html){var prev=document.activeElement,m=document.createElement('div');m.className='p2u-lock-m';m.innerHTML='<div role="dialog" aria-modal="true" aria-labelledby="p2u-lock-h"><button type="button" class="p2u-lock-x" aria-label="Close">&times;</button>'+html+'</div>';document.body.appendChild(m);
    var ov=document.body.style.overflow;document.body.style.overflow='hidden';
    function close(){if(!m.isConnected)return;m.remove();document.body.style.overflow=ov;document.removeEventListener('keydown',kd,true);try{prev&&prev.focus&&prev.focus()}catch(e){}}
    function kd(e){if(e.key==='Escape'){e.preventDefault();close();return;}if(e.key==='Tab'){var f=[].filter.call(m.querySelectorAll('button,input,a[href]'),function(x){return !x.disabled;});if(!f.length)return;var i=f.indexOf(document.activeElement);if(e.shiftKey&&i<=0){e.preventDefault();f[f.length-1].focus();}else if(!e.shiftKey&&i===f.length-1){e.preventDefault();f[0].focus();}}}
    document.addEventListener('keydown',kd,true);m.p2uClose=close;var _rm=m.remove.bind(m);m.remove=function(){_rm();document.body.style.overflow=ov;document.removeEventListener('keydown',kd,true);};
    m.addEventListener('click',function(e){if(e.target===m||e.target.closest('.p2u-lock-x'))close();});
    setTimeout(function(){var f=m.querySelector('input')||m.querySelector('.p2u-lock-x');f&&f.focus();},0);return m;}
  function loadPop(){return new Promise(function(ok,no){if(window.PaystackPop)return ok();var s=document.createElement('script');s.src='https://js.paystack.co/v2/inline.js';s.onload=ok;s.onerror=no;document.head.appendChild(s);});}
  function verify(ref,id){return post('/pay/verify',{reference:ref,id:id}).then(function(g){save(g);refresh();return g;});}
  function pay(id){var m=cfg.locked[id]||{},pl=priceHtml(),pt=priceTxt();
    var md=modal('<b id="p2u-lock-h">Unlock '+esc(m.title||'slip')+' · '+pl+'</b><label style="display:block;margin-top:10px">Email for your receipt<input type="email" autocomplete="email" placeholder="you@example.com"></label><button class="p2u-lock-btn" style="width:100%">Pay '+pt+'</button><div class="p2u-lock-err"></div><small>Charged as GHS 50 via Paystack (mobile money or card). Codes show right after payment and stay unlocked on this device. 18+ only.</small>');
    var inp=md.querySelector('input'),btn=md.querySelector('.p2u-lock-btn'),err=md.querySelector('.p2u-lock-err');
    try{inp.value=localStorage.getItem('p2u-email')||''}catch(e){}
    btn.onclick=function(){var em=inp.value.trim();if(!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(em)){err.textContent='Enter a valid email.';return;}
      try{localStorage.setItem('p2u-email',em)}catch(e){}btn.disabled=true;btn.textContent='Opening payment…';
      post('/pay/init',{id:id,email:em,device:device(),back:location.href}).then(function(r){return loadPop().then(function(){md.remove();
        var p=new window.PaystackPop();p.resumeTransaction(r.access_code,{onSuccess:function(tx){verify(tx.reference||r.reference,id).catch(function(){alert('Payment received. If the codes do not show, tap "Already paid?" and enter your email.');});},onCancel:function(){}});
      }).catch(function(){location.href=r.authorization_url;});}).catch(function(e){btn.disabled=false;btn.textContent='Pay '+pt;err.textContent='Could not start payment: '+e.message;});};
  }
  function restore(){var md=modal('<b id="p2u-lock-h">Restore your unlocked codes</b><label style="display:block;margin-top:10px">Email you paid with<input type="email" autocomplete="email"></label><button class="p2u-lock-btn" style="width:100%">Restore</button><div class="p2u-lock-err"></div>');
    var inp=md.querySelector('input'),btn=md.querySelector('.p2u-lock-btn'),err=md.querySelector('.p2u-lock-err');try{inp.value=localStorage.getItem('p2u-email')||''}catch(e){}
    btn.onclick=function(){btn.disabled=true;post('/pay/restore',{email:inp.value.trim()}).then(function(r){(r.unlocks||[]).forEach(save);refresh();if((r.unlocks||[]).length)md.remove();else{err.textContent='No paid codes found for that email.';btn.disabled=false;}}).catch(function(e){err.textContent=e.message;btn.disabled=false;});};}
  document.addEventListener('click',function(e){var a=e.target.closest('[data-p2u-pay]');if(a){e.preventDefault();if(cfg&&cfg.enabled)pay(a.getAttribute('data-p2u-pay'));else info(a.getAttribute('data-p2u-pay'), a.closest('[data-p2u-odds]')||a);return;}
    if(e.target.closest('[data-p2u-restore]')){e.preventDefault();var om=e.target.closest('.p2u-lock-m');if(om)om.p2uClose();restore();return;}
    var inf=e.target.closest('[data-p2u-info]');if(inf&&!e.target.closest('.p2u-lock-m')){e.preventDefault();info(inf.getAttribute('data-p2u-info'),inf.closest('[data-p2u-odds]')||inf);return;}
    var c=e.target.closest('[data-p2u-unlocked] .p2u-chip-cp');if(c){try{navigator.clipboard.writeText(c.getAttribute('data-copy'));c.textContent='Copied';}catch(_){}}});
  document.addEventListener('keydown',function(e){if((e.key==='Enter'||e.key===' ')&&e.target.matches&&e.target.matches('.p2u-lock[data-p2u-info]')){e.preventDefault();info(e.target.getAttribute('data-p2u-info'));}});
  /* Free-codes mode (/p2u-free-mode.js sets window.P2U_FREE_CODES=true): no payment, no lock boxes, no relay call.
     Any old sealed placeholder whose real code was not saved is blanked so the code guard hides that chip. */
  function isFree(){return window.P2U_FREE_CODES===true;}
  function freeScan(){
    var RXG=new RegExp(RX.source,'gi'),w=document.createTreeWalker(document.body,NodeFilter.SHOW_TEXT,null),n,hit=[];
    while((n=w.nextNode())){RXG.lastIndex=0;if(RXG.test(n.nodeValue))hit.push(n);}
    hit.forEach(function(x){x.nodeValue=x.nodeValue.replace(RXG,'—');});
    document.querySelectorAll('[href*="P2ULOCK-" i],[data-copy*="P2ULOCK-" i],[data-cc-copy*="P2ULOCK-" i],[data-p2u-share*="P2ULOCK-" i],[data-cx*="P2ULOCK-" i]').forEach(function(e){
      ['href','data-copy','data-cc-copy','data-p2u-share','data-cx'].forEach(function(a){var v=e.getAttribute(a);if(v&&/P2ULOCK-/i.test(v))e.removeAttribute(a);});});
    document.querySelectorAll('.p2u-lock-m').forEach(function(m){m.remove();});
    if(window.P2UCode&&P2UCode.sweep)P2UCode.sweep(document);
  }
  function bootFree(){freeScan();var t=0;new MutationObserver(function(){clearTimeout(t);t=setTimeout(freeScan,60);}).observe(document.body,{childList:true,subtree:true,characterData:true});}
  function boot(){if(isFree())return bootFree();scan();new MutationObserver(function(){scan();}).observe(document.body,{childList:true,subtree:true});
    config().then(function(){var s=store();var ids=Object.keys(s);
      var q=new URLSearchParams(location.search),ref=q.get('reference')||q.get('trxref'),sid=q.get('p2uslip');
      var jobs=ids.map(function(id){return post('/unlock',{token:s[id].token}).then(function(g){got[id]=g;}).catch(function(){});});
      if(ref&&sid&&cfg.enabled)jobs.push(verify(ref,sid).catch(function(){}));
      return Promise.all(jobs);}).then(refresh);}
  window.P2UPaywall={free:isFree,has:function(id){return !!(got[id]&&got[id].codes);},show:function(g){if(!g||!g.id)return;got[g.id]=g;refresh();}};
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot);else boot();
})();
