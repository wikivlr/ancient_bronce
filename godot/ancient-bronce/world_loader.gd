class_name WorldLoader
extends RefCounted

func load_world(path: String) -> Dictionary:
	var file := FileAccess.open(path, FileAccess.READ)

	if file == null:
		push_error("No se pudo abrir: " + path)
		return {}

	var text := file.get_as_text()
	var parsed = JSON.parse_string(text)

	if parsed == null:
		push_error("No se pudo parsear el JSON del mundo.")
		return {}

	return parsed
