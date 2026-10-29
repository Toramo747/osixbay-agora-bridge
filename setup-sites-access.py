"""Transfer the Sites gate token using RSA-OAEP; never print plaintext secrets."""
import base64, os, subprocess, sys
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

LABEL = b'osixbay-agora-sites-access-v1'
TEMP_SECRET = 'SITES_BOOTSTRAP_PRIVATE_KEY'

def secret_command(action, name, value=None):
    result = subprocess.run(
        ['gh', 'secret', action, name, '--repo', os.environ['GITHUB_REPOSITORY']],
        input=value, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        check=False,
    )
    if result.returncode:
        raise RuntimeError('Secret operation failed')

def prepare():
    existing = os.environ.get(TEMP_SECRET)
    if existing:
        key = serialization.load_der_private_key(base64.b64decode(existing, validate=True), None)
    else:
        key = rsa.generate_private_key(public_exponent=65537, key_size=3072)
        private = base64.b64encode(key.private_bytes(
            serialization.Encoding.DER, serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )).decode()
        print('::add-mask::' + private, flush=True)
        secret_command('set', TEMP_SECRET, private.encode())
    # This public key is the only variable data printed by the workflow.
    print(key.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode(), end='')

def decrypt(private, ciphertext):
    key = serialization.load_der_private_key(base64.b64decode(private, validate=True), None)
    return key.decrypt(base64.b64decode(ciphertext, validate=True), padding.OAEP(
        mgf=padding.MGF1(hashes.SHA256()), algorithm=hashes.SHA256(), label=LABEL,
    ))

def install():
    if not os.environ.get('SITES_ACCESS_TOKEN'):
        token = decrypt(os.environ[TEMP_SECRET], os.environ['ENCRYPTED_TOKEN'])
        if not 32 <= len(token) <= 4096 or any(c < 33 or c > 126 for c in token):
            raise RuntimeError('Invalid token')
        print('::add-mask::' + token.decode('ascii'), flush=True)
        secret_command('set', 'SITES_ACCESS_TOKEN', token)
    # A retry after the final deletion failed only repeats cleanup, not rotation.
    if os.environ.get(TEMP_SECRET):
        secret_command('delete', TEMP_SECRET)
    print('SITES_ACCESS_TOKEN saved; temporary private key removed.')

if __name__ == '__main__':
    try:
        {'prepare': prepare, 'install': install}[os.environ['SETUP_ACTION']]()
    except Exception:
        print('Setup incomplete; check configuration and retry. No secret was printed.', file=sys.stderr)
        sys.exit(1)
