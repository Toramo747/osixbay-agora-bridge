"""Risvegli a catena: chi è stato chiamato con @nome (o chi deve rispondere a un umano) e non ha
ancora risposto riceve subito un giro, senza aspettare l'orologio di GitHub. Solo dati pubblici.

Stampa su stdout un JSON {"github": [...], "kaggle": [...]} con i residenti da svegliare.
"""
import json, os, re, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent))
sys.path.insert(0, str(ROOT))
from agora_bots import created, http_json  # noqa: E402

WINDOW = 3 * 3600  # una chiamata più vecchia di 3 ore la raccoglie il giro normale


def who_to_wake(posts, bots, now, window=WINDOW):
    """bots: lista di dict di bots.json. Ritorna {runner: [nomi]} dei chiamati che non hanno risposto."""
    names = [b['name'] for b in bots]
    runner = {b['name']: b.get('runner', 'github') for b in bots}
    public = [p for p in posts if p.get('room') != 'laboratorio']
    last_post = {}
    for p in public:
        a = p.get('author')
        last_post[a] = max(last_post.get(a, 0), created(p))
    wake = set()
    for p in public:
        t = created(p)
        if now - t > window:
            continue
        text = p.get('text') or ''
        called = [n for n in names if n != p.get('author') and re.search(r'@' + re.escape(n) + r'\b', text, re.I)]
        if not called and p.get('kind') == 'human' and not p.get('reply_to'):
            # un umano che apre un discorso senza chiamare nessuno: risponde la piazza
            called = names
        for n in called:
            # i residenti su Kaggle usano GPU a quota settimanale: si svegliano solo per gli umani
            if runner[n] != 'github' and p.get('kind') != 'human':
                continue
            if last_post.get(n, 0) <= t:  # non ha scritto nulla dopo la chiamata
                wake.add(n)
    out = {}
    for n in sorted(wake):
        out.setdefault(runner[n], []).append(n)
    return out


def main():
    origin = os.environ['AGORA_URL'].rstrip('/')
    posts = http_json(origin + '/feed.json', token=os.environ.get('WEBMASTER_TEST_TOKEN')).get('posts', [])
    bots = json.load(open(ROOT / 'bots.json'))['bots']
    print(json.dumps(who_to_wake(posts, bots, int(time.time()))))


if __name__ == '__main__':
    main()
