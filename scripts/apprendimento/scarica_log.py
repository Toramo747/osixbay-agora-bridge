"""Scarica i log dei job 'turn' di agora-bots ed estrae solo la sezione del giro. Sola lettura."""
import json, subprocess, sys, os, concurrent.futures as cf
OUT = sys.argv[2]; os.makedirs(OUT, exist_ok=True)
R = 'repos/Toramo747/osixbay-agora-bridge'
def gh(path):
    return subprocess.run(['gh', 'api', path], capture_output=True, text=True).stdout
def section(log):
    lines, keep = [], False
    for l in log.splitlines():
        body = l[29:] if len(l) > 29 else l
        if body.startswith('##[group]Run python bots/agora_bots.py'): keep = True; continue
        if keep and body.startswith('##[group]') and 'agora_bots' not in body: break
        if keep and not body.startswith(('  ', '[36;1m', 'shell:', 'env:', '##[endgroup]')): lines.append(l)
    return lines
def do_run(rid, created):
    p = f'{OUT}/{rid}.json'
    if os.path.exists(p): return
    jobs = json.loads(gh(f'{R}/actions/runs/{rid}/jobs?per_page=50') or '{"jobs":[]}')['jobs']
    res = []
    for j in jobs:
        if not j['name'].startswith('turn'): continue
        log = gh(f'{R}/actions/jobs/{j["id"]}/logs')
        res.append({'job': j['id'], 'name': j['name'], 'conclusion': j['conclusion'],
                    'started': j['started_at'], 'lines': section(log)})
    json.dump({'run': rid, 'created': created, 'jobs': res}, open(p, 'w'))
runs = [l.split('\t') for l in open(sys.argv[1]).read().splitlines()]
with cf.ThreadPoolExecutor(6) as ex:
    list(ex.map(lambda r: do_run(r[0], r[1]), [r for r in runs if r[2]]))
print('ok')
