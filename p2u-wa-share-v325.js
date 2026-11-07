/* Predict2U v325 — WhatsApp share: image card + per-slip link predict2u.com/s/<code>/ (link preview shows the card). Deep-link highlight via ?code=. */
(function(global){
  'use strict';
  var BOOKS=[['sportybet','SportyBet'],['msport','MSport'],['betika','Betika'],['footballcom','football.com'],['betpawa','Betpawa'],['betway','Betway']];
  var REG={};
  function cv(v){ if(Array.isArray(v)) v=v[0]; if(v&&typeof v==='object') v=v.code; return v||''; }
  function codesOf(s){ var o={},c=s.codes||{}; Object.keys(c).forEach(function(k){var x=cv(c[k]); if(x&&!/^P2ULOCK-/.test(x))o[k]=x;}); if(!o.sportybet&&s.code&&!/^P2ULOCK-/i.test(s.code))o.sportybet=s.code; return o; }
  function label(s){
    var r=(s.risk||'').toLowerCase(), n=s.name||s.label||'Slip';
    if(r==='safe'||/safe slip/i.test(n)) return 'Safe slip';
    if(r==='medium'||/medium slip/i.test(n)) return 'Medium slip';
    if(s.banker||/banker/i.test(n)) return 'Banker slip';
    return n;
  }
  function key(s){ var c=codesOf(s); return c.sportybet||c[Object.keys(c)[0]]||''; }
  function img(s){ var k=key(s); return k?'https://predict2u.com/share/'+encodeURIComponent(k)+'.png':''; }
  function slipUrl(s){ var k=key(s); return k?'https://predict2u.com/s/'+encodeURIComponent(k)+'/':page(); }
  function page(){ var p=location.pathname.split('/').pop()||'index.html'; return 'https://predict2u.com/'+(/hot-picks|bankers/.test(p)?p:/high-odds/.test(location.pathname)?'high-odds/#':''); }
  function text(s){
    var codes=codesOf(s);
    var odds=(s.bookOdds&&s.bookOdds.sportybet)||s.totalOdds||s.odds;
    var n=(s.bookPicks&&s.bookPicks.sportybet)||s.picks||(Array.isArray(s.legs)?s.legs.length:s.legs);
    var P=s.parts||[],ok=function(c){return c&&c.code&&(!window.P2UCode||P2UCode.isReal(c.code));};
    var lines=['Predict2U — '+label(s)+(P.length||s.highRisk?' · HIGH RISK':''), '@'+Number(odds||0).toFixed(2)+' · '+n+' picks', ''];
    if(P.length){
      lines.push('Bookmakers take max 50 picks per code, so use the '+P.length+' parts:');
      P.forEach(function(pt,i){
        var L=BOOKS.map(function(b){var c=((pt.codes||{})[b[0]]||[])[0];return ok(c)?'  '+b[1]+': '+c.code+' ('+c.legs+' picks @'+Number(c.totalOdds).toFixed(2)+')':null;}).filter(Boolean);
        if(!L.length)return; var f=((pt.codes||{}).sportybet||[])[0]||{};
        lines.push('','Part '+(i+1)+' · '+pt.legs+' picks'+(ok(f)?' · https://predict2u.com/s/'+encodeURIComponent(f.code)+'/':''));
        lines.push.apply(lines,L);
      });
      lines.push('', 'Full code ('+n+' picks, too many for one slip): '+(codes.sportybet||''));
    } else BOOKS.forEach(function(b){ if(codes[b[0]]) lines.push(b[1]+': '+codes[b[0]]); });
    if(!Object.keys(codes).length) lines.push('🔒 Premium codes: unlock on predict2u.com');
    lines.push('', 'Open this slip: '+slipUrl(s), '18+ Bet responsibly');
    return lines.join('\n');
  }
  function fallbackText(s){ return text(s); }
  function href(s){ var h='https://wa.me/?text='+encodeURIComponent(fallbackText(s)); REG[h]=s; var k=key(s); if(k)REG['k:'+k]=s; return h; }
  function button(s, cls){
    var k=key(s);
    return '<a class="'+(cls||'p2u-wa')+'" data-p2u-share="'+k+'" target="_blank" rel="noopener" href="'+href(s)+'" aria-label="Share on WhatsApp">Share on WhatsApp</a>'+
      (k?'<a class="p2u-dl" href="/share/'+k+'.png" download="predict2u-'+k+'.png" aria-label="Download slip image">Download image</a>':'');
  }
  function share(s, a){
    var u=img(s);
    if(!u||!navigator.canShare||!global.fetch||!global.File) return false;
    a.classList.add('p2u-busy');
    fetch(u,{cache:'force-cache'}).then(function(r){ if(!r.ok) throw 0; return r.blob(); }).then(function(b){
      var f=new File([b],'predict2u-'+key(s)+'.png',{type:'image/png'});
      var d={files:[f],text:text(s),url:slipUrl(s)};
      if(!navigator.canShare(d)) d={files:[f],text:text(s)};
      if(!navigator.canShare(d)) throw 0;
      return navigator.share(d);
    }).catch(function(e){ if(e&&e.name==='AbortError') return; global.open(a.href,'_blank','noopener'); })
      .then(function(){ a.classList.remove('p2u-busy'); });
    return true;
  }
  document.addEventListener('click',function(ev){
    var a=ev.target.closest&&ev.target.closest('a.p2u-wa,a.bp-wa'); if(!a) return;
    var s=REG[a.getAttribute('href')]||REG['k:'+(a.getAttribute('data-p2u-share')||'')]; if(!s) return;
    var mobile=/Android|iPhone|iPad|iPod|Mobile/i.test(navigator.userAgent);
    if(mobile&&navigator.canShare){ ev.preventDefault(); share(s,a); }
  });
  function css(){
    if(document.getElementById('p2u-wa-css')) return;
    var st=document.createElement('style'); st.id='p2u-wa-css';
    st.textContent='.p2u-wa,.bp-wa{display:inline-flex;align-items:center;justify-content:center;gap:6px;min-height:40px;padding:0 14px;border-radius:999px;background:#128C7E;color:#fff!important;font-weight:800;font-size:.82rem;text-decoration:none!important;border:0;margin-top:8px}'+
      '.p2u-wa:hover,.bp-wa:hover,.p2u-dl:hover{filter:brightness(1.08);text-decoration:none!important}'+
      '.p2u-wa::before,.bp-wa::before{content:"↪";font-size:.95rem}.p2u-busy{opacity:.6}'+
      '.p2u-dl{display:inline-flex;align-items:center;min-height:40px;padding:0 14px;border-radius:999px;background:#0b1c2f;color:#fff!important;border:1px solid #78be20;font-weight:800;font-size:.82rem;text-decoration:none!important;margin-top:8px}.p2u-dl::before{content:"⬇";margin-right:6px}'+
      '.bp-card-a .bp-wa{min-height:36px;padding:0 10px;font-size:.75rem;margin-top:0}'+
      '.p2u-wa-row{display:flex;flex-wrap:wrap;gap:8px;margin-top:8px}';
    document.head.appendChild(st);
  }
  function hl(){
    var m=/[?&]code=([A-Za-z0-9_-]+)/.exec(location.search); if(!m) return; var c=m[1], n=0;
    (function t(){
      var w=document.createTreeWalker(document.body,NodeFilter.SHOW_TEXT,null), x, el=null;
      while((x=w.nextNode())){ if(x.nodeValue.indexOf(c)>-1&&x.parentElement&&x.parentElement.offsetParent!==null){ el=x.parentElement; break; } }
      if(!el){ var d=document.querySelectorAll('details:not([open])'); for(var i=0;i<d.length;i++){ if((d[i].textContent||'').indexOf(c)>-1){ d[i].open=true; } } if(++n<40) return setTimeout(t,250); return; }
      var card=el.closest('[class*="slip"],[class*="card"],article,li')||el;
      card.style.outline='3px solid #ffcc00'; card.style.outlineOffset='3px'; card.style.borderRadius='14px';
      card.scrollIntoView({behavior:'smooth',block:'center'});
    })();
  }
  if(document.readyState==='loading') document.addEventListener('DOMContentLoaded',hl); else hl();
  global.P2UWA={slipUrl:slipUrl,text:text,href:href,button:button,css:css,image:img,share:share};
})(window);
