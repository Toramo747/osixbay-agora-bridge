extends SceneTree

const AgentMemory = preload("agent_memory.gd")


func _init() -> void:
	var m := AgentMemory.new()
	var first := m.perceive(Vector2i(0, 0), 10, 1)
	var again := m.perceive(Vector2i(1, 1), 10, 2)
	var ok := first.size() == 4 and again.is_empty()       # (-1,-1),(0,-1),(-1,0),(0,0)
	ok = ok and m.explored[Vector2i(-1, -1)] == 1
	m.remember(Vector2i(50, 5), "acqua")
	m.remember(Vector2i(-4, 2), "acqua")
	m.remember(Vector2i(1, 1), "pietra")
	ok = ok and m.nearest_landmark(Vector2i(0, 0), "acqua") == Vector2i(-4, 2)
	ok = ok and m.nearest_landmark(Vector2i(0, 0), "oro") == null
	var d := m.to_dict()
	ok = ok and JSON.parse_string(JSON.stringify(d)).explored.has("-1,-1")
	print("EXAMPLE_OK" if ok else "EXAMPLE_FAIL")
	quit(0 if ok else 1)
