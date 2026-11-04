extends Node
# Emulatore del Mondo del ponte genesis-godot: dati persistenti in JSON tra un'esecuzione e l'altra.
var dati := {}
var uscita := []
func _init():
	if FileAccess.file_exists("user://dati.json"):
		dati = JSON.parse_string(FileAccess.get_file_as_string("user://dati.json"))
func racconta(t):
	uscita.append(str(t))
	print(t)
func salva():
	var f := FileAccess.open("user://dati.json", FileAccess.WRITE)
	f.store_string(JSON.stringify(dati))
