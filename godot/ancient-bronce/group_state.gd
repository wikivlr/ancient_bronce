class_name GroupState
extends RefCounted

var global_position := Vector2i(-1, -1)
var local_position := Vector2i(-1, -1)

var population := [
	{"name": "Humano 1", "hunger": 5, "cold": 5},
	{"name": "Humano 2", "hunger": 5, "cold": 5},
	{"name": "Humano 3", "hunger": 5, "cold": 5},
	{"name": "Humano 4", "hunger": 5, "cold": 5},
	{"name": "Humano 5", "hunger": 5, "cold": 5},
]

var inventory := {}


func place_initial_group(world: Array, grid_width: int, grid_height: int, local_width: int, local_height: int) -> void:
	for global_y in range(grid_height):
		for global_x in range(grid_width):
			var global_cell = world[global_y][global_x]
			var local_cells = global_cell.get("local_cells", [])

			for local_y in range(local_height):
				for local_x in range(local_width):
					var local_cell = local_cells[local_y][local_x]
					var terrain := str(local_cell.get("terrain_type", ""))

					if terrain != "Mar" and terrain != "Oceano" and terrain != "Aguas poco profundas":
						global_position = Vector2i(global_x, global_y)
						local_position = Vector2i(local_x, local_y)
						return


func get_local_cell(world: Array) -> Dictionary:
	return world[global_position.y][global_position.x]["local_cells"][local_position.y][local_position.x]


func add_inventory(resource_name: String, amount: int) -> void:
	if not inventory.has(resource_name):
		inventory[resource_name] = 0

	inventory[resource_name] += amount


func inventory_text() -> String:
	var keys := inventory.keys()
	keys.sort()

	if keys.is_empty():
		return "vacio"

	var parts := []

	for key in keys:
		parts.append("%s:%s" % [key, inventory[key]])

	return ", ".join(parts)


func average_hunger() -> float:
	var total := 0.0

	for person in population:
		total += int(person.hunger)

	return total / population.size()


func average_cold() -> float:
	var total := 0.0

	for person in population:
		total += int(person.cold)

	return total / population.size()
