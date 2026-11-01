import json, random, sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'bots'))
import agora_bots as ab  # noqa: E402
import knowledge as kn  # noqa: E402

RSS = ('<rss><channel><item><title>Manovra, cosa cambia per la sanità - ANSA</title><source url="https://www.ansa.it">ANSA</source>'
       '<pubDate>Sat, 31 Oct 2026 10:00:00 GMT</pubDate></item></channel></rss>')
CHECK = ('<rss><channel><item><title>La Svezia non ha abbandonato i vaccini a mRNA - Open</title><source url="https://www.open.online">Open</source>'
         '<pubDate>Fri, 30 Oct 2026 09:00:00 GMT</pubDate></item></channel></rss>')
GDELT = json.dumps({'articles': [{'title': 'Fondo sanitario a 146 miliardi', 'domain': 'ilsole24ore.com', 'seendate': '20261031T100000Z'},
                                 {'title': 'Manovra, cosa cambia per la sanità', 'domain': 'ansa.it', 'seendate': '20261031T100000Z'}]})


def fake_get(url):
    if 'news.google.com' in url:
        return CHECK if 'site%3Afacta.news' in url else RSS
    if 'gdeltproject' in url:
        return GDELT
    raise ValueError(url)


class News(unittest.TestCase):
    def test_news_and_fact_checks(self):
        text = kn.news('sanità', get=fake_get)
        self.assertIn('Manovra, cosa cambia per la sanità (ANSA, 31 Oct 2026)', text)
        self.assertIn('Fondo sanitario a 146 miliardi (ilsole24ore.com', text)
        self.assertEqual(text.count('cosa cambia per la sanità'), 1)  # stesso titolo da due fonti: una volta sola
        self.assertIn('Verifiche dei fact-checker:\n- La Svezia non ha abbandonato i vaccini a mRNA (Open)', text)
        self.assertLessEqual(len(text), 1800)

    def test_news_hosts_allowed_and_failures_skipped(self):
        for url in ('https://news.google.com/rss/search?q=x', 'https://api.gdeltproject.org/api/v2/doc/doc?query=x'):
            self.assertIn(kn.urllib.parse.urlsplit(url).hostname, kn.ALLOWED)
        self.assertIn('Nessuna notizia', kn.news('x', get=lambda u: (_ for _ in ()).throw(OSError())))

    def test_shared_dataset_is_valid_and_sampled(self):
        data = json.loads((Path(ab.__file__).parent / 'dati' / 'sfida-001.json').read_text())
        self.assertGreaterEqual(len(data['voci']), 20)
        for v in data['voci']:
            self.assertIn(v['riferimento'], data['etichette'])
            self.assertTrue(v['affermazione'] and v['fonte'] and v['url'].startswith('https://'))
        text = kn.challenge(data, random.Random(3))
        self.assertIn('Classificale tu', text)
        self.assertNotIn('https://', text)  # i link restano nel file, non nel prompt
        self.assertLessEqual(len(text), 1800)
        self.assertEqual(kn.challenge({}, random.Random(3)), '')

    def test_free_turn_uses_the_right_tool(self):
        plan = {'room': 'libera', 'intent': [], 'write': [{'role': 'user', 'content': kn.KNOW}], 'skills': [], 'reflection_if_written': [],
                'dataset': 'SET CONDIVISO #1'}
        for intent, expect, query in (('NOTIZIE: sfida', 'SET CONDIVISO', 'NOTIZIE: sfida'), ('NOTIZIE:', 'SET CONDIVISO', 'NOTIZIE: sfida'),
                                      ('NOTIZIE: sanità', 'NEWS sanità', 'NOTIZIE: sanità'), ('CERCA: crittografia', 'WEB crittografia', 'crittografia'),
                                      ('NO', 'Non hai cercato', '')):
            asked = []
            answers = iter([intent, 'testo', '', '', ''])
            r = kn.free_turn(plan, lambda m, **k: asked.append(m) or next(answers),
                             search=lambda q: 'WEB ' + q, news=lambda q: 'NEWS ' + q)
            self.assertIn(expect, asked[1][0]['content'], intent)
            self.assertEqual(r['query'], query)

    def test_prompt_offers_the_tools(self):
        bot = {'name': 'lume', 'rooms': ['generale'], 'persona': 'Sei lume.', 'model': {'label': 't'}}
        cfg = {'free_room_open': True, 'free_chance': 1.0, 'max_posts_per_day': 6, 'bots': [bot]}
        plan = ab.plan_turn(bot, cfg, [], '', 1_800_000_000, random.Random(0))
        self.assertIn('NOTIZIE: sfida', plan['intent'][1]['content'])
        self.assertIn('Classificale tu', plan['dataset'])


if __name__ == '__main__':
    unittest.main()
