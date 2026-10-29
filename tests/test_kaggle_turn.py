import contextlib
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import kaggle_turn as kt

BOT = {'name': 'kenshiro', 'model': {'hf': 'Qwen/Qwen3-8B'}}
RUN = 'current-invocation'
SHA = hashlib.sha256(b'current plan').hexdigest()


def draft(**changes):
    return dict(bot=BOT['name'], model=BOT['model']['hf'], run_id=RUN,
                plan_sha256=SHA, text='Current reply', diary='Current diary', **changes)


class KaggleTurn(unittest.TestCase):
    def run_sequence(self, statuses, outputs, polls=None):
        states, files = iter(statuses), iter(outputs)
        commands = []

        def command(*args):
            commands.append(args[0])
            if args[0] == 'status':
                return next(states)
            target = Path(args[args.index('-p') + 1]) / 'drafts.json'
            value = next(files)
            if value is not None:
                target.write_text(json.dumps(value) if not isinstance(value, str) else value)
            return ''

        result = kt.wait_for_drafts('user/agora-kenshiro', RUN, SHA, BOT,
                                    command=command, sleep=lambda _: None,
                                    polls=polls or len(statuses))
        return result, commands

    def test_previous_complete_does_not_publish_old_drafts(self):
        old = dict(draft(), run_id='previous-invocation')
        result, commands = self.run_sequence(
            ['complete', 'complete', 'running', 'complete'], [old, old, draft()])
        self.assertEqual(result['run_id'], RUN)
        self.assertEqual(commands.count('status'), 4)

    def test_already_complete_current_run_is_safe_without_observing_running(self):
        result, _ = self.run_sequence(['complete'], [draft()])
        self.assertEqual(result, draft())

    def test_only_previous_output_times_out(self):
        with self.assertRaisesRegex(kt.KaggleFailure, 'timeout_no_matching_drafts'):
            self.run_sequence(['complete'] * 5, [dict(draft(), run_id='old')] * 5)

    def test_nonterminal_timeout_never_downloads(self):
        calls = []
        def command(*args):
            calls.append(args[0])
            return 'running'
        with self.assertRaisesRegex(kt.KaggleFailure, 'timeout_no_matching_drafts'):
            kt.wait_for_drafts('u/k', RUN, SHA, BOT, command=command,
                               sleep=lambda _: None, polls=3)
        self.assertEqual(calls, ['status'] * 3)

    def test_wrong_plan_bot_model_and_malformed_data_are_rejected(self):
        for change in ({'plan_sha256': 'old'}, {'bot': 'doraimon'}, {'model': 'other'},
                       {'text': []}, {'diary': 'x' * 4001}):
            with self.subTest(change=next(iter(change))):
                self.assertFalse(kt.matches(dict(draft(), **change), RUN, SHA, BOT))
        self.assertFalse(kt.matches([], RUN, SHA, BOT))
        result, _ = self.run_sequence(['complete', 'complete', 'complete'], ['{', None, draft()])
        self.assertEqual(result, draft())

    def test_error_or_cancel_never_returns_output(self):
        for state in ('error', 'failed', 'cancelled', 'canceled'):
            with self.subTest(state=state), self.assertRaisesRegex(kt.KaggleFailure, 'run_failed'):
                self.run_sequence([state], [])

    def test_raw_cli_failure_is_not_in_exception_or_logs(self):
        # A synthetic marker verifies suppression without using any credential.
        marker = 'RAW_OUTPUT_MUST_STAY_PRIVATE'
        result = subprocess.CompletedProcess([], 1, marker, marker)
        output = io.StringIO()
        with patch.object(kt.subprocess, 'run', return_value=result), contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
            with self.assertRaisesRegex(kt.KaggleFailure, '^kaggle_push_failed$'):
                kt.cli('push', '-p', '/tmp/kernel')
        self.assertNotIn(marker, output.getvalue())

    def test_private_kernel_contains_only_plan_and_public_challenge(self):
        plan = json.dumps({'bot': BOT['name'], 'messages': []}).encode()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            ref, sha = kt.prepare_kernel(path, 'user', BOT, plan, RUN)
            self.assertEqual(ref, 'user/agora-kenshiro')
            self.assertEqual(sha, hashlib.sha256(plan).hexdigest())
            metadata = json.loads((path / 'kernel-metadata.json').read_text())
            self.assertTrue(metadata['is_private'])
            src = (path / 'agora_writer.py').read_text()
            self.assertIn(RUN, src)
            self.assertIn(sha, src)
            self.assertNotIn('KAGGLE_API_TOKEN', src)
            self.assertNotIn('CLAUDE_ED25519_PRIVATE_KEY', src)
            compile(src, 'agora_writer.py', 'exec')

    def test_failure_removes_existing_drafts_before_any_publish(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / 'drafts.json'
            target.write_text(json.dumps(draft()))
            with patch.object(sys, 'argv', ['kaggle_turn.py', 'unused', str(target)]), patch.dict(kt.os.environ, {'KAGGLE_USERNAME': ''}):
                with self.assertRaisesRegex(kt.KaggleFailure, 'username_missing'):
                    kt.main()
            self.assertFalse(target.exists())


if __name__ == '__main__':
    unittest.main()
