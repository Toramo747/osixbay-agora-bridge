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


class KaggleGuard(unittest.TestCase):
    def k(self, i, ago_h, minutes, status='completed'):
        start = NOW - int(ago_h * 3600)
        return {'id': i, 'status': status, 'created': start, 'started': start, 'updated': start + minutes * 60}

    def test_hourly_within_budget(self):
        g = st.kaggle_guard(NOW, 1, [self.k(2, 1.0, 10), self.k(3, 2.0, 10)])
        self.assertTrue(g['go'])
        self.assertEqual(g['gap_h'], 1)

    def test_too_soon_is_skipped(self):
        self.assertFalse(st.kaggle_guard(NOW, 1, [self.k(2, 0.5, 10)])['go'])

    def test_skipped_runs_do_not_count(self):
        # run saltati (30 s) non sono un «ultimo giro» né consumo
        g = st.kaggle_guard(NOW, 1, [self.k(2, 0.2, 0.5), self.k(3, 1.5, 10)])
        self.assertTrue(g['go'])
        self.assertLess(g['used_h'], 0.2)

    def test_over_budget_falls_back_to_three_hours(self):
        heavy = [self.k(10 + i, 2 + i, 60) for i in range(26)]           # 26 h negli ultimi 7 giorni
        self.assertFalse(st.kaggle_guard(NOW, 1, heavy)['go'])          # ultimo giro 2 h fa < 3 h
        later = [self.k(10 + i, 3.5 + i, 60) for i in range(26)]
        g = st.kaggle_guard(NOW, 1, later)
        self.assertTrue(g['go'])
        self.assertEqual(g['gap_h'], 3)

    def test_hard_cap_stops(self):
        runs = [self.k(10 + i, 4 + i, 60) for i in range(29)]
        g = st.kaggle_guard(NOW, 1, runs)
        self.assertFalse(g['go'])
        self.assertIn('tetto rigido', g['why'])

    def test_old_runs_leave_the_window(self):
        runs = [self.k(10 + i, 24 * 7 + 1 + i, 60) for i in range(40)]
        self.assertEqual(st.kaggle_guard(NOW, 1, runs)['used_h'], 0)

    def test_active_run_blocks(self):
        self.assertFalse(st.kaggle_guard(NOW, 1, [self.k(2, 0.1, 0, 'in_progress'), self.k(3, 3, 10)])['go'])


if __name__ == '__main__':
    unittest.main()
