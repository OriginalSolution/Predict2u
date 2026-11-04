/* Predict2U v290 — Picks board: booking-code carousel by bookmaker + graded slips, reads picks.json. */
(function(){
  'use strict';
  var $=function(id){return document.getElementById(id);};
  var esc=function(s){return String(s==null?'':s).replace(/[&<>"']/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c];});};
  var ZONE='Africa/Accra',GR={A:0,B:1,C:2};
  var BOOKS=[['sportybet','SportyBet'],['msport','MSport'],['onexbet','1xBet']];
  var data=null,state={day:null};
  function stamp(d){return new Intl.DateTimeFormat('en-CA',{timeZone:ZONE,year:'numeric',month:'2-digit',day:'2-digit'}).format(d);}
  function ko(iso){if(!iso)return '';var d=new Date(iso);if(isNaN(d))return '';return d.toLocaleTimeString('en-GB',{timeZone:ZONE,hour:'2-digit',minute:'2-digit'});}
  function badge(r){r=r||'pending';return '<span class="bp-res bp-'+esc(r)+'">'+esc(r.toUpperCase())+'</span>';}
  function grade(g){return '<span class="bp-grade bp-g'+esc(g)+'">'+esc(g)+'</span>';}
  function pct(c){return c==null?'—':Math.round(c*100)+'%';}
  function daySlips(){
    return data.slips.filter(function(s){return (s.dates||[s.date]).indexOf(state.day)>=0;})
      .sort(function(a,b){return (GR[a.grade]-GR[b.grade])||(b.rating-a.rating);})
      .map(function(s,i){return Object.assign({},s,{label:'Slip '+(i+1)});});
  }
  function carousel(slips){
    return BOOKS.map(function(b){
      var cards=slips.filter(function(s){return s.codes&&s.codes[b[0]];});
      if(!cards.length)return '';
      return '<div class="bp-book"><h3>'+b[1]+' codes <small>('+cards.length+')</small></h3><div class="bp-car" tabindex="0">'+cards.map(function(s){
        var code=s.codes[b[0]],link=(s.links||{})[b[0]];
        return '<div class="bp-card">'+grade(s.grade)+'<div class="bp-card-l">'+esc(s.label)+'</div><div class="bp-card-code">'+esc(code)+'</div>'+
          '<div class="bp-card-m">@'+Number(s.totalOdds).toFixed(2)+' · '+s.picks+' picks</div>'+
          '<div class="bp-card-a"><button type="button" data-copy="'+esc(code)+'">Copy</button>'+(link?'<a target="_blank" rel="noopener" href="'+esc(link)+'" aria-label="Open on '+b[1]+'">Open ↗</a>':'')+'</div></div>';
      }).join('')+'</div></div>';
    }).join('');
  }
  function render(){
    var slips=daySlips(),legs=0,w=0,l=0;
    slips.forEach(function(s){s.legs.forEach(function(x){if(x.date!==state.day)return;legs++;if(x.result==='won')w++;if(x.result==='lost')l++;});});
    $('bp-summary').textContent=slips.length+' slips · '+legs+' picks · '+w+' won · '+l+' lost';
    $('bp-carousel').innerHTML=carousel(slips);
    var list=$('bp-list');
    if(!slips.length){list.innerHTML='<div class="p2u-bankers-empty">No slips for this day yet.</div>';return;}
    list.innerHTML=slips.map(function(s,i){
      var st=s.legs.some(function(x){return x.result==='lost';})?'lost':(s.legs.every(function(x){return x.result==='won'||x.result==='void';})?'won':'pending');
      return '<details class="bp-slip"'+(i===0?' open':'')+'><summary><header><div>'+grade(s.grade)+' <b>'+esc(s.label)+'</b> <small>'+s.picks+' picks</small></div>'+
        '<div>'+(s.link?'<a class="bp-code" target="_blank" rel="noopener" href="'+esc(s.link)+'">SportyBet '+esc(s.code)+'</a>':'')+
        ' <b>@'+Number(s.totalOdds).toFixed(2)+'</b> '+badge(st)+'</div></header></summary><table class="bp-legs"><thead><tr><th>KO</th><th>Match</th><th>Pick</th><th>Odds</th><th>P2U score</th><th>Result</th></tr></thead><tbody>'+
        s.legs.map(function(x){return '<tr><td data-l="KO">'+esc(ko(x.kickoff))+'</td><td class="bp-m"><div>'+esc(x.match)+'</div><small>'+esc(x.league)+'</small></td><td class="bp-p"><div>'+esc(x.selection)+'</div><small>'+esc(x.market)+'</small></td><td data-l="Odds">'+(x.odds==null?'—':Number(x.odds).toFixed(2))+'</td><td data-l="P2U">'+pct(x.score)+'</td><td data-l="Result">'+badge(x.result)+'</td></tr>';}).join('')+
        '</tbody></table></details>';
    }).join('');
  }
  document.addEventListener('click',function(e){
    var b=e.target.closest&&e.target.closest('[data-copy]');if(!b)return;
    var c=b.getAttribute('data-copy'),done=function(){b.textContent='Copied ✓';b.classList.add('is-ok');setTimeout(function(){b.textContent='Copy';b.classList.remove('is-ok');},1600);};
    if(navigator.clipboard&&navigator.clipboard.writeText)navigator.clipboard.writeText(c).then(done,done);else done();
  });
  function init(d){
    data=d;var days=[];d.slips.forEach(function(s){(s.dates||[s.date]).forEach(function(x){if(days.indexOf(x)<0)days.push(x);});});days.sort();
    var t=stamp(new Date());state.day=days.indexOf(t)>=0?t:(days.filter(function(x){return x>=t;})[0]||days[days.length-1]);
    $('bp-day').innerHTML=days.map(function(x){return '<option value="'+x+'"'+(x===state.day?' selected':'')+'>'+x+(x===t?' (today)':'')+'</option>';}).join('');
    $('bp-day').onchange=function(){state.day=this.value;render();};
    var up=new Date(d.DATA_UPDATED);
    $('bankers-meta').textContent='Updated '+up.toLocaleString('en-GB',{timeZone:ZONE,day:'numeric',month:'short',hour:'2-digit',minute:'2-digit'})+' GMT';
    render();
  }
  fetch('picks.json',{cache:'no-cache'}).then(function(r){if(!r.ok)throw new Error(r.status);return r.json();}).then(init)
    .catch(function(e){$('bankers-meta').textContent='Could not load picks ('+e.message+').';});
})();
