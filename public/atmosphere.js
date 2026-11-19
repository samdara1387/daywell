/* Money Theory Atmosphere. Local graphics only; no financial records are changed here. */
(() => {
  'use strict';
  const body = document.body;
  const reduced = matchMedia('(prefers-reduced-motion: reduce)');
  const read = (key, fallback) => { try { return localStorage.getItem(key) || fallback; } catch { return fallback; } };
  const remember = (key, value) => { try { localStorage.setItem(key, value); } catch {} };
  let preference = read('daywell-motion', 'on');
  let scene = read('daywell-atmosphere', 'aurora');
  if (!['aurora', 'ember', 'tide'].includes(scene)) scene = 'aurora';
  let observer, animations = [], lastPage = '', mounted = false, lastData, lastScope = '';
  const moving = () => preference === 'on' && !reduced.matches;
  body.dataset.scene = scene;

  function syncControls() {
    body.dataset.motion = moving() ? 'on' : 'off';
    const button = document.getElementById('motion-toggle');
    if (button) {
      button.innerHTML = '<span class="motion-waves" aria-hidden="true"><i></i><i></i><i></i></span><span>' + (reduced.matches ? 'Reduced motion' : moving() ? 'Motion on' : 'Motion paused') + '</span>';
      button.setAttribute('aria-label', reduced.matches ? 'Visual effects paused by your system preference' : moving() ? 'Pause visual effects' : 'Resume visual effects');
      button.setAttribute('aria-pressed', String(moving()));
      button.disabled = reduced.matches;
    }
    document.querySelectorAll('[data-atmosphere]').forEach(button => button.setAttribute('aria-pressed', String(button.dataset.atmosphere === scene)));
  }

  function mount() {
    observer?.disconnect();animations.forEach(a=>a.cancel());animations=[];
    const main=document.getElementById('main');if(!main)return;
    const route=location.hash||'#overview',changed=lastPage!==route;lastPage=route;
    main.dataset.route=route.slice(1);
    const scope=route+'|'+selected+'|'+period, chartChanged=changed||lastData!==state||lastScope!==scope;lastData=state;lastScope=scope;
    syncControls();
    if(changed){
      const nav=document.getElementById('nav'),active=nav?.querySelector('[aria-current="page"]');
      if(nav&&active){const left=active.offsetLeft-nav.offsetLeft;nav.scrollTo({left:Math.max(0,left-(nav.clientWidth-active.offsetWidth)/2),behavior:moving()?'smooth':'instant'});}
      if(moving())animations.push(main.animate([{opacity:.45,transform:'translateY(7px)'},{opacity:1,transform:'translateY(0)'}],{duration:280,easing:'cubic-bezier(.2,.7,.2,1)'}));
    }
    if(moving()&&chartChanged){
      observer=new IntersectionObserver(entries=>entries.forEach(entry=>{if(!entry.isIntersecting)return;const el=entry.target;const vertical=el.matches('.week-bar,.chart .bar,.bill-week-track>i');const amount=el.classList.contains('stat-value');const frames=amount?[{opacity:.5,transform:'translateY(4px)'},{opacity:1,transform:'translateY(0)'}]:[{transform:vertical?'scaleY(0)':'scaleX(0)',opacity:.4},{transform:vertical?'scaleY(1)':'scaleX(1)',opacity:1}];el.style.transformOrigin=vertical?'bottom':'left';animations.push(el.animate(frames,{duration:amount?340:620,easing:'cubic-bezier(.2,.7,.2,1)'}));observer.unobserve(el);}),{threshold:.15});
      main.querySelectorAll('.week-bar,.progress-track>div,.chart .bar,.bill-week-track>i,.stat-value').forEach(el=>observer.observe(el));
    }

    mounted=true;
  }

  function toggleMotion(){preference=moving()?'off':'on';remember('daywell-motion',preference);syncControls();if(!moving()){animations.forEach(a=>a.cancel());observer?.disconnect();document.querySelectorAll('.effect-spark,.button-ripple').forEach(el=>el.remove());}document.dispatchEvent(new Event('daywell:visual-change'));}
  document.getElementById('motion-toggle')?.addEventListener('click',toggleMotion);
  reduced.addEventListener('change',()=>{syncControls();if(mounted)mount();});
  document.addEventListener('visibilitychange',()=>{body.classList.toggle('effects-hidden',document.hidden);});
  document.addEventListener('click',event=>{
    const atmosphere=event.target.closest('[data-atmosphere]');
    if(atmosphere){scene=atmosphere.dataset.atmosphere;body.dataset.scene=scene;remember('daywell-atmosphere',scene);syncControls();document.dispatchEvent(new Event('daywell:visual-change'));}
    const button=event.target.closest('.primary,.secondary,.hero-primary');
    if(button&&!button.disabled&&moving()){
      const rect=button.getBoundingClientRect(),ripple=document.createElement('span');ripple.className='button-ripple';ripple.setAttribute('aria-hidden','true');ripple.style.left=(event.detail?event.clientX-rect.left:rect.width/2)+'px';ripple.style.top=(event.detail?event.clientY-rect.top:rect.height/2)+'px';button.append(ripple);ripple.addEventListener('animationend',()=>ripple.remove(),{once:true});setTimeout(()=>ripple.remove(),850);
    }
  });
  let hoverFrame=0;
  document.addEventListener('pointermove',event=>{
    if(!moving()||event.pointerType==='touch'||hoverFrame)return;
    const card=event.target.closest('.card,.stat,.goal-mini');if(!card)return;
    const x=event.clientX,y=event.clientY;hoverFrame=requestAnimationFrame(()=>{hoverFrame=0;if(!card.isConnected)return;const rect=card.getBoundingClientRect();card.style.setProperty('--spot-x',(x-rect.left)+'px');card.style.setProperty('--spot-y',(y-rect.top)+'px');});
  },{passive:true});
  function celebrate(message){
    if(!moving()||!(/Savings added|Task complete/.test(message)))return;
    const rect=document.getElementById('toast').getBoundingClientRect();
    for(let i=0;i<16;i++){const spark=document.createElement('i');spark.className='effect-spark';spark.setAttribute('aria-hidden','true');const a=i/16*Math.PI*2; spark.style.cssText=`left:${rect.left+rect.width/2}px;top:${rect.top}px;--dx:${Math.cos(a)*(35+Math.random()*70)}px;--dy:${-45-Math.random()*95}px;--spin:${Math.random()*360}deg;--delay:${i*12}ms`;body.append(spark);setTimeout(()=>spark.remove(),1300);}
  }
  window.DaywellVisual={mount,celebrate};syncControls();
})();
