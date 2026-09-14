from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from ancient_bronce.map_generator import flatten_local_cells, generate_world, load_rules, world_to_dict


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RULES_PATH = PROJECT_ROOT / "rules" / "map_rules.json"


class ResourceGenerationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.rules = load_rules(RULES_PATH)
        cls.world = generate_world(cls.rules, seed=7)
        cls.cells = [cell for row in flatten_local_cells(cls.world) for cell in row]

    def test_every_resource_is_a_boolean_layer_on_every_cell(self) -> None:
        resource_ids = set(self.rules["resources"]["types"])
        for cell in self.cells:
            self.assertEqual(set(cell.resources), resource_ids)
            self.assertTrue(all(type(value) is bool for value in cell.resources.values()))

    def test_resource_generation_is_deterministic_for_a_seed(self) -> None:
        second_world = generate_world(self.rules, seed=7)
        first_resources = [cell.resources for cell in self.cells]
        second_resources = [
            cell.resources
            for row in flatten_local_cells(second_world)
            for cell in row
        ]
        self.assertEqual(first_resources, second_resources)

    def test_copper_only_occurs_in_dry_high_cells(self) -> None:
        copper_cells = [cell for cell in self.cells if cell.resources["copper"]]
        self.assertGreater(len(copper_cells), 0)
        for cell in copper_cells:
            self.assertIn(cell.layers["altitude"].effective_value, range(1, 5))
            self.assertIn(cell.layers["humidity"].effective_value, range(6, 10))

    def test_wood_only_occurs_in_forests_and_jungles(self) -> None:
        wood_cells = [cell for cell in self.cells if cell.resources["wood"]]
        self.assertGreater(len(wood_cells), 0)
        self.assertTrue(
            all(cell.biome in {"Temperate forest", "Jungle"} for cell in wood_cells)
        )

    def test_fish_only_occurs_in_water_or_rivers(self) -> None:
        fish_cells = [cell for cell in self.cells if cell.resources["fish"]]
        self.assertGreater(len(fish_cells), 0)
        self.assertTrue(
            all(
                cell.layers["altitude"].effective_value >= 7 or cell.has_river
                for cell in fish_cells
            )
        )

    def test_resources_can_be_disabled(self) -> None:
        rules = copy.deepcopy(self.rules)
        rules["resources"]["enabled"] = False
        world = generate_world(rules, seed=7)
        cells = [cell for row in flatten_local_cells(world) for cell in row]
        self.assertTrue(all(cell.resources == {} for cell in cells))

    def test_serialized_resource_values_are_json_booleans(self) -> None:
        serialized = json.loads(json.dumps(world_to_dict(self.world)))
        resources = serialized["global_cells"][0][0]["local_cells"][0][0]["resources"]
        self.assertTrue(all(type(value) is bool for value in resources.values()))


if __name__ == "__main__":
    unittest.main()
