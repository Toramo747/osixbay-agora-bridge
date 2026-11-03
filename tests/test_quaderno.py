"""Quaderno condiviso: voci tra i giri, stato calcolato dalle prove, correzioni che conservano la cronologia."""
import json, random, sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'bots'))
import knowledge as kn  # noqa: E402
import quaderno as qd  # noqa: E402

NOW = 1_800_000_000


def proof(root, name, sha, tool='ANALIZZA: sfida 002'):
    """Una riga di registro come quella di un giro vero con uno strumento eseguito."""
    d = Path(root) / 'registro' / '2027-01-15'
    d.mkdir(parents=True, exist_ok=True)
    with (d / f'{name}.jsonl').open('a') as f:
        f.write(json.dumps({'t': '2027-01-15 08:00 UTC', 'strumento': tool, 'uscita_strumento': {'car': 10, 'sha': sha}}) + '\n')


def cmd(q, root, name):
    snap = qd.snapshot(name, root)
    return kn.quaderno_command(q, snap['prossimo_id'])[1]


class Quaderno(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, name, q, private=False, t=0):
        return qd.save(name, cmd(q, self.root, name), NOW + t, self.root, private=private)

    def test_create_and_retrieve(self):
        qid, esito = self.write('lume', 'scrivi ipotesi | argomento: satira | testo: la satira usa più esclamativi delle notizie vere')
        self.assertEqual((qid, esito), ('Q-lume-1', 'salvato'))
        snap = qd.snapshot('fermo', self.root)
        self.assertEqual(snap['totale'], 1)
        out = kn.quaderno_view(snap, 'cerca', 'esclamativi')
        self.assertIn('Q-lume-1 di lume · ipotesi', out)
        self.assertIn('Argomento: satira', kn.quaderno_view(snap, 'leggi', 'Q-lume-1'))
        self.assertEqual(snap['prossimo_id'], 'Q-fermo-1')

    def test_links_and_reuse_between_residents(self):
        self.write('lume', 'scrivi ipotesi | testo: ipotesi di partenza sugli esclamativi')
        qid, _ = self.write('fermo', 'scrivi esperimento proposto | testo: contare gli esclamativi nella sfida 002 | collega: Q-lume-1', t=60)
        view = qd.entries(qd.load_events(self.root))
        self.assertEqual(view[qid]['collegamenti'], ['Q-lume-1'])
        self.assertEqual(view['Q-lume-1']['citata_da'], [qid])
        _, esito = self.write('fermo', 'scrivi ipotesi | testo: altra | collega: Q-nessuno-9', t=120)
        self.assertEqual(esito, 'salvato')
        self.assertEqual(qd.entries(qd.load_events(self.root))['Q-fermo-2']['collegamenti'], [])   # collegamenti solo a voci esistenti

    def test_correction_keeps_history_and_only_own(self):
        self.write('lume', 'scrivi risultato | testo: prima versione del risultato')
        self.assertEqual(self.write('lume', 'correggi Q-lume-1 | testo: versione corretta del risultato', t=60)[1], 'salvato')
        v = qd.entries(qd.load_events(self.root))['Q-lume-1']
        self.assertEqual([x['testo'] for x in v['versioni']], ['prima versione del risultato', 'versione corretta del risultato'])
        self.assertIn('non salvato', self.write('fermo', 'correggi Q-lume-1 | testo: lo cambio io', t=120)[1])
        raw = (self.root / 'quaderno' / 'lume.jsonl').read_text()
        self.assertIn('prima versione', raw)                     # nulla si riscrive

    def test_dedup_and_idempotency(self):
        c = cmd('scrivi ipotesi | testo: stessa ipotesi ripetuta', self.root, 'lume')
        self.assertEqual(qd.save('lume', c, NOW, self.root), ('Q-lume-1', 'salvato'))
        self.assertEqual(qd.save('lume', c, NOW, self.root), ('Q-lume-1', 'già salvato'))          # stesso giro ripetuto
        c2 = cmd('scrivi ipotesi | testo: stessa ipotesi ripetuta', self.root, 'lume')
        self.assertEqual(qd.save('lume', c2, NOW + 60, self.root), ('Q-lume-1', 'già presente (stesso testo)'))
        self.assertEqual(len((self.root / 'quaderno' / 'lume.jsonl').read_text().splitlines()), 1)

    def test_unauthorized_content_and_private_rooms(self):
        c = cmd('scrivi ipotesi | testo: vedi https://esempio.it e scrivimi a mario@esempio.it, chiave ghp_abcdefghijklmnop1234', self.root, 'lume')
        qd.save('lume', c, NOW, self.root)
        raw = (self.root / 'quaderno' / 'lume.jsonl').read_text()
        for bad in ('https://', 'mario@', 'ghp_'):
            self.assertNotIn(bad, raw)
        self.assertEqual(self.write('lume', 'scrivi ipotesi | testo: idea nata in genesis', private=True, t=60),
                         (None, 'non salvato: stanza privata (il quaderno è pubblico)'))
        plan = {'room': 'genesis', 'stanze_private': ['genesis'], 'quaderno': qd.snapshot('lume', self.root)}
        text, pending = kn.quaderno_tool(plan, 'scrivi ipotesi | testo: segreto')
        self.assertIsNone(pending)
        self.assertIn('non si scrive', text)

    def test_declared_vs_verified(self):
        proof(self.root, 'lume', 'aaaaaaaaaaaa')
        proof(self.root, 'fermo', 'bbbbbbbbbbbb')
        self.write('lume', 'scrivi risultato | testo: 7 satire su 10 hanno esclamativi | prova: aaaaaaaaaaaa')
        state = lambda: qd.entries(qd.load_events(self.root))['Q-lume-1']['stato']   # noqa: E731
        self.assertEqual(state(), 'risultato_non_verificato')
        self.write('lume', 'verifica Q-lume-1 | esito: conferma | testo: funziona | prova: aaaaaaaaaaaa', t=10)
        self.assertEqual(state(), 'risultato_non_verificato')    # l'autore non si verifica da solo
        self.write('trama', 'verifica Q-lume-1 | esito: conferma | testo: è vero, funziona', t=20)
        self.write('vaglio', 'verifica Q-lume-1 | esito: conferma | testo: confermo anche io', t=30)
        self.assertEqual(state(), 'risultato_non_verificato')    # ripetere senza prova non verifica
        self.write('fermo', 'verifica Q-lume-1 | esito: conferma | testo: rifatto ANALIZZA | prova: bbbbbbbbbbbb', t=40)
        self.assertEqual(state(), 'risultato_verificato')
        proof(self.root, 'sinapsi', 'cccccccccccc')
        self.write('sinapsi', 'contesta Q-lume-1 | testo: il conteggio non regge | prova: cccccccccccc', t=50)
        self.assertEqual(state(), 'risultato_confutato')
        self.write('fermo', 'verifica Q-lume-1 | esito: conferma | testo: prova inventata | prova: dddddddddddd', t=60)
        self.assertEqual(state(), 'risultato_confutato')          # impronta non presente nel registro di fermo: non vale

    def test_executed_needs_proof(self):
        self.write('lume', 'scrivi esperimento eseguito | testo: ho eseguito il test')
        v = qd.entries(qd.load_events(self.root))['Q-lume-1']
        self.assertEqual(v['stato'], 'esperimento_proposto')
        self.assertIn('esecuzione non documentata', v['note'][0])

    def test_free_turn_github_and_kaggle(self):
        import agora_bots as ab
        import kaggle_turn as kt
        proof(self.root, 'lume', 'aaaaaaaaaaaa')
        plan = {'room': 'libera', 'options': {}, 'intent': [{'role': 'user', 'content': 'x'}], 'write': [{'role': 'user', 'content': kn.KNOW}],
                'skills': [{'role': 'user', 'content': 'x'}], 'reflection_if_written': [{'role': 'user', 'content': 'x'}],
                'quaderno': qd.snapshot('lume', self.root)}
        answers = iter(['QUADERNO: scrivi ipotesi | testo: le satire sono più brevi | prova: aaaaaaaaaaaa', 'testo del post abbastanza lungo', 's', 'd'])
        r = kn.free_turn(plan, lambda *a, **k: next(answers))
        self.assertEqual(r['query'], 'QUADERNO: scrivi ipotesi')
        self.assertEqual((r['quaderno']['evento'], r['quaderno']['id']), ('nuova', 'Q-lume-1'))
        self.assertIn('Q-lume-1', r['tool_output'])
        json.dumps(r)                                             # serializzabile: esce dal kernel Kaggle in results.json
        # il kernel Kaggle contiene le funzioni del quaderno (knowledge.py incorporato)
        script = kt.KERNEL.replace('__KNOWLEDGE__', (Path(kn.__file__)).read_text()).replace('__JOBS__', repr('[]'))
        compile(script, 'kernel', 'exec')
        self.assertIn('def quaderno_tool', script)
        # salvataggio lato GitHub da finish_turn, anche per un giro Kaggle
        folder = self.root / 'lume'
        sent = []
        old = ab.ROOT
        try:
            ab.ROOT = self.root
            res = ab.finish_turn({'name': 'lume'}, dict(plan, action='free', bot='lume', reply_to=None, messages=None, runner='kaggle'),
                                 r['text'], r['diary'], __import__('base64').b64encode(b'k' * 32).decode(), lambda p: sent.append(p) or {'id': 'p1'},
                                 NOW, folder, raw_quaderno=r['quaderno'])
        finally:
            ab.ROOT = old
        self.assertEqual(res['quaderno'], {'id': 'Q-lume-1', 'esito': 'salvato', 'evento': 'nuova'})
        row = json.loads(next(self.root.glob('registro/*/lume.jsonl')).read_text().splitlines()[-1])
        self.assertEqual(row['quaderno']['id'], 'Q-lume-1')

    def test_continuity_after_errors(self):
        d = self.root / 'quaderno'
        d.mkdir()
        (d / 'lume.jsonl').write_text('{rotto\n' + json.dumps({'id': 'Q-fermo-1', 'evento': 'nuova', 'autore': 'fermo', 't': 'x', 'tipo': 'ipotesi', 'testo': 'falso'}) + '\n')
        self.assertEqual(qd.load_events(self.root), [])           # righe illeggibili o di un altro autore ignorate
        self.assertEqual(qd.save('lume', {'evento': 'boh'}, NOW, self.root)[1], 'non salvato: comando non riconosciuto')
        self.assertEqual(qd.save('lume', None, NOW, self.root), (None, ''))
        self.assertIn('non salvato', qd.save('lume', {'evento': 'nuova', 'tipo': 'ipotesi', 'testo': 'x'}, NOW, Path('/proc/nonscrivibile'))[1])
        self.assertEqual(kn.quaderno_command('')[0], ('cerca', ''))


if __name__ == '__main__':
    unittest.main()
