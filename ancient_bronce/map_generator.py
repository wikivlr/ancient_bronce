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


@dataclass(frozen=True)
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

    return WorldMap(
        width=size_rules["global_width"],
        height=size_rules["global_height"],
        local_width=size_rules["local_width"],
        local_height=size_rules["local_height"],
        global_cells=global_cells,
    )


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
                )
            )
        local_cells.append(row)
    return local_cells


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
