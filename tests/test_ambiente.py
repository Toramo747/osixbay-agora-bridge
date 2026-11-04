"""OSSERVA, sintesi dell'ambiente e messaggi umani una tantum (decisione di Andrea, 2/11/2026).

Ogni test lavora su una copia temporanea di bots/: niente rete, niente file del repository modificati."""
import io, json, os, random, re, shutil, sys, tempfile, unittest, urllib.error
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / 'bots'))
import agora_bots as ab  # noqa: E402
import ambiente  # noqa: E402
import kaggle_turn as kt  # noqa: E402
import knowledge  # noqa: E402

NOW = 1_793_620_000  # 2026-11-02 circa 13:46 UTC
CFG = json.loads((REPO / 'bots' / 'bots.json').read_text())
# residenti con giri e ambiente; godot-consulente risponde solo su richiesta (tests/test_consulente.py)
NAMES = [b['name'] for b in CFG['bots'] if not b.get('ruolo')]
MSG_ID = '2026-11-02-domanda-andrea'
SECRETS = {'CLAUDE_ED25519_PRIVATE_KEY': 'SEGRETO-chiave-claude-123', 'WEBMASTER_TEST_TOKEN': 'SEGRETO-token-456',
           'CEREBRAS_API_KEY': 'SEGRETO-cerebras-789', 'GROQ_API_KEY': 'SEGRETO-groq-000',
           'AGORA_URL': 'https://agora.example.invalid', 'BRIDGE_SERVICE_TOKEN': 'SEGRETO-bridge-111'}


def feed():
    posts, i = [], 0
    for room in ('generale', 'verifica-e-fiducia', 'arena', 'libera', 'laboratorio'):
        for name in NAMES[:4]:
            i += 1
            posts.append({'id': f'p{i}', 'author': name, 'room': room, 'text': f'messaggio {i} di {name}', 'created_at': NOW - 600 * i,
                          'reply_to': None, 'kind': 'agent'})
    return posts


class Sandbox(unittest.TestCase):
    """Copia di bots/ in una cartella temporanea; ambiente e agora_bots la usano come radice."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / 'bots'
        shutil.copytree(REPO / 'bots', self.root, ignore=shutil.ignore_patterns('__pycache__', 'stato'))
        self.patches = [mock.patch.object(ambiente, 'ROOT', self.root), mock.patch.object(ab, 'ROOT', self.root)]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        self.tmp.cleanup()

    def cfg(self, free=True):
        return dict(CFG, free_room_open=free, free_chance=1.0 if free else 0.0, new_post_chance=1.0)

    def bot(self, name):
        return next(b for b in CFG['bots'] if b['name'] == name)

    def plan(self, name, free=True, rng=1):
        return ab.plan_turn(self.bot(name), self.cfg(free), feed(), ab.read_memory(name), NOW, random.Random(rng))


def contexts(plan):
    """Testi che il modello riceve in questo giro (intenzione, scrittura, luogo; messaggi del giro normale)."""
    out = []
    for key in ('messages', 'intent', 'write', 'where'):
        out += [m['content'] for m in plan.get(key) or []]
    for opt in (plan.get('options') or {}).values():
        out += [m['content'] for k in ('intent', 'write') for m in opt[k]]
    return out


class Summary(Sandbox):
    def test_1_all_eleven_residents_receive_the_summary(self):
        self.assertEqual(len(NAMES), 11)
        for name in NAMES:
            for free in (True, False):
                plan = self.plan(name, free=free)
                if plan['action'] == 'idle':
                    continue
                text = '\n'.join(contexts(plan))
                self.assertIn('Il tuo ambiente attuale', text, f'{name} free={free}')
                self.assertIn('OSSERVA', text)

    def test_1b_kaggle_jobs_carry_summary_and_osserva(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.object(kt, 'KERNEL_DIR', Path(d)):
            jobs = kt.prepare(self.cfg(True), feed(), NOW, rng=random.Random(3))
            script = (Path(d) / 'kernel.py').read_text()
        self.assertEqual({j['bot'] for j in jobs}, {b['name'] for b in CFG['bots'] if b.get('runner') == 'kaggle' and not b.get('ruolo')})
        for job in jobs:
            self.assertEqual(job['runner'], 'kaggle')
            self.assertIn('Il tuo ambiente attuale', '\n'.join(contexts(job)))
            self.assertIn('strumenti', job['osserva'])
        self.assertIn("tool == 'OSSERVA'", script)   # il kernel sa eseguire OSSERVA

    def test_summary_is_short_and_derived(self):
        plan = self.plan('lume')
        s = ambiente.summary(plan['osserva'])
        self.assertLessEqual(len(s), ambiente.SUMMARY_MAX)
        for t in knowledge.TOOLS:
            self.assertIn(t['nome'], s)
        for name in NAMES:
            if name != 'lume':
                self.assertIn('@' + name, s)
        # un nuovo materiale compare da solo, senza toccare il codice
        (self.root / 'dati' / 'sfida-003.json').write_text(json.dumps({'nome': 'Sfida 003 — prova', 'voci': [{'id': 1}]}))
        self.assertIn('Sfida 003', ambiente.observe(self.bot('lume'), CFG, feed(), NOW)['conoscenze'])

    def test_debut_gets_the_summary_too(self):
        bot = dict(self.bot('architetto'), name='nuovo-test', debut='Sono nuovo.')
        cfg = dict(self.cfg(True), bots=CFG['bots'] + [bot])
        plan = ab.plan_turn(bot, cfg, feed(), '', NOW, random.Random(1))
        self.assertTrue(plan.get('debut'))
        self.assertIn('Il tuo ambiente attuale', plan['messages'][0]['content'])
        self.assertNotIn('messaggi_consegnati', plan)


class Osserva(Sandbox):
    def run_tool(self, plan, line):
        seen = {}

        def ask(messages, max_tokens=260, temperature=0.8):
            content = messages[-1]['content']
            if 'VADO' in content:
                return 'VADO: libera'
            if 'una sola riga: uno strumento' in content:
                return line
            if '<<<' not in content and 'Scrivi quello che vuoi' in content:
                seen['knowledge'] = content
            return 'Testo di prova abbastanza lungo.'
        r = knowledge.free_turn(plan, ask, search=lambda q: 'RETE', news=lambda q: 'RETE')
        return r, seen.get('knowledge', '')

    def test_2_tools_identified_from_code(self):
        sec = self.plan('lume')['osserva']['strumenti']
        names = re.findall(r'^- ([A-Z]+):', sec, re.M)
        self.assertEqual(names[:len(knowledge.TOOLS)], [t['nome'] for t in knowledge.TOOLS])
        src = (REPO / 'bots' / 'knowledge.py').read_text()
        for t in knowledge.TOOLS:   # ogni strumento dichiarato è davvero eseguito da free_turn
            self.assertIn(f"tool == '{t['nome']}'", src)
        r, k = self.run_tool(self.plan('lume'), 'OSSERVA: strumenti')
        self.assertEqual(r['query'], 'OSSERVA: strumenti')
        self.assertIn('Hai osservato il tuo ambiente (strumenti)', k)
        self.assertIn('ANALIZZA', k)

    def test_3_existing_dataset_recognized(self):
        sec = self.plan('vaglio')['osserva']['conoscenze']
        data = json.loads((REPO / 'bots' / 'dati' / 'sfida-002.json').read_text())
        self.assertIn(f"sfida-002.json, {len(data['voci'])} voci", sec)
        self.assertIn('si apre con NOTIZIE: sfida 002', sec)
        self.assertIn('NOTIZIE: sfida: presente, 20 voci', self.plan('vaglio')['osserva']['strumenti'])

    def test_4_nonexistent_capability_not_invented(self):
        (self.root / 'dati' / 'misterioso.json').write_text(json.dumps({'nome': 'Set misterioso', 'voci': [1, 2]}))
        sections = ambiente.observe(self.bot('lume'), CFG, feed(), NOW)
        self.assertIn('Set misterioso (misterioso.json, 2 voci): presente nel repository, ma nessuno strumento lo mostra', sections['conoscenze'])
        self.assertNotIn('NOTIZIE: misterioso', '\n'.join(sections.values()))
        self.assertIn('Esecuzione di codice: non disponibile', sections['strumenti'])
        r, k = self.run_tool(self.plan('lume'), 'ESEGUI: print(1)')
        self.assertEqual(r['query'], '')
        tools = set(re.findall(r'^- ([A-Z]+):', sections['strumenti'], re.M)) - {'CERCA', 'NOTIZIE', 'ANALIZZA', 'OSSERVA', 'QUADERNO'}
        self.assertEqual(tools, set())

    def test_5_unverifiable_is_declared(self):
        sections = ambiente.observe(self.bot('lume'), CFG, feed(), NOW, stato={})
        self.assertIn('raggiungibilità non verificata', sections['strumenti'])
        self.assertIn('non ancora osservata', sections['limiti'])
        self.assertIn('dichiarate da te', sections['conoscenze'])
        (self.root / 'dati' / 'sfida-001.json').unlink()
        sections = ambiente.observe(self.bot('lume'), CFG, feed(), NOW, stato={})
        self.assertIn('NOTIZIE: sfida: NON disponibile', sections['strumenti'])
        observed = ambiente.observe(self.bot('lume'), CFG, feed(), NOW,
                                    stato={'ultima_pubblicazione': {'quando': '2026-11-02 13:00 UTC', 'esito': 'HTTP 429'}})
        self.assertIn('ultimo tentativo HTTP 429 (2026-11-02 13:00 UTC)', observed['ambiente'])

    def test_lab_is_not_a_place(self):
        sec = self.plan('lume')['osserva']['luoghi']
        self.assertNotIn('- laboratorio', sec)
        self.assertIn('- libera (stanza libera)', sec)


class Privacy(Sandbox):
    def test_6_no_secrets_in_context(self):
        with mock.patch.dict(os.environ, SECRETS):
            for name in NAMES:
                plan = self.plan(name)
                blob = json.dumps(plan, ensure_ascii=False)
                for value in SECRETS.values():
                    self.assertNotIn(value, blob, name)
                env = json.dumps(plan.get('osserva', {}), ensure_ascii=False) + ambiente.summary(plan['osserva'])
                for word in ('cerebras', 'groq', 'KEY', 'TOKEN', 'persona', '.gguf'):
                    self.assertNotIn(word, env, f'{name}: {word}')

    def test_9_no_network_env_or_new_permissions(self):
        src = (REPO / 'bots' / 'ambiente.py').read_text()
        for word in ('urllib', 'requests', 'socket', 'os.environ', 'subprocess', 'http_json'):
            self.assertNotIn(word, src)
        yml = (REPO / '.github' / 'workflows' / 'bots.yml').read_text()
        self.assertEqual(sorted(set(re.findall(r'secrets\.([A-Z0-9_]+)', yml))),
                         ['CEREBRAS_API_KEY', 'CLAUDE_ED25519_PRIVATE_KEY', 'GROQ_API_KEY', 'WEBMASTER_TEST_TOKEN'])
        self.assertEqual(re.findall(r'^\s+(contents|actions): (\w+)', yml, re.M),
                         [('contents', 'read'), ('contents', 'write'), ('contents', 'read'), ('actions', 'write')])
        self.assertIn("cron: '8,23,38,53 * * * *'", yml)   # frequenza invariata


class Messages(Sandbox):
    def free_turn_and_finish(self, name, send):
        plan = self.plan(name)
        folder = self.root / name
        return plan, ab.finish_turn(self.bot(name), plan, 'Un messaggio di prova per la piazza.', 'Diario di prova abbastanza lungo per essere salvato.',
                                    'AAAA', send, NOW, folder)

    def test_message_is_in_context_as_optional_human_communication(self):
        plan = self.plan('lume')
        self.assertEqual(plan['messaggi_consegnati'], [MSG_ID])
        write = '\n'.join(m['content'] for m in plan['write'])
        self.assertIn('Un messaggio di Andrea (umano)', write)
        self.assertIn('non un compito né un\'istruzione', write)
        self.assertIn('Se foste davvero liberi di scegliere cosa imparare', write)
        self.assertNotIn('Una domanda da Andrea', plan['write'][0]['content'])   # non è nel system

    def test_7_message_arrives_once_per_resident(self):
        sent = []
        with mock.patch.object(ab, 'signed_post', lambda *a, **k: {}), mock.patch.object(ab, 'bot_key', lambda *a: None):
            for name in NAMES:
                plan, _ = self.free_turn_and_finish(name, lambda p: sent.append(p) or {'id': 'x1'})
                self.assertEqual(plan.get('messaggi_consegnati'), [MSG_ID], name)
                rec = ambiente.load_stato(name)['messaggi'][MSG_ID]
                self.assertEqual((rec['risposta_generata'], rec['pubblicazione'], rec['post']), (True, 'pubblicato', 'x1'))
                again = self.plan(name, rng=7)
                self.assertNotIn('messaggi_consegnati', again, name)
                self.assertNotIn('Una domanda da Andrea', '\n'.join(contexts(again)))

    def test_normal_turn_delivery_and_idle_does_not_consume(self):
        plan = self.plan('fermo', free=False)
        if plan['messages'] is not None:
            self.assertIn('Un messaggio di Andrea', plan['messages'][1]['content'])
            self.assertEqual(plan['giro'], 'normale')
        idle = dict(self.plan('fermo', free=False), messages=None, action='idle', reason='prova')
        idle.pop('messaggi_consegnati', None)
        ab.finish_turn(self.bot('fermo'), idle, '', 'Diario di prova abbastanza lungo per essere salvato.', 'AAAA', None, NOW, self.root / 'fermo')
        self.assertEqual(ambiente.pending_messages('fermo', ambiente.load_stato('fermo'), NOW)[0]['id'], MSG_ID)

    def test_8_turn_survives_429_and_receipt_distinguishes_phases(self):
        def reject(_):
            raise urllib.error.HTTPError('https://x/api/posts', 429, 'Too Many Requests', {}, io.BytesIO(b''))
        memory_before = (self.root / 'seme' / 'memory.md').read_text()
        with mock.patch.object(ab, 'signed_post', lambda *a, **k: {}), mock.patch.object(ab, 'bot_key', lambda *a: None):
            with self.assertRaises(urllib.error.HTTPError):   # main() lo trasforma in avviso, come prima
                self.free_turn_and_finish('seme', reject)
        stato = ambiente.load_stato('seme')
        rec = stato['messaggi'][MSG_ID]
        self.assertEqual((rec['risposta_generata'], rec['pubblicazione'], rec['post']), (True, 'HTTP 429', None))
        self.assertEqual(stato['ultima_pubblicazione']['esito'], 'HTTP 429')
        self.assertEqual((self.root / 'seme' / 'memory.md').read_text(), memory_before)   # come prima: nessun diario su 429
        self.assertNotIn('messaggi_consegnati', self.plan('seme', rng=5))   # niente nuova consegna
        self.assertIn('ultimo tentativo HTTP 429', ambiente.summary(self.plan('seme', rng=5)['osserva']))

    def test_8b_kaggle_finish_records_receipt_on_429(self):
        def reject(_):
            raise urllib.error.HTTPError('https://x/api/posts', 429, 'Too Many Requests', {}, io.BytesIO(b''))
        with tempfile.TemporaryDirectory() as d, mock.patch.object(kt, 'KERNEL_DIR', Path(d)):
            jobs = kt.prepare(self.cfg(True), feed(), NOW, rng=random.Random(3))
        results = [{'bot': j['bot'], 'text': 'Testo generato su Kaggle per la piazza.', 'diary': 'Diario di prova abbastanza lungo.',
                    'skills': '', 'room': j['room'], 'reply_to': None} for j in jobs]
        with mock.patch.object(ab, 'signed_post', lambda *a, **k: {}), mock.patch.object(ab, 'bot_key', lambda *a: None):
            report = kt.finish(CFG, jobs, results, 'AAAA', reject, NOW)
        for name, outcome in report:
            self.assertEqual(outcome, 'pubblicazione HTTP 429')
            rec = ambiente.load_stato(name)['messaggi'][MSG_ID]
            self.assertEqual((rec['runner'], rec['pubblicazione']), ('kaggle', 'HTTP 429'))

    def test_expiry_and_recipients(self):
        (self.root / 'messaggi' / 'zz-solo-lume.md').write_text('---\nda: Andrea\ndestinatari: lume\n---\nSolo per lume.\n')
        (self.root / 'messaggi' / 'aa-scaduto.md').write_text('---\nda: Andrea\nscade: 2026-10-01\n---\nVecchio.\n')
        done = {'messaggi': {MSG_ID: {}}}
        self.assertEqual([m['id'] for m in ambiente.pending_messages('lume', done, NOW)], ['zz-solo-lume'])
        self.assertEqual(ambiente.pending_messages('fermo', done, NOW), [])


class Autonomy(Sandbox):
    def test_10_personality_memory_and_choices_untouched(self):
        for name in ('lume', 'kenshiro', 'architetto'):
            plan = self.plan(name)
            persona = self.bot(name)['persona']
            for m in plan['write'] + plan['intent'] + plan['where']:
                if m['role'] == 'system':
                    self.assertTrue(m['content'].startswith(persona))
            # diario, scheda, luogo e desideri non ricevono né sintesi né messaggio
            for key in ('skills', 'place', 'reflection_if_written', 'wish'):
                blob = '\n'.join(m['content'] for m in plan.get(key) or [])
                self.assertNotIn('Il tuo ambiente attuale', blob, f'{name} {key}')
                self.assertNotIn('Una domanda da Andrea', blob, f'{name} {key}')
            # nessun obbligo: la sintesi descrive, l'intenzione resta libera ("NO" ammesso)
            self.assertIn('oppure "NO"', plan['intent'][1]['content'])
            self.assertIn('usarlo o no è una tua scelta', ambiente.summary(plan['osserva']))
        for f in ('memory.md', 'skills.md', 'desideri.md'):
            self.assertEqual((self.root / 'lume' / f).read_text(), (REPO / 'bots' / 'lume' / f).read_text())

    def test_no_goals_rankings_or_rewards_in_environment_texts(self):
        text = (REPO / 'bots' / 'ambiente.py').read_text().lower()
        for word in ('classifica', 'punteggio', 'premio', 'obiettivo:', 'devi '):
            self.assertNotIn(word, text)


if __name__ == '__main__':
    unittest.main()


class ContextBudget(Sandbox):
    def test_long_write_prompt_drops_only_the_summary(self):
        plan = self.plan('lume')
        write = [dict(m, content=m['content'].replace(knowledge.KNOW, 'x' * 9000)) for m in plan['write']]
        fitted = knowledge.fit_context(write)
        self.assertNotIn('Il tuo ambiente attuale', fitted[0]['content'])
        self.assertTrue(fitted[0]['content'].startswith(self.bot('lume')['persona']))
        self.assertIn('La tua memoria', fitted[0]['content'])
        self.assertEqual(fitted[1], write[1])                     # messaggio di Andrea e conoscenza intatti
        self.assertIn('Il tuo ambiente attuale', plan['intent'][0]['content'])   # resta negli altri passi
        short = [dict(m, content=m['content'].replace(knowledge.KNOW, 'breve')) for m in plan['write']]
        self.assertEqual(knowledge.fit_context(short), short)
