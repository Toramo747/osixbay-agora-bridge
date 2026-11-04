extends SceneTree
## Simulazione di molte entità con dati in array compatti (PackedVector2Array/PackedFloat32Array)
## invece di un Node per entità: un tick aggiorna tutte le entità in un ciclo.
## Nativo: Packed*Array, RandomNumberGenerator, Time. Da sviluppare: regole di comportamento.
## Il test misura i tick al secondo sull'hardware dove gira: il valore stampato è una misura, non una garanzia.

const N := 10000
const TICKS := 20

var pos := PackedVector2Array()
var vel := PackedVector2Array()
var energy := PackedFloat32Array()


func setup(world_seed: int) -> void:
	var rng := RandomNumberGenerator.new()
	rng.seed = world_seed
	pos.resize(N)
	vel.resize(N)
	energy.resize(N)
	for i in N:
		pos[i] = Vector2(rng.randf_range(-1000, 1000), rng.randf_range(-1000, 1000))
		vel[i] = Vector2.from_angle(rng.randf() * TAU) * 2.0
		energy[i] = 100.0


func tick() -> void:
	for i in N:
		if energy[i] <= 0.0:
			continue
		pos[i] += vel[i]
		energy[i] -= 0.5


func _init() -> void:
	setup(42)
	var t0 := Time.get_ticks_usec()
	for t in TICKS:
		tick()
	var secs := (Time.get_ticks_usec() - t0) / 1e6
	var ok := is_equal_approx(energy[0], 100.0 - 0.5 * TICKS)
	var p0 := pos[0]
	setup(42)
	for t in TICKS:
		tick()
	ok = ok and pos[0] == p0          # deterministico a parità di seed
	print("entita: %d tick: %d secondi: %.3f tick/s: %.1f" % [N, TICKS, secs, TICKS / max(secs, 0.000001)])
	print("EXAMPLE_OK" if ok else "EXAMPLE_FAIL")
	quit(0 if ok else 1)
