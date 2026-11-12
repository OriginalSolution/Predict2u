(function(){
  'use strict';
  // v293: lightweight pages skip match-tip add-ons they never use
  const LITE=/(?:bankers\.html$|\/high-odds\/?$)/i.test(location.pathname);
  // v257: load the foldable/mobile rescue layer before mounting navigation.
  if(!document.querySelector('link[data-p2u-mobile-zfold-v257]')){
    const rescue=document.createElement('link');
    rescue.rel='stylesheet';
    rescue.href='/mobile-zfold-v257.css';
    rescue.dataset.p2uMobileZfoldV257='true';
    document.head.appendChild(rescue);
  }
  if(!LITE&&!document.querySelector('link[data-p2u-context-flags-v280]')){
    const riskCss=document.createElement('link');
    riskCss.rel='stylesheet';
    riskCss.href='/pick-context-flags-v280.css';
    riskCss.dataset.p2uContextFlagsV280='true';
    document.head.appendChild(riskCss);
  }
  if(!LITE&&!document.querySelector('script[data-p2u-context-flags-v280]')){
    const riskJs=document.createElement('script');
    riskJs.src='/pick-context-flags-v280.js';
    riskJs.async=false;
    riskJs.dataset.p2uContextFlagsV280='true';
    document.head.appendChild(riskJs);
  }
  if(!LITE&&!document.querySelector('link[data-p2u-tip-clean-v281]')){
    const cleanCss=document.createElement('link');
    cleanCss.rel='stylesheet';
    cleanCss.href='/tip-explanation-clean-v281.css';
    cleanCss.dataset.p2uTipCleanV281='true';
    document.head.appendChild(cleanCss);
  }
  if(!LITE&&!document.querySelector('script[data-p2u-tip-clean-v281]')){
    const cleanJs=document.createElement('script');
    cleanJs.src='/tip-explanation-clean-v281.js';
    cleanJs.async=false;
    cleanJs.dataset.p2uTipCleanV281='true';
    document.head.appendChild(cleanJs);
  }
  if(!document.querySelector('link[data-p2u-ui-scale-v282]')){
    const scale=document.createElement('link');
    scale.rel='stylesheet';
    scale.href='/ui-scale-v282.css';
    scale.dataset.p2uUiScaleV282='true';
    document.head.appendChild(scale);
  }
  if(!document.querySelector('link[data-p2u-bcod-v300]')){
    const adCss=document.createElement('link');
    adCss.rel='stylesheet';
    adCss.href='/p2u-banker-pop-v300.css?v=301';
    adCss.dataset.p2uBcodV300='true';
    document.head.appendChild(adCss);
  }
  if(!/\/high-odds\/?$/i.test(location.pathname)&&!document.querySelector('script[data-p2u-bcod-v300]')){
    const adJs=document.createElement('script');
    adJs.src='/p2u-banker-pop-v300.js?v=362';
    adJs.async=true;
    adJs.dataset.p2uBcodV300='true';
    document.head.appendChild(adJs);
  }
  if(document.querySelector('.p2u-v245-nav-wrap')) return;

  document.querySelectorAll('.p2u-v227-nav-wrap,.p2u-v227-dock,.p2u-v227-more-backdrop,.p2u-phase2-nav-wrap,.p2u-phase2-dock,.p2u-mobile-app-nav').forEach(node=>node.remove());
  ['user-chip','user-name','user-sub','user-av'].forEach(id=>document.querySelectorAll('#'+id).forEach(node=>node.removeAttribute('id')));

  const page=(location.pathname.split('/').pop()||'index.html').toLowerCase();
  const active=/\/high-odds\/?$/i.test(location.pathname)?'high-odds':page===''?'index.html':page;
  const svg=(name)=>{
    const icons={
      overview:'<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="3" y="3" width="7" height="7" rx="2"/><rect x="14" y="3" width="7" height="7" rx="2"/><rect x="3" y="14" width="7" height="7" rx="2"/><rect x="14" y="14" width="7" height="7" rx="2"/></svg>',
      picks:'<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="4" y="5" width="16" height="15" rx="2"/><path d="M8 3v4M16 3v4M4 9h16M8 13h3M13 13h3M8 17h3"/></svg>',
      bankers:'<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 4h12l2 5-8 11L4 9z"/><path d="M8 9h8M10 4l2 5 2-5"/></svg>',
      fullboard:'<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="3" y="4" width="18" height="16" rx="2"/><path d="M3 9h18M9 9v11"/></svg>',
      engines:'<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="7" y="7" width="10" height="10" rx="2"/><path d="M9 1v3M15 1v3M9 20v3M15 20v3M20 9h3M20 15h3M1 9h3M1 15h3M10 10h4v4h-4z"/></svg>',
      news:'<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="4" y="4" width="16" height="16" rx="2"/><path d="M8 8h8M8 12h8M8 16h5"/></svg>',
      community:'<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="9" cy="8" r="3"/><path d="M3 20v-1a6 6 0 0 1 12 0v1M17 5a3 3 0 0 1 0 6M17 14a5 5 0 0 1 4 5v1"/></svg>',
      proof:'<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3l7 3v5c0 5-3 8-7 10-4-2-7-5-7-10V6z"/><path d="M9 12l2 2 4-5"/></svg>',
      score:'<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 19V9M10 19V5M16 19v-7M22 19V3"/></svg>',
      dna:'<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M7 3c6 4 4 14 10 18M17 3C11 7 13 17 7 21M8 7h8M7 12h10M8 17h8"/></svg>',
      rankings:'<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 20V10M10 20V4M16 20v-7M22 20V7"/><path d="M3 20h20"/></svg>',
      trust:'<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3l7 3v5c0 5-3 8-7 10-4-2-7-5-7-10V6z"/></svg>',
      account:'<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/></svg>',
      hot:'<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 2c1 4 5 6 5 11a5 5 0 0 1-10 0c0-3 2-4 2-7 2 1 3 3 3 5 1-2 1-5 0-9z"/></svg>',
      rocket:'<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M13 2 3 14h8l-1 8 11-13h-8V2Z"/></svg>',
      more:'<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="5" cy="12" r="1.4"/><circle cx="12" cy="12" r="1.4"/><circle cx="19" cy="12" r="1.4"/></svg>'
    };
    return icons[name]||icons.overview;
  };

  const desktopLinks=[
    {href:'/index.html',label:'Home',icon:'rankings'},
    {href:'/bankers.html',label:'Bankers',icon:'bankers'},
    {href:'/hot-picks.html',label:'🔥 Hot Picks',icon:'hot'},
    {href:'/news.html',label:'News',icon:'news'},
    {href:'/staked.html',label:'🎟 Staked',icon:'picks'}
  ];
  const mobileLinks=[
    {href:'/index.html',label:'Home',icon:'rankings'},
    {href:'/bankers.html',label:'Bankers',icon:'bankers'},
    {href:'/news.html',label:'News',icon:'news'}
  ];
  const moreLinks=[
    {href:'/account.html',label:'Account',icon:'account'},
    {href:'/rg.html',label:'18+ Responsible',icon:'trust'},
    {href:'/record.html',label:'Track record',icon:'proof'}
  ];
  const isActive=item=>{if(item.href==='/index.html')return active==='index.html'||active==='team-rankings.html'||active==='';return active===item.href.split('?')[0].replace(/^\//,'');};
  const primaryHrefs=new Set([...desktopLinks,...mobileLinks].map(item=>item.href));
  const moreActive=moreLinks.some(item=>isActive(item)&&!primaryHrefs.has(item.href));

  const nav=document.createElement('nav');
  nav.className='p2u-v245-nav-wrap';
  nav.setAttribute('aria-label','Primary navigation');
  nav.innerHTML=`
    <div class="p2u-v245-shell">
      <a class="p2u-v245-brand" href="/index.html" aria-label="Predict2U overview"><img src="/predict2u-logo-sm.webp" alt="Predict2U" width="118" height="47" decoding="async"/></a>
      <div class="p2u-v245-rail" role="navigation">
        ${desktopLinks.map(item=>`<a href="${item.href}" class="p2u-v245-link${isActive(item)?' is-active':''}"${isActive(item)?' aria-current="page"':''}>${svg(item.icon)}<span>${item.label}</span></a>`).join('')}
      </div>
      <div class="p2u-v245-side">
        <a id="user-chip" class="p2u-v245-user" href="account.html" aria-label="Account">
          <span class="p2u-v245-user-copy"><strong id="user-name">Sign in</strong><small id="user-sub">Account</small></span>
          <span id="user-av" class="p2u-v245-avatar">${svg('account')}</span>
        </a>
      </div>
    </div>`;
  document.body.prepend(nav);

  const dock=document.createElement('nav');
  dock.className='p2u-v245-dock';
  dock.setAttribute('aria-label','Mobile navigation');
  dock.innerHTML=mobileLinks.map(item=>`<a href="${item.href}" class="${isActive(item)?'is-active':''}">${svg(item.icon)}<span>${item.mobileLabel||item.label}</span></a>`).join('')+
    `<a href="/hot-picks.html" class="p2u-hot-tab${active==='hot-picks.html'?' is-active':''}"><span style="font-size:20px;line-height:1">🔥</span><span>Hot</span></a>`+
    `<a href="/staked.html" class="p2u-staked-tab${active==='staked.html'?' is-active':''}"><span style="font-size:20px;line-height:1">🎟</span><span>Staked</span></a>`+
    `<a href="/high-odds/" class="p2u-highodds-tab${active==='high-odds'?' is-active':''}"${active==='high-odds'?' aria-current="page"':''}>${svg('rocket')}<span>High</span></a>`;
  document.body.appendChild(dock);

  // Links that used to live under "More" now sit in a footer strip on every page
  const foot=document.createElement('footer');
  foot.className='p2u-more-footer';
  foot.setAttribute('aria-label','More links');
  foot.innerHTML=`<div class="p2u-more-footer-in">${moreLinks.map(item=>`<a href="${item.href}" class="${isActive(item)?'is-active':''}">${svg(item.icon)}<span>${item.label}</span></a>`).join('')}</div>`;
  const st=document.createElement('style');
  st.textContent='@media(max-width:420px){.p2u-v245-dock{gap:2px!important;padding:5px!important}.p2u-v245-dock a,.p2u-v245-dock button{padding-inline:0!important;font-size:9px!important;letter-spacing:-.1px!important}.p2u-v245-dock a span:last-child,.p2u-v245-dock button span:last-child{font-size:9px!important;line-height:1.1!important;overflow:visible!important;text-overflow:clip!important;max-width:none!important}}.p2u-more-footer{margin:28px auto 0;padding:18px 14px 96px;max-width:1200px;border-top:1px solid rgba(255,255,255,.14)}.p2u-more-footer-in{display:flex;flex-wrap:wrap;gap:8px;justify-content:center}.p2u-more-footer a{display:inline-flex;align-items:center;gap:6px;padding:8px 12px;border-radius:999px;background:rgba(255,255,255,.08);color:#f4f6fb;font:600 13px/1.2 system-ui,sans-serif;text-decoration:none}.p2u-more-footer a:hover,.p2u-more-footer a.is-active{background:#ff6a00;color:#111}.p2u-more-footer svg{width:15px;height:15px;fill:none;stroke:currentColor;stroke-width:2}.p2u-v245-dock .p2u-hot-tab.is-active,.p2u-v245-dock .p2u-hot-tab{color:#ff8a1f}.p2u-rg-foot{margin:12px 0 0;text-align:center;color:#9fb0c6;font:600 12px/1.4 system-ui,sans-serif}.p2u-rg-foot a{color:#7ff0b8;font-weight:800;text-decoration:none}';
  document.head.appendChild(st);
  (document.readyState==='loading')?document.addEventListener('DOMContentLoaded',()=>document.body.appendChild(foot)):document.body.appendChild(foot);

  document.body.classList.add('p2u-v227-ready','p2u-v245-ready','p2u-v245-page-'+active.replace('.html','').replace(/[^a-z0-9-]/g,''));
  document.documentElement.classList.add('p2u-v227-html','p2u-v245-html');

  
  // Responsible gambling: 18+ strip + one-time age check
  if(!document.querySelector('script[data-p2u-rg-v322]')){
    const rg=document.createElement('script');
    rg.src='/p2u-rg-v322.js?v=322';
    rg.defer=true;
    rg.dataset.p2uRgV318='true';
    document.head.appendChild(rg);
  }
requestAnimationFrame(()=>{
    const current=nav.querySelector('.p2u-v245-rail .is-active');
    const rail=nav.querySelector('.p2u-v245-rail');
    if(current&&rail)rail.scrollLeft=Math.max(0,current.offsetLeft-(rail.clientWidth-current.offsetWidth)/2);
  });
})();
