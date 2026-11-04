/* Predict2U v289 — Bot picks board (NerdyTips + Bets For The Day), reads picks.json. */
(function(){
  'use strict';
  var $=function(id){return document.getElementById(id);};
  var esc=function(s){return String(s==null?'':s).replace(/[&<>"']/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c];});};
  var ZONE='Africa/Accra';
  var data=null,state={day:null,source:'all'};
  function stamp(d){return new Intl.DateTimeFormat('en-CA',{timeZone:ZONE,year:'numeric',month:'2-digit',day:'2-digit'}).format(d);}
  function ko(iso){if(!iso)return '';var d=new Date(iso);if(isNaN(d))return '';return d.toLocaleTimeString('en-GB',{timeZone:ZONE,hour:'2-digit',minute:'2-digit'});}
  function badge(r){r=r||'pending';return '<span class="bp-res bp-'+esc(r)+'">'+esc(r.toUpperCase())+'</span>';}
  function conf(c){return c==null?'—':Math.round(c*100)+'%';}
  function render(){
    var list=$('bp-list'),slips=data.slips.filter(function(s){return (s.dates||[s.date]).indexOf(state.day)>=0&&(state.source==='all'||s.source===state.source);});
    var legs=0,w=0,l=0;slips.forEach(function(s){s.legs.forEach(function(x){if(x.date!==state.day)return;legs++;if(x.result==='won')w++;if(x.result==='lost')l++;});});
    $('bp-summary').textContent=slips.length+' slips · '+legs+' picks · '+w+' won · '+l+' lost';
    if(!slips.length){list.innerHTML='<div class="p2u-bankers-empty">No bot slips for this day yet.</div>';return;}
    list.innerHTML=slips.map(function(s){
      var st=s.legs.some(function(x){return x.result==='lost';})?'lost':(s.legs.every(function(x){return x.result==='won'||x.result==='void';})?'won':'pending');
      return '<article class="bp-slip"><header><div><span class="bp-bot">'+esc(s.bot)+'</span> <small>'+esc(s.build||'')+'</small></div>'+
        '<div>'+(s.code?'<a class="bp-code" target="_blank" rel="noopener" href="'+esc(s.link)+'">SportyBet '+esc(s.code)+'</a>':'')+
        ' <b>@'+Number(s.totalOdds).toFixed(2)+'</b> '+badge(st)+'</div></header><table class="bp-legs"><thead><tr><th>KO</th><th>Match</th><th>Pick</th><th>Odds</th><th>Conf</th><th>Result</th></tr></thead><tbody>'+
        s.legs.map(function(x){return '<tr><td>'+esc(ko(x.kickoff))+'</td><td><div>'+esc(x.match)+'</div><small>'+esc(x.league)+'</small></td><td><div>'+esc(x.selection)+'</div><small>'+esc(x.market)+'</small></td><td>'+(x.odds==null?'—':Number(x.odds).toFixed(2))+'</td><td>'+conf(x.confidence)+'</td><td>'+badge(x.result)+'</td></tr>';}).join('')+
        '</tbody></table></article>';
    }).join('');
  }
  function init(d){
    data=d;var days=[];d.slips.forEach(function(s){(s.dates||[s.date]).forEach(function(x){if(days.indexOf(x)<0)days.push(x);});});days.sort();
    var t=stamp(new Date());state.day=days.indexOf(t)>=0?t:(days.filter(function(x){return x>=t;})[0]||days[days.length-1]);
    $('bp-day').innerHTML=days.map(function(x){return '<option value="'+x+'"'+(x===state.day?' selected':'')+'>'+x+(x===t?' (today)':'')+'</option>';}).join('');
    $('bp-source').innerHTML='<option value="all">All bots</option>'+Object.keys(d.sources).map(function(k){return '<option value="'+k+'">'+esc(d.sources[k])+'</option>';}).join('');
    $('bp-day').onchange=function(){state.day=this.value;render();};
    $('bp-source').onchange=function(){state.source=this.value;render();};
    var up=new Date(d.DATA_UPDATED);
    $('bankers-meta').textContent='Updated '+up.toLocaleString('en-GB',{timeZone:ZONE,day:'numeric',month:'short',hour:'2-digit',minute:'2-digit'})+' GMT';
    render();
  }
  fetch('picks.json?t='+Date.now(),{cache:'no-store'}).then(function(r){if(!r.ok)throw new Error(r.status);return r.json();}).then(init)
    .catch(function(e){$('bankers-meta').textContent='Could not load picks ('+e.message+').';});
})();
