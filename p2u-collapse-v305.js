/* Predict2U v305 — shared collapsible pattern: every code block starts collapsed; state kept per session only. */
(function(){'use strict';
var SK='p2u-cx',st={};try{st=JSON.parse(sessionStorage.getItem(SK))||{};}catch(e){}
function save(){try{sessionStorage.setItem(SK,JSON.stringify(st));}catch(e){}}
var css='.p2u-cx-h{all:unset;box-sizing:border-box;display:flex;align-items:center;gap:8px;width:100%;cursor:pointer;min-height:44px;padding:8px 10px;border-radius:12px;color:#fff;font-weight:700}.p2u-cx-h:focus-visible{outline:2px solid #7fb2ff;outline-offset:2px}.p2u-cx-h .p2u-cx-s{flex:1;min-width:0}.p2u-cx-h small{display:block;font-weight:500;color:#c9d6ea;font-size:.8rem}'+
'.p2u-cx-d{display:inline-flex;gap:4px;align-items:center}.p2u-cx-d i{width:10px;height:10px;border-radius:50%;background:var(--c);box-shadow:0 0 6px var(--c)}.p2u-cx-d img{width:18px;height:18px;border-radius:4px}'+
'.p2u-cx-v{flex:none;width:9px;height:9px;border-right:2px solid #a9c9ff;border-bottom:2px solid #a9c9ff;transform:rotate(45deg);transition:transform .25s;margin:0 6px}.p2u-cx.is-open>.p2u-cx-h .p2u-cx-v{transform:rotate(225deg)}'+
'.p2u-cx-b{display:grid;grid-template-rows:0fr;transition:grid-template-rows .3s ease}.p2u-cx.is-open>.p2u-cx-b{grid-template-rows:1fr}.p2u-cx-b>div{overflow:hidden;min-height:0}'+
'details>summary~*{animation:p2uCx .25s ease}@keyframes p2uCx{from{opacity:0;transform:translateY(-4px)}}'+
'@media (prefers-reduced-motion:reduce){.p2u-cx-b,.p2u-cx-v{transition:none}details>summary~*{animation:none}}';
var s=document.createElement('style');s.textContent=css;document.head.appendChild(s);
var COL={sportybet:'#e41827',msport:'#ffd325',betika:'#00b140',footballcom:'#282450',betpawa:'#78be20',onexbet:'#1f6fb2','1xbet':'#1f6fb2',betway:'#00a826','22bet':'#1b5e20'};
function dots(root){var seen={},h='';(root.querySelectorAll('[class*="p2u-chip-"],[class*="bp-book-"]')).forEach(function(el){(el.className.match(/(?:p2u-chip|bp-book)-([a-z0-9]+)/g)||[]).forEach(function(m){var k=m.split('-').pop();if(COL[k]&&!seen[k]){seen[k]=1;h+='<i style="--c:'+COL[k]+'" title="'+k+'"></i>';}});});return h?'<span class="p2u-cx-d" aria-hidden="true">'+h+'</span>':'';}
function wrap(host,id,title,sub,body){var o=!!st[id];var w=document.createElement('div');w.className='p2u-cx'+(o?' is-open':'');w.dataset.cx=id;
 w.innerHTML='<button type="button" class="p2u-cx-h" aria-expanded="'+o+'"><span class="p2u-cx-s">'+title+(sub?'<small>'+sub+'</small>':'')+'</span>'+dots(body)+'<i class="p2u-cx-v" aria-hidden="true"></i></button><div class="p2u-cx-b"><div></div></div>';
 var inner=w.querySelector('.p2u-cx-b>div');while(body.firstChild)inner.appendChild(body.firstChild);if(!o)w.querySelector('.p2u-cx-b').setAttribute('inert','');host.appendChild(w);}
function enhance(){
 // Home "Book all of today's picks"
 var hc=document.getElementById('hp-code');if(hc&&!hc.querySelector('.p2u-cx')&&hc.querySelector('.p2u-chip')){var h2=hc.querySelector('.hp-code-h'),n=hc.querySelectorAll('.p2u-chip').length,f=document.createDocumentFragment(),tmp=document.createElement('div');
  Array.prototype.slice.call(hc.children).forEach(function(c){if(c!==h2)tmp.appendChild(c);});
  var ttl=h2?h2.textContent:'Book all of today’s picks';if(h2)h2.remove();var ho=document.createElement('h2');ho.className='hp-code-h';ho.style.margin='0';
  wrap(hc,'homecode','<span class="hp-code-h" style="margin:0">'+ttl+'</span>',n+' code'+(n>1?'s':'')+' · tap to open',tmp);}
 // Bankers slips: move chips out of summary, add brand dots, never open by default
 document.querySelectorAll('details.bp-slip').forEach(function(d){if(d.dataset.cx)return;d.dataset.cx=1;var sm=d.querySelector('summary'),ch=sm&&sm.querySelector('.p2u-chips');if(ch){sm.insertAdjacentHTML('beforeend',dots(ch));d.insertBefore(ch,sm.nextSibling);}});
 // Carousel cards: code details collapse
 document.querySelectorAll('.cc-card').forEach(function(c){if(c.dataset.cx)return;c.dataset.cx=1;var b=document.createElement('div');c.querySelectorAll('.cc-code,.cc-n,.cc-a').forEach(function(x){b.appendChild(x);});var m=c.querySelector('.cc-m');var k='cc-'+((b.querySelector('.cc-code')||{}).textContent||'');wrap(c,k,'Show code',m?'':null,b);lbl(c.querySelector('.p2u-cx'));});
 // Generic details: start closed unless opened this session
 document.querySelectorAll('details').forEach(function(d){if(d.dataset.cxd)return;d.dataset.cxd=1;var k='d-'+(d.className||'')+'-'+((d.querySelector('summary')||{}).textContent||'').slice(0,60);if(!d.classList.contains('hp-bkw'))d.open=!!st[k];d.addEventListener('toggle',function(){if(d.open)st[k]=1;else delete st[k];save();});});
}
document.addEventListener('click',function(e){var h=e.target.closest&&e.target.closest('.p2u-cx-h');if(!h)return;e.preventDefault();e.stopPropagation();var w=h.parentNode,o=!w.classList.contains('is-open');w.classList.toggle('is-open',o);h.setAttribute('aria-expanded',o);var b=w.querySelector('.p2u-cx-b');if(o)b.removeAttribute('inert');else b.setAttribute('inert','');if(o)st[w.dataset.cx]=1;else delete st[w.dataset.cx];save();lbl(w);},true);
function lbl(w){if(!w.parentNode||!w.parentNode.classList||!w.parentNode.classList.contains('cc-card'))return;var t=w.querySelector('.p2u-cx-s');if(t&&t.firstChild&&t.firstChild.nodeType===3)t.firstChild.nodeValue=w.classList.contains('is-open')?'Hide code':'Show code';}
var t;new MutationObserver(function(){clearTimeout(t);t=setTimeout(enhance,30);}).observe(document.documentElement,{childList:true,subtree:true});
if(document.readyState!=='loading')enhance();else document.addEventListener('DOMContentLoaded',enhance);
})();
