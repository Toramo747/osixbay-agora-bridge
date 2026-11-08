"""Regressioni: i giri ordinari Genesis non devono finire in chiaro nel repo pubblico."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'bots'))

import agora_bots as ab  # noqa: E402
import ambiente  # noqa: E402

MASTER = "bW1tbW1tbW1tbW1tbW1tbW1tbW1tbW1tbW1tbW1tbW0="  # 32 byte di test
NOW = 1_800_000_000
SECRET = "MARCATORE_FAUNA_PRIVATO_NON_PUBBLICARE"


class PrivateLogFailsafe(unittest.TestCase):
    def test_normal_reply_and_new_plans_receive_private_acl(self):
        for action in ('reply', 'new'):
            with self.subTest(action=action):
                synthetic = {'action': action, 'room': 'genesis',
                             'reply_to': 'thread', 'giro': 'normale',
                             'messages': [], 'options': {}}
                with mock.patch.object(ab, '_plan_turn', return_value=synthetic):
                    plan = ab.plan_turn({'name': 'lume'},
                                        {'private_rooms': ['genesis']}, [], '', NOW)
                self.assertIn('genesis', plan['stanze_private'])
                self.assertTrue(ab.is_private_turn(plan))

    def test_no_private_text_in_public_journal_even_without_acl_flag(self):
        for action in ('reply', 'new', 'free'):
            for runner in ('github', 'kaggle'):
                with self.subTest(action=action, runner=runner):
                    with tempfile.TemporaryDirectory() as d:
                        root = Path(d)
                        plan = {'action': action, 'giro': 'normale',
                                'room': 'genesis', 'reply_to': SECRET,
                                'runner': runner}
                        row = ambiente.journal(
                            'lume', plan, NOW, 'pubblicato',
                            {'text': SECRET, 'query': 'CERCA ' + SECRET,
                             'tool_output': SECRET, 'opened': SECRET},
                            SECRET, root)
                        self.assertNotIn('testo', row)
                        self.assertEqual(row['testo_omesso']['motivo'], 'stanza privata')
                        self.assertNotIn('estratto', row['uscita_strumento'])
                        self.assertIsNone(row['risposta_a'])
                        self.assertIsNone(row['post'])
                        self.assertNotIn('vincoli', row)
                        self.assertFalse(list(root.rglob('uscite')))
                        published = ''.join(p.read_text(encoding='utf-8')
                                            for p in root.rglob('*') if p.is_file())
                        self.assertNotIn(SECRET, published)

    def test_finish_turn_does_not_write_private_diary_or_files(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            folder = root / 'lume'
            folder.mkdir()
            with mock.patch.object(ab, 'ROOT', root), mock.patch.object(ambiente, 'ROOT', root):
                plan = {'action': 'reply', 'room': 'genesis', 'reply_to': 'thread',
                        'giro': 'normale', 'messages': [{'role': 'user', 'content': 'test'}]}
                sent = []
                result = ab.finish_turn(
                    {'name': 'lume'}, plan, SECRET + ' vita aliena',
                    SECRET + ' diario', MASTER, lambda p: sent.append(p) or {'id': 'ok'},
                    NOW, folder, raw_wish='DESIDERIO: ' + SECRET,
                    raw_skills='Competenza ' + SECRET,
                    raw_place='Luogo ' + SECRET,
                    extra={'query': 'ANALIZZA: ' + SECRET, 'tool_output': SECRET})
                self.assertTrue(result['privato'])
                self.assertEqual(sent[0]['room'], 'genesis')
                published = ''.join(p.read_text(encoding='utf-8')
                                    for p in root.rglob('*') if p.is_file())
                self.assertNotIn(SECRET, published)
                self.assertFalse((folder / 'memory.md').exists())
                self.assertFalse((root / 'luoghi' / 'genesis.md').exists())

    def test_dynamic_private_room_and_public_room_are_distinguished(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / 'bots.json').write_text(json.dumps({'private_rooms': ['stanza-riservata']}))
            self.assertTrue(ambiente.is_private_room({'room': 'stanza-riservata'}, root))
            self.assertTrue(ambiente.is_private_room({'room': 'biblioteca-genesis'}, root))
            self.assertFalse(ambiente.is_private_room({'room': 'generale'}, root))
            row = ambiente.journal('lume', {'room': 'generale', 'action': 'new'},
                                   NOW, 'pubblicato', {'text': 'messaggio pubblico'}, 'p', root)
            self.assertEqual(row['testo'], 'messaggio pubblico')


if __name__ == '__main__':
    unittest.main()
