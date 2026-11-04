/* Predict2U Staked codes page */
(function(){
  var S=window.P2UStaked,root=document.getElementById('staked');if(!S||!root)return;
  var B=S.BOOKS,LIVE={sportybet:'www.sportybet.com',footballcom:'www.football.com'};
  var feed={},live={},timer=null,openSet={};
  var esc=function(s){return String(s==null?'':s).replace(/[&<>"]/g,function(c){return{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]})};
  var PROX=[function(u){return u},function(u){return 'https://api.allorigins.win/raw?url='+encodeURIComponent(u)},function(u){return 'https://api.codetabs.com/v1/proxy/?quest='+encodeURIComponent(u)}];
  var good=+(sessionStorage.getItem('p2u_st_px')||0);
  function tryFetch(u){var order=[good].concat([0,1,2].filter(function(i){return i!==good}));var i=0;
    function nx(){if(i>=order.length)return Promise.reject('all');var k=order[i++],c=new AbortController(),t=setTimeout(function(){c.abort()},9000);
      return fetch(PROX[k](u),{signal:c.signal}).then(function(r){clearTimeout(t);if(!r.ok)throw 0;return r.json()}).then(function(j){if(!j||!j.data)throw 0;good=k;sessionStorage.setItem('p2u_st_px',k);return j}).catch(nx)}
    return nx()}
  function side(d,H,A){return d.replace(/\bHome\b/g,H).replace(/\bAway\b/g,A)}
  function lookup(x){var h=LIVE[x.book];if(!h)return Promise.resolve(null);
    return tryFetch('https://'+h+'/api/gh/orders/share/'+encodeURIComponent(x.code)).then(function(j){return (j.data.outcomes||[]).map(function(o){var m=o.markets[0],oc=m.outcomes[0],H=o.homeTeamName,A=o.awayTeamName;return{eventId:o.eventId,match:H+' v '+A,selection:side(oc.desc,H,A),market:m.desc,odds:+oc.odds||null,kickoff:o.estimateStartTime,score:o.setScore,status:o.matchStatus,played:o.playedSeconds,league:((o.sport||{}).category||{}).tournament&&o.sport.category.tournament.name}})}).catch(function(){return null})}
  function settle(l){if(l.result==='won'||l.result==='lost'||l.result==='void')return l.result;if(l.status!=='Ended'||!l.score)return isLive(l)?'live':'pending';
    var p=l.score.split(':').map(Number),h=p[0],a=p[1],s=l.selection.trim(),m=s.match(/^(Over|Under) (\d+(?:\.\d+)?)$/);
    if(m)return((h+a)>+m[2])===(m[1]==='Over')?'won':'lost';var T=l.match.split(' v '),out={1:h>a,X:h===a,2:a>h};
    var ps=s.split(' or ').map(function(x){x=x.trim();return x===T[0]?'1':x===T[1]?'2':x.toLowerCase()==='draw'?'X':null});
    if(ps.every(Boolean))return ps.some(function(q){return out[q]})?'won':'lost';
    if(/^(gg|yes)$/i.test(s))return h&&a?'won':'lost';if(/^(ng|no)$/i.test(s))return !(h&&a)?'won':'lost';return 'pending'}
  function isLive(l){return l.status&&l.status!=='Not start'&&l.status!=='Ended'&&l.status!=='Cancelled'}
  function legsFor(x){var k=x.book+':'+x.code,f=(feed[k]||{}).legs||[],L=live[k];if(!L)return f.map(function(l){var c=Object.assign({},l);c.result=settle(c);return c});
    var byE={};f.forEach(function(l){byE[l.eventId]=l});var seen={};var out=L.map(function(l){seen[l.eventId]=1;var c=Object.assign({},byE[l.eventId]||{},l);if(byE[l.eventId]&&byE[l.eventId].status==='Ended'&&!(l.status==='Ended')){c.status='Ended';c.score=byE[l.eventId].score}c.result=settle(c);return c});
    f.forEach(function(l){if(!seen[l.eventId]){var c=Object.assign({},l);c.result=settle(c);out.push(c)}});return out}
  function overall(legs){var r=legs.map(function(l){return l.result});if(!r.length)return'unknown';if(r.indexOf('lost')>=0)return'lost';if(r.every(function(x){return x==='won'||x==='void'}))return'won';return r.indexOf('live')>=0?'live':'pending'}
  function ko(t){if(!t)return'';var d=new Date(+t);return d.toLocaleDateString('en-GB',{weekday:'short',day:'numeric',month:'short',timeZone:'Africa/Accra'})+' '+d.toLocaleTimeString('en-GB',{hour:'2-digit',minute:'2-digit',timeZone:'Africa/Accra'})+' GMT'}
  var LBL={won:'WON',lost:'LOST',pending:'PENDING',live:'LIVE',unknown:'LOOKING UP'};
  function render(){var l=S.load(),anyLive=false,changed=false;
    var h='<h1>🎟 Staked codes</h1><p class="st-sub">Add the booking codes you staked. We track every leg, show live scores and tell you when a code wins or busts. Codes you click or copy on Predict2U are added automatically.</p>'+
    '<form class="st-form" id="stF"><input id="stC" placeholder="Booking code, e.g. 8S4XPK" autocomplete="off" required maxlength="12" aria-label="Booking code"><select id="stB" aria-label="Bookmaker">'+Object.keys(B).filter(function(b){return b!=='1xbet'}).map(function(b){return'<option value="'+b+'">'+B[b]+'</option>'}).join('')+'</select><input id="stS" type="number" min="0" step="0.01" inputmode="decimal" placeholder="Stake (GH₵, optional)" aria-label="Stake"><button class="st-btn">Track code</button></form>'+
    '<p class="st-note">Live lookup works for any SportyBet and football.com code. MSport, Betika and Betpawa codes are tracked when they are Predict2U codes; live lookup for other codes on those sites is coming soon.</p>'+
    '<div class="st-tools"><button class="st-btn ghost sm" id="stN">🔔 '+(window.Notification?(Notification.permission==='granted'?'Alerts on':'Turn on win/loss alerts'):'Alerts not supported')+'</button><button class="st-btn ghost sm" id="stR">↻ Refresh</button><span id="stU"></span></div>';
    if(!l.length)h+='<div class="st-empty">No staked codes yet. Add one above, or tap any code on the site to track it.</div>';
    l.forEach(function(x,i){var k=x.book+':'+x.code,legs=legsFor(x),st=overall(legs),f=feed[k]||{};
      if(st==='live'||legs.some(function(q){return q.result==='live'}))anyLive=true;
      if((st==='won'||st==='lost')&&x.last!==st){x.last=st;if(x.notified!==st){x.notified=st;S.notifyChange(k,st,x)}changed=true}
      var odds=legs.reduce(function(a,q){return a*(+q.odds||1)},1);if(!legs.length)odds=f.odds||0;var hit=legs.filter(function(q){return q.result==='won'}).length;
      var ret=x.stake?(x.stake*odds):null;
      h+='<details class="st-card'+(x.changed?' st-changed':'')+'" data-k="'+esc(k)+'"'+(openSet[k]?' open':'')+'><summary><span class="st-chip '+esc(x.book)+'">'+esc(B[x.book])+'</span><span class="st-code">'+esc(x.code)+'</span><span class="st-meta">'+(legs.length?hit+'/'+legs.length+' won · ':'')+(odds?'odds '+odds.toFixed(2):'')+(f.name?' · '+esc(f.name):'')+'</span><span class="st-stat '+st+'">'+LBL[st]+'</span></summary><div class="st-body">'+
      '<div class="st-sum"><span>Total odds <b>'+(odds?odds.toFixed(2):'—')+'</b></span><span>Stake <b>'+(x.stake?'GH₵ '+(+x.stake).toFixed(2):'—')+'</b></span><span>Potential return <b>'+(ret?'GH₵ '+ret.toFixed(2):'—')+'</b></span></div>'+
      (legs.length?'<table class="st-legs"><thead><tr><th>Match</th><th>Pick</th><th>Odds</th><th class="hide-m">Kickoff</th><th class="hide-m">Score</th><th>Result</th></tr></thead><tbody>'+legs.map(function(q){return'<tr><td>'+esc(q.match)+'<div class="st-meta show-m">'+(q.score?'Score '+esc(q.score)+(isLive(q)?' · '+esc(q.status):''):ko(q.kickoff))+'</div>'+(q.league?'<div class="st-meta">'+esc(q.league)+'</div>':'')+'</td><td>'+esc(q.selection)+'</td><td>'+(q.odds?(+q.odds).toFixed(2):'')+'</td><td class="hide-m">'+ko(q.kickoff)+'</td><td class="hide-m">'+esc(q.score||'–')+(isLive(q)?'<div class="st-meta">'+esc(q.status)+'</div>':'')+'</td><td><span class="st-r '+q.result+'">'+LBL[q.result]+'</span></td></tr>'}).join('')+'</tbody></table>':'<p class="st-note">'+(LIVE[x.book]?'Looking up this code… if it stays empty, check the code is correct and still open.':'This is not a Predict2U '+esc(B[x.book])+' code, so we can\'t read its picks yet (live lookup for '+esc(B[x.book])+' is coming soon).')+'</p>')+
      '<div class="st-tools"><label class="st-meta">Stake GH₵ <input data-stake="'+i+'" type="number" min="0" step="0.01" value="'+(x.stake||'')+'" style="width:110px;min-height:34px;border-radius:8px;border:1px solid #33557a;background:#07111d;color:#fff;padding:0 8px"></label><button class="st-btn ghost sm" data-rm="'+i+'">Remove</button></div></div></details>'});
    root.innerHTML=h;if(changed)S.save(l);
    document.getElementById('stU').textContent=Object.keys(feed).length?'Updated '+new Date().toLocaleTimeString('en-GB',{hour:'2-digit',minute:'2-digit',timeZone:'Africa/Accra'})+' GMT'+(anyLive?' · live, refreshing every 60s':''):'';
    clearTimeout(timer);timer=setTimeout(refresh,anyLive?60000:300000);}
  root.addEventListener('submit',function(e){e.preventDefault();var c=document.getElementById('stC').value.trim().toUpperCase(),b=document.getElementById('stB').value,s=parseFloat(document.getElementById('stS').value);
    if(b==='betika')c=document.getElementById('stC').value.trim();
    if(!S.add(c,b,'manual',true)){S.toast('That code is already tracked or is not valid');return}if(s>0){var l=S.load();l[0].stake=s;S.save(l)}S.toast('🎟 Tracking '+B[b]+' '+c);openSet[b+':'+c]=1;refresh()});
  root.addEventListener('click',function(e){var t=e.target;if(t.dataset.rm!=null){var l=S.load();var x=l.splice(+t.dataset.rm,1)[0];S.save(l);S.toast('Removed '+x.code);render()}
    else if(t.id==='stN'&&window.Notification){Notification.requestPermission().then(function(p){S.toast(p==='granted'?'🔔 Win/loss alerts are on':'Alerts were blocked in your browser');render()})}
    else if(t.id==='stR')refresh()});
  root.addEventListener('change',function(e){var t=e.target;if(t.dataset.stake!=null){var l=S.load();l[+t.dataset.stake].stake=parseFloat(t.value)||null;S.save(l);render()}});
  root.addEventListener('toggle',function(e){var d=e.target;if(d.dataset&&d.dataset.k){openSet[d.dataset.k]=d.open}},true);
  function refresh(){var l=S.load();
    var pf=fetch('staked-codes.json?t='+Math.floor(Date.now()/6e4)).then(function(r){return r.json()}).then(function(d){feed=d.codes||{}}).catch(function(){});
    var pl=Promise.all(l.filter(function(x){return LIVE[x.book]}).map(function(x){var k=x.book+':'+x.code;return lookup(x).then(function(L){if(L&&L.length)live[k]=L})}));
    render();return Promise.all([pf,pl]).then(render)}
  refresh();
  setTimeout(function(){var l=S.load(),c=false;l.forEach(function(x){if(x.changed){x.changed=false;c=true}});if(c)S.save(l)},4000);
})();
