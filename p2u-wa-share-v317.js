/* Predict2U v317 — WhatsApp share helper for slips (wa.me with codes text). */
(function(global){
  'use strict';
  var BOOKS=[['sportybet','SportyBet'],['msport','MSport'],['betika','Betika'],['footballcom','football.com'],['betpawa','Betpawa']];
  function label(s){
    var r=(s.risk||'').toLowerCase(), n=s.name||s.label||'Slip';
    if(r==='safe'||/safe slip/i.test(n)) return 'Safe slip';
    if(r==='medium'||/medium slip/i.test(n)) return 'Medium slip';
    if(s.banker||/banker/i.test(n)) return 'Banker slip';
    return n;
  }
  function text(s){
    var codes=s.codes||{}; if(!codes.sportybet&&s.code) codes=Object.assign({sportybet:s.code},codes);
    var odds=(s.bookOdds&&s.bookOdds.sportybet)||s.totalOdds;
    var n=(s.bookPicks&&s.bookPicks.sportybet)||s.picks||(s.legs||[]).length;
    var lines=['Predict2U — '+label(s), '@'+Number(odds||0).toFixed(2)+' · '+n+' picks', ''];
    BOOKS.forEach(function(b){ if(codes[b[0]]) lines.push(b[1]+': '+codes[b[0]]); });
    lines.push('', 'https://predict2u.com/bankers.html', '18+ Bet responsibly');
    return lines.join('\n');
  }
  function href(s){ return 'https://wa.me/?text='+encodeURIComponent(text(s)); }
  function button(s, cls){
    return '<a class="'+(cls||'p2u-wa')+'" target="_blank" rel="noopener" href="'+href(s)+'" aria-label="Share on WhatsApp">Share on WhatsApp</a>';
  }
  function css(){
    if(document.getElementById('p2u-wa-css')) return;
    var st=document.createElement('style'); st.id='p2u-wa-css';
    st.textContent='.p2u-wa,.bp-wa{display:inline-flex;align-items:center;justify-content:center;gap:6px;min-height:40px;padding:0 14px;border-radius:999px;background:#128C7E;color:#fff!important;font-weight:800;font-size:.82rem;text-decoration:none!important;border:0;margin-top:8px}'+
      '.p2u-wa:hover,.bp-wa:hover{filter:brightness(1.08);text-decoration:none!important}'+
      '.p2u-wa::before,.bp-wa::before{content:"↪";font-size:.95rem}'+
      '.bp-card-a .bp-wa{min-height:36px;padding:0 10px;font-size:.75rem;margin-top:0}'+
      '.p2u-wa-row{display:flex;flex-wrap:wrap;gap:8px;margin-top:8px}';
    document.head.appendChild(st);
  }
  global.P2UWA={text:text,href:href,button:button,css:css};
})(window);
