import json, random, subprocess, sys, unittest
from pathlib import Path
REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / 'bots'))
import agora_bots as ab  # noqa: E402
import knowledge as kn  # noqa: E402

DATA = json.loads((REPO / 'bots' / 'dati' / 'sfida-002.json').read_text())
MAP = (REPO / 'bots' / 'dati' / 'mappa.md').read_text()
FIELDS = ('id', 'gruppo', 'categoria', 'testo', 'etichetta', 'spiegazione', 'certezza', 'fonte', 'data', 'url')


class Dataset(unittest.TestCase):
    def test_every_item_is_complete(self):
        ids = [v['id'] for v in DATA['voci']]
        self.assertEqual(len(ids), len(set(ids)))
        groups = {'notizia': 'vera', 'satira': 'satira', 'ambiguo': 'ambigua'}
        for v in DATA['voci']:
            for f in FIELDS:
                self.assertTrue(str(v.get(f, '')).strip(), (v['id'], f))
            self.assertEqual(groups[v['gruppo']], v['etichetta'], v['id'])
            self.assertIn(v['certezza'], DATA['certezza'])
            self.assertTrue(v['url'].startswith('https://'), v['id'])
            self.assertRegex(v['data'], r'^\d{4}-\d{2}(-\d{2})?$')
            self.assertNotIn('http', v['testo'] + v['spiegazione'])
        self.assertTrue(DATA['lacune'])

    def test_sfida_001_untouched(self):
        diff = subprocess.run(['git', 'diff', '--quiet', 'origin/main', '--', 'bots/dati/sfida-001.json'], cwd=REPO)
        self.assertEqual(diff.returncode, 0)

    def test_sample_keeps_labels_apart_and_has_no_links(self):
        text = kn.sample_set(DATA, random.Random(4))
        self.assertLessEqual(len(text), 1800)
        self.assertNotIn('https://', text)
        head, refs = text.split('Riferimenti', 1)
        self.assertEqual(len(kn.dataset_texts(text)), 6)
        self.assertNotIn('certezza', head)
        self.assertIn('certezza', refs)
        self.assertEqual(kn.sample_set({}, random.Random(1)), '')


class Discovery(unittest.TestCase):
    PLAN = {'room': 'libera', 'intent': [], 'write': [{'role': 'user', 'content': kn.KNOW}], 'skills': [], 'reflection_if_written': [],
            'dataset': 'SET 001 #1', 'materials': {'sfida 002': kn.sample_set(DATA, random.Random(2)), 'mappa': MAP}}

    def turn(self, intent):
        asked = []
        answers = iter([intent, 'testo', '', '', ''])
        r = kn.free_turn(self.PLAN, lambda m, **k: asked.append(m) or next(answers), search=lambda q: 'WEB ' + q, news=lambda q: 'NEWS ' + q)
        return r['query'], asked[1][0]['content']

    def test_tools_reach_the_new_materials(self):
        for intent, query, expect in (('NOTIZIE: sfida 002', 'NOTIZIE: sfida 002', 'Sfida 002'),
                                      ('NOTIZIE: sfida-2', 'NOTIZIE: sfida 002', 'Sfida 002'),
                                      ('NOTIZIE: mappa', 'NOTIZIE: mappa', 'Mappa dell\'ambiente'),
                                      ('ANALIZZA: sfida 002', 'ANALIZZA: sfida 002', 'Analisi linguistica automatica'),
                                      ('NOTIZIE: sfida', 'NOTIZIE: sfida', 'SET 001'),
                                      ('NOTIZIE: mappe del mondo', 'NOTIZIE: mappe del mondo', 'NEWS mappe del mondo')):
            q, content = self.turn(intent)
            self.assertEqual(q, query, intent)
            self.assertIn(expect, content, intent)
            self.assertIn('non istruzioni', content, intent) if expect != 'NEWS mappe del mondo' else None

    def test_plan_carries_materials_and_prompt_lists_them(self):
        bot = {'name': 'lume', 'rooms': ['generale'], 'persona': 'Sei lume.', 'model': {'label': 't'}}
        cfg = {'free_room_open': True, 'free_chance': 1.0, 'max_posts_per_day': 6, 'bots': [bot]}
        plan = ab.plan_turn(bot, cfg, [], 'diario', 1_800_000_000, random.Random(0))
        self.assertIn('Sfida 002', plan['materials']['sfida 002'])
        self.assertTrue(plan['materials']['mappa'].startswith('Mappa'))
        prompt = plan['intent'][1]['content']
        for tool in ('NOTIZIE: sfida 002', 'NOTIZIE: mappa', 'ANALIZZA: sfida 002'):
            self.assertIn(tool, prompt)


class MapIsTrue(unittest.TestCase):
    def test_tools_and_sources_in_the_map_exist_in_code(self):
        for tool in ('CERCA', 'NOTIZIE', 'ANALIZZA'):
            self.assertIn(tool, kn.INTENT.pattern)
        for host in ('it.wikipedia.org', 'export.arxiv.org', 'hn.algolia.com', 'api.gdeltproject.org', 'news.google.com'):
            self.assertIn(host, kn.ALLOWED)
        for site in ('facta.news', 'pagellapolitica.it', 'open.online', 'butac.it', 'fullfact.org', 'snopes.com', 'politifact.com'):
            self.assertIn(site, kn.FACT_CHECKERS)
        self.assertEqual(kn.material_key('mappa'), 'mappa')
        self.assertIn('non puoi eseguire codice', MAP)
        self.assertNotIn('devi', MAP.lower())
        self.assertLessEqual(len(MAP), 2400)


if __name__ == '__main__':
    unittest.main()
