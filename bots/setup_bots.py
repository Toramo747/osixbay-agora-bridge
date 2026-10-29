"""Setup una tantum dei residenti: chiave madre nei Secret, registrazione di ogni bot con il suo invito.

BOTS_INVITES (Secret, temporaneo): una riga per bot, "nome=codice". Si cancella dopo il setup.
Stampa solo nomi, chiavi pubbliche ed esiti; mai inviti o chiavi private.
"""
import base64, json, os, secrets, subprocess, sys, urllib.error, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent))
sys.path.insert(0, str(ROOT))
from transport import headers, open_request  # noqa: E402
from agora_bots import bot_key, public_b64  # noqa: E402


def note(level, text):
    print(f'::{level} title=setup-bots::{text}', flush=True)


def ensure_master():
    master = os.environ.get('BOTS_MASTER_KEY')
    if master:
        return master
    master = base64.b64encode(secrets.token_bytes(32)).decode()
    print('::add-mask::' + master, flush=True)
    result = subprocess.run(['gh', 'secret', 'set', 'BOTS_MASTER_KEY', '--repo', os.environ['GITHUB_REPOSITORY']],
                            input=master.encode(), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if result.returncode:
        raise SystemExit('Could not save BOTS_MASTER_KEY')
    return master


def parse_invites(raw):
    out = {}
    for line in (raw or '').splitlines():
        if '=' in line:
            name, code = line.split('=', 1)
            out[name.strip()] = code.strip()
    return out


def register(origin, observer, name, public, invite):
    try:
        request = urllib.request.Request(origin + '/api/agents/' + name, headers=headers(observer))
        with open_request(request, timeout=30) as response:
            existing = json.load(response)
        return 'già registrato' if existing.get('public_key') == public else 'REGISTRATO CON UN\'ALTRA CHIAVE: nessuna modifica'
    except urllib.error.HTTPError as error:
        locked = error.code == 503 and error.headers.get('X-Agora-Preview-Lock') == 'on'
        if error.code != 404 and not locked:
            return f'controllo HTTP {error.code}'
    if not invite:
        return 'invito mancante in BOTS_INVITES'
    body = json.dumps({'name': name, 'public_key': public, 'invite': invite}).encode()
    request = urllib.request.Request(origin + '/api/agents/register', data=body, headers=headers(), method='POST')
    try:
        with open_request(request, timeout=30) as response:
            return 'registrato' if response.status in (200, 201) else f'registrazione HTTP {response.status}'
    except urllib.error.HTTPError as failure:
        try:
            code = str(json.loads(failure.read(2000) or b'{}').get('error', ''))
        except Exception:
            code = ''
        return f'registrazione HTTP {failure.code} ' + ''.join(c for c in code if c.isalnum() or c in '_-.')[:60]


def main():
    origin = os.environ['AGORA_URL'].rstrip('/')
    if not origin.startswith('https://'):
        raise SystemExit('HTTPS required')
    cfg = json.loads((ROOT / 'bots.json').read_text())
    master = ensure_master()
    invites = parse_invites(os.environ.get('BOTS_INVITES'))
    failed = False
    for bot in cfg['bots']:
        public = public_b64(bot_key(master, bot['name']))
        outcome = register(origin, os.environ.get('WEBMASTER_TEST_TOKEN'), bot['name'], public, invites.get(bot['name']))
        ok = outcome in ('registrato', 'già registrato')
        failed |= not ok
        note('notice' if ok else 'error', f"{bot['name']}: {outcome} (chiave pubblica {public})")
    sys.exit(1 if failed else 0)


if __name__ == '__main__':
    main()
