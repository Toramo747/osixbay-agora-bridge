#!/usr/bin/env python3
"""Esegue gli esempi di genesis/knowledge/examples/*/test.gd con Godot headless isolato.

Un esempio è dichiarato funzionante solo se in QUESTA esecuzione: exit code 0 e riga EXAMPLE_OK.
Il risultato va in knowledge/reports/examples-validation.json (con versione Godot, data, tempi, output).

Uso:  python3 genesis/tools/validate_examples.py [nome_esempio ...]
"""
import datetime, json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import EXAMPLES, REPORTS, dump_json, lock  # noqa: E402
from godot_runner import run_godot  # noqa: E402

NEEDS_LOOPBACK = {'rete_enet'}


def validate(names=None):
    results = []
    for d in sorted(p for p in EXAMPLES.iterdir() if (p / 'test.gd').exists()):
        if names and d.name not in names:
            continue
        files = {f'{d.name}/{f.name}': f.read_text() for f in d.glob('*.gd')}
        r = run_godot(files, f'{d.name}/test.gd', timeout=120, allow_loopback=d.name in NEEDS_LOOPBACK)
        ok = bool(r.get('eseguito')) and r.get('exit_code') == 0 and 'EXAMPLE_OK' in r.get('output', '')
        tail = [l for l in r.get('output', '').splitlines() if l.strip() and not l.startswith('Godot Engine v')][-12:]
        results.append({'esempio': d.name, 'funzionante': ok, 'eseguito': r.get('eseguito', False),
                        'exit_code': r.get('exit_code'), 'secondi': r.get('secondi'), 'isolamento_rete': r.get('isolamento_rete'),
                        'motivo': r.get('motivo'), 'output': tail})
        print(f"{'OK  ' if ok else 'FAIL'} {d.name} ({r.get('secondi')}s)")
    return results


def main():
    names = set(sys.argv[1:]) or None
    results = validate(names)
    report = {'godot_version': lock()['godot_version'],
              'eseguito_il': datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat(),
              'superati': sum(r['funzionante'] for r in results), 'totale': len(results), 'risultati': results}
    if not names:
        dump_json(REPORTS / 'examples-validation.json', report)
    print(json.dumps({k: report[k] for k in ('superati', 'totale')}))
    return 0 if report['superati'] == report['totale'] else 1


if __name__ == '__main__':
    sys.exit(main())
