/* Predict2U v296 — Picks of the Day (favourites strategy), reads home.json. */
(function(){
  'use strict';
  var $=function(id){return document.getElementById(id);};
  var esc=function(s){return String(s==null?'':s).replace(/[&<>"']/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c];});};
  var ZONE='Africa/Accra';
  function stamp(d){return new Intl.DateTimeFormat('en-CA',{timeZone:ZONE,year:'numeric',month:'2-digit',day:'2-digit'}).format(d);}
  function ko(iso){var d=new Date(iso);return isNaN(d)?'':d.toLocaleTimeString('en-GB',{timeZone:ZONE,hour:'2-digit',minute:'2-digit'});}
  function pct(x){return x==null?'—':Math.round(x*100)+'%';}
  function badge(r){r=r||'pending';return '<span class="bp-res bp-'+esc(r)+'">'+esc(r.toUpperCase())+'</span>';}
  function gradeOf(c){return c>=0.8?'A':c>=0.72?'B':'C';}
  var data,day;
  function render(){
    var P=(data.days[day]||[]).slice();
    var w=P.filter(function(p){return p.result==='won';}),l=P.filter(function(p){return p.result==='lost';}),pend=P.length-w.length-l.length;
    $('hp-tally').innerHTML='<div class="hp-t hp-tw"><b>'+w.length+'</b><span>Won</span></div><div class="hp-t hp-tl"><b>'+l.length+'</b><span>Lost</span></div><div class="hp-t"><b>'+pend+'</b><span>Pending</span></div><div class="hp-t"><b>'+(w.length+l.length?Math.round(100*w.length/(w.length+l.length))+'%':'—')+'</b><span>Hit rate</span></div>'+
      (w.length?'<div class="hp-wonlist">'+w.map(function(p){return '<span>✓ '+esc(p.match)+' · '+esc(p.selection)+(p.score?' ('+esc(p.score)+')':'')+'</span>';}).join('')+'</div>':'');
    if(!P.length){$('hp-list').innerHTML='<div class="p2u-bankers-empty">No picks for this day yet.</div>';return;}
    P.sort(function(a,b){return (a.result==='won'?0:1)-(b.result==='won'?0:1)||a.kickoff.localeCompare(b.kickoff);});
    $('hp-list').innerHTML=P.map(function(p){var g=gradeOf(p.confidence);
      return '<article class="hp-pick'+(p.result==='won'?' is-won':p.result==='lost'?' is-lost':'')+'"><div class="hp-top"><span class="bp-grade bp-g'+g+'">'+g+'</span><div class="hp-mt"><b>'+esc(p.match)+'</b><small>'+esc(ko(p.kickoff))+' · '+esc(p.league)+'</small></div>'+badge(p.result)+'</div>'+
        '<div class="hp-sel"><span>'+esc(p.selection)+'</span><b>@'+Number(p.odds).toFixed(2)+'</b></div>'+
        '<dl class="hp-stats"><div><dt>League fav. rate</dt><dd>'+pct(p.leagueRate)+'</dd></div><div><dt>Sample</dt><dd>'+esc(p.sample)+' games</dd></div><div><dt>Our confidence</dt><dd>'+pct(p.confidence)+'</dd></div><div><dt>'+(p.score?'Score':'Table')+'</dt><dd>'+esc(p.score||p.table||'—')+'</dd></div></dl></article>';}).join('');
  }
  function leagues(){
    var L=data.leagues.filter(function(x){return (x.favGames||0)>=20||x.recent;}).slice(0,40);
    $('hp-leagues').innerHTML='<table class="bp-legs hp-lt"><thead><tr><th>League</th><th>Games</th><th>Fav. win %</th><th>Recent form</th></tr></thead><tbody>'+L.map(function(x){
      var r=x.recent?(x.recent.won+'W–'+x.recent.lost+'L'):'—';
      return '<tr><td class="bp-m">'+esc(x.league)+'</td><td data-l="Games">'+(x.games==null?'—':x.games)+(x.favGames?' <small>('+x.favGames+' fav)</small>':'')+'</td><td data-l="Fav. win %"><span class="hp-bar"><i style="width:'+Math.round((x.favWin||0)*100)+'%"></i></span>'+pct(x.favWin)+'</td><td data-l="Recent form">'+r+'</td></tr>';}).join('')+'</tbody></table>';
  }
  function init(d){data=d;var days=Object.keys(d.days).sort();var t=stamp(new Date());day=days.indexOf(t)>=0?t:days[days.length-1];
    $('hp-day').innerHTML=days.map(function(x){return '<option value="'+x+'"'+(x===day?' selected':'')+'>'+x+(x===t?' (today)':'')+'</option>';}).join('');
    $('hp-day').onchange=function(){day=this.value;render();};
    $('hp-meta').textContent='Updated '+new Date(d.DATA_UPDATED).toLocaleString('en-GB',{timeZone:ZONE,day:'numeric',month:'short',hour:'2-digit',minute:'2-digit'})+' GMT';
    render();leagues();}
  fetch('home.json',{cache:'no-cache'}).then(function(r){if(!r.ok)throw new Error(r.status);return r.json();}).then(init).catch(function(e){$('hp-meta').textContent='Could not load picks ('+e.message+').';});
})();
