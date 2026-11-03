"""Rilevatore di vincoli in modalità solo misura."""
import json, random, sys, unittest
from pathlib import Path
from unittest import mock
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from test_ambiente import NOW, Sandbox, contexts  # noqa: E402
from test_registro import Turns  # noqa: E402
import ambiente  # noqa: E402
import knowledge  # noqa: E402
import vincoli  # noqa: E402
import vincoli_report  # noqa: E402


class Detectors(unittest.TestCase):
    def test_imaginary_tools(self):
        self.assertEqual(vincoli.imaginary_tools('Possiamo usare AuthentiCheck e il Question Refinement Engine (QRE).'),
                         ['AuthentiCheck', 'Question Refinement Engine', 'QRE'])
        self.assertEqual(vincoli.imaginary_tools('Ho letto su PolitiFact e YouTube una verifica.'), [])
        self.assertEqual(vincoli.imaginary_tools('Uso lo strumento ANALIZZA e NOTIZIE: sfida.'), [])
        self.assertEqual(vincoli.imaginary_tools('Il sistema DataSentinel promette molto.'), ['DataSentinel'])
        self.assertEqual(vincoli.imaginary_tools('Ho parlato con MarioRossi ieri.'), [])   # CamelCase senza contesto da strumento

    def test_redundant_requests(self):
        r = vincoli.redundant_request('un dataset di notizie satiriche e vere ben etichettate')
        self.assertEqual(r, [{'chiede': 'dataset di notizie satiriche e vere', 'esiste_gia': 'NOTIZIE: sfida 002'}])
        self.assertEqual(vincoli.redundant_request('un approccio metodologico per creare un dataset di notizie satiriche'), [])
        self.assertEqual(vincoli.redundant_request('un gruppo di volontari umani'), [])
        self.assertEqual(vincoli.redundant_request('uno strumento di analisi linguistica del testo')[0]['esiste_gia'], 'ANALIZZA: <testo>')

    def test_redundant_only_if_resource_exists(self):
        with mock.patch.object(vincoli, '_exists', lambda root, stem: False):
            self.assertEqual(vincoli.redundant_request('un dataset di notizie satiriche e vere'), [])

    def test_command_misuse(self):
        self.assertEqual(vincoli.command_misuse('Sfida 001'), 'materiale condiviso cercato con CERCA invece di NOTIZIE')
        self.assertEqual(vincoli.command_misuse('<cosa>'), 'segnaposto copiato')
        self.assertEqual(vincoli.command_misuse('Wikipedia'), 'nome di fonte o comando usato come ricerca')
        self.assertEqual(vincoli.command_misuse('trama'), 'nome di residente usato come ricerca')
        for ok in ('negative sampling', 'NOTIZIE: sfida', 'OSSERVA: strumenti', '', None):
            self.assertIsNone(vincoli.command_misuse(ok))

    def test_copy_ratio(self):
        refs = '#3: falsa — Video e foto sono generati con l\'IA (filigrana SynthID); nessuna fonte conferma il recupero dei telefoni'
        self.assertGreaterEqual(vincoli.copy_ratio('Secondo me #3 è falsa: video e foto sono generati con l\'IA (filigrana SynthID); nessuna fonte conferma il recupero dei telefoni', refs), 0.5)
        self.assertEqual(vincoli.copy_ratio('Penso che la notizia tre sia inventata, non ho trovato conferme altrove.', refs), 0.0)


class InTheJournal(Turns):
    def test_violations_recorded_and_invisible_to_residents(self):
        text = 'Potremmo usare AuthentiCheck per verificare le notizie, cosa ne pensate?'
        plan, r = self.turn('lume', 'CERCA: Sfida 001', lambda p: {'id': 'v1'}, text=text)
        row = self.rows('lume')[-1]
        kinds = {v['tipo'] for v in row['vincoli']}
        self.assertEqual(kinds, {'strumento_inesistente', 'comando_errato'})
        nxt = self.plan('lume', rng=5)
        blob = json.dumps(nxt, ensure_ascii=False)
        for word in ('vincoli', 'strumento_inesistente', 'comando_errato', 'violazion'):
            self.assertNotIn(word, blob)
        self.assertNotIn('vincoli', json.dumps(ambiente.load_stato('lume')))

    def test_copy_detected_when_refs_were_shown(self):
        self.turn('fermo', 'NOTIZIE: sfida', lambda p: {'id': 'c1'})
        ids = ambiente.load_stato('fermo')['riferimenti_in_sospeso']['ids']
        d1 = json.loads((self.root / 'dati' / 'sfida-001.json').read_text())
        v = next(x for x in d1['voci'] if x['id'] == ids[0])
        copied = f"#{v['id']}: {v['riferimento']} — {v['perche']}"
        self.turn('fermo', 'NO', lambda p: {'id': 'c2'}, rng=9, text=copied)
        row = self.rows('fermo')[-1]
        self.assertEqual(row['riferimenti_visti'], 'sfida-001')
        self.assertIn('copia_riferimenti', {x['tipo'] for x in row['vincoli']})

    def test_detector_failure_never_stops_a_turn(self):
        with mock.patch.object(vincoli, 'check', side_effect=RuntimeError('boom')):
            self.turn('seme', 'NO', lambda p: {'id': 'e1'})
        row = self.rows('seme')[-1]
        self.assertEqual((row['vincoli_errore'], row['pubblicazione']), ('RuntimeError', 'pubblicato'))

    def test_report(self):
        self.turn('lume', 'CERCA: <cosa>', lambda p: {'id': 'r1'}, text='Useremo VeriCheck come strumento comune per tutti.')
        with mock.patch.object(vincoli_report, 'ROOT', self.root):
            rep = vincoli_report.build(self.root)
        day = rep['residenti']['lume']['giorni']['2026-11-02']
        self.assertEqual((day['violazioni']['strumento_inesistente'], day['violazioni']['comando_errato']), (1, 1))
        for claim in rep['residenti']['lume']['abilita_dichiarate'].values():
            self.assertEqual(claim['prova_prestazione'], 'NON VERIFICABILE')
        md = vincoli_report.markdown(rep)
        self.assertIn('| lume | 2026-11-02 |', md)


if __name__ == '__main__':
    unittest.main()
