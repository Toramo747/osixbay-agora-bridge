"""Stanza privata genesis: lettura firmata dei residenti, testo omesso nel registro pubblico."""
import base64, json, sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'bots'))
import agora_bots as ab  # noqa: E402
import ambiente  # noqa: E402

MASTER = base64.b64encode(b'm' * 32).decode()
NOW = 1_800_000_000


class Genesis(unittest.TestCase):
    def test_signed_read_matches_server_scheme(self):
        key = ab.bot_key(MASTER, 'lume')
        h = ab.signed_read_headers(key, 'lume', 'genesis', NOW)
        self.assertEqual((h['X-Agora-Agent'], h['X-Agora-Timestamp']), ('lume', str(NOW)))
        self.assertRegex(h['X-Agora-Nonce'], r'^[A-Za-z0-9-]{16,100}$')
        payload = {'author': 'lume', 'room': 'genesis', 'reply_to': None, 'text': 'GET /rooms/genesis.json',
                   'nonce': h['X-Agora-Nonce'], 'timestamp': NOW}
        canonical = json.dumps(payload, ensure_ascii=False, separators=(',', ':')).encode()
        key.public_key().verify(base64.b64decode(h['X-Agora-Signature']), canonical)   # solleva se non valida
        self.assertEqual(len(base64.b64decode(h['X-Agora-Signature'])), 64)

    def test_private_posts_merged_and_denied_room_skipped(self):
        def get(room):
            if room == 'segreta':
                raise OSError('404')
            return {'posts': [{'id': 'g1', 'author': 'Toramo747', 'kind': 'human', 'text': 'GENESIS', 'date': '2027-01-15T08:00:00Z'}]}
        posts = ab.read_private_rooms('https://x', ['genesis', 'segreta'], 'lume', MASTER, get=get)
        self.assertEqual([(p['id'], p['room']) for p in posts], [('g1', 'genesis')])
        self.assertIn('genesis', ab.public_places(posts))

    def test_registro_omits_private_text(self):
        with tempfile.TemporaryDirectory() as d:
            plan = {'action': 'free', 'room': 'genesis', 'stanze_private': ['genesis'], 'giro': 'libero'}
            row = ambiente.journal('lume', plan, NOW, 'pubblicato', {'text': 'idea per il mondo 2D'}, 'p', Path(d))
            self.assertNotIn('testo', row)
            self.assertEqual(row['testo_omesso']['motivo'], 'stanza privata')
            pub = dict(plan, room='libera')
            self.assertEqual(ambiente.journal('lume', pub, NOW, 'pubblicato', {'text': 'ciao'}, 'q', Path(d))['testo'], 'ciao')

    def test_empty_room_stays_accessible_error_is_not_empty(self):
        def get(room):
            if room == 'rotta':
                raise OSError('rete')
            if room == 'strana':
                return {'errore': 'x'}
            return {'posts': []}
        st = ab.read_private_rooms_status('https://x', ['genesis', 'rotta', 'strana'], 'lume', MASTER, get=get)
        self.assertEqual((st['posts'], st['accessible']), ([], ['genesis']))
        self.assertEqual(set(st['errors']), {'rotta', 'strana'})
        self.assertIn('genesis', ab.public_places([], st['accessible']))
        self.assertNotIn('genesis', ab.public_places([], []))
        self.assertNotIn(ab.LAB, ab.public_places([], [ab.LAB]))

    def test_observe_lists_empty_private_room(self):
        cfg = {'bots': [{'name': 'lume'}], 'private_rooms': ['genesis'], 'private_rooms_accessible': ['genesis']}
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / 'dati').mkdir()
            sec = ambiente.observe({'name': 'lume'}, cfg, [], NOW, stato={}, root=Path(d))
        self.assertIn('- genesis (riservata ai residenti e ad Andrea)', sec['luoghi'])
        self.assertIn('genesis', sec['ambiente'])

    def test_plan_free_offers_empty_genesis(self):
        import random
        cfg = json.loads((Path(__file__).resolve().parents[1] / 'bots' / 'bots.json').read_text())
        cfg.update(free_room_open=True, free_chance=1.0, private_rooms_accessible=['genesis'])
        bot = cfg['bots'][0]
        plan = ab.plan_free(bot, cfg, [], '', '', NOW, random.Random(1))
        self.assertIn('genesis', plan['options'])
        self.assertIn('genesis (riservata ai residenti e ad Andrea)', plan['where'][1]['content'])
        cfg['private_rooms_accessible'] = []
        self.assertNotIn('genesis', ab.plan_free(bot, cfg, [], '', '', NOW, random.Random(1))['options'])

    def test_private_turn_writes_nothing_public(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            folder = root / 'lume'
            folder.mkdir()
            (folder / 'memory.md').write_text('# Memoria di lume\n\nprima\n')
            sent = []
            plan = {'action': 'free', 'room': 'genesis', 'reply_to': None, 'stanze_private': ['genesis'], 'giro': 'libero', 'messages': None}
            old_root = ab.ROOT
            ab.ROOT = root
            try:
                res = ab.finish_turn({'name': 'lume'}, plan, 'Un universo 2D persistente con regole fisiche semplici.',
                                     'Ho parlato di SEGRETOGENESIS e del mondo 2D in modo approfondito oggi.', MASTER,
                                     lambda p: sent.append(p) or {'id': 'g9'}, NOW, folder,
                                     raw_skills='So fare SEGRETOGENESIS e molto altro ancora, imparo ogni giorno.',
                                     raw_wish='DESIDERIO: vorrei SEGRETOGENESIS per il mondo',
                                     raw_place='In genesis si immagina SEGRETOGENESIS e si discute del mondo 2D.',
                                     extra={'query': 'ANALIZZA: SEGRETOGENESIS frase privata', 'tool_output': 'SEGRETOGENESIS conteggi'})
            finally:
                ab.ROOT = old_root
            self.assertEqual((res['room'], res['privato']), ('genesis', True))
            self.assertEqual(sent[0]['room'], 'genesis')
            public = ''.join(p.read_text() for p in root.rglob('*') if p.is_file())
            self.assertNotIn('SEGRETOGENESIS', public)
            self.assertNotIn('mondo 2D', public)
            self.assertFalse((root / 'luoghi' / 'genesis.md').exists())
            self.assertFalse(list(root.rglob('uscite')))
            row = json.loads(next(root.glob('registro/*/lume.jsonl')).read_text())
            self.assertEqual((row['strumento'], row['testo_omesso']['motivo']), ('ANALIZZA', 'stanza privata'))
            self.assertNotIn('estratto', row['uscita_strumento'])

    def test_private_search_query_reduced_to_kind(self):
        with tempfile.TemporaryDirectory() as d:
            plan = {'action': 'free', 'room': 'genesis', 'stanze_private': ['genesis'], 'giro': 'libero'}
            row = ambiente.journal('lume', plan, NOW, 'pubblicato', {'text': 'x' * 20, 'query': 'motore fisico segreto'}, 'p', Path(d))
            self.assertEqual(row['strumento'], 'CERCA')

    def test_map_mentions_genesis_neutrally(self):
        self.assertIn('genesis', ab.read_map())

    def test_config(self):
        cfg = json.loads((Path(__file__).resolve().parents[1] / 'bots' / 'bots.json').read_text())
        self.assertEqual(cfg['private_rooms'], ['genesis'])


if __name__ == '__main__':
    unittest.main()
