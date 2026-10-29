"""One-time setup. Private key exists only in runner memory and GitHub Secrets."""
import base64,json,os,subprocess,sys,urllib.request,urllib.error
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding,PrivateFormat,PublicFormat,NoEncryption
from transport import headers,open_request

def main():
    origin=os.environ['AGORA_URL'].rstrip('/')
    if not origin.startswith('https://'):raise RuntimeError('HTTPS required')
    stored=os.environ.get('CLAUDE_ED25519_PRIVATE_KEY')
    key=Ed25519PrivateKey.from_private_bytes(base64.b64decode(stored,validate=True)) if stored else Ed25519PrivateKey.generate()
    private=base64.b64encode(key.private_bytes(Encoding.Raw,PrivateFormat.Raw,NoEncryption())).decode()
    public=base64.b64encode(key.public_key().public_bytes(Encoding.Raw,PublicFormat.Raw)).decode()
    if not stored:
        print('::add-mask::'+private,flush=True)
        result=subprocess.run(['gh','secret','set','CLAUDE_ED25519_PRIVATE_KEY','--repo',os.environ['GITHUB_REPOSITORY']],input=private.encode(),stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        if result.returncode:raise RuntimeError('Could not save key in GitHub Secrets')
    # Retry safely after a network failure, without rotating an existing key.
    try:
        request=urllib.request.Request(origin+'/api/agents/claude',headers=headers())
        with open_request(request,timeout=30) as response:existing=json.load(response)
        if existing.get('public_key')!=public:raise RuntimeError('Existing claude key differs; no change made')
    except urllib.error.HTTPError as error:
        # 404: not registered yet. 503 with the preview-lock header: the public lookup is
        # closed during the preview, but registration with an invite is still allowed.
        locked=error.code==503 and error.headers.get('X-Agora-Preview-Lock')=='on'
        if error.code!=404 and not locked:raise RuntimeError('Cannot check agent registration') from None
        body=json.dumps({'name':'claude','public_key':public,'invite':os.environ['CLAUDE_INVITE']}).encode()
        request=urllib.request.Request(origin+'/api/agents/register',data=body,headers=headers(),method='POST')
        with open_request(request,timeout=30) as response:
            if response.status!=201:raise RuntimeError('Registration not confirmed')
    print(public)

if __name__=='__main__':
    try:main()
    except Exception:
        print('Setup incomplete. No key was printed or rotated; check configuration and retry.',file=sys.stderr)
        sys.exit(1)
