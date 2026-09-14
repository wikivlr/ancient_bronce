from __future__ import annotations

import json
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any


LayerName = str


@dataclass(frozen=True)
class LayerValues:
    global_value: int
    local_value: int
    effective_value: int
    category: str


@dataclass
class LocalCell:
    global_x: int
    global_y: int
    local_x: int
    local_y: int
    layers: dict[LayerName, LayerValues]
    terrain_type: str
    biome: str
    symbol: str
    color: str
    rain_units: float
    has_river: bool
    erosion_count: int
    oceanic: bool
    resources: dict[str, bool]


@dataclass(frozen=True)
class GlobalCell:
    x: int
    y: int
    layers: dict[LayerName, int]
    local_cells: list[list[LocalCell]]


@dataclass(frozen=True)
class WorldMap:
    width: int
    height: int
    local_width: int
    local_height: int
    global_cells: list[list[GlobalCell]]


def load_rules(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as file:
        return json.load(file)


def effective_value(global_value: int, local_value: int) -> int:
    return (global_value - 1) * 3 + local_value


def generate_world(rules: dict[str, Any], seed: int | None = None) -> WorldMap:
    rng = random.Random(seed)
    size_rules = rules["map"]
    layer_names = list(rules["layers"])
    global_layer_grids = {
        layer: _generate_value_grid(
            rng=rng,
            width=size_rules["global_width"],
            height=size_rules["global_height"],
            weights=rules["layers"][layer]["global_weights"],
            generation_rules=rules["layers"][layer].get("global_generation", {"mode": "continuous", "max_neighbor_delta": 1}),
        )
        for layer in layer_names
    }

    global_cells: list[list[GlobalCell]] = []
    for global_y in range(size_rules["global_height"]):
        row: list[GlobalCell] = []
        for global_x in range(size_rules["global_width"]):
            global_layers = {
                layer: global_layer_grids[layer][global_y][global_x]
                for layer in layer_names
            }
            local_cells = _generate_local_cells(
                rng=rng,
                rules=rules,
                global_x=global_x,
                global_y=global_y,
                global_layers=global_layers,
            )
            row.append(
                GlobalCell(
                    x=global_x,
                    y=global_y,
                    layers=global_layers,
                    local_cells=local_cells,
                )
            )
        global_cells.append(row)

    world = WorldMap(
        width=size_rules["global_width"],
        height=size_rules["global_height"],
        local_width=size_rules["local_width"],
        local_height=size_rules["local_height"],
        global_cells=global_cells,
    )
    if rules.get("hydrology", {}).get("enabled", False):
        _apply_hydrology(world, rules, rng)
    if rules.get("resources", {}).get("enabled", False):
        _apply_resources(world, rules, rng)
    return world


def flatten_local_cells(world: WorldMap) -> list[list[LocalCell]]:
    rows: list[list[LocalCell]] = []
    for global_row in world.global_cells:
        for local_y in range(world.local_height):
            row: list[LocalCell] = []
            for global_cell in global_row:
                row.extend(global_cell.local_cells[local_y])
            rows.append(row)
    return rows


def world_to_dict(world: WorldMap) -> dict[str, Any]:
    return {
        "width": world.width,
        "height": world.height,
        "local_width": world.local_width,
        "local_height": world.local_height,
        "global_cells": [
            [
                {
                    "x": global_cell.x,
                    "y": global_cell.y,
                    "layers": global_cell.layers,
                    "local_cells": [
                        [
                            {
                                "global_x": local_cell.global_x,
                                "global_y": local_cell.global_y,
                                "local_x": local_cell.local_x,
                                "local_y": local_cell.local_y,
                                "layers": {
                                    layer: {
                                        "global": values.global_value,
                                        "local": values.local_value,
                                        "effective": values.effective_value,
                                        "category": values.category,
                                    }
                                    for layer, values in local_cell.layers.items()
                                },
                                "terrain_type": local_cell.terrain_type,
                                "biome": local_cell.biome,
                                "symbol": local_cell.symbol,
                                "color": local_cell.color,
                                "hydrology": {
                                    "rain_units": local_cell.rain_units,
                                    "has_river": local_cell.has_river,
                                    "erosion_count": local_cell.erosion_count,
                                    "oceanic": local_cell.oceanic,
                                },
                                "resources": local_cell.resources,
                            }
                            for local_cell in local_row
                        ]
                        for local_row in global_cell.local_cells
                    ],
                }
                for global_cell in global_row
            ]
            for global_row in world.global_cells
        ],
    }


def save_world(path: str | Path, world: WorldMap) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as file:
        json.dump(world_to_dict(world), file, indent=2)


def _generate_local_cells(
    rng: random.Random,
    rules: dict[str, Any],
    global_x: int,
    global_y: int,
    global_layers: dict[LayerName, int],
) -> list[list[LocalCell]]:
    local_layer_grids = {
        layer: _generate_local_layer_grid(
            rng=rng,
            rules=rules,
            layer=layer,
            width=rules["map"]["local_width"],
            height=rules["map"]["local_height"],
        )
        for layer in global_layers
    }
    local_cells: list[list[LocalCell]] = []
    for local_y in range(rules["map"]["local_height"]):
        row: list[LocalCell] = []
        for local_x in range(rules["map"]["local_width"]):
            layers = _generate_effective_layers(rules, global_layers, local_layer_grids, local_x, local_y)
            terrain_type = layers["altitude"].category
            biome_rule = _classify_biome(rules, layers)
            row.append(
                LocalCell(
                    global_x=global_x,
                    global_y=global_y,
                    local_x=local_x,
                    local_y=local_y,
                    layers=layers,
                    terrain_type=terrain_type,
                    biome=biome_rule["name"],
                    symbol=biome_rule["symbol"],
                    color=biome_rule["color"],
                    rain_units=0,
                    has_river=False,
                    erosion_count=0,
                    oceanic=global_layers["altitude"] == 3,
                    resources={},
                )
            )
        local_cells.append(row)
    return local_cells


def _apply_resources(world: WorldMap, rules: dict[str, Any], rng: random.Random) -> None:
    """Generate one boolean local layer per configured resource.

    Resources are generated after hydrology so habitats can depend on rivers.
    Initial occurrences are expanded in simultaneous passes, producing coherent
    deposits and populations without making resource layers affect one another.
    """
    rows = flatten_local_cells(world)
    height = len(rows)
    width = len(rows[0])
    resource_rules = rules["resources"]

    for row in rows:
        for cell in row:
            cell.resources = {
                resource_id: False
                for resource_id in resource_rules.get("types", {})
            }

    for resource_id, resource_rule in resource_rules.get("types", {}).items():
        suitable = [
            [_resource_is_suitable(cell, resource_rule) for cell in row]
            for row in rows
        ]
        present = [
            [
                suitable[y][x] and rng.random() < resource_rule["base_chance"]
                for x in range(width)
            ]
            for y in range(height)
        ]

        for _pass in range(resource_rule.get("spread_passes", 0)):
            next_present = [row[:] for row in present]
            for y in range(height):
                for x in range(width):
                    if present[y][x] or not suitable[y][x]:
                        continue
                    occupied_neighbors = sum(
                        present[neighbor_y][neighbor_x]
                        for neighbor_x, neighbor_y in _neighbor_positions(rows, x, y)
                    )
                    if occupied_neighbors == 0:
                        continue
                    spread_chance = 1 - (1 - resource_rule["spread_chance"]) ** occupied_neighbors
                    if rng.random() < spread_chance:
                        next_present[y][x] = True
            present = next_present

        for y, row in enumerate(rows):
            for x, cell in enumerate(row):
                cell.resources[resource_id] = present[y][x]


def _resource_is_suitable(cell: LocalCell, resource_rule: dict[str, Any]) -> bool:
    """A resource may use several alternative habitats; each habitat is ANDed."""
    return any(
        _cell_matches_habitat(cell, habitat)
        for habitat in resource_rule.get("habitats", [])
    )


def _cell_matches_habitat(cell: LocalCell, habitat: dict[str, Any]) -> bool:
    layer_conditions = habitat.get("layers", {})
    if any(
        not _in_range(cell.layers[layer].effective_value, value_range)
        for layer, value_range in layer_conditions.items()
    ):
        return False
    if "biomes" in habitat and cell.biome not in habitat["biomes"]:
        return False
    if "has_river" in habitat and cell.has_river != habitat["has_river"]:
        return False
    if "oceanic" in habitat and cell.oceanic != habitat["oceanic"]:
        return False
    return True


def _generate_local_layer_grid(
    rng: random.Random,
    rules: dict[str, Any],
    layer: LayerName,
    width: int,
    height: int,
) -> list[list[int]]:
    layer_rules = rules["layers"][layer]
    return _generate_value_grid(
        rng=rng,
        width=width,
        height=height,
        weights=layer_rules["local_weights"],
        generation_rules=layer_rules.get("local_generation", {"mode": "continuous", "max_neighbor_delta": 1}),
    )


def _generate_effective_layers(
    rules: dict[str, Any],
    global_layers: dict[LayerName, int],
    local_layer_grids: dict[LayerName, list[list[int]]],
    local_x: int,
    local_y: int,
) -> dict[LayerName, LayerValues]:
    result: dict[LayerName, LayerValues] = {}
    for layer, global_value in global_layers.items():
        local_value = local_layer_grids[layer][local_y][local_x]
        layer_effective_value = effective_value(global_value, local_value)
        result[layer] = LayerValues(
            global_value=global_value,
            local_value=local_value,
            effective_value=layer_effective_value,
            category=rules["layers"][layer]["effective_scale"][str(layer_effective_value)],
        )
    return result


def _apply_hydrology(world: WorldMap, rules: dict[str, Any], rng: random.Random) -> None:
    hydrology_rules = rules["hydrology"]
    rows = flatten_local_cells(world)
    rain_sources = _select_rain_sources(rows, hydrology_rules, rng)
    for _turn in range(hydrology_rules["turns"]):
        _add_rainfall(rows, hydrology_rules, rain_sources)
        transported_to = _move_rainfall_downhill(rows, hydrology_rules, rng)
        _apply_rain_erosion(rows, rules, transported_to)
        _mark_rivers(
            rows,
            hydrology_rules["river_threshold"],
        )
    _connect_short_water_gaps(rows, hydrology_rules)
    _connect_rivers(rows, hydrology_rules)


def _add_rainfall(
    rows: list[list[LocalCell]],
    hydrology_rules: dict[str, Any],
    rain_sources: set[tuple[int, int, int, int]],
) -> None:
    rain_units = hydrology_rules["rain_units_by_effective_humidity"]
    for row in rows:
        for cell in row:
            if cell.has_river:
                continue
            source_key = (cell.global_x, cell.global_y, cell.local_x, cell.local_y)
            if source_key not in rain_sources:
                continue
            effective_humidity = cell.layers["humidity"].effective_value
            cell.rain_units += rain_units[str(effective_humidity)]


def _select_rain_sources(
    rows: list[list[LocalCell]],
    hydrology_rules: dict[str, Any],
    rng: random.Random,
) -> set[tuple[int, int, int, int]]:
    max_sources = hydrology_rules.get("max_rain_sources_per_global_cell")
    rain_units = hydrology_rules["rain_units_by_effective_humidity"]
    candidates_by_global_cell: dict[tuple[int, int], list[LocalCell]] = {}
    for row in rows:
        for cell in row:
            effective_humidity = cell.layers["humidity"].effective_value
            if rain_units[str(effective_humidity)] <= 0:
                continue
            global_key = (cell.global_x, cell.global_y)
            candidates_by_global_cell.setdefault(global_key, []).append(cell)

    sources: set[tuple[int, int, int, int]] = set()
    for candidates in candidates_by_global_cell.values():
        rng.shuffle(candidates)
        candidates.sort(
            key=lambda cell: (
                cell.layers["altitude"].effective_value,
                cell.layers["humidity"].effective_value,
            )
        )
        selected = candidates if max_sources is None else candidates[:max_sources]
        for cell in selected:
            sources.add((cell.global_x, cell.global_y, cell.local_x, cell.local_y))
    return sources


def _move_rainfall_downhill(
    rows: list[list[LocalCell]],
    hydrology_rules: dict[str, Any],
    rng: random.Random,
) -> list[list[bool]]:
    height = len(rows)
    width = len(rows[0])
    next_units = [[0 for _x in range(width)] for _y in range(height)]
    transported_to = [[False for _x in range(width)] for _y in range(height)]

    for y, row in enumerate(rows):
        for x, cell in enumerate(row):
            if _is_oceanic_global_cell(cell):
                continue
            if not cell.has_river and _is_next_to_river(rows, x, y):
                next_units[y][x] += cell.rain_units
                continue
            destination = _downhill_destination(rows, x, y, rng)
            destination_x, destination_y = destination
            destination_cell = rows[destination_y][destination_x]
            if not _is_oceanic_global_cell(destination_cell):
                next_units[destination_y][destination_x] += cell.rain_units
                if destination != (x, y):
                    transported_to[destination_y][destination_x] = True

    for y, row in enumerate(rows):
        for x, cell in enumerate(row):
            if not cell.has_river:
                cell.rain_units = next_units[y][x]

    _mark_rivers(
        rows,
        hydrology_rules["river_threshold"],
    )
    return transported_to


def _apply_rain_erosion(
    rows: list[list[LocalCell]],
    rules: dict[str, Any],
    transported_to: list[list[bool]],
) -> None:
    erosion_threshold = rules["hydrology"].get("erosion_threshold")
    if not erosion_threshold:
        return
    for y, row in enumerate(rows):
        for x, cell in enumerate(row):
            if not transported_to[y][x]:
                continue
            if cell.has_river:
                continue
            if _is_oceanic_global_cell(cell):
                continue
            while cell.rain_units >= (cell.erosion_count + 1) * erosion_threshold:
                if not _lower_cell_altitude(cell, rules):
                    break
                _refresh_cell_biome(cell, rules)
                cell.erosion_count += 1


def _lower_cell_altitude(cell: LocalCell, rules: dict[str, Any]) -> bool:
    altitude = cell.layers["altitude"]
    if altitude.effective_value >= 9:
        return False
    new_effective = altitude.effective_value + 1
    new_local = ((new_effective - 1) % 3) + 1
    cell.layers["altitude"] = LayerValues(
        global_value=altitude.global_value,
        local_value=new_local,
        effective_value=new_effective,
        category=rules["layers"]["altitude"]["effective_scale"][str(new_effective)],
    )
    cell.terrain_type = cell.layers["altitude"].category
    return True


def _refresh_cell_biome(cell: LocalCell, rules: dict[str, Any]) -> None:
    biome_rule = _classify_biome(rules, cell.layers)
    cell.biome = biome_rule["name"]
    cell.symbol = biome_rule["symbol"]
    cell.color = biome_rule["color"]


def _downhill_destination(
    rows: list[list[LocalCell]],
    x: int,
    y: int,
    rng: random.Random,
) -> tuple[int, int]:
    origin_altitude = rows[y][x].layers["altitude"].effective_value
    downhill_candidates: list[tuple[int, int, int]] = []
    equal_height_candidates: list[tuple[int, int]] = []
    for neighbor_x, neighbor_y in _neighbor_positions(rows, x, y):
        neighbor = rows[neighbor_y][neighbor_x]
        neighbor_altitude = neighbor.layers["altitude"].effective_value
        if neighbor_altitude > origin_altitude:
            downhill_candidates.append((neighbor_altitude, neighbor_x, neighbor_y))
        elif neighbor_altitude == origin_altitude:
            equal_height_candidates.append((neighbor_x, neighbor_y))
    if downhill_candidates:
        lowest_altitude = max(altitude for altitude, _nx, _ny in downhill_candidates)
        lowest_neighbors = [
            (neighbor_x, neighbor_y)
            for altitude, neighbor_x, neighbor_y in downhill_candidates
            if altitude == lowest_altitude
        ]
        return rng.choice(lowest_neighbors)
    if equal_height_candidates:
        return rng.choice(equal_height_candidates)
    return x, y


def _mark_rivers(
    rows: list[list[LocalCell]],
    river_threshold: int,
) -> None:
    for y, row in enumerate(rows):
        for x, cell in enumerate(row):
            if _is_oceanic_global_cell(cell):
                continue
            if cell.rain_units >= river_threshold:
                cell.has_river = True
                cell.rain_units = river_threshold


def _connect_rivers(rows: list[list[LocalCell]], hydrology_rules: dict[str, Any]) -> None:
    if not hydrology_rules.get("connect_large_rivers_to_sea", False):
        return
    min_component_size = hydrology_rules.get("min_river_component_size_for_connection", 1)
    for _pass in range(hydrology_rules.get("river_connection_passes", 1)):
        changed = False
        for component in _river_components(rows):
            if len(component) < min_component_size:
                continue
            if _component_touches_sea(rows, component):
                continue
            start = _lowest_component_position(rows, component)
            target = _nearest_sea(rows, start[0], start[1])
            if target is None:
                continue
            path = _lowest_neighbor_route(rows, start, target)
            if not path:
                continue
            changed = _mark_river_path(rows, path, hydrology_rules["river_threshold"]) or changed
        if not changed:
            break


def _connect_short_water_gaps(rows: list[list[LocalCell]], hydrology_rules: dict[str, Any]) -> None:
    gap_distance = hydrology_rules.get("connect_water_gaps_distance")
    if gap_distance != 2:
        return
    river_threshold = hydrology_rules["river_threshold"]
    for y, row in enumerate(rows):
        for x, cell in enumerate(row):
            if not cell.has_river:
                continue
            for offset_x, offset_y in (
                (-2, 0),
                (-1, -1),
                (-1, 1),
                (0, -2),
                (0, 2),
                (1, -1),
                (1, 1),
                (2, 0),
            ):
                target_x = x + offset_x
                target_y = y + offset_y
                if not _is_inside(rows, target_x, target_y):
                    continue
                target = rows[target_y][target_x]
                if not target.has_river and not _is_oceanic_global_cell(target):
                    continue
                middle_positions = _shared_orthogonal_neighbors(rows, x, y, target_x, target_y)
                if not middle_positions:
                    continue
                mid_x, mid_y = max(
                    middle_positions,
                    key=lambda position: rows[position[1]][position[0]].layers["altitude"].effective_value,
                )
                middle = rows[mid_y][mid_x]
                if middle.has_river or _is_oceanic_global_cell(middle):
                    continue
                middle.has_river = True
                middle.rain_units = river_threshold


def _mark_river_path(
    rows: list[list[LocalCell]],
    path: list[tuple[int, int]],
    river_threshold: int,
) -> bool:
    changed = False
    for path_x, path_y in path:
        cell = rows[path_y][path_x]
        if _is_oceanic_global_cell(cell):
            continue
        if not cell.has_river:
            cell.has_river = True
            cell.rain_units = river_threshold
            changed = True
    return changed


def _river_components(rows: list[list[LocalCell]]) -> list[set[tuple[int, int]]]:
    components: list[set[tuple[int, int]]] = []
    visited: set[tuple[int, int]] = set()
    for y, row in enumerate(rows):
        for x, cell in enumerate(row):
            if not cell.has_river or (x, y) in visited:
                continue
            component = _flood_river_component(rows, x, y)
            visited.update(component)
            components.append(component)
    return components


def _flood_river_component(rows: list[list[LocalCell]], x: int, y: int) -> set[tuple[int, int]]:
    component = {(x, y)}
    frontier = [(x, y)]
    while frontier:
        current_x, current_y = frontier.pop()
        for neighbor_x, neighbor_y in _neighbor_positions(rows, current_x, current_y):
            neighbor_position = (neighbor_x, neighbor_y)
            if neighbor_position in component:
                continue
            if rows[neighbor_y][neighbor_x].has_river:
                component.add(neighbor_position)
                frontier.append(neighbor_position)
    return component


def _component_touches_sea(rows: list[list[LocalCell]], component: set[tuple[int, int]]) -> bool:
    for x, y in component:
        for neighbor_x, neighbor_y in _neighbor_positions(rows, x, y):
            if _is_oceanic_global_cell(rows[neighbor_y][neighbor_x]):
                return True
    return False


def _lowest_component_position(
    rows: list[list[LocalCell]],
    component: set[tuple[int, int]],
) -> tuple[int, int]:
    return max(
        component,
        key=lambda position: rows[position[1]][position[0]].layers["altitude"].effective_value,
    )


def _nearest_sea(rows: list[list[LocalCell]], x: int, y: int) -> tuple[int, int] | None:
    candidates: list[tuple[int, int, int]] = []
    for target_y, row in enumerate(rows):
        for target_x, cell in enumerate(row):
            if not _is_oceanic_global_cell(cell):
                continue
            distance = abs(target_x - x) + abs(target_y - y)
            candidates.append((distance, target_x, target_y))
    if not candidates:
        return None
    _distance, target_x, target_y = min(candidates)
    return target_x, target_y


def _lowest_neighbor_route(
    rows: list[list[LocalCell]],
    start: tuple[int, int],
    target: tuple[int, int],
) -> list[tuple[int, int]]:
    path = [start]
    visited = {start}
    current = start
    max_steps = len(rows) + len(rows[0])
    for _step in range(max_steps):
        if current == target:
            return path
        current_x, current_y = current
        candidates = [
            (neighbor_x, neighbor_y)
            for neighbor_x, neighbor_y in _neighbor_positions(rows, current_x, current_y)
            if (neighbor_x, neighbor_y) not in visited
        ]
        if not candidates:
            return []
        current_distance = abs(target[0] - current_x) + abs(target[1] - current_y)
        closer_candidates = [
            position
            for position in candidates
            if abs(target[0] - position[0]) + abs(target[1] - position[1]) < current_distance
        ]
        if closer_candidates:
            candidates = closer_candidates
        next_position = min(
            candidates,
            key=lambda position: (
                -rows[position[1]][position[0]].layers["altitude"].effective_value,
                abs(target[0] - position[0]) + abs(target[1] - position[1]),
            ),
        )
        path.append(next_position)
        visited.add(next_position)
        current = next_position
        if rows[current[1]][current[0]].has_river or _is_oceanic_global_cell(rows[current[1]][current[0]]):
            return path
    return []


def _is_oceanic_global_cell(cell: LocalCell) -> bool:
    return cell.oceanic


def _is_next_to_river(rows: list[list[LocalCell]], x: int, y: int) -> bool:
    return any(rows[neighbor_y][neighbor_x].has_river for neighbor_x, neighbor_y in _neighbor_positions(rows, x, y))


def _neighbor_positions(rows: list[list[LocalCell]], x: int, y: int) -> list[tuple[int, int]]:
    positions: list[tuple[int, int]] = []
    for offset_x, offset_y in ((0, -1), (1, 0), (0, 1), (-1, 0)):
        neighbor_x = x + offset_x
        neighbor_y = y + offset_y
        if 0 <= neighbor_y < len(rows) and 0 <= neighbor_x < len(rows[0]):
            positions.append((neighbor_x, neighbor_y))
    return positions


def _is_inside(rows: list[list[LocalCell]], x: int, y: int) -> bool:
    return 0 <= y < len(rows) and 0 <= x < len(rows[0])


def _shared_orthogonal_neighbors(
    rows: list[list[LocalCell]],
    first_x: int,
    first_y: int,
    second_x: int,
    second_y: int,
) -> list[tuple[int, int]]:
    first_neighbors = set(_neighbor_positions(rows, first_x, first_y))
    second_neighbors = set(_neighbor_positions(rows, second_x, second_y))
    return list(first_neighbors & second_neighbors)


def _generate_value_grid(
    rng: random.Random,
    width: int,
    height: int,
    weights: dict[str, int],
    generation_rules: dict[str, Any],
) -> list[list[int]]:
    mode = generation_rules.get("mode", "continuous")
    if mode != "continuous":
        return [
            [
                _roll_weighted_value(rng, weights)
                for _x in range(width)
            ]
            for _y in range(height)
        ]

    max_delta = generation_rules.get("max_neighbor_delta", 1)
    grid: list[list[int | None]] = [[None for _x in range(width)] for _y in range(height)]
    for y in range(height):
        for x in range(width):
            existing_neighbors = _existing_neighbor_values(grid, x, y)
            allowed_values = _allowed_continuous_values(existing_neighbors, max_delta)
            grid[y][x] = _roll_weighted_value(rng, _filter_weights(weights, allowed_values))
    return [[int(value) for value in row] for row in grid]


def _existing_neighbor_values(grid: list[list[int | None]], x: int, y: int) -> list[int]:
    values: list[int] = []
    for neighbor_y in range(max(0, y - 1), y + 1):
        for neighbor_x in range(max(0, x - 1), min(len(grid[0]), x + 2)):
            if neighbor_x == x and neighbor_y == y:
                continue
            value = grid[neighbor_y][neighbor_x]
            if value is not None:
                values.append(value)
    return values


def _allowed_continuous_values(neighbors: list[int], max_delta: int) -> list[int]:
    if not neighbors:
        return [1, 2, 3]
    minimum = max(1, max(neighbor - max_delta for neighbor in neighbors))
    maximum = min(3, min(neighbor + max_delta for neighbor in neighbors))
    if minimum > maximum:
        center = round(sum(neighbors) / len(neighbors))
        return [min(3, max(1, center))]
    return list(range(minimum, maximum + 1))


def _classify_biome(
    rules: dict[str, Any],
    layers: dict[LayerName, LayerValues],
) -> dict[str, str]:
    effective_layers = {
        layer: values.effective_value
        for layer, values in layers.items()
    }
    for biome in rules["biomes"]:
        if all(_in_range(effective_layers[layer], value_range) for layer, value_range in biome["conditions"].items()):
            return biome
    return rules["fallback_biome"]


def _roll_weighted_value(rng: random.Random, weights: dict[str, int]) -> int:
    values = [int(value) for value in weights]
    weighted_values = [weights[str(value)] for value in values]
    return rng.choices(values, weights=weighted_values, k=1)[0]


def _filter_weights(weights: dict[str, int], allowed_values: list[int]) -> dict[str, int]:
    return {
        str(value): weights[str(value)]
        for value in allowed_values
        if weights.get(str(value), 0) > 0
    }


def _in_range(value: int, value_range: list[int]) -> bool:
    minimum, maximum = value_range
    return minimum <= value <= maximum
