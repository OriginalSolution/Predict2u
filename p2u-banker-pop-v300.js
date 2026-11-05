/* Predict2U v300 - Banker code of the day */
(function(){
  'use strict';
  var KEY='p2u-bcod-seen';
  var BOOKS={
    msport:['MSport','book-msport.webp','https://www.msport.com/gh/sports/share?shareCode={c}'],
    betika:['Betika','book-betika.webp','https://betika.com/en-gh/share/{c}'],
    footballcom:['football.com','book-footballcom.webp','https://www.football.com/gh/?shareCode={c}'],
    betpawa:['Betpawa','book-betpawa.webp','https://www.betpawa.com.gh/#{c}'],
    onexbet:['1xBet','book-1xbet.webp','https://1xbet.com/en/?coupon={c}'],
    betway:['Betway','book-betway.webp',null],'22bet':['22Bet','book-22bet.webp',null]
  };
  function esc(s){return String(s==null?'':s).replace(/[&<>"']/g,function(c){return{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c];});}
  function pick(d){
    var sl=(d&&d.slips||[]).filter(function(s){return s.codes&&s.codes.sportybet&&Number(s.totalOdds)>=25;});
    if(!sl.length)return null;
    sl.sort(function(a,b){var am=/^main/i.test(a.name)?0:1,bm=/^main/i.test(b.name)?0:1;return am-bm||a.totalOdds-b.totalOdds;});
    return sl[0];
  }
  function show(d){
    var s=pick(d);if(!s)return;
    var day=d.date||'';
    try{if(localStorage.getItem(KEY)===day)return;}catch(e){}
    var code=s.codes.sportybet,link='https://www.sportybet.com/gh/?shareCode='+encodeURIComponent(code);
    var n=(s.bookPicks&&s.bookPicks.sportybet)||(s.legs||[]).length;
    var chips=Object.keys(s.codes).filter(function(k){return k!=='sportybet'&&s.codes[k]&&BOOKS[k];}).map(function(k){
      var b=BOOKS[k],c=esc(s.codes[k]),inner='<img src="'+b[1]+'" alt="" width="20" height="20"><span>'+b[0]+'</span><b>'+c+'</b>';
      return b[2]?'<a class="bcod-chip" href="'+b[2].replace('{c}',encodeURIComponent(s.codes[k]))+'" target="_blank" rel="noopener" aria-label="'+b[0]+' code '+c+'">'+inner+'</a>':'<span class="bcod-chip">'+inner+'</span>';
    }).join('');
    var prev=document.activeElement;
    var wrap=document.createElement('div');
    wrap.className='bcod-back';
    wrap.innerHTML='<div class="bcod" role="dialog" aria-modal="true" aria-labelledby="bcod-t">'+
      '<button class="bcod-x" type="button" aria-label="Close">&times;</button>'+
      '<p class="bcod-kick">Predict2U</p><h2 id="bcod-t">Banker code of the day</h2>'+
      '<div class="bcod-main"><img src="book-sportybet.webp" alt="SportyBet" width="36" height="36"><div><small>SportyBet code</small><strong class="bcod-code">'+esc(code)+'</strong></div></div>'+
      '<div class="bcod-stats"><div><small>Total odds</small><b>'+Number(s.totalOdds).toFixed(2)+'</b></div><div><small>Picks</small><b>'+n+'</b></div></div>'+
      '<div class="bcod-act"><button type="button" class="bcod-copy">Copy code</button><a class="bcod-open" href="'+link+'" target="_blank" rel="noopener">Open on SportyBet</a></div>'+
      (chips?'<p class="bcod-also">Also booked on</p><div class="bcod-chips">'+chips+'</div>':'')+
      (window.P2UWA?'<div class="p2u-wa-row" style="justify-content:center">'+P2UWA.button(s,'p2u-wa')+'</div>':'')+
      '<a class="bcod-all" href="bankers.html">See all codes</a><p class="bcod-18">18+ | Bet responsibly</p></div>';
    document.body.appendChild(wrap);if(window.P2UWA)P2UWA.css();
    var box=wrap.firstChild;
    function close(){try{localStorage.setItem(KEY,day);}catch(e){}wrap.remove();document.removeEventListener('keydown',key);if(prev&&prev.focus)prev.focus();}
    function key(e){
      if(e.key==='Escape'){close();return;}
      if(e.key==='Tab'){var f=box.querySelectorAll('a,button');var a=f[0],z=f[f.length-1];
        if(e.shiftKey&&document.activeElement===a){e.preventDefault();z.focus();}else if(!e.shiftKey&&document.activeElement===z){e.preventDefault();a.focus();}}
    }
    document.addEventListener('keydown',key);
    box.querySelector('.bcod-x').onclick=close;
    wrap.addEventListener('click',function(e){if(e.target===wrap)close();});
    box.querySelector('.bcod-copy').onclick=function(){var b=this;
      var done=function(){b.textContent='Copied!';setTimeout(function(){b.textContent='Copy code';},1500);};
      if(navigator.clipboard)navigator.clipboard.writeText(code).then(done,done);else done();};
    box.querySelector('.bcod-x').focus();
  }
  function go(){fetch('home-picks.json?t='+Date.now(),{cache:'no-store'}).then(function(r){return r.ok?r.json():null;}).then(function(d){if(d)setTimeout(function(){show(d);},900);}).catch(function(){});}
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',go);else go();
})();
