/* Predict2U v336 — first-party live visit beacon for the owner dashboard.
   Sends anonymous page/heartbeat/unlock events unless the visitor declined
   product analytics or sent a browser privacy signal (DNT / GPC).
   No email, payment data, raw IP or full user agent. */
(function(){
  'use strict';
  var RELAY='https://p2u-relay.onrender.com/live/hit',CONSENT='p2uAnalyticsConsent',SID='p2uLiveSid',VID='p2uLiveVid';
  var sent={},timer=null;
  function declined(){try{return localStorage.getItem(CONSENT)==='declined';}catch(e){return false;}}
  function blocked(){try{return navigator.globalPrivacyControl===true||navigator.doNotTrack==='1'||window.doNotTrack==='1'||declined();}catch(e){return true;}}
  function id(storage,key){try{var v=storage.getItem(key);if(!/^[A-Za-z0-9_-]{12,64}$/.test(v||'')){var a=new Uint8Array(18);if(window.crypto&&crypto.getRandomValues)crypto.getRandomValues(a);else for(var i=0;i<a.length;i++)a[i]=Math.random()*256;v=Array.prototype.map.call(a,function(n){return('0'+n.toString(16)).slice(-2);}).join('');storage.setItem(key,v);}return v;}catch(e){return '';}}
  function device(){var w=Math.max(document.documentElement.clientWidth||0,window.innerWidth||0);return w<600?'mobile':w<1025?'tablet':'desktop';}
  function send(type){
    if(blocked()||document.hidden&&type==='heartbeat')return;
    var sid=id(sessionStorage,SID),vid=id(localStorage,VID);if(!sid||!vid)return;
    var payload=JSON.stringify({type:type,sid:sid,vid:vid,page:location.pathname,referrer:document.referrer,device:device()});
    if(navigator.sendBeacon){try{if(navigator.sendBeacon(RELAY,new Blob([payload],{type:'text/plain;charset=UTF-8'})))return;}catch(e){}}
    try{fetch(RELAY,{method:'POST',headers:{'Content-Type':'text/plain;charset=UTF-8'},body:payload,keepalive:true,credentials:'omit',cache:'no-store'}).catch(function(){});}catch(e){}
  }
  function boot(){if(blocked()||sent.page)return;sent.page=true;send('page');clearInterval(timer);timer=setInterval(function(){send('heartbeat');},60000);}
  document.addEventListener('click',function(e){if(blocked())return;var el=e.target.closest&&e.target.closest('[data-p2u-pay],[data-p2u-info],[data-p2u-go],a[href*="unlock" i]');if(!el)return;var key=location.pathname+'|'+((el.getAttribute('data-p2u-pay')||el.getAttribute('data-p2u-info')||'link'))+'|'+Math.floor(Date.now()/1000);if(sent[key])return;sent[key]=true;send('unlock');},true);
  document.addEventListener('visibilitychange',function(){if(!document.hidden&&sent.page)send('heartbeat');});
  window.addEventListener('p2u:analytics-consent',function(e){if(e.detail&&e.detail.consent==='accepted'){sent={};boot();}else if(e.detail&&e.detail.consent==='declined'){clearInterval(timer);sent={};try{sessionStorage.removeItem(SID);localStorage.removeItem(VID);}catch(_){}}});
  window.addEventListener('storage',function(e){if(e.key===CONSENT){if(e.newValue==='declined'){clearInterval(timer);sent={};}else boot();}});
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot);else boot();
})();
