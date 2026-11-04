"""godot-consulente: richieste dal feed, piano per Kaggle, pubblicazione con fonti e controllo delle API."""
import base64, json, sys, tempfile, unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / 'bots'))
import consulente as co  # noqa: E402
import kaggle_turn as kt  # noqa: E402

MASTER = base64.b64encode(b'm' * 32).decode()
NOW = 1_800_000_000
CFG = json.loads((REPO / 'bots' / 'bots.json').read_text())
BOT = next(b for b in CFG['bots'] if b['name'] == 'godot-consulente')
LIB = co.library()


def post(pid, text, author='lume', room='generale', ago=60, reply_to=None):
    return {'id': pid, 'author': author, 'room': room, 'text': text, 'created': NOW - ago, 'reply_to': reply_to}


class Requests(unittest.TestCase):
    def test_config(self):
        self.assertEqual((BOT['runner'], BOT['ruolo']), ('kaggle', co.ROLE))
        self.assertNotIn('genesis-godot', [b['name'] for b in CFG['bots']])     # il nome del ponte locale resta libero
        names = [b['name'] for b in CFG['bots']]
        self.assertEqual(names.index('godot-consulente'), names.index('doraimon') + 1)   # stesso modello: caricato una volta
        self.assertEqual(BOT['model']['hf'], next(b for b in CFG['bots'] if b['name'] == 'doraimon')['model']['hf'])
        # non è nell'elenco dei residenti senza tetto del server: il suo tetto (24) resta sotto i 40 del server
        core = (REPO / 'agora' / 'core.mjs').read_text()
        self.assertNotIn("'godot-consulente'", core)
        self.assertLess(CFG['consulente_max_per_day'], 40)

    def test_commands_and_mentions(self):
        self.assertEqual(co.requests_in(post('a', 'Ciao\nGODOT: classe TileMapLayer'), 'godot-consulente'), ['GODOT: classe TileMapLayer'])
        self.assertEqual(co.requests_in(post('a', 'godot: compatibilita TileMap'), 'godot-consulente'), ['GODOT: compatibilita TileMap'])
        code = 'GODOT: verifica\n```gdscript\nextends Node\nfunc _ready():\n\tpass\n```'
        self.assertEqual(co.requests_in(post('a', code), 'godot-consulente'), ['GODOT: verifica extends Node\nfunc _ready():\n\tpass\n'])
        self.assertEqual(co.requests_in(post('a', '@godot-consulente come salvo il mondo?'), 'godot-consulente'),
                         ['GODOT: cerca come salvo il mondo?', 'GODOT: progetta come salvo il mondo?'])
        mention = co.requests_in(post('a', '@godot-consulente come salvo il mondo?\n```gdscript\nextends Node\n```'), 'godot-consulente')
        self.assertEqual(mention[0], 'GODOT: cerca come salvo il mondo?')
        self.assertTrue(mention[1].startswith('GODOT: verifica extends Node'))
        self.assertEqual(co.requests_in(post('a', 'parliamo di godot in generale'), 'godot-consulente'), [])
        self.assertEqual(co.requests_in(post('a', 'GODOT: classe X', author='godot-consulente'), 'godot-consulente'), [])
        self.assertEqual(co.requests_in(post('a', 'GODOT: classe X', author='genesis-godot'), 'godot-consulente'), [])
        self.assertEqual(co.requests_in(post('a', 'GODOT: inventa qualcosa'), 'godot-consulente'), [])

    def test_pending_skips_answered_old_and_lab(self):
        posts = [post('a', 'GODOT: classe Node', ago=100), post('b', 'GODOT: classe Node2D', ago=50),
                 post('r', 'risposta', author='godot-consulente', reply_to='a'),
                 post('c', 'GODOT: classe Timer', ago=5 * 86400), post('d', 'GODOT: classe Timer', room='laboratorio'),
                 post('e', 'GODOT: classe Sprite2D', ago=10)]
        queue = co.pending(posts, 'godot-consulente', {'evase': {'e': {}}}, NOW)
        self.assertEqual([p['id'] for p, _ in queue], ['b'])


@unittest.skipUnless(LIB, 'biblioteca Godot non costruita (genesis/tools/acquire_docs.py + build_index.py)')
class Turn(unittest.TestCase):
    def test_plan_is_text_only_and_bounded(self):
        posts = [post('a', 'GODOT: metodo TileMapLayer.set_cell', ago=200), post('b', '@godot-consulente come uso AStarGrid2D?', ago=100)]
        plan = co.plan(BOT, CFG, posts, NOW, stato={}, lib=LIB)
        self.assertEqual(plan['action'], 'consult')
        self.assertEqual([i['post_id'] for i in plan['items']], ['a'])          # una risposta per giro, la più vecchia
        item = plan['items'][0]
        self.assertIn('func set_cell(coords: Vector2i', item['messages'][1]['content'])
        self.assertNotIn('http', json.dumps(plan))                                # niente link nel kernel né nel testo
        self.assertIn('Fonti (Godot 4.6.3-stable)', item['footer'])
        self.assertLess(sum(len(m['content']) for m in item['messages']), 6000)

    def test_no_requests_no_job(self):
        self.assertIsNone(co.plan(BOT, CFG, [post('a', 'buongiorno')], NOW, stato={}, lib=LIB))
        stato = {'giorno': '2027-01-15', 'risposte_oggi': 99}
        self.assertIsNone(co.plan(BOT, CFG, [post('a', 'GODOT: classe Node')], NOW, stato=stato, lib=LIB))

    def test_compose_footer_warning_and_limits(self):
        plan = co.plan(BOT, CFG, [post('a', 'GODOT: classe TileMapLayer')], NOW, stato={}, lib=LIB)
        item = plan['items'][0]
        text, meta = co.compose(item, 'Usa TileMapLayer.set_cell(). Oppure TileMapLayer.magic_fill() e il nodo SuperChunker.', LIB)
        self.assertIn('magic_fill', ' '.join(meta['api_non_trovate']))
        self.assertIn('SuperChunker', meta['api_non_trovate'])
        self.assertNotIn('TileMapLayer.set_cell', meta['api_non_trovate'])
        self.assertTrue(text.endswith(item['footer'].splitlines()[-1]))
        self.assertLessEqual(len(text), 900)
        long_text, _ = co.compose(item, 'parola ' * 400, LIB)
        self.assertLessEqual(len(long_text), 900)
        empty, meta = co.compose(item, '', LIB)
        self.assertEqual(meta['origine'], 'estratto')
        self.assertIn('Estratto dalla documentazione', empty)

    def test_free_question_adds_catalog_only_when_relevant(self):
        genesis = co.plan(BOT, CFG, [post('a', '@godot-consulente come carico il terreno a chunk in un mondo enorme?')], NOW, stato={}, lib=LIB)
        self.assertIn('catalogo progettuale Genesis', genesis['items'][0]['footer'])
        plain = co.plan(BOT, CFG, [post('a', '@godot-consulente cos\'è un Callable?')], NOW, stato={}, lib=LIB)
        self.assertNotIn('catalogo', plain['items'][0]['footer'])

    def test_not_found_is_declared(self):
        plan = co.plan(BOT, CFG, [post('a', 'GODOT: metodo Node.teleport_to_mars')], NOW, stato={}, lib=LIB)
        self.assertEqual(plan['items'][0]['found'], [False])
        self.assertIn('NON TROVATO', plan['items'][0]['messages'][1]['content'])

    def test_finish_signs_publishes_and_keeps_only_metadata(self):
        posts = [post('a', 'GODOT: classe Node', room='genesis')]
        cfg = dict(CFG, private_rooms_accessible=['genesis'])
        plan = co.plan(BOT, cfg, posts, NOW, stato={}, lib=LIB)
        sent = []
        with tempfile.TemporaryDirectory() as tmp:
            out = co.finish(BOT, plan, {'answers': [{'post_id': 'a', 'text': 'Node è la classe base delle scene.'}]},
                            MASTER, lambda p: sent.append(p) or {'id': 'x1'}, NOW, root=tmp, lib=LIB)
            stato = json.loads((Path(tmp) / 'stato' / 'godot-consulente.json').read_text())
        self.assertEqual(out, [('a', 'pubblicato')])
        self.assertEqual((sent[0]['author'], sent[0]['room'], sent[0]['reply_to']), ('godot-consulente', 'genesis', 'a'))
        self.assertIn('Fonti (Godot 4.6.3-stable)', sent[0]['text'])
        self.assertTrue(sent[0]['signature'])
        rec = stato['evase']['a']
        self.assertEqual((rec['esito'], rec['privata'], rec['risposta']), ('pubblicato', True, 'x1'))
        self.assertNotIn('Node è la classe', json.dumps(stato))                  # nessun testo nello stato pubblico
        self.assertEqual(stato['risposte_oggi'], 1)

    def test_kaggle_prepare_and_finish(self):
        posts = [post('a', '@godot-consulente cos\'è un segnale?')]
        with tempfile.TemporaryDirectory() as tmp:
            kt.KERNEL_DIR = Path(tmp)
            jobs = kt.prepare(CFG, posts, NOW, only='godot-consulente', username='u')
            self.assertEqual([j['action'] for j in jobs], ['consult'])
            script = (Path(tmp) / 'kernel.py').read_text()
            compile(script, 'kernel.py', 'exec')
            self.assertIn('"consult"', script)
            self.assertEqual(kt.prepare(CFG, [post('a', 'ciao')], NOW, only='godot-consulente', username='u'), [])
            sent = []
            co_root = Path(tmp) / 'bots'
            co_root.mkdir()
            orig = co.ab.ROOT
            co.ab.ROOT = co_root
            try:
                report = kt.finish(CFG, jobs, [{'bot': 'godot-consulente', 'answers': [{'post_id': 'a', 'text': 'Un segnale notifica un evento.'}]}],
                                   MASTER, lambda p: sent.append(p) or {'id': 'z'}, NOW)
            finally:
                co.ab.ROOT = orig
        self.assertEqual(report, [('godot-consulente', 'pubblicato (risposta a a)')])
        self.assertEqual(sent[0]['reply_to'], 'a')


if __name__ == '__main__':
    unittest.main()
