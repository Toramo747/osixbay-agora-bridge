"""Residenti senza tetto giornaliero (decisione di Andrea, 2/11/2026): client, codice del server e monitor."""
import json, re, shutil, subprocess, sys, tempfile, unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'bots'))
sys.path.insert(0, str(ROOT / 'scripts'))
import agora_bots as ab  # noqa: E402
import staffetta_monitor as sm  # noqa: E402

NOW = 1_800_000_000
CORE = (ROOT / 'agora' / 'core.mjs').read_text()
CFG = json.loads((ROOT / 'bots' / 'bots.json').read_text())


def post(i, author='lume', ago=60):
    return {'id': f'p{i}', 'author': author, 'room': 'generale', 'text': 'x', 'created_at': NOW - ago, 'reply_to': None}


class Client(unittest.TestCase):
    def test_config_has_no_daily_cap(self):
        self.assertIn('max_posts_per_day', CFG)
        self.assertIsNone(CFG['max_posts_per_day'])
        self.assertEqual(CFG['max_replies_per_thread_per_day'], 2)   # invariato

    def test_null_cap_never_stops(self):
        self.assertFalse(ab.over_daily_cap({'max_posts_per_day': None}, [post(i) for i in range(500)]))

    def test_numeric_cap_still_works(self):
        self.assertTrue(ab.over_daily_cap({'max_posts_per_day': 6}, [post(i) for i in range(6)]))
        self.assertFalse(ab.over_daily_cap({'max_posts_per_day': 6}, [post(i) for i in range(5)]))
        self.assertTrue(ab.over_daily_cap({}, [post(i) for i in range(6)]))   # default storico: 6

    def test_decide_does_not_idle_for_quota_without_cap(self):
        cfg = {'max_posts_per_day': None, 'max_replies_per_thread_per_day': 2, 'new_post_chance': 0.0, 'rooms_for_bot': ['generale']}
        posts = [post(i, ago=60 + i) for i in range(80)]
        self.assertNotEqual(ab.decide('lume', posts, cfg, NOW), ('idle', 'quota giornaliera raggiunta'))


class ServerCode(unittest.TestCase):
    def test_resident_list_matches_bots_json(self):
        m = re.search(r'RESIDENTS = new Set\(\[([^\]]*)\]\)', CORE)
        self.assertIsNotNone(m)
        self.assertEqual(set(re.findall(r"'([a-z0-9-]+)'", m.group(1))), {b['name'] for b in CFG['bots']})

    def test_reserved_names_are_not_exempt(self):
        names = set(re.findall(r"'([a-z0-9-]+)'", re.search(r'RESIDENTS = new Set\(\[([^\]]*)\]\)', CORE).group(1)))
        self.assertFalse(names & {'neo', 'claude', 'andrea', 'admin', 'osixbay'})

    @unittest.skipUnless(shutil.which('node'), 'node non disponibile')
    def test_limits_behaviour(self):
        script = """
import { limits } from '%s';
const now = 1800000000, day = Math.floor(now / 86400) * 86400;
const many = n => Array.from({length: n}, (_, i) => day + i * 60);
console.log(JSON.stringify({
  resident200: limits('lume', many(200), now),
  residentRecent: limits('lume', [now - 10], now),
  external40: limits('ospite', many(40), now),
  external39: limits('ospite', many(39), now),
  neo60: limits('neo', many(60), now),
  neo59: limits('neo', many(59), now),
}));""" % (ROOT / 'agora' / 'core.mjs').as_uri()
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / 't.mjs'
            f.write_text(script)
            out = json.loads(subprocess.run(['node', str(f)], capture_output=True, text=True, check=True).stdout)
        self.assertIsNone(out['resident200'])
        self.assertEqual(out['residentRecent'], 'Attendi 30 secondi')
        self.assertEqual(out['external40'], 'Limite giornaliero raggiunto')
        self.assertIsNone(out['external39'])
        self.assertEqual(out['neo60'], 'Limite giornaliero raggiunto')
        self.assertIsNone(out['neo59'])


class Monitor(unittest.TestCase):
    def test_declared_limits_show_exempt_residents(self):
        lim = sm.declared_limits()
        self.assertEqual(lim['codice_server']['post_giorno'], 40)
        self.assertEqual(set(lim['codice_server']['senza_tetto']), {b['name'] for b in CFG['bots']})
        self.assertIsNone(lim['client_residenti']['post_giorno'])
        self.assertEqual(sm.limit_mismatches(lim), ['eccezione nel codice del server: neo fino a 60 post/giorno'])

    def test_mismatch_when_client_uncapped_but_server_not_exempting(self):
        lim = {'codice_server': {'post_giorno': 40, 'eccezioni': {}, 'senza_tetto': []},
               'client_residenti': {'post_giorno': None}, 'documentazione': None}
        self.assertTrue(any('non li esenta' in m for m in sm.limit_mismatches(lim)))


if __name__ == '__main__':
    unittest.main()
