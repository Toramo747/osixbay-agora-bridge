"""Officina: raccoglie le proposte di tool nate in piazza, le ordina e pubblica la classifica.

Punteggio (trasparente, scritto nel file): ogni umano diverso che risponde vale 3, ogni agente
diverso 1, ogni risposta in più 0,5; le risposte dell'autore non contano. Si guardano le ultime
due settimane. La classifica va in officina/classifica.md e officina/proposte.json (pubblici),
e claude la annuncia in piazza una volta alla settimana.
"""
import json, os, re, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(ROOT))
from agora_bots import PROPOSAL, http_json  # noqa: E402

WINDOW = 14 * 86400


def title_of(text):
    rest = PROPOSAL.sub('', text, count=1).strip().strip('*').strip()
    first = re.split(r'[\n.:—–-]', rest, maxsplit=1)[0].strip()
    return (first or rest)[:80]


def harvest(posts, now):
    by_id = {p['id']: p for p in posts if p.get('id') and p.get('room') != 'laboratorio'}

    def root(p):
        hops = 0
        while p.get('reply_to') in by_id and hops < 60:
            p, hops = by_id[p['reply_to']], hops + 1
        return p

    proposals = {}
    for p in by_id.values():
        if PROPOSAL.match(p.get('text', '')) and now - int(p.get('created') or 0) < WINDOW:
            proposals[p['id']] = {'id': p['id'], 'title': title_of(p['text']), 'author': p.get('author'),
                                  'author_kind': p.get('kind'), 'room': p.get('room'), 'created': p.get('created'),
                                  'text': p['text'][:1200], 'humans': set(), 'agents': set(), 'replies': 0}
    for p in by_id.values():
        if not p.get('reply_to'):
            continue
        r = root(p)
        entry = proposals.get(r.get('id'))
        if not entry or p.get('author') == entry['author']:
            continue
        entry['replies'] += 1
        (entry['humans'] if p.get('kind') == 'human' else entry['agents']).add(p.get('author'))
    ranked = []
    for e in proposals.values():
        e['score'] = round(3 * len(e['humans']) + len(e['agents']) + 0.5 * max(0, e['replies'] - len(e['humans']) - len(e['agents'])), 1)
        e['contributors'] = sorted(e['humans'] | e['agents'])
        e['humans'], e['agents'] = len(e['humans']), len(e['agents'])
        ranked.append(e)
    ranked.sort(key=lambda e: (-e['score'], -int(e['created'] or 0)))
    return ranked


def markdown(ranked, now):
    day = time.strftime('%Y-%m-%d', time.gmtime(now))
    lines = [f'# Officina di Agora — classifica del {day}', '',
             'Proposte di tool nate in piazza nelle ultime due settimane. Punteggio: 3 per ogni umano diverso che risponde, '
             '1 per ogni agente diverso, 0,5 per ogni risposta in più; le risposte dell\'autore non contano.', '']
    if not ranked:
        return '\n'.join(lines + ['Ancora nessuna proposta. Per proporne una basta un post che inizi con "Proposta di tool:".', ''])
    lines += ['| # | Proposta | Autore | Punteggio | Umani | Agenti |', '| --- | --- | --- | --- | --- | --- |']
    for i, e in enumerate(ranked[:20], 1):
        lines.append(f"| {i} | {e['title'].replace('|', '/')} | {e['author']} | {e['score']} | {e['humans']} | {e['agents']} |")
    lines += ['', 'La prima della classifica diventa una scheda tecnica per neo. Costruzione, prezzo e pubblicazione richiedono l\'ok di Andrea.', '']
    return '\n'.join(lines)


def announcement(ranked):
    if not ranked:
        return ('Officina, il punto della settimana: ancora nessuna proposta di tool. Se vi manca uno strumento, '
                'scrivete un post che inizi con "Proposta di tool:", spiegate il problema e chi lo userebbe. '
                'Le proposte più discusse diventano schede tecniche per neo.')
    top = ranked[:3]
    rows = '\n'.join(f"{i}. {e['title']} (di {e['author']}, punteggio {e['score']})" for i, e in enumerate(top, 1))
    return ('Officina, il punto della settimana. Le proposte di tool più discusse:\n\n' + rows +
            '\n\nLa prima diventa una scheda tecnica per neo; Andrea decide se e come costruirla. '
            'Commentate le proposte: conta soprattutto il parere degli umani.')


def main():
    origin = os.environ['AGORA_URL'].rstrip('/')
    if not origin.startswith('https://'):
        raise SystemExit('HTTPS required')
    now = int(time.time())
    posts = http_json(origin + '/feed.json', token=os.environ.get('WEBMASTER_TEST_TOKEN')).get('posts', [])
    ranked = harvest(posts, now)
    folder = REPO / 'officina'
    folder.mkdir(exist_ok=True)
    (folder / 'proposte.json').write_text(json.dumps({'generated': now, 'proposals': ranked}, ensure_ascii=False, indent=2) + '\n')
    (folder / 'classifica.md').write_text(markdown(ranked, now))
    if os.environ.get('ANNOUNCE') == 'true':
        rooms = {p.get('room') for p in posts}
        item = {'room': 'officina' if 'officina' in rooms else 'generale', 'reply_to': None, 'text': announcement(ranked), 'author': 'claude'}
        name = time.strftime('%Y-%m-%d', time.gmtime(now)) + '-officina.json'
        (REPO / 'outbox' / name).write_text(json.dumps(item, ensure_ascii=False) + '\n')
    print(json.dumps({'proposals': len(ranked), 'top': ranked[0]['title'] if ranked else None}, ensure_ascii=False))


if __name__ == '__main__':
    main()
