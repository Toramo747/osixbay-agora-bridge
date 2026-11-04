"""Percorsi e utilità condivise della biblioteca genesis-godot. Solo libreria standard."""
import json, re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]              # genesis/
KNOWLEDGE = ROOT / 'knowledge'
LOCK = KNOWLEDGE / 'sources' / 'sources.lock.json'
CACHE = KNOWLEDGE / 'sources' / 'cache'                 # ricostruibile, non versionata
MANIFEST = KNOWLEDGE / 'manifest.json'
INDEX = KNOWLEDGE / 'index' / 'godot.sqlite'            # ricostruibile, non versionato
CATALOG = KNOWLEDGE / 'catalog' / 'genesis_catalog.json'
EXAMPLES = KNOWLEDGE / 'examples'
REPORTS = KNOWLEDGE / 'reports'
TOOLS_DIR = ROOT / 'tools'
GODOT_DIR = CACHE / 'godot-bin'


def load_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def dump_json(path, data):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=False) + '\n', encoding='utf-8')


def lock():
    return load_json(LOCK)


def glob_to_re(pattern):
    """Glob con ** (qualsiasi profondità), * (un livello) e ? → regex ancorata."""
    out, i = '', 0
    while i < len(pattern):
        c = pattern[i]
        if pattern.startswith('**/', i):
            out += '(?:.*/)?'; i += 3; continue
        if pattern.startswith('**', i):
            out += '.*'; i += 2; continue
        out += {'*': '[^/]*', '?': '[^/]'}.get(c, re.escape(c)); i += 1
    return re.compile('^' + out + '$')


def selected(rel, include, exclude):
    rel = rel.replace('\\', '/')
    return any(glob_to_re(p).match(rel) for p in include) and not any(glob_to_re(p).match(rel) for p in exclude)


def godot_binary():
    """Percorso del binario Godot fissato, se già scaricato e verificato da acquire_docs.py --with-godot."""
    for p in sorted(GODOT_DIR.glob('Godot_v*_linux.x86_64')):
        if p.is_file():
            return p
    return None
