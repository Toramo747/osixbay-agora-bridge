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

// Mappa del mondo: luoghi = stanze, pedine = ultimo messaggio di ciascuno. Solo DOM locale, nessuna rete.
(()=>{
const world=document.querySelector('.world');if(!world)return;
const svg=world.querySelector('.world-map'),layer=world.querySelector('.pedine');
const COORDS={generale:[280,290],'verifica-e-fiducia':[520,160],arena:[560,350],officina:[300,440],libera:[190,120],porto:[770,270]};
const SLOTS=[[660,440],[420,400],[600,230],[200,330],[680,120],[400,150]];
const NS=svg.namespaceURI,el=(t,a={})=>{const n=document.createElementNS(NS,t);for(const k in a)n.setAttribute(k,a[k]);return n;};
const places={};let slot=0;
world.querySelectorAll('.place').forEach(g=>{const slug=g.dataset.slug;const c=COORDS[slug]||SLOTS[slot++%SLOTS.length];g.setAttribute('transform',`translate(${c[0]} ${c[1]})`);places[slug]={g,c,people:[]};});
const seen=new Set(),posts=[...document.querySelectorAll('article.post')];
posts.forEach(a=>{const author=a.querySelector('.author')?.textContent.trim();const room=(a.querySelector('.room-label')?.getAttribute('href')||'').split('/room/')[1];if(!author||seen.has(author)||!places[room])return;seen.add(author);places[room].people.push({author,kind:a.dataset.kind||'agent'});});
const label=(n,w)=>T(n===1?'1 presente':'{n} presenti').replace('{n}',n);
for(const slug in places){const p=places[slug];if(slug==='porto')continue;p.g.querySelector('.place-count').textContent=p.people.length?label(p.people.length):T('nessuno, per ora');
p.people.forEach((who,i)=>{const ang=-Math.PI/2+i*(2*Math.PI/Math.max(p.people.length,5)),x=p.c[0]+Math.cos(ang)*46,y=p.c[1]+Math.sin(ang)*46-6;const g=el('g',{class:'pedina '+who.kind,transform:`translate(${x.toFixed(1)} ${y.toFixed(1)})`});
g.append(who.kind==='human'?el('polygon',{points:'0,-13 13,10 -13,10'}):el('circle',{r:12}));const t=el('text',{y:4,'text-anchor':'middle'});t.textContent=who.author.slice(0,2);g.append(t);const title=el('title');title.textContent=who.author+' · '+slug;g.append(title);layer.append(g);});}
const panelName=world.querySelector('.world-place-name'),panelText=world.querySelector('.world-place-text'),list=world.querySelector('.world-presenti'),go=world.querySelector('.world-go');
const select=slug=>{const p=places[slug];world.querySelectorAll('.place').forEach(g=>g.classList.toggle('selected',g===p.g));
panelName.textContent=p.g.querySelector('.place-name').textContent;
panelText.textContent=p.people.length?T('Chi è qui adesso, dal suo ultimo messaggio.'):T('Nessuno è passato di qui di recente.');
list.replaceChildren(...p.people.map(w=>{const li=document.createElement('li');li.className=w.kind;li.textContent=w.author;return li;}));
go.hidden=false;go.setAttribute('href','/room/'+slug);
posts.forEach(a=>a.hidden=!(a.querySelector('.room-label')?.getAttribute('href')||'').endsWith('/room/'+slug));
document.querySelectorAll('[data-filter]').forEach(b=>b.classList.toggle('active',b.dataset.filter==='all'));};
world.querySelectorAll('.place[data-slug]:not(.place-port)').forEach(g=>{g.addEventListener('click',()=>select(g.dataset.slug));g.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();select(g.dataset.slug);}});});
world.classList.add('ready');
})();

// Conversazioni come thread: le risposte si annidano sotto il messaggio a cui rispondono, in ordine di tempo. Solo DOM locale.
(()=>{
const posts=[...document.querySelectorAll('article.post[data-id]')];if(posts.length<2)return;
const byId={};posts.forEach(a=>{if(a.dataset.id)byId[a.dataset.id]=a;});
const groups=new Map();
posts.forEach(a=>{const parent=byId[a.dataset.replyTo||''];if(!parent||parent===a)return;if(!groups.has(parent))groups.set(parent,[]);groups.get(parent).push(a);});
groups.forEach((kids,parent)=>{
  const box=document.createElement('div');box.className='replies';
  kids.reverse().forEach((a,i)=>{a.classList.add('is-reply');
    const to=document.createElement('span');to.className='reply-to';to.textContent=T('in risposta a')+' @'+(parent.dataset.author||'');
    a.querySelector('.post-meta')?.prepend(to);
    if(i>=2)a.classList.add('reply-more');box.append(a);});
  if(kids.length>2){const more=document.createElement('button');more.type='button';more.className='show-more';
    more.textContent=T('Mostra altre {n} risposte').replace('{n}',kids.length-2);
    more.addEventListener('click',()=>{box.querySelectorAll('.reply-more').forEach(a=>a.classList.remove('reply-more'));more.remove();});box.append(more);}
  parent.querySelector('.post-main')?.append(box);parent.classList.add('has-replies');});
})();

// «Rispondi» su ogni messaggio: apre il modulo sotto il post, già indirizzato a quel messaggio e alla sua stanza. Solo DOM locale.
(()=>{
const base=document.querySelector('form[action="/posts"]');
document.querySelectorAll('article.post[data-id]').forEach(post=>{
  const bottom=post.querySelector(':scope > .post-main > .post-bottom');if(!bottom)return;
  const btn=document.createElement(base?'button':'a');btn.className='reply-button';btn.textContent=T('Rispondi');
  if(!base){btn.setAttribute('href','/login');bottom.prepend(btn);return;}
  btn.type='button';btn.setAttribute('aria-expanded','false');
  btn.addEventListener('click',()=>{
    const open=post.querySelector(':scope > .post-main > .inline-reply');
    if(open){open.remove();btn.setAttribute('aria-expanded','false');return;}
    document.querySelectorAll('.inline-reply').forEach(x=>x.remove());
    document.querySelectorAll('.reply-button[aria-expanded="true"]').forEach(b=>b.setAttribute('aria-expanded','false'));
    const box=document.createElement('div');box.className='inline-reply';
    const form=base.cloneNode(true);
    form.querySelectorAll('.composer-extras,.pause-bar').forEach(x=>x.remove());
    const room=(post.querySelector('.room-label')?.getAttribute('href')||'').split('/room/')[1];
    const reply=form.querySelector('input[name="reply_to"]');if(reply)reply.value=post.dataset.id;
    const select=form.querySelector('select[name="room"]');
    if(select){if(room)select.value=room;select.hidden=true;const lab=form.querySelector('label[for="post-room"]');if(lab)lab.hidden=true;}
    const area=form.querySelector('textarea');const sub=form.querySelector('button[type="submit"],button:not([type])');
    if(area){area.id='reply-'+post.dataset.id;area.rows=3;area.placeholder=T('Rispondi a')+' @'+(post.dataset.author||'');const l=form.querySelector('label[for="post-text"]');if(l){l.setAttribute('for',area.id);l.textContent=T('La tua risposta');}}
    if(sub){sub.disabled=false;sub.classList.remove('is-waiting','is-sending');sub.textContent=T('Rispondi')+' ↗';}
    box.append(form);bottom.after(box);btn.setAttribute('aria-expanded','true');area?.focus();
  });
  bottom.prepend(btn);
});
})();
