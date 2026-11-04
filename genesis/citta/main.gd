extends Node3D
# Genesis — città (Godot 4.6.3, computer del ponte).
# Il terreno si ricalcola dal seme e dalle zone di bots/genesi/mondo.json con la STESSA formula di
# bots/dati/genesi_costruttore.gd (biomi e risorse identici al ponte), a tessere 1×1 come una griglia
# di SimCity. Sopra il giocatore costruisce strade ed edifici (modelli CC0 di Kenney).
# Comandi: WASD/frecce sposta · rotella zoom · tasto destro o centrale trascinato ruota · Q/E ruota
# 1–0 o barra in basso = strumento · clic sinistro costruisci · clic destro (fermo) o X demolisci · R ruota edificio · F5 ricarica il mondo

const URL := "https://raw.githubusercontent.com/Toramo747/osixbay-agora-bridge/main/bots/genesi/mondo.json"
const LIV := 0.3          # altezza di un gradone
const MARE := -0.14
const BASE := -2.6
const M := "res://kenney/modelli/"

var n := FastNoiseLite.new()
var seme := 0
var zone: Array[Vector2i] = []
var celle := {}            # Vector2i -> {b, liv, y, ris}
var mondo: Node3D
var perno: Node3D
var cam: Camera3D
var info: Label
var stato: Label
var yaw := 45.0
var pitch := -38.0
var zoom := 60.0
var trascina := false
var mosso := 0.0
var foto := ""
var demo := false

# città
var citta := {}            # Vector2i -> {"t": strumento, "r": rotazione}
var nodi := {}             # Vector2i -> Node3D
var veg := {}              # Vector2i -> [MultiMesh, indice, Transform3D]
var strumento := 0
var rot := 0
var cursore: MeshInstance3D
var anteprima: Node3D
var cella_mouse = null
var mesh_cache := {}
var suoni := {}
var barra: HBoxContainer

const STRUMENTI := [
	{"id": "strada", "nome": "Strada", "tasto": KEY_1},
	{"id": "building-small-a", "nome": "Casa", "tasto": KEY_2},
	{"id": "building-small-b", "nome": "Palazzina", "tasto": KEY_3},
	{"id": "building-small-c", "nome": "Torre", "tasto": KEY_4},
	{"id": "building-small-d", "nome": "Negozio", "tasto": KEY_5},
	{"id": "building-garage", "nome": "Garage", "tasto": KEY_6},
	{"id": "pavement", "nome": "Piazza", "tasto": KEY_7},
	{"id": "pavement-fountain", "nome": "Fontana", "tasto": KEY_8},
	{"id": "grass-trees", "nome": "Parco", "tasto": KEY_9},
	{"id": "demolisci", "nome": "Demolisci", "tasto": KEY_0},
]

# --- formula del costruttore -------------------------------------------------------------
func campi(x: float, y: float) -> Vector2:
	return Vector2(n.get_noise_2d(x, y), n.get_noise_2d(x * 0.4 + 5e3, y * 0.4))

func bioma(h: float, m: float) -> String:
	return "oceano" if h < -0.2 else "spiaggia" if h < -0.12 else "montagna" if h > 0.45 else "foresta" if m > 0.05 else "deserto" if m < -0.3 else "prateria"

func risorsa(w: Vector2i, b: String) -> String:
	if (hash(w) + seme) % 97 != 0:
		return ""
	return {"oceano": "pesce", "montagna": "pietra", "foresta": "legno"}.get(b, "argilla")

# --- gradoni (solo resa: la classificazione resta quella del costruttore) ------------------
func livello(h: float, b: String) -> int:
	match b:
		"oceano": return -1 - clampi(int((-0.2 - h) / 0.09), 0, 4)
		"spiaggia": return 0
		"montagna": return 3 + clampi(int((h - 0.45) / 0.05), 0, 6)
	return 0 if h < 0.1 else 1 if h < 0.28 else 2

func quota(liv: int, b: String) -> float:
	return -0.06 if b == "spiaggia" else liv * LIV

func costruibile(c: Vector2i) -> bool:
	return celle.has(c) and celle[c].b in ["prateria", "foresta", "deserto", "spiaggia"]

# --- avvio -------------------------------------------------------------------------------
func _ready():
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--foto="): foto = a.substr(7)
		elif a == "--demo": demo = true
	_scena()
	_interfaccia()
	for s in ["placement-a", "placement-b", "removal-a", "rotate", "toggle"]:
		var p := AudioStreamPlayer.new()
		p.stream = load("res://kenney/suoni/%s.ogg" % s)
		p.volume_db = -14.0
		add_child(p)
		suoni[s] = p
	var locale := ""
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--mondo="): locale = a.substr(8)
	for p in [locale, "user://mondo.json"]:
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
			info.text = "Genesis — mondo non raggiungibile (HTTP %d). F5 per riprovare." % code)
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
	mondo = Node3D.new()
	add_child(mondo)
	celle.clear(); nodi.clear(); veg.clear()
	_costruisci()
	_carica_citta()
	if demo:
		_demo()
	info.text = "GENESIS   seme %d · %d zone · %d passi del costruttore" % [seme, zone.size(), (d.get("passi", []) as Array).size()]
	if foto != "":
		_scatta.call_deferred()

# --- ambiente (come lo Starter Kit City Builder di Kenney) ---------------------------------
func _scena():
	var env := Environment.new()
	var cielo := Sky.new()
	var sm := ProceduralSkyMaterial.new()
	sm.sky_top_color = Color(0.45, 0.62, 0.86)
	sm.sky_horizon_color = Color(0.72, 0.78, 0.86)
	sm.ground_horizon_color = Color(0.72, 0.78, 0.86)
	sm.ground_bottom_color = Color(0.6, 0.66, 0.76)
	cielo.sky_material = sm
	env.background_mode = Environment.BG_SKY
	env.sky = cielo
	env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	env.ambient_light_color = Color(0.66, 0.70, 0.78)
	env.ambient_light_energy = 0.55
	env.tonemap_mode = Environment.TONE_MAPPER_FILMIC
	env.ssao_enabled = true
	env.ssao_radius = 0.25
	env.ssao_intensity = 0.6
	env.glow_enabled = false
	env.glow_intensity = 0.6
	env.adjustment_enabled = true
	env.adjustment_saturation = 1.18
	env.adjustment_brightness = 0.9
	env.tonemap_exposure = 0.9
	var we := WorldEnvironment.new()
	we.environment = env
	add_child(we)
	var sole := DirectionalLight3D.new()
	sole.rotation_degrees = Vector3(-50, -150, 0)
	sole.light_energy = 1.15
	sole.light_color = Color(1.0, 0.97, 0.9)
	sole.shadow_enabled = true
	sole.shadow_opacity = 0.75
	sole.directional_shadow_max_distance = 120.0
	add_child(sole)
	perno = Node3D.new()
	add_child(perno)
	cam = Camera3D.new()
	cam.fov = 20.0
	cam.far = 2000.0
	perno.add_child(cam)
	cursore = MeshInstance3D.new()
	var q := PlaneMesh.new()
	q.size = Vector2(1.02, 1.02)
	cursore.mesh = q
	var cm := StandardMaterial3D.new()
	cm.albedo_color = Color(1, 1, 1, 0.45)
	cm.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	cm.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	cursore.material_override = cm
	cursore.visible = false
	add_child(cursore)
	anteprima = Node3D.new()
	add_child(anteprima)

func _interfaccia():
	var cl := CanvasLayer.new()
	add_child(cl)
	var font := load("res://kenney/font/lilita_one_regular.ttf")
	var tema := Theme.new()
	tema.default_font = font
	tema.default_font_size = 20
	var su := PanelContainer.new()
	su.theme = tema
	su.position = Vector2(16, 14)
	var sb := StyleBoxFlat.new()
	sb.bg_color = Color(0.12, 0.14, 0.2, 0.72)
	sb.set_corner_radius_all(10)
	sb.content_margin_left = 16; sb.content_margin_right = 16; sb.content_margin_top = 8; sb.content_margin_bottom = 8
	su.add_theme_stylebox_override("panel", sb)
	var col := VBoxContainer.new()
	su.add_child(col)
	info = Label.new()
	stato = Label.new()
	stato.add_theme_font_size_override("font_size", 15)
	stato.add_theme_color_override("font_color", Color(0.8, 0.85, 0.95))
	col.add_child(info)
	col.add_child(stato)
	cl.add_child(su)
	var giu := PanelContainer.new()
	giu.theme = tema
	giu.add_theme_stylebox_override("panel", sb)
	giu.anchor_left = 0.5; giu.anchor_right = 0.5; giu.anchor_top = 1.0; giu.anchor_bottom = 1.0
	giu.grow_horizontal = Control.GROW_DIRECTION_BOTH
	giu.grow_vertical = Control.GROW_DIRECTION_BEGIN
	giu.offset_bottom = -16
	barra = HBoxContainer.new()
	barra.add_theme_constant_override("separation", 6)
	giu.add_child(barra)
	for i in STRUMENTI.size():
		var b := Button.new()
		b.text = "%d  %s" % [(i + 1) % 10, STRUMENTI[i].nome]
		b.toggle_mode = true
		b.focus_mode = Control.FOCUS_NONE
		b.pressed.connect(_scegli.bind(i))
		barra.add_child(b)
	cl.add_child(giu)
	_scegli(0)

func _scegli(i: int):
	strumento = i
	for k in barra.get_child_count():
		(barra.get_child(k) as Button).button_pressed = k == i
	for c in anteprima.get_children():
		c.queue_free()
	var id: String = STRUMENTI[i].id
	if id != "demolisci":
		var sc := load(M + ("road-straight" if id == "strada" else id) + ".glb") as PackedScene
		var g := sc.instantiate()
		anteprima.add_child(g)
	_suona("toggle")
	stato.text = "Strumento: %s · clic sinistro costruisci · R ruota · clic destro demolisci" % STRUMENTI[i].nome

func _suona(s: String):
	if suoni.has(s):
		suoni[s].play()

# --- terreno a tessere ---------------------------------------------------------------------
const COL := {
	"prateria": Color(0.38, 0.72, 0.42), "foresta": Color(0.29, 0.62, 0.38), "spiaggia": Color(0.95, 0.85, 0.62),
	"deserto": Color(0.93, 0.76, 0.48), "montagna": Color(0.56, 0.55, 0.58), "oceano": Color(0.84, 0.76, 0.56),
}
const TERRA := Color(0.55, 0.40, 0.29)
const ROCCIA := Color(0.46, 0.45, 0.48)

func mesh_di(nome: String) -> Mesh:
	if mesh_cache.has(nome):
		return mesh_cache[nome]
	var g := (load(M + nome + ".glb") as PackedScene).instantiate()
	var mi := g.find_children("*", "MeshInstance3D", true, false)
	var mesh: Mesh = (mi[0] as MeshInstance3D).mesh if mi.size() > 0 else null
	g.free()
	mesh_cache[nome] = mesh
	return mesh

func _costruisci():
	var lo := zone[0]
	var hi := zone[0]
	for z in zone:
		lo = Vector2i(min(lo.x, z.x), min(lo.y, z.y))
		hi = Vector2i(max(hi.x, z.x), max(hi.y, z.y))
		for y in 32:
			for x in 32:
				var w := Vector2i(z.x * 32 + x, z.y * 32 + y)
				var f := campi(w.x, w.y)
				var b := bioma(f.x, f.y)
				var lv := livello(f.x, b)
				celle[w] = {"b": b, "liv": lv, "y": quota(lv, b), "h": f.x, "ris": risorsa(w, b)}
	perno.position = Vector3((lo.x + hi.x + 1) * 16.0, 0, (lo.y + hi.y + 1) * 16.0)
	zoom = max(hi.x - lo.x + 1, hi.y - lo.y + 1) * 32.0 * 3.1
	_terreno()
	_acqua()
	_tessere()

func top(c: Vector2i) -> float:
	# altezza del piano calpestabile (le tessere Kenney sono spesse 0.06)
	return celle[c].y + 0.06

func _terreno():
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	var dirs := [Vector2i(1, 0), Vector2i(-1, 0), Vector2i(0, 1), Vector2i(0, -1)]
	for c in celle:
		var d = celle[c]
		var y := top(c)
		var b: String = d.b
		var x0: float = c.x - 0.5; var x1: float = c.x + 0.5; var z0: float = c.y - 0.5; var z1: float = c.y + 0.5
		# piano superiore (sotto le tessere Kenney resta nascosto)
		if not b in ["prateria", "foresta"]:
			var tinta: Color = COL[b]
			if b == "montagna":
				tinta = ROCCIA.lerp(Color(0.95, 0.96, 1.0), clamp((d.liv - 6) / 2.0, 0.0, 1.0))
			elif b == "oceano":
				tinta = tinta.darkened(0.12 * -d.liv)
			tinta = tinta.lightened(float(abs(hash(c)) % 7) * 0.006)
			st.set_color(tinta)
			_quad(st, Vector3(x0, y, z0), Vector3(x1, y, z0), Vector3(x1, y, z1), Vector3(x0, y, z1))
		# pareti dei gradoni e del bordo
		for k in 4:
			var v: Vector2i = c + dirs[k]
			var giu := BASE
			if celle.has(v):
				giu = top(v)
			if giu >= y - 0.001:
				continue
			var a: Vector3; var e: Vector3
			match k:
				0: a = Vector3(x1, 0, z1); e = Vector3(x1, 0, z0)
				1: a = Vector3(x0, 0, z0); e = Vector3(x0, 0, z1)
				2: a = Vector3(x0, 0, z1); e = Vector3(x1, 0, z1)
				3: a = Vector3(x1, 0, z0); e = Vector3(x0, 0, z0)
			var bande := []
			if b in ["prateria", "foresta"]:
				bande = [[y, y - 0.08, COL.prateria.darkened(0.15)], [y - 0.08, giu, TERRA]]
			elif b == "montagna":
				bande = [[y, giu, ROCCIA.darkened(0.1)]]
			elif b in ["spiaggia", "deserto", "oceano"]:
				bande = [[y, giu, (COL[b] as Color).darkened(0.18)]]
			if not celle.has(v):
				# bordo del diorama: strati di terra e roccia
				var fine := giu
				bande[-1][1] = max(fine, y - 0.5) if bande.size() == 1 else max(fine, y - 0.6)
				bande.append([bande[-1][1], max(fine, -1.2), TERRA.darkened(0.15)])
				bande.append([max(fine, -1.2), fine, ROCCIA.darkened(0.25)])
			for bd in bande:
				var t0: float = bd[0]; var t1: float = bd[1]
				if t0 - t1 < 0.001:
					continue
				st.set_color(bd[2])
				_quad(st, Vector3(a.x, t0, a.z), Vector3(e.x, t0, e.z), Vector3(e.x, t1, e.z), Vector3(a.x, t1, a.z))
	st.generate_normals()
	var mat := StandardMaterial3D.new()
	mat.vertex_color_use_as_albedo = true
	mat.roughness = 0.9
	var mi := MeshInstance3D.new()
	mi.mesh = st.commit()
	mi.material_override = mat
	mondo.add_child(mi)

func _quad(st: SurfaceTool, a: Vector3, b: Vector3, c: Vector3, d: Vector3):
	for v in [a, b, c, a, c, d]:
		st.add_vertex(v)

func _acqua():
	var mat := ShaderMaterial.new()
	mat.shader = load("res://acqua.gdshader")
	mat.set_shader_parameter("profonda", Color(0.16, 0.47, 0.72))
	mat.set_shader_parameter("chiara", Color(0.36, 0.72, 0.86))
	mat.set_shader_parameter("ampiezza", 0.03)
	var pareti := SurfaceTool.new()
	pareti.begin(Mesh.PRIMITIVE_TRIANGLES)
	for z in zone:
		var pm := PlaneMesh.new()
		pm.size = Vector2(32, 32)
		pm.subdivide_width = 31
		pm.subdivide_depth = 31
		var w := MeshInstance3D.new()
		w.mesh = pm
		w.material_override = mat
		w.position = Vector3(z.x * 32 + 15.5, MARE, z.y * 32 + 15.5)
		w.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		mondo.add_child(w)
	# acqua vista di lato sul bordo del diorama
	var dirs := [Vector2i(1, 0), Vector2i(-1, 0), Vector2i(0, 1), Vector2i(0, -1)]
	for c in celle:
		if top(c) >= MARE:
			continue
		for k in 4:
			if celle.has(c + dirs[k]):
				continue
			var x0: float = c.x - 0.5; var x1: float = c.x + 0.5; var z0: float = c.y - 0.5; var z1: float = c.y + 0.5
			var a: Vector3; var e: Vector3
			match k:
				0: a = Vector3(x1, 0, z1); e = Vector3(x1, 0, z0)
				1: a = Vector3(x0, 0, z0); e = Vector3(x0, 0, z1)
				2: a = Vector3(x0, 0, z1); e = Vector3(x1, 0, z1)
				3: a = Vector3(x1, 0, z0); e = Vector3(x0, 0, z0)
			_quad(pareti, Vector3(a.x, MARE, a.z), Vector3(e.x, MARE, e.z), Vector3(e.x, top(c), e.z), Vector3(a.x, top(c), a.z))
	pareti.generate_normals()
	var pm2 := StandardMaterial3D.new()
	pm2.albedo_color = Color(0.25, 0.6, 0.82, 0.55)
	pm2.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	pm2.roughness = 0.1
	var wi := MeshInstance3D.new()
	wi.mesh = pareti.commit()
	wi.material_override = pm2
	wi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	mondo.add_child(wi)

# --- forme generate dal codice per ciò che il kit non ha -------------------------------------
func forma(parti: Array, colore: Color) -> ArrayMesh:
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	for p in parti:
		var src := SurfaceTool.new()
		src.create_from(p[0], 0)
		var arr := src.commit_to_arrays()
		var verts: PackedVector3Array = arr[Mesh.ARRAY_VERTEX]
		for i in (arr[Mesh.ARRAY_INDEX] as PackedInt32Array):
			st.add_vertex(p[1] * verts[i])
	st.generate_normals()
	var am := st.commit()
	var mat := StandardMaterial3D.new()
	mat.albedo_color = colore
	mat.roughness = 0.85
	mat.vertex_color_use_as_albedo = false
	am.surface_set_material(0, mat)
	return am

func palla(r: float, seg := 6, anelli := 3) -> SphereMesh:
	var s := SphereMesh.new()
	s.radius = r; s.height = r * 2; s.radial_segments = seg; s.rings = anelli
	return s

func cil(r: float, h: float, seg := 6) -> CylinderMesh:
	var c := CylinderMesh.new()
	c.top_radius = r * 0.85; c.bottom_radius = r; c.height = h; c.radial_segments = seg; c.rings = 1
	return c

func T(pos: Vector3, sc := Vector3.ONE) -> Transform3D:
	return Transform3D(Basis().scaled(sc), pos)

func _tessere():
	var forme := {
		"roccia": forma([[palla(0.3), T(Vector3(0, 0.08, 0), Vector3(1.2, 0.7, 1))], [palla(0.18), T(Vector3(0.22, 0.05, 0.12))]], Color(0.62, 0.6, 0.62)),
		"roccia_grande": forma([[palla(0.36), T(Vector3(0, 0.15, 0), Vector3(1.1, 1.0, 1))], [palla(0.24), T(Vector3(0.26, 0.08, 0.15))], [palla(0.2), T(Vector3(-0.22, 0.06, -0.18))]], Color(0.5, 0.5, 0.54)),
		"argilla": forma([[palla(0.3), T(Vector3(0, 0.04, 0), Vector3(1.3, 0.5, 1.1))], [palla(0.18), T(Vector3(0.25, 0.03, 0.15), Vector3(1, 0.6, 1))]], Color(0.8, 0.42, 0.27)),
		"cactus": forma([[cil(0.08, 0.55), T(Vector3(0, 0.27, 0))], [cil(0.05, 0.22), T(Vector3(0.12, 0.36, 0))], [cil(0.05, 0.18), T(Vector3(-0.11, 0.42, 0))]], Color(0.35, 0.6, 0.36)),
		"pesci": forma([[palla(0.07, 5, 2), T(Vector3(0.15, 0, 0), Vector3(1.8, 0.7, 0.8))], [palla(0.07, 5, 2), T(Vector3(-0.12, 0, 0.14), Vector3(1.8, 0.7, 0.8))], [palla(0.07, 5, 2), T(Vector3(-0.05, 0, -0.16), Vector3(1.8, 0.7, 0.8))]], Color(1.0, 0.56, 0.24)),
	}
	var posti := {}
	var r := RandomNumberGenerator.new()
	for c in celle:
		var d = celle[c]
		r.seed = hash(Vector3i(c.x, c.y, seme))
		var y: float = celle[c].y
		var giro := Basis(Vector3.UP, (r.randi() % 4) * PI / 2)
		var b: String = d.b
		var ris: String = d.ris
		var base := Transform3D(giro, Vector3(c.x, y, c.y))
		if b == "prateria":
			_metti(posti, "grass", base, c)
		elif b == "foresta":
			var v := r.randf()
			_metti(posti, "grass-trees-tall" if ris == "legno" or v < 0.4 else "grass-trees" if v < 0.85 else "grass", base, c)
		var sopra := Transform3D(Basis(Vector3.UP, r.randf() * TAU), Vector3(c.x + r.randf_range(-0.2, 0.2), top(c), c.y + r.randf_range(-0.2, 0.2)))
		if ris == "pietra":
			_metti(posti, "roccia_grande", sopra.scaled_local(Vector3.ONE * 1.4), c)
		elif ris == "argilla":
			_metti(posti, "argilla", Transform3D(sopra.basis, Vector3(sopra.origin.x, max(top(c), MARE), sopra.origin.z)), c)
		elif ris == "pesce":
			_metti(posti, "pesci", Transform3D(sopra.basis, Vector3(c.x, MARE - 0.08, c.y)), c)
		elif b == "montagna" and r.randf() < 0.18:
			_metti(posti, "roccia", sopra.scaled_local(Vector3.ONE * r.randf_range(0.7, 1.3)), c)
		elif b == "deserto" and r.randf() < 0.06:
			_metti(posti, "cactus", sopra.scaled_local(Vector3.ONE * r.randf_range(0.8, 1.2)), c)
		elif b == "spiaggia" and r.randf() < 0.03:
			_metti(posti, "roccia", sopra.scaled_local(Vector3.ONE * 0.5), c)
	for nome in posti:
		var mm := MultiMesh.new()
		mm.transform_format = MultiMesh.TRANSFORM_3D
		mm.mesh = forme[nome] if forme.has(nome) else mesh_di(nome)
		var lista: Array = posti[nome]
		mm.instance_count = lista.size()
		for i in lista.size():
			mm.set_instance_transform(i, lista[i][0])
			if not veg.has(lista[i][1]):
				veg[lista[i][1]] = []
			veg[lista[i][1]].append([mm, i, lista[i][0]])
		var mmi := MultiMeshInstance3D.new()
		mmi.multimesh = mm
		mondo.add_child(mmi)

func _metti(posti: Dictionary, nome: String, xf: Transform3D, c: Vector2i):
	if not posti.has(nome):
		posti[nome] = []
	posti[nome].append([xf, c])

func _veg_visibile(c: Vector2i, si: bool):
	for v in veg.get(c, []):
		v[0].set_instance_transform(v[1], v[2] if si else Transform3D(Basis().scaled(Vector3.ONE * 0.0001), v[2].origin))

# --- città ---------------------------------------------------------------------------------
func _costruisci_in(c: Vector2i, id: String, r: int, salva := true):
	if id == "demolisci":
		_demolisci(c, salva)
		return
	if not costruibile(c):
		return
	if citta.has(c) and citta[c].t == id and id != "strada" and citta[c].r == r:
		return
	_togli_nodo(c)
	citta[c] = {"t": id, "r": r}
	_veg_visibile(c, false)
	_disegna(c)
	if id == "strada":
		for d in [Vector2i(1, 0), Vector2i(-1, 0), Vector2i(0, 1), Vector2i(0, -1)]:
			if citta.has(c + d) and citta[c + d].t == "strada":
				_togli_nodo(c + d)
				_disegna(c + d)
	if salva:
		_suona("placement-a" if randi() % 2 == 0 else "placement-b")
		_salva_citta()

func _demolisci(c: Vector2i, salva := true):
	if not citta.has(c):
		return
	var era: String = citta[c].t
	citta.erase(c)
	_togli_nodo(c)
	_veg_visibile(c, true)
	if era == "strada":
		for d in [Vector2i(1, 0), Vector2i(-1, 0), Vector2i(0, 1), Vector2i(0, -1)]:
			if citta.has(c + d) and citta[c + d].t == "strada":
				_togli_nodo(c + d)
				_disegna(c + d)
	if salva:
		_suona("removal-a")
		_salva_citta()

func _togli_nodo(c: Vector2i):
	if nodi.has(c):
		nodi[c].queue_free()
		nodi.erase(c)

func _strada(c: Vector2i) -> Array:
	# modello e rotazione della strada dai vicini (N, E, S, O)
	var v := []
	for d in [Vector2i(0, -1), Vector2i(1, 0), Vector2i(0, 1), Vector2i(-1, 0)]:
		v.append(citta.has(c + d) and citta[c + d].t == "strada")
	var k := v.count(true)
	if k == 4:
		return ["road-intersection", 0]
	if k == 3:
		var manca := v.find(false)
		return ["road-split", manca]
	if k == 2:
		if v[0] and v[2]: return ["road-straight", 0]
		if v[1] and v[3]: return ["road-straight", 1]
		for i in 4:
			if v[i] and v[(i + 1) % 4]:
				return ["road-corner", i]
	if v[1] or v[3]:
		return ["road-straight", 1]
	return ["road-straight", 0]

func _disegna(c: Vector2i):
	var d = citta[c]
	var nome: String = d.t
	var r: int = d.r
	if nome == "strada":
		var s := _strada(c)
		nome = s[0]; r = s[1]
		if nome == "road-straight" and (c.x + c.y) % 6 == 0:
			nome = "road-straight-lightposts"
	var g := (load(M + nome + ".glb") as PackedScene).instantiate() as Node3D
	g.position = Vector3(c.x, celle[c].y, c.y)
	g.rotation.y = r * PI / 2 + GIRO.get(nome, 0.0)
	mondo.add_child(g)
	nodi[c] = g

const GIRO := {}   # correzioni d'orientamento dei modelli strada, se servono

func _salva_citta():
	var out := {"seme": seme, "celle": {}}
	for c in citta:
		out.celle["%d,%d" % [c.x, c.y]] = citta[c]
	var f := FileAccess.open("user://citta.json", FileAccess.WRITE)
	f.store_string(JSON.stringify(out))
	f.close()

func _carica_citta():
	citta.clear()
	if not FileAccess.file_exists("user://citta.json"):
		return
	var d = JSON.parse_string(FileAccess.get_file_as_string("user://citta.json"))
	if typeof(d) != TYPE_DICTIONARY or int(d.get("seme", -1)) != seme:
		return
	for k in d.celle:
		var p = k.split(",")
		var c := Vector2i(int(p[0]), int(p[1]))
		if costruibile(c):
			citta[c] = {"t": str(d.celle[k].t), "r": int(d.celle[k].r)}
			_veg_visibile(c, false)
	for c in citta:
		_disegna(c)

# --- comandi -------------------------------------------------------------------------------
func _camera():
	perno.rotation_degrees = Vector3(pitch, yaw, 0)
	cam.position = cam.position.lerp(Vector3(0, 0, zoom), 0.25)

func _process(dt):
	var v := Vector3.ZERO
	if Input.is_key_pressed(KEY_W) or Input.is_key_pressed(KEY_UP): v.z -= 1
	if Input.is_key_pressed(KEY_S) or Input.is_key_pressed(KEY_DOWN): v.z += 1
	if Input.is_key_pressed(KEY_A) or Input.is_key_pressed(KEY_LEFT): v.x -= 1
	if Input.is_key_pressed(KEY_D) or Input.is_key_pressed(KEY_RIGHT): v.x += 1
	if Input.is_key_pressed(KEY_Q): yaw += dt * 60
	if Input.is_key_pressed(KEY_E): yaw -= dt * 60
	if v != Vector3.ZERO:
		perno.position += v.rotated(Vector3.UP, deg_to_rad(yaw)).normalized() * dt * zoom * 0.35
	_camera()
	_mira()

func _mira():
	cella_mouse = null
	if celle.is_empty():
		return
	var mp := get_viewport().get_mouse_position()
	var o := cam.project_ray_origin(mp)
	var d := cam.project_ray_normal(mp)
	if d.y >= -0.01:
		cursore.visible = false; anteprima.visible = false
		return
	# dal piano più alto in giù: il primo gradone che il raggio incontra
	var t: float = max(0.0, (4.0 - o.y) / d.y)
	var fine := (BASE - o.y) / d.y
	while t < fine:
		var p: Vector3 = o + d * t
		var c := Vector2i(roundi(p.x), roundi(p.z))
		if celle.has(c) and p.y <= max(top(c), MARE):
			cella_mouse = c
			break
		t += 0.04
	if cella_mouse == null:
		cursore.visible = false; anteprima.visible = false
		return
	var c: Vector2i = cella_mouse
	var ok: bool = costruibile(c) or (STRUMENTI[strumento].id == "demolisci" and citta.has(c))
	cursore.visible = true
	cursore.position = Vector3(c.x, top(c) + 0.02, c.y)
	(cursore.material_override as StandardMaterial3D).albedo_color = Color(1, 1, 1, 0.45) if ok else Color(1, 0.25, 0.2, 0.45)
	anteprima.visible = ok and STRUMENTI[strumento].id != "demolisci"
	anteprima.position = Vector3(c.x, celle[c].y + 0.02, c.y)
	anteprima.rotation.y = rot * PI / 2

func _unhandled_input(e):
	if e is InputEventMouseButton:
		if e.button_index == MOUSE_BUTTON_WHEEL_UP: zoom = max(8.0, zoom * 0.88)
		elif e.button_index == MOUSE_BUTTON_WHEEL_DOWN: zoom = min(900.0, zoom * 1.12)
		elif e.button_index in [MOUSE_BUTTON_RIGHT, MOUSE_BUTTON_MIDDLE]:
			if e.pressed:
				trascina = true; mosso = 0.0
			else:
				trascina = false
				if e.button_index == MOUSE_BUTTON_RIGHT and mosso < 6.0 and cella_mouse != null:
					_demolisci(cella_mouse)
		elif e.button_index == MOUSE_BUTTON_LEFT and e.pressed and cella_mouse != null:
			_costruisci_in(cella_mouse, STRUMENTI[strumento].id, rot)
	elif e is InputEventMouseMotion:
		if trascina:
			mosso += e.relative.length()
			yaw -= e.relative.x * 0.3
			pitch = clamp(pitch - e.relative.y * 0.2, -85.0, -15.0)
		elif Input.is_mouse_button_pressed(MOUSE_BUTTON_LEFT) and cella_mouse != null and STRUMENTI[strumento].id in ["strada", "demolisci", "pavement"]:
			_costruisci_in(cella_mouse, STRUMENTI[strumento].id, rot)
	elif e is InputEventKey and e.pressed and not e.echo:
		for i in STRUMENTI.size():
			if e.keycode == STRUMENTI[i].tasto:
				_scegli(i)
		if e.keycode == KEY_R:
			rot = (rot + 1) % 4
			_suona("rotate")
		elif e.keycode == KEY_X and cella_mouse != null:
			_demolisci(cella_mouse)
		elif e.keycode == KEY_F5:
			if FileAccess.file_exists("user://mondo.json"):
				DirAccess.remove_absolute(ProjectSettings.globalize_path("user://mondo.json"))
			_scarica()

# --- dimostrazione e foto (--demo, --foto=percorso.png) ---------------------------------------
func _demo():
	# un quartiere di prova sulla terra piana più vicina al centro, solo per controllare la resa
	var best := Vector2i.ZERO
	var punti := -1
	for c in celle:
		if not costruibile(c) or c.x % 2 != 0 or c.y % 2 != 0:
			continue
		var s := 0
		for y in range(-5, 6):
			for x in range(-5, 6):
				var q: Vector2i = c + Vector2i(x, y)
				if costruibile(q) and celle[q].liv == celle[c].liv:
					s += 1
		if s > punti:
			punti = s; best = c
	var case := ["building-small-a", "building-small-b", "building-small-c", "building-small-d", "building-garage", "building-small-a"]
	var r := RandomNumberGenerator.new()
	r.seed = 7
	for i in range(-5, 6):
		_costruisci_in(best + Vector2i(i, 0), "strada", 0, false)
		_costruisci_in(best + Vector2i(0, i), "strada", 0, false)
	for i in [-4, -2, 2, 4]:
		for j in [-1, 1]:
			for p in [Vector2i(i, j), Vector2i(j, i)]:
				var giro := 0 if p.y == -1 else 2 if p.y == 1 else 1 if p.x == -1 else 3
				_costruisci_in(best + p, case[r.randi() % case.size()], giro, false)
	_costruisci_in(best + Vector2i(1, 1), "pavement-fountain", 0, false)
	_costruisci_in(best + Vector2i(-1, -1), "pavement", 0, false)
	_costruisci_in(best + Vector2i(1, -1), "grass-trees", 0, false)
	perno.position = Vector3(best.x, 0, best.y)
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--zoom="): zoom = float(a.substr(7))

func _scatta():
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--zoomtot="): zoom *= float(a.substr(10))
		elif a.begins_with("--yaw="): yaw = float(a.substr(6))
	cam.position = Vector3(0, 0, zoom)
	for i in 40:
		await get_tree().process_frame
	await RenderingServer.frame_post_draw
	get_viewport().get_texture().get_image().save_png(foto)
	print("FOTO ", foto)
	get_tree().quit()
