from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ancient_bronce.actions import HumanState, perform_action
from ancient_bronce.map_generator import LocalCell


@dataclass
class HumanGroupState:
    group_id: str
    human_ids: set[str]
    knowledge: set[str] = field(default_factory=set)


class KnowledgeError(ValueError):
    pass


def load_knowledge_rules(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as file:
        return json.load(file)


def research_knowledge(
    group: HumanGroupState,
    researcher: HumanState,
    all_humans: list[HumanState],
    knowledge_id: str,
    cell: LocalCell,
    knowledge_rules: dict[str, Any],
    game_rules: dict[str, Any],
) -> str:
    rule = _knowledge_rule(knowledge_id, knowledge_rules)
    members = _group_members(group, all_humans)
    if researcher.human_id not in group.human_ids:
        raise KnowledgeError("The researcher is not a member of this group.")
    if knowledge_id in group.knowledge:
        raise KnowledgeError(f"Knowledge already researched: {knowledge_id}")
    missing_prerequisites = set(rule.get("prerequisites", [])) - group.knowledge
    if missing_prerequisites:
        raise KnowledgeError(
            f"Missing knowledge prerequisites: {sorted(missing_prerequisites)}"
        )

    _validate_group_requirements(members, rule.get("group_requirements", {}))
    matching_path = next(
        (
            path
            for path in rule.get("discovery_paths", [])
            if _discovery_path_matches(researcher, cell, path)
        ),
        None,
    )
    if matching_path is None:
        raise KnowledgeError("No discovery path requirements are currently met.")

    perform_action(researcher, "research", game_rules)
    group.knowledge.add(knowledge_id)
    return matching_path["id"]


def can_build(
    group: HumanGroupState,
    construction_id: str,
    cell: LocalCell,
    knowledge_rules: dict[str, Any],
) -> bool:
    try:
        construction = knowledge_rules["constructions"][construction_id]
    except KeyError as error:
        raise KnowledgeError(f"Unknown construction: {construction_id}") from error
    required = set(construction.get("required_knowledge", []))
    return required.issubset(group.knowledge) and _cell_matches(cell, construction.get("cell", {}))


def required_hungry_humans(group_size: int, requirement: dict[str, Any]) -> int:
    if requirement.get("rounding") != "floor":
        raise KnowledgeError("Only floor hungry-fraction rounding is supported.")
    return group_size * requirement["numerator"] // requirement["denominator"]


def _knowledge_rule(knowledge_id: str, rules: dict[str, Any]) -> dict[str, Any]:
    try:
        return rules["knowledge"][knowledge_id]
    except KeyError as error:
        raise KnowledgeError(f"Unknown knowledge: {knowledge_id}") from error


def _group_members(
    group: HumanGroupState,
    all_humans: list[HumanState],
) -> list[HumanState]:
    by_id = {human.human_id: human for human in all_humans}
    missing = group.human_ids - set(by_id)
    if missing:
        raise KnowledgeError(f"Missing group humans: {sorted(missing)}")
    return [by_id[human_id] for human_id in group.human_ids]


def _validate_group_requirements(
    members: list[HumanState],
    requirements: dict[str, Any],
) -> None:
    hungry_requirement = requirements.get("hungry_fraction")
    if hungry_requirement is None:
        return
    required = required_hungry_humans(len(members), hungry_requirement)
    hungry = sum(
        human.hunger < hungry_requirement["hunger_below"]
        for human in members
    )
    if hungry < required:
        raise KnowledgeError(
            f"Not enough hungry humans in the group: {hungry}/{required}."
        )


def _discovery_path_matches(
    researcher: HumanState,
    cell: LocalCell,
    path: dict[str, Any],
) -> bool:
    inventory_requirement = path.get("researcher_inventory", {})
    if any(
        researcher.inventory.get(item_id, 0) < amount
        for item_id, amount in inventory_requirement.items()
    ):
        return False
    return _cell_matches(cell, path.get("cell", {}))


def _cell_matches(cell: LocalCell, requirements: dict[str, Any]) -> bool:
    if "biomes" in requirements and cell.biome not in requirements["biomes"]:
        return False
    if "has_river" in requirements and cell.has_river != requirements["has_river"]:
        return False
    return True
