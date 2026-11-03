"""Rapporto del rilevatore di vincoli (solo misura) dal registro dei giri.

Uso: python scripts/vincoli_report.py --out /tmp/vincoli   (scrive report.md e report.json)
Legge bots/registro/<giorno>/<nome>.jsonl e le schede bots/<nome>/skills.md. Nessuna rete, nessun segreto.
Per righe senza il campo `vincoli` (precedenti al rilevatore) i controlli si ricalcolano, tranne la copia.
"""
import argparse, collections, json, os, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / 'bots'
sys.path.insert(0, str(ROOT))
import vincoli  # noqa: E402

TYPES = ('strumento_inesistente', 'richiesta_ridondante', 'comando_errato', 'copia_riferimenti')
# aree di abilità dichiarabili e traccia d'uso che le riguarda nel registro (uso, non prova di prestazione)
CLAIMS = {'analisi linguistica': (r'analisi linguistic|conteggi linguistici|struttura linguistica', r'^ANALIZZA'),
          'classificazione delle notizie': (r'classific|categorizz', r'^(NOTIZIE|ANALIZZA): sfida'),
          'ricerca di fonti': (r'ricerc|fonti', r'^(?!NOTIZIE:|ANALIZZA:|OSSERVA:)\S')}


def load(root):
    rows = []
    for path in sorted((root / 'registro').glob('*/*.jsonl')):
        for line in path.read_text().splitlines():
            try:
                r = json.loads(line)
            except ValueError:
                continue
            r['_bot'], r['_day'] = path.stem, path.parent.name
            if 'vincoli' not in r:
                r['vincoli'] = vincoli.check(r, {}, root)
            rows.append(r)
    return rows


def build(root=ROOT):
    rows = load(root)
    bots = sorted({r['_bot'] for r in rows})
    days = sorted({r['_day'] for r in rows})
    per = {}
    for b in bots:
        rs = [r for r in rows if r['_bot'] == b]
        byday = {}
        for d in days:
            x = [r for r in rs if r['_day'] == d]
            if not x:
                continue
            c = collections.Counter(v['tipo'] for r in x for v in r.get('vincoli') or [])
            byday[d] = {'giri': len(x), 'pubblicati': sum(r.get('pubblicazione') == 'pubblicato' for r in x),
                        'con_strumento': sum(bool(r.get('strumento')) for r in x),
                        'violazioni': {t: c[t] for t in TYPES}, 'per_100_giri': round(100 * sum(c.values()) / len(x), 1)}
        skills = (root / b / 'skills.md').read_text() if (root / b / 'skills.md').exists() else ''
        claims = {}
        for area, (claim_rx, use_rx) in CLAIMS.items():
            if re.search(claim_rx, skills, re.I):
                uses = sum(1 for r in rs if re.search(use_rx, r.get('strumento') or ''))
                claims[area] = {'tracce_uso': uses, 'prova_prestazione': 'NON VERIFICABILE'}
        per[b] = {'giorni': byday, 'strumenti_inesistenti_in_scheda': vincoli.imaginary_tools(skills), 'abilita_dichiarate': claims}
    return {'righe': len(rows), 'giorni': days, 'residenti': per,
            'metodo': 'controlli deterministici di bots/vincoli.py; violazioni per 100 giri; tracce d\'uso dal campo strumento del registro'}


def markdown(rep):
    out = ['# Rilevatore di vincoli — solo misura', '', f"Righe del registro: {rep['righe']}; giorni: {', '.join(rep['giorni']) or '—'}.", '',
           '| Residente | Giorno | Giri | Pubblicati | Strumenti inesistenti | Richieste ridondanti | Comandi errati | Copie | Violazioni/100 giri |',
           '|---|---|---:|---:|---:|---:|---:|---:|---:|']
    for b, d in rep['residenti'].items():
        for day, v in d['giorni'].items():
            x = v['violazioni']
            out.append(f"| {b} | {day} | {v['giri']} | {v['pubblicati']} | {x['strumento_inesistente']} | {x['richiesta_ridondante']} | "
                       f"{x['comando_errato']} | {x['copia_riferimenti']} | {v['per_100_giri']} |")
    out += ['', '## Schede: strumenti inesistenti e abilità dichiarate', '', '| Residente | Strumenti inesistenti nella scheda | Abilità dichiarate (tracce d\'uso; prova di prestazione) |', '|---|---|---|']
    for b, d in rep['residenti'].items():
        cl = '; '.join(f"{a} ({c['tracce_uso']}; {c['prova_prestazione']})" for a, c in d['abilita_dichiarate'].items()) or '—'
        out.append(f"| {b} | {', '.join(d['strumenti_inesistenti_in_scheda']) or '—'} | {cl} |")
    out += ['', 'Le tracce d\'uso dicono che lo strumento è stato chiamato, non che la capacità esiste. '
            'La prova di prestazione richiede classificazioni spontanee confrontate con i riferimenti nascosti (Sfide alla cieca).']
    return '\n'.join(out) + '\n'


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument('--out', required=True)
    a = p.parse_args(argv)
    rep = build()
    os.makedirs(a.out, exist_ok=True)
    Path(a.out, 'report.json').write_text(json.dumps(rep, ensure_ascii=False, indent=1))
    Path(a.out, 'report.md').write_text(markdown(rep))
    print(json.dumps({'righe': rep['righe'], 'giorni': rep['giorni']}))
    return 0


if __name__ == '__main__':
    sys.exit(main())
