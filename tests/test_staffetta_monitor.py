"""Test del monitor della staffetta: solo istantanee sintetiche, nessuna chiamata di rete."""
import json, sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import staffetta_monitor as sm  # noqa: E402

NOW = sm.ts('2026-11-05T12:00:00Z')
MIN = 60


def jobs(turns=('ok', 'ok'), remember='success', staffetta='success', plan='success', start=None, length=18 * MIN):
    """Job di un run: `turns` = esiti dei residenti ('ok', 'fail', 'skip')."""
    t0 = start or 0
    out = [{'id': 1, 'name': 'plan', 'status': 'completed', 'conclusion': plan,
            'started_at': sm.iso(t0) if plan != 'skipped' else None, 'completed_at': sm.iso(t0 + 5)}]
    conc = {'ok': 'success', 'fail': 'failure', 'skip': 'skipped'}
    for i, t in enumerate(turns):
        out.append({'id': 10 + i, 'name': f'turn (bot{i})', 'status': 'completed', 'conclusion': conc[t],
                    'started_at': None if t == 'skip' else sm.iso(t0 + 10), 'completed_at': sm.iso(t0 + 300)})
    if remember:
        out.append({'id': 90, 'name': 'remember', 'status': 'completed', 'conclusion': remember,
                    'started_at': sm.iso(t0 + 400) if remember != 'skipped' else None, 'completed_at': sm.iso(t0 + 410)})
    if staffetta:
        out.append({'id': 91, 'name': 'staffetta', 'status': 'completed', 'conclusion': staffetta,
                    'started_at': sm.iso(t0 + 420) if staffetta != 'skipped' else None, 'completed_at': sm.iso(t0 + length)})
    return out


def run(i, ago_min, event='workflow_dispatch', actor='github-actions[bot]', status='completed', conclusion='success',
        length=18 * MIN, attempt=1, with_jobs=True, notes=None, **job_kw):
    """notes: None = avvisi dei turni non letti; 'ok' = letti e puliti; dict = avvisi per job."""
    created = NOW - ago_min * MIN
    r = {'id': i, 'event': event, 'status': status, 'conclusion': conclusion if status == 'completed' else None,
         'created_at': sm.iso(created), 'run_started_at': sm.iso(created), 'updated_at': sm.iso(created + length),
         'run_attempt': attempt, 'actor': actor, 'html_url': f'https://example.invalid/{i}'}
    if with_jobs:
        r['jobs'] = jobs(start=created, length=length, **job_kw)
        if notes == 'ok':
            r['turn_notes'] = {j['name']: [] for j in r['jobs'] if j['name'].startswith('turn') and j['conclusion'] == 'success'}
        elif notes is not None:
            r['turn_notes'] = notes
    return r


def chain(n, every=20, first_ago=None, start_id=100, **kw):
    first_ago = first_ago if first_ago is not None else every * n
    return [run(start_id + k, first_ago - k * every, **kw) for k in range(n)]


def snap(runs, since_hours=80, commits=()):
    return {'repo': 'x/y', 'workflow': 'bots.yml', 'since': sm.iso(NOW - since_hours * 3600),
            'fetched_at': sm.iso(NOW), 'runs': runs, 'diary_commits': list(commits)}


def report(runs, **kw):
    return sm.build_report(snap(runs, **{k: v for k, v in kw.items() if k in ('since_hours', 'commits')}), now=NOW,
                           baseline_until=sm.iso(NOW - 48 * 3600))


class Classification(unittest.TestCase):
    def test_triggers(self):
        self.assertEqual(sm.trigger_of({'event': 'schedule', 'actor': 'Toramo747'}), 'cron')
        self.assertEqual(sm.trigger_of({'event': 'workflow_dispatch', 'actor': 'github-actions[bot]'}), 'staffetta')
        self.assertEqual(sm.trigger_of({'event': 'workflow_dispatch', 'actor': 'Toramo747'}), 'manuale')
        self.assertEqual(sm.trigger_of({'event': 'push'}), 'altro')

    def test_github_success_is_not_enough(self):
        # run verde ma nessun residente ha girato davvero e remember fallito
        rec = sm.classify(run(1, 30, remember='failure'))
        self.assertEqual(rec['status'], 'completato')
        self.assertFalse(rec['verified'])
        # run verde, turni verdi ma tutti respinti dal server (HTTP 429)
        rec = sm.classify(run(2, 30, notes={'turn (bot0)': ['respinto:429'], 'turn (bot1)': ['respinto:429']}))
        self.assertEqual(set(rec['turns'].values()), {'respinto'})
        self.assertEqual(rec['rejections'], {'429': 2})
        self.assertEqual(rec['verifica'], 'respinto')
        self.assertFalse(rec['verified'])

    def test_unread_annotations_are_not_success(self):
        rec = sm.classify(run(1, 30))                       # job verdi, avvisi mai letti
        self.assertEqual(set(rec['turns'].values()), {'non_verificabile'})
        self.assertEqual(rec['verifica'], 'non_verificabile')
        self.assertFalse(rec['verified'])
        # avvisi letti per un solo turno: l'altro resta non verificabile, non riuscito
        rec = sm.classify(run(2, 30, notes={'turn (bot0)': ['respinto:429']}))
        self.assertEqual(rec['turns'], {'turn (bot0)': 'respinto', 'turn (bot1)': 'non_verificabile'})
        self.assertEqual(rec['verifica'], 'non_verificabile')

    def test_four_explicit_turn_states(self):
        rec = sm.classify(run(1, 30, conclusion='failure', turns=('ok', 'ok', 'ok', 'fail'),
                              notes={'turn (bot0)': [], 'turn (bot1)': ['respinto:429', 'degradato']}))
        self.assertEqual(rec['turns'], {'turn (bot0)': 'riuscito', 'turn (bot1)': 'respinto',
                                        'turn (bot2)': 'non_verificabile', 'turn (bot3)': 'fallito'})
        self.assertTrue(rec['partial'])
        self.assertEqual(rec['turn_degraded'], 0)   # il respinto non conta come degradato
        ok = sm.classify(run(2, 30, notes={'turn (bot0)': ['degradato'], 'turn (bot1)': []}))
        self.assertEqual(ok['verifica'], 'verificato')
        self.assertEqual(ok['turn_degraded'], 1)

    def test_turn_note_kinds(self):
        self.assertEqual(sm.turn_note_kind('HTTP 429 on /api/posts'), 'respinto:429')
        self.assertEqual(sm.turn_note_kind('HTTP 401 on /api/posts'), 'respinto:401')
        self.assertEqual(sm.turn_note_kind('groq:llama HTTP 429, passo al successivo'), 'degradato')
        self.assertIsNone(sm.turn_note_kind('Node.js 20 is deprecated'))
        self.assertIsNone(sm.turn_note_kind(None))

    def test_diary_commit_is_linked_to_its_run(self):
        r = run(1, 30)
        rem = next(j for j in r['jobs'] if j['name'] == 'remember')
        rec = sm.classify(r, [{'date': rem['completed_at'], 'message': sm.DIARY_COMMIT}])
        self.assertTrue(rec['diary_commit'])
        self.assertFalse(sm.classify(r, [{'date': sm.iso(NOW - 5 * 3600), 'message': sm.DIARY_COMMIT}])['diary_commit'])


class Scenarios(unittest.TestCase):
    def test_no_runs(self):
        rep = report([])
        w = rep['finestre']['24h']
        self.assertEqual(w['avviati'], 0)
        self.assertIsNone(w['success_rate'])
        self.assertEqual(w['intervalli_min']['n'], 0)
        self.assertEqual(rep['stato']['semaforo'], 'ROSSO')
        self.assertEqual(w['interruzioni_n'], 1)   # tutta la finestra è un buco aperto
        self.assertTrue(w['interruzioni'][0]['aperta'])
        sm.render_markdown(rep); sm.render_svg(rep)   # non deve rompersi

    def test_steady_chain_is_green(self):
        rep = report(chain(72, every=20, first_ago=24 * 60 - 5))
        w = rep['finestre']['24h']
        self.assertEqual(w['effettivi'], 72)
        self.assertEqual(w['success_rate'], 100.0)
        self.assertEqual(w['intervalli_min']['mediana'], 20.0)
        self.assertEqual(w['interruzioni_n'], 0)
        self.assertEqual(w['continuita'], 100.0)
        self.assertEqual(rep['stato']['semaforo'], 'VERDE')

    def test_duplicates_and_retries(self):
        runs = chain(10, first_ago=200)
        runs.append(run(999, 200 - 20 * 3 - 1, event='schedule', actor='Toramo747'))   # cron a 1 minuto da un giro
        runs[5]['run_attempt'] = 2   # rerun: GitHub tiene lo stesso id e incrementa il tentativo
        w = report(runs)['finestre']['24h']
        self.assertEqual(w['duplicati'], 1)
        self.assertEqual(w['retry'], 1)
        self.assertEqual(w['avviati'], 11)
        self.assertEqual(w['effettivi'], 10)

    def test_superseded_in_queue_is_not_a_failure(self):
        runs = chain(6, first_ago=130)
        q = run(500, 70, event='schedule', actor='Toramo747', conclusion='cancelled')
        q['jobs'] = []
        runs.append(q)
        w = report(runs)['finestre']['24h']
        self.assertEqual(w['sostituiti'], 1)
        self.assertEqual(w['annullati'], 0)
        self.assertEqual(w['success_rate'], 100.0)

    def test_run_in_progress(self):
        runs = chain(5, first_ago=100) + [run(700, 3, status='in_progress')]
        rep = report(runs)
        w = rep['finestre']['24h']
        self.assertEqual(w['in_corso'], 1)
        self.assertEqual(w['conclusi'], 5)
        self.assertEqual(w['success_rate'], 100.0)
        self.assertTrue(any('in corso' in m for m in rep['dati_mancanti']))
        stuck = report(chain(3, first_ago=400) + [run(701, 300, status='in_progress')])
        self.assertEqual(stuck['stato']['semaforo'], 'ROSSO')

    def test_failed_runs(self):
        runs = chain(4, first_ago=80)
        runs.append(run(800, 5, conclusion='failure', turns=('ok', 'fail'), notes='ok'))   # parziale
        runs.append(run(801, 2, conclusion='failure', turns=('fail', 'fail')))             # fallito vero
        w = report(runs)['finestre']['24h']
        self.assertEqual(w['falliti'], 2)
        self.assertEqual(w['parziali'], 1)
        self.assertEqual(w['success_rate'], round(100 * 4 / 6, 1))
        self.assertEqual(w['turni']['fallito'], 3)

    def test_suspension_does_not_count_as_interruption(self):
        runs = chain(3, first_ago=600)
        runs += [run(900 + k, 540 - k * 60, event='schedule', actor='Toramo747', plan='skipped',
                     turns=('skip',), remember='skipped', staffetta='skipped', length=20) for k in range(6)]
        runs += chain(3, first_ago=150, start_id=950)
        w = report(runs)['finestre']['24h']
        self.assertEqual(w['sospesi'], 6)
        self.assertGreater(w['minuti_sospensione'], 0)
        # nessuna interruzione dentro la sospensione; restano testa della finestra e buco 600->540? no: 540 è sospeso
        inside = [i for i in w['interruzioni'] if sm.ts(i['da']) >= NOW - 600 * MIN]
        self.assertTrue(all(i['dopo'] != 'sospeso' for i in inside))
        self.assertLess(w['attesi']['configurazione_max'], 72)

    def test_irregular_intervals_and_open_gap(self):
        gaps = [20, 25, 90, 20, 140, 21]
        t, runs = 600, []
        for k, g in enumerate(gaps):
            runs.append(run(k, t)); t -= g
        runs.append(run(99, t))
        w = report(runs)['finestre']['24h']
        self.assertEqual(w['intervalli_min']['max'], 140.0)
        self.assertEqual(w['intervalli_min']['mediana'], 23.0)   # 20,20,21,25,90,140
        long_ = [i for i in w['interruzioni'] if not i['aperta'] and i['dopo'] == 'giro']
        self.assertEqual(sorted(i['minuti'] for i in long_), [90.0, 140.0])
        # l'ultimo giro è a t=254 min fa: catena ferma, buco aperto
        self.assertTrue(any(i['aperta'] for i in w['interruzioni']))
        self.assertLess(w['continuita'], 100)

    def test_incomplete_data(self):
        runs = chain(5, first_ago=100, with_jobs=False)
        rep = report(runs)
        w = rep['finestre']['24h']
        self.assertEqual(w['job_sconosciuti'], 5)
        self.assertEqual(w['verificati'], 0)
        self.assertEqual(w['completati'], 5)
        self.assertIsNone(w['lavoro_rate'])
        self.assertTrue(any('senza dettaglio dei job' in m for m in rep['dati_mancanti']))
        self.assertEqual(rep['stato']['lavoro_agenti'], 'non verificabile (nessun avviso dei turni letto)')
        self.assertIsNone(w['verified_rate'])

    def test_unverifiable_window_is_reported_not_counted_as_success(self):
        runs = chain(6, first_ago=130)                                   # nessun avviso letto
        runs += [run(600, 10, notes={'turn (bot0)': ['respinto:429'], 'turn (bot1)': []})]
        rep = report(runs)
        w = rep['finestre']['24h']
        self.assertEqual(w['non_verificabili'], 6)
        self.assertEqual(w['verificati'], 1)
        self.assertEqual(w['verified_rate'], 100.0)                       # 1 verificabile su 1
        self.assertEqual(w['copertura_verifica'], round(100 / 7, 1))
        self.assertEqual(w['turni'], {'riuscito': 1, 'respinto': 1, 'fallito': 0, 'non_verificabile': 12})
        self.assertEqual(w['lavoro_rate'], 50.0)                          # i 12 non verificabili non contano
        self.assertTrue(any('non verificabile' in m for m in rep['dati_mancanti']))
        md = sm.render_markdown(rep)
        self.assertIn('| Turni: non verificabili | 12 |', md)
        self.assertIn('Copertura della verifica', md)

    def test_rejections_counted_by_http_code(self):
        runs = chain(3, first_ago=60, notes={'turn (bot0)': ['respinto:429'], 'turn (bot1)': ['respinto:401']})
        w = report(runs)['finestre']['24h']
        self.assertEqual(w['rifiuti_per_codice'], {'401': 3, '429': 3})
        self.assertEqual(w['respinti'], 3)
        self.assertEqual(w['lavoro_rate'], 0.0)

    def test_partial_window(self):
        rep = report(chain(10, first_ago=200), since_hours=6)
        w72 = rep['finestre']['72h']
        self.assertTrue(w72['parziale'])
        self.assertEqual(w72['dati_da'], sm.iso(NOW - 6 * 3600))
        self.assertTrue(any('72h parziale' in m for m in rep['dati_mancanti']))
        # la testa mancante non diventa un'interruzione inventata
        self.assertTrue(all(i['dopo'] != 'inizio' for i in w72['interruzioni']))

    def test_expected_turns_follow_configuration_not_the_cap(self):
        w = report(chain(3, first_ago=60))['finestre']['24h']
        self.assertEqual(w['attesi']['tetto_giorno'], 80)
        self.assertEqual(w['attesi']['configurazione_max'], 73)   # 24h/20min + 1 < 80
        rep = sm.build_report(snap(chain(3, first_ago=60)), now=NOW, gap_min=60, baseline_until=sm.iso(NOW - 48 * 3600))
        self.assertEqual(rep['finestre']['24h']['attesi']['configurazione_max'], 25)

    def test_pre_and_post_pr_comparison(self):
        old = [run(k, 72 * 60 - k * 190, event='schedule', actor='Toramo747') for k in range(8)]
        new = chain(60, first_ago=24 * 60 - 1, start_id=300)
        rep = report(old + new)
        pre, post = rep['finestre']['pre_pr51'], rep['finestre']['post_pr51']
        self.assertGreater(pre['intervalli_min']['mediana'], 60)
        self.assertEqual(post['intervalli_min']['mediana'], 20.0)
        self.assertGreater(post['continuita'], pre['continuita'])


CORE = """export function limits(name, history, now) {
    if (history.some(t => now - t < 30))
        return 'Attendi 30 secondi';
    if (history.filter(t => t >= Math.floor(now / 86400) * 86400).length >= (name === 'neo' ? 60 : 40))
        return 'Limite giornaliero raggiunto';
}"""


def fake_repo(d, core=CORE, bots={'max_posts_per_day': 30, 'max_replies_per_thread_per_day': 2},
              readme='Limiti: 30 post al giorno per bot, 2 risposte'):
    (Path(d) / 'agora').mkdir()
    (Path(d) / 'bots').mkdir()
    if core is not None:
        (Path(d) / 'agora' / 'core.mjs').write_text(core)
    if bots is not None:
        (Path(d) / 'bots' / 'bots.json').write_text(json.dumps(bots))
    if readme is not None:
        (Path(d) / 'README.md').write_text(readme)


class Limits(unittest.TestCase):
    def test_declared_limits_are_read_per_source(self):
        with tempfile.TemporaryDirectory() as d:
            fake_repo(d)
            lim = sm.declared_limits(d)
        self.assertEqual(lim['codice_server']['post_giorno'], 40)
        self.assertEqual(lim['codice_server']['eccezioni'], {'neo': 60})
        self.assertEqual(lim['codice_server']['attesa_minima_s'], 30)
        self.assertEqual(lim['client_residenti']['post_giorno'], 30)
        self.assertEqual(lim['documentazione']['post_giorno'], 30)
        mism = sm.limit_mismatches(lim)
        self.assertIn('README dichiara 30 post/giorno, il codice del server in agora/core.mjs 40', mism)
        self.assertTrue(any('neo fino a 60' in m for m in mism))

    def test_real_repository_values(self):
        lim = sm.declared_limits()   # il repository vero: se il formato cambia, il test lo segnala
        self.assertEqual(lim['codice_server']['post_giorno'], 40)
        self.assertEqual(lim['codice_server']['eccezioni'], {'neo': 60})

    def test_missing_or_changed_sources_are_none_not_guessed(self):
        with tempfile.TemporaryDirectory() as d:
            fake_repo(d, core='export const LIMIT = 40;', bots=None, readme=None)
            lim = sm.declared_limits(d)
        self.assertEqual(lim, {'codice_server': None, 'client_residenti': None, 'documentazione': None})
        self.assertEqual(sm.limit_mismatches(lim), [])

    def test_server_applied_limit_is_never_assumed(self):
        snapshot = snap(chain(3, first_ago=60, notes={'turn (bot0)': ['respinto:429'], 'turn (bot1)': []}))
        snapshot['limiti_dichiarati'] = {'codice_server': {'fonte': 'x', 'post_giorno': 40, 'eccezioni': {'neo': 60},
                                                           'conteggio': 'giorno solare UTC', 'attesa_minima_s': 30},
                                         'client_residenti': None, 'documentazione': {'fonte': 'README.md', 'post_giorno': 30}}
        rep = sm.build_report(snapshot, now=NOW, baseline_until=sm.iso(NOW - 48 * 3600))
        lim = rep['limiti_pubblicazione']
        self.assertEqual(lim['dichiarati_da'], 'istantanea')
        self.assertEqual(lim['applicato_dal_server']['stato'], 'non_verificabile')
        self.assertEqual(lim['applicato_dal_server']['rifiuti_24h_per_codice'], {'429': 3})
        md = sm.render_markdown(rep)
        self.assertIn('**Applicato dal server in produzione: non verificabile**', md)
        self.assertIn('| `agora/core.mjs` (codice del server) | 40 | neo: 60', md)
        self.assertIn('HTTP 429: 3 su 6 turni verificabili', md)
        self.assertNotIn('30 post al giorno per residente', md)


class Output(unittest.TestCase):
    def test_files_are_written_and_reproducible(self):
        runs = chain(10, first_ago=200)
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 's.json'
            path.write_text(json.dumps(snap(runs)))
            for out in ('a', 'b'):
                sm.main(['analyze', str(path), '--out', str(Path(d) / out), '--now', sm.iso(NOW)])
            for name in ('report.json', 'report.md', 'timeline.svg'):
                self.assertEqual((Path(d) / 'a' / name).read_text(), (Path(d) / 'b' / name).read_text())
            md = (Path(d) / 'a' / 'report.md').read_text()
            self.assertIn('Ultima misurazione: `2026-11-05T12:00:00Z`', md)
            self.assertIn('Periodi UTC', md)
            self.assertTrue((Path(d) / 'a' / 'timeline.svg').read_text().startswith('<svg'))

    def test_no_secrets_or_tokens_in_report(self):
        rep = report(chain(3, first_ago=60))
        text = json.dumps(rep) + sm.render_markdown(rep)
        for word in ('token', 'secret', 'Bearer', 'PRIVATE_KEY'):
            self.assertNotIn(word, text)


if __name__ == '__main__':
    unittest.main()
