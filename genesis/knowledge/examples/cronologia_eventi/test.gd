extends SceneTree
## Cronologia del mondo come registro append-only in formato JSON Lines (una riga JSON per evento).
## Nativo: FileAccess (READ_WRITE + seek_end), JSON. Da sviluppare: schema degli eventi, rotazione file.
## Append-only = la storia non si riscrive; si ricostruisce lo stato rileggendo gli eventi.

const PATH := "user://genesis_test_chronicle.jsonl"


func append_event(ev: Dictionary) -> void:
	var f: FileAccess
	if FileAccess.file_exists(PATH):
		f = FileAccess.open(PATH, FileAccess.READ_WRITE)
		f.seek_end()
	else:
		f = FileAccess.open(PATH, FileAccess.WRITE)
	f.store_line(JSON.stringify(ev))
	f.close()


func read_events(since_tick: int = 0) -> Array:
	var out := []
	var f := FileAccess.open(PATH, FileAccess.READ)
	while not f.eof_reached():
		var line := f.get_line()
		if line.is_empty():
			continue
		var ev: Variant = JSON.parse_string(line)
		if ev is Dictionary and int(ev.tick) >= since_tick:
			out.append(ev)
	return out


func _init() -> void:
	if FileAccess.file_exists(PATH):
		DirAccess.remove_absolute(PATH)
	append_event({"tick": 1, "agente": "a1", "tipo": "esplora", "chunk": [0, 0]})
	append_event({"tick": 5, "agente": "a2", "tipo": "costruisce", "cella": [3, -2], "oggetto": "riparo"})
	append_event({"tick": 9, "agente": "a1", "tipo": "scopre", "risorsa": "acqua"})
	var all := read_events()
	var recent := read_events(5)
	var ok: bool = all.size() == 3 and recent.size() == 2 and recent[0].tipo == "costruisce"
	DirAccess.remove_absolute(PATH)
	print("EXAMPLE_OK" if ok else "EXAMPLE_FAIL")
	quit(0 if ok else 1)
