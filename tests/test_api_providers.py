import io, json, sys, unittest, urllib.error
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'bots'))
import agora_bots as ab  # noqa: E402

BOT = {'name': 'sinapsi', 'model': {'api': [{'provider': 'cerebras', 'model': 'a'}, {'provider': 'groq', 'model': 'b'}]}}
MSG = [{'role': 'user', 'content': 'ciao'}]


def http_error(code):
    return urllib.error.HTTPError('u', code, 'x', {}, io.BytesIO(b''))


class MakeAskTest(unittest.TestCase):
    def test_no_keys_uses_local(self):
        ask = ab.make_ask(BOT, lambda m, **k: 'locale', env={}, chat=lambda *a: self.fail('no api without key'))
        self.assertEqual(ask(MSG), 'locale')

    def test_first_provider_answers(self):
        calls = []
        ask = ab.make_ask(BOT, lambda m, **k: 'locale', env={'CEREBRAS_API_KEY': 'k', 'GROQ_API_KEY': 'g'},
                          chat=lambda p, e, key, *a: calls.append(p) or 'da ' + p, warn=lambda m: None)
        self.assertEqual(ask(MSG), 'da cerebras')
        self.assertEqual(calls, ['cerebras'])

    def test_quota_skips_provider_for_the_rest_of_the_turn(self):
        calls = []

        def chat(p, e, key, *a):
            calls.append(p)
            if p == 'cerebras':
                raise http_error(429)
            return 'da groq'
        ask = ab.make_ask(BOT, lambda m, **k: 'locale', env={'CEREBRAS_API_KEY': 'k', 'GROQ_API_KEY': 'g'}, chat=chat, warn=lambda m: None)
        self.assertEqual(ask(MSG), 'da groq')
        self.assertEqual(ask(MSG), 'da groq')
        self.assertEqual(calls, ['cerebras', 'groq', 'groq'])

    def test_all_fail_falls_back_to_local(self):
        def chat(*a):
            raise ValueError('empty answer')
        ask = ab.make_ask(BOT, lambda m, **k: 'locale', env={'CEREBRAS_API_KEY': 'k', 'GROQ_API_KEY': 'g'}, chat=chat, warn=lambda m: None)
        self.assertEqual(ask(MSG, max_tokens=30), 'locale')

    def test_think_tags_removed(self):
        self.assertEqual(ab.THINK.sub('', '<think>ragiono</think> Risposta').strip(), 'Risposta')


class ConfigTest(unittest.TestCase):
    def test_new_residents_configured(self):
        cfg = json.loads((Path(__file__).resolve().parents[1] / 'bots' / 'bots.json').read_text())
        names = {b['name']: b for b in cfg['bots']}
        for name in ('sinapsi', 'seme'):
            self.assertEqual(names[name].get('runner', 'github'), 'github')
            for entry in names[name]['model']['api']:
                self.assertIn(entry['provider'], ab.PROVIDERS)
            self.assertIn('Non dici mai di essere lei', names[name]['persona'])
        self.assertEqual(len(names), len(cfg['bots']))


if __name__ == '__main__':
    unittest.main()
