## Generatore procedurale deterministico a chunk per un mondo 2D molto esteso.
## Nativo Godot: FastNoiseLite, Vector2i, PackedByteArray. Da sviluppare: regole dei biomi, chunking.
## Stessa seed + stesse coordinate => stesso chunk: nessun salvataggio necessario per il terreno intatto.
class_name WorldGenerator
extends RefCounted

const CHUNK_SIZE := 32

enum Biome { OCEANO, SPIAGGIA, PRATERIA, FORESTA, DESERTO, MONTAGNA }

var _height := FastNoiseLite.new()
var _moisture := FastNoiseLite.new()


func _init(world_seed: int) -> void:
	_height.seed = world_seed
	_height.noise_type = FastNoiseLite.TYPE_SIMPLEX_SMOOTH
	_height.frequency = 0.01
	_height.fractal_type = FastNoiseLite.FRACTAL_FBM
	_height.fractal_octaves = 4
	_moisture.seed = world_seed + 1013
	_moisture.frequency = 0.004


## Coordinate del chunk che contiene una cella (corrette anche per valori negativi).
static func cell_to_chunk(cell: Vector2i) -> Vector2i:
	return Vector2i(floori(cell.x / float(CHUNK_SIZE)), floori(cell.y / float(CHUNK_SIZE)))


func biome_at(cell: Vector2i) -> Biome:
	var h := _height.get_noise_2d(cell.x, cell.y)      # circa [-1, 1]
	var m := _moisture.get_noise_2d(cell.x, cell.y)
	if h < -0.2:
		return Biome.OCEANO
	if h < -0.12:
		return Biome.SPIAGGIA
	if h > 0.45:
		return Biome.MONTAGNA
	if m > 0.15:
		return Biome.FORESTA
	if m < -0.25:
		return Biome.DESERTO
	return Biome.PRATERIA


## Un chunk come PackedByteArray compatto (CHUNK_SIZE * CHUNK_SIZE byte, un bioma per cella).
func generate_chunk(chunk: Vector2i) -> PackedByteArray:
	var data := PackedByteArray()
	data.resize(CHUNK_SIZE * CHUNK_SIZE)
	var origin := chunk * CHUNK_SIZE
	for y in CHUNK_SIZE:
		for x in CHUNK_SIZE:
			data[y * CHUNK_SIZE + x] = biome_at(origin + Vector2i(x, y))
	return data
