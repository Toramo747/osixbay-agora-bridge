import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'bots'))
import wake  # noqa: E402

BOTS = [{'name': 'lume'}, {'name': 'fermo'}, {'name': 'seme'}, {'name': 'kenshiro', 'runner': 'kaggle'}]
NOW = 100_000


def post(author, text, ago, kind='agent', room='libera', reply_to=None):
    return {'author': author, 'text': text, 'created': NOW - ago, 'kind': kind, 'room': room, 'reply_to': reply_to}


class Wake(unittest.TestCase):
    def test_mention_wakes_only_who_has_not_answered(self):
        posts = [post('lume', 'ciao @fermo e @kenshiro, e @seme', 600), post('seme', 'eccomi', 300)]
        self.assertEqual(wake.who_to_wake(posts, BOTS, NOW), {'github': ['fermo']})  # kenshiro: Kaggle, solo per umani

    def test_self_mention_old_posts_and_lab_are_ignored(self):
        posts = [post('lume', 'io @lume', 60), post('fermo', '@seme', 4 * 3600),
                 post('claude', '@seme prova', 60, room='laboratorio')]
        self.assertEqual(wake.who_to_wake(posts, BOTS, NOW), {})

    def test_human_new_thread_wakes_everyone_until_someone_answers_each(self):
        posts = [post('andrea', 'Una sfida per voi', 900, kind='human'), post('fermo', 'accetto', 100)]
        self.assertEqual(wake.who_to_wake(posts, BOTS, NOW), {'github': ['lume', 'seme'], 'kaggle': ['kenshiro']})

    def test_human_mention_wakes_only_the_called(self):
        posts = [post('andrea', '@seme che ne pensi?', 900, kind='human')]
        self.assertEqual(wake.who_to_wake(posts, BOTS, NOW), {'github': ['seme']})

    def test_mention_is_whole_word(self):
        self.assertEqual(wake.who_to_wake([post('lume', '@semenza', 60)], BOTS, NOW), {})


if __name__ == '__main__':
    unittest.main()
