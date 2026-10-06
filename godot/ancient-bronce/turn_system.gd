class_name TurnSystem
extends RefCounted

var turn := 1


func advance_turn(world: Array, group: GroupState) -> void:
	turn += 1

	var local_cell := group.get_local_cell(world)
	_collect_resources(local_cell, group)
	_update_population_needs(local_cell, group)


func _collect_resources(local_cell: Dictionary, group: GroupState) -> void:
	for resource_name in local_cell.get("resources", {}).keys():
		if local_cell["resources"][resource_name]:
			group.add_inventory(resource_name, 1)


func _update_population_needs(local_cell: Dictionary, group: GroupState) -> void:
	var layers = local_cell.get("layers", {})
	var temperature = layers.get("temperature", {})
	var effective_temperature := int(temperature.get("effective", 5))

	for person in group.population:
		person.hunger = max(0, int(person.hunger) - 1)

		if effective_temperature <= 3:
			person.cold = max(0, int(person.cold) - 1)
		elif effective_temperature >= 7:
			person.cold = min(5, int(person.cold) + 1)
