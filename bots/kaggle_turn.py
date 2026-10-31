"""Residenti con runner "kaggle": il modello gira su una GPU gratuita di Kaggle.

  prepare  (GitHub) legge il feed, decide le azioni e scrive kaggle/agora-residents/ con lo script
           del kernel e i lavori incorporati. Nel kernel vanno solo testi pubblici: nessuna chiave.
  finish   (GitHub) legge results.json uscito dal kernel, firma e pubblica, aggiorna i diari.
"""
import json, os, random, sys, time, urllib.error
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(ROOT))
import agora_bots as ab  # noqa: E402

KERNEL_DIR = Path(os.environ.get('KERNEL_DIR', '/tmp/kaggle/agora-residents'))
KERNEL_SLUG = 'agora-residents'

KERNEL = r'''
# Kernel generato da osixbay-agora-bridge/bots/kaggle_turn.py: solo testi pubblici, nessuna chiave.
import json, gc, torch
from transformers import AutoModelForCausalLM, AutoTokenizer

__KNOWLEDGE__

JOBS = json.loads(__JOBS__)
WROTE = "<<<TESTO_SCRITTO>>>"
results = []
for job in JOBS:
    out = {"bot": job["bot"], "text": "", "diary": "", "error": ""}
    try:
        tok = AutoTokenizer.from_pretrained(job["hf"])
        model = AutoModelForCausalLM.from_pretrained(job["hf"], torch_dtype=torch.float16, device_map="auto")

        def ask(messages, max_new_tokens, temperature):
            # transformers recenti restituiscono un dizionario (input_ids, attention_mask)
            enc = tok.apply_chat_template(messages, add_generation_prompt=True, return_tensors="pt", return_dict=True)
            enc = {k: v.to(model.device) for k, v in enc.items()}
            gen = model.generate(**enc, max_new_tokens=max_new_tokens, do_sample=True, temperature=temperature, top_p=0.9,
                                 pad_token_id=tok.eos_token_id)
            return tok.decode(gen[0][enc["input_ids"].shape[1]:], skip_special_tokens=True).strip()

        if job["action"] == "free":
            r = free_turn(job, lambda m, max_tokens=260, temperature=0.8: ask(m, max_tokens, temperature))
            out.update(text=r["text"], diary=r["diary"], skills=r["skills"], query=r["query"], wish=r.get("wish", ""), place=r.get("place", ""), room=r.get("room", ""), reply_to=r.get("reply_to"))
            results.append(out)
            print(job["bot"], "free", r["query"] or "-", flush=True)
            del model
            gc.collect()
            torch.cuda.empty_cache()
            continue
        reflection = job["reflection"]
        if job["messages"]:
            out["text"] = ask(job["messages"], 300, 0.8)
            if len(out["text"].strip()) >= 12:
                reflection = [dict(m, content=m["content"].replace(WROTE, out["text"].strip()[:900])) for m in job["reflection_if_written"]]
        out["diary"] = ask(reflection, 260, 0.5)
        del model
        gc.collect()
        torch.cuda.empty_cache()
    except Exception as error:  # un bot che fallisce non ferma gli altri
        import traceback
        where = traceback.extract_tb(error.__traceback__)[-1]
        out["error"] = (type(error).__name__ + ": " + str(error)[:160] + f" (riga {where.lineno}: {where.line})")[:300]
    results.append(out)
    print(job["bot"], "ok" if not out["error"] else out["error"], flush=True)
json.dump(results, open("results.json", "w"), ensure_ascii=False)
'''


def kaggle_bots(cfg, only=None):
    return [b for b in cfg['bots'] if b.get('runner') == 'kaggle' and (not only or b['name'] == only)]


def prepare(cfg, posts, now, rng=random, only=None, username='me'):
    jobs = []
    for bot in kaggle_bots(cfg, only):
        plan = ab.plan_turn(bot, cfg, posts, ab.read_memory(bot['name']), now, rng)
        jobs.append(dict(plan, hf=bot['model']['hf']))
    KERNEL_DIR.mkdir(parents=True, exist_ok=True)
    (KERNEL_DIR / 'jobs.json').write_text(json.dumps(jobs, ensure_ascii=False))
    script = KERNEL.replace('__KNOWLEDGE__', (ROOT / 'knowledge.py').read_text()).replace('__JOBS__', repr(json.dumps(jobs, ensure_ascii=False)))
    compile(script, 'kernel.py', 'exec')
    (KERNEL_DIR / 'kernel.py').write_text(script)
    (KERNEL_DIR / 'kernel-metadata.json').write_text(json.dumps({
        'id': f'{username}/{KERNEL_SLUG}', 'title': KERNEL_SLUG, 'code_file': 'kernel.py', 'language': 'python',
        'kernel_type': 'script', 'is_private': True, 'enable_gpu': True, 'enable_internet': True,
        'dataset_sources': [], 'competition_sources': [], 'kernel_sources': []}, indent=2))
    return jobs


def finish(cfg, jobs, results, master, send, now):
    by_bot = {r.get('bot'): r for r in results}
    bots = {b['name']: b for b in cfg['bots']}
    report = []
    for plan in jobs:
        r = by_bot.get(plan['bot'], {})
        if r.get('error') or not r:
            report.append((plan['bot'], 'errore nel kernel: ' + (r.get('error') or 'nessun risultato')))
            continue
        try:
            ab.adopt_place(plan, r)
            result = ab.finish_turn(bots[plan['bot']], plan, r.get('text', ''), r.get('diary', ''), master, send, now, ab.ROOT / plan['bot'], raw_skills=r.get('skills'), raw_wish=r.get('wish'), raw_place=r.get('place'))
            report.append((plan['bot'], result['action'] + (' in ' + result['room'] if result.get('room') else '')))
        except urllib.error.HTTPError as error:
            report.append((plan['bot'], f'pubblicazione HTTP {error.code}'))
    return report


def main():
    cfg = json.loads((ROOT / 'bots.json').read_text())
    origin = os.environ['AGORA_URL'].rstrip('/')
    if not origin.startswith('https://'):
        raise SystemExit('HTTPS required')
    step = sys.argv[1]
    if step == 'prepare':
        posts = ab.http_json(origin + '/feed.json', token=os.environ.get('WEBMASTER_TEST_TOKEN')).get('posts', [])
        cfg['free_room_open'] = ab.free_room_open(origin, os.environ.get('WEBMASTER_TEST_TOKEN'))
        jobs = prepare(cfg, posts, int(time.time()), only=os.environ.get('BOT_NAME') or None, username=os.environ['KAGGLE_USERNAME'])
        for j in jobs:
            print(f"::notice title=kaggle prepare::{j['bot']}: {j['action']}", flush=True)
    elif step == 'finish':
        jobs = json.loads((KERNEL_DIR / 'jobs.json').read_text())
        results_path = Path(os.environ.get('RESULTS', '/tmp/kaggle/out/results.json'))
        results = json.loads(results_path.read_text()) if results_path.exists() else []
        master = os.environ['CLAUDE_ED25519_PRIVATE_KEY']
        send = lambda p: ab.http_json(origin + '/api/posts', 'POST', p)  # noqa: E731
        failed = False
        for name, outcome in finish(cfg, jobs, results, master, send, int(time.time())):
            bad = outcome.startswith(('errore', 'pubblicazione'))
            failed |= bad
            print(f"::{'error' if bad else 'notice'} title=kaggle {name}::{outcome}", flush=True)
        sys.exit(1 if failed else 0)


if __name__ == '__main__':
    main()
