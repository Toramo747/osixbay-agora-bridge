"""Scarica i log dei job 'turn' di agora-bots ed estrae solo la sezione del giro (righe di output del residente).
Sola lettura. Non salva le righe di ambiente (env) né i comandi: solo l'output del giro.
Uso: python3 scarica_log.py <runs.tsv: id, creato, conclusione, evento> <cartella cache>
Un run già in cache non viene riscaricato; un run con errori di download non viene messo in cache."""
import json, os, subprocess, sys, concurrent.futures as cf

OUT = sys.argv[2]
os.makedirs(OUT, exist_ok=True)
R = 'repos/' + os.environ.get('GITHUB_REPOSITORY', 'Toramo747/osixbay-agora-bridge')


def gh(path):
    p = subprocess.run(['gh', 'api', path], capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError(f'{path}: {p.stderr.strip()[:200]}')
    return p.stdout


def section(log):
    lines, keep = [], False
    for l in log.splitlines():
        body = l[29:] if len(l) > 29 else l
        if body.startswith('##[group]Run python bots/agora_bots.py'):
            keep = True
            continue
        if keep and body.startswith('##[group]') and 'agora_bots' not in body:
            break
        if keep and not body.startswith(('  ', '[36;1m', '\x1b[36;1m', 'shell:', 'env:', '##[endgroup]')):
            lines.append(l)
    return lines


def do_run(rid, created):
    p = f'{OUT}/{rid}.json'
    if os.path.exists(p):
        return 'cache'
    try:
        jobs = json.loads(gh(f'{R}/actions/runs/{rid}/jobs?per_page=50'))['jobs']
        res = []
        for j in jobs:
            if not j['name'].startswith('turn'):
                continue
            log = gh(f'{R}/actions/jobs/{j["id"]}/logs') if j.get('conclusion') != 'skipped' else ''
            res.append({'job': j['id'], 'name': j['name'], 'conclusion': j['conclusion'], 'started': j['started_at'], 'lines': section(log)})
    except (RuntimeError, ValueError, KeyError) as e:
        print('salto', rid, e, file=sys.stderr)
        return 'errore'
    json.dump({'run': rid, 'created': created, 'jobs': res}, open(p, 'w'))
    return 'nuovo'


runs = [l.split('\t') for l in open(sys.argv[1]).read().splitlines() if l.strip()]
with cf.ThreadPoolExecutor(4) as ex:
    esiti = list(ex.map(lambda r: do_run(r[0], r[1]), [r for r in runs if len(r) > 2 and r[2]]))
print({k: esiti.count(k) for k in set(esiti)})
