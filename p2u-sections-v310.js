/* Predict2U v310 — every home section collapsible; state remembered in localStorage. */
(function(){'use strict';
var SK='p2u-sec',st={};try{st=JSON.parse(localStorage.getItem(SK))||{};}catch(e){}
var css='.p2u-sec{margin:12px 0;border:1px solid rgba(148,163,184,.22);border-radius:16px;background:rgba(15,23,42,.55)}.p2u-sec[hidden]{display:none}'+
'.p2u-sec-h{all:unset;box-sizing:border-box;display:flex;align-items:center;gap:10px;width:100%;min-height:48px;padding:10px 14px;cursor:pointer;color:#fff;font-weight:900;font-size:clamp(1rem,3.6vw,1.15rem)}.p2u-sec-h:focus-visible{outline:2px solid #facc15;outline-offset:2px;border-radius:16px}'+
'.p2u-sec-h span{flex:1}.p2u-sec-h small{font-weight:600;color:#cbd5e1;font-size:.78rem}'+
'.p2u-sec-v{width:9px;height:9px;border-right:2px solid #facc15;border-bottom:2px solid #facc15;transform:rotate(45deg);transition:transform .25s;margin-right:4px}.p2u-sec.is-open>.p2u-sec-h .p2u-sec-v{transform:rotate(225deg)}'+
'.p2u-sec-b{display:grid;grid-template-rows:0fr;transition:grid-template-rows .3s ease}.p2u-sec.is-open>.p2u-sec-b{grid-template-rows:1fr}.p2u-sec-b>div{overflow:hidden;min-height:0;padding:0 10px}.p2u-sec.is-open>.p2u-sec-b>div{padding-bottom:10px}'+
'.p2u-sec-b>div>section{margin-top:0}@media (prefers-reduced-motion:reduce){.p2u-sec-b,.p2u-sec-v{transition:none}}';
var s=document.createElement('style');s.textContent=css;document.head.appendChild(s);
var D=[['.p2u-bankers-hero','hero','Picks of the Day',1],['#hp-carousel','carousel','Booking codes carousel',1],['#hp-code','code','Banker & all-picks codes',1],['#hp-tally','tally','Today’s tally',0],['#hp-list','list','Today’s picks',1],['.hp-lg','leagues','How favourites perform by league',1],['#news-hub','hub','Football hub · code results, fixtures, injuries, transfers',1]];
D.forEach(function(x){var sec=document.querySelector(x[0]);if(!sec)return;var o=x[1] in st?!!st[x[1]]:!!x[3];
 var w=document.createElement('div');w.className='p2u-sec'+(o?' is-open':'');w.dataset.sec=x[1];
 w.innerHTML='<button type="button" class="p2u-sec-h" aria-expanded="'+o+'"><span>'+x[2]+'</span><i class="p2u-sec-v" aria-hidden="true"></i></button><div class="p2u-sec-b"'+(o?'':' inert')+'><div></div></div>';
 sec.parentNode.insertBefore(w,sec);w.querySelector('.p2u-sec-b>div').appendChild(sec);
 var sync=function(){w.hidden=sec.hidden;};sync();new MutationObserver(sync).observe(sec,{attributes:true,attributeFilter:['hidden']});
 w.firstChild.addEventListener('click',function(){var n=!w.classList.contains('is-open');w.classList.toggle('is-open',n);this.setAttribute('aria-expanded',n);var b=w.querySelector('.p2u-sec-b');if(n)b.removeAttribute('inert');else b.setAttribute('inert','');st[x[1]]=n?1:0;try{localStorage.setItem(SK,JSON.stringify(st));}catch(e){}});});
})();
