## Memoria spaziale di un agente: chunk esplorati, punti notevoli, percezione in un raggio.
## Interamente codice aggiuntivo (Godot non ha un sistema nativo di "memoria" per agenti);
## usa solo tipi nativi: Dictionary con chiavi Vector2i, Rect2i.
class_name AgentMemory
extends RefCounted

const CHUNK_SIZE := 32

var explored := {}        # Vector2i chunk -> tick della prima esplorazione
var landmarks := {}       # Vector2i cella -> String descrizione


## Percezione: restituisce i chunk entro il raggio (in celle) e li registra come esplorati.
func perceive(cell: Vector2i, radius: int, tick: int) -> Array[Vector2i]:
	var seen: Array[Vector2i] = []
	var r := Rect2i(cell - Vector2i(radius, radius), Vector2i(radius * 2 + 1, radius * 2 + 1))
	var c0 := Vector2i(floori(r.position.x / float(CHUNK_SIZE)), floori(r.position.y / float(CHUNK_SIZE)))
	var c1 := Vector2i(floori(r.end.x / float(CHUNK_SIZE)), floori(r.end.y / float(CHUNK_SIZE)))
	for cy in range(c0.y, c1.y + 1):
		for cx in range(c0.x, c1.x + 1):
			var k := Vector2i(cx, cy)
			if not explored.has(k):
				explored[k] = tick
				seen.append(k)
	return seen


func remember(cell: Vector2i, what: String) -> void:
	landmarks[cell] = what


func nearest_landmark(from: Vector2i, what: String) -> Variant:
	var best: Variant = null
	var best_d := INF
	for cell: Vector2i in landmarks:
		if landmarks[cell] == what:
			var d := Vector2(cell - from).length_squared()
			if d < best_d:
				best_d = d
				best = cell
	return best


## Serializzazione per la persistenza (JSON-safe).
func to_dict() -> Dictionary:
	var e := {}
	for k: Vector2i in explored:
		e["%d,%d" % [k.x, k.y]] = explored[k]
	var l := {}
	for k: Vector2i in landmarks:
		l["%d,%d" % [k.x, k.y]] = landmarks[k]
	return {"explored": e, "landmarks": l}
