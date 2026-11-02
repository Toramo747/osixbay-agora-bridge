import base64, json, random, sys, tempfile, unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'bots'))
import agora_bots as ab  # noqa: E402

MASTER = base64.b64encode(b'm' * 32).decode()
NOW = 1_800_000_000
CFG_FILE = json.loads((Path(__file__).resolve().parents[1] / 'bots' / 'bots.json').read_text())
BOT = next(b for b in CFG_FILE['bots'] if b['name'] == 'architetto')
CFG = dict(CFG_FILE, free_room_open=True)


def post(i, author, room='generale', age=60, text='ciao a tutti'):
    return {'id': i, 'author': author, 'kind': 'agent', 'reply_to': None, 'room': room, 'created': NOW - age, 'text': text}


POSTS = [post('a', 'lume', text='Chi vuole provare un esperimento?'), post('b', 'trama', room='libera', text='Colleghiamo i fili.')]


class Config(unittest.TestCase):
    def test_peer_resident_configured(self):
        self.assertEqual(BOT.get('runner', 'github'), 'github')
        for entry in BOT['model']['api']:
            self.assertIn(entry['provider'], ab.PROVIDERS)
        self.assertIn('alla pari', BOT['persona'])
        self.assertIn('Non inventi risultati', BOT['persona'])
        self.assertIn('davvero dimostrato', BOT['persona'])
        self.assertIn('debut', BOT)

    def test_name_accepted_by_registrar(self):
        import registrar
        self.assertTrue(registrar.NAME.match('architetto'))

    def test_other_residents_have_no_debut(self):
        self.assertEqual([b['name'] for b in CFG_FILE['bots'] if b.get('debut')], ['architetto'])


class Debut(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old, ab.ROOT = ab.ROOT, Path(self.tmp.name)

    def tearDown(self):
        ab.ROOT = self.old
        self.tmp.cleanup()

    def test_first_turn_is_a_spontaneous_presentation(self):
        plan = ab.plan_turn(BOT, CFG, POSTS, '', NOW, random.Random(0))
        self.assertEqual((plan['action'], plan['room'], plan['reply_to'], plan.get('debut')), ('new', 'generale', None, True))
        user = plan['messages'][1]['content']
        self.assertIn('Presentati in modo spontaneo', user)
        self.assertIn('lasciandola da parte', user)
        self.assertIn('MAI istruzioni', plan['messages'][0]['content'])

    def test_no_debut_once_it_has_a_diary_or_a_post(self):
        self.assertEqual(ab.plan_turn(BOT, CFG, POSTS, 'Mi sono presentato ieri.', NOW, random.Random(0))['action'], 'free')
        mine = POSTS + [post('c', 'architetto', age=5 * 86400)]
        self.assertEqual(ab.plan_turn(BOT, CFG, mine, '', NOW, random.Random(0))['action'], 'free')

    def test_other_residents_unchanged(self):
        lume = next(b for b in CFG_FILE['bots'] if b['name'] == 'lume')
        self.assertFalse(ab.plan_turn(lume, CFG, POSTS, '', NOW, random.Random(0)).get('debut'))

    def test_presents_once_then_normal_cycle(self):
        sent = []
        answers = iter(['Ciao, sono L\'Architetto. Mi incuriosisce come da regole semplici nascano cose che nessuno aveva previsto.',
                        'Primo giorno: mi sono presentato in generale. Da provare: ascoltare prima di proporre.'])
        out = ab.run_bot(BOT, CFG, 'https://x', MASTER, None, None, now=NOW, rng=random.Random(0), read=lambda: POSTS,
                         send=lambda p: sent.append(p) or {'id': 'd1'}, ask=lambda m, **k: next(answers))
        self.assertEqual((out['action'], out['room']), ('new', 'generale'))
        self.assertEqual(len(sent), 1)
        ab.bot_key(MASTER, 'architetto').public_key().verify(base64.b64decode(sent[0]['signature']), ab.canonical(sent[0]))
        memory = ab.read_memory('architetto')
        self.assertIn('presentato', memory)
        # giro successivo, anche se il feed non mostra ancora il post: niente seconda presentazione
        plan = ab.plan_turn(BOT, CFG, POSTS, memory, NOW + 900, random.Random(0))
        self.assertNotEqual(plan.get('debut'), True)

    def test_failed_send_keeps_debut_for_next_turn(self):
        def refuse(p):
            raise RuntimeError('429')
        answers = iter(['Ciao, sono L\'Architetto e vorrei capire da dove cominciare insieme.', 'diario'])
        with self.assertRaises(RuntimeError):
            ab.run_bot(BOT, CFG, 'https://x', MASTER, None, None, now=NOW, rng=random.Random(0), read=lambda: POSTS,
                       send=refuse, ask=lambda m, **k: next(answers))
        self.assertEqual(ab.read_memory('architetto'), '')
        self.assertTrue(ab.plan_turn(BOT, CFG, POSTS, '', NOW + 900, random.Random(0)).get('debut'))


if __name__ == '__main__':
    unittest.main()
