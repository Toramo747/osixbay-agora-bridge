"""Test della biblioteca genesis-godot.

Senza corpus: parser (RST, XML, rinomine) e utilità, su input sintetici.
Con indice costruito: domande di controllo, catalogo, ancore delle URL, aggiornamento incrementale.
Con binario Godot: esecuzione degli esempi in headless.

Uso:  python3 -m unittest discover -s genesis/knowledge/tests -v
"""
import re, sqlite3, sys, tempfile, unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[2] / 'tools'
sys.path.insert(0, str(TOOLS))
import build_index as bi  # noqa: E402
from common import CACHE, CATALOG, EXAMPLES, INDEX, glob_to_re, godot_binary, load_json, selected  # noqa: E402

HAS_INDEX = INDEX.exists()


class Parsers(unittest.TestCase):
    def test_glob(self):
        self.assertTrue(glob_to_re('**/*.rst').match('a/b/c.rst'))
        self.assertTrue(glob_to_re('**/*.rst').match('c.rst'))
        self.assertFalse(glob_to_re('doc/classes/*.xml').match('doc/classes/x/y.xml'))
        self.assertTrue(selected('tutorials/a.rst', ['**/*.rst'], ['classes/**']))
        self.assertFalse(selected('classes/class_node.rst', ['**/*.rst'], ['classes/**']))

    def test_rst_sections_and_code(self):
        raw = ('.. _doc_x:\n\nTitolo\n======\n\nIntro :ref:`Node <class_Node>` testo.\n\nSezione Due\n-----------\n\n'
               'Usa ``set_cell``.\n\n.. code-block:: gdscript\n\n    func f():\n        pass\n\nFine.\n')
        secs, exs = bi.parse_rst(raw, 'tutorials/x.rst', 'https://d/')
        self.assertEqual([s['section'] for s in secs], ['Titolo', 'Sezione Due'])
        self.assertIn('Node', secs[0]['body'])
        self.assertNotIn(':ref:', secs[0]['body'])
        self.assertTrue(secs[1]['url'].endswith('tutorials/x.html#sezione-due'))
        self.assertEqual(exs[0]['language'], 'gdscript')
        self.assertEqual(exs[0]['code'], 'func f():\n    pass')

    def test_class_xml(self):
        xml = ('<class name="Foo" inherits="Node" deprecated="Use [Bar] instead."><brief_description>Brief.</brief_description>'
               '<description>Brief. Long [code]x[/code].\n[codeblocks][gdscript]\n\tvar a = 1\n[/gdscript][csharp]int a;[/csharp][/codeblocks]</description>'
               '<methods><method name="go" qualifiers="const"><return type="int"/><param index="0" name="n" type="int" default="2"/>'
               '<description>Go.</description></method><method name="_virt" qualifiers="virtual"><return type="void"/><description/></method></methods>'
               '<members><member name="speed" type="float" default="1.0" overrides="Node">S</member></members>'
               '<signals><signal name="done"><param index="0" name="ok" type="bool"/><description/></signal></signals></class>')
        rows, exs = bi.parse_class_xml(xml, 'doc/classes/Foo.xml', 'https://d/classes/')
        by = {(r['kind'], r['name']): r for r in rows}
        self.assertEqual(by[('class', 'Foo')]['deprecated'], 'Use Bar instead.')
        self.assertEqual(by[('method', 'go')]['signature'], 'func go(n: int = 2) -> int  [const]')
        self.assertTrue(by[('method', 'go')]['url'].endswith('class_foo.html#class-foo-method-go'))
        self.assertTrue(by[('method', '_virt')]['url'].endswith('#class-foo-private-method-virt'))
        self.assertTrue(by[('property', 'speed')]['url'].endswith('class_node.html#class-node-property-speed'))
        self.assertEqual(by[('signal', 'done')]['signature'], 'signal done(ok: bool)')
        self.assertEqual(exs[0]['code'], 'var a = 1')
        self.assertEqual(by[('class', 'Foo')]['description'].count('Brief.'), 1)

    def test_renames(self):
        src = 'const char *RenamesMap3To4::class_renames[][2] = {\n\t{ "KinematicBody2D", "CharacterBody2D" },\n\t{ nullptr, nullptr },\n};'
        self.assertEqual(bi.parse_renames(src), [('class_renames', 'KinematicBody2D', 'CharacterBody2D')])


@unittest.skipUnless(HAS_INDEX, 'indice assente: eseguire acquire_docs.py e build_index.py')
class Library(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from godot_api import GodotLibrary
        cls.lib = GodotLibrary()

    def test_control_questions(self):
        import run_checks
        results = run_checks.run()
        self.assertGreaterEqual(len(results), 30)
        self.assertGreaterEqual(sum(r['categoria'].startswith('negativo') for r in results), 8)
        failed = [(r['id'], r['errori']) for r in results if not r['superato']]
        self.assertEqual(failed, [])

    def test_evaluator_detects_wrong_answers(self):
        import run_checks
        res = self.lib.handle('GODOT: classe TileMapLayer')
        errs, _ = run_checks.evaluate(res, {'trovato': False, 'url': 'class_tilemap.html#nope'}, self.lib.version)
        self.assertEqual(len(errs), 2)

    def test_catalog_references_exist(self):
        cat = load_json(CATALOG)
        self.assertGreaterEqual(len(cat['voci']), 12)
        for v in cat['voci']:
            for key in ('supportato_godot', 'codice_aggiuntivo', 'ipotesi'):
                self.assertIn(key, v)
            for s in v['supportato_godot']:
                c, _, m = s['api'].partition('.')
                cls = self.lib.class_name(c)
                self.assertIsNotNone(cls, s['api'])
                if m:
                    self.assertIsNotNone(self.lib.find_member(cls, m), s['api'])
            for d in v['doc']:
                self.assertTrue(self.lib.db.execute('SELECT 1 FROM docs WHERE path=?', (d,)).fetchone(), d)
            for e in v['esempi']:
                self.assertTrue((EXAMPLES / e / 'test.gd').exists(), e)

    def test_api_urls_match_official_class_pages(self):
        """Ogni URL dell'API deve puntare a una pagina e a un'ancora che esistono nelle pagine ufficiali generate."""
        root = CACHE / 'godot-docs' / 'classes'
        if not root.exists():
            self.skipTest('pagine classes/ assenti nella cache')
        ids, pages = set(), {p.stem for p in root.glob('*.rst')}
        for p in root.glob('*.rst'):
            for lab in re.findall(r'^\.\. _([^:]+):\s*$', p.read_text(errors='replace'), re.M):
                ids.add((p.stem, bi.slug(lab)))
        bad = []
        for (url,) in self.lib.db.execute('SELECT url FROM members'):
            page, _, anc = url.rsplit('/', 1)[1].partition('#')
            page = page[:-5]
            if page not in pages or (anc and (page, anc) not in ids):
                bad.append(url)
        self.assertEqual(bad[:5], [])

    def test_incremental_rebuild_is_noop(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / 'copy.sqlite'
            db.write_bytes(INDEX.read_bytes())
            stats = bi.build(False, db)
            self.assertEqual((stats['indicizzati'], stats['rimossi']), (0, 0))

    def test_incremental_removes_vanished_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / 'copy.sqlite'
            db_path.write_bytes(INDEX.read_bytes())
            db = sqlite3.connect(db_path)
            db.execute("INSERT INTO files VALUES('godot-docs','sparito.rst','x')")
            db.execute("INSERT INTO docs(source,path,title,section,anchor,url,body) VALUES('godot-docs','sparito.rst','t','t','','u','b')")
            db.commit(); db.close()
            stats = bi.build(False, db_path)
            self.assertEqual(stats['rimossi'], 1)
            db = sqlite3.connect(db_path)
            self.assertEqual(db.execute("SELECT count(*) FROM docs WHERE path='sparito.rst'").fetchone()[0], 0)

    def test_answers_are_bounded(self):
        from godot_api import to_text
        for cmd in ('GODOT: classe Node', 'GODOT: cerca navigation', 'GODOT: progetta persistenza'):
            self.assertLessEqual(len(to_text(self.lib.handle(cmd))), 2500)


@unittest.skipUnless(HAS_INDEX and godot_binary(), 'binario Godot assente: acquire_docs.py --with-godot')
class Examples(unittest.TestCase):
    def test_examples_run_headless(self):
        import validate_examples
        results = validate_examples.validate()
        self.assertGreaterEqual(len(results), 8)
        self.assertEqual([r['esempio'] for r in results if not r['funzionante']], [])


if __name__ == '__main__':
    unittest.main()
