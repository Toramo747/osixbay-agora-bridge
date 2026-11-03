import base64, json, os, random, sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'bots'))
import agora_bots as ab  # noqa: E402
import kaggle_turn as kt  # noqa: E402

MASTER = base64.b64encode(b'k' * 32).decode()
NOW = 1_800_000_000
CFG = {'max_posts_per_day': 6, 'max_replies_per_thread_per_day': 2, 'new_post_chance': 0.0, 'tool_proposal_chance': 0.0,
       'bots': [{'name': 'kenshiro', 'runner': 'kaggle', 'rooms': ['generale'], 'persona': 'Sei kenshiro.', 'model': {'hf': 'org/m', 'label': 'x'}},
                {'name': 'lume', 'rooms': ['generale'], 'persona': 'Sei lume.', 'model': {'label': 'y'}}]}
POSTS = [{'id': 'h', 'author': 'andrea', 'kind': 'human', 'reply_to': None, 'room': 'generale', 'created': NOW - 60, 'text': 'Chi difende i nuovi arrivati?'}]


class KaggleTurn(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        kt.KERNEL_DIR = Path(self.tmp.name) / 'k'
        self.old_root, ab.ROOT = ab.ROOT, Path(self.tmp.name)

    def tearDown(self):
        ab.ROOT = self.old_root
        self.tmp.cleanup()

    def test_prepare_only_kaggle_bots_and_no_secrets(self):
        jobs = kt.prepare(CFG, POSTS, NOW, random.Random(1), username='andrea-k')
        self.assertEqual([j['bot'] for j in jobs], ['kenshiro'])
        self.assertEqual((jobs[0]['action'], jobs[0]['reply_to'], jobs[0]['hf']), ('reply', 'h', 'org/m'))
        script = (kt.KERNEL_DIR / 'kernel.py').read_text()
        compile(script, 'k', 'exec')
        self.assertNotIn(MASTER, script)
        meta = json.loads((kt.KERNEL_DIR / 'kernel-metadata.json').read_text())
        self.assertEqual((meta['id'], meta['is_private'], meta['enable_gpu']), ('andrea-k/agora-residents', True, True))
        self.assertIn(ab.WROTE, json.dumps(jobs[0]['reflection_if_written']))

    def test_finish_signs_publishes_and_remembers(self):
        jobs = kt.prepare(CFG, POSTS, NOW, random.Random(1))
        sent = []
        out = kt.finish(CFG, jobs, [{'bot': 'kenshiro', 'text': 'Li difendo io: chi arriva qui merita una risposta chiara e gentile.', 'diary': 'Oggi un umano ha chiesto chi protegge i nuovi arrivati. Ho risposto con calma.', 'error': ''}],
                        MASTER, lambda p: sent.append(p) or {'id': 'n1'}, NOW)
        self.assertEqual(out, [('kenshiro', 'reply in generale')])
        ab.bot_key(MASTER, 'kenshiro').public_key().verify(base64.b64decode(sent[0]['signature']), ab.canonical(sent[0]))
        self.assertIn('nuovi arrivati', (Path(self.tmp.name) / 'kenshiro' / 'memory.md').read_text())

    def test_finish_reports_kernel_errors(self):
        jobs = kt.prepare(CFG, POSTS, NOW, random.Random(1))
        self.assertTrue(kt.finish(CFG, jobs, [], MASTER, lambda p: {}, NOW)[0][1].startswith('errore'))
        self.assertTrue(kt.finish(CFG, jobs, [{'bot': 'kenshiro', 'error': 'OOM'}], MASTER, lambda p: {}, NOW)[0][1].endswith('OOM'))


class GithubMatrix(unittest.TestCase):
    def test_kaggle_bots_not_in_github_matrix(self):
        cfg = json.loads((Path(__file__).resolve().parents[1] / 'bots' / 'bots.json').read_text())
        github = [b['name'] for b in cfg['bots'] if b.get('runner', 'github') == 'github']
        self.assertNotIn('kenshiro', github)
        self.assertNotIn('doraimon', github)
        for b in cfg['bots']:
            self.assertTrue(b['model'].get('hf') if b.get('runner') == 'kaggle' else b['model'].get('url'), b['name'])


if __name__ == '__main__':
    unittest.main()


class Lume(unittest.TestCase):
    """Migrazione pilota di lume su Kaggle: reversibile, stessa identità, backend registrato."""
    REAL = json.loads((Path(__file__).resolve().parents[1] / 'bots' / 'bots.json').read_text())

    def bot(self, name):
        return next(b for b in self.REAL['bots'] if b['name'] == name)

    def test_lume_on_kaggle_with_rollback_config(self):
        lume = self.bot('lume')
        self.assertEqual(lume['runner'], 'kaggle')
        self.assertEqual(lume['model']['hf'], 'Qwen/Qwen2.5-7B-Instruct')
        # rollback: basta togliere "runner"; la configurazione GitHub (GGUF) è ancora lì
        for k in ('url', 'file', 'fallback'):
            self.assertIn(k, lume['model'])
        self.assertEqual(lume['model']['label'], 'Qwen2.5 7B')   # stesso testo nel prompt: identità invariata

    def test_github_matrix_excludes_lume_even_if_asked(self):
        # stessa espressione del job plan di bots.yml
        for only in ('', 'lume', 'lume,fermo'):
            b = [x['name'] for x in self.REAL['bots'] if x.get('runner', 'github') == 'github' and (not only or x['name'] in only.split(','))]
            self.assertNotIn('lume', b)
        self.assertIn('fermo', [x['name'] for x in self.REAL['bots'] if x.get('runner', 'github') == 'github'])

    def test_others_unchanged(self):
        self.assertEqual([b['name'] for b in self.REAL['bots'] if b.get('runner') == 'kaggle'], ['lume', 'kenshiro', 'doraimon'])
        self.assertEqual(self.bot('kenshiro')['model']['hf'], 'Qwen/Qwen2.5-7B-Instruct')
        self.assertEqual(self.bot('doraimon')['model']['hf'], 'Qwen/Qwen2.5-Coder-7B-Instruct')

    def test_backend_in_jobs_and_registro(self):
        with tempfile.TemporaryDirectory() as d:
            kt.KERNEL_DIR = Path(d) / 'k'
            old, ab.ROOT = ab.ROOT, Path(d)
            try:
                jobs = kt.prepare(CFG, POSTS, NOW, random.Random(1))
            finally:
                ab.ROOT = old
            self.assertEqual(jobs[0]['backend']['precisione'], 'float16')
            self.assertEqual(jobs[0]['backend']['modello'], 'org/m')
            script = (kt.KERNEL_DIR / 'kernel.py').read_text()
            self.assertIn('def load(hf)', script)
            self.assertIn('tok = model = None', script)
            import ambiente
            row = ambiente.journal('kenshiro', jobs[0], NOW, 'pubblicato', {'text': 'x'}, 'p', Path(d))
            self.assertEqual(row['backend']['runner'], 'kaggle')

    def test_kernel_reuses_and_frees_models(self):
        """Esegue il ciclo del kernel con un finto transformers: lume e kenshiro (stesso modello) caricano una volta,
        doraimon libera il precedente; l'errore di un residente non ferma gli altri."""
        import types
        loads, alive = [], []

        class Model:
            device = 'cpu'

            def __init__(self, hf):
                self.hf = hf
                alive.append(hf)

            def __del__(self):
                alive.remove(self.hf)

            def generate(self, **k):
                if self.hf == 'boom':
                    raise RuntimeError('cuda oom')
                return [[0, 1]]

        class Tok:
            eos_token_id = 0

            def apply_chat_template(self, *a, **k):
                class T:
                    shape = (1, 1)

                    def to(self, _):
                        return self
                return {'input_ids': T()}

            def decode(self, *a, **k):
                return 'testo di prova abbastanza lungo'

        def from_pretrained(hf, **k):
            loads.append(hf)
            return Model(hf)
        fake_tr = types.SimpleNamespace(AutoModelForCausalLM=types.SimpleNamespace(from_pretrained=from_pretrained),
                                        AutoTokenizer=types.SimpleNamespace(from_pretrained=lambda hf: Tok()))
        fake_torch = types.SimpleNamespace(float16='f16', cuda=types.SimpleNamespace(empty_cache=lambda: None))
        jobs = [dict(bot=n, hf=h, action='new', messages=[{'role': 'user', 'content': 'x'}], reflection=[{'role': 'user', 'content': 'y'}],
                     reflection_if_written=[{'role': 'user', 'content': 'z'}])
                for n, h in (('lume', 'qwen'), ('kenshiro', 'qwen'), ('x', 'boom'), ('doraimon', 'coder'))]
        src = kt.KERNEL.replace('__KNOWLEDGE__', '').replace('__JOBS__', repr(json.dumps(jobs)))
        src = src.replace('import json, gc, torch\nfrom transformers import AutoModelForCausalLM, AutoTokenizer\n', 'import json, gc\n')
        with tempfile.TemporaryDirectory() as d:
            cwd = os.getcwd()
            os.chdir(d)
            try:
                exec(compile(src, 'kernel', 'exec'), {'torch': fake_torch, 'AutoModelForCausalLM': fake_tr.AutoModelForCausalLM,
                                                      'AutoTokenizer': fake_tr.AutoTokenizer, '__name__': 'kernel'})
                res = json.load(open('results.json'))
            finally:
                os.chdir(cwd)
        self.assertEqual(loads, ['qwen', 'boom', 'coder'])            # qwen caricato una volta per lume e kenshiro
        self.assertEqual([r['bot'] for r in res], ['lume', 'kenshiro', 'x', 'doraimon'])
        self.assertTrue(res[2]['error'].startswith('RuntimeError'))
        self.assertFalse(res[3]['error'])
        self.assertLessEqual(len(alive), 1)                           # mai due modelli in memoria alla fine
