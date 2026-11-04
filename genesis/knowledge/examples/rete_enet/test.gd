extends SceneTree
## Architettura server-authoritative: server ENet e client nello stesso processo, su localhost.
## Nativo: ENetMultiplayerPeer, SceneMultiplayer, MultiplayerAPI.poll, segnali peer_connected.
## Cosa verifica: il client si connette e il server riceve l'evento. NON verifica RPC né sincronizzazione
## di scene (MultiplayerSynchronizer/Spawner): da sperimentare in un progetto con scene.

const PORT := 47231

var server_api := SceneMultiplayer.new()
var client_api := SceneMultiplayer.new()
var connected_ids: Array[int] = []
var frames := 0


func _init() -> void:
	var server := ENetMultiplayerPeer.new()
	if server.create_server(PORT, 4, 0, 0, 0) != OK:
		print("EXAMPLE_FAIL create_server")
		quit(1)
		return
	server_api.multiplayer_peer = server
	server_api.peer_connected.connect(func(id: int) -> void: connected_ids.append(id))
	var client := ENetMultiplayerPeer.new()
	client.create_client("127.0.0.1", PORT)
	client_api.multiplayer_peer = client


func _process(_delta: float) -> bool:
	server_api.poll()
	client_api.poll()
	frames += 1
	if not connected_ids.is_empty() and client_api.get_unique_id() > 1:
		var ok := server_api.is_server() and connected_ids[0] == client_api.get_unique_id()
		print("client id: ", client_api.get_unique_id(), " frame: ", frames)
		print("EXAMPLE_OK" if ok else "EXAMPLE_FAIL")
		_close()
		quit(0 if ok else 1)
	elif frames > 600:
		print("EXAMPLE_FAIL timeout connessione")
		_close()
		quit(1)
	return false


func _close() -> void:
	client_api.multiplayer_peer.close()
	server_api.multiplayer_peer.close()
