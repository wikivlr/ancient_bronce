extends Node2D

const WORLD_PATH := "res://data/generated_world.json"

enum ViewMode {
	GLOBAL,
	LOCAL,
}

var view_mode := ViewMode.GLOBAL

var selected_cell := Vector2i(-1, -1)
var selected_local_cell := Vector2i(-1, -1)
var current_global_cell := Vector2i(-1, -1)

var world_data := {}
var world := []
var grid_width := 10
var grid_height := 10
var local_width := 10
var local_height := 10

var world_loader := WorldLoader.new()
var world_view := WorldView.new()
var group_state := GroupState.new()
var turn_system := TurnSystem.new()


func _ready() -> void:
	world_data = world_loader.load_world(WORLD_PATH)

	if world_data.is_empty():
		push_error("No se pudo cargar el mundo.")
		return

	grid_width = int(world_data.get("width", 10))
	grid_height = int(world_data.get("height", 10))
	local_width = int(world_data.get("local_width", 10))
	local_height = int(world_data.get("local_height", 10))
	world = world_data.get("global_cells", [])

	group_state.place_initial_group(world, grid_width, grid_height, local_width, local_height)

	selected_cell = group_state.global_position
	current_global_cell = group_state.global_position
	selected_local_cell = group_state.local_position

	queue_redraw()


func _draw() -> void:
	if world.is_empty():
		return

	match view_mode:
		ViewMode.GLOBAL:
			world_view.draw_global_view(
				self,
				world,
				grid_width,
				grid_height,
				selected_cell
			)
			world_view.draw_global_info_panel(
				self,
				world,
				grid_width,
				grid_height,
				selected_cell
			)

		ViewMode.LOCAL:
			world_view.draw_local_view(
				self,
				world,
				local_width,
				local_height,
				current_global_cell,
				selected_local_cell,
				group_state
			)
			world_view.draw_local_info_panel(
				self,
				world,
				current_global_cell,
				selected_local_cell,
				group_state,
				turn_system
			)


func _input(event: InputEvent) -> void:
	if event is InputEventKey and event.pressed and event.keycode == KEY_ESCAPE:
		_return_to_global_view()

	if event is InputEventKey and event.pressed and event.keycode == KEY_T:
		turn_system.advance_turn(world, group_state)
		queue_redraw()

	if event is InputEventMouseButton and event.pressed and event.button_index == MOUSE_BUTTON_LEFT:
		match view_mode:
			ViewMode.GLOBAL:
				_handle_global_click(event)
			ViewMode.LOCAL:
				_handle_local_click(event)


func _return_to_global_view() -> void:
	if view_mode != ViewMode.LOCAL:
		return

	view_mode = ViewMode.GLOBAL
	selected_local_cell = Vector2i(-1, -1)
	queue_redraw()


func _handle_global_click(event: InputEventMouseButton) -> void:
	var clicked := world_view.global_cell_from_mouse(
		event.position,
		grid_width,
		grid_height
	)

	if clicked.x < 0:
		return

	selected_cell = clicked

	if event.double_click:
		current_global_cell = clicked
		selected_local_cell = Vector2i(-1, -1)
		view_mode = ViewMode.LOCAL

	queue_redraw()


func _handle_local_click(event: InputEventMouseButton) -> void:
	var clicked := world_view.local_cell_from_mouse(
		event.position,
		local_width,
		local_height
	)

	if clicked.x < 0:
		return

	selected_local_cell = clicked
	queue_redraw()
