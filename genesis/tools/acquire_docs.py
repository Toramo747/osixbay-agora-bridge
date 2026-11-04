#!/usr/bin/env python3
"""Acquisisce le fonti ufficiali di Godot fissate in sources.lock.json e scrive il manifest.

- clone sparse e superficiale (--depth 1, --filter=blob:none) di ogni repository al ref fissato;
- verifica che il commit ottenuto coincida con quello del lock (altrimenti si ferma);
- calcola SHA256 di ogni file selezionato e un hash complessivo per fonte;
- scrive knowledge/manifest.json e knowledge/sources/files.sha256 (formato sha256sum);
- con --with-godot scarica il binario Godot fissato e ne verifica lo SHA512 ufficiale.

La cache (knowledge/sources/cache/) non si versiona: si ricostruisce con questo comando.
Solo libreria standard + git. Nessuna chiave, nessun servizio a pagamento.

Uso:  python3 genesis/tools/acquire_docs.py [--offline] [--with-godot]
"""
import argparse, datetime, hashlib, io, os, subprocess, sys, urllib.request, zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import CACHE, GODOT_DIR, KNOWLEDGE, MANIFEST, dump_json, load_json, lock, selected  # noqa: E402


def git(*args, cwd=None):
    return subprocess.run(['git', *args], cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()


def _has_head(dest):
    return subprocess.run(['git', 'rev-parse', '--verify', '-q', 'HEAD'], cwd=dest, capture_output=True).returncode == 0


def fetch_source(src, offline=False):
    dest = CACHE / src['id']
    if not (dest / '.git').exists():
        if offline:
            raise SystemExit(f"cache assente per {src['id']}: eseguire senza --offline")
        dest.mkdir(parents=True, exist_ok=True)
        git('init', '-q', cwd=dest)
        git('remote', 'add', 'origin', src['repo'], cwd=dest)
    if not offline and (not _has_head(dest) or git('rev-parse', 'HEAD', cwd=dest) != src['commit']):
        # si scarica il commit fissato, non il ref: il ref è solo documentazione
        git('config', 'core.sparseCheckout', 'true', cwd=dest)
        git('sparse-checkout', 'set', '--no-cone', *src['sparse'], cwd=dest)
        git('fetch', '-q', '--depth', '1', '--filter=blob:none', 'origin', src['commit'], cwd=dest)
        git('checkout', '-q', '--detach', 'FETCH_HEAD', cwd=dest)
    head = git('rev-parse', 'HEAD', cwd=dest)
    if head != src['commit']:
        raise SystemExit(f"{src['id']}: commit {head} diverso dal lock {src['commit']}. "
                         'Aggiornare il lock solo dopo aver rivisto la nuova versione.')
    return dest


def hash_files(src, dest):
    files = []
    for p in sorted(dest.rglob('*')):
        if '.git' in p.parts or not p.is_file():
            continue
        rel = p.relative_to(dest).as_posix()
        if selected(rel, src['include'], src['exclude']):
            data = p.read_bytes()
            files.append((rel, hashlib.sha256(data).hexdigest(), len(data)))
    total = hashlib.sha256(''.join(f'{h}  {r}\n' for r, h, _ in files).encode()).hexdigest()
    return files, total


def fetch_godot(spec):
    GODOT_DIR.mkdir(parents=True, exist_ok=True)
    zpath = GODOT_DIR / spec['file']
    if not zpath.exists():
        with urllib.request.urlopen(spec['url'], timeout=300) as r:
            zpath.write_bytes(r.read())
    digest = hashlib.sha512(zpath.read_bytes()).hexdigest()
    if digest != spec['sha512']:
        zpath.unlink()
        raise SystemExit('SHA512 del binario Godot non corrisponde: file rimosso')
    with zipfile.ZipFile(io.BytesIO(zpath.read_bytes())) as z:
        for name in z.namelist():
            out = GODOT_DIR / Path(name).name
            out.write_bytes(z.read(name))
            out.chmod(0o755)
    return digest


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--offline', action='store_true', help='usa solo la cache esistente')
    ap.add_argument('--with-godot', action='store_true', help='scarica e verifica anche il binario Godot')
    ap.add_argument('--no-write', action='store_true', help='verifica soltanto: non riscrive manifest.json e files.sha256 '
                    '(per i runner, così i file versionati non cambiano)')
    a = ap.parse_args(argv)
    cfg = lock()
    previous = {}
    sums = KNOWLEDGE / 'sources' / 'files.sha256'
    if sums.exists():
        for line in sums.read_text().splitlines():
            h, _, path = line.partition('  ')
            previous[path] = h
    now = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat()
    manifest = {'godot_version': cfg['godot_version'], 'docs_release': cfg['docs_release'], 'acquisito_il': now,
                'sources': [], 'godot_binary': None}
    lines, current = [], {}
    for src in cfg['sources']:
        dest = fetch_source(src, a.offline)
        files, total = hash_files(src, dest)
        lic = dest / src['licenza_file']
        manifest['sources'].append({
            'id': src['id'], 'titolo': src['titolo'], 'url': src['repo'], 'ref': src['ref'], 'commit': src['commit'],
            'url_base': src['url_base'], 'licenza': src['licenza'], 'attribuzione': src['attribuzione'],
            'redistribuibile': src['redistribuibile'],
            'licenza_sha256': hashlib.sha256(lic.read_bytes()).hexdigest() if lic.exists() else None,
            'file': len(files), 'byte': sum(s for _, _, s in files), 'contenuto_sha256': total})
        for rel, h, _ in files:
            key = f"{src['id']}/{rel}"
            lines.append(f'{h}  {key}')
            current[key] = h
    if a.with_godot:
        spec = cfg['godot_binary']
        manifest['godot_binary'] = {'file': spec['file'], 'url': spec['url'], 'sha512_verificato': fetch_godot(spec),
                                    'sha512_fonte': spec['sha512_fonte']}
    elif MANIFEST.exists():
        manifest['godot_binary'] = load_json(MANIFEST).get('godot_binary')
    changes = {'aggiunti': sorted(set(current) - set(previous)), 'rimossi': sorted(set(previous) - set(current)),
               'modificati': sorted(k for k in current if k in previous and previous[k] != current[k])}
    manifest['ultima_variazione'] = {k: len(v) for k, v in changes.items()}
    if not a.no_write:
        sums.write_text('\n'.join(lines) + '\n')
        dump_json(MANIFEST, manifest)
    for s in manifest['sources']:
        print(f"{s['id']}: {s['file']} file, {s['byte']} byte, sha256 {s['contenuto_sha256'][:16]}…")
    print('variazioni rispetto alla volta precedente:', manifest['ultima_variazione'])
    return manifest


if __name__ == '__main__':
    os.umask(0o022)
    main()
