extends SceneTree
## TileMapLayer (Godot 4.3+, sostituisce TileMap deprecato) riempito da codice con un TileSet creato a runtime.
## Nativo: TileSet, TileSetAtlasSource, TileMapLayer.set_cell/get_cell_source_id/erase_cell.
## Nota dal riferimento: le coordinate serializzate da TileMapLayer sono limitate a interi 16 bit con segno
## (-32768..32767): per mondi più grandi servono più layer/chunk con origine propria (codice aggiuntivo).

const CHUNK := 16


func make_tileset() -> TileSet:
	var img := Image.create(64, 16, false, Image.FORMAT_RGBA8)
	for i in 4:
		img.fill_rect(Rect2i(i * 16, 0, 16, 16), Color.from_hsv(i / 4.0, 0.6, 0.9))
	var src := TileSetAtlasSource.new()
	src.texture = ImageTexture.create_from_image(img)
	src.texture_region_size = Vector2i(16, 16)
	for i in 4:
		src.create_tile(Vector2i(i, 0))
	var ts := TileSet.new()
	ts.tile_size = Vector2i(16, 16)
	ts.add_source(src, 0)
	return ts


func fill_chunk(layer: TileMapLayer, chunk: Vector2i) -> void:
	var origin := chunk * CHUNK
	for y in CHUNK:
		for x in CHUNK:
			layer.set_cell(origin + Vector2i(x, y), 0, Vector2i((x + y) % 4, 0))


func _init() -> void:
	var layer := TileMapLayer.new()
	layer.tile_set = make_tileset()
	root.add_child(layer)
	fill_chunk(layer, Vector2i(-1, 2))
	var ok := layer.get_used_cells().size() == CHUNK * CHUNK
	ok = ok and layer.get_cell_source_id(Vector2i(-16, 32)) == 0
	ok = ok and layer.get_cell_atlas_coords(Vector2i(-15, 32)) == Vector2i(1, 0)
	ok = ok and layer.get_cell_source_id(Vector2i(0, 0)) == -1
	# scaricare un chunk = cancellarne le celle
	for c in layer.get_used_cells():
		layer.erase_cell(c)
	ok = ok and layer.get_used_cells().is_empty()
	ok = ok and layer.local_to_map(Vector2(-8, 520)) == Vector2i(-1, 32)
	print("EXAMPLE_OK" if ok else "EXAMPLE_FAIL")
	quit(0 if ok else 1)
