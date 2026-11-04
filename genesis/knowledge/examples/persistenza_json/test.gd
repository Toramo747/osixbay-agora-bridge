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
	if typeof(d) != TYPE_DICTIONARY or int(d.get("version", 0)) != 1:
		return {}
	var chunks := {}
	for key: String in d.chunks:
		var p := key.split(",")
		chunks[Vector2i(int(p[0]), int(p[1]))] = Marshalls.base64_to_raw(d.chunks[key])
	return {"seed": int(d.seed), "tick": int(d.tick), "chunks": chunks}


func _init() -> void:
	DirAccess.make_dir_recursive_absolute(DIR)
	var state := {"seed": 42, "tick": 1200, "chunks": {Vector2i(-3, 7): PackedByteArray([1, 2, 3]), Vector2i(0, 0): PackedByteArray([5])}}
	# salvataggio atomico: scrivi su file temporaneo e poi rinomina
	var f := FileAccess.open(DIR + "/world.json.tmp", FileAccess.WRITE)
	f.store_string(world_to_json(state))
	f.close()
	DirAccess.rename_absolute(DIR + "/world.json.tmp", DIR + "/world.json")
	var loaded := world_from_json(FileAccess.get_file_as_string(DIR + "/world.json"))
	var ok: bool = loaded.seed == 42 and loaded.tick == 1200 and loaded.chunks[Vector2i(-3, 7)] == PackedByteArray([1, 2, 3])
	# formato binario con tipi Godot conservati
	var bin := var_to_bytes(state)
	var back: Dictionary = bytes_to_var(bin)
	ok = ok and back.chunks.has(Vector2i(-3, 7)) and typeof(back.tick) == TYPE_INT
	ok = ok and world_from_json("{\"version\": 99}").is_empty()     # versione sconosciuta rifiutata
	DirAccess.remove_absolute(DIR + "/world.json")
	DirAccess.remove_absolute(DIR)
	print("byte JSON: ", world_to_json(state).length(), " byte binari: ", bin.size())
	print("EXAMPLE_OK" if ok else "EXAMPLE_FAIL")
	quit(0 if ok else 1)
