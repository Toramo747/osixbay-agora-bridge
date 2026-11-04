# Esempi di interrogazione

Output reale di `genesis/tools/search_docs.py` (rendering `to_text`, troncato a 2500 caratteri; gli esempi di codice a 900).

```text
GODOT: cerca generazione procedurale rumore
```

```text
[GODOT 4.6.3-stable] cerca: generazione procedurale rumore
The random number generation shown above can show its limits when you need a value that *slowly* changes depending on the input. The input can be a position, time, or anything else. To achieve this, you can use random *noise* functions. Noise functions are especially popular in procedural generation to generate realistic-looking terrain. Godot provides fastnoiselite for this, which supports 1D, 2D and 3D noise. Here's an example with 1D noise: var _noise = FastNoiseLite.new() func _ready(): # Configure the FastNoiseLite instance. _noise.noise_type = FastNoiseLite.NoiseType.TYPE_SIMPLEX_SMOOTH _noise.seed = randi() _noise.fractal_octaves = 4 _noise.frequency = 1.0 / 20.0 for i in 100: # …
Fonti: Random number generation — Random noise <https://docs.godotengine.org/en/4.6/tutorials/math/random_number_generation.html#random-noise> ; Demo: Procedural Materials — Procedural Materials <https://github.com/godotengine/godot-demo-projects/blob/52f6a4fa6efe7be4e441d69437bf856a9bdbac51/3d/procedural_materials/README.md> ; Volumetric fog and fog volumes — Using 3D noise density textures <https://docs.godotengine.org/en/4.6/tutorials/3d/volumetric_fog.html#using-3d-noise-density-textures> ; Noise <https://docs.godotengine.org/en/4.6/classes/class_noise.html>
Alternative: Demo: Procedural Materials — Procedural Materials, Volumetric fog and fog volumes — Using 3D noise density textures, Noise
Verifica: documentazione ufficiale Godot (estratto citato)
```

```text
GODOT: classe AStarGrid2D
```

```text
[GODOT 4.6.3-stable] classe: AStarGrid2D
An implementation of A* for finding the shortest path between two points on a partial 2D grid. AStarGrid2D is a variant of AStar2D that is specialized for partial 2D grids. It is simpler to use because it doesn't require you to manually create points and connect them together. This class also supports multiple types of heuristics, modes for diagonal movement, and a jumping mode to speed up calculations. To use AStarGrid2D, you only need to set the region of the grid, optionally set the cell_size, and then call the update method: [vedi esempio] To remove a point from the pathfinding grid, it must be set as "solid" with set_point_solid.
Fonti: AStarGrid2D <https://docs.godotengine.org/en/4.6/classes/class_astargrid2d.html>
Verifica: riferimento classi ufficiale (XML del motore)
```

```text
GODOT: metodo TileMapLayer.set_cell
```

```text
[GODOT 4.6.3-stable] metodo: TileMapLayer.set_cell
Sets the tile identifiers for the cell at coordinates coords. Each tile of the TileSet is identified using three parts: - The source identifier source_id identifies a TileSetSource identifier. See TileSet.set_source_id, - The atlas coordinate identifier atlas_coords identifies a tile coordinates in the atlas (if the source is a TileSetAtlasSource). For TileSetScenesCollectionSource it should always be Vector2i(0, 0), - The alternative tile identifier alternative_tile identifies a tile alternative in the atlas (if the source is a TileSetAtlasSource), and the scene for a TileSetScenesCollectionSource. If source_id is set to -1, atlas_coords to Vector2i(-1, -1), or alternative_tile to -1, the cell will be erased. An erased cell gets all its identifiers automatically set to their respective invalid values, namely -1, Vector2i(-1, -1) and -1.
- TileMapLayer: func set_cell(coords: Vector2i, source_id: int = -1, atlas_coords: Vector2i = Vector2i(-1, -1), alternative_tile: int = 0) -> void
Fonti: TileMapLayer.set_cell <https://docs.godotengine.org/en/4.6/classes/class_tilemaplayer.html#class-tilemaplayer-method-set-cell>
Verifica: riferimento classi ufficiale (XML del motore)
```

```text
GODOT: esempio salvataggio json
```

```text
[GODOT 4.6.3-stable] esempio: salvataggio json
1 esempi locali e 5 esempi ufficiali pertinenti.
Fonti: demo loading/serialization/save_load_json.gd <https://github.com/godotengine/godot-demo-projects/blob/52f6a4fa6efe7be4e441d69437bf856a9bdbac51/loading/serialization/save_load_json.gd> ; Saving games — Saving and reading data <https://docs.godotengine.org/en/4.6/tutorials/io/saving_games.html#saving-and-reading-data> ; demo 3d/voxel/settings.gd <https://github.com/godotengine/godot-demo-projects/blob/52f6a4fa6efe7be4e441d69437bf856a9bdbac51/3d/voxel/settings.gd> ; esempio locale persistenza_json <genesis/knowledge/examples/persistenza_json/>
Esempio (esempio eseguito con Godot headless in questa biblioteca):
extends SceneTree
## Persistenza dello stato del mondo: JSON per dati leggibili e var_to_bytes per dati compatti.
## Nativo: FileAccess, JSON.stringify/parse_string, var_to_bytes/bytes_to_var, DirAccess.
## Attenzione (documentazione): JSON non conosce Vector2i, int e float si confondono (i numeri tornano float):
## serve una conversione esplicita. var_to_bytes conserva i tipi Godot; non usare bytes_to_var_with_objects
## su dati non fidati.

const DIR := "user://genesis_test_save"


func world_to_json(state: Dictionary) -> String:
	var chunks := {}
	for k: Vector2i in state.chunks:
		chunks["%d,%d" % [k.x, k.y]] = Marshalls.raw_to_base64(state.chunks[k])
	return JSON.stringify({"version": 1, "seed": state.seed, "tick": state.tick, "chunks": chunks})


func world_from_json(text: String) -> Dictionary:
	var d: Variant = JSON.parse_string(text)
	if typeof(d) != TYPE_DICTIONARY or int(d.get
Alternative: Saving games — Saving and reading data, demo 3d/voxel/settings.gd, Saving games — Saving and reading data
Verifica: esempio eseguito con Godot headless in questa biblioteca
```

```text
GODOT: progetta caricamento del terreno a chunk
```

```text
[GODOT 4.6.3-stable] progetta: caricamento del terreno a chunk
Caricamento del terreno a chunk. Supportato da Godot: TileMapLayer.set_cell (scrittura di una cella (TileMap è deprecato: usare TileMapLayer)); TileMapLayer.erase_cell (scaricare un chunk = cancellarne le celle); TileMapLayer.set_cells_terrain_connect (terreni con transizioni automatiche); WorkerThreadPool.add_task (generazione dei chunk fuori dal thread principale); ResourceLoader.load_threaded_request (caricamento di risorse in background). Da realizzare con codice aggiuntivo: gestore dei chunk attivi attorno agli osservatori (agenti) con raggio di caricamento e isteresi; le coordinate serializzate da TileMapLayer sono interi a 16 bit con segno (-32768..32767): per un mondo più ampio usare più TileMapLayer con origine propria o tenere solo i chunk vicini.
Limitazioni: ipotesi da sperimentare: un TileMapLayer per chunk contro un unico layer condiviso: confrontare i tempi di aggiornamento
Fonti: Using TileMaps <https://docs.godotengine.org/en/4.6/tutorials/2d/using_tilemaps.html> ; Background loading <https://docs.godotengine.org/en/4.6/tutorials/io/background_loading.html> ; Using multiple threads <https://docs.godotengine.org/en/4.6/tutorials/performance/using_multiple_threads.html> ; Thread-safe APIs <https://docs.godotengine.org/en/4.6/tutorials/performance/thread_safe_apis.html>
Alternative: Generazione procedurale del mondo
Verifica: catalogo progettuale Genesis: riferimenti verificati, soluzione da sviluppare
```

```text
GODOT: verifica extends KinematicBody2D
onready var s = $Sprite
func _ready():
	yield(get_tree(), "idle_frame")

```

```text
[GODOT 4.6.3-stable] verifica: extends KinematicBody2D onready var s = $Sprite func _ready(): yield(get_tree(), "idle_frame")
4 problemi rilevati. Il codice NON è stato eseguito: un esito positivo non garantisce il comportamento a runtime.
- problema sintassi_godot3: yield è stato rimosso in Godot 4: usare await (es. await get_tree().process_frame)
- problema sintassi_godot3: onready var → @onready var
- problema classe_inesistente: KinematicBody2D nome Godot 3: in 4.x è CharacterBody2D
- problema errore_parsing_godot: The "onready" keyword was removed in Godot 4. Use the "@onready" annotation instead.
Fonti: Upgrading from Godot 3 to Godot 4 <https://docs.godotengine.org/en/4.6/tutorials/migrating/upgrading_to_godot_4.html>
Verifica: analisi statica + parsing Godot headless --check-only isolato (codice non eseguito)
```

```text
GODOT: compatibilità TileMap
```

```text
[GODOT 4.6.3-stable] compatibilità: TileMap
TileMap: deprecata in Godot 4.6.3-stable. Use multiple TileMapLayer nodes instead. To convert a TileMap to a set of TileMapLayer nodes, open the TileMap bottom panel with the node selected, click the toolbox icon in the top-right corner and choose 'Extract TileMap layers as individual TileMapLayer nodes'.
Limitazioni: Use multiple TileMapLayer nodes instead. To convert a TileMap to a set of TileMapLayer nodes, open the TileMap bottom panel with the node selected, click the toolbox icon in the top-right corner and choose 'Extract TileMap layers as individual TileMapLayer nodes'.
Fonti: TileMap <https://docs.godotengine.org/en/4.6/classes/class_tilemap.html>
Verifica: riferimento classi ufficiale (XML del motore)
```

```text
GODOT: compatibilità KinematicBody2D
```

```text
[GODOT 4.6.3-stable] compatibilità: KinematicBody2D
KinematicBody2D non esiste in Godot 4.6.3-stable: nome di Godot 3 rinominato in CharacterBody2D (tabella class_renames).
Limitazioni: fonte: renames_map_3_to_4.cpp del convertitore ufficiale
Alternative: CharacterBody2D
Verifica: riferimento classi ufficiale (XML del motore)
```

```text
GODOT: metodo Node.teleport_to_mars
```

```text
[GODOT 4.6.3-stable] metodo: Node.teleport_to_mars
NON TROVATO. Node.teleport_to_mars non è presente nel riferimento di Godot 4.6.3-stable nella classe Node (né nelle sue classi base).
Verifica: nessuna fonte nell'indice: risposta non disponibile
```
