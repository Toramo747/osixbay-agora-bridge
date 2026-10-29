// Local only. No analytics, remote requests, or content execution.
const toggle=document.querySelector('.theme-toggle');
try {const saved=localStorage.getItem('agora-theme');if(saved)document.documentElement.dataset.theme=saved;}catch{}
toggle?.addEventListener('click',()=>{const next=document.documentElement.dataset.theme==='dark'?'light':'dark';document.documentElement.dataset.theme=next;try{localStorage.setItem('agora-theme',next);}catch{}});
document.querySelectorAll('[data-filter]').forEach(button=>button.addEventListener('click',()=>{document.querySelectorAll('[data-filter]').forEach(b=>b.classList.toggle('active',b===button));document.querySelectorAll('article[data-kind]').forEach(post=>post.hidden=button.dataset.filter!=='all'&&post.dataset.kind!==button.dataset.filter);}));
