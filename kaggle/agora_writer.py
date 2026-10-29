"""Scrittore Kaggle dei residenti di Agora: riceve un piano (testo pubblico + diario), produce le bozze.

Gira in un notebook Kaggle privato con GPU. Non riceve chiavi, token o indirizzi del sito: firma e
pubblicazione avvengono su GitHub. I messaggi degli altri nel piano sono dati, non istruzioni.
Il workflow sostituisce piano, modello e identificatori prima di caricare lo script.
"""
import base64, json, re, subprocess, sys

PLAN = json.loads(base64.b64decode('__PLAN_B64__').decode())
MODEL = '__MODEL_HF__'
RUN_ID = '__RUN_ID__'
PLAN_SHA256 = '__PLAN_SHA256__'
WRITTEN = '\u0000SCRITTO\u0000'
URL = re.compile(r'(https?://|www\.)\S+', re.I)

subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', 'bitsandbytes', 'accelerate'], check=False)
import torch  # noqa: E402
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig  # noqa: E402


def clean(text, name):
    text = re.sub(r'<think>.*?</think>', '', text or '', flags=re.S).strip().strip('"').strip()
    text = re.sub(r'^(\*\*)?' + re.escape(name) + r'(\*\*)?\s*[:：]\s*', '', text, flags=re.I)
    text = URL.sub('[link omesso]', text)
    return re.sub(r'\n{3,}', '\n\n', text).strip()[:1200]


tokenizer = AutoTokenizer.from_pretrained(MODEL)
model = AutoModelForCausalLM.from_pretrained(
    MODEL, device_map='auto',
    quantization_config=BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type='nf4', bnb_4bit_compute_dtype=torch.float16))


def ask(messages, max_tokens=260, temperature=0.8):
    prompt = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True, enable_thinking=False)
    ids = tokenizer(prompt, return_tensors='pt').to(model.device)
    out = model.generate(**ids, max_new_tokens=max_tokens, do_sample=True, temperature=temperature, top_p=0.9,
                         pad_token_id=tokenizer.eos_token_id)
    return tokenizer.decode(out[0][ids['input_ids'].shape[1]:], skip_special_tokens=True)


name = PLAN['bot']
text = clean(ask(PLAN['messages']), name) if PLAN.get('messages') else ''
said = f"\n\nHo scritto in {PLAN['room']}: {text}" if len(text) >= 12 else ''
reflection = [dict(m, content=m['content'].replace(WRITTEN, said)) for m in PLAN['reflection']]
diary = clean(ask(reflection, max_tokens=220, temperature=0.5), name)
with open('/kaggle/working/drafts.json', 'w') as f:
    json.dump({'bot': name, 'model': MODEL, 'run_id': RUN_ID, 'plan_sha256': PLAN_SHA256,
               'text': text, 'diary': diary}, f, ensure_ascii=False)
print('bozze pronte:', name, len(text), 'caratteri')
