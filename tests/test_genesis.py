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

    def test_config(self):
        cfg = json.loads((Path(__file__).resolve().parents[1] / 'bots' / 'bots.json').read_text())
        self.assertEqual(cfg['private_rooms'], ['genesis'])


if __name__ == '__main__':
    unittest.main()
