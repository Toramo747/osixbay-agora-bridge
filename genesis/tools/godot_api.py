"""Interfaccia della biblioteca per il futuro agente genesis-godot (non ancora creato né attivato).

Comandi:
  GODOT: cerca <argomento>        ricerca nel manuale, nell'API e negli esempi
  GODOT: classe <nome>            scheda di una classe (ereditarietà, membri, stato)
  GODOT: metodo <nome|Classe.nome> metodo/proprietà/segnale/costante, con firma
  GODOT: esempio <funzione>       esempi GDScript (validati in locale, del manuale, dei demo ufficiali)
  GODOT: progetta <componente>    voce del catalogo Genesis + API e documenti verificati
  GODOT: verifica <codice>        analisi statica (API inesistenti/obsolete, sintassi Godot 3) e,
                                  se disponibile, parsing isolato con Godot headless --check-only
  GODOT: compatibilità <API>      esistenza nella versione fissata, deprecazione, rinomina da Godot 3

Ogni risposta è un dizionario con: operazione, richiesta, trovato, versione_godot, spiegazione,
riferimenti, esempio, limitazioni, livello_verifica, alternative. Se la documentazione non contiene la
risposta, trovato=False e lo si dichiara: nessuna invenzione. La risposta testuale (to_text) è
limitata in lunghezza: all'agente arriva solo l'estratto pertinente, mai l'intera documentazione.
"""
import difflib, json, re, sqlite3, sys, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import CATALOG, EXAMPLES, INDEX, REPORTS, load_json  # noqa: E402

LIVELLI = {
    'documentazione': 'documentazione ufficiale Godot (estratto citato)',
    'api': 'riferimento classi ufficiale (XML del motore)',
    'eseguito': 'esempio eseguito con Godot headless in questa biblioteca',
    'ufficiale_non_eseguito': 'esempio ufficiale, non eseguito da noi',
    'catalogo': 'catalogo progettuale Genesis: riferimenti verificati, soluzione da sviluppare',
    'statica': 'analisi statica sull\'indice (nessuna esecuzione)',
    'parsing': 'analisi statica + parsing Godot headless --check-only isolato (codice non eseguito)',
    'non_trovato': 'nessuna fonte nell\'indice: risposta non disponibile',
}

# Glossario minimo italiano -> inglese: la documentazione è in inglese, i residenti scrivono in italiano.
GLOSSARIO = {
    'salvataggio': 'save', 'salvare': 'save', 'caricare': 'load', 'caricamento': 'loading', 'percorso': 'path',
    'mappa': 'map', 'mappe': 'map', 'generazione': 'generation', 'procedurale': 'procedural', 'rumore': 'noise',
    'segnale': 'signal', 'segnali': 'signals', 'nodo': 'node', 'nodi': 'nodes', 'scena': 'scene', 'scene': 'scene',
    'risorsa': 'resource', 'risorse': 'resources', 'fisica': 'physics', 'collisione': 'collision',
    'collisioni': 'collisions', 'navigazione': 'navigation', 'ostacoli': 'obstacles', 'ostacolo': 'obstacle',
    'rete': 'network', 'multigiocatore': 'multiplayer', 'ottimizzazione': 'optimization', 'prestazioni': 'performance',
    'memoria': 'memory', 'thread': 'thread', 'animazione': 'animation', 'animazioni': 'animations', 'tessere': 'tiles',
    'mattonelle': 'tiles', 'terreno': 'terrain', 'esportazione': 'export', 'esportare': 'export', 'terminale': 'command line',
    'riga': 'line', 'comando': 'command', 'comandi': 'command', 'test': 'test', 'debug': 'debug', 'variabili': 'variables',
    'variabile': 'variable', 'funzione': 'function', 'funzioni': 'functions', 'classe': 'class', 'classi': 'classes',
    'ereditarietà': 'inheritance', 'tipizzazione': 'typing', 'tipi': 'types', 'coordinate': 'coordinates',
    'mondo': 'world', 'grande': 'large', 'esteso': 'large', 'telecamera': 'camera', 'input': 'input', 'file': 'file',
    'sprite': 'sprite', 'movimento': 'movement', 'agente': 'agent', 'agenti': 'agents', 'casuale': 'random',
    'numeri': 'number', 'server': 'server', 'serializzazione': 'serialization', 'inventario': 'inventory',
    'oggetti': 'objects', 'griglia': 'grid', 'evitamento': 'avoidance', 'sicurezza': 'security', 'eventi': 'events',
}
STOP = set('il lo la i gli le un una uno di da in con su per tra fra e o a al del della dei delle come cosa quale '
           'quali posso si fa fare usare uso the a an of to in on for with how what is are do does use using and or'.split())
GODOT3_SYNTAX = [
    (r'\byield\s*\(', 'yield è stato rimosso in Godot 4: usare await (es. await get_tree().process_frame)', 'yield'),
    (r'^\s*onready\s+var\b', 'onready var → @onready var', 'onready'),
    (r'^\s*export(\s*\(|\s+var\b)', 'export var → @export var (con @export_range ecc. per i suggerimenti)', 'export'),
    (r'^\s*tool\s*$', 'tool → @tool', 'tool'),
    (r'\bsetget\b', 'setget rimosso: usare la sintassi var x: set = ..., get = ...', 'setget'),
    (r'(?:^|[^\w])connect\(\s*"[^"]+"\s*,\s*self\s*,', 'connect("segnale", self, "metodo") → segnale.connect(metodo) (Callable)', 'connect'),
    (r'^\s*(remote|master|puppet|remotesync|mastersync|puppetsync)\s+func\b', 'parole chiave di rete Godot 3 → annotazione @rpc', 'rpc'),
]


def _tokens(text):
    out = []
    for t in re.findall(r'[\w@]+', text.lower()):
        if t in STOP or len(t) < 2:
            continue
        out.append(GLOSSARIO.get(t, t))
    return [w for t in out for w in t.split()]


def _fts(tokens, mode='AND'):
    return f' {mode} '.join('"' + t.replace('"', '') + '"' for t in tokens)


def _short(text, n=600):
    text = re.sub(r'\s+', ' ', text or '').strip()
    return text if len(text) <= n else text[:n].rsplit(' ', 1)[0] + ' …'


class GodotLibrary:
    def __init__(self, index=INDEX, catalog=CATALOG):
        if not Path(index).exists():
            raise FileNotFoundError(f'indice assente: {index}. Eseguire acquire_docs.py e build_index.py')
        self.db = sqlite3.connect(f'file:{index}?mode=ro', uri=True)
        self.db.row_factory = sqlite3.Row
        self.meta = dict(self.db.execute('SELECT key, value FROM meta').fetchall())
        self.version = self.meta.get('godot_version', '?')
        self.catalog = load_json(catalog) if Path(catalog).exists() else {'voci': []}
        val = REPORTS / 'examples-validation.json'
        self.validated = {r['esempio']: r for r in load_json(val)['risultati']} if val.exists() else {}
        self._classes = {r['name'].lower(): r['name'] for r in self.db.execute("SELECT name FROM members WHERE kind='class'")}

    # ------------------------------------------------------------ utilità
    def _resp(self, op, query, trovato, spiegazione, riferimenti=(), esempio=None, limitazioni=(), livello='non_trovato',
              alternative=(), **extra):
        r = {'operazione': op, 'richiesta': query, 'trovato': trovato, 'versione_godot': self.version,
             'spiegazione': spiegazione, 'riferimenti': list(riferimenti), 'esempio': esempio,
             'limitazioni': list(limitazioni), 'livello_verifica': livello, 'livello_descrizione': LIVELLI[livello],
             'alternative': list(alternative)}
        r.update(extra)
        return r

    def _ref(self, titolo, url, fonte):
        return {'titolo': titolo, 'url': url, 'fonte': fonte, 'versione': self.version}

    def class_name(self, name):
        return self._classes.get((name or '').strip().lower())

    def chain(self, cls):
        out = []
        while cls and cls not in out:
            out.append(cls)
            row = self.db.execute("SELECT inherits FROM members WHERE kind='class' AND name=?", (cls,)).fetchone()
            cls = row['inherits'] if row else None
        return out

    def find_member(self, cls, name):
        """Membro di una classe, cercato anche nelle classi base (es. FastNoiseLite.get_noise_2d è in Noise)."""
        for c in self.chain(cls):
            row = self.db.execute("SELECT * FROM members WHERE class=? AND name=? AND kind!='class'", (c, name)).fetchone()
            if row:
                return row
        return None

    def renamed_from_godot3(self, name, categories=None):
        q = 'SELECT category, old, new FROM renames WHERE old=?'
        rows = self.db.execute(q, (name,)).fetchall()
        return [dict(r) for r in rows if not categories or r['category'] in categories]

    def _search_docs(self, tokens, limit=5):
        for mode in ('AND', 'OR'):
            if not tokens:
                return []
            rows = self.db.execute(
                'SELECT d.*, bm25(docs_fts, 6.0, 4.0, 1.0) AS score FROM docs_fts JOIN docs d ON d.id = docs_fts.rowid '
                'WHERE docs_fts MATCH ? ORDER BY score LIMIT ?', (_fts(tokens, mode), limit)).fetchall()
            if rows:
                return rows
        return []

    def _search_api(self, tokens, limit=5):
        for mode in ('AND', 'OR'):
            if not tokens:
                return []
            rows = self.db.execute(
                'SELECT m.*, bm25(api_fts, 8.0, 8.0, 2.0, 1.0) AS score FROM api_fts JOIN members m ON m.id = api_fts.rowid '
                "WHERE api_fts MATCH ? ORDER BY (m.kind='class') DESC, score LIMIT ?", (_fts(tokens, mode), limit * 3)).fetchall()
            if rows:
                rows = sorted(rows, key=lambda r: r['score'])[:limit]
                return rows
        return []

    def _local_examples(self, tokens):
        out = []
        for d in sorted(p for p in EXAMPLES.iterdir() if (p / 'test.gd').exists()):
            text = '\n'.join(f.read_text() for f in sorted(d.glob('*.gd'), key=lambda f: (f.name == 'test.gd', f.name)))
            hay = (d.name + ' ' + text).lower()
            score = sum(hay.count(t) for t in tokens)
            if score and all(t in hay for t in tokens[:2]):
                v = self.validated.get(d.name, {})
                out.append({'id': d.name, 'score': score, 'codice': text, 'funzionante': v.get('funzionante', False),
                            'path': f'genesis/knowledge/examples/{d.name}/'})
        return sorted(out, key=lambda e: -e['score'])

    # ------------------------------------------------------------ operazioni
    def cerca(self, query):
        toks = _tokens(query)
        docs, api = self._search_docs(toks), self._search_api(toks, 3)
        if not docs and not api:
            return self._resp('cerca', query, False, 'La documentazione indicizzata non contiene risultati per questa richiesta.',
                              alternative=['riformulare in inglese o con il nome di una classe Godot'])
        refs = [self._ref(f"{d['title']} — {d['section']}" if d['section'] != d['title'] else d['title'], d['url'], d['source'])
                for d in docs]
        refs += [self._ref(f"{a['class']}.{a['name']}" if a['kind'] != 'class' else a['class'], a['url'], 'godot-class-reference')
                 for a in api]
        top = docs[0] if docs else None
        spieg = _short(top['body'], 700) if top else _short(api[0]['description'], 700)
        lim = [f"API deprecata: {a['class']}.{a['name']} — {a['deprecated']}" for a in api if a['deprecated']]
        ex = self.esempio(query, _limit=1)
        attach = ex['trovato'] and ex.get('corrispondenza') in ('locale', 'completa')
        return self._resp('cerca', query, True, spieg, refs, ex['esempio'] if attach else None, lim,
                          'documentazione' if top else 'api', [r['titolo'] for r in refs[1:4]])

    def classe(self, name):
        cls = self.class_name(name)
        if not cls:
            ren = self.renamed_from_godot3(name.strip(), {'class_renames'})
            sugg = difflib.get_close_matches(name.strip(), list(self._classes.values()), n=3, cutoff=0.75)
            if ren:
                new = ren[0]['new']
                return self._resp('classe', name, False, f'{name} non esiste in Godot {self.version}: è un nome di Godot 3, '
                                  f'rinominato in {new}.', limitazioni=['rinomina ufficiale dal convertitore di progetto 3→4'],
                                  livello='api', alternative=[new], rinominata_in=new)
            return self._resp('classe', name, False, f'La classe {name} non esiste nel riferimento di Godot {self.version}.',
                              alternative=sugg)
        row = self.db.execute("SELECT * FROM members WHERE kind='class' AND name=?", (cls,)).fetchone()
        counts = dict(self.db.execute('SELECT kind, count(*) FROM members WHERE class=? AND kind!="class" GROUP BY kind', (cls,)).fetchall())
        names = {k: [r[0] for r in self.db.execute('SELECT name FROM members WHERE class=? AND kind=? ORDER BY name', (cls, k))]
                 for k in ('method', 'property', 'signal')}
        lim = []
        if row['deprecated']:
            lim.append('CLASSE DEPRECATA: ' + row['deprecated'])
        if row['experimental']:
            lim.append('CLASSE SPERIMENTALE: ' + row['experimental'])
        demos = [r['path'] for r in self.db.execute(
            "SELECT path FROM examples WHERE source='godot-demo-projects' AND id IN "
            "(SELECT rowid FROM examples_fts WHERE examples_fts MATCH ?) LIMIT 3", (f'"{cls}"',))]
        return self._resp('classe', name, True, _short(row['description'], 900),
                          [self._ref(cls, row['url'], 'godot-class-reference')], None, lim, 'api',
                          [], ereditarieta=self.chain(cls), conteggi=counts,
                          metodi=names['method'][:60], proprieta=names['property'][:60], segnali=names['signal'],
                          demo_ufficiali=demos)

    def metodo(self, query):
        q = query.strip().rstrip('()')
        cls, _, name = q.rpartition('.') if '.' in q else ('', '', q)
        if cls:
            c = self.class_name(cls)
            row = self.find_member(c, name) if c else None
            rows = [row] if row else []
        else:
            rows = self.db.execute("SELECT * FROM members WHERE name=? AND kind!='class' ORDER BY "
                                   "(deprecated IS NOT NULL), class LIMIT 12", (name,)).fetchall()
        if not rows:
            ren = self.renamed_from_godot3(name, {'gdscript_function_renames', 'gdscript_properties_renames', 'gdscript_signals_renames'})
            if ren:
                return self._resp('metodo', query, False, f'{name} non esiste in Godot {self.version}: in Godot 3 è stato '
                                  f"rinominato in {ren[0]['new']}.", livello='api', alternative=[r['new'] for r in ren],
                                  limitazioni=['la rinomina vale nel contesto delle classi interessate: verificare la classe'])
            allnames = [r[0] for r in self.db.execute("SELECT DISTINCT name FROM members WHERE kind IN ('method','property','signal')")]
            sugg = difflib.get_close_matches(name, allnames, n=4, cutoff=0.8)
            where = f' nella classe {cls} (né nelle sue classi base)' if cls else ''
            return self._resp('metodo', query, False, f'{q} non è presente nel riferimento di Godot {self.version}{where}.',
                              alternative=sugg)
        first = rows[0]
        lim = [f"DEPRECATO ({r['class']}.{r['name']}): {r['deprecated']}" for r in rows if r['deprecated']]
        lim += [f"SPERIMENTALE ({r['class']}.{r['name']}): {r['experimental']}" for r in rows if r['experimental']]
        if len(rows) > 1:
            lim.append(f'nome presente in {len(rows)} classi: specificare Classe.{name}')
        ex = next((e for e in self.db.execute(
            "SELECT * FROM examples WHERE source='godot-class-reference' AND title=?", (f"{first['class']}.{first['name']}",))), None)
        return self._resp('metodo', query, True, _short(first['description'], 900),
                          [self._ref(f"{r['class']}.{r['name']}", r['url'], 'godot-class-reference') for r in rows],
                          {'codice': ex['code'], 'fonte': ex['url'], 'stato': LIVELLI['ufficiale_non_eseguito']} if ex else None,
                          lim, 'api', [f"{r['class']}.{r['name']}" for r in rows[1:]],
                          firme=[{'classe': r['class'], 'tipo': r['kind'], 'firma': r['signature']} for r in rows])

    def esempio(self, query, _limit=3):
        toks = _tokens(query)
        if not toks:
            return self._resp('esempio', query, False, 'Richiesta vuota.')
        local = self._local_examples(toks)
        rows, mode_used = [], None
        for mode in ('AND', 'OR'):
            mode_used = mode
            rows = self.db.execute(
                "SELECT e.*, bm25(examples_fts, 6.0, 0.5, 3.0) AS score FROM examples_fts JOIN examples e ON e.id = examples_fts.rowid "
                "WHERE examples_fts MATCH ? AND e.language LIKE 'gdscript%' ORDER BY score LIMIT ?",
                (_fts(toks, mode), _limit + 10)).fetchall()
            # il codice deve contenere i termini richiesti, non solo il README del demo
            rows = [r for r in rows if all(t in (r['code'] + r['title']).lower() for t in toks[:2])][:_limit + 2]
            if rows:
                break
        if not local and not rows:
            return self._resp('esempio', query, False, 'Nessun esempio GDScript nell\'indice per questa richiesta.')
        if local:
            e = local[0]
            ok = e['funzionante']
            esempio = {'codice': e['codice'], 'fonte': e['path'],
                       'stato': LIVELLI['eseguito'] if ok else 'esempio locale NON validato (validazione assente o fallita)'}
            livello = 'eseguito' if ok else 'statica'
        else:
            e0 = rows[0]
            esempio = {'codice': e0['code'], 'fonte': e0['url'], 'stato': LIVELLI['ufficiale_non_eseguito']}
            livello = 'ufficiale_non_eseguito'
        refs = [self._ref(r['title'], r['url'], r['source']) for r in rows[:_limit]]
        refs += [self._ref(f"esempio locale {x['id']}", x['path'], 'genesis-examples') for x in local[:2]]
        return self._resp('esempio', query, True, f"{len(local)} esempi locali e {len(rows)} esempi ufficiali pertinenti.",
                          refs, esempio, [] if livello == 'eseguito' else ['esempio non eseguito in questa biblioteca'],
                          livello, [r['title'] for r in rows[1:_limit + 1]],
                          corrispondenza='locale' if local else ('completa' if mode_used == 'AND' else 'parziale'))

    def progetta(self, componente):
        toks = set(_tokens(componente)) | {t for t in re.findall(r'\w+', componente.lower()) if t not in STOP}
        scored = []
        for v in self.catalog.get('voci', []):
            kw = {k.lower() for k in v['parole_chiave']} | set(re.findall(r'\w+', v['titolo'].lower())) - STOP
            s = len(toks & kw)
            if s:
                scored.append((s, v))
        if not scored:
            base = self.cerca(componente)
            base.update(operazione='progetta', limitazioni=base['limitazioni'] + ['nessuna voce nel catalogo Genesis: solo risultati documentali'])
            return base
        scored.sort(key=lambda x: -x[0])
        v = scored[0][1]
        supp = []
        for s in v['supportato_godot']:
            c, _, m = s['api'].partition('.')
            cls = self.class_name(c)
            row = (self.find_member(cls, m) if m else self.db.execute("SELECT * FROM members WHERE kind='class' AND name=?", (cls,)).fetchone()) if cls else None
            supp.append({'api': s['api'], 'nota': s['nota'], 'verificata': bool(row), 'firma': row['signature'] if row else None,
                         'url': row['url'] if row else None, 'deprecata': row['deprecated'] if row else None})
        refs = [self._ref(d['title'], d['url'], 'godot-docs') for p in v['doc']
                for d in self.db.execute('SELECT title, url FROM docs WHERE path=? ORDER BY id LIMIT 1', (p,))]
        esempi = [{'id': e, 'percorso': f'genesis/knowledge/examples/{e}/',
                   'stato': LIVELLI['eseguito'] if self.validated.get(e, {}).get('funzionante') else 'non validato'}
                  for e in v['esempi']]
        spieg = (f"{v['titolo']}. Supportato da Godot: " + '; '.join(f"{s['api']} ({s['nota']})" for s in supp) +
                 '. Da realizzare con codice aggiuntivo: ' + '; '.join(v['codice_aggiuntivo']) + '.')
        return self._resp('progetta', componente, True, spieg, refs, esempi[0] if esempi else None,
                          v.get('limitazioni', []) + [f'ipotesi da sperimentare: {h}' for h in v['ipotesi']],
                          'catalogo', [x[1]['titolo'] for x in scored[1:3]],
                          voce=v['id'], supportato_godot=supp, codice_aggiuntivo=v['codice_aggiuntivo'],
                          ipotesi=v['ipotesi'], esempi=esempi)

    def verifica(self, code, parse_with_godot=True):
        problems, notes = [], []
        own_funcs = set(re.findall(r'^\s*(?:static\s+)?func\s+(\w+)', code, re.M))
        own_classes = set(re.findall(r'^\s*(?:class_name|class)\s+(\w+)', code, re.M))
        own_vars = set(re.findall(r'^\s*(?:@\w+\s+)*(?:var|const)\s+(\w+)', code, re.M))
        for pat, msg, _ in GODOT3_SYNTAX:
            if re.search(pat, code, re.M):
                problems.append({'tipo': 'sintassi_godot3', 'dettaglio': msg})
        types = set(re.findall(r'\bextends\s+([A-Z]\w*)', code)) | set(re.findall(r'(?::|->)\s*([A-Z]\w*)', code)) \
            | set(re.findall(r'\b([A-Z]\w*)\.new\(', code)) | set(re.findall(r'\b(?:is|as)\s+([A-Z]\w*)', code))
        for t in sorted(types - own_classes):
            if t in ('Array', 'Dictionary') or self.class_name(t) == t:
                row = self.db.execute("SELECT deprecated FROM members WHERE kind='class' AND name=?", (t,)).fetchone()
                if row and row['deprecated']:
                    problems.append({'tipo': 'classe_deprecata', 'nome': t, 'dettaglio': row['deprecated']})
                continue
            ren = self.renamed_from_godot3(t, {'class_renames', 'builtin_types_renames'})
            problems.append({'tipo': 'classe_inesistente', 'nome': t,
                             'dettaglio': f"nome Godot 3: in 4.x è {ren[0]['new']}" if ren else 'non presente nel riferimento'})
        calls = set(re.findall(r'\.(\w+)\s*\(', code)) - own_funcs
        for m in sorted(calls):
            rows = self.db.execute("SELECT class, deprecated FROM members WHERE name=? AND kind IN ('method','constructor')", (m,)).fetchall()
            if not rows:
                ren = self.renamed_from_godot3(m, {'gdscript_function_renames'})
                if ren:
                    problems.append({'tipo': 'metodo_godot3', 'nome': m, 'dettaglio': f"in 4.x: {ren[0]['new']}"})
                elif m not in own_vars:
                    notes.append(f'.{m}() non è un metodo del motore: corretto solo se definito in un altro script')
            elif all(r['deprecated'] for r in rows):
                problems.append({'tipo': 'metodo_deprecato', 'nome': m, 'dettaglio': rows[0]['deprecated']})
        livello, parse = 'statica', None
        if parse_with_godot:
            try:
                from godot_runner import run_godot
                r = run_godot({'check.gd': code}, 'check.gd', check_only=True, timeout=30)
                if r.get('eseguito'):
                    errs = [l.strip() for l in r['output'].splitlines() if 'Parse Error' in l or 'SCRIPT ERROR' in l]
                    parse = {'exit_code': r['exit_code'], 'errori': errs[:10], 'isolamento_rete': r['isolamento_rete']}
                    livello = 'parsing'
                    for e in errs:
                        if 'Parse Error' in e:
                            problems.append({'tipo': 'errore_parsing_godot', 'dettaglio': e.split('Parse Error:', 1)[-1].strip()})
                else:
                    notes.append(r.get('motivo', 'Godot non disponibile'))
            except Exception as exc:     # l'analisi statica resta valida anche se il parsing non è possibile
                notes.append(f'parsing Godot non eseguito: {exc}')
        ok = not problems
        spieg = ('Nessun problema rilevato.' if ok else f'{len(problems)} problemi rilevati.') + \
            ' Il codice NON è stato eseguito: un esito positivo non garantisce il comportamento a runtime.'
        refs = [self._ref('Upgrading from Godot 3 to Godot 4', self.meta.get('docs_url', 'https://docs.godotengine.org/en/stable') + '/tutorials/migrating/upgrading_to_godot_4.html', 'godot-docs')] \
            if any(p['tipo'] in ('sintassi_godot3', 'metodo_godot3') for p in problems) else []
        return self._resp('verifica', _short(code, 120), True, spieg, refs, None, notes, livello, [],
                          valido=ok, problemi=problems, parsing=parse)

    def compatibilita(self, api):
        a = api.strip().rstrip('()')
        c, _, m = a.partition('.')
        cls = self.class_name(c)
        if cls and not m:
            row = self.db.execute("SELECT * FROM members WHERE kind='class' AND name=?", (cls,)).fetchone()
            stato = 'deprecata' if row['deprecated'] else ('sperimentale' if row['experimental'] else 'disponibile')
            note = [x for x in (row['deprecated'], row['experimental']) if x]
            return self._resp('compatibilità', api, True, f'{cls}: {stato} in Godot {self.version}.' + (' ' + note[0] if note else ''),
                              [self._ref(cls, row['url'], 'godot-class-reference')], None, note, 'api', [], stato=stato)
        if cls and m:
            row = self.find_member(cls, m)
            if row:
                stato = 'deprecata' if row['deprecated'] else ('sperimentale' if row['experimental'] else 'disponibile')
                note = [x for x in (row['deprecated'], row['experimental']) if x]
                return self._resp('compatibilità', api, True,
                                  f"{row['class']}.{row['name']}: {stato} in Godot {self.version}. Firma: {row['signature']}",
                                  [self._ref(f"{row['class']}.{row['name']}", row['url'], 'godot-class-reference')], None,
                                  note, 'api', [], stato=stato)
        name = m or c
        ren = self.renamed_from_godot3(name)
        if ren:
            return self._resp('compatibilità', api, True,
                              f"{name} non esiste in Godot {self.version}: nome di Godot 3 rinominato in {ren[0]['new']} "
                              f"(tabella {ren[0]['category']}).", [], None,
                              ['fonte: renames_map_3_to_4.cpp del convertitore ufficiale'], 'api',
                              sorted({r['new'] for r in ren}), stato='rinominata_da_godot3')
        return self._resp('compatibilità', api, False, f'{api} non è presente in Godot {self.version} e non risulta tra le '
                          'rinomine ufficiali da Godot 3.', stato='inesistente',
                          alternative=difflib.get_close_matches(name, list(self._classes.values()), n=3, cutoff=0.8))

    # ------------------------------------------------------------ comando testuale
    OPS = {'cerca': 'cerca', 'classe': 'classe', 'metodo': 'metodo', 'esempio': 'esempio', 'progetta': 'progetta',
           'verifica': 'verifica', 'compatibilità': 'compatibilita', 'compatibilita': 'compatibilita'}

    def handle(self, line):
        t0 = time.perf_counter()
        m = re.match(r'^\s*GODOT:\s*(\S+)\s*(.*)$', line, re.S | re.I)
        if not m or m.group(1).lower() not in self.OPS:
            r = self._resp('sconosciuta', line, False, 'Comando non riconosciuto. Forme: ' +
                           ', '.join(f'GODOT: {k} <...>' for k in ('cerca', 'classe', 'metodo', 'esempio', 'progetta', 'verifica', 'compatibilità')))
        elif not m.group(2).strip():
            r = self._resp(m.group(1).lower(), '', False, 'Argomento mancante.')
        else:
            r = getattr(self, self.OPS[m.group(1).lower()])(m.group(2).strip())
        r['tempo_ms'] = round((time.perf_counter() - t0) * 1000, 1)
        return r


def to_text(r, budget=2500):
    """Rendering compatto per il contesto di un agente (lunghezza limitata)."""
    out = [f"[GODOT {r['versione_godot']}] {r['operazione']}: {r['richiesta']}",
           ('' if r['trovato'] else 'NON TROVATO. ') + r['spiegazione']]
    for k in ('firme',):
        for f in r.get(k, [])[:4]:
            out.append(f"- {f['classe']}: {f['firma']}")
    for p in r.get('problemi', [])[:8]:
        out.append(f"- problema {p['tipo']}: {p.get('nome', '')} {p['dettaglio']}".replace('  ', ' '))
    if r['limitazioni']:
        out.append('Limitazioni: ' + ' | '.join(r['limitazioni'][:4]))
    if r['riferimenti']:
        out.append('Fonti: ' + ' ; '.join(f"{x['titolo']} <{x['url']}>" for x in r['riferimenti'][:4]))
    if r.get('esempio') and r['esempio'].get('codice'):
        out.append(f"Esempio ({r['esempio']['stato']}):\n" + r['esempio']['codice'][:900])
    if r['alternative']:
        out.append('Alternative: ' + ', '.join(map(str, r['alternative'][:5])))
    out.append(f"Verifica: {r['livello_descrizione']}")
    text = '\n'.join(out)
    return text if len(text) <= budget else text[:budget - 2] + ' …'


if __name__ == '__main__':
    from search_docs import main
    sys.exit(main())
