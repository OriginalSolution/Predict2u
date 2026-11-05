/* Predict2U v317 — public Track record page, reads record.json (settled codes only). */
(function(){
  'use strict';
  var $=function(id){return document.getElementById(id);};
  var esc=function(s){return String(s==null?'':s).replace(/[&<>"']/g,function(c){return{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c];});};
  var ZONE='Africa/Accra';
  var BOOKS={sportybet:'SportyBet',msport:'MSport',betika:'Betika',footballcom:'football.com',betpawa:'Betpawa',onexbet:'1xBet'};
  function money(n){var x=Number(n)||0;return (x<0?'−':'')+'GH₵'+Math.abs(x).toLocaleString('en-GH',{minimumFractionDigits:0,maximumFractionDigits:2});}
  function pct(n){return n==null?'—':Number(n).toFixed(1)+'%';}
  function pill(st){st=(st||'').toLowerCase();return '<span class="pill pill-'+esc(st)+'">'+esc(st||'—')+'</span>';}
  function table(rows, label){
    if(!rows||!rows.length) return '<p class="empty">No settled codes in this breakdown yet.</p>';
    return '<div style="overflow-x:auto"><table class="tbl"><thead><tr><th>'+esc(label)+'</th><th>Settled</th><th>Won</th><th>Win rate</th><th>ROI</th><th>Profit</th></tr></thead><tbody>'+
      rows.map(function(r){return '<tr><th scope="row">'+esc(BOOKS[r.key]||r.key)+'</th><td>'+r.n+'</td><td>'+r.won+'</td><td>'+pct(r.winRate)+'</td><td class="'+(r.roi>=0?'pos':'neg')+'">'+pct(r.roi)+'</td><td class="'+(r.profit>=0?'pos':'neg')+'">'+money(r.profit)+'</td></tr>';}).join('')+
      '</tbody></table></div>';
  }
  function render(d){
    var o=d.overall||{}, st=d.streak||{}, pk=d.picks||{};
    $('rec-meta').textContent=d.DATA_UPDATED?'Updated '+new Date(d.DATA_UPDATED).toLocaleString('en-GB',{timeZone:ZONE,day:'numeric',month:'short',hour:'2-digit',minute:'2-digit'})+' GMT · flat stake '+money(d.flatStake||10):'';
    var streakTxt=st.current?(st.current.toUpperCase()+' ×'+st.currentLen):'—';
    $('rec-kpis').innerHTML=
      '<div class="kpi '+(o.winRate>0?'win':(o.n?'lose':''))+'"><span>Win rate</span><b>'+pct(o.winRate)+'</b></div>'+
      '<div class="kpi"><span>Settled slips</span><b>'+(o.n||0)+'</b></div>'+
      '<div class="kpi '+(o.roi>=0?'win':'lose')+'"><span>ROI @ GH₵10</span><b>'+pct(o.roi)+'</b></div>'+
      '<div class="kpi '+(st.current==='won'?'win':'lose')+'"><span>Streak</span><b>'+esc(streakTxt)+'</b></div>'+
      '<div class="kpi win"><span>Pick hit rate</span><b>'+pct(pk.winRate)+'</b></div>'+
      '<div class="kpi"><span>Picks settled</span><b>'+(pk.settled||0)+'</b></div>'+
      '<div class="kpi lose"><span>Profit</span><b>'+money(o.profit)+'</b></div>'+
      '<div class="kpi flat"><span>Pending codes</span><b>'+(o.pending||0)+'</b></div>';
    if(d.note){$('rec-note').hidden=false;$('rec-note').textContent=d.note+(st.bestLoss?' Best losing streak: '+st.bestLoss+'.':'')+(st.bestWin?' Best winning streak: '+st.bestWin+'.':'');}
    $('rec-type').innerHTML=table(d.byType,'Type');
    $('rec-site').innerHTML=table(d.bySite,'Site');
    $('rec-market').innerHTML=table(d.byMarket,'Market');
    $('rec-day').innerHTML=table(d.byDay,'Day');
    var recent=d.recent||[];
    $('rec-recent').innerHTML=recent.length?recent.map(function(r){
      return '<article class="rc"><div class="rc-top"><div><b>'+esc(r.name||r.code)+'</b> '+pill(r.status)+'</div><div class="rc-meta">'+esc(r.date)+' · '+esc(BOOKS[r.book]||r.book)+'</div></div>'+
        '<div class="rc-bot"><span>Code <b>'+esc(r.code)+'</b></span><span>@'+Number(r.odds||0).toLocaleString('en-GB',{maximumFractionDigits:2})+'</span><span>'+esc(r.hit)+'/'+esc(r.total)+' legs hit</span><span class="'+(r.profit>=0?'pos':'neg')+'">'+money(r.profit)+'</span></div></article>';
    }).join(''):'<p class="empty">No settled codes yet — check back after tonight’s games.</p>';
  }
  function fail(e){$('rec-meta').textContent='Could not load track record'+(e&&e.message?': '+e.message:'');$('rec-kpis').innerHTML='';}
  fetch('record.json',{cache:'no-cache'}).then(function(r){if(!r.ok)throw new Error(r.status);return r.json();}).then(render).catch(fail);
})();
