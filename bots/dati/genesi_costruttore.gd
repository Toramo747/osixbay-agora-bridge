extends Node
const D := __DIR__
const K := __K__
var n := FastNoiseLite.new()
var s := 0

func _ready():
	var g: Dictionary = Mondo.dati.get("genesi", {})
	if not g.has("seme"):
		g = {"seme": randi() % 999999, "chunk": {}, "tot": {}, "passi": 0}
	s = int(g.seme)
	n.seed = s
	var c := ["0,0"] if g.chunk.is_empty() else []
	for k in g.chunk:
		for o in [Vector2i.RIGHT, Vector2i.LEFT, Vector2i.DOWN, Vector2i.UP]:
			var q = "%d,%d" % [vi(k).x + o.x, vi(k).y + o.y]
			if not g.chunk.has(q) and not q in c:
				c.append(q)
	c.sort_custom(func(a, b): return voto(a) > voto(b))
	var nuovi = c.slice(0, K)
	for k in nuovi:
		g.chunk[k] = conta(vi(k))
		for b in g.chunk[k]:
			g.tot[b] = int(g.tot.get(b, 0)) + int(g.chunk[k][b])
	g.passi = int(g.passi) + 1
	Mondo.dati["genesi"] = g
	Mondo.racconta("GENESI " + JSON.stringify({"passo": g.passi, "chunk": g.chunk.size(), "nuovi": nuovi, "totali": g.tot}))

func vi(k):
	var p = k.split(",")
	return Vector2i(int(p[0]), int(p[1]))

func voto(k):
	var v = Vector2(vi(k))
	return v.dot(Vector2(D)) - v.length() * 0.5

func conta(p):
	var c = {}
	for y in 32:
		for x in 32:
			var w = p * 32 + Vector2i(x, y)
			var h = n.get_noise_2d(w.x, w.y)
			var m = n.get_noise_2d(w.x * 0.4 + 5e3, w.y * 0.4)
			var b = "oceano" if h < -0.2 else "spiaggia" if h < -0.12 else "montagna" if h > 0.45 else "foresta" if m > 0.05 else "deserto" if m < -0.3 else "prateria"
			c[b] = c.get(b, 0) + 1
			if (hash(w) + s) % 97 == 0:
				var r = {"oceano": "pesce", "montagna": "pietra", "foresta": "legno"}.get(b, "argilla")
				c[r] = c.get(r, 0) + 1
	return c
