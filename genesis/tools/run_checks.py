#!/usr/bin/env python3
"""Esegue le domande di controllo (knowledge/tests/questions.json) e scrive il rapporto dei test.

Per ogni domanda registra: risultato recuperato, fonte, correttezza rispetto alla documentazione
(confronto con la verità di riferimento in 'atteso'), compatibilità di versione, tempo di risposta.

Uso:  python3 genesis/tools/run_checks.py
"""
import datetime, json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import KNOWLEDGE, REPORTS, dump_json, load_json, lock  # noqa: E402
from godot_api import GodotLibrary  # noqa: E402


def evaluate(res, exp, version):
    errs = []
    if 'trovato' in exp and res['trovato'] != exp['trovato']:
        errs.append(f"trovato={res['trovato']} atteso {exp['trovato']}")
    if 'url' in exp and not any(exp['url'] in r['url'] for r in res['riferimenti'][:3]):
        errs.append(f"nessun riferimento entro i primi 3 contiene {exp['url']}")
    if 'firma' in exp and not any(exp['firma'] in f['firma'] for f in res.get('firme', [])):
        errs.append(f"firma senza '{exp['firma']}'")
    if 'livello' in exp and res['livello_verifica'] != exp['livello']:
        errs.append(f"livello {res['livello_verifica']} atteso {exp['livello']}")
    if 'non_livello' in exp and res['livello_verifica'] == exp['non_livello']:
        errs.append(f"livello {res['livello_verifica']} non ammesso")
    if 'voce' in exp and res.get('voce') != exp['voce']:
        errs.append(f"voce {res.get('voce')} attesa {exp['voce']}")
    if 'stato' in exp and res.get('stato') != exp['stato']:
        errs.append(f"stato {res.get('stato')} atteso {exp['stato']}")
    if 'ereditarieta' in exp and exp['ereditarieta'] not in res.get('ereditarieta', []):
        errs.append(f"ereditarietà senza {exp['ereditarieta']}")
    if 'valido' in exp and res.get('valido') != exp['valido']:
        errs.append(f"valido={res.get('valido')} atteso {exp['valido']}")
    for t in exp.get('problemi', []):
        if t not in {p['tipo'] for p in res.get('problemi', [])}:
            errs.append(f'problema {t} non rilevato')
    if 'alternativa' in exp and exp['alternativa'] not in res['alternative']:
        errs.append(f"alternativa {exp['alternativa']} assente")
    version_ok = res['versione_godot'] == version and all(r['versione'] == version for r in res['riferimenti'])
    if not version_ok:
        errs.append('versione diversa da quella fissata')
    return errs, version_ok


def run():
    lib = GodotLibrary()
    version = lock()['godot_version']
    qs = load_json(KNOWLEDGE / 'tests' / 'questions.json')['domande']
    out = []
    for q in qs:
        res = lib.handle(q['comando'])
        errs, vok = evaluate(res, q['atteso'], version)
        out.append({'id': q['id'], 'categoria': q['categoria'], 'comando': q['comando'].split('\n')[0][:90],
                    'superato': not errs, 'errori': errs, 'trovato': res['trovato'],
                    'risultato': res['spiegazione'][:160],
                    'fonte': res['riferimenti'][0]['url'] if res['riferimenti'] else None,
                    'livello_verifica': res['livello_verifica'], 'versione_compatibile': vok, 'tempo_ms': res['tempo_ms']})
    return out


def write_report(results):
    passed = sum(r['superato'] for r in results)
    times = sorted(r['tempo_ms'] for r in results)
    rep = {'godot_version': lock()['godot_version'],
           'eseguito_il': datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat(),
           'superati': passed, 'falliti': len(results) - passed, 'totale': len(results),
           'negativi': sum(r['categoria'].startswith('negativo') for r in results),
           'tempo_mediano_ms': times[len(times) // 2], 'tempo_max_ms': times[-1], 'risultati': results}
    dump_json(REPORTS / 'test-results.json', rep)
    lines = [f"# Risultati delle domande di controllo — Godot {rep['godot_version']}", '',
             f"Eseguito il {rep['eseguito_il']}. Superati **{passed}/{len(results)}** "
             f"(di cui {rep['negativi']} test negativi). Tempo mediano {rep['tempo_mediano_ms']} ms, massimo {rep['tempo_max_ms']} ms.",
             '', '| id | categoria | esito | livello | ms | fonte / errori |', '|---|---|---|---|---|---|']
    for r in results:
        detail = '; '.join(r['errori']) if r['errori'] else (r['fonte'] or '—')
        lines.append(f"| {r['id']} | {r['categoria']} | {'OK' if r['superato'] else 'FALLITO'} | {r['livello_verifica']} | "
                     f"{r['tempo_ms']} | {detail.replace('|', '/')} |")
    (REPORTS / 'test-results.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    return rep


if __name__ == '__main__':
    rep = write_report(run())
    for r in rep['risultati']:
        if not r['superato']:
            print('FALLITO', r['id'], r['errori'])
    print(f"superati {rep['superati']}/{rep['totale']}")
    sys.exit(0 if rep['falliti'] == 0 else 1)
