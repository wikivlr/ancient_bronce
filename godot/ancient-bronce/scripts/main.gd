extends Node2D

const CELL_SIZE := 56
const CELL_GAP := 4
const LOCAL_CELL_SIZE := 46
const LOCAL_CELL_GAP := 3
const WORLD_PATH := "res://data/generated_world.json"

enum ViewMode {
	GLOBAL,
	LOCAL,
}

var view_mode := ViewMode.GLOBAL

var selected_cell := Vector2i(-1, -1)
var selected_local_cell := Vector2i(-1, -1)
var current_global_cell := Vector2i(-1, -1)

var world := []
var grid_width := 10
var grid_height := 10
var local_width := 10
var local_height := 10


func _ready() -> void:
	_load_world()
	queue_redraw()


func _load_world() -> void:
	var file := FileAccess.open(WORLD_PATH, FileAccess.READ)

	if file == null:
		push_error("No se pudo abrir: " + WORLD_PATH)
		return

	var text := file.get_as_text()
	var parsed = JSON.parse_string(text)

	if parsed == null:
		push_error("No se pudo parsear el JSON del mundo.")
		return

	grid_width = int(parsed.get("width", 10))
	grid_height = int(parsed.get("height", 10))
	local_width = int(parsed.get("local_width", 10))
	local_height = int(parsed.get("local_height", 10))
	world = parsed.get("global_cells", [])


func _draw() -> void:
	if world.is_empty():
		return

	match view_mode:
		ViewMode.GLOBAL:
			_draw_global_view()
		ViewMode.LOCAL:
			_draw_local_view()


func _draw_global_view() -> void:
	var origin := Vector2(40, 40)

	for y in range(grid_height):
		for x in range(grid_width):
			var cell = world[y][x]
			var rect := Rect2(
				origin.x + x * (CELL_SIZE + CELL_GAP),
				origin.y + y * (CELL_SIZE + CELL_GAP),
				CELL_SIZE,
				CELL_SIZE
			)

			draw_rect(rect, _color_for_global_cell(cell), true)
			draw_rect(rect, Color.BLACK, false, 2.0)

			if selected_cell == Vector2i(x, y):
				draw_rect(rect.grow(3), Color.WHITE, false, 3.0)

	_draw_global_info_panel()


func _draw_local_view() -> void:
	var origin := Vector2(40, 40)
	var global_cell = world[current_global_cell.y][current_global_cell.x]
	var local_cells = global_cell.get("local_cells", [])

	for y in range(local_height):
		for x in range(local_width):
			var local_cell = local_cells[y][x]
			var rect := Rect2(
				origin.x + x * (LOCAL_CELL_SIZE + LOCAL_CELL_GAP),
				origin.y + y * (LOCAL_CELL_SIZE + LOCAL_CELL_GAP),
				LOCAL_CELL_SIZE,
				LOCAL_CELL_SIZE
			)

			draw_rect(rect, _color_for_local_cell(local_cell), true)
			draw_rect(rect, Color.BLACK, false, 2.0)

			if _local_cell_has_river(local_cell):
				var river_rect := rect.grow(-LOCAL_CELL_SIZE * 0.35)
				draw_rect(river_rect, Color(0.20, 0.65, 1.0), true)

			if selected_local_cell == Vector2i(x, y):
				draw_rect(rect.grow(3), Color.WHITE, false, 3.0)

	_draw_local_info_panel()


func _draw_global_info_panel() -> void:
	var panel_x := 680.0
	var panel_y := 40.0

	draw_string(ThemeDB.fallback_font, Vector2(panel_x, panel_y), "Ancient Bronce", HORIZONTAL_ALIGNMENT_LEFT, -1, 24, Color.WHITE)
	draw_string(ThemeDB.fallback_font, Vector2(panel_x, panel_y + 36), "Mapa global %sx%s" % [grid_width, grid_height], HORIZONTAL_ALIGNMENT_LEFT, -1, 18, Color.LIGHT_GRAY)
	draw_string(ThemeDB.fallback_font, Vector2(panel_x, panel_y + 64), "Doble click para entrar", HORIZONTAL_ALIGNMENT_LEFT, -1, 16, Color.LIGHT_GRAY)

	if selected_cell.x == -1:
		draw_string(ThemeDB.fallback_font, Vector2(panel_x, panel_y + 110), "Selecciona una celda", HORIZONTAL_ALIGNMENT_LEFT, -1, 18, Color.WHITE)
		return

	var cell = world[selected_cell.y][selected_cell.x]
	var layers = cell.get("layers", {})
	var summary := _local_summary(cell)

	var lines := [
		"Celda: %s, %s" % [int(cell.get("x", selected_cell.x)), int(cell.get("y", selected_cell.y))],
		"Altitud global: %s" % int(layers.get("altitude", 0)),
		"Humedad global: %s" % int(layers.get("humidity", 0)),
		"Temperatura global: %s" % int(layers.get("temperature", 0)),
		"Rios locales: %s" % summary.rivers,
		"Recursos:",
	]

	lines.append_array(_wrap_text(summary.resources, 42))
	_draw_lines(lines, Vector2(panel_x, panel_y + 110), 18, 28)


func _draw_local_info_panel() -> void:
	var panel_x := 580.0
	var panel_y := 40.0
	var global_cell = world[current_global_cell.y][current_global_cell.x]

	draw_string(ThemeDB.fallback_font, Vector2(panel_x, panel_y), "Ancient Bronce", HORIZONTAL_ALIGNMENT_LEFT, -1, 24, Color.WHITE)
	draw_string(ThemeDB.fallback_font, Vector2(panel_x, panel_y + 36), "Mapa local de %s, %s" % [current_global_cell.x, current_global_cell.y], HORIZONTAL_ALIGNMENT_LEFT, -1, 18, Color.LIGHT_GRAY)
	draw_string(ThemeDB.fallback_font, Vector2(panel_x, panel_y + 64), "Esc para volver", HORIZONTAL_ALIGNMENT_LEFT, -1, 16, Color.LIGHT_GRAY)

	if selected_local_cell.x == -1:
		draw_string(ThemeDB.fallback_font, Vector2(panel_x, panel_y + 110), "Selecciona una celda local", HORIZONTAL_ALIGNMENT_LEFT, -1, 18, Color.WHITE)
		return

	var local_cell = global_cell["local_cells"][selected_local_cell.y][selected_local_cell.x]
	var layers = local_cell.get("layers", {})
	var hydrology = local_cell.get("hydrology", {})
	var resources := _resources_for_local_cell(local_cell)

	var lines := [
		"Celda local: %s, %s" % [selected_local_cell.x, selected_local_cell.y],
		"Terreno: %s" % local_cell.get("terrain_type", "?"),
		"Bioma: %s" % local_cell.get("biome", "?"),
		"Altitud: %s (%s)" % [int(layers.altitude.get("effective", 0)), layers.altitude.get("category", "?")],
		"Humedad: %s (%s)" % [int(layers.humidity.get("effective", 0)), layers.humidity.get("category", "?")],
		"Temperatura: %s (%s)" % [int(layers.temperature.get("effective", 0)), layers.temperature.get("category", "?")],
		"Rio: %s" % ("si" if hydrology.get("has_river", false) else "no"),
		"Lluvia acumulada: %s" % int(hydrology.get("rain_units", 0)),
		"Recursos:",
	]

	lines.append_array(_wrap_text(resources, 42))
	_draw_lines(lines, Vector2(panel_x, panel_y + 110), 18, 28)


func _draw_lines(lines: Array, start: Vector2, font_size: int, line_height: int) -> void:
	for i in range(lines.size()):
		draw_string(
			ThemeDB.fallback_font,
			Vector2(start.x, start.y + i * line_height),
			str(lines[i]),
			HORIZONTAL_ALIGNMENT_LEFT,
			-1,
			font_size,
			Color.WHITE
		)


func _input(event: InputEvent) -> void:
	if event is InputEventKey and event.pressed and event.keycode == KEY_ESCAPE:
		if view_mode == ViewMode.LOCAL:
			view_mode = ViewMode.GLOBAL
			selected_local_cell = Vector2i(-1, -1)
			queue_redraw()

	if event is InputEventMouseButton and event.pressed and event.button_index == MOUSE_BUTTON_LEFT:
		match view_mode:
			ViewMode.GLOBAL:
				_handle_global_click(event)
			ViewMode.LOCAL:
				_handle_local_click(event)


func _handle_global_click(event: InputEventMouseButton) -> void:
	var clicked := _global_cell_from_mouse(event.position)

	if clicked.x < 0:
		return

	selected_cell = clicked

	if event.double_click:
		current_global_cell = clicked
		selected_local_cell = Vector2i(-1, -1)
		view_mode = ViewMode.LOCAL

	queue_redraw()


func _handle_local_click(event: InputEventMouseButton) -> void:
	var clicked := _local_cell_from_mouse(event.position)

	if clicked.x >= 0:
		selected_local_cell = clicked
		queue_redraw()


func _global_cell_from_mouse(mouse_position: Vector2) -> Vector2i:
	var origin := Vector2(40, 40)

	for y in range(grid_height):
		for x in range(grid_width):
			var rect := Rect2(
				origin.x + x * (CELL_SIZE + CELL_GAP),
				origin.y + y * (CELL_SIZE + CELL_GAP),
				CELL_SIZE,
				CELL_SIZE
			)

			if rect.has_point(mouse_position):
				return Vector2i(x, y)

	return Vector2i(-1, -1)


func _local_cell_from_mouse(mouse_position: Vector2) -> Vector2i:
	var origin := Vector2(40, 40)

	for y in range(local_height):
		for x in range(local_width):
			var rect := Rect2(
				origin.x + x * (LOCAL_CELL_SIZE + LOCAL_CELL_GAP),
				origin.y + y * (LOCAL_CELL_SIZE + LOCAL_CELL_GAP),
				LOCAL_CELL_SIZE,
				LOCAL_CELL_SIZE
			)

			if rect.has_point(mouse_position):
				return Vector2i(x, y)

	return Vector2i(-1, -1)


func _color_for_global_cell(cell: Dictionary) -> Color:
	var layers = cell.get("layers", {})
	var altitude := int(layers.get("altitude", 2))
	var humidity := int(layers.get("humidity", 2))

	if altitude == 3:
		return Color(0.08, 0.30, 0.70)

	if altitude == 1 and humidity == 1:
		return Color(0.62, 0.55, 0.38)

	if altitude == 1:
		return Color(0.50, 0.50, 0.45)

	if humidity == 1:
		return Color(0.20, 0.55, 0.25)

	if humidity == 2:
		return Color(0.38, 0.62, 0.28)

	return Color(0.65, 0.55, 0.34)


func _color_for_local_cell(local_cell: Dictionary) -> Color:
	var color_text := str(local_cell.get("color", ""))

	if color_text.begins_with("#") and color_text.length() == 7:
		return Color.html(color_text)

	return Color(0.45, 0.45, 0.45)


func _local_summary(cell: Dictionary) -> Dictionary:
	var rivers := 0
	var resources := {}

	for row in cell.get("local_cells", []):
		for local_cell in row:
			if _local_cell_has_river(local_cell):
				rivers += 1

			for resource_name in local_cell.get("resources", {}).keys():
				if local_cell["resources"][resource_name]:
					resources[resource_name] = true

	var resource_names := resources.keys()
	resource_names.sort()

	return {
		"rivers": rivers,
		"resources": ", ".join(resource_names) if resource_names.size() > 0 else "ninguno"
	}


func _local_cell_has_river(local_cell: Dictionary) -> bool:
	return local_cell.get("hydrology", {}).get("has_river", false)


func _resources_for_local_cell(local_cell: Dictionary) -> String:
	var resources := []

	for resource_name in local_cell.get("resources", {}).keys():
		if local_cell["resources"][resource_name]:
			resources.append(resource_name)

	resources.sort()

	return ", ".join(resources) if resources.size() > 0 else "ninguno"


func _wrap_text(text: String, max_chars: int) -> Array[String]:
	var words := text.split(", ")
	var lines: Array[String] = []
	var current := ""

	for word in words:
		if current.is_empty():
			current = word
		elif current.length() + word.length() + 2 <= max_chars:
			current += ", " + word
		else:
			lines.append(current)
			current = word

	if not current.is_empty():
		lines.append(current)

	return lines
