/* Predict2U v322 — one-time 18+ age check + sitewide responsible-gambling notice. */
(function(){
  'use strict';
  var KEY='p2u-age-ok';
  var page=(location.pathname.split('/').pop()||'index.html').toLowerCase();
  var skipAge=document.body && document.body.getAttribute('data-p2u-skip-age')==='1'
    || /^(rg|responsible-gambling)\.html$/.test(page);

  function css(){
    if(document.getElementById('p2u-rg-css')) return;
    var st=document.createElement('style'); st.id='p2u-rg-css';
    st.textContent=
      '.p2u-rg-strip{position:relative;z-index:40;display:flex;flex-wrap:wrap;gap:8px 12px;align-items:center;justify-content:center;padding:8px 12px;background:#1a1408;border-top:1px solid #7a5a20;margin-top:24px;padding-bottom:calc(8px + env(safe-area-inset-bottom));color:#ffd99a;font:700 .78rem/1.3 system-ui,sans-serif;text-align:center}'+
      '.p2u-rg-strip b{color:#fff;letter-spacing:.04em}'+
      '.p2u-rg-strip a{color:#7ff0b8;font-weight:800;text-decoration:none;min-height:40px;display:inline-flex;align-items:center}'+
      '.p2u-rg-strip a:hover{text-decoration:underline}'+
      '.p2u-age{position:fixed;inset:0;z-index:10000;background:rgba(4,8,14,.92);display:flex;align-items:center;justify-content:center;padding:16px;backdrop-filter:blur(6px)}'+
      '.p2u-age-card{width:min(400px,100%);background:#0f1724;border:1px solid rgba(255,255,255,.12);border-radius:18px;padding:18px 16px;color:#e8eef7;box-shadow:0 20px 60px rgba(0,0,0,.55)}'+
      '.p2u-age-card h2{margin:0 0 8px;font-size:1.25rem;letter-spacing:-.02em}'+
      '.p2u-age-card p{margin:0 0 12px;color:#b4c2d6;font-size:.92rem;line-height:1.45}'+
      '.p2u-age-badge{display:inline-flex;align-items:center;justify-content:center;min-width:48px;height:32px;padding:0 10px;border-radius:10px;background:#3a2a12;color:#ffd99a;border:1px solid #7a5a20;font-weight:900;margin-bottom:10px}'+
      '.p2u-age-actions{display:grid;gap:8px;margin-top:4px}'+
      '.p2u-age-actions button{min-height:48px;border-radius:12px;border:0;font:800 .95rem/1 system-ui,sans-serif;cursor:pointer}'+
      '.p2u-age-yes{background:#22c55e;color:#052e22}'+
      '.p2u-age-no{background:#1f2a3a;color:#e8eef7;border:1px solid rgba(255,255,255,.1)!important}'+
      '.p2u-age-blocked{text-align:center}'+
      '.p2u-age-blocked a{color:#7ff0b8;font-weight:800}'+
      '@media(prefers-reduced-motion:reduce){.p2u-age{backdrop-filter:none}}';
    document.head.appendChild(st);
  }

  function strip(){
    if(document.querySelector('.p2u-rg-strip')) return;
    var el=document.createElement('div');
    el.className='p2u-rg-strip';
    el.setAttribute('role','note');
    el.innerHTML='<span><b>18+</b> only · Gamble responsibly</span><a href="rg.html">Ghana help &amp; self-exclusion →</a>';
    el.setAttribute('data-p2u-rg-footer','1');
    var foot=document.querySelector('footer, .footer, .site-footer');
    if(foot){ foot.appendChild(el); } else document.body.appendChild(el);
    // keep last in body if other scripts append later
    if(!foot) setTimeout(function(){ if(el.parentNode===document.body && el.nextElementSibling){ var n=el.nextElementSibling, moved=false; while(n){ if(n.tagName!=='SCRIPT' && getComputedStyle(n).position!=='fixed'){ moved=true; break;} n=n.nextElementSibling;} if(moved) document.body.appendChild(el);} },1500);
  }

  function ageGate(){
    if(skipAge) return;
    if(document.querySelector('.p2u-age')) return;
    try{ if(localStorage.getItem(KEY)==='1') return; }catch(e){}
    css();
    var wrap=document.createElement('div');
    wrap.className='p2u-age';
    wrap.setAttribute('role','dialog');
    wrap.setAttribute('aria-modal','true');
    wrap.setAttribute('aria-labelledby','p2u-age-title');
    wrap.innerHTML=
      '<div class="p2u-age-card">'+
        '<div class="p2u-age-badge" aria-hidden="true">18+</div>'+
        '<h2 id="p2u-age-title">Are you 18 or older?</h2>'+
        '<p>Predict2u shows football picks and booking codes. You must be an adult to use this site. Under-18s are not allowed.</p>'+
        '<div class="p2u-age-actions">'+
          '<button type="button" class="p2u-age-yes" data-age="yes">I am 18 or older</button>'+
          '<button type="button" class="p2u-age-no" data-age="no">I am under 18</button>'+
        '</div>'+
      '</div>';
    document.body.appendChild(wrap);
    document.documentElement.style.overflow='hidden';
    wrap.addEventListener('click', function(e){
      var btn=e.target.closest('[data-age]'); if(!btn) return;
      if(btn.getAttribute('data-age')==='yes'){
        try{ localStorage.setItem(KEY,'1'); }catch(err){}
        wrap.remove();
        document.documentElement.style.overflow='';
        return;
      }
      wrap.querySelector('.p2u-age-card').innerHTML=
        '<div class="p2u-age-blocked">'+
          '<div class="p2u-age-badge">18+</div>'+
          '<h2>Sorry — adults only</h2>'+
          '<p>This site is not available if you are under 18. If gambling is affecting someone you know, Ghana help is on our responsible gambling page.</p>'+
          '<p><a href="rg.html">Responsible gambling help →</a></p>'+
        '</div>';
    });
  }

  function boot(){
    css();
    strip();
    ageGate();
  }
  if(document.readyState==='loading') document.addEventListener('DOMContentLoaded', boot);
  else boot();
})();
