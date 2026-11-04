extends SceneTree
## Verifica: determinismo per seed, chunk di coordinate negative, varietà dei biomi.

const WorldGenerator = preload("world_generator.gd")


func _init() -> void:
	var ok := true
	var a := WorldGenerator.new(42)
	var b := WorldGenerator.new(42)
	var c := WorldGenerator.new(7)
	ok = ok and a.generate_chunk(Vector2i(3, -5)) == b.generate_chunk(Vector2i(3, -5))
	ok = ok and a.generate_chunk(Vector2i(0, 0)) != c.generate_chunk(Vector2i(0, 0))
	ok = ok and WorldGenerator.cell_to_chunk(Vector2i(-1, -33)) == Vector2i(-1, -2)
	ok = ok and WorldGenerator.cell_to_chunk(Vector2i(31, 32)) == Vector2i(0, 1)
	var seen := {}
	for cy in range(-6, 6):
		for cx in range(-6, 6):
			for v in a.generate_chunk(Vector2i(cx, cy)):
				seen[v] = true
	ok = ok and seen.size() >= 3
	print("biomi distinti su 144 chunk: ", seen.size())
	print("EXAMPLE_OK" if ok else "EXAMPLE_FAIL")
	quit(0 if ok else 1)
