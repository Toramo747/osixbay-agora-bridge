# Copertura della biblioteca — Godot 4.7.2-stable

Generato il 2026-11-04T08:40:37+00:00 dall'indice reale.

## Per fonte

| fonte | file selezionati | file con contenuto indicizzato | copertura | byte |
|---|---|---|---|---|
| godot-docs | 516 | 516/516 | 100.0% | 5624024 |
| godot-class-reference | 1079 | 1079/1079 | 100.0% | 9487585 |
| godot-demo-projects | 731 | 599/599 | 100.0% | 1475260 |

## Conteggi

- sezioni_manuale: 4113
- pagine_manuale: 516
- readme_demo: 148
- classi: 1078
- metodi: 10732
- membri_per_tipo: {'annotation': 36, 'constant': 6012, 'constructor': 154, 'enum': 793, 'method': 10732, 'operator': 351, 'property': 6999, 'signal': 503, 'theme_item': 635}
- api_deprecate: 476
- api_sperimentali: 14
- esempi_totali: 3120
- esempi_gdscript: 1850
- esempi_per_fonte: {'godot-class-reference': 790, 'godot-demo-projects': 451, 'godot-docs': 1879}
- rinomine_godot3: 1593
- esempi_locali_eseguiti_ok: 8/8
- dimensione indice SQLite: 47124480 byte

## Aree richieste

| area | pagine | sezioni | classi chiave | note / lacune |
|---|---|---|---|---|
| 1. GDScript | 9 | 185 | @GDScript, GDScript |  |
| 2. Classi e API | 0 | 0 |  | 1078 classi dal riferimento XML |
| 3. Nodi, scene, segnali, risorse | 11 | 70 | Node, PackedScene, Resource, Signal |  |
| 4. Rendering 2D, TileMapLayer, sprite, animazioni | 23 | 278 | TileMapLayer, Sprite2D, AnimatedSprite2D, AnimationPlayer |  |
| 5. Generazione procedurale | 1 | 10 | FastNoiseLite, RandomNumberGenerator, Noise |  |
| 6. Coordinate e mondi estesi | 3 | 36 | Vector2i, Transform2D |  |
| 7. Navigazione e pathfinding | 19 | 63 | AStarGrid2D, NavigationAgent2D, NavigationServer2D |  |
| 8. Simulazione di agenti ed entità | 2 | 8 | WorkerThreadPool | nessuna guida ufficiale dedicata alla simulazione di molti agenti: coperta da catalogo Genesis + esempio simulazione_batch |
| 9. Fisica e collisioni | 20 | 151 | CharacterBody2D, Area2D, PhysicsDirectSpaceState2D |  |
| 10. Inventario, risorse, economia | 2 | 12 | Resource, Dictionary | Godot non ha sistemi nativi di inventario o economia: solo Resource/Dictionary; da sviluppare (catalogo) |
| 11. Persistenza | 6 | 66 | FileAccess, JSON, ResourceSaver, ConfigFile |  |
| 12. Networking e multiplayer | 7 | 42 | MultiplayerAPI, ENetMultiplayerPeer, MultiplayerSynchronizer |  |
| 13. Ottimizzazione e prestazioni | 13 | 102 | RenderingServer, MultiMesh |  |
| 14. Riga di comando e headless | 2 | 17 | OS, DisplayServer |  |
| 15. Test, debug, validazione | 8 | 73 | EngineDebugger | Godot non offre un framework nativo di unit test per i progetti GDScript: si usano script headless (come examples/) o addon di terze parti non acquisiti |
| 16. Esportazione e distribuzione | 16 | 128 | EditorExportPlugin |  |
| 17. Esempi ufficiali | 451 | 0 |  | 451 script .gd dei demo ufficiali |
| Extra: formati, JSON, serializzazione | 4 | 61 | JSON, Marshalls |  |
