"""Monitor di affidabilità della staffetta dei residenti (workflow agora-bots).

Misura, con i soli dati pubblici di GitHub Actions, quanto la staffetta introdotta dalla PR #51
tiene davvero i giri regolari: avvii per origine (cron, manuale, staffetta), esiti, intervalli
reali fra un giro e l'altro, interruzioni della catena, continuità operativa e confronto con il
periodo precedente alla PR. Solo lettura: nessun segreto, nessuna API a pagamento, nessun avvio
di workflow. Non tocca residenti, prompt, memoria né i limiti della staffetta.

Uso:
  python scripts/staffetta_monitor.py fetch   --repo Toramo747/osixbay-agora-bridge --out /tmp/sm/snapshot.json
  python scripts/staffetta_monitor.py analyze /tmp/sm/snapshot.json --out /tmp/sm/report
  python scripts/staffetta_monitor.py run     --repo ... --out /tmp/sm/report   (fetch + analyze)

`fetch` richiede GH_TOKEN (o GITHUB_TOKEN) con permesso `actions: read`; salva un'istantanea
ridotta ai campi necessari, riproducibile. `analyze` lavora solo sull'istantanea: stessa
istantanea, stesso rapporto. Scrive report.json, report.md e timeline.svg.

Un giro è "verificato" solo se il run è riuscito, almeno un job `turn (<bot>)` è riuscito e il
job `remember` (salvataggio dei diari) è riuscito. L'esito `success` di GitHub da solo non basta.
Quel che i residenti hanno scritto nel giro (efficienza cognitiva) non si misura qui.
"""
import argparse, json, os, statistics, sys, time, urllib.error, urllib.parse, urllib.request
from datetime import datetime, timezone

API = 'https://api.github.com'
WORKFLOW_FILE = 'bots.yml'
PR51_MERGED_AT = '2026-11-01T16:44:59Z'   # unione della staffetta (PR #51)
GAP_LIMIT_MIN = 60                         # catena interrotta oltre questo silenzio
DUPLICATE_WINDOW_S = 120                   # due avvii più vicini di così sono doppioni
DEFAULT_GAP_MIN = 20                       # intervallo minimo della staffetta (STAFFETTA_MINUTES)
DEFAULT_MAX_DAY = 80                       # tetto giornaliero (STAFFETTA_MAX_PER_DAY)
ACTIVE = {'queued', 'in_progress', 'waiting', 'pending', 'requested'}
VERSION = 1


# ---------- tempo ----------

def ts(value):
    """ISO 8601 di GitHub -> secondi UTC (0 se assente)."""
    return int(datetime.fromisoformat(value.replace('Z', '+00:00')).timestamp()) if value else 0


def iso(seconds):
    return datetime.fromtimestamp(int(seconds), timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def clamp(value, low, high, default):
    try:
        return max(low, min(high, int(value)))
    except (TypeError, ValueError):
        return default


# ---------- raccolta (sola lettura) ----------

class GitHub:
    def __init__(self, token, repo, sleep=0.0):
        self.token, self.repo, self.sleep = token, repo, sleep
        self.calls = 0

    def get(self, path, params=None):
        url = f'{API}/repos/{self.repo}/{path}'
        if params:
            url += ('&' if '?' in url else '?') + urllib.parse.urlencode(params)
        req = urllib.request.Request(url, headers={
            'Accept': 'application/vnd.github+json', 'X-GitHub-Api-Version': '2022-11-28',
            'User-Agent': 'osixbay-staffetta-monitor', **({'Authorization': f'Bearer {self.token}'} if self.token else {})})
        self.calls += 1
        if self.sleep:
            time.sleep(self.sleep)
        with urllib.request.urlopen(req, timeout=60) as response:
            return json.load(response)

    def paginate(self, path, key, params=None):
        page, out = 1, []
        while True:
            data = self.get(path, {**(params or {}), 'per_page': 100, 'page': page})
            items = data.get(key, [])
            out += items
            if len(items) < 100:
                return out
            page += 1


def slim_run(run):
    actor = (run.get('triggering_actor') or run.get('actor') or {}).get('login', '')
    return {'id': run['id'], 'event': run.get('event'), 'status': run.get('status'), 'conclusion': run.get('conclusion'),
            'created_at': run.get('created_at'), 'run_started_at': run.get('run_started_at'),
            'updated_at': run.get('updated_at'), 'run_attempt': run.get('run_attempt', 1), 'actor': actor,
            'html_url': run.get('html_url')}


def slim_job(job):
    return {'id': job['id'], 'name': job.get('name'), 'status': job.get('status'), 'conclusion': job.get('conclusion'),
            'started_at': job.get('started_at'), 'completed_at': job.get('completed_at')}


DIARY_COMMIT = 'Residents: update diaries'   # commit del job remember (quelli Kaggle hanno un altro testo)
DECISIONS_TO_FETCH = 12                      # annotazioni della staffetta solo per gli ultimi giri
TURN_NOTES_TO_FETCH = 12                     # annotazioni dei job turn (giri a vuoto) solo per gli ultimi giri


def turn_note_kind(message):
    """Avvisi di agora_bots.py: 'HTTP <code> on <percorso>' = il residente non ha pubblicato (il job
    esce comunque con 0); '... passo al successivo' = API gratuita saltata, lavoro fatto col fallback."""
    message = str(message or '')
    if message.startswith('HTTP ') and ' on ' in message:
        return 'vuoto'
    if 'passo al successivo' in message:
        return 'degradato'
    return None


def fetch(repo, since, token, workflow=WORKFLOW_FILE, jobs_since=None, decisions=DECISIONS_TO_FETCH,
          turn_notes=TURN_NOTES_TO_FETCH, baseline=None, log=print):
    """Scarica un'istantanea ridotta: run del workflow dal momento `since`, job (dal momento
    `jobs_since` e per la finestra di confronto `baseline` = (inizio, fine)), annotazioni della
    staffetta e dei job turn per gli ultimi giri, commit dei diari. Nessun segreto, nessun log di
    job. Circa 1 chiamata per run, più 1 per job annotato."""
    gh = GitHub(token, repo)
    missing = []
    try:
        runs = [slim_run(r) for r in gh.paginate(f'actions/workflows/{workflow}/runs', 'workflow_runs', {'created': f'>={since}'})]
    except (urllib.error.URLError, KeyError, ValueError) as error:
        raise SystemExit(f'elenco dei run non disponibile: {error}')
    runs.sort(key=lambda r: ts(r['created_at']))
    log(f'run trovati: {len(runs)} (dal {since})')

    def wanted(run):
        created = ts(run['created_at'])
        if baseline and ts(baseline[0]) <= created < ts(baseline[1]):
            return True
        return not jobs_since or created >= ts(jobs_since)
    detailed = [r for r in runs if wanted(r)]
    for run in detailed:
        try:
            jobs = gh.paginate(f"actions/runs/{run['id']}/jobs", 'jobs', {'filter': 'latest'})
            run['jobs'] = [slim_job(j) for j in jobs]
        except (urllib.error.URLError, KeyError, ValueError) as error:
            missing.append(f"job del run {run['id']}: {error}")
    recent = [r for r in detailed if r.get('jobs') and r.get('status') == 'completed']
    for run in recent[-decisions:]:
        staffetta = next((j for j in run['jobs'] if j.get('name') == 'staffetta'), None)
        if not staffetta or staffetta.get('conclusion') != 'success':
            continue
        run['staffetta_notes'] = []
        try:
            notes = gh.get(f"check-runs/{staffetta['id']}/annotations", {'per_page': 100})
            run['staffetta_notes'] = [n.get('message', '') for n in notes if n.get('title') == 'staffetta']
        except (urllib.error.URLError, ValueError) as error:
            missing.append(f"annotazioni della staffetta del run {run['id']}: {error}")
    for run in recent[-turn_notes:]:
        notes, ok = {}, True
        for job in run['jobs']:
            if not str(job.get('name', '')).startswith('turn') or job.get('conclusion') != 'success':
                continue
            try:
                found = gh.get(f"check-runs/{job['id']}/annotations", {'per_page': 100})
                notes[job['name']] = [k for k in (turn_note_kind(n.get('message')) for n in found
                                          if n.get('annotation_level') == 'warning' and str(n.get('title', '')).startswith('bot ')) if k]
            except (urllib.error.URLError, ValueError) as error:
                missing.append(f"annotazioni dei turni del run {run['id']}: {error}")
                ok = False
                break
        if ok:
            run['turn_notes'] = notes
    try:
        commits = _commits(gh, since)
    except (urllib.error.URLError, ValueError) as error:
        commits, missing = [], missing + [f'commit dei diari: {error}']
    log(f'chiamate API: {gh.calls}; lacune: {len(missing)}')
    return {'version': VERSION, 'repo': repo, 'workflow': workflow, 'since': since, 'jobs_since': jobs_since,
            'fetched_at': iso(time.time()), 'runs': runs, 'diary_commits': commits, 'fetch_missing': missing}


def _commits(gh, since):
    out, page = [], 1
    while True:
        data = gh.get('commits', {'author': 'agora-bots[bot]@users.noreply.github.com', 'since': since, 'per_page': 100, 'page': page})
        out += [{'sha': c['sha'], 'date': c['commit']['author']['date'], 'message': c['commit']['message'].split('\n')[0]} for c in data]
        if len(data) < 100:
            return [c for c in out if c['message'] == DIARY_COMMIT]
        page += 1


# ---------- classificazione ----------

def trigger_of(run):
    if run.get('event') == 'schedule':
        return 'cron'
    if run.get('event') == 'workflow_dispatch':
        actor = (run.get('actor') or '').lower()
        return 'staffetta' if actor.endswith('[bot]') else 'manuale'
    return 'altro'


def status_of(run):
    if run.get('status') in ACTIVE or run.get('status') != 'completed':
        return 'in_corso'
    return {'success': 'completato', 'failure': 'fallito', 'cancelled': 'annullato', 'skipped': 'saltato',
            'timed_out': 'scaduto', 'startup_failure': 'fallito'}.get(run.get('conclusion'), 'altro')


def classify(run, diary_commits=()):
    """Record normalizzato di un run. I job possono mancare (dati incompleti)."""
    jobs = run.get('jobs')
    created, started = ts(run.get('created_at')), ts(run.get('run_started_at')) or ts(run.get('created_at'))
    rec = {'id': run['id'], 'url': run.get('html_url'), 'trigger': trigger_of(run), 'status': status_of(run),
           'created': created, 'started': started, 'attempt': run.get('run_attempt') or 1,
           'jobs_known': jobs is not None, 'suspended': False, 'superseded': False,
           'turn_ok': 0, 'turn_failed': 0, 'turn_total': 0, 'turn_empty': None, 'turn_degraded': None,
           'remember': None, 'diary_commit': None, 'staffetta_job': None, 'decision': None,
           'decision_fetched': run.get('staffetta_notes') is not None,
           'verified': False, 'partial': False, 'duplicate': False}
    rec['ended'] = ts(run.get('updated_at')) if rec['status'] != 'in_corso' else None
    rec['duration_s'] = (rec['ended'] - created) if rec['ended'] else None
    if jobs is not None:
        plan = next((j for j in jobs if j.get('name') == 'plan'), None)
        turns = [j for j in jobs if str(j.get('name', '')).startswith('turn') and j.get('conclusion') != 'skipped']
        rec['turn_total'] = len(turns)
        rec['turn_ok'] = sum(1 for j in turns if j.get('conclusion') == 'success')
        rec['turn_failed'] = sum(1 for j in turns if j.get('conclusion') in ('failure', 'timed_out', 'cancelled'))
        remember = next((j for j in jobs if j.get('name') == 'remember'), None)
        rec['remember'] = remember.get('conclusion') if remember else None
        staffetta = next((j for j in jobs if j.get('name') == 'staffetta'), None)
        rec['staffetta_job'] = staffetta.get('conclusion') if staffetta else None
        never_started = not jobs or all(j.get('conclusion') in ('cancelled', 'skipped', None) and not j.get('started_at') for j in jobs)
        # sostituito: annullato in coda prima di partire (concurrency di GitHub), non è un giro fallito
        rec['superseded'] = rec['status'] == 'annullato' and never_started
        # sospeso: interruttori spenti (plan saltato) o nessun residente da far girare
        rec['suspended'] = not rec['superseded'] and rec['status'] != 'in_corso' and (
            (plan is not None and plan.get('conclusion') == 'skipped') or
            (not turns and plan is not None and plan.get('conclusion') == 'success'))
        if remember and remember.get('conclusion') == 'success' and remember.get('started_at'):
            lo, hi = ts(remember['started_at']), ts(remember.get('completed_at') or remember['started_at']) + 120
            rec['diary_commit'] = any(lo - 5 <= ts(c['date']) <= hi for c in diary_commits)
        notes = run.get('turn_notes')
        if notes is not None:
            rec['turn_empty'] = sum(1 for kinds in notes.values() if 'vuoto' in kinds)
            rec['turn_degraded'] = sum(1 for kinds in notes.values() if 'degradato' in kinds and 'vuoto' not in kinds)
        worked = rec['turn_ok'] - (rec['turn_empty'] or 0)
        rec['verified'] = rec['status'] == 'completato' and worked > 0 and rec['remember'] == 'success'
        # parziale: GitHub dice failure (un residente è caduto) ma altri hanno girato e la memoria è salva
        rec['partial'] = rec['status'] in ('fallito', 'scaduto') and worked > 0 and rec['remember'] == 'success'
    elif rec['status'] == 'annullato' and not run.get('run_started_at'):
        rec['superseded'] = True
    for note in run.get('staffetta_notes') or []:
        try:
            rec['decision'] = json.loads(note)   # l'ultima decisione è quella che conta
        except ValueError:
            pass
    return rec


def mark_duplicates(records):
    """Avvii distinti a meno di DUPLICATE_WINDOW_S l'uno dall'altro: il secondo è un doppione."""
    last = None
    for rec in sorted(records, key=lambda r: r['created']):
        if rec['suspended'] or rec['superseded']:
            continue
        if last is not None and rec['created'] - last < DUPLICATE_WINDOW_S:
            rec['duplicate'] = True
        else:
            last = rec['created']
    return records


# ---------- analisi di una finestra ----------

def pct(num, den):
    return round(100.0 * num / den, 1) if den else None


def _stats(values):
    if not values:
        return {'n': 0, 'media': None, 'mediana': None, 'min': None, 'max': None}
    return {'n': len(values), 'media': round(statistics.mean(values), 1), 'mediana': round(statistics.median(values), 1),
            'min': round(min(values), 1), 'max': round(max(values), 1)}


def analyze_window(records, start, end, data_start=None, gap_min=DEFAULT_GAP_MIN, max_day=DEFAULT_MAX_DAY,
                   gap_limit_min=GAP_LIMIT_MIN, diary_commits=()):
    """Indicatori nella finestra [start, end). `data_start`: da quando i dati esistono (finestra
    parziale se successivo a start). Tempi in secondi UTC."""
    inside = sorted((r for r in records if start <= r['created'] < end), key=lambda r: r['created'])
    partial = data_start is not None and data_start > start
    eff_start = max(start, data_start) if partial else start
    span_min = max(0, (end - eff_start)) / 60
    out = {'inizio': iso(start), 'fine': iso(end), 'ore': round((end - start) / 3600, 1), 'parziale': partial,
           'dati_da': iso(eff_start), 'minuti_osservati': round(span_min, 1)}
    by_trigger = {k: sum(1 for r in inside if r['trigger'] == k) for k in ('cron', 'manuale', 'staffetta', 'altro')}
    by_status = {k: sum(1 for r in inside if r['status'] == k) for k in ('completato', 'fallito', 'annullato', 'in_corso', 'saltato', 'scaduto', 'altro')}
    suspended = [r for r in inside if r['suspended']]
    dups = [r for r in inside if r['duplicate']]
    superseded = [r for r in inside if r['superseded']]
    effective = [r for r in inside if not r['suspended'] and not r['duplicate'] and not r['superseded']]
    finished = [r for r in effective if r['status'] != 'in_corso']
    ok = [r for r in finished if r['status'] == 'completato']
    verified = [r for r in finished if r['verified']]
    unknown_jobs = [r for r in finished if not r['jobs_known']]
    out.update({
        'avviati': len(inside), 'per_origine': by_trigger, 'per_esito': by_status,
        'sospesi': len(suspended), 'duplicati': len(dups), 'sostituiti': len(superseded), 'retry': sum(1 for r in inside if r['attempt'] > 1),
        'effettivi': len(effective), 'conclusi': len(finished), 'in_corso': len(effective) - len(finished),
        'completati': len(ok), 'verificati': len(verified), 'falliti': sum(1 for r in finished if r['status'] in ('fallito', 'scaduto')),
        'annullati': sum(1 for r in finished if r['status'] == 'annullato'),
        'success_rate': pct(len(ok), len(finished)), 'verified_rate': pct(len(verified), len(finished)),
        'parziali': sum(1 for r in finished if r['partial']),
        'job_sconosciuti': len(unknown_jobs),
        'turni_ok': sum(r['turn_ok'] for r in finished), 'turni_falliti': sum(r['turn_failed'] for r in finished),
        'turni_controllati': sum(r['turn_ok'] for r in finished if r['turn_empty'] is not None),
        'turni_a_vuoto': sum(r['turn_empty'] or 0 for r in finished),
        'turni_degradati': sum(r['turn_degraded'] or 0 for r in finished),
        'giri_con_commit_diari': sum(1 for r in finished if r['diary_commit']),
        'catena_dopo_giro': sum(1 for r in ok if r['staffetta_job'] == 'success'),
        'catena_non_prenotata': sum(1 for r in finished if r['remember'] == 'success' and r['staffetta_job'] in ('skipped', 'failure', 'cancelled')),
        'memoria_salvata': sum(1 for r in finished if r['remember'] == 'success'),
        'memoria_fallita': sum(1 for r in finished if r['remember'] in ('failure', 'cancelled', 'timed_out')),
        'commit_diari': sum(1 for c in diary_commits if start <= ts(c['date']) < end),
    })
    checked = out['turni_controllati']
    out['lavoro_rate'] = pct(checked - out['turni_a_vuoto'], checked)
    # intervalli reali fra avvii effettivi
    gaps = [(effective[i + 1]['created'] - effective[i]['created']) / 60 for i in range(len(effective) - 1)]
    out['intervalli_min'] = _stats(gaps)
    chained = [(effective[i + 1]['created'] - effective[i]['created']) / 60 for i in range(len(effective) - 1)
               if effective[i + 1]['trigger'] == 'staffetta']
    out['intervalli_staffetta_min'] = _stats(chained)
    durations = [r['duration_s'] / 60 for r in finished if r['duration_s'] is not None]
    out['durata_giro_min'] = _stats(durations)
    # interruzioni (> gap_limit) comprese testa e coda della finestra; le pause sospese non contano
    limit = gap_limit_min * 60
    kept = [r for r in inside if not r['duplicate'] and not r['superseded']]
    points = [eff_start] + [r['created'] for r in kept] + [end]
    kinds = ['inizio'] + [('sospeso' if r['suspended'] else 'giro') for r in kept] + ['fine']
    interruptions, suspended_s, covered_s = [], 0, 0
    for i in range(len(points) - 1):
        length = points[i + 1] - points[i]
        if kinds[i] == 'sospeso':
            suspended_s += length
            continue
        if kinds[i] == 'inizio' and partial:
            covered_s += min(length, limit)   # non sappiamo cosa c'era prima: non si conta come buco
            continue
        covered_s += min(length, limit)
        if length > limit:
            interruptions.append({'da': iso(points[i]), 'a': iso(points[i + 1]), 'minuti': round(length / 60, 1),
                                  'aperta': kinds[i + 1] == 'fine', 'dopo': kinds[i]})
    active_s = max(0, (end - eff_start) - suspended_s)
    out['interruzioni'] = interruptions
    out['interruzioni_n'] = len(interruptions)
    out['minuti_sospensione'] = round(suspended_s / 60, 1)
    out['continuita'] = pct(covered_s, active_s) if active_s else None
    # giri attesi: il tetto non è un obbligo. Si parte dalla configurazione (intervallo minimo,
    # tetto giornaliero) sul tempo attivo; "ciclo" usa la durata mediana osservata di un giro.
    active_min = active_s / 60
    cap = min(active_min / gap_min + 1, max_day * active_min / 1440) if gap_min and active_min > 0 else 0
    cycle = max(gap_min, out['durata_giro_min']['mediana'] or 0)
    out['attesi'] = {'configurazione_max': int(cap), 'per_ciclo_reale': int(active_min / cycle) if cycle else None,
                     'ciclo_min': round(cycle, 1), 'intervallo_min_config': gap_min, 'tetto_giorno': max_day,
                     'copertura_pct': pct(len(effective), int(cap)) if cap >= 1 else None}
    last = max(inside, key=lambda r: r['created']) if inside else None
    out['ultimo'] = {'id': last['id'], 'quando': iso(last['created']), 'origine': last['trigger'], 'esito': last['status'],
                     'sospeso': last['suspended'], 'minuti_fa': round((end - last['created']) / 60, 1),
                     'decisione': last['decision']} if last else None
    return out


# ---------- rapporto ----------

def status_light(w24):
    if w24['avviati'] == 0:
        return 'ROSSO', 'nessun giro nelle ultime 24 ore'
    if w24['ultimo'] and w24['ultimo']['esito'] == 'in_corso' and w24['ultimo']['minuti_fa'] > GAP_LIMIT_MIN * 2:
        return 'ROSSO', 'l\'ultimo giro è in corso da troppo tempo'
    if w24['ultimo'] and w24['ultimo'].get('sospeso'):
        return 'SOSPESA', 'interruttori spenti: l\'ultimo avvio è stato saltato'
    open_gap = any(i['aperta'] for i in w24['interruzioni'])
    if open_gap:
        return 'ROSSO', f'catena ferma da più di {GAP_LIMIT_MIN} minuti'
    if (w24['success_rate'] or 0) < 70 or (w24['continuita'] or 0) < 70:
        return 'ROSSO', 'troppi giri falliti o troppo tempo scoperto'
    if w24['interruzioni_n'] or (w24['success_rate'] or 0) < 90 or (w24['verified_rate'] or 0) < 90 or \
            (w24['attesi']['copertura_pct'] or 0) < 70:
        return 'GIALLO', 'catena con interruzioni o giri falliti, ma viva'
    return 'VERDE', 'catena continua, giri verificati'


def build_report(snapshot, now=None, gap_min=DEFAULT_GAP_MIN, max_day=DEFAULT_MAX_DAY, baseline_until=PR51_MERGED_AT,
                 baseline_hours=72):
    now = int(now if now is not None else time.time())
    commits = snapshot.get('diary_commits', [])
    records = mark_duplicates([classify(r, commits) for r in snapshot.get('runs', [])])
    data_start = ts(snapshot.get('since')) if snapshot.get('since') else (min(r['created'] for r in records) if records else now)
    kw = dict(gap_min=gap_min, max_day=max_day, diary_commits=commits, data_start=data_start)
    merged = ts(baseline_until)
    windows = {'24h': analyze_window(records, now - 86400, now, **kw), '72h': analyze_window(records, now - 72 * 3600, now, **kw)}
    windows['pre_pr51'] = analyze_window(records, merged - baseline_hours * 3600, merged, **kw)
    windows['post_pr51'] = analyze_window(records, merged, now, **kw) if now > merged else None
    light, reason = status_light(windows['24h'])
    work = windows['24h']['lavoro_rate']
    work_note = 'non misurato (nessun avviso dei turni letto)' if work is None else (
        f"{work}% dei turni controllati ha pubblicato" + (' — molti turni verdi sono a vuoto' if work < 70 else ''))
    missing = list(snapshot.get('fetch_missing', []))
    unknown = [r['id'] for r in records if not r['jobs_known']]
    if unknown:
        missing.append(f'{len(unknown)} run senza dettaglio dei job: esito verificato non calcolabile per loro')
    no_notes = [r['id'] for r in records if r['decision_fetched'] and r['decision'] is None]
    if no_notes:
        missing.append(f'{len(no_notes)} giri riusciti senza annotazione della decisione di staffetta')
    for name in ('24h', '72h', 'pre_pr51'):
        if windows[name]['parziale']:
            missing.append(f"finestra {name} parziale: dati disponibili solo dal {windows[name]['dati_da']}")
    running = [r['id'] for r in records if r['status'] == 'in_corso']
    if running:
        missing.append(f'{len(running)} run ancora in corso: esclusi dalle percentuali di esito')
    return {'version': VERSION, 'repo': snapshot.get('repo'), 'workflow': snapshot.get('workflow'),
            'misurato_il': iso(now), 'istantanea_del': snapshot.get('fetched_at'), 'dati_da': iso(data_start),
            'pr51_unita_il': baseline_until, 'configurazione': {'intervallo_min': gap_min, 'tetto_giorno': max_day, 'limite_interruzione_min': GAP_LIMIT_MIN},
            'stato': {'semaforo': light, 'motivo': reason, 'lavoro_agenti': work_note}, 'finestre': windows, 'dati_mancanti': missing,
            'run': [{k: (iso(v) if k in ('created', 'started', 'ended') and v else v) for k, v in r.items()} for r in records
                    if r['created'] >= now - 72 * 3600]}


def _fmt(value, suffix=''):
    return '—' if value is None else f'{value}{suffix}'


def render_markdown(report):
    w = report['finestre']
    a, b, c, d = w['24h'], w['72h'], w['pre_pr51'], w.get('post_pr51')
    light = report['stato']['semaforo']
    lines = ['# Staffetta dei residenti — monitor di affidabilità', '',
             f"**Stato dell'automazione: {light}** — {report['stato']['motivo']}.  ",
             f"**Lavoro effettivo dei residenti (ultime 24h, campione):** {report['stato']['lavoro_agenti']}.  ",
             f"Ultima misurazione: `{report['misurato_il']}` (istantanea GitHub del `{report['istantanea_del']}`, dati dal `{report['dati_da']}`).  ",
             f"Workflow `{report['workflow']}` di `{report['repo']}`; configurazione assunta: intervallo minimo "
             f"{report['configurazione']['intervallo_min']} min, tetto {report['configurazione']['tetto_giorno']} giri/24h, "
             f"interruzione = silenzio > {report['configurazione']['limite_interruzione_min']} min.", '',
             '![andamento](timeline.svg)', '',
             '## Indicatori', '',
             f"Periodi UTC: ultime 24h `{a['inizio']}` → `{a['fine']}`; ultime 72h `{b['inizio']}` → `{b['fine']}`; "
             f"prima della PR #51 `{c['inizio']}` → `{c['fine']}`" + (' (parziale)' if c['parziale'] else '') +
             (f"; dopo la PR #51 `{d['inizio']}` → `{d['fine']}` ({d['ore']} h)" if d else '') + '.', '',
             '| Indicatore | 24h | 72h | pre-PR51 (72h) | post-PR51 |', '|---|---:|---:|---:|---:|']

    def row(label, key, fmt=lambda x: _fmt(x)):
        lines.append(f'| {label} | {fmt(key(a))} | {fmt(key(b))} | {fmt(key(c))} | {fmt(key(d)) if d else "—"} |')
    row('Giri avviati', lambda x: x['avviati'])
    row('· da cron', lambda x: x['per_origine']['cron'])
    row('· manuali', lambda x: x['per_origine']['manuale'])
    row('· da staffetta', lambda x: x['per_origine']['staffetta'])
    row('Sospesi (interruttori spenti)', lambda x: x['sospesi'])
    row('Doppioni / retry / sostituiti in coda', lambda x: f"{x['duplicati']} / {x['retry']} / {x['sostituiti']}")
    row('Giri effettivi', lambda x: x['effettivi'])
    row('Ancora in corso', lambda x: x['in_corso'])
    row('Completati (GitHub success)', lambda x: x['completati'])
    row('Verificati (turn + memoria; vuoti esclusi solo nel campione)', lambda x: x['verificati'])
    row('Falliti / annullati', lambda x: f"{x['falliti']} / {x['annullati']}")
    row('· falliti ma con lavoro e memoria salvati', lambda x: x['parziali'])
    row('Success rate', lambda x: x['success_rate'], lambda v: _fmt(v, '%'))
    row('Verified rate', lambda x: x['verified_rate'], lambda v: _fmt(v, '%'))
    row('Intervallo medio (min)', lambda x: x['intervalli_min']['media'])
    row('Intervallo mediano (min)', lambda x: x['intervalli_min']['mediana'])
    row('Intervallo massimo (min)', lambda x: x['intervalli_min']['max'])
    row('Intervallo mediano dopo staffetta (min)', lambda x: x['intervalli_staffetta_min']['mediana'])
    row('Giri che hanno prenotato il successivo', lambda x: x['catena_dopo_giro'])
    row('Giri senza prenotazione (staffetta spenta/fallita)', lambda x: x['catena_non_prenotata'])
    row('Durata mediana di un giro (min)', lambda x: x['durata_giro_min']['mediana'])
    row(f'Interruzioni > {GAP_LIMIT_MIN} min', lambda x: x['interruzioni_n'])
    row('Continuità operativa', lambda x: x['continuita'], lambda v: _fmt(v, '%'))
    row('Giri attesi (tetto da configurazione)', lambda x: x['attesi']['configurazione_max'])
    row('Giri attesi (ciclo reale)', lambda x: x['attesi']['per_ciclo_reale'])
    row('Copertura del tetto', lambda x: x['attesi']['copertura_pct'], lambda v: _fmt(v, '%'))
    row('Turni dei residenti riusciti / falliti', lambda x: f"{x['turni_ok']} / {x['turni_falliti']}")
    row('Turni controllati negli avvisi (campione)', lambda x: x['turni_controllati'])
    row('· a vuoto (HTTP, nessun post)', lambda x: x['turni_a_vuoto'])
    row('· degradati (API saltata, fallback)', lambda x: x['turni_degradati'])
    row('Turni con pubblicazione riuscita (campione)', lambda x: x['lavoro_rate'], lambda v: _fmt(v, '%'))
    row('Memoria salvata (job remember ok)', lambda x: x['memoria_salvata'])
    row('Giri con commit dei diari', lambda x: x['giri_con_commit_diari'])
    row('Commit dei diari (totale)', lambda x: x['commit_diari'])
    row('Minuti di sospensione', lambda x: x['minuti_sospensione'])
    lines += ['', '## Interruzioni della catena (72h)', '']
    if b['interruzioni']:
        lines += ['| Da | A | Minuti | Dopo | Aperta |', '|---|---|---:|---|---|']
        lines += [f"| {i['da']} | {i['a']} | {i['minuti']} | {i['dopo']} | {'sì' if i['aperta'] else 'no'} |" for i in b['interruzioni']]
    else:
        lines.append('Nessuna.')
    if b['ultimo']:
        u = b['ultimo']
        lines += ['', f"Ultimo avvio: run `{u['id']}` ({u['origine']}, {u['esito']}) alle `{u['quando']}`, {u['minuti_fa']} minuti prima della misurazione."
                  + (f" Decisione della staffetta: `{json.dumps(u['decisione'], ensure_ascii=False)}`." if u['decisione'] else '')]
    lines += ['', '## Dati mancanti o incompleti', '']
    lines += [f'- {m}' for m in report['dati_mancanti']] or ['Nessuno.']
    lines += ['', '## Come leggere', '',
              '- **Fatti**: conteggi, esiti e tempi vengono dalle API di GitHub Actions (run, job, annotazioni) e dai commit dei diari.',
              '- **Verificato** = run riuscito **e** almeno un job `turn (<residente>)` riuscito e non a vuoto **e** job `remember` riuscito. `success` da solo non basta.',
              '- **A vuoto**: `agora_bots.py` su un errore HTTP del server emette un avviso ed esce con 0, quindi GitHub segna il turno verde anche se il residente non ha pubblicato. Gli avvisi si leggono solo per gli ultimi giri (campione), per non consumare troppe chiamate API.',
              '- **Sostituiti**: avvii annullati in coda prima di partire dalla `concurrency` di GitHub (un solo giro alla volta). Non sono fallimenti e non contano come giri.',
              '- **Commit dei diari**: un giro può salvare correttamente senza commit, se nessun diario è cambiato.',
              '- La durata di un giro include l\'attesa della staffetta prima di prenotare il successivo.',
              '- **Stime**: i giri attesi derivano dalla configurazione (intervallo minimo, tetto) e dalla durata mediana osservata; il tetto è un massimo, non un obbligo.',
              '- **Continuità** = quota del tempo attivo in cui l\'ultimo avvio risale a meno di 60 minuti (le sospensioni volute non contano).',
              '- Questo monitor misura l\'**affidabilità dell\'automazione**. Non dice nulla sulla qualità di ciò che i residenti scrivono (efficienza cognitiva): quella va letta nei diari e in piazza.',
              '- Le finestre segnate come parziali iniziano dopo l\'inizio nominale: i dati più vecchi non esistono o non sono stati scaricati.']
    return '\n'.join(lines) + '\n'


def render_svg(report, hours=72, width=960, height=170):
    """Linea del tempo delle ultime `hours` ore: una barra per giro (larghezza = durata, colore = esito),
    bande rosse per le interruzioni. Nessuna dipendenza esterna."""
    end = ts(report['misurato_il'])
    start = end - hours * 3600
    left, right, top, bottom = 40, width - 20, 36, height - 36
    span = max(1, end - start)

    def x(t):
        return left + (right - left) * (t - start) / span
    colors = {'completato': '#2e7d32', 'fallito': '#c62828', 'annullato': '#8d6e63', 'in_corso': '#1565c0', 'saltato': '#9e9e9e', 'scaduto': '#c62828', 'altro': '#9e9e9e'}
    esc = lambda s: str(s).replace('&', '&amp;').replace('<', '&lt;')
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" font-family="sans-serif" font-size="11">',
             f'<rect width="{width}" height="{height}" fill="#fafafa"/>',
             f'<text x="{left}" y="16" font-size="13" font-weight="bold">Giri del workflow agora-bots — ultime {hours} ore (UTC), misurato {esc(report["misurato_il"])}</text>']
    for i in report['finestre']['72h']['interruzioni']:
        parts.append(f'<rect x="{x(ts(i["da"])):.1f}" y="{top}" width="{max(1, x(ts(i["a"])) - x(ts(i["da"]))):.1f}" height="{bottom - top}" fill="#ffcdd2" opacity="0.7"><title>interruzione {i["minuti"]} min</title></rect>')
    for h in range(0, hours + 1, 6):
        t = start + h * 3600
        parts.append(f'<line x1="{x(t):.1f}" y1="{top}" x2="{x(t):.1f}" y2="{bottom}" stroke="#ddd"/>')
        parts.append(f'<text x="{x(t):.1f}" y="{bottom + 14}" text-anchor="middle" fill="#555">{esc(iso(t)[5:16].replace("T", " "))}</text>')
    lanes = {'cron': 0, 'manuale': 1, 'staffetta': 2, 'altro': 3}
    lane_h = (bottom - top) / 4
    for name, idx in lanes.items():
        parts.append(f'<text x="4" y="{top + idx * lane_h + lane_h / 2 + 4:.1f}" fill="#555" font-size="10">{name[:5]}</text>')
    for r in report['run']:
        created = ts(r['created'])
        if created < start:
            continue
        dur = (r['duration_s'] or (end - created)) if r['status'] == 'in_corso' or r['duration_s'] else 60
        w = max(2, x(created + dur) - x(created))
        y = top + lanes.get(r['trigger'], 3) * lane_h + 3
        fill = '#bdbdbd' if r['suspended'] else colors.get(r['status'], '#9e9e9e')
        stroke = ' stroke="#000" stroke-dasharray="2,2"' if r['duplicate'] else ''
        parts.append(f'<rect x="{x(created):.1f}" y="{y:.1f}" width="{w:.1f}" height="{lane_h - 6:.1f}" fill="{fill}"{stroke}>'
                     f'<title>{esc(r["id"])} {esc(r["trigger"])} {esc(r["status"])}{" sospeso" if r["suspended"] else ""}{" doppione" if r["duplicate"] else ""} {esc(r["created"])} ({_fmt(round(r["duration_s"] / 60, 1) if r["duration_s"] else None)} min)</title></rect>')
    legend = [('completato', colors['completato']), ('fallito', colors['fallito']), ('in corso', colors['in_corso']), ('sospeso', '#bdbdbd'), ('interruzione', '#ffcdd2')]
    lx = left
    for label, color in legend:
        parts.append(f'<rect x="{lx}" y="{height - 14}" width="10" height="10" fill="{color}"/><text x="{lx + 14}" y="{height - 5}" fill="#333">{label}</text>')
        lx += 95
    parts.append('</svg>')
    return '\n'.join(parts)


# ---------- comando ----------

def write_report(report, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, 'report.json'), 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=1)
    with open(os.path.join(out_dir, 'report.md'), 'w', encoding='utf-8') as f:
        f.write(render_markdown(report))
    with open(os.path.join(out_dir, 'timeline.svg'), 'w', encoding='utf-8') as f:
        f.write(render_svg(report))


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    sub = p.add_subparsers(dest='cmd', required=True)
    for name in ('fetch', 'run'):
        s = sub.add_parser(name)
        s.add_argument('--repo', default=os.environ.get('GITHUB_REPOSITORY', 'Toramo747/osixbay-agora-bridge'))
        s.add_argument('--since', help='ISO UTC; default: 72h prima della PR #51, così il confronto è possibile')
        s.add_argument('--jobs-hours', type=int, default=80, help='scarica i job per i run delle ultime N ore (oltre alla finestra pre-PR #51)')
        s.add_argument('--turn-notes', type=int, default=TURN_NOTES_TO_FETCH, help='giri recenti di cui leggere gli avvisi dei turni')
        s.add_argument('--out', required=True, help='fetch: file snapshot.json; run: cartella del rapporto')
        s.add_argument('--snapshot', help='run: dove salvare anche l\'istantanea')
    s = sub.add_parser('analyze')
    s.add_argument('snapshot')
    s.add_argument('--out', required=True)
    s.add_argument('--now', help='ISO UTC del momento di misurazione (default: adesso)')
    args = p.parse_args(argv)
    gap_min = clamp(os.environ.get('STAFFETTA_MINUTES'), 15, 180, DEFAULT_GAP_MIN)
    max_day = clamp(os.environ.get('STAFFETTA_MAX_PER_DAY'), 1, 96, DEFAULT_MAX_DAY)
    if args.cmd in ('fetch', 'run'):
        token = os.environ.get('GH_TOKEN') or os.environ.get('GITHUB_TOKEN') or ''
        baseline = (iso(ts(PR51_MERGED_AT) - 72 * 3600), PR51_MERGED_AT)
        since = args.since or baseline[0]
        jobs_since = iso(time.time() - args.jobs_hours * 3600)
        snapshot = fetch(args.repo, since, token, jobs_since=jobs_since, turn_notes=args.turn_notes, baseline=baseline,
                         log=lambda m: print(m, file=sys.stderr))
        path = args.out if args.cmd == 'fetch' else args.snapshot
        if path:
            os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(snapshot, f, ensure_ascii=False)
        if args.cmd == 'fetch':
            return 0
    else:
        with open(args.snapshot, encoding='utf-8') as f:
            snapshot = json.load(f)
    now = ts(args.now) if getattr(args, 'now', None) else None
    report = build_report(snapshot, now=now, gap_min=gap_min, max_day=max_day)
    write_report(report, args.out)
    print(json.dumps({'stato': report['stato'], '24h': {k: report['finestre']['24h'][k] for k in ('avviati', 'effettivi', 'success_rate', 'verified_rate', 'interruzioni_n', 'continuita')}}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    sys.exit(main())
