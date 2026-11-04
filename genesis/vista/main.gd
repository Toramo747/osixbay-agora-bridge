extends Node3D
# Vista 3D low-poly di Genesis (Godot 4.6.3, computer del ponte).
# Il terreno si ricalcola dal seme e dalle zone di bots/genesi/mondo.json con la STESSA formula
# di bots/dati/genesi_costruttore.gd: biomi e risorse coincidono con il mondo del ponte.
# Comandi: trascina con il mouse = ruota; rotella = zoom; WASD/frecce = sposta; Q/E = ruota;
# Spazio = rotazione automatica; R = ricarica il mondo da GitHub.

const URL := "https://raw.githubusercontent.com/Toramo747/osixbay-agora-bridge/main/bots/genesi/mondo.json"
const MARE := -0.05
const BASE := -9.0

var n := FastNoiseLite.new()
var seme := 0
var zone: Array[Vector2i] = []
var mondo: Node3D
var perno: Node3D
var cam: Camera3D
var info: Label
var yaw := -0.6
var pitch := -0.55
var dist := 120.0
var giro := true
var trascina := false
var pesci: Array[Node3D] = []
var foto := ""

# --- formula del costruttore -------------------------------------------------------------
func campi(x: float, y: float) -> Vector2:
	return Vector2(n.get_noise_2d(x, y), n.get_noise_2d(x * 0.4 + 5e3, y * 0.4))

func bioma(h: float, m: float) -> String:
	return "oceano" if h < -0.2 else "spiaggia" if h < -0.12 else "montagna" if h > 0.45 else "foresta" if m > 0.05 else "deserto" if m < -0.3 else "prateria"

func risorsa(w: Vector2i, b: String) -> String:
	if (hash(w) + seme) % 97 != 0:
		return ""
	return {"oceano": "pesce", "montagna": "pietra", "foresta": "legno"}.get(b, "argilla")

# --- altezza del rilievo (solo resa grafica) ------------------------------------------------
func quota(h: float) -> float:
	if h < -0.2:
		return max((h + 0.2) * 16.0, -7.0)
	if h < -0.12:
		return (h + 0.2) / 0.08 * 0.55
	var y := 0.55 + (h + 0.12) * 9.0
	if h > 0.45:
		y += pow((h - 0.45) * 10.0, 1.6) * 2.2
	return y

func quota_in(x: float, y: float) -> float:
	return quota(campi(x, y).x)

# --- avvio -------------------------------------------------------------------------------
func _ready():
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--foto="):
			foto = a.substr(7)
		elif a.begins_with("--yaw="):
			yaw = float(a.substr(6))
	_scena()
	var locale := ""
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--mondo="):
			locale = a.substr(8)
	for p in [locale, "user://mondo.json", "res://mondo.json"]:
		if p != "" and FileAccess.file_exists(p):
			_carica(FileAccess.get_file_as_string(p))
			return
	_scarica()

func _scarica():
	info.text = "Genesis — scarico il mondo da GitHub…"
	var req := HTTPRequest.new()
	add_child(req)
	req.request_completed.connect(func(_r, code, _h, body):
		req.queue_free()
		if code == 200:
			var f := FileAccess.open("user://mondo.json", FileAccess.WRITE)
			f.store_string(body.get_string_from_utf8())
			f.close()
			_carica(body.get_string_from_utf8())
		else:
			info.text = "Genesis — mondo non raggiungibile (HTTP %d). Premi R per riprovare." % code)
	req.request(URL)

func _carica(testo: String):
	var d = JSON.parse_string(testo)
	if typeof(d) != TYPE_DICTIONARY or d.get("seme") == null or (d.get("zone", []) as Array).is_empty():
		info.text = "Genesis — il mondo non ha ancora seme o zone."
		return
	seme = int(d.seme)
	n.seed = seme
	zone.clear()
	for z in d.zone:
		var p = str(z).split(",")
		zone.append(Vector2i(int(p[0]), int(p[1])))
	if mondo:
		mondo.queue_free()
	pesci.clear()
	mondo = Node3D.new()
	add_child(mondo)
	_costruisci()
	var passi: Array = d.get("passi", [])
	info.text = "GENESIS   seme %d · %d zone · %d passi\ntrascina: ruota · rotella: zoom · WASD: sposta · spazio: giro automatico · R: ricarica" % [seme, zone.size(), passi.size()]
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--zoom="):
			dist *= float(a.substr(7))
		elif a.begins_with("--pitch="):
			pitch = float(a.substr(8))
		elif a.begins_with("--centro="):
			var c = a.substr(9).split(",")
			perno.position = Vector3(float(c[0]), 0, float(c[1]))
	if foto != "":
		_scatta.call_deferred()

# --- ambiente, luce, camera ----------------------------------------------------------------
func _scena():
	var env := Environment.new()
	var cielo := Sky.new()
	var sm := ProceduralSkyMaterial.new()
	sm.sky_top_color = Color(0.32, 0.55, 0.85)
	sm.sky_horizon_color = Color(0.78, 0.86, 0.93)
	sm.ground_horizon_color = Color(0.80, 0.87, 0.93)
	sm.ground_bottom_color = Color(0.62, 0.74, 0.86)
	sm.sun_angle_max = 20.0
	cielo.sky_material = sm
	env.background_mode = Environment.BG_SKY
	env.sky = cielo
	env.ambient_light_source = Environment.AMBIENT_SOURCE_SKY
	env.ambient_light_energy = 0.75
	env.tonemap_mode = Environment.TONE_MAPPER_FILMIC
	env.tonemap_white = 6.0
	env.glow_enabled = true
	env.glow_intensity = 0.4
	env.glow_bloom = 0.05
	env.ssao_enabled = true
	env.ssao_intensity = 1.6
	env.fog_enabled = true
	env.fog_light_color = Color(0.74, 0.83, 0.92)
	env.fog_density = 0.0009
	env.fog_sky_affect = 0.0
	env.adjustment_enabled = true
	env.adjustment_saturation = 1.12
	var we := WorldEnvironment.new()
	we.environment = env
	add_child(we)

	var sole := DirectionalLight3D.new()
	sole.rotation_degrees = Vector3(-48, -38, 0)
	sole.light_color = Color(1.0, 0.95, 0.86)
	sole.light_energy = 1.25
	sole.shadow_enabled = true
	sole.directional_shadow_max_distance = 260.0
	sole.shadow_blur = 1.5
	add_child(sole)

	perno = Node3D.new()
	add_child(perno)
	cam = Camera3D.new()
	cam.fov = 45.0
	cam.far = 1500.0
	perno.add_child(cam)
	_camera()

	var cl := CanvasLayer.new()
	add_child(cl)
	info = Label.new()
	info.position = Vector2(18, 14)
	info.add_theme_font_size_override("font_size", 16)
	info.add_theme_color_override("font_color", Color(1, 1, 1))
	info.add_theme_color_override("font_outline_color", Color(0.05, 0.1, 0.15, 0.85))
	info.add_theme_constant_override("outline_size", 6)
	cl.add_child(info)

func _camera():
	perno.rotation = Vector3(pitch, yaw, 0)
	cam.position = Vector3(0, 0, dist)

func _process(dt):
	var v := Vector3.ZERO
	if Input.is_key_pressed(KEY_W) or Input.is_key_pressed(KEY_UP): v.z -= 1
	if Input.is_key_pressed(KEY_S) or Input.is_key_pressed(KEY_DOWN): v.z += 1
	if Input.is_key_pressed(KEY_A) or Input.is_key_pressed(KEY_LEFT): v.x -= 1
	if Input.is_key_pressed(KEY_D) or Input.is_key_pressed(KEY_RIGHT): v.x += 1
	if Input.is_key_pressed(KEY_Q): yaw += dt
	if Input.is_key_pressed(KEY_E): yaw -= dt
	if v != Vector3.ZERO:
		perno.position += v.rotated(Vector3.UP, yaw).normalized() * dt * dist * 0.6
	if giro and not trascina:
		yaw += dt * 0.05
	_camera()
	var t := Time.get_ticks_msec() / 1000.0
	for p in pesci:
		p.rotation.y = t * 0.7 + p.get_meta("fase")

func _unhandled_input(e):
	if e is InputEventMouseButton:
		if e.button_index == MOUSE_BUTTON_WHEEL_UP: dist = max(12.0, dist * 0.9)
		elif e.button_index == MOUSE_BUTTON_WHEEL_DOWN: dist = min(400.0, dist * 1.1)
		elif e.button_index in [MOUSE_BUTTON_LEFT, MOUSE_BUTTON_RIGHT]: trascina = e.pressed
	elif e is InputEventMouseMotion and trascina:
		yaw -= e.relative.x * 0.005
		pitch = clamp(pitch - e.relative.y * 0.004, -1.45, -0.12)
	elif e is InputEventKey and e.pressed and not e.echo:
		if e.keycode == KEY_SPACE: giro = not giro
		elif e.keycode == KEY_R:
			if FileAccess.file_exists("user://mondo.json"):
				DirAccess.remove_absolute(ProjectSettings.globalize_path("user://mondo.json"))
			_scarica()

# --- costruzione del mondo -----------------------------------------------------------------
const COLORI := {
	"oceano": [Color(0.70, 0.66, 0.50), Color(0.32, 0.36, 0.34)],
	"spiaggia": [Color(0.93, 0.84, 0.60), Color(0.88, 0.78, 0.55)],
	"prateria": [Color(0.55, 0.74, 0.32), Color(0.72, 0.80, 0.40)],
	"foresta": [Color(0.24, 0.48, 0.22), Color(0.32, 0.56, 0.26)],
	"deserto": [Color(0.88, 0.70, 0.40), Color(0.94, 0.78, 0.50)],
	"montagna": [Color(0.50, 0.46, 0.42), Color(0.96, 0.97, 1.0)],
}

func colore(b: String, h: float, rnd: float) -> Color:
	var c: Array = COLORI[b]
	var t := 0.0
	match b:
		"oceano": t = clamp((-0.2 - h) / 0.4, 0.0, 1.0)
		"montagna": t = clamp((h - 0.55) / 0.15, 0.0, 1.0)
		_: t = clamp((h + 0.12) / 0.6, 0.0, 1.0)
	return (c[0] as Color).lerp(c[1], t).lightened(rnd * 0.05).darkened((1.0 - rnd) * 0.05)

func _costruisci():
	var lo := zone[0]
	var hi := zone[0]
	for z in zone:
		lo = Vector2i(min(lo.x, z.x), min(lo.y, z.y))
		hi = Vector2i(max(hi.x, z.x), max(hi.y, z.y))
	var centro := Vector3((lo.x + hi.x + 1) * 16.0, 0, (lo.y + hi.y + 1) * 16.0)
	mondo.position = -centro
	dist = max(hi.x - lo.x + 1, hi.y - lo.y + 1) * 32.0 * 1.12

	var terra := StandardMaterial3D.new()
	terra.vertex_color_use_as_albedo = true
	terra.roughness = 0.95
	var acqua := ShaderMaterial.new()
	acqua.shader = load("res://acqua.gdshader")
	var bordo_acqua := StandardMaterial3D.new()
	bordo_acqua.albedo_color = Color(0.12, 0.42, 0.62, 0.65)
	bordo_acqua.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	bordo_acqua.roughness = 0.1

	var set_z := {}
	for z in zone:
		set_z[z] = true
	for z in zone:
		_zona(z, set_z, terra, acqua, bordo_acqua)
	_vegetazione()
	_nuvole(lo, hi)

func _zona(z: Vector2i, set_z: Dictionary, terra: Material, acqua: Material, bordo_acqua: Material):
	var ox := z.x * 32
	var oy := z.y * 32
	var hq := {}
	for y in 33:
		for x in 33:
			hq[Vector2i(x, y)] = quota_in(ox + x, oy + y)
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	for y in 32:
		for x in 32:
			var p := [Vector3(ox + x, hq[Vector2i(x, y)], oy + y), Vector3(ox + x + 1, hq[Vector2i(x + 1, y)], oy + y),
				Vector3(ox + x + 1, hq[Vector2i(x + 1, y + 1)], oy + y + 1), Vector3(ox + x, hq[Vector2i(x, y + 1)], oy + y + 1)]
			var tris := [[0, 1, 2], [0, 2, 3]] if (x + y) % 2 == 0 else [[0, 1, 3], [1, 2, 3]]
			for t in tris:
				var c: Vector3 = (p[t[0]] + p[t[1]] + p[t[2]]) / 3.0
				var f := campi(c.x, c.z)
				var rnd := float(abs(hash(Vector3i(int(c.x * 3), int(c.z * 3), seme))) % 1000) / 1000.0
				st.set_color(colore(bioma(f.x, f.y), f.x, rnd))
				for i in [t[0], t[1], t[2]]:
					st.add_vertex(p[i])
	# pareti del diorama dove non c'è una zona vicina
	var lati := [[Vector2i(0, -1), Vector2i(0, 0), Vector2i(32, 0)], [Vector2i(1, 0), Vector2i(32, 0), Vector2i(32, 32)],
		[Vector2i(0, 1), Vector2i(32, 32), Vector2i(0, 32)], [Vector2i(-1, 0), Vector2i(0, 32), Vector2i(0, 0)]]
	var sa := SurfaceTool.new()
	sa.begin(Mesh.PRIMITIVE_TRIANGLES)
	var acqua_lati := false
	for l in lati:
		if set_z.has(z + l[0]):
			continue
		var a: Vector2i = l[1]
		var b: Vector2i = l[2]
		var dir := (b - a) / 32
		for i in 32:
			var q0 := a + dir * i
			var q1 := a + dir * (i + 1)
			var h0: float = hq[q0]
			var h1: float = hq[q1]
			var v0 := Vector3(ox + q0.x, h0, oy + q0.y)
			var v1 := Vector3(ox + q1.x, h1, oy + q1.y)
			var strati := [[0.0, 0.8, Color(0.42, 0.30, 0.20)], [0.8, 3.5, Color(0.55, 0.40, 0.28)], [3.5, 100.0, Color(0.46, 0.43, 0.40)]]
			for s in strati:
				var t0: float = min(h0, max(BASE, min(h0, h1) - s[0]))
				var top0: float = h0 - s[0]
				var top1: float = h1 - s[0]
				var bot0: float = max(BASE, h0 - s[1])
				var bot1: float = max(BASE, h1 - s[1])
				if top0 <= BASE and top1 <= BASE:
					continue
				st.set_color((s[2] as Color).darkened(0.08 * float(i % 3) / 2.0))
				var A := Vector3(v0.x, max(top0, BASE), v0.z)
				var B := Vector3(v1.x, max(top1, BASE), v1.z)
				var C := Vector3(v1.x, bot1, v1.z)
				var D := Vector3(v0.x, bot0, v0.z)
				for v in [A, C, B, A, D, C]:
					st.add_vertex(v)
			if h0 < MARE or h1 < MARE:
				acqua_lati = true
				var W0 := Vector3(v0.x, MARE, v0.z)
				var W1 := Vector3(v1.x, MARE, v1.z)
				for v in [W0, Vector3(v1.x, min(h1, MARE), v1.z), W1, W0, Vector3(v0.x, min(h0, MARE), v0.z), Vector3(v1.x, min(h1, MARE), v1.z)]:
					sa.add_vertex(v)
	# fondo del diorama
	st.set_color(Color(0.3, 0.24, 0.18))
	for v in [Vector3(ox, BASE, oy), Vector3(ox + 32, BASE, oy + 32), Vector3(ox, BASE, oy + 32), Vector3(ox, BASE, oy), Vector3(ox + 32, BASE, oy), Vector3(ox + 32, BASE, oy + 32)]:
		st.add_vertex(v)
	st.generate_normals()
	var mi := MeshInstance3D.new()
	mi.mesh = st.commit()
	mi.material_override = terra
	mondo.add_child(mi)
	if acqua_lati:
		sa.generate_normals()
		var wa := MeshInstance3D.new()
		wa.mesh = sa.commit()
		wa.material_override = bordo_acqua
		wa.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		mondo.add_child(wa)
	# superficie dell'acqua
	var pm := PlaneMesh.new()
	pm.size = Vector2(32, 32)
	pm.subdivide_width = 31
	pm.subdivide_depth = 31
	var w := MeshInstance3D.new()
	w.mesh = pm
	w.material_override = acqua
	w.position = Vector3(ox + 16, MARE, oy + 16)
	w.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	mondo.add_child(w)

# --- forme low-poly generate dal codice ----------------------------------------------------
func piatto(mesh: PrimitiveMesh, xf := Transform3D.IDENTITY, st: SurfaceTool = null) -> SurfaceTool:
	var src := SurfaceTool.new()
	src.create_from(mesh, 0)
	var arr := src.commit_to_arrays()
	var verts: PackedVector3Array = arr[Mesh.ARRAY_VERTEX]
	var idx: PackedInt32Array = arr[Mesh.ARRAY_INDEX]
	if st == null:
		st = SurfaceTool.new()
		st.begin(Mesh.PRIMITIVE_TRIANGLES)
	for i in idx:
		st.add_vertex(xf * verts[i])
	return st

func forma(parti: Array, colori: Array) -> ArrayMesh:
	# parti: [[mesh, transform], ...] per superficie; ogni superficie ha il suo materiale (colore istanza solo sulla 0)
	var am := ArrayMesh.new()
	for s in parti.size():
		var st: SurfaceTool = null
		for p in parti[s]:
			st = piatto(p[0], p[1], st)
		st.generate_normals()
		st.commit(am)
		var mat := StandardMaterial3D.new()
		mat.albedo_color = colori[s]
		mat.roughness = 0.9
		if s == 0:
			mat.vertex_color_use_as_albedo = true
		am.surface_set_material(s, mat)
	return am

func cono(r: float, h: float, seg := 7) -> CylinderMesh:
	var c := CylinderMesh.new()
	c.top_radius = 0.0; c.bottom_radius = r; c.height = h; c.radial_segments = seg; c.rings = 1
	return c

func tronco(r: float, h: float) -> CylinderMesh:
	var c := CylinderMesh.new()
	c.top_radius = r * 0.7; c.bottom_radius = r; c.height = h; c.radial_segments = 6; c.rings = 1
	return c

func palla(r: float, seg := 7, anelli := 4) -> SphereMesh:
	var s := SphereMesh.new()
	s.radius = r; s.height = r * 2; s.radial_segments = seg; s.rings = anelli
	return s

func T(pos: Vector3, sc := Vector3.ONE, rot := 0.0) -> Transform3D:
	return Transform3D(Basis(Vector3.UP, rot).scaled(sc), pos)

func modelli() -> Dictionary:
	var legno := Color(0.42, 0.28, 0.17)
	return {
		"pino": forma([[[cono(0.95, 1.5), T(Vector3(0, 1.3, 0))], [cono(0.75, 1.3), T(Vector3(0, 2.0, 0), Vector3.ONE, 0.4)], [cono(0.5, 1.1), T(Vector3(0, 2.7, 0), Vector3.ONE, 0.9)]],
			[[tronco(0.14, 0.9), T(Vector3(0, 0.45, 0))]]], [Color.WHITE, legno]),
		"latifoglia": forma([[[palla(0.9), T(Vector3(0, 1.75, 0), Vector3(1, 0.85, 1))], [palla(0.6, 6, 3), T(Vector3(0.45, 1.45, 0.2))], [palla(0.55, 6, 3), T(Vector3(-0.4, 1.5, -0.25))]],
			[[tronco(0.15, 1.3), T(Vector3(0, 0.65, 0))]]], [Color.WHITE, legno]),
		"cespuglio": forma([[[palla(0.45, 6, 3), T(Vector3(0, 0.3, 0), Vector3(1.2, 0.8, 1))], [palla(0.32, 5, 3), T(Vector3(0.35, 0.22, 0.1))]]], [Color.WHITE]),
		"roccia": forma([[[palla(0.8, 5, 3), T(Vector3(0, 0.25, 0), Vector3(1.3, 0.75, 1))], [palla(0.45, 5, 2), T(Vector3(0.6, 0.15, 0.3))]]], [Color.WHITE]),
		"cactus": forma([[[tronco(0.16, 1.4), T(Vector3(0, 0.7, 0))], [tronco(0.09, 0.5), T(Vector3(0.24, 0.85, 0), Vector3.ONE)], [tronco(0.08, 0.4), T(Vector3(-0.22, 1.0, 0))],
			[tronco(0.1, 0.25), T(Vector3(0.14, 0.6, 0), Vector3(1, 1, 1), 0.0).rotated_local(Vector3.FORWARD, PI / 2)], [tronco(0.09, 0.22), T(Vector3(-0.13, 0.8, 0)).rotated_local(Vector3.FORWARD, PI / 2)]]], [Color.WHITE]),
		"argilla": forma([[[palla(0.7, 6, 3), T(Vector3(0, 0.1, 0), Vector3(1.4, 0.55, 1.1))], [palla(0.4, 6, 3), T(Vector3(0.6, 0.05, 0.4), Vector3(1, 0.6, 1))]]], [Color.WHITE]),
	}

func _vegetazione():
	var m := modelli()
	var erba := (load("res://modelli/grass-small.glb") as PackedScene)
	var erba_mesh: Mesh = null
	if erba:
		var e := erba.instantiate()
		var mi := e.find_children("*", "MeshInstance3D", true, false)
		if mi.size() > 0:
			erba_mesh = (mi[0] as MeshInstance3D).mesh
		e.free()
	var posti := {}          # nome -> [[Transform3D, Color], ...]
	var r := RandomNumberGenerator.new()
	for z in zone:
		for y in 32:
			for x in 32:
				var w := Vector2i(z.x * 32 + x, z.y * 32 + y)
				var f := campi(w.x, w.y)
				var b := bioma(f.x, f.y)
				var ris := risorsa(w, b)
				r.seed = hash(Vector3i(w.x, w.y, seme))
				var p := Vector3(w.x + r.randf_range(-0.35, 0.35), 0, w.y + r.randf_range(-0.35, 0.35))
				p.y = quota_in(p.x, p.z) - 0.05
				var rot := r.randf() * TAU
				if ris == "legno":
					_metti(posti, "latifoglia", T(p, Vector3.ONE * 1.9, rot), Color(0.36, 0.62, 0.22))
				elif ris == "pietra":
					_metti(posti, "roccia", T(p, Vector3.ONE * 1.8, rot), Color(0.55, 0.53, 0.52))
				elif ris == "argilla":
					_metti(posti, "argilla", T(Vector3(p.x, max(p.y, MARE), p.z), Vector3.ONE, rot), Color(0.74, 0.36, 0.22))
				elif ris == "pesce":
					_pesci(Vector3(w.x, MARE, w.y), max(quota_in(w.x, w.y), -3.0))
				match b:
					"foresta":
						var v := r.randf()
						if v < 0.42:
							var pino := f.x > 0.18 or r.randf() < 0.35
							var sc := r.randf_range(0.75, 1.3)
							var col := Color(0.16, 0.38, 0.2) if pino else Color(0.27, 0.52, 0.2)
							_metti(posti, "pino" if pino else "latifoglia", T(p, Vector3.ONE * sc, rot), col.lightened(r.randf() * 0.12))
						elif v < 0.5:
							_metti(posti, "cespuglio", T(p, Vector3.ONE * r.randf_range(0.7, 1.2), rot), Color(0.25, 0.47, 0.2).lightened(r.randf() * 0.1))
					"prateria":
						var v := r.randf()
						if v < 0.035:
							_metti(posti, "latifoglia", T(p, Vector3.ONE * r.randf_range(0.8, 1.2), rot), Color(0.36, 0.6, 0.22))
						elif v < 0.09:
							_metti(posti, "cespuglio", T(p, Vector3.ONE * r.randf_range(0.6, 1.0), rot), Color(0.4, 0.62, 0.24))
						elif v < 0.3 and erba_mesh:
							_metti(posti, "erba", T(p, Vector3.ONE * r.randf_range(0.6, 1.0), rot), Color.WHITE)
					"deserto":
						var v := r.randf()
						if v < 0.035:
							_metti(posti, "cactus", T(p, Vector3.ONE * r.randf_range(0.8, 1.3), rot), Color(0.35, 0.55, 0.3))
						elif v < 0.055:
							_metti(posti, "roccia", T(p, Vector3.ONE * r.randf_range(0.3, 0.6), rot), Color(0.72, 0.58, 0.42))
					"montagna":
						if r.randf() < 0.14:
							_metti(posti, "roccia", T(p, Vector3.ONE * r.randf_range(0.5, 1.2), rot), Color(0.5, 0.48, 0.46).lightened(r.randf() * 0.15))
					"spiaggia":
						if r.randf() < 0.02:
							_metti(posti, "roccia", T(p, Vector3.ONE * r.randf_range(0.25, 0.45), rot), Color(0.66, 0.62, 0.56))
	m["erba"] = erba_mesh
	for nome in posti:
		var mm := MultiMesh.new()
		mm.transform_format = MultiMesh.TRANSFORM_3D
		mm.use_colors = nome != "erba"
		mm.mesh = m[nome]
		var lista: Array = posti[nome]
		mm.instance_count = lista.size()
		for i in lista.size():
			mm.set_instance_transform(i, lista[i][0])
			if mm.use_colors:
				mm.set_instance_color(i, lista[i][1])
		var mmi := MultiMeshInstance3D.new()
		mmi.multimesh = mm
		if nome == "erba":
			mmi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		mondo.add_child(mmi)

func _metti(posti: Dictionary, nome: String, xf: Transform3D, col: Color):
	if not posti.has(nome):
		posti[nome] = []
	posti[nome].append([xf, col])

func _pesci(sopra: Vector3, fondo: float):
	var banco := Node3D.new()
	banco.position = Vector3(sopra.x, lerp(MARE, fondo, 0.35), sopra.z)
	banco.set_meta("fase", float(hash(sopra) % 628) / 100.0)
	var mat := StandardMaterial3D.new()
	mat.albedo_color = Color(1.0, 0.55, 0.2)
	mat.roughness = 0.5
	for i in 4:
		var pesce := MeshInstance3D.new()
		var pr := PrismMesh.new()
		pr.size = Vector3(0.18, 0.5, 0.12)
		pesce.mesh = pr
		pesce.material_override = mat
		var a := TAU * i / 4.0
		pesce.position = Vector3(cos(a), sin(i) * 0.15, sin(a)) * 0.7
		pesce.rotation = Vector3(0, -a, PI / 2)
		banco.add_child(pesce)
	mondo.add_child(banco)
	pesci.append(banco)

func _nuvole(lo: Vector2i, hi: Vector2i):
	var mat := StandardMaterial3D.new()
	mat.albedo_color = Color(1, 1, 1)
	mat.roughness = 1.0
	mat.emission_enabled = true
	mat.emission = Color(0.55, 0.6, 0.68)
	var r := RandomNumberGenerator.new()
	r.seed = seme
	for i in 6:
		var parti := []
		for k in r.randi_range(4, 7):
			parti.append([palla(r.randf_range(1.4, 2.4), 8, 5), T(Vector3(r.randf_range(-3, 3), r.randf_range(-0.4, 0.8), r.randf_range(-1.5, 1.5)), Vector3(1, 0.7, 1))])
		var nube := MeshInstance3D.new()
		nube.mesh = forma([parti], [Color.WHITE])
		nube.mesh.surface_set_material(0, mat)
		nube.position = Vector3(r.randf_range(lo.x * 32, (hi.x + 1) * 32), r.randf_range(24, 32), r.randf_range(lo.y * 32, (hi.y + 1) * 32))
		nube.scale = Vector3.ONE * r.randf_range(1.0, 1.6)
		mondo.add_child(nube)

# --- foto per controlli (--foto=percorso.png) -----------------------------------------------
func _scatta():
	giro = false
	for i in 30:
		await get_tree().process_frame
	await RenderingServer.frame_post_draw
	get_viewport().get_texture().get_image().save_png(foto)
	print("FOTO ", foto)
	get_tree().quit()
