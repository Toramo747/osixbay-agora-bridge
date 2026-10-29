import base64, json, sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'bots'))
import registrar as r  # noqa: E402
import agora_bots as ab  # noqa: E402

KEY = base64.b64encode(b'k' * 32).decode()


class Registrar(unittest.TestCase):
    def test_signed_action_is_a_verifiable_post(self):
        key = r.claude_key(KEY)
        p = r.signed_action(key, 'approve_request', {'id': 'q1', 'reason': 'ok'}, 1_800_000_000)
        key.public_key().verify(base64.b64decode(p['signature']), ab.canonical(p))
        self.assertEqual((p['author'], p['room'], p['reply_to']), ('claude', 'registro', None))
        self.assertEqual(json.loads(p['text']), {'action': 'approve_request', 'id': 'q1', 'reason': 'ok'})
        self.assertTrue(16 <= len(p['nonce']) <= 100 and p['nonce'].isalnum())

    def test_residents_use_keys_derived_from_claude(self):
        sent = []
        cfg = {'bots': [{'name': 'lume'}, {'name': 'Bad Name'}]}
        out = r.residents(cfg, KEY, lambda a, args: sent.append((a, args)) or 'registered')
        self.assertEqual(out, [('lume', 'registered'), ('Bad Name', 'nome non valido')])
        self.assertEqual(sent[0][1]['public_key'], ab.public_b64(ab.bot_key(KEY, 'lume')))

    def test_public_requests_keep_only_public_fields(self):
        rows = [{'id': 'b', 'kind': 'agent', 'name': 'skitter', 'note': 'x' * 500, 'created': 2, 'public_key': 'K', 'ip': '1.2.3.4'},
                {'id': 'a', 'kind': 'human', 'github_login': 'someone', 'created': 1, 'session': 's'}]
        out = r.public_requests(rows)
        self.assertEqual([x['id'] for x in out], ['a', 'b'])
        self.assertNotIn('ip', out[1]); self.assertNotIn('session', out[0]); self.assertNotIn('public_key', out[1])
        self.assertEqual(len(out[1]['note']), 300)

    def test_apply_moves_done_keeps_retry_and_rejects_bad(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp); (f / 'decisioni').mkdir()
            (f / 'decisioni' / '1.json').write_text(json.dumps({'id': 'q1', 'decision': 'approve', 'reason': 'agente utile'}))
            (f / 'decisioni' / '2.json').write_text(json.dumps({'id': 'q2', 'decision': 'reject'}))
            (f / 'decisioni' / '3.json').write_text('{"id": "q3", "decision": "maybe"}')
            (f / 'decisioni' / '4.json').write_text('non json')
            calls = []
            def send(action, args):
                calls.append((action, args['id']))
                return 'riprova' if args['id'] == 'q2' else 'ok'
            out = dict(r.apply_decisions(f, send))
            self.assertEqual(calls, [('approve_request', 'q1'), ('reject_request', 'q2')])
            self.assertEqual(out['2.json'], 'riprova')
            self.assertTrue((f / 'decisioni' / '2.json').exists())
            self.assertEqual(json.loads((f / 'applicate' / '1.json').read_text())['outcome'], 'ok')
            self.assertTrue(out['3.json'].startswith('scartata'))
            self.assertTrue(out['4.json'].startswith('scartata'))


if __name__ == '__main__':
    unittest.main()
