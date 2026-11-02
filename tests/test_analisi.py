import json, random, sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'bots'))
import agora_bots as ab  # noqa: E402
import knowledge as kn  # noqa: E402

SATIRA = 'INCREDIBILE! Il governo abolisce il lunedì: tutti felicissimi, nessuno andrà mai più al lavoro!!'
NOTIZIA = 'Secondo i dati Istat, nel 2025 la disoccupazione è scesa al 6,1%. Il rapporto sembra confermare la tendenza.'


class Analyze(unittest.TestCase):
    def test_counts_signals_without_judging(self):
        a, b = kn.analyze(SATIRA), kn.analyze(NOTIZIA)
        self.assertEqual(a['punti esclamativi'], 3)
        self.assertGreaterEqual(a['parole tutte maiuscole'], 1)
        self.assertGreaterEqual(a['intensificatori e assoluti'], 3)
        self.assertEqual(a['attribuzioni a una fonte'], 0)
        self.assertGreaterEqual(b['numeri e percentuali'], 2)
        self.assertGreaterEqual(b['attribuzioni a una fonte'], 3)
        self.assertGreaterEqual(b['cautele (forse, sembra, potrebbe…)'], 1)
        self.assertEqual(kn.analyze(''), {})
        report = kn.linguistic_report([('A', SATIRA)])
        self.assertIn('non dice se un testo è vero, falso o satira', report)
        self.assertLessEqual(len(kn.linguistic_report([('x', 'parola ' * 3000)] * 20)), 1800)

    def test_dataset_lines_are_read(self):
        data = json.loads((Path(__file__).resolve().parents[1] / 'bots' / 'dati' / 'sfida-001.json').read_text())
        sample = kn.challenge(data, random.Random(1))
        texts = kn.dataset_texts(sample)
        self.assertEqual(len(texts), 6)
        self.assertTrue(all(label.startswith('#') for label, _ in texts))

    def test_free_turn_analyze(self):
        plan = {'room': 'libera', 'intent': [], 'write': [{'role': 'user', 'content': kn.KNOW}], 'skills': [], 'reflection_if_written': [],
                'dataset': 'Set (20 affermazioni)\n#3 [salute] Il caffè allunga la vita del 50%!\nRiferimenti (ANSA):\n#3: x — y'}
        for intent, expect, query in (('ANALIZZA: sfida', 'Analisi linguistica automatica', 'ANALIZZA: sfida'),
                                      ('ANALIZZA: ' + SATIRA, 'punti esclamativi 3', 'ANALIZZA: ' + SATIRA[:80]),
                                      ('ANALIZZA: corto', 'Non hai cercato', '')):
            asked = []
            answers = iter([intent, 'testo', '', '', ''])
            r = kn.free_turn(plan, lambda m, **k: asked.append(m) or next(answers), search=lambda q: 'WEB', news=lambda q: 'NEWS')
            self.assertIn(expect, asked[1][0]['content'], intent)
            self.assertEqual(r['query'], query)
        self.assertNotIn('Riferimenti', kn.linguistic_report(kn.dataset_texts(plan['dataset'])))

    def test_search_queries_keep_their_old_length(self):
        plan = {'room': 'libera', 'intent': [], 'write': [{'role': 'user', 'content': kn.KNOW}], 'skills': [], 'reflection_if_written': []}
        seen = []
        answers = iter(['CERCA: ' + 'a' * 500, 'testo', '', '', ''])
        kn.free_turn(plan, lambda m, **k: next(answers), search=lambda q: seen.append(q) or 'WEB', news=lambda q: 'NEWS')
        self.assertEqual(len(seen[0]), 120)

    def test_prompt_offers_analyze(self):
        bot = {'name': 'architetto', 'rooms': ['generale'], 'persona': 'Sei architetto.', 'model': {'label': 't'}}
        cfg = {'free_room_open': True, 'free_chance': 1.0, 'max_posts_per_day': 6, 'bots': [bot]}
        plan = ab.plan_turn(bot, cfg, [], 'diario', 1_800_000_000, random.Random(0))
        self.assertIn('ANALIZZA: sfida', plan['intent'][1]['content'])


if __name__ == '__main__':
    unittest.main()
