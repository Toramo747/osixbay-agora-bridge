"""Test dell'opzione --habitat di integrazione/applica_patch.py.

python3 -m unittest discover -s genesis/fauna01/adapter/tests -p "test_*.py" -v
Serve `node`. Il test end-to-end sulla patch gira solo con GENESIS_WORKER_SRC=<cartella con i 7 src/*.js del Worker>.
"""
import copy, json, os, pathlib, subprocess, sys, tempfile, unittest

QUI = pathlib.Path(__file__).resolve().parent
ADAPTER = QUI.parent
sys.path.insert(0, str(ADAPTER / 'integrazione'))
import applica_patch as ap  # noqa: E402

FIXTURE = json.loads((ADAPTER / 'fixtures/habitat_sintetico_v1.json').read_text(encoding='utf-8'))
_HASH_JS = r"""
import { pathToFileURL } from 'node:url';
const { hashHabitat } = await import(pathToFileURL(process.argv[1]).href);
let t = ''; for await (const c of process.stdin) t += c;
console.log(hashHabitat(JSON.parse(t)));
"""


def rehash(h):
    r = subprocess.run(['node', '--input-type=module', '-e', _HASH_JS, str(ADAPTER / 'habitat.mjs')],
                       input=json.dumps(h), capture_output=True, text=True, check=True)
    h['sha256'] = r.stdout.strip()
    return h


def come_export_reale(h):
    """Stessa griglia della fixture, dichiarata come export Godot: serve solo a provare il percorso 'reale'."""
    h = copy.deepcopy(h)
    h['synthetic'] = False
    h['source'] = {'kind': 'godot_export', 'scene': 'res://prova.tscn', 'commit': 'test', 'exported_at': '2026-11-10T00:00:00Z',
                   'exporter': 'test_applica_patch.py'}
    return rehash(h)


class TestOpzioneHabitat(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = pathlib.Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def scrivi(self, nome, h):
        p = self.dir / nome
        p.write_text(json.dumps(h), encoding='utf-8')
        return p

    def test_export_reale_valido_accettato(self):
        testo, info = ap.convalida_habitat_reale(self.scrivi('reale.json', come_export_reale(FIXTURE)))
        self.assertEqual(json.loads(testo)['source']['kind'], 'godot_export')
        self.assertRegex(info['sha256'], r'^[0-9a-f]{64}$')
        self.assertGreater(info['suitable_cells'], 0)

    def test_fixture_sintetica_rifiutata(self):
        with self.assertRaisesRegex(ap.HabitatRifiutato, 'fixture sintetica rifiutata'):
            ap.convalida_habitat_reale(self.scrivi('sint.json', FIXTURE))

    def test_campi_mancanti_rifiutati(self):
        # come l'export S03 di oggi: niente cibo e niente species.F01
        h = come_export_reale(FIXTURE)
        for k in ['food_capacity', 'food_initial', 'food_regrowth']:
            del h['layers'][k]
        del h['species']
        with self.assertRaisesRegex(ap.HabitatRifiutato, 'food_capacity'):
            ap.convalida_habitat_reale(self.scrivi('incompleto.json', rehash(h)))

    def test_hash_manomesso_rifiutato(self):
        h = come_export_reale(FIXTURE)
        h['layers']['playable'][0] = ('1' if h['layers']['playable'][0][0] == '0' else '0') + h['layers']['playable'][0][1:]
        with self.assertRaisesRegex(ap.HabitatRifiutato, 'sha256 non corrisponde'):
            ap.convalida_habitat_reale(self.scrivi('manomesso.json', h))

    def test_file_non_json_rifiutato(self):
        p = self.dir / 'rotto.json'
        p.write_text('{non json', encoding='utf-8')
        with self.assertRaisesRegex(ap.HabitatRifiutato, 'non e\' JSON valido'):
            ap.convalida_habitat_reale(p)

    def test_rifiuto_non_scrive_nulla(self):
        src = self.dir / 'src'; src.mkdir()
        uscita = self.dir / 'uscita'
        with self.assertRaises(ap.HabitatRifiutato):
            ap.applica(src, uscita, self.scrivi('sint.json', FIXTURE))
        self.assertFalse(uscita.exists())

    def test_cli_rifiuto_codice_di_uscita(self):
        src = self.dir / 'src'; src.mkdir()
        r = subprocess.run([sys.executable, str(ADAPTER / 'integrazione/applica_patch.py'), str(src), str(self.dir / 'u'),
                            '--habitat', str(self.scrivi('sint.json', FIXTURE))], capture_output=True, text=True)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn('patch NON applicata', r.stderr)
        self.assertFalse((self.dir / 'u').exists())


@unittest.skipUnless(os.environ.get('GENESIS_WORKER_SRC'), 'serve GENESIS_WORKER_SRC con il sorgente del Worker')
class TestPatchCompleta(unittest.TestCase):
    def test_habitat_reale_incorporato_e_fixture_predefinita(self):
        src = pathlib.Path(os.environ['GENESIS_WORKER_SRC'])
        with tempfile.TemporaryDirectory() as t:
            t = pathlib.Path(t)
            reale = come_export_reale(FIXTURE)
            p = t / 'reale.json'; p.write_text(json.dumps(reale), encoding='utf-8')
            info = ap.applica(src, t / 'con_habitat', p)
            self.assertEqual(info['sha256'], reale['sha256'])
            dati = (t / 'con_habitat/fauna/habitat_dati.mjs').read_text(encoding='utf-8')
            self.assertTrue(dati.startswith('export default {'))
            self.assertEqual(json.loads(dati[len('export default '):].rstrip().rstrip(';')), reale)
            ap.applica(src, t / 'predefinito')
            pred = (t / 'predefinito/fauna/habitat_dati.mjs').read_text(encoding='utf-8')
            self.assertTrue(json.loads(pred[len('export default '):].rstrip().rstrip(';'))['synthetic'])
            for f in ['mondo.js', 'index.js']:
                self.assertEqual((t / 'con_habitat' / f).read_text(), (t / 'predefinito' / f).read_text())


if __name__ == '__main__':
    unittest.main()
