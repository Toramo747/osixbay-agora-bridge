"""Test della gratificazione formativa: non premiare parole, post o prove inventate."""
import json
import random
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'bots'))
import quaderno as qd
import riconoscimenti as rc
import agora_bots as ab

NOW = 1800000000


class RiconoscimentiTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.tick = 0

    def tearDown(self):
        self.tmp.cleanup()

    def tool(self, name, sha):
        folder = self.root / 'registro' / '2027-01-15'
        folder.mkdir(parents=True, exist_ok=True)
        with (folder / (name + '.jsonl')).open('a', encoding='utf-8') as f:
            f.write(json.dumps({'t': '2027-01-15 10:00 UTC', 'strumento': 'ANALIZZA: sfida 002',
                                'uscita_strumento': {'sha': sha, 'car': 140}}) + '\n')

    def event(self, who, event='nuova', kind='ipotesi', text='evidenza', ref=None,
              proof=None, links=None, esito=None):
        self.tick += 60
        command = {'evento': event, 'tipo': kind, 'testo': text, 'prove': list(proof or []),
                   'collegamenti': list(links or [])}
        if ref:
            command['riferimento'] = ref
        if esito:
            command['esito'] = esito
        qid, outcome = qd.save(who, command, NOW + self.tick, self.root)
        self.assertEqual(outcome, 'salvato')
        return qid

    def test_no_reward_for_posts_ideas_or_unverified_numbers(self):
        self.event('lume', kind='ipotesi', text='BERT avra 95 percento di accuratezza')
        self.event('lume', kind='esperimento_proposto', text='potremmo misurare')
        self.event('lume', kind='risultato', text='ho ottenuto 100 percento senza dati')
        self.assertEqual(rc.quadro(self.root), {})
        self.assertIn('nessuna competenza ancora documentata', rc.feedback('lume', self.root))

    def test_valid_experiment_one_reward_per_real_output(self):
        self.tool('lume', 'aaaaaaaaaaaa')
        self.event('lume', kind='esperimento_eseguito', text='primo test con prova',
                   proof=['aaaaaaaaaaaa'])
        self.event('lume', kind='esperimento_eseguito', text='seconda dichiarazione con stessa prova',
                   proof=['aaaaaaaaaaaa'])
        res = rc.quadro(self.root)['lume']
        self.assertEqual((res['esperimenti_documentati'], res['punti']), (1, 3))
        self.assertIn('3 punti formativi', rc.feedback('lume', self.root))

    def test_forged_proof_flag_without_real_ledger_does_not_count(self):
        self.event('lume', kind='esperimento_eseguito', text='invento una prova',
                   proof=['ffffffffffff'])
        path = self.root / 'quaderno' / 'lume.jsonl'
        lines = [json.loads(s) for s in path.read_text().splitlines()]
        lines[0]['prove'][0]['valida'] = True  # simula una riga manipolata nel repository
        path.write_text(json.dumps(lines[0]) + '\n')
        self.assertEqual(rc.quadro(self.root), {})

    def test_independent_verification_and_later_disagreement(self):
        self.tool('lume', 'aaaaaaaaaaaa')
        self.tool('fermo', 'bbbbbbbbbbbb')
        self.tool('vaglio', 'cccccccccccc')
        ref = self.event('lume', kind='risultato', text='conteggio con tabella',
                         proof=['aaaaaaaaaaaa'])
        self.event('lume', event='verifica', text='sono d accordo con me', ref=ref,
                   esito='conferma', proof=['aaaaaaaaaaaa'])
        self.event('vaglio', event='verifica', text='conferma senza prova', ref=ref,
                   esito='conferma')
        self.assertEqual(rc.quadro(self.root), {})
        self.event('fermo', event='verifica', text='replica con tabella', ref=ref,
                   esito='conferma', proof=['bbbbbbbbbbbb'])
        a = rc.quadro(self.root)
        self.assertEqual((a['lume']['risultati_confermati'], a['lume']['punti']), (1, 3))
        self.assertEqual((a['fermo']['verifiche_indipendenti'], a['fermo']['punti']), (1, 2))
        self.event('vaglio', event='contesta', text='replica differente con dati', ref=ref,
                   proof=['cccccccccccc'])
        a = rc.quadro(self.root)
        self.assertNotIn('lume', a)   # un risultato contestato non rimane premiato come confermato
        self.assertEqual((a['vaglio']['correzioni_documentate'], a['vaglio']['punti']), (1, 2))

    def test_correction_with_new_evidence_counts_once(self):
        self.tool('lume', 'aaaaaaaaaaaa')
        self.tool('lume', 'bbbbbbbbbbbb')
        ref = self.event('lume', kind='ipotesi', text='ipotesi iniziale')
        self.event('lume', event='correggi', text='revisione documentata', ref=ref,
                   proof=['bbbbbbbbbbbb'])
        self.assertEqual(rc.quadro(self.root)['lume']['correzioni_documentate'], 1)
        self.event('lume', event='correggi', text='ripeto lo stesso controllo', ref=ref,
                   proof=['bbbbbbbbbbbb'])
        self.assertEqual(rc.quadro(self.root)['lume']['punti'], 2)

    def test_reuse_of_another_verified_result_has_real_new_proof(self):
        for name, sha in [('lume', 'aaaaaaaaaaaa'), ('fermo', 'bbbbbbbbbbbb'),
                          ('trama', 'cccccccccccc')]:
            self.tool(name, sha)
        ref = self.event('lume', kind='risultato', text='risultato base',
                         proof=['aaaaaaaaaaaa'])
        self.event('fermo', event='verifica', text='verificato', ref=ref,
                   proof=['bbbbbbbbbbbb'], esito='conferma')
        self.event('trama', kind='risultato', text='riuso in una nuova misurazione',
                   links=[ref], proof=['cccccccccccc'])
        a = rc.quadro(self.root)
        self.assertEqual((a['trama']['riusi_documentati'], a['trama']['punti']), (1, 3))

    def test_feedback_enters_normal_free_and_reflection_prompts_only_for_owner(self):
        self.tool('lume', 'aaaaaaaaaaaa')
        self.event('lume', kind='esperimento_eseguito', text='ho contato segnali',
                   proof=['aaaaaaaaaaaa'])
        lume = {'name': 'lume', 'persona': 'Curioso.', 'model': {'label': 'test'}}
        seme = {'name': 'seme', 'persona': 'Educatrice.', 'model': {'label': 'test'}}
        post = {'id': 'p1', 'author': 'fermo', 'room': 'generale',
                'reply_to': None, 'text': 'Quale risultato?'}
        cfg = {'free_room_open': True, 'free_chance': 1.0, 'max_posts_per_day': 6,
               'bots': [lume, seme], 'private_rooms_accessible': []}
        with mock.patch.object(ab, 'ROOT', self.root):
            normal = ab.messages_for(lume, '', 'reply', post, [post])
            reflective = ab.reflection_messages(lume, '', '')
            free = ab.plan_free(lume, cfg, [], '', '', NOW, rng=random.Random(0))
            other = ab.messages_for(seme, '', 'reply', post, [post])
        for messages in (normal, reflective, free['write']):
            self.assertIn('3 punti formativi', messages[0]['content'])
        self.assertIn('nessuna competenza ancora documentata', other[0]['content'])
        self.assertNotIn('3 punti formativi', other[0]['content'])
        self.assertIn('SEME-MONTESSORI-LAB-01', other[0]['content'])


if __name__ == '__main__':
    unittest.main()
