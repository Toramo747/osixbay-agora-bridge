"""Daily public snapshot. No private API fields are mirrored."""
import datetime,json,os,urllib.error,urllib.request
from pathlib import Path
from transport import headers,open_request

def main():
    origin=os.environ['AGORA_URL'].rstrip('/')
    if not origin.startswith('https://'):raise ValueError('HTTPS required')
    request=urllib.request.Request(origin+'/api/mirror',headers=headers(os.environ['BRIDGE_SERVICE_TOKEN']))
    try:
        with open_request(request,timeout=60) as response:
            rows=[json.loads(line) for line in response.read().decode().splitlines() if line.strip()]
    except urllib.error.HTTPError as error:
        # While the preview lock is on the server refuses the export on purpose: nothing to mirror yet.
        if error.code==503 and error.headers.get('X-Agora-Preview-Lock')=='on':
            print('Preview lock on: mirror skipped.');return
        raise
    allowed={'text','author','date','signature'}
    if any(set(row)!=allowed for row in rows):raise ValueError('Unexpected private fields')
    root=Path(__file__).parent/'mirror';root.mkdir(exist_ok=True)
    filename=datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d')+'.jsonl'
    (root/filename).write_text(''.join(json.dumps(row,ensure_ascii=False)+'\n' for row in rows))

if __name__=='__main__':main()
