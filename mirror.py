"""Daily public snapshot. No private API fields are mirrored."""
import datetime,json,os,urllib.request
from pathlib import Path
from transport import headers,open_request

def main():
    origin=os.environ['AGORA_URL'].rstrip('/')
    if not origin.startswith('https://'):raise ValueError('HTTPS required')
    request=urllib.request.Request(origin+'/api/mirror',headers=headers(os.environ['BRIDGE_SERVICE_TOKEN']))
    with open_request(request,timeout=60) as response:
        rows=[json.loads(line) for line in response.read().decode().splitlines() if line.strip()]
    allowed={'text','author','date','signature'}
    if any(set(row)!=allowed for row in rows):raise ValueError('Unexpected private fields')
    root=Path(__file__).parent/'mirror';root.mkdir(exist_ok=True)
    filename=datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d')+'.jsonl'
    (root/filename).write_text(''.join(json.dumps(row,ensure_ascii=False)+'\n' for row in rows))

if __name__=='__main__':main()
