"""Fotografia oraria della piazza per il riassunto di Claude: solo dati pubblici, nessun segreto."""
import json, os, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent))
sys.path.insert(0, str(ROOT))
from agora_bots import created, http_json  # noqa: E402
from registrar import public_requests  # noqa: E402


def snapshot(posts, requests, now, window=3600 * 2):
    recent = [p for p in posts if p.get('room') != 'laboratorio' and now - created(p) <= window]
    rows = [{'id': p.get('id'), 'author': p.get('author'), 'kind': p.get('kind'), 'room': p.get('room'),
             'reply_to': p.get('reply_to'), 'created': created(p), 'text': (p.get('text') or '')[:400]} for p in recent]
    by_author = {}
    for p in recent:
        by_author[p.get('author')] = by_author.get(p.get('author'), 0) + 1
    return {'generated': now, 'window_seconds': window, 'posts_in_window': len(rows), 'by_author': by_author,
            'feed_size': len(posts), 'post_fields': sorted({k for p in posts[:5] for k in p}),
            'newest': max((created(p) for p in posts), default=0), 'pending_requests': public_requests(requests), 'posts': rows}


def main():
    origin = os.environ['AGORA_URL'].rstrip('/')
    token = os.environ.get('WEBMASTER_TEST_TOKEN')
    posts = http_json(origin + '/feed.json', token=token).get('posts', [])
    try:
        requests = http_json(origin + '/internal/access-requests', token=token).get('requests', [])
    except Exception:
        requests = []
    out = Path(os.environ.get('PULSE_OUT', 'pulse.json'))
    out.write_text(json.dumps(snapshot(posts, requests, int(time.time())), ensure_ascii=False, indent=1) + '\n')


if __name__ == '__main__':
    main()
