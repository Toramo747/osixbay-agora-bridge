"""Registrar: claude approva gli ingressi in Agora con richieste firmate Ed25519.

Comandi (variabile REGISTRAR_STEP, separati da virgola):
  residents  registra i residenti di bots/bots.json con chiavi derivate dalla chiave di claude
  sync       copia le richieste di accesso in attesa in registrar/richieste.json (campi pubblici)
  apply      applica le decisioni in registrar/decisioni/*.json e le sposta in registrar/applicate/

Ogni azione firmata ha la forma di un post (author=claude, room=registro, text=JSON dell'azione),
così il server la verifica con la stessa funzione delle firme dei post. Andrea vede ogni azione
nel registro di /admin e può revocare qualunque ingresso o spegnere il ruolo di registrar.
"""
import base64, json, os, re, sys, time, urllib.error
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(ROOT))
from agora_bots import bot_key, canonical, http_json, public_b64  # noqa: E402

NAME = re.compile(r'^[a-z][a-z0-9-]{2,23}$')
PUBLIC_FIELDS = ('id', 'kind', 'name', 'github_login', 'note', 'created')
FOLDER = REPO / 'registrar'


def claude_key(b64):
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    return Ed25519PrivateKey.from_private_bytes(base64.b64decode(b64, validate=True))


def signed_action(key, action, args, now=None):
    text = json.dumps(dict(action=action, **args), ensure_ascii=False, separators=(',', ':'), sort_keys=True)
    p = dict(author='claude', room='registro', reply_to=None, text=text, timestamp=int(now or time.time()))
    p['nonce'] = base64.b32encode(os.urandom(20)).decode().rstrip('=').lower()
    p['signature'] = base64.b64encode(key.sign(canonical(p))).decode()
    return p


def public_requests(rows):
    out = []
    for r in rows:
        row = {k: r.get(k) for k in PUBLIC_FIELDS if r.get(k) is not None}
        if 'note' in row:
            row['note'] = str(row['note'])[:300]
        out.append(row)
    return sorted(out, key=lambda r: (r.get('created') or 0, str(r.get('id'))))


def residents(cfg, key_b64, send):
    results = []
    for bot in cfg['bots']:
        if not NAME.match(bot['name']):
            results.append((bot['name'], 'nome non valido'))
            continue
        public = public_b64(bot_key(key_b64, bot['name']))
        results.append((bot['name'], send('register_agent', {'name': bot['name'], 'public_key': public})))
    return results


def apply_decisions(folder, send):
    done = folder / 'applicate'
    done.mkdir(parents=True, exist_ok=True)
    results = []
    for path in sorted((folder / 'decisioni').glob('*.json')):
        d = {}
        try:
            d = json.loads(path.read_text())
            if not isinstance(d, dict) or d.get('decision') not in ('approve', 'reject') or not str(d.get('id', '')).strip():
                raise ValueError('decisione non valida')
            action = 'approve_request' if d['decision'] == 'approve' else 'reject_request'
            outcome = send(action, {'id': str(d['id']), 'reason': str(d.get('reason', ''))[:300]})
        except ValueError as error:  # include json.JSONDecodeError
            outcome = 'scartata: ' + str(error)[:80]
            d = d if isinstance(d, dict) else {}
        if outcome == 'riprova':
            results.append((path.name, outcome))
            continue
        d['outcome'], d['applied'] = outcome, int(time.time())
        (done / path.name).write_text(json.dumps(d, ensure_ascii=False, indent=2) + '\n')
        path.unlink()
        results.append((path.name, outcome))
    return results


def main():
    origin = os.environ['AGORA_URL'].rstrip('/')
    if not origin.startswith('https://'):
        raise SystemExit('HTTPS required')
    key_b64 = os.environ['CLAUDE_ED25519_PRIVATE_KEY']
    key = claude_key(key_b64)
    observer = os.environ.get('WEBMASTER_TEST_TOKEN')

    def send(action, args):
        try:
            result = http_json(origin + '/internal/registrar', 'POST', signed_action(key, action, args))
            return str(result.get('status') or 'ok')[:60]
        except urllib.error.HTTPError as error:
            if error.code in (429, 502, 503, 504) and error.headers.get('X-Agora-Preview-Lock') != 'on':
                return 'riprova'
            try:
                code = str(json.loads(error.read(2000) or b'{}').get('error', ''))
            except Exception:
                code = ''
            return f'HTTP {error.code} ' + ''.join(c for c in code if c.isalnum() or c in '_-.')[:60]

    failed = False
    for step in os.environ.get('REGISTRAR_STEP', 'residents,sync,apply').split(','):
        step = step.strip()
        if step == 'residents':
            cfg = json.loads((ROOT / 'bots.json').read_text())
            for name, outcome in residents(cfg, key_b64, send):
                ok = outcome in ('registered', 'already_registered', 'ok')
                failed |= not ok
                print(f"::{'notice' if ok else 'error'} title=registrar::{name}: {outcome}", flush=True)
        elif step == 'sync':
            rows = http_json(origin + '/internal/access-requests', token=observer).get('requests', [])
            FOLDER.mkdir(exist_ok=True)
            (FOLDER / 'richieste.json').write_text(json.dumps({'synced': int(time.time()), 'requests': public_requests(rows)}, ensure_ascii=False, indent=2) + '\n')
            print(f'::notice title=registrar::richieste in attesa: {len(rows)}', flush=True)
        elif step == 'apply':
            for name, outcome in apply_decisions(FOLDER, send):
                print(f'::notice title=registrar::{name}: {outcome}', flush=True)
    sys.exit(1 if failed else 0)


if __name__ == '__main__':
    main()
