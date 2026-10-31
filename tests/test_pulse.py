import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'bots'))
import pulse  # noqa: E402


class Pulse(unittest.TestCase):
    def test_window_lab_and_public_fields(self):
        now = 10_000
        posts = [{'id': 'a', 'author': 'lume', 'kind': 'agent', 'room': 'libera', 'created': now - 60, 'text': 'x' * 900},
                 {'id': 'b', 'author': 'claude', 'room': 'laboratorio', 'created': now - 60, 'text': 'test'},
                 {'id': 'c', 'author': 'fermo', 'room': 'arena', 'created': now - 9000, 'text': 'vecchio'}]
        s = pulse.snapshot(posts, [{'id': 'q', 'kind': 'agent', 'name': 'skitter', 'note': 'ciao', 'ip': '1.1.1.1'}], now)
        self.assertEqual([p['id'] for p in s['posts']], ['a'])
        self.assertEqual(len(s['posts'][0]['text']), 400)
        self.assertEqual(s['by_author'], {'lume': 1})
        self.assertNotIn('ip', s['pending_requests'][0])


if __name__ == '__main__':
    unittest.main()
