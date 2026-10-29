import base64, importlib.util, io, json, os, unittest, urllib.error
from unittest.mock import patch
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

spec=importlib.util.spec_from_file_location('setup', 'setup-claude-key.py')
setup=importlib.util.module_from_spec(spec);spec.loader.exec_module(setup)

class Response:
    status=201
    def __init__(self,data):self.data=data
    def __enter__(self):return io.BytesIO(json.dumps(self.data).encode()) if self.data is not None else self
    def __exit__(self,*args):pass

class LookupTests(unittest.TestCase):
    def run_setup(self,mode):
        seed=bytes(range(32)); public=base64.b64encode(Ed25519PrivateKey.from_private_bytes(seed).public_key().public_bytes(Encoding.Raw,PublicFormat.Raw)).decode()
        requests=[]
        def request(req,timeout):
            requests.append(req)
            if req.get_method()=='GET':
                self.assertEqual(req.get_header('Authorization'),'Bearer fake-observer-for-test')
                if mode=='missing':raise urllib.error.HTTPError(req.full_url,404,'',{},None)
                if mode=='forbidden':raise urllib.error.HTTPError(req.full_url,403,'',{},None)
                return Response({'public_key': public if mode=='existing' else 'different'})
            self.assertIsNone(req.get_header('Authorization'))
            self.assertEqual(json.loads(req.data)['invite'],'fake-invite-for-test')
            return Response(None)
        env={'AGORA_URL':'https://example.invalid','CLAUDE_ED25519_PRIVATE_KEY':base64.b64encode(seed).decode(),'CLAUDE_INVITE':'fake-invite-for-test','WEBMASTER_TEST_TOKEN':'fake-observer-for-test'}
        with patch.dict(os.environ,env,clear=True),patch.object(setup,'open_request',side_effect=request),patch.object(setup.subprocess,'run',side_effect=AssertionError('Must not rotate stored key')),patch('sys.stdout',new_callable=io.StringIO):
            setup.main()
        return requests
    def test_registration_uses_invite_without_observer_token(self):
        self.assertEqual(len(self.run_setup('missing')),2)
    def test_existing_key_is_checked_without_registration(self):
        self.assertEqual(len(self.run_setup('existing')),1)
    def test_mismatched_key_stops_without_rotation(self):
        with self.assertRaisesRegex(setup.Diagnostic,'Existing claude key differs'):self.run_setup('mismatch')
    def test_forbidden_lookup_is_not_treated_as_missing(self):
        with self.assertRaisesRegex(setup.Diagnostic,'Lookup HTTP 403'):self.run_setup('forbidden')

if __name__=='__main__':unittest.main()
