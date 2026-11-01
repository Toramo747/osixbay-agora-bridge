import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'bots'))
import staffetta as st  # noqa: E402

NOW = 1_000_000


def run(i, ago, status='completed', started_ago=None):
    return {'id': i, 'status': status, 'created': NOW - ago,
            'started': NOW - (ago if started_ago is None else started_ago)}


class Staffetta(unittest.TestCase):
    def test_waits_for_the_minimum_gap_then_relays(self):
        d = st.decide(NOW, 1, [run(1, 5 * 60, 'in_progress')], [run(9, 3600)])
        self.assertTrue(d['bots'])
        self.assertEqual(d['wait'], 15 * 60)
        self.assertFalse(d['kaggle'])  # Kaggle ha girato un'ora fa

    def test_long_turn_relays_at_once(self):
        self.assertEqual(st.decide(NOW, 1, [run(1, 40 * 60, 'in_progress')], [])['wait'], 0)

    def test_no_duplicate_when_another_run_is_queued(self):
        d = st.decide(NOW, 1, [run(1, 600, 'in_progress'), run(2, 60, 'queued')], [])
        self.assertFalse(d['bots'])
        self.assertIn('coda', d['why'])

    def test_daily_cap_stops_the_chain(self):
        runs = [run(1, 60, 'in_progress')] + [run(i, i * 600) for i in range(2, 90)]
        d = st.decide(NOW, 1, runs, [], max_day=80)
        self.assertFalse(d['bots'])
        self.assertIn('tetto', d['why'])

    def test_kaggle_every_three_hours_never_twice(self):
        self.assertTrue(st.decide(NOW, 1, [run(1, 60, 'in_progress')], [run(9, 3 * 3600 + 1)])['kaggle'])
        self.assertFalse(st.decide(NOW, 1, [run(1, 60, 'in_progress')], [run(9, 4 * 3600), run(8, 60, 'queued')])['kaggle'])

    def test_settings_are_clamped(self):
        self.assertEqual(st.clamp('5', 15, 180, 20), 15)
        self.assertEqual(st.clamp('abc', 15, 180, 20), 20)
        self.assertEqual(st.clamp(None, 1, 96, 80), 80)

    def test_github_time_format(self):
        self.assertEqual(st.ts('2026-11-01T13:39:19Z'), 1793540359)


if __name__ == '__main__':
    unittest.main()
