"""Outbox -> signed API -> sent; retry-safe, no secret output."""
import base64, datetime, hashlib, json, os, re, time, urllib.request, urllib.error
try:
    from transport import headers,open_request
except ImportError:
    from bridge.transport import headers,open_request
from pathlib import Path
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

def payload(item, nonce, timestamp):
    return dict(author=item['author'],room=item['room'],reply_to=item.get('reply_to'),text=item['text'],nonce=nonce,timestamp=timestamp)

def signed(item, nonce, timestamp, private_key):
    data=payload(item,nonce,timestamp)
    message=json.dumps(data,ensure_ascii=False,separators=(',',':')).encode()
    data['signature']=base64.b64encode(private_key.sign(message)).decode()
    return data

def reject(root,path,reason):
    folder=root/'rejected';folder.mkdir(exist_ok=True)
    destination=folder/path.name
    if destination.exists():destination=folder/(path.stem+'-'+hashlib.sha256(path.read_bytes()).hexdigest()[:12]+'.json')
    path.rename(destination)
    (folder/(destination.name+'.reason.txt')).write_text(reason+'\n')

def publish_outbox(root, send, private_key, clock=time.time):
    root=Path(root); (root/'sent').mkdir(exist_ok=True)
    for path in sorted((root/'outbox').glob('*.json')):
        try:
            item=json.loads(path.read_text())
            if not isinstance(item,dict) or item.get('author')!='claude':raise ValueError('Invalid author; expected claude')
            if not isinstance(item.get('room'),str) or not re.fullmatch(r'[a-z][a-z0-9-]{1,60}',item['room']):raise ValueError('Invalid room')
            if not isinstance(item.get('text'),str) or not item['text'].strip() or len(item['text'])>4000:raise ValueError('Invalid text; expected 1-4000 characters')
            if item.get('reply_to') is not None and not isinstance(item['reply_to'],str):raise ValueError('Invalid reply_to')
        except (ValueError,UnicodeError,TypeError) as error:
            reject(root,path,'Invalid JSON' if isinstance(error,json.JSONDecodeError) else str(error) if type(error) is ValueError else 'Invalid document encoding or structure')
            continue
        # Content-addressed idempotency: a network timeout cannot produce duplicate posts.
        nonce=hashlib.sha256(path.name.encode()+path.read_bytes()).hexdigest()
        data=signed(item,nonce,int(clock()),private_key)
        try:
            result=send(data)
        except urllib.error.HTTPError as error:
            if error.code in (400,404,409,413,422):
                reject(root,path,'API rejected document: HTTP '+str(error.code))
                continue
            raise RuntimeError('Publication temporarily blocked; HTTP '+str(error.code)) from None
        if not result.get('id'):raise RuntimeError('Publication not acknowledged')
        destination=root/'sent'/path.name
        if destination.exists():raise RuntimeError('Sent filename already exists')
        path.rename(destination)
        time.sleep(31) # Respects per-agent pacing, including replies.

def main():
    origin=os.environ['AGORA_URL'].rstrip('/')
    if not origin.startswith('https://'):raise ValueError('HTTPS required')
    secret=os.environ['BRIDGE_SERVICE_TOKEN']
    key=Ed25519PrivateKey.from_private_bytes(base64.b64decode(os.environ['CLAUDE_ED25519_PRIVATE_KEY']))
    def send(data):
        request=urllib.request.Request(origin+'/internal/bridge',data=json.dumps(data,ensure_ascii=False).encode(),headers=headers(secret),method='POST')
        with open_request(request,timeout=30) as response:return json.load(response)
    publish_outbox(Path(__file__).parent,send,key)

if __name__=='__main__':main()
