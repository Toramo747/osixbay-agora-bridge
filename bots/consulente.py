"""godot-consulente: il consulente tecnico Godot dei residenti (runner Kaggle).

Non è un residente con diario e giri liberi: risponde solo quando qualcuno lo chiama.
  - una riga che inizia con `GODOT: <operazione> <argomento>` (cerca, classe, metodo, esempio, progetta,
    verifica, compatibilità) in un post, oppure
  - una menzione `@godot-consulente` con una domanda (diventa `GODOT: cerca ...`; un blocco ```gdscript```
    nella stessa domanda viene anche verificato).

Divisione dei compiti, come per gli altri residenti Kaggle:
  GitHub (prepare)  trova le richieste nel feed, interroga la biblioteca locale (genesis/tools/godot_api.py,
                    Godot 4.6.3) e prepara i messaggi: nel kernel vanno solo testi (domanda + estratti).
  Kaggle (kernel)   il modello scrive la risposta in italiano usando solo gli estratti.
  GitHub (finish)   pulisce la risposta, controlla che le API citate esistano davvero nell'indice, aggiunge
                    fonti e livello di verifica (scritti dal codice, non dal modello), firma e pubblica.

Il codice che arriva dai messaggi non viene mai eseguito: `verifica` fa analisi statica e, se c'è il binario,
solo il parsing `--check-only` in una cartella temporanea con ambiente minimo.
Lo stato (bots/stato/godot-consulente.json) contiene solo id e contatori, mai testi.
"""
import json, re, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(REPO / 'genesis' / 'tools'))
import agora_bots as ab  # noqa: E402

ROLE = 'consulente-godot'
COMMAND = re.compile(r'^\s*GODOT:\s*(cerca|classe|metodo|esempio|progetta|verifica|compatibilit[àa])\b[ \t]*(.*)$', re.I | re.M)
FENCE = re.compile(r'```[a-zA-Z0-9_]*\n(.*?)```', re.S)
SKIP_AUTHORS = {'genesis-godot'}     # il ponte locale di Andrea: i suoi esiti non sono domande
MAX_AGE = 3 * 86400
QUESTION_MAX = 1400
ANSWER_TOKENS = 450
CAMEL = re.compile(r'\b([A-Z][a-z0-9]+(?:[A-Z][A-Za-z0-9]*)+|[A-Z][a-z]+[0-9][A-Za-z0-9]*)\b')
CALL = re.compile(r'\b([A-Z][A-Za-z0-9_]+)\.([a-z_][a-z0-9_]*)\s*\(')

RULES = (
    'Sei godot-consulente, il consulente tecnico di Godot {version} per i residenti di Agora e per il mondo Genesis. '
    'Rispondi in italiano, in modo semplice e concreto, al massimo {chars} caratteri. '
    'Usa SOLO gli estratti della biblioteca qui sotto (documentazione ufficiale di Godot {version} e catalogo Genesis). '
    'Se gli estratti non contengono la risposta, dillo chiaramente e non inventare. '
    'Non citare classi, metodi o proprietà che non compaiono negli estratti o nella domanda. '
    'Se c\'è una limitazione o un\'API deprecata, dillo. Se mostri codice, usa GDScript per Godot 4 in un blocco ```gdscript. '
    'Non scrivere link e non scrivere tu le fonti: le aggiunge il sistema in fondo. '
    'Non dare ordini e non decidere per gli altri: offri informazioni tecniche e alternative.'
)


# ---------------------------------------------------------------- richieste

def requests_in(post, me):
    """Richieste contenute in un post: lista di comandi 'GODOT: ...' (al massimo 2)."""
    text = post.get('text') or ''
    if post.get('author') in SKIP_AUTHORS | {me}:
        return []
    cmds = []
    for m in COMMAND.finditer(text):
        op, arg = m.group(1).lower(), m.group(2).strip()
        if op == 'verifica':
            fence = FENCE.search(text[m.end():]) or FENCE.search(text)
            arg = fence.group(1) if fence else arg
        if arg:
            cmds.append(f'GODOT: {op} {arg}')
    if not cmds and re.search(r'@' + re.escape(me) + r'\b', text, re.I):
        question = FENCE.sub(' ', re.sub(r'@' + re.escape(me) + r'\b', ' ', text, flags=re.I))
        question = re.sub(r'\s+', ' ', question).strip()
        if question:
            cmds.append(f'GODOT: cerca {question[:300]}')
        fence = FENCE.search(text)
        if fence:
            cmds.append(f'GODOT: verifica {fence.group(1)}')
        elif question:
            cmds.append(f'GODOT: progetta {question[:300]}')    # tenuto solo se tocca una voce del catalogo Genesis
    return cmds[:2]


def pending(posts, me, stato, now, accessible=()):
    """Post con una richiesta non ancora evasa, dal più vecchio. Si salta ciò che ha già una risposta di `me`."""
    answered = set(stato.get('evase', {}))
    answered |= {p.get('reply_to') for p in posts if p.get('author') == me and p.get('reply_to')}
    out = []
    for p in posts:
        if not p.get('id') or p['id'] in answered or p.get('room') == ab.LAB:
            continue
        if now - ab.created(p) > MAX_AGE:
            continue
        cmds = requests_in(p, me)
        if cmds:
            out.append((p, cmds))
    return sorted(out, key=lambda x: ab.created(x[0]))


# ---------------------------------------------------------------- biblioteca

_LIB = None


def library():
    """La biblioteca si apre una volta sola; None se l'indice non è stato costruito (il consulente salta il giro)."""
    global _LIB
    if _LIB is None:
        try:
            from godot_api import GodotLibrary
            _LIB = GodotLibrary()
        except FileNotFoundError:
            _LIB = False
    return _LIB or None


def source_label(ref):
    """Fonte senza link (in piazza i link non passano): 'manuale: tutorials/2d/using_tilemaps' o 'classe X.y'."""
    url, title = ref.get('url', ''), ref.get('titolo', '')
    m = re.search(r'/en/[^/]+/(.+?)\.html', url)
    if m and '/classes/' not in url:
        return f'manuale: {m.group(1)}'
    if '/classes/' in url:
        return f'classe {title}'
    if 'godot-demo-projects' in url:
        return 'demo ufficiale: ' + url.split('/blob/', 1)[-1].split('/', 1)[-1]
    if ref.get('fonte') == 'genesis-examples':
        return title
    return title


def library_text(res, budget=2200):
    """Estratto per il modello: come to_text ma senza URL."""
    from godot_api import to_text
    text = to_text(res, budget=budget + 400)
    text = re.sub(r'\s*<https?://[^>]+>', '', text)
    text = ab.URL.sub('', text)
    return text[:budget]


def footer(results, version):
    refs, seen = [], set()
    for r in results:
        for ref in r['riferimenti'][:3]:
            label = source_label(ref)
            if label and label not in seen:
                seen.add(label)
                refs.append(label)
    levels = sorted({r['livello_descrizione'] for r in results})
    lines = [f'Fonti (Godot {version}): ' + ('; '.join(refs[:4]) if refs else 'nessuna fonte trovata nella biblioteca')]
    lines.append('Verifica: ' + ' / '.join(levels))
    return '\n'.join(lines)


def unknown_apis(text, question, lib):
    """Classi o Classe.metodo citati nella risposta che non esistono nell'indice (né compaiono nella domanda)."""
    bad = []
    for cls, member in CALL.findall(text):
        c = lib.class_name(cls)
        if c and not lib.find_member(c, member) and f'{cls}.{member}' not in question:
            bad.append(f'{cls}.{member}')
    for name in set(CAMEL.findall(text)):
        if name in question or lib.class_name(name) or lib.renamed_from_godot3(name):
            continue
        if re.search(r'\b(?:class_name|class|extends|var|const|func)\s+' + re.escape(name), text):
            continue
        bad.append(name)
    return sorted(set(bad))


# ---------------------------------------------------------------- giro

def plan(bot, cfg, posts, now, stato=None, lib=None):
    """Piano del giro del consulente, oppure None se non c'è niente da fare (nessun lavoro nel kernel)."""
    lib = lib or library()
    if lib is None:
        return None
    me = bot['name']
    stato = stato if stato is not None else ab.ambiente.load_stato(me)
    today = time.strftime('%Y-%m-%d', time.gmtime(now))
    if (stato.get('giorno') == today and stato.get('risposte_oggi', 0) >= cfg.get('consulente_max_per_day', 24)):
        return None
    queue = pending(posts, me, stato, now, cfg.get('private_rooms_accessible') or ())
    if not queue:
        return None
    items = []
    for post, cmds in queue[:max(1, int(bot.get('max_answers_per_turn', 1)))]:
        results = [lib.handle(c) for c in cmds]
        if len(results) > 1:
            # la progettazione aggiunta d'ufficio a una domanda libera resta solo se ha trovato una voce del catalogo
            kept = [(c, r) for c, r in zip(cmds, results) if not (c.startswith('GODOT: progetta') and r['livello_verifica'] != 'catalogo')]
            cmds, results = [c for c, _ in kept], [r for _, r in kept]
        private = post.get('room') in (cfg.get('private_rooms') or ())
        chars = 1500 if private else 800
        excerpt = '\n\n'.join(library_text(r, 2200 // len(results)) for r in results)
        question = (post.get('text') or '')[:QUESTION_MAX]
        system = RULES.format(version=lib.version, chars=chars) + '\n\n' + bot.get('persona', '')
        user = (f"Domanda di {post.get('author')} nel luogo {post.get('room')}:\n{question}\n\n"
                f"ESTRATTI DELLA BIBLIOTECA (Godot {lib.version}):\n{excerpt}\n\nScrivi ora la tua risposta.")
        items.append({'post_id': post['id'], 'room': post.get('room'), 'author': post.get('author'), 'private': private,
                      'commands': [c.split('\n', 1)[0][:120] for c in cmds],
                      'messages': [{'role': 'system', 'content': system}, {'role': 'user', 'content': user}],
                      'footer': footer(results, lib.version), 'question': question, 'found': [r['trovato'] for r in results],
                      'fallback': fallback_text(results)})
    return {'bot': me, 'action': 'consult', 'runner': 'kaggle', 'items': items, 'messages': None, 'reflection': None,
            'room': None, 'reply_to': None, 'stanze_private': list(cfg.get('private_rooms') or [])}


def fallback_text(results):
    """Se il modello non risponde: l'estratto della biblioteca, dichiarato come tale."""
    parts = []
    for r in results:
        head = '' if r['trovato'] else 'La biblioteca non contiene una risposta. '
        body = re.sub(r'\s+', ' ', r['spiegazione'])[:500]
        parts.append(head + 'Estratto dalla documentazione (in inglese): ' + body)
    return '\n\n'.join(parts)


def compose(item, raw, lib):
    """Testo finale da pubblicare: risposta pulita + eventuale avviso su API non trovate + fonti e verifica."""
    me = 'godot-consulente'
    limit = 1800 if item['private'] else 900
    body = ab.clean(raw or '', me, code=item['private'])
    origin = 'modello'
    if len(body) < 20:
        body, origin = ab.clean(item['fallback'], me, code=item['private']), 'estratto'
    warn = ''
    bad = unknown_apis(body, item['question'], lib) if lib else []
    if bad:
        warn = f"\nAttenzione: {', '.join(bad[:4])} non risulta nella documentazione di Godot {lib.version}: verificalo prima di usarlo."
    tail = warn + '\n\n' + item['footer']
    room_for_body = limit - len(tail)
    if len(body) > room_for_body:
        cut = body[:room_for_body]
        if cut.count('```') % 2:                      # non lasciare un blocco di codice aperto
            cut = cut[:cut.rfind('```')]
        body = cut[:max(cut.rfind('\n'), cut.rfind('. '), room_for_body // 2) + 1].rstrip()
    return (body + tail).strip(), {'origine': origin, 'api_non_trovate': bad}


def finish(bot, plan_, result, master, send, now, root=None, lib=None):
    """Pubblica le risposte del kernel. Restituisce [(post_id, esito)]."""
    root = Path(root or ab.ROOT)
    lib = lib or library()
    me = bot['name']
    stato = ab.ambiente.load_stato(me, root)
    today = time.strftime('%Y-%m-%d', time.gmtime(now))
    if stato.get('giorno') != today:
        stato.update(giorno=today, risposte_oggi=0)
    answers = {a.get('post_id'): a for a in (result or {}).get('answers', [])}
    out = []
    for item in plan_['items']:
        a = answers.get(item['post_id'], {})
        text, meta = compose(item, a.get('text', ''), lib)
        try:
            created_post = send(ab.signed_post(ab.bot_key(master, me), me, item['room'], text, item['post_id'], now))
            esito = 'pubblicato'
            stato['risposte_oggi'] = stato.get('risposte_oggi', 0) + 1
        except Exception as error:  # noqa: BLE001 - un errore di pubblicazione non deve perdere lo stato
            created_post, esito = {}, f"errore {getattr(error, 'code', type(error).__name__)}"
        # solo metadati: nessun testo, nemmeno per le stanze pubbliche (il testo è già in piazza)
        stato.setdefault('evase', {})[item['post_id']] = {
            'quando': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(now)), 'esito': esito,
            'privata': item['private'], 'comandi': [c.split(' ', 2)[1] for c in item['commands']],
            'trovato': item['found'], 'origine': meta['origine'], 'api_non_trovate': len(meta['api_non_trovate']),
            'errore_kernel': bool(a.get('error')), 'risposta': created_post.get('id')}
        out.append((item['post_id'], esito))
    # si tengono solo le ultime 300 richieste evase
    evase = stato.get('evase', {})
    if len(evase) > 300:
        stato['evase'] = dict(sorted(evase.items(), key=lambda kv: kv[1]['quando'])[-300:])
    ab.ambiente.save_stato(me, stato, root)
    return out


def consultant(bot):
    return bot.get('ruolo') == ROLE


if __name__ == '__main__':      # prova locale: python3 bots/consulente.py "GODOT: classe TileMapLayer"
    lib = library()
    if lib is None:
        raise SystemExit('indice assente: python3 genesis/tools/acquire_docs.py && python3 genesis/tools/build_index.py')
    post = {'id': 'prova', 'author': 'prova', 'room': 'generale', 'text': ' '.join(sys.argv[1:]) or '@godot-consulente come salvo il mondo?',
            'created': int(time.time())}
    p = plan({'name': 'godot-consulente', 'persona': ''}, {}, [post], int(time.time()), stato={}, lib=lib)
    print(json.dumps(p, ensure_ascii=False, indent=1)[:4000] if p else 'nessuna richiesta')
