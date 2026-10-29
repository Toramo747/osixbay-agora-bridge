import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'bots'))
import officina as o  # noqa: E402

NOW = 1_800_000_000


def p(i, author, kind='agent', reply_to=None, text='ok', age=100, room='arena'):
    return {'id': i, 'author': author, 'kind': kind, 'reply_to': reply_to, 'text': text, 'created': NOW - age, 'room': room}


class Harvest(unittest.TestCase):
    def test_scores_humans_above_agents_and_ignores_author(self):
        posts = [p('a', 'lume', text='Proposta di tool: Verificatore di citazioni. Controlla che una citazione esista.'),
                 p('b', 'fermo', text='**Proposta di tool:** Orologio di fiducia'),
                 p('a1', 'andrea', 'human', 'a'), p('a2', 'fermo', reply_to='a1'), p('a3', 'lume', reply_to='a2'),
                 p('b1', 'trama', reply_to='b'), p('b2', 'lume', reply_to='b')]
        ranked = o.harvest(posts, NOW)
        self.assertEqual([e['id'] for e in ranked], ['a', 'b'])
        self.assertEqual(ranked[0]['title'], 'Verificatore di citazioni')
        self.assertEqual((ranked[0]['humans'], ranked[0]['agents'], ranked[0]['score']), (1, 1, 4))
        self.assertEqual(ranked[0]['contributors'], ['andrea', 'fermo'])
        self.assertEqual(ranked[1]['title'], 'Orologio di fiducia')

    def test_old_lab_and_plain_posts_skipped(self):
        posts = [p('x', 'lume', text='Proposta di tool: vecchio', age=20 * 86400),
                 p('y', 'lume', text='Proposta di tool: segreto', room='laboratorio'), p('z', 'lume', text='ciao')]
        self.assertEqual(o.harvest(posts, NOW), [])

    def test_texts(self):
        self.assertIn('Proposta di tool:', o.announcement([]))
        self.assertIn('nessuna proposta', o.markdown([], NOW))
        ranked = o.harvest([p('a', 'lume', text='Proposta di tool: A|B')], NOW)
        self.assertIn('A/B', o.markdown(ranked, NOW))
        self.assertIn('1. A|B', o.announcement(ranked))


if __name__ == '__main__':
    unittest.main()
