from __future__ import annotations

import json
import math
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
    """Generate a square-grid world using MapGen4-style causal layers."""
    rng = random.Random(seed)
    map_rules = rules["map"]
    local_width = map_rules["local_width"]
    local_height = map_rules["local_height"]
    width = map_rules["global_width"] * local_width
    height = map_rules["global_height"] * local_height

    elevation = _generate_elevation(width, height, rng)
    altitude_values = _elevation_to_altitude_values(elevation)
    downslope = _calculate_downslope(altitude_values, elevation, rng)
    flow = _calculate_flow(altitude_values, downslope)
    river_cells = _calculate_rivers(altitude_values, flow, rules)
    humidity_values = _calculate_humidity(altitude_values, river_cells, width, height, rng)
    temperature_values = _calculate_temperature(altitude_values, width, height, rng)

    world = _build_world(
        rules=rules,
        altitude_values=altitude_values,
        humidity_values=humidity_values,
        temperature_values=temperature_values,
        flow=flow,
        river_cells=river_cells,
    )
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


def _generate_elevation(width: int, height: int, rng: random.Random) -> list[list[float]]:
    plates = [
        (rng.uniform(-0.15, 1.15), rng.uniform(-0.15, 1.15), rng.uniform(0.25, 1.0))
        for _ in range(7)
    ]
    grid: list[list[float]] = []
    for y in range(height):
        row: list[float] = []
        ny = y / max(1, height - 1)
        for x in range(width):
            nx = x / max(1, width - 1)
            island = 1.0 - min(1.0, math.hypot(nx - 0.5, ny - 0.5) / 0.72)
            ridges = sum(
                weight * max(0.0, 1.0 - math.hypot(nx - px, ny - py) / 0.34)
                for px, py, weight in plates
            )
            broad_noise = _value_noise(nx * 3.0, ny * 3.0, rng)
            fine_noise = _value_noise(nx * 9.0 + 17.0, ny * 9.0 + 31.0, rng)
            row.append(0.52 * island + 0.34 * ridges + 0.10 * broad_noise + 0.04 * fine_noise)
        grid.append(row)
    return _normalize(_smooth(grid, passes=3))


def _elevation_to_altitude_values(elevation: list[list[float]]) -> list[list[int]]:
    thresholds = ((0.90, 1), (0.80, 2), (0.68, 3), (0.55, 4), (0.43, 5), (0.34, 6), (0.27, 7), (0.18, 8))
    return [
        [next((altitude for limit, altitude in thresholds if value >= limit), 9) for value in row]
        for row in elevation
    ]


def _calculate_downslope(
    altitude_values: list[list[int]],
    elevation: list[list[float]],
    rng: random.Random,
) -> list[list[tuple[int, int] | None]]:
    rows: list[list[tuple[int, int] | None]] = []
    for y, row in enumerate(altitude_values):
        downslope_row: list[tuple[int, int] | None] = []
        for x, altitude in enumerate(row):
            if altitude >= 7:
                downslope_row.append(None)
                continue
            candidates = [
                (nx, ny)
                for nx, ny in _grid_neighbors(altitude_values, x, y)
                if elevation[ny][nx] < elevation[y][x] or altitude_values[ny][nx] > altitude
            ]
            if not candidates:
                downslope_row.append(None)
                continue
            lowest = min(elevation[ny][nx] for nx, ny in candidates)
            best = [(nx, ny) for nx, ny in candidates if elevation[ny][nx] == lowest]
            downslope_row.append(rng.choice(best))
        rows.append(downslope_row)
    return rows


def _calculate_flow(
    altitude_values: list[list[int]],
    downslope: list[list[tuple[int, int] | None]],
) -> list[list[float]]:
    height = len(altitude_values)
    width = len(altitude_values[0])
    flow = [[0.0 for _x in range(width)] for _y in range(height)]
    order = sorted((altitude_values[y][x], x, y) for y in range(height) for x in range(width))
    for altitude, x, y in order:
        if altitude >= 7:
            continue
        flow[y][x] += max(0.2, (7 - altitude) * 0.35)
        destination = downslope[y][x]
        if destination is None:
            continue
        nx, ny = destination
        flow[ny][nx] += flow[y][x]
    return flow


def _calculate_rivers(
    altitude_values: list[list[int]],
    flow: list[list[float]],
    rules: dict[str, Any],
) -> set[tuple[int, int]]:
    if not rules.get("hydrology", {}).get("enabled", False):
        return set()
    threshold = rules.get("hydrology", {}).get("river_threshold", 21) / 2.2
    rivers = {
        (x, y)
        for y, row in enumerate(flow)
        for x, amount in enumerate(row)
        if altitude_values[y][x] < 7 and amount >= threshold
    }
    return _connect_short_water_gaps(altitude_values, rivers)


def _calculate_humidity(
    altitude_values: list[list[int]],
    rivers: set[tuple[int, int]],
    width: int,
    height: int,
    rng: random.Random,
) -> list[list[int]]:
    water = {
        (x, y)
        for y in range(height)
        for x in range(width)
        if altitude_values[y][x] >= 7 or (x, y) in rivers
    }
    values: list[list[int]] = []
    for y in range(height):
        row: list[int] = []
        latitude_dryness = abs((y / max(1, height - 1)) - 0.52) * 1.2
        for x in range(width):
            nearest_water = min(abs(wx - x) + abs(wy - y) for wx, wy in water)
            altitude = altitude_values[y][x]
            moisture = 1.0 - min(1.0, nearest_water / 18.0)
            if altitude in (1, 2):
                moisture -= 0.25
            moisture += 0.16 * _value_noise(x / 14.0 + 101.0, y / 14.0 + 211.0, rng)
            dryness = 1.0 - moisture + latitude_dryness
            row.append(_clamp(round(1 + dryness * 5.2), 1, 9))
        values.append(row)
    return _smooth_discrete(values, passes=1)


def _calculate_temperature(
    altitude_values: list[list[int]],
    width: int,
    height: int,
    rng: random.Random,
) -> list[list[int]]:
    values: list[list[int]] = []
    for y in range(height):
        row: list[int] = []
        latitude = abs((y / max(1, height - 1)) - 0.5) * 2
        for x in range(width):
            altitude = altitude_values[y][x]
            coldness = latitude * 3.8 + max(0, 7 - altitude) * 0.38
            coldness += 0.45 * _value_noise(x / 18.0 + 307.0, y / 18.0 + 419.0, rng)
            row.append(_clamp(round(1 + coldness), 1, 9))
        values.append(row)
    return _smooth_discrete(values, passes=1)


def _build_world(
    rules: dict[str, Any],
    altitude_values: list[list[int]],
    humidity_values: list[list[int]],
    temperature_values: list[list[int]],
    flow: list[list[float]],
    river_cells: set[tuple[int, int]],
) -> WorldMap:
    map_rules = rules["map"]
    global_width = map_rules["global_width"]
    global_height = map_rules["global_height"]
    local_width = map_rules["local_width"]
    local_height = map_rules["local_height"]
    global_cells: list[list[GlobalCell]] = []

    for global_y in range(global_height):
        global_row: list[GlobalCell] = []
        for global_x in range(global_width):
            global_layers = {
                "temperature": _global_layer_value(temperature_values, global_x, global_y, local_width, local_height),
                "humidity": _global_layer_value(humidity_values, global_x, global_y, local_width, local_height),
                "altitude": _global_layer_value(altitude_values, global_x, global_y, local_width, local_height),
            }
            local_cells: list[list[LocalCell]] = []
            for local_y in range(local_height):
                local_row: list[LocalCell] = []
                for local_x in range(local_width):
                    world_x = global_x * local_width + local_x
                    world_y = global_y * local_height + local_y
                    layers = {
                        "temperature": _layer_values(rules, "temperature", temperature_values[world_y][world_x]),
                        "humidity": _layer_values(rules, "humidity", humidity_values[world_y][world_x]),
                        "altitude": _layer_values(rules, "altitude", altitude_values[world_y][world_x]),
                    }
                    biome = _classify_biome(rules, layers)
                    local_row.append(
                        LocalCell(
                            global_x=global_x,
                            global_y=global_y,
                            local_x=local_x,
                            local_y=local_y,
                            layers=layers,
                            terrain_type=layers["altitude"].category,
                            biome=biome["name"],
                            symbol=biome["symbol"],
                            color=biome["color"],
                            rain_units=round(flow[world_y][world_x], 2),
                            has_river=(world_x, world_y) in river_cells,
                            erosion_count=0,
                            oceanic=altitude_values[world_y][world_x] >= 8,
                            resources={},
                        )
                    )
                local_cells.append(local_row)
            global_row.append(GlobalCell(global_x, global_y, global_layers, local_cells))
        global_cells.append(global_row)

    return WorldMap(global_width, global_height, local_width, local_height, global_cells)


def _layer_values(rules: dict[str, Any], layer: LayerName, effective: int) -> LayerValues:
    global_value = ((effective - 1) // 3) + 1
    local_value = ((effective - 1) % 3) + 1
    return LayerValues(
        global_value=global_value,
        local_value=local_value,
        effective_value=effective,
        category=rules["layers"][layer]["effective_scale"][str(effective)],
    )


def _global_layer_value(values: list[list[int]], global_x: int, global_y: int, local_width: int, local_height: int) -> int:
    sample = [
        values[y][x]
        for y in range(global_y * local_height, (global_y + 1) * local_height)
        for x in range(global_x * local_width, (global_x + 1) * local_width)
    ]
    return ((round(sum(sample) / len(sample)) - 1) // 3) + 1


def _apply_resources(world: WorldMap, rules: dict[str, Any], rng: random.Random) -> None:
    rows = flatten_local_cells(world)
    height = len(rows)
    width = len(rows[0])
    resource_rules = rules["resources"]

    for row in rows:
        for cell in row:
            cell.resources = {resource_id: False for resource_id in resource_rules.get("types", {})}

    for resource_id, resource_rule in resource_rules.get("types", {}).items():
        suitable = [[_resource_is_suitable(cell, resource_rule) for cell in row] for row in rows]
        present = [
            [suitable[y][x] and rng.random() < resource_rule["base_chance"] for x in range(width)]
            for y in range(height)
        ]
        for _pass in range(resource_rule.get("spread_passes", 0)):
            next_present = [row[:] for row in present]
            for y in range(height):
                for x in range(width):
                    if present[y][x] or not suitable[y][x]:
                        continue
                    occupied_neighbors = sum(present[ny][nx] for nx, ny in _grid_neighbors(rows, x, y))
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
    return any(_cell_matches_habitat(cell, habitat) for habitat in resource_rule.get("habitats", []))


def _cell_matches_habitat(cell: LocalCell, habitat: dict[str, Any]) -> bool:
    layer_conditions = habitat.get("layers", {})
    if any(not _in_range(cell.layers[layer].effective_value, value_range) for layer, value_range in layer_conditions.items()):
        return False
    if "biomes" in habitat and cell.biome not in habitat["biomes"]:
        return False
    if "has_river" in habitat and cell.has_river != habitat["has_river"]:
        return False
    if "oceanic" in habitat and cell.oceanic != habitat["oceanic"]:
        return False
    return True


def _classify_biome(rules: dict[str, Any], layers: dict[LayerName, LayerValues]) -> dict[str, str]:
    effective_layers = {layer: values.effective_value for layer, values in layers.items()}
    for biome in rules["biomes"]:
        if all(_in_range(effective_layers[layer], value_range) for layer, value_range in biome["conditions"].items()):
            return biome
    return rules["fallback_biome"]


def _connect_short_water_gaps(altitude_values: list[list[int]], rivers: set[tuple[int, int]]) -> set[tuple[int, int]]:
    connected = set(rivers)
    water = {
        (x, y)
        for y, row in enumerate(altitude_values)
        for x, altitude in enumerate(row)
        if altitude >= 7
    }
    for x, y in list(rivers):
        for ox, oy in ((-2, 0), (2, 0), (0, -2), (0, 2)):
            target = (x + ox, y + oy)
            if target not in rivers and target not in water:
                continue
            middle = (x + ox // 2, y + oy // 2)
            if 0 <= middle[1] < len(altitude_values) and 0 <= middle[0] < len(altitude_values[0]):
                if altitude_values[middle[1]][middle[0]] < 7:
                    connected.add(middle)
    return connected


def _smooth(grid: list[list[float]], passes: int) -> list[list[float]]:
    result = grid
    for _ in range(passes):
        result = [
            [
                (value * 2 + sum(result[ny][nx] for nx, ny in _grid_neighbors(result, x, y)))
                / (2 + len(_grid_neighbors(result, x, y)))
                for x, value in enumerate(row)
            ]
            for y, row in enumerate(result)
        ]
    return result


def _smooth_discrete(grid: list[list[int]], passes: int) -> list[list[int]]:
    result = grid
    for _ in range(passes):
        result = [
            [
                _clamp(
                    round((value * 2 + sum(result[ny][nx] for nx, ny in _grid_neighbors(result, x, y))) / (2 + len(_grid_neighbors(result, x, y)))),
                    1,
                    9,
                )
                for x, value in enumerate(row)
            ]
            for y, row in enumerate(result)
        ]
    return result


def _normalize(grid: list[list[float]]) -> list[list[float]]:
    values = [value for row in grid for value in row]
    minimum = min(values)
    span = max(values) - minimum or 1.0
    return [[(value - minimum) / span for value in row] for row in grid]


def _value_noise(x: float, y: float, rng: random.Random) -> float:
    ix = math.floor(x)
    iy = math.floor(y)
    fx = x - ix
    fy = y - iy
    a = _hash_noise(ix, iy, rng)
    b = _hash_noise(ix + 1, iy, rng)
    c = _hash_noise(ix, iy + 1, rng)
    d = _hash_noise(ix + 1, iy + 1, rng)
    return _lerp(_lerp(a, b, _smoothstep(fx)), _lerp(c, d, _smoothstep(fx)), _smoothstep(fy))


def _hash_noise(x: int, y: int, rng: random.Random) -> float:
    state = rng.getstate()
    rng.seed((x * 73856093) ^ (y * 19349663) ^ 83492791)
    value = rng.random()
    rng.setstate(state)
    return value


def _grid_neighbors(grid: list[list[Any]], x: int, y: int) -> list[tuple[int, int]]:
    positions: list[tuple[int, int]] = []
    for offset_x, offset_y in ((0, -1), (1, 0), (0, 1), (-1, 0)):
        nx = x + offset_x
        ny = y + offset_y
        if 0 <= ny < len(grid) and 0 <= nx < len(grid[0]):
            positions.append((nx, ny))
    return positions


def _in_range(value: int, value_range: list[int]) -> bool:
    minimum, maximum = value_range
    return minimum <= value <= maximum


def _clamp(value: int, minimum: int, maximum: int) -> int:
    return min(maximum, max(minimum, value))


def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def _smoothstep(value: float) -> float:
    return value * value * (3 - 2 * value)
