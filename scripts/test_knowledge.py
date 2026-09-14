from __future__ import annotations

import unittest
from pathlib import Path
from types import SimpleNamespace

from ancient_bronce.actions import Position, create_human, load_game_rules
from ancient_bronce.knowledge import (
    HumanGroupState,
    KnowledgeError,
    can_build,
    can_craft,
    load_knowledge_rules,
    recipe_for,
    record_group_history,
    required_hungry_humans,
    research_knowledge,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
GAME_RULES_PATH = PROJECT_ROOT / "rules" / "game_rules.json"
KNOWLEDGE_RULES_PATH = PROJECT_ROOT / "rules" / "knowledge_rules.json"


class KnowledgeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.game_rules = load_game_rules(GAME_RULES_PATH)
        self.knowledge_rules = load_knowledge_rules(KNOWLEDGE_RULES_PATH)
        self.humans = [
            create_human(f"human-{index}", f"Human {index}", Position(index, 0), self.game_rules)
            for index in range(5)
        ]
        self.group = HumanGroupState(
            group_id="group-1",
            human_ids={human.human_id for human in self.humans},
        )
        self.researcher = self.humans[0]

    def _make_hungry(self, amount: int) -> None:
        for human in self.humans[:amount]:
            human.hunger = 1

    def test_hungry_requirement_uses_half_rounded_down(self) -> None:
        requirement = self.knowledge_rules["knowledge"]["agriculture"][
            "group_requirements"
        ]["population_conditions"][0]
        self.assertEqual(required_hungry_humans(5, requirement), 2)
        self.assertEqual(required_hungry_humans(6, requirement), 3)

    def test_wheat_path_researches_agriculture_on_plains(self) -> None:
        self._make_hungry(2)
        self.researcher.inventory["wheat"] = 1
        plains = SimpleNamespace(biome="Plains", has_river=False)
        path = research_knowledge(
            self.group,
            self.researcher,
            self.humans,
            "agriculture",
            plains,
            self.knowledge_rules,
            self.game_rules,
        )
        self.assertEqual(path, "wheat_observation")
        self.assertIn("agriculture", self.group.knowledge)
        self.assertIn("wheat_farming", self.group.knowledge)
        self.assertNotIn("rice_farming", self.group.knowledge)
        self.assertEqual(self.researcher.fatigue, 2)

    def test_rice_path_researches_agriculture_on_river(self) -> None:
        self._make_hungry(2)
        self.researcher.inventory["rice"] = 1
        river = SimpleNamespace(biome="Hills", has_river=True)
        path = research_knowledge(
            self.group,
            self.researcher,
            self.humans,
            "agriculture",
            river,
            self.knowledge_rules,
            self.game_rules,
        )
        self.assertEqual(path, "rice_observation")
        self.assertIn("agriculture", self.group.knowledge)
        self.assertIn("rice_farming", self.group.knowledge)

    def test_hunger_must_be_strictly_below_two(self) -> None:
        self.humans[0].hunger = 2
        self.humans[1].hunger = 2
        self.researcher.inventory["wheat"] = 1
        plains = SimpleNamespace(biome="Plains", has_river=False)
        with self.assertRaises(KnowledgeError):
            research_knowledge(
                self.group,
                self.researcher,
                self.humans,
                "agriculture",
                plains,
                self.knowledge_rules,
                self.game_rules,
            )

    def test_wrong_cell_or_missing_crop_blocks_discovery(self) -> None:
        self._make_hungry(2)
        hills = SimpleNamespace(biome="Hills", has_river=False)
        with self.assertRaises(KnowledgeError):
            research_knowledge(
                self.group,
                self.researcher,
                self.humans,
                "agriculture",
                hills,
                self.knowledge_rules,
                self.game_rules,
            )

    def test_construction_requires_knowledge_and_correct_cell(self) -> None:
        plains = SimpleNamespace(biome="Plains", has_river=False, resources={})
        river = SimpleNamespace(biome="Hills", has_river=True, resources={})
        self.assertFalse(can_build(self.group, "wheat_field", plains, self.knowledge_rules))
        self.group.knowledge.update({"agriculture", "wheat_farming"})
        self.assertTrue(can_build(self.group, "wheat_field", plains, self.knowledge_rules))
        self.assertFalse(can_build(self.group, "wheat_field", river, self.knowledge_rules))
        self.assertFalse(can_build(self.group, "rice_paddy", river, self.knowledge_rules))
        self.group.knowledge.add("rice_farming")
        self.assertTrue(can_build(self.group, "rice_paddy", river, self.knowledge_rules))

    def test_shelter_material_unlocks_only_its_own_recipe(self) -> None:
        for human in self.humans[:2]:
            human.temperature = -1
        self.researcher.inventory["wood"] = 1
        cell = SimpleNamespace(biome="Hills", has_river=False, resources={})
        research_knowledge(
            self.group,
            self.researcher,
            self.humans,
            "wood_shelter",
            cell,
            self.knowledge_rules,
            self.game_rules,
        )
        self.assertTrue(can_build(self.group, "wood_shelter", cell, self.knowledge_rules))
        self.assertFalse(can_build(self.group, "stone_shelter", cell, self.knowledge_rules))
        self.assertEqual(
            recipe_for("constructions", "wood_shelter", self.knowledge_rules),
            {"wood": 12},
        )

    def test_fire_requires_cold_history_and_both_materials(self) -> None:
        for human in self.humans[:2]:
            human.temperature = -1
        self.researcher.inventory.update({"wood": 1, "stone": 1})
        cell = SimpleNamespace(biome="Hills", has_river=False, resources={})
        with self.assertRaises(KnowledgeError):
            research_knowledge(
                self.group, self.researcher, self.humans, "fire", cell,
                self.knowledge_rules, self.game_rules,
            )
        record_group_history(self.group, "turns_cold", 3)
        research_knowledge(
            self.group, self.researcher, self.humans, "fire", cell,
            self.knowledge_rules, self.game_rules,
        )
        self.assertTrue(can_build(self.group, "campfire", cell, self.knowledge_rules))

    def test_stone_tools_require_collection_experience(self) -> None:
        self.researcher.inventory.update({"wood": 1, "stone": 1})
        cell = SimpleNamespace(biome="Hills", has_river=False, resources={})
        record_group_history(self.group, "collected_total", 20)
        research_knowledge(
            self.group, self.researcher, self.humans, "stone_tools", cell,
            self.knowledge_rules, self.game_rules,
        )
        self.assertTrue(can_craft(self.group, "stone_axe", self.knowledge_rules))
        self.assertEqual(
            recipe_for("items", "stone_pick", self.knowledge_rules),
            {"stone": 3, "wood": 1},
        )

    def test_fishing_requires_fish_in_cell(self) -> None:
        self._make_hungry(2)
        self.researcher.inventory["wood"] = 1
        fishing_cell = SimpleNamespace(
            biome="Shallow waters", has_river=False, resources={"fish": 12}
        )
        research_knowledge(
            self.group, self.researcher, self.humans, "fishing", fishing_cell,
            self.knowledge_rules, self.game_rules,
        )
        self.assertTrue(can_craft(self.group, "fishing_spear", self.knowledge_rules))

    def test_domestication_requires_attempts_animal_and_any_feed(self) -> None:
        self.researcher.inventory["cabbages"] = 1
        sheep_cell = SimpleNamespace(
            biome="Plains", has_river=False, resources={"sheep": 8}
        )
        record_group_history(self.group, "domestication_attempts", 3, key="sheep")
        research_knowledge(
            self.group, self.researcher, self.humans, "sheep_domestication", sheep_cell,
            self.knowledge_rules, self.game_rules,
        )
        self.assertIn("herd_sheep", self.group.abilities)

    def test_pottery_requires_fire(self) -> None:
        self.researcher.inventory["clay"] = 1
        river = SimpleNamespace(biome="Plains", has_river=True, resources={})
        with self.assertRaises(KnowledgeError):
            research_knowledge(
                self.group, self.researcher, self.humans, "pottery", river,
                self.knowledge_rules, self.game_rules,
            )
        self.group.knowledge.add("fire")
        research_knowledge(
            self.group, self.researcher, self.humans, "pottery", river,
            self.knowledge_rules, self.game_rules,
        )
        self.assertTrue(can_craft(self.group, "clay_vessel", self.knowledge_rules))

    def test_all_unlock_references_and_recipes_are_valid(self) -> None:
        knowledge_ids = set(self.knowledge_rules["knowledge"])
        construction_ids = set(self.knowledge_rules["constructions"])
        item_ids = set(self.knowledge_rules["items"])
        for rule in self.knowledge_rules["knowledge"].values():
            self.assertTrue(set(rule.get("prerequisites", [])).issubset(knowledge_ids))
            self.assertTrue(
                set(rule.get("unlocks_constructions", [])).issubset(construction_ids)
            )
            self.assertTrue(set(rule.get("unlocks_items", [])).issubset(item_ids))
            for path in rule.get("discovery_paths", []):
                self.assertTrue(
                    set(path.get("also_unlocks_knowledge", [])).issubset(knowledge_ids)
                )
        for recipe_group in ("constructions", "items"):
            for recipe in self.knowledge_rules[recipe_group].values():
                self.assertTrue(recipe["recipe"])
                self.assertTrue(all(amount > 0 for amount in recipe["recipe"].values()))


if __name__ == "__main__":
    unittest.main()
