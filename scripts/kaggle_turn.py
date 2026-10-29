"""Run a private Kaggle writer; accept only drafts from this invocation and plan.

CLI output is never forwarded: it may contain credentials or notebook content.
Only public plan data and an invocation identifier are uploaded, never credentials.
"""
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]


class KaggleFailure(Exception):
    pass


def cli(*args):
    try:
        result = subprocess.run(['kaggle', 'kernels', *args], capture_output=True,
                                text=True, timeout=120, check=False)
    except (OSError, subprocess.TimeoutExpired):
        raise KaggleFailure('kaggle_command_unavailable_or_timeout') from None
    if result.returncode:
        # Never propagate raw stderr, stdout or exception messages.
        raise KaggleFailure('kaggle_' + args[0] + '_failed')
    return result.stdout.lower() if args[0] == 'status' else ''


def matches(drafts, run_id, plan_sha, bot):
    return (isinstance(drafts, dict)
            and drafts.get('run_id') == run_id
            and drafts.get('plan_sha256') == plan_sha
            and drafts.get('bot') == bot['name']
            and drafts.get('model') == bot['model']['hf']
            and all(isinstance(drafts.get(k), str) and len(drafts[k]) <= 4000
                    for k in ('text', 'diary')))


def wait_for_drafts(ref, run_id, plan_sha, bot, *, command=cli, sleep=time.sleep,
                    polls=90, interval=30):
    for _ in range(polls):
        sleep(interval)
        status = command('status', ref)
        if re.search(r'\b(error|failed|cancelled|canceled)\b', status):
            raise KaggleFailure('kaggle_run_failed_or_cancelled')
        if not re.search(r'\bcomplete\b', status):
            continue
        # COMPLETE and output can both belong to an older visible version.
        # A fresh directory prevents partial downloads reusing a previous file.
        with tempfile.TemporaryDirectory() as tmp:
            command('output', ref, '-p', tmp, '--file-pattern', '^drafts[.]json$')
            path = Path(tmp) / 'drafts.json'
            if not path.is_file() or path.stat().st_size > 32_000:
                continue
            try:
                drafts = json.loads(path.read_text())
            except (ValueError, UnicodeError):
                continue
            if matches(drafts, run_id, plan_sha, bot):
                return drafts
    raise KaggleFailure('kaggle_timeout_no_matching_drafts')


def prepare_kernel(folder, username, bot, plan_bytes, run_id):
    plan_sha = hashlib.sha256(plan_bytes).hexdigest()
    src = (ROOT / 'kaggle/agora_writer.py').read_text()
    src = src.replace('__PLAN_B64__', base64.b64encode(plan_bytes).decode())
    src = src.replace('__MODEL_HF__', bot['model']['hf'])
    src = src.replace('__RUN_ID__', run_id).replace('__PLAN_SHA256__', plan_sha)
    (folder / 'agora_writer.py').write_text(src)
    slug = 'agora-' + bot['name']
    metadata = {'id': username + '/' + slug, 'title': slug, 'code_file': 'agora_writer.py',
                'language': 'python', 'kernel_type': 'script', 'is_private': True,
                'enable_gpu': True, 'enable_internet': True, 'dataset_sources': [],
                'competition_sources': [], 'kernel_sources': [], 'model_sources': []}
    (folder / 'kernel-metadata.json').write_text(json.dumps(metadata))
    return metadata['id'], plan_sha


def main():
    output = Path(sys.argv[2])
    output.unlink(missing_ok=True)
    username = os.environ.get('KAGGLE_USERNAME', '')
    if not re.fullmatch(r'[A-Za-z0-9_-]+', username):
        raise KaggleFailure('kaggle_username_missing_or_invalid')
    if not os.environ.get('KAGGLE_API_TOKEN', '').strip():
        raise KaggleFailure('kaggle_api_token_missing')
    cfg = json.loads((ROOT / 'bots/bots.json').read_text())
    bot = next(b for b in cfg['bots'] if b['name'] == os.environ['BOT_NAME']
               and b.get('runner') == 'kaggle')
    plan_bytes = Path(sys.argv[1]).read_bytes()
    if json.loads(plan_bytes).get('bot') != bot['name']:
        raise KaggleFailure('kaggle_plan_bot_mismatch')
    run_id = secrets.token_hex(16)  # Public challenge, not an authentication token.
    with tempfile.TemporaryDirectory() as tmp:
        ref, plan_sha = prepare_kernel(Path(tmp), username, bot, plan_bytes, run_id)
        cli('push', '-p', tmp)
        drafts = wait_for_drafts(ref, run_id, plan_sha, bot)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(drafts, ensure_ascii=False))
    print('Kaggle: current invocation and plan verified')


if __name__ == '__main__':
    try:
        main()
    except KaggleFailure as error:
        print('::error title=kaggle::' + str(error), file=sys.stderr)
        sys.exit(1)
    except Exception:
        print('::error title=kaggle::kaggle_unexpected_failure', file=sys.stderr)
        sys.exit(1)
