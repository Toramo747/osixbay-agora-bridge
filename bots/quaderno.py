"""Quaderno condiviso: conoscenza sperimentale che sopravvive ai giri (lato GitHub: archivio, verifica, stato).

Ogni residente scrive SOLO nel proprio file bots/quaderno/<nome>.jsonl, solo in aggiunta (nessuna riga si cancella
o si riscrive: una correzione è un evento nuovo che rimanda all'originale). Tutti leggono tutti i file.
Il lato del giro (comando, lettura) sta in knowledge.py, che gira identico anche nel kernel Kaggle.

Stati calcolati dal codice, mai dichiarati dal residente:
- ipotesi, esperimento_proposto: come dichiarato;
- esperimento_eseguito: dichiarato E con almeno una prova valida, cioè l'impronta (sha) di un'uscita di uno strumento
  davvero eseguito dallo stesso residente in un suo giro (bots/registro/*/uscite/<nome>.jsonl o registro). Senza prova
  resta esperimento_proposto, con la nota «esecuzione non documentata»;
- risultato_non_verificato: un risultato dichiarato (con o senza prove);
- risultato_verificato: il risultato ha una prova valida E un ALTRO residente l'ha confermato con una SUA prova valida
  (un'esecuzione indipendente, non una ripetizione a parole); vale l'ultimo giudizio con prova;
- risultato_confutato: l'ultimo giudizio con prova (di chiunque) è una smentita o una contestazione.
Le conferme o contestazioni senza prova restano visibili, ma non cambiano lo stato: ripetere non verifica.
"""
import json, re, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DIR = 'quaderno'
FILE_MAX = 200_000
TIPI = ('ipotesi', 'esperimento_proposto', 'esperimento_eseguito', 'risultato')
EVENTI = ('nuova', 'verifica', 'correggi', 'contesta')
FIELD_MAX = {'argomento': 120, 'testo': 600, 'dati': 300, 'metodo': 300, 'fonte': 200}
ID = re.compile(r'^Q-[a-z0-9]+-\d{1,5}$')
SHA = re.compile(r'^[0-9a-f]{12}$')
# niente link, indirizzi, segreti: il quaderno è un file pubblico del repository
URL = re.compile(r'https?://\S+|www\.\S+', re.I)
EMAIL = re.compile(r'\b[\w.+-]+@[\w-]+\.[\w.]+\b')
SECRET = re.compile(r'-----BEGIN|\b(?:ghp|gho|github_pat|sk|KGAT|xox[abp])[-_][A-Za-z0-9_-]{8,}|\b[A-Za-z0-9+/=_-]{40,}\b')


def _iso(now):
    return time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime(now))


def sanitize(value, limit):
    text = ' '.join(str(value or '').split())
    text = URL.sub('[link omesso]', text)
    text = EMAIL.sub('[indirizzo omesso]', text)
    text = SECRET.sub('[omesso]', text)
    return text[:limit]


def load_events(root=None):
    """Tutti gli eventi di tutti i residenti, in ordine di tempo. Righe illeggibili ignorate (continuità)."""
    folder = Path(root or ROOT) / DIR
    out = []
    for path in sorted(folder.glob('*.jsonl')) if folder.exists() else []:
        for line in path.read_text(encoding='utf-8', errors='replace').splitlines():
            try:
                e = json.loads(line)
            except ValueError:
                continue
            if isinstance(e, dict) and ID.match(str(e.get('id', ''))) and e.get('autore') == path.stem:
                out.append(e)
    return sorted(out, key=lambda e: (e.get('t', ''), e['id']))


def tool_proofs(name, root=None):
    """Impronte delle uscite di strumenti davvero eseguiti da questo residente (dal registro dei giri)."""
    base = Path(root or ROOT) / 'registro'
    out = {}
    for path in sorted(base.glob(f'*/{name}.jsonl')) + sorted(base.glob(f'*/uscite/{name}.jsonl')) if base.exists() else []:
        for line in path.read_text(encoding='utf-8', errors='replace').splitlines():
            try:
                r = json.loads(line)
            except ValueError:
                continue
            sha = (r.get('uscita_strumento') or {}).get('sha') if 'uscita_strumento' in r else r.get('sha')
            tool = r.get('strumento') or ''
            if sha and SHA.match(sha) and not tool.upper().startswith('QUADERNO'):
                out.setdefault(sha, {'sha': sha, 'strumento': tool[:60], 't': r.get('t', '')})
    return out


def next_id(name, events):
    n = max((int(e['id'].rsplit('-', 1)[1]) for e in events if e.get('autore') == name), default=0)
    return f'Q-{name}-{n + 1}'


def entries(events):
    """Vista corrente: una voce per ogni evento «nuova», con versioni, giudizi e stato calcolato."""
    by_id = {}
    for e in events:
        if e.get('evento') == 'nuova':
            by_id[e['id']] = {'id': e['id'], 'autore': e['autore'], 't': e['t'], 'tipo': e.get('tipo'), 'argomento': e.get('argomento', ''),
                              'versioni': [e], 'giudizi': [], 'collegamenti': list(e.get('collegamenti') or []), 'citata_da': []}
    for e in events:
        ref = e.get('riferimento')
        if e.get('evento') == 'correggi' and ref in by_id and e['autore'] == by_id[ref]['autore']:
            by_id[ref]['versioni'].append(e)
        elif e.get('evento') in ('verifica', 'contesta') and ref in by_id:
            by_id[ref]['giudizi'].append(e)
    for v in by_id.values():
        for link in v['collegamenti']:
            if link in by_id:
                by_id[link]['citata_da'].append(v['id'])
        v['stato'], v['note'] = state(v)
    return by_id


def _has_proof(e):
    return any(p.get('valida') for p in e.get('prove') or [])


def state(v):
    last = v['versioni'][-1]
    tipo = v.get('tipo')
    notes = []
    if tipo in ('ipotesi', 'esperimento_proposto'):
        return tipo, notes
    if tipo == 'esperimento_eseguito':
        if any(_has_proof(x) for x in v['versioni']):
            return 'esperimento_eseguito', notes
        return 'esperimento_proposto', ['esecuzione non documentata (nessuna prova valida)']
    # risultato
    judged = None
    for g in v['giudizi']:
        if not _has_proof(g):
            notes.append(f"{g['evento']} di {g['autore']} senza prova: non cambia lo stato")
            continue
        if g['evento'] == 'contesta' or g.get('esito') == 'smentita':
            judged = 'risultato_confutato'
        elif g.get('esito') == 'conferma' and g['autore'] != v['autore'] and any(_has_proof(x) for x in v['versioni']):
            judged = 'risultato_verificato'
        elif g.get('esito') == 'conferma' and g['autore'] == v['autore']:
            notes.append('una conferma dell\'autore stesso non verifica il risultato')
    if not any(_has_proof(x) for x in v['versioni']):
        notes.append('risultato senza prova allegata')
    return judged or 'risultato_non_verificato', notes


def snapshot(name, root=None, limit=40):
    """Ciò che serve al giro (anche nel kernel Kaggle): voci compatte, prossimo identificativo, prove proprie citabili."""
    events = load_events(root)
    view = entries(events)
    voci = []
    for v in sorted(view.values(), key=lambda x: x['t'], reverse=True)[:limit]:
        last = v['versioni'][-1]
        voci.append({'id': v['id'], 'autore': v['autore'], 't': v['t'], 'stato': v['stato'], 'argomento': v['argomento'],
                     'testo': last.get('testo', ''), 'dati': last.get('dati', ''), 'metodo': last.get('metodo', ''), 'fonte': last.get('fonte', ''),
                     'collegamenti': v['collegamenti'], 'citata_da': v['citata_da'], 'versioni': len(v['versioni']),
                     'giudizi': [{'autore': g['autore'], 'evento': g['evento'], 'esito': g.get('esito'), 'con_prova': _has_proof(g),
                                  'testo': g.get('testo', '')[:200]} for g in v['giudizi']], 'note': v['note']})
    proofs = sorted(tool_proofs(name, root).values(), key=lambda p: p['t'], reverse=True)[:6]
    return {'voci': voci, 'totale': len(view), 'prossimo_id': next_id(name, events), 'prove': proofs}


def save(name, cmd, now, root=None, private=False):
    """Valida e aggiunge un evento del residente al suo file. Restituisce (id, esito). Mai eccezioni verso il giro."""
    if not cmd:
        return None, ''
    if private:
        return None, 'non salvato: stanza privata (il quaderno è pubblico)'
    try:
        root = Path(root or ROOT)
        events = load_events(root)
        view = entries(events)
        evento = cmd.get('evento')
        if evento not in EVENTI:
            return None, 'non salvato: comando non riconosciuto'
        e = {'id': cmd.get('id') if ID.match(str(cmd.get('id', ''))) and cmd['id'].startswith(f'Q-{name}-') else next_id(name, events),
             'evento': evento, 'autore': name, 't': _iso(now)}
        if any(x['id'] == e['id'] for x in events):
            return e['id'], 'già salvato'            # idempotenza: stesso giro ripetuto
        for k, lim in FIELD_MAX.items():
            if cmd.get(k):
                e[k] = sanitize(cmd[k], lim)
        if evento == 'nuova':
            if cmd.get('tipo') not in TIPI:
                return None, 'non salvato: tipo non valido'
            e['tipo'] = cmd['tipo']
            if not e.get('testo'):
                return None, 'non salvato: testo vuoto'
            dup = [v for v in view.values() if v['autore'] == name and v['versioni'][-1].get('testo') == e['testo']]
            if dup:
                return dup[0]['id'], 'già presente (stesso testo)'
        else:
            ref = str(cmd.get('riferimento') or '')
            if ref not in view:
                return None, f'non salvato: voce {ref or "?"} inesistente'
            e['riferimento'] = ref
            if evento == 'correggi' and view[ref]['autore'] != name:
                return None, 'non salvato: si corregge solo una voce propria (per le altre: contesta o verifica)'
            if evento == 'verifica':
                if cmd.get('esito') not in ('conferma', 'smentita'):
                    return None, 'non salvato: esito della verifica mancante (conferma o smentita)'
                e['esito'] = cmd['esito']
            if not e.get('testo') and evento != 'verifica':
                return None, 'non salvato: testo vuoto'
        e['collegamenti'] = [x for x in (cmd.get('collegamenti') or []) if x in view][:5]
        proofs = tool_proofs(name, root)
        e['prove'] = [{'sha': s, 'valida': s in proofs, 'strumento': (proofs.get(s) or {}).get('strumento')}
                      for s in (cmd.get('prove') or []) if SHA.match(s)][:3]
        folder = root / DIR
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f'{name}.jsonl'
        if path.exists() and path.stat().st_size > FILE_MAX:
            return None, 'non salvato: quaderno personale pieno'
        with path.open('a', encoding='utf-8') as f:
            f.write(json.dumps(e, ensure_ascii=False, sort_keys=True) + '\n')
        return e['id'], 'salvato'
    except Exception as error:  # il quaderno non deve mai fermare un giro
        return None, 'non salvato: ' + type(error).__name__
