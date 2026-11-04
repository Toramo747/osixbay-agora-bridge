#!/usr/bin/env python3
"""Rapporto di copertura: quanto del corpus selezionato è nell'indice, per fonte e per area richiesta.
Scrive knowledge/reports/coverage.json e coverage.md. Tutti i numeri sono contati dall'indice reale.

Uso:  python3 genesis/tools/coverage_report.py
"""
import datetime, sqlite3, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import CACHE, INDEX, KNOWLEDGE, REPORTS, dump_json, load_json, lock, selected  # noqa: E402

# area richiesta -> (prefissi di percorso nel manuale, classi chiave). Le aree senza guida ufficiale sono dichiarate.
AREE = [
    ('1. GDScript', ['tutorials/scripting/gdscript/'], ['@GDScript', 'GDScript']),
    ('2. Classi e API', [], []),
    ('3. Nodi, scene, segnali, risorse', ['getting_started/step_by_step/', 'tutorials/scripting/nodes_and_scene_instances', 'tutorials/scripting/resources', 'tutorials/scripting/scene_tree', 'tutorials/scripting/groups'], ['Node', 'PackedScene', 'Resource', 'Signal']),
    ('4. Rendering 2D, TileMapLayer, sprite, animazioni', ['tutorials/2d/', 'tutorials/animation/'], ['TileMapLayer', 'Sprite2D', 'AnimatedSprite2D', 'AnimationPlayer']),
    ('5. Generazione procedurale', ['tutorials/math/random_number_generation'], ['FastNoiseLite', 'RandomNumberGenerator', 'Noise']),
    ('6. Coordinate e mondi estesi', ['tutorials/physics/large_world_coordinates', 'tutorials/2d/2d_transforms', 'tutorials/math/vector_math'], ['Vector2i', 'Transform2D']),
    ('7. Navigazione e pathfinding', ['tutorials/navigation/'], ['AStarGrid2D', 'NavigationAgent2D', 'NavigationServer2D']),
    ('8. Simulazione di agenti ed entità', ['tutorials/performance/using_servers', 'tutorials/scripting/idle_and_physics_processing'], ['WorkerThreadPool']),
    ('9. Fisica e collisioni', ['tutorials/physics/'], ['CharacterBody2D', 'Area2D', 'PhysicsDirectSpaceState2D']),
    ('10. Inventario, risorse, economia', ['tutorials/scripting/resources', 'tutorials/best_practices/data_preferences'], ['Resource', 'Dictionary']),
    ('11. Persistenza', ['tutorials/io/'], ['FileAccess', 'JSON', 'ResourceSaver', 'ConfigFile']),
    ('12. Networking e multiplayer', ['tutorials/networking/'], ['MultiplayerAPI', 'ENetMultiplayerPeer', 'MultiplayerSynchronizer']),
    ('13. Ottimizzazione e prestazioni', ['tutorials/performance/'], ['RenderingServer', 'MultiMesh']),
    ('14. Riga di comando e headless', ['tutorials/editor/command_line_tutorial', 'tutorials/export/exporting_for_dedicated_servers'], ['OS', 'DisplayServer']),
    ('15. Test, debug, validazione', ['tutorials/scripting/debug/', 'tutorials/scripting/logging'], ['EngineDebugger']),
    ('16. Esportazione e distribuzione', ['tutorials/export/'], ['EditorExportPlugin']),
    ('17. Esempi ufficiali', [], []),
    ('Extra: formati, JSON, serializzazione', ['tutorials/io/binary_serialization_api', 'tutorials/io/saving_games', 'engine_details/file_formats/'], ['JSON', 'Marshalls']),
]
LACUNE = {
    '8. Simulazione di agenti ed entità': 'nessuna guida ufficiale dedicata alla simulazione di molti agenti: coperta da catalogo Genesis + esempio simulazione_batch',
    '10. Inventario, risorse, economia': 'Godot non ha sistemi nativi di inventario o economia: solo Resource/Dictionary; da sviluppare (catalogo)',
    '15. Test, debug, validazione': 'Godot non offre un framework nativo di unit test per i progetti GDScript: si usano script headless (come examples/) o addon di terze parti non acquisiti',
}


def main():
    db = sqlite3.connect(INDEX)
    cfg = lock()
    rep = {'godot_version': cfg['godot_version'], 'generato_il': datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat(),
           'fonti': {}, 'aree': [], 'indice_byte': INDEX.stat().st_size}
    for src in cfg['sources']:
        root = CACHE / src['id']
        sel = [p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file() and '.git' not in p.parts
               and selected(p.relative_to(root).as_posix(), src['include'], src['exclude'])]
        idx = {r[0] for r in db.execute('SELECT path FROM files WHERE source=?', (src['id'],))}
        content = set()
        for t in ('docs', 'members', 'examples'):
            content |= {r[0] for r in db.execute(f'SELECT DISTINCT path FROM {t} WHERE source=?', (src['id'],))}
        content |= {p for p in idx if p.endswith('renames_map_3_to_4.cpp')} if db.execute('SELECT count(*) FROM renames').fetchone()[0] else set()
        useful = [p for p in sel if not p.endswith('project.godot')]      # project.godot: solo contesto dei demo
        rep['fonti'][src['id']] = {'file_selezionati': len(sel), 'file_registrati': len(idx), 'file_con_contenuto': len(content & set(useful)),
                                  'file_contenuto_attesi': len(useful), 'copertura_pct': round(100 * len(content & set(useful)) / max(len(useful), 1), 1),
                                  'byte_cache': sum((root / p).stat().st_size for p in sel)}
    q = lambda s, *a: db.execute(s, a).fetchone()[0]  # noqa: E731
    rep['conteggi'] = {
        'sezioni_manuale': q("SELECT count(*) FROM docs WHERE source='godot-docs'"),
        'pagine_manuale': q("SELECT count(DISTINCT path) FROM docs WHERE source='godot-docs'"),
        'readme_demo': q("SELECT count(*) FROM docs WHERE source='godot-demo-projects'"),
        'classi': q("SELECT count(*) FROM members WHERE kind='class'"),
        'metodi': q("SELECT count(*) FROM members WHERE kind='method'"),
        'membri_per_tipo': dict(db.execute("SELECT kind, count(*) FROM members WHERE kind!='class' GROUP BY kind").fetchall()),
        'api_deprecate': q('SELECT count(*) FROM members WHERE deprecated IS NOT NULL'),
        'api_sperimentali': q('SELECT count(*) FROM members WHERE experimental IS NOT NULL'),
        'esempi_totali': q('SELECT count(*) FROM examples'),
        'esempi_gdscript': q("SELECT count(*) FROM examples WHERE language LIKE 'gdscript%'"),
        'esempi_per_fonte': dict(db.execute('SELECT source, count(*) FROM examples GROUP BY source').fetchall()),
        'rinomine_godot3': q('SELECT count(*) FROM renames'),
    }
    val = REPORTS / 'examples-validation.json'
    if val.exists():
        v = load_json(val)
        rep['conteggi']['esempi_locali_eseguiti_ok'] = f"{v['superati']}/{v['totale']}"
    for name, prefixes, classes in AREE:
        if name.startswith('2.'):
            pages, sec = 0, 0
            note = f"{rep['conteggi']['classi']} classi dal riferimento XML"
        elif name.startswith('17.'):
            pages = q("SELECT count(DISTINCT path) FROM examples WHERE source='godot-demo-projects'")
            sec, note = 0, f'{pages} script .gd dei demo ufficiali'
        else:
            cond = ' OR '.join('path LIKE ?' for _ in prefixes)
            args = [p + '%' for p in prefixes]
            pages = q(f"SELECT count(DISTINCT path) FROM docs WHERE source='godot-docs' AND ({cond})", *args)
            sec = q(f"SELECT count(*) FROM docs WHERE source='godot-docs' AND ({cond})", *args)
            note = ''
        found = [c for c in classes if q("SELECT count(*) FROM members WHERE kind='class' AND name=?", c)]
        rep['aree'].append({'area': name, 'pagine': pages, 'sezioni': sec, 'classi_chiave_presenti': found,
                            'classi_chiave_mancanti': sorted(set(classes) - set(found)), 'nota': note, 'lacuna': LACUNE.get(name)})
    dump_json(REPORTS / 'coverage.json', rep)
    c = rep['conteggi']
    md = [f"# Copertura della biblioteca — Godot {rep['godot_version']}", '', f"Generato il {rep['generato_il']} dall'indice reale.", '',
          '## Per fonte', '', '| fonte | file selezionati | file con contenuto indicizzato | copertura | byte |', '|---|---|---|---|---|']
    for k, s in rep['fonti'].items():
        md.append(f"| {k} | {s['file_selezionati']} | {s['file_con_contenuto']}/{s['file_contenuto_attesi']} | {s['copertura_pct']}% | {s['byte_cache']} |")
    md += ['', '## Conteggi', '']
    md += [f'- {k}: {v}' for k, v in c.items()]
    md += [f"- dimensione indice SQLite: {rep['indice_byte']} byte", '', '## Aree richieste', '',
           '| area | pagine | sezioni | classi chiave | note / lacune |', '|---|---|---|---|---|']
    for a in rep['aree']:
        extra = '; '.join(x for x in (a['nota'], a['lacuna'] or '', ('mancano: ' + ', '.join(a['classi_chiave_mancanti'])) if a['classi_chiave_mancanti'] else '') if x)
        md.append(f"| {a['area']} | {a['pagine']} | {a['sezioni']} | {', '.join(a['classi_chiave_presenti'])} | {extra} |")
    (REPORTS / 'coverage.md').write_text('\n'.join(md) + '\n', encoding='utf-8')
    print(json_summary(rep))


def json_summary(rep):
    return {k: v['copertura_pct'] for k, v in rep['fonti'].items()} | {'classi': rep['conteggi']['classi'], 'metodi': rep['conteggi']['metodi']}


if __name__ == '__main__':
    main()
