extends Node3D
# Genesis (Godot 4.6.3, computer del ponte) — città secondo il concept art di Genesis (4/11/2026):
# palette, luce di tardo pomeriggio, pianeta con anello, architettura in intonaco e legno con volte curve.
# Il terreno si ricalcola dal seme e dalle zone di bots/genesi/mondo.json con la STESSA formula di
# bots/dati/genesi_costruttore.gd: biomi e risorse coincidono con il ponte. Rilievo, erba, case e luce
# sono solo resa grafica. Il giocatore costruisce su una griglia 1×1 che compare vicino al cursore.
# Comandi: WASD/frecce sposta · rotella zoom · tasto destro/centrale trascinato ruota · Q/E ruota
# 1–0 o barra = strumento · clic sinistro costruisci · R ruota · clic destro (fermo) o X demolisci · F5 ricarica il mondo

const URL := "https://raw.githubusercontent.com/Toramo747/osixbay-agora-bridge/main/bots/genesi/mondo.json"
const MARE := -0.02
const BASE := -2.4
const RIS := 0.5                     # passo della griglia del terreno (mezza cella)

var n := FastNoiseLite.new()
var n2 := FastNoiseLite.new()        # macchie dei boschi e varietà (solo resa)
var seme := 0
var zone: Array[Vector2i] = []
var celle := {}
var mondo: Node3D
var perno: Node3D
var cam: Camera3D
var attr: CameraAttributesPractical
var info: Label
var stato: Label
var barra: HBoxContainer
var yaw := 40.0
var pitch := -34.0
var zoom := 60.0
var trascina := false
var mosso := 0.0
var foto := ""
var demo := false
var mat_terreno: ShaderMaterial

var citta := {}
var nodi := {}
var veg := {}
var strumento := 0
var rot := 0
var cella_mouse = null
var anteprima: Node3D
var strade_mi: MeshInstance3D
var suoni := {}
var cache := {}

const STRUMENTI := [
	{"id": "strada", "nome": "Via", "tasto": KEY_1},
	{"id": "casa", "nome": "Casa", "tasto": KEY_2},
	{"id": "palazzina", "nome": "Palazzina", "tasto": KEY_3},
	{"id": "torre", "nome": "Torre", "tasto": KEY_4},
	{"id": "negozio", "nome": "Negozio", "tasto": KEY_5},
	{"id": "fienile", "nome": "Fienile", "tasto": KEY_6},
	{"id": "piazza", "nome": "Piazza", "tasto": KEY_7},
	{"id": "fontana", "nome": "Fontana", "tasto": KEY_8},
	{"id": "parco", "nome": "Parco", "tasto": KEY_9},
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

func costruibile(c: Vector2i) -> bool:
	return celle.has(c) and celle[c].b in ["prateria", "foresta", "deserto", "spiaggia"]

# --- rilievo morbido (solo resa) ------------------------------------------------------------
func alt(x: float, z: float) -> float:
	var h := campi(x, z).x
	if h < -0.2:
		return -0.05 + (h + 0.2) * 5.0
	return -0.05 + (h + 0.2) * 2.6 + smoothstep(0.38, 0.72, h) * 5.5

func alt_cella(c: Vector2i) -> float:
	# piano d'appoggio degli edifici: il punto più basso della cella, così nessun angolo resta sospeso
	var m := alt(c.x, c.y)
	for d in [Vector2(-0.45, -0.45), Vector2(0.45, -0.45), Vector2(0.45, 0.45), Vector2(-0.45, 0.45)]:
		m = minf(m, alt(c.x + d.x, c.y + d.y))
	return m

# --- palette del concept art di Genesis (tavola «Palette, luce e regole visive») -----------------
const P_PRATO := Color("7FAE4E")        # erba primaverile
const P_PRATO2 := Color("9BBE58")       # erba più chiara e dorata
const P_SOTTOBOSCO := Color("4E7F37")   # bosco profondo
const P_SABBIA := Color("D6B273")       # sabbia e terre chiare
const P_DESERTO := Color("C9A262")      # terre aride
const P_ROCCIA := Color("7A746E")       # roccia e scogli
const P_NEVE := Color("F2F5F8")         # pietra chiara / neve
const P_FONDALE := Color("8FC9B8")      # fondale basso, sabbia sotto l'acqua chiara
const P_TERRA := Color("8F6A43")        # terra fertile
const P_ESOTICO := Color("3FA58F")      # verde-azzurro, foglie esotiche
const P_VIOLA := Color("B96AD8")        # viola floreale, alberi alieni
const P_INTONACO := Color("E6D9C4")     # intonaco e superfici principali
const P_LEGNO := Color("9B6A3C")        # tetti, legno e strutture
const P_ORO := Color("F4C769")          # oro caldo, insegne e lumi
const P_LUCE := Color("71DDF2")         # luce magica, cristalli e bagliori
const P_STENDARDO := Color("A8343C")    # stendardi rossi del concept

func colore_suolo(x: float, z: float) -> Color:
	var f := campi(x, z)
	var h := f.x
	var m := f.y
	var v := n2.get_noise_2d(x * 2.0, z * 2.0)
	var c := P_PRATO.lerp(P_PRATO2, clampf(0.5 + v, 0.0, 1.0))
	c = c.lerp(P_SOTTOBOSCO, smoothstep(-0.02, 0.14, m))
	c = c.lerp(P_DESERTO, smoothstep(-0.24, -0.36, m))
	c = c.lerp(P_SABBIA, smoothstep(-0.10, -0.16, h))
	c = c.lerp(P_ROCCIA, smoothstep(0.42, 0.5, h))
	c = c.lerp(P_NEVE, smoothstep(0.64, 0.72, h))
	if h < -0.2:
		c = P_SABBIA.lerp(P_FONDALE, smoothstep(-0.2, -0.3, h))
	return c

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
	info.text = "Genesis — scarico il mondo…"
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
	n2.seed = seme + 1
	n2.frequency = 0.06
	zone.clear()
	for z in d.zone:
		var p = str(z).split(",")
		zone.append(Vector2i(int(p[0]), int(p[1])))
	if mondo:
		mondo.queue_free()
	mondo = Node3D.new()
	add_child(mondo)
	celle.clear(); nodi.clear(); veg.clear(); citta.clear()
	_costruisci()
	_carica_citta()
	if demo:
		_demo()
	info.text = "Genesis   ·   %d zone   ·   seme %d" % [zone.size(), seme]
	if foto != "":
		_scatta.call_deferred()

# --- ambiente: luce calda di fine giornata ---------------------------------------------------
func _scena():
	var env := Environment.new()
	var cielo := Sky.new()
	var sm := ProceduralSkyMaterial.new()
	# cielo diurno #87B8E8 che sale verso il serale #5A6FB1, orizzonte caldo di tardo pomeriggio
	sm.sky_top_color = Color("5A6FB1").lerp(Color("87B8E8"), 0.45)
	sm.sky_horizon_color = Color(0.88, 0.84, 0.82)
	sm.sky_curve = 0.09
	sm.ground_horizon_color = Color(0.82, 0.80, 0.76)
	sm.ground_bottom_color = Color(0.46, 0.50, 0.58)
	sm.sun_angle_max = 22.0
	sm.sun_curve = 0.08
	cielo.sky_material = sm
	env.background_mode = Environment.BG_SKY
	env.sky = cielo
	# ombre blu-violetto morbide: luce ambiente fredda contro il sole dorato
	env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	env.ambient_light_color = Color(0.66, 0.68, 0.88)
	env.ambient_light_energy = 0.9
	env.tonemap_mode = Environment.TONE_MAPPER_AGX
	env.ssao_enabled = true
	env.ssao_radius = 0.6
	env.ssao_intensity = 1.2
	env.glow_enabled = true
	env.glow_intensity = 0.6
	env.glow_bloom = 0.06
	env.glow_hdr_threshold = 1.1
	# nebbia poca, azzurro-grigia
	env.fog_enabled = true
	env.fog_light_color = Color(0.72, 0.79, 0.90)
	env.fog_density = 0.0028
	env.fog_aerial_perspective = 0.6
	env.fog_sky_affect = 0.08
	env.adjustment_enabled = true
	env.adjustment_saturation = 1.12
	env.adjustment_contrast = 1.03
	var we := WorldEnvironment.new()
	we.environment = env
	attr = CameraAttributesPractical.new()
	attr.dof_blur_far_enabled = true
	attr.dof_blur_near_enabled = true
	attr.dof_blur_amount = 0.05
	we.camera_attributes = attr
	add_child(we)
	var sole := DirectionalLight3D.new()
	# sole caldo dorato di tardo pomeriggio (ora standard del concept)
	sole.rotation_degrees = Vector3(-27, -128, 0)
	sole.light_color = Color(1.0, 0.86, 0.66)
	sole.light_energy = 1.75
	sole.shadow_enabled = true
	sole.shadow_blur = 1.8
	sole.directional_shadow_max_distance = 140.0
	add_child(sole)
	_cielo_pianeti()

func _astro(r: float, col: Color, pos: Vector3, ombra := 0.0) -> MeshInstance3D:
	var a := MeshInstance3D.new()
	a.mesh = palla(r, 40, 20)
	var m := StandardMaterial3D.new()
	m.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	m.albedo_color = col
	m.disable_fog = true
	if ombra > 0.0:
		# il lato in ombra si tinge del cielo serale
		m.shading_mode = BaseMaterial3D.SHADING_MODE_PER_PIXEL
		m.roughness = 1.0
		m.albedo_color = col
		m.emission_enabled = true
		m.emission = Color("5A6FB1") * ombra
	a.material_override = m
	a.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	a.position = pos
	return a

func _cielo_pianeti():
	# grande pianeta chiaro, luna minore e anello sottile spezzato (tavola «Luce e atmosfera»)
	var pianeta := _astro(150.0, Color(0.84, 0.88, 0.97), Vector3(-300, 200, -1150), 0.55)
	add_child(pianeta)
	var luna := _astro(22.0, Color(0.95, 0.93, 0.90), Vector3(150, 330, -1250))
	add_child(luna)
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	var r0 := 185.0
	var r1 := 215.0
	var passi := 72
	for i in passi:
		var a0 := TAU * i / passi
		var a1 := TAU * (i + 1) / passi
		# l'anello è spezzato: manca un arco in alto a destra
		if a0 > 0.35 and a0 < 1.05:
			continue
		var p := [Vector3(cos(a0) * r0, 0, sin(a0) * r0), Vector3(cos(a0) * r1, 0, sin(a0) * r1),
			Vector3(cos(a1) * r1, 0, sin(a1) * r1), Vector3(cos(a1) * r0, 0, sin(a1) * r0)]
		for idx in [0, 1, 2, 0, 2, 3, 0, 2, 1, 0, 3, 2]:
			st.add_vertex(p[idx])
	var anello := MeshInstance3D.new()
	anello.mesh = st.commit()
	var am := StandardMaterial3D.new()
	am.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	am.albedo_color = Color(0.92, 0.94, 1.0, 0.55)
	am.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	am.cull_mode = BaseMaterial3D.CULL_DISABLED
	am.disable_fog = true
	anello.material_override = am
	anello.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	anello.position = pianeta.position
	anello.rotation_degrees = Vector3(-72, 0, 18)
	add_child(anello)
	perno = Node3D.new()
	add_child(perno)
	cam = Camera3D.new()
	cam.fov = 26.0
	cam.far = 2000.0
	perno.add_child(cam)
	anteprima = Node3D.new()
	add_child(anteprima)

func _interfaccia():
	var cl := CanvasLayer.new()
	add_child(cl)
	var tema := Theme.new()
	tema.default_font = load("res://kenney/font/lilita_one_regular.ttf")
	tema.default_font_size = 19
	var pill := StyleBoxFlat.new()
	# pannelli in pietra chiara con bordo di legno caldo (tavola «Interfaccia»)
	pill.bg_color = Color(0.96, 0.93, 0.87, 0.92)
	pill.set_corner_radius_all(16)
	pill.border_color = P_LEGNO.lightened(0.15)
	pill.set_border_width_all(2)
	pill.shadow_color = Color(0.2, 0.12, 0.05, 0.22)
	pill.shadow_size = 8
	pill.content_margin_left = 18; pill.content_margin_right = 18; pill.content_margin_top = 8; pill.content_margin_bottom = 8
	var testo := Color(0.30, 0.22, 0.14)
	var su := PanelContainer.new()
	su.theme = tema
	su.position = Vector2(18, 16)
	su.add_theme_stylebox_override("panel", pill)
	var col := VBoxContainer.new()
	su.add_child(col)
	info = Label.new()
	info.add_theme_color_override("font_color", testo)
	stato = Label.new()
	stato.add_theme_font_size_override("font_size", 14)
	stato.add_theme_color_override("font_color", Color(0.45, 0.42, 0.4))
	col.add_child(info)
	col.add_child(stato)
	cl.add_child(su)
	var giu := PanelContainer.new()
	giu.theme = tema
	giu.add_theme_stylebox_override("panel", pill)
	giu.anchor_left = 0.5; giu.anchor_right = 0.5; giu.anchor_top = 1.0; giu.anchor_bottom = 1.0
	giu.grow_horizontal = Control.GROW_DIRECTION_BOTH
	giu.grow_vertical = Control.GROW_DIRECTION_BEGIN
	giu.offset_bottom = -18
	barra = HBoxContainer.new()
	barra.add_theme_constant_override("separation", 4)
	giu.add_child(barra)
	var normale := StyleBoxFlat.new()
	normale.bg_color = Color(0, 0, 0, 0)
	normale.set_corner_radius_all(12)
	normale.content_margin_left = 12; normale.content_margin_right = 12; normale.content_margin_top = 6; normale.content_margin_bottom = 6
	var attivo := normale.duplicate() as StyleBoxFlat
	attivo.bg_color = P_ORO
	var sopra := normale.duplicate() as StyleBoxFlat
	sopra.bg_color = Color(0.90, 0.84, 0.74)
	for i in STRUMENTI.size():
		var b := Button.new()
		b.text = STRUMENTI[i].nome
		b.toggle_mode = true
		b.focus_mode = Control.FOCUS_NONE
		b.add_theme_stylebox_override("normal", normale)
		b.add_theme_stylebox_override("hover", sopra)
		b.add_theme_stylebox_override("pressed", attivo)
		b.add_theme_stylebox_override("hover_pressed", attivo)
		b.add_theme_color_override("font_color", testo)
		b.add_theme_color_override("font_hover_color", testo)
		b.add_theme_color_override("font_pressed_color", Color(0.28, 0.18, 0.08))
		b.add_theme_color_override("font_hover_pressed_color", Color(0.28, 0.18, 0.08))
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
	if id != "demolisci" and id != "strada":
		anteprima.add_child(_edificio(id, Vector2i(0, 0), true))
	_suona("toggle")
	stato.text = "%s  ·  clic: costruisci  ·  R: ruota  ·  tasto destro: demolisci" % STRUMENTI[i].nome

func _suona(s: String):
	if suoni.has(s):
		suoni[s].play()

# --- terreno ---------------------------------------------------------------------------------
func _costruisci():
	var lo := zone[0]
	var hi := zone[0]
	for z in zone:
		lo = Vector2i(mini(lo.x, z.x), mini(lo.y, z.y))
		hi = Vector2i(maxi(hi.x, z.x), maxi(hi.y, z.y))
		for y in 32:
			for x in 32:
				var w := Vector2i(z.x * 32 + x, z.y * 32 + y)
				var f := campi(w.x, w.y)
				var b := bioma(f.x, f.y)
				celle[w] = {"b": b, "h": f.x, "ris": risorsa(w, b)}
	perno.position = Vector3((lo.x + hi.x + 1) * 16.0, 0, (lo.y + hi.y + 1) * 16.0)
	zoom = maxi(hi.x - lo.x + 1, hi.y - lo.y + 1) * 32.0 * 2.6
	mat_terreno = ShaderMaterial.new()
	mat_terreno.shader = load("res://terreno.gdshader")
	var zset := {}
	for z in zone:
		zset[z] = true
	for z in zone:
		_zona(z, zset)
	_acqua()
	_natura()
	strade_mi = MeshInstance3D.new()
	mondo.add_child(strade_mi)

func _zona(z: Vector2i, zset: Dictionary):
	var k := int(32 / RIS)
	var ox := z.x * 32 - 0.5
	var oz := z.y * 32 - 0.5
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	for j in k + 1:
		for i in k + 1:
			var x := ox + i * RIS
			var zz := oz + j * RIS
			st.set_color(colore_suolo(x, zz))
			st.add_vertex(Vector3(x, alt(x, zz), zz))
	for j in k:
		for i in k:
			var a := j * (k + 1) + i
			var b := a + 1
			var c := a + k + 1
			var d := c + 1
			for idx in [a, b, d, a, d, c]:
				st.add_index(idx)
	st.generate_normals()
	var mi := MeshInstance3D.new()
	mi.mesh = st.commit()
	mi.material_override = mat_terreno
	mondo.add_child(mi)
	# bordo del plastico: terra a strati dove non c'è una zona vicina
	var bordo := SurfaceTool.new()
	bordo.begin(Mesh.PRIMITIVE_TRIANGLES)
	var lati := [[Vector2i(0, -1), Vector2(0, 0), Vector2(1, 0)], [Vector2i(1, 0), Vector2(1, 0), Vector2(1, 1)],
		[Vector2i(0, 1), Vector2(1, 1), Vector2(0, 1)], [Vector2i(-1, 0), Vector2(0, 1), Vector2(0, 0)]]
	for l in lati:
		if zset.has(z + l[0]):
			continue
		for i in k:
			var p0: Vector2 = Vector2(ox, oz) + (l[1] as Vector2) * 32.0 + ((l[2] as Vector2) - (l[1] as Vector2)) * 32.0 * float(i) / k
			var p1: Vector2 = Vector2(ox, oz) + (l[1] as Vector2) * 32.0 + ((l[2] as Vector2) - (l[1] as Vector2)) * 32.0 * float(i + 1) / k
			var y0 := alt(p0.x, p0.y)
			var y1 := alt(p1.x, p1.y)
			var strati := [[0.0, 0.12, colore_suolo(p0.x, p0.y).darkened(0.25)], [0.12, 0.9, P_TERRA], [0.9, 99.0, P_TERRA.darkened(0.3)]]
			for s in strati:
				var a0 := maxf(y0 - s[0], BASE); var a1 := maxf(y1 - s[0], BASE)
				var b0 := maxf(y0 - s[1], BASE); var b1 := maxf(y1 - s[1], BASE)
				if a0 <= BASE and a1 <= BASE:
					continue
				bordo.set_color(s[2])
				for v in [Vector3(p0.x, a0, p0.y), Vector3(p1.x, b1, p1.y), Vector3(p1.x, a1, p1.y), Vector3(p0.x, a0, p0.y), Vector3(p0.x, b0, p0.y), Vector3(p1.x, b1, p1.y)]:
					bordo.add_vertex(v)
			if y0 < MARE or y1 < MARE:
				pass
	bordo.generate_normals()
	var bm := StandardMaterial3D.new()
	bm.vertex_color_use_as_albedo = true
	bm.roughness = 1.0
	var bmi := MeshInstance3D.new()
	bmi.mesh = bordo.commit()
	bmi.material_override = bm
	mondo.add_child(bmi)

func _acqua():
	var mat := ShaderMaterial.new()
	mat.shader = load("res://acqua.gdshader")
	for z in zone:
		var st := SurfaceTool.new()
		st.begin(Mesh.PRIMITIVE_TRIANGLES)
		var ox := z.x * 32 - 0.5
		var oz := z.y * 32 - 0.5
		var pr := {}
		for j in 65:
			for i in 65:
				var y := alt(ox + i * 0.5, oz + j * 0.5)
				pr[Vector2i(i, j)] = clampf((MARE - y) / 1.2, 0.0, 1.0)
		for j in 64:
			for i in 64:
				var q := [Vector2i(i, j), Vector2i(i + 1, j), Vector2i(i + 1, j + 1), Vector2i(i, j + 1)]
				var tutti_terra := true
				for p in q:
					if pr[p] > 0.0: tutti_terra = false
				if tutti_terra and alt(ox + i * 0.5, oz + j * 0.5) > 0.3:
					continue
				for idx in [0, 1, 2, 0, 2, 3]:
					st.set_color(Color(pr[q[idx]], 0, 0))
					st.add_vertex(Vector3(ox + q[idx].x * 0.5, MARE, oz + q[idx].y * 0.5))
		var w := MeshInstance3D.new()
		w.mesh = st.commit()
		w.material_override = mat
		w.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		mondo.add_child(w)

# --- forme morbide generate dal codice ---------------------------------------------------------
func T(pos: Vector3, sc := Vector3.ONE, ry := 0.0) -> Transform3D:
	return Transform3D(Basis(Vector3.UP, ry).scaled(sc), pos)

func palla(r: float, seg := 12, anelli := 7) -> SphereMesh:
	var s := SphereMesh.new()
	s.radius = r; s.height = r * 2; s.radial_segments = seg; s.rings = anelli
	return s

func cil(r: float, h: float, seg := 10, cima := 0.85) -> CylinderMesh:
	var c := CylinderMesh.new()
	c.top_radius = r * cima; c.bottom_radius = r; c.height = h; c.radial_segments = seg; c.rings = 1
	return c

func forma_morbida(parti: Array, colori: Array) -> ArrayMesh:
	# parti: una lista per superficie; la superficie 0 prende il colore dell'istanza
	var am := ArrayMesh.new()
	for s in parti.size():
		var st := SurfaceTool.new()
		st.begin(Mesh.PRIMITIVE_TRIANGLES)
		for p in parti[s]:
			st.append_from(p[0], 0, p[1])
		st.commit(am)
		var mat := StandardMaterial3D.new()
		mat.albedo_color = colori[s]
		mat.roughness = 0.9
		mat.vertex_color_use_as_albedo = s == 0
		mat.diffuse_mode = BaseMaterial3D.DIFFUSE_LAMBERT_WRAP
		am.surface_set_material(s, mat)
	return am

func _ciuffo() -> ArrayMesh:
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	var r := RandomNumberGenerator.new()
	r.seed = 3
	for i in 7:
		var a := r.randf() * TAU
		var o := Vector3(r.randf_range(-0.12, 0.12), 0, r.randf_range(-0.12, 0.12))
		var d := Vector3(cos(a), 0, sin(a)) * 0.018
		var h := r.randf_range(0.12, 0.2)
		var cima := o + Vector3(r.randf_range(-0.03, 0.03), h, r.randf_range(-0.03, 0.03))
		for v in [o - d, o + d, cima]:
			st.add_vertex(v)
	var m := st.commit()
	var mat := ShaderMaterial.new()
	mat.shader = load("res://erba.gdshader")
	m.surface_set_material(0, mat)
	return m

func _natura():
	var legno := Color(0.47, 0.34, 0.25)
	var forme := {
		"tondo": forma_morbida([[[palla(0.24), T(Vector3(0, 0.46, 0), Vector3(1, 0.92, 1))], [palla(0.15), T(Vector3(0.14, 0.38, 0.05))], [palla(0.14), T(Vector3(-0.12, 0.4, -0.07))]],
			[[cil(0.035, 0.32, 8), T(Vector3(0, 0.16, 0))]]], [Color.WHITE, legno]),
		"conifera": forma_morbida([[[cil(0.2, 0.34, 12, 0.0), T(Vector3(0, 0.3, 0))], [cil(0.15, 0.28, 12, 0.0), T(Vector3(0, 0.46, 0))], [cil(0.1, 0.22, 12, 0.0), T(Vector3(0, 0.6, 0))]],
			[[cil(0.03, 0.16, 8), T(Vector3(0, 0.08, 0))]]], [Color.WHITE, legno]),
		"slanciato": forma_morbida([[[palla(0.13, 10, 8), T(Vector3(0, 0.55, 0), Vector3(1, 2.3, 1))]], [[cil(0.028, 0.24, 8), T(Vector3(0, 0.12, 0))]]], [Color.WHITE, Color(0.85, 0.83, 0.78)]),
		"cespuglio": forma_morbida([[[palla(0.12), T(Vector3(0, 0.06, 0), Vector3(1.25, 0.8, 1))], [palla(0.08), T(Vector3(0.1, 0.05, 0.04))]]], [Color.WHITE]),
		"fiori": forma_morbida([[[palla(0.022, 6, 3), T(Vector3(0, 0.05, 0))], [palla(0.022, 6, 3), T(Vector3(0.07, 0.04, 0.05))], [palla(0.022, 6, 3), T(Vector3(-0.05, 0.045, 0.07))], [palla(0.022, 6, 3), T(Vector3(0.03, 0.05, -0.07))]]], [Color.WHITE]),
		"sasso": forma_morbida([[[palla(0.26, 8, 5), T(Vector3(0, 0.05, 0), Vector3(1.3, 0.6, 1))], [palla(0.15, 8, 5), T(Vector3(0.2, 0.03, 0.12), Vector3(1, 0.7, 1))]]], [Color.WHITE]),
		"argilla": forma_morbida([[[palla(0.26, 10, 5), T(Vector3(0, 0.0, 0), Vector3(1.3, 0.45, 1.1))], [palla(0.16, 10, 5), T(Vector3(0.24, 0.0, 0.14), Vector3(1, 0.5, 1))]]], [Color.WHITE]),
		"cactus": forma_morbida([[[cil(0.06, 0.46, 10, 0.9), T(Vector3(0, 0.23, 0))], [palla(0.054, 10, 5), T(Vector3(0, 0.46, 0))], [cil(0.04, 0.16, 8), T(Vector3(0.09, 0.32, 0))], [cil(0.04, 0.13, 8), T(Vector3(-0.09, 0.36, 0))]]], [Color.WHITE]),
		"pesci": forma_morbida([[[palla(0.06, 8, 4), T(Vector3(0.14, 0, 0), Vector3(1.8, 0.7, 0.8))], [palla(0.06, 8, 4), T(Vector3(-0.1, 0, 0.13), Vector3(1.8, 0.7, 0.8))], [palla(0.06, 8, 4), T(Vector3(-0.04, 0, -0.15), Vector3(1.8, 0.7, 0.8))]]], [Color.WHITE]),
		"erba": _ciuffo(),
		"gigante": forma_morbida([[[palla(0.5, 14, 6), T(Vector3(0, 1.55, 0), Vector3(1.5, 0.32, 1.5))], [palla(0.36, 14, 6), T(Vector3(0.1, 1.75, 0.05), Vector3(1.4, 0.36, 1.4))], [palla(0.42, 14, 6), T(Vector3(-0.35, 1.3, 0.2), Vector3(1.1, 0.3, 1.1))]],
			[[cil(0.16, 0.5, 10, 0.7), T(Vector3(0, 0.25, 0))], [cil(0.11, 0.55, 10, 0.75), T(Vector3(0.04, 0.75, 0.02))], [cil(0.08, 0.45, 10, 0.8), T(Vector3(0.0, 1.2, 0.0))], [palla(0.2, 10, 5), T(Vector3(0, 0.06, 0), Vector3(1.6, 0.5, 1.6))]]], [Color.WHITE, Color(0.46, 0.36, 0.34)]),
		"bulbo": _bulbo(),
	}
	var posti := {}
	var r := RandomNumberGenerator.new()
	var fiori := [Color(1.0, 0.86, 0.4), Color(0.98, 0.6, 0.66), Color(1.0, 0.98, 0.94), Color(0.72, 0.62, 0.98)]
	for c in celle:
		var d = celle[c]
		r.seed = hash(Vector3i(c.x, c.y, seme))
		var b: String = d.b
		var ris: String = d.ris
		var h: float = d.h
		var bosco: float = clampf(0.5 + n2.get_noise_2d(c.x, c.y) * 1.4, 0.0, 1.0)
		var punto := func() -> Vector3:
			var x: float = c.x + r.randf_range(-0.45, 0.45)
			var z: float = c.y + r.randf_range(-0.45, 0.45)
			return Vector3(x, alt(x, z) - 0.01, z)
		var xf := func(p: Vector3, s: float) -> Transform3D:
			return Transform3D(Basis(Vector3.UP, r.randf() * TAU).scaled(Vector3.ONE * s), p)
		if b == "foresta" or ris == "legno":
			var k := 3 if ris == "legno" else int(round(bosco * 3.2 + r.randf() * 0.8 - 0.5))
			for i in clampi(k, 0, 4):
				var t := r.randf()
				var specie := "conifera" if (h > 0.12 and t < 0.7) or t < 0.3 else "slanciato" if t < 0.42 else "tondo"
				# foresta del concept: bosco profondo, chiome esotiche verde-azzurre, alberi in fiore viola e qualche chioma arancio
				var col := P_SOTTOBOSCO.darkened(0.1) if specie == "conifera" else P_PRATO.lerp(P_SOTTOBOSCO, 0.4) if specie == "tondo" else P_ESOTICO
				if specie == "tondo" and r.randf() < 0.2:
					col = [P_VIOLA, P_VIOLA, Color(0.88, 0.50, 0.26), P_ESOTICO][r.randi() % 4]
				_metti(posti, specie, xf.call(punto.call(), r.randf_range(0.8, 1.35)), c, col.lightened(r.randf_range(-0.04, 0.08)))
			if r.randf() < 0.03 * bosco:
				_metti(posti, "gigante", xf.call(punto.call(), r.randf_range(1.6, 2.6)), c, [P_ESOTICO, P_SOTTOBOSCO.lightened(0.1), P_ESOTICO.darkened(0.1), P_VIOLA.darkened(0.1), P_SOTTOBOSCO, Color(0.86, 0.46, 0.24)][r.randi() % 6].lightened(r.randf() * 0.08))
			if r.randf() < 0.035:
				_metti(posti, "bulbo", xf.call(punto.call(), r.randf_range(0.8, 1.4)), c, P_ESOTICO.darkened(0.2))
			if r.randf() < 0.4:
				_metti(posti, "cespuglio", xf.call(punto.call(), r.randf_range(0.8, 1.4)), c, P_PRATO.lerp(P_SOTTOBOSCO, 0.5))
		if b in ["prateria", "foresta"]:
			for i in (3 if b == "prateria" else 2):
				_metti(posti, "erba", xf.call(punto.call(), r.randf_range(0.8, 1.3)), c, colore_suolo(c.x, c.y).lightened(0.08))
		if b == "prateria":
			var v := r.randf()
			if v < 0.05 * bosco + 0.008:
				# albero da prateria a chioma ampia; uno su sei è un arbusto fiorito viola
				_metti(posti, "tondo", xf.call(punto.call(), r.randf_range(0.9, 1.3)), c, P_VIOLA if r.randf() < 0.17 else P_PRATO.lerp(P_SOTTOBOSCO, 0.25))
			elif v < 0.12:
				_metti(posti, "cespuglio", xf.call(punto.call(), r.randf_range(0.7, 1.2)), c, P_PRATO.lerp(P_SOTTOBOSCO, 0.35))
			if n2.get_noise_2d(c.x * 3.0, c.y * 3.0) > 0.22 and r.randf() < 0.7:
				_metti(posti, "fiori", xf.call(punto.call(), r.randf_range(0.8, 1.3)), c, fiori[r.randi() % fiori.size()])
		var p: Vector3 = punto.call()
		# risorse del concept: pietra (affioramenti), argilla (terra rossastra), pesce (banchi), legno (sopra)
		if ris == "pietra":
			_metti(posti, "sasso", xf.call(p, 1.7), c, P_ROCCIA.lightened(0.08))
		elif ris == "argilla":
			_metti(posti, "argilla", xf.call(Vector3(p.x, maxf(p.y, MARE), p.z), 1.0), c, Color(0.76, 0.42, 0.28))
		elif ris == "pesce":
			_metti(posti, "pesci", xf.call(Vector3(c.x, MARE - 0.1, c.y), 1.0), c, Color(0.95, 0.62, 0.30))
		elif b == "montagna" and r.randf() < 0.18:
			_metti(posti, "sasso", xf.call(p, r.randf_range(0.6, 1.2)), c, P_ROCCIA.lightened(r.randf() * 0.12))
		elif b == "deserto" and r.randf() < 0.07:
			_metti(posti, "cactus", xf.call(p, r.randf_range(0.8, 1.2)), c, P_PRATO.lerp(P_ESOTICO, 0.4))
		elif b in ["spiaggia", "deserto"] and r.randf() < 0.03:
			_metti(posti, "sasso", xf.call(p, 0.45), c, P_SABBIA.darkened(0.15))
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
		if nome in ["fiori", "cespuglio", "erba"]:
			mmi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		mondo.add_child(mmi)

func _bulbo() -> ArrayMesh:
	# pianta aliena: stelo curvo e bulbo che brilla di luce propria
	var m := forma_morbida([[[cil(0.025, 0.3, 8), T(Vector3(0, 0.15, 0))], [cil(0.02, 0.22, 8), T(Vector3(0.03, 0.4, 0))]], [[palla(0.07, 10, 6), T(Vector3(0.04, 0.55, 0), Vector3(1, 1.3, 1))]]], [Color.WHITE, P_LUCE.lightened(0.3)])
	var luce := m.surface_get_material(1) as StandardMaterial3D
	luce.emission_enabled = true
	luce.emission = P_LUCE
	luce.emission_energy_multiplier = 2.2
	return m

func _luminoso(mesh: Mesh, col: Color, energia := 2.5) -> MeshInstance3D:
	# cristalli e lumi: materiale emissivo nella luce magica del concept
	var mi := MeshInstance3D.new()
	mi.mesh = mesh
	var mat := StandardMaterial3D.new()
	mat.albedo_color = col.lightened(0.35)
	mat.emission_enabled = true
	mat.emission = col
	mat.emission_energy_multiplier = energia
	mat.roughness = 0.3
	mi.material_override = mat
	mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	return mi

func _metti(posti: Dictionary, nome: String, xf: Transform3D, c: Vector2i, col := Color.WHITE):
	if not posti.has(nome):
		posti[nome] = []
	posti[nome].append([xf, c, col])

func _veg_visibile(c: Vector2i, si: bool):
	for v in veg.get(c, []):
		v[0].set_instance_transform(v[1], v[2] if si else Transform3D(Basis().scaled(Vector3.ONE * 0.0001), v[2].origin))

# --- edifici generati dal codice (tavola «Architettura modulare»: intonaco, legno caldo, volte curve) ---
const MURI := [Color("E6D9C4"), Color("EFE4D2"), Color("DCCDB3"), Color("F2EADB"), Color("E2D2B8"), Color("EADFCB")]
const TETTI := [Color("9B6A3C"), Color("A97545"), Color("8A5D34"), Color("B07E4C"), Color("946439")]
const VETRO := Color(0.46, 0.76, 0.82)          # vetro che riflette la luce turchese
const LEGNO_P := Color("7E5430")
const PIETRA := Color("D9D3C8")                  # pietra chiara lavorata

func _box(st: SurfaceTool, c: Vector3, s: Vector3, col: Color):
	var x0 := c.x - s.x / 2; var x1 := c.x + s.x / 2
	var y0 := c.y; var y1 := c.y + s.y
	var z0 := c.z - s.z / 2; var z1 := c.z + s.z / 2
	st.set_color(col)
	var f := [
		[Vector3(x0, y1, z0), Vector3(x1, y1, z0), Vector3(x1, y1, z1), Vector3(x0, y1, z1)],
		[Vector3(x0, y0, z1), Vector3(x1, y0, z1), Vector3(x1, y1, z1), Vector3(x0, y1, z1)],
		[Vector3(x1, y0, z0), Vector3(x0, y0, z0), Vector3(x0, y1, z0), Vector3(x1, y1, z0)],
		[Vector3(x1, y0, z1), Vector3(x1, y0, z0), Vector3(x1, y1, z0), Vector3(x1, y1, z1)],
		[Vector3(x0, y0, z0), Vector3(x0, y0, z1), Vector3(x0, y1, z1), Vector3(x0, y1, z0)],
	]
	for k in f.size():
		var ordine := [0, 1, 2, 0, 2, 3] if k == 0 else [0, 2, 1, 0, 3, 2]
		for i in ordine:
			st.add_vertex(f[k][i])

func _tetto(st: SurfaceTool, w: float, d: float, y: float, alto: float, col: Color, sporg := 0.07):
	# tetto a due falde, colmo lungo x
	var x0 := -w / 2 - sporg; var x1 := w / 2 + sporg
	var z0 := -d / 2 - sporg; var z1 := d / 2 + sporg
	var t := y + alto
	st.set_color(col)
	for v in [Vector3(x0, y, z1), Vector3(x1, t, 0), Vector3(x1, y, z1), Vector3(x0, y, z1), Vector3(x0, t, 0), Vector3(x1, t, 0)]:
		st.add_vertex(v)
	for v in [Vector3(x1, y, z0), Vector3(x0, t, 0), Vector3(x0, y, z0), Vector3(x1, y, z0), Vector3(x1, t, 0), Vector3(x0, t, 0)]:
		st.add_vertex(v)
	# spessore del bordo
	st.set_color(col.darkened(0.25))
	for v in [Vector3(x0, y - 0.035, z1), Vector3(x1, y - 0.035, z1), Vector3(x1, y, z1), Vector3(x0, y - 0.035, z1), Vector3(x1, y, z1), Vector3(x0, y, z1)]:
		st.add_vertex(v)
	for v in [Vector3(x1, y - 0.035, z0), Vector3(x0, y - 0.035, z0), Vector3(x0, y, z0), Vector3(x1, y - 0.035, z0), Vector3(x0, y, z0), Vector3(x1, y, z0)]:
		st.add_vertex(v)

func _timpani(st: SurfaceTool, w: float, d: float, y: float, alto: float, col: Color):
	st.set_color(col)
	for v in [Vector3(w / 2, y, d / 2), Vector3(w / 2, y + alto, 0), Vector3(w / 2, y, -d / 2)]:
		st.add_vertex(v)
	for v in [Vector3(-w / 2, y, -d / 2), Vector3(-w / 2, y + alto, 0), Vector3(-w / 2, y, d / 2)]:
		st.add_vertex(v)

func _piramide(st: SurfaceTool, w: float, y: float, alto: float, col: Color):
	var s := w / 2 + 0.06
	var p := [Vector3(-s, y, -s), Vector3(s, y, -s), Vector3(s, y, s), Vector3(-s, y, s)]
	var cima := Vector3(0, y + alto, 0)
	st.set_color(col)
	for i in 4:
		for v in [p[i], p[(i + 1) % 4], cima]:
			st.add_vertex(v)

func _finestre(st: SurfaceTool, w: float, d: float, y0: float, piani: int, h_piano: float, porta: bool):
	for pi in piani:
		var y := y0 + pi * h_piano + h_piano * 0.38
		var nx := maxi(1, int(w / 0.28))
		for i in nx:
			var x := -w / 2 + w * (i + 0.5) / nx
			if porta and pi == 0 and i == nx / 2:
				_box(st, Vector3(x, y0, d / 2 + 0.004), Vector3(0.12, h_piano * 0.72, 0.02), LEGNO_P)
				continue
			_box(st, Vector3(x, y - 0.01, d / 2 + 0.006), Vector3(0.15, 0.2, 0.012), Color(0.99, 0.98, 0.96))
			_box(st, Vector3(x, y, d / 2 + 0.012), Vector3(0.11, 0.16, 0.012), VETRO)
			_box(st, Vector3(x, y - 0.01, -d / 2 - 0.006), Vector3(0.15, 0.2, 0.012), Color(0.99, 0.98, 0.96))
			_box(st, Vector3(x, y, -d / 2 - 0.012), Vector3(0.11, 0.16, 0.012), VETRO)
		var nz := maxi(1, int(d / 0.32))
		for i in nz:
			var z := -d / 2 + d * (i + 0.5) / nz
			_box(st, Vector3(w / 2 + 0.006, y - 0.01, z), Vector3(0.012, 0.2, 0.15), Color(0.99, 0.98, 0.96))
			_box(st, Vector3(w / 2 + 0.012, y, z), Vector3(0.012, 0.16, 0.11), VETRO)
			_box(st, Vector3(-w / 2 - 0.006, y - 0.01, z), Vector3(0.012, 0.2, 0.15), Color(0.99, 0.98, 0.96))
			_box(st, Vector3(-w / 2 - 0.012, y, z), Vector3(0.012, 0.16, 0.11), VETRO)

func _mesh_edificio(tipo: String, var_: int) -> ArrayMesh:
	var chiave := "%s/%d" % [tipo, var_]
	if cache.has(chiave):
		return cache[chiave]
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	var muro: Color = MURI[var_ % MURI.size()]
	var tetto: Color = TETTI[(var_ / MURI.size() + var_) % TETTI.size()]
	_box(st, Vector3(0, -0.6, 0), Vector3(0.86, 0.62, 0.86), PIETRA)     # zoccolo che entra nel terreno
	var pav := Color("E8E0D2")   # pavimentazione in pietra chiara
	match tipo:
		"casa":
			_box(st, Vector3(0, 0, 0), Vector3(0.62, 0.42, 0.52), muro)
			_finestre(st, 0.62, 0.52, 0.0, 1, 0.42, true)
			_box(st, Vector3(0, 0.42, 0), Vector3(0.66, 0.03, 0.56), LEGNO_P)      # cornice in legno sotto la volta
			_box(st, Vector3(0.2, 0.42, -0.1), Vector3(0.07, 0.26, 0.07), muro.darkened(0.1))
		"palazzina":
			_box(st, Vector3(0, 0, 0), Vector3(0.76, 0.9, 0.62), muro)
			_box(st, Vector3(0, 0.0, 0), Vector3(0.79, 0.08, 0.65), PIETRA)
			_box(st, Vector3(0, 0.44, 0), Vector3(0.82, 0.03, 0.68), LEGNO_P)      # logge
			_box(st, Vector3(0, 0.90, 0), Vector3(0.80, 0.03, 0.66), LEGNO_P)
			for i in 3:
				_box(st, Vector3(-0.3 + 0.3 * i, 0.47, 0.33), Vector3(0.025, 0.4, 0.025), LEGNO_P)
			_finestre(st, 0.76, 0.62, 0.0, 2, 0.45, true)
		"torre":
			# base ad archi: il corpo slanciato e il cristallo sono parti tonde in _edificio
			_box(st, Vector3(0, 0, 0), Vector3(0.5, 0.3, 0.5), muro)
			_finestre(st, 0.5, 0.5, 0.0, 1, 0.3, true)
			_box(st, Vector3(0, 0.3, 0), Vector3(0.56, 0.04, 0.56), LEGNO_P)
		"negozio":
			_box(st, Vector3(0, 0, 0), Vector3(0.7, 0.5, 0.56), muro)
			_box(st, Vector3(0, 0.08, 0.284), Vector3(0.5, 0.24, 0.02), VETRO)
			_box(st, Vector3(0, 0.0, 0.29), Vector3(0.14, 0.32, 0.02), LEGNO_P)
			# tenda arancio su travi di legno, come nel concept
			_box(st, Vector3(0, 0.38, 0.36), Vector3(0.62, 0.025, 0.18), Color(0.93, 0.56, 0.22))
			for x in [-0.28, 0.28]:
				_box(st, Vector3(x, 0.0, 0.43), Vector3(0.025, 0.38, 0.025), LEGNO_P)
			# stendardo rosso sull'asta
			_box(st, Vector3(-0.36, 0.0, -0.2), Vector3(0.025, 0.82, 0.025), LEGNO_P)
			_box(st, Vector3(-0.36, 0.5, -0.2), Vector3(0.01, 0.28, 0.14), P_STENDARDO)
			_box(st, Vector3(0, 0.5, 0), Vector3(0.74, 0.03, 0.6), LEGNO_P)
		"fienile":
			_box(st, Vector3(0, 0, 0), Vector3(0.7, 0.48, 0.56), muro)
			_box(st, Vector3(0, 0, 0.284), Vector3(0.3, 0.38, 0.02), LEGNO_P)   # grande portale
			_box(st, Vector3(0, 0.1, 0.29), Vector3(0.26, 0.26, 0.02), tetto.lightened(0.15))
			_box(st, Vector3(0, 0.48, 0), Vector3(0.74, 0.03, 0.6), LEGNO_P)
		"piazza":
			_box(st, Vector3(0, -0.3, 0), Vector3(0.98, 0.42, 0.98), pav)
			_box(st, Vector3(0, -0.3, 0), Vector3(0.84, 0.44, 0.84), pav.darkened(0.06))   # gradino centrale
			for i in 4:
				var a := i * PI / 2 + PI / 4
				_box(st, Vector3(cos(a) * 0.6, 0.0, sin(a) * 0.6), Vector3(0.025, 0.5, 0.025), LEGNO_P)
				_box(st, Vector3(cos(a) * 0.6, 0.26, sin(a) * 0.6), Vector3(0.1, 0.22, 0.01) if i % 2 == 0 else Vector3(0.01, 0.22, 0.1), P_STENDARDO)
		"fontana":
			_box(st, Vector3(0, -0.3, 0), Vector3(0.98, 0.42, 0.98), pav)
		"parco":
			_box(st, Vector3(0, -0.3, 0), Vector3(0.98, 0.39, 0.98), P_PRATO.lerp(P_SOTTOBOSCO, 0.2))
			_box(st, Vector3(0, -0.3, 0), Vector3(0.18, 0.395, 0.98), pav)
	st.generate_normals()
	var m := st.commit()
	var mat := StandardMaterial3D.new()
	mat.vertex_color_use_as_albedo = true
	mat.roughness = 0.8
	mat.diffuse_mode = BaseMaterial3D.DIFFUSE_LAMBERT_WRAP
	m.surface_set_material(0, mat)
	cache[chiave] = m
	return m

func _volta(w: float, d: float, y: float) -> Array:
	# volta a botte in legno che poggia sui muri: cilindro coricato lungo x, un po' sporgente
	var c := cil(d / 2 * 1.06, w + 0.1, 18, 1.0)
	return [c, Transform3D(Basis(Vector3(0, 0, 1), PI / 2), Vector3(0, y, 0))]

func _anello(r: float, y: float, sp := 0.03) -> Array:
	return [cil(r, sp, 16, 1.0), T(Vector3(0, y, 0))]

func _parti_tonde(tipo: String, var_: int) -> Array:
	# parti curve di ogni modulo (volte, torre, silo, fontana, archi): liste [mesh, colore]
	var chiave := "tondo/%s/%d" % [tipo, var_]
	if cache.has(chiave):
		return cache[chiave]
	var tetto: Color = TETTI[(var_ / MURI.size() + var_) % TETTI.size()]
	var out := []
	match tipo:
		"casa":
			out.append([forma_morbida([[_volta(0.62, 0.52, 0.42)]], [tetto]), null])
		"palazzina":
			out.append([forma_morbida([[_volta(0.76, 0.62, 0.90)]], [tetto]), null])
		"negozio":
			out.append([forma_morbida([[_volta(0.70, 0.56, 0.50)]], [tetto]), null])
		"fienile":
			out.append([forma_morbida([[_volta(0.70, 0.56, 0.48)]], [tetto]), null])
			# silo cilindrico in intonaco con cupola
			out.append([forma_morbida([[[cil(0.11, 0.62, 14, 1.0), T(Vector3(0.38, 0.31, -0.2))], [palla(0.11, 14, 8), T(Vector3(0.38, 0.62, -0.2), Vector3(1, 0.7, 1))]],
				[_anello(0.12, 0.3), _anello(0.12, 0.55)]], [MURI[var_ % MURI.size()], LEGNO_P]), null])
		"torre":
			# torre civica: fusto in pietra chiara che si assottiglia, anelli d'oro, cristallo in cima
			out.append([forma_morbida([[[cil(0.19, 1.2, 14, 0.55), T(Vector3(0, 0.9, 0))]],
				[[cil(0.21, 0.035, 14, 0.95), T(Vector3(0, 0.62, 0))], [cil(0.165, 0.035, 14, 0.95), T(Vector3(0, 1.0, 0))], [cil(0.125, 0.04, 14, 0.9), T(Vector3(0, 1.5, 0))]],
				[[cil(0.03, 1.1, 6, 0.6), Transform3D(Basis(Vector3(0, 0, 1), 0.12), Vector3(0.2, 0.85, 0))], [cil(0.03, 1.1, 6, 0.6), Transform3D(Basis(Vector3(0, 0, 1), -0.12), Vector3(-0.2, 0.85, 0))]]],
				[PIETRA, P_ORO, LEGNO_P]), null])
			out.append([palla(0.085, 10, 8), ["luce", Vector3(0, 1.75, 0), Vector3(1, 2.6, 1)]])
		"fontana":
			out.append([forma_morbida([[[cil(0.38, 0.12, 20, 1.0), T(Vector3(0, 0.06, 0))], [cil(0.1, 0.2, 12, 0.8), T(Vector3(0, 0.1, 0))]],
				[[cil(0.4, 0.04, 20, 1.0), T(Vector3(0, 0.12, 0))], [cil(0.09, 0.03, 12, 1.0), T(Vector3(0, 0.2, 0))]]], [PIETRA, P_ORO]), null])
			out.append([cil(0.34, 0.03, 20, 1.0), ["luce", Vector3(0, 0.105, 0), Vector3.ONE, 1.3]])
			out.append([palla(0.07, 10, 8), ["luce", Vector3(0, 0.36, 0), Vector3(1, 2.8, 1)]])
		"parco":
			var alb := [palla(0.18), cil(0.03, 0.26, 8)]
			var parti := []
			var k := 0
			for p in [Vector3(0.28, 0, 0.26), Vector3(-0.26, 0, -0.24), Vector3(-0.28, 0, 0.3)]:
				parti.append([forma_morbida([[[alb[0], T(p + Vector3(0, 0.38, 0))]], [[alb[1], T(p + Vector3(0, 0.13, 0))]]],
					[P_VIOLA if k != 1 else P_PRATO.lerp(P_SOTTOBOSCO, 0.3), LEGNO_P]), null])
				k += 1
			# arco in legno sul vialetto
			var arco := TorusMesh.new()
			arco.inner_radius = 0.2; arco.outer_radius = 0.235; arco.rings = 20; arco.ring_segments = 8
			parti.append([forma_morbida([[[arco, Transform3D(Basis(Vector3(0, 0, 1), PI / 2), Vector3(0, 0.02, -0.1))]]], [LEGNO_P]), null])
			out = parti
	cache[chiave] = out
	return out

func _edificio(tipo: String, c: Vector2i, anteprima_ := false) -> Node3D:
	var radice := Node3D.new()
	var var_: int = 0 if anteprima_ else abs(hash(c * 7 + Vector2i(seme, 3))) % 30
	var mi := MeshInstance3D.new()
	mi.mesh = _mesh_edificio(tipo, var_)
	radice.add_child(mi)
	for p in _parti_tonde(tipo, var_):
		if p[1] == null:
			var t := MeshInstance3D.new()
			t.mesh = p[0]
			radice.add_child(t)
		else:
			var l := _luminoso(p[0], P_LUCE, p[1][3] if p[1].size() > 3 else 2.5)
			l.position = p[1][1]
			l.scale = p[1][2]
			radice.add_child(l)
	return radice

# --- vie: nastri morbidi che seguono il terreno -------------------------------------------------
func _ricostruisci_vie():
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	var dirs := [Vector2i(0, -1), Vector2i(1, 0), Vector2i(0, 1), Vector2i(-1, 0)]
	var col := Color(0.87, 0.82, 0.73)   # vie in pietra chiara
	for c in citta:
		if citta[c].t != "strada":
			continue
		var centro := Vector2(c.x, c.y)
		# disco al centro
		for i in 16:
			var a0 := i * TAU / 16
			var a1 := (i + 1) * TAU / 16
			_tri_terra(st, centro, centro + Vector2(cos(a0), sin(a0)) * 0.22, centro + Vector2(cos(a1), sin(a1)) * 0.22, col)
		for d in dirs:
			if not (citta.has(c + d) and citta[c + d].t == "strada"):
				continue
			var dv := Vector2(d.x, d.y)
			var lato := Vector2(-dv.y, dv.x) * 0.22
			for s in 3:
				var p0 := centro + dv * (0.5 * s / 3.0)
				var p1 := centro + dv * (0.5 * (s + 1) / 3.0)
				_tri_terra(st, p0 - lato, p1 - lato, p1 + lato, col)
				_tri_terra(st, p0 - lato, p1 + lato, p0 + lato, col)
	st.generate_normals()
	var m := st.commit()
	var mat := StandardMaterial3D.new()
	mat.vertex_color_use_as_albedo = true
	mat.roughness = 0.95
	strade_mi.mesh = m
	strade_mi.material_override = mat

func _tri_terra(st: SurfaceTool, a: Vector2, b: Vector2, c: Vector2, col: Color):
	for p in [a, b, c]:
		var v: Vector2 = p
		var rumore := n2.get_noise_2d(v.x * 9.0, v.y * 9.0) * 0.05
		st.set_color(col.lightened(rumore))
		st.add_vertex(Vector3(v.x, alt(v.x, v.y) + 0.025, v.y))

# --- città ---------------------------------------------------------------------------------
func _costruisci_in(c: Vector2i, id: String, r: int, salva := true):
	if id == "demolisci":
		_demolisci(c, salva)
		return
	if not costruibile(c):
		return
	_togli_nodo(c)
	citta[c] = {"t": id, "r": r}
	_veg_visibile(c, false)
	if id == "strada":
		_ricostruisci_vie()
	else:
		_disegna(c)
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
		_ricostruisci_vie()
	if salva:
		_suona("removal-a")
		_salva_citta()

func _togli_nodo(c: Vector2i):
	if nodi.has(c):
		nodi[c].queue_free()
		nodi.erase(c)

func _disegna(c: Vector2i):
	var d = citta[c]
	var g := _edificio(d.t, c)
	g.position = Vector3(c.x, alt_cella(c), c.y)
	g.rotation.y = int(d.r) * PI / 2
	mondo.add_child(g)
	nodi[c] = g

func _salva_citta():
	var out := {"seme": seme, "celle": {}}
	for c in citta:
		out.celle["%d,%d" % [c.x, c.y]] = citta[c]
	var f := FileAccess.open("user://citta2.json", FileAccess.WRITE)
	f.store_string(JSON.stringify(out))
	f.close()

func _carica_citta():
	if not FileAccess.file_exists("user://citta2.json"):
		return
	var d = JSON.parse_string(FileAccess.get_file_as_string("user://citta2.json"))
	if typeof(d) != TYPE_DICTIONARY or int(d.get("seme", -1)) != seme:
		return
	for k in d.celle:
		var p = k.split(",")
		var c := Vector2i(int(p[0]), int(p[1]))
		if costruibile(c):
			citta[c] = {"t": str(d.celle[k].t), "r": int(d.celle[k].r)}
			_veg_visibile(c, false)
	for c in citta:
		if citta[c].t != "strada":
			_disegna(c)
	_ricostruisci_vie()

# --- comandi -------------------------------------------------------------------------------
func _camera():
	perno.rotation_degrees = Vector3(pitch, yaw, 0)
	cam.position = cam.position.lerp(Vector3(0, 0, zoom), 0.25)
	var dz := cam.position.z
	attr.dof_blur_far_distance = dz * 1.15
	attr.dof_blur_far_transition = dz * 0.6
	attr.dof_blur_near_distance = dz * 0.85
	attr.dof_blur_near_transition = dz * 0.35

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
	if d.y < -0.01:
		var t: float = maxf(0.0, (7.0 - o.y) / d.y)
		var fine: float = (BASE - o.y) / d.y
		while t < fine:
			var p: Vector3 = o + d * t
			if p.y <= maxf(alt(p.x, p.z), MARE):
				var c := Vector2i(roundi(p.x), roundi(p.z))
				if celle.has(c):
					cella_mouse = c
				break
			t += 0.05
	var costruisco: bool = STRUMENTI[strumento].id != "demolisci"
	mat_terreno.set_shader_parameter("griglia", 1.0 if cella_mouse != null and foto == "" else 0.0)
	if cella_mouse == null:
		anteprima.visible = false
		return
	var c: Vector2i = cella_mouse
	mat_terreno.set_shader_parameter("cursore", Vector2(c.x, c.y))
	anteprima.visible = costruisco and costruibile(c) and STRUMENTI[strumento].id != "strada"
	anteprima.position = Vector3(c.x, alt_cella(c) + 0.03, c.y)
	anteprima.rotation.y = rot * PI / 2

func _unhandled_input(e):
	if e is InputEventMouseButton:
		if e.button_index == MOUSE_BUTTON_WHEEL_UP: zoom = maxf(6.0, zoom * 0.88)
		elif e.button_index == MOUSE_BUTTON_WHEEL_DOWN: zoom = minf(800.0, zoom * 1.12)
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
			pitch = clampf(pitch - e.relative.y * 0.2, -85.0, -12.0)
		elif Input.is_mouse_button_pressed(MOUSE_BUTTON_LEFT) and cella_mouse != null and STRUMENTI[strumento].id in ["strada", "demolisci"]:
			if not (citta.has(cella_mouse) and citta[cella_mouse].t == STRUMENTI[strumento].id):
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
	var best := Vector2i.ZERO
	var punti := -1
	for c in celle:
		if not costruibile(c) or c.x % 3 != 0 or c.y % 3 != 0:
			continue
		var s := 0
		for y in range(-6, 7):
			for x in range(-6, 7):
				var q: Vector2i = c + Vector2i(x, y)
				if costruibile(q) and absf(alt(q.x, q.y) - alt(c.x, c.y)) < 0.25:
					s += 1
		if s > punti:
			punti = s; best = c
	var tipi := ["casa", "casa", "palazzina", "casa", "negozio", "torre", "casa", "palazzina", "fienile"]
	var r := RandomNumberGenerator.new()
	r.seed = 11
	for i in range(-6, 7):
		_costruisci_in(best + Vector2i(i, 0), "strada", 0, false)
		_costruisci_in(best + Vector2i(0, i), "strada", 0, false)
	for i in range(-3, 4):
		_costruisci_in(best + Vector2i(i, 3), "strada", 0, false)
	for i in [-5, -4, -3, -2, 2, 3, 4, 5]:
		for j in [-1, 1]:
			_costruisci_in(best + Vector2i(i, j), tipi[r.randi() % tipi.size()], 2 if j == -1 else 0, false)
			_costruisci_in(best + Vector2i(j, i), tipi[r.randi() % tipi.size()], 1 if j == -1 else 3, false)
	for i in [-3, -2, 2, 3]:
		_costruisci_in(best + Vector2i(i, 4), tipi[r.randi() % tipi.size()], 0, false)
	_costruisci_in(best + Vector2i(1, 1), "fontana", 0, false)
	_costruisci_in(best + Vector2i(-1, -1), "piazza", 0, false)
	_costruisci_in(best + Vector2i(1, -1), "parco", 0, false)
	_costruisci_in(best + Vector2i(-1, 1), "piazza", 0, false)
	perno.position = Vector3(best.x, alt(best.x, best.y), best.y)
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--zoom="): zoom = float(a.substr(7))

func _scatta():
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--yaw="): yaw = float(a.substr(6))
		elif a.begins_with("--pitch="): pitch = float(a.substr(8))
		elif a.begins_with("--centro="):
			var cc = a.substr(9).split(",")
			perno.position = Vector3(float(cc[0]), 0, float(cc[1]))
	cam.position = Vector3(0, 0, zoom)
	for i in 40:
		await get_tree().process_frame
	await RenderingServer.frame_post_draw
	get_viewport().get_texture().get_image().save_png(foto)
	print("FOTO ", foto)
	get_tree().quit()
