extends Node
# esegue res://passo.gd come farebbe il ponte: un nodo figlio, 300 frame, poi Mondo.dati salvato
var f := 0
func _ready():
	add_child(load("res://passo.gd").new())
func _process(_d):
	f += 1
	if f >= 300:
		Mondo.salva()
		get_tree().quit()
