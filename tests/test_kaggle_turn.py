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
