extends SceneTree
## Pathfinding su griglia con AStarGrid2D (nativo, Godot 4.0+): ostacoli, pesi, diagonali.

func _init() -> void:
	var grid := AStarGrid2D.new()
	grid.region = Rect2i(0, 0, 20, 12)
	grid.cell_size = Vector2(16, 16)
	grid.diagonal_mode = AStarGrid2D.DIAGONAL_MODE_ONLY_IF_NO_OBSTACLES
	grid.update()
	# un muro verticale con un varco in basso
	for y in range(0, 10):
		grid.set_point_solid(Vector2i(10, y))
	# terreno costoso (palude) che il percorso tende a evitare
	grid.set_point_weight_scale(Vector2i(5, 11), 8.0)
	var path := grid.get_id_path(Vector2i(2, 2), Vector2i(17, 2))
	var ok := not path.is_empty()
	ok = ok and path[0] == Vector2i(2, 2) and path[-1] == Vector2i(17, 2)
	for p in path:
		ok = ok and not grid.is_point_solid(p)
	ok = ok and (Vector2i(10, 10) in path or Vector2i(10, 11) in path)   # passa dal varco
	var world := grid.get_point_path(Vector2i(2, 2), Vector2i(3, 2))
	ok = ok and world.size() == 2 and world[1] == Vector2(48, 32)
	# destinazione irraggiungibile: percorso vuoto
	grid.set_point_solid(Vector2i(10, 10))
	grid.set_point_solid(Vector2i(10, 11))
	ok = ok and grid.get_id_path(Vector2i(2, 2), Vector2i(17, 2)).is_empty()
	print("lunghezza percorso: ", path.size())
	print("EXAMPLE_OK" if ok else "EXAMPLE_FAIL")
	quit(0 if ok else 1)
