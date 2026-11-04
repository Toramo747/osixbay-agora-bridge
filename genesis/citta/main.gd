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
var attr: CameraAttributesPractical

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
	env.adjustment_saturation = 1.05
	env.adjustment_brightness = 0.9
	env.tonemap_exposure = 0.9
	env.adjustment_contrast = 1.06
	var we := WorldEnvironment.new()
	we.environment = env
	add_child(we)
	attr = CameraAttributesPractical.new()
	attr.dof_blur_far_enabled = true
	attr.dof_blur_near_enabled = true
	attr.dof_blur_amount = 0.06
	we.camera_attributes = attr
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

# --- terreno: gradoni a griglia, coste fini, colori sfumati ---------------------------------
const SUB := 4                 # suddivisione delle celle di costa per bordi più fini
const TERRA := Color(0.50, 0.36, 0.25)
const ROCCIA := Color(0.47, 0.46, 0.49)
# palette unica, calda, intonata ai modelli Kenney
const P_PRATO := Color(0.46, 0.62, 0.32)
const P_PRATO2 := Color(0.55, 0.66, 0.35)
const P_SOTTOBOSCO := Color(0.34, 0.49, 0.26)
const P_SABBIA := Color(0.88, 0.77, 0.54)
const P_DESERTO := Color(0.90, 0.72, 0.46)
const P_ROCCIA := Color(0.55, 0.53, 0.55)
const P_NEVE := Color(0.95, 0.96, 0.99)
const P_FONDALE := Color(0.62, 0.66, 0.52)

var n2 := FastNoiseLite.new()  # macchie dei boschi e sfumature (solo resa)

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
	n2.seed = seme + 1
	n2.frequency = 0.06
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
	return celle[c].y + 0.06

func colore_suolo(x: float, z: float) -> Color:
	# colore continuo dal campo del costruttore: le soglie dei biomi diventano sfumature
	var f := campi(x, z)
	var h := f.x; var m := f.y
	var v := n2.get_noise_2d(x * 2.0, z * 2.0)
	var c := P_PRATO.lerp(P_PRATO2, clamp(0.5 + v * 0.8, 0.0, 1.0))
	c = c.lerp(P_SOTTOBOSCO, smoothstep(-0.02, 0.12, m))
	c = c.lerp(P_DESERTO, smoothstep(-0.24, -0.36, m))
	c = c.lerp(P_SABBIA, smoothstep(-0.09, -0.14, h))
	c = c.lerp(P_ROCCIA, smoothstep(0.40, 0.47, h))
	c = c.lerp(P_NEVE, smoothstep(0.62, 0.70, h))
	if h < -0.2:
		c = P_SABBIA.lerp(P_FONDALE, smoothstep(-0.2, -0.32, h)).darkened(smoothstep(-0.25, -0.6, h) * 0.45)
	return c.lightened(v * 0.04)

func _alt_sub(c: Vector2i, i: int, j: int) -> float:
	# altezza di un quarto di cella: le celle costruibili restano piane, l'acqua segue il campo continuo
	var px := c.x - 0.5 + (i + 0.5) / SUB
	var pz := c.y - 0.5 + (j + 0.5) / SUB
	var f := campi(px, pz)
	var b := bioma(f.x, f.y)
	if costruibile(c):
		return top(c) if b != "oceano" else quota(livello(f.x, b), b) + 0.06
	if celle[c].b == "oceano" and b != "oceano":
		return 0.0
	return quota(livello(f.x, b), b) + 0.06

func _terreno():
	# griglia fine: ogni cella è SUB×SUB quadratini; quelle uniformi si emettono come un solo quadrato
	var hs := {}
	var uni := {}
	for c in celle:
		var ref := -999.0
		var tutte := true
		for j in SUB:
			for i in SUB:
				var a := _alt_sub(c, i, j)
				hs[c * SUB + Vector2i(i, j)] = a
				if ref == -999.0: ref = a
				elif abs(a - ref) > 0.001: tutte = false
		uni[c] = tutte
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	var passo := 1.0 / SUB
	for c in celle:
		var x0: float = c.x - 0.5
		var z0: float = c.y - 0.5
		if uni[c]:
			var y: float = hs[c * SUB]
			_quad_col(st, x0, z0, 1.0, y)
		else:
			for j in SUB:
				for i in SUB:
					_quad_col(st, x0 + i * passo, z0 + j * passo, passo, hs[c * SUB + Vector2i(i, j)])
	# pareti tra quadratini (o celle) a quote diverse e bordo del diorama
	var dirs := [Vector2i(1, 0), Vector2i(-1, 0), Vector2i(0, 1), Vector2i(0, -1)]
	for c in celle:
		for j in SUB:
			for i in SUB:
				var s: Vector2i = c * SUB + Vector2i(i, j)
				var y: float = hs[s]
				for k in 4:
					var v: Vector2i = s + dirs[k]
					var vc := Vector2i(floori(float(v.x) / SUB), floori(float(v.y) / SUB))
					# i lati interni alle celle uniformi non servono
					if vc == c and uni[c]:
						continue
					var giu := BASE
					if hs.has(v):
						giu = hs[v]
					if giu >= y - 0.001:
						continue
					var sx := s.x * passo - 0.5; var sz := s.y * passo - 0.5
					var a: Vector3; var e: Vector3
					match k:
						0: a = Vector3(sx + passo, 0, sz + passo); e = Vector3(sx + passo, 0, sz)
						1: a = Vector3(sx, 0, sz); e = Vector3(sx, 0, sz + passo)
						2: a = Vector3(sx, 0, sz + passo); e = Vector3(sx + passo, 0, sz + passo)
						3: a = Vector3(sx + passo, 0, sz); e = Vector3(sx, 0, sz)
					var b: String = celle[c].b
					var cima := colore_suolo(a.x, a.z).darkened(0.2)
					var bande := [[y, max(giu, y - 0.07), cima]]
					var corpo := ROCCIA.darkened(0.12) if b == "montagna" else TERRA
					if b in ["spiaggia", "deserto", "oceano"]:
						corpo = (P_SABBIA if b != "deserto" else P_DESERTO).darkened(0.25)
					bande.append([y - 0.07, max(giu, -1.0), corpo])
					if not hs.has(v):
						bande.append([max(giu, -1.0), giu, ROCCIA.darkened(0.3)])
					for bd in bande:
						var t0: float = bd[0]; var t1: float = bd[1]
						if t0 - t1 < 0.001:
							continue
						st.set_color(bd[2])
						_quad(st, Vector3(a.x, t0, a.z), Vector3(e.x, t0, e.z), Vector3(e.x, t1, e.z), Vector3(a.x, t1, a.z))
	st.generate_normals()
	var mat := StandardMaterial3D.new()
	mat.vertex_color_use_as_albedo = true
	mat.roughness = 0.95
	var mi := MeshInstance3D.new()
	mi.mesh = st.commit()
	mi.material_override = mat
	mondo.add_child(mi)
	_hs = hs

var _hs := {}

func _quad_col(st: SurfaceTool, x0: float, z0: float, l: float, y: float):
	var p := [Vector3(x0, y, z0), Vector3(x0 + l, y, z0), Vector3(x0 + l, y, z0 + l), Vector3(x0, y, z0 + l)]
	for k in [0, 1, 2, 0, 2, 3]:
		st.set_color(colore_suolo(p[k].x, p[k].z))
		st.add_vertex(p[k])

func _quad(st: SurfaceTool, a: Vector3, b: Vector3, c: Vector3, d: Vector3):
	for v in [a, b, c, a, c, d]:
		st.add_vertex(v)

func _acqua():
	var mat := ShaderMaterial.new()
	mat.shader = load("res://acqua.gdshader")
	for z in zone:
		# superficie a griglia di mezza cella; nel colore la profondità del fondale
		var st := SurfaceTool.new()
		st.begin(Mesh.PRIMITIVE_TRIANGLES)
		var ox := z.x * 32 - 0.5
		var oz := z.y * 32 - 0.5
		var pr := {}
		for j in 65:
			for i in 65:
				var h := campi(ox + i * 0.5, oz + j * 0.5).x
				pr[Vector2i(i, j)] = clamp((-0.2 - h) / 0.35, 0.0, 1.0)
		for j in 64:
			for i in 64:
				var q := [Vector2i(i, j), Vector2i(i + 1, j), Vector2i(i + 1, j + 1), Vector2i(i, j + 1)]
				for k in [0, 1, 2, 0, 2, 3]:
					st.set_color(Color(pr[q[k]], 0, 0))
					st.add_vertex(Vector3(ox + q[k].x * 0.5, MARE, oz + q[k].y * 0.5))
		var w := MeshInstance3D.new()
		w.mesh = st.commit()
		w.material_override = mat
		w.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		mondo.add_child(w)
	# acqua vista di lato sul bordo del diorama
	var pareti := SurfaceTool.new()
	pareti.begin(Mesh.PRIMITIVE_TRIANGLES)
	var passo := 1.0 / SUB
	var dirs := [Vector2i(1, 0), Vector2i(-1, 0), Vector2i(0, 1), Vector2i(0, -1)]
	for s in _hs:
		var y: float = _hs[s]
		if y >= MARE:
			continue
		for k in 4:
			if _hs.has(s + dirs[k]):
				continue
			var sx: float = s.x * passo - 0.5; var sz: float = s.y * passo - 0.5
			var a: Vector3; var e: Vector3
			match k:
				0: a = Vector3(sx + passo, 0, sz + passo); e = Vector3(sx + passo, 0, sz)
				1: a = Vector3(sx, 0, sz); e = Vector3(sx, 0, sz + passo)
				2: a = Vector3(sx, 0, sz + passo); e = Vector3(sx + passo, 0, sz + passo)
				3: a = Vector3(sx + passo, 0, sz); e = Vector3(sx, 0, sz)
			_quad(pareti, Vector3(a.x, MARE, a.z), Vector3(e.x, MARE, e.z), Vector3(e.x, y, e.z), Vector3(a.x, y, a.z))
	pareti.generate_normals()
	var pm2 := StandardMaterial3D.new()
	pm2.albedo_color = Color(0.2, 0.55, 0.75, 0.6)
	pm2.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	pm2.roughness = 0.1
	var wi := MeshInstance3D.new()
	wi.mesh = pareti.commit()
	wi.material_override = pm2
	wi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	mondo.add_child(wi)

# --- forme generate dal codice (alberi, rocce, fiori…) --------------------------------------
func forma(parti: Array, colori: Array) -> ArrayMesh:
	# parti: una lista per superficie; la superficie 0 prende il colore dell'istanza
	var am := ArrayMesh.new()
	for s in parti.size():
		var st := SurfaceTool.new()
		st.begin(Mesh.PRIMITIVE_TRIANGLES)
		for p in parti[s]:
			var src := SurfaceTool.new()
			src.create_from(p[0], 0)
			var arr := src.commit_to_arrays()
			var verts: PackedVector3Array = arr[Mesh.ARRAY_VERTEX]
			for i in (arr[Mesh.ARRAY_INDEX] as PackedInt32Array):
				st.add_vertex(p[1] * verts[i])
		st.generate_normals()
		st.commit(am)
		var mat := StandardMaterial3D.new()
		mat.albedo_color = colori[s]
		mat.roughness = 0.85
		mat.vertex_color_use_as_albedo = s == 0
		am.surface_set_material(s, mat)
	return am

func palla(r: float, seg := 6, anelli := 3) -> SphereMesh:
	var s := SphereMesh.new()
	s.radius = r; s.height = r * 2; s.radial_segments = seg; s.rings = anelli
	return s

func cil(r: float, h: float, seg := 6) -> CylinderMesh:
	var c := CylinderMesh.new()
	c.top_radius = r * 0.8; c.bottom_radius = r; c.height = h; c.radial_segments = seg; c.rings = 1
	return c

func cono(r: float, h: float, seg := 7) -> CylinderMesh:
	var c := CylinderMesh.new()
	c.top_radius = 0.0; c.bottom_radius = r; c.height = h; c.radial_segments = seg; c.rings = 1
	return c

func T(pos: Vector3, sc := Vector3.ONE) -> Transform3D:
	return Transform3D(Basis().scaled(sc), pos)

func _forme() -> Dictionary:
	var legno := Color(0.45, 0.30, 0.2)
	var b := Color.WHITE
	return {
		"pino": forma([[[cono(0.24, 0.38), T(Vector3(0, 0.3, 0))], [cono(0.19, 0.32), T(Vector3(0, 0.47, 0))], [cono(0.13, 0.26), T(Vector3(0, 0.62, 0))]],
			[[cil(0.035, 0.18), T(Vector3(0, 0.09, 0))]]], [b, legno]),
		"quercia": forma([[[palla(0.22, 7, 4), T(Vector3(0, 0.42, 0), Vector3(1, 0.85, 1))], [palla(0.15), T(Vector3(0.12, 0.36, 0.06))], [palla(0.14), T(Vector3(-0.11, 0.38, -0.07))]],
			[[cil(0.04, 0.3), T(Vector3(0, 0.15, 0))]]], [b, legno]),
		"pioppo": forma([[[palla(0.13, 6, 4), T(Vector3(0, 0.52, 0), Vector3(1, 2.4, 1))]], [[cil(0.03, 0.22), T(Vector3(0, 0.11, 0))]]], [b, legno]),
		"cespuglio": forma([[[palla(0.13), T(Vector3(0, 0.07, 0), Vector3(1.2, 0.8, 1))], [palla(0.09), T(Vector3(0.1, 0.05, 0.04))]]], [b]),
		"fiori": forma([[[palla(0.025, 4, 2), T(Vector3(0, 0.03, 0))], [palla(0.025, 4, 2), T(Vector3(0.08, 0.03, 0.05))], [palla(0.025, 4, 2), T(Vector3(-0.06, 0.03, 0.07))], [palla(0.025, 4, 2), T(Vector3(0.03, 0.03, -0.08))]]], [b]),
		"roccia": forma([[[palla(0.3, 5, 3), T(Vector3(0, 0.08, 0), Vector3(1.2, 0.7, 1))], [palla(0.18, 5, 2), T(Vector3(0.22, 0.05, 0.12))]]], [b]),
		"argilla": forma([[[palla(0.3), T(Vector3(0, 0.04, 0), Vector3(1.3, 0.5, 1.1))], [palla(0.18), T(Vector3(0.25, 0.03, 0.15), Vector3(1, 0.6, 1))]]], [b]),
		"cactus": forma([[[cil(0.07, 0.5), T(Vector3(0, 0.25, 0))], [cil(0.045, 0.2), T(Vector3(0.1, 0.33, 0))], [cil(0.045, 0.16), T(Vector3(-0.1, 0.38, 0))]]], [b]),
		"pesci": forma([[[palla(0.07, 5, 2), T(Vector3(0.15, 0, 0), Vector3(1.8, 0.7, 0.8))], [palla(0.07, 5, 2), T(Vector3(-0.12, 0, 0.14), Vector3(1.8, 0.7, 0.8))], [palla(0.07, 5, 2), T(Vector3(-0.05, 0, -0.16), Vector3(1.8, 0.7, 0.8))]]], [b]),
	}

func _tessere():
	var forme := _forme()
	var posti := {}
	var r := RandomNumberGenerator.new()
	var fiori := [Color(0.98, 0.9, 0.35), Color(0.95, 0.55, 0.6), Color(0.98, 0.98, 0.95), Color(0.65, 0.55, 0.95)]
	for c in celle:
		var d = celle[c]
		r.seed = hash(Vector3i(c.x, c.y, seme))
		var b: String = d.b
		var ris: String = d.ris
		var y := top(c)
		var bosco: float = clamp(0.5 + n2.get_noise_2d(c.x, c.y) * 1.4, 0.0, 1.0)   # macchie e radure
		var punto := func(): return Vector3(c.x + r.randf_range(-0.42, 0.42), y, c.y + r.randf_range(-0.42, 0.42))
		var xf := func(p: Vector3, s: float): return Transform3D(Basis(Vector3.UP, r.randf() * TAU).scaled(Vector3.ONE * s), p)
		if b == "foresta" or ris == "legno":
			var k := 3 if ris == "legno" else int(round(bosco * 3.4 + r.randf() * 0.8 - 0.4))
			for i in clampi(k, 0, 4):
				var t := r.randf()
				var specie := "pino" if (d.h > 0.15 and t < 0.75) or t < 0.35 else "pioppo" if t < 0.45 else "quercia"
				var col := Color(0.18, 0.42, 0.25) if specie == "pino" else Color(0.33, 0.58, 0.24) if specie == "quercia" else Color(0.45, 0.62, 0.25)
				if r.randf() < 0.12 and specie == "quercia":
					col = Color(0.78, 0.55, 0.2)      # qualche chioma autunnale
				_metti(posti, specie, xf.call(punto.call(), r.randf_range(0.75, 1.35)), c, col.lightened(r.randf_range(-0.05, 0.1)))
			if r.randf() < 0.35:
				_metti(posti, "cespuglio", xf.call(punto.call(), r.randf_range(0.8, 1.4)), c, Color(0.3, 0.5, 0.22))
		elif b == "prateria":
			var v := r.randf()
			if v < 0.06 * bosco + 0.01:
				_metti(posti, "quercia", xf.call(punto.call(), r.randf_range(0.8, 1.3)), c, Color(0.38, 0.62, 0.26))
			elif v < 0.16:
				_metti(posti, "cespuglio", xf.call(punto.call(), r.randf_range(0.7, 1.2)), c, Color(0.38, 0.6, 0.26))
			if n2.get_noise_2d(c.x * 3.0, c.y * 3.0) > 0.25 and r.randf() < 0.6:
				_metti(posti, "fiori", xf.call(punto.call(), r.randf_range(0.8, 1.3)), c, fiori[r.randi() % fiori.size()])
		var p: Vector3 = punto.call()
		if ris == "pietra":
			_metti(posti, "roccia", xf.call(p, 1.6), c, Color(0.5, 0.5, 0.54))
		elif ris == "argilla":
			_metti(posti, "argilla", xf.call(Vector3(p.x, max(y, MARE), p.z), 1.0), c, Color(0.8, 0.42, 0.27))
		elif ris == "pesce":
			_metti(posti, "pesci", xf.call(Vector3(c.x, MARE - 0.08, c.y), 1.0), c, Color(1.0, 0.56, 0.24))
		elif b == "montagna" and r.randf() < 0.2:
			_metti(posti, "roccia", xf.call(p, r.randf_range(0.6, 1.2)), c, P_ROCCIA.lightened(r.randf() * 0.15))
		elif b == "deserto" and r.randf() < 0.07:
			_metti(posti, "cactus", xf.call(p, r.randf_range(0.8, 1.2)), c, Color(0.36, 0.58, 0.35))
		elif b in ["spiaggia", "deserto"] and r.randf() < 0.03:
			_metti(posti, "roccia", xf.call(p, 0.45), c, Color(0.7, 0.64, 0.56))
	for nome in posti:
		var mm := MultiMesh.new()
		mm.transform_format = MultiMesh.TRANSFORM_3D
		mm.use_colors = true
		mm.mesh = forme[nome]
		var lista: Array = posti[nome]
		mm.instance_count = lista.size()
		for i in lista.size():
			mm.set_instance_transform(i, lista[i][0])
			mm.set_instance_color(i, lista[i][2])
			if not veg.has(lista[i][1]):
				veg[lista[i][1]] = []
			veg[lista[i][1]].append([mm, i, lista[i][0]])
		var mmi := MultiMeshInstance3D.new()
		mmi.multimesh = mm
		if nome in ["fiori", "cespuglio"]:
			mmi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		mondo.add_child(mmi)

func _metti(posti: Dictionary, nome: String, xf: Transform3D, c: Vector2i, col := Color.WHITE):
	if not posti.has(nome):
		posti[nome] = []
	posti[nome].append([xf, c, col])

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
	g.position = Vector3(c.x, top(c) + 0.004, c.y)
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
	if attr:   # effetto plastico (tilt-shift): nitido al centro, sfocato davanti e dietro
		attr.dof_blur_far_distance = cam.position.z * 1.12
		attr.dof_blur_far_transition = cam.position.z * 0.5
		attr.dof_blur_near_distance = cam.position.z * 0.88
		attr.dof_blur_near_transition = cam.position.z * 0.3

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
	anteprima.position = Vector3(c.x, top(c) + 0.02, c.y)
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
		elif a.begins_with("--centro="):
			var cc = a.substr(9).split(",")
			perno.position = Vector3(float(cc[0]), 0, float(cc[1]))
		elif a.begins_with("--pitch="): pitch = float(a.substr(8))
		elif a.begins_with("--yaw="): yaw = float(a.substr(6))
	cam.position = Vector3(0, 0, zoom)
	for i in 40:
		await get_tree().process_frame
	await RenderingServer.frame_post_draw
	get_viewport().get_texture().get_image().save_png(foto)
	print("FOTO ", foto)
	get_tree().quit()
