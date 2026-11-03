"""Registro dei giri (osservabilità anche con post respinti) e Sfide alla cieca (riferimenti al giro dopo)."""
import io, json, os, random, sys, tempfile, unittest, urllib.error
from pathlib import Path
from unittest import mock
sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_ambiente import CFG, NOW, SECRETS, Sandbox, feed, contexts  # noqa: E402
import agora_bots as ab  # noqa: E402
import ambiente  # noqa: E402
import kaggle_turn as kt  # noqa: E402
import knowledge  # noqa: E402

D1 = json.loads((Path(__file__).resolve().parents[1] / 'bots' / 'dati' / 'sfida-001.json').read_text())
D2 = json.loads((Path(__file__).resolve().parents[1] / 'bots' / 'dati' / 'sfida-002.json').read_text())


def http(code):
    def send(_):
        raise urllib.error.HTTPError('https://x/api/posts', code, 'x', {}, io.BytesIO(b''))
    return send


class Blind(unittest.TestCase):
    def test_challenge_without_refs_hides_answers(self):
        chosen = knowledge.pick(D1, random.Random(1))
        text = knowledge.challenge(D1, random.Random(1), refs=False, chosen=chosen)
        self.assertNotIn('Riferimenti', text)
        for v in chosen:
            self.assertIn(f"#{v['id']} ", text)
            self.assertNotIn(v['perche'][:30], text)
        self.assertIn('prossimo giro', text)
        refs = knowledge.challenge_refs(D1, [v['id'] for v in chosen])
        for v in chosen:
            self.assertIn(v['perche'][:30], refs)

    def test_sample_set_without_refs_hides_labels(self):
        chosen = knowledge.pick(D2, random.Random(2))
        text = knowledge.sample_set(D2, random.Random(2), refs=False, chosen=chosen)
        self.assertNotIn('certezza', text)
        for v in chosen:
            self.assertNotIn(v.get('spiegazione', '')[:30] or 'zz', text)
        self.assertIn('Etichette possibili', text)

    def test_default_keeps_old_behaviour(self):
        self.assertIn('Riferimenti', knowledge.challenge(D1, random.Random(1)))
        self.assertIn('certezza', knowledge.sample_set(D2, random.Random(1)))


class Turns(Sandbox):
    def turn(self, name, tool_line, send, rng=1, text='Un messaggio di prova per la piazza, abbastanza lungo.'):
        plan = self.plan(name, rng=rng)

        def ask(messages, max_tokens=260, temperature=0.8):
            c = messages[-1]['content']
            if 'VADO' in c:
                return 'VADO: libera'
            if 'una sola riga: uno strumento' in c:
                return tool_line
            return text
        r = knowledge.free_turn(plan, ask, search=lambda q: 'RISULTATI DI RETE', news=lambda q: 'NOTIZIE DI RETE')
        ab.adopt_place(plan, r)
        extra = {'query': r['query'], 'tool_output': r['tool_output'], 'opened': r['opened']}
        with mock.patch.object(ab, 'signed_post', lambda *a, **k: {}), mock.patch.object(ab, 'bot_key', lambda *a: None):
            ab.finish_turn(self.bot(name), plan, r['text'], 'Diario di prova abbastanza lungo per essere salvato.', 'AAAA', send,
                           NOW, self.root / name, raw_skills=r['skills'], raw_wish=r.get('wish'), raw_place=r.get('place'), extra=extra)
        return plan, r

    def rows(self, name):
        path = self.root / 'registro' / '2026-11-02' / f'{name}.jsonl'
        return [json.loads(l) for l in path.read_text().splitlines()] if path.exists() else []

    def test_references_arrive_next_turn_once(self):
        plan, r = self.turn('lume', 'NOTIZIE: sfida', lambda p: {'id': 'a1'})
        self.assertEqual(r['opened'], 'sfida-001')
        self.assertNotIn('Riferimenti', r['tool_output'])
        ids = ambiente.load_stato('lume')['riferimenti_in_sospeso']['ids']
        self.assertEqual(ids, plan['campioni']['sfida-001'])
        nxt = self.plan('lume', rng=9)
        self.assertEqual(nxt['riferimenti_consegnati'], 'sfida-001')
        write = '\n'.join(m['content'] for m in nxt['write'])
        self.assertIn('Ecco i riferimenti di quelle voci', write)
        for v in D1['voci']:
            (self.assertIn if v['id'] in ids else self.assertNotIn)(f"#{v['id']}: {v['riferimento']}", write)
        self.turn('lume', 'NO', lambda p: {'id': 'a2'}, rng=9)
        self.assertNotIn('riferimenti_in_sospeso', ambiente.load_stato('lume'))
        self.assertFalse(self.plan('lume', rng=11)['riferimenti_consegnati'])
        self.assertEqual(self.rows('lume')[-1]['riferimenti_visti'], 'sfida-001')

    def test_sfida_002_blind_and_analizza_still_works(self):
        plan, r = self.turn('trama', 'ANALIZZA: sfida 002', lambda p: {'id': 'b1'})
        self.assertIn('Hai analizzato le voci della Sfida 002', r['tool_output'])
        self.assertNotIn('certezza', r['tool_output'])
        self.assertEqual(ambiente.load_stato('trama')['riferimenti_in_sospeso']['set'], 'sfida-002')

    def test_journal_success_row(self):
        self.turn('fermo', 'CERCA: negative sampling', lambda p: {'id': 'p9'})
        row = self.rows('fermo')[-1]
        self.assertEqual((row['strumento'], row['pubblicazione'], row['post'], row['runner'], row['giro']),
                         ('negative sampling', 'pubblicato', 'p9', 'github', 'libero'))
        self.assertIn('RISULTATI DI RETE', row['uscita_strumento']['estratto'])
        self.assertEqual(len(row['uscita_strumento']['sha']), 12)
        self.assertTrue(row['testo'].startswith('Un messaggio di prova'))

    def test_journal_keeps_text_on_429(self):
        with self.assertRaises(urllib.error.HTTPError):
            self.turn('seme', 'OSSERVA: strumenti', http(429))
        row = self.rows('seme')[-1]
        self.assertEqual((row['strumento'], row['pubblicazione']), ('OSSERVA: strumenti', 'HTTP 429'))
        self.assertIn('testo', row)
        self.assertIn('Hai osservato il tuo ambiente', row['uscita_strumento']['estratto'])

    def test_journal_omits_text_refused_for_content(self):
        with self.assertRaises(urllib.error.HTTPError):
            self.turn('vaglio', 'NO', http(400))
        row = self.rows('vaglio')[-1]
        self.assertNotIn('testo', row)
        self.assertEqual(row['testo_omesso']['car'], len('Un messaggio di prova per la piazza, abbastanza lungo.'))
        self.assertEqual(row['strumento'], '')
        self.assertNotIn('uscita_strumento', row)

    def test_journal_idle_normal_turn(self):
        plan = dict(self.plan('inciampo', free=False), messages=None, action='idle', reason='prova')
        ab.finish_turn(self.bot('inciampo'), plan, '', 'Diario di prova abbastanza lungo per essere salvato.', 'AAAA', None, NOW, self.root / 'inciampo')
        row = self.rows('inciampo')[-1]
        self.assertEqual((row['azione'], row['pubblicazione'], row['strumento']), ('idle', 'nessun messaggio', None))

    def test_journal_has_no_secrets_and_is_capped(self):
        with mock.patch.dict(os.environ, SECRETS):
            self.turn('lume', 'CERCA: prova', lambda p: {'id': 'x'})
        blob = (self.root / 'registro' / '2026-11-02' / 'lume.jsonl').read_text()
        for v in SECRETS.values():
            self.assertNotIn(v, blob)
        path = self.root / 'registro' / '2026-11-02' / 'lume.jsonl'
        path.write_text('{"x": 1}\n' * (ambiente.JOURNAL_MAX // 9 + 10))
        size = path.stat().st_size
        self.turn('lume', 'NO', lambda p: {'id': 'y'}, rng=4)
        self.assertEqual(path.stat().st_size, size)

    def test_kaggle_records_tool_output(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.object(kt, 'KERNEL_DIR', Path(d)):
            jobs = kt.prepare(self.cfg(True), feed(), NOW, rng=random.Random(3))
            script = (Path(d) / 'kernel.py').read_text()
        self.assertIn('tool_output=r.get("tool_output", "")', script)
        results = [{'bot': j['bot'], 'text': 'Testo generato su Kaggle per la piazza.', 'diary': 'Diario di prova abbastanza lungo.',
                    'skills': '', 'room': j['room'], 'reply_to': None, 'query': 'NOTIZIE: sfida', 'tool_output': 'voci del set',
                    'opened': 'sfida-001'} for j in jobs]
        with mock.patch.object(ab, 'signed_post', lambda *a, **k: {}), mock.patch.object(ab, 'bot_key', lambda *a: None):
            kt.finish(CFG, jobs, results, 'AAAA', lambda p: {'id': 'k1'}, NOW)
        for j in jobs:
            row = self.rows(j['bot'])[-1]
            self.assertEqual((row['runner'], row['strumento'], row['pubblicazione']), ('kaggle', 'NOTIZIE: sfida', 'pubblicato'))
            self.assertEqual(ambiente.load_stato(j['bot'])['riferimenti_in_sospeso']['set'], 'sfida-001')


if __name__ == '__main__':
    unittest.main()
