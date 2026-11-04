(function(){
  'use strict';
  // v293: lightweight pages skip match-tip add-ons they never use
  const LITE=/bankers\.html$/i.test(location.pathname);
  // v257: load the foldable/mobile rescue layer before mounting navigation.
  if(!document.querySelector('link[data-p2u-mobile-zfold-v257]')){
    const rescue=document.createElement('link');
    rescue.rel='stylesheet';
    rescue.href='mobile-zfold-v257.css';
    rescue.dataset.p2uMobileZfoldV257='true';
    document.head.appendChild(rescue);
  }
  if(!LITE&&!document.querySelector('link[data-p2u-context-flags-v280]')){
    const riskCss=document.createElement('link');
    riskCss.rel='stylesheet';
    riskCss.href='pick-context-flags-v280.css';
    riskCss.dataset.p2uContextFlagsV280='true';
    document.head.appendChild(riskCss);
  }
  if(!LITE&&!document.querySelector('script[data-p2u-context-flags-v280]')){
    const riskJs=document.createElement('script');
    riskJs.src='pick-context-flags-v280.js';
    riskJs.async=false;
    riskJs.dataset.p2uContextFlagsV280='true';
    document.head.appendChild(riskJs);
  }
  if(!LITE&&!document.querySelector('link[data-p2u-tip-clean-v281]')){
    const cleanCss=document.createElement('link');
    cleanCss.rel='stylesheet';
    cleanCss.href='tip-explanation-clean-v281.css';
    cleanCss.dataset.p2uTipCleanV281='true';
    document.head.appendChild(cleanCss);
  }
  if(!LITE&&!document.querySelector('script[data-p2u-tip-clean-v281]')){
    const cleanJs=document.createElement('script');
    cleanJs.src='tip-explanation-clean-v281.js';
    cleanJs.async=false;
    cleanJs.dataset.p2uTipCleanV281='true';
    document.head.appendChild(cleanJs);
  }
  if(!document.querySelector('link[data-p2u-ui-scale-v282]')){
    const scale=document.createElement('link');
    scale.rel='stylesheet';
    scale.href='ui-scale-v282.css';
    scale.dataset.p2uUiScaleV282='true';
    document.head.appendChild(scale);
  }
  if(!document.querySelector('link[data-p2u-s2p-ad-v288]')){
    const adCss=document.createElement('link');
    adCss.rel='stylesheet';
    adCss.href='p2u-s2p-ad-v288.css?v=289';
    adCss.dataset.p2uS2pAdV288='true';
    document.head.appendChild(adCss);
  }
  if(!document.querySelector('script[data-p2u-s2p-ad-v288]')){
    const adJs=document.createElement('script');
    adJs.src='p2u-s2p-ad-v288.js?v=289';
    adJs.async=true;
    adJs.dataset.p2uS2pAdV288='true';
    document.head.appendChild(adJs);
  }
  if(document.querySelector('.p2u-v245-nav-wrap')) return;

  document.querySelectorAll('.p2u-v227-nav-wrap,.p2u-v227-dock,.p2u-v227-more-backdrop,.p2u-phase2-nav-wrap,.p2u-phase2-dock,.p2u-mobile-app-nav').forEach(node=>node.remove());
  ['user-chip','user-name','user-sub','user-av'].forEach(id=>document.querySelectorAll('#'+id).forEach(node=>node.removeAttribute('id')));

  const page=(location.pathname.split('/').pop()||'index.html').toLowerCase();
  const active=page===''?'index.html':page;
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
      more:'<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="5" cy="12" r="1.4"/><circle cx="12" cy="12" r="1.4"/><circle cx="19" cy="12" r="1.4"/></svg>'
    };
    return icons[name]||icons.overview;
  };

  const desktopLinks=[
    {href:'index.html',label:'Home',icon:'rankings'},
    {href:'bankers.html',label:'Bankers',icon:'bankers'},
    {href:'news.html',label:'News',icon:'news'},
    {href:'community.html',label:'Community',icon:'community'},
    {href:'all-engines.html',label:'Engines',icon:'engines'},
    {href:'proof.html',label:'Proof',icon:'proof'}
  ];
  const mobileLinks=[
    {href:'index.html',label:'Home',icon:'rankings'},
    {href:'bankers.html',label:'Bankers',icon:'bankers'},
    {href:'news.html',label:'News',icon:'news'},
    {href:'community.html',label:'Community',icon:'community'}
  ];
  const moreLinks=[
    {href:'all-engines.html',label:'Engines',icon:'engines'},
    {href:'board.html',label:'Board',icon:'picks'},
    {href:'proof.html',label:'Proof',icon:'proof'},
    {href:'engines.html',label:'Full Board',icon:'fullboard'},
    {href:'scorecards.html',label:'Scorecards',icon:'score'},
    {href:'league-dna.html',label:'League DNA',icon:'dna'},
    {href:'trust.html',label:'Trust Center',icon:'trust'},
    {href:'account.html',label:'Account',icon:'account'},
    {href:'index.html?tour=1',label:'Replay walkthrough',icon:'overview'}
  ];
  const isActive=item=>{if(item.href==='index.html')return active==='index.html'||active==='team-rankings.html'||active==='';return active===item.href.split('?')[0];};
  const primaryHrefs=new Set([...desktopLinks,...mobileLinks].map(item=>item.href));
  const moreActive=moreLinks.some(item=>isActive(item)&&!primaryHrefs.has(item.href));

  const nav=document.createElement('nav');
  nav.className='p2u-v245-nav-wrap';
  nav.setAttribute('aria-label','Primary navigation');
  nav.innerHTML=`
    <div class="p2u-v245-shell">
      <a class="p2u-v245-brand" href="index.html" aria-label="Predict2U overview"><img src="predict2u-logo-sm.webp" alt="Predict2U" width="118" height="47" decoding="async"/></a>
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
    `<button type="button" id="p2u-v245-more" class="${moreActive?'is-active':''}" aria-haspopup="dialog" aria-controls="p2u-v245-more-panel" aria-expanded="false">${svg('more')}<span>More</span></button>`;
  document.body.appendChild(dock);

  const backdrop=document.createElement('div');
  backdrop.className='p2u-v245-more-backdrop';
  backdrop.id='p2u-v245-more-panel';
  backdrop.setAttribute('aria-hidden','true');
  backdrop.innerHTML=`<section class="p2u-v245-more-panel" role="dialog" aria-modal="true" aria-label="More navigation">
    <div class="p2u-v245-more-head"><div><strong>More</strong><small>Board, records and account tools</small></div><button type="button" class="p2u-v245-more-close" aria-label="Close">×</button></div>
    <div class="p2u-v245-more-grid">${moreLinks.map(item=>`<a href="${item.href}" class="${isActive(item)?'is-active':''}">${svg(item.icon)}<span>${item.label}</span></a>`).join('')}</div>
  </section>`;
  document.body.appendChild(backdrop);

  const moreButton=dock.querySelector('#p2u-v245-more');
  const close=()=>{backdrop.classList.remove('is-open');backdrop.setAttribute('aria-hidden','true');moreButton.setAttribute('aria-expanded','false');document.body.classList.remove('p2u-v245-menu-open');};
  const open=()=>{backdrop.classList.add('is-open');backdrop.setAttribute('aria-hidden','false');moreButton.setAttribute('aria-expanded','true');document.body.classList.add('p2u-v245-menu-open');
};
  moreButton.addEventListener('click',()=>backdrop.classList.contains('is-open')?close():open());
  backdrop.addEventListener('click',event=>{if(event.target===backdrop||event.target.closest('.p2u-v245-more-close'))close();});
  document.addEventListener('keydown',event=>{if(event.key==='Escape')close();});

  document.body.classList.add('p2u-v227-ready','p2u-v245-ready','p2u-v245-page-'+active.replace('.html','').replace(/[^a-z0-9-]/g,''));
  document.documentElement.classList.add('p2u-v227-html','p2u-v245-html');

  requestAnimationFrame(()=>{
    const current=nav.querySelector('.p2u-v245-rail .is-active');
    const rail=nav.querySelector('.p2u-v245-rail');
    if(current&&rail)rail.scrollLeft=Math.max(0,current.offsetLeft-(rail.clientWidth-current.offsetWidth)/2);
  });
})();
