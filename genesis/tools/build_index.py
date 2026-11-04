#!/usr/bin/env python3
"""Costruisce l'indice SQLite FTS5 della biblioteca Godot di Genesis dalla cache acquisita.

Tabelle principali
  docs      sezioni del manuale (RST), una riga per sezione, con URL e ancora
  members   API: classi e loro metodi, proprietà, segnali, costanti, enum, annotazioni, theme item
  examples  esempi di codice: blocchi del manuale, [codeblocks] delle classi, script .gd dei demo ufficiali
  renames   tabella ufficiale delle rinomine Godot 3 → 4 (renames_map_3_to_4.cpp)
  files     hash SHA256 dei file indicizzati, per l'aggiornamento incrementale

Ricostruzione incrementale: un file già indicizzato con lo stesso SHA256 viene saltato; file cambiati
vengono reindicizzati, file spariti vengono rimossi. --full ricostruisce da zero.

Uso:  python3 genesis/tools/build_index.py [--full]
"""
import argparse, hashlib, re, sqlite3, sys, time
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import CACHE, INDEX, lock, selected  # noqa: E402

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS files(source TEXT, path TEXT, sha256 TEXT, PRIMARY KEY(source, path));
CREATE TABLE IF NOT EXISTS docs(id INTEGER PRIMARY KEY, source TEXT, path TEXT, title TEXT, section TEXT,
  anchor TEXT, url TEXT, body TEXT);
CREATE VIRTUAL TABLE IF NOT EXISTS docs_fts USING fts5(title, section, body, tokenize='porter unicode61');
CREATE TABLE IF NOT EXISTS members(id INTEGER PRIMARY KEY, source TEXT, path TEXT, class TEXT, kind TEXT, name TEXT,
  signature TEXT, type TEXT, inherits TEXT, description TEXT, deprecated TEXT, experimental TEXT, url TEXT);
CREATE INDEX IF NOT EXISTS members_name ON members(name);
CREATE INDEX IF NOT EXISTS members_class ON members(class);
CREATE VIRTUAL TABLE IF NOT EXISTS api_fts USING fts5(class, name, signature, description, tokenize='porter unicode61');
CREATE TABLE IF NOT EXISTS examples(id INTEGER PRIMARY KEY, source TEXT, path TEXT, title TEXT, language TEXT,
  code TEXT, context TEXT, url TEXT);
CREATE VIRTUAL TABLE IF NOT EXISTS examples_fts USING fts5(title, context, code, tokenize='porter unicode61');
CREATE TABLE IF NOT EXISTS renames(category TEXT, old TEXT, new TEXT);
CREATE INDEX IF NOT EXISTS renames_old ON renames(old);
"""
DOCS_URL = 'https://docs.godotengine.org/en/' + lock()['docs_release']
HEADING = set('=-~^"\'`#*+<>_:.')


def slug(text):
    return re.sub(r'[^a-z0-9]+', '-', text.lower()).strip('-')


# ---------------------------------------------------------------- RST (manuale)

def clean_rst(text):
    text = re.sub(r':(?:ref|doc|class|meth|attr|any|abbr|kbd|menu|term|code|ui|inlinerst):`([^`<]*?)\s*<[^>]*>`', r'\1', text)
    text = re.sub(r':ref:`([^`]*)`', lambda m: m.group(1).replace('class_', '').replace('doc_', '').replace('_', ' '), text)
    text = re.sub(r':[a-z]+:`([^`]*)`', r'\1', text)
    text = re.sub(r'``([^`]*)``', r'\1', text)
    text = re.sub(r'`([^`<]*?)\s*<[^>]*>`_+', r'\1', text)
    text = re.sub(r'^\s*\.\. (?:_[^:]+|\|[^|]+\|[^\n]*|image|figure|video|seealso::?|note|tip|warning|important|danger|caution|attention|rst-class|toctree|table|list-table|csv-table|raw|only|tabs|tab|admonition|code-block|code-tab|highlight|contents|include)[^\n]*$', '', text, flags=re.M)
    text = re.sub(r'^\s*:(?:maxdepth|caption|name|glob|hidden|alt|align|width|target|header-rows|widths|class|linenos|emphasize-lines|titlesonly)[^\n]*$', '', text, flags=re.M)
    return re.sub(r'\n{3,}', '\n\n', text).strip()


def rst_code_blocks(lines):
    """Estrae blocchi '.. code-block:: lang' e '.. code-tab:: lang' con il loro contenuto indentato."""
    blocks, i = [], 0
    while i < len(lines):
        m = re.match(r'^(\s*)\.\. (?:code-block|code-tab|code)::\s*(\S*)(.*)$', lines[i])
        if not m:
            i += 1; continue
        base, lang = len(m.group(1)), (m.group(2) or 'text').lower()
        i += 1
        while i < len(lines) and re.match(r'^\s*:\w[\w-]*:', lines[i]):
            i += 1
        body = []
        while i < len(lines) and (not lines[i].strip() or len(lines[i]) - len(lines[i].lstrip()) > base):
            body.append(lines[i]); i += 1
        while body and not body[-1].strip():
            body.pop()
        code = [l for l in body]
        ind = min((len(l) - len(l.lstrip()) for l in code if l.strip()), default=0)
        text = '\n'.join(l[ind:] for l in code).strip('\n')
        if text.strip():
            blocks.append((lang, text))
    return blocks


def parse_rst(raw, path, url_base):
    """Divide una pagina in sezioni per titolo. Restituisce (sezioni, esempi)."""
    lines = raw.splitlines()
    page_url = url_base + path[:-4] + '.html'
    heads = []
    for i in range(len(lines) - 1):
        t, u = lines[i].rstrip(), lines[i + 1].rstrip()
        if t and not t.startswith(' ') and u and len(set(u)) == 1 and u[0] in HEADING and len(u) >= len(t) >= 2 \
                and not t.startswith('..') and not (i > 0 and lines[i - 1].rstrip() == u):
            heads.append(i)
        elif i + 2 < len(lines) and t and len(set(t)) == 1 and t[0] in HEADING and lines[i + 2].rstrip() == t and u.strip():
            heads.append(i + 1)    # titolo con sopralinea
    page_title = lines[heads[0]].strip() if heads else Path(path).stem
    sections, examples = [], []
    bounds = [0] + heads + [len(lines)]
    for k in range(len(bounds) - 1):
        start, end = bounds[k], bounds[k + 1]
        if k > 0:
            title = lines[start].strip(); start += 2
            if start < len(lines) and lines[start - 1].strip() and len(set(lines[start - 1].strip())) == 1 \
                    and lines[start].strip() and len(set(lines[start].strip())) == 1:
                start += 1
        else:
            title = page_title
        chunk = lines[start:end]
        body = clean_rst('\n'.join(chunk))
        anchor = '' if k <= 1 else slug(title)
        url = page_url + (f'#{anchor}' if anchor else '')
        if len(body) > 20 or k == 1:
            sections.append({'title': page_title, 'section': title if k > 1 else page_title, 'anchor': anchor,
                             'url': url, 'body': body})
        for lang, code in rst_code_blocks(chunk):
            ctx = re.sub(r'\s+', ' ', body[:400])
            examples.append({'title': f'{page_title} — {title}', 'language': lang, 'code': code, 'context': ctx, 'url': url})
    return sections, examples


# ---------------------------------------------------------------- XML (riferimento classi)

def clean_bb(text):
    if not text:
        return ''
    text = re.sub(r'\[codeblocks?\].*?\[/codeblocks?\]', ' [vedi esempio] ', text, flags=re.S)
    text = re.sub(r'\[(?:method|member|signal|constant|enum|annotation|theme_item|constructor|operator) ([^\]]+)\]', r'\1', text)
    text = re.sub(r'\[param ([^\]]+)\]', r'\1', text)
    text = re.sub(r'\[url=([^\]]+)\]([^\[]*)\[/url\]', r'\2 (\1)', text)
    text = re.sub(r'\[/?(?:b|i|u|code|kbd|br|center|codeblock|gdscript|csharp|lb|rb)\]', '', text)
    text = re.sub(r'\[([A-Z@][A-Za-z0-9_@.]*)\]', r'\1', text)
    text = text.replace('$DOCS_URL', DOCS_URL)
    return '\n'.join(l.strip() for l in text.strip().splitlines()).strip()


def bb_examples(text):
    out = []
    for block in re.findall(r'\[codeblocks?\](.*?)\[/codeblocks?\]', text or '', flags=re.S):
        gd = re.search(r'\[gdscript\](.*?)\[/gdscript\]', block, flags=re.S)
        code = gd.group(1) if gd else (block if '[csharp]' not in block else '')
        lines = [l for l in code.split('\n')]
        ind = min((len(l) - len(l.lstrip('\t')) for l in lines if l.strip()), default=0)
        code = '\n'.join(l[ind:] for l in lines).strip('\n')
        if code.strip():
            out.append(code)
    return out


def anchor(cls, kind, name):
    if kind == 'enum':
        return f"enum-{slug(cls)}-{slug(name)}"
    if kind == 'method' and name.startswith('_'):
        kind = 'private-method'
    return f"class-{slug(cls)}-{slug(kind)}-{slug(name)}"


def params_sig(el):
    ps = []
    for p in sorted(el.findall('param'), key=lambda p: int(p.get('index', 0))):
        s = f"{p.get('name')}: {p.get('type')}"
        if p.get('default') is not None:
            s += f" = {p.get('default')}"
        ps.append(s)
    return ps


def parse_class_xml(raw, path, url_base):
    root = ET.fromstring(raw)
    cls = root.get('name')
    page = url_base + 'class_' + cls.lower() + '.html'
    rows, examples = [], []
    desc = root.findtext('description') or ''
    brief = (root.findtext('brief_description') or '').strip()
    full = desc if desc.strip().startswith(brief) else brief + '\n' + desc
    rows.append({'class': cls, 'kind': 'class', 'name': cls, 'signature': f"class {cls}" + (f" extends {root.get('inherits')}" if root.get('inherits') else ''),
                 'type': None, 'inherits': root.get('inherits'),
                 'description': clean_bb(full),
                 'deprecated': clean_bb(root.get('deprecated')) or None, 'experimental': clean_bb(root.get('experimental')) or None,
                 'url': page})
    for code in bb_examples(desc):
        examples.append({'title': f'{cls} (descrizione classe)', 'language': 'gdscript', 'code': code,
                         'context': clean_bb(root.findtext('brief_description') or ''), 'url': page})

    def add(kind, el, sig, typ, akind=None):
        d = el.findtext('description') or ''
        if kind == 'operator':
            url = page                       # le ancore degli operatori dipendono dai tipi: si cita la pagina
        elif el.get('overrides'):            # proprietà ridefinita: la documentazione sta nella classe base
            base = el.get('overrides')
            url = url_base + 'class_' + base.lower() + '.html#' + anchor(base, akind or kind, el.get('name'))
        else:
            url = page + '#' + anchor(cls, akind or kind, el.get('name'))
        rows.append({'class': cls, 'kind': kind, 'name': el.get('name'), 'signature': sig, 'type': typ, 'inherits': None,
                     'description': clean_bb(d), 'deprecated': clean_bb(el.get('deprecated')) or None,
                     'experimental': clean_bb(el.get('experimental')) or None, 'url': url})
        for code in bb_examples(d):
            examples.append({'title': f"{cls}.{el.get('name')}", 'language': 'gdscript', 'code': code,
                             'context': clean_bb(d)[:400], 'url': url})

    for tag, kind in (('methods/method', 'method'), ('constructors/constructor', 'constructor'), ('operators/operator', 'operator')):
        for m in root.findall(tag):
            ret = m.find('return')
            rt = ret.get('type') if ret is not None else 'void'
            q = m.get('qualifiers') or ''
            sig = f"{('static ' if 'static' in q else '')}func {m.get('name')}({', '.join(params_sig(m))}{', ...' if 'vararg' in q else ''}) -> {rt}" + (f'  [{q}]' if q else '')
            add(kind, m, sig, rt)
    for m in root.findall('members/member'):
        sig = f"var {m.get('name')}: {m.get('type')}" + (f" = {m.get('default')}" if m.get('default') is not None else '')
        add('property', m, sig, m.get('type'))
    for s in root.findall('signals/signal'):
        add('signal', s, f"signal {s.get('name')}({', '.join(params_sig(s))})", None)
    for c in root.findall('constants/constant'):
        add('constant', c, f"{(c.get('enum') + '.') if c.get('enum') else ''}{c.get('name')} = {c.get('value')}", c.get('enum'))
    for a in root.findall('annotations/annotation'):
        add('annotation', a, f"{a.get('name')}({', '.join(params_sig(a))})", None)
    for t in root.findall('theme_items/theme_item'):
        add('theme_item', t, f"theme {t.get('data_type')} {t.get('name')}: {t.get('type')}", t.get('type'), 'theme-' + (t.get('data_type') or ''))
    enums = sorted({c.get('enum') for c in root.findall('constants/constant') if c.get('enum')})
    for e in enums:
        vals = [c.get('name') for c in root.findall('constants/constant') if c.get('enum') == e]
        rows.append({'class': cls, 'kind': 'enum', 'name': e, 'signature': f"enum {e} {{{', '.join(vals)}}}", 'type': None,
                     'inherits': None, 'description': '', 'deprecated': None, 'experimental': None,
                     'url': page + '#' + anchor(cls, 'enum', e)})
    return rows, examples


def parse_renames(raw):
    out, cat = [], None
    for line in raw.splitlines():
        m = re.match(r'const char \*RenamesMap3To4::(\w+)\[\]\[2\]', line)
        if m:
            cat = m.group(1); continue
        m = re.match(r'\s*\{\s*"([^"]*)",\s*"([^"]*)"\s*\}', line)
        if m and cat:
            out.append((cat, m.group(1), m.group(2)))
    return out


# ---------------------------------------------------------------- Demo ufficiali

def demo_context(root, rel):
    proj = Path(rel).parts[:2]
    ctx = '/'.join(proj)
    d = root.joinpath(*proj)
    pg = d / 'project.godot'
    if pg.exists():
        m = re.search(r'config/name="([^"]*)"', pg.read_text(errors='replace'))
        if m:
            ctx = m.group(1) + f' ({ctx})'
    rd = d / 'README.md'
    if rd.exists():
        ctx += ' — ' + re.sub(r'\s+', ' ', rd.read_text(errors='replace'))[:500]
    return ctx


# ---------------------------------------------------------------- indicizzazione

def delete_path(db, source, path):
    for table, fts in (('docs', 'docs_fts'), ('members', 'api_fts'), ('examples', 'examples_fts')):
        ids = [r[0] for r in db.execute(f'SELECT id FROM {table} WHERE source=? AND path=?', (source, path))]
        for i in ids:
            db.execute(f'DELETE FROM {fts} WHERE rowid=?', (i,))
        db.execute(f'DELETE FROM {table} WHERE source=? AND path=?', (source, path))
    if path.endswith('renames_map_3_to_4.cpp'):
        db.execute('DELETE FROM renames')
    db.execute('DELETE FROM files WHERE source=? AND path=?', (source, path))


def insert(db, table, fts, row, fts_cols):
    cols = list(row)
    cur = db.execute(f"INSERT INTO {table}({','.join(cols)}) VALUES({','.join('?' * len(cols))})", [row[c] for c in cols])
    db.execute(f"INSERT INTO {fts}(rowid,{','.join(fts_cols)}) VALUES(?{',?' * len(fts_cols)})",
               [cur.lastrowid] + [row.get(c) or '' for c in fts_cols])


_LABELS = {}


def published_labels(page):
    """Ancore presenti nella pagina classes/<page>.rst del manuale (None se la pagina non è nella cache)."""
    if page not in _LABELS:
        f = CACHE / 'godot-docs' / 'classes' / f'{page}.rst'
        _LABELS[page] = {slug(l) for l in re.findall(r'^\.\. _([^:]+):\s*$', f.read_text(errors='replace'), re.M)} if f.exists() else None
    return _LABELS[page]


def check_url(url):
    """Se il manuale pubblicato non ha l'ancora (membro aggiunto dopo l'ultima sincronizzazione delle pagine classi),
    si cita la pagina senza ancora invece di un link rotto."""
    page, _, anc = url.rsplit('/', 1)[1].partition('#')
    labels = published_labels(page[:-5])
    return url.split('#')[0] if anc and labels is not None and anc not in labels else url


def index_file(db, src, root, rel, raw):
    sid, base = src['id'], src['url_base']
    text = raw.decode('utf-8', errors='replace')
    if sid == 'godot-docs' and rel.endswith('.rst'):
        secs, exs = parse_rst(text, rel, base)
        for s in secs:
            insert(db, 'docs', 'docs_fts', {'source': sid, 'path': rel, **s}, ['title', 'section', 'body'])
        for e in exs:
            insert(db, 'examples', 'examples_fts', {'source': sid, 'path': rel, **e}, ['title', 'context', 'code'])
    elif sid == 'godot-class-reference' and rel.endswith('.xml'):
        rows, exs = parse_class_xml(text, rel, base)
        for r in rows:
            r['url'] = check_url(r['url'])
            insert(db, 'members', 'api_fts', {'source': sid, 'path': rel, **r}, ['class', 'name', 'signature', 'description'])
        for e in exs:
            insert(db, 'examples', 'examples_fts', {'source': sid, 'path': rel, **e}, ['title', 'context', 'code'])
    elif sid == 'godot-class-reference' and rel.endswith('renames_map_3_to_4.cpp'):
        db.execute('DELETE FROM renames')
        db.executemany('INSERT INTO renames VALUES(?,?,?)', parse_renames(text))
    elif sid == 'godot-demo-projects' and rel.endswith('.gd'):
        insert(db, 'examples', 'examples_fts', {'source': sid, 'path': rel, 'title': 'demo ' + rel, 'language': 'gdscript',
               'code': text, 'context': demo_context(root, rel), 'url': base + rel}, ['title', 'context', 'code'])
    elif sid == 'godot-demo-projects' and rel.endswith('README.md'):
        title = (text.strip().splitlines() or [rel])[0].lstrip('# ').strip()
        insert(db, 'docs', 'docs_fts', {'source': sid, 'path': rel, 'title': 'Demo: ' + title, 'section': title, 'anchor': '',
               'url': base + rel, 'body': text}, ['title', 'section', 'body'])


def build(full=False, db_path=INDEX):
    cfg = lock()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if full and db_path.exists():
        db_path.unlink()
    db = sqlite3.connect(db_path)
    db.executescript(SCHEMA)
    stats = {'saltati': 0, 'indicizzati': 0, 'rimossi': 0}
    t0 = time.time()
    for src in cfg['sources']:
        root = CACHE / src['id']
        if not root.exists():
            raise SystemExit(f"cache mancante: {root}. Eseguire prima acquire_docs.py")
        known = dict(db.execute('SELECT path, sha256 FROM files WHERE source=?', (src['id'],)).fetchall())
        seen = set()
        for p in sorted(root.rglob('*')):
            if '.git' in p.parts or not p.is_file():
                continue
            rel = p.relative_to(root).as_posix()
            if not selected(rel, src['include'], src['exclude']):
                continue
            raw = p.read_bytes()
            h = hashlib.sha256(raw).hexdigest()
            seen.add(rel)
            if known.get(rel) == h:
                stats['saltati'] += 1; continue
            if rel in known:
                delete_path(db, src['id'], rel)
            index_file(db, src, root, rel, raw)
            db.execute('INSERT OR REPLACE INTO files VALUES(?,?,?)', (src['id'], rel, h))
            stats['indicizzati'] += 1
        for rel in set(known) - seen:
            delete_path(db, src['id'], rel); stats['rimossi'] += 1
    meta = {'godot_version': cfg['godot_version'], 'docs_release': cfg['docs_release'],
            'commits': ';'.join(f"{s['id']}@{s['commit']}" for s in cfg['sources']),
            'docs_url': DOCS_URL, 'built_at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}
    db.executemany('INSERT OR REPLACE INTO meta VALUES(?,?)', meta.items())
    db.commit()
    for fts in ('docs_fts', 'api_fts', 'examples_fts'):
        db.execute(f"INSERT INTO {fts}({fts}) VALUES('optimize')")
    db.commit()
    db.execute('VACUUM')
    db.close()
    stats['secondi'] = round(time.time() - t0, 1)
    return stats


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--full', action='store_true', help='ricostruisce da zero')
    a = ap.parse_args()
    print(build(a.full))
