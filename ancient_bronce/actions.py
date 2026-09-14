from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Position:
    x: int
    y: int


@dataclass
class HumanState:
    human_id: str
    name: str
    position: Position
    health: int = 3
    hunger: int = 3
    thirst: int = 3
    fatigue: int = 3
    temperature: int = 0
    inventory: dict[str, int] = field(default_factory=dict)
    movement_used: int = 0
    action_counts: dict[str, int] = field(default_factory=dict)
    turn_ended: bool = False


class ActionError(ValueError):
    pass


def load_game_rules(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as file:
        return json.load(file)


def create_human(
    human_id: str,
    name: str,
    position: Position,
    rules: dict[str, Any],
) -> HumanState:
    human_rules = rules["human"]
    return HumanState(
        human_id=human_id,
        name=name,
        position=position,
        health=human_rules["max_health"],
        hunger=human_rules["max_hunger"],
        thirst=human_rules["max_thirst"],
        fatigue=human_rules["max_fatigue"],
    )


def begin_turn(
    human: HumanState,
    rules: dict[str, Any],
    effective_temperature: int,
) -> None:
    human_rules = rules["human"]
    human.hunger = max(0, human.hunger - human_rules["hunger_loss_per_turn"])
    human.thirst = max(0, human.thirst - human_rules["thirst_loss_per_turn"])
    human.temperature = human_rules["temperature_by_effective_value"][
        str(effective_temperature)
    ]
    human.movement_used = 0
    human.action_counts = {}
    human.turn_ended = False


def perform_action(
    human: HumanState,
    action_id: str,
    rules: dict[str, Any],
) -> None:
    action = _action_rule(action_id, rules)
    _validate_action(human, action_id, action)
    human.fatigue -= action["fatigue_cost"]
    human.action_counts[action_id] = human.action_counts.get(action_id, 0) + 1

    if action_id == "rest":
        maximum = rules["human"]["max_fatigue"]
        human.fatigue = min(maximum, human.fatigue + action["fatigue_recovery"])
    if action.get("ends_person_turn", False):
        human.turn_ended = True


def move_human(
    human: HumanState,
    path: list[Position],
    rules: dict[str, Any],
    world_width: int,
    world_height: int,
) -> None:
    if not path:
        raise ActionError("Movement requires at least one destination cell.")
    action = _action_rule("move", rules)
    _validate_action(human, "move", action)
    _validate_path(human.position, path, world_width, world_height)

    movement_limit = rules["human"]["movement_cells_per_turn"]
    if human.movement_used + len(path) > movement_limit:
        raise ActionError(f"A human can move at most {movement_limit} cells per turn.")

    human.fatigue -= action["fatigue_cost"]
    human.movement_used += len(path)
    human.action_counts["move"] = human.action_counts.get("move", 0) + 1
    human.position = path[-1]


def eat(human: HumanState, nutrition: int, rules: dict[str, Any]) -> None:
    if nutrition <= 0:
        raise ActionError("Nutrition must be positive.")
    perform_action(human, "eat", rules)
    human.hunger = min(rules["human"]["max_hunger"], human.hunger + nutrition)


def drink(human: HumanState, hydration: int, rules: dict[str, Any]) -> None:
    if hydration <= 0:
        raise ActionError("Hydration must be positive.")
    perform_action(human, "drink", rules)
    human.thirst = min(rules["human"]["max_thirst"], human.thirst + hydration)


def _action_rule(action_id: str, rules: dict[str, Any]) -> dict[str, Any]:
    try:
        return rules["actions"][action_id]
    except KeyError as error:
        raise ActionError(f"Unknown action: {action_id}") from error


def _validate_action(
    human: HumanState,
    action_id: str,
    action: dict[str, Any],
) -> None:
    if human.turn_ended:
        raise ActionError("This human has already ended their turn.")
    if human.fatigue < action["fatigue_cost"]:
        raise ActionError("This human does not have enough fatigue charges.")
    limit = action.get("limit_per_turn")
    if limit is not None and human.action_counts.get(action_id, 0) >= limit:
        raise ActionError(f"Action {action_id} has reached its turn limit.")


def _validate_path(
    origin: Position,
    path: list[Position],
    world_width: int,
    world_height: int,
) -> None:
    previous = origin
    for position in path:
        if not (0 <= position.x < world_width and 0 <= position.y < world_height):
            raise ActionError("Movement cannot leave the local world map.")
        distance = abs(position.x - previous.x) + abs(position.y - previous.y)
        if distance != 1:
            raise ActionError("Movement path must use orthogonally adjacent cells.")
        previous = position
