"""genesi-costruttore: stato dal feed di genesis, piano per Kaggle, messaggio con script fisso, ponte emulato."""
import base64, json, os, shutil, subprocess, sys, tempfile, unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / 'bots'))
sys.path.insert(0, str(REPO / 'genesis' / 'tools'))
import costruttore as cs  # noqa: E402
import kaggle_turn as kt  # noqa: E402

MASTER = base64.b64encode(b'm' * 32).decode()
NOW = 1_800_000_000
CFG = json.loads((REPO / 'bots' / 'bots.json').read_text())
BOT = next(b for b in CFG['bots'] if b['name'] == 'genesi-costruttore')
OPEN = dict(CFG, private_rooms_accessible=['genesis'])
ME = 'genesi-costruttore'
cs.PUBLIC_WORLD = Path(tempfile.mkdtemp()) / 'genesi' / 'mondo.json'  # i test non scrivono nel repository


def step(pid, ago, direction='est'):
    return {'id': pid, 'author': ME, 'room': 'genesis', 'created': NOW - ago, 'reply_to': None,
            'text': 'nota\n```gdscript\n' + cs.script(direction) + '\n```'}


def bridge(pid, to, ok=True, passo=3, ago=10):
    out = 'GENESI {"passo": %d, "chunk": 9, "nuovi": ["2,0"], "totali": {"oceano": 900}}' % passo if ok else 'Errore: Parse Error'
    return {'id': pid, 'author': 'genesis-godot', 'room': 'genesis', 'created': NOW - ago, 'reply_to': to, 'text': 'Esito: ok\n' + out}


class State(unittest.TestCase):
    def test_config(self):
        self.assertEqual((BOT['runner'], BOT['ruolo'], BOT['rooms']), ('kaggle', cs.ROLE, ['genesis']))
        self.assertIn('architetto', [b['name'] for b in CFG['bots']])          # L'Architetto resta com'era
        arch = next(b for b in CFG['bots'] if b['name'] == 'architetto')
        self.assertNotIn('ruolo', arch)

    def test_script_fits_and_is_fixed(self):
        for d in cs.DIRECTIONS:
            code = cs.script(d)
            self.assertNotIn('__', code)
            self.assertIn(cs.DIRECTIONS[d], code)
            self.assertLess(len(code), 1620)
        self.assertNotIn('http', cs.script('est'))

    def test_closed_without_genesis(self):
        self.assertEqual(cs.status([], ME, NOW, CFG)[0], 'chiuso')
        self.assertIsNone(cs.plan(BOT, CFG, [], NOW))

    def test_first_step_then_wait_then_continue(self):
        self.assertEqual(cs.status([], ME, NOW, OPEN)[0], 'pronto')
        pending = [step('s1', 3600)]
        self.assertEqual(cs.status(pending, ME, NOW, OPEN)[0], 'attesa')         # computer spento: si aspetta
        self.assertEqual(cs.status([step('s1', 49 * 3600)], ME, NOW, OPEN)[0], 'pronto')   # dopo 48 h si ripropone
        done = pending + [bridge('b1', 's1')]
        self.assertEqual(cs.status(done, ME, NOW, OPEN)[0], 'pronto')

    def test_two_failures_stop(self):
        posts = [step('s1', 7200), bridge('b1', 's1', ok=False, ago=7000), step('s2', 3600), bridge('b2', 's2', ok=False, ago=3000)]
        self.assertEqual(cs.status(posts, ME, NOW, OPEN)[0], 'fermo')
        posts[-1] = bridge('b2', 's2', ok=True)
        self.assertEqual(cs.status(posts, ME, NOW, OPEN)[0], 'pronto')

    def test_daily_cap(self):
        posts = []
        for i in range(12):
            posts += [step(f's{i}', 3600 * (i + 1)), bridge(f'b{i}', f's{i}', ago=3600 * i + 60)]
        self.assertEqual(cs.status(posts, ME, NOW, OPEN)[0], 'tetto')

    def test_plan_uses_last_result_and_suggestions_as_data(self):
        posts = [step('s1', 7200, 'sud'), bridge('b1', 's1', passo=3),
                 {'id': 'r1', 'author': 'lume', 'room': 'genesis', 'created': NOW - 100, 'text': '@genesi-costruttore vai verso il mare'}]
        p = cs.plan(BOT, OPEN, posts, NOW)
        user = p['items'][0]['messages'][1]['content']
        self.assertIn('9 zone dopo il passo 3', user)
        self.assertIn('Ultima direzione: sud', user)
        self.assertIn('lume: @genesi-costruttore vai verso il mare', user)
        self.assertEqual((p['passo_atteso'], p['default_direction']), (4, 'nord'))     # ORDER[3 % 4]

    def test_compose_model_choice_default_and_limit(self):
        p = cs.plan(BOT, OPEN, [], NOW)
        text, meta = cs.compose(p, 'DIREZIONE: nord\nNOTA: Allargo la costa verso nord.')
        self.assertEqual(meta, {'direzione': 'nord', 'scelta_dal_modello': True})
        self.assertTrue(text.startswith('Allargo la costa verso nord.\n```gdscript\nextends Node'))
        self.assertIn('const D := Vector2i(0, -1)', text)
        self.assertLessEqual(len(text), cs.MESSAGE_MAX)
        text, meta = cs.compose(p, 'scrivo codice: ```gdscript\nOS.execute("rm")\n```')
        self.assertEqual(meta['scelta_dal_modello'], False)
        self.assertNotIn('OS.execute', text)                                      # il modello non scrive codice
        self.assertEqual(text.count('```'), 2)
        long, _ = cs.compose(p, 'DIREZIONE: est\nNOTA: ' + 'parola ' * 200)
        self.assertLessEqual(len(long), cs.MESSAGE_MAX)

    def test_kaggle_prepare_and_finish_publish_only_in_genesis(self):
        with tempfile.TemporaryDirectory() as tmp:
            kt.KERNEL_DIR = Path(tmp)
            private = {'genesi-costruttore': {'accessible': ['genesis'], 'posts': [], 'status': {'genesis': 'ok'}}}
            jobs = kt.prepare(CFG, [], NOW, only='genesi-costruttore', username='u', private=private)
            self.assertEqual([j['action'] for j in jobs], ['build'])
            compile((Path(tmp) / 'kernel.py').read_text(), 'kernel.py', 'exec')
            sent = []
            report = kt.finish(CFG, jobs, [{'bot': ME, 'answers': [{'post_id': 'passo', 'text': 'DIREZIONE: est\nNOTA: Primo passo.'}]}],
                               MASTER, lambda p: sent.append(p) or {'id': 'g1'}, NOW)
        self.assertEqual(report, [(ME, 'pubblicato passo 1 verso est')])
        self.assertEqual((sent[0]['room'], sent[0]['reply_to'], sent[0]['author']), ('genesis', None, ME))
        self.assertTrue(sent[0]['signature'])


def godot():
    try:
        from common import godot_binary
        return godot_binary()
    except Exception:  # noqa: BLE001
        return None


@unittest.skipUnless(godot(), 'binario Godot 4.6.3 assente: python3 genesis/tools/acquire_docs.py --with-godot')
class EmulatedBridge(unittest.TestCase):
    """Lo script pubblicato gira davvero in Godot 4.6.3 con un ponte emulato, per più passi di fila."""

    def run_step(self, proj, env, direction):
        (proj / 'passo.gd').write_text(cs.script(direction))
        out = subprocess.run([str(godot()), '--headless', '--path', str(proj)], env=env, capture_output=True, text=True, timeout=120)
        return cs.bridge_result(out.stdout), out

    def test_four_steps_persist_and_grow(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = Path(tmp) / 'p'
            shutil.copytree(REPO / 'tests' / 'ponte_emulato', proj)
            env = {'PATH': '/usr/bin:/bin', 'HOME': f'{tmp}/home', 'XDG_DATA_HOME': f'{tmp}/xdg', 'XDG_CONFIG_HOME': f'{tmp}/xdg'}
            subprocess.run([str(godot()), '--headless', '--import', '--path', str(proj)], env=env, capture_output=True, timeout=120)
            results = []
            for d in ('est', 'est', 'nord', 'ovest'):
                res, out = self.run_step(proj, env, d)
                self.assertIsNotNone(res, out.stdout[-500:] + out.stderr[-500:])
                self.assertNotIn('SCRIPT ERROR', out.stderr)
                results.append(res)
        self.assertEqual([r['passo'] for r in results], [1, 2, 3, 4])
        self.assertEqual([r['chunk'] for r in results], [1, 5, 9, 13])
        self.assertEqual(sum(results[-1]['totali'].get(b, 0) for b in
                             ('oceano', 'spiaggia', 'montagna', 'foresta', 'deserto', 'prateria')), 13 * 32 * 32)
        self.assertTrue(all(int(k.split(',')[1]) <= 0 for k in results[2]['nuovi']))      # passo verso nord


if __name__ == '__main__':
    unittest.main()


class PublicWorld(unittest.TestCase):
    """Eccezione decisa da Andrea (4/11): seme, esiti e zone pubblici; nient'altro di genesis."""
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)

    def test_only_seed_outcomes_and_zones(self):
        ok = {'id': 'b2', 'author': 'genesis-godot', 'room': 'genesis', 'created': NOW - 10, 'reply_to': 's2',
              'text': 'C:/Users/andrea/ponte\nGENESI {"passo": 2, "seme": 4242, "chunk": 5, "nuovi": ["1,0", "-1,0", "../x"], "totali": {"oceano": 9}}'}
        b1 = dict(bridge('b1', 's1', passo=1, ago=7000), text='GENESI {"passo": 1, "chunk": 1, "nuovi": ["0,0"], "totali": {}}')
        posts = [step('s1', 7200), b1, step('s2', 3600), ok, step('s3', 60)]
        world = cs.public_world(cs.history(posts, ME))
        self.assertEqual(world, {'seme': 4242, 'zone': ['0,0', '1,0', '-1,0'],
                                 'passi': [{'passo': 1, 'esito': 'riuscito'}, {'passo': 2, 'esito': 'riuscito'}],
                                 'passo_in_attesa_del_ponte': True})
        text = json.dumps(world)
        for leak in ('Users', 'andrea', 'nota', 'gdscript', 'oceano', '../x'):
            self.assertNotIn(leak, text)

    def test_failed_step_and_write_only_on_change(self):
        posts = [step('s1', 7200), bridge('b1', 's1', ok=False, ago=7000)]
        world = cs.public_world(cs.history(posts, ME))
        self.assertEqual((world['seme'], world['zone'], world['passi']), (None, [], [{'passo': 1, 'esito': 'fallito'}]))
        path = self.tmp / 'genesi' / 'mondo.json'
        self.assertTrue(cs.save_public_world(cs.history(posts, ME), path))
        self.assertFalse(cs.save_public_world(cs.history(posts, ME), path))

    def test_script_reports_seed(self):
        self.assertIn('"seme": s', cs.script('est'))
