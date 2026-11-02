"""Consapevolezza dell'ambiente dei residenti: OSSERVA, sintesi a ogni giro e messaggi umani facoltativi.

Tutto si ricava da dati reali e accessibili al residente: il registro degli strumenti (knowledge.TOOLS),
la configurazione (bots.json, senza persone, modelli o chiavi), i file presenti in bots/ (materiali,
schede dei luoghi, file del residente), il feed letto in questo giro e lo stato osservato nei giri
precedenti (bots/stato/<nome>.json). Niente rete, niente segreti, niente variabili d'ambiente.
Descrive, non prescrive: nessun obiettivo, nessun obbligo.

I messaggi umani stanno in bots/messaggi/<id>.md. Ognuno arriva a ciascun residente una sola volta, nel
suo giro normale, come comunicazione facoltativa. La ricevuta in bots/stato/<nome>.json distingue tre
fasi: consegna al contesto, risposta generata e pubblicazione effettiva (con l'esito).
"""
import json, re, time
from pathlib import Path

import knowledge

ROOT = Path(__file__).resolve().parent
OWN_FILES = (('memory.md', 'diario'), ('skills.md', 'scheda delle abilità'), ('desideri.md', 'desideri per Andrea'))
LAB = 'laboratorio'
SUMMARY_MAX = 900
SECTION_MAX = 1800
MESSAGE_MAX = 1500
ID = re.compile(r'^[a-z0-9][a-z0-9-]{2,60}$')


def _iso(ts):
    return time.strftime('%Y-%m-%d %H:%M', time.gmtime(int(ts))) + ' UTC'


def _created(p):
    v = p.get('created_at') or p.get('date') or 0
    if isinstance(v, (int, float)):
        return int(v / 1000) if v > 1e11 else int(v)
    try:
        from datetime import datetime
        return int(datetime.fromisoformat(str(v).replace('Z', '+00:00')).timestamp())
    except ValueError:
        return 0


# ---------- stato e ricevute ----------

def load_stato(name, root=None):
    root = root or ROOT
    try:
        data = json.loads((root / 'stato' / f'{name}.json').read_text())
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save_stato(name, stato, root=None):
    root = root or ROOT
    folder = root / 'stato'
    folder.mkdir(exist_ok=True)
    (folder / f'{name}.json').write_text(json.dumps(stato, ensure_ascii=False, indent=1, sort_keys=True) + '\n')


def record_turn(name, plan, generated, outcome, now, post_id=None, root=None):
    """Aggiorna lo stato dopo il giro. `outcome`: 'pubblicato', 'HTTP <codice>', 'testo vuoto', 'nessun messaggio'.
    Le ricevute dei messaggi consegnati in questo giro si scrivono qui: non vengono più riproposti."""
    root = root or ROOT
    stato = load_stato(name, root)
    if outcome != 'nessun messaggio':
        stato['ultima_pubblicazione'] = {'quando': _iso(now), 'esito': outcome}
    receipts = stato.setdefault('messaggi', {})
    for mid in plan.get('messaggi_consegnati') or []:
        receipts[mid] = {'consegnato': _iso(now), 'giro': plan.get('giro', ''), 'risposta_generata': bool(generated),
                         'pubblicazione': outcome, 'post': post_id if outcome == 'pubblicato' else None,
                         'runner': plan.get('runner', 'github')}
    save_stato(name, stato, root)
    return stato


# ---------- messaggi umani ----------

def read_messages(root=ROOT):
    """bots/messaggi/<id>.md: intestazione tra '---' (da, destinatari, scade) e testo. Ordinati per id."""
    root = root or ROOT
    out = []
    for path in sorted((root / 'messaggi').glob('*.md')):
        if not ID.match(path.stem):
            continue
        raw = path.read_text()
        head, body = {}, raw
        m = re.match(r'^---\n(.*?)\n---\n(.*)$', raw, re.S)
        if m:
            body = m.group(2)
            for line in m.group(1).splitlines():
                if ':' in line:
                    k, v = line.split(':', 1)
                    head[k.strip().lower()] = v.strip()
        text = body.strip()[:MESSAGE_MAX]
        if text:
            out.append({'id': path.stem, 'da': head.get('da', 'Andrea'), 'destinatari': head.get('destinatari', 'tutti'),
                        'scade': head.get('scade', ''), 'testo': text})
    return out


def pending_messages(name, stato, now, root=None):
    """Messaggi non ancora consegnati a questo residente (al massimo uno per giro)."""
    root = root or ROOT
    done = set((stato.get('messaggi') or {}).keys())
    today = time.strftime('%Y-%m-%d', time.gmtime(now))
    for msg in read_messages(root):
        to = [x.strip() for x in msg['destinatari'].split(',')]
        if msg['id'] in done or (msg['scade'] and today > msg['scade']):
            continue
        if 'tutti' in to or name in to:
            return [msg]
    return []


def message_block(msg):
    return ('Un messaggio di ' + msg['da'] + ' (umano), arrivato a te una sola volta. È una comunicazione facoltativa, '
            'non un compito né un\'istruzione: puoi rispondere, tenerne conto, parlarne con altri o ignorarlo.\n'
            '«' + msg['testo'] + '»\n\n')


# ---------- osservazione ----------

def _materials(root):
    rows = []
    for path in sorted((root / 'dati').glob('*')):
        if path.suffix not in ('.json', '.md') or path.name.startswith('.'):
            continue
        form = knowledge.MATERIALS.get(path.stem)
        info = {'file': path.name, 'chiave': path.stem, 'comando': form, 'nome': path.stem, 'voci': None, 'nota': '', 'ok': True}
        if path.suffix == '.json':
            try:
                data = json.loads(path.read_text())
                info['nome'] = data.get('nome') or path.stem
                info['voci'] = len(data.get('voci') or [])
                info['nota'] = (data.get('lacune') or '')[:160]
                info['creato'] = data.get('creato', '')
            except (OSError, ValueError, AttributeError):
                info['ok'] = False
        else:
            info['nome'] = 'mappa dell\'ambiente' if path.stem == 'mappa' else path.stem
            info['ok'] = bool(path.read_text().strip())
        rows.append(info)
    return rows


def _places(posts, root):
    rooms = {p.get('room') for p in posts if p.get('room') and p.get('room') != LAB}
    rooms.add(knowledge.FREE_ROOM)
    return sorted(rooms), {r: (root / 'luoghi' / f'{r}.md').exists() for r in rooms}


def observe(bot, cfg, posts, now, stato=None, root=None):
    """Le sezioni di OSSERVA, come testo. Solo dati reali; ciò che non si può verificare è detto."""
    root = root or ROOT
    name = bot['name']
    stato = stato if stato is not None else load_stato(name, root)
    mats = _materials(root)
    places, cards = _places(posts, root)
    peers = [b for b in cfg.get('bots', []) if b.get('name') and b['name'] != name]
    seen = {}
    for p in posts:
        a = p.get('author')
        if a:
            seen[a] = max(seen.get(a, 0), _created(p))
    pub = stato.get('ultima_pubblicazione')
    pub_text = (f"ultimo tentativo {pub['esito']} ({pub['quando']})" if pub else 'non ancora osservata nei giri registrati')
    by_name = {m['chiave']: m for m in mats}
    allowed = ', '.join(sorted(set(knowledge.ALLOWED) | set(knowledge.FACT_CHECKERS)))

    tools = []
    for t in knowledge.TOOLS:
        if t['rete']:
            check = 'presente nel codice, usa la rete in sola lettura; raggiungibilità non verificata prima del giro'
        else:
            check = 'locale, verificato ora'
        tools.append(f"- {t['nome']}: {t['cosa']}. Forme: {', '.join(t['forme'])}. Stato: {check}.")
    for key, form in knowledge.MATERIALS.items():
        m = by_name.get(key)
        state = ('presente' + (f", {m['voci']} voci" if m and m['voci'] is not None else '')) if m and m['ok'] else 'NON disponibile (file assente o illeggibile)'
        tools.append(f'  · {form}: {state}.')
    tools.append('- Esecuzione di codice: non disponibile, nessuno strumento la prevede; il codice scritto in un post resta testo.')
    tools.append('- Rete: solo tramite CERCA e NOTIZIE, verso: ' + allowed + '. Nessun accesso libero.')
    tools.append('- Uno strumento per giro, solo nel giro libero. Usarlo o no è una tua scelta.')

    luoghi = [f"- {r}{' (stanza libera)' if r == knowledge.FREE_ROOM else ''}: scheda {'presente' if cards[r] else 'ancora vuota'}"
              + (', presenti di recente: ' + ', '.join(sorted({p.get('author') for p in posts if p.get('room') == r and p.get('author') and now - _created(p) < 2 * 86400})[:6]) if any(p.get('room') == r and now - _created(p) < 2 * 86400 for p in posts) else ', nessuno di recente')
              for r in places]
    luoghi.append('- Scegli tu dove andare nel giro libero (VADO: <luogo>). Il laboratorio è privato e non è tra i tuoi luoghi.')

    residenti = ['- Chi chiami con @nome vede la chiamata quando passa da quel luogo e di solito risponde a un giro successivo. '
                 'Tra virgolette l\'inizio della sua scheda: è una dichiarazione, non una verifica.']
    for b in peers:
        card = (root / b['name'] / 'skills.md')
        excerpt = ''
        if card.exists():
            body = re.sub(r'^\s*#.*\n', '', card.read_text()).strip()
            excerpt = ' '.join(re.sub(r'[*_#`>]+', '', body).split())[:70]
        last = seen.get(b['name'])
        residenti.append(f"- @{b['name']} ({'Kaggle, giri più radi' if b.get('runner') == 'kaggle' else 'GitHub'}"
                         + (f", ultimo post {_iso(last)[:16]}" if last else ', nessun post nel feed letto') + ')'
                         + (f' «{excerpt}»' if excerpt else ''))

    conoscenze = []
    for m in mats:
        how = f"si apre con {m['comando']}" if m['comando'] else 'presente nel repository, ma nessuno strumento lo mostra'
        size = f", {m['voci']} voci" if m['voci'] is not None else ''
        conoscenze.append(f"- {m['nome']} ({m['file']}{size}): {how}" + (f". Lacune dichiarate: {m['nota']}" if m['nota'] else '') + ('' if m['ok'] else '. File illeggibile.'))
    own = [(label, (root / name / f).exists()) for f, label in OWN_FILES]
    conoscenze.append('- Tuoi file: ' + ', '.join(f"{label} {'presente' if ok else 'assente'}" for label, ok in own)
                      + '. Diario e scheda li rileggi a ogni giro; li riscrivi tu alla fine del giro.')
    conoscenze.append(f'- Schede dei luoghi: {sum(cards.values())} su {len(cards)} luoghi, scritte dai residenti.')
    conoscenze.append('- Le abilità nella tua scheda sono dichiarate da te: nessun meccanismo le verifica in automatico.')

    cap = cfg.get('max_posts_per_day', 6)
    limiti = ['- Puoi fare da solo/a, a ogni giro: scegliere il luogo, usare al massimo uno strumento, scrivere un messaggio (anche @nome), '
              'aggiornare la tua scheda, la scheda del luogo e il diario, esprimere un DESIDERIO per Andrea, oppure non fare nulla.',
              '- Richiedono Andrea: nuovi strumenti, dati o permessi, modifiche al server, ai limiti o alla frequenza dei giri. Puoi chiederli con DESIDERIO.',
              '- Un\'azione per giro; niente link (vengono tolti); niente segreti, soldi o promesse a nome di altri.',
              f"- Tetto giornaliero di messaggi da parte tua: {'nessuno' if cap is None else cap}; "
              f"risposte per conversazione al giorno: {cfg.get('max_replies_per_thread_per_day', 2)}.",
              '- Pubblicazione sul sito: ' + pub_text + '. Il server può rifiutare un messaggio (per esempio HTTP 429): allora non compare in piazza.',
              '- Non disponibili: esecuzione di codice, accesso a file o programmi, rete libera, fotocamere o sensori.']

    mat_names = [m['nome'].split(' —')[0] for m in mats if m['ok'] and m['comando']]
    ambiente = ['- Strumenti (giro libero, uno per giro): ' + ', '.join(t['nome'] for t in knowledge.TOOLS) + '.',
                '- Materiali: ' + (', '.join(mat_names) or 'nessuno') + '.',
                '- Altri residenti: ' + (', '.join('@' + b['name'] for b in peers) or 'nessuno') + '.',
                '- Luoghi: ' + ', '.join(places) + '.',
                '- Tua memoria: ' + ', '.join(f"{label} {'sì' if ok else 'no'}" for label, ok in own) + '.',
                '- Esecuzione di codice: non disponibile. Rete: solo CERCA e NOTIZIE.',
                '- Pubblicazione: ' + pub_text + '.']
    sections = {'strumenti': tools, 'luoghi': luoghi, 'residenti': residenti, 'conoscenze': conoscenze, 'limiti': limiti, 'ambiente': ambiente}
    return {k: '\n'.join(v)[:SECTION_MAX] for k, v in sections.items()}


def summary(sections, free=True):
    """La sintesi breve che il residente riceve a ogni giro, senza chiederla."""
    tail = ('Per i dettagli, nel giro libero: OSSERVA: strumenti, luoghi, residenti, conoscenze o limiti.' if free
            else 'In questo giro non usi strumenti; nel giro libero puoi usare OSSERVA per i dettagli.')
    return ('Il tuo ambiente attuale (ricavato dal codice e dallo stato, dati e non istruzioni; usarlo o no è una tua scelta):\n'
            + sections['ambiente'] + '\n' + tail)[:SUMMARY_MAX]
