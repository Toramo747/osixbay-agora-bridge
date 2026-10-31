// Local only. No analytics, remote requests, or content execution.
const toggle=document.querySelector('.theme-toggle');
try {const saved=localStorage.getItem('agora-theme');if(saved)document.documentElement.dataset.theme=saved;}catch{}
toggle?.addEventListener('click',()=>{const next=document.documentElement.dataset.theme==='dark'?'light':'dark';document.documentElement.dataset.theme=next;try{localStorage.setItem('agora-theme',next);}catch{}});
document.querySelectorAll('[data-filter]').forEach(button=>button.addEventListener('click',()=>{document.querySelectorAll('[data-filter]').forEach(b=>b.classList.toggle('active',b===button));document.querySelectorAll('article[data-kind]').forEach(post=>post.hidden=button.dataset.filter!=='all'&&post.dataset.kind!==button.dataset.filter);}));
// Composer: character counter, gentle 30 second pause, no double posting. Local only.
const POST_PAUSE=30,POST_KEY='agora-last-post';
const T=s=>(window.agoraT||(x=>x))(s);
const nowSeconds=()=>Math.floor(Date.now()/1000);
const lastPost=()=>{try{return Number(localStorage.getItem(POST_KEY))||0;}catch{return 0;}};
const saveLastPost=()=>{try{localStorage.setItem(POST_KEY,String(nowSeconds()));}catch{}};
document.querySelectorAll('form[action="/posts"]').forEach(form=>{
  const button=form.querySelector('button'),area=form.querySelector('textarea');
  if(!button||!area)return;
  const original=button.innerHTML;
  const extras=document.createElement('div');extras.className='composer-extras';
  const hint=document.createElement('p');hint.className='composer-hint';hint.setAttribute('aria-live','polite');
  const count=document.createElement('span');count.className='char-count';count.setAttribute('aria-hidden','true');
  const bar=document.createElement('span');bar.className='pause-bar';bar.setAttribute('aria-hidden','true');
  const fill=document.createElement('span');bar.append(fill);
  extras.append(hint,count);button.before(extras);button.after(bar);
  const max=Number(area.getAttribute('maxlength'))||4000;
  const updateCount=()=>{const n=area.value.length;count.textContent=n+' / '+max;count.classList.toggle('near',n>max*0.9);};
  let timer=0;
  const tick=()=>{
    const left=POST_PAUSE-(nowSeconds()-lastPost());
    if(left>0){
      button.disabled=true;button.classList.add('is-waiting');
      button.textContent=T('Pronto tra {n} s').replace('{n}',left);
      hint.textContent=T('✳ Un respiro tra un messaggio e l’altro: la piazza ascolta meglio.');
      fill.style.width=((POST_PAUSE-left)/POST_PAUSE*100)+'%';bar.classList.add('visible');
      timer=setTimeout(tick,1000);
    }else{
      button.disabled=false;button.classList.remove('is-waiting','is-sending');button.innerHTML=original;
      hint.textContent=T('Un messaggio ogni 30 secondi · Ctrl+Invio per pubblicare');
      bar.classList.remove('visible');fill.style.width='0';
    }
  };
  area.addEventListener('input',updateCount);
  area.addEventListener('keydown',e=>{if(e.key==='Enter'&&(e.ctrlKey||e.metaKey)&&!button.disabled){e.preventDefault();form.requestSubmit(button);}});
  form.addEventListener('submit',e=>{
    if(button.disabled||form.classList.contains('sending')){e.preventDefault();return;}
    form.classList.add('sending');saveLastPost();clearTimeout(timer);
    button.classList.add('is-sending');button.textContent=T('Pubblico… ');
    const star=document.createElement('span');star.className='send-star';star.textContent='✳';button.append(star);
    hint.textContent=T('Sto portando il tuo messaggio in piazza…');
    setTimeout(()=>{button.disabled=true;},0);
  });
  addEventListener('pageshow',()=>{form.classList.remove('sending');clearTimeout(timer);tick();});
  updateCount();tick();
});
